"""MellowTech: (1) fixes the Connect a laptop panel so text and the command wrap and fit the page;
(2) adds a "Feedback" button in the top bar. Customers send ideas, problems or praise with a star rating.
Messages arrive by email and in the Internal Portal, Help messages tab (topic starts with "Feedback:").
Run from the project folder (next to index.html):   python apply_feedback.py
Needs apply_connect_help.py to have been run before. Backup: index.html.before-feedback.bak
Then hard-refresh with Ctrl+Shift+R (no server restart needed).
"""
import sys
from pathlib import Path

INDEX = Path(__file__).resolve().parent / "index.html"
if not INDEX.is_file():
    sys.exit("Could not find index.html next to this script.")
raw = INDEX.read_bytes().decode("utf-8")
crlf = "\r\n" in raw
html = raw.replace("\r\n", "\n")


def rep(text, old, new, step):
    if text.count(old) != 1:
        sys.exit(f"STEP FAILED ({step}): anchor found {text.count(old)} times. Nothing was changed.")
    return text.replace(old, new)


if "mt-feedback" in html:
    sys.exit("Already applied. Nothing was changed.")

html = rep(html, ".cl-steps .code-box { margin: 10px 0 8px; overflow-x: auto; }",
""".cl-steps > li > div { min-width: 0; flex: 1; line-height: 1.55; }
.cl-steps .code-box { margin: 10px 0 8px; white-space: pre-wrap; word-break: break-all; overflow-x: hidden; font-size: 13px; line-height: 1.5; }
#enroll-box { min-width: 0; max-width: 100%; box-sizing: border-box; overflow-wrap: anywhere; }
#enroll-box h3 { margin-top: 0; }
.cl-tabs { margin-bottom: 18px !important; }
@media (max-width: 600px) { .cl-steps > li { gap: 10px; } .cl-tab { padding: 7px 14px; } }""", "css fix")

html = rep(html, '                <button type="button" id="theme-toggle"',
'''                <button type="button" id="mt-feedback-open" class="mt-fb-open" title="Send feedback to MellowTech">
                    <svg class="icon" aria-hidden="true" viewBox="0 0 24 24" style="width:18px;height:18px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round"><path d="M21 12a8 8 0 01-11.5 7.2L4 20l1-4.6A8 8 0 1121 12z"/></svg><span>Feedback</span>
                </button>
                <button type="button" id="theme-toggle"''', "button")

html = rep(html, "</body>", '''<style id="mt-feedback">
.mt-fb-open { display: inline-flex; align-items: center; gap: 7px; height: 42px; padding: 0 14px; border-radius: 999px; border: 1px solid rgba(120,140,160,.35); background: transparent; color: inherit; font: inherit; font-weight: 600; font-size: 14px; cursor: pointer; }
.mt-fb-open:hover { background: rgba(47,125,225,.1); }
@media (max-width: 900px) { .mt-fb-open span { display: none; } .mt-fb-open { width: 42px; padding: 0; justify-content: center; } }
.mt-fb-back { position: fixed; inset: 0; z-index: 9999; background: rgba(7,17,29,.55); display: grid; place-items: center; padding: 16px; }
.mt-fb-back[hidden] { display: none; }
.mt-fb-card { box-sizing: border-box; width: 100%; max-width: 480px; max-height: 92vh; overflow: auto; padding: 24px; border-radius: 18px; background: #fff; color: #14202e; box-shadow: 0 24px 60px rgba(0,0,0,.35); }
html[data-theme="dark"] .mt-fb-card { background: #16233a; color: #e6edf6; }
.mt-fb-card h3 { margin: 0 0 4px; font-size: 20px; }
.mt-fb-card p.sub { margin: 0 0 14px; opacity: .75; font-size: 14px; }
.mt-fb-card label { display: block; margin: 14px 0 0; font-weight: 600; font-size: 14px; }
.mt-fb-card select, .mt-fb-card textarea { display: block; box-sizing: border-box; width: 100%; margin-top: 6px; padding: 10px 12px; border-radius: 10px; border: 1px solid rgba(120,140,160,.5); font: inherit; background: transparent; color: inherit; }
.mt-fb-stars { display: flex; gap: 4px; margin-top: 6px; }
.mt-fb-stars button { border: 0; background: none; font-size: 30px; line-height: 1; cursor: pointer; color: rgba(120,140,160,.55); padding: 0 2px; }
.mt-fb-stars button.on { color: #f5a623; }
.mt-fb-row { display: flex; gap: 10px; justify-content: flex-end; margin-top: 18px; }
.mt-fb-row button { padding: 10px 18px; border-radius: 10px; font: inherit; font-weight: 700; cursor: pointer; border: 1px solid rgba(120,140,160,.5); background: transparent; color: inherit; }
.mt-fb-row button.go { background: #2563eb; border-color: #2563eb; color: #fff; }
.mt-fb-row button:disabled { opacity: .6; cursor: default; }
#mt-fb-status { min-height: 1.4em; margin: 10px 0 0; font-weight: 600; font-size: 14px; }
#mt-fb-status.ok { color: #12906e; } #mt-fb-status.err { color: #d64545; }
</style>
<div class="mt-fb-back" id="mt-fb-back" hidden>
  <div class="mt-fb-card" role="dialog" aria-modal="true" aria-labelledby="mt-fb-title">
    <h3 id="mt-fb-title">Send us feedback</h3>
    <p class="sub">Tell us what works, what does not and what you would like next. We read every message.</p>
    <label>How is MellowTech so far?
      <div class="mt-fb-stars" id="mt-fb-stars" role="radiogroup" aria-label="Rating out of 5">
        <button type="button" data-n="1" aria-label="1 star">&#9733;</button><button type="button" data-n="2" aria-label="2 stars">&#9733;</button><button type="button" data-n="3" aria-label="3 stars">&#9733;</button><button type="button" data-n="4" aria-label="4 stars">&#9733;</button><button type="button" data-n="5" aria-label="5 stars">&#9733;</button>
      </div></label>
    <label>What is it about?
      <select id="mt-fb-type"><option>Idea or suggestion</option><option>Something is not working</option><option>Praise</option><option>Other</option></select></label>
    <label>Your message
      <textarea id="mt-fb-text" rows="5" maxlength="1800" placeholder="Write here..."></textarea></label>
    <p id="mt-fb-status" role="status"></p>
    <div class="mt-fb-row"><button type="button" id="mt-fb-cancel">Close</button><button type="button" class="go" id="mt-fb-send">Send feedback</button></div>
  </div>
</div>
<script>
(function () {
    var back = document.getElementById("mt-fb-back"), status = document.getElementById("mt-fb-status"),
        send = document.getElementById("mt-fb-send"), text = document.getElementById("mt-fb-text"), rating = 0;
    function stars(n) { rating = n; document.querySelectorAll("#mt-fb-stars button").forEach(function (b) { b.classList.toggle("on", Number(b.dataset.n) <= n); }); }
    function open() { back.hidden = false; status.textContent = ""; status.className = ""; send.disabled = false; text.focus(); }
    function close() { back.hidden = true; }
    document.getElementById("mt-feedback-open").addEventListener("click", open);
    document.getElementById("mt-fb-cancel").addEventListener("click", close);
    back.addEventListener("click", function (e) { if (e.target === back) close(); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !back.hidden) close(); });
    document.querySelectorAll("#mt-fb-stars button").forEach(function (b) { b.addEventListener("click", function () { stars(Number(b.dataset.n)); }); });
    send.addEventListener("click", async function () {
        var body = text.value.trim();
        if (body.length < 5) { status.textContent = "Please write a few words first."; status.className = "err"; return; }
        send.disabled = true; status.textContent = "Sending..."; status.className = "";
        try {
            var type = document.getElementById("mt-fb-type").value;
            await apiPost("/api/support/message", {
                topic: "Feedback: " + type,
                message: (rating ? "Rating: " + rating + " out of 5\\n\\n" : "") + body
            });
            text.value = ""; stars(0);
            status.textContent = "Thank you! Your feedback has reached the MellowTech team."; status.className = "ok";
            setTimeout(close, 2200);
        } catch (err) {
            status.textContent = err.message || "Could not send. Please try again."; status.className = "err"; send.disabled = false;
        }
    });
})();
</script>
</body>''', "widget")

bak = INDEX.with_name("index.html.before-feedback.bak")
if not bak.exists():
    bak.write_bytes(INDEX.read_bytes())
INDEX.write_bytes((html.replace("\n", "\r\n") if crlf else html).encode("utf-8"))
print("Done. Hard-refresh with Ctrl+Shift+R.")