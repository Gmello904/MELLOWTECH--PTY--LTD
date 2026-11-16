"""
MellowTech info collector.
Put this file in your MELLOWTECH folder and run:   python dump_info.py
It reads a few small parts of your project and writes them to info.txt,
then opens info.txt in Notepad. It changes nothing. Passwords/keys are hidden.
"""
import os
import re
import sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))
SECRET = re.compile(r"((secret|key|token|password|passwd|pass)\w*\s*[=:]\s*)(['\"]).*?\3", re.I)


def clean(text):
    return SECRET.sub(r"\1\3REDACTED\3", text)


def first_existing(*parts_list):
    for parts in parts_list:
        path = os.path.join(BASE, *parts)
        if os.path.exists(path):
            return path
    return None


def read_lines(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read().splitlines()


out = []


def section(title):
    out.append("")
    out.append("=" * 20 + " " + title + " " + "=" * 20)


# 1. database structure only (no data)
section("DATABASE TABLES (structure only)")
db = first_existing(("MELLOWTECH-AWS", "backend", "mellowtech.db"), ("backend", "mellowtech.db"))
if db:
    try:
        con = sqlite3.connect("file:" + db.replace("\\", "/") + "?mode=ro", uri=True)
        for name, sql in con.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL"):
            out.append(sql)
            out.append("")
        con.close()
    except Exception as exc:
        out.append("Could not read database: %s" % exc)
else:
    out.append("No mellowtech.db found")

app_py = first_existing(("MELLOWTECH-AWS", "backend", "app.py"), ("backend", "app.py"))

# 2. the route list and the sign-in success code
if app_py:
    lines = read_lines(app_py)

    section("ROUTES (names only)")
    for number, line in enumerate(lines, 1):
        if re.match(r"\s*@app\.(get|post|put|patch|delete|route)\(", line):
            out.append("%d: %s" % (number, line.strip()))

    section("SIGN-IN CODE")
    for number, line in enumerate(lines):
        if line.strip().startswith("def login("):
            for part in lines[number:number + 90]:
                out.append(clean(part))
            break

    section("/api/auth/me CODE")
    for number, line in enumerate(lines):
        if '"/api/auth/me"' in line:
            for part in lines[max(0, number - 2):number + 30]:
                out.append(clean(part))
            break
else:
    section("app.py")
    out.append("app.py not found")

# 3. how app.js handles being signed out
app_js = first_existing(("MELLOWTECH-AWS", "app.js"), ("app.js",))
section("app.js sign-out handling")
if app_js:
    js = read_lines(app_js)
    shown = 0
    for number, line in enumerate(js):
        if re.search(r"401|login\.html|function api\(|location\.(href|replace)", line):
            for part in js[max(0, number - 1):number + 5]:
                out.append(clean(part))
            out.append("--")
            shown += 1
            if shown >= 14:
                break
else:
    out.append("app.js not found")

result = os.path.join(BASE, "info.txt")
with open(result, "w", encoding="utf-8") as handle:
    handle.write("\n".join(out))

print("Done. Wrote", result)
try:
    os.startfile(result)
except Exception:
    pass