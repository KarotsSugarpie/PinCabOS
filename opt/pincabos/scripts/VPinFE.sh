#!/usr/bin/env bash
set -Eeuo pipefail

PINBALL_USER="pinball"
PINBALL_HOME="/home/pinball"
VFE_BIN="/home/pinball/vpinfe/vpinfe"
DOF_BUNDLE="/opt/pincabos/overlays/vpinfe-dof-ledwiz-hidraw-stable"
HIDUSB="/usr/lib/x86_64-linux-gnu/libhidapi-libusb.so.0.15.0"

[[ -x "$VFE_BIN" ]] || {
  echo "ERREUR: VPinFE absent." >&2
  exit 1
}

[[ -f "$DOF_BUNDLE/libdof_python.so" ]] || {
  echo "ERREUR: bridge DOF VPinFE absent." >&2
  exit 1
}

# Aucun LD_PRELOAD.
# LD_LIBRARY_PATH force uniquement le bridge DOF VPinFE
# a prendre le libdof hybride local.
if [[ "$(id -u)" -eq 0 ]]; then
  exec runuser -u "$PINBALL_USER" -- env     -u LD_PRELOAD     HOME="$PINBALL_HOME"     USER="$PINBALL_USER"     LOGNAME="$PINBALL_USER"     PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"     DISPLAY="${DISPLAY:-:0}"     XAUTHORITY="$PINBALL_HOME/.Xauthority"     XDG_RUNTIME_DIR="/run/user/1000"     DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/1000/bus"     LD_LIBRARY_PATH="$DOF_BUNDLE"     VPINFE_DOF_DIR="$DOF_BUNDLE"     LIBDOF_LEDWIZ_HIDAPI_LIBUSB="$HIDUSB"     "$VFE_BIN" "$@"
fi

exec env   -u LD_PRELOAD   LD_LIBRARY_PATH="$DOF_BUNDLE"   VPINFE_DOF_DIR="$DOF_BUNDLE"   LIBDOF_LEDWIZ_HIDAPI_LIBUSB="$HIDUSB"   "$VFE_BIN" "$@"
