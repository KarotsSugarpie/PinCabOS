/* PINCABOS_DASHBOARD_JPEG_X11_V16 */
/* PINCABOS_LIVE_PLAYSTOP_V1 — apercu a la demande.
 *
 * L'apercu ne tourne plus par defaut : chaque tuile a un bouton play/stop dans
 * son titre, et un bouton global pilote toutes les tuiles. Une tuile en pause
 * est exclue du heartbeat, donc sa capture s'eteint cote cabinet. Au repos
 * (rien en lecture), plus aucun ffmpeg — fini les ~6% d'idle. L'etat de lecture
 * est memorise par tuile (localStorage), le defaut etant "en pause".
 */
(() => {
  "use strict";

  const config = window.PCO_LOBBY || {};
  const root = document.getElementById("pco-lobby");
  if (!root || !config.csrf) return;

  const STORE_KEY = "pco.live.playing";

  // Slots en lecture (defaut : aucun => tout en pause).
  const playing = new Set();
  try {
    const raw = window.localStorage.getItem(STORE_KEY);
    if (raw) JSON.parse(raw).forEach((s) => {
      const n = Number(s);
      if (Number.isInteger(n) && n >= 0 && n <= 2) playing.add(n);
    });
  } catch (_) { /* stockage indisponible : on reste en pause */ }

  const persist = () => {
    try { window.localStorage.setItem(STORE_KEY, JSON.stringify([...playing])); }
    catch (_) { /* sans effet */ }
  };

  let lastLease = 0;
  let busy = false;

  const visible = (element) => {
    const rect = element.getBoundingClientRect();
    return rect.bottom > 0 && rect.top < window.innerHeight &&
      rect.right > 0 && rect.left < window.innerWidth;
  };

  const slotOf = (el) => {
    const n = Number(el.dataset.pcoLiveJpegSlot ?? el.dataset.pcoLiveJpeg);
    return Number.isInteger(n) && n >= 0 && n <= 2 ? n : null;
  };

  // Images a rafraichir : visibles ET en lecture.
  const cameras = () =>
    [...root.querySelectorAll("img[data-pco-live-jpeg-slot]")]
      .filter((image) => {
        const slot = slotOf(image);
        return slot !== null && playing.has(slot) && visible(image);
      });

  const status = (slot, text) =>
    root.querySelector(`[data-pco-live-jpeg-status="${slot}"]`)?.replaceChildren(text);

  async function renewLease(slots) {
    const response = await fetch("/dashboard/lobby/live/heartbeat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": String(config.csrf || "")
      },
      body: JSON.stringify({ csrf: config.csrf, slots }),
      cache: "no-store"
    });
    if (!response.ok) throw new Error("heartbeat");
  }

  // Heartbeat immediat avec l'ensemble courant (meme vide) : sert a eteindre
  // tout de suite la capture quand on met en pause.
  function pushNow() {
    const slots = [...new Set(cameras().map(slotOf))];
    renewLease(slots).catch(() => {});
    lastLease = Date.now();
  }

  function paint(slot) {
    const container = root.querySelector(`.pco-live-jpeg[data-pco-live-jpeg="${slot}"]`);
    if (container) container.classList.toggle("is-paused", !playing.has(slot));
    const btn = root.querySelector(`.pco-live-toggle[data-slot="${slot}"]`);
    if (btn) {
      const on = playing.has(slot);
      btn.classList.toggle("is-playing", on);
      btn.setAttribute("aria-pressed", on ? "true" : "false");
      btn.title = on ? "Mettre l'apercu en pause" : "Demarrer l'apercu";
      btn.textContent = on ? "⏸" : "▶";
    }
    if (!playing.has(slot)) status(slot, "Apercu en pause · cliquez ▶ pour l'activer");
    paintGlobal();
  }

  function paintGlobal() {
    const btn = root.querySelector("#pco-live-global");
    if (!btn) return;
    const anyOn = playing.size > 0;
    btn.classList.toggle("is-playing", anyOn);
    btn.textContent = anyOn ? "⏸ Aperçus" : "▶ Aperçus";
    btn.title = anyOn ? "Mettre tous les aperçus en pause" : "Démarrer tous les aperçus";
  }

  function setSlot(slot, on) {
    if (on) playing.add(slot); else playing.delete(slot);
    persist();
    paint(slot);
    pushNow();               // allumage/extinction immediat
    if (on) tick(true);
  }

  function knownSlots() {
    return [...new Set(
      [...root.querySelectorAll("img[data-pco-live-jpeg-slot]")]
        .map(slotOf).filter((s) => s !== null)
    )];
  }

  // Ajoute le bouton play/stop dans le titre des tuiles live, et le bouton
  // global dans la barre d'actions. Re-appelable : instrumente les tuiles
  // ajoutees dynamiquement (catalogue, actualisation).
  function instrument() {
    root.querySelectorAll('article.pco-card[data-pco-kind="live"]').forEach((card) => {
      if (card.querySelector(".pco-live-toggle")) return;
      const img = card.querySelector("img[data-pco-live-jpeg-slot]");
      const slot = img ? slotOf(img) : null;
      if (slot === null) return;
      // Le bouton plein ecran est en absolu en haut a droite de la tuile ;
      // on pose le play/stop dans le meme conteneur, juste a sa gauche, pour
      // qu'ils ne se recouvrent pas.
      // Selecteur tolerant : le bouton plein ecran a ete versionne (-v3...),
      // on matche toute variante de la classe pour ne pas se retrouver en
      // position "solo" par erreur (ce qui recouvrirait le coin droit).
      const fs = card.querySelector('[class*="pincabos-live-fullscreen-open"]');
      const host = (fs && fs.parentElement) ||
        card.querySelector(".pco-live-jpeg") || card.querySelector(".pco-card-body");
      if (!host) return;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "pco-live-toggle";
      btn.dataset.slot = String(slot);
      // A gauche du plein ecran s'il existe, sinon coin haut droit.
      btn.classList.toggle("pco-live-toggle-solo", !fs);
      btn.addEventListener("click", (e) => {
        e.preventDefault(); e.stopPropagation();
        setSlot(slot, !playing.has(slot));
      });
      host.appendChild(btn);
      paint(slot);
    });

    const actions = root.querySelector(".pco-lobby-actions");
    if (actions && !root.querySelector("#pco-live-global") && knownSlots().length) {
      const g = document.createElement("button");
      g.type = "button";
      g.id = "pco-live-global";
      g.addEventListener("click", (e) => {
        e.preventDefault(); e.stopPropagation();
        const slots = knownSlots();
        const turnOn = playing.size === 0;      // tout eteint -> tout allumer, sinon tout eteindre
        slots.forEach((s) => { if (turnOn) playing.add(s); else playing.delete(s); });
        persist();
        slots.forEach(paint);
        pushNow();
        if (turnOn) tick(true);
      });
      actions.insertBefore(g, actions.firstChild);
      paintGlobal();
    }
  }

  function refreshImage(image, timestamp) {
    if (image.dataset.pcoJpegBusy === "1") return;
    const slot = slotOf(image);
    if (slot === null) return;

    image.dataset.pcoJpegBusy = "1";
    const complete = () => { image.dataset.pcoJpegBusy = "0"; };

    image.onload = () => {
      status(slot, "Caméra X11 active · JPEG basse résolution · priorité cabinet");
      complete();
    };
    image.onerror = () => {
      status(slot, "Capture X11 en attente · nouvel essai automatique");
      complete();
    };

    image.src = `/dashboard/lobby/live/${slot}?t=${timestamp}`;
    window.setTimeout(complete, 850);
  }

  async function tick(force = false) {
    instrument();
    if (busy || document.visibilityState !== "visible") return;

    const images = cameras();
    if (!images.length) return;

    busy = true;
    try {
      const now = Date.now();
      const slots = [...new Set(images.map(slotOf))];
      if (force || now - lastLease >= 1200) {
        await renewLease(slots);
        lastLease = now;
      }
      images.forEach((image) => refreshImage(image, now));
    } catch (_) {
      /* Le prochain cycle relancera automatiquement la lease. */
    } finally {
      busy = false;
    }
  }

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") tick(true);
  });

  window.setTimeout(() => { instrument(); tick(true); }, 250);
  window.setInterval(() => tick(false), 200);
})();
