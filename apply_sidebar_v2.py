#!/usr/bin/env python3
"""
apply_sidebar_v2.py  -  MellowSecure sidebar v2

Run from the MELLOWTECH folder:   python apply_sidebar_v2.py

What it does to index.html (a backup is made first):
  1. Rebuilds the sidebar <nav> into 6 collapsible groups + a search box.
     Your existing buttons are KEPT as they are (same data-page, icons,
     admin-only flags, badges) and only regrouped.
  2. Adds buttons for the new services (data-page="mod-<name>").
  3. Adds a "Coming soon" placeholder page for every new service,
     inserted just before the Network Monitoring page.
  4. Adds a small block of CSS (before </head>) and JS (before </body>).

Safe to run once. If it has already been applied it stops and does nothing.
To undo: copy index.html.before-sidebar.bak back over index.html.
"""
import html
import os
import re
import shutil
import sys
from datetime import datetime

TARGET = "index.html"
MARK = "MS-SIDEBAR-V2"

GROUP_ORDER = ["core", "protect", "assess", "intel", "gov", "future"]
GROUP_TITLES = {
    "core": "Core Platform",
    "protect": "Protection Services",
    "assess": "Security Assessment",
    "intel": "Intelligence & Response",
    "gov": "Governance & Management",
    "future": "Premium (coming later)",
}

# ("old", data-page of an existing button) or ("new", key in MODULES)
LAYOUT = {
    "core": [
        ("old", "dashboard"), ("old", "devices"), ("old", "events"),
        ("old", "threats"), ("old", "severity"), ("old", "svc-soc_monitoring"),
        ("new", "siem"), ("new", "reports"),
    ],
    "protect": [
        ("old", "network"), ("new", "endpoint"), ("old", "svc-cloud_security"),
        ("new", "iam"), ("new", "email"), ("new", "dlp"), ("new", "zerotrust"),
        ("new", "backup"), ("new", "firewall"), ("new", "database"),
        ("new", "mobile"), ("new", "encryption"), ("new", "waf"),
    ],
    "assess": [
        ("old", "scanner"), ("new", "asm"), ("new", "appsec"), ("new", "patch"),
        ("new", "vendor"), ("new", "pentest"), ("new", "audits"),
        ("new", "configassess"),
    ],
    "intel": [
        ("old", "svc-ai_security"), ("old", "assistant"), ("old", "autopilot"),
        ("old", "svc-incident_response"), ("new", "forensics"),
        ("new", "awareness"), ("new", "threatintel"), ("new", "darkweb"),
        ("new", "malware"), ("new", "soar"),
    ],
    "gov": [
        ("old", "svc-grc_compliance"), ("new", "privacy"), ("old", "docscan"),
        ("old", "svc-requests"), ("old", "billing"), ("old", "settings"),
        ("old", "company"), ("old", "requests"),
    ],
    "future": [
        ("new", "fraud"), ("new", "mdr"), ("new", "cspm"), ("new", "pam"),
    ],
}

# tag: "new" = one of your 5 priority modules, "soon" = placeholder for later
# icon must be one of the symbols already in your page:
# dashboard laptop network shield bars list card lock alert building refresh users
MODULES = {
    "siem": ("SIEM & Log Management", "list", "new",
             "Collect, search and correlate security logs from all your devices and services in one place."),
    "reports": ("Security Reports & Analytics", "bars", "soon",
                "Scheduled and on-demand security reports with trends and analytics."),
    "endpoint": ("Endpoint Protection", "laptop", "soon",
                 "Protect laptops, desktops and servers against malware and suspicious activity."),
    "iam": ("Identity & Access Management (IAM)", "users", "soon",
            "Manage who can access what, with strong authentication and least-privilege access."),
    "email": ("Email & Phishing Protection", "alert", "soon",
              "Detect phishing, spoofing and malicious attachments before they reach your people."),
    "dlp": ("Data Loss Prevention (DLP)", "lock", "soon",
            "Stop sensitive data from leaving your organisation by accident or on purpose."),
    "zerotrust": ("Zero Trust Security", "shield", "soon",
                  "Verify every user, device and request instead of trusting the network by default."),
    "backup": ("Backup & Disaster Recovery", "refresh", "soon",
               "Back up critical systems and recover quickly after an attack or outage."),
    "firewall": ("Firewall & DNS Security", "shield", "soon",
                 "Manage firewall rules and block malicious domains at the DNS level."),
    "database": ("Database Security", "lock", "new",
                 "Monitor and protect your critical databases against misuse, leaks and attacks."),
    "mobile": ("Mobile Device Security", "laptop", "soon",
               "Secure and monitor phones and tablets that access company data."),
    "encryption": ("Encryption & Key Management", "lock", "soon",
                   "Manage encryption keys and confirm that sensitive data is encrypted."),
    "waf": ("Web Application Protection", "shield", "soon",
            "Shield your websites and web apps from common attacks such as injection and bots."),
    "asm": ("Attack Surface Management", "network", "soon",
            "Discover every internet-facing asset you own and see what attackers can see."),
    "appsec": ("Application & API Security", "shield", "soon",
               "Find and fix security weaknesses in your applications and APIs."),
    "patch": ("Patch & Configuration Management", "refresh", "soon",
              "Track missing patches and risky configurations across your systems."),
    "vendor": ("Third-Party & Vendor Risk Management", "building", "soon",
               "Assess and track the security risk that suppliers and partners bring."),
    "pentest": ("Penetration Testing", "alert", "new",
                "Request and track controlled attack tests that reveal real security weaknesses."),
    "audits": ("Security Audits", "list", "soon",
               "Plan, run and record security audits with findings and follow-up actions."),
    "configassess": ("Configuration Security Assessment", "bars", "soon",
                     "Check systems against hardening baselines and recommended settings."),
    "forensics": ("Digital Forensics", "list", "soon",
                  "Collect and preserve evidence to investigate what happened after an incident."),
    "awareness": ("Security Awareness", "users", "soon",
                  "Train staff to spot phishing and follow safe security habits."),
    "threatintel": ("Threat Intelligence", "alert", "new",
                    "Stay ahead of known and emerging threats with curated intelligence feeds."),
    "darkweb": ("Dark Web & Credential Monitoring", "alert", "soon",
                "Be alerted when your company's credentials or data appear on the dark web."),
    "malware": ("Malware Analysis", "shield", "soon",
                "Analyse suspicious files safely to learn what they do and how to respond."),
    "soar": ("Security Automation & Orchestration (SOAR)", "refresh", "new",
             "Automate repetitive security workflows and coordinate responses across tools."),
    "privacy": ("Privacy & Data Governance", "building", "soon",
                "Manage personal data, consent and data-handling obligations."),
    "fraud": ("Fraud Detection & Prevention", "alert", "soon",
              "Detect suspicious transactions, account activity and potential digital fraud."),
    "mdr": ("Managed Detection & Response (MDR)", "shield", "soon",
            "Continuous monitoring, threat investigation and response services."),
    "cspm": ("Cloud Security Posture Management (CSPM)", "network", "soon",
             "Continuously identify misconfigured and exposed cloud resources."),
    "pam": ("Privileged Access Management (PAM)", "lock", "soon",
            "Protect administrator accounts and control access to sensitive systems."),
}

CSS = """
<style id="ms-sidebar-v2-css">
.nav-hide{display:none !important}
.nav-search{padding:6px 4px 10px}
.nav-search input{width:100%;box-sizing:border-box;padding:9px 12px;border-radius:10px;border:1px solid rgba(148,163,184,.25);background:rgba(255,255,255,.06);color:#e2e8f0;font:inherit;font-size:.85rem;outline:none}
.nav-search input:focus{border-color:#38bdf8}
.nav-group-title{display:flex;align-items:center;justify-content:space-between;margin:14px 4px 4px;padding:6px 10px;font-size:.68rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:rgba(148,163,184,.85);cursor:pointer;user-select:none;border-radius:8px}
.nav-group-title:hover{color:#e2e8f0;background:rgba(255,255,255,.04)}
.nav-chev{display:inline-block;transition:transform .15s}
.nav-group-title.closed .nav-chev{transform:rotate(-90deg)}
.nav-tag{margin-left:auto;font-size:.58rem;font-weight:700;letter-spacing:.08em;padding:2px 6px;border-radius:999px;white-space:nowrap}
.nav-tag-new{background:rgba(45,212,191,.18);color:#2dd4bf}
.nav-tag-soon{background:rgba(148,163,184,.16);color:#94a3b8}
.soon-panel{text-align:center;padding:36px 20px}
.soon-panel .nav-tag{margin:0 0 12px;display:inline-block;font-size:.7rem;padding:4px 10px}
</style>
"""

JS = """
<script id="ms-sidebar-v2-js">
(function () {
  var nav = document.querySelector('nav[aria-label="Main navigation"]');
  if (!nav) { return; }
  var KEY = "ms_nav_groups_v2", state = {};
  try { state = JSON.parse(localStorage.getItem(KEY) || "{}") || {}; } catch (e) { state = {}; }
  function isOpen(g) { return (g in state) ? !!state[g] : g === "core"; }
  function save() { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {} }
  var titles = [].slice.call(nav.querySelectorAll(".nav-group-title"));
  var items = [].slice.call(nav.querySelectorAll(".nav-button[data-group]"));
  var search = document.getElementById("nav-search");

  function refresh() {
    var q = ((search && search.value) || "").trim().toLowerCase();
    var hit = {};
    items.forEach(function (b) {
      var g = b.getAttribute("data-group"), hide;
      if (q) {
        var label = (b.textContent || "").replace(/\\s+/g, " ").toLowerCase();
        var m = label.indexOf(q) > -1;
        if (m) { hit[g] = true; }
        hide = !m;
      } else { hide = !isOpen(g); }
      b.classList.toggle("nav-hide", hide);
    });
    titles.forEach(function (t) {
      var g = t.getAttribute("data-nav-group");
      t.classList.toggle("nav-hide", !!q && !hit[g]);
      t.classList.toggle("closed", !q && !isOpen(g));
      t.setAttribute("aria-expanded", q ? "true" : String(isOpen(g)));
    });
  }

  function toggle(t) {
    var g = t.getAttribute("data-nav-group");
    state[g] = !isOpen(g); save(); refresh();
  }
  titles.forEach(function (t) {
    t.addEventListener("click", function () { toggle(t); });
    t.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(t); }
    });
  });
  if (search) { search.addEventListener("input", refresh); }

  // keep the group of the active page open
  function openActive() {
    if (search && search.value) { return; }
    var a = nav.querySelector(".nav-button.active[data-group]");
    if (!a) { return; }
    var g = a.getAttribute("data-group");
    if (!isOpen(g)) { state[g] = true; save(); refresh(); }
  }
  new MutationObserver(openActive).observe(nav, { attributes: true, subtree: true, attributeFilter: ["class"] });
  refresh();
  openActive();
})();
</script>
"""


def esc(s):
    return html.escape(s, quote=True)


def new_button(key, group):
    label, icon, tag, _desc = MODULES[key]
    tag_text = "NEW" if tag == "new" else "SOON"
    return (
        '            <button type="button" class="nav-button" data-group="%s" data-page="mod-%s">\n'
        '                <svg class="icon" aria-hidden="true"><use href="#i-%s"/></svg>%s'
        '<span class="nav-tag nav-tag-%s">%s</span>\n'
        '            </button>'
    ) % (group, key, icon, esc(label), tag, tag_text)


def placeholder_page(key):
    label, _icon, _tag, desc = MODULES[key]
    return (
        '        <section id="mod-%s" class="page" hidden>\n'
        '            <h2>%s</h2>\n'
        '            <p class="page-description">%s</p>\n'
        '            <div class="panel soon-panel">\n'
        '                <span class="nav-tag nav-tag-soon">COMING SOON</span>\n'
        '                <h3>This module is on the MellowSecure roadmap</h3>\n'
        '                <p>It is not available yet. It will appear here as soon as it is released.</p>\n'
        '            </div>\n'
        '        </section>\n'
    ) % (key, esc(label), esc(desc))


def group_title(group):
    return (
        '            <div class="nav-group-title" data-nav-group="%s" role="button" tabindex="0" aria-expanded="true">'
        '<span>%s</span><span class="nav-chev" aria-hidden="true">&#9662;</span></div>'
    ) % (group, esc(GROUP_TITLES[group]))


def main():
    if not os.path.isfile(TARGET):
        sys.exit("ERROR: %s not found. Run this script from the MELLOWTECH folder." % TARGET)

    with open(TARGET, "r", encoding="utf-8", newline="") as fh:
        text = fh.read()

    if MARK in text:
        print("Sidebar v2 is already applied. Nothing changed.")
        return

    nav_re = re.compile(r'(<nav aria-label="Main navigation">)(.*?)(</nav>)', re.S)
    nav_m = nav_re.search(text)
    page_marker = "<!-- ========== NETWORK MONITORING ========== -->"
    problems = []
    if not nav_m:
        problems.append('could not find <nav aria-label="Main navigation">')
    if page_marker not in text:
        problems.append("could not find the NETWORK MONITORING page marker comment")
    if "</head>" not in text:
        problems.append("could not find </head>")
    if text.rfind("</body>") == -1:
        problems.append("could not find </body>")
    if problems:
        sys.exit("ERROR: " + "; ".join(problems) + ". index.html was NOT changed.")

    # existing buttons, keyed by data-page
    btn_re = re.compile(r'<button\b[^>]*class="nav-button[^"]*"[^>]*>.*?</button>', re.S)
    existing = {}
    order = []
    for m in btn_re.finditer(nav_m.group(2)):
        block = m.group(0)
        pm = re.search(r'data-page="([^"]+)"', block)
        if pm:
            existing[pm.group(1)] = block
            order.append(pm.group(1))

    placed = set()
    parts = [
        '\n            <div class="nav-search"><input type="search" id="nav-search" '
        'placeholder="Search services..." aria-label="Search services" autocomplete="off"></div>'
    ]
    for g in GROUP_ORDER:
        parts.append(group_title(g))
        for kind, key in LAYOUT[g]:
            if kind == "new" and key in existing:
                kind = "old"      # a real page with this name already exists (e.g. SIEM), keep it
            if kind == "old":
                block = existing.get(key)
                if block is None:
                    print("  note: existing button '%s' not found, skipped" % key)
                    continue
                placed.add(key)
                parts.append("            " + block.strip().replace("<button ", '<button data-group="%s" ' % g, 1))
            else:
                parts.append(new_button(key, g))
    # any existing button we did not know about goes to the end of the last real group
    leftovers = [k for k in order if k not in placed]
    if leftovers:
        print("  note: unplaced existing buttons added to Governance:", ", ".join(leftovers))
        parts.insert(
            len(parts),
            "\n".join("            " + existing[k].strip().replace("<button ", '<button data-group="gov" ', 1)
                      for k in leftovers),
        )
    new_inner = "\n".join(parts) + "\n        "

    # backup
    backup = TARGET + ".before-sidebar.bak"
    if os.path.exists(backup):
        backup = "%s.before-sidebar-%s.bak" % (TARGET, datetime.now().strftime("%H%M%S"))
    shutil.copy2(TARGET, backup)

    # 1. nav
    text = text[:nav_m.start(2)] + new_inner + text[nav_m.end(2):]

    # 2. placeholder pages (inserted right before the Network Monitoring page)
    pages = "        <!-- %s: placeholder pages -->\n" % MARK
    added = [k for k in MODULES if k not in existing]
    for key in added:
        pages += placeholder_page(key) + "\n"
    text = text.replace(page_marker, pages + "        " + page_marker, 1)

    # 3. CSS
    text = text.replace("</head>", CSS + "</head>", 1)

    # 4. JS
    i = text.rfind("</body>")
    text = text[:i] + JS + text[i:]

    with open(TARGET, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)

    n_new = len(added)
    print("Done.")
    print("  Backup saved as:        %s" % backup)
    print("  Existing buttons kept:  %d" % len(placed))
    print("  New services added:     %d (each with a placeholder page)" % n_new)
    print("Next: open the site locally, test, then redeploy (make_eb_zip.py).")


if __name__ == "__main__":
    main()