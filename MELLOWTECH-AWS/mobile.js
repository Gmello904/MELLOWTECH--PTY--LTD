/* MellowTech mobile support. Laptop layout is untouched (everything here is for screens 900px wide or narrower).
   Load in <head> of index.html:  <script src="mobile.js"></script>   (no changes to app.js needed) */
(function () {
    "use strict";

    var CSS = `
.mt-burger, .mt-scrim { display: none; }
@media (max-width: 900px) {
  html, body { overflow-x: hidden; max-width: 100%; }
  body { display: block !important; }
  body.mt-nav-open { overflow: hidden; }

  .sidebar {
    position: fixed !important; top: 0; left: 0; bottom: 0; height: 100% !important;
    width: min(300px, 86vw) !important; max-width: none !important; box-sizing: border-box;
    transform: translateX(-105%); transition: transform .28s ease; z-index: 300 !important;
    overflow-x: hidden; overflow-y: auto; -webkit-overflow-scrolling: touch;
  }
  body.mt-nav-open .sidebar { transform: none; box-shadow: 0 0 44px rgba(0,0,0,.55); }
  .mt-scrim { position: fixed; inset: 0; z-index: 250; background: rgba(4,10,20,.6); }
  body.mt-nav-open .mt-scrim { display: block; }

  .sidebar nav { display: flex !important; flex-direction: column; flex-wrap: nowrap !important; flex: 0 0 auto !important; gap: 4px; }
  .sidebar-bottom { margin-top: 18px; }
  .nav-button {
    display: flex !important; align-items: center; gap: 12px; float: none !important;
    width: 100% !important; margin: 0 !important; box-sizing: border-box; text-align: left;
    padding: 13px 52px 13px 14px !important; min-height: 46px; white-space: normal; line-height: 1.25;
  }
  .nav-button[hidden] { display: none !important; }
  .nav-button .icon { flex: none; }
  .nav-lock { right: 12px !important; }

  .main-content { margin: 0 !important; width: 100% !important; max-width: 100% !important; min-width: 0; box-sizing: border-box; padding: 10px !important; }

  .mt-burger { display: inline-grid; place-items: center; grid-row: 1 / span 2; width: 44px; height: 44px; border-radius: 12px; cursor: pointer; padding: 0;
    border: 1px solid rgba(120,140,160,.4); background: rgba(120,140,160,.12); color: inherit; }
  .mt-burger svg { width: 22px; height: 22px; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; }
  .topbar { grid-template-columns: minmax(0,1fr) !important; gap: 10px !important; padding: 12px !important; border-radius: 14px !important; top: 8px !important; }
  .topbar > div:first-child { display: grid; grid-template-columns: auto minmax(0,1fr); column-gap: 12px; align-items: center; min-width: 0; }
  .topbar h1 { font-size: 20px !important; margin: 0; }
  .topbar p { font-size: 12px; margin: 0; }
  .mt-search { grid-column: auto !important; order: 0 !important; max-width: none !important; }
  .user-area { display: flex !important; flex-wrap: wrap; align-items: center; gap: 8px !important; min-width: 0; }
  .plan-badge { padding: 6px 12px; }

  .stats-grid, .severity-grid { grid-template-columns: 1fr 1fr !important; gap: 10px !important; }
  .dashboard-grid, .ov-grid, .tg-grid, .device-grid, .tg-hero, .plans-grid { grid-template-columns: 1fr !important; }
  .tg-radar-box { display: none; }
  .panel, .stat-card { min-width: 0; box-sizing: border-box; }
  .panel-header { flex-wrap: wrap; gap: 10px; }
  .status-item { flex-wrap: wrap; gap: 4px 12px; }
  .form-row { flex-wrap: wrap; }
  .form-row .field, .form-row label.field { flex: 1 1 100% !important; }
  .actions, .event-controls { flex-wrap: wrap; gap: 8px; }
  .table-scroll, .table-panel { overflow-x: auto; -webkit-overflow-scrolling: touch; max-width: 100%; }
  .events-table { min-width: 560px; }
  img, svg, canvas, video { max-width: 100%; }
  .bl-hero, .dh-hero { padding: 20px !important; }
  .bl-hero h3 { font-size: 26px !important; }
  .am-msg { max-width: 94%; }
}
@media (max-width: 420px) {
  .stats-grid, .severity-grid { grid-template-columns: 1fr !important; }
  .dh-hero h2 { font-size: 24px !important; }
}`;

    var style = document.createElement("style");
    style.id = "mt-mobile";
    style.textContent = CSS;
    document.head.appendChild(style);

    /* The false "page styling is missing" banner: app.js decides the CSS is missing because the sidebar is
       "static" on phones. Skip that one check on phone widths; laptops still get the real warning. */
    var RE = /page styling is missing|style\.css was found/i;
    function sweep() {
        if (window.innerWidth > 900 || !document.body) return;
        [].slice.call(document.body.children).forEach(function (n) {
            if (/^(SCRIPT|STYLE|LINK)$/.test(n.tagName)) return;
            var t = n.textContent || "";
            if (t.length < 600 && RE.test(t)) { n.remove(); }
        });
        var box = document.getElementById("mt-banners");
        if (box) {
            [].slice.call(box.children).forEach(function (bar) { if (RE.test(bar.textContent)) bar.remove(); });
        }
    }
    new MutationObserver(sweep).observe(document.documentElement, { childList: true, subtree: true });

    document.addEventListener("DOMContentLoaded", function () {
        /* wrap app.js's check (this listener runs before app.js's own, so the wrap is in place in time) */
        if (typeof window.checkStylesheet === "function") {
            var original = window.checkStylesheet;
            window.checkStylesheet = function () {
                if (window.innerWidth <= 900) { return; }
                return original.apply(this, arguments);
            };
        }
        sweep();

        /* hamburger + drawer */
        var first = document.querySelector(".topbar > div");
        var side = document.querySelector(".sidebar");
        if (!first || !side) { return; }

        var burger = document.createElement("button");
        burger.type = "button";
        burger.className = "mt-burger";
        burger.setAttribute("aria-label", "Open menu");
        burger.setAttribute("aria-expanded", "false");
        burger.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"/></svg>';
        first.insertBefore(burger, first.firstChild);

        var scrim = document.createElement("div");
        scrim.className = "mt-scrim";
        document.body.appendChild(scrim);

        function set(open) {
            document.body.classList.toggle("mt-nav-open", open);
            burger.setAttribute("aria-expanded", open ? "true" : "false");
        }
        burger.addEventListener("click", function () { set(!document.body.classList.contains("mt-nav-open")); });
        scrim.addEventListener("click", function () { set(false); });
        side.addEventListener("click", function (e) { if (e.target.closest(".nav-button")) { set(false); } });
        document.addEventListener("keydown", function (e) { if (e.key === "Escape") { set(false); } });
        window.addEventListener("resize", function () { if (window.innerWidth > 900) { set(false); } });
    });
})();