from __future__ import annotations

import datetime as _datetime
import fcntl
import json
import os
import shutil
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

RUN_DIR = Path(os.environ.get("PINCABOS_BATCH_IMPORT_LIVE_DIR", "/var/lib/pincabos/batch-live-import"))
UPLOAD_ROOT = RUN_DIR / "uploads"
ACTIVE_PATH = RUN_DIR / "active.json"
STATE_LOCK_PATH = RUN_DIR / "state.lock"
SHARED_ENGINE_LOCK = Path(os.environ.get("PINCABOS_BATCH_LIVE_SHARED_LOCK", "/var/lib/pincabos/batch-live/export.lock"))
MAX_HISTORY = 40
MAX_ARCHIVES = 1200
ACTIVE_STATES = {"uploading", "queued", "running", "stopping"}
FINAL_STATES = {"completed", "completed_with_warning", "failed", "stopped", "cancelled"}

# PINCABOS_BATCH_FAILSAFE_V1
# "paused" n'est ni actif ni final : le travail ne consomme pas le creneau
# d'execution, mais il reste repris tel quel par resume_job().
PAUSED_STATE = "paused"

# Au-dela de ce delai sans la moindre mise a jour, un travail actif qui n'a
# rien a traiter est considere comme abandonne (onglet ferme, televersement
# interrompu, plantage) : sans cela il gardait le creneau indefiniment.
STALE_SECONDS = int(os.environ.get("PINCABOS_BATCH_STALE_SECONDS", "900"))


def utc_now() -> str:
    return _datetime.datetime.now(_datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_dirs() -> None:
    for path in (RUN_DIR, UPLOAD_ROOT):
        path.mkdir(parents=True, exist_ok=True, mode=0o2770)
        try:
            os.chmod(path, 0o2770)
        except OSError:
            pass


@contextmanager
def state_lock(exclusive: bool = True) -> Iterator[None]:
    ensure_dirs()
    fd = os.open(str(STATE_LOCK_PATH), os.O_CREAT | os.O_RDWR, 0o660)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def atomic_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def job_path(job_id: str) -> Path:
    return RUN_DIR / f"job-{job_id}.json"


def upload_dir(job_id: str) -> Path:
    return UPLOAD_ROOT / job_id


def load_job_unlocked(job_id: str) -> dict[str, Any] | None:
    value = read_json(job_path(job_id), None)
    return value if isinstance(value, dict) else None


def save_job_unlocked(job: dict[str, Any]) -> None:
    job["updated_at"] = utc_now()
    atomic_write(job_path(str(job["id"])), job)


def load_job(job_id: str) -> dict[str, Any] | None:
    with state_lock(False):
        return load_job_unlocked(job_id)


def update_job(job_id: str, callback: Callable[[dict[str, Any]], None]) -> dict[str, Any] | None:
    with state_lock(True):
        job = load_job_unlocked(job_id)
        if not job:
            return None
        callback(job)
        save_job_unlocked(job)
        return job


def active_job_id_unlocked() -> str | None:
    value = read_json(ACTIVE_PATH, {})
    if not isinstance(value, dict):
        return None
    job_id = value.get("job_id")
    return str(job_id) if isinstance(job_id, str) and job_id else None


def active_job_id() -> str | None:
    with state_lock(False):
        return active_job_id_unlocked()


def set_active_unlocked(job_id: str | None) -> None:
    if job_id:
        atomic_write(ACTIVE_PATH, {"job_id": job_id, "updated_at": utc_now()})
    else:
        try:
            ACTIVE_PATH.unlink()
        except FileNotFoundError:
            pass


def add_event(job: dict[str, Any], message: str, level: str = "info") -> None:
    events = job.setdefault("events", [])
    events.append({"at": utc_now(), "level": str(level), "message": str(message)})
    if len(events) > 240:
        del events[:-240]


def refresh_progress(job: dict[str, Any], label: str | None = None, current: str | None = None) -> None:
    total = max(0, int(job.get("total_archives", 0) or 0))
    completed = max(0, min(total, int(job.get("processed_archives", 0) or 0)))
    uploaded = max(0, min(total, int(job.get("uploaded_archives", 0) or 0)))
    state = str(job.get("state", ""))
    if current is not None:
        job["current_item"] = current
    if label is None:
        label = str((job.get("progress") or {}).get("label") or state or "En attente")
    if state == "uploading":
        percent = int((uploaded * 10) / total) if total else 0
    elif total:
        percent = 10 + int((completed * 90) / total)
    else:
        percent = 0
    if state in FINAL_STATES:
        percent = 100
    job["progress"] = {
        "mode": "archives",
        "total": total,
        "uploaded": uploaded,
        "completed": completed,
        "percent": max(0, min(100, percent)),
        "label": str(label),
        "current_item": str(job.get("current_item", "") or ""),
        "successful": int(job.get("successful_archives", 0) or 0),
        "warnings": int(job.get("warning_archives", 0) or 0),
        "failed": int(job.get("failed_archives", 0) or 0),
    }


def public_job(job: dict[str, Any]) -> dict[str, Any]:
    result = dict(job)
    items = []
    for item in job.get("uploads", []) or []:
        if not isinstance(item, dict):
            continue
        items.append({
            "index": item.get("index"),
            "name": item.get("name"),
            "size": item.get("size"),
            "state": item.get("state"),
            "detail": item.get("detail", ""),
        })
    result["uploads"] = items[-40:]
    result.pop("upload_dir", None)
    return result


def list_jobs(limit: int = MAX_HISTORY) -> list[dict[str, Any]]:
    ensure_dirs()
    with state_lock(False):
        paths = sorted(RUN_DIR.glob("job-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        jobs: list[dict[str, Any]] = []
        for path in paths[: max(1, int(limit))]:
            value = read_json(path, None)
            if isinstance(value, dict):
                jobs.append(value)
        return jobs


def create_job(total: int, conflict_mode: str) -> dict[str, Any]:
    total = int(total)
    if total < 1 or total > MAX_ARCHIVES:
        raise ValueError(f"Le nombre de packages doit être entre 1 et {MAX_ARCHIVES}.")
    if conflict_mode not in {"skip", "rename", "replace"}:
        conflict_mode = "skip"
    ensure_dirs()
    with state_lock(True):
        current = active_job_id_unlocked()
        if current:
            current_job = load_job_unlocked(current)
            if current_job and str(current_job.get("state")) in ACTIVE_STATES:
                raise RuntimeError("Un Batch Import est déjà actif.")
            set_active_unlocked(None)
        job_id = uuid.uuid4().hex
        root = upload_dir(job_id)
        root.mkdir(parents=True, exist_ok=False, mode=0o750)
        job: dict[str, Any] = {
            "id": job_id,
            "version": 2,
            "state": "uploading",
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "started_at": None,
            "finished_at": None,
            "total_archives": total,
            "uploaded_archives": 0,
            "processed_archives": 0,
            "successful_archives": 0,
            "warning_archives": 0,
            "failed_archives": 0,
            "current_index": 0,
            "current_item": "",
            "conflict_mode": conflict_mode,
            "stop_requested": False,
            "uploads_complete": False,
            "accepting_uploads": True,
            "last_upload_at": utc_now(),
            "uploads": [],
            "upload_dir": str(root),
            "events": [],
            "result_excerpt": "",
            "error": "",
        }
        add_event(job, f"File créée pour {total} package(s).")
        refresh_progress(job, "Téléversement 0/%d" % total)
        save_job_unlocked(job)
        set_active_unlocked(job_id)
        return job


def job_is_stale(job: dict[str, Any]) -> bool:
    """Travail actif sans la moindre mise a jour depuis STALE_SECONDS."""
    stamp = str(job.get("updated_at") or job.get("started_at") or job.get("created_at") or "")
    if not stamp:
        return True
    try:
        moment = _datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return True
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=_datetime.timezone.utc)
    age = (_datetime.datetime.now(_datetime.timezone.utc) - moment).total_seconds()
    return age > STALE_SECONDS


def pause_job(job_id: str) -> dict[str, Any] | None:
    """Suspend un travail en cours sans perdre ce qui a deja ete traite."""
    with state_lock(True):
        job = load_job_unlocked(job_id)
        if not job:
            return None
        state = str(job.get("state", ""))
        if state in FINAL_STATES or state == PAUSED_STATE:
            return job
        job["state"] = PAUSED_STATE
        job["paused_at"] = utc_now()
        for item in job.get("uploads", []) or []:
            if isinstance(item, dict) and str(item.get("state")) == "running":
                item["state"] = "queued"
                item["detail"] = "Repris à la reprise du travail"
        add_event(job, "Travail mis en pause. Reprise possible à tout moment.", "warning")
        refresh_progress(job, "En pause")
        save_job_unlocked(job)
        if active_job_id_unlocked() == job_id:
            set_active_unlocked(None)
        return job


def resume_job(job_id: str) -> dict[str, Any] | None:
    """Reprend un travail en pause, ou relance ce qui reste d'un travail
    interrompu : les elements deja importes ne sont pas refaits."""
    with state_lock(True):
        job = load_job_unlocked(job_id)
        if not job:
            return None
        remaining = [
            item for item in (job.get("uploads") or [])
            if isinstance(item, dict) and str(item.get("state")) in {"queued", "running", "uploading"}
        ]
        if not remaining:
            return job
        for item in remaining:
            if str(item.get("state")) == "running":
                item["state"] = "queued"
        job["state"] = "queued"
        job["stop_requested"] = False
        job.pop("error", None)
        job.pop("finished_at", None)
        add_event(
            job,
            f"Reprise du travail : {len(remaining)} paquet(s) restant(s).",
            "info",
        )
        refresh_progress(job, "Reprise en file")
        save_job_unlocked(job)
        if not active_job_id_unlocked():
            set_active_unlocked(job_id)
        return job


def collect_orphan_uploads() -> list[str]:
    """PINCABOS_BATCH_ORPHAN_GC_V1

    Archives televersees dont le travail est termine ou n'existe plus : sans
    ce menage, une interruption laissait plusieurs Go sur le disque pour
    toujours.
    """
    ensure_dirs()
    removed: list[str] = []
    try:
        entries = sorted(UPLOAD_ROOT.iterdir())
    except FileNotFoundError:
        return removed

    with state_lock(True):
        for entry in entries:
            if not entry.is_dir():
                continue
            job = load_job_unlocked(entry.name)
            if job is not None and str(job.get("state")) not in FINAL_STATES:
                continue
            try:
                shutil.rmtree(entry)
                removed.append(entry.name)
            except OSError:
                pass
    return removed


def next_queued_job_id() -> str | None:
    ensure_dirs()
    with state_lock(True):
        current = active_job_id_unlocked()
        if current:
            job = load_job_unlocked(current)
            if job and str(job.get("state")) in ACTIVE_STATES:
                pending = any(str(item.get("state", "")) == "queued" for item in (job.get("uploads") or []) if isinstance(item, dict))
                if pending or bool(job.get("uploads_complete")):
                    return current
                # PINCABOS_BATCH_FAILSAFE_V1 : rien a traiter et plus aucune
                # mise a jour depuis longtemps -> le creneau est libere, sinon
                # la file entiere reste bloquee derriere ce travail fantome.
                if job_is_stale(job):
                    job["state"] = "failed"
                    job["finished_at"] = utc_now()
                    job["error"] = "Travail abandonné (téléversement interrompu)."
                    add_event(
                        job,
                        "Travail abandonné : aucune activité depuis "
                        f"{STALE_SECONDS // 60} minutes. Le créneau est libéré.",
                        "warning",
                    )
                    refresh_progress(job, "Abandonné")
                    cleanup_uploads(job)
                    save_job_unlocked(job)
                    set_active_unlocked(None)
                else:
                    return None
            else:
                set_active_unlocked(None)
        paths = sorted(RUN_DIR.glob("job-*.json"), key=lambda p: p.stat().st_mtime)
        for path in paths:
            value = read_json(path, None)
            if isinstance(value, dict) and str(value.get("state")) == "queued":
                set_active_unlocked(str(value["id"]))
                return str(value["id"])
        return None


def cleanup_uploads(job: dict[str, Any]) -> None:
    raw = str(job.get("upload_dir", "") or "")
    if not raw:
        return
    try:
        target = Path(raw).resolve()
        parent = UPLOAD_ROOT.resolve()
        if target != parent and parent in target.parents:
            shutil.rmtree(target, ignore_errors=True)
    except Exception:
        pass


def recover_after_restart() -> None:
    ensure_dirs()
    with state_lock(True):
        current = active_job_id_unlocked()
        if current:
            job = load_job_unlocked(current)
            if job and str(job.get("state")) in {"running", "stopping"}:
                for item in job.get("uploads", []) or []:
                    if isinstance(item, dict) and str(item.get("state")) == "running":
                        item["state"] = "queued"
                        item["detail"] = "Repris après redémarrage"
                if job.get("stop_requested"):
                    job["state"] = "stopped"
                    job["finished_at"] = utc_now()
                    add_event(job, "Arrêt confirmé après redémarrage du worker.", "warning")
                    refresh_progress(job, "Arrêté")
                    cleanup_uploads(job)
                else:
                    job["state"] = "queued"
                    job["current_item"] = ""
                    add_event(job, "Worker redémarré : reprise de la file persistante.", "warning")
                    refresh_progress(job, "Reprise en file")
                save_job_unlocked(job)
            set_active_unlocked(None)
