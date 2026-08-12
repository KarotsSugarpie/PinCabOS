# ------------------------------------------------------------
# Swap
# ------------------------------------------------------------
/swap.img
/swapfile

# ------------------------------------------------------------
# Pseudo-filesystems Linux
# ------------------------------------------------------------
/proc/**
/sys/**
/dev/**
/run/**
/tmp/**

# ------------------------------------------------------------
# Montages externes
# ------------------------------------------------------------
/mnt/**
/media/**

# ------------------------------------------------------------
# Journaux runtime
# ------------------------------------------------------------
/var/log/**
/var/tmp/**

# ------------------------------------------------------------
# Cache systeme
# ------------------------------------------------------------
/var/cache/**

# ------------------------------------------------------------
# Python genere
# ------------------------------------------------------------
**/__pycache__/**
**/*.pyc
**/*.pyo

# Environnements Python reconstruisibles
**/.venv/**
**/venv/**

# ------------------------------------------------------------
# Node genere
# ------------------------------------------------------------
**/node_modules/**

# ------------------------------------------------------------
# Caches utilisateur
# ------------------------------------------------------------
/home/*/.cache/**
/root/.cache/**

# ------------------------------------------------------------
# Navigateurs / profils runtime
# ------------------------------------------------------------
/home/*/.config/google-chrome/**
/home/*/.config/chromium/**

# ------------------------------------------------------------
# Git imbrique
# ------------------------------------------------------------
**/.git/**
EOF

cat /opt/pincabos/.gitignore-rootfs
clear
echo "==============================================================="
echo " PINCABOS — AUDIT SOURCE ROOTFS POUR GITHUB"
echo "==============================================================="
TMP="/tmp/pincabos-github-source-files.txt"
: > "$TMP"
for ROOT in     /etc     /opt     /home/pinball     /root     /usr/local     /srv     /var/www; do     if [ -e "$ROOT" ]; then         find "$ROOT" -xdev -type f -printf '%s\t%p\n' 2>/dev/null;     fi; done > "$TMP"
echo
echo "=== Taille brute des zones PinCabOS ==="
awk -F '\t' '{s += $1} END {
    printf "%.2f GiB\n", s/1024/1024/1024
}' "$TMP"
echo
echo "=== Fichiers > 95 MiB AVANT exclusions fines ==="
awk -F '\t' '$1 > 99614720 {print}' "$TMP"     | sort -nr     | while IFS=$'\t' read -r size file; do     printf "%-10s %s\n"         "$(numfmt --to=iec "$size")"         "$file"; done
echo
echo "=== Taille des principales zones ==="
du -sh     /etc     /opt     /home/pinball     /root     /usr/local     /srv     /var/www     2>/dev/null || true
clear
set -e
ISO="/opt/pincabos/script/iso.sh"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="${ISO}.before-remove-old-webroot-${STAMP}"
echo "==============================================================="
echo " PINCABOS — RETRAIT ANCIEN WEBROOT"
echo "==============================================================="
test -f "$ISO" || {     echo "ERREUR [X] $ISO introuvable";     exit 1; }
bash -n "$ISO" || {     echo "ERREUR [X] iso.sh invalide avant modification";     exit 1; }
echo
echo "=== 1) Sauvegarde ==="
cp -a "$ISO" "$BACKUP"
echo "GO [OK] $BACKUP"
echo
echo "=== 2) Correction publication Web ==="
python3 - "$ISO" <<'PY'
from pathlib import Path
import sys

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

OLD = """/var/www/update.pincabos.cc/updates"""

if OLD not in s:
    print("INFO : ancien WebRoot déjà absent.")
else:
    # Cas du bloc WEB_INDEX_SYNC_V2
    old_array = '''WEB_ROOTS=(
    "/var/www/html/updates"
    "/var/www/update.pincabos.cc/updates"
)'''

    new_array = '''WEB_ROOTS=(
    "/var/www/html/updates"
)'''

    if old_array in s:
        s = s.replace(old_array, new_array, 1)
        print("GO [OK] WEB_ROOTS réduit à /var/www/html/updates")
    else:
        # Sécurité : ne pas faire un remplacement aveugle.
        raise SystemExit(
            "ERREUR: ancien chemin trouvé, mais structure WEB_ROOTS inconnue."
        )

    # Nettoyage de quelques commentaires/messages uniquement.
    s = s.replace(
        "# Synchronise toutes les racines Web PinCabOS connues.",
        "# Synchronise la racine Web PinCabOS active."
    )

    s = s.replace(
        "# Les deux arbres existent actuellement sur le serveur.",
        "# Racine Web PinCabOS active."
    )

    s = s.replace(
        'echo "=== SHA256 DES DEUX COPIES ==="',
        'echo "=== SHA256 ISO PUBLIEE ==="'
    )

    s = s.replace(
        'echo "GO [OK] TOUS LES INDEX WEB SONT SYNCHRONISES"',
        'echo "GO [OK] INDEX WEB SYNCHRONISE"'
    )

    s = s.replace(
        'echo "GO [OK] synchronisation automatique des index terminee"',
        'echo "GO [OK] mise a jour automatique de l index terminee"'
    )

p.write_text(s, encoding="utf-8")
PY

echo
echo "=== 3) Validation syntaxique ==="
if ! bash -n "$ISO"; then     echo "ERREUR [X] iso.sh invalide après modification";     echo "Restauration...";     cp -a "$BACKUP" "$ISO";     exit 1; fi
echo "GO [OK] bash -n"
echo
echo "=== 4) Vérification ancien chemin ==="
OLD_COUNT="$(
    grep -c '/var/www/update\.pincabos\.cc/updates' "$ISO" || true
)"
echo "Ancien WebRoot : $OLD_COUNT occurrence(s)"
if [ "$OLD_COUNT" != "0" ]; then     echo "ERREUR [X] ancien chemin encore présent";     cp -a "$BACKUP" "$ISO";     exit 1; fi
echo "GO [OK] ancien WebRoot retiré"
echo
echo "=== 5) WebRoot actif ==="
grep -n -A5 -B2     'WEB_ROOTS=('     "$ISO" || true
echo
echo "=== 6) REMOTE_ROOT principal ==="
grep -n     'REMOTE_ROOT='     "$ISO" | tail -10
echo
echo "=== 7) SHA256 ==="
sha256sum "$BACKUP"
sha256sum "$ISO"
echo
echo "==============================================================="
echo " GO [OK] PUBLICATION WEB CORRIGEE"
echo "==============================================================="
echo
echo "WebRoot actif : /var/www/html/updates"
echo "ISO distante  : /var/www/html/updates/iso"
clear
set -euo pipefail
echo "==============================================================="
echo " PINCABOS — INITIALISATION GIT ROOTFS + AUDIT FILTRE"
echo "==============================================================="
GITDIR="/opt/pincabos/.git-rootfs"
EXCLUDE="/opt/pincabos/config/github-rootfs-exclude.txt"
MANIFEST="/opt/pincabos/system-manifests"
mkdir -p /opt/pincabos/config
mkdir -p "$MANIFEST"
echo
echo "=== 1. Mise a jour des manifests systeme ==="
dpkg-query -W -f='${binary:Package}\t${Version}\n'     > "$MANIFEST/apt-packages.tsv"
apt-mark showmanual     > "$MANIFEST/apt-manual-packages.txt"
uname -a     > "$MANIFEST/kernel.txt"
cat /etc/os-release     > "$MANIFEST/os-release.txt"
systemctl list-unit-files --state=enabled --no-pager     > "$MANIFEST/systemd-enabled.txt"
snap list > "$MANIFEST/snap-packages.txt" 2>/dev/null || true
flatpak list > "$MANIFEST/flatpak-packages.txt" 2>/dev/null || true
echo "GO [√] Manifests crees"
echo
echo "=== 2. Creation des exclusions RootFS ==="
cat > "$EXCLUDE" <<'EOF'
# ============================================================
# PinCabOS — Git RootFS exclusions
# ============================================================

# ------------------------------------------------------------
# Le depot Git lui-meme
# ------------------------------------------------------------
/opt/pincabos/.git-rootfs/

# ------------------------------------------------------------
# TABLES — jamais publiees
# ------------------------------------------------------------
/home/pinball/Tables/
/home/pinball/tables/

# ------------------------------------------------------------
# Imports / exports de tables
# ------------------------------------------------------------
/home/pinball/Exports/
/home/pinball/Downloads/

# ------------------------------------------------------------
# ISO — jamais publiees
# ------------------------------------------------------------
*.iso
*.ISO

# ------------------------------------------------------------
# Swap
# ------------------------------------------------------------
/swap.img
/swapfile

# ------------------------------------------------------------
# Pseudo-filesystems / runtime Linux
# ------------------------------------------------------------
/proc/
/sys/
/dev/
/run/
/tmp/
/lost+found/

# ------------------------------------------------------------
# Disques, NAS et montages externes
# ------------------------------------------------------------
/mnt/
/media/
/snap/

# ------------------------------------------------------------
# Logs / caches
# ------------------------------------------------------------
/var/log/
/var/tmp/
/var/cache/

# ------------------------------------------------------------
# Etats de paquets reconstruisibles
# ------------------------------------------------------------
/var/lib/apt/
/var/lib/dpkg/
/var/lib/kdump/
/var/lib/snapd/
/var/lib/flatpak/

# ------------------------------------------------------------
# Docker runtime — pas les fichiers source
# ------------------------------------------------------------
/var/lib/docker/
/var/lib/containerd/

# ------------------------------------------------------------
# Ubuntu — binaires fournis par les paquets
# On les reconstruit avec apt-packages.tsv
# ------------------------------------------------------------
/boot/
/bin/
/sbin/
/lib/
/lib32/
/lib64/

/usr/bin/
/usr/sbin/
/usr/lib/
/usr/lib32/
/usr/lib64/
/usr/libexec/
/usr/share/
/usr/include/
/usr/src/

# /usr/local RESTE inclus

# ------------------------------------------------------------
# Chrome installe
# ------------------------------------------------------------
/opt/google/

# ------------------------------------------------------------
# Donnees generees du builder PinCabOS
# ------------------------------------------------------------
/opt/pincabos/build/output/
/opt/pincabos/build/known-good/
/opt/pincabos/cache/iso-base/
/opt/pincabos/build/legacy-package-builder/pilot-*/

# ------------------------------------------------------------
# VPinFE — packages de mise a jour telecharges
# ------------------------------------------------------------
/home/pinball/.config/vpinfe/updates/

# ------------------------------------------------------------
# Python — environnements reconstruisibles
# ------------------------------------------------------------
**/.venv/
**/venv/
**/__pycache__/
**/*.pyc
**/*.pyo

# ------------------------------------------------------------
# Node
# ------------------------------------------------------------
**/node_modules/

# ------------------------------------------------------------
# Caches utilisateurs
# ------------------------------------------------------------
/home/*/.cache/
/root/.cache/

# ------------------------------------------------------------
# Corbeilles
# ------------------------------------------------------------
/home/*/.local/share/Trash/

# ------------------------------------------------------------
# Profils navigateurs / sessions
# ------------------------------------------------------------
/home/*/.config/google-chrome/
/home/*/.config/chromium/
/home/*/.mozilla/

# ------------------------------------------------------------
# Cles d'authentification de la MACHINE
# Les mots de passe/configs PinCabOS restent publies.
# ------------------------------------------------------------
/root/.ssh/
/home/*/.ssh/

/etc/ssh/ssh_host_*_key
/etc/ssh/ssh_host_*_key.pub

/etc/shadow
/etc/shadow-
/etc/gshadow
/etc/gshadow-

/etc/ssl/private/
/etc/NetworkManager/system-connections/

# ------------------------------------------------------------
# Git imbriques : garder le code, pas leurs metadata .git
# ------------------------------------------------------------
**/.git/
EOF

echo "GO [√] Exclusions creees : $EXCLUDE"
echo
echo "=== 3. Initialisation de l'index Git RootFS ==="
if [ ! -d "$GITDIR/objects" ]; then     mkdir -p "$GITDIR";      git       --git-dir="$GITDIR"       --work-tree=/       init; fi
git --git-dir="$GITDIR" --work-tree=/     symbolic-ref HEAD refs/heads/main
git --git-dir="$GITDIR" --work-tree=/     config user.name "KarotsSugarpie"
git --git-dir="$GITDIR" --work-tree=/     config user.email "jrl@jrlinfo.com"
mkdir -p "$GITDIR/info"
cp -f "$EXCLUDE" "$GITDIR/info/exclude"
echo "GO [√] Git RootFS initialise"
echo
echo "=== 4. Creation d'une commande pincabos-git ==="
cat > /usr/local/bin/pincabos-git <<'EOF'
#!/bin/bash
exec git \
  --git-dir=/opt/pincabos/.git-rootfs \
  --work-tree=/ \
  "$@"
EOF

chmod 755 /usr/local/bin/pincabos-git
echo "GO [√] Commande disponible : pincabos-git"
echo
echo "=== 5. Verification des exclusions critiques ==="
for TEST in     "home/pinball/Tables"     "home/pinball/Exports"     "home/pinball/Downloads"     "opt/pincabos/build/output"     "opt/google"     "var/log"     "usr/lib"; do     printf "%-50s : " "/$TEST";      if pincabos-git check-ignore -q "$TEST" 2>/dev/null; then         echo "EXCLU [√]";     else         echo "A VERIFIER";     fi; done
echo
echo "=== 6. Construction de la liste REELLE qui entrerait dans Git ==="
CANDIDATES="/tmp/pincabos-github-candidates.z"
pincabos-git ls-files     --others     --exclude-standard     -z > "$CANDIDATES"
echo
echo "=== 7. Analyse de taille apres exclusions ==="
python3 <<'PY'
import os

candidate_file = "/tmp/pincabos-github-candidates.z"

with open(candidate_file, "rb") as f:
    entries = [x.decode("utf-8", "surrogateescape")
               for x in f.read().split(b"\0") if x]

total = 0
count = 0
large = []
by_root = {}

for rel in entries:
    path = "/" + rel

    try:
        st = os.lstat(path)
    except (FileNotFoundError, PermissionError):
        continue

    if not os.path.isfile(path):
        size = st.st_size if os.path.islink(path) else 0
    else:
        size = st.st_size

    total += size
    count += 1

    root = rel.split("/", 1)[0]
    by_root[root] = by_root.get(root, 0) + size

    if size > 95 * 1024 * 1024:
        large.append((size, path))


def human(n):
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    x = float(n)

    for u in units:
        if x < 1024 or u == units[-1]:
            return f"{x:.2f} {u}"
        x /= 1024


print()
print("===============================================================")
print(" RESULTAT APRES EXCLUSIONS")
print("===============================================================")
print()
print(f"Nombre de fichiers : {count}")
print(f"Taille totale      : {human(total)}")

print()
print("Taille par zone :")

for root, size in sorted(
    by_root.items(),
    key=lambda x: x[1],
    reverse=True
):
    print(f"  /{root:<20} {human(size)}")

print()
print("Fichiers > 95 MiB :")

if not large:
    print("  AUCUN [√]")
else:
    for size, path in sorted(large, reverse=True):
        print(f"  {human(size):>12}  {path}")

print()
print("===============================================================")
PY

echo
echo "=== 8. Verification Tables ==="
TABLE_COUNT="$(
    pincabos-git ls-files \
      --others \
      --exclude-standard \
    | grep -E '^home/pinball/[Tt]ables/' \
    | wc -l
)"
