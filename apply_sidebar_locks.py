"""MellowTech: gold padlock on the right of every paid sidebar item (Document Scanner, Autopilot, Ask Mellow and the
five security services). Run AFTER apply_service_packages.py, from the project folder:  python apply_sidebar_locks.py
Patches index.html only. Backup: index.html.before-locks.bak"""
import sys
from pathlib import Path

path = Path(__file__).resolve().parent / "index.html"
if not path.is_file():
    sys.exit("index.html not found next to this script.")
raw = path.read_bytes().decode("utf-8")
crlf = "\r\n" in raw
t = raw.replace("\r\n", "\n")
if "mt-locks" in t:
    sys.exit("Already applied. Nothing was changed.")


def rep(text, old, new, step):
    if text.count(old) != 1:
        sys.exit(f"STEP FAILED ({step}): anchor found {text.count(old)} times. Nothing was changed.")
    return text.replace(old, new)


t = rep(t, '.nav-button.svc-lock::after { content: attr(data-lock); margin-left: auto; font-size: 10px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; padding: 2px 7px; border-radius: 999px; background: rgba(255,184,74,.18); color: #b26a00; }\n'
           'html[data-theme="dark"] .nav-button.svc-lock::after { color: #ffb84a; }\n',
        '''.nav-button { position: relative; }
.nav-lock { position: absolute; right: 12px; top: 50%; transform: translateY(-50%); display: inline-flex; align-items: center; gap: 5px;
  padding: 3px 8px 3px 6px; border-radius: 999px; font-size: 10px; font-weight: 800; letter-spacing: .05em; text-transform: uppercase;
  color: #3b2a00; background: linear-gradient(135deg, #ffe9a8, #f4c24d); box-shadow: 0 2px 8px rgba(244,194,77,.35); pointer-events: none; }
.nav-lock svg { width: 12px; height: 12px; fill: none; stroke: currentColor; stroke-width: 2.4; stroke-linecap: round; stroke-linejoin: round; }
.nav-lock.open { background: rgba(61,219,176,.16); color: #3ddbb0; box-shadow: none; }
''', "css")

t = rep(t, "</body>", r'''<script id="mt-locks">
(function () {
    var CLOSED = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>';
    var OPEN = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 7.5-2"/></svg>';
    var FEATURE_PAGES = { docscan: "document_scan", autopilot: "autopilot", assistant: "assistant" };
    function get(url) { return fetch(url, { credentials: "same-origin" }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }); }
    function cap(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : ""; }

    function mark(page, needs, unlocked, staff) {
        var b = document.querySelector('.nav-button[data-page="' + page + '"]');
        if (!b) { return; }
        var old = b.querySelector(".nav-lock");
        if (old) { old.remove(); }
        if (unlocked && !staff) { return; }          // paid for: no lock
        var tag = document.createElement("span");
        tag.className = "nav-lock" + (unlocked ? " open" : "");
        tag.innerHTML = (unlocked ? OPEN : CLOSED) + "<span>" + cap(needs) + "</span>";
        tag.title = unlocked ? "MellowTech staff access (customers need " + cap(needs) + ")" : "Locked: pay for " + cap(needs) + " to unlock";
        b.appendChild(tag);
    }

    function refresh() {
        Promise.all([get("/api/features"), get("/api/services"), get("/api/auth/me")]).then(function (res) {
            var feats = res[0], svcs = res[1], staff = !!(res[2] && res[2].user && res[2].user.is_platform);
            if (feats && feats.features) {
                feats.features.forEach(function (f) {
                    Object.keys(FEATURE_PAGES).forEach(function (page) {
                        if (FEATURE_PAGES[page] === f.key) { mark(page, f.needs, f.unlocked, staff); }
                    });
                });
            }
            if (Array.isArray(svcs)) {
                svcs.forEach(function (s) { if (s.needs) { mark("svc-" + s.key, s.needs, s.unlocked !== false, staff); } });
            }
        });
    }
    document.addEventListener("DOMContentLoaded", function () {
        refresh();
        setInterval(function () { if (!document.hidden) { refresh(); } }, 30000);
        document.addEventListener("click", function (e) { if (e.target.closest(".nav-button")) { setTimeout(refresh, 400); } });
    });
})();
</script>
</body>''', "script")

backup = path.with_name("index.html.before-locks.bak")
if not backup.exists():
    backup.write_bytes(path.read_bytes())
path.write_bytes((t.replace("\n", "\r\n") if crlf else t).encode("utf-8"))
print("patched index.html\n\nDone. Hard-refresh the browser with Ctrl+Shift+R (no server restart needed after the previous step).")