import sys
path = sys.argv[1]
text = open(path, encoding="utf-8", newline="").read()

def swap(old, new):
    global text
    if text.count(old) != 1:
        sys.exit("STOPPED: expected exactly one match for: " + old)
    text = text.replace(old, new)

if "def approval_required" in text:
    sys.exit("Already patched.")

swap('"pending" if REQUIRE_APPROVAL else "approved"', '"pending" if approval_required() else "approved"')
swap('email you." if REQUIRE_APPROVAL', 'email you." if approval_required()')

NEW = """def approval_required():
    row = get_db().execute("SELECT value FROM platform_settings WHERE key = 'require_approval'").fetchone()
    return REQUIRE_APPROVAL if row is None else row["value"] != "0"


@app.get("/api/requests/setting")
@login_required("platform_admin")
def approval_setting_get():
    return jsonify({"require_approval": approval_required()})


@app.post("/api/requests/setting")
@login_required("platform_admin")
def approval_setting_set():
    on = bool((request.get_json(silent=True) or {}).get("require_approval"))
    db = get_db()
    db.execute("INSERT INTO platform_settings (key, value) VALUES ('require_approval', ?) "
               "ON CONFLICT(key) DO UPDATE SET value = excluded.value", ("1" if on else "0",))
    released = 0
    if not on:
        released = db.execute("UPDATE users SET approval = 'approved' WHERE approval = 'pending' "
                              "AND org_id IN (SELECT id FROM organisations WHERE is_platform = 0)").rowcount
    db.commit()
    audit("approval_required_on" if on else "approval_required_off", f"released {released}", g.user["id"])
    return jsonify({"ok": True, "require_approval": on, "released": released})


"""
swap('@app.post("/api/requests/<int:user_id>/approve")', NEW + '@app.post("/api/requests/<int:user_id>/approve")')
open(path, "w", encoding="utf-8", newline="").write(text)
print("Patched", path)
