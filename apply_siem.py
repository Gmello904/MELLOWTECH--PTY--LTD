#!/usr/bin/env python3
"""
apply_siem.py  -  MellowSecure SIEM & Log Management (first working version)

Run from the MELLOWTECH folder:   python apply_siem.py

It patches three files (a .before-siem.bak backup of each is made first):
  backend/app.py              new table siem_logs, POST /api/agent/logs (agents send logs),
                              GET /api/siem/logs (search), alert rules that raise Security Events
  agent/mellowtech_agent.py   collects security logs (Windows event logs, Linux ssh/sudo/useradd)
                              and sends them to the server every ~20 seconds
  index.html                  the SIEM page (search, filters, stats, CSV export) + sidebar button

Nothing is written unless ALL anchors are found and the new Python code compiles.
Safe to run twice: files that are already patched are skipped.
To undo: copy each .before-siem.bak file back over its original.
"""
import os
import re
import shutil
import sys

APP = os.path.join("backend", "app.py")
AGENT = os.path.join("agent", "mellowtech_agent.py")
INDEX = "index.html"

# ---------------------------------------------------------------------------
# SERVER BLOCK (inserted before the agent heartbeat route in backend/app.py)
# ---------------------------------------------------------------------------
SERVER_MARK = "MellowSecure SIEM: log collection and search"
SERVER_BLOCK = r'''# ===== MellowSecure SIEM: log collection and search (added by apply_siem.py) =====
import re as _siem_re
from datetime import timezone as _siem_tz

SIEM_RETENTION_DAYS = 30
SIEM_MAX_BATCH = 50
_SIEM_TS = _siem_re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d{1,3})?Z$")
_SIEM_LEVELS = ("info", "warning", "high")
_siem_ready = False

# log code -> (Security Event type, severity). Seeing one of these raises a Security Event.
_SIEM_RULES = {
    "1102": ("Security log cleared", "High"),
    "1116": ("Malware detected", "High"),
    "4720": ("New user account created", "Medium"),
    "useradd": ("New user account created", "Medium"),
    "4732": ("User added to a security group", "Medium"),
    "4740": ("Account locked out", "Medium"),
    "7045": ("New service installed", "Medium"),
}
_SIEM_FAIL_CODES = ("4625", "ssh_failed")


def _siem_utc_stamp(delta=None):
    moment = datetime.now(_siem_tz.utc)
    if delta is not None:
        moment = moment - delta
    return moment.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _siem_norm_ts(value):
    value = str(value or "")
    if not _SIEM_TS.match(value):
        return _siem_utc_stamp()
    base, _, frac = value[:-1].partition(".")
    return base + "." + (frac + "000")[:3] + "Z"


def _siem_table(db):
    global _siem_ready
    if _siem_ready:
        return
    db.executescript("""
        CREATE TABLE IF NOT EXISTS siem_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, org_id INTEGER NOT NULL, device_id INTEGER,
            device TEXT NOT NULL, ts TEXT NOT NULL, source TEXT, level TEXT NOT NULL DEFAULT 'info',
            code TEXT, message TEXT NOT NULL, ip TEXT);
        CREATE INDEX IF NOT EXISTS idx_siem_org_ts ON siem_logs (org_id, ts);
        CREATE INDEX IF NOT EXISTS idx_siem_org_code_ip ON siem_logs (org_id, code, ip, ts);
    """)
    db.commit()
    _siem_ready = True


def _siem_event(db, device, etype, severity, description, ip=None):
    cursor = db.execute(
        "INSERT INTO security_events (event_id,event_type,device,severity,status,description,timestamp,org_id,source_ip,device_id) "
        "VALUES ('PENDING',?,?,?,'New',?,?,?,?,?)",
        (etype[:100], device["name"], severity, description[:500], datetime.now().isoformat(),
         device["org_id"], ip, device["id"]))
    db.execute("UPDATE security_events SET event_id = ? WHERE id = ?", (f"EVT-{cursor.lastrowid:03d}", cursor.lastrowid))


@app.post("/api/agent/logs")
def siem_ingest():
    device = agent_device()
    if not device:
        return error("Unknown or removed device.", 401)
    data = request.get_json(silent=True) or {}
    items = data.get("logs")
    if not isinstance(items, list):
        return error("Send a list of logs.", 400)
    db = get_db()
    _siem_table(db)
    rows, hits, fail_ips = [], [], set()
    for item in items[:SIEM_MAX_BATCH]:
        if not isinstance(item, dict):
            continue
        message = str(item.get("message", "")).strip()[:300]
        if not message:
            continue
        level = str(item.get("level", "info")).lower()
        if level not in _SIEM_LEVELS:
            level = "info"
        code = str(item.get("code", ""))[:20]
        ip = clean_ip(item.get("ip", "")) or None
        rows.append((device["org_id"], device["id"], device["name"], _siem_norm_ts(item.get("ts")),
                     str(item.get("source", ""))[:60], level, code, message, ip))
        if code in _SIEM_RULES:
            hits.append((code, message, ip))
        if code in _SIEM_FAIL_CODES and ip:
            fail_ips.add(ip)
    if rows:
        db.executemany("INSERT INTO siem_logs (org_id,device_id,device,ts,source,level,code,message,ip) "
                       "VALUES (?,?,?,?,?,?,?,?,?)", rows)
    db.execute("DELETE FROM siem_logs WHERE org_id = ? AND ts < ?",
               (device["org_id"], _siem_utc_stamp(timedelta(days=SIEM_RETENTION_DAYS))))

    # alert rules: turn important logs into Security Events (max 5 per request, no repeats within 10 minutes)
    raised, alerts = 0, []
    recent_local = (datetime.now() - timedelta(minutes=10)).isoformat()
    for code, message, ip in hits:
        if raised >= 5:
            break
        etype, severity = _SIEM_RULES[code]
        seen = db.execute("SELECT 1 FROM security_events WHERE org_id=? AND device_id=? AND event_type=? "
                          "AND timestamp>? LIMIT 1", (device["org_id"], device["id"], etype, recent_local)).fetchone()
        if seen:
            continue
        _siem_event(db, device, etype, severity, message, ip)
        raised += 1
        if severity == "High":
            alerts.append((etype, device["name"] + ": " + message[:300]))

    # correlation: the same address failing to sign in on 3 or more devices within 10 minutes
    recent_utc = _siem_utc_stamp(timedelta(minutes=10))
    hour_local = (datetime.now() - timedelta(hours=1)).isoformat()
    for ip in list(fail_ips)[:10]:
        count = db.execute("SELECT COUNT(DISTINCT device_id) FROM siem_logs WHERE org_id=? AND ip=? "
                           "AND code IN ('4625','ssh_failed') AND ts>=?",
                           (device["org_id"], ip, recent_utc)).fetchone()[0]
        if count < 3:
            continue
        seen = db.execute("SELECT 1 FROM security_events WHERE org_id=? AND event_type=? AND source_ip=? "
                          "AND timestamp>? LIMIT 1",
                          (device["org_id"], "Coordinated sign-in attack", ip, hour_local)).fetchone()
        if seen:
            continue
        text = f"{ip} failed to sign in on {count} different devices in the last 10 minutes."
        _siem_event(db, device, "Coordinated sign-in attack", "High", text, ip)
        alerts.append(("Coordinated sign-in attack", text))
    db.commit()
    for title, detail in alerts[:3]:
        alert_org(device["org_id"], title, detail)
    return jsonify({"stored": len(rows)})


@app.get("/api/siem/logs")
@login_required()
def siem_search():
    db = get_db()
    _siem_table(db)
    org = g.user["org_id"]
    try:
        hours = max(1, min(24 * SIEM_RETENTION_DAYS, int(request.args.get("hours", "24"))))
    except ValueError:
        hours = 24
    try:
        limit = max(1, min(500, int(request.args.get("limit", "200"))))
    except ValueError:
        limit = 200
    since = _siem_utc_stamp(timedelta(hours=hours))
    where, args = ["org_id = ?", "ts >= ?"], [org, since]
    level = request.args.get("level", "").lower()
    if level in _SIEM_LEVELS:
        where.append("level = ?")
        args.append(level)
    device = request.args.get("device", "")[:100]
    if device:
        where.append("device = ?")
        args.append(device)
    q = request.args.get("q", "").strip().lower()[:100]
    if q:
        where.append("(instr(lower(message),?)>0 OR instr(lower(source),?)>0 OR instr(lower(code),?)>0 "
                     "OR instr(lower(coalesce(ip,'')),?)>0 OR instr(lower(device),?)>0)")
        args += [q] * 5
    clause = " AND ".join(where)
    total = db.execute("SELECT COUNT(*) FROM siem_logs WHERE " + clause, args).fetchone()[0]
    found = db.execute("SELECT id,ts,device,source,level,code,message,ip FROM siem_logs WHERE " + clause +
                       " ORDER BY ts DESC, id DESC LIMIT ?", args + [limit]).fetchall()
    day = _siem_utc_stamp(timedelta(hours=24))
    s = db.execute("SELECT COUNT(*), COALESCE(SUM(level='warning'),0), COALESCE(SUM(level='high'),0), "
                   "COUNT(DISTINCT device_id) FROM siem_logs WHERE org_id=? AND ts>=?", (org, day)).fetchone()
    devices = [r[0] for r in db.execute("SELECT DISTINCT device FROM siem_logs WHERE org_id=? AND ts>=? "
                                        "ORDER BY device LIMIT 100", (org, since)).fetchall()]
    return jsonify({
        "logs": [{"id": r["id"], "ts": r["ts"], "device": r["device"], "source": r["source"], "level": r["level"],
                  "code": r["code"], "message": r["message"], "ip": r["ip"]} for r in found],
        "total": total,
        "summary": {"total": s[0], "warnings": s[1], "high": s[2], "devices": s[3]},
        "devices": devices,
    })


'''
SERVER_ANCHOR = '@app.post("/api/agent/heartbeat")'

# ---------------------------------------------------------------------------
# AGENT BLOCK (inserted before def heartbeat in agent/mellowtech_agent.py)
# ---------------------------------------------------------------------------
AGENT_MARK = "MellowSecure SIEM: send security logs"
AGENT_BLOCK = r'''# ===== MellowSecure SIEM: send security logs to the server (added by apply_siem.py) =====
import xml.etree.ElementTree as _siem_et
from datetime import datetime as _siem_dt, timezone as _siem_utc

SIEM_EVERY_SECONDS = 20     # how often logs are collected and sent
SIEM_FETCH = 100            # most events read per log, per round
SIEM_CHUNK = 40             # most logs in one request
SIEM_MAX_BYTES = 12000      # the server refuses requests over 16 KB

# (Windows log name, label shown in the dashboard, event ids to collect)
_SIEM_WIN = [
    ("Security", "Windows Security", (4625, 4624, 4720, 4726, 4732, 4740, 1102)),
    ("System", "Windows System", (7045,)),
    ("Microsoft-Windows-Windows Defender/Operational", "Windows Defender", (1116,)),
]


def _siem_stamp(seconds_ago=0):
    return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(time.time() - seconds_ago))


def _siem_norm(ts):
    m = re.match(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.(\d+))?", str(ts or ""))
    if not m:
        return None
    return m.group(1) + "." + ((m.group(2) or "") + "000")[:3] + "Z"


def _siem_win_entry(code, d):
    """Turns one Windows event into (level, message, ip), or None if we do not want it."""
    def get(key):
        return (d.get(key) or "").strip()
    ip = get("IpAddress")
    ip = ip if (ip and valid_ip(ip) and ip not in ("127.0.0.1", "::1")) else None
    user = get("TargetUserName")
    if code == "4625":
        return "warning", "Failed sign-in for %s%s" % (user or "unknown user", (" from " + ip) if ip else ""), ip
    if code == "4624":
        if get("LogonType") not in ("2", "10"):
            return None
        if not user or user.endswith("$") or user.upper().startswith(("DWM-", "UMFD-")):
            return None
        return "info", "Sign-in succeeded for %s%s" % (user, (" from " + ip) if ip else ""), ip
    if code == "4720":
        return "warning", "User account created: %s (by %s)" % (user or "?", get("SubjectUserName") or "?"), None
    if code == "4726":
        return "warning", "User account deleted: %s (by %s)" % (user or "?", get("SubjectUserName") or "?"), None
    if code == "4732":
        return "warning", "A user was added to the group %s (by %s)" % (user or "?", get("SubjectUserName") or "?"), None
    if code == "4740":
        return "warning", "Account locked out: %s" % (user or "?"), None
    if code == "1102":
        return "high", "The Windows security audit log was cleared", None
    if code == "7045":
        return "warning", "New service installed: %s (%s)" % (get("ServiceName") or "?", get("ImagePath")[:120]), None
    if code == "1116":
        return "high", "Malware detected: %s %s" % (get("Threat Name") or "unknown threat", get("Path")[:120]), None
    return None


def _siem_parse_windows(text, label, since):
    """Returns (entries, newest_timestamp_seen)."""
    entries, newest = [], None
    try:
        root = _siem_et.fromstring("<Events>" + text + "</Events>")
    except Exception:
        return entries, newest
    for event in root:
        code, ts, data = None, None, {}
        for el in event.iter():
            tag = el.tag.rsplit("}", 1)[-1]
            if tag == "EventID":
                code = (el.text or "").strip()
            elif tag == "TimeCreated":
                ts = _siem_norm(el.get("SystemTime"))
            elif tag == "Data" and el.get("Name"):
                data[el.get("Name")] = el.text or ""
        if not code or not ts or ts <= since:
            continue
        if newest is None or ts > newest:
            newest = ts
        made = _siem_win_entry(code, data)
        if made:
            level, message, ip = made
            entries.append({"ts": ts, "source": label, "level": level, "code": code, "message": message[:300], "ip": ip})
    return entries, newest


def _siem_collect_windows(sinces):
    found = []
    for channel, label, ids in _SIEM_WIN:
        since = sinces.get(channel) or _siem_stamp(600)
        condition = " or ".join("EventID=%d" % i for i in ids)
        query = "*[System[(%s) and TimeCreated[@SystemTime>'%s']]]" % (condition, since)
        code, text = run(["wevtutil", "qe", channel, "/q:" + query, "/f:xml", "/rd:false", "/c:%d" % SIEM_FETCH], 40)
        if code != 0 or not text.strip():
            continue
        entries, newest = _siem_parse_windows(text, label, since)
        found.append((channel, entries, newest))
    return found


def _siem_collect_linux(sinces):
    if not shutil.which("journalctl"):
        return []
    since = sinces.get("journal") or _siem_stamp(600)
    stamp = since[:19].replace("T", " ") + " UTC"
    code, text = run(["journalctl", "--since", stamp, "--no-pager", "-q", "-o", "short-iso",
                      "-t", "sshd", "-t", "sudo", "-t", "useradd"], 30)
    entries, newest = [], None
    if code != 0 or not text.strip():
        return []
    for line in text.splitlines()[-SIEM_FETCH:]:
        m = re.match(r"^(\S+)\s+\S+\s+(\S+?)(?:\[\d+\])?:\s+(.*)$", line)
        if not m:
            continue
        try:
            moment = _siem_dt.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S%z").astimezone(_siem_utc.utc)
            ts = moment.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        except Exception:
            continue
        if ts <= since:
            continue
        if newest is None or ts > newest:
            newest = ts
        tag, body = m.group(2), m.group(3)
        found = re.search(r"Failed password for (?:invalid user )?(\S+) from (\S+)", body)
        if found and valid_ip(found.group(2)):
            entries.append({"ts": ts, "source": "Linux auth", "level": "warning", "code": "ssh_failed",
                            "message": "Failed SSH sign-in for %s from %s" % (found.group(1), found.group(2)),
                            "ip": found.group(2)})
            continue
        found = re.search(r"Accepted \S+ for (\S+) from (\S+)", body)
        if found and valid_ip(found.group(2)):
            entries.append({"ts": ts, "source": "Linux auth", "level": "info", "code": "ssh_ok",
                            "message": "SSH sign-in succeeded for %s from %s" % (found.group(1), found.group(2)),
                            "ip": found.group(2)})
            continue
        if tag == "useradd" and "new user" in body:
            entries.append({"ts": ts, "source": "Linux auth", "level": "warning", "code": "useradd",
                            "message": "A new user account was created", "ip": None})
            continue
        if tag == "sudo" and "COMMAND=" in body:
            who = body.split(":", 1)[0].strip()[:40]
            entries.append({"ts": ts, "source": "Linux auth", "level": "info", "code": "sudo",
                            "message": "sudo was used by %s" % who, "ip": None})   # the command itself is not stored
    return [("journal", entries, newest)]


def ship_logs(config, state):
    """Collects new security logs and sends them. Never raises: a failure here must not stop the agent."""
    try:
        if time.time() < state.get("siem_next", 0):
            return
        state["siem_next"] = time.time() + SIEM_EVERY_SECONDS
        sinces = state.get("siem_since")
        if not isinstance(sinces, dict):
            sinces = state["siem_since"] = {}
        if SYSTEM == "Windows":
            rounds = _siem_collect_windows(sinces)
        elif SYSTEM == "Linux":
            rounds = _siem_collect_linux(sinces)
        else:
            return
        entries = [e for _key, items, _newest in rounds for e in items]
        entries.sort(key=lambda e: e["ts"])
        chunk, size = [], 0
        for entry in entries:
            piece = len(json.dumps(entry))
            if chunk and (len(chunk) >= SIEM_CHUNK or size + piece > SIEM_MAX_BYTES):
                call(config["server"], "/api/agent/logs", {"logs": chunk}, config["token"])
                chunk, size = [], 0
            chunk.append(entry)
            size += piece
        if chunk:
            call(config["server"], "/api/agent/logs", {"logs": chunk}, config["token"])
        for key, _items, newest in rounds:       # only move forward after everything was sent
            if newest:
                sinces[key] = newest
    except Gone:
        raise
    except Exception as exc:
        log("Could not send logs, will retry:", exc)


'''
AGENT_ANCHOR = "def heartbeat(config, state, posture, alerts):"
AGENT_LOOP_OLD = "            acknowledge(config, results)\n"
AGENT_LOOP_NEW = "            acknowledge(config, results)\n            ship_logs(config, state)\n"

# ---------------------------------------------------------------------------
# FRONT END (index.html)
# ---------------------------------------------------------------------------
INDEX_MARK = 'id="siem-js"'

SIEM_BUTTON = (
    '<button type="button" class="nav-button" data-page="siem">\n'
    '                <svg class="icon" aria-hidden="true"><use href="#i-list"/></svg>SIEM &amp; Log Management\n'
    '            </button>'
)

SIEM_PAGE = r'''<section id="siem" class="page" hidden>
            <h2>SIEM &amp; Log Management</h2>
            <p class="page-description">Security logs from your connected devices, searchable in one place. Logs are kept for 30 days.</p>

            <div class="stats-grid">
                <div class="stat-card"><span>LOGS (24H)</span><strong id="siem-s-total">0</strong></div>
                <div class="stat-card"><span>WARNINGS (24H)</span><strong id="siem-s-warn">0</strong></div>
                <div class="stat-card"><span>HIGH (24H)</span><strong id="siem-s-high">0</strong></div>
                <div class="stat-card"><span>DEVICES REPORTING</span><strong id="siem-s-dev">0</strong></div>
            </div>

            <div class="panel">
                <div class="panel-header">
                    <div>
                        <h3>Log search</h3>
                        <p>Filter by text, level, device and time range.</p>
                    </div>
                    <span class="live-indicator">LIVE</span>
                </div>
                <div class="siem-controls">
                    <input type="search" id="siem-q" placeholder="Search logs (user, IP, device, text)..." aria-label="Search logs" autocomplete="off">
                    <select id="siem-level" aria-label="Level">
                        <option value="">All levels</option>
                        <option value="high">High</option>
                        <option value="warning">Warning</option>
                        <option value="info">Info</option>
                    </select>
                    <select id="siem-device" aria-label="Device"><option value="">All devices</option></select>
                    <select id="siem-hours" aria-label="Time range">
                        <option value="1">Last hour</option>
                        <option value="24" selected>Last 24 hours</option>
                        <option value="168">Last 7 days</option>
                        <option value="720">Last 30 days</option>
                    </select>
                    <button type="button" class="siem-btn" id="siem-refresh">Refresh</button>
                    <button type="button" class="siem-btn" id="siem-export">Export CSV</button>
                    <label class="siem-auto"><input type="checkbox" id="siem-auto" checked> Auto-refresh</label>
                </div>
                <p id="siem-msg" class="siem-msg"></p>
                <div class="siem-scroll">
                    <table class="siem-table">
                        <thead><tr><th>Time</th><th>Level</th><th>Device</th><th>Source</th><th>Code</th><th>Message</th><th>IP</th></tr></thead>
                        <tbody id="siem-body"></tbody>
                    </table>
                </div>
            </div>
        </section>'''

SIEM_CSS = r'''<style id="siem-css">
.siem-controls{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:14px 0 8px}
.siem-controls input[type=search]{flex:1 1 240px;min-width:200px}
.siem-controls input[type=search],.siem-controls select{padding:9px 12px;border-radius:10px;border:1px solid #cbd5e1;background:#fff;color:#0f172a;font:inherit;font-size:.9rem}
.siem-btn{padding:9px 16px;border-radius:10px;border:1px solid #cbd5e1;background:#f1f5f9;color:#0f172a;font:inherit;font-size:.9rem;font-weight:600;cursor:pointer}
.siem-btn:hover{background:#e2e8f0}
.siem-auto{font-size:.85rem;color:#475569;display:flex;gap:6px;align-items:center}
.siem-msg{margin:6px 0 10px;color:#475569;font-size:.9rem}
.siem-scroll{overflow-x:auto;max-width:100%}
.siem-table{width:100%;border-collapse:collapse;font-size:.85rem}
.siem-table th{text-align:left;padding:8px 10px;border-bottom:2px solid #e2e8f0;color:#475569;font-size:.72rem;letter-spacing:.08em;text-transform:uppercase;white-space:nowrap}
.siem-table td{padding:8px 10px;border-bottom:1px solid #eef2f7;vertical-align:top}
.siem-table td.siem-time{white-space:nowrap;color:#475569}
.siem-table td.siem-msgcell{min-width:260px;word-break:break-word}
.siem-lvl{display:inline-block;padding:2px 8px;border-radius:999px;font-size:.7rem;font-weight:700;text-transform:uppercase}
.siem-lvl-info{background:#e0f2fe;color:#075985}
.siem-lvl-warning{background:#fef3c7;color:#92400e}
.siem-lvl-high{background:#fee2e2;color:#991b1b}
</style>
'''

SIEM_JS = r'''<script id="siem-js">
(function () {
  var page = document.getElementById("siem");
  if (!page) { return; }
  var $ = function (id) { return document.getElementById(id); };
  var body = $("siem-body"), msg = $("siem-msg");
  var rows = [], busy = false, typing = null;

  function params() {
    var p = new URLSearchParams();
    var q = $("siem-q").value.trim();
    if (q) { p.set("q", q); }
    ["level", "device", "hours"].forEach(function (k) {
      var v = $("siem-" + k).value;
      if (v) { p.set(k, v); }
    });
    p.set("limit", "300");
    return p.toString();
  }

  function cell(tr, text, cls) {
    var td = document.createElement("td");
    td.textContent = (text === null || text === undefined) ? "" : String(text);
    if (cls) { td.className = cls; }
    tr.appendChild(td);
    return td;
  }

  function fillDevices(list) {
    var select = $("siem-device"), current = select.value;
    while (select.options.length > 1) { select.remove(1); }
    var names = list.slice();
    if (current && names.indexOf(current) === -1) { names.push(current); }
    names.forEach(function (name) {
      var o = document.createElement("option");
      o.value = name; o.textContent = name;
      select.appendChild(o);
    });
    select.value = current;
  }

  function render(data) {
    var s = data.summary || {};
    $("siem-s-total").textContent = s.total || 0;
    $("siem-s-warn").textContent = s.warnings || 0;
    $("siem-s-high").textContent = s.high || 0;
    $("siem-s-dev").textContent = s.devices || 0;
    fillDevices(data.devices || []);
    rows = data.logs || [];
    body.textContent = "";
    rows.forEach(function (r) {
      var tr = document.createElement("tr");
      var when = new Date(r.ts);
      cell(tr, isNaN(when) ? r.ts : when.toLocaleString(), "siem-time");
      var lvl = cell(tr, "");
      var badge = document.createElement("span");
      badge.className = "siem-lvl siem-lvl-" + (["info", "warning", "high"].indexOf(r.level) > -1 ? r.level : "info");
      badge.textContent = r.level;
      lvl.appendChild(badge);
      cell(tr, r.device); cell(tr, r.source); cell(tr, r.code);
      cell(tr, r.message, "siem-msgcell"); cell(tr, r.ip);
      body.appendChild(tr);
    });
    if (!rows.length) {
      msg.textContent = (s.total ? "No logs match these filters." :
        "No logs yet. Logs appear here once a device running the updated MellowTech agent reports in.");
    } else {
      msg.textContent = "Showing " + rows.length + " of " + data.total + " matching logs (newest first).";
    }
  }

  function load() {
    if (busy) { return; }
    busy = true;
    fetch("/api/siem/logs?" + params(), { credentials: "same-origin" })
      .then(function (r) {
        if (r.status === 401) { throw new Error("Please sign in again."); }
        if (!r.ok) { throw new Error("Could not load logs."); }
        return r.json();
      })
      .then(render)
      .catch(function (e) { msg.textContent = e.message || "Could not load logs."; })
      .then(function () { busy = false; });
  }

  function csvCell(v) {
    var t = (v === null || v === undefined) ? "" : String(v);
    if (/^[=+\-@\t\r]/.test(t)) { t = "'" + t; }
    return '"' + t.replace(/"/g, '""') + '"';
  }

  function exportCsv() {
    var lines = [["time", "level", "device", "source", "code", "message", "ip"].join(",")];
    rows.forEach(function (r) {
      lines.push([r.ts, r.level, r.device, r.source, r.code, r.message, r.ip].map(csvCell).join(","));
    });
    var blob = new Blob([lines.join("\r\n")], { type: "text/csv" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "mellowsecure-logs.csv";
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
  }

  $("siem-refresh").addEventListener("click", load);
  $("siem-export").addEventListener("click", exportCsv);
  ["level", "device", "hours"].forEach(function (k) { $("siem-" + k).addEventListener("change", load); });
  $("siem-q").addEventListener("input", function () { clearTimeout(typing); typing = setTimeout(load, 350); });
  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest('.nav-button[data-page="siem"]');
    if (b) { setTimeout(load, 0); }
  });
  setInterval(function () { if (!page.hidden && $("siem-auto").checked) { load(); } }, 15000);
})();
</script>
'''


def read(path):
    with open(path, "r", encoding="utf-8", newline="") as fh:
        raw = fh.read()
    return raw.replace("\r\n", "\n"), ("\r\n" in raw)


def write(path, text, crlf):
    if crlf:
        text = text.replace("\n", "\r\n")
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def patch_app(text):
    if SERVER_MARK in text:
        return None, "already patched"
    if text.count(SERVER_ANCHOR) != 1:
        raise ValueError("backend/app.py: could not find the agent heartbeat route exactly once")
    for taken in ('"/api/agent/logs"', '"/api/siem/logs"'):
        if taken in text:
            raise ValueError("backend/app.py: the route %s already exists" % taken)
    new = text.replace(SERVER_ANCHOR, SERVER_BLOCK + SERVER_ANCHOR, 1)
    compile(new, APP, "exec")
    return new, "patched"


def patch_agent(text):
    if AGENT_MARK in text:
        return None, "already patched"
    if text.count(AGENT_ANCHOR) != 1:
        raise ValueError("agent: could not find 'def heartbeat' exactly once")
    if text.count(AGENT_LOOP_OLD) != 1:
        raise ValueError("agent: could not find the acknowledge(config, results) line in the main loop exactly once")
    new = text.replace(AGENT_ANCHOR, AGENT_BLOCK + AGENT_ANCHOR, 1)
    new = new.replace(AGENT_LOOP_OLD, AGENT_LOOP_NEW, 1)
    compile(new, AGENT, "exec")
    return new, "patched"


def patch_index(text):
    if INDEX_MARK in text:
        return None, "already patched"
    if 'id="siem"' in text:
        raise ValueError("index.html: a page with id=\"siem\" already exists")
    if 'id="mod-siem"' in text:
        # the sidebar v2 placeholder is there: turn it into the real page
        text = text.replace('data-page="mod-siem"', 'data-page="siem"')
        text, n = re.subn(r'<section id="mod-siem" class="page" hidden>.*?</section>',
                          lambda m: SIEM_PAGE, text, count=1, flags=re.S)
        if n != 1:
            raise ValueError("index.html: could not replace the SIEM placeholder page")
    else:
        events_btn = re.search(r'<button\b[^>]*data-page="events"[^>]*>.*?</button>', text, re.S)
        marker = "<!-- ========== NETWORK MONITORING ========== -->"
        if not events_btn or marker not in text:
            raise ValueError("index.html: could not find the Security Events button or the Network Monitoring marker")
        text = text[:events_btn.end()] + "\n            " + SIEM_BUTTON + text[events_btn.end():]
        text = text.replace(marker, SIEM_PAGE + "\n\n        " + marker, 1)
    if "</head>" not in text or text.rfind("</body>") == -1:
        raise ValueError("index.html: could not find </head> or </body>")
    text = text.replace("</head>", SIEM_CSS + "</head>", 1)
    i = text.rfind("</body>")
    text = text[:i] + SIEM_JS + text[i:]
    return text, "patched"


def main():
    missing = [p for p in (APP, AGENT, INDEX) if not os.path.isfile(p)]
    if missing:
        sys.exit("ERROR: not found: %s\nRun this script from the MELLOWTECH folder." % ", ".join(missing))

    plan = []
    try:
        for path, fn in ((APP, patch_app), (AGENT, patch_agent), (INDEX, patch_index)):
            text, crlf = read(path)
            new, status = fn(text)
            plan.append((path, new, crlf, status))
    except (ValueError, SyntaxError) as exc:
        sys.exit("ERROR: %s\nNothing was changed." % exc)

    for path, new, crlf, status in plan:
        if new is None:
            print("  %-28s already patched, skipped" % path)
            continue
        backup = path + ".before-siem.bak"
        if not os.path.exists(backup):
            shutil.copy2(path, backup)
        write(path, new, crlf)
        print("  %-28s patched (backup: %s)" % (path, os.path.basename(backup)))

    print("\nDone. Next:")
    print("  1. Test locally (start.bat), open SIEM & Log Management in the sidebar.")
    print("  2. Deploy the server first (make_eb_zip.py + upload), then rebuild the agent")
    print("     (agent\\build_agent_exe.bat) and reinstall it on your devices to start sending logs.")


if __name__ == "__main__":
    main()