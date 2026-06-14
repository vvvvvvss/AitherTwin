# AitherTwin — AI Agent Guide

**Project:** Factory Digital Twin with ML-based predictive maintenance, energy optimization, and production scheduling.

## Quick Start

```bash
# Setup (one-time)
pip install -r backend/requirements.txt
python backend/models/data_generator.py      # Initialize DB + train models
python backend/models/app.py                  # Start Flask server (port 5000)

# Access
http://localhost:5000                         # Dashboard
http://localhost:5000/api/health              # Health check
```

See [README.md](README.md) for full API reference.

## Architecture at a Glance

```
FRONTEND (dashboard.html + dashboard.js)
         ↓ (5 API calls)
BACKEND (Flask app.py)
         ↓ (query DB, call logic)
LOGIC (simulator.py, recommender.py)
         ↓ (read predictions/energy)
DATABASE (SQLite: machines, predictions, energy_forecast, simulations)
         ↑ (seed from data_generator.py)
```

**Responsibilities:**
- **[backend/models/app.py](backend/models/app.py)** — Flask routes, serves frontend & JSON API
- **[backend/models/database.py](backend/models/database.py)** — SQLite schema (4 tables), connection management
- **[backend/models/simulator.py](backend/models/simulator.py)** — Production schedule optimizer (cost-aware)
- **[backend/models/recommender.py](backend/models/recommender.py)** — Maintenance + energy recommendations from XGBoost predictions
- **[backend/models/data_generator.py](backend/models/data_generator.py)** — Synthetic sensor data + model training
- **[frontend/static/dashboard.js](frontend/static/dashboard.js)** — Fetch API endpoints, render with Plotly
- **[frontend/static/style.css](frontend/static/style.css)** — Dark theme styling

## Key Conventions

| Item | Rule | Example |
|------|------|---------|
| **Currency** | Indian Rupees (₹) hardcoded | Energy cost: ₹8/kWh, downtime: ₹8,750/hr |
| **Machine IDs** | M1, M2, M3, ... | Used consistently across DB, logic, frontend |
| **Timestamps** | ISO 8601 format | `2025-06-13T10:00:00` in database |
| **Sensor Freq** | 15-minute intervals | Rolling windows: 1h & 3h aggregates for features |
| **Python Naming** | snake_case | `get_predictions()`, `calculate_cost()` |
| **JS Naming** | camelCase | `fetchMachines()`, `renderChart()` |
| **Feature Columns** | Derived from sensor data | vibration_mms, temperature_c, energy_kwh, rpm, + rolling stats |

## Common Pitfalls

| Issue | Solution |
|-------|----------|
| **"Database not found" error** | Always run `data_generator.py` before `app.py`. It auto-creates schema and seeds initial data. |
| **Port 5000 already in use** | Kill: `lsof -i :5000 \| grep python \| awk '{print $2}' \| xargs kill -9`. Or edit [app.py line 42](backend/models/app.py#L42). |
| **Dashboard shows "System Offline"** | Backend crashed or not running. Check [app.py line 42](backend/models/app.py#L42) port; test `/api/health` directly. |
| **Empty predictions/recommendations** | `data_generator.py` must complete first (creates trained XGBoost models in memory, writes predictions to DB). |
| **Simulation errors in POST /api/simulate** | Validate batch request body matches database keys. Simulator silently skips unknown batch IDs. |
| **Feature mismatch in recommender.py** | Must match columns from [data_generator.py line 23-34](backend/models/data_generator.py#L23-L34): vibration_mms, temperature_c, energy_kwh, rpm + rolling aggregates. |

## Integration Points

### Backend → Frontend
- `/api/health` — uptime check
- `/api/machines` — factory layout (machine status scatter)
- `/api/predictions` — failure risks (sorted HIGH → LOW)
- `/api/energy` — hourly kWh (actual vs. forecast)
- `/api/recommendations` — maintenance + energy tips
- `/api/simulate` (POST) — schedule optimization

### Data Pipeline
1. **[data_generator.py](backend/models/data_generator.py)** generates 60 days of synthetic sensor data
2. Trains XGBoost models (saved in memory; no .pkl files)
3. Writes **predictions** table (machine_id, failure_probability, predicted_failure_in_hrs, timestamp)
4. Writes **energy_forecast** table (machine_id, hour, forecast_kwh)
5. **[recommender.py](backend/models/recommender.py)** reads predictions + energy → ranks by priority & cost

### Production Scheduler
- User POSTs batch list + proposed order to `/api/simulate`
- **[simulator.py](backend/models/simulator.py)** brute-forces optimal permutation (≤8 batches) or greedy fallback
- Returns proposed vs. optimized schedule with time/energy/cost deltas (₹ savings in rupees)

## Development Workflow

1. **Start fresh:** Delete `backend/data/factory.db` if needed, then re-run `data_generator.py`
2. **Test an endpoint:** Use `/api/health` first (simplest, no DB reads)
3. **Check DB state:** Open `backend/data/factory.db` in SQLite browser; verify tables have rows
4. **Debug frontend:** Open browser DevTools (F12); check Network tab for API response JSON
5. **Modify models:** Edit [recommender.py](backend/models/recommender.py) or [simulator.py](backend/models/simulator.py); no restart needed if just changing logic (but if changing feature columns, regenerate with `data_generator.py`)

## File Locations

```
backend/
├── requirements.txt              ← All dependencies
├── models/
│   ├── app.py                    ← Flask entry point
│   ├── database.py               ← SQLite schema + helpers
│   ├── simulator.py              ← Schedule optimizer
│   ├── recommender.py            ← ML inference layer
│   └── data_generator.py         ← Setup & training script
└── data/
    └── factory.db                ← Auto-created SQLite DB

frontend/
├── templates/
│   └── dashboard.html            ← Jinja2 template (served by Flask)
└── static/
    ├── dashboard.js              ← Fetch + Plotly rendering
    └── style.css                 ← Dark theme
```

## Quick Debugging Checklist

- [ ] Backend running? Test: `curl http://localhost:5000/api/health`
- [ ] Database exists? Check: `ls -la backend/data/factory.db`
- [ ] Database has data? Run in Python: `sqlite3 backend/data/factory.db "SELECT COUNT(*) FROM predictions;"`
- [ ] Requirements installed? Run: `pip show xgboost scikit-learn flask`
- [ ] Port conflict? Run: `lsof -i :5000`
- [ ] Frontend loads? Open http://localhost:5000 in browser
- [ ] API endpoints return JSON? Test each in browser/curl before debugging frontend

---

**For detailed setup and API docs, see [README.md](README.md).**
