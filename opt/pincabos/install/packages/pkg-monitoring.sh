#!/usr/bin/env bash
# Created by Karots Sugarpie
# PINCABOS_SCRIPT_NAME="pkg-monitoring.sh"
# PINCABOS_SCRIPT_ROLE="Install monitoring tools required by PinCabOS System page and VPinFE diagnostics"
# PINCABOS_SCRIPT_REQUIRES_FILES="/opt/pincabos/install/packages/pkg-lib.sh"
# PINCABOS_SCRIPT_REQUIRES_PACKAGES="procps psmisc util-linux coreutils sysstat lm-sensors pciutils usbutils lshw nvtop mesa-utils vulkan-tools python3-psutil"
# PINCABOS_SCRIPT_REQUIRES_COMMANDS="ps free df lscpu lspci lsusb lshw sensors nvtop glxinfo vulkaninfo python3"
# PINCABOS_SCRIPT_LOG_DIR="/opt/pincabos/logs"
# PINCABOS_SCRIPT_MANIFEST="/opt/pincabos/install/install.json"

PKG_NAME="pkg-monitoring"
PKG_TITLE="System page monitoring tools"
source /opt/pincabos/install/packages/pkg-lib.sh

main() {
  pkg_start

  pco_step "01" "Install CPU / memory / disk / GPU monitoring tools"
  apt_install_available \
    procps psmisc util-linux coreutils sysstat lm-sensors pciutils usbutils lshw \
    nvtop mesa-utils vulkan-tools python3-psutil

  pco_step "02" "Validate System page tools"
  echo
  command -v ps >/dev/null 2>&1 && write_summary_line "CPU utilization tools" "OK" || write_summary_line "CPU utilization tools" "NOGO"
  command -v free >/dev/null 2>&1 && write_summary_line "Memory utilization tools" "OK" || write_summary_line "Memory utilization tools" "NOGO"
  command -v df >/dev/null 2>&1 && write_summary_line "Free disk space tools" "OK" || write_summary_line "Free disk space tools" "NOGO"
  command -v lspci >/dev/null 2>&1 && write_summary_line "GPU details tools" "OK" || write_summary_line "GPU details tools" "WARN"
  command -v nvtop >/dev/null 2>&1 && write_summary_line "GPU nvtop monitoring" "OK" || write_summary_line "GPU nvtop monitoring" "WARN"
  command -v glxinfo >/dev/null 2>&1 && write_summary_line "OpenGL information" "OK" || write_summary_line "OpenGL information" "WARN"
  command -v vulkaninfo >/dev/null 2>&1 && write_summary_line "Vulkan information" "OK" || write_summary_line "Vulkan information" "WARN"

  pco_step "03" "Hard validation"
  require_command ps free df python3
  optional_command lspci lsusb lshw sensors nvtop glxinfo vulkaninfo

  pkg_done
}

main "$@"
