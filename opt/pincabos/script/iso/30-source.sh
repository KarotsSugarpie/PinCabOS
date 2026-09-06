#!/usr/bin/env bash
# PINCABOS_ISO_ETAPES_V1 — etape 30-source d iso.sh (texte de l ancienne section, inchange)
set -Eeuo pipefail
. "$(dirname "$(readlink -f "$0")")/00-lib.sh"
trap cleanup_mounts EXIT

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
