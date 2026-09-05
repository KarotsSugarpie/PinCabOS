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

  function lastIndex() {
    try {
      return Number.parseInt(sessionStorage.getItem(STORAGE_KEY) || '-1', 10);
    } catch (_) {
      return -1;
    }
  }

  function remember(index) {
    try {
      sessionStorage.setItem(STORAGE_KEY, String(index));
    } catch (_) {}
  }

  function candidateOrder() {
    const last = lastIndex();
    const indexes = BACKGROUNDS.map((_, i) => i);

    for (let i = indexes.length - 1; i > 0; i -= 1) {
      const j = Math.floor(Math.random() * (i + 1));
      [indexes[i], indexes[j]] = [indexes[j], indexes[i]];
    }

    if (indexes.length > 1 && indexes[0] === last) {
      [indexes[0], indexes[1]] = [indexes[1], indexes[0]];
    }

    return indexes;
  }

  function imageExists(url) {
    return new Promise((resolve) => {
      const image = new Image();
      image.onload = () => resolve(true);
      image.onerror = () => resolve(false);
      image.src = url;
    });
  }

  function ensureStyle() {
    if (document.getElementById('pincabos-random-background-style-v1')) return;

    const style = document.createElement('style');
    style.id = 'pincabos-random-background-style-v1';
    style.textContent = `
      html {
        min-height: 100%;
      }

      html body.pincabos-random-background-v1 {
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
        html body.pincabos-random-background-v1 {
          background-attachment: scroll !important;
        }
      }
    `;
    document.head.appendChild(style);
  }

  async function applyRandomBackground() {
    ensureStyle();

    for (const index of candidateOrder()) {
      const url = BACKGROUNDS[index];
      if (url === currentUrl && BACKGROUNDS.length > 1) continue;
      if (!(await imageExists(url))) continue;

      currentUrl = url;
      remember(index);
      document.documentElement.style.setProperty(
        '--pincabos-random-background-v1',
        `url("${url}")`
      );
      document.body.classList.add('pincabos-random-background-v1');
      return;
    }

    // Assets absents: conserver le fond historique de la WebApp.
    document.body.classList.remove('pincabos-random-background-v1');
    document.documentElement.style.removeProperty('--pincabos-random-background-v1');
  }

  function installNavigationHooks() {
    ['pushState', 'replaceState'].forEach((method) => {
      const original = history[method];
      if (typeof original !== 'function' || original.__pincabosBgWrapped) return;

      const wrapped = function () {
        const result = original.apply(this, arguments);
        window.setTimeout(() => { void applyRandomBackground(); }, 0);
        return result;
      };

      wrapped.__pincabosBgWrapped = true;
      history[method] = wrapped;
    });

    window.addEventListener('popstate', () => { void applyRandomBackground(); });
  }

  function init() {
    void applyRandomBackground();
    installNavigationHooks();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();
