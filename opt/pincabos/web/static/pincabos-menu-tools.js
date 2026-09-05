(function () {
  "use strict";

  // PINCABOS_MENU_PIN_SIMPLE_V9
  // One menu, one DOM location, no overlay, no MutationObserver.
  var KEY = "pincabos_menu_force_pinned_v5";
  var NAV_SELECTOR = ".pincabos-nav";
  var PIN_CLASS = "pco-menu-pinned-v9";

  var bodyPaddingInline = null;
  var bodyPaddingBasePx = 0;
  var resizeTimer = null;

  function q(sel) {
    return document.querySelector(sel);
  }

  function getMenu() {
    return q(NAV_SELECTOR);
  }

  function getPinned() {
    try {
      return localStorage.getItem(KEY) === "1";
    } catch (e) {
      return false;
    }
  }

  function setPinnedStored(value) {
    try {
      localStorage.setItem(KEY, value ? "1" : "0");
    } catch (e) {}
  }

  function rememberBodyPadding() {
    if (!document.body || bodyPaddingInline !== null) return;
    bodyPaddingInline = document.body.style.paddingTop || "";
    var computed = window.getComputedStyle(document.body).paddingTop || "0";
    bodyPaddingBasePx = parseFloat(computed) || 0;
  }

  function menuHeight(menu) {
    if (!menu) return 0;
    var rect = menu.getBoundingClientRect();
    return Math.max(0, Math.ceil(rect.height || menu.offsetHeight || 0));
  }

  function updateBodyOffset() {
    var menu = getMenu();
    if (!document.body || !menu || !menu.classList.contains(PIN_CLASS)) return;
    var h = menuHeight(menu);
    document.body.style.paddingTop = Math.ceil(bodyPaddingBasePx + h) + "px";
    document.documentElement.style.setProperty("--pco-menu-pinned-offset", h + "px");
    document.body.classList.add("pco-menu-is-pinned");
  }

  function restoreBodyOffset() {
    if (!document.body) return;
    document.body.style.paddingTop = bodyPaddingInline !== null ? bodyPaddingInline : "";
    document.documentElement.style.setProperty("--pco-menu-pinned-offset", "0px");
    document.body.classList.remove("pco-menu-is-pinned");
  }

  function updatePinButton(pinned) {
    var btn = q("#pco-menu-pin-btn");
    if (!btn) return;

    btn.classList.toggle("pco-pinned", pinned);
    btn.textContent = pinned ? "📍" : "📌";
    btn.title = pinned ? "Menu épinglé" : "Épingler le menu";
    btn.setAttribute("aria-label", btn.title);
    btn.setAttribute("aria-pressed", pinned ? "true" : "false");
  }

  function applyPinnedState() {
    var menu = getMenu();
    var pinned = getPinned();

    updatePinButton(pinned);
    if (!menu) return false;

    rememberBodyPadding();
    menu.classList.toggle(PIN_CLASS, pinned);

    // Remove every legacy pin class left by V7/V8. No DOM move is performed.
    menu.classList.remove("pco-menu-force-fixed");
    menu.classList.remove("pco-menu-viewport-fixed-v7");
    menu.classList.remove("pco-menu-viewport-fixed-v8");

    // Remove legacy inline geometry/hit-testing written by V7/V8.
    [
      "position", "top", "left", "right", "bottom", "width", "max-width",
      "height", "min-height", "max-height", "margin", "z-index", "box-sizing",
      "overflow", "transform", "filter", "isolation", "pointer-events",
      "box-shadow", "border-bottom"
    ].forEach(function (prop) {
      menu.style.removeProperty(prop);
    });

    if (pinned) {
      updateBodyOffset();
    } else {
      restoreBodyOffset();
    }

    return pinned;
  }

  window.pcoMenuTogglePin = function (ev) {
    if (ev) {
      ev.preventDefault();
      ev.stopPropagation();
    }
    setPinnedStored(!getPinned());
    applyPinnedState();
    return false;
  };

  window.pcoMenuClosePage = function (ev) {
    if (ev) {
      ev.preventDefault();
      ev.stopPropagation();
    }

    fetch("/api/menu/close-tab", {
      method: "POST",
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      body: "{}"
    }).then(function (res) {
      if (res.ok) return;
      try { window.open("", "_self"); window.close(); } catch (e) {}
      setTimeout(function () {
        try { window.location.href = "about:blank"; } catch (e2) {}
      }, 150);
    }).catch(function () {
      try { window.open("", "_self"); window.close(); } catch (e) {}
      setTimeout(function () {
        try { window.location.href = "about:blank"; } catch (e2) {}
      }, 150);
    });

    return false;
  };

  function csrfFromPage() {
    if (window.PCO_LOBBY && window.PCO_LOBBY.csrf) {
      return String(window.PCO_LOBBY.csrf);
    }
    var input = q('input[name="csrf"]');
    return input && input.value ? String(input.value) : "";
  }

  function csrfFromHome() {
    var current = csrfFromPage();
    if (current) return Promise.resolve(current);

    return fetch("/", {
      method: "GET",
      credentials: "same-origin",
      cache: "no-store"
    }).then(function (res) {
      return res.text();
    }).then(function (body) {
      var match = body.match(/["']csrf["']\s*:\s*["']([^"']+)["']/i);
      return match ? match[1] : "";
    });
  }

  function submitShutdown(csrf) {
    var form = document.createElement("form");
    form.method = "POST";
    form.action = "/dashboard/control/service/system/shutdown";
    form.style.display = "none";

    var token = document.createElement("input");
    token.type = "hidden";
    token.name = "csrf";
    token.value = csrf;
    form.appendChild(token);
    document.body.appendChild(form);
    form.submit();
  }

  window.pcoMenuShutdown = function (ev) {
    if (ev) {
      ev.preventDefault();
      ev.stopPropagation();
    }

    if (!window.confirm("Éteindre complètement le PinCab maintenant ?")) return false;

    var button = q("#pco-menu-power-btn");
    if (button) button.disabled = true;

    csrfFromHome().then(function (csrf) {
      if (!csrf) throw new Error("Jeton de sécurité Dashboard introuvable.");
      submitShutdown(csrf);
    }).catch(function (error) {
      if (button) button.disabled = false;
      window.alert(
        "PinCabOS : arrêt impossible. " +
        (error && error.message ? error.message : "Erreur inconnue.")
      );
    });

    return false;
  };

  function ensurePowerButton() {
    var existing = q("#pco-menu-power-btn");
    if (existing) return existing;

    var tools = q(".pco-menu-tools");
    var closeBtn = q("#pco-menu-close-btn");
    if (!tools && closeBtn) tools = closeBtn.parentElement;
    if (!tools) return null;

    var button = document.createElement("button");
    button.type = "button";
    button.id = "pco-menu-power-btn";
    button.className = "pco-menu-tool-btn pco-menu-close-btn pco-menu-power-btn";
    button.textContent = "⏻";
    button.title = "Éteindre le PinCab";
    button.setAttribute("aria-label", "Éteindre le PinCab");
    button.onclick = window.pcoMenuShutdown;

    if (closeBtn && closeBtn.parentNode === tools) {
      tools.insertBefore(button, closeBtn);
    } else {
      tools.appendChild(button);
    }

    return button;
  }

  function boot() {
    rememberBodyPadding();
    ensurePowerButton();
    applyPinnedState();

    window.addEventListener("resize", function () {
      window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(function () {
        if (getPinned()) updateBodyOffset();
      }, 100);
    });

    window.addEventListener("pageshow", function () {
      applyPinnedState();
    });

    window.addEventListener("storage", function (event) {
      if (event && event.key === KEY) applyPinnedState();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();
