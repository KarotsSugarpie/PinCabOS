#!/usr/bin/env bash
set -Eeuo pipefail

clear

echo "==============================================================="
echo " PINCABOS — PUBLICATION GITHUB COMPLETE"
echo " ECRASE MAIN AVEC PINCABOS-PR-INTEGRATION"
echo " BACKUP REMOTE AVANT FORCE PUSH"
echo "==============================================================="
echo

REPO="/opt/pincabos/tmp/pr-integration"
EXPECTED_BRANCH="pincabos-pr-integration"
EXPECTED_HEAD="0f1a4a3c35a798aac12c7e8c2e77f290cffe09aa"
EXPECTED_REPO="KarotsSugarpie/PinCabOS"

STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_BRANCH="backup-main-before-full-overwrite-$STAMP"
BACKUP_DIR="/opt/pincabos/backups/github-main-overwrite-$STAMP"

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

[ "$(id -u)" -eq 0 ] ||
    fail "Execution root requise."

[ -d "$REPO/.git" ] ||
    fail "Repo staging absent."

cd "$REPO"

echo "=== 1. VALIDATION LOCALE ==="

BRANCH="$(git branch --show-current)"
HEAD="$(git rev-parse HEAD)"

echo "Branche : $BRANCH"
echo "HEAD    : $HEAD"

[ "$BRANCH" = "$EXPECTED_BRANCH" ] ||
    fail "Mauvaise branche."

[ "$HEAD" = "$EXPECTED_HEAD" ] ||
    fail "HEAD inattendu. Aucun push effectue."

[ -z "$(git status --porcelain)" ] ||
    fail "Git local non propre."

ok "Staging local valide et propre."

echo
echo "=== 2. VALIDATION REMOTE ==="

git remote -v

ORIGIN_URL="$(git remote get-url origin)"

echo
echo "Origin : $ORIGIN_URL"

case "$ORIGIN_URL" in
    *KarotsSugarpie/PinCabOS.git|*KarotsSugarpie/PinCabOS)
        ;;
    *)
        fail "Origin ne pointe pas vers $EXPECTED_REPO."
        ;;
esac

ok "Depot GitHub correct."

echo
echo "=== 3. FETCH GITHUB ==="

git fetch --prune origin

REMOTE_MAIN="$(
    git rev-parse refs/remotes/origin/main
)"

echo "GitHub main : $REMOTE_MAIN"
echo "Local HEAD  : $HEAD"

ok "Etat GitHub recupere."

echo
echo "=== 4. BACKUP LOCAL COMPLET ==="

mkdir -p "$BACKUP_DIR"

git bundle create \
    "$BACKUP_DIR/before-main-overwrite.bundle" \
    --all

git log \
    --oneline \
    --decorate \
    -40 \
    > "$BACKUP_DIR/local-history.txt"

git log \
    --oneline \
    -40 \
    origin/main \
    > "$BACKUP_DIR/github-main-before.txt"

printf '%s\n' "$REMOTE_MAIN" \
    > "$BACKUP_DIR/github-main-before.sha"

printf '%s\n' "$HEAD" \
    > "$BACKUP_DIR/local-head.sha"

ok "Bundle : $BACKUP_DIR/before-main-overwrite.bundle"

echo
echo "=== 5. BACKUP DU MAIN SUR GITHUB ==="

echo "Creation : origin/$BACKUP_BRANCH"

git push \
    origin \
    "$REMOTE_MAIN:refs/heads/$BACKUP_BRANCH"

ok "Backup GitHub cree : $BACKUP_BRANCH"

echo
echo "=== 6. FORCE PUSH CONTROLE VERS MAIN ==="

echo
echo "ATTENTION :"
echo "  GitHub main AVANT : $REMOTE_MAIN"
echo "  GitHub main APRES : $HEAD"
echo

git push \
    --force-with-lease="refs/heads/main:$REMOTE_MAIN" \
    origin \
    HEAD:refs/heads/main

ok "MAIN GitHub remplace."

echo
echo "=== 7. VERIFICATION REMOTE ==="

git fetch origin main

REMOTE_AFTER="$(
    git rev-parse refs/remotes/origin/main
)"

echo "Local       : $HEAD"
echo "GitHub main : $REMOTE_AFTER"

[ "$REMOTE_AFTER" = "$HEAD" ] ||
    fail "GitHub main ne correspond pas au HEAD local."

ok "GitHub main == staging local."

echo
echo "=== 8. VALIDATION FICHIERS V3.5D ==="

git show \
    origin/main:opt/pincabos/web/pincabos_batch_import_live.py \
    | grep -q 'PINCABOS_BATCH_STAGING_GUARD_V35B' ||
    fail "Stage Guard absent de GitHub."

git show \
    origin/main:opt/pincabos/web/pincabos_dashboard_lobby.py \
    | grep -q 'PINCABOS_DASHBOARD_STAGING_V35D' ||
    fail "Dashboard V3.5D absent de GitHub."

git show \
    origin/main:opt/pincabos/web/pincabos_dashboard_lobby.py \
    | grep -q 'PINCABOS_BATCH_BUTTON_LABELS_V35D' ||
    fail "Boutons V3.5D absents de GitHub."

ok "V3.5D confirme sur GitHub."

echo
echo "==============================================================="
echo " GO [OK] GITHUB MAIN MIS A JOUR"
echo "==============================================================="
echo
echo "Depot        : $EXPECTED_REPO"
echo "Main avant   : $REMOTE_MAIN"
echo "Main apres   : $REMOTE_AFTER"
echo
echo "Backup GitHub:"
echo "  $BACKUP_BRANCH"
echo
echo "Backup local :"
echo "  $BACKUP_DIR"
echo
echo "SOURCE OFFICIELLE MAINTENANT :"
echo "  pincabos-pr-integration -> GitHub main"
echo "==============================================================="
