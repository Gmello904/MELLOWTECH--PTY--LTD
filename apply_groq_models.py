"""MellowTech: make Ask Mellow survive Groq model changes. If the chosen Groq model is unavailable it tries the next one.
Run from the project folder AFTER apply_groq.py:  python apply_groq_models.py   Patches backend/app.py (backup: app.py.before-groqmodels.bak)"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
path = next((HERE / n for n in ("backend/app.py", "app.py") if (HERE / n).is_file()), None)
if not path:
    sys.exit("backend/app.py not found next to this script.")
raw = path.read_bytes().decode("utf-8-sig")
crlf = "\r\n" in raw
t = raw.replace("\r\n", "\n")
a, b = t.find("def call_groq(system, messages):"), t.find("def ai_configured():")
if a < 0 or b < a:
    sys.exit("call_groq not found. Run apply_groq.py first. Nothing was changed.")
if "GROQ_FALLBACK_MODELS" in t:
    sys.exit("Already applied. Nothing was changed.")

new = '''GROQ_FALLBACK_MODELS = ["openai/gpt-oss-120b", "llama-3.3-70b-versatile", "llama-3.1-8b-instant", "openai/gpt-oss-20b"]


def call_groq(system, messages):
    """One request to the Groq API (OpenAI-compatible) using only the standard library.
    Tries GROQ_MODEL first, then other current Groq models if one is unavailable. Raises RuntimeError with a safe message."""
    key = os.environ.get("GROQ_API_KEY", "").strip()
    chosen = os.environ.get("GROQ_MODEL", "").strip()
    models = ([chosen] if chosen else []) + [m for m in GROQ_FALLBACK_MODELS if m != chosen]
    chat = [{"role": "system", "content": system}] + [
        {"role": "user" if m["role"] == "user" else "assistant", "content": m["content"]} for m in messages]
    last = "failed"
    for model in models:
        payload = {"model": model, "messages": chat, "temperature": 0.3, "max_tokens": 900}
        if model.startswith("openai/gpt-oss"):          # reasoning models: keep thinking short so the answer fits
            payload.update({"reasoning_effort": "low", "max_tokens": 2000})
        request_ = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions", data=json.dumps(payload).encode(),
                                          method="POST", headers={"content-type": "application/json",
                                                                  "authorization": "Bearer " + key, "user-agent": "MellowTech/1.0"})
        try:
            with urllib.request.urlopen(request_, timeout=45) as response:
                data = json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            print("Ask Mellow: the Groq API answered", exc.code, "for model", model, exc.read()[:300], flush=True)
            if exc.code in (404, 400, 403):             # this model is not available to you: try the next one
                last = "failed"
                continue
            raise RuntimeError("busy" if exc.code in (429, 503) else "failed")
        except Exception as exc:
            print("Ask Mellow: could not reach the Groq API:", exc, flush=True)
            raise RuntimeError("failed")
        try:
            text = (data["choices"][0]["message"]["content"] or "").strip()
        except (KeyError, IndexError, TypeError):
            text = ""
        if text:
            return text
        print("Ask Mellow: Groq returned no text for model", model, str(data)[:300], flush=True)
    raise RuntimeError(last)


'''
t = t[:a] + new + t[b:]
compile(t, "app.py", "exec")
bak = path.with_name("app.py.before-groqmodels.bak")
if not bak.exists():
    bak.write_bytes(path.read_bytes())
path.write_bytes((t.replace("\n", "\r\n") if crlf else t).encode("utf-8"))
print("patched", path.relative_to(HERE), "\nDone. Restart the server (python app.py) and ask Ask Mellow again.")