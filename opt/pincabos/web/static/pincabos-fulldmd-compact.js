/* PinCabOS-File created by Karots Sugarpie */
document.addEventListener("DOMContentLoaded", function () {
  const path = window.location.pathname || "";
  const txt = document.body.innerText || "";

  const isFullDmd =
    path.includes("fulldmd") ||
    txt.includes("Calibration FullDMD") ||
    txt.includes("Écran FullDMD") ||
    txt.includes("Réglage du DMD dans le FullDMD");

  if (!isFullDmd) return;

  document.body.classList.add("pincabos-fulldmd-page");

  document.querySelectorAll(".fulldmd-inline-fields, .fulldmd-inline-fields-final").forEach(function (el) {
    el.remove();
  });

  function installDmdStepSlider() {
    const root = document.getElementById("pincabos-dmd-overlay-only-v4");
    if (!root || root.dataset.stepSlider100 === "1") return false;

    const stepHost = root.querySelector(".pco-dmd4-step");
    const panel = stepHost && stepHost.closest(".pco-dmd4-panel");
    if (!stepHost || !panel) return false;

    const originalButtons = Array.from(stepHost.querySelectorAll("button[data-step]"));
    const bridge = originalButtons[0];
    if (!bridge) return false;

    root.dataset.stepSlider100 = "1";

    const style = document.createElement("style");
    style.textContent = `
      .pco-dmd4-step-slider-wrap{width:100%;margin:0 0 10px}
      .pco-dmd4-step-value{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:5px;font-weight:800;color:#fff}
      .pco-dmd4-step-value strong{color:#ffb000;font-size:17px}
      .pco-dmd4-step-range{width:100%;margin:0;accent-color:#7a00ff;cursor:pointer}
      .pco-dmd4-step-ticks{display:grid;grid-template-columns:repeat(10,1fr);gap:0;margin-top:2px;color:#cfc6df;font-size:10px;line-height:1}
      .pco-dmd4-step-ticks span{text-align:center;transform:translateX(-1px)}
      .pco-dmd4-step-quick{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}
    `;
    panel.appendChild(style);

    const wrap = document.createElement("div");
    wrap.className = "pco-dmd4-step-slider-wrap";
    wrap.innerHTML = `
      <div class="pco-dmd4-step-value"><span>Pas sélectionné</span><strong id="pco-dmd4-step-value">1 px</strong></div>
      <input id="pco-dmd4-step-range" class="pco-dmd4-step-range" type="range" min="1" max="100" step="1" value="1" aria-label="Pas du DMD de 1 à 100 pixels">
      <div class="pco-dmd4-step-ticks" aria-hidden="true">
        <span>10</span><span>20</span><span>30</span><span>40</span><span>50</span><span>60</span><span>70</span><span>80</span><span>90</span><span>100</span>
      </div>
    `;
    stepHost.parentNode.insertBefore(wrap, stepHost);
    stepHost.classList.add("pco-dmd4-step-quick");

    const button1 = originalButtons.find((b) => Number(b.dataset.step) === 1);
    const button10 = originalButtons.find((b) => Number(b.dataset.step) === 10);
    const button50 = originalButtons.find((b) => Number(b.dataset.step) === 50);
    if (button1) button1.textContent = "1 px";
    if (button10) button10.textContent = "10 px";
    if (button50) button50.textContent = "50 px";

    const button100 = document.createElement("button");
    button100.type = "button";
    button100.className = "button secondary";
    button100.textContent = "100 px";
    button100.dataset.pcoStep = "100";
    stepHost.appendChild(button100);

    const slider = wrap.querySelector("#pco-dmd4-step-range");
    const value = wrap.querySelector("#pco-dmd4-step-value");

    function clampStep(raw) {
      const parsed = Number.parseInt(raw, 10);
      return Math.max(1, Math.min(100, Number.isFinite(parsed) ? parsed : 1));
    }

    function paintSelected(selected) {
      value.textContent = `${selected} px`;
      slider.value = String(selected);
      originalButtons.forEach((button) => {
        button.classList.toggle("active", Number(button.dataset.step) === selected);
      });
      button100.classList.toggle("active", selected === 100);
    }

    function setRuntimeStep(raw) {
      const selected = clampStep(raw);

      /*
       * Le moteur du tuner garde volontairement son pas dans une closure.
       * Le premier bouton déjà câblé sert de pont : on lui injecte la valeur
       * du slider le temps d'un click, puis on restaure son data-step.
       * Cela évite de dupliquer le moteur de déplacement ou ses appels API.
       */
      const previous = bridge.dataset.step;
      bridge.dataset.step = String(selected);
      bridge.click();
      bridge.dataset.step = previous;

      paintSelected(selected);
    }

    slider.addEventListener("input", function () {
      setRuntimeStep(slider.value);
    });

    originalButtons.forEach((button) => {
      button.addEventListener("click", function () {
        paintSelected(clampStep(button.dataset.step));
      });
    });

    button100.addEventListener("click", function () {
      setRuntimeStep(100);
    });

    paintSelected(1);
    return true;
  }

  if (!installDmdStepSlider()) {
    const observer = new MutationObserver(function () {
      if (installDmdStepSlider()) observer.disconnect();
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
    window.setTimeout(function () { observer.disconnect(); }, 10000);
  }
});
