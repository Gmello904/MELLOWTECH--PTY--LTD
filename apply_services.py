"""Part 1b: turns Security Roles into Security Services with real buttons.

Each service gets: Run security check (questionnaire with a score and a fix list) and Request help (sent to MellowTech).
Security Monitoring also gets Open live alerts, and Incident Response gets Report an incident.

Put this file in the MELLOWTECH folder (next to index.html) and run:
    python apply_services.py
Run apply_features.py first. Backups are saved next to each changed file as *.bak
"""
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent

SERVICES_PY = r'''"""MellowTech security services: quick self-checks, help requests and incident reports.

Each service matches a cybersecurity role. A check is a short yes/no questionnaire that scores the company and
lists what to fix. It is practical guidance, not a formal audit and not legal advice.
"""
from datetime import datetime

from flask import g, jsonify, request

SERVICES = [
    {"key": "ai_security", "name": "AI Security", "role": "AI Security Engineer", "extra": None,
     "blurb": "Protect AI models and applications against attacks, test them for weaknesses and protect the data they use.",
     "questions": [
         ("Do you test your AI chatbot or app against prompt injection (tricking it into ignoring its rules)?",
          "Test with hostile prompts before launch and after every change, and keep the AI's instructions separate from user input."),
         ("Is personal or confidential data kept out of AI prompts, training data and logs unless it is really needed?",
          "Remove or mask personal and confidential data before it reaches an AI tool, and set limits on how long it is kept."),
         ("Do you control who can use your AI models and API keys, with sign-in and usage limits?",
          "Use named accounts, store keys in a secrets manager, rotate them regularly and set spending and usage limits."),
         ("Does a person approve AI output before it moves money, deletes data or does anything risky?",
          "Add human approval for high-impact actions and limit what AI agents are allowed to do."),
         ("Do you keep records of what your AI systems were asked and what they did?",
          "Log requests, answers and tool actions so misuse can be investigated."),
         ("Do you check outside AI models, plugins and datasets before using them?",
          "Use trusted sources and scan downloads. An unchecked model or plugin can hide malicious code."),
     ]},
    {"key": "incident_response", "name": "Incident Response", "role": "Incident Response Analyst", "extra": "incident",
     "blurb": "Investigate confirmed attacks, contain the damage, examine the evidence and recover securely.",
     "questions": [
         ("Do you have a written incident response plan that says who does what?",
          "Write a one-page plan with names, phone numbers and the first steps to take."),
         ("Do you know exactly who to call first (your lead, IT provider, insurer, lawyer)?",
          "Keep an emergency contact list printed and stored somewhere an attack cannot reach."),
         ("Are your backups tested, and kept where an attacker cannot delete them?",
          "Keep offline or locked (immutable) backups and test a full restore every quarter."),
         ("Do you keep security logs (sign-ins, firewall, servers) for at least 90 days?",
          "Switch on logging and keep logs in a central place so the evidence survives an attack."),
         ("Do your staff know how to report a suspected attack straight away?",
          "Give staff one phone number or email for reporting, and practise it."),
         ("Do you know how to report a data breach to the Information Regulator and the people affected (POPIA)?",
          "Under POPIA a compromise of personal information must be reported as soon as reasonably possible. Write down your process and get legal advice."),
     ]},
    {"key": "cloud_security", "name": "Cloud Security", "role": "Cloud Security Engineer", "extra": None,
     "blurb": "Protect data, applications and systems in the cloud, secure AWS and Azure, and control who can reach what.",
     "questions": [
         ("Is multi-factor authentication (MFA) on for every cloud admin account, including the owner or root account?",
          "Turn on MFA for every cloud admin account today, starting with the owner or root account."),
         ("Does each person have only the access they need, and is that reviewed regularly?",
          "Apply least privilege: remove unused accounts and broad admin rights, and review access every quarter."),
         ("Have you checked that no storage, database or server is open to the whole internet by mistake?",
          "Review public access settings and security groups, and close anything that does not have to be public."),
         ("Is activity logging switched on and kept (for example CloudTrail or the Azure Activity Log)?",
          "Turn on cloud audit logging in every account and region, and keep the logs safe."),
         ("Is your cloud data encrypted, both when stored and when moving?",
          "Enable encryption at rest and require HTTPS/TLS for all traffic."),
         ("Are access keys and passwords kept out of code and rotated regularly?",
          "Move secrets into a secrets manager, remove them from code repositories and rotate any that were exposed."),
     ]},
    {"key": "soc_monitoring", "name": "Security Monitoring (SOC)", "role": "SOC Analyst", "extra": "alerts",
     "blurb": "Watch your systems for threats, investigate suspicious activity and alerts, and stop attacks early.",
     "questions": [
         ("Are logs from laptops, servers, firewalls and cloud services collected in one place?",
          "Collect logs centrally so one person can search across all of them."),
         ("Does someone look at security alerts every day, and is there a plan for after hours?",
          "Name who checks alerts each day and who is on call after hours."),
         ("Have you defined what counts as high, medium and low severity, and how fast each must be handled?",
          "Write a short table: for example high within 1 hour, medium within 1 day, low within 1 week."),
         ("Do all your laptops run endpoint protection that reports back to a central place?",
          "Connect every laptop to MellowTech so its protection state and alerts are visible."),
         ("Do you get an alert when someone fails to sign in again and again?",
          "Turn on alerts and automatic lockout for repeated failed sign-ins."),
         ("Do you review blocked addresses and false alarms to improve your alerts?",
          "Review blocks and false alarms monthly, then tune the rules to cut noise."),
     ]},
    {"key": "grc_compliance", "name": "Compliance and Risk (GRC)", "role": "GRC Analyst", "extra": None,
     "blurb": "Create security policies, assess cyber risk and make sure you follow the laws and standards that apply to you.",
     "questions": [
         ("Do you have written security and acceptable-use policies that staff have read and signed?",
          "Write short policies in plain language and have every staff member sign them."),
         ("Do you keep a list of the personal information you hold and where it is stored?",
          "Build a simple register of personal data: what it is, where it lives, who can see it and why you hold it."),
         ("Have you appointed an Information Officer and registered them with the Information Regulator?",
          "Under POPIA a business needs an Information Officer. Appoint one and register them with the Information Regulator."),
         ("Do you assess your cyber risks at least once a year and write down the results?",
          "Run a yearly risk review: list what could go wrong, how likely it is, how bad it would be and what you will do."),
         ("Do you check that suppliers who handle your data have proper security?",
          "Ask suppliers for security evidence and put data protection terms in your contracts."),
         ("Do your staff get security awareness training at least once a year?",
          "Run a short yearly training and test staff with simulated phishing emails."),
     ]},
]


def init_services(app, deps):
    get_db, error, iso, utcnow = deps["get_db"], deps["error"], deps["iso"], deps["utcnow"]
    login_required, audit, too_many = deps["login_required"], deps["audit"], deps["too_many"]
    locked, notify_staff = deps["locked"], deps["notify_staff"]
    by_key = {s["key"]: s for s in SERVICES}

    def ensure_tables(db):
        db.execute("CREATE TABLE IF NOT EXISTS service_checks (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                   "org_id INTEGER NOT NULL, user_id INTEGER NOT NULL, service TEXT NOT NULL, "
                   "score INTEGER NOT NULL, created_at TEXT NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS service_requests (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                   "org_id INTEGER NOT NULL, user_id INTEGER NOT NULL, service TEXT NOT NULL, note TEXT, "
                   "urgent INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'new', created_at TEXT NOT NULL)")

    @app.get("/api/services")
    @login_required()
    def services_list():
        db = get_db()
        ensure_tables(db)
        last = {}
        for row in db.execute("SELECT service, score, created_at FROM service_checks WHERE org_id = ? ORDER BY id DESC",
                              (g.user["org_id"],)):
            last.setdefault(row["service"], {"score": row["score"], "at": row["created_at"]})
        return jsonify([{"key": s["key"], "name": s["name"], "role": s["role"], "blurb": s["blurb"],
                         "extra": s["extra"], "questions": [q for q, _ in s["questions"]],
                         "last": last.get(s["key"])} for s in SERVICES])

    @app.post("/api/services/check")
    @login_required()
    def services_check():
        data = request.get_json(silent=True) or {}
        service = by_key.get(data.get("service"))
        if not service:
            return error("Unknown service.", 400)
        answers = data.get("answers")
        if (not isinstance(answers, list) or len(answers) != len(service["questions"])
                or any(a not in ("yes", "no", "unsure") for a in answers)):
            return error("Please answer every question.", 400)
        if too_many("svccheck:" + str(g.user["id"]), 30, 3600):
            return error("Too many checks. Try again later.", 429)

        score = round(100 * sum(1 for a in answers if a == "yes") / len(answers))
        gaps = [{"question": q, "fix": fix, "answer": a}
                for (q, fix), a in zip(service["questions"], answers) if a != "yes"]
        level, text = (("low", "Good") if score >= 80 else ("medium", "Needs work") if score >= 50 else ("high", "At risk"))
        db = get_db()
        ensure_tables(db)
        db.execute("INSERT INTO service_checks (org_id,user_id,service,score,created_at) VALUES (?,?,?,?,?)",
                   (g.user["org_id"], g.user["id"], service["key"], score, iso(utcnow())))
        db.commit()
        audit("service_check", f"{service['name']} {score}%")
        return jsonify({"service": service["name"], "score": score, "level": level, "verdict": text, "gaps": gaps})

    @app.post("/api/services/request")
    @login_required()
    def services_request():
        data = request.get_json(silent=True) or {}
        service = by_key.get(data.get("service"))
        if not service:
            return error("Unknown service.", 400)
        urgent = service["key"] == "incident_response" and bool(data.get("urgent"))
        if not urgent:                       # an urgent incident report is never held back by a plan
            denied = locked("service_request")
            if denied:
                return denied
        if too_many("svcreq:" + str(g.user["id"]), 10, 3600):
            return error("Too many requests. Try again later.", 429)
        note = str(data.get("note", "")).strip()[:500]
        if urgent and len(note) < 5:
            return error("Please describe what happened in a few words.", 400)

        db = get_db()
        ensure_tables(db)
        db.execute("INSERT INTO service_requests (org_id,user_id,service,note,urgent,created_at) VALUES (?,?,?,?,?,?)",
                   (g.user["org_id"], g.user["id"], service["key"], note, 1 if urgent else 0, iso(utcnow())))
        if urgent:                           # also show it as a High alert on the customer's own dashboard
            cursor = db.execute(
                "INSERT INTO security_events (event_id,event_type,device,severity,status,description,timestamp,org_id) "
                "VALUES ('PENDING',?,?,?,?,?,?,?)",
                ("Incident reported by a user", ("Reported by " + str(g.user["name"]))[:100], "High", "New",
                 note, datetime.now().isoformat(), g.user["org_id"]))
            db.execute("UPDATE security_events SET event_id = ? WHERE id = ?",
                       (f"EVT-{cursor.lastrowid:03d}", cursor.lastrowid))
        db.commit()
        audit("service_request", f"{service['name']}{' (URGENT)' if urgent else ''}")
        notify_staff(("URGENT incident report: " if urgent else "New service request: ") + service["name"],
                     f"{g.user['name']} <{g.user['email']}> from {g.user['org_name']} asked for help with "
                     f"{service['name']}.\n\n{note or '(no message)'}\n\nOpen the dashboard, Security Services page.")
        return jsonify({"ok": True, "urgent": urgent}), 201

    @app.get("/api/services/requests")
    @login_required("platform_admin")
    def services_requests():
        db = get_db()
        ensure_tables(db)
        rows = db.execute(
            "SELECT r.id, r.service, r.note, r.urgent, r.status, r.created_at, o.name AS company, "
            "u.name AS person, u.email FROM service_requests r JOIN organisations o ON o.id = r.org_id "
            "JOIN users u ON u.id = r.user_id ORDER BY (r.status = 'done'), r.urgent DESC, r.id DESC LIMIT 100").fetchall()
        return jsonify([{"id": r["id"], "service": by_key.get(r["service"], {}).get("name", r["service"]),
                         "note": r["note"], "urgent": bool(r["urgent"]), "status": r["status"], "at": r["created_at"],
                         "company": r["company"], "person": r["person"], "email": r["email"]} for r in rows])

    @app.post("/api/services/requests/<int:request_id>/status")
    @login_required("platform_admin")
    def services_request_status(request_id):
        status = (request.get_json(silent=True) or {}).get("status")
        if status not in ("new", "in_progress", "done"):
            return error("Invalid status.", 400)
        db = get_db()
        ensure_tables(db)
        cursor = db.execute("UPDATE service_requests SET status = ? WHERE id = ?", (status, request_id))
        db.commit()
        if cursor.rowcount == 0:
            return error("Request not found.", 404)
        audit("service_request_" + status, str(request_id))
        return jsonify({"ok": True})
'''

APP_REPLACEMENTS = [
    ("import docscan\n",
     "import docscan\nimport services\n"),

    ('    "device_command": ("business", "Device isolation, virus scans and USB control"),\n',
     '    "device_command": ("business", "Device isolation, virus scans and USB control"),\n'
     '    "service_request": ("starter", "Security service requests"),\n'),

    ("    login_required=login_required, audit=audit, too_many=too_many, locked=locked))\n",
     "    login_required=login_required, audit=audit, too_many=too_many, locked=locked))\n"
     "services.init_services(app, dict(\n"
     "    get_db=get_db, error=error, iso=iso, utcnow=utcnow,\n"
     "    login_required=login_required, audit=audit, too_many=too_many, locked=locked, notify_staff=notify_staff))\n"),
]

PANELS = '''<div class="rl-grid" id="roles-grid"></div>
            <div id="svc-message" class="result-message" role="status" aria-live="polite"></div>
            <div id="svc-panel"></div>
            <div class="panel" id="svc-requests-panel" hidden>
                <h3>Service requests from customers</h3>
                <p class="page-description" style="margin-top:4px">Urgent incident reports are listed first.</p>
                <div class="table-scroll">
                    <table class="events-table">
                        <caption class="sr-only">Customer service requests</caption>
                        <thead><tr><th scope="col">Time</th><th scope="col">Company</th><th scope="col">Person</th><th scope="col">Service</th><th scope="col">Message</th><th scope="col">Status</th><th scope="col">Action</th></tr></thead>
                        <tbody id="svc-requests-body"></tbody>
                    </table>
                </div>
            </div>'''

SCRIPT = r'''<!-- Security Services (checks, help requests, incident reports) -->
    <script>
    (function () {
        var csrf = "";
        var me = null;
        var services = [];

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

        function openPage(page) {
            var button = document.querySelector('.nav-button[data-page="' + page + '"]');
            if (button) { button.click(); }
        }

        function say(text, kind, withUnlock) {
            var box = $("svc-message");
            box.textContent = text || "";
            box.style.color = kind === "err" ? "#b42318" : kind === "ok" ? "#12906e" : "";
            if (text && withUnlock) {
                var unlock = document.createElement("button");
                unlock.type = "button";
                unlock.className = "btn-small";
                unlock.style.marginLeft = "12px";
                unlock.textContent = "Unlock with a plan";
                unlock.addEventListener("click", function () { openPage("billing"); });
                box.appendChild(unlock);
            }
        }

        function find(key) {
            return services.filter(function (s) { return s.key === key; })[0];
        }

        function drawServices() {
            $("roles-grid").innerHTML = services.map(function (s) {
                var last = s.last
                    ? '<p class="rl-skills">Last check: <b>' + esc(s.last.score) + "%</b> on " + esc(new Date(s.last.at).toLocaleDateString()) + "</p>"
                    : '<p class="rl-skills">Not checked yet.</p>';
                var extra = s.extra === "alerts"
                    ? '<button type="button" class="btn-small" data-svc-open="threats">Open live alerts</button>'
                    : s.extra === "incident"
                        ? '<button type="button" class="btn-small btn-danger" data-svc-incident="1">Report an incident</button>'
                        : "";
                return '<div class="panel rl-card"><h3>' + esc(s.name) + '</h3><p class="rl-skills">' + esc(s.role) + "</p><p>" +
                    esc(s.blurb) + "</p>" + last + '<div class="actions" style="margin-top:12px">' +
                    '<button type="button" class="btn-small" data-svc-check="' + esc(s.key) + '">Run security check</button>' +
                    '<button type="button" class="btn-small" data-svc-request="' + esc(s.key) + '">Request help</button>' +
                    extra + "</div></div>";
            }).join("");
        }

        function loadServices() {
            api("/api/services").then(function (list) {
                services = list;
                drawServices();
            }).catch(function (problem) {
                $("roles-grid").textContent = problem.message;
            });
        }

        function loadRequests() {
            api("/api/services/requests").then(function (rows) {
                $("svc-requests-panel").hidden = false;
                $("svc-requests-body").innerHTML = rows.length ? rows.map(function (r) {
                    var done = r.status === "done";
                    return "<tr><td>" + esc(new Date(r.at).toLocaleString()) + "</td><td>" + esc(r.company) + "</td><td>" +
                        esc(r.person) + " (" + esc(r.email) + ")</td><td>" + (r.urgent ? '<span class="badge danger">URGENT</span> ' : "") +
                        esc(r.service) + "</td><td>" + esc(r.note || "") + "</td><td>" + esc(r.status.replace("_", " ")) + "</td><td>" +
                        (done ? "" : '<button type="button" class="btn-small" data-svc-done="' + esc(r.id) + '">Mark done</button>') +
                        "</td></tr>";
                }).join("") : '<tr><td colspan="7">No requests yet.</td></tr>';
            }).catch(function () {});
        }

        function openCheck(key) {
            var s = find(key);
            if (!s) { return; }
            var html = '<div class="panel"><div class="panel-header"><div><h3>' + esc(s.name) + ' security check</h3>' +
                "<p>Answer honestly. This is practical guidance, not a formal audit.</p></div></div>";
            s.questions.forEach(function (q, i) {
                html += '<div class="status-item" style="align-items:flex-start;gap:16px"><span style="flex:1">' + esc(q) + "</span><span>" +
                    [["yes", "Yes"], ["no", "No"], ["unsure", "Not sure"]].map(function (o) {
                        return '<label style="margin-left:12px;white-space:nowrap"><input type="radio" name="svcq' + i + '" value="' + o[0] + '"> ' + o[1] + "</label>";
                    }).join("") + "</span></div>";
            });
            html += '<div class="actions" style="margin-top:14px"><button type="button" class="btn-small" data-svc-submit="' + esc(key) +
                '">See my result</button></div><div id="svc-result"></div></div>';
            $("svc-panel").innerHTML = html;
            $("svc-panel").scrollIntoView({ behavior: "smooth", block: "start" });
        }

        function submitCheck(key) {
            var s = find(key);
            var answers = [];
            for (var i = 0; i < s.questions.length; i++) {
                var chosen = document.querySelector('input[name="svcq' + i + '"]:checked');
                if (!chosen) { say("Answer every question first.", "err"); return; }
                answers.push(chosen.value);
            }
            say("", "");
            api("/api/services/check", { service: key, answers: answers }).then(function (r) {
                var colour = r.level === "high" ? "#b42318" : r.level === "medium" ? "#c47b00" : "#12906e";
                var html = '<h3 style="margin-top:18px">Your result: <span style="color:' + colour + '">' + esc(r.score) + "% (" + esc(r.verdict) + ")</span></h3>";
                if (r.gaps.length) {
                    html += "<p>Fix these first:</p><ul style=\"margin:8px 0 0;padding-left:20px;display:grid;gap:10px\">" +
                        r.gaps.map(function (g) {
                            return "<li><b>" + esc(g.question) + "</b><br>" + esc(g.fix) + "</li>";
                        }).join("") + "</ul>" +
                        '<div class="actions" style="margin-top:14px"><button type="button" class="btn-small" data-svc-request="' + esc(key) + '">Ask MellowTech to help with these</button></div>';
                } else {
                    html += "<p>Well done: every answer was Yes. Re-check regularly, because things change.</p>";
                }
                $("svc-result").innerHTML = html;
                loadServices();
            }).catch(function (problem) { say(problem.message, "err"); });
        }

        function sendRequest(key, urgent) {
            var s = find(key);
            var note = window.prompt(urgent
                ? "Describe what happened, in a few words.\n\nIf you can, disconnect the affected devices from the network. This sends an URGENT alert to MellowTech."
                : "How can MellowTech help with " + s.name + "? (optional)", "");
            if (note === null) { return; }
            api("/api/services/request", { service: key, note: note, urgent: !!urgent }).then(function () {
                say(urgent ? "Incident reported. MellowTech has been alerted and a High alert was added to your dashboard."
                           : "Request sent. MellowTech will contact you.", "ok");
                if (urgent && typeof loadSecurityEvents === "function") { loadSecurityEvents(); }
                if (me && me.is_platform && me.role === "admin") { loadRequests(); }
            }).catch(function (problem) { say(problem.message, "err", problem.locked); });
        }

        document.addEventListener("click", function (event) {
            var t = event.target.closest("[data-svc-check],[data-svc-request],[data-svc-submit],[data-svc-open],[data-svc-incident],[data-svc-done]");
            if (!t) { return; }
            var d = t.dataset;
            if (d.svcCheck) { openCheck(d.svcCheck); }
            else if (d.svcSubmit) { submitCheck(d.svcSubmit); }
            else if (d.svcRequest) { sendRequest(d.svcRequest, false); }
            else if (d.svcIncident) { sendRequest("incident_response", true); }
            else if (d.svcOpen) { openPage(d.svcOpen); }
            else if (d.svcDone) {
                api("/api/services/requests/" + encodeURIComponent(d.svcDone) + "/status", { status: "done" })
                    .then(loadRequests).catch(function (problem) { say(problem.message, "err"); });
            }
        });

        document.addEventListener("DOMContentLoaded", function () {
            $("roles-grid").textContent = "Loading...";
            api("/api/auth/me").then(function (data) {
                csrf = data.csrf;
                me = data.user;
                loadServices();
                if (me.is_platform && me.role === "admin") { loadRequests(); }
            }).catch(function () {});
            var nav = document.querySelector('.nav-button[data-page="roles"]');
            if (nav) {
                nav.addEventListener("click", function () {
                    loadServices();
                    if (me && me.is_platform && me.role === "admin") { loadRequests(); }
                });
            }
        });
    })();
    </script>
'''

INDEX_MARKER = 'id="svc-panel"'

INDEX_REPLACEMENTS = [
    ("</svg>Security Roles", "</svg>Security Services"),
    ("<h2>Security Roles</h2>", "<h2>Security Services</h2>"),
    ('<p class="page-description">The cybersecurity roles that keep organisations safe.</p>',
     '<p class="page-description">Run a quick security check, ask MellowTech for help, or report an incident.</p>'),
    ('<div class="rl-grid" id="roles-grid"></div>', PANELS),
    ("</body>", SCRIPT + "</body>"),
]


def apply(path, replacements, marker):
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return "already updated"
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
        if "FEATURE_PLANS" not in app_file.read_text(encoding="utf-8"):
            print(f"{folder.name}\\app.py: NOT changed: run apply_features.py first")
            continue
        (folder / "services.py").write_text(SERVICES_PY, encoding="utf-8")
        print(f"{folder.name}\\services.py: written")
        print(f"{folder.name}\\app.py: {apply(app_file, APP_REPLACEMENTS, 'import services')}")
    for path in (HERE / "index.html", HERE / "aws-deploy" / "index.html"):
        if path.is_file():
            print(f"{path.relative_to(HERE)}: {apply(path, INDEX_REPLACEMENTS, INDEX_MARKER)}")
    print("\nDone. Restart python app.py and refresh the browser with Ctrl+Shift+R.")


if __name__ == "__main__":
    main()