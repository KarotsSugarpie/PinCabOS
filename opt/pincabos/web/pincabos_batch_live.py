# PINCABOS_BATCH_LIVE_V6
"""Professional, non-blocking UI for PinCabOS Batch Export V1.

The existing V1 POST route remains the only archive engine. This module places
that same request in a protected background job and observes V1's individual
`.PinCabOS` copy operations. It never alters table content or archive logic.
"""
from __future__ import annotations

import contextvars
import fcntl
import html
import json
import os
import re
import shutil
import threading
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest

from flask import g, jsonify, request

MARKER = "PINCABOS_BATCH_LIVE_V6"
RUN_DIR = Path(os.environ.get("PINCABOS_BATCH_LIVE_DIR", "/var/lib/pincabos/batch-live"))
LOCK_PATH = Path(os.environ.get(
    "PINCABOS_BATCH_LIVE_SHARED_LOCK",
    "/var/lib/pincabos/batch-live/export.lock",
))
ACTIVE_PATH = RUN_DIR / "active.json"
INTERNAL_BASE_URL = os.environ.get("PINCABOS_BATCH_LIVE_INTERNAL_URL", "http://127.0.0.1").rstrip("/")
INTERNAL_TARGET = "/tools/batch-export/run"
INTERNAL_HEADER = "X-PinCabOS-Batch-Live"
MAX_EVENTS = 700
MAX_HISTORY = 20
_COPY_JOB = contextvars.ContextVar("pincabos_batch_live_copy_job", default=None)
_ORIGINAL_COPY2 = shutil.copy2
_PATCH_LOCK = threading.Lock()
_PATCHED = False


class BatchStopRequested(RuntimeError):
    """Raised at a safe package boundary after the operator presses Stop."""


def _stop_requested(job_id: str) -> bool:
    job = _load_job(job_id)
    return bool(job and job.get("stop_requested"))


def _mark_stopped(job: dict[str, Any], message: str = "Export arrêté par l’utilisateur.") -> None:
    job["state"] = "stopped"
    job["finished_at"] = _utc_now()
    job["error"] = ""
    _progress(job, "Arrêté", current=str(job.get("current_table", "") or ""), percent=100)
    _event(job, message, "warning")
    _save_job(job)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_run_dir() -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True, mode=0o750)
    try:
        os.chmod(RUN_DIR, 0o750)
    except OSError:
        pass


def _job_path(job_id: str) -> Path:
    return RUN_DIR / f"job-{job_id}.json"


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError, TypeError):
        return default


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    _ensure_run_dir()
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=False)
        handle.write("\n")
    os.chmod(temporary, 0o640)
    os.replace(temporary, path)


def _event(job: dict[str, Any], message: str, level: str = "info") -> None:
    events = job.setdefault("events", [])
    events.append({"at": _utc_now(), "level": level, "message": message})
    if len(events) > MAX_EVENTS:
        del events[:-MAX_EVENTS]


def _save_job(job: dict[str, Any]) -> None:
    job["updated_at"] = _utc_now()
    _write_json(_job_path(job["id"]), job)


def _load_job(job_id: str) -> dict[str, Any] | None:
    if not re.fullmatch(r"[a-f0-9]{32}", job_id or ""):
        return None
    value = _read_json(_job_path(job_id), None)
    return value if isinstance(value, dict) else None


def _set_active(job_id: str | None) -> None:
    _write_json(ACTIVE_PATH, {"job_id": job_id, "updated_at": _utc_now()})


def _active_job_id() -> str | None:
    value = _read_json(ACTIVE_PATH, {})
    candidate = value.get("job_id") if isinstance(value, dict) else None
    return candidate if isinstance(candidate, str) and re.fullmatch(r"[a-f0-9]{32}", candidate) else None


def _compact_html(raw_html: str) -> str:
    cleaned = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw_html)
    cleaned = re.sub(r"(?i)<(?:br|/p|/div|/li|/tr|/h[1-6])[^>]*>", "\n", cleaned)
    cleaned = re.sub(r"(?is)<[^>]+>", " ", cleaned)
    lines = []
    for line in html.unescape(cleaned).splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines[-22:])[:7000] or "Aucun résumé textuel retourné par V1."


def _selected_tables(fields: list[tuple[str, str]]) -> list[str]:
    values = [value.strip() for key, value in fields if key == "table_folder" and value.strip()]
    if not values:
        raise ValueError("Sélectionne au moins une table avant de lancer l’export.")
    if len(values) > 500:
        raise ValueError("Trop de tables sélectionnées.")
    return values


def _progress(job: dict[str, Any], label: str, *, current: str | None = None, percent: int | None = None) -> None:
    total = max(1, int(job.get("total_tables", 0) or 0))
    completed = max(0, min(total, int(job.get("completed_tables", 0) or 0)))
    if percent is None:
        # 4% queue/start, then progress advances exactly as each package copy completes.
        percent = 4 + int((completed / total) * 92)
    job["progress"] = {
        "percent": max(0, min(100, int(percent))),
        "label": label,
        "current_table": current or job.get("current_table") or "",
        "completed": completed,
        "total": total,
        "mode": "packages",
    }


def _public_job(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": job.get("id"),
        "state": job.get("state"),
        "created_at": job.get("created_at"),
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
        "updated_at": job.get("updated_at"),
        "progress": job.get("progress", {}),
        "events": job.get("events", []),
        "result_excerpt": job.get("result_excerpt", ""),
        "error": job.get("error", ""),
        "total_tables": job.get("total_tables", 0),
        "completed_tables": job.get("completed_tables", 0),
        "current_table": job.get("current_table", ""),
        "completed_names": job.get("completed_names", []),
    }


def _recover_stale_active() -> None:
    active_id = _active_job_id()
    if not active_id:
        return
    job = _load_job(active_id)
    if job and job.get("state") in {"queued", "running"}:
        job["state"] = "failed"
        job["finished_at"] = _utc_now()
        job["error"] = "Job interrompu par un redémarrage ou arrêt du WebApp."
        _progress(job, "Interrompu", percent=100)
        _event(job, job["error"], "error")
        _save_job(job)
    _set_active(None)


def _safe_table_name(job: dict[str, Any], completed: int) -> str:
    tables = job.get("selected_tables", [])
    if isinstance(tables, list) and 0 <= completed < len(tables):
        return str(tables[completed])
    return f"Table {completed + 1}"


def _copy_started(job_id: str, source: Any, destination: Any) -> None:
    job = _load_job(job_id)
    if not job or job.get("state") not in {"queued", "running"}:
        return
    completed = int(job.get("completed_tables", 0) or 0)
    current = _safe_table_name(job, completed)
    job["current_table"] = current
    job["current_package"] = Path(str(source)).name
    _progress(job, "Création/copie du package", current=current)
    _event(job, f"Table {completed + 1}/{job.get('total_tables', 0)} en cours : {current}")
    _save_job(job)


def _copy_finished(job_id: str, source: Any, destination: Any) -> None:
    job = _load_job(job_id)
    if not job or job.get("state") not in {"queued", "running"}:
        return
    completed = int(job.get("completed_tables", 0) or 0)
    total = int(job.get("total_tables", 0) or 0)
    current = job.get("current_table") or _safe_table_name(job, completed)
    completed = min(total, completed + 1)
    job["completed_tables"] = completed
    names = job.setdefault("completed_names", [])
    if isinstance(names, list) and len(names) < total:
        names.append(current)
    next_name = _safe_table_name(job, completed) if completed < total else ""
    job["current_table"] = next_name
    if completed < total:
        _progress(job, "Package copié", current=next_name)
        _event(job, f"Package terminé : {current} ({completed}/{total}). Prochaine table : {next_name}")
    else:
        _progress(job, "Dernier package copié", current="")
        _event(job, f"Package terminé : {current} ({completed}/{total}).")
    _save_job(job)


def _copy_failed(job_id: str, source: Any, exc: Exception) -> None:
    job = _load_job(job_id)
    if not job:
        return
    current = job.get("current_table") or _safe_table_name(job, int(job.get("completed_tables", 0) or 0))
    _event(job, f"Erreur pendant la copie de {current} : {exc}", "error")
    _save_job(job)


def _install_copy_observer() -> None:
    global _PATCHED
    with _PATCH_LOCK:
        if _PATCHED:
            return

        def observed_copy2(source: Any, destination: Any, *args: Any, **kwargs: Any) -> Any:
            job_id = _COPY_JOB.get()
            observe = bool(job_id) and Path(str(source)).suffix.lower() == ".pincabos"
            if observe and _stop_requested(str(job_id)):
                raise BatchStopRequested("Arrêt demandé par l’utilisateur avant la copie du prochain package.")
            if observe:
                _copy_started(str(job_id), source, destination)
            try:
                result = _ORIGINAL_COPY2(source, destination, *args, **kwargs)
            except Exception as exc:
                if observe:
                    _copy_failed(str(job_id), source, exc)
                raise
            if observe:
                _copy_finished(str(job_id), source, destination)
            return result

        shutil.copy2 = observed_copy2
        _PATCHED = True


def _validate_fields(raw_fields: Any) -> list[tuple[str, str]]:
    if not isinstance(raw_fields, list) or not raw_fields or len(raw_fields) > 1500:
        raise ValueError("Formulaire Batch Export invalide ou trop volumineux.")
    fields: list[tuple[str, str]] = []
    for item in raw_fields:
        if not isinstance(item, list) or len(item) != 2:
            raise ValueError("Structure de formulaire invalide.")
        key, value = item
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("Champ Batch Export invalide.")
        if not key or len(key) > 160 or len(value) > 32768:
            raise ValueError("Taille de champ Batch Export invalide.")
        fields.append((key, value))
    _selected_tables(fields)
    return fields


def _run_v1(job_id: str, fields: list[tuple[str, str]], lock_fd: int) -> None:
    job = _load_job(job_id)
    try:
        if not job:
            return
        job["state"] = "running"
        job["started_at"] = _utc_now()
        first = _safe_table_name(job, 0)
        job["current_table"] = first
        _progress(job, "Préparation du moteur V1", current=first, percent=8)
        _event(job, f"Export V1 démarré en arrière-plan : {job.get('total_tables', 0)} table(s).")
        _event(job, f"Première table planifiée : {first}")
        _save_job(job)

        encoded = urlparse.urlencode(fields, doseq=True).encode("utf-8")
        outbound = urlrequest.Request(
            f"{INTERNAL_BASE_URL}{INTERNAL_TARGET}",
            data=encoded,
            method="POST",
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
                "Accept": "text/html,application/xhtml+xml",
                INTERNAL_HEADER: job_id,
            },
        )
        _progress(job, "Moteur V1 en cours", current=first, percent=10)
        _event(job, "Requête interne envoyée au moteur V1. La page reste utilisable.")
        _save_job(job)
        with urlrequest.urlopen(outbound, timeout=6 * 60 * 60) as response:
            status = int(getattr(response, "status", response.getcode()))
            body = response.read().decode("utf-8", errors="replace")
        if status < 200 or status >= 300:
            raise RuntimeError(f"Le moteur V1 a retourné HTTP {status}.")

        job = _load_job(job_id) or job
        if job.get("stop_requested"):
            _mark_stopped(job)
            return
        job["result_excerpt"] = _compact_html(body)
        completed = int(job.get("completed_tables", 0) or 0)
        total = int(job.get("total_tables", 0) or 0)
        if completed == total:
            job["state"] = "completed"
            job["current_table"] = ""
            _progress(job, "Terminé", current="", percent=100)
            _event(job, f"Export terminé : {completed}/{total} fichier(s) .PinCabOS copiés.")
        else:
            job["state"] = "completed_with_warning"
            job["current_table"] = _safe_table_name(job, completed) if completed < total else ""
            _progress(job, "Terminé avec vérification requise", percent=100)
            _event(job, f"V1 a répondu HTTP 200, mais seulement {completed}/{total} copies .PinCabOS ont été observées.", "warning")
        job["finished_at"] = _utc_now()
        _save_job(job)
    except urlerror.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
        job = _load_job(job_id) or job
        if job and job.get("stop_requested"):
            _mark_stopped(job)
        elif job:
            job["state"] = "failed"
            job["finished_at"] = _utc_now()
            job["error"] = f"HTTP {exc.code} depuis le moteur V1."
            job["result_excerpt"] = _compact_html(text) if text else "Aucun détail HTML disponible."
            _progress(job, "Erreur", percent=100)
            _event(job, job["error"], "error")
            _save_job(job)
    except Exception as exc:  # diagnostic for a running job
        job = _load_job(job_id) or job
        if job and job.get("stop_requested"):
            _mark_stopped(job)
        elif job:
            job["state"] = "failed"
            job["finished_at"] = _utc_now()
            job["error"] = str(exc)
            _progress(job, "Erreur", percent=100)
            _event(job, f"Échec : {exc}", "error")
            _event(job, traceback.format_exc(limit=5), "debug")
            _save_job(job)
    finally:
        try:
            if _active_job_id() == job_id:
                _set_active(None)
        finally:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            finally:
                os.close(lock_fd)


def register_batch_live(app: Any) -> None:
    if app.config.get("PINCABOS_BATCH_LIVE_V6_REGISTERED"):
        return
    app.config["PINCABOS_BATCH_LIVE_V6_REGISTERED"] = True
    _ensure_run_dir()
    _recover_stale_active()
    _install_copy_observer()

    @app.before_request
    def pincabos_batch_live_v4_copy_context() -> None:
        if request.method != "POST" or request.path != INTERNAL_TARGET:
            return
        raw_job_id = request.headers.get(INTERNAL_HEADER, "")
        if request.remote_addr not in {"127.0.0.1", "::1"}:
            return
        job = _load_job(raw_job_id)
        if not job or _active_job_id() != raw_job_id:
            return
        token = _COPY_JOB.set(raw_job_id)
        g.pincabos_batch_live_v4_token = token

    @app.teardown_request
    def pincabos_batch_live_v4_clear_copy_context(_error: BaseException | None = None) -> None:
        token = getattr(g, "pincabos_batch_live_v4_token", None)
        if token is not None:
            try:
                _COPY_JOB.reset(token)
            except (LookupError, ValueError):
                pass

    @app.route("/api/batch-export/live/start", methods=["POST"])
    def pincabos_batch_live_v4_start() -> Any:
        payload = request.get_json(silent=True) or {}
        try:
            fields = _validate_fields(payload.get("fields"))
            tables = _selected_tables(fields)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

        _ensure_run_dir()
        LOCK_PATH.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
        lock_fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_RDWR, 0o660)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(lock_fd)
            return jsonify({"ok": False, "error": "Un export est déjà actif.", "active_job_id": _active_job_id()}), 409

        job_id = uuid.uuid4().hex
        job = {
            "id": job_id,
            "state": "queued",
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
            "started_at": None,
            "finished_at": None,
            "selected_tables": tables,
            "total_tables": len(tables),
            "completed_tables": 0,
            "completed_names": [],
            "current_table": tables[0],
            "current_package": "",
            "events": [],
            "result_excerpt": "",
            "error": "",
        }
        _progress(job, "En file", current=tables[0], percent=2)
        _event(job, f"Job créé : {len(tables)} table(s) sélectionnée(s).")
        _event(job, "Le moteur V1 créera un fichier .PinCabOS individuel pour chaque table.")
        _save_job(job)
        _set_active(job_id)
        worker = threading.Thread(
            target=_run_v1,
            args=(job_id, fields, lock_fd),
            name=f"pincabos-batch-live-v4-{job_id[:8]}",
            daemon=True,
        )
        worker.start()
        return jsonify({"ok": True, "job": _public_job(job)}), 202

    # PINCABOS_BATCH_LIVE_STOP_ENDPOINT_V11
    @app.route("/api/batch-export/live/stop/<job_id>", methods=["POST"])
    def pincabos_batch_live_stop(job_id: str) -> Any:
        job = _load_job(job_id)
        if not job:
            return jsonify({"ok": False, "error": "Job introuvable."}), 404
        if _active_job_id() != job_id or str(job.get("state", "")).lower() not in {"queued", "running", "stopping"}:
            return jsonify({"ok": False, "error": "Ce job n’est plus actif.", "job": _public_job(job)}), 409
        if not job.get("stop_requested"):
            job["stop_requested"] = True
            job["state"] = "stopping"
            _progress(job, "Arrêt demandé", current=str(job.get("current_table", "") or ""), percent=int((job.get("progress") or {}).get("percent", 0) or 0))
            _event(job, "Arrêt demandé par l’utilisateur. Le package déjà en cours peut se terminer; le suivant ne sera pas copié.", "warning")
            _save_job(job)
        return jsonify({"ok": True, "job": _public_job(job)}), 202

    @app.route("/api/batch-export/live/status/<job_id>", methods=["GET"])
    def pincabos_batch_live_v4_status(job_id: str) -> Any:
        job = _load_job(job_id)
        if not job:
            return jsonify({"ok": False, "error": "Job introuvable."}), 404
        return jsonify({"ok": True, "job": _public_job(job)})

    @app.route("/api/batch-export/live/history", methods=["GET"])
    def pincabos_batch_live_v4_history() -> Any:
        _ensure_run_dir()
        records: list[dict[str, Any]] = []
        paths = sorted(RUN_DIR.glob("job-*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
        for path in paths[:MAX_HISTORY]:
            job = _read_json(path, None)
            if isinstance(job, dict):
                records.append(_public_job(job))
        return jsonify({"ok": True, "active_job_id": _active_job_id(), "jobs": records})

    # PINCABOS_BATCH_LIVE_MENU_GLOBAL_REENABLE_V7
    @app.after_request
    def pincabos_batch_live_v5_inject_ui(response: Any) -> Any:
        # Native Import/Export Centers must suppress only the obsolete large
        # Batch page console. The compact status card must still be injected
        # into normal HTML pages so it can render in the main navigation menu.
        if request.method != "GET":
            return response
        if "text/html" not in (response.headers.get("Content-Type") or "").lower():
            return response
        try:
            body = response.get_data(as_text=True)
        except Exception:
            return response
        closing = body.lower().rfind("</body>")
        if closing < 0:
            return response
        additions: list[str] = []
        native_centers = bool(app.config.get("PINCABOS_IMPEXP_NATIVE_UI"))
        if (
            not native_centers
            and request.path == "/tools/batch-export"
            and "PINCABOS_BATCH_LIVE_V6_BATCH_UI" not in body
        ):
            additions.append(_BATCH_UI)
        if "PINCABOS_BATCH_LIVE_V6_MENU" not in body:
            additions.append(_GLOBAL_UI)
        if not additions:
            return response
        response.set_data(body[:closing] + "".join(additions) + body[closing:])
        response.headers.pop("Content-Length", None)
        return response

_BATCH_UI = r'''
<!-- PINCABOS_BATCH_LIVE_V6_BATCH_UI -->
<style>
#pcos-bxp5-message { display:none; margin:10px 0 0; padding:9px 11px; border-left:3px solid #ff7a00; border-radius:0 7px 7px 0; background:rgba(255,122,0,.13); color:#fff; font-size:.9em; line-height:1.35; }
#pcos-bxp5-message.pcos-bxp5-error { border-left-color:#ff6f61; background:rgba(190,45,45,.16); }
[data-pcos-bxp5-submit='1'] { position:relative; }
</style>
<script>
(() => {
  if (window.__pcosBatchLiveV5Page) return;
  window.__pcosBatchLiveV5Page = true;
  let starting = false;
  let boundForm = null;
  let message = null;

  function findExportForm() {
    const controls = Array.from(document.querySelectorAll('[name="table_folder"]'));
    for (const control of controls) {
      if (control.form) return control.form;
    }
    for (const form of Array.from(document.forms)) {
      try { if (new FormData(form).has('table_folder')) return form; } catch (_) {}
    }
    return Array.from(document.forms).find((form) => /batch-export/.test(String(form.getAttribute('action') || ''))) || null;
  }

  function selected(form) {
    return Array.from(new FormData(form).getAll('table_folder')).map(String).filter(Boolean);
  }

  function messageNode(button) {
    if (message) return message;
    message = document.getElementById('pcos-bxp5-message');
    if (!message) {
      message = document.createElement('div');
      message.id = 'pcos-bxp5-message';
      message.setAttribute('aria-live', 'polite');
      (button && button.parentElement ? button.parentElement : document.body).appendChild(message);
    }
    return message;
  }

  function say(text, isError, button) {
    const node = messageNode(button);
    node.textContent = text;
    node.classList.toggle('pcos-bxp5-error', Boolean(isError));
    node.style.display = 'block';
  }

  function submitters(form) {
    return Array.from(form.querySelectorAll('button, input[type="submit"], input[type="image"]')).filter((button) => {
      const label = String(button.value || button.textContent || '').trim();
      const type = String(button.getAttribute('type') || '').toLowerCase();
      return type === 'submit' || type === '' || /\b(batch|export|exporter)\b/i.test(label);
    }).filter((button) => /\b(batch|export|exporter)\b/i.test(String(button.value || button.textContent || '')) || String(button.getAttribute('type') || '').toLowerCase() === 'submit');
  }

  function setButtons(form, disabled) {
    for (const button of submitters(form)) {
      button.disabled = disabled;
      button.dataset.pcosBxp5Submit = '1';
      if (button.tagName === 'INPUT') button.value = disabled ? 'Export en préparation…' : 'Lancer en arrière-plan';
      else button.textContent = disabled ? 'Export en préparation…' : 'Lancer en arrière-plan';
    }
  }

  async function requestJson(url, options) {
    const response = await fetch(url, Object.assign({cache:'no-store'}, options || {}));
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) {
      const error = new Error(payload.error || ('HTTP ' + response.status));
      error.payload = payload;
      throw error;
    }
    return payload;
  }

  async function start(form, button) {
    if (starting) return;
    const tables = selected(form);
    if (!tables.length) {
      say('Sélectionne au moins une table avant de lancer l’export.', true, button);
      return;
    }
    starting = true;
    setButtons(form, true);
    say('Mise en file de ' + tables.length + ' table(s)… Le statut apparaîtra dans le menu supérieur.', false, button);
    try {
      const fields = Array.from(new FormData(form).entries()).map(([key, value]) => [String(key), String(value)]);
      const payload = await requestJson('/api/batch-export/live/start', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({fields})
      });
      const total = Number((payload.job || {}).total_tables || tables.length);
      say('Export lancé en arrière-plan : 0 / ' + total + ' package. Le suivi est visible dans le menu.', false, button);
      window.dispatchEvent(new CustomEvent('pcos-batch-live-started', {detail: payload.job || {}}));
    } catch (error) {
      const active = error.payload && error.payload.active_job_id;
      say(active ? 'Un export est déjà actif. Son suivi est visible dans le menu.' : ('Lancement impossible : ' + error.message), true, button);
      setButtons(form, false);
    } finally {
      starting = false;
    }
  }

  function wire() {
    const form = findExportForm();
    if (!form || form === boundForm) return;
    boundForm = form;
    for (const button of submitters(form)) {
      button.dataset.pcosBxp5Submit = '1';
      if (button.tagName === 'INPUT') button.value = 'Lancer en arrière-plan';
      else button.textContent = 'Lancer en arrière-plan';
      button.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopImmediatePropagation();
        start(form, button);
      }, true);
    }
  }

  document.addEventListener('submit', (event) => {
    const form = findExportForm();
    if (!form || event.target !== form) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    start(form, event.submitter || submitters(form)[0] || null);
  }, true);
  wire();
  requestAnimationFrame(wire);
  window.setTimeout(wire, 250);
  window.setTimeout(wire, 1000);
})();
</script>
'''

_GLOBAL_UI = r'''
<!-- PINCABOS_BATCH_LIVE_V6_MENU_IN_LANGUAGE_V2 -->
<!-- PINCABOS_BATCH_LIVE_MENU_EXPLICIT_TOGGLE_V5 -->
<style>
.pco-impexp-menu-status{display:none;width:100%;overflow:hidden;padding:9px 10px;border:1px solid rgba(255,142,35,.78);border-radius:10px;background:linear-gradient(125deg,rgba(42,16,9,.98),rgba(42,16,57,.98));box-shadow:inset 0 0 18px rgba(0,0,0,.28);color:#fff;cursor:pointer;text-align:left;font:inherit}
.pco-impexp-menu-status[aria-hidden='false']{display:block}.pco-impexp-menu-status:hover{filter:brightness(1.12)}.pco-impexp-menu-status *{box-sizing:border-box}
.pco-impexp-menu-status .pcos-bxp6-titleline{display:flex;align-items:center;justify-content:space-between;gap:8px}.pco-impexp-menu-status .pcos-bxp6-title{display:flex;align-items:center;gap:7px;color:#fff1df;font-size:.72rem;font-weight:900;letter-spacing:.055em;text-transform:uppercase}.pco-impexp-menu-status .pcos-bxp6-orb{width:8px;height:8px;flex:0 0 auto;border-radius:50%;background:#ffc164;box-shadow:0 0 0 4px rgba(255,193,100,.16);animation:pcos-bxp6-pulse 1.35s ease-in-out infinite}.pco-impexp-menu-status .pcos-bxp6-pct{color:#ffd087;font-size:1rem;font-weight:900;line-height:1}.pco-impexp-menu-status .pcos-bxp6-current{overflow:hidden;margin-top:5px;color:#fff;font-size:.80rem;font-weight:700;line-height:1.2;text-overflow:ellipsis;white-space:nowrap}.pco-impexp-menu-status .pcos-bxp6-counter{margin-top:3px;color:#dacddd;font-size:.74rem}.pco-impexp-menu-status .pcos-bxp6-track{display:block;height:6px;margin-top:8px;overflow:hidden;border-radius:999px;background:rgba(255,255,255,.16)}.pco-impexp-menu-status .pcos-bxp6-bar{display:block;width:0%;height:100%;border-radius:inherit;background:linear-gradient(90deg,#ff7a00,#ffd06b);box-shadow:0 0 12px rgba(255,122,0,.55);transition:width .35s ease}@keyframes pcos-bxp6-pulse{50%{opacity:.42;transform:scale(.72)}}
</style>
<script>
(()=>{
  if(window.__pcosBatchLiveV6MainMenuV5)return;
  window.__pcosBatchLiveV6MainMenuV5=true;
  let timer=null;
  // PINCABOS_BATCH_LIVE_STOP_BUTTON_V11
  // PINCABOS_BATCH_LIVE_BODY_HOST_V10
  const host=()=>{
    let root=document.getElementById('pco-impexp-live-overlay-root');
    if(root)return root;
    root=document.createElement('div');
    root.id='pco-impexp-live-overlay-root';
    root.setAttribute('aria-live','polite');
    document.body.appendChild(root);
    return root;
  };
  const syncRow=()=>{
    const root=host();
    const shown=root.querySelectorAll('.pco-impexp-menu-status[aria-hidden="false"]').length>0;
    root.classList.toggle('is-active',shown);
  };
  function ensureCard(){
    let card=document.getElementById('pcos-bxp6-language-status');
    if(card)return card;
    card=document.createElement('button');
    card.type='button';
    card.id='pcos-bxp6-language-status';
    card.className='pco-impexp-menu-status';
    card.setAttribute('aria-hidden','true');
    card.setAttribute('aria-label','Open Batch Export progress');
    card.innerHTML='<span class="pcos-bxp6-titleline"><span class="pcos-bxp6-title"><span class="pcos-bxp6-orb"></span>Active export</span><span class="pcos-bxp6-actions"><strong id="pcos-bxp6-pct" class="pcos-bxp6-pct">0%</strong><button type="button" id="pcos-bxp6-stop" class="pcos-live-stop" aria-label="Stop active export">Stop</button></span></span><span id="pcos-bxp6-current" class="pcos-bxp6-current">Preparing…</span><span id="pcos-bxp6-counter" class="pcos-bxp6-counter">0 / 0 packages</span><span class="pcos-bxp6-track"><span id="pcos-bxp6-bar" class="pcos-bxp6-bar"></span></span>';
    card.addEventListener('click',(event)=>{
      if(event.target && event.target.closest('.pcos-live-stop'))return;
      window.location.assign('/tools/export-table');
    });
    card.querySelector('#pcos-bxp6-stop').addEventListener('click',async(event)=>{
      event.preventDefault();event.stopPropagation();
      const jobId=card.dataset.jobId||'';
      if(!jobId)return;
      const button=event.currentTarget;
      button.disabled=true;button.textContent='Stopping…';
      try{await json('/api/batch-export/live/stop/'+encodeURIComponent(jobId),{method:'POST'});}
      catch(error){button.disabled=false;button.textContent='Stop';window.alert(error.message||'Unable to stop the export.');}
    });
    const target=host();
    if(target)target.appendChild(card);
    return card;
  }
  function hide(){
    const card=document.getElementById('pcos-bxp6-language-status');
    if(card)card.setAttribute('aria-hidden','true');
    syncRow();
  }
  function render(job){
    if(!job||!['queued','running'].includes(String(job.state||''))){hide();return;}
    const card=ensureCard();
    if(!card||!card.parentElement){syncRow();return;}
    const progress=job.progress||{};
    const percent=Math.max(0,Math.min(100,Number(progress.percent||0)));
    const total=Number(progress.total||job.total_tables||0);
    const done=Number(progress.completed||job.completed_tables||0);
    const current=String(progress.current_table||job.current_table||'Preparing…');
    card.querySelector('#pcos-bxp6-pct').textContent=percent+'%';
    card.querySelector('#pcos-bxp6-current').textContent=current;
    card.querySelector('#pcos-bxp6-counter').textContent=done+' / '+total+(total===1?' package':' packages');
    card.dataset.jobId=String(job.id||'');
    const stopButton=card.querySelector('#pcos-bxp6-stop');
    const stopping=Boolean(job.stop_requested)||String(job.state||'')==='stopping';
    stopButton.disabled=stopping;
    stopButton.textContent=stopping?'Stopping…':'Stop';
    card.querySelector('#pcos-bxp6-bar').style.width=percent+'%';
    card.setAttribute('aria-hidden','false');
    syncRow();
  }
  async function json(url,options={}){
    const response=await fetch(url,{cache:'no-store',...options});
    const payload=await response.json().catch(()=>({}));
    if(!response.ok||payload.ok===false)throw new Error(payload.error||('HTTP '+response.status));
    return payload;
  }
  async function poll(){
    try{
      const history=await json('/api/batch-export/live/history');
      if(!history.active_job_id){hide();return;}
      const status=await json('/api/batch-export/live/status/'+encodeURIComponent(history.active_job_id));
      render(status.job);
    }catch(_){hide();}
  }
  function start(){
    if(timer)window.clearInterval(timer);
    poll();
    timer=window.setInterval(poll,1000);
  }
  window.addEventListener('pcos-batch-live-started',poll);
  start();
})();
</script>
'''
