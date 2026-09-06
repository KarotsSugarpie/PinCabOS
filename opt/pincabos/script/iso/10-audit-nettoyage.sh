#!/usr/bin/env bash
# PINCABOS_ISO_ETAPES_V1 — etape 10-audit-nettoyage d iso.sh (texte de l ancienne section, inchange)
set -Eeuo pipefail
. "$(dirname "$(readlink -f "$0")")/00-lib.sh"
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
