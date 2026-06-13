"""
Production Schedule Simulator
------------------------------
Takes a list of batches and a proposed order,
simulates the schedule, detects bottlenecks,
and suggests an optimized order.
"""

from itertools import permutations


ENERGY_RATE_PER_KWH = 8  # ₹ per kWh (adjust to local rate)


def run_schedule_simulation(batches: list, order: list) -> dict:
    """
    Simulates a production schedule given a batch order.

    Args:
        batches: list of dicts with keys: id, machine, duration_hrs, energy_kw
        order:   list of batch IDs in proposed sequence

    Returns:
        dict with simulation results
    """
    batch_map = {b["id"]: b for b in batches}

    # --- Simulate proposed order ---
    proposed = _simulate_order(batch_map, order)

    # --- Find optimized order (brute force for small batches) ---
    best_order, best_result = _find_best_order(batch_map, order)

    # --- Build response ---
    return {
        "proposed_order": {
            "sequence": order,
            "total_duration_hrs": proposed["total_duration_hrs"],
            "total_energy_kwh": proposed["total_energy_kwh"],
            "estimated_cost_inr": proposed["estimated_cost_inr"],
            "bottleneck_machine": proposed["bottleneck"],
            "schedule": proposed["schedule"]
        },
        "optimized_order": {
            "sequence": best_order,
            "total_duration_hrs": best_result["total_duration_hrs"],
            "total_energy_kwh": best_result["total_energy_kwh"],
            "estimated_cost_inr": best_result["estimated_cost_inr"],
            "bottleneck_machine": best_result["bottleneck"],
            "schedule": best_result["schedule"]
        },
        "savings": {
            "time_saved_hrs": round(proposed["total_duration_hrs"] - best_result["total_duration_hrs"], 2),
            "energy_saved_kwh": round(proposed["total_energy_kwh"] - best_result["total_energy_kwh"], 2),
            "cost_saved_inr": round(proposed["estimated_cost_inr"] - best_result["estimated_cost_inr"], 2),
        }
    }


def _simulate_order(batch_map: dict, order: list) -> dict:
    """Simulate a given order and return metrics."""
    machine_free_at = {}   # tracks when each machine is next free
    schedule = []
    total_energy = 0.0

    current_time = 0.0

    for batch_id in order:
        if batch_id not in batch_map:
            continue
        batch = batch_map[batch_id]
        machine = batch["machine"]
        duration = batch["duration_hrs"]
        energy_kw = batch["energy_kw"]

        # Batch can start when the machine is free
        start = max(current_time, machine_free_at.get(machine, 0))
        end = start + duration
        machine_free_at[machine] = end

        energy_used = energy_kw * duration
        total_energy += energy_used

        schedule.append({
            "batch_id": batch_id,
            "machine": machine,
            "start_hr": round(start, 2),
            "end_hr": round(end, 2),
            "energy_kwh": round(energy_used, 2)
        })

    total_duration = max(machine_free_at.values()) if machine_free_at else 0

    # Bottleneck = machine with the most total usage time
    machine_usage = {}
    for s in schedule:
        m = s["machine"]
        machine_usage[m] = machine_usage.get(m, 0) + (s["end_hr"] - s["start_hr"])
    bottleneck = max(machine_usage, key=machine_usage.get) if machine_usage else None

    return {
        "total_duration_hrs": round(total_duration, 2),
        "total_energy_kwh": round(total_energy, 2),
        "estimated_cost_inr": round(total_energy * ENERGY_RATE_PER_KWH, 2),
        "bottleneck": bottleneck,
        "schedule": schedule
    }


def _find_best_order(batch_map: dict, order: list) -> tuple:
    """
    Brute-force best order by minimizing total duration.
    Only feasible for <= 8 batches. For larger sets, use greedy fallback.
    """
    if len(order) <= 8:
        best_order = order
        best_result = _simulate_order(batch_map, order)

        for perm in permutations(order):
            result = _simulate_order(batch_map, list(perm))
            if result["total_duration_hrs"] < best_result["total_duration_hrs"]:
                best_result = result
                best_order = list(perm)

        return best_order, best_result
    else:
        # Greedy fallback: sort by duration ascending
        sorted_order = sorted(order, key=lambda b: batch_map[b]["duration_hrs"])
        return sorted_order, _simulate_order(batch_map, sorted_order)