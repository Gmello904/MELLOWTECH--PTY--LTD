"""MellowTech: Windows / Mac / Linux choice in "Connect a laptop", and Mac + Linux support on the Devices cards.
Run from the project folder (next to index.html) AFTER apply_connect_help.py:   python apply_agents.py
Patches app.js and index.html (backups: *.before-agents.bak). Nothing is written unless every step succeeds.
Then restart the server and hard-refresh with Ctrl+Shift+R.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
JS, INDEX = HERE / "app.js", HERE / "index.html"
for p in (JS, INDEX):
    if not p.is_file():
        sys.exit("Could not find " + p.name + " next to this script.")


def load(p):
    raw = p.read_bytes().decode("utf-8")
    return raw.replace("\r\n", "\n"), "\r\n" in raw


def rep(text, old, new, step):
    if text.count(old) != 1:
        sys.exit(f"STEP FAILED ({step}): anchor found {text.count(old)} times. Nothing was changed.")
    return text.replace(old, new)


js, js_crlf = load(JS)
index, ix_crlf = load(INDEX)
if "cl-tabs" in js:
    sys.exit("Already applied. Nothing was changed.")
if "cl-send" not in js:
    sys.exit("Run apply_connect_help.py first, then this script.")

# 1. commands for each system
js = rep(js, '''    const command = `MellowTechAgent.exe install --server ${location.origin} --key ${data.key}`;
    const pyCommand = `python mellowtech_agent.py install --server ${location.origin} --key ${data.key}`;
''', '''    const server = location.origin, key = data.key;
    const pyCommand = `python mellowtech_agent.py install --server ${server} --key ${key}`;
    const unixCommand = `curl -fsSL ${server}/download/mellowtech_agent.py -o mellowtech_agent.py && sudo python3 mellowtech_agent.py install --server ${server} --key ${key}`;
    const commands = {
        windows: `MellowTechAgent.exe install --server ${server} --key ${key}`,
        mac: unixCommand,
        linux: unixCommand
    };
    let command = commands.windows;
''', "commands")

# 2. the steps become tabs
start = js.index('        <p class="cl-intro">Three easy steps. It takes about two minutes.</p>')
end = js.index('        </ol>\n', start) + len('        </ol>\n')
js = js[:start] + '''        <p class="cl-intro">Pick the kind of computer, then follow the three steps. It takes about two minutes.</p>
        <div class="cl-tabs" role="tablist">
            <button type="button" class="cl-tab on" data-os="windows">Windows</button>
            <button type="button" class="cl-tab" data-os="mac">Mac</button>
            <button type="button" class="cl-tab" data-os="linux">Linux</button>
        </div>
        <ol class="cl-steps">
            <li><div><b>Download the program.</b> <span id="cl-s1"></span></div></li>
            <li><div><b id="cl-s2t"></b> <span id="cl-s2"></span></div></li>
            <li><div><b>Paste this line and press Enter.</b> <span id="cl-s3"></span>
                <pre class="code-box" id="cl-command"></pre>
                <button type="button" class="btn-small" id="cl-copy">Copy the line</button></div></li>
        </ol>
''' + js[end:]

js = rep(js, "<p>If the download link does not work yet, use the Python way instead: install Python 3, run <code>pip install psutil</code>,\n            download <a href=\"${location.origin}/download/mellowtech_agent.py\">mellowtech_agent.py</a> and run this as Administrator:</p>",
         "<p><b>Windows without the download:</b> install Python 3, run <code>pip install psutil</code>,\n            download <a href=\"${location.origin}/download/mellowtech_agent.py\">mellowtech_agent.py</a> and run this as Administrator:</p>", "py text")
js = rep(js, '''                    <option>I cannot download the program</option>''',
         '''                    <option>I cannot download the program</option>
                    <option>My company uses a different system</option>''', "topic")

# 3. tab behaviour and copy
js = rep(js, '''    const copyButton = element("cl-copy");
    copyButton.addEventListener("click", async () => {''', '''    const guide = {
        windows: {
            s1: `On the laptop you want to protect, click <a class="cl-download" href="${server}/download/MellowTechAgent.exe">Download MellowTechAgent</a>`,
            s2t: "Open Terminal as Administrator.",
            s2: "Right-click the Windows Start button and choose <b>Terminal (Admin)</b> (or <b>Windows PowerShell (Admin)</b>). Click <b>Yes</b> if Windows asks. Then go to the folder you downloaded to, for example <code>cd $HOME\\\\Downloads</code>.",
            s3: ""
        },
        mac: {
            s1: "Nothing to download by hand. The line in step 3 downloads it for you. Python 3 comes with recent Macs (if a Mac asks to install developer tools, click Install).",
            s2t: "Open Terminal.",
            s2: "Press <b>Command + Space</b>, type <b>Terminal</b> and press Enter.",
            s3: "It asks for your Mac password. Typing shows nothing, that is normal."
        },
        linux: {
            s1: "Nothing to download by hand. The line in step 3 downloads it for you. It needs Python 3 and curl (most Linux computers have both).",
            s2t: "Open a terminal.",
            s2: "Press <b>Ctrl + Alt + T</b>, or search for <b>Terminal</b> in your apps.",
            s3: "It asks for your password. Typing shows nothing, that is normal."
        }
    };
    function showSystem(name) {
        command = commands[name];
        box.querySelectorAll(".cl-tab").forEach(b => b.classList.toggle("on", b.dataset.os === name));
        element("cl-s1").innerHTML = guide[name].s1;
        element("cl-s2t").textContent = guide[name].s2t;
        element("cl-s2").innerHTML = guide[name].s2;
        element("cl-s3").textContent = guide[name].s3;
        element("cl-command").textContent = command;
        element("cl-copy").textContent = "Copy the line";
    }
    box.querySelectorAll(".cl-tab").forEach(b => b.addEventListener("click", () => showSystem(b.dataset.os)));
    const detected = /Mac/i.test(navigator.platform || navigator.userAgent) && !/iPhone|iPad/i.test(navigator.userAgent) ? "mac"
        : /Linux/i.test(navigator.platform || "") && !/Android/i.test(navigator.userAgent) ? "linux" : "windows";
    showSystem(detected);

    const copyButton = element("cl-copy");
    copyButton.addEventListener("click", async () => {''', "tabs js")

# 4. Devices cards: Mac and Linux
js = rep(js, '''    if (p.platform) return '<p class="mt-note">Security checks are only available on Windows laptops.</p>';
''', '''    if (p.platform) return '<p class="mt-note">Security checks are not available for this kind of computer yet.</p>';
''', "platform note")
js = rep(js, '''        stateRow("Web protection", p.web_protection, ON_OFF) + pRow("Windows updates", updates) +''',
         '''        stateRow("Web protection", p.web_protection, ON_OFF) + pRow(p.os_family && p.os_family !== "windows" ? "System updates" : "Windows updates", updates) +''', "updates label")
js = rep(js, '''            (p.usb_storage === "blocked" ? button("usb_allow", "Allow USB storage") : button("usb_block", "Block USB storage"));''',
         '''            (p.os_family === "macos" ? "" : p.usb_storage === "blocked" ? button("usb_allow", "Allow USB storage") : button("usb_block", "Block USB storage"));''', "usb")

# 5. styles
index = rep(index, '<style id="mt-help">', '''<style id="mt-tabs">
.cl-tabs{display:flex;gap:6px;margin:10px 0 4px;flex-wrap:wrap}
.cl-tab{padding:7px 18px;border-radius:999px;border:1px solid var(--line,#d0d7de);background:transparent;color:inherit;font:inherit;font-weight:600;cursor:pointer}
.cl-tab.on{background:#2563eb;border-color:#2563eb;color:#fff}
</style>
<style id="mt-help">''', "css")

for path, text, crlf in ((JS, js, js_crlf), (INDEX, index, ix_crlf)):
    bak = path.with_name(path.name + ".before-agents.bak")
    if not bak.exists():
        bak.write_bytes(path.read_bytes())
    path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
print("Done. Restart the server, then hard-refresh with Ctrl+Shift+R.")