#!/usr/bin/env bash
# PINCABOS_SCRIPT_NAME="pkg-plymouth.sh"
# PINCABOS_SCRIPT_DESCRIPTION="Compatibility wrapper. Plymouth theme handling is delegated to modules/system/mod-plymouth-install.sh"
# PINCABOS_SCRIPT_REQUIRES_PACKAGES="plymouth plymouth-themes zstd tar"
# PINCABOS_SCRIPT_REQUIRES_COMMANDS="/usr/bin/bash /usr/bin/apt-get /usr/bin/dpkg /usr/sbin/update-initramfs"
# PINCABOS_SCRIPT_REQUIRES_FILES="/opt/pincabos/modules/system/mod-plymouth-install.sh"
# PINCABOS_SCRIPT_REQUIRES_DIRS="/opt/pincabos/modules/system /opt/pincabos/modules/system/assets/plymouth"
# PINCABOS_SCRIPT_TOUCHES="/usr/share/plymouth/themes/PinCabOs-install /usr/share/plymouth/themes/default.plymouth /boot/initrd*"
# Created by Karots Sugarpie

set +e

ORANGE="\033[38;5;208m"
GREEN="\033[32m"
RED="\033[31m"
NC="\033[0m"

clear
echo -e "${ORANGE}────────────────────────────────────────────────────────────────${NC}"
echo -e "${ORANGE} PinCabOS - pkg-plymouth wrapper${NC}"
echo -e "${ORANGE}────────────────────────────────────────────────────────────────${NC}"

MOD="/opt/pincabos/modules/system/mod-plymouth-install.sh"

echo
echo "=== 1) Install Plymouth package dependencies ==="
if command -v apt-get >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update || true
  apt-get install -y plymouth plymouth-themes zstd tar || true
fi

echo
echo "=== 2) Delegate to module ==="
if [ ! -x "$MOD" ]; then
  echo -e "${RED}NOGOOD:${NC} module absent: $MOD"
  exit 1
fi

bash "$MOD"
RC=$?

echo
echo "=== Résultat pkg-plymouth wrapper ==="
echo "RC=$RC"

if [ "$RC" -eq 0 ]; then
  echo -e "${GREEN}GO:${NC} pkg-plymouth delegated to module successfully"
else
  echo -e "${RED}NOGOOD:${NC} module returned RC=$RC"
fi

exit "$RC"
