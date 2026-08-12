#!/usr/bin/env bash
# PinCabOS — lancement VPX permanent
# LED-Wiz : LIBUSB local isole
# DudesCab + UMX : HIDRAW

set -Eeuo pipefail

PINBALL_USER="pinball"
PINBALL_HOME="/home/pinball"

VPX_MAIN="/home/pinball/VPinballX_BGFX-10.8.1-5231-7ca174632-linux-x64/VPinballX_BGFX"
VPX_ALT="/home/pinball/VPinballX_BGFX-10.8.1-5231-7ca174632-linux-x64/VPinballX_BGFX.pincabos-original-paced2"
DOF_DIR="/home/pinball/VPinballX_BGFX-10.8.1-5231-7ca174632-linux-x64/plugins/dof"
OVERLAY="/opt/pincabos/overlays/libdof-ledwiz-hidraw-stable"
DOF_LOCAL="/opt/pincabos/overlays/libdof-ledwiz-hidraw-stable/libdof.so.0.4.7"
HIDUSB="/usr/lib/x86_64-linux-gnu/libhidapi-libusb.so.0.15.0"

DEFAULT_TABLE="/home/pinball/Tables/Attack from Mars (Bally 1995)/Attack from Mars (Midway 1995).vpx"

die() {
  echo "ERREUR: $*" >&2
  exit 1
}

if file "$VPX_MAIN" 2>/dev/null | grep -q 'ELF'; then
  VPX="$VPX_MAIN"
elif file "$VPX_ALT" 2>/dev/null | grep -q 'ELF'; then
  VPX="$VPX_ALT"
else
  die "Aucun binaire VPX ELF valide trouve."
fi

# Compatible avec:
# - appel direct: VPXlauncher.sh "/chemin/table.vpx"
# - appel VPinFE: VPXlauncher.sh -ini ... -tableini ... -play "/chemin/table.vpx"
ORIGINAL_ARGS=("$@")
TABLE=""

for ((i=0; i<${#ORIGINAL_ARGS[@]}; i++)); do
  if [[ "${ORIGINAL_ARGS[$i]}" == "-play" ]]; then
    (( i + 1 < ${#ORIGINAL_ARGS[@]} )) || die "Option -play sans table."
    TABLE="${ORIGINAL_ARGS[$((i + 1))]}"
    break
  fi
done

if [[ -n "$TABLE" ]]; then
  # VPinFE: preserve exactement -ini, -tableini et -play.
  VPX_ARGS=("${ORIGINAL_ARGS[@]}")
elif [[ ${#ORIGINAL_ARGS[@]} -eq 0 ]]; then
  TABLE="$DEFAULT_TABLE"
  VPX_ARGS=(-play "$TABLE")
else
  # Compatibilité lancement manuel historique.
  TABLE="${ORIGINAL_ARGS[0]}"
  VPX_ARGS=(-play "$TABLE" "${ORIGINAL_ARGS[@]:1}")
fi

[[ -x "$VPX" ]] || die "VPX absent: $VPX"
[[ -f "$TABLE" ]] || die "Table absente: $TABLE"
[[ -f "$DOF_LOCAL" ]] || die "libdof permanent absent."
[[ -f "$HIDUSB" ]] || die "backend LED-Wiz absent."

ENV_ARGS=(
  -u LD_PRELOAD
  HOME="$PINBALL_HOME"
  USER="$PINBALL_USER"
  LOGNAME="$PINBALL_USER"
  DISPLAY="${DISPLAY:-:0}"
  XAUTHORITY="$PINBALL_HOME/.Xauthority"
  XDG_RUNTIME_DIR="/run/user/1000"
  DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/1000/bus"
  XDG_DATA_HOME="$PINBALL_HOME/.local/share"
  XDG_CONFIG_HOME="$PINBALL_HOME/.config"
  XDG_CACHE_HOME="$PINBALL_HOME/.cache"
  SDL_VIDEODRIVER="x11"
  LD_LIBRARY_PATH="$OVERLAY:$DOF_DIR"
  LD_PRELOAD="$DOF_LOCAL"
  LIBDOF_LEDWIZ_HIDAPI_LIBUSB="$HIDUSB"
)

if [[ "$(id -u)" -eq 0 ]]; then
  exec runuser -u "$PINBALL_USER" -- env "${ENV_ARGS[@]}" "$VPX" "${VPX_ARGS[@]}"
fi

[[ "$(id -un)" == "$PINBALL_USER" ]] ||   die "Lance ce script comme root ou pinball."

exec env "${ENV_ARGS[@]}" "$VPX" "${VPX_ARGS[@]}"
