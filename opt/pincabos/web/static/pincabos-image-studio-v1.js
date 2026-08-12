/* PINCABOS_IMAGE_STUDIO_V1 */
(() => {
  "use strict";

  const qs = (root, sel) => root.querySelector(sel);
  const qsa = (root, sel) => Array.from(root.querySelectorAll(sel));

  function initStudio(root) {
    const canvas = qs(root, "canvas[data-pcx-img-canvas]");
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    const status = qs(root, "[data-pcx-img-status]");
    const fileUrl = root.dataset.fileUrl;
    const saveUrl = root.dataset.saveUrl;
    const rootName = root.dataset.rootName;
    const relPath = root.dataset.relPath;

    let zoom = 1;
    let drawing = false;
    let start = null;
    let snapshot = null;
    let cropRect = null;
    let history = [];
    let historyIndex = -1;
    let loaded = false;

    const setStatus = (msg, good = false) => {
      status.textContent = msg;
      status.style.color = good ? "#86ffc5" : "#ffdca4";
    };

    const tool = () => qs(root, "[data-pcx-img-tool]").value;
    const color = () => qs(root, "[data-pcx-img-color]").value || "#ffffff";
    const size = () => Math.max(1, parseInt(qs(root, "[data-pcx-img-size]").value || "8", 10));
    const textValue = () => qs(root, "[data-pcx-img-text]").value || "PinCabOS";
    const textSize = () => Math.max(6, parseInt(qs(root, "[data-pcx-img-text-size]").value || "48", 10));

    function updateMeta() {
      qs(root, "[data-pcx-img-dim]").textContent = canvas.width + " × " + canvas.height;
      qs(root, "[data-pcx-img-zoom]").textContent = Math.round(zoom * 100) + "%";
      canvas.style.width = Math.max(1, Math.round(canvas.width * zoom)) + "px";
      canvas.style.height = Math.max(1, Math.round(canvas.height * zoom)) + "px";
    }

    function pointFromEvent(ev) {
      const rect = canvas.getBoundingClientRect();
      return {
        x: Math.max(0, Math.min(canvas.width, (ev.clientX - rect.left) * canvas.width / rect.width)),
        y: Math.max(0, Math.min(canvas.height, (ev.clientY - rect.top) * canvas.height / rect.height))
      };
    }

    function pushHistory() {
      if (!loaded) return;
      history = history.slice(0, historyIndex + 1);
      try {
        history.push(canvas.toDataURL("image/png"));
        if (history.length > 28) history.shift();
        historyIndex = history.length - 1;
      } catch (e) {
        console.warn("Image Studio history error", e);
      }
    }

    function restoreHistory(index) {
      if (index < 0 || index >= history.length) return;
      const img = new Image();
      img.onload = () => {
        canvas.width = img.naturalWidth;
        canvas.height = img.naturalHeight;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0);
        historyIndex = index;
        cropRect = null;
        updateMeta();
        setStatus("Historique restauré.");
      };
      img.src = history[index];
    }

    function loadImage() {
      const img = new Image();
      img.onload = () => {
        canvas.width = img.naturalWidth || img.width;
        canvas.height = img.naturalHeight || img.height;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0);
        loaded = true;
        history = [];
        historyIndex = -1;
        pushHistory();
        updateMeta();
        setStatus("Image chargée. Prêt.", true);
      };
      img.onerror = () => setStatus("Erreur: impossible de charger l’image.");
      img.src = fileUrl + (fileUrl.includes("?") ? "&" : "?") + "v=" + Date.now();
    }

    function restoreSnapshot() {
      if (snapshot) ctx.putImageData(snapshot, 0, 0);
    }

    function drawPreviewRect(p, mode) {
      restoreSnapshot();
      const x = Math.min(start.x, p.x), y = Math.min(start.y, p.y);
      const w = Math.abs(p.x - start.x), h = Math.abs(p.y - start.y);
      ctx.save();
      ctx.lineWidth = Math.max(1, size());
      ctx.strokeStyle = mode === "crop" ? "#ffbd00" : color();
      ctx.fillStyle = color();
      if (mode === "crop") {
        ctx.setLineDash([10, 8]);
        ctx.strokeRect(x, y, w, h);
        cropRect = { x: Math.round(x), y: Math.round(y), w: Math.round(w), h: Math.round(h) };
      } else if (mode === "rect") {
        ctx.strokeRect(x, y, w, h);
      } else if (mode === "ellipse") {
        ctx.beginPath();
        ctx.ellipse(x + w / 2, y + h / 2, w / 2, h / 2, 0, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.restore();
    }

    function drawPreviewLine(p) {
      restoreSnapshot();
      ctx.save();
      ctx.lineWidth = Math.max(1, size());
      ctx.strokeStyle = color();
      ctx.lineCap = "round";
      ctx.beginPath();
      ctx.moveTo(start.x, start.y);
      ctx.lineTo(p.x, p.y);
      ctx.stroke();
      ctx.restore();
    }

    function drawTextAt(p) {
      ctx.save();
      ctx.fillStyle = color();
      ctx.font = `bold ${textSize()}px system-ui, Arial, sans-serif`;
      ctx.textBaseline = "top";
      ctx.lineJoin = "round";
      ctx.miterLimit = 2;
      ctx.fillText(textValue(), p.x, p.y);
      ctx.restore();
      pushHistory();
      setStatus("Texte ajouté.", true);
    }

    function beginDraw(ev) {
      if (!loaded) return;
      const p = pointFromEvent(ev);
      const t = tool();

      if (t === "text") {
        drawTextAt(p);
        return;
      }

      drawing = true;
      start = p;
      snapshot = ctx.getImageData(0, 0, canvas.width, canvas.height);

      if (t === "brush" || t === "eraser") {
        ctx.save();
        ctx.lineWidth = size();
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
        if (t === "eraser") {
          ctx.globalCompositeOperation = "destination-out";
          ctx.strokeStyle = "rgba(0,0,0,1)";
        } else {
          ctx.globalCompositeOperation = "source-over";
          ctx.strokeStyle = color();
        }
        ctx.beginPath();
        ctx.moveTo(p.x, p.y);
      }
    }

    function moveDraw(ev) {
      if (!drawing || !loaded) return;
      const p = pointFromEvent(ev);
      const t = tool();

      if (t === "brush" || t === "eraser") {
        ctx.lineTo(p.x, p.y);
        ctx.stroke();
      } else if (t === "line") {
        drawPreviewLine(p);
      } else if (t === "rect" || t === "ellipse" || t === "crop") {
        drawPreviewRect(p, t);
      }
    }

    function endDraw() {
      if (!drawing) return;
      const t = tool();
      if (t === "brush" || t === "eraser") ctx.restore();
      drawing = false;
      snapshot = null;
      if (t !== "crop") pushHistory();
      setStatus(t === "crop" ? "Sélection crop prête. Clique Appliquer crop." : "Modification ajoutée.", true);
    }

    function applyCrop() {
      if (!cropRect || cropRect.w < 2 || cropRect.h < 2) {
        setStatus("Aucune sélection crop valide.");
        return;
      }
      const tmp = document.createElement("canvas");
      tmp.width = cropRect.w;
      tmp.height = cropRect.h;
      tmp.getContext("2d").drawImage(canvas, cropRect.x, cropRect.y, cropRect.w, cropRect.h, 0, 0, cropRect.w, cropRect.h);
      canvas.width = tmp.width;
      canvas.height = tmp.height;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(tmp, 0, 0);
      cropRect = null;
      pushHistory();
      updateMeta();
      setStatus("Crop appliqué.", true);
    }

    function rotate(dir) {
      const tmp = document.createElement("canvas");
      tmp.width = canvas.height;
      tmp.height = canvas.width;
      const tctx = tmp.getContext("2d");
      if (dir === "left") {
        tctx.translate(0, tmp.height);
        tctx.rotate(-Math.PI / 2);
      } else {
        tctx.translate(tmp.width, 0);
        tctx.rotate(Math.PI / 2);
      }
      tctx.drawImage(canvas, 0, 0);
      canvas.width = tmp.width;
      canvas.height = tmp.height;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(tmp, 0, 0);
      pushHistory();
      updateMeta();
      setStatus("Rotation appliquée.", true);
    }

    function flip(horizontal) {
      const tmp = document.createElement("canvas");
      tmp.width = canvas.width;
      tmp.height = canvas.height;
      const tctx = tmp.getContext("2d");
      if (horizontal) {
        tctx.translate(tmp.width, 0);
        tctx.scale(-1, 1);
      } else {
        tctx.translate(0, tmp.height);
        tctx.scale(1, -1);
      }
      tctx.drawImage(canvas, 0, 0);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(tmp, 0, 0);
      pushHistory();
      setStatus("Flip appliqué.", true);
    }

    function resizeCanvas() {
      const w = Math.max(1, parseInt(qs(root, "[data-pcx-img-width]").value || canvas.width, 10));
      const h = Math.max(1, parseInt(qs(root, "[data-pcx-img-height]").value || canvas.height, 10));
      const tmp = document.createElement("canvas");
      tmp.width = w;
      tmp.height = h;
      tmp.getContext("2d").drawImage(canvas, 0, 0, w, h);
      canvas.width = w;
      canvas.height = h;
      ctx.clearRect(0, 0, w, h);
      ctx.drawImage(tmp, 0, 0);
      pushHistory();
      updateMeta();
      setStatus("Image redimensionnée.", true);
    }

    function mimeForName(name) {
      const lower = (name || relPath || "").toLowerCase();
      if (lower.endsWith(".jpg") || lower.endsWith(".jpeg")) return "image/jpeg";
      if (lower.endsWith(".webp")) return "image/webp";
      return "image/png";
    }

    async function saveImage(asCopy) {
      const newName = asCopy ? (qs(root, "[data-pcx-img-new-name]").value || "").trim() : "";
      if (asCopy && !newName) {
        setStatus("Entre un nouveau nom pour Sauver sous.");
        qs(root, "[data-pcx-img-new-name]").focus();
        return;
      }
      const mime = mimeForName(newName || relPath);
      const quality = mime === "image/png" ? undefined : 0.94;
      setStatus("Encodage image…");

      canvas.toBlob(async (blob) => {
        if (!blob) {
          setStatus("Erreur: encodage impossible.");
          return;
        }
        const reader = new FileReader();
        reader.onload = async () => {
          try {
            setStatus("Sauvegarde serveur…");
            const response = await fetch(saveUrl, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                root: rootName,
                path: relPath,
                new_name: newName,
                image_data: reader.result
              })
            });
            const data = await response.json();
            if (!response.ok || !data.ok) throw new Error(data.error || "Sauvegarde impossible.");
            setStatus("Sauvegardé: " + (data.saved || "OK") + (data.backup ? " · backup: " + data.backup : ""), true);
          } catch (err) {
            setStatus("Erreur sauvegarde: " + (err.message || String(err)));
          }
        };
        reader.readAsDataURL(blob);
      }, mime, quality);
    }

    canvas.addEventListener("pointerdown", (e) => { e.preventDefault(); canvas.setPointerCapture(e.pointerId); beginDraw(e); });
    canvas.addEventListener("pointermove", (e) => { e.preventDefault(); moveDraw(e); });
    canvas.addEventListener("pointerup", (e) => { e.preventDefault(); endDraw(); });
    canvas.addEventListener("pointercancel", endDraw);

    qsa(root, "[data-pcx-action]").forEach(btn => {
      btn.addEventListener("click", () => {
        const a = btn.dataset.pcxAction;
        if (a === "undo") restoreHistory(historyIndex - 1);
        if (a === "redo") restoreHistory(historyIndex + 1);
        if (a === "reset") loadImage();
        if (a === "zoom-in") { zoom = Math.min(6, zoom + 0.1); updateMeta(); }
        if (a === "zoom-out") { zoom = Math.max(0.05, zoom - 0.1); updateMeta(); }
        if (a === "zoom-fit") { zoom = Math.min(1, Math.max(0.05, (root.clientWidth - 48) / Math.max(1, canvas.width))); updateMeta(); }
        if (a === "rotate-left") rotate("left");
        if (a === "rotate-right") rotate("right");
        if (a === "flip-h") flip(true);
        if (a === "flip-v") flip(false);
        if (a === "resize") resizeCanvas();
        if (a === "crop") applyCrop();
        if (a === "save") saveImage(false);
        if (a === "save-copy") saveImage(true);
      });
    });

    qs(root, "[data-pcx-img-use-current]").addEventListener("click", () => {
      qs(root, "[data-pcx-img-width]").value = canvas.width;
      qs(root, "[data-pcx-img-height]").value = canvas.height;
      setStatus("Dimensions copiées dans Resize.");
    });

    document.addEventListener("keydown", (e) => {
      if (!root.isConnected) return;
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
        e.preventDefault();
        restoreHistory(e.shiftKey ? historyIndex + 1 : historyIndex - 1);
      }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        saveImage(false);
      }
    });

    loadImage();
  }

  document.addEventListener("DOMContentLoaded", () => {
    qsa(document, "[data-pcx-image-studio='1']").forEach(initStudio);
  });
})();

/* PINCABOS_IMAGE_STUDIO_V12_FLOATING */
(() => {
  "use strict";

  function ready(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  ready(() => {
    window.setTimeout(() => {
      document.querySelectorAll('[data-pcx-image-studio="1"]').forEach((studio) => {
        if (studio.dataset.pcxImageStudioFloatingReady === "1") return;
        studio.dataset.pcxImageStudioFloatingReady = "1";

        studio.classList.add("pcx-imgstudio-modal");

        const launcher = document.createElement("button");
        launcher.type = "button";
        launcher.className = "pcx-imgstudio-launcher";
        launcher.textContent = "🎨 Modifier l’image";

        const close = document.createElement("button");
        close.type = "button";
        close.className = "pcx-imgstudio-close";
        close.textContent = "×";

        function openStudio() {
          studio.classList.add("is-open");
          document.body.classList.add("pcx-imgstudio-open");
          launcher.style.display = "none";
        }

        function closeStudio() {
          studio.classList.remove("is-open");
          document.body.classList.remove("pcx-imgstudio-open");
          launcher.style.display = "";
        }

        launcher.addEventListener("click", openStudio);
        close.addEventListener("click", closeStudio);

        document.addEventListener("keydown", (event) => {
          if (event.key === "Escape" && studio.classList.contains("is-open")) {
            closeStudio();
          }
        });

        studio.prepend(close);
        document.body.appendChild(studio);
        document.body.appendChild(launcher);
      });
    }, 150);
  });
})();

/* PINCABOS_IMAGE_STUDIO_V13_INLINE */
(() => {
  "use strict";

  function ready(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  function forceInline() {
    const studio = document.querySelector('[data-pcx-image-studio="1"]');
    if (!studio) return;

    document.body.classList.remove("pcx-imgstudio-open");

    document.querySelectorAll(".pcx-imgstudio-launcher, .pcx-imgstudio-close").forEach((el) => el.remove());

    studio.classList.remove("pcx-imgstudio-modal", "is-open");
    studio.style.display = "";
    studio.style.position = "";
    studio.style.left = "";
    studio.style.right = "";
    studio.style.top = "";
    studio.style.bottom = "";
    studio.style.width = "";
    studio.style.height = "";
    studio.style.margin = "";

    const img =
      document.querySelector('img[src*="/tools/commander/live/file"]') ||
      Array.from(document.images).find((image) => {
        const src = image.getAttribute("src") || "";
        return src.includes("/tools/commander/live/file");
      });

    let anchor = null;

    if (img) {
      anchor =
        img.closest(".card") ||
        img.closest("section") ||
        img.closest("div") ||
        img.parentElement;
    }

    if (!anchor) {
      const code = Array.from(document.querySelectorAll("code, pre")).find((el) =>
        (el.textContent || "").includes("/home/pinball/Tables")
      );
      anchor = code ? (code.closest(".card") || code.parentElement) : null;
    }

    if (anchor && anchor.parentElement && studio.previousElementSibling !== anchor) {
      anchor.insertAdjacentElement("afterend", studio);
    }

    const h2 = studio.querySelector("h2");
    if (h2) h2.textContent = "🎨 PinCabOS Image Studio — outils image";

    const status = studio.querySelector("[data-pcx-img-status]");
    if (status && !status.dataset.v13Touched) {
      status.dataset.v13Touched = "1";
      status.textContent = "Outils image chargés directement dans la page.";
    }
  }

  ready(() => {
    forceInline();
    setTimeout(forceInline, 200);
    setTimeout(forceInline, 700);
  });
})();

/* PINCABOS_IMAGE_STUDIO_V14_HEADER_ACTIONS */
(() => {
  "use strict";

  function ready(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  function textOf(el) {
    return (el && el.textContent ? el.textContent : "").replace(/\s+/g, " ").trim();
  }

  function basename(path) {
    const clean = (path || "").split("?")[0].split("#")[0];
    const parts = clean.split("/").filter(Boolean);
    return parts.length ? parts[parts.length - 1] : clean;
  }

  function findLegacyHeader() {
    const back = Array.from(document.querySelectorAll('a.button, a'))
      .find(a => /Retour Explorer/i.test(textOf(a)));
    const download = Array.from(document.querySelectorAll('a.button, a'))
      .find(a => /Télécharger/i.test(textOf(a)));

    if (!back || !download) return null;

    const candidates = [];
    let node = back.parentElement;
    while (node) {
      candidates.push(node);
      node = node.parentElement;
    }

    for (const el of candidates) {
      const txt = textOf(el);
      const hasBack = el.contains(back);
      const hasDownload = el.contains(download);
      const looksLikeView = /Vue\s*:/.test(txt) || /\/home\/pinball\//.test(txt);
      if (hasBack && hasDownload && looksLikeView) {
        return el;
      }
    }

    return back.parentElement || null;
  }

  function cloneButton(button) {
    const clone = button.cloneNode(true);
    clone.removeAttribute("id");
    clone.removeAttribute("onclick");
    clone.style.display = "";
    return clone;
  }

  function installHeaderActions() {
    const studio = document.querySelector('[data-pcx-image-studio="1"]');
    if (!studio) return;
    if (studio.dataset.pcxHeaderActionsReady === "1") return;
    studio.dataset.pcxHeaderActionsReady = "1";

    const head = studio.querySelector(".pcx-imgstudio-head");
    if (!head) return;

    const h2 = head.querySelector("h2");
    const desc = head.querySelector("p");
    const status = head.querySelector("[data-pcx-img-status]");

    const currentPath =
      studio.dataset.relPath ||
      textOf(document.querySelector(".pcx-imgstudio-meta code")) ||
      "";

    const fileName = basename(currentPath);

    if (h2) {
      h2.textContent = "🎨 Image Studio — " + fileName;
    }

    let main = head.querySelector(".pcx-imgstudio-head-main");
    if (!main) {
      main = document.createElement("div");
      main.className = "pcx-imgstudio-head-main";

      if (h2) main.appendChild(h2);
      if (desc) {
        desc.textContent = "Édition directe de l’image avec outils intégrés PinCabOS.";
        main.appendChild(desc);
      }
      if (status) main.appendChild(status);

      head.prepend(main);
    }

    let actions = head.querySelector(".pcx-imgstudio-head-actions");
    if (!actions) {
      actions = document.createElement("div");
      actions.className = "pcx-imgstudio-head-actions";
      head.appendChild(actions);
    }

    const back = Array.from(document.querySelectorAll('a.button, a'))
      .find(a => /Retour Explorer/i.test(textOf(a)));
    const download = Array.from(document.querySelectorAll('a.button, a'))
      .find(a => /Télécharger/i.test(textOf(a)));

    if (back && !actions.querySelector('[data-pcx-action-origin="back"]')) {
      const backClone = cloneButton(back);
      backClone.dataset.pcxActionOrigin = "back";
      actions.appendChild(backClone);
    }

    if (download && !actions.querySelector('[data-pcx-action-origin="download"]')) {
      const downClone = cloneButton(download);
      downClone.dataset.pcxActionOrigin = "download";
      actions.appendChild(downClone);
    }

    const legacy = findLegacyHeader();
    if (legacy) {
      legacy.classList.add("pcx-imgstudio-legacy-hidden");
    }
  }

  ready(() => {
    setTimeout(installHeaderActions, 150);
    setTimeout(installHeaderActions, 700);
    setTimeout(installHeaderActions, 1400);
  });
})();

/* PINCABOS_IMAGE_STUDIO_V15_MAGIC_WAND */
(() => {
  "use strict";

  function ready(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  function qs(root, sel) {
    return root.querySelector(sel);
  }

  function qsa(root, sel) {
    return Array.from(root.querySelectorAll(sel));
  }

  function setStatus(studio, msg, good) {
    const status = qs(studio, "[data-pcx-img-status]");
    if (status) {
      status.textContent = msg;
      status.style.color = good ? "#86ffc5" : "#ffdca4";
    }
  }

  function pointFromEvent(canvas, ev) {
    const rect = canvas.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(canvas.width - 1, Math.floor((ev.clientX - rect.left) * canvas.width / rect.width))),
      y: Math.max(0, Math.min(canvas.height - 1, Math.floor((ev.clientY - rect.top) * canvas.height / rect.height)))
    };
  }

  function toleranceOf(studio) {
    const input = qs(studio, "[data-pcx-magic-tolerance]");
    return Math.max(0, Math.min(255, parseInt((input && input.value) || "38", 10)));
  }

  function alphaCutOf(studio) {
    const input = qs(studio, "[data-pcx-magic-alpha]");
    return Math.max(0, Math.min(255, parseInt((input && input.value) || "18", 10)));
  }

  function colorDistanceOk(data, idx, base, tolerance, alphaCut) {
    const a = data[idx + 3];
    if (a <= alphaCut) return true;

    const dr = data[idx] - base[0];
    const dg = data[idx + 1] - base[1];
    const db = data[idx + 2] - base[2];
    const da = data[idx + 3] - base[3];

    // Distance perceptuelle simple, un peu plus sensible au vert.
    const dist = Math.sqrt((dr * dr * 0.30) + (dg * dg * 0.59) + (db * db * 0.11) + (da * da * 0.08));
    return dist <= tolerance;
  }

  function pushNativeUndo(canvas) {
    // Le module V1 a son propre historique privé. On ne peut pas l'appeler directement.
    // On simule un petit trait invisible impossible, donc on garde plutôt un rollback local V1.5.
    try {
      canvas.dataset.pcxMagicLast = canvas.toDataURL("image/png");
    } catch (_) {}
  }

  function eraseFlood(studio, canvas, x, y) {
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    const width = canvas.width;
    const height = canvas.height;
    const img = ctx.getImageData(0, 0, width, height);
    const data = img.data;
    const startIdx = (y * width + x) * 4;
    const base = [data[startIdx], data[startIdx + 1], data[startIdx + 2], data[startIdx + 3]];
    const tolerance = toleranceOf(studio);
    const alphaCut = alphaCutOf(studio);

    pushNativeUndo(canvas);

    const total = width * height;
    const seen = new Uint8Array(total);
    const stack = [y * width + x];
    let erased = 0;

    while (stack.length) {
      const p = stack.pop();
      if (seen[p]) continue;
      seen[p] = 1;

      const px = p % width;
      const py = Math.floor(p / width);
      const idx = p * 4;

      if (!colorDistanceOk(data, idx, base, tolerance, alphaCut)) continue;

      data[idx + 3] = 0;
      erased++;

      if (px > 0) stack.push(p - 1);
      if (px < width - 1) stack.push(p + 1);
      if (py > 0) stack.push(p - width);
      if (py < height - 1) stack.push(p + width);
    }

    ctx.putImageData(img, 0, 0);
    setStatus(studio, "Baguette magique: " + erased.toLocaleString("fr-CA") + " pixel(s) effacé(s).", true);
  }

  function eraseCorners(studio, canvas) {
    const corners = [
      [0, 0],
      [canvas.width - 1, 0],
      [0, canvas.height - 1],
      [canvas.width - 1, canvas.height - 1]
    ];

    pushNativeUndo(canvas);

    // Pour éviter que chaque coin écrase le rollback, on fait une version locale de flood sans status détaillé.
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    const width = canvas.width;
    const height = canvas.height;
    const img = ctx.getImageData(0, 0, width, height);
    const data = img.data;
    const tolerance = toleranceOf(studio);
    const alphaCut = alphaCutOf(studio);
    const seenGlobal = new Uint8Array(width * height);
    let erased = 0;

    for (const [cx, cy] of corners) {
      const start = cy * width + cx;
      const startIdx = start * 4;
      const base = [data[startIdx], data[startIdx + 1], data[startIdx + 2], data[startIdx + 3]];
      const stack = [start];

      while (stack.length) {
        const p = stack.pop();
        if (seenGlobal[p]) continue;
        seenGlobal[p] = 1;

        const px = p % width;
        const py = Math.floor(p / width);
        const idx = p * 4;

        if (!colorDistanceOk(data, idx, base, tolerance, alphaCut)) continue;

        if (data[idx + 3] !== 0) {
          data[idx + 3] = 0;
          erased++;
        }

        if (px > 0) stack.push(p - 1);
        if (px < width - 1) stack.push(p + 1);
        if (py > 0) stack.push(p - width);
        if (py < height - 1) stack.push(p + width);
      }
    }

    ctx.putImageData(img, 0, 0);
    setStatus(studio, "Effacer coins: " + erased.toLocaleString("fr-CA") + " pixel(s) de fond effacé(s).", true);
  }

  function restoreMagic(studio, canvas) {
    const last = canvas.dataset.pcxMagicLast;
    if (!last) {
      setStatus(studio, "Aucun rollback baguette disponible. Utilise Reset au besoin.");
      return;
    }

    const img = new Image();
    img.onload = () => {
      const ctx = canvas.getContext("2d", { willReadFrequently: true });
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0);

      const dim = qs(studio, "[data-pcx-img-dim]");
      if (dim) dim.textContent = canvas.width + " × " + canvas.height;

      setStatus(studio, "Rollback baguette restauré.", true);
    };
    img.src = last;
  }

  function addMagicUi(studio) {
    const select = qs(studio, "[data-pcx-img-tool]");
    if (select && !select.querySelector('option[value="magic-wand"]')) {
      const opt = document.createElement("option");
      opt.value = "magic-wand";
      opt.textContent = "🪄 Baguette magique";
      select.appendChild(opt);
    }

    const toolbar = qs(studio, ".pcx-imgstudio-toolbar");
    if (!toolbar || qs(studio, "[data-pcx-magic-group]")) return;

    const group = document.createElement("div");
    group.className = "pcx-imgstudio-group pcx-imgstudio-magic-group";
    group.setAttribute("data-pcx-magic-group", "1");
    group.innerHTML = `
      <label>🪄 Baguette magique</label>
      <div class="pcx-imgstudio-row">
        <input type="number" min="0" max="255" value="38" data-pcx-magic-tolerance title="Tolérance couleur">
        <input type="number" min="0" max="255" value="18" data-pcx-magic-alpha title="Seuil alpha">
        <button type="button" class="magic" data-pcx-magic-corners>Effacer coins</button>
        <button type="button" data-pcx-magic-restore>Rollback</button>
      </div>
      <small class="pcx-imgstudio-magic-note">Choisis “Baguette magique”, clique le fond à effacer. Monte la tolérance si le fond reste.</small>
    `;
    toolbar.appendChild(group);

    const canvas = qs(studio, "canvas[data-pcx-img-canvas]");
    if (!canvas) return;

    qs(studio, "[data-pcx-magic-corners]").addEventListener("click", () => eraseCorners(studio, canvas));
    qs(studio, "[data-pcx-magic-restore]").addEventListener("click", () => restoreMagic(studio, canvas));

    canvas.addEventListener("pointerdown", (ev) => {
      const tool = select ? select.value : "";
      if (tool !== "magic-wand") return;

      ev.preventDefault();
      ev.stopPropagation();
      ev.stopImmediatePropagation();

      const p = pointFromEvent(canvas, ev);
      eraseFlood(studio, canvas, p.x, p.y);
    }, true);

    canvas.addEventListener("pointermove", (ev) => {
      if (select && select.value === "magic-wand") {
        ev.preventDefault();
        ev.stopPropagation();
        ev.stopImmediatePropagation();
      }
    }, true);

    canvas.addEventListener("pointerup", (ev) => {
      if (select && select.value === "magic-wand") {
        ev.preventDefault();
        ev.stopPropagation();
        ev.stopImmediatePropagation();
      }
    }, true);
  }

  ready(() => {
    const run = () => qsa(document, '[data-pcx-image-studio="1"]').forEach(addMagicUi);
    run();
    setTimeout(run, 300);
    setTimeout(run, 900);
  });
})();

/* PINCABOS_IMAGE_STUDIO_V18_LOAD_ERROR */
(() => {
  "use strict";
  function ready(fn) {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", fn);
    else fn();
  }
  ready(() => {
    setTimeout(() => {
      document.querySelectorAll('[data-pcx-image-studio="1"]').forEach((studio) => {
        const canvas = studio.querySelector("canvas[data-pcx-img-canvas]");
        const status = studio.querySelector("[data-pcx-img-status]");
        if (!canvas || !status) return;

        setTimeout(() => {
          if (canvas.width < 2 || canvas.height < 2) {
            status.textContent = "Erreur: Image Studio n’a pas pu charger l’image. Route image-studio-file à vérifier.";
            status.style.color = "#ff6a6a";
          }
        }, 1800);
      });
    }, 300);
  });
})();

/* PINCABOS_IMAGE_STUDIO_V19_COMPACT_UI */
(() => {
  "use strict";

  function ready(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  function qsa(root, sel) {
    return Array.from(root.querySelectorAll(sel));
  }

  function applyCompactUi(studio) {
    if (!studio || studio.dataset.pcxCompactUiReady === "1") return;
    studio.dataset.pcxCompactUiReady = "1";

    const toolSelect = studio.querySelector("[data-pcx-img-tool]");
    if (toolSelect) {
      const labels = {
        "brush": "🖌 Brush",
        "eraser": "🩹 Eraser",
        "text": "🔤 Text",
        "line": "📏 Line",
        "rect": "▭ Rectangle",
        "ellipse": "◯ Ellipse",
        "crop": "✂ Crop",
        "magic-wand": "🪄 Magic Wand"
      };

      qsa(toolSelect, "option").forEach((opt) => {
        const val = (opt.value || "").trim();
        if (labels[val]) opt.textContent = labels[val];
      });
    }

    const saveBtn = studio.querySelector('[data-pcx-action="save"]');
    if (saveBtn) {
      saveBtn.textContent = "Save";
      saveBtn.classList.add("good");
    }

    const saveCopyBtn = studio.querySelector('[data-pcx-action="save-copy"]');
    if (saveCopyBtn) {
      saveCopyBtn.textContent = "Save as";
    }

    const useCurrentBtn = studio.querySelector("[data-pcx-img-use-current]");
    if (useCurrentBtn) {
      useCurrentBtn.textContent = "Current";
    }

    const cropBtn = studio.querySelector('[data-pcx-action="crop"]');
    if (cropBtn) {
      cropBtn.textContent = "Crop";
    }

    const resizeBtn = studio.querySelector('[data-pcx-action="resize"]');
    if (resizeBtn) {
      resizeBtn.textContent = "Resize";
    }

    const resetBtn = studio.querySelector('[data-pcx-action="reset"]');
    if (resetBtn) {
      resetBtn.textContent = "Reset";
    }

    const undoBtn = studio.querySelector('[data-pcx-action="undo"]');
    if (undoBtn) {
      undoBtn.textContent = "Undo";
    }

    const redoBtn = studio.querySelector('[data-pcx-action="redo"]');
    if (redoBtn) {
      redoBtn.textContent = "Redo";
    }

    const magicCorners = studio.querySelector("[data-pcx-magic-corners]");
    if (magicCorners) {
      magicCorners.textContent = "Erase corners";
    }

    const magicRollback = studio.querySelector("[data-pcx-magic-restore]");
    if (magicRollback) {
      magicRollback.textContent = "Rollback";
    }

    qsa(studio, ".pcx-imgstudio-group > label").forEach((label) => {
      const txt = (label.textContent || "").trim().toLowerCase();

      if (txt.includes("historical")) label.textContent = "History";
      if (txt.includes("color / size")) label.textContent = "Color / Size";
      if (txt.includes("transform")) label.textContent = "Transform";
      if (txt.includes("resize / crop")) label.textContent = "Resize / Crop";
      if (txt.includes("backup")) label.textContent = "Save";
      if (txt.includes("magic wand")) label.textContent = "🪄 Magic Wand";
    });

    const nameInput = studio.querySelector("[data-pcx-img-new-name]");
    if (nameInput) {
      nameInput.placeholder = "new-name.png";
    }

    const txtInput = studio.querySelector("[data-pcx-img-text]");
    if (txtInput && txtInput.value === "PinCabOS") {
      txtInput.value = "";
      txtInput.placeholder = "Text";
    }
  }

  ready(() => {
    const run = () => {
      qsa(document, '[data-pcx-image-studio="1"]').forEach(applyCompactUi);
    };
    run();
    setTimeout(run, 300);
    setTimeout(run, 900);
  });
})();
