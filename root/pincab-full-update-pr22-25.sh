#!/usr/bin/env bash
set -Eeuo pipefail

clear

echo "==============================================================="
echo " PINCABOS — FULL UPDATE PR22 -> PR25"
echo " PR24 INCLUSE"
echo " BACKUP + STAGING + LIVE + VALIDATION"
echo " AUCUN PUSH GITHUB"
echo "==============================================================="
echo

REPO="/opt/pincabos/tmp/pr-integration"
BASE_BRANCH="pincabos-pr-integration"

STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="/opt/pincabos/backups/full-pr22-25-$STAMP"
BACKUP_BRANCH="backup/full-before-pr22-25-$STAMP"
WORK_BRANCH="integration/full-pr22-25-$STAMP"

mkdir -p "$BACKUP"

fail() {
    echo
    echo "==============================================================="
    echo " NOGO [ERREUR] $*"
    echo " BACKUP : $BACKUP"
    echo "==============================================================="
    exit 1
}

ok() {
    echo "GO [OK] $*"
}

info() {
    echo "INFO $*"
}

echo "=== 1. VALIDATION ROOT ==="

[ "$(id -u)" -eq 0 ] || fail "Ce script doit etre execute en root."

ok "Execution root."
echo

echo "=== 2. VALIDATION DU CAB ==="

[ -d "$REPO/.git" ] || fail "Depot Git absent : $REPO"

cd "$REPO"

CURRENT_BRANCH="$(git branch --show-current)"
START_HEAD="$(git rev-parse HEAD)"

echo "Repo    : $REPO"
echo "Branche : $CURRENT_BRANCH"
echo "HEAD    : $START_HEAD"
echo

if [ "$CURRENT_BRANCH" != "$BASE_BRANCH" ]; then
    fail "Branche actuelle inattendue : $CURRENT_BRANCH"
fi

if [ -n "$(git status --porcelain)" ]; then
    echo "Modifications detectees :"
    git status --short
    fail "Le staging Git n'est pas propre."
fi

ok "Staging propre."

echo
echo "=== 3. PROTECTION CONTRE UNE TABLE EN COURS ==="

if pgrep -af 'VPinballX|VPinballX_BGFX' >/tmp/pincab-vpx-running.$$ 2>/dev/null; then
    cat /tmp/pincab-vpx-running.$$
    rm -f /tmp/pincab-vpx-running.$$
    fail "Une table VPX semble actuellement ouverte. Ferme-la avant l'update."
fi

rm -f /tmp/pincab-vpx-running.$$ 2>/dev/null || true

ok "Aucune table VPX active."

echo
echo "=== 4. VERIFICATION QU'AUCUNE PR > 25 N'EST APPARUE ==="

MAX_PR="$(
    git ls-remote origin 'refs/pull/*/head' 2>/dev/null |
    sed -n 's#.*refs/pull/\([0-9][0-9]*\)/head#\1#p' |
    sort -n |
    tail -n1
)"

echo "Derniere PR detectee sur GitHub : #${MAX_PR:-inconnue}"

if [ -n "${MAX_PR:-}" ] && [ "$MAX_PR" -gt 25 ]; then
    fail "Une nouvelle PR #$MAX_PR existe. Ne pas faire une update incomplete."
fi

ok "PR #25 est toujours la derniere PR disponible."

echo
echo "=== 5. BACKUP GIT AVANT INTEGRATION ==="

git branch "$BACKUP_BRANCH" "$START_HEAD"

git bundle create \
    "$BACKUP/staging-before-pr22-25.bundle" \
    "$BACKUP_BRANCH"

echo "$START_HEAD" > "$BACKUP/start-head.txt"

ok "Branche backup : $BACKUP_BRANCH"
ok "Bundle Git : $BACKUP/staging-before-pr22-25.bundle"

echo
echo "=== 6. RECUPERATION PR22-PR25 ==="

for PR in 22 23 24 25
do
    echo "--- FETCH PR #$PR ---"

    git fetch --force --no-tags origin \
        "refs/pull/$PR/head:refs/remotes/origin/pr/$PR"

    SHA="$(git rev-parse "refs/remotes/origin/pr/$PR")"

    echo "$SHA" > "$BACKUP/pr$PR-head.txt"

    echo "PR #$PR : $SHA"
done

ok "PR22-PR25 recuperees."

echo
echo "=== 7. CREATION BRANCHE D'INTEGRATION ==="

git switch -c "$WORK_BRANCH" "$START_HEAD"

ok "Branche : $WORK_BRANCH"

merge_pr() {
    local PR="$1"
    local REF="refs/remotes/origin/pr/$PR"

    echo
    echo "---------------------------------------------------------------"
    echo " INTEGRATION PR #$PR"
    echo "---------------------------------------------------------------"

    if git merge-base --is-ancestor "$REF" HEAD 2>/dev/null; then
        echo "GO [DEJA PRESENTE] PR #$PR"
        return 0
    fi

    if git merge --no-ff --no-edit "$REF"; then
        echo "GO [OK] PR #$PR integree."
        return 0
    fi

    echo
    echo "NOGO [CONFLIT] PR #$PR"
    git status --short || true

    git merge --abort 2>/dev/null || true
    git switch "$BASE_BRANCH" 2>/dev/null || true

    fail "Conflit pendant PR #$PR. Aucun fichier LIVE n'a ete modifie."
}

echo
echo "=== 8. INTEGRATION DE TOUTES LES NOUVELLES PR ==="

merge_pr 22
merge_pr 23
merge_pr 24
merge_pr 25

MERGED_HEAD="$(git rev-parse HEAD)"

echo
echo "HEAD apres integration : $MERGED_HEAD"

echo
echo "=== 9. VALIDATION GIT ==="

git diff --check "$START_HEAD"..HEAD ||
    fail "git diff --check a detecte une anomalie."

ok "git diff --check."

echo
echo "=== 10. VALIDATION DES MARQUEURS PR ==="

grep -q 'PINCABOS_SAMPLE_TABLES_UI_V1' \
    opt/pincabos/web/tools.py ||
    fail "PR22 absente de tools.py"

grep -q 'PINCABOS_WHEEL_SMALL_LIBRARY_V1' \
    home/pinball/.config/vpinfe/themes/Trinidad/theme.js ||
    fail "PR23 absente de theme.js"

grep -q 'PINCABOS_PHANTOM_OUTPUT_GUARD_V1' \
    opt/pincabos/tools/pincabos-screen-lightdm-safe.sh ||
    fail "PR24 absente du gestionnaire ecran"

grep -q 'PINCABOS_GRAPHICAL_VT_DYNAMIC_V1' \
    usr/local/sbin/pincabos-final-graphical-guard.sh ||
    fail "PR25 absente du graphical guard"

ok "PR22 detectee."
ok "PR23 detectee."
ok "PR24 detectee."
ok "PR25 detectee."

echo
echo "=== 11. VALIDATION SYNTAXE SOURCE ==="

bash -n usr/local/sbin/pincabos-sample-tables ||
    fail "Syntaxe pincabos-sample-tables"

bash -n opt/pincabos/tools/pincabos-screen-lightdm-safe.sh ||
    fail "Syntaxe screen-lightdm-safe"

bash -n usr/local/sbin/pincabos-final-graphical-guard.sh ||
    fail "Syntaxe graphical guard"

bash -n opt/pincabos/script/iso.sh ||
    fail "Syntaxe iso.sh"

python3 -m py_compile opt/pincabos/web/tools.py ||
    fail "Syntaxe Python tools.py"

if command -v node >/dev/null 2>&1; then
    node --check \
        home/pinball/.config/vpinfe/themes/Trinidad/theme.js ||
        fail "Syntaxe Javascript theme.js"

    ok "theme.js valide."
else
    info "[SKIP] node absent."
fi

visudo -cf etc/sudoers.d/pincabos-sample-tables ||
    fail "sudoers PR22 invalide"

ok "Syntaxes validees."

echo
echo "=== 12. PROMOTION DU STAGING ==="

git switch "$BASE_BRANCH"

git merge --ff-only "$WORK_BRANCH" ||
    fail "Impossible de promouvoir l'integration."

git branch -d "$WORK_BRANCH"

FINAL_HEAD="$(git rev-parse HEAD)"

echo "$FINAL_HEAD" > "$BACKUP/final-head.txt"

ok "Staging PR22-25 complet."
echo "HEAD final : $FINAL_HEAD"

echo
echo "=== 13. BACKUP DES FICHIERS LIVE ==="

BACKUP_LIST="$BACKUP/live-files.txt"

cat > "$BACKUP_LIST" <<'EOF'
etc/default/grub
etc/sudoers.d/pincabos-sample-tables
etc/systemd/system/pincabos-sample-tables.path
etc/systemd/system/pincabos-sample-tables.service
etc/systemd/system/multi-user.target.wants/pincabos-sample-tables.path
etc/systemd/system/multi-user.target.wants/pincabos-sample-tables.service
etc/lightdm/lightdm.conf.d/60-pincabos-vt.conf
etc/systemd/system/lightdm.service.d/20-pincabos-vt1.conf
etc/systemd/system/pincabos-switch-graphical-vt.service
home/pinball/.config/vpinfe/collections.ini
home/pinball/.config/vpinfe/vpinfe.ini
home/pinball/.config/vpinfe/themes/Trinidad/theme.js
opt/pincabos/assets/sample-tables
opt/pincabos/script/iso.sh
opt/pincabos/tools/pincabos-screen-lightdm-safe.sh
opt/pincabos/web/tools.py
usr/local/sbin/pincabos-sample-tables
usr/local/sbin/pincabos-final-graphical-guard.sh
EOF

EXISTING_LIST="$BACKUP/live-existing.txt"
: > "$EXISTING_LIST"

while IFS= read -r REL
do
    if [ -e "/$REL" ] || [ -L "/$REL" ]; then
        echo "$REL" >> "$EXISTING_LIST"
    fi
done < "$BACKUP_LIST"

if [ -s "$EXISTING_LIST" ]; then
    tar -C / \
        -cpf "$BACKUP/live-before-pr22-25.tar" \
        -T "$EXISTING_LIST"
fi

ok "Backup LIVE : $BACKUP/live-before-pr22-25.tar"

echo
echo "=== 14. FONCTION DEPLOIEMENT ATOMIQUE ==="

deploy_file() {
    local REL="$1"
    local SRC="$REPO/$REL"
    local DST="/$REL"
    local DIR
    local TMP
    local UID=""
    local GID=""
    local MODE=""

    [ -f "$SRC" ] ||
        fail "Source absente : $SRC"

    DIR="$(dirname "$DST")"

    mkdir -p "$DIR"

    if [ -e "$DST" ]; then
        UID="$(stat -c '%u' "$DST")"
        GID="$(stat -c '%g' "$DST")"
        MODE="$(stat -c '%a' "$DST")"
    fi

    TMP="$DIR/.pincab-update-$(basename "$DST").$$"

    cp -a "$SRC" "$TMP"
    mv -f "$TMP" "$DST"

    if [ -n "$UID" ]; then
        chown "$UID:$GID" "$DST"
        chmod "$MODE" "$DST"
    fi

    echo "GO [DEPLOY] /$REL"
}

echo "GO [OK] Fonction prete."

echo
echo "=== 15. DEPLOIEMENT PR22 — TABLES DE DEMONSTRATION ==="

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
echo "--- Artwork samples ---"

for KEY in example nudge
do
    mkdir -p "/opt/pincabos/assets/sample-tables/$KEY"

    for PNG in bg.png dmd.png table.png wheel.png
    do
        SRC="$REPO/opt/pincabos/assets/sample-tables/$KEY/$PNG"
        DST="/opt/pincabos/assets/sample-tables/$KEY/$PNG"

        [ -f "$SRC" ] ||
            fail "Media PR22 manquant : $SRC"

        install -m 0644 \
            "$SRC" \
            "$DST"

        echo "GO [DEPLOY] $DST"
    done
done

chown -R root:root /opt/pincabos/assets/sample-tables

echo
echo "=== 16. MIGRATION VPinFE PR22 SANS PERDRE LES DONNEES USER ==="

VPINFE_INI="/home/pinball/.config/vpinfe/vpinfe.ini"
COLLECTIONS="/home/pinball/.config/vpinfe/collections.ini"

if [ -f "$VPINFE_INI" ]; then

    # Seulement l'ancien defaut embarque SugarPie's Favorites.
    sed -i \
        "s/^startup_collection[[:space:]]*=[[:space:]]*SugarPie's Favorites[[:space:]]*$/startup_collection = /" \
        "$VPINFE_INI"

    # Applique les options PR22 seulement si aucune option custom n'existe.
    sed -i \
        's/^chromeoptions[[:space:]]*=[[:space:]]*$/chromeoptions = --disable-features=Translate,TranslateUI --no-default-browser-check --disable-infobars/' \
        "$VPINFE_INI"

    chown pinball:pinball "$VPINFE_INI"

    ok "vpinfe.ini migre sans effacer lasttable ou autres preferences."
fi

if [ -f "$COLLECTIONS" ]; then

    FAVORITE_NAME="Favorites"

    if [ -r /etc/pincabos/regional.conf ]; then
        LOCALE="$(
            grep -E '^PINCABOS_LOCALE=' /etc/pincabos/regional.conf 2>/dev/null |
            tail -n1 |
            cut -d= -f2- |
            tr -d '"'"'"
        )"

        case "${LOCALE%%_*}" in
            fr) FAVORITE_NAME="Favoris" ;;
            de) FAVORITE_NAME="Favoriten" ;;
            it) FAVORITE_NAME="Preferiti" ;;
            es) FAVORITE_NAME="Favoritos" ;;
        esac
    fi

    if grep -Fqx "[SugarPie's Favorites]" "$COLLECTIONS"; then

        if ! grep -Fqx "[$FAVORITE_NAME]" "$COLLECTIONS"; then
            sed -i \
                "s/^\[SugarPie's Favorites\]$/[$FAVORITE_NAME]/" \
                "$COLLECTIONS"

            ok "Collection SugarPie's Favorites renommee : $FAVORITE_NAME"
        else
            info "[PRESERVE] Collection $FAVORITE_NAME existe deja."
        fi
    fi

    # Last Played est volontairement conserve sur un cab deja utilise.
    chown pinball:pinball "$COLLECTIONS"

    ok "Historique Last Played conserve."
fi

echo
echo "=== 17. DEPLOIEMENT PR23 — CARROUSEL ==="

deploy_file \
    "home/pinball/.config/vpinfe/themes/Trinidad/theme.js"

chown pinball:pinball \
    /home/pinball/.config/vpinfe/themes/Trinidad/theme.js

ok "PR23 deployee."

echo
echo "=== 18. DEPLOIEMENT PR24 — PROTECTION EDID ==="

deploy_file \
    "opt/pincabos/tools/pincabos-screen-lightdm-safe.sh"

chmod 0755 \
    /opt/pincabos/tools/pincabos-screen-lightdm-safe.sh

ok "PR24 deployee."

echo
echo "=== 19. DEPLOIEMENT PR25 — BOOT / PLYMOUTH / VT ==="

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

chown root:root \
    /etc/lightdm/lightdm.conf.d/60-pincabos-vt.conf \
    /etc/systemd/system/lightdm.service.d/20-pincabos-vt1.conf \
    /etc/systemd/system/pincabos-switch-graphical-vt.service \
    /usr/local/sbin/pincabos-final-graphical-guard.sh

chmod 0644 \
    /etc/lightdm/lightdm.conf.d/60-pincabos-vt.conf \
    /etc/systemd/system/lightdm.service.d/20-pincabos-vt1.conf \
    /etc/systemd/system/pincabos-switch-graphical-vt.service

chmod 0755 \
    /usr/local/sbin/pincabos-final-graphical-guard.sh

GRUB_LINE='GRUB_CMDLINE_LINUX_DEFAULT="quiet splash loglevel=3 rd.udev.log_level=3 systemd.show_status=false rd.systemd.show_status=false vt.global_cursor_default=0"'

if grep -q '^GRUB_CMDLINE_LINUX_DEFAULT=' /etc/default/grub; then
    sed -i \
        "s|^GRUB_CMDLINE_LINUX_DEFAULT=.*|$GRUB_LINE|" \
        /etc/default/grub
else
    echo "$GRUB_LINE" >> /etc/default/grub
fi

ok "Configuration GRUB PR25 appliquee."

echo
echo "=== 20. DEPLOIEMENT ISO.SH FINAL PR22+PR25 ==="

deploy_file "opt/pincabos/script/iso.sh"
chmod 0755 /opt/pincabos/script/iso.sh

ok "iso.sh final deploye."

echo
echo "=== 21. VALIDATION LIVE AVANT SERVICES ==="

bash -n /usr/local/sbin/pincabos-sample-tables ||
    fail "Syntaxe LIVE sample-tables"

bash -n /opt/pincabos/tools/pincabos-screen-lightdm-safe.sh ||
    fail "Syntaxe LIVE screen safe"

bash -n /usr/local/sbin/pincabos-final-graphical-guard.sh ||
    fail "Syntaxe LIVE graphical guard"

bash -n /opt/pincabos/script/iso.sh ||
    fail "Syntaxe LIVE iso.sh"

python3 -m py_compile /opt/pincabos/web/tools.py ||
    fail "Syntaxe LIVE tools.py"

visudo -cf /etc/sudoers.d/pincabos-sample-tables ||
    fail "sudoers LIVE invalide"

ok "Validation LIVE reussie."

echo
echo "=== 22. SYSTEMD ==="

systemctl daemon-reload

systemctl enable pincabos-sample-tables.service
systemctl enable --now pincabos-sample-tables.path

ok "Sample tables service/path actives."

echo
echo "=== 23. RECONCILIATION TABLES ==="

/usr/local/sbin/pincabos-sample-tables reconcile

echo
echo "--- STATUS SAMPLE TABLES ---"
/usr/local/sbin/pincabos-sample-tables status || true

echo
echo "=== 24. UPDATE GRUB ==="

if command -v update-grub >/dev/null 2>&1; then
    update-grub
    ok "GRUB regenere."
else
    fail "Commande update-grub absente."
fi

echo
echo "=== 25. RESTART WEBAPP ==="

systemctl restart pincabos-webapp.service

sleep 2

if systemctl is-active --quiet pincabos-webapp.service; then
    ok "WebApp active."
else
    systemctl --no-pager -l status pincabos-webapp.service || true
    fail "WebApp n'est pas active."
fi

echo
echo "=== 26. RESTART VPINFE ==="

systemctl restart pincabos-vpinfe.service

sleep 3

if systemctl is-active --quiet pincabos-vpinfe.service; then
    ok "VPinFE actif."
else
    systemctl --no-pager -l status pincabos-vpinfe.service || true
    fail "VPinFE n'est pas actif."
fi

echo
echo "=== 27. VALIDATION MARQUEURS LIVE ==="

grep -q 'PINCABOS_SAMPLE_TABLES_UI_V1' \
    /opt/pincabos/web/tools.py &&
    echo "GO [PR22] Sample tables UI"

grep -q 'PINCABOS_WHEEL_SMALL_LIBRARY_V1' \
    /home/pinball/.config/vpinfe/themes/Trinidad/theme.js &&
    echo "GO [PR23] Small library carousel"

grep -q 'PINCABOS_PHANTOM_OUTPUT_GUARD_V1' \
    /opt/pincabos/tools/pincabos-screen-lightdm-safe.sh &&
    echo "GO [PR24] Phantom output guard"

grep -q 'PINCABOS_GRAPHICAL_VT_DYNAMIC_V1' \
    /usr/local/sbin/pincabos-final-graphical-guard.sh &&
    echo "GO [PR25] Dynamic graphical VT"

echo
echo "=== 28. VALIDATION SYSTEMD ==="

printf "%-45s : " "pincabos-webapp.service"
systemctl is-active pincabos-webapp.service || true

printf "%-45s : " "pincabos-vpinfe.service"
systemctl is-active pincabos-vpinfe.service || true

printf "%-45s : " "pincabos-sample-tables.path"
systemctl is-active pincabos-sample-tables.path || true

printf "%-45s : " "pincabos-sample-tables.path enabled"
systemctl is-enabled pincabos-sample-tables.path || true

printf "%-45s : " "pincabos-sample-tables.service enabled"
systemctl is-enabled pincabos-sample-tables.service || true

echo
echo "=== 29. ETAT GIT FINAL ==="

cd "$REPO"

echo "Branche : $(git branch --show-current)"
echo "HEAD    : $(git rev-parse HEAD)"
echo "Backup  : $BACKUP_BRANCH"
echo

git --no-pager log \
    --oneline \
    --decorate \
    --graph \
    -20

echo
echo "--- STATUS ---"

git status --short

if [ -z "$(git status --porcelain)" ]; then
    ok "Working tree Git propre."
else
    echo "NOGO [ATTENTION] Working tree non propre."
fi

echo
echo "=== 30. RAPPORT ==="

cat > "$BACKUP/UPDATE-SUMMARY.txt" <<EOF
PinCabOS FULL PR UPDATE
Date: $(date -Is)

Repo:
$REPO

Branch:
$BASE_BRANCH

Start HEAD:
$START_HEAD

Final HEAD:
$FINAL_HEAD

PR:
22
23
24
25

Git backup:
$BACKUP_BRANCH

Live backup:
$BACKUP/live-before-pr22-25.tar

Etat:
STAGING UPDATED
LIVE UPDATED
GITHUB NOT PUSHED
REBOOT REQUIRED FOR PR25
EOF

echo
echo "==============================================================="
echo " GO [OK] PINCABOS FULL UPDATE PR22 -> PR25 TERMINE"
echo "==============================================================="
echo
echo "PR22 : GO"
echo "PR23 : GO"
echo "PR24 : GO"
echo "PR25 : GO"
echo
echo "Staging : $BASE_BRANCH"
echo "HEAD    : $FINAL_HEAD"
echo
echo "Backup :"
echo "$BACKUP"
echo
echo "IMPORTANT :"
echo "  GitHub n'a PAS encore ete modifie."
echo "  Aucun push n'a ete effectue."
echo
echo "  PR25 necessite maintenant un REBOOT pour tester"
echo "  le passage Plymouth -> LightDM -> VPinFE."
echo
echo "==============================================================="
