import sys, re, base64
from pathlib import Path

root = Path(sys.argv[1])
login = root / "login.html"
lt = login.read_text(encoding="utf-8")

def block_end(text, start):
    depth = 0
    for m in re.finditer(r"<div\b|</div>", text[start:]):
        if m.group().startswith("<div"):
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                return start + m.end()
    return -1

s = lt.find('<div class="mark"')
e = block_end(lt, s) if s >= 0 else -1
LOGO = lt[s:e] if e > 0 else ""
if "logo-arrows" not in LOGO or "<img" not in LOGO:
    sys.exit("STOPPED: could not find the new logo in login.html. Nothing was changed.")

CSS = """<style id="mt-brand">
.brand-panel .mark{position:relative;width:82px;height:64px;margin:0 0 12px -7px}
.brand-panel .mark svg{position:absolute;inset:0;width:100%;height:100%}
.brand-panel .mark .arrows{overflow:visible;filter:drop-shadow(0 0 7px rgba(40,190,255,.85))}
.brand-panel .mark .arrows .head{fill:#2fb4ff;stroke:none}
.brand-panel .mark .logo-text{position:absolute;left:50%;top:50%;width:65%;transform:translate(-50%,-50%);filter:drop-shadow(0 2px 8px rgba(0,0,0,.5))}
@media (max-width:800px){.brand-panel .mark{width:68px;height:52px}}
</style>
</head>"""

JS = """<script>
(function () {
    var svg = document.getElementById("logo-arrows");
    if (!svg || !svg.pauseAnimations) { return; }
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) { svg.pauseAnimations(); return; }
    var n = 0, loading = true;
    function sync() { try { if (n > 0 || loading) { svg.unpauseAnimations(); } else { svg.pauseAnimations(); } } catch (e) {} }
    sync();
    function done() { setTimeout(function () { loading = false; sync(); }, 1400); }
    if (document.readyState === "complete") { done(); } else { window.addEventListener("load", done); }
    var f = window.fetch;
    if (f) {
        window.fetch = function () {
            n++; sync();
            var p = f.apply(this, arguments);
            var end = function () { n = Math.max(0, n - 1); sync(); };
            p.then(end, end);
            return p;
        };
    }
})();
</script>
</body>"""

FAV_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><defs>'
 '<linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#38d6ff"/><stop offset="1" stop-color="#1c8cff"/></linearGradient></defs>'
 '<rect width="64" height="64" rx="14" fill="#07111d"/>'
 '<g fill="none" stroke="url(#g)" stroke-width="5" stroke-linecap="round"><path d="M12 28A21 21 0 0 1 49 20"/><path d="M52 36A21 21 0 0 1 15 44"/></g>'
 '<path d="M54 28L54 15L42 23Z" fill="#2fb4ff"/><path d="M10 36L10 49L22 41Z" fill="#2fb4ff"/>'
 '<text x="32" y="41" font-family="Arial,Helvetica,sans-serif" font-size="22" font-weight="900" fill="#ffffff" text-anchor="middle">M</text></svg>')
ICON = '<link rel="icon" type="image/svg+xml" href="data:image/svg+xml;base64,' + base64.b64encode(FAV_SVG.encode()).decode() + '">'

for page in sorted(root.glob("*.html")):
    t = page.read_text(encoding="utf-8", newline="") if False else page.read_text(encoding="utf-8")
    notes = []
    # favicon on every page
    if re.search(r'<link rel="icon"[^>]*>', t):
        t = re.sub(r'<link rel="icon"[^>]*>', lambda m: ICON, t, count=1)
    elif "</head>" in t:
        t = t.replace("</head>", ICON + "\n</head>", 1)
    notes.append("tab icon")
    # new logo on pages that still carry the old one
    if 'class="mark"' in t and "logo-arrows" not in t:
        ms = t.find('<div class="mark"')
        me = block_end(t, ms)
        if ms >= 0 and me > 0 and t.count("</head>") == 1 and t.count("</body>") == 1:
            t = t[:ms] + LOGO + t[me:]
            t = t.replace("</head>", CSS, 1).replace("</body>", JS, 1)
            notes.append("new logo")
        else:
            notes.append("SKIPPED the logo (page layout not recognised)")
    page.write_text(t, encoding="utf-8", newline="")
    print(page.name + ": " + ", ".join(notes))
print("Done.")
