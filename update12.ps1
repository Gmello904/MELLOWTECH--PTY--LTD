$ErrorActionPreference = 'Stop'
$src      = "$env:TEMP\mt4"
$dl       = "$env:USERPROFILE\Downloads"
$old      = "$dl\MELLOWTECH-AWS-update-11.zip"
$out      = "$dl\MELLOWTECH-AWS-update-12.zip"
$appPath  = "$src\backend\app.py"
$htmlPath = "$src\internal.html"

if (-not (Test-Path $old)) { throw "update-11 zip not found in Downloads" }
$py   = [IO.File]::ReadAllText($appPath)
$html = [IO.File]::ReadAllText($htmlPath)
if (-not $py.Contains('= 150, 15')) { throw "app.py is not the update-11 version" }
if ($py.Contains('def record_visit')) { throw "Already applied" }
if (Test-Path $out) { Remove-Item $out -Force }
Copy-Item $appPath  "$dl\app.py.backup-update11" -Force
Copy-Item $htmlPath "$dl\internal.html.backup-update11" -Force

function Rep($t, $o, $n) {
  $c = ([regex]::Matches($t, [regex]::Escape($o))).Count
  if ($c -ne 1) { throw "found $c matches (need 1) for: $($o.Substring(0,[Math]::Min(70,$o.Length)))" }
  $nl = if ($t.Contains("`r`n")) { "`r`n" } else { "`n" }
  return $t.Replace($o, ($n -replace "`r?`n", $nl))
}

# ================= BACKEND =================
$visitPy = @'
VISIT_PAGES = {"login.html", "register.html", "reset.html", "privacy.html", "terms.html", "cookies.html", "index.html"}
BOT_WORDS = ("bot", "crawl", "spider", "slurp", "curl", "wget", "python", "monitor", "uptime", "health", "scan",
             "preview", "headless", "facebookexternalhit", "go-http", "java/", "okhttp", "axios", "node-fetch", "postman")


def ensure_visits_table(db):
    db.execute("CREATE TABLE IF NOT EXISTS visits (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, day TEXT NOT NULL, "
               "page TEXT NOT NULL, visitor TEXT NOT NULL, user_id INTEGER, device TEXT)")
    db.execute("CREATE INDEX IF NOT EXISTS visits_day ON visits (day)")


def record_visit(name):
    """Count one page view. No IP address is stored, only a code that changes every day. Never breaks the page."""
    try:
        if request.method != "GET" or name not in VISIT_PAGES:
            return
        agent = (request.headers.get("User-Agent") or "")[:300]
        low = agent.lower()
        if not agent or any(word in low for word in BOT_WORDS):
            return
        import hmac
        now = utcnow()
        day = (now + timedelta(hours=2)).strftime("%Y-%m-%d")
        code = hmac.new(str(app.config["SECRET_KEY"]).encode(),
                        f"{request.remote_addr}|{agent}|{day}".encode(), hashlib.sha256).hexdigest()[:12]
        device = "Mobile" if any(w in low for w in ("mobile", "android", "iphone", "ipad")) else "Desktop"
        db = get_db()
        ensure_visits_table(db)
        db.execute("INSERT INTO visits (ts, day, page, visitor, user_id, device) VALUES (?,?,?,?,?,?)",
                   (iso(now), day, "/" + name, code, session.get("uid"), device))
        if secrets.randbelow(200) == 0:
            db.execute("DELETE FROM visits WHERE day < ?", ((now - timedelta(days=90)).strftime("%Y-%m-%d"),))
        db.commit()
    except Exception:
        pass
'@

$endpointPy = @'
@app.get("/api/internal/visitors")
@internal_required("view_visitors", full=True)
def internal_visitors():
    db = get_db()
    ensure_visits_table(db)
    local = utcnow() + timedelta(hours=2)
    today = local.strftime("%Y-%m-%d")

    def days_ago(n):
        return (local - timedelta(days=n)).strftime("%Y-%m-%d")

    def count(sql, args=()):
        return db.execute(sql, args).fetchone()[0] or 0

    summary = {
        "visits_today": count("SELECT COUNT(*) FROM visits WHERE day = ?", (today,)),
        "unique_today": count("SELECT COUNT(DISTINCT visitor) FROM visits WHERE day = ?", (today,)),
        "visits_7": count("SELECT COUNT(*) FROM visits WHERE day >= ?", (days_ago(6),)),
        "visits_30": count("SELECT COUNT(*) FROM visits WHERE day >= ?", (days_ago(29),)),
    }
    daily = [dict(r) for r in db.execute(
        "SELECT day, COUNT(*) AS visits, COUNT(DISTINCT visitor) AS unique_visitors, "
        "SUM(CASE WHEN user_id IS NOT NULL THEN 1 ELSE 0 END) AS signed_in "
        "FROM visits WHERE day >= ? GROUP BY day ORDER BY day DESC", (days_ago(13),))]
    pages = [dict(r) for r in db.execute(
        "SELECT page, COUNT(*) AS visits FROM visits WHERE day >= ? GROUP BY page ORDER BY visits DESC LIMIT 10",
        (days_ago(29),))]
    recent = [dict(r) for r in db.execute(
        "SELECT v.ts, v.page, v.visitor, v.device, u.name, u.email FROM visits v LEFT JOIN users u ON u.id = v.user_id "
        "ORDER BY v.id DESC LIMIT 60")]
    return jsonify({"summary": summary, "daily": daily, "pages": pages, "recent": recent})
'@

$py = Rep $py 'def initialize_database():' ($visitPy.TrimEnd() + "`n`n`ndef initialize_database():")
$py = Rep $py 'def permission_level(user, permission):' ('PERMISSIONS["view_visitors"] = {"super_admin": True}      # only Super Admins see who visits the website' + "`n`n`ndef permission_level(user, permission):")
$py = Rep $py 'response = send_from_directory(ROOT, name)' ("record_visit(name)`n    response = send_from_directory(ROOT, name)")
$py = Rep $py '@app.post("/api/internal/employees/<int:user_id>/level")' ($endpointPy.TrimEnd() + "`n`n`n" + '@app.post("/api/internal/employees/<int:user_id>/level")')

# ================= INTERNAL PORTAL PAGE =================
$iconJs = @'
ICONS.visitors = '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>';
'@

$visitorsJs = @'
function visitors() {
        return api("/api/internal/visitors").then(function (d) {
            function tile(label, value) {
                var p = el("div", null, "panel");
                p.appendChild(el("small", label));
                p.appendChild(el("b", String(value)));
                return p;
            }
            var strip = el("div", null, "strip");
            strip.appendChild(tile("Visits today", d.summary.visits_today));
            strip.appendChild(tile("Different visitors today", d.summary.unique_today));
            strip.appendChild(tile("Visits, last 7 days", d.summary.visits_7));
            strip.appendChild(tile("Visits, last 30 days", d.summary.visits_30));

            var parts = [heading("Visitors", "Everyone who opened a MellowTech page, signed in or not. Bots are left out. No IP addresses are stored: each visitor gets a code that changes every day, so the same person on two days counts as two visitors. Records are deleted after 90 days."), strip];
            if (!d.recent.length) {
                parts.push(el("p", "No visits recorded yet. They appear here as people open the website.", "empty"));
            } else {
                parts.push(el("h3", "Last 14 days"));
                parts.push(panel(table(["Day", "Visits", "Different visitors", "Signed in"], d.daily.map(function (r) {
                    return [r.day, String(r.visits), String(r.unique_visitors), String(r.signed_in)];
                }))));
                parts.push(el("h3", "Most opened pages, last 30 days"));
                parts.push(panel(table(["Page", "Visits"], d.pages.map(function (r) {
                    return [r.page, String(r.visits)];
                }))));
                parts.push(el("h3", "Latest visits"));
                parts.push(panel(table(["Time", "Page", "Who", "Device", "Visitor code"], d.recent.map(function (v) {
                    return [when(v.ts), v.page, v.name ? v.name + " (" + v.email + ")" : "Not signed in", v.device || "-", "#" + String(v.visitor).slice(0, 6)];
                }))));
            }
            show(parts);
        });
    }
'@

$html = Rep $html 'function api(path, body) {' ($iconJs.TrimEnd() + "`n    function api(path, body) {")
$html = Rep $html 'function audit() {' ($visitorsJs.TrimEnd() + "`n    function audit() {")
$html = Rep $html '{ key: "view_audit_logs", label: "Audit log"' ('{ key: "view_visitors", label: "Visitors", icon: "visitors", run: visitors },' + "`n        " + '{ key: "view_audit_logs", label: "Audit log"')

$enc = New-Object Text.UTF8Encoding($false)
[IO.File]::WriteAllText($appPath,  $py,   $enc)
[IO.File]::WriteAllText($htmlPath, $html, $enc)
Write-Host "app.py and internal.html updated" -ForegroundColor Green

# ================= SYNTAX CHECKS =================
if (Get-Command python -ErrorAction SilentlyContinue) {
  python -c "import ast,sys; ast.parse(open(sys.argv[1],encoding='utf-8').read()); print('app.py syntax OK')" $appPath
  if ($LASTEXITCODE -ne 0) { throw "app.py SYNTAX ERROR - do not deploy" }
}
if (Get-Command node -ErrorAction SilentlyContinue) {
  $i = 0
  foreach ($m in [regex]::Matches($html, '(?s)<script>(.*?)</script>')) {
    $i++
    $tmp = "$env:TEMP\mt-check-$i.js"
    [IO.File]::WriteAllText($tmp, $m.Groups[1].Value, $enc)
    node --check $tmp
    if ($LASTEXITCODE -ne 0) { throw "internal.html script $i SYNTAX ERROR - do not deploy" }
  }
  "internal.html scripts syntax OK"
} else { "node not installed, internal.html syntax check skipped" }

# ================= BUILD update-12 FROM update-11 =================
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
Copy-Item $old $out -Force
$zip = [IO.Compression.ZipFile]::Open($out, 'Update')
try {
  foreach ($pair in @(@('backend/app.py', $appPath), @('internal.html', $htmlPath))) {
    $zip.GetEntry($pair[0]).Delete()
    [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $pair[1], $pair[0], 'Optimal') | Out-Null
  }
} finally { $zip.Dispose() }

function ReadEntry($z, $name) { $sr = New-Object IO.StreamReader($z.GetEntry($name).Open()); $c = $sr.ReadToEnd(); $sr.Close(); $c }
$z = [IO.Compression.ZipFile]::OpenRead($out)
"Files in zip: $($z.Entries.Count)"
$z.Entries | Where-Object FullName -eq 'agent/MellowTechAgent.exe' | Select-Object FullName, Length
$a = ReadEntry $z 'backend/app.py'
$h = ReadEntry $z 'internal.html'
"Visit counter:         " + $a.Contains('def record_visit')
"Visitors endpoint:     " + $a.Contains('/api/internal/visitors')
"Visitors page:         " + $h.Contains('function visitors()')
"Visitors menu item:    " + $h.Contains('label: "Visitors"')
"Welcome email kept:    " + $a.Contains('def welcome_text')
"150-second rule kept:  " + $a.Contains('= 150, 15')
"Idle timer kept:       " + $h.Contains('MellowTech has not been used')
"Offline wording kept:  " + (ReadEntry $z 'app.js').Contains('You seem to be offline')
$z.Dispose()

"---- how the portal decides which tabs to show (for me to check) ----"
$lines = Get-Content $appPath
$n = ($lines | Select-String -Pattern 'def internal_permissions' | Select-Object -First 1).LineNumber
$lines[($n-1)..($n+9)]