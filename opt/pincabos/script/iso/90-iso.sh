#!/usr/bin/env bash
# PINCABOS_ISO_ETAPES_V1 — etape 90-iso d iso.sh (texte de l ancienne section, inchange)
set -Eeuo pipefail
. "$(dirname "$(readlink -f "$0")")/00-lib.sh"
trap cleanup_mounts EXIT

ROOTFS_DIR="$LIVE_ROOTFS"   # pose par l etape 80 (9L) dans l ancien flux
echo
echo "=== 14L) Live model: ISO built by iso-live.sh ==="
cleanup_mounts
rm -f "$ROOTFS_DIR/etc/skel/Desktop/Install-PinCabOS.desktop"
LIVE_SH="${PCO_ISO_SCRIPT_DIR:-$(dirname "$(readlink -f "$0")")}/iso-live.sh"
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
