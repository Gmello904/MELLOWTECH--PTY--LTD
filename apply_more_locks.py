"""MellowTech: lock Threat Detection, Network Monitoring and the Vulnerability Scanner behind packages too,
make the sidebar padlock a small icon only, and show the package on every paid page.

Run AFTER apply_sidebar_locks.py, from the project folder:  python apply_more_locks.py
Patches backend/app.py and index.html. Backups: *.before-morelocks.bak. Nothing is written unless every step succeeds.
Then RESTART the server (stop it with Ctrl+C, then: cd backend  and  python app.py) and hard-refresh with Ctrl+Shift+R.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def find(*names):
    for n in names:
        if (HERE / n).is_file():
            return HERE / n
    sys.exit("Could not find " + " or ".join(names) + " next to this script.")


FILES = {"app": find("backend/app.py", "app.py"), "index": find("index.html")}


def load(p):
    raw = p.read_bytes().decode("utf-8-sig") if p.suffix == ".py" else p.read_bytes().decode("utf-8")
    return raw.replace("\r\n", "\n"), "\r\n" in raw


def rep(text, old, new, step):
    if text.count(old) != 1:
        sys.exit(f"STEP FAILED ({step}): anchor found {text.count(old)} times. Nothing was changed.")
    return text.replace(old, new)


# ---------------------------------------------------------------- app.py
app, app_crlf = load(FILES["app"])
if "PAGE_PLANS" in app:
    sys.exit("Already applied. Nothing was changed.")

app = rep(app, '    FEATURE_PLANS["svc_" + _key] = (_plan, SERVICE_LABELS[_key])\n',
'''    FEATURE_PLANS["svc_" + _key] = (_plan, SERVICE_LABELS[_key])

# Pages that are paid too. Change a package here, restart the server, and it applies everywhere.
PAGE_PLANS = {"threats": "starter", "scanner": "starter", "network": "business"}
PAGE_LABELS = {"threats": "Threat Detection", "scanner": "Vulnerability Scanner", "network": "Network Monitoring"}
for _key, _plan in PAGE_PLANS.items():
    FEATURE_PLANS["page_" + _key] = (_plan, PAGE_LABELS[_key])


@app.before_request
def scanner_package_lock():
    """The Vulnerability Scanner's data is refused on the server too, not just hidden on the page."""
    if request.path.startswith("/api/scanner"):
        user = current_user()
        if user and not user["is_platform"] and not feature_allowed(user["org_id"], "page_scanner"):
            need = PLANS[PAGE_PLANS["scanner"]]["name"]
            return jsonify({"error": f"The Vulnerability Scanner is part of {need}. Pay for that package in Billing & Plans to unlock it.",
                            "locked": True, "needs": PAGE_PLANS["scanner"]}), 402
''', "app.py page plans")
compile(app, "app.py", "exec")

# ---------------------------------------------------------------- index.html
ix, ix_crlf = load(FILES["index"])
if "mt-locks2" in ix:
    sys.exit("Already applied. Nothing was changed.")

ix = rep(ix, 'var FEATURE_PAGES = { docscan: "document_scan", autopilot: "autopilot", assistant: "assistant" };',
 'var FEATURE_PAGES = { docscan: "document_scan", autopilot: "autopilot", assistant: "assistant", scanner: "page_scanner", threats: "page_threats", network: "page_network" };\n'
 '    var LOCK_CARD_PAGES = { scanner: "Vulnerability Scanner", threats: "Threat Detection", network: "Network Monitoring" };\n'
 '    var plans = {};', "feature pages")

ix = rep(ix, "    function mark(page, needs, unlocked, staff) {\n        var b = document.querySelector('.nav-button[data-page=\"' + page + '\"]');\n        if (!b) { return; }\n",
 r'''    function pill(page, needs) {
        var h = document.querySelector("#" + page + " h2");
        if (!h) { return; }
        var old = h.querySelector(".pkg-pill");
        if (old) { old.remove(); }
        var p = document.createElement("span");
        p.className = "pkg-pill";
        p.textContent = cap(needs) + " package";
        h.appendChild(p);
    }

    function pageLock(page, needs, unlocked, staff) {
        var sec = document.getElementById(page), name = LOCK_CARD_PAGES[page];
        if (!sec || !name) { return; }
        var card = sec.querySelector(".pg-lockcard");
        if (unlocked || staff) { sec.classList.remove("pg-locked"); if (card) { card.remove(); } return; }
        sec.classList.add("pg-locked");
        if (card) { return; }
        var info = plans[needs] || {};
        card = document.createElement("div");
        card.className = "panel pg-lockcard";
        card.innerHTML = '<div class="svc-lockicon">' + CLOSED + "</div><h3>" + name + " is locked</h3>" +
            "<p>This is part of <b>" + (info.name || cap(needs)) + "</b>" + (info.price ? " ($" + info.price + " / month)" : "") +
            ". It unlocks as soon as your payment goes through.</p>" +
            '<div class="actions" style="margin-top:14px"><button type="button" class="btn-small svc-unlock" data-svc-open="billing">Unlock with ' + (info.name || cap(needs)) + "</button></div>";
        var h = sec.querySelector("h2");
        if (h && h.nextSibling) { h.parentNode.insertBefore(card, h.nextSibling); } else { sec.appendChild(card); }
    }

    function mark(page, needs, unlocked, staff) {
        pill(page, needs);
        pageLock(page, needs, unlocked, staff);
        var b = document.querySelector('.nav-button[data-page="' + page + '"]');
        if (!b) { return; }
''', "mark")

ix = rep(ix, 'Promise.all([get("/api/features"), get("/api/services"), get("/api/auth/me")]).then(function (res) {\n            var feats = res[0], svcs = res[1],',
 'Promise.all([get("/api/features"), get("/api/services"), get("/api/auth/me"), get("/api/billing")]).then(function (res) {\n'
 '            if (res[3] && res[3].plans) { res[3].plans.forEach(function (p) { plans[p.key] = p; }); }\n'
 '            var feats = res[0], svcs = res[1],', "refresh")

ix = rep(ix, "</head>", '''<style id="mt-locks2">
.nav-lock { padding: 5px; gap: 0; right: 14px; }
.nav-lock > span { display: none; }
.nav-lock svg { width: 13px; height: 13px; }
.pkg-pill { display: inline-block; vertical-align: middle; margin-left: 12px; padding: 4px 12px; border-radius: 999px; font: 800 11px/1 inherit; letter-spacing: .06em; text-transform: uppercase;
  color: #3b2a00; background: linear-gradient(135deg, #ffe9a8, #f4c24d); }
.pg-locked > *:not(h2):not(.pg-lockcard) { display: none !important; }
.pg-lockcard { text-align: center; max-width: 560px; margin: 24px auto; padding: 34px 28px; }
</style>
</head>''', "css")

for key, (text, crlf) in {"app": (app, app_crlf), "index": (ix, ix_crlf)}.items():
    p = FILES[key]
    b = p.with_name(p.name + ".before-morelocks.bak")
    if not b.exists():
        b.write_bytes(p.read_bytes())
    p.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
    print("patched", p.relative_to(HERE))
print("\nDone. Now STOP the running server (Ctrl+C), then:  cd backend   and   python app.py   then Ctrl+Shift+R in the browser.")