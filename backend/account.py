"""MellowTech account settings: profile, password change, signed-in devices and the activity log."""
import secrets
from datetime import timedelta

from flask import g, jsonify, request, session
from werkzeug.security import check_password_hash

_deps = {}
_ready = {"done": False}
TOUCH_SECONDS = 60


def ensure_tables(db):
    if _ready["done"]:
        return
    db.execute("CREATE TABLE IF NOT EXISTS user_sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, "
               "sid TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL, last_seen TEXT NOT NULL, ip TEXT, agent TEXT, "
               "revoked INTEGER NOT NULL DEFAULT 0)")
    db.commit()
    _ready["done"] = True


def describe_agent(agent):
    text = agent or ""
    browser = ("Edge" if "Edg/" in text else "Opera" if "OPR/" in text else "Chrome" if "Chrome/" in text
               else "Firefox" if "Firefox/" in text else "Safari" if "Safari/" in text else "Browser")
    system = ("Windows" if "Windows" in text else "Android" if "Android" in text else "iPhone" if "iPhone" in text
              else "iPad" if "iPad" in text else "Mac" if "Mac OS X" in text else "Linux" if "Linux" in text else "unknown system")
    return f"{browser} on {system}"


def new_session(user_id):
    """Called after a successful sign-in: records this browser so it can be listed and signed out later."""
    db = _deps["get_db"]()
    ensure_tables(db)
    now = _deps["iso"](_deps["utcnow"]())
    db.execute("DELETE FROM user_sessions WHERE created_at < ?", (_deps["iso"](_deps["utcnow"]() - timedelta(days=30)),))
    sid = secrets.token_urlsafe(24)
    db.execute("INSERT INTO user_sessions (user_id,sid,created_at,last_seen,ip,agent) VALUES (?,?,?,?,?,?)",
               (user_id, sid, now, now, request.remote_addr, (request.headers.get("User-Agent") or "")[:200]))
    db.commit()
    session["sid"] = sid


def end_session():
    sid = session.get("sid")
    if sid and _deps:
        db = _deps["get_db"]()
        ensure_tables(db)
        db.execute("UPDATE user_sessions SET revoked = 1 WHERE sid = ?", (sid,))
        db.commit()


def session_ok(user_id, idle_seconds=None):
    """False when this browser's session was signed out from the Settings page, or sat idle longer than the company allows."""
    sid = session.get("sid")
    if not sid or not _deps:
        return True                      # signed in before this feature existed
    db = _deps["get_db"]()
    ensure_tables(db)
    row = db.execute("SELECT revoked, last_seen FROM user_sessions WHERE sid = ? AND user_id = ?", (sid, user_id)).fetchone()
    if not row or row["revoked"]:
        return False
    now = _deps["utcnow"]()
    if idle_seconds and row["last_seen"] < _deps["iso"](now - timedelta(seconds=idle_seconds)):
        db.execute("UPDATE user_sessions SET revoked = 1 WHERE sid = ?", (sid,))
        db.commit()
        return False
    if row["last_seen"] < _deps["iso"](now - timedelta(seconds=TOUCH_SECONDS)):
        db.execute("UPDATE user_sessions SET last_seen = ?, ip = ? WHERE sid = ?", (_deps["iso"](now), request.remote_addr, sid))
        db.commit()
    return True


def init_account(app, deps):
    _deps.update(deps)
    get_db, error, iso, utcnow = deps["get_db"], deps["error"], deps["iso"], deps["utcnow"]
    login_required, audit, too_many = deps["login_required"], deps["audit"], deps["too_many"]
    password_problem, hash_password, send_email = deps["password_problem"], deps["hash_password"], deps["send_email"]

    @app.get("/api/account")
    @login_required()
    def account_profile():
        row = get_db().execute("SELECT name, email, role, created_at, last_login FROM users WHERE id = ?",
                               (g.user["id"],)).fetchone()
        return jsonify({"name": row["name"], "email": row["email"], "role": row["role"], "org": g.user["org_name"],
                        "created_at": row["created_at"], "last_login": row["last_login"]})

    @app.post("/api/account/profile")
    @login_required()
    def account_update_profile():
        name = str((request.get_json(silent=True) or {}).get("name", "")).strip()
        if not 2 <= len(name) <= 120:
            return error("Your name must be between 2 and 120 characters.", 400)
        db = get_db()
        db.execute("UPDATE users SET name = ? WHERE id = ?", (name, g.user["id"]))
        db.commit()
        audit("profile_changed", "name", g.user["id"])
        return jsonify({"ok": True, "name": name})

    @app.post("/api/account/password")
    @login_required()
    def account_change_password():
        data = request.get_json(silent=True) or {}
        current, new = str(data.get("current", ""))[:256], str(data.get("new", ""))
        uid = g.user["id"]
        if too_many("pwchange:" + str(uid), 5, 900):
            return error("Too many attempts. Try again in a few minutes.", 429)
        db = get_db()
        row = db.execute("SELECT password_hash FROM users WHERE id = ?", (uid,)).fetchone()
        if not check_password_hash(row["password_hash"], current):
            audit("password_change_failed", "", uid)
            return error("Your current password is wrong.", 400)
        problem = password_problem(new)
        if problem:
            return error(problem, 400)
        if check_password_hash(row["password_hash"], new):
            return error("The new password must be different from the current one.", 400)
        db.execute("UPDATE users SET password_hash = ?, session_version = session_version + 1 WHERE id = ?",
                   (hash_password(new), uid))
        version = db.execute("SELECT session_version FROM users WHERE id = ?", (uid,)).fetchone()[0]
        db.execute("UPDATE user_sessions SET revoked = 1 WHERE user_id = ? AND sid != ?", (uid, session.get("sid", "")))
        db.commit()
        session["sv"] = version                      # this browser stays signed in; every other one is signed out
        audit("password_changed", "", uid)
        send_email(g.user["email"], "Your MellowTech password was changed",
                   f"Hello {g.user['name']},\n\nYour MellowTech password was just changed and all your other devices were signed out.\n\n"
                   "If this was not you, reset your password straight away from the sign-in page and tell your administrator.")
        return jsonify({"ok": True})

    @app.get("/api/account/sessions")
    @login_required()
    def account_sessions():
        if not session.get("sid"):
            new_session(g.user["id"])               # adopt a session that started before this feature existed
        db = get_db()
        ensure_tables(db)
        rows = db.execute("SELECT id, sid, created_at, last_seen, ip, agent FROM user_sessions "
                          "WHERE user_id = ? AND revoked = 0 ORDER BY last_seen DESC LIMIT 50", (g.user["id"],)).fetchall()
        return jsonify([{"id": r["id"], "device": describe_agent(r["agent"]), "ip": r["ip"], "created_at": r["created_at"],
                         "last_seen": r["last_seen"], "current": r["sid"] == session.get("sid")} for r in rows])

    @app.post("/api/account/sessions/revoke")
    @login_required()
    def account_revoke_session():
        try:
            row_id = int((request.get_json(silent=True) or {}).get("id"))
        except (TypeError, ValueError):
            return error("Unknown session.", 400)
        db = get_db()
        cursor = db.execute("UPDATE user_sessions SET revoked = 1 WHERE id = ? AND user_id = ? AND sid != ?",
                            (row_id, g.user["id"], session.get("sid", "")))
        db.commit()
        if cursor.rowcount == 0:
            return error("That device is not signed in, or it is this one. Use Sign out for this device.", 404)
        audit("session_signed_out", str(row_id), g.user["id"])
        return jsonify({"ok": True})

    @app.post("/api/account/sessions/revoke-others")
    @login_required()
    def account_revoke_others():
        db = get_db()
        cursor = db.execute("UPDATE user_sessions SET revoked = 1 WHERE user_id = ? AND sid != ? AND revoked = 0",
                            (g.user["id"], session.get("sid", "")))
        db.commit()
        audit("sessions_signed_out", f"{cursor.rowcount} device(s)", g.user["id"])
        return jsonify({"ok": True, "count": cursor.rowcount})

    @app.get("/api/account/audit")
    @login_required("admin")
    def account_audit():
        db = get_db()
        if request.args.get("all") == "1" and g.user["is_platform"] and g.user["staff_level"] == "super_admin":
            rows = db.execute("SELECT a.ts, a.action, a.detail, a.ip, u.name, u.email, o.name AS company FROM audit_log a "
                              "LEFT JOIN users u ON u.id = a.user_id LEFT JOIN organisations o ON o.id = u.org_id "
                              "ORDER BY a.id DESC LIMIT 200").fetchall()
        else:
            rows = db.execute("SELECT a.ts, a.action, a.detail, a.ip, u.name, u.email, o.name AS company FROM audit_log a "
                              "LEFT JOIN users u ON u.id = a.user_id LEFT JOIN organisations o ON o.id = u.org_id "
                              "WHERE u.org_id = ? OR (a.action = 'login_failed' AND a.detail IN "
                              "(SELECT email FROM users WHERE org_id = ?)) ORDER BY a.id DESC LIMIT 200",
                              (g.user["org_id"], g.user["org_id"])).fetchall()
        return jsonify([{"ts": r["ts"], "action": r["action"], "detail": r["detail"], "ip": r["ip"],
                         "who": (r["name"] or "") + (f" ({r['email']})" if r["email"] else ""), "company": r["company"]}
                        for r in rows])