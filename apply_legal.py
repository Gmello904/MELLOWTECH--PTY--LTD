"""Part 2: Privacy Policy, Terms and Conditions, Cookie Policy and a cookie banner.

Creates privacy.html, terms.html, cookies.html and consent.js, lets the server show them, and adds the
cookie banner (plus links to the policies) to index.html, login.html, register.html and reset.html.

Put this file in the MELLOWTECH folder (next to index.html) and run:
    python apply_legal.py
Backups are saved next to each changed file as *.bak.

IMPORTANT: the policies are TEMPLATES. Search each page for the yellow [BRACKETS] and fill them in, remove the
red DRAFT box, and have a South African lawyer review them before you rely on them. They are not legal advice.
"""
import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>@@TITLE@@ | MellowTech</title>
<style>
body{font-family:system-ui,-apple-system,"Segoe UI",Arial,sans-serif;margin:0;background:#eef2f6;color:#17202a;line-height:1.6}
header{background:#0d1b2a;color:#fff;padding:18px 24px}
header a{color:#3ddbb0;text-decoration:none;font-weight:700}
main{max-width:820px;margin:24px auto;padding:0 20px 60px}
article{background:#fff;border-radius:14px;padding:28px 32px;box-shadow:0 4px 18px rgba(15,34,54,.06)}
h1{font-size:28px;margin:0 0 4px}
h2{font-size:19px;margin:28px 0 8px}
p,li{font-size:15px}
li{margin:4px 0}
mark{background:#fff3a3;padding:0 3px;border-radius:3px}
.draft-note{background:#fde8e8;color:#8b1f1f;border:1px solid #f0b9be;border-radius:10px;padding:12px 16px;margin:0 0 18px;font-size:14px;font-weight:600}
.small{color:#68737d;font-size:13px}
table{border-collapse:collapse;width:100%;margin:10px 0;font-size:14px}
th,td{border:1px solid #d8e0e8;padding:8px 10px;text-align:left;vertical-align:top}
th{background:#f4f7fb}
nav a{margin-right:16px}
</style>
</head>
<body data-legal-page>
<header><a href="/">MELLOWTECH</a></header>
<main>
<article>
<div class="draft-note">DRAFT TEMPLATE: fill in every yellow [BRACKET], have a South African lawyer review this page, then delete this red box.</div>
@@BODY@@
<p class="small"><a href="privacy.html">Privacy Policy</a> &middot; <a href="terms.html">Terms and Conditions</a> &middot; <a href="cookies.html">Cookie Policy</a> &middot; <a href="#" data-cookie-settings>Cookie settings</a></p>
</article>
</main>
<script src="consent.js"></script>
</body>
</html>
"""

PRIVACY = """<h1>Privacy Policy</h1>
<p class="small">Last updated: 31 October 2026</p>
<p>This policy explains how MellowTech (Pty) Ltd ("MellowTech", "we", "us") collects, uses and protects personal information when you use the MellowTech Security Platform. We follow the Protection of Personal Information Act, 2013 (POPIA).</p>

<h2>1. Who is responsible</h2>
<p>MellowTech (Pty) Ltd, registration number <mark>[REGISTRATION NUMBER]</mark>, <mark>[PHYSICAL ADDRESS]</mark>.<br>
Information Officer: <mark>[NAME]</mark>, <mark>[PRIVACY EMAIL ADDRESS]</mark>.</p>

<h2>2. What we collect</h2>
<ul>
<li><b>Account details:</b> your name, email address, company name and role. Your password is stored only as a scrambled hash, never as readable text.</li>
<li><b>Sign-in with Google or GitHub:</b> your name and verified email address, if you choose that way to sign in.</li>
<li><b>Devices you connect:</b> device name, operating system, IP address, processor, memory and disk use, security status (such as antivirus, firewall, disk encryption and updates), security alerts, and the actions you send to the device.</li>
<li><b>Security information you give us:</b> events and alerts, blocked addresses, domains you add for scanning and the results, and text or files you paste into our tools (for example logs or cloud settings).</li>
<li><b>Documents you scan:</b> the file name, type, a fingerprint (hash) of the file and the scan result. We do not keep the document itself.</li>
<li><b>Payments:</b> PayPal and Payfast handle your card details. We keep only your plan, the amount, the status and the order reference.</li>
<li><b>Technical and activity records:</b> your IP address and a log of important actions on your account (for example sign-ins and changes), kept for security.</li>
</ul>

<h2>3. Why we use it</h2>
<ul>
<li>To provide the service you asked for, including security monitoring, alerts and the automatic actions you switch on.</li>
<li>To create and manage your account, approve new organisations and take payment.</li>
<li>To keep the platform secure, prevent abuse and investigate problems.</li>
<li>To send service emails, such as confirmation and password reset messages.</li>
<li>To meet legal duties.</li>
</ul>
<p>We rely on your consent, on our contract with you, on our legitimate interest in running a secure service, and on legal obligations.</p>

<h2>4. Who we share it with</h2>
<p>We do not sell personal information. We share it only with service providers who help us run the platform: <mark>[HOSTING PROVIDER, for example Amazon Web Services]</mark>, our email provider <mark>[EMAIL PROVIDER]</mark>, PayPal and Payfast for payments, and Google or GitHub if you use them to sign in. We may also disclose information when the law requires it.</p>

<h2>5. Sending information outside South Africa</h2>
<p>Some providers process information outside South Africa. Where this happens we make sure the provider is bound by law, a binding agreement or similar protections as POPIA requires. Our data is hosted in <mark>[HOSTING COUNTRY OR REGION]</mark>.</p>

<h2>6. How long we keep it</h2>
<p>We keep account information while your account is active and for <mark>[PERIOD, for example 12 months]</mark> after it closes. Security records and logs are kept for <mark>[PERIOD]</mark>. Payment records are kept for <mark>[PERIOD, usually 5 years for tax purposes]</mark>.</p>

<h2>7. How we protect it</h2>
<p>We store passwords as hashes, separate each organisation's data, record important actions in an audit log, limit repeated sign-in attempts and protect forms against forged requests. <mark>[CONFIRM: our live service is served over HTTPS.]</mark> No system is perfectly secure. If personal information is compromised, we will tell the Information Regulator and the people affected as the law requires.</p>

<h2>8. Your rights</h2>
<p>You may ask to see the personal information we hold about you, to correct it, to delete it, to object to how we use it, and to withdraw your consent. Email <mark>[PRIVACY EMAIL ADDRESS]</mark>. If you are unhappy with how we handle your information, you may complain to the Information Regulator of South Africa.</p>

<h2>9. Cookies</h2>
<p>See our <a href="cookies.html">Cookie Policy</a>.</p>

<h2>10. Who this service is for</h2>
<p>The platform is for organisations and adults. It is not meant for people under 18.</p>

<h2>11. Changes</h2>
<p>We may update this policy. The date at the top shows when it last changed. If a change is important we will tell you.</p>
"""

TERMS = """<h1>Terms and Conditions</h1>
<p class="small">Last updated: 31 October 2026</p>
<p>These terms are an agreement between you (or the organisation you represent) and MellowTech (Pty) Ltd ("MellowTech"). By creating an account or using the MellowTech Security Platform you accept them.</p>

<h2>1. The service</h2>
<p>MellowTech provides cybersecurity monitoring and tools, including device monitoring, alerts, blocking, vulnerability scanning, a document scanner, security checks, policy templates and an Autopilot that can act automatically on your connected devices.</p>

<h2>2. Accounts</h2>
<ul>
<li>You must give correct information and keep your password secret. You are responsible for what happens under your account.</li>
<li>New organisations may need our approval before they can sign in. We may refuse or end an account.</li>
<li>The person who registers an organisation confirms they may act for it.</li>
</ul>

<h2>3. Acceptable use</h2>
<ul>
<li>Only scan websites and systems you own or have written permission to test. You must prove ownership of a domain before we scan it.</li>
<li>Only connect devices you own or manage.</li>
<li>Do not use the platform to attack, harass or defraud anyone, break the law, or try to harm or overload the platform.</li>
<li>Do not use the Document Scanner to harass or wrongly accuse people. Its result is only a warning sign.</li>
</ul>

<h2>4. Automatic actions (Autopilot)</h2>
<p>When you switch on Autopilot or confirm an action, you authorise MellowTech to act on your connected devices, for example to block an address, update protection, run a scan, isolate a laptop or block USB storage. These actions can interrupt work. You are responsible for choosing which actions to allow and for the devices you connect. Every action is recorded in your Autopilot log.</p>

<h2>5. Plans and payment</h2>
<ul>
<li>Prices are shown on the Billing &amp; Plans page. Paid plans run for the number of days shown and do not renew automatically unless we tell you otherwise.</li>
<li>A setup fee, where shown, is charged once on your first purchase.</li>
<li>Some features are available only on certain plans and stay locked until you pay for a plan that includes them.</li>
<li>Payments are processed by PayPal or Payfast. <mark>[REFUND AND CANCELLATION RULES]</mark></li>
<li>Prices may change. Changes do not affect a period you have already paid for.</li>
</ul>

<h2>6. Guidance, not guarantees</h2>
<p>The platform gives security information, warnings and recommendations. It cannot find every threat or weakness, and a clean result is not proof that something is safe or genuine. Security checks, playbooks and policy documents are practical guidance and templates, not legal, financial or audit advice. You should get professional advice before relying on them.</p>

<h2>7. Your information</h2>
<p>You keep ownership of your information. You allow us to process it to provide the service, as explained in our <a href="privacy.html">Privacy Policy</a>.</p>

<h2>8. Availability</h2>
<p>We work to keep the platform available, but we cannot promise it will always be uninterrupted or error free. We may change or improve it, and may pause it for maintenance.</p>

<h2>9. Limits on our responsibility</h2>
<p>To the extent the law allows, MellowTech is not responsible for indirect or consequential losses, lost profits or lost data, or for losses caused by your devices, your settings, third-party services or events outside our control. Where the law does not allow a limit, that limit does not apply. <mark>[LAWYER TO CONFIRM LIABILITY WORDING AND CAP, including the Consumer Protection Act where it applies]</mark></p>

<h2>10. Ending your account</h2>
<p>You may stop using the platform at any time. We may suspend or end an account that breaks these terms or puts others at risk. We will explain why when we reasonably can.</p>

<h2>11. Changes to these terms</h2>
<p>We may update these terms. If you keep using the platform after a change is announced, you accept it.</p>

<h2>12. Governing law and contact</h2>
<p>These terms are governed by the laws of South Africa. Questions: <mark>[CONTACT EMAIL ADDRESS]</mark>.</p>
"""

COOKIES = """<h1>Cookie Policy</h1>
<p class="small">Last updated: 31 October 2026</p>
<p>Cookies are small files a website stores in your browser. This page explains what the MellowTech Security Platform uses.</p>

<h2>What we use</h2>
<table>
<tr><th>Name</th><th>Purpose</th><th>Type</th><th>Lasts</th></tr>
<tr><td>session</td><td>Keeps you signed in and protects your account against forged requests.</td><td>Essential, set by us</td><td>Up to 8 hours</td></tr>
<tr><td>mt-consent (browser storage)</td><td>Remembers your cookie choice so we do not ask again on every visit.</td><td>Essential, set by us</td><td>Until you clear your browser data</td></tr>
</table>

<h2>Third parties</h2>
<ul>
<li><b>PayPal and Payfast:</b> when you open Billing &amp; Plans or pay, these companies may set their own cookies. See their policies.</li>
<li><b>Google and GitHub:</b> if you choose to sign in with them, they may set cookies on their own pages.</li>
</ul>

<h2>What we do not use</h2>
<p>We do not use advertising cookies and we do not track you across other websites. <mark>[UPDATE THIS PAGE IF YOU ADD ANALYTICS]</mark></p>

<h2>Your choices</h2>
<p>You can change your choice at any time with the "Cookie settings" link at the bottom of any page. You can also block or delete cookies in your browser, but the platform will not work without the essential session cookie.</p>

<p>More about how we handle your information is in our <a href="privacy.html">Privacy Policy</a>.</p>
"""

CONSENT_JS = r"""(function () {
    "use strict";
    var KEY = "mt-consent";

    function read() {
        try { return JSON.parse(localStorage.getItem(KEY) || "null"); } catch (e) { return null; }
    }

    function save(choice) {
        try { localStorage.setItem(KEY, JSON.stringify({ v: 1, choice: choice, at: new Date().toISOString() })); } catch (e) { /* storage blocked */ }
        window.mtConsent = choice;
    }

    function addStyle() {
        if (document.getElementById("mt-consent-style")) { return; }
        var style = document.createElement("style");
        style.id = "mt-consent-style";
        style.textContent =
            "#mt-consent{position:fixed;left:16px;right:16px;bottom:16px;z-index:2147483000;max-width:720px;margin:0 auto;padding:16px 18px;" +
            "background:#0d1b2a;color:#eaf2fb;border:1px solid #26405c;border-radius:14px;box-shadow:0 12px 36px rgba(0,0,0,.35);" +
            "font:14px/1.5 system-ui,-apple-system,Segoe UI,Arial,sans-serif}" +
            "#mt-consent p{margin:0 0 12px}#mt-consent a{color:#3ddbb0}" +
            "#mt-consent .mt-row{display:flex;flex-wrap:wrap;gap:10px}" +
            "#mt-consent button{padding:9px 16px;border-radius:10px;border:1px solid #3ddbb0;background:transparent;color:#eaf2fb;font:inherit;font-weight:700;cursor:pointer}" +
            "#mt-consent button.mt-yes{background:#3ddbb0;color:#07111d}" +
            ".mt-legal-links{margin:14px 0;text-align:center;font-size:13px;color:#68737d}.mt-legal-links a{color:inherit;margin:0 6px}";
        document.head.appendChild(style);
    }

    function close() {
        var box = document.getElementById("mt-consent");
        if (box) { box.remove(); }
    }

    function show() {
        if (document.getElementById("mt-consent")) { return; }
        addStyle();
        var box = document.createElement("div");
        box.id = "mt-consent";
        box.setAttribute("role", "dialog");
        box.setAttribute("aria-label", "Cookie notice");
        box.innerHTML =
            "<p>We use one essential cookie to keep you signed in securely. When you pay or sign in with Google or GitHub, those companies may set their own cookies. " +
            "We do not use advertising or tracking cookies. See our <a href=\"cookies.html\" target=\"_blank\" rel=\"noopener\">Cookie Policy</a> and " +
            "<a href=\"privacy.html\" target=\"_blank\" rel=\"noopener\">Privacy Policy</a>.</p>" +
            "<div class=\"mt-row\"><button type=\"button\" class=\"mt-yes\" data-choice=\"all\">Accept</button>" +
            "<button type=\"button\" data-choice=\"essential\">Essential only</button></div>";
        box.addEventListener("click", function (event) {
            var button = event.target.closest("[data-choice]");
            if (!button) { return; }
            save(button.dataset.choice);
            close();
        });
        document.body.appendChild(box);
    }

    function addLinks() {
        if (document.body.hasAttribute("data-legal-page") || document.querySelector(".mt-legal-links")) { return; }
        var html = '<a href="privacy.html" target="_blank" rel="noopener">Privacy Policy</a> &middot; ' +
            '<a href="terms.html" target="_blank" rel="noopener">Terms and Conditions</a> &middot; ' +
            '<a href="cookies.html" target="_blank" rel="noopener">Cookie Policy</a> &middot; <a href="#" data-cookie-settings>Cookie settings</a>';
        var holder = document.createElement("p");
        holder.className = "mt-legal-links";
        holder.innerHTML = html;
        var footer = document.querySelector("footer");
        (footer || document.body).appendChild(holder);
    }

    document.addEventListener("click", function (event) {
        if (event.target.closest("[data-cookie-settings]")) {
            event.preventDefault();
            show();
        }
    });

    function start() {
        var saved = read();
        if (saved && saved.choice) { window.mtConsent = saved.choice; } else { show(); }
        addLinks();
    }

    if (document.readyState === "loading") { document.addEventListener("DOMContentLoaded", start); } else { start(); }
})();
"""

PAGES = {"privacy.html": ("Privacy Policy", PRIVACY), "terms.html": ("Terms and Conditions", TERMS),
         "cookies.html": ("Cookie Policy", COOKIES)}

OLD_PUBLIC = '"register.html", "style.css", "app.js"}'
NEW_PUBLIC = '"register.html", "style.css", "app.js",\n                "privacy.html", "terms.html", "cookies.html", "consent.js"}'
TAG = '<script src="consent.js"></script>\n'


def backup(path):
    shutil.copy2(path, str(path) + ".bak")


def patch_app(path):
    text = path.read_text(encoding="utf-8")
    if '"consent.js"' in text:
        return "already updated"
    if text.count(OLD_PUBLIC) != 1:
        return "NOT changed: could not find the PUBLIC_PAGES line"
    backup(path)
    path.write_text(text.replace(OLD_PUBLIC, NEW_PUBLIC, 1), encoding="utf-8")
    return "updated"


def add_tag(path):
    text = path.read_text(encoding="utf-8")
    if "consent.js" in text:
        return "already has the cookie banner"
    if text.count("</body>") != 1:
        return f"NOT changed: expected one </body>, found {text.count('</body>')}"
    backup(path)
    path.write_text(text.replace("</body>", TAG + "</body>", 1), encoding="utf-8")
    return "banner added"


def main():
    for folder in (HERE, HERE / "aws-deploy"):
        if not (folder / "index.html").is_file():
            continue
        label = "." if folder == HERE else folder.name
        for name, (title, body) in PAGES.items():
            (folder / name).write_text(PAGE.replace("@@TITLE@@", title).replace("@@BODY@@", body), encoding="utf-8")
            print(f"{label}\\{name}: written")
        (folder / "consent.js").write_text(CONSENT_JS, encoding="utf-8")
        print(f"{label}\\consent.js: written")
        for page in ("index.html", "login.html", "register.html", "reset.html"):
            if (folder / page).is_file():
                print(f"{label}\\{page}: {add_tag(folder / page)}")
    for folder in (HERE / "backend", HERE / "aws-deploy"):
        if (folder / "app.py").is_file():
            print(f"{foldr.name}\\app.py: {patch_app(folder / 'app.py')}")
    print("\nDone. Restart python app.py, refresh with Ctrl+Shift+R, then open http://127.0.0.1:5000/privacy.html")
    print("Now open privacy.html, terms.html and cookies.html in VS Code, fill in every [BRACKET] and delete the DRAFT box.")


if __name__ == "__main__":
    main()