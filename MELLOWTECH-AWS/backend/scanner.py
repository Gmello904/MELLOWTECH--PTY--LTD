"""Vulnerability scanner for MellowTech customers: passive, non-destructive checks on verified domains.

A customer must prove they own a domain before it can be scanned, the same way Google Search
Console or an SSL certificate provider verifies ownership. Scans never attempt to exploit anything;
they only look at what is already publicly visible (HTTP headers, the TLS certificate, a handful of
commonly-exposed file paths), the same way browser security scanners like Mozilla Observatory do.
"""
import json
import secrets
import socket
import sqlite3
import ssl
import time
import urllib.request
from datetime import datetime, timezone

from flask import g, jsonify, request

SCAN_TIMEOUT = 8
MAX_DOMAINS_PER_ORG = 10
SCAN_COOLDOWN_SECONDS = 60
COMMON_EXPOSED_PATHS = (
    "/.env", "/.git/config", "/.git/HEAD", "/wp-config.php.bak", "/config.php.bak",
    "/.DS_Store", "/backup.sql", "/.aws/credentials", "/phpinfo.php",
)
_last_scan = {}   # domain_id -> unix time, to enforce the cooldown


def _ensure_tables(db_path):
    db = sqlite3.connect(db_path)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS scan_domains (
            id INTEGER PRIMARY KEY AUTOINCREMENT, org_id INTEGER NOT NULL, domain TEXT NOT NULL,
            verify_token TEXT NOT NULL, verified INTEGER NOT NULL DEFAULT 0, verified_at TEXT,
            created_by INTEGER, created_at TEXT NOT NULL,
            UNIQUE (org_id, domain));
        CREATE TABLE IF NOT EXISTS scan_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT, domain_id INTEGER NOT NULL,
            started_at TEXT NOT NULL, finished_at TEXT, score INTEGER, findings TEXT);
    """)
    db.commit()
    db.close()


def _clean_domain(value):
    value = str(value or "").strip().lower()
    for prefix in ("https://", "http://"):
        if value.startswith(prefix):
            value = value[len(prefix):]
    value = value.split("/")[0]
    if not value or len(value) > 253 or " " in value or "." not in value:
        return None
    return value


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "MellowTech-Scanner/1.0"})
    return urllib.request.urlopen(req, timeout=SCAN_TIMEOUT)


def _check_verification(domain, token):
    """The owner must publish our token at /.well-known/mellowtech-verify.txt."""
    for scheme in ("https", "http"):
        try:
            with _fetch(f"{scheme}://{domain}/.well-known/mellowtech-verify.txt") as response:
                body = response.read(2048).decode("utf-8", "ignore").strip()
                if body == token:
                    return True
        except Exception:
            continue
    return False


def _check_tls(domain, findings):
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=SCAN_TIMEOUT) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as tls:
                cert = tls.getpeercert()
        not_after = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        days_left = (not_after - datetime.now(timezone.utc)).days
        if days_left < 0:
            findings.append({"id": "tls_expired", "severity": "High", "title": "TLS certificate has expired",
                             "detail": "Visitors will see a security warning until this is renewed."})
        elif days_left < 14:
            findings.append({"id": "tls_expiring", "severity": "Medium", "title": "TLS certificate expires soon",
                             "detail": f"Only {days_left} day(s) left. Renew it before it lapses."})
    except ssl.SSLCertVerificationError:
        findings.append({"id": "tls_invalid", "severity": "High", "title": "TLS certificate is not trusted",
                         "detail": "Browsers will warn visitors that the connection may not be private."})
    except Exception:
        findings.append({"id": "tls_unreachable", "severity": "Medium", "title": "Could not connect over HTTPS on port 443",
                         "detail": "Confirm the site serves HTTPS and no firewall is blocking the scan."})


def _check_headers(domain, findings):
    try:
        with _fetch(f"https://{domain}/") as response:
            headers = {k.lower(): v for k, v in response.getheaders()}
            cookies = response.headers.get_all("set-cookie") if hasattr(response.headers, "get_all") else []
    except Exception:
        findings.append({"id": "https_unreachable", "severity": "High", "title": "The site did not respond over HTTPS",
                         "detail": "Visitors may be served the page over plain, unencrypted HTTP instead."})
        return

    if "strict-transport-security" not in headers:
        findings.append({"id": "no_hsts", "severity": "Medium", "title": "Missing Strict-Transport-Security header",
                         "detail": "Without HSTS, a visitor's very first request can still be intercepted over HTTP."})
    if "content-security-policy" not in headers:
        findings.append({"id": "no_csp", "severity": "Medium", "title": "Missing Content-Security-Policy header",
                         "detail": "A CSP limits the damage a cross-site scripting bug could do."})
    if "x-frame-options" not in headers and "content-security-policy" not in headers:
        findings.append({"id": "no_frame_options", "severity": "Low", "title": "Missing X-Frame-Options header",
                         "detail": "Without it, the site can be loaded inside another site's invisible frame (clickjacking)."})
    if "x-content-type-options" not in headers:
        findings.append({"id": "no_nosniff", "severity": "Low", "title": "Missing X-Content-Type-Options header",
                         "detail": "Browsers may guess a file's type in a way that enables an attack."})
    server = headers.get("server", "")
    if any(char.isdigit() for char in server):
        findings.append({"id": "server_version", "severity": "Low", "title": "Server header reveals a version number",
                         "detail": f"'{server}' helps an attacker pick a matching exploit. Hide the version string."})
    for cookie in (cookies or []):
        low = cookie.lower()
        if "secure" not in low or "httponly" not in low:
            findings.append({"id": "weak_cookie", "severity": "Medium", "title": "A cookie is missing Secure or HttpOnly",
                             "detail": "Cookies without these flags are easier to steal through scripts or over HTTP."})
            break


def _check_exposed_files(domain, findings):
    for path in COMMON_EXPOSED_PATHS:
        try:
            with _fetch(f"https://{domain}{path}") as response:
                if response.status == 200:
                    key = "exposed_" + path.strip("/").replace("/", "_").replace(".", "_")
                    findings.append({"id": key, "severity": "High",
                                     "title": f"A sensitive file may be publicly readable: {path}",
                                     "detail": "This path returned HTTP 200. Confirm it is not exposing secrets, and block it if so."})
        except Exception:
            continue   # 403, 404 or a timeout all mean "not exposed", which is the good outcome


def _run_checks(domain):
    findings = []
    _check_headers(domain, findings)
    _check_tls(domain, findings)
    _check_exposed_files(domain, findings)
    weight = {"High": 25, "Medium": 10, "Low": 4}
    score = max(0, 100 - sum(weight.get(f["severity"], 5) for f in findings))
    return score, findings


def init_scanner(app, db_path, h):
    """h carries helpers from app.py: get_db, error, iso, utcnow, login_required, audit, too_many."""
    _ensure_tables(db_path)
    get_db, error, iso, utcnow = h["get_db"], h["error"], h["iso"], h["utcnow"]
    login_required, audit, too_many = h["login_required"], h["audit"], h["too_many"]

    @app.get("/api/scanner/domains")
    @login_required()
    def scanner_list_domains():
        rows = get_db().execute(
            "SELECT id, domain, verify_token, verified, verified_at, created_at FROM scan_domains "
            "WHERE org_id = ? ORDER BY id DESC", (g.user["org_id"],)).fetchall()
        out = []
        for r in rows:
            last = get_db().execute(
                "SELECT score, finished_at, findings FROM scan_results WHERE domain_id = ? AND finished_at IS NOT NULL "
                "ORDER BY id DESC LIMIT 1", (r["id"],)).fetchone()
            out.append({"id": r["id"], "domain": r["domain"], "verified": bool(r["verified"]),
                       "verified_at": r["verified_at"], "created_at": r["created_at"], "verify_token": r["verify_token"],
                       "verify_url": f"https://{r['domain']}/.well-known/mellowtech-verify.txt",
                       "last_score": last["score"] if last else None,
                       "last_scanned_at": last["finished_at"] if last else None,
                       "last_findings": json.loads(last["findings"]) if last else []})
        return jsonify(out)

    @app.post("/api/scanner/domains")
    @login_required("admin")
    def scanner_add_domain():
        if too_many("scanner-add:" + str(g.user["org_id"]), 10, 3600):
            return error("Too many domains added. Try again later.", 429)
        domain = _clean_domain((request.get_json(silent=True) or {}).get("domain"))
        if not domain:
            return error("Enter a valid domain, for example yourcompany.com (no https:// needed).", 400)
        count = get_db().execute("SELECT COUNT(*) FROM scan_domains WHERE org_id = ?", (g.user["org_id"],)).fetchone()[0]
        if count >= MAX_DOMAINS_PER_ORG:
            return error(f"You can add up to {MAX_DOMAINS_PER_ORG} domains.", 400)
        token = secrets.token_urlsafe(18)
        db = get_db()
        try:
            cursor = db.execute(
                "INSERT INTO scan_domains (org_id, domain, verify_token, created_by, created_at) VALUES (?,?,?,?,?)",
                (g.user["org_id"], domain, token, g.user["id"], iso(utcnow())))
            db.commit()
        except sqlite3.IntegrityError:
            return error("That domain has already been added.", 409)
        audit("scanner_domain_added", domain)
        return jsonify({"id": cursor.lastrowid, "domain": domain, "verify_token": token,
                        "verify_url": f"https://{domain}/.well-known/mellowtech-verify.txt"}), 201

    @app.post("/api/scanner/domains/<int:domain_id>/verify")
    @login_required("admin")
    def scanner_verify_domain(domain_id):
        if too_many("scanner-verify:" + str(g.user["id"]), 20, 900):
            return error("Too many attempts. Wait a few minutes.", 429)
        row = get_db().execute("SELECT * FROM scan_domains WHERE id = ? AND org_id = ?",
                               (domain_id, g.user["org_id"])).fetchone()
        if not row:
            return error("Domain not found.", 404)
        if row["verified"]:
            return jsonify({"verified": True})
        if not _check_verification(row["domain"], row["verify_token"]):
            return error("The verification file was not found, or its contents did not match. "
                         "Publish the exact token at the address shown, then try again.", 400)
        db = get_db()
        db.execute("UPDATE scan_domains SET verified = 1, verified_at = ? WHERE id = ?", (iso(utcnow()), domain_id))
        db.commit()
        audit("scanner_domain_verified", row["domain"])
        return jsonify({"verified": True})

    @app.post("/api/scanner/domains/<int:domain_id>/scan")
    @login_required("admin")
    def scanner_run_scan(domain_id):
        row = get_db().execute("SELECT * FROM scan_domains WHERE id = ? AND org_id = ?",
                               (domain_id, g.user["org_id"])).fetchone()
        if not row:
            return error("Domain not found.", 404)
        if not row["verified"]:
            return error("Verify that you own this domain before scanning it.", 403)
        if time.time() - _last_scan.get(domain_id, 0) < SCAN_COOLDOWN_SECONDS:
            return error("Please wait a minute between scans of the same domain.", 429)
        _last_scan[domain_id] = time.time()

        db = get_db()
        cursor = db.execute("INSERT INTO scan_results (domain_id, started_at) VALUES (?,?)", (domain_id, iso(utcnow())))
        db.commit()
        score, findings = _run_checks(row["domain"])
        db.execute("UPDATE scan_results SET finished_at = ?, score = ?, findings = ? WHERE id = ?",
                   (iso(utcnow()), score, json.dumps(findings), cursor.lastrowid))
        db.commit()
        audit("scanner_scan_run", f"{row['domain']} score {score}")
        return jsonify({"score": score, "findings": findings})

    @app.post("/api/scanner/domains/<int:domain_id>/remove")
    @login_required("admin")
    def scanner_remove_domain(domain_id):
        db = get_db()
        row = db.execute("SELECT domain FROM scan_domains WHERE id = ? AND org_id = ?",
                         (domain_id, g.user["org_id"])).fetchone()
        if not row:
            return error("Domain not found.", 404)
        db.execute("DELETE FROM scan_results WHERE domain_id = ?", (domain_id,))
        db.execute("DELETE FROM scan_domains WHERE id = ?", (domain_id,))
        db.commit()
        audit("scanner_domain_removed", row["domain"])
        return jsonify({"ok": True})