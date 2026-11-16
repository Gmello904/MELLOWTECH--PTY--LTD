"""Part 1c: gives every security service its own button in the left menu and its own page.

Put this file in the MELLOWTECH folder (next to index.html) and run:
    python apply_service_pages.py
Run apply_features.py and apply_services.py first. Backups are saved next to each changed file as *.bak
"""
import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent

# key, menu label, page heading, icon
PAGES = [
    ("ai_security", "AI Security", "AI Security", "i-lock"),
    ("incident_response", "Incident Response", "Incident Response", "i-alert"),
    ("cloud_security", "Cloud Security", "Cloud Security", "i-network"),
    ("soc_monitoring", "Security Monitoring", "Security Monitoring (SOC)", "i-bars"),
    ("grc_compliance", "Compliance and Risk", "Compliance and Risk (GRC)", "i-building"),
]

NAV = "".join(
    f'''<button type="button" class="nav-button" data-page="svc-{key}">
                <svg class="icon" aria-hidden="true"><use href="#{icon}"/></svg>{label}
            </button>
            '''
    for key, label, _heading, icon in PAGES
) + '''<button type="button" class="nav-button" data-page="svc-requests" data-platform-admin hidden>
                <svg class="icon" aria-hidden="true"><use href="#i-users"/></svg>Service requests
            </button>
            '''

SECTIONS = "".join(
    f'''<!-- ========== SERVICE: {heading} ========== -->
        <section id="svc-{key}" class="page" hidden>
            <h2>{heading}</h2>
            <p class="page-description">Run a quick security check, ask MellowTech for help, or report a problem.</p>
            <div id="svc-top-{key}">Loading...</div>
            <div id="svc-msg-{key}" class="result-message" role="status" aria-live="polite"></div>
            <div id="svc-form-{key}"></div>
        </section>

        '''
    for key, _label, heading, _icon in PAGES
) + '''<!-- ========== SERVICE REQUESTS (staff) ========== -->
        <section id="svc-requests" class="page" hidden>
            <h2>Service requests</h2>
            <p class="page-description">Help requests and incident reports from customers. Urgent incident reports are listed first.</p>
            <div class="panel">
                <div class="table-scroll">
                    <table class="events-table">
                        <caption class="sr-only">Customer service requests</caption>
                        <thead><tr><th scope="col">Time</th><th scope="col">Company</th><th scope="col">Person</th><th scope="col">Service</th><th scope="col">Message</th><th scope="col">Status</th><th scope="col">Action</th></tr></thead>
                        <tbody id="svc-requests-body"><tr><td colspan="7">Loading...</td></tr></tbody>
                    </table>
                </div>
            </div>
        </section>

        '''

SCRIPT = r'''<!-- Security service pages (one menu button each) -->
    <script>
    (function () {
        var csrf = "";
        var me = null;
        var services = [];

        function $(id) { return document.getElementById(id); }

        function esc(value) {
            return String(value == null ? "" : value).replace(/[&<>"']/g, function (c) {
                return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
            });
        }

        function api(path, body) {
            var options = { credentials: "same-origin", headers: { "Content-Type": "application/json" } };
            if (body !== undefined) {
                options.method = "POST";
                options.headers["X-CSRF-Token"] = csrf;
                options.body = JSON.stringify(body);
            }
            return fetch(path, options).then(function (response) {
                return response.json().catch(function () { return {}; }).then(function (data) {
                    if (!response.ok) {
                        var problem = new Error(data.error || "Something went wrong.");
                        problem.locked = !!data.locked;
                        throw problem;
                    }
                    return data;
                });
            });
        }

        function openPage(page) {
            var button = document.querySelector('.nav-button[data-page="' + page + '"]');
            if (button) { button.click(); }
        }

        function isStaffAdmin() { return !!(me && me.is_platform && me.role === "admin"); }

        function say(key, text, kind, withUnlock) {
            var box = $("svc-msg-" + key);
            if (!box) { return; }
            box.textContent = text || "";
            box.style.color = kind === "err" ? "#b42318" : kind === "ok" ? "#12906e" : "";
            if (text && withUnlock) {
                var unlock = document.createElement("button");
                unlock.type = "button";
                unlock.className = "btn-small";
                unlock.style.marginLeft = "12px";
                unlock.textContent = "Unlock with a plan";
                unlock.addEventListener("click", function () { openPage("billing"); });
                box.appendChild(unlock);
            }
        }

        function find(key) {
            return services.filter(function (s) { return s.key === key; })[0];
        }

        function drawService(s) {
            var top = $("svc-top-" + s.key);
            if (!top) { return; }
            var last = s.last
                ? '<p class="rl-skills">Last check: <b>' + esc(s.last.score) + "%</b> on " + esc(new Date(s.last.at).toLocaleDateString()) + "</p>"
                : '<p class="rl-skills">Not checked yet.</p>';
            var extra = s.extra === "alerts"
                ? '<button type="button" class="btn-small" data-svc-open="threats">Open live alerts</button>'
                : s.extra === "incident"
                    ? '<button type="button" class="btn-small btn-danger" data-svc-incident="1">Report an incident</button>'
                    : "";
            top.innerHTML = '<div class="panel"><h3>' + esc(s.role) + "</h3><p>" + esc(s.blurb) + "</p>" + last +
                '<div class="actions" style="margin-top:12px">' +
                '<button type="button" class="btn-small" data-svc-check="' + esc(s.key) + '">Run security check</button>' +
                '<button type="button" class="btn-small" data-svc-request="' + esc(s.key) + '">Request help</button>' +
                extra + "</div></div>";
        }

        function loadServices() {
            api("/api/services").then(function (list) {
                services = list;
                services.forEach(drawService);
            }).catch(function (problem) {
                document.querySelectorAll('[id^="svc-top-"]').forEach(function (box) { box.textContent = problem.message; });
            });
        }

        function loadRequests() {
            api("/api/services/requests").then(function (rows) {
                $("svc-requests-body").innerHTML = rows.length ? rows.map(function (r) {
                    var done = r.status === "done";
                    return "<tr><td>" + esc(new Date(r.at).toLocaleString()) + "</td><td>" + esc(r.company) + "</td><td>" +
                        esc(r.person) + " (" + esc(r.email) + ")</td><td>" + (r.urgent ? '<span class="badge danger">URGENT</span> ' : "") +
                        esc(r.service) + "</td><td>" + esc(r.note || "") + "</td><td>" + esc(r.status.replace("_", " ")) + "</td><td>" +
                        (done ? "" : '<button type="button" class="btn-small" data-svc-done="' + esc(r.id) + '">Mark done</button>') +
                        "</td></tr>";
                }).join("") : '<tr><td colspan="7">No requests yet.</td></tr>';
            }).catch(function () {});
        }

        function openCheck(key) {
            var s = find(key);
            if (!s) { return; }
            var html = '<div class="panel"><div class="panel-header"><div><h3>' + esc(s.name) + ' security check</h3>' +
                "<p>Answer honestly. This is practical guidance, not a formal audit.</p></div></div>";
            s.questions.forEach(function (q, i) {
                html += '<div class="status-item" style="align-items:flex-start;gap:16px"><span style="flex:1">' + esc(q) + "</span><span>" +
                    [["yes", "Yes"], ["no", "No"], ["unsure", "Not sure"]].map(function (o) {
                        return '<label style="margin-left:12px;white-space:nowrap"><input type="radio" name="svcq-' + esc(key) + "-" + i + '" value="' + o[0] + '"> ' + o[1] + "</label>";
                    }).join("") + "</span></div>";
            });
            html += '<div class="actions" style="margin-top:14px"><button type="button" class="btn-small" data-svc-submit="' + esc(key) +
                '">See my result</button></div><div id="svc-result-' + esc(key) + '"></div></div>';
            $("svc-form-" + key).innerHTML = html;
            $("svc-form-" + key).scrollIntoView({ behavior: "smooth", block: "start" });
        }

        function submitCheck(key) {
            var s = find(key);
            var answers = [];
            for (var i = 0; i < s.questions.length; i++) {
                var chosen = document.querySelector('input[name="svcq-' + key + "-" + i + '"]:checked');
                if (!chosen) { say(key, "Answer every question first.", "err"); return; }
                answers.push(chosen.value);
            }
            say(key, "", "");
            api("/api/services/check", { service: key, answers: answers }).then(function (r) {
                var colour = r.level === "high" ? "#b42318" : r.level === "medium" ? "#c47b00" : "#12906e";
                var html = '<h3 style="margin-top:18px">Your result: <span style="color:' + colour + '">' + esc(r.score) + "% (" + esc(r.verdict) + ")</span></h3>";
                if (r.gaps.length) {
                    html += "<p>Fix these first:</p><ul style=\"margin:8px 0 0;padding-left:20px;display:grid;gap:10px\">" +
                        r.gaps.map(function (g) {
                            return "<li><b>" + esc(g.question) + "</b><br>" + esc(g.fix) + "</li>";
                        }).join("") + "</ul>" +
                        '<div class="actions" style="margin-top:14px"><button type="button" class="btn-small" data-svc-request="' + esc(key) + '">Ask MellowTech to help with these</button></div>';
                } else {
                    html += "<p>Well done: every answer was Yes. Re-check regularly, because things change.</p>";
                }
                $("svc-result-" + key).innerHTML = html;
                loadServices();
            }).catch(function (problem) { say(key, problem.message, "err"); });
        }

        function sendRequest(key, urgent) {
            var s = find(key);
            var note = window.prompt(urgent
                ? "Describe what happened, in a few words.\n\nIf you can, disconnect the affected devices from the network. This sends an URGENT alert to MellowTech."
                : "How can MellowTech help with " + s.name + "? (optional)", "");
            if (note === null) { return; }
            api("/api/services/request", { service: key, note: note, urgent: !!urgent }).then(function () {
                say(key, urgent ? "Incident reported. MellowTech has been alerted and a High alert was added to your dashboard."
                                : "Request sent. MellowTech will contact you.", "ok");
                if (urgent && typeof loadSecurityEvents === "function") { loadSecurityEvents(); }
                if (isStaffAdmin()) { loadRequests(); }
            }).catch(function (problem) { say(key, problem.message, "err", problem.locked); });
        }

        document.addEventListener("click", function (event) {
            var t = event.target.closest("[data-svc-check],[data-svc-request],[data-svc-submit],[data-svc-open],[data-svc-incident],[data-svc-done]");
            if (!t) { return; }
            var d = t.dataset;
            if (d.svcCheck) { openCheck(d.svcCheck); }
            else if (d.svcSubmit) { submitCheck(d.svcSubmit); }
            else if (d.svcRequest) { sendRequest(d.svcRequest, false); }
            else if (d.svcIncident) { sendRequest("incident_response", true); }
            else if (d.svcOpen) { openPage(d.svcOpen); }
            else if (d.svcDone) {
                api("/api/services/requests/" + encodeURIComponent(d.svcDone) + "/status", { status: "done" })
                    .then(loadRequests).catch(function () {});
            }
        });

        document.addEventListener("DOMContentLoaded", function () {
            api("/api/auth/me").then(function (data) {
                csrf = data.csrf;
                me = data.user;
                loadServices();
                if (isStaffAdmin()) { loadRequests(); }
            }).catch(function () {});
            document.querySelectorAll('.nav-button[data-page^="svc-"]').forEach(function (button) {
                button.addEventListener("click", function () {
                    loadServices();
                    if (isStaffAdmin()) { loadRequests(); }
                });
            });
        });
    })();
    </script>
'''

MARKER = 'id="svc-top-ai_security"'


def patch(path):
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return "already updated"
    if 'id="svc-panel"' not in text:
        return "NOT changed: run apply_services.py first"

    steps = [
        ("menu button", r'<button type="button" class="nav-button" data-page="roles">.*?</button>\s*', NAV),
        ("page", r"<!-- ========== SECURITY ROLES ========== -->.*?(?=<!-- ========== COMPANY ========== -->)", SECTIONS),
        ("script", r"<!-- Security Services \(checks, help requests, incident reports\) -->\s*<script>.*?</script>\s*", SCRIPT.rstrip() + "\n    "),
    ]
    for name, pattern, replacement in steps:
        matches = re.findall(pattern, text, re.S)
        if len(matches) != 1:
            return f"NOT changed: could not find the {name} to replace (found {len(matches)})"
        text = re.sub(pattern, lambda m, r=replacement: r, text, count=1, flags=re.S)

    shutil.copy2(path, str(path) + ".bak")
    path.write_text(text, encoding="utf-8")
    return "updated"


def main():
    for path in (HERE / "index.html", HERE / "aws-deploy" / "index.html"):
        if path.is_file():
            print(f"{path.relative_to(HERE)}: {patch(path)}")
        else:
            print(f"{path.relative_to(HERE)}: not found, skipped")
    print("\nDone. Refresh the browser with Ctrl+Shift+R (no restart needed).")


if __name__ == "__main__":
    main()