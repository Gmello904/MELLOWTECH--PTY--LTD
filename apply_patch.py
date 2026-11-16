"""MellowTech patch: moon (light/dark) button + payments on/off switch.

HOW TO USE
1. Put this file in your MELLOWTECH folder (the one that contains the "backend" folder).
2. Close the running server (Ctrl+C).
3. In PowerShell, in that folder, run:   python apply_patch.py
4. Start the server again:               cd backend ; python app.py
5. In the browser press Ctrl+Shift+R.

It edits app.py, payfast.py and index.html in place. Before changing a file it saves a
copy next to it (app.py.bak, payfast.py.bak, index.html.bak). If any anchor text is not
found, that file is left untouched and the script tells you which step failed.
Running it twice is safe: files that are already patched are skipped.
"""
import re
import sys
from pathlib import Path


def find(name):
    here = Path.cwd()
    for folder in (here, here / "backend", here.parent, here.parent / "backend"):
        if (folder / name).is_file():
            return folder / name
    sys.exit("Could not find %s. Run this script from your MELLOWTECH folder." % name)


class Patch:
    def __init__(self, name, marker):
        self.path = find(name)
        raw = self.path.read_bytes().decode("utf-8")
        self.crlf = "\r\n" in raw
        self.text = raw.replace("\r\n", "\n")
        self.marker = marker
        self.errors = []
        self.skip = marker in self.text

    def _one(self, pattern, label):
        found = list(re.finditer(pattern, self.text))
        if len(found) != 1:
            self.errors.append("%s (found %d places, expected 1)" % (label, len(found)))
            return None
        return found[0]

    def after(self, pattern, new, label):
        m = self._one(pattern, label)
        if m:
            self.text = self.text[:m.end()] + new + self.text[m.end():]

    def before(self, pattern, new, label):
        m = self._one(pattern, label)
        if m:
            self.text = self.text[:m.start()] + new + self.text[m.start():]

    def save(self):
        if self.skip:
            print("%-12s already patched, skipped." % self.path.name)
            return True
        if self.errors:
            print("%-12s NOT changed. Problems:" % self.path.name)
            for e in self.errors:
                print("   - " + e)
            return False
        backup = self.path.with_name(self.path.name + ".bak")
        if not backup.exists():
            backup.write_bytes(self.path.read_bytes())
        out = self.text.replace("\n", "\r\n") if self.crlf else self.text
        self.path.write_bytes(out.encode("utf-8"))
        print("%-12s patched. (backup: %s)" % (self.path.name, backup.name))
        return True


# ======================================================================= app.py
app = Patch("app.py", "def payments_enabled()")
if not app.skip:
    app.after(
        r'"count INTEGER NOT NULL DEFAULT 0, PRIMARY KEY \(org_id, day\)\)"\)\n',
        '    db.execute("CREATE TABLE IF NOT EXISTS platform_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")\n',
        "app.py step 1: platform_settings table")
    app.before(
        r'@app\.get\("/api/billing"\)\n',
        '''def payments_enabled():
    row = get_db().execute("SELECT value FROM platform_settings WHERE key = 'payments_enabled'").fetchone()
    return not row or row["value"] != "0"


@app.post("/api/billing/payments-switch")
@login_required("platform_admin")
def payments_switch():
    on = bool((request.get_json(silent=True) or {}).get("enabled"))
    db = get_db()
    db.execute("INSERT INTO platform_settings (key, value) VALUES ('payments_enabled', ?) "
               "ON CONFLICT(key) DO UPDATE SET value = excluded.value", ("1" if on else "0",))
    db.commit()
    audit("payments_switched", "on" if on else "off")
    return jsonify({"ok": True, "enabled": on})


''',
        "app.py step 2: payments_enabled and switch route")
    app.after(
        r'"rate": f"\{USD_ZAR_RATE:\.2f\}",\n',
        '                    "payments_enabled": payments_enabled(),\n',
        "app.py step 3: billing_info field")
    app.before(
        r'    if too_many\("pay:" \+ str\(g\.user\["id"\]\), 10, 600\):\n',
        '''    if not payments_enabled():
        return error("Payments are switched off right now. Please try again later.", 503)
''',
        "app.py step 4: PayPal create-order check")
    app.after(
        r'    amount_due=amount_due_zar,\n',
        '    payments_enabled=payments_enabled,\n',
        "app.py step 5: pass switch to payfast")

# ===================================================================== payfast.py
pf = Patch("payfast.py", 'h.get("payments_enabled"')
if not pf.skip:
    pf.after(
        r'    current_org_id = h\["current_org_id"\]\n',
        '    payments_enabled = h.get("payments_enabled", lambda: True)\n',
        "payfast.py step 1: read the switch")
    pf.after(
        r'        if not ready\(\):\n            return error\("Payfast is not connected yet\.", 503\)\n',
        '''
        if not payments_enabled():
            return error("Payments are switched off right now. Please try again later.", 503)
''',
        "payfast.py step 2: create-order check")

# ===================================================================== index.html
HEAD_SCRIPT = '''    <script>
    (function () {
        var t = null;
        try { t = localStorage.getItem("mt-theme"); } catch (e) {}
        if (!t) t = (window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches) ? "dark" : "light";
        document.documentElement.setAttribute("data-theme", t);
    })();
    </script>
'''

BUTTON = '''
                <button type="button" id="theme-toggle" class="theme-toggle" aria-label="Switch light or dark mode" title="Light / dark mode"></button>'''

CSS = '''
        /* ===== moon / sun button ===== */
        .theme-toggle {
            width: 40px; height: 40px; border-radius: 50%; display: grid; place-items: center;
            border: 1px solid #e3e9f0; background: #f4f7fb; color: #1d3550; cursor: pointer;
            transition: transform .15s, background .15s;
        }
        .theme-toggle:hover { transform: translateY(-1px); }
        .theme-toggle svg { width: 20px; height: 20px; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }

        /* ===== dark mode ===== */
        html[data-theme="dark"] {
            color-scheme: dark;
            --ink: #e5e7eb; --line: #243049; --bg: #0b1220; --text: #e5e7eb; --mute: #9fb0c3;
        }
        html[data-theme="dark"] .topbar, html[data-theme="dark"] .panel, html[data-theme="dark"] .stat-card,
        html[data-theme="dark"] .severity-card, html[data-theme="dark"] .device-card, html[data-theme="dark"] .ov-card,
        html[data-theme="dark"] .tg-card, html[data-theme="dark"] .plan-card, html[data-theme="dark"] .bl-trust,
        html[data-theme="dark"] .am-box, html[data-theme="dark"] .stx-tile, html[data-theme="dark"] .stx-subnav {
            background: #111a2e; border-color: #243049;
        }
        html[data-theme="dark"] .device-details { background: #162038; }
        html[data-theme="dark"] .plan-card, html[data-theme="dark"] .plan-card h4, html[data-theme="dark"] .plan-price,
        html[data-theme="dark"] .stx-tile, html[data-theme="dark"] .stx-tile b { color: #f3f4f6; }
        html[data-theme="dark"] .plan-sub, html[data-theme="dark"] .plan-days, html[data-theme="dark"] .plan-price small,
        html[data-theme="dark"] .plan-features li, html[data-theme="dark"] .bl-trust span,
        html[data-theme="dark"] .stx-note, html[data-theme="dark"] .stx-tile span.t,
        html[data-theme="dark"] .rl-skills, html[data-theme="dark"] .am-foot { color: #9fb0c3; }
        html[data-theme="dark"] .btn-small { background: #111a2e; color: #e5e7eb; border-color: #334155; }
        html[data-theme="dark"] .btn-small:hover { background: #1b2740; border-color: #5b6b82; }
        html[data-theme="dark"] .btn-danger { color: #ff8a93; border-color: #7a2a33; }
        html[data-theme="dark"] .btn-danger:hover { background: #3a1a1f; }
        html[data-theme="dark"] input, html[data-theme="dark"] select, html[data-theme="dark"] textarea {
            background: #0f172a; color: #e5e7eb; border-color: #334155;
        }
        html[data-theme="dark"] .events-table tbody tr:hover { background: #1b2740; }
        html[data-theme="dark"] #threats .events-table tbody tr { background: #162038; }
        html[data-theme="dark"] #threats .events-table tbody tr:hover { background: #1b2740; }
        html[data-theme="dark"] #threats .form-row { background: #0f172a; border-color: #334155; }
        html[data-theme="dark"] .distribution-bar, html[data-theme="dark"] .ov-scale i,
        html[data-theme="dark"] .demo-tag { background: #243049; }
        html[data-theme="dark"] .tg-gauge .trk { stroke: #243049; }
        html[data-theme="dark"] .live-indicator, html[data-theme="dark"] .badge.safe,
        html[data-theme="dark"] .plan-tag { background: #12332c; color: #3ddbb0; }
        html[data-theme="dark"] .badge.warning { background: #3a2f10; color: #f5c451; }
        html[data-theme="dark"] .badge.danger { background: #3a1a1f; color: #ff8a93; }
        html[data-theme="dark"] .user-chip { background: #111a2e; border-color: #243049; color: #e5e7eb; }
        html[data-theme="dark"] .plan-badge { background: #1b2740; color: #cbd5e1; }
        html[data-theme="dark"] .plan-badge.paid { background: #12332c; color: #3ddbb0; }
        html[data-theme="dark"] .logout-button { background: transparent; border-color: #7a2a33; color: #ff8a93; }
        html[data-theme="dark"] .theme-toggle { background: #1b2740; border-color: #334155; color: #ffd36b; }
        html[data-theme="dark"] .am-msg.bot { background: #1b2740; color: #e5e7eb; }
        html[data-theme="dark"] .am-msg.err { background: #3a1a1f; color: #ff9aa2; }
        html[data-theme="dark"] .am-hints button { background: #111a2e; color: #e5e7eb; border-color: #334155; }
        html[data-theme="dark"] .am-form, html[data-theme="dark"] .stx-row, html[data-theme="dark"] .stx-int,
        html[data-theme="dark"] .plan-features { border-color: #243049; }
        html[data-theme="dark"] .stx-subnav button { color: #cbd5e1; }
        html[data-theme="dark"] .stx-subnav button:hover { background: #1b2740; }
        html[data-theme="dark"] .stx-subnav button.on { background: #12332c; color: #3ddbb0; }
        html[data-theme="dark"] .bill-notice.info { background: #1b2740; color: #cbd5e1; }
        html[data-theme="dark"] .bill-notice.ok { background: #12332c; color: #3ddbb0; }
        html[data-theme="dark"] .bill-notice.err { background: #3a1a1f; color: #ff9aa2; }
        html[data-theme="dark"] .free-btn { background: #1b2740; border-color: #334155; color: #9fb0c3; }

        /* colours injected by app.js */
        html[data-theme="dark"] .sev-high, html[data-theme="dark"] .sev-critical { color: #ff8a93; background: rgba(255,107,107,.18); }
        html[data-theme="dark"] .sev-medium { color: #ffc46b; background: rgba(255,180,84,.18); }
        html[data-theme="dark"] .sev-low { color: #3ddbb0; background: rgba(61,219,176,.16); }
        html[data-theme="dark"] .st-new { color: #7db4ff; background: rgba(47,125,225,.2); }
        html[data-theme="dark"] .st-investigating, html[data-theme="dark"] .st-monitoring,
        html[data-theme="dark"] .st-open { color: #ffc46b; background: rgba(255,180,84,.18); }
        html[data-theme="dark"] .st-blocked { color: #ff8a93; background: rgba(255,107,107,.18); }
        html[data-theme="dark"] .st-resolved { color: #3ddbb0; background: rgba(61,219,176,.16); }
        html[data-theme="dark"] .st-false-positive { color: #aab6c5; background: #243049; }
        html[data-theme="dark"] .primary-button {
            background: linear-gradient(135deg, #2f7de1, #1c5fd1);
            box-shadow: 0 6px 16px rgba(47,125,225,.3);
        }
        html[data-theme="dark"] #ov-svg circle:first-child,
        html[data-theme="dark"] #tg-svg circle:first-child { stroke: #243049; }
'''

SWITCH_PANEL = '''
            <div class="panel" id="pay-switch" hidden>
                <div class="stx-row">
                    <div><b id="pay-switch-title">Payments are ON</b><small>Staff only. When off, customers cannot start a payment.</small></div>
                    <button type="button" class="btn-small" id="pay-switch-btn">Switch off</button>
                </div>
            </div>'''

BILLING_FUNCS = '''        function renderSwitch() {
            var box = $("pay-switch");
            box.hidden = !(me && me.is_platform && me.role === "admin");
            $("pay-switch-title").textContent = paymentsOn ? "Payments are ON" : "Payments are OFF";
            $("pay-switch-btn").textContent = paymentsOn ? "Switch off" : "Switch on";
        }

        function hidePayButtons() {
            Array.prototype.forEach.call(document.querySelectorAll(".pp-slot"), function (s) { s.style.display = "none"; });
        }

'''

BILLING_CHECK = '''
                paymentsOn = info.payments_enabled !== false;
                renderSwitch();
                if (!paymentsOn) {
                    window.__payfastReady = false;
                    drawPlans(info, false);
                    hidePayButtons();
                    say(me.is_platform ? "Payments are switched off. Customers cannot pay until you switch them on."
                                       : "Payments are temporarily unavailable. Please try again later.", "info");
                    billingReady = true;
                    return;
                }'''

BILLING_LISTENER = '''            $("pay-switch-btn").addEventListener("click", function () {
                api("/api/billing/payments-switch", { enabled: !paymentsOn }).then(function () {
                    billingReady = false;
                    openBilling();
                }).catch(function (problem) { say(problem.message, "err"); });
            });

'''

MOON_SCRIPT = '''<script>
(function () {
    var MOON = '<svg viewBox="0 0 24 24"><path d="M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z"/></svg>';
    var SUN = '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>';
    var root = document.documentElement, btn = document.getElementById("theme-toggle");
    function paint() { btn.innerHTML = root.getAttribute("data-theme") === "dark" ? SUN : MOON; }
    btn.addEventListener("click", function () {
        var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
        root.setAttribute("data-theme", next);
        try { localStorage.setItem("mt-theme", next); } catch (e) {}
        paint();
    });
    paint();
})();
</script>
'''

html = Patch("index.html", 'id="theme-toggle"')
if not html.skip:
    html.before(r'    <link rel="stylesheet" href="style\.css">', HEAD_SCRIPT, "index.html step 1: theme start script")
    html.after(r'<div class="user-area">', BUTTON, "index.html step 2: moon button")
    html.before(r'    </style>\n</head>', CSS, "index.html step 3: dark mode CSS")
    html.after(r'<div id="bill-message"></div>', SWITCH_PANEL, "index.html step 4: payment switch panel")
    html.after(r'        var billingReady = false;\n', '        var paymentsOn = true;\n', "index.html step 5: paymentsOn variable")
    html.before(r'[ \t]*function openBilling\(\) \{\s*\n\s*if \(billingReady\)', BILLING_FUNCS, "index.html step 6: switch functions")
    html.after(r'api\("/api/billing"\)\.then\(function \(info\) \{', BILLING_CHECK, "index.html step 7: payments-off check")
    html.before(r'[ \t]*\$\("plan-badge"\)\.addEventListener\("click"', BILLING_LISTENER, "index.html step 8: switch button listener")
    # moon script goes right before the last </body>
    idx = html.text.rfind("</body>")
    if idx == -1:
        html.errors.append("index.html step 9: </body> not found")
    else:
        html.text = html.text[:idx] + MOON_SCRIPT + html.text[idx:]

results = [app.save(), pf.save(), html.save()]
print()
if all(results):
    print("Done. Restart the server (cd backend ; python app.py) and press Ctrl+Shift+R in the browser.")
else:
    print("Some files were not changed. Send me the problem lines above and I will fix the anchors.")