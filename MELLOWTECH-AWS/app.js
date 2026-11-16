"use strict";

/* =========================================================
   MELLOWTECH CYBERSECURITY PLATFORM
   Frontend: HTML, CSS, JavaScript  |  Backend: Python Flask
   ========================================================= */

const APP_VERSION = "2026.10.15-protection";   // must match the server and index.html
const API_BASE_URL = "";   // same origin: the Flask server also serves this page
let csrfToken = "";
let userRole = "viewer";
let lastDevices = [], lastBlocks = [];
let isPlatform = true;   // MellowTech staff see this computer's server details; customers do not
const REFRESH_INTERVAL = 5000;
const MAX_REFRESH_INTERVAL = 30000;
const REQUEST_TIMEOUT = 4000;
const HISTORY_POINTS = 30;
const CIRC = 2 * Math.PI * 46;

let currentPage = "dashboard";
let pollTimer = null;
let consecutiveFailures = 0;
let navigationInitialized = false;
const inFlight = { system: false, network: false, events: false, devices: false, blocks: false };
const history = { cpu: [], mem: [], disk: [] };

/* -------------------- STYLES (injected, no CSS file edits needed) -------------------- */

const MT_CSS = `
.mt-panel{--ink:#0d1b2a;--well:#13263a;--line:#26405c;--text:#eaf2fb;--mute:#8fa6bf;--ok:#3ddbb0;--warn:#ffb454;--bad:#ff6b6b;
 margin:20px 0;padding:24px;border-radius:14px;background:var(--ink);color:var(--text);border:1px solid var(--line)}
.mt-panel h2{margin:0;font-size:1.2rem;font-weight:650;color:#fff}
.mt-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:20px}
.mt-meta{display:flex;flex-wrap:wrap;gap:4px 16px;margin:6px 0 0;font-size:.85rem;color:var(--mute)}
.mt-meta b{color:var(--text);font-weight:600}
.mt-chip{display:inline-flex;align-items:center;gap:7px;padding:5px 12px;border-radius:999px;font-size:.8rem;font-weight:600;color:var(--ok);border:1px solid rgba(61,219,176,.4)}
.mt-chip i{width:8px;height:8px;border-radius:50%;background:currentColor}
.mt-chip.off{color:var(--bad);border-color:rgba(255,107,107,.45)}
.mt-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}
.mt-card{padding:20px 18px 14px;border-radius:10px;background:var(--well)}
.mt-gauge{position:relative;width:150px;height:150px;margin:0 auto}
.mt-gauge svg{width:100%;height:100%;transform:rotate(-90deg)}
.mt-track,.mt-arc{fill:none;stroke-width:10}
.mt-track{stroke:rgba(143,166,191,.16)}
.mt-arc{stroke-linecap:round;transition:stroke-dashoffset 1.2s cubic-bezier(.22,1,.36,1),stroke .5s;filter:drop-shadow(0 0 5px currentColor)}
.mt-gauge-val{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center}
.mt-gauge-val b{font-size:2.3rem;line-height:1;font-weight:650;color:#fff;font-variant-numeric:tabular-nums}
.mt-gauge-val small{font-size:1rem;color:var(--mute);margin-left:1px}
.mt-gauge-val span{margin-top:5px;font-size:.85rem;color:var(--mute)}
.mt-sub{margin:10px 0 0;min-height:1.2em;text-align:center;font-size:.85rem;color:var(--mute)}
.mt-spark{display:block;width:100%;height:60px;margin-top:8px}
.mt-foot{margin:16px 0 0;font-size:.8rem;color:var(--mute)}
.mt-error{margin:10px 0 0;font-size:.88rem;color:var(--bad)}
.mt-error:empty{display:none}
.mt-net{--well:#13263a;--line:#26405c;--text:#eaf2fb;--mute:#8fa6bf;--ok:#3ddbb0;--bad:#ff6b6b;--warn:#ffb454;display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px}
.mt-net .mt-card{padding:18px}
.mt-net h3{display:flex;justify-content:space-between;align-items:center;gap:8px;margin:0 0 8px;font-size:1rem;color:#fff}
.mt-pill{padding:3px 11px;border-radius:999px;font-size:.78rem;font-weight:650}
.mt-pill.up{color:var(--ok);background:rgba(61,219,176,.13)}
.mt-pill.down{color:var(--bad);background:rgba(255,107,107,.14)}
.mt-row{display:flex;justify-content:space-between;gap:12px;padding:8px 0;border-top:1px solid var(--line);font-size:.88rem;color:var(--mute)}
.mt-row b{color:var(--text);font-weight:600;font-variant-numeric:tabular-nums}
.mt-badge{display:inline-block;padding:3px 11px;border-radius:999px;font-size:.78rem;font-weight:650}
.sev-high,.sev-critical{color:#b4232f;background:rgba(255,107,107,.18)}
.sev-medium{color:#92560a;background:rgba(255,180,84,.24)}
.sev-low{color:#0a7a5c;background:rgba(61,219,176,.2)}
.mt-card .btn-small{background:transparent;color:var(--text);border-color:var(--line)}
.mt-card .btn-small:hover{background:rgba(255,255,255,.07);border-color:var(--text)}
.mt-meter{display:grid;grid-template-columns:70px 1fr 42px;gap:10px;align-items:center;padding:7px 0;border-top:1px solid var(--line);font-size:.86rem;color:var(--mute)}
.mt-bar{height:7px;border-radius:4px;background:rgba(143,166,191,.18);overflow:hidden}
.mt-bar i{display:block;height:100%}
.mt-meter b{color:var(--text);text-align:right;font-variant-numeric:tabular-nums}
.st-new{color:#1d4f91;background:rgba(47,125,225,.14)}
.st-investigating,.st-monitoring,.st-open{color:#92560a;background:rgba(255,180,84,.24)}
.st-blocked{color:#b4232f;background:rgba(255,107,107,.18)}
.st-resolved{color:#0a7a5c;background:rgba(61,219,176,.2)}
.st-false-positive{color:#5d6c7e;background:#edf1f5}
.mt-pill.warn{color:var(--warn);background:rgba(255,180,84,.14)}
.mt-pill.na{color:var(--mute);background:rgba(143,166,191,.14)}
.mt-note{margin:10px 0 0;font-size:.82rem;color:var(--mute)}
.mt-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
#system-status.is-online{color:#12906e!important}
#system-status.is-connecting{color:#b7740f!important}
#system-status.is-offline{color:#d6303d!important}
@media (prefers-reduced-motion:reduce){.mt-arc{transition:none}}
`;

function injectStyles() {
    if (document.getElementById("mt-style")) return;
    const style = document.createElement("style");
    style.id = "mt-style";
    style.textContent = MT_CSS;
    document.head.appendChild(style);
}

/* -------------------- UTILITIES -------------------- */

function element(id) { return document.getElementById(id); }

function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, c => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[c]);
}

function setText(id, value) {
    const node = element(id);
    if (node) node.textContent = value;
}

function clamp(value) { return Math.max(0, Math.min(100, Number(value) || 0)); }

function levelColor(v) {
    return v >= 85 ? "#ff6b6b" : v >= 60 ? "#ffb454" : "#3ddbb0";
}

function formatTime(value) {
    if (!value) return "";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
}

function formatBytes(n) {
    n = Number(n);
    if (!Number.isFinite(n)) return "Not reported";
    const units = ["B", "KB", "MB", "GB", "TB"];
    let i = 0;
    while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
    return n.toFixed(i ? 1 : 0) + " " + units[i];
}

function setStatus(state) {
    const tone = { ONLINE: "", CONNECTING: "#ffb454", OFFLINE: "#ff6b6b" }[state] ?? "";

    const node = element("system-status");
    if (node) {
        node.textContent = state;
        node.classList.remove("is-online", "is-connecting", "is-offline");
        node.classList.add("is-" + state.toLowerCase());
    }

    // Keep the sidebar and the Network page's BACKEND card in step with the real connection.
    const side = element("sidebar-status");
    if (side) {
        side.textContent = "\u25CF " + (state === "ONLINE" ? "SYSTEM ONLINE"
            : state === "OFFLINE" ? "BACKEND OFFLINE" : "CONNECTING");
        side.style.color = tone;
    }

    const backend = element("backend-status");
    if (backend) {
        backend.textContent = state;
        backend.style.color = tone;
    }
}

async function fetchJSON(path) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);
    try {
        const response = await fetch(API_BASE_URL + path, {
            cache: "no-store",
            credentials: "same-origin",
            signal: controller.signal
        });
        if (response.status === 401) {
            (window.mtNeedLogin ? window.mtNeedLogin() : (window.location.href = "/login.html"));   // not signed in, or the session ended
            throw new Error("Not signed in");
        }
        if (!response.ok) throw new Error(path + " HTTP " + response.status);
        return await response.json();
    } finally {
        clearTimeout(timeout);
    }
}

function ensurePanel(id, pageId, heading) {
    let panel = element(id);
    if (panel) return panel;

    const page = element(pageId);
    if (!page) {
        console.error("MellowTech: page not found:", pageId);
        return null;
    }

    panel = document.createElement("section");
    panel.id = id;
    panel.className = "live-monitoring-panel mt-panel";

    const title = document.createElement("h2");
    title.textContent = heading;
    panel.appendChild(title);

    page.appendChild(panel);
    return panel;
}

/* -------------------- CHARTS (inline SVG) -------------------- */

function sparkline(values, color, id) {
    const w = 240, h = 60, p = 4;
    if (values.length < 2) {
        return `<svg class="mt-spark" viewBox="0 0 ${w} ${h}"></svg>`;
    }
    const step = (w - p * 2) / (values.length - 1);
    const pts = values.map((v, i) => [p + i * step, h - p - (v / 100) * (h - p * 2)]);
    const line = pts.map(([x, y], i) => (i ? "L" : "M") + x.toFixed(1) + " " + y.toFixed(1)).join(" ");
    const last = pts[pts.length - 1], first = pts[0];
    const area = `${line} L${last[0].toFixed(1)} ${h} L${first[0].toFixed(1)} ${h} Z`;

    return `<svg class="mt-spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
        <defs><linearGradient id="mt-g-${id}" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="${color}" stop-opacity=".35"/>
            <stop offset="1" stop-color="${color}" stop-opacity="0"/>
        </linearGradient></defs>
        <path d="${area}" fill="url(#mt-g-${id})"/>
        <path d="${line}" fill="none" stroke="${color}" stroke-width="2"
              stroke-linejoin="round" stroke-linecap="round"
              vector-effect="non-scaling-stroke"/>
    </svg>`;
}

function updateGauge(key, value, sub) {
    const v = clamp(value);
    const color = levelColor(v);
    const arc = element(`mt-${key}-arc`);
    if (!arc) return;

    arc.style.stroke = color;
    arc.style.color = color;
    arc.style.strokeDashoffset = (CIRC * (1 - v / 100)).toFixed(1);

    element(`mt-${key}-val`).innerHTML = `${v.toFixed(0)}<small>%</small>`;
    setText(`mt-${key}-sub`, sub);
    element(`mt-${key}-spark`).innerHTML = sparkline(history[key], color, key);
}

/* -------------------- NAVIGATION -------------------- */

function showPage(pageId) {
    const target = element(pageId);
    if (!target) {
        console.error("MellowTech navigation error: no HTML element with id:", pageId);
        return;
    }

    document.querySelectorAll(".page").forEach(page => {
        page.classList.toggle("active-page", page.id === pageId);
        page.hidden = page.id !== pageId;
    });

    document.querySelectorAll(".nav-button").forEach(button => {
        const buttonPage = button.dataset.page || button.getAttribute("data-target");
        button.classList.toggle("active", buttonPage === pageId);
        if (buttonPage === pageId) button.setAttribute("aria-current", "page");
        else button.removeAttribute("aria-current");
    });

    const changed = currentPage !== pageId;
    currentPage = pageId;
    if (changed) window.scrollTo(0, 0);   // new page starts at the top

    if (pageId === "dashboard") loadSystemInfo();
    if (pageId === "network") loadNetworkInfo();
    if (pageId === "events") loadSecurityEvents();
    if (pageId === "devices") loadDevices();
    if (pageId === "requests") loadRequests();
    if (pageId === "threats") { loadBlocks(); renderAlerts(); }
}

function initializeNavigation() {
    if (navigationInitialized) return;
    navigationInitialized = true;

    document.querySelectorAll(".nav-button").forEach(button => {
        button.removeAttribute("onclick");
        button.addEventListener("click", event => {
            event.preventDefault();
            const pageId = button.dataset.page || button.getAttribute("data-target");
            if (!pageId) {
                console.error("Navigation button has no data-page attribute:", button);
                return;
            }
            showPage(pageId);
        });
    });

    showPage("dashboard");
}

/* -------------------- SYSTEM MONITORING -------------------- */

function getSystemPanel() {
    const panel = ensurePanel("live-system-monitor", "dashboard", "Live System Monitoring");
    if (!panel || panel.dataset.built) return panel;

    const gauges = [["cpu", "CPU"], ["mem", "Memory"], ["disk", "Disk"]].map(([k, name]) => `
        <article class="mt-card">
            <div class="mt-gauge">
                <svg viewBox="0 0 120 120">
                    <circle class="mt-track" cx="60" cy="60" r="46"/>
                    <circle class="mt-arc" id="mt-${k}-arc" cx="60" cy="60" r="46"
                            stroke-dasharray="${CIRC.toFixed(1)}"
                            stroke-dashoffset="${CIRC.toFixed(1)}"/>
                </svg>
                <div class="mt-gauge-val">
                    <b id="mt-${k}-val">0<small>%</small></b><span>${name}</span>
                </div>
            </div>
            <p class="mt-sub" id="mt-${k}-sub"></p>
            <div id="mt-${k}-spark"></div>
        </article>`).join("");

    panel.innerHTML = `
        <div class="mt-head">
            <div>
                <h2>Live System Monitoring</h2>
                <p class="mt-meta" id="mt-meta"></p>
            </div>
            <span class="mt-chip" id="mt-chip"><i></i><span>Live</span></span>
        </div>
        <div class="mt-grid">${gauges}</div>
        <p class="mt-foot" id="mt-foot"></p>
        <p id="system-monitor-error" class="mt-error" role="status"></p>`;

    panel.dataset.built = "1";
    // Sit directly under the "Local System Information" panel.
    const info = element("system-hostname")?.closest(".panel");
    if (info && info !== panel) info.after(panel);
    return panel;
}

function pushHistory(key, value) {
    history[key].push(clamp(value));
    if (history[key].length > HISTORY_POINTS) history[key].shift();
}

function markSystemFieldsUnavailable() {
    ["system-hostname", "system-os", "system-processor",
     "system-memory-total", "system-disk-total", "system-last-update"]
        .forEach(id => setText(id, "Unavailable"));
}

function renderSystemInfo(data) {
    const panel = getSystemPanel();
    if (!panel) return;

    const osText = [data.operating_system, data.operating_system_version].filter(Boolean).join(" ") || "Unknown";
    const processor = data.processor || data.processor_name || data.cpu_model || data.cpu_name || "Not reported by API";

    setText("system-hostname", data.hostname || "Unknown");
    setText("system-os", osText);
    setText("system-processor", processor);
    setText("system-memory-total", Number(data.memory_total_gb).toFixed(1) + " GB");
    setText("system-disk-total", Number(data.disk_total_gb).toFixed(0) + " GB");
    setText("system-last-update", formatTime(data.timestamp) || new Date().toLocaleString());

    pushHistory("cpu", data.cpu_usage_percent);
    pushHistory("mem", data.memory_usage_percent);
    pushHistory("disk", data.disk_usage_percent);

    updateGauge("cpu", data.cpu_usage_percent, "Processor load");
    updateGauge("mem", data.memory_usage_percent, `${Number(data.memory_total_gb).toFixed(1)} GB installed`);
    updateGauge("disk", data.disk_usage_percent, `${Number(data.disk_total_gb).toFixed(0)} GB capacity`);

    element("mt-meta").innerHTML =
        `<span><b>${escapeHTML(data.hostname || "Unknown")}</b></span><span>${escapeHTML(osText)}</span>`;
    setText("mt-foot", "Last update from the server: " + (formatTime(data.timestamp) || "just now"));
    setText("system-monitor-error", "");

    const chip = element("mt-chip");
    chip.classList.remove("off");
    chip.lastElementChild.textContent = "Live";
}

async function loadSystemInfo() {
    if (!isPlatform || inFlight.system) return null;
    inFlight.system = true;

    try {
        const data = await fetchJSON("/api/system");
        const required = ["cpu_usage_percent", "memory_usage_percent", "disk_usage_percent", "memory_total_gb", "disk_total_gb"];

        for (const field of required) {
            if (!Number.isFinite(Number(data[field]))) throw new Error("Invalid API field: " + field);
        }

        renderSystemInfo(data);
        setStatus("ONLINE");
        return true;

    } catch (error) {
        console.error("System monitoring failed:", error);
        setStatus("OFFLINE");
        markSystemFieldsUnavailable();

        if (getSystemPanel()) {
            setText("system-monitor-error", "Live system data is unavailable. Start the Flask backend (python app.py) and check that it is running on port 5000.");
            const chip = element("mt-chip");
            chip.classList.add("off");
            chip.lastElementChild.textContent = "Offline";
        }
        return false;

    } finally {
        inFlight.system = false;
    }
}

/* -------------------- NETWORK MONITORING -------------------- */

function netRow(label, value) {
    return `<div class="mt-row"><span>${label}</span><b>${escapeHTML(value)}</b></div>`;
}

function netBody() {
    const panel = element("network-details");
    if (!panel) return null;

    let body = element("mt-net-body");
    if (!body) {
        panel.querySelectorAll(":scope > p").forEach(p => p.remove());
        body = document.createElement("div");
        body.id = "mt-net-body";
        panel.appendChild(body);
    }
    return body;
}

async function loadNetworkInfo() {
    if (inFlight.network) return null;
    inFlight.network = true;

    const body = netBody();
    if (!body) {
        inFlight.network = false;
        return false;
    }
    if (!isPlatform) {
        body.innerHTML = "<p>No devices are connected to your account yet. Live network data will appear here once you connect a device.</p>";
        inFlight.network = false;
        return null;
    }

    try {
        const data = await fetchJSON("/api/network");
        const interfaces = Array.isArray(data.interfaces) ? data.interfaces : [];

        const cards = interfaces.map(n => `
            <article class="mt-card">
                <h3>${escapeHTML(n.name || "Network interface")}
                    <span class="mt-pill ${n.is_up ? "up" : "down"}">${n.is_up ? "Up" : "Down"}</span></h3>
                ${netRow("IPv4 address", n.ipv4 || "Not reported")}
                ${netRow("Link speed", (n.speed_mbps || n.speed) ? (n.speed_mbps || n.speed) + " Mbps" : "Not reported")}
                ${netRow("Data sent", formatBytes(n.bytes_sent))}
                ${netRow("Data received", formatBytes(n.bytes_received))}
            </article>`).join("");

        body.innerHTML =
            `<p><strong>${escapeHTML(data.hostname || "Unknown")}</strong>, ` +
            `${interfaces.length} interface${interfaces.length === 1 ? "" : "s"}</p>` +
            `<div class="mt-net">${cards || "<p>The API returned no interfaces. Check the backend response format.</p>"}</div>`;
        return true;

    } catch (error) {
        console.error("Network monitoring failed:", error);
        body.innerHTML =
            '<p style="color:#d6303d">Network data is unavailable. Check that the Flask /api/network endpoint is running.</p>';
        return false;

    } finally {
        inFlight.network = false;
    }
}

/* -------------------- SECURITY EVENTS -------------------- */

let lastEvents = [];

function updateSeverityStats(events) {
    const count = level => events.filter(e => String(e.severity).toLowerCase() === level).length;
    const counts = { high: count("high"), medium: count("medium"), low: count("low") };
    const total = events.length || 1;

    setText("event-count", events.length);
    setText("high-threat-count", counts.high);
    setText("severity-high", counts.high);
    setText("severity-medium", counts.medium);
    setText("severity-low", counts.low);

    Object.entries(counts).forEach(([level, n]) => {
        const fill = document.querySelector(".distribution-fill." + level + "-fill");
        if (!fill) return;
        const pct = Math.round((n / total) * 100);
        fill.style.width = pct + "%";
        const label = fill.closest(".distribution-item")
            ?.querySelector(".distribution-label span:last-child");
        if (label) label.textContent = pct + "%";
    });
}

function renderEvents() {
    const table = element("events-table-body");
    if (!table) return;

    const filter = (element("severity-filter")?.value || "all").toLowerCase();
    const rows = lastEvents.filter(e =>
        filter === "all" || String(e.severity).toLowerCase() === filter);

    table.replaceChildren();

    if (rows.length === 0) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 6;
        cell.textContent = lastEvents.length
            ? "No events match this filter."
            : "No security events recorded.";
        row.appendChild(cell);
        table.appendChild(row);
        return;
    }

    rows.forEach(item => {
        const row = document.createElement("tr");
        const values = [item.id, item.type, item.device, item.severity,
                        item.status, formatTime(item.time || item.timestamp || item.created_at)];

        values.forEach((value, index) => {
            const cell = document.createElement("td");

            if (index === 3 && value) {
                const badge = document.createElement("span");
                badge.className = "mt-badge sev-" + String(value).toLowerCase();
                badge.textContent = value;
                cell.appendChild(badge);
            } else {
                cell.textContent = value ?? "";
            }
            row.appendChild(cell);
        });

        table.appendChild(row);
    });
}

async function loadSecurityEvents() {
    if (inFlight.events) return null;
    inFlight.events = true;

    try {
        const events = await fetchJSON("/api/events");
        if (!Array.isArray(events)) throw new Error("Events API did not return a list");

        lastEvents = events;
        updateSeverityStats(events);
        renderEvents();
        renderAlerts();
        if (!isPlatform) setStatus("ONLINE");
        return true;

    } catch (error) {
        console.error("Security events unavailable:", error);
        if (!isPlatform) setStatus("OFFLINE");
        return false;

    } finally {
        inFlight.events = false;
    }
}

function refreshEvents() { loadSecurityEvents(); }

/* -------------------- ACTIONS -------------------- */

function timeNow() { return new Date().toLocaleTimeString(); }

async function networkScan() {
    setText("network-result", "Refreshing network telemetry...");
    const ok = await loadNetworkInfo();
    setText("network-result",
        ok === true ? "Network telemetry refreshed at " + timeNow() + "." :
        ok === false ? "Could not reach the backend. Check that Flask is running on port 5000." :
        "A refresh is already running.");
}

async function runScan() {
    setText("scan-result", "Refreshing...");
    const [system] = await Promise.all([loadSystemInfo(), loadSecurityEvents()]);
    setText("scan-result", system === false
        ? "Could not reach the backend. Check that Flask is running on port 5000."
        : "Refreshed system telemetry and security events at " + timeNow() +
          ". No vulnerability scan was performed.");
}

function analyseThreat() {
    setText("threat-result",
        "Automated threat detection is not yet implemented. No security scan was performed.");
}

function showDevice(name) {
    const box = element("device-details");
    if (!box) return;

    const devices = {
        "Admin-PC": ["Windows", "Online"],
        "Server-01": ["Linux server", "Online"],
        "Router-01": ["Network router", "Online"],
        "Workstation-04": ["Windows", "Monitoring"]
    };
    const info = devices[name];

    box.innerHTML = info
        ? `<strong>${escapeHTML(name)}</strong>` +
          `<p>Type: ${escapeHTML(info[0])}<br>Status: ${escapeHTML(info[1])}</p>` +
          `<p>Demonstration device. Live telemetry is only collected for the local computer.</p>`
        : "No details available for " + escapeHTML(name) + ".";
}

/** A customer's company has no connected devices yet, so show that honestly instead of our own server's data. */
function applyCustomerView() {
    setText("device-count", "0");
    const info = element("system-hostname")?.closest(".panel");
    if (info) info.hidden = true;
}

async function loadSession() {
    try {
        const data = await fetchJSON("/api/auth/me");
        csrfToken = data.csrf;
        isPlatform = data.user.is_platform;
        userRole = data.user.role;
        document.querySelectorAll("[data-admin-only]").forEach(node => { node.hidden = userRole !== "admin"; });
        isPlatformAdmin = isPlatform && userRole === "admin";
        document.querySelectorAll("[data-platform-admin]").forEach(node => { node.hidden = !isPlatformAdmin; });
        setText("logged-user", (data.user.name || data.user.email) + (data.user.role === "admin" ? " (admin)" : "") +
                (isPlatform ? "" : ", " + data.user.org));
        if (!isPlatform) applyCustomerView();
        return true;
    } catch (error) {
        return false;
    }
}

async function logout() {
    try {
        await fetch(API_BASE_URL + "/api/auth/logout", {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
            body: "{}"
        });
    } catch (error) {
        // leave anyway; the server session expires by itself
    }
    (window.mtNeedLogin ? window.mtNeedLogin() : (window.location.href = "/login.html"));
}

/* -------------------- ACCOUNT REQUESTS (MellowTech administrators) -------------------- */

let isPlatformAdmin = false;

function renderRequests(data) {
    const badge = element("request-badge");
    if (badge) { badge.textContent = data.pending; badge.hidden = data.pending === 0; }
    const pending = data.requests.filter(r => r.status === "pending");
    const decided = data.requests.filter(r => r.status !== "pending");

    const pendingBody = element("requests-pending");
    if (pendingBody) {
        pendingBody.innerHTML = pending.length ? pending.map(r => `<tr>
            <td><b>${escapeHTML(r.company)}</b></td><td>${escapeHTML(r.name)}</td><td>${escapeHTML(r.email)}</td>
            <td>${escapeHTML(formatTime(r.requested_at))}</td>
            <td><span class="mt-badge ${r.email_confirmed ? "st-resolved" : "st-investigating"}">${r.email_confirmed ? "Yes" : "Not yet"}</span></td>
            <td><div class="actions">
                <button type="button" class="btn-small" data-action="approve-request" data-id="${r.id}" data-name="${escapeHTML(r.name)}" ${r.email_confirmed ? "" : "disabled title=\"They must confirm their email first\""}>Approve</button>
                <button type="button" class="btn-small btn-danger" data-action="reject-request" data-id="${r.id}" data-name="${escapeHTML(r.name)}">Reject</button>
            </div></td></tr>`).join("")
            : '<tr><td colspan="6">No requests are waiting. New ones appear here after the person confirms their email.</td></tr>';
    }
    const decidedBody = element("requests-decided");
    if (decidedBody) {
        decidedBody.innerHTML = decided.length ? decided.map(r => `<tr>
            <td>${escapeHTML(r.company)}</td><td>${escapeHTML(r.name)}</td><td>${escapeHTML(r.email)}</td>
            <td><span class="mt-badge ${r.status === "approved" ? "st-resolved" : "st-blocked"}">${r.status === "approved" ? "Approved" : "Rejected"}</span></td>
            <td>${escapeHTML(formatTime(r.decided_at))}</td><td>${escapeHTML(r.note || "")}</td></tr>`).join("")
            : '<tr><td colspan="6">No decisions yet.</td></tr>';
    }
}

async function loadRequests() {
    if (!isPlatformAdmin) return null;
    try {
        renderRequests(await fetchJSON("/api/requests"));
        return true;
    } catch (error) {
        console.error("Account requests unavailable:", error);
        return false;
    }
}

/* -------------------- DEVICES, ALERTS AND BLOCKING -------------------- */

const OPEN_STATUSES = ["New", "Investigating", "Blocked", "Open", "Monitoring"];   // "Blocked" stays open until someone resolves it
const isAdmin = () => userRole === "admin";

async function apiPost(path, body) {
    const response = await fetch(API_BASE_URL + path, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
        body: JSON.stringify(body || {})
    });
    if (response.status === 401) {
        (window.mtNeedLogin ? window.mtNeedLogin() : (window.location.href = "/login.html"));
        throw new Error("Not signed in");
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || "Request failed (" + response.status + ")");
    return data;
}

function meter(label, value) {
    const v = clamp(value);
    return `<div class="mt-meter"><span>${label}</span><div class="mt-bar"><i style="width:${v}%;background:${levelColor(v)}"></i></div><b>${v.toFixed(0)}%</b></div>`;
}

const ACTION_LABELS = { scan: "Virus scan", update_protection: "Protection update", isolate: "Isolate", release: "Release",
                        usb_block: "Block USB storage", usb_allow: "Allow USB storage" };
const COMMAND_STATUS = { pending: "waiting for the laptop", sent: "sent to the laptop", done: "done", failed: "failed",
                         cancelled: "cancelled (the laptop was offline)" };
const ON_OFF = { on: ["up", "On"], off: ["down", "Off"], partial: ["warn", "Partly on"], audit: ["warn", "Test mode"],
                 unavailable: ["na", "Not available"], unknown: ["na", "Unknown"] };

function pill(kind, text) { return `<span class="mt-pill ${kind}">${escapeHTML(text)}</span>`; }
function pRow(label, html) { return `<div class="mt-row"><span>${label}</span><b>${html}</b></div>`; }
function plural(n, word) { return n + " " + word + (n === 1 ? "" : "s"); }
function stateRow(label, value, map) {
    const [kind, text] = map[value] || ["na", "Unknown"];
    return pRow(label, pill(kind, text));
}

function postureRows(d) {
    const p = d.posture;
    if (!p) {
        return `<p class="mt-note">Waiting for the first security check${d.version && d.version < "0.2" ? ". This laptop runs an older agent: install the newer one to see its security state" : ""}.</p>`;
    }
    if (p.platform) return '<p class="mt-note">Security checks are not available for this kind of computer yet.</p>';

    const df = p.defender || {};
    const av = df.state === "on" ? pill("up", "Microsoft Defender on")
        : df.state === "other" ? pill("up", "Other antivirus" + (df.other_av ? ": " + df.other_av : ""))
        : df.state === "off" ? pill("down", "Off") : pill("na", "Unknown");
    const age = df.definitions_age_days;
    const defs = age == null ? "" : " " + pill(age >= 7 ? "warn" : "up", "definitions " + plural(age, "day") + " old");
    const scan = df.quick_scan_age_days;
    const threats = df.threats_active > 0 ? pill("down", df.threats_active + " active")
        : df.threats_total > 0 ? pill("warn", plural(df.threats_total, "past threat")) : pill("up", "None found");

    let updates = pill("na", "Unknown");
    const up = p.updates;
    if (up) {
        const needs = (up.last_update_days != null && up.last_update_days > 45) || (up.pending || 0) > 0 || up.reboot_required;
        const bits = [];
        if (up.last_update_days != null) bits.push("last installed " + plural(up.last_update_days, "day") + " ago");
        if (up.pending != null) bits.push(plural(up.pending, "update") + " waiting");
        if (up.reboot_required) bits.push("restart needed");
        updates = pill(needs ? "warn" : "up", needs ? "Needs attention" : "Up to date") + (bits.length ? " " + escapeHTML(bits.join(", ")) : "");
    }
    const signin = { ok: ["up", "Watching"], needs_admin: ["warn", "Needs administrator rights"], unavailable: ["na", "Unavailable"] };
    const usb = { allowed: ["na", "Allowed"], blocked: ["up", "Blocked"], unknown: ["na", "Unknown"] };

    return pRow("Virus protection", av + defs) +
        pRow("Last quick scan", escapeHTML(scan == null ? "Never" : plural(scan, "day") + " ago")) +
        pRow("Threats found", threats) +
        stateRow("Firewall", p.firewall, ON_OFF) + stateRow("Disk encryption", p.disk_encryption, ON_OFF) +
        stateRow("Web protection", p.web_protection, ON_OFF) + pRow(p.os_family && p.os_family !== "windows" ? "System updates" : "Windows updates", updates) +
        stateRow("USB storage", p.usb_storage, usb) + stateRow("Sign-in monitoring", p.signin_monitoring, signin);
}

function lastCommandNote(d) {
    const c = d.last_command;
    if (!c) return "";
    const detail = c.status === "failed" && c.result ? ": " + c.result.slice(0, 160) : "";
    return `<p class="mt-note">Last action: ${escapeHTML(ACTION_LABELS[c.action] || c.action)}, ${escapeHTML(COMMAND_STATUS[c.status] || c.status)}${escapeHTML(detail)} (${escapeHTML(formatTime(c.at))})</p>`;
}

function deviceActions(d) {
    if (!isAdmin()) return "";
    const p = d.posture, name = escapeHTML(d.name);
    const button = (command, label, danger) =>
        `<button type="button" class="btn-small${danger ? " btn-danger" : ""}" data-action="device-command" data-id="${d.id}" data-command="${command}" data-name="${name}">${label}</button>`;
    let buttons = "";
    if (d.online && p && !p.platform) {
        buttons += button("scan", "Run virus scan") + button("update_protection", "Update protection") +
            (p.isolated ? button("release", "Release laptop") : button("isolate", "Isolate", true)) +
            (p.os_family === "macos" ? "" : p.usb_storage === "blocked" ? button("usb_allow", "Allow USB storage") : button("usb_block", "Block USB storage"));
    }
    buttons += `<button type="button" class="btn-small" data-action="remove-device" data-id="${d.id}">Remove</button>`;
    return `<div class="mt-actions">${buttons}</div>` + (d.online ? "" : '<p class="mt-note">Actions are available when the laptop is online.</p>');
}

function renderDevices() {
    const grid = element("devices-grid");
    if (!grid) return;
    if (!lastDevices.length) {
        grid.innerHTML = '<p class="empty">No laptops are connected yet. Use "Connect a laptop" to add the first one.</p>';
        return;
    }
    grid.innerHTML = lastDevices.map(d => `
        <article class="mt-card">
            <h3>${escapeHTML(d.name)}
                <span>${d.posture && d.posture.isolated ? pill("down", "Isolated") + " " : ""}<span class="mt-pill ${d.online ? "up" : "down"}">${d.online ? "Online" : "Offline"}</span></span></h3>
            ${netRow("Operating system", d.os || "Unknown")}
            ${netRow("IP address", d.ip || "Unknown")}
            ${meter("CPU", d.cpu)}${meter("Memory", d.memory)}${meter("Disk", d.disk)}
            ${postureRows(d)}
            ${netRow("Last seen", formatTime(d.last_seen))}
            ${lastCommandNote(d)}${deviceActions(d)}
        </article>`).join("");
}

async function loadDevices() {
    if (inFlight.devices) return null;
    inFlight.devices = true;
    try {
        lastDevices = await fetchJSON("/api/devices");
        setText("device-count", lastDevices.length);
        setText("threat-devices", lastDevices.length);
        renderDevices();
        return true;
    } catch (error) {
        console.error("Devices unavailable:", error);
        return false;
    } finally {
        inFlight.devices = false;
    }
}

async function connectLaptop() {
    const data = await apiPost("/api/devices/enroll-key");
    const box = element("enroll-box");
    box.hidden = false;
    const server = location.origin, key = data.key;
    const pyCommand = `python mellowtech_agent.py install --server ${server} --key ${key}`;
    const unixCommand = `curl -fsSL ${server}/download/mellowtech_agent.py -o mellowtech_agent.py && sudo python3 mellowtech_agent.py install --server ${server} --key ${key}`;
    const commands = {
        windows: `MellowTechAgent.exe install --server ${server} --key ${key}`,
        mac: unixCommand,
        linux: unixCommand
    };
    let command = commands.windows;
    const sameComputerNote = ["127.0.0.1", "localhost"].includes(location.hostname)
        ? `<p>This page is open on <b>this</b> computer. If the laptop is a <b>different</b> computer, open MellowTech on that laptop (or replace <code>${escapeHTML(location.hostname)}</code> in the line with this computer's network address).</p>` : "";
    box.innerHTML = `<h3>Connect a laptop</h3>
        <p class="cl-intro">Pick the kind of computer, then follow the three steps. It takes about two minutes.</p>
        <div class="cl-tabs" role="tablist">
            <button type="button" class="cl-tab on" data-os="windows">Windows</button>
            <button type="button" class="cl-tab" data-os="mac">Mac</button>
            <button type="button" class="cl-tab" data-os="linux">Linux</button>
        </div>
        <ol class="cl-steps">
            <li><div><b>Download the program.</b> <span id="cl-s1"></span></div></li>
            <li><div><b id="cl-s2t"></b> <span id="cl-s2"></span></div></li>
            <li><div><b>Paste this line and press Enter.</b> <span id="cl-s3"></span>
                <pre class="code-box" id="cl-command"></pre>
                <button type="button" class="btn-small" id="cl-copy">Copy the line</button></div></li>
        </ol>
        <p class="cl-done"><b>That is all.</b> Your laptop appears in the list below within a minute. The line works once and stops working in ${data.expires_minutes} minutes. If it expires, click &ldquo;Connect a laptop&rdquo; again for a new one.</p>
        <details class="cl-more"><summary>No download link, or a different computer?</summary>
            ${sameComputerNote}
            <p><b>Windows without the download:</b> install Python 3, run <code>pip install psutil</code>,
            download <a href="${location.origin}/download/mellowtech_agent.py">mellowtech_agent.py</a> and run this as Administrator:</p>
            <pre class="code-box">${escapeHTML(pyCommand)}</pre>
        </details>
        <div class="cl-help">
            <h4>Stuck? Tell us and we will help</h4>
            <p>If the download, the line or the list did not work, write to us here. We get your message straight away and reply to your email.</p>
            <label>What went wrong?
                <select id="cl-topic">
                    <option>I cannot download the program</option>
                    <option>My company uses a different system</option>
                    <option>The line gave an error</option>
                    <option>The laptop does not appear in the list</option>
                    <option>Something else</option>
                </select></label>
            <label>Tell us what you see
                <textarea id="cl-message" rows="3" maxlength="2000" placeholder="For example: the screen says ..."></textarea></label>
            <button type="button" class="btn-small" id="cl-send">Send to MellowTech</button>
            <p class="cl-status" id="cl-status" role="status"></p>
        </div>`;

    const guide = {
        windows: {
            s1: `On the laptop you want to protect, click <a class="cl-download" href="${server}/download/MellowTechAgent.exe">Download MellowTechAgent</a>`,
            s2t: "Open Terminal as Administrator.",
            s2: "Right-click the Windows Start button and choose <b>Terminal (Admin)</b> (or <b>Windows PowerShell (Admin)</b>). Click <b>Yes</b> if Windows asks. Then go to the folder you downloaded to, for example <code>cd $HOME\\Downloads</code>.",
            s3: ""
        },
        mac: {
            s1: "Nothing to download by hand. The line in step 3 downloads it for you. Python 3 comes with recent Macs (if a Mac asks to install developer tools, click Install).",
            s2t: "Open Terminal.",
            s2: "Press <b>Command + Space</b>, type <b>Terminal</b> and press Enter.",
            s3: "It asks for your Mac password. Typing shows nothing, that is normal."
        },
        linux: {
            s1: "Nothing to download by hand. The line in step 3 downloads it for you. It needs Python 3 and curl (most Linux computers have both).",
            s2t: "Open a terminal.",
            s2: "Press <b>Ctrl + Alt + T</b>, or search for <b>Terminal</b> in your apps.",
            s3: "It asks for your password. Typing shows nothing, that is normal."
        }
    };
    function showSystem(name) {
        command = commands[name];
        box.querySelectorAll(".cl-tab").forEach(b => b.classList.toggle("on", b.dataset.os === name));
        element("cl-s1").innerHTML = guide[name].s1;
        element("cl-s2t").textContent = guide[name].s2t;
        element("cl-s2").innerHTML = guide[name].s2;
        element("cl-s3").textContent = guide[name].s3;
        element("cl-command").textContent = command;
        element("cl-copy").textContent = "Copy the line";
    }
    box.querySelectorAll(".cl-tab").forEach(b => b.addEventListener("click", () => showSystem(b.dataset.os)));
    const detected = /Mac/i.test(navigator.platform || navigator.userAgent) && !/iPhone|iPad/i.test(navigator.userAgent) ? "mac"
        : /Linux/i.test(navigator.platform || "") && !/Android/i.test(navigator.userAgent) ? "linux" : "windows";
    showSystem(detected);

    const copyButton = element("cl-copy");
    copyButton.addEventListener("click", async () => {
        try { await navigator.clipboard.writeText(command); copyButton.textContent = "Copied"; }
        catch (error) { copyButton.textContent = "Select the line above and press Ctrl+C"; }
    });

    const sendButton = element("cl-send");
    sendButton.addEventListener("click", async () => {
        const status = element("cl-status");
        const text = element("cl-message").value.trim();
        if (text.length < 5) { status.textContent = "Please tell us what you see, even in a few words."; status.className = "cl-status err"; return; }
        sendButton.disabled = true;
        status.textContent = "Sending...";
        status.className = "cl-status";
        try {
            const result = await apiPost("/api/support/message", {
                topic: element("cl-topic").value,
                message: text + "\n\n(Sent from Connect a laptop. Browser: " + navigator.userAgent.slice(0, 140) + ")"
            });
            element("cl-message").value = "";
            status.textContent = "Sent. Thank you. We will reply to " + result.email + ".";
            status.className = "cl-status ok";
        } catch (error) {
            status.textContent = error.message;
            status.className = "cl-status err";
        }
        sendButton.disabled = false;
    });
}

function renderAlerts() {
    const open = lastEvents.filter(e => OPEN_STATUSES.includes(e.status));
    setText("threat-open", open.length);
    setText("threat-high", open.filter(e => String(e.severity).toLowerCase() === "high").length);

    const body = element("alerts-body");
    if (!body) return;
    const filter = element("alert-filter")?.value || "open";
    const rows = lastEvents.filter(e => filter === "all" || (filter === "open") === OPEN_STATUSES.includes(e.status));

    if (!rows.length) {
        body.innerHTML = `<tr><td colspan="7">${lastEvents.length ? "Nothing in this view." : "No alerts yet. Alerts from your connected laptops appear here."}</td></tr>`;
        return;
    }
    body.innerHTML = rows.map(e => {
        const status = String(e.status || "");
        const done = status === "Resolved" || status === "False positive";
        const key = e.row_key;
        const buttons = !isAdmin() ? "" : `<div class="actions">
            ${e.source_ip && status !== "Blocked" && !done ? `<button type="button" class="btn-small btn-danger" data-action="block-ip" data-ip="${escapeHTML(e.source_ip)}" data-key="${key}" data-reason="${escapeHTML(e.type)}">Block IP</button>` : ""}
            ${status === "New" ? `<button type="button" class="btn-small" data-action="alert-status" data-key="${key}" data-status="Investigating">Investigate</button>` : ""}
            ${done ? "" : `<button type="button" class="btn-small" data-action="alert-status" data-key="${key}" data-status="Resolved">Resolve</button>
            <button type="button" class="btn-small" data-action="alert-status" data-key="${key}" data-status="False positive">False alarm</button>`}
        </div>`;
        return `<tr>
            <td><span class="mt-badge sev-${String(e.severity).toLowerCase()}">${escapeHTML(e.severity)}</span></td>
            <td>${escapeHTML(formatTime(e.timestamp))}</td><td>${escapeHTML(e.device)}</td>
            <td>${escapeHTML(e.source_ip || "")}</td><td>${escapeHTML(e.type)}</td>
            <td><span class="mt-badge st-${status.toLowerCase().replace(/\s+/g, "-")}">${escapeHTML(status)}</span></td>
            <td>${buttons}</td></tr>`;
    }).join("");
}

function renderBlocks() {
    setText("threat-blocked", lastBlocks.filter(b => b.status === "active").length);
    const body = element("blocks-body");
    if (!body) return;
    if (!lastBlocks.length) {
        body.innerHTML = '<tr><td colspan="7">No addresses are blocked.</td></tr>';
        return;
    }
    body.innerHTML = lastBlocks.map(b => {
        const active = b.status === "active";
        const label = active ? "Blocked" : b.status.charAt(0).toUpperCase() + b.status.slice(1);
        const applied = active ? `${b.enforced} of ${b.total} laptop${b.total === 1 ? "" : "s"}${b.failed ? ", " + b.failed + " failed" : ""}` : "";
        return `<tr><td><b>${escapeHTML(b.ip)}</b></td><td>${escapeHTML(b.reason || "")}</td>
            <td>${escapeHTML(formatTime(b.created_at))}</td><td>${active ? escapeHTML(formatTime(b.expires_at)) : ""}</td>
            <td>${escapeHTML(applied)}</td>
            <td><span class="mt-badge ${active ? "st-blocked" : "st-resolved"}">${escapeHTML(label)}</span></td>
            <td>${isAdmin() && active ? `<button type="button" class="btn-small" data-action="unblock" data-id="${b.id}" data-ip="${escapeHTML(b.ip)}">Unblock</button>` : ""}</td></tr>`;
    }).join("");
}

async function loadBlocks() {
    if (inFlight.blocks) return null;
    inFlight.blocks = true;
    try {
        lastBlocks = await fetchJSON("/api/blocks");
        renderBlocks();
        return true;
    } catch (error) {
        console.error("Blocks unavailable:", error);
        return false;
    } finally {
        inFlight.blocks = false;
    }
}

async function blockIp(ip, reason, hours, eventKey) {
    if (!ip) throw new Error("Type the IP address you want to block.");
    const n = lastDevices.length;
    const where = n ? `on all ${n} connected laptop${n === 1 ? "" : "s"}` : "(no laptops are connected yet)";
    if (!window.confirm(`Block ${ip} ${where} for ${hours} hour${hours === 1 ? "" : "s"}?\n\nThose laptops will stop talking to this address. You can undo it at any time.`)) return;
    const result = await apiPost("/api/blocks", { ip: ip, reason: reason, hours: hours, event_key: eventKey });
    setText("threat-result", `Block sent to ${result.devices} laptop${result.devices === 1 ? "" : "s"}. It takes effect within about 15 seconds.`);
    if (element("block-ip")) element("block-ip").value = "";
    await Promise.all([loadSecurityEvents(), loadBlocks()]);
}

async function handleActionClick(event) {
    const button = event.target.closest("[data-action]");
    if (!button || button.disabled) return;
    const d = button.dataset;
    button.disabled = true;
    try {
        if (d.action === "connect-laptop") {
            await connectLaptop();
        } else if (d.action === "remove-device") {
            if (window.confirm("Remove this laptop? It stops reporting and must be connected again with a new key.")) {
                await apiPost(`/api/devices/${d.id}/remove`);
                await loadDevices();
            }
        } else if (d.action === "device-command") {
            const asks = {
                scan: `Start a quick virus scan on ${d.name}? It uses Microsoft Defender and may slow the laptop for a few minutes.`,
                update_protection: `Ask ${d.name} to update its virus definitions now?`,
                release: `Release ${d.name}? Its normal network access will return.`,
                usb_block: `Block USB storage on ${d.name}? USB drives plugged in from now on will not work. Keyboards and mice are not affected.`,
                usb_allow: `Allow USB storage on ${d.name} again?`
            };
            let minutes;
            if (d.command === "isolate") {
                const answer = window.prompt(`Isolate ${d.name}?\n\nIt will lose ALL network access except to MellowTech. It lifts by itself after the time you choose (5 to 480 minutes), or sooner if you press Release.\n\nHow many minutes?`, "60");
                if (answer === null) return;
                minutes = Number(answer);
            } else if (!window.confirm(asks[d.command])) {
                return;
            }
            await apiPost(`/api/devices/${d.id}/command`, { action: d.command, minutes: minutes });
            setText("threat-result", "");
            await loadDevices();
        } else if (d.action === "alert-status") {
            await apiPost(`/api/alerts/${d.key}/status`, { status: d.status });
            await loadSecurityEvents();
        } else if (d.action === "block-ip") {
            await blockIp(d.ip, d.reason, 24, d.key);
        } else if (d.action === "block-form") {
            await blockIp(element("block-ip").value.trim(), element("block-reason").value.trim(), Number(element("block-hours").value), null);
        } else if (d.action === "unblock") {
            if (window.confirm(`Unblock ${d.ip}? Laptops will be allowed to talk to it again.`)) {
                await apiPost(`/api/blocks/${d.id}/remove`);
                setText("threat-result", `${d.ip} unblocked. It takes effect within about 15 seconds.`);
                await Promise.all([loadBlocks(), loadSecurityEvents()]);
            }
        } else if (d.action === "approve-request") {
            if (window.confirm(`Approve ${d.name}? They will be able to sign in straight away and we will email them.`)) {
                await apiPost(`/api/requests/${d.id}/approve`);
                setText("request-result", `${d.name} approved. They have been emailed.`);
                await loadRequests();
            }
        } else if (d.action === "reject-request") {
            const note = window.prompt(`Reject ${d.name}?\n\nOptional reason (included in the email). Press Cancel to keep the request.`, "");
            if (note !== null) {
                await apiPost(`/api/requests/${d.id}/reject`, { note: note });
                setText("request-result", `${d.name} rejected. They have been emailed.`);
                await loadRequests();
            }
        } else if (d.action === "test-alert") {
            await apiPost("/api/events", {
                type: "Test alert: repeated failed logins", device: lastDevices[0]?.name || "Test device",
                severity: "High", status: "New", source_ip: "203.0.113.50",
                description: "Test alert created from the dashboard."
            });
            setText("threat-result", "Test alert created.");
            await loadSecurityEvents();
        }
    } catch (error) {
        window.alert(error.message);
    } finally {
        button.disabled = false;
    }
}

/* -------------------- POLLING -------------------- */

function schedulePoll(delay) {
    clearTimeout(pollTimer);
    pollTimer = setTimeout(pollCycle, delay);
}

async function pollCycle() {
    if (document.hidden) {
        schedulePoll(REFRESH_INTERVAL);
        return;
    }

    const tasks = [loadSystemInfo(), loadSecurityEvents(), loadDevices()];
    if (currentPage === "network") tasks.push(loadNetworkInfo());
    if (currentPage === "threats") tasks.push(loadBlocks());
    if (isPlatformAdmin) tasks.push(loadRequests());

    const results = await Promise.all(tasks);

    if (results[0] === false) consecutiveFailures = Math.min(consecutiveFailures + 1, 4);
    else if (results[0] === true) consecutiveFailures = 0;

    schedulePoll(Math.min(REFRESH_INTERVAL * Math.pow(2, consecutiveFailures), MAX_REFRESH_INTERVAL));
}

document.addEventListener("visibilitychange", () => {
    if (!document.hidden) schedulePoll(0);
});

/* -------------------- SELF-CHECKS -------------------- */

function showBanner(message) {
    let box = element("mt-banners");
    if (!box) {
        box = document.createElement("div");
        box.id = "mt-banners";
        box.setAttribute("role", "alert");
        box.style.cssText =
            "position:fixed;left:0;right:0;top:0;z-index:1000;display:flex;flex-direction:column;";
        document.body.appendChild(box);
    }

    const bar = document.createElement("div");
    bar.style.cssText =
        "padding:12px 16px;background:#b4232f;color:#fff;font:600 14px/1.4 system-ui,sans-serif;" +
        "display:flex;gap:12px;align-items:center;justify-content:space-between;" +
        "border-bottom:1px solid rgba(255,255,255,.3);";

    const text = document.createElement("span");
    text.textContent = message;

    const close = document.createElement("button");
    close.type = "button";
    close.textContent = "Dismiss";
    close.style.cssText =
        "flex:none;padding:6px 12px;border:1px solid #fff;border-radius:6px;" +
        "background:transparent;color:#fff;font:inherit;cursor:pointer;";
    close.addEventListener("click", () => bar.remove());

    bar.append(text, close);
    box.appendChild(bar);
}

/** Says so on screen if something keeps refreshing this page (counted per tab, 30 s). */
function checkForReloadLoop() {
    try {
        const now = Date.now();
        const loads = JSON.parse(sessionStorage.getItem("mt-loads") || "[]")
            .filter(t => now - t < 30000);
        loads.push(now);
        sessionStorage.setItem("mt-loads", JSON.stringify(loads));

        if (loads.length < 5) return;

        const entry = performance.getEntriesByType("navigation")[0];
        const type = entry ? entry.type : "unknown";
        console.warn("MellowTech: page loaded " + loads.length + " times in 30 seconds (" + type + ").");

        showBanner(
            "This page has reloaded " + loads.length + " times in 30 seconds (last load: " + type + "). " +
            (window.__mtLiveReloadBlocked
                ? "Live Server's reload signal was blocked, so something else is refreshing it. " +
                  "Press F12, open the Network tab, tick Preserve log, and send me what appears just before a reload."
                : "Something is refreshing it, most likely a file-watcher. " +
                  "Close Live Server and open the site from start.bat at http://127.0.0.1:5000/")
        );
    } catch (error) {
        // sessionStorage can be unavailable; this check is optional.
    }
}

/** Shows the version, and says so if the server, index.html and app.js are not from the same download. */
async function checkVersions() {
    try {
        const status = await (await fetch(API_BASE_URL + "/api/status", { cache: "no-store" })).json();
        const page = document.querySelector('meta[name="mellowtech-version"]')?.content || "missing";
        setText("app-version", "Version " + (status.version || "unknown"));
        if (status.version !== APP_VERSION || page !== APP_VERSION) {
            showBanner("Some MellowTech files are out of date. Server: " + (status.version || "old") +
                       ", app.js: " + APP_VERSION + ", index.html: " + page +
                       ". Copy ALL files from the newest MellowTech.zip into the folder you start from, close any old server window, then run start.bat again.");
        }
    } catch (error) {
        // the other self-checks already report an unreachable server
    }
}

/** Says so on screen if style.css is missing, empty or not applied. */
async function checkStylesheet() {
    const sidebar = document.querySelector(".sidebar");
    if (!sidebar || getComputedStyle(sidebar).position !== "static") return;

    let detail;
    try {
        const response = await fetch("style.css", { cache: "no-store" });
        const css = response.ok ? await response.text() : "";
        detail = !response.ok
            ? "style.css returned HTTP " + response.status + " (not found next to index.html)."
            : css.trim().length < 200
                ? "style.css is empty or nearly empty."
                : "style.css was found but is not being applied.";
    } catch (error) {
        detail = "style.css could not be fetched.";
    }

    showBanner(
        "The page styling is missing. " + detail +
        " Make sure the file is named exactly style.css and sits in the same folder as index.html."
    );
}

/* -------------------- STARTUP -------------------- */

document.addEventListener("DOMContentLoaded", () => {
    checkForReloadLoop();
    checkStylesheet();
    checkVersions();
    injectStyles();
    element("severity-filter")?.addEventListener("change", renderEvents);
    element("alert-filter")?.addEventListener("change", renderAlerts);
    document.addEventListener("click", handleActionClick);
    setStatus("CONNECTING");
    loadSession().then(ok => {
        if (!ok) return;
        initializeNavigation();
        schedulePoll(0);
    });
});