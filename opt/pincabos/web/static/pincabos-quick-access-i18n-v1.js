/* PINCABOS_QUICK_ACCESS_I18N_V1 */
(() => {
  "use strict";

  const translations = Object.freeze({
    fr: "Accès rapides",
    en: "Quick access",
    es: "Acceso rápido",
    it: "Accesso rapido",
    de: "Schnellzugriff",
    nl: "Snelle toegang",
  });

  const normalizeLanguage = (value) => {
    const language = String(value || "")
      .trim()
      .toLowerCase()
      .split(/[-_]/, 1)[0];

    return Object.prototype.hasOwnProperty.call(translations, language)
      ? language
      : "fr";
  };

  const selectedLanguage = () => {
    const selector = document.querySelector(
      ".top-language-widget select, select[name='language'], select[name='lang'], #language-select"
    );

    if (selector && selector.value) {
      return normalizeLanguage(selector.value);
    }

    return normalizeLanguage(document.documentElement.lang);
  };

  const applyTranslation = () => {
    const language = selectedLanguage();
    const text = translations[language];

    document.querySelectorAll("[data-pco-i18n-quick-access='1']").forEach((element) => {
      element.textContent = text;
      element.setAttribute("lang", language);
      element.setAttribute("aria-label", text);
    });
  };

  const start = () => {
    applyTranslation();

    document.addEventListener("change", () => {
      window.setTimeout(applyTranslation, 0);
    });

    new MutationObserver(applyTranslation).observe(
      document.documentElement,
      { attributes: true, attributeFilter: ["lang"] }
    );

    window.setTimeout(applyTranslation, 250);
    window.setTimeout(applyTranslation, 1000);
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
