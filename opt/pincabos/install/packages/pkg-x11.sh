#!/usr/bin/env bash
# Created by Karots Sugarpie
# PINCABOS_SCRIPT_NAME="pkg-x11.sh"
# PINCABOS_SCRIPT_ROLE="Install X11 display stack and desktop helpers required by PinCabOS cabinet mode"
# PINCABOS_SCRIPT_REQUIRES_FILES="/opt/pincabos/install/packages/pkg-lib.sh"
# PINCABOS_SCRIPT_REQUIRES_PACKAGES="xorg xinit x11-xserver-utils xserver-xorg-input-libinput xdotool wmctrl xterm dbus-x11 polkitd pkexec"
# PINCABOS_SCRIPT_REQUIRES_COMMANDS="Xorg xrandr xset xdotool wmctrl dbus-launch"
# PINCABOS_SCRIPT_LOG_DIR="/opt/pincabos/logs"
# PINCABOS_SCRIPT_MANIFEST="/opt/pincabos/install/install.json"

PKG_NAME="pkg-x11"
PKG_TITLE="X11 display stack"
source /opt/pincabos/install/packages/pkg-lib.sh

main() {
  pkg_start
  pco_step "01" "Install X11 packages"
  apt_install_available \
    xorg xinit x11-xserver-utils xserver-xorg-input-libinput \
    xdotool wmctrl xterm dbus-x11 polkitd pkexec

  pco_step "02" "Validate X11 tools"
  optional_command Xorg xrandr xset xdotool wmctrl dbus-launch
  pkg_done
}

main "$@"
