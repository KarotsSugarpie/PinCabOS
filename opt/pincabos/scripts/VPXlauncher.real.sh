#!/usr/bin/env bash
set -Eeuo pipefail
# PINCABOS_DMD_OVERLAY_SCOREVIEW_CONTENT_V6_PUP_LAYER

POLICY="/opt/pincabos/bin/pincabos-native-b2s-scoreview-prelaunch.sh"
SCOREVIEW="/opt/pincabos/bin/pincabos-hybrid-scoreview-enable-prelaunch.py"
PUP_LAYER="/opt/pincabos/bin/pincabos-pup-scoreview-layer-watch.sh"
REAL="/opt/pincabos/scripts/VPXlauncher.pincabos-original.sh"

[[ -x "$POLICY" ]] && "$POLICY" "$@" || true
[[ -x "$SCOREVIEW" ]] && "$SCOREVIEW" "$@" || true

MODE="${PINCABOS_GAME_CHOICE:-original}"
MODE="${MODE,,}"
TABLE=""
for arg in "$@"; do
  [[ "${arg,,}" == *.vpx ]] && { TABLE="$arg"; break; }
done

if [[ "$MODE" == pup* && -x "$PUP_LAYER" ]]; then
  "$PUP_LAYER" "$$" "${TABLE:-unknown}" >/dev/null 2>&1 &
fi

if [[ "${PINCABOS_DMD_PRELAUNCH_ONLY:-0}" == "1" ]]; then
  exit 0
fi

exec "$REAL" "$@"
