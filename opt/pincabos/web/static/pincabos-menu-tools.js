(function () {
  "use strict";

  // PINCABOS_MENU_PIN_PERSISTENT_V7
  // Keep the historical key so the user's preference survives upgrades.
  var KEY = "pincabos_menu_force_pinned_v5";
  var NAV_SELECTOR = "nav.pincabos-nav, .pincabos-nav";
  var VIEWPORT_CLASS = "pco-menu-viewport-fixed-v7";

  var originalMenu = null;
  var originalMenuElement = null;
  var originalParent = null;
  var originalNextSibling = null;
  var originalBodyPaddingTop = null;
  var placeholder = null;
  var iniOriginals = new WeakMap();
  var observer = null;
  var syncTimer = null;
  var resizeTimer = null;

  function q(sel) {
    return document.querySelector(sel);
  }

  function qa(sel) {
    return Array.prototype.slice.call(document.querySelectorAll(sel));
  }

  function stop(ev) {
    if (!ev) return;
    ev.preventDefault();
    ev.stopPropagation();
    if (ev.stopImmediatePropagation) ev.stopImmediatePropagation();
  }

  function txt(el) {
    return ((el && el.textContent) || "").replace(/\s+/g, " ").trim();
  }

  function visible(el) {
    if (!el || !el.getBoundingClientRect) return false;
    var r = el.getBoundingClientRect();
    return r.width > 80 && r.height > 20;
  }

  function getPinned() {
    try { return localStorage.getItem(KEY) === "1"; }
    catch (e) { return false; }
  }

  function setPinnedStored(v) {
    try { localStorage.setItem(KEY, v ? "1" : "0"); }
    catch (e) {}
  }

  function findMenu() {
    return q(NAV_SELECTOR);
  }

  function setOffset(px) {
    px = Math.max(0, Math.ceil(px || 0));
    document.documentElement.style.setProperty("--pco-menu-pinned-offset", px + "px");
    if (document.body) {
      document.body.classList.toggle("pco-menu-is-pinned", px > 0);
    }
  }

  function rememberMenu(menu) {
    if (!menu || (originalMenu && originalMenuElement === menu)) return;

    originalMenuElement = menu;
    originalParent = menu.parentNode || null;
    originalNextSibling = menu.nextSibling || null;
    originalBodyPaddingTop = document.body ? (document.body.style.paddingTop || "") : "";

    originalMenu = {};
    [
      "position",
      "top",
      "left",
      "right",
      "bottom",
      "width",
      "max-width",
      "margin",
      "z-index",
      "box-sizing",
      "box-shadow",
      "border-bottom"
    ].forEach(function (prop) {
      originalMenu[prop] = {
        value: menu.style.getPropertyValue(prop),
        priority: menu.style.getPropertyPriority(prop)
      };
    });
  }

  function restoreMenuStyles(menu) {
    if (!menu || !originalMenu || originalMenuElement !== menu) return;

    Object.keys(originalMenu).forEach(function (prop) {
      var state = originalMenu[prop];
      if (state.value) {
        menu.style.setProperty(prop, state.value, state.priority || "");
      } else {
        menu.style.removeProperty(prop);
      }
    });
  }

  function detachMenuToViewportRoot(menu) {
    if (!menu || !document.body || menu.parentNode === document.body) return;

    if (!placeholder || !placeholder.parentNode) {
      placeholder = document.createComment("pincabos-menu-pin-v7-placeholder");
      if (menu.parentNode) menu.parentNode.insertBefore(placeholder, menu);
    }

    document.body.appendChild(menu);
  }

  function restoreMenuPlacement(menu) {
    if (!menu) return;

    if (placeholder && placeholder.parentNode) {
      placeholder.parentNode.insertBefore(menu, placeholder);
      placeholder.parentNode.removeChild(placeholder);
      placeholder = null;
      return;
    }

    if (originalParent && originalParent.isConnected) {
      if (originalNextSibling && originalNextSibling.parentNode === originalParent) {
        originalParent.insertBefore(menu, originalNextSibling);
      } else {
        originalParent.appendChild(menu);
      }
    }
  }

  function getMenuHeight(menu) {
    if (!menu) return 0;
    var rect = menu.getBoundingClientRect ? menu.getBoundingClientRect() : null;
    var h = rect ? rect.height : 0;
    h = h || menu.offsetHeight || menu.scrollHeight || 0;
    return Math.max(0, Math.ceil(h || 90));
  }

  function clearWrongFixedTargets(menu) {
    qa(".pco-menu-force-fixed").forEach(function (el) {
      if (el !== menu) el.classList.remove("pco-menu-force-fixed");
    });
  }

  function candidateLooksLikeIniHeader(el) {
    if (!visible(el)) return false;

    var t = txt(el).toLowerCase();
    var hasIniWords =
      t.indexOf("navigation") !== -1 ||
      t.indexOf("safe editor") !== -1 ||
      t.indexOf("filter a section") !== -1 ||
      t.indexOf("reset filter") !== -1 ||
      t.indexOf("save approved changes") !== -1 ||
      t.indexOf("last modified") !== -1;

    if (!hasIniWords) return false;

    var r = el.getBoundingClientRect();
    if (r.top > 420) return false;
    if (r.height > 420) return false;
    return true;
  }

  function climbToIniBlock(el) {
    var best = el;
    var cur = el;

    while (cur && cur !== document.body && cur !== document.documentElement) {
      if (!visible(cur)) break;

      var r = cur.getBoundingClientRect();
      var t = txt(cur).toLowerCase();
      if (
        r.top < 420 &&
        r.height < 520 &&
        (
          t.indexOf("navigation") !== -1 ||
          t.indexOf("safe editor") !== -1 ||
          t.indexOf("filter a section") !== -1 ||
          t.indexOf("save approved changes") !== -1
        )
      ) {
        best = cur;
      }
      cur = cur.parentElement;
    }

    return best;
  }

  function findIniBlocks() {
    var found = [];
    qa("div,section,aside,nav,header,form").forEach(function (el) {
      if (!candidateLooksLikeIniHeader(el)) return;
      var block = climbToIniBlock(el);
      if (block && found.indexOf(block) === -1) found.push(block);
    });
    return found;
  }

  function rememberIni(el) {
    if (iniOriginals.has(el)) return;
    iniOriginals.set(el, {
      position: el.style.position || "",
      top: el.style.top || "",
      zIndex: el.style.zIndex || "",
      boxShadow: el.style.boxShadow || "",
      background: el.style.background || ""
    });
  }

  function forceIniOffset(menuHeight) {
    var top = Math.max(0, menuHeight + 12);
    findIniBlocks().forEach(function (el) {
      if (el === findMenu()) return;
      rememberIni(el);
      el.classList.add("pco-ini-offset-forced");
      el.style.position = "sticky";
      el.style.top = top + "px";
      el.style.zIndex = "2147482500";
      el.style.boxShadow = "0 8px 18px rgba(0,0,0,.35)";
      if (!el.style.background) el.style.background = "inherit";
    });
  }

  function clearIniOffset() {
    qa(".pco-ini-offset-forced").forEach(function (el) {
      var o = iniOriginals.get(el);
      el.classList.remove("pco-ini-offset-forced");
      if (o) {
        el.style.position = o.position;
        el.style.top = o.top;
        el.style.zIndex = o.zIndex;
        el.style.boxShadow = o.boxShadow;
        el.style.background = o.background;
      } else {
        el.style.position = "";
        el.style.top = "";
        el.style.zIndex = "";
        el.style.boxShadow = "";
        el.style.background = "";
      }
    });
  }

  function setPinButtonVisual(v) {
    var pinBtn = q("#pco-menu-pin-btn");
    if (!pinBtn) return;

    if (v) {
      pinBtn.classList.add("pco-pinned");
      pinBtn.textContent = "📍";
      pinBtn.title = "Menu complet épinglé";
      pinBtn.setAttribute("aria-label", "Menu complet épinglé");
      pinBtn.setAttribute("aria-pressed", "true");
    } else {
      pinBtn.classList.remove("pco-pinned");
      pinBtn.textContent = "📌";
      pinBtn.title = "Épingler le menu complet";
      pinBtn.setAttribute("aria-label", "Épingler le menu complet");
      pinBtn.setAttribute("aria-pressed", "false");
    }
  }

  function applyViewportGeometry(menu) {
    clearWrongFixedTargets(menu);
    detachMenuToViewportRoot(menu);

    menu.classList.add("pco-menu-force-fixed");
    menu.classList.add(VIEWPORT_CLASS);

    // Inline !important wins against page-specific legacy CSS.
    menu.style.setProperty("position", "fixed", "important");
    menu.style.setProperty("top", "0", "important");
    menu.style.setProperty("left", "0", "important");
    menu.style.setProperty("right", "0", "important");
    menu.style.setProperty("bottom", "auto", "important");
    menu.style.setProperty("width", "100vw", "important");
    menu.style.setProperty("max-width", "none", "important");
    menu.style.setProperty("margin", "0", "important");
    menu.style.setProperty("z-index", "2147482999", "important");
    menu.style.setProperty("box-sizing", "border-box", "important");
  }

  function enforcePinnedState() {
    var pinned = getPinned();
    var menu = findMenu();

    setPinButtonVisual(pinned);

    if (!menu) {
      if (!pinned) {
        setOffset(0);
        clearIniOffset();
      }
      return false;
    }

    rememberMenu(menu);

    if (pinned) {
      applyViewportGeometry(menu);
      var h = getMenuHeight(menu);
      if (document.body) document.body.style.paddingTop = h + "px";
      setOffset(h);
      forceIniOffset(h);
      return true;
    }

    menu.classList.remove(VIEWPORT_CLASS);
    menu.classList.remove("pco-menu-force-fixed");
    restoreMenuStyles(menu);
    restoreMenuPlacement(menu);

    if (document.body) {
      document.body.style.paddingTop = originalBodyPaddingTop !== null
        ? originalBodyPaddingTop
        : "";
    }
    setOffset(0);
    clearIniOffset();
    return false;
  }

  function applyPinned(v) {
    setPinnedStored(v);
    enforcePinnedState();
    return false;
  }

  function bindSingleClick(btn, handler) {
    if (!btn) return btn;
    if (btn.getAttribute("data-pco-menu-bound") === "1") return btn;
    btn.removeAttribute("onclick");
    btn.addEventListener("click", handler, true);
    btn.setAttribute("data-pco-menu-bound", "1");
    return btn;
  }

  window.pcoMenuTogglePin = function (ev) {
    stop(ev);
    return applyPinned(!getPinned());
  };

  window.pcoMenuClosePage = function (ev) {
    stop(ev);
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
    stop(ev);
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

    if (closeBtn && closeBtn.parentNode === tools) tools.insertBefore(button, closeBtn);
    else tools.appendChild(button);
    return button;
  }

  function syncMenuTools() {
    bindSingleClick(q("#pco-menu-pin-btn"), window.pcoMenuTogglePin);
    bindSingleClick(q("#pco-menu-close-btn"), window.pcoMenuClosePage);
    bindSingleClick(ensurePowerButton(), window.pcoMenuShutdown);
    enforcePinnedState();
  }

  function scheduleSync(delay) {
    window.clearTimeout(syncTimer);
    syncTimer = window.setTimeout(syncMenuTools, delay || 0);
  }

  function observeMenuChanges() {
    if (observer || !window.MutationObserver || !document.body) return;

    observer = new MutationObserver(function (mutations) {
      var relevant = mutations.some(function (mutation) {
        return mutation.type === "childList" && (
          mutation.addedNodes.length > 0 || mutation.removedNodes.length > 0
        );
      });

      // The move to <body> itself produces mutations. Delay the sync so DOM
      // settles; attributes are deliberately ignored to avoid a feedback loop.
      if (relevant) scheduleSync(70);
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true
    });
  }

  function boot() {
    syncMenuTools();
    observeMenuChanges();

    window.addEventListener("resize", function () {
      window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(syncMenuTools, 120);
    });

    window.addEventListener("pageshow", function () {
      scheduleSync(20);
    });

    window.addEventListener("storage", function (event) {
      if (event && event.key === KEY) scheduleSync(20);
    });

    // Win against late Dashboard scripts that rewrite menu geometry.
    window.setTimeout(syncMenuTools, 160);
    window.setTimeout(syncMenuTools, 600);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
