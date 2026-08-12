(() => {
  "use strict";

  const inExplorer = () => (
    location.pathname === "/tools/commander" ||
    location.pathname.startsWith("/tools/commander/")
  );

  if (!inExplorer()) return;
  if (window.__pincabosExplorerVpsNewTabV2) return;

  window.__pincabosExplorerVpsNewTabV2 = true;

  const originalOpen = window.open.bind(window);

  function parseUrl(rawUrl) {
    if (!rawUrl) return null;

    try {
      return new URL(String(rawUrl), location.href);
    } catch (_) {
      return null;
    }
  }

  function isVpsUrl(url) {
    if (!url) return false;

    const hostname = url.hostname.toLowerCase();
    const pathname = url.pathname.toLowerCase();

    return (
      hostname === "virtualpinballspreadsheet.github.io" ||
      hostname.endsWith(".virtualpinballspreadsheet.github.io") ||
      pathname.includes("/vps-db/")
    );
  }

  function isVpsLink(anchor, url) {
    if (!anchor) return isVpsUrl(url);

    const text = String(anchor.textContent || "")
      .replace(/\s+/g, " ")
      .trim()
      .toUpperCase();

    const title = String(
      anchor.getAttribute("title") || ""
    ).toUpperCase();

    const ariaLabel = String(
      anchor.getAttribute("aria-label") || ""
    ).toUpperCase();

    return (
      isVpsUrl(url) ||
      text === "VPS" ||
      text.endsWith(" VPS") ||
      text.includes("OUVRIR VPS") ||
      title.includes("VPS") ||
      ariaLabel.includes("VPS")
    );
  }

  function configureAnchor(anchor) {
    if (!(anchor instanceof HTMLAnchorElement)) return;

    const url = parseUrl(anchor.getAttribute("href"));

    if (isVpsLink(anchor, url)) {
      anchor.target = "_blank";
      anchor.rel = "noopener noreferrer";
      anchor.dataset.pincabosVpsNewTab = "1";
      return;
    }

    /*
     * Comportement original de PinCab Explorer :
     * les autres liens restent dans l'onglet actuel.
     */
    anchor.target = "_self";
    delete anchor.dataset.pincabosVpsNewTab;
  }

  function configureLinks(root) {
    if (!root) return;

    if (
      root instanceof HTMLAnchorElement &&
      root.matches("a[href]")
    ) {
      configureAnchor(root);
    }

    if (typeof root.querySelectorAll === "function") {
      root.querySelectorAll("a[href]").forEach(configureAnchor);
    }
  }

  /*
   * Corrige les liens déjà présents.
   */
  configureLinks(document);

  /*
   * Corrige aussi les cartes Play / Stop / VPS ajoutées
   * dynamiquement après l'analyse des tables.
   */
  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      for (const node of mutation.addedNodes) {
        if (node instanceof Element) {
          configureLinks(node);
        }
      }
    }
  });

  observer.observe(document.documentElement, {
    childList: true,
    subtree: true
  });

  /*
   * Dernière protection au moment du clic.
   */
  document.addEventListener(
    "click",
    (event) => {
      const target = event.target;

      if (!(target instanceof Element)) return;

      const anchor = target.closest("a[href]");
      if (!anchor) return;

      configureAnchor(anchor);
    },
    true
  );

  /*
   * Supporte aussi un bouton VPS qui appelle window.open()
   * depuis son propre gestionnaire JavaScript.
   */
  window.open = function pincabosExplorerOpen(
    rawUrl,
    target,
    features
  ) {
    const url = parseUrl(rawUrl);

    if (isVpsUrl(url)) {
      const safeFeatures = features
        ? `${features},noopener,noreferrer`
        : "noopener,noreferrer";

      const newWindow = originalOpen(
        rawUrl,
        "_blank",
        safeFeatures
      );

      try {
        if (newWindow) {
          newWindow.opener = null;
        }
      } catch (_) {
        // Le navigateur peut bloquer l'accès à opener.
      }

      return newWindow;
    }

    return originalOpen(rawUrl, "_self", features);
  };
})();
