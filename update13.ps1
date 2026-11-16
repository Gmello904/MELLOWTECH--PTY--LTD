$ErrorActionPreference = 'Stop'
$src = "$env:TEMP\mt4"
$dl  = "$env:USERPROFILE\Downloads"
$old = "$dl\MELLOWTECH-AWS-update-12.zip"
$out = "$dl\MELLOWTECH-AWS-update-13.zip"
$P = @{
  'index.html'    = "$src\index.html"
  'app.js'        = "$src\app.js"
  'style.css'     = "$src\style.css"
  'internal.html' = "$src\internal.html"
}

if (-not (Test-Path $old)) { throw "update-12 zip not found in Downloads" }
$T = @{}
foreach ($k in $P.Keys) { $T[$k] = [IO.File]::ReadAllText($P[$k]) }
if (-not $T['app.js'].Contains('You seem to be offline')) { throw "app.js is not the update-11 version" }
if (-not $T['internal.html'].Contains('function visitors()')) { throw "internal.html is not the update-12 version" }
if ($T['index.html'].Contains('brand-logo')) { throw "Already applied" }
if (Test-Path $out) { Remove-Item $out -Force }

function NL($s) { if ($s.Contains("`r`n")) { "`r`n" } else { "`n" } }
function RepN($s, $o, $n, $expected) {
  $c = ([regex]::Matches($s, [regex]::Escape($o))).Count
  if ($c -ne $expected) { throw "found $c matches (need $expected) for: $($o.Substring(0,[Math]::Min(70,$o.Length)))" }
  $nl = NL $s
  return $s.Replace($o, ($n -replace "`r?`n", $nl))
}

# ================= the logo, taken from login.html =================
$login = [IO.File]::ReadAllText("$src\login.html")
$mt = [regex]::Match($login, '<img class="logo-text" src="data:image/png;base64,([A-Za-z0-9+/=\s]+?)"')
if (-not $mt.Success) { throw "could not find the logo in login.html" }
$bytes = [Convert]::FromBase64String(($mt.Groups[1].Value -replace '\s',''))
$sig = ($bytes[0..7] | ForEach-Object { $_.ToString('X2') }) -join ' '
if ($sig -ne '89 50 4E 47 0D 0A 1A 0A') { throw "the logo is not a PNG file" }
$w = ($bytes[16] -shl 24) + ($bytes[17] -shl 16) + ($bytes[18] -shl 8) + $bytes[19]
$h = ($bytes[20] -shl 24) + ($bytes[21] -shl 16) + ($bytes[22] -shl 8) + $bytes[23]
"Logo found: $w x $h px, $([math]::Round($bytes.Length/1024)) KB (a copy is saved in Downloads as logo-text.png)"
$logoFile = "$dl\logo-text.png"
[IO.File]::WriteAllBytes($logoFile, $bytes)

$logoTag = '<img class="brand-logo" src="/logo-text.png" alt="MellowTech Secure logo" style="display:block;width:118px;height:auto;margin:0 0 14px">'

# ================= index.html: logo and new button name =================
$ix = $T['index.html']
$ix = RepN $ix '<div class="logo">MELLOWTECH</div>' ($logoTag + "`n" + '<div class="logo">MELLOWTECH</div>') 1
$ix = RepN $ix 'data-action="connect-laptop">Connect a laptop</button>' 'data-action="connect-laptop">Instructions and Connect Laptop</button>' 1

# ================= app.js: new name in the panel =================
$js = $T['app.js']
$js = RepN $js '<h3>Connect a laptop</h3>' '<h3>Instructions and Connect Laptop</h3>' 1
$js = RepN $js 'Use "Connect a laptop" to add the first one.' 'Use "Instructions and Connect Laptop" to add the first one.' 1
$js = RepN $js '&ldquo;Connect a laptop&rdquo; again for a new one.' '&ldquo;Instructions and Connect Laptop&rdquo; again for a new one.' 2

# ================= style.css: sidebar refresh =================
$cssNew = @'
/* ===== update 13: sidebar refresh ===== */
.sidebar .brand{padding:0 12px 22px;margin-bottom:14px;border-bottom:1px solid rgba(255,255,255,.07)}
.nav-button{padding:11px 14px;border-radius:12px;margin-bottom:5px;transition:background .15s,color .15s,transform .15s}
.nav-button:hover{background:rgba(255,255,255,.08);transform:translateX(2px)}
.nav-button.active{background:linear-gradient(90deg,rgba(61,219,176,.26),rgba(61,219,176,.04));box-shadow:inset 3px 0 0 var(--teal),0 6px 18px rgba(0,0,0,.18)}
.nav-button.active .icon{filter:drop-shadow(0 0 6px rgba(61,219,176,.45))}
.sidebar::-webkit-scrollbar{width:6px}
.sidebar::-webkit-scrollbar-thumb{background:rgba(255,255,255,.14);border-radius:6px}
'@
$css = $T['style.css']
$cn = NL $css
$css = $css.TrimEnd() + $cn + ($cssNew.TrimEnd() -replace "`r?`n", $cn) + $cn

# ================= internal.html: logo, dark/light button =================
$portalCss = @'
    /* ---------- logo and light mode (update 13) ---------- */
    .brand-logo { display: block; width: 118px; height: auto; margin: 0 0 14px; }
    html[data-theme="light"] { color-scheme: light;
        --ink: #eef3f8; --deep: #e4ecf4; --panel: #ffffff; --raise: #f3f7fb;
        --line: rgba(20, 50, 80, .14); --text: #14263a; --muted: #5a6b7d;
        --signal: #0f9d78; --cyan: #1a7fc4; --coral: #d6303d; --amber: #b87400; }
    html[data-theme="light"] body { background: var(--ink); }
    html[data-theme="light"] aside { --text: #e4eef8; --muted: #8aa0b6; --signal: #1fd6a4; --line: rgba(130, 175, 215, .15); }
    html[data-theme="light"] .panel { background: #ffffff; box-shadow: 0 1px 4px rgba(20, 50, 80, .08); }
    html[data-theme="light"] .btn { background: rgba(20, 50, 80, .06); }
    html[data-theme="light"] .btn:hover { background: rgba(20, 50, 80, .12); }
    html[data-theme="light"] .btn.primary { background: var(--signal); border-color: var(--signal); color: #ffffff; }
    html[data-theme="light"] .btn.danger { background: rgba(214, 48, 61, .08); border-color: rgba(214, 48, 61, .4); color: #b3202c; }
    html[data-theme="light"] aside .btn { background: rgba(255, 255, 255, .08); color: #e4eef8; }
    html[data-theme="light"] aside .btn:hover { background: rgba(255, 255, 255, .16); }
    html[data-theme="light"] input, html[data-theme="light"] select { background: #ffffff; color: var(--text); }
    html[data-theme="light"] .msg { color: var(--text); }
    html[data-theme="light"] .msg.err { color: #9c1f2a; }
    html[data-theme="light"] .msg.ok { color: #0b6b52; }
'@
$themeJs = @'
<script>
(function () {
  try {
    var root = document.documentElement, btn = document.getElementById("theme-toggle"), saved = null;
    try { saved = localStorage.getItem("mt-portal-theme"); } catch (e) {}
    function apply(t) {
      root.setAttribute("data-theme", t);
      if (btn) { btn.textContent = t === "light" ? "\u263E Dark" : "\u2600 Light"; }
    }
    apply(saved === "light" ? "light" : "dark");
    if (btn) {
      btn.addEventListener("click", function () {
        var next = root.getAttribute("data-theme") === "light" ? "dark" : "light";
        apply(next);
        try { localStorage.setItem("mt-portal-theme", next); } catch (e) {}
      });
    }
  } catch (e) {}
})();
</script>
'@
$ih = $T['internal.html']
$ih = RepN $ih '<div class="brand"><b>MELLOWTECH</b><span>Internal portal</span></div>' ('<div class="brand">' + $logoTag + '<b>MELLOWTECH</b><span>Internal portal</span></div>') 1
$ih = RepN $ih '<button class="btn" id="logout">Sign out</button>' ('<button class="btn" id="theme-toggle" type="button" title="Switch between dark and light">Light</button>' + "`n        " + '<button class="btn" id="logout">Sign out</button>') 1
$ih = RepN $ih '<style>' ('<script>try{if(localStorage.getItem("mt-portal-theme")==="light"){document.documentElement.setAttribute("data-theme","light");}}catch(e){}</script>' + "`n" + '<style>') 1
$ih = RepN $ih '</style>' ($portalCss.TrimEnd() + "`n" + '</style>') 1
$ih = RepN $ih '</body>' ($themeJs.TrimEnd() + "`n" + '</body>') 1

# ================= syntax checks BEFORE anything is saved =================
$enc = New-Object Text.UTF8Encoding($false)
if (Get-Command node -ErrorAction SilentlyContinue) {
  $tmp = "$env:TEMP\mt-check-app.js"
  [IO.File]::WriteAllText($tmp, $js, $enc)
  node --check $tmp
  if ($LASTEXITCODE -ne 0) { throw "app.js SYNTAX ERROR - nothing was saved" }
  $i = 0
  foreach ($b in [regex]::Matches($ih, '(?s)<script>(.*?)</script>')) {
    $i++
    $tmp = "$env:TEMP\mt-check-$i.js"
    [IO.File]::WriteAllText($tmp, $b.Groups[1].Value, $enc)
    node --check $tmp
    if ($LASTEXITCODE -ne 0) { throw "internal.html script $i SYNTAX ERROR - nothing was saved" }
  }
  "syntax OK (app.js and internal.html)"
} else { "node not installed, syntax check skipped" }

# ================= save backups, then the new files =================
foreach ($k in $P.Keys) { Copy-Item $P[$k] "$dl\$k.backup-update12" -Force }
[IO.File]::WriteAllText($P['index.html'],    $ix,  $enc)
[IO.File]::WriteAllText($P['app.js'],        $js,  $enc)
[IO.File]::WriteAllText($P['style.css'],     $css, $enc)
[IO.File]::WriteAllText($P['internal.html'], $ih,  $enc)
Write-Host "index.html, app.js, style.css and internal.html updated" -ForegroundColor Green

# ================= build update-13 from update-12 =================
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
Copy-Item $old $out -Force
$zip = [IO.Compression.ZipFile]::Open($out, 'Update')
try {
  foreach ($k in $P.Keys) {
    $e = $zip.GetEntry($k)
    if (-not $e) { throw "$k was not found inside the zip" }
    $e.Delete()
    [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $P[$k], $k, 'Optimal') | Out-Null
  }
  if ($zip.GetEntry('logo-text.png')) { $zip.GetEntry('logo-text.png').Delete() }
  [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $logoFile, 'logo-text.png', 'Optimal') | Out-Null
} finally { $zip.Dispose() }

# ================= check the result =================
function ReadEntry($z, $name) { $sr = New-Object IO.StreamReader($z.GetEntry($name).Open()); $c = $sr.ReadToEnd(); $sr.Close(); $c }
$z = [IO.Compression.ZipFile]::OpenRead($out)
"Files in zip: $($z.Entries.Count)  (should be 26)"
$z.Entries | Where-Object { $_.FullName -in 'agent/MellowTechAgent.exe','logo-text.png' } | Select-Object FullName, Length
$zi = ReadEntry $z 'index.html'; $za = ReadEntry $z 'app.js'; $zs = ReadEntry $z 'style.css'; $zh = ReadEntry $z 'internal.html'
"Sidebar logo (main site):    " + $zi.Contains('brand-logo')
"New button name (main site): " + $zi.Contains('Instructions and Connect Laptop</button>')
"New panel name (app.js):     " + $za.Contains('<h3>Instructions and Connect Laptop</h3>')
"Sidebar refresh (style.css): " + $zs.Contains('update 13: sidebar refresh')
"Portal logo and button:      " + ($zh.Contains('brand-logo') -and $zh.Contains('theme-toggle'))
"Visitors page kept:          " + $zh.Contains('function visitors()')
"Idle timer kept:             " + $zh.Contains('MellowTech has not been used')
"Windows guide kept:          " + $za.Contains('function applyGuideMode')
"Offline wording kept:        " + $za.Contains('You seem to be offline')
$z.Dispose()

"---- places that still say Connect a laptop (for me to check) ----"
Select-String -Path $P['index.html'], $P['app.js'] -Pattern "Connect a laptop" | Select-Object Filename, LineNumber, @{n='Line';e={$t2=$_.Line.Trim(); $t2.Substring(0,[Math]::Min(110,$t2.Length))}} | Format-List