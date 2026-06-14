// ====== AitherTwin Dashboard Frontend Logic (Dynamic) ======
// This file calls all 5 backend API endpoints and renders live updates.
const API_BASE = ""; // same origin, since Flask serves both page + API

// Config for live updates
const REFRESH_INTERVAL_MS = 5000; // Update every 5 seconds
let lastUpdateTime = null;
let updateCounter = 0;

// -------------------- 0. UPDATE INDICATOR --------------------
function updateTimestamp() {
  const el = document.getElementById("last-update");
  if (!el) return;
  const now = new Date().toLocaleTimeString();
  el.textContent = `Last update: ${now}`;
  el.style.opacity = "1";
  // Fade out after 3 seconds
  setTimeout(() => {
    el.style.opacity = "0.5";
  }, 3000);
}

// -------------------- 1. HEALTH CHECK --------------------
async function checkHealth() {
  const el = document.getElementById("health-status");
  try {
    const res = await fetch(`${API_BASE}/api/health`);
    const data = await res.json();
    el.textContent = "System Online ✅ " + (data.status || data.message || "");
    el.classList.remove("error");
    el.classList.add("ok");
  } catch (err) {
    el.textContent = "Backend not reachable ❌";
    el.classList.remove("ok");
    el.classList.add("error");
    console.error("Health check failed:", err);
  }
}

// -------------------- 2. FACTORY LAYOUT (Plotly - Live) --------------------
async function loadFactoryLayout() {
  try {
    const res = await fetch(`${API_BASE}/api/machines`);
    const data = await res.json();

    const machines = data.machines || data;

    const x = machines.map(m => m.x ?? Math.random() * 10);
    const y = machines.map(m => m.y ?? Math.random() * 10);
    const labels = machines.map(m => `${m.name || m.id}\n${m.status}`);
    const statuses = machines.map(m => m.status || "normal");

    // Color-code by status with live updates
    const colors = statuses.map(s => {
      if (s.toLowerCase().includes("critical")) return "#f44336"; // Red for critical
      if (s.toLowerCase().includes("warning")) return "#ffb300";   // Orange for warning
      return "#4caf50"; // Green for running
    });

    const trace = {
      x: x,
      y: y,
      text: labels,
      mode: "markers+text",
      type: "scatter",
      textposition: "top center",
      marker: { 
        size: 24, 
        color: colors, 
        line: { width: 2, color: "#fff" },
        opacity: 0.8
      },
      hovertemplate: "<b>%{text}</b><extra></extra>",
    };

    const layout = {
      paper_bgcolor: "#161a23",
      plot_bgcolor: "#161a23",
      font: { color: "#e6e6e6" },
      xaxis: { title: "Factory X (m)", gridcolor: "#2a2f3a" },
      yaxis: { title: "Factory Y (m)", gridcolor: "#2a2f3a" },
      margin: { t: 20 },
      title: { text: "🏭 Factory Layout (Live)", font: { size: 16 } }
    };

    Plotly.newPlot("factory-layout", [trace], layout, { responsive: true });
  } catch (err) {
    console.error("Failed to load machines:", err);
    document.getElementById("factory-layout").innerHTML =
      "<p style='color:#f44336'>Could not load factory layout.</p>";
  }
}

// -------------------- 3. PREDICTIONS (Live - Sorted) --------------------
async function loadPredictions() {
  const container = document.getElementById("predictions-list");
  try {
    const res = await fetch(`${API_BASE}/api/predictions`);
    const data = await res.json();

    const predictions = data.predictions || data;

    container.innerHTML = "";
    predictions.forEach(p => {
      const severity = (p.severity || p.status || "normal").toLowerCase();
      const div = document.createElement("div");
      
      // Determine styling class
      let styleClass = "pred-item";
      if (severity.includes("critical")) styleClass += " critical";
      else if (severity.includes("warning")) styleClass += " warning";
      else styleClass += " normal";
      
      div.className = styleClass;
      
      // Live-updating failure countdown
      const failureHrs = p.predicted_failure_in_hrs || 0;
      const failureLabel = failureHrs > 0 ? `⏰ ${failureHrs} hrs` : "Stable";
      
      div.innerHTML = `
        <div class="pred-header">
          <div class="machine-name">${p.machine || p.machine_id || "Machine"}</div>
          <div class="severity-badge">${severity.toUpperCase()}</div>
        </div>
        <div class="pred-detail">
          Risk: <strong>${((p.failure_probability || 0) * 100).toFixed(1)}%</strong> | ${failureLabel}<br>
          Confidence: ${(p.confidence ? (p.confidence * 100).toFixed(0) : "N/A")}%
        </div>
      `;
      container.appendChild(div);
    });
  } catch (err) {
    console.error("Failed to load predictions:", err);
    container.innerHTML = "<p style='color:#f44336'>Could not load predictions.</p>";
  }
}

// -------------------- 4. ENERGY GRAPH (Plotly - Live) --------------------
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
      line: { color: "#4dd0e1", width: 2 },
      marker: { size: 6 }
    };

    const trace2 = {
      x: data.map(e => e.hour),
      y: data.map(e => e.predicted_kwh),
      type: "scatter",
      mode: "lines+markers",
      name: "Predicted Energy",
      line: { color: "#ff9800", width: 2, dash: "dash" },
      marker: { size: 6 }
    };

    const layout = {
      paper_bgcolor: "#161a23",
      plot_bgcolor: "#161a23",
      font: { color: "#e6e6e6" },
      title: { text: "⚡ Energy Consumption (Live)", font: { size: 14 } },
      xaxis: { title: "Hour", gridcolor: "#2a2f3a" },
      yaxis: { title: "Energy (kWh)", gridcolor: "#2a2f3a" },
      margin: { t: 20, l: 50, r: 20, b: 40 },
      hovermode: "x unified"
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

// -------------------- 5. RECOMMENDATIONS (Live) --------------------
async function loadRecommendations() {
  const container = document.getElementById("recommendations-list");
  try {
    const res = await fetch(`${API_BASE}/api/recommendations`);
    const data = await res.json();

    const recs = data.recommendations || data;

    container.innerHTML = "";
    recs.forEach(r => {
      const div = document.createElement("div");
      const priority = (r.priority || r.severity || "normal").toLowerCase();
      
      let priorityClass = "rec-item";
      if (priority.includes("critical")) priorityClass += " critical";
      else if (priority.includes("warning")) priorityClass += " warning";
      
      div.className = priorityClass;
      div.innerHTML = `
        <div class="rec-header">
          <div class="machine-name">${r.machine || r.machine_id || "Factory"}</div>
          <div class="priority-label">${priority.toUpperCase()}</div>
        </div>
        <div class="rec-detail">${r.recommendation || r.message || JSON.stringify(r)}</div>
      `;
      container.appendChild(div);
    });

    // Update financial summary with latest data
    renderFinancialSummary(recs);
  } catch (err) {
    console.error("Failed to load recommendations:", err);
    container.innerHTML = "<p style='color:#f44336'>Could not load recommendations.</p>";
  }
}

// -------------------- 6. FINANCIAL SUMMARY (Derived) --------------------
function renderFinancialSummary(recs) {
  const container = document.getElementById("financial-summary");

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
      <div class="label">Est. Savings (24h)</div>
    </div>
    <div class="fin-box">
      <div class="value">${totalDowntime.toFixed(1)} hrs</div>
      <div class="label">Downtime Prevented</div>
    </div>
    <div class="fin-box" style="grid-column: 1 / -1; text-align: center; opacity: 0.7; font-size: 0.9em;">
      <div id="last-update">Last update: --:--:--</div>
    </div>
  `;
  updateTimestamp();
}

// -------------------- INIT & AUTO-REFRESH --------------------
async function loadAll() {
  updateCounter++;
  console.log(`[Update #${updateCounter}] Refreshing all data...`);
  
  try {
    // Check health first
    await checkHealth();
    
    // Load all data in parallel
    await Promise.all([
      loadFactoryLayout(),
      loadPredictions(),
      loadEnergyChart(),
      loadRecommendations()
    ]);
    
    updateTimestamp();
  } catch (err) {
    console.error("Error in loadAll():", err);
  }
}

// Initial load
console.log("🚀 AitherTwin Dashboard - Starting...");
loadAll();

// Auto-refresh every REFRESH_INTERVAL_MS milliseconds
setInterval(loadAll, REFRESH_INTERVAL_MS);