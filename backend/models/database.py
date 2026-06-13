import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "factory.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Called by app.py on startup. Creates tables only if they don't exist.
    Does NOT overwrite data — your ML predictions from data_generator.py are safe."""
    import os
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS machines (
            id TEXT PRIMARY KEY,
            name TEXT,
            status TEXT,
            temperature REAL,
            vibration REAL,
            last_maintenance TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id TEXT,
            failure_probability REAL,
            predicted_failure_in_hrs INTEGER,
            timestamp TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS energy_forecast (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hour TEXT,
            actual_kwh REAL,
            predicted_kwh REAL
        )
    """)
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