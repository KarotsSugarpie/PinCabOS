#!/usr/bin/env bash
set -Eeuo pipefail

export GIT_PAGER=cat
export PAGER=cat
export GIT_EDITOR=true

GITDIR="/opt/pincabos/.git-rootfs"
REPO="KarotsSugarpie/PinCabOS"
STATE="/opt/pincabos/config/gitpush-release-sequence.json"
CALLER="${SUDO_USER:-pinball}"
CHANNEL="beta"

pgit() {
    git --no-pager \
        --git-dir="$GITDIR" \
        --work-tree=/ \
        "$@"
}

pgh() {
    sudo -u "$CALLER" -H \
        gh "$@"
}

cd /

echo
echo "================================================================"
echo " PINCABOS - RELEASE APRES GITPUSH"
echo "================================================================"

echo
echo "=== 1. AUTHENTIFICATION GITHUB ==="

if ! pgh auth status \
        --hostname github.com \
        >/dev/null 2>&1
then
    echo "NOGO [GH AUTH]"
    echo "GitHub CLI de $CALLER n'est pas authentifie."
    exit 1
fi

echo "GO [OK] GitHub CLI."

echo
echo "=== 2. DERNIERE PR GITHUB MERGEE ==="

LATEST_PR="$(
    pgh pr list \
        --repo "$REPO" \
        --state merged \
        --limit 100 \
        --json number,mergedAt \
        --jq \
        'sort_by([.mergedAt, .number]) | last | .number'
)"

[[ "$LATEST_PR" =~ ^[0-9]+$ ]] || {
    echo "NOGO [PR] Impossible de detecter la derniere PR."
    exit 1
}

LATEST_TITLE="$(
    pgh pr view \
        "$LATEST_PR" \
        --repo "$REPO" \
        --json title \
        --jq '.title'
)"

echo "Derniere PR GitHub : #$LATEST_PR"
echo "Titre              : $LATEST_TITLE"

LAST_NUMBER=""
MANUAL="false"

if [[ -f "$STATE" ]]; then
    readarray -t STATE_DATA < <(
        python3 - "$STATE" <<'PY'
import json
import sys

try:
    data = json.load(open(sys.argv[1], encoding="utf-8"))
    print(data.get("last_number", ""))
    print("true" if data.get("manual_sequence") else "false")
except Exception:
    print("")
    print("false")
PY
    )

    LAST_NUMBER="${STATE_DATA[0]:-}"
    MANUAL="${STATE_DATA[1]:-false}"
fi

if [[ "$MANUAL" == "true" &&
      "$LAST_NUMBER" =~ ^[0-9]+$ ]]
then
    NEXT_MANUAL=$((LAST_NUMBER + 1))

    echo
    echo "Sequence PinCabOS personnalisee :"
    echo "Derniere release PR             : $LAST_NUMBER"
    echo "Prochaine                       : $NEXT_MANUAL"
fi

echo
echo "=== 3. CHOIX DU NUMERO ==="

printf \
    "Utiliser la derniere PR GitHub #%s pour la release ? [O/n] " \
    "$LATEST_PR"

read -r ANSWER

ANSWER="${ANSWER,,}"

case "$ANSWER" in

    ""|o|oui|y|yes)
        RELEASE_NUMBER="$LATEST_PR"
        MANUAL_NEW="false"
        ;;

    n|non|no)

        if [[ "$MANUAL" == "true" &&
              "$LAST_NUMBER" =~ ^[0-9]+$ ]]
        then
            DEFAULT_NUMBER=$((LAST_NUMBER + 1))
        else
            DEFAULT_NUMBER=$((LATEST_PR + 1))
        fi

        printf \
            "Numero PR/release [%s] : " \
            "$DEFAULT_NUMBER"

        read -r CUSTOM

        RELEASE_NUMBER="${CUSTOM:-$DEFAULT_NUMBER}"

        [[ "$RELEASE_NUMBER" =~ ^[0-9]+$ ]] || {
            echo "NOGO [NUMERO] Entier requis."
            exit 1
        }

        MANUAL_NEW="true"
        ;;

    *)
        echo "NOGO [REPONSE] Utiliser O ou N."
        exit 1
        ;;
esac

DISPLAY_VERSION="Alpha 2.${RELEASE_NUMBER}"

echo
echo "Release choisie : PR${RELEASE_NUMBER}"
echo "Version          : $DISPLAY_VERSION"
echo "PR source        : #$LATEST_PR"

echo
echo "=== 4. SYNCHRONISATION VERSION SUR LE CABINET ==="

python3 - \
    "$RELEASE_NUMBER" \
    "$DISPLAY_VERSION" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

number = int(sys.argv[1])
display = sys.argv[2]

stamp = datetime.now(
    timezone.utc
).strftime("%Y-%m-%dT%H:%M:%SZ")

paths = [
    Path("/opt/pincabos/version.json"),
    Path("/opt/pincabos/config/version.json"),
]

for path in paths:
    if not path.exists():
        continue

    data = json.loads(
        path.read_text(encoding="utf-8")
    )

    data["version"] = display

    if "updated_at" in data:
        data["updated_at"] = (
            stamp
            .replace("T", " ")
            .replace("Z", "")
        )

    if "generated_at" in data:
        data["generated_at"] = stamp

    path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )
PY

echo "GO [OK] Version cabinet = $DISPLAY_VERSION"

echo
echo "=== 5. COMMIT VERSION ==="

pgit fetch origin \
    '+refs/heads/main:refs/remotes/origin/main'

LOCAL="$(pgit rev-parse HEAD)"
REMOTE="$(pgit rev-parse refs/remotes/origin/main)"

if [[ "$LOCAL" != "$REMOTE" ]]; then
    echo "NOGO [COLLISION]"
    echo "Local  : $LOCAL"
    echo "GitHub : $REMOTE"
    exit 1
fi

VERSION_FILES=()

[[ -f /opt/pincabos/version.json ]] &&
    VERSION_FILES+=("opt/pincabos/version.json")

[[ -f /opt/pincabos/config/version.json ]] &&
    VERSION_FILES+=("opt/pincabos/config/version.json")

if (( ${#VERSION_FILES[@]} > 0 )); then

    pgit add -- "${VERSION_FILES[@]}"

    if ! pgit diff --cached --quiet; then

        pgit commit \
            -m "chore(release): ${DISPLAY_VERSION} [skip ci]"

        pgit push origin \
            HEAD:refs/heads/main
    fi
fi

RELEASE_SHA="$(pgit rev-parse HEAD)"

echo "Release commit : $RELEASE_SHA"

echo
echo "=== 6. GENERATION DU TAG ==="

DATE_TAG="$(date -u +%Y%m%d)"

SERIAL=1

while true; do

    TAG="alpha2.${RELEASE_NUMBER}-${CHANNEL}.${DATE_TAG}.${SERIAL}"

    if ! pgh release view \
        "$TAG" \
        --repo "$REPO" \
        >/dev/null 2>&1
    then
        break
    fi

    SERIAL=$((SERIAL + 1))
done

echo "Tag : $TAG"

echo
echo "=== 7. BUILD RELEASE V4 ==="

DIST="$(
    mktemp -d \
        "/tmp/pincabos-release-${RELEASE_NUMBER}-XXXXXX"
)"

cleanup() {
    rm -rf "$DIST"
}

trap cleanup EXIT

GITHUB_SHA="$RELEASE_SHA" \
python3 \
    /opt/pincabos/update/build_release_v4.py \
    --version "$TAG" \
    --display-version "$DISPLAY_VERSION" \
    --channel "$CHANNEL" \
    --out "$DIST"

echo
echo "=== 8. VALIDATION SHA256 ==="

(
    cd "$DIST"
    sha256sum -c audit.sha256
)

echo "GO [OK] SHA256."

echo
echo "=== 9. VALIDATION DES ASSETS ==="

ASSETS=(
    "pincabos-update.tar.zst"
    "files.list"
    "remove.list"
    "release.json"
    "audit.sha256"
)

for F in "${ASSETS[@]}"; do

    [[ -s "$DIST/$F" ]] || {
        echo "NOGO [ASSET] $F absent/vide."
        exit 1
    }

    echo "GO [OK] $F"
done

#
# Le user pinball doit pouvoir lire les assets.
#
chown -R "$CALLER":"$CALLER" "$DIST"

echo
echo "=== 10. PUBLICATION GITHUB RELEASE ==="

NOTES="$(
cat <<EOF
PinCabOS ${DISPLAY_VERSION}

Release creee par gitpush depuis le cabinet PinCabOS.

PR GitHub source : #${LATEST_PR}
${LATEST_TITLE}

Commit cabinet : ${RELEASE_SHA}

Release complete des fichiers geres par Updates V4.
Validation SHA-256, backup et rollback.
EOF
)"

pgh release create \
    "$TAG" \
    "$DIST/pincabos-update.tar.zst" \
    "$DIST/files.list" \
    "$DIST/remove.list" \
    "$DIST/release.json" \
    "$DIST/audit.sha256" \
    --repo "$REPO" \
    --target "$RELEASE_SHA" \
    --title "PinCabOS ${DISPLAY_VERSION}" \
    --notes "$NOTES" \
    --prerelease

echo
echo "=== 11. VALIDATION RELEASE ==="

CHECK_TAG="$(
    pgh release view \
        "$TAG" \
        --repo "$REPO" \
        --json tagName \
        --jq '.tagName'
)"

[[ "$CHECK_TAG" == "$TAG" ]] || {
    echo "NOGO [RELEASE]"
    exit 1
}

echo "GO [OK] Release GitHub : $TAG"

echo
echo "=== 12. MEMORISATION DE LA SEQUENCE ==="

mkdir -p /opt/pincabos/config

python3 - \
    "$STATE" \
    "$RELEASE_NUMBER" \
    "$MANUAL_NEW" \
    "$LATEST_PR" \
    "$TAG" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])

data = {
    "last_number": int(sys.argv[2]),
    "manual_sequence": sys.argv[3] == "true",
    "source_pr": int(sys.argv[4]),
    "last_tag": sys.argv[5],
    "updated_at": datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ"),
}

path.write_text(
    json.dumps(
        data,
        indent=2,
        ensure_ascii=False,
    ) + "\n",
    encoding="utf-8",
)
PY

pgit add -- \
    opt/pincabos/config/gitpush-release-sequence.json

if ! pgit diff --cached --quiet; then

    pgit commit \
        -m "chore(release): remember PR${RELEASE_NUMBER} sequence [skip ci]"

    pgit push origin \
        HEAD:refs/heads/main
fi

echo
echo "================================================================"
echo " GO [OK] RELEASE TERMINEE"
echo "================================================================"
echo "PR GitHub source : #$LATEST_PR"
echo "Numero PinCabOS  : PR$RELEASE_NUMBER"
echo "Version          : $DISPLAY_VERSION"
echo "Tag              : $TAG"
echo "================================================================"
