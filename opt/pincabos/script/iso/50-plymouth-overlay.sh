#!/usr/bin/env bash
# PINCABOS_ISO_ETAPES_V1 — etape 50-plymouth-overlay d iso.sh (texte de l ancienne section, inchange)
set -Eeuo pipefail
. "$(dirname "$(readlink -f "$0")")/00-lib.sh"
trap cleanup_mounts EXIT

echo
echo "=== 6) Build Plymouth overlay ==="
tar \
  --acls \
  --xattrs \
  --numeric-owner \
  -I 'zstd -T0 -10' \
  -cpf "$OVERLAY" \
  -C "$PCO_ISO_SOURCE" \
  usr/share/plymouth/themes/pincabos \
  etc/plymouth
