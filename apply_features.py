"""Part 1: Document Scanner, Security Roles page and the paywall (locked features + log).

Put this file in the MELLOWTECH folder (next to index.html) and run:
    python apply_features.py
Backups are saved next to each changed file as *.bak
"""
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent

# =====================================================================================
# 1) New backend file: docscan.py
# =====================================================================================
DOCSCAN_PY = r'''"""MellowTech document scanner.

Looks at the hidden details inside a PDF, JPG or PNG (which program made it, and when it was created and
changed) and reports warning signs that it was edited or generated. It cannot prove that a document is genuine:
always confirm important documents with the company or person who issued them.
"""
import base64
import hashlib
import io
import re
from datetime import datetime, timedelta

from flask import g, jsonify, request

try:
    from PIL import Image
except ImportError:                 # Pillow is optional; without it the image checks are simpler
    Image = None

MAX_BYTES = 5 * 1024 * 1024

DOC_TYPES = {
    "invoice": "Invoice",
    "payslip": "Payslip",
    "bank_statement": "Bank statement",
    "id_document": "ID document or passport",
    "proof_of_address": "Proof of address or utility bill",
    "tax_document": "Tax document",
    "contract": "Contract or agreement",
    "qualification": "Qualification certificate",
    "medical": "Medical certificate",
    "other": "Other document",
}

CHECKS = {
    "invoice": ["Phone the supplier on a number you already trust, not the number printed on the invoice.",
                "Compare the bank details with earlier invoices from the same supplier.",
                "Check the company with CIPC and the VAT number with the SARS VAT vendor search.",
                "Check that the line items, VAT and total add up."],
    "payslip": ["Contact the employer's HR or payroll using details you found yourself.",
                "Check that gross pay minus PAYE, UIF and other deductions equals the net pay.",
                "Compare the net pay with the deposits on the bank statement.",
                "Check that the employer name and tax reference match other documents."],
    "bank_statement": ["Confirm the statement with the bank, or ask the person to share it from their banking app.",
                       "Check that the running balance is correct on every line.",
                       "Check that fonts, spacing and the layout are the same on every page."],
    "id_document": ["Verify the ID number through official channels such as Home Affairs.",
                    "For a South African ID number, the first six digits are the date of birth: check they match.",
                    "Ask to see the original document in person."],
    "proof_of_address": ["Check the issuer's own website or phone the issuer to confirm the account.",
                         "Check that the date is recent and the address matches other documents."],
    "tax_document": ["Verify the document with SARS (eFiling or the SARS contact centre).",
                     "Check the reference numbers against other tax documents."],
    "contract": ["Check the signatures and initials on every page.",
                 "Compare the copy with the other party's copy.",
                 "Check that the page numbers run in order and nothing is missing."],
    "qualification": ["Verify with the institution that issued it (or with SAQA for South African qualifications).",
                      "Check the name, qualification and year with the institution."],
    "medical": ["Phone the practice using a number you found yourself.",
                "Check the practitioner's registration number with their professional council."],
    "other": ["Confirm the document with whoever issued it, using contact details you found yourself.",
              "Compare it with earlier genuine documents from the same source."],
}

IMAGE_EDITORS = ("photoshop", "gimp", "pixlr", "paint.net", "snapseed", "lightroom", "affinity photo",
                 "illustrator", "inkscape", "picsart", "fotor", "photopea")
ONLINE_TOOLS = ("canva", "ilovepdf", "smallpdf", "sejda", "pdfescape", "pdf24", "pdfelement", "wondershare",
                "xodo", "pdffiller", "lightpdf", "soda pdf", "docfly", "pdfsimpli")
AI_MARKERS = ("trainedalgorithmicmedia", "midjourney", "stable diffusion", "dall-e", "openai", "adobe firefly")


class Report:
    def __init__(self):
        self.findings, self.facts, self.score = [], [], 0

    def add(self, severity, title, detail, points):
        if any(f["title"] == title for f in self.findings):
            return
        self.findings.append({"severity": severity, "title": title, "detail": detail, "points": points})
        self.score += points

    def fact(self, label, value):
        if value:
            self.facts.append({"label": label, "value": str(value)[:200]})


def clean(value):
    return (value or "").replace("\x00", "").replace("\xfe\xff", "").replace("\xff\xfe", "").strip()


def human(delta):
    seconds = int(delta.total_seconds())
    if seconds >= 86400:
        return f"{seconds // 86400} day(s)"
    if seconds >= 3600:
        return f"{seconds // 3600} hour(s)"
    return f"{max(1, seconds // 60)} minute(s)"


def parse_date(value):
    value = (value or "").strip()
    match = re.match(r"D:(\d{4})(\d\d)?(\d\d)?(\d\d)?(\d\d)?(\d\d)?", value)
    if match:
        parts = [int(p) if p else d for p, d in zip(match.groups(), (0, 1, 1, 0, 0, 0))]
    else:
        match = re.match(r"(\d{4})[-:](\d\d)[-:](\d\d)[T ](\d\d):(\d\d):(\d\d)", value)
        if not match:
            return None
        parts = [int(p) for p in match.groups()]
    try:
        return datetime(*parts)
    except ValueError:
        return None


def pdf_field(text, name):
    match = re.search(r"/" + name + r"\s*\(((?:\\.|[^\\)]){0,200})\)", text)
    if match:
        return clean(match.group(1).replace("\\(", "(").replace("\\)", ")"))
    match = re.search(r"/" + name + r"\s*<((?:[0-9A-Fa-f]{2}){1,200})>", text)
    if match:
        data = bytes.fromhex(match.group(1))
        if data[:2] in (b"\xfe\xff", b"\xff\xfe"):
            return clean(data.decode("utf-16", "ignore"))
        return clean(data.decode("latin-1"))
    return ""


def xmp_value(xmp, tag):
    match = re.search(re.escape(tag) + r'(?:>|\s*=\s*")([^<"]{1,200})', xmp)
    return match.group(1).strip() if match else ""


def check_tools(report, label, value, shown=None):
    if not value:
        return
    low = value.lower()
    shown = shown or value
    editor = next((n for n in IMAGE_EDITORS if n in low), None)
    online = next((n for n in ONLINE_TOOLS if n in low), None)
    if editor:
        report.add("High", "Made or changed in an image editor",
                   f"{label}: {shown}. Genuine invoices, payslips and statements come from accounting, payroll or "
                   "banking systems, not from image editors.", 45)
    elif online:
        report.add("Medium", "Made or changed with an online design or PDF editing tool",
                   f"{label}: {shown}. Genuine documents are normally produced by the issuer's own system.", 25)


def check_ai(report, low_text):
    marker = next((m for m in AI_MARKERS if m in low_text), None)
    if marker:
        report.add("High", "Marked as AI-generated",
                   f"The file's hidden details contain an AI marker ({marker}).", 60)


def jpeg_metadata(raw):
    out, i = [], 2
    while i + 4 <= len(raw) and raw[i] == 0xFF:
        marker = raw[i + 1]
        if marker in (0xDA, 0xD9):
            break
        if marker == 0x01 or 0xD0 <= marker <= 0xD7 or marker == 0xFF:
            i += 1 if marker == 0xFF else 2
            continue
        length = int.from_bytes(raw[i + 2:i + 4], "big")
        if length < 2:
            break
        if 0xE0 <= marker <= 0xEF or marker == 0xFE:
            out.append(raw[i + 4:i + 2 + length])
        i += 2 + length
    return b" ".join(out)


def png_metadata(raw):
    out, i = [], 8
    while i + 8 <= len(raw):
        length = int.from_bytes(raw[i:i + 4], "big")
        kind = raw[i + 4:i + 8]
        if kind in (b"tEXt", b"iTXt", b"eXIf"):
            out.append(raw[i + 8:i + 8 + length])
        if kind == b"IEND":
            break
        i += 12 + length
    return b" ".join(out)


def analyse_pdf(raw, report):
    text = raw.decode("latin-1")
    found = re.search(r"<x:xmpmeta.*?</x:xmpmeta>", text, re.S)
    xmp = found.group(0) if found else ""
    producer = pdf_field(text, "Producer") or xmp_value(xmp, "pdf:Producer")
    creator = pdf_field(text, "Creator") or xmp_value(xmp, "xmp:CreatorTool")
    created_raw = pdf_field(text, "CreationDate") or xmp_value(xmp, "xmp:CreateDate")
    modified_raw = pdf_field(text, "ModDate") or xmp_value(xmp, "xmp:ModifyDate")
    created, modified = parse_date(created_raw), parse_date(modified_raw)

    report.fact("Made with", creator)
    report.fact("PDF producer", producer)
    report.fact("Created", created.strftime("%Y-%m-%d %H:%M") if created else "")
    report.fact("Last changed", modified.strftime("%Y-%m-%d %H:%M") if modified else "")

    check_tools(report, "Made with", creator)
    check_tools(report, "PDF producer", producer)
    check_ai(report, xmp.lower() + " " + (creator + " " + producer).lower())

    saves = raw.count(b"%%EOF") - (1 if b"/Linearized" in raw[:2048] else 0)
    report.fact("Saved versions", saves if saves > 0 else "")
    if saves > 1:
        report.add("Medium", "Saved more than once",
                   f"The file holds {saves} saved versions. A PDF is saved again when it is edited, but also when it "
                   "is signed or a form is filled in.", 15)

    if created and modified and (modified - created).total_seconds() > 120:
        report.add("Medium", "Changed after it was created",
                   f"The file was changed {human(modified - created)} after it was created.", 20)
    limit = datetime.now() + timedelta(days=1)
    if (created and created > limit) or (modified and modified > limit):
        report.add("High", "Dated in the future", "A date inside the file is later than today.", 25)
    if b"/ByteRange" in raw and b"/Sig" in raw:
        report.add("Info", "Has a digital signature",
                   "Open the PDF in Adobe Reader to check that the signature is valid and nothing changed after it.", 0)
    if not (producer or creator or created or modified):
        report.add("Low", "Hidden details are missing",
                   "The file has no readable producer or dates. They may have been removed, or stored in a way this "
                   "scanner cannot read.", 10)


def analyse_image(raw, kind, report):
    blob = jpeg_metadata(raw) if kind == "jpg" else png_metadata(raw)
    low = blob.decode("latin-1").lower()
    check_ai(report, low)
    for name in IMAGE_EDITORS + ONLINE_TOOLS:
        if name in low:
            check_tools(report, "The image's hidden details mention", name, shown=name.title())
            break

    if Image is None:
        return
    try:
        img = Image.open(io.BytesIO(raw))
        report.fact("Image size", f"{img.width} x {img.height} pixels")
        exif = img.getexif()
        software = clean(str(exif.get(305, "") or ""))
        modified = parse_date(str(exif.get(306, "") or ""))
        try:
            original = parse_date(str(exif.get_ifd(0x8769).get(36867, "") or ""))
        except Exception:
            original = None
        report.fact("Made with", software)
        report.fact("Photo taken", original.strftime("%Y-%m-%d %H:%M") if original else "")
        report.fact("Last changed", modified.strftime("%Y-%m-%d %H:%M") if modified else "")
        check_tools(report, "Made with", software)
        if original and modified and (modified - original).total_seconds() > 120:
            report.add("Medium", "Changed after the photo was taken",
                       f"The image was saved {human(modified - original)} after it was taken.", 20)
        if kind == "jpg" and len(exif) == 0:
            report.add("Low", "No camera details",
                       "A photo straight from a phone or scanner normally carries camera details. This one has none: "
                       "it may be a screenshot or a re-saved copy.", 5)
    except Exception:
        pass


def detect(raw):
    if b"%PDF-" in raw[:1024]:
        return "pdf"
    if raw[:3] == b"\xff\xd8\xff":
        return "jpg"
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    return None


def verdict(score):
    if score >= 50:
        return "High risk: likely edited or generated", "high"
    if score >= 20:
        return "Needs a closer look", "medium"
    return "No warning signs found", "low"


def analyse(raw, kind):
    report = Report()
    if kind == "pdf":
        analyse_pdf(raw, report)
    else:
        analyse_image(raw, kind, report)
    score = min(100, report.score)
    if any(f["severity"] == "High" for f in report.findings):
        score = max(score, 50)          # one serious sign is enough to call it high risk
    text, level = verdict(score)
    order = {"High": 0, "Medium": 1, "Low": 2, "Info": 3}
    findings = sorted(report.findings, key=lambda f: order.get(f["severity"], 9))
    return score, text, level, [{k: f[k] for k in ("severity", "title", "detail")} for f in findings], report.facts


def init_docscan(app, deps):
    get_db, error, iso, utcnow = deps["get_db"], deps["error"], deps["iso"], deps["utcnow"]
    login_required, audit, too_many, locked = deps["login_required"], deps["audit"], deps["too_many"], deps["locked"]

    def ensure_table(db):
        db.execute("CREATE TABLE IF NOT EXISTS document_scans (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                   "org_id INTEGER NOT NULL, user_id INTEGER NOT NULL, file_name TEXT NOT NULL, doc_type TEXT NOT NULL, "
                   "sha256 TEXT NOT NULL, score INTEGER NOT NULL, verdict TEXT NOT NULL, created_at TEXT NOT NULL)")

    @app.post("/api/documents/scan")
    @login_required()
    def docscan_run():
        denied = locked("document_scan")
        if denied:
            return denied
        if too_many("docscan:" + str(g.user["id"]), 20, 600):
            return error("Too many scans. Wait a few minutes and try again.", 429)
        data = request.get_json(silent=True) or {}
        name = str(data.get("name", "document"))[:120]
        doc_type = data.get("type") if data.get("type") in DOC_TYPES else "other"
        try:
            raw = base64.b64decode(str(data.get("data", "")), validate=True)
        except Exception:
            return error("The file could not be read. Please try again.", 400)
        if not raw:
            return error("The file is empty.", 400)
        if len(raw) > MAX_BYTES:
            return error("That file is bigger than 5 MB.", 413)
        kind = detect(raw)
        if not kind:
            return error("Only PDF, JPG and PNG files can be scanned.", 400)

        score, text, level, findings, facts = analyse(raw, kind)
        digest = hashlib.sha256(raw).hexdigest()
        db = get_db()
        ensure_table(db)
        db.execute("INSERT INTO document_scans (org_id,user_id,file_name,doc_type,sha256,score,verdict,created_at) "
                   "VALUES (?,?,?,?,?,?,?,?)",
                   (g.user["org_id"], g.user["id"], name, doc_type, digest, score, text, iso(utcnow())))
        db.commit()
        audit("document_scanned", f"{name} ({doc_type}) risk {score}")
        return jsonify({"name": name, "type_label": DOC_TYPES[doc_type], "score": score, "verdict": text,
                        "level": level, "findings": findings, "facts": facts, "checks": CHECKS[doc_type],
                        "sha256": digest})

    @app.get("/api/documents/history")
    @login_required()
    def docscan_history():
        db = get_db()
        ensure_table(db)
        rows = db.execute("SELECT file_name, doc_type, verdict, score, created_at FROM document_scans "
                          "WHERE org_id = ? ORDER BY id DESC LIMIT 20", (g.user["org_id"],)).fetchall()
        return jsonify([{"name": r["file_name"], "type": DOC_TYPES.get(r["doc_type"], "Other document"),
                         "verdict": r["verdict"], "score": r["score"], "at": r["created_at"]} for r in rows])
'''

# =====================================================================================
# 2) Changes to app.py
# =====================================================================================
APP_HELPERS = r'''# ---------------------------------------------------------------- paid features (locked until the plan is paid for)
FEATURE_PLANS = {      # feature: (plan that unlocks it, name shown to customers). MellowTech staff are never locked.
    "document_scan":  ("starter",  "Document Scanner"),
    "ip_block":       ("starter",  "IP address blocking"),
    "device_command": ("business", "Device isolation, virus scans and USB control"),
}
PLAN_ORDER = {"free": 0, "starter": 1, "business": 2, "enterprise": 3}


def current_plan(org_id):
    org = get_db().execute("SELECT plan, plan_expires FROM organisations WHERE id = ?", (org_id,)).fetchone()
    plan = org["plan"] if org else "free"
    if plan != "free" and org["plan_expires"] and org["plan_expires"] < iso(utcnow()):
        plan = "free"        # paid time has run out
    return plan


def locked(feature):
    """Returns an error reply when the signed-in company's plan does not include the feature, and logs the attempt."""
    user = g.user
    if user["is_platform"]:
        return None
    needs, label = FEATURE_PLANS[feature]
    plan = current_plan(user["org_id"])
    if PLAN_ORDER.get(plan, 0) >= PLAN_ORDER[needs]:
        return None
    audit("feature_locked", f"{user['org_name']} ({user['email']}) tried '{label}' on the {plan} plan; it needs {needs}")
    return jsonify({"error": f"{label} is included in {needs.title()} or a higher plan. Open Billing & Plans to unlock it.",
                    "locked": True, "needs": needs}), 402


@app.get("/api/features")
@login_required()
def feature_list():
    plan = current_plan(g.user["org_id"])
    rank = PLAN_ORDER.get(plan, 0)
    staff = bool(g.user["is_platform"])
    return jsonify({"plan": plan, "features": [
        {"key": k, "label": label, "needs": need, "unlocked": staff or rank >= PLAN_ORDER[need]}
        for k, (need, label) in FEATURE_PLANS.items()]})


@app.get("/api/locked-log")
@login_required("platform_admin")
def locked_log():
    rows = get_db().execute("SELECT ts, detail FROM audit_log WHERE action = 'feature_locked' "
                            "ORDER BY id DESC LIMIT 100").fetchall()
    return jsonify([dict(r) for r in rows])


'''

APP_INIT = '''    current_user_id=current_user_id, current_org_id=current_org_id))
docscan.init_docscan(app, dict(
    get_db=get_db, error=error, iso=iso, utcnow=utcnow,
    login_required=login_required, audit=audit, too_many=too_many, locked=locked))
'''

APP_REPLACEMENTS = [
    ("import scanner\nimport payfast\n",
     "import scanner\nimport payfast\nimport docscan\n"),

    ("    MAX_CONTENT_LENGTH=16 * 1024,\n",
     "    MAX_CONTENT_LENGTH=8 * 1024 * 1024,      # normal requests are held to 16 KB in api_guard; document scans may be larger\n"),

    ('    if request.path.startswith("/api/") and request.method in ("POST", "PUT", "PATCH", "DELETE"):\n',
     '    if request.path.startswith("/api/") and request.method in ("POST", "PUT", "PATCH", "DELETE"):\n'
     '        if request.path != "/api/documents/scan" and (request.content_length or 0) > 16 * 1024:\n'
     '            return error("That request is too large.", 413)\n'),

    ("def create_block():\n",
     'def create_block():\n    lock = locked("ip_block")\n    if lock:\n        return lock\n'),

    ('    """An administrator sends one action to one laptop (virus scan, isolate, USB control ...)."""\n',
     '    """An administrator sends one action to one laptop (virus scan, isolate, USB control ...)."""\n'
     '    lock = locked("device_command")\n    if lock:\n        return lock\n'),

    ("\ninitialize_database()\nscanner.init_scanner(",
     "\n" + APP_HELPERS + "initialize_database()\nscanner.init_scanner("),

    ("    current_user_id=current_user_id, current_org_id=current_org_id))\n", APP_INIT),
]

# =====================================================================================
# 3) Changes to index.html
# =====================================================================================
NAV_BUTTONS = '''<button type="button" class="nav-button" data-page="docscan">
                <svg class="icon" aria-hidden="true"><use href="#i-list"/></svg>Document Scanner
            </button>
            <button type="button" class="nav-button" data-page="roles">
                <svg class="icon" aria-hidden="true"><use href="#i-users"/></svg>Security Roles
            </button>
            '''

SECTIONS = '''<!-- ========== DOCUMENT SCANNER ========== -->
        <section id="docscan" class="page" hidden>
            <h2>Document Scanner</h2>
            <p class="page-description">Check an invoice, payslip or other document for signs that it was edited or generated.</p>

            <div id="ds-lock" class="bill-notice info" hidden>
                Locked: the Document Scanner is included in Starter Protection or a higher plan.
                <button type="button" class="btn-small" id="ds-unlock" style="margin-left:12px">Unlock with a plan</button>
            </div>

            <div class="panel">
                <h3>Scan a document</h3>
                <div class="form-row" style="margin-top:0;border-top:0;padding-top:0">
                    <label class="field">Document type
                        <select id="ds-type">
                            <option value="invoice">Invoice</option>
                            <option value="payslip">Payslip</option>
                            <option value="bank_statement">Bank statement</option>
                            <option value="id_document">ID document or passport</option>
                            <option value="proof_of_address">Proof of address or utility bill</option>
                            <option value="tax_document">Tax document</option>
                            <option value="contract">Contract or agreement</option>
                            <option value="qualification">Qualification certificate</option>
                            <option value="medical">Medical certificate</option>
                            <option value="other">Other document</option>
                        </select>
                    </label>
                    <label class="field" style="flex:1">File (PDF, JPG or PNG, up to 5 MB)
                        <input type="file" id="ds-file" accept=".pdf,.jpg,.jpeg,.png">
                    </label>
                    <button type="button" class="btn-small" id="ds-scan">Scan document</button>
                </div>
                <p class="page-description" style="margin:10px 0 0">The scan reads the hidden details inside the file: which program made it, and when it was created and changed. It shows warning signs only. It cannot prove that a document is genuine, so always confirm important documents with whoever issued them.</p>
            </div>

            <div id="ds-message" class="result-message" role="status" aria-live="polite"></div>
            <div id="ds-result"></div>

            <div class="panel">
                <h3>Recent scans</h3>
                <div class="table-scroll">
                    <table class="events-table">
                        <caption class="sr-only">Recent document scans</caption>
                        <thead><tr><th scope="col">Time</th><th scope="col">Document</th><th scope="col">Type</th><th scope="col">Result</th></tr></thead>
                        <tbody id="ds-history"><tr><td colspan="4">Loading...</td></tr></tbody>
                    </table>
                </div>
            </div>
        </section>

        <!-- ========== SECURITY ROLES ========== -->
        <section id="roles" class="page" hidden>
            <h2>Security Roles</h2>
            <p class="page-description">The cybersecurity roles that keep organisations safe.</p>
            <div class="rl-grid" id="roles-grid"></div>
        </section>

        '''

BILLING_PANELS = '''<div class="panel" id="feature-locks">
                <h3>What each plan unlocks</h3>
                <p class="page-description" style="margin-top:4px">Some features stay locked until a plan that includes them is paid for.</p>
                <div id="feature-locks-list">Loading...</div>
            </div>
            <div class="panel" id="lock-log-panel" hidden>
                <h3>Locked-feature log</h3>
                <p class="page-description" style="margin-top:4px">Times a customer tried a feature their plan does not include.</p>
                <div class="table-scroll">
                    <table class="events-table">
                        <caption class="sr-only">Locked feature attempts</caption>
                        <thead><tr><th scope="col">Time</th><th scope="col">What happened</th></tr></thead>
                        <tbody id="lock-log-body"></tbody>
                    </table>
                </div>
            </div>

            '''

EXTRA_HTML = r'''<!-- Document Scanner, Security Roles and locked features -->
    <style>
        .rl-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .rl-card ul { margin: 10px 0 12px; padding-left: 20px; display: grid; gap: 6px; }
        .rl-skills { margin: 0; font-size: 13px; color: #68737d; }
    </style>
    <script>
    (function () {
        var csrf = "";
        var me = null;
        var NEEDS = { starter: "Starter Protection", business: "Business Protection", enterprise: "Premium Enterprise Protection" };

        /* Edit this list to change the Security Roles page. */
        var ROLES = [
            { name: "AI Security Engineer",
              points: ["Protects AI models and applications against attacks.", "Tests AI systems for security weaknesses.", "Protects sensitive data used by AI."],
              skills: "Python, cybersecurity, AI and machine learning." },
            { name: "Incident Response Analyst",
              points: ["Investigates confirmed cyberattacks.", "Contains threats to prevent further damage.", "Examines digital evidence to determine what happened.", "Helps organisations recover securely after an attack."],
              skills: "Digital forensics, security logs, investigation and problem-solving." },
            { name: "Cloud Security Engineer",
              points: ["Protects data, applications and systems stored in the cloud.", "Secures cloud platforms such as AWS and Microsoft Azure.", "Controls who can access cloud resources."],
              skills: "Cloud computing, networking, Linux and IAM (Identity and Access Management)." },
            { name: "SOC Analyst (Security Operations Centre)",
              points: ["Monitors computer systems for cyber threats.", "Investigates suspicious activities and security alerts.", "Detects and helps stop cyberattacks."],
              skills: "Networking, Linux, SIEM tools and threat detection." },
            { name: "GRC Analyst (Governance, Risk and Compliance)",
              points: ["Creates cybersecurity policies and procedures.", "Identifies and assesses cyber risks.", "Ensures companies follow laws and security standards.", "Supports AI governance and cybersecurity strategy."],
              skills: "Communication, risk assessment, report writing and compliance." }
        ];

        function $(id) { return document.getElementById(id); }

        function esc(value) {
            return String(value == null ? "" : value).replace(/[&<>"']/g, function (c) {
                return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
            });
        }

        function api(path, body) {
            var options = { credentials: "same-origin", headers: { "Content-Type": "application/json" } };
            if (body !== undefined) {
                options.method = "POST";
                options.headers["X-CSRF-Token"] = csrf;
                options.body = JSON.stringify(body);
            }
            return fetch(path, options).then(function (response) {
                return response.json().catch(function () { return {}; }).then(function (data) {
                    if (!response.ok) {
                        var problem = new Error(data.error || "Something went wrong.");
                        problem.locked = !!data.locked;
                        throw problem;
                    }
                    return data;
                });
            });
        }

        function openBilling() {
            var button = document.querySelector('.nav-button[data-page="billing"]');
            if (button) { button.click(); }
        }

        function say(text, kind) {
            var box = $("ds-message");
            box.textContent = text || "";
            box.style.color = kind === "err" ? "#b42318" : kind === "ok" ? "#12906e" : "";
        }

        function badgeClass(severity) {
            return severity === "High" ? "danger" : severity === "Medium" ? "warning" : "safe";
        }

        function drawRoles() {
            var host = $("roles-grid");
            if (!host) { return; }
            host.innerHTML = ROLES.map(function (role) {
                return '<div class="panel rl-card"><h3>' + esc(role.name) + "</h3><ul>" +
                    role.points.map(function (point) { return "<li>" + esc(point) + "</li>"; }).join("") +
                    '</ul><p class="rl-skills"><b>Key skills:</b> ' + esc(role.skills) + "</p></div>";
            }).join("");
        }

        function loadFeatures() {
            api("/api/features").then(function (data) {
                $("feature-locks-list").innerHTML = data.features.map(function (f) {
                    var tag = f.unlocked
                        ? '<span class="badge safe">Unlocked</span>'
                        : '<span class="badge danger">Locked: needs ' + esc(NEEDS[f.needs] || f.needs) + "</span>";
                    return '<div class="status-item"><span>' + esc(f.label) + "</span>" + tag + "</div>";
                }).join("");
                var scan = data.features.filter(function (f) { return f.key === "document_scan"; })[0];
                $("ds-lock").hidden = !scan || scan.unlocked;
            }).catch(function () {});
        }

        function loadLockLog() {
            api("/api/locked-log").then(function (rows) {
                $("lock-log-panel").hidden = false;
                $("lock-log-body").innerHTML = rows.length
                    ? rows.map(function (r) {
                        return "<tr><td>" + esc(new Date(r.ts).toLocaleString()) + "</td><td>" + esc(r.detail) + "</td></tr>";
                    }).join("")
                    : '<tr><td colspan="2">Nothing yet.</td></tr>';
            }).catch(function () {});
        }

        function loadHistory() {
            api("/api/documents/history").then(function (rows) {
                $("ds-history").innerHTML = rows.length
                    ? rows.map(function (r) {
                        return "<tr><td>" + esc(new Date(r.at).toLocaleString()) + "</td><td>" + esc(r.name) + "</td><td>" +
                            esc(r.type) + "</td><td>" + esc(r.verdict) + " (" + esc(r.score) + "/100)</td></tr>";
                    }).join("")
                    : '<tr><td colspan="4">No documents scanned yet.</td></tr>';
            }).catch(function () {});
        }

        function show(r) {
            var colour = r.level === "high" ? "#b42318" : r.level === "medium" ? "#c47b00" : "#12906e";
            var html = '<div class="panel"><div class="panel-header"><div><h3>' + esc(r.name) + "</h3><p>" + esc(r.type_label) +
                " &middot; SHA-256 " + esc(r.sha256.slice(0, 16)) + '...</p></div><span class="badge" style="background:' +
                colour + "22;color:" + colour + '">' + esc(r.verdict) + " (" + esc(r.score) + "/100)</span></div>";

            if (r.findings.length) {
                html += '<div class="table-scroll"><table class="events-table"><thead><tr><th>Level</th><th>Warning sign</th><th>Detail</th></tr></thead><tbody>';
                r.findings.forEach(function (f) {
                    html += '<tr><td><span class="badge ' + badgeClass(f.severity) + '">' + esc(f.severity) + "</span></td><td>" +
                        esc(f.title) + "</td><td>" + esc(f.detail) + "</td></tr>";
                });
                html += "</tbody></table></div>";
            } else {
                html += '<p class="result-message">No warning signs were found in the hidden details of this file.</p>';
            }

            if (r.facts.length) {
                html += "<h3 style=\"margin-top:18px\">What the file says about itself</h3>";
                r.facts.forEach(function (f) {
                    html += '<div class="status-item"><span>' + esc(f.label) + "</span><strong>" + esc(f.value) + "</strong></div>";
                });
            }

            html += '<h3 style="margin-top:18px">Always check these yourself</h3><ul style="margin:8px 0 0;padding-left:20px;display:grid;gap:6px">' +
                r.checks.map(function (c) { return "<li>" + esc(c) + "</li>"; }).join("") + "</ul>" +
                '<p class="page-description" style="margin-top:14px">This scan reads hidden file details only. A clean result does not prove a document is genuine, and a warning does not prove it is fake.</p></div>';
            $("ds-result").innerHTML = html;
        }

        function scan() {
            var file = $("ds-file").files[0];
            if (!file) { say("Choose a file first.", "err"); return; }
            if (file.size > 5 * 1024 * 1024) { say("That file is bigger than 5 MB.", "err"); return; }
            var button = $("ds-scan");
            var reader = new FileReader();
            reader.onload = function () {
                var data = String(reader.result).split(",")[1] || "";
                say("Scanning...", "");
                button.disabled = true;
                api("/api/documents/scan", { name: file.name, type: $("ds-type").value, data: data }).then(function (result) {
                    say("", "");
                    show(result);
                    loadHistory();
                }).catch(function (problem) {
                    say(problem.message, "err");
                    if (problem.locked) { loadFeatures(); }
                }).then(function () { button.disabled = false; });
            };
            reader.onerror = function () { say("The file could not be read.", "err"); };
            reader.readAsDataURL(file);
        }

        document.addEventListener("DOMContentLoaded", function () {
            drawRoles();
            $("ds-scan").addEventListener("click", scan);
            $("ds-unlock").addEventListener("click", openBilling);

            api("/api/auth/me").then(function (data) {
                csrf = data.csrf;
                me = data.user;
                loadFeatures();
                loadHistory();
                if (me.is_platform && me.role === "admin") { loadLockLog(); }
            }).catch(function () {});

            var scanNav = document.querySelector('.nav-button[data-page="docscan"]');
            if (scanNav) { scanNav.addEventListener("click", function () { loadFeatures(); loadHistory(); }); }
            var billNav = document.querySelector('.nav-button[data-page="billing"]');
            if (billNav) {
                billNav.addEventListener("click", function () {
                    loadFeatures();
                    if (me && me.is_platform && me.role === "admin") { loadLockLog(); }
                });
            }
        });
    })();
    </script>
'''

INDEX_MARKER = 'id="docscan"'

INDEX_REPLACEMENTS = [
    ('<button type="button" class="nav-button" data-page="company">',
     NAV_BUTTONS + '<button type="button" class="nav-button" data-page="company">'),
    ("<!-- ========== COMPANY ========== -->",
     SECTIONS + "<!-- ========== COMPANY ========== -->"),
    ('<div class="bl-trust">',
     BILLING_PANELS + '<div class="bl-trust">'),
    ("</body>",
     EXTRA_HTML + "</body>"),
]


# =====================================================================================
# Runner
# =====================================================================================
def apply(path, replacements, marker):
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return "already updated"
    for old, new in replacements:
        count = text.count(old)
        if count != 1:
            return f"NOT changed: could not find a unique match for {old.strip()[:50]!r} (found {count})"
        text = text.replace(old, new, 1)
    shutil.copy2(path, str(path) + ".bak")
    path.write_text(text, encoding="utf-8")
    return "updated"


def main():
    for folder in (HERE / "backend", HERE / "aws-deploy"):
        if (folder / "app.py").is_file():
            (folder / "docscan.py").write_text(DOCSCAN_PY, encoding="utf-8")
            print(f"{folder.name}\\docscan.py: written")
            print(f"{folder.name}\\app.py: {apply(folder / 'app.py', APP_REPLACEMENTS, 'FEATURE_PLANS')}")
    for path in (HERE / "index.html", HERE / "aws-deploy" / "index.html"):
        if path.is_file():
            print(f"{path.relative_to(HERE)}: {apply(path, INDEX_REPLACEMENTS, INDEX_MARKER)}")
    print("\nDone. Restart python app.py and refresh the browser with Ctrl+Shift+R.")


if __name__ == "__main__":
    main()