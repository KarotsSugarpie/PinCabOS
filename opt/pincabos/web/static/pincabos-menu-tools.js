(function () {
  "use strict";

  // PINCABOS_MENU_PIN_HEADER_V11
  // One header, one DOM location, no clone/reparenting and no body padding.
  // A tiny inert spacer preserves document flow only while the header is fixed.
  var KEY = "pincabos_menu_force_pinned_v5";
  var NAV_SELECTOR = ".pincabos-nav";
  var HEADER_SELECTOR = ".top";
  var PIN_CLASS = "pco-menu-pinned-v11";
  var HEADER_PIN_CLASS = "pco-header-pinned-v11";
  var SPACER_ID = "pco-header-pin-spacer-v11";

  var resizeTimer = null;
  var settleTimer = null;
  var headerInlineBackup = null;
  var observedHeader = null;
  var resizeObserver = null;

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

  function elementHeight(el) {
    if (!el) return 0;
    var rect = el.getBoundingClientRect();
    return Math.max(0, Math.ceil(rect.height || el.offsetHeight || 0));
  }

  function captureHeaderInline(header) {
    if (!header || headerInlineBackup) return;

    var props = [
      "position", "top", "left", "right", "bottom", "width", "max-width",
      "margin", "transform", "z-index", "box-sizing", "pointer-events"
    ];

    headerInlineBackup = {};
    props.forEach(function (prop) {
      headerInlineBackup[prop] = {
        value: header.style.getPropertyValue(prop),
        priority: header.style.getPropertyPriority(prop)
      };
    });
  }

  function restoreHeaderInline(header) {
    if (!header) return;

    if (!headerInlineBackup) {
      [
        "position", "top", "left", "right", "bottom", "width", "max-width",
        "margin", "transform", "z-index", "box-sizing", "pointer-events"
      ].forEach(function (prop) {
        header.style.removeProperty(prop);
      });
      return;
    }

    Object.keys(headerInlineBackup).forEach(function (prop) {
      var saved = headerInlineBackup[prop];
      if (saved && saved.value) {
        header.style.setProperty(prop, saved.value, saved.priority || "");
      } else {
        header.style.removeProperty(prop);
      }
    });
  }

  function forceHeaderFixed(header) {
    if (!header) return;

    captureHeaderInline(header);

    header.style.setProperty("position", "fixed", "important");
    header.style.setProperty("top", "0", "important");
    header.style.setProperty("left", "50%", "important");
    header.style.setProperty("right", "auto", "important");
    header.style.setProperty("bottom", "auto", "important");
    header.style.setProperty(
      "width",
      "var(--pco-content-rail-width, calc(100vw - 60px))",
      "important"
    );
    header.style.setProperty(
      "max-width",
      "var(--pco-content-rail-width, calc(100vw - 60px))",
      "important"
    );
    header.style.setProperty("margin", "0", "important");
    header.style.setProperty("transform", "translateX(-50%)", "important");
    header.style.setProperty("z-index", "5000", "important");
    header.style.setProperty("box-sizing", "border-box", "important");
    header.style.setProperty("pointer-events", "auto", "important");

    if (window.matchMedia && window.matchMedia("(max-width: 850px)").matches) {
      header.style.setProperty("left", "0", "important");
      header.style.setProperty("right", "0", "important");
      header.style.setProperty("width", "100vw", "important");
      header.style.setProperty("max-width", "100vw", "important");
      header.style.setProperty("transform", "none", "important");
    }
  }

  function clearLegacyBodyOffset() {
    if (!document.body) return;

    // V9/V10 used body padding as the flow offset. V11 does not.
    document.body.classList.remove("pco-menu-is-pinned");
    document.documentElement.style.setProperty("--pco-menu-pinned-offset", "0px");

    // Only remove the inline padding written by the previous pinning stack.
    if (document.body.style.paddingTop) {
      document.body.style.removeProperty("padding-top");
    }
  }

  function clearLegacyGeometry(menu, header) {
    if (menu) {
      [
        "pco-menu-force-fixed",
        "pco-menu-viewport-fixed-v7",
        "pco-menu-viewport-fixed-v8",
        "pco-menu-pinned-v9",
        "pco-menu-pinned-v10"
      ].forEach(function (name) {
        menu.classList.remove(name);
      });

      [
        "position", "top", "left", "right", "bottom", "width", "max-width",
        "height", "min-height", "max-height", "margin", "z-index", "box-sizing",
        "overflow", "transform", "filter", "isolation", "pointer-events",
        "box-shadow", "border-bottom"
      ].forEach(function (prop) {
        menu.style.removeProperty(prop);
      });
    }

    if (header) {
      header.classList.remove("pco-header-pinned-v10");
    }
  }

  function ensureSpacer(header) {
    if (!header || !header.parentNode) return null;

    var spacer = q("#" + SPACER_ID);
    if (!spacer) {
      spacer = document.createElement("div");
      spacer.id = SPACER_ID;
      spacer.className = "pco-header-pin-spacer-v11";
      spacer.setAttribute("aria-hidden", "true");
      header.parentNode.insertBefore(spacer, header);
    }

    return spacer;
  }

  function removeSpacer() {
    var spacer = q("#" + SPACER_ID);
    if (spacer && spacer.parentNode) {
      spacer.parentNode.removeChild(spacer);
    }
  }

  function updateSpacer() {
    var header = getHeader();
    var spacer = q("#" + SPACER_ID);

    if (!getPinned() || !header || !spacer) return;

    var computed = window.getComputedStyle(header);
    var h = elementHeight(header);

    // Header is fixed with margin:0, so preserve the normal 12px bottom flow
    // from the original .top rule explicitly.
    var normalMargin = 0;
    if (headerInlineBackup && headerInlineBackup.margin && headerInlineBackup.margin.value) {
      normalMargin = px(headerInlineBackup.margin.value);
    } else {
      // The normal PinCabOS header has a 12px bottom margin.
      normalMargin = 12;
    }

    // If a stylesheet supplies a larger vertical margin, keep it.
    normalMargin = Math.max(
      normalMargin,
      px(computed.marginTop) + px(computed.marginBottom)
    );

    spacer.style.height = Math.max(0, Math.ceil(h + normalMargin)) + "px";
  }

  function keepControlsInteractive(root) {
    if (!root) return;

    root.style.setProperty("pointer-events", "auto", "important");
    root.querySelectorAll("a, button, select, input, form, label").forEach(function (el) {
      el.style.setProperty("pointer-events", "auto", "important");
    });
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

  function settlePinnedLayout() {
    window.clearTimeout(settleTimer);
    if (!getPinned()) return;

    if (typeof window.requestAnimationFrame === "function") {
      window.requestAnimationFrame(function () {
        if (!getPinned()) return;
        forceHeaderFixed(getHeader());
        updateSpacer();
      });
    }

    settleTimer = window.setTimeout(function () {
      if (!getPinned()) return;
      forceHeaderFixed(getHeader());
      updateSpacer();
    }, 120);
  }

  function observeHeader(header) {
    if (!header || observedHeader === header) return;

    if (resizeObserver) {
      try { resizeObserver.disconnect(); } catch (e) {}
      resizeObserver = null;
    }

    observedHeader = header;

    if (typeof window.ResizeObserver === "function") {
      resizeObserver = new ResizeObserver(function () {
        if (getPinned()) updateSpacer();
      });
      resizeObserver.observe(header);
    }
  }

  function applyPinnedState() {
    var menu = getMenu();
    var header = getHeader();
    var pinned = getPinned();

    updatePinButton(pinned);
    if (!menu || !header) return false;

    captureHeaderInline(header);
    observeHeader(header);
    clearLegacyGeometry(menu, header);
    clearLegacyBodyOffset();

    if (pinned) {
      var spacer = ensureSpacer(header);
      if (spacer) spacer.style.display = "block";

      menu.classList.add(PIN_CLASS);
      header.classList.add(HEADER_PIN_CLASS);

      forceHeaderFixed(header);
      keepControlsInteractive(menu);
      keepControlsInteractive(header);
      updateSpacer();
      settlePinnedLayout();
    } else {
      window.clearTimeout(settleTimer);

      menu.classList.remove(PIN_CLASS);
      header.classList.remove(HEADER_PIN_CLASS);

      restoreHeaderInline(header);
      removeSpacer();

      keepControlsInteractive(menu);
      keepControlsInteractive(header);
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
    clearLegacyBodyOffset();
    ensurePowerButton();
    applyPinnedState();

    window.addEventListener("resize", function () {
      window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(function () {
        applyPinnedState();
      }, 100);
    });

    window.addEventListener("pageshow", function () {
      applyPinnedState();
    });

    window.addEventListener("storage", function (event) {
      if (event && event.key === KEY) applyPinnedState();
    });

    // pincabos-header-final.js moves Language into .top on DOMContentLoaded.
    // Re-measure after that final DOM composition without observing mutations.
    window.setTimeout(function () {
      if (getPinned()) {
        forceHeaderFixed(getHeader());
        updateSpacer();
      }
    }, 250);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();
