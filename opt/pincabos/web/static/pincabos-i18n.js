/* PINCABOS_I18N_SINGLE_LOADER_V3
 *
 * PINCABOS_I18N_SINGLE_GOOGLE_LOADER_V2
 * Un seul chargeur Google Translate pour toute la WebApp.
 */
(function () {
  "use strict";

  const STORAGE_KEY = "pincabos_lang";
  const GOOGLE_SCRIPT_ID = "pincabos-google-translate-script";
  const GOOGLE_ELEMENT_ID = "google_translate_element";
  const HIDE_STYLE_ID = "pincabos-google-translate-hide-style";

  const SUPPORTED_LANGS = {
    fr: "Français",
    en: "English",
    es: "Español",
    it: "Italiano",
    de: "Deutsch",
    nl: "Nederlands"
  };

  const INCLUDED_LANGUAGES = Object.keys(SUPPORTED_LANGS).join(",");
  let widgetCreated = false;
  let applyTimer = null;

  function normalizeLang(lang) {
    return Object.prototype.hasOwnProperty.call(SUPPORTED_LANGS, lang)
      ? lang
      : "fr";
  }

  function getSavedLanguage() {
    try {
      return normalizeLang(localStorage.getItem(STORAGE_KEY) || "fr");
    } catch (_) {
      return "fr";
    }
  }

  function setSavedLanguage(lang) {
    try {
      localStorage.setItem(STORAGE_KEY, normalizeLang(lang));
    } catch (_) {}
  }

  function setHtmlLang(lang) {
    document.documentElement.setAttribute("lang", normalizeLang(lang));
  }

  function injectHideStyle() {
    if (document.getElementById(HIDE_STYLE_ID)) return;

    const style = document.createElement("style");
    style.id = HIDE_STYLE_ID;
    style.textContent = `
      html, body {
        top: 0 !important;
      }

      body {
        position: static !important;
        min-height: 100vh !important;
      }

      .goog-te-banner-frame,
      .goog-te-banner-frame.skiptranslate,
      iframe.goog-te-banner-frame,
      iframe.goog-te-menu-frame,
      .skiptranslate iframe,
      body > .skiptranslate,
      .goog-logo-link,
      .goog-te-gadget span,
      .goog-te-balloon-frame {
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
        width: 0 !important;
        height: 0 !important;
        max-width: 0 !important;
        max-height: 0 !important;
        overflow: hidden !important;
        pointer-events: none !important;
      }

      #google_translate_element,
      .goog-te-combo {
        position: fixed !important;
        left: -99999px !important;
        top: -99999px !important;
        width: 1px !important;
        height: 1px !important;
        opacity: 0 !important;
        overflow: hidden !important;
        pointer-events: none !important;
        z-index: -1 !important;
      }
    `;

    document.head.appendChild(style);
  }

  function ensureGoogleElement() {
    let element = document.getElementById(GOOGLE_ELEMENT_ID);

    if (!element) {
      element = document.createElement("div");
      element.id = GOOGLE_ELEMENT_ID;
      element.setAttribute("aria-hidden", "true");
      document.body.appendChild(element);
    }

    return element;
  }

  function setCookie(name, value) {
    const age = 60 * 60 * 24 * 365;
    document.cookie = `${name}=${value}; path=/; max-age=${age}`;

    try {
      const host = window.location.hostname;
      if (host && host.includes(".") && !/^\d+\.\d+\.\d+\.\d+$/.test(host)) {
        document.cookie =
          `${name}=${value}; path=/; domain=.${host}; max-age=${age}`;
      }
    } catch (_) {}
  }

  function clearGoogleTranslateCookie() {
    document.cookie = "googtrans=; path=/; max-age=0";

    try {
      const host = window.location.hostname;
      if (host && host.includes(".") && !/^\d+\.\d+\.\d+\.\d+$/.test(host)) {
        document.cookie =
          `googtrans=; path=/; domain=.${host}; max-age=0`;
      }
    } catch (_) {}
  }

  function cleanGoogleOffset() {
    try {
      document.documentElement.style.top = "0px";
      document.body.style.top = "0px";
      document.body.style.position = "static";
    } catch (_) {}

    document.querySelectorAll(
      ".goog-te-banner-frame, iframe.goog-te-banner-frame, " +
      "iframe.goog-te-menu-frame, .goog-te-balloon-frame"
    ).forEach((element) => {
      try {
        element.style.display = "none";
        element.style.visibility = "hidden";
        element.style.opacity = "0";
        element.style.width = "0";
        element.style.height = "0";
      } catch (_) {}
    });
  }

  function findGoogleCombo() {
    return document.querySelector("select.goog-te-combo");
  }

  function dispatchChange(element) {
    if (!element) return;
    element.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function applyGoogleLanguage(lang, attempt) {
    const target = normalizeLang(lang);
    const tries = Number(attempt || 0);
    const combo = findGoogleCombo();

    if (!combo) {
      if (tries < 24) {
        window.setTimeout(() => {
          applyGoogleLanguage(target, tries + 1);
        }, 250);
      }
      return;
    }

    combo.value = target === "fr" ? "" : target;
    dispatchChange(combo);

    window.setTimeout(cleanGoogleOffset, 100);
    window.setTimeout(cleanGoogleOffset, 500);
    window.setTimeout(cleanGoogleOffset, 1200);
  }

  function scheduleApply(lang) {
    window.clearTimeout(applyTimer);
    applyTimer = window.setTimeout(() => {
      applyGoogleLanguage(lang, 0);
    }, 80);
  }

  function createGoogleWidget() {
    if (widgetCreated) {
      scheduleApply(getSavedLanguage());
      return;
    }

    if (
      !window.google ||
      !window.google.translate ||
      !window.google.translate.TranslateElement
    ) {
      return;
    }

    try {
      ensureGoogleElement();

      new window.google.translate.TranslateElement(
        {
          pageLanguage: "fr",
          includedLanguages: INCLUDED_LANGUAGES,
          autoDisplay: false,
          layout: window.google.translate.TranslateElement.InlineLayout.SIMPLE
        },
        GOOGLE_ELEMENT_ID
      );

      widgetCreated = true;
      scheduleApply(getSavedLanguage());
    } catch (_) {}
  }

  window.googleTranslateElementInit = function () {
    injectHideStyle();
    ensureGoogleElement();
    createGoogleWidget();
  };

  function loadGoogleWidget() {
    injectHideStyle();
    ensureGoogleElement();

    /*
      Une balise Google déjà présente peut venir d'une ancienne page
      conservée en cache. On l'utilise au lieu d'en injecter une deuxième.
    */
    const existing = document.querySelector(
      'script[src*="translate.google.com/translate_a/element.js"]'
    );

    if (existing) {
      if (!existing.id) {
        existing.id = GOOGLE_SCRIPT_ID;
      }
      return;
    }

    if (document.getElementById(GOOGLE_SCRIPT_ID)) {
      return;
    }

    const script = document.createElement("script");
    script.id = GOOGLE_SCRIPT_ID;
    script.src =
      "https://translate.google.com/translate_a/element.js" +
      "?cb=googleTranslateElementInit";
    script.async = true;
    document.head.appendChild(script);
  }

  function reloadForLanguageChange() {
    try {
      const url = new URL(window.location.href);
      url.searchParams.set("_pincabos_lang_reload", Date.now().toString());
      window.location.replace(url.toString());
    } catch (_) {
      window.location.reload();
    }
  }

  window.setPinCabOSLanguage = function (lang) {
    const target = normalizeLang(lang);
    const current = getSavedLanguage();

    setSavedLanguage(target);
    setHtmlLang(target);

    const select = document.getElementById("pincabos_language_select");
    if (select) select.value = target;

    if (target === "fr") {
      clearGoogleTranslateCookie();
    } else {
      setCookie("googtrans", `/fr/${target}`);
    }

    if (current !== target) {
      reloadForLanguageChange();
      return;
    }

    scheduleApply(target);
  };

  function updateLanguageSelect() {
    const select = document.getElementById("pincabos_language_select");
    if (!select) return;

    const existing = Array.from(select.options || []).map((option) => option.value);

    Object.keys(SUPPORTED_LANGS).forEach((code) => {
      if (existing.includes(code)) return;

      const option = document.createElement("option");
      option.value = code;
      option.textContent = SUPPORTED_LANGS[code];
      select.appendChild(option);
    });

    select.value = getSavedLanguage();
    select.onchange = function () {
      window.setPinCabOSLanguage(this.value);
    };
  }

  function boot() {
    injectHideStyle();
    ensureGoogleElement();
    setHtmlLang(getSavedLanguage());
    updateLanguageSelect();
    loadGoogleWidget();

    window.setInterval(cleanGoogleOffset, 1000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();


/* PINCABOS_HIDE_GOOGLE_TRANSLATE_FLOATING_BUBBLE_V2_JS */
(function(){
  function hideGoogleBubble(){
    try {
      const selectors = [
        "#google_translate_element",
        ".goog-te-gadget",
        ".goog-te-gadget-icon",
        ".goog-logo-link",
        ".goog-te-banner-frame",
        "iframe.goog-te-banner-frame",
        "iframe.goog-te-menu-frame",
        "iframe.skiptranslate",
        ".goog-te-balloon-frame",
        ".VIpgJd-ZVi9od-xl07Ob-lTBxed",
        ".VIpgJd-ZVi9od-ORHb-OEVmcd",
        ".VIpgJd-ZVi9od-aZ2wEe-wOHMyf",
        ".VIpgJd-yAWNEb-L7lbkb",
        ".VIpgJd-yAWNEb-hvhgNd",
        ".VIpgJd-ZVi9od-aZ2wEe-OiiCO",
        ".VIpgJd-ZVi9od-aZ2wEe"
      ];

      selectors.forEach(function(sel){
        document.querySelectorAll(sel).forEach(function(node){
          node.style.setProperty("display", "none", "important");
          node.style.setProperty("visibility", "hidden", "important");
          node.style.setProperty("opacity", "0", "important");
          node.style.setProperty("pointer-events", "none", "important");
          node.style.setProperty("width", "0", "important");
          node.style.setProperty("height", "0", "important");
          node.style.setProperty("max-width", "0", "important");
          node.style.setProperty("max-height", "0", "important");
          node.style.setProperty("overflow", "hidden", "important");
        });
      });

      document.body.style.setProperty("top", "0", "important");
    } catch(e) {}
  }

  hideGoogleBubble();
  document.addEventListener("DOMContentLoaded", hideGoogleBubble);
  window.addEventListener("load", hideGoogleBubble);
  setInterval(hideGoogleBubble, 750);

  try {
    new MutationObserver(hideGoogleBubble).observe(
      document.documentElement,
      {childList:true, subtree:true, attributes:true}
    );
  } catch(e) {}
})();

