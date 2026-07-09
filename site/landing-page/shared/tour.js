/* Design-rationale tour engine.
   Usage: define window.TOUR_STEPS = [{sel, title, body}, ...] before this script.
   Adds a floating launch button; ?tour=1 starts the tour automatically. */
(function () {
  "use strict";
  var steps = (window.TOUR_STEPS || []).filter(function (s) {
    return document.querySelector(s.sel);
  });
  if (!steps.length) return;

  var launch = document.createElement("button");
  launch.className = "tour-launch";
  launch.innerHTML = '<span class="dot"></span>Why this page works — take the tour';
  document.body.appendChild(launch);

  var spot = null, card = null, i = 0, open = false;

  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  }

  function close() {
    open = false;
    if (spot) spot.remove(); spot = null;
    if (card) card.remove(); card = null;
    launch.style.display = "";
    document.removeEventListener("keydown", onKey);
    window.removeEventListener("resize", position);
    window.removeEventListener("scroll", position, true);
  }

  function position() {
    if (!open) return;
    var t = document.querySelector(steps[i].sel);
    if (!t) return;
    var r = t.getBoundingClientRect();
    var pad = 10;
    var top = r.top + window.scrollY - pad;
    var left = Math.max(8, r.left + window.scrollX - pad);
    spot.style.top = top + "px";
    spot.style.left = left + "px";
    spot.style.width = Math.min(r.width + pad * 2, document.documentElement.clientWidth - 16) + "px";
    spot.style.height = r.height + pad * 2 + "px";

    // card below the target unless there is more room above
    var ch = card.offsetHeight || 220;
    var below = r.bottom + ch + 28 < window.innerHeight;
    var cardTop = below ? r.bottom + window.scrollY + 16
                        : Math.max(window.scrollY + 12, r.top + window.scrollY - ch - 16);
    card.style.top = cardTop + "px";
    card.style.left = Math.max(12, Math.min(r.left + window.scrollX,
      window.scrollX + document.documentElement.clientWidth - card.offsetWidth - 12)) + "px";
  }

  function render() {
    var s = steps[i];
    var t = document.querySelector(s.sel);
    if (!t) { next(1); return; }
    if (!spot) { spot = el("div", "tour-spot"); document.body.appendChild(spot); }
    if (!card) { card = el("div", "tour-card"); document.body.appendChild(card); }
    card.innerHTML =
      '<div class="k"><span>Design decision</span><span>' + (i + 1) + " / " + steps.length + "</span></div>" +
      "<h4>" + s.title + "</h4><p>" + s.body + "</p>" +
      '<div class="row">' +
      '<button class="end" data-a="end">End tour</button>' +
      '<span><button data-a="prev"' + (i === 0 ? " disabled" : "") + ">← Back</button> " +
      '<button class="primary" data-a="next">' + (i === steps.length - 1 ? "Finish" : "Next →") + "</button></span></div>";
    card.querySelectorAll("button").forEach(function (b) {
      b.addEventListener("click", function () {
        var a = b.getAttribute("data-a");
        if (a === "end") close();
        if (a === "prev") next(-1);
        if (a === "next") i === steps.length - 1 ? close() : next(1);
      });
    });
    t.scrollIntoView({ behavior: "smooth", block: "center" });
    setTimeout(position, 350);
    position();
  }

  function next(d) { i = Math.min(steps.length - 1, Math.max(0, i + d)); render(); }

  function onKey(e) {
    if (e.key === "Escape") close();
    if (e.key === "ArrowRight") i === steps.length - 1 ? close() : next(1);
    if (e.key === "ArrowLeft") next(-1);
  }

  function start() {
    if (open) return;
    open = true; i = 0;
    launch.style.display = "none";
    document.addEventListener("keydown", onKey);
    window.addEventListener("resize", position);
    window.addEventListener("scroll", position, true);
    render();
  }

  launch.addEventListener("click", start);
  if (/[?&]tour=1/.test(location.search)) setTimeout(start, 800);
})();
