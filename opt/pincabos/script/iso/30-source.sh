#!/usr/bin/env bash
# PINCABOS_ISO_ETAPES_V1 — etape 30-source d iso.sh (texte de l ancienne section, inchange)
set -Eeuo pipefail
. "$(dirname "$(readlink -f "$0")")/00-lib.sh"
trap cleanup_mounts EXIT

echo
echo "=== 4) Validate source cabinet boot, modules, GRUB and Plymouth ==="
# PINCABOS_ISO_SOURCE_V1 : la source est le cab courant (/) ou un rootfs prepare
echo "Source: $PCO_ISO_SOURCE"
test -d "$SRC/boot" || die "$SRC/boot missing"
test -d "$SRC/lib/modules" || die "$SRC/lib/modules missing"
test -f "$SRC/etc/default/grub" || die "$SRC/etc/default/grub missing"
test -f "$SRC/usr/share/plymouth/themes/pincabos/pincabos.plymouth" || die "Plymouth pincabos theme missing"
ls "$SRC"/boot/vmlinuz-* >/dev/null || die "No kernel in $SRC/boot"
ls "$SRC"/boot/initrd.img-* >/dev/null || die "No initrd in $SRC/boot"
ls "$SRC"/lib/modules/* >/dev/null || die "No modules in $SRC/lib/modules"
test -d "$SRC/opt/pincabos" || die "$SRC/opt/pincabos missing : not a PinCabOS root"

echo "OK: source boot/modules/grub/plymouth present"
