/* PINCABOS_EXPLORER_SAME_TAB_V1 */
(() => {
  "use strict";

  const inExplorer = () => (
    location.pathname === "/tools/commander" ||
    location.pathname.startsWith("/tools/commander/")
  );

  if (!inExplorer()) return;

  const normalize = (root = document) => {
    root.querySelectorAll(
      'a[target="_blank"], area[target="_blank"], form[target="_blank"]'
    ).forEach((node) => {
      node.removeAttribute("target");
      node.removeAttribute("rel");
    });
  };

  normalize();

  document.addEventListener("click", (event) => {
    const link = event.target.closest("a, area");
    if (!link) return;

    if ((link.getAttribute("target") || "").toLowerCase() === "_blank") {
      link.removeAttribute("target");
      link.removeAttribute("rel");
    }
  }, true);

  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (!form || form.tagName !== "FORM") return;

    if ((form.getAttribute("target") || "").toLowerCase() === "_blank") {
      form.removeAttribute("target");
    }
  }, true);

  const originalOpen = window.open.bind(window);

  window.open = function(url, target, features) {
    const destination = String(target || "_blank").toLowerCase();

    if (destination === "_blank") {
      if (url && String(url) !== "about:blank") {
        window.location.assign(String(url));
      }
      return window;
    }

    return originalOpen(url, target, features);
  };

  new MutationObserver(() => normalize())
    .observe(document.documentElement, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["target"]
    });
})();
