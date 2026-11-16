import sys
path = sys.argv[1]
text = open(path, encoding="utf-8", newline="").read()
if "mt-compact" in text:
    sys.exit("Already patched.")

a = text.find('"<h2>Select your cookie')
b = text.find('"<ul class=')
if a < 0 or b < 0 or b < a or text.count('"<ul class=') != 1:
    sys.exit("STOPPED: consent.js does not look as expected. Nothing was changed.")
NEWTEXT = r'''"<h2>Cookies</h2>" +
            "<p>We use one essential cookie to keep you signed in. With your OK we also remember light or dark mode. No ads, no tracking. " +
            "<a href=\"cookies.html\" target=\"_blank\" rel=\"noopener\">Learn more</a></p>" +
            '''
text = text[:a] + NEWTEXT + text[b:]

ANCHOR = '".mt-legal-links{margin:14px 0;'
if text.count(ANCHOR) != 1:
    sys.exit("STOPPED: style anchor not found. Nothing was changed.")
CSS = r'''"/*mt-compact*/#mt-consent{left:16px;right:auto;bottom:16px;width:min(360px,calc(100vw - 32px));padding:16px 18px;border-radius:14px;border:1px solid #26405c;max-height:70vh;font-size:13.5px;line-height:1.45}" +
            "#mt-consent .mt-wrap{display:block}" +
            "#mt-consent h2{font-size:16px;margin:0 0 6px}" +
            "#mt-consent .mt-actions{width:100%;margin-top:12px;grid-template-columns:1fr 1fr;gap:8px}" +
            "#mt-consent .mt-actions .mt-yes.mt-main,#mt-consent .mt-actions .mt-save{grid-column:1 / -1}" +
            "#mt-consent button{padding:9px 10px;font-size:13px;border-radius:8px}" +
            "#mt-consent .mt-opts li{padding:10px 0}" +
            '''
text = text.replace(ANCHOR, CSS + ANCHOR)
open(path, "w", encoding="utf-8", newline="").write(text)
print("Patched", path)
