"""One-time update for MellowTech: real email sending, settings file, and live-server support.

Put this file in the same folder as app.py (the backend folder) and run:   python update_email.py
It makes a backup called app.py.bak first, so nothing is lost.
"""
import py_compile, shutil, sys
from pathlib import Path

path = Path(__file__).resolve().parent / "app.py"
text = path.read_text(encoding="utf-8")

if "def deliver_email" in text:
    sys.exit("app.py is already updated. Nothing to do.")


def replace(old, new):
    global text
    if text.count(old) != 1:
        sys.exit("Could not update automatically: this line was not found exactly once in app.py:\n  " + old.strip()[:90] +
                 "\nPlease send this message to your helper and they will give you the full file.")
    text = text.replace(old, new)


replace("from werkzeug.exceptions import HTTPException\n",
        "from werkzeug.exceptions import HTTPException\nfrom werkzeug.middleware.proxy_fix import ProxyFix\n")

replace("HERE = Path(__file__).resolve().parent\n", '''HERE = Path(__file__).resolve().parent


def _load_settings_file():
    """Optional backend/settings.env with lines like KEY=value. Real environment variables always win."""
    file = HERE / "settings.env"
    if not file.is_file():
        return
    for line in file.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_settings_file()
''')

replace('VERSION = "2026.10.11-approval"      # the page and app.js must carry the same version\n',
        'VERSION = "2026.10.11-approval"      # the page and app.js must carry the same version\n'
        'BEHIND_PROXY = os.environ.get("MELLOWTECH_BEHIND_PROXY") == "1"      # live behind Caddy or Nginx\n')

replace("app = Flask(__name__, static_folder=None)\n", '''app = Flask(__name__, static_folder=None)
if BEHIND_PROXY:        # trust the real visitor address that Caddy / Nginx passes on (needed for rate limits and logs)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
''')

replace('''    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response''', '''    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    if BASE_URL.startswith("https://"):
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
    return response''')

start = text.index("def send_email(to, subject, body):")
end = text.index("# ---------------------------------------------------------------- sessions and guards")
text = text[:start] + '''def local_url(url):
    return (urllib.parse.urlparse(url).hostname or "") in ("127.0.0.1", "localhost", "::1")


def email_ready():
    """True when real email is set up, or when running on this computer (links are then printed in the server window)."""
    return bool(os.environ.get("SMTP_HOST")) or local_url(BASE_URL)


def deliver_email(to, subject, body):
    """Send one email. Raises an exception that explains why when it cannot be sent."""
    host = os.environ.get("SMTP_HOST")
    if not host:                                    # development: show the email in this window
        print(f"\\n[EMAIL NOT SENT: SMTP_HOST is not set, so it is only shown here]\\nTo: {to}\\nSubject: {subject}\\n{body}\\n", flush=True)
        return
    message = EmailMessage()
    message["From"] = os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER") or "no-reply@localhost"
    message["To"], message["Subject"] = to, subject
    message.set_content(body)
    port = int(os.environ.get("SMTP_PORT", "587"))
    security = os.environ.get("SMTP_SECURITY", "ssl" if port == 465 else "starttls").lower()    # starttls, ssl or none
    connection = smtplib.SMTP_SSL if security == "ssl" else smtplib.SMTP
    with connection(host, port, timeout=20) as smtp:
        if security == "starttls":
            smtp.starttls()
        if os.environ.get("SMTP_USER"):
            smtp.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASSWORD", ""))
        smtp.send_message(message)


def send_email(to, subject, body):
    """Send an email without ever raising. The reason for a failure is printed in the server window."""
    try:
        deliver_email(to, subject, body)
        return True
    except Exception as exc:
        print(f"Could not send email to {to}: {exc}", flush=True)
        return False


''' + text[end:]

replace('    send_email(email, "Confirm your MellowTech account",', '    return send_email(email, "Confirm your MellowTech account",')

replace('''    existing = get_db().execute("SELECT id, name, email_verified FROM users WHERE email = ?", (email,)).fetchone()
    if existing is None:
        user_id = create_company_and_admin(company, name, email, hash_password(password), False)
        audit("registered", email, user_id)
        send_verification(user_id, email, name)
    elif not existing["email_verified"]:
        send_verification(existing["id"], email, existing["name"])      # lost the first email: send a new link
''', '''    if not email_ready():
        return error("Sign-up is not available yet because this server cannot send email. Please contact MellowTech.", 503)
    existing = get_db().execute("SELECT id, name, email_verified FROM users WHERE email = ?", (email,)).fetchone()
    sent = True
    if existing is None:
        user_id = create_company_and_admin(company, name, email, hash_password(password), False)
        audit("registered", email, user_id)
        sent = send_verification(user_id, email, name)
    elif not existing["email_verified"]:
        sent = send_verification(existing["id"], email, existing["name"])      # lost the first email: send a new link
    if not sent:
        return error("We could not send the confirmation email right now. Please try again in a few minutes.", 503)
''')

replace('''    if len(sys.argv) > 1 and sys.argv[1] == "create-user":
        create_user_cli(sys.argv[2] if len(sys.argv) > 2 else "admin")
        sys.exit(0)
''', '''    if len(sys.argv) > 1 and sys.argv[1] == "create-user":
        create_user_cli(sys.argv[2] if len(sys.argv) > 2 else "admin")
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "test-email":
        target = sys.argv[2] if len(sys.argv) > 2 else input("Send the test email to: ").strip()
        if not os.environ.get("SMTP_HOST"):
            print("Email is not set up (SMTP_HOST is empty), so the message below is only printed here, not sent.")
        try:
            deliver_email(target, "MellowTech test email", "If you can read this, MellowTech can send email.")
        except Exception as exc:
            sys.exit(f"Could not send: {exc}")
        print("Done. If email is set up, check the inbox (and the spam folder) of", target)
        sys.exit(0)
''')

replace('    print(f"Serving the website files from: {ROOT}")\n', '''    print(f"Serving the website files from: {ROOT}")
    if os.environ.get("SMTP_HOST"):
        print(f"Email: sending through {os.environ['SMTP_HOST']}:{os.environ.get('SMTP_PORT', '587')}")
    elif local_url(BASE_URL):
        print("Email: NOT set up. Confirmation and reset links are printed in this window instead.")
    else:
        print("Email: NOT set up, so sign-up is switched off. Fill in backend/settings.env and restart.")
''')

shutil.copyfile(path, path.with_name("app.py.bak"))
path.write_text(text, encoding="utf-8")
py_compile.compile(str(path), doraise=True)
print("Updated. A backup of the old file is app.py.bak. Now create settings.env (see settings.env.example) and restart.")