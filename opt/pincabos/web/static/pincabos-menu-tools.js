(function () {
  "use strict";

  // PINCABOS_MENU_PIN_HEADER_V10
  // One header, one DOM location, no clone/reparenting/overlay.
  var KEY = "pincabos_menu_force_pinned_v5";
  var NAV_SELECTOR = ".pincabos-nav";
  var HEADER_SELECTOR = ".top";
  var PIN_CLASS = "pco-menu-pinned-v10";
  var HEADER_PIN_CLASS = "pco-header-pinned-v10";

  var bodyPaddingInline = null;
  var bodyPaddingBasePx = 0;
  var headerFlowMarginPx = 0;
  var layoutRemembered = false;
  var resizeTimer = null;
  var settleTimer = null;

  function q(sel) {
    return document.querySelector(sel);
  }

  function getMenu() {
    return q(NAV_SELECTOR);
  }

  function getHeader() {
    var menu = getMenu();
    if (menu && typeof menu.closest === "function") {
      var closestHeader = menu.closest(HEADER_SELECTOR);
      if (closestHeader) return closestHeader;
    }
    return q(HEADER_SELECTOR);
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

  function px(value) {
    var n = parseFloat(value || "0");
    return Number.isFinite(n) ? n : 0;
  }

  function rememberLayoutBase() {
    if (layoutRemembered || !document.body) return;

    bodyPaddingInline = document.body.style.paddingTop || "";
    bodyPaddingBasePx = px(window.getComputedStyle(document.body).paddingTop);

    var header = getHeader();
    if (header) {
      var computed = window.getComputedStyle(header);
      headerFlowMarginPx = px(computed.marginTop) + px(computed.marginBottom);
    }

    layoutRemembered = true;
  }

  function elementHeight(el) {
    if (!el) return 0;
    var rect = el.getBoundingClientRect();
    return Math.max(0, Math.ceil(rect.height || el.offsetHeight || 0));
  }

  function updateBodyOffset() {
    var header = getHeader();
    if (!document.body || !header || !header.classList.contains(HEADER_PIN_CLASS)) return;

    var h = Math.max(0, Math.ceil(elementHeight(header) + headerFlowMarginPx));
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
    btn.title = pinned ? "Désépingler le menu" : "Épingler le menu";
    btn.setAttribute("aria-label", btn.title);
    btn.setAttribute("aria-pressed", pinned ? "true" : "false");
  }

  function clearLegacyMenuGeometry(menu) {
    if (!menu) return;

    menu.classList.remove("pco-menu-force-fixed");
    menu.classList.remove("pco-menu-viewport-fixed-v7");
    menu.classList.remove("pco-menu-viewport-fixed-v8");
    menu.classList.remove("pco-menu-pinned-v9");

    [
      "position", "top", "left", "right", "bottom", "width", "max-width",
      "height", "min-height", "max-height", "margin", "z-index", "box-sizing",
      "overflow", "transform", "filter", "isolation", "pointer-events",
      "box-shadow", "border-bottom"
    ].forEach(function (prop) {
      menu.style.removeProperty(prop);
    });
  }

  function keepControlsInteractive(root) {
    if (!root) return;

    root.style.removeProperty("pointer-events");
    root.querySelectorAll("a, button, select, input, form, label").forEach(function (el) {
      el.style.removeProperty("pointer-events");
    });
  }

  function settlePinnedLayout() {
    window.clearTimeout(settleTimer);
    if (!getPinned()) return;

    if (typeof window.requestAnimationFrame === "function") {
      window.requestAnimationFrame(function () {
        if (getPinned()) updateBodyOffset();
      });
    }

    settleTimer = window.setTimeout(function () {
      if (getPinned()) updateBodyOffset();
    }, 80);
  }

  function applyPinnedState() {
    var menu = getMenu();
    var header = getHeader();
    var pinned = getPinned();

    updatePinButton(pinned);
    if (!menu || !header) return false;

    rememberLayoutBase();
    clearLegacyMenuGeometry(menu);

    menu.classList.toggle(PIN_CLASS, pinned);
    header.classList.toggle(HEADER_PIN_CLASS, pinned);

    keepControlsInteractive(menu);
    keepControlsInteractive(header);

    if (pinned) {
      updateBodyOffset();
      settlePinnedLayout();
    } else {
      window.clearTimeout(settleTimer);
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
    rememberLayoutBase();
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
