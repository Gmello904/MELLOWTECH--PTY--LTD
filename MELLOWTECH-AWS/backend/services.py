"""MellowTech security services: quick self-checks, help requests and incident reports.

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
    feature_allowed, service_plans, plan_info = deps["feature_allowed"], deps["service_plans"], deps["plan_info"]

    def package_lock(key):
        """A 402 reply when the company's plan does not include this service, else None. MellowTech staff are never locked."""
        need = service_plans.get(key)
        if not need or feature_allowed(g.user["org_id"], "svc_" + key):
            return None
        name = plan_info.get(need, {}).get("name", need.title())
        audit("feature_locked", f"{g.user['org_name']} ({g.user['email']}) tried the {by_key[key]['name']} service; it needs {name}")
        return jsonify({"error": f"{by_key[key]['name']} is part of {name}. Pay for that package in Billing & Plans to unlock it.",
                        "locked": True, "needs": need}), 402
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
                         "last": last.get(s["key"]),
                         "needs": service_plans.get(s["key"], ""),
                         "package": plan_info.get(service_plans.get(s["key"], ""), {}).get("name", ""),
                         "price": plan_info.get(service_plans.get(s["key"], ""), {}).get("price", ""),
                         "unlocked": feature_allowed(g.user["org_id"], "svc_" + s["key"]) if s["key"] in service_plans else True}
                        for s in SERVICES])

    @app.post("/api/services/check")
    @login_required()
    def services_check():
        data = request.get_json(silent=True) or {}
        service = by_key.get(data.get("service"))
        if not service:
            return error("Unknown service.", 400)
        denied = package_lock(service["key"])
        if denied:
            return denied
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
        if not urgent:                       # an urgent incident report is always allowed, even on the Free plan
            denied = package_lock(service["key"])
            if denied:
                return denied
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
