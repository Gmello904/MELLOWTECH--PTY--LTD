"""MellowTech: dashboard makeover + search + new Sign out button + separate PayPal / PayFast switches.

Put this file in your MellowTech project folder (the one that holds index.html and internal.html),
then run:   python apply_dashboard_and_payment_switches.py

It patches index.html, internal.html, backend/app.py and backend/payfast.py.
A backup of each file is saved next to it as <name>.before-polish.bak.
If any step cannot find its place, NOTHING is written and the script tells you which step failed.
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def find(*names):
    for name in names:
        p = HERE / name
        if p.is_file():
            return p
    sys.exit("Could not find " + " or ".join(names) + " next to this script.")


FILES = {
    "index": find("index.html"),
    "internal": find("internal.html"),
    "app": find("backend/app.py", "app.py"),
    "payfast": find("backend/payfast.py", "payfast.py"),
}


def load(path):
    raw = path.read_bytes().decode("utf-8-sig") if path.suffix == ".py" else path.read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    return raw.replace("\r\n", "\n"), crlf


def rep(text, old, new, step):
    n = text.count(old)
    if n != 1:
        sys.exit(f"STEP FAILED ({step}): expected to find the anchor once, found {n} times. Nothing was changed.")
    return text.replace(old, new)


# =====================================================================  app.py
app, app_crlf = load(FILES["app"])

start = app.find("def payments_enabled():")
end_marker = 'return jsonify({"ok": True, "enabled": on})'
end = app.find(end_marker, start)
if start == -1 or end == -1:
    sys.exit("STEP FAILED (app.py payments switch block). Nothing was changed.")
end += len(end_marker)
app = app[:start] + '''PAYMENT_SERVICES = {"paypal": "PayPal", "payfast": "PayFast"}      # each one has its own switch in the Internal Portal


def payment_enabled(service):
    """True unless an employee switched this payment service off. PayPal and PayFast are independent."""
    row = get_db().execute("SELECT value FROM platform_settings WHERE key = ?", (service + "_enabled",)).fetchone()
    return not row or row["value"] != "0"


def payments_enabled():
    """True when at least one payment service is on."""
    return any(payment_enabled(key) for key in PAYMENT_SERVICES)''' + app[end:]

app = rep(app, 'STAFF_LEVELS = ("staff", "super_admin")',
          'STAFF_LEVELS = ("staff", "super_admin")\nPERMISSIONS["manage_payments"] = {"staff": True, "super_admin": True}      # employees can switch payment services on and off',
          "app.py permission")

app = rep(app, '"payments_enabled": payments_enabled(),',
          '"payments_enabled": payments_enabled(),\n'
          '                    "payments": {"paypal": payment_enabled("paypal"), "payfast": payment_enabled("payfast")},',
          "app.py billing info")

app = rep(app, 'if not payments_enabled():\n        return error("Payments are switched off right now. Please try again later.", 503)',
          'if not payment_enabled("paypal"):\n        return error("PayPal payments are switched off right now. Please try again later.", 503)',
          "app.py paypal create-order")

app = rep(app, "payments_enabled=payments_enabled,",
          'payments_enabled=lambda: payment_enabled("payfast"),', "app.py payfast hook")

app = rep(app, '@app.get("/api/internal/customers")\n@internal_required("view_customers")\ndef internal_customers():',
          '''@app.get("/api/internal/payments")
@internal_required("manage_payments")
def internal_payments():
    return jsonify({"services": [{"key": key, "name": name, "enabled": payment_enabled(key)}
                                 for key, name in PAYMENT_SERVICES.items()]})


@app.post("/api/internal/payments/<service>")
@internal_required("manage_payments")
def internal_payments_switch(service):
    """Employees only. Switches ONE payment service; the other one is not touched."""
    if service not in PAYMENT_SERVICES:
        return error("Unknown payment service.", 404)
    on = bool((request.get_json(silent=True) or {}).get("enabled"))
    db = get_db()
    db.execute("INSERT INTO platform_settings (key, value) VALUES (?, ?) "
               "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (service + "_enabled", "1" if on else "0"))
    db.commit()
    audit("payment_switched", PAYMENT_SERVICES[service] + (" on" if on else " off"), g.user["id"])
    return jsonify({"ok": True, "service": service, "enabled": on})


@app.get("/api/internal/customers")
@internal_required("view_customers")
def internal_customers():''', "app.py internal routes")

try:
    compile(app, "app.py", "exec")
except SyntaxError as exc:
    sys.exit(f"The patched app.py would have a syntax error ({exc}). Nothing was changed.")

# =====================================================================  payfast.py
pf, pf_crlf = load(FILES["payfast"])
pf = rep(pf, 'return error("Payfast is not connected yet.", 503)',
         'return error("Payfast is not connected yet.", 503)\n\n'
         '        payments_on = h.get("payments_enabled")\n'
         '        if callable(payments_on) and not payments_on():\n'
         '            return error("PayFast payments are switched off right now. Please try again later.", 503)',
         "payfast.py switch check")
compile(pf, "payfast.py", "exec")

# =====================================================================  internal.html
internal, internal_crlf = load(FILES["internal"])

internal = rep(internal, '''audit: '<path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5M9 13h7M9 17h7"/>\'''',
               '''audit: '<path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5M9 13h7M9 17h7"/>',
        payments: '<rect x="3" y="6" width="18" height="13" rx="2"/><path d="M3 10h18M7 15h4"/>\'''',
               "internal icon")

internal = rep(internal, '{ key: "view_audit_logs", label: "Audit log", icon: "audit", run: audit }',
               '{ key: "manage_payments", label: "Payments", icon: "payments", run: payments },\n'
               '        { key: "view_audit_logs", label: "Audit log", icon: "audit", run: audit }',
               "internal tab")

internal = rep(internal, "    var TABS = [", r'''    /* ------------------------------------------------ Payments: one independent switch per service */
    function payments() {
        return api("/api/internal/payments").then(function (d) {
            var grid = el("div", null, "pay-grid");
            d.services.forEach(function (s) {
                var card = el("div", null, "panel pay-card" + (s.enabled ? "" : " off"));
                var top = el("div", null, "pay-top"), title = el("div");
                title.appendChild(el("h4", s.name));
                title.appendChild(el("p", s.key === "paypal" ? "Card and PayPal payments, charged in US dollars." : "Card and PayShap payments, charged in rand.", "note"));
                top.appendChild(title);
                top.appendChild(badge(s.enabled ? "ON" : "OFF", s.enabled ? "green" : "red"));
                card.appendChild(top);
                card.appendChild(el("p", s.enabled
                    ? "Customers can start a " + s.name + " payment."
                    : "Customers cannot start a " + s.name + " payment. The other service is not affected.", "pay-state"));
                var want = !s.enabled;
                var btn = el("button", s.enabled ? "Switch off " + s.name : "Switch on " + s.name, s.enabled ? "btn danger" : "btn primary");
                btn.addEventListener("click", function () {
                    if (!want && !window.confirm("Switch off " + s.name + "? Customers will not be able to pay with it until you switch it on again.")) { return; }
                    btn.disabled = true;
                    api("/api/internal/payments/" + s.key, { enabled: want }).then(function () {
                        say(s.name + " is now " + (want ? "ON" : "OFF") + ".", "ok");
                        return payments();
                    }).catch(function (e) { say(e.message, "err"); btn.disabled = false; });
                });
                card.appendChild(btn);
                grid.appendChild(card);
            });
            show([heading("Payments", "Each payment service has its own switch. Switching one off never affects the other. Every change is saved in the audit log."), grid]);
        });
    }

    var TABS = [''', "internal function")

internal = rep(internal, "    @media (max-width: 1100px) { .hero, .duo",
               '''    .pay-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
    .pay-card { display: flex; flex-direction: column; gap: 14px; border-left: 4px solid var(--signal); }
    .pay-card.off { border-left-color: var(--coral); }
    .pay-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
    .pay-state { margin: 0; color: var(--muted); }
    .pay-card .btn { align-self: flex-start; }
    @media (max-width: 1100px) { .hero, .duo''', "internal css")

# --- internal portal: top search bar (pages + customers)
internal = rep(internal, '<main class="content"><div id="msg" role="status"></div>',
'<main class="content"><div class="topbar"><div class="isearch"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/></svg><input id="isearch-input" type="search" placeholder="Search pages and customers   ( / )" autocomplete="off" aria-label="Search the internal portal"><div id="isearch-res" class="isearch-res" hidden></div></div></div><div id="msg" role="status"></div>',
"internal search markup")

internal = rep(internal, "    @media (max-width: 1100px) { .hero, .duo",
r"""    .topbar { display: flex; justify-content: flex-end; margin: -10px 0 18px; position: relative; z-index: 20; }
    .isearch { position: relative; width: 380px; max-width: 100%; }
    .isearch svg { position: absolute; left: 13px; top: 50%; transform: translateY(-50%); width: 17px; height: 17px; fill: none; stroke: var(--muted); stroke-width: 2; stroke-linecap: round; pointer-events: none; }
    .isearch input { width: 100%; padding: 11px 14px 11px 40px; border-radius: 999px; background: rgba(255,255,255,.07); }
    .isearch input:focus { border-color: var(--signal); box-shadow: 0 0 0 3px rgba(31,214,164,.18); outline: none; }
    .isearch-res { position: absolute; top: calc(100% + 8px); left: 0; right: 0; background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 6px; box-shadow: 0 18px 40px rgba(0,0,0,.5); max-height: 380px; overflow: auto; }
    .isearch-res h6 { margin: 8px 10px 4px; font: 600 11px var(--body); letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
    .isearch-res button { display: block; width: 100%; text-align: left; background: none; border: 0; color: var(--text); padding: 9px 10px; border-radius: 9px; font: 400 14px var(--body); cursor: pointer; }
    .isearch-res button:hover, .isearch-res button.on { background: rgba(31,214,164,.14); }
    .isearch-res .none { padding: 12px; color: var(--muted); font-size: 14px; }
    @media (max-width: 1100px) { .hero, .duo""", "internal search css")

internal = rep(internal, "    function start() {\n        var nav = document.getElementById(\"tabs\"), first = true;",
r"""    /* ------------------------------------------------ search: pages and customers */
    function setupSearch() {
        var input = document.getElementById("isearch-input"), box = document.getElementById("isearch-res");
        var customerList = null, items = [], cur = -1;
        function close() { box.hidden = true; cur = -1; }
        function mark() { Array.prototype.forEach.call(box.querySelectorAll("button"), function (b, i) { b.className = i === cur ? "on" : ""; }); }
        function draw() {
            var q = input.value.trim().toLowerCase();
            box.textContent = ""; items = []; cur = -1;
            if (!q) { close(); return; }
            var pages = TABS.filter(function (t) { return t.btn && t.label.toLowerCase().indexOf(q) !== -1; });
            var firms = (customerList || []).filter(function (c) { return c.name.toLowerCase().indexOf(q) !== -1; }).slice(0, 8);
            function add(label, fn) {
                var b = el("button", label); b.type = "button";
                b.addEventListener("mousedown", function (e) { e.preventDefault(); input.value = ""; close(); fn(); });
                box.appendChild(b); items.push(b);
            }
            if (pages.length) { box.appendChild(el("h6", "Pages")); pages.forEach(function (t) { add(t.label, function () { t.btn.click(); }); }); }
            if (firms.length) { box.appendChild(el("h6", "Customers")); firms.forEach(function (c) { add(c.name, function () { customerDetail(c.id); }); }); }
            if (!items.length) { box.appendChild(el("div", "Nothing found for “" + input.value.trim() + "”", "none")); }
            box.hidden = false;
        }
        input.addEventListener("focus", function () {
            if (customerList === null && perms.view_customers) {
                customerList = [];
                api("/api/internal/customers").then(function (l) { customerList = l; draw(); }).catch(function () {});
            }
        });
        input.addEventListener("input", draw);
        input.addEventListener("keydown", function (e) {
            if (e.key === "ArrowDown") { e.preventDefault(); if (items.length) { cur = (cur + 1) % items.length; mark(); } }
            else if (e.key === "ArrowUp") { e.preventDefault(); if (items.length) { cur = (cur - 1 + items.length) % items.length; mark(); } }
            else if (e.key === "Enter") { e.preventDefault(); var t = items[cur >= 0 ? cur : 0]; if (t) { t.dispatchEvent(new MouseEvent("mousedown")); } }
            else if (e.key === "Escape") { input.value = ""; close(); input.blur(); }
        });
        input.addEventListener("blur", function () { setTimeout(close, 120); });
        document.addEventListener("keydown", function (e) {
            var tag = (document.activeElement && document.activeElement.tagName) || "";
            if ((e.key === "/" && !/INPUT|TEXTAREA|SELECT/.test(tag)) || ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k")) { e.preventDefault(); input.focus(); input.select(); }
        });
    }

    function start() {
        var nav = document.getElementById("tabs"), first = true;
        setupSearch();""", "internal search js")

internal = rep(internal, "            nav.appendChild(b);\n            if (first)", "            tab.btn = b;\n            nav.appendChild(b);\n            if (first)", "internal tab btn")

# =====================================================================  index.html
index, index_crlf = load(FILES["index"])

# --- 1. remove the customer-facing switch
index, n = re.subn(r'<div class="panel" id="pay-switch" hidden>.*?</button>\s*</div>\s*</div>', "", index, count=1, flags=re.S)
if n != 1:
    sys.exit("STEP FAILED (index.html pay-switch panel). Nothing was changed.")

# --- 2. billing script: per-service switches, no staff switch
index = rep(index, "/* Edit these lists to describe what each plan includes. */",
            '''var ppNote = "Available once PayPal is connected";
        var pfNote = "Available once Payfast is connected";
        var lastKey = "";

        /* Edit these lists to describe what each plan includes. */''', "index vars")
index = rep(index, """'<p class="pp-note">Available once PayPal is connected</p>'""",
            """'<p class="pp-note">' + ppNote + '</p>'""", "index paypal note")
index = rep(index, """'<p class="pp-note">Available once Payfast is connected</p>'""",
            """'<p class="pp-note">' + pfNote + '</p>'""", "index payfast note")

s = index.find("function renderSwitch() {")
e = index.find('document.addEventListener("DOMContentLoaded"', s)
if s == -1 or e == -1:
    sys.exit("STEP FAILED (index.html openBilling block). Nothing was changed.")
index = index[:s] + r'''function openBilling() {
            if (!billingReady) { say("Loading plans...", "info"); }
            api("/api/billing").then(function (info) {
                var on = info.payments || { paypal: info.payments_enabled !== false, payfast: info.payments_enabled !== false };
                var isAdmin = me.role === "admin";
                var ppOk = !!(on.paypal && info.paypal_client_id && isAdmin);
                var pfWanted = !!(on.payfast && isAdmin);
                ppNote = !on.paypal ? "PayPal is temporarily unavailable"
                       : !info.paypal_client_id ? "Available once PayPal is connected"
                       : !isAdmin ? "Only an account administrator can pay" : "";
                pfNote = !on.payfast ? "Payfast is temporarily unavailable"
                       : !isAdmin ? "Only an account administrator can pay" : "Available once Payfast is connected";

                var key = JSON.stringify([on, me.plan, info.paypal_client_id, isAdmin]);
                if (billingReady && key === lastKey) { return; }       /* nothing changed since the last visit */

                var check = pfWanted
                    ? api("/api/payfast/ready").then(function (pf) { window.__payfastReady = !!pf.ready; })
                          .catch(function () { window.__payfastReady = false; })
                    : Promise.resolve().then(function () { window.__payfastReady = false; });

                return check.then(function () {
                    return ppOk ? loadPayPal(info.paypal_client_id, info.currency) : null;
                }).then(function () {
                    drawPlans(info, ppOk);
                    if (!on.paypal && !on.payfast) {
                        say("Payments are temporarily unavailable. Please try again later.", "info");
                    } else if (!isAdmin) {
                        say("Only an account administrator can buy or change a plan.", "info");
                    } else if (!info.paypal_client_id && me.is_platform) {
                        say("PayPal is not connected yet. Put <code>PAYPAL_CLIENT_ID</code> and <code>PAYPAL_SECRET</code> in " +
                            "<code>backend/settings.env</code>, then restart <code>python app.py</code>.", "info", true);
                    } else {
                        say("", "info");
                    }
                    lastKey = key;
                    billingReady = true;
                });
            }).catch(function (problem) {
                say(problem.message, "err");
            });
        }

        ''' + index[e:]

index, n = re.subn(r'\s*\$\("pay-switch-btn"\)\.addEventListener\("click", function \(\) \{.*?\}\)\.catch\(function \(problem\) \{ say\(problem\.message, "err"\); \}\);\s*\}\);',
                   "\n", index, count=1, flags=re.S)
if n != 1:
    sys.exit("STEP FAILED (index.html old switch listener). Nothing was changed.")

# --- 3. header: search + new sign out button
index = rep(index, '<symbol id="i-refresh"',
            '<symbol id="i-search" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></symbol>\n        <symbol id="i-refresh"',
            "index search icon")

index = rep(index, '<div class="user-area">', '''<div class="mt-search" id="mt-search" role="search">
                <svg class="icon" aria-hidden="true"><use href="#i-search"/></svg>
                <input type="search" id="mt-search-input" placeholder="Search pages, alerts, devices..." autocomplete="off" aria-label="Search the platform">
                <kbd title="Press / to search">/</kbd>
                <div class="mt-search-results" id="mt-search-results" hidden></div>
            </div>
            <div class="user-area">''', "index search box")

index = rep(index, '<svg class="icon" aria-hidden="true"><use href="#i-logout"/></svg>Sign out',
            '<span class="lo-ico"><svg class="icon" aria-hidden="true"><use href="#i-logout"/></svg></span><span>Sign out</span>',
            "index sign out")

# --- 4. dashboard hero
index, n = re.subn(r'<h2>Security Dashboard</h2>\s*<p class="page-description">.*?</p>', '''<div class="dh-hero">
                <div class="dh-left">
                    <span class="dh-eyebrow"><i></i><span id="dh-greet">Welcome back</span></span>
                    <h2>Security Dashboard</h2>
                    <p>Monitor your cybersecurity environment from one central dashboard.</p>
                    <div class="dh-actions">
                        <button type="button" class="dh-btn primary" onclick="runScan()">Run security scan</button>
                        <button type="button" class="dh-btn" data-goto="threats">View alerts</button>
                        <button type="button" class="dh-btn" data-goto="devices">My devices</button>
                    </div>
                    <div class="dh-meta"><span id="dh-date"></span><span id="dh-time"></span></div>
                </div>
                <div class="dh-shield" aria-hidden="true">
                    <div class="dh-ring r1"></div><div class="dh-ring r2"></div><div class="dh-ring r3"></div>
                    <svg viewBox="0 0 24 24"><path d="M12 2l9 3v7c0 5.5-3.8 8.6-9 10-5.2-1.4-9-4.5-9-10V5z"/><path d="M8 12l3 3 5-6"/></svg>
                    <div class="dh-level"><small>THREAT LEVEL</small><b id="dh-level">Secure</b></div>
                </div>
            </div>''', index, count=1, flags=re.S)
if n != 1:
    sys.exit("STEP FAILED (index.html dashboard heading). Nothing was changed.")

# --- 5. CSS
CSS = r'''
    <style id="mt-polish">
        /* ===== MellowTech polish: header, search, sign out, dashboard ===== */
        body { background: radial-gradient(900px 500px at 8% -5%, rgba(47,125,225,.10), transparent 60%), radial-gradient(800px 500px at 100% 0, rgba(61,219,176,.10), transparent 55%), var(--bg); background-attachment: fixed; }
        html[data-theme="dark"] body { background: radial-gradient(900px 500px at 8% -5%, rgba(47,125,225,.14), transparent 60%), radial-gradient(800px 500px at 100% 0, rgba(61,219,176,.08), transparent 55%), #0b1220; }

        .topbar { position: sticky; top: 12px; z-index: 60; display: grid; grid-template-columns: auto minmax(220px, 1fr) auto; gap: 22px; align-items: center;
            padding: 14px 20px 14px 24px; background: rgba(255,255,255,.84); backdrop-filter: blur(14px) saturate(1.4); -webkit-backdrop-filter: blur(14px) saturate(1.4);
            border: 1px solid rgba(227,233,240,.9); border-radius: 18px; box-shadow: 0 10px 30px rgba(15,34,54,.08); }
        html[data-theme="dark"] .topbar { background: rgba(17,26,46,.86); border-color: #243049; box-shadow: 0 10px 30px rgba(0,0,0,.35); }
        .topbar h1 { font-size: 24px; font-weight: 800; letter-spacing: .2px; background: linear-gradient(90deg, #0d1b2a, #2f7de1 70%, #3ddbb0); -webkit-background-clip: text; background-clip: text; color: transparent; }
        html[data-theme="dark"] .topbar h1 { background: linear-gradient(90deg, #fff, #7db4ff 70%, #3ddbb0); -webkit-background-clip: text; background-clip: text; }

        /* search */
        .mt-search { position: relative; width: 100%; max-width: 480px; justify-self: center; }
        .mt-search > .icon { position: absolute; left: 14px; top: 50%; transform: translateY(-50%); width: 18px; height: 18px; color: #7b8794; pointer-events: none; }
        .mt-search input { width: 100%; padding: 11px 46px 11px 42px; border-radius: 999px; border: 1.5px solid #e1e8f0; background: #f4f7fb; font-size: 14px; font-family: inherit; color: inherit; transition: border-color .15s, box-shadow .15s, background .15s; }
        .mt-search input:focus { outline: none; background: #fff; border-color: #3ddbb0; box-shadow: 0 0 0 4px rgba(61,219,176,.22); }
        .mt-search kbd { position: absolute; right: 12px; top: 50%; transform: translateY(-50%); font: 700 11px "Segoe UI", sans-serif; padding: 2px 8px; border-radius: 6px; border: 1px solid #d5dce3; color: #68737d; background: #fff; pointer-events: none; }
        .mt-search-results { position: absolute; left: 0; right: 0; top: calc(100% + 10px); z-index: 80; padding: 8px; max-height: 62vh; overflow: auto; background: #fff; border: 1px solid #e3e9f0; border-radius: 16px; box-shadow: 0 24px 50px rgba(15,34,54,.2); }
        .sr-group { padding: 8px 10px 4px; font-size: 11px; font-weight: 800; letter-spacing: 1.2px; color: #7b8794; text-transform: uppercase; }
        .sr-item { display: flex; flex-direction: column; align-items: flex-start; gap: 1px; width: 100%; padding: 9px 12px; border: 0; border-radius: 10px; background: transparent; text-align: left; cursor: pointer; font-family: inherit; color: #17202a; }
        .sr-item b { font-size: 14px; }
        .sr-item small { font-size: 12px; color: #68737d; }
        .sr-item:hover, .sr-item.on { background: #e6f7f1; }
        .sr-empty { padding: 14px; font-size: 14px; color: #68737d; }
        html[data-theme="dark"] .mt-search input { background: #0f172a; border-color: #334155; }
        html[data-theme="dark"] .mt-search input:focus { background: #111a2e; }
        html[data-theme="dark"] .mt-search kbd { background: #111a2e; border-color: #334155; color: #9fb0c3; }
        html[data-theme="dark"] .mt-search-results { background: #111a2e; border-color: #243049; }
        html[data-theme="dark"] .sr-item { color: #e5e7eb; }
        html[data-theme="dark"] .sr-item small, html[data-theme="dark"] .sr-empty { color: #9fb0c3; }
        html[data-theme="dark"] .sr-item:hover, html[data-theme="dark"] .sr-item.on { background: #12332c; }

        /* sign out */
        .logout-button { padding: 5px 18px 5px 5px; gap: 10px; border: 0; border-radius: 999px; background: linear-gradient(135deg, #17304b, #0b1727); color: #fff; box-shadow: 0 6px 16px rgba(11,23,39,.28); }
        .logout-button .lo-ico { width: 32px; height: 32px; border-radius: 50%; display: grid; place-items: center; background: linear-gradient(135deg, #ff6b78, #c62f3b); transition: transform .25s, background .25s; }
        .logout-button .lo-ico .icon { width: 16px; height: 16px; stroke: #fff; }
        .logout-button:hover { background: linear-gradient(135deg, #c62f3b, #8b2635); color: #fff; transform: translateY(-1px); box-shadow: 0 10px 22px rgba(139,38,53,.4); }
        .logout-button:hover .lo-ico { transform: translateX(3px); background: rgba(255,255,255,.22); }
        html[data-theme="dark"] .logout-button { background: linear-gradient(135deg, #1b2740, #111a2e); border: 1px solid #2b3a57; color: #fff; }
        html[data-theme="dark"] .logout-button:hover { background: linear-gradient(135deg, #c62f3b, #8b2635); border-color: transparent; }

        /* dashboard hero */
        .dh-hero { position: relative; display: grid; grid-template-columns: 1.5fr 1fr; gap: 24px; align-items: center; margin-bottom: 22px; padding: 32px 36px; overflow: hidden; border-radius: 22px; color: #eaf2fb;
            background: radial-gradient(520px 320px at 100% 0, rgba(61,219,176,.24), transparent 65%), radial-gradient(460px 300px at 0 100%, rgba(74,168,255,.26), transparent 65%), linear-gradient(150deg, #0f2236 0%, #08121f 100%);
            box-shadow: 0 18px 44px rgba(8,18,31,.35), inset 0 0 0 1px rgba(255,255,255,.06); }
        .dh-hero::before { content: ""; position: absolute; inset: 0; pointer-events: none; background-image: linear-gradient(rgba(143,166,191,.07) 1px, transparent 1px), linear-gradient(90deg, rgba(143,166,191,.07) 1px, transparent 1px); background-size: 44px 44px; -webkit-mask-image: radial-gradient(ellipse at 75% 50%, #000 15%, transparent 75%); mask-image: radial-gradient(ellipse at 75% 50%, #000 15%, transparent 75%); }
        .dh-hero > * { position: relative; }
        .dh-eyebrow { display: inline-flex; align-items: center; gap: 8px; padding: 5px 13px; border-radius: 999px; font-size: 11px; font-weight: 800; letter-spacing: 1.5px; text-transform: uppercase; color: #3ddbb0; background: rgba(61,219,176,.1); border: 1px solid rgba(61,219,176,.35); }
        .dh-eyebrow i { width: 7px; height: 7px; border-radius: 50%; background: #3ddbb0; animation: dhPulse 2s infinite; }
        @keyframes dhPulse { 0% { box-shadow: 0 0 0 0 rgba(61,219,176,.6); } 70% { box-shadow: 0 0 0 8px rgba(61,219,176,0); } 100% { box-shadow: 0 0 0 0 rgba(61,219,176,0); } }
        .dh-hero h2 { margin: 14px 0 6px; font-size: 36px; line-height: 1.05; font-weight: 800; letter-spacing: -.5px; color: #fff; }
        .dh-hero p { margin: 0 0 20px; max-width: 48ch; font-size: 15px; color: #9fb4c9; }
        .dh-actions { display: flex; flex-wrap: wrap; gap: 10px; }
        .dh-btn { padding: 11px 18px; border-radius: 12px; border: 1px solid rgba(255,255,255,.22); background: rgba(255,255,255,.08); color: #fff; font-family: inherit; font-size: 14px; font-weight: 700; cursor: pointer; transition: transform .15s, background .15s, box-shadow .15s; }
        .dh-btn:hover { background: rgba(255,255,255,.16); transform: translateY(-1px); }
        .dh-btn.primary { border: 0; color: #07111d; background: linear-gradient(135deg, #3ddbb0, #2f7de1); box-shadow: 0 8px 20px rgba(47,125,225,.4); }
        .dh-btn.primary:hover { background: linear-gradient(135deg, #5be6c2, #4a93f0); }
        .dh-meta { display: flex; flex-wrap: wrap; gap: 6px 18px; margin-top: 18px; font-size: 13px; color: #8fa6bf; }
        .dh-meta span:last-child { font-variant-numeric: tabular-nums; color: #cfe0f0; font-weight: 600; }
        .dh-shield { position: relative; display: grid; place-items: center; width: 100%; max-width: 250px; aspect-ratio: 1; margin: 0 auto; }
        .dh-shield > svg { position: relative; width: 92px; height: 92px; fill: rgba(61,219,176,.12); stroke: #3ddbb0; stroke-width: 1.4; stroke-linecap: round; stroke-linejoin: round; filter: drop-shadow(0 0 14px rgba(61,219,176,.7)); }
        .dh-ring { position: absolute; inset: 0; border-radius: 50%; border: 1px solid rgba(61,219,176,.35); animation: dhRing 4.5s ease-out infinite; }
        .dh-ring.r2 { animation-delay: 1.5s; }
        .dh-ring.r3 { animation-delay: 3s; }
        @keyframes dhRing { from { transform: scale(.45); opacity: .9; } to { transform: scale(1); opacity: 0; } }
        .dh-level { position: absolute; bottom: 6px; left: 0; right: 0; text-align: center; }
        .dh-level small { display: block; font-size: 10px; letter-spacing: 1.6px; color: #7f96ad; }
        .dh-level b { font-size: 22px; font-weight: 800; color: #3ddbb0; }

        /* stat cards */
        #dashboard .stat-card { padding: 22px 24px; border-radius: 18px; background: linear-gradient(180deg, #fff, #f6f9fc); }
        #dashboard .stat-card strong { font-size: 38px; letter-spacing: -1px; }
        #dashboard .stat-card .dh-ico { position: absolute; right: 18px; top: 18px; width: 44px; height: 44px; border-radius: 14px; display: grid; place-items: center; background: rgba(47,125,225,.12); color: #2f7de1; }
        #dashboard .stat-card:nth-child(2) .dh-ico { background: rgba(139,92,246,.13); color: #8b5cf6; }
        #dashboard .stat-card:nth-child(3) .dh-ico { background: rgba(198,47,59,.12); color: #c62f3b; }
        #dashboard .stat-card:nth-child(4) .dh-ico { background: rgba(18,144,110,.13); color: #12906e; }
        #dashboard .stat-card .dh-ico svg { width: 22px; height: 22px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
        html[data-theme="dark"] #dashboard .stat-card { background: linear-gradient(180deg, #131d33, #0f1829); }

        /* cards and panels */
        #dashboard .ov-card, #dashboard .panel { border-radius: 18px; transition: transform .2s, box-shadow .2s; }
        #dashboard .ov-card:hover, #dashboard .panel:hover { transform: translateY(-2px); box-shadow: 0 14px 32px rgba(15,34,54,.11); }
        #dashboard .panel h3 { position: relative; padding-left: 14px; }
        #dashboard .panel h3::before { content: ""; position: absolute; left: 0; top: 4px; bottom: 4px; width: 4px; border-radius: 4px; background: linear-gradient(180deg, #3ddbb0, #2f7de1); }
        #activity-feed .activity-item { position: relative; padding-left: 26px; }
        #activity-feed .activity-item::before { content: ""; position: absolute; left: 4px; top: 20px; width: 10px; height: 10px; border-radius: 50%; background: #fff; border: 2px solid #3ddbb0; }
        html[data-theme="dark"] #activity-feed .activity-item::before { background: #111a2e; }

        /* entrance */
        @keyframes dhRise { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: none; } }
        #dashboard > * { animation: dhRise .6s cubic-bezier(.22,1,.36,1) both; }
        #dashboard > *:nth-child(2) { animation-delay: .06s; }
        #dashboard > *:nth-child(3) { animation-delay: .12s; }
        #dashboard > *:nth-child(4) { animation-delay: .18s; }
        #dashboard > *:nth-child(5) { animation-delay: .24s; }

        @media (max-width: 1100px) {
            .topbar { grid-template-columns: 1fr auto; }
            .mt-search { grid-column: 1 / -1; order: 3; max-width: none; }
            .dh-hero { grid-template-columns: 1fr; }
            .dh-shield { max-width: 190px; }
        }
        @media (max-width: 760px) { .dh-hero { padding: 24px; } .dh-hero h2 { font-size: 28px; } .logout-button span:last-child { display: none; } .logout-button { padding-right: 5px; } }
    </style>
</head>'''
index = rep(index, "</head>", CSS.lstrip("\n"), "index css")

# --- 6. JS
JS = r'''
<!-- Dashboard polish: greeting, stat icons, search -->
<script>
(function () {
    function $(id) { return document.getElementById(id); }
    function esc(v) { return String(v == null ? "" : v).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }

    /* greeting, date and clock */
    function tick() {
        var now = new Date(), h = now.getHours();
        var word = h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
        var who = ($("logged-user") ? $("logged-user").textContent : "").replace(/\s*\(.*$/, "").replace(/,.*$/, "").trim();
        if ($("dh-greet")) { $("dh-greet").textContent = word + (who && who !== "Admin" ? ", " + who : ""); }
        if ($("dh-date")) { $("dh-date").textContent = now.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long", year: "numeric" }); }
        if ($("dh-time")) { $("dh-time").textContent = now.toLocaleTimeString(); }
        var src = $("ov-level"), dst = $("dh-level");
        if (src && dst) {
            dst.textContent = src.textContent;
            dst.style.color = { "Secure": "#3ddbb0", "Elevated": "#ffb454", "High": "#ff7a3d", "Critical": "#ff5b66" }[src.textContent] || "#3ddbb0";
        }
    }
    tick();
    setInterval(tick, 1000);

    /* icons on the four stat cards */
    var icons = ["i-laptop", "i-list", "i-flame", "i-shield"];
    document.querySelectorAll("#dashboard .stats-grid .stat-card").forEach(function (card, i) {
        if (card.querySelector(".dh-ico") || !icons[i]) { return; }
        var s = document.createElement("span");
        s.className = "dh-ico";
        s.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><use href="#' + icons[i] + '"/></svg>';
        card.appendChild(s);
    });

    /* search: pages, alerts and devices */
    var input = $("mt-search-input"), box = $("mt-search-results"), items = [], active = -1;
    if (!input || !box) { return; }

    function label(btn) {
        return Array.prototype.filter.call(btn.childNodes, function (n) { return n.nodeType === 3; })
            .map(function (n) { return n.textContent; }).join("").trim();
    }
    function go(page) {
        var b = document.querySelector('.nav-button[data-page="' + page + '"]');
        if (b) { b.click(); }
        close();
        input.value = "";
        input.blur();
    }
    function close() { box.hidden = true; active = -1; }
    function mark() {
        Array.prototype.forEach.call(box.querySelectorAll(".sr-item"), function (el, i) { el.classList.toggle("on", i === active); });
    }

    function gather(q) {
        var out = [];
        Array.prototype.filter.call(document.querySelectorAll(".nav-button"), function (b) {
            return !b.hidden && b.dataset.page && label(b).toLowerCase().indexOf(q) !== -1;
        }).slice(0, 7).forEach(function (b) { out.push({ group: "Pages", title: label(b), sub: "Open page", page: b.dataset.page }); });
        if (q) {
            var ev = (typeof lastEvents !== "undefined" && Array.isArray(lastEvents)) ? lastEvents : [];
            ev.filter(function (e) { return [e.type, e.device, e.id, e.severity, e.status, e.source_ip].join(" ").toLowerCase().indexOf(q) !== -1; })
              .slice(0, 5).forEach(function (e) { out.push({ group: "Alerts and events", title: e.type, sub: [e.device, e.severity, e.status].join(" \u00b7 "), page: "threats" }); });
            var dv = (typeof lastDevices !== "undefined" && Array.isArray(lastDevices)) ? lastDevices : [];
            dv.filter(function (d) { return [d.name, d.ip, d.os].join(" ").toLowerCase().indexOf(q) !== -1; })
              .slice(0, 5).forEach(function (d) { out.push({ group: "Devices", title: d.name, sub: [d.os, d.ip, d.online ? "Online" : "Offline"].join(" \u00b7 "), page: "devices" }); });
        }
        return out;
    }

    function render() {
        var q = input.value.trim().toLowerCase();
        items = gather(q);
        active = items.length ? 0 : -1;
        var html = "", last = "";
        if (!items.length) { html = '<div class="sr-empty">No matches for \u201c' + esc(input.value.trim()) + '\u201d.</div>'; }
        items.forEach(function (it, i) {
            if (it.group !== last) { html += '<div class="sr-group">' + esc(it.group) + "</div>"; last = it.group; }
            html += '<button type="button" class="sr-item" data-i="' + i + '"><b>' + esc(it.title) + "</b><small>" + esc(it.sub) + "</small></button>";
        });
        box.innerHTML = html;
        box.hidden = false;
        mark();
    }

    input.addEventListener("focus", render);
    input.addEventListener("input", render);
    input.addEventListener("keydown", function (e) {
        if (e.key === "ArrowDown") { e.preventDefault(); if (items.length) { active = (active + 1) % items.length; mark(); } }
        else if (e.key === "ArrowUp") { e.preventDefault(); if (items.length) { active = (active - 1 + items.length) % items.length; mark(); } }
        else if (e.key === "Enter") { e.preventDefault(); if (items[active]) { go(items[active].page); } }
        else if (e.key === "Escape") { close(); input.blur(); }
    });
    box.addEventListener("click", function (e) {
        var b = e.target.closest("[data-i]");
        if (b && items[Number(b.dataset.i)]) { go(items[Number(b.dataset.i)].page); }
    });
    document.addEventListener("click", function (e) {
        if (!e.target.closest("#mt-search")) { close(); }
        var g = e.target.closest("[data-goto]");
        if (g) { go(g.dataset.goto); }
    });
    document.addEventListener("keydown", function (e) {
        var tag = (document.activeElement && document.activeElement.tagName) || "";
        var typing = /INPUT|TEXTAREA|SELECT/.test(tag);
        if ((e.key === "/" && !typing) || ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k")) { e.preventDefault(); input.focus(); input.select(); }
    });
})();
</script>
'''
index = index[:index.rindex("</body>")] + JS.lstrip("\n") + index[index.rindex("</body>"):]

# =====================================================================  write everything
def save(path, text, crlf):
    backup = path.with_name(path.name + ".before-polish.bak")
    if not backup.exists():
        backup.write_bytes(path.read_bytes())
    path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
    print("patched", path.relative_to(HERE))


save(FILES["app"], app, app_crlf)
save(FILES["payfast"], pf, pf_crlf)
save(FILES["internal"], internal, internal_crlf)
save(FILES["index"], index, index_crlf)
print("\nDone. Restart the server (python app.py), then press Ctrl+Shift+R in the browser.")