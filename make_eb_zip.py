"""Builds a clean ZIP of the MellowTech project for AWS Elastic Beanstalk.
Why: the ZIP made by Windows "Send to > Compressed folder" / Compress-Archive stores paths with backslashes, and
Elastic Beanstalk's unzip refuses them ("appears to use backslashes as path separators"). This script writes forward slashes.
It also leaves out secrets (settings.env), databases, backups, caches and build folders.

Run from the project folder (the one that contains index.html and the backend folder):
    python make_eb_zip.py
Result: mellowtech-eb.zip next to this script. Upload that file in Elastic Beanstalk (Upload and deploy).
"""
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "mellowtech-eb.zip"
SKIP_DIRS = {"__pycache__", ".git", ".venv", "venv", "env", "node_modules", "build", "dist", ".elasticbeanstalk", "aws-deploy", "uploads", "backups"}
SKIP_NAMES = {"settings.env", ".env", "mellowtech-eb.zip", "mellowtech.service", "MellowTech.spec", "MellowTechAgent.spec"}
SKIP_SUFFIX = (".bak", ".db", ".sqlite", ".sqlite3", ".db-wal", ".db-shm", ".pyc", ".log", ".ps1", ".bat", ".pdf", ".docx", ".zip")
KEEP = {"mellowtech_agent.py", "MellowTechAgent.exe"}          # the agent downloads must be served by the site

if not (ROOT / "index.html").is_file() or not (ROOT / "backend").is_dir():
    sys.exit("Run this from the project folder (it must contain index.html and the backend folder).")

files = []
for path in sorted(ROOT.rglob("*")):
    if not path.is_file():
        continue
    rel = path.relative_to(ROOT)
    if any(part in SKIP_DIRS for part in rel.parts[:-1]):
        continue
    if rel.name in SKIP_NAMES or rel.name.startswith("apply_") or rel.name.startswith("make_eb"):
        continue
    if rel.suffix.lower() in SKIP_SUFFIX and rel.name not in KEEP:
        continue
    files.append(rel)

# The app's database defaults to a folder AWS makes read-only for the app (that caused "unable to open database file").
# This config creates a writable folder and points the app at it.
STORAGE = (
    "commands:\n"
    "  01_data_dir:\n"
    "    command: \"mkdir -p /var/app/data; chown webapp:webapp /var/app/data 2>/dev/null || chmod 777 /var/app/data\"\n"
    "option_settings:\n"
    "  aws:elasticbeanstalk:application:environment:\n"
    "    MELLOWTECH_DB: /var/app/data/mellowtech.db\n"
)

# One-time copy of your existing database (accounts) onto the server. Put a copy at seed\\mellowtech.db to use it.
# It is copied only once (a marker file stops it overwriting live data on later deploys).
SEED = ROOT / "seed" / "mellowtech.db"
if SEED.is_file():
    STORAGE += (
        "container_commands:\n"
        "  02_seed_db:\n"
        "    command: \"if [ ! -f /var/app/data/.seeded ] && [ -f seed/mellowtech.db ]; then "
        "rm -f /var/app/data/mellowtech.db-wal /var/app/data/mellowtech.db-shm; "
        "cp seed/mellowtech.db /var/app/data/mellowtech.db && chown webapp:webapp /var/app/data/mellowtech.db "
        "&& touch /var/app/data/.seeded; fi\"\n"
    )

missing = [n for n in ("requirements.txt", "Procfile") if not (ROOT / n).is_file()]
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for rel in files:
        z.write(ROOT / rel, rel.as_posix())            # as_posix() = forward slashes, which is the whole fix
    z.writestr(".ebextensions/01_storage.config", STORAGE)
    if SEED.is_file():
        z.write(SEED, "seed/mellowtech.db")
        print("Including seed/mellowtech.db (your existing accounts). It contains customer data: delete the seed folder after the first deploy works.")

print(f"Wrote {OUT.name}: {len(files)} files, {OUT.stat().st_size // 1024} KB")
bad = [n for n in zipfile.ZipFile(OUT).namelist() if "\\" in n]
print("Backslashes in paths:", len(bad))
for name in missing:
    print(f"WARNING: no {name} at the top level. Elastic Beanstalk needs it. See the instructions I sent.")