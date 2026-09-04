(function () {
  "use strict";

  // PINCABOS_MENU_PIN_PERSISTENT_V6
  // Keep the existing key so a user's current preference survives upgrades.
  var KEY = "pincabos_menu_force_pinned_v5";
  var originalCard = null;
  var originalCardElement = null;
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

  function cachedMenuCard() {
    if (
      originalCardElement &&
      originalCardElement.isConnected &&
      originalCardElement.querySelector &&
      originalCardElement.querySelector(".pco-menu-tools")
    ) {
      return originalCardElement;
    }
    return null;
  }

  function findFullMenuCard() {
    var cached = cachedMenuCard();
    if (cached) return cached;

    var tools = q(".pco-menu-tools");
    var about = q('a[href="/about"]');
    var anchor = tools || about;
    if (!anchor) return null;

    var candidates = [];
    var cur = anchor;
    while (cur && cur !== document.documentElement) {
      candidates.push(cur);
      cur = cur.parentElement;
    }

    var best = anchor.parentElement || anchor;
    var bestScore = -999999;
    var allowHidden = getPinned();

    candidates.forEach(function (el) {
      var isVisible = visible(el);
      if (!isVisible && !allowHidden) return;

      var r = el.getBoundingClientRect
        ? el.getBoundingClientRect()
        : { top: 0, width: 0, height: 0 };
      var t = txt(el).toLowerCase();
      var controls = el.querySelectorAll
        ? el.querySelectorAll("a,button,select,input").length
        : 0;
      var hasAbout = el.querySelector && el.querySelector('a[href="/about"]') ? 1 : 0;
      var hasTools = el.querySelector && el.querySelector(".pco-menu-tools") ? 1 : 0;
      var hasQuickAccess = /acc[eè]s rapides|quick access|ouvrir vpinfe|open vpinfe/i.test(t) ? 1 : 0;
      var hasLang = /lang|fr|en|english|français|francais/.test(t) ? 1 : 0;

      var score = 0;
      score += hasTools * 1600;
      score += hasAbout * 900;
      score += hasQuickAccess * 600;
      score += hasLang * 250;
      score += Math.min(controls, 40) * 20;
      score += Math.min(r.width || 0, window.innerWidth || r.width || 0) / 18;
      score += isVisible ? 100 : 0;
      score -= Math.max(0, (r.height || 0) - 240) * 8;
      score -= Math.abs(r.top || 0) * 2;
      if (el === document.body) score -= 10000;

      if (score > bestScore) {
        best = el;
        bestScore = score;
      }
    });

    return best;
  }

  function setOffset(px) {
    px = Math.max(0, Math.ceil(px || 0));
    document.documentElement.style.setProperty("--pco-menu-pinned-offset", px + "px");
    document.body.classList.toggle("pco-menu-is-pinned", px > 0);
  }

  function rememberCard(card) {
    if (!card) return;
    if (originalCard && originalCardElement === card) return;

    originalCardElement = card;
    originalCard = {
      position: card.style.position || "",
      top: card.style.top || "",
      left: card.style.left || "",
      right: card.style.right || "",
      width: card.style.width || "",
      maxWidth: card.style.maxWidth || "",
      zIndex: card.style.zIndex || "",
      boxShadow: card.style.boxShadow || "",
      borderBottom: card.style.borderBottom || "",
      bodyPaddingTop: document.body.style.paddingTop || ""
    };
  }

  function restoreCard(card) {
    card.classList.remove("pco-menu-force-fixed");

    if (originalCard && originalCardElement === card) {
      card.style.position = originalCard.position;
      card.style.top = originalCard.top;
      card.style.left = originalCard.left;
      card.style.right = originalCard.right;
      card.style.width = originalCard.width;
      card.style.maxWidth = originalCard.maxWidth;
      card.style.zIndex = originalCard.zIndex;
      card.style.boxShadow = originalCard.boxShadow;
      card.style.borderBottom = originalCard.borderBottom;
      document.body.style.paddingTop = originalCard.bodyPaddingTop;
    } else {
      document.body.style.paddingTop = "";
    }
  }

  function getMenuHeight(card) {
    if (!card) return 0;
    var h = card.offsetHeight || 0;
    if (!h && card.getBoundingClientRect) {
      h = Math.ceil(card.getBoundingClientRect().height || 0);
    }
    return h || 90;
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
      if (candidateLooksLikeIniHeader(el)) {
        var block = climbToIniBlock(el);
        if (block && found.indexOf(block) === -1) found.push(block);
      }
    });

    return found;
  }

  function rememberIni(el) {
    if (!iniOriginals.has(el)) {
      iniOriginals.set(el, {
        position: el.style.position || "",
        top: el.style.top || "",
        zIndex: el.style.zIndex || "",
        boxShadow: el.style.boxShadow || "",
        background: el.style.background || ""
      });
    }
  }

  function forceIniOffset(menuHeight) {
    var blocks = findIniBlocks();
    var top = Math.max(0, menuHeight + 12);

    blocks.forEach(function (el) {
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

  function enforcePinnedState() {
    var pinned = getPinned();
    var card = findFullMenuCard();

    setPinButtonVisual(pinned);

    if (!card) {
      if (!pinned) {
        setOffset(0);
        clearIniOffset();
      }
      return false;
    }

    rememberCard(card);

    if (pinned) {
      // The CSS class owns the fixed geometry with !important declarations.
      // Add it first, then measure the final wrapped height for body offset.
      card.classList.add("pco-menu-force-fixed");
      var h = getMenuHeight(card);
      document.body.style.paddingTop = h + "px";
      setOffset(h);
      forceIniOffset(h);
      return true;
    }

    restoreCard(card);
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
      setTimeout(function () { try { window.location.href = "about:blank"; } catch (e2) {} }, 150);
    }).catch(function () {
      try { window.open("", "_self"); window.close(); } catch (e) {}
      setTimeout(function () { try { window.location.href = "about:blank"; } catch (e2) {} }, 150);
    });
    return false;
  };

  function csrfFromPage() {
    if (window.PCO_LOBBY && window.PCO_LOBBY.csrf) return String(window.PCO_LOBBY.csrf);
    var input = q('input[name="csrf"]');
    return input && input.value ? String(input.value) : "";
  }

  function csrfFromHome() {
    var current = csrfFromPage();
    if (current) return Promise.resolve(current);

    return fetch("/", { method: "GET", credentials: "same-origin", cache: "no-store" })
      .then(function (res) { return res.text(); })
      .then(function (body) {
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
      window.alert("PinCabOS : arrêt impossible. " + (error && error.message ? error.message : "Erreur inconnue."));
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
          mutation.addedNodes.length > 0 ||
          mutation.removedNodes.length > 0
        );
      });

      if (relevant) scheduleSync(40);
    });

    // Only observe DOM structure. We deliberately ignore attributes/styles so
    // applying the pinned class does not create an observer feedback loop.
    observer.observe(document.body, {
      childList: true,
      subtree: true
    });
  }

  function boot() {
    // Read localStorage and apply the pinned state immediately on every page.
    syncMenuTools();
    observeMenuChanges();

    window.addEventListener("resize", function () {
      window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(syncMenuTools, 80);
    });

    window.addEventListener("pageshow", function () {
      scheduleSync(0);
    });

    window.addEventListener("storage", function (event) {
      if (event && event.key === KEY) scheduleSync(0);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
