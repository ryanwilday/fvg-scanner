const API = "";

// ---------------------------------------------------------------------------
// Toast
// ---------------------------------------------------------------------------
function showToast(msg, type = "success") {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.className = `toast ${type}`;
  setTimeout(() => (t.className = "toast hidden"), 3000);
}

// ---------------------------------------------------------------------------
// Watchlist
// ---------------------------------------------------------------------------
async function loadWatchlist() {
  const res = await fetch(`${API}/api/watchlist`);
  const items = await res.json();
  const ul = document.getElementById("watchlist");
  ul.innerHTML = "";

  const filterSymbol = document.getElementById("filter-symbol");
  const prevVal = filterSymbol.value;
  filterSymbol.innerHTML = '<option value="">All symbols</option>';

  for (const item of items) {
    const li = document.createElement("li");
    li.className = "watchlist-item";
    li.innerHTML = `
      <div class="item-info">
        <span class="symbol">${item.symbol}</span>
        <span class="meta">${item.asset_type} &middot; ${item.timeframe}</span>
      </div>
      <button class="remove-btn" data-symbol="${item.symbol}" title="Remove">&times;</button>
    `;
    ul.appendChild(li);

    const opt = document.createElement("option");
    opt.value = item.symbol;
    opt.textContent = item.symbol;
    filterSymbol.appendChild(opt);
  }

  filterSymbol.value = prevVal;

  ul.querySelectorAll(".remove-btn").forEach((btn) => {
    btn.addEventListener("click", () => removeSymbol(btn.dataset.symbol));
  });
}

async function removeSymbol(symbol) {
  await fetch(`${API}/api/watchlist/${symbol}`, { method: "DELETE" });
  showToast(`${symbol} removed`);
  loadWatchlist();
  loadAlerts();
}

document.getElementById("add-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const symbol = document.getElementById("symbol-input").value.trim().toUpperCase();
  const asset_type = document.getElementById("type-select").value;
  const timeframe = document.getElementById("timeframe-select").value;

  const res = await fetch(`${API}/api/watchlist`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol, asset_type, timeframe }),
  });

  if (res.ok) {
    document.getElementById("symbol-input").value = "";
    showToast(`${symbol} added to watchlist`);
    loadWatchlist();
  } else {
    const err = await res.json();
    showToast(err.detail || "Error adding symbol", "error");
  }
});

// ---------------------------------------------------------------------------
// Settings (persisted to localStorage)
// ---------------------------------------------------------------------------
function getSetting(id, fallback) {
  return localStorage.getItem(`fvg_${id}`) ?? fallback;
}

function saveSetting(id, value) {
  localStorage.setItem(`fvg_${id}`, value);
}

function initSettings() {
  const tz = document.getElementById("setting-timezone");
  const ps = document.getElementById("setting-per-symbol");
  tz.value = getSetting("timezone", "America/New_York");
  ps.value = getSetting("per_symbol", "1");

  tz.addEventListener("change", () => { saveSetting("timezone", tz.value); loadAlerts(); });
  ps.addEventListener("change", () => { saveSetting("per_symbol", ps.value); loadAlerts(); });
}

// ---------------------------------------------------------------------------
// Alerts
// ---------------------------------------------------------------------------
function formatTime(iso) {
  // Append Z so JS always parses the backend UTC string as UTC
  const d = new Date(iso.endsWith("Z") ? iso : iso + "Z");
  const tz = document.getElementById("setting-timezone").value;
  return d.toLocaleString("en-US", {
    timeZone: tz,
    month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
    timeZoneName: "short",
  });
}

function applyPerSymbolLimit(alerts) {
  const limit = parseInt(document.getElementById("setting-per-symbol").value, 10) || 1;
  const counts = {};
  return alerts.filter((a) => {
    const key = `${a.symbol}_${a.timeframe}_${a.direction}`;
    counts[key] = (counts[key] || 0) + 1;
    return counts[key] <= limit;
  });
}

async function loadAlerts() {
  const symbol = document.getElementById("filter-symbol").value;
  const direction = document.getElementById("filter-direction").value;
  const showMitigated = document.getElementById("filter-mitigated").checked;

  const params = new URLSearchParams();
  if (symbol) params.set("symbol", symbol);
  if (direction) params.set("direction", direction);
  if (!showMitigated) params.set("mitigated", "false");
  params.set("limit", "500");

  const res = await fetch(`${API}/api/alerts?${params}`);
  let alerts = await res.json();
  alerts = applyPerSymbolLimit(alerts);

  const container = document.getElementById("alerts-container");
  if (!alerts.length) {
    container.innerHTML = '<p class="empty-state">No FVGs found for current filters.</p>';
    return;
  }

  container.innerHTML = alerts.map((a) => `
    <div class="alert-card ${a.direction} ${a.mitigated ? "mitigated" : ""}">
      <div>
        <div class="alert-top">
          <span class="alert-symbol">${a.symbol}</span>
          <span class="badge ${a.direction}">${a.direction}</span>
          <span class="badge tf">${a.timeframe}</span>
          ${a.mitigated ? '<span class="badge mitigated-badge">mitigated</span>' : ""}
        </div>
        <div class="alert-prices">
          Zone: <strong>$${a.gap_bottom.toFixed(4)}</strong> &mdash; <strong>$${a.gap_top.toFixed(4)}</strong>
        </div>
      </div>
      <div class="alert-time">
        <div>Candle: ${formatTime(a.candle_time)}</div>
        <div>Detected: ${formatTime(a.detected_at)}</div>
      </div>
    </div>
  `).join("");
}

// ---------------------------------------------------------------------------
// Manual scan
// ---------------------------------------------------------------------------
document.getElementById("scan-btn").addEventListener("click", async () => {
  const btn = document.getElementById("scan-btn");
  btn.disabled = true;
  btn.textContent = "Scanning...";

  const res = await fetch(`${API}/api/scan`, { method: "POST" });
  const data = await res.json();
  showToast(data.message);

  document.getElementById("last-scan").textContent =
    `Last scan: ${new Date().toLocaleTimeString()}`;

  await loadAlerts();
  btn.disabled = false;
  btn.textContent = "Scan Now";
});

// ---------------------------------------------------------------------------
// Filter listeners
// ---------------------------------------------------------------------------
["filter-symbol", "filter-direction", "filter-mitigated"].forEach((id) => {
  document.getElementById(id).addEventListener("change", loadAlerts);
});

// ---------------------------------------------------------------------------
// Auto-refresh alerts every 60s
// ---------------------------------------------------------------------------
setInterval(loadAlerts, 60_000);

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
initSettings();
loadWatchlist();
loadAlerts();
