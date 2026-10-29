
#include <WiFi.h>
#include <Wire.h>
#include <Adafruit_ADS1X15.h>
#include <PubSubClient.h>
#include <math.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>

#include <mbedtls/gcm.h>
#include <mbedtls/base64.h>
#include <esp_system.h>

#include "secrets.h"

// ============================================================
// NETWORK AND MQTT CONFIGURATION
// ============================================================

const char* MQTT_BROKER = "10.182.68.229";
const int MQTT_PORT = 1883;
const char* MQTT_TOPIC = "secure-bms/telemetry";

WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);
Adafruit_ADS1115 ads;

// ============================================================
// HARDWARE CONFIGURATION
// ============================================================

#define COMPARATOR_PIN 26
#define BUZZER_PIN 25
#define MOSFET_GATE 27

const float FIXED_RESISTOR = 10000.0;
const float SUPPLY_VOLTAGE = 3.3;
const float R0 = 100000.0;
const float BETA = 3950.0;
const float T0_KELVIN = 298.15;

// ============================================================
// TIMING
// ============================================================

const unsigned long LOG_INTERVAL = 1000;
const unsigned long WIFI_RETRY_INTERVAL = 10000;
const unsigned long MQTT_RETRY_INTERVAL = 5000;

unsigned long lastWiFiAttempt = 0;
unsigned long lastMQTTAttempt = 0;
unsigned long lastLog = 0;
unsigned long stateStartTime = 0;
unsigned long alertStartTime = 0;
unsigned long totalAlertDuration = 0;

// ============================================================
// TELEMETRY STATE
// ============================================================

unsigned long alertEventCount = 0;
unsigned long sensorFaultCount = 0;

float peakTemperature = -1000.0;
float minimumVoltage = 1000.0;
float maximumVoltage = -1000.0;

enum SystemState {
  NORMAL_STATE,
  ALERT_STATE,
  SENSOR_FAULT_STATE
};

SystemState currentState = NORMAL_STATE;

const bool TEST_SENSOR_FAULT = false;
const bool LOAD_ENABLE = false;

volatile bool safetyTripLatched = false;

// ============================================================
// AES-128-GCM CONFIGURATION
// ============================================================

static uint8_t aesKey[16];
static uint8_t noncePrefix[8];

static uint32_t messageCounter = 0;
static bool aesReady = false;

// ============================================================
// SAFETY INTERRUPT
// ============================================================

void IRAM_ATTR comparatorFallingISR() {
  safetyTripLatched = true;

  digitalWrite(MOSFET_GATE, LOW);
  digitalWrite(BUZZER_PIN, LOW);
}

// ============================================================
// SYSTEM STATE HELPERS
// ============================================================

const char* stateName(SystemState state) {
  switch (state) {
    case NORMAL_STATE:
      return "NORMAL";

    case ALERT_STATE:
      return "TEMPERATURE_ALERT";

    case SENSOR_FAULT_STATE:
      return "SENSOR_FAULT";

    default:
      return "UNKNOWN";
  }
}

void changeState(SystemState newState) {
  if (newState == currentState) {
    return;
  }

  unsigned long now = millis();

  if (currentState == ALERT_STATE) {
    totalAlertDuration += now - alertStartTime;
  }

  Serial.print("[EVENT] ");
  Serial.print(now);
  Serial.print(" ms | ");
  Serial.print(stateName(currentState));
  Serial.print(" -> ");
  Serial.println(stateName(newState));

  if (newState == ALERT_STATE) {
    alertEventCount++;
    alertStartTime = now;
  }

  if (newState == SENSOR_FAULT_STATE) {
    sensorFaultCount++;
  }

  currentState = newState;
  stateStartTime = now;
}

unsigned long getAlertDuration() {
  if (currentState == ALERT_STATE) {
    return totalAlertDuration + millis() - alertStartTime;
  }

  return totalAlertDuration;
}

// ============================================================
// OUTPUT CONTROL
// ============================================================

void setOutputs() {
  bool alertActive = (currentState != NORMAL_STATE);

  bool loadOn =
      (currentState == NORMAL_STATE) &&
      LOAD_ENABLE &&
      !safetyTripLatched;

  digitalWrite(BUZZER_PIN, alertActive ? LOW : HIGH);
  digitalWrite(MOSFET_GATE, loadOn ? HIGH : LOW);
}

// ============================================================
// AES KEY INITIALIZATION
// ============================================================

bool initializeAES() {
  size_t keyLength = 0;

  int result = mbedtls_base64_decode(
    aesKey,
    sizeof(aesKey),
    &keyLength,
    (const unsigned char*)AES128_KEY_B64,
    strlen(AES128_KEY_B64)
  );

  if (result != 0 || keyLength != sizeof(aesKey)) {
    Serial.println("[AES] Invalid AES-128 key configuration");
    return false;
  }

  return true;
}

// ============================================================
// AES-128-GCM ENCRYPTION
//
// Envelope:
// {
//   "enc": "A128GCM",
//   "nonce": "<Base64 12-byte nonce>",
//   "ciphertext": "<Base64 ciphertext + 16-byte tag>"
// }
//
// MQTT topic is authenticated as additional authenticated data.
// ============================================================

bool encryptTelemetry(
  const char* plaintext,
  size_t plaintextLength,
  char* envelope,
  size_t envelopeSize
) {
  if (!aesReady || plaintextLength > 767) {
    return false;
  }

  // Never allow the counter to wrap under the same prefix.
  if (messageCounter == UINT32_MAX) {
    Serial.println("[AES] Nonce counter exhausted");
    return false;
  }

  uint8_t nonce[12];

  memcpy(nonce, noncePrefix, sizeof(noncePrefix));

  nonce[8] = (messageCounter >> 24) & 0xFF;
  nonce[9] = (messageCounter >> 16) & 0xFF;
  nonce[10] = (messageCounter >> 8) & 0xFF;
  nonce[11] = messageCounter & 0xFF;

  // Consume a nonce even if encryption subsequently fails.
  messageCounter++;

  uint8_t ciphertext[768];
  uint8_t tag[16];
  uint8_t combined[784];

  unsigned char nonceB64[25];
  unsigned char ciphertextB64[1050];

  size_t nonceB64Length = 0;
  size_t ciphertextB64Length = 0;

  mbedtls_gcm_context ctx;
  mbedtls_gcm_init(&ctx);

  int result = mbedtls_gcm_setkey(
    &ctx,
    MBEDTLS_CIPHER_ID_AES,
    aesKey,
    128
  );

  if (result == 0) {
    result = mbedtls_gcm_crypt_and_tag(
      &ctx,
      MBEDTLS_GCM_ENCRYPT,
      plaintextLength,
      nonce,
      sizeof(nonce),
      (const unsigned char*)MQTT_TOPIC,
      strlen(MQTT_TOPIC),
      (const unsigned char*)plaintext,
      ciphertext,
      sizeof(tag),
      tag
    );
  }

  mbedtls_gcm_free(&ctx);

  if (result != 0) {
    Serial.printf("[AES] Encryption failed: %d\n", result);
    return false;
  }

  // Python AESGCM.decrypt expects ciphertext followed by tag.
  memcpy(combined, ciphertext, plaintextLength);
  memcpy(combined + plaintextLength, tag, sizeof(tag));

  result = mbedtls_base64_encode(
    nonceB64,
    sizeof(nonceB64),
    &nonceB64Length,
    nonce,
    sizeof(nonce)
  );

  if (result != 0 || nonceB64Length >= sizeof(nonceB64)) {
    return false;
  }

  nonceB64[nonceB64Length] = '\0';

  result = mbedtls_base64_encode(
    ciphertextB64,
    sizeof(ciphertextB64),
    &ciphertextB64Length,
    combined,
    plaintextLength + sizeof(tag)
  );

  if (result != 0 ||
      ciphertextB64Length >= sizeof(ciphertextB64)) {
    return false;
  }

  ciphertextB64[ciphertextB64Length] = '\0';

  int written = snprintf(
    envelope,
    envelopeSize,
    "{\"enc\":\"A128GCM\",\"nonce\":\"%s\","
    "\"ciphertext\":\"%s\"}",
    (const char*)nonceB64,
    (const char*)ciphertextB64
  );

  return written > 0 &&
         (size_t)written < envelopeSize;
}

// ============================================================
// WI-FI MANAGEMENT
// ============================================================

void maintainWiFi() {
  if (WiFi.status() == WL_CONNECTED) {
    return;
  }

  if (millis() - lastWiFiAttempt >= WIFI_RETRY_INTERVAL) {
    lastWiFiAttempt = millis();

    Serial.println("[NETWORK] Reconnecting to Wi-Fi...");
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  }
}

// ============================================================
// MQTT MANAGEMENT
// ============================================================

void maintainMQTT() {
  if (WiFi.status() != WL_CONNECTED ||
      mqttClient.connected()) {
    return;
  }

  if (millis() - lastMQTTAttempt < MQTT_RETRY_INTERVAL) {
    return;
  }

  lastMQTTAttempt = millis();

  Serial.print("[MQTT] Connecting to ");
  Serial.println(MQTT_BROKER);

  if (mqttClient.connect(
        "SecureBMS-ESP32",
        MQTT_USER,
        MQTT_PASSWORD)) {
    Serial.println("[MQTT] Connected successfully");
  } else {
    Serial.print("[MQTT] Connection failed. State: ");
    Serial.println(mqttClient.state());
  }
}

// ============================================================
// ENCRYPTED TELEMETRY PUBLISHER
// ============================================================

void publishTelemetry(
  unsigned long now,
  int raw,
  float voltage,
  float resistance,
  float temperature,
  bool valid
) {
  if (!mqttClient.connected()) {
    return;
  }

  if (!aesReady) {
    Serial.println("[AES] Not initialized; refusing to publish");
    return;
  }

  char payload[768];
  int length;

  if (valid) {
    length = snprintf(
      payload,
      sizeof(payload),
      "{\"time_ms\":%lu,\"adc_raw\":%d,"
      "\"sensor_voltage_v\":%.4f,"
      "\"ntc_resistance_ohm\":%.1f,"
      "\"temperature_c\":%.2f,"
      "\"peak_temperature_c\":%.2f,"
      "\"min_voltage_v\":%.4f,"
      "\"max_voltage_v\":%.4f,"
      "\"state\":\"%s\","
      "\"alert_events\":%lu,"
      "\"sensor_fault_events\":%lu,"
      "\"alert_duration_s\":%lu,"
      "\"buzzer\":\"%s\","
      "\"mosfet_command\":\"%s\"}",
      now,
      raw,
      voltage,
      resistance,
      temperature,
      peakTemperature,
      minimumVoltage,
      maximumVoltage,
      stateName(currentState),
      alertEventCount,
      sensorFaultCount,
      getAlertDuration() / 1000,
      currentState == NORMAL_STATE ? "OFF" : "ON",
      (currentState == NORMAL_STATE && LOAD_ENABLE)
          ? "ON" : "OFF"
    );
  } else {
    length = snprintf(
      payload,
      sizeof(payload),
      "{\"time_ms\":%lu,\"adc_raw\":%d,"
      "\"sensor_voltage_v\":%.4f,"
      "\"state\":\"SENSOR_FAULT\","
      "\"alert_events\":%lu,"
      "\"sensor_fault_events\":%lu,"
      "\"alert_duration_s\":%lu,"
      "\"buzzer\":\"ON\","
      "\"mosfet_command\":\"OFF\"}",
      now,
      raw,
      voltage,
      alertEventCount,
      sensorFaultCount,
      getAlertDuration() / 1000
    );
  }

  if (length <= 0 || length >= (int)sizeof(payload)) {
    Serial.println("[MQTT] Telemetry JSON formatting failed");
    return;
  }

  char encryptedPayload[1200];

  if (!encryptTelemetry(
        payload,
        (size_t)length,
        encryptedPayload,
        sizeof(encryptedPayload))) {
    Serial.println("[AES] Telemetry encryption failed");
    return;
  }

  if (mqttClient.publish(MQTT_TOPIC, encryptedPayload)) {
    Serial.println("[MQTT] Encrypted telemetry published");
  } else {
    Serial.println("[MQTT] Encrypted publish failed");
  }
}

// ============================================================
// SENSOR FAULT HANDLING
// ============================================================

void reportSensorFault(
  unsigned long now,
  int raw,
  float voltage,
  const char* reason
) {
  changeState(SENSOR_FAULT_STATE);
  setOutputs();

  Serial.print("[FAULT] ");
  Serial.println(reason);

  // Avoid publishing a separate plaintext telemetry object.
  // Fault telemetry is published only through AES-GCM.
  publishTelemetry(
    now,
    raw,
    voltage,
    NAN,
    NAN,
    false
  );
}

// ============================================================
// ADS1115 MEDIAN SAMPLING
// ============================================================

int16_t readMedianADC() {
  const int SAMPLE_COUNT = 9;
  int16_t samples[SAMPLE_COUNT];

  for (int i = 0; i < SAMPLE_COUNT; i++) {
    samples[i] = ads.readADC_SingleEnded(0);
    delay(10);
  }

  for (int i = 0; i < SAMPLE_COUNT - 1; i++) {
    for (int j = i + 1; j < SAMPLE_COUNT; j++) {
      if (samples[j] < samples[i]) {
        int16_t temp = samples[i];
        samples[i] = samples[j];
        samples[j] = temp;
      }
    }
  }

  Serial.print("[ADC DIAGNOSTIC] Samples: ");

  for (int i = 0; i < SAMPLE_COUNT; i++) {
    Serial.print(samples[i]);

    if (i < SAMPLE_COUNT - 1) {
      Serial.print(", ");
    }
  }

  Serial.print(" | Median: ");
  Serial.println(samples[SAMPLE_COUNT / 2]);

  return samples[SAMPLE_COUNT / 2];
}

// ============================================================
// SETUP
// ============================================================

void setup() {
  Serial.begin(115200);

  Wire.begin(21, 22);

  pinMode(COMPARATOR_PIN, INPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(MOSFET_GATE, OUTPUT);

  attachInterrupt(
    digitalPinToInterrupt(COMPARATOR_PIN),
    comparatorFallingISR,
    FALLING
  );

  if (digitalRead(COMPARATOR_PIN) == LOW) {
    safetyTripLatched = true;
  }

  digitalWrite(BUZZER_PIN, LOW);
  digitalWrite(MOSFET_GATE, LOW);

  Serial.println();
  Serial.println("==============================================");
  Serial.println(" SECURE-BMS | AES-GCM TELEMETRY MONITOR");
  Serial.println("==============================================");

  aesReady = initializeAES();

  if (!aesReady) {
    Serial.println("[AES] Initialization failed");
  }

  if (!ads.begin(0x48)) {
    Serial.println("[FATAL] ADS1115 NOT FOUND");

    while (true) {
      digitalWrite(BUZZER_PIN, LOW);
      digitalWrite(MOSFET_GATE, LOW);
      delay(100);
    }
  }

  ads.setGain(GAIN_ONE);

  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setBufferSize(1536);
  mqttClient.setKeepAlive(30);
  mqttClient.setSocketTimeout(2);

  stateStartTime = millis();
  lastLog = millis() - LOG_INTERVAL;

  Serial.println("ADS1115 detected at 0x48");
  Serial.print("MQTT topic: ");
  Serial.println(MQTT_TOPIC);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  // Wi-Fi is enabled before obtaining random session bytes.
  esp_fill_random(noncePrefix, sizeof(noncePrefix));

  lastWiFiAttempt = millis();
  lastMQTTAttempt = millis() - MQTT_RETRY_INTERVAL;

  Serial.println(
    aesReady
      ? "[AES] AES-128-GCM initialized"
      : "[AES] Telemetry encryption unavailable"
  );

  Serial.println("[NETWORK] Connecting to Wi-Fi...");
}

// ============================================================
// MAIN LOOP
// ============================================================

void loop() {
  maintainWiFi();

  if (WiFi.status() == WL_CONNECTED) {
    maintainMQTT();
  }

  mqttClient.loop();

  if (WiFi.status() == WL_CONNECTED) {
    static bool wifiReported = false;

    if (!wifiReported) {
      Serial.print("[NETWORK] Connected. IP: ");
      Serial.println(WiFi.localIP());

      wifiReported = true;
    }
  }

  unsigned long now = millis();

  if (now - lastLog < LOG_INTERVAL) {
    return;
  }

  lastLog = now;

  int16_t raw = readMedianADC();
  float voltage = ads.computeVolts(raw);

  if (TEST_SENSOR_FAULT ||
      !isfinite(voltage) ||
      voltage <= 0.01 ||
      voltage >= SUPPLY_VOLTAGE) {
    reportSensorFault(
      now,
      raw,
      voltage,
      "TEST_OR_INVALID_SENSOR_VOLTAGE"
    );

    return;
  }

  float resistance =
      FIXED_RESISTOR *
      (SUPPLY_VOLTAGE / voltage - 1.0);

  if (!isfinite(resistance) || resistance <= 0) {
    reportSensorFault(
      now,
      raw,
      voltage,
      "INVALID_RESISTANCE"
    );

    return;
  }

  float temperatureK =
      1.0 / (
        1.0 / T0_KELVIN +
        log(resistance / R0) / BETA
      );

  float temperatureC = temperatureK - 273.15;

  if (!isfinite(temperatureC) ||
      temperatureC < -40.0 ||
      temperatureC > 150.0) {
    reportSensorFault(
      now,
      raw,
      voltage,
      "TEMPERATURE_OUT_OF_RANGE"
    );

    return;
  }

  if (temperatureC > peakTemperature) {
    peakTemperature = temperatureC;
  }

  if (voltage < minimumVoltage) {
    minimumVoltage = voltage;
  }

  if (voltage > maximumVoltage) {
    maximumVoltage = voltage;
  }

  int comparatorValue = digitalRead(COMPARATOR_PIN);
  bool comparatorAlert = comparatorValue == LOW;

  if (comparatorAlert) {
    safetyTripLatched = true;
  }

  if (currentState != SENSOR_FAULT_STATE) {
    if (comparatorAlert) {
      changeState(ALERT_STATE);
    } else {
      changeState(NORMAL_STATE);
    }
  }

  setOutputs();

  Serial.println();
  Serial.println("--------------- LIVE STATUS ----------------");

  Serial.print("Uptime: ");
  Serial.print(now / 1000);
  Serial.println(" sec");

  Serial.print("Temperature: ");
  Serial.print(temperatureC, 2);
  Serial.println(" C");

  Serial.print("Peak Temperature: ");
  Serial.print(peakTemperature, 2);
  Serial.println(" C");

  Serial.print("Sensor Voltage: ");
  Serial.print(voltage, 4);
  Serial.println(" V");

  Serial.print("NTC Resistance: ");
  Serial.print(resistance / 1000.0, 2);
  Serial.println(" kOhm");

  Serial.print("System State: ");
  Serial.println(stateName(currentState));

  Serial.print("Alert Events: ");
  Serial.println(alertEventCount);

  Serial.print("Sensor Fault Events: ");
  Serial.println(sensorFaultCount);

  Serial.print("Total Alert Duration: ");
  Serial.print(getAlertDuration() / 1000);
  Serial.println(" sec");

  Serial.print("Comparator GPIO26: ");
  Serial.println(comparatorValue == LOW ? "LOW" : "HIGH");

  Serial.print("Buzzer: ");
  Serial.println(
    currentState == NORMAL_STATE ? "OFF" : "ON"
  );

  Serial.print("MOSFET GPIO27 Command: ");
  Serial.println(
    (currentState == NORMAL_STATE && LOAD_ENABLE)
        ? "ON" : "OFF"
  );

  Serial.println("---------------------------------------------");

  publishTelemetry(
    now,
    raw,
    voltage,
    resistance,
    temperatureC,
    true
  );
}
