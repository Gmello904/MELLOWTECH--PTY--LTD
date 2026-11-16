"""MellowTech: make Ask Mellow use Groq (GROQ_API_KEY in settings.env). Run from the project folder:  python apply_groq.py
Patches backend/app.py. Backup: app.py.before-groq.bak. Gemini/Claude keep working if no Groq key is set."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
path = next((HERE / n for n in ("backend/app.py", "app.py") if (HERE / n).is_file()), None)
if not path:
    sys.exit("backend/app.py not found next to this script.")
raw = path.read_bytes().decode("utf-8-sig")
crlf = "\r\n" in raw
t = raw.replace("\r\n", "\n")
if "def call_groq" in t:
    sys.exit("Already applied. Nothing was changed.")


def rep(text, old, new, step):
    if text.count(old) != 1:
        sys.exit(f"STEP FAILED ({step}): anchor found {text.count(old)} times. Nothing was changed.")
    return text.replace(old, new)


t = rep(t, "def ai_configured():\n    return bool(os.environ.get(\"GEMINI_API_KEY\", \"\").strip() or os.environ.get(\"ANTHROPIC_API_KEY\", \"\").strip())\n",
'''def call_groq(system, messages):
    """One request to the Groq API (OpenAI-compatible) using only the standard library. Raises RuntimeError with a safe message."""
    key = os.environ.get("GROQ_API_KEY", "").strip()
    model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
    chat = [{"role": "system", "content": system}] + [
        {"role": "user" if m["role"] == "user" else "assistant", "content": m["content"]} for m in messages]
    body = json.dumps({"model": model, "messages": chat, "max_tokens": 900, "temperature": 0.3}).encode()
    request_ = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions", data=body, method="POST", headers={
        "content-type": "application/json", "authorization": "Bearer " + key, "user-agent": "MellowTech/1.0"})
    try:
        with urllib.request.urlopen(request_, timeout=45) as response:
            data = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        print("Ask Mellow: the Groq API answered", exc.code, exc.read()[:300], flush=True)
        raise RuntimeError("busy" if exc.code in (429, 503) else "failed")
    except Exception as exc:
        print("Ask Mellow: could not reach the Groq API:", exc, flush=True)
        raise RuntimeError("failed")
    try:
        text = (data["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError):
        text = ""
    if not text:
        print("Ask Mellow: Groq returned no text:", str(data)[:300], flush=True)
        raise RuntimeError("failed")
    return text


def ai_configured():
    return bool(os.environ.get("GROQ_API_KEY", "").strip() or os.environ.get("GEMINI_API_KEY", "").strip()
                or os.environ.get("ANTHROPIC_API_KEY", "").strip())
''', "ai_configured")

t = rep(t, '''    """Gemini when GEMINI_API_KEY is set, otherwise Claude when ANTHROPIC_API_KEY is set."""
    if os.environ.get("GEMINI_API_KEY", "").strip():''',
'''    """Groq when GROQ_API_KEY is set, else Gemini when GEMINI_API_KEY is set, otherwise Claude when ANTHROPIC_API_KEY is set."""
    if os.environ.get("GROQ_API_KEY", "").strip():
        return call_groq(system, messages)
    if os.environ.get("GEMINI_API_KEY", "").strip():''', "call_ai")

t = rep(t, '("ready (Gemini)" if os.environ.get("GEMINI_API_KEY", "").strip()',
        '("ready (Groq)" if os.environ.get("GROQ_API_KEY", "").strip() else "ready (Gemini)" if os.environ.get("GEMINI_API_KEY", "").strip()', "startup line")
compile(t, "app.py", "exec")
b = path.with_name("app.py.before-groq.bak")
if not b.exists():
    b.write_bytes(path.read_bytes())
path.write_bytes((t.replace("\n", "\r\n") if crlf else t).encode("utf-8"))
print("patched", path.relative_to(HERE), "\n\nDone. In backend/settings.env use:  GROQ_API_KEY=your_key   (optional: GROQ_MODEL=llama-3.3-70b-versatile)\nThen restart the server.")