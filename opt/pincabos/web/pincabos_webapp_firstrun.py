# PinCabOS WebApp module: First Run wizard and reboot-gated GPU/screens workflow.
# Generated from the monolithic app.py refactor.
# The host app injects legacy shared helpers during register().
from __future__ import annotations

import glob
import html
import json
import os
import re
import shlex
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import zipfile
from datetime import datetime
from pathlib import Path

from flask import jsonify, redirect, request, send_file, session, url_for

ROUTES: list[tuple[str, dict, object]] = []
BEFORE_REQUESTS: list[object] = []
AFTER_REQUESTS: list[object] = []

def route(rule: str, **options):
    """Record a Flask route locally; register() attaches it to the host app."""
    def decorator(func):
        ROUTES.append((rule, options, func))
        return func
    return decorator

def before_request(func):
    BEFORE_REQUESTS.append(func)
    return func

def after_request(func):
    AFTER_REQUESTS.append(func)
    return func

def register(host_app, runtime_globals: dict):
    """Bind shared helpers once, then register module-owned routes unchanged."""
    protected = {'ROUTES', 'route', 'register', '__name__', '__file__', '__package__'}
    for key, value in runtime_globals.items():
        if key not in protected:
            globals()[key] = value
    # Publish moved helpers back to the host namespace for legacy core pages that
    # still call them (for example page() -> firstrun_load_cfg()).
    prefixes = ("audio_", "ssf_", "inputs_", "firstrun_", "pincabos_", "PINCABOS_", "AUDIO_")
    for key, value in list(globals().items()):
        if key.startswith(prefixes):
            runtime_globals[key] = value
    for before_func in BEFORE_REQUESTS:
        host_app.before_request(before_func)
    for after_func in AFTER_REQUESTS:
        host_app.after_request(after_func)
    for rule, options, view_func in ROUTES:
        host_app.add_url_rule(rule, endpoint=view_func.__name__, view_func=view_func, **options)



PINCABOS_FIRSTRUN_CFG = "/opt/pincabos/config/firstrun.json"
PINCABOS_FIRSTRUN_GPU_STATE = Path("/opt/pincabos/config/firstrun-gpu-state.json")


def firstrun_default_cfg():
    return {
        "show_popup": True,
        "network": False,
        "gpu": False,
        "screens": False,
    }


def firstrun_required_keys():
    return ["network", "gpu", "screens"]


def firstrun_boot_time_ts():
    try:
        for line in Path("/proc/stat").read_text(errors="replace").splitlines():
            if line.startswith("btime "):
                return float(line.split()[1])
    except Exception:
        pass
    return 0.0



def _firstrun_boot_id():
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text(
            encoding="ascii",
            errors="ignore",
        ).strip()
    except OSError:
        return ""


def _firstrun_gpu_probe():
    """Confirme qu’un pilote graphique utilisable est réellement lié."""
    try:
        lspci = subprocess.run(
            ["/usr/bin/lspci", "-nn"],
            text=True,
            capture_output=True,
            timeout=8,
            check=False,
        )
        gpu_lines = [
            line.strip()
            for line in (lspci.stdout or "").splitlines()
            if "VGA compatible controller" in line or "3D controller" in line
        ]
    except Exception:
        gpu_lines = []

    if not gpu_lines:
        return False, "Aucun contrôleur GPU détecté par lspci."

    folded = " ".join(gpu_lines).casefold()
    if "nvidia" in folded:
        try:
            probe = subprocess.run(
                [
                    "/usr/bin/nvidia-smi",
                    "--query-gpu=name,driver_version",
                    "--format=csv,noheader",
                ],
                text=True,
                capture_output=True,
                timeout=12,
                check=False,
            )
            if probe.returncode == 0 and (probe.stdout or "").strip():
                return True, (probe.stdout or "").strip().splitlines()[0]
            return False, (probe.stderr or probe.stdout or "nvidia-smi en erreur").strip()
        except Exception as exc:
            return False, f"nvidia-smi indisponible: {exc}"

    # AMD/Intel/autre: un pilote DRM lié constitue le minimum vérifiable.
    bound = []
    for driver in sorted(Path("/sys/class/drm").glob("card*/device/driver")):
        try:
            bound.append(driver.resolve().name)
        except OSError:
            pass
    if bound:
        return True, "Pilote DRM lié: " + ", ".join(sorted(set(bound)))
    return False, "GPU détecté, mais aucun pilote DRM lié."


def firstrun_gpu_state():
    marker = {}
    try:
        marker = json.loads(
            PINCABOS_FIRSTRUN_GPU_STATE.read_text(encoding="utf-8")
        )
        if not isinstance(marker, dict):
            marker = {}
    except Exception:
        marker = {}

    requested_boot = str(marker.get("boot_id") or "")
    current_boot = _firstrun_boot_id()
    has_update = bool(requested_boot)
    reboot_pending = bool(has_update and current_boot and requested_boot == current_boot)
    probe_ok, probe_detail = _firstrun_gpu_probe()
    ready = bool(has_update and not reboot_pending and probe_ok)

    if not has_update:
        state = "not_started"
        message = "Gestion GPU non confirmée. Lance l’étape GPU manuelle."
    elif reboot_pending:
        state = "reboot_pending"
        message = "Étape GPU enregistrée. Redémarrage obligatoire avant les écrans."
    elif ready:
        state = "ready"
        message = "GPU prêt après redémarrage: " + probe_detail
    else:
        state = "driver_error"
        message = "Redémarrage confirmé, mais le pilote GPU n’est pas prêt: " + probe_detail

    return {
        "ready": ready,
        "running": False,
        "state": state,
        "message": message,
        "has_update": has_update,
        "reboot_pending": reboot_pending,
        "boot_id": current_boot,
        "probe_ok": probe_ok,
        "probe_detail": probe_detail,
    }

def firstrun_gpu_status_text(state=None):
    state = state or firstrun_gpu_state()
    if not state.get("has_update"):
        return "Gestion GPU manuelle non détectée. Lance la gestion GPU manuelle, puis redémarre."
    if state.get("reboot_pending"):
        return "Gestion GPU manuelle détectée. Reboot requis avant de continuer vers les écrans."
    if state.get("ready"):
        return "Gestion GPU manuelle détectée et reboot confirmé. Les écrans peuvent être configurés."
    return "État GPU incomplet. Relance la gestion GPU manuelle puis redémarre."


def firstrun_load_cfg():
    from pathlib import Path
    import json

    cfg = firstrun_default_cfg()
    p = Path(PINCABOS_FIRSTRUN_CFG)

    if p.exists():
        try:
            data = json.loads(p.read_text(errors="replace"))
            if isinstance(data, dict):
                for key in cfg.keys():
                    if key in data:
                        cfg[key] = data[key]
        except Exception:
            pass

    return cfg


def firstrun_save_cfg(cfg):
    from pathlib import Path
    import json, subprocess

    clean = firstrun_default_cfg()
    for key in clean.keys():
        if key in cfg:
            clean[key] = bool(cfg[key])

    p = Path(PINCABOS_FIRSTRUN_CFG)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(clean, indent=2, ensure_ascii=False) + "\n")

    try:
        subprocess.run(["chown", "pinball:pinball", str(p)], timeout=5)
    except Exception:
        pass


def firstrun_card(key, icon, title, text, buttons, cfg, locked=False, lock_text=""):
    checked = "checked" if cfg.get(key) else ""
    done = "done" if cfg.get(key) else ""
    locked_cls = " locked" if locked else ""
    disabled = "disabled" if locked else ""
    lock_html = f'<div class="firstrun-lock">🔒 {esc(lock_text)}</div>' if locked and lock_text else ""

    return f"""
<div class="firstrun-step {done}{locked_cls}" style="position:relative;">
  <button class="button secondary firstrun-step-save"
          type="button"
          onclick="saveFirstRunStep('{esc(key)}')">
    💾 Sauvegarder
  </button>

  <div class="firstrun-left">
    <label class="firstrun-check">
      <input class="firstrun-step-check" type="checkbox" name="{esc(key)}" value="1" {checked} {disabled}>
      <span>{icon}</span>
    </label>
  </div>

  <div class="firstrun-step-body">
    <h3>{esc(title)}</h3>
    <p>{text}</p>
    {lock_html}
    <div class="firstrun-buttons">{buttons}</div>
    <pre id="firstrun-log-{esc(key)}" class="firstrun-log">En attente.</pre>
  </div>
</div>
"""


def firstrun_network_card(cfg, remote_ip, remote_url):
    checked = "checked" if cfg.get("network") else ""
    done = "done" if cfg.get("network") else ""

    return f"""
<div class="firstrun-step {done}" style="position:relative;">
  <button class="button secondary firstrun-step-save"
          type="button"
          onclick="saveFirstRunStep('network')">
    💾 Sauvegarder
  </button>

  <div class="firstrun-left">
    <label class="firstrun-check">
      <input class="firstrun-step-check" type="checkbox" name="network" value="1" {checked}>
      <span>🌐</span>
    </label>
  </div>

  <div class="firstrun-step-body">
    <h3>1 — Accès WebApp réseau</h3>
    <p>Adresse à utiliser depuis un autre appareil pour ouvrir la WebApp PinCabOS.</p>

    <div class="firstrun-network-remote">
      <div>Adresse remote WebApp</div>
      <div class="ip">{esc(remote_ip)}</div>
      <a href="{esc(remote_url)}" target="_blank">{esc(remote_url)}</a>
    </div>
  </div>
</div>
"""


@route("/first-run")
def firstrun_page():
    cfg = firstrun_load_cfg()
    gpu_state = firstrun_gpu_state()
    gpu_ready = bool(gpu_state.get("ready"))

    if cfg.get("gpu") and not gpu_ready:
        cfg["gpu"] = False
        cfg["screens"] = False

    remote_ip = get_ip()
    remote_url = "http://" + str(remote_ip or "127.0.0.1") + "/"

    keys = firstrun_required_keys()
    done = sum(1 for k in keys if cfg.get(k))
    pct = int((done / len(keys)) * 100)

    gpu_done = bool(cfg.get("gpu")) and gpu_ready
    screens_disabled_attr = "" if gpu_done else "disabled"
    screens_lock_text = "" if gpu_done else firstrun_gpu_status_text(gpu_state)

    body = """
<style>
body {
  background-image:
    linear-gradient(rgba(8,0,18,.74), rgba(8,0,18,.84)),
    url("/static/branding/firstrun-welcome-bg.png?v=firstrun") !important;
  background-position: center center, center center !important;
  background-size: cover, 58% auto !important;
  background-attachment: fixed, fixed !important;
  background-repeat: no-repeat, no-repeat !important;
}

.pincabos-nav,
.nav,
.nav-row,
.nav-pages,
.nav-tools-clean,
.brand-title,
.brand-subtitle {
  display: none !important;
}

.top {
  justify-content: center !important;
  min-height: 135px !important;
  align-items: center !important;
}

.brand-left {
  justify-content: center !important;
}

.firstrun-banner {
  position: static;
  transform: none;
  margin: 0;
  z-index: 10;
  flex: 1 1 auto;
  text-align: left;
}

.firstrun-banner img {
  max-width: min(42vw, 625px);
  width: 100%;
  height: auto;
  border-radius: 14px;
  box-shadow: 0 0 24px rgba(255,122,0,.24);
}

.firstrun-network-remote {
  margin-top: 12px;
  border: 1px solid rgba(0,255,120,.85);
  background: rgba(0,120,60,.30);
  border-radius: 14px;
  padding: 14px 16px;
  text-align: left;
  max-width: 460px;
  box-shadow: 0 0 20px rgba(0,255,120,.18);
}

.firstrun-network-remote .ip {
  font-size: 34px;
  font-weight: 900;
  color: #00ff78;
  text-shadow: 0 0 12px rgba(0,255,120,.55);
  margin: 6px 0;
}

.firstrun-network-remote a {
  color: var(--pco-appearance-accent, #ffb000);
  font-weight: 800;
  font-size: 18px;
}

.firstrun-hero {
  border: 1px solid rgba(255,176,0,.35);
  border-radius: 20px;
  padding: 18px;
  background: linear-gradient(135deg, rgba(255,122,0,.10), rgba(95,42,145,.18));
  box-shadow: 0 0 28px rgba(255,122,0,.13);
}

.firstrun-progress-wrap {
  margin: 16px 0;
  height: 20px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(0,0,0,.35);
  border: 1px solid rgba(255,176,0,.35);
}

.firstrun-progress {
  height: 100%;
  width: """ + str(pct) + """%;
  background: linear-gradient(90deg, #ff7a00, #ffb000);
  box-shadow: 0 0 14px rgba(255,176,0,.55);
}

.firstrun-list {
  display: grid;
  grid-template-columns: 1fr;
  gap: 14px;
}

.firstrun-step {
  display: flex;
  gap: 14px;
  position: relative;
  border: 1px solid rgba(255,70,70,.55);
  border-radius: 16px;
  padding: 14px;
  background: rgba(140,0,0,.16);
  box-shadow: 0 0 14px rgba(255,0,0,.12);
}

.firstrun-step.done {
  border-color: rgba(0,255,120,.95);
  background: rgba(0,180,80,.34);
  box-shadow: 0 0 24px rgba(0,255,120,.38);
}

.firstrun-step.locked {
  opacity: .72;
  filter: grayscale(.25);
}

.firstrun-lock {
  border: 1px solid rgba(255,176,0,.42);
  background: rgba(255,176,0,.10);
  border-radius: 12px;
  padding: 10px;
  margin: 10px 0;
  color: #ffcf66;
  font-weight: 800;
}

.firstrun-check {
  font-size: 32px;
  min-width: 62px;
  text-align: center;
}

.firstrun-check input {
  width: 22px;
  height: 22px;
  display: block;
  margin: 0 auto 8px auto;
}

.firstrun-step-body {
  width: 100%;
}

.firstrun-step-body h3 {
  margin: 0 0 6px 0;
  color: var(--pco-appearance-accent, #ffb000);
}

.firstrun-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin: 10px 0;
}

.firstrun-buttons button:disabled {
  opacity: .45;
  cursor: not-allowed;
}

.firstrun-step-save {
  position: absolute;
  top: 12px;
  right: 12px;
  font-size: 12px !important;
  padding: 6px 10px !important;
  z-index: 5;
}

.firstrun-log {
  min-height: 80px;
  max-height: 280px;
  overflow: auto;
  background: rgba(0,0,0,.42);
  border: 1px solid rgba(255,176,0,.18);
  border-radius: 12px;
  padding: 10px;
  white-space: pre-wrap;
}

.firstrun-warning {
  border: 1px solid rgba(255,176,0,.42);
  border-radius: 14px;
  padding: 12px;
  background: rgba(255,176,0,.08);
  margin-top: 12px;
}
</style>

<script>
document.addEventListener("DOMContentLoaded", function() {
  const top = document.querySelector(".top");
  if (top && !document.querySelector(".firstrun-banner")) {
    const banner = document.createElement("div");
    banner.className = "firstrun-banner";
    banner.innerHTML = '<img src="/static/branding/FBBanner.png?v=firstrun" alt="PinCabOS First Run">';
    top.prepend(banner);
  }
});
</script>

<div class="card firstrun-hero">
  <h1>🚀 Assistant Premier Démarrage PinCabOS</h1>
  <p>
    Nouvelle méthode PinCabOS : seulement les étapes essentielles après installation.
    Le réseau affiche l’adresse WebApp, le GPU doit être validé avant les écrans.
  </p>

  <div class="firstrun-progress-wrap">
    <div class="firstrun-progress" id="firstrun-progress-bar"></div>
  </div>

  <p><strong>Progression :</strong> <span id="firstrun-done-count">""" + str(done) + """</span> / """ + str(len(keys)) + """ étapes complétées — <span id="firstrun-pct">""" + str(pct) + """</span>%</p>

  <div class="firstrun-warning">
    ⚠️ Après la gestion GPU manuelle, redémarre le cab avant de cocher l’étape GPU et de passer à la détection des écrans.
  </div>
</div>

<form method="post" action="/first-run/save">

<div class="card">
  <h2>Checklist de configuration</h2>
  <div class="firstrun-list">
"""

    body += firstrun_network_card(cfg, remote_ip, remote_url)

    body += firstrun_card(
        "gpu", "🎮", "2 — GPU et pilotes",
        "Étape primordiale : détecte la carte vidéo, lance la gestion des pilotes GPU, puis redémarre PinCabOS avant de sauvegarder le crochet GPU.<br><strong>État GPU :</strong> " + esc(firstrun_gpu_status_text(gpu_state)),
        '<button class="button" type="button" onclick="firstrunAction(\'gpu\', \'gpu-detect\')">Détecter GPU</button>'
        '<button class="button secondary" type="button" onclick="firstrunGpuManual()">Mettre à jour pilotes GPU</button>',
        cfg
    )

    body += firstrun_card(
        "screens", "🖥️", "3 — Détection et assignation des écrans",
        "Détecte les écrans, modifie l’ordre X11/système, puis applique la configuration à VPX et VPinFE.",
        '<button class="button" type="button" ' + screens_disabled_attr + ' onclick="firstrunAction(\'screens\', \'screens-apply-all\')">Détecter et appliquer automatiquement</button>',
        cfg,
        locked=not gpu_done,
        lock_text=screens_lock_text
    )

    show_checked = "checked" if cfg.get("show_popup") else ""

    body += """
  </div>
</div>

<div class="card">
  <button class="button" type="submit">💾 Sauvegarder la checklist</button>
  <button class="button secondary" type="button" onclick="firstrunReboot()">🔄 Redémarrer</button>
  <label style="margin-left:12px;">
    <input id="firstrun-show-popup" type="checkbox" name="show_popup" value="1" """ + show_checked + """>
    Afficher automatiquement au démarrage
  </label>
</div>

</form>

<script>
async function firstrunReboot() {
  if (!confirm("Redémarrer PinCabOS maintenant ?")) return;

  try {
    const r = await fetch("/first-run/reboot", {method:"POST", cache:"no-store"});
    let data = {};
    try { data = await r.json(); } catch(e) {}

    if (!r.ok || data.ok === false) {
      alert("Erreur redémarrage: " + (data.error || ("HTTP " + r.status)));
      return;
    }

    document.body.innerHTML = "<div style='padding:40px;font-family:Arial;color:#ffb000;background:#080012;min-height:100vh;'><h1>🔄 Redémarrage PinCabOS...</h1><p>La WebApp sera temporairement indisponible.</p></div>";
  } catch(e) {
    alert("Erreur redémarrage: " + e);
  }
}

async function firstrunAction(step, action) {
  const log = document.getElementById("firstrun-log-" + step);
  if (log) log.textContent = "Exécution : " + action + "...";

  try {
    const r = await fetch("/first-run/action/" + action, {method:"POST"});
    const data = await r.json();
    if (log) log.textContent = data.output || data.error || "Terminé.";
  } catch(e) {
    if (log) log.textContent = "Erreur : " + e;
  }
}

async function firstrunGpuManual() {
  const log = document.getElementById("firstrun-log-gpu");
  if (log) log.textContent = "Lancement mise à jour pilotes GPU...";
  await fetch("/first-run/gpu-manual", {method:"POST"});
  firstrunPollUpdate("gpu");
}

async function firstrunPollUpdate(targetStep) {
  const step = targetStep || "gpu";
  const log = document.getElementById("firstrun-log-" + step);

  async function poll() {
    try {
      const r = await fetch("/first-run/gpu-manual-status?t=" + Date.now());
      const data = await r.json();

      if (log) {
        log.textContent =
          "Statut: " + (data.status || "idle") + "\\n" +
          "Cible: " + (data.target || "aucune") + "\\n" +
          "Progression: " + (data.progress || 0) + "%\\n\\n" +
          (data.log || data.message || "");
        log.scrollTop = log.scrollHeight;
      }

      if (data.status === "running") setTimeout(poll, 2000);
    } catch(e) {
      if (log) log.textContent = "Erreur progression : " + e;
    }
  }

  poll();
}

function saveFirstRunStep(step) {
  const cb = document.querySelector('input[name="' + step + '"]');
  if (cb) cb.checked = true;

  updateFirstRunProgressUI();

  const form = document.querySelector('form[action="/first-run/save"]');
  if (form) {
    form.submit();
  } else {
    window.location.reload();
  }
}

function updateFirstRunProgressUI() {
  const checks = Array.from(document.querySelectorAll(".firstrun-step-check"));
  const done = checks.filter(c => c.checked).length;
  const total = checks.length || 3;
  const pct = Math.round((done / total) * 100);

  const bar = document.getElementById("firstrun-progress-bar");
  const count = document.getElementById("firstrun-done-count");
  const pctEl = document.getElementById("firstrun-pct");
  const popup = document.getElementById("firstrun-show-popup");

  if (bar) bar.style.width = pct + "%";
  if (count) count.textContent = done;
  if (pctEl) pctEl.textContent = pct;

  if (popup) {
    if (done < total) {
      popup.checked = true;
      popup.disabled = true;
      popup.title = "Les 3 étapes doivent être complétées avant de désactiver le popup.";
    } else {
      popup.disabled = false;
      popup.title = "";
    }
  }
}

document.addEventListener("DOMContentLoaded", function() {
  document.querySelectorAll(".firstrun-step-check").forEach(c => {
    c.addEventListener("change", updateFirstRunProgressUI);
  });
  updateFirstRunProgressUI();
});
</script>
"""
    return page("First Run", body)


@route("/first-run/reboot", methods=["POST"])
def firstrun_reboot():
    try:
        reboot_cmd = "/sbin/reboot"
        if not Path(reboot_cmd).exists():
            reboot_cmd = "/usr/sbin/reboot"

        subprocess.Popen(
            ["/usr/bin/sudo", "-n", reboot_cmd],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return jsonify({"ok": True, "command": reboot_cmd})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@route("/first-run/action/<action>", methods=["POST"])
def firstrun_action(action):
    try:
        cfg = firstrun_load_cfg()

        if action == "gpu-detect":
            return jsonify({"ok": True, "output": gpu_info_text()})

        if action in ("screens-apply-all", "screens-detect", "screens-apply-vpx", "screens-apply-vpinfe") and not (cfg.get("gpu") and firstrun_gpu_state().get("ready")):
            return jsonify({
                "ok": False,
                "error": "Étape bloquée : lance la gestion GPU manuelle, redémarre PinCabOS, puis sauvegarde le crochet GPU avant les écrans."
            }), 403

        if action == "screens-apply-all":
            command = ["/usr/bin/sudo", "-n", str(pco_script("auto_detect_screens"))]
            try:
                completed = subprocess.run(
                    command,
                    text=True,
                    capture_output=True,
                    timeout=90,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                return jsonify({"ok": False, "error": "La détection des écrans a dépassé 90 secondes. L’étape n’a pas été validée."}), 504

            out = ((completed.stdout or "") + (completed.stderr or "")).strip()
            if completed.returncode != 0:
                return jsonify({
                    "ok": False,
                    "error": "Détection des écrans échouée; la checklist n’a pas été modifiée.",
                    "output": out or ("Code retour: " + str(completed.returncode)),
                }), 500

            vpx_out = pincabos_gpu_apply_config_to_vpx()
            vpinfe_out = pincabos_gpu_apply_config_to_vpinfe()

            cfg["screens"] = True
            if all(cfg.get(k) for k in firstrun_required_keys()):
                cfg["show_popup"] = False
            firstrun_save_cfg(cfg)

            extra = screens_layout_text()
            return jsonify({
                "ok": True,
                "output": out
                    + "\n\n===== VPX =====\n" + str(vpx_out)
                    + "\n\n===== VPinFE =====\n" + str(vpinfe_out)
                    + "\n\n===== screens.json =====\n" + extra
                    + "\n\nOK: étape Écrans complétée automatiquement."
            })

        if action == "screens-detect":
            out = run_cmd(["/usr/bin/sudo", str(pco_script("auto_detect_screens"))], timeout=60)
            extra = screens_layout_text()
            return jsonify({"ok": True, "output": out + "\\n\\n===== screens.json =====\\n" + extra})

        if action == "screens-apply-vpx":
            result = pincabos_gpu_apply_config_to_vpx()
            if isinstance(result, (list, tuple)):
                output = "Appliqué à VPX.\\n" + "\\n".join(str(x) for x in result)
            else:
                output = "Appliqué à VPX.\\n" + str(result)
            return jsonify({"ok": True, "output": output})

        if action == "screens-apply-vpinfe":
            result = pincabos_gpu_apply_config_to_vpinfe()
            if isinstance(result, (list, tuple)):
                output = "Appliqué à VPinFE.\\n" + "\\n".join(str(x) for x in result)
            else:
                output = "Appliqué à VPinFE.\\n" + str(result)
            return jsonify({"ok": True, "output": output})

        return jsonify({"ok": False, "error": "Action inconnue: " + action}), 404

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@route("/first-run/popup-disable", methods=["POST"])
def firstrun_popup_disable():
    cfg = firstrun_load_cfg()
    required = firstrun_required_keys()

    if cfg.get("gpu") and not firstrun_gpu_state().get("ready"):
        cfg["gpu"] = False
        cfg["screens"] = False

    if cfg.get("screens") and not cfg.get("gpu"):
        cfg["screens"] = False

    if not all(cfg.get(k) for k in required):
        cfg["show_popup"] = True
        firstrun_save_cfg(cfg)
        return jsonify({"ok": False, "error": "Les 3 étapes First Run doivent être complétées avant de désactiver le popup."}), 403

    cfg["show_popup"] = False
    firstrun_save_cfg(cfg)
    return jsonify({"ok": True})


@route("/first-run/save", methods=["POST"])
def firstrun_save():
    previous = firstrun_load_cfg()
    cfg = firstrun_default_cfg()
    required = firstrun_required_keys()

    # Network and GPU are confirmations; Screens is only unlocked by a successful
    # /first-run/action/screens-apply-all command, never by a manually ticked form.
    cfg["network"] = request.form.get("network") == "1"
    cfg["gpu"] = request.form.get("gpu") == "1"
    cfg["screens"] = bool(previous.get("screens"))

    if cfg.get("gpu") and not firstrun_gpu_state().get("ready"):
        cfg["gpu"] = False
        cfg["screens"] = False

    if cfg.get("screens") and not cfg.get("gpu"):
        cfg["screens"] = False

    if all(cfg.get(k) for k in required):
        cfg["show_popup"] = request.form.get("show_popup") == "1"
    else:
        cfg["show_popup"] = True

    firstrun_save_cfg(cfg)
    return redirect("/first-run")


@route("/first-run/gpu-manual", methods=["POST"])
def pincabos_firstrun_gpu_manual():
    marker = {
        "requested_at": datetime.now().isoformat(timespec="seconds"),
        "boot_id": _firstrun_boot_id(),
        "state": "reboot_pending",
    }
    PINCABOS_FIRSTRUN_GPU_STATE.parent.mkdir(parents=True, exist_ok=True)
    temporary = PINCABOS_FIRSTRUN_GPU_STATE.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(marker, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, PINCABOS_FIRSTRUN_GPU_STATE)

    cfg = firstrun_load_cfg()
    cfg["gpu"] = False
    cfg["screens"] = False
    cfg["show_popup"] = True
    firstrun_save_cfg(cfg)

    state = firstrun_gpu_state()
    return jsonify({"ok": True, **state})


@route("/first-run/gpu-manual-status")
def pincabos_firstrun_gpu_manual_status():
    return jsonify({"ok": True, **firstrun_gpu_state()})
