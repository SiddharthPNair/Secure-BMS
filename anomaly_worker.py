
import os
import time

import numpy as np
import pandas as pd
import psycopg
from sklearn.ensemble import IsolationForest

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "secure_bms"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}

POLL_INTERVAL = 5
WINDOW_SIZE = 1000
MODEL_NAME = "IsolationForest"


def analyse_new_telemetry():
    with psycopg.connect(**DB_CONFIG) as connection:
        rows = connection.execute(
            """
            SELECT id, received_at, temperature_c,
                   sensor_voltage_v, ntc_resistance_ohm
            FROM (
                SELECT id, received_at, temperature_c,
                       sensor_voltage_v, ntc_resistance_ohm
                FROM telemetry
                ORDER BY id DESC
                LIMIT %s
            ) recent
            ORDER BY id ASC
            """,
            (WINDOW_SIZE,),
        ).fetchall()

        saved_row = connection.execute(
            """
            SELECT MAX(telemetry_id)
            FROM anomaly_history
            WHERE model_name = %s
            """,
            (MODEL_NAME,),
        ).fetchone()

        last_saved_id = saved_row[0] or 0

    columns = [
        "id",
        "received_at",
        "temperature_c",
        "sensor_voltage_v",
        "ntc_resistance_ohm",
    ]
    df = pd.DataFrame(rows, columns=columns)

    if len(df) < 20:
        print("Waiting for at least 20 telemetry records.")
        return

    features = [
        "temperature_c",
        "sensor_voltage_v",
        "ntc_resistance_ohm",
    ]

    df["temperature_change_c"] = df["temperature_c"].diff()
    features.append("temperature_change_c")

    df[features] = df[features].replace(
        [np.inf, -np.inf], np.nan
    )

    valid = df.dropna(subset=features).copy()

    if len(valid) < 20:
        print("Waiting for at least 20 valid sensor readings.")
        return

    newest_id = int(df["id"].max())

    if newest_id <= last_saved_id:
        print(f"No new telemetry. Latest ID: {newest_id}")
        return

    model = IsolationForest(
        n_estimators=200,
        contamination=0.03,
        random_state=42,
    )

    predictions = model.fit_predict(valid[features])
    valid["anomaly_score"] = model.decision_function(
        valid[features]
    )
    valid["anomaly_status"] = np.where(
        predictions == -1, "ANOMALY", "NORMAL"
    )

    new_results = valid[valid["id"] > last_saved_id]

    if new_results.empty:
        print(f"No new valid readings to save. Latest ID: {newest_id}")
        return

    records = [
        (
            int(row.id),
            row.anomaly_status,
            float(row.anomaly_score),
            MODEL_NAME,
        )
        for row in new_results.itertuples()
    ]

    with psycopg.connect(**DB_CONFIG) as connection:
        with connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO anomaly_history
                    (telemetry_id, anomaly_status,
                     anomaly_score, model_name)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (telemetry_id, model_name)
                DO UPDATE SET
                    anomaly_status = EXCLUDED.anomaly_status,
                    anomaly_score = EXCLUDED.anomaly_score,
                    detected_at = NOW()
                """,
                records,
            )

    flagged = int(
        (new_results["anomaly_status"] == "ANOMALY").sum()
    )

    print(
        f"Processed through telemetry ID {newest_id} | "
        f"New results saved: {len(records)} | "
        f"Anomalies flagged: {flagged}"
    )


if __name__ == "__main__":
    print("Secure-BMS anomaly worker started.")
    print(f"Polling interval: {POLL_INTERVAL} seconds")

    while True:
        try:
            analyse_new_telemetry()
        except KeyboardInterrupt:
            print("\nAnomaly worker stopped.")
            break
        except Exception as error:
            print(f"Worker error: {error}")

        time.sleep(POLL_INTERVAL)
