"""Adds PayPal / PayShap buttons to the Premium Enterprise card and keeps Contact sales."""
import re
import shutil
from pathlib import Path

SALES_EMAIL = "sales@yourdomain.co.za"   # only used if your current email can't be found

HERE = Path(__file__).resolve().parent

OLD_DAYS = ("'<div class=\"plan-days\">/ month' + (plan.setup_fee ? \" &middot; Setup fee: \" + info.currency + \" \" + "
            "plan.setup_fee : \"\") + \"</div>\"")
NEW_DAYS = ("'<div class=\"plan-days\">' + (plan.key === \"enterprise\" ? "
            "\"/ month starting price &middot; custom contracts and SLAs available\" : "
            "\"/ month\" + (plan.setup_fee ? \" &middot; Setup fee: \" + info.currency + \" \" + plan.setup_fee : \"\")) "
            "+ \"</div>\"")

CONTACT = '''

                if (plan.key === "enterprise") {
                    var contact = document.createElement("a");
                    contact.className = "btn-small";
                    contact.style.cssText = "display:block;text-align:center;text-decoration:none;margin-top:10px;padding:13px;border-radius:10px;background:#0f2236;color:#fff;font-weight:700";
                    contact.href = "mailto:__EMAIL__?subject=Enterprise%20Protection%20enquiry";
                    contact.textContent = "Contact sales";
                    card.appendChild(contact);
                }'''

FEATURED_OLD = "var featured = index === info.plans.length - 1 && info.plans.length > 1;"
FEATURED_NEW = 'var featured = plan.key === "business";'
SLOT_OLD = 'var payFastSlot = card.querySelector("#payfast-" + plan.key);'


def save(path, text):
    shutil.copy2(path, str(path) + ".bak")
    path.write_text(text, encoding="utf-8")


def patch_app(path):
    text = path.read_text(encoding="utf-8")
    if '"enterprise"' in text:
        return "already updated"
    old = '"business": {"name": "Business Protection", "price": "89.00", "days": 30, "setup_fee": "59.00"},'
    if text.count(old) != 1:
        return "NOT changed: the Business plan line was not found"
    new = old + '\n    "enterprise": {"name": "Premium Enterprise Protection", "price": "499.00", "days": 30},'
    save(path, text.replace(old, new, 1))
    return "updated"


def patch_index(path):
    text = path.read_text(encoding="utf-8")
    if 'plan.key === "enterprise"' in text:
        return "already updated"

    block = re.search(r'var ent = document\.createElement\("div"\);.*?grid\.appendChild\(ent\);', text, re.S)
    if not block:
        return "NOT changed: the old Enterprise card was not found"
    email = SALES_EMAIL
    found = re.search(r"mailto:([^?\"'\s]+)\?", block.group(0))
    if found:
        email = found.group(1)

    text = re.sub(r'(\n[ \t]*/\* Premium Enterprise card[^\n]*\*/)?\s*var ent = document\.createElement\("div"\);.*?grid\.appendChild\(ent\);',
                  "", text, count=1, flags=re.S)

    for old, new in ((FEATURED_OLD, FEATURED_NEW),
                     (OLD_DAYS, NEW_DAYS),
                     (SLOT_OLD, SLOT_OLD + CONTACT.replace("__EMAIL__", email))):
        if text.count(old) != 1:
            return "NOT changed: could not find " + repr(old[:50])
        text = text.replace(old, new, 1)

    save(path, text)
    return "updated"


def main():
    for path, fn in ((HERE / "backend" / "app.py", patch_app),
                     (HERE / "aws-deploy" / "app.py", patch_app),
                     (HERE / "index.html", patch_index),
                     (HERE / "aws-deploy" / "index.html", patch_index)):
        if path.is_file():
            print(f"{path.relative_to(HERE)}: {fn(path)}")
        else:
            print(f"{path.relative_to(HERE)}: not found, skipped")
    print("\nDone. Restart python app.py and refresh the browser with Ctrl+Shift+R.")


if __name__ == "__main__":
    main()