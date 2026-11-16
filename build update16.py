"""
Build update-16 for MellowTech (starts from update-15, the version that is live now).

  1. Every visitor opens the dashboard first, as a read-only Guest, on laptop AND phone.
     (welcome.html stays available at /welcome.html.)
  2. Phone fixes: header no longer sticks to the top and eats the screen, text boxes do not
     zoom the page on iPhones, and the "You are viewing a demo" bar fits a phone screen.
  3. New sidebar logo, only if you put the circular logo in Downloads as  mellow-logo.png
     (it is trimmed and shrunk automatically so pages stay fast on a phone).

Nothing in update-15 or any other folder is changed. Everything is built in a NEW folder,
update-16, and zipped as update-16.zip. If a step fails, the new folder is deleted again
and the reason is printed.

Run (PowerShell):   python build_update16.py
"""
import io
import os
import re
import shutil
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

BASE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"C:\Users\Given\Downloads")
SRC = BASE / "update-15"
OUT = BASE / "update-16"
ZIP = BASE / "update-16.zip"
LOGO = BASE / "mellow-logo.png"
PREVIEW = BASE / "update-16-logo-preview.png"
created = False


def fail(message):
    print("\nSTOPPED: " + message)
    if created and OUT.exists():
        shutil.rmtree(OUT, ignore_errors=True)
        print("The unfinished update-16 folder was deleted. Nothing else was changed.")
    else:
        print("Nothing was changed.")
    sys.exit(1)


def read(path):
    raw = Path(path).read_bytes()
    return raw.decode("utf-8").replace("\r\n", "\n"), b"\r\n" in raw


def write(path, text, crlf):
    Path(path).write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))


def prepare_logo(path):
    raw = Path(path).read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        fail("mellow-logo.png is not a PNG file. Save or export the logo as a PNG and try again.")
    w, h = struct.unpack(">II", raw[16:24])
    print("  logo file: %d x %d px, %d KB" % (w, h, len(raw) // 1024))
    try:
        from PIL import Image
    except ImportError:
        Image = None
    if Image is None:
        if len(raw) > 150 * 1024 or w > 700:
            fail("The logo is large (%d KB, %d px wide) and has to be shrunk first so phones load fast.\n"
                 "Run this once:   python -m pip install pillow\nThen run this script again." % (len(raw) // 1024, w))
        return raw, w, h
    im = Image.open(path).convert("RGBA")
    box = im.getchannel("A").point(lambda a: 255 if a > 12 else 0).getbbox()
    if box and box != (0, 0, im.width, im.height):
        pad = int(max(box[2] - box[0], box[3] - box[1]) * 0.03)
        im = im.crop((max(0, box[0] - pad), max(0, box[1] - pad),
                      min(im.width, box[2] + pad), min(im.height, box[3] + pad)))
    if im.width > 480:
        im = im.resize((480, round(im.height * 480 / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return buf.getvalue(), im.width, im.height


# ---------------------------------------------------------------- preflight
needed = [SRC / "index.html", SRC / "internal.html", SRC / "backend" / "app.py", SRC / "logo-text.png",
          SRC / "app.js", SRC / "welcome.html", SRC / "agent" / "MellowTechAgent.exe", SRC / "agent" / "MellowTechAgent.msi"]
missing = [str(p) for p in needed if not p.exists()]
if missing:
    fail("These files were not found:\n  " + "\n  ".join(missing))
if OUT.exists():
    fail("The folder %s already exists. Rename or delete it, then run this again." % OUT)

# ---------------------------------------------------------------- read what we will change
py, py_crlf = read(SRC / "backend" / "app.py")
HOME = r'return redirect\("/index\.html" if current_user\(\) else "/welcome\.html"\)[^\n]*'
if len(re.findall(HOME, py)) != 1:
    fail("Could not find the home-page rule in backend/app.py exactly once (found %d)." % len(re.findall(HOME, py)))
py = re.sub(HOME, lambda m: 'return redirect("/index.html")      # every visitor opens the dashboard first; guests get the read-only demo', py)

html, html_crlf = read(SRC / "index.html")
if html.count("</head>") != 1:
    fail("index.html: expected one </head>, found %d." % html.count("</head>"))

logo_bytes = None
if LOGO.exists():
    print("Found mellow-logo.png, preparing it:")
    logo_bytes, lw, lh = prepare_logo(LOGO)
    print("  sidebar logo: %d x %d px, %d KB" % (lw, lh, len(logo_bytes) // 1024))
else:
    print("No mellow-logo.png in Downloads, so the sidebar logo is left as it is.")

TAG = re.compile(r'(<img class="brand-logo"[^>]*?)width:118px')
tags = {}
if logo_bytes:
    for name in ("index.html", "internal.html"):
        text, crlf = read(SRC / name) if name != "index.html" else (html, html_crlf)
        if len(TAG.findall(text)) != 1:
            fail("%s: expected to find the sidebar logo once, found %d." % (name, len(TAG.findall(text))))
        tags[name] = (TAG.sub(lambda m: m.group(1) + "width:150px;max-width:100%", text), crlf)
    html = tags["index.html"][0]

PHONE_CSS = """<style id="mt-phone16">
@media (max-width: 900px) {
  html { -webkit-text-size-adjust: 100%; text-size-adjust: 100%; }
  .topbar { position: static !important; }
  input, select, textarea { font-size: 16px !important; }
  #mt-bar { left: 12px !important; right: 12px !important; bottom: calc(12px + env(safe-area-inset-bottom, 0px)) !important;
    transform: none !important; max-width: none !important; flex-wrap: wrap; justify-content: center; text-align: center;
    border-radius: 16px !important; gap: 6px 14px !important; padding: 10px 14px !important; }
@@LOGO@@}
</style>
"""
logo_phone = "  .brand-logo { width: 130px !important; }\n" if logo_bytes else ""
html = html.replace("</head>", PHONE_CSS.replace("@@LOGO@@", logo_phone) + "</head>")

# ---------------------------------------------------------------- write the new folder
created = True
shutil.copytree(SRC, OUT, ignore=shutil.ignore_patterns("*.bak", "__pycache__"))
write(OUT / "backend" / "app.py", py, py_crlf)
write(OUT / "index.html", html, html_crlf)
if logo_bytes:
    (OUT / "logo-text.png").write_bytes(logo_bytes)
    PREVIEW.write_bytes(logo_bytes)
    text, crlf = tags["internal.html"]
    write(OUT / "internal.html", text, crlf)

# ---------------------------------------------------------------- checks
py2, _ = read(OUT / "backend" / "app.py")
html2, _ = read(OUT / "index.html")
try:
    compile(py2, "backend/app.py", "exec")
    compiles = True
except SyntaxError as exc:
    compiles = False
    print("app.py syntax problem:", exc)
checks = [
    ("visitors open the dashboard first", 'return redirect("/index.html")      # every visitor' in py2),
    ("welcome page still available at /welcome.html", '"welcome.html"' in py2 and (OUT / "welcome.html").exists()),
    ("phone fixes added", 'id="mt-phone16"' in html2),
    ("guest mode still in place", "MT-GUEST-MODE" in html2 and "DEMO_EMAIL" in py2),
    ("map and graph still in place", "Global Threat Map" in html2 and "Network Activity" in html2),
    ("backend/app.py has no syntax errors", compiles),
    ("visitor counting: record_visit defined and used", py2.count("record_visit(") >= 2),
    ("agent installers present", (OUT / "agent" / "MellowTechAgent.exe").exists() and (OUT / "agent" / "MellowTechAgent.msi").exists()),
]
if logo_bytes:
    checks.append(("new sidebar logo in place", "width:150px" in html2 and (OUT / "logo-text.png").read_bytes() == logo_bytes))
print("\nChecks:")
bad = 0
for label, ok in checks:
    print("  [%s] %s" % ("ok" if ok else "FAIL", label))
    bad += 0 if ok else 1
if bad:
    fail("%d check(s) failed, so no zip was made." % bad)

# ---------------------------------------------------------------- zip
with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(OUT.rglob("*")):
        if p.is_file() and p.suffix.lower() != ".bak" and "__pycache__" not in p.parts:
            z.write(p, p.relative_to(OUT).as_posix())
with zipfile.ZipFile(ZIP) as z:
    names = z.namelist()
print("\nZip: %s  (%d files, %.1f MB)" % (ZIP, len(names), ZIP.stat().st_size / 1048576))
print("First entries:", ", ".join(names[:6]))
if logo_bytes:
    print("Logo preview saved as:", PREVIEW)
print("\nDone. update-15 and your other folders were not changed.")
if os.name == "nt":
    subprocess.run(["explorer", "/select," + str(ZIP)])