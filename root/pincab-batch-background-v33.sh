#!/usr/bin/env bash
set -Eeuo pipefail

clear

echo "==============================================================="
echo " PINCABOS — BATCH IMPORT BACKGROUND V3.3"
echo " STAGE ALL -> WORKER BACKGROUND"
echo " CONTROLE COMPLET PAR LE WIDGET SERVICES"
echo " AUCUN PUSH GITHUB"
echo "==============================================================="
echo

REPO="/opt/pincabos/tmp/pr-integration"

LIVE_REL="opt/pincabos/web/pincabos_batch_import_live.py"
WORKER_REL="opt/pincabos/web/pincabos_batch_import_worker_v2.py"

LIVE="$REPO/$LIVE_REL"
WORKER="$REPO/$WORKER_REL"

STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="/opt/pincabos/backups/batch-background-v33-$STAMP"
BACKUP_BRANCH="backup/pre-batch-background-v33-$STAMP"

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

echo "=== 1. VALIDATION ==="

[ "$(id -u)" -eq 0 ] ||
    fail "Execute avec sudo -i."

[ -d "$REPO/.git" ] ||
    fail "Repo absent."

cd "$REPO"

echo "Branche : $(git branch --show-current)"
echo "HEAD    : $(git rev-parse HEAD)"

[ "$(git branch --show-current)" = "pincabos-pr-integration" ] ||
    fail "Mauvaise branche."

[ -z "$(git status --porcelain)" ] ||
    fail "Git non propre."

grep -q \
    'PINCABOS_BATCH_CONTROLS_V3' \
    "$WORKER" ||
    fail "Backend Batch V3 absent."

grep -q \
    'PINCABOS_BATCH_IMPORT_UPLOAD_PAUSED_V31' \
    "$LIVE" ||
    fail "Fix V3.1 absent."

ok "Base Batch V3 detectee."

echo
echo "=== 2. AUCUN JOB IMPORT ACTIF ==="

ACTIVE="$(
curl -s \
    --max-time 5 \
    http://127.0.0.1/api/batch-import/live/active |
python3 -c '
import json,sys
try:
    d=json.load(sys.stdin)
    print(((d.get("job") or {}).get("id")) or "")
except Exception:
    print("API_ERROR")
'
)"

[ "$ACTIVE" != "API_ERROR" ] ||
    fail "API Import indisponible."

[ -z "$ACTIVE" ] ||
    fail "Job encore actif : $ACTIVE"

ok "Aucun Batch Import actif."

echo
echo "=== 3. STAGING == LIVE ==="

for REL in "$LIVE_REL" "$WORKER_REL"
do
    S="$(sha256sum "$REPO/$REL" | awk '{print $1}')"
    L="$(sha256sum "/$REL" | awk '{print $1}')"

    echo "$REL"
    echo "  staging : $S"
    echo "  live    : $L"

    [ "$S" = "$L" ] ||
        fail "Staging/LIVE different : $REL"
done

ok "Source et LIVE synchronises."

echo
echo "=== 4. BACKUP ==="

mkdir -p "$BACKUP"

git branch "$BACKUP_BRANCH"

cp -a \
    "/$LIVE_REL" \
    "$BACKUP/pincabos_batch_import_live.py.before"

cp -a \
    "/$WORKER_REL" \
    "$BACKUP/pincabos_batch_import_worker_v2.py.before"

git bundle create \
    "$BACKUP/staging-before.bundle" \
    --all

ok "Backup : $BACKUP"
ok "Branche : $BACKUP_BRANCH"

echo
echo "==============================================================="
echo " 5. PATCH V3.3"
echo "==============================================================="

python3 - \
    "$LIVE" \
    "$WORKER" <<'PY'
from pathlib import Path
import re
import sys

live_path = Path(sys.argv[1])
worker_path = Path(sys.argv[2])


def die(message):
    raise SystemExit("NOGO PATCH: " + message)


# ============================================================
# PAGE IMPORT
#
# AVANT:
#   upload fichier 1
#   attendre IMPORT fichier 1
#   upload fichier 2
#   attendre IMPORT fichier 2
#
# APRES:
#   upload TOUS les fichiers
#   finish
#   worker systemd traite ensuite indépendamment du navigateur
# ============================================================

text = live_path.read_text(encoding="utf-8")

marker = "PINCABOS_BATCH_STAGE_ALL_V33"

if marker not in text:

    pattern = re.compile(
        r'  async function submitQueue\(target\) \{.*?'
        r'\n  \}\n\n'
        r'  function wire\(\) \{',
        re.S,
    )

    match = pattern.search(text)

    if not match:
        die("submitQueue() introuvable")

    replacement = r'''  async function submitQueue(target) {
    /* PINCABOS_BATCH_STAGE_ALL_V33 */

    const input = target.querySelector(
      'input[name="archives"]'
    );

    const files = Array.from(
      input?.files || []
    );

    if (!files.length) {
      throw new Error(
        "Choisis au moins un package .PinCabOS."
      );
    }

    const conflict = (
      target.querySelector(
        'input[name="conflict_mode"]:checked'
      )?.value
      || "skip"
    );

    disable(target, true);

    setMessage(
      `Préparation de ${files.length} package(s). `
      + `Ne quitte pas cette page avant `
      + `${files.length}/${files.length} téléversés.`
    );

    const created = await json(
      "/api/batch-import/live/create",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json"
        },
        body: JSON.stringify({
          total: files.length,
          conflict_mode: conflict
        })
      }
    );

    const jobId = created.job.id;

    emit(
      "pcos-batch-import-started",
      created.job
    );

    try {

      /*
       * Important:
       * on STAGE tous les fichiers sur le cab AVANT de
       * dépendre du worker.
       *
       * Aucune attente de processed_archives ici.
       */
      for (
        let index = 0;
        index < files.length;
        index += 1
      ) {

        const file = files[index];

        setMessage(
          `Téléversement ${index + 1}/${files.length} : `
          + `${file.name} · `
          + `garde cette page ouverte`
        );

        emit(
          "pcos-batch-import-uploading",
          {
            job_id: jobId,
            index: index + 1,
            total: files.length,
            name: file.name
          }
        );

        const body = new FormData();

        body.append(
          "archive",
          file,
          file.name
        );

        body.append(
          "index",
          String(index + 1)
        );

        await json(
          `/api/batch-import/live/upload/`
          + encodeURIComponent(jobId),
          {
            method: "POST",
            body
          }
        );

        setMessage(
          `Téléversement ${index + 1}/${files.length} terminé. `
          + (
            index + 1 === files.length
              ? "Préparation du traitement en arrière-plan…"
              : "Envoi du package suivant…"
          )
        );
      }

      /*
       * Tous les fichiers sont maintenant physiquement
       * stockés sur le cab.
       */
      const finished = await json(
        `/api/batch-import/live/finish/`
        + encodeURIComponent(jobId),
        {
          method: "POST"
        }
      );

      setMessage(
        `${files.length}/${files.length} packages téléversés. `
        + `Import en arrière-plan actif. `
        + `Tu peux maintenant quitter cette page et contrôler `
        + `le Batch depuis le widget Services.`
      );

      emit(
        "pcos-batch-import-started",
        finished.job
      );

    } catch (error) {

      /*
       * Une erreur de TRANSMISSION est différente d'une
       * erreur d'import.
       *
       * On arrête la file incomplète : les fichiers locaux
       * non envoyés ne sont pas récupérables par le serveur.
       */
      try {
        await json(
          `/api/batch-import/live/stop/`
          + encodeURIComponent(jobId),
          {
            method: "POST"
          }
        );
      } catch (_) {}

      emit(
        "pcos-batch-import-upload-failed",
        {
          job_id: jobId,
          error: error.message
        }
      );

      throw error;

    } finally {
      disable(target, false);
    }
  }

  function wire() {'''

    text = (
        text[:match.start()]
        + replacement
        + text[match.end():]
    )

    live_path.write_text(
        text,
        encoding="utf-8",
    )

    print(
        "GO [PATCH] Upload-all puis background"
    )
else:
    print(
        "GO [DEJA] Stage-all V3.3"
    )


# ============================================================
# WORKER
#
# Ne doit PAS commencer l'import tant que le navigateur
# n'a pas terminé le staging complet.
# ============================================================

text = worker_path.read_text(encoding="utf-8")

marker = "PINCABOS_BATCH_WAIT_FULL_STAGE_V33"

if marker not in text:

    old = '''def process_job(job_id: str) -> None:
    job = mark_running(job_id)
    if not job:
        return

    conflict_mode = str(job.get("conflict_mode", "skip") or "skip")
'''

    new = '''def process_job(job_id: str) -> None:
    # PINCABOS_BATCH_WAIT_FULL_STAGE_V33
    #
    # Le navigateur commence par déposer TOUS les packages.
    # Le worker ne démarre aucun import avant uploads_complete.
    #
    # Une fois ce drapeau positionné, le navigateur n'est plus
    # nécessaire et le Batch peut vivre entièrement en arrière-plan.
    staging = queue.load_job(job_id)

    if not staging:
        return

    if not bool(staging.get("uploads_complete")):
        uploaded = int(
            staging.get("uploaded_archives", 0) or 0
        )

        total = int(
            staging.get("total_archives", 0) or 0
        )

        def waiting_for_stage(job: dict[str, Any]) -> None:
            queue.refresh_progress(
                job,
                f"Téléversement vers le cab "
                f"{uploaded}/{total}",
                str(job.get("current_item", "") or ""),
            )

        queue.update_job(
            job_id,
            waiting_for_stage,
        )

        heartbeat(
            "waiting-upload",
            job_id,
            f"{uploaded}/{total}",
        )

        return

    job = mark_running(job_id)

    if not job:
        return

    conflict_mode = str(
        job.get("conflict_mode", "skip")
        or "skip"
    )
'''

    count = text.count(old)

    if count != 1:
        die(
            "Début process_job attendu 1 fois, trouve "
            + str(count)
        )

    text = text.replace(
        old,
        new,
        1,
    )

    worker_path.write_text(
        text,
        encoding="utf-8",
    )

    print(
        "GO [PATCH] Worker attend staging complet"
    )
else:
    print(
        "GO [DEJA] Worker V3.3"
    )
PY

echo
echo "=== 6. VALIDATION PYTHON ==="

python3 -m py_compile "$LIVE" ||
    fail "Syntaxe Import Live."

python3 -m py_compile "$WORKER" ||
    fail "Syntaxe Worker."

git diff --check ||
    fail "git diff --check."

grep -q \
    'PINCABOS_BATCH_STAGE_ALL_V33' \
    "$LIVE" ||
    fail "Marqueur Stage All absent."

grep -q \
    'PINCABOS_BATCH_WAIT_FULL_STAGE_V33' \
    "$WORKER" ||
    fail "Marqueur Worker absent."

ok "Source V3.3 valide."

echo
echo "=== 7. DIFF ==="

git --no-pager diff --stat

echo
git --no-pager diff \
    -- "$LIVE_REL" \
       "$WORKER_REL" \
    | head -320

echo
echo "=== 8. COMMIT LOCAL ==="

git add \
    "$LIVE_REL" \
    "$WORKER_REL"

git commit \
    -m "fix(batch): stage all imports before background processing"

NEW_HEAD="$(git rev-parse HEAD)"

ok "Commit local : $NEW_HEAD"
echo "GITHUB : AUCUN PUSH"

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

    TMP="${DST}.v33.$$"

    install \
        -o "$DST_UID" \
        -g "$DST_GID" \
        -m "$DST_MODE" \
        "$SRC" \
        "$TMP"

    mv -f "$TMP" "$DST"

    echo "GO [DEPLOY] $DST"
}

deploy "$LIVE_REL"
deploy "$WORKER_REL"

echo
echo "=== 10. STAGING == LIVE ==="

for REL in \
    "$LIVE_REL" \
    "$WORKER_REL"
do
    S="$(sha256sum "$REPO/$REL" | awk '{print $1}')"
    L="$(sha256sum "/$REL" | awk '{print $1}')"

    [ "$S" = "$L" ] ||
        fail "Mismatch : $REL"

    echo "GO [OK] $REL"
done

echo
echo "=== 11. RESTART SERVICES ==="

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
echo "=== 12. VALIDATION HTTP ==="

curl -fsS \
    --max-time 10 \
    http://127.0.0.1/tools/batch-import \
    > /tmp/pincab-v33-import.html

grep -q \
    'PINCABOS_BATCH_STAGE_ALL_V33' \
    /tmp/pincab-v33-import.html ||
    fail "V3.3 non servi dans la page Import."

ok "Page Import V3.3 servie."

echo
echo "=== 13. ETAT FINAL ==="

printf "%-45s : " \
    "pincabos-webapp.service"

systemctl is-active \
    pincabos-webapp.service || true

printf "%-45s : " \
    "pincabos-batch-import-worker.service"

systemctl is-active \
    pincabos-batch-import-worker.service || true

echo
echo "Branche : $(git branch --show-current)"
echo "HEAD    : $(git rev-parse HEAD)"

[ -z "$(git status --porcelain)" ] ||
    fail "Git non propre."

ok "Git propre."

echo
echo "==============================================================="
echo " GO [OK] BACKGROUND IMPORT V3.3 INSTALLE"
echo "==============================================================="
echo
echo "NOUVEAU PIPELINE :"
echo
echo "  Browser :"
echo "    Upload 1/N"
echo "    Upload 2/N"
echo "    ..."
echo "    Upload N/N"
echo
echo "  PUIS :"
echo "    uploads_complete = true"
echo
echo "  Worker systemd :"
echo "    Table 1"
echo "    Table 2"
echo "    Table 3"
echo "    ..."
echo
echo "  Le navigateur peut etre ferme."
echo
echo "  Widget Services :"
echo "    Pause"
echo "    Reprendre"
echo "    Skip"
echo "    Stop"
echo "    Actualiser"
echo
echo "Backup : $BACKUP"
echo "HEAD   : $NEW_HEAD"
echo
echo "GITHUB : PAS ENCORE PUSH"
echo "==============================================================="
