/* The request pipeline of Keel Web in an advanced installation (decision
   0030): CrowdSec bans first, Nginx terminates TLS and runs the WAF inline,
   Anubis sits behind Nginx, then the application. Requests are drawn as
   dots; the list under the canvas says the same in words. Loaded lazily. */
(function () {
  "use strict";

  var STATIONS = [
    { name: "Internet", short: "Net" },
    { name: "CrowdSec", short: "CrowdSec" },
    { name: "Nginx + WAF", short: "WAF" },
    { name: "Anubis", short: "Anubis" },
    { name: "Application", short: "App" }
  ];
  // Where a request ends: banned by CrowdSec, refused by the WAF, or it
  // reaches the application, after an Anubis challenge unless it is an
  // exempt crawler. The shares are for the picture, not a measurement.
  var OUTCOMES = [
    { stop: 1, kind: "ban", weight: 0.16 },
    { stop: 2, kind: "waf", weight: 0.14 },
    { stop: 4, kind: "pow", weight: 0.42 },
    { stop: 4, kind: "crawler", weight: 0.28 }
  ];

  function colors() {
    var style = getComputedStyle(document.documentElement);
    function read(name, fallback) {
      var value = style.getPropertyValue(name).trim();
      return value || fallback;
    }
    return {
      mesh: read("--mesh", "#0E7C77"),
      accent: read("--accent", "#0072C9"),
      warn: read("--warn", "#8A5300"),
      stop: read("--stop", "#B42318"),
      fg: read("--fg", "#0B1F3A"),
      muted: read("--muted", "#44576F"),
      surface: read("--surface-2", "#F2F6FA"),
      line: read("--line-strong", "#B9C7D6")
    };
  }

  function pick() {
    var roll = Math.random();
    for (var i = 0; i < OUTCOMES.length; i += 1) {
      roll -= OUTCOMES[i].weight;
      if (roll <= 0) { return OUTCOMES[i]; }
    }
    return OUTCOMES[OUTCOMES.length - 1];
  }

  function pipeline(element, options) {
    var canvas = element.querySelector("canvas");
    if (!canvas || !canvas.getContext) { return; }
    var context = canvas.getContext("2d");
    var palette = colors();
    var width = 0;
    var height = 0;
    var requests = [];
    var last = 0;
    var running = false;
    var visible = false;
    var frame = 0;
    var still = options.reduceMotion;

    function stationX(index) {
      // The centre of each column of the list under the canvas
      return (width * (2 * index + 1)) / (2 * STATIONS.length);
    }

    function resize() {
      var ratio = Math.min(window.devicePixelRatio || 1, 2);
      var box = canvas.getBoundingClientRect();
      width = box.width;
      height = box.height;
      canvas.width = Math.round(width * ratio);
      canvas.height = Math.round(height * ratio);
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      if (!running) { draw(performance.now()); }
    }

    function drawStations() {
      var mid = height * 0.46;
      context.save();
      context.strokeStyle = palette.line;
      context.lineWidth = 2;
      context.beginPath();
      context.moveTo(stationX(0), mid);
      context.lineTo(stationX(STATIONS.length - 1), mid);
      context.stroke();
      STATIONS.forEach(function (station, index) {
        var x = stationX(index);
        var size = index === 0 ? 14 : 20;
        context.fillStyle = palette.surface;
        context.strokeStyle = index === STATIONS.length - 1 ? palette.mesh : palette.fg;
        context.lineWidth = 2;
        context.beginPath();
        if (context.roundRect) {
          context.roundRect(x - size, mid - size, size * 2, size * 2, 8);
        } else {
          context.rect(x - size, mid - size, size * 2, size * 2);
        }
        context.fill();
        context.stroke();
        context.fillStyle = palette.muted;
        context.font = "600 " + (width < 520 ? 10 : 12) + "px system-ui, sans-serif";
        context.textAlign = "center";
        context.fillText(width < 520 ? station.short : station.name, x, mid + 42);
      });
      context.restore();
    }

    function spawn(time) {
      var outcome = pick();
      requests.push({ born: time, outcome: outcome, lane: (Math.random() - 0.5) * 10 });
    }

    function colorOf(kind) {
      if (kind === "ban") { return palette.stop; }
      if (kind === "waf") { return palette.warn; }
      if (kind === "pow") { return palette.accent; }
      return palette.mesh;
    }

    function drawRequest(request, time) {
      var speed = width / 3200; // pixels per millisecond
      var start = stationX(0);
      var end = stationX(request.outcome.stop);
      var challenge = request.outcome.kind === "pow";
      var anubis = stationX(3);
      var hold = challenge ? 650 : 0;
      var age = time - request.born;
      var x = start + age * speed;
      var fade = 1;
      var held = false;
      if (challenge && x >= anubis) {
        var over = age - (anubis - start) / speed;
        if (over < hold) { x = anubis; held = true; } else { x = anubis + (over - hold) * speed; }
      }
      if (x >= end) {
        var after = age - (end - start) / speed - hold;
        x = end;
        fade = Math.max(0, 1 - after / 500);
        if (fade <= 0) { request.dead = true; return; }
      }
      var y = height * 0.46 + request.lane;
      context.save();
      context.globalAlpha = fade;
      context.fillStyle = colorOf(request.outcome.kind);
      if (request.outcome.kind === "crawler") {
        context.fillRect(x - 3.5, y - 3.5, 7, 7);
      } else {
        context.beginPath();
        context.arc(x, y, 3.8, 0, Math.PI * 2);
        context.fill();
      }
      if (held) {
        context.strokeStyle = palette.accent;
        context.lineWidth = 1.5;
        context.beginPath();
        context.arc(x, y, 9, -Math.PI / 2, -Math.PI / 2 + ((time / 180) % (Math.PI * 2)));
        context.stroke();
      }
      if (x === end && request.outcome.stop < 4) {
        context.fillStyle = colorOf(request.outcome.kind);
        context.font = "700 11px ui-monospace, Menlo, Consolas, monospace";
        context.textAlign = "center";
        context.fillText(request.outcome.kind === "ban" ? "banned" : "403", x, height * 0.46 - 28 - (1 - fade) * 10);
      }
      context.restore();
    }

    function drawStill() {
      var mid = height * 0.46;
      var samples = [
        { x: 0.5, kind: "ban", stop: 1 }, { x: 1.5, kind: "waf" }, { x: 2.5, kind: "pow" },
        { x: 3.5, kind: "crawler" }, { x: 3.7, kind: "pow" }
      ];
      samples.forEach(function (sample) {
        var from = Math.floor(sample.x);
        var x = stationX(from) + (stationX(from + 1) - stationX(from)) * (sample.x - from);
        context.fillStyle = colorOf(sample.kind);
        context.beginPath();
        context.arc(x, mid, 3.8, 0, Math.PI * 2);
        context.fill();
      });
    }

    function draw(time) {
      context.clearRect(0, 0, width, height);
      drawStations();
      if (still) { drawStill(); return; }
      requests.forEach(function (request) { drawRequest(request, time); });
      requests = requests.filter(function (request) { return !request.dead; });
    }

    function tick(now) {
      if (!running) { return; }
      if (now - last > 420) { spawn(now); last = now; }
      draw(now);
      frame = window.requestAnimationFrame(tick);
    }

    function play() {
      if (still || running || !visible || document.hidden) { return; }
      running = true;
      frame = window.requestAnimationFrame(tick);
    }

    function pause() {
      running = false;
      window.cancelAnimationFrame(frame);
    }

    resize();
    if (window.ResizeObserver) { new ResizeObserver(resize).observe(canvas); }
    document.addEventListener("keel:theme", function () { palette = colors(); if (!running) { draw(performance.now()); } });
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (entries) {
        visible = entries[0].isIntersecting;
        if (visible) { play(); } else { pause(); }
      }).observe(canvas);
    } else {
      visible = true;
      play();
    }
    document.addEventListener("visibilitychange", function () {
      if (document.hidden) { pause(); } else { play(); }
    });
  }

  window.KeelModules = window.KeelModules || {};
  window.KeelModules.pipeline = pipeline;
})();
