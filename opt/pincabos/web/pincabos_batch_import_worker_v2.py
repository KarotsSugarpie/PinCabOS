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
    # PINCABOS_SMART_BATCH_BEST_EFFORT_V1
    excerpt = compact_html(body)
    folded = excerpt.casefold()

    # Erreur propre au package : on l'ignore et on continue.
    if "pincabos_archive_invalide" in folded or "not a zip file" in folded or "badzipfile" in folded:
        return (
            "failed",
            "Archive invalide ou incomplète (ce n'est pas une archive ZIP lisible)",
            "Le fichier reçu n'est pas une archive ZIP exploitable : "
            "téléchargement ou copie incomplète. Le package sera ignoré et "
            "le Batch poursuivra avec le suivant.",
        )

    # Une table déjà présente n'est pas une erreur.
    already_present_tokens = (
        "table déjà installée",
        "table deja installee",
        "existe déjà",
        "existe deja",
        "import skip",
    )
    if any(token in folded for token in already_present_tokens):
        return "skipped", "Table déjà installée — ignorée automatiquement", excerpt

    # Une archive temporaire manquante ne doit pas bloquer les suivantes.
    if "archive temporaire introuvable" in folded:
        return "failed", "Archive temporaire introuvable — package ignoré", excerpt

    # Erreurs globales : continuer ferait probablement échouer toute la file.
    fatal_tokens = (
        "no space left on device",
        "disk quota exceeded",
        "quota exceeded",
        "read-only file system",
        "filesystem full",
        "file system full",
        "input/output error",
    )
    if curl_code != 0:
        return "fatal", "Erreur de communication WebApp", excerpt
    if status in {502, 503, 504, 507}:
        return "fatal", f"HTTP {status} — service ou stockage indisponible", excerpt
    if any(token in folded for token in fatal_tokens):
        return "fatal", "Erreur système ou stockage indisponible", excerpt

    # Les autres erreurs appartiennent au package courant : auto-skip.
    if status < 200 or status >= 300:
        return "failed", f"HTTP {status}", excerpt
    if "batch import interrompu" in folded or "batch import impossible" in folded:
        return "failed", "Moteur Import interrompu pour ce package", excerpt
    if " erreur " in f" {folded} " or "class=bad" in folded:
        return "failed", "Erreur signalée par le moteur", excerpt
    if "refusé" in folded or "vérification" in folded:
        return "warning", "Package terminé avec avertissement", excerpt
    if "ignoré" in folded or "ignore" in folded:
        return "skipped", "Package ignoré automatiquement", excerpt
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

        if str(job.get("state", "")) in {
            queue.PAUSED_STATE,
            queue.PAUSING_STATE,
        }:
            return None

        job["current_index"] = index
        job["current_item"] = name

        for saved in job.get("uploads", []) or []:
            if int(saved.get("index", 0) or 0) == index:
                saved["state"] = "running"
                saved["detail"] = label
                break

        queue.refresh_progress(job, label, name)
        queue.add_event(
            job,
            f"Package {index}/{job.get('total_archives', 0)} : "
            f"{name} — {label}",
        )
        queue.save_job_unlocked(job)
        return job


def finish_item(
    job_id: str,
    item: dict[str, Any],
    outcome: str,
    detail: str,
    excerpt: str,
    removed: list[str],
) -> dict[str, Any] | None:
    # PINCABOS_SMART_BATCH_BEST_EFFORT_V1
    index = int(item.get("index", 0) or 0)
    name = str(item.get("name", "Package"))
    source = Path(str(item.get("path", "")))

    # Une vraie panne globale met la file en pause et CONSERVE l'archive.
    # L'utilisateur peut corriger le stockage/service puis Reprendre.
    if outcome == "fatal":
        with queue.state_lock(True):
            job = queue.load_job_unlocked(job_id)
            if not job:
                return None

            for saved in job.get("uploads", []) or []:
                if int(saved.get("index", 0) or 0) == index:
                    saved["state"] = "error"
                    saved["detail"] = detail
                    break

            job["state"] = queue.PAUSED_STATE
            job["pause_requested"] = False
            job["paused_at"] = queue.utc_now()
            job["current_index"] = index
            job["current_item"] = name
            job["error"] = detail
            job["error_attempts"] = int(job.get("error_attempts", 0) or 0) + 1
            job["result_excerpt"] = excerpt

            cleanup_text = (
                f"; temporaires moteur supprimés: {', '.join(removed)}"
                if removed else ""
            )
            queue.add_event(
                job,
                f"PAUSE SÉCURITÉ — {name} : {detail}{cleanup_text}. "
                "Les packages restants sont conservés. Corrige le problème "
                "système puis utilise Reprendre.",
                "error",
            )
            queue.refresh_progress(job, "Erreur système — en pause", name)
            queue.save_job_unlocked(job)

            if queue.active_job_id_unlocked() == job_id:
                queue.set_active_unlocked(None)
            return job

    # Success / warning / skipped / failed local : le package est consommé.
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

        job["processed_archives"] = max(
            int(job.get("processed_archives", 0) or 0),
            index,
        )

        if outcome == "success":
            job["successful_archives"] = int(job.get("successful_archives", 0) or 0) + 1
            level = "info"
        elif outcome == "skipped":
            job["skipped_archives"] = int(job.get("skipped_archives", 0) or 0) + 1
            level = "warning"
        elif outcome == "failed":
            job["failed_archives"] = int(job.get("failed_archives", 0) or 0) + 1
            level = "error"
        else:
            job["warning_archives"] = int(job.get("warning_archives", 0) or 0) + 1
            level = "warning"

        job["error"] = ""
        job["result_excerpt"] = excerpt

        cleanup_text = (
            f"; temporaires supprimés: {', '.join(removed)}"
            if removed else ""
        )

        if outcome == "failed":
            message = (
                f"ERREUR IGNORÉE AUTOMATIQUEMENT — {index}/{job.get('total_archives', 0)} "
                f"{name} : {detail}{cleanup_text}. Passage au package suivant."
            )
        elif outcome == "skipped":
            message = (
                f"SKIP AUTOMATIQUE — {index}/{job.get('total_archives', 0)} "
                f"{name} : {detail}{cleanup_text}. Passage au package suivant."
            )
        else:
            message = f"{name} : {detail}{cleanup_text}"

        queue.add_event(job, message, level)
        queue.refresh_progress(job, detail, name)
        queue.save_job_unlocked(job)
        return job


def refresh_frontend(imported: int) -> str:
    """Relance VPinFE pour qu'il prenne en compte les tables installees.

    PINCABOS_IMPORT_REFRESH_FRONTEND_V1

    Le worker tourne en root : pas de sudo, pas de regle a maintenir.
    """
    if imported <= 0:
        return ""

    try:
        playing = subprocess.run(
            # Le motif vise le binaire, pas la chaine : "VPinballX" tout
            # court se reconnait dans la ligne de commande de qui le cherche.
            ["/usr/bin/pgrep", "-f", "/VPinballX_BGFX[^/]*/VPinballX_BGFX"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).returncode == 0
    except Exception:
        playing = False

    if playing:
        log("Table en cours : frontend non relance.")
        return "Une table est en cours — relance le frontend quand tu auras fini."

    try:
        result = subprocess.run(
            ["/usr/bin/systemctl", "restart", "pincabos-vpinfe.service"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except Exception as exc:
        log(f"Relance du frontend impossible : {exc}")
        return f"Frontend non relance ({exc})."

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        log(f"Relance du frontend en echec : {detail}")
        return f"Frontend non relance ({detail})."

    log("Frontend relance : les nouvelles tables sont visibles.")
    return "Frontend relance — les nouvelles tables sont dans le carrousel."


def finalize_job(job_id: str, stopped: bool = False) -> None:
    with queue.state_lock(True):
        job = queue.load_job_unlocked(job_id)
        if not job:
            queue.set_active_unlocked(None)
            return

        ok_count = int(job.get("successful_archives", 0) or 0)
        skipped_count = int(job.get("skipped_archives", 0) or 0)
        failed_count = int(job.get("failed_archives", 0) or 0)
        warning_count = int(job.get("warning_archives", 0) or 0)
        summary = (
            f"{ok_count} importé(s) · {skipped_count} ignoré(s) · "
            f"{failed_count} erreur(s) ignorée(s) · {warning_count} avertissement(s)"
        )

        job["current_item"] = ""
        job["finished_at"] = queue.utc_now()
        if stopped or job.get("stop_requested"):
            job["state"] = "stopped"
            label = "Arrêté proprement"
            queue.add_event(
                job,
                f"Import arrêté — {summary}. Les packages non traités ont été supprimés.",
                "warning",
            )
        elif failed_count or warning_count or skipped_count:
            job["state"] = "completed_with_warning"
            label = "Terminé avec avertissement"
            queue.add_event(job, f"SMART BATCH TERMINÉ — {summary}.", "warning")
        else:
            job["state"] = "completed"
            label = "Terminé"
            queue.add_event(job, f"SMART BATCH TERMINÉ — {summary}.")

        # PINCABOS_IMPORT_LOCK_V1
        # La relance du frontend attend un service, jusqu'a une minute. La
        # faire ici bloquerait la file entiere pendant ce temps : ni la page
        # ni un autre import ne pourraient lire l'etat. On note seulement
        # qu'elle est a faire, et on la fait le verrou relache.
        relance = ok_count if not stopped and not job.get("stop_requested") else 0

        queue.refresh_progress(job, label, "")
        queue.cleanup_uploads(job)
        queue.save_job_unlocked(job)
        if queue.active_job_id_unlocked() == job_id:
            queue.set_active_unlocked(None)

    # PINCABOS_IMPORT_LOCK_V1 — hors du verrou.
    note = refresh_frontend(relance)
    if note:
        with queue.state_lock(True):
            job = queue.load_job_unlocked(job_id)
            if job:
                queue.add_event(job, note)
                queue.save_job_unlocked(job)


def fail_job(job_id: str, error: str) -> None:
    # Une exception interne du worker est une panne globale potentielle.
    # On conserve donc la file au lieu de supprimer les uploads restants.
    with queue.state_lock(True):
        job = queue.load_job_unlocked(job_id)
        if not job:
            queue.set_active_unlocked(None)
            return
        job["state"] = queue.PAUSED_STATE
        job["pause_requested"] = False
        job["paused_at"] = queue.utc_now()
        job["finished_at"] = None
        job["error"] = error
        queue.add_event(
            job,
            f"PAUSE SÉCURITÉ — {error}. Les packages restants sont conservés; "
            "corrige le problème puis utilise Reprendre.",
            "error",
        )
        queue.refresh_progress(job, "Erreur système — en pause")
        queue.save_job_unlocked(job)
        if queue.active_job_id_unlocked() == job_id:
            queue.set_active_unlocked(None)


def process_job(job_id: str) -> None:
    # PINCABOS_SMART_BATCH_PIPELINE_V321
    #
    # PIPELINE PRODUCTEUR / CONSOMMATEUR :
    # le navigateur téléverse les packages pendant que le worker traite
    # immédiatement ceux qui sont déjà complètement reçus.
    #
    # Il n'est PLUS nécessaire d'attendre uploads_complete=True.
    # L'absence temporaire de package est gérée plus bas par
    # "En attente du package suivant".
    staging = queue.load_job(job_id)

    if not staging:
        return

    uploaded = int(staging.get("uploaded_archives", 0) or 0)
    total = int(staging.get("total_archives", 0) or 0)

    if uploaded <= 0 and not bool(staging.get("uploads_complete")):
        heartbeat("waiting-upload", job_id, f"0/{total}")
        return

    job = mark_running(job_id)

    if not job:
        return

    # PINCABOS_SMART_BATCH_BEST_EFFORT_V1 : le Live est toujours non destructif.
    conflict_mode = "skip"

    while RUNNING:
        current = queue.load_job(job_id)
        if not current:
            return

        state = str(current.get("state", ""))

        if state == queue.PAUSED_STATE:
            return

        # PINCABOS_WORKER_PAUSING_FIX_V32
        if state == queue.PAUSING_STATE:
            queue.complete_pause(job_id)
            return

        if current.get("stop_requested"):
            finalize_job(job_id, stopped=True)
            return

        items = sorted(
            [
                item
                for item in (current.get("uploads") or [])
                if isinstance(item, dict)
            ],
            key=lambda item: int(item.get("index", 0) or 0),
        )

        pending = next(
            (
                item for item in items
                if str(item.get("state", "")) == "queued"
            ),
            None,
        )

        if pending is None:
            total = int(current.get("total_archives", 0) or 0)
            done = int(current.get("processed_archives", 0) or 0)

            if current.get("uploads_complete"):
                if done >= total:
                    finalize_job(job_id)
                else:
                    fail_job(
                        job_id,
                        f"File incomplète : {done}/{total} package(s) traités.",
                    )
                return

            def waiting(job: dict[str, Any]) -> None:
                job["current_item"] = ""
                queue.refresh_progress(
                    job,
                    "En attente du package suivant",
                    "",
                )

            queue.update_job(job_id, waiting)
            heartbeat("waiting-upload", job_id, f"{done}/{total}")
            return

        item = pending

        phase = set_item_phase(
            job_id,
            item,
            "Validation, extraction, manifest et installation",
        )

        if not phase:
            return

        heartbeat(
            "running",
            job_id,
            str(item.get("name", "")),
        )

        before = engine_dirs()
        curl_code, status, body = call_engine(
            job_id,
            conflict_mode,
            item,
        )
        removed = cleanup_new_engine_dirs(before)
        outcome, detail, excerpt = classify_response(
            status,
            body,
            curl_code,
        )

        finish_item(
            job_id,
            item,
            outcome,
            detail,
            excerpt,
            removed,
        )

        log(
            f"{outcome.upper()} "
            f"{item.get('index')}/{current.get('total_archives')} "
            f"{item.get('name')}: {detail}"
        )

        # Seule une panne système globale arrête la boucle. Une erreur de
        # table/package est enregistrée puis le worker passe au suivant.
        if outcome == "fatal":
            return

        current = queue.load_job(job_id)
        if not current:
            return

        if current.get("stop_requested"):
            finalize_job(job_id, stopped=True)
            return

        if (
            current.get("pause_requested")
            or str(current.get("state", "")) == queue.PAUSING_STATE
        ):
            queue.complete_pause(job_id)
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
