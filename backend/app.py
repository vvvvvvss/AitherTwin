from flask import Flask, jsonify, request
from database import init_db, get_machines, get_predictions, get_energy_data, save_simulation
from simulator import run_schedule_simulation
from recommender import generate_recommendations

app = Flask(__name__)

# Initialize DB on startup
init_db()

# ----------------------------
# ROUTES
# ----------------------------

@app.route("/api/machines", methods=["GET"])
def machines():
    """Returns machine list and current status."""
    data = get_machines()
    return jsonify(data)


@app.route("/api/predictions", methods=["GET"])
def predictions():
    """Returns ML failure predictions (fed by Person 1's model output)."""
    data = get_predictions()
    return jsonify(data)


@app.route("/api/energy", methods=["GET"])
def energy():
    """Returns energy consumption forecast data."""
    data = get_energy_data()
    return jsonify(data)


@app.route("/api/simulate", methods=["POST"])
def simulate():
    """
    Runs what-if production schedule simulation.
    
    Expected JSON body:
    {
        "batches": [
            {"id": "B1", "machine": "M1", "duration_hrs": 3, "energy_kw": 15},
            {"id": "B2", "machine": "M2", "duration_hrs": 2, "energy_kw": 10}
        ],
        "order": ["B1", "B2"]   # sequence to simulate
    }
    """
    body = request.get_json()
    if not body or "batches" not in body or "order" not in body:
        return jsonify({"error": "Missing 'batches' or 'order' in request body"}), 400

    result = run_schedule_simulation(body["batches"], body["order"])
    save_simulation(body["order"], result)
    return jsonify(result)


@app.route("/api/recommendations", methods=["GET"])
def recommendations():
    """Returns AI-generated recommendations with financial impact."""
    data = generate_recommendations()
    return jsonify(data)


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)