/*
 * PinCabOS-File created by Karots Sugarpie
 * VPX Ball / Cabinet clean grid editor v4
 *
 * Dependencies / requisites:
 * - /tools/vpx-ball-cabinet
 * - /tools/vpx-ball-cabinet/images.json
 * - /tools/vpx-ball-cabinet/image?path=...
 *
 * Created by Karots Sugarpie
 */

(function () {
  "use strict";

  const IMAGE_KEYS = new Set(["BallImage", "DecalImage", "Image", "SphereMap"]);

  const ESSENTIAL_KEYS = new Set([
    "OverwriteBallImage",
    "BallImage",
    "DecalImage",
    "Image",
    "SphereMap",
    "BallTrail",
    "BallTrailStrength",
    "CabinetAutofitMode",
    "CabinetAutofitPos",
    "BallAntiStretch"
  ]);

  const BOOL_KEYS = new Set([
    "OverwriteBallImage",
    "BallAntiStretch",
    "DisableLightingForBalls",
    "BallTrail",
    "TouchOverlay",
    "ForceReflection",
    "ReflectionEnabled"
  ]);

  const NUMBER_KEYS = new Set(["BallTrailStrength", "BulbIntensityScale", "PFReflStrength"]);

  const DESCRIPTIONS = {
    CabinetAutofitMode: "Ajuste automatiquement la bille en mode cabinet selon le rendu VPX.",
    CabinetAutofitPos: "Position ou ajustement utilisé par le mode Cabinet Autofit.",
    BallAntiStretch: "Évite que la bille semble étirée ou déformée sur un playfield cabinet.",
    DisableLightingForBalls: "Désactive certains effets de lumière appliqués aux billes.",
    BallTrail: "Active ou désactive la traînée visuelle derrière la bille.",
    BallTrailStrength: "Intensité de la traînée. Plus haut = effet plus visible.",
    OverwriteBallImage: "Force VPX à utiliser l’image personnalisée de bille.",
    BallImage: "Image personnalisée de bille utilisée dans la section Player.",
    DecalImage: "Image de décalque appliquée sur la bille.",
    TouchOverlay: "Overlay tactile VPX. Normalement inutile sur un pincab.",
    ForceReflection: "Force les réflexions de la bille.",
    DecalMode: "Mode de rendu du décalque de bille.",
    Image: "Image de bille par défaut dans DefaultProps\\Ball.",
    BulbIntensityScale: "Échelle d’intensité lumineuse de la bille.",
    PFReflStrength: "Force de réflexion du playfield sur la bille.",
    Color: "Couleur de bille, si utilisée par VPX.",
    SphereMap: "Texture sphere map utilisée pour les reflets de la bille.",
    ReflectionEnabled: "Active ou désactive les réflexions."
  };

  const SELECT_OPTIONS = {
    bool: [
      ["", "vide / défaut"],
      ["0", "0 — Désactivé"],
      ["1", "1 — Activé"]
    ],
    BallTrailStrength: [
      ["", "vide / défaut"],
      ["0.25", "0.25 — très léger"],
      ["0.5", "0.5 — léger"],
      ["1", "1 — normal"],
      ["1.5", "1.5 — fort"],
      ["2", "2 — très fort"]
    ],
    CabinetAutofitMode: [
      ["", "vide / défaut"],
      ["0", "0"],
      ["1", "1"],
      ["2", "2"]
    ],
    CabinetAutofitPos: [
      ["", "vide / défaut"],
      ["0", "0"],
      ["1", "1"],
      ["2", "2"]
    ],
    DecalMode: [
      ["", "vide / défaut"],
      ["0", "0"],
      ["1", "1"],
      ["2", "2"]
    ]
  };

  function norm(value) {
    return String(value || "").replace(/\\/g, "/").toLowerCase().trim();
  }

  function filename(value) {
    const parts = norm(value).split("/");
    return parts[parts.length - 1] || "";
  }

  function findImage(images, value) {
    const needle = norm(value);
    const needleName = filename(value);
    if (!needle) return null;

    return images.find(function (img) {
      const name = norm(img.name);
      const rel = norm(img.rel);
      const path = norm(img.path);
      return needle === name || needle === rel || needle === path || needleName === name || rel.endsWith("/" + needle) || path.endsWith("/" + needle);
    }) || null;
  }

  function injectStyle() {
    if (document.getElementById("pco-vpxball-grid-v4-style")) return;

    const style = document.createElement("style");
    style.id = "pco-vpxball-grid-v4-style";
    style.textContent = `
      .pco-vpxball-original-table-hidden {
        display: none !important;
      }

      .pco-vpxball-toolbar {
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
        align-items: center;
        margin: 14px 0 16px 0;
        padding: 12px;
        border: 1px solid rgba(255,176,0,.24);
        border-radius: 14px;
        background: rgba(0,0,0,.22);
      }

      .pco-vpxball-toolbar input {
        min-width: 300px;
        max-width: 520px;
        padding: 9px 12px;
        border-radius: 10px;
      }

      .pco-vpxball-badge {
        color: #ffb000;
        font-weight: 700;
        border: 1px solid rgba(255,176,0,.30);
        border-radius: 999px;
        padding: 7px 11px;
        background: rgba(255,176,0,.07);
      }

      .pco-vpxball-grid {
        display: flex;
        flex-direction: column;
        gap: 0;
        border: 1px solid rgba(255,176,0,.18);
        border-radius: 14px;
        overflow: hidden;
        background: rgba(0,0,0,.16);
      }

      .pco-vpxball-grid-header,
      .pco-vpxball-row {
        display: grid;
        grid-template-columns: minmax(220px, 1.05fr) minmax(330px, 1.45fr) minmax(160px, .72fr) minmax(280px, 1.18fr);
        column-gap: 18px;
        align-items: stretch;
      }

      .pco-vpxball-grid-header {
        position: sticky;
        top: 0;
        z-index: 3;
        background: #271235;
        color: #ffb000;
        font-weight: 800;
        border-bottom: 1px solid rgba(255,176,0,.24);
      }

      .pco-vpxball-grid-header > div {
        padding: 11px 14px;
      }

      .pco-vpxball-section {
        padding: 10px 14px;
        color: #ffb000;
        font-size: 14px;
        font-weight: 800;
        background: rgba(255,136,0,.15);
        border-top: 1px solid rgba(255,176,0,.18);
        border-bottom: 1px solid rgba(255,176,0,.13);
      }

      .pco-vpxball-row {
        min-height: 68px;
        border-bottom: 1px solid rgba(255,176,0,.11);
      }

      .pco-vpxball-row:nth-of-type(odd) {
        background: rgba(255,255,255,.025);
      }

      .pco-vpxball-row:nth-of-type(even) {
        background: rgba(255,176,0,.04);
      }

      .pco-vpxball-row:hover {
        background: rgba(255,176,0,.105);
      }

      .pco-vpxball-cell {
        padding: 12px 14px;
        min-width: 0;
        display: flex;
        flex-direction: column;
        justify-content: center;
      }

      .pco-vpxball-option-title {
        font-size: 13px;
        font-weight: 800;
        color: #fff;
        line-height: 1.25;
      }

      .pco-vpxball-option-key {
        margin-top: 4px;
        color: #ccc;
        font-size: 11px;
        font-family: monospace;
        overflow-wrap: anywhere;
      }

      .pco-vpxball-value-cell input,
      .pco-vpxball-value-cell select {
        width: 100% !important;
        min-width: 0 !important;
        max-width: none !important;
        padding: 8px 10px !important;
        border-radius: 8px;
      }

      .pco-vpxball-current {
        display: inline-block;
        width: fit-content;
        max-width: 100%;
        padding: 5px 9px;
        border-radius: 8px;
        border: 1px solid rgba(255,176,0,.16);
        background: rgba(0,0,0,.30);
        color: #e8e8e8;
        font-family: monospace;
        font-size: 12px;
        overflow-wrap: anywhere;
      }

      .pco-vpxball-desc {
        color: #d9d9d9;
        font-size: 12px;
        line-height: 1.38;
      }

      .pco-vpxball-tag {
        display: inline-block;
        width: fit-content;
        margin-top: 7px;
        color: #ffb000;
        font-size: 11px;
        border: 1px solid rgba(255,176,0,.24);
        border-radius: 999px;
        padding: 2px 8px;
        background: rgba(0,0,0,.18);
      }

      .pco-vpxball-image-line {
        display: grid;
        grid-template-columns: minmax(210px, 1fr) 126px 54px;
        gap: 12px;
        align-items: center;
        width: 100%;
      }

      .pco-vpxball-image-line input {
        width: 100% !important;
      }

      .pco-vpxball-image-line button {
        width: 126px;
        justify-content: center;
        white-space: nowrap;
      }

      .pco-vpxball-thumb {
        width: 52px;
        height: 52px;
        border: 1px solid rgba(255,176,0,.28);
        border-radius: 9px;
        background: rgba(0,0,0,.35);
        display: flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
      }

      .pco-vpxball-thumb img {
        max-width: 50px;
        max-height: 50px;
        object-fit: contain;
      }

      .pco-vpxball-thumb span {
        color: #999;
        font-size: 10px;
        text-align: center;
      }

      .pco-vpxball-browser {
        display: none;
        grid-column: 1 / -1;
        margin-top: 9px;
        padding: 10px;
        border: 1px solid rgba(255,176,0,.22);
        border-radius: 12px;
        background: rgba(0,0,0,.24);
      }

      .pco-vpxball-browser select {
        width: 100% !important;
      }

      .pco-vpxball-muted {
        color: #aaa;
        font-size: 11px;
        margin-top: 6px;
      }

      .pco-vpxball-hidden {
        display: none !important;
      }

      @media (max-width: 1200px) {
        .pco-vpxball-grid-header,
        .pco-vpxball-row {
          grid-template-columns: minmax(180px, 1fr) minmax(300px, 1.35fr) minmax(140px, .7fr) minmax(230px, 1fr);
          column-gap: 12px;
        }
      }

      @media (max-width: 850px) {
        .pco-vpxball-grid-header {
          display: none;
        }

        .pco-vpxball-row {
          grid-template-columns: 1fr;
          row-gap: 0;
          padding: 8px 0;
        }

        .pco-vpxball-cell {
          padding: 8px 12px;
        }

        .pco-vpxball-cell::before {
          content: attr(data-label);
          color: #ffb000;
          font-size: 11px;
          font-weight: 800;
          margin-bottom: 4px;
        }

        .pco-vpxball-image-line {
          grid-template-columns: 1fr;
        }

        .pco-vpxball-image-line button {
          width: 100%;
        }
      }
    `;
    document.head.appendChild(style);
  }

  function rowKey(row) {
    const code = row.querySelector("td:first-child code");
    return code ? code.textContent.trim() : "";
  }

  function rowLabel(row) {
    const strong = row.querySelector("td:first-child strong");
    return strong ? strong.textContent.trim() : "";
  }

  function rowCurrent(row) {
    const code = row.querySelector("td:nth-child(3) code");
    return code ? code.textContent.trim() : "vide";
  }

  function tagForKey(key) {
    if (IMAGE_KEYS.has(key)) return "image";
    if (BOOL_KEYS.has(key)) return "0 / 1";
    if (NUMBER_KEYS.has(key)) return "nombre";
    return "VPX";
  }

  function descriptionForKey(key) {
    return DESCRIPTIONS[key] || "Option VPX avancée. Laisser vide conserve le comportement par défaut.";
  }

  function buildSelectFromInput(input, key) {
    let options = null;
    if (BOOL_KEYS.has(key)) options = SELECT_OPTIONS.bool;
    else if (SELECT_OPTIONS[key]) options = SELECT_OPTIONS[key];

    if (!options) return input;

    const current = String(input.value || "").trim();
    const select = document.createElement("select");
    select.name = input.name;

    options.forEach(function (pair) {
      const opt = document.createElement("option");
      opt.value = pair[0];
      opt.textContent = pair[1];
      if (current === pair[0]) opt.selected = true;
      select.appendChild(opt);
    });

    if (current && !options.some(function (pair) { return pair[0] === current; })) {
      const opt = document.createElement("option");
      opt.value = current;
      opt.textContent = current + " — valeur actuelle";
      opt.selected = true;
      select.appendChild(opt);
    }

    input.remove();
    return select;
  }

  function makeThumb(img, emptyText) {
    const box = document.createElement("div");
    box.className = "pco-vpxball-thumb";

    if (img && img.url) {
      const image = document.createElement("img");
      image.src = img.url + "&v=" + Date.now();
      image.alt = img.name || "preview";
      box.appendChild(image);
    } else {
      const span = document.createElement("span");
      span.textContent = emptyText || "aucun";
      box.appendChild(span);
    }

    return box;
  }

  function buildImageControl(input, key, images, index) {
    const currentImg = findImage(images, input.value);
    const fieldId = "pco-vpxball-grid-" + index + "-" + key.replace(/[^A-Za-z0-9_-]/g, "-");

    const wrap = document.createElement("div");
    wrap.className = "pco-vpxball-image-line";

    input.placeholder = "nom image VPX";
    wrap.appendChild(input);

    const button = document.createElement("button");
    button.type = "button";
    button.className = "button secondary";
    button.textContent = "Parcourir";
    wrap.appendChild(button);

    const thumb = makeThumb(currentImg, "aucun");
    wrap.appendChild(thumb);

    const browser = document.createElement("div");
    browser.className = "pco-vpxball-browser";
    browser.id = fieldId + "-browser";

    const select = document.createElement("select");

    const empty = document.createElement("option");
    empty.value = "";
    empty.dataset.url = "";
    empty.textContent = "— choisir une image —";
    select.appendChild(empty);

    images.forEach(function (img) {
      const opt = document.createElement("option");
      opt.value = img.name || "";
      opt.dataset.url = img.url || "";
      opt.textContent = img.name === img.rel ? img.name : img.name + " — " + img.rel;

      const current = norm(input.value);
      if (current && [norm(img.name), norm(img.rel), norm(img.path)].includes(current)) {
        opt.selected = true;
      }

      select.appendChild(opt);
    });

    const hint = document.createElement("div");
    hint.className = "pco-vpxball-muted";
    hint.textContent = "Choisir remplace la valeur par le nom de fichier VPX.";

    browser.appendChild(select);
    browser.appendChild(hint);
    wrap.appendChild(browser);

    button.addEventListener("click", function () {
      browser.style.display = browser.style.display === "block" ? "none" : "block";
    });

    select.addEventListener("change", function () {
      const opt = select.options[select.selectedIndex];
      const value = opt ? opt.value : "";
      const url = opt ? opt.dataset.url : "";

      input.value = value;
      thumb.innerHTML = "";

      if (url) {
        const img = document.createElement("img");
        img.src = url + "&v=" + Date.now();
        thumb.appendChild(img);
      } else {
        const span = document.createElement("span");
        span.textContent = "aucun";
        thumb.appendChild(span);
      }
    });

    return wrap;
  }

  function makeCell(label, className) {
    const cell = document.createElement("div");
    cell.className = "pco-vpxball-cell " + (className || "");
    cell.dataset.label = label;
    return cell;
  }

  function buildDataRow(sourceRow, images, index) {
    const key = rowKey(sourceRow);
    const label = rowLabel(sourceRow);
    if (!key) return null;

    const input = sourceRow.querySelector("td:nth-child(2) input");
    if (!input) return null;

    const row = document.createElement("div");
    row.className = "pco-vpxball-row";
    row.dataset.key = key;
    row.dataset.essential = ESSENTIAL_KEYS.has(key) ? "1" : "0";

    const optionCell = makeCell("Option", "");
    const title = document.createElement("div");
    title.className = "pco-vpxball-option-title";
    title.textContent = label || key;

    const keyEl = document.createElement("div");
    keyEl.className = "pco-vpxball-option-key";
    keyEl.textContent = key;

    optionCell.appendChild(title);
    optionCell.appendChild(keyEl);

    const valueCell = makeCell("Nouvelle valeur", "pco-vpxball-value-cell");

    if (IMAGE_KEYS.has(key)) {
      valueCell.appendChild(buildImageControl(input, key, images, index));
    } else {
      valueCell.appendChild(buildSelectFromInput(input, key));
    }

    const currentCell = makeCell("Valeur actuelle", "");
    const current = document.createElement("div");
    current.className = "pco-vpxball-current";
    current.textContent = rowCurrent(sourceRow);
    currentCell.appendChild(current);

    const descCell = makeCell("Description", "");
    const desc = document.createElement("div");
    desc.className = "pco-vpxball-desc";
    desc.textContent = descriptionForKey(key);

    const tag = document.createElement("div");
    tag.className = "pco-vpxball-tag";
    tag.textContent = tagForKey(key);

    descCell.appendChild(desc);
    descCell.appendChild(tag);

    row.appendChild(optionCell);
    row.appendChild(valueCell);
    row.appendChild(currentCell);
    row.appendChild(descCell);

    return row;
  }

  function addToolbar(container, images) {
    const toolbar = document.createElement("div");
    toolbar.className = "pco-vpxball-toolbar";

    const search = document.createElement("input");
    search.type = "search";
    search.placeholder = "Filtrer option, clé ou description...";
    toolbar.appendChild(search);

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "button secondary";
    toggle.textContent = "Afficher avancé";
    toolbar.appendChild(toggle);

    const badge = document.createElement("span");
    badge.className = "pco-vpxball-badge";
    badge.textContent = "Images VPX : " + images.length;
    toolbar.appendChild(badge);

    container.parentNode.insertBefore(toolbar, container);

    let advancedShown = false;

    function refresh() {
      const q = search.value.trim().toLowerCase();

      Array.from(container.querySelectorAll(".pco-vpxball-row")).forEach(function (row) {
        const advancedHidden = row.dataset.essential !== "1" && !advancedShown;
        const queryHidden = q && !row.textContent.toLowerCase().includes(q);
        row.classList.toggle("pco-vpxball-hidden", advancedHidden || queryHidden);
      });

      Array.from(container.querySelectorAll(".pco-vpxball-section")).forEach(function (section) {
        let next = section.nextElementSibling;
        let visible = false;

        while (next && !next.classList.contains("pco-vpxball-section")) {
          if (!next.classList.contains("pco-vpxball-hidden")) {
            visible = true;
            break;
          }
          next = next.nextElementSibling;
        }

        section.classList.toggle("pco-vpxball-hidden", !visible);
      });
    }

    toggle.addEventListener("click", function () {
      advancedShown = !advancedShown;
      toggle.textContent = advancedShown ? "Masquer avancé" : "Afficher avancé";
      refresh();
    });

    search.addEventListener("input", refresh);
    refresh();
  }

  async function init() {
    const title = document.querySelector("h2");
    if (!title || title.textContent.trim() !== "VPX Ball / Cabinet") return;

    injectStyle();

    const form = document.querySelector('form[action="/tools/vpx-ball-cabinet/apply"]');
    if (!form) return;

    const table = form.querySelector("table");
    if (!table || table.dataset.pcoGridDone === "1") return;
    table.dataset.pcoGridDone = "1";

    let payload = { images: [] };
    try {
      const res = await fetch("/tools/vpx-ball-cabinet/images.json", { cache: "no-store" });
      payload = await res.json();
    } catch (err) {
      console.warn("PinCabOS VPX Ball/Cabinet: images.json unavailable", err);
    }

    const images = payload && payload.images ? payload.images : [];

    const grid = document.createElement("div");
    grid.className = "pco-vpxball-grid";

    const header = document.createElement("div");
    header.className = "pco-vpxball-grid-header";
    ["Option", "Nouvelle valeur", "Valeur actuelle", "Description"].forEach(function (txt) {
      const h = document.createElement("div");
      h.textContent = txt;
      header.appendChild(h);
    });
    grid.appendChild(header);

    Array.from(table.querySelectorAll("tr")).forEach(function (tr, index) {
      const th = tr.querySelector("th");
      if (th) {
        const section = document.createElement("div");
        section.className = "pco-vpxball-section";
        section.textContent = th.textContent.trim();
        grid.appendChild(section);
        return;
      }

      const row = buildDataRow(tr, images, index);
      if (row) grid.appendChild(row);
    });

    table.parentNode.insertBefore(grid, table);
    table.classList.add("pco-vpxball-original-table-hidden");

    addToolbar(grid, images);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
