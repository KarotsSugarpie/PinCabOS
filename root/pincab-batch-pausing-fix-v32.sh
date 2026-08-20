#!/usr/bin/env bash
set -Eeuo pipefail

clear

echo "==============================================================="
echo " PINCABOS — BATCH CONTROLS V3.2"
echo " FIX PAUSING BLOQUE + REPRENDRE DURANT PAUSE DEMANDEE"
echo " CONSERVATION DU JOB ACTUEL"
echo " AUCUN PUSH GITHUB"
echo "==============================================================="
echo

REPO="/opt/pincabos/tmp/pr-integration"
EXPECTED_HEAD="cd66f83240c360ffbe8d6eac0f3d0ebf228b3611"

QUEUE_REL="opt/pincabos/web/pincabos_batch_import_queue_v2.py"
WORKER_REL="opt/pincabos/web/pincabos_batch_import_worker_v2.py"
DASH_REL="opt/pincabos/web/pincabos_dashboard_lobby.py"

QUEUE="$REPO/$QUEUE_REL"
WORKER="$REPO/$WORKER_REL"
DASH="$REPO/$DASH_REL"

STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="/opt/pincabos/backups/batch-controls-v32-$STAMP"
BACKUP_BRANCH="backup/pre-batch-controls-v32-$STAMP"

fail()
{
    echo
    echo "==============================================================="
    echo " NOGO [ERREUR] $*"
    echo "==============================================================="
    exit 1
}

ok()
{
    echo "GO [OK] $*"
}

echo "=== 1. VALIDATION GIT ==="

[ "$(id -u)" -eq 0 ] ||
    fail "Execution root requise."

[ -d "$REPO/.git" ] ||
    fail "Repo absent."

cd "$REPO"

echo "Branche : $(git branch --show-current)"
echo "HEAD    : $(git rev-parse HEAD)"

[ "$(git branch --show-current)" = "pincabos-pr-integration" ] ||
    fail "Mauvaise branche."

[ "$(git rev-parse HEAD)" = "$EXPECTED_HEAD" ] ||
    fail "HEAD differente de V3.1."

[ -z "$(git status --porcelain)" ] ||
    fail "Git non propre."

ok "Base V3.1 correcte."

echo
echo "=== 2. CAPTURE DU JOB IMPORT ACTUEL ==="

ACTIVE_JSON="$(
    curl -s \
        --max-time 5 \
        http://127.0.0.1/api/batch-import/live/active
)"

JOB_ID="$(
    printf '%s' "$ACTIVE_JSON" |
    python3 -c '
import json,sys
d=json.load(sys.stdin)
print(((d.get("job") or {}).get("id")) or "")
'
)"

[ -n "$JOB_ID" ] ||
    fail "Aucun job Import actif/pausable trouve."

echo "Job : $JOB_ID"

printf '%s' "$ACTIVE_JSON" |
python3 -m json.tool

echo
echo "=== 3. VALIDATION DE LA PAUSE BLOQUEE ==="

printf '%s' "$ACTIVE_JSON" |
python3 - <<'PY'
import json
import sys

data = json.load(sys.stdin)
job = data.get("job") or {}

state = str(job.get("state") or "")
uploads = job.get("uploads") or []

running = [
    x for x in uploads
    if isinstance(x, dict)
    and str(x.get("state") or "") == "running"
]

print("State         :", state)
print("Running items :", len(running))

if state not in {"pausing", "paused"}:
    raise SystemExit(
        "NOGO: état inattendu, attendu pausing/paused."
    )

if running:
    raise SystemExit(
        "NOGO: un package est réellement running; "
        "on ne force pas la transition."
    )

print("GO [OK] Aucun package réellement running.")
PY

ok "On peut terminer la pause sans interrompre un package."

echo
echo "=== 4. BACKUP ==="

mkdir -p "$BACKUP"

git branch "$BACKUP_BRANCH"

for REL in \
    "$QUEUE_REL" \
    "$WORKER_REL" \
    "$DASH_REL"
do
    cp -a "/$REL" \
        "$BACKUP/$(basename "$REL").before"
done

echo "$JOB_ID" > "$BACKUP/job-id.txt"

printf '%s\n' "$ACTIVE_JSON" \
    > "$BACKUP/job-before.json"

ok "Backup : $BACKUP"
ok "Branche : $BACKUP_BRANCH"

echo
echo "==============================================================="
echo " 5. MISE EN PAUSE PROPRE DU JOB ACTUEL"
echo "==============================================================="

systemctl stop pincabos-batch-import-worker.service

ok "Worker arrete temporairement."

PYTHONPATH=/opt/pincabos/web \
python3 - "$JOB_ID" <<'PY'
import sys
import pincabos_batch_import_queue_v2 as queue

job_id = sys.argv[1]

job = queue.load_job(job_id)

if not job:
    raise SystemExit("NOGO: job introuvable")

state = str(job.get("state") or "")

running = [
    item
    for item in (job.get("uploads") or [])
    if isinstance(item, dict)
    and str(item.get("state") or "") == "running"
]

if running:
    raise SystemExit(
        "NOGO: package running detecte; aucune force."
    )

if state == queue.PAUSING_STATE:
    job = queue.complete_pause(job_id)

elif state == queue.PAUSED_STATE:
    pass

else:
    raise SystemExit(
        f"NOGO: état inattendu {state}"
    )

job = queue.load_job(job_id) or job

print("GO [OK] State :", job.get("state"))
print(
    "GO [OK] Processed :",
    job.get("processed_archives"),
)
print(
    "GO [OK] Uploaded :",
    job.get("uploaded_archives"),
)
PY

echo
echo "=== 6. VERIFICATION JOB MAINTENANT PAUSED ==="

curl -s \
    --max-time 5 \
    "http://127.0.0.1/api/batch-import/live/status/$JOB_ID" |
python3 -c '
import json,sys

d=json.load(sys.stdin)
j=d.get("job") or {}

print("state           :", j.get("state"))
print("uploaded        :", j.get("uploaded_archives"))
print("processed       :", j.get("processed_archives"))
print("current_item    :", j.get("current_item"))
print("pause_requested :", j.get("pause_requested"))

if j.get("state") != "paused":
    raise SystemExit("NOGO: job pas en paused")
'

ok "Job actuel sauve et place en PAUSED."

echo
echo "==============================================================="
echo " 7. PATCH DEFINITIF DU CODE"
echo "==============================================================="

python3 - \
    "$QUEUE" \
    "$WORKER" \
    "$DASH" <<'PY'
from pathlib import Path
import sys

queue_path = Path(sys.argv[1])
worker_path = Path(sys.argv[2])
dash_path = Path(sys.argv[3])

MARKER = "PINCABOS_BATCH_PAUSING_FIX_V32"


def die(msg):
    raise SystemExit("NOGO PATCH: " + msg)


# ------------------------------------------------------------
# QUEUE — Reprendre peut annuler "Pause demandée"
# ------------------------------------------------------------

text = queue_path.read_text(encoding="utf-8")

if MARKER not in text:

    old = '''        if str(job.get("state", "")) == PAUSING_STATE:
            return job
'''

    new = '''        if str(job.get("state", "")) == PAUSING_STATE:
            # PINCABOS_BATCH_PAUSING_FIX_V32
            #
            # Reprendre pendant "Pause demandée" annule la demande
            # de pause. S'il n'y a plus de package réellement
            # running, le job repart simplement en file.
            running_item = next(
                (
                    item
                    for item in (job.get("uploads") or [])
                    if isinstance(item, dict)
                    and str(item.get("state", "")) == "running"
                ),
                None,
            )

            job["pause_requested"] = False
            job["paused_at"] = None
            job["state"] = (
                "running"
                if running_item is not None
                else "queued"
            )

            add_event(
                job,
                "Demande de pause annulée; reprise du Batch.",
                "info",
            )
            refresh_progress(job, "Reprise du Batch")
            save_job_unlocked(job)

            if not active_job_id_unlocked():
                set_active_unlocked(job_id)

            return job
'''

    if text.count(old) != 1:
        die(
            "queue resume PAUSING: attendu 1 occurrence, trouve "
            + str(text.count(old))
        )

    text = text.replace(old, new, 1)

    queue_path.write_text(
        text,
        encoding="utf-8",
    )

    print("GO [PATCH] resume_job pausing")
else:
    print("GO [DEJA] queue V3.2")


# ------------------------------------------------------------
# WORKER — pausing sans moteur actif => paused immédiatement
# ------------------------------------------------------------

text = worker_path.read_text(encoding="utf-8")

worker_marker = "PINCABOS_WORKER_PAUSING_FIX_V32"

if worker_marker not in text:

    old = '''        if str(current.get("state", "")) == queue.PAUSED_STATE:
            return

        if current.get("stop_requested"):
'''

    new = '''        state = str(current.get("state", ""))

        if state == queue.PAUSED_STATE:
            return

        # PINCABOS_WORKER_PAUSING_FIX_V32
        #
        # Si le worker reprend un job déjà en "pausing" alors
        # qu'aucun package n'est dans le moteur, la frontière
        # sécurisée est déjà atteinte : on finalise la pause.
        if state == queue.PAUSING_STATE:
            queue.complete_pause(job_id)
            return

        if current.get("stop_requested"):
'''

    if text.count(old) != 1:
        die(
            "worker process_job pause block: attendu 1, trouve "
            + str(text.count(old))
        )

    text = text.replace(old, new, 1)

    worker_path.write_text(
        text,
        encoding="utf-8",
    )

    print("GO [PATCH] worker pausing -> paused")
else:
    print("GO [DEJA] worker V3.2")


# ------------------------------------------------------------
# DASHBOARD — Reprendre autorisé même durant "Pause demandée"
# ------------------------------------------------------------

text = dash_path.read_text(encoding="utf-8")

dash_marker = "PINCABOS_DASHBOARD_PAUSING_RESUME_V32"

if dash_marker not in text:

    old = '''    const canResume =
      state === "paused" &&
'''

    new = '''    /* PINCABOS_DASHBOARD_PAUSING_RESUME_V32 */
    const canResume =
      ["paused", "pausing"].includes(state) &&
'''

    if text.count(old) != 1:
        die(
            "dashboard canResume: attendu 1, trouve "
            + str(text.count(old))
        )

    text = text.replace(old, new, 1)

    dash_path.write_text(
        text,
        encoding="utf-8",
    )

    print("GO [PATCH] Dashboard Resume pausing")
else:
    print("GO [DEJA] dashboard V3.2")
PY

echo
echo "=== 8. VALIDATION SOURCE ==="

python3 -m py_compile "$QUEUE" ||
    fail "Queue syntaxe invalide."

python3 -m py_compile "$WORKER" ||
    fail "Worker syntaxe invalide."

python3 -m py_compile "$DASH" ||
    fail "Dashboard syntaxe invalide."

git diff --check ||
    fail "git diff --check."

grep -q \
    'PINCABOS_BATCH_PAUSING_FIX_V32' \
    "$QUEUE" ||
    fail "Marqueur queue absent."

grep -q \
    'PINCABOS_WORKER_PAUSING_FIX_V32' \
    "$WORKER" ||
    fail "Marqueur worker absent."

grep -q \
    'PINCABOS_DASHBOARD_PAUSING_RESUME_V32' \
    "$DASH" ||
    fail "Marqueur Dashboard absent."

ok "Sources V3.2 valides."

echo
echo "=== 9. DIFF ==="

git --no-pager diff --stat

echo
git --no-pager diff \
    -- "$QUEUE_REL" \
       "$WORKER_REL" \
       "$DASH_REL" \
    | head -260

echo
echo "=== 10. COMMIT LOCAL ==="

git add \
    "$QUEUE_REL" \
    "$WORKER_REL" \
    "$DASH_REL"

git commit \
    -m "fix(batch): complete pending pause and allow resume"

NEW_HEAD="$(git rev-parse HEAD)"

ok "Commit : $NEW_HEAD"
echo "GITHUB : AUCUN PUSH"

echo
echo "=== 11. DEPLOIEMENT LIVE ==="

deploy()
{
    REL="$1"
    SRC="$REPO/$REL"
    DST="/$REL"

    UID_DST="$(stat -c %u "$DST")"
    GID_DST="$(stat -c %g "$DST")"
    MODE_DST="$(stat -c %a "$DST")"

    TMP="${DST}.v32.$$"

    install \
        -o "$UID_DST" \
        -g "$GID_DST" \
        -m "$MODE_DST" \
        "$SRC" \
        "$TMP"

    mv -f "$TMP" "$DST"

    echo "GO [DEPLOY] $DST"
}

deploy "$QUEUE_REL"
deploy "$WORKER_REL"
deploy "$DASH_REL"

echo
echo "=== 12. RESTART SERVICES ==="

systemctl start pincabos-batch-import-worker.service
sleep 2

systemctl is-active --quiet \
    pincabos-batch-import-worker.service ||
    fail "Worker inactif."

ok "Worker actif."

systemctl restart pincabos-webapp.service
sleep 3

systemctl is-active --quiet \
    pincabos-webapp.service ||
    fail "WebApp inactive."

ok "WebApp active."

echo
echo "=== 13. VERIFICATION DU JOB APRES RESTART ==="

curl -s \
    --max-time 5 \
    http://127.0.0.1/api/batch-import/live/active |
python3 -c '
import json,sys

d=json.load(sys.stdin)
j=d.get("job") or {}

print("ID               :", j.get("id"))
print("STATE            :", j.get("state"))
print("UPLOADED         :", j.get("uploaded_archives"))
print("PROCESSED        :", j.get("processed_archives"))
print("TOTAL            :", j.get("total_archives"))
print("CURRENT ITEM     :", j.get("current_item"))
print("PAUSE REQUESTED  :", j.get("pause_requested"))
print("RESUMABLE        :", d.get("resumable"))
print("REMAINING        :", d.get("remaining"))

if j.get("state") != "paused":
    raise SystemExit(
        "NOGO: le job devrait rester paused."
    )
'

ok "Le job courant est toujours PAUSED."

echo
echo "=== 14. STAGING == LIVE ==="

for REL in \
    "$QUEUE_REL" \
    "$WORKER_REL" \
    "$DASH_REL"
do
    S="$(sha256sum "$REPO/$REL" | awk '{print $1}')"
    L="$(sha256sum "/$REL" | awk '{print $1}')"

    [ "$S" = "$L" ] ||
        fail "Mismatch : $REL"

    echo "GO [OK] $REL"
done

echo
echo "=== 15. GIT FINAL ==="

cd "$REPO"

echo "Branche : $(git branch --show-current)"
echo "HEAD    : $(git rev-parse HEAD)"

[ -z "$(git status --porcelain)" ] ||
    fail "Git non propre."

ok "Git propre."

echo
echo "==============================================================="
echo " GO [OK] BATCH PAUSE V3.2 INSTALLE"
echo "==============================================================="
echo
echo "JOB ACTUEL :"
echo "  $JOB_ID"
echo
echo "Etat attendu maintenant : PAUSED"
echo
echo "Tu peux cliquer REPRENDRE dans l'onglet deja ouvert."
echo "NE RECHARGE PAS LA PAGE pour ce test."
echo
echo "Backup : $BACKUP"
echo "HEAD   : $NEW_HEAD"
echo
echo "GITHUB : PAS ENCORE PUSH"
echo "==============================================================="
