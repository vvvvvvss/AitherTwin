import sqlite3
import json
from datetime import datetime

DB_PATH = "data/factory.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets us access columns by name
    return conn


def init_db():
    import os
    os.makedirs("data", exist_ok=True)

    conn = get_connection()
    c = conn.cursor()

    # Machines table
    c.execute("""
        CREATE TABLE IF NOT EXISTS machines (
            id TEXT PRIMARY KEY,
            name TEXT,
            status TEXT,           -- 'running', 'idle', 'maintenance'
            temperature REAL,
            vibration REAL,
            last_maintenance TEXT
        )
    """)

    # Predictions table (ML model writes here)
    c.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id TEXT,
            failure_probability REAL,
            predicted_failure_in_hrs INTEGER,
            timestamp TEXT
        )
    """)

    # Energy table
    c.execute("""
        CREATE TABLE IF NOT EXISTS energy_forecast (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hour TEXT,
            actual_kwh REAL,
            predicted_kwh REAL
        )
    """)

    # Simulations log
    c.execute("""
        CREATE TABLE IF NOT EXISTS simulations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_order TEXT,
            result TEXT,
            timestamp TEXT
        )
    """)

    # Seed machines if empty
    c.execute("SELECT COUNT(*) FROM machines")
    if c.fetchone()[0] == 0:
        seed_machines = [
            ("M1", "CNC Machine A", "running", 72.4, 0.8, "2025-05-20"),
            ("M2", "Lathe Machine B", "running", 68.1, 0.3, "2025-06-01"),
            ("M3", "Drill Press C",   "idle",    55.0, 0.1, "2025-06-10"),
            ("M4", "Conveyor D",      "running", 80.5, 1.4, "2025-04-15"),
        ]
        c.executemany(
            "INSERT INTO machines VALUES (?,?,?,?,?,?)", seed_machines
        )

    # Seed predictions if empty
    c.execute("SELECT COUNT(*) FROM predictions")
    if c.fetchone()[0] == 0:
        seed_predictions = [
            ("M1", 0.85, 48, datetime.now().isoformat()),
            ("M2", 0.22, 200, datetime.now().isoformat()),
            ("M4", 0.61, 72, datetime.now().isoformat()),
        ]
        c.executemany(
            "INSERT INTO predictions (machine_id, failure_probability, predicted_failure_in_hrs, timestamp) VALUES (?,?,?,?)",
            seed_predictions
        )

    # Seed energy forecast if empty
    c.execute("SELECT COUNT(*) FROM energy_forecast")
    if c.fetchone()[0] == 0:
        import random
        seed_energy = [
            (f"2025-06-13 {h:02d}:00", round(random.uniform(80, 130), 1), round(random.uniform(75, 135), 1))
            for h in range(24)
        ]
        c.executemany(
            "INSERT INTO energy_forecast (hour, actual_kwh, predicted_kwh) VALUES (?,?,?)",
            seed_energy
        )

    conn.commit()
    conn.close()
    print("Database initialized.")


# ----------------------------
# QUERY FUNCTIONS
# ----------------------------

def get_machines():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM machines").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_predictions():
    conn = get_connection()
    rows = conn.execute("""
        SELECT p.machine_id, m.name, p.failure_probability, p.predicted_failure_in_hrs, p.timestamp
        FROM predictions p
        JOIN machines m ON p.machine_id = m.id
        ORDER BY p.failure_probability DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_energy_data():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM energy_forecast ORDER BY hour").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_simulation(order, result):
    conn = get_connection()
    conn.execute(
        "INSERT INTO simulations (batch_order, result, timestamp) VALUES (?,?,?)",
        (json.dumps(order), json.dumps(result), datetime.now().isoformat())
    )
    conn.commit()
    conn.close()