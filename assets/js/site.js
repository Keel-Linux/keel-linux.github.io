/* Keel Linux site: theme, navigation, scroll reveal and lazy modules.
   Vanilla JavaScript, no dependencies. Every page works without it. */
(function () {
  "use strict";

  var root = document.documentElement;
  var reduceMotion = window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  window.KeelModules = window.KeelModules || {};
  window.keelReady = true;

  /* Theme toggle. The stored choice is read before paint by the inline
     script in each page's head; this only switches and remembers it. */
  function initTheme() {
    var button = document.getElementById("theme-toggle");
    if (!button || !window.matchMedia) { return; }
    var query = window.matchMedia("(prefers-color-scheme: dark)");

    function current() {
      var set = root.getAttribute("data-theme");
      if (set === "light" || set === "dark") { return set; }
      return query.matches ? "dark" : "light";
    }

    function describe() {
      var next = current() === "dark" ? "light" : "dark";
      button.setAttribute("aria-label", "Switch to " + next + " theme");
      button.title = "Switch to " + next + " theme";
    }

    button.addEventListener("click", function () {
      var next = current() === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("keel-theme", next); } catch (e) { /* private mode */ }
      describe();
      document.dispatchEvent(new CustomEvent("keel:theme"));
    });

    if (query.addEventListener) {
      query.addEventListener("change", function () {
        describe();
        document.dispatchEvent(new CustomEvent("keel:theme"));
      });
    }
    describe();
    button.hidden = false;
  }

  /* The menu button on narrow screens */
  function initNav() {
    var button = document.getElementById("nav-toggle");
    var nav = document.getElementById("site-nav");
    if (!button || !nav) { return; }

    function set(open) {
      nav.classList.toggle("is-open", open);
      button.setAttribute("aria-expanded", open ? "true" : "false");
      button.setAttribute("aria-label", open ? "Close menu" : "Open menu");
    }

    button.addEventListener("click", function () {
      set(button.getAttribute("aria-expanded") !== "true");
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && nav.classList.contains("is-open")) {
        set(false);
        button.focus();
      }
    });
    nav.addEventListener("click", function (event) {
      if (event.target.closest("a")) { set(false); }
    });
    button.hidden = false;
  }

  /* Scroll reveal: elements marked data-reveal fade in once */
  function initReveal() {
    var items = document.querySelectorAll("[data-reveal]");
    if (!root.classList.contains("js-motion") || !("IntersectionObserver" in window)) {
      items.forEach(function (item) { item.classList.add("is-in"); });
      return;
    }
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-in");
          observer.unobserve(entry.target);
        }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
    items.forEach(function (item) { observer.observe(item); });
  }

  /* Lazy modules: an element with data-module and data-src loads its script
     only when it comes near the viewport, then the module starts on it. */
  var loaded = {};

  function start(name, element) {
    var module = window.KeelModules[name];
    if (typeof module !== "function" || element.dataset.started) { return; }
    element.dataset.started = "1";
    try {
      module(element, { reduceMotion: reduceMotion });
    } catch (error) {
      if (window.console) { window.console.error("keel module " + name, error); }
    }
  }

  function load(element) {
    var name = element.getAttribute("data-module");
    var src = element.getAttribute("data-src");
    if (!name || !src) { return; }
    if (loaded[src] === true) { start(name, element); return; }
    if (loaded[src]) { loaded[src].push(element); return; }
    loaded[src] = [element];
    var script = document.createElement("script");
    script.src = src;
    script.async = true;
    script.onload = function () {
      var waiting = loaded[src];
      loaded[src] = true;
      waiting.forEach(function (item) { start(name, item); });
    };
    script.onerror = function () {
      if (window.console) { window.console.error("keel: could not load " + src); }
    };
    document.head.appendChild(script);
  }

  function initModules() {
    var elements = document.querySelectorAll("[data-module][data-src]");
    if (!("IntersectionObserver" in window)) {
      elements.forEach(load);
      return;
    }
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          observer.unobserve(entry.target);
          load(entry.target);
        }
      });
    }, { rootMargin: "300px 0px" });
    elements.forEach(function (element) { observer.observe(element); });
  }

  /* Contents column: mark the section being read */
  function initToc() {
    var links = document.querySelectorAll(".toc a[href^='#']");
    if (!links.length || !("IntersectionObserver" in window)) { return; }
    var byId = {};
    links.forEach(function (link) { byId[link.getAttribute("href").slice(1)] = link; });
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) { return; }
        links.forEach(function (link) { link.classList.remove("is-active"); });
        var link = byId[entry.target.id];
        if (link) { link.classList.add("is-active"); }
      });
    }, { rootMargin: "-20% 0px -70% 0px" });
    Object.keys(byId).forEach(function (id) {
      var section = document.getElementById(id);
      if (section) { observer.observe(section); }
    });
  }

  /* Roadmap: show every task, only the open ones, or only the done ones */
  function initFilters() {
    var group = document.querySelector("[data-filters]");
    if (!group) { return; }
    var buttons = group.querySelectorAll("button");
    var lists = document.querySelectorAll(".tasks");
    buttons.forEach(function (button) {
      button.addEventListener("click", function () {
        var mode = button.getAttribute("data-filter");
        buttons.forEach(function (other) {
          other.setAttribute("aria-pressed", other === button ? "true" : "false");
        });
        lists.forEach(function (list) {
          list.classList.toggle("only-open", mode === "open");
          list.classList.toggle("only-done", mode === "done");
        });
      });
    });
    group.hidden = false;
  }

  initTheme();
  initNav();
  initReveal();
  initModules();
  initToc();
  initFilters();
})();
