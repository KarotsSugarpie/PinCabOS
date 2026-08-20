#!/usr/bin/env bash
set -Eeuo pipefail

clear

echo "==============================================================="
echo " PINCABOS — BATCH CONTROLS V3.2B"
echo " FIX PAUSING -> PAUSED + REPRENDRE"
echo " CONSERVATION DU JOB ACTUEL"
echo " AUCUN PUSH GITHUB"
echo "==============================================================="
echo

REPO="/opt/pincabos/tmp/pr-integration"
EXPECTED_HEAD="cd66f83240c360ffbe8d6eac0f3d0ebf228b3611"
EXPECTED_JOB="d649c032da4040cbafaeada5e607d91e"

QUEUE_REL="opt/pincabos/web/pincabos_batch_import_queue_v2.py"
WORKER_REL="opt/pincabos/web/pincabos_batch_import_worker_v2.py"
DASH_REL="opt/pincabos/web/pincabos_dashboard_lobby.py"

QUEUE="$REPO/$QUEUE_REL"
WORKER="$REPO/$WORKER_REL"
DASH="$REPO/$DASH_REL"

STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="/opt/pincabos/backups/batch-controls-v32b-$STAMP"
BACKUP_BRANCH="backup/pre-batch-controls-v32b-$STAMP"

ACTIVE_JSON="/tmp/pincab-v32b-active.json"

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
    fail "Repo absent : $REPO"

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
echo "=== 2. LECTURE FRAICHE DU JOB ==="

curl -fsS \
    --max-time 10 \
    http://127.0.0.1/api/batch-import/live/active \
    > "$ACTIVE_JSON"

python3 -m json.tool "$ACTIVE_JSON"

echo
echo "=== 3. VALIDATION DU JOB SANS stdin CONFLICT ==="

python3 - "$ACTIVE_JSON" "$EXPECTED_JOB" <<'PY'
import json
import sys

path = sys.argv[1]
expected = sys.argv[2]

with open(path, "r", encoding="utf-8") as fh:
    data = json.load(fh)

job = data.get("job") or {}

job_id = str(job.get("id") or "")
state = str(job.get("state") or "")

uploads = [
    item
    for item in (job.get("uploads") or [])
    if isinstance(item, dict)
]

running = [
    item
    for item in uploads
    if str(item.get("state") or "") == "running"
]

print("ID               :", job_id)
print("STATE            :", state)
print("UPLOADED         :", job.get("uploaded_archives"))
print("PROCESSED        :", job.get("processed_archives"))
print("TOTAL            :", job.get("total_archives"))
print("CURRENT ITEM     :", job.get("current_item"))
print("PAUSE REQUESTED  :", job.get("pause_requested"))
print("RUNNING ITEMS    :", len(running))
print()

for item in uploads:
    print(
        "%3s | %-10s | %s"
        % (
            item.get("index", ""),
            item.get("state", ""),
            item.get("name", ""),
        )
    )

if job_id != expected:
    raise SystemExit(
        f"NOGO: job attendu {expected}, actuel {job_id or 'AUCUN'}"
    )

if state not in {"pausing", "paused"}:
    raise SystemExit(
        f"NOGO: état inattendu : {state}"
    )

if running:
    raise SystemExit(
        "NOGO: un package est réellement RUNNING. "
        "Aucune transition forcée."
    )

print()
print("GO [OK] Frontiere securisee deja atteinte.")
PY

ok "Aucun package en cours : pause finalisable."

echo
echo "=== 4. BACKUP ==="

mkdir -p "$BACKUP"

git branch "$BACKUP_BRANCH"

for REL in \
    "$QUEUE_REL" \
    "$WORKER_REL" \
    "$DASH_REL"
do
    cp -a \
        "/$REL" \
        "$BACKUP/$(basename "$REL").before"
done

cp -a "$ACTIVE_JSON" "$BACKUP/job-before.json"

git bundle create \
    "$BACKUP/staging-before.bundle" \
    --all

ok "Backup : $BACKUP"
ok "Branche : $BACKUP_BRANCH"

echo
echo "==============================================================="
echo " 5. GEL TEMPORAIRE DU WORKER"
echo "==============================================================="

systemctl stop pincabos-batch-import-worker.service

if systemctl is-active --quiet pincabos-batch-import-worker.service
then
    fail "Worker encore actif."
fi

ok "Worker arrete proprement."

echo
echo "==============================================================="
echo " 6. FINALISATION DU JOB PAUSING -> PAUSED"
echo "==============================================================="

PYTHONPATH=/opt/pincabos/web \
python3 - "$EXPECTED_JOB" <<'PY'
import sys
import pincabos_batch_import_queue_v2 as queue

job_id = sys.argv[1]

job = queue.load_job(job_id)

if not job:
    raise SystemExit("NOGO: job introuvable.")

state = str(job.get("state") or "")

running = [
    item
    for item in (job.get("uploads") or [])
    if isinstance(item, dict)
    and str(item.get("state") or "") == "running"
]

if running:
    raise SystemExit(
        "NOGO: un package est RUNNING."
    )

if state == queue.PAUSING_STATE:
    result = queue.complete_pause(job_id)

elif state == queue.PAUSED_STATE:
    result = job

else:
    raise SystemExit(
        f"NOGO: état inattendu : {state}"
    )

result = queue.load_job(job_id) or result

print("ID               :", result.get("id"))
print("STATE            :", result.get("state"))
print("UPLOADED         :", result.get("uploaded_archives"))
print("PROCESSED        :", result.get("processed_archives"))
print("PAUSE REQUESTED  :", result.get("pause_requested"))

if result.get("state") != queue.PAUSED_STATE:
    raise SystemExit(
        "NOGO: transition PAUSED non appliquee."
    )

print("GO [OK] Job maintenant PAUSED.")
PY

echo
echo "==============================================================="
echo " 7. PATCH DEFINITIF V3.2"
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


def die(message):
    raise SystemExit("NOGO PATCH: " + message)


# ============================================================
# QUEUE
# Reprendre pendant PAUSING annule la demande de pause.
# ============================================================

text = queue_path.read_text(encoding="utf-8")

marker = "PINCABOS_BATCH_PAUSING_FIX_V32"

if marker not in text:

    old = '''        if str(job.get("state", "")) == PAUSING_STATE:
            return job
'''

    new = '''        if str(job.get("state", "")) == PAUSING_STATE:
            # PINCABOS_BATCH_PAUSING_FIX_V32
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

            refresh_progress(
                job,
                "Reprise du Batch",
            )

            save_job_unlocked(job)

            if not active_job_id_unlocked():
                set_active_unlocked(job_id)

            return job
'''

    count = text.count(old)

    if count != 1:
        die(
            "queue resume PAUSING : "
            f"attendu 1 occurrence, trouve {count}"
        )

    text = text.replace(old, new, 1)

    queue_path.write_text(
        text,
        encoding="utf-8",
    )

    print("GO [PATCH] queue resume PAUSING")
else:
    print("GO [DEJA] queue V3.2")


# ============================================================
# WORKER
# PAUSING à l'entrée de la boucle = frontière déjà atteinte.
# ============================================================

text = worker_path.read_text(encoding="utf-8")

marker = "PINCABOS_WORKER_PAUSING_FIX_V32"

if marker not in text:

    old = '''        if str(current.get("state", "")) == queue.PAUSED_STATE:
            return

        if current.get("stop_requested"):
'''

    new = '''        state = str(current.get("state", ""))

        if state == queue.PAUSED_STATE:
            return

        # PINCABOS_WORKER_PAUSING_FIX_V32
        if state == queue.PAUSING_STATE:
            queue.complete_pause(job_id)
            return

        if current.get("stop_requested"):
'''

    count = text.count(old)

    if count != 1:
        die(
            "worker PAUSING : "
            f"attendu 1 occurrence, trouve {count}"
        )

    text = text.replace(old, new, 1)

    worker_path.write_text(
        text,
        encoding="utf-8",
    )

    print("GO [PATCH] worker PAUSING -> PAUSED")
else:
    print("GO [DEJA] worker V3.2")


# ============================================================
# DASHBOARD
# Reprendre doit être disponible durant PAUSING aussi.
# ============================================================

text = dash_path.read_text(encoding="utf-8")

marker = "PINCABOS_DASHBOARD_PAUSING_RESUME_V32"

if marker not in text:

    old = '''    const canResume =
      state === "paused" &&
'''

    new = '''    /* PINCABOS_DASHBOARD_PAUSING_RESUME_V32 */
    const canResume =
      ["paused", "pausing"].includes(state) &&
'''

    count = text.count(old)

    if count != 1:
        die(
            "dashboard canResume : "
            f"attendu 1 occurrence, trouve {count}"
        )

    text = text.replace(old, new, 1)

    dash_path.write_text(
        text,
        encoding="utf-8",
    )

    print("GO [PATCH] Dashboard Resume PAUSING")
else:
    print("GO [DEJA] Dashboard V3.2")
PY

echo
echo "=== 8. VALIDATION SOURCE ==="

python3 -m py_compile "$QUEUE" ||
    fail "Syntaxe Queue."

python3 -m py_compile "$WORKER" ||
    fail "Syntaxe Worker."

python3 -m py_compile "$DASH" ||
    fail "Syntaxe Dashboard."

git diff --check ||
    fail "git diff --check."

grep -q \
    'PINCABOS_BATCH_PAUSING_FIX_V32' \
    "$QUEUE" ||
    fail "Marqueur Queue absent."

grep -q \
    'PINCABOS_WORKER_PAUSING_FIX_V32' \
    "$WORKER" ||
    fail "Marqueur Worker absent."

grep -q \
    'PINCABOS_DASHBOARD_PAUSING_RESUME_V32' \
    "$DASH" ||
    fail "Marqueur Dashboard absent."

ok "Source V3.2 valide."

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

ok "Commit local : $NEW_HEAD"
echo "GITHUB : AUCUN PUSH"

echo
echo "==============================================================="
echo " 11. DEPLOIEMENT LIVE"
echo "==============================================================="

deploy()
{
    REL="$1"
    SRC="$REPO/$REL"
    DST="/$REL"

    DST_UID="$(stat -c %u "$DST")"
    DST_GID="$(stat -c %g "$DST")"
    DST_MODE="$(stat -c %a "$DST")"

    TMP="${DST}.v32b.$$"

    install \
        -o "$DST_UID" \
        -g "$DST_GID" \
        -m "$DST_MODE" \
        "$SRC" \
        "$TMP"

    mv -f "$TMP" "$DST"

    echo "GO [DEPLOY] $DST"
}

deploy "$QUEUE_REL"
deploy "$WORKER_REL"
deploy "$DASH_REL"

echo
echo "=== 12. STAGING == LIVE ==="

for REL in \
    "$QUEUE_REL" \
    "$WORKER_REL" \
    "$DASH_REL"
do
    SRC_HASH="$(
        sha256sum "$REPO/$REL" |
        awk '{print $1}'
    )"

    LIVE_HASH="$(
        sha256sum "/$REL" |
        awk '{print $1}'
    )"

    [ "$SRC_HASH" = "$LIVE_HASH" ] ||
        fail "Mismatch : $REL"

    echo "GO [OK] $REL"
done

echo
echo "==============================================================="
echo " 13. RESTART SERVICES"
echo "==============================================================="

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
echo "=== 14. VERIFICATION JOB APRES RESTART ==="

curl -fsS \
    --max-time 10 \
    http://127.0.0.1/api/batch-import/live/active \
    > /tmp/pincab-v32b-after.json

python3 - \
    /tmp/pincab-v32b-after.json \
    "$EXPECTED_JOB" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as fh:
    data = json.load(fh)

expected = sys.argv[2]
job = data.get("job") or {}

print("ID               :", job.get("id"))
print("STATE            :", job.get("state"))
print("UPLOADED         :", job.get("uploaded_archives"))
print("PROCESSED        :", job.get("processed_archives"))
print("TOTAL            :", job.get("total_archives"))
print("CURRENT ITEM     :", job.get("current_item"))
print("PAUSE REQUESTED  :", job.get("pause_requested"))
print("RESUMABLE        :", data.get("resumable"))
print("REMAINING        :", data.get("remaining"))

if str(job.get("id") or "") != expected:
    raise SystemExit("NOGO: mauvais job apres restart.")

if str(job.get("state") or "") != "paused":
    raise SystemExit(
        "NOGO: le job devrait etre PAUSED."
    )

print("GO [OK] Job conserve en PAUSED.")
PY

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
echo " GO [OK] BATCH PAUSE V3.2B INSTALLE"
echo "==============================================================="
echo
echo "JOB CONSERVE :"
echo "  $EXPECTED_JOB"
echo
echo "ATTENDU :"
echo "  state      = paused"
echo "  processed  = 1"
echo "  uploaded   = 2"
echo "  total      = 4"
echo
echo "NE RECHARGE PAS LE NAVIGATEUR."
echo "Clique maintenant REPRENDRE."
echo
echo "Backup : $BACKUP"
echo "HEAD   : $NEW_HEAD"
echo "GITHUB : PAS ENCORE PUSH"
echo "==============================================================="
