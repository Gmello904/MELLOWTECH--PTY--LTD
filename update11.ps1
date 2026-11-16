$ErrorActionPreference = 'Stop'
$src = "$env:TEMP\mt4"
$dl  = "$env:USERPROFILE\Downloads"
$old = "$dl\MELLOWTECH-AWS-update-10.zip"
$out = "$dl\MELLOWTECH-AWS-update-11.zip"
$files = @{
  'app.js'               = "$src\app.js"
  'backend/app.py'       = "$src\backend\app.py"
  'backend/autopilot.py' = "$src\backend\autopilot.py"
}

if (-not (Test-Path $old)) { throw "update-10 zip not found in Downloads" }
$js = [IO.File]::ReadAllText($files['app.js'])
if (-not $js.Contains('function applyGuideMode')) { throw "app.js is not the update-10 version" }
if ($js.Contains('You seem to be offline')) { throw "Already applied" }
if (Test-Path $out) { Remove-Item $out -Force }
foreach ($k in $files.Keys) { Copy-Item $files[$k] "$dl\$(Split-Path $files[$k] -Leaf).backup-update10" -Force }

function Rep($t, $o, $n, $expected) {
  $c = ([regex]::Matches($t, [regex]::Escape($o))).Count
  if ($c -ne $expected) { throw "found $c matches (need $expected) for: $($o.Substring(0,[Math]::Min(70,$o.Length)))" }
  return $t.Replace($o, $n)
}

# ---- offline wording (app.js) ----
$js = Rep $js '"Live system data is unavailable. Start the Flask backend (python app.py) and check that it is running on port 5000."' '(navigator.onLine === false ? "You seem to be offline. Please check your internet connection and try again." : "MellowTech is temporarily unavailable. Please try again in a few minutes.")' 1
$js = Rep $js '"BACKEND OFFLINE"' '(navigator.onLine === false ? "YOU ARE OFFLINE" : "SERVER UNAVAILABLE")' 1
$js = Rep $js 'Network data is unavailable. Check that the Flask /api/network endpoint is running.' 'Network data is unavailable. Please check your internet connection and try again in a few minutes.' 1
$js = Rep $js 'Could not reach the backend. Check that Flask is running on port 5000.' 'Could not reach MellowTech. Please check your internet connection and try again.' 2

# ---- laptop counts as Online for 150 seconds (app.py) ----
$py = [IO.File]::ReadAllText($files['backend/app.py'])
$py = Rep $py 'ONLINE_SECONDS, AGENT_INTERVAL = 60, 15' 'ONLINE_SECONDS, AGENT_INTERVAL = 150, 15' 1

# ---- automatic quick scan every day instead of every 7 days (autopilot.py) ----
$ap = [IO.File]::ReadAllText($files['backend/autopilot.py'])
$ap = Rep $ap '(scan_age is None or scan_age >= 7)' '(scan_age is None or scan_age >= 1)' 1

$enc = New-Object Text.UTF8Encoding($false)
[IO.File]::WriteAllText($files['app.js'], $js, $enc)
[IO.File]::WriteAllText($files['backend/app.py'], $py, $enc)
[IO.File]::WriteAllText($files['backend/autopilot.py'], $ap, $enc)
Write-Host "app.js, app.py and autopilot.py updated" -ForegroundColor Green

if (Get-Command node -ErrorAction SilentlyContinue) {
  node --check $files['app.js']
  if ($LASTEXITCODE -ne 0) { throw "app.js SYNTAX ERROR - do not deploy" }
  "app.js syntax OK"
} else { "node not installed, app.js syntax check skipped" }
if (Get-Command python -ErrorAction SilentlyContinue) {
  foreach ($k in 'backend/app.py','backend/autopilot.py') {
    python -c "import ast,sys; ast.parse(open(sys.argv[1],encoding='utf-8').read()); print('python syntax OK')" $files[$k]
    if ($LASTEXITCODE -ne 0) { throw "$k SYNTAX ERROR - do not deploy" }
  }
}

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
Copy-Item $old $out -Force
$zip = [IO.Compression.ZipFile]::Open($out, 'Update')
try {
  foreach ($k in $files.Keys) {
    $zip.GetEntry($k).Delete()
    [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $files[$k], $k, 'Optimal') | Out-Null
  }
} finally { $zip.Dispose() }

function ReadEntry($z, $name) { $sr = New-Object IO.StreamReader($z.GetEntry($name).Open()); $c = $sr.ReadToEnd(); $sr.Close(); $c }
$z = [IO.Compression.ZipFile]::OpenRead($out)
"Files in zip: $($z.Entries.Count)"
$z.Entries | Where-Object FullName -eq 'agent/MellowTechAgent.exe' | Select-Object FullName, Length
$a = ReadEntry $z 'app.js'
"Offline wording:     " + $a.Contains('You seem to be offline')
"Flask text gone:     " + (-not $a.Contains('Check that Flask') -and -not $a.Contains('(python app.py)'))
"Windows guide kept:  " + $a.Contains('function applyGuideMode')
"150-second rule:     " + (ReadEntry $z 'backend/app.py').Contains('= 150, 15')
"Daily scan rule:     " + (ReadEntry $z 'backend/autopilot.py').Contains('scan_age >= 1)')
"Welcome email kept:  " + (ReadEntry $z 'backend/app.py').Contains('def welcome_text')
$z.Dispose()

"---- any Flask wording still left in app.js ----"
Select-String -Path $files['app.js'] -Pattern "Flask|python app.py" | Select-Object LineNumber, @{n='Line';e={$t=$_.Line.Trim(); $t.Substring(0,[Math]::Min(110,$t.Length))}} | Format-List