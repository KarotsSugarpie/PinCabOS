#!/usr/bin/env bash
set -Eeuo pipefail

REPO="KarotsSugarpie/PinCabOS"
PRNUM="42"
DISPLAY="Alpha 2.42"
TAG="alpha2.42-beta.20260822.1"

WORK="/home/pinball/pincabos-fullwidth-auto-release-20260822-093232"
SRC="$WORK/source"

MERGE_SHA="785904e1f96a8ac53bfbccdddc9c1164daf0dfc3"

fail()
{
    echo
    echo "==============================================================="
    echo " NOGO [!!] CONTINUATION PR42"
    echo "==============================================================="
    exit 1
}

echo "==============================================================="
echo " PINCABOS - CONTINUATION APRES MERGE PR #42"
echo " ALPHA 2.42 + RELEASE + UPDATE + TEST WEB"
echo " AUCUN REBOOT"
echo "==============================================================="
echo

sudo -v

echo "=== 1. VALIDATION PR #42 ==="

MERGED_AT="$(
    gh pr view \
        "$PRNUM" \
        --repo "$REPO" \
        --json mergedAt \
        --jq '.mergedAt'
)"

STATE="$(
    gh pr view \
        "$PRNUM" \
        --repo "$REPO" \
        --json state \
        --jq '.state'
)"

REMOTE_MERGE_SHA="$(
    gh pr view \
        "$PRNUM" \
        --repo "$REPO" \
        --json mergeCommit \
        --jq '.mergeCommit.oid'
)"

echo "Etat       : $STATE"
echo "Merged at  : $MERGED_AT"
echo "Merge SHA  : $REMOTE_MERGE_SHA"

if [ -z "$MERGED_AT" ] || [ "$MERGED_AT" = "null" ]; then
    echo "NOGO [!!] PR #42 non mergee."
    exit 1
fi

if [ "$REMOTE_MERGE_SHA" != "$MERGE_SHA" ]; then
    echo "NOGO [!!] Merge SHA inattendu."
    exit 1
fi

echo "GO [OK] PR #42 officiellement mergee."
echo

echo "=== 2. VALIDATION QUE PR #42 EST TOUJOURS LA DERNIERE MERGEE ==="

LATEST_PR="$(
    gh pr list \
        --repo "$REPO" \
        --state merged \
        --limit 100 \
        --json number,mergedAt \
        --jq 'sort_by(.mergedAt) | last | .number'
)"

echo "Derniere PR mergee : #$LATEST_PR"

if [ "$LATEST_PR" != "$PRNUM" ]; then
    echo "NOGO [!!] Une PR plus recente est deja mergee : #$LATEST_PR"
    echo "On ne doit plus publier Alpha 2.42 comme derniere version."
    exit 1
fi

echo "GO [OK] Alpha 2.42 correspond a la derniere PR mergee."
echo

echo "=== 3. SYNCHRONISATION LOCALE DE MAIN ==="

git -C "$SRC" fetch origin main

MAIN_SHA="$(
    git -C "$SRC" rev-parse origin/main
)"

echo "Main actuel : $MAIN_SHA"

if ! git -C "$SRC" merge-base \
    --is-ancestor \
    "$MERGE_SHA" \
    origin/main
then
    echo "NOGO [!!] Le merge PR42 n'est pas dans main."
    exit 1
fi

echo "GO [OK] PR42 presente dans main."
echo

echo "=== 4. VERSION GITHUB ==="

GITHUB_VERSION="$(
    git -C "$SRC" \
        show \
        origin/main:opt/pincabos/config/version.json \
    | python3 -c '
import json
import sys
print(json.load(sys.stdin).get("version",""))
'
)"

echo "Version GitHub : $GITHUB_VERSION"

if [ "$GITHUB_VERSION" != "$DISPLAY" ]; then
    echo "NOGO [!!] GitHub n'affiche pas $DISPLAY."
    exit 1
fi

echo "GO [OK] GitHub = $DISPLAY."
echo

echo "=== 5. ATTENTE DE LA RELEASE AUTOMATIQUE ==="

FOUND=0

for N in $(seq 1 36); do

    if gh release view \
        "$TAG" \
        --repo "$REPO" \
        >/dev/null 2>&1
    then
        FOUND=1
        break
    fi

    printf "Attente Release... %02d/36\r" "$N"
    sleep 5
done

echo

if [ "$FOUND" != "1" ]; then

    echo
    echo "INFO [--] Release pas encore detectee."
    echo
    echo "=== WORKFLOW RELEASE ==="

    gh run list \
        --repo "$REPO" \
        --workflow pincabos-release-v4.yml \
        --limit 8 \
        --json databaseId,status,conclusion,event,createdAt,displayTitle \
        --jq '.[] |
          "RUN=\(.databaseId) STATUS=\(.status) CONCLUSION=\(.conclusion) EVENT=\(.event) DATE=\(.createdAt) TITLE=\(.displayTitle)"'

    RUN_ID="$(
        gh run list \
            --repo "$REPO" \
            --workflow pincabos-release-v4.yml \
            --limit 1 \
            --json databaseId \
            --jq '.[0].databaseId // empty'
    )"

    RUN_STATUS="$(
        gh run list \
            --repo "$REPO" \
            --workflow pincabos-release-v4.yml \
            --limit 1 \
            --json status \
            --jq '.[0].status // empty'
    )"

    RUN_CONCLUSION="$(
        gh run list \
            --repo "$REPO" \
            --workflow pincabos-release-v4.yml \
            --limit 1 \
            --json conclusion \
            --jq '.[0].conclusion // empty'
    )"

    echo
    echo "Dernier run : $RUN_ID"
    echo "Status      : $RUN_STATUS"
    echo "Conclusion  : $RUN_CONCLUSION"
    echo

    if [ "$RUN_STATUS" = "in_progress" ] || \
       [ "$RUN_STATUS" = "queued" ]
    then

        echo "INFO [--] Workflow toujours actif."

        for N in $(seq 1 36); do

            if gh release view \
                "$TAG" \
                --repo "$REPO" \
                >/dev/null 2>&1
            then
                FOUND=1
                break
            fi

            printf "Workflow actif... %02d/36\r" "$N"
            sleep 5
        done

        echo

    elif [ "$RUN_CONCLUSION" = "failure" ]; then

        echo "NOGO [!!] Workflow Release en echec."
        echo
        echo "=== LOGS ECHEC ==="

        gh run view \
            "$RUN_ID" \
            --repo "$REPO" \
            --log-failed || true

        exit 1

    elif [ -z "$RUN_ID" ]; then

        echo "INFO [--] Aucun workflow automatique detecte."
        echo "Declenchement manuel securise..."

        gh workflow run \
            pincabos-release-v4.yml \
            --repo "$REPO" \
            -f pr_number="$PRNUM" \
            -f channel=beta

        echo "GO [OK] Workflow declenche."

        for N in $(seq 1 48); do

            if gh release view \
                "$TAG" \
                --repo "$REPO" \
                >/dev/null 2>&1
            then
                FOUND=1
                break
            fi

            printf "Attente Release... %02d/48\r" "$N"
            sleep 5
        done

        echo
    fi
fi

if [ "$FOUND" != "1" ]; then
    echo "NOGO [!!] Release $TAG non disponible."
    exit 1
fi

echo "GO [OK] Release detectee : $TAG"
echo

echo "=== 6. AUDIT DE LA RELEASE ==="

gh release view \
    "$TAG" \
    --repo "$REPO" \
    --json tagName,name,isPrerelease,url,assets \
    --jq '
      "Tag       : \(.tagName)",
      "Nom       : \(.name)",
      "Prerelease: \(.isPrerelease)",
      "URL       : \(.url)",
      "Assets:",
      (.assets[].name)
    '

ASSET_COUNT="$(
    gh release view \
        "$TAG" \
        --repo "$REPO" \
        --json assets \
        --jq '
        [
          .assets[].name
          | select(
              . == "audit.sha256"
              or . == "files.list"
              or . == "remove.list"
              or . == "release.json"
              or . == "pincabos-update.tar.zst"
          )
        ] | length
        '
)"

if [ "$ASSET_COUNT" != "5" ]; then
    echo "NOGO [!!] La Release ne contient pas les 5 assets requis."
    exit 1
fi

echo "GO [OK] 5 assets officiels."
echo

echo "=== 7. TELECHARGEMENT + SHA256 ==="

RELCHK="$WORK/release-check-42"

rm -rf "$RELCHK"
mkdir -p "$RELCHK"

gh release download \
    "$TAG" \
    --repo "$REPO" \
    --dir "$RELCHK"

cd "$RELCHK"

sha256sum -c audit.sha256

echo
echo "=== RELEASE.JSON ==="

cat release.json

echo

python3 - "$TAG" "$DISPLAY" <<'PY'
import json
import sys
from pathlib import Path

tag = sys.argv[1]
display = sys.argv[2]

data = json.loads(
    Path("release.json").read_text(
        encoding="utf-8"
    )
)

assert data["schema"] == 4
assert data["version"] == tag
assert data["display_version"] == display
assert data["channel"] == "beta"
assert data["repository"] == "KarotsSugarpie/PinCabOS"

count = int(
    data.get(
        "file_count",
        0
    )
)

if count < 400:
    raise SystemExit(
        f"NOGO [!!] Full Release trop petite : {count}"
    )

print(
    f"GO [OK] release.json valide : "
    f"{count} fichiers."
)

print(
    "Reboot required:",
    data.get(
        "reboot_required"
    )
)
PY

echo

echo "=== 8. BOOTSTRAP UNIQUE DU NOUVEAU MOTEUR ==="
echo "Le Full Release doit etre installe avec le nouveau moteur"
echo "afin de conserver les UID/GID des fichiers existants."
echo

cd "$SRC"

git fetch origin main

BOOT_ENGINE="$WORK/pincabos_updates-main-42.py"

git show \
    origin/main:opt/pincabos/update/pincabos_updates.py \
    > "$BOOT_ENGINE"

grep -q \
    'def local_tag():' \
    "$BOOT_ENGINE"

grep -q \
    'owners.json' \
    "$BOOT_ENGINE"

grep -q \
    'reboot_required' \
    "$BOOT_ENGINE"

PYTHONPYCACHEPREFIX="$WORK/bootstrap-pycache" \
python3 -m py_compile \
    "$BOOT_ENGINE"

LIVE_ENGINE="/opt/pincabos/update/pincabos_updates.py"
BOOT_BACKUP="/opt/pincabos/backups/updates-bootstrap/$(date +%Y%m%d-%H%M%S)"

sudo mkdir -p "$BOOT_BACKUP"

sudo cp -a \
    "$LIVE_ENGINE" \
    "$BOOT_BACKUP/pincabos_updates.py.before-alpha242"

sudo install \
    -o root \
    -g root \
    -m 0755 \
    "$BOOT_ENGINE" \
    "$LIVE_ENGINE"

echo "GO [OK] Nouveau moteur bootstrappe."
echo "Backup : $BOOT_BACKUP"
echo

echo "=== 9. VALIDATION MOTEUR LIVE ==="

PYTHONPYCACHEPREFIX="$WORK/live-pycache" \
python3 -m py_compile \
    "$LIVE_ENGINE"

grep -q \
    'def local_tag():' \
    "$LIVE_ENGINE"

grep -q \
    'owners.json' \
    "$LIVE_ENGINE"

echo "GO [OK] Nouveau moteur actif."
echo

echo "=== 10. CHECK AVANT UPDATE ==="

sudo /usr/local/sbin/getpcos status

echo

sudo /usr/local/sbin/getpcos check

echo

echo "=== 11. UPDATE REEL ALPHA 2.42 ==="

sudo /usr/local/sbin/getpcos update

echo
echo "=== 12. STATUS APRES UPDATE ==="

sudo /usr/local/sbin/getpcos status

echo

echo "=== 13. VALIDATION STATE + VERSION ==="

sudo python3 - "$TAG" "$DISPLAY" <<'PY'
import json
import sys
from pathlib import Path

tag = sys.argv[1]
display = sys.argv[2]

state_path = Path(
    "/var/lib/pincabos/updates/state.json"
)

state = json.loads(
    state_path.read_text(
        encoding="utf-8"
    )
)

print(
    "installed_version :",
    state.get("installed_version")
)

print(
    "display_version   :",
    state.get("display_version")
)

print(
    "last_backup       :",
    state.get("last_backup")
)

print(
    "reboot_required   :",
    state.get("reboot_required")
)

if state.get("installed_version") != tag:
    raise SystemExit(
        "NOGO [!!] installed_version incorrect."
    )

if state.get("display_version") != display:
    raise SystemExit(
        "NOGO [!!] display_version incorrect."
    )

for path in [
    Path(
        "/opt/pincabos/config/version.json"
    ),
    Path(
        "/opt/pincabos/version.json"
    ),
]:
    if not path.exists():
        continue

    data = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    print(
        f"{path} : "
        f"{data.get('version')}"
    )

    if data.get("version") != display:
        raise SystemExit(
            f"NOGO [!!] Mauvaise version : {path}"
        )

print(
    "GO [OK] Alpha 2.42 synchronise partout."
)
PY

echo

echo "=== 14. SERVICES ==="

for SERVICE in \
    pincabos-webapp.service \
    pincabos-vpinfe.service
do

    VALUE="$(
        systemctl is-active \
            "$SERVICE" \
            2>/dev/null || true
    )"

    echo "$SERVICE : $VALUE"

    if [ "$VALUE" != "active" ]; then
        echo "NOGO [!!] Service non actif : $SERVICE"
        exit 1
    fi
done

echo "GO [OK] Services actifs."
echo

echo "=== 15. RUNNER WEB + SUDOERS ==="

ls -l \
    /usr/local/sbin/pincabos-update-web-runner \
    /etc/sudoers.d/pincabos-updates-web

sudo visudo \
    -cf \
    /etc/sudoers.d/pincabos-updates-web

if sudo grep -Eq \
    '/bin/bash|/usr/bin/bash' \
    /etc/sudoers.d/pincabos-updates-web
then
    echo "NOGO [!!] Sudoers contient encore bash."
    exit 1
fi

echo "GO [OK] Sudoers minimal."
echo

echo "=== 16. TEST FULL WIDTH LIVE ==="

curl -sS \
    http://127.0.0.1/static/pincabos-appearance-dashboard-menu-v2.css \
    -o "$WORK/fullwidth-alpha242.css"

grep -q \
    'PINCABOS_FULLWIDTH_GLOBAL_V1_BEGIN' \
    "$WORK/fullwidth-alpha242.css"

grep -q \
    'max-width: none' \
    "$WORK/fullwidth-alpha242.css"

TOOLS_HTTP="$(
    curl -sS \
        -o "$WORK/tools-alpha242.html" \
        -w '%{http_code}' \
        http://127.0.0.1/tools
)"

UPDATES_HTTP="$(
    curl -sS \
        -o "$WORK/updates-alpha242.html" \
        -w '%{http_code}' \
        http://127.0.0.1/tools/updates
)"

echo "/tools         : HTTP $TOOLS_HTTP"
echo "/tools/updates : HTTP $UPDATES_HTTP"

[ "$TOOLS_HTTP" = "200" ] || exit 1
[ "$UPDATES_HTTP" = "200" ] || exit 1

python3 - <<'PY'
from pathlib import Path
import re

html = Path(
    "/home/pinball/"
    "pincabos-fullwidth-auto-release-20260822-093232/"
    "tools-alpha242.html"
).read_text(
    encoding="utf-8",
    errors="replace"
)

m = re.search(
    r'<section id="pincabos-tools-system-family".*?'
    r'<div class="pco-tools-card-list">(.*?)'
    r'</a>',
    html,
    flags=re.S
)

if not m:
    raise SystemExit(
        "NOGO [!!] Liste Outils introuvable."
    )

first = re.search(
    r'<a class="tool-card" href="([^"]+)"',
    m.group(1),
    flags=re.S
)

if not first:
    raise SystemExit(
        "NOGO [!!] Premiere carte introuvable."
    )

print(
    "Premiere carte:",
    first.group(1)
)

if first.group(1) != "/tools/updates":
    raise SystemExit(
        "NOGO [!!] Updates n'est plus la premiere carte."
    )

print(
    "GO [OK] Updates est la premiere carte."
)
PY

echo "GO [OK] Full Width global charge."
echo

echo "=== 17. TEST BOUTON WEB - VERIFIER ==="

rm -f \
    /tmp/pincabos-update-web-state.json \
    /tmp/pincabos-update-web.log

curl -sS \
    -X POST \
    -H 'Content-Type: application/json' \
    -d '{"action":"check","reboot_after":false}' \
    http://127.0.0.1/api/updates/run

echo
echo

STATE_JSON=""

for N in $(seq 1 60); do

    sleep 1

    STATE_JSON="$(
        curl -sS \
            http://127.0.0.1/api/updates/state
    )"

    RUNNING="$(
        printf '%s' "$STATE_JSON" \
        | python3 -c '
import json
import sys

data=json.load(sys.stdin)

print(
    "1"
    if data.get("running")
    else "0"
)
'
    )"

    [ "$RUNNING" = "0" ] && break
done

printf '%s\n' "$STATE_JSON" \
    | python3 -m json.tool

echo
echo "--- LOG CHECK ---"

cat \
    /tmp/pincabos-update-web.log \
    || true

echo

STATUS="$(
    printf '%s' "$STATE_JSON" \
    | python3 -c '
import json
import sys

print(
    json.load(sys.stdin)
    .get("status","")
)
'
)"

if [ "$STATUS" != "success" ]; then
    echo "NOGO [!!] Bouton Verifier en echec."
    exit 1
fi

echo "GO [OK] Bouton Verifier fonctionne."
echo

echo "=== 18. TEST BOUTON WEB - INSTALLER ==="

curl -sS \
    -X POST \
    -H 'Content-Type: application/json' \
    -d '{"action":"update","reboot_after":false}' \
    http://127.0.0.1/api/updates/run

echo
echo

STATE_JSON=""

for N in $(seq 1 60); do

    sleep 1

    STATE_JSON="$(
        curl -sS \
            http://127.0.0.1/api/updates/state
    )"

    RUNNING="$(
        printf '%s' "$STATE_JSON" \
        | python3 -c '
import json
import sys

data=json.load(sys.stdin)

print(
    "1"
    if data.get("running")
    else "0"
)
'
    )"

    [ "$RUNNING" = "0" ] && break
done

printf '%s\n' "$STATE_JSON" \
    | python3 -m json.tool

echo
echo "--- LOG INSTALLER ---"

cat \
    /tmp/pincabos-update-web.log \
    || true

echo

STATUS="$(
    printf '%s' "$STATE_JSON" \
    | python3 -c '
import json
import sys

print(
    json.load(sys.stdin)
    .get("status","")
)
'
)"

if [ "$STATUS" != "success" ]; then
    echo "NOGO [!!] Bouton Installer en echec."
    exit 1
fi

grep -q \
    'Already up to date' \
    /tmp/pincabos-update-web.log || {
        echo "NOGO [!!] Already up to date absent."
        exit 1
    }

echo "GO [OK] Bouton Installer fonctionne."
echo

echo "==============================================================="
echo " GO [OK] ALPHA 2.42 COMPLETEMENT VALIDEE"
echo "==============================================================="
echo
echo "PR                : #42"
echo "Version           : Alpha 2.42"
echo "Release           : $TAG"
echo "Full Release      : valide"
echo "Update reel       : valide"
echo "Full Width        : actif"
echo "Updates 1ere carte: valide"
echo "Bouton Verifier   : valide"
echo "Bouton Installer  : valide"
echo "Reboot requis     : NON"
echo "Reboot effectue   : NON"
echo
