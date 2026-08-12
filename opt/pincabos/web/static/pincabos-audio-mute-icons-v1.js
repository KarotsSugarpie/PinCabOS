(() => {
  "use strict";

  function normalize() {
    document.querySelectorAll("#pco-lobby .pco-audio-volume-card .pco-av-mute").forEach((btn) => {
      const raw = (btn.textContent || "").trim().toUpperCase();
      if (raw === "OFF") {
        btn.textContent = "🔇";
        btn.title = "Muet";
      } else if (raw === "ON") {
        btn.textContent = "🔊";
        btn.title = "Actif";
      }
    });
  }

  function start() {
    normalize();

    let timer = null;
    new MutationObserver(() => {
      clearTimeout(timer);
      timer = setTimeout(normalize, 50);
    }).observe(document.documentElement, {
      childList: true,
      subtree: true,
      characterData: true
    });

    setInterval(normalize, 1000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
