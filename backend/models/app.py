from flask import Flask, jsonify, request, render_template
from database import init_db, get_machines, get_predictions, get_energy_data, save_simulation
from simulator import run_schedule_simulation
from recommender import generate_recommendations

app = Flask(
    __name__,
    template_folder="../../frontend/templates",
    static_folder="../../frontend/static"
)

# Initialize DB on startup
init_db()

# ----------------------------
# DASHBOARD ROUTE
# ----------------------------
@app.route("/")
def dashboard():
    return render_template("dashboard.html")


# ----------------------------
# API ROUTES
# ----------------------------

@app.route("/api/machines", methods=["GET"])
def machines():
    data = get_machines()
    return jsonify(data)


@app.route("/api/predictions", methods=["GET"])
def predictions():
    data = get_predictions()
    return jsonify(data)


@app.route("/api/energy", methods=["GET"])
def energy():
    data = get_energy_data()
    return jsonify(data)


@app.route("/api/simulate", methods=["POST"])
def simulate():
    body = request.get_json()

    if not body or "batches" not in body or "order" not in body:
        return jsonify({
            "error": "Missing 'batches' or 'order' in request body"
        }), 400

    result = run_schedule_simulation(
        body["batches"],
        body["order"]
    )

    save_simulation(body["order"], result)
    return jsonify(result)


@app.route("/api/recommendations", methods=["GET"])
def recommendations():
    data = generate_recommendations()
    return jsonify(data)


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)