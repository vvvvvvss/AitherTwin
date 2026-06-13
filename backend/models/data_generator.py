"""
data_generator.py  (updated to match team schema)
--------------------------------------------------
Simulates factory sensor data AND writes ML predictions
into the shared factory.db in the format the team's
database.py / recommender.py / app.py expect.

Tables written:
  machines         — machine list with live sensor snapshot
  sensor_data      — full time-series (used by ML training)
  energy_forecast  — hourly energy actual + predicted
  predictions      — ML failure probability output

Run once before starting app.py:
    python data_generator.py
"""

import sqlite3
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "factory.db"
MACHINES_META = [
    ("M1", "CNC Machine A",   "M1_Press",  "running"),
    ("M2", "Lathe Machine B", "M2_Lathe",  "running"),
    ("M3", "Drill Press C",   "M3_Welder", "running"),
]
DAYS = 60
FREQ = "15min"
np.random.seed(42)


# ── Sensor simulation ─────────────────────────────────────────────────────────

def _add_drift(arr, drift_start, strength):
    n = len(arr)
    drift = np.zeros(n)
    drift[drift_start:] = np.linspace(0, strength, n - drift_start)
    return arr + drift

def _make_labels(vibration, temperature, threshold_vib=6.5, threshold_temp=78.0):
    labels = np.zeros(len(vibration), dtype=int)
    for i in range(len(vibration) - 4):
        if vibration[i:i+4].max() > threshold_vib or temperature[i:i+4].max() > threshold_temp:
            labels[i] = 1
    return labels

def generate_sensor_series(machine_key: str, n_rows: int) -> pd.DataFrame:
    profiles = {
        "M1_Press":  dict(vib_base=2.1, temp_base=52, energy_base=18, rpm_base=1450),
        "M2_Lathe":  dict(vib_base=3.4, temp_base=61, energy_base=22, rpm_base=960),
        "M3_Welder": dict(vib_base=1.8, temp_base=67, energy_base=31, rpm_base=1200),
    }
    p = profiles[machine_key]
    drift_start = int(n_rows * 0.65)

    vibration = _add_drift(
        p["vib_base"] + np.random.normal(0, 0.4, n_rows),
        drift_start, 4.5
    ).clip(0.5, 12.0)

    temperature = _add_drift(
        p["temp_base"] + 3.0 * np.sin(np.linspace(0, 8*np.pi, n_rows)) + np.random.normal(0, 1.2, n_rows),
        drift_start, 18.0
    ).clip(35, 95)

    load = 0.7 + 0.3 * np.abs(np.sin(np.linspace(0, 12*np.pi, n_rows)))
    energy = (p["energy_base"] * load + np.random.normal(0, 0.8, n_rows)).clip(5, 55)

    rpm = _add_drift(
        p["rpm_base"] + np.random.normal(0, 15, n_rows),
        drift_start, -80
    ).clip(600, 1800)

    timestamps = pd.date_range(end=datetime.now(), periods=n_rows, freq=FREQ)
    return pd.DataFrame({
        "timestamp":      timestamps,
        "machine_id":     machine_key,
        "vibration_mms":  vibration.round(3),
        "temperature_c":  temperature.round(2),
        "energy_kwh":     energy.round(3),
        "rpm":            rpm.round(1),
        "failure_label":  _make_labels(vibration, temperature),
    })


# ── Feature engineering (mirrors recommender.py) ──────────────────────────────

def build_maintenance_features(df: pd.DataFrame) -> pd.DataFrame:
    records = []
    for machine, grp in df.groupby("machine_id"):
        grp = grp.sort_values("timestamp").copy()
        for window, suffix in [(4, "1h"), (12, "3h")]:
            grp[f"vib_mean_{suffix}"]  = grp["vibration_mms"].rolling(window, min_periods=1).mean()
            grp[f"vib_std_{suffix}"]   = grp["vibration_mms"].rolling(window, min_periods=1).std().fillna(0)
            grp[f"vib_max_{suffix}"]   = grp["vibration_mms"].rolling(window, min_periods=1).max()
            grp[f"temp_mean_{suffix}"] = grp["temperature_c"].rolling(window, min_periods=1).mean()
            grp[f"temp_max_{suffix}"]  = grp["temperature_c"].rolling(window, min_periods=1).max()
            grp[f"temp_std_{suffix}"]  = grp["temperature_c"].rolling(window, min_periods=1).std().fillna(0)
        rpm_baseline = grp["rpm"].median()
        grp["rpm_deviation"] = (grp["rpm"] - rpm_baseline).abs()
        grp["hour_of_day"]   = grp["timestamp"].dt.hour
        records.append(grp)
    return pd.concat(records, ignore_index=True)

def build_energy_features(df: pd.DataFrame) -> pd.DataFrame:
    records = []
    for machine, grp in df.groupby("machine_id"):
        grp = grp.sort_values("timestamp").copy()
        for lag in range(1, 7):
            grp[f"energy_lag_{lag}"] = grp["energy_kwh"].shift(lag)
        grp["energy_roll_3h"] = grp["energy_kwh"].rolling(12, min_periods=1).mean()
        grp["energy_roll_6h"] = grp["energy_kwh"].rolling(24, min_periods=1).mean()
        grp["hour_of_day"]    = grp["timestamp"].dt.hour
        grp["day_of_week"]    = grp["timestamp"].dt.dayofweek
        grp["energy_target"]  = grp["energy_kwh"].shift(-12).ffill()
        records.append(grp)
    return pd.concat(records, ignore_index=True).dropna()


MAINT_FEATURES = [
    "vibration_mms", "temperature_c", "energy_kwh", "rpm",
    "vib_mean_1h", "vib_std_1h", "vib_max_1h",
    "temp_mean_1h", "temp_max_1h", "temp_std_1h",
    "vib_mean_3h", "vib_std_3h", "vib_max_3h",
    "temp_mean_3h", "temp_max_3h", "temp_std_3h",
    "rpm_deviation", "hour_of_day",
]
ENERGY_FEATURES = [
    "energy_lag_1","energy_lag_2","energy_lag_3",
    "energy_lag_4","energy_lag_5","energy_lag_6",
    "energy_roll_3h","energy_roll_6h","hour_of_day","day_of_week",
]


# ── DB writer ─────────────────────────────────────────────────────────────────

def _train_models(all_sensor):
    import joblib
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report, mean_absolute_error
    from xgboost import XGBClassifier, XGBRegressor

    MODEL_DIR = Path(__file__).resolve().parent / "saved_models"
    MODEL_DIR.mkdir(exist_ok=True)

    print("Training maintenance model ...")
    df_m = build_maintenance_features(all_sensor)
    X = df_m[MAINT_FEATURES]; y = df_m["failure_label"]
    from sklearn.model_selection import train_test_split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    maint_model = XGBClassifier(n_estimators=150, max_depth=5, learning_rate=0.08,
        scale_pos_weight=(y==0).sum()/max((y==1).sum(),1),
        eval_metric="logloss", random_state=42, verbosity=0)
    maint_model.fit(X_train, y_train)
    print(classification_report(y_test, maint_model.predict(X_test), target_names=["OK","FAILURE_RISK"]))
    joblib.dump(maint_model, MODEL_DIR / "maintenance_model.pkl")

    print("Training energy model ...")
    df_e = build_energy_features(all_sensor)
    Xe = df_e[ENERGY_FEATURES]; ye = df_e["energy_target"]
    Xe_tr, Xe_te, ye_tr, ye_te = train_test_split(Xe, ye, test_size=0.2, random_state=42)
    energy_model = XGBRegressor(n_estimators=120, max_depth=4, learning_rate=0.1, random_state=42, verbosity=0)
    energy_model.fit(Xe_tr, ye_tr)
    print(f"Energy MAE: {mean_absolute_error(ye_te, energy_model.predict(Xe_te)):.3f} kWh")
    joblib.dump(energy_model, MODEL_DIR / "energy_model.pkl")
    print("Models saved.")
    return maint_model, energy_model


def build_database():
    import joblib

    MODEL_DIR = Path(__file__).resolve().parent / "saved_models"
    MODEL_DIR.mkdir(exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    n_rows = int(DAYS * 24 * 60 / 15)

    print("Generating sensor data ...")
    all_sensor = pd.concat(
        [generate_sensor_series(mk, n_rows) for _, _, mk, _ in MACHINES_META],
        ignore_index=True,
    )

    maint_pkl  = MODEL_DIR / "maintenance_model.pkl"
    energy_pkl = MODEL_DIR / "energy_model.pkl"
    if not maint_pkl.exists() or not energy_pkl.exists():
        print("No saved models found — training from scratch ...")
        maint_model, energy_model = _train_models(all_sensor)
    else:
        maint_model  = joblib.load(maint_pkl)
        energy_model = joblib.load(energy_pkl)
        print("Loaded existing models.")

    # Build ML feature frames
    df_maint  = build_maintenance_features(all_sensor)
    df_energy = build_energy_features(all_sensor)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # ── sensor_data (for ML retraining / debugging) ───────────────────────────
    all_sensor.to_sql("sensor_data", conn, if_exists="replace", index=False)

    # ── machines (team schema) ────────────────────────────────────────────────
    c.execute("DROP TABLE IF EXISTS machines")
    c.execute("""
        CREATE TABLE machines (
            id TEXT PRIMARY KEY,
            name TEXT,
            status TEXT,
            temperature REAL,
            vibration REAL,
            last_maintenance TEXT
        )
    """)
    for mid, name, mk, status in MACHINES_META:
        latest = all_sensor[all_sensor["machine_id"] == mk].sort_values("timestamp").iloc[-1]
        c.execute("INSERT INTO machines VALUES (?,?,?,?,?,?)", (
            mid, name, status,
            round(float(latest["temperature_c"]), 1),
            round(float(latest["vibration_mms"]), 2),
            "2025-06-01",
        ))

    # ── predictions (team schema) — ML model output ───────────────────────────
    c.execute("DROP TABLE IF EXISTS predictions")
    c.execute("""
        CREATE TABLE predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id TEXT,
            failure_probability REAL,
            predicted_failure_in_hrs INTEGER,
            timestamp TEXT
        )
    """)
    for mid, _, mk, _ in MACHINES_META:
        machine_df = df_maint[df_maint["machine_id"] == mk].sort_values("timestamp")
        latest = machine_df.iloc[-1]
        X = pd.DataFrame([latest[MAINT_FEATURES]])
        prob = float(maint_model.predict_proba(X)[0][1])

        # Estimate hours to failure from risk level
        if prob >= 0.75:
            hrs_to_failure = 24
        elif prob >= 0.50:
            hrs_to_failure = 72
        else:
            hrs_to_failure = 200

        c.execute(
            "INSERT INTO predictions (machine_id, failure_probability, predicted_failure_in_hrs, timestamp) VALUES (?,?,?,?)",
            (mid, round(prob, 4), hrs_to_failure, datetime.now().isoformat())
        )

    # ── energy_forecast (team schema) ─────────────────────────────────────────
    c.execute("DROP TABLE IF EXISTS energy_forecast")
    c.execute("""
        CREATE TABLE energy_forecast (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hour TEXT,
            actual_kwh REAL,
            predicted_kwh REAL
        )
    """)

    # Aggregate actual energy by hour across all machines, then forecast next 24h
    all_sensor["hour"] = pd.to_datetime(all_sensor["timestamp"]).dt.floor("h")
    hourly_actual = all_sensor.groupby("hour")["energy_kwh"].sum().reset_index()
    hourly_actual = hourly_actual.sort_values("hour").tail(24)  # last 24h actual

    # Forecast next 24h using energy model (per machine, then sum)
    forecast_rows = []
    for h_offset in range(24):
        future_hour = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=h_offset)
        total_forecast = 0.0
        for _, _, mk, _ in MACHINES_META:
            edf = df_energy[df_energy["machine_id"] == mk].sort_values("timestamp")
            if edf.empty:
                continue
            last = edf.iloc[-1].copy()
            last["hour_of_day"]  = future_hour.hour
            last["day_of_week"]  = future_hour.weekday()
            X = pd.DataFrame([last[ENERGY_FEATURES]])
            total_forecast += float(energy_model.predict(X)[0])
        forecast_rows.append((future_hour.strftime("%Y-%m-%d %H:%M"), total_forecast * 4))  # *4: 15-min interval → hourly

    # Match actual + forecast by position (last 24h actual vs next 24h predicted)
    for i, (hour_label, pred_kwh) in enumerate(forecast_rows):
        if i < len(hourly_actual):
            actual = float(hourly_actual.iloc[i]["energy_kwh"])  # already summed across all machines x 4 intervals
        else:
            actual = pred_kwh * np.random.uniform(0.92, 1.08)
        c.execute(
            "INSERT INTO energy_forecast (hour, actual_kwh, predicted_kwh) VALUES (?,?,?)",
            (hour_label, round(actual, 2), round(pred_kwh, 2))
        )

    # ── simulations log (team schema) ─────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS simulations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_order TEXT,
            result TEXT,
            timestamp TEXT
        )
    """)

    conn.commit()
    conn.close()

    print(f"✅  factory.db rebuilt → {DB_PATH}")
    print(f"   sensor_data    : {len(all_sensor):,} rows")
    print(f"   machines       : {len(MACHINES_META)} rows")
    print(f"   predictions    : {len(MACHINES_META)} rows")
    print(f"   energy_forecast: {len(forecast_rows)} rows")

    # Print what the team's recommender will see
    import json
    conn2 = sqlite3.connect(DB_PATH)
    conn2.row_factory = sqlite3.Row
    preds = [dict(r) for r in conn2.execute("""
        SELECT p.machine_id, m.name, p.failure_probability, p.predicted_failure_in_hrs
        FROM predictions p JOIN machines m ON p.machine_id = m.id
        ORDER BY p.failure_probability DESC
    """).fetchall()]
    conn2.close()
    print("\n🔮  Predictions written to DB:")
    for p in preds:
        status = "CRITICAL" if p["failure_probability"] >= 0.75 else ("WARNING" if p["failure_probability"] >= 0.50 else "OK")
        print(f"   {p['name']:20s}  risk={p['failure_probability']:.1%}  [{status}]  est. failure in {p['predicted_failure_in_hrs']}h")


if __name__ == "__main__":
    build_database()