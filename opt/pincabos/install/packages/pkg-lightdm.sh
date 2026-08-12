#!/usr/bin/env bash
# Created by Karots Sugarpie
# PINCABOS_SCRIPT_NAME="pkg-lightdm.sh"
# PINCABOS_SCRIPT_ROLE="Install and enable LightDM display manager"
# PINCABOS_SCRIPT_REQUIRES_FILES="/opt/pincabos/install/packages/pkg-lib.sh"
# PINCABOS_SCRIPT_REQUIRES_PACKAGES="lightdm lightdm-gtk-greeter"
# PINCABOS_SCRIPT_REQUIRES_COMMANDS="lightdm systemctl"
# PINCABOS_SCRIPT_LOG_DIR="/opt/pincabos/logs"
# PINCABOS_SCRIPT_MANIFEST="/opt/pincabos/install/install.json"

PKG_NAME="pkg-lightdm"
PKG_TITLE="LightDM display manager"
source /opt/pincabos/install/packages/pkg-lib.sh

main() {
  pkg_start
  pco_step "01" "Install LightDM"
  apt_install_available lightdm lightdm-gtk-greeter

  pco_step "02" "Enable LightDM without reboot"
  run_spin "Enable lightdm.service" systemctl enable lightdm.service

  pco_step "03" "Validate LightDM"
  optional_command lightdm
  pkg_done
}

main "$@"
