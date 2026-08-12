(()=>{
  'use strict';
  if (window.__PCO_KEYBOARD_TOOLS_V7__) return;
  window.__PCO_KEYBOARD_TOOLS_V7__ = true;

  const PATH = '/keyboard';
  const IMAGE = '/static/pincabos-assets/PCOSKeyboard.png';
  const TITLE = 'Clavier système';
  const DESCRIPTION = 'Changer la disposition clavier : US, FR et internationale.';
  const ACTION = 'Ouvrir Clavier système';
  const norm = value => String(value || '').replace(/\s+/g, ' ').trim().toLowerCase();
  const cardLike = node => {
    if (!node || node === document.body) return false;
    if (node.matches('article,li')) return true;
    const classes = typeof node.className === 'string' ? node.className : '';
    return /(^|\s)(tool-card|tools-card|feature-card|action-card|card)(\s|$)/i.test(classes);
  };

  function cardRoot(node) {
    let current = node;
    while (current && current !== document.body) {
      if (cardLike(current)) return current;
      if (current.matches && current.matches('a[href]') && current.querySelector('img')) return current;
      current = current.parentElement;
    }
    return node && node.matches && node.matches('a[href]') ? node : null;
  }

  function leafWithText(root, matcher) {
    return [...root.querySelectorAll('*')].reverse().find(node => {
      const value = norm(node.textContent);
      return node.children.length === 0 && matcher.test(value);
    }) || null;
  }

  function setImage(root) {
    let image = root.querySelector('img');
    if (!image) {
      image = document.createElement('img');
      image.loading = 'lazy';
      image.decoding = 'async';
      const target = root.querySelector('a[href]') || root;
      target.insertBefore(image, target.firstChild);
    }
    image.src = IMAGE;
    image.alt = TITLE;
  }

  function rewriteCard(root) {
    if (!root) return;
    root.dataset.pcoTool = 'keyboard';
    root.querySelectorAll('[id]').forEach(node => node.removeAttribute('id'));
    if (root.matches('a[href]')) root.href = PATH;
    root.querySelectorAll('a[href]').forEach(link => { link.href = PATH; });

    const heading = leafWithText(root, /apparence|import|export|map commander|dof commander|explorer|console|disques/) ||
      [...root.querySelectorAll('h1,h2,h3,h4,h5,strong,b')].find(node => norm(node.textContent));
    if (heading) heading.textContent = TITLE;

    const description = [...root.querySelectorAll('p,small,span,div')].find(node => {
      const value = norm(node.textContent);
      return node.children.length === 0 && value.length > 18 &&
        !/ouvrir|gérer|personnaliser|configuration|→/.test(value);
    });
    if (description) description.textContent = DESCRIPTION;

    const action = leafWithText(root, /^(personnaliser|ouvrir|gérer|lancer|open)/) ||
      leafWithText(root, /apparence|import|export|explorer|console|disques/);
    if (action && action !== heading && action !== description) action.textContent = ACTION;

    setImage(root);
  }

  function existingKeyboardCard() {
    const link = [...document.querySelectorAll('a[href]')].find(anchor => {
      const href = anchor.getAttribute('href') || '';
      return href === PATH || href.endsWith(PATH) || norm(anchor.textContent).includes('clavier système');
    });
    return cardRoot(link);
  }

  function appearanceSourceCard() {
    const link = [...document.querySelectorAll('a[href]')].find(anchor => {
      const all = `${anchor.getAttribute('href') || ''} ${anchor.textContent || ''}`;
      return /appearance|apparence/i.test(all);
    });
    if (link) return cardRoot(link);

    const title = [...document.querySelectorAll('h1,h2,h3,h4,h5,strong,b,span,div')].find(node => {
      const value = norm(node.textContent);
      return node.children.length === 0 && (value === 'apparence pincabos' || value.includes('apparence pincabos'));
    });
    return cardRoot(title);
  }

  function ensureKeyboardCard() {
    if (location.pathname !== '/tools') return true;

    const existing = existingKeyboardCard();
    if (existing) {
      rewriteCard(existing);
      return true;
    }

    const source = appearanceSourceCard();
    if (!source || !source.parentElement) return false;

    const clone = source.cloneNode(true);
    rewriteCard(clone);
    source.insertAdjacentElement('afterend', clone);
    return true;
  }

  function start() {
    if (ensureKeyboardCard()) return;
    let tries = 0;
    const observer = new MutationObserver(() => {
      if (ensureKeyboardCard() || ++tries > 25) observer.disconnect();
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
    setTimeout(() => observer.disconnect(), 5000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, { once: true });
  } else {
    start();
  }
})();
