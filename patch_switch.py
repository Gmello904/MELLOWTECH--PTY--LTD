import sys
path = sys.argv[1]
text = open(path, encoding="utf-8", newline="").read()
if "rq-switch" in text:
    sys.exit("Already patched.")

ANCHOR = '<div id="request-result" class="result-message" role="status" aria-live="polite"></div>'
if text.count(ANCHOR) != 1 or text.count("</body>") != 1:
    sys.exit("STOPPED: the page does not look as expected. Nothing was changed.")

PANEL = ANCHOR + """
            <div class="panel" id="rq-switch" hidden>
                <div class="stx-row" style="border-top:0">
                    <div>
                        <b>Require approval for new accounts</b>
                        <small id="rq-state">Loading...</small>
                    </div>
                    <button type="button" class="btn-small" id="rq-toggle" disabled>...</button>
                </div>
                <p class="stx-note">ON: new people wait until you approve them. OFF: they can sign in as soon as they confirm their email, and anyone already waiting is approved at that moment. People you rejected stay rejected.</p>
            </div>"""

SCRIPT = """<script>
(function () {
    var csrf = "", on = true;
    function $(id) { return document.getElementById(id); }
    function say(t, ok) {
        var b = $("request-result");
        b.textContent = t || "";
        b.style.color = ok ? "#12906e" : "#b42318";
    }
    function paint() {
        $("rq-state").textContent = on ? "ON: new accounts wait for your approval." : "OFF: new accounts can sign in after confirming their email.";
        $("rq-toggle").textContent = on ? "Turn OFF" : "Turn ON";
        $("rq-toggle").className = "btn-small" + (on ? " btn-danger" : "");
        $("rq-toggle").disabled = false;
    }
    function api(path, body) {
        var o = { credentials: "same-origin", headers: { "Content-Type": "application/json" } };
        if (body !== undefined) { o.method = "POST"; o.headers["X-CSRF-Token"] = csrf; o.body = JSON.stringify(body); }
        return fetch(path, o).then(function (r) {
            return r.json().catch(function () { return {}; }).then(function (d) {
                if (!r.ok) { throw new Error(d.error || "Something went wrong."); }
                return d;
            });
        });
    }
    document.addEventListener("DOMContentLoaded", function () {
        api("/api/auth/me").then(function (d) {
            csrf = d.csrf;
            return api("/api/requests/setting");
        }).then(function (s) {
            on = !!s.require_approval;
            $("rq-switch").hidden = false;
            paint();
        }).catch(function () {});
        $("rq-toggle").addEventListener("click", function () {
            var next = !on;
            if (!next && !window.confirm("Turn approval OFF? New people can sign in right after confirming their email, and everyone now waiting will be approved at once.")) { return; }
            $("rq-toggle").disabled = true;
            api("/api/requests/setting", { require_approval: next }).then(function (r) {
                on = !!r.require_approval;
                paint();
                say(on ? "Approval is ON. New accounts will wait for you." :
                    "Approval is OFF. " + r.released + " waiting account(s) were approved.", true);
            }).catch(function (e) { paint(); say(e.message, false); });
        });
    });
})();
</script>
</body>"""

text = text.replace(ANCHOR, PANEL).replace("</body>", SCRIPT)
open(path, "w", encoding="utf-8", newline="").write(text)
print("Patched", path)
