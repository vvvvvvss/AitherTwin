"""
live_simulator.py
─────────────────
Simulates real-time factory data. Machines change status, predictions update,
energy fluctuates. This makes the dashboard dynamic and responsive.
"""

import numpy as np
from datetime import datetime
import random

# In-memory state of machines (updated every API call)
MACHINES_STATE = {
    "M1": {
        "name": "CNC Machine A",
        "x": 2,
        "y": 3,
        "status": "running",
        "vibration": 3.2,
        "temperature": 62,
        "energy_kw": 18,
        "rpm": 1450,
    },
    "M2": {
        "name": "Lathe Machine B",
        "x": 5,
        "y": 4,
        "status": "running",
        "vibration": 4.1,
        "temperature": 68,
        "energy_kw": 22,
        "rpm": 950,
    },
    "M3": {
        "name": "Drill Press C",
        "x": 8,
        "y": 2,
        "status": "running",
        "vibration": 2.5,
        "temperature": 71,
        "energy_kw": 31,
        "rpm": 1200,
    },
}

# Track time for energy hourly aggregation
ENERGY_HISTORY = []


def simulate_sensor_drift():
    """Simulate real-time sensor changes with occasional faults."""
    for machine_id, state in MACHINES_STATE.items():
        # Add random sensor noise
        state["vibration"] += np.random.normal(0, 0.2)
        state["temperature"] += np.random.normal(0, 0.5)
        state["energy_kw"] += np.random.normal(0, 0.5)
        state["rpm"] += np.random.normal(0, 10)

        # Clamp values
        state["vibration"] = max(1.0, min(12.0, state["vibration"]))
        state["temperature"] = max(35, min(95, state["temperature"]))
        state["energy_kw"] = max(5, min(55, state["energy_kw"]))
        state["rpm"] = max(600, min(1800, state["rpm"]))

        # Simulate occasional faults (10% chance per update)
        if random.random() < 0.10:
            state["status"] = random.choice(["warning", "critical", "running"])
            if state["status"] == "critical":
                state["vibration"] += 3.0  # spike vibration during fault
                state["temperature"] += 5.0  # spike temperature
        else:
            state["status"] = "running"


def get_live_machines():
    """Return current machine states with simulated changes."""
    simulate_sensor_drift()
    machines = []
    for machine_id, state in MACHINES_STATE.items():
        machines.append({
            "id": machine_id,
            "name": state["name"],
            "x": state["x"],
            "y": state["y"],
            "status": state["status"],
            "vibration": round(state["vibration"], 2),
            "temperature": round(state["temperature"], 1),
            "energy_kw": round(state["energy_kw"], 2),
            "rpm": round(state["rpm"], 0),
        })
    return {"machines": machines}


def get_live_predictions():
    """Generate predictions based on current sensor state."""
    predictions = []
    for machine_id, state in MACHINES_STATE.items():
        # Calculate failure probability based on sensor values
        vib_risk = min(1.0, state["vibration"] / 10.0)
        temp_risk = min(1.0, (state["temperature"] - 50) / 45.0)
        failure_prob = (vib_risk * 0.6 + temp_risk * 0.4) + np.random.normal(0, 0.05)
        failure_prob = max(0, min(1.0, failure_prob))

        # Determine severity
        if failure_prob > 0.75:
            severity = "critical"
            failure_in_hrs = max(1, int(np.random.normal(6, 2)))
        elif failure_prob > 0.5:
            severity = "warning"
            failure_in_hrs = max(4, int(np.random.normal(24, 4)))
        else:
            severity = "normal"
            failure_in_hrs = int(np.random.normal(48, 8))

        predictions.append({
            "machine_id": machine_id,
            "machine": state["name"],
            "failure_probability": round(failure_prob, 3),
            "predicted_failure_in_hrs": max(0, failure_in_hrs),
            "severity": severity,
            "confidence": round(0.85 + np.random.uniform(0, 0.15), 2),
        })

    # Sort by risk (highest first)
    predictions.sort(
        key=lambda x: x["failure_probability"], reverse=True
    )
    return {"predictions": predictions}


def get_live_energy():
    """Return hourly energy data with rolling updates."""
    now = datetime.now()
    energy_data = []

    for hour_offset in range(24):
        hour_ago = now.replace(hour=(now.hour - hour_offset) % 24)
        hour_str = hour_ago.strftime("%H:00")

        # Base energy + random variation
        total_actual = sum(
            MACHINES_STATE[m]["energy_kw"] for m in MACHINES_STATE
        )
        actual = total_actual + np.random.normal(0, 5)
        actual = max(20, min(120, actual))

        # Predicted is smoother
        predicted = actual + np.random.normal(0, 2)
        predicted = max(20, min(120, predicted))

        energy_data.append({
            "hour": hour_str,
            "actual_kwh": round(actual, 2),
            "predicted_kwh": round(predicted, 2),
        })

    return energy_data


def get_live_recommendations():
    """Generate AI recommendations based on predictions."""
    predictions_data = get_live_predictions()["predictions"]
    recommendations = []

    for pred in predictions_data:
        machine_id = pred["machine_id"]
        state = MACHINES_STATE[machine_id]
        severity = pred["severity"]

        if severity == "critical":
            message = f"⚠️ URGENT: {state['name']} at critical vibration ({state['vibration']} mm/s). Schedule maintenance within 6 hrs."
            savings = int(np.random.uniform(15000, 30000))
            downtime = int(np.random.uniform(2, 6))
        elif severity == "warning":
            message = f"⚡ {state['name']} showing elevated temperature ({state['temperature']}°C). Monitor closely. Plan maintenance this week."
            savings = int(np.random.uniform(5000, 12000))
            downtime = int(np.random.uniform(1, 3))
        else:
            message = f"✅ {state['name']} operating normally. Energy consumption: {state['energy_kw']} kW"
            savings = int(np.random.uniform(500, 2000))
            downtime = 0

        recommendations.append({
            "machine_id": machine_id,
            "machine": state["name"],
            "recommendation": message,
            "priority": severity,
            "financial_impact": {
                "estimated_savings_inr": savings,
                "downtime_avoided_hrs": downtime,
            },
        })

    return {"recommendations": recommendations}
