/* The hero's mesh: appliances joining a WireGuard mesh over IPv6.
   Tunnels come up one by one, packets travel them, and one node behind a
   NAT opens its tunnel from the inside. Loaded lazily by site.js. The
   addresses are from the documentation prefix, 2001:db8::/32. */
(function () {
  "use strict";

  var NODES = [
    { x: 0.16, y: 0.20, label: "2001:db8:a::10" },
    { x: 0.50, y: 0.12, label: "2001:db8:b::10" },
    { x: 0.85, y: 0.24, label: "2001:db8:c::10" },
    { x: 0.30, y: 0.52, label: "2001:db8:a::20" },
    { x: 0.68, y: 0.50, label: "2001:db8:b::20" },
    { x: 0.12, y: 0.84, label: "behind NAT", nat: true },
    { x: 0.47, y: 0.84, label: "2001:db8:c::20" },
    { x: 0.86, y: 0.78, label: "2001:db8:d::10" },
    { x: 0.62, y: 0.28, small: true },
    { x: 0.36, y: 0.30, small: true },
    { x: 0.75, y: 0.66, small: true },
    { x: 0.24, y: 0.68, small: true }
  ];
  // Tunnels, in the order they come up. The last one is the NAT's.
  var EDGES = [
    [0, 9], [9, 1], [1, 8], [8, 2], [0, 3], [9, 3], [8, 4], [2, 4],
    [3, 4], [3, 11], [11, 6], [4, 10], [10, 7], [6, 7], [1, 4], [2, 7],
    [5, 11, "nat"]
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
      fg: read("--fg", "#0B1F3A"),
      faint: read("--faint", "#5F7089"),
      surface: read("--surface", "#FFFFFF"),
      line: read("--line-strong", "#B9C7D6")
    };
  }

  function mesh(element, options) {
    var canvas = element.querySelector("canvas");
    if (!canvas || !canvas.getContext) { return; }
    var context = canvas.getContext("2d");
    var palette = colors();
    var width = 0;
    var height = 0;
    var started = null; // set when the mesh is first seen, so its tunnels come up in view
    var packets = [];
    var lastPacket = 0;
    var running = false;
    var visible = true;
    var frame = 0;
    var still = options.reduceMotion;
    var counter = element.querySelector("[data-mesh-count]");

    function resize() {
      var ratio = Math.min(window.devicePixelRatio || 1, 2);
      var box = canvas.getBoundingClientRect();
      width = box.width;
      height = box.height;
      canvas.width = Math.round(width * ratio);
      canvas.height = Math.round(height * ratio);
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      if (!running) { draw(settled()); }
    }

    // A frame with every tunnel up: for reduced motion, and before the mesh is seen
    function settled() {
      return still || started === null ? 1e6 : performance.now() - started;
    }

    function position(node, time) {
      var drift = still ? 0 : 1;
      var phase = node.x * 13 + node.y * 7;
      return {
        x: (node.x + drift * 0.012 * Math.sin(time / 2600 + phase)) * width,
        y: (node.y + drift * 0.014 * Math.cos(time / 3100 + phase)) * height
      };
    }

    function edgeProgress(index, time) {
      if (still) { return 1; }
      var begin = 300 + index * 220;
      return Math.max(0, Math.min(1, (time - begin) / 520));
    }

    function drawEdge(edge, index, time, points) {
      var progress = edgeProgress(index, time);
      if (progress <= 0) { return; }
      var a = points[edge[0]];
      var b = points[edge[1]];
      var nat = edge[2] === "nat";
      var x = a.x + (b.x - a.x) * progress;
      var y = a.y + (b.y - a.y) * progress;
      context.save();
      context.strokeStyle = nat ? palette.accent : palette.mesh;
      context.globalAlpha = nat ? 0.9 : 0.55;
      context.lineWidth = nat ? 1.6 : 1.3;
      if (nat) {
        context.setLineDash([6, 5]);
        context.lineDashOffset = still ? 0 : -time / 40;
      }
      context.beginPath();
      context.moveTo(a.x, a.y);
      context.lineTo(x, y);
      context.stroke();
      context.restore();
    }

    function drawNode(node, point, index, time) {
      var joined = EDGES.some(function (edge, e) {
        return (edge[0] === index || edge[1] === index) && edgeProgress(e, time) >= 1;
      });
      var radius = node.small ? 3.5 : 6;
      context.save();
      if (!node.small && joined && !still) {
        var pulse = (time / 1800 + index * 0.37) % 1;
        context.globalAlpha = 0.35 * (1 - pulse);
        context.fillStyle = node.nat ? palette.accent : palette.mesh;
        context.beginPath();
        context.arc(point.x, point.y, radius + 14 * pulse, 0, Math.PI * 2);
        context.fill();
      }
      context.globalAlpha = 1;
      context.fillStyle = palette.surface;
      context.strokeStyle = joined ? (node.nat ? palette.accent : palette.mesh) : palette.line;
      context.lineWidth = 2;
      context.beginPath();
      context.arc(point.x, point.y, radius, 0, Math.PI * 2);
      context.fill();
      context.stroke();
      if (!node.small) {
        context.fillStyle = joined ? (node.nat ? palette.accent : palette.mesh) : palette.line;
        context.beginPath();
        context.arc(point.x, point.y, 2.5, 0, Math.PI * 2);
        context.fill();
      }
      if (node.label && width > 300) {
        context.font = "600 " + (width < 460 ? 10 : 11) + "px ui-monospace, Menlo, Consolas, monospace";
        context.textAlign = node.x > 0.75 ? "right" : node.x < 0.2 ? "left" : "center";
        var dx = node.x > 0.75 ? 8 : node.x < 0.2 ? -8 : 0;
        var labelX = point.x + dx;
        var labelY = point.y + radius + 16;
        var textWidth = context.measureText(node.label).width;
        var left = context.textAlign === "right" ? labelX - textWidth :
          context.textAlign === "left" ? labelX : labelX - textWidth / 2;
        context.globalAlpha = 0.9;
        context.fillStyle = palette.surface;
        context.fillRect(left - 4, labelY - 11, textWidth + 8, 15);
        context.globalAlpha = 1;
        context.fillStyle = palette.faint;
        context.fillText(node.label, labelX, labelY);
      }
      context.restore();
    }

    function spawn(time) {
      var ready = EDGES.filter(function (edge, index) { return edgeProgress(index, time) >= 1; });
      if (!ready.length) { return; }
      var edge = ready[Math.floor(Math.random() * ready.length)];
      var forward = edge[2] === "nat" ? true : Math.random() > 0.5;
      packets.push({
        from: forward ? edge[0] : edge[1],
        to: forward ? edge[1] : edge[0],
        born: time,
        life: 1100 + Math.random() * 900,
        nat: edge[2] === "nat"
      });
    }

    function drawPackets(time, points) {
      packets = packets.filter(function (packet) { return time - packet.born < packet.life; });
      packets.forEach(function (packet) {
        var t = (time - packet.born) / packet.life;
        var eased = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
        var a = points[packet.from];
        var b = points[packet.to];
        var x = a.x + (b.x - a.x) * eased;
        var y = a.y + (b.y - a.y) * eased;
        context.save();
        context.fillStyle = packet.nat ? palette.accent : palette.mesh;
        context.shadowColor = context.fillStyle;
        context.shadowBlur = 10;
        context.beginPath();
        context.arc(x, y, 2.8, 0, Math.PI * 2);
        context.fill();
        context.restore();
      });
    }

    function draw(time) {
      context.clearRect(0, 0, width, height);
      var points = NODES.map(function (node) { return position(node, time); });
      EDGES.forEach(function (edge, index) { drawEdge(edge, index, time, points); });
      if (!still) { drawPackets(time, points); }
      NODES.forEach(function (node, index) { drawNode(node, points[index], index, time); });
      if (counter) {
        var up = EDGES.filter(function (edge, index) { return edgeProgress(index, time) >= 1; }).length;
        counter.textContent = up + "/" + EDGES.length + " tunnels up";
      }
    }

    function tick(now) {
      if (!running) { return; }
      var time = now - started;
      if (time - lastPacket > 260) {
        spawn(time);
        lastPacket = time;
      }
      draw(time);
      frame = window.requestAnimationFrame(tick);
    }

    function play() {
      if (still || running || !visible || document.hidden) { return; }
      if (started === null) { started = performance.now(); }
      running = true;
      frame = window.requestAnimationFrame(tick);
    }

    function pause() {
      running = false;
      window.cancelAnimationFrame(frame);
    }

    resize();
    if (window.ResizeObserver) {
      new ResizeObserver(resize).observe(canvas);
    } else {
      window.addEventListener("resize", resize);
    }
    document.addEventListener("keel:theme", function () {
      palette = colors();
      if (!running) { draw(settled()); }
    });
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (entries) {
        visible = entries[0].isIntersecting;
        if (visible) { play(); } else { pause(); }
      }).observe(canvas);
    }
    document.addEventListener("visibilitychange", function () {
      if (document.hidden) { pause(); } else { play(); }
    });
    if (still) { draw(1e6); } else { play(); }
  }

  window.KeelModules = window.KeelModules || {};
  window.KeelModules.mesh = mesh;
})();
