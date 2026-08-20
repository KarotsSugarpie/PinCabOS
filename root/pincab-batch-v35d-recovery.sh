#!/usr/bin/env bash
set -Eeuo pipefail

clear

echo "==============================================================="
echo " PINCABOS — BATCH IMPORT V3.5D RECOVERY"
echo " FIX JOB STOPPED FANTOME + FIN PATCH DASHBOARD"
echo " CONSERVE PATCH PARTIEL V3.5B"
echo " AUCUN PUSH GITHUB"
echo "==============================================================="
echo

REPO="/opt/pincabos/tmp/pr-integration"
EXPECTED_HEAD="9f7150cdc8d8540c6808669793c88454dfcf052b"
OLD_JOB="17423af15156435a8468f648c90b975d"

IMPORT_REL="opt/pincabos/web/pincabos_batch_import_live.py"
DASH_REL="opt/pincabos/web/pincabos_dashboard_lobby.py"

IMPORT="$REPO/$IMPORT_REL"
DASH="$REPO/$DASH_REL"

STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="/opt/pincabos/backups/batch-v35d-$STAMP"
BACKUP_BRANCH="backup/pre-batch-v35d-$STAMP"

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

echo "=== 1. VALIDATION SERVICES ==="

systemctl start pincabos-batch-import-worker.service

systemctl is-active --quiet \
    pincabos-batch-import-worker.service ||
    fail "Worker Import inactif."

systemctl is-active --quiet \
    pincabos-webapp.service ||
    fail "WebApp inactive."

ok "Worker + WebApp actifs."

echo
echo "=== 2. VALIDATION GIT PARTIEL ==="

[ "$(id -u)" -eq 0 ] ||
    fail "Root requis."

cd "$REPO"

echo "Branche : $(git branch --show-current)"
echo "HEAD    : $(git rev-parse HEAD)"
echo

git status --short

[ "$(git branch --show-current)" = "pincabos-pr-integration" ] ||
    fail "Mauvaise branche."

[ "$(git rev-parse HEAD)" = "$EXPECTED_HEAD" ] ||
    fail "HEAD inattendue."

BAD=0

while IFS= read -r REL
do
    [ -n "$REL" ] || continue

    case "$REL" in
        "$IMPORT_REL"|"$DASH_REL")
            echo "GO [AUTORISE] $REL"
            ;;
        *)
            echo "NOGO [INATTENDU] $REL"
            BAD=1
            ;;
    esac
done < <(
    git status --porcelain |
    sed 's/^...//'
)

[ "$BAD" -eq 0 ] ||
    fail "Working tree contient d'autres modifications."

grep -q \
    'PINCABOS_BATCH_STAGE_ALL_V33' \
    "$IMPORT" ||
    fail "V3.3 absent."

grep -q \
    'PINCABOS_BATCH_STAGING_GUARD_V35B' \
    "$IMPORT" ||
    fail "Patch partiel V3.5B absent."

ok "Patch partiel V3.5B conserve."

echo
echo "=== 3. BACKUP RECOVERY ==="

mkdir -p "$BACKUP"

git branch "$BACKUP_BRANCH"

git diff > "$BACKUP/working-tree-before.patch"

cp -a \
    "/$IMPORT_REL" \
    "$BACKUP/import-live-before.py"

cp -a \
    "/$DASH_REL" \
    "$BACKUP/dashboard-live-before.py"

ok "Backup : $BACKUP"
ok "Branche : $BACKUP_BRANCH"

echo
echo "==============================================================="
echo " 4. TERMINALISATION DU VIEUX JOB INCOMPLET"
echo "==============================================================="

PYTHONPATH=/opt/pincabos/web \
python3 - "$OLD_JOB" <<'PY'
import sys
import pincabos_batch_import_queue_v2 as queue

job_id = sys.argv[1]

with queue.state_lock(True):

    job = queue.load_job_unlocked(job_id)

    if not job:
        print("INFO [ABSENT] Ancien job déjà disparu.")
        queue.set_active_unlocked(None)
        raise SystemExit(0)

    print("ID              :", job.get("id"))
    print("STATE AVANT     :", job.get("state"))
    print("UPLOADED        :", job.get("uploaded_archives"))
    print("PROCESSED       :", job.get("processed_archives"))
    print("TOTAL           :", job.get("total_archives"))
    print("UPLOAD COMPLETE :", job.get("uploads_complete"))

    if bool(job.get("uploads_complete")):
        raise SystemExit(
            "NOGO: ce job est maintenant complet; "
            "on ne doit pas le purger."
        )

    for item in job.get("uploads") or []:

        if not isinstance(item, dict):
            continue

        state = str(item.get("state") or "")

        if state in {
            "queued",
            "running",
            "uploading",
            "error",
        }:
            item["state"] = "cancelled"
            item["detail"] = (
                "Téléversement incomplet abandonné; "
                "package temporaire supprimé."
            )
            item["path"] = ""

    job["state"] = "stopped"
    job["stop_requested"] = True
    job["pause_requested"] = False
    job["accepting_uploads"] = False
    job["current_item"] = ""
    job["finished_at"] = queue.utc_now()

    job["error"] = (
        "Téléversement incomplet abandonné. "
        "Ce job n'est pas reprenable."
    )

    queue.add_event(
        job,
        "Job de staging incomplet rendu définitivement terminal.",
        "warning",
    )

    queue.refresh_progress(
        job,
        "Arrêté — staging incomplet",
        "",
    )

    queue.cleanup_uploads(job)
    queue.save_job_unlocked(job)

    if queue.active_job_id_unlocked() == job_id:
        queue.set_active_unlocked(None)

    print()
    print("STATE APRES :", job.get("state"))

    for item in job.get("uploads") or []:
        if isinstance(item, dict):
            print(
                "%3s | %-10s | %s"
                % (
                    item.get("index", ""),
                    item.get("state", ""),
                    item.get("name", ""),
                )
            )

print("GO [OK] Ancien job non-reprenable.")
PY

echo
echo "=== 5. VALIDATION DU VRAI POINTEUR ACTIF ==="

PYTHONPATH=/opt/pincabos/web \
python3 <<'PY'
import pincabos_batch_import_queue_v2 as queue

with queue.state_lock(False):
    active = queue.active_job_id_unlocked()

print("active_job_id :", active or "AUCUN")

if active:
    raise SystemExit(
        "NOGO: pointeur actif encore présent."
    )

print("GO [OK] Aucun pointeur actif.")
PY

echo
echo "--- /active HTTP ---"

curl -s \
    --max-time 5 \
    http://127.0.0.1/api/batch-import/live/active |
python3 -m json.tool || true

echo
echo "==============================================================="
echo " 6. FIN DU PATCH DASHBOARD V3.5D"
echo "==============================================================="

python3 - "$DASH" <<'PY'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")

start_marker = '  function render(kind, packet, error = "") {'
end_marker = '  async function refresh(kind) {'

start = text.find(start_marker)

if start < 0:
    raise SystemExit(
        "NOGO PATCH: render(kind, packet...) introuvable"
    )

end = text.find(end_marker, start)

if end < 0:
    raise SystemExit(
        "NOGO PATCH: refresh(kind) introuvable"
    )

new_render = r'''  function render(kind, packet, error = "") {
    /* PINCABOS_DASHBOARD_STAGING_V35D */

    const target = row(kind);
    if (!target) return;

    const job = packet?.job || null;

    const state = String(
      job?.state || ""
    ).toLowerCase();

    const progress = job?.progress || {};

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

    /*
     * Staging = tous les fichiers locaux ne sont pas encore
     * confirmes physiquement sur le cab.
     */
    const staging = Boolean(
      kind === "import"
      && job
      && job.uploads_complete === false
      && totalUploads > 0
      && ![
        "stopped",
        "failed",
        "cancelled",
        "completed",
        "completed_with_warning"
      ].includes(state)
    );

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
        : staging
          ? "Téléversement"
          : label(state);
    }

    if (detail) {

      if (error) {

        detail.textContent = error;

      } else if (!job) {

        detail.textContent = kind === "import"
          ? "Worker prêt · aucun job."
          : "Aucun job en cours.";

      } else if (staging) {

        detail.textContent =
          `Téléversement vers le cab `
          + `${uploaded}/${totalUploads} · `
          + `garde la page Import ouverte jusqu'à `
          + `${totalUploads}/${totalUploads}`;

      } else {

        const count = total(job);
        const completed = done(job);
        const name = currentName(job);

        const skipped = Number(
          progress.skipped
          ?? job.skipped_archives
          ?? job.skipped_tables
          ?? 0
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
      open.textContent = staging
        ? "Voir transfert"
        : working
          ? "Voir tâche"
          : "Ouvrir";
    }

    /*
     * Pendant staging :
     * seul STOP est autorise.
     */
    const canPause =
      !staging
      && ["queued", "running"].includes(state);

    const canResume =
      !staging
      && ["paused", "pausing"].includes(state)
      && (
        kind === "import"
          ? Boolean(packet?.resumable)
          : Boolean(job?.resumable)
      );

    const canSkip =
      !staging
      && state === "paused"
      && Boolean(job?.error)
      && (
        kind === "import"
        || Boolean(job?.skippable)
      );

    /* PINCABOS_BATCH_BUTTON_LABELS_V35D */

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

    if (stop) {

      const canStop =
        staging
        || [
          "uploading",
          "queued",
          "running",
          "pausing",
          "stopping"
        ].includes(state);

      stop.hidden = !canStop;
      stop.disabled = state === "stopping";

      stop.textContent =
        state === "stopping"
          ? "Arrêt…"
          : "Stop";
    }
  }

'''

text = (
    text[:start]
    + new_render
    + text[end:]
)

pattern = re.compile(
    r'#pco-dashboard-batch-controls '
    r'button\[disabled\]\{.*?\}',
    re.S,
)

replacement = '''#pco-dashboard-batch-controls button[disabled]{
  opacity:.28;
  cursor:not-allowed;
  filter:grayscale(1);
  box-shadow:none;
}'''

text, _ = pattern.subn(
    replacement,
    text,
    count=1,
)

path.write_text(
    text,
    encoding="utf-8",
)

print("GO [PATCH] Dashboard V3.5D.")
PY

echo
echo "=== 7. VALIDATION SOURCE ==="

python3 -m py_compile "$IMPORT" ||
    fail "Syntaxe Import."

python3 -m py_compile "$DASH" ||
    fail "Syntaxe Dashboard."

git diff --check ||
    fail "git diff --check."

grep -q \
    'PINCABOS_BATCH_STAGING_GUARD_V35B' \
    "$IMPORT" ||
    fail "Stage Guard Import absent."

grep -q \
    'PINCABOS_DASHBOARD_STAGING_V35D' \
    "$DASH" ||
    fail "Dashboard V3.5D absent."

grep -q \
    'PINCABOS_BATCH_BUTTON_LABELS_V35D' \
    "$DASH" ||
    fail "Boutons V3.5D absents."

ok "Sources V3.5D valides."

echo
echo "=== 8. DIFF ==="

git --no-pager diff --stat

echo
git --no-pager diff \
    -- "$IMPORT_REL" \
       "$DASH_REL" \
    | head -420

echo
echo "=== 9. COMMIT LOCAL ==="

git add \
    "$IMPORT_REL" \
    "$DASH_REL"

git commit \
    -m "fix(batch): guard incomplete staging in service widget"

NEW_HEAD="$(git rev-parse HEAD)"

ok "Commit local : $NEW_HEAD"
echo "GITHUB : AUCUN PUSH"

echo
echo "==============================================================="
echo " 10. DEPLOIEMENT LIVE"
echo "==============================================================="

deploy()
{
    REL="$1"
    SRC="$REPO/$REL"
    DST="/$REL"

    U="$(stat -c %u "$DST")"
    G="$(stat -c %g "$DST")"
    M="$(stat -c %a "$DST")"

    TMP="${DST}.v35d.$$"

    install \
        -o "$U" \
        -g "$G" \
        -m "$M" \
        "$SRC" \
        "$TMP"

    mv -f "$TMP" "$DST"

    echo "GO [DEPLOY] $DST"
}

deploy "$IMPORT_REL"
deploy "$DASH_REL"

echo
echo "=== 11. STAGING == LIVE ==="

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
echo "=== 12. RESTART WEBAPP + WORKER ==="

systemctl restart \
    pincabos-batch-import-worker.service

sleep 2

systemctl restart \
    pincabos-webapp.service

sleep 3

systemctl is-active --quiet \
    pincabos-batch-import-worker.service ||
    fail "Worker inactif."

systemctl is-active --quiet \
    pincabos-webapp.service ||
    fail "WebApp inactive."

ok "Worker + WebApp actifs."

echo
echo "=== 13. VALIDATION HTTP ==="

curl -fsS \
    --max-time 10 \
    http://127.0.0.1/tools/batch-import \
    > /tmp/pco-v35d-import.html

grep -q \
    'PINCABOS_BATCH_STAGING_GUARD_V35B' \
    /tmp/pco-v35d-import.html ||
    fail "Stage Guard Import non servi."

curl -fsS \
    --max-time 10 \
    http://127.0.0.1/ \
    > /tmp/pco-v35d-dashboard.html

grep -q \
    'PINCABOS_DASHBOARD_STAGING_V35D' \
    /tmp/pco-v35d-dashboard.html ||
    fail "Dashboard V3.5D non servi."

ok "Import + Dashboard servis."

echo
echo "=== 14. POINTEUR ACTIF FINAL ==="

PYTHONPATH=/opt/pincabos/web \
python3 <<'PY'
import pincabos_batch_import_queue_v2 as queue

with queue.state_lock(False):
    active = queue.active_job_id_unlocked()

print("active_job_id :", active or "AUCUN")

if active:
    raise SystemExit(
        "NOGO: pointeur actif non vide."
    )

print("GO [OK] Aucun job réellement actif.")
PY

echo
echo "=== 15. GIT FINAL ==="

cd "$REPO"

echo "Branche : $(git branch --show-current)"
echo "HEAD    : $(git rev-parse HEAD)"

git status --short

[ -z "$(git status --porcelain)" ] ||
    fail "Git non propre."

ok "Git propre."

echo
echo "==============================================================="
echo " GO [OK] BATCH IMPORT V3.5D INSTALLE"
echo "==============================================================="
echo
echo "ANCIEN JOB :"
echo "  stopped"
echo "  non-reprenable"
echo "  packages temporaires purges"
echo
echo "PENDANT STAGING :"
echo "  Widget = TELEVERSEMENT N/N"
echo "  Pause     = grisee"
echo "  Reprendre = grise"
echo "  Skip      = grise"
echo "  Stop      = actif"
echo "  Page Import doit rester ouverte"
echo
echo "APRES N/N :"
echo "  uploads_complete=true"
echo "  navigateur peut quitter"
echo "  worker background autonome"
echo "  widget controle le job"
echo
echo "Backup : $BACKUP"
echo "HEAD   : $NEW_HEAD"
echo "GITHUB : PAS ENCORE PUSH"
echo "==============================================================="
