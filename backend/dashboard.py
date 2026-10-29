
import os

import numpy as np
import pandas as pd
import psycopg
import requests
import streamlit as st
from sklearn.ensemble import IsolationForest
from streamlit_autorefresh import st_autorefresh

st.set_page_config(
    page_title="Secure-BMS Dashboard",
    page_icon="🔋",
    layout="wide",
)
st_autorefresh(
    interval=5000,
    limit=None,
    key="secure_bms_auto_refresh",
)

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "secure_bms"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}


@st.cache_data(ttl=5)
def get_history(limit):
    response = requests.get(
        f"{API_URL}/telemetry/history",
        params={"limit": limit},
        timeout=5,
    )
    response.raise_for_status()
    data = response.json()

    if isinstance(data, dict):
        data = data.get("items", data.get("data", data.get("records", [])))

    return pd.DataFrame(data)


@st.cache_data(ttl=5)
def get_health():
    response = requests.get(f"{API_URL}/health", timeout=5)
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=5)
def get_anomalies(limit):
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
            (limit,),
        ).fetchall()

    columns = [
        "id",
        "received_at",
        "temperature_c",
        "sensor_voltage_v",
        "ntc_resistance_ohm",
    ]
    df = pd.DataFrame(rows, columns=columns)

    if len(df) < 20:
        return df, "INSUFFICIENT_DATA"

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

    result = df.dropna(subset=features).copy()

    if len(result) < 20:
        return result, "INSUFFICIENT_DATA"

    model = IsolationForest(
        n_estimators=200,
        contamination=0.03,
        random_state=42,
    )

    predictions = model.fit_predict(result[features])
    result["anomaly_score"] = model.decision_function(
        result[features]
    )
    result["anomaly_status"] = np.where(
        predictions == -1, "ANOMALY", "NORMAL"
    )

    return result, "READY"


@st.cache_data(ttl=5)
def get_saved_anomaly_history(limit=100):
    with psycopg.connect(**DB_CONFIG) as connection:
        rows = connection.execute(
            """
            SELECT
                ah.telemetry_id,
                ah.detected_at,
                ah.anomaly_status,
                ah.anomaly_score,
                ah.model_name,
                t.temperature_c,
                t.sensor_voltage_v
            FROM anomaly_history ah
            JOIN telemetry t ON t.id = ah.telemetry_id
            ORDER BY ah.detected_at DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()

    columns = [
        "telemetry_id",
        "detected_at",
        "anomaly_status",
        "anomaly_score",
        "model_name",
        "temperature_c",
        "sensor_voltage_v",
    ]

    return pd.DataFrame(rows, columns=columns)


@st.cache_data(ttl=5)
def get_live_ml_status():
    with psycopg.connect(**DB_CONFIG) as connection:
        latest = connection.execute(
            """
            SELECT
                t.id,
                ah.detected_at,
                ah.anomaly_status,
                ah.anomaly_score,
                t.temperature_c,
                t.sensor_voltage_v
            FROM anomaly_history ah
            JOIN telemetry t ON t.id = ah.telemetry_id
            WHERE ah.model_name = 'IsolationForest'
            ORDER BY ah.telemetry_id DESC
            LIMIT 1
            """
        ).fetchone()

        recent_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM anomaly_history
            WHERE model_name = 'IsolationForest'
              AND anomaly_status = 'ANOMALY'
              AND detected_at >= NOW() - INTERVAL '5 minutes'
            """
        ).fetchone()[0]

        recent_flags = connection.execute(
            """
            SELECT
                t.id,
                ah.detected_at,
                ah.anomaly_score,
                t.temperature_c,
                t.sensor_voltage_v
            FROM anomaly_history ah
            JOIN telemetry t ON t.id = ah.telemetry_id
            WHERE ah.model_name = 'IsolationForest'
              AND ah.anomaly_status = 'ANOMALY'
            ORDER BY ah.detected_at DESC
            LIMIT 10
            """
        ).fetchall()

    return latest, recent_count, recent_flags


st.title("🔋 Secure-BMS Monitoring Dashboard")
st.caption(
    "Battery monitoring, sensor telemetry, and machine-learning anomaly detection"
)

with st.sidebar:
    st.header("Settings")
    history_limit = st.selectbox(
        "Historical records",
        [100, 250, 500, 1000],
        index=3,
    )

    if st.button("Refresh dashboard", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.caption("Data refresh cache: 5 seconds")


# Load historical telemetry from FastAPI
try:
    history = get_history(history_limit)
    health = get_health()

    st.success("FastAPI connection successful")

    if history.empty:
        st.warning("No telemetry records are available yet.")
    else:
        for column in ["received_at", "temperature_c",
                       "peak_temperature_c", "sensor_voltage_v",
                       "state", "buzzer", "mosfet_command"]:
            if column not in history.columns:
                history[column] = np.nan

        history["received_at"] = pd.to_datetime(
            history["received_at"], errors="coerce"
        )

        latest = history.sort_values(
            "received_at"
        ).iloc[-1]

        st.subheader("Latest Telemetry")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric(
            "Temperature",
            f"{latest['temperature_c']:.2f} °C"
            if pd.notna(latest["temperature_c"]) else "N/A",
        )
        c2.metric(
            "Recorded Peak",
            f"{latest['peak_temperature_c']:.2f} °C"
            if pd.notna(latest["peak_temperature_c"]) else "N/A",
        )
        c3.metric(
            "Sensor Divider Voltage",
            f"{latest['sensor_voltage_v']:.4f} V"
            if pd.notna(latest["sensor_voltage_v"]) else "N/A",
        )
        c4.metric(
            "System State",
            str(latest["state"]),
        )

        c5, c6, c7 = st.columns(3)
        c5.metric("Buzzer", str(latest["buzzer"]))
        c6.metric("MOSFET Command", str(latest["mosfet_command"]))
        c7.metric("History Records", len(history))

        st.caption(
            "Sensor divider voltage is not battery-cell voltage. "
            "MOSFET command is not confirmation of physical load state."
        )

        st.subheader("Temperature History")
        temperature_data = history.dropna(
            subset=["received_at", "temperature_c"]
        )
        if not temperature_data.empty:
            st.line_chart(
                temperature_data.set_index("received_at")[
                    ["temperature_c", "peak_temperature_c"]
                ]
            )
        else:
            st.info("No temperature history is available.")

        st.subheader("Sensor Divider Voltage History")
        voltage_data = history.dropna(
            subset=["received_at", "sensor_voltage_v"]
        )
        if not voltage_data.empty:
            st.line_chart(
                voltage_data.set_index("received_at")[
                    ["sensor_voltage_v"]
                ]
            )
        else:
            st.info("No voltage history is available.")

        with st.expander("View historical telemetry"):
            st.dataframe(history, use_container_width=True, hide_index=True)

except Exception as error:
    st.error(f"Telemetry/API error: {error}")


# Machine-learning panel
st.divider()
st.header("ML Anomaly Detection")
st.write(
    "Isolation Forest analyses historical sensor readings "
    "and flags statistically unusual patterns."
)

try:
    anomaly_df, anomaly_state = get_anomalies(history_limit)

    if anomaly_state != "READY":
        st.info(
            "Collect at least 20 valid telemetry records "
            "before running anomaly detection."
        )
    else:
        flagged = anomaly_df[
            anomaly_df["anomaly_status"] == "ANOMALY"
        ].sort_values("anomaly_score")

        total = len(anomaly_df)
        anomaly_count = len(flagged)
        anomaly_rate = 100 * anomaly_count / total if total else 0

        a1, a2, a3 = st.columns(3)
        a1.metric("Records Analysed", total)
        a2.metric("Anomalies Flagged", anomaly_count)
        a3.metric("Anomaly Rate", f"{anomaly_rate:.2f}%")

        st.subheader("Temperature With Anomaly Markers")

        chart_data = anomaly_df.dropna(
            subset=["received_at", "temperature_c"]
        ).copy()

        normal_points = chart_data[
            chart_data["anomaly_status"] == "NORMAL"
        ].set_index("received_at")

        anomaly_points = chart_data[
            chart_data["anomaly_status"] == "ANOMALY"
        ].set_index("received_at")

        left, right = st.columns(2)

        with left:
            st.caption("All readings")
            st.line_chart(
                chart_data.set_index("received_at")[["temperature_c"]]
            )

        with right:
            st.caption("Flagged readings only")
            if not anomaly_points.empty:
                st.scatter_chart(
                    anomaly_points[["temperature_c"]]
                )
            else:
                st.info("No anomalous temperature points.")

        st.subheader("Flagged Historical Readings")

        if flagged.empty:
            st.success("No unusual readings were flagged in this analysis.")
        else:
            st.dataframe(
                flagged[
                    [
                        "id",
                        "received_at",
                        "temperature_c",
                        "sensor_voltage_v",
                        "ntc_resistance_ohm",
                        "anomaly_score",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )

        st.caption(
            "An anomaly is a statistically unusual reading, not a confirmed "
            "battery fault. This model does not trigger the hardware cutoff."
        )

except Exception as error:
    st.error(f"ML anomaly detection error: {error}")
    st.info(
        "Check PostgreSQL credentials in DB_PASSWORD and confirm "
        "that the database is running."
    )


st.divider()
st.header("Persistent Anomaly History")

try:
    saved_history = get_saved_anomaly_history(100)

    if saved_history.empty:
        st.info(
            "No saved anomaly results yet. Run anomaly_detection.py first."
        )
    else:
        saved_anomalies = saved_history[
            saved_history["anomaly_status"] == "ANOMALY"
        ]

        c1, c2 = st.columns(2)
        c1.metric("Saved Results Shown", len(saved_history))
        c2.metric("Flagged Results Shown", len(saved_anomalies))

        st.dataframe(
            saved_history,
            use_container_width=True,
            hide_index=True,
        )

except Exception as error:
    st.error(f"Could not load saved anomaly history: {error}")


st.divider()
st.header("Live ML Status")

try:
    latest_ml, recent_count, recent_flags = get_live_ml_status()

    if latest_ml is None:
        st.info(
            "Waiting for the anomaly worker to save its first result."
        )
    else:
        (
            telemetry_id,
            detected_at,
            anomaly_status,
            anomaly_score,
            temperature,
            sensor_voltage,
        ) = latest_ml

        st.caption(
            f"Latest processed telemetry ID: {telemetry_id} | "
            f"Detection saved: {detected_at}"
        )

        c1, c2, c3 = st.columns(3)

        c1.metric("Latest ML Status", anomaly_status)
        c2.metric("Anomalies in Last 5 Minutes", recent_count)
        c3.metric(
            "Latest Anomaly Score",
            f"{anomaly_score:.5f}",
        )

        c4, c5 = st.columns(2)
        c4.metric(
            "Temperature",
            f"{temperature:.2f} °C"
            if temperature is not None else "N/A",
        )
        c5.metric(
            "Sensor Divider Voltage",
            f"{sensor_voltage:.4f} V"
            if sensor_voltage is not None else "N/A",
        )

        if anomaly_status == "ANOMALY":
            st.warning(
                "The latest processed reading was flagged as unusual."
            )
        else:
            st.success(
                "The latest processed reading was classified as normal."
            )

        st.subheader("Recent Flagged Readings")

        if recent_flags:
            flags_df = pd.DataFrame(
                recent_flags,
                columns=[
                    "telemetry_id",
                    "detected_at",
                    "anomaly_score",
                    "temperature_c",
                    "sensor_voltage_v",
                ],
            )
            st.dataframe(
                flags_df,
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No saved anomaly flags are available yet.")

        st.caption(
            "This panel displays saved ML classifications. "
            "It is not a hardware safety monitor or cutoff controller."
        )

except Exception as error:
    st.error(f"Could not load live ML status: {error}")
