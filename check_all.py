import sys, os, re, ast, io, shutil, tempfile, subprocess, contextlib
from pathlib import Path
sys.dont_write_bytecode = True

root = Path(sys.argv[1] if len(sys.argv) > 1 else "MELLOWTECH-AWS").resolve()
backend = root / "backend"
fails, warns = [], []

def ok(m): print("  ok    " + m)
def bad(m): fails.append(m); print("  FAIL  " + m)
def warn(m): warns.append(m); print("  check " + m)

def finish():
    print("\n" + "=" * 50)
    print("%d FAIL, %d to look at" % (len(fails), len(warns)))
    for m in fails: print("  FAIL  " + m)
    shutil.rmtree(tmp, ignore_errors=True) if "tmp" in globals() else None
    sys.exit(1 if fails else 0)

if not (root / "application.py").exists() or not backend.is_dir():
    sys.exit("Run from the MELLOWTECH folder: python check_all.py MELLOWTECH-AWS")

print("\n1. Python files compile")
for f in sorted(list(root.glob("*.py")) + list(backend.glob("*.py"))):
    try:
        ast.parse(f.read_text(encoding="utf-8"), str(f)); ok(f.name)
    except SyntaxError as e:
        bad("%s line %s: %s" % (f.name, e.lineno, e.msg))

print("\n2. JavaScript syntax (needs Node.js)")
node = shutil.which("node")
if not node:
    warn("Node.js is not installed, so JavaScript syntax was not checked. Use the browser console (F12) instead.")
else:
    td = Path(tempfile.mkdtemp())
    jobs = [(f.name, f) for f in root.glob("*.js")]
    for h in root.glob("*.html"):
        t = h.read_text(encoding="utf-8", errors="replace")
        for i, body in enumerate(re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", t, re.S)):
            if body.strip():
                p = td / ("%s_%d.js" % (h.stem, i)); p.write_text(body, encoding="utf-8")
                jobs.append(("%s script #%d" % (h.name, i + 1), p))
    for name, p in jobs:
        r = subprocess.run([node, "--check", str(p)], capture_output=True, text=True)
        if r.returncode: bad(name + ": " + " | ".join(r.stderr.strip().splitlines()[:4]))
        else: ok(name)
    shutil.rmtree(td, ignore_errors=True)

print("\n3. Start the whole app on a throw-away database")
tmp = tempfile.mkdtemp()
os.environ.update(MELLOWTECH_DATA_DIR=tmp, MELLOWTECH_DB=str(Path(tmp) / "check.db"),
                  MELLOWTECH_SECRET_KEY="check-key-check-key-check-key")
for k in ("SMTP_HOST", "GROQ_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY",
          "MELLOWTECH_REQUIRE_APPROVAL", "MELLOWTECH_BASE_URL", "MELLOWTECH_BEHIND_PROXY"):
    os.environ.pop(k, None)
sys.path.insert(0, str(backend))
try:
    import app as mt
except Exception as e:
    import traceback; traceback.print_exc()
    bad("the app could not start: %r" % e); finish()
app = mt.app
if Path(mt.ROOT).resolve() == root: ok("app starts and serves pages from " + root.name)
else: bad("app serves pages from %s, not %s" % (mt.ROOT, root))

print("\n4. Pages and access rules")
anon = app.test_client()
def want(client, path, code, label=None):
    got = client.get(path).status_code
    (ok if got == code else bad)("%s -> %s (wanted %s)" % (label or path, got, code))
for page in sorted(mt.PUBLIC_PAGES):
    if (root / page).exists(): want(anon, "/" + page, 200)
want(anon, "/api/status", 200)
want(anon, "/", 302)
want(anon, "/index.html", 302, "/index.html when signed out")
want(anon, "/internal.html", 302, "/internal.html when signed out")
want(anon, "/api/auth/me", 401, "/api/auth/me when signed out")
want(anon, "/api/requests/setting", 401, "approval switch when signed out")
want(anon, "/does-not-exist", 404)

print("\n5. Sign-in and the approval switch")
PW = "CheckPass12345"
with app.app_context():
    d = mt.get_db()
    owner = d.execute("SELECT id FROM organisations WHERE is_platform = 1 ORDER BY id LIMIT 1").fetchone()[0]
    d.execute("INSERT INTO users (email,name,password_hash,role,created_at,org_id,staff_level) VALUES (?,?,?,?,?,?,?)",
              ("admin@check.local", "Check Admin", mt.hash_password(PW), "admin", mt.iso(mt.utcnow()), owner, "super_admin"))
    d.commit()
admin = app.test_client()
if admin.post("/api/auth/login", json={"email": "admin@check.local", "password": PW}).status_code != 200:
    bad("test admin could not sign in"); finish()
H = {"X-CSRF-Token": admin.get("/api/auth/me").get_json()["csrf"]}
r = admin.get("/api/requests/setting")
if r.status_code == 200 and r.get_json().get("require_approval") is True: ok("approval switch exists and starts ON")
else: bad("approval switch endpoint answered %s (is patch_approval applied?)" % r.status_code); finish()

def signup(email):
    c = app.test_client()
    with contextlib.redirect_stdout(io.StringIO()):
        r = c.post("/api/auth/register", json={"company": "Check Co", "name": "Check User", "email": email, "password": PW})
    with app.app_context():
        d = mt.get_db()
        d.execute("UPDATE users SET email_verified = 1 WHERE email = ?", (email,)); d.commit()
        row = d.execute("SELECT id, approval FROM users WHERE email = ?", (email,)).fetchone()
        info = (row["id"], row["approval"]) if row else (None, None)
    return c, r.status_code, info
def sign_in(c, email):
    return c.post("/api/auth/login", json={"email": email, "password": PW}).status_code
def expect(cond, good, badmsg):
    ok(good) if cond else bad(badmsg)
def switch(on):
    r = admin.post("/api/requests/setting", json={"require_approval": on}, headers=H)
    return r.status_code, (r.get_json() or {})

customer = None
c, code, (uid, appr) = signup("a@check.local")
expect(code == 200 and appr == "pending", "ON: new sign-up waits for approval", "ON: sign-up gave %s / %s" % (code, appr))
expect(sign_in(c, "a@check.local") == 403, "ON: unapproved person cannot sign in", "ON: unapproved person could sign in")
expect(admin.get("/api/requests").status_code == 200, "admin can list account requests", "account request list failed")
expect(admin.post("/api/requests/%s/approve" % uid, json={}, headers=H).status_code == 200, "admin can approve by hand", "manual approve failed")
expect(sign_in(c, "a@check.local") == 200, "approved person can sign in", "approved person could not sign in")
customer = c

c, code, (uid, appr) = signup("b@check.local")
expect(appr == "pending" and sign_in(c, "b@check.local") == 403, "ON: second person is waiting", "ON: second person was not held")
status, body = switch(False)
expect(status == 200 and body.get("released", 0) >= 1 and body.get("require_approval") is False, "switch OFF approves everyone waiting", "switch OFF failed: %s %s" % (status, body))
expect(sign_in(c, "b@check.local") == 200, "OFF: waiting person can now sign in", "OFF: waiting person still blocked")
c, code, (uid, appr) = signup("c@check.local")
expect(appr == "approved" and sign_in(c, "c@check.local") == 200, "OFF: new person signs in right after confirming email", "OFF: new person was held (%s)" % appr)
status, body = switch(True)
expect(status == 200 and body.get("require_approval") is True, "switch back ON works", "switch back ON failed")
c, code, (uid, appr) = signup("d@check.local")
expect(appr == "pending" and sign_in(c, "d@check.local") == 403, "ON again: new person waits", "ON again: new person was not held")

print("\n6. Every page and API address, as admin and as customer")
def sweep(client, label):
    n = 0
    for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
        if "GET" not in rule.methods or rule.arguments or rule.rule.startswith("/auth/"): continue
        r = client.get(rule.rule); n += 1
        if r.status_code >= 500: bad("%s: GET %s gave server error %s" % (label, rule.rule, r.status_code))
    ok("%s: %d addresses answered" % (label, n))
sweep(admin, "admin")
sweep(customer, "customer")
want(admin, "/index.html", 200, "admin opens index.html")
want(admin, "/internal.html", 200, "admin opens internal.html")
want(customer, "/index.html", 200, "customer opens index.html")
want(customer, "/internal.html", 404, "customer is kept out of internal.html")

print("\n7. Addresses used by the pages exist in the backend")
pats = []
for rule in app.url_map.iter_rules():
    parts = re.split(r"<[^>]+>", rule.rule)
    pats.append((rule.rule, re.compile("[^/]+".join(re.escape(p) for p in parts))))
seen = {}
for f in list(root.glob("*.html")) + list(root.glob("*.js")):
    t = f.read_text(encoding="utf-8", errors="replace")
    for lit in set(re.findall(r"[\"'`](/api/[A-Za-z0-9_\-/.]*)", t)):
        seen.setdefault(lit, set()).add(f.name)
missing = 0
for lit, files in sorted(seen.items()):
    if any(p.fullmatch(lit) for _, p in pats) or any(r_.startswith(lit) for r_, _ in pats): continue
    missing += 1; bad("%s is called by %s but the backend has no such address" % (lit, ", ".join(sorted(files))))
if not missing: ok("%d addresses checked, all exist" % len(seen))

print("\n8. Buttons, IDs and linked files in each page")
appjs = (root / "app.js").read_text(encoding="utf-8", errors="replace") if (root / "app.js").exists() else ""
for h in sorted(root.glob("*.html")):
    t = h.read_text(encoding="utf-8", errors="replace")
    static = re.sub(r"<script.*?</script>", "", t, flags=re.S)
    combined = t + (appjs if 'src="app.js"' in t else "")
    ids = re.findall(r'\sid="([^"]+)"', static)
    dups = sorted({i for i in ids if ids.count(i) > 1})
    if dups: bad("%s has duplicate ids: %s" % (h.name, ", ".join(dups[:10])))
    defined = set(re.findall(r'\bid=\\?["\']([\w\-]+)', combined)) | set(re.findall(r'\.id\s*=\s*["\']([\w\-]+)', combined))
    wanted = set(re.findall(r'(?:getElementById|\$)\(\s*["\']([\w\-]+)["\']\s*\)', combined))
    gone = sorted(wanted - defined)
    if gone: warn("%s: scripts look for ids that are not in the page: %s" % (h.name, ", ".join(gone[:15])))
    funcs = set(re.findall(r"function\s+([A-Za-z_$][\w$]*)\s*\(", combined)) | set(re.findall(r"window\.([A-Za-z_$][\w$]*)\s*=", combined)) | set(re.findall(r"(?:var|let|const)\s+([A-Za-z_$][\w$]*)\s*=", combined))
    for name in sorted(set(re.findall(r'\bon(?:click|submit|change|input)="\s*(?:return\s+)?([A-Za-z_$][\w$]*)\s*\(', static))):
        if name not in funcs and name not in ("confirm", "alert", "prompt"):
            bad("%s: a button calls %s() but that function does not exist" % (h.name, name))
    client = admin if h.name in ("index.html", "internal.html") else anon
    for ref in sorted(set(re.findall(r'(?:src|href)="([^"]+)"', t))):
        ref = ref.split("#")[0].split("?")[0]
        if not ref or not re.fullmatch(r"/?[\w\-./]+", ref) or ref.startswith(("/auth/", "/download/", "/api/")): continue
        code = client.get("/" + ref.lstrip("/")).status_code
        if code != 200: bad("%s links to %s which gives %s" % (h.name, ref, code))
    ok("%s scanned" % h.name)

print("\n9. Files that should not be in the zip")
for p in sorted(root.rglob("*")):
    if p.is_file() and (p.suffix in (".bak", ".db", ".env", ".zip", ".pyc") or p.name == ".secret_key"):
        extra = " (it is copied to the live server on first start, so make sure it has no real customer data)" if p.name == "mellowtech.db" else ""
        warn("%s is inside %s%s" % (p.relative_to(root), root.name, extra))
finish()
