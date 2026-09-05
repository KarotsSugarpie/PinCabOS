#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import threading
from datetime import datetime
from pathlib import Path

from flask import jsonify, request

CONFIG = Path("/etc/pincabos/updates.json")
STATE = Path("/var/lib/pincabos/updates/state.json")
WEBSTATE = Path("/run/pincabos-updates/update-web-state.json")
LOGFILE = Path("/run/pincabos-updates/update-web.log")
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


def _config():
    data = _load_json(CONFIG, {})
    return {
        "repository": data.get("repository", "PinCabOS/PinCabOS"),
        "channel": data.get("channel", "beta"),
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
    data = _load_json(STATE, {})
    installed = data.get("display_version") or _display_from_tag(data.get("installed_version", ""))
    if not installed:
        for path in VERSION_FILES:
            version = _load_json(path, {})
            if version.get("version"):
                installed = version.get("version")
                break
    if not installed:
        installed = "unknown"
    cfg = _config()
    return {
        "repository": cfg["repository"],
        "channel": cfg["channel"],
        "installed_version": installed,
        "last_backup": data.get("last_backup", ""),
    }


def _read_log_tail(limit=200000):
    try:
        text = LOGFILE.read_text(encoding="utf-8", errors="replace")
        return text[-limit:] if len(text) > limit else text
    except Exception:
        return ""


def _pid_alive(pid):
    try:
        pid = int(pid)
        if pid <= 0:
            return False
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except (ProcessLookupError, ValueError, TypeError):
        return False
    except Exception:
        return False


def _web_state():
    data = _load_json(WEBSTATE, {})
    if data.get("running") and not _pid_alive(data.get("pid", 0)):
        data["running"] = False
        data["status"] = "success" if data.get("last_exit_code") == 0 else "error"
        _save_json(WEBSTATE, data)
    return data


def _append_log(line: str):
    LOGFILE.parent.mkdir(parents=True, exist_ok=True)
    with LOGFILE.open("a", encoding="utf-8") as handle:
        handle.write(line.rstrip() + "\n")


def _launch_reboot_delayed():
    subprocess.Popen(
        ["sudo", "-n", "/usr/local/sbin/pincabos-update-web-runner", "reboot"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def _run_action(action):
    subprocess.Popen(
        ["sudo", "-n", "/usr/local/sbin/pincabos-update-web-runner", action],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def _start_action(action: str):
    state = _web_state()
    if state.get("running"):
        return False, "Une opération est déjà en cours."
    thread = threading.Thread(target=_run_action, args=(action,), daemon=True)
    thread.start()
    return True, "Opération démarrée."


def _status_payload():
    info = _engine_state()
    state = _web_state()
    return {
        **info,
        "running": bool(state.get("running")),
        "status": state.get("status", "idle"),
        "action": state.get("action", ""),
        "started_at": state.get("started_at", ""),
        "finished_at": state.get("finished_at", ""),
        "last_exit_code": state.get("last_exit_code"),
        "message": state.get("message", ""),
        "reboot_recommended": bool(state.get("reboot_recommended", False)),
        "reboot_scheduled": bool(state.get("reboot_scheduled", False)),
        "reboot_prompt": bool(state.get("reboot_prompt", False)),
        "progress_percent": int(state.get("progress_percent", 0) or 0),
        "progress_mode": state.get("progress_mode", "determinate"),
        "steps": state.get("steps", {}),
        "log": _read_log_tail(),
        "log_path": str(LOGFILE),
    }


def _updates_body_html():
    return r'''
<style>
:root{
  --pco-bg:#0a0610;--pco-panel:#11081a;--pco-panel-2:#170c22;
  --pco-border:#ff8a00;--pco-border-soft:rgba(255,138,0,.35);
  --pco-text:#fff3e6;--pco-dim:#d6b48e;--pco-accent:#ff9500;
  --pco-accent-2:#ffb347;--pco-ok:#4bd37b;--pco-warn:#ffc14d;
  --pco-bad:#ff6a6a;--pco-shadow:0 0 0 1px rgba(255,138,0,.15),0 12px 36px rgba(0,0,0,.45);
}
.pco-up-wrap{max-width:none;margin:0 auto;padding:18px 16px 28px;color:var(--pco-text)}
.pco-up-hero{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:18px 20px;background:linear-gradient(180deg,rgba(255,149,0,.12),rgba(17,8,26,.92));border:1px solid var(--pco-border-soft);border-radius:16px;box-shadow:var(--pco-shadow);margin-bottom:16px}
.pco-up-hero h1{margin:0 0 6px;font-size:28px;line-height:1.1}.pco-up-sub{color:var(--pco-dim);font-size:14px}
.pco-badge{display:inline-flex;align-items:center;gap:8px;padding:8px 12px;background:rgba(255,149,0,.13);border:1px solid var(--pco-border-soft);border-radius:999px;font-weight:700;white-space:nowrap}
.pco-cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-bottom:16px}.pco-card{background:linear-gradient(180deg,var(--pco-panel),var(--pco-panel-2));border:1px solid var(--pco-border-soft);border-radius:16px;padding:16px;box-shadow:var(--pco-shadow);min-height:92px}.pco-card-label{font-size:12px;color:var(--pco-dim);text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px}.pco-card-value{font-size:18px;font-weight:700;word-break:break-word}
.pco-grid{display:grid;grid-template-columns:1.08fr .92fr;gap:16px}.pco-panel{background:linear-gradient(180deg,var(--pco-panel),var(--pco-panel-2));border:1px solid var(--pco-border-soft);border-radius:16px;box-shadow:var(--pco-shadow)}.pco-panel-head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:16px 18px 10px}.pco-panel-title{margin:0;font-size:18px}.pco-panel-body{padding:0 18px 18px}
.pco-status-row{display:flex;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:14px}.pco-status{display:inline-flex;align-items:center;gap:8px;padding:8px 12px;border-radius:999px;font-weight:700;border:1px solid var(--pco-border-soft)}.pco-status.idle{background:rgba(255,149,0,.10)}.pco-status.running{background:rgba(255,193,77,.12);color:var(--pco-warn)}.pco-status.success{background:rgba(75,211,123,.12);color:var(--pco-ok)}.pco-status.error{background:rgba(255,106,106,.12);color:var(--pco-bad)}.pco-msg{color:var(--pco-dim);font-size:13px}
.pco-progress{height:12px;border-radius:999px;overflow:hidden;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.08);margin:0 0 6px;position:relative}.pco-progress-bar{height:100%;width:0;background:linear-gradient(90deg,var(--pco-accent),var(--pco-accent-2),var(--pco-accent));background-size:200% 100%;transition:width .35s ease;animation:pcoShimmer 1.1s linear infinite}.pco-progress-bar.indeterminate{width:42%!important;position:absolute;animation:pcoIndeterminate 1.15s ease-in-out infinite,pcoShimmer 1s linear infinite}.pco-progress-label{text-align:right;color:var(--pco-dim);font-size:12px;margin-bottom:14px}@keyframes pcoShimmer{to{background-position:200% 0}}@keyframes pcoIndeterminate{0%{left:-45%}100%{left:105%}}
.pco-steps{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:0 0 14px}.pco-step{border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.025);border-radius:12px;padding:10px;min-height:70px}.pco-step-name{font-size:12px;font-weight:800;margin-bottom:5px}.pco-step-state{font-size:12px;color:var(--pco-dim)}.pco-step.running{border-color:var(--pco-warn)}.pco-step.running .pco-step-state{color:var(--pco-warn)}.pco-step.go{border-color:rgba(75,211,123,.55);background:rgba(75,211,123,.07)}.pco-step.go .pco-step-state{color:var(--pco-ok);font-weight:800}.pco-step.nogo{border-color:rgba(255,106,106,.65);background:rgba(255,106,106,.08)}.pco-step.nogo .pco-step-state{color:var(--pco-bad);font-weight:800}
.pco-actions{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:14px}.pco-btn{appearance:none;border:1px solid rgba(255,149,0,.55);background:linear-gradient(180deg,#ff9a12,#e77900);color:#1b0900;font-weight:800;border-radius:12px;padding:11px 14px;cursor:pointer;box-shadow:0 8px 18px rgba(0,0,0,.24)}.pco-btn:hover{filter:brightness(1.06)}.pco-btn:disabled{opacity:.5;cursor:not-allowed}.pco-btn.alt{background:linear-gradient(180deg,#2b173b,#1b1028);color:var(--pco-text);border:1px solid rgba(255,255,255,.12)}.pco-btn.danger{background:linear-gradient(180deg,#ff9346,#ff6d2d)}
.pco-reboot{display:none;padding:14px;margin:0 0 14px;border:1px solid rgba(255,149,0,.45);border-radius:14px;background:rgba(255,149,0,.08)}.pco-reboot.show{display:block}.pco-reboot-q{font-weight:900;font-size:16px;margin-bottom:6px}.pco-reboot-sub{color:var(--pco-dim);font-size:12px;margin-bottom:10px}
.pco-kv{display:grid;grid-template-columns:160px 1fr;gap:8px 12px;font-size:14px}.pco-kv .k{color:var(--pco-dim)}.pco-log-tools{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:10px}.pco-mini{font-size:12px;color:var(--pco-dim)}.pco-log{background:#06030a;color:#ffe8d0;border:1px solid rgba(255,138,0,.30);border-radius:14px;padding:14px;min-height:360px;max-height:520px;overflow:auto;white-space:pre-wrap;font:13px/1.42 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;box-shadow:inset 0 0 0 1px rgba(255,255,255,.02)}.pco-note{margin-top:12px;color:var(--pco-dim);font-size:13px}
@media(max-width:1100px){.pco-cards{grid-template-columns:repeat(2,minmax(0,1fr))}.pco-grid{grid-template-columns:1fr}.pco-steps{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:680px){.pco-cards,.pco-steps{grid-template-columns:1fr}.pco-up-hero{flex-direction:column;align-items:flex-start}}
</style>

<div class="pco-up-wrap">
  <div class="pco-up-hero">
    <div><h1>PinCabOS Updates</h1><div class="pco-up-sub">Mise à jour transactionnelle protégée par <strong>HotFiles</strong>.</div></div>
    <div class="pco-badge">↻ Backup → Update → Restore → GO/NOGO</div>
  </div>

  <div class="pco-cards">
    <div class="pco-card"><div class="pco-card-label">Repository</div><div class="pco-card-value" id="pcoRepo">-</div></div>
    <div class="pco-card"><div class="pco-card-label">Channel</div><div class="pco-card-value" id="pcoChannel">-</div></div>
    <div class="pco-card"><div class="pco-card-label">Installed version</div><div class="pco-card-value" id="pcoInstalled">-</div></div>
    <div class="pco-card"><div class="pco-card-label">Last release backup</div><div class="pco-card-value" id="pcoBackup">-</div></div>
  </div>

  <div class="pco-grid">
    <section class="pco-panel">
      <div class="pco-panel-head"><h2 class="pco-panel-title">Contrôle des opérations</h2></div>
      <div class="pco-panel-body">
        <div class="pco-status-row"><div class="pco-status idle" id="pcoStatus">Prêt</div><div class="pco-msg" id="pcoMsg">Prêt.</div></div>

        <div class="pco-progress" id="pcoProgressWrap" style="display:none"><div class="pco-progress-bar" id="pcoProgressBar"></div></div>
        <div class="pco-progress-label" id="pcoProgressLabel" style="display:none">0%</div>

        <div class="pco-steps" id="pcoSteps">
          <div class="pco-step" data-step="backup"><div class="pco-step-name">1. Backup HotFiles</div><div class="pco-step-state">En attente</div></div>
          <div class="pco-step" data-step="update"><div class="pco-step-name">2. Mise à jour en ligne</div><div class="pco-step-state">En attente</div></div>
          <div class="pco-step" data-step="restore"><div class="pco-step-name">3. Restauration HotFiles</div><div class="pco-step-state">En attente</div></div>
          <div class="pco-step" data-step="final"><div class="pco-step-name">4. GO / NOGO</div><div class="pco-step-state">En attente</div></div>
        </div>

        <div class="pco-actions">
          <button class="pco-btn" id="btnCheck">Vérifier les mises à jour</button>
          <button class="pco-btn" id="btnUpdate">Installer la mise à jour</button>
          <button class="pco-btn alt" id="btnRollback">Rollback</button>
        </div>

        <div class="pco-reboot" id="pcoRebootPrompt">
          <div class="pco-reboot-q">Voulez-vous redémarrer le cabinet ?</div>
          <div class="pco-reboot-sub" id="pcoRebootSub">La mise à jour est terminée. Aucun redémarrage automatique ne sera effectué.</div>
          <div class="pco-actions" style="margin-bottom:0">
            <button class="pco-btn danger" id="btnRebootYes">Oui, redémarrer</button>
            <button class="pco-btn alt" id="btnRebootNo">Non, plus tard</button>
          </div>
        </div>

        <div class="pco-kv">
          <div class="k">Action en cours</div><div id="pcoAction">-</div>
          <div class="k">Démarrée</div><div id="pcoStarted">-</div>
          <div class="k">Terminée</div><div id="pcoFinished">-</div>
          <div class="k">Code retour</div><div id="pcoExit">-</div>
          <div class="k">Log</div><div id="pcoLogPath">-</div>
        </div>
        <div class="pco-note">Une mise à jour réussie restaure les HotFiles avant de proposer le redémarrage. Aucun reboot automatique.</div>
      </div>
    </section>

    <section class="pco-panel">
      <div class="pco-panel-head"><h2 class="pco-panel-title">Console des mises à jour</h2></div>
      <div class="pco-panel-body">
        <div class="pco-log-tools">
          <div class="pco-mini">Log live avec GO / NOGO et défilement automatique</div>
          <div style="display:flex;gap:8px;align-items:center"><label class="pco-mini" style="display:flex;align-items:center;gap:6px"><input type="checkbox" id="autoScroll" checked>Auto-scroll</label><button class="pco-btn alt" id="btnClearView" type="button">Effacer l’affichage</button></div>
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
    repo:$("pcoRepo"),channel:$("pcoChannel"),installed:$("pcoInstalled"),backup:$("pcoBackup"),
    status:$("pcoStatus"),msg:$("pcoMsg"),progressWrap:$("pcoProgressWrap"),progressBar:$("pcoProgressBar"),
    progressLabel:$("pcoProgressLabel"),action:$("pcoAction"),started:$("pcoStarted"),finished:$("pcoFinished"),
    exit:$("pcoExit"),logPath:$("pcoLogPath"),log:$("pcoLog"),autoScroll:$("autoScroll"),
    btnCheck:$("btnCheck"),btnUpdate:$("btnUpdate"),btnRollback:$("btnRollback"),btnClearView:$("btnClearView"),
    rebootPrompt:$("pcoRebootPrompt"),rebootSub:$("pcoRebootSub"),btnRebootYes:$("btnRebootYes"),btnRebootNo:$("btnRebootNo")
  };
  let localClearMode=false;
  let expectedOfflineUntil=0;
  const text=(v)=>(v??"").toString();

  function setStatus(cls,label){el.status.className="pco-status "+cls;el.status.textContent=label}
  function disableButtons(disabled){el.btnCheck.disabled=disabled;el.btnUpdate.disabled=disabled;el.btnRollback.disabled=disabled}

  function renderSteps(steps){
    document.querySelectorAll(".pco-step[data-step]").forEach((node)=>{
      const key=node.getAttribute("data-step");
      const data=(steps&&steps[key])||{};
      const status=data.status||"pending";
      node.className="pco-step "+(status==="pending"?"":status);
      const state=node.querySelector(".pco-step-state");
      let label="En attente";
      if(status==="running") label="EN COURS";
      if(status==="go") label="GO [OK]";
      if(status==="nogo") label="NOGO [X]";
      state.textContent=data.message ? label+" — "+data.message : label;
    });
  }

  function render(data){
    el.repo.textContent=text(data.repository||"-");el.channel.textContent=text(data.channel||"-");
    el.installed.textContent=text(data.installed_version||"-");el.backup.textContent=text(data.last_backup||"-");
    el.action.textContent=text(data.action||"-");el.started.textContent=text(data.started_at||"-");
    el.finished.textContent=text(data.finished_at||"-");el.exit.textContent=(data.last_exit_code===null||data.last_exit_code===undefined)?"-":text(data.last_exit_code);
    el.logPath.textContent=text(data.log_path||"-");renderSteps(data.steps||{});

    const percent=Math.max(0,Math.min(100,Number(data.progress_percent||0)));
    if(data.running){
      setStatus("running","Opération en cours");el.msg.textContent=data.message||"Traitement en cours...";
      el.progressWrap.style.display="";el.progressLabel.style.display="";disableButtons(true);
      if(data.progress_mode==="indeterminate"){
        el.progressBar.classList.add("indeterminate");el.progressBar.style.width="42%";el.progressLabel.textContent="Mise à jour en cours…";
      }else{
        el.progressBar.classList.remove("indeterminate");el.progressBar.style.width=percent+"%";el.progressLabel.textContent=Math.round(percent)+"%";
      }
    }else{
      disableButtons(false);el.progressBar.classList.remove("indeterminate");
      if(data.status==="success"){
        setStatus("success","GO [OK]");el.msg.textContent=data.message||"Opération terminée avec succès.";
        el.progressWrap.style.display="";el.progressLabel.style.display="";el.progressBar.style.width="100%";el.progressLabel.textContent="100% — GO";
      }else if(data.status==="error"){
        setStatus("error","NOGO [X]");el.msg.textContent=data.message||"L’opération a échoué.";
        el.progressWrap.style.display="";el.progressLabel.style.display="";el.progressBar.style.width="100%";el.progressLabel.textContent="NOGO";
      }else{
        setStatus("idle","Prêt");el.msg.textContent=data.message||"Prêt.";el.progressWrap.style.display="none";el.progressLabel.style.display="none";
      }
    }

    if(!localClearMode){el.log.textContent=text(data.log||"");if(el.autoScroll.checked) el.log.scrollTop=el.log.scrollHeight}

    const showPrompt=!data.running && !!data.reboot_prompt && !data.reboot_scheduled;
    el.rebootPrompt.classList.toggle("show",showPrompt);
    el.btnRebootYes.disabled=!!data.running;el.btnRebootNo.disabled=!!data.running;
    el.rebootSub.textContent=data.reboot_recommended
      ? "La mise à jour est terminée et PinCabOS recommande un redémarrage. Aucun redémarrage automatique ne sera effectué."
      : "La mise à jour est terminée. Aucun redémarrage automatique ne sera effectué.";
  }

  async function refreshState(){
    try{const res=await fetch("/api/updates/state",{cache:"no-store"});const data=await res.json();render(data)}
    catch(err){
      if(expectedOfflineUntil&&Date.now()<expectedOfflineUntil){setStatus("running","Mise à jour en cours");el.msg.textContent="Connexion temporairement interrompue pendant l’installation. PinCabOS continue la mise à jour et cette page se reconnectera automatiquement."}
      else{setStatus("error","Erreur");el.msg.textContent="Impossible de lire l’état du module Updates."}
    }
  }

  async function runAction(action){
    localClearMode=false;
    try{
      const res=await fetch("/api/updates/run",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:action})});
      const data=await res.json();if(!res.ok||!data.ok){alert(data.error||"Opération refusée.");return}
      if(action==="update"||action==="rollback"){
        expectedOfflineUntil=Date.now()+180000;
        setStatus("running",action==="update"?"Mise à jour en cours":"Rollback en cours");
        el.msg.textContent="L’opération a démarré. Le WebApp peut être indisponible quelques secondes.";
      }
      await refreshState();
    }catch(err){alert("Erreur lors du lancement de l’opération.")}
  }

  async function rebootNow(){
    try{const res=await fetch("/api/updates/reboot",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});const data=await res.json();if(!res.ok||!data.ok){alert(data.error||"Reboot refusé.");return}await refreshState()}
    catch(err){alert("Erreur lors de la demande de reboot.")}
  }

  async function dismissReboot(){
    try{const res=await fetch("/api/updates/reboot-dismiss",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});const data=await res.json();if(!res.ok||!data.ok){alert(data.error||"Action refusée.");return}await refreshState()}
    catch(err){alert("Erreur lors de l’enregistrement du choix.")}
  }

  el.btnCheck.addEventListener("click",()=>runAction("check"));
  el.btnUpdate.addEventListener("click",()=>runAction("update"));
  el.btnRollback.addEventListener("click",()=>{if(confirm("Confirmer le rollback ?")) runAction("rollback")});
  el.btnRebootYes.addEventListener("click",rebootNow);el.btnRebootNo.addEventListener("click",dismissReboot);
  el.btnClearView.addEventListener("click",()=>{localClearMode=true;el.log.textContent=""});
  refreshState();setInterval(refreshState,1500);
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
        if action not in {"check", "update", "rollback"}:
            return _json_error("Action invalide.", 400)
        ok, msg = _start_action(action)
        if not ok:
            return _json_error(msg, 409)
        return jsonify({"ok": True, "message": msg})

    @app.post("/api/updates/reboot")
    def pincabos_updates_reboot():
        state = _web_state()
        if state.get("running"):
            return _json_error("Une opération est déjà en cours.", 409)
        state["reboot_scheduled"] = True
        state["reboot_prompt"] = False
        state["message"] = "Redémarrage du cab demandé."
        _save_json(WEBSTATE, state)
        _append_log("")
        _append_log("INFO Redémarrage explicitement demandé depuis l'interface Web.")
        _append_log("INFO Redémarrage dans quelques secondes...")
        _launch_reboot_delayed()
        return jsonify({"ok": True})

    @app.post("/api/updates/reboot-dismiss")
    def pincabos_updates_reboot_dismiss():
        state = _web_state()
        if state.get("running"):
            return _json_error("Une opération est déjà en cours.", 409)
        state["reboot_prompt"] = False
        state["message"] = "Mise à jour terminée. Redémarrage reporté par l'utilisateur."
        _save_json(WEBSTATE, state)
        _append_log("INFO Redémarrage reporté par l'utilisateur.")
        return jsonify({"ok": True})


# Interface publique attendue par tools.py
def register(app, page):
    return _pincabos_updates_register(app, page)
