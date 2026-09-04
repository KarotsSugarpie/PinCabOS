// PINCABOS_EXPLORER_DUAL_LAUNCH_V1_JS
// PINCABOS_EXPLORER_NATIVE_TABLES_V1_JS
// PINCABOS_EXPLORER_GLOBAL_SEARCH_V1_JS
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
  let globalCatalog = null;
  let globalCatalogPromise = null;
  let globalSearchTimer = null;

  const COUNT_BADGE_ID = "pco-explorer-installed-table-count";
  const GLOBAL_SEARCH_PANEL_ID = "pco-explorer-global-search-results";

  function normalizedText(node) {
    return String(node?.textContent || "")
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();
  }

  function searchText(value) {
    return String(value || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
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
      const plays = Array.from(
        tool.querySelectorAll(
          '[data-pco-action="play"], '
          + '[data-pco-action="play-legacy"], '
          + '[data-pco-action="play-pup"]'
        )
      );

      const stop = tool.querySelector(
        '[data-pco-action="stop"]'
      );

      plays.forEach(play => {
        const baseDisabled = (
          play.dataset.pcoBaseDisabled === "1"
        );

        play.disabled = (
          baseDisabled
          || active
          || requestBusy
        );
      });

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

  async function play(rel, mode = "original") {
    requestBusy = true;

    const pupMode = mode === "pup";

    toast(
      pupMode
        ? "Préparation du test PuP…"
        : "Préparation du test Legacy…"
    );
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
          body: JSON.stringify({
            path: rel,
            mode: mode
          })
        }
      );

      toast(
        pupMode
          ? "Table lancée en mode PuP. VPinFE a été fermé."
          : "Table lancée en mode Legacy. VPinFE a été fermé."
      );
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

  function ensureGlobalSearchPanel() {
    let panel = document.getElementById(GLOBAL_SEARCH_PANEL_ID);
    if (panel) return panel;

    const main = document.querySelector(".pcx-main");
    const head = main?.querySelector(".pcx-head");
    if (!main || !head) return null;

    panel = document.createElement("section");
    panel.id = GLOBAL_SEARCH_PANEL_ID;
    panel.hidden = true;
    panel.setAttribute("aria-live", "polite");
    panel.style.margin = "14px 0";
    panel.style.padding = "12px";
    panel.style.border = "1px solid rgba(255,176,0,.35)";
    panel.style.borderRadius = "12px";
    panel.style.background = "rgba(12,8,20,.88)";
    head.insertAdjacentElement("afterend", panel);
    return panel;
  }

  function setExplorerNativeVisibility(visible) {
    const targets = [
      document.getElementById("pcxList"),
      document.getElementById("pcxGrid"),
      ...document.querySelectorAll(".pcx-pagination")
    ].filter(Boolean);

    targets.forEach(node => {
      if (visible) {
        node.removeAttribute("data-pco-global-search-hidden");
        node.hidden = false;
      } else {
        node.setAttribute("data-pco-global-search-hidden", "1");
        node.hidden = true;
      }
    });
  }

  async function loadGlobalCatalog() {
    if (Array.isArray(globalCatalog)) return globalCatalog;
    if (globalCatalogPromise) return globalCatalogPromise;

    globalCatalogPromise = json(
      "/api/explorer/table-test/list?path="
    ).then(payload => {
      globalCatalog = Array.isArray(payload.tables)
        ? payload.tables
        : [];
      return globalCatalog;
    }).finally(() => {
      globalCatalogPromise = null;
    });

    return globalCatalogPromise;
  }

  function tableSearchHaystack(table) {
    return searchText([
      table?.name,
      table?.rel,
      table?.main_vpx_name,
      table?.vps_id,
      table?.content_summary,
      table?.test_log_status,
      ...(Array.isArray(table?.problems) ? table.problems : []),
      ...(Array.isArray(table?.warnings) ? table.warnings : [])
    ].filter(Boolean).join(" "));
  }

  function statusLabel(table) {
    const status = String(table?.test_log_status || "VERIFY").toUpperCase();
    if (status === "GO") return "✓ GO";
    if (status === "NOGO") return "✗ NOGO";
    if (status === "RUNNING") return "● EN TEST";
    return "! À VÉRIFIER";
  }

  function renderGlobalResults(query, tables) {
    const panel = ensureGlobalSearchPanel();
    if (!panel) return;

    const needle = searchText(query);
    const matches = tables.filter(table => (
      tableSearchHaystack(table).includes(needle)
    ));

    panel.replaceChildren();
    panel.hidden = false;
    setExplorerNativeVisibility(false);

    const summary = document.createElement("div");
    summary.style.marginBottom = "10px";
    summary.style.fontWeight = "800";
    summary.textContent = (
      `${matches.length} résultat${matches.length === 1 ? "" : "s"} `
      + `sur ${tables.length} tables installées`
    );
    panel.appendChild(summary);

    if (!matches.length) {
      const empty = document.createElement("div");
      empty.textContent = `Aucune table ne correspond à « ${query} ».`;
      panel.appendChild(empty);
      return;
    }

    const tableNode = document.createElement("table");
    tableNode.className = "pcx-table";

    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");
    ["Nom", "État", "Contenu", "Action"].forEach(label => {
      const th = document.createElement("th");
      th.textContent = label;
      headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    tableNode.appendChild(thead);

    const tbody = document.createElement("tbody");
    matches.forEach(table => {
      const tr = document.createElement("tr");
      tr.className = "pcx-row pco-global-search-row";

      const nameTd = document.createElement("td");
      const nameLink = document.createElement("a");
      nameLink.className = "pcx-name";
      nameLink.href = (
        "/tools/commander?root=Tables&path="
        + encodeURIComponent(String(table?.rel || table?.name || ""))
      );
      nameLink.textContent = `📁 ${String(table?.name || table?.rel || "Table")}`;
      nameTd.appendChild(nameLink);

      const statusTd = document.createElement("td");
      statusTd.textContent = statusLabel(table);

      const contentTd = document.createElement("td");
      contentTd.textContent = String(
        table?.content_summary || "Analyse non disponible"
      );

      const actionTd = document.createElement("td");
      const openLink = document.createElement("a");
      openLink.className = "pcx-small";
      openLink.href = nameLink.href;
      openLink.textContent = "Ouvrir";
      actionTd.appendChild(openLink);

      [nameTd, statusTd, contentTd, actionTd].forEach(td => {
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });

    tableNode.appendChild(tbody);
    panel.appendChild(tableNode);
  }

  function clearGlobalSearch() {
    window.clearTimeout(globalSearchTimer);
    const panel = document.getElementById(GLOBAL_SEARCH_PANEL_ID);
    if (panel) {
      panel.hidden = true;
      panel.replaceChildren();
    }
    setExplorerNativeVisibility(true);
  }

  function bindGlobalSearch() {
    if (!isTablesRoot) return;

    const input = document.getElementById("pcxSearch");
    if (!input || input.dataset.pcoGlobalSearchBound === "1") return;

    input.dataset.pcoGlobalSearchBound = "1";
    input.placeholder = "Rechercher dans toutes les tables...";
    input.setAttribute(
      "aria-label",
      "Rechercher dans toutes les tables installées"
    );

    input.addEventListener("input", () => {
      const query = String(input.value || "").trim();
      window.clearTimeout(globalSearchTimer);

      if (!query) {
        clearGlobalSearch();
        return;
      }

      globalSearchTimer = window.setTimeout(async () => {
        try {
          const tables = await loadGlobalCatalog();
          if (String(input.value || "").trim() !== query) return;
          renderGlobalResults(query, tables);
        } catch (error) {
          toast(
            `Recherche globale impossible : ${error.message}`,
            true
          );
        }
      }, 120);
    });

    input.addEventListener("keydown", event => {
      if (event.key !== "Escape") return;
      input.value = "";
      clearGlobalSearch();
      if (typeof window.pcxFilter === "function") {
        window.pcxFilter();
      }
    });
  }

  document.addEventListener("click", event => {
    const control = event.target.closest(
      "[data-pco-action]"
    );

    if (!control || control.disabled) return;

    const action = control.dataset.pcoAction;
    const rel = String(control.dataset.pcoRel || "");

    if (
      (action === "play" || action === "play-legacy")
      && rel
    ) {
      event.preventDefault();
      play(rel, "original");
    }

    if (action === "play-pup" && rel) {
      event.preventDefault();
      play(rel, "pup");
    }

    if (action === "stop") {
      event.preventDefault();
      stop();
    }
  });

  // PINCABOS_COMMANDER_ZERO_BACKGROUND_V1_JS
  // Aucun scan ni polling au chargement. La recherche globale ne charge
  // le catalogue complet qu'après une saisie explicite de l'utilisateur.
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindGlobalSearch);
  } else {
    bindGlobalSearch();
  }
})();
