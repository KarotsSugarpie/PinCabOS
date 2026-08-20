#!/usr/bin/env bash
set -Eeuo pipefail

clear

echo "==============================================================="
echo " PINCABOS — IMPORT PR #27 + #28"
echo " NETTOYAGE DEPOT UNIQUEMENT"
echo " AUCUNE SUPPRESSION SUR LE CAB LIVE"
echo "==============================================================="
echo

REPO="/opt/pincabos/tmp/pr-integration"
MAIN_BRANCH="pincabos-pr-integration"

BASE_HEAD="8bc3e103bc9b0d125f1844bf62cf26fca99eae9d"

PR27_HEAD="de57fe14301aab41b1412653fba8210b837cd0d9"
PR28_HEAD="4b2015b6109ea1d0e37072324075bb0e4354f8c4"

STAMP="$(date +%Y%m%d-%H%M%S)"

WORK_BRANCH="integration/pr27-28-$STAMP"
BACKUP_LOCAL="backup/pre-pr27-28-$STAMP"
BACKUP_REMOTE="backup-main-before-pr27-28-$STAMP"

BACKUP_DIR="/opt/pincabos/backups/pr27-28-$STAMP"

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
    fail "Root requis."

[ -d "$REPO/.git" ] ||
    fail "Repo absent."

cd "$REPO"

echo "=== 1. VALIDATION LOCALE ==="

BRANCH="$(git branch --show-current)"
HEAD="$(git rev-parse HEAD)"

echo "Branche : $BRANCH"
echo "HEAD    : $HEAD"

[ "$BRANCH" = "$MAIN_BRANCH" ] ||
    fail "Mauvaise branche."

[ "$HEAD" = "$BASE_HEAD" ] ||
    fail "HEAD local inattendu."

[ -z "$(git status --porcelain)" ] ||
    fail "Git local non propre."

ok "Base locale valide."

echo
echo "=== 2. VALIDATION GITHUB ==="

gh auth status >/dev/null 2>&1 ||
    fail "GitHub CLI non authentifie."

git fetch --prune origin

REMOTE_MAIN="$(git rev-parse refs/remotes/origin/main)"

echo "Local       : $HEAD"
echo "GitHub main : $REMOTE_MAIN"

[ "$REMOTE_MAIN" = "$BASE_HEAD" ] ||
    fail "GitHub main a change."

ok "GitHub == local."

echo
echo "=== 3. BACKUPS AVANT IMPORT ==="

mkdir -p "$BACKUP_DIR"

git branch \
    "$BACKUP_LOCAL" \
    "$BASE_HEAD"

git bundle create \
    "$BACKUP_DIR/before-pr27-28.bundle" \
    --all

git push \
    origin \
    "$BASE_HEAD:refs/heads/$BACKUP_REMOTE"

ok "Backup local  : $BACKUP_LOCAL"
ok "Backup GitHub : $BACKUP_REMOTE"
ok "Bundle        : $BACKUP_DIR/before-pr27-28.bundle"

echo
echo "=== 4. FETCH PR #27 ==="

git fetch \
    origin \
    "+refs/pull/27/head:refs/remotes/origin/pr/27"

ACTUAL27="$(git rev-parse refs/remotes/origin/pr/27)"

echo "Attendu : $PR27_HEAD"
echo "Recu    : $ACTUAL27"

[ "$ACTUAL27" = "$PR27_HEAD" ] ||
    fail "PR #27 a change."

git log -1 --oneline refs/remotes/origin/pr/27

ok "PR #27 valide."

echo
echo "=== 5. FETCH PR #28 ==="

git fetch \
    origin \
    "+refs/pull/28/head:refs/remotes/origin/pr/28"

ACTUAL28="$(git rev-parse refs/remotes/origin/pr/28)"

echo "Attendu : $PR28_HEAD"
echo "Recu    : $ACTUAL28"

[ "$ACTUAL28" = "$PR28_HEAD" ] ||
    fail "PR #28 a change."

git log -1 --oneline refs/remotes/origin/pr/28

ok "PR #28 valide."

echo
echo "==============================================================="
echo " 6. BRANCHE TEMPORAIRE"
echo "==============================================================="

git switch \
    -c "$WORK_BRANCH" \
    "$BASE_HEAD"

ok "$WORK_BRANCH"

echo
echo "==============================================================="
echo " 7. MERGE PR #27"
echo "==============================================================="

if ! git merge \
    --no-ff \
    -m "merge(pr): import PR #27" \
    refs/remotes/origin/pr/27
then
    echo
    git status --short

    git merge --abort || true

    fail "Conflit PR #27. Main intact."
fi

HEAD27="$(git rev-parse HEAD)"

ok "PR #27 fusionnee : $HEAD27"

echo
echo "==============================================================="
echo " 8. MERGE PR #28"
echo "==============================================================="

if ! git merge \
    --no-ff \
    -m "merge(pr): import PR #28" \
    refs/remotes/origin/pr/28
then
    echo
    echo "Conflits detectes :"
    git status --short
    echo

    #
    # Les deux PR partent du meme main et ajoutent des regles
    # a la fin de .gitignore. Si le SEUL conflit est .gitignore,
    # on conserve le resultat PR27 puis ajoute la regle PR28.
    #

    mapfile -t CONFLICTS < <(
        git diff \
            --name-only \
            --diff-filter=U
    )

    if [ "${#CONFLICTS[@]}" -ne 1 ] ||
       [ "${CONFLICTS[0]}" != ".gitignore" ]
    then
        git merge --abort || true

        fail "Conflit autre que .gitignore. Aucun push."
    fi

    echo "GO [INFO] Conflit limite a .gitignore."
    echo "Resolution controlee PR27 + PR28."

    git checkout --ours .gitignore

    if ! grep -Fxq '/var/crash/' .gitignore
    then
        cat >> .gitignore <<'EOF'

# ------------------------------------------------------------
# Vidages de plantage : residus propres a la machine qui les a
# ecrits, deja exclus de l'ISO par iso.sh.
# ------------------------------------------------------------
/var/crash/
EOF
    fi

    git add .gitignore

    #
    # Les suppressions de PR28 doivent aussi etre conservees.
    #

    git rm -f --ignore-unmatch \
        var/crash/_opt_google_chrome_chrome.1000.crash \
        var/crash/_opt_pincabos_bin_pincabos-fulldmd-extract-frame.py.0.crash \
        var/crash/_opt_pincabos_bin_pincabos-fulldmd-extract-frame.py.1000.crash \
        var/crash/_opt_pincabos_bin_pincabos-native-b2s-scoreview-prelaunch.sh.1000.crash \
        var/crash/_opt_pincabos_launchers_pincabos-hybrid-chooser.py.1000.crash \
        var/crash/_opt_pincabos_tools_pincabos-smart-archive-import.py.1000.crash \
        var/crash/_usr_lib_cargo_bin_sudo.0.crash \
        var/crash/kdump_lock

    if git diff --name-only --diff-filter=U | grep -q .
    then
        git status --short
        fail "Conflit non resolu."
    fi

    git commit \
        -m "merge(pr): import PR #28"

    ok "Conflit .gitignore resolu proprement."
fi

FINAL_WORK_HEAD="$(git rev-parse HEAD)"

ok "PR #28 fusionnee : $FINAL_WORK_HEAD"

echo
echo "==============================================================="
echo " 9. AUDIT DU RESULTAT"
echo "==============================================================="

git --no-pager diff \
    --stat \
    "$BASE_HEAD..$FINAL_WORK_HEAD"

echo
echo "=== FICHIERS MODIFIES ==="

git diff \
    --name-status \
    "$BASE_HEAD..$FINAL_WORK_HEAD" \
    | tee "$BACKUP_DIR/name-status.txt"

echo
echo "=== 10. GARDE-FOU : AUCUN CODE LIVE MODIFIE ==="

BAD="$(
    git diff \
        --name-status \
        "$BASE_HEAD..$FINAL_WORK_HEAD" |
    awk '
        $1 != "D" && $2 != ".gitignore" {
            print
        }
    '
)"

if [ -n "$BAD" ]
then
    echo "$BAD"

    fail "Une PR modifie autre chose que .gitignore ou des suppressions."
fi

ok "Seulement .gitignore + suppressions de residus."

echo
echo "=== 11. VALIDATION .gitignore ==="

for PATTERN in \
    '**/*.bak' \
    '**/*.bak.*' \
    '**/*.bak-*' \
    '**/*.before-*' \
    '**/*.orig' \
    '**/*.old' \
    '/opt/pincabos/web/backups/' \
    '/home/pinball/.local/share/pincabos/editor-backups/' \
    '/etc/lvm/backup/' \
    '/etc/lvm/archive/' \
    '/var/crash/'
do
    grep -Fxq "$PATTERN" .gitignore ||
        fail "Regle absente : $PATTERN"

    echo "GO [OK] $PATTERN"
done

echo
echo "=== 12. VALIDATION CRASH DUMPS NON VERSIONNES ==="

if git ls-files 'var/crash/*' | grep -q .
then
    echo "Encore presents :"
    git ls-files 'var/crash/*'

    fail "Crash dumps encore versionnes."
fi

ok "Aucun var/crash versionne."

echo
echo "=== 13. VALIDATION BACKUPS NON VERSIONNES ==="

RESIDUE="$(
    git ls-files |
    grep -E \
        '(\.bak($|[.-])|\.before-|\.orig$|\.old$|^etc/lvm/(backup|archive)/|^opt/pincabos/web/backups/)' \
    || true
)"

if [ -n "$RESIDUE" ]
then
    echo "$RESIDUE"

    fail "Residus backup encore versionnes."
fi

ok "Residus PR #27 retires."

echo
echo "=== 14. GIT DIFF CHECK ==="

git diff \
    --check \
    "$BASE_HEAD..$FINAL_WORK_HEAD" ||
    fail "git diff --check."

ok "Diff propre."

echo
echo "==============================================================="
echo " 15. PROMOTION VERS PINCABOS-PR-INTEGRATION"
echo "==============================================================="

git switch "$MAIN_BRANCH"

[ "$(git rev-parse HEAD)" = "$BASE_HEAD" ] ||
    fail "Branche principale a change."

git merge \
    --ff-only \
    "$WORK_BRANCH"

FINAL_HEAD="$(git rev-parse HEAD)"

[ "$FINAL_HEAD" = "$FINAL_WORK_HEAD" ] ||
    fail "HEAD final inattendu."

ok "Staging principal mis a jour."

echo
echo "==============================================================="
echo " 16. PUSH GITHUB MAIN"
echo "==============================================================="

git push \
    origin \
    HEAD:refs/heads/main

ok "Push GitHub termine."

echo
echo "=== 17. VERIFICATION GITHUB ==="

git fetch origin main

REMOTE_AFTER="$(git rev-parse refs/remotes/origin/main)"

echo "Local       : $FINAL_HEAD"
echo "GitHub main : $REMOTE_AFTER"

[ "$REMOTE_AFTER" = "$FINAL_HEAD" ] ||
    fail "GitHub main != local."

ok "GitHub == staging."

echo
echo "=== 18. ETAT PR #27 / #28 ==="

for PR in 27 28
do
    gh pr view \
        "$PR" \
        --repo KarotsSugarpie/PinCabOS \
        --json number,state,mergedAt,title \
        --template \
'PR #{{.number}} | {{.state}} | merged={{.mergedAt}} | {{.title}}{{"\n"}}'
done

echo
echo "=== 19. PR ENCORE OUVERTES ==="

gh pr list \
    --repo KarotsSugarpie/PinCabOS \
    --state open \
    --limit 100

echo
echo "=== 20. ETAT FINAL ==="

git status --short

[ -z "$(git status --porcelain)" ] ||
    fail "Git local non propre."

ok "Git propre."

echo
echo "==============================================================="
echo " GO [OK] PR #27 + #28 IMPORTEES"
echo "==============================================================="
echo
echo "Ancien HEAD:"
echo "  $BASE_HEAD"
echo
echo "Nouveau HEAD:"
echo "  $FINAL_HEAD"
echo
echo "PR #27:"
echo "  backups retires du DEPOT"
echo "  backups LIVE conserves"
echo
echo "PR #28:"
echo "  crash dumps retires du DEPOT"
echo "  fichiers LIVE conserves"
echo
echo "Backup GitHub:"
echo "  $BACKUP_REMOTE"
echo
echo "Backup local:"
echo "  $BACKUP_LOCAL"
echo
echo "Bundle:"
echo "  $BACKUP_DIR/before-pr27-28.bundle"
echo
echo "==============================================================="
