(function () {
  "use strict";

  /*
   * PINCABOS_MENU_PIN_VIEWPORT_V7
   *
   * Correctif de geometrie uniquement. Le moteur historique
   * pincabos-menu-tools.js garde la preference, le bouton, les actions et les
   * offsets INI. Cette couche garantit que, quand l'option est activee, le
   * menu principal .pincabos-nav est REELLEMENT fixe au viewport.
   *
   * Le menu epingle est temporairement rattache directement au <body>. Ainsi,
   * aucun parent avec transform/filter/overflow ne peut creer un containing
   * block qui ferait suivre le menu avec le scroll. Un marqueur conserve sa
   * place exacte pour le remettre au meme endroit au desepinglage.
   */

  var KEY = "pincabos_menu_force_pinned_v5";
  var NAV_SELECTOR = "nav.pincabos-nav, .pincabos-nav";
  var ownedClass = "pco-menu-viewport-fixed-v7";
  var observer = null;
  var syncTimer = null;
  var resizeTimer = null;
  var originalStyles = null;
  var originalNav = null;
  var originalParent = null;
  var originalNextSibling = null;
  var originalBodyPaddingTop = null;
  var placeholder = null;

  function pinned() {
    try {
      return window.localStorage.getItem(KEY) === "1";
    } catch (e) {
      return false;
    }
  }

  function nav() {
    return document.querySelector(NAV_SELECTOR);
  }

  function rememberState(el) {
    if (!el || (originalStyles && originalNav === el)) return;

    originalNav = el;
    originalStyles = {};
    originalParent = el.parentNode || null;
    originalNextSibling = el.nextSibling || null;
    originalBodyPaddingTop = document.body.style.paddingTop || "";

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
      originalStyles[prop] = {
        value: el.style.getPropertyValue(prop),
        priority: el.style.getPropertyPriority(prop)
      };
    });
  }

  function restoreStyles(el) {
    if (!el || !originalStyles || originalNav !== el) return;

    Object.keys(originalStyles).forEach(function (prop) {
      var state = originalStyles[prop];
      if (state.value) {
        el.style.setProperty(prop, state.value, state.priority || "");
      } else {
        el.style.removeProperty(prop);
      }
    });
  }

  function detachToViewportRoot(menu) {
    if (!menu || menu.parentNode === document.body) return;

    if (!placeholder || !placeholder.parentNode) {
      placeholder = document.createComment("pincabos-menu-pin-v7-placeholder");
      if (menu.parentNode) {
        menu.parentNode.insertBefore(placeholder, menu);
      }
    }

    document.body.appendChild(menu);
  }

  function restorePlacement(menu) {
    if (!menu) return;

    if (placeholder && placeholder.parentNode) {
      placeholder.parentNode.insertBefore(menu, placeholder);
      placeholder.parentNode.removeChild(placeholder);
      placeholder = null;
      return;
    }

    if (originalParent && originalParent.isConnected) {
      if (
        originalNextSibling &&
        originalNextSibling.parentNode === originalParent
      ) {
        originalParent.insertBefore(menu, originalNextSibling);
      } else {
        originalParent.appendChild(menu);
      }
    }
  }

  function clearWrongFixedTargets(menu) {
    Array.prototype.slice.call(
      document.querySelectorAll(".pco-menu-force-fixed")
    ).forEach(function (el) {
      if (el !== menu) {
        el.classList.remove("pco-menu-force-fixed");
      }
    });
  }

  function menuHeight(menu) {
    if (!menu) return 0;
    var rect = menu.getBoundingClientRect();
    return Math.max(
      0,
      Math.ceil(rect.height || menu.offsetHeight || menu.scrollHeight || 0)
    );
  }

  function applyViewportPin() {
    var menu = nav();
    if (!menu) return false;

    rememberState(menu);
    clearWrongFixedTargets(menu);
    detachToViewportRoot(menu);

    menu.classList.add("pco-menu-force-fixed");
    menu.classList.add(ownedClass);

    /* Inline + important : gagne aussi contre les vieux CSS des pages. */
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

    var h = menuHeight(menu);
    if (h > 0) {
      /* Le moteur historique utilise aussi cette variable pour l'editeur INI. */
      document.documentElement.style.setProperty(
        "--pco-menu-pinned-offset",
        h + "px"
      );
      document.body.style.paddingTop = h + "px";
      document.body.classList.add("pco-menu-is-pinned");
    }

    return true;
  }

  function clearViewportPin() {
    var menu = nav();
    if (!menu) return;

    menu.classList.remove(ownedClass);
    menu.classList.remove("pco-menu-force-fixed");
    restoreStyles(menu);
    restorePlacement(menu);

    /*
     * Le vieux moteur peut avoir recapture son etat pendant que le nav etait
     * deja fixe. On restaure donc explicitement le padding memorise avant le
     * pin pour garantir un desepinglage propre.
     */
    if (originalBodyPaddingTop !== null) {
      document.body.style.paddingTop = originalBodyPaddingTop;
    }
    document.documentElement.style.setProperty("--pco-menu-pinned-offset", "0px");
    document.body.classList.remove("pco-menu-is-pinned");
  }

  function sync() {
    if (pinned()) {
      applyViewportPin();
    } else {
      clearViewportPin();
    }
  }

  function schedule(delay) {
    window.clearTimeout(syncTimer);
    syncTimer = window.setTimeout(sync, delay || 0);
  }

  function watchDom() {
    if (!window.MutationObserver || !document.body || observer) return;

    observer = new MutationObserver(function (mutations) {
      var relevant = mutations.some(function (mutation) {
        if (mutation.type === "childList") {
          return mutation.addedNodes.length > 0 || mutation.removedNodes.length > 0;
        }
        if (mutation.type === "attributes") {
          return mutation.target === document.body ||
            (mutation.target && mutation.target.id === "pco-menu-pin-btn");
        }
        return false;
      });

      /* Le vieux moteur resynchronise a ~40 ms. On gagne volontairement apres. */
      if (relevant) schedule(70);
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["class", "aria-pressed"]
    });
  }

  function boot() {
    /* Au chargement, le vieux moteur est deja enregistre avant cette couche. */
    sync();
    watchDom();

    /*
     * Le clic historique continue de faire tout son travail. On programme
     * seulement la correction de geometrie juste apres son handler.
     */
    document.addEventListener("click", function (event) {
      var target = event.target && event.target.closest
        ? event.target.closest("#pco-menu-pin-btn")
        : null;
      if (target) {
        schedule(0);
        window.setTimeout(sync, 90);
      }
    }, true);

    window.addEventListener("resize", function () {
      window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(sync, 120);
    });

    window.addEventListener("pageshow", function () {
      schedule(20);
    });

    window.addEventListener("storage", function (event) {
      if (event && event.key === KEY) schedule(20);
    });

    /* Verifie aussi apres les scripts tardifs du Dashboard. */
    window.setTimeout(sync, 160);
    window.setTimeout(sync, 600);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
