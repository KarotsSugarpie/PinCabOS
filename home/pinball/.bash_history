clear
set -Eeuo pipefail
echo "────────────────────────────────────────────────────────────────"
echo " ISODev - Activer SSH root avec password"
echo "────────────────────────────────────────────────────────────────"
echo
echo "=== 1) Installer OpenSSH Server ==="
sudo apt update
sudo apt install -y openssh-server
echo
echo "=== 2) Définir le mot de passe root ==="
sudo passwd root
echo
echo "=== 3) Backup SSH config ==="
TS="$(date +%Y%m%d-%H%M%S)"
sudo mkdir -p /root/ssh-backups
sudo cp -a /etc/ssh/sshd_config "/root/ssh-backups/sshd_config.$TS" 2>/dev/null || true
echo
echo "=== 4) Autoriser root login + password auth ==="
sudo mkdir -p /etc/ssh/sshd_config.d
sudo tee /etc/ssh/sshd_config.d/99-isodev-root-login.conf >/dev/null <<'EOF'
PermitRootLogin yes
PasswordAuthentication yes
KbdInteractiveAuthentication yes
UsePAM yes
EOF

echo
echo "=== 5) Valider sshd ==="
sudo sshd -t
echo
echo "=== 6) Activer/redémarrer SSH ==="
sudo systemctl enable ssh
sudo systemctl restart ssh
echo
echo "=== 7) Vérification ==="
sudo systemctl is-enabled ssh
sudo systemctl is-active ssh
sudo sshd -T | grep -Ei 'permitrootlogin|passwordauthentication|kbdinteractiveauthentication|usepam'
hostname -I
echo
echo "GO: SSH root avec password activé"
echo "Backup: /root/ssh-backups/sshd_config.$TS"
exit
ip a
clear
set -e
TAG="v10.8.1-3788-2151290"
ASSET="VPinballX_BGFX-10.8.1-3788-2151290-linux-x64-Release.tar.gz"
mkdir -p "$HOME/Downloads"
cd "$HOME/Downloads"
echo "=== TELECHARGEMENT OFFICIEL VPINBALL BGFX ==="
gh release download "$TAG"   --repo vpinball/vpinball   --pattern "$ASSET"
clear
gh auth login --hostname github.com --git-protocol https --web
gh auth status -h github.com
clear
gh run list   --repo vpinball/vpinball   --status success   --limit 12   --json databaseId,displayTitle,createdAt,headSha,workflowName,url   --jq '.[] | select(.workflowName == "vpinball") | "\(.databaseId) | \(.createdAt) | \(.displayTitle) | \(.headSha)"'
clear
gh api   "repos/vpinball/vpinball/actions/runs/28302304858/artifacts"   --paginate   --jq '.artifacts[] | select(.expired == false) | .name'
clear
RUN_ID="28302304858"
ASSET="VPinballX_BGFX-10.8.1-5231-7ca174632-linux-x64-Release.tar.gz"
mkdir -p "$HOME/Downloads/vpinball-bgfx-5231"
cd "$HOME/Downloads/vpinball-bgfx-5231"
echo "=== TELECHARGEMENT OFFICIEL ==="
gh run download "$RUN_ID"   --repo vpinball/vpinball   --name "$ASSET"   --dir "$HOME/Downloads/vpinball-bgfx-5231"
echo
echo "=== FICHIERS RECUS ==="
find "$HOME/Downloads/vpinball-bgfx-5231" -maxdepth 2 -type f -printf '%P\n' | sort
clear
RUN_ID="28302304858"
ASSET="VPinballX_BGFX-10.8.1-5231-7ca174632-linux-x64-Release.tar.gz"
WORK="$HOME/Downloads/vpinball-bgfx-5231"
INSTALL="$HOME/VPinballX_BGFX-10.8.1-5231-7ca174632-linux-x64"
mkdir -p "$WORK" "$INSTALL"
cd "$WORK" || echo "ERREUR: dossier inaccessible."
ARTIFACT_ID="$(gh api \
  "/repos/vpinball/vpinball/actions/runs/${RUN_ID}/artifacts?per_page=100" \
  --jq ".artifacts[] | select(.name == \"${ASSET}\" and .expired == false) | .id")"
EXPECTED_DIGEST="$(gh api \
  "/repos/vpinball/vpinball/actions/runs/${RUN_ID}/artifacts?per_page=100" \
  --jq ".artifacts[] | select(.name == \"${ASSET}\" and .expired == false) | .digest")"
echo "=== ARTEFACT OFFICIEL ==="
echo "ID     : $ARTIFACT_ID"
echo "Digest : $EXPECTED_DIGEST"
if [ -z "$ARTIFACT_ID" ] || [ -z "$EXPECTED_DIGEST" ]; then   echo "ERREUR: artefact ou digest introuvable. Rien n'a ete installe."; else   rm -f action-artifact.zip "$ASSET";    TOKEN="$(gh auth token -h github.com)";   curl -fL --retry 3 --retry-all-errors     -H "Accept: application/vnd.github+json"     -H "Authorization: Bearer $TOKEN"     -H "X-GitHub-Api-Version: 2026-03-10"     "https://api.github.com/repos/vpinball/vpinball/actions/artifacts/${ARTIFACT_ID}/zip"     -o action-artifact.zip;   unset TOKEN;    echo;   echo "=== VERIFICATION ARCHIVE ACTIONS ===";   file action-artifact.zip;   ACTUAL_DIGEST="sha256:$(sha256sum action-artifact.zip | awk '{print $1}')";   echo "Recu    : $ACTUAL_DIGEST";   echo "Attendu : $EXPECTED_DIGEST";    if [ "$ACTUAL_DIGEST" != "$EXPECTED_DIGEST" ]; then     echo "ERREUR: digest different. Extraction bloquee.";   elif ! unzip -t action-artifact.zip; then     echo "ERREUR: ZIP GitHub invalide. Extraction bloquee.";   else     unzip -o action-artifact.zip;     echo;     echo "=== VERIFICATION TAR.GZ VPX ===";     file "$ASSET";     tar -tzf "$ASSET" | head -25;      echo;     echo "=== EXTRACTION MANUELLE VPX ===";     tar -xzf "$ASSET" -C "$INSTALL";      echo;     echo "=== EXECUTABLE OFFICIEL ===";     find "$INSTALL" -type f -name 'VPinballX_BGFX' -executable -print;   fi; fi
clear
ASSET="VPinballX_BGFX-10.8.1-5231-7ca174632-linux-x64-Release.tar.gz"
INSTALL="$HOME/VPinballX_BGFX-10.8.1-5231-7ca174632-linux-x64"
echo "=== VALIDATION TAR.GZ ==="
gzip -t action-artifact.zip
tar -tzf action-artifact.zip | head -30
echo
echo "=== INSTALLATION MANUELLE STANDARD ==="
mkdir -p "$INSTALL"
mv -f action-artifact.zip "$ASSET"
tar -xzf "$ASSET" -C "$INSTALL"
echo
echo "=== EXECUTABLE INSTALLE ==="
find "$INSTALL" -type f -name 'VPinballX_BGFX' -executable -print
clear
cd "$HOME/VPinballX_BGFX-10.8.1-5231-7ca174632-linux-x64"
./VPinballX_BGFX -v
clear
cd "$HOME/VPinballX_BGFX-10.8.1-5231-7ca174632-linux-x64"
DISPLAY=:0 XAUTHORITY="$HOME/.Xauthority" ./VPinballX_BGFX
clear
export XDG_RUNTIME_DIR="/run/user/1000"
export DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/1000/bus"
export DISPLAY=":0"
export XAUTHORITY="$HOME/.Xauthority"
cd "$HOME/VPinballX_BGFX-10.8.1-5231-7ca174632-linux-x64"
./VPinballX_BGFX
clear
VPX="$HOME/VPinballX_BGFX-10.8.1-5231-7ca174632-linux-x64"
echo "=== DOF INCLUS DANS VPX ==="
find "$VPX/plugins/dof" -maxdepth 1 \( -type f -o -type l \) -printf '%f\n' | sort
clear
set -Eeuo pipefail
VPX_DIR="$HOME/VPinballX_BGFX-10.8.1-5231-7ca174632-linux-x64"
VPX_BIN="$VPX_DIR/VPinballX_BGFX"
OLD_INI="$HOME/.vpinball/VPinballX.ini"
NEW_DIR="$HOME/.local/share/VPinballX/10.8"
NEW_INI="$NEW_DIR/VPinballX.ini"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$NEW_DIR/backups-afm-$STAMP"
echo "==============================================================="
echo " AFM — CONFIGURATION VPX BGFX 5231"
echo "==============================================================="
if pgrep -af 'VPinballX|VPinballX_BGFX' >/dev/null; then   echo "ERREUR : VPX est deja ouvert. Ferme VPX puis relance cette commande.";   exit 1; fi
test -x "$VPX_BIN" || { echo "ERREUR : VPX BGFX introuvable."; exit 1; }
test -f "$OLD_INI" || { echo "ERREUR : ancienne configuration introuvable : $OLD_INI"; exit 1; }
reboot
sudo reboot
clear
echo "==============================================================="
echo " PINCABOS V8.1E — PAYLOAD RAPIDE SANS TABLES"
echo " Compression zstd -6 + checkpoints tar"
echo "==============================================================="
pkill -TERM -f 'pincabos-rootfs-cab-v8.1.tar.zst' 2>/dev/null || true
sleep 2
rm -rf /root/pincabos-v8.1-cab-payload
python3 <<'PY'
from pathlib import Path

p = Path("/root/pincabos-v8-build-cab-payload.sh")
s = p.read_text()

# Compression rapide au lieu de -19
s = s.replace(
    "-I 'zstd -T0 -19 --long=31'",
    "-I 'zstd -T0 -6'"
)

# Ajoute progression tar si absente
if "--checkpoint=10000" not in s:
    s = s.replace(
        "tar \\\n  --acls",
        "tar \\\n  --checkpoint=10000 \\\n  --checkpoint-action=echo='archived %u entries...' \\\n  --acls"
    )

# Exclusions sûres pour payload ISO
anchor = "  --exclude='./var/cache/apt/archives/*.deb' \\"
extra_excludes = [
    "  --exclude='./home/pinball/Tables/*' \\",
    "  --exclude='./home/pinball/Backups/*' \\",
    "  --exclude='./home/pinball/Downloads/*' \\",
    "  --exclude='./home/pinball/.cache/*' \\",
    "  --exclude='./home/pinball/.local/share/Trash/*' \\",
    "  --exclude='./opt/pincabos/build/rootfs-staging/*' \\",
    "  --exclude='./opt/pincabos/build/rootfs-staging' \\",
    "  --exclude='./var/log/journal/*' \\",
]

for ex in reversed(extra_excludes):
    if ex not in s:
        s = s.replace(anchor, ex + "\n" + anchor)

# Garde thème final pincabos forcé
s = s.replace(
    'PIN_THEME_NAME="$(printf \'%s\\n\' "$PIN_PLYMOUTH_FILES" | head -n1 | xargs -r basename | sed \'s/\\.plymouth$//\')"',
    'PIN_THEME_NAME="pincabos"'
)

# S'assure que le helper force pincabos
s = s.replace(
    'chroot "$TARGET" plymouth-set-default-theme "$PIN_THEME_NAME"',
    'chroot "$TARGET" plymouth-set-default-theme pincabos'
)

p.write_text(s)
PY

chmod +x /root/pincabos-v8-build-cab-payload.sh
echo
echo "=== Vérification patch rapide ==="
grep -nE "zstd -T0|checkpoint|home/pinball/Tables|Backups|Downloads|rootfs-staging|plymouth-set-default-theme"   /root/pincabos-v8-build-cab-payload.sh | sed -n '1,220p'
echo
echo "=== Relance build rapide ==="
bash /root/pincabos-v8-build-cab-payload.sh
sudo-i
sudo -i
clear
set -euo pipefail
echo "==============================================================="
echo " PINCABOS — VALIDATION ABOUT/HELP V2.4B SANS FAUX POSITIF FOOTER"
echo " Vérifie seulement le contenu About/Help, pas le footer global"
echo "==============================================================="
curl -fsS -o /tmp/pincabos-about-v24b.html http://127.0.0.1/about
curl -fsS -o /tmp/pincabos-help-v24b.html http://127.0.0.1/help
echo
echo "--- Extraction section About seulement ---"
python3 - <<'PY'
from pathlib import Path

html = Path("/tmp/pincabos-about-v24b.html").read_text(errors="replace")

start = html.find('<div class="about-page about-v24">')
if start < 0:
    raise SystemExit("ERREUR: section about-v24 introuvable")

# Le footer arrive après le contenu injecté par page().
footer_markers = [
    "Soutenir PinCabOS",
    "Release notes",
    "★★ Testers",
    "pincabos-footer",
]

end = len(html)
for marker in footer_markers:
    pos = html.find(marker, start)
    if pos > 0:
        end = min(end, pos)

about = html[start:end]
Path("/tmp/pincabos-about-v24b-body-only.html").write_text(about)

required = [
    "Dashboard configurable",
    "Batch Smart Import",
    "Batch Smart Export",
    "Apparence",
    "Clavier régional",
    "Map Commander",
    "FullDMD / DMD",
    "ConfigTools",
    "Ouvrir VPinFE",
    "Ouvrir VPS",
    "Playfield",
    "Backglass",
    "version.json",
]

missing = [x for x in required if x not in about]
if missing:
    print("ERREUR: éléments manquants:")
    for x in missing:
        print(" -", x)
    raise SystemExit(1)

forbidden = [
    "Current state Alpha 1.3",
    "What remains to be done",
    "{esc(pco_path_text",
    "Testeurs / Soutiens fondateurs",
    "Founder Supporters",
]

bad = [x for x in forbidden if x in about]
if bad:
    print("ERREUR: vieux contenu encore dans le About:")
    for x in bad:
        print(" -", x)
    raise SystemExit(1)

print("OK: About V2.4 propre. Le footer n'est pas compté.")
PY

echo
echo "--- Vérification Help seulement ---"
grep -nE "Dashboard entièrement configurable|Widgets Dashboard disponibles|Apparence PinCabOS|Configuration clavier régional|Batch Smart Import|Batch Smart Export|Map Commander|Visuel Nudge|auto-réglage du DMD|Ouvrir VPinFE|Ouvrir VPS|ConfigTools" /tmp/pincabos-help-v24b.html | head -n 120
echo
echo "--- Vérification mot de passe pas en texte dans Help ---"
if grep -nE 'Pinball123\$|Pinbal123\$|Pinball[[:space:]]+\$123' /tmp/pincabos-help-v24b.html; then   echo "ERREUR: mot de passe visible en texte HTML";   exit 1; else   echo "OK: mot de passe seulement en image."; fi
echo
echo "==============================================================="
echo " VALIDATION OK"
echo " About/Help V2.4 est installé correctement."
echo " Le faux positif venait du footer global."
echo "==============================================================="
sudo -i
pincabos --check
sudo -i
