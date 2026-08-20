#!/usr/bin/env bash
set -Eeuo pipefail

clear

echo "==============================================================="
echo " PINCABOS — BATCH IMPORT V3.5B"
echo " STAGING GUARD + WIDGET + BOUTONS"
echo " BASE DIRECTE V3.3"
echo " AUCUN PUSH GITHUB"
echo "==============================================================="
echo

REPO="/opt/pincabos/tmp/pr-integration"
EXPECTED_HEAD="9f7150cdc8d8540c6808669793c88454dfcf052b"

IMPORT_REL="opt/pincabos/web/pincabos_batch_import_live.py"
DASH_REL="opt/pincabos/web/pincabos_dashboard_lobby.py"

IMPORT="$REPO/$IMPORT_REL"
DASH="$REPO/$DASH_REL"

STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="/opt/pincabos/backups/batch-staging-v35b-$STAMP"
BACKUP_BRANCH="backup/pre-batch-staging-v35b-$STAMP"

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

CURRENT_BRANCH="$(git branch --show-current)"
CURRENT_HEAD="$(git rev-parse HEAD)"

echo "Branche : $CURRENT_BRANCH"
echo "HEAD    : $CURRENT_HEAD"

[ "$CURRENT_BRANCH" = "pincabos-pr-integration" ] ||
    fail "Mauvaise branche."

[ "$CURRENT_HEAD" = "$EXPECTED_HEAD" ] ||
    fail "HEAD differente de V3.3."

[ -z "$(git status --porcelain)" ] ||
    fail "Git non propre."

grep -q \
    'PINCABOS_BATCH_STAGE_ALL_V33' \
    "$IMPORT" ||
    fail "Stage All V3.3 absent."

grep -q \
    'PINCABOS_BATCH_WAIT_FULL_STAGE_V33' \
    "$REPO/opt/pincabos/web/pincabos_batch_import_worker_v2.py" ||
    fail "Worker Background V3.3 absent."

ok "Base V3.3 correcte."

echo
echo "=== 2. BACKUP ==="

mkdir -p "$BACKUP"

git branch "$BACKUP_BRANCH"

cp -a \
    "/$IMPORT_REL" \
    "$BACKUP/pincabos_batch_import_live.py.before"

cp -a \
    "/$DASH_REL" \
    "$BACKUP/pincabos_dashboard_lobby.py.before"

git bundle create \
    "$BACKUP/staging-before.bundle" \
    --all

ok "Backup : $BACKUP"
ok "Branche : $BACKUP_BRANCH"

echo
echo "=== 3. ETAT DU JOB IMPORT ACTUEL ==="

curl -fsS \
    --max-time 10 \
    http://127.0.0.1/api/batch-import/live/active \
    > "$BACKUP/active-before.json"

python3 - "$BACKUP/active-before.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as fh:
    d = json.load(fh)

j = d.get("job")

if not j:
    print("INFO [AUCUN JOB IMPORT ACTIF]")
    raise SystemExit

print("ID              :", j.get("id"))
print("STATE           :", j.get("state"))
print("UPLOADED        :", j.get("uploaded_archives"))
print("PROCESSED       :", j.get("processed_archives"))
print("TOTAL           :", j.get("total_archives"))
print("UPLOAD COMPLETE :", j.get("uploads_complete"))
print("CURRENT         :", j.get("current_item"))

running = [
    x for x in (j.get("uploads") or [])
    if isinstance(x, dict)
    and str(x.get("state") or "") == "running"
]

if running:
    raise SystemExit(
        "NOGO: un package est réellement en cours."
    )

if j.get("uploads_complete"):
    raise SystemExit(
        "NOGO: staging déjà complet; ne pas abandonner ce job."
    )

print()
print("GO [OK] Job de staging incomplet seulement.")
PY

JOB_ID="$(
python3 - "$BACKUP/active-before.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as fh:
    d = json.load(fh)

print(((d.get("job") or {}).get("id")) or "")
PY
)"

if [ -n "$JOB_ID" ]; then

    echo
    echo "=== 4. LIBERATION DU JOB INCOMPLET ==="

    systemctl stop \
        pincabos-batch-import-worker.service

    PYTHONPATH=/opt/pincabos/web \
    python3 - "$JOB_ID" <<'PY'
import sys
import pincabos_batch_import_queue_v2 as queue

job_id = sys.argv[1]

with queue.state_lock(True):

    job = queue.load_job_unlocked(job_id)

    if not job:
        raise SystemExit("NOGO: job introuvable.")

    running = [
        x for x in (job.get("uploads") or [])
        if isinstance(x, dict)
        and str(x.get("state") or "") == "running"
    ]

    if running:
        raise SystemExit(
            "NOGO: package running."
        )

    if job.get("uploads_complete"):
        raise SystemExit(
            "NOGO: staging complet."
        )

    job["state"] = "stopped"
    job["stop_requested"] = True
    job["pause_requested"] = False
    job["accepting_uploads"] = False
    job["finished_at"] = queue.utc_now()
    job["current_item"] = ""
    job["error"] = (
        "Téléversement incomplet abandonné "
        "avant installation V3.5B."
    )

    queue.add_event(
        job,
        "Téléversement incomplet abandonné proprement.",
        "warning",
    )

    queue.refresh_progress(
        job,
        "Arrêté — téléversement incomplet",
        "",
    )

    queue.cleanup_uploads(job)
    queue.save_job_unlocked(job)

    if queue.active_job_id_unlocked() == job_id:
        queue.set_active_unlocked(None)

print("GO [OK] Job incomplet libéré :", job_id)
PY

else
    echo
    echo "=== 4. LIBERATION DU JOB INCOMPLET ==="
    echo "INFO [SKIP] Aucun job incomplet."
fi

echo
echo "==============================================================="
echo " 5. PATCH IMPORT + DASHBOARD"
echo "==============================================================="

python3 - \
    "$IMPORT" \
    "$DASH" <<'PY'
from pathlib import Path
import re
import sys

import_path = Path(sys.argv[1])
dash_path = Path(sys.argv[2])


def die(message):
    raise SystemExit("NOGO PATCH: " + message)


# ============================================================
# IMPORT PAGE
# ============================================================

text = import_path.read_text(encoding="utf-8")

if "PINCABOS_BATCH_STAGING_GUARD_V35B" not in text:

    anchor = '''  async function submitQueue(target) {
    /* PINCABOS_BATCH_STAGE_ALL_V33 */
'''

    replacement = '''  /*
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
'''

    if text.count(anchor) != 1:
        die("submitQueue V3.3 introuvable")

    text = text.replace(anchor, replacement, 1)

    anchor = '''    const jobId = created.job.id;
'''

    replacement = '''    const jobId = created.job.id;

    pcosStagingTransfer = {
      jobId: jobId,
      total: files.length
    };
'''

    if text.count(anchor) != 1:
        die("jobId V3.3 introuvable")

    text = text.replace(anchor, replacement, 1)

    old = '''    } finally {
      disable(target, false);
    }
'''

    new = '''    } finally {
      pcosStagingTransfer = null;
      disable(target, false);
    }
'''

    if text.count(old) != 1:
        die("finally submitQueue introuvable")

    text = text.replace(old, new, 1)

    import_path.write_text(text, encoding="utf-8")

    print("GO [PATCH] Stage Guard navigateur")

else:
    print("GO [DEJA] Stage Guard navigateur")


# ============================================================
# DASHBOARD
# ============================================================

text = dash_path.read_text(encoding="utf-8")

if "PINCABOS_DASHBOARD_STAGING_V35B" not in text:

    anchor = '''    const progress = job?.progress || {};
'''

    replacement = '''    const progress = job?.progress || {};

    /* PINCABOS_DASHBOARD_STAGING_V35B */
    const totalUploads = Number(
      job?.total_archives
      ?? progress.total
      ?? 0
    );

    const uploaded = Number(
      job?.uploaded_archives
      ?? progress.uploaded
      ?? 0
    );

    const staging = Boolean(
      kind === "import"
      && job
      && job.uploads_complete === false
      && totalUploads > 0
      && uploaded < totalUploads
    );
'''

    if text.count(anchor) != 1:
        die("progress dashboard introuvable")

    text = text.replace(anchor, replacement, 1)

    old = '''    if (status) {
      status.textContent = error
        ? "API indisponible"
        : label(state);
    }
'''

    new = '''    if (status) {
      status.textContent = error
        ? "API indisponible"
        : staging
          ? "Téléversement"
          : label(state);
    }
'''

    if text.count(old) != 1:
        die("status dashboard introuvable")

    text = text.replace(old, new, 1)

    old = '''      } else {
        const count = total(job);
'''

    new = '''      } else if (staging) {

        detail.textContent =
          `Téléversement vers le cab `
          + `${uploaded}/${totalUploads} · `
          + `garde la page Import ouverte jusqu'à `
          + `${totalUploads}/${totalUploads}`;

      } else {
        const count = total(job);
'''

    if text.count(old) != 1:
        die("detail dashboard introuvable")

    text = text.replace(old, new, 1)

    # Pause
    pattern = re.compile(
        r'const canPause\s*=\s*'
        r'\["uploading",\s*"queued",\s*"running"\]'
        r'\.includes\(state\);'
    )

    text, count = pattern.subn(
        '''const canPause =
      !staging
      && ["queued", "running"].includes(state);''',
        text,
        count=1,
    )

    if count != 1:
        # Accepte aussi l'ancienne variante queued/running.
        pattern2 = re.compile(
            r'const canPause\s*=\s*'
            r'\["queued",\s*"running"\]'
            r'\.includes\(state\);'
        )

        text, count = pattern2.subn(
            '''const canPause =
      !staging
      && ["queued", "running"].includes(state);''',
            text,
            count=1,
        )

    if count != 1:
        die("canPause dashboard introuvable")

    # Resume
    old = '''    const canResume =
      ["paused", "pausing"].includes(state) &&
'''

    if old in text:
        new = '''    const canResume =
      !staging &&
      ["paused", "pausing"].includes(state) &&
'''
        text = text.replace(old, new, 1)

    else:
        old = '''    const canResume =
      state === "paused" &&
'''

        new = '''    const canResume =
      !staging &&
      state === "paused" &&
'''

        if text.count(old) != 1:
            die("canResume dashboard introuvable")

        text = text.replace(old, new, 1)

    # Skip
    old = '''    const canSkip =
      state === "paused" &&
'''

    new = '''    const canSkip =
      !staging &&
      state === "paused" &&
'''

    if text.count(old) != 1:
        die("canSkip dashboard introuvable")

    text = text.replace(old, new, 1)

    # Libelles permanents des boutons.
    old = '''    if (pause) {
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
'''

    new = '''    /* PINCABOS_BATCH_BUTTON_LABELS_V35B */
    if (pause) {
      pause.hidden = false;
      pause.disabled = !canPause;
      pause.textContent =
        state === "pausing"
          ? "Pause…"
          : "Pause";
    }

    if (resume) {
      resume.hidden = false;
      resume.disabled = !canResume;
      resume.textContent = "Reprendre";
    }

    if (skip) {
      skip.hidden = false;
      skip.disabled = !canSkip;
      skip.textContent = "Skip";
    }
'''

    if text.count(old) != 1:
        die("bloc boutons dashboard introuvable")

    text = text.replace(old, new, 1)

    # Disabled visuellement clair.
    old = '''#pco-dashboard-batch-controls button[disabled]{
  opacity:.55;
  cursor:wait;
}
'''

    new = '''#pco-dashboard-batch-controls button[disabled]{
  opacity:.30;
  cursor:not-allowed;
  filter:grayscale(1);
  box-shadow:none;
}
'''

    if old in text:
        text = text.replace(old, new, 1)

    dash_path.write_text(text, encoding="utf-8")

    print("GO [PATCH] Dashboard staging + boutons")

else:
    print("GO [DEJA] Dashboard V3.5B")
PY

echo
echo "=== 6. VALIDATION SOURCE ==="

python3 -m py_compile "$IMPORT" ||
    fail "Syntaxe Import."

python3 -m py_compile "$DASH" ||
    fail "Syntaxe Dashboard."

git diff --check ||
    fail "git diff --check."

grep -q \
    'PINCABOS_BATCH_STAGING_GUARD_V35B' \
    "$IMPORT" ||
    fail "Stage Guard absent."

grep -q \
    'PINCABOS_DASHBOARD_STAGING_V35B' \
    "$DASH" ||
    fail "Dashboard Stage Guard absent."

grep -q \
    'PINCABOS_BATCH_BUTTON_LABELS_V35B' \
    "$DASH" ||
    fail "Labels boutons absents."

ok "Source V3.5B valide."

echo
echo "=== 7. DIFF ==="

git --no-pager diff --stat

echo
git --no-pager diff \
    -- "$IMPORT_REL" \
       "$DASH_REL" \
    | head -360

echo
echo "=== 8. COMMIT LOCAL ==="

git add \
    "$IMPORT_REL" \
    "$DASH_REL"

git commit \
    -m "fix(batch): guard staging and clarify service controls"

NEW_HEAD="$(git rev-parse HEAD)"

ok "Commit : $NEW_HEAD"

echo
echo "=== 9. DEPLOIEMENT LIVE ==="

deploy()
{
    REL="$1"
    SRC="$REPO/$REL"
    DST="/$REL"

    DST_UID="$(stat -c %u "$DST")"
    DST_GID="$(stat -c %g "$DST")"
    DST_MODE="$(stat -c %a "$DST")"

    TMP="${DST}.v35b.$$"

    install \
        -o "$DST_UID" \
        -g "$DST_GID" \
        -m "$DST_MODE" \
        "$SRC" \
        "$TMP"

    mv -f "$TMP" "$DST"

    echo "GO [DEPLOY] $DST"
}

deploy "$IMPORT_REL"
deploy "$DASH_REL"

echo
echo "=== 10. RESTART SERVICES ==="

systemctl start \
    pincabos-batch-import-worker.service

systemctl restart \
    pincabos-batch-import-worker.service

sleep 2

systemctl is-active --quiet \
    pincabos-batch-import-worker.service ||
    fail "Worker inactif."

ok "Worker actif."

systemctl restart \
    pincabos-webapp.service

sleep 3

systemctl is-active --quiet \
    pincabos-webapp.service ||
    fail "WebApp inactive."

ok "WebApp active."

echo
echo "=== 11. VALIDATION HTTP ==="

curl -fsS \
    --max-time 10 \
    http://127.0.0.1/tools/batch-import \
    > /tmp/pco-v35b-import.html

grep -q \
    'PINCABOS_BATCH_STAGING_GUARD_V35B' \
    /tmp/pco-v35b-import.html ||
    fail "Stage Guard non servi."

curl -fsS \
    --max-time 10 \
    http://127.0.0.1/ \
    > /tmp/pco-v35b-dashboard.html

grep -q \
    'PINCABOS_DASHBOARD_STAGING_V35B' \
    /tmp/pco-v35b-dashboard.html ||
    fail "Dashboard V3.5B non servi."

ok "Import + Dashboard V3.5B servis."

echo
echo "=== 12. ACTIVE FINAL ==="

curl -s \
    --max-time 5 \
    http://127.0.0.1/api/batch-import/live/active |
python3 -m json.tool

echo
echo "=== 13. GIT FINAL ==="

cd "$REPO"

echo "Branche : $(git branch --show-current)"
echo "HEAD    : $(git rev-parse HEAD)"

[ -z "$(git status --porcelain)" ] ||
    fail "Git non propre."

ok "Git propre."

echo
echo "==============================================================="
echo " GO [OK] BATCH IMPORT V3.5B INSTALLE"
echo "==============================================================="
echo
echo "PENDANT STAGING :"
echo "  Widget = TELEVERSEMENT"
echo "  Page Import doit rester ouverte"
echo "  Pause grisee"
echo "  Reprendre grise"
echo "  Skip grise"
echo "  Stop actif"
echo
echo "APRES N/N :"
echo "  uploads_complete = true"
echo "  navigateur libere"
echo "  worker background autonome"
echo "  Pause/Reprendre/Skip via widget"
echo
echo "Backup : $BACKUP"
echo "HEAD   : $NEW_HEAD"
echo "GITHUB : PAS ENCORE PUSH"
echo "==============================================================="
