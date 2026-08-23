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


# PINCABOS_SMART_BATCH_STAGING_FIX_V31
def _save_raw_upload(
    job_id: str,
    stream: Any,
    filename: str,
    index: int,
    expected_size: int = 0,
) -> dict[str, Any]:
    # Écrit un upload application/octet-stream directement dans le staging.
    # Le multipart historique peut provoquer un second SpooledTemporaryFile
    # côté Werkzeug. Le chemin RAW évite ce deuxième spool.
    shown = _safe_name(str(filename or ""), f"package-{index}.PinCabOS")
    suffix = Path(shown).suffix.lower()
    if suffix not in {".pincabos", ".zip"}:
        raise ValueError(
            f"Extension refusée pour {shown}. Utilise .PinCabOS ou .zip."
        )

    root = queue.upload_dir(job_id)
    root.mkdir(parents=True, exist_ok=True, mode=0o750)

    stored = root / f"{index:04d}--{shown}"
    temp = root / f".{stored.name}.{uuid.uuid4().hex}.raw-upload"
    size = 0

    try:
        with temp.open("wb") as output:
            while True:
                chunk = stream.read(2 * 1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                size += len(chunk)

            output.flush()
            os.fsync(output.fileno())

        if expected_size > 0 and size != expected_size:
            raise IOError(
                f"Taille reçue invalide pour {shown}: "
                f"{size} octets reçus / {expected_size} attendus."
            )

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

        if (
            str(job.get("state"))
            not in {"uploading", "running", "queued", "paused", "pausing"}
            or job.get("uploads_complete")
        ):
            stored.unlink(missing_ok=True)
            raise RuntimeError("Ce job n’accepte plus de packages.")

        total = int(job.get("total_archives", 0) or 0)

        if index < 1 or index > total:
            stored.unlink(missing_ok=True)
            raise ValueError("Position de package invalide.")

        uploads = [
            item
            for item in (job.get("uploads") or [])
            if int(item.get("index", 0) or 0) != index
        ]

        uploads.append({
            "index": index,
            "name": shown,
            "path": str(stored),
            "size": size,
            "state": "queued",
            "detail": "Téléversé",
        })

        uploads.sort(
            key=lambda item: int(item.get("index", 0) or 0)
        )

        job["uploads"] = uploads
        job["uploaded_archives"] = len(uploads)
        job["last_upload_at"] = queue.utc_now()
        job["accepting_uploads"] = True
        job["current_item"] = shown

        queue.add_event(
            job,
            f"Téléversement {len(uploads)}/{total} terminé : {shown}",
        )
        queue.refresh_progress(
            job,
            f"Téléversement {len(uploads)}/{total}",
            shown,
        )
        queue.save_job_unlocked(job)

        return job


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
      /* PINCABOS_UPLOAD_SPEED_V1 — memes en-tetes que la version fetch(). */
      xhr.setRequestHeader("Accept", "application/json");
      xhr.setRequestHeader("Content-Type", "application/octet-stream");
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
    skipped:  ["\u23ed\ufe0f", "ignor\u00e9 automatiquement", "#ffd27e"],
    failed:   ["\u23ed\ufe0f", "erreur ignor\u00e9e — suite du Batch", "#f08080"],
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
      if (progress.successful) counters.push(progress.successful + " import\u00e9e(s)");
      if (progress.skipped) counters.push(progress.skipped + " ignor\u00e9e(s)");
      if (progress.failed) counters.push(progress.failed + " erreur(s) ignor\u00e9e(s)");
      if (progress.warnings) counters.push(progress.warnings + " avert.");
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

  /*
   * PINCABOS_BATCH_STAGING_GUARD_V35B
   *
   * Les File du navigateur n'existent que dans cette page.
   * Tant que N/N n'est pas televerse sur le cab, on avertit
   * avant navigation/reload/fermeture.
   */
  let pcosStagingTransfer = null;

  window.addEventListener(
    "beforeunload",
    event => {
      if (!pcosStagingTransfer) return;
      event.preventDefault();
      event.returnValue = "";
    }
  );

  async function submitQueue(target) {
    /* PINCABOS_BATCH_STAGE_ALL_V33 */
    /* PINCABOS_SMART_BATCH_STAGING_FIX_V31 */

    const input = target.querySelector(
      'input[name="archives"]'
    );

    const files = Array.from(
      input?.files || []
    );

    if (!files.length) {
      throw new Error(
        "Choisis au moins un package .PinCabOS."
      );
    }

    const conflict = "skip";
    const wait = ms => new Promise(
      resolve => window.setTimeout(resolve, ms)
    );

    const humanSize = bytes => {
      const value = Number(bytes || 0);
      if (value >= 1024 ** 3) {
        return `${(value / (1024 ** 3)).toFixed(2)} Go`;
      }
      return `${(value / (1024 ** 2)).toFixed(1)} Mo`;
    };

    /* PINCABOS_UPLOAD_SPEED_V1 */
    const humanDuree = secondes => {
      const value = Math.max(0, Math.round(Number(secondes) || 0));
      if (value < 60) return `${value} s`;
      const minutes = Math.floor(value / 60);
      if (minutes < 60) {
        return `${minutes} min ${String(value % 60).padStart(2, "0")} s`;
      }
      return `${Math.floor(minutes / 60)} h ${String(minutes % 60).padStart(2, "0")} min`;
    };

    async function sendOne(
      jobId,
      file,
      index,
      total
    ) {
      let lastError = null;

      for (
        let attempt = 1;
        attempt <= 5;
        attempt += 1
      ) {
        try {
          const url =
            `/api/batch-import/live/upload-raw/`
            + `${encodeURIComponent(jobId)}/${index}`
            + `?name=${encodeURIComponent(file.name)}`
            + `&size=${encodeURIComponent(String(file.size))}`;

          /*
           * PINCABOS_UPLOAD_SPEED_V1
           * fetch() ne rend compte de rien avant la fin du transfert.
           * XMLHttpRequest, si — c'est la seule raison de ce detour.
           * Le debit est moyenne depuis le debut du package : plus stable
           * qu'une mesure instantanee sur un reseau qui respire.
           */
          const debut = Date.now();
          let dernierAffichage = 0;

          await uploadWithProgress(url, file, (envoye, taille) => {
            const maintenant = Date.now();
            if (maintenant - dernierAffichage < 200 && envoye < taille) return;
            dernierAffichage = maintenant;

            const secondes = Math.max(0.3, (maintenant - debut) / 1000);
            const debit = envoye / secondes;
            const reste = debit > 0 ? (taille - envoye) / debit : 0;

            setProgress(
              taille ? envoye / taille : 0,
              `Téléversement ${index}/${total} : ${file.name} — `
              + `${humanSize(envoye)} / ${humanSize(taille)} · `
              + `${humanSize(debit)}/s`
              + (reste > 1 ? ` · ${humanDuree(reste)} restantes` : "")
            );
          });

          return;

        } catch (error) {
          lastError = error;

          setMessage(
            `Téléversement ${index}/${total} en erreur : `
            + `${file.name} (${humanSize(file.size)}). `
            + `Tentative ${attempt}/5.`,
            true
          );

          if (attempt < 5) {
            await wait(
              Math.min(15000, 2500 * attempt)
            );
          }
        }
      }

      throw new Error(
        `Téléversement ${index}/${total} impossible après 5 tentatives : `
        + `${lastError?.message || "erreur inconnue"}`
      );
    }

    disable(target, true);

    let jobId = "";
    let startIndex = 0;
    let stagingCompleted = false;

    let activePacket = null;

    try {
      activePacket = await json(
        "/api/batch-import/live/active"
      );
    } catch (_) {
      activePacket = null;
    }

    const activeJob = activePacket?.job || null;
    const activeState = String(
      activeJob?.state || ""
    ).toLowerCase();
    const activeTotal = Number(
      activeJob?.total_archives || 0
    );
    const activeUploaded = Number(
      activeJob?.uploaded_archives || 0
    );
    const activeComplete = Boolean(
      activeJob?.uploads_complete
    );

    if (
      activeJob?.id
      && ["uploading", "queued"].includes(activeState)
      && !activeComplete
    ) {
      if (activeTotal !== files.length) {
        disable(target, false);
        throw new Error(
          `Un staging incomplet existe déjà `
          + `(${activeUploaded}/${activeTotal}). `
          + `Sélection actuelle : ${files.length}. `
          + `Resélectionne exactement les mêmes `
          + `${activeTotal} packages.`
        );
      }

      const received = Array.from(
        activeJob.uploads || []
      )
        .filter(
          item => item
            && Number(item.index || 0) > 0
        )
        .sort(
          (a, b) =>
            Number(a.index || 0)
            - Number(b.index || 0)
        );

      let contiguous = 0;

      for (const item of received) {
        const idx = Number(item.index || 0);

        if (idx !== contiguous + 1) {
          break;
        }

        const local = files[idx - 1];
        const remoteName = String(
          item.name || ""
        );

        if (
          !local
          || local.name !== remoteName
        ) {
          disable(target, false);
          throw new Error(
            `La sélection ne correspond pas `
            + `au staging au package ${idx}. `
            + `Attendu : ${remoteName || "?"}. `
            + `Reçu : ${local?.name || "?"}.`
          );
        }

        contiguous = idx;
      }

      if (contiguous !== activeUploaded) {
        disable(target, false);
        throw new Error(
          `Staging non continu : `
          + `${contiguous}/${activeUploaded}.`
        );
      }

      jobId = String(activeJob.id);
      startIndex = contiguous;

      pcosStagingTransfer = {
        jobId,
        total: files.length
      };

      setMessage(
        `Reprise du téléversement : `
        + `${startIndex}/${files.length} déjà reçu(s). `
        + `Reprise au package ${startIndex + 1}.`
      );

      emit(
        "pcos-batch-import-started",
        activeJob
      );

    } else if (activeJob?.id) {
      disable(target, false);

      throw new Error(
        `Un Smart Batch est déjà présent `
        + `(état ${activeState || "inconnu"}).`
      );

    } else {
      setMessage(
        `Préparation de ${files.length} package(s). `
        + `Ne quitte pas cette page avant `
        + `${files.length}/${files.length} téléversés.`
      );

      const created = await json(
        "/api/batch-import/live/create",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Accept": "application/json"
          },
          body: JSON.stringify({
            total: files.length,
            conflict_mode: conflict
          })
        }
      );

      jobId = String(created.job.id);

      pcosStagingTransfer = {
        jobId,
        total: files.length
      };

      emit(
        "pcos-batch-import-started",
        created.job
      );
    }

    try {
      for (
        let index = startIndex;
        index < files.length;
        index += 1
      ) {
        const file = files[index];
        const humanIndex = index + 1;

        setMessage(
          `Téléversement ${humanIndex}/${files.length} : `
          + `${file.name} (${humanSize(file.size)}) · `
          + `garde cette page ouverte`
        );

        emit(
          "pcos-batch-import-uploading",
          {
            job_id: jobId,
            index: humanIndex,
            total: files.length,
            name: file.name,
            size: file.size
          }
        );

        await sendOne(
          jobId,
          file,
          humanIndex,
          files.length
        );

        setMessage(
          `Téléversement ${humanIndex}/${files.length} terminé. `
          + (
            humanIndex === files.length
              ? "Préparation du traitement en arrière-plan…"
              : "Envoi du package suivant…"
          )
        );
      }

      const finished = await json(
        `/api/batch-import/live/finish/`
        + encodeURIComponent(jobId),
        {
          method: "POST"
        }
      );

      stagingCompleted = true;
      setProgress(null); /* PINCABOS_UPLOAD_SPEED_V1 */

      setMessage(
        `${files.length}/${files.length} packages téléversés. `
        + `Import en arrière-plan actif. `
        + `Tu peux maintenant quitter cette page.`
      );

      emit(
        "pcos-batch-import-started",
        finished.job
      );

    } catch (error) {
      emit(
        "pcos-batch-import-upload-failed",
        {
          job_id: jobId,
          error: error.message
        }
      );

      throw new Error(
        `${error.message}. `
        + `Aucun STOP automatique n'a été envoyé. `
        + `Les packages déjà reçus restent sur le cab. `
        + `Resélectionne les mêmes ${files.length} packages `
        + `et reclique Lancer pour reprendre.`
      );

    } finally {
      if (stagingCompleted) {
        pcosStagingTransfer = null;
      }

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
<!-- PINCABOS_SMART_BATCH_PRO_V2 -->
<style>
/*
 * Smart Batch Import PRO V2
 * Une seule carte de pilotage : staging, import, compteurs, journal,
 * packages et historique. Les jobs stoppés ne sont jamais présentés
 * comme des jobs actifs/reprenables.
 */
#pco-bi-resume{
  --sb-bg:rgba(17,15,24,.82);
  --sb-panel:rgba(255,255,255,.045);
  --sb-border:rgba(255,255,255,.12);
  --sb-text:rgba(255,255,255,.92);
  --sb-muted:rgba(255,255,255,.58);
  --sb-orange:#ff9a24;
  --sb-green:#6fdda0;
  --sb-yellow:#ffd27e;
  --sb-red:#ff8e98;
  --sb-blue:#81b9ff;
  box-sizing:border-box;
  width:100%;
  margin:18px 0;
  padding:0;
  overflow:hidden;
  border:1px solid var(--sb-border);
  border-radius:18px;
  background:linear-gradient(145deg,rgba(30,24,39,.94),var(--sb-bg));
  box-shadow:0 18px 44px rgba(0,0,0,.22);
  color:var(--sb-text);
  font-size:13px;
}
#pco-bi-resume *,#pco-bi-resume *::before,#pco-bi-resume *::after{box-sizing:border-box}
#pco-bi-resume[data-floating="1"]{
  position:fixed;right:18px;bottom:18px;z-index:9998;
  width:min(760px,calc(100vw - 36px));max-height:calc(100vh - 36px);overflow:auto;
  background:rgba(20,16,28,.98);box-shadow:0 18px 50px rgba(0,0,0,.52)
}
#pco-bi-resume .sb-head{display:flex;gap:16px;align-items:flex-start;padding:18px 20px 16px;border-bottom:1px solid var(--sb-border)}
#pco-bi-resume .sb-title-wrap{min-width:0;flex:1}
#pco-bi-resume .sb-kicker{font-size:10px;font-weight:900;letter-spacing:.14em;text-transform:uppercase;color:var(--sb-orange);opacity:.9}
#pco-bi-resume h3{margin:4px 0 0;font-size:18px;line-height:1.2;color:#fff;font-weight:850;letter-spacing:.1px}
#pco-bi-resume .sb-job{margin-top:5px;color:var(--sb-muted);font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#pco-bi-resume .sb-badge{flex:0 0 auto;border:1px solid var(--sb-border);border-radius:999px;padding:7px 10px;font-size:11px;font-weight:850;color:#fff;background:rgba(255,255,255,.06)}
#pco-bi-resume[data-tone="active"] .sb-badge{border-color:rgba(255,154,36,.34);color:#ffd2a1;background:rgba(255,154,36,.10)}
#pco-bi-resume[data-tone="ok"] .sb-badge{border-color:rgba(111,221,160,.34);color:#baf3d2;background:rgba(111,221,160,.10)}
#pco-bi-resume[data-tone="warn"] .sb-badge{border-color:rgba(255,210,126,.35);color:#ffe2a8;background:rgba(255,210,126,.10)}
#pco-bi-resume[data-tone="bad"] .sb-badge{border-color:rgba(255,142,152,.38);color:#ffc4c9;background:rgba(255,142,152,.10)}
#pco-bi-resume .sb-body{padding:18px 20px 20px}
#pco-bi-resume .sb-alert{display:none;margin-bottom:14px;padding:11px 13px;border:1px solid rgba(255,210,126,.28);border-radius:12px;background:rgba(255,210,126,.07);color:#ffe4b7;line-height:1.45}
#pco-bi-resume .sb-alert[data-visible="1"]{display:block}
#pco-bi-resume .sb-progress-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-bottom:12px}
#pco-bi-resume .sb-progress-card{padding:12px 13px;border:1px solid var(--sb-border);border-radius:13px;background:var(--sb-panel)}
#pco-bi-resume .sb-progress-top{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:8px}
#pco-bi-resume .sb-progress-label{font-size:11px;font-weight:800;color:var(--sb-muted);text-transform:uppercase;letter-spacing:.06em}
#pco-bi-resume .sb-progress-value{font-size:12px;font-weight:900;color:#fff}
#pco-bi-resume .sb-bar{height:7px;border-radius:999px;background:rgba(255,255,255,.08);overflow:hidden}
#pco-bi-resume .sb-fill{height:100%;width:0;border-radius:inherit;transition:width .25s ease}
#pco-bi-resume .sb-upload-fill{background:linear-gradient(90deg,#5e99ff,#81b9ff)}
#pco-bi-resume .sb-process-fill{background:linear-gradient(90deg,#ffb000,#ff7a00)}
#pco-bi-resume .sb-stats{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:9px;margin-bottom:12px}
#pco-bi-resume .sb-stat{padding:11px 10px;border:1px solid var(--sb-border);border-radius:12px;background:var(--sb-panel);min-width:0}
#pco-bi-resume .sb-stat strong{display:block;font-size:20px;line-height:1;color:#fff;font-variant-numeric:tabular-nums}
#pco-bi-resume .sb-stat span{display:block;margin-top:5px;font-size:10px;line-height:1.25;color:var(--sb-muted)}
#pco-bi-resume .sb-current{display:grid;grid-template-columns:auto minmax(0,1fr);gap:10px 14px;align-items:center;padding:12px 13px;margin-bottom:12px;border:1px solid var(--sb-border);border-radius:13px;background:rgba(0,0,0,.13)}
#pco-bi-resume .sb-current-label{font-size:10px;font-weight:850;color:var(--sb-muted);text-transform:uppercase;letter-spacing:.06em}
#pco-bi-resume .sb-current-name{min-width:0;font-weight:750;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#pco-bi-resume .sb-current-detail{grid-column:1/-1;color:var(--sb-muted);font-size:11.5px;line-height:1.45;overflow-wrap:anywhere}
#pco-bi-resume .sb-actions{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}
#pco-bi-resume button{border:1px solid var(--sb-border);border-radius:10px;padding:8px 12px;background:rgba(255,255,255,.055);color:#fff;cursor:pointer;font:inherit;font-weight:800;transition:background .15s ease,border-color .15s ease,transform .05s ease}
#pco-bi-resume button:hover{background:rgba(255,255,255,.10)}
#pco-bi-resume button:active{transform:translateY(1px)}
#pco-bi-resume button[hidden]{display:none!important}
#pco-bi-resume .sb-pause{border-color:rgba(255,210,126,.30);color:#ffe0a5}
#pco-bi-resume .sb-resume{border-color:rgba(111,221,160,.32);color:#baf3d2}
#pco-bi-resume .sb-stop{border-color:rgba(255,142,152,.32);color:#ffc4c9}
#pco-bi-resume .sb-tabs{display:flex;gap:6px;flex-wrap:wrap;padding-top:2px;border-top:1px solid var(--sb-border)}
#pco-bi-resume .sb-tab{margin-top:12px;padding:7px 10px;border-radius:9px;color:var(--sb-muted)}
#pco-bi-resume .sb-tab[data-selected="1"]{background:rgba(255,154,36,.12);border-color:rgba(255,154,36,.26);color:#ffd2a1}
#pco-bi-resume .sb-section{display:none;margin-top:10px}
#pco-bi-resume .sb-section[data-visible="1"]{display:block}
#pco-bi-resume .sb-section-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:7px;color:var(--sb-muted);font-size:11px}
#pco-bi-resume .sb-log,#pco-bi-resume .sb-packages,#pco-bi-resume .sb-history{border:1px solid var(--sb-border);border-radius:12px;background:rgba(0,0,0,.16);overflow:auto}
#pco-bi-resume .sb-log{height:min(410px,42vh);padding:5px 0;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:11px;line-height:1.45}
#pco-bi-resume .sb-log-row{display:grid;grid-template-columns:68px 78px minmax(0,1fr);gap:8px;padding:6px 10px;border-bottom:1px solid rgba(255,255,255,.045)}
#pco-bi-resume .sb-log-time{color:rgba(255,255,255,.38)}
#pco-bi-resume .sb-log-level{font-weight:900;font-size:10px}
#pco-bi-resume .sb-log-msg{color:rgba(255,255,255,.72);overflow-wrap:anywhere}
#pco-bi-resume .sb-log-row[data-level="warning"] .sb-log-level{color:var(--sb-yellow)}
#pco-bi-resume .sb-log-row[data-level="error"] .sb-log-level{color:var(--sb-red)}
#pco-bi-resume .sb-log-row[data-level="info"] .sb-log-level{color:var(--sb-blue)}
#pco-bi-resume .sb-packages{max-height:420px}
#pco-bi-resume .sb-package-row{display:grid;grid-template-columns:52px minmax(160px,1.4fr) 145px minmax(180px,1fr);gap:10px;padding:8px 10px;border-bottom:1px solid rgba(255,255,255,.045);align-items:center;font-size:11px}
#pco-bi-resume .sb-package-row.sb-package-head{position:sticky;top:0;z-index:2;background:rgba(28,23,36,.98);font-size:10px;font-weight:900;color:var(--sb-muted);text-transform:uppercase;letter-spacing:.04em}
#pco-bi-resume .sb-package-name,#pco-bi-resume .sb-package-detail{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#pco-bi-resume .sb-package-state{font-weight:850}
#pco-bi-resume .sb-package-row[data-state="success"] .sb-package-state{color:var(--sb-green)}
#pco-bi-resume .sb-package-row[data-state="skipped"] .sb-package-state{color:var(--sb-yellow)}
#pco-bi-resume .sb-package-row[data-state="failed"],#pco-bi-resume .sb-package-row[data-state="error"] .sb-package-state{color:var(--sb-red)}
#pco-bi-resume .sb-package-row[data-state="running"] .sb-package-state{color:var(--sb-orange)}
#pco-bi-resume .sb-history{max-height:340px}
#pco-bi-resume .sb-history-row{display:grid;grid-template-columns:minmax(150px,.9fr) 160px minmax(220px,1.7fr);gap:10px;padding:9px 10px;border-bottom:1px solid rgba(255,255,255,.045);font-size:11px;align-items:center}
#pco-bi-resume .sb-history-id{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:rgba(255,255,255,.68);font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
#pco-bi-resume .sb-history-state{font-weight:850;color:#fff}
#pco-bi-resume .sb-history-detail{color:var(--sb-muted);overflow-wrap:anywhere}
#pco-bi-resume .sb-empty{padding:18px;text-align:center;color:var(--sb-muted)}
/* Harmonise aussi la file de téléversement existante avec la nouvelle carte. */
#pco-bi-queue{border:1px solid rgba(255,255,255,.12)!important;border-radius:14px!important;background:rgba(17,15,24,.70)!important;padding:12px 13px!important}
#pco-bi-upwrap{height:8px!important;border-radius:999px!important;background:rgba(255,255,255,.08)!important}
#pco-bi-upbar{border-radius:999px!important}
@media(max-width:850px){
  #pco-bi-resume .sb-stats{grid-template-columns:repeat(2,minmax(0,1fr))}
  #pco-bi-resume .sb-progress-grid{grid-template-columns:1fr}
  #pco-bi-resume .sb-package-row{grid-template-columns:44px minmax(130px,1fr) 125px}
  #pco-bi-resume .sb-package-detail{display:none}
  #pco-bi-resume .sb-history-row{grid-template-columns:1fr 130px}
  #pco-bi-resume .sb-history-detail{grid-column:1/-1}
}
</style>
<script>
(() => {
  "use strict";
  if (window.__pcosSmartBatchProV2) return;
  window.__pcosSmartBatchProV2 = true;

  let current = null;
  let historyCache = [];
  let selectedTab = "journal";

  const FINAL_STATES = new Set(["completed", "completed_with_warning", "stopped", "cancelled", "failed"]);
  const ACTIVE_STATES = new Set(["uploading", "queued", "running", "stopping", "pausing"]);

  async function api(url, options = {}) {
    const response = await fetch(url, {
      cache: "no-store",
      credentials: "same-origin",
      headers: {"Accept": "application/json", ...(options.headers || {})},
      ...options
    });
    let data = {};
    try { data = await response.json(); } catch (_) {}
    if (!response.ok && response.status !== 202) {
      throw new Error(data.error || `HTTP ${response.status}`);
    }
    return data;
  }

  function anchor() {
    return document.getElementById("pco-bi-queue")
      || document.getElementById("pco-bi-upwrap")
      || document.querySelector("form[enctype]");
  }

  function panel() {
    let node = document.getElementById("pco-bi-resume");
    if (node) return node;

    node = document.createElement("section");
    node.id = "pco-bi-resume";
    node.setAttribute("aria-live", "polite");
    node.dataset.tone = "active";
    node.innerHTML = `
      <div class="sb-head">
        <div class="sb-title-wrap">
          <div class="sb-kicker">Smart Batch Import</div>
          <h3>Prêt</h3>
          <div class="sb-job">Aucun job actif</div>
        </div>
        <div class="sb-badge">PRÊT</div>
      </div>
      <div class="sb-body">
        <div class="sb-alert"></div>
        <div class="sb-progress-grid">
          <div class="sb-progress-card">
            <div class="sb-progress-top"><span class="sb-progress-label">Téléversement</span><span class="sb-progress-value sb-upload-value">0 / 0</span></div>
            <div class="sb-bar"><div class="sb-fill sb-upload-fill"></div></div>
          </div>
          <div class="sb-progress-card">
            <div class="sb-progress-top"><span class="sb-progress-label">Traitement</span><span class="sb-progress-value sb-process-value">0 / 0</span></div>
            <div class="sb-bar"><div class="sb-fill sb-process-fill"></div></div>
          </div>
        </div>
        <div class="sb-stats">
          <div class="sb-stat"><strong data-stat="success">0</strong><span>Importées</span></div>
          <div class="sb-stat"><strong data-stat="skipped">0</strong><span>Déjà présentes / ignorées</span></div>
          <div class="sb-stat"><strong data-stat="failed">0</strong><span>Erreurs ignorées</span></div>
          <div class="sb-stat"><strong data-stat="warnings">0</strong><span>Avertissements</span></div>
          <div class="sb-stat"><strong data-stat="remaining">0</strong><span>Restantes</span></div>
        </div>
        <div class="sb-current">
          <div class="sb-current-label">Table actuelle</div>
          <div class="sb-current-name">—</div>
          <div class="sb-current-detail">Worker prêt.</div>
        </div>
        <div class="sb-actions">
          <button class="sb-pause" type="button">Pause</button>
          <button class="sb-resume" type="button">Reprendre</button>
          <button class="sb-stop" type="button">Arrêter</button>
          <button class="sb-copy" type="button">Copier le journal</button>
          <button class="sb-download" type="button">Télécharger le journal</button>
          <button class="sb-dismiss" type="button">Masquer le résultat</button>
        </div>
        <div class="sb-tabs">
          <button class="sb-tab" data-tab="journal" data-selected="1" type="button">Journal</button>
          <button class="sb-tab" data-tab="packages" type="button">Packages</button>
          <button class="sb-tab" data-tab="history" type="button">Historique</button>
        </div>
        <div class="sb-section" data-section="journal" data-visible="1">
          <div class="sb-section-head"><span class="sb-log-count">0 événement</span><span>Journal complet conservé par le job</span></div>
          <div class="sb-log"></div>
        </div>
        <div class="sb-section" data-section="packages">
          <div class="sb-section-head"><span class="sb-package-count">0 package</span><span>État individuel des packages</span></div>
          <div class="sb-packages"></div>
        </div>
        <div class="sb-section" data-section="history">
          <div class="sb-section-head"><span>Derniers Smart Batch</span><span class="sb-history-count">0 job</span></div>
          <div class="sb-history"></div>
        </div>
      </div>`;

    const ref = anchor();
    if (ref && ref.parentNode) {
      ref.parentNode.insertBefore(node, ref.nextSibling);
    } else {
      node.dataset.floating = "1";
      document.body.appendChild(node);
    }

    node.querySelector(".sb-pause").addEventListener("click", () => act("pause"));
    node.querySelector(".sb-resume").addEventListener("click", () => act("resume"));
    node.querySelector(".sb-stop").addEventListener("click", () => act("stop"));
    node.querySelector(".sb-copy").addEventListener("click", copyLog);
    node.querySelector(".sb-download").addEventListener("click", downloadLog);
    node.querySelector(".sb-dismiss").addEventListener("click", dismissCurrent);
    node.querySelectorAll(".sb-tab").forEach(button => {
      button.addEventListener("click", () => selectTab(button.dataset.tab || "journal"));
    });
    return node;
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

  function selectTab(name) {
    selectedTab = name;
    const node = panel();
    node.querySelectorAll(".sb-tab").forEach(button => {
      button.dataset.selected = button.dataset.tab === name ? "1" : "0";
    });
    node.querySelectorAll(".sb-section").forEach(section => {
      section.dataset.visible = section.dataset.section === name ? "1" : "0";
    });
  }

  function stateInfo(job) {
    if (!job) return {title:"Prêt", badge:"PRÊT", tone:"ok", detail:"Aucun Smart Batch actif."};
    const state = String(job.state || "").toLowerCase();
    const total = Number(job.total_archives || 0);
    const uploaded = Number(job.uploaded_archives ?? (job.uploads || []).length ?? 0);
    const done = Number(job.processed_archives || 0);
    const complete = Boolean(job.uploads_complete);

    if (!complete && ["uploading", "queued", "paused"].includes(state)) {
      return {
        title:"Téléversement incomplet",
        badge:"STAGING",
        tone:"warn",
        detail:`${uploaded}/${total} package(s) reçus · ${Math.max(0,total-uploaded)} non reçu(s) · import non démarré.`
      };
    }
    if (state === "uploading") return {title:"Téléversement en cours", badge:"UPLOAD", tone:"active", detail:"Garde cette page ouverte jusqu’à N/N téléversés."};
    if (state === "queued") return {title:"Prêt pour le worker", badge:"EN FILE", tone:"active", detail:"Tous les packages sont sur le cab. Le worker va commencer."};
    if (state === "running") return {title:"Import en cours", badge:"ACTIF", tone:"active", detail:"Traitement séquentiel en arrière-plan."};
    if (state === "stopping") return {title:"Arrêt demandé", badge:"ARRÊT…", tone:"warn", detail:"Le package courant se termine proprement."};
    if (state === "paused" && job.error) return {title:"Pause de sécurité", badge:"PAUSE", tone:"bad", detail:String(job.error)};
    if (state === "paused") return {title:"En pause", badge:"PAUSE", tone:"warn", detail:"Le Batch peut être repris sans retransmettre les packages déjà stockés."};
    if (state === "completed") return {title:"Terminé", badge:"TERMINÉ", tone:"ok", detail:"Smart Batch terminé sans erreur."};
    if (state === "completed_with_warning") return {title:"Terminé avec avertissements", badge:"TERMINÉ", tone:"warn", detail:"Le Batch est terminé. Consulte les compteurs et le journal."};
    if (state === "stopped") return {title:"Arrêté", badge:"ARRÊTÉ", tone:"warn", detail:done ? "Batch arrêté volontairement." : `Téléversement interrompu : ${uploaded}/${total} reçus · import non démarré.`};
    if (state === "failed") return {title:"Erreur", badge:"ERREUR", tone:"bad", detail:String(job.error || "Erreur du Batch.")};
    return {title:state || "État inconnu", badge:(state || "—").toUpperCase(), tone:"warn", detail:"État du Smart Batch."};
  }

  function packetLabel(state) {
    return ({
      queued:"En attente", running:"En cours", success:"Importée", done:"Importée",
      skipped:"Ignorée", failed:"Erreur ignorée", warning:"Avertissement", error:"Erreur système"
    })[state] || state || "—";
  }

  function eventLevel(event) {
    const level = String(event?.level || "info").toLowerCase();
    return level === "warning" || level === "error" ? level : "info";
  }

  function eventText(events) {
    return (events || []).map(event => {
      const time = String(event.at || "").replace("T", " ").replace("Z", " UTC");
      return `${time} [${eventLevel(event).toUpperCase()}] ${event.message || ""}`;
    }).join("\n");
  }

  function safeFileName(value) {
    return String(value || "smart-batch").replace(/[^a-zA-Z0-9._-]+/g, "-").replace(/^-+|-+$/g, "") || "smart-batch";
  }

  async function copyLog() {
    const events = current?.events || [];
    if (!events.length) return;
    try {
      await navigator.clipboard.writeText(eventText(events));
      const button = panel().querySelector(".sb-copy");
      const old = button.textContent;
      button.textContent = "Copié ✓";
      window.setTimeout(() => { button.textContent = old; }, 1400);
    } catch (_) {}
  }

  function downloadLog() {
    const events = current?.events || [];
    if (!events.length) return;
    const blob = new Blob([eventText(events) + "\n"], {type:"text/plain;charset=utf-8"});
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${safeFileName(current?.id)}-smart-batch.log.txt`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  function dismissCurrent() {
    if (!current?.id) return;
    localStorage.setItem(`pcos-smart-batch-pro-v2-dismissed-${current.id}`, "1");
    current = null;
    renderCurrent({job:null}, historyCache);
  }

  async function act(action) {
    if (!current?.id) return;
    if (action === "stop") {
      const ok = window.confirm("Arrêter ce Smart Batch ? Les packages non traités seront supprimés. Cette action ne désinstalle aucune table déjà importée.");
      if (!ok) return;
    }
    try {
      await api(`/api/batch-import/live/${action}/${encodeURIComponent(current.id)}`, {method:"POST"});
    } catch (error) {
      const alert = panel().querySelector(".sb-alert");
      alert.dataset.visible = "1";
      alert.textContent = `Action impossible : ${error.message}`;
    }
    await refresh();
  }

  function renderLog(job) {
    const node = panel();
    const log = node.querySelector(".sb-log");
    const events = job?.events || [];
    node.querySelector(".sb-log-count").textContent = `${events.length} événement(s)`;

    const same = log.dataset.jobId === String(job?.id || "");
    let rendered = same ? Number(log.dataset.count || 0) : 0;
    if (!same || rendered > events.length) {
      log.innerHTML = "";
      rendered = 0;
    }

    const nearBottom = log.scrollHeight - log.scrollTop - log.clientHeight < 50;
    events.slice(rendered).forEach(event => {
      const row = document.createElement("div");
      const level = eventLevel(event);
      row.className = "sb-log-row";
      row.dataset.level = level;
      row.innerHTML = '<span class="sb-log-time"></span><span class="sb-log-level"></span><span class="sb-log-msg"></span>';
      row.querySelector(".sb-log-time").textContent = String(event.at || "").slice(11,19);
      row.querySelector(".sb-log-level").textContent = level.toUpperCase();
      row.querySelector(".sb-log-msg").textContent = String(event.message || "");
      log.appendChild(row);
    });

    if (!events.length) log.innerHTML = '<div class="sb-empty">Aucun événement pour ce job.</div>';
    log.dataset.jobId = String(job?.id || "");
    log.dataset.count = String(events.length);
    if (nearBottom || rendered === 0) log.scrollTop = log.scrollHeight;
  }

  function renderPackages(job) {
    const node = panel();
    const host = node.querySelector(".sb-packages");
    const items = Array.isArray(job?.uploads) ? [...job.uploads] : [];
    items.sort((a,b) => Number(a.index || 0) - Number(b.index || 0));
    node.querySelector(".sb-package-count").textContent = `${items.length} package(s)`;

    if (!items.length) {
      host.innerHTML = '<div class="sb-empty">Aucun package dans ce job.</div>';
      return;
    }

    host.innerHTML = '<div class="sb-package-row sb-package-head"><span>#</span><span>Package</span><span>Statut</span><span>Détail</span></div>';
    items.forEach(item => {
      const state = String(item.state || "").toLowerCase();
      const row = document.createElement("div");
      row.className = "sb-package-row";
      row.dataset.state = state;
      row.innerHTML = '<span></span><span class="sb-package-name"></span><span class="sb-package-state"></span><span class="sb-package-detail"></span>';
      row.children[0].textContent = String(item.index || "");
      row.querySelector(".sb-package-name").textContent = String(item.name || "Package");
      row.querySelector(".sb-package-state").textContent = packetLabel(state);
      row.querySelector(".sb-package-detail").textContent = String(item.detail || "");
      row.title = [item.name, packetLabel(state), item.detail].filter(Boolean).join(" — ");
      host.appendChild(row);
    });
  }

  function historyInfo(job) {
    const state = String(job?.state || "").toLowerCase();
    const total = Number(job?.total_archives || 0);
    const uploaded = Number(job?.uploaded_archives ?? (job?.uploads || []).length ?? 0);
    const done = Number(job?.processed_archives || 0);
    const p = job?.progress || {};
    if (state === "stopped" && done === 0 && uploaded < total) {
      return ["Téléversement interrompu", `${uploaded}/${total} téléversés · import non démarré`];
    }
    const label = stateInfo(job).title;
    const detail = [
      `${done}/${total} traités`,
      `${Number(p.successful || 0)} importées`,
      `${Number(p.skipped || 0)} ignorées`,
      `${Number(p.failed || 0)} erreurs ignorées`
    ].join(" · ");
    return [label, detail];
  }

  function renderHistory(jobs) {
    const node = panel();
    const host = node.querySelector(".sb-history");
    const rows = Array.isArray(jobs) ? jobs.slice(0,40) : [];
    node.querySelector(".sb-history-count").textContent = `${rows.length} job(s)`;
    if (!rows.length) {
      host.innerHTML = '<div class="sb-empty">Aucun historique.</div>';
      return;
    }
    host.innerHTML = "";
    rows.forEach(job => {
      const [label, detail] = historyInfo(job);
      const row = document.createElement("div");
      row.className = "sb-history-row";
      row.innerHTML = '<span class="sb-history-id"></span><span class="sb-history-state"></span><span class="sb-history-detail"></span>';
      row.querySelector(".sb-history-id").textContent = String(job.id || "");
      row.querySelector(".sb-history-state").textContent = label;
      row.querySelector(".sb-history-detail").textContent = detail;
      host.appendChild(row);
    });
  }

  function renderCurrent(data, jobs) {
    const node = panel();
    let job = data?.job || null;

    if (job?.id && localStorage.getItem(`pcos-smart-batch-pro-v2-dismissed-${job.id}`) === "1") {
      job = null;
    }
    current = job;

    const info = stateInfo(job);
    node.dataset.tone = info.tone;
    node.querySelector("h3").textContent = info.title;
    node.querySelector(".sb-badge").textContent = info.badge;
    node.querySelector(".sb-job").textContent = job?.id ? `Job ${job.id}` : "Aucun job actif";
    node.querySelector(".sb-job").title = job?.id || "";

    const progress = job?.progress || {};
    const total = Number(progress.total ?? job?.total_archives ?? 0);
    const uploaded = Number(job?.uploaded_archives ?? (job?.uploads || []).length ?? 0);
    const done = Number(progress.completed ?? job?.processed_archives ?? 0);
    const success = Number(progress.successful || 0);
    const skipped = Number(progress.skipped || 0);
    const failed = Number(progress.failed || 0);
    const warnings = Number(progress.warnings || 0);
    const remaining = Math.max(0, total - done);
    const uploadPct = total ? Math.max(0,Math.min(100,uploaded * 100 / total)) : 0;
    const processPct = total ? Math.max(0,Math.min(100,done * 100 / total)) : 0;

    node.querySelector(".sb-upload-value").textContent = `${uploaded} / ${total}`;
    node.querySelector(".sb-process-value").textContent = `${done} / ${total}`;
    node.querySelector(".sb-upload-fill").style.width = `${uploadPct}%`;
    node.querySelector(".sb-process-fill").style.width = `${processPct}%`;
    node.querySelector('[data-stat="success"]').textContent = String(success);
    node.querySelector('[data-stat="skipped"]').textContent = String(skipped);
    node.querySelector('[data-stat="failed"]').textContent = String(failed);
    node.querySelector('[data-stat="warnings"]').textContent = String(warnings);
    node.querySelector('[data-stat="remaining"]').textContent = String(remaining);

    const currentName = String(progress.current_item || job?.current_item || "");
    node.querySelector(".sb-current-name").textContent = currentName || "—";
    node.querySelector(".sb-current-name").title = currentName;
    const currentDetail = [progress.label, info.detail, job?.error].filter(Boolean).join(" · ");
    node.querySelector(".sb-current-detail").textContent = currentDetail || "Worker prêt.";

    const alert = node.querySelector(".sb-alert");
    const state = String(job?.state || "").toLowerCase();
    const uploadsComplete = Boolean(job?.uploads_complete);
    if (job && !uploadsComplete && ["uploading", "queued", "paused"].includes(state)) {
      alert.dataset.visible = "1";
      alert.textContent = `Téléversement incomplet : ${uploaded}/${total} reçu(s). Le worker ne doit pas commencer avant ${total}/${total}. Si le navigateur n’a plus les fichiers locaux, arrête ce brouillon et relance une nouvelle sélection.`;
    } else if (job?.error) {
      alert.dataset.visible = "1";
      alert.textContent = String(job.error);
    } else {
      alert.dataset.visible = "0";
      alert.textContent = "";
    }

    const active = ACTIVE_STATES.has(state);
    const pauseAllowed = uploadsComplete && ["queued", "running"].includes(state);
    const resumeAllowed = uploadsComplete && state === "paused" && Boolean(data?.resumable);
    node.querySelector(".sb-pause").hidden = !pauseAllowed;
    node.querySelector(".sb-resume").hidden = !resumeAllowed;
    node.querySelector(".sb-stop").hidden = !(active || state === "paused");
    node.querySelector(".sb-copy").hidden = !(job?.events || []).length;
    node.querySelector(".sb-download").hidden = !(job?.events || []).length;
    node.querySelector(".sb-dismiss").hidden = !(job && ["completed", "completed_with_warning"].includes(state));

    renderLog(job);
    renderPackages(job);
    renderHistory(jobs);
    selectTab(selectedTab);
  }

  async function refresh() {
    try {
      const [active, history] = await Promise.all([
        api("/api/batch-import/live/active"),
        api("/api/batch-import/live/history")
      ]);
      historyCache = history.jobs || [];
      renderCurrent(active, historyCache);
      reseat();
    } catch (error) {
      const node = panel();
      node.dataset.tone = "bad";
      node.querySelector("h3").textContent = "État indisponible";
      node.querySelector(".sb-badge").textContent = "API";
      const alert = node.querySelector(".sb-alert");
      alert.dataset.visible = "1";
      alert.textContent = `Impossible de lire l’état Smart Batch : ${error.message}`;
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", refresh, {once:true});
  } else {
    refresh();
  }
  window.addEventListener("pcos-batch-import-started", refresh);
  window.addEventListener("pcos-batch-import-finished", refresh);
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

    # PINCABOS_SMART_BATCH_STAGING_FIX_V31
    @app.route(
        "/api/batch-import/live/upload-raw/<job_id>/<int:index>",
        methods=["POST"],
    )
    def pincabos_batch_import_v31_upload_raw(
        job_id: str,
        index: int,
    ) -> Any:
        filename = str(request.args.get("name", "") or "")
        try:
            expected_size = int(
                request.args.get("size", "0") or 0
            )
        except (TypeError, ValueError):
            expected_size = 0

        try:
            job = _save_raw_upload(
                job_id,
                request.stream,
                filename,
                index,
                expected_size,
            )
        except ValueError as exc:
            return jsonify({
                "ok": False,
                "error": str(exc),
            }), 400
        except RuntimeError as exc:
            return jsonify({
                "ok": False,
                "error": str(exc),
            }), 409
        except Exception as exc:
            return jsonify({
                "ok": False,
                "error": f"Téléversement RAW impossible : {exc}",
            }), 500

        return jsonify({
            "ok": True,
            "job": queue.public_job(job),
        }), 202


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
        """Retourne uniquement un Smart Batch réellement pertinent à piloter.

        Priorité :
        1) slot actif ;
        2) dernier job en pause et réellement reprenable ;
        Aucun ancien résultat terminé n'est injecté à la place du job courant.

        Un job stopped/cancelled/failed ou un staging incomplet stoppé reste dans
        /history, mais n'est jamais présenté comme actif ou reprenable.
        """
        job_id = queue.active_job_id()
        job = queue.load_job(job_id) if job_id else None

        history = queue.list_jobs()

        if not job:
            for candidate in history:
                state = str(candidate.get("state", ""))
                if state != queue.PAUSED_STATE:
                    continue
                if not bool(candidate.get("uploads_complete")):
                    continue
                remaining = any(
                    isinstance(item, dict)
                    and str(item.get("state")) in {"queued", "running", "error"}
                    for item in (candidate.get("uploads") or [])
                )
                if remaining:
                    job = candidate
                    break

        # PINCABOS_SMART_BATCH_STAGING_FIX_V31
        # Aucun fallback vers une ancienne job terminée.
        # L'historique reste disponible via /history.
        if not job:
            return jsonify({"ok": True, "job": None, "resumable": False, "paused": False, "remaining": 0})

        state = str(job.get("state", ""))
        remaining = sum(
            1 for item in (job.get("uploads") or [])
            if isinstance(item, dict)
            and str(item.get("state")) in {"queued", "running", "error"}
        )
        resumable = (
            state == queue.PAUSED_STATE
            and bool(job.get("uploads_complete"))
            and remaining > 0
        )
        return jsonify({
            "ok": True,
            "job": queue.public_job(job),
            "resumable": resumable,
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
