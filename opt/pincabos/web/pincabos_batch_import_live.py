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
        # PINCABOS_BATCH_IMPORT_UPLOAD_PAUSED_V31
        if str(job.get("state")) not in {"uploading", "running", "queued", "paused", "pausing"} or job.get("uploads_complete"):
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

  function progressBar() {
    let bar = document.getElementById("pco-bi-upbar");
    if (!bar) {
      let msg = document.getElementById("pco-bi-message");
      const host = (msg && msg.parentNode) || form();
      if (!host) return null;
      if (!msg) {
        msg = document.createElement("div");
        msg.id = "pco-bi-message";
        msg.style.cssText = "margin-top:10px;font-size:13px;color:#ffb347;";
        host.appendChild(msg);
      }
      const wrap = document.createElement("div");
      wrap.id = "pco-bi-upwrap";
      wrap.style.cssText = "margin-top:6px;height:14px;background:#2a2a2a;border-radius:7px;overflow:hidden;display:none;";
      bar = document.createElement("div");
      bar.id = "pco-bi-upbar";
      bar.style.cssText = "height:100%;width:0%;background:linear-gradient(90deg,#ff7a00,#ffb347);transition:width .2s;";
      wrap.appendChild(bar);
      if (msg.nextSibling) msg.parentNode.insertBefore(wrap, msg.nextSibling); else msg.parentNode.appendChild(wrap);
    }
    return bar;
  }

  function setProgress(fraction, label) {
    const bar = progressBar();
    if (!bar) return;
    const wrap = document.getElementById("pco-bi-upwrap");
    if (fraction === null) { if (wrap) wrap.style.display = "none"; return; }
    if (wrap) wrap.style.display = "block";
    bar.style.width = `${Math.round(fraction * 100)}%`;
    if (label) setMessage(label);
  }

  function uploadWithProgress(url, body, onProgress) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", url, true);
      xhr.responseType = "json";
      xhr.withCredentials = true;
      xhr.upload.onprogress = event => {
        if (event.lengthComputable && onProgress) onProgress(event.loaded, event.total);
      };
      xhr.onerror = () => reject(new Error("R\u00e9seau indisponible pendant le t\u00e9l\u00e9versement."));
      xhr.onload = () => {
        const data = xhr.response || {};
        if (xhr.status >= 200 && xhr.status < 300 && data.ok !== false) resolve(data);
        else reject(new Error((data && data.error) || `HTTP ${xhr.status}`));
      };
      xhr.send(body);
    });
  }

  function queuePanel(files) {
    let panel = document.getElementById("pco-bi-queue");
    if (!panel) {
      const wrap = document.getElementById("pco-bi-upwrap");
      const host = (wrap && wrap.parentNode) || form();
      panel = document.createElement("div");
      panel.id = "pco-bi-queue";
      panel.style.cssText = "margin-top:10px;font-size:13px;background:#181818;border:1px solid #333;border-radius:8px;padding:8px 10px;";
      host.appendChild(panel);
    }
    panel.innerHTML = "";
    const title = document.createElement("div");
    title.style.cssText = "font-weight:bold;color:#ffb347;margin-bottom:6px;";
    title.textContent = "File d’import — " + files.length + " package(s)";
    panel.appendChild(title);
    files.forEach((file, i) => {
      const row = document.createElement("div");
      row.id = "pco-bi-q-" + i;
      row.style.cssText = "display:flex;gap:8px;align-items:baseline;padding:2px 0;border-top:1px solid #262626;";
      const icon = document.createElement("span");
      icon.style.cssText = "width:1.4em;text-align:center;";
      icon.textContent = "\u23f3";
      const name = document.createElement("span");
      name.style.cssText = "color:#ddd;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:45%;";
      name.textContent = file.name;
      const status = document.createElement("span");
      status.style.cssText = "color:#999;flex:1;";
      status.textContent = "en attente (" + (file.size / (1024 * 1024)).toFixed(1) + " Mo)";
      row.appendChild(icon); row.appendChild(name); row.appendChild(status);
      panel.appendChild(row);
    });
    const worker = document.createElement("div");
    worker.id = "pco-bi-worker";
    worker.style.cssText = "margin-top:6px;padding-top:6px;border-top:1px solid #333;color:#ffb347;";
    worker.textContent = "";
    panel.appendChild(worker);
    return panel;
  }

  function setRow(i, icon, text, color) {
    const row = document.getElementById("pco-bi-q-" + i);
    if (!row) return;
    row.children[0].textContent = icon;
    row.children[2].textContent = text;
    row.children[2].style.color = color || "#999";
  }

  function setWorkerLine(text) {
    const el = document.getElementById("pco-bi-worker");
    if (el) el.textContent = text;
  }

  const ROW_STATES = {
    queued:   ["\u23f3", "en file d\u2019import", "#999"],
    running:  ["\u2699\ufe0f", "import en cours\u2026", "#ffb347"],
    done:     ["\u2705", "install\u00e9", "#7ec97e"],
    success:  ["\u2705", "install\u00e9", "#7ec97e"],
    warning:  ["\u26a0\ufe0f", "avertissement", "#ffd27e"],
    skipped:  ["\u26a0\ufe0f", "ignor\u00e9 (d\u00e9j\u00e0 install\u00e9)", "#ffd27e"],
    failed:   ["\u274c", "\u00e9chec", "#f08080"],
    error:    ["\u274c", "\u00e9chec", "#f08080"],
  };

  function applyPacketRows(job, files) {
    (job.uploads || []).forEach(item => {
      const i = Number(item.index || 0) - 1;
      if (i < 0 || i >= files.length) return;
      const meta = ROW_STATES[String(item.state || "")];
      if (meta) setRow(i, meta[0], meta[1] + (item.detail ? " \u2014 " + item.detail : ""), meta[2]);
    });
  }

  function pollWorker(jobId, files) {
    let ticks = 0;
    const timer = window.setInterval(async () => {
      ticks += 1;
      if (ticks > 2400) { window.clearInterval(timer); return; }
      let packet;
      try {
        packet = await json(`/api/batch-import/live/status/${encodeURIComponent(jobId)}`);
      } catch (_) { return; }
      const job = packet.job || {};
      const progress = job.progress || {};
      applyPacketRows(job, files);
      const bits = [];
      if (progress.label) bits.push(progress.label);
      if (progress.current_item) bits.push(progress.current_item);
      if (progress.total) bits.push(`${progress.completed || 0}/${progress.total} trait\u00e9s`);
      const counters = [];
      if (progress.successful) counters.push(progress.successful + " ok");
      if (progress.warnings) counters.push(progress.warnings + " avert.");
      if (progress.failed) counters.push(progress.failed + " \u00e9chec(s)");
      if (counters.length) bits.push(counters.join(", "));
      setWorkerLine("Worker : " + (bits.join(" \u2014 ") || job.state || ""));
      const state = String(job.state || "");
      if (["stopped", "failed", "completed", "finished", "done"].includes(state) || (progress.percent >= 100 && state !== "running" && state !== "queued")) {
        window.clearInterval(timer);
        setWorkerLine("Termin\u00e9 : " + (bits.join(" \u2014 ") || state));
        emit("pcos-batch-import-finished", job);
      }
    }, 2500);
  }

  async function submitQueue(target) {
    const input = target.querySelector('input[name="archives"]');
    const files = Array.from(input?.files || []);
    if (!files.length) throw new Error("Choisis au moins un package .PinCabOS.");
    const conflict = target.querySelector('input[name="conflict_mode"]:checked')?.value || "skip";
    disable(target, true);
    setProgress(0, null);
    queuePanel(files);
    setMessage(`Cr\u00e9ation de la file s\u00e9quentielle pour ${files.length} package(s)\u2026`);

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
        emit("pcos-batch-import-uploading", {job_id: jobId, index: index + 1, total: files.length, name: file.name});
        const body = new FormData();
        body.append("archive", file, file.name);
        body.append("index", String(index + 1));
        const startedAt = Date.now();
        await uploadWithProgress(`/api/batch-import/live/upload/${encodeURIComponent(jobId)}`, body, (loaded, totalBytes) => {
          const seconds = Math.max((Date.now() - startedAt) / 1000, 0.2);
          const mbps = (loaded / (1024 * 1024)) / seconds;
          const pct = Math.round(100 * loaded / totalBytes);
          setProgress(loaded / totalBytes, `T\u00e9l\u00e9versement ${index + 1}/${files.length} : ${file.name} \u2014 ${pct}% (${mbps.toFixed(1)} Mo/s)`);
          setRow(index, "\u2b06\ufe0f", `envoi ${pct}% (${mbps.toFixed(1)} Mo/s)`, "#ffb347");
          emit("pcos-batch-import-upload-progress", {job_id: jobId, index: index + 1, total: files.length, loaded: loaded, total_bytes: totalBytes});
        });
        setProgress(null);
        const upSeconds = Math.max((Date.now() - startedAt) / 1000, 0.01);
        const upMbps = (file.size / (1024 * 1024)) / upSeconds;
        setRow(index, "\u2699\ufe0f", `envoy\u00e9 (${(file.size / (1024 * 1024)).toFixed(1)} Mo, ${upMbps.toFixed(1)} Mo/s) \u2014 analyse\u2026`, "#ffb347");
        setMessage(`Traitement ${index + 1}/${files.length} : ${file.name}\u2026`);
        while (true) {
          await new Promise(resolve => window.setTimeout(resolve, 900));
          const packet = await json(`/api/batch-import/live/status/${encodeURIComponent(jobId)}`);
          const job = packet.job || {};
          applyPacketRows(job, files);
          if (["failed", "stopped", "cancelled"].includes(String(job.state || ""))) {
            throw new Error(job.error || `Le job s\u2019est arr\u00eat\u00e9 \u00e0 ${index + 1}/${files.length}.`);
          }
          if (Number(job.processed_archives || 0) >= index + 1) break;
        }
        setRow(index, "\u23f3", "pr\u00e9par\u00e9 \u2014 en file d\u2019import", "#999");
      }
      const finished = await json(`/api/batch-import/live/finish/${encodeURIComponent(jobId)}`, {method: "POST"});
      setMessage(`Les ${files.length} package(s) sont en file. Le worker les importe un \u00e0 la fois \u2014 suivi ci-dessous.`);
      emit("pcos-batch-import-started", finished.job);
      pollWorker(jobId, files);
    } catch (error) {
      try { await json(`/api/batch-import/live/stop/${encodeURIComponent(jobId)}`, {method: "POST"}); } catch (_) {}
      emit("pcos-batch-import-upload-failed", {job_id: jobId, error: error.message});
      throw error;
    } finally {
      setProgress(null);
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

  console.info("PinCabOS upload-bar v2 actif");
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire, {once: true});
  else wire();
})();
</script>

<!-- PINCABOS_BATCH_RESUME_PANEL_V1 -->
<style>
/* PINCABOS_BATCH_RESUME_PANEL_V3 : le panneau reprend le langage visuel des
   cartes de la page (fond translucide, grands arrondis, marges aerees) au
   lieu du rectangle opaque qui detonnait. */
#pco-bi-resume{margin:16px 0;padding:16px 18px;border:1px solid rgba(255,255,255,.14);border-radius:16px;background:rgba(255,255,255,.035);font-size:13px}
#pco-bi-resume[data-floating="1"]{position:fixed;right:16px;bottom:16px;z-index:9998;width:min(340px,calc(100vw - 32px));background:rgba(24,20,32,.96);box-shadow:0 12px 34px rgba(0,0,0,.5)}
#pco-bi-resume h3{margin:0 0 10px;font-size:14px;font-weight:700;color:rgb(255,143,28);letter-spacing:.2px}
#pco-bi-resume .pco-r-detail{color:rgba(255,255,255,.72);margin-bottom:12px;line-height:1.45}
#pco-bi-resume .pco-r-bar{height:6px;border-radius:99px;background:rgba(255,255,255,.09);overflow:hidden;margin-bottom:14px}
#pco-bi-resume .pco-r-fill{height:100%;width:0;border-radius:inherit;background:linear-gradient(90deg,#ffb000,#ff7a00);transition:width .3s ease}
#pco-bi-resume .pco-r-actions{display:flex;gap:10px;flex-wrap:wrap}
#pco-bi-resume button{border:1px solid rgba(255,255,255,.14);border-radius:11px;padding:8px 16px;font:inherit;font-weight:700;cursor:pointer;background:rgba(255,255,255,.05);color:rgba(255,255,255,.9);transition:background .15s ease}
#pco-bi-resume button:hover{background:rgba(255,255,255,.11)}
#pco-bi-resume .pco-r-pause{border-color:rgba(255,176,0,.4);color:#ffd79b}
#pco-bi-resume .pco-r-resume{border-color:rgba(88,214,141,.42);color:#b9f5d0}
#pco-bi-resume .pco-r-stop{border-color:rgba(215,55,70,.42);color:#ffbec5}
#pco-bi-resume .pco-r-log{margin-top:14px;max-height:104px;overflow:auto;border-top:1px solid rgba(255,255,255,.09);padding-top:10px;color:rgba(255,255,255,.5);font-size:11.5px;line-height:1.6}
#pco-bi-resume .pco-r-log div{padding:1px 0}
#pco-bi-resume button[hidden]{display:none}
</style>
<script>
(() => {
  "use strict";
  if (window.__pcosBatchResumePanelV1) return;
  window.__pcosBatchResumePanelV1 = true;

  let current = null;

  async function api(url, options = {}) {
    const response = await fetch(url, {cache: "no-store", credentials: "same-origin",
      headers: {"Accept": "application/json"}, ...options});
    if (!response.ok && response.status !== 202) throw new Error(response.status);
    return response.json();
  }

  // Le suivi doit vivre AVEC la zone d'import, pas en tete de page.
  function anchor() {
    return document.getElementById("pco-bi-queue")
        || document.getElementById("pco-bi-upwrap")
        || document.querySelector("form[enctype]");
  }

  function panel() {
    let node = document.getElementById("pco-bi-resume");
    if (node) return node;
    node = document.createElement("div");
    node.id = "pco-bi-resume";
    node.hidden = true;
    node.innerHTML = '<h3>Transfert en cours</h3>'
      + '<div class="pco-r-detail">—</div>'
      + '<div class="pco-r-bar"><div class="pco-r-fill"></div></div>'
      + '<div class="pco-r-actions">'
      + '<button class="pco-r-pause" type="button">Pause</button>'
      + '<button class="pco-r-resume" type="button">Reprendre</button>'
      + '<button class="pco-r-stop" type="button">Arrêter</button>'
      + '</div>'
      + '<div class="pco-r-log"></div>';
    const ref = anchor();
    if (ref && ref.parentNode) {
      ref.parentNode.insertBefore(node, ref.nextSibling);
    } else {
      // Aucune zone d'import sur cette page : vignette discrete en bas a
      // droite, jamais un bloc pose en haut du document.
      node.dataset.floating = "1";
      document.body.appendChild(node);
    }
    node.querySelector(".pco-r-pause").addEventListener("click", () => act("pause"));
    node.querySelector(".pco-r-resume").addEventListener("click", () => act("resume"));
    node.querySelector(".pco-r-stop").addEventListener("click", () => act("stop"));
    return node;
  }

  const LABELS = {uploading:"Téléversement", queued:"En file", running:"Import actif",
    stopping:"Arrêt demandé", paused:"En pause", completed:"Terminé",
    completed_with_warning:"Terminé avec avertissement", failed:"Interrompu",
    stopped:"Arrêté", cancelled:"Annulé"};

  async function act(action) {
    if (!current?.id) return;
    try {
      await api(`/api/batch-import/live/${action}/${encodeURIComponent(current.id)}`, {method: "POST"});
    } catch (_) {}
    refresh();
  }

  function render(data) {
    const job = data?.job || null;
    const node = panel();
    current = job;
    if (!job) { node.hidden = true; return; }

    const state = String(job.state || "").toLowerCase();
    const progress = job.progress || {};
    const total = Number(progress.total ?? job.total_archives ?? 0);
    const done = Number(progress.completed ?? job.processed_archives ?? 0);
    const remaining = Number(data.remaining || 0);
    const finished = ["completed", "completed_with_warning", "stopped", "cancelled"].includes(state);

    // Un travail termine sans reste n'a rien a reprendre : on n'encombre pas la page.
    if (finished && !remaining) { node.hidden = true; return; }

    node.hidden = false;
    node.querySelector("h3").textContent = `Transfert — ${LABELS[state] || state}`;
    node.querySelector(".pco-r-detail").textContent =
      [`${done}/${total} paquet(s) traité(s)`,
       remaining ? `${remaining} restant(s)` : "",
       String(progress.current_item || job.current_item || ""),
       String(job.error || "")].filter(Boolean).join(" · ");
    node.querySelector(".pco-r-fill").style.width =
      `${Math.max(0, Math.min(100, Number(progress.percent || 0)))}%`;

    const active = ["uploading", "queued", "running"].includes(state);
    node.querySelector(".pco-r-pause").hidden = !active;
    const resumeButton = node.querySelector(".pco-r-resume");
    resumeButton.hidden = !(data.resumable || state === "paused");
    resumeButton.textContent = remaining ? `Reprendre (${remaining})` : "Reprendre";
    node.querySelector(".pco-r-stop").hidden = !(active || state === "paused");

    const log = node.querySelector(".pco-r-log");
    log.innerHTML = "";
    (job.events || []).slice(-8).forEach(event => {
      const line = document.createElement("div");
      line.textContent = `${String(event.at || "").slice(11, 19)} — ${event.message || ""}`;
      if (event.level === "warning") line.style.color = "#ffd27e";
      if (event.level === "error") line.style.color = "#f08080";
      log.appendChild(line);
    });
  }

  function reseat() {
    const node = document.getElementById("pco-bi-resume");
    const ref = anchor();
    if (!node || !ref || !ref.parentNode) return;
    if (node.dataset.floating === "1" || node.previousElementSibling !== ref) {
      delete node.dataset.floating;
      ref.parentNode.insertBefore(node, ref.nextSibling);
    }
  }

  async function refresh() {
    try {
      render(await api("/api/batch-import/live/active"));
      reseat();
    } catch (_) {}
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", refresh, {once: true});
  } else {
    refresh();
  }
  window.setInterval(refresh, 2500);
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
#pcos-biq-v2-card .pcos-biq-pause{background:rgba(255,176,0,.22);color:#ffdb9b}
#pcos-biq-v2-card .pcos-biq-resume{background:rgba(88,214,141,.22);color:#b9f5d0}
#pcos-biq-v2-card button[hidden]{display:none}
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
    node.innerHTML = '<div class="pcos-biq-head"><i class="pcos-biq-dot"></i><strong>Batch Import</strong><span class="pcos-biq-state">—</span></div><div class="pcos-biq-detail">Aucun job.</div><div class="pcos-biq-bar"><div class="pcos-biq-fill"></div></div><div class="pcos-biq-actions"><button class="pcos-biq-pause" type="button">Pause</button><button class="pcos-biq-resume" type="button">Reprendre</button><button class="pcos-biq-stop" type="button">Stop</button><button class="pcos-biq-close" type="button">Fermer</button></div>';
    target.appendChild(node);
    node.querySelector(".pcos-biq-pause").addEventListener("click", pause);
    node.querySelector(".pcos-biq-resume").addEventListener("click", resume);
    node.querySelector(".pcos-biq-stop").addEventListener("click", stop);
    node.querySelector(".pcos-biq-close").addEventListener("click", dismiss);
    return node;
  }

  function dismissed(job) {
    return localStorage.getItem(`pcos-biq-v2-dismissed-${job.id}`) === "1";
  }

  function labelFor(state) {
    return ({uploading:"Téléversement",queued:"En file",running:"Import actif",stopping:"Arrêt demandé",paused:"En pause",completed:"Terminé",completed_with_warning:"Terminé avec avertissement",failed:"Erreur",stopped:"Arrêté",cancelled:"Annulé"})[state] || state || "—";
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

    // PINCABOS_BATCH_PAUSE_UI_V1
    // Pause tant que le travail avance ; Reprendre des qu'il est en pause ou
    // interrompu avec des paquets restants (ceux deja importes ne sont pas
    // refaits).
    const pauseButton = node.querySelector(".pcos-biq-pause");
    const resumeButton = node.querySelector(".pcos-biq-resume");
    const paused = state === "paused";
    const resumable = paused || Boolean(job.resumable);
    pauseButton.hidden = !active || state === "stopping";
    resumeButton.hidden = !resumable;
    if (resumable && Number(job.remaining || 0) > 0) {
      resumeButton.textContent = `Reprendre (${Number(job.remaining)})`;
    } else {
      resumeButton.textContent = "Reprendre";
    }
    node.querySelector(".pcos-biq-close").hidden = active && !paused;
  }

  async function poll() {
    try {
      // PINCABOS_BATCH_PAUSE_UI_V1 : /active rattache la carte au travail en
      // cours OU en pause OU interrompu — sans lui, revenir sur la page de
      // transfert affichait un ecran vierge alors que l'import continuait.
      const active = await json("/api/batch-import/live/active");
      let job = active.job || null;
      if (job) {
        job.resumable = Boolean(active.resumable);
        job.remaining = Number(active.remaining || 0);
      } else {
        const history = await json("/api/batch-import/live/history");
        job = (history.jobs || [])[0] || null;
      }
      render(job);
    } catch (_) {}
  }

  async function pause() {
    if (!current?.id) return;
    try {
      const data = await json(`/api/batch-import/live/pause/${encodeURIComponent(current.id)}`, {method:"POST"});
      render(data.job || current);
    } catch (_) {}
  }

  async function resume() {
    if (!current?.id) return;
    try {
      const data = await json(`/api/batch-import/live/resume/${encodeURIComponent(current.id)}`, {method:"POST"});
      render(data.job || current);
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

    # PINCABOS_BATCH_FAILSAFE_ROUTES_V1
    @app.route("/api/batch-import/live/pause/<job_id>", methods=["POST"])
    def pincabos_batch_import_v2_pause(job_id: str) -> Any:
        job = queue.pause_job(job_id)
        if not job:
            return jsonify({"ok": False, "error": "Job introuvable."}), 404
        return jsonify({"ok": True, "job": queue.public_job(job)}), 202

    @app.route("/api/batch-import/live/resume/<job_id>", methods=["POST"])
    def pincabos_batch_import_v2_resume(job_id: str) -> Any:
        job = queue.resume_job(job_id)
        if not job:
            return jsonify({"ok": False, "error": "Job introuvable."}), 404
        remaining = sum(
            1 for item in (job.get("uploads") or [])
            if isinstance(item, dict) and str(item.get("state")) == "queued"
        )
        return jsonify({
            "ok": True,
            "remaining": remaining,
            "job": queue.public_job(job),
        }), 202


    # PINCABOS_BATCH_SKIP_ROUTE_V3
    @app.route("/api/batch-import/live/skip/<job_id>", methods=["POST"])
    def pincabos_batch_import_v3_skip(job_id: str) -> Any:
        before = queue.load_job(job_id)
        if not before:
            return jsonify({"ok": False, "error": "Job introuvable."}), 404

        error_item = next(
            (
                item
                for item in (before.get("uploads") or [])
                if isinstance(item, dict)
                and str(item.get("state", "")) == "error"
            ),
            None,
        )

        if str(before.get("state", "")) != queue.PAUSED_STATE:
            return jsonify({
                "ok": False,
                "error": "Le Batch doit être en pause avant Skip.",
                "job": queue.public_job(before),
            }), 409

        if error_item is None:
            return jsonify({
                "ok": False,
                "error": "Aucun package fautif à ignorer.",
                "job": queue.public_job(before),
            }), 409

        job = queue.skip_job(job_id)

        return jsonify({
            "ok": True,
            "job": queue.public_job(job or before),
        }), 202

    @app.route("/api/batch-import/live/active", methods=["GET"])
    def pincabos_batch_import_v2_active() -> Any:
        """Travail a reprendre en charge quand on (re)vient sur la page.

        Sans cela, quitter la page de transfert faisait perdre le suivi : on
        revenait sur un ecran vierge alors que l'import continuait.
        """
        job_id = queue.active_job_id()
        job = queue.load_job(job_id) if job_id else None

        if not job:
            # Rien d'actif : on propose le travail le plus recent qui reste
            # reprenable (en pause, ou interrompu avec des paquets restants).
            for candidate in reversed(queue.list_jobs()):
                state = str(candidate.get("state", ""))
                remaining = any(
                    isinstance(item, dict) and str(item.get("state")) in {"queued", "running", "error"}
                    for item in (candidate.get("uploads") or [])
                )
                if state == queue.PAUSED_STATE or (remaining and state not in {"completed", "completed_with_warning"}):
                    job = candidate
                    break

        if not job:
            return jsonify({"ok": True, "job": None})

        state = str(job.get("state", ""))
        remaining = sum(
            1 for item in (job.get("uploads") or [])
            if isinstance(item, dict) and str(item.get("state")) in {"queued", "running", "error"}
        )
        return jsonify({
            "ok": True,
            "job": queue.public_job(job),
            "resumable": bool(remaining) and state != "running",
            "paused": state == queue.PAUSED_STATE,
            "remaining": remaining,
        })

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
