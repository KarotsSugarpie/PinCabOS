#!/usr/bin/env bash
set -Eeuo pipefail
# PINCABOS_PUP_SCOREVIEW_LAYER_WATCH_V3

PARENT_PID="${1:-0}"
TABLE="${2:-unknown}"
DISPLAY="${DISPLAY:-:0}"
XAUTHORITY="${XAUTHORITY:-/home/pinball/.Xauthority}"
XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
X="${PINCABOS_FULLDMD_X:-5760}"
Y="${PINCABOS_FULLDMD_Y:-0}"
W="${PINCABOS_FULLDMD_W:-1920}"
H="${PINCABOS_FULLDMD_H:-1200}"
RUNTIME="${XDG_RUNTIME_DIR}/pincabos-pup-scoreview-layer"
LOG="/var/log/pincabos-hybrid-launcher/pup-scoreview-layer.log"
mkdir -p "$RUNTIME"
[[ -w "$(dirname "$LOG")" ]] || LOG="$RUNTIME/pup-scoreview-layer.log"
exec 9>"$RUNTIME/watcher.lock"
flock -n 9 || exit 0

log(){ printf '%s %s\n' "$(date -Is)" "$*" >> "$LOG" 2>/dev/null || true; }
find_score(){ wmctrl -lx 2>/dev/null | awk 'BEGIN{IGNORECASE=1}/Visual Pinball Score View/{print $1;exit}'; }
vpx_active(){ pgrep -u "$(id -u)" -f '[V]PinballX' >/dev/null 2>&1; }
apply_layer(){
  local id="$1"
  wmctrl -i -r "$id" -e "0,${X},${Y},${W},${H}" >/dev/null 2>&1 || true
  wmctrl -i -r "$id" -b add,above >/dev/null 2>&1 || true
  wmctrl -i -r "$id" -b add,skip_taskbar >/dev/null 2>&1 || true
  wmctrl -i -r "$id" -b add,skip_pager >/dev/null 2>&1 || true
  command -v xdotool >/dev/null 2>&1 && xdotool windowraise "$id" >/dev/null 2>&1 || true
}

seen_vpx=0
seen_score=0
last_id=""
loops=0
log "START table=$TABLE parent=$PARENT_PID"

while :; do
  if vpx_active; then
    seen_vpx=1
  elif (( seen_vpx == 1 )); then
    break
  elif [[ "$PARENT_PID" =~ ^[0-9]+$ ]] && (( PARENT_PID > 0 )) && ! kill -0 "$PARENT_PID" 2>/dev/null; then
    break
  fi

  id="$(find_score || true)"
  if [[ -n "$id" ]]; then
    apply_layer "$id"
    seen_score=1
    if [[ "$id" != "$last_id" ]]; then
      log "SCOREVIEW_FOUND id=$id geometry=${W}x${H}+${X}+${Y} state=above"
      last_id="$id"
    fi
  fi

  loops=$((loops+1))
  (( loops < 80 )) && sleep 0.25 || sleep 0.75
done

log "STOP scoreview_seen=$seen_score"
