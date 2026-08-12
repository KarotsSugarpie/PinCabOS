/* PINCABOS_DASHBOARD_JPEG_X11_V16 */
(() => {
  "use strict";

  const config = window.PCO_LOBBY || {};
  const root = document.getElementById("pco-lobby");
  if (!root || !config.csrf) return;

  let lastLease = 0;
  let busy = false;

  const visible = (element) => {
    const rect = element.getBoundingClientRect();
    return rect.bottom > 0 && rect.top < window.innerHeight &&
      rect.right > 0 && rect.left < window.innerWidth;
  };

  const cameras = () =>
    [...root.querySelectorAll("img[data-pco-live-jpeg-slot]")]
      .filter((image) => visible(image));

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

  function refreshImage(image, timestamp) {
    if (image.dataset.pcoJpegBusy === "1") return;

    const slot = Number(image.dataset.pcoLiveJpegSlot);
    if (!Number.isInteger(slot) || slot < 0 || slot > 2) return;

    image.dataset.pcoJpegBusy = "1";

    const complete = () => {
      image.dataset.pcoJpegBusy = "0";
    };

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
    if (busy || document.visibilityState !== "visible") return;

    const images = cameras();
    if (!images.length) return;

    busy = true;

    try {
      const now = Date.now();
      const slots = [...new Set(
        images
          .map((image) => Number(image.dataset.pcoLiveJpegSlot))
          .filter((slot) => Number.isInteger(slot) && slot >= 0 && slot <= 2)
      )];

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

  window.setTimeout(() => tick(true), 250);
  window.setInterval(() => tick(false), 200);
})();
