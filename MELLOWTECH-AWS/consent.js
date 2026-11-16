(function () {
    "use strict";
    var KEY = "mt-consent";

    function read() {
        try { return JSON.parse(localStorage.getItem(KEY) || "null"); } catch (e) { return null; }
    }

    function save(choice, prefs) {
        try { localStorage.setItem(KEY, JSON.stringify({ v: 2, choice: choice, prefs: prefs !== false, at: new Date().toISOString() })); } catch (e) { /* storage blocked */ }
        window.mtConsent = choice;
        applyPrefs(prefs !== false);
    }

    /* "Preferences" off: the light/dark choice is not remembered on this device. */
    function applyPrefs(on) {
        window.mtPrefsAllowed = on;
        if (!on) { try { localStorage.removeItem("mt-theme"); } catch (e) { /* ignore */ } }
        if (window.__mtGuard) { return; }
        window.__mtGuard = true;
        try {
            var original = Storage.prototype.setItem;
            Storage.prototype.setItem = function (key, value) {
                if (key === "mt-theme" && window.mtPrefsAllowed === false) { return; }
                return original.call(this, key, value);
            };
        } catch (e) { /* ignore */ }
    }

    function addStyle() {
        if (document.getElementById("mt-consent-style")) { return; }
        var style = document.createElement("style");
        style.id = "mt-consent-style";
        style.textContent =
            "#mt-consent{position:fixed;left:0;right:0;bottom:0;z-index:2147483000;box-sizing:border-box;padding:26px clamp(18px,4vw,60px);" +
            "background:#0d1b2a;color:#eaf2fb;border-top:1px solid #26405c;box-shadow:0 -12px 36px rgba(0,0,0,.35);" +
            "font:15px/1.55 system-ui,-apple-system,Segoe UI,Arial,sans-serif;max-height:92vh;overflow:auto}" +
            "#mt-consent .mt-wrap{display:flex;gap:40px;align-items:center;justify-content:space-between;max-width:1500px;margin:0 auto}" +
            "#mt-consent .mt-text{flex:1;min-width:0}" +
            "#mt-consent h2{margin:0 0 10px;font-size:24px;line-height:1.25;font-weight:800;color:#fff}" +
            "#mt-consent p{margin:0 0 12px}#mt-consent p:last-child{margin-bottom:0}#mt-consent a{color:#3ddbb0}" +
            "#mt-consent .mt-actions{flex:none;width:min(260px,100%);display:grid;gap:12px}" +
            "#mt-consent button{padding:11px 16px;border-radius:4px;border:1px solid #fff;background:#fff;color:#0d1b2a;font:inherit;font-weight:700;cursor:pointer}" +
            "#mt-consent button:hover{filter:brightness(.92)}" +
            "#mt-consent button.mt-yes{background:#3ddbb0;border-color:#3ddbb0;color:#07111d}" +
            "#mt-consent .mt-opts{display:none;margin:14px 0 0;padding:0;list-style:none;border-top:1px solid #26405c}" +
            "#mt-consent.mt-custom .mt-opts{display:block}" +
            "#mt-consent .mt-opts li{padding:14px 0;border-bottom:1px solid #26405c}" +
            "#mt-consent .mt-opts label{display:flex;gap:12px;align-items:flex-start;font-weight:700;cursor:pointer}" +
            "#mt-consent .mt-opts input{width:18px;height:18px;margin-top:3px;accent-color:#3ddbb0}" +
            "#mt-consent .mt-opts small{display:block;font-weight:400;opacity:.8;margin-top:2px}" +
            "#mt-consent .mt-save{display:none}#mt-consent.mt-custom .mt-save{display:block}#mt-consent.mt-custom .mt-main{display:none}" +
            "@media(max-width:820px){#mt-consent .mt-wrap{flex-direction:column;align-items:stretch;gap:20px}#mt-consent .mt-actions{width:100%}#mt-consent h2{font-size:21px}}" +
            "/*mt-compact*/#mt-consent{left:16px;right:auto;bottom:16px;width:min(360px,calc(100vw - 32px));padding:16px 18px;border-radius:14px;border:1px solid #26405c;max-height:70vh;font-size:13.5px;line-height:1.45}" +
            "#mt-consent .mt-wrap{display:block}" +
            "#mt-consent h2{font-size:16px;margin:0 0 6px}" +
            "#mt-consent .mt-actions{width:100%;margin-top:12px;grid-template-columns:1fr 1fr;gap:8px}" +
            "#mt-consent .mt-actions .mt-yes.mt-main,#mt-consent .mt-actions .mt-save{grid-column:1 / -1}" +
            "#mt-consent button{padding:9px 10px;font-size:13px;border-radius:8px}" +
            "#mt-consent .mt-opts li{padding:10px 0}" +
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
        box.setAttribute("aria-label", "Cookie preferences");
        var current = read();
        var prefsOn = current && current.prefs === false ? "" : " checked";
        box.innerHTML =
            "<div class=\"mt-wrap\"><div class=\"mt-text\">" +
            "<h2>Cookies</h2>" +
            "<p>We use one essential cookie to keep you signed in. With your OK we also remember light or dark mode. No ads, no tracking. " +
            "<a href=\"cookies.html\" target=\"_blank\" rel=\"noopener\">Learn more</a></p>" +
            "<ul class=\"mt-opts\">" +
            "<li><label><input type=\"checkbox\" checked disabled> <span>Essential<small>Keeps you signed in and protects your account. Always on.</small></span></label></li>" +
            "<li><label><input type=\"checkbox\" id=\"mt-pref-box\"" + prefsOn + "> <span>Preferences<small>Remembers your light or dark mode on this device.</small></span></label></li>" +
            "</ul></div>" +
            "<div class=\"mt-actions\">" +
            "<button type=\"button\" class=\"mt-yes mt-main\" data-choice=\"all\">Accept</button>" +
            "<button type=\"button\" class=\"mt-main\" data-choice=\"essential\">Decline</button>" +
            "<button type=\"button\" class=\"mt-main\" data-customize>Customize</button>" +
            "<button type=\"button\" class=\"mt-yes mt-save\" data-choice=\"custom\">Save preferences</button>" +
            "</div></div>";
        box.addEventListener("click", function (event) {
            if (event.target.closest("[data-customize]")) { box.classList.add("mt-custom"); return; }
            var button = event.target.closest("[data-choice]");
            if (!button) { return; }
            var choice = button.dataset.choice;
            var prefs = choice === "all" ? true : choice === "essential" ? false : !!box.querySelector("#mt-pref-box").checked;
            save(choice, prefs);
            close();
        });
        document.body.appendChild(box);
    }

    function addLinks() {
        /* The legal links appear only inside the platform, after sign-in (the page with the sidebar menu).
           The sign-in, sign-up and password pages do not show them. The legal pages carry their own links. */
        var insidePlatform = !!document.querySelector(".nav-button[data-page]");
        if (!insidePlatform || document.body.hasAttribute("data-legal-page") || document.querySelector(".mt-legal-links")) { return; }
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
        if (saved && saved.choice) { window.mtConsent = saved.choice; applyPrefs(saved.prefs !== false && saved.choice !== "essential"); } else { show(); }
        addLinks();
    }

    if (document.readyState === "loading") { document.addEventListener("DOMContentLoaded", start); } else { start(); }
})();