/* PinCabOs-File created by Karots Sugarpie */
/* PINCABOS_DUDESCAB_CONFIG_PAGE_V323_PERSISTENT_MAINTENANCE */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const state = { status: null, protocol: null, probe: null, live: null, manifest: null, local: [], jobId: null, timer: null, connectedUi: false, dirty: false, memoryDirty: false, monitorMode: "local", monitorTimer: null, liveTimer: null, liveStartTimer: null, outputTimers: new Map(), cardConfig: null, extensionIndex: 0, liveBusy: false, configBusy: false, connectBusy: false, maintenance: null, maintenanceToken: null, maintenanceTimer: null, maintenanceBusy: false, maintenanceOwned: false };
  const KEY_NAMES = ["[Invalid key code]","Keyboard ErrorRollOver","Keyboard POSTFail","Keyboard ErrorUndefined","A","B","C","D","E","F","G","H","I","J","K","L","M","N","O","P","Q","R","S","T","U","V","W","X","Y","Z","1","2","3","4","5","6","7","8","9","0","Enter","Escape","Backspace","Tab","Spacebar","-","=","[","]","\\","#",";","'","`",",",".","/","Caps Lock","F1","F2","F3","F4","F5","F6","F7","F8","F9","F10","F11","F12","Print Screen","Scroll Lock","Pause","Insert","Home","Page Up","Delete","End","Page Down","Right Arrow","Left Arrow","Down Arrow","Up Arrow","Num Lock","Keypad /","Keypad *","Keypad -","Keypad +","Keypad Enter","Keypad 1","Keypad 2","Keypad 3","Keypad 4","Keypad 5","Keypad 6","Keypad 7","Keypad 8","Keypad 9","Keypad 0","Keypad .","\\ (Non-US)","Application Key","Power","Keypad =","F13","F14","F15","F16","F17","F18","F19","F20","F21","F22","F23","F24","Execute","Help","Menu","Select","Stop","Again","Undo","Cut","Copy","Paste","Find","Mute","Volume Up","Volume Down","Locking Caps Lock","Locking Num Lock","Locking Scroll Lock","Keypad Comma","Keypad Equal Sign","International1","International2","International3","International4","International5","International6","International7","International8","International9","LANG1","LANG2","LANG3","LANG4","LANG5","LANG6","LANG7","LANG8","LANG9","Alternate Erase","SysReq/Attention","Cancel","Clear","Prior","Return","Separator","Out","Oper","Clear/Again","CrSel/Props","ExSel","Left Control","Left Shift","Left Alt","Left GUI","Right Control","Right Shift","Right Alt","Right GUI"];

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>'"]/g, (ch) => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[ch]));
  }
  function toast(message, error = false) {
    const box = $("dc-toast");
    box.textContent = message;
    box.classList.toggle("is-error", error);
    box.hidden = false;
    clearTimeout(box._timer);
    box._timer = setTimeout(() => { box.hidden = true; }, 4800);
  }
  async function api(url, options = {}) {
    const headers = new Headers(options.headers || {});
    if (state.maintenanceToken) headers.set("X-DudesCab-Maintenance", state.maintenanceToken);
    const response = await fetch(url, {cache:"no-store", ...options, headers});
    let payload;
    try { payload = await response.json(); } catch { payload = {ok:false,error:`Réponse HTTP ${response.status}`}; }
    if (!response.ok || payload.ok === false) throw new Error(payload.error || `Erreur HTTP ${response.status}`);
    return payload;
  }
  function maintenanceToken() {
    const key = "pincabosDudesCabMaintenanceToken";
    // Migrate the former per-tab token so an already active session survives
    // this upgrade. localStorage lets a reopened tab reclaim the same lock.
    let token = localStorage.getItem(key) || sessionStorage.getItem(key) || "";
    if (!/^[A-Za-z0-9_-]{16,128}$/.test(token)) {
      const bytes = new Uint8Array(24);
      crypto.getRandomValues(bytes);
      token = Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("");
    }
    localStorage.setItem(key, token);
    sessionStorage.removeItem(key);
    state.maintenanceToken = token;
    return token;
  }
  function ensureMaintenanceBanner() {
    if ($("dc-maintenance-banner")) return;
    const style = document.createElement("style");
    style.textContent = `
      #dc-maintenance-banner{position:sticky;top:0;z-index:10050;display:flex;align-items:center;gap:12px;padding:10px 14px;background:linear-gradient(90deg,#3d0066,#6f1aa8);border-bottom:2px solid #d8a9ff;color:#fff;box-shadow:0 8px 24px rgba(0,0,0,.38)}
      #dc-maintenance-banner.is-error{background:linear-gradient(90deg,#661010,#a12626);border-color:#ff9c9c}
      #dc-maintenance-banner strong{font-size:14px}#dc-maintenance-banner small{display:block;margin-top:2px;color:#eadcf5}
      #dc-maintenance-banner .dc-maintenance-spacer{flex:1}#dc-maintenance-banner button{min-height:34px;padding:7px 13px;border:1px solid #ead8ff;border-radius:6px;background:#6c2c9f;color:#fff;font-weight:800}
      #dc-maintenance-banner button:hover{background:#8d48bf}#dc-maintenance-banner button.dc-maintenance-quit{background:#40105e}
    `;
    document.head.appendChild(style);
    const banner = document.createElement("div");
    banner.id = "dc-maintenance-banner";
    banner.innerHTML = `<div><strong id="dc-maintenance-title">Dude détectée · VPinFE et VPX actifs</strong><small id="dc-maintenance-detail">VPinFE et VPX seront arrêtés uniquement lorsque tu cliqueras Connecter.</small></div><div class="dc-maintenance-spacer"></div><button type="button" id="dc-maintenance-retry" hidden>Réessayer</button><button type="button" id="dc-maintenance-quit" class="dc-maintenance-quit">Quitter DudesCabConfig</button>`;
    const app = $("dc-app") || document.body;
    app.insertBefore(banner, app.firstChild);
    $("dc-maintenance-retry").addEventListener("click", enterMaintenance);
    $("dc-maintenance-quit").addEventListener("click", exitMaintenance);
  }
  function setMaintenanceControls(enabled) {
    const selectors = ["[data-card-action]", "[data-output-test]", "#dc-all-off", "#dc-mx-test", "#dc-mx-alloff", "#dc-refresh-status", "#dc-plunger-calibrate"];
    $$(selectors.join(",")).forEach((element) => { element.disabled = !enabled; });
    const connect = $("dc-connect-btn");
    if (connect) connect.disabled = !state.status?.connected || state.connectBusy || state.configBusy;
  }
  function renderMaintenance(status, error = "") {
    ensureMaintenanceBanner();
    state.maintenance = status || {active:false};
    const banner = $("dc-maintenance-banner");
    const active = !!status?.active && !!state.maintenanceOwned && !error;
    const waiting = !active && !error;
    banner.classList.toggle("is-error", !!error);
    if (active) {
      $("dc-maintenance-title").textContent = "Mode maintenance DudesCab actif";
      const restored = status.vpinfe_was_active ? "VPinFE sera restauré à la déconnexion" : "VPinFE était déjà arrêté";
      $("dc-maintenance-detail").textContent = `Verrou persistant sans expiration · VPinFE arrêté · VPX arrêté · ${restored}.`;
      $("dc-maintenance-retry").hidden = true;
    } else if (waiting) {
      $("dc-maintenance-title").textContent = state.status?.connected ? "Dude détectée · VPinFE et VPX actifs" : "Dude's Cab absente";
      $("dc-maintenance-detail").textContent = state.status?.connected
        ? "VPinFE et VPX seront arrêtés seulement quand tu cliqueras Connecter."
        : "La page DudesCabConfig nécessite une carte USB 2e8a:106f.";
      $("dc-maintenance-retry").hidden = true;
    } else {
      $("dc-maintenance-title").textContent = "Connexion DudesCab impossible";
      $("dc-maintenance-detail").textContent = error || status?.error || "Le mode maintenance n'a pas pu être activé.";
      $("dc-maintenance-retry").hidden = false;
    }
    setMaintenanceControls(active);
  }
  async function enterMaintenance() {
    if (state.maintenanceBusy) return false;
    state.maintenanceBusy = true;
    ensureMaintenanceBanner();
    $("dc-maintenance-title").textContent = "Connexion en préparation…";
    $("dc-maintenance-detail").textContent = "Arrêt contrôlé de VPinFE et de tout processus VPX.";
    setMaintenanceControls(false);
    try {
      const data = await api("/api/dudescabconfig/maintenance/enter", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({token:maintenanceToken()})});
      state.maintenanceOwned = true;
      renderMaintenance(data);
      clearInterval(state.maintenanceTimer);
      state.maintenanceTimer = setInterval(heartbeatMaintenance, 15000);
      toast("Verrou maintenance persistant actif: aucune déconnexion automatique.");
      return true;
    } catch (error) {
      state.maintenanceOwned = false;
      renderMaintenance(null, error.message);
      toast(`Mode maintenance: ${error.message}`, true);
      return false;
    } finally {
      state.maintenanceBusy = false;
    }
  }
  async function heartbeatMaintenance() {
    if (!state.maintenance?.active) return;
    try {
      const data = await api("/api/dudescabconfig/maintenance/heartbeat", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({token:maintenanceToken()})});
      state.maintenanceOwned = true;
      renderMaintenance(data);
    } catch (error) {
      // A browser/network heartbeat failure must never release or invalidate
      // the server-side persistent lock. Keep controls attached to the last
      // known ownership and retry on the next interval.
      const detail = $("dc-maintenance-detail");
      if (detail) detail.textContent = `Verrou serveur conservé · heartbeat temporairement indisponible: ${error.message}`;
      toast(`Heartbeat indisponible; la session reste verrouillée: ${error.message}`, true);
    }
  }
  async function releaseMaintenance({redirectToCommander=false, quiet=false} = {}) {
    clearInterval(state.maintenanceTimer); state.maintenanceTimer = null;
    if (!state.maintenance?.active && !state.maintenanceOwned) {
      if (redirectToCommander) window.location.assign("/dof/commander");
      else renderMaintenance({active:false});
      return true;
    }
    try {
      const data = await api("/api/dudescabconfig/maintenance/exit", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({token:maintenanceToken()})});
      state.maintenance = data;
      state.maintenanceOwned = false;
      localStorage.removeItem("pincabosDudesCabMaintenanceToken");
      sessionStorage.removeItem("pincabosDudesCabMaintenanceToken");
      if (!quiet) toast(data.vpinfe_was_active ? "VPinFE restauré après la déconnexion." : "Mode maintenance terminé.");
      if (redirectToCommander) window.location.assign("/dof/commander");
      else renderMaintenance({active:false});
      return true;
    } catch (error) {
      renderMaintenance(null, error.message);
      if (!quiet) toast(`Restauration VPinFE: ${error.message}`, true);
      return false;
    }
  }
  async function exitMaintenance() {
    const button = $("dc-maintenance-quit");
    if (button) { button.disabled = true; button.textContent = "Restauration…"; }
    try {
      if (state.connectedUi) {
        await api('/api/dudescabconfig/protocol/disconnect', {method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
        state.connectedUi = false;
      }
      await releaseMaintenance({redirectToCommander:true});
    } catch (error) {
      toast(`Sortie DudesCabConfig: ${error.message}`, true);
      if (button) { button.disabled = false; button.textContent = "Quitter DudesCabConfig"; }
    }
  }

  function requireMaintenanceUi() {
    if (state.maintenance?.active && state.maintenanceOwned) return true;
    toast("Mode maintenance requis. VPinFE et VPX doivent être arrêtés.", true);
    return false;
  }

  function formatBytes(bytes) {
    const n = Number(bytes || 0);
    if (n < 1024) return `${n} o`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} Kio`;
    return `${(n / 1024 / 1024).toFixed(1)} Mio`;
  }
  function setTab(id) {
    $$('[data-dc-tab]').forEach((button) => button.classList.toggle("is-active", button.dataset.dcTab === id));
    $$('[data-dc-panel]').forEach((panel) => panel.classList.toggle("is-active", panel.dataset.dcPanel === id));
    history.replaceState(null, "", `#${id}`);
    if (id === "monitor") loadStatus();
  }
  function installTabs() {
    $$('[data-dc-tab]').forEach((button) => button.addEventListener("click", () => setTab(button.dataset.dcTab)));
    $$('[data-dc-tab-jump]').forEach((button) => button.addEventListener("click", () => setTab(button.dataset.dcTabJump)));
    const initial = location.hash.slice(1);
    if (initial && document.querySelector(`[data-dc-panel="${CSS.escape(initial)}"]`)) setTab(initial);
  }
  function markDirty() {
    state.dirty = true;
    $("dc-send-dirty").hidden = false;
  }
  function markMemoryDirty() {
    state.memoryDirty = true;
    $("dc-memory-dirty").hidden = false;
  }
  function collectConfig() {
    const values = {};
    $$('[data-config-key]').forEach((element) => {
      values[element.dataset.configKey] = element.type === "checkbox" ? element.checked : element.value;
    });
    return {format:"DudesCabConfig-Web", version:2, exported_at:new Date().toISOString(), values};
  }
  function applyConfig(payload) {
    const values = payload?.values || payload || {};
    $$('[data-config-key]').forEach((element) => {
      if (!(element.dataset.configKey in values)) return;
      if (element.type === "checkbox") element.checked = !!values[element.dataset.configKey];
      else element.value = values[element.dataset.configKey];
      element.dispatchEvent(new Event("input", {bubbles:true}));
    });
    markDirty();
    toast("Configuration DUDE chargée dans l'interface Web.");
  }
  function exportConfig() {
    const blob = new Blob([JSON.stringify(collectConfig(), null, 2) + "\n"], {type:"application/json"});
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `DudesCab-${new Date().toISOString().slice(0,10)}.dude`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast("Fichier DUDE sauvegardé.");
  }
  async function importConfig(file) {
    try { applyConfig(JSON.parse(await file.text())); }
    catch (error) { toast(`Fichier DUDE invalide: ${error.message}`, true); }
  }
  function ensureSelectValue(element, value) {
    if (!element) return;
    const wanted = String(value ?? "");
    let option = Array.from(element.options || []).find((item) => item.value === wanted || item.textContent === wanted);
    if (!option) {
      option = document.createElement("option");
      option.value = wanted;
      option.textContent = wanted;
      element.appendChild(option);
    }
    element.value = option.value;
  }
  function setControl(key, value) {
    const element = document.querySelector(`[data-config-key="${CSS.escape(key)}"]`);
    if (!element || value === undefined || value === null) return;
    if (element.type === "checkbox") element.checked = !!value;
    else if (element.tagName === "SELECT") ensureSelectValue(element, value);
    else {
      const numeric = Number(value);
      if (element.type === "range" && Number.isFinite(numeric)) {
        if (numeric < Number(element.min || numeric)) element.min = String(numeric);
        if (numeric > Number(element.max || numeric)) element.max = String(numeric);
      }
      element.value = String(value);
    }
    if (element.dataset.rangeOutput) syncRange(element);
    element.dispatchEvent(new Event("input", {bubbles:true}));
  }
  function pinLabel(pin, noneLabel = "Aucun") {
    const value = Number(pin || 0);
    return value > 0 ? `Bouton ${value}` : noneLabel;
  }
  function inputFunctionLabel(binding) {
    const type = Number(binding?.type ?? 0);
    const fn = Number(binding?.function ?? 0);
    if (type === 0) return "None";
    if (type === 2) {
      if (fn >= 0 && fn < 32) return `Button ${fn + 1}`;
      const dpad = ["DPAD Up", "DPAD Right", "DPAD Down", "DPAD Left"];
      return dpad[fn - 32] || `Joystick ${fn}`;
    }
    const key = KEY_NAMES[fn] || `${type === 3 ? "Media" : "Keyboard"} ${fn}`;
    return key === "Spacebar" ? "Space" : key.replace("Right Arrow", "Arrow Right").replace("Left Arrow", "Arrow Left").replace("Down Arrow", "Arrow Down").replace("Up Arrow", "Arrow Up");
  }
  function presetLabel(value) {
    return ["Custom", "Flipper Logic", "Contacteurs", "Moteurs", "Leds", "Ampoules"][Number(value)] || `Preset ${value}`;
  }
  function testLabel(value) {
    return ["Aucun", "RGB", "Couleurs", "Laser"][Number(value)] || `Test ${value}`;
  }
  function chipsetLabel(value) {
    return ["WS2811", "WS2812", "WS2812B", "WS2813", "WS2815", "SK6812"][Number(value)] || `Chipset ${value}`;
  }
  function arrangementLabel(value) {
    return ["LeftRightTopDown","LeftRightBottomUp","RightLeftTopDown","RightLeftBottomUp","TopDownLeftRight","TopDownRightLeft","BottomUpLeftRight","BottomUpRightLeft","LeftRightAlternateTopDown","LeftRightAlternateBottomUp","RightLeftAlternateTopDown","RightLeftAlternateBottomUp","TopDownAlternateLeftRight","TopDownAlternateRightLeft","BottomUpAlternateLeftRight","BottomUpAlternateRightLeft"][Number(value)] || `Arrangement ${value}`;
  }
  function applyExtension(index) {
    const config = state.cardConfig;
    const extension = config?.extensions?.[Number(index)] || null;
    if (state.extLoaded && Number(index) !== state.extensionIndex) writeBackSelectedOutputs();
    state.extensionIndex = Number(index) || 0;
    if (!extension) return;
    setControl("extension.1.name", extension.name || `Extension ${extension.address}`);
    setControl("extension.1.id", extension.address);
    if (extension.pwm_frequency !== null) setControl("extension.1.pwm", extension.pwm_frequency);
    setControl("extension.1.power", 100);
    (extension.outputs || []).forEach((output, offset) => {
      const number = offset + 1;
      setControl(`output.${number}.enabled`, output.enabled);
      setControl(`output.${number}.name`, output.name);
      setControl(`output.${number}.preset`, presetLabel(output.preset));
      setControl(`output.${number}.night`, output.night_mode_affected);
      setControl(`output.${number}.digital`, output.digital);
      setControl(`output.${number}.gamma`, output.gamma_correct);
      setControl(`output.${number}.inverted`, output.inverted);
      setControl(`output.${number}.max`, output.max_value);
      setControl(`output.${number}.intensity`, output.intensity);
      setControl(`output.${number}.falloff`, output.falloff_value);
      setControl(`output.${number}.minimum`, output.min_active_time);
      setControl(`output.${number}.falloff_delay`, output.falloff_delay);
      setControl(`output.${number}.safety`, output.security_delay);
      const card = document.querySelector(`[data-output-card="${number}"]`);
      const dof = card?.querySelector('.dc-dof-number strong');
      if (dof) dof.textContent = String(output.dof_number);
      const selector = document.querySelector(`[data-output-select="${number}"]`);
      if (selector) selector.classList.toggle("dc-output-disabled", !output.enabled);
    });
    state.extLoaded = true;
  }
  function renderExtensionSelector(extensions) {
    const select = $("dc-extension-select");
    if (!select) return;
    const rows = extensions || [];
    select.innerHTML = rows.length
      ? rows.map((extension, index) => `<option value="${index}">#${escapeHtml(extension.address)} — ${escapeHtml(extension.name || `Extension ${extension.address}`)}</option>`).join("")
      : '<option value="0">Aucune extension configurée</option>';
    select.disabled = rows.length === 0;
    select.value = "0";
    if (rows.length) applyExtension(0);
  }
  function renderMxCardConfig(mx) {
    if (!mx) return;
    setControl("mx.enabled", mx.enabled);
    setControl("mx.model", chipsetLabel(mx.led_chipset));
    setControl("mx.ledwiz", mx.ledwiz_equivalent);
    setControl("mx.reset_test", testLabel(mx.test_on_reset));
    setControl("mx.connection_test", testLabel(mx.test_on_connect));
    setControl("mx.duration", mx.test_on_connect_duration || mx.test_on_reset_duration || 0);
    setControl("mx.brightness", mx.test_brightness);
    if (mx.compression_ratio !== null) setControl("mx.compression", mx.compression_ratio);
    for (let lane=1; lane<=8; lane++) {
      const holder=document.querySelector(`[data-mx-lane="${lane}"] .dc-mx-strips`);
      const empty=document.querySelector(`[data-mx-lane="${lane}"] .dc-mx-empty`);
      const count=document.querySelector(`[data-mx-lane="${lane}"] [data-mx-count]`);
      if(holder) holder.innerHTML="";
      if(empty) empty.hidden=false;
      if(count) count.textContent="0";
    }
    (mx.ledstrips || []).forEach((strip) => {
      const first = strip.splits?.[0]?.data_output_num ?? 0;
      const lane = first >= 0 && first <= 7 ? first + 1 : Math.max(1, Math.min(8, Number(first) || 1));
      const holder=document.querySelector(`[data-mx-lane="${lane}"] .dc-mx-strips`);
      const empty=document.querySelector(`[data-mx-lane="${lane}"] .dc-mx-empty`);
      if(!holder) return;
      const row=document.createElement("div");
      row.className="dc-mx-strip dc-mx-strip-read";
      const splitText=(strip.splits || []).map((split)=>`Ligne ${Number(split.data_output_num)+1}: ${split.nb_leds} LEDs`).join(" · ");
      row.innerHTML=`<label>Nom<input type="text" value="${escapeHtml(strip.name)}"></label><label>Largeur<input type="number" value="${Number(strip.width)}"></label><label>Hauteur<input type="number" value="${Number(strip.height)}"></label><label>Numéro sortie DOF<input type="number" value="${Number(strip.dof_output_num)}"></label><label>Arrangement<select><option>${escapeHtml(arrangementLabel(strip.led_arrangement))}</option></select></label><label>Brillance<input type="number" value="${Number(strip.brightness)}"></label><div class="dc-mx-splits" title="${escapeHtml(splitText)}">${escapeHtml(splitText || "Aucun split")}</div>`;
      holder.appendChild(row);
      if(empty) empty.hidden=true;
    });
    for (let lane=1; lane<=8; lane++) {
      const count=document.querySelector(`[data-mx-lane="${lane}"] [data-mx-count]`);
      const total=(mx.ledstrips || []).flatMap((strip)=>strip.splits || []).filter((split)=>Number(split.data_output_num)+1===lane).reduce((sum,split)=>sum+Number(split.nb_leds||0),0);
      if(count) count.textContent=String(total);
    }
  }
  function applyCardConfiguration(config) {
    state.cardConfig = config;
    const general=config.general || {};
    $("dc-config-version").textContent = String(config.version ?? "—");
    setControl("general.name", general.name);
    setControl("general.id", general.card_id);
    if (general.cpu_frequency !== null) setControl("general.cpu", general.cpu_frequency);
    setControl("general.night_boot", general.default_night_mode);
    if (general.watchdog_delay !== null) setControl("general.watchdog", general.watchdog_delay);
    setControl("inputs.keyboard", ["Qwerty","Azerty","Qwertz","Colemak"][Number(general.keyboard_layout)] || `Clavier ${general.keyboard_layout}`);
    const colors=general.colors || {};
    if(colors.default) setControl("color.default", colors.default.hex);
    if(colors.admin) setControl("color.admin", colors.admin.hex);
    if(colors.night) setControl("color.night", colors.night.hex);
    if(colors.calibration) setControl("color.calibration", colors.calibration.hex);
    setControl("inputs.shift", pinLabel(config.inputs?.shift_button_pin));
    setControl("inputs.night", pinLabel(config.inputs?.night_mode_button_pin));
    (config.inputs?.items || []).forEach((item,index)=>{
      const number=index+1;
      setControl(`input.${number}.primary`, inputFunctionLabel(item.default));
      setControl(`input.${number}.shifted`, inputFunctionLabel(item.shifted));
      setControl(`input.${number}.latency`, Number(item.latency)===0 ? "Optimal" : "Normale");
      setControl(`input.${number}.debounce`, item.debounce_delay);
    });
    const acc=config.accelerometer || {};
    setControl("accelerometer.orientation", ["Arrière","Droite","Avant","Gauche"][Number(general.usb_orientation)] || `Orientation ${general.usb_orientation}`);
    if(acc.precision !== null) setControl("accelerometer.range", ["±4g","±8g","±16g","±32g"][Number(acc.precision)] || `Précision ${acc.precision}`);
    setControl("accelerometer.poll", acc.report_delay);
    if(acc.history_buffer !== null) setControl("accelerometer.cache", acc.history_buffer);
    if(acc.filter_strength !== null) setControl("accelerometer.filter", acc.filter_strength);
    setControl("accelerometer.x", acc.x_sensitivity);
    setControl("accelerometer.y", acc.y_sensitivity);
    setControl("accelerometer.dead", acc.dead_zone);
    setControl("accelerometer.tilt", acc.tilt_range);
    setControl("accelerometer.tilt_button", pinLabel(acc.tilt_button_pin, "Aucun"));
    const plunger=config.plunger || {};
    setControl("plunger.enabled", plunger.enabled);
    setControl("plunger.inverted", plunger.inverted);
    setControl("plunger.poll", plunger.report_delay);
    setControl("plunger.shake", plunger.jitter_window);
    setControl("plunger.calibration", plunger.calibration_duration);
    setControl("plunger.cal_button", pinLabel(plunger.calibration_button_pin, "Aucun"));
    setControl("plunger.pulled", pinLabel(plunger.pull_button_pin, "Aucun"));
    setControl("plunger.pushed", pinLabel(plunger.push_button_pin, "Aucun"));
    if($("dc-plunger-calibrated")) $("dc-plunger-calibrated").checked=!!plunger.calibrated;
    state.extLoaded = false;
    renderExtensionSelector(config.extensions || []);
    renderMxCardConfig(config.mx);
    state.dirty=false; state.memoryDirty=false;
    $("dc-send-dirty").hidden=true; $("dc-memory-dirty").hidden=true;
    if(state.monitorMode==="local") renderLocalMonitor();
  }
  const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

  async function waitForLiveIdle(timeoutMs=5000) {
    const deadline = Date.now() + timeoutMs;
    stopLivePolling();
    while (state.liveBusy && Date.now() < deadline) await delay(50);
    if (state.liveBusy) throw new Error("Une lecture de statut HID est encore active. Réessaie dans quelques secondes.");
  }

  async function readCardConfig(silent=false) {
    if(!requireMaintenanceUi()) return;
    if(!state.connectedUi){ if(!silent) toast("Connecte d'abord la Dude's Cab.",true); return; }
    if(state.configBusy || state.connectBusy) return;
    const button=document.querySelector('[data-card-action="read"]');
    const resumeLive=!!(state.liveTimer || state.liveStartTimer);
    state.configBusy=true;
    if(button){button.disabled=true;button.textContent="Lecture…";}
    try {
      await waitForLiveIdle(5000);
      const data=await api('/api/dudescabconfig/protocol/config');
      applyCardConfiguration(data.config);
      $("dc-last-error").textContent = "Aucune";
      if(!silent) toast(`Configuration réelle v${data.config.version} lue: ${data.config.raw_size} octets.`);
    } catch(error) {
      toast(`Lire Config: ${error.message}`,true);
      throw error;
    } finally {
      state.configBusy=false;
      if(button){button.disabled=false;button.textContent="Lire Config";}
      if(resumeLive && state.connectedUi) stopLivePolling();
    }
  }

  function statusText(connected) {
    if (!connected) return "Rien à boire? Connecte ta Dude!";
    return state.connectedUi ? "C'est l'apéro !!" : "Dude détectée - clique sur Connecter";
  }
  function renderStatus(status) {
    state.status = status;
    const connected = !!status.connected;
    $("dc-main-status").textContent = connected ? "Dude's Cab détectée" : "Dude's Cab absente";
    $("dc-main-detail").textContent = connected ? `${status.hid_count || 0} HID · ${status.serial_ready ? "série prête" : "série absente"}` : "USB 2e8a:106f non détecté";
    $("dc-status-idle").classList.toggle("is-active", connected);
    $("dc-connect-btn").textContent = state.connectedUi ? "Déconnecter" : "Connecter";
    $("dc-connect-btn").disabled = !connected;
    const usb = status.usb?.[0] || {};
    const select = $("dc-device-select");
    select.innerHTML = connected
      ? `<option>${escapeHtml(usb.name || "Dude's Cab")} - ${escapeHtml(status.serial?.[0]?.path || "HID")} - ${escapeHtml(usb.serial || "sans numéro")}</option>`
      : '<option>Aucune Dude\'s Cab détectée</option>';
    const low = (status.space || []).filter((x) => (x.free_mb ?? 99999) < (x.path === "/run" ? 20 : 200) || (x.free_inodes ?? 99999) < 100);
    const warning = $("dc-space-warning");
    warning.hidden = low.length === 0;
    warning.textContent = low.length ? `Espace ou inodes insuffisants: ${low.map((x) => `${x.path}: ${x.free_mb ?? "?"} Mio / ${x.free_inodes ?? "?"} inodes`).join(" · ")}.` : "";
    $("dc-hid-pill").textContent = `${status.hid_count || 0} interface(s)`;
    $("dc-serial-pill").textContent = `${status.serial?.length || 0} port(s)`;
    $("dc-hid-list").innerHTML = (status.hidraw || []).map((item) => `<div class="dc-device-row"><code>${escapeHtml(item.path)}</code><span class="${item.readable && item.writable ? "dc-ok" : "dc-bad"}">${item.readable && item.writable ? "RW" : "REFUSÉ"}</span></div>`).join("") || '<div>Aucune interface HID.</div>';
    $("dc-serial-list").innerHTML = (status.serial || []).map((item) => `<div class="dc-device-row"><code>${escapeHtml(item.path)}</code><span class="${item.readable && item.writable ? "dc-ok" : "dc-bad"}">${item.readable && item.writable ? "RW" : "REFUSÉ"}</span></div>`).join("") || '<div>Aucun port série.</div>';
    if (state.monitorMode === "local") renderLocalMonitor();
    if (status.vpx_running) $("dc-last-error").textContent = "VPX en jeu: tests physiques interdits";
    else if (!state.probe?.status?.last_error) $("dc-last-error").textContent = "Aucune";
    renderConnectionSummary();
  }
  function showMissingDeviceWarning() {
    if ($("dc-device-missing-overlay")) return;
    setMaintenanceControls(false);
    const overlay = document.createElement("div");
    overlay.id = "dc-device-missing-overlay";
    overlay.style.cssText = "position:fixed;inset:0;z-index:12000;display:flex;align-items:center;justify-content:center;padding:24px;background:rgba(7,5,9,.92)";
    overlay.innerHTML = `
      <section style="width:min(620px,94vw);padding:30px;border:1px solid #9b5ac2;border-radius:14px;background:linear-gradient(180deg,#321c3e,#17101c);box-shadow:0 25px 80px rgba(0,0,0,.62);text-align:center;color:#fff">
        <div style="width:68px;height:68px;margin:0 auto 16px;border-radius:50%;display:grid;place-items:center;background:#6f2d9e;border:2px solid #ddbaff;font-size:34px;font-weight:900">!</div>
        <h2 style="margin:0 0 10px">Dude's Cab déconnectée</h2>
        <p style="color:#ded1e6;line-height:1.5">La carte USB <code style="color:#edceff">2e8a:106f</code> n'est plus détectée. Les fonctions matérielles sont désactivées.</p>
        <p style="color:#ded1e6">Le verrou maintenance reste actif. VPinFE et VPX ne seront pas relancés automatiquement.</p>
        <div style="display:flex;justify-content:center;gap:12px;flex-wrap:wrap;margin-top:20px">
          <button type="button" id="dc-device-retry" style="min-height:44px;padding:0 22px;border:1px solid #ddbaff;border-radius:8px;background:#6f2d9e;color:#fff;font-weight:800">Réessayer</button>
          <button type="button" id="dc-device-return" style="min-height:44px;padding:0 22px;border:1px solid #b99acb;border-radius:8px;background:#382241;color:#fff;font-weight:800">Retour au DOF Commander</button>
        </div>
      </section>`;
    document.body.appendChild(overlay);
    $("dc-device-retry").addEventListener("click", () => window.location.reload());
    $("dc-device-return").addEventListener("click", () => window.location.assign("/dof/commander"));
  }

  async function loadStatus() {
    if (state.configBusy || state.connectBusy) return;
    try {
      const [hardware, protocol] = await Promise.all([
        api("/api/dudescabconfig/status"),
        api("/api/dudescabconfig/protocol/status")
      ]);
      state.protocol = protocol;
      if (protocol.maintenance) {
        renderMaintenance(protocol.maintenance, protocol.maintenance.ok === false ? protocol.maintenance.error : "");
        if (protocol.maintenance.active && !state.maintenanceOwned) {
          try {
            const reclaimed = await api("/api/dudescabconfig/maintenance/heartbeat", {
              method:"POST",
              headers:{"Content-Type":"application/json"},
              body:JSON.stringify({token:maintenanceToken()})
            });
            state.maintenanceOwned = true;
            renderMaintenance(reclaimed);
            clearInterval(state.maintenanceTimer);
            state.maintenanceTimer = setInterval(heartbeatMaintenance, 15000);
          } catch (claimError) {
            state.maintenanceOwned = false;
            renderMaintenance(protocol.maintenance, "Verrou actif dans une autre session. Utilise le même navigateur ou la récupération SSH.");
          }
        }
      }
      if (protocol.last_probe && Object.keys(protocol.last_probe).length) state.probe = protocol.last_probe;
      state.connectedUi = !!protocol.admin_enabled;
      renderStatus(hardware.status);
      if (state.probe) renderProbe(state.probe);
      if (!hardware.status.connected) {
        // Never release maintenance automatically. During a future write or
        // flash operation, USB detection can be transient; VPinFE/VPX must
        // remain stopped until an explicit user action.
        showMissingDeviceWarning();
      }
    } catch (error) {
      $("dc-last-error").textContent = error.message;
      toast(error.message, true);
    }
  }
  async function toggleConnection() {
    if (!state.status?.connected || state.connectBusy || state.configBusy) return;
    const target = !state.connectedUi;
    const button = $("dc-connect-btn");
    let maintenanceStarted = false;
    state.connectBusy = true;
    stopLivePolling();
    button.disabled = true;
    button.textContent = target ? "Préparation…" : "Déconnexion…";
    try {
      await waitForLiveIdle(5000);
      if (target) {
        const ready = await enterMaintenance();
        if (!ready) throw new Error("VPinFE/VPX n'ont pas pu être arrêtés pour la connexion.");
        maintenanceStarted = true;
        button.textContent = "Connexion…";
      }
      const data = await api(`/api/dudescabconfig/protocol/${target ? "connect" : "disconnect"}`, {method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});
      state.connectedUi = target;
      state.probe = data.probe;
      renderProbe(data.probe);
      renderConnectionSummary();
      stopLivePolling();
      if (target) {
        toast("Dude's Cab connectée. VPinFE et VPX resteront arrêtés jusqu'à Déconnecter ou Quitter.");
      } else {
        $("dc-last-error").textContent = "Aucune";
        await releaseMaintenance();
        toast("Dude's Cab déconnectée. Les services précédemment actifs ont été restaurés.");
      }
    } catch (error) {
      state.connectedUi = false;
      stopLivePolling();
      if (target && maintenanceStarted) await releaseMaintenance({quiet:true});
      toast(error.message, true);
    } finally {
      state.connectBusy = false;
      button.disabled = !state.status?.connected;
      button.textContent = state.connectedUi ? "Déconnecter" : "Connecter";
      setMaintenanceControls(!!state.maintenance?.active && state.maintenanceOwned);
    }
  }

  async function protectedAction(action) {
    const messages = {
      send:"La commande Admin SetConfig reste verrouillée: lecture seulement dans cette V3.1.",
      "memory-read":"La commande de lecture Flash reste verrouillée.",
      "memory-save":"La commande de sauvegarde Flash reste verrouillée.",
      "memory-reset":"La remise à zéro de la mémoire reste bloquée.",
    };
    if (action === "read") { await readCardConfig(false); return; }
    if (action === "monitor") { setTab("monitor"); return; }
    if (action === "reset") { resetDude(); return; }
    if (action === "watchdog-test") { testWatchdog(); return; }
    if (action === "send") { await saveCardConfig(); return; }
    if (action === "memory-read") { await memoryRead(); return; }
    if (action === "memory-reset") { await memoryReset(); return; }
    if (action === "memory-save") { toast("Écriture mémoire flash : structure du blob non documentée (endpoint brut /flash/write disponible).", true); return; }
    toast(messages[action] || "Commande Admin d'écriture volontairement bloquée.", true);
  }
  function unitFor(id, value) {
    if (/cpu/.test(id)) return `${value} MHz`;
    if (/watchdog|duration|cal-time|safe-/.test(id)) return `${value} s`;
    if (/poll|delay|min-|pulse/.test(id)) return `${value} ms`;
    if (/power|brightness|filter|intensity/.test(id)) return `${value} %`;
    if (/pwm-frequency/.test(id)) return `${value} Hz`;
    if (/card-id/.test(id)) return `${value} (LedWiz ${89 + Number(value)})`;
    return String(value);
  }
  function syncRange(range) {
    const output = document.getElementById(range.dataset.rangeOutput);
    if (output) output.textContent = unitFor(range.dataset.rangeOutput, range.value);
  }
  function installConfigEvents() {
    $$('[data-config-key]').forEach((element) => {
      element.addEventListener("change", markDirty);
      element.addEventListener("input", () => { if (element.dataset.rangeOutput) syncRange(element); });
      if (element.dataset.rangeOutput) syncRange(element);
    });
    $$('input[type=range][data-range-output]').forEach((range) => range.addEventListener("input", () => syncRange(range)));
    $("dc-dead-range").addEventListener("input", () => { const v = Number($("dc-dead-range").value); $("dc-dead-circle").style.width = `${Math.max(4,v)}%`; $("dc-dead-circle").style.height = `${Math.max(4,v)}%`; });
    $("dc-tilt-range").addEventListener("input", () => { const v = Number($("dc-tilt-range").value); $("dc-tilt-circle").style.width = `${v}%`; $("dc-tilt-circle").style.height = `${v}%`; });
    $("dc-nudge-visual").addEventListener("pointermove", (event) => {
      if (!event.buttons) return;
      const rect = event.currentTarget.getBoundingClientRect();
      const x = Math.max(0, Math.min(100, ((event.clientX - rect.left) / rect.width) * 100));
      const y = Math.max(0, Math.min(100, ((event.clientY - rect.top) / rect.height) * 100));
      $("dc-nudge-dot").style.left = `${x}%`; $("dc-nudge-dot").style.top = `${y}%`;
      $("dc-axis-x").textContent = Math.round((x - 50) * 2); $("dc-axis-y").textContent = Math.round((50 - y) * 2);
    });
    $("dc-nudge-visual").addEventListener("pointerleave", () => { $("dc-nudge-dot").style.left="50%"; $("dc-nudge-dot").style.top="50%"; $("dc-axis-x").textContent="0"; $("dc-axis-y").textContent="0"; });
    $("dc-shift-button").addEventListener("change", () => { const enabled = $("dc-shift-button").value !== "Aucun"; $$('.dc-shifted-field').forEach((x) => x.style.opacity = enabled ? "1" : ".35"); });
    $("dc-save-dude").addEventListener("click", exportConfig);
    $("dc-load-dude").addEventListener("click", () => $("dc-load-dude-input").click());
    $("dc-load-dude-input").addEventListener("change", (e) => e.target.files?.[0] && importConfig(e.target.files[0]));
  }
  function installOutputUi() {
    const extensionSelect=$("dc-extension-select");
    if(extensionSelect) extensionSelect.addEventListener("change",()=>applyExtension(Number(extensionSelect.value)));
    $$('[data-output-select]').forEach((button) => button.addEventListener("click", () => {
      $$('[data-output-select]').forEach((x) => x.classList.toggle("is-active", x === button));
      $$('[data-output-card]').forEach((x) => x.classList.toggle("is-active", x.dataset.outputCard === button.dataset.outputSelect));
    }));
    $$('[data-test-slider]').forEach((range) => range.addEventListener("input", () => range.nextElementSibling.textContent = range.value));
    $$('[data-output-test]').forEach((button) => button.addEventListener("click", () => runOutputTest(button)));
    $$('[data-output-preset]').forEach((select) => select.addEventListener("change", () => {
      const card = select.closest('.dc-output-card');
      const checks = $$('input[type=checkbox]', card);
      if (select.value === "Contacteurs") { const item=checks.find((x) => x.dataset.configKey?.endsWith('.digital')); if(item)item.checked = true; }
      if (select.value === "Leds") { const item=checks.find((x) => x.dataset.configKey?.endsWith('.gamma')); if(item)item.checked = true; }
      markDirty();
    }));
    const top = document.querySelector('.dc-outputs-top');
    if (top && !$("dc-all-off")) {
      const button = document.createElement('button');
      button.type='button'; button.id='dc-all-off'; button.className='dc-danger-button'; button.textContent='TOUT ÉTEINDRE';
      button.addEventListener('click', allOutputsOff); top.appendChild(button);
    }
  }
  function addMxStrip(lane) {
    const holder = document.querySelector(`[data-mx-lane="${lane}"] .dc-mx-strips`);
    const empty = document.querySelector(`[data-mx-lane="${lane}"] .dc-mx-empty`);
    const index = holder.children.length + 1;
    const row = document.createElement("div");
    row.className = "dc-mx-strip";
    row.innerHTML = `<label>Nom<input type="text" value="Ledstrip ${lane}.${index}"></label><label>Largeur<input type="number" min="1" max="512" value="1"></label><label>Hauteur<input type="number" min="1" max="512" value="1"></label><label>Numéro sortie DOF<input type="number" min="1" max="999" value="${(lane-1)*3+1}"></label><label>Arrangement<select><option>LeftRightTopDown</option><option>LeftRightBottomUp</option><option>TopDownLeftRight</option><option>BottomUpLeftRight</option></select></label><label>Brillance<input type="number" min="0" max="100" value="50"></label><button type="button" class="dc-remove-strip">🗑</button>`;
    holder.appendChild(row); empty.hidden = true;
    const update = () => {
      let total = 0;
      $$('.dc-mx-strip', holder).forEach((strip) => { const nums = $$('input[type=number]', strip); total += Number(nums[0]?.value || 0) * Number(nums[1]?.value || 0); });
      document.querySelector(`[data-mx-lane="${lane}"] [data-mx-count]`).textContent = String(total);
    };
    row.addEventListener("input", () => { update(); markDirty(); });
    row.querySelector('.dc-remove-strip').addEventListener("click", () => { row.remove(); empty.hidden = holder.children.length > 0; update(); markDirty(); });
    update(); markDirty();
  }
  function installMxUi() {
    $$('[data-add-strip]').forEach((button) => button.addEventListener("click", () => addMxStrip(button.dataset.addStrip)));
    $("dc-mx-test").addEventListener("click", runMxTest);
    const host = $("dc-mx-test")?.parentElement;
    if (host && !$("dc-mx-alloff")) {
      const button=document.createElement('button'); button.type='button'; button.id='dc-mx-alloff'; button.className='dc-danger-button'; button.textContent='Éteindre MX';
      button.addEventListener('click', allMxOff); host.appendChild(button);
    }
  }
  function renderOfficial(manifest) {
    state.manifest = manifest;
    $("dc-manifest-age").textContent = manifest?.fetched_at ? `Mise à jour: ${manifest.fetched_at}` : "Aucun manifeste chargé.";
    const select = $("dc-firmware-select");
    const rows = manifest?.firmwares || [];
    select.innerHTML = rows.length ? rows.map((item) => `<option value="${escapeHtml(item.version)}">${escapeHtml(item.version)} — ${escapeHtml(item.file)}</option>`).join("") : '<option value="">Aucun firmware disponible</option>';
  }
  function renderLocal(rows) {
    state.local = rows || [];
    $("dc-local-list").innerHTML = state.local.length ? state.local.slice(0,4).map((item) => `<div class="dc-local-row"><span>${escapeHtml(item.relative)} <small>${formatBytes(item.size)}</small></span><button type="button" data-local-flash="${escapeHtml(item.relative)}" ${item.valid ? "" : "disabled"}>Installer</button></div>`).join("") : "";
    $$('[data-local-flash]').forEach((button) => button.addEventListener("click", () => startFlash(button.dataset.localFlash)));
  }
  async function loadFirmwares() {
    try { const data = await api(`/api/dudescabconfig/firmwares?channel=${encodeURIComponent($("dc-channel").value)}`); renderOfficial(data.manifest); renderLocal(data.local); }
    catch (error) { toast(error.message, true); }
  }
  async function refreshManifest() {
    const button = $("dc-refresh-manifest"); button.disabled = true; button.textContent = "Recherche…";
    try { const data = await api("/api/dudescabconfig/firmwares/refresh", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({channel:$("dc-channel").value})}); renderOfficial(data.manifest); toast("Liste officielle des firmwares actualisée."); }
    catch (error) { toast(error.message, true); }
    finally { button.disabled = false; button.textContent = "Rechercher"; }
  }
  async function flashSelectedOfficial() {
    const version = $("dc-firmware-select").value;
    if (!version) { toast("Choisis d'abord un firmware disponible.", true); return; }
    const button = $("dc-firmware-flash"); button.disabled = true; button.textContent = "Téléchargement…";
    try {
      const data = await api("/api/dudescabconfig/firmwares/download", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({channel:$("dc-channel").value,version})});
      renderLocal(data.local);
      await startFlash(data.firmware.relative);
    } catch (error) { toast(error.message, true); }
    finally { button.disabled = false; button.textContent = "Flasher le Firmware"; }
  }
  async function uploadAndFlash(event) {
    event.preventDefault();
    const input = $("dc-upload-file"); if (!input.files?.length) return;
    const form = new FormData(); form.append("firmware", input.files[0]);
    const button = event.currentTarget.querySelector('button[type=submit]'); button.disabled = true; button.textContent = "Validation…";
    try { const data = await api("/api/dudescabconfig/firmwares/upload", {method:"POST",body:form}); renderLocal(data.local); input.value=""; await startFlash(data.firmware.relative); }
    catch (error) { toast(error.message, true); }
    finally { button.disabled = false; button.textContent = "Flasher un fichier Firmware"; }
  }
  async function startFlash(relative) {
    if (state.status?.vpx_running) { toast("VPX est en jeu. Ferme la table avant le flash.", true); return; }
    if (!window.confirm(`Installer ce firmware sur la Dude's Cab?\n\n${relative}\n\nNe débranche pas le câble USB.`)) return;
    try {
      const data = await api("/api/dudescabconfig/firmwares/flash", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({relative,confirmed:true})});
      state.jobId = data.job_id; $("dc-job-card").hidden = false; $("dc-job-close").disabled = true; pollJob();
    } catch (error) { toast(error.message, true); }
  }
  function renderJob(job) {
    const done = ["go","nogo"].includes(job.status);
    $("dc-job-status").textContent = job.status === "go" ? "GO" : job.status === "nogo" ? "NOGO" : "EN TEST";
    $("dc-job-bar").style.width = `${Math.max(0,Math.min(100,Number(job.progress || 0)))}%`;
    $("dc-job-detail").textContent = job.detail || job.stage || "—";
    $("dc-job-log").textContent = job.log || "";
    $("dc-job-log").scrollTop = $("dc-job-log").scrollHeight;
    $("dc-job-close").disabled = !done;
    if (done) { clearTimeout(state.timer); state.timer = null; loadStatus(); loadFirmwares(); toast(job.status === "go" ? "Firmware copié et Dude's Cab reconnectée." : `Flash échoué: ${job.detail || "voir le journal"}`, job.status !== "go"); }
  }
  async function pollJob() {
    if (!state.jobId) return;
    try { const data = await api(`/api/dudescabconfig/jobs/${encodeURIComponent(state.jobId)}`); renderJob(data.job); if (!["go","nogo"].includes(data.job.status)) state.timer=setTimeout(pollJob,1000); }
    catch (error) { $("dc-job-detail").textContent=error.message; state.timer=setTimeout(pollJob,2000); }
  }
  function installMonitor() {
    $("dc-monitor-refresh").addEventListener("click", () => state.monitorMode === "card" ? loadCardLogs() : refreshProtocol());
    $("dc-monitor-clear").addEventListener("click", clearMonitor);
    $("dc-monitor-local").addEventListener("click", () => {
      state.monitorMode="local"; $("dc-monitor-local").classList.add("is-active"); $("dc-monitor-card").classList.remove("is-active");
      stopMonitorPolling(); renderLocalMonitor();
    });
    $("dc-monitor-card").addEventListener("click", () => {
      state.monitorMode="card"; $("dc-monitor-card").classList.add("is-active"); $("dc-monitor-local").classList.remove("is-active");
      loadCardLogs(); startMonitorPolling();
    });
    $("dc-log-level").addEventListener("change", setLogLevel);
  }

  function renderConnectionSummary() {
    const connected = !!state.status?.connected;
    const liveStatus = state.live?.status || state.probe?.status;
    $("dc-status-message").textContent = !connected ? "Rien à boire? Connecte ta Dude!" : state.connectedUi ? "C'est l'apéro !!" : "Dude détectée - clique sur Connecter";
    $("dc-status-admin").classList.toggle("is-active", !!(state.connectedUi || liveStatus?.admin_mode));
    $("dc-status-calibration").classList.toggle("is-active", liveStatus?.name === "Calibration");
    $("dc-status-night").classList.toggle("is-active", !!liveStatus?.night_mode);
    $("dc-status-shift").classList.toggle("is-active", !!liveStatus?.shift_active);
    $("dc-status-warning").classList.toggle("is-active", liveStatus?.name === "Warning" || (!!connected && !state.status?.serial_ready));
    $("dc-status-error").classList.toggle("is-active", liveStatus?.name === "Error" || Number(liveStatus?.last_error || 0) > 0);
    if (liveStatus?.last_error_text) $("dc-last-error").textContent = liveStatus.last_error ? `${liveStatus.last_error}: ${liveStatus.last_error_text}` : "Aucune";
  }
  function renderProbe(probe) {
    state.probe = probe || {};
    const version = probe?.version?.text || "—";
    $("dc-firmware-installed").textContent = version;
    state.live = {version:probe?.version, status:probe?.status};
    renderConnectionSummary();
    const pwm = probe?.pwm;
    if (pwm?.extensions?.length) {
      const addresses = pwm.extensions.map((x) => x.address).join(', ');
      $("dc-main-detail").textContent = `${state.status?.hid_count || 0} HID · Firmware ${version} · Walter ${addresses}`;
    }
    if (state.monitorMode === 'local') renderLocalMonitor();
    const usefulErrors = (probe?.errors || []).filter((message) => !String(message).startsWith("Statut:"));
    if (usefulErrors.length) toast(`Lecture partielle: ${usefulErrors[0]}`, true);
  }
  function renderLive(live) {
    state.live = live || {};
    if (live?.version?.text) $("dc-firmware-installed").textContent = live.version.text;
    renderConnectionSummary();
  }
  function renderLocalMonitor() {
    const payload = {safe_mode:'manual HID only', hardware:state.status, protocol:state.protocol, probe:state.probe, live:state.live, card_config:state.cardConfig};
    $("dc-monitor-json").textContent = JSON.stringify(payload, null, 2);
  }
  async function refreshProtocol() {
    if (!requireMaintenanceUi()) return;
    const button=$("dc-refresh-status"); if(button){button.disabled=true;button.textContent='Lecture…';}
    try { const data=await api('/api/dudescabconfig/protocol/probe'); renderProbe(data.probe); toast('Handshake, version, PWM et MX actualisés. Statut HID désactivé en mode SAFE.'); }
    catch(error){toast(error.message,true);}
    finally { if(button){button.disabled=false;button.textContent='Actualiser le matériel';} }
  }
  async function pollLive() {
    if (!state.connectedUi || document.hidden || state.liveBusy || state.configBusy) return;
    state.liveBusy=true;
    try { const data=await api('/api/dudescabconfig/protocol/live'); renderLive(data.live); }
    catch(error) { $("dc-last-error").textContent=error.message; }
    finally { state.liveBusy=false; }
  }
  function startLivePolling() {
    // SAFE V3.1.4: no automatic HID polling.  Keep this function as a no-op so
    // cached call sites cannot create timers after a partial browser refresh.
    stopLivePolling();
  }
  function stopLivePolling() {
    if(state.liveStartTimer){clearTimeout(state.liveStartTimer);state.liveStartTimer=null;}
    if(state.liveTimer){clearInterval(state.liveTimer);state.liveTimer=null;}
  }
  async function resetDude() {
    if (!requireMaintenanceUi()) return;
    if(!window.confirm("Redémarrer la Dude's Cab? VPX doit être fermé.")) return;
    try { await api('/api/dudescabconfig/protocol/reset',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirmation:'RESET DUDE'})}); state.connectedUi=false; stopLivePolling(); toast("Reset envoyé. Attente de la reconnexion USB."); setTimeout(loadStatus,2500); }
    catch(error){toast(error.message,true);}
  }
  async function testWatchdog() {
    if (!requireMaintenanceUi()) return;
    if(!window.confirm("Ce test bloque volontairement la carte afin que le watchdog la redémarre. Continuer?")) return;
    try { await api('/api/dudescabconfig/protocol/watchdog',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirmation:'TEST WATCHDOG'})}); state.connectedUi=false; stopLivePolling(); toast("Test Watchdog lancé. La carte doit redémarrer."); setTimeout(loadStatus,3500); }
    catch(error){toast(error.message,true);}
  }
  async function runOutputTest(button) {
    if (!requireMaintenanceUi()) return;
    const output=Number(button.dataset.output); const extension=Number(document.querySelector('[data-config-key="extension.1.id"]')?.value || 1); const card=button.closest('[data-output-card]'); const slider=card?.querySelector('[data-test-slider]');
    const operation=button.dataset.outputTest;
    if(operation==='on' && button.dataset.active==='1') {
      try { await api('/api/dudescabconfig/protocol/outputs/test',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({extension,output,operation:'off'})}); button.dataset.active='0';button.textContent='ON';toast(`Sortie ${output} éteinte.`); }
      catch(error){toast(error.message,true);} return;
    }
    const value=operation==='on' ? 255 : Math.max(1,Number(slider?.value || 255));
    const duration=operation==='pulse' ? Number(document.querySelector('[data-config-key="outputs.pulse"]')?.value || 50) : 10000;
    try {
      const data=await api('/api/dudescabconfig/protocol/outputs/test',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({extension,output,operation,value,duration_ms:duration})});
      if(operation==='on'){button.dataset.active='1';button.textContent='OFF';clearTimeout(state.outputTimers.get(button));state.outputTimers.set(button,setTimeout(()=>{button.dataset.active='0';button.textContent='ON';},duration+200));}
      toast(`Walter ${extension}, sortie ${output}: ${value} pendant ${data.result.auto_off_ms} ms.`);
    } catch(error){toast(error.message,true);}
  }
  async function allOutputsOff() {
    if (!requireMaintenanceUi()) return;
    try { await api('/api/dudescabconfig/protocol/outputs/alloff',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}); $$('[data-output-test="on"]').forEach((b)=>{b.dataset.active='0';b.textContent='ON';}); toast('Toutes les sorties PWM sont éteintes.'); }
    catch(error){toast(error.message,true);}
  }
  async function runMxTest() {
    if (!requireMaintenanceUi()) return;
    const label=document.querySelector('[data-config-key="mx.connection_test"]')?.value || 'RGB'; const map={'Aucun':'none','RGB':'rgb','Couleurs':'colors','Laser':'laser'}; const test=map[label] || 'rgb'; const duration=Number(document.querySelector('[data-config-key="mx.duration"]')?.value || 5);
    if(test==='none'){toast('Choisis RGB, Couleurs ou Laser.',true);return;}
    try { await api('/api/dudescabconfig/protocol/mx/test',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({test,duration})}); toast(`Test MX ${label} lancé pour ${duration} s.`); }
    catch(error){toast(error.message,true);}
  }
  async function allMxOff() {
    if (!requireMaintenanceUi()) return; try { await api('/api/dudescabconfig/protocol/mx/alloff',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}); toast('Toutes les sorties MX sont éteintes.'); } catch(error){toast(error.message,true);} }
  async function setLogLevel() {
    if (!requireMaintenanceUi()) return; try { await api('/api/dudescabconfig/protocol/log-level',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({level:$("dc-log-level").value})}); toast(`Niveau de log: ${$("dc-log-level").value}`); } catch(error){toast(error.message,true);} }
  async function loadCardLogs() {
    try { const data=await api('/api/dudescabconfig/protocol/logs'); $("dc-monitor-json").textContent=(data.lines || []).join('\n') || `Aucune ligne reçue sur ${data.serial || 'le port série'}.`; if($("dc-auto-scroll").checked) $("dc-monitor-json").scrollTop=$("dc-monitor-json").scrollHeight; }
    catch(error){$("dc-monitor-json").textContent=error.message;}
  }
  function startMonitorPolling(){stopMonitorPolling();state.monitorTimer=setInterval(()=>{if(state.monitorMode==='card'&&!document.hidden)loadCardLogs();},1000);}
  function stopMonitorPolling(){if(state.monitorTimer){clearInterval(state.monitorTimer);state.monitorTimer=null;}}
  async function clearMonitor(){ if(state.monitorMode==='card'){try{await api('/api/dudescabconfig/protocol/logs/clear',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});}catch{} } $("dc-monitor-json").textContent=''; }
  function pauseFirmware() {
    const box=document.querySelector('.dc-firmware-box'); if(!box)return;
    box.querySelectorAll('input,select,button').forEach((el)=>el.disabled=true);
    const note=document.createElement('div');note.className='dc-safe-note';note.textContent='Gestion du firmware mise sur glace. Cette V3 travaille uniquement avec le protocole HID documenté et ne flashe rien.';box.appendChild(note);
    const local=$("dc-local-list");if(local)local.innerHTML='';
  }
  // === PINCABOS_DUDESCAB_WRITE_V1 : ecriture config carte (UI -> modele -> SetConfig) ===
  const KEYBOARD_LABELS = ["Qwerty","Azerty","Qwertz","Colemak"];
  const ORIENTATION_LABELS = ["Arrière","Droite","Avant","Gauche"];
  const PRECISION_LABELS = ["±4g","±8g","±16g","±32g"];
  const PRESET_LABELS = ["Custom","Flipper Logic","Contacteurs","Moteurs","Leds","Ampoules"];
  const CHIPSET_LABELS = ["WS2811","WS2812","WS2812B","WS2813","WS2815","SK6812"];
  const TEST_LABELS = ["Aucun","RGB","Couleurs","Laser"];
  function ctrlEl(key){ return document.querySelector(`[data-config-key="${CSS.escape(key)}"]`); }
  function ctrlVal(key){ const e=ctrlEl(key); if(!e) return undefined; return e.type==="checkbox"?e.checked:e.value; }
  function num0(v){ const n=Number(v); return Number.isFinite(n)?n:0; }
  function idxOfLabel(arr,label){ const i=arr.indexOf(String(label ?? "")); return i<0?null:i; }
  function pinFromLabel(t){ const m=/(\d+)/.exec(String(t ?? "")); return (/aucun/i.test(String(t ?? "")) || !m)?0:Number(m[1]); }
  function hexToRgb(hex){ const m=/^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(String(hex ?? "")); if(!m) return null; return {r:parseInt(m[1],16),g:parseInt(m[2],16),b:parseInt(m[3],16),hex:("#"+m[1]+m[2]+m[3]).toLowerCase()}; }

  function writeBackSelectedOutputs(){
    const c=state.cardConfig; const ext=c && c.extensions && c.extensions[state.extensionIndex||0]; if(!ext) return;
    (ext.outputs||[]).forEach((o,off)=>{ const n=off+1;
      if(ctrlEl(`output.${n}.enabled`)) o.enabled=!!ctrlVal(`output.${n}.enabled`);
      if(ctrlEl(`output.${n}.name`)) o.name=String(ctrlVal(`output.${n}.name`) ?? "");
      const pr=idxOfLabel(PRESET_LABELS, ctrlVal(`output.${n}.preset`)); if(pr!==null) o.preset=pr;
      if(ctrlEl(`output.${n}.night`)) o.night_mode_affected=!!ctrlVal(`output.${n}.night`);
      if(ctrlEl(`output.${n}.digital`)) o.digital=!!ctrlVal(`output.${n}.digital`);
      if(ctrlEl(`output.${n}.gamma`)) o.gamma_correct=!!ctrlVal(`output.${n}.gamma`);
      if(ctrlEl(`output.${n}.inverted`)) o.inverted=!!ctrlVal(`output.${n}.inverted`);
      if(ctrlEl(`output.${n}.max`)) o.max_value=num0(ctrlVal(`output.${n}.max`));
      if(ctrlEl(`output.${n}.intensity`)) o.intensity=num0(ctrlVal(`output.${n}.intensity`));
      if(ctrlEl(`output.${n}.falloff`)) o.falloff_value=num0(ctrlVal(`output.${n}.falloff`));
      if(ctrlEl(`output.${n}.minimum`)) o.min_active_time=num0(ctrlVal(`output.${n}.minimum`));
      if(ctrlEl(`output.${n}.falloff_delay`)) o.falloff_delay=num0(ctrlVal(`output.${n}.falloff_delay`));
      if(ctrlEl(`output.${n}.safety`)) o.security_delay=num0(ctrlVal(`output.${n}.safety`));
      let f=0; if(o.enabled)f|=0x80; if(o.night_mode_affected)f|=0x01; if(!o.digital)f|=0x02; if(o.gamma_correct)f|=0x04; if(o.inverted)f|=0x08;
      o.flags=((Number(o.flags)||0) & 0x70) | f;
    });
  }

  function writeConfigBack(){
    const c=state.cardConfig; if(!c) throw new Error("Lis d'abord la configuration de la carte (Lire Config).");
    const g=c.general=c.general||{};
    if(ctrlEl("general.name")) g.name=String(ctrlVal("general.name") ?? "");
    if(ctrlEl("general.id")) g.card_id=num0(ctrlVal("general.id"));
    if(ctrlEl("general.cpu") && g.cpu_frequency!=null) g.cpu_frequency=num0(ctrlVal("general.cpu"));
    if(ctrlEl("general.night_boot")) g.default_night_mode=!!ctrlVal("general.night_boot");
    if(ctrlEl("general.watchdog") && g.watchdog_delay!=null) g.watchdog_delay=num0(ctrlVal("general.watchdog"));
    const kb=idxOfLabel(KEYBOARD_LABELS, ctrlVal("inputs.keyboard")); if(kb!==null) g.keyboard_layout=kb;
    const ori=idxOfLabel(ORIENTATION_LABELS, ctrlVal("accelerometer.orientation")); if(ori!==null) g.usb_orientation=ori;
    if(g.colors){ ["default","admin","night","calibration"].forEach((k)=>{ const col=hexToRgb(ctrlVal("color."+k)); if(col) g.colors[k]=col; }); }
    c.inputs=c.inputs||{};
    if(ctrlEl("inputs.shift")) c.inputs.shift_button_pin=pinFromLabel(ctrlVal("inputs.shift"));
    if(ctrlEl("inputs.night")) c.inputs.night_mode_button_pin=pinFromLabel(ctrlVal("inputs.night"));
    (c.inputs.items||[]).forEach((item,i)=>{ const n=i+1; if(ctrlEl(`input.${n}.debounce`)) item.debounce_delay=num0(ctrlVal(`input.${n}.debounce`)); });
    const a=c.accelerometer=c.accelerometer||{};
    if(ctrlEl("accelerometer.poll")) a.report_delay=num0(ctrlVal("accelerometer.poll"));
    if(ctrlEl("accelerometer.x")) a.x_sensitivity=num0(ctrlVal("accelerometer.x"));
    if(ctrlEl("accelerometer.y")) a.y_sensitivity=num0(ctrlVal("accelerometer.y"));
    if(ctrlEl("accelerometer.dead")) a.dead_zone=num0(ctrlVal("accelerometer.dead"));
    if(ctrlEl("accelerometer.tilt")) a.tilt_range=num0(ctrlVal("accelerometer.tilt"));
    if(ctrlEl("accelerometer.tilt_button")) a.tilt_button_pin=pinFromLabel(ctrlVal("accelerometer.tilt_button"));
    const prec=idxOfLabel(PRECISION_LABELS, ctrlVal("accelerometer.range")); if(prec!==null && a.precision!=null) a.precision=prec;
    if(ctrlEl("accelerometer.cache") && a.history_buffer!=null) a.history_buffer=num0(ctrlVal("accelerometer.cache"));
    if(ctrlEl("accelerometer.filter") && a.filter_strength!=null) a.filter_strength=num0(ctrlVal("accelerometer.filter"));
    const p=c.plunger=c.plunger||{};
    if(ctrlEl("plunger.enabled")) p.enabled=!!ctrlVal("plunger.enabled");
    if(ctrlEl("plunger.inverted")) p.inverted=!!ctrlVal("plunger.inverted");
    if(ctrlEl("plunger.poll")) p.report_delay=num0(ctrlVal("plunger.poll"));
    if(ctrlEl("plunger.shake")) p.jitter_window=num0(ctrlVal("plunger.shake"));
    if(ctrlEl("plunger.calibration")) p.calibration_duration=num0(ctrlVal("plunger.calibration"));
    if(ctrlEl("plunger.cal_button")) p.calibration_button_pin=pinFromLabel(ctrlVal("plunger.cal_button"));
    if(ctrlEl("plunger.pulled")) p.pull_button_pin=pinFromLabel(ctrlVal("plunger.pulled"));
    if(ctrlEl("plunger.pushed")) p.push_button_pin=pinFromLabel(ctrlVal("plunger.pushed"));
    writeBackSelectedOutputs();
    if(c.mx){ const m=c.mx;
      if(ctrlEl("mx.enabled")) m.enabled=!!ctrlVal("mx.enabled");
      if(ctrlEl("mx.ledwiz")) m.ledwiz_equivalent=num0(ctrlVal("mx.ledwiz"));
      if(ctrlEl("mx.brightness")) m.test_brightness=num0(ctrlVal("mx.brightness"));
      const chip=idxOfLabel(CHIPSET_LABELS, ctrlVal("mx.model")); if(chip!==null) m.led_chipset=chip;
      const rt=idxOfLabel(TEST_LABELS, ctrlVal("mx.reset_test")); if(rt!==null) m.test_on_reset=rt;
      const ct=idxOfLabel(TEST_LABELS, ctrlVal("mx.connection_test")); if(ct!==null) m.test_on_connect=ct;
      if(ctrlEl("mx.duration")){ const d=num0(ctrlVal("mx.duration")); m.test_on_connect_duration=d; m.test_on_reset_duration=d; }
      if(ctrlEl("mx.compression") && m.compression_ratio!=null) m.compression_ratio=num0(ctrlVal("mx.compression"));
    }
    return c;
  }

  async function saveCardConfig(){
    if(!requireMaintenanceUi()) return;
    if(!state.connectedUi){ toast("Connecte d'abord la Dude's Cab.",true); return; }
    if(state.configBusy || state.connectBusy) return;
    const btn=document.querySelector('[data-card-action="send"]');
    state.configBusy=true; if(btn) btn.disabled=true;
    try{
      const config=writeConfigBack();
      await waitForLiveIdle(3000);
      await api("/api/dudescabconfig/protocol/config/write",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({config,save:true})});
      state.dirty=false; if($("dc-send-dirty")) $("dc-send-dirty").hidden=true;
      toast("Configuration écrite et sauvegardée sur la carte.");
      state.configBusy=false;
      await readCardConfig(true);
    }catch(error){
      state.configBusy=false;
      toast(`Envoyer Config: ${error.message}`,true);
    }finally{
      state.configBusy=false; if(btn) btn.disabled=false;
    }
  }

  async function calibratePlunger(){
    if(!requireMaintenanceUi()) return;
    if(!state.connectedUi){ toast("Connecte d'abord la Dude's Cab.",true); return; }
    try{
      await api("/api/dudescabconfig/protocol/plunger/calibrate",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});
      toast("Calibration du plunger déclenchée — suis la procédure (tire/pousse) puis relis la config.");
    }catch(error){ toast(`Calibration: ${error.message}`,true); }
  }

  async function memoryRead(){
    if(!requireMaintenanceUi()) return;
    if(!state.connectedUi){ toast("Connecte d'abord la Dude's Cab.",true); return; }
    try{
      const data=await api("/api/dudescabconfig/protocol/flash/read",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});
      if($("dc-monitor-json")){ setTab("monitor"); $("dc-monitor-json").textContent=`Mémoire flash (${data.size} octets):\n${data.response_hex}`; }
      toast(`Mémoire flash lue: ${data.size} octets.`);
    }catch(error){ toast(`Lire mémoire: ${error.message}`,true); }
  }

  async function memoryReset(){
    if(!requireMaintenanceUi()) return;
    if(!state.connectedUi){ toast("Connecte d'abord la Dude's Cab.",true); return; }
    if(!window.confirm("Réinitialiser la mémoire flash de la carte ? Action irréversible.")) return;
    try{
      await api("/api/dudescabconfig/protocol/flash/reset",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({confirmed:true})});
      toast("Mémoire flash réinitialisée.");
    }catch(error){ toast(`Réinitialiser mémoire: ${error.message}`,true); }
  }


  function install() {
    ensureMaintenanceBanner();
    installTabs(); installConfigEvents(); installOutputUi(); installMxUi(); installMonitor(); pauseFirmware();
    setMaintenanceControls(false);
    $("dc-connect-btn").addEventListener("click", toggleConnection);
    $$('[data-card-action]').forEach((button) => button.addEventListener("click", () => protectedAction(button.dataset.cardAction).catch(()=>{})));
    $$('[data-lang]').forEach((button) => button.addEventListener("click", () => { $$('[data-lang]').forEach((x) => x.classList.toggle("is-active", x===button)); toast(button.dataset.lang === "fr" ? "Interface française active." : "La traduction complète sera reliée aux dictionnaires du logiciel original."); }));
    $("dc-refresh-status").addEventListener("click", refreshProtocol);
    $("dc-job-close").addEventListener("click", () => { $("dc-job-card").hidden=true; state.jobId=null; });
    $("dc-plunger-calibrate").addEventListener("click", calibratePlunger);
    window.addEventListener('pagehide', () => {
      stopLivePolling();
      stopMonitorPolling();
      clearInterval(state.maintenanceTimer);
    });
    document.addEventListener('visibilitychange', () => { if (!document.hidden && state.maintenance?.active) heartbeatMaintenance(); });
    renderMaintenance({active:false});
    loadStatus().then(() => stopLivePolling());
    setInterval(loadStatus, 10000);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", install); else install();
})();
