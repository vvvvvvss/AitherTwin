// ====== AitherTwin Dashboard Frontend Logic ======
// This file calls all 5 backend API endpoints and renders the results.
const API_BASE = ""; // same origin, since Flask serves both page + API

// -------------------- 1. HEALTH CHECK --------------------
async function checkHealth() {
  const el = document.getElementById("health-status");
  try {
    const res = await fetch(`${API_BASE}/api/health`);
    const data = await res.json();
    el.textContent = "System Online ✅ " + (data.status || data.message || "");
    el.classList.add("ok");
  } catch (err) {
    el.textContent = "Backend not reachable ❌";
    el.classList.add("error");
    console.error("Health check failed:", err);
  }
}

// -------------------- 2. FACTORY LAYOUT (Plotly) --------------------
async function loadFactoryLayout() {
  try {
    const res = await fetch(`${API_BASE}/api/machines`);
    const data = await res.json();

    // Expecting something like:
    // { machines: [ {id, name, x, y, status}, ... ] }
    // Adjust "machines" key below if your backend returns a plain array.
    const machines = data.machines || data;

    const x = machines.map(m => m.x ?? Math.random() * 10);
    const y = machines.map(m => m.y ?? Math.random() * 10);
    const labels = machines.map(m => m.name || m.id || "Machine");
    const statuses = machines.map(m => m.status || "normal");

    // Color-code by status
    const colors = statuses.map(s => {
      if (s.toLowerCase().includes("fault") || s.toLowerCase().includes("critical")) return "#f44336";
      if (s.toLowerCase().includes("warn")) return "#ffb300";
      return "#4caf50";
    });

    const trace = {
      x: x,
      y: y,
      text: labels,
      mode: "markers+text",
      type: "scatter",
      textposition: "top center",
      marker: { size: 22, color: colors, line: { width: 2, color: "#fff" } }
    };

    const layout = {
      paper_bgcolor: "#161a23",
      plot_bgcolor: "#161a23",
      font: { color: "#e6e6e6" },
      xaxis: { title: "Factory X (m)", gridcolor: "#2a2f3a" },
      yaxis: { title: "Factory Y (m)", gridcolor: "#2a2f3a" },
      margin: { t: 20 }
    };

    Plotly.newPlot("factory-layout", [trace], layout, { responsive: true });
  } catch (err) {
    console.error("Failed to load machines:", err);
    document.getElementById("factory-layout").innerHTML =
      "<p style='color:#f44336'>Could not load factory layout.</p>";
  }
}

// -------------------- 3. PREDICTIONS --------------------
async function loadPredictions() {
  const container = document.getElementById("predictions-list");
  try {
    const res = await fetch(`${API_BASE}/api/predictions`);
    const data = await res.json();

    // Expecting: { predictions: [ {machine, prediction, confidence, severity}, ... ] }
    const predictions = data.predictions || data;

    container.innerHTML = "";
    predictions.forEach(p => {
      const severity = (p.severity || p.status || "normal").toLowerCase();
      const div = document.createElement("div");
      div.className = "pred-item " + (severity.includes("crit") ? "critical" : severity.includes("warn") ? "warning" : "");
      div.innerHTML = `
        <div class="machine-name">${p.machine || p.machine_id || "Machine"}</div>
        <div class="pred-detail">
          Prediction: ${p.prediction || p.failure_type || "Normal operation"} <br>
          Confidence: ${p.confidence ? (p.confidence * 100).toFixed(1) + "%" : "N/A"}
        </div>
      `;
      container.appendChild(div);
    });
  } catch (err) {
    console.error("Failed to load predictions:", err);
    container.innerHTML = "<p style='color:#f44336'>Could not load predictions.</p>";
  }
}

// -------------------- 4. ENERGY GRAPH (Plotly) --------------------
async function loadEnergyChart() {
  try {
    const res = await fetch(`${API_BASE}/api/energy`);
    const data = await res.json();

    const trace1 = {
      x: data.map(e => e.hour),
      y: data.map(e => e.actual_kwh),
      type: "scatter",
      mode: "lines+markers",
      name: "Actual Energy",
      line: { color: "#4dd0e1" }
    };

    const trace2 = {
      x: data.map(e => e.hour),
      y: data.map(e => e.predicted_kwh),
      type: "scatter",
      mode: "lines+markers",
      name: "Predicted Energy",
      line: { color: "#ff9800" }
    };

    const layout = {
      paper_bgcolor: "#161a23",
      plot_bgcolor: "#161a23",
      font: { color: "#e6e6e6" },
      title: "Energy Consumption",
      xaxis: { title: "Time", gridcolor: "#2a2f3a" },
      yaxis: { title: "Energy (kWh)", gridcolor: "#2a2f3a" },
      margin: { t: 20 }
    };

    Plotly.newPlot(
      "energy-chart",
      [trace1, trace2],
      layout,
      { responsive: true }
    );

  } catch (err) {
    console.error("Failed to load energy data:", err);
    document.getElementById("energy-chart").innerHTML =
      "<p style='color:#f44336'>Could not load energy data.</p>";
  }
}

// -------------------- 5. RECOMMENDATIONS --------------------
async function loadRecommendations() {
  const container = document.getElementById("recommendations-list");
  try {
    const res = await fetch(`${API_BASE}/api/recommendations`);
    const data = await res.json();

    const recs = data.recommendations || data;

    container.innerHTML = "";
    recs.forEach(r => {
      const div = document.createElement("div");
      div.className = "rec-item";
      div.innerHTML = `
        <div class="machine-name">${r.machine || r.machine_id || "General"}</div>
        <div class="rec-detail">${r.recommendation || r.message || JSON.stringify(r)}</div>
      `;
      container.appendChild(div);
    });

    // -------------------- 6. FINANCIAL SUMMARY (derived from recommendations) --------------------
    renderFinancialSummary(recs);
  } catch (err) {
    console.error("Failed to load recommendations:", err);
    container.innerHTML = "<p style='color:#f44336'>Could not load recommendations.</p>";
  }
}

function renderFinancialSummary(recs) {
  const container = document.getElementById("financial-summary");

  // Extract financial impact from nested structure
  let totalSavings = 0;
  let totalDowntime = 0;

  recs.forEach(r => {
    if (r.financial_impact) {
      totalSavings += Number(r.financial_impact.estimated_savings_inr || 0);
      totalDowntime += Number(r.financial_impact.downtime_avoided_hrs || 0);
    }
  });

  container.innerHTML = `
    <div class="fin-box">
      <div class="value">₹${totalSavings.toLocaleString("en-IN")}</div>
      <div class="label">Estimated Cost Savings</div>
    </div>
    <div class="fin-box">
      <div class="value">${totalDowntime.toFixed(1)} hrs</div>
      <div class="label">Downtime Avoided</div>
    </div>
  `;
}

// -------------------- INIT --------------------
function loadAll() {
  checkHealth();
  loadFactoryLayout();
  loadPredictions();
  loadEnergyChart();
  loadRecommendations();
}

loadAll();

// Auto-refresh every 30 seconds to simulate live digital twin
setInterval(loadAll, 30000);
