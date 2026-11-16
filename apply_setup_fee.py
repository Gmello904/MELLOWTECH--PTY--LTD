"""Charges the one-time setup fee on a customer's first PayPal purchase.

Put this file in the MELLOWTECH folder (next to index.html) and run:
    python apply_setup_fee.py
Backups are saved next to each file as *.bak
"""
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent

HELPERS = '''def is_first_purchase(org_id):
    """True when this company has never paid, so the one-time setup fee still applies."""
    db = get_db()
    if db.execute("SELECT 1 FROM payments WHERE org_id = ? AND status = 'completed' LIMIT 1", (org_id,)).fetchone():
        return False
    if db.execute("SELECT 1 FROM payfast_payments WHERE org_id = ? AND paid_at IS NOT NULL LIMIT 1", (org_id,)).fetchone():
        return False
    return True


def amount_due(org_id, plan):
    """Monthly price, plus the setup fee on the first purchase. Returned as text like '58.00'."""
    total = Decimal(plan["price"])
    if plan.get("setup_fee") and is_first_purchase(org_id):
        total += Decimal(plan["setup_fee"])
    return f"{total:.2f}"


'''

# (old text, new text): each old text must appear exactly once in app.py
REPLACEMENTS = [
    ('@app.get("/api/billing")',
     HELPERS + '@app.get("/api/billing")'),

    ('    return jsonify({"paypal_client_id": PAYPAL_CLIENT_ID if PAYPAL_SECRET else "",',
     '    first = is_first_purchase(g.user["org_id"])\n'
     '    return jsonify({"paypal_client_id": PAYPAL_CLIENT_ID if PAYPAL_SECRET else "",'),

    ('"plans": [{"key": k, **v} for k, v in PLANS.items()]})',
     '"plans": [{"key": k, **v, "setup_fee": (v.get("setup_fee") or "") if first else ""} '
     'for k, v in PLANS.items()]})'),

    ('    try:\n        order = paypal_call("POST", "/v2/checkout/orders", {',
     '    charge = amount_due(g.user["org_id"], plan)\n'
     '    try:\n        order = paypal_call("POST", "/v2/checkout/orders", {'),

    ('"amount": {"currency_code": PAYPAL_CURRENCY, "value": plan["price"]}}]})',
     '"amount": {"currency_code": PAYPAL_CURRENCY, "value": charge}}]})'),

    ('plan_key, plan["price"], PAYPAL_CURRENCY, order["id"]',
     'plan_key, charge, PAYPAL_CURRENCY, order["id"]'),
]


def patch(path):
    text = path.read_text(encoding="utf-8")
    if "def amount_due" in text:
        return "already updated"
    for old, new in REPLACEMENTS:
        count = text.count(old)
        if count != 1:
            return f"NOT changed: could not find a unique match for: {old.strip()[:60]!r} (found {count})"
        text = text.replace(old, new, 1)
    shutil.copy2(path, str(path) + ".bak")
    path.write_text(text, encoding="utf-8")
    return "updated"


def main():
    for path in (HERE / "backend" / "app.py", HERE / "aws-deploy" / "app.py"):
        if path.is_file():
            print(f"{path.relative_to(HERE)}: {patch(path)}")
        else:
            print(f"{path.relative_to(HERE)}: not found, skipped")
    print("\nDone. Restart python app.py and refresh the browser with Ctrl+Shift+R.")


if __name__ == "__main__":
    main()