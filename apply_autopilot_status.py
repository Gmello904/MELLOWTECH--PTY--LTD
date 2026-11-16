"""Part 3b: shows that Autopilot is running.

Adds to the Autopilot page: a live status line (running or waiting, last check time, laptops online, actions
in the last 24 hours) and, for MellowTech staff, a view of Autopilot activity across all customers.
Autopilot actions are also printed in the server window.

Put this file in the MELLOWTECH folder (next to index.html) and run:
    python apply_autopilot_status.py
Run apply_autopilot.py first. Backups are saved next to each changed file as *.bak
"""
import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent

PY_REPLACEMENTS = [
    ('''    db.execute("CREATE TABLE IF NOT EXISTS autopilot_log (id INTEGER PRIMARY KEY AUTOINCREMENT, org_id INTEGER NOT NULL, "
               "ts TEXT NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL)")
''',
     '''    db.execute("CREATE TABLE IF NOT EXISTS autopilot_log (id INTEGER PRIMARY KEY AUTOINCREMENT, org_id INTEGER NOT NULL, "
               "ts TEXT NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS autopilot_state (org_id INTEGER PRIMARY KEY, last_run TEXT NOT NULL)")
'''),

    ('''               (org_id, _deps["iso"](_deps["utcnow"]()), action, detail[:300]))
''',
     '''               (org_id, _deps["iso"](_deps["utcnow"]()), action, detail[:300]))
    print(f"Autopilot: {action}: {detail}", flush=True)
'''),

    ('''        ensure_tables(db)
        if is_on(db, org_id, "block_attackers"):
''',
     '''        ensure_tables(db)
        db.execute("INSERT INTO autopilot_state (org_id, last_run) VALUES (?,?) "
                   "ON CONFLICT(org_id) DO UPDATE SET last_run = excluded.last_run",
                   (org_id, _deps["iso"](_deps["utcnow"]())))
        if is_on(db, org_id, "block_attackers"):
'''),

    ('''        log = db.execute("SELECT ts, action, detail FROM autopilot_log WHERE org_id = ? ORDER BY id DESC LIMIT 40",
                         (org_id,)).fetchall()
        return jsonify({"allowed": feature_allowed(org_id, "autopilot"),
''',
     '''        log = db.execute("SELECT ts, action, detail FROM autopilot_log WHERE org_id = ? ORDER BY id DESC LIMIT 40",
                         (org_id,)).fetchall()
        state = db.execute("SELECT last_run FROM autopilot_state WHERE org_id = ?", (org_id,)).fetchone()
        day_ago = iso(utcnow() - timedelta(hours=24))
        actions = db.execute("SELECT COUNT(*) FROM autopilot_log WHERE org_id = ? AND ts >= ?", (org_id, day_ago)).fetchone()[0]
        online = db.execute("SELECT COUNT(*) FROM devices WHERE org_id = ? AND last_seen >= ?",
                            (org_id, iso(utcnow() - timedelta(seconds=60)))).fetchone()[0]
        total = db.execute("SELECT COUNT(*) FROM devices WHERE org_id = ?", (org_id,)).fetchone()[0]
        return jsonify({"allowed": feature_allowed(org_id, "autopilot"),
                        "last_run": state["last_run"] if state else None, "actions_24h": actions,
                        "laptops_online": online, "laptops_total": total,
'''),

    ('''        audit("autopilot_setting", f"{key} {'on' if data['enabled'] else 'off'}")
        return jsonify({"ok": True})
''',
     '''        audit("autopilot_setting", f"{key} {'on' if data['enabled'] else 'off'}")
        return jsonify({"ok": True})

    @app.get("/api/autopilot/all")
    @login_required("platform_admin")
    def autopilot_all():
        db = get_db()
        ensure_tables(db)
        rows = db.execute("SELECT l.ts, l.action, l.detail, o.name AS company FROM autopilot_log l "
                          "JOIN organisations o ON o.id = l.org_id ORDER BY l.id DESC LIMIT 100").fetchall()
        active = db.execute("SELECT COUNT(*) FROM autopilot_state WHERE last_run >= ?",
                            (iso(utcnow() - timedelta(minutes=5)),)).fetchone()[0]
        actions = db.execute("SELECT COUNT(*) FROM autopilot_log WHERE ts >= ?",
                             (iso(utcnow() - timedelta(hours=24)),)).fetchone()[0]
        return jsonify({"companies_active": active, "actions_24h": actions, "log": [dict(r) for r in rows]})
'''),
]

PANELS = '''<div id="ap-message" class="result-message" role="status" aria-live="polite"></div>

            <div class="panel" id="ap-status">
                <h3>Status</h3>
                <div id="ap-status-body">Loading...</div>
            </div>

            <div class="panel" id="ap-owner" hidden>
                <h3>All customers (MellowTech staff only)</h3>
                <div id="ap-owner-summary"></div>
                <div class="table-scroll">
                    <table class="events-table">
                        <caption class="sr-only">Autopilot activity across all customers</caption>
                        <thead><tr><th scope="col">Time</th><th scope="col">Company</th><th scope="col">Action</th><th scope="col">Details</th></tr></thead>
                        <tbody id="ap-owner-log"></tbody>
                    </table>
                </div>
            </div>'''

SCRIPT = r'''<!-- Autopilot -->
    <script>
    (function () {
        var csrf = "";
        var me = null;

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

        function ago(seconds) {
            if (seconds < 90) { return Math.max(0, seconds) + " seconds ago"; }
            if (seconds < 5400) { return Math.round(seconds / 60) + " minutes ago"; }
            return Math.round(seconds / 3600) + " hours ago";
        }

        function row(label, value) {
            return '<div class="status-item"><span>' + esc(label) + "</span><strong>" + esc(value) + "</strong></div>";
        }

        function renderStatus(d) {
            var checked = d.last_run ? new Date(d.last_run) : null;
            var age = checked ? Math.round((Date.now() - checked.getTime()) / 1000) : null;
            var colour = "#c47b00", text;
            if (!d.allowed) { text = "Autopilot is switched off for your plan. Unlock it so the software can fix problems by itself."; }
            else if (!d.laptops_total) { text = "No laptop is connected yet. Autopilot starts as soon as one is."; }
            else if (age === null) { text = "Waiting for the first check-in from a connected laptop."; }
            else if (age <= 180) { colour = "#12906e"; text = "Autopilot is running."; }
            else { text = "Autopilot is waiting: no laptop has checked in for " + Math.round(age / 60) + " minute(s)."; }
            $("ap-status-body").innerHTML = '<p style="font-size:18px;margin:0 0 8px"><span style="color:' + colour + '">&#9679;</span> <b>' + esc(text) + "</b></p>" +
                row("Last check", checked ? checked.toLocaleTimeString() + " (" + ago(age) + ")" : "Not yet") +
                row("Laptops online", d.laptops_online + " of " + d.laptops_total) +
                row("Actions in the last 24 hours", d.actions_24h);
        }

        function loadOwner() {
            api("/api/autopilot/all").then(function (d) {
                $("ap-owner").hidden = false;
                $("ap-owner-summary").innerHTML = row("Customers with Autopilot active (last 5 minutes)", d.companies_active) +
                    row("Actions across all customers (24 hours)", d.actions_24h);
                $("ap-owner-log").innerHTML = d.log.length ? d.log.map(function (l) {
                    return "<tr><td>" + esc(new Date(l.ts).toLocaleString()) + "</td><td>" + esc(l.company) + "</td><td><b>" + esc(l.action) + "</b></td><td>" + esc(l.detail) + "</td></tr>";
                }).join("") : '<tr><td colspan="4">Nothing yet.</td></tr>';
            }).catch(function () {});
        }

        function load() {
            api("/api/autopilot").then(function (data) {
                $("ap-lock").hidden = data.allowed;
                renderStatus(data);
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
            if (me && me.is_platform && me.role === "admin") { loadOwner(); }
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
            api("/api/auth/me").then(function (data) { csrf = data.csrf; me = data.user; load(); }).catch(function () {});
            var nav = document.querySelector('.nav-button[data-page="autopilot"]');
            if (nav) { nav.addEventListener("click", load); }
            $("ap-unlock").addEventListener("click", openBilling);
            setInterval(function () { if (!$("autopilot").hidden) { load(); } }, 15000);
        });
    })();
    </script>
'''

MARKER_PY = "autopilot_state"
MARKER_HTML = 'id="ap-status"'
OLD_SCRIPT = r"<!-- Autopilot -->\s*<script>.*?</script>\s*"
ANCHOR = '<div id="ap-message" class="result-message" role="status" aria-live="polite"></div>'


def patch_py(path):
    text = path.read_text(encoding="utf-8")
    if MARKER_PY in text:
        return "already updated"
    for old, new in PY_REPLACEMENTS:
        count = text.count(old)
        if count != 1:
            return f"NOT changed: could not find a unique match for {old.strip()[:50]!r} (found {count})"
        text = text.replace(old, new, 1)
    shutil.copy2(path, str(path) + ".bak")
    path.write_text(text, encoding="utf-8")
    return "updated"


def patch_html(path):
    text = path.read_text(encoding="utf-8")
    if MARKER_HTML in text:
        return "already updated"
    if text.count(ANCHOR) != 1 or len(re.findall(OLD_SCRIPT, text, re.S)) != 1:
        return "NOT changed: run apply_autopilot.py first"
    text = text.replace(ANCHOR, PANELS, 1)
    text = re.sub(OLD_SCRIPT, lambda m: SCRIPT.rstrip() + "\n    ", text, count=1, flags=re.S)
    shutil.copy2(path, str(path) + ".bak")
    path.write_text(text, encoding="utf-8")
    return "updated"


def main():
    for folder in (HERE / "backend", HERE / "aws-deploy"):
        target = folder / "autopilot.py"
        if target.is_file():
            print(f"{folder.name}\\autopilot.py: {patch_py(target)}")
    for path in (HERE / "index.html", HERE / "aws-deploy" / "index.html"):
        if path.is_file():
            print(f"{path.relative_to(HERE)}: {patch_html(path)}")
    print("\nDone. Restart python app.py, then refresh the browser with Ctrl+Shift+R.")


if __name__ == "__main__":
    main()