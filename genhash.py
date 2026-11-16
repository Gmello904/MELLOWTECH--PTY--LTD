import hashlib, secrets, string, getpass
pw = getpass.getpass("New password (12+ chars, typing is invisible): ")
pw2 = getpass.getpass("Repeat it: ")
print("lengths:", len(pw), len(pw2))
if len(pw) < 12:
    raise SystemExit("Too short: use at least 12 characters")
if pw != pw2:
    raise SystemExit("The two entries do not match")
salt = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))
h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 600000).hex()
open("seed/newpw.txt", "w", newline="\n").write(f"pbkdf2:sha256:600000${salt}${h}")
print("hash written")
