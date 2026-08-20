#!/bin/bash
set -Eeuo pipefail

clear

echo "==============================================================="
echo " PINCABOS — BATCH CONTROLS V3"
echo " IMPORT + EXPORT"
echo " PAUSE / RESUME / ERROR-PAUSE / SKIP"
echo " BACKUP + GIT + LIVE + VALIDATION"
echo " AUCUN PUSH GITHUB"
echo "==============================================================="
echo

REPO="/opt/pincabos/tmp/pr-integration"
EXPECTED_HEAD="8ee36d43b2db828285db416a00c549b6cee0c983"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="/opt/pincabos/backups/batch-controls-v3-${STAMP}"

FILES=(
  "opt/pincabos/web/pincabos_dashboard_lobby.py"
  "opt/pincabos/web/pincabos_batch_import_live.py"
  "opt/pincabos/web/pincabos_batch_import_queue_v2.py"
  "opt/pincabos/web/pincabos_batch_import_worker_v2.py"
  "opt/pincabos/web/pincabos_batch_live.py"
)

declare -A EXPECTED_HASH

EXPECTED_HASH["opt/pincabos/web/pincabos_dashboard_lobby.py"]="cd452ca21296f764601a9da32115533abf2f0d68c9a1dffdad93c6a7c6ea634b"
EXPECTED_HASH["opt/pincabos/web/pincabos_batch_import_live.py"]="473cd8523e3538997e14acd8026c8ee7a3e2b88022b3ef6c3715f909ebb45167"
EXPECTED_HASH["opt/pincabos/web/pincabos_batch_import_queue_v2.py"]="14f4f182477905ff62fc3b27394171604845e0029d4a517251c1a74f23ce28bf"
EXPECTED_HASH["opt/pincabos/web/pincabos_batch_import_worker_v2.py"]="55897ad2d0bf1155cf9c74a9353e8b5141301111e63707acbec0c111045e1fb3"
EXPECTED_HASH["opt/pincabos/web/pincabos_batch_live.py"]="11652ba1ec26f21786f751e8824529db253850f8a4da6bcd7bc7f352f334a692"

fail()
{
    echo
    echo "==============================================================="
    echo " NOGO [ERREUR] $*"
    echo " AUCUN PUSH GITHUB"
    echo "==============================================================="
    exit 1
}

echo "=== 1. VALIDATION ROOT ==="

[ "$(id -u)" -eq 0 ] || fail "Execute ce script avec sudo -i."

echo "GO [OK] Execution root."
echo

echo "=== 2. VALIDATION REPO ==="

[ -d "$REPO/.git" ] || fail "Depot Git absent : $REPO"

cd "$REPO"

BRANCH="$(git branch --show-current)"
HEAD_NOW="$(git rev-parse HEAD)"

echo "Repo    : $REPO"
echo "Branche : $BRANCH"
echo "HEAD    : $HEAD_NOW"

[ "$BRANCH" = "pincabos-pr-integration" ] || \
    fail "Branche inattendue : $BRANCH"

[ "$HEAD_NOW" = "$EXPECTED_HEAD" ] || \
    fail "HEAD a change depuis l'audit."

[ -z "$(git status --porcelain)" ] || \
    fail "Working tree Git non propre."

echo "GO [OK] Git exactement dans l'etat audite."
echo

echo "=== 3. VALIDATION HASH STAGING + LIVE ==="

for F in "${FILES[@]}"
do
    SRC="$REPO/$F"
    DST="/$F"

    [ -f "$SRC" ] || fail "Source absente : $SRC"
    [ -f "$DST" ] || fail "LIVE absent : $DST"

    SRC_HASH="$(sha256sum "$SRC" | awk '{print $1}')"
    DST_HASH="$(sha256sum "$DST" | awk '{print $1}')"
    WANT="${EXPECTED_HASH[$F]}"

    echo
    echo "$F"
    echo "Attendu : $WANT"
    echo "Staging : $SRC_HASH"
    echo "LIVE    : $DST_HASH"

    [ "$SRC_HASH" = "$WANT" ] || \
        fail "Le staging de $F a change."

    [ "$DST_HASH" = "$WANT" ] || \
        fail "Le LIVE de $F a change."
done

echo
echo "GO [OK] Les 5 fichiers sont exactement ceux de l'audit."
echo

echo "=== 4. PROTECTION VPX ==="

if pgrep -fa VPinballX >/tmp/pincab-batch-v3-vpx.txt 2>/dev/null
then
    cat /tmp/pincab-batch-v3-vpx.txt
    fail "Une table VPX est active."
fi

echo "GO [OK] Aucune table VPX active."
echo

echo "=== 5. PROTECTION BATCH ACTIFS ==="

IMPORT_ACTIVE="$(
curl -s --max-time 5 \
    http://127.0.0.1/api/batch-import/live/active |
python3 -c '
import json,sys
try:
    d=json.load(sys.stdin)
    j=d.get("job")
    print((j or {}).get("id",""))
except Exception:
    print("API_ERROR")
'
)"

[ "$IMPORT_ACTIVE" != "API_ERROR" ] || \
    fail "API Import indisponible."

[ -z "$IMPORT_ACTIVE" ] || \
    fail "Un Batch Import est encore rattache : $IMPORT_ACTIVE"

EXPORT_ACTIVE="$(
curl -s --max-time 5 \
    http://127.0.0.1/api/batch-export/live/history |
python3 -c '
import json,sys
try:
    d=json.load(sys.stdin)
    print(d.get("active_job_id") or "")
except Exception:
    print("API_ERROR")
'
)"

[ "$EXPORT_ACTIVE" != "API_ERROR" ] || \
    fail "API Export indisponible."

[ -z "$EXPORT_ACTIVE" ] || \
    fail "Un Batch Export est encore actif : $EXPORT_ACTIVE"

echo "GO [OK] Aucun Import/Export actif."
echo

echo "=== 6. BACKUP ==="

mkdir -p "$BACKUP"

git branch "backup/pre-batch-controls-v3-${STAMP}"

git bundle create \
    "$BACKUP/staging-before.bundle" \
    --all

tar -cpf \
    "$BACKUP/live-before.tar" \
    -C / \
    "${FILES[@]}"

echo "GO [OK] Branche backup : backup/pre-batch-controls-v3-${STAMP}"
echo "GO [OK] Git bundle      : $BACKUP/staging-before.bundle"
echo "GO [OK] Backup LIVE     : $BACKUP/live-before.tar"
echo

echo "==============================================================="
echo " 7. MODIFICATION SOURCE"
echo "==============================================================="

python3 - "$REPO" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

repo = Path(sys.argv[1])

DASH = repo / "opt/pincabos/web/pincabos_dashboard_lobby.py"
ILIVE = repo / "opt/pincabos/web/pincabos_batch_import_live.py"
QUEUE = repo / "opt/pincabos/web/pincabos_batch_import_queue_v2.py"
WORKER = repo / "opt/pincabos/web/pincabos_batch_import_worker_v2.py"
EXPORT = repo / "opt/pincabos/web/pincabos_batch_live.py"

MARKER = "PINCABOS_BATCH_CONTROLS_V3"


def die(message: str) -> None:
    raise SystemExit(f"NOGO PATCH: {message}")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        die(f"{label}: attendu 1 occurrence, trouve {count}")
    return text.replace(old, new, 1)


def replace_top_def(text: str, name: str, replacement: str) -> str:
    pattern = re.compile(
        rf"(?ms)^def {re.escape(name)}\b.*?(?=^def |^class |\Z)"
    )
    match = pattern.search(text)
    if not match:
        die(f"fonction introuvable : {name}")
    return (
        text[:match.start()]
        + replacement.rstrip()
        + "\n\n"
        + text[match.end():]
    )


# ===============================================================
# IMPORT QUEUE
# ===============================================================

text = QUEUE.read_text(encoding="utf-8")

if MARKER in text:
    die("Batch Controls V3 existe deja dans queue")

text = replace_once(
    text,
    'ACTIVE_STATES = {"uploading", "queued", "running", "stopping"}',
    'ACTIVE_STATES = {"uploading", "queued", "running", "stopping", "pausing"}',
    "queue ACTIVE_STATES",
)

text = replace_once(
    text,
    'PAUSED_STATE = "paused"\n',
    'PAUSED_STATE = "paused"\n'
    'PAUSING_STATE = "pausing"\n'
    '# PINCABOS_BATCH_CONTROLS_V3\n',
    "queue PAUSED_STATE",
)

text = replace_top_def(
    text,
    "refresh_progress",
r'''
def refresh_progress(job: dict[str, Any], label: str | None = None, current: str | None = None) -> None:
    total = max(0, int(job.get("total_archives", 0) or 0))
    completed = max(0, min(total, int(job.get("processed_archives", 0) or 0)))
    uploaded = max(0, min(total, int(job.get("uploaded_archives", 0) or 0)))
    skipped = max(0, int(job.get("skipped_archives", 0) or 0))
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
        "skipped": skipped,
        "error_attempts": int(job.get("error_attempts", 0) or 0),
    }
'''
)

text = replace_top_def(
    text,
    "pause_job",
r'''
def pause_job(job_id: str) -> dict[str, Any] | None:
    """Pause a la prochaine frontiere sure.

    Si un package est deja dans le moteur, il se termine avant la pause.
    """
    with state_lock(True):
        job = load_job_unlocked(job_id)
        if not job:
            return None

        state = str(job.get("state", ""))

        if state in FINAL_STATES or state == PAUSED_STATE:
            return job

        running_item = next(
            (
                item for item in (job.get("uploads") or [])
                if isinstance(item, dict)
                and str(item.get("state", "")) == "running"
            ),
            None,
        )

        if running_item is not None or state == "running":
            job["pause_requested"] = True
            job["state"] = PAUSING_STATE
            add_event(
                job,
                "Pause demandée; le package actuel se termine avant la pause.",
                "warning",
            )
            refresh_progress(job, "Pause demandée")
            save_job_unlocked(job)
            return job

        job["pause_requested"] = False
        job["state"] = PAUSED_STATE
        job["paused_at"] = utc_now()

        add_event(
            job,
            "Travail mis en pause. Reprise possible à tout moment.",
            "warning",
        )
        refresh_progress(job, "En pause")
        save_job_unlocked(job)

        if active_job_id_unlocked() == job_id:
            set_active_unlocked(None)

        return job


def complete_pause(job_id: str) -> dict[str, Any] | None:
    """Finalise une pause demandee apres le package courant."""
    with state_lock(True):
        job = load_job_unlocked(job_id)
        if not job:
            return None

        job["state"] = PAUSED_STATE
        job["pause_requested"] = False
        job["paused_at"] = utc_now()

        add_event(
            job,
            "Pause effective à la frontière sécurisée du package.",
            "warning",
        )
        refresh_progress(job, "En pause")
        save_job_unlocked(job)

        if active_job_id_unlocked() == job_id:
            set_active_unlocked(None)

        return job
'''
)

text = replace_top_def(
    text,
    "resume_job",
r'''
def resume_job(job_id: str) -> dict[str, Any] | None:
    """Reprend le travail restant sans refaire les packages termines."""
    with state_lock(True):
        job = load_job_unlocked(job_id)
        if not job:
            return None

        if str(job.get("state", "")) == PAUSING_STATE:
            return job

        remaining = [
            item
            for item in (job.get("uploads") or [])
            if isinstance(item, dict)
            and str(item.get("state", "")) in {
                "queued",
                "running",
                "uploading",
                "error",
            }
        ]

        if not remaining:
            return job

        for item in remaining:
            if str(item.get("state", "")) in {
                "running",
                "uploading",
                "error",
            }:
                item["state"] = "queued"

            if not str(item.get("detail", "")).strip():
                item["detail"] = "En attente de traitement"

        job["state"] = "queued"
        job["pause_requested"] = False
        job["stop_requested"] = False
        job["error"] = ""
        job["finished_at"] = None

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


def skip_job(job_id: str) -> dict[str, Any] | None:
    """Ignore uniquement le package fautif puis remet la file en marche."""
    with state_lock(True):
        job = load_job_unlocked(job_id)
        if not job:
            return None

        if str(job.get("state", "")) != PAUSED_STATE:
            return job

        target = next(
            (
                item
                for item in (job.get("uploads") or [])
                if isinstance(item, dict)
                and str(item.get("state", "")) == "error"
            ),
            None,
        )

        if target is None:
            return job

        index = int(target.get("index", 0) or 0)
        name = str(target.get("name", "Package"))
        source = Path(str(target.get("path", "") or ""))

        if source.is_file():
            try:
                source.unlink()
            except OSError:
                pass

        target["state"] = "skipped"
        target["detail"] = "Ignoré par l’utilisateur après erreur"
        target["path"] = ""

        job["skipped_archives"] = int(job.get("skipped_archives", 0) or 0) + 1
        job["processed_archives"] = max(
            int(job.get("processed_archives", 0) or 0),
            index,
        )
        job["current_index"] = index
        job["current_item"] = ""
        job["error"] = ""
        job["pause_requested"] = False
        job["stop_requested"] = False
        job["state"] = "queued"

        add_event(
            job,
            f"SKIP {index}/{job.get('total_archives', 0)} : {name}. "
            "Passage au package suivant.",
            "warning",
        )
        refresh_progress(job, "Package ignoré; reprise de la file", "")
        save_job_unlocked(job)

        if not active_job_id_unlocked():
            set_active_unlocked(job_id)

        return job
'''
)

QUEUE.write_text(text, encoding="utf-8")


# ===============================================================
# IMPORT WORKER
# ===============================================================

text = WORKER.read_text(encoding="utf-8")

if MARKER in text:
    die("Batch Controls V3 existe deja dans worker")

text = replace_top_def(
    text,
    "set_item_phase",
r'''
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
'''
)

text = replace_top_def(
    text,
    "finish_item",
r'''
def finish_item(
    job_id: str,
    item: dict[str, Any],
    outcome: str,
    detail: str,
    excerpt: str,
    removed: list[str],
) -> dict[str, Any] | None:
    # PINCABOS_BATCH_CONTROLS_V3
    index = int(item.get("index", 0) or 0)
    name = str(item.get("name", "Package"))
    source = Path(str(item.get("path", "")))

    # Une erreur est maintenant REPRENABLE.
    # L'archive source reste sur disque afin que Reprendre puisse retenter
    # exactement le meme package.
    if outcome == "failed":
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
                f"{name} : {detail}{cleanup_text} — "
                "Batch mis automatiquement en pause. "
                "Utilise Reprendre pour retenter ou Skip pour ignorer.",
                "error",
            )
            queue.refresh_progress(job, "Erreur — en pause", name)
            queue.save_job_unlocked(job)

            if queue.active_job_id_unlocked() == job_id:
                queue.set_active_unlocked(None)

            return job

    # Succes / warning : le package a ete consomme et peut etre supprime.
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
            job["successful_archives"] = (
                int(job.get("successful_archives", 0) or 0) + 1
            )
            level = "info"
        else:
            job["warning_archives"] = (
                int(job.get("warning_archives", 0) or 0) + 1
            )
            level = "warning"

        job["error"] = ""
        job["result_excerpt"] = excerpt

        cleanup_text = (
            f"; temporaires supprimés: {', '.join(removed)}"
            if removed else ""
        )

        queue.add_event(
            job,
            f"{name} : {detail}{cleanup_text}",
            level,
        )
        queue.refresh_progress(job, detail, name)
        queue.save_job_unlocked(job)
        return job
'''
)

old = '''        elif int(job.get("failed_archives", 0) or 0) or int(job.get("warning_archives", 0) or 0):
            job["state"] = "completed_with_warning"
'''

new = '''        elif (
            int(job.get("failed_archives", 0) or 0)
            or int(job.get("warning_archives", 0) or 0)
            or int(job.get("skipped_archives", 0) or 0)
        ):
            job["state"] = "completed_with_warning"
'''

text = replace_once(
    text,
    old,
    new,
    "worker finalize warning/skipped",
)

text = replace_top_def(
    text,
    "process_job",
r'''
def process_job(job_id: str) -> None:
    job = mark_running(job_id)
    if not job:
        return

    conflict_mode = str(job.get("conflict_mode", "skip") or "skip")

    while RUNNING:
        current = queue.load_job(job_id)
        if not current:
            return

        if str(current.get("state", "")) == queue.PAUSED_STATE:
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

        # Une erreur est maintenant une pause automatique.
        if outcome == "failed":
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
'''
)

WORKER.write_text(text, encoding="utf-8")


# ===============================================================
# IMPORT API
# ===============================================================

text = ILIVE.read_text(encoding="utf-8")

if "PINCABOS_BATCH_SKIP_ROUTE_V3" in text:
    die("Import Skip V3 existe deja")

anchor = '''    @app.route("/api/batch-import/live/active", methods=["GET"])
'''

if text.count(anchor) != 1:
    die("anchor /api/batch-import/live/active invalide")

skip_route = r'''
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

'''

text = text.replace(anchor, skip_route + anchor, 1)

needle = 'str(item.get("state")) in {"queued", "running"}'
count = text.count(needle)

if count < 2:
    die(f"Import active remaining: seulement {count} occurrence(s)")

text = text.replace(
    needle,
    'str(item.get("state")) in {"queued", "running", "error"}',
)

ILIVE.write_text(text, encoding="utf-8")


# ===============================================================
# EXPORT LIVE
# ===============================================================

text = EXPORT.read_text(encoding="utf-8")

if MARKER in text:
    die("Batch Controls V3 existe deja dans Export")

text = replace_top_def(
    text,
    "_mark_stopped",
r'''
def _mark_stopped(
    job: dict[str, Any],
    message: str = "Export arrêté par l’utilisateur.",
) -> None:
    job["state"] = "stopped"
    job["finished_at"] = _utc_now()
    job["pause_requested"] = False
    job["error"] = ""
    _progress(
        job,
        "Arrêté",
        current=str(job.get("current_table", "") or ""),
    )
    _event(job, message, "warning")
    _save_job(job)


def _mark_paused(
    job: dict[str, Any],
    message: str,
    error_message: str = "",
) -> None:
    # PINCABOS_BATCH_CONTROLS_V3
    job["state"] = "paused"
    job["pause_requested"] = False
    job["finished_at"] = None
    job["paused_at"] = _utc_now()
    job["error"] = error_message

    remaining = _remaining_tables(job)
    job["current_table"] = remaining[0] if remaining else ""

    _progress(
        job,
        "Erreur — en pause" if error_message else "En pause",
        current=job["current_table"],
    )
    _event(job, message, "error" if error_message else "warning")
    _save_job(job)
    _set_active(str(job["id"]))
'''
)

text = replace_top_def(
    text,
    "_progress",
r'''
def _progress(
    job: dict[str, Any],
    label: str,
    *,
    current: str | None = None,
    percent: int | None = None,
) -> None:
    total = max(1, int(job.get("total_tables", 0) or 0))
    successful = max(0, int(job.get("completed_tables", 0) or 0))
    skipped = max(0, int(job.get("skipped_tables", 0) or 0))
    done = min(total, successful + skipped)

    if percent is None:
        percent = 4 + int((done / total) * 92)

    current_value = (
        str(job.get("current_table", "") or "")
        if current is None
        else str(current)
    )

    job["progress"] = {
        "percent": max(0, min(100, int(percent))),
        "label": label,
        "current_table": current_value,
        "completed": done,
        "successful": successful,
        "skipped": skipped,
        "total": total,
        "mode": "packages",
    }
'''
)

text = replace_top_def(
    text,
    "_public_job",
r'''
def _public_job(job: dict[str, Any]) -> dict[str, Any]:
    remaining = _remaining_tables(job)
    state = str(job.get("state", "") or "")

    return {
        "id": job.get("id"),
        "state": state,
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
        "completed_names": job.get("completed_names", []),
        "skipped_tables": job.get("skipped_tables", 0),
        "skipped_names": job.get("skipped_names", []),
        "current_table": job.get("current_table", ""),
        "remaining": len(remaining),
        "resumable": (
            state == "paused"
            and bool(remaining)
            and bool(job.get("fields"))
        ),
        "skippable": (
            state == "paused"
            and bool(remaining)
            and bool(job.get("error"))
        ),
    }
'''
)

text = replace_top_def(
    text,
    "_recover_stale_active",
r'''
def _recover_stale_active() -> None:
    """Un restart WebApp devient une pause recuperable, jamais un dead-end."""
    active_id = _active_job_id()
    if not active_id:
        return

    job = _load_job(active_id)
    if not job:
        _set_active(None)
        return

    state = str(job.get("state", "") or "")

    if state in {"queued", "running", "pausing"}:
        job["state"] = "paused"
        job["pause_requested"] = False
        job["finished_at"] = None
        job["error"] = (
            "Export interrompu par un redémarrage du WebApp. "
            "Clique Reprendre pour continuer à la prochaine table."
        )

        remaining = _remaining_tables(job)
        job["current_table"] = remaining[0] if remaining else ""

        _progress(
            job,
            "En pause après redémarrage",
            current=job["current_table"],
        )
        _event(job, job["error"], "warning")
        _save_job(job)
        _set_active(active_id)
        return

    if state == "paused":
        _set_active(active_id)
        return

    _set_active(None)
'''
)

text = replace_top_def(
    text,
    "_safe_table_name",
r'''
def _remaining_tables(job: dict[str, Any]) -> list[str]:
    selected = [
        str(value)
        for value in (job.get("selected_tables") or [])
        if str(value)
    ]
    finished = {
        str(value)
        for value in (job.get("completed_names") or [])
    }
    finished.update(
        str(value)
        for value in (job.get("skipped_names") or [])
    )
    return [value for value in selected if value not in finished]


def _stored_fields(job: dict[str, Any]) -> list[tuple[str, str]]:
    raw = job.get("fields")
    if not isinstance(raw, list):
        return []

    result: list[tuple[str, str]] = []

    for item in raw:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            continue
        key, value = item
        if isinstance(key, str) and isinstance(value, str):
            result.append((key, value))

    return result


def _fields_for_table(
    job: dict[str, Any],
    table_name: str,
) -> list[tuple[str, str]]:
    base = _stored_fields(job)
    if not base:
        return []

    fields = [
        (key, value)
        for key, value in base
        if key != "table_folder"
    ]
    fields.append(("table_folder", table_name))
    return fields


def _safe_table_name(job: dict[str, Any], completed: int) -> str:
    del completed
    remaining = _remaining_tables(job)
    if remaining:
        return remaining[0]
    return ""
'''
)

text = replace_top_def(
    text,
    "_copy_started",
r'''
def _copy_started(job_id: str, source: Any, destination: Any) -> None:
    job = _load_job(job_id)
    if not job or job.get("state") not in {
        "queued",
        "running",
        "pausing",
        "stopping",
    }:
        return

    successful = int(job.get("completed_tables", 0) or 0)
    skipped = int(job.get("skipped_tables", 0) or 0)
    current = _safe_table_name(job, successful + skipped)

    if not current:
        return

    job["current_table"] = current
    job["current_package"] = Path(str(source)).name

    _progress(job, "Création/copie du package", current=current)
    _event(
        job,
        f"Table {successful + skipped + 1}/"
        f"{job.get('total_tables', 0)} en cours : {current}",
    )
    _save_job(job)
'''
)

text = replace_top_def(
    text,
    "_copy_finished",
r'''
def _copy_finished(job_id: str, source: Any, destination: Any) -> None:
    job = _load_job(job_id)
    if not job or job.get("state") not in {
        "queued",
        "running",
        "pausing",
        "stopping",
    }:
        return

    total = int(job.get("total_tables", 0) or 0)
    current = str(job.get("current_table", "") or "")

    if not current:
        current = _safe_table_name(
            job,
            int(job.get("completed_tables", 0) or 0)
            + int(job.get("skipped_tables", 0) or 0),
        )

    names = job.setdefault("completed_names", [])

    if current and isinstance(names, list) and current not in names:
        names.append(current)
        job["completed_tables"] = int(
            job.get("completed_tables", 0) or 0
        ) + 1

    remaining = _remaining_tables(job)
    next_name = remaining[0] if remaining else ""
    job["current_table"] = next_name

    done = (
        int(job.get("completed_tables", 0) or 0)
        + int(job.get("skipped_tables", 0) or 0)
    )

    if remaining:
        _progress(job, "Package copié", current=next_name)
        _event(
            job,
            f"Package terminé : {current} ({done}/{total}). "
            f"Prochaine table : {next_name}",
        )
    else:
        _progress(job, "Dernier package copié", current="")
        _event(
            job,
            f"Package terminé : {current} ({done}/{total}).",
        )

    _save_job(job)
'''
)

# Le V3 traite maintenant UNE table par requete V1.
# On ne doit donc plus interrompre shutil.copy2 :
# Pause/Stop sont appliques juste apres le package courant.
observer_old = '''            if observe and _stop_requested(str(job_id)):
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
'''

observer_new = '''            # PINCABOS_BATCH_CONTROLS_V3
            # Le runner appelle V1 une table a la fois. Le package courant
            # se termine donc proprement avant Pause ou Stop.
            if observe:
                _copy_started(str(job_id), source, destination)
            try:
                result = _ORIGINAL_COPY2(
                    source,
                    destination,
                    *args,
                    **kwargs,
                )
            except Exception as exc:
                if observe:
                    _copy_failed(str(job_id), source, exc)
                raise
            if observe:
                _copy_finished(str(job_id), source, destination)
            return result
'''

text = replace_once(
    text,
    observer_old,
    observer_new,
    "Export copy observer",
)

text = replace_top_def(
    text,
    "_run_v1",
r'''
def _run_v1(
    job_id: str,
    fields: list[tuple[str, str]],
    lock_fd: int,
) -> None:
    """PINCABOS_BATCH_CONTROLS_V3

    Le moteur V1 est appele UNE TABLE A LA FOIS.
    C'est la frontiere qui rend Pause / Resume / Skip deterministes.
    """
    try:
        job = _load_job(job_id)
        if not job:
            return

        if not job.get("fields") and fields:
            job["fields"] = [[key, value] for key, value in fields]
            _save_job(job)

        while True:
            job = _load_job(job_id)
            if not job:
                return

            if job.get("stop_requested"):
                _mark_stopped(job)
                return

            if (
                job.get("pause_requested")
                or str(job.get("state", "")) in {"paused", "pausing"}
            ):
                _mark_paused(
                    job,
                    "Export mis en pause à la frontière sécurisée.",
                )
                return

            remaining = _remaining_tables(job)

            if not remaining:
                skipped = int(job.get("skipped_tables", 0) or 0)

                job["state"] = (
                    "completed_with_warning"
                    if skipped
                    else "completed"
                )
                job["finished_at"] = _utc_now()
                job["current_table"] = ""
                job["error"] = ""

                _progress(
                    job,
                    (
                        "Terminé avec table(s) ignorée(s)"
                        if skipped
                        else "Terminé"
                    ),
                    current="",
                    percent=100,
                )

                _event(
                    job,
                    (
                        f"Export terminé : "
                        f"{job.get('completed_tables', 0)} succès, "
                        f"{skipped} ignorée(s), "
                        f"{job.get('total_tables', 0)} total."
                    ),
                    "warning" if skipped else "info",
                )
                _save_job(job)
                return

            current = remaining[0]
            first_start = not bool(job.get("started_at"))

            job["state"] = "running"
            job["started_at"] = job.get("started_at") or _utc_now()
            job["current_table"] = current
            job["error"] = ""

            _progress(
                job,
                "Préparation du moteur V1",
                current=current,
            )

            if first_start:
                _event(
                    job,
                    f"Export V3 démarré : "
                    f"{job.get('total_tables', 0)} table(s), "
                    "traitement une table à la fois.",
                )
            else:
                _event(
                    job,
                    f"Traitement de la prochaine table : {current}",
                )

            _save_job(job)

            table_fields = _fields_for_table(job, current)

            if not table_fields:
                _mark_paused(
                    job,
                    (
                        "Impossible de reconstruire la requête Export. "
                        "Le job reste en pause."
                    ),
                    "Informations de reprise absentes.",
                )
                return

            encoded = urlparse.urlencode(
                table_fields,
                doseq=True,
            ).encode("utf-8")

            outbound = urlrequest.Request(
                f"{INTERNAL_BASE_URL}{INTERNAL_TARGET}",
                data=encoded,
                method="POST",
                headers={
                    "Content-Type":
                        "application/x-www-form-urlencoded; charset=utf-8",
                    "Accept": "text/html,application/xhtml+xml",
                    INTERNAL_HEADER: job_id,
                },
            )

            _progress(
                job,
                "Moteur V1 en cours",
                current=current,
            )
            _event(
                job,
                f"Requête V1 envoyée pour : {current}",
            )
            _save_job(job)

            try:
                with urlrequest.urlopen(
                    outbound,
                    timeout=6 * 60 * 60,
                ) as response:
                    status = int(
                        getattr(
                            response,
                            "status",
                            response.getcode(),
                        )
                    )
                    body = response.read().decode(
                        "utf-8",
                        errors="replace",
                    )

            except urlerror.HTTPError as exc:
                text = (
                    exc.read().decode("utf-8", errors="replace")
                    if hasattr(exc, "read")
                    else ""
                )

                job = _load_job(job_id) or job

                if job.get("stop_requested"):
                    _mark_stopped(job)
                    return

                if (
                    job.get("pause_requested")
                    or str(job.get("state", "")) in {
                        "paused",
                        "pausing",
                    }
                ):
                    _mark_paused(
                        job,
                        "Export mis en pause après le package courant.",
                    )
                    return

                # Si la copie a quand meme ete observee, cette table est
                # terminee malgré l'erreur HTTP de rendu. On journalise et
                # continue.
                if current in set(job.get("completed_names") or []):
                    _event(
                        job,
                        f"{current} : package copié malgré HTTP {exc.code}. "
                        "Continuation.",
                        "warning",
                    )
                    _save_job(job)
                    continue

                job["result_excerpt"] = (
                    _compact_html(text)
                    if text
                    else "Aucun détail HTML disponible."
                )

                _mark_paused(
                    job,
                    (
                        f"Erreur sur {current}. "
                        "Utilise Reprendre pour retenter ou Skip pour ignorer."
                    ),
                    f"HTTP {exc.code} depuis le moteur V1.",
                )
                return

            except Exception as exc:
                job = _load_job(job_id) or job

                if job.get("stop_requested"):
                    _mark_stopped(job)
                    return

                if (
                    job.get("pause_requested")
                    or str(job.get("state", "")) in {
                        "paused",
                        "pausing",
                    }
                ):
                    _mark_paused(
                        job,
                        "Export mis en pause après le package courant.",
                    )
                    return

                if current in set(job.get("completed_names") or []):
                    _event(
                        job,
                        f"{current} : package copié malgré l'exception "
                        f"{exc}. Continuation.",
                        "warning",
                    )
                    _save_job(job)
                    continue

                _event(
                    job,
                    traceback.format_exc(limit=5),
                    "debug",
                )

                _mark_paused(
                    job,
                    (
                        f"Erreur sur {current}. "
                        "Utilise Reprendre pour retenter ou Skip pour ignorer."
                    ),
                    str(exc),
                )
                return

            if status < 200 or status >= 300:
                job = _load_job(job_id) or job
                _mark_paused(
                    job,
                    f"Erreur V1 sur {current}.",
                    f"HTTP {status} depuis le moteur V1.",
                )
                return

            job = _load_job(job_id) or job
            job["result_excerpt"] = _compact_html(body)
            _save_job(job)

            # Une table est valide seulement si le copy observer a vu son
            # .PinCabOS.
            if current not in set(job.get("completed_names") or []):
                _mark_paused(
                    job,
                    (
                        f"{current} n'a produit aucun fichier .PinCabOS. "
                        "Le Batch est en pause : Reprendre ou Skip."
                    ),
                    "Aucun package .PinCabOS produit par V1.",
                )
                return

            if job.get("stop_requested"):
                _mark_stopped(job)
                return

            if (
                job.get("pause_requested")
                or str(job.get("state", "")) == "pausing"
            ):
                _mark_paused(
                    job,
                    "Pause effective après le package courant.",
                )
                return

            # La boucle repart avec la prochaine table.

    finally:
        try:
            final_job = _load_job(job_id)

            if (
                final_job
                and str(final_job.get("state", "")) in {
                    "completed",
                    "completed_with_warning",
                    "stopped",
                    "cancelled",
                    "failed",
                }
                and _active_job_id() == job_id
            ):
                _set_active(None)

        finally:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            finally:
                os.close(lock_fd)


def _acquire_export_lock() -> int | None:
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
    lock_fd = os.open(
        str(LOCK_PATH),
        os.O_CREAT | os.O_RDWR,
        0o660,
    )

    try:
        fcntl.flock(
            lock_fd,
            fcntl.LOCK_EX | fcntl.LOCK_NB,
        )
        return lock_fd
    except BlockingIOError:
        os.close(lock_fd)
        return None


def _spawn_export_worker(
    job_id: str,
    fields: list[tuple[str, str]],
    lock_fd: int,
) -> None:
    worker = threading.Thread(
        target=_run_v1,
        args=(job_id, fields, lock_fd),
        name=f"pincabos-batch-v3-{job_id[:8]}",
        daemon=True,
    )
    worker.start()
'''
)

start_marker = '''    @app.route("/api/batch-export/live/start", methods=["POST"])
'''
stop_comment = '''    # PINCABOS_BATCH_LIVE_STOP_ENDPOINT_V11
'''

start_pos = text.find(start_marker)
if start_pos < 0:
    die("Export start route introuvable")

stop_pos = text.find(stop_comment, start_pos)
if stop_pos < 0:
    die("Export stop comment introuvable")

new_start = r'''    @app.route("/api/batch-export/live/start", methods=["POST"])
    def pincabos_batch_live_v3_start() -> Any:
        payload = request.get_json(silent=True) or {}

        try:
            fields = _validate_fields(payload.get("fields"))
            tables = _selected_tables(fields)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

        active_id = _active_job_id()

        if active_id:
            active_job = _load_job(active_id)
            active_state = str(
                (active_job or {}).get("state", "")
            )

            if active_job and active_state not in {
                "completed",
                "completed_with_warning",
                "stopped",
                "cancelled",
                "failed",
            }:
                return jsonify({
                    "ok": False,
                    "error": "Un export est déjà actif ou en pause.",
                    "active_job_id": active_id,
                }), 409

            _set_active(None)

        lock_fd = _acquire_export_lock()
        if lock_fd is None:
            return jsonify({
                "ok": False,
                "error": "Un Batch Import ou Batch Export utilise déjà le moteur.",
            }), 409

        job_id = uuid.uuid4().hex

        job = {
            "id": job_id,
            "version": 3,
            "state": "queued",
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
            "started_at": None,
            "finished_at": None,
            "selected_tables": tables,
            "fields": [[key, value] for key, value in fields],
            "total_tables": len(tables),
            "completed_tables": 0,
            "completed_names": [],
            "skipped_tables": 0,
            "skipped_names": [],
            "current_table": tables[0],
            "current_package": "",
            "pause_requested": False,
            "stop_requested": False,
            "events": [],
            "result_excerpt": "",
            "error": "",
        }

        _progress(
            job,
            "En file",
            current=tables[0],
            percent=2,
        )
        _event(
            job,
            f"Job V3 créé : {len(tables)} table(s) sélectionnée(s).",
        )
        _event(
            job,
            "Mode V3 : une table par requête pour permettre "
            "Pause / Reprendre / Skip.",
        )
        _save_job(job)
        _set_active(job_id)

        _spawn_export_worker(
            job_id,
            fields,
            lock_fd,
        )

        return jsonify({
            "ok": True,
            "job": _public_job(job),
        }), 202

'''

text = (
    text[:start_pos]
    + new_start
    + text[stop_pos:]
)

status_marker = '''    @app.route("/api/batch-export/live/status/<job_id>", methods=["GET"])
'''

stop_pos = text.find(stop_comment)
status_pos = text.find(status_marker, stop_pos)

if stop_pos < 0 or status_pos < 0:
    die("Export stop/status range invalide")

new_controls = r'''    # PINCABOS_BATCH_CONTROLS_V3
    @app.route("/api/batch-export/live/stop/<job_id>", methods=["POST"])
    def pincabos_batch_live_v3_stop(job_id: str) -> Any:
        job = _load_job(job_id)

        if not job:
            return jsonify({"ok": False, "error": "Job introuvable."}), 404

        state = str(job.get("state", "")).lower()

        if state == "paused":
            job["stop_requested"] = True
            _mark_stopped(job)
            if _active_job_id() == job_id:
                _set_active(None)

            return jsonify({
                "ok": True,
                "job": _public_job(job),
            }), 202

        if state not in {
            "queued",
            "running",
            "pausing",
            "stopping",
        }:
            return jsonify({
                "ok": False,
                "error": "Ce job n’est plus actif.",
                "job": _public_job(job),
            }), 409

        job["stop_requested"] = True
        job["pause_requested"] = False
        job["state"] = "stopping"

        _progress(
            job,
            "Arrêt demandé",
            current=str(job.get("current_table", "") or ""),
        )
        _event(
            job,
            "Arrêt demandé. La table déjà en cours se termine; "
            "la suivante ne démarre pas.",
            "warning",
        )
        _save_job(job)

        return jsonify({
            "ok": True,
            "job": _public_job(job),
        }), 202


    @app.route("/api/batch-export/live/pause/<job_id>", methods=["POST"])
    def pincabos_batch_live_v3_pause(job_id: str) -> Any:
        job = _load_job(job_id)

        if not job:
            return jsonify({"ok": False, "error": "Job introuvable."}), 404

        state = str(job.get("state", "")).lower()

        if state == "paused":
            return jsonify({
                "ok": True,
                "job": _public_job(job),
            }), 200

        if state not in {"queued", "running", "pausing"}:
            return jsonify({
                "ok": False,
                "error": "Ce job ne peut pas être mis en pause.",
                "job": _public_job(job),
            }), 409

        if state == "queued":
            _mark_paused(
                job,
                "Export mis en pause avant la prochaine table.",
            )
        else:
            job["pause_requested"] = True
            job["state"] = "pausing"

            _progress(
                job,
                "Pause demandée",
                current=str(job.get("current_table", "") or ""),
            )
            _event(
                job,
                "Pause demandée. La table actuelle se termine "
                "avant la pause.",
                "warning",
            )
            _save_job(job)

        return jsonify({
            "ok": True,
            "job": _public_job(_load_job(job_id) or job),
        }), 202


    @app.route("/api/batch-export/live/resume/<job_id>", methods=["POST"])
    def pincabos_batch_live_v3_resume(job_id: str) -> Any:
        job = _load_job(job_id)

        if not job:
            return jsonify({"ok": False, "error": "Job introuvable."}), 404

        if str(job.get("state", "")) != "paused":
            return jsonify({
                "ok": False,
                "error": "Le job n'est pas en pause.",
                "job": _public_job(job),
            }), 409

        remaining = _remaining_tables(job)

        if not remaining:
            return jsonify({
                "ok": False,
                "error": "Aucune table restante.",
                "job": _public_job(job),
            }), 409

        fields = _stored_fields(job)

        if not fields:
            return jsonify({
                "ok": False,
                "error": (
                    "Ce vieux job ne contient pas les données V3 "
                    "nécessaires à une reprise."
                ),
                "job": _public_job(job),
            }), 409

        lock_fd = _acquire_export_lock()

        if lock_fd is None:
            return jsonify({
                "ok": False,
                "error": "Le moteur Batch est encore occupé.",
                "job": _public_job(job),
            }), 409

        job["state"] = "queued"
        job["pause_requested"] = False
        job["stop_requested"] = False
        job["finished_at"] = None
        job["error"] = ""
        job["current_table"] = remaining[0]

        _progress(
            job,
            "Reprise en file",
            current=remaining[0],
        )
        _event(
            job,
            f"Reprise : {len(remaining)} table(s) restante(s).",
        )
        _save_job(job)
        _set_active(job_id)

        _spawn_export_worker(
            job_id,
            fields,
            lock_fd,
        )

        return jsonify({
            "ok": True,
            "job": _public_job(job),
        }), 202


    @app.route("/api/batch-export/live/skip/<job_id>", methods=["POST"])
    def pincabos_batch_live_v3_skip(job_id: str) -> Any:
        job = _load_job(job_id)

        if not job:
            return jsonify({"ok": False, "error": "Job introuvable."}), 404

        if str(job.get("state", "")) != "paused":
            return jsonify({
                "ok": False,
                "error": "Le job doit être en pause avant Skip.",
                "job": _public_job(job),
            }), 409

        if not job.get("error"):
            return jsonify({
                "ok": False,
                "error": "Skip est disponible après une erreur.",
                "job": _public_job(job),
            }), 409

        remaining = _remaining_tables(job)

        if not remaining:
            return jsonify({
                "ok": False,
                "error": "Aucune table à ignorer.",
                "job": _public_job(job),
            }), 409

        current = remaining[0]
        skipped = job.setdefault("skipped_names", [])

        if current not in skipped:
            skipped.append(current)

        job["skipped_tables"] = len(skipped)
        job["error"] = ""
        job["pause_requested"] = False

        _event(
            job,
            f"SKIP : {current}. Passage à la table suivante.",
            "warning",
        )

        remaining = _remaining_tables(job)

        if not remaining:
            job["state"] = "completed_with_warning"
            job["finished_at"] = _utc_now()
            job["current_table"] = ""

            _progress(
                job,
                "Terminé avec table(s) ignorée(s)",
                current="",
                percent=100,
            )
            _save_job(job)

            if _active_job_id() == job_id:
                _set_active(None)

            return jsonify({
                "ok": True,
                "job": _public_job(job),
            }), 202

        job["current_table"] = remaining[0]
        job["state"] = "paused"

        _progress(
            job,
            "Table ignorée — reprise",
            current=remaining[0],
        )
        _save_job(job)

        fields = _stored_fields(job)
        lock_fd = _acquire_export_lock()

        if lock_fd is None:
            _event(
                job,
                "Table ignorée. Le moteur est encore occupé; "
                "clique Reprendre.",
                "warning",
            )
            _save_job(job)

            return jsonify({
                "ok": True,
                "job": _public_job(job),
            }), 202

        job["state"] = "queued"
        _progress(
            job,
            "Reprise après Skip",
            current=remaining[0],
        )
        _save_job(job)
        _set_active(job_id)

        _spawn_export_worker(
            job_id,
            fields,
            lock_fd,
        )

        return jsonify({
            "ok": True,
            "job": _public_job(job),
        }), 202


'''

text = (
    text[:stop_pos]
    + new_controls
    + text[status_pos:]
)

EXPORT.write_text(text, encoding="utf-8")


# ===============================================================
# DASHBOARD
# ===============================================================

text = DASH.read_text(encoding="utf-8")

if "PINCABOS_DASHBOARD_BATCH_CONTROLS_V3" in text:
    die("Dashboard V3 existe deja")

old_import = '''      <a href="/tools/batch-import" data-pco-batch-open>Ouvrir</a>
      <button type="button" data-pco-batch-stop hidden>Stop</button>
      <button type="button" data-pco-batch-refresh>Actualiser</button>
'''

new_import = '''      <a href="/tools/batch-import" data-pco-batch-open>Ouvrir</a>
      <button type="button" data-pco-batch-pause>Pause</button>
      <button type="button" data-pco-batch-resume>Reprendre</button>
      <button type="button" data-pco-batch-skip>Skip</button>
      <button type="button" data-pco-batch-stop hidden>Stop</button>
      <button type="button" data-pco-batch-refresh>Actualiser</button>
'''

old_export = '''      <a href="/tools/batch-export" data-pco-batch-open>Ouvrir</a>
      <button type="button" data-pco-batch-stop hidden>Stop</button>
      <button type="button" data-pco-batch-refresh>Actualiser</button>
'''

new_export = '''      <a href="/tools/batch-export" data-pco-batch-open>Ouvrir</a>
      <button type="button" data-pco-batch-pause>Pause</button>
      <button type="button" data-pco-batch-resume>Reprendre</button>
      <button type="button" data-pco-batch-skip>Skip</button>
      <button type="button" data-pco-batch-stop hidden>Stop</button>
      <button type="button" data-pco-batch-refresh>Actualiser</button>
'''

text = replace_once(
    text,
    old_import,
    new_import,
    "dashboard import controls",
)

text = replace_once(
    text,
    old_export,
    new_export,
    "dashboard export controls",
)

marker = 'if (window.__pcoDashboardBatchControlsV2) return;'
position = text.find(marker)

if position < 0:
    die("Dashboard JS V2 marker absent")

script_start = text.rfind("<script>", 0, position)
script_end = text.find("</script>", position)

if script_start < 0 or script_end < 0:
    die("Dashboard script range introuvable")

script_end += len("</script>")

new_script = r'''<script>
/* PINCABOS_DASHBOARD_BATCH_CONTROLS_V3 */
(() => {
  "use strict";

  if (window.__pcoDashboardBatchControlsV3) return;
  window.__pcoDashboardBatchControlsV3 = true;

  const root = document.getElementById("pco-dashboard-batch-controls");
  if (!root) return;

  const cache = {import: null, export: null};

  const row = kind =>
    root.querySelector(`[data-pco-batch-kind="${kind}"]`);

  const api = (kind, suffix) =>
    `/api/batch-${kind}/live/${suffix}`;

  async function json(url, options = {}) {
    const response = await fetch(url, {
      cache: "no-store",
      credentials: "same-origin",
      headers: {"Accept": "application/json"},
      ...options
    });

    let data = {};
    try {
      data = await response.json();
    } catch (_) {}

    if (!response.ok || data.ok === false) {
      throw new Error(
        data.error || `HTTP ${response.status}`
      );
    }

    return data;
  }

  function label(state) {
    return ({
      uploading: "Téléversement",
      queued: "En file",
      running: "Actif",
      pausing: "Pause demandée",
      paused: "En pause",
      stopping: "Arrêt demandé",
      completed: "Terminé",
      completed_with_warning: "Avertissement",
      failed: "Erreur",
      stopped: "Arrêté",
      cancelled: "Annulé"
    })[state] || "Disponible";
  }

  function currentName(job) {
    const progress = job?.progress || {};
    return String(
      progress.current_item ||
      progress.current_table ||
      job?.current_item ||
      job?.current_table ||
      ""
    );
  }

  function done(job) {
    const progress = job?.progress || {};
    return Number(
      progress.completed ??
      job?.processed_archives ??
      job?.completed_tables ??
      0
    );
  }

  function total(job) {
    const progress = job?.progress || {};
    return Number(
      progress.total ??
      job?.total_archives ??
      job?.total_tables ??
      0
    );
  }

  async function load(kind) {
    if (kind === "import") {
      const active = await json(
        "/api/batch-import/live/active"
      );

      if (active.job) {
        return {
          id: String(active.job.id || ""),
          job: active.job,
          resumable: Boolean(active.resumable),
          remaining: Number(active.remaining || 0)
        };
      }
    }

    const history = await json(api(kind, "history"));
    const activeId = String(history.active_job_id || "");

    if (activeId) {
      const status = await json(
        api(kind, `status/${encodeURIComponent(activeId)}`)
      );

      return {
        id: activeId,
        job: status.job || null,
        resumable: Boolean(status.job?.resumable)
      };
    }

    const latest = (history.jobs || [])[0] || null;

    return {
      id: String(latest?.id || ""),
      job: latest,
      resumable: Boolean(latest?.resumable)
    };
  }

  function render(kind, packet, error = "") {
    const target = row(kind);
    if (!target) return;

    const job = packet?.job || null;
    const state = String(job?.state || "").toLowerCase();
    const progress = job?.progress || {};

    const working = [
      "uploading",
      "queued",
      "running",
      "pausing",
      "paused",
      "stopping"
    ].includes(state);

    target.classList.toggle(
      "is-active",
      working && state !== "paused"
    );

    const status = target.querySelector(
      "[data-pco-batch-state]"
    );
    const detail = target.querySelector(
      "[data-pco-batch-detail]"
    );
    const open = target.querySelector(
      "[data-pco-batch-open]"
    );

    const pause = target.querySelector(
      "[data-pco-batch-pause]"
    );
    const resume = target.querySelector(
      "[data-pco-batch-resume]"
    );
    const skip = target.querySelector(
      "[data-pco-batch-skip]"
    );
    const stop = target.querySelector(
      "[data-pco-batch-stop]"
    );

    if (status) {
      status.textContent = error
        ? "API indisponible"
        : label(state);
    }

    if (detail) {
      if (error) {
        detail.textContent = error;
      } else if (!job) {
        detail.textContent = kind === "import"
          ? "Worker prêt · aucun job."
          : "Aucun job en cours.";
      } else {
        const count = total(job);
        const completed = done(job);
        const name = currentName(job);
        const skipped = Number(
          progress.skipped ??
          job.skipped_archives ??
          job.skipped_tables ??
          0
        );

        detail.textContent = [
          progress.label || label(state),
          count ? `${completed}/${count}` : "",
          skipped ? `Skip ${skipped}` : "",
          name,
          job.error || ""
        ].filter(Boolean).join(" · ");
      }

      detail.title = detail.textContent;
    }

    if (open) {
      open.textContent = working ? "Voir tâche" : "Ouvrir";
    }

    const canPause = ["queued", "running"].includes(state);

    const canResume =
      state === "paused" &&
      (
        kind === "import"
          ? Boolean(packet?.resumable)
          : Boolean(job?.resumable)
      );

    const canSkip =
      state === "paused" &&
      Boolean(job?.error) &&
      (
        kind === "import" ||
        Boolean(job?.skippable)
      );

    if (pause) {
      pause.hidden = false;
      pause.disabled = !canPause;
    }

    if (resume) {
      resume.hidden = false;
      resume.disabled = !canResume;
    }

    if (skip) {
      skip.hidden = false;
      skip.disabled = !canSkip;
    }

    if (stop) {
      const canStop = [
        "uploading",
        "queued",
        "running",
        "pausing",
        "stopping"
      ].includes(state);

      stop.hidden = !canStop;
      stop.disabled = state === "stopping";
      stop.textContent =
        state === "stopping" ? "Arrêt…" : "Stop";
    }
  }

  async function refresh(kind) {
    try {
      cache[kind] = await load(kind);
      render(kind, cache[kind]);
    } catch (error) {
      cache[kind] = null;
      render(
        kind,
        null,
        `État indisponible : ${error.message}`
      );
    }
  }

  async function refreshAll() {
    await Promise.all([
      refresh("import"),
      refresh("export")
    ]);
  }

  async function act(kind, action, button) {
    const packet = cache[kind];

    if (!packet?.id || button.disabled) return;

    const original = button.textContent;
    button.disabled = true;
    button.textContent = "…";

    try {
      const data = await json(
        api(
          kind,
          `${action}/${encodeURIComponent(packet.id)}`
        ),
        {method: "POST"}
      );

      cache[kind] = {
        id: packet.id,
        job: data.job || packet.job,
        resumable: Boolean(
          data.resumable ??
          data.job?.resumable
        )
      };

      render(kind, cache[kind]);
      await refreshAll();

    } catch (error) {
      button.textContent = original;

      const detail = row(kind)?.querySelector(
        "[data-pco-batch-detail]"
      );

      if (detail) {
        detail.textContent =
          `${action} impossible : ${error.message}`;
        detail.title = detail.textContent;
      }

      await refresh(kind);
    }
  }

  root.addEventListener("click", event => {
    const target = event.target;
    const targetRow = target.closest(
      "[data-pco-batch-kind]"
    );

    if (!targetRow) return;

    const kind = String(
      targetRow.dataset.pcoBatchKind || ""
    );

    if (!["import", "export"].includes(kind)) return;

    const refreshButton = target.closest(
      "[data-pco-batch-refresh]"
    );

    if (refreshButton) {
      event.preventDefault();
      refresh(kind);
      return;
    }

    const pauseButton = target.closest(
      "[data-pco-batch-pause]"
    );

    if (pauseButton) {
      event.preventDefault();
      act(kind, "pause", pauseButton);
      return;
    }

    const resumeButton = target.closest(
      "[data-pco-batch-resume]"
    );

    if (resumeButton) {
      event.preventDefault();
      act(kind, "resume", resumeButton);
      return;
    }

    const skipButton = target.closest(
      "[data-pco-batch-skip]"
    );

    if (skipButton) {
      event.preventDefault();

      if (
        window.confirm(
          "Ignorer l'élément fautif et passer au suivant ?"
        )
      ) {
        act(kind, "skip", skipButton);
      }
      return;
    }

    const stopButton = target.closest(
      "[data-pco-batch-stop]"
    );

    if (stopButton) {
      event.preventDefault();

      if (
        window.confirm(
          "Arrêter ce Batch après l'élément en cours ?"
        )
      ) {
        act(kind, "stop", stopButton);
      }
    }
  });

  refreshAll();
  window.setInterval(refreshAll, 2500);
})();
</script>'''

text = (
    text[:script_start]
    + new_script
    + text[script_end:]
)

DASH.write_text(text, encoding="utf-8")

print("GO [OK] Source Batch Controls V3 generee.")
PY

echo
echo "=== 8. VALIDATION PYTHON ==="

for F in "${FILES[@]}"
do
    case "$F" in
        *.py)
            python3 -m py_compile "$REPO/$F" || \
                fail "Syntaxe Python invalide : $F"
            echo "GO [OK] $F"
            ;;
    esac
done

echo
echo "=== 9. VALIDATION DIFF GIT ==="

git diff --check || \
    fail "git diff --check detecte une erreur."

echo
git diff --stat

echo
echo "--- MARQUEURS V3 ---"

grep -n \
    -E 'PINCABOS_BATCH_CONTROLS_V3|PINCABOS_DASHBOARD_BATCH_CONTROLS_V3|PINCABOS_BATCH_SKIP_ROUTE_V3' \
    "${FILES[@]}" || \
    fail "Marqueurs V3 absents."

echo
echo "GO [OK] Diff source valide."
echo

echo "=== 10. COMMIT LOCAL ==="

git add "${FILES[@]}"

git commit \
    -m "feat(batch): pause resume skip and recoverable errors"

NEW_HEAD="$(git rev-parse HEAD)"

echo "GO [OK] Commit local : $NEW_HEAD"
echo "GITHUB : AUCUN PUSH"
echo

echo "=== 11. BACKUP METADATA LIVE ==="

META="$BACKUP/live-metadata.txt"
: > "$META"

for F in "${FILES[@]}"
do
    stat -c '%n|%u|%g|%a' "/$F" >> "$META"
done

cat "$META"

echo
echo "=== 12. DEPLOIEMENT LIVE ATOMIQUE ==="

deploy_file()
{
    REL="$1"
    SRC="$REPO/$REL"
    DST="/$REL"

    F_UID="$(stat -c %u "$DST")"
    F_GID="$(stat -c %g "$DST")"
    F_MODE="$(stat -c %a "$DST")"

    TMP="${DST}.pincab-v3.$$"

    install \
        -o "$F_UID" \
        -g "$F_GID" \
        -m "$F_MODE" \
        "$SRC" \
        "$TMP"

    mv -f "$TMP" "$DST"

    echo "GO [DEPLOY] $DST"
}

for F in "${FILES[@]}"
do
    deploy_file "$F"
done

echo
echo "=== 13. VALIDATION STAGING == LIVE ==="

for F in "${FILES[@]}"
do
    SRC_HASH="$(sha256sum "$REPO/$F" | awk '{print $1}')"
    DST_HASH="$(sha256sum "/$F" | awk '{print $1}')"

    if [ "$SRC_HASH" != "$DST_HASH" ]
    then
        fail "Mismatch staging/live : $F"
    fi

    echo "GO [OK] $F"
done

echo
echo "=== 14. RESTART SERVICES ==="

systemctl restart pincabos-batch-import-worker.service
sleep 2

systemctl is-active --quiet pincabos-batch-import-worker.service || \
    fail "Worker Import inactif."

echo "GO [OK] Worker Import actif."

systemctl restart pincabos-webapp.service
sleep 3

systemctl is-active --quiet pincabos-webapp.service || \
    fail "WebApp inactive."

echo "GO [OK] WebApp active."
echo

echo "=== 15. TEST HTTP ==="

HTTP_CODE="$(
curl -s \
    -o /tmp/pincab-batch-v3-home.html \
    -w '%{http_code}' \
    --max-time 10 \
    http://127.0.0.1/
)"

echo "HTTP / : $HTTP_CODE"

[ "$HTTP_CODE" = "200" ] || \
    fail "WebApp ne retourne pas HTTP 200."

if ! grep -q \
    'PINCABOS_DASHBOARD_BATCH_CONTROLS_V3' \
    /tmp/pincab-batch-v3-home.html
then
    curl -s \
        --max-time 10 \
        http://127.0.0.1/dashboard \
        > /tmp/pincab-batch-v3-dashboard.html || true

    grep -q \
        'PINCABOS_DASHBOARD_BATCH_CONTROLS_V3' \
        /tmp/pincab-batch-v3-dashboard.html || \
        fail "Widget Dashboard V3 non detecte."
fi

echo "GO [OK] Dashboard V3 servi."
echo

echo "=== 16. VALIDATION API IMPORT ==="

curl -s \
    --max-time 5 \
    http://127.0.0.1/api/batch-import/live/active |
python3 -m json.tool || \
    fail "API Import active invalide."

for ACTION in pause resume skip
do
    BODY="$(
        curl -s \
            --max-time 5 \
            -X POST \
            "http://127.0.0.1/api/batch-import/live/${ACTION}/00000000000000000000000000000000"
    )"

    echo "$ACTION : $BODY"

    echo "$BODY" | grep -qi "Job introuvable" || \
        fail "Route Import $ACTION absente."
done

echo "GO [OK] API Import Pause/Resume/Skip."
echo

echo "=== 17. VALIDATION API EXPORT ==="

curl -s \
    --max-time 5 \
    http://127.0.0.1/api/batch-export/live/history |
python3 -m json.tool >/tmp/pincab-batch-v3-export-history.txt || \
    fail "API Export history invalide."

for ACTION in pause resume skip
do
    BODY="$(
        curl -s \
            --max-time 5 \
            -X POST \
            "http://127.0.0.1/api/batch-export/live/${ACTION}/00000000000000000000000000000000"
    )"

    echo "$ACTION : $BODY"

    echo "$BODY" | grep -qi "Job introuvable" || \
        fail "Route Export $ACTION absente."
done

echo "GO [OK] API Export Pause/Resume/Skip."
echo

echo "=== 18. ETAT FINAL ==="

printf "%-45s : " "pincabos-webapp.service"
systemctl is-active pincabos-webapp.service || true

printf "%-45s : " "pincabos-batch-import-worker.service"
systemctl is-active pincabos-batch-import-worker.service || true

echo
echo "Git branche : $(git branch --show-current)"
echo "Git HEAD    : $(git rev-parse HEAD)"

if [ -z "$(git status --porcelain)" ]
then
    echo "GO [OK] Git propre."
else
    git status --short
    fail "Git non propre apres commit."
fi

echo
echo "==============================================================="
echo " GO [OK] BATCH CONTROLS V3 INSTALLE"
echo "==============================================================="
echo
echo "IMPORT :"
echo "  Pause       : GO"
echo "  Reprendre   : GO"
echo "  Erreur->Pause : GO"
echo "  Retry meme package : GO"
echo "  Skip        : GO"
echo
echo "EXPORT :"
echo "  1 table par requete V1 : GO"
echo "  Pause       : GO"
echo "  Reprendre   : GO"
echo "  Erreur->Pause : GO"
echo "  Skip->suivante : GO"
echo "  Restart WebApp->Pause : GO"
echo
echo "DASHBOARD :"
echo "  Pause / Reprendre / Skip / Actualiser : GO"
echo
echo "BACKUP :"
echo "  $BACKUP"
echo
echo "COMMIT LOCAL :"
echo "  $NEW_HEAD"
echo
echo "GITHUB : PAS ENCORE PUSH"
echo "REBOOT : NON REQUIS"
echo
echo "==============================================================="

