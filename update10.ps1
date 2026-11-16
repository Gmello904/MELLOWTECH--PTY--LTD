$ErrorActionPreference = 'Stop'
$src = "$env:TEMP\mt4"
$js  = "$src\app.js"
$dl  = "$env:USERPROFILE\Downloads"
$old = "$dl\MELLOWTECH-AWS-update-8.zip"
$out = "$dl\MELLOWTECH-AWS-update-10.zip"

if (-not (Test-Path $old)) { throw "update-8 zip not found in Downloads" }
$cur = [IO.File]::ReadAllText($js)
if (-not $cur.Contains('MellowTech has not been used')) { throw "app.js is not the update-8 version" }
if ($cur.Contains('function applyGuideMode')) { throw "Already applied" }
if (Test-Path $out) { Remove-Item $out -Force }
Copy-Item $js "$dl\app.js.backup-update8" -Force

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

# SHA-256 of the exe inside update-8 (the file customers download)
$hash = ""
try {
  $zr = [IO.Compression.ZipFile]::OpenRead($old)
  $st = $zr.GetEntry('agent/MellowTechAgent.exe').Open()
  $hash = ([BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash($st)) -replace '-','').ToLower()
  $st.Close(); $zr.Dispose()
  "Agent SHA-256: $hash"
} catch {
  Write-Host "Could not read the exe, so the check-your-download part is left out." -ForegroundColor Yellow
  $hash = ""
}

$nl = if ($cur.Contains("`r`n")) { "`r`n" } else { "`n" }
function Rep($t, $o, $n) {
  $c = ([regex]::Matches($t, [regex]::Escape($o))).Count
  if ($c -ne 1) { throw "found $c matches (need 1) for: $($o.Substring(0,[Math]::Min(60,$o.Length)))" }
  return $t.Replace($o, ($n -replace "`r?`n", $nl))
}

$guideFn = @'
function applyGuideMode(name) {
        const win = element("cl-win");
        const list = box.querySelector(".cl-steps");
        if (!win || !list) { return; }
        if (name !== "windows") { win.style.display = "none"; list.style.display = ""; return; }
        list.style.display = "none";
        win.style.display = "";
        const code = (text) => `<pre class="code-box">${escapeHTML(text)}</pre><button type="button" class="btn-small cl-copy-step">Copy the line</button>`;
        win.innerHTML = `<ol class="cl-steps">
            <li><div><b>Download the agent.</b> On the laptop you want to protect, click <a class="cl-download" href="${server}/download/MellowTechAgent.exe">Download MellowTechAgent</a> and save it in your Downloads folder. The file must be named exactly <code>MellowTechAgent.exe</code>. If your browser saved it as <code>MellowTechAgent (1).exe</code>, delete the old copies and download again.</div></li>
            <li><div><b>Open Command Prompt as Administrator.</b> Press the Windows key and type <b>cmd</b>. Right-click <b>Command Prompt</b>, choose <b>Run as administrator</b> and click <b>Yes</b>.</div></li>
            <li><div><b>Go to the Downloads folder.</b> Click Copy the line, click inside the black window, press Ctrl + V and press Enter.${code("cd %USERPROFILE%\\Downloads")}</div></li>
            <li><div><b>Check the file.</b> Do the same with this line. You should see one file of about 9.3 MB.${code("dir MellowTechAgent*.exe")}</div></li>
            <li><div><b>Install.</b> This line already contains your personal registration key. Copy it, paste it and press Enter.${code(command)}<div style="margin-top:10px">You should see:</div><pre class="code-box">${escapeHTML("Connecting to " + server + "\nInstalled. This computer will show up in your dashboard within a minute.")}</pre><div style="margin-top:10px">The key works once and stops working in ${data.expires_minutes} minutes. If it expires, click &ldquo;Connect a laptop&rdquo; again for a new one. Using PowerShell instead? Put <code>.\\</code> in front of the line.</div></div></li>
            <li><div><b>Check the agent.</b> Copy this line and press Enter. It shows the version and the website it is connected to.${code("MellowTechAgent.exe status")}</div></li>
            <li><div><b>Check the dashboard.</b> Wait about a minute. Your computer appears in the list below with the status <b>Online</b> and real CPU, memory and disk numbers.</div></li>
        </ol>`;
        win.querySelectorAll(".cl-copy-step").forEach(btn => {
            btn.addEventListener("click", async () => {
                const text = btn.previousElementSibling.textContent;
                try { await navigator.clipboard.writeText(text); btn.textContent = "Copied"; }
                catch (error) { btn.textContent = "Select the line above and press Ctrl+C"; }
                setTimeout(() => { btn.textContent = "Copy the line"; }, 2500);
            });
        });
    }
    function showSystem(name) {
'@

$panel = @'
const hashLine = "__HASH__";
        const verify = hashLine ? `<p><b>Check your download first (optional).</b> Copy this line and press Enter. It shows a code for your file, which should match the expected code below.</p>${code("certutil -hashfile MellowTechAgent.exe SHA256")}<p>Expected: <code style="word-break:break-all">${hashLine}</code></p>` : "";
        win.insertAdjacentHTML("beforeend", `<details class="cl-more"><summary>Windows Security blocked or removed the agent?</summary>
            <p>MellowTech is a security program that watches your computer, so Windows Security can mistake it for something unwanted. If it blocked or removed the agent, you can tell Windows Security to trust just the agent. Only do this for a file you downloaded from this page, and do not add any other exclusions.</p>
            ${verify}
            <p><b>1. Allow the MellowTech folder.</b> In the same Administrator Command Prompt, copy this line, paste it and press Enter.</p>${code("powershell -Command \"Add-MpPreference -ExclusionPath 'C:\\Program Files\\MellowTech'\"")}
            <p><b>2. Allow the agent file.</b> Do the same with this line.</p>${code("powershell -Command \"Add-MpPreference -ExclusionPath ($env:USERPROFILE + '\\Downloads\\MellowTechAgent.exe')\"")}
            <p><b>3. Check.</b> Both paths should appear in the list.</p>${code("powershell -Command \"(Get-MpPreference).ExclusionPath\"")}
            <p><b>4. Try again.</b> Download the agent again (step 1), then repeat steps 3 to 7.</p>
        </details>`);
        win.querySelectorAll(".cl-copy-step").forEach(btn => {
'@
$panel = $panel.Replace('__HASH__', $hash)

$t = $cur
$t = Rep $t '<p class="cl-done"><b>That is all.</b>' "<div id=`"cl-win`" style=`"display:none`"></div>`n        <p class=`"cl-done`"><b>That is all.</b>"
$t = Rep $t 'function showSystem(name) {' $guideFn.TrimEnd()
$t = Rep $t 'element("cl-command").textContent = command;' "element(`"cl-command`").textContent = command;`n        applyGuideMode(name);"
$t = Rep $t 'win.querySelectorAll(".cl-copy-step").forEach(btn => {' $panel.TrimEnd()

[IO.File]::WriteAllText($js, $t, (New-Object Text.UTF8Encoding($false)))
Write-Host "app.js updated" -ForegroundColor Green

if (Get-Command node -ErrorAction SilentlyContinue) {
  node --check $js
  if ($LASTEXITCODE -ne 0) { throw "SYNTAX ERROR - do not deploy" }
  "app.js syntax OK"
} else { "node not installed, syntax check skipped" }

Copy-Item $old $out -Force
$zip = [IO.Compression.ZipFile]::Open($out, 'Update')
try {
  $zip.GetEntry('app.js').Delete()
  [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $js, 'app.js', 'Optimal') | Out-Null
} finally { $zip.Dispose() }

$z = [IO.Compression.ZipFile]::OpenRead($out)
"Files in zip: $($z.Entries.Count)"
$z.Entries | Where-Object FullName -eq 'agent/MellowTechAgent.exe' | Select-Object FullName, Length
$sr = New-Object IO.StreamReader($z.GetEntry('app.js').Open()); $c = $sr.ReadToEnd(); $sr.Close()
"Windows guide:        " + $c.Contains('function applyGuideMode')
"Copy buttons:         " + $c.Contains('cl-copy-step')
"Blocked-agent panel:  " + $c.Contains('blocked or removed the agent')
"Idle timer kept:      " + $c.Contains('MellowTech has not been used')
$z.Dispose()