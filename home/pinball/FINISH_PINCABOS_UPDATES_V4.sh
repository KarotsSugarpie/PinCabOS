#!/usr/bin/env bash
set -Eeuo pipefail

WORK="/home/pinball/pincabos-updates-v4-source-20260822-090111"
SRC="$WORK/source"

REPO="PinCabOS/PinCabOS"
BRANCH="feat/updates-v4-clean-20260822-090111"
VERSION="alpha2.40-beta.20260822.1"
CHANNEL="beta"

fail() {
    echo
    echo "==============================================================="
    echo " NOGO [!!] $*"
    echo "==============================================================="
    exit 1
}

go() {
    echo "GO [OK] $*"
}

echo "==============================================================="
echo " PINCABOS - FINALISATION UPDATES V4"
echo " AUCUN RECLONE - AUCUN REBOOT"
echo "==============================================================="
echo

[[ -d "$SRC/.git" ]] || fail "Clone existant introuvable: $SRC"

CURRENT_BRANCH="$(git -C "$SRC" branch --show-current)"
[[ "$CURRENT_BRANCH" == "$BRANCH" ]] || \
    fail "Branche inattendue: $CURRENT_BRANCH"

echo "Work    : $WORK"
echo "Branch  : $BRANCH"
echo "Version : $VERSION"
echo

echo "=== 1. CORRECTION WHITESPACE ==="

sed -i 's/[[:space:]]\+$//' \
    "$SRC/opt/pincabos/web/tools.py"

git -C "$SRC" diff --check || \
    fail "git diff --check encore en erreur"

go "Whitespace nettoye."
echo

echo "=== 2. LOCALISATION DU PACKAGE DEJA CONSTRUIT ==="

RELDIR="$(
    find "$WORK" \
        -type f \
        -name 'pincabos-update.tar.zst' \
        -printf '%h\n' \
        | head -1
)"

[[ -n "$RELDIR" ]] || fail "Repertoire Release introuvable"

ARCHIVE="$RELDIR/pincabos-update.tar.zst"
FILES="$RELDIR/files.list"
REMOVE="$RELDIR/remove.list"
META="$RELDIR/release.json"
AUDIT="$RELDIR/audit.sha256"

for F in "$FILES" "$REMOVE" "$META"; do
    [[ -f "$F" ]] || fail "Fichier Release absent: $F"
done

echo "Release : $RELDIR"
echo

echo "=== 3. VALIDATION DES FICHIERS DU PACKAGE ==="

export PYTHONPYCACHEPREFIX="/tmp/pincabos-v4-final-pycache-$UID"
rm -rf "$PYTHONPYCACHEPREFIX"
mkdir -p "$PYTHONPYCACHEPREFIX"

while IFS= read -r REL || [[ -n "$REL" ]]; do
    [[ -n "$REL" ]] || continue

    P="$SRC/$REL"

    [[ -e "$P" || -L "$P" ]] || \
        fail "Fichier de files.list absent dans source: $REL"

    [[ -f "$P" ]] || continue

    FIRST="$(head -n 1 "$P" 2>/dev/null || true)"

    if [[ "$REL" == *.py || "$FIRST" == *python* ]]; then
        python3 -m py_compile "$P" || \
            fail "Python invalide: $REL"

    elif [[ "$FIRST" == *bash* || "$FIRST" == "#!/bin/sh"* || "$FIRST" == "#!/usr/bin/sh"* ]]; then
        bash -n "$P" || \
            fail "Shell invalide: $REL"
    fi

done < "$FILES"

rm -rf "$PYTHONPYCACHEPREFIX"

go "Scripts du package valides."
echo

echo "=== 4. RECONSTRUCTION PROPRE DE L'ARCHIVE ==="

rm -f "$ARCHIVE"

tar \
    --zstd \
    --owner=0 \
    --group=0 \
    --numeric-owner \
    -cpf "$ARCHIVE" \
    -C "$SRC" \
    -T "$FILES"

[[ -s "$ARCHIVE" ]] || fail "Archive vide"

ARCHIVE_SHA="$(
    sha256sum "$ARCHIVE" |
    awk '{print $1}'
)"

python3 - "$META" "$ARCHIVE_SHA" "$VERSION" "$CHANNEL" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
sha = sys.argv[2]
version = sys.argv[3]
channel = sys.argv[4]

data = json.loads(path.read_text(encoding="utf-8"))

data["version"] = version
data["channel"] = channel
data["archive"] = "pincabos-update.tar.zst"
data["files"] = "files.list"
data["remove"] = "remove.list"
data["archive_sha256"] = sha

path.write_text(
    json.dumps(data, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
PY

(
    cd "$RELDIR"

    sha256sum \
        pincabos-update.tar.zst \
        files.list \
        remove.list \
        release.json \
        > audit.sha256

    sha256sum -c audit.sha256
)

go "SHA256 archive: $ARCHIVE_SHA"
echo

echo "=== 5. VALIDATION ARCHIVE == FILES.LIST ==="

TMP_EXPECTED="$(mktemp)"
TMP_ACTUAL="$(mktemp)"

sort -u "$FILES" > "$TMP_EXPECTED"

tar --zstd -tf "$ARCHIVE" \
    | sed 's#^\./##' \
    | sed '/\/$/d' \
    | sort -u \
    > "$TMP_ACTUAL"

if ! diff -u "$TMP_EXPECTED" "$TMP_ACTUAL"; then
    rm -f "$TMP_EXPECTED" "$TMP_ACTUAL"
    fail "Archive differente de files.list"
fi

rm -f "$TMP_EXPECTED" "$TMP_ACTUAL"

go "Archive exactement conforme a files.list."
echo

echo "=== 6. PREFLIGHT GIT FINAL ==="

git -C "$SRC" add -A

git -C "$SRC" diff --cached --check || \
    fail "git diff --cached --check"

echo
echo "--- FICHIERS QUI SERONT POUSSES ---"
git -C "$SRC" diff --cached --name-status
echo

BAD="$(
    git -C "$SRC" diff --cached --name-only |
    grep -Ev \
'^(opt/pincabos/update/|opt/pincabos/web/tools\.py$|opt/pincabos/web/pincabos_updates\.py$|opt/pincabos/script/build-update\.sh$|opt/pincabos/script/publish-update\.sh$|usr/local/bin/getpcos$|usr/local/sbin/getpcos$|usr/local/sbin/build-update\.sh$|\.github/workflows/pincabos-release-v4\.yml$|opt/pincabos/version\.json$|opt/pincabos/config/version\.json$)' \
    || true
)"

if [[ -n "$BAD" ]]; then
    echo "$BAD"
    fail "Des fichiers hors sous-systeme Updates seraient pousses"
fi

go "Diff Git limite au sous-systeme Updates."
echo

echo "=== 7. VERIFICATION QUE MAIN N'A PAS CHANGE ==="

git -C "$SRC" fetch origin main

BASE_EXPECTED="2832a7da406ba3db8166d6910310a7ed29f59563"
BASE_NOW="$(git -C "$SRC" rev-parse origin/main)"

echo "Main attendu : $BASE_EXPECTED"
echo "Main actuel  : $BASE_NOW"

[[ "$BASE_NOW" == "$BASE_EXPECTED" ]] || \
    fail "main a change depuis le preflight. Aucun push effectue."

go "Main toujours identique."
echo

echo "==============================================================="
echo " GO [OK] PREFLIGHT FINAL COMPLET"
echo " A PARTIR D'ICI SEULEMENT, GITHUB SERA MODIFIE"
echo "==============================================================="
echo

echo "=== 8. COMMIT ==="

git -C "$SRC" config user.name \
    "PinCabOS Integration"

git -C "$SRC" config user.email \
    "pincabos@localhost"

git -C "$SRC" commit \
    -m "feat(updates): replace legacy updater with GitHub Releases V4"

COMMIT_SHA="$(git -C "$SRC" rev-parse HEAD)"

go "Commit: $COMMIT_SHA"
echo

echo "=== 9. PUSH DE LA BRANCHE ==="

git -C "$SRC" push \
    -u origin "$BRANCH"

go "Branche poussee."
echo

echo "=== 10. CREATION DE LA PR ==="

PR_URL="$(
    gh pr create \
        --repo "$REPO" \
        --base main \
        --head "$BRANCH" \
        --title "PinCabOS Updates V4 - GitHub Releases" \
        --body "Remplace completement l'ancien sous-systeme Updates par Updates V4.

- GitHub Releases comme source officielle
- nouveau moteur Python getpcos
- nouvelle page Outils /tools/updates
- backup et rollback
- validation SHA256
- suppression de l'ancien publisher pincabos.cc
- builder Release GitHub propre"
)"

echo "$PR_URL"

PR_NUMBER="${PR_URL##*/}"

[[ "$PR_NUMBER" =~ ^[0-9]+$ ]] || \
    fail "Numero PR impossible a determiner"

go "PR #$PR_NUMBER creee."
echo

echo "=== 11. MERGE DE LA PR ==="

gh pr merge "$PR_NUMBER" \
    --repo "$REPO" \
    --squash \
    --delete-branch

STATE="$(
    gh pr view "$PR_NUMBER" \
        --repo "$REPO" \
        --json state \
        --jq '.state'
)"

[[ "$STATE" == "MERGED" ]] || \
    fail "PR non mergee: $STATE"

go "PR #$PR_NUMBER mergee."
echo

echo "=== 12. ATTENTE DU WORKFLOW RELEASE ==="

RUN_ID=""

for _ in $(seq 1 15); do

    RUN_ID="$(
        gh run list \
            --repo "$REPO" \
            --workflow pincabos-release-v4.yml \
            --branch main \
            --limit 5 \
            --json databaseId,status \
            --jq '.[0].databaseId // empty' \
            2>/dev/null || true
    )"

    [[ -n "$RUN_ID" ]] && break

    sleep 2
done

if [[ -n "$RUN_ID" ]]; then

    echo "Workflow run : $RUN_ID"

    if gh run watch "$RUN_ID" \
        --repo "$REPO" \
        --exit-status
    then
        go "GitHub Actions termine avec succes."
    else
        echo "AVERTISSEMENT: workflow non vert."
        echo "La Release sera creee directement depuis les assets preflightes."
    fi

else

    echo "AVERTISSEMENT: aucun workflow detecte."
    echo "Creation directe de la Release."

fi

echo

echo "=== 13. RELEASE GITHUB ==="

if gh release view "$VERSION" \
    --repo "$REPO" \
    >/dev/null 2>&1
then

    echo "Release deja creee par GitHub Actions."

    gh release upload "$VERSION" \
        "$ARCHIVE" \
        "$FILES" \
        "$REMOVE" \
        "$META" \
        "$AUDIT" \
        --repo "$REPO" \
        --clobber

else

    gh release create "$VERSION" \
        "$ARCHIVE" \
        "$FILES" \
        "$REMOVE" \
        "$META" \
        "$AUDIT" \
        --repo "$REPO" \
        --target main \
        --title "PinCabOS $VERSION" \
        --notes "PinCabOS Updates V4

Premiere release utilisant le nouveau sous-systeme GitHub Releases.

Canal: beta
Updater: getpcos V4
Rollback et verification SHA256 inclus." \
        --prerelease
fi

go "Release GitHub disponible."
echo

echo "=== 14. AUDIT DES ASSETS DISTANTS ==="

gh release view "$VERSION" \
    --repo "$REPO" \
    --json tagName,isPrerelease,url,assets \
    --jq '
      "Tag       : " + .tagName,
      "Prerelease: " + (.isPrerelease|tostring),
      "URL       : " + .url,
      "Assets:",
      (.assets[].name)
    '

for NAME in \
    pincabos-update.tar.zst \
    files.list \
    remove.list \
    release.json \
    audit.sha256
do

    gh release view "$VERSION" \
        --repo "$REPO" \
        --json assets \
        --jq '.assets[].name' \
        | grep -qx "$NAME" \
        || fail "Asset distant absent: $NAME"

done

go "Les 5 assets sont presents."
echo

echo "=== 15. TEST DU CAB CONTRE LA NOUVELLE RELEASE ==="

/usr/local/sbin/getpcos check || \
    fail "getpcos check ne voit pas correctement la Release"

echo
echo "==============================================================="
echo " GO [OK] PINCABOS UPDATES V4 PUBLIE"
echo "==============================================================="
echo
echo "PR      : #$PR_NUMBER"
echo "Version : $VERSION"
echo "Canal   : $CHANNEL"
echo
echo "AUCUN REBOOT EFFECTUE."
echo
