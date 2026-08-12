// PINCABOS_EXPLORER_NATIVE_TABLES_V1_JS
(() => {
  "use strict";

  if (window.__pcoExplorerNativeTablesV1) return;
  window.__pcoExplorerNativeTablesV1 = true;

  const pageUrl = new URL(window.location.href);
  const root = pageUrl.searchParams.get("root") || "Tables";
  const currentPath = (
    pageUrl.searchParams.get("path") || ""
  ).replace(/^\/+|\/+$/g, "");

  if (root !== "Tables") return;
  const isTablesRoot = currentPath === "";

  const STATUS_CLASSES = [
    "is-go",
    "is-problem",
    "is-running",
    "is-warning",
    "is-indexing"
  ];

  let statusTimer = null;
  let requestBusy = false;

  const COUNT_BADGE_ID = "pco-explorer-installed-table-count";

  function normalizedText(node) {
    return String(node?.textContent || "")
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();
  }

  function findExplorerCard() {
    const titles = Array.from(
      document.querySelectorAll("h1,h2,h3,h4,strong")
    ).filter(
      node => normalizedText(node) === "pincab explorer"
    );

    for (const title of titles) {
      let candidate = title.parentElement;

      for (
        let depth = 0;
        candidate && depth < 7;
        depth += 1
      ) {
        const text = normalizedText(candidate);
        const controls = candidate.querySelectorAll(
          "a,button,input[type='button'],input[type='submit']"
        ).length;

        if (
          text.includes("actions")
          && controls >= 5
        ) {
          return candidate;
        }

        candidate = candidate.parentElement;
      }
    }

    return null;
  }

  function ensureCountBadge() {
    const card = findExplorerCard();
    if (!card) return null;

    card.classList.add(
      "pco-explorer-card-with-table-count"
    );

    let badge = document.getElementById(
      COUNT_BADGE_ID
    );

    if (!badge) {
      badge = document.createElement("div");
      badge.id = COUNT_BADGE_ID;
      badge.className = (
        "pco-explorer-installed-table-count is-loading"
      );
      badge.setAttribute("role", "status");
      badge.setAttribute("aria-live", "polite");
      badge.innerHTML = [
        '<span class="pco-explorer-table-count-icon" aria-hidden="true">🎮</span>',
        '<span class="pco-explorer-table-count-value">…</span>',
        '<span class="pco-explorer-table-count-label">tables installées</span>'
      ].join("");
      card.appendChild(badge);
    }

    return badge;
  }

  async function refreshCount() {
    const badge = ensureCountBadge();
    if (!badge) return;

    try {
      const payload = await json(
        "/api/explorer/table-count"
      );

      const count = Math.max(
        0,
        Math.trunc(Number(payload.count) || 0)
      );

      const value = badge.querySelector(
        ".pco-explorer-table-count-value"
      );
      const label = badge.querySelector(
        ".pco-explorer-table-count-label"
      );

      if (value) {
        value.textContent = count.toLocaleString(
          "fr-CA"
        );
      }

      if (label) {
        label.textContent = (
          count === 1
            ? "table installée"
            : "tables installées"
        );
      }

      badge.classList.remove(
        "is-loading",
        "is-error"
      );
    } catch (error) {
      badge.classList.remove("is-loading");
      badge.classList.add("is-error");
      console.error(
        "PinCabOS table count:",
        error
      );
    }
  }

  async function json(url, options = {}) {
    const response = await fetch(url, {
      cache: "no-store",
      ...options
    });

    let payload = {};
    try {
      payload = await response.json();
    } catch (_) {
      payload = {};
    }

    if (!response.ok || payload.ok === false) {
      throw new Error(
        payload.error || `Erreur HTTP ${response.status}`
      );
    }

    return payload;
  }

  function toast(text, isError = false) {
    let node = document.getElementById(
      "pco-native-table-toast"
    );

    if (!node) {
      node = document.createElement("div");
      node.id = "pco-native-table-toast";
      node.className = "pco-native-table-toast";
      document.body.appendChild(node);
    }

    node.textContent = text;
    node.classList.toggle("is-error", isError);
    node.classList.add("is-visible");

    window.clearTimeout(node.__hideTimer);
    node.__hideTimer = window.setTimeout(() => {
      node.classList.remove("is-visible");
    }, 2800);
  }

  function setToolStatus(tool, status, label) {
    STATUS_CLASSES.forEach(name => {
      tool.classList.remove(name);
    });

    tool.classList.add(`is-${status}`);

    const badge = tool.querySelector(
      ".pco-native-status"
    );

    if (badge) {
      STATUS_CLASSES.forEach(name => {
        badge.classList.remove(name);
      });
      badge.classList.add(`is-${status}`);
      badge.textContent = label;
    }
  }

  function restoreToolStatus(tool) {
    const status = (
      tool.dataset.pcoBaseStatus || "indexing"
    );
    const badge = tool.querySelector(
      ".pco-native-status"
    );
    const label = (
      badge?.dataset.pcoBaseLabel || "··· ANALYSE"
    );

    tool.classList.remove("is-active");
    setToolStatus(tool, status, label);
  }

  function applyStatus(payload) {
    const active = Boolean(payload.active);
    const phase = String(payload.phase || "idle");
    const activeRel = (
      active
      ? String(payload.state?.rel || "")
      : ""
    );

    document.querySelectorAll(
      ".pco-native-table-tools"
    ).forEach(tool => {
      const rel = String(tool.dataset.pcoRel || "");
      const isActive = active && rel === activeRel;
      const play = tool.querySelector(
        '[data-pco-action="play"]'
      );
      const stop = tool.querySelector(
        '[data-pco-action="stop"]'
      );

      if (play) {
        const baseDisabled = (
          play.dataset.pcoBaseDisabled === "1"
        );
        play.disabled = baseDisabled || active || requestBusy;
      }

      if (stop) {
        stop.disabled = !isActive || requestBusy;
      }

      if (isActive) {
        tool.classList.add("is-active");

        const stopping = (
          phase === "stopping"
          || phase === "stopped"
        );

        setToolStatus(
          tool,
          "running",
          stopping ? "■ ARRÊT" : "● EN TEST"
        );
      } else {
        restoreToolStatus(tool);
      }
    });

    return active;
  }

  function scheduleStatus(active) {
    window.clearTimeout(statusTimer);
    statusTimer = window.setTimeout(
      refreshStatus,
      active ? 2000 : 10000
    );
  }

  async function refreshStatus() {
    try {
      const payload = await json(
        "/api/explorer/table-test/status"
      );
      scheduleStatus(applyStatus(payload));
    } catch (error) {
      console.error(
        "PinCabOS native table status:",
        error
      );
      scheduleStatus(false);
    }
  }

  async function play(rel) {
    requestBusy = true;
    toast("Préparation du test…");
    applyStatus({
      active: false,
      phase: "starting",
      state: {}
    });

    try {
      const payload = await json(
        "/api/explorer/table-test/play",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({ path: rel })
        }
      );

      toast("Table lancée. VPinFE a été fermé.");
      scheduleStatus(applyStatus(payload));
    } catch (error) {
      toast(error.message, true);
      await refreshStatus();
    } finally {
      requestBusy = false;
      window.setTimeout(refreshStatus, 0);
    }
  }

  async function stop() {
    requestBusy = true;
    toast("Arrêt de la table…");

    try {
      const payload = await json(
        "/api/explorer/table-test/stop",
        { method: "POST" }
      );

      toast("Table arrêtée. VPinFE redémarre.");
      scheduleStatus(applyStatus(payload));
    } catch (error) {
      toast(error.message, true);
      await refreshStatus();
    } finally {
      requestBusy = false;
      window.setTimeout(refreshStatus, 0);
    }
  }

  document.addEventListener("click", event => {
    const control = event.target.closest(
      "[data-pco-action]"
    );

    if (!control || control.disabled) return;

    const action = control.dataset.pcoAction;
    const rel = String(control.dataset.pcoRel || "");

    if (action === "play" && rel) {
      event.preventDefault();
      play(rel);
    }

    if (action === "stop") {
      event.preventDefault();
      stop();
    }
  });

// PINCABOS_COMMANDER_ZERO_BACKGROUND_V1_JS
  // Aucun fetch, timer, pageshow ou visibilitychange au chargement.
  // Play et Stop restent déclenchés uniquement par un clic.
})();

