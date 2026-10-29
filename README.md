Secure-BMS

Secure-BMS is an ESP32-based battery monitoring prototype with temperature sensing, encrypted MQTT telemetry, a FastAPI backend, PostgreSQL storage, anomaly-processing scripts, and a Streamlit dashboard.

Prerequisites
- Windows, Python, and a project virtual environment
- Mosquitto MQTT broker
- PostgreSQL
- Required Python packages installed in .venv
  
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

6. MQTT test
   
With the broker running, use a separate terminal. Set credentials first:

set MQTT_USER=securebms

set MQTT_PASSWORD=<your-mqtt-password>

mosquitto_pub -h localhost -p 1883 -u "%MQTT_USER%" -P "%MQTT_PASSWORD%" -t "secure-bms/test" -m "Secure-BMS MQTT test successful"

mosquitto_sub -h localhost -p 1883 -u "%MQTT_USER%" -P "%MQTT_PASSWORD%" -t "secure-bms/test" -v

To test the broker, start the subscriber before publishing the message.

7. PostgreSQL setup
   
Connect to PostgreSQL:

psql -U postgres -h localhost -p 5432

Create and select the database:

CREATE DATABASE secure_bms;

\c secure_bms

Create the telemetry and anomaly_history tables using the schema defined by the project. If the application initializes these tables automatically, use that initialization path instead. Run SQL commands inside psql; run pip install ... in Command Prompt, not at the SQL prompt.

Useful checks:

SELECT COUNT(*) FROM telemetry;

SELECT id, received_at, temperature_c, peak_temperature_c, state FROM telemetry
ORDER BY id DESC LIMIT 10;

Install the PostgreSQL Python driver from Command Prompt if required:
python -m pip install "psycopg[binary]"

Network note:

Only configure Windows Firewall rules when remote devices on the local subnet need to reach the broker. For local-only testing, keep the broker bound to localhost where possible. Do not expose MQTT credentials or the broker to untrusted networks.

Security
Credentials and an encryption-key-like value were included in the setup notes used to prepare this README. They have intentionally not been copied here. Rotate any exposed MQTT password or encryption key, then store replacements in local environment variables or an untracked configuration file. Never commit real secrets to the repository.
