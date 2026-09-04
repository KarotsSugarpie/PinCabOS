(function () {
  "use strict";

  if (window.__pcoExplorerAnalysisReportV1) return;
  window.__pcoExplorerAnalysisReportV1 = true;

  var pageUrl = new URL(window.location.href);
  var root = pageUrl.searchParams.get("root") || "Tables";
  var rel = (pageUrl.searchParams.get("path") || "").replace(/^\/+|\/+$/g, "");

  if (root !== "Tables" || !rel) return;

  var OVERLAY_ID = "pco-explorer-analysis-report";
  var STYLE_ID = "pco-explorer-analysis-report-style";

  function requestJson(url) {
    return fetch(url, { cache: "no-store" }).then(function (response) {
      return response.json().catch(function () { return {}; }).then(function (payload) {
        if (!response.ok || payload.ok === false) {
          throw new Error(payload.error || ("Erreur HTTP " + response.status));
        }
        return payload;
      });
    });
  }

  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return;

    var style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent =
      "#" + OVERLAY_ID + "{position:fixed;inset:0;z-index:2147482600;display:flex;align-items:center;justify-content:center;padding:28px;background:rgba(0,0,0,.78);backdrop-filter:blur(4px)}" +
      "#" + OVERLAY_ID + "[hidden]{display:none!important}" +
      "#" + OVERLAY_ID + " .pco-analysis-dialog{width:min(980px,96vw);max-height:88vh;overflow:auto;border:1px solid rgba(255,145,25,.55);border-radius:18px;padding:20px;background:#0f0918;color:#f7f2fb;box-shadow:0 24px 70px rgba(0,0,0,.7)}" +
      "#" + OVERLAY_ID + " .pco-analysis-head{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;margin-bottom:16px}" +
      "#" + OVERLAY_ID + " h2{margin:0}" +
      "#" + OVERLAY_ID + " .pco-analysis-close{min-width:38px;height:38px;border:1px solid #ff6b6b;border-radius:9px;background:#8c1111;color:#fff;cursor:pointer;font-weight:900}" +
      "#" + OVERLAY_ID + " .pco-analysis-verdict{display:inline-flex;align-items:center;gap:8px;margin:8px 0 16px;padding:8px 12px;border-radius:999px;font-weight:900}" +
      "#" + OVERLAY_ID + " .is-go{background:rgba(28,155,75,.22);border:1px solid #42c778}" +
      "#" + OVERLAY_ID + " .is-nogo{background:rgba(190,34,34,.22);border:1px solid #ff5b5b}" +
      "#" + OVERLAY_ID + " .is-running{background:rgba(52,125,220,.22);border:1px solid #66a8ff}" +
      "#" + OVERLAY_ID + " .is-verify{background:rgba(222,143,24,.18);border:1px solid #ffad32}" +
      "#" + OVERLAY_ID + " .pco-analysis-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:14px 0}" +
      "#" + OVERLAY_ID + " .pco-analysis-item{min-width:0;padding:11px 12px;border:1px solid rgba(255,255,255,.12);border-radius:11px;background:rgba(255,255,255,.035)}" +
      "#" + OVERLAY_ID + " .pco-analysis-item strong{color:#ffb04a}" +
      "#" + OVERLAY_ID + " .pco-analysis-detail{margin-top:4px;color:#d8cbe4;font-size:13px;overflow-wrap:anywhere}" +
      "#" + OVERLAY_ID + " .pco-analysis-reasons{margin:14px 0 0;padding:12px 14px;border-left:3px solid #ff8a00;background:rgba(255,138,0,.07)}" +
      "#" + OVERLAY_ID + " .pco-analysis-source{margin-top:16px;color:#ad9dbc;font-size:12px}" +
      "@media(max-width:720px){#" + OVERLAY_ID + "{padding:10px}#" + OVERLAY_ID + " .pco-analysis-grid{grid-template-columns:1fr}}";
    document.head.appendChild(style);
  }

  function ensureOverlay() {
    ensureStyle();
    var overlay = document.getElementById(OVERLAY_ID);
    if (overlay) return overlay;

    overlay = document.createElement("div");
    overlay.id = OVERLAY_ID;
    overlay.hidden = true;
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-label", "Rapport d'analyse de la table");
    overlay.innerHTML = '<div class="pco-analysis-dialog"></div>';
    document.body.appendChild(overlay);

    overlay.addEventListener("click", function (event) {
      if (event.target === overlay || event.target.closest(".pco-analysis-close")) {
        overlay.hidden = true;
      }
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && !overlay.hidden) overlay.hidden = true;
    });

    return overlay;
  }

  function verdict(health) {
    var status = String((health && health.test_log_status) || "VERIFY").toUpperCase();
    if (status === "GO") return { cls: "is-go", label: "✓ GO — dernier test validé" };
    if (status === "NOGO") return { cls: "is-nogo", label: "✗ NOGO — dernier test en erreur" };
    if (status === "RUNNING") return { cls: "is-running", label: "● EN TEST" };
    return { cls: "is-verify", label: "! À VÉRIFIER" };
  }

  function addItem(grid, label, value, detail) {
    var item = document.createElement("div");
    item.className = "pco-analysis-item";

    var strong = document.createElement("strong");
    strong.textContent = label + " : " + value;
    item.appendChild(strong);

    if (detail) {
      var text = document.createElement("div");
      text.className = "pco-analysis-detail";
      text.textContent = detail;
      item.appendChild(text);
    }

    grid.appendChild(item);
  }

  function yesNo(value) {
    return value ? "Détecté" : "Non observé";
  }

  function render(health) {
    health = health || {};
    var inventory = health.content_inventory && typeof health.content_inventory === "object"
      ? health.content_inventory
      : {};
    var state = verdict(health);
    var overlay = ensureOverlay();
    var dialog = overlay.querySelector(".pco-analysis-dialog");
    dialog.replaceChildren();

    var head = document.createElement("div");
    head.className = "pco-analysis-head";

    var titleWrap = document.createElement("div");
    var title = document.createElement("h2");
    title.textContent = "Rapport d’analyse PinCabOS";
    var subtitle = document.createElement("div");
    subtitle.className = "pco-analysis-detail";
    subtitle.textContent = String(health.name || health.rel || rel);
    titleWrap.appendChild(title);
    titleWrap.appendChild(subtitle);

    var close = document.createElement("button");
    close.type = "button";
    close.className = "pco-analysis-close";
    close.textContent = "X";
    close.setAttribute("aria-label", "Fermer le rapport");
    head.appendChild(titleWrap);
    head.appendChild(close);
    dialog.appendChild(head);

    var badge = document.createElement("div");
    badge.className = "pco-analysis-verdict " + state.cls;
    badge.textContent = state.label;
    dialog.appendChild(badge);

    var grid = document.createElement("div");
    grid.className = "pco-analysis-grid";

    addItem(grid, "VPX", Number(health.vpx_count || 0) > 0 ? ("Présent (" + health.vpx_count + ")") : "Absent", health.main_vpx_name ? ("Principal : " + health.main_vpx_name) : "");
    addItem(grid, "B2S", Number(health.b2s_count || 0) > 0 ? ("Présent (" + health.b2s_count + ")") : "Non observé", inventory.b2s ? "Utilisation confirmée par le journal de test." : "Aucune utilisation B2S confirmée dans le dernier journal.");
    addItem(grid, "PuP", yesNo(inventory.pup), inventory.pup ? "PuP observé dans le contenu ou le journal du dernier test." : "Aucune utilisation PuP confirmée dans les données actuelles.");
    addItem(grid, "FlexDMD / UltraDMD", "Non déterminé", "Le backend courant ne publie pas encore une preuve FlexDMD fiable; le rapport n’invente donc pas de statut.");
    addItem(grid, "ROM", inventory.rom ? "Utilisée" : "Non observée", inventory.game_id ? ("Game ID observé : " + inventory.game_id) : "L’absence de ROM observée n’est pas considérée comme une erreur; les tables PuP-only restent valides.");
    addItem(grid, "Serum", yesNo(inventory.serum), "Preuve issue du contenu/runtime analysé par PinCabOS.");
    addItem(grid, "AltSound", yesNo(inventory.altsound), "Preuve issue du contenu/runtime analysé par PinCabOS.");
    addItem(grid, "AltColor", yesNo(inventory.altcolor), "PAL/VNI/PAC ou activité runtime détectée par PinCabOS.");
    addItem(grid, "VPS", health.vps_exact ? "Associé" : "Non associé", health.vps_id ? ("VPS ID : " + health.vps_id) : "");
    addItem(grid, "VBS", health.has_vbs ? "Présent" : "Non observé", (health.has_info ? "INFO ✓" : "INFO —") + " · " + (health.has_pov ? "POV ✓" : "POV —") + " · " + (health.has_ini ? "INI ✓" : "INI —"));
    dialog.appendChild(grid);

    var reasons = [];
    [health.test_log_reasons, health.problems, health.warnings].forEach(function (list) {
      if (Array.isArray(list)) list.forEach(function (item) { if (item) reasons.push(String(item)); });
    });

    if (reasons.length) {
      var box = document.createElement("div");
      box.className = "pco-analysis-reasons";
      var boxTitle = document.createElement("strong");
      boxTitle.textContent = "Détails du dernier test";
      box.appendChild(boxTitle);
      var ul = document.createElement("ul");
      reasons.forEach(function (reason) {
        var li = document.createElement("li");
        li.textContent = reason;
        ul.appendChild(li);
      });
      box.appendChild(ul);
      dialog.appendChild(box);
    }

    var source = document.createElement("div");
    source.className = "pco-analysis-source";
    source.textContent = "Verdict GO/NOGO : PinCabOS-Test.log uniquement. Inventaire : analyse profonde déclenchée au clic. Aucun statut manquant n’est converti artificiellement en erreur.";
    dialog.appendChild(source);

    overlay.hidden = false;
    close.focus();
  }

  function openReport() {
    var overlay = ensureOverlay();
    var dialog = overlay.querySelector(".pco-analysis-dialog");
    dialog.textContent = "Analyse profonde de la table…";
    overlay.hidden = false;

    requestJson("/api/explorer/table-test/health?path=" + encodeURIComponent(rel))
      .then(function (payload) { render(payload.health || {}); })
      .catch(function (error) {
        dialog.replaceChildren();
        var title = document.createElement("h2");
        title.textContent = "Rapport indisponible";
        var detail = document.createElement("p");
        detail.textContent = error.message;
        var close = document.createElement("button");
        close.type = "button";
        close.className = "pco-analysis-close";
        close.textContent = "X";
        dialog.appendChild(title);
        dialog.appendChild(detail);
        dialog.appendChild(close);
      });
  }

  function installButton() {
    var tool = document.querySelector('.pco-native-table-tools[data-pco-rel="' + CSS.escape(rel) + '"]') || document.querySelector(".pco-native-table-tools");
    if (!tool) return false;

    var line = tool.querySelector(".pco-native-controls-line");
    if (!line || line.querySelector("[data-pco-analysis-report]")) return Boolean(line);

    var button = document.createElement("button");
    button.type = "button";
    button.className = "pco-native-button pco-native-report";
    button.setAttribute("data-pco-analysis-report", "1");
    button.textContent = "📊 Rapport";
    button.title = "Rapport d’analyse basé sur les données réelles de cette table";
    button.addEventListener("click", function (event) {
      event.preventDefault();
      openReport();
    });
    line.appendChild(button);
    return true;
  }

  function boot() {
    if (installButton()) return;
    var tries = 0;
    var timer = window.setInterval(function () {
      tries += 1;
      if (installButton() || tries >= 20) window.clearInterval(timer);
    }, 100);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
