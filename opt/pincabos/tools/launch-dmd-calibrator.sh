#!/usr/bin/env bash
# PinCabOS-File created by Karots Sugarpie
set -u

export DISPLAY="${DISPLAY:-:0}"
export HOME="/home/pinball"
export XDG_RUNTIME_DIR="/run/user/1000"
export XAUTHORITY="/home/pinball/.Xauthority"

mkdir -p /opt/pincabos/logs

CAL="/opt/pincabos/config/dmd-calibration.json"
URL_BASE="${1:-http://127.0.0.1/dmd-screen}"

read_json_value() {
  local key="$1"
  local default="$2"
  python3 - "$CAL" "$key" "$default" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
key = sys.argv[2]
default = sys.argv[3]
try:
    d = json.loads(p.read_text(errors="replace"))
except Exception:
    d = {}

# Si le fichier contient déjà une structure local/real, privilégier local pour réouvrir le rectangle.
if key in ("x", "y", "width", "height") and isinstance(d.get("local"), dict):
    print(d["local"].get(key, default))
else:
    print(d.get(key, default))
PY
}

get_geometry_from_xrandr() {
  local wanted="$1"
  sudo -u pinball env DISPLAY=:0 XAUTHORITY=/home/pinball/.Xauthority xrandr --query 2>/dev/null | awk -v wanted="$wanted" '
    $2 == "connected" {
      geom=""
      for (i=1; i<=NF; i++) {
        if ($i ~ /^[0-9]+x[0-9]+\+[0-9-]+\+[0-9-]+$/) {
          geom=$i
          break
        }
      }
      if (geom != "") print geom
    }
  ' | sed -n "$((wanted + 1))p"
}

choose_best_calibration_screen() {
  local id geom
  for id in 2 1 0; do
    geom="$(get_geometry_from_xrandr "$id" || true)"
    if [ -n "$geom" ]; then
      SCREEN_ID="$id"
      GEOM="$geom"
      return 0
    fi
  done
  return 1
}

SCREEN_ID="$(read_json_value screen_id 2)"
if ! [[ "$SCREEN_ID" =~ ^[0-9]+$ ]]; then
  SCREEN_ID="2"
fi

GEOM="$(get_geometry_from_xrandr "$SCREEN_ID")"
if [ -z "$GEOM" ]; then
  echo "WARN: écran demandé ID $SCREEN_ID introuvable, sélection prioritaire 3e > 2e > 1er"
  if ! choose_best_calibration_screen; then
    echo "ERREUR: impossible de trouver une géométrie xrandr utilisable pour DMD"
    sudo -u pinball env DISPLAY=:0 XAUTHORITY=/home/pinball/.Xauthority xrandr --query || true
    exit 1
  fi
fi

SCREEN_W="$(echo "$GEOM" | sed -E 's/^([0-9]+)x([0-9]+)\+([-0-9]+)\+([-0-9]+)$/\1/')"
SCREEN_H="$(echo "$GEOM" | sed -E 's/^([0-9]+)x([0-9]+)\+([-0-9]+)\+([-0-9]+)$/\2/')"
SCREEN_X="$(echo "$GEOM" | sed -E 's/^([0-9]+)x([0-9]+)\+([-0-9]+)\+([-0-9]+)$/\3/')"
SCREEN_Y="$(echo "$GEOM" | sed -E 's/^([0-9]+)x([0-9]+)\+([-0-9]+)\+([-0-9]+)$/\4/')"

# DMD = rectangle interne dans la même fenêtre/surface que FullDMD.
LOCAL_X="$(read_json_value x 80)"
LOCAL_Y="$(read_json_value y 40)"
LOCAL_W="$(read_json_value width 512)"
LOCAL_H="$(read_json_value height 128)"

PROFILE="/tmp/pincabos_dmd_calibrator_screen${SCREEN_ID}"
WIN_NAME="pincabos-dmd-calibrator"

CHROME_BIN="$(command -v google-chrome || command -v google-chrome-stable || command -v chromium-browser || command -v chromium || true)"
if [ -z "$CHROME_BIN" ]; then
  echo "ERREUR: aucun navigateur Chrome/Chromium trouvé" | tee -a /opt/pincabos/logs/dmd-calibrator-launch-error.log
  exit 1
fi

URL="${URL_BASE}?override=${LOCAL_X},${LOCAL_Y},${LOCAL_W},${LOCAL_H}&window=${SCREEN_X},${SCREEN_Y},${SCREEN_W},${SCREEN_H}&screen_id=${SCREEN_ID}"

rm -rf "$PROFILE"
mkdir -p "$PROFILE"
chown -R pinball:pinball "$PROFILE" 2>/dev/null || true

echo "PinCabOS DMD calibration:"
echo "  screen_id=$SCREEN_ID"
echo "  dmd_calibration_window=${SCREEN_W}x${SCREEN_H}+${SCREEN_X}+${SCREEN_Y}"
echo "  local_rectangle=${LOCAL_X},${LOCAL_Y},${LOCAL_W},${LOCAL_H}"
echo "  real_formula=x=${SCREEN_X}+${LOCAL_X}, y=${SCREEN_Y}+${LOCAL_Y}"
echo "  url=$URL"

touch /run/pincabos-dmd-calibrator.active 2>/dev/null || true
chmod 666 /run/pincabos-dmd-calibrator.active 2>/dev/null || true

sudo -u pinball env \
  DISPLAY=:0 \
  XAUTHORITY=/home/pinball/.Xauthority \
  HOME=/home/pinball \
  XDG_RUNTIME_DIR=/run/user/1000 \
  "$CHROME_BIN" \
    --app="$URL" \
    --window-name="$WIN_NAME" \
    --window-position="$SCREEN_X,$SCREEN_Y" \
    --window-size="$SCREEN_W,$SCREEN_H" \
    --user-data-dir="$PROFILE" \
    --kiosk \
    --start-maximized \
    --no-first-run \
    --noerrdialogs \
    --disable-infobars \
    --disable-session-crashed-bubble \
    --disable-restore-session-state \
    --disable-background-networking \
    --disable-component-update \
    --disable-default-apps \
    --disable-background-timer-throttling \
    --disable-backgrounding-occluded-windows \
    --disable-renderer-backgrounding \
    --disable-features=CalculateNativeWindowOcclusion,PreloadMediaEngagementData,MediaEngagementBypassAutoplayPolicies \
    --disable-hang-monitor \
    --disable-ipc-flooding-protection \
    --disable-gpu-process-crash-limit \
    --ignore-gpu-blocklist \
    --no-sandbox \
    --disable-gpu-sandbox \
    --test-type \
    --log-level=3 \
    >/tmp/pincabos_dmd_calibrator.log 2>&1 &

exit 0
