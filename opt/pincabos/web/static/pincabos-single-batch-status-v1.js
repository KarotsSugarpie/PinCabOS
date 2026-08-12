/* PINCABOS_SINGLE_BATCH_STATUS_OWNER_V1 */
/* PINCABOS_BATCH_CARD_FLOAT_UNDER_LANGUAGE_V2 */
(() => {
  "use strict";

  if (window.__PINCABOS_BATCH_CARD_FLOAT_UNDER_LANGUAGE_V2__) return;
  window.__PINCABOS_BATCH_CARD_FLOAT_UNDER_LANGUAGE_V2__ = true;

  const CANONICAL_ID = "pcos-bxp6-language-status";
  const OVERLAY_ID = "pco-impexp-live-overlay-root";
  const SLOT_ID = "pco-impexp-live-menu-slot";

  const LEGACY_SELECTORS = [
    "#pcos-bip-language-status",
    ".pco-impexp-menu-import",
    "#pincabos-batch-live-status-card",
    "#pincabos-batch-status-card",
    ".pincabos-batch-live-status-card",
    ".pincabos-batch-status-card"
  ];

  let scheduled = false;
  let observer = null;
  let resizeObserver = null;

  function normalizedText(node) {
    return String(node?.textContent || "")
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();
  }

  function menuSlot() {
    return document.getElementById(SLOT_ID);
  }

  function canonicalCards() {
    return Array.from(
      document.querySelectorAll(`[id="${CANONICAL_ID}"]`)
    );
  }

  function isCanonicalActive(card) {
    if (!card) return false;
    if (card.hidden) return false;

    const ariaHidden = String(
      card.getAttribute("aria-hidden") || ""
    ).toLowerCase();

    if (ariaHidden === "true") return false;

    const inlineDisplay = String(card.style.display || "")
      .toLowerCase();

    const inlineVisibility = String(card.style.visibility || "")
      .toLowerCase();

    if (
      inlineDisplay === "none" ||
      inlineVisibility === "hidden"
    ) {
      return false;
    }

    const text = normalizedText(card);

    if (!text) return false;

    const inactiveOnly =
      /\b(inactif|inactive|aucun batch|aucune tâche|idle)\b/.test(text) ||
      (
        /\b(terminé|termine|terminée|fini|completed|complete)\b/.test(text) &&
        !/\b(actif|active|en cours|attente|préparation|traitement|running|queued)\b/.test(text)
      );

    if (inactiveOnly) return false;

    const activeWords =
      /\b(actif|active|en cours|attente|préparation|traitement|importation|exportation|running|queued|processing)\b/.test(text);

    const progress =
      /\b\d{1,3}\s*%/.test(text) ||
      /\b\d+\s*\/\s*\d+\b/.test(text);

    const batchWords =
      /\b(batch|import|export|package|archive|table)\b/.test(text);

    const activeClass =
      card.classList.contains("is-active") ||
      card.classList.contains("active") ||
      card.closest(".is-active") !== null;

    return (
      activeClass ||
      (batchWords && activeWords) ||
      (batchWords && progress)
    );
  }

  function looksLikeLanguageText(node) {
    const text = normalizedText(node);
    return (
      text === "langue" ||
      text === "language" ||
      text === "langage"
    );
  }

  function validAnchorRect(rect) {
    return (
      rect &&
      rect.width >= 180 &&
      rect.width <= 700 &&
      rect.height >= 45 &&
      rect.height <= 520 &&
      rect.right > window.innerWidth * 0.48 &&
      rect.bottom > 0 &&
      rect.top < window.innerHeight
    );
  }

  function candidateScore(rect) {
    const rightGap = Math.max(0, window.innerWidth - rect.right);
    const areaPenalty = (rect.width * rect.height) / 10000;
    return rightGap + areaPenalty;
  }

  function findLanguageAnchor(slot) {
    const candidates = [];

    /*
     * Le slot est normalement injecté directement sous la carte Langue.
     * On inspecte donc d'abord ses parents immédiats.
     */
    let parent = slot?.parentElement || null;

    for (let depth = 0; parent && depth < 6; depth += 1) {
      const rect = parent.getBoundingClientRect();

      if (validAnchorRect(rect)) {
        candidates.push({
          node: parent,
          rect,
          score: candidateScore(rect) - 80 + depth * 4
        });
      }

      parent = parent.parentElement;
    }

    /*
     * Repli sémantique : recherche du titre Langue/Language visible,
     * puis remontée vers sa carte.
     */
    const titleNodes = Array.from(
      document.querySelectorAll(
        "h1,h2,h3,h4,h5,strong,b,span,div,label"
      )
    ).filter(looksLikeLanguageText);

    for (const title of titleNodes) {
      let node = title;

      for (let depth = 0; node && depth < 7; depth += 1) {
        const rect = node.getBoundingClientRect();

        if (validAnchorRect(rect)) {
          candidates.push({
            node,
            rect,
            score: candidateScore(rect) + depth * 5
          });
        }

        node = node.parentElement;
      }
    }

    if (!candidates.length) return null;

    candidates.sort((a, b) => a.score - b.score);
    return candidates[0];
  }

  function positionSlot(slot) {
    const anchor = findLanguageAnchor(slot);

    if (!anchor) {
      slot.style.setProperty(
        "--pco-batch-float-top",
        "118px"
      );
      slot.style.setProperty(
        "--pco-batch-float-right",
        "18px"
      );
      slot.style.setProperty(
        "--pco-batch-float-width",
        "430px"
      );
      return;
    }

    const rect = anchor.rect;
    const top = Math.max(
      12,
      Math.min(
        window.innerHeight - 90,
        Math.round(rect.bottom + 8)
      )
    );

    const right = Math.max(
      12,
      Math.round(window.innerWidth - rect.right)
    );

    const width = Math.max(
      330,
      Math.min(500, Math.round(rect.width))
    );

    slot.style.setProperty(
      "--pco-batch-float-top",
      `${top}px`
    );
    slot.style.setProperty(
      "--pco-batch-float-right",
      `${right}px`
    );
    slot.style.setProperty(
      "--pco-batch-float-width",
      `${width}px`
    );
  }

  function removeLegacyCards() {
    for (const selector of LEGACY_SELECTORS) {
      document.querySelectorAll(selector).forEach(node => {
        if (node.id !== CANONICAL_ID) node.remove();
      });
    }
  }

  function neutralizeOldOverlay(slot) {
    const overlay = document.getElementById(OVERLAY_ID);

    if (!overlay) return;

    overlay
      .querySelectorAll(
        ".pco-global-system-notice, .pco-impexp-menu-status"
      )
      .forEach(node => {
        if (node.id === CANONICAL_ID) {
          if (node.parentElement !== slot) {
            slot.appendChild(node);
          }
          return;
        }

        const text = normalizedText(node);

        const duplicateBatch =
          /\b(batch|import|export)\b/.test(text) &&
          (
            /\b(actif|active|en cours|attente|running|queued)\b/.test(text) ||
            /\b\d{1,3}\s*%/.test(text) ||
            /\b\d+\s*\/\s*\d+\b/.test(text)
          );

        if (
          node.matches(LEGACY_SELECTORS.join(",")) ||
          duplicateBatch
        ) {
          node.remove();
        }
      });

    overlay.classList.remove("is-active");
    overlay.setAttribute("aria-hidden", "true");
    overlay.style.setProperty("display", "none", "important");
  }

  function enforce() {
    scheduled = false;

    const slot = menuSlot();

    if (!slot) {
      document.documentElement.classList.remove(
        "pco-single-batch-status-owner"
      );
      return;
    }

    document.documentElement.classList.add(
      "pco-single-batch-status-owner"
    );

    const cards = canonicalCards();
    const canonical = cards.shift() || null;

    for (const duplicate of cards) {
      duplicate.remove();
    }

    if (canonical && canonical.parentElement !== slot) {
      slot.appendChild(canonical);
    }

    removeLegacyCards();
    neutralizeOldOverlay(slot);

    const active = isCanonicalActive(canonical);

    slot.classList.toggle(
      "pco-batch-float-active",
      active
    );

    slot.setAttribute(
      "aria-hidden",
      active ? "false" : "true"
    );

    if (active) {
      positionSlot(slot);
    }
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    window.requestAnimationFrame(enforce);
  }

  function start() {
    schedule();

    observer = new MutationObserver(schedule);
    observer.observe(document.documentElement, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: [
        "class",
        "style",
        "hidden",
        "aria-hidden"
      ]
    });

    if ("ResizeObserver" in window) {
      resizeObserver = new ResizeObserver(schedule);
      resizeObserver.observe(document.documentElement);
    }

    window.addEventListener("resize", schedule);
    window.addEventListener("scroll", schedule, true);
    window.addEventListener("pageshow", schedule);
    window.addEventListener("pincabos:notify", schedule);

    /*
     * Relances pour les fragments injectés après le chargement.
     * Aucun nouvel appel API n'est créé par ce correctif.
     */
    [
      100,
      300,
      700,
      1500,
      3000,
      6000,
      10000
    ].forEach(delay => {
      window.setTimeout(schedule, delay);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded",
      start,
      { once: true }
    );
  } else {
    start();
  }
})();
