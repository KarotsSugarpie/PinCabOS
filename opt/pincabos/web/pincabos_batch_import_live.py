# PINCABOS_BATCH_IMPORT_QUEUE_V2
"""Persistent sequential Batch Import API and UI for PinCabOS."""
from __future__ import annotations

import contextvars
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Any

from flask import g, jsonify, request
from werkzeug.datastructures import FileStorage

import pincabos_batch_import_queue_v2 as queue

INTERNAL_HEADER = "X-PinCabOS-Batch-Import-Live"
INTERNAL_TARGET = "/tools/batch-import/run"
_IMPORT_JOB: contextvars.ContextVar[str | None] = contextvars.ContextVar("pincabos_batch_import_v2_job", default=None)
_PATCHED = False
_ORIGINAL_FILE_SAVE = FileStorage.save
_ORIGINAL_COPYTREE = shutil.copytree


def _safe_name(value: str, fallback: str) -> str:
    raw = Path(value or "").name.strip()
    raw = re.sub(r"[^A-Za-z0-9À-ÿ._ ()\-\[\]]+", "_", raw).strip(" ._")
    return raw or fallback


def _compact_html(value: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script\s*>", " ", value, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style\s*>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()[:4000]


def _job_update(job_id: str, label: str, current: str = "", event: str = "") -> None:
    def mutate(job: dict[str, Any]) -> None:
        if current:
            job["current_item"] = current
        queue.refresh_progress(job, label, current if current else None)
        if event:
            queue.add_event(job, event)
    queue.update_job(job_id, mutate)


def _install_observers() -> None:
    global _PATCHED
    if _PATCHED:
        return

    def observed_file_save(self: FileStorage, dst: Any, *args: Any, **kwargs: Any) -> Any:
        job_id = _IMPORT_JOB.get()
        if job_id:
            shown = _safe_name(str(getattr(self, "filename", "") or ""), "Package PinCabOS")
            _job_update(job_id, "Copie locale du package", shown, f"Copie locale : {shown}")
        return _ORIGINAL_FILE_SAVE(self, dst, *args, **kwargs)

    def observed_copytree(source: Any, destination: Any, *args: Any, **kwargs: Any) -> Any:
        job_id = _IMPORT_JOB.get()
        source_text = str(source).replace("\\", "/")
        if job_id and "/uploads/batch-import/" in source_text and "/extracts/" in source_text:
            name = Path(str(destination)).name or "Table"
            _job_update(job_id, "Installation de la table", name, f"Installation : {name}")
        return _ORIGINAL_COPYTREE(source, destination, *args, **kwargs)

    FileStorage.save = observed_file_save
    shutil.copytree = observed_copytree
    _PATCHED = True


def _save_one_upload(job_id: str, upload: FileStorage, index: int) -> dict[str, Any]:
    if not upload or not upload.filename:
        raise ValueError("Aucun package reçu.")
    shown = _safe_name(str(upload.filename), f"package-{index}.PinCabOS")
    suffix = Path(shown).suffix.lower()
    if suffix not in {".pincabos", ".zip"}:
        raise ValueError(f"Extension refusée pour {shown}. Utilise .PinCabOS ou .zip.")
    root = queue.upload_dir(job_id)
    root.mkdir(parents=True, exist_ok=True, mode=0o750)
    stored = root / f"{index:04d}--{shown}"
    temp = root / f".{stored.name}.{uuid.uuid4().hex}.upload"
    size = 0
    try:
        with temp.open("wb") as output:
            while True:
                chunk = upload.stream.read(2 * 1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                size += len(chunk)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp, stored)
    except Exception:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass
        raise

    with queue.state_lock(True):
        job = queue.load_job_unlocked(job_id)
        if not job:
            stored.unlink(missing_ok=True)
            raise RuntimeError("Job introuvable.")
        if str(job.get("state")) not in {"uploading", "running", "queued"} or job.get("uploads_complete"):
            stored.unlink(missing_ok=True)
            raise RuntimeError("Ce job n’accepte plus de packages.")
        total = int(job.get("total_archives", 0) or 0)
        if index < 1 or index > total:
            stored.unlink(missing_ok=True)
            raise ValueError("Position de package invalide.")
        uploads = [item for item in (job.get("uploads") or []) if int(item.get("index", 0) or 0) != index]
        uploads.append({
            "index": index,
            "name": shown,
            "path": str(stored),
            "size": size,
            "state": "queued",
            "detail": "Téléversé",
        })
        uploads.sort(key=lambda item: int(item.get("index", 0) or 0))
        job["uploads"] = uploads
        job["uploaded_archives"] = len(uploads)
        job["last_upload_at"] = queue.utc_now()
        job["accepting_uploads"] = True
        job["current_item"] = shown
        queue.add_event(job, f"Téléversement {len(uploads)}/{total} terminé : {shown}")
        queue.refresh_progress(job, f"Téléversement {len(uploads)}/{total}", shown)
        queue.save_job_unlocked(job)
        return job


_PAGE_UI = r'''
<!-- PINCABOS_BATCH_IMPORT_QUEUE_V2_PAGE -->
<script>
(() => {
  "use strict";
  if (window.__pcosBatchImportQueueV2Page) return;
  window.__pcosBatchImportQueueV2Page = true;

  const json = async (url, options = {}) => {
    const response = await fetch(url, {cache: "no-store", credentials: "same-origin", ...options});
    let data = {};
    try { data = await response.json(); } catch (_) {}
    if (!response.ok || data.ok === false) throw new Error(data.error || `HTTP ${response.status}`);
    return data;
  };

  const emit = (name, detail = {}) => window.dispatchEvent(new CustomEvent(name, {detail}));

  function form() {
    return document.getElementById("pco-batch-import-native") ||
      document.querySelector('form[action="/tools/batch-import/run"]');
  }

  function setMessage(text, bad = false) {
    const node = document.getElementById("pco-bi-message");
    if (node) {
      node.hidden = false;
      node.textContent = text;
      node.classList.toggle("bad", bad);
    }
  }

  function disable(target, value) {
    target.querySelectorAll('button[type="submit"],input[type="submit"]').forEach(button => {
      button.disabled = value;
      if (button.tagName === "BUTTON") button.textContent = value ? "Téléversement en file…" : "⚡ Lancer en arrière-plan";
    });
  }

  async function submitQueue(target) {
    const input = target.querySelector('input[name="archives"]');
    const files = Array.from(input?.files || []);
    if (!files.length) throw new Error("Choisis au moins un package .PinCabOS.");
    const conflict = target.querySelector('input[name="conflict_mode"]:checked')?.value || "skip";
    disable(target, true);
    setMessage(`Création de la file séquentielle pour ${files.length} package(s)…`);

    const created = await json("/api/batch-import/live/create", {
      method: "POST",
      headers: {"Content-Type": "application/json", "Accept": "application/json"},
      body: JSON.stringify({total: files.length, conflict_mode: conflict})
    });
    const jobId = created.job.id;
    emit("pcos-batch-import-started", created.job);

    try {
      for (let index = 0; index < files.length; index += 1) {
        const file = files[index];
        setMessage(`Téléversement ${index + 1}/${files.length} : ${file.name}`);
        emit("pcos-batch-import-uploading", {job_id: jobId, index: index + 1, total: files.length, name: file.name});
        const body = new FormData();
        body.append("archive", file, file.name);
        body.append("index", String(index + 1));
        await json(`/api/batch-import/live/upload/${encodeURIComponent(jobId)}`, {method: "POST", body});
        setMessage(`Traitement ${index + 1}/${files.length} : validation, extraction, manifest et installation…`);
        while (true) {
          await new Promise(resolve => window.setTimeout(resolve, 900));
          const packet = await json(`/api/batch-import/live/status/${encodeURIComponent(jobId)}`);
          const job = packet.job || {};
          if (["failed", "stopped", "cancelled"].includes(String(job.state || ""))) {
            throw new Error(job.error || `Le job s’est arrêté à ${index + 1}/${files.length}.`);
          }
          if (Number(job.processed_archives || 0) >= index + 1) break;
        }
      }
      const finished = await json(`/api/batch-import/live/finish/${encodeURIComponent(jobId)}`, {method: "POST"});
      setMessage(`Les ${files.length} packages sont en file. Le worker les importe maintenant un à la fois.`);
      emit("pcos-batch-import-started", finished.job);
    } catch (error) {
      try { await json(`/api/batch-import/live/stop/${encodeURIComponent(jobId)}`, {method: "POST"}); } catch (_) {}
      emit("pcos-batch-import-upload-failed", {job_id: jobId, error: error.message});
      throw error;
    } finally {
      disable(target, false);
    }
  }

  function wire() {
    const target = form();
    if (!target || target.dataset.pcosQueueV2 === "1") return;
    target.dataset.pcosQueueV2 = "1";
    target.addEventListener("submit", event => {
      event.preventDefault();
      event.stopImmediatePropagation();
      submitQueue(target).catch(error => {
        setMessage(`Lancement impossible : ${error.message}`, true);
        disable(target, false);
      });
    }, true);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire, {once: true});
  else wire();
})();
</script>
'''

_GLOBAL_UI = r'''
<!-- PINCABOS_BATCH_IMPORT_QUEUE_V2_GLOBAL -->
<style>
#pcos-biq-v2-card{display:none;width:100%;box-sizing:border-box;margin:7px 0 0;padding:9px 10px;border:1px solid rgba(145,76,229,.52);border-radius:10px;background:linear-gradient(135deg,rgba(35,18,55,.97),rgba(11,18,29,.97));box-shadow:0 8px 22px rgba(0,0,0,.26);color:#f3edff;font-size:12px;line-height:1.3}
#pcos-biq-v2-card[data-visible="1"]{display:block}
#pcos-biq-v2-card .pcos-biq-head{display:flex;align-items:center;gap:7px;min-width:0}
#pcos-biq-v2-card .pcos-biq-dot{width:8px;height:8px;flex:0 0 auto;border-radius:50%;background:#a77bff;box-shadow:0 0 0 4px rgba(167,123,255,.15)}
#pcos-biq-v2-card[data-active="1"] .pcos-biq-dot{animation:pcos-biq-pulse 1.1s ease-in-out infinite}
#pcos-biq-v2-card strong{font-size:12px;white-space:nowrap}
#pcos-biq-v2-card .pcos-biq-state{margin-left:auto;color:#d8c5ff;font-weight:800;white-space:nowrap}
#pcos-biq-v2-card .pcos-biq-detail{overflow:hidden;margin-top:5px;color:#ddd3ea;text-overflow:ellipsis;white-space:nowrap}
#pcos-biq-v2-card .pcos-biq-bar{height:5px;margin-top:7px;overflow:hidden;border-radius:99px;background:rgba(255,255,255,.11)}
#pcos-biq-v2-card .pcos-biq-fill{height:100%;width:0;border-radius:inherit;background:linear-gradient(90deg,#914ce5,#d99aff);transition:width .25s ease}
#pcos-biq-v2-card .pcos-biq-actions{display:flex;justify-content:flex-end;gap:6px;margin-top:7px}
#pcos-biq-v2-card button{border:0;border-radius:7px;padding:4px 8px;background:rgba(255,255,255,.1);color:#fff;cursor:pointer;font:inherit;font-weight:800}
#pcos-biq-v2-card .pcos-biq-stop{background:rgba(215,55,70,.25);color:#ffbec5}
@keyframes pcos-biq-pulse{50%{transform:scale(.65);opacity:.45}}
</style>
<script>
(() => {
  "use strict";
  if (window.__pcosBatchImportQueueV2Global) return;
  window.__pcosBatchImportQueueV2Global = true;
  const activeStates = new Set(["uploading", "queued", "running", "stopping"]);
  let current = null;

  const json = async (url, options = {}) => {
    const response = await fetch(url, {cache: "no-store", credentials: "same-origin", headers: {"Accept":"application/json"}, ...options});
    let data = {};
    try { data = await response.json(); } catch (_) {}
    if (!response.ok || data.ok === false) throw new Error(data.error || `HTTP ${response.status}`);
    return data;
  };

  function host() {
    return document.getElementById("pco-impexp-live-menu-slot") ||
      document.querySelector(".pco-impexp-live-menu-row") ||
      document.querySelector(".top-language-widget")?.parentElement ||
      null;
  }

  function card() {
    let node = document.getElementById("pcos-biq-v2-card");
    if (node) return node;
    const target = host();
    if (!target) return null;
    node = document.createElement("section");
    node.id = "pcos-biq-v2-card";
    node.setAttribute("aria-live", "polite");
    node.innerHTML = '<div class="pcos-biq-head"><i class="pcos-biq-dot"></i><strong>Batch Import</strong><span class="pcos-biq-state">—</span></div><div class="pcos-biq-detail">Aucun job.</div><div class="pcos-biq-bar"><div class="pcos-biq-fill"></div></div><div class="pcos-biq-actions"><button class="pcos-biq-stop" type="button">Stop</button><button class="pcos-biq-close" type="button">Fermer</button></div>';
    target.appendChild(node);
    node.querySelector(".pcos-biq-stop").addEventListener("click", stop);
    node.querySelector(".pcos-biq-close").addEventListener("click", dismiss);
    return node;
  }

  function dismissed(job) {
    return localStorage.getItem(`pcos-biq-v2-dismissed-${job.id}`) === "1";
  }

  function labelFor(state) {
    return ({uploading:"Téléversement",queued:"En file",running:"Import actif",stopping:"Arrêt demandé",completed:"Terminé",completed_with_warning:"Terminé avec avertissement",failed:"Erreur",stopped:"Arrêté",cancelled:"Annulé"})[state] || state || "—";
  }

  function render(job) {
    const node = card();
    if (!node) return;
    current = job || null;
    if (!job || dismissed(job)) { node.dataset.visible = "0"; return; }
    const state = String(job.state || "").toLowerCase();
    const active = activeStates.has(state);
    const progress = job.progress || {};
    const done = Number(progress.completed ?? job.processed_archives ?? 0);
    const total = Number(progress.total ?? job.total_archives ?? 0);
    const uploaded = Number(progress.uploaded ?? job.uploaded_archives ?? 0);
    const percent = Number(progress.percent || 0);
    const currentName = String(progress.current_item || job.current_item || "");
    const error = String(job.error || "");
    const counts = state === "uploading" ? `${uploaded}/${total} téléversé(s)` : `${done}/${total} traité(s)`;
    node.dataset.visible = "1";
    node.dataset.active = active ? "1" : "0";
    node.querySelector(".pcos-biq-state").textContent = labelFor(state);
    node.querySelector(".pcos-biq-detail").textContent = [progress.label, counts, currentName, error].filter(Boolean).join(" · ");
    node.querySelector(".pcos-biq-detail").title = node.querySelector(".pcos-biq-detail").textContent;
    node.querySelector(".pcos-biq-fill").style.width = `${Math.max(0, Math.min(100, percent))}%`;
    const stopButton = node.querySelector(".pcos-biq-stop");
    stopButton.hidden = !active;
    stopButton.disabled = state === "stopping";
    stopButton.textContent = state === "stopping" ? "Arrêt…" : "Stop";
    node.querySelector(".pcos-biq-close").hidden = active;
  }

  async function poll() {
    try {
      const history = await json("/api/batch-import/live/history");
      let job = null;
      if (history.active_job_id) {
        const status = await json(`/api/batch-import/live/status/${encodeURIComponent(history.active_job_id)}`);
        job = status.job || null;
      } else {
        job = (history.jobs || [])[0] || null;
      }
      render(job);
    } catch (_) {}
  }

  async function stop() {
    if (!current?.id) return;
    try {
      const data = await json(`/api/batch-import/live/stop/${encodeURIComponent(current.id)}`, {method:"POST"});
      render(data.job || current);
    } catch (_) {}
  }

  function dismiss() {
    if (!current?.id) return;
    localStorage.setItem(`pcos-biq-v2-dismissed-${current.id}`, "1");
    render(null);
  }

  const observer = new MutationObserver(() => { if (!document.getElementById("pcos-biq-v2-card")) card(); });
  observer.observe(document.documentElement, {childList:true, subtree:true});
  window.addEventListener("pcos-batch-import-started", poll);
  poll();
  window.setInterval(poll, 2000);
})();
</script>
'''

_SERVICE_WIDGET_FIX = r'''
<!-- PINCABOS_BATCH_SERVICE_WIDGET_FIX_V2 -->
<script>
(() => {
  "use strict";
  if (window.__pcosBatchServiceWidgetFixV2) return;
  window.__pcosBatchServiceWidgetFixV2 = true;
  /* PINCABOS_BATCH_SERVICE_WIDGET_FIX_V2_POLLER_DISABLED_V3 */
  return;
  const activeStates = new Set(["uploading", "queued", "running", "stopping"]);
  const cache = {import: null, export: null};

  async function json(url, options = {}) {
    const response = await fetch(url, {cache:"no-store", credentials:"same-origin", headers:{"Accept":"application/json"}, ...options});
    let data = {};
    try { data = await response.json(); } catch (_) {}
    if (!response.ok || data.ok === false) throw new Error(data.error || `HTTP ${response.status}`);
    return data;
  }

  function root() { return document.getElementById("pco-dashboard-batch-controls"); }
  function row(kind) { return root()?.querySelector(`[data-pco-batch-kind="${kind}"]`) || null; }
  function stateLabel(state) {
    return ({uploading:"Téléversement",queued:"En file",running:"Actif",stopping:"Arrêt demandé",completed:"Terminé",completed_with_warning:"Avertissement",failed:"Erreur",stopped:"Arrêté"})[state] || "Disponible";
  }

  function render(kind, job, error = "") {
    const target = row(kind);
    if (!target) return;
    const state = String(job?.state || "").toLowerCase();
    const active = Boolean(job?.id && activeStates.has(state));
    const progress = job?.progress || {};
    const status = target.querySelector("[data-pco-batch-state]");
    const detail = target.querySelector("[data-pco-batch-detail]");
    const open = target.querySelector("[data-pco-batch-open]");
    const stop = target.querySelector("[data-pco-batch-stop]");
    target.classList.toggle("is-active", active);
    if (status) status.textContent = error ? "API indisponible" : stateLabel(state);
    if (detail) {
      if (error) detail.textContent = error;
      else if (!job) detail.textContent = kind === "import" ? "Worker prêt · aucun job." : "Aucun job en cours.";
      else {
        const done = Number(progress.completed ?? job.processed_archives ?? job.completed_tables ?? 0);
        const total = Number(progress.total ?? job.total_archives ?? job.total_tables ?? 0);
        const name = String(progress.current_item || job.current_item || job.current_table || "");
        detail.textContent = [progress.label || stateLabel(state), total ? `${done}/${total}` : "", name, job.error || ""].filter(Boolean).join(" · ");
      }
      detail.title = detail.textContent;
    }
    if (open) open.textContent = active ? "Voir tâche" : "Ouvrir";
    if (stop) {
      stop.hidden = !active;
      stop.disabled = state === "stopping";
      stop.textContent = state === "stopping" ? "Arrêt…" : "Stop";
    }
  }

  async function refresh(kind) {
    try {
      const history = await json(`/api/batch-${kind}/live/history`);
      let job = null;
      if (history.active_job_id) {
        const status = await json(`/api/batch-${kind}/live/status/${encodeURIComponent(history.active_job_id)}`);
        job = status.job || null;
      } else job = (history.jobs || [])[0] || null;
      cache[kind] = job;
      render(kind, job);
    } catch (error) {
      cache[kind] = null;
      render(kind, null, `État indisponible : ${error.message}`);
    }
  }

  async function refreshAll() { await Promise.all([refresh("import"), refresh("export")]); }

  async function stop(kind, button) {
    const job = cache[kind];
    if (!job?.id) return;
    button.disabled = true;
    button.textContent = "Arrêt…";
    try {
      const data = await json(`/api/batch-${kind}/live/stop/${encodeURIComponent(job.id)}`, {method:"POST"});
      cache[kind] = data.job || job;
      render(kind, cache[kind]);
    } catch (error) {
      render(kind, job, `Arrêt impossible : ${error.message}`);
    }
  }

  document.addEventListener("click", event => {
    const refreshButton = event.target.closest?.("#pco-dashboard-batch-controls [data-pco-batch-refresh]");
    if (refreshButton) {
      event.preventDefault();
      event.stopImmediatePropagation();
      refreshAll();
      return;
    }
    const stopButton = event.target.closest?.("#pco-dashboard-batch-controls [data-pco-batch-stop]");
    if (stopButton) {
      event.preventDefault();
      event.stopImmediatePropagation();
      const kind = stopButton.closest("[data-pco-batch-kind]")?.dataset.pcoBatchKind;
      if (kind === "import" || kind === "export") stop(kind, stopButton);
    }
  }, true);

  const observer = new MutationObserver(() => {
    if (root()) {
      observer.disconnect();
      refreshAll();
    }
  });
  if (root()) refreshAll();
  else observer.observe(document.documentElement, {childList:true, subtree:true});
  window.setInterval(() => { if (root()) refreshAll(); }, 2500);
})();
</script>
'''


def _inject_before_body(body: str, fragment: str) -> str:
    index = body.lower().rfind("</body>")
    return body[:index] + fragment + body[index:] if index >= 0 else body + fragment


def register_batch_import_live(app: Any) -> None:
    if app.config.get("PINCABOS_BATCH_IMPORT_QUEUE_V2_REGISTERED"):
        return
    app.config["PINCABOS_BATCH_IMPORT_QUEUE_V2_REGISTERED"] = True
    queue.ensure_dirs()
    _install_observers()

    @app.before_request
    def pincabos_batch_import_v2_context() -> None:
        if request.method != "POST" or request.path != INTERNAL_TARGET:
            return
        if request.remote_addr not in {"127.0.0.1", "::1"}:
            return
        job_id = str(request.headers.get(INTERNAL_HEADER, "") or "")
        job = queue.load_job(job_id)
        if not job:
            return
        token = _IMPORT_JOB.set(job_id)
        g.pincabos_batch_import_v2_token = token

    @app.teardown_request
    def pincabos_batch_import_v2_clear(_error: BaseException | None = None) -> None:
        token = getattr(g, "pincabos_batch_import_v2_token", None)
        if token is not None:
            try:
                _IMPORT_JOB.reset(token)
            except (LookupError, ValueError):
                pass

    @app.route("/api/batch-import/live/create", methods=["POST"])
    def pincabos_batch_import_v2_create() -> Any:
        payload = request.get_json(silent=True) or {}
        try:
            job = queue.create_job(int(payload.get("total", 0) or 0), str(payload.get("conflict_mode", "skip") or "skip").lower())
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except RuntimeError as exc:
            return jsonify({"ok": False, "error": str(exc), "active_job_id": queue.active_job_id()}), 409
        return jsonify({"ok": True, "job": queue.public_job(job)}), 201

    @app.route("/api/batch-import/live/upload/<job_id>", methods=["POST"])
    def pincabos_batch_import_v2_upload(job_id: str) -> Any:
        try:
            index = int(request.form.get("index", "0") or 0)
            job = _save_one_upload(job_id, request.files.get("archive"), index)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except RuntimeError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 409
        except Exception as exc:
            return jsonify({"ok": False, "error": f"Téléversement impossible : {exc}"}), 500
        return jsonify({"ok": True, "job": queue.public_job(job)}), 202

    @app.route("/api/batch-import/live/finish/<job_id>", methods=["POST"])
    def pincabos_batch_import_v2_finish(job_id: str) -> Any:
        with queue.state_lock(True):
            job = queue.load_job_unlocked(job_id)
            if not job:
                return jsonify({"ok": False, "error": "Job introuvable."}), 404
            total = int(job.get("total_archives", 0) or 0)
            uploaded = len(job.get("uploads") or [])
            if uploaded != total:
                return jsonify({"ok": False, "error": f"Téléversement incomplet : {uploaded}/{total}."}), 409
            job["accepting_uploads"] = False
            if job.get("stop_requested"):
                job["state"] = "stopped"
                job["finished_at"] = queue.utc_now()
                queue.refresh_progress(job, "Arrêté avant traitement")
                queue.add_event(job, "File annulée avant le traitement.", "warning")
                queue.cleanup_uploads(job)
                queue.set_active_unlocked(None)
            else:
                job["uploads_complete"] = True
                if str(job.get("state")) == "uploading":
                    job["state"] = "queued"
                queue.refresh_progress(job, "Tous les packages ont été transmis")
                queue.add_event(job, "Tous les packages ont été transmis un par un.")
            queue.save_job_unlocked(job)
        return jsonify({"ok": True, "job": queue.public_job(job)}), 202

    @app.route("/api/batch-import/live/start", methods=["POST"])
    def pincabos_batch_import_v2_legacy_start() -> Any:
        files = [item for item in request.files.getlist("archives") if item and item.filename]
        if not files:
            return jsonify({"ok": False, "error": "Aucune archive reçue."}), 400
        try:
            job = queue.create_job(len(files), str(request.form.get("conflict_mode", "skip") or "skip").lower())
            for index, upload in enumerate(files, start=1):
                job = _save_one_upload(str(job["id"]), upload, index)
            with queue.state_lock(True):
                job = queue.load_job_unlocked(str(job["id"])) or job
                job["uploads_complete"] = True
                job["accepting_uploads"] = False
                if str(job.get("state")) == "uploading":
                    job["state"] = "queued"
                queue.refresh_progress(job, "En file pour le worker")
                queue.add_event(job, "Compatibilité V1 : requête globale reçue; le traitement reste séquentiel.", "warning")
                queue.save_job_unlocked(job)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except RuntimeError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 409
        except Exception as exc:
            return jsonify({"ok": False, "error": f"Préparation impossible : {exc}"}), 500
        return jsonify({"ok": True, "job": queue.public_job(job)}), 202

    @app.route("/api/batch-import/live/stop/<job_id>", methods=["POST"])
    def pincabos_batch_import_v2_stop(job_id: str) -> Any:
        with queue.state_lock(True):
            job = queue.load_job_unlocked(job_id)
            if not job:
                return jsonify({"ok": False, "error": "Job introuvable."}), 404
            state = str(job.get("state", ""))
            if state not in queue.ACTIVE_STATES:
                return jsonify({"ok": True, "job": queue.public_job(job)}), 200
            job["stop_requested"] = True
            if state in {"uploading", "queued"}:
                job["state"] = "stopped"
                job["finished_at"] = queue.utc_now()
                queue.refresh_progress(job, "Arrêté")
                queue.add_event(job, "File arrêtée avant le prochain package.", "warning")
                queue.cleanup_uploads(job)
                if queue.active_job_id_unlocked() == job_id:
                    queue.set_active_unlocked(None)
            else:
                job["state"] = "stopping"
                queue.refresh_progress(job, "Arrêt demandé")
                queue.add_event(job, "Arrêt demandé; le package actuel se termine proprement.", "warning")
            queue.save_job_unlocked(job)
        return jsonify({"ok": True, "job": queue.public_job(job)}), 202

    @app.route("/api/batch-import/live/status/<job_id>", methods=["GET"])
    def pincabos_batch_import_v2_status(job_id: str) -> Any:
        job = queue.load_job(job_id)
        if not job:
            return jsonify({"ok": False, "error": "Job introuvable."}), 404
        return jsonify({"ok": True, "job": queue.public_job(job)})

    @app.route("/api/batch-import/live/history", methods=["GET"])
    def pincabos_batch_import_v2_history() -> Any:
        jobs = [queue.public_job(job) for job in queue.list_jobs()]
        return jsonify({"ok": True, "active_job_id": queue.active_job_id(), "jobs": jobs})

    @app.route("/api/batch-import/live/worker", methods=["GET"])
    def pincabos_batch_import_v2_worker() -> Any:
        marker = queue.RUN_DIR / "worker-heartbeat.json"
        heartbeat = queue.read_json(marker, {})
        return jsonify({"ok": True, "heartbeat": heartbeat, "active_job_id": queue.active_job_id()})

    @app.after_request
    def pincabos_batch_import_v2_inject(response: Any) -> Any:
        if request.method != "GET":
            return response
        if "text/html" not in (response.headers.get("Content-Type") or "").lower():
            return response
        try:
            body = response.get_data(as_text=True)
        except Exception:
            return response
        changed = False
        if request.path.rstrip("/") in {"/tools/batch-import", "/tools/import-table"} and "PINCABOS_BATCH_IMPORT_QUEUE_V2_PAGE" not in body:
            body = _inject_before_body(body, _PAGE_UI)
            changed = True
        # PINCABOS_QUEUE_V2_GLOBAL_UI_DISABLED_V1
        # Le moteur, la file, le worker et la page Smart Import restent actifs.
        # Seule la deuxième carte globale concurrente est désactivée.
        if (
            app.config.get("PINCABOS_BATCH_IMPORT_QUEUE_V2_GLOBAL_UI", False)
            and "PINCABOS_BATCH_IMPORT_QUEUE_V2_GLOBAL" not in body
        ):
            body = _inject_before_body(body, _GLOBAL_UI)
            changed = True
        if "PINCABOS_BATCH_SERVICE_WIDGET_FIX_V2" not in body:
            body = _inject_before_body(body, _SERVICE_WIDGET_FIX)
            changed = True
        if changed:
            response.set_data(body)
            response.headers.pop("Content-Length", None)
        return response
