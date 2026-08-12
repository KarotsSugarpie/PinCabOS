#!/usr/bin/env bash
# Created by Karots Sugarpie
# PINCABOS_SCRIPT_NAME="pkg-system-validation.sh"
# PINCABOS_SCRIPT_ROLE="Validate PinCabOS commands, full VPX BGFX app, full VPinFE app, wrappers, config, and services"
# PINCABOS_SCRIPT_REQUIRES_COMMANDS="bash command systemctl grep test"
# PINCABOS_SCRIPT_LOG_DIR="/opt/pincabos/logs"
# PINCABOS_SCRIPT_MANIFEST="/opt/pincabos/install/install.json"

set -Eeuo pipefail

ORANGE="\033[38;5;208m"; GREEN="\033[32m"; YELLOW="\033[33m"; RED="\033[31m"; NC="\033[0m"
failed=0
pco_go(){ echo -e "${GREEN}GO [√]${NC} $*"; }
pco_warn(){ echo -e "${YELLOW}WARN${NC} $*"; }
pco_nogo_soft(){ echo -e "${RED}NOGO [***]${NC} $*"; failed=1; }

echo -e "${ORANGE}PinCabOS - pkg-system-validation${NC}"

for c in bash curl wget jq tar unzip zstd xz file rsync python3 openbox-session xset; do
  command -v "$c" >/dev/null 2>&1 && pco_go "Command available: $c" || pco_nogo_soft "Missing command: $c"
done

command -v 7z >/dev/null 2>&1 && pco_go "Command available: 7z" || pco_warn "7z missing; archive support reduced"
command -v ttyd >/dev/null 2>&1 && pco_go "Optional ttyd available" || pco_warn "Optional ttyd missing"

[ -x /opt/pincabos/bin/vpx.sh ] && pco_go "VPX wrapper exists: /opt/pincabos/bin/vpx.sh" || pco_nogo_soft "Missing /opt/pincabos/bin/vpx.sh"
[ -x /opt/pincabos/apps/vpinball/VPinballX-BGFX ] && pco_go "VPX BGFX binary exists" || pco_nogo_soft "Missing /opt/pincabos/apps/vpinball/VPinballX-BGFX"
[ -f /home/pinball/.vpinball/VPinballX.ini ] && pco_go "VPX INI exists" || pco_nogo_soft "Missing VPinballX.ini"

[ -f /opt/pincabos/apps/frontend/vpinfe/current/main.py ] && pco_go "VPinFE main.py exists" || pco_nogo_soft "Missing VPinFE main.py"
[ -x /opt/pincabos/apps/frontend/vpinfe/current/.venv/bin/python ] && pco_go "VPinFE venv exists" || pco_nogo_soft "Missing VPinFE venv"
[ -x /opt/pincabos/tools/run-vpinfe.sh ] && pco_go "run-vpinfe.sh exists" || pco_nogo_soft "Missing run-vpinfe.sh"
grep -q '/opt/pincabos/bin/vpx.sh' /opt/pincabos/config/vpinfe/vpinfe.ini 2>/dev/null && pco_go "VPinFE points to vpx.sh" || pco_nogo_soft "VPinFE does not point to vpx.sh"

if grep -RInE 'VPinballX[_]GL|vpinball[_]gl|VPinball[_]GL|VPINBALL[_]GL' \
  /opt/pincabos/bin/vpx.sh \
  /home/pinball/.vpinball/VPinballX.ini \
  /opt/pincabos/config/vpinfe/vpinfe.ini 2>/dev/null
then
  pco_nogo_soft "Forbidden GL reference found in active runtime configs"
else
  pco_go "No forbidden GL reference in active runtime configs"
fi

systemctl list-unit-files pincabos-vpinfe.service >/dev/null 2>&1 && pco_go "pincabos-vpinfe.service installed" || pco_nogo_soft "Missing pincabos-vpinfe.service"
systemctl list-unit-files pincabos-vpinfe.service >/dev/null 2>&1 && pco_go "pincabos-vpinfe.service installed" || pco_nogo_soft "Missing pincabos-vpinfe.service"

[ "$failed" -eq 0 ] || exit 1
pco_go "pkg-system-validation completed"
