#!/usr/bin/env bash
set -Eeuo pipefail

clear
echo "==============================================================="
echo " PINCABOS — MASTER ISO BUILDER V8.1G ENGLISH"
echo " Clean -> Payload -> ISO-ready -> Live installer -> Bootable ISO"
echo "==============================================================="

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run as root"
  exit 1
fi

VERSION="v8.1g"
VERSION_UPPER="V8.1G"

CACHE_DIR="/opt/pincabos/cache/iso-base"

BUILD_BASE="/opt/pincabos/build"
WORK="$BUILD_BASE/live-v8.1g-english"
PAYLOAD_FULL="$WORK/payload-full"
ISO_DIR="$WORK/iso"
ROOTFS_DIR="$WORK/squashfs-root"

OUT_DIR="$BUILD_BASE/output"
OUT_ISO="$OUT_DIR/PinCabOS-beta-Installer.iso"

# PINCABOS_ISO_MODELE_LIVE_V2
# Le modele live est LE modele (decision Yann + Karots 05/09/2026) : le payload
# EST le systeme live (casper/filesystem.squashfs), meme noyau, memes pilotes,
# memes outils que le cab installe ; l assistant graphique y voit le vrai
# materiel. L ISO est produite par iso-live.sh. Le modele classique (base Ubuntu
# live-server + payload en morceaux, sections 9-11 et 14-20) a ete retire :
# --classic refuse, --live reste accepte par compatibilite.
PCO_ISO_MODEL="live"
for pco_arg in "$@"; do
  case "$pco_arg" in
    --live) ;;
    --classic) echo "ERROR: le modele classique a ete retire (PINCABOS_ISO_MODELE_LIVE_V2) : l ISO est le systeme, voir iso-live.sh"; exit 2 ;;
  esac
done
LIVE_ROOTFS="$WORK/live-rootfs"
# PINCABOS_INSTALLEUR_FICHIERS_V1 : le moteur d installation, le helper de payload,
# l attente du media et l unite tty sont des fichiers du depot (opt/pincabos/script/installer/),
# installes tels quels ; plus de heredoc.
INSTALLER_SRC="$(dirname "$(readlink -f "$0")")/installer"
[ -d "$INSTALLER_SRC" ] || INSTALLER_SRC="/opt/pincabos/script/installer"
echo "ISO model: $PCO_ISO_MODEL"

LOG_DIR="$BUILD_BASE/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/iso-v8.1g-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1

echo
echo "Log:"
echo "$LOG"

die() {
  echo
  echo "ERROR: $*"
  exit 1
}

run() {
  echo
  echo ">>> $*"
  "$@"
}

cleanup_mounts() {
  set +e
  for p in "$ROOTFS_DIR/dev" "$ROOTFS_DIR/proc" "$ROOTFS_DIR/sys" "$ROOTFS_DIR/run"; do
    mountpoint -q "$p" && umount -R "$p"
  done
  set -e
}
trap cleanup_mounts EXIT

echo
echo "=== 1) Safety audit before cleanup ==="
echo "Build base: $BUILD_BASE"
echo "Work dir:   $WORK"
echo "Output ISO: $OUT_ISO"
df -h /
du -sh "$BUILD_BASE" 2>/dev/null || true
du -sh /root/pincabos-v8.1g-cab-payload 2>/dev/null || true
du -sh /root/pincabos-v8.1g-iso-ready 2>/dev/null || true

echo
echo "=== 2) Cleanup obsolete/generated build files only ==="
echo "Cleaning generated build work, old payloads and old ISOs."
echo "The installed PinCabOS system is NOT touched."
echo "PINCABOS_V81G_GENERATED_CLEANUP_V2"

mkdir -p "$BUILD_BASE" "$OUT_DIR" "$CACHE_DIR"

echo
echo "--- Before cleanup ---"
du -sh "$BUILD_BASE" "$OUT_DIR" /root/pincabos-v8* 2>/dev/null || true

echo
echo "--- Removing current/old generated live build work ---"
rm -rf "$WORK"

find "$BUILD_BASE" -mindepth 1 -maxdepth 1 -type d \( \
  -name 'live-v8*' -o \
  -name 'pincabos-v8*-cab-payload' -o \
  -name 'pincabos-v8*-iso-ready' -o \
  -name 'pincabos-v8*-payload' -o \
  -name 'cab-payload-v8*' -o \
  -name 'iso-ready-v8*' \
\) -print -exec rm -rf {} + 2>/dev/null || true

echo
echo "--- Removing old generated ISO outputs ---"
find "$OUT_DIR" -maxdepth 1 -type f \( \
  -name 'PinCabOS-*.iso' -o \
  -name 'PinCabOS-*.iso.sha256' -o \
  -name '*.iso.part' \
\) -print -delete 2>/dev/null || true

echo
echo "--- Removing old generated root payload directories only ---"
find /root -maxdepth 1 -type d \( \
  -name 'pincabos-v8*-cab-payload' -o \
  -name 'pincabos-v8*-iso-ready' -o \
  -name 'pincabos-v8*-payload' \
\) -print -exec rm -rf {} + 2>/dev/null || true

echo
echo "--- Removing accidental root-level generated payload files only ---"
echo "PINCABOS_ROOT_GENERATED_PAYLOAD_CLEANUP_V1"

find / \
  -maxdepth 1 \
  -type f \
  \( \
    -name 'pincabos-rootfs-cab-*.tar.zst' -o \
    -name 'pincabos-rootfs-cab-*.tar.zst.part-*' -o \
    -name 'pincabos-rootfs-cab-*.sha256' -o \
    -name 'pincabos-rootfs-cab-*.manifest.txt' -o \
    -name 'pincabos-plymouth-theme-overlay-*.tar.zst' -o \
    -name 'pincabos-plymouth-theme-overlay-*.tar.zst.part-*' -o \
    -name 'pincabos-plymouth-theme-overlay-*.sha256' -o \
    -name 'payload-file-list-python-webapp.txt' -o \
    -name 'MANIFEST.txt' \
  \) \
  -print \
  -delete \
  2>/dev/null || true

echo
echo "--- Removing stale partial downloads only ---"
find "$CACHE_DIR" -maxdepth 1 -type f -name '*.part' -print -delete 2>/dev/null || true

echo
echo "--- After cleanup ---"
du -sh "$BUILD_BASE" "$OUT_DIR" /root/pincabos-v8* 2>/dev/null || true

mkdir -p "$PAYLOAD_FULL" "$ISO_DIR" "$ROOTFS_DIR" "$OUT_DIR" "$CACHE_DIR"

echo
echo "=== 3) Install required host builder tools ==="
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  xorriso \
  squashfs-tools \
  rsync \
  wget \
  zstd \
  ca-certificates \
  parted \
  dosfstools \
  gdisk \
  util-linux \
  coreutils \
  grub-pc-bin \
  grub-efi-amd64-bin \
  mtools \
  e2fsprogs

echo
echo "=== 4) Validate source cabinet boot, modules, GRUB and Plymouth ==="
test -d /boot || die "/boot missing"
test -d /lib/modules || die "/lib/modules missing"
test -f /etc/default/grub || die "/etc/default/grub missing"
test -f /usr/share/plymouth/themes/pincabos/pincabos.plymouth || die "Plymouth pincabos theme missing"
ls /boot/vmlinuz-* >/dev/null || die "No kernel in /boot"
ls /boot/initrd.img-* >/dev/null || die "No initrd in /boot"
ls /lib/modules/* >/dev/null || die "No modules in /lib/modules"

echo "OK: source boot/modules/grub/plymouth present"

echo
echo "=== 5) Build lean PinCabOS payload from current cabinet ==="
ARCHIVE="$PAYLOAD_FULL/pincabos-rootfs-cab-v8.1g.tar.zst"
OVERLAY="$PAYLOAD_FULL/pincabos-plymouth-theme-overlay-v8.1g.tar.zst"
MANIFEST="$PAYLOAD_FULL/pincabos-rootfs-cab-v8.1g.manifest.txt"

{
  echo "PinCabOS V8.1G LEAN CAB PAYLOAD"
  echo "Generated: $(date -Is)"
  echo
  echo "Excluded:"
  echo "/home/pinball/Tables"
  echo "/opt/pincabos/build"
  echo "/swap.img"
  echo "/swapfile"
  echo "venv/.venv/virtualenv preserved when needed for WebApp runtime"
  echo "node_modules"
  echo "__pycache__"
  echo "/root old payloads"
  echo "/opt/pincabos/cache"
  echo "/opt/pincabos/logs"
  echo "/var/tmp, /var/crash, /var/cache, /var/log, apt archives, journals"
  echo
  findmnt /
  echo
  ls -lah /boot/vmlinuz-* /boot/initrd.img-* 2>/dev/null || true
  echo
  ls -lah /lib/modules
  echo
  cat /etc/default/grub
  echo
  find /usr/share/plymouth/themes/pincabos -maxdepth 2 -type f | sort
} > "$MANIFEST"

sed -n '1,140p' "$MANIFEST"

# PINCABOS_ISO_LEAN_EXCLUSIONS_V2
# PINCABOS_PAYLOAD_LIVE_TAR_STABILITY_V2
# PINCABOS_ISO_AUDIO_PRIVACY_V1
#
# Prépare une copie neutre des VPinballX.ini sans noms de cartes audio.
# La configuration originale du cabinet source n'est jamais modifiée.

AUDIO_SANITIZE_STAGE="/tmp/pincabos-audio-sanitize-$$"
AUDIO_SANITIZE_LIST="/tmp/pincabos-audio-sanitize-list-$$"

rm -rf "$AUDIO_SANITIZE_STAGE"
rm -f "$AUDIO_SANITIZE_LIST"

mkdir -p \
  "$AUDIO_SANITIZE_STAGE/__PINCABOS_AUDIO_SANITIZED__"

: > "$AUDIO_SANITIZE_LIST"

python3 - \
  "$AUDIO_SANITIZE_STAGE/__PINCABOS_AUDIO_SANITIZED__" \
  "$AUDIO_SANITIZE_LIST" <<'PINCABOS_AUDIO_PRIVACY_PY'
from pathlib import Path
import os
import re
import shutil
import sys

stage = Path(sys.argv[1])
list_file = Path(sys.argv[2])

sources = []

roots = [
    # PINCABOS_VPX_PREF_PATH_V1 : preferences VPX (-PrefPath) depuis Alpha 3.0x ;
    # ~/.local/share/VPinballX/10.8 n'est plus qu'un lien vers ce dossier, et
    # rglob ne suit pas les liens : sans cette racine le fichier reel partait
    # dans la photo avec les noms de cartes audio du master (garde audio).
    Path("/home/pinball/.pincabos/vpx"),
    Path("/home/pinball/.local/share/VPinballX"),
    Path("/home/pinball/.vpinball"),
]

for root in roots:
    if not root.exists():
        continue

    sources.extend(
        candidate
        for candidate in root.rglob("VPinballX.ini")
        if candidate.is_file() and not candidate.is_symlink()
    )

hardware_audio_key = re.compile(
    r"^\s*("
    r"SoundDevice|"
    r"SoundDeviceBG|"
    r"MusicDevice|"
    r"Sound3DDevice|"
    r"AudioDevice|"
    r"AudioDeviceBG"
    r")\s*=.*$",
    re.IGNORECASE,
)

archive_members = []

for source in sorted(set(sources)):
    relative = source.relative_to("/")

    destination = stage / relative
    destination.parent.mkdir(parents=True, exist_ok=True)

    original = source.read_text(
        encoding="utf-8",
        errors="replace",
    )

    lines = original.splitlines(keepends=True)

    sanitized = "".join(
        line
        for line in lines
        if not hardware_audio_key.match(line)
    )

    destination.write_text(
        sanitized,
        encoding="utf-8",
    )

    source_stat = source.stat()

    os.chmod(
        destination,
        source_stat.st_mode & 0o7777,
    )

    os.chown(
        destination,
        source_stat.st_uid,
        source_stat.st_gid,
    )

    archive_members.append(
        "./__PINCABOS_AUDIO_SANITIZED__/"
        + str(relative)
    )

list_file.write_text(
    "".join(member + "\n" for member in archive_members),
    encoding="utf-8",
)

print(
    f"GO [√] VPinballX.ini neutralisés : "
    f"{len(archive_members)}"
)
PINCABOS_AUDIO_PRIVACY_PY

if [ "$?" -ne 0 ]; then
  die "Unable to prepare sanitized VPX audio configuration"
fi

# PINCABOS_VPXTOOL_ISO_EMBED_V1
#
# Every freshly built ISO must contain the exact vpxtool pinned by the same
# manifest used by the runtime updater.  Never depend on a manually installed
# copy on the source cabinet.  Download into /tmp, verify SHA-256, validate the
# binary, and overlay it into the payload TAR without modifying the cabinet.
VPXTOOL_MANIFEST="/opt/pincabos/update/vpxtool-release.json"
VPXTOOL_STAGE="/tmp/pincabos-vpxtool-iso-$$"
VPXTOOL_PAYLOAD_ROOT="$VPXTOOL_STAGE/__PINCABOS_VPXTOOL_EMBEDDED__"
VPXTOOL_DOWNLOAD_DIR="$VPXTOOL_STAGE/download"
VPXTOOL_EXTRACT_DIR="$VPXTOOL_STAGE/extract"

test -s "$VPXTOOL_MANIFEST" \
  || die "vpxtool release manifest missing: $VPXTOOL_MANIFEST"

case "$(uname -m)" in
  x86_64|amd64) VPXTOOL_ARCH="x86_64" ;;
  aarch64|arm64) VPXTOOL_ARCH="aarch64" ;;
  *) die "Unsupported vpxtool build architecture: $(uname -m)" ;;
esac

rm -rf "$VPXTOOL_STAGE"
mkdir -p "$VPXTOOL_DOWNLOAD_DIR" "$VPXTOOL_EXTRACT_DIR" "$VPXTOOL_PAYLOAD_ROOT"

mapfile -t VPXTOOL_META < <(
  python3 - "$VPXTOOL_MANIFEST" "$VPXTOOL_ARCH" <<'PINCABOS_VPXTOOL_META_PY'
import json
import re
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
arch = sys.argv[2]
data = json.loads(manifest_path.read_text(encoding="utf-8"))
version = str(data.get("version") or "").strip().lstrip("v")
if not re.fullmatch(r"\d+(?:\.\d+){2,3}", version):
    raise SystemExit(f"invalid vpxtool version in manifest: {version!r}")
sha = str(data["sha256"][arch]).strip().lower()
if not re.fullmatch(r"[0-9a-f]{64}", sha):
    raise SystemExit(f"invalid vpxtool sha256 for {arch}")
base = str(data["release_base_template"]).format(version=version).rstrip("/")
name = str(data["archive_template"]).format(arch=arch, version=version)
print(version)
print(f"{base}/{name}")
print(sha)
PINCABOS_VPXTOOL_META_PY
)

[ "${#VPXTOOL_META[@]}" -eq 3 ] \
  || die "Unable to resolve vpxtool release metadata"

VPXTOOL_VERSION="${VPXTOOL_META[0]}"
VPXTOOL_URL="${VPXTOOL_META[1]}"
VPXTOOL_SHA256="${VPXTOOL_META[2]}"
VPXTOOL_ARCHIVE="$VPXTOOL_DOWNLOAD_DIR/vpxtool.tar.gz"

echo "Embedding vpxtool v$VPXTOOL_VERSION ($VPXTOOL_ARCH) into ISO payload"
wget -q --show-progress -O "$VPXTOOL_ARCHIVE" "$VPXTOOL_URL" \
  || die "Unable to download pinned vpxtool archive"

echo "$VPXTOOL_SHA256  $VPXTOOL_ARCHIVE" | sha256sum -c - \
  || die "vpxtool archive SHA-256 mismatch"

tar --no-same-owner --no-same-permissions -xzf "$VPXTOOL_ARCHIVE" \
  -C "$VPXTOOL_EXTRACT_DIR" \
  || die "Unable to extract pinned vpxtool archive"

VPXTOOL_SOURCE_BIN="$(find "$VPXTOOL_EXTRACT_DIR" -type f -name vpxtool -print -quit)"
[ -n "$VPXTOOL_SOURCE_BIN" ] && [ -f "$VPXTOOL_SOURCE_BIN" ] \
  || die "vpxtool binary missing from pinned archive"

VPXTOOL_VERSION_DIR="$VPXTOOL_PAYLOAD_ROOT/opt/pincabos/apps/vpxtool/$VPXTOOL_VERSION"
VPXTOOL_STAGED_BIN="$VPXTOOL_VERSION_DIR/vpxtool"
install -D -m 0755 "$VPXTOOL_SOURCE_BIN" "$VPXTOOL_STAGED_BIN"
ln -s "$VPXTOOL_VERSION" "$VPXTOOL_PAYLOAD_ROOT/opt/pincabos/apps/vpxtool/current"
mkdir -p "$VPXTOOL_PAYLOAD_ROOT/opt/pincabos/bin"
ln -s "/opt/pincabos/apps/vpxtool/current/vpxtool" \
  "$VPXTOOL_PAYLOAD_ROOT/opt/pincabos/bin/vpxtool"

VPXTOOL_VERSION_TEXT="$("$VPXTOOL_STAGED_BIN" --version 2>&1)"
printf '%s\n' "$VPXTOOL_VERSION_TEXT" | grep -Fq "v$VPXTOOL_VERSION" \
  || die "Staged vpxtool does not report v$VPXTOOL_VERSION"
"$VPXTOOL_STAGED_BIN" patch --help >/dev/null 2>&1 \
  || die "Staged vpxtool does not provide the patch command"

echo "GO [OK] vpxtool v$VPXTOOL_VERSION pinned and staged for ISO"

# PINCABOS_ROOT_GENERATED_PAYLOAD_EXCLUSIONS_V1
echo "Creating live cabinet payload with controlled TAR status."

set +e

tar \
  --checkpoint=10000 \
  --checkpoint-action=echo='archived %u entries...' \
  --acls \
  --xattrs \
  --numeric-owner \
  --one-file-system \
  --ignore-failed-read \
  --warning=no-file-changed \
  --exclude='./boot/efi' \
  --exclude='./boot/efi/*' \
  --exclude='./proc/*' \
  --exclude='./sys/*' \
  --exclude='./dev/*' \
  --exclude='./run/*' \
  --exclude='./tmp/*' \
  --exclude='./mnt/*' \
  --exclude='./media/*' \
  --exclude='./cdrom/*' \
  --exclude='./lost+found' \
  --exclude='./swap.img' \
  --exclude='./swapfile' \
  --exclude='./home/pinball/Tables' \
  --exclude='./home/pinball/Tables/*' \
  --exclude='./home/pinball/Backups/*' \
  --exclude='./home/pinball/pincabos-*' \
  --exclude='./home/pinball/vpinfe.pre-*' \
  --exclude='./home/pinball/Downloads/*' \
  --exclude='./home/pinball/.cache' \
  --exclude='./home/pinball/.cache/*' \
  --exclude='./home/pinball/Exports' \
  --exclude='./home/pinball/Exports/*' \
  --exclude='./home/pinball/.ssh' \
  --exclude='./home/pinball/.ssh/*' \
  --exclude='./home/pinball/.config/gh' \
  --exclude='./home/pinball/.config/gh/*' \
  --exclude='./home/pinball/.config/google-chrome' \
  --exclude='./home/pinball/.config/google-chrome/*' \
  --exclude='./home/pinball/.config/vpinfe/cache' \
  --exclude='./home/pinball/.config/vpinfe/cache/*' \
  --exclude='./home/pinball/.config/vpinfe/updates' \
  --exclude='./home/pinball/.config/vpinfe/updates/*' \
  --exclude='./home/pinball/.config/vpinfe/vpinfe.log' \
  --exclude='./home/pinball/.config/sunshine/credentials' \
  --exclude='./home/pinball/.config/pincabos/smb' \
  --exclude='./home/pinball/.config/pincabos/smb/*' \
  --exclude='./home/pinball/.config/pincabos/smb-sessions' \
  --exclude='./home/pinball/.config/pincabos/smb-sessions/*' \
  --exclude='./home/pinball/.local/share/Trash/*' \
  --exclude='./home/*/snap' \
  --exclude='./home/*/snap/*' \
  --exclude='./snap' \
  --exclude='./snap/*' \
  --exclude='./var/snap' \
  --exclude='./var/snap/*' \
  --exclude='./var/lib/snapd' \
  --exclude='./var/lib/snapd/*' \
  --exclude='./etc/asound.conf' \
  --exclude='./var/lib/alsa' \
  --exclude='./var/lib/alsa/*' \
  --exclude='./var/lib/pipewire' \
  --exclude='./var/lib/pipewire/*' \
  --exclude='./home/pinball/.asoundrc' \
  --exclude='./home/pinball/.config/pulse' \
  --exclude='./home/pinball/.config/pulse/*' \
  --exclude='./home/pinball/.config/pipewire' \
  --exclude='./home/pinball/.config/pipewire/*' \
  --exclude='./home/pinball/.config/wireplumber' \
  --exclude='./home/pinball/.config/wireplumber/*' \
  --exclude='./home/pinball/.local/state/pipewire' \
  --exclude='./home/pinball/.local/state/pipewire/*' \
  --exclude='./home/pinball/.local/state/wireplumber' \
  --exclude='./home/pinball/.local/state/wireplumber/*' \
  --exclude='./opt/pincabos/config/audio-router.json' \
  --exclude='./opt/pincabos/config/audio.json' \
  --exclude='./opt/pincabos/config/audio-ssf.json' \
  --exclude='./opt/pincabos/config/ssf-commander.json' \
  --exclude='./opt/pincabos/backups/*audio*' \
  --exclude='./opt/pincabos/backups/*audio*/*' \
  --exclude='./home/pinball/.local/share/VPinballX/*/VPinballX.ini' \
  --exclude='./home/pinball/.vpinball/VPinballX.ini' \
  --exclude='./home/pinball/.pincabos/vpx/VPinballX.ini' \
  --exclude='./opt/pincabos/config/screens/screens.json' \
  --exclude='./opt/pincabos/config/screens/bindings.json' \
  --exclude='./opt/pincabos/config/screens/display-bindings.json' \
  --exclude='./opt/pincabos/config/screens/display-role-bindings.json' \
  --exclude='./home/pinball/.config/monitors.xml' \
  --exclude='./var/log/journal/*' \
  --exclude='./var/cache/apt/archives/*.deb' \
  --exclude='./var/lib/apt/lists' \
  --exclude='./var/lib/apt/lists/*' \
  --exclude='./var/backups' \
  --exclude='./var/backups/*' \
  --exclude='./var/tmp/*' \
  --exclude='./var/crash/*' \
  --exclude='./root/.cache' \
  --exclude='./root/.cache/*' \
  --exclude='./root/*' \
  --exclude='./pincabos-rootfs-cab-*.tar.zst' \
  --exclude='./pincabos-rootfs-cab-*.tar.zst.part-*' \
  --exclude='./pincabos-rootfs-cab-*.sha256' \
  --exclude='./pincabos-rootfs-cab-*.manifest.txt' \
  --exclude='./pincabos-plymouth-theme-overlay-*.tar.zst' \
  --exclude='./pincabos-plymouth-theme-overlay-*.tar.zst.part-*' \
  --exclude='./pincabos-plymouth-theme-overlay-*.sha256' \
  --exclude='./payload-file-list-python-webapp.txt' \
  --exclude='./MANIFEST.txt' \
  --exclude='./var/lib/kdump' \
  --exclude='./var/lib/kdump/*' \
  --exclude='./var/lib/systemd/coredump' \
  --exclude='./var/lib/systemd/coredump/*' \
  --exclude='./home/pinball/.nv' \
  --exclude='./home/pinball/.nv/*' \
  --exclude='./home/pinball/.dbus' \
  --exclude='./home/pinball/.dbus/*' \
  --exclude='./opt/pincabos/runtime/live-gpu' \
  --exclude='./opt/pincabos/runtime/live-gpu/*' \
  --exclude='./opt/pincabos/script/*.bak' \
  --exclude='./opt/pincabos/script/*.bak-*' \
  --exclude='./opt/pincabos/script/*.backup' \
  --exclude='./opt/pincabos/script/*.orig' \
  --exclude='./opt/pincabos/script/*~' \
  --exclude='./root/pincabos-v8.1-cab-payload' \
  --exclude='./root/pincabos-v8.1-cab-payload/*' \
  --exclude='./root/pincabos-v8.1f-iso-ready' \
  --exclude='./root/pincabos-v8.1f-iso-ready/*' \
  --exclude='./root/pincabos-v8.1g-cab-payload' \
  --exclude='./root/pincabos-v8.1g-cab-payload/*' \
  --exclude='./root/pincabos-v8.1g-iso-ready' \
  --exclude='./root/pincabos-v8.1g-iso-ready/*' \
  --exclude='./opt/pincabos/build' \
  --exclude='./opt/pincabos/build/*' \
  --exclude='./opt/pincabos/tmp' \
  --exclude='./opt/pincabos/tmp/*' \
  --exclude='./opt/pincabos/apps/vpxtool' \
  --exclude='./opt/pincabos/apps/vpxtool/*' \
  --exclude='./opt/pincabos/bin/vpxtool' \
  --exclude='./opt/pincabos/.git-rootfs' \
  --exclude='./opt/pincabos/.git-rootfs/*' \
  --exclude='./opt/pincabos/backups' \
  --exclude='./opt/pincabos/backups/*' \
  --exclude='./opt/pincabos/script/*.bak-*' \
  --exclude='./opt/pincabos/script/*.before-*' \
  --exclude='./opt/pincabos/web/*.bak-*' \
  --exclude='./opt/pincabos/web/*.before-*' \
  --exclude='./opt/pincabos/cache' \
  --exclude='./opt/pincabos/cache/*' \
  --exclude='./opt/pincabos/logs/*' \
  --exclude='./var/cache/*' \
  --exclude='./var/log/*' \
  --exclude='*/node_modules' \
  --exclude='*/node_modules/*' \
  --exclude='*/__pycache__' \
  --exclude='*/__pycache__/*' \
  --exclude='./__pincabos_keep_webapp_venv_runtime_marker_never_matches__' \
  -I 'zstd -T0 -10' \
  -cpf "$ARCHIVE" \
  --transform='s#^\./__PINCABOS_AUDIO_SANITIZED__$#.#' \
  --transform='s#^\./__PINCABOS_AUDIO_SANITIZED__/#./#' \
  --transform='s#^\./__PINCABOS_VPXTOOL_EMBEDDED__$#.#' \
  --transform='s#^\./__PINCABOS_VPXTOOL_EMBEDDED__/#./#' \
  -C / . \
  -C "$AUDIO_SANITIZE_STAGE" -T "$AUDIO_SANITIZE_LIST" \
  -C "$VPXTOOL_STAGE" \
    ./__PINCABOS_VPXTOOL_EMBEDDED__/opt/pincabos/apps/vpxtool \
    ./__PINCABOS_VPXTOOL_EMBEDDED__/opt/pincabos/bin/vpxtool

TAR_CREATE_RC="$?"

rm -rf "$AUDIO_SANITIZE_STAGE"
rm -f "$AUDIO_SANITIZE_LIST"
rm -rf "$VPXTOOL_STAGE"
set -e

echo
echo "=== Validate completed live payload archive ==="
echo "TAR_CREATE_RC=$TAR_CREATE_RC"

if [ "$TAR_CREATE_RC" -gt 1 ]; then
  die "Payload TAR creation failed with fatal status $TAR_CREATE_RC"
fi

if [ ! -s "$ARCHIVE" ]; then
  die "Payload archive is absent or empty: $ARCHIVE"
fi

echo "--- Zstandard integrity test ---"
zstd -t "$ARCHIVE"

echo "--- TAR stream readability test ---"
tar -I zstd -tf "$ARCHIVE" >/dev/null

# PINCABOS_ISO_AUDIO_PRIVACY_ARCHIVE_VALIDATION_V1

AUDIO_PRIVACY_FORBIDDEN_RE='^\./etc/asound\.conf$|^\./var/lib/alsa/|^\./var/lib/pipewire/|^\./home/pinball/\.asoundrc$|^\./home/pinball/\.config/(pulse|pipewire|wireplumber)(/|$)|^\./home/pinball/\.local/state/(pipewire|wireplumber)(/|$)|^\./opt/pincabos/config/(audio-router|audio|audio-ssf|ssf-commander)\.json$'

AUDIO_PRIVACY_FOUND="$(
  tar -I zstd -tf "$ARCHIVE" |
  grep -E "$AUDIO_PRIVACY_FORBIDDEN_RE" ||
  true
)"

if [ -n "$AUDIO_PRIVACY_FOUND" ]; then
  echo "$AUDIO_PRIVACY_FOUND"
  die "Personal audio state found inside payload"
fi

AUDIO_DEVICE_KEY_RE='^[[:space:]]*(SoundDevice|SoundDeviceBG|MusicDevice|Sound3DDevice|AudioDevice|AudioDeviceBG)[[:space:]]*='

while IFS= read -r VPX_INI_MEMBER; do
  [ -n "$VPX_INI_MEMBER" ] || continue

  if tar -I zstd -xOf "$ARCHIVE" "$VPX_INI_MEMBER" |
     grep -Eiq "$AUDIO_DEVICE_KEY_RE"
  then
    echo "Hardware audio key found in: $VPX_INI_MEMBER"
    die "Hardware-specific VPX audio configuration found"
  fi
done < <(
  tar -I zstd -tf "$ARCHIVE" |
  grep -E '/VPinballX\.ini$' ||
  true
)

echo "GO [√] Payload audio privacy validation passed"


echo "--- Completed live payload archive ---"
ls -lh "$ARCHIVE"

if [ "$TAR_CREATE_RC" -eq 1 ]; then
  echo "WARNING: TAR returned status 1 during live capture."
  echo "The completed archive passed both integrity tests."
else
  echo "OK: TAR completed with status 0."
fi

echo "GO [√] Live payload archive is structurally valid"


echo
echo "=== 6) Build Plymouth overlay ==="
tar \
  --acls \
  --xattrs \
  --numeric-owner \
  -I 'zstd -T0 -10' \
  -cpf "$OVERLAY" \
  -C / \
  usr/share/plymouth/themes/pincabos \
  etc/plymouth

echo
echo "=== 7) Validate payload exclusions and boot contents ==="
tar -I zstd -tf "$ARCHIVE" \
  | grep -E '^./boot/(vmlinuz|initrd.img|grub)|^./lib/modules/' \
  | sed -n '1,120p'

if tar -I zstd -tf "$ARCHIVE" | grep -q '^./home/pinball/Tables/'; then
  die "Tables included in payload"
fi
echo "OK: Tables excluded"

if tar -I zstd -tf "$ARCHIVE" | grep -q '^./opt/pincabos/build/'; then
  die "/opt/pincabos/build included in payload"
fi
echo "OK: /opt/pincabos/build excluded"


# PINCABOS_PAYLOAD_TRANSIENT_VALIDATION_V1
echo "=== Validation fichiers transitoires exclus ==="

if tar -I zstd -tf "$ARCHIVE" | grep -E -q \
'^\./opt/pincabos/(\.git-rootfs(/|$)|backups(/|$)|tmp(/|$)|script/.*\.(bak|before)-|web/.*\.(bak|before)-)'
then
    die "Fichiers transitoires PinCabOS inclus dans le payload"
fi

echo "OK: .git-rootfs excluded"
echo "OK: /opt/pincabos/backups excluded"
echo "OK: /opt/pincabos/tmp excluded"
echo "OK: script/web backups excluded"


if tar -I zstd -tf "$ARCHIVE" | grep -Eq '^\./swap\.img$|^\./swapfile$'; then
  echo "Bad swap entries:"
  tar -I zstd -tf "$ARCHIVE" | grep -E '^\./swap\.img$|^\./swapfile$' | sed -n '1,80p'
  die "swap included in payload"
fi
echo "OK: swap excluded"

if tar -I zstd -tf "$ARCHIVE" | grep -Eq '/(venv|\.venv|virtualenv)(/|$)'; then
  echo "NOTICE: venv/virtualenv entries present in payload; allowed for WebApp runtime"
  tar -I zstd -tf "$ARCHIVE" | grep -E '/(venv|\.venv|virtualenv)(/|$)' | sed -n '1,80p'
else
  echo "NOTICE: no venv/virtualenv entries found; WebApp must use system Python or fallback"
fi

if tar -I zstd -tf "$ARCHIVE" | grep -q '^./root/pincabos-v8'; then
  die "old /root payload included"
fi
echo "OK: old root payloads excluded"

echo
echo "=== Validate Python + PinCabOS WebApp in payload ==="
echo "PINCABOS_PAYLOAD_PYTHON_WEBAPP_VALIDATE_V3_PIPEFAIL_SAFE"

ARCHIVE_LIST_PYWEB="$WORK/payload-file-list-python-webapp.txt"
echo "Creating payload file list:"
echo "$ARCHIVE_LIST_PYWEB"
tar -I zstd -tf "$ARCHIVE" > "$ARCHIVE_LIST_PYWEB"

echo "--- vpxtool deterministic ISO validation ---"
for VPXTOOL_MEMBER in \
  "./opt/pincabos/apps/vpxtool/$VPXTOOL_VERSION/vpxtool" \
  "./opt/pincabos/apps/vpxtool/current" \
  "./opt/pincabos/bin/vpxtool"
do
  VPXTOOL_MEMBER_COUNT="$(grep -Fxc "$VPXTOOL_MEMBER" "$ARCHIVE_LIST_PYWEB" || true)"
  [ "$VPXTOOL_MEMBER_COUNT" -eq 1 ] \
    || die "vpxtool payload member count invalid ($VPXTOOL_MEMBER_COUNT): $VPXTOOL_MEMBER"
done
echo "GO [OK] vpxtool v$VPXTOOL_VERSION is present exactly once in payload"

echo "--- Python entries detected in payload ---"
grep -E '^\./usr/bin/python3($|[.0-9-])|^\./usr/lib/python3' "$ARCHIVE_LIST_PYWEB" | sed -n '1,80p' || true

if grep -Eq '^\./usr/bin/python3$|^\./usr/bin/python3[.0-9]+$|^\./usr/lib/python3' "$ARCHIVE_LIST_PYWEB"; then
  echo "OK: Python runtime present in payload"
else
  die "Python runtime missing from payload"
fi

grep -q '^\./opt/pincabos/web/app.py$' "$ARCHIVE_LIST_PYWEB" \
  || die "PinCabOS WebApp missing from payload: /opt/pincabos/web/app.py"

if grep -Eq '^\./etc/systemd/system/pincabos-webapp.service$|^\./lib/systemd/system/pincabos-webapp.service$|^\./usr/lib/systemd/system/pincabos-webapp.service$' "$ARCHIVE_LIST_PYWEB"; then
  echo "OK: pincabos-webapp.service present in payload"
else
  die "pincabos-webapp.service missing from payload"
fi

if grep -Eq '^\./usr/sbin/nginx$|^\./etc/nginx/' "$ARCHIVE_LIST_PYWEB"; then
  echo "NOTICE: nginx is present in payload"
else
  echo "NOTICE: nginx not present in payload; OK, PinCabOS WebApp runs direct without nginx"
fi

if grep -Eq '/(site-packages|dist-packages)/flask($|/)' "$ARCHIVE_LIST_PYWEB"; then
  echo "OK: Flask package present in payload"
else
  echo "WARNING: Flask package not detected in payload path scan"
  echo "Fallback WebApp may rely on official service runtime only."
fi

echo "OK: Python + WebApp payload validation passed"

echo
echo "=== Validate VPX runtime in payload ==="
echo "PINCABOS_PAYLOAD_VPX_VALIDATE_V1"

if [ -z "${ARCHIVE_LIST_PYWEB:-}" ] || [ ! -s "$ARCHIVE_LIST_PYWEB" ]; then
  ARCHIVE_LIST_PYWEB="$WORK/payload-file-list-python-webapp.txt"
  tar -I zstd -tf "$ARCHIVE" > "$ARCHIVE_LIST_PYWEB"
fi

echo "--- VPX payload entries ---"
grep -Ei 'VPinballX|VPinball|vpx\.sh|VPXlauncher|vpinball|PinMAME|VPinballX\.ini' "$ARCHIVE_LIST_PYWEB" | sed -n '1,240p' || true

if grep -Eq '^\./opt/pincabos/bin/vpx\.sh$|^\./opt/pincabos/scripts/VPXlauncher\.sh$' "$ARCHIVE_LIST_PYWEB"; then
  echo "OK: VPX launcher present in payload"
else
  die "VPX launcher missing from payload: /opt/pincabos/bin/vpx.sh or /opt/pincabos/scripts/VPXlauncher.sh"
fi

if grep -Eq 'VPinballX_BGFX$|VPinballX$|/VPinballX_BGFX$|/VPinballX$' "$ARCHIVE_LIST_PYWEB"; then
  echo "OK: VPX executable present in payload"
else
  die "VPX executable missing from payload"
fi

if grep -Eq '^\./home/pinball/\.vpinball/VPinballX\.ini$|^\./home/pinball/\.local/share/VPinballX/.*/VPinballX\.ini$|^\./home/pinball/\.pincabos/vpx/VPinballX\.ini$' "$ARCHIVE_LIST_PYWEB"; then
  echo "OK: VPX INI present in payload"
else
  echo "WARNING: VPX INI not found at expected path"
fi

if grep -Eq '^\./opt/pincabos/apps/vpinball/PinMAME($|/)|^\./home/pinball/\.pinmame($|/)' "$ARCHIVE_LIST_PYWEB"; then
  echo "OK: PinMAME/runtime files present in payload"
else
  echo "WARNING: PinMAME/runtime path not detected in payload"
fi

if grep -q '^\./home/pinball/Tables/' "$ARCHIVE_LIST_PYWEB"; then
  die "Tables were included unexpectedly"
else
  echo "OK: Tables still excluded"
fi

echo "OK: VPX payload validation passed"


echo
echo "=== Validate VPinFE packaged runtime in payload ==="
echo "PINCABOS_PAYLOAD_VPINFE_PACKAGED_RUNTIME_VALIDATE_V1"

if [ -z "${ARCHIVE_LIST_PYWEB:-}" ] || [ ! -s "$ARCHIVE_LIST_PYWEB" ]; then
  ARCHIVE_LIST_PYWEB="$WORK/payload-file-list-python-webapp.txt"
  tar -I zstd -tf "$ARCHIVE" > "$ARCHIVE_LIST_PYWEB"
fi

echo "--- VPinFE payload entries ---"
grep -Ei '^\./home/pinball/vpinfe($|/)|^\./opt/pincabos/tools/run-vpinfe-systemd\.sh$|pincabos-vpinfe\.service' "$ARCHIVE_LIST_PYWEB" | sed -n '1,220p' || true

grep -q '^\./home/pinball/vpinfe/' "$ARCHIVE_LIST_PYWEB" \
  || die "VPinFE runtime missing from payload: /home/pinball/vpinfe"

grep -q '^\./home/pinball/vpinfe/_internal/' "$ARCHIVE_LIST_PYWEB" \
  || die "VPinFE packaged _internal runtime missing from payload"

grep -q '^\./opt/pincabos/tools/run-vpinfe-systemd\.sh$' "$ARCHIVE_LIST_PYWEB" \
  || die "VPinFE launcher missing from payload: /opt/pincabos/tools/run-vpinfe-systemd.sh"

if grep -Eq '^\./etc/systemd/system/pincabos-vpinfe\.service$|^\./lib/systemd/system/pincabos-vpinfe\.service$|^\./usr/lib/systemd/system/pincabos-vpinfe\.service$' "$ARCHIVE_LIST_PYWEB"; then
  echo "OK: pincabos-vpinfe.service present in payload"
else
  die "pincabos-vpinfe.service missing from payload"
fi

echo "OK: VPinFE packaged runtime validation passed"


echo
echo "=== Validate WebApp runtime dependencies in payload ==="
echo "PINCABOS_PAYLOAD_WEBAPP_RUNTIME_VALIDATE_V3_PIPEFAIL_SAFE"

if [ -z "${ARCHIVE_LIST_PYWEB:-}" ] || [ ! -s "$ARCHIVE_LIST_PYWEB" ]; then
  ARCHIVE_LIST_PYWEB="$WORK/payload-file-list-python-webapp.txt"
  tar -I zstd -tf "$ARCHIVE" > "$ARCHIVE_LIST_PYWEB"
fi

if grep -Eq '^\./opt/pincabos/web/(\.venv|venv)/bin/python$|^\./opt/pincabos/(\.venv|venv)/bin/python$' "$ARCHIVE_LIST_PYWEB"; then
  echo "OK: WebApp/local PinCabOS venv python present in payload"
else
  echo "NOTICE: no WebApp/local venv python found in payload; will rely on system Python/fallback"
fi

if grep -Eq '/(site-packages|dist-packages)/flask($|/)' "$ARCHIVE_LIST_PYWEB"; then
  echo "OK: Flask package present somewhere in payload"
else
  echo "WARNING: Flask package not detected by archive path scan"
  echo "The fallback service may fail if Flask is only installed by another mechanism."
fi

tar -I zstd -tf "$OVERLAY" | grep '^usr/share/plymouth/themes/pincabos/pincabos.plymouth$' \
  || die "Plymouth overlay missing pincabos.plymouth"
echo "OK: Plymouth overlay valid"

echo
echo "=== 8) Payload helper (live model) ==="
sha256sum "$ARCHIVE" > "$PAYLOAD_FULL/pincabos-rootfs-cab-v8.1g.sha256"
sha256sum "$OVERLAY" > "$PAYLOAD_FULL/pincabos-plymouth-theme-overlay-v8.1g.sha256"

install -m 755 "$INSTALLER_SRC/pincabos-install-payload" "$PAYLOAD_FULL/pincabos-v8.1g-install-cab-payload-to-target.sh" \
  || die "payload helper missing: $INSTALLER_SRC/pincabos-install-payload"

bash -n "$PAYLOAD_FULL/pincabos-v8.1g-install-cab-payload-to-target.sh" \
  || die "Payload helper has a Bash syntax error"
# PINCABOS_ISO_HELPER_CONTINUATION_GUARD_V1
# `bash -n` ne voit pas une continuation cassee : une ligne finissant par
# deux backslashes est du Bash valide (argument litteral « \ ») mais coupe la
# commande en deux ; avec `set -e` le helper s'arrete et l'installation
# rend « Payload extraction/install failed (code 1) » (Alpha 3.12 a 3.46,
# commit adf4c1e du 01/09). On refuse de construire l'ISO dans ce cas.
if grep -nE '\\\\$' "$PAYLOAD_FULL/pincabos-v8.1g-install-cab-payload-to-target.sh"; then
  die "Payload helper: a line ends with a double backslash (broken continuation)"
fi
echo "GO [OK] payload helper syntax valid"


echo
echo "=== 9L) Live model: the payload becomes the live root filesystem ==="
echo "PINCABOS_ISO_MODELE_LIVE_V1"
rm -rf "$LIVE_ROOTFS" "$ISO_DIR"
mkdir -p "$LIVE_ROOTFS" "$ISO_DIR/casper"
tar --zstd -xpf "$ARCHIVE" -C "$LIVE_ROOTFS" --numeric-owner
test -d "$LIVE_ROOTFS/opt/pincabos" || die "live rootfs incomplete: $LIVE_ROOTFS/opt/pincabos missing"
test -d "$LIVE_ROOTFS/lib/modules" || die "live rootfs incomplete: no kernel modules"
ROOTFS_DIR="$LIVE_ROOTFS"
echo "GO [OK] live rootfs unpacked in $LIVE_ROOTFS"

echo
echo "=== 12) Ensure required live installer tools inside squashfs ==="
cp -a /etc/resolv.conf "$ROOTFS_DIR/etc/resolv.conf" || true

echo
echo "--- PinCabOS hard reset apt sources inside live chroot ---"
mkdir -p "$ROOTFS_DIR/etc/apt/sources.list.d"
mkdir -p "$ROOTFS_DIR/etc/apt/pincabos-disabled-sources"
mkdir -p "$ROOTFS_DIR/etc/apt/pincabos-empty-sourceparts"

# Disable every sourceparts file, including ubuntu.sources.
# This avoids both file:/cdrom and duplicate source warnings.
while IFS= read -r aptsrc; do
  [ -f "$aptsrc" ] || continue
  rel="${aptsrc#$ROOTFS_DIR/}"
  safe="$(echo "$rel" | tr '/' '_')"
  echo "Disabling apt sourceparts file: /$rel"
  cp -a "$aptsrc" "$ROOTFS_DIR/etc/apt/pincabos-disabled-sources/${safe}.bak" || true
  mv "$aptsrc" "$ROOTFS_DIR/etc/apt/pincabos-disabled-sources/${safe}.disabled" || true
done < <(find "$ROOTFS_DIR/etc/apt/sources.list.d" -maxdepth 1 -type f \( -name '*.list' -o -name '*.sources' \) 2>/dev/null | sort)

cat > "$ROOTFS_DIR/etc/apt/sources.list" <<'PINCABOS_APT_SOURCES'
deb http://archive.ubuntu.com/ubuntu resolute main restricted universe multiverse
deb http://archive.ubuntu.com/ubuntu resolute-updates main restricted universe multiverse
deb http://archive.ubuntu.com/ubuntu resolute-backports main restricted universe multiverse
deb http://security.ubuntu.com/ubuntu resolute-security main restricted universe multiverse
PINCABOS_APT_SOURCES

rm -rf "$ROOTFS_DIR/var/lib/apt/lists"
mkdir -p "$ROOTFS_DIR/var/lib/apt/lists/partial"

echo "--- Final active apt sources.list ---"
cat "$ROOTFS_DIR/etc/apt/sources.list"

echo "--- Final sourceparts directory should be empty ---"
find "$ROOTFS_DIR/etc/apt/sources.list.d" -maxdepth 1 -type f -print || true

if grep -RniE 'cdrom:|file:/cdrom' "$ROOTFS_DIR/etc/apt/sources.list" "$ROOTFS_DIR/etc/apt/sources.list.d" 2>/dev/null; then
  die "Active cdrom apt source still present after hard reset"
fi
echo "OK: active apt sources have no cdrom/file:/cdrom"

mount --bind /dev "$ROOTFS_DIR/dev"
mount --bind /proc "$ROOTFS_DIR/proc"
mount --bind /sys "$ROOTFS_DIR/sys"
mount --bind /run "$ROOTFS_DIR/run"

APT_FORCE_OPTS=(
  -o Dir::Etc::sourcelist=/etc/apt/sources.list
  -o Dir::Etc::sourceparts=/etc/apt/pincabos-empty-sourceparts
  -o APT::Get::List-Cleanup=0
)

# cache apt persistant entre les builds (les .deb survivent au menage)
mkdir -p "$CACHE_DIR/apt-archives"
mount --bind "$CACHE_DIR/apt-archives" "$ROOTFS_DIR/var/cache/apt/archives"
chroot "$ROOTFS_DIR" apt-get "${APT_FORCE_OPTS[@]}" update
DEBIAN_FRONTEND=noninteractive chroot "$ROOTFS_DIR" apt-get "${APT_FORCE_OPTS[@]}" install -y \
  zstd \
  parted \
  gdisk \
  dosfstools \
  e2fsprogs \
  util-linux \
  coreutils \
  sudo \
  grub-efi-amd64-bin \
  ca-certificates \
  plymouth \
  plymouth-label \
  fontconfig \
  casper \
  kbd \
  console-setup \
  xserver-xorg-core \
  xserver-xorg-video-all \
  xinit \
  x11-xserver-utils \
  openbox \
  python3-gi \
  gir1.2-webkit-6.0 \
  python3-flask \
  curl \
  fonts-dejavu-core \
  libgl1-mesa-dri

echo
echo "--- PinCabOS: dist-upgrade du live (kernel tenu) + menage apt du live ---"
chroot "$ROOTFS_DIR" bash -c "
  export DEBIAN_FRONTEND=noninteractive
  apt-mark hold linux-generic linux-image-generic linux-headers-generic 2>/dev/null || true
  apt-get -y -qq -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold dist-upgrade 2>&1 | tail -3
  apt-get -y -qq purge mdadm 2>&1 | tail -1
  apt-get -y -qq autoremove --purge 2>&1 | tail -2
"
umount "$ROOTFS_DIR/var/cache/apt/archives"
rm -rf "$ROOTFS_DIR/var/lib/apt/lists"/* "$ROOTFS_DIR/var/cache/apt/archives"/*.deb

echo
echo "--- PinCabOS: theme Plymouth + regeneration initrd live (base server) ---"
mkdir -p "$ROOTFS_DIR/usr/share/plymouth/themes" "$ROOTFS_DIR/etc/plymouth"
cp -a /usr/share/plymouth/themes/pincabos "$ROOTFS_DIR/usr/share/plymouth/themes/"
# Splash du LIVE : la mascotte "Tux au flipper" (theme install de Karots),
# le systeme installe garde le logo classique.
cp /usr/share/plymouth/themes/pincabos-install/PCOSLinuxWP.png \
   "$ROOTFS_DIR/usr/share/plymouth/themes/pincabos/pincabos.png"
printf '[Daemon]\nTheme=pincabos\nShowDelay=0\n' > "$ROOTFS_DIR/etc/plymouth/plymouthd.conf"
# Le plugin "script" n est pas dans le paquet plymouth de base : on le garantit.
DEBIAN_FRONTEND=noninteractive chroot "$ROOTFS_DIR" apt-get install -y -qq plymouth-themes 2>/dev/null || true
PLY_LIB="usr/lib/x86_64-linux-gnu/plymouth"
if [ ! -f "$ROOTFS_DIR/$PLY_LIB/script.so" ]; then
  cp "/$PLY_LIB/script.so" "$ROOTFS_DIR/$PLY_LIB/script.so"
fi
[ ! -f "/$PLY_LIB/label.so" ] || cp -n "/$PLY_LIB/label.so" "$ROOTFS_DIR/$PLY_LIB/" || true
chroot "$ROOTFS_DIR" update-alternatives --install \
  /usr/share/plymouth/themes/default.plymouth default.plymouth \
  /usr/share/plymouth/themes/pincabos/pincabos.plymouth 200
chroot "$ROOTFS_DIR" update-alternatives --set default.plymouth \
  /usr/share/plymouth/themes/pincabos/pincabos.plymouth
[ ! -x "$ROOTFS_DIR/usr/sbin/plymouth-set-default-theme" ] \
  || chroot "$ROOTFS_DIR" /usr/sbin/plymouth-set-default-theme pincabos
echo "--- PinCabOS: reseau DHCP du live ---"
mkdir -p "$ROOTFS_DIR/etc/netplan"
cat > "$ROOTFS_DIR/etc/netplan/01-pincabos-live-dhcp.yaml" <<'PCO_NET'
# pincabos-live-dhcp : DHCP simple sur toute interface ethernet du live
network:
  version: 2
  ethernets:
    all-en:
      match: {name: "en*"}
      dhcp4: true
      optional: true
PCO_NET
chmod 600 "$ROOTFS_DIR/etc/netplan/01-pincabos-live-dhcp.yaml"

echo "--- PinCabOS: hostname du live ---"
echo pincabos-installer > "$ROOTFS_DIR/etc/hostname"
printf '127.0.0.1 localhost\n127.0.1.1 pincabos-installer\n' > "$ROOTFS_DIR/etc/hosts"

echo "--- PinCabOS: installeur GUI (wizard + kiosk + dispatch) ---"
mkdir -p "$ROOTFS_DIR/opt/pincabos/installer-gui"
cp -a /opt/pincabos/installer-gui/. "$ROOTFS_DIR/opt/pincabos/installer-gui/"
install -m 755 /usr/local/sbin/pincabos-installer-dispatch \
  "$ROOTFS_DIR/usr/local/sbin/pincabos-installer-dispatch"
install -m 755 /usr/local/bin/pincabos-kiosk.py \
  "$ROOTFS_DIR/usr/local/bin/pincabos-kiosk.py"
install -m 755 /usr/local/bin/pincabos-kiosk-session \
  "$ROOTFS_DIR/usr/local/bin/pincabos-kiosk-session"
# PINCABOS_INSTALLEUR_UN_SEUL_CHEMIN_V1 : plus d'installeur texte de secours ;
# si le kiosque ne tient pas, la panne est annoncee en clair sur tty1.
install -m 755 /usr/local/sbin/pincabos-installer-failure \
  "$ROOTFS_DIR/usr/local/sbin/pincabos-installer-failure"
cp /etc/systemd/system/pincabos-gui-wizard.service \
   /etc/systemd/system/pincabos-gui-kiosk.service \
   /etc/systemd/system/pincabos-installer-failure.service \
   "$ROOTFS_DIR/etc/systemd/system/"
rm -f "$ROOTFS_DIR/usr/local/sbin/pincabos-gui-fallback" \
      "$ROOTFS_DIR/usr/local/sbin/pincabos-live-installer-console" \
      "$ROOTFS_DIR/etc/systemd/system/pincabos-tui-fallback.service"
mkdir -p "$ROOTFS_DIR/etc/X11/xorg.conf.d"
cat > "$ROOTFS_DIR/etc/X11/xorg.conf.d/10-pincabos-kiosk.conf" <<'PCO_XORG'
Section "Device"
  Identifier "PinCabOS Kiosk"
  Driver "modesetting"
EndSection
PCO_XORG
echo "OK: installeur GUI embarque dans le live"

LIVE_KVER="$(ls "$ROOTFS_DIR/lib/modules" | sort -V | tail -1)"
DEBIAN_FRONTEND=noninteractive chroot "$ROOTFS_DIR" update-initramfs -c -k "$LIVE_KVER" \
  || DEBIAN_FRONTEND=noninteractive chroot "$ROOTFS_DIR" update-initramfs -u -k "$LIVE_KVER"
cp "$ROOTFS_DIR/boot/initrd.img-$LIVE_KVER" "$ISO_DIR/casper/initrd"
if [ -f "$ROOTFS_DIR/boot/vmlinuz-$LIVE_KVER" ]; then
  cp "$ROOTFS_DIR/boot/vmlinuz-$LIVE_KVER" "$ISO_DIR/casper/vmlinuz"
fi
lsinitramfs "$ISO_DIR/casper/initrd" | grep -q "themes/pincabos/pincabos.script" \
  || die "Theme pincabos absent de l initrd live"
lsinitramfs "$ISO_DIR/casper/initrd" | grep -q "plymouth/script.so" \
  || die "Plugin script.so absent de l initrd live"
echo "OK: initrd live regenere avec plymouth+casper ($LIVE_KVER), theme pincabos verifie"

cleanup_mounts

echo
echo "=== 13) Disable Ubuntu Welcome/GDM and force PinCabOS tty installer ==="
mkdir -p "$ROOTFS_DIR/etc/systemd/system"
mkdir -p "$ROOTFS_DIR/etc/systemd/system/multi-user.target.wants"

ln -sfn /lib/systemd/system/multi-user.target "$ROOTFS_DIR/etc/systemd/system/default.target"
ln -sfn /dev/null "$ROOTFS_DIR/etc/systemd/system/display-manager.service"
ln -sfn /dev/null "$ROOTFS_DIR/etc/systemd/system/gdm.service"
ln -sfn /dev/null "$ROOTFS_DIR/etc/systemd/system/gdm3.service"

echo
echo "--- Disable unused CUPS services in live ISO to avoid reboot/shutdown delay ---"
echo "PINCABOS_LIVE_DISABLE_CUPS_SHUTDOWN_DELAY_V1"
for unit in cups.service cups.socket cups.path cups-browsed.service; do
  echo "Masking live unit: $unit"
  ln -sfn /dev/null "$ROOTFS_DIR/etc/systemd/system/$unit" || true
done

DISABLED_DIR="$ROOTFS_DIR/var/lib/pincabos-disabled-ubuntu-welcome"
mkdir -p "$DISABLED_DIR"

while IFS= read -r f; do
  [ -f "$f" ] || continue
  rel="${f#$ROOTFS_DIR/}"
  safe="$(echo "$rel" | tr '/' '_')"
  echo "Disabling: /$rel"
  cp -a "$f" "$DISABLED_DIR/$safe" || true
  mv "$f" "$f.disabled-by-pincabos" || true
done < <(find "$ROOTFS_DIR" -xdev -type f \( \
  -path '*/etc/xdg/autostart/*' -o \
  -path '*/usr/share/applications/*' -o \
  -path '*/etc/systemd/system/*' -o \
  -path '*/lib/systemd/system/*' -o \
  -path '*/usr/lib/systemd/system/*' \
\) \( \
  -iname '*ubuntu*welcome*' -o \
  -iname '*ubuntu*bootstrap*' -o \
  -iname '*ubuntu*desktop*installer*' -o \
  -iname '*subiquity*' -o \
  -iname '*casper*installer*' \
\) | sort)

mkdir -p "$ROOTFS_DIR/usr/local/sbin"

install -m 755 "$INSTALLER_SRC/pincabos-live-installer" "$ROOTFS_DIR/usr/local/sbin/pincabos-live-installer" \
  || die "live installer missing: $INSTALLER_SRC/pincabos-live-installer"

bash -n "$ROOTFS_DIR/usr/local/sbin/pincabos-live-installer" \
  || die "Live installer has a Bash syntax error"
echo "GO [OK] live installer syntax valid"

echo
echo "=== PinCabOS lean live TTY boot ==="
echo "PINCABOS_LIVE_TTY_BOOT_NO_CYCLE_V1"

mkdir -p \
  "$ROOTFS_DIR/etc/systemd/system" \
  "$ROOTFS_DIR/etc/systemd/system/multi-user.target.wants" \
  "$ROOTFS_DIR/usr/local/sbin"

echo
echo "--- Set stable live hostname ---"

printf 'pincabos-live\n' > "$ROOTFS_DIR/etc/hostname"

if [ -f "$ROOTFS_DIR/etc/hosts" ]; then
  sed -i \
    '/^[[:space:]]*127\.0\.1\.1[[:space:]]/d' \
    "$ROOTFS_DIR/etc/hosts"
else
  printf '127.0.0.1 localhost\n' > "$ROOTFS_DIR/etc/hosts"
fi

printf '127.0.1.1 pincabos-live\n' \
  >> "$ROOTFS_DIR/etc/hosts"

echo
echo "--- Mask unnecessary desktop/live background services ---"

LIVE_MASK_UNITS=(
  casper-md5check.service
  cloud-init-local.service
  cloud-init.service
  cloud-config.service
  cloud-final.service
  cloud-init.target
  snapd.service
  snapd.socket
  snapd.seeded.service
  snapd.autoimport.service
  apt-daily.service
  apt-daily.timer
  apt-daily-upgrade.service
  apt-daily-upgrade.timer
  unattended-upgrades.service
  packagekit.service
  NetworkManager-wait-online.service
  systemd-networkd-wait-online.service
  fwupd.service
  fwupd-refresh.service
  fwupd-refresh.timer
  whoopsie.service
  apport.service
)
# plymouth n est plus masque : le live affiche le splash PinCabOS (theme via 17b)

for unit in "${LIVE_MASK_UNITS[@]}"; do
  echo "Masking live-only unit: $unit"
  ln -sfn /dev/null \
    "$ROOTFS_DIR/etc/systemd/system/$unit"
done

# tty1 belongs exclusively to the PinCabOS installer.
ln -sfn /dev/null \
  "$ROOTFS_DIR/etc/systemd/system/getty@tty1.service"

ln -sfn /dev/null \
  "$ROOTFS_DIR/etc/systemd/system/autovt@tty1.service"

install -m 755 "$INSTALLER_SRC/pincabos-live-installer-wait" "$ROOTFS_DIR/usr/local/sbin/pincabos-live-installer-wait" \
  || die "live installer wait missing: $INSTALLER_SRC/pincabos-live-installer-wait"


# PINCABOS_INSTALLEUR_UN_SEUL_CHEMIN_V1 : l'installeur texte (console tty1)
# n'existe plus ; tty1 lance l'assistant graphique via le dispatch.
install -m 644 "$INSTALLER_SRC/pincabos-live-installer-tty.service" "$ROOTFS_DIR/etc/systemd/system/pincabos-live-installer-tty.service" \
  || die "live installer tty unit missing: $INSTALLER_SRC/pincabos-live-installer-tty.service"

ln -sfn ../pincabos-live-installer-tty.service \
  "$ROOTFS_DIR/etc/systemd/system/multi-user.target.wants/pincabos-live-installer-tty.service"

echo
echo "=== 14L) Live model: ISO built by iso-live.sh ==="
cleanup_mounts
rm -f "$ROOTFS_DIR/etc/skel/Desktop/Install-PinCabOS.desktop"
LIVE_SH="$(dirname "$(readlink -f "$0")")/iso-live.sh"
[ -f "$LIVE_SH" ] || LIVE_SH="/opt/pincabos/script/iso-live.sh"
test -f "$LIVE_SH" || die "iso-live.sh not found next to iso.sh nor in /opt/pincabos/script"
mkdir -p "$OUT_DIR"
bash "$LIVE_SH" --rootfs "$ROOTFS_DIR" --payload "$PAYLOAD_FULL" --out "$OUT_ISO" \
  || die "iso-live.sh failed"
test -f "$OUT_ISO" || die "live ISO was not created"
ls -lh "$OUT_ISO"
sha256sum "$OUT_ISO" | tee "$OUT_ISO.sha256"
echo
echo "==============================================================="
echo " ISO CREATED OK (live model)"
echo "==============================================================="

# PINCABOS_OPTIONAL_WEB_PUBLISH_V1
# Publication optionnelle de l'ISO apres un build reussi.
# Demande IP/login/password une seule fois.
# Met a jour automatiquement les index du serveur Web.
# ======================================================================

pincabos_offer_web_publish() {
    local ANSWER=""
    local WEB_IP=""
    local WEB_USER=""
    local WEB_PASS=""
    local ISO_FILE=""
    local ISO_NAME=""
    local ISO_SHA=""
    local ISO_SIZE_BYTES=""
    local PUB_DATE=""
    local REMOTE_ROOT="/var/www/html/updates"
    local REMOTE_ISO_DIR="${REMOTE_ROOT}/iso"
    local REMOTE_SHA=""

    echo
    echo "==============================================================="
    echo " PINCABOS — PUBLICATION ISO"
    echo "==============================================================="
    echo

    read -rp "Publier l'ISO sur le serveur Web ? [o/N] : " ANSWER || true

    case "${ANSWER,,}" in
        o|oui|y|yes)
            ;;
        *)
            echo "INFO : publication Web ignoree."
            return 0
            ;;
    esac

    echo
    echo "=== Configuration serveur Web ==="

    while [ -z "$WEB_IP" ]; do
        read -rp "Adresse IP du serveur Web : " WEB_IP
    done

    while [ -z "$WEB_USER" ]; do
        read -rp "Login SSH : " WEB_USER
    done

    while [ -z "$WEB_PASS" ]; do
        read -rsp "Mot de passe SSH : " WEB_PASS
        echo
    done

    echo
    echo "=== Recherche ISO produite ==="

    ISO_FILE="/opt/pincabos/build/output/PinCabOS-beta-Installer.iso"

    if [ ! -s "$ISO_FILE" ]; then
        ISO_FILE="$(
            find /opt/pincabos/build/output \
                -maxdepth 1 \
                -type f \
                -name '*.iso' \
                -printf '%T@ %p\n' 2>/dev/null \
            | sort -nr \
            | head -1 \
            | cut -d' ' -f2-
        )"
    fi

    if [ -z "${ISO_FILE:-}" ] || [ ! -s "$ISO_FILE" ]; then
        echo "ERREUR [X] aucune ISO valide trouvee."
        WEB_PASS=""
        return 1
    fi

    ISO_NAME="$(basename "$ISO_FILE")"
    ISO_SHA="$(sha256sum "$ISO_FILE" | awk '{print $1}')"
    ISO_SIZE_BYTES="$(stat -c '%s' "$ISO_FILE")"
    PUB_DATE="$(date '+%Y-%m-%dT%H:%M:%S%z')"

    printf '%s  %s\n' \
        "$ISO_SHA" \
        "$ISO_NAME" \
        > "${ISO_FILE}.sha256"

    echo "ISO    : $ISO_FILE"
    echo "Taille : $(du -h "$ISO_FILE" | awk '{print $1}')"
    echo "SHA256 : $ISO_SHA"

    echo
    echo "=== Outils de publication ==="

    if ! command -v sshpass >/dev/null 2>&1; then
        echo "INFO : installation de sshpass..."

        apt-get update
        DEBIAN_FRONTEND=noninteractive \
            apt-get install -y sshpass
    fi

    if ! command -v rsync >/dev/null 2>&1; then
        echo "INFO : installation de rsync..."

        apt-get update
        DEBIAN_FRONTEND=noninteractive \
            apt-get install -y rsync
    fi

    command -v sshpass >/dev/null
    command -v rsync >/dev/null

    export SSHPASS="$WEB_PASS"

    local SSH_OPTS=(
        -o StrictHostKeyChecking=accept-new
        -o ConnectTimeout=15
        -o ServerAliveInterval=30
        -o ServerAliveCountMax=6
    )

    echo
    echo "=== Test connexion SSH ==="

    if ! sshpass -e ssh \
        "${SSH_OPTS[@]}" \
        "${WEB_USER}@${WEB_IP}" \
        'echo "GO [OK] connexion SSH"'
    then
        echo "ERREUR [X] connexion SSH impossible."
        unset SSHPASS
        WEB_PASS=""
        return 1
    fi

    echo
    echo "=== Preparation serveur Web ==="

    if ! sshpass -e ssh \
        "${SSH_OPTS[@]}" \
        "${WEB_USER}@${WEB_IP}" \
        "mkdir -p '$REMOTE_ISO_DIR' && test -w '$REMOTE_ISO_DIR'"
    then
        echo
        echo "ERREUR [X] impossible d'ecrire dans :"
        echo "$REMOTE_ISO_DIR"
        echo
        echo "Le compte SSH doit avoir acces en ecriture a /var/www/html/updates."
        unset SSHPASS
        WEB_PASS=""
        return 1
    fi

    echo
    echo "=== Transfert ISO + SHA256 ==="

# PINCABOS_WEB_RSYNC_SAFE_V3
    if ! sshpass -e rsync \
        -avhP \
        --checksum \
        -e "ssh -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 -o ServerAliveCountMax=6" \
        "$ISO_FILE" \
        "${ISO_FILE}.sha256" \
        "${WEB_USER}@${WEB_IP}:${REMOTE_ISO_DIR}/"
    then
        echo "ERREUR [X] transfert rsync."
        unset SSHPASS
        WEB_PASS=""
        return 1
    fi

    echo
    echo "=== Validation SHA256 distant ==="

    REMOTE_SHA="$(
        sshpass -e ssh \
            "${SSH_OPTS[@]}" \
            "${WEB_USER}@${WEB_IP}" \
            "sha256sum '$REMOTE_ISO_DIR/$ISO_NAME' | awk '{print \$1}'"
    )"

    echo "Local   : $ISO_SHA"
    echo "Distant : $REMOTE_SHA"

    if [ "$REMOTE_SHA" != "$ISO_SHA" ]; then
        echo "ERREUR [X] SHA256 distant different."
        unset SSHPASS
        WEB_PASS=""
        return 1
    fi

    echo "GO [OK] ISO distante identique"

    echo
    echo "=== INDEX WEB CANONIQUE ==="

    # ==============================================================
    # PINCABOS_CANONICAL_WEB_INDEX_V6
    #
    # IMPORTANT :
    # - réécrit complètement /updates/index.html
    # - réécrit complètement /updates/iso/index.html
    # - n'ajoute jamais de bloc dans un ancien HTML
    # - une seule ISO affichée : ISO_NAME
    # ==============================================================

    if ! sshpass -e ssh \
        "${SSH_OPTS[@]}" \
        "${WEB_USER}@${WEB_IP}" \
        bash -s -- \
        "$REMOTE_ROOT" \
        "$ISO_NAME" \
        "$ISO_SHA" \
        "$ISO_SIZE_BYTES" <<'PINCABOS_CANONICAL_INDEX_V6'
set -Eeuo pipefail

ROOT="$1"
ISO_NAME="$2"
EXPECTED_SHA="$3"
EXPECTED_SIZE="$4"

ISO_DIR="$ROOT/iso"
ISO_FILE="$ISO_DIR/$ISO_NAME"

echo
echo "---------------------------------------------------------------"
echo " PINCABOS — GENERATION INDEX CANONIQUE V6"
echo "---------------------------------------------------------------"

test -d "$ROOT" || {
    echo "ERREUR [X] racine Web absente : $ROOT"
    exit 1
}

test -s "$ISO_FILE" || {
    echo "ERREUR [X] ISO distante absente : $ISO_FILE"
    exit 1
}

ACTUAL_SHA="$(sha256sum "$ISO_FILE" | awk '{print $1}')"
ACTUAL_SIZE="$(stat -c '%s' "$ISO_FILE")"

echo
echo "SHA attendu : $EXPECTED_SHA"
echo "SHA distant : $ACTUAL_SHA"

if [ "$ACTUAL_SHA" != "$EXPECTED_SHA" ]; then
    echo "ERREUR [X] SHA ISO distant différent"
    exit 1
fi

if [ "$ACTUAL_SIZE" != "$EXPECTED_SIZE" ]; then
    echo "ERREUR [X] taille ISO distante différente"
    exit 1
fi

echo "GO [OK] ISO distante validée"

PUB_DATE="$(date '+%Y-%m-%d %H:%M:%S %Z')"

STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="/var/backups/pincabos-web-index/$STAMP"

mkdir -p "$BACKUP_DIR"

echo
echo "--- Backup anciens index ---"

for FILE in \
    "$ROOT/index.html" \
    "$ISO_DIR/index.html"
do
    if [ -f "$FILE" ]; then
        cp -a "$FILE" "$BACKUP_DIR/"
        echo "GO [OK] backup : $FILE"
    fi
done

echo
echo "--- SHA256 officiel ---"

printf '%s  %s\n' \
    "$ACTUAL_SHA" \
    "$ISO_NAME" \
    > "$ISO_FILE.sha256"

chmod 0644 \
    "$ISO_FILE" \
    "$ISO_FILE.sha256"

echo
echo "--- Liens de compatibilité ---"

ln -sfn \
    "$ISO_NAME" \
    "$ISO_DIR/PinCabOS-Installer.iso"

ln -sfn \
    "$ISO_NAME.sha256" \
    "$ISO_DIR/PinCabOS-Installer.iso.sha256"

echo "GO [OK] liens"

echo
echo "--- Génération HTML complète ---"

python3 - \
    "$ROOT" \
    "$ISO_NAME" \
    "$ACTUAL_SHA" \
    "$ACTUAL_SIZE" \
    "$PUB_DATE" <<'PYHTML'
from pathlib import Path
import html
import sys

root = Path(sys.argv[1])
iso_name = sys.argv[2]
sha = sys.argv[3]
size_bytes = int(sys.argv[4])
pub_date = sys.argv[5]


def human_size(value):
    value = float(value)

    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            if unit in ("GiB", "TiB"):
                return f"{value:.2f} {unit}"
            if unit == "MiB":
                return f"{value:.1f} {unit}"
            return f"{value:.0f} {unit}"

        value /= 1024


filename = html.escape(iso_name)
checksum = html.escape(sha)
size = html.escape(human_size(size_bytes))
published = html.escape(pub_date)

byte_text = f"{size_bytes:,}".replace(",", " ")


def render(prefix):
    iso_url = html.escape(prefix + iso_name)
    sha_url = html.escape(prefix + iso_name + ".sha256")

    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta
    name="viewport"
    content="width=device-width,initial-scale=1"
>

<title>PinCabOS Installer</title>

<style>
:root {{
    color-scheme: dark;

    --bg: #070a0f;
    --panel: #111822;
    --panel2: #0d131c;
    --border: #2d3948;

    --text: #f6f8fb;
    --muted: #9bacc0;

    --orange: #ff9700;
    --orange-light: #ffb32d;

    --green: #36df8c;
    --blue: #58baff;
}}

* {{
    box-sizing: border-box;
}}

html {{
    min-height: 100%;
    background: var(--bg);
}}

body {{
    margin: 0;
    min-height: 100vh;

    background:
        radial-gradient(
            circle at 50% -160px,
            rgba(73, 45, 107, .38) 0,
            rgba(24, 18, 40, .20) 300px,
            transparent 650px
        ),
        var(--bg);

    color: var(--text);

    font-family:
        Inter,
        "Segoe UI",
        Roboto,
        Helvetica,
        Arial,
        sans-serif;

    -webkit-font-smoothing: antialiased;
}}

.wrapper {{
    width: min(760px, calc(100% - 36px));
    margin: 0 auto;
    padding: 72px 0 50px;
}}

.status {{
    display: flex;
    align-items: center;
    gap: 8px;

    margin-bottom: 12px;

    color: var(--green);
    font-size: 14px;
    font-weight: 750;
}}

.status-dot {{
    width: 7px;
    height: 7px;

    border-radius: 50%;
    background: var(--green);

    box-shadow:
        0 0 10px rgba(54, 223, 140, .8);
}}

h1 {{
    margin: 0;

    font-size: clamp(34px, 6vw, 48px);
    line-height: 1.08;
    letter-spacing: -.8px;
}}

.subtitle {{
    margin: 13px 0 30px;

    color: var(--muted);
    font-size: 15px;
    line-height: 1.6;
}}

.download {{
    display: inline-flex;
    align-items: center;
    justify-content: center;

    min-height: 48px;
    padding: 0 25px;

    border: 0;
    border-radius: 9px;

    background:
        linear-gradient(
            180deg,
            var(--orange-light),
            var(--orange)
        );

    color: #111;
    text-decoration: none;

    font-size: 14px;
    font-weight: 800;

    box-shadow:
        0 10px 25px rgba(0, 0, 0, .35);

    transition:
        transform .12s ease,
        filter .12s ease;
}}

.download:hover {{
    filter: brightness(1.08);
    transform: translateY(-1px);
}}

.card {{
    margin-top: 30px;

    overflow: hidden;

    border: 1px solid var(--border);
    border-radius: 13px;

    background:
        linear-gradient(
            180deg,
            rgba(19, 27, 38, .96),
            rgba(13, 19, 28, .96)
        );

    box-shadow:
        0 20px 55px rgba(0, 0, 0, .33);
}}

.row {{
    display: grid;

    grid-template-columns:
        135px
        minmax(0, 1fr);

    gap: 20px;

    padding: 16px 19px;

    border-bottom:
        1px solid var(--border);
}}

.row:last-child {{
    border-bottom: 0;
}}

.label {{
    color: var(--muted);
    font-size: 14px;
}}

.value {{
    min-width: 0;

    color: var(--text);
    font-size: 14px;
    font-weight: 650;

    overflow-wrap: anywhere;
}}

code {{
    font-family:
        Consolas,
        "SFMono-Regular",
        Monaco,
        monospace;

    font-size: 12px;
    line-height: 1.55;

    color: #e5edf7;
}}

.sha-link {{
    color: var(--blue);
    text-decoration: none;
}}

.sha-link:hover {{
    text-decoration: underline;
}}

footer {{
    margin-top: 29px;

    color: #718398;

    font-size: 12px;
}}

@media (max-width: 600px) {{

    .wrapper {{
        width: min(100% - 24px, 760px);
        padding-top: 38px;
    }}

    .row {{
        grid-template-columns: 1fr;
        gap: 6px;
    }}

    h1 {{
        font-size: 34px;
    }}

    .download {{
        width: 100%;
    }}
}}
</style>
</head>

<body>

<main class="wrapper">

    <div class="status">
        <span class="status-dot"></span>
        <span>ISO disponible</span>
    </div>

    <h1>PinCabOS Installer</h1>

    <p class="subtitle">
        Dernière image d'installation officielle de PinCabOS.
    </p>

    <a
        class="download"
        href="{iso_url}"
    >
        Télécharger PinCabOS
    </a>

    <section class="card">

        <div class="row">
            <div class="label">Fichier</div>

            <div class="value">
                <code>{filename}</code>
            </div>
        </div>

        <div class="row">
            <div class="label">Taille</div>

            <div class="value">
                {size} — {byte_text} octets
            </div>
        </div>

        <div class="row">
            <div class="label">SHA-256</div>

            <div class="value">
                <code>{checksum}</code>
            </div>
        </div>

        <div class="row">
            <div class="label">Somme</div>

            <div class="value">
                <a
                    class="sha-link"
                    href="{sha_url}"
                >
                    {filename}.sha256
                </a>
            </div>
        </div>

        <div class="row">
            <div class="label">Publication</div>

            <div class="value">
                {published}
            </div>
        </div>

    </section>

    <footer>
        PinCabOS — Linux Virtual Pinball Cabinet OS
    </footer>

</main>

<!-- PINCABOS_CANONICAL_INDEX_V6 -->

</body>
</html>
"""


# /updates/
(root / "index.html").write_text(
    render("iso/"),
    encoding="utf-8",
)

# /updates/iso/
(root / "iso" / "index.html").write_text(
    render(""),
    encoding="utf-8",
)

print("GO [OK] /updates/index.html")
print("GO [OK] /updates/iso/index.html")
PYHTML

chmod 0644 \
    "$ROOT/index.html" \
    "$ISO_DIR/index.html"

echo
echo "--- Validation HTML ---"

for INDEX in \
    "$ROOT/index.html" \
    "$ISO_DIR/index.html"
do
    test -s "$INDEX"

    COUNT="$(
        grep -c \
            'PINCABOS_CANONICAL_INDEX_V6' \
            "$INDEX" || true
    )"

    if [ "$COUNT" != "1" ]; then
        echo "ERREUR [X] marker HTML invalide : $INDEX"
        exit 1
    fi

    # Ces anciens blocs ne doivent PLUS exister.
    if grep -qE \
        'PINCABOS_(PUBLISH_INFO|AUTO_ISO|ISO_SECTION)_(START|END)' \
        "$INDEX"
    then
        echo "ERREUR [X] ancien bloc HTML détecté : $INDEX"
        exit 1
    fi

    echo "GO [OK] index canonique : $INDEX"
done

echo
echo "--- Validation checksum ---"

cd "$ISO_DIR"
sha256sum -c "$ISO_NAME.sha256"

if command -v nginx >/dev/null 2>&1; then
    echo
    echo "--- Validation Nginx ---"
    nginx -t
fi

echo
echo "GO [OK] INDEX WEB CANONIQUE V6"
PINCABOS_CANONICAL_INDEX_V6

    then
        echo "ERREUR [X] génération index canonique."
        unset SSHPASS
        WEB_PASS=""
        return 1
    fi

    echo "GO [OK] index Web canonique terminé"


    unset SSHPASS
    WEB_PASS=""

    echo
    echo "==============================================================="
    echo " GO [OK] PUBLICATION WEB TERMINEE"
    echo "==============================================================="
    echo
    echo "Serveur : $WEB_IP"
    echo "ISO     : $ISO_NAME"
    echo "SHA256  : $ISO_SHA"
    echo
    echo "Index mis a jour :"
    echo "  $REMOTE_ROOT/index.html"
    echo "  $REMOTE_ISO_DIR/index.html"

    return 0
}


# Le build a atteint la fin de iso.sh : l'ISO est donc consideree reussie.
if ! pincabos_offer_web_publish; then
    echo
    echo "WARNING: le build ISO est reussi, mais la publication Web a echoue."
    echo "L'ISO locale est conservee."
fi
