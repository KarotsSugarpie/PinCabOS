/* PinCabOS Dashboard Lobby V13 — native grid board, no external runtime dependency */
(() => {
  const cfg = window.PCO_LOBBY;
  if (!cfg) return;
  const root = document.getElementById('pco-lobby');
  const board = document.getElementById('pco-lobby-board');
  const templates = new Map([...document.querySelectorAll('template[data-pco-template]')].map(t => [t.dataset.pcoTemplate, t]));
  const deep = value => JSON.parse(JSON.stringify(value));
  let registry = cfg.registry || {};
  let layout = deep(cfg.layout || []);
  let savedLayout = deep(layout);
  let editing = false;
  let drag = null;
  let resize = null;
  let lastRemovedSlot = null; // PINCABOS_DASHBOARD_EDIT_REMOVED_SLOT_V1
  const cols = 12;
  const gap = () => parseFloat(getComputedStyle(board).gap || '12') || 12;
  const row = () => parseFloat(getComputedStyle(board).gridAutoRows || '50') || 50;
  const notify = message => {
    const old = root.querySelector('.pco-toast:not(.server)'); if (old) old.remove();
    const el = document.createElement('div'); el.className = 'pco-toast'; el.textContent = message; root.append(el);
    setTimeout(() => el.remove(), 3500);
  };
  const used = (except) => layout.filter(item => item.id !== except);
  const fits = (item, x, y, except) => {
    if (x < 0 || y < 0 || x + item.w > cols) return false;
    return !used(except).some(other => !(x + item.w <= other.x || other.x + other.w <= x || y + item.h <= other.y || other.y + other.h <= y));
  };
  const firstFit = (item, startX = 0, startY = 0, except = null) => {
    const maxY = 240;
    for (let y = Math.max(0, startY); y <= maxY; y++) {
      for (let x = (y === Math.max(0,startY) ? Math.max(0,startX) : 0); x <= cols - item.w; x++) {
        if (fits(item, x, y, except)) return {x, y};
      }
    }
    return {x: 0, y: Math.max(0, ...used(except).map(i => i.y + i.h), 0)};
  };
  const itemById = id => layout.find(item => item.id === id);
  const applyStyle = (el, item) => { el.style.gridColumn = `${item.x + 1} / span ${item.w}`; el.style.gridRow = `${item.y + 1} / span ${item.h}`; el.dataset.w = item.w; el.dataset.h = item.h; };
  const wireCard = (el, item) => {
    const remove = el.querySelector('.pco-remove');
    remove?.addEventListener('click', ev => { ev.stopPropagation(); const title = registry[item.id]?.title || 'Widget'; lastRemovedSlot = {x:item.x, y:item.y, w:item.w, h:item.h}; layout = layout.filter(x => x.id !== item.id); render(); if (editing) { openCatalog(); notify(`${title} retiré : disponible de nouveau dans le catalogue.`); } });
    const grip = el.querySelector('.pco-grip');
    if (grip) {
      grip.addEventListener('dragstart', ev => { if (!editing) return ev.preventDefault(); drag = {kind:'move', id:item.id}; ev.dataTransfer.effectAllowed = 'move'; ev.dataTransfer.setData('text/plain', `move:${item.id}`); el.classList.add('pco-dragging'); });
      grip.addEventListener('dragend', () => { drag = null; el.classList.remove('pco-dragging'); board.classList.remove('pco-drop-target'); });
    }
    const handle = el.querySelector('.pco-resize');
    handle?.addEventListener('pointerdown', ev => {
      if (!editing) return; ev.preventDefault(); ev.stopPropagation(); handle.setPointerCapture?.(ev.pointerId);
      resize = {id:item.id, startX:ev.clientX, startY:ev.clientY, w:item.w, h:item.h, el};
      document.body.style.userSelect='none';
    });
  };
  const render = () => {
    board.replaceChildren();
    layout.sort((a,b) => (a.y-b.y) || (a.x-b.x));
    for (const item of layout) {
      const template = templates.get(item.id); if (!template) continue;
      const node = template.content.firstElementChild.cloneNode(true);
      applyStyle(node, item); wireCard(node, item); board.append(node);
    }
    root.classList.toggle('is-editing', editing);
    document.getElementById('pco-lobby-edit').textContent = editing ? 'Mode édition actif' : 'Modifier le Dashboard';
    document.getElementById('pco-lobby-edit').classList.toggle('pco-good', editing);
    if (!editing) refreshLive();
  };
  const boardPos = event => {
    const rect = board.getBoundingClientRect(); const g = gap(); const cellW = (rect.width - g * (cols - 1)) / cols;
    let x = Math.floor((event.clientX - rect.left) / (cellW + g));
    let y = Math.floor((event.clientY - rect.top) / (row() + g));
    return {x:Math.max(0,Math.min(cols-1,x)), y:Math.max(0,y)};
  };
  const addWidget = (id, pos = null) => {
    const meta = registry[id]; if (!meta || itemById(id)) return;
    const item = {id, x:0, y:0, w:Math.max(1,Math.min(cols,Number(meta.w)||3)), h:Math.max(1,Math.min(20,Number(meta.h)||3))};
    let place = null;

    // PINCABOS_DASHBOARD_EDIT_REMOVED_SLOT_RESIZE_V2
    // Si on ajoute depuis le catalogue après avoir retiré un widget,
    // le nouveau widget prend la taille exacte du trou libéré.
    if (!pos && lastRemovedSlot) {
      const slot = {
        x: Math.max(0, Math.min(cols - 1, Number(lastRemovedSlot.x) || 0)),
        y: Math.max(0, Number(lastRemovedSlot.y) || 0),
        w: Math.max(1, Math.min(cols, Number(lastRemovedSlot.w) || item.w)),
        h: Math.max(1, Math.min(20, Number(lastRemovedSlot.h) || item.h))
      };

      slot.w = Math.max(1, Math.min(slot.w, cols - slot.x));

      const original = {w:item.w, h:item.h};
      item.w = slot.w;
      item.h = slot.h;

      if (fits(item, slot.x, slot.y)) {
        place = {x:slot.x, y:slot.y};
      } else {
        item.w = original.w;
        item.h = original.h;
      }
    }

    if (!place) place = firstFit(item, pos?.x || 0, pos?.y || 0);
    item.x = Math.min(place.x, cols-item.w); item.y = place.y; layout.push(item); lastRemovedSlot = null; render();
  };
  const openCatalog = () => {
    const modal = document.getElementById('pco-lobby-catalog'); const list = document.getElementById('pco-lobby-catalog-list'); list.replaceChildren();
    const active = new Set(layout.map(item => item.id)); const groups = {};
    Object.entries(registry).filter(([id]) => !active.has(id)).forEach(([id,meta]) => (groups[meta.category || 'Autres'] ||= []).push([id,meta]));
    const categories = Object.keys(groups).sort();
    if (!categories.length) { list.textContent = 'Tous les widgets détectés sont déjà présents.'; }
    for (const category of categories) {
      const section = document.createElement('section'); section.className='pco-category'; const title=document.createElement('h3'); title.textContent=category; const grid=document.createElement('div'); grid.className='pco-catalog-grid';
      groups[category].sort((a,b)=>a[1].title.localeCompare(b[1].title,'fr')).forEach(([id,meta]) => {
        const card=document.createElement('div'); card.className='pco-catalog-item'; card.draggable=true; card.dataset.id=id;
        const preview=document.createElement('span'); preview.className='pco-catalog-preview';
        if (meta.image_url) { const image=document.createElement('img'); image.src=meta.image_url; image.alt=''; image.loading='lazy'; image.draggable=false; preview.append(image); }
        else { const glyph=document.createElement('span'); glyph.textContent=meta.kind==='live' ? 'LIVE' : (meta.kind==='tool' ? 'OUTIL' : 'WIDGET'); preview.append(glyph); }
        const text=document.createElement('div'); const strong=document.createElement('strong'); strong.textContent=meta.title; const small=document.createElement('small'); small.textContent=meta.subtitle || ''; text.append(strong,small);
        const button=document.createElement('button'); button.type='button'; button.className='pco-catalog-add'; button.textContent='Ajouter'; button.addEventListener('click',()=>{addWidget(id); modal.hidden=true;});
        card.append(preview,text,button); card.addEventListener('dragstart',ev=>{drag={kind:'new',id}; ev.dataTransfer.effectAllowed='copy'; ev.dataTransfer.setData('text/plain',`new:${id}`);}); grid.append(card);
      }); section.append(title,grid); list.append(section);
    }
    modal.hidden=false;
  };
  const closeCatalog = () => { document.getElementById('pco-lobby-catalog').hidden=true; };
  board.addEventListener('dragover', ev => { if (!editing) return; ev.preventDefault(); board.classList.add('pco-drop-target'); ev.dataTransfer.dropEffect = drag?.kind === 'new' ? 'copy' : 'move'; });
  board.addEventListener('dragleave', ev => { if (!board.contains(ev.relatedTarget)) board.classList.remove('pco-drop-target'); });
  board.addEventListener('drop', ev => {
    if (!editing) return; ev.preventDefault(); board.classList.remove('pco-drop-target');
    const value = ev.dataTransfer.getData('text/plain') || ''; const [kind,id] = value.split(':'); const pos = boardPos(ev);
    if (kind === 'new') {
      // PINCABOS_DASHBOARD_EDIT_ADD_TOP_GAP_V1
      // Par défaut: remplir le premier trou libre en haut du Dashboard.
      // Shift+drop: respecter la position exacte du drop.
      addWidget(id, ev.shiftKey ? pos : null);
      closeCatalog();
      notify(ev.shiftKey ? 'Widget ajouté à l’endroit choisi.' : 'Widget ajouté au premier espace libre en haut.');
      return;
    }
    if (kind === 'move') { const item=itemById(id); if (!item) return; const place=firstFit(item,Math.min(pos.x,cols-item.w),pos.y,item.id); item.x=place.x; item.y=place.y; render(); }
  });
  document.addEventListener('pointermove', ev => {
    if (!resize) return; const item=itemById(resize.id); if (!item) return;
    const rect=board.getBoundingClientRect(); const cellW=(rect.width-gap()*(cols-1))/cols;
    const w=Math.max(1,Math.min(cols-item.x, resize.w+Math.round((ev.clientX-resize.startX)/(cellW+gap()))));
    const h=Math.max(1,Math.min(20, resize.h+Math.round((ev.clientY-resize.startY)/(row()+gap()))));
    item.w=w; item.h=h; applyStyle(resize.el,item);
  });
  document.addEventListener('pointerup', () => {
    if (!resize) return; const item=itemById(resize.id); if (item) { const place=firstFit(item,item.x,item.y,item.id); item.x=place.x; item.y=place.y; } resize=null; document.body.style.userSelect=''; render();
  });
  const post = async (url, body={}) => {
    const response=await fetch(url,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':cfg.csrf},body:JSON.stringify({csrf:cfg.csrf,...body})});
    const payload=await response.json().catch(()=>({ok:false,error:'Réponse invalide.'})); if (!response.ok || !payload.ok) throw new Error(payload.error || 'Échec de l opération.'); return payload;
  };
  document.getElementById('pco-lobby-edit').addEventListener('click',()=>{editing=!editing; if (!editing) closeCatalog(); render();});
  document.getElementById('pco-lobby-add').addEventListener('click',openCatalog);
  const catalogModal = document.getElementById('pco-lobby-catalog');
  const catalogClose = document.getElementById('pco-lobby-catalog-close');
  const closeCatalogHard = event => {
    if (event) { event.preventDefault(); event.stopPropagation(); }
    closeCatalog();
  };
  catalogClose?.addEventListener('pointerup', closeCatalogHard, true);
  catalogClose?.addEventListener('click', closeCatalogHard, true);
  catalogModal?.addEventListener('click', event => {
    if (event.target === catalogModal) closeCatalogHard(event);
  }, true);
  document.addEventListener('click', event => {
    if (event.target.closest('#pco-lobby-catalog-close')) closeCatalogHard(event);
  }, true);
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && catalogModal && !catalogModal.hidden) closeCatalogHard(event);
  });
  // PINCABOS_DASHBOARD_MODES_V1
  // L'interrupteur de vue vit dans la meme portee que layout/savedLayout :
  // il charge la grille de la vue choisie par la meme route que le reste.
  const modeButtons = Array.from(document.querySelectorAll('[data-pco-mode]'));
  const paintMode = (mode) => {
    modeButtons.forEach(b => b.classList.toggle('pco-good', b.dataset.pcoMode === mode));
  };
  paintMode(cfg.mode || 'pro');
  modeButtons.forEach(b => b.addEventListener('click', async () => {
    const mode = b.dataset.pcoMode;
    if (b.classList.contains('pco-good')) return;
    if (editing && !confirm('Quitter le mode édition sans enregistrer, et changer de vue ?')) return;
    try {
      const result = await post('/dashboard/lobby/mode', {mode});
      layout = deep(result.layout); savedLayout = deep(layout); editing = false; closeCatalog(); render();
      paintMode(result.mode); notify('Vue ' + result.label + ' affichée.');
    } catch (error) { notify(error.message); }
  }));
  document.getElementById('pco-lobby-cancel').addEventListener('click',()=>{layout=deep(savedLayout); editing=false; closeCatalog(); render(); notify('Modifications annulées.');});
  document.getElementById('pco-lobby-save').addEventListener('click',async()=>{try{const result=await post('/dashboard/lobby/layout',{layout}); layout=deep(result.layout); savedLayout=deep(layout); editing=false; closeCatalog(); render(); notify('Dashboard enregistré.');}catch(error){notify(error.message);}});
  document.getElementById('pco-lobby-default').addEventListener('click',async()=>{if(!confirm('Remettre cette vue à sa disposition d\'origine ? L\'autre vue n\'est pas touchée.'))return;try{const result=await post('/dashboard/lobby/default'); layout=deep(result.layout); savedLayout=deep(layout); render(); notify('Disposition par défaut enregistrée.');}catch(error){notify(error.message);}});
  document.getElementById('pco-lobby-refresh').addEventListener('click',()=>{refreshStatus(true);refreshLive(true);});
  root.addEventListener('click',ev=>{const target=ev.target.closest('[data-confirm]');if(target && !confirm(target.dataset.confirm))ev.preventDefault();});
  const getPath=(data,path)=>path.split('.').reduce((v,k)=>v&&v[k],data);
  const refreshStatus=async(force=false)=>{ if(editing&&!force)return; try{const response=await fetch('/dashboard/lobby/status',{credentials:'same-origin',cache:'no-store'});if(!response.ok)return;const data=await response.json();root.querySelectorAll('[data-pco-bind]').forEach(el=>{const value=getPath(data,el.dataset.pcoBind);if(value===undefined)return;el.textContent=el.dataset.pcoFormat==='percent'?`${Math.round(Number(value)||0)}%`:value;});root.querySelectorAll('[data-pco-service]').forEach(el=>{const item=data.services?.[el.dataset.pcoService];if(item)el.textContent=item.label;});}catch(_){}};
  let liveTick=false;
  let liveLeaseAt=0;
  const visible=(el)=>{const r=el.getBoundingClientRect();return r.bottom>0&&r.top<innerHeight&&r.right>0&&r.left<innerWidth;};
  const refreshLive=async(force=false)=>{
    if(editing||document.visibilityState!=='visible'||liveTick)return;
    const images=[...root.querySelectorAll('img[data-pco-live-slot]')].filter(img=>force||visible(img));
    if(!images.length)return;
    liveTick=true;
    try{
      const now=Date.now();
      const slots=[...new Set(images.map(img=>Number(img.dataset.pcoLiveSlot)).filter(slot=>Number.isInteger(slot)&&slot>=0&&slot<=2))];
      if(force||now-liveLeaseAt>1500){await post('/dashboard/lobby/live/heartbeat',{slots});liveLeaseAt=now;}
      images.forEach(img=>{
        if(img.dataset.pcoLiveBusy==='1')return;
        img.dataset.pcoLiveBusy='1';
        const state=img.parentElement.querySelector('.pco-live-state small');
        const done=()=>{img.dataset.pcoLiveBusy='0';};
        img.onload=()=>{if(state)state.textContent='Caméra X11 légère · actualisation continue · priorité cabinet';done();};
        img.onerror=()=>{if(state)state.textContent='Connexion X11 en attente · nouvel essai automatique';done();};
        img.src=`/dashboard/lobby/live/${img.dataset.pcoLiveSlot}?t=${now}`;
        setTimeout(done,900);
      });
    }catch(_){}finally{setTimeout(()=>{liveTick=false;},40);}
  };
  document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible'){refreshStatus(true);refreshLive(true);}});
  setInterval(()=>refreshStatus(),7000); setInterval(()=>refreshLive(),200);
  render();
})();

/* BEGIN PINCABOS_DASHBOARD_LIVE_FULLSCREEN_V1 */
(() => {
  "use strict";

  if (window.__pincabosDashboardLiveFullscreenV1) return;
  window.__pincabosDashboardLiveFullscreenV1 = true;

  let activeImage = null;
  let modal = null;
  let modalImage = null;

  const isVisible = (el) => {
    if (!el) return false;
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return (
      style.display !== "none" &&
      style.visibility !== "hidden" &&
      rect.width > 0 &&
      rect.height > 0
    );
  };

  const textOf = (el) => (el?.textContent || "").replace(/\s+/g, " ").trim();

  const liveBlocks = () =>
    [...document.querySelectorAll("[data-pco-live-jpeg]")].filter(isVisible);

  const imageFor = (block) =>
    block.querySelector("img[data-pco-live-jpeg-slot]") ||
    block.querySelector("img");

  const titleFor = (block, image) => {
    const fromAlt = (image?.alt || "").trim();
    if (fromAlt) return fromAlt;

    const text = textOf(block.parentElement);
    const match = text.match(/(Playfield|Backglass|FullDMD)[^·\n]*/i);
    return match ? match[0].trim() : "Live display";
  };

  const cardFor = (block, image, title) => {
    const imageRect = image.getBoundingClientRect();
    const titleKey = title.toLowerCase();

    let parent = block.parentElement;
    let best = block.parentElement || block;
    let bestScore = -999;

    for (let level = 0; parent && parent !== document.body && level < 8; level += 1) {
      const rect = parent.getBoundingClientRect();
      const text = textOf(parent).toLowerCase();

      if (
        rect.width >= Math.max(220, imageRect.width) &&
        rect.width < window.innerWidth * 0.62 &&
        rect.height >= imageRect.height &&
        rect.top <= imageRect.top - 4
      ) {
        let score = 0;

        if (text.includes(titleKey.toLowerCase())) score += 8;
        if (rect.width <= imageRect.width + 150) score += 4;
        if (rect.height <= imageRect.height + 170) score += 4;
        if (level <= 3) score += 3;

        if (score > bestScore) {
          best = parent;
          bestScore = score;
        }
      }

      parent = parent.parentElement;
    }

    return best || block;
  };

  const ensureModal = () => {
    if (modal) return;

    modal = document.createElement("div");
    modal.id = "pincabos-live-fullscreen-popup";
    modal.setAttribute("aria-hidden", "true");

    modal.innerHTML = `
      <button type="button"
              class="pincabos-live-fullscreen-close"
              aria-label="Fermer"
              title="Fermer">×</button>
      <img class="pincabos-live-fullscreen-image" alt="">
    `;

    document.body.appendChild(modal);

    modalImage = modal.querySelector(".pincabos-live-fullscreen-image");

    modal.querySelector(".pincabos-live-fullscreen-close")
      .addEventListener("click", closeFullscreen);

    modal.addEventListener("click", (event) => {
      if (event.target === modal) closeFullscreen();
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeFullscreen();
    });
  };

  const syncFullscreenImage = () => {
    if (!modal || modal.getAttribute("aria-hidden") !== "false" || !activeImage) return;
    if (!activeImage.isConnected) {
      closeFullscreen();
      return;
    }

    const source = activeImage.currentSrc || activeImage.src;
    if (source && modalImage.src !== source) {
      modalImage.src = source;
    }
  };

  const openFullscreen = (image) => {
    if (!image) return;

    ensureModal();
    activeImage = image;

    modalImage.src = image.currentSrc || image.src || "";
    modal.setAttribute("aria-hidden", "false");
    document.body.classList.add("pincabos-live-fullscreen-open");
  };

  function closeFullscreen() {
    if (!modal) return;

    activeImage = null;
    modalImage.removeAttribute("src");
    modal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("pincabos-live-fullscreen-open");
  }

  const decorateLiveWidgets = () => {
    liveBlocks().forEach((block) => {
      const image = imageFor(block);
      if (!image) return;

      const title = titleFor(block, image);
      const card = cardFor(block, image, title);

      if (!card || card.dataset.pincabosLiveFullscreenReady === "1") return;

      card.dataset.pincabosLiveFullscreenReady = "1";
      card.classList.add("pincabos-live-fullscreen-card");

      if (getComputedStyle(card).position === "static") {
        card.style.position = "relative";
      }

      const button = document.createElement("button");
      button.type = "button";
      button.className = "pincabos-live-fullscreen-open";
      button.setAttribute("aria-label", `Afficher ${title} plein écran`);
      button.setAttribute("title", "Plein écran");
      button.textContent = "⛶";

      button.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        openFullscreen(image);
      });

      card.appendChild(button);

      image.addEventListener("load", syncFullscreenImage);
    });
  };

  const style = document.createElement("style");
  style.id = "pincabos-live-fullscreen-style";
  style.textContent = `
    .pincabos-live-fullscreen-card {
      position: relative !important;
    }

    .pincabos-live-fullscreen-open {
      position: absolute !important;
      top: 13px !important;
      right: 14px !important;
      z-index: 30 !important;
      width: 36px !important;
      height: 36px !important;
      min-width: 36px !important;
      min-height: 36px !important;
      display: inline-flex !important;
      align-items: center !important;
      justify-content: center !important;
      border: 1px solid rgba(0, 224, 255, .65) !important;
      border-radius: 9px !important;
      background: rgba(0, 20, 32, .92) !important;
      color: #00e5ff !important;
      cursor: pointer !important;
      font-size: 1.35rem !important;
      font-weight: 900 !important;
      line-height: 1 !important;
      box-shadow: 0 4px 16px rgba(0, 0, 0, .34) !important;
    }

    .pincabos-live-fullscreen-open:hover {
      background: #00cfe8 !important;
      color: #00131a !important;
    }

    #pincabos-live-fullscreen-popup {
      position: fixed;
      inset: 0;
      z-index: 2147483647;
      display: none;
      align-items: center;
      justify-content: center;
      background: #000;
    }

    #pincabos-live-fullscreen-popup[aria-hidden="false"] {
      display: flex;
    }

    #pincabos-live-fullscreen-popup .pincabos-live-fullscreen-image {
      display: block;
      width: 100vw;
      height: 100vh;
      max-width: 100vw;
      max-height: 100vh;
      object-fit: contain;
      background: #000;
    }

    #pincabos-live-fullscreen-popup .pincabos-live-fullscreen-close {
      position: fixed;
      top: 18px;
      right: 20px;
      z-index: 2;
      width: 48px;
      height: 48px;
      border: 1px solid rgba(255, 255, 255, .58);
      border-radius: 12px;
      background: rgba(0, 0, 0, .64);
      color: #fff;
      cursor: pointer;
      font-size: 2.2rem;
      font-weight: 700;
      line-height: 1;
    }

    #pincabos-live-fullscreen-popup .pincabos-live-fullscreen-close:hover {
      background: rgba(210, 35, 55, .95);
      border-color: rgba(255, 255, 255, .95);
    }

    body.pincabos-live-fullscreen-open {
      overflow: hidden !important;
    }
  `;

  if (!document.getElementById(style.id)) {
    document.head.appendChild(style);
  }

  decorateLiveWidgets();

  const observer = new MutationObserver(() => {
    decorateLiveWidgets();
    syncFullscreenImage();
  });

  observer.observe(document.documentElement, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ["src", "class", "style"]
  });

  setInterval(syncFullscreenImage, 180);
})();
/* END PINCABOS_DASHBOARD_LIVE_FULLSCREEN_V1 */

/* BEGIN PINCABOS_DASHBOARD_SERVICES_UNIFORM_V1 */
(() => {
  "use strict";

  if (window.__pcoDashboardServicesUniformV1) return;
  window.__pcoDashboardServicesUniformV1 = true;

  const styleId = "pco-dashboard-services-uniform-style";

  function addStyle() {
    if (document.getElementById(styleId)) return;

    const style = document.createElement("style");
    style.id = styleId;
    style.textContent = `
      .pco-services-scroll > .pco-service-unified-card {
        display: grid;
        gap: 10px;
        margin: 10px 0;
        padding: 12px 14px;
        border: 1px solid rgba(110,220,255,.24);
        border-radius: 12px;
        background: rgba(4,20,30,.38);
      }

      .pco-services-scroll > .pco-service-unified-card:first-child {
        margin-top: 0;
      }

      .pco-service-unified-card .pco-service {
        display: grid !important;
        grid-template-columns: 12px minmax(0,1fr) auto !important;
        align-items: center !important;
        gap: 10px !important;
        min-width: 0;
        margin: 0 !important;
        padding: 0 !important;
        border: 0 !important;
        background: transparent !important;
      }

      .pco-service-unified-card .pco-service i {
        width: 10px !important;
        height: 10px !important;
        min-width: 10px !important;
        border-radius: 50% !important;
      }

      .pco-service-unified-card .pco-service span {
        overflow: hidden;
        color: #eefbff !important;
        font-size: .92rem !important;
        font-weight: 850 !important;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .pco-service-unified-card .pco-service b {
        color: #eefbff !important;
        font-size: .82rem !important;
        font-weight: 850 !important;
        white-space: nowrap;
      }

      .pco-service-unified-card .pco-actions {
        display: flex !important;
        flex-wrap: wrap !important;
        gap: 7px !important;
        margin: 0 !important;
        padding: 10px 0 0 !important;
        border-top: 1px solid rgba(255,255,255,.12);
      }

      .pco-service-unified-card .pco-actions a,
      .pco-service-unified-card .pco-actions button {
        min-height: 36px;
        margin: 0 !important;
        border-radius: 8px !important;
        font-size: .78rem !important;
        font-weight: 800 !important;
      }

      .pco-service-unified-card .pco-protected {
        margin: 0 !important;
        padding: 9px 10px !important;
        border: 1px solid rgba(255,174,0,.20);
        border-radius: 8px;
        background: rgba(255,174,0,.07);
        color: rgba(255,232,181,.90);
        font-size: .76rem;
      }

      @media (max-width: 620px) {
        .pco-service-unified-card .pco-service {
          grid-template-columns: 10px minmax(0,1fr) !important;
        }

        .pco-service-unified-card .pco-service b {
          grid-column: 2;
        }

        .pco-service-unified-card .pco-actions {
          justify-content: flex-start;
        }
      }
    `;

    document.head.appendChild(style);
  }

  function isServiceRow(node) {
    return node instanceof HTMLElement &&
      node.classList.contains("pco-service");
  }

  function canMoveIntoCard(node) {
    return node instanceof HTMLElement && (
      node.classList.contains("pco-actions") ||
      node.classList.contains("pco-protected") ||
      node.classList.contains("pco-note")
    );
  }

  function normalizeServiceCards() {
    document.querySelectorAll(".pco-services-scroll").forEach((scrollRoot) => {
      const serviceRows = [...scrollRoot.children].filter(isServiceRow);

      serviceRows.forEach((serviceRow) => {
        if (
          serviceRow.closest("#pco-dashboard-batch-controls") ||
          serviceRow.parentElement?.classList.contains("pco-service-unified-card")
        ) {
          return;
        }

        const card = document.createElement("section");
        card.className = "pco-service-unified-card";
        card.dataset.pcoServiceUniform = "1";

        scrollRoot.insertBefore(card, serviceRow);
        card.appendChild(serviceRow);

        let next = card.nextElementSibling;

        while (
          next &&
          !isServiceRow(next) &&
          next.id !== "pco-dashboard-batch-controls"
        ) {
          const candidate = next;
          next = next.nextElementSibling;

          if (!canMoveIntoCard(candidate)) break;
          card.appendChild(candidate);
        }
      });
    });
  }

  addStyle();
  normalizeServiceCards();

  const observer = new MutationObserver(() => {
    normalizeServiceCards();
  });

  observer.observe(document.documentElement, {
    childList: true,
    subtree: true
  });

  window.setTimeout(normalizeServiceCards, 200);
  window.setTimeout(normalizeServiceCards, 800);
})();
/* END PINCABOS_DASHBOARD_SERVICES_UNIFORM_V1 */

/* BEGIN PINCABOS_DASHBOARD_SERVICES_COMPACT_V2 */
(() => {
  "use strict";

  if (window.__pcoDashboardServicesCompactV2) return;
  window.__pcoDashboardServicesCompactV2 = true;

  const styleId = "pco-dashboard-services-compact-v2-style";

  function addStyle() {
    if (document.getElementById(styleId)) return;

    const style = document.createElement("style");
    style.id = styleId;
    style.textContent = `
      .pco-services-scroll > .pco-service-unified-card {
        display: grid !important;
        gap: 7px !important;
        margin: 8px 0 !important;
        padding: 9px 12px !important;
        min-height: 0 !important;
        border-radius: 12px !important;
      }

      .pco-service-unified-card .pco-service {
        min-height: 24px !important;
        gap: 8px !important;
      }

      .pco-service-unified-card .pco-service i {
        width: 9px !important;
        height: 9px !important;
        min-width: 9px !important;
      }

      .pco-service-unified-card .pco-service span {
        font-size: .84rem !important;
        line-height: 1.1 !important;
      }

      .pco-service-unified-card .pco-service b {
        font-size: .76rem !important;
        line-height: 1.1 !important;
      }

      .pco-service-unified-card .pco-actions {
        display: flex !important;
        flex-wrap: wrap !important;
        gap: 6px !important;
        margin: 0 !important;
        padding: 8px 0 0 !important;
        border-top: 1px solid rgba(255,255,255,.10) !important;
      }

      .pco-service-unified-card .pco-actions form {
        display: inline-flex !important;
        margin: 0 !important;
      }

      .pco-service-unified-card .pco-actions a,
      .pco-service-unified-card .pco-actions button,
      .pco-service-unified-card .pco-actions input[type="submit"] {
        min-height: 32px !important;
        margin: 0 !important;
        padding: 7px 10px !important;
        border-radius: 8px !important;
        font-size: .72rem !important;
        font-weight: 800 !important;
        line-height: 1 !important;
      }

      .pco-service-unified-card .pco-protected {
        margin: 0 !important;
        padding: 7px 9px !important;
        font-size: .70rem !important;
        line-height: 1.2 !important;
      }

      #pco-dashboard-batch-controls {
        gap: 8px !important;
        margin: 10px 0 !important;
        padding-top: 10px !important;
      }

      #pco-dashboard-batch-controls .pco-batch-row {
        gap: 8px !important;
        padding: 9px 10px !important;
      }

      #pco-dashboard-batch-controls .pco-batch-title {
        font-size: .82rem !important;
      }

      #pco-dashboard-batch-controls .pco-batch-detail {
        font-size: .69rem !important;
      }

      #pco-dashboard-batch-controls .pco-batch-actions a,
      #pco-dashboard-batch-controls .pco-batch-actions button {
        min-height: 32px !important;
        padding: 7px 9px !important;
        font-size: .70rem !important;
      }

      @media (max-width: 620px) {
        .pco-service-unified-card .pco-actions {
          justify-content: flex-start !important;
        }
      }
    `;

    document.head.appendChild(style);
  }

  function serviceCardName(card) {
    const label = card.querySelector(".pco-service span");
    return (label?.textContent || "").trim().toLowerCase();
  }

  function isBoundary(node) {
    if (!(node instanceof HTMLElement)) return true;

    return (
      node.classList.contains("pco-service-unified-card") ||
      node.classList.contains("pco-service") ||
      node.id === "pco-dashboard-batch-controls"
    );
  }

  function isActionNode(node) {
    if (!(node instanceof HTMLElement)) return false;

    return (
      node.matches("form, .pco-actions, .pco-protected, .pco-note") ||
      Boolean(node.querySelector("button, input[type='submit'], a"))
    );
  }

  function actionContainer(card) {
    let actions = card.querySelector(":scope > .pco-actions");

    if (!actions) {
      actions = document.createElement("div");
      actions.className = "pco-actions";
      card.appendChild(actions);
    }

    return actions;
  }

  function moveLooseActionsInsideCards() {
    document.querySelectorAll(".pco-services-scroll > .pco-service-unified-card").forEach((card) => {
      const name = serviceCardName(card);

      if (!name) return;

      let next = card.nextElementSibling;
      const movable = [];

      while (next && !isBoundary(next)) {
        const candidate = next;
        next = next.nextElementSibling;

        if (!isActionNode(candidate)) break;
        movable.push(candidate);
      }

      if (!movable.length) return;

      const actions = actionContainer(card);

      movable.forEach((node) => {
        if (node.classList.contains("pco-actions")) {
          [...node.children].forEach((child) => actions.appendChild(child));
          node.remove();
        } else if (node.classList.contains("pco-protected")) {
          card.appendChild(node);
        } else {
          actions.appendChild(node);
        }
      });
    });
  }

  function normalize() {
    addStyle();
    moveLooseActionsInsideCards();
  }

  normalize();

  const observer = new MutationObserver(() => {
    normalize();
  });

  observer.observe(document.documentElement, {
    childList: true,
    subtree: true
  });

  window.setTimeout(normalize, 150);
  window.setTimeout(normalize, 700);
  window.setTimeout(normalize, 1800);
})();
/* END PINCABOS_DASHBOARD_SERVICES_COMPACT_V2 */

/* BEGIN PINCABOS_DASHBOARD_SERVICES_ULTRA_COMPACT_V1 */
(() => {
  "use strict";

  const STYLE_ID = "pco-dashboard-services-ultra-compact-style";

  if (document.getElementById(STYLE_ID)) return;

  const style = document.createElement("style");
  style.id = STYLE_ID;

  style.textContent = `
    /* Cartes de services normales */
    .pco-services-scroll > .pco-service-unified-card {
      gap: 6px !important;
      margin: 6px 0 !important;
      padding: 8px 10px !important;
      min-height: 0 !important;
      border-radius: 11px !important;
    }

    .pco-services-scroll > .pco-service-unified-card > * {
      margin-top: 0 !important;
      margin-bottom: 0 !important;
    }

    .pco-service-unified-card .pco-service {
      min-height: 22px !important;
      gap: 7px !important;
      padding: 0 !important;
    }

    .pco-service-unified-card .pco-service i {
      width: 8px !important;
      height: 8px !important;
      min-width: 8px !important;
    }

    .pco-service-unified-card .pco-service span {
      font-size: .78rem !important;
      font-weight: 700 !important;
      line-height: 1.05 !important;
    }

    .pco-service-unified-card .pco-service b {
      font-size: .70rem !important;
      font-weight: 700 !important;
      line-height: 1.05 !important;
    }

    .pco-service-unified-card .pco-actions {
      display: flex !important;
      flex-wrap: wrap !important;
      gap: 5px !important;
      margin: 0 !important;
      padding: 6px 0 0 !important;
    }

    .pco-service-unified-card .pco-actions form {
      display: inline-flex !important;
      margin: 0 !important;
      padding: 0 !important;
    }

    .pco-service-unified-card .pco-actions a,
    .pco-service-unified-card .pco-actions button,
    .pco-service-unified-card .pco-actions input[type="submit"],
    .pco-service-unified-card .pco-actions .pco-action {
      min-height: 28px !important;
      height: 28px !important;
      margin: 0 !important;
      padding: 0 8px !important;
      border-radius: 7px !important;
      font-size: .66rem !important;
      font-weight: 700 !important;
      line-height: 28px !important;
    }

    .pco-service-unified-card .pco-protected {
      margin: 0 !important;
      padding: 6px 8px !important;
      font-size: .66rem !important;
      line-height: 1.15 !important;
    }

    /* Batch Import / Export */
    #pco-dashboard-batch-controls {
      gap: 6px !important;
      margin: 8px 0 !important;
      padding-top: 8px !important;
    }

    #pco-dashboard-batch-controls .pco-batch-row {
      gap: 7px !important;
      min-height: 0 !important;
      padding: 8px 9px !important;
      border-radius: 10px !important;
    }

    #pco-dashboard-batch-controls .pco-batch-title {
      gap: 6px !important;
      font-size: .76rem !important;
      font-weight: 700 !important;
      line-height: 1.05 !important;
    }

    #pco-dashboard-batch-controls .pco-batch-title b {
      font-size: .68rem !important;
      font-weight: 700 !important;
    }

    #pco-dashboard-batch-controls .pco-batch-detail {
      margin-top: 2px !important;
      font-size: .65rem !important;
      line-height: 1.1 !important;
    }

    #pco-dashboard-batch-controls .pco-batch-actions {
      gap: 5px !important;
    }

    #pco-dashboard-batch-controls .pco-batch-actions a,
    #pco-dashboard-batch-controls .pco-batch-actions button {
      min-height: 28px !important;
      height: 28px !important;
      padding: 0 8px !important;
      border-radius: 7px !important;
      font-size: .66rem !important;
      font-weight: 700 !important;
      line-height: 28px !important;
    }

    @media (max-width: 620px) {
      .pco-service-unified-card .pco-actions,
      #pco-dashboard-batch-controls .pco-batch-actions {
        justify-content: flex-start !important;
      }
    }
  `;

  document.head.appendChild(style);
})();
/* END PINCABOS_DASHBOARD_SERVICES_ULTRA_COMPACT_V1 */


/* PINCABOS_NETWORK_TRUECHART_V1 */
(()=>{
  const samples=[]; const maxSamples=90; let inFlight=false;
  const q=(selector,scope=document)=>scope.querySelector(selector);
  const qa=(selector,scope=document)=>[...scope.querySelectorAll(selector)];
  const mbps=value=>`${Number(value||0).toFixed(Number(value||0)>=10?1:2)} Mb/s`;
  const text=(card,selector,value)=>{const el=q(selector,card);if(el)el.textContent=value ?? '—';};
  const visible=el=>!!(el&&el.getClientRects().length&&getComputedStyle(el).visibility!=='hidden');
  function draw(canvas){
    if(!canvas||!visible(canvas))return;
    const rect=canvas.getBoundingClientRect(), ratio=Math.max(1,window.devicePixelRatio||1);
    const width=Math.max(1,Math.round(rect.width*ratio)), height=Math.max(1,Math.round(rect.height*ratio));
    if(canvas.width!==width||canvas.height!==height){canvas.width=width;canvas.height=height;}
    const ctx=canvas.getContext('2d'); if(!ctx)return;
    ctx.setTransform(ratio,0,0,ratio,0,0);
    const w=rect.width,h=rect.height,left=4,right=42,top=7,bottom=7,plotW=Math.max(1,w-left-right),plotH=Math.max(1,h-top-bottom),mid=top+plotH/2;
    const max=Math.max(1,...samples.flatMap(s=>[s.rx,s.tx]));
    const step=max<=2?1:max<=10?2:max<=50?10:max<=100?20:Math.ceil(max/50)*50;
    const scale=Math.ceil(max/step)*step;
    ctx.clearRect(0,0,w,h); ctx.lineWidth=1;
    ctx.strokeStyle='rgba(205,188,226,.13)'; ctx.fillStyle='rgba(208,193,226,.58)'; ctx.font='10px system-ui, sans-serif';
    for(let i=0;i<=4;i++){
      const y=top+(plotH*i/4);ctx.beginPath();ctx.moveTo(left,y+.5);ctx.lineTo(left+plotW,y+.5);ctx.stroke();
      if(i!==2){const label=`${Math.round(scale*Math.abs(2-i)/2)} Mb/s`;ctx.fillText(label,left+plotW+6,y+3);}
    }
    ctx.strokeStyle='rgba(205,188,226,.26)';ctx.beginPath();ctx.moveTo(left,mid+.5);ctx.lineTo(left+plotW,mid+.5);ctx.stroke();ctx.fillText('0/s',left+plotW+6,mid+3);
    if(samples.length<2)return;
    const point=(sample,index,kind)=>{const x=left+(index/(maxSamples-1))*plotW;const value=Number(sample[kind]||0);const y=kind==='rx'?mid-(value/scale)*(plotH/2):mid+(value/scale)*(plotH/2);return [x,y];};
    const area=(kind,color,positive)=>{ctx.beginPath();samples.forEach((s,i)=>{const [x,y]=point(s,i,kind);i?ctx.lineTo(x,y):ctx.moveTo(x,y);});const last=point(samples[samples.length-1],samples.length-1,kind)[0];const first=point(samples[0],0,kind)[0];ctx.lineTo(last,mid);ctx.lineTo(first,mid);ctx.closePath();ctx.fillStyle=color.replace('1)','0.20)');ctx.fill();ctx.beginPath();samples.forEach((s,i)=>{const [x,y]=point(s,i,kind);i?ctx.lineTo(x,y):ctx.moveTo(x,y);});ctx.strokeStyle=color;ctx.lineWidth=1.7;ctx.stroke();};
    area('rx','rgba(62,167,255,1)',true); area('tx','rgba(255,154,46,1)',false);
  }
  function update(data){
    const rx=Number(data.rx_mbps||0),tx=Number(data.tx_mbps||0);samples.push({rx,tx});if(samples.length>maxSamples)samples.shift();
    qa('[data-pco-network-widget="1"]').forEach(card=>{
      text(card,'[data-pco-network-ip]',data.ip);text(card,'[data-pco-network-gateway]',data.gateway);text(card,'[data-pco-network-mask]',data.mask);
      text(card,'[data-pco-network-addressing]',data.addressing);text(card,'[data-pco-network-dns]',data.dns);text(card,'[data-pco-network-internet]',data.internet);
      text(card,'[data-pco-network-link]',data.link);text(card,'[data-pco-network-interface]',data.interface);text(card,'[data-pco-network-speed]',data.speed==='—'?'Trafic live':data.speed);
      text(card,'[data-pco-network-rx]',mbps(rx));text(card,'[data-pco-network-tx]',mbps(tx));qa('[data-pco-network-chart]',card).forEach(draw);
    });
  }
  async function refresh(){
    if(inFlight||!q('[data-pco-network-widget="1"]'))return;inFlight=true;
    try{const response=await fetch('/dashboard/lobby/network/traffic',{credentials:'same-origin',cache:'no-store'});if(!response.ok)return;update(await response.json());}catch(_){ }finally{inFlight=false;}
  }
  function boot(){refresh();window.setInterval(refresh,1000);window.addEventListener('resize',()=>qa('[data-pco-network-chart]').forEach(draw),{passive:true});}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();

/* PINCABOS_AUDIO_VOLUME_DASHBOARD_WIDGET_V3_1_JS */
(() => {
  "use strict";

  window.__pincabosAudioVolumeDashboardWidgetV3 = true;
  window.__pincabosAudioVolumeDashboardWidgetV31 = true;

  const API = "/api/pincabos/audio-volume";
  const STEP = 5;
  const timers = new Map();

  let busy = false;
  let lastData = null;
  let configured = false;
  let selectedKeys = new Set();
  let dirtyConfig = false;

  const q = (sel, root = document) => root.querySelector(sel);
  const qa = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, ch => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;"
    }[ch]));
  }

  function widgets() {
    return qa("[data-pco-audio-volume-widget='1']");
  }

  function anyConfigOpen() {
    return widgets().some(widget => {
      const panel = q("[data-pco-audio-volume-config]", widget);
      return panel && !panel.hidden;
    });
  }

  function keyOf(card, ctrl) {
    return String(ctrl.key || `${card.card_id}:${ctrl.name}`);
  }

  function allAvailableKeys() {
    const keys = [];
    const cards = Array.isArray(lastData?.cards) ? lastData.cards : [];
    for (const card of cards) {
      for (const ctrl of (Array.isArray(card.controls) ? card.controls : [])) {
        keys.push(keyOf(card, ctrl));
      }
    }
    return keys;
  }

  async function post(path, payload) {
    const response = await fetch(API + path, {
      method: "POST",
      credentials: "same-origin",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload || {})
    });
    const data = await response.json().catch(() => ({ok:false, error:"Réponse invalide"}));
    if (!response.ok || !data.ok) throw new Error(data.error || "Échec API audio");
    return data;
  }

  function setConfigFromPayload(data) {
    if (dirtyConfig || anyConfigOpen()) return;

    const cfg = data?.config || data || {};
    configured = Boolean(cfg.configured);
    selectedKeys = new Set(Array.isArray(cfg.selected) ? cfg.selected.map(String) : []);
  }

  function visibleSelected(card, ctrl) {
    if (!configured) return true;
    return selectedKeys.has(keyOf(card, ctrl));
  }

  function syncSelectionFromOpenPanel(widget) {
    const panel = q("[data-pco-audio-volume-config]", widget);
    if (!panel || panel.hidden) return;

    configured = true;
    dirtyConfig = true;
    selectedKeys = new Set(
      qa("input[type='checkbox']", panel)
        .filter(input => input.checked)
        .map(input => String(input.value))
    );
  }

  function scheduleSet(cardId, control, volume) {
    const key = `${cardId}:${control}`;
    clearTimeout(timers.get(key));
    timers.set(key, setTimeout(() => {
      post("/set", {card_id: cardId, control, volume}).catch(() => {});
    }, 120));
  }

  function rowHtml(card, ctrl) {
    const muted = Boolean(ctrl.muted);
    const vol = Math.max(0, Math.min(100, Number(ctrl.volume) || 0));

    return `
      <div class="pco-av-row"
           data-card-id="${esc(card.card_id)}"
           data-control="${esc(ctrl.name)}"
           data-key="${esc(keyOf(card, ctrl))}">
        <div class="pco-av-label">${esc(ctrl.name)}</div>
        <button class="pco-av-step" type="button" data-step="-${STEP}">−</button>
        <input class="pco-av-slider" type="range" min="0" max="100" step="1" value="${vol}">
        <button class="pco-av-step" type="button" data-step="${STEP}">+</button>
        <div class="pco-av-pct">${vol}%</div>
        <button class="pco-av-mute ${muted ? "is-muted" : ""}" type="button">${muted ? "OFF" : "ON"}</button>
      </div>`;
  }

  function renderBody(widget) {
    const body = q("[data-pco-audio-volume-body]", widget);
    if (!body) return;

    const cards = Array.isArray(lastData?.cards) ? lastData.cards : [];
    if (!cards.length) {
      body.innerHTML = '<div class="pco-audio-volume-loading">Aucune carte audio détectée.</div>';
      return;
    }

    const html = [];
    let visibleCount = 0;

    for (const card of cards) {
      const controls = (Array.isArray(card.controls) ? card.controls : [])
        .filter(ctrl => visibleSelected(card, ctrl));

      if (!controls.length) continue;

      visibleCount += controls.length;
      html.push(`
        <section class="pco-av-card">
          <div class="pco-av-title">Carte ${esc(card.card_id)} · ${esc(card.name || "Audio")}</div>
          ${controls.map(ctrl => rowHtml(card, ctrl)).join("")}
        </section>`);
    }

    body.innerHTML = visibleCount
      ? html.join("")
      : '<div class="pco-audio-volume-loading">Aucune sortie cochée. Clique sur ⚙ pour sélectionner les sorties à afficher.</div>';
  }

  function renderConfig(widget, force = false) {
    const panel = q("[data-pco-audio-volume-config]", widget);
    const list = q("[data-pco-audio-volume-config-list]", widget);
    if (!panel || !list) return;

    if (!force && !panel.hidden) {
      widget.classList.add("is-audio-config-open");
      return;
    }

    const cards = Array.isArray(lastData?.cards) ? lastData.cards : [];
    const lines = [];

    for (const card of cards) {
      const controls = Array.isArray(card.controls) ? card.controls : [];
      for (const ctrl of controls) {
        const key = keyOf(card, ctrl);
        const checked = configured ? selectedKeys.has(key) : true;

        lines.push(`
          <label class="pco-av-check">
            <input type="checkbox" value="${esc(key)}" ${checked ? "checked" : ""}>
            <span class="pco-av-check-text">Carte ${esc(card.card_id)} · ${esc(card.name || "Audio")} · ${esc(ctrl.name)}</span>
          </label>`);
      }
    }

    list.innerHTML = lines.length
      ? lines.join("")
      : '<div class="pco-audio-volume-loading">Aucune sortie réglable détectée.</div>';

    widget.classList.toggle("is-audio-config-open", !panel.hidden);
  }

  function renderAll(forceConfig = false) {
    widgets().forEach(widget => {
      renderConfig(widget, forceConfig);
      renderBody(widget);
    });
  }

  async function refresh(force = false) {
    if (busy && !force) return;
    if (!widgets().length) return;

    busy = true;
    try {
      const response = await fetch(API + "/cards", {
        credentials: "same-origin",
        cache: "no-store"
      });
      const data = await response.json();

      if (!data || !data.ok) throw new Error(data?.error || "API audio non disponible");

      lastData = data;
      setConfigFromPayload(data);
      renderAll(false);
    } catch (_) {
      widgets().forEach(widget => {
        const body = q("[data-pco-audio-volume-body]", widget);
        if (body) body.innerHTML = '<div class="pco-audio-volume-loading">API audio non disponible.</div>';
      });
    } finally {
      busy = false;
    }
  }

  document.addEventListener("change", event => {
    const checkbox = event.target.closest("[data-pco-audio-volume-config] input[type='checkbox']");
    if (!checkbox) return;

    const widget = checkbox.closest("[data-pco-audio-volume-widget='1']");
    syncSelectionFromOpenPanel(widget);
    renderBody(widget);
  });

  document.addEventListener("input", event => {
    const slider = event.target.closest(".pco-av-slider");
    if (!slider) return;

    const row = slider.closest(".pco-av-row");
    const pct = q(".pco-av-pct", row);
    const mute = q(".pco-av-mute", row);
    const value = Math.max(0, Math.min(100, parseInt(slider.value, 10) || 0));

    if (pct) pct.textContent = value + "%";
    if (mute) {
      mute.textContent = "ON";
      mute.classList.remove("is-muted");
    }

    scheduleSet(Number(row.dataset.cardId), row.dataset.control, value);
  });

  document.addEventListener("click", async event => {
    const gear = event.target.closest(".pco-audio-volume-gear");
    if (gear) {
      const widget = gear.closest("[data-pco-audio-volume-widget='1']");
      const panel = q("[data-pco-audio-volume-config]", widget);
      if (!panel) return;

      panel.hidden = !panel.hidden;

      if (!panel.hidden) {
        dirtyConfig = false;
        renderConfig(widget, true);
      } else {
        dirtyConfig = false;
        await refresh(true);
      }

      widget.classList.toggle("is-audio-config-open", !panel.hidden);
      return;
    }

    const refreshButton = event.target.closest(".pco-audio-volume-refresh");
    if (refreshButton) {
      refresh(true);
      return;
    }

    const selectAll = event.target.closest("[data-pco-av-select-all]");
    if (selectAll) {
      const widget = selectAll.closest("[data-pco-audio-volume-widget='1']");
      const panel = q("[data-pco-audio-volume-config]", widget);
      qa("input[type='checkbox']", panel).forEach(input => input.checked = true);
      syncSelectionFromOpenPanel(widget);
      renderBody(widget);
      return;
    }

    const selectNone = event.target.closest("[data-pco-av-select-none]");
    if (selectNone) {
      const widget = selectNone.closest("[data-pco-audio-volume-widget='1']");
      const panel = q("[data-pco-audio-volume-config]", widget);
      qa("input[type='checkbox']", panel).forEach(input => input.checked = false);
      syncSelectionFromOpenPanel(widget);
      renderBody(widget);
      return;
    }

    const save = event.target.closest("[data-pco-av-save]");
    if (save) {
      const widget = save.closest("[data-pco-audio-volume-widget='1']");
      const panel = q("[data-pco-audio-volume-config]", widget);

      syncSelectionFromOpenPanel(widget);

      try {
        const payload = await post("/config", {
          selected: Array.from(selectedKeys)
        });

        configured = true;
        dirtyConfig = false;
        selectedKeys = new Set(Array.isArray(payload.selected) ? payload.selected.map(String) : Array.from(selectedKeys));

        panel.hidden = true;
        widget.classList.remove("is-audio-config-open");
        renderAll(true);
      } catch (error) {
        alert(error.message || "Sauvegarde impossible");
      }
      return;
    }

    const step = event.target.closest(".pco-av-step");
    if (step) {
      const row = step.closest(".pco-av-row");
      const slider = q(".pco-av-slider", row);
      if (!slider) return;

      const value = Math.max(0, Math.min(100,
        (parseInt(slider.value, 10) || 0) + (parseInt(step.dataset.step, 10) || 0)
      ));

      slider.value = String(value);
      slider.dispatchEvent(new Event("input", {bubbles:true}));
      return;
    }

    const mute = event.target.closest(".pco-av-mute");
    if (mute) {
      const row = mute.closest(".pco-av-row");
      await post("/mute-toggle", {
        card_id: Number(row.dataset.cardId),
        control: row.dataset.control
      }).catch(() => {});
      refresh(true);
    }
  });

  function boot() {
    refresh(true);
    window.setInterval(() => {
      if (!anyConfigOpen()) refresh(false);
    }, 5000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, {once:true});
  } else {
    boot();
  }
})();


/* PINCABOS_SERVICES_REMOVE_BATCH_OPEN_BUTTON_V3 */
(function(){
  function textOf(node) {
    return String((node && node.textContent) || "").replace(/\s+/g, " ").trim();
  }

  function isBatchCard(node) {
    const txt = textOf(node).toLowerCase();
    return txt.includes("batch import") || txt.includes("batch export");
  }

  function isOpenButton(node) {
    const txt = textOf(node).toLowerCase();
    return txt === "ouvrir" || txt === "open" || txt === "ouvrir batch import" || txt === "ouvrir batch export";
  }

  function cleanupBatchOpenButtons() {
    try {
      document.querySelectorAll("a, button").forEach(function(btn){
        if (!isOpenButton(btn)) return;

        let parent = btn.parentElement;
        let depth = 0;

        while (parent && depth < 8) {
          if (isBatchCard(parent)) {
            btn.remove();
            return;
          }
          parent = parent.parentElement;
          depth += 1;
        }
      });
    } catch (e) {}
  }

  cleanupBatchOpenButtons();
  document.addEventListener("DOMContentLoaded", cleanupBatchOpenButtons);
  window.addEventListener("load", cleanupBatchOpenButtons);
  setInterval(cleanupBatchOpenButtons, 750);

  try {
    new MutationObserver(cleanupBatchOpenButtons).observe(
      document.documentElement,
      { childList: true, subtree: true }
    );
  } catch (e) {}
})();
