(() => {
  "use strict";

  // PINCABOS_SYSTEM_MESSAGES_MENU_FREE_SPACE_V4_JS

  const TRAY_ID = "pco-system-message-tray";
  const LIST_ID = "pco-system-message-tray-list";

  const CANDIDATE_SELECTOR = [
    ".pco-toast.server",
    ".flash:not(.card)",
    ".flashes > li",
    ".flashes > div",
    ".alert:not(.card)",
    ".notice:not(.card)",
    ".notification:not(.card)",
    "[role='alert']:not(.card)"
  ].join(",");

  const IGNORE_SELECTOR = [
    "#" + TRAY_ID,
    "#" + TRAY_ID + " *",

    ".pincabos-live-table-status-card",
    ".pincabos-live-table-status-card *",

    "#pincabos-batch-live-status-card",
    "#pincabos-batch-live-status-card *",

    "#pincabos-batch-status-card",
    "#pincabos-batch-status-card *",

    ".pincabos-batch-live-status-card",
    ".pincabos-batch-live-status-card *",

    ".pincabos-batch-status-card",
    ".pincabos-batch-status-card *",

    ".pco-modal",
    ".pco-modal *",

    "[role='dialog']",
    "[role='dialog'] *"
  ].join(",");

  let scheduled = false;

  function languageCard() {
    const select = document.getElementById(
      "pincabos_language_select"
    );

    if (!select) {
      return null;
    }

    return (
      select.closest(".top-language-widget")
      || select.closest(".brand-language-slot")
      || select.parentElement
    );
  }

  function menuCard() {
    const language = languageCard();

    if (!language) {
      return null;
    }

    return (
      document.querySelector(".top")
      || language.closest(".top")
      || language.parentElement
    );
  }

  function visibleElement(node) {
    if (!(node instanceof HTMLElement)) {
      return false;
    }

    const style = window.getComputedStyle(node);

    if (
      style.display === "none"
      || style.visibility === "hidden"
    ) {
      return false;
    }

    const rect = node.getBoundingClientRect();

    return rect.width > 1 && rect.height > 1;
  }

  function screenControlCards(menu) {
    if (!menu) {
      return [];
    }

    let controls = Array.from(
      menu.querySelectorAll(".nav-inline-form")
    ).filter(visibleElement);

    if (!controls.length) {
      controls = Array.from(
        menu.querySelectorAll(".screen-toggle-btn")
      ).filter(visibleElement);
    }

    return controls;
  }

  function createTray() {
    const tray = document.createElement("section");

    tray.id = TRAY_ID;
    tray.className = "pco-system-message-tray";
    tray.hidden = true;

    tray.setAttribute("aria-live", "polite");
    tray.setAttribute(
      "aria-label",
      "Messages système PinCabOS"
    );

    const list = document.createElement("div");

    list.id = LIST_ID;
    list.className = "pco-system-message-tray-list";

    tray.appendChild(list);

    return tray;
  }

  function ensureTray() {
    let tray = document.getElementById(TRAY_ID);

    if (!tray) {
      tray = createTray();
    }

    if (tray.parentNode !== document.body) {
      document.body.appendChild(tray);
    }

    positionTray();

    return tray;
  }

  function applyTrayRectangle(
    tray,
    left,
    top,
    width,
    height
  ) {
    const viewportPadding = 8;

    left = Math.max(
      viewportPadding,
      Math.round(left)
    );

    top = Math.max(
      viewportPadding,
      Math.round(top)
    );

    width = Math.max(
      280,
      Math.round(width)
    );

    height = Math.max(
      70,
      Math.round(height)
    );

    if (left + width > window.innerWidth - viewportPadding) {
      width = Math.max(
        280,
        window.innerWidth - left - viewportPadding
      );
    }

    if (top + height > window.innerHeight - viewportPadding) {
      height = Math.max(
        70,
        window.innerHeight - top - viewportPadding
      );
    }

    tray.style.left = left + "px";
    tray.style.top = top + "px";
    tray.style.width = width + "px";
    tray.style.height = height + "px";

    tray.dataset.pcoPlacement = "menu-free-space";
  }

  function positionTray() {
    const language = languageCard();
    const menu = menuCard();
    const tray = document.getElementById(TRAY_ID);

    if (!language || !tray) {
      return;
    }

    const languageRect = language.getBoundingClientRect();

    /*
     * Mode principal :
     * utilise toute la zone libre de la grande carte du menu.
     */
    if (menu && visibleElement(menu)) {
      const menuRect = menu.getBoundingClientRect();
      const controls = screenControlCards(menu);

      let controlsRight = menuRect.left + 18;

      controls.forEach(control => {
        const rect = control.getBoundingClientRect();

        if (
          rect.bottom >= menuRect.top
          && rect.top <= menuRect.bottom
        ) {
          controlsRight = Math.max(
            controlsRight,
            rect.right
          );
        }
      });

      const left = Math.max(
        menuRect.left + 18,
        controlsRight + 16
      );

      const right = Math.min(
        menuRect.right - 18,
        languageRect.right
      );

      const top = Math.max(
        menuRect.top + 18,
        languageRect.bottom + 10
      );

      const bottom = menuRect.bottom - 18;

      const width = right - left;
      const height = bottom - top;

      if (width >= 320 && height >= 70) {
        applyTrayRectangle(
          tray,
          left,
          top,
          width,
          height
        );

        return;
      }

      /*
       * Repli si les cartes de boutons prennent trop de place :
       * toute la largeur intérieure disponible du menu.
       */
      const fallbackLeft = menuRect.left + 18;
      const fallbackRight = menuRect.right - 18;
      const fallbackTop = languageRect.bottom + 10;
      const fallbackBottom = menuRect.bottom - 18;

      if (
        fallbackRight - fallbackLeft >= 320
        && fallbackBottom - fallbackTop >= 70
      ) {
        applyTrayRectangle(
          tray,
          fallbackLeft,
          fallbackTop,
          fallbackRight - fallbackLeft,
          fallbackBottom - fallbackTop
        );

        return;
      }
    }

    /*
     * Dernier repli :
     * sous Langue, mais beaucoup plus large que l’ancienne V3.
     */
    const width = Math.max(
      320,
      Math.min(
        760,
        window.innerWidth - 24
      )
    );

    let left = languageRect.right - width;

    left = Math.max(
      8,
      Math.min(
        left,
        window.innerWidth - width - 8
      )
    );

    applyTrayRectangle(
      tray,
      left,
      languageRect.bottom + 10,
      width,
      88
    );
  }

  function trayList() {
    const tray = ensureTray();

    return tray
      ? tray.querySelector("#" + LIST_ID)
      : null;
  }

  function cleanText(node) {
    return String(node.textContent || "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function isCompactMessage(node) {
    if (!(node instanceof HTMLElement)) {
      return false;
    }

    if (
      [
        "SECTION",
        "MAIN",
        "ARTICLE",
        "FORM",
        "TABLE",
        "TBODY",
        "THEAD",
        "TR",
        "IFRAME"
      ].includes(node.tagName.toUpperCase())
    ) {
      return false;
    }

    const text = cleanText(node);

    if (!text || text.length > 420) {
      return false;
    }

    if (node.children.length > 8) {
      return false;
    }

    if (
      node.querySelector(
        "form, table, iframe, video, canvas, "
        + ".card, .pco-card, .pco-modal, "
        + "[role='dialog']"
      )
    ) {
      return false;
    }

    return true;
  }

  function isCandidate(node) {
    if (!(node instanceof HTMLElement)) {
      return false;
    }

    if (!node.matches(CANDIDATE_SELECTOR)) {
      return false;
    }

    if (node.matches(IGNORE_SELECTOR)) {
      return false;
    }

    if (node.dataset.pcoSystemMessageMoved === "1") {
      return false;
    }

    if (!isCompactMessage(node)) {
      return false;
    }

    const parentMessage = node.parentElement
      ? node.parentElement.closest(CANDIDATE_SELECTOR)
      : null;

    if (
      parentMessage
      && parentMessage !== node
      && !parentMessage.closest("#" + TRAY_ID)
    ) {
      return false;
    }

    return true;
  }

  function severity(node) {
    const text = cleanText(node)
      .toLocaleLowerCase("fr-CA");

    const classes = String(node.className || "")
      .toLocaleLowerCase("fr-CA");

    if (
      classes.includes("error")
      || classes.includes("danger")
      || classes.includes("bad")
      || text.startsWith("échec")
      || text.startsWith("erreur")
      || text.includes(" refusée")
      || text.includes(" impossible")
    ) {
      return "error";
    }

    if (
      classes.includes("success")
      || classes.includes("good")
      || classes.includes("ok")
      || text.includes(" configuré")
      || text.includes(" appliqué")
      || text.includes(" terminé")
      || text.includes(" demandé")
    ) {
      return "success";
    }

    return "warning";
  }

  function ensureCloseButton(node) {
    if (
      node.querySelector(
        ":scope > .pco-system-message-close"
      )
    ) {
      return;
    }

    const button = document.createElement("button");

    button.type = "button";
    button.className = "pco-system-message-close";

    button.setAttribute(
      "aria-label",
      "Fermer ce message"
    );

    button.title = "Fermer";
    button.textContent = "×";

    button.addEventListener("click", () => {
      node.remove();
      updateVisibility();
    });

    node.appendChild(button);
  }

  function normalizeMessage(node) {
    node.dataset.pcoSystemMessageMoved = "1";

    node.classList.add("pco-system-tray-message");

    node.classList.remove(
      "is-error",
      "is-warning",
      "is-success"
    );

    node.classList.add(
      "is-" + severity(node)
    );

    node.removeAttribute("hidden");

    [
      "position",
      "inset",
      "top",
      "right",
      "bottom",
      "left",
      "transform",
      "z-index",
      "margin",
      "width",
      "height",
      "min-height",
      "max-height"
    ].forEach(property => {
      node.style.removeProperty(property);
    });

    ensureCloseButton(node);
  }

  function moveMessage(node) {
    if (!isCandidate(node)) {
      return false;
    }

    const list = trayList();

    if (!list) {
      return false;
    }

    normalizeMessage(node);
    list.appendChild(node);

    return true;
  }

  function updateVisibility() {
    const tray = document.getElementById(TRAY_ID);

    if (!tray) {
      return;
    }

    const list = tray.querySelector("#" + LIST_ID);

    const count = list
      ? list.querySelectorAll(
          ":scope > .pco-system-tray-message"
        ).length
      : 0;

    tray.hidden = count === 0;
    tray.dataset.messageCount = String(count);

    if (count > 0) {
      positionTray();
    }
  }

  function cleanDashboardNoticeFromUrl() {
    try {
      const url = new URL(window.location.href);

      if (!url.searchParams.has("dashboard_notice")) {
        return;
      }

      url.searchParams.delete("dashboard_notice");

      history.replaceState(
        history.state,
        "",
        url.pathname
          + (
              url.searchParams.toString()
                ? "?" + url.searchParams.toString()
                : ""
            )
          + url.hash
      );
    } catch (_) {
      /* Aucune conséquence. */
    }
  }

  function sweep() {
    ensureTray();

    Array.from(
      document.querySelectorAll(CANDIDATE_SELECTOR)
    ).forEach(moveMessage);

    updateVisibility();
    cleanDashboardNoticeFromUrl();
    positionTray();
  }

  function scheduleSweep() {
    if (scheduled) {
      return;
    }

    scheduled = true;

    window.setTimeout(() => {
      scheduled = false;
      sweep();
    }, 45);
  }

  function start() {
    ensureTray();
    sweep();

    new MutationObserver(scheduleSweep).observe(
      document.body,
      {
        childList: true,
        subtree: true
      }
    );

    const language = languageCard();
    const menu = menuCard();

    if ("ResizeObserver" in window) {
      const observer = new ResizeObserver(positionTray);

      if (language) {
        observer.observe(language);
      }

      if (menu) {
        observer.observe(menu);
      }

      screenControlCards(menu).forEach(control => {
        observer.observe(control);
      });
    }

    window.addEventListener(
      "resize",
      positionTray,
      { passive: true }
    );

    window.addEventListener(
      "scroll",
      positionTray,
      {
        passive: true,
        capture: true
      }
    );

    window.setTimeout(sweep, 250);
    window.setTimeout(sweep, 900);
    window.setTimeout(sweep, 2200);
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
/* PINCABOS_ALL_NOTIFICATIONS_UNDER_LANGUAGE_V14 */
;(() => {
  'use strict';

  if (window.__PINCABOS_ALL_NOTIFICATIONS_UNDER_LANGUAGE_V14__) {
    return;
  }

  window.__PINCABOS_ALL_NOTIFICATIONS_UNDER_LANGUAGE_V14__ = true;

  const ROOT_ID = 'pco-impexp-live-overlay-root';
  const CARD_ID = 'pcos-global-system-notice-v14';
  const STYLE_ID = 'pcos-global-system-notice-style-v14';

  /*
   * Messages dynamiques seulement.
   * Les cartes d'information statiques ne sont pas déplacées.
   */
  const MESSAGE_SELECTOR = [
    '#pco-bi-message',
    '#pco-be-message',
    '#pco-smart-import-message',
    '#pco-smart-export-message',
    '.pco-ie-note[aria-live]',
    '[role="alert"]',
    '.flash-message',
    '.pincabos-notification',
    '.pincabos-runtime-message'
  ].join(',');

  let closeTimer = null;

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function installStyle() {
    if (document.getElementById(STYLE_ID)) {
      return;
    }

    const style = document.createElement('style');
    style.id = STYLE_ID;

    style.textContent = `
      /*
       * Les messages locaux Import/Export ne doivent plus apparaître
       * dans les grandes cartes de contenu.
       */
      #pco-bi-message,
      #pco-be-message,
      #pco-smart-import-message,
      #pco-smart-export-message {
        display: none !important;
      }

      #${CARD_ID} {
        display: none;
        width: 100%;
        box-sizing: border-box;
        overflow: hidden;
        padding: 10px 11px;
        border: 1px solid rgba(255, 154, 54, .82);
        border-radius: 10px;
        background:
          linear-gradient(
            125deg,
            rgba(48, 20, 11, .98),
            rgba(39, 13, 48, .98)
          );
        box-shadow:
          inset 0 0 18px rgba(0, 0, 0, .30),
          0 8px 24px rgba(0, 0, 0, .32);
        color: #fff;
        text-align: left;
      }

      #${CARD_ID}[aria-hidden="false"] {
        display: block;
      }

      #${CARD_ID}[data-kind="error"] {
        border-color: rgba(255, 82, 98, .92);
        background:
          linear-gradient(
            125deg,
            rgba(66, 13, 20, .98),
            rgba(48, 12, 43, .98)
          );
      }

      #${CARD_ID}[data-kind="warning"] {
        border-color: rgba(255, 176, 52, .95);
      }

      #${CARD_ID}[data-kind="success"] {
        border-color: rgba(71, 214, 133, .88);
        background:
          linear-gradient(
            125deg,
            rgba(11, 50, 37, .98),
            rgba(27, 17, 51, .98)
          );
      }

      #${CARD_ID} .pcos-global-notice-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
      }

      #${CARD_ID} .pcos-global-notice-title {
        display: flex;
        align-items: center;
        gap: 7px;
        color: #fff0dd;
        font-size: .73rem;
        font-weight: 900;
        letter-spacing: .055em;
        text-transform: uppercase;
      }

      #${CARD_ID} .pcos-global-notice-dot {
        width: 8px;
        height: 8px;
        flex: 0 0 auto;
        border-radius: 50%;
        background: #ff9a36;
        box-shadow: 0 0 0 4px rgba(255, 154, 54, .16);
      }

      #${CARD_ID}[data-kind="error"] .pcos-global-notice-dot {
        background: #ff5262;
        box-shadow: 0 0 0 4px rgba(255, 82, 98, .17);
      }

      #${CARD_ID}[data-kind="success"] .pcos-global-notice-dot {
        background: #47d685;
        box-shadow: 0 0 0 4px rgba(71, 214, 133, .16);
      }

      #${CARD_ID} .pcos-global-notice-close {
        border: 0;
        background: transparent;
        color: #fff;
        cursor: pointer;
        font-size: 1rem;
        font-weight: 900;
        line-height: 1;
        opacity: .78;
      }

      #${CARD_ID} .pcos-global-notice-close:hover {
        opacity: 1;
      }

      #${CARD_ID} .pcos-global-notice-text {
        margin-top: 6px;
        color: #fff;
        font-size: .80rem;
        font-weight: 700;
        line-height: 1.3;
        overflow-wrap: anywhere;
      }
    `;

    document.head.appendChild(style);
  }

  function getRoot() {
    let root = document.getElementById(ROOT_ID);

    if (root) {
      return root;
    }

    root = document.createElement('div');
    root.id = ROOT_ID;
    root.setAttribute('aria-live', 'polite');
    document.body.appendChild(root);

    return root;
  }

  function rootHasVisibleCards(root) {
    return Array.from(
      root.querySelectorAll('.pco-impexp-menu-status')
    ).some((node) => {
      return (
        node.getAttribute('aria-hidden') === 'false' &&
        !node.hidden
      );
    });
  }

  function syncRoot() {
    const root = document.getElementById(ROOT_ID);

    if (!root) {
      return;
    }

    root.classList.toggle(
      'is-active',
      rootHasVisibleCards(root)
    );
  }

  function hideNotice() {
    const card = document.getElementById(CARD_ID);

    if (closeTimer) {
      window.clearTimeout(closeTimer);
      closeTimer = null;
    }

    if (card) {
      card.setAttribute('aria-hidden', 'true');
    }

    syncRoot();
  }

  function normalizeKind(kind, message) {
    const requested = String(kind || '').toLowerCase();
    const lower = String(message || '').toLowerCase();

    if (
      requested === 'error' ||
      /erreur|échec|impossible|failed|failure|nogo|refus/.test(lower)
    ) {
      return 'error';
    }

    if (
      requested === 'warning' ||
      /attention|avertissement|warning/.test(lower)
    ) {
      return 'warning';
    }

    if (
      requested === 'success' ||
      /terminé|réussi|succès|success|go \[/.test(lower)
    ) {
      return 'success';
    }

    return 'info';
  }

  function kindTitle(kind) {
    if (kind === 'error') {
      return 'Erreur';
    }

    if (kind === 'warning') {
      return 'Avertissement';
    }

    if (kind === 'success') {
      return 'Terminé';
    }

    return 'Information';
  }

  function showNotice(message, kind = 'info', timeout = null) {
    const text = String(message || '').trim();

    if (!text) {
      return;
    }

    installStyle();

    const normalizedKind = normalizeKind(kind, text);
    const root = getRoot();

    let card = document.getElementById(CARD_ID);

    if (!card) {
      card = document.createElement('div');
      card.id = CARD_ID;
      card.className =
        'pco-impexp-menu-status pco-global-system-notice';
      root.appendChild(card);
    }

    card.dataset.kind = normalizedKind;
    card.innerHTML = `
      <div class="pcos-global-notice-head">
        <div class="pcos-global-notice-title">
          <span class="pcos-global-notice-dot"></span>
          <span>${escapeHtml(kindTitle(normalizedKind))}</span>
        </div>

        <button
          class="pcos-global-notice-close"
          type="button"
          aria-label="Fermer"
          title="Fermer"
        >×</button>
      </div>

      <div class="pcos-global-notice-text">
        ${escapeHtml(text)}
      </div>
    `;

    card
      .querySelector('.pcos-global-notice-close')
      .addEventListener('click', hideNotice);

    card.setAttribute('aria-hidden', 'false');
    root.classList.add('is-active');

    if (closeTimer) {
      window.clearTimeout(closeTimer);
    }

    const requestedTimeout = Number(timeout);
    const duration = Number.isFinite(requestedTimeout)
      ? requestedTimeout
      : normalizedKind === 'error'
        ? 16000
        : normalizedKind === 'warning'
          ? 13000
          : 9000;

    if (duration > 0) {
      closeTimer = window.setTimeout(
        hideNotice,
        duration
      );
    }
  }

  /*
   * API globale utilisable par tous les modules PinCabOS.
   */
  window.PinCabOSNotify = showNotice;

  window.addEventListener(
    'pincabos:notify',
    (event) => {
      const detail = event?.detail || {};

      showNotice(
        detail.message || detail.text || '',
        detail.kind || detail.type || 'info',
        detail.timeout
      );
    }
  );

  /*
   * Toutes les alert() JavaScript vont aussi sous Langue.
   */
  window.alert = (message) => {
    showNotice(message, 'error', 16000);
  };

  function isUploadProgressMessage(text) {
    const lower = text.toLowerCase();

    return (
      lower.startsWith('téléversement de ') ||
      lower.includes('suis la progression dans le menu') ||
      lower.includes('progression affichée dans le menu') ||
      lower.startsWith('import démarré')
    );
  }

  function harvestMessage(node) {
    if (!(node instanceof Element)) {
      return;
    }

    if (!node.matches(MESSAGE_SELECTOR)) {
      return;
    }

    if (node.closest(`#${ROOT_ID}`)) {
      return;
    }

    if (node.hidden) {
      return;
    }

    const text = String(node.textContent || '').trim();

    if (!text) {
      return;
    }

    if (node.dataset.pcosMovedMessage === text) {
      node.hidden = true;
      node.setAttribute('aria-hidden', 'true');
      return;
    }

    node.dataset.pcosMovedMessage = text;

    /*
     * Le message local est toujours retiré.
     */
    node.hidden = true;
    node.setAttribute('aria-hidden', 'true');

    /*
     * Le téléversement est déjà représenté par la carte de progression.
     * On évite donc une deuxième carte identique.
     */
    if (isUploadProgressMessage(text)) {
      return;
    }

    const kind = normalizeKind(
      node.dataset.kind ||
      node.dataset.type ||
      '',
      text
    );

    showNotice(text, kind);
  }

  function inspectNode(node) {
    if (!(node instanceof Element)) {
      return;
    }

    harvestMessage(node);

    node
      .querySelectorAll(MESSAGE_SELECTOR)
      .forEach(harvestMessage);
  }

  const observer = new MutationObserver((records) => {
    for (const record of records) {
      if (record.type === 'characterData') {
        const parent = record.target.parentElement;

        if (parent) {
          harvestMessage(parent);
        }

        continue;
      }

      if (record.target instanceof Element) {
        harvestMessage(record.target);
      }

      for (const added of record.addedNodes) {
        inspectNode(added);
      }
    }
  });

  function start() {
    installStyle();

    observer.observe(document.documentElement, {
      subtree: true,
      childList: true,
      characterData: true,
      attributes: true,
      attributeFilter: [
        'hidden',
        'class',
        'aria-hidden'
      ]
    });

    /*
     * Déplace aussi une alerte déjà rendue au chargement.
     */
    document
      .querySelectorAll(MESSAGE_SELECTOR)
      .forEach((node) => {
        if (!node.hidden) {
          harvestMessage(node);
        }
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener(
      'DOMContentLoaded',
      start,
      {once: true}
    );
  } else {
    start();
  }
})();

/* PINCABOS_BATCH_IMPORT_SINGLE_STATUS_UNDER_LANGUAGE_V31 */
(() => {
  "use strict";
  if (window.__pcosBatchImportSingleStatusUnderLanguageV31) return;
  window.__pcosBatchImportSingleStatusUnderLanguageV31 = true;

  const ACTIVE = "pcos-biq-v2-card";
  const LEGACY = "pcos-bip-language-status";
  const TRAY = "pco-system-message-tray";
  const LIST = "pco-system-message-tray-list";
  const STYLE = "pcos-batch-v31-style";
  let timer = 0;

  function ensureStyle() {
    if (document.getElementById(STYLE)) return;
    const s = document.createElement("style");
    s.id = STYLE;
    s.textContent = `
      #${LEGACY}{
        display:none!important;
        visibility:hidden!important;
        opacity:0!important;
        pointer-events:none!important
      }
      #${LIST}>#${ACTIVE}{
        display:none;
        width:100%!important;
        min-width:0!important;
        max-width:100%!important;
        margin:0!important;
        padding:8px 10px!important;
        overflow:hidden!important;
        box-sizing:border-box!important;
        border:1px solid rgba(255,137,35,.76)!important;
        border-radius:10px!important;
        background:linear-gradient(135deg,rgba(126,50,11,.98),rgba(72,26,8,.98))!important;
        color:#fff7ef!important;
        font-size:11px!important;
        line-height:1.2!important
      }
      #${LIST}>#${ACTIVE}[data-visible="1"]{display:block!important}
      #${ACTIVE} .pcos-biq-head{
        display:flex!important;
        align-items:center!important;
        gap:7px!important;
        width:100%!important;
        min-width:0!important
      }
      #${ACTIVE} .pcos-biq-head strong{
        flex:1 1 auto!important;
        min-width:0!important;
        overflow:hidden!important;
        text-overflow:ellipsis!important;
        white-space:nowrap!important
      }
      #${ACTIVE} .pcos-biq-state{
        flex:0 0 auto!important;
        margin-left:auto!important;
        white-space:nowrap!important
      }
      #${ACTIVE} .pcos-biq-detail{
        display:block!important;
        width:100%!important;
        min-width:0!important;
        max-width:100%!important;
        margin-top:4px!important;
        overflow:hidden!important;
        text-overflow:ellipsis!important;
        white-space:nowrap!important
      }
      #${ACTIVE} .pcos-biq-bar{
        width:100%!important;
        height:4px!important;
        margin-top:6px!important;
        overflow:hidden!important;
        border-radius:999px!important;
        background:rgba(255,255,255,.16)!important
      }
      #${ACTIVE} .pcos-biq-actions{
        display:flex!important;
        justify-content:flex-end!important;
        gap:6px!important;
        margin-top:6px!important
      }
      #${ACTIVE} .pcos-biq-actions button{
        min-height:0!important;
        padding:4px 9px!important;
        border-radius:8px!important;
        font-size:10px!important;
        line-height:1.1!important
      }
      #${TRAY}[data-pcos-batch-active="1"]{
        display:block!important;
        visibility:visible!important;
        opacity:1!important
      }
      #${TRAY}[data-pcos-batch-active="1"][hidden]{display:block!important}
    `;
    document.head.appendChild(s);
  }

  function textOf(node){
    return String(node?.textContent || "").replace(/\s+/g," ").trim().toLowerCase();
  }

  function removeFakeNotices(){
    const list=document.getElementById(LIST);
    if(!list) return;
    Array.from(list.children).forEach(node=>{
      if(node.id===ACTIVE) return;
      const t=textOf(node);
      if(
        node.id==="pco-bi-message" ||
        t.includes("téléversement") ||
        t.includes("televersement") ||
        t.includes("en attente du package suivant") ||
        t.includes("traitement du package suivant")
      ){
        node.remove();
      }
    });
  }

  function hideLegacy(){
    const legacy=document.getElementById(LEGACY);
    if(!legacy) return;
    legacy.hidden=true;
    legacy.setAttribute("aria-hidden","true");
    legacy.style.setProperty("display","none","important");

    const slot=legacy.closest("#pco-impexp-live-menu-slot,.pco-impexp-live-menu-slot");
    if(!slot) return;

    const other=Array.from(slot.querySelectorAll(".pco-impexp-menu-status"))
      .some(n=>n.id!==LEGACY && n.getAttribute("aria-hidden")!=="true" && !n.hidden);

    if(!other){
      slot.classList.remove("is-active");
      slot.style.setProperty("display","none","important");
      const row=slot.closest(".pco-impexp-live-menu-row");
      if(row){
        row.classList.remove("is-active");
        row.style.setProperty("display","none","important");
      }
    }
  }

  function moveCard(){
    const card=document.getElementById(ACTIVE);
    const tray=document.getElementById(TRAY);
    const list=document.getElementById(LIST);
    if(!card || !tray || !list) return;

    if(card.parentElement!==list) list.prepend(card);

    const active=
      card.dataset.visible==="1" ||
      card.getAttribute("aria-hidden")==="false" ||
      (!card.hidden && card.offsetParent!==null);

    if(active){
      card.hidden=false;
      tray.hidden=false;
      tray.dataset.pcosBatchActive="1";
    }else{
      delete tray.dataset.pcosBatchActive;
    }
  }

  function sync(){
    ensureStyle();
    removeFakeNotices();
    hideLegacy();
    moveCard();
  }

  function schedule(){
    clearTimeout(timer);
    timer=setTimeout(sync,25);
  }

  function start(){
    sync();
    new MutationObserver(schedule).observe(document.documentElement,{
      childList:true,
      subtree:true,
      attributes:true,
      attributeFilter:["data-visible","aria-hidden","hidden","class","style"]
    });
    setInterval(sync,500);
  }

  if(document.readyState==="loading"){
    document.addEventListener("DOMContentLoaded",start,{once:true});
  }else{
    start();
  }
})();

/* PINCABOS_BATCH_SERVICE_WIDGET_SINGLE_POLLER_V3 */
(() => {
  "use strict";

  if (window.__pcosBatchServiceWidgetSinglePollerV3) return;
  window.__pcosBatchServiceWidgetSinglePollerV3 = true;

  /*
   * Bloque le correctif V2 lorsqu’il est injecté après ce fichier.
   * L’ancien poller Dashboard est aussi désactivé dans sa source Python.
   */
  window.__pcosBatchServiceWidgetFixV2 = true;

  const activeStates = new Set([
    "uploading",
    "queued",
    "running",
    "stopping"
  ]);

  const cache = {
    import: null,
    export: null
  };

  let inFlight = false;
  let renderScheduled = false;
  let observer = null;

  function root() {
    return document.getElementById("pco-dashboard-batch-controls");
  }

  function row(kind) {
    return root()?.querySelector(
      `[data-pco-batch-kind="${kind}"]`
    ) || null;
  }

  function stateLabel(state) {
    return ({
      uploading: "Téléversement",
      queued: "En file",
      running: "Actif",
      stopping: "Arrêt demandé",
      completed: "Terminé",
      completed_with_warning: "Avertissement",
      failed: "Erreur",
      stopped: "Arrêté"
    })[state] || "Disponible";
  }

  async function json(url, options = {}) {
    const response = await fetch(url, {
      cache: "no-store",
      credentials: "same-origin",
      headers: {
        "Accept": "application/json",
        ...(options.headers || {})
      },
      ...options
    });

    let data = {};

    try {
      data = await response.json();
    } catch (_) {}

    if (!response.ok || data.ok === false) {
      throw new Error(
        data.error || `HTTP ${response.status}`
      );
    }

    return data;
  }

  function text(node, value) {
    if (!node) return;

    const next = String(value ?? "");

    if (node.textContent !== next) {
      node.textContent = next;
    }
  }

  function title(node, value) {
    if (!node) return;

    const next = String(value ?? "");

    if (node.title !== next) {
      node.title = next;
    }
  }

  function hidden(node, value) {
    if (!node) return;

    const next = Boolean(value);

    if (node.hidden !== next) {
      node.hidden = next;
    }
  }

  function disabled(node, value) {
    if (!node) return;

    const next = Boolean(value);

    if (node.disabled !== next) {
      node.disabled = next;
    }
  }

  function activeClass(node, active) {
    if (!node) return;

    if (node.classList.contains("is-active") !== active) {
      node.classList.toggle("is-active", active);
    }
  }

  function render(kind, packet) {
    const target = row(kind);
    if (!target) return;

    const job = packet?.job || null;
    const error = String(packet?.error || "");
    const state = String(job?.state || "").toLowerCase();
    const active = Boolean(
      job?.id && activeStates.has(state)
    );
    const progress = job?.progress || {};

    const status = target.querySelector(
      "[data-pco-batch-state]"
    );
    const detail = target.querySelector(
      "[data-pco-batch-detail]"
    );
    const open = target.querySelector(
      "[data-pco-batch-open]"
    );
    const stop = target.querySelector(
      "[data-pco-batch-stop]"
    );

    activeClass(target, active);

    if (error && !job) {
      text(status, "API indisponible");
      text(detail, error);
      title(detail, error);
      text(open, "Ouvrir");
      hidden(stop, true);
      return;
    }

    text(status, stateLabel(state));

    let detailText = "";

    if (!job) {
      detailText = kind === "import"
        ? "Worker prêt · aucun job."
        : "Aucun job en cours.";
    } else {
      const done = Number(
        progress.completed
        ?? job.processed_archives
        ?? job.completed_tables
        ?? 0
      );

      const total = Number(
        progress.total
        ?? job.total_archives
        ?? job.total_tables
        ?? 0
      );

      const current = String(
        progress.current_item
        || job.current_item
        || job.current_table
        || ""
      );

      detailText = [
        progress.label || stateLabel(state),
        total ? `${done}/${total}` : "",
        current,
        job.error || ""
      ].filter(Boolean).join(" · ");
    }

    text(detail, detailText);
    title(detail, detailText);
    text(open, active ? "Voir tâche" : "Ouvrir");

    hidden(stop, !active);
    disabled(stop, state === "stopping");
    text(
      stop,
      state === "stopping" ? "Arrêt…" : "Stop"
    );
  }

  function renderAll() {
    render("import", cache.import);
    render("export", cache.export);
  }

  function scheduleRender() {
    if (renderScheduled) return;

    renderScheduled = true;

    queueMicrotask(() => {
      renderScheduled = false;
      renderAll();
    });
  }

  async function load(kind) {
    const history = await json(
      `/api/batch-${kind}/live/history`
    );

    let job = null;

    if (history.active_job_id) {
      const status = await json(
        `/api/batch-${kind}/live/status/`
        + encodeURIComponent(history.active_job_id)
      );

      job = status.job || null;
    } else {
      job = (history.jobs || [])[0] || null;
    }

    return {
      job,
      error: ""
    };
  }

  async function refreshAll() {
    if (inFlight) return;

    inFlight = true;

    try {
      const results = await Promise.allSettled([
        load("import"),
        load("export")
      ]);

      const kinds = ["import", "export"];

      results.forEach((result, index) => {
        const kind = kinds[index];

        if (result.status === "fulfilled") {
          cache[kind] = result.value;
          return;
        }

        /*
         * Une erreur passagère ne doit pas effacer un état valide
         * et ne doit jamais provoquer de clignotement.
         */
        if (!cache[kind]?.job) {
          cache[kind] = {
            job: null,
            error:
              "État temporairement indisponible : "
              + String(
                result.reason?.message
                || result.reason
                || "API"
              )
          };
        }
      });

      renderAll();
    } finally {
      inFlight = false;
    }
  }

  async function stop(kind, button) {
    const job = cache[kind]?.job;

    if (!job?.id) return;

    disabled(button, true);
    text(button, "Arrêt…");

    try {
      const data = await json(
        `/api/batch-${kind}/live/stop/`
        + encodeURIComponent(job.id),
        {
          method: "POST"
        }
      );

      cache[kind] = {
        job: data.job || job,
        error: ""
      };

      render(kind, cache[kind]);
      await refreshAll();
    } catch (error) {
      cache[kind] = {
        job,
        error:
          "Arrêt impossible : "
          + String(error.message || error)
      };

      render(kind, cache[kind]);
    }
  }

  document.addEventListener("click", event => {
    const refreshButton = event.target.closest?.(
      "#pco-dashboard-batch-controls "
      + "[data-pco-batch-refresh]"
    );

    if (refreshButton) {
      event.preventDefault();
      event.stopImmediatePropagation();
      refreshAll();
      return;
    }

    const stopButton = event.target.closest?.(
      "#pco-dashboard-batch-controls "
      + "[data-pco-batch-stop]"
    );

    if (!stopButton) return;

    event.preventDefault();
    event.stopImmediatePropagation();

    const kind = stopButton
      .closest("[data-pco-batch-kind]")
      ?.dataset.pcoBatchKind;

    if (kind === "import" || kind === "export") {
      stop(kind, stopButton);
    }
  }, true);

  function observe() {
    if (observer) return;

    observer = new MutationObserver(mutations => {
      if (!root()) return;

      const touchedBatchWidget = mutations.some(
        mutation => (
          mutation.target?.closest?.(
            "#pco-dashboard-batch-controls"
          )
          || Array.from(mutation.addedNodes || []).some(
            node => (
              node.nodeType === 1
              && (
                node.id === "pco-dashboard-batch-controls"
                || node.querySelector?.(
                  "#pco-dashboard-batch-controls"
                )
              )
            )
          )
        )
      );

      if (touchedBatchWidget) {
        scheduleRender();
      }
    });

    observer.observe(document.documentElement, {
      childList: true,
      subtree: true,
      attributes: true,
      characterData: true,
      attributeFilter: [
        "class",
        "hidden",
        "disabled",
        "title"
      ]
    });
  }

  function start() {
    observe();
    refreshAll();

    window.setInterval(() => {
      if (root() && !document.hidden) {
        refreshAll();
      }
    }, 2000);

    document.addEventListener(
      "visibilitychange",
      () => {
        if (!document.hidden) refreshAll();
      }
    );

    window.addEventListener(
      "pcos-batch-import-started",
      refreshAll
    );

    window.addEventListener(
      "pcos-batch-live-started",
      refreshAll
    );
  }

  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded",
      start,
      {once: true}
    );
  } else {
    start();
  }
})();

/* PINCABOS_SYSTEM_MESSAGES_AUTOSIZE_V5_JS_BEGIN */
(() => {
    "use strict";

    const TRAY_ID = "pco-system-message-tray";
    const LIST_ID = "pco-system-message-tray-list";
    const PARENT_CLASS = "pco-system-message-autosize-parent";

    let scheduled = false;

    function forceAutoSize(element) {
        if (!(element instanceof HTMLElement)) {
            return;
        }

        const properties = {
            height: "auto",
            minHeight: "0",
            maxHeight: "none",
            overflow: "visible",
            overflowY: "visible",
            overflowX: "hidden",
            scrollbarWidth: "none",
            flex: "0 0 auto"
        };

        for (const [name, value] of Object.entries(properties)) {
            element.style.setProperty(
                name.replace(/[A-Z]/g, letter => `-${letter.toLowerCase()}`),
                value,
                "important"
            );
        }
    }

    function isRestrictiveWrapper(element) {
        if (!(element instanceof HTMLElement)) {
            return false;
        }

        const style = window.getComputedStyle(element);
        const overflowY = style.overflowY;
        const maxHeight = style.maxHeight;
        const height = style.height;

        const scrollsInternally =
            overflowY === "auto" ||
            overflowY === "scroll";

        const clipsContent =
            element.clientHeight > 0 &&
            element.scrollHeight > element.clientHeight + 2;

        const hasMaximum =
            maxHeight !== "none" &&
            maxHeight !== "0px";

        const hasFixedPixelHeight =
            /^\d+(?:\.\d+)?px$/.test(height) &&
            element.scrollHeight > element.clientHeight + 2;

        return (
            scrollsInternally ||
            clipsContent ||
            hasMaximum ||
            hasFixedPixelHeight
        );
    }

    function repairParents(tray) {
        let parent = tray.parentElement;
        let depth = 0;

        while (
            parent &&
            parent !== document.body &&
            parent !== document.documentElement &&
            depth < 5
        ) {
            const identity = [
                parent.id || "",
                typeof parent.className === "string"
                    ? parent.className
                    : ""
            ].join(" ");

            const looksLikeContainer =
                /(card|panel|menu|tray|notification|message|system|body|content|section|widget)/i
                    .test(identity);

            if (
                isRestrictiveWrapper(parent) &&
                (looksLikeContainer || depth <= 2)
            ) {
                parent.classList.add(PARENT_CLASS);
                forceAutoSize(parent);
            }

            parent = parent.parentElement;
            depth += 1;
        }
    }

    function applyAutoSize() {
        scheduled = false;

        const tray = document.getElementById(TRAY_ID);
        const list = document.getElementById(LIST_ID);

        if (!tray && !list) {
            return;
        }

        forceAutoSize(tray);
        forceAutoSize(list);

        if (tray) {
            repairParents(tray);
        }

        if (list) {
            for (const child of list.children) {
                forceAutoSize(child);
                child.style.setProperty(
                    "white-space",
                    "normal",
                    "important"
                );
                child.style.setProperty(
                    "overflow-wrap",
                    "anywhere",
                    "important"
                );
            }
        }
    }

    function scheduleAutoSize() {
        if (scheduled) {
            return;
        }

        scheduled = true;

        window.requestAnimationFrame(() => {
            window.setTimeout(applyAutoSize, 25);
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener(
            "DOMContentLoaded",
            scheduleAutoSize,
            { once: true }
        );
    } else {
        scheduleAutoSize();
    }

    const observer = new MutationObserver(scheduleAutoSize);

    /*
     * On surveille seulement l'ajout et le retrait de notifications.
     * Ne pas surveiller l'attribut style évite une boucle causée par
     * les styles appliqués par ce correctif.
     */
    observer.observe(document.documentElement, {
        childList: true,
        subtree: true
    });

    window.addEventListener("resize", scheduleAutoSize);
    window.addEventListener("load", scheduleAutoSize);
})();
/* PINCABOS_SYSTEM_MESSAGES_AUTOSIZE_V5_JS_END */
