import sys
path = sys.argv[1]
text = open(path, encoding="utf-8", newline="").read()
if "mt-login-look" in text:
    sys.exit("Already patched.")
if text.count("</head>") != 1 or text.count("</body>") != 1 or 'id="logo-arrows"' not in text:
    sys.exit("STOPPED: unexpected page. Nothing was changed.")

CSS = """<style id="mt-login-look">
/* logo: half size */
.mark{width:82px;height:64px;margin:0 0 12px -7px}
.brand-top{position:relative}
.brand-top::before{content:"";position:absolute;left:-40px;top:-40px;width:210px;height:210px;border-radius:50%;
 background:radial-gradient(circle,rgba(56,214,255,.30),transparent 65%);filter:blur(6px);pointer-events:none;z-index:-1}
/* feature card */
.features{padding:18px 20px 16px;border-radius:16px;background:rgba(255,255,255,.045);border:1px solid rgba(143,166,191,.18);
 -webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px);box-shadow:0 10px 30px rgba(0,0,0,.25)}
/* form side */
.form-panel{position:relative}
.form-panel::before{content:"";position:absolute;left:0;right:0;top:0;height:5px;
 background:linear-gradient(90deg,#3ddbb0,#4aa8ff,#3ddbb0);background-size:200% 100%;animation:mtflow 6s linear infinite}
@keyframes mtflow{to{background-position:200% 0}}
h1{background:linear-gradient(90deg,#0d1b2a 0%,#1d6fd6 70%,#12906e 100%);-webkit-background-clip:text;background-clip:text;
 -webkit-text-fill-color:transparent;color:transparent;font-weight:800}
input[type="email"],input[type="password"],input[type="text"]{border-radius:12px;background:#f7f9fc}
input:focus{border-color:#12906e;box-shadow:0 0 0 4px rgba(61,219,176,.28)}
/* sign in button: white pill, double outline, padlock */
.login-button{display:flex;align-items:center;justify-content:center;gap:12px;padding:13px 22px;border-radius:999px;
 background:#fff;color:#0d1b2a;border:4px double #0d1b2a;box-shadow:0 8px 20px rgba(13,27,42,.12);
 font-weight:800;font-size:15px;letter-spacing:.16em;text-transform:uppercase}
.login-button::after{display:none}
.login-button::before{content:"";order:3;width:20px;height:22px;flex:none;background:currentColor;
 -webkit-mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M6 11h12a1 1 0 011 1v8a1 1 0 01-1 1H6a1 1 0 01-1-1v-8a1 1 0 011-1z'/%3E%3Cpath d='M8 11V7a4 4 0 017.5-2' fill='none' stroke='black' stroke-width='2.4' stroke-linecap='round'/%3E%3C/svg%3E") center/contain no-repeat;
 mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M6 11h12a1 1 0 011 1v8a1 1 0 01-1 1H6a1 1 0 01-1-1v-8a1 1 0 011-1z'/%3E%3Cpath d='M8 11V7a4 4 0 017.5-2' fill='none' stroke='black' stroke-width='2.4' stroke-linecap='round'/%3E%3C/svg%3E") center/contain no-repeat}
.login-button:hover{background:#0d1b2a;color:#fff;transform:translateY(-1px);box-shadow:0 12px 26px rgba(13,27,42,.34)}
.login-button .spinner{margin-right:0;border-color:rgba(13,27,42,.25);border-top-color:#0d1b2a}
.login-button:hover .spinner{border-color:rgba(255,255,255,.35);border-top-color:#fff}
.login-button.busy::before{display:none}
/* Google and GitHub */
.or{margin:22px 0 16px;font-weight:600;letter-spacing:.04em}
.social-row{gap:12px}
.social-button{padding:13px 14px;border-radius:999px;border:1.5px solid #e1e7ee;background:linear-gradient(#fff,#f6f8fb);
 box-shadow:0 2px 6px rgba(13,27,42,.07);font-weight:700;font-size:14.5px;gap:11px}
.social-button svg{width:22px;height:22px}
.social-button:hover{transform:translateY(-2px)}
#google-button:hover{background:#fff;border-color:#4285F4;box-shadow:0 10px 24px rgba(66,133,244,.28)}
#github-button:hover{background:#0d1b2a;border-color:#0d1b2a;color:#fff;box-shadow:0 10px 24px rgba(13,27,42,.35)}
#github-button:hover svg path{fill:#fff}
.register a{color:#12906e;text-decoration:none;border-bottom:2px solid rgba(18,144,110,.35)}
.register a:hover{border-bottom-color:#12906e}
@media (max-width:800px){.mark{width:68px;height:52px;margin:0 0 8px -6px}.features{padding:14px 16px}}
@media (prefers-reduced-motion:reduce){.form-panel::before{animation:none}}
</style>
</head>"""

JS = """<script>
/* the logo arrows spin only while the page loads and while signing in */
(function () {
    var svg = document.getElementById("logo-arrows");
    if (!svg || !svg.pauseAnimations) { return; }
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) { return; }
    function spin(on) { try { if (on) { svg.unpauseAnimations(); } else { svg.pauseAnimations(); } } catch (e) {} }
    window.__mtBusy = false;
    spin(true);
    function stopLoading() { setTimeout(function () { if (!window.__mtBusy) { spin(false); } }, 1400); }
    if (document.readyState === "complete") { stopLoading(); } else { window.addEventListener("load", stopLoading); }
    var original = window.setBusy;
    if (typeof original === "function") {
        window.setBusy = function (busy) {
            window.__mtBusy = !!busy;
            original.apply(this, arguments);
            spin(!!busy);
        };
    }
})();
</script>
</body>"""

text = text.replace("</head>", CSS).replace("</body>", JS)
open(path, "w", encoding="utf-8", newline="").write(text)
print("Patched", path)
