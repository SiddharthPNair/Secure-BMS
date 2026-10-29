
import os
import json
import base64
import threading

import psycopg
import paho.mqtt.client as mqtt

from psycopg.rows import dict_row
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import FastAPI, HTTPException, Query




# ============================================================
# CONFIGURATION
# ============================================================

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "secure_bms")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

MQTT_BROKER = os.getenv("MQTT_BROKER", "10.182.68.229")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv(
    "MQTT_TOPIC",
    "secure-bms/telemetry",
)
MQTT_USER = os.getenv(
    "MQTT_USER",
    os.getenv("MQTT_USERNAME", ""),
)
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")

AES_ENABLED = (
    os.getenv("AES_ENABLED", "false").lower() == "true"
)
AES_KEY_B64 = os.getenv("AES128_KEY_B64", "")

app = FastAPI(title="Secure-BMS API")

mqtt_client = None
mqtt_connected = False
message_count = 0
counter_lock = threading.Lock()

class ReplayDetected(Exception):
    pass
# ============================================================
# TELEMETRY FIELDS
# ============================================================

REQUIRED_FIELDS = {
    "time_ms",
    "adc_raw",
    "sensor_voltage_v",
    "ntc_resistance_ohm",
    "temperature_c",
    "peak_temperature_c",
    "min_voltage_v",
    "max_voltage_v",
    "state",
    "alert_events",
    "sensor_fault_events",
    "alert_duration_s",
    "buzzer",
    "mosfet_command",
}


# ============================================================
# AES-128-GCM
# ============================================================

def get_aes_key():
    if not AES_KEY_B64:
        raise ValueError(
            "AES128_KEY_B64 environment variable is missing"
        )

    try:
        key = base64.b64decode(
            AES_KEY_B64,
            validate=True,
        )
    except Exception as exc:
        raise ValueError(
            "AES128_KEY_B64 is not valid Base64"
        ) from exc

    if len(key) != 16:
        raise ValueError(
            "AES-128 key must decode to exactly 16 bytes"
        )

    return key


def decode_telemetry_payload(payload, topic):
    """
    Decrypt the MQTT envelope when AES is enabled.
    Return the actual telemetry dictionary, not the envelope.
    """

    if not AES_ENABLED:
        data = json.loads(payload.decode("utf-8"))

    else:
        key = get_aes_key()

        envelope = json.loads(payload.decode("utf-8"))

        if not isinstance(envelope, dict):
            raise ValueError(
                "Encrypted MQTT envelope must be a JSON object"
            )

        if envelope.get("enc") != "A128GCM":
            raise ValueError(
                "Expected an A128GCM encrypted envelope"
            )

        nonce = base64.b64decode(
            envelope["nonce"],
            validate=True,
        )

        ciphertext_and_tag = base64.b64decode(
            envelope["ciphertext"],
            validate=True,
        )

        if len(nonce) != 12:
            raise ValueError(
                "AES-GCM nonce must be 12 bytes"
            )

        if len(ciphertext_and_tag) < 16:
            raise ValueError(
                "Encrypted payload is missing its GCM tag"
            )

        # Topic is authenticated additional data (AAD).
        plaintext = AESGCM(key).decrypt(
            nonce,
            ciphertext_and_tag,
            topic.encode("utf-8"),
        )

        data = json.loads(plaintext.decode("utf-8"))

    if not isinstance(data, dict):
        raise ValueError(
            "Decoded telemetry must be a JSON object"
        )

    return data


# ============================================================
# TELEMETRY VALIDATION
# ============================================================

def validate_payload(data):
    if not isinstance(data, dict):
        raise ValueError(
            "Telemetry must be a JSON object"
        )

    missing = REQUIRED_FIELDS - set(data.keys())

    if missing:
        raise ValueError(
            "Telemetry fields missing: "
            + ", ".join(sorted(missing))
        )

    if not isinstance(data["state"], str):
        raise ValueError("state must be a string")

    numeric_fields = REQUIRED_FIELDS - {
        "state",
        "buzzer",
        "mosfet_command",
    }

    for field in numeric_fields:
        value = data[field]

        if isinstance(value, bool) or not isinstance(
            value, (int, float)
        ):
            raise ValueError(
                f"{field} must be numeric"
            )

        if isinstance(value, float):
            import math

            if not math.isfinite(value):
                raise ValueError(
                    f"{field} must be finite"
                )

    return data


# ============================================================
# DATABASE
# ============================================================

def get_db_connection():
    return psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        connect_timeout=5,
        row_factory=dict_row,
    )



def save_telemetry(data, nonce=None):
    # Reject encrypted envelopes or incomplete dictionaries.
    validate_payload(data)

    sql = """
        INSERT INTO telemetry (
            device_time_ms,
            adc_raw,
            sensor_voltage_v,
            ntc_resistance_ohm,
            temperature_c,
            peak_temperature_c,
            min_voltage_v,
            max_voltage_v,
            state,
            alert_events,
            sensor_fault_events,
            alert_duration_s,
            buzzer,
            mosfet_command,
            raw_payload
        )
        VALUES (
            %(time_ms)s,
            %(adc_raw)s,
            %(sensor_voltage_v)s,
            %(ntc_resistance_ohm)s,
            %(temperature_c)s,
            %(peak_temperature_c)s,
            %(min_voltage_v)s,
            %(max_voltage_v)s,
            %(state)s,
            %(alert_events)s,
            %(sensor_fault_events)s,
            %(alert_duration_s)s,
            %(buzzer)s,
            %(mosfet_command)s,
            %(raw_payload)s
        )
        RETURNING id
    """

    values = {
        **data,
        "raw_payload": json.dumps(data),
    }

    with get_db_connection() as connection:

        # Enforce replay protection when AES encryption is enabled.
        if AES_ENABLED:
            if nonce is None:
                raise ValueError(
                    "AES replay protection requires the authenticated nonce."
                )

            if not isinstance(nonce, bytes) or len(nonce) != 12:
                raise ValueError("Invalid AES-GCM nonce for replay protection.")

            session_id = nonce[:8]
            counter = int.from_bytes(nonce[8:], byteorder="big")

            # Serialize replay checks so concurrent messages cannot
            # accept the same counter.
            replay_state = connection.execute(
                """
                SELECT active_session_id, last_counter
                FROM secure_bms_replay_state
                WHERE singleton_id = 1
                FOR UPDATE
                """
            ).fetchone()

            if replay_state is None:
                raise RuntimeError(
                    "Replay-protection state is missing. Run the SQL setup first."
                )

            active_session_id = replay_state["active_session_id"]
            last_counter = replay_state["last_counter"]

            if active_session_id is not None:
                active_session_id = bytes(active_session_id)

            if active_session_id == session_id:
                # Same boot session: only strictly increasing counters
                # are accepted.
                if counter <= last_counter:
                    raise ReplayDetected(
                        f"Counter {counter} is not newer than "
                        f"the last accepted counter {last_counter}."
                    )

                connection.execute(
                    """
                    UPDATE secure_bms_replay_state
                    SET last_counter = %s
                    WHERE singleton_id = 1
                    """,
                    (counter,),
                )

            else:
                # A previously seen session must not become active again.
                previous_session = connection.execute(
                    """
                    SELECT 1
                    FROM secure_bms_replay_sessions
                    WHERE session_id = %s
                    """,
                    (session_id,),
                ).fetchone()

                if previous_session is not None:
                    raise ReplayDetected(
                        "Message belongs to an inactive or previous ESP32 session."
                    )

                # Register a new ESP32 boot session.
                connection.execute(
                    """
                    INSERT INTO secure_bms_replay_sessions (session_id)
                    VALUES (%s)
                    """,
                    (session_id,),
                )

                connection.execute(
                    """
                    UPDATE secure_bms_replay_state
                    SET active_session_id = %s,
                        last_counter = %s
                    WHERE singleton_id = 1
                    """,
                    (session_id, counter),
                )

        # Existing telemetry insert remains unchanged.
        row = connection.execute(
            sql,
            values,
        ).fetchone()

    return row["id"]



# ============================================================
# MQTT CALLBACKS
# ============================================================

def on_connect(client, userdata, flags, reason_code, properties=None):
    global mqtt_connected

    mqtt_connected = str(reason_code) in ("Success", "0")

    if mqtt_connected:
        print("MQTT connected successfully")
        client.subscribe(MQTT_TOPIC)
        print("Subscribed to:", MQTT_TOPIC)
    else:
        print("MQTT connection failed:", reason_code)


def on_disconnect(
    client,
    userdata,
    disconnect_flags=None,
    reason_code=None,
    properties=None,
):
    global mqtt_connected

    mqtt_connected = False
    print("MQTT disconnected:", reason_code)



def on_message(client, userdata, message):
    global message_count

    try:
        # Decrypt and authenticate the incoming MQTT payload.
        data = decode_telemetry_payload(
            message.payload,
            message.topic,
        )

        # Extract the nonce from the encrypted envelope.
        nonce = None

        if AES_ENABLED:
            envelope = json.loads(message.payload.decode("utf-8"))

            if not isinstance(envelope, dict):
                raise ValueError("Invalid encrypted telemetry envelope.")

            nonce = base64.b64decode(
                envelope["nonce"],
                validate=True,
            )

            if len(nonce) != 12:
                raise ValueError("Invalid AES-GCM nonce length.")

        validate_payload(data)

        print("Decoded telemetry fields:", sorted(data.keys()))

        # Replay validation and telemetry insertion share one transaction.
        record_id = save_telemetry(data, nonce=nonce)

        with counter_lock:
            message_count += 1

        print(
            f"Telemetry saved successfully. Database record ID: {record_id}"
        )

    except InvalidTag:
        print(
            "SECURITY EVENT: AES-GCM authentication failed. "
            "Telemetry rejected."
        )

    except ReplayDetected as exc:
        print(
            "SECURITY EVENT: Replayed/stale telemetry rejected:",
            str(exc),
        )

    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        print(
            "SECURITY EVENT: Invalid telemetry payload:",
            str(exc),
        )

    except Exception as exc:
        print("Telemetry database save failed:", str(exc))


# ============================================================
# MQTT CLIENT LIFECYCLE
# ============================================================

def start_mqtt():
    global mqtt_client

    if mqtt_client is not None:
        return

    if AES_ENABLED:
        # Fail early if the key is missing or invalid.
        get_aes_key()
        print("AES-128-GCM decryption enabled")
    else:
        print(
            "WARNING: AES decryption disabled; "
            "expecting plaintext JSON telemetry"
        )

    client = mqtt.Client(
        client_id="secure-bms-backend",
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    )

    if MQTT_USER:
        client.username_pw_set(
            MQTT_USER,
            MQTT_PASSWORD,
        )

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    mqtt_client = client

    try:
        client.connect_async(
            MQTT_BROKER,
            MQTT_PORT,
            keepalive=60,
        )
        client.loop_start()

        print(
            f"MQTT client started for "
            f"{MQTT_BROKER}:{MQTT_PORT}"
        )

    except Exception:
        mqtt_client = None
        raise


def stop_mqtt():
    global mqtt_client, mqtt_connected

    if mqtt_client is not None:
        client = mqtt_client
        mqtt_client = None
        mqtt_connected = False

        client.disconnect()
        client.loop_stop()

        print("MQTT client stopped")


@app.on_event("startup")
def startup_event():
    start_mqtt()


@app.on_event("shutdown")
def shutdown_event():
    stop_mqtt()


# ============================================================
# FASTAPI ENDPOINTS
# ============================================================

@app.get("/")
def root():
    return {
        "project": "Secure-BMS",
        "status": "running",
        "mqtt_connected": mqtt_connected,
        "aes_enabled": AES_ENABLED,
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "database": DB_NAME,
        "mqtt_connected": mqtt_connected,
        "aes_enabled": AES_ENABLED,
        "messages_saved": message_count,
    }


@app.get("/telemetry/latest")
def latest_telemetry():
    try:
        with get_db_connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM telemetry
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()

        if row is None:
            return {"message": "No telemetry records yet"}

        return row

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not retrieve latest telemetry: {exc}",
        ) from exc


@app.get("/telemetry/history")
def telemetry_history(
    limit: int = Query(default=100, ge=1, le=5000),
):
    try:
        with get_db_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM telemetry
                ORDER BY id DESC
                LIMIT %s
                """,
                (limit,),
            ).fetchall()

        return rows

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not retrieve telemetry history: {exc}",
        ) from exc
