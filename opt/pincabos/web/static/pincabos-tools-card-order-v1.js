/* PinCabOS Tools Card Order V1 — persistent per-section ordering */
(() => {
  "use strict";

  if (window.__pcoToolsCardOrderV1) return;
  window.__pcoToolsCardOrderV1 = true;

  const start = () => {
    if (window.location.pathname.replace(/\/+$/, "") !== "/tools") return;

    const page = document.querySelector(".pco-tools-page");
    const hero = page?.querySelector(".pco-tools-hero");
    const families = [...(page?.querySelectorAll(".pco-tools-family") || [])];
    if (!page || !hero || !families.length) return;

    const sectionKey = section => {
      const title = String(section.querySelector("h2")?.textContent || "").trim().toLowerCase();
      if (title.includes("vpinballx")) return "vpinballx";
      if (title.includes("vpinfe")) return "vpinfe";
      return "pincabos";
    };

    const cardKey = card => {
      const href = String(card.getAttribute("href") || "").trim();
      if (href) return `href:${href}`;
      const title = String(card.querySelector("strong")?.textContent || card.textContent || "")
        .replace(/\s+/g, " ")
        .trim()
        .toLowerCase();
      return `title:${title}`;
    };

    const lists = new Map();
    families.forEach(section => {
      const list = section.querySelector(".pco-tools-card-list");
      if (!list) return;
      const key = sectionKey(section);
      list.dataset.pcoToolsOrderSection = key;
      lists.set(key, list);
    });
    if (!lists.size) return;

    const style = document.createElement("style");
    style.id = "pco-tools-card-order-v1-style";
    style.textContent = `
      .pco-tools-hero{position:relative}
      .pco-tools-order-toolbar{
        display:flex;align-items:center;justify-content:flex-end;gap:8px;flex-wrap:wrap;
        position:absolute;top:18px;right:22px;z-index:7;
      }
      .pco-tools-order-btn{
        min-height:36px;padding:8px 12px;border:1px solid rgba(255,151,32,.72);
        border-radius:10px;background:rgba(20,8,33,.92);color:#fff;font:inherit;
        font-size:12px;font-weight:900;cursor:pointer;
      }
      .pco-tools-order-btn:hover:not(:disabled){border-color:#ff9b25;filter:brightness(1.12)}
      .pco-tools-order-btn:disabled{opacity:.48;cursor:not-allowed}
      .pco-tools-order-save{background:rgba(123,61,9,.96)}
      .pco-tools-order-status{width:100%;text-align:right;color:#d9cce8;font-size:11px;font-weight:700}
      .pco-tools-page .tool-card{position:relative}
      .pco-tools-order-grip{
        display:none;position:absolute;top:7px;right:7px;z-index:12;
        align-items:center;justify-content:center;width:36px;height:36px;
        border:1px solid rgba(255,151,32,.88);border-radius:10px;
        background:rgba(22,7,37,.96);color:#ffad43;font-size:21px;font-weight:900;
        line-height:1;cursor:grab;user-select:none;touch-action:none;
        box-shadow:0 3px 12px rgba(0,0,0,.34);
      }
      .pco-tools-page.is-order-editing .pco-tools-order-grip{display:flex}
      .pco-tools-page.is-order-editing .tool-card{cursor:default;border-style:dashed}
      .pco-tools-page.is-order-editing .tool-card.pco-tools-order-dragging{opacity:.48}
      .pco-tools-page.is-order-editing .pco-tools-card-list{min-height:54px}
      .pco-tools-page.is-order-editing .pco-tools-card-list.pco-tools-order-drop{
        outline:1px dashed rgba(255,151,32,.62);outline-offset:5px;border-radius:12px;
      }
      @media(max-width:900px){
        .pco-tools-order-toolbar{position:static;justify-content:flex-start;margin-top:14px}
        .pco-tools-order-status{text-align:left}
      }
    `;
    document.head.append(style);

    const toolbar = document.createElement("div");
    toolbar.className = "pco-tools-order-toolbar";
    toolbar.innerHTML = `
      <button type="button" class="pco-tools-order-btn pco-tools-order-edit">Changer l’ordre</button>
      <button type="button" class="pco-tools-order-btn pco-tools-order-save" hidden disabled>Enregistrer</button>
      <button type="button" class="pco-tools-order-btn pco-tools-order-cancel" hidden>Annuler</button>
      <span class="pco-tools-order-status" aria-live="polite"></span>
    `;
    hero.append(toolbar);

    const editButton = toolbar.querySelector(".pco-tools-order-edit");
    const saveButton = toolbar.querySelector(".pco-tools-order-save");
    const cancelButton = toolbar.querySelector(".pco-tools-order-cancel");
    const status = toolbar.querySelector(".pco-tools-order-status");

    let csrf = "";
    let editing = false;
    let dragging = null;
    let dragList = null;
    let armed = null;
    let snapshot = null;

    const cardsFor = list => [...list.querySelectorAll(":scope > .tool-card")];

    const serialize = () => {
      const sections = {};
      lists.forEach((list, key) => {
        sections[key] = cardsFor(list).map(cardKey);
      });
      return sections;
    };

    const applyOrder = sections => {
      if (!sections || typeof sections !== "object") return;
      lists.forEach((list, key) => {
        const order = Array.isArray(sections[key]) ? sections[key] : [];
        const cards = cardsFor(list);
        const byKey = new Map(cards.map(card => [cardKey(card), card]));
        const used = new Set();
        order.forEach(id => {
          const card = byKey.get(String(id));
          if (!card || used.has(card)) return;
          list.append(card);
          used.add(card);
        });
        cards.forEach(card => {
          if (!used.has(card)) list.append(card);
        });
      });
    };

    const setStatus = (message, isError = false) => {
      status.textContent = message || "";
      status.style.color = isError ? "#ffad72" : "";
    };

    const moveCard = (card, delta) => {
      const list = card?.parentElement;
      if (!editing || !list?.matches(".pco-tools-card-list")) return;
      const cards = cardsFor(list);
      const index = cards.indexOf(card);
      const target = index + delta;
      if (index < 0 || target < 0 || target >= cards.length) return;
      if (delta < 0) list.insertBefore(card, cards[target]);
      else list.insertBefore(cards[target], card);
      setStatus("Ordre modifié — clique Enregistrer pour le conserver.");
    };

    const ensureGrip = card => {
      if (card.querySelector(":scope > .pco-tools-order-grip")) return;
      const grip = document.createElement("span");
      grip.className = "pco-tools-order-grip";
      grip.setAttribute("role", "button");
      grip.setAttribute("tabindex", "0");
      grip.setAttribute("aria-label", "Déplacer cette carte");
      grip.setAttribute("title", "Déplacer cette carte — glisser ou utiliser ↑ / ↓");
      grip.textContent = "⠿";
      grip.addEventListener("pointerdown", event => {
        if (!editing) return;
        event.stopPropagation();
        armed = card;
      });
      grip.addEventListener("click", event => {
        event.preventDefault();
        event.stopPropagation();
      });
      grip.addEventListener("keydown", event => {
        if (!editing) return;
        if (event.key === "ArrowUp") {
          event.preventDefault();
          event.stopPropagation();
          moveCard(card, -1);
        } else if (event.key === "ArrowDown") {
          event.preventDefault();
          event.stopPropagation();
          moveCard(card, 1);
        } else if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          event.stopPropagation();
        }
      });
      card.append(grip);
    };

    lists.forEach(list => {
      cardsFor(list).forEach(card => {
        ensureGrip(card);
        card.addEventListener("click", event => {
          if (!editing) return;
          event.preventDefault();
          event.stopPropagation();
        }, true);
        card.addEventListener("dragstart", event => {
          if (!editing || armed !== card) {
            event.preventDefault();
            return;
          }
          dragging = card;
          dragList = list;
          card.classList.add("pco-tools-order-dragging");
          event.dataTransfer.effectAllowed = "move";
          event.dataTransfer.setData("text/plain", cardKey(card));
        });
        card.addEventListener("dragend", () => {
          card.classList.remove("pco-tools-order-dragging");
          lists.forEach(value => value.classList.remove("pco-tools-order-drop"));
          dragging = null;
          dragList = null;
          armed = null;
        });
      });

      list.addEventListener("dragover", event => {
        if (!editing || !dragging || dragList !== list) return;
        event.preventDefault();
        event.dataTransfer.dropEffect = "move";
        list.classList.add("pco-tools-order-drop");
        const target = event.target.closest(".tool-card");
        if (!target || target === dragging || target.parentElement !== list) return;
        const rect = target.getBoundingClientRect();
        const after = event.clientY > rect.top + rect.height / 2;
        list.insertBefore(dragging, after ? target.nextSibling : target);
      });

      list.addEventListener("drop", event => {
        if (!editing || !dragging || dragList !== list) return;
        event.preventDefault();
        list.classList.remove("pco-tools-order-drop");
        setStatus("Ordre modifié — clique Enregistrer pour le conserver.");
      });

      list.addEventListener("dragleave", event => {
        if (!list.contains(event.relatedTarget)) list.classList.remove("pco-tools-order-drop");
      });
    });

    document.addEventListener("pointerup", () => {
      if (!dragging) armed = null;
    });

    const setEditing = value => {
      editing = Boolean(value);
      page.classList.toggle("is-order-editing", editing);
      editButton.hidden = editing;
      saveButton.hidden = !editing;
      cancelButton.hidden = !editing;
      lists.forEach(list => cardsFor(list).forEach(card => {
        card.draggable = editing;
      }));
      if (editing) {
        snapshot = serialize();
        setStatus("Glisse les cartes avec ⠿. Chaque carte reste dans sa section.");
      } else {
        armed = null;
        dragging = null;
        dragList = null;
      }
    };

    editButton.addEventListener("click", () => setEditing(true));

    cancelButton.addEventListener("click", () => {
      if (snapshot) applyOrder(snapshot);
      setEditing(false);
      setStatus("Modifications annulées.");
    });

    saveButton.addEventListener("click", async () => {
      if (!csrf) {
        setStatus("Sauvegarde indisponible : recharge la page.", true);
        return;
      }
      saveButton.disabled = true;
      setStatus("Enregistrement de l’ordre…");
      try {
        const response = await fetch("/tools/order", {
          method: "POST",
          credentials: "same-origin",
          headers: {"Content-Type": "application/json", "X-CSRF-Token": csrf},
          body: JSON.stringify({csrf, sections: serialize()})
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || !payload.ok) throw new Error(payload.error || `HTTP ${response.status}`);
        applyOrder(payload.sections || {});
        snapshot = serialize();
        setEditing(false);
        setStatus("Ordre enregistré sur ce PinCabOS.");
      } catch (error) {
        console.error("PinCabOS Tools order save:", error);
        setStatus(`Échec de sauvegarde : ${error.message || error}`, true);
      } finally {
        saveButton.disabled = !csrf;
      }
    });

    const load = async () => {
      setStatus("Chargement de l’ordre des cartes…");
      try {
        const response = await fetch("/tools/order", {
          method: "GET",
          credentials: "same-origin",
          cache: "no-store",
          headers: {"Accept": "application/json"}
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || !payload.ok) throw new Error(payload.error || `HTTP ${response.status}`);
        csrf = String(payload.csrf || "");
        applyOrder(payload.sections || {});
        saveButton.disabled = !csrf;
        setStatus(payload.saved ? "Ordre personnalisé chargé." : "Ordre par défaut — prêt à être personnalisé.");
      } catch (error) {
        console.error("PinCabOS Tools order load:", error);
        saveButton.disabled = true;
        setStatus("Réorganisation disponible, mais sauvegarde serveur indisponible.", true);
      }
    };

    load();
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, {once: true});
  else start();
})();
