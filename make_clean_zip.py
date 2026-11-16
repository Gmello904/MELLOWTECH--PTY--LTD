import zipfile, os
src = r"MELLOWTECH-AWS"
out = r"C:\Users\Given\Downloads\MELLOWTECH-AWS-update-4.zip"
if os.path.exists(out):
    os.remove(out)
skip_ext = (".db", ".pyc", ".bak", ".zip")
n = 0
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for folder, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            if f.endswith(skip_ext) or f == ".secret_key":
                continue
            full = os.path.join(folder, f)
            z.write(full, os.path.relpath(full, src).replace("\\", "/"))
            n += 1
print("zip built with", n, "files")
