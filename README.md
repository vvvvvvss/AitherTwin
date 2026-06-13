# AitherTwin

# Factory Digital Twin — Backend

## Setup

```bash
pip install -r requirements.txt
python backend/models/data_generator.py
python backend/models/app.py
```

Server runs at `http://localhost:5000`

---

## API Reference

### GET /api/machines
Returns all machines and their current status.

### GET /api/predictions
Returns ML failure predictions, sorted by highest risk first.

### GET /api/energy
Returns hourly energy forecast data.

### GET /api/recommendations
Returns AI recommendations with ₹ financial impact.

### POST /api/simulate
Simulates a production schedule and returns optimized order.

**Request body:**
```json
{
  "batches": [
    {"id": "B1", "machine": "M1", "duration_hrs": 3, "energy_kw": 15},
    {"id": "B2", "machine": "M2", "duration_hrs": 2, "energy_kw": 10},
    {"id": "B3", "machine": "M1", "duration_hrs": 1, "energy_kw": 8}
  ],
  "order": ["B1", "B2", "B3"]
}
```

**Response includes:**
- Proposed schedule timeline
- Optimized schedule (auto-calculated)
- Time / energy / cost savings comparison

---

## File Structure

```
backend/
├── app.py           # Flask routes
├── database.py      # SQLite init + queries
├── simulator.py     # Schedule simulation logic
├── recommender.py   # Recommendation engine
├── requirements.txt
└── data/
    └── factory.db   # Auto-created on first run
```

## Integration Notes (for teammates)

**Person 1 (ML):** Write your model predictions into the `predictions` table:
```python
import sqlite3, json
conn = sqlite3.connect("data/factory.db")
conn.execute(
    "INSERT INTO predictions (machine_id, failure_probability, predicted_failure_in_hrs, timestamp) VALUES (?,?,?,?)",
    ("M1", 0.87, 36, "2025-06-13T10:00:00")
)
conn.commit()
```

**Person 3 (Frontend):** All endpoints return JSON. Base URL: `http://localhost:5000`