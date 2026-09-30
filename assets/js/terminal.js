/* A terminal that replays a keel session: the transcript is in the page,
   and this types it out once the terminal is in view. Screen readers get
   the transcript as it is; the typed copy is hidden from them. Loaded
   lazily; with reduced motion the transcript stays as written. */
(function () {
  "use strict";

  var TYPE_MS = 28;
  var LINE_MS = 90;
  var PAUSE_MS = 700;

  function terminal(element, options) {
    var pre = element.querySelector("pre");
    if (!pre || options.reduceMotion) { return; }
    var lines = Array.prototype.map.call(pre.querySelectorAll("[data-line]"), function (line) {
      return { kind: line.getAttribute("data-line"), node: line.cloneNode(true) };
    });
    if (!lines.length) { return; }

    // Keep the full transcript for assistive technology
    var source = pre.cloneNode(true);
    source.className = "sr-only";
    source.removeAttribute("tabindex");
    source.setAttribute("aria-label", pre.getAttribute("aria-label") || "Terminal transcript");
    pre.parentNode.insertBefore(source, pre);
    pre.setAttribute("aria-hidden", "true");
    pre.removeAttribute("tabindex");

    var replay = element.querySelector("[data-replay]");
    var timer = 0;

    function caret() {
      var span = document.createElement("span");
      span.className = "caret";
      return span;
    }

    function run() {
      window.clearTimeout(timer);
      pre.textContent = "";
      var index = 0;
      var cursor = caret();
      pre.appendChild(cursor);

      function next() {
        if (index >= lines.length) {
          if (replay) { replay.hidden = false; }
          return;
        }
        var line = lines[index];
        index += 1;
        if (line.kind === "cmd") {
          typeLine(line.node, function () { timer = window.setTimeout(next, PAUSE_MS); });
        } else {
          pre.insertBefore(line.node.cloneNode(true), cursor);
          timer = window.setTimeout(next, LINE_MS);
        }
      }

      function typeLine(node, done) {
        var holder = document.createElement("span");
        var prompt = node.querySelector(".prompt");
        var command = node.querySelector(".cmd");
        var text = command ? command.textContent : node.textContent;
        if (prompt) { holder.appendChild(prompt.cloneNode(true)); }
        var typed = document.createElement("span");
        typed.className = "cmd";
        holder.appendChild(typed);
        pre.insertBefore(holder, cursor);
        var position = 0;
        (function type() {
          typed.textContent = text.slice(0, position);
          position += 1;
          if (position <= text.length) {
            timer = window.setTimeout(type, TYPE_MS + Math.random() * 30);
          } else {
            pre.insertBefore(document.createTextNode("\n"), cursor);
            done();
          }
        })();
      }

      if (replay) { replay.hidden = true; }
      timer = window.setTimeout(next, 400);
    }

    if (replay) { replay.addEventListener("click", run); }
    run();
  }

  window.KeelModules = window.KeelModules || {};
  window.KeelModules.terminal = terminal;
})();
