/* PINCABOS_QUICK_ACCESS_I18N_V2 */
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

  const configureQuickAccess = () => {
    document.querySelectorAll(".nav-vpinfe-vps-group").forEach((group) => {
      let pincabosSite = group.querySelector("a[data-pco-quick-access='pincabos-site']");

      if (!pincabosSite) {
        pincabosSite = document.createElement("a");
        pincabosSite.href = "https://pincabos.cc";
        pincabosSite.className = "secondary nav-action";
        pincabosSite.textContent = "PinCabOs.cc";
        pincabosSite.dataset.pcoQuickAccess = "pincabos-site";
      }

      const vpinfe = group.querySelector("a[href^='http://'][href$=':8001']");
      const vps = group.querySelector("a[href='https://virtualpinballspreadsheet.github.io/']");
      const explorer = group.querySelector("a[href='/tools/commander']");
      const consoleLink = group.querySelector("a[href='/console']");

      if (vpinfe) {
        vpinfe.textContent = "VPinFE";
        vpinfe.dataset.pcoQuickAccess = "vpinfe";
      }

      if (vps) {
        vps.textContent = "VPS";
        vps.dataset.pcoQuickAccess = "vps";
      }

      if (explorer) {
        explorer.dataset.pcoQuickAccess = "explorer";
      }

      if (consoleLink) {
        consoleLink.dataset.pcoQuickAccess = "console";
      }

      const orderedLinks = [pincabosSite, vpinfe, vps, explorer, consoleLink].filter(Boolean);

      orderedLinks.forEach((anchor) => {
        anchor.target = "_blank";
        anchor.rel = "noopener noreferrer";
      });

      orderedLinks.forEach((anchor) => group.appendChild(anchor));
    });
  };

  const apply = () => {
    applyTranslation();
    configureQuickAccess();
  };

  const start = () => {
    apply();

    document.addEventListener("change", () => {
      window.setTimeout(apply, 0);
    });

    new MutationObserver(applyTranslation).observe(
      document.documentElement,
      { attributes: true, attributeFilter: ["lang"] }
    );

    window.setTimeout(apply, 250);
    window.setTimeout(apply, 1000);
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
