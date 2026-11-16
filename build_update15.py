"""
Build update-15 for MellowTech.

  * starts from your newest build  (MELLOWTECH-AWS-update-13-msi-demo-ai: AI Assistant,
    MSI installer, welcome page, demo page)
  * brings back the Network Activity graph, Global Threat Map and the
    "Instructions and Connect Devices" tab from update-14
  * adds guest mode (apply_guest_mode_u13.py) and points "Try the live demo" at it
  * makes the lock badges blue instead of yellow
  * checks that visitor counting (record_visit) is still in place

Nothing in your existing folders or zips is changed. Everything is built in a NEW
folder, update-15, and zipped as update-15-guest-map.zip. If any step fails, the
new folder is deleted again and the reason is printed.

Run (PowerShell):   python build_update15.py
"""
import difflib
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

BASE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"C:\Users\Given\Downloads")
LATEST = BASE / "MELLOWTECH-AWS-update-13-msi-demo-ai"
OLD13 = BASE / "_scan" / "MELLOWTECH-AWS-update-13" / "index.html"
MAP14 = BASE / "_scan" / "MELLOWTECH-AWS-update-14" / "index.html"
GUEST = BASE / "MELLOWTECH" / "apply_guest_mode_u13.py"
OUT = BASE / "update-15"
ZIP = BASE / "update-15-guest-map.zip"
created = False


def fail(message):
    print("\nSTOPPED: " + message)
    if created and OUT.exists():
        shutil.rmtree(OUT, ignore_errors=True)
        print("The unfinished update-15 folder was deleted. Nothing else was changed.")
    else:
        print("Nothing was changed.")
    sys.exit(1)


def read(path):
    raw = Path(path).read_bytes()
    return raw.decode("utf-8").replace("\r\n", "\n"), b"\r\n" in raw


def write(path, text, crlf):
    Path(path).write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))


# ---------------------------------------------------------------- 3-way merge
def hunks(a, b):
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    return [(i1, i2, b[j1:j2]) for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal"]


def clash(h1, h2):
    a1, a2, t1 = h1
    b1, b2, t2 = h2
    if a1 == a2 and b1 == b2:
        return a1 == b1 and t1 != t2
    if a1 == a2:
        return b1 < a1 < b2
    if b1 == b2:
        return a1 < b1 < a2
    return max(a1, b1) < min(a2, b2)


def merge3(base, ours, theirs):
    """Apply everything 'theirs' changed to 'ours', both measured against 'base'."""
    ho, ht = hunks(base, ours), hunks(base, theirs)
    out, pos, i, j = [], 0, 0, 0
    while i < len(ho) or j < len(ht):
        if i < len(ho) and j < len(ht):
            h1, h2 = ho[i], ht[j]
            if h1 == h2:
                take = h1
                i += 1
                j += 1
            elif clash(h1, h2):
                lines = "\n".join("   " + x.strip()[:110] for x in (h1[2][:2] + ["  ...  (other side)"] + h2[2][:2]))
                fail("Both versions changed the same lines of index.html (around line %d of update-13).\n"
                     "This is the text involved:\n%s" % (max(h1[0], h2[0]) + 1, lines))
            elif (h1[0], h1[1]) <= (h2[0], h2[1]):
                take = h1
                i += 1
            else:
                take = h2
                j += 1
        elif i < len(ho):
            take = ho[i]
            i += 1
        else:
            take = ht[j]
            j += 1
        a1, a2, text = take
        out.extend(base[pos:a1])
        out.extend(text)
        pos = a2
    out.extend(base[pos:])
    return out


# ---------------------------------------------------------------- preflight
needed = [LATEST / "index.html", LATEST / "app.js", LATEST / "login.html", LATEST / "welcome.html",
          LATEST / "backend" / "app.py", LATEST / "agent" / "MellowTechAgent.exe",
          LATEST / "agent" / "MellowTechAgent.msi", OLD13, MAP14, GUEST]
missing = [str(p) for p in needed if not p.exists()]
if missing:
    fail("These files were not found:\n  " + "\n  ".join(missing))
if OUT.exists():
    fail("The folder %s already exists. Rename or delete it, then run this again." % OUT)

# ---------------------------------------------------------------- 1. merge index.html
A, _ = read(OLD13)          # update-13: the common starting point
B, crlf_b = read(LATEST / "index.html")     # newest build (no map)
C, _ = read(MAP14)          # update-14 (has the map)
merged = "\n".join(merge3(A.split("\n"), B.split("\n"), C.split("\n")))

for needle in ("Global Threat Map", "Network Activity", "Instructions and Connect Devices",
               "AI Assistant", "TOTAL EVENTS", "logo-text"):
    if needle not in merged:
        fail("After merging, index.html is missing: " + needle)
for opener, closer in (("<script", "</script>"), ("<style", "</style>"), ("<div", "</div>")):
    if merged.count(opener) - merged.count(closer) != B.count(opener) - B.count(closer):
        fail("The merged index.html has unbalanced %s tags." % opener)
print("Step 1 ok: map, graph and Connect Devices tab merged into your newest index.html")

# ---------------------------------------------------------------- 2. new folder
created = True
shutil.copytree(LATEST, OUT, ignore=shutil.ignore_patterns("*.bak", "__pycache__"))
write(OUT / "index.html", merged, crlf_b)
print("Step 2 ok: copied your newest folder to", OUT)

# ---------------------------------------------------------------- 3. guest mode
run = subprocess.run([sys.executable, str(GUEST), str(OUT)], cwd=str(GUEST.parent),
                     capture_output=True, text=True)
print(run.stdout.strip())
if run.returncode != 0:
    fail("The guest-mode patch did not apply:\n" + (run.stdout + run.stderr).strip())
print("Step 3 ok: guest mode installed")

# ---------------------------------------------------------------- 4. demo links
OLD_LINK = 'href="demo.html">Try the live demo'
NEW_LINK = 'href="index.html">Try the live demo'
for name in ("welcome.html", "login.html"):
    text, crlf = read(OUT / name)
    if text.count(OLD_LINK) != 1:
        fail("%s: expected to find the demo link once, found %d." % (name, text.count(OLD_LINK)))
    write(OUT / name, text.replace(OLD_LINK, NEW_LINK), crlf)
print("Step 4 ok: 'Try the live demo' now opens the guest dashboard")

# ---------------------------------------------------------------- 5. blue locks
html, crlf = read(OUT / "index.html")
blocks = re.findall(r"\.nav-lock \{[^}]*#ffe9a8[^}]*\}", html)
if len(blocks) != 1:
    fail("Could not find the yellow lock style exactly once (found %d)." % len(blocks))
block = blocks[0]
blue = block
for old, new in (("#3b2a00", "#06203a"),
                 ("linear-gradient(135deg, #ffe9a8, #f4c24d)", "linear-gradient(135deg, #9fd2ff, #4aa8ff)"),
                 ("rgba(244,194,77,.35)", "rgba(74,168,255,.38)")):
    if old not in blue:
        fail("The lock style is different from expected (missing %s)." % old)
    blue = blue.replace(old, new)
write(OUT / "index.html", html.replace(block, blue), crlf)
print("Step 5 ok: lock badges are blue")

# ---------------------------------------------------------------- 6. checks
html, _ = read(OUT / "index.html")
py, _ = read(OUT / "backend" / "app.py")
js, _ = read(OUT / "app.js")
try:
    compile(py, "backend/app.py", "exec")
    compiles = True
except SyntaxError as exc:
    compiles = False
    print("app.py syntax problem:", exc)
checks = [
    ("Global Threat Map in index.html", "Global Threat Map" in html),
    ("Network Activity graph in index.html", "Network Activity" in html),
    ("Instructions and Connect Devices tab", "Instructions and Connect Devices" in html),
    ("AI Assistant (newest wording)", "AI Assistant" in html and "TOTAL EVENTS" in html),
    ("Mellow SECURE logo file", (OUT / "logo-text.png").exists() and "logo-text" in html),
    ("guest mode in index.html", "MT-GUEST-MODE" in html),
    ("guest mode in app.js", "mtNeedLogin" in js),
    ("guest mode in backend/app.py", "DEMO_EMAIL" in py),
    ("backend/app.py has no syntax errors", compiles),
    ("visitor counting: record_visit defined and used", py.count("record_visit(") >= 2),
    ("welcome page and demo page present", (OUT / "welcome.html").exists() and (OUT / "demo.html").exists()),
    ("agent installers present (.exe and .msi)", (OUT / "agent" / "MellowTechAgent.exe").exists()
     and (OUT / "agent" / "MellowTechAgent.msi").exists()),
    ("blue lock style", "#9fd2ff" in html),
]
print("\nChecks:")
bad = 0
for label, ok in checks:
    print("  [%s] %s" % ("ok" if ok else "FAIL", label))
    bad += 0 if ok else 1
if bad:
    fail("%d check(s) failed, so no zip was made." % bad)

# what feeds the graph/map (for the next step: sample data for guests)
lines = html.split("\n")
start = next((n for n, line in enumerate(lines) if 'class="mt-viz"' in line), None)
if start is not None:
    seen = [l.strip()[:170] for l in lines[start:start + 500] if "/api/" in l or ".demo" in l or "demo" in l.lower()]
    print("\nHow the graph/map get their data (send me this part if guests see an empty map):")
    for l in seen[:25]:
        print("   " + l)

# ---------------------------------------------------------------- 7. zip
with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(OUT.rglob("*")):
        if p.is_file() and p.suffix.lower() != ".bak" and "__pycache__" not in p.parts:
            z.write(p, p.relative_to(OUT).as_posix())
with zipfile.ZipFile(ZIP) as z:
    names = z.namelist()
print("\nZip: %s  (%d files, %.1f MB)" % (ZIP, len(names), ZIP.stat().st_size / 1048576))
print("First entries:", ", ".join(names[:6]))
if any(n.endswith(".bak") for n in names):
    print("WARNING: a .bak file is inside the zip")
print("\nDone. Your existing folders and zips were not changed.")
if os.name == "nt":
    subprocess.run(["explorer", "/select," + str(ZIP)])