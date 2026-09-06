#!/usr/bin/env bash
# PINCABOS_ISO_ETAPES_V1 — etape 20-outils-hote d iso.sh (texte de l ancienne section, inchange)
set -Eeuo pipefail
. "$(dirname "$(readlink -f "$0")")/00-lib.sh"
trap cleanup_mounts EXIT

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
