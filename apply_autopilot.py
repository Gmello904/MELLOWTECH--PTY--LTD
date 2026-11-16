"""Part 3: Autopilot. The software fixes problems on its own and records what it did.

Put this file in the MELLOWTECH folder (next to index.html) and run:
    python apply_autopilot.py
Run apply_features.py first. Backups are saved next to each changed file as *.bak
"""
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent

AUTOPILOT_PY = r'''"""MellowTech Autopilot: fixes problems on its own, with safeguards, and records everything it did.

It runs whenever a laptop agent checks in. It can only use actions the laptop agents already support:
block an attacking address, update virus definitions, run a virus scan, isolate a laptop and block USB storage.
It cannot change anything outside the connected laptops (for example a company's cloud account).
"""
import json
from datetime import datetime, timedelta

from flask import g, jsonify, request

RULES = [
    {"key": "block_attackers", "label": "Block attacking addresses", "default": True, "risky": False,
     "description": "When your laptops report a serious attack from an outside address, block that address on every laptop for 24 hours."},
    {"key": "update_protection", "label": "Keep virus definitions up to date", "default": True, "risky": False,
     "description": "If a laptop's virus definitions are 3 days old or more, update them."},
    {"key": "scan_stale", "label": "Run a virus scan when one is overdue", "default": True, "risky": False,
     "description": "If a laptop has not had a quick scan for 7 days, scan it."},
    {"key": "isolate_threats", "label": "Isolate a laptop with an active threat", "default": False, "risky": True,
     "description": "If the antivirus reports an active threat, cut that laptop off the network for 60 minutes so the infection cannot spread. It is released automatically."},
    {"key": "block_usb", "label": "Block USB storage on laptops", "default": False, "risky": True,
     "description": "Turn off USB drives on every laptop that allows them. Keyboards and mice keep working."},
]
RULE_KEYS = {r["key"]: r for r in RULES}

MAX_AUTO_BLOCKS_PER_HOUR = 5
RUN_EVERY_SECONDS = 20
_deps = {}
_last_run = {}


def ensure_tables(db):
    db.execute("CREATE TABLE IF NOT EXISTS autopilot_settings (org_id INTEGER NOT NULL, rule TEXT NOT NULL, "
               "enabled INTEGER NOT NULL, PRIMARY KEY (org_id, rule))")
    db.execute("CREATE TABLE IF NOT EXISTS autopilot_log (id INTEGER PRIMARY KEY AUTOINCREMENT, org_id INTEGER NOT NULL, "
               "ts TEXT NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL)")


def is_on(db, org_id, rule):
    row = db.execute("SELECT enabled FROM autopilot_settings WHERE org_id = ? AND rule = ?", (org_id, rule)).fetchone()
    return bool(row["enabled"]) if row else RULE_KEYS[rule]["default"]


def note(db, org_id, action, detail):
    db.execute("INSERT INTO autopilot_log (org_id, ts, action, detail) VALUES (?,?,?,?)",
               (org_id, _deps["iso"](_deps["utcnow"]()), action, detail[:300]))


def queue(db, org_id, device_id, action, param=None):
    db.execute("INSERT INTO commands (org_id,device_id,block_id,action,ip,param,status,created_at) "
               "VALUES (?,?,NULL,?,'',?,'pending',?)", (org_id, device_id, action, param, _deps["iso"](_deps["utcnow"]())))


def done_recently(db, device_id, action, hours):
    since = _deps["iso"](_deps["utcnow"]() - timedelta(hours=hours))
    return db.execute("SELECT 1 FROM commands WHERE device_id = ? AND action = ? AND created_at >= ? "
                      "AND status != 'cancelled' LIMIT 1", (device_id, action, since)).fetchone() is not None


def block_attackers(db, org_id):
    since = (datetime.now() - timedelta(hours=24)).isoformat()      # events store local time without a zone
    rows = db.execute("SELECT id, source_ip, severity FROM security_events WHERE org_id = ? AND status = 'New' "
                      "AND source_ip IS NOT NULL AND source_ip != '' AND timestamp >= ? ORDER BY id",
                      (org_id, since)).fetchall()
    by_ip = {}
    for row in rows:
        entry = by_ip.setdefault(row["source_ip"], {"first": row["id"], "high": 0, "medium": 0})
        if row["severity"] == "High":
            entry["high"] += 1
        elif row["severity"] == "Medium":
            entry["medium"] += 1

    hour_ago = _deps["iso"](_deps["utcnow"]() - timedelta(hours=1))
    made = db.execute("SELECT COUNT(*) FROM autopilot_log WHERE org_id = ? AND action = 'Blocked an attacker' AND ts >= ?",
                      (org_id, hour_ago)).fetchone()[0]
    for ip, entry in by_ip.items():
        if entry["high"] < 1 and entry["medium"] < 3:
            continue
        if made >= MAX_AUTO_BLOCKS_PER_HOUR:
            break
        if db.execute("SELECT 1 FROM blocks WHERE org_id = ? AND ip = ? AND status = 'active'", (org_id, ip)).fetchone():
            continue
        if _deps["block_problem"](ip, org_id):          # never block our own server, our laptops or private addresses
            continue
        now = _deps["utcnow"]()
        cursor = db.execute("INSERT INTO blocks (org_id,ip,reason,created_by,created_at,expires_at,event_id) VALUES (?,?,?,?,?,?,?)",
                            (org_id, ip, "Autopilot: repeated or serious attack", None, _deps["iso"](now),
                             _deps["iso"](now + timedelta(hours=24)), entry["first"]))
        count = _deps["queue_commands"](org_id, cursor.lastrowid, ip, "block")
        db.execute("UPDATE security_events SET status = 'Blocked' WHERE org_id = ? AND source_ip = ? AND status = 'New'",
                   (org_id, ip))
        alerts = entry["high"] + entry["medium"]
        note(db, org_id, "Blocked an attacker",
             f"{ip} was blocked on {count} laptop(s) for 24 hours after {alerts} alert(s). Undo it on the Threat Detection page.")
        made += 1


def check_device(db, org_id, device_id):
    row = db.execute("SELECT name, posture FROM devices WHERE id = ? AND org_id = ?", (device_id, org_id)).fetchone()
    if not row or not row["posture"]:
        return
    try:
        posture = json.loads(row["posture"])
    except ValueError:
        return
    if not isinstance(posture, dict) or posture.get("platform"):
        return
    name, defender = row["name"], posture.get("defender") or {}
    working = defender.get("state") == "on"

    age = defender.get("definitions_age_days")
    if (is_on(db, org_id, "update_protection") and working and age is not None and age >= 3
            and not done_recently(db, device_id, "update_protection", 6)):
        queue(db, org_id, device_id, "update_protection")
        note(db, org_id, "Updated protection", f"{name}: virus definitions were {age} day(s) old, so an update was started.")

    scan_age = defender.get("quick_scan_age_days")
    if (is_on(db, org_id, "scan_stale") and working and (scan_age is None or scan_age >= 7)
            and not done_recently(db, device_id, "scan", 24)):
        queue(db, org_id, device_id, "scan")
        note(db, org_id, "Started a virus scan",
             f"{name}: no recent scan" + ("" if scan_age is None else f" ({scan_age} days)") + ", so a quick scan was started.")

    if (is_on(db, org_id, "isolate_threats") and (defender.get("threats_active") or 0) > 0 and not posture.get("isolated")
            and not done_recently(db, device_id, "isolate", 6)):
        queue(db, org_id, device_id, "isolate", "60")
        note(db, org_id, "Isolated a laptop",
             f"{name} has an active threat, so it was cut off the network for 60 minutes. It is released automatically.")

    if (is_on(db, org_id, "block_usb") and posture.get("usb_storage") == "allowed"
            and not done_recently(db, device_id, "usb_block", 24)):
        queue(db, org_id, device_id, "usb_block")
        note(db, org_id, "Blocked USB storage", f"{name} allowed USB drives, so USB storage was blocked.")


def run(db, org_id, device_id):
    """Called every time a laptop agent checks in. Never raises, so a problem here cannot break the agent."""
    try:
        if not _deps or not _deps["feature_allowed"](org_id, "autopilot"):
            return
        now = datetime.now().timestamp()
        if now - _last_run.get(org_id, 0) < RUN_EVERY_SECONDS:
            return
        _last_run[org_id] = now
        ensure_tables(db)
        if is_on(db, org_id, "block_attackers"):
            block_attackers(db, org_id)
        for row in db.execute("SELECT id FROM devices WHERE org_id = ?", (org_id,)).fetchall():
            check_device(db, org_id, row["id"])
        db.commit()
    except Exception as exc:
        print(f"Autopilot problem (agent not affected): {exc}", flush=True)


def init_autopilot(app, deps):
    _deps.update(deps)
    get_db, error, iso, utcnow = deps["get_db"], deps["error"], deps["iso"], deps["utcnow"]
    login_required, audit, locked, feature_allowed = deps["login_required"], deps["audit"], deps["locked"], deps["feature_allowed"]

    @app.get("/api/autopilot")
    @login_required()
    def autopilot_status():
        db = get_db()
        ensure_tables(db)
        org_id = g.user["org_id"]
        log = db.execute("SELECT ts, action, detail FROM autopilot_log WHERE org_id = ? ORDER BY id DESC LIMIT 40",
                         (org_id,)).fetchall()
        return jsonify({"allowed": feature_allowed(org_id, "autopilot"),
                        "rules": [{"key": r["key"], "label": r["label"], "description": r["description"],
                                   "risky": r["risky"], "enabled": is_on(db, org_id, r["key"])} for r in RULES],
                        "log": [dict(r) for r in log]})

    @app.post("/api/autopilot/rule")
    @login_required("admin")
    def autopilot_rule():
        data = request.get_json(silent=True) or {}
        key = data.get("key")
        if key not in RULE_KEYS or not isinstance(data.get("enabled"), bool):
            return error("Unknown setting.", 400)
        denied = locked("autopilot")
        if denied:
            return denied
        db = get_db()
        ensure_tables(db)
        db.execute("INSERT INTO autopilot_settings (org_id, rule, enabled) VALUES (?,?,?) "
                   "ON CONFLICT(org_id, rule) DO UPDATE SET enabled = excluded.enabled",
                   (g.user["org_id"], key, 1 if data["enabled"] else 0))
        db.commit()
        audit("autopilot_setting", f"{key} {'on' if data['enabled'] else 'off'}")
        return jsonify({"ok": True})
'''

APP_HELPER = '''def feature_allowed(org_id, feature):
    """True when the company's plan includes the feature (MellowTech staff are never locked)."""
    org = get_db().execute("SELECT is_platform FROM organisations WHERE id = ?", (org_id,)).fetchone()
    if org and org["is_platform"]:
        return True
    needs, _label = FEATURE_PLANS[feature]
    return PLAN_ORDER.get(current_plan(org_id), 0) >= PLAN_ORDER[needs]


'''

APP_REPLACEMENTS = [
    ("import docscan\n",
     "import docscan\nimport autopilot\n"),

    ('    "device_command": ("business", "Device isolation, virus scans and USB control"),\n',
     '    "device_command": ("business", "Device isolation, virus scans and USB control"),\n'
     '    "autopilot":      ("business", "Autopilot: fixes problems automatically"),\n'),

    ('@app.get("/api/features")\n',
     APP_HELPER + '@app.get("/api/features")\n'),

    ('    expire_blocks(device["org_id"])\n',
     '    expire_blocks(device["org_id"])\n'
     '    autopilot.run(db, device["org_id"], device["id"])        # fixes problems by itself; queued orders go out below\n'),

    ("    login_required=login_required, audit=audit, too_many=too_many, locked=locked))\n",
     "    login_required=login_required, audit=audit, too_many=too_many, locked=locked))\n"
     "autopilot.init_autopilot(app, dict(\n"
     "    get_db=get_db, error=error, iso=iso, utcnow=utcnow, login_required=login_required, audit=audit,\n"
     "    locked=locked, feature_allowed=feature_allowed, block_problem=block_problem, queue_commands=queue_commands))\n"),
]

NAV_BUTTON = '''<button type="button" class="nav-button" data-page="autopilot">
                <svg class="icon" aria-hidden="true"><use href="#i-refresh"/></svg>Autopilot
            </button>
            '''

SECTION = '''<!-- ========== AUTOPILOT ========== -->
        <section id="autopilot" class="page" hidden>
            <h2>Autopilot</h2>
            <p class="page-description">Autopilot watches your laptops and fixes problems by itself, without waiting for a person. Choose what it is allowed to do.</p>

            <div id="ap-lock" class="bill-notice info" hidden>
                Locked: Autopilot is included in Business Protection or a higher plan.
                <button type="button" class="btn-small" id="ap-unlock" style="margin-left:12px">Unlock with a plan</button>
            </div>
            <div id="ap-message" class="result-message" role="status" aria-live="polite"></div>

            <div class="panel">
                <h3>What Autopilot may do</h3>
                <div id="ap-rules">Loading...</div>
                <p class="page-description" style="margin:12px 0 0">Autopilot only uses actions your connected laptops support. It never blocks your own laptops or this server, and it blocks at most five addresses an hour. Every action is recorded below, and blocks can be undone on the Threat Detection page.</p>
            </div>

            <div class="panel">
                <h3>What Autopilot did</h3>
                <div class="table-scroll">
                    <table class="events-table">
                        <caption class="sr-only">Actions taken by Autopilot</caption>
                        <thead><tr><th scope="col">Time</th><th scope="col">Action</th><th scope="col">Details</th></tr></thead>
                        <tbody id="ap-log"><tr><td colspan="3">Loading...</td></tr></tbody>
                    </table>
                </div>
            </div>
        </section>

        '''

SCRIPT = r'''<!-- Autopilot -->
    <script>
    (function () {
        var csrf = "";

        function $(id) { return document.getElementById(id); }

        function esc(value) {
            return String(value == null ? "" : value).replace(/[&<>"']/g, function (c) {
                return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
            });
        }

        function api(path, body) {
            var options = { credentials: "same-origin", headers: { "Content-Type": "application/json" } };
            if (body !== undefined) {
                options.method = "POST";
                options.headers["X-CSRF-Token"] = csrf;
                options.body = JSON.stringify(body);
            }
            return fetch(path, options).then(function (response) {
                return response.json().catch(function () { return {}; }).then(function (data) {
                    if (!response.ok) {
                        var problem = new Error(data.error || "Something went wrong.");
                        problem.locked = !!data.locked;
                        throw problem;
                    }
                    return data;
                });
            });
        }

        function say(text, kind, withUnlock) {
            var box = $("ap-message");
            box.textContent = text || "";
            box.style.color = kind === "err" ? "#b42318" : kind === "ok" ? "#12906e" : "";
            if (text && withUnlock) {
                var unlock = document.createElement("button");
                unlock.type = "button";
                unlock.className = "btn-small";
                unlock.style.marginLeft = "12px";
                unlock.textContent = "Unlock with a plan";
                unlock.addEventListener("click", openBilling);
                box.appendChild(unlock);
            }
        }

        function openBilling() {
            var button = document.querySelector('.nav-button[data-page="billing"]');
            if (button) { button.click(); }
        }

        function load() {
            api("/api/autopilot").then(function (data) {
                $("ap-lock").hidden = data.allowed;
                $("ap-rules").innerHTML = data.rules.map(function (r) {
                    return '<label class="status-item" style="align-items:flex-start;gap:14px;cursor:pointer">' +
                        '<input type="checkbox" data-ap-rule="' + esc(r.key) + '"' + (r.enabled ? " checked" : "") + ' style="margin-top:4px">' +
                        '<span style="flex:1"><b>' + esc(r.label) + "</b>" + (r.risky ? ' <span class="badge warning">Use with care</span>' : "") +
                        '<br><span class="rl-skills">' + esc(r.description) + "</span></span></label>";
                }).join("");
                $("ap-log").innerHTML = data.log.length ? data.log.map(function (l) {
                    return "<tr><td>" + esc(new Date(l.ts).toLocaleString()) + "</td><td><b>" + esc(l.action) + "</b></td><td>" + esc(l.detail) + "</td></tr>";
                }).join("") : '<tr><td colspan="3">Nothing yet. Autopilot acts as soon as a connected laptop reports a problem.</td></tr>';
            }).catch(function (problem) { say(problem.message, "err"); });
        }

        document.addEventListener("change", function (event) {
            var box = event.target;
            if (!box.dataset || !box.dataset.apRule) { return; }
            var wanted = box.checked;
            api("/api/autopilot/rule", { key: box.dataset.apRule, enabled: wanted }).then(function () {
                say(wanted ? "Turned on." : "Turned off.", "ok");
            }).catch(function (problem) {
                box.checked = !wanted;
                say(problem.message, "err", problem.locked);
            });
        });

        document.addEventListener("DOMContentLoaded", function () {
            api("/api/auth/me").then(function (data) { csrf = data.csrf; load(); }).catch(function () {});
            var nav = document.querySelector('.nav-button[data-page="autopilot"]');
            if (nav) { nav.addEventListener("click", load); }
            $("ap-unlock").addEventListener("click", openBilling);
            setInterval(function () { if (!$("autopilot").hidden) { load(); } }, 15000);
        });
    })();
    </script>
'''

MARKER = 'id="autopilot"'

INDEX_REPLACEMENTS = [
    ('<button type="button" class="nav-button" data-page="company">',
     NAV_BUTTON + '<button type="button" class="nav-button" data-page="company">'),
    ("<!-- ========== COMPANY ========== -->",
     SECTION + "<!-- ========== COMPANY ========== -->"),
    ("</body>", SCRIPT + "</body>"),
]


def apply(path, replacements, marker, needs=None):
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return "already updated"
    if needs and needs not in text:
        return f"NOT changed: run apply_features.py first"
    for old, new in replacements:
        count = text.count(old)
        if count != 1:
            return f"NOT changed: could not find a unique match for {old.strip()[:50]!r} (found {count})"
        text = text.replace(old, new, 1)
    shutil.copy2(path, str(path) + ".bak")
    path.write_text(text, encoding="utf-8")
    return "updated"


def main():
    for folder in (HERE / "backend", HERE / "aws-deploy"):
        app_file = folder / "app.py"
        if not app_file.is_file():
            continue
        (folder / "autopilot.py").write_text(AUTOPILOT_PY, encoding="utf-8")
        print(f"{folder.name}\\autopilot.py: written")
        print(f"{folder.name}\\app.py: {apply(app_file, APP_REPLACEMENTS, 'import autopilot', needs='FEATURE_PLANS')}")
    for path in (HERE / "index.html", HERE / "aws-deploy" / "index.html"):
        if path.is_file():
            print(f"{path.relative_to(HERE)}: {apply(path, INDEX_REPLACEMENTS, MARKER)}")
    print("\nDone. Restart python app.py, then refresh the browser with Ctrl+Shift+R.")


if __name__ == "__main__":
    main()