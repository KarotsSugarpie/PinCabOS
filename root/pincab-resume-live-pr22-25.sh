#!/usr/bin/env bash
set -Eeuo pipefail

clear

echo "==============================================================="
echo " PINCABOS — REPRISE DEPLOIEMENT LIVE PR22 -> PR25"
echo " STAGING DEJA VALIDE"
echo "==============================================================="
echo

REPO="/opt/pincabos/tmp/pr-integration"
BRANCH="pincabos-pr-integration"
EXPECTED_HEAD="8ee36d43b2db828285db416a00c549b6cee0c983"

BACKUP="/opt/pincabos/backups/full-pr22-25-20260818-132557"
BACKUP_TAR="$BACKUP/live-before-pr22-25.tar"

fail() {
    echo
    echo "==============================================================="
    echo " NOGO [ERREUR] $*"
    echo "==============================================================="
    exit 1
}

ok() {
    echo "GO [OK] $*"
}

echo "=== 1. VALIDATION DU STAGING ==="

[ "$(id -u)" -eq 0 ] || fail "Execution root requise."
[ -d "$REPO/.git" ] || fail "Depot absent."
[ -f "$BACKUP_TAR" ] || fail "Backup LIVE absent."

cd "$REPO"

CURRENT_BRANCH="$(git branch --show-current)"
CURRENT_HEAD="$(git rev-parse HEAD)"

echo "Branche : $CURRENT_BRANCH"
echo "HEAD    : $CURRENT_HEAD"
echo "Backup  : $BACKUP_TAR"

[ "$CURRENT_BRANCH" = "$BRANCH" ] ||
    fail "Mauvaise branche."

[ "$CURRENT_HEAD" = "$EXPECTED_HEAD" ] ||
    fail "HEAD inattendue."

[ -z "$(git status --porcelain)" ] ||
    fail "Working tree Git non propre."

ok "Staging PR1 -> PR25 valide."

echo
echo "=== 2. VERIFICATION QU'AUCUNE NOUVELLE PR N'EST APPARUE ==="

MAX_PR="$(
    git ls-remote origin 'refs/pull/*/head' 2>/dev/null |
    sed -n 's#.*refs/pull/\([0-9][0-9]*\)/head#\1#p' |
    sort -n |
    tail -n1
)"

echo "Derniere PR detectee : #${MAX_PR:-inconnue}"

if [ -n "${MAX_PR:-}" ] && [ "$MAX_PR" -gt 25 ]; then
    fail "Une PR #$MAX_PR existe maintenant. Arret avant deploy live."
fi

ok "PR25 est toujours la derniere PR detectee."

echo
echo "=== 3. VALIDATION DES MARQUEURS SOURCE ==="

grep -q 'PINCABOS_SAMPLE_TABLES_UI_V1' \
    opt/pincabos/web/tools.py ||
    fail "PR22 absente."

grep -q 'PINCABOS_WHEEL_SMALL_LIBRARY_V1' \
    home/pinball/.config/vpinfe/themes/Trinidad/theme.js ||
    fail "PR23 absente."

grep -q 'PINCABOS_PHANTOM_OUTPUT_GUARD_V1' \
    opt/pincabos/tools/pincabos-screen-lightdm-safe.sh ||
    fail "PR24 absente."

grep -q 'PINCABOS_GRAPHICAL_VT_DYNAMIC_V1' \
    usr/local/sbin/pincabos-final-graphical-guard.sh ||
    fail "PR25 absente."

ok "PR22."
ok "PR23."
ok "PR24."
ok "PR25."

echo
echo "=== 4. FONCTION DE DEPLOIEMENT CORRIGEE ==="

deploy_file() {
    local REL="$1"
    local SRC="$REPO/$REL"
    local DST="/$REL"
    local DIR
    local DST_UID=""
    local DST_GID=""
    local DST_MODE=""
    local TMP

    [ -f "$SRC" ] ||
        fail "Source absente : $SRC"

    DIR="$(dirname "$DST")"
    mkdir -p "$DIR"

    if [ -e "$DST" ]; then
        DST_UID="$(stat -c '%u' "$DST")"
        DST_GID="$(stat -c '%g' "$DST")"
        DST_MODE="$(stat -c '%a' "$DST")"
    fi

    TMP="$DIR/.pco-update-$(basename "$DST").$$"

    cp -a "$SRC" "$TMP"
    mv -f "$TMP" "$DST"

    if [ -n "$DST_UID" ]; then
        chown "$DST_UID:$DST_GID" "$DST"
        chmod "$DST_MODE" "$DST"
    fi

    echo "GO [DEPLOY] $DST"
}

ok "Fonction deploy_file corrigee."

echo
echo "==============================================================="
echo " 5. DEPLOIEMENT PR22"
echo "==============================================================="

deploy_file "usr/local/sbin/pincabos-sample-tables"
chown root:root /usr/local/sbin/pincabos-sample-tables
chmod 0755 /usr/local/sbin/pincabos-sample-tables

deploy_file "etc/sudoers.d/pincabos-sample-tables"
chown root:root /etc/sudoers.d/pincabos-sample-tables
chmod 0440 /etc/sudoers.d/pincabos-sample-tables

deploy_file "etc/systemd/system/pincabos-sample-tables.service"
deploy_file "etc/systemd/system/pincabos-sample-tables.path"

chown root:root \
    /etc/systemd/system/pincabos-sample-tables.service \
    /etc/systemd/system/pincabos-sample-tables.path

chmod 0644 \
    /etc/systemd/system/pincabos-sample-tables.service \
    /etc/systemd/system/pincabos-sample-tables.path

deploy_file "opt/pincabos/web/tools.py"

echo
echo "--- MEDIAS DES TABLES DE TEST ---"

for KEY in example nudge
do
    mkdir -p "/opt/pincabos/assets/sample-tables/$KEY"

    for PNG in bg.png dmd.png table.png wheel.png
    do
        SRC="$REPO/opt/pincabos/assets/sample-tables/$KEY/$PNG"
        DST="/opt/pincabos/assets/sample-tables/$KEY/$PNG"

        [ -f "$SRC" ] ||
            fail "Media manquant : $SRC"

        install \
            -o root \
            -g root \
            -m 0644 \
            "$SRC" \
            "$DST"

        echo "GO [DEPLOY] $DST"
    done
done

ok "PR22 code live."

echo
echo "=== 6. CONFIG VPinFE PERSONNELLE ==="

echo "GO [PRESERVE] /home/pinball/.config/vpinfe/vpinfe.ini"
echo "GO [PRESERVE] /home/pinball/.config/vpinfe/collections.ini"

echo
echo "Les defaults PR22 restent dans Git/ISO,"
echo "mais les donnees du cab existant ne sont pas remplacees."

echo
echo "==============================================================="
echo " 7. DEPLOIEMENT PR23"
echo "==============================================================="

deploy_file \
    "home/pinball/.config/vpinfe/themes/Trinidad/theme.js"

chown pinball:pinball \
    /home/pinball/.config/vpinfe/themes/Trinidad/theme.js

ok "PR23 live."

echo
echo "==============================================================="
echo " 8. DEPLOIEMENT PR24"
echo "==============================================================="

deploy_file \
    "opt/pincabos/tools/pincabos-screen-lightdm-safe.sh"

chmod 0755 \
    /opt/pincabos/tools/pincabos-screen-lightdm-safe.sh

ok "PR24 live."

echo
echo "==============================================================="
echo " 9. DEPLOIEMENT PR25"
echo "==============================================================="

mkdir -p \
    /etc/lightdm/lightdm.conf.d \
    /etc/systemd/system/lightdm.service.d

deploy_file \
    "etc/lightdm/lightdm.conf.d/60-pincabos-vt.conf"

deploy_file \
    "etc/systemd/system/lightdm.service.d/20-pincabos-vt1.conf"

deploy_file \
    "etc/systemd/system/pincabos-switch-graphical-vt.service"

deploy_file \
    "usr/local/sbin/pincabos-final-graphical-guard.sh"

chmod 0755 \
    /usr/local/sbin/pincabos-final-graphical-guard.sh

chown root:root \
    /etc/lightdm/lightdm.conf.d/60-pincabos-vt.conf \
    /etc/systemd/system/lightdm.service.d/20-pincabos-vt1.conf \
    /etc/systemd/system/pincabos-switch-graphical-vt.service \
    /usr/local/sbin/pincabos-final-graphical-guard.sh

ok "PR25 fichiers live."

echo
echo "=== 10. DEPLOIEMENT ISO.SH FINAL ==="

deploy_file "opt/pincabos/script/iso.sh"

chmod 0755 /opt/pincabos/script/iso.sh

ok "iso.sh PR22+PR25 live."

echo
echo "=== 11. CONFIGURATION GRUB PR25 ==="

python3 <<'PY'
from pathlib import Path
import re

p = Path("/etc/default/grub")
text = p.read_text()

line = (
    'GRUB_CMDLINE_LINUX_DEFAULT="quiet splash '
    'loglevel=3 rd.udev.log_level=3 '
    'systemd.show_status=false '
    'rd.systemd.show_status=false '
    'vt.global_cursor_default=0"'
)

if re.search(r'^GRUB_CMDLINE_LINUX_DEFAULT=.*$', text, re.M):
    text = re.sub(
        r'^GRUB_CMDLINE_LINUX_DEFAULT=.*$',
        line,
        text,
        count=1,
        flags=re.M,
    )
else:
    text += "\n" + line + "\n"

p.write_text(text)
PY

grep '^GRUB_CMDLINE_LINUX_DEFAULT=' /etc/default/grub

ok "GRUB PR25 configure."

echo
echo "==============================================================="
echo " 12. VALIDATION LIVE AVANT SERVICES"
echo "==============================================================="

bash -n /usr/local/sbin/pincabos-sample-tables ||
    fail "sample-tables invalide"

bash -n /opt/pincabos/tools/pincabos-screen-lightdm-safe.sh ||
    fail "screen-lightdm-safe invalide"

bash -n /usr/local/sbin/pincabos-final-graphical-guard.sh ||
    fail "graphical-guard invalide"

bash -n /opt/pincabos/script/iso.sh ||
    fail "iso.sh invalide"

python3 - <<'PY'
from pathlib import Path

p = Path("/opt/pincabos/web/tools.py")
compile(p.read_text(), str(p), "exec")
print("GO [OK] tools.py syntaxe")
PY

visudo -cf /etc/sudoers.d/pincabos-sample-tables ||
    fail "sudoers invalide"

if command -v node >/dev/null 2>&1; then
    node --check \
        /home/pinball/.config/vpinfe/themes/Trinidad/theme.js ||
        fail "theme.js invalide"
fi

ok "Validation syntaxe live."

echo
echo "=== 13. VALIDATION MARQUEURS LIVE ==="

grep -q 'PINCABOS_SAMPLE_TABLES_UI_V1' \
    /opt/pincabos/web/tools.py &&
    echo "GO [PR22] Sample Tables"

grep -q 'PINCABOS_WHEEL_SMALL_LIBRARY_V1' \
    /home/pinball/.config/vpinfe/themes/Trinidad/theme.js &&
    echo "GO [PR23] Wheel"

grep -q 'PINCABOS_PHANTOM_OUTPUT_GUARD_V1' \
    /opt/pincabos/tools/pincabos-screen-lightdm-safe.sh &&
    echo "GO [PR24] EDID Guard"

grep -q 'PINCABOS_GRAPHICAL_VT_DYNAMIC_V1' \
    /usr/local/sbin/pincabos-final-graphical-guard.sh &&
    echo "GO [PR25] Dynamic VT"

echo
echo "==============================================================="
echo " 14. SYSTEMD"
echo "==============================================================="

systemctl daemon-reload

systemctl enable pincabos-sample-tables.service
systemctl enable pincabos-sample-tables.path

systemctl start pincabos-sample-tables.service
systemctl start pincabos-sample-tables.path

ok "Sample Tables systemd configure."

echo
echo "--- SAMPLE TABLES STATUS ---"

/usr/local/sbin/pincabos-sample-tables status || true

echo
echo "=== 15. UPDATE GRUB ==="

command -v update-grub >/dev/null ||
    fail "update-grub absent"

update-grub

ok "grub.cfg regenere."

echo
echo "=== 16. RESTART WEBAPP ==="

systemctl restart pincabos-webapp.service

sleep 2

if systemctl is-active --quiet pincabos-webapp.service; then
    ok "WebApp active."
else
    systemctl --no-pager -l status pincabos-webapp.service || true
    fail "WebApp inactive."
fi

echo
echo "=== 17. TEST HTTP WEBAPP ==="

if command -v curl >/dev/null 2>&1; then
    HTTP="$(
        curl \
            -s \
            -o /dev/null \
            -w '%{http_code}' \
            --max-time 5 \
            http://127.0.0.1/
    )"

    echo "HTTP / : $HTTP"

    case "$HTTP" in
        200|301|302)
            ok "WebApp HTTP repond."
            ;;
        *)
            fail "WebApp HTTP retourne $HTTP"
            ;;
    esac
fi

echo
echo "=== 18. RESTART VPINFE ==="

systemctl restart pincabos-vpinfe.service

sleep 3

if systemctl is-active --quiet pincabos-vpinfe.service; then
    ok "VPinFE actif."
else
    systemctl --no-pager -l status pincabos-vpinfe.service || true
    fail "VPinFE inactif."
fi

echo
echo "==============================================================="
echo " 19. ETAT SERVICES"
echo "==============================================================="

for SERVICE in \
    pincabos-webapp.service \
    pincabos-vpinfe.service \
    pincabos-sample-tables.service \
    pincabos-sample-tables.path \
    pincabos-final-graphical-guard.service \
    lightdm.service
do
    printf "%-45s : " "$SERVICE"
    systemctl is-active "$SERVICE" 2>/dev/null || true
done

echo
echo "=== 20. ETAT SAMPLE TABLES ==="

/usr/local/sbin/pincabos-sample-tables status || true

echo
echo "=== 21. CONFIG LIGHTDM PR25 ==="

grep -R \
    -E 'minimum-vt|Conflicts=getty@tty1' \
    /etc/lightdm/lightdm.conf.d/60-pincabos-vt.conf \
    /etc/systemd/system/lightdm.service.d/20-pincabos-vt1.conf \
    || true

echo
echo "=== 22. ETAT GIT FINAL ==="

cd "$REPO"

echo "Branche : $(git branch --show-current)"
echo "HEAD    : $(git rev-parse HEAD)"

git status --short

if [ -z "$(git status --porcelain)" ]; then
    ok "Git propre."
else
    fail "Git non propre."
fi

echo
echo "=== 23. RAPPORT ==="

cat > "$BACKUP/UPDATE-SUMMARY.txt" <<EOF
PINCABOS FULL PR UPDATE

Date:
$(date -Is)

Git Branch:
$(git branch --show-current)

Git HEAD:
$(git rev-parse HEAD)

PR22:
LIVE OK

PR23:
LIVE OK

PR24:
LIVE OK

PR25:
LIVE OK

Live backup:
$BACKUP_TAR

VPinFE personal config:
PRESERVED

GitHub:
NOT PUSHED

Reboot:
REQUIRED TO VALIDATE PR25
EOF

echo
echo "==============================================================="
echo " GO [OK] PINCABOS LIVE FULL UPDATE PR1 -> PR25"
echo "==============================================================="
echo
echo "Git staging : GO"
echo "PR22 live   : GO"
echo "PR23 live   : GO"
echo "PR24 live   : GO"
echo "PR25 live   : GO"
echo
echo "Backup :"
echo "$BACKUP_TAR"
echo
echo "GITHUB : PAS ENCORE PUSH"
echo "REBOOT : PAS ENCORE"
echo
echo "==============================================================="
