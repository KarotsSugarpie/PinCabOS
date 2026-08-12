#!/usr/bin/env bash
# Created by Karots Sugarpie
# PINCABOS_SCRIPT_NAME="pkg-openbox.sh"
# PINCABOS_SCRIPT_ROLE="Install Openbox and minimal kiosk desktop helpers"
# PINCABOS_SCRIPT_REQUIRES_FILES="/opt/pincabos/install/packages/pkg-lib.sh"
# PINCABOS_SCRIPT_REQUIRES_PACKAGES="openbox obconf menu tint2 feh unclutter"
# PINCABOS_SCRIPT_REQUIRES_COMMANDS="openbox feh unclutter"
# PINCABOS_SCRIPT_LOG_DIR="/opt/pincabos/logs"
# PINCABOS_SCRIPT_MANIFEST="/opt/pincabos/install/install.json"

PKG_NAME="pkg-openbox"
PKG_TITLE="Openbox kiosk desktop"
source /opt/pincabos/install/packages/pkg-lib.sh

main() {
  pkg_start
  pco_step "01" "Install Openbox and desktop helpers"
  apt_install_available openbox obconf menu tint2 feh unclutter

  pco_step "02" "Validate Openbox tools"
  require_command openbox
  optional_command feh unclutter
  pkg_done
}

main "$@"
