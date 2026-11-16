import sys
path = sys.argv[1]
text = open(path, encoding="utf-8", newline="").read()
if "mt-signout" in text:
    sys.exit("Already patched.")
if text.count("</head>") != 1:
    sys.exit("STOPPED: unexpected page. Nothing was changed.")

CSS = """<style id="mt-signout">
.plan-svc{margin-top:14px;padding-top:12px;border-top:1px dashed rgba(120,140,160,.35);text-align:left}
.plan-svc ul{list-style:none;margin:0;padding:0;display:grid;gap:6px;font-size:14px}
.plan-svc li{display:flex;gap:8px;align-items:flex-start}
.plan-svc li svg,.plan-features li svg{width:18px!important;height:18px!important;flex:none;margin-top:1px;fill:none!important;stroke:#12906e;stroke-width:2.4;stroke-linecap:round;stroke-linejoin:round}
.logout-button{display:inline-flex!important;align-items:center;justify-content:center;gap:10px;padding:9px 22px!important;border-radius:999px!important;
 background:#fff!important;color:#111!important;border:4px double #111!important;box-shadow:none!important;
 font-family:inherit;font-size:14px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;cursor:pointer;transition:transform .15s,background .15s,color .15s}
.logout-button .lo-ico{display:none!important}
.logout-button::after{content:"";width:18px;height:20px;flex:none;background:currentColor;
 -webkit-mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M6 11h12a1 1 0 011 1v8a1 1 0 01-1 1H6a1 1 0 01-1-1v-8a1 1 0 011-1z'/%3E%3Cpath d='M8 11V7a4 4 0 017.5-2' fill='none' stroke='black' stroke-width='2.4' stroke-linecap='round'/%3E%3C/svg%3E") center/contain no-repeat;
 mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M6 11h12a1 1 0 011 1v8a1 1 0 01-1 1H6a1 1 0 01-1-1v-8a1 1 0 011-1z'/%3E%3Cpath d='M8 11V7a4 4 0 017.5-2' fill='none' stroke='black' stroke-width='2.4' stroke-linecap='round'/%3E%3C/svg%3E") center/contain no-repeat}
.logout-button:hover{background:#111!important;color:#fff!important;transform:translateY(-1px)}
html[data-theme="dark"] .logout-button{background:transparent!important;color:#fff!important;border-color:#fff!important}
html[data-theme="dark"] .logout-button:hover{background:#fff!important;color:#111!important}
@media (max-width:760px){.logout-button span:last-child{display:inline!important}.logout-button{padding:8px 14px!important;font-size:12px}}
</style>
</head>"""

text = text.replace("</head>", CSS)
open(path, "w", encoding="utf-8", newline="").write(text)
print("Patched", path)
