#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

from flask import jsonify, request

CONFIG = Path("/etc/pincabos/updates.json")
STATE = Path("/var/lib/pincabos/updates/state.json")
WEBSTATE = Path("/run/pincabos-updates/update-web-state.json")
LOGFILE = Path("/run/pincabos-updates/update-web.log")
BACKUPS = Path("/opt/pincabos/backups/updates")
VERSION_FILES = [
    Path("/opt/pincabos/config/version.json"),
    Path("/opt/pincabos/version.json"),
]

_LOCK = threading.Lock()


def _load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {} if default is None else default


def _save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _config():
    d = _load_json(CONFIG, {})
    return {
        "repository": d.get("repository", "PinCabOS/PinCabOS"),
        "channel": d.get("channel", "beta"),
    }



def _display_from_tag(value):
    value = str(value or "").strip()
    low = value.lower()

    if low.startswith("alpha2."):
        core = value.split("-", 1)[0]
        number = core.split(".", 1)[1]
        return f"Alpha 2.{number}"

    return value


def _engine_state():
    d = _load_json(STATE, {})
    installed = d.get("display_version") or _display_from_tag(d.get("installed_version", ""))
    if not installed:
        for p in VERSION_FILES:
            j = _load_json(p, {})
            if j.get("version"):
                installed = j.get("version")
                break
    if not installed:
        installed = "unknown"

    last_backup = d.get("last_backup", "")

    cfg = _config()
    return {
        "repository": cfg["repository"],
        "channel": cfg["channel"],
        "installed_version": installed,
        "last_backup": last_backup,
    }


def _read_log_tail(limit=200000):
    try:
        txt = LOGFILE.read_text(encoding="utf-8", errors="replace")
        if len(txt) > limit:
            txt = txt[-limit:]
        return txt
    except Exception:
        return ""


def _pid_alive(pid):
    # PINCABOS_ROOT_PID_ALIVE_V1
    try:
        pid = int(pid)
        if pid <= 0:
            return False
        os.kill(pid, 0)
        return True
    except PermissionError:
        # Le WebApp tourne sous pinball alors que le runner
        # tourne sous root. EPERM signifie que le PID existe.
        return True
    except (ProcessLookupError, ValueError, TypeError):
        return False
    except Exception:
        return False


def _web_state():
    d = _load_json(WEBSTATE, {})
    if d.get("running") and not _pid_alive(d.get("pid", 0)):
        d["running"] = False
        d["status"] = "done" if d.get("last_exit_code", 0) == 0 else "error"
        _save_json(WEBSTATE, d)
    return d


def _append_log(line: str):
    LOGFILE.parent.mkdir(parents=True, exist_ok=True)
    with LOGFILE.open("a", encoding="utf-8") as f:
        f.write(line.rstrip() + "\n")



def _launch_reboot_delayed(
    delay_sec=4
):
    subprocess.Popen(
        [
            "sudo",
            "-n",
            "/usr/local/sbin/"
            "pincabos-update-web-runner",
            "reboot",
            "0",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

def _run_action(
    action,
    reboot_after=False
):
    flag = (
        "1"
        if reboot_after
        else "0"
    )

    subprocess.Popen(
        [
            "sudo",
            "-n",
            "/usr/local/sbin/"
            "pincabos-update-web-runner",
            action,
            flag,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

def _start_action(action: str, reboot_after: bool):
    st = _web_state()
    if st.get("running"):
        return False, "Une operation est deja en cours."
    t = threading.Thread(target=_run_action, args=(action, reboot_after), daemon=True)
    t.start()
    return True, "Operation demarree."


def _status_payload():
    info = _engine_state()
    ws = _web_state()
    payload = {
        **info,
        "running": bool(ws.get("running")),
        "status": ws.get("status", "idle"),
        "action": ws.get("action", ""),
        "started_at": ws.get("started_at", ""),
        "finished_at": ws.get("finished_at", ""),
        "last_exit_code": ws.get("last_exit_code"),
        "message": ws.get("message", ""),
        "reboot_after": bool(ws.get("reboot_after", False)),
        "reboot_recommended": bool(ws.get("reboot_recommended", False)),
        "reboot_scheduled": bool(ws.get("reboot_scheduled", False)),
        "log": _read_log_tail(),
        "log_path": str(LOGFILE),
    }
    return payload


def _updates_body_html():
    return r'''
<style>
:root{
  --pco-bg:#0a0610;
  --pco-panel:#11081a;
  --pco-panel-2:#170c22;
  --pco-border:#ff8a00;
  --pco-border-soft:rgba(255,138,0,.35);
  --pco-text:#fff3e6;
  --pco-dim:#d6b48e;
  --pco-accent:#ff9500;
  --pco-accent-2:#ffb347;
  --pco-ok:#4bd37b;
  --pco-warn:#ffc14d;
  --pco-bad:#ff6a6a;
  --pco-shadow:0 0 0 1px rgba(255,138,0,.15), 0 12px 36px rgba(0,0,0,.45);
}
.pco-up-wrap{
  max-width:none;
  margin:0 auto;
  padding:18px 16px 28px;
  color:var(--pco-text);
}
.pco-up-hero{
  display:flex;
  justify-content:space-between;
  align-items:center;
  gap:16px;
  padding:18px 20px;
  background:linear-gradient(180deg, rgba(255,149,0,.12), rgba(17,8,26,.92));
  border:1px solid var(--pco-border-soft);
  border-radius:16px;
  box-shadow:var(--pco-shadow);
  margin-bottom:16px;
}
.pco-up-hero h1{
  margin:0 0 6px 0;
  font-size:28px;
  line-height:1.1;
}
.pco-up-sub{
  color:var(--pco-dim);
  font-size:14px;
}
.pco-badge{
  display:inline-flex;
  align-items:center;
  gap:8px;
  padding:8px 12px;
  background:rgba(255,149,0,.13);
  border:1px solid var(--pco-border-soft);
  border-radius:999px;
  font-weight:700;
  white-space:nowrap;
}
.pco-cards{
  display:grid;
  grid-template-columns:repeat(4,minmax(0,1fr));
  gap:14px;
  margin-bottom:16px;
}
.pco-card{
  background:linear-gradient(180deg,var(--pco-panel),var(--pco-panel-2));
  border:1px solid var(--pco-border-soft);
  border-radius:16px;
  padding:16px;
  box-shadow:var(--pco-shadow);
  min-height:92px;
}
.pco-card-label{
  font-size:12px;
  color:var(--pco-dim);
  text-transform:uppercase;
  letter-spacing:.08em;
  margin-bottom:8px;
}
.pco-card-value{
  font-size:18px;
  font-weight:700;
  word-break:break-word;
}
.pco-grid{
  display:grid;
  grid-template-columns:1.08fr .92fr;
  gap:16px;
}
.pco-panel{
  background:linear-gradient(180deg,var(--pco-panel),var(--pco-panel-2));
  border:1px solid var(--pco-border-soft);
  border-radius:16px;
  box-shadow:var(--pco-shadow);
}
.pco-panel-head{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:12px;
  padding:16px 18px 10px;
}
.pco-panel-title{
  margin:0;
  font-size:18px;
}
.pco-panel-body{
  padding:0 18px 18px;
}
.pco-status-row{
  display:flex;
  align-items:center;
  flex-wrap:wrap;
  gap:10px;
  margin-bottom:14px;
}
.pco-status{
  display:inline-flex;
  align-items:center;
  gap:8px;
  padding:8px 12px;
  border-radius:999px;
  font-weight:700;
  border:1px solid var(--pco-border-soft);
}
.pco-status.idle{ background:rgba(255,149,0,.10); }
.pco-status.running{ background:rgba(255,193,77,.12); color:var(--pco-warn); }
.pco-status.success{ background:rgba(75,211,123,.12); color:var(--pco-ok); }
.pco-status.error{ background:rgba(255,106,106,.12); color:var(--pco-bad); }
.pco-msg{
  color:var(--pco-dim);
  font-size:13px;
}
.pco-progress{
  height:8px;
  border-radius:999px;
  overflow:hidden;
  background:rgba(255,255,255,.06);
  border:1px solid rgba(255,255,255,.06);
  margin:0 0 14px;
}
.pco-progress-bar{
  height:100%;
  width:0%;
  background:linear-gradient(90deg,var(--pco-accent),var(--pco-accent-2),var(--pco-accent));
  background-size:200% 100%;
  animation:pcoRun 1.1s linear infinite;
}
@keyframes pcoRun{
  0%{ width:18%; margin-left:-10%; background-position:0 0; }
  50%{ width:55%; margin-left:25%; background-position:50% 0; }
  100%{ width:22%; margin-left:100%; background-position:100% 0; }
}
.pco-actions{
  display:flex;
  flex-wrap:wrap;
  gap:10px;
  margin-bottom:14px;
}
.pco-btn{
  appearance:none;
  border:1px solid rgba(255,149,0,.55);
  background:linear-gradient(180deg,#ff9a12,#e77900);
  color:#1b0900;
  font-weight:800;
  border-radius:12px;
  padding:11px 14px;
  cursor:pointer;
  box-shadow:0 8px 18px rgba(0,0,0,.24);
}
.pco-btn:hover{ filter:brightness(1.06); }
.pco-btn:disabled{ opacity:.5; cursor:not-allowed; }
.pco-btn.alt{
  background:linear-gradient(180deg,#2b173b,#1b1028);
  color:var(--pco-text);
  border:1px solid rgba(255,255,255,.12);
}
.pco-btn.danger{
  background:linear-gradient(180deg,#ff9346,#ff6d2d);
}
.pco-opt{
  display:flex;
  align-items:center;
  gap:10px;
  padding:12px 14px;
  background:rgba(255,255,255,.03);
  border:1px solid rgba(255,255,255,.06);
  border-radius:12px;
}
.pco-opt input{ transform:scale(1.15); }
.pco-kv{
  display:grid;
  grid-template-columns:160px 1fr;
  gap:8px 12px;
  font-size:14px;
}
.pco-kv .k{ color:var(--pco-dim); }
.pco-log-tools{
  display:flex;
  justify-content:space-between;
  align-items:center;
  gap:10px;
  margin-bottom:10px;
}
.pco-mini{
  font-size:12px;
  color:var(--pco-dim);
}
.pco-log{
  background:#06030a;
  color:#ffe8d0;
  border:1px solid rgba(255,138,0,.30);
  border-radius:14px;
  padding:14px;
  min-height:360px;
  max-height:520px;
  overflow:auto;
  white-space:pre-wrap;
  font:13px/1.42 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  box-shadow:inset 0 0 0 1px rgba(255,255,255,.02);
}
.pco-note{
  margin-top:12px;
  color:var(--pco-dim);
  font-size:13px;
}
@media (max-width:1100px){
  .pco-cards{ grid-template-columns:repeat(2,minmax(0,1fr)); }
  .pco-grid{ grid-template-columns:1fr; }
}
@media (max-width:680px){
  .pco-cards{ grid-template-columns:1fr; }
  .pco-up-hero{ flex-direction:column; align-items:flex-start; }
}
</style>

<div class="pco-up-wrap">
  <div class="pco-up-hero">
    <div>
      <h1>PinCabOS Updates</h1>
      <div class="pco-up-sub">
        Nouveau moteur propre basé sur les <strong>GitHub Releases officielles</strong>.
      </div>
    </div>
    <div class="pco-badge">↻ Mise à jour & rollback sécurisés</div>
  </div>

  <div class="pco-cards">
    <div class="pco-card">
      <div class="pco-card-label">Repository</div>
      <div class="pco-card-value" id="pcoRepo">-</div>
    </div>
    <div class="pco-card">
      <div class="pco-card-label">Channel</div>
      <div class="pco-card-value" id="pcoChannel">-</div>
    </div>
    <div class="pco-card">
      <div class="pco-card-label">Installed version</div>
      <div class="pco-card-value" id="pcoInstalled">-</div>
    </div>
    <div class="pco-card">
      <div class="pco-card-label">Last backup</div>
      <div class="pco-card-value" id="pcoBackup">-</div>
    </div>
  </div>

  <div class="pco-grid">
    <section class="pco-panel">
      <div class="pco-panel-head">
        <h2 class="pco-panel-title">Contrôle des opérations</h2>
      </div>
      <div class="pco-panel-body">
        <div class="pco-status-row">
          <div class="pco-status idle" id="pcoStatus">Idle</div>
          <div class="pco-msg" id="pcoMsg">Prêt.</div>
        </div>

        <div class="pco-progress" id="pcoProgressWrap" style="display:none">
          <div class="pco-progress-bar"></div>
        </div>

        <div class="pco-actions">
          <button class="pco-btn" id="btnCheck">Vérifier les mises à jour</button>
          <button class="pco-btn" id="btnUpdate">Installer la mise à jour</button>
          <button class="pco-btn alt" id="btnRollback">Rollback</button>
          <button class="pco-btn danger" id="btnRebootNow" style="display:none">Redémarrer maintenant</button>
        </div>

        <label class="pco-opt">
          <input type="checkbox" id="rebootAfter">
          <span>Redémarrer automatiquement le cab après une <strong>mise à jour réussie</strong> si nécessaire.</span>
        </label>

        <div style="height:14px"></div>

        <div class="pco-kv">
          <div class="k">Action en cours</div><div id="pcoAction">-</div>
          <div class="k">Démarrée</div><div id="pcoStarted">-</div>
          <div class="k">Terminée</div><div id="pcoFinished">-</div>
          <div class="k">Code retour</div><div id="pcoExit">-</div>
          <div class="k">Log</div><div id="pcoLogPath">-</div>
        </div>

        <div class="pco-note">
          Après une mise à jour ou un rollback, un redémarrage peut être recommandé pour repartir sur une base propre.
        </div>
      </div>
    </section>

    <section class="pco-panel">
      <div class="pco-panel-head">
        <h2 class="pco-panel-title">Console des mises à jour</h2>
      </div>
      <div class="pco-panel-body">
        <div class="pco-log-tools">
          <div class="pco-mini">Zone de log défilante avec rafraîchissement automatique</div>
          <div style="display:flex; gap:8px; align-items:center;">
            <label class="pco-mini" style="display:flex;align-items:center;gap:6px;">
              <input type="checkbox" id="autoScroll" checked>
              Auto-scroll
            </label>
            <button class="pco-btn alt" id="btnClearView" type="button">Effacer l’affichage</button>
          </div>
        </div>
        <div class="pco-log" id="pcoLog"></div>
      </div>
    </section>
  </div>
</div>

<script>
(function(){
  const $ = (id) => document.getElementById(id);

  const el = {
    repo: $("pcoRepo"),
    channel: $("pcoChannel"),
    installed: $("pcoInstalled"),
    backup: $("pcoBackup"),
    status: $("pcoStatus"),
    msg: $("pcoMsg"),
    progressWrap: $("pcoProgressWrap"),
    action: $("pcoAction"),
    started: $("pcoStarted"),
    finished: $("pcoFinished"),
    exit: $("pcoExit"),
    logPath: $("pcoLogPath"),
    log: $("pcoLog"),
    rebootAfter: $("rebootAfter"),
    autoScroll: $("autoScroll"),
    btnCheck: $("btnCheck"),
    btnUpdate: $("btnUpdate"),
    btnRollback: $("btnRollback"),
    btnRebootNow: $("btnRebootNow"),
    btnClearView: $("btnClearView"),
  };

  let localClearMode = false;

  // PINCABOS_UPDATE_RECONNECT_UX_V1
  let expectedOfflineUntil = 0;

  function esc(s){
    return (s ?? "").toString();
  }

  function setStatus(cls, label){
    el.status.className = "pco-status " + cls;
    el.status.textContent = label;
  }

  function disableButtons(disabled){
    el.btnCheck.disabled = disabled;
    el.btnUpdate.disabled = disabled;
    el.btnRollback.disabled = disabled;
  }

  function render(data){
    el.repo.textContent = esc(data.repository || "-");
    el.channel.textContent = esc(data.channel || "-");
    el.installed.textContent = esc(data.installed_version || "-");
    el.backup.textContent = esc(data.last_backup || "-");
    el.action.textContent = esc(data.action || "-");
    el.started.textContent = esc(data.started_at || "-");
    el.finished.textContent = esc(data.finished_at || "-");
    el.exit.textContent = (data.last_exit_code === null || data.last_exit_code === undefined) ? "-" : esc(data.last_exit_code);
    el.logPath.textContent = esc(data.log_path || "-");
    el.rebootAfter.checked = !!data.reboot_after;

    if(data.running){
      setStatus("running", "Opération en cours");
      el.msg.textContent = data.message || "Traitement en cours...";
      el.progressWrap.style.display = "";
      disableButtons(true);
    } else {
      el.progressWrap.style.display = "none";
      disableButtons(false);

      if(data.status === "success"){
        setStatus("success", "Succès");
        el.msg.textContent = data.message || "Opération terminée avec succès.";
      } else if(data.status === "error"){
        setStatus("error", "Erreur");
        el.msg.textContent = data.message || "L’opération a échoué.";
      } else {
        setStatus("idle", "Prêt");
        el.msg.textContent = data.message || "Prêt.";
      }
    }

    if (!localClearMode) {
      el.log.textContent = esc(data.log || "");
      if(el.autoScroll.checked){
        el.log.scrollTop = el.log.scrollHeight;
      }
    }

    const showRebootNow = (!data.running) && !!data.reboot_recommended && !data.reboot_scheduled;
    el.btnRebootNow.style.display = showRebootNow ? "" : "none";
    el.btnRebootNow.disabled = data.running;
  }

  async function refreshState(){
    try{
      const res = await fetch("/api/updates/state", {cache:"no-store"});
      const data = await res.json();
      render(data);
    }catch(err){
      if(expectedOfflineUntil && Date.now() < expectedOfflineUntil){
        setStatus("running", "Mise à jour en cours");
        el.msg.textContent =
          "Connexion temporairement interrompue pendant l’installation. "
          + "PinCabOS continue la mise à jour et cette page se reconnectera automatiquement.";
      }else{
        setStatus("error", "Erreur");
        el.msg.textContent = "Impossible de lire l’état du module Updates.";
      }
    }
  }

  async function runAction(action){
    localClearMode = false;
    try{
      const res = await fetch("/api/updates/run", {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({
          action: action,
          reboot_after: el.rebootAfter.checked
        })
      });
      const data = await res.json();
      if(!res.ok || !data.ok){
        alert(data.error || "Operation refusee.");
        return;
      }

      if(action === "update" || action === "rollback"){
        expectedOfflineUntil = Date.now() + 120000;

        setStatus(
          "running",
          action === "update"
            ? "Mise à jour en cours"
            : "Rollback en cours"
        );

        el.msg.textContent =
          "L’opération a démarré. Le WebApp peut être indisponible quelques secondes.";
      }

      await refreshState();
    }catch(err){
      alert("Erreur lors du lancement de l’operation.");
    }
  }

  async function rebootNow(){
    if(!confirm("Redémarrer le cab maintenant ?")) return;
    try{
      const res = await fetch("/api/updates/reboot", {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({})
      });
      const data = await res.json();
      if(!res.ok || !data.ok){
        alert(data.error || "Reboot refuse.");
      } else {
        await refreshState();
      }
    }catch(err){
      alert("Erreur lors de la demande de reboot.");
    }
  }

  el.btnCheck.addEventListener("click", () => runAction("check"));
  el.btnUpdate.addEventListener("click", () => runAction("update"));
  el.btnRollback.addEventListener("click", () => {
    if(confirm("Confirmer le rollback ?")){
      runAction("rollback");
    }
  });
  el.btnRebootNow.addEventListener("click", rebootNow);

  el.btnClearView.addEventListener("click", () => {
    localClearMode = true;
    el.log.textContent = "";
  });

  refreshState();
  setInterval(refreshState, 2000);
})();
</script>
'''


def _page_response(page, title: str, body: str):
    try:
        return page(title, body)
    except TypeError:
        try:
            return page(title=title, body=body)
        except TypeError:
            return body


def _json_error(msg, code=400):
    return jsonify({"ok": False, "error": msg}), code


def _pincabos_updates_register(app, page):
    @app.get("/tools/updates")
    def pincabos_updates_page():
        return _page_response(page, "PinCabOS Updates", _updates_body_html())

    @app.get("/api/updates/state")
    def pincabos_updates_state():
        return jsonify(_status_payload())

    @app.post("/api/updates/run")
    def pincabos_updates_run():
        data = request.get_json(silent=True) or {}
        action = str(data.get("action", "")).strip().lower()
        reboot_after = bool(data.get("reboot_after", False))

        if action not in {"check", "update", "rollback"}:
            return _json_error("Action invalide.", 400)

        ok, msg = _start_action(action, reboot_after)
        if not ok:
            return _json_error(msg, 409)

        return jsonify({"ok": True, "message": msg})

    @app.post("/api/updates/reboot")
    def pincabos_updates_reboot():
        ws = _web_state()
        if ws.get("running"):
            return _json_error("Une operation est deja en cours.", 409)

        ws["reboot_scheduled"] = True
        ws["message"] = "Redemarrage du cab demande."
        _save_json(WEBSTATE, ws)
        _append_log("")
        _append_log("INFO     : Redemarrage demande depuis l'interface Web.")
        _append_log("INFO     : Redemarrage dans 4 secondes...")
        _launch_reboot_delayed(4)
        return jsonify({"ok": True})

# Interface publique attendue par tools.py
def register(app, page):
    return _pincabos_updates_register(app, page)
