"""
MellowTech guest mode patch.

What it does
  * Visitors who are not signed in now open the dashboard (index.html) straight away.
  * They are signed in automatically as a read-only "Guest" that belongs to a separate
    demo company with sample devices and sample alerts. Nobody's real data is shown.
  * Anything that changes data (POST/PUT/PATCH/DELETE) is refused for guests, and the
    page shows a "Sign in to continue" popup instead.
  * Clicking Network Monitoring, Threat Detection, Vulnerability Scanner, Billing or
    "Run security scan" as a guest shows the same popup.
  * Real accounts and the real login page work exactly as before.

How to use (PowerShell, inside your MELLOWTECH folder)
    python apply_guest_mode.py            patches the MELLOWTECH-AWS folder
    python apply_guest_mode.py undo       puts the old files back

Every file is backed up first as <name>.before-guest.bak.
Nothing is written unless every change can be made, so a half-patched project is not possible.
"""
import os
import re
import shutil
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
args = [a for a in sys.argv[1:]]
UNDO = "undo" in args
folders = [a for a in args if a != "undo"]
ROOT = os.path.join(BASE, folders[0] if folders else "MELLOWTECH-AWS")

APP_PY = os.path.join(ROOT, "backend", "app.py")
INDEX = os.path.join(ROOT, "index.html")
APP_JS = os.path.join(ROOT, "app.js")
TARGETS = [APP_PY, INDEX, APP_JS]
BAK = ".before-guest.bak"


def fail(message):
    print("\nSTOPPED: " + message)
    print("Nothing was changed.")
    sys.exit(1)


if UNDO:
    for path in TARGETS:
        if os.path.exists(path + BAK):
            shutil.copy2(path + BAK, path)
            print("Restored", path)
        else:
            print("No backup for", path)
    sys.exit(0)

for path in TARGETS:
    if not os.path.exists(path):
        fail("Cannot find " + path + "\nRun this from the MELLOWTECH folder (the one that contains MELLOWTECH-AWS).")


def read(path):
    with open(path, "rb") as handle:
        raw = handle.read()
    crlf = b"\r\n" in raw
    return raw.decode("utf-8").replace("\r\n", "\n"), crlf


def write(path, text, crlf):
    data = text.replace("\n", "\r\n") if crlf else text
    with open(path, "wb") as handle:
        handle.write(data.encode("utf-8"))


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        fail("Could not find the '%s' spot in your code exactly once (found %d).\n"
             "Your file is a little different from what I expected. Send me this message." % (label, count))
    return text.replace(old, new)


# ------------------------------------------------------------------ app.py
GUEST_BLOCK = '''# ---------------------------------------------------------------- guest mode (read-only demo)
DEMO_EMAIL = "guest@demo.mellowtech.invalid"
DEMO_ORG_NAME = "MellowTech Demo"
GUEST_WRITE_OK = {"/api/auth/login", "/api/auth/forgot", "/api/auth/reset",
                  "/api/auth/register", "/api/auth/verify", "/api/auth/logout"}


def guest_user():
    return get_db().execute(
        "SELECT u.id,u.email,u.name,u.role,u.active,u.approval,u.session_version,u.org_id,o.name AS org_name,"
        "o.is_platform,u.staff_level,o.suspended FROM users u JOIN organisations o ON o.id = u.org_id "
        "WHERE u.email = ? AND u.active = 1", (DEMO_EMAIL,)).fetchone()


def ensure_demo():
    """Create (or refresh) the demo company, its sample devices and its sample alerts."""
    import hashlib
    from werkzeug.security import generate_password_hash
    db = get_db()
    now = utcnow()
    org = db.execute("SELECT id FROM organisations WHERE name = ?", (DEMO_ORG_NAME,)).fetchone()
    if org is None:
        cursor = db.execute("INSERT INTO organisations (name, is_platform, created_at, plan) VALUES (?,?,?,?)",
                            (DEMO_ORG_NAME, 0, iso(now), "free"))
        org_id = cursor.lastrowid
    else:
        org_id = org["id"]
    if db.execute("SELECT id FROM users WHERE email = ?", (DEMO_EMAIL,)).fetchone() is None:
        # nobody knows this password, so the demo account can never be signed in to with a password
        db.execute("INSERT INTO users (email, name, password_hash, role, active, created_at, org_id, email_verified, approval) "
                   "VALUES (?,?,?,?,?,?,?,?,?)",
                   (DEMO_EMAIL, "Guest", generate_password_hash(secrets.token_urlsafe(32)), "viewer", 1,
                    iso(now), org_id, 1, "approved"))
    if db.execute("SELECT COUNT(*) AS n FROM devices WHERE org_id = ?", (org_id,)).fetchone()["n"] == 0:
        sample_devices = [("Office-Laptop-01", "Windows 11", "192.168.1.21", 23.0, 48.0, 61.0),
                          ("Reception-PC", "Windows 10", "192.168.1.34", 12.0, 39.0, 54.0),
                          ("File-Server", "Ubuntu 22.04", "192.168.1.5", 31.0, 57.0, 72.0)]
        for name, os_name, ip, cpu, mem, disk in sample_devices:
            db.execute("INSERT INTO devices (org_id, name, token_hash, os, ip, cpu, memory, disk, agent_version, enrolled_at, last_seen) "
                       "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                       (org_id, name, hashlib.sha256(secrets.token_bytes(16)).hexdigest(), os_name, ip, cpu, mem, disk,
                        "demo", iso(now - timedelta(days=12)), iso(now)))
    db.execute("UPDATE devices SET last_seen = ? WHERE org_id = ?", (iso(now), org_id))
    newest = db.execute("SELECT MAX(timestamp) AS t FROM security_events WHERE org_id = ?", (org_id,)).fetchone()["t"]
    if not newest or newest < iso(now - timedelta(hours=12)):
        db.execute("DELETE FROM security_events WHERE org_id = ?", (org_id,))
        ids = [row["id"] for row in db.execute("SELECT id FROM devices WHERE org_id = ? ORDER BY id", (org_id,))]
        names = [row["name"] for row in db.execute("SELECT name FROM devices WHERE org_id = ? ORDER BY id", (org_id,))]
        sample_events = [
            ("Brute force login", 2, "High", "Investigating", "Many failed sign-in attempts from one address.", 2, "203.0.113.45"),
            ("Malware blocked", 0, "High", "Blocked", "A harmful file was stopped before it could run.", 6, "198.51.100.23"),
            ("Port scan", 2, "Medium", "New", "Someone probed several open ports on this server.", 9, "203.0.113.77"),
            ("Suspicious download", 1, "Medium", "Monitoring", "A file from an unknown site was downloaded.", 20, "192.0.2.14"),
            ("Outdated software", 0, "Low", "New", "A program on this device needs an update.", 30, "192.168.1.21"),
            ("Failed login", 1, "Low", "Resolved", "Two wrong passwords, then a correct one.", 52, "192.168.1.34"),
            ("Phishing link blocked", 0, "Medium", "Blocked", "A fake sign-in page was blocked.", 75, "198.51.100.90"),
            ("Firewall rule changed", 2, "Low", "Resolved", "A firewall rule was edited by an administrator.", 100, "192.168.1.5"),
        ]
        for number, (kind, which, severity, status, text, hours, ip) in enumerate(sample_events, 1):
            db.execute("INSERT INTO security_events (event_id, event_type, device, severity, status, description, timestamp, org_id, source_ip, device_id) "
                       "VALUES (?,?,?,?,?,?,?,?,?,?)",
                       ("DEMO-%04d" % number, kind, names[which], severity, status, text,
                        iso(now - timedelta(hours=hours)), org_id, ip, ids[which]))
    db.commit()


def start_guest():
    try:
        ensure_demo()
    except Exception:
        app.logger.exception("Could not prepare the demo account")
        return
    session.clear()
    session["guest"] = True
    session["csrf"] = secrets.token_urlsafe(24)


def current_user():
    uid = session.get("uid")
    if not uid:
        if session.get("guest"):
            return guest_user()
        return None
'''

OLD_CURRENT = '''def current_user():
    uid = session.get("uid")
    if not uid:
        return None
'''

OLD_GUARD = '''def api_guard():
    if request.path.startswith("/api/") and request.method in ("POST", "PUT", "PATCH", "DELETE"):
'''
NEW_GUARD = '''def api_guard():
    if (session.get("guest") and not session.get("uid") and request.path.startswith("/api/")
            and request.method in ("POST", "PUT", "PATCH", "DELETE")):
        if request.path == "/api/auth/logout":
            session.clear()
            return jsonify({"ok": True})
        if request.path not in GUEST_WRITE_OK:
            return error("Sign in or create a free account to use this feature.", 401)
    if request.path.startswith("/api/") and request.method in ("POST", "PUT", "PATCH", "DELETE"):
'''

OLD_HOME = '''def home():
    return redirect("/index.html" if current_user() else "/welcome.html")
'''
NEW_HOME = '''def home():
    return redirect("/index.html" if current_user() else "/welcome.html")      # visitors see the welcome page first
'''

OLD_PAGE = '''    elif name == "index.html":
        if not current_user():
            return redirect("/login.html")
'''
NEW_PAGE = '''    elif name == "index.html":
        if not current_user():
            start_guest()      # not signed in: open the dashboard as a read-only guest
'''

OLD_ME = '''"plan": plan, "plan_expires": expires},'''
NEW_ME = '''"plan": plan, "plan_expires": expires,
                             "guest": user["email"] == DEMO_EMAIL},'''

# ------------------------------------------------------------------ browser side
LOGIN_HREF = re.compile(r"""(?:window\.)?location\.href\s*=\s*(["'])/login\.html\1""")
LOGIN_REPLACE = re.compile(r"""(?:window\.)?location\.replace\(\s*(["'])/login\.html\1\s*\)""")
NEED_LOGIN = '(window.mtNeedLogin ? window.mtNeedLogin() : (window.location.href = "/login.html"))'

MARKER = "<!-- MT-GUEST-MODE -->"
GUEST_HTML = MARKER + '''
<style>
#mt-gate{position:fixed;inset:0;z-index:99999;display:none;align-items:center;justify-content:center;padding:20px;
  background:rgba(5,12,22,.74);-webkit-backdrop-filter:blur(4px);backdrop-filter:blur(4px)}
#mt-gate.on{display:flex}
.mt-card{width:100%;max-width:400px;padding:30px 28px 24px;border-radius:18px;text-align:center;color:#e9f1f9;
  background:linear-gradient(160deg,#0f2236,#0a1a2b);border:1px solid rgba(143,166,191,.25);
  box-shadow:0 30px 70px rgba(0,0,0,.55);font-family:inherit}
.mt-card h2{margin:0 0 8px;font-size:22px;color:#fff}
.mt-card p{margin:0 0 20px;font-size:14px;line-height:1.6;color:#9db0c4}
.mt-btn{display:block;width:100%;box-sizing:border-box;margin-top:10px;padding:13px;border-radius:10px;border:1.5px solid transparent;
  font-weight:700;font-size:15px;font-family:inherit;cursor:pointer;text-decoration:none;text-align:center}
.mt-primary{background:linear-gradient(135deg,#3ddbb0,#4aa8ff);color:#06202a}
.mt-ghost{background:transparent;border-color:rgba(143,166,191,.35);color:#e9f1f9}
.mt-quiet{background:transparent;color:#8fa6bf;font-weight:600;font-size:13px}
#mt-bar{position:fixed;left:50%;bottom:16px;transform:translateX(-50%);z-index:9999;display:none;align-items:center;gap:12px;
  max-width:calc(100vw - 24px);padding:10px 14px;border-radius:999px;font-size:13px;color:#e9f1f9;
  background:rgba(10,26,43,.94);border:1px solid rgba(61,219,176,.45);box-shadow:0 10px 30px rgba(0,0,0,.4)}
#mt-bar.on{display:flex}
#mt-bar a{color:#3ddbb0;font-weight:700;text-decoration:none;white-space:nowrap}
#mt-bar button{background:none;border:0;color:#8fa6bf;font-size:16px;cursor:pointer;padding:0 2px}
</style>
<div id="mt-gate" role="dialog" aria-modal="true" aria-labelledby="mt-gate-title">
  <div class="mt-card">
    <h2 id="mt-gate-title">Sign in to continue</h2>
    <p>This feature works on your own account. It is free to start and needs no credit card.</p>
    <a class="mt-btn mt-primary" href="/register.html">Create free account</a>
    <a class="mt-btn mt-ghost" href="/login.html">Sign in</a>
    <button type="button" class="mt-btn mt-quiet" id="mt-gate-close">Keep exploring the demo</button>
  </div>
</div>
<div id="mt-bar"><span>You are viewing a demo with sample data.</span>
  <a href="/register.html">Create free account</a><a href="/login.html">Sign in</a>
  <button type="button" id="mt-bar-close" aria-label="Close">&times;</button></div>
<script>
(function () {
  var guest = false, interacted = false;
  ["click", "keydown", "touchstart"].forEach(function (name) {
    window.addEventListener(name, function () { interacted = true; }, { capture: true, passive: true });
  });

  function openGate() { var gate = document.getElementById("mt-gate"); if (gate) { gate.classList.add("on"); } }
  function closeGate() { var gate = document.getElementById("mt-gate"); if (gate) { gate.classList.remove("on"); } }

  /* app.js and the page scripts call this whenever the server says "sign in required" */
  window.mtNeedLogin = function () {
    return fetch("/api/auth/me", { credentials: "same-origin", cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (d && d.user && d.user.guest) { if (interacted) { openGate(); } }
        else { window.location.href = "/login.html"; }
      })
      .catch(function () { window.location.href = "/login.html"; });
  };

  var LOCKED_NAV = /network monitoring|threat detection|vulnerability scanner|billing/i;
  document.addEventListener("click", function (e) {
    if (!guest || !e.target.closest) { return; }
    var signIn = e.target.closest("[data-mt-signin]");
    if (signIn) { e.preventDefault(); e.stopImmediatePropagation(); window.location.href = "/login.html"; return; }
    var item = e.target.closest("button, a, .nav-button");
    if (!item || item.closest("#mt-gate") || item.closest("#mt-bar")) { return; }
    var text = (item.textContent || "").replace(/\\s+/g, " ").trim();
    var isNav = item.classList.contains("nav-button");
    if ((isNav && LOCKED_NAV.test(text)) || /^run security scan$/i.test(text)) {
      e.preventDefault(); e.stopImmediatePropagation(); openGate();
    }
  }, true);

  function relabel() {
    Array.prototype.forEach.call(document.querySelectorAll("button, a"), function (el) {
      if (el.hasAttribute("data-mt-signin")) { return; }
      var text = (el.textContent || "").replace(/\\s+/g, " ").trim().toLowerCase();
      if (text !== "sign out") { return; }
      el.setAttribute("data-mt-signin", "1");
      var walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT), first = true, node;
      while ((node = walker.nextNode())) {
        if (!node.nodeValue.trim()) { continue; }
        node.nodeValue = first ? "Sign in" : "";
        first = false;
      }
    });
  }

  function start() {
    fetch("/api/auth/me", { credentials: "same-origin", cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d || !d.user || !d.user.guest) { return; }
        guest = true;
        document.getElementById("mt-bar").classList.add("on");
        relabel(); setTimeout(relabel, 800); setTimeout(relabel, 2500);
      }).catch(function () {});
  }

  document.getElementById("mt-gate-close").addEventListener("click", closeGate);
  document.getElementById("mt-gate").addEventListener("click", function (e) { if (e.target === this) { closeGate(); } });
  document.getElementById("mt-bar-close").addEventListener("click", function () { document.getElementById("mt-bar").classList.remove("on"); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") { closeGate(); } });
  start();
})();
</script>
'''

# ------------------------------------------------------------------ build all new texts first
py, py_crlf = read(APP_PY)
if "DEMO_EMAIL" in py:
    fail("Guest mode is already installed in app.py.")
py = replace_once(py, OLD_CURRENT, GUEST_BLOCK, "current_user")
py = replace_once(py, OLD_GUARD, NEW_GUARD, "api_guard")
py = replace_once(py, OLD_HOME, NEW_HOME, "home page")
py = replace_once(py, OLD_PAGE, NEW_PAGE, "index.html page rule")
py = replace_once(py, OLD_ME, NEW_ME, "/api/auth/me")
try:
    compile(py, APP_PY, "exec")
except SyntaxError as exc:
    fail("The patched app.py would have a mistake (%s). Send me this message." % exc)

html, html_crlf = read(INDEX)
if MARKER in html:
    fail("Guest mode is already installed in index.html.")
html, html_hits_a = LOGIN_HREF.subn(lambda m: NEED_LOGIN, html)
html, html_hits_b = LOGIN_REPLACE.subn(lambda m: NEED_LOGIN, html)
closing = html.rfind("</body>")
if closing == -1:
    fail("index.html has no </body> tag.")
html = html[:closing] + GUEST_HTML + html[closing:]

js, js_crlf = read(APP_JS)
if "mtNeedLogin" in js:
    fail("Guest mode is already installed in app.js.")
js, js_hits_a = LOGIN_HREF.subn(lambda m: NEED_LOGIN, js)
js, js_hits_b = LOGIN_REPLACE.subn(lambda m: NEED_LOGIN, js)
if js_hits_a + js_hits_b == 0:
    fail("Found no sign-in redirects in app.js to change.")

# ------------------------------------------------------------------ write
for path in TARGETS:
    shutil.copy2(path, path + BAK)
write(APP_PY, py, py_crlf)
write(INDEX, html, html_crlf)
write(APP_JS, js, js_crlf)

print("Guest mode installed in", ROOT)
print("  app.py      : guest session, demo data, write protection")
print("  index.html  : popup + demo banner (%d redirects changed)" % (html_hits_a + html_hits_b))
print("  app.js      : %d redirects changed to the popup" % (js_hits_a + js_hits_b))
print("Backups saved as *%s. To undo:  python apply_guest_mode.py undo" % BAK)