#!/usr/bin/env bash
set -Eeuo pipefail

clear

echo "==============================================================="
echo " PINCABOS — CONTINUATION FULL UPDATE PR22 -> PR25"
echo " RESOLUTION PR24 + PR25 + DEPLOIEMENT LIVE"
echo " AUCUN PUSH GITHUB"
echo "==============================================================="
echo

REPO="/opt/pincabos/tmp/pr-integration"

BASE_BRANCH="pincabos-pr-integration"
WORK_BRANCH="integration/full-pr22-25-20260818-132557"

BACKUP="/opt/pincabos/backups/full-pr22-25-20260818-132557"

PR24_SHA="2f342551d8ae5ba915e2e8a2d53b242093ceddc4"
PR25_SHA="e1ac38697ec5eedbc28c968e5764aee094c47b7a"

PR24_REF="refs/remotes/origin/pr/24"
PR25_REF="refs/remotes/origin/pr/25"

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

[ "$(id -u)" -eq 0 ] || fail "Execution root requise."
[ -d "$REPO/.git" ] || fail "Depot absent : $REPO"

cd "$REPO"

echo "=== 1. ETAT APRES LE CONFLIT PRECEDENT ==="

echo "Branche actuelle : $(git branch --show-current)"
echo "HEAD actuelle    : $(git rev-parse HEAD)"
echo

if [ -n "$(git status --porcelain)" ]; then
    echo "NOGO : le depot n'est pas propre."
    git status --short
    exit 1
fi

git show-ref --verify --quiet "refs/heads/$WORK_BRANCH" ||
    fail "Branche temporaire absente : $WORK_BRANCH"

ok "Depot propre."
ok "Branche temporaire PR22/23 retrouvee."

echo
echo "=== 2. VALIDATION PR22 + PR23 DANS LA BRANCHE TEMPORAIRE ==="

git switch "$WORK_BRANCH"

grep -q 'PINCABOS_SAMPLE_TABLES_UI_V1' \
    opt/pincabos/web/tools.py ||
    fail "PR22 absente de la branche temporaire."

grep -q 'PINCABOS_WHEEL_SMALL_LIBRARY_V1' \
    home/pinball/.config/vpinfe/themes/Trinidad/theme.js ||
    fail "PR23 absente de la branche temporaire."

ok "PR22 presente."
ok "PR23 presente."

echo
echo "=== 3. REFRESH PR24 + PR25 ==="

git fetch --force --no-tags origin \
    "refs/pull/24/head:$PR24_REF" \
    "refs/pull/25/head:$PR25_REF"

ACTUAL24="$(git rev-parse "$PR24_REF")"
ACTUAL25="$(git rev-parse "$PR25_REF")"

echo "PR24 : $ACTUAL24"
echo "PR25 : $ACTUAL25"

[ "$ACTUAL24" = "$PR24_SHA" ] ||
    fail "PR24 a change depuis l'audit."

[ "$ACTUAL25" = "$PR25_SHA" ] ||
    fail "PR25 a change depuis l'audit."

ok "SHA PR24/25 valides."

echo
echo "==============================================================="
echo " 4. INTEGRATION PR24 AVEC RESOLUTION CONTROLEE"
echo "==============================================================="

SCREEN_FILE="opt/pincabos/tools/pincabos-screen-lightdm-safe.sh"

if git merge-base --is-ancestor "$PR24_REF" HEAD 2>/dev/null; then

    ok "PR24 deja integree."

else

    set +e
    git merge --no-ff --no-commit "$PR24_REF"
    MERGE_RC=$?
    set -e

    if [ "$MERGE_RC" -ne 0 ]; then

        echo
        echo "Conflit PR24 attendu."

        UNMERGED="$(git diff --name-only --diff-filter=U)"

        echo "$UNMERGED"

        [ "$UNMERGED" = "$SCREEN_FILE" ] || {
            git merge --abort 2>/dev/null || true
            fail "PR24 presente un conflit inattendu."
        }

        echo
        echo "--- Conservation de notre version recente ---"

        git checkout --ours -- "$SCREEN_FILE"

        echo
        echo "--- Injection du guard EDID PR24 ---"

        python3 - "$SCREEN_FILE" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()

marker = "PINCABOS_PHANTOM_OUTPUT_GUARD_V1"

if marker in text:
    print("GO [DEJA PRESENT] marqueur PR24")
    raise SystemExit(0)

anchor = 'xrandr --query >"$TMP" 2>&1 || exit 0\n'

if anchor not in text:
    raise SystemExit(
        "NOGO: ancre xrandr introuvable dans le gestionnaire ecran"
    )

block = r'''
# PINCABOS_PHANTOM_OUTPUT_GUARD_V1
# Une sortie annoncee « connected » mais sans EDID n'est pas un ecran : c'est
# un cable qui pend, un adaptateur seul ou un moniteur en veille profonde. Le
# pilote lui donne un mode de secours 640x480 et X la place a +0+0, donc
# par-dessus le playfield. On l'ecarte avant de composer quoi que ce soit.
drop_phantom_outputs() {
  local edid conn dropped=0
  for edid in /sys/class/drm/card*-*/edid; do
    [ -e "$edid" ] || continue
    [ -s "$edid" ] && continue
    conn="${edid%/edid}"
    conn="${conn##*/}"
    conn="${conn#card*-}"
    grep -q "^$conn connected" "$TMP" || continue
    echo "sortie sans EDID ignoree (cable sans ecran ?) : $conn"
    xrandr --output "$conn" --off 2>/dev/null || true
    dropped=1
  done
  [ "$dropped" = 1 ] && xrandr --query >"$TMP" 2>&1
  return 0
}
drop_phantom_outputs

'''

text = text.replace(anchor, anchor + block, 1)

path.write_text(text)

print("GO [OK] PR24 injectee dans la version courante.")
PY

        git add "$SCREEN_FILE"
    fi

    grep -q 'PINCABOS_PHANTOM_OUTPUT_GUARD_V1' "$SCREEN_FILE" ||
        fail "Marqueur PR24 absent apres resolution."

    bash -n "$SCREEN_FILE" ||
        fail "Syntaxe invalide apres PR24."

    git diff --cached --check ||
        fail "git diff --check PR24."

    git commit \
        -m "Merge PR #24 - phantom output guard resolved on integration"

    ok "PR24 integree avec son historique Git."
fi

echo
echo "==============================================================="
echo " 5. INTEGRATION PR25"
echo "==============================================================="

if git merge-base --is-ancestor "$PR25_REF" HEAD 2>/dev/null; then

    ok "PR25 deja integree."

else

    set +e
    git merge --no-ff --no-commit "$PR25_REF"
    MERGE25_RC=$?
    set -e

    if [ "$MERGE25_RC" -ne 0 ]; then

        echo
        echo "INFO : conflit PR25 detecte — resolution ciblee."

        UNMERGED="$(git diff --name-only --diff-filter=U)"

        echo "$UNMERGED"

        while IFS= read -r F
        do
            [ -n "$F" ] || continue

            case "$F" in
                etc/default/grub|\
                etc/systemd/system/pincabos-switch-graphical-vt.service|\
                opt/pincabos/script/iso.sh|\
                usr/local/sbin/pincabos-final-graphical-guard.sh)

                    echo "OURS : $F"
                    git checkout --ours -- "$F"
                    ;;

                etc/lightdm/lightdm.conf.d/60-pincabos-vt.conf|\
                etc/systemd/system/lightdm.service.d/20-pincabos-vt1.conf)

                    echo "THEIRS : $F"
                    git checkout --theirs -- "$F"
                    ;;

                *)
                    git merge --abort 2>/dev/null || true
                    fail "Conflit PR25 inattendu : $F"
                    ;;
            esac

        done <<< "$UNMERGED"
    fi

    echo
    echo "--- Normalisation exacte des modifications PR25 ---"

    python3 <<'PY'
from pathlib import Path
import re

# ------------------------------------------------------------
# /etc/default/grub
# ------------------------------------------------------------
p = Path("etc/default/grub")
text = p.read_text()

new_line = (
    'GRUB_CMDLINE_LINUX_DEFAULT="quiet splash loglevel=3 '
    'rd.udev.log_level=3 systemd.show_status=false '
    'rd.systemd.show_status=false vt.global_cursor_default=0"'
)

text, n = re.subn(
    r'^GRUB_CMDLINE_LINUX_DEFAULT=.*$',
    new_line,
    text,
    count=1,
    flags=re.MULTILINE,
)

if n != 1:
    raise SystemExit("NOGO: GRUB_CMDLINE_LINUX_DEFAULT introuvable")

p.write_text(text)

# ------------------------------------------------------------
# service switch graphical VT
# ------------------------------------------------------------
p = Path("etc/systemd/system/pincabos-switch-graphical-vt.service")
text = p.read_text()

new_exec = (
    "ExecStart=/bin/bash -lc 'for i in $(seq 1 60); do "
    "[ -S /tmp/.X11-unix/X0 ] && break; sleep 1; done; "
    'PCO_GVT=$(ps -eo args= | sed -n "s/.*Xorg .* '
    'vt\\\\([0-9]\\\\{1,\\\\}\\\\).*/\\\\1/p" | head -n1); '
    '[ -n "${PCO_GVT:-}" ] || PCO_GVT=7; '
    'command -v chvt >/dev/null 2>&1 && chvt "$PCO_GVT" || true; '
    'echo "GO: pincabos-vpinfe restart deferred until final reboot"\''
)

lines = text.splitlines()
found = False

for i, line in enumerate(lines):
    if line.startswith("ExecStart=/bin/bash -lc "):
        lines[i] = new_exec
        found = True
        break

if not found:
    raise SystemExit("NOGO: ExecStart graphical VT introuvable")

text = "\n".join(lines) + "\n"

if "Le terminal graphique suit Xorg" not in text:
    text = text.replace(
        new_exec + "\n",
        "# Le terminal graphique suit Xorg : LightDM peut reprendre celui de\n"
        "# Plymouth (VT 1) pour un passage de relais sans console visible.\n"
        + new_exec + "\n",
        1,
    )

p.write_text(text)

# ------------------------------------------------------------
# iso.sh
# ------------------------------------------------------------
p = Path("opt/pincabos/script/iso.sh")
text = p.read_text()

new_cmd = (
    'quiet splash loglevel=3 rd.udev.log_level=3 '
    'systemd.show_status=false rd.systemd.show_status=false '
    'vt.global_cursor_default=0'
)

if new_cmd not in text:
    old = '''if grep -q '^GRUB_CMDLINE_LINUX_DEFAULT=' "$TARGET/etc/default/grub"; then
  sed -i 's/^GRUB_CMDLINE_LINUX_DEFAULT=.*/GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"/' "$TARGET/etc/default/grub"
else
  echo 'GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"' >> "$TARGET/etc/default/grub"
fi'''

    new = '''if grep -q '^GRUB_CMDLINE_LINUX_DEFAULT=' "$TARGET/etc/default/grub"; then
  sed -i 's/^GRUB_CMDLINE_LINUX_DEFAULT=.*/GRUB_CMDLINE_LINUX_DEFAULT="quiet splash loglevel=3 rd.udev.log_level=3 systemd.show_status=false rd.systemd.show_status=false vt.global_cursor_default=0"/' "$TARGET/etc/default/grub"
else
  echo 'GRUB_CMDLINE_LINUX_DEFAULT="quiet splash loglevel=3 rd.udev.log_level=3 systemd.show_status=false rd.systemd.show_status=false vt.global_cursor_default=0"' >> "$TARGET/etc/default/grub"
fi'''

    if old not in text:
        raise SystemExit("NOGO: bloc GRUB cible absent de iso.sh")

    text = text.replace(old, new, 1)

p.write_text(text)

# ------------------------------------------------------------
# final graphical guard
# ------------------------------------------------------------
p = Path("usr/local/sbin/pincabos-final-graphical-guard.sh")
text = p.read_text()

if "PINCABOS_GRAPHICAL_VT_DYNAMIC_V1" not in text:

    pattern = re.compile(
        r'if command -v chvt >/dev/null 2>&1; then\n'
        r'.*?'
        r'else\n'
        r'  echo "WARN: chvt missing; install package kbd in RUN_01"\n'
        r'fi',
        re.DOTALL,
    )

    replacement = r'''if command -v chvt >/dev/null 2>&1; then
  # PINCABOS_GRAPHICAL_VT_DYNAMIC_V1
  # Le terminal graphique n'est plus fige a 7 : LightDM reprend desormais
  # celui de Plymouth, pour que le splash cede la place a X sans laisser voir
  # la console. On bascule vers le terminal que Xorg utilise reellement.
  PCO_GVT="$(ps -eo args= | sed -n 's/.*Xorg .* vt\([0-9]\{1,\}\).*/\1/p' | head -n1)"
  [ -n "${PCO_GVT:-}" ] || PCO_GVT=7
  chvt "$PCO_GVT" || true
  sleep 2
  if command -v fgconsole >/dev/null 2>&1; then
    echo "VT after chvt$PCO_GVT: $(fgconsole 2>/dev/null || true)"
  fi
  echo "GO: chvt $PCO_GVT attempted"
else
  echo "WARN: chvt missing; install package kbd in RUN_01"
fi'''

    text, n = pattern.subn(replacement, text, count=1)

    if n != 1:
        raise SystemExit("NOGO: bloc chvt cible introuvable")

p.write_text(text)

print("GO [OK] fichiers PR25 normalises.")
PY

    echo
    echo "--- Fichiers nouveaux PR25 ---"

    mkdir -p \
        etc/lightdm/lightdm.conf.d \
        etc/systemd/system/lightdm.service.d

    git show \
        "$PR25_REF:etc/lightdm/lightdm.conf.d/60-pincabos-vt.conf" \
        > etc/lightdm/lightdm.conf.d/60-pincabos-vt.conf

    git show \
        "$PR25_REF:etc/systemd/system/lightdm.service.d/20-pincabos-vt1.conf" \
        > etc/systemd/system/lightdm.service.d/20-pincabos-vt1.conf

    git add \
        etc/default/grub \
        etc/lightdm/lightdm.conf.d/60-pincabos-vt.conf \
        etc/systemd/system/lightdm.service.d/20-pincabos-vt1.conf \
        etc/systemd/system/pincabos-switch-graphical-vt.service \
        opt/pincabos/script/iso.sh \
        usr/local/sbin/pincabos-final-graphical-guard.sh

    if [ -n "$(git diff --name-only --diff-filter=U)" ]; then
        git diff --name-only --diff-filter=U
        fail "Il reste des conflits PR25."
    fi

    git diff --cached --check ||
        fail "git diff --check PR25."

    git commit \
        -m "Merge PR #25 - quiet Plymouth to LightDM handoff"

    ok "PR25 integree avec son historique Git."
fi

echo
echo "==============================================================="
echo " 6. VALIDATION SOURCE PR22 -> PR25"
echo "==============================================================="

grep -q 'PINCABOS_SAMPLE_TABLES_UI_V1' \
    opt/pincabos/web/tools.py ||
    fail "PR22"

grep -q 'PINCABOS_WHEEL_SMALL_LIBRARY_V1' \
    home/pinball/.config/vpinfe/themes/Trinidad/theme.js ||
    fail "PR23"

grep -q 'PINCABOS_PHANTOM_OUTPUT_GUARD_V1' \
    opt/pincabos/tools/pincabos-screen-lightdm-safe.sh ||
    fail "PR24"

grep -q 'PINCABOS_GRAPHICAL_VT_DYNAMIC_V1' \
    usr/local/sbin/pincabos-final-graphical-guard.sh ||
    fail "PR25"

bash -n usr/local/sbin/pincabos-sample-tables
bash -n opt/pincabos/tools/pincabos-screen-lightdm-safe.sh
bash -n usr/local/sbin/pincabos-final-graphical-guard.sh
bash -n opt/pincabos/script/iso.sh

python3 -m py_compile opt/pincabos/web/tools.py

visudo -cf etc/sudoers.d/pincabos-sample-tables

if command -v node >/dev/null 2>&1; then
    node --check \
        home/pinball/.config/vpinfe/themes/Trinidad/theme.js
fi

git diff --check "$BASE_BRANCH"..HEAD

ok "PR22 source."
ok "PR23 source."
ok "PR24 source."
ok "PR25 source."
ok "Syntaxes source."

echo
echo "=== 7. PROMOTION SUR pincabos-pr-integration ==="

FINAL_HEAD="$(git rev-parse HEAD)"

git switch "$BASE_BRANCH"

git merge --ff-only "$WORK_BRANCH" ||
    fail "Promotion fast-forward impossible."

git branch -d "$WORK_BRANCH"

echo
echo "HEAD FINAL STAGING : $(git rev-parse HEAD)"

[ "$(git rev-parse HEAD)" = "$FINAL_HEAD" ] ||
    fail "HEAD final incorrect."

[ -z "$(git status --porcelain)" ] ||
    fail "Working tree non propre."

ok "Staging complet PR1 -> PR25."

echo
echo "==============================================================="
echo " 8. BACKUP LIVE AVANT DEPLOIEMENT"
echo "==============================================================="

mkdir -p "$BACKUP"

LIVE_LIST="$BACKUP/live-files-before-deploy.txt"
LIVE_EXIST="$BACKUP/live-existing-before-deploy.txt"

cat > "$LIVE_LIST" <<'EOF'
etc/default/grub
boot/grub/grub.cfg
etc/sudoers.d/pincabos-sample-tables
etc/systemd/system/pincabos-sample-tables.path
etc/systemd/system/pincabos-sample-tables.service
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

: > "$LIVE_EXIST"

while IFS= read -r F
do
    if [ -e "/$F" ] || [ -L "/$F" ]; then
        echo "$F" >> "$LIVE_EXIST"
    fi
done < "$LIVE_LIST"

tar -C / \
    -cpf "$BACKUP/live-before-pr22-25.tar" \
    -T "$LIVE_EXIST"

ok "Backup LIVE : $BACKUP/live-before-pr22-25.tar"

echo
echo "=== 9. DEPLOIEMENT DES FICHIERS CODE ==="

cd "$REPO"

deploy_file() {
    local REL="$1"
    local SRC="$REPO/$REL"
    local DST="/$REL"
    local DIR
    local UID=""
    local GID=""
    local MODE=""
    local TMP

    [ -f "$SRC" ] || fail "Source absente : $SRC"

    DIR="$(dirname "$DST")"
    mkdir -p "$DIR"

    if [ -e "$DST" ]; then
        UID="$(stat -c '%u' "$DST")"
        GID="$(stat -c '%g' "$DST")"
        MODE="$(stat -c '%a' "$DST")"
    fi

    TMP="$DIR/.pco-update-$(basename "$DST").$$"

    cp -a "$SRC" "$TMP"
    mv -f "$TMP" "$DST"

    if [ -n "$UID" ]; then
        chown "$UID:$GID" "$DST"
        chmod "$MODE" "$DST"
    fi

    echo "GO [DEPLOY] $DST"
}

# PR22
deploy_file "usr/local/sbin/pincabos-sample-tables"
deploy_file "etc/sudoers.d/pincabos-sample-tables"
deploy_file "etc/systemd/system/pincabos-sample-tables.path"
deploy_file "etc/systemd/system/pincabos-sample-tables.service"
deploy_file "opt/pincabos/web/tools.py"

chmod 0755 /usr/local/sbin/pincabos-sample-tables
chown root:root /usr/local/sbin/pincabos-sample-tables

chmod 0440 /etc/sudoers.d/pincabos-sample-tables
chown root:root /etc/sudoers.d/pincabos-sample-tables

chmod 0644 \
    /etc/systemd/system/pincabos-sample-tables.path \
    /etc/systemd/system/pincabos-sample-tables.service

chown root:root \
    /etc/systemd/system/pincabos-sample-tables.path \
    /etc/systemd/system/pincabos-sample-tables.service

mkdir -p \
    /opt/pincabos/assets/sample-tables/example \
    /opt/pincabos/assets/sample-tables/nudge

for KEY in example nudge
do
    for PNG in bg.png dmd.png table.png wheel.png
    do
        install \
            -o root \
            -g root \
            -m 0644 \
            "$REPO/opt/pincabos/assets/sample-tables/$KEY/$PNG" \
            "/opt/pincabos/assets/sample-tables/$KEY/$PNG"

        echo "GO [DEPLOY] sample/$KEY/$PNG"
    done
done

# PR23
deploy_file \
    "home/pinball/.config/vpinfe/themes/Trinidad/theme.js"

chown pinball:pinball \
    /home/pinball/.config/vpinfe/themes/Trinidad/theme.js

# PR24
deploy_file \
    "opt/pincabos/tools/pincabos-screen-lightdm-safe.sh"

chmod 0755 \
    /opt/pincabos/tools/pincabos-screen-lightdm-safe.sh

# PR25
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

# ISO final = PR22 + PR25
deploy_file "opt/pincabos/script/iso.sh"
chmod 0755 /opt/pincabos/script/iso.sh

echo
echo "=== 10. CONFIG VPinFE PERSONNELLE ==="

echo "GO [PRESERVE] /home/pinball/.config/vpinfe/vpinfe.ini"
echo "GO [PRESERVE] /home/pinball/.config/vpinfe/collections.ini"
echo
echo "Les valeurs par defaut PR22 sont dans Git pour les futures installations,"
echo "mais les donnees personnelles de CE cab sont conservees."

echo
echo "=== 11. APPLICATION GRUB PR25 SANS ECRASER LE RESTE ==="

GRUB_VALUE='quiet splash loglevel=3 rd.udev.log_level=3 systemd.show_status=false rd.systemd.show_status=false vt.global_cursor_default=0'

python3 - "$GRUB_VALUE" <<'PY'
from pathlib import Path
import re
import sys

value = sys.argv[1]

p = Path("/etc/default/grub")
text = p.read_text()

line = f'GRUB_CMDLINE_LINUX_DEFAULT="{value}"'

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

ok "GRUB PR25 applique."

echo
echo "=== 12. VALIDATION LIVE AVANT RESTART ==="

bash -n /usr/local/sbin/pincabos-sample-tables
bash -n /opt/pincabos/tools/pincabos-screen-lightdm-safe.sh
bash -n /usr/local/sbin/pincabos-final-graphical-guard.sh
bash -n /opt/pincabos/script/iso.sh

python3 -m py_compile /opt/pincabos/web/tools.py

visudo -cf /etc/sudoers.d/pincabos-sample-tables

grep -q 'PINCABOS_SAMPLE_TABLES_UI_V1' \
    /opt/pincabos/web/tools.py

grep -q 'PINCABOS_WHEEL_SMALL_LIBRARY_V1' \
    /home/pinball/.config/vpinfe/themes/Trinidad/theme.js

grep -q 'PINCABOS_PHANTOM_OUTPUT_GUARD_V1' \
    /opt/pincabos/tools/pincabos-screen-lightdm-safe.sh

grep -q 'PINCABOS_GRAPHICAL_VT_DYNAMIC_V1' \
    /usr/local/sbin/pincabos-final-graphical-guard.sh

ok "PR22 LIVE."
ok "PR23 LIVE."
ok "PR24 LIVE."
ok "PR25 LIVE."

echo
echo "=== 13. SYSTEMD SAMPLE TABLES ==="

systemctl daemon-reload

systemctl enable pincabos-sample-tables.service
systemctl enable pincabos-sample-tables.path

systemctl start pincabos-sample-tables.service
systemctl start pincabos-sample-tables.path

echo
echo "--- STATUS SAMPLE TABLES ---"

/usr/local/sbin/pincabos-sample-tables status || true

echo
echo "=== 14. GENERATION GRUB ==="

update-grub

ok "grub.cfg regenere."

echo
echo "=== 15. RESTART WEBAPP ==="

systemctl restart pincabos-webapp.service
sleep 2

systemctl is-active --quiet pincabos-webapp.service ||
    fail "WebApp inactive."

ok "WebApp active."

echo
echo "=== 16. RESTART VPINFE ==="

systemctl restart pincabos-vpinfe.service
sleep 3

systemctl is-active --quiet pincabos-vpinfe.service ||
    fail "VPinFE inactif."

ok "VPinFE actif."

echo
echo "=== 17. ETAT SERVICES ==="

for S in \
    pincabos-webapp.service \
    pincabos-vpinfe.service \
    pincabos-sample-tables.service \
    pincabos-sample-tables.path \
    pincabos-final-graphical-guard.service
do
    printf "%-45s : " "$S"
    systemctl is-active "$S" 2>/dev/null || true
done

echo
echo "=== 18. ETAT GIT FINAL ==="

cd "$REPO"

echo "Branche : $(git branch --show-current)"
echo "HEAD    : $(git rev-parse HEAD)"
echo

git --no-pager log \
    --graph \
    --decorate \
    --oneline \
    -20

echo
echo "--- STATUS ---"
git status --short

[ -z "$(git status --porcelain)" ] ||
    fail "Git final non propre."

echo
echo "=== 19. RAPPORT FINAL ==="

cat > "$BACKUP/UPDATE-SUMMARY.txt" <<EOF
PINCABOS FULL UPDATE PR22-PR25

Date:
$(date -Is)

Repository:
$REPO

Branch:
$BASE_BRANCH

Final HEAD:
$(git rev-parse HEAD)

PR22: APPLIED
PR23: APPLIED
PR24: APPLIED - manual conflict resolution preserving current screen code
PR25: APPLIED

Live:
UPDATED

VPinFE personal configuration:
PRESERVED

GitHub push:
NOT DONE

Reboot:
REQUIRED
EOF

echo
echo "==============================================================="
echo " GO [OK] PINCABOS EST FULL UPDATE JUSQU'A PR25"
echo "==============================================================="
echo
echo "PR22 : GO"
echo "PR23 : GO"
echo "PR24 : GO"
echo "PR25 : GO"
echo
echo "Git staging : GO"
echo "Live        : GO"
echo "GitHub push : PAS ENCORE"
echo
echo "Backup :"
echo "$BACKUP"
echo
echo "PROCHAINE ETAPE :"
echo "  NE PUSH PAS GITHUB ENCORE."
echo "  REBOOT + AUDIT DU BOOT / ECRANS / WEBAPP / VPINFE."
echo "==============================================================="
