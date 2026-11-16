"""MellowTech document scanner.

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
