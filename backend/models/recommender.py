"""
recommender.py
--------------
Two responsibilities:
  1. ML model training + inference (XGBoost maintenance + energy)
  2. generate_recommendations() — called by app.py
"""

import sqlite3
import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, mean_absolute_error
from xgboost import XGBClassifier, XGBRegressor

BASE_DIR  = Path(__file__).resolve().parent
DB_PATH   = BASE_DIR.parent / "data" / "factory.db"
MODEL_DIR = BASE_DIR / "saved_models"
MODEL_DIR.mkdir(exist_ok=True)

DOWNTIME_COST_PER_HR      = 8750
MAINTENANCE_COST_REACTIVE  = 25000
MAINTENANCE_COST_PREVENTIVE = 8000
ENERGY_RATE_PER_KWH        = 8

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


# ── DB helpers ────────────────────────────────────────────────────────────────

def _get_predictions():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT p.machine_id, m.name, p.failure_probability, p.predicted_failure_in_hrs, p.timestamp
        FROM predictions p
        JOIN machines m ON p.machine_id = m.id
        ORDER BY p.failure_probability DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def _get_machines():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM machines").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def _get_energy_data():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM energy_forecast ORDER BY hour").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Recommendations (called by app.py) ───────────────────────────────────────

def generate_recommendations() -> dict:
    predictions = _get_predictions()
    machines    = _get_machines()
    energy      = _get_energy_data()

    recommendations = []

    for pred in predictions:
        prob       = pred["failure_probability"]
        hrs        = pred["predicted_failure_in_hrs"]
        name       = pred["name"]
        machine_id = pred["machine_id"]

        if prob >= 0.75:
            downtime_avoided_hrs = 4
            savings = (MAINTENANCE_COST_REACTIVE - MAINTENANCE_COST_PREVENTIVE) + \
                      (downtime_avoided_hrs * DOWNTIME_COST_PER_HR)
            recommendations.append({
                "type": "CRITICAL_MAINTENANCE",
                "machine": name,
                "machine_id": machine_id,
                "message": f"{name} has a {int(prob*100)}% failure probability within {hrs} hours. Schedule maintenance immediately.",
                "priority": "HIGH",
                "financial_impact": {
                    "downtime_avoided_hrs": downtime_avoided_hrs,
                    "estimated_savings_inr": savings,
                    "maintenance_cost_inr": MAINTENANCE_COST_PREVENTIVE,
                    "breakdown": {
                        "reactive_cost_avoided": MAINTENANCE_COST_REACTIVE,
                        "downtime_cost_avoided": downtime_avoided_hrs * DOWNTIME_COST_PER_HR,
                    }
                }
            })
        elif prob >= 0.50:
            downtime_avoided_hrs = 2
            savings = (MAINTENANCE_COST_REACTIVE - MAINTENANCE_COST_PREVENTIVE) + \
                      (downtime_avoided_hrs * DOWNTIME_COST_PER_HR)
            recommendations.append({
                "type": "SCHEDULED_MAINTENANCE",
                "machine": name,
                "machine_id": machine_id,
                "message": f"{name} shows moderate wear ({int(prob*100)}% failure risk). Plan maintenance within {hrs} hours.",
                "priority": "MEDIUM",
                "financial_impact": {
                    "downtime_avoided_hrs": downtime_avoided_hrs,
                    "estimated_savings_inr": savings,
                    "maintenance_cost_inr": MAINTENANCE_COST_PREVENTIVE,
                }
            })

    if energy:
        avg_kwh    = sum(e["predicted_kwh"] for e in energy) / len(energy)
        peak_hours = [e for e in energy if e["predicted_kwh"] > avg_kwh * 1.15]
        if peak_hours:
            peak_labels = [e["hour"].split(" ")[1][:5] for e in peak_hours[:3]]
            potential_saving_kwh = sum(e["predicted_kwh"] - avg_kwh for e in peak_hours)
            recommendations.append({
                "type": "ENERGY_OPTIMIZATION",
                "machine": "All",
                "machine_id": None,
                "message": f"Shift heavy operations away from peak hours ({', '.join(peak_labels)}). Predicted high energy draw.",
                "priority": "MEDIUM",
                "financial_impact": {
                    "energy_reduction_kwh": round(potential_saving_kwh, 1),
                    "estimated_savings_inr": round(potential_saving_kwh * ENERGY_RATE_PER_KWH, 2),
                    "energy_reduction_pct": round(
                        (potential_saving_kwh / sum(e["predicted_kwh"] for e in energy)) * 100, 1
                    )
                }
            })

    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    recommendations.sort(key=lambda r: priority_order.get(r["priority"], 3))

    total_savings = sum(
        r["financial_impact"].get("estimated_savings_inr", 0)
        for r in recommendations
    )

    return {
        "total_recommendations": len(recommendations),
        "total_estimated_savings_inr": round(total_savings, 2),
        "recommendations": recommendations,
    }