"""
AI Recommendation Engine
--------------------------
Reads predictions and machine data from the DB,
generates human-readable recommendations with financial impact estimates.
"""

from database import get_predictions, get_machines, get_energy_data

DOWNTIME_COST_PER_HR = 8750      # ₹ per hour of machine downtime
MAINTENANCE_COST_REACTIVE = 25000 # ₹ reactive (breakdown) maintenance
MAINTENANCE_COST_PREVENTIVE = 8000 # ₹ preventive maintenance
ENERGY_RATE_PER_KWH = 8          # ₹ per kWh


def generate_recommendations() -> dict:
    predictions = get_predictions()
    machines = get_machines()
    energy = get_energy_data()

    recommendations = []

    # --- Maintenance recommendations from ML predictions ---
    for pred in predictions:
        prob = pred["failure_probability"]
        hrs = pred["predicted_failure_in_hrs"]
        name = pred["name"]
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
                        "downtime_cost_avoided": downtime_avoided_hrs * DOWNTIME_COST_PER_HR
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

    # --- Energy recommendation (peak hours) ---
    if energy:
        avg_kwh = sum(e["predicted_kwh"] for e in energy) / len(energy)
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
                    "energy_reduction_pct": round((potential_saving_kwh / sum(e["predicted_kwh"] for e in energy)) * 100, 1)
                }
            })

    # --- Sort by priority ---
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    recommendations.sort(key=lambda r: priority_order.get(r["priority"], 3))

    total_savings = sum(
        r["financial_impact"].get("estimated_savings_inr", 0)
        for r in recommendations
    )

    return {
        "total_recommendations": len(recommendations),
        "total_estimated_savings_inr": round(total_savings, 2),
        "recommendations": recommendations
    }