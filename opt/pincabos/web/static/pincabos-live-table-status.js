/* PINCABOS_LIVE_TABLE_STATUS_CARD_V5 */
(() => {
  "use strict";

  const root = document.getElementById("pincabos-live-table-status-root");
  if (root && root.dataset.liveTableStatusReady === "1") return;
  if (root) root.dataset.liveTableStatusReady = "1";

  let current = null;
  let polling = false;

  const batchSelectors = [
    "#pincabos-batch-live-status-card",
    "#pincabos-batch-status-card",
    "#pincabos-batch-live-card",
    ".pincabos-batch-live-status-card",
    ".pincabos-batch-status-card",
    ".pincabos-batch-live-card"
  ];

  const languageSelectors = [
    "#language-switcher",
    "#language-selector",
    "#language-select",
    "#languageSelect",
    "select[name='language']",
    "[data-language-control]",
    "[data-language-selector]",
    "[data-testid='language-selector']"
  ];

  const visible = (el) => {
    if (!el) return false;
    const s = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return s.display !== "none" && s.visibility !== "hidden" && r.width > 0 && r.height > 0;
  };

  const elementText = (el) => (el?.textContent || "").replace(/\s+/g, "");

  const hasVisibleMediaOrUi = (el) => {
    if (!el) return false;
    return [...el.querySelectorAll("img,svg,canvas,video,iframe,button,a,input,select,textarea")].some(visible);
  };

  const isDecorativePanel = (el) => {
    if (!el) return false;
    const s = getComputedStyle(el);
    const bw =
      parseFloat(s.borderTopWidth || "0") +
      parseFloat(s.borderRightWidth || "0") +
      parseFloat(s.borderBottomWidth || "0") +
      parseFloat(s.borderLeftWidth || "0");
    const br =
      parseFloat(s.borderTopLeftRadius || "0") +
      parseFloat(s.borderTopRightRadius || "0") +
      parseFloat(s.borderBottomLeftRadius || "0") +
      parseFloat(s.borderBottomRightRadius || "0");
    return (
      bw > 0 ||
      br > 12 ||
      s.boxShadow !== "none" ||
      s.backgroundColor !== "rgba(0, 0, 0, 0)"
    );
  };

  const batchCard = () => {
    for (const selector of batchSelectors) {
      const el = document.querySelector(selector);
      if (el && el !== root) return el;
    }
    return null;
  };

  const languageAnchor = () => {
    for (const selector of languageSelectors) {
      const el = document.querySelector(selector);
      if (el) return el;
    }

    return [...document.querySelectorAll("label,button,select,span,div")]
      .find((el) => {
        const text = (el.textContent || "").trim().toLowerCase();
        if (!(text === "language" || text.startsWith("language :") || text === "langue" || text.startsWith("langue :"))) {
          return false;
        }
        const r = el.getBoundingClientRect();
        return r.width > 0 && r.height > 0;
      }) || null;
  };

  const positionCard = () => {
    if (!root || root.hidden) return;

    const batch = batchCard();
    if (batch && visible(batch)) {
      const r = batch.getBoundingClientRect();
      root.style.top = `${Math.round(r.bottom + 12)}px`;
      root.style.right = `${Math.max(16, Math.round(innerWidth - r.right))}px`;
      return;
    }

    const language = languageAnchor();
    if (language && visible(language)) {
      const r = language.getBoundingClientRect();
      root.style.top = `${Math.round(r.bottom + 12)}px`;
      root.style.right = `${Math.max(16, Math.round(innerWidth - r.right))}px`;
      return;
    }

    root.style.top = "76px";
    root.style.right = "16px";
  };

  const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  }[char]));

  function markHidden(el) {
    if (!el || el.dataset.pincabosKilledEmptyLogoSlot === "1") return;
    el.dataset.pincabosKilledEmptyLogoSlot = "1";
    el.style.setProperty("display", "none", "important");
    el.style.setProperty("visibility", "hidden", "important");
    el.style.setProperty("min-height", "0", "important");
    el.style.setProperty("height", "0", "important");
    el.style.setProperty("margin", "0", "important");
    el.style.setProperty("padding", "0", "important");
    el.style.setProperty("border", "0", "important");
    el.style.setProperty("overflow", "hidden", "important");
  }

  function findLogoImage() {
    const imgs = [...document.querySelectorAll("img")].filter((img) => visible(img));
    const candidates = imgs.filter((img) => {
      const r = img.getBoundingClientRect();
      const sig = `${img.src || ""} ${img.alt || ""} ${img.className || ""}`.toLowerCase();
      return (
        r.left < Math.max(420, window.innerWidth * 0.35) &&
        r.top < Math.max(260, window.innerHeight * 0.35) &&
        r.width >= 80 &&
        r.height >= 80 &&
        (sig.includes("pincabos") || sig.includes("logo") || img.src.startsWith("data:") || true)
      );
    });

    return candidates.sort((a, b) => {
      const ar = a.getBoundingClientRect();
      const br = b.getBoundingClientRect();
      return (br.width * br.height) - (ar.width * ar.height);
    })[0] || null;
  }

  function findLogoCard(logoImg) {
    if (!logoImg) return null;

    let el = logoImg;
    let best = null;

    while (el && el !== document.body) {
      const r = el.getBoundingClientRect();
      if (
        r.width >= 140 && r.width <= 360 &&
        r.height >= 140 && r.height <= 340 &&
        r.left < Math.max(420, window.innerWidth * 0.35)
      ) {
        best = el;
      }
      el = el.parentElement;
    }

    return best || logoImg.parentElement;
  }

  function killEmptyPanelBelowLogo() {
    const logo = findLogoImage();
    if (!logo) return;

    const logoCard = findLogoCard(logo);
    if (!logoCard) return;

    const logoRect = logoCard.getBoundingClientRect();
    const searchRoot = logoCard.parentElement || document.body;

    const candidates = [];

    for (const el of searchRoot.children) {
      if (!visible(el) || el === logoCard || el.contains(logoCard) || logoCard.contains(el)) continue;

      const r = el.getBoundingClientRect();
      const sameColumn =
        Math.abs(r.left - logoRect.left) <= 20 &&
        Math.abs(r.width - logoRect.width) <= 40;

      const belowLogo =
        r.top >= logoRect.bottom + 4 &&
        r.top <= logoRect.bottom + 180;

      const properSize =
        r.width >= 120 && r.width <= 380 &&
        r.height >= 20 && r.height <= 140;

      const empty = elementText(el).length === 0 && !hasVisibleMediaOrUi(el);
      const decorative = isDecorativePanel(el);

      if (sameColumn && belowLogo && properSize && empty && decorative) {
        candidates.push(el);
      }
    }

    candidates.sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top);

    if (candidates.length) {
      markHidden(candidates[0]);

      let parent = candidates[0].parentElement;
      while (parent && parent !== document.body) {
        const text = elementText(parent);
        const childPanels = [...parent.children].filter((x) => visible(x));
        if (text.length === 0 && childPanels.length <= 1) {
          markHidden(parent);
          parent = parent.parentElement;
          continue;
        }
        break;
      }
      return;
    }

    // Fallback agressif si le panneau est imbriqué plus profond
    const deepNodes = [...searchRoot.querySelectorAll("div,section,aside")];
    for (const el of deepNodes) {
      if (!visible(el) || el === logoCard || el.contains(logoCard) || logoCard.contains(el)) continue;

      const r = el.getBoundingClientRect();
      const sameColumn =
        r.left >= logoRect.left - 16 &&
        r.right <= logoRect.right + 16;

      const belowLogo =
        r.top >= logoRect.bottom + 4 &&
        r.top <= logoRect.bottom + 180;

      const properSize =
        r.width >= 120 && r.width <= 380 &&
        r.height >= 20 && r.height <= 140;

      const empty = elementText(el).length === 0 && !hasVisibleMediaOrUi(el);
      const decorative = isDecorativePanel(el);

      if (sameColumn && belowLogo && properSize && empty && decorative) {
        markHidden(el);
        break;
      }
    }
  }

  const requestStop = async (button) => {
    if (!current?.stop_token || !button) return;

    button.disabled = true;
    button.textContent = "Stopping...";

    try {
      const response = await fetch("/api/live-table-status/stop", {
        method: "POST",
        credentials: "same-origin",
        cache: "no-store",
        headers: {
          "Accept": "application/json",
          "Content-Type": "application/json",
          "X-Requested-With": "PinCabOSLiveTableStatus",
          "X-PinCabOS-Live-Stop-Token": current.stop_token
        },
        body: JSON.stringify({ stop_token: current.stop_token })
      });

      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) throw new Error(data.error || "stop_refused");

      setTimeout(poll, 350);
    } catch (_) {
      button.disabled = false;
      button.textContent = "Stop";
      setTimeout(poll, 700);
    }
  };

  const render = (state) => {
    if (!root) return;

    current = state;
    root.hidden = false;

    root.innerHTML = `
      <section class="pincabos-live-table-status-card" aria-live="polite">
        <div class="pincabos-live-table-status-copy">
          <div class="pincabos-live-table-status-kicker">Table in play</div>
          <div class="pincabos-live-table-status-name" title="${escapeHtml(state.table_name)}">${escapeHtml(state.table_name)}</div>
        </div>
        <button type="button" class="pincabos-live-table-stop-button">Stop</button>
      </section>
    `;

    const button = root.querySelector(".pincabos-live-table-stop-button");
    if (button) button.addEventListener("click", () => requestStop(button));

    killEmptyPanelBelowLogo();
    positionCard();
  };

  const hide = () => {
    current = null;
    if (root) {
      root.hidden = true;
      root.innerHTML = "";
    }
    killEmptyPanelBelowLogo();
  };

  const poll = async () => {
    if (!root) {
      killEmptyPanelBelowLogo();
      return;
    }

    if (polling) return;
    polling = true;

    try {
      const response = await fetch("/api/live-table-status", {
        credentials: "same-origin",
        cache: "no-store",
        headers: { "Accept": "application/json" }
      });

      if (!response.ok) throw new Error("status_unavailable");

      const state = await response.json();
      if (!state.running) {
        hide();
        return;
      }

      const changed =
        !current ||
        String(current.pid) !== String(state.pid) ||
        String(current.table_name) !== String(state.table_name) ||
        String(current.stop_token) !== String(state.stop_token);

      if (changed) {
        render(state);
      } else {
        killEmptyPanelBelowLogo();
        positionCard();
      }
    } catch (_) {
      hide();
    } finally {
      polling = false;
    }
  };

  addEventListener("resize", () => {
    killEmptyPanelBelowLogo();
    positionCard();
  }, { passive: true });

  addEventListener("scroll", () => {
    killEmptyPanelBelowLogo();
    positionCard();
  }, { passive: true, capture: true });

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
      killEmptyPanelBelowLogo();
      poll();
    }
  });

  const runCleanup = () => killEmptyPanelBelowLogo();

  runCleanup();
  setTimeout(runCleanup, 150);
  setTimeout(runCleanup, 500);
  setTimeout(runCleanup, 1200);
  setTimeout(runCleanup, 2500);

  new MutationObserver(() => {
    killEmptyPanelBelowLogo();
  }).observe(document.documentElement, {
    childList: true,
    subtree: true,
    attributes: true
  });

  poll();
  setInterval(poll, 2000);
})();
