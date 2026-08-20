#!/usr/bin/env bash
set -Eeuo pipefail

clear

echo "==============================================================="
echo " PINCABOS — BATCH IMPORT V3.5C RECOVERY"
echo " REPRISE APRES PATCH PARTIEL V3.5B"
echo " STAGING GUARD + DASHBOARD ROBUSTE"
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
BACKUP="/opt/pincabos/backups/batch-staging-v35c-$STAMP"
BACKUP_BRANCH="backup/pre-batch-staging-v35c-$STAMP"

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

echo "=== 1. RETABLISSEMENT DU WORKER ==="

systemctl start pincabos-batch-import-worker.service

sleep 2

systemctl is-active --quiet \
    pincabos-batch-import-worker.service ||
    fail "Worker Import inactif."

ok "Worker Import actif."

echo
echo "=== 2. VALIDATION GIT ==="

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
    fail "HEAD differente de V3.3."

echo
echo "--- MODIFICATIONS ACTUELLES ---"
git status --short

echo
echo "=== 3. VALIDATION DES MODIFICATIONS PARTIELLES ==="

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
    fail "Fichiers Git inattendus modifies."

grep -q \
    'PINCABOS_BATCH_STAGE_ALL_V33' \
    "$IMPORT" ||
    fail "V3.3 absent."

grep -q \
    'PINCABOS_BATCH_STAGING_GUARD_V35B' \
    "$IMPORT" &&
    echo "GO [OK] Stage Guard V3.5B deja present dans staging." ||
    echo "INFO [ABSENT] Stage Guard sera ajoute."

ok "Working tree recuperable."

echo
echo "=== 4. VALIDATION AUCUN JOB IMPORT ACTIF ==="

curl -fsS \
    --max-time 10 \
    http://127.0.0.1/api/batch-import/live/active \
    > /tmp/pco-v35c-active.json

python3 - /tmp/pco-v35c-active.json <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as fh:
    d = json.load(fh)

j = d.get("job")

if j:
    print("ID              :", j.get("id"))
    print("STATE           :", j.get("state"))
    print("UPLOADED        :", j.get("uploaded_archives"))
    print("PROCESSED       :", j.get("processed_archives"))
    print("TOTAL           :", j.get("total_archives"))
    print("UPLOAD COMPLETE :", j.get("uploads_complete"))
    raise SystemExit(
        "NOGO: un job Import est encore actif."
    )

print("GO [OK] Aucun job Import actif.")
PY

echo
echo "=== 5. BACKUP DE RECOVERY ==="

mkdir -p "$BACKUP"

git branch "$BACKUP_BRANCH"

cp -a \
    "/$IMPORT_REL" \
    "$BACKUP/pincabos_batch_import_live.py.live-before"

cp -a \
    "/$DASH_REL" \
    "$BACKUP/pincabos_dashboard_lobby.py.live-before"

git diff > "$BACKUP/working-tree-before.patch"

ok "Backup : $BACKUP"
ok "Branche : $BACKUP_BRANCH"

echo
echo "==============================================================="
echo " 6. PATCH ROBUSTE IMPORT + DASHBOARD"
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
# IMPORT : ajoute le Stage Guard uniquement s'il manque.
# ============================================================

text = import_path.read_text(encoding="utf-8")

if "PINCABOS_BATCH_STAGING_GUARD_V35B" not in text:

    anchor = '''  async function submitQueue(target) {
    /* PINCABOS_BATCH_STAGE_ALL_V33 */
'''

    replacement = '''  /*
   * PINCABOS_BATCH_STAGING_GUARD_V35B
   *
   * Les fichiers locaux n'existent que dans cette page.
   * Avant N/N, navigation/reload/fermeture doit avertir.
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
        die("jobId introuvable")

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

    print("GO [PATCH] Import Stage Guard")
else:
    print("GO [DEJA] Import Stage Guard")


# ============================================================
# DASHBOARD
#
# On remplace LA FONCTION render() COMPLETE.
# Plus de dépendance à une petite ancre fragile.
# ============================================================

text = dash_path.read_text(encoding="utf-8")

start_marker = '''  function render(kind, packet, error = "") {'''
end_marker = '''  async function refresh(kind) {'''

start = text.find(start_marker)

if start < 0:
    die("Début function render() introuvable")

end = text.find(end_marker, start)

if end < 0:
    die("Fin function render() introuvable")

new_render = r'''  function render(kind, packet, error = "") {
    /* PINCABOS_DASHBOARD_STAGING_V35C */

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
     * STAGING =
     * les fichiers locaux ne sont pas encore tous confirmes
     * physiquement sur le cab.
     */
    const staging = Boolean(
      kind === "import"
      && job
      && job.uploads_complete === false
      && totalUploads > 0
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

    /*
     * ETAT
     */
    if (status) {
      status.textContent = error
        ? "API indisponible"
        : staging
          ? "Téléversement"
          : label(state);
    }

    /*
     * DETAIL
     */
    if (detail) {

      if (error) {

        detail.textContent = error;

      } else if (!job) {

        detail.textContent = kind === "import"
          ? "Worker prêt · aucun job."
          : "Aucun job en cours.";

      } else if (staging) {

        if (uploaded < totalUploads) {

          detail.textContent =
            `Téléversement vers le cab `
            + `${uploaded}/${totalUploads} · `
            + `garde la page Import ouverte jusqu'à `
            + `${totalUploads}/${totalUploads}`;

        } else {

          detail.textContent =
            `${uploaded}/${totalUploads} téléversés · `
            + `finalisation de la file…`;
        }

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

    /*
     * OUVRIR
     */
    if (open) {
      open.textContent = staging
        ? "Voir transfert"
        : working
          ? "Voir tâche"
          : "Ouvrir";
    }

    /*
     * COMMANDES
     *
     * Pendant STAGING :
     * - Pause     = interdit
     * - Reprendre = interdit
     * - Skip      = interdit
     * - Stop      = autorise
     *
     * Apres uploads_complete :
     * le widget pilote entierement le worker.
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

    /*
     * PINCABOS_BATCH_BUTTON_LABELS_V35C
     */
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

      const canStop = staging || [
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


# ============================================================
# CSS : boutons réellement gris lorsqu'ils sont désactivés.
# ============================================================

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

text, count = pattern.subn(
    replacement,
    text,
    count=1,
)

if count == 0:
    print(
        "INFO [CSS] bloc disabled non trouve; "
        "fonctionnel quand meme."
    )
else:
    print(
        "GO [PATCH] CSS boutons disabled"
    )

dash_path.write_text(
    text,
    encoding="utf-8",
)

print(
    "GO [PATCH] Dashboard render V3.5C"
)
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
    fail "Stage Guard absent."

grep -q \
    'PINCABOS_DASHBOARD_STAGING_V35C' \
    "$DASH" ||
    fail "Dashboard V3.5C absent."

grep -q \
    'PINCABOS_BATCH_BUTTON_LABELS_V35C' \
    "$DASH" ||
    fail "Labels V3.5C absents."

ok "Source valide."

echo
echo "=== 8. DIFF FINAL ==="

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
    -m "fix(batch): guard upload staging and clarify dashboard"

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

    DST_UID="$(stat -c %u "$DST")"
    DST_GID="$(stat -c %g "$DST")"
    DST_MODE="$(stat -c %a "$DST")"

    TMP="${DST}.v35c.$$"

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
echo "=== 12. RESTART SERVICES ==="

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
echo "=== 13. VALIDATION HTTP ==="

curl -fsS \
    --max-time 10 \
    http://127.0.0.1/tools/batch-import \
    > /tmp/pco-v35c-import.html

grep -q \
    'PINCABOS_BATCH_STAGING_GUARD_V35B' \
    /tmp/pco-v35c-import.html ||
    fail "Stage Guard non servi."

curl -fsS \
    --max-time 10 \
    http://127.0.0.1/ \
    > /tmp/pco-v35c-dashboard.html

grep -q \
    'PINCABOS_DASHBOARD_STAGING_V35C' \
    /tmp/pco-v35c-dashboard.html ||
    fail "Dashboard V3.5C non servi."

ok "Import + Dashboard V3.5C servis."

echo
echo "=== 14. ETAT API ==="

curl -s \
    --max-time 5 \
    http://127.0.0.1/api/batch-import/live/active |
python3 -m json.tool

echo
echo "=== 15. ETAT GIT FINAL ==="

cd "$REPO"

echo "Branche : $(git branch --show-current)"
echo "HEAD    : $(git rev-parse HEAD)"

git status --short

[ -z "$(git status --porcelain)" ] ||
    fail "Git non propre."

ok "Git propre."

echo
echo "==============================================================="
echo " GO [OK] BATCH IMPORT V3.5C INSTALLE"
echo "==============================================================="
echo
echo "PENDANT TELEVERSEMENT :"
echo "  Titre       : TELEVERSEMENT"
echo "  Detail      : uploaded/total"
echo "  Page Import : doit rester ouverte"
echo "  Pause       : grisee"
echo "  Reprendre   : grise"
echo "  Skip        : grise"
echo "  Stop        : actif"
echo
echo "APRES N/N :"
echo "  uploads_complete=true"
echo "  page peut etre fermee"
echo "  worker background autonome"
echo "  widget reprend le controle"
echo
echo "Backup : $BACKUP"
echo "HEAD   : $NEW_HEAD"
echo "GITHUB : PAS ENCORE PUSH"
echo "==============================================================="
