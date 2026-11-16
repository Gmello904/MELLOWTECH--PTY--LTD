"""Applies the new MellowTech packages to your project.

Put this file in the MELLOWTECH folder (next to index.html) and run:
    python apply_pricing.py
Backups are saved next to each file as *.bak
"""
import re
import shutil
from pathlib import Path

SALES_EMAIL = "mphogivenmello@gmail.com"      # <-- change to your real address

HERE = Path(__file__).resolve().parent

PLANS_NEW = '''PLANS = {
    "starter":  {"name": "Starter Protection",  "price": "29.00", "days": 30, "setup_fee": "29.00"},
    "business": {"name": "Business Protection", "price": "89.00", "days": 30, "setup_fee": "59.00"},
}'''

FEATURES_NEW = '''var FEATURES = {
            free:     ["Dashboard and live monitoring", "Security event log", "Email support"],
            starter:  ["Basic security assessment", "Monthly vulnerability scans", "Security alerts for supported systems",
                       "Monthly security report", "Standard email support"],
            business: ["Everything in Starter", "Weekly vulnerability scans", "Ongoing monitoring of supported devices",
                       "Priority security alerts", "Monthly risk reports", "Remote incident guidance"],
            enterprise: ["Advanced security monitoring for agreed systems", "Threat detection and prioritised alerts",
                         "Regular vulnerability assessments", "Incident response coordination",
                         "Executive-level security reports", "POPIA security-control support",
                         "Dedicated onboarding and security reviews"]
        };
        var SUBTITLE = {
            free: "Get started at no cost",
            starter: "For startups and small businesses.",
            business: "For established and growing businesses.",
            enterprise: "Government, large enterprises, financial institutions and critical infrastructure."
        };'''

DAYS_OLD = "'<div class=\"plan-days\">for ' + plan.days + \" days</div>\" + featureList(plan.key) +"
DAYS_NEW = ("'<div class=\"plan-days\">/ month' + (plan.setup_fee ? \" &middot; Setup fee: \" + info.currency + \" \" + plan.setup_fee : \"\") "
            "+ \"</div>\" + featureList(plan.key) +")

ENTERPRISE_CARD = '''

            var ent = document.createElement("div");
            ent.className = "plan-card";
            ent.innerHTML =
                '<h4>Premium Enterprise Protection</h4><p class="plan-sub">' + SUBTITLE.enterprise + '</p>' +
                '<div class="plan-price"><small>' + info.currency + '</small>499</div>' +
                '<div class="plan-days">/ month starting price &middot; custom contracts and SLAs available</div>' +
                featureList("enterprise") +
                '<a class="btn-small" style="display:block;text-align:center;text-decoration:none;padding:13px;border-radius:10px;background:#0f2236;color:#fff;font-weight:700" ' +
                'href="mailto:__SALES__?subject=Enterprise%20Protection%20enquiry">Contact sales</a>';
            grid.appendChild(ent);'''.replace("__SALES__", SALES_EMAIL)


def backup(path):
    shutil.copy2(path, str(path) + ".bak")


def patch_app(path):
    text = path.read_text(encoding="utf-8")
    if '"Starter Protection"' in text:
        return "already updated"
    new, count = re.subn(r"PLANS = \{.*?\n\}", lambda m: PLANS_NEW, text, count=1, flags=re.S)
    if not count:
        return "PLANS block NOT FOUND (left unchanged)"
    backup(path)
    path.write_text(new, encoding="utf-8")
    return "updated"


def patch_index(path):
    text = path.read_text(encoding="utf-8")
    if "Premium Enterprise Protection" in text:
        return "already updated"
    notes = []

    text, c = re.subn(r"var FEATURES = \{.*?\};\s*var SUBTITLE = \{.*?\};", lambda m: FEATURES_NEW, text, count=1, flags=re.S)
    notes.append("features " + ("ok" if c else "NOT FOUND"))

    if DAYS_OLD in text:
        text = text.replace(DAYS_OLD, DAYS_NEW, 1)
        notes.append("setup fee line ok")
    else:
        notes.append("setup fee line NOT FOUND")

    text, c = re.subn(r"(payFastSlot\.appendChild\(pfBtn\);\s*\}\s*\}\);)",
                      lambda m: m.group(1) + ENTERPRISE_CARD, text, count=1)
    notes.append("enterprise card " + ("ok" if c else "NOT FOUND"))

    backup(path)
    path.write_text(text, encoding="utf-8")
    return ", ".join(notes)


def main():
    targets = [
        (HERE / "backend" / "app.py", patch_app),
        (HERE / "aws-deploy" / "app.py", patch_app),
        (HERE / "index.html", patch_index),
        (HERE / "aws-deploy" / "index.html", patch_index),
    ]
    for path, fn in targets:
        if path.is_file():
            print(f"{path.relative_to(HERE)}: {fn(path)}")
        else:
            print(f"{path.relative_to(HERE)}: not found, skipped")
    print("\nDone. Restart python app.py and refresh the browser with Ctrl+Shift+R.")


if __name__ == "__main__":
    main()