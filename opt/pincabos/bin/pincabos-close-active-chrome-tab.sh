#!/usr/bin/env bash
set -u

LOG="/opt/pincabos/logs/menu-close-tab.log"
mkdir -p "$(dirname "$LOG")" 2>/dev/null || true

log() {
  echo "[$(date '+%F %T')] $*" >> "$LOG" 2>/dev/null || true
}

run_as_pinball() {
  if [ "$(id -un 2>/dev/null || true)" = "pinball" ]; then
    env DISPLAY="${DISPLAY:-:0}" XAUTHORITY="${XAUTHORITY:-/home/pinball/.Xauthority}" "$@"
  else
    sudo -n -u pinball env DISPLAY="${DISPLAY:-:0}" XAUTHORITY="${XAUTHORITY:-/home/pinball/.Xauthority}" "$@"
  fi
}

log "---- close-tab request start uid=$(id -un 2>/dev/null) DISPLAY=${DISPLAY:-unset} XAUTHORITY=${XAUTHORITY:-unset}"

export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-/home/pinball/.Xauthority}"

if ! command -v xdotool >/dev/null 2>&1; then
  log "NOGO xdotool missing"
  echo "NOGO: xdotool missing"
  exit 20
fi

# 1) Prefer active window, because the click comes from Chrome.
ACTIVE="$(run_as_pinball xdotool getactivewindow 2>>"$LOG" || true)"
ACTIVE_CLASS=""
ACTIVE_NAME=""
if [ -n "$ACTIVE" ]; then
  ACTIVE_CLASS="$(run_as_pinball xdotool getwindowclassname "$ACTIVE" 2>>"$LOG" || true)"
  ACTIVE_NAME="$(run_as_pinball xdotool getwindowname "$ACTIVE" 2>>"$LOG" || true)"
fi
log "active=$ACTIVE class=$ACTIVE_CLASS name=$ACTIVE_NAME"

is_chrome_window() {
  echo "$1 $2" | grep -Eiq 'chrome|chromium|google-chrome|Google-chrome'
}

send_ctrl_w() {
  local win="$1"
  log "try ctrl+w win=$win"
  run_as_pinball xdotool windowactivate --sync "$win" 2>>"$LOG" || true
  sleep 0.15
  run_as_pinball xdotool key --clearmodifiers ctrl+w >>"$LOG" 2>&1
}

close_window_wmctrl() {
  local win="$1"
  if command -v wmctrl >/dev/null 2>&1; then
    local hex
    hex="$(printf '0x%08x' "$win" 2>/dev/null || true)"
    if [ -n "$hex" ]; then
      log "try wmctrl close win=$win hex=$hex"
      run_as_pinball wmctrl -ic "$hex" >>"$LOG" 2>&1 || true
    fi
  fi
}

# If active window is Chrome, Ctrl+W is the clean tab close.
if [ -n "$ACTIVE" ] && is_chrome_window "$ACTIVE_CLASS" "$ACTIVE_NAME"; then
  send_ctrl_w "$ACTIVE"
  sleep 0.30

  # If still active and same window, try again once.
  ACTIVE2="$(run_as_pinball xdotool getactivewindow 2>>"$LOG" || true)"
  log "after ctrl+w active2=$ACTIVE2"

  if [ "$ACTIVE2" = "$ACTIVE" ]; then
    log "same active window after ctrl+w, trying alt+F4/window close fallback"
    run_as_pinball xdotool key --clearmodifiers alt+F4 >>"$LOG" 2>&1 || true
    sleep 0.20
    close_window_wmctrl "$ACTIVE"
  fi

  echo "GO: close command sent to active Chrome window: class=$ACTIVE_CLASS name=$ACTIVE_NAME"
  log "GO close command sent active"
  exit 0
fi

# 2) If active is not Chrome, find visible Chrome windows and close the newest/last one.
SEARCH="$(run_as_pinball xdotool search --onlyvisible --class 'chrome|chromium|google-chrome|Google-chrome' 2>>"$LOG" || true)"
log "search result=$SEARCH"

WIN="$(echo "$SEARCH" | tail -n 1 | tr -d '[:space:]')"
if [ -n "$WIN" ]; then
  CLASS="$(run_as_pinball xdotool getwindowclassname "$WIN" 2>>"$LOG" || true)"
  NAME="$(run_as_pinball xdotool getwindowname "$WIN" 2>>"$LOG" || true)"
  log "selected=$WIN class=$CLASS name=$NAME"

  send_ctrl_w "$WIN"
  sleep 0.30

  # For kiosk/app mode, Ctrl+W can be ignored. Fallback closes the Chrome window.
  log "fallback alt+F4/window close selected"
  run_as_pinball xdotool key --clearmodifiers alt+F4 >>"$LOG" 2>&1 || true
  sleep 0.20
  close_window_wmctrl "$WIN"

  echo "GO: close command sent to selected Chrome window: class=$CLASS name=$NAME"
  log "GO close command sent selected"
  exit 0
fi

log "NOGO no Chrome window found"
echo "NOGO: no visible Chrome/Chromium window found"
exit 22
