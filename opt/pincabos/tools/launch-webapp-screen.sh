#!/usr/bin/env bash
# PinCabOS-File created by Karots Sugarpie
set -u

SCREEN_ID="${1:-0}"
URL="${2:-http://127.0.0.1/}"

export DISPLAY="${DISPLAY:-:0}"
export HOME="/home/pinball"
export XDG_RUNTIME_DIR="/run/user/1000"
export XAUTHORITY="/home/pinball/.Xauthority"

mkdir -p /opt/pincabos/logs

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

choose_fallback_screen() {
  local id geom
  # Pour Playfield/Backglass: on respecte l'écran demandé si possible.
  # Si absent, fallback visible vers écran 0 pour VM/test.
  for id in "$SCREEN_ID" 0; do
    geom="$(get_geometry_from_xrandr "$id" || true)"
    if [ -n "$geom" ]; then
      SCREEN_ID="$id"
      GEOM="$geom"
      return 0
    fi
  done
  return 1
}

if ! [[ "$SCREEN_ID" =~ ^[0-9]+$ ]]; then
  SCREEN_ID="0"
fi

GEOM="$(get_geometry_from_xrandr "$SCREEN_ID" || true)"
if [ -z "$GEOM" ]; then
  echo "WARN: écran WebApp ID $SCREEN_ID introuvable, fallback écran 0"
  if ! choose_fallback_screen; then
    echo "ERREUR: aucune géométrie xrandr utilisable"
    sudo -u pinball env DISPLAY=:0 XAUTHORITY=/home/pinball/.Xauthority xrandr --query || true
    exit 1
  fi
fi

SCREEN_W="$(echo "$GEOM" | sed -E 's/^([0-9]+)x([0-9]+)\+([-0-9]+)\+([-0-9]+)$/\1/')"
SCREEN_H="$(echo "$GEOM" | sed -E 's/^([0-9]+)x([0-9]+)\+([-0-9]+)\+([-0-9]+)$/\2/')"
SCREEN_X="$(echo "$GEOM" | sed -E 's/^([0-9]+)x([0-9]+)\+([-0-9]+)\+([-0-9]+)$/\3/')"
SCREEN_Y="$(echo "$GEOM" | sed -E 's/^([0-9]+)x([0-9]+)\+([-0-9]+)\+([-0-9]+)$/\4/')"

CHROME_BIN="$(command -v google-chrome || command -v google-chrome-stable || command -v chromium-browser || command -v chromium || true)"
if [ -z "$CHROME_BIN" ]; then
  echo "ERREUR: aucun navigateur Chrome/Chromium trouvé" | tee -a /opt/pincabos/logs/menu-webapp-screen-launch-error.log
  exit 1
fi

PROFILE="/tmp/pincabos_webapp_screen_${SCREEN_ID}"
WIN_NAME="pincabos-webapp-screen-${SCREEN_ID}"
LOG="/opt/pincabos/logs/menu-webapp-screen-${SCREEN_ID}.log"

rm -rf "$PROFILE"
mkdir -p "$PROFILE"
chown -R pinball:pinball "$PROFILE" 2>/dev/null || true

echo "PinCabOS WebApp screen launch:" | tee -a "$LOG"
echo "  screen_id=$SCREEN_ID" | tee -a "$LOG"
echo "  geometry=${SCREEN_W}x${SCREEN_H}+${SCREEN_X}+${SCREEN_Y}" | tee -a "$LOG"
echo "  url=$URL" | tee -a "$LOG"

touch "/run/pincabos-webapp-screen-${SCREEN_ID}.active" 2>/dev/null || true
chmod 666 "/run/pincabos-webapp-screen-${SCREEN_ID}.active" 2>/dev/null || true

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
    >>"$LOG" 2>&1 &

exit 0
