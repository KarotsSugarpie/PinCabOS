#!/usr/bin/env bash
set -Eeuo pipefail

clear

echo "==============================================================="
echo " PINCABOS — IMPORT DE TOUTES LES PR OUVERTES"
echo " PR #12 #13 #15 #21 #26"
echo " INTEGRATION TEMPORAIRE + CONTROLE AVANT PUSH"
echo "==============================================================="
echo

REPO="/opt/pincabos/tmp/pr-integration"
MAIN_BRANCH="pincabos-pr-integration"

EXPECTED_HEAD="f8159c97501ff8883b152a8aaa93951af666f3c8"

STAMP="$(date +%Y%m%d-%H%M%S)"

BACKUP_LOCAL="backup/pre-all-open-prs-$STAMP"
BACKUP_REMOTE="backup-main-before-all-open-prs-$STAMP"
WORK_BRANCH="integration/all-open-prs-$STAMP"

BACKUP_DIR="/opt/pincabos/backups/all-open-prs-$STAMP"

PRS=(12 13 15 21 26)

declare -A EXPECTED_PR_HEAD
EXPECTED_PR_HEAD[12]="56d11dc9945826fc35d6ca5c5951edeb58ffe504"
EXPECTED_PR_HEAD[13]="dc70216d714e8323453e1ab6b00662fb743ff193"
EXPECTED_PR_HEAD[15]="e8338d5ccef5c07f90af20d29ab33177cea0904a"
EXPECTED_PR_HEAD[21]="52046db45b169041bef72958692b489e9c5ce974"
EXPECTED_PR_HEAD[26]="9216ee580e19617092457ffb8e88775b7d9684e0"

EXPECTED_CONTENT_CHANGE="opt/pincabos/tools/pincabos-screen-lightdm-safe.sh"

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
    fail "Repo absent : $REPO"

cd "$REPO"

echo "=== 1. VALIDATION LOCALE ==="

BRANCH="$(git branch --show-current)"
HEAD="$(git rev-parse HEAD)"

echo "Branche : $BRANCH"
echo "HEAD    : $HEAD"

[ "$BRANCH" = "$MAIN_BRANCH" ] ||
    fail "Mauvaise branche."

[ "$HEAD" = "$EXPECTED_HEAD" ] ||
    fail "HEAD inattendu. Aucun import effectue."

[ -z "$(git status --porcelain)" ] ||
    fail "Git local non propre."

ok "Base locale correcte."

echo
echo "=== 2. VALIDATION GITHUB ==="

gh auth status >/dev/null 2>&1 ||
    fail "GitHub CLI non authentifie."

git fetch --prune origin

REMOTE_MAIN="$(git rev-parse refs/remotes/origin/main)"

echo "Local       : $HEAD"
echo "GitHub main : $REMOTE_MAIN"

[ "$REMOTE_MAIN" = "$HEAD" ] ||
    fail "GitHub main n'est plus identique au cab."

ok "GitHub main == local."

echo
echo "=== 3. BACKUPS ==="

mkdir -p "$BACKUP_DIR"

git branch \
    "$BACKUP_LOCAL" \
    "$HEAD"

git bundle create \
    "$BACKUP_DIR/before-all-open-prs.bundle" \
    --all

git push \
    origin \
    "$HEAD:refs/heads/$BACKUP_REMOTE"

ok "Backup local  : $BACKUP_LOCAL"
ok "Backup GitHub : $BACKUP_REMOTE"
ok "Bundle        : $BACKUP_DIR/before-all-open-prs.bundle"

echo
echo "==============================================================="
echo " 4. FETCH DE TOUTES LES PR"
echo "==============================================================="

for PR in "${PRS[@]}"
do
    echo
    echo "--- PR #$PR ---"

    git fetch \
        origin \
        "+refs/pull/$PR/head:refs/remotes/origin/pr/$PR"

    ACTUAL="$(
        git rev-parse \
        "refs/remotes/origin/pr/$PR"
    )"

    EXPECTED="${EXPECTED_PR_HEAD[$PR]}"

    echo "HEAD attendu : $EXPECTED"
    echo "HEAD recu    : $ACTUAL"

    [ "$ACTUAL" = "$EXPECTED" ] ||
        fail "PR #$PR a change depuis l'audit."

    git log \
        -1 \
        --oneline \
        "refs/remotes/origin/pr/$PR"

    ok "PR #$PR valide."
done

echo
echo "==============================================================="
echo " 5. CREATION BRANCHE D'INTEGRATION TEMPORAIRE"
echo "==============================================================="

git switch \
    -c "$WORK_BRANCH" \
    "$HEAD"

ok "Branche temporaire : $WORK_BRANCH"

echo
echo "==============================================================="
echo " 6. MERGE DES PR"
echo "==============================================================="

for PR in "${PRS[@]}"
do
    echo
    echo "---------------------------------------------------------------"
    echo " IMPORT PR #$PR"
    echo "---------------------------------------------------------------"

    BEFORE="$(git rev-parse HEAD)"

    if ! git merge \
        --no-ff \
        -m "merge(pr): import PR #$PR" \
        "refs/remotes/origin/pr/$PR"
    then
        echo
        echo "Conflits :"
        git status --short

        git merge --abort || true

        fail \
            "Conflit PR #$PR. Branche principale intacte."
    fi

    AFTER="$(git rev-parse HEAD)"

    echo "Avant : $BEFORE"
    echo "Apres : $AFTER"

    ok "PR #$PR fusionnee dans la branche temporaire."
done

NEW_HEAD="$(git rev-parse HEAD)"

echo
echo "==============================================================="
echo " 7. AUDIT DU CONTENU RESULTANT"
echo "==============================================================="

echo "Ancien HEAD : $HEAD"
echo "Nouveau HEAD: $NEW_HEAD"
echo

git --no-pager diff \
    --stat \
    "$HEAD..$NEW_HEAD"

echo
echo "--- FICHIERS DONT LE CONTENU CHANGE ---"

mapfile -t CHANGED < <(
    git diff \
        --name-only \
        "$HEAD..$NEW_HEAD"
)

if [ "${#CHANGED[@]}" -eq 0 ]
then
    fail "Aucun changement de contenu; PR #26 non appliquee."
fi

BAD=0

for REL in "${CHANGED[@]}"
do
    echo "$REL"

    if [ "$REL" != "$EXPECTED_CONTENT_CHANGE" ]
    then
        echo "NOGO [INATTENDU] $REL"
        BAD=1
    fi
done

[ "$BAD" -eq 0 ] ||
    fail \
        "Une ancienne PR modifie du contenu actuel. Aucun push."

ok "Seule la correction PR #26 change le contenu."

echo
echo "=== 8. VALIDATION EXACTE DE PR #26 ==="

TMP_PR26="/tmp/pincab-pr26-$$"

git show \
    "refs/remotes/origin/pr/26:$EXPECTED_CONTENT_CHANGE" \
    > "$TMP_PR26"

cmp -s \
    "$REPO/$EXPECTED_CONTENT_CHANGE" \
    "$TMP_PR26" ||
    fail "Le resultat final ne correspond pas exactement a PR #26."

rm -f "$TMP_PR26"

bash -n \
    "$REPO/$EXPECTED_CONTENT_CHANGE" ||
    fail "Syntaxe shell invalide dans PR #26."

git diff --check \
    "$HEAD..$NEW_HEAD" ||
    fail "git diff --check."

ok "PR #26 identique et syntaxiquement valide."

echo
echo "==============================================================="
echo " 9. RETOUR BRANCHE PRINCIPALE + FAST-FORWARD"
echo "==============================================================="

git switch "$MAIN_BRANCH"

git merge \
    --ff-only \
    "$WORK_BRANCH"

FINAL_HEAD="$(git rev-parse HEAD)"

[ "$FINAL_HEAD" = "$NEW_HEAD" ] ||
    fail "HEAD final inattendu."

ok "Toutes les PR sont maintenant rattachees au staging."

echo
echo "==============================================================="
echo " 10. PUSH GITHUB MAIN"
echo "==============================================================="

git push \
    origin \
    HEAD:refs/heads/main

ok "Push GitHub termine."

echo
echo "=== 11. VALIDATION GITHUB ==="

git fetch origin main

REMOTE_AFTER="$(
    git rev-parse refs/remotes/origin/main
)"

echo "Local       : $FINAL_HEAD"
echo "GitHub main : $REMOTE_AFTER"

[ "$REMOTE_AFTER" = "$FINAL_HEAD" ] ||
    fail "GitHub main != local."

ok "GitHub main == local."

echo
echo "==============================================================="
echo " 12. DEPLOIEMENT LIVE PR #26"
echo "==============================================================="

SRC="$REPO/$EXPECTED_CONTENT_CHANGE"
DST="/$EXPECTED_CONTENT_CHANGE"

[ -f "$SRC" ] ||
    fail "Source PR #26 absente."

[ -f "$DST" ] ||
    fail "Fichier live cible absent."

mkdir -p "$BACKUP_DIR/live"

cp -a \
    "$DST" \
    "$BACKUP_DIR/live/$(basename "$DST").before-pr26"

DST_UID="$(stat -c %u "$DST")"
DST_GID="$(stat -c %g "$DST")"
DST_MODE="$(stat -c %a "$DST")"

TMP="${DST}.pr26.$$"

install \
    -o "$DST_UID" \
    -g "$DST_GID" \
    -m "$DST_MODE" \
    "$SRC" \
    "$TMP"

mv -f \
    "$TMP" \
    "$DST"

cmp -s \
    "$SRC" \
    "$DST" ||
    fail "Live != staging apres deploy."

ok "PR #26 deployee sur le cab."

echo
echo "=== 13. ETAT DES PR GITHUB ==="

gh pr list \
    --repo KarotsSugarpie/PinCabOS \
    --state open \
    --json number,title \
    --template \
'{{range .}}{{printf "#%v  %s\n" .number .title}}{{end}}' \
    || true

echo
echo "=== 14. GIT FINAL ==="

git status --short

[ -z "$(git status --porcelain)" ] ||
    fail "Git local non propre."

ok "Git propre."

echo
echo "==============================================================="
echo " GO [OK] TOUTES LES PR OUVERTES IMPORTEES"
echo "==============================================================="
echo
echo "PR traitees :"
echo "  #12"
echo "  #13"
echo "  #15"
echo "  #21"
echo "  #26"
echo
echo "Ancien HEAD : $HEAD"
echo "Nouveau HEAD: $FINAL_HEAD"
echo
echo "Changement fonctionnel nouveau:"
echo "  PR #26"
echo "  retrait du garde EDID dangereux pour NVIDIA"
echo
echo "Backup GitHub:"
echo "  $BACKUP_REMOTE"
echo
echo "Backup local:"
echo "  $BACKUP_LOCAL"
echo
echo "Backup fichiers:"
echo "  $BACKUP_DIR"
echo
echo "==============================================================="
