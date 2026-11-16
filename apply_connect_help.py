"""MellowTech: simple "Connect a laptop" instructions plus a help box that sends the customer's message to MellowTech.
Messages arrive (1) by email to the MellowTech admin accounts and (2) in a new "Help messages" tab in the Internal Portal.

Run from the project folder, next to index.html:   python apply_connect_help.py
Patches app.js, index.html, internal.html and backend/app.py (backups: *.before-help.bak).
Nothing is written unless every step succeeds. Then restart the server and hard-refresh with Ctrl+Shift+R.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def find(*names):
    for n in names:
        if (HERE / n).is_file():
            return HERE / n
    sys.exit("Could not find " + " or ".join(names) + " next to this script.")


FILES = {"js": find("app.js"), "index": find("index.html"), "internal": find("internal.html"), "app": find("backend/app.py", "app.py")}


def load(p):
    raw = p.read_bytes().decode("utf-8-sig") if p.suffix == ".py" else p.read_bytes().decode("utf-8")
    return raw.replace("\r\n", "\n"), "\r\n" in raw


def rep(text, old, new, step):
    if text.count(old) != 1:
        sys.exit(f"STEP FAILED ({step}): anchor found {text.count(old)} times. Nothing was changed.")
    return text.replace(old, new)


texts = {k: load(p) for k, p in FILES.items()}
js, index, internal, app = (texts[k][0] for k in ("js", "index", "internal", "app"))
if "help_messages" in app or "cl-send" in js:
    sys.exit("Already applied. Nothing was changed.")

# ============================================================ backend/app.py
app = rep(app, 'PERMISSIONS["manage_payments"] = {"staff": True, "super_admin": True}      # employees can switch payment services on and off\n',
'''PERMISSIONS["manage_payments"] = {"staff": True, "super_admin": True}      # employees can switch payment services on and off
PERMISSIONS["manage_support"] = {"staff": True, "super_admin": True}       # employees can read and answer customers' help messages
''', "permission")

app = rep(app, '    db.execute("CREATE TABLE IF NOT EXISTS platform_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")\n',
'''    db.execute("CREATE TABLE IF NOT EXISTS platform_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS help_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, org_id INTEGER NOT NULL, "
               "user_id INTEGER NOT NULL, topic TEXT NOT NULL, message TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open', "
               "created_at TEXT NOT NULL)")
''', "table")

app = rep(app, '@app.get("/api/internal/payments")\n', '''@app.post("/api/support/message")
@login_required()
def support_message():
    """A customer who is stuck writes to MellowTech. Saved for the Internal Portal and emailed to the MellowTech admins."""
    data = request.get_json(silent=True) or {}
    topic = str(data.get("topic", "")).strip()[:80] or "Something else"
    message = str(data.get("message", "")).strip()[:2000]
    if len(message) < 5:
        return error("Please tell us what went wrong, even in a few words.", 400)
    if too_many("support:" + str(g.user["id"]), 5, 3600):
        return error("You have already sent several messages. Please give us a little time to reply.", 429)
    db = get_db()
    db.execute("INSERT INTO help_messages (org_id, user_id, topic, message, status, created_at) VALUES (?,?,?,?,'open',?)",
               (g.user["org_id"], g.user["id"], topic, message, iso(utcnow())))
    db.commit()
    audit("support_message", f"{topic} ({g.user['email']})", g.user["id"])
    notify_staff("MellowTech help message: " + topic,
                 f"A customer needs help.\\n\\nCompany: {g.user['org_name']}\\nPerson: {g.user['name']} <{g.user['email']}>\\n"
                 f"Topic: {topic}\\n\\n{message}\\n\\nReply to them by email, or open the Internal Portal, Help messages tab.")
    return jsonify({"ok": True, "email": g.user["email"]})


@app.get("/api/internal/support")
@internal_required("manage_support")
def internal_support():
    rows = get_db().execute(
        "SELECT h.id, h.topic, h.message, h.status, h.created_at, o.name AS company, u.name AS person, u.email "
        "FROM help_messages h JOIN organisations o ON o.id = h.org_id JOIN users u ON u.id = h.user_id "
        "ORDER BY (h.status = 'open') DESC, h.id DESC LIMIT 300").fetchall()
    return jsonify([dict(r) for r in rows])


@app.post("/api/internal/support/<int:message_id>")
@internal_required("manage_support")
def internal_support_update(message_id):
    status = "done" if (request.get_json(silent=True) or {}).get("status") == "done" else "open"
    db = get_db()
    cursor = db.execute("UPDATE help_messages SET status = ? WHERE id = ?", (status, message_id))
    db.commit()
    if not cursor.rowcount:
        return error("Message not found.", 404)
    audit("support_message_" + status, f"message {message_id}", g.user["id"])
    return jsonify({"ok": True, "status": status})


@app.get("/api/internal/payments")
''', "routes")
compile(app, "app.py", "exec")

# ============================================================ internal.html
internal = rep(internal, '        payments: \'<rect x="3" y="6" width="18" height="13" rx="2"/><path d="M3 10h18M7 15h4"/>\'\n',
 '        payments: \'<rect x="3" y="6" width="18" height="13" rx="2"/><path d="M3 10h18M7 15h4"/>\',\n'
 '        help: \'<path d="M4 5h16v11H9l-5 4z"/><path d="M8 9h8M8 12h5"/>\'\n', "icon")

internal = rep(internal, "    .pay-card .btn { align-self: flex-start; }\n", '''    .pay-card .btn { align-self: flex-start; }
    .help-list { display: grid; gap: 14px; }
    .help-card { border-left: 4px solid var(--coral); }
    .help-card.done { border-left-color: var(--signal); opacity: .75; }
    .help-top { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; justify-content: space-between; margin-bottom: 8px; }
    .help-msg { white-space: pre-wrap; margin: 8px 0 14px; line-height: 1.55; }
    .help-actions { display: flex; flex-wrap: wrap; gap: 10px; }
''', "css")

internal = rep(internal, "    var TABS = [\n", r'''    /* ------------------------------------------------ Help messages from customers */
    function helpMessages() {
        return api("/api/internal/support").then(function (list) {
            var waiting = list.filter(function (m) { return m.status === "open"; }).length;
            var box = el("div", null, "help-list");
            if (!list.length) { box.appendChild(panel(el("p", "No messages yet. When a customer gets stuck and writes to you, it appears here.", "note"))); }
            list.forEach(function (m) {
                var card = el("div", null, "panel help-card" + (m.status === "done" ? " done" : ""));
                var top = el("div", null, "help-top"), left = el("div");
                left.appendChild(el("h4", m.company + " – " + m.topic));
                left.appendChild(el("p", m.person + " (" + m.email + ") · " + when(m.created_at), "note"));
                top.appendChild(left);
                top.appendChild(badge(m.status === "open" ? "WAITING" : "ANSWERED", m.status === "open" ? "red" : "green"));
                card.appendChild(top);
                card.appendChild(el("p", m.message, "help-msg"));
                var actions = el("div", null, "help-actions");
                var reply = el("a", "Reply by email", "btn primary");
                reply.href = "mailto:" + encodeURIComponent(m.email).replace("%40", "@") + "?subject=" + encodeURIComponent("Re: " + m.topic);
                actions.appendChild(reply);
                var toggle = el("button", m.status === "open" ? "Mark as answered" : "Reopen", "btn");
                toggle.addEventListener("click", function () {
                    toggle.disabled = true;
                    api("/api/internal/support/" + m.id, { status: m.status === "open" ? "done" : "open" })
                        .then(function () { return helpMessages(); })
                        .catch(function (e) { say(e.message, "err"); toggle.disabled = false; });
                });
                actions.appendChild(toggle);
                card.appendChild(actions);
                box.appendChild(card);
            });
            show([heading("Help messages", waiting + " waiting for a reply. Customers write here when they get stuck, for example when connecting a laptop. You also get each one by email.", null), box]);
        });
    }

    var TABS = [
''', "function")

internal = rep(internal, '        { key: "view_audit_logs", label: "Audit log", icon: "audit", run: audit }\n',
 '        { key: "manage_support", label: "Help messages", icon: "help", run: helpMessages },\n'
 '        { key: "view_audit_logs", label: "Audit log", icon: "audit", run: audit }\n', "tab")

# ============================================================ app.js  (the customer-facing panel)
start = "    box.innerHTML = `<h3>Connect a laptop</h3>"
end = "instead of <code>${escapeHTML(location.hostname)}</code>.</p>`;\n"
a = js.find(start)
b = js.find(end)
if a < 0 or b < a or js.count(start) != 1:
    sys.exit("STEP FAILED (app.js panel): could not find the Connect a laptop panel. Nothing was changed.")
b += len(end)

panel = r'''    const command = `MellowTechAgent.exe install --server ${location.origin} --key ${data.key}`;
    const pyCommand = `python mellowtech_agent.py install --server ${location.origin} --key ${data.key}`;
    const sameComputerNote = ["127.0.0.1", "localhost"].includes(location.hostname)
        ? `<p>This page is open on <b>this</b> computer. If the laptop is a <b>different</b> computer, open MellowTech on that laptop (or replace <code>${escapeHTML(location.hostname)}</code> in the line with this computer's network address).</p>` : "";
    box.innerHTML = `<h3>Connect a laptop</h3>
        <p class="cl-intro">Three easy steps. It takes about two minutes.</p>
        <ol class="cl-steps">
            <li><div><b>Download the program.</b> On the laptop you want to protect, click the button.<br>
                <a class="cl-download" href="${location.origin}/download/MellowTechAgent.exe">Download MellowTechAgent</a></div></li>
            <li><div><b>Open Terminal as Administrator.</b> Right-click the Windows Start button and choose <b>Terminal (Admin)</b>
                (or <b>Windows PowerShell (Admin)</b>). Click <b>Yes</b> if Windows asks.</div></li>
            <li><div><b>Paste this line and press Enter.</b>
                <pre class="code-box" id="cl-command">${escapeHTML(command)}</pre>
                <button type="button" class="btn-small" id="cl-copy">Copy the line</button></div></li>
        </ol>
        <p class="cl-done"><b>That is all.</b> Your laptop appears in the list below within a minute. The line works once and stops working in ${data.expires_minutes} minutes. If it expires, click &ldquo;Connect a laptop&rdquo; again for a new one.</p>
        <details class="cl-more"><summary>No download link, or a different computer?</summary>
            ${sameComputerNote}
            <p>If the download link does not work yet, use the Python way instead: install Python 3, run <code>pip install psutil</code>,
            download <a href="${location.origin}/download/mellowtech_agent.py">mellowtech_agent.py</a> and run this as Administrator:</p>
            <pre class="code-box">${escapeHTML(pyCommand)}</pre>
        </details>
        <div class="cl-help">
            <h4>Stuck? Tell us and we will help</h4>
            <p>If the download, the line or the list did not work, write to us here. We get your message straight away and reply to your email.</p>
            <label>What went wrong?
                <select id="cl-topic">
                    <option>I cannot download the program</option>
                    <option>The line gave an error</option>
                    <option>The laptop does not appear in the list</option>
                    <option>Something else</option>
                </select></label>
            <label>Tell us what you see
                <textarea id="cl-message" rows="3" maxlength="2000" placeholder="For example: the screen says ..."></textarea></label>
            <button type="button" class="btn-small" id="cl-send">Send to MellowTech</button>
            <p class="cl-status" id="cl-status" role="status"></p>
        </div>`;

    const copyButton = element("cl-copy");
    copyButton.addEventListener("click", async () => {
        try { await navigator.clipboard.writeText(command); copyButton.textContent = "Copied"; }
        catch (error) { copyButton.textContent = "Select the line above and press Ctrl+C"; }
    });

    const sendButton = element("cl-send");
    sendButton.addEventListener("click", async () => {
        const status = element("cl-status");
        const text = element("cl-message").value.trim();
        if (text.length < 5) { status.textContent = "Please tell us what you see, even in a few words."; status.className = "cl-status err"; return; }
        sendButton.disabled = true;
        status.textContent = "Sending...";
        status.className = "cl-status";
        try {
            const result = await apiPost("/api/support/message", {
                topic: element("cl-topic").value,
                message: text + "\n\n(Sent from Connect a laptop. Browser: " + navigator.userAgent.slice(0, 140) + ")"
            });
            element("cl-message").value = "";
            status.textContent = "Sent. Thank you. We will reply to " + result.email + ".";
            status.className = "cl-status ok";
        } catch (error) {
            status.textContent = error.message;
            status.className = "cl-status err";
        }
        sendButton.disabled = false;
    });
'''
js = js[:a] + panel + js[b:]

# ============================================================ index.html styles
index = rep(index, "</head>", '''<style id="mt-help">
.cl-intro { margin: 0 0 12px; opacity: .8; }
.cl-steps { list-style: none; counter-reset: cl; padding: 0; margin: 0 0 14px; display: grid; gap: 14px; }
.cl-steps > li { counter-increment: cl; display: flex; gap: 14px; align-items: flex-start; }
.cl-steps > li::before { content: counter(cl); flex: none; width: 32px; height: 32px; border-radius: 50%; display: grid; place-items: center; font-weight: 800; color: #07111d; background: linear-gradient(135deg, #3ddbb0, #2f7de1); }
.cl-steps b { font-weight: 700; }
.cl-download { display: inline-block; margin-top: 8px; padding: 10px 18px; border-radius: 10px; background: #12906e; color: #fff !important; font-weight: 700; text-decoration: none; }
.cl-download:hover { filter: brightness(1.1); }
.cl-steps .code-box { margin: 10px 0 8px; overflow-x: auto; }
.cl-done { padding: 12px 16px; border-radius: 10px; background: rgba(61,219,176,.14); }
.cl-more { margin: 14px 0; }
.cl-more summary { cursor: pointer; font-weight: 600; }
.cl-help { margin-top: 18px; padding-top: 16px; border-top: 1px dashed rgba(120,140,160,.45); }
.cl-help h4 { margin: 0 0 4px; font-size: 17px; }
.cl-help label { display: block; margin: 12px 0 0; font-weight: 600; font-size: 14px; }
.cl-help select, .cl-help textarea { display: block; box-sizing: border-box; width: 100%; margin-top: 6px; padding: 10px 12px; border-radius: 10px; border: 1px solid rgba(120,140,160,.5); font: inherit; background: transparent; color: inherit; }
.cl-help button { margin-top: 12px; }
.cl-status { min-height: 1.4em; margin: 8px 0 0; font-weight: 600; }
.cl-status.ok { color: #12906e; }
.cl-status.err { color: #d64545; }
</style>
</head>''', "styles")

# ============================================================ write all
new = {"js": js, "index": index, "internal": internal, "app": app}
for key, text in new.items():
    path, crlf = FILES[key], texts[key][1]
    bak = path.with_name(path.name + ".before-help.bak")
    if not bak.exists():
        bak.write_bytes(path.read_bytes())
    path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
    print("patched", path.relative_to(HERE))
print("\nDone. Restart the server (python app.py), then press Ctrl+Shift+R in the browser and in the Internal Portal.")