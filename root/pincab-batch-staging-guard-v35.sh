#!/usr/bin/env bash
set -Eeuo pipefail

clear

echo "==============================================================="
echo " PINCABOS — BATCH IMPORT V3.5"
echo " STAGING GUARD + ETAT WIDGET EXACT"
echo " BACKGROUND APRES N/N"
echo " AUCUN PUSH GITHUB"
echo "==============================================================="
echo

REPO="/opt/pincabos/tmp/pr-integration"

IMPORT_REL="opt/pincabos/web/pincabos_batch_import_live.py"
DASH_REL="opt/pincabos/web/pincabos_dashboard_lobby.py"

IMPORT="$REPO/$IMPORT_REL"
DASH="$REPO/$DASH_REL"

STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="/opt/pincabos/backups/batch-staging-v35-$STAMP"
BACKUP_BRANCH="backup/pre-batch-staging-v35-$STAMP"

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

echo "=== 1. VALIDATION ROOT / GIT ==="

[ "$(id -u)" -eq 0 ] ||
    fail "Execution root requise."

[ -d "$REPO/.git" ] ||
    fail "Repo absent : $REPO"

cd "$REPO"

echo "Branche : $(git branch --show-current)"
echo "HEAD    : $(git rev-parse HEAD)"

[ "$(git branch --show-current)" = "pincabos-pr-integration" ] ||
    fail "Mauvaise branche."

[ -z "$(git status --porcelain)" ] ||
    fail "Git non propre."

grep -q \
    'PINCABOS_BATCH_STAGE_ALL_V33' \
    "$IMPORT" ||
    fail "V3.3 Stage All absent."

grep -q \
    'PINCABOS_BATCH_BUTTON_LABELS_V34' \
    "$DASH" ||
    fail "V3.4 boutons absent."

ok "Base V3.3/V3.4 valide."

echo
echo "=== 2. BACKUP SOURCE ==="

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
echo "==============================================================="
echo " 3. TRAITEMENT D'UN EVENTUEL JOB DE STAGING INCOMPLET"
echo "==============================================================="

curl -fsS \
    --max-time 10 \
    http://127.0.0.1/api/batch-import/live/active \
    > "$BACKUP/active-before.json"

JOB_ID="$(
python3 - "$BACKUP/active-before.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as fh:
    data = json.load(fh)

job = data.get("job") or {}
print(job.get("id") or "")
PY
)"

if [ -z "$JOB_ID" ]; then

    echo "GO [OK] Aucun job Import actif."

else

    echo "Job detecte : $JOB_ID"

    python3 - "$BACKUP/active-before.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as fh:
    data = json.load(fh)

j = data.get("job") or {}

print("STATE           :", j.get("state"))
print("UPLOADED        :", j.get("uploaded_archives"))
print("PROCESSED       :", j.get("processed_archives"))
print("TOTAL           :", j.get("total_archives"))
print("UPLOAD COMPLETE :", j.get("uploads_complete"))

running = [
    x
    for x in (j.get("uploads") or [])
    if isinstance(x, dict)
    and str(x.get("state") or "") == "running"
]

if running:
    raise SystemExit(
        "NOGO: un package est réellement en traitement."
    )

if bool(j.get("uploads_complete")):
    raise SystemExit(
        "NOGO: ce job a fini son staging et doit être "
        "laissé au worker."
    )

print("GO [OK] Job uniquement en staging incomplet.")
PY

    echo
    echo "--- LIBERATION DE LA FILE INCOMPLETE ---"

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
        raise SystemExit(
            "NOGO: job disparu."
        )

    running = [
        x
        for x in (job.get("uploads") or [])
        if isinstance(x, dict)
        and str(x.get("state") or "") == "running"
    ]

    if running:
        raise SystemExit(
            "NOGO: package running."
        )

    if job.get("uploads_complete"):
        raise SystemExit(
            "NOGO: staging déjà complet."
        )

    job["state"] = "stopped"
    job["stop_requested"] = True
    job["pause_requested"] = False
    job["accepting_uploads"] = False
    job["finished_at"] = queue.utc_now()
    job["current_item"] = ""
    job["error"] = (
        "Téléversement incomplet abandonné avant "
        "installation du Stage Guard V3.5."
    )

    queue.add_event(
        job,
        (
            "File de téléversement incomplète abandonnée "
            "proprement avant V3.5."
        ),
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

print(
    "GO [OK] Ancienne file incomplete liberee :",
    job_id,
)
PY

    ok "Aucun package temporaire incomplet conserve."
fi

echo
echo "==============================================================="
echo " 4. PATCH SOURCE V3.5"
echo "==============================================================="

python3 - \
    "$IMPORT" \
    "$DASH" <<'PY'
from pathlib import Path
import re
import sys

import_path = Path(sys.argv[1])
dash_path = Path(sys.argv[2])


def die(msg):
    raise SystemExit(
        "NOGO PATCH: " + msg
    )


# ============================================================
# IMPORT LIVE
# ============================================================

text = import_path.read_text(
    encoding="utf-8"
)

marker = "PINCABOS_BATCH_STAGING_GUARD_V35"

if marker not in text:

    # --------------------------------------------------------
    # 1. Le vrai state serveur doit être UPLOADING tant
    #    que le staging n'est pas complet.
    # --------------------------------------------------------

    anchor = '''        job["accepting_uploads"] = True
'''

    insert = '''        job["accepting_uploads"] = True

        # PINCABOS_BATCH_STAGING_STATE_V35
        # Tant que le navigateur envoie les packages,
        # l'état public doit dire TELEVERSEMENT, pas EN FILE.
        if (
            not job.get("uploads_complete")
            and str(job.get("state", "")) in {
                "queued",
                "uploading",
            }
        ):
            job["state"] = "uploading"
'''

    count = text.count(anchor)

    if count != 1:
        die(
            "accepting_uploads attendu 1 fois, trouve "
            + str(count)
        )

    text = text.replace(
        anchor,
        insert,
        1,
    )

    # --------------------------------------------------------
    # 2. Protection navigateur pendant le staging.
    # --------------------------------------------------------

    anchor = '''  async function submitQueue(target) {
    /* PINCABOS_BATCH_STAGE_ALL_V33 */
'''

    guard = '''  /*
   * PINCABOS_BATCH_STAGING_GUARD_V35
   *
   * Tant que les fichiers locaux ne sont pas tous rendus
   * sur le cab, quitter cette page détruirait la source
   * File API du navigateur.
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

    count = text.count(anchor)

    if count != 1:
        die(
            "submitQueue V3.3 attendu 1 fois, trouve "
            + str(count)
        )

    text = text.replace(
        anchor,
        guard,
        1,
    )

    # --------------------------------------------------------
    # 3. Active le guard dès que le job serveur existe.
    # --------------------------------------------------------

    anchor = '''    const jobId = created.job.id;
'''

    insert = '''    const jobId = created.job.id;

    pcosStagingTransfer = {
      jobId,
      total: files.length
    };
'''

    count = text.count(anchor)

    if count != 1:
        die(
            "jobId attendu 1 fois, trouve "
            + str(count)
        )

    text = text.replace(
        anchor,
        insert,
        1,
    )

    # --------------------------------------------------------
    # 4. Le finally libère le guard seulement quand submitQueue
    #    se termine (succès ou arrêt propre après erreur).
    # --------------------------------------------------------

    old = '''    } finally {
      disable(target, false);
    }
'''

    new = '''    } finally {
      pcosStagingTransfer = null;
      disable(target, false);
    }
'''

    count = text.count(old)

    if count != 1:
        die(
            "finally submitQueue attendu 1 fois, trouve "
            + str(count)
        )

    text = text.replace(
        old,
        new,
        1,
    )

    import_path.write_text(
        text,
        encoding="utf-8",
    )

    print(
        "GO [PATCH] Import Stage Guard V3.5"
    )

else:
    print(
        "GO [DEJA] Import Stage Guard V3.5"
    )


# ============================================================
# DASHBOARD
# ============================================================

text = dash_path.read_text(
    encoding="utf-8"
)

marker = "PINCABOS_DASHBOARD_STAGING_V35"

if marker not in text:

    # --------------------------------------------------------
    # Variables staging réelles.
    # --------------------------------------------------------

    anchor = '''    const progress = job?.progress || {};
'''

    insert = '''    const progress = job?.progress || {};

    /* PINCABOS_DASHBOARD_STAGING_V35 */
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

    count = text.count(anchor)

    if count != 1:
        die(
            "dashboard progress attendu 1 fois, trouve "
            + str(count)
        )

    text = text.replace(
        anchor,
        insert,
        1,
    )

    # --------------------------------------------------------
    # Titre de state.
    # --------------------------------------------------------

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

    count = text.count(old)

    if count != 1:
        die(
            "dashboard status attendu 1 fois, trouve "
            + str(count)
        )

    text = text.replace(
        old,
        new,
        1,
    )

    # --------------------------------------------------------
    # Texte explicite de staging.
    # --------------------------------------------------------

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

    count = text.count(old)

    if count != 1:
        die(
            "dashboard detail attendu 1 fois, trouve "
            + str(count)
        )

    text = text.replace(
        old,
        new,
        1,
    )

    # --------------------------------------------------------
    # Pendant le staging :
    # Pause / Resume / Skip interdits.
    # STOP reste possible.
    # --------------------------------------------------------

    pattern = re.compile(
        r'const canPause = '
        r'\["uploading", "queued", "running"\]'
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
        die(
            "dashboard canPause attendu 1 fois"
        )

    # Reprendre
    old = '''    const canResume =
      ["paused", "pausing"].includes(state) &&
'''

    new = '''    const canResume =
      !staging &&
      ["paused", "pausing"].includes(state) &&
'''

    count = text.count(old)

    if count != 1:
        die(
            "dashboard canResume attendu 1 fois, trouve "
            + str(count)
        )

    text = text.replace(
        old,
        new,
        1,
    )

    # Skip
    old = '''    const canSkip =
      state === "paused" &&
'''

    new = '''    const canSkip =
      !staging &&
      state === "paused" &&
'''

    count = text.count(old)

    if count != 1:
        die(
            "dashboard canSkip attendu 1 fois, trouve "
            + str(count)
        )

    text = text.replace(
        old,
        new,
        1,
    )

    # --------------------------------------------------------
    # Disabled vraiment visible.
    # --------------------------------------------------------

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
        text = text.replace(
            old,
            new,
            1,
        )

    dash_path.write_text(
        text,
        encoding="utf-8",
    )

    print(
        "GO [PATCH] Dashboard staging exact V3.5"
    )

else:
    print(
        "GO [DEJA] Dashboard V3.5"
    )
PY

echo
echo "=== 5. VALIDATION SOURCE ==="

python3 -m py_compile "$IMPORT" ||
    fail "Syntaxe Import."

python3 -m py_compile "$DASH" ||
    fail "Syntaxe Dashboard."

git diff --check ||
    fail "git diff --check."

grep -q \
    'PINCABOS_BATCH_STAGING_GUARD_V35' \
    "$IMPORT" ||
    fail "Stage Guard absent."

grep -q \
    'PINCABOS_BATCH_STAGING_STATE_V35' \
    "$IMPORT" ||
    fail "Stage state absent."

grep -q \
    'PINCABOS_DASHBOARD_STAGING_V35' \
    "$DASH" ||
    fail "Dashboard staging absent."

ok "Source V3.5 valide."

echo
echo "=== 6. DIFF ==="

git --no-pager diff --stat

echo
git --no-pager diff \
    -- "$IMPORT_REL" \
       "$DASH_REL" \
    | head -340

echo
echo "=== 7. COMMIT LOCAL ==="

git add \
    "$IMPORT_REL" \
    "$DASH_REL"

git commit \
    -m "fix(batch): guard incomplete staging and clarify dashboard"

NEW_HEAD="$(git rev-parse HEAD)"

ok "Commit local : $NEW_HEAD"
echo "GITHUB : AUCUN PUSH"

echo
echo "==============================================================="
echo " 8. DEPLOIEMENT LIVE"
echo "==============================================================="

deploy()
{
    REL="$1"
    SRC="$REPO/$REL"
    DST="/$REL"

    UID_DST="$(stat -c %u "$DST")"
    GID_DST="$(stat -c %g "$DST")"
    MODE_DST="$(stat -c %a "$DST")"

    TMP="${DST}.v35.$$"

    install \
        -o "$UID_DST" \
        -g "$GID_DST" \
        -m "$MODE_DST" \
        "$SRC" \
        "$TMP"

    mv -f "$TMP" "$DST"

    echo "GO [DEPLOY] $DST"
}

deploy "$IMPORT_REL"
deploy "$DASH_REL"

echo
echo "=== 9. STAGING == LIVE ==="

for REL in \
    "$IMPORT_REL" \
    "$DASH_REL"
do
    S="$(sha256sum "$REPO/$REL" | awk '{print $1}')"
    L="$(sha256sum "/$REL" | awk '{print $1}')"

    [ "$S" = "$L" ] ||
        fail "Mismatch : $REL"

    echo "GO [OK] $REL"
done

echo
echo "==============================================================="
echo " 10. RESTART SERVICES"
echo "==============================================================="

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
    > /tmp/pincab-v35-import.html

grep -q \
    'PINCABOS_BATCH_STAGING_GUARD_V35' \
    /tmp/pincab-v35-import.html ||
    fail "Stage Guard non servi."

curl -fsS \
    --max-time 10 \
    http://127.0.0.1/ \
    > /tmp/pincab-v35-dashboard.html

grep -q \
    'PINCABOS_DASHBOARD_STAGING_V35' \
    /tmp/pincab-v35-dashboard.html ||
    fail "Dashboard V3.5 non servi."

ok "Import + Dashboard V3.5 servis."

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
echo " GO [OK] BATCH STAGING GUARD V3.5 INSTALLE"
echo "==============================================================="
echo
echo "PENDANT LE TELEVERSEMENT :"
echo "  Widget = TELEVERSEMENT"
echo "  N/N affiche clairement"
echo "  Message = garde page Import ouverte"
echo "  Pause = desactive"
echo "  Reprendre = desactive"
echo "  Skip = desactive"
echo "  Stop = disponible"
echo "  Quitter/recharger = avertissement navigateur"
echo
echo "APRES N/N :"
echo "  uploads_complete = true"
echo "  page peut etre quittee"
echo "  worker background prend le relais"
echo "  widget controle Pause/Reprendre/Skip/Stop"
echo
echo "Backup : $BACKUP"
echo "HEAD   : $NEW_HEAD"
echo "GITHUB : PAS ENCORE PUSH"
echo "==============================================================="
