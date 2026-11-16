#!/usr/bin/env python3
"""
build_update32.py  -  builds update-32 from update-31 (the latest AWS package)

What it does
  1. Reads  Downloads\\update-31.zip  (it is NEVER modified; it stays as your rollback).
  2. Unpacks a copy into a NEW folder  Downloads\\update-32  (stops if that folder or update-32.zip exists).
  3. Runs apply_siem.py and then apply_sidebar_v2.py on that copy. Each of them stops without
     changing anything if its anchors are not found in the real update-31 files.
  4. Checks that EXACTLY these three files changed and nothing else:
        index.html   backend/app.py   agent/mellowtech_agent.py
  5. Writes  Downloads\\update-32.zip  with forward-slash paths and the same file list as update-31.
  6. Re-opens the new zip and verifies it. If any step fails, the unfinished folder and zip are
     deleted again and the reason is printed.

Put this file in the same folder as apply_siem.py and apply_sidebar_v2.py (your MELLOWTECH folder), then run:
    python build_update32.py
Optional: python build_update32.py "C:\\Users\\Given\\Downloads"
"""
import hashlib
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

BASE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "Downloads"
HERE = Path(__file__).resolve().parent
SRC = BASE / "update-31.zip"
OUT_DIR = BASE / "update-32"
OUT_ZIP = BASE / "update-32.zip"

# (script, text that proves it is the right version of the script)
PATCHERS = [
    ("apply_siem.py", "MellowSecure SIEM: log collection and search"),
    ("apply_sidebar_v2.py", "real page with this name already exists"),
]
EXPECTED_CHANGED = {"index.html", "backend/app.py", "agent/mellowtech_agent.py"}
TEMP_BACKUP_MARKS = (".before-siem", ".before-sidebar")

made_dir = False
made_zip = False


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def fail(message):
    print("\nSTOPPED: " + message)
    if made_zip and OUT_ZIP.exists():
        OUT_ZIP.unlink()
    if made_dir and OUT_DIR.exists():
        shutil.rmtree(OUT_DIR, ignore_errors=True)
    if made_dir or made_zip:
        print("The unfinished update-32 folder/zip were deleted again. update-31.zip was not touched.")
    else:
        print("Nothing was changed.")
    sys.exit(1)


def norm(name):
    return name.replace("\\", "/")


def main():
    global made_dir, made_zip

    # ---- checks before anything is created
    if not SRC.is_file():
        fail("update-31.zip was not found in %s" % BASE)
    if OUT_DIR.exists() or OUT_ZIP.exists():
        fail("update-32 (folder or zip) already exists in %s. Rename or remove it first; this script never overwrites." % BASE)
    for script, proof in PATCHERS:
        path = HERE / script
        if not path.is_file():
            fail("%s is not in the same folder as this script (%s)." % (script, HERE))
        if proof not in path.read_text(encoding="utf-8", errors="replace"):
            fail("%s is an old version. Download the latest copy and replace it." % script)

    src_hash_before = sha256(SRC)
    with zipfile.ZipFile(SRC) as zf:
        if zf.testzip() is not None:
            fail("update-31.zip is damaged (zip test failed).")
        infos = zf.infolist()
        names = [norm(i.filename) for i in infos]
        files = [n for n in names if not n.endswith("/")]
        for needed in sorted(EXPECTED_CHANGED) + ["Procfile", "requirements.txt"]:
            if needed not in files:
                fail("update-31.zip does not contain %s. It does not look like a full site package." % needed)
        print("update-31.zip: %d entries, %d files" % (len(names), len(files)))

        # ---- unpack a copy
        made_dir = True
        OUT_DIR.mkdir()
        root = OUT_DIR.resolve()
        original = {}
        for info, name in zip(infos, names):
            dest = (OUT_DIR / name).resolve()
            if root != dest and root not in dest.parents:
                fail("unsafe path in zip: %s" % name)
            if name.endswith("/"):
                dest.mkdir(parents=True, exist_ok=True)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            data = zf.read(info)
            dest.write_bytes(data)
            original[name] = data

    # ---- patch the copy
    for script, _proof in PATCHERS:
        print("\n--- running %s ---" % script)
        run = subprocess.run([sys.executable, str(HERE / script)], cwd=str(OUT_DIR),
                             capture_output=True, text=True)
        print(run.stdout.strip())
        if run.returncode != 0:
            fail("%s stopped with this message:\n%s" % (script, (run.stderr.strip() or run.stdout.strip() or "(no message)")))

    # ---- remove the temporary backups the patch scripts made
    for path in sorted(OUT_DIR.rglob("*")):
        if not path.is_file():
            continue
        rel = norm(str(path.relative_to(OUT_DIR)))
        if rel in original:
            continue
        if any(mark in rel for mark in TEMP_BACKUP_MARKS):
            path.unlink()
        else:
            fail("a patch script created an unexpected file: %s" % rel)

    # ---- exactly three files may differ
    changed = set()
    for name, data in original.items():
        if (OUT_DIR / name).read_bytes() != data:
            changed.add(name)
    if changed != EXPECTED_CHANGED:
        fail("unexpected set of changed files.\n  expected: %s\n  got:      %s" % (sorted(EXPECTED_CHANGED), sorted(changed)))

    # ---- write the new zip (same entries and order as update-31, forward slashes)
    made_zip = True
    with zipfile.ZipFile(SRC) as zf, zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as out:
        for info in zf.infolist():
            name = norm(info.filename)
            new = zipfile.ZipInfo(name, date_time=info.date_time)
            new.external_attr = info.external_attr
            if name.endswith("/"):
                out.writestr(new, b"")
                continue
            new.compress_type = zipfile.ZIP_DEFLATED
            out.writestr(new, (OUT_DIR / name).read_bytes())

    # ---- verify the result
    with zipfile.ZipFile(OUT_ZIP) as z2, zipfile.ZipFile(SRC) as z1:
        if z2.testzip() is not None:
            fail("the new zip failed its integrity test.")
        n2 = [i.filename for i in z2.infolist()]
        n1 = [norm(i.filename) for i in z1.infolist()]
        if n2 != n1:
            fail("the new zip does not have the same file list as update-31.zip.")
        if any("\\" in n for n in n2):
            fail("the new zip has backslashes in its paths.")
        diff = {n for n in n1 if not n.endswith("/") and z2.read(n) != original[n]}
        if diff != EXPECTED_CHANGED:
            fail("verification: wrong files differ from update-31: %s" % sorted(diff))
        print("\nChanged files (and only these):")
        for n in sorted(diff):
            print("  %-28s %8d -> %8d bytes" % (n, len(original[n]), len(z2.read(n))))
    if sha256(SRC) != src_hash_before:
        fail("update-31.zip changed while running. This should never happen.")

    print("\nDONE.  %s  (%d KB)" % (OUT_ZIP, OUT_ZIP.stat().st_size // 1024))
    print("update-31.zip is unchanged and remains your rollback.")
    print("The unpacked copy is in %s (use it for the local test)." % OUT_DIR)


if __name__ == "__main__":
    main()