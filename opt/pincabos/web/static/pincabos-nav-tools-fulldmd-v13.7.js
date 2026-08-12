/* PinCabOS V13.8 — direct menu cleanup + standard cards for DMD / FullDMD in Outils VPX. */
(() => {
  'use strict';
  const normal = value => (value || '').replace(/\s+/g, ' ').trim().toLowerCase();
  const route = value => {
    try { return new URL(value || '', window.location.origin).pathname.replace(/\/+$/, '') || '/'; }
    catch (_) { return ''; }
  };

  function removeOutputsTopShortcut() {
    document.querySelectorAll('a,button,[role="button"]').forEach(el => {
      const r = route(el.getAttribute('href') || el.getAttribute('data-href') || '');
      const label = normal(el.textContent);
      const inNavigation = Boolean(el.closest('header,nav,[role="navigation"],.navbar,.topbar,.top-nav,.nav-menu,.main-menu,.toolbar,.menu'));
      if (inNavigation && (r === '/outputs' || label === 'outputs' || label === 'output')) {
        (el.closest('li') || el).remove();
      }
    });
  }

  function findVpxColumn() {
    const heading = [...document.querySelectorAll('h1,h2,h3,h4,h5,.section-title,.card-title,.tools-title,strong')]
      .find(el => normal(el.textContent) === 'outils vpx');
    if (!heading) return null;

    let node = heading.parentElement;
    for (let depth = 0; node && depth < 7; depth += 1, node = node.parentElement) {
      const links = [...node.querySelectorAll('a[href]')];
      const hasVpxItems = links.some(a => ['/gpu', '/audio', '/tools/vpx-ball-cabinet', '/tools/vpinball/ini'].includes(route(a.getAttribute('href'))));
      const avoidsOtherColumns = !normal(node.textContent).includes('outils pincabos') && !normal(node.textContent).includes('outils vpinfe');
      if (hasVpxItems && avoidsOtherColumns) return node;
    }
    return null;
  }

  function cardTemplate(column) {
    const links = [...column.querySelectorAll('a[href]')].filter(a => {
      const r = route(a.getAttribute('href'));
      return ['/gpu', '/audio', '/tools/vpx-ball-cabinet', '/tools/vpinball/ini'].includes(r);
    });
    return links.at(-1) || null;
  }

  function updateText(el, title, description, action) {
    const titleNode = [...el.querySelectorAll('h1,h2,h3,h4,h5,strong,b')].find(node => (node.textContent || '').trim().length > 2);
    if (titleNode) titleNode.textContent = title;

    const bodyNode = [...el.querySelectorAll('p,small,span,div')].find(node => {
      const t = (node.textContent || '').trim();
      return t.length > 25 && t.length < 240 && node.children.length === 0;
    });
    if (bodyNode) bodyNode.textContent = description;

    const actionNode = [...el.querySelectorAll('a,button,strong,b,span')].reverse().find(node => {
      const t = normal(node.textContent);
      return t.startsWith('ouvrir') || t === '→' || t === '>';
    });
    if (actionNode && actionNode !== titleNode) actionNode.textContent = action;
  }

  function addCard(column, spec) {
    if (document.getElementById(spec.id)) return;
    const template = cardTemplate(column);
    if (!template) return;
    const card = template.cloneNode(true);
    card.id = spec.id;
    card.href = spec.href;
    card.removeAttribute('onclick');
    card.querySelectorAll('img').forEach(img => {
      img.src = spec.image;
      img.alt = spec.title;
      img.style.objectFit = 'contain';
    });
    updateText(card, spec.title, spec.description, spec.action);
    template.parentElement.appendChild(card);
  }

  function installVpxTools() {
    const column = findVpxColumn();
    if (!column) return;
    addCard(column, {
      id: 'pco-tools-dmd-card',
      href: '/dmd-screen',
      image: '/static/pincabos-assets/PCOSEcransGPUVPX.png',
      title: 'DMD',
      description: 'Écran DMD et calibrage de l’affichage.',
      action: 'Ouvrir DMD'
    });
    addCard(column, {
      id: 'pco-tools-fulldmd-card',
      href: '/fulldmd',
      image: '/static/pincabos-assets/PCOSFullDMDConfigurator.png',
      title: 'FullDMD',
      description: 'Affichage et configuration FullDMD.',
      action: 'Ouvrir FullDMD'
    });
  }

  const apply = () => {
    removeOutputsTopShortcut();
    installVpxTools();
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', apply, { once: true });
  else apply();
  setTimeout(apply, 150);
  setTimeout(apply, 900);
})();
