"""PinCabOS HotFiles backup/restore WebApp module."""
from __future__ import annotations

import hmac
import html
import json
import os
import re
import secrets
import subprocess
import threading
import zipfile
from datetime import datetime
from pathlib import Path

from flask import jsonify, redirect, request, send_file, session

ROUTES: list[tuple[str, dict, object]] = []


def route(rule: str, **options):
    def decorator(func):
        ROUTES.append((rule, options, func))
        return func
    return decorator


def register(host_app, runtime_globals: dict):
    protected = {"ROUTES", "route", "register", "__name__", "__file__", "__package__"}
    for key, value in runtime_globals.items():
        if key not in protected:
            globals()[key] = value
    for rule, options, view_func in ROUTES:
        host_app.add_url_rule(rule, endpoint=view_func.__name__, view_func=view_func, **options)


HELPER = Path("/opt/pincabos/tools/pincabos-backupcfg")
WORK_ROOT = Path("/var/tmp/pincabos-backupcfg")
LOCAL_ARCHIVE = Path("/home/pinball/usersettings/UserSettings.PCOSCFG")
LOG_ROOT = Path("/opt/pincabos/logs")
MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024
JOB_RE = re.compile(r"^[a-f0-9]{32}$")
ARCHIVE_RE = re.compile(r"^UserSettings-[0-9]{8}-[0-9]{6}\.PCOSCFG$")
CSRF_KEY = "pco_backupcfg_csrf_v1"
JOBS_KEY = "pco_backupcfg_jobs_v1"
_operation_lock = threading.Lock()


def _csrf() -> str:
    token = session.get(CSRF_KEY)
    if not isinstance(token, str) or len(token) < 32:
        token = secrets.token_urlsafe(48)
        session[CSRF_KEY] = token
        session.modified = True
    return token


def _csrf_ok() -> bool:
    supplied = str(request.headers.get("X-PCOSCFG-CSRF") or request.form.get("csrf") or "")
    expected = session.get(CSRF_KEY, "")
    return bool(supplied and expected and hmac.compare_digest(supplied, expected))


def _job_dir(job_id: str) -> Path:
    if not JOB_RE.fullmatch(job_id or ""):
        raise ValueError("Identifiant de tâche invalide.")
    return WORK_ROOT / job_id


def _remember_job(job_id: str, archive_name: str, mode: str, action: str, stamp: str) -> None:
    jobs = session.get(JOBS_KEY)
    if not isinstance(jobs, list):
        jobs = []
    jobs = [item for item in jobs if isinstance(item, dict) and item.get("id") != job_id]
    jobs.append({"id": job_id, "archive_name": archive_name, "mode": mode, "action": action, "stamp": stamp})
    session[JOBS_KEY] = jobs[-12:]
    session.modified = True


def _known_job(job_id: str) -> dict | None:
    if not JOB_RE.fullmatch(job_id or ""):
        return None
    jobs = session.get(JOBS_KEY)
    if not isinstance(jobs, list):
        return None
    for item in jobs:
        if isinstance(item, dict) and item.get("id") == job_id:
            return item
    return None


def _atomic_progress(job_dir: Path, archive_name: str, message: str) -> None:
    value = {
        "ok": False,
        "done": True,
        "percent": 100,
        "stage": "error",
        "message": message,
        "archive_name": archive_name,
        "log_path": "",
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    temp = job_dir / ".progress.json.tmp"
    temp.write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")
    os.chmod(temp, 0o600)
    os.replace(temp, job_dir / "progress.json")


def _worker(action: str, mode: str, job_id: str, stamp: str, archive_name: str) -> None:
    job_dir = _job_dir(job_id)
    try:
        command = ["/usr/bin/sudo", "-n", str(HELPER), action, job_id, stamp]
        result = subprocess.run(command, capture_output=True, text=True, timeout=7200, check=False)
        progress_path = job_dir / "progress.json"
        if result.returncode != 0 and not progress_path.is_file():
            detail = (result.stderr or result.stdout or f"code {result.returncode}").strip()[-500:]
            _atomic_progress(job_dir, archive_name, f"Échec du moteur Backup Config: {detail}")
    except Exception as exc:
        try:
            _atomic_progress(job_dir, archive_name, f"Échec du moteur Backup Config: {exc}")
        except OSError:
            pass
    finally:
        _operation_lock.release()


def _prepare_job(action: str, mode: str) -> tuple[dict, int]:
    if not HELPER.is_file():
        return {"ok": False, "error": f"Moteur absent: {HELPER}"}, 503
    if not _operation_lock.acquire(blocking=False):
        return {"ok": False, "error": "Une sauvegarde ou restauration est déjà en cours."}, 409
    try:
        job_id = secrets.token_hex(16)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        archive_name = f"UserSettings-{stamp}.PCOSCFG"
        WORK_ROOT.mkdir(parents=True, exist_ok=True, mode=0o755)
        job_dir = _job_dir(job_id)
        job_dir.mkdir(mode=0o700)
        os.chmod(job_dir, 0o700)
        _remember_job(job_id, archive_name, mode, action, stamp)
        return {
            "ok": True,
            "job_id": job_id,
            "archive_name": archive_name,
            "mode": mode,
            "action": action,
            "stamp": stamp,
        }, 202
    except Exception:
        _operation_lock.release()
        raise


def _launch_job(value: dict) -> None:
    thread = threading.Thread(
        target=_worker,
        args=(value["action"], value["mode"], value["job_id"], value["stamp"], value["archive_name"]),
        name=f"pincabos-backupcfg-{value['job_id'][:8]}",
        daemon=True,
    )
    try:
        thread.start()
    except Exception:
        _operation_lock.release()
        raise


def _cleanup_download(job_id: str, stamp: str) -> None:
    try:
        subprocess.run(
            ["/usr/bin/sudo", "-n", str(HELPER), "cleanup-download", job_id, stamp],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except Exception:
        pass


def _safe_log_tail(raw_path: str) -> str:
    try:
        path = Path(raw_path)
        if path.parent != LOG_ROOT or not path.name.endswith(".PCOSCFG.log") or path.is_symlink():
            return ""
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - 64 * 1024))
            return handle.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def _local_status() -> dict:
    if not LOCAL_ARCHIVE.is_file() or LOCAL_ARCHIVE.is_symlink():
        return {"exists": False, "path": str(LOCAL_ARCHIVE)}
    status = {
        "exists": True,
        "path": str(LOCAL_ARCHIVE),
        "size": LOCAL_ARCHIVE.stat().st_size,
        "modified_at": datetime.fromtimestamp(LOCAL_ARCHIVE.stat().st_mtime).astimezone().isoformat(timespec="seconds"),
        "archive_name": "",
        "created_at": "",
    }
    try:
        with zipfile.ZipFile(LOCAL_ARCHIVE, "r") as archive:
            value = json.loads(archive.read("pincabos-backupcfg-manifest.json").decode("utf-8"))
        status["archive_name"] = str(value.get("archive_name") or "")
        status["created_at"] = str(value.get("created_at") or "")
    except Exception:
        status["invalid"] = True
    return status


def _page_body() -> str:
    token = html.escape(_csrf(), quote=True)
    local = _local_status()
    local_json = html.escape(json.dumps(local, ensure_ascii=False), quote=True)
    local_label = "Aucune copie locale" if not local["exists"] else (
        f"{local.get('archive_name') or LOCAL_ARCHIVE.name} · {local['size'] / 1024:.1f} Kio"
    )
    local_disabled = " disabled" if not local["exists"] or local.get("invalid") else ""
    return r'''
<style>
.pcos-backupcfg{max-width:1180px;margin:0 auto;color:#f7f1ff}.pcos-backupcfg *{box-sizing:border-box}
.pcos-backupcfg .hero,.pcos-backupcfg .panel{border:1px solid rgba(216,158,255,.24);border-radius:20px;background:linear-gradient(180deg,rgba(30,14,53,.90),rgba(12,7,23,.94));box-shadow:0 15px 34px rgba(0,0,0,.25)}
.pcos-backupcfg .hero{padding:24px 27px;margin-bottom:18px;background:radial-gradient(circle at 90% 0,rgba(255,132,18,.15),transparent 34%),linear-gradient(180deg,rgba(30,14,53,.90),rgba(12,7,23,.94))}
.pcos-backupcfg h1{margin:0;color:#fff;font-size:clamp(28px,3vw,44px)}.pcos-backupcfg h1 span{color:#ff9b25}.pcos-backupcfg .hero p{color:#d9cce8;line-height:1.55;max-width:900px}
.pcos-backupcfg .grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.pcos-backupcfg .panel{padding:22px}.pcos-backupcfg h2{margin:0 0 8px;color:#fff}.pcos-backupcfg .muted{color:#c8b9d7;line-height:1.5}
.pcos-backupcfg .actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:18px}.pcos-backupcfg button,.pcos-backupcfg .back{display:inline-flex;align-items:center;justify-content:center;border:1px solid rgba(255,155,37,.75);border-radius:11px;padding:11px 15px;background:linear-gradient(135deg,#ff8b19,#b950db);color:#fff;font-weight:850;text-decoration:none;cursor:pointer}.pcos-backupcfg button.secondary,.pcos-backupcfg .back{background:rgba(255,255,255,.06);border-color:rgba(216,158,255,.42)}.pcos-backupcfg button.danger{background:linear-gradient(135deg,#a72d52,#d06522)}.pcos-backupcfg button:disabled{opacity:.45;cursor:not-allowed}
.pcos-backupcfg input[type=file]{width:100%;margin-top:13px;padding:12px;border:1px dashed rgba(216,158,255,.45);border-radius:12px;background:#0d0718;color:#eee}.pcos-backupcfg .local{padding:11px 13px;border-radius:11px;background:rgba(255,255,255,.045);color:#dccfea;font-family:ui-monospace,monospace;overflow-wrap:anywhere}
.pcos-backupcfg .warning{margin:18px 0 0;padding:13px 15px;border:1px solid rgba(255,158,29,.42);border-radius:12px;background:rgba(255,125,20,.08);color:#ffd29e;line-height:1.45}
.pcos-backupcfg .progress-panel{margin-top:18px}.pcos-backupcfg .bar{height:18px;overflow:hidden;border-radius:999px;background:#08040f;border:1px solid rgba(255,255,255,.13)}.pcos-backupcfg .fill{width:0;height:100%;background:linear-gradient(90deg,#8d43df,#ff8b19);transition:width .25s ease}.pcos-backupcfg .status{display:flex;justify-content:space-between;gap:16px;margin:10px 0;color:#e9dcf5}.pcos-backupcfg pre{min-height:180px;max-height:360px;overflow:auto;margin:0;padding:15px;border-radius:12px;background:#050208;color:#d9c7e8;border:1px solid rgba(255,255,255,.11);font:12px/1.5 ui-monospace,SFMono-Regular,Consolas,monospace;white-space:pre-wrap}.pcos-backupcfg .ok{color:#7dffb0}.pcos-backupcfg .bad{color:#ff899a}
@media(max-width:820px){.pcos-backupcfg .grid{grid-template-columns:1fr}.pcos-backupcfg .status{display:block}}
</style>
<main class="pcos-backupcfg" id="pcos-backupcfg" data-csrf="__CSRF__" data-local="__LOCAL_JSON__">
  <section class="hero">
    <a class="back" href="/tools">← Retour aux outils</a>
    <h1><span>Backup Config</span> PinCabOS</h1>
    <p>Crée une archive ZIP à compression maximale contenant uniquement les HotFiles du cab. L'arborescence, les permissions, les propriétaires et les empreintes SHA-256 sont conservés.</p>
    <div class="warning"><strong>Contenu sensible :</strong> le fichier PCOSCFG inclut les réglages réseau, les clés SSH et les secrets du cab. Conserve-le comme un mot de passe. <code>version.json</code>, les tables, ROMs, PuP-Packs et médias sont exclus.</div>
  </section>
  <div class="grid">
    <section class="panel">
      <h2>Sauvegarder</h2>
      <p class="muted">Le téléchargement porte le nom <code>UserSettings-AAAAMMJJ-HHMMSS.PCOSCFG</code>. La copie locale est toujours remplacée sans historique ni timestamp.</p>
      <div class="local"><strong>Copie locale :</strong><br>/home/pinball/usersettings/UserSettings.PCOSCFG<br><span id="pcos-local-label">__LOCAL_LABEL__</span></div>
      <div class="actions">
        <button id="pcos-backup-download">Backup Config — Télécharger</button>
        <button class="secondary" id="pcos-backup-local">Enregistrer seulement sur le cab</button>
      </div>
    </section>
    <section class="panel">
      <h2>Restaurer</h2>
      <p class="muted">L'archive est intégralement validée avant toute écriture. En cas d'échec, un rollback temporaire remet l'état précédent. Aucun service VPX, BGFX ou VPinFE n'est redémarré.</p>
      <input id="pcos-restore-file" type="file" accept=".pcoscfg,.PCOSCFG,application/octet-stream">
      <div class="actions">
        <button class="danger" id="pcos-restore-upload">Restaurer le fichier choisi</button>
        <button class="danger" id="pcos-restore-local"__LOCAL_DISABLED__>Restaurer la copie du cab</button>
      </div>
    </section>
  </div>
  <section class="panel progress-panel">
    <h2>Progression</h2>
    <div class="bar"><div class="fill" id="pcos-progress-fill"></div></div>
    <div class="status"><span id="pcos-progress-message">Prêt.</span><strong id="pcos-progress-percent">0 %</strong></div>
    <h2>Journal</h2>
    <pre id="pcos-log">Aucune opération en cours.</pre>
  </section>
</main>
<script>
(()=>{"use strict";
 const root=document.getElementById("pcos-backupcfg"),csrf=root.dataset.csrf;
 const fill=document.getElementById("pcos-progress-fill"),pct=document.getElementById("pcos-progress-percent"),message=document.getElementById("pcos-progress-message"),log=document.getElementById("pcos-log");
 const buttons=[...root.querySelectorAll("button")]; let timer=null;
 function localAvailable(){const value=JSON.parse(root.dataset.local);return value.exists&&!value.invalid;}
 function busy(value){buttons.forEach(button=>button.disabled=value||(button.id==="pcos-restore-local"&&!localAvailable()));}
 function show(data){const percent=Number(data.percent||0);fill.style.width=Math.max(0,Math.min(100,percent))+"%";pct.textContent=percent+" %";message.textContent=data.message||data.stage||"";message.className=data.done?(data.success?"ok":"bad"):"";if(data.log)log.textContent=data.log;log.scrollTop=log.scrollHeight;}
 async function jsonFetch(url,options={}){options.headers=Object.assign({"Accept":"application/json","X-PCOSCFG-CSRF":csrf},options.headers||{});const response=await fetch(url,options);const data=await response.json().catch(()=>({}));if(!response.ok||data.ok===false)throw Error(data.error||("HTTP "+response.status));return data;}
 async function poll(job,download){clearTimeout(timer);try{const data=await jsonFetch("/api/backupcfg/status/"+job);show(data);if(!data.done){timer=setTimeout(()=>poll(job,download),500);return;}if(data.success)root.dataset.local=JSON.stringify({exists:true,invalid:false});busy(false);if(data.success&&download){const link=document.createElement("a");link.href="/api/backupcfg/download/"+job;link.download=data.archive_name||"UserSettings.PCOSCFG";document.body.appendChild(link);link.click();link.remove();}}catch(error){show({done:true,success:false,percent:100,message:error.message});busy(false);}}
 async function startBackup(mode){busy(true);show({percent:1,message:"Démarrage du Backup Config…"});log.textContent="Préparation du moteur…";try{const data=await jsonFetch("/api/backupcfg/backup",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({mode})});poll(data.job_id,mode==="download");}catch(error){show({done:true,success:false,percent:100,message:error.message});busy(false);}}
 document.getElementById("pcos-backup-download").addEventListener("click",()=>startBackup("download"));
 document.getElementById("pcos-backup-local").addEventListener("click",()=>startBackup("local"));
 document.getElementById("pcos-restore-upload").addEventListener("click",async()=>{const input=document.getElementById("pcos-restore-file"),file=input.files[0];if(!file){show({done:true,success:false,percent:0,message:"Choisis d'abord un fichier .PCOSCFG."});return;}if(!confirm("Restaurer cette configuration sur le cab? Les HotFiles correspondants seront remplacés."))return;busy(true);show({percent:1,message:"Téléversement local de l'archive…"});log.textContent="Validation à venir…";const form=new FormData();form.append("archive",file);try{const data=await jsonFetch("/api/backupcfg/restore-upload",{method:"POST",body:form});poll(data.job_id,false);}catch(error){show({done:true,success:false,percent:100,message:error.message});busy(false);}});
 document.getElementById("pcos-restore-local").addEventListener("click",async()=>{if(!confirm("Restaurer /home/pinball/usersettings/UserSettings.PCOSCFG?"))return;busy(true);show({percent:1,message:"Démarrage de la restauration locale…"});log.textContent="Validation à venir…";try{const data=await jsonFetch("/api/backupcfg/restore-local",{method:"POST"});poll(data.job_id,false);}catch(error){show({done:true,success:false,percent:100,message:error.message});busy(false);}});
})();
</script>
'''.replace("__CSRF__", token).replace("__LOCAL_JSON__", local_json).replace(
        "__LOCAL_LABEL__", html.escape(local_label)
    ).replace("__LOCAL_DISABLED__", local_disabled)


@route("/backupcfg", methods=["GET"])
def backupcfg_page():
    return page("Backup Config", _page_body())


@route("/tools/backupcfg", methods=["GET"])
def backupcfg_tools_alias():
    return redirect("/backupcfg", code=302)


@route("/api/backupcfg/backup", methods=["POST"])
def backupcfg_start():
    if not _csrf_ok():
        return jsonify({"ok": False, "error": "Session Backup Config invalide. Recharge la page."}), 403
    payload = request.get_json(silent=True) or {}
    mode = str(payload.get("mode") or "download")
    if mode not in {"download", "local"}:
        return jsonify({"ok": False, "error": "Mode de sauvegarde invalide."}), 400
    action = "create-download" if mode == "download" else "create-local"
    value, status = _prepare_job(action, mode)
    if status == 202:
        _launch_job(value)
    return jsonify(value), status


@route("/api/backupcfg/restore-upload", methods=["POST"])
def backupcfg_restore_upload():
    if not _csrf_ok():
        return jsonify({"ok": False, "error": "Session Backup Config invalide. Recharge la page."}), 403
    upload = request.files.get("archive")
    if not upload or not upload.filename:
        return jsonify({"ok": False, "error": "Aucun fichier PCOSCFG reçu."}), 400
    if not upload.filename.lower().endswith(".pcoscfg"):
        return jsonify({"ok": False, "error": "Extension refusée: un fichier .PCOSCFG est requis."}), 400
    if request.content_length and request.content_length > MAX_UPLOAD_BYTES:
        return jsonify({"ok": False, "error": "Archive PCOSCFG trop volumineuse."}), 413
    value, status = _prepare_job("restore-upload", "restore-upload")
    if status != 202:
        return jsonify(value), status
    job_dir = _job_dir(value["job_id"])
    target = job_dir / "upload.PCOSCFG"
    try:
        upload.save(target)
        os.chmod(target, 0o600)
        if target.stat().st_size <= 0 or target.stat().st_size > MAX_UPLOAD_BYTES:
            raise ValueError("Taille de l'archive PCOSCFG refusée.")
    except Exception as exc:
        _atomic_progress(job_dir, value["archive_name"], f"Échec du téléversement: {exc}")
        _operation_lock.release()
        return jsonify({"ok": False, "error": f"Échec du téléversement: {exc}"}), 400
    _launch_job(value)
    return jsonify(value), status


@route("/api/backupcfg/restore-local", methods=["POST"])
def backupcfg_restore_local():
    if not _csrf_ok():
        return jsonify({"ok": False, "error": "Session Backup Config invalide. Recharge la page."}), 403
    if not LOCAL_ARCHIVE.is_file() or LOCAL_ARCHIVE.is_symlink():
        return jsonify({"ok": False, "error": "Aucune copie locale UserSettings.PCOSCFG disponible."}), 404
    value, status = _prepare_job("restore-local", "restore-local")
    if status == 202:
        _launch_job(value)
    return jsonify(value), status


@route("/api/backupcfg/status/<job_id>", methods=["GET"])
def backupcfg_status(job_id: str):
    job = _known_job(job_id)
    if job is None:
        return jsonify({"ok": False, "error": "Tâche Backup Config inconnue."}), 404
    path = _job_dir(job_id) / "progress.json"
    if not path.is_file() or path.is_symlink():
        return jsonify({
            "ok": True,
            "done": False,
            "percent": 1,
            "stage": "start",
            "message": "Démarrage du moteur…",
            "archive_name": job["archive_name"],
            "log": "",
        })
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return jsonify({"ok": True, "done": False, "percent": 1, "message": "Lecture de la progression…"})
    data["log"] = _safe_log_tail(str(data.get("log_path") or ""))
    # API request success is distinct from the operation's terminal result.
    data["success"] = data.get("ok")
    data["ok"] = True
    return jsonify(data)


@route("/api/backupcfg/download/<job_id>", methods=["GET"])
def backupcfg_download(job_id: str):
    job = _known_job(job_id)
    if job is None or job.get("action") != "create-download":
        return jsonify({"ok": False, "error": "Téléchargement Backup Config inconnu."}), 404
    archive_name = str(job.get("archive_name") or "")
    if not ARCHIVE_RE.fullmatch(archive_name):
        return jsonify({"ok": False, "error": "Nom de téléchargement invalide."}), 400
    path = _job_dir(job_id) / "download.PCOSCFG"
    progress_path = _job_dir(job_id) / "progress.json"
    try:
        state = json.loads(progress_path.read_text(encoding="utf-8"))
    except Exception:
        state = {}
    if not path.is_file() or path.is_symlink() or state.get("done") is not True or state.get("ok") is not True:
        return jsonify({"ok": False, "error": "Archive PCOSCFG pas encore disponible."}), 409
    response = send_file(path, as_attachment=True, download_name=archive_name, mimetype="application/octet-stream", conditional=True)
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.call_on_close(lambda: _cleanup_download(job_id, str(job.get("stamp") or "")))
    return response
