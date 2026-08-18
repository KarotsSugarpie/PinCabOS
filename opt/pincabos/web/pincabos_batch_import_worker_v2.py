from __future__ import annotations

import fcntl
import html
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import zipfile
import time
import traceback
from pathlib import Path
from typing import Any

import pincabos_batch_import_queue_v2 as queue

WEB_URL = os.environ.get("PINCABOS_BATCH_IMPORT_INTERNAL_URL", "http://127.0.0.1/tools/batch-import/run")
INTERNAL_HEADER = "X-PinCabOS-Batch-Import-Live"
ENGINE_IMPORT_ROOT = Path("/opt/pincabos/uploads/batch-import")
HEARTBEAT_PATH = queue.RUN_DIR / "worker-heartbeat.json"
POLL_SECONDS = 1.0
RUNNING = True


def log(message: str) -> None:
    print(f"[{queue.utc_now()}] {message}", flush=True)


def heartbeat(state: str, job_id: str = "", detail: str = "") -> None:
    queue.atomic_write(HEARTBEAT_PATH, {
        "at": queue.utc_now(),
        "pid": os.getpid(),
        "state": state,
        "job_id": job_id,
        "detail": detail,
    })


def compact_html(value: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script\s*>", " ", value, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style\s*>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return html.unescape(re.sub(r"\s+", " ", text).strip())[:4000]


def engine_dirs() -> set[Path]:
    try:
        return {path.resolve() for path in ENGINE_IMPORT_ROOT.iterdir() if path.is_dir()}
    except FileNotFoundError:
        return set()
    except Exception:
        return set()


def cleanup_new_engine_dirs(before: set[Path]) -> list[str]:
    removed: list[str] = []
    try:
        root = ENGINE_IMPORT_ROOT.resolve()
    except Exception:
        return removed
    for path in sorted(engine_dirs() - before, key=lambda item: len(str(item)), reverse=True):
        try:
            resolved = path.resolve()
            if resolved != root and root in resolved.parents:
                shutil.rmtree(resolved, ignore_errors=False)
                removed.append(resolved.name)
        except Exception as exc:
            log(f"NOGO cleanup moteur {path}: {exc}")
    return removed


def classify_response(status: int, body: str, curl_code: int) -> tuple[str, str, str]:
    excerpt = compact_html(body)
    folded = excerpt.casefold()

    # PINCABOS_ARCHIVE_INVALID_MESSAGE_V1
    # Archive tronquee ou corrompue : le motif exact ne vivait que dans un
    # journal serveur, l'utilisateur ne voyait qu'une erreur generique et
    # soupconnait son installation.
    if "pincabos_archive_invalide" in folded or "not a zip file" in folded or "badzipfile" in folded:
        return (
            "failed",
            "Archive invalide ou incomplète (ce n'est pas une archive ZIP lisible)",
            "Le fichier reçu n'est pas une archive ZIP exploitable : "
            "téléchargement ou copie incomplète. Récupérez à nouveau ce paquet "
            "avant de le réimporter.",
        )

    if curl_code != 0:
        return "failed", "Erreur de communication WebApp", excerpt
    if status < 200 or status >= 300:
        return "failed", f"HTTP {status}", excerpt
    if "batch import interrompu" in folded or "batch import impossible" in folded:
        return "failed", "Moteur Import interrompu", excerpt
    if " erreur " in f" {folded} " or "class=bad" in folded:
        return "failed", "Erreur signalée par le moteur", excerpt
    if "refusé" in folded or "ignoré" in folded or "vérification" in folded:
        return "warning", "Package terminé avec avertissement", excerpt
    if "succès" in folded or "batch import terminé" in folded:
        return "success", "Package importé", excerpt
    return "warning", "Réponse terminée à vérifier", excerpt


def call_engine(job_id: str, conflict_mode: str, item: dict[str, Any]) -> tuple[int, int, str]:
    source = Path(str(item.get("path", "")))
    name = str(item.get("name", source.name))
    if not source.is_file():
        return 2, 0, f"Archive temporaire introuvable : {source}"

    # PINCABOS_ARCHIVE_INVALID_MESSAGE_V1 : on refuse tout de suite une archive
    # illisible, plutot que de la televerser au moteur pour rien.
    if not zipfile.is_zipfile(source):
        return 0, 200, "PINCABOS_ARCHIVE_INVALIDE"
    with tempfile.NamedTemporaryFile(prefix="pincabos-biq-v2-response-", suffix=".html", delete=False) as temp:
        response_path = Path(temp.name)
    try:
        command = [
            "/usr/bin/curl",
            "--silent",
            "--show-error",
            "--connect-timeout", "15",
            "--max-time", "21600",
            "--output", str(response_path),
            "--write-out", "%{http_code}",
            "--header", f"{INTERNAL_HEADER}: {job_id}",
            "--form-string", f"conflict_mode={conflict_mode}",
            "--form", f"archives=@{source};filename={name}",
            WEB_URL,
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        try:
            status = int((result.stdout or "0").strip()[-3:])
        except ValueError:
            status = 0
        body = response_path.read_text(encoding="utf-8", errors="replace") if response_path.exists() else ""
        if result.stderr:
            body = body + "\n" + result.stderr.strip()
        return int(result.returncode), status, body
    finally:
        try:
            response_path.unlink()
        except FileNotFoundError:
            pass


def mark_running(job_id: str) -> dict[str, Any] | None:
    with queue.state_lock(True):
        job = queue.load_job_unlocked(job_id)
        if not job or str(job.get("state")) not in {"uploading", "queued", "running"}:
            return None
        first_start = not bool(job.get("started_at"))
        job["state"] = "running"
        job["started_at"] = job.get("started_at") or queue.utc_now()
        job["error"] = ""
        if first_start:
            queue.add_event(job, "Worker systemd V2 démarré; traitement strictement séquentiel.")
        queue.refresh_progress(job, "Worker prêt pour le prochain package")
        queue.save_job_unlocked(job)
        queue.set_active_unlocked(job_id)
        return job


def set_item_phase(job_id: str, item: dict[str, Any], label: str) -> dict[str, Any] | None:
    index = int(item.get("index", 0) or 0)
    name = str(item.get("name", "Package"))
    with queue.state_lock(True):
        job = queue.load_job_unlocked(job_id)
        if not job:
            return None
        job["current_index"] = index
        job["current_item"] = name
        for saved in job.get("uploads", []) or []:
            if int(saved.get("index", 0) or 0) == index:
                saved["state"] = "running"
                saved["detail"] = label
                break
        queue.refresh_progress(job, label, name)
        queue.add_event(job, f"Package {index}/{job.get('total_archives', 0)} : {name} — {label}")
        queue.save_job_unlocked(job)
        return job


def finish_item(job_id: str, item: dict[str, Any], outcome: str, detail: str, excerpt: str, removed: list[str]) -> dict[str, Any] | None:
    index = int(item.get("index", 0) or 0)
    name = str(item.get("name", "Package"))
    source = Path(str(item.get("path", "")))
    try:
        source.unlink()
    except FileNotFoundError:
        pass
    except Exception as exc:
        detail += f"; nettoyage archive impossible: {exc}"
    with queue.state_lock(True):
        job = queue.load_job_unlocked(job_id)
        if not job:
            return None
        for saved in job.get("uploads", []) or []:
            if int(saved.get("index", 0) or 0) == index:
                saved["state"] = outcome
                saved["detail"] = detail
                saved["path"] = ""
                break
        job["processed_archives"] = max(int(job.get("processed_archives", 0) or 0), index)
        if outcome == "success":
            job["successful_archives"] = int(job.get("successful_archives", 0) or 0) + 1
            level = "info"
        elif outcome == "warning":
            job["warning_archives"] = int(job.get("warning_archives", 0) or 0) + 1
            level = "warning"
        else:
            job["failed_archives"] = int(job.get("failed_archives", 0) or 0) + 1
            level = "error"
        job["result_excerpt"] = excerpt
        cleanup_text = f"; temporaires supprimés: {', '.join(removed)}" if removed else ""
        queue.add_event(job, f"{name} : {detail}{cleanup_text}", level)
        queue.refresh_progress(job, detail, name)
        queue.save_job_unlocked(job)
        return job


def finalize_job(job_id: str, stopped: bool = False) -> None:
    with queue.state_lock(True):
        job = queue.load_job_unlocked(job_id)
        if not job:
            queue.set_active_unlocked(None)
            return
        job["current_item"] = ""
        job["finished_at"] = queue.utc_now()
        if stopped or job.get("stop_requested"):
            job["state"] = "stopped"
            label = "Arrêté proprement"
            queue.add_event(job, "Import arrêté; les packages non traités ont été supprimés.", "warning")
        elif int(job.get("failed_archives", 0) or 0) or int(job.get("warning_archives", 0) or 0):
            job["state"] = "completed_with_warning"
            label = "Terminé avec avertissement"
            queue.add_event(job, "File terminée; consulte les compteurs et le journal.", "warning")
        else:
            job["state"] = "completed"
            label = "Terminé"
            queue.add_event(job, "Tous les packages ont été traités et nettoyés.")
        queue.refresh_progress(job, label, "")
        queue.cleanup_uploads(job)
        queue.save_job_unlocked(job)
        if queue.active_job_id_unlocked() == job_id:
            queue.set_active_unlocked(None)


def fail_job(job_id: str, error: str) -> None:
    with queue.state_lock(True):
        job = queue.load_job_unlocked(job_id)
        if not job:
            queue.set_active_unlocked(None)
            return
        job["state"] = "failed"
        job["error"] = error
        job["finished_at"] = queue.utc_now()
        queue.add_event(job, error, "error")
        queue.refresh_progress(job, "Erreur du worker")
        queue.cleanup_uploads(job)
        queue.save_job_unlocked(job)
        if queue.active_job_id_unlocked() == job_id:
            queue.set_active_unlocked(None)


def process_job(job_id: str) -> None:
    job = mark_running(job_id)
    if not job:
        return
    conflict_mode = str(job.get("conflict_mode", "skip") or "skip")

    while RUNNING:
        current = queue.load_job(job_id)
        if not current:
            return
        if current.get("stop_requested"):
            finalize_job(job_id, stopped=True)
            return

        items = sorted(
            [item for item in (current.get("uploads") or []) if isinstance(item, dict)],
            key=lambda item: int(item.get("index", 0) or 0),
        )
        pending = next((item for item in items if str(item.get("state", "")) == "queued"), None)

        if pending is None:
            total = int(current.get("total_archives", 0) or 0)
            done = int(current.get("processed_archives", 0) or 0)
            if current.get("uploads_complete"):
                if done >= total:
                    finalize_job(job_id)
                else:
                    fail_job(job_id, f"File incomplète : {done}/{total} package(s) traités.")
                return

            def waiting(job: dict[str, Any]) -> None:
                job["current_item"] = ""
                queue.refresh_progress(job, "En attente du package suivant", "")
            queue.update_job(job_id, waiting)
            heartbeat("waiting-upload", job_id, f"{done}/{total}")
            return

        item = pending
        set_item_phase(job_id, item, "Validation, extraction, manifest et installation")
        heartbeat("running", job_id, str(item.get("name", "")))
        before = engine_dirs()
        curl_code, status, body = call_engine(job_id, conflict_mode, item)
        removed = cleanup_new_engine_dirs(before)
        outcome, detail, excerpt = classify_response(status, body, curl_code)
        finish_item(job_id, item, outcome, detail, excerpt, removed)
        log(f"{outcome.upper()} {item.get('index')}/{current.get('total_archives')} {item.get('name')}: {detail}")

        current = queue.load_job(job_id)
        if current and current.get("stop_requested"):
            finalize_job(job_id, stopped=True)
            return


def cleanup_stale_engine_dirs(min_age_seconds: int = 3600) -> list[str]:
    """PINCABOS_BATCH_ORPHAN_GC_V1

    Extractions laissees a mi-chemin par un import interrompu : elles font
    echouer les tentatives suivantes sur la MEME table. On ne prend que celles
    d'au moins une heure, et seulement si le moteur est libre — jamais un
    import en cours, y compris lance depuis la page Smart Import.
    """
    removed: list[str] = []
    lock_fd = acquire_engine_lock()
    if lock_fd is None:
        return removed
    try:
        now = time.time()
        for path in engine_dirs():
            try:
                if now - path.stat().st_mtime < min_age_seconds:
                    continue
                shutil.rmtree(path)
                removed.append(path.name)
            except OSError:
                pass
    finally:
        release_engine_lock(lock_fd)
    return removed


def acquire_engine_lock() -> int | None:
    queue.SHARED_ENGINE_LOCK.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
    fd = os.open(str(queue.SHARED_ENGINE_LOCK), os.O_CREAT | os.O_RDWR, 0o660)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except BlockingIOError:
        os.close(fd)
        return None


def release_engine_lock(fd: int) -> None:
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def stop_signal(signum: int, _frame: Any) -> None:
    global RUNNING
    RUNNING = False
    log(f"Signal {signum} reçu; arrêt après la frontière sécurisée.")


def main() -> int:
    signal.signal(signal.SIGTERM, stop_signal)
    signal.signal(signal.SIGINT, stop_signal)
    queue.ensure_dirs()
    queue.recover_after_restart()

    # PINCABOS_BATCH_ORPHAN_GC_V1 : restes des imports interrompus.
    for name in queue.collect_orphan_uploads():
        log(f"Menage: archives televersees abandonnees supprimees ({name})")
    for name in cleanup_stale_engine_dirs():
        log(f"Menage: extraction inachevee supprimee ({name})")

    heartbeat("idle")
    log("GO worker Batch Import V2 actif")

    while RUNNING:
        try:
            job_id = queue.next_queued_job_id()
            if not job_id:
                heartbeat("idle")
                time.sleep(POLL_SECONDS)
                continue
            job = queue.load_job(job_id)

            # PINCABOS_BATCH_IMPORT_STOPPING_FIX_V1
            # Un travail dont l'arrêt est demandé doit être finalisé ici.
            # Sans ce contrôle, l'état "stopping" est ignoré indéfiniment.
            if not job:
                heartbeat("waiting", job_id, "missing")
                time.sleep(POLL_SECONDS)
                continue

            state = str(job.get("state", ""))

            if state == "stopping" or bool(job.get("stop_requested")):
                heartbeat(
                    "stopping",
                    job_id,
                    "Finalisation de l'arrêt demandé",
                )
                finalize_job(job_id, stopped=True)
                continue

            if state not in {"uploading", "queued", "running"}:
                heartbeat("waiting", job_id, state)
                time.sleep(POLL_SECONDS)
                continue

            lock_fd = acquire_engine_lock()
            if lock_fd is None:
                heartbeat("waiting-shared-lock", job_id, "Import/Export déjà actif")
                time.sleep(2.0)
                continue
            try:
                process_job(job_id)
            except Exception as exc:
                error = f"Worker V2: {exc}"
                log("NOGO " + error)
                log(traceback.format_exc())
                fail_job(job_id, error)
            finally:
                release_engine_lock(lock_fd)
        except Exception as exc:
            log(f"NOGO boucle worker: {exc}")
            log(traceback.format_exc())
            heartbeat("error", detail=str(exc))
            time.sleep(2.0)

    heartbeat("stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
