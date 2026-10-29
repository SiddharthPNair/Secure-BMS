
CHAPTER 10
CONCLUSION AND FUTURE ENHANCEMENTS
10.1 Conclusion

The Secure-BMS (Secure Battery Management System) project presents an experimental cyber-physical system for monitoring a physical 18650 lithium-ion battery cell and integrating embedded sensing with secure telemetry communication, backend processing, persistent data storage, and dashboard-based visualization.

The hardware prototype uses an ESP32 NodeMCU development board as its primary controller. Temperature measurements are obtained using a nominally 100 kΩ NTC thermistor with a B3950 characteristic and an ADS1115 analog-to-digital converter. The embedded firmware applies multi-sample median filtering, maintains temperature-alert and sensor-fault states, and supports Wi-Fi connectivity. A comparator and active-low buzzer provide a local alert mechanism when the configured alert condition is reached.

A key aspect of Secure-BMS is the integration of security mechanisms into the telemetry pipeline. AES-128-GCM authenticated encryption is used to protect telemetry payloads, while MQTT provides message transport between the embedded device and the backend. The backend authenticates and decrypts incoming messages before processing them. Database-backed replay protection uses session information and message counters to identify duplicate or stale messages. PostgreSQL provides persistent telemetry storage and transactional handling of related replay-protection state.

The software implementation also includes a FastAPI backend and a Streamlit dashboard for accessing and presenting available system information. Isolation Forest and Random Forest form part of the project's anomaly-detection approach, although their performance has not yet been comprehensively validated.

The tests conducted during development demonstrated basic temperature-sensing behavior, comparator-state changes, buzzer operation, and selected software-level replay-protection and database transaction scenarios. These results provide evidence that important hardware and software components have been implemented and tested under the conditions examined.

However, several limitations remain. Temperature measurements require comprehensive calibration, INA219 current measurements have not been fully validated, and end-to-end replay testing through the live MQTT callback remains incomplete. Automated load switching is disabled in the current firmware configuration. In addition, the prototype has not undergone comprehensive battery-safety certification or full system reliability validation.

In conclusion, Secure-BMS establishes an experimental foundation for combining battery monitoring with authenticated telemetry, replay protection, and centralized data management. The project demonstrates the feasibility of integrating these capabilities within a cyber-physical prototype while identifying the additional verification required to improve its reliability and practical applicability. The prototype should be considered a monitoring and research testbed rather than a certified battery protection system.
10.2 Future Enhancements

Several enhancements can be introduced to improve the accuracy, reliability, security, and usability of Secure-BMS.
10.2.1 Improved Temperature Measurement

The temperature-sensing circuit can be calibrated against a suitable reference thermometer over the intended operating range. Calibration can help quantify measurement error and improve the reliability of temperature estimates.

Further improvements may include evaluating sensor placement, thermal contact, sampling intervals, filtering parameters, and temperature-response time. These changes would help establish more reliable measurement behavior under controlled conditions.
10.2.2 Validated Voltage and Current Monitoring

The current prototype includes an INA219 sensor interface, but its measurements have not been fully validated. Future work should verify the sensor connections and measurement configuration, then compare its voltage and current readings with suitable reference instruments.

Once validated, voltage and current measurements could be integrated with temperature readings to provide a more comprehensive view of battery behavior. Derived quantities such as power and accumulated energy could then be calculated where the measurement data and sampling method support them.
10.2.3 Automated Load Management

The hardware includes an IRLZ44N MOSFET interface for load control, but automated switching is disabled in the current firmware. Future development could introduce a carefully validated load-control state machine with defined operating thresholds, fault handling, and recovery behavior.

Before enabling automated switching, the design should be evaluated using a controlled test setup and an appropriate load. The implementation should also account for microcontroller resets, sensor failures, unexpected switching states, and loss of communication. Independent hardware protection should be considered wherever required by the electrical design.
10.2.4 Enhanced Telemetry Security

The existing AES-128-GCM mechanism and database-backed replay protection provide a basis for further security evaluation. Future work could include systematic end-to-end testing through the live MQTT broker and backend callback.

Additional improvements may include secure key provisioning, controlled key rotation, protected credential storage, stronger session lifecycle management, and more comprehensive testing of duplicate delivery, reconnect behavior, malformed payloads, and process restarts. MQTT transport security and access controls should also be configured appropriately for the intended deployment environment.
10.2.5 Improved Anomaly Detection

The anomaly-detection component can be strengthened through systematic evaluation of Isolation Forest and Random Forest using representative telemetry datasets. The evaluation should use clearly defined training and testing data and report appropriate metrics, such as precision, recall, F1-score, and false-positive rate where applicable.

Future models could consider multiple input variables, including temperature, voltage, current, and changes in measurements over time, provided these measurements are validated and available. The system should distinguish experimental anomaly scores from confirmed battery faults and should not rely on an unvalidated model as the sole safety mechanism.
10.2.6 Dashboard Improvements

The Streamlit dashboard could be extended to present temperature trends, validated voltage and current measurements, alert history, communication status, and replay-protection events. Historical charts and filtering options could help users examine changes over time.

Additional features could include configurable alert thresholds, downloadable telemetry records, clearer sensor-fault indicators, and system-health summaries. Any dashboard controls that affect hardware behavior would require authentication, authorization, and appropriate safety validation before being enabled.
10.2.7 Comprehensive Testing and Reliability Evaluation

Future testing should cover the complete telemetry path from physical sensing through encryption, MQTT transmission, backend validation, database storage, and dashboard display.

Testing should also include Wi-Fi interruptions, broker restarts, database failures, invalid sensor readings, repeated messages, counter-boundary conditions, and recovery after power loss. The results should be documented using reproducible procedures, recorded test outcomes, and clearly defined acceptance criteria.

These enhancements would improve the evidence available to assess the prototype's accuracy, security, and reliability.
10.3 Future Scope

Secure-BMS can be extended into a more comprehensive battery-monitoring and research platform. Its current architecture provides a starting point for further work in cyber-physical system monitoring, secure communication, fault detection, and battery-data analysis.
10.3.1 Multi-Cell Battery Monitoring

The system could be extended from a single-cell testbed to a multi-cell battery arrangement. This would require additional sensing channels, cell-level measurement management, suitable isolation and protection considerations, and methods for comparing individual cell behavior.

Multi-cell monitoring could help identify differences in temperature and electrical behavior between cells. However, such an extension would require a redesigned and validated hardware architecture rather than simply connecting additional cells to the existing prototype.
10.3.2 Cloud-Based Monitoring

The local MQTT and backend architecture could be extended to a securely configured cloud environment. Remote storage and visualization could allow authorized users to monitor telemetry from multiple test devices and examine historical trends.

Such a deployment would require secure device authentication, encrypted network connections, protected key management, access control, reliable connectivity, and appropriate data-retention policies. Cloud deployment should follow successful validation of the local system.
10.3.3 Predictive Analytics and Battery Health Estimation

With sufficiently accurate and representative datasets, future versions could investigate battery-state estimation and predictive analytics. Possible research directions include state-of-charge estimation, state-of-health estimation, degradation analysis, and detection of unusual thermal or electrical behavior.

These capabilities would require additional validated measurements and suitable reference data. Model performance would need to be evaluated under representative operating conditions before predictions could be considered reliable.
10.3.4 Digital Twin Integration

A future version could incorporate a digital representation of the monitored battery and its operating conditions. Such a digital twin could combine measured telemetry with a model of expected battery behavior to support visualization, simulation, and comparison between measured and predicted values.

The usefulness of this approach would depend on the accuracy of the physical measurements and the validity of the underlying model. Model assumptions, prediction errors, and differences between simulated and physical behavior would need to be documented.
10.3.5 Advanced Fault Detection and Recovery

The system could be extended to identify a broader set of fault conditions, including sensor disconnection, abnormal temperature trends, communication loss, inconsistent measurements, and unexpected system restarts.

A future fault-management framework could associate each detected condition with a defined response, event record, and recovery procedure. Any response involving battery isolation or load switching would require dedicated hardware design and safety validation.
10.3.6 Scalable Monitoring and Research Applications

The architecture could eventually support multiple battery-monitoring nodes reporting to a centralized platform. This would allow researchers to compare telemetry from different test conditions, examine patterns across datasets, and evaluate detection algorithms using recorded experimental data.

Potential applications include academic research, laboratory battery experiments, and prototype monitoring systems for battery-powered equipment. Suitability for any practical deployment would depend on further validation, electrical-safety assessment, and the requirements of the intended application.

Overall, the future scope of Secure-BMS extends beyond basic temperature monitoring toward a more comprehensive platform for secure battery telemetry, data analysis, and experimental fault detection. Achieving this scope will require incremental development, reliable measurement data, reproducible testing, and careful validation of all hardware and software functions.
CHAPTER 11
REFERENCES

    Espressif Systems. ESP32 Series Datasheet. Available at: https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf

    Texas Instruments. ADS111x Ultra-Small, Low-Power, I²C-Compatible, 860-SPS, 16-Bit ADCs Datasheet. Available at: https://www.ti.com/lit/ds/symlink/ads1115.pdf

    Texas Instruments. LM339 Quad Differential Comparator Datasheet. Available at: https://www.ti.com/lit/ds/symlink/lm339.pdf

    Infineon Technologies. IRLZ44N HEXFET Power MOSFET Datasheet. Available at: https://www.infineon.com/

    Eclipse Foundation. Eclipse Mosquitto: An Open-Source MQTT Broker. Available at: https://mosquitto.org/

    OASIS. MQTT Version 3.1.1 Specification. Available at: https://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html

    National Institute of Standards and Technology (NIST). Recommendation for Block Cipher Modes of Operation: Galois/Counter Mode (GCM) and GMAC. NIST Special Publication 800-38D. Available at: https://csrc.nist.gov/pubs/sp/800/38/d/final

    PostgreSQL Global Development Group. PostgreSQL Documentation. Available at: https://www.postgresql.org/docs/

    FastAPI. FastAPI Documentation. Available at: https://fastapi.tiangolo.com/

    Streamlit. Streamlit Documentation. Available at: https://docs.streamlit.io/

    Scikit-learn Developers. Scikit-learn User Guide: Ensemble Methods and Isolation Forest. Available at: https://scikit-learn.org/stable/user_guide.html

    Python Software Foundation. Python Documentation. Available at: https://docs.python.org/3/

    Eclipse Paho Project. Eclipse Paho MQTT Python Client Documentation. Available at: https://eclipse.dev/paho/

    pytest Development Team. pytest Documentation. Available at: https://docs.pytest.org/

    Arduino. Arduino Documentation. Available at: https://docs.arduino.cc/

APPENDIX A
GITHUB REPOSITORY AND DEMONSTRATION VIDEO
A.1 GitHub Repository

The GitHub repository serves as the central location for maintaining the source code and supporting software files developed for the Secure-BMS (Secure Battery Management System) project. It supports version control, code organization, and documentation of the project's implementation.

The repository may contain the ESP32 firmware, backend application, database-related code, dashboard implementation, anomaly-detection component, and relevant project documentation. Organizing these components in a single repository makes it easier to review the implementation and understand the relationship between the embedded and software subsystems.

GitHub Repository Link: [Insert the actual Secure-BMS GitHub repository URL]

The repository should be configured to prevent the exposure of cryptographic keys, passwords, database credentials, Wi-Fi credentials, and other sensitive configuration values.
A.2 Demonstration Video

The demonstration video provides a visual overview of the Secure-BMS prototype and its implemented functions. It can be used to demonstrate the physical hardware, temperature-sensing circuit, local alert mechanism, and available software components.

The demonstration may include the ESP32 development board, thermistor-based temperature sensing, comparator output, buzzer operation, MQTT telemetry communication, backend processing, database storage, and dashboard visualization, provided each feature is shown working in the recorded demonstration.

Demonstration Video Link: [Insert the actual demonstration video URL]

The video should present the prototype under controlled testing conditions and distinguish between demonstrated functionality and features that remain incomplete or unvalidated.
APPENDIX B
SOURCE CODE
B.1 ESP32 Firmware

The ESP32 firmware implements the embedded monitoring functions of Secure-BMS. It initializes the hardware interfaces, acquires temperature-sensor readings through the ADS1115 analog-to-digital converter, processes the measurements, manages alert and sensor-fault states, and supports Wi-Fi-based telemetry communication.

The firmware uses a multi-sample median-filtering method to reduce the influence of isolated measurement variations. It also monitors the comparator input and controls the active-low buzzer according to the configured alert logic.

The firmware includes AES-128-GCM authenticated encryption for telemetry payloads. The encrypted message envelope contains the encryption identifier, nonce, and ciphertext. The MQTT telemetry topic used by the implementation is secure-bms/telemetry.

The embedded implementation also includes message-counter handling intended to support replay protection at the receiving backend. The current firmware configuration keeps automated load switching disabled.

Source code location: [Insert the actual firmware file path or repository link]

Suggested code listing: Include the relevant firmware sections for hardware initialization, temperature acquisition, median filtering, alert-state management, telemetry encryption, and MQTT publishing. Include the complete firmware in the electronic submission or repository where required.
B.2 Backend and Data Processing Code

The backend processes encrypted telemetry received through MQTT. It authenticates and decrypts incoming messages, validates the decoded information, and forwards valid telemetry for database storage.

The backend uses FastAPI for the HTTP application interface and Paho MQTT for message communication. PostgreSQL provides persistent storage for telemetry and replay-protection state. Database transactions are used to maintain consistency between telemetry insertion and replay-state updates.

Replay protection uses session information and message counters to help reject duplicate or stale messages. The backend maintains session and counter state in dedicated database tables. Software-level tests have covered selected counter-validation, session-validation, and transaction-rollback scenarios.

The project also includes a Streamlit dashboard for presenting available monitoring information and an anomaly-detection component using Isolation Forest and Random Forest approaches. Comprehensive anomaly-detection performance has not yet been established.

Source code location: [Insert the actual backend, database, dashboard, and anomaly-detection file paths or repository links]

Suggested code listings:

    MQTT message reception and telemetry decoding.

    AES-GCM authenticated decryption and payload validation.

    Database transaction and replay-protection logic.

    Telemetry storage and dashboard data retrieval.

    Anomaly-detection implementation, where available.

Only code that exists in the submitted implementation should be included.
B.3 Source Code Availability

The source code should be made available through the project's actual GitHub repository or the submission method specified by the institution. The repository should be organized so that the embedded firmware and software components can be identified independently.

A suggested directory organization is shown below. This is an organizational example and should be adjusted to match the actual repository structure.

Secure-BMS/
├── firmware/
│   └── secure_bms.ino
├── backend/
│   ├── main.py
│   ├── database.py
│   └── replay_protection.py
├── dashboard/
│   └── dashboard.py
├── anomaly_detection/
│   └── anomaly_detection.py
├── tests/
├── requirements.txt
└── README.md

The final repository should include setup instructions, required dependencies, configuration guidance, and instructions for running the available components. Sensitive credentials and encryption keys must be excluded from the repository and supplied through an appropriate secure configuration mechanism.

Repository URL: [Insert the actual repository URL]
APPENDIX C
ADDITIONAL HARDWARE AND TESTING EVIDENCE
C.1 Hardware Prototype

The Secure-BMS hardware prototype combines an ESP32 NodeMCU development board, an ADS1115 analog-to-digital converter, a thermistor-based temperature-sensing circuit, an LM339 comparator, an active-low buzzer, and a MOSFET-based load-control interface.

The ESP32 acts as the primary controller, while the ADS1115 acquires the analog voltage generated by the thermistor divider. The comparator provides a separate hardware alert signal, and the buzzer provides local audible notification.

The prototype uses a physical 18650 lithium-ion cell rated at 3.7 V and 2000 mAh according to its label. The hardware is intended for experimental monitoring and development; it has not been certified as a battery protection system.

Figure C.1: Overall view of the Secure-BMS hardware prototype.

[Insert a photograph showing the complete hardware setup.]

Figure C.2: ESP32, ADS1115, and temperature-sensing connections.

[Insert a clear photograph showing the controller and sensor circuit.]

Figure C.3: Comparator, buzzer, and MOSFET interface.

[Insert a photograph showing the alert and load-control circuitry.]
C.2 Temperature-Sensing Results

Temperature sensing is implemented using a nominally 100 kΩ NTC thermistor with a B3950 characteristic and a 10 kΩ fixed resistor. The voltage-divider output is measured using the ADS1115, and the firmware calculates an estimated temperature from the acquired reading.

Multiple samples are collected and median filtering is applied to reduce the effect of isolated reading variations. During development, the displayed readings changed in response to changes in the thermistor's temperature conditions.

These observations demonstrate basic sensing behavior but do not establish calibrated measurement accuracy over the intended operating range.

Figure C.4: Serial Monitor output showing temperature-sensor readings.

[Insert an actual screenshot of the firmware output.]

Table C.1: Temperature-Sensing Evidence
Evidence item	Observation or status
ADC detection	ADS1115 detected at I²C address 0x48.
Thermistor configuration	Nominally 100 kΩ NTC, B3950 characteristic.
Fixed divider resistor	10 kΩ.
Sampling method	Multi-sample median filtering.
Response to sensor changes	Readings changed under different temperature conditions.
Calibration status	Comprehensive reference-based calibration not completed.
C.3 Comparator and Buzzer Testing

The LM339 comparator output is connected to ESP32 GPIO26, while the active-low buzzer is controlled through GPIO25. The comparator output was observed to change state when the sensor condition crossed the configured threshold. The buzzer was also observed to operate according to the configured control logic.

This test provides evidence of the basic local alert path. However, a controlled reference-temperature experiment would be required to establish threshold accuracy, response time, and repeatability.

Figure C.5: Comparator output during a temperature-alert condition.

[Insert an actual photograph or Serial Monitor screenshot.]

Figure C.6: Buzzer response during alert testing.

[Insert an actual photograph or short test-video frame.]

Table C.2: Comparator and Buzzer Test Evidence
Test item	Observed result
Comparator output	State changed during threshold testing.
Alert-state handling	Firmware responds to the comparator input.
Buzzer operation	Buzzer operated according to the configured control logic.
Threshold calibration	Not comprehensively validated.
Automated load switching	Disabled in the current firmware configuration.
C.4 Additional Software Testing Evidence

The software implementation includes encrypted telemetry processing, PostgreSQL storage, and database-backed replay protection. Tests were conducted at the software and database levels to examine the handling of message counters, session information, and transactional updates.

The tested cases included acceptance of fresh messages, handling of increasing counters, rejection of duplicate or stale counters, handling of new sessions, rejection of previously seen inactive sessions, and rollback behavior when database operations fail.

These tests provide evidence for selected software functions. They do not establish that the entire hardware-to-dashboard path has been validated under all operating conditions. In particular, replay testing through the complete live MQTT callback remains incomplete.

Figure C.7: Actual test output for replay-protection and database validation.

[Insert the real test-run output.]

Figure C.8: PostgreSQL tables used for telemetry and replay-protection state.

[Insert an actual database screenshot with credentials and sensitive information excluded.]

Figure C.9: Secure-BMS dashboard.

[Insert a screenshot of the running dashboard, if available.]
C.5 Limitations of the Evidence

The evidence presented in this appendix documents selected observations from the development and testing of the Secure-BMS prototype. It should be interpreted within the scope of the tests performed.

The temperature-sensing results demonstrate changes in readings under different sensor conditions but do not establish comprehensive measurement accuracy. The INA219 sensor was detected at I²C address 0x40, but its current and voltage measurements were not fully validated.

Software-level tests provide evidence for selected replay-protection and database operations. However, end-to-end replay testing through the live MQTT callback remains incomplete. Automated load switching is disabled in the current firmware configuration, and comprehensive anomaly-detection performance has not been established.

The photographs, screenshots, and test outputs included in the final submission should be genuine records from the actual implementation. They should not be replaced with illustrative images presented as experimental evidence.

The prototype is an experimental monitoring testbed and should not be relied upon as the sole safety mechanism for a lithium-ion battery.
Secure-BMS

Secure-BMS is an ESP32-based battery monitoring prototype with temperature sensing, encrypted MQTT telemetry, a FastAPI backend, PostgreSQL storage, anomaly-processing scripts, and a Streamlit dashboard.
Prerequisites

    Windows, Python, and a project virtual environment
    Mosquitto MQTT broker
    PostgreSQL
    Required Python packages installed in .venv

Run the project

Open separate Command Prompt windows as needed.
1. Go to the project and activate the environment
cd C:\SecureBMS
.\.venv\Scripts\activate.bat
set MQTT_USER=securebms
set MQTT_PASSWORD=<your-mqtt-password>
set AES_ENABLED=true

Set MQTT_PASSWORD and the AES key using your local configuration. Do not commit credentials or encryption keys to Git.
2. Start Mosquitto
"C:\Program Files\Mosquitto\mosquitto.exe" -c "C:\Program Files\Mosquitto\mosquitto.conf" -v
3. Start the backend
cd C:\SecureBMS
.\.venv\Scripts\activate.bat
uvicorn main:app --reload

Health endpoint: http://127.0.0.1:8000/health
Latest telemetry: http://localhost:8000/telemetry/latest
4. Start the dashboard

In another terminal:
cd C:\SecureBMS
.\.venv\Scripts\activate.bat
streamlit run dashboard.py

Dashboard: http://localhost:8501/
5. Run anomaly utilities

Run from the project directory with the virtual environment activated:
python anomaly_worker.py
python inspect_timing.py
python inspect_anomalies.py
python validate_anomalies.py

Run each script according to the workflow required by the project; the inspection and validation scripts may be used for analysis rather than as persistent services.
MQTT test

With the broker running, use a separate terminal. Set credentials first:
set MQTT_USER=securebms
set MQTT_PASSWORD=<your-mqtt-password>
mosquitto_pub -h localhost -p 1883 -u "%MQTT_USER%" -P "%MQTT_PASSWORD%" -t "secure-bms/test" -m "Secure-BMS MQTT test successful"
mosquitto_sub -h localhost -p 1883 -u "%MQTT_USER%" -P "%MQTT_PASSWORD%" -t "secure-bms/test" -v

To test the broker, start the subscriber before publishing the message.
PostgreSQL setup

Connect to PostgreSQL:
psql -U postgres -h localhost -p 5432

Create and select the database:
CREATE DATABASE secure_bms;
\c secure_bms

Create the telemetry and anomaly_history tables using the schema defined by the project. If the application initializes these tables automatically, use that initialization path instead. Run SQL commands inside psql; run pip install ... in Command Prompt, not at the SQL prompt.

Useful checks:
SELECT COUNT(*) FROM telemetry;

SELECT id, received_at, temperature_c, peak_temperature_c, state
FROM telemetry
ORDER BY id DESC
LIMIT 10;

Install the PostgreSQL Python driver from Command Prompt if required:
python -m pip install "psycopg[binary]"
Network note

Only configure Windows Firewall rules when remote devices on the local subnet need to reach the broker. For local-only testing, keep the broker bound to localhost where possible. Do not expose MQTT credentials or the broker to untrusted networks.
Security

Credentials and an encryption-key-like value were included in the setup notes used to prepare this README. They have intentionally not been copied here. Rotate any exposed MQTT password or encryption key, then store replacements in local environment variables or an untracked configuration file. Never commit real secrets to the repository.
⋮⋮
⋮⋮
⋮⋮
⋮⋮
⋮⋮
⋮⋮
