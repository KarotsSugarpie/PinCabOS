/* PinCabOS V13.6 — hides only direct top-menu shortcuts now represented by tools. */
(() => {
  'use strict';
  const TARGETS = new Set(['/inputs', '/outputs']); /* PINCABOS_V17_KEEP_FULLDMD_TOOLCARD */
  const routeOf = (element) => {
    const raw = element.getAttribute?.('href') || element.getAttribute?.('data-href') || '';
    if (raw) {
      try { return new URL(raw, window.location.origin).pathname.replace(/\/+$/, '') || '/'; } catch (_) {}
    }
    const inline = element.getAttribute?.('onclick') || '';
    const match = inline.match(/['"](\/(?:inputs|outputs|fulldmd))\/?['"]/i);
    return match ? match[1].toLowerCase() : '';
  };
  const beforePrimaryContent = (element) => {
    const lobby = document.getElementById('pco-lobby');
    if (lobby?.contains(element)) return false;
    const primary = document.querySelector('main, #pco-lobby, .page-content, .content');
    if (!primary || !element.compareDocumentPosition) return Boolean(element.closest('nav, header, [class*="nav"], [class*="menu"], [class*="toolbar"]'));
    return Boolean(element.compareDocumentPosition(primary) & Node.DOCUMENT_POSITION_FOLLOWING)
      || Boolean(element.closest('nav, header, [class*="nav"], [class*="menu"], [class*="toolbar"]'));
  };
  const clean = () => {
    document.querySelectorAll('a, button, [role="button"]').forEach((element) => {
      if (!beforePrimaryContent(element)) return;
      const route = routeOf(element);
      const text = (element.textContent || '').replace(/\s+/g, ' ').trim().toLowerCase();
      const byRoute = TARGETS.has(route);
      const byText = ['inputs', 'outputs', 'fulldmd'].includes(text) && (route || element.hasAttribute('onclick'));
      if (!byRoute && !byText) return;
      const clickable = element.closest('a, button, [role="button"]') || element;
      clickable.remove();
    });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', clean, {once:true}); else clean();
  setTimeout(clean, 150);
  setTimeout(clean, 1000);
})();
