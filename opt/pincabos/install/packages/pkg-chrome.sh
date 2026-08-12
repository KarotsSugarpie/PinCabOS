#!/usr/bin/env bash
# Created by Karots Sugarpie
# PINCABOS_SCRIPT_NAME="pkg-chrome.sh"
# PINCABOS_SCRIPT_ROLE="Install Google Chrome Stable for PinCabOS kiosk/WebApp mode"
# PINCABOS_SCRIPT_REQUIRES_FILES="/opt/pincabos/install/packages/pkg-lib.sh"
# PINCABOS_SCRIPT_REQUIRES_PACKAGES="wget ca-certificates fonts-liberation xdg-utils"
# PINCABOS_SCRIPT_REQUIRES_COMMANDS="wget apt-get google-chrome"
# PINCABOS_SCRIPT_LOG_DIR="/opt/pincabos/logs"
# PINCABOS_SCRIPT_MANIFEST="/opt/pincabos/install/install.json"

PKG_NAME="pkg-chrome"
PKG_TITLE="Google Chrome Stable"
source /opt/pincabos/install/packages/pkg-lib.sh

main() {
  pkg_start

  pco_step "01" "Install Chrome prerequisites"
  apt_install_available wget ca-certificates fonts-liberation xdg-utils

  if command -v google-chrome >/dev/null 2>&1 || command -v google-chrome-stable >/dev/null 2>&1; then
    pco_go "Google Chrome already installed"
    pkg_done
    return 0
  fi

  pco_step "02" "Download Google Chrome Stable"
  tmp="/tmp/google-chrome-stable_current_amd64.deb"
  run_spin "Download Chrome .deb" wget -O "$tmp" "https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb"

  pco_step "03" "Install Google Chrome Stable"
  run_spin "Install Chrome .deb" apt-get install -y "$tmp"

  pco_step "04" "Validate Chrome"
  if command -v google-chrome >/dev/null 2>&1 || command -v google-chrome-stable >/dev/null 2>&1; then
    pco_go "Google Chrome installed"
  else
    pco_nogo "ERR-PKG-CHROME-VALIDATE-001" "Google Chrome command not found after install"
  fi

  pkg_done
}

main "$@"
