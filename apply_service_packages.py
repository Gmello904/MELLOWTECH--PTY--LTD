"""MellowTech: group the security services into packages, locked until the package is paid for.

Run AFTER apply_dashboard_and_payment_switches.py. Put this file in the project folder (next to index.html)
and run:  python apply_service_packages.py
Patches index.html, backend/app.py and backend/services.py. Backups: *.before-packages.bak
Nothing is written unless every step succeeds.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def find(*names):
    for n in names:
        p = HERE / n
        if p.is_file():
            return p
    sys.exit("Could not find " + " or ".join(names) + " next to this script.")


FILES = {"index": find("index.html"), "app": find("backend/app.py", "app.py"),
         "services": find("backend/services.py", "services.py")}


def load(path):
    raw = path.read_bytes().decode("utf-8-sig") if path.suffix == ".py" else path.read_bytes().decode("utf-8")
    return raw.replace("\r\n", "\n"), "\r\n" in raw


def rep(text, old, new, step):
    n = text.count(old)
    if n != 1:
        sys.exit(f"STEP FAILED ({step}): expected the anchor once, found {n} times. Nothing was changed.")
    return text.replace(old, new)


# ===================================================================== app.py
app, app_crlf = load(FILES["app"])
if "SERVICE_PLANS" in app:
    sys.exit("backend/app.py already has SERVICE_PLANS. This script was already applied. Nothing was changed.")

app = rep(app, 'PLAN_ORDER = {"free": 0, "starter": 1, "business": 2, "enterprise": 3}\n',
'''PLAN_ORDER = {"free": 0, "starter": 1, "business": 2, "enterprise": 3}

# Which package unlocks which security service. Higher packages include everything in the lower ones.
# Change the package on any line to move a service; restart the server and it applies everywhere.
SERVICE_PLANS = {
    "incident_response": "starter",
    "grc_compliance":    "starter",
    "cloud_security":    "business",
    "soc_monitoring":    "business",
    "ai_security":       "enterprise",
}
SERVICE_LABELS = {
    "incident_response": "Incident Response",
    "grc_compliance":    "Compliance and Risk (GRC)",
    "cloud_security":    "Cloud Security",
    "soc_monitoring":    "Security Monitoring (SOC)",
    "ai_security":       "AI Security",
}
for _key, _plan in SERVICE_PLANS.items():
    FEATURE_PLANS["svc_" + _key] = (_plan, SERVICE_LABELS[_key])
''', "app.py service plans")

app = rep(app, '''"zar_month": f"{Decimal(v['price']) * USD_ZAR_RATE:.2f}"} for k, v in PLANS.items()]})''',
'''"zar_month": f"{Decimal(v['price']) * USD_ZAR_RATE:.2f}",
                               "services": [SERVICE_LABELS[s] for s, p in SERVICE_PLANS.items() if p == k]}
                              for k, v in PLANS.items()]})''', "app.py billing services")

app = rep(app, "login_required=login_required, audit=audit, too_many=too_many, locked=locked, notify_staff=notify_staff))",
"login_required=login_required, audit=audit, too_many=too_many, locked=locked, notify_staff=notify_staff,\n"
"    feature_allowed=feature_allowed, service_plans=SERVICE_PLANS,\n"
"    plan_info={k: {\"name\": v[\"name\"], \"price\": v[\"price\"]} for k, v in PLANS.items()}))", "app.py services init")
compile(app, "app.py", "exec")

# ===================================================================== services.py
sv, sv_crlf = load(FILES["services"])
sv = rep(sv, 'locked, notify_staff = deps["locked"], deps["notify_staff"]\n',
'''locked, notify_staff = deps["locked"], deps["notify_staff"]
    feature_allowed, service_plans, plan_info = deps["feature_allowed"], deps["service_plans"], deps["plan_info"]

    def package_lock(key):
        """A 402 reply when the company's plan does not include this service, else None. MellowTech staff are never locked."""
        need = service_plans.get(key)
        if not need or feature_allowed(g.user["org_id"], "svc_" + key):
            return None
        name = plan_info.get(need, {}).get("name", need.title())
        audit("feature_locked", f"{g.user['org_name']} ({g.user['email']}) tried the {by_key[key]['name']} service; it needs {name}")
        return jsonify({"error": f"{by_key[key]['name']} is part of {name}. Pay for that package in Billing & Plans to unlock it.",
                        "locked": True, "needs": need}), 402
''', "services deps")

sv = rep(sv, '''"extra": s["extra"], "questions": [q for q, _ in s["questions"]],
                         "last": last.get(s["key"])} for s in SERVICES])''',
'''"extra": s["extra"], "questions": [q for q, _ in s["questions"]],
                         "last": last.get(s["key"]),
                         "needs": service_plans.get(s["key"], ""),
                         "package": plan_info.get(service_plans.get(s["key"], ""), {}).get("name", ""),
                         "price": plan_info.get(service_plans.get(s["key"], ""), {}).get("price", ""),
                         "unlocked": feature_allowed(g.user["org_id"], "svc_" + s["key"]) if s["key"] in service_plans else True}
                        for s in SERVICES])''', "services list")

sv = rep(sv, '        answers = data.get("answers")\n',
'''        denied = package_lock(service["key"])
        if denied:
            return denied
        answers = data.get("answers")
''', "services check lock")

sv = rep(sv, '        urgent = service["key"] == "incident_response" and bool(data.get("urgent"))\n',
'''        urgent = service["key"] == "incident_response" and bool(data.get("urgent"))
        if not urgent:                       # an urgent incident report is always allowed, even on the Free plan
            denied = package_lock(service["key"])
            if denied:
                return denied
''', "services request lock")
compile(sv, "services.py", "exec")

# ===================================================================== index.html
ix, ix_crlf = load(FILES["index"])

ix = rep(ix, '''            var top = $("svc-top-" + s.key);
            if (!top) { return; }
            var last = s.last''', '''            var top = $("svc-top-" + s.key);
            if (!top) { return; }
            if (s.unlocked === false) { drawLocked(s, top); return; }
            if ($("svc-form-" + s.key) && top.getAttribute("data-was-locked")) { top.removeAttribute("data-was-locked"); }
            var last = s.last''', "index drawService")

ix = rep(ix, "        function drawService(s) {", r'''        var PKG_ORDER = { starter: 1, business: 2, enterprise: 3 };

        function drawLocked(s, top) {
            var same = services.filter(function (x) { return x.needs === s.needs; });
            var admin = me && me.role === "admin";
            var form = $("svc-form-" + s.key);
            if (form) { form.innerHTML = ""; }
            var msg = $("svc-msg-" + s.key);
            if (msg) { msg.textContent = ""; }
            top.setAttribute("data-was-locked", "1");
            top.innerHTML = '<div class="panel svc-lockbox">' +
                '<div class="svc-lockicon"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg></div>' +
                "<h3>" + esc(s.name) + " is locked</h3>" +
                "<p>This service is part of <b>" + esc(s.package) + "</b>" +
                (s.price ? " ($" + esc(s.price) + " / month)" : "") + ". It unlocks as soon as your payment goes through.</p>" +
                '<p class="svc-lockhead">Also in this package</p><ul class="svc-locklist">' +
                same.map(function (x) { return "<li>" + esc(x.name) + "</li>"; }).join("") + "</ul>" +
                '<div class="actions" style="margin-top:14px">' +
                (admin ? '<button type="button" class="btn-small svc-unlock" data-svc-open="billing">Unlock with ' + esc(s.package) + "</button>"
                       : '<p class="rl-skills">Ask your account administrator to pay for this package.</p>') +
                "</div></div>";
        }

        function markNav() {
            services.forEach(function (s) {
                var b = document.querySelector('.nav-button[data-page="svc-' + s.key + '"]');
                if (!b) { return; }
                var locked = s.unlocked === false;
                b.classList.toggle("svc-lock", locked);
                if (locked) { b.setAttribute("data-lock", (s.needs || "").charAt(0).toUpperCase() + (s.needs || "").slice(1)); }
                else { b.removeAttribute("data-lock"); }
            });
        }

        function drawService(s) {''', "index locked block")

ix = rep(ix, "                services.forEach(drawService);\n", "                services.forEach(drawService);\n                markNav();\n", "index loadServices")

ix = rep(ix, '"</div>" + featureList(plan.key) +\n                    \'<div class="pp-slot" id="paypal-\'',
          '"</div>" + featureList(plan.key) + serviceList(plan) +\n                    \'<div class="pp-slot" id="paypal-\'', "index plan card")

ix = rep(ix, "        function zar(value) {", r'''        function serviceList(plan) {
            var own = plan.services || [];
            if (!own.length) { return ""; }
            var prev = { business: "Starter Protection", enterprise: "Business Protection" }[plan.key];
            return '<div class="plan-svc"><p class="plan-svc-head">Security services unlocked</p><ul>' +
                (prev ? '<li class="plan-svc-all">Everything in ' + prev + "</li>" : "") +
                own.map(function (n) { return "<li>" + TICK + "<span>" + n + "</span></li>"; }).join("") + "</ul></div>";
        }

        function zar(value) {''', "index serviceList")

ix = rep(ix, "</head>", '''<style id="mt-packages">
.nav-button.svc-lock::after { content: attr(data-lock); margin-left: auto; font-size: 10px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; padding: 2px 7px; border-radius: 999px; background: rgba(255,184,74,.18); color: #b26a00; }
html[data-theme="dark"] .nav-button.svc-lock::after { color: #ffb84a; }
.svc-lockbox { text-align: center; max-width: 560px; margin: 10px auto; padding: 34px 28px; }
.svc-lockicon { width: 64px; height: 64px; margin: 0 auto 14px; border-radius: 50%; display: grid; place-items: center; background: linear-gradient(135deg, rgba(61,219,176,.22), rgba(31,110,200,.16)); }
.svc-lockicon svg { width: 30px; height: 30px; fill: none; stroke: #12906e; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.svc-lockhead, .plan-svc-head { margin: 18px 0 6px; font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; opacity: .65; }
.svc-locklist { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
.svc-locklist li { padding: 8px 12px; border-radius: 10px; background: rgba(120,140,160,.12); font-weight: 600; }
.plan-svc { margin-top: 14px; padding-top: 12px; border-top: 1px dashed rgba(120,140,160,.35); text-align: left; }
.plan-svc ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; font-size: 14px; }
.plan-svc li { display: flex; gap: 8px; align-items: flex-start; }
.plan-svc-all { font-weight: 700; }
</style>
</head>''', "index css")

# ---- write everything only now
for key, (text, crlf) in {"app": (app, app_crlf), "services": (sv, sv_crlf), "index": (ix, ix_crlf)}.items():
    path = FILES[key]
    backup = path.with_name(path.name + ".before-packages.bak")
    if not backup.exists():
        backup.write_bytes(path.read_bytes())
    path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
    print("patched", path.relative_to(HERE))
print("\nDone. Restart the server (python app.py), then press Ctrl+Shift+R in the browser.")