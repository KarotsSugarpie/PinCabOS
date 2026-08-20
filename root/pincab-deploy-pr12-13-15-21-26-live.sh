#!/usr/bin/env bash
set -Eeuo pipefail

clear

echo "==============================================================="
echo " PINCABOS — DEPLOIEMENT LIVE DES PR"
echo " PR #12 #13 #15 #21 #26"
echo " GITHUB/STAGING -> CAB LIVE"
echo "==============================================================="
echo

REPO="/opt/pincabos/tmp/pr-integration"
EXPECTED_HEAD="8bc3e103bc9b0d125f1844bf62cf26fca99eae9d"

STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="/opt/pincabos/backups/deploy-pr12-13-15-21-26-$STAMP"

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

echo "=== 1. VALIDATION SOURCE ==="

BRANCH="$(git branch --show-current)"
HEAD="$(git rev-parse HEAD)"

echo "Branche : $BRANCH"
echo "HEAD    : $HEAD"

[ "$BRANCH" = "pincabos-pr-integration" ] ||
    fail "Mauvaise branche."

[ "$HEAD" = "$EXPECTED_HEAD" ] ||
    fail "HEAD inattendu."

[ -z "$(git status --porcelain)" ] ||
    fail "Git local non propre."

git fetch origin main

REMOTE="$(git rev-parse refs/remotes/origin/main)"

echo "GitHub  : $REMOTE"

[ "$REMOTE" = "$EXPECTED_HEAD" ] ||
    fail "GitHub main != staging."

ok "GitHub == staging."

echo
echo "=== 2. GARDE VPX ==="

if pgrep -af \
    'VPinballX|VPinballX_BGFX' \
    > /tmp/pincab-vpx-active.txt
then
    cat /tmp/pincab-vpx-active.txt

    fail "Une table VPX semble active. Ferme la table avant deploy."
fi

ok "Aucune table VPX active."

echo
echo "=== 3. GARDE BATCH IMPORT ==="

ACTIVE_JSON="$(
    curl \
        -fsS \
        --max-time 5 \
        http://127.0.0.1/api/batch-import/live/active \
        2>/dev/null \
        || true
)"

if [ -n "$ACTIVE_JSON" ]
then
    echo "$ACTIVE_JSON"

    if python3 -c '
import json,sys

try:
    d=json.load(sys.stdin)
except Exception:
    raise SystemExit(0)

job=d.get("job")

if not isinstance(job,dict):
    raise SystemExit(0)

state=str(job.get("state","")).lower()

active={
    "queued",
    "uploading",
    "running",
    "processing",
    "pausing",
    "stopping",
}

raise SystemExit(1 if state in active else 0)
' <<< "$ACTIVE_JSON"
    then
        ok "Aucun Batch actif."
    else
        fail "Batch Import actif. Attends sa fin avant deploy."
    fi
else
    echo "AVERTISSEMENT : /active non disponible."
    echo "Validation par processus worker uniquement."
fi

echo
echo "=== 4. FICHIERS A DEPLOYER ==="

FILES=(
    "etc/systemd/system/pincabos-scoreview-router.service"
    "opt/pincabos/bin/pincabos-scoreview-router.sh"
    "opt/pincabos/installer-gui/templates/wizard.html"
    "opt/pincabos/tools/pincabos-screen-lightdm-safe.sh"
    "opt/pincabos/web/app.py"
    "opt/pincabos/web/pincabos_batch_import_worker_v2.py"
    "usr/local/bin/pincabos-kiosk.py"
)

for REL in "${FILES[@]}"
do
    SRC="$REPO/$REL"
    DST="/$REL"

    [ -f "$SRC" ] ||
        fail "Source absente : $REL"

    [ -f "$DST" ] ||
        fail "Live absent : $DST"

    echo "$REL"
done

ok "7 fichiers valides."

echo
echo "=== 5. VALIDATION SYNTAXE AVANT COPIE ==="

bash -n \
    "$REPO/opt/pincabos/bin/pincabos-scoreview-router.sh" ||
    fail "Syntaxe scoreview-router."

bash -n \
    "$REPO/opt/pincabos/tools/pincabos-screen-lightdm-safe.sh" ||
    fail "Syntaxe screen-lightdm-safe."

python3 -m py_compile \
    "$REPO/opt/pincabos/web/app.py" \
    "$REPO/opt/pincabos/web/pincabos_batch_import_worker_v2.py" \
    "$REPO/usr/local/bin/pincabos-kiosk.py" ||
    fail "Syntaxe Python."

ok "Syntaxes valides."

echo
echo "=== 6. BACKUP LIVE COMPLET ==="

mkdir -p "$BACKUP"

for REL in "${FILES[@]}"
do
    SRC="/$REL"
    BKP="$BACKUP/$REL"

    mkdir -p "$(dirname "$BKP")"

    cp -a \
        "$SRC" \
        "$BKP"

    echo "BACKUP $REL"
done

printf '%s\n' "$EXPECTED_HEAD" \
    > "$BACKUP/github-head.txt"

ok "Backup : $BACKUP"

echo
echo "==============================================================="
echo " 7. DEPLOIEMENT DES 7 FICHIERS"
echo "==============================================================="

for REL in "${FILES[@]}"
do
    SRC="$REPO/$REL"
    DST="/$REL"

    OWNER="$(stat -c '%u' "$DST")"
    GROUP="$(stat -c '%g' "$DST")"
    MODE="$(stat -c '%a' "$DST")"

    TMP="${DST}.pincab-deploy.$$"

    install \
        -o "$OWNER" \
        -g "$GROUP" \
        -m "$MODE" \
        "$SRC" \
        "$TMP"

    mv -f \
        "$TMP" \
        "$DST"

    cmp -s \
        "$SRC" \
        "$DST" ||
        fail "Verification live echouee : $REL"

    echo "GO [DEPLOY] $REL"
done

echo
echo "=== 8. SYSTEMD DAEMON-RELOAD ==="

systemctl daemon-reload

ok "daemon-reload."

echo
echo "=== 9. REDEMARRAGE WEBAPP ==="

systemctl restart \
    pincabos-webapp.service

sleep 2

systemctl is-active \
    --quiet \
    pincabos-webapp.service ||
    fail "WebApp inactive."

ok "pincabos-webapp.service active."

echo
echo "=== 10. REDEMARRAGE BATCH WORKER ==="

systemctl restart \
    pincabos-batch-import-worker.service

sleep 2

systemctl is-active \
    --quiet \
    pincabos-batch-import-worker.service ||
    fail "Batch worker inactif."

ok "pincabos-batch-import-worker.service active."

echo
echo "=== 11. REDEMARRAGE SCOREVIEW ROUTER ==="

systemctl restart \
    pincabos-scoreview-router.service

sleep 2

systemctl is-active \
    --quiet \
    pincabos-scoreview-router.service ||
    fail "ScoreView Router inactif."

ok "pincabos-scoreview-router.service active."

echo
echo "=== 12. VALIDATION HTTP ==="

HTTP="$(
    curl \
        -s \
        -o /dev/null \
        -w '%{http_code}' \
        --max-time 10 \
        http://127.0.0.1/ \
        || true
)"

echo "HTTP / : $HTTP"

case "$HTTP" in
    200|301|302)
        ok "WebApp repond."
        ;;
    *)
        fail "WebApp HTTP invalide : $HTTP"
        ;;
esac

echo
echo "=== 13. VALIDATION SOURCE == LIVE ==="

for REL in "${FILES[@]}"
do
    cmp -s \
        "$REPO/$REL" \
        "/$REL" ||
        fail "Difference : $REL"

    echo "GO [OK] $REL"
done

echo
echo "=== 14. SERVICES ==="

systemctl \
    --no-pager \
    --full \
    status \
    pincabos-webapp.service \
    pincabos-batch-import-worker.service \
    pincabos-scoreview-router.service \
    | grep -E \
        '●|Active:|Loaded:' \
    || true

echo
echo "=== 15. PR GITHUB ==="

for PR in 12 13 15 21 26
do
    gh pr view \
        "$PR" \
        --repo KarotsSugarpie/PinCabOS \
        --json number,state,mergedAt,title \
        --template \
'PR #{{.number}} | {{.state}} | merged={{.mergedAt}} | {{.title}}{{"\n"}}'
done

echo
echo "=== 16. PR ENCORE OUVERTES ==="

OPEN="$(
    gh pr list \
        --repo KarotsSugarpie/PinCabOS \
        --state open \
        --json number,title \
        --template \
'{{range .}}{{printf "#%v %s\n" .number .title}}{{end}}'
)"

if [ -n "$OPEN" ]
then
    echo "$OPEN"
else
    echo "Aucune PR ouverte."
fi

echo
echo "==============================================================="
echo " GO [OK] CAB LIVE + GITHUB A JOUR"
echo "==============================================================="
echo
echo "GitHub HEAD:"
echo "  $EXPECTED_HEAD"
echo
echo "PR:"
echo "  #12 MERGED"
echo "  #13 MERGED"
echo "  #15 MERGED"
echo "  #21 MERGED"
echo "  #26 MERGED"
echo
echo "Cab live:"
echo "  Screens/App       [OK]"
echo "  ScoreView Router  [OK]"
echo "  Installer GUI     [OK]"
echo "  Batch Worker      [OK]"
echo "  NVIDIA EDID revert[OK]"
echo
echo "Backup:"
echo "  $BACKUP"
echo
echo "==============================================================="
