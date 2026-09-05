(function () {
  'use strict';

  const BACKGROUNDS = [
    '/static/pincabos-assets/background/background-01.webp',
    '/static/pincabos-assets/background/background-02.webp',
    '/static/pincabos-assets/background/background-03.webp',
    '/static/pincabos-assets/background/background-04.webp',
    '/static/pincabos-assets/background/background-05.webp'
  ];

  const STORAGE_KEY = 'pincabos.background.last.v1';
  let currentUrl = '';

  function pickBackground() {
    if (BACKGROUNDS.length === 0) return '';

    let last = -1;
    try {
      last = Number.parseInt(sessionStorage.getItem(STORAGE_KEY) || '-1', 10);
    } catch (_) {}

    let index = Math.floor(Math.random() * BACKGROUNDS.length);

    if (BACKGROUNDS.length > 1 && index === last) {
      index = (index + 1 + Math.floor(Math.random() * (BACKGROUNDS.length - 1))) % BACKGROUNDS.length;
    }

    try {
      sessionStorage.setItem(STORAGE_KEY, String(index));
    } catch (_) {}

    return BACKGROUNDS[index];
  }

  function ensureStyle() {
    let style = document.getElementById('pincabos-random-background-style-v1');
    if (style) return style;

    style = document.createElement('style');
    style.id = 'pincabos-random-background-style-v1';
    style.textContent = `
      html {
        min-height: 100%;
        background: #07050b !important;
      }

      html body {
        min-height: 100vh;
        background-color: #07050b !important;
        background-image:
          linear-gradient(rgba(6, 5, 10, .34), rgba(6, 5, 10, .48)),
          var(--pincabos-random-background-v1) !important;
        background-size: cover !important;
        background-position: center center !important;
        background-repeat: no-repeat !important;
        background-attachment: fixed !important;
      }

      @media (max-width: 900px), (prefers-reduced-motion: reduce) {
        html body {
          background-attachment: scroll !important;
        }
      }
    `;
    document.head.appendChild(style);
    return style;
  }

  function applyRandomBackground() {
    ensureStyle();

    const url = pickBackground();
    if (url === '' || url === currentUrl) return;

    currentUrl = url;
    document.documentElement.style.setProperty(
      '--pincabos-random-background-v1',
      `url("${url}")`
    );
  }

  function installNavigationHooks() {
    ['pushState', 'replaceState'].forEach(function (method) {
      const original = history[method];
      if (typeof original !== 'function') return;
      if (original.__pincabosBgWrapped === true) return;

      const wrapped = function () {
        const result = original.apply(this, arguments);
        window.setTimeout(applyRandomBackground, 0);
        return result;
      };

      wrapped.__pincabosBgWrapped = true;
      history[method] = wrapped;
    });

    window.addEventListener('popstate', applyRandomBackground);
  }

  function init() {
    applyRandomBackground();
    installNavigationHooks();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();
