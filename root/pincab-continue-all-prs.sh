#!/usr/bin/env bash
set -Eeuo pipefail

clear

echo "==============================================================="
echo " PINCABOS — CONTINUATION IMPORT TOUTES LES PR"
echo " PR #12 #13 #15 #21 #26"
echo " VALIDATION -> STAGING -> GITHUB MAIN"
echo " AUCUN REDEPLOIEMENT LIVE DANS CETTE ETAPE"
echo "==============================================================="
echo

REPO="/opt/pincabos/tmp/pr-integration"

MAIN_BRANCH="pincabos-pr-integration"
WORK_BRANCH="integration/all-open-prs-20260818-160210"

BASE_HEAD="f8159c97501ff8883b152a8aaa93951af666f3c8"
WORK_HEAD="8bc3e103bc9b0d125f1844bf62cf26fca99eae9d"

BACKUP_REMOTE="backup-main-before-all-open-prs-20260818-160210"
BACKUP_LOCAL="backup/pre-all-open-prs-20260818-160210"

TMPDIR="$(mktemp -d /tmp/pincab-pr-continue.XXXXXX)"

cleanup()
{
    rm -rf "$TMPDIR"
}
trap cleanup EXIT

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

echo "=== 1. VALIDATION BRANCHE TEMPORAIRE ==="

CURRENT_BRANCH="$(git branch --show-current)"
CURRENT_HEAD="$(git rev-parse HEAD)"

echo "Branche actuelle : $CURRENT_BRANCH"
echo "HEAD actuel      : $CURRENT_HEAD"

[ "$CURRENT_BRANCH" = "$WORK_BRANCH" ] ||
    fail "On n'est plus sur la branche temporaire attendue."

[ "$CURRENT_HEAD" = "$WORK_HEAD" ] ||
    fail "Le HEAD temporaire a change."

[ -z "$(git status --porcelain)" ] ||
    fail "Working tree non propre."

ok "Branche temporaire intacte."

echo
echo "=== 2. VALIDATION BASE PRINCIPALE ==="

MAIN_HEAD="$(git rev-parse "$MAIN_BRANCH")"

echo "Staging principal : $MAIN_HEAD"

[ "$MAIN_HEAD" = "$BASE_HEAD" ] ||
    fail "$MAIN_BRANCH a change depuis le NOGO."

git fetch --prune origin

REMOTE_MAIN="$(git rev-parse refs/remotes/origin/main)"

echo "GitHub main       : $REMOTE_MAIN"

[ "$REMOTE_MAIN" = "$BASE_HEAD" ] ||
    fail "GitHub main a change depuis le NOGO."

ok "Base locale et GitHub intactes."

echo
echo "=== 3. VALIDATION DES BACKUPS EXISTANTS ==="

git show-ref \
    --verify \
    --quiet \
    "refs/heads/$BACKUP_LOCAL" ||
    fail "Backup local introuvable."

if ! git ls-remote \
    --exit-code \
    --heads \
    origin \
    "$BACKUP_REMOTE" \
    >/dev/null 2>&1
then
    fail "Backup GitHub introuvable."
fi

ok "Backup local present."
ok "Backup GitHub present."

echo
echo "=== 4. VALIDATION DES 5 PR DANS LE RESULTAT ==="

for PR in 12 13 15 21 26
do
    REF="refs/remotes/origin/pr/$PR"

    git show-ref \
        --verify \
        --quiet \
        "$REF" ||
        fail "Reference PR #$PR absente."

    PR_HEAD="$(git rev-parse "$REF")"

    if git merge-base \
        --is-ancestor \
        "$PR_HEAD" \
        "$WORK_HEAD"
    then
        echo "GO [OK] PR #$PR incluse : $PR_HEAD"
    else
        fail "PR #$PR n'est pas incluse dans le resultat."
    fi
done

echo
echo "=== 5. VALIDATION EXACTE DES FICHIERS MODIFIES ==="

cat > "$TMPDIR/expected.txt" <<'EOF'
etc/systemd/system/pincabos-scoreview-router.service
opt/pincabos/bin/pincabos-scoreview-router.sh
opt/pincabos/installer-gui/templates/wizard.html
opt/pincabos/tools/pincabos-screen-lightdm-safe.sh
opt/pincabos/web/app.py
opt/pincabos/web/pincabos_batch_import_worker_v2.py
usr/local/bin/pincabos-kiosk.py
EOF

sort -o "$TMPDIR/expected.txt" "$TMPDIR/expected.txt"

git diff \
    --name-only \
    "$BASE_HEAD..$WORK_HEAD" \
    | sort \
    > "$TMPDIR/actual.txt"

echo "--- ATTENDU ---"
cat "$TMPDIR/expected.txt"

echo
echo "--- REEL ---"
cat "$TMPDIR/actual.txt"

if ! diff \
    -u \
    "$TMPDIR/expected.txt" \
    "$TMPDIR/actual.txt"
then
    fail "Liste des fichiers differente de l'audit."
fi

ok "Exactement 7 fichiers modifies."

echo
echo "=== 6. DIFF STAT ==="

git --no-pager diff \
    --stat \
    "$BASE_HEAD..$WORK_HEAD"

echo
echo "=== 7. VALIDATION SHELL ==="

for REL in \
    opt/pincabos/bin/pincabos-scoreview-router.sh \
    opt/pincabos/tools/pincabos-screen-lightdm-safe.sh
do
    bash -n "$REPO/$REL" ||
        fail "Erreur syntaxe shell : $REL"

    echo "GO [OK] $REL"
done

echo
echo "=== 8. VALIDATION PYTHON ==="

for REL in \
    opt/pincabos/web/app.py \
    opt/pincabos/web/pincabos_batch_import_worker_v2.py \
    usr/local/bin/pincabos-kiosk.py
do
    python3 -m py_compile "$REPO/$REL" ||
        fail "Erreur syntaxe Python : $REL"

    echo "GO [OK] $REL"
done

echo
echo "=== 9. VALIDATION SYSTEMD ==="

if command -v systemd-analyze >/dev/null 2>&1
then
    if systemd-analyze verify \
        "$REPO/etc/systemd/system/pincabos-scoreview-router.service" \
        >"$TMPDIR/systemd-verify.txt" 2>&1
    then
        ok "Service systemd syntaxiquement valide."
    else
        cat "$TMPDIR/systemd-verify.txt"
        fail "systemd-analyze verify."
    fi
else
    echo "AVERTISSEMENT : systemd-analyze absent."
fi

echo
echo "=== 10. VALIDATION DIFF GIT ==="

git diff \
    --check \
    "$BASE_HEAD..$WORK_HEAD" ||
    fail "git diff --check a detecte une erreur."

ok "Diff Git valide."

echo
echo "=== 11. SCAN CREDENTIALS AJOUTES ==="

git diff \
    --unified=0 \
    "$BASE_HEAD..$WORK_HEAD" \
    > "$TMPDIR/all.diff"

if sed -n \
    '/^+++ /!s/^+//p' \
    "$TMPDIR/all.diff" |
    grep -E \
    'gh[opusr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|BEGIN (OPENSSH |RSA |EC |DSA )?PRIVATE KEY|AKIA[A-Z0-9]{16}' \
    > "$TMPDIR/secrets.txt"
then
    echo "NOGO : credential potentiel detecte."
    sed \
        's/[A-Za-z0-9_]\{8,\}/[MASQUE]/g' \
        "$TMPDIR/secrets.txt"

    fail "Credential potentiel dans les ajouts."
fi

ok "Aucun token/cle privee evident ajoute."

echo
echo "==============================================================="
echo " 12. PROMOTION VERS PINCABOS-PR-INTEGRATION"
echo "==============================================================="

git switch "$MAIN_BRANCH"

[ "$(git rev-parse HEAD)" = "$BASE_HEAD" ] ||
    fail "Base locale differente juste avant promotion."

git merge \
    --ff-only \
    "$WORK_BRANCH"

FINAL_HEAD="$(git rev-parse HEAD)"

echo "Ancien HEAD : $BASE_HEAD"
echo "Nouveau HEAD: $FINAL_HEAD"

[ "$FINAL_HEAD" = "$WORK_HEAD" ] ||
    fail "HEAD final inattendu."

ok "Staging principal mis a jour."

echo
echo "==============================================================="
echo " 13. PUSH GITHUB MAIN"
echo "==============================================================="

git push \
    origin \
    HEAD:refs/heads/main

ok "Push termine."

echo
echo "=== 14. VERIFICATION GITHUB ==="

git fetch origin main

REMOTE_AFTER="$(git rev-parse refs/remotes/origin/main)"

echo "Local       : $FINAL_HEAD"
echo "GitHub main : $REMOTE_AFTER"

[ "$REMOTE_AFTER" = "$FINAL_HEAD" ] ||
    fail "GitHub main != staging."

ok "GitHub main == staging."

echo
echo "=== 15. VERIFICATION DES PR ==="

for PR in 12 13 15 21 26
do
    echo
    echo "--- PR #$PR ---"

    gh pr view \
        "$PR" \
        --repo KarotsSugarpie/PinCabOS \
        --json number,state,mergedAt,title \
        --template \
'PR #{{.number}} | {{.state}} | merged={{.mergedAt}} | {{.title}}{{"\n"}}' \
        || true
done

echo
echo "=== 16. ETAT FINAL GIT ==="

git status --short

[ -z "$(git status --porcelain)" ] ||
    fail "Git non propre apres push."

ok "Git propre."

echo
echo "==============================================================="
echo " GO [OK] TOUTES LES PR IMPORTEES DANS GITHUB MAIN"
echo "==============================================================="
echo
echo "PR integrees:"
echo "  #12"
echo "  #13"
echo "  #15"
echo "  #21"
echo "  #26"
echo
echo "Ancien HEAD:"
echo "  $BASE_HEAD"
echo
echo "Nouveau HEAD:"
echo "  $FINAL_HEAD"
echo
echo "Backup GitHub:"
echo "  $BACKUP_REMOTE"
echo
echo "IMPORTANT:"
echo "  Le code est maintenant dans staging + GitHub."
echo "  Aucun service live du cab n'a ete redemarre."
echo "==============================================================="
