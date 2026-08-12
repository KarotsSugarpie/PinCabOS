#!/usr/bin/env bash
set -Eeuo pipefail

PINUSER="pinball"
LOG="/var/log/pincabos/dudescab-watchdog.log"
mkdir -p "$(dirname "$LOG")"

dude_count() {
  local c=0
  local dev product manufacturer
  for dev in /sys/bus/usb/devices/*; do
    [ -d "$dev" ] || continue
    product="$(cat "$dev/product" 2>/dev/null || true)"
    manufacturer="$(cat "$dev/manufacturer" 2>/dev/null || true)"
    if echo "$manufacturer $product" | grep -Eiq 'DudesCab|Ultimate VPinball'; then
      c=$((c+1))
    fi
  done
  echo "$c"
}

log() {
  echo "$(date '+%F %T') $*" >>"$LOG"
}

log "DudesCab watchdog lightweight started"

baseline=""

while true; do
  vpx_pids="$(pgrep -u "$PINUSER" -f 'VPinballX|VPinballX_BGFX' || true)"

  if [ -z "$vpx_pids" ]; then
    baseline=""
    sleep 3
    continue
  fi

  count="$(dude_count)"

  if [ -z "$baseline" ]; then
    if [ "$count" -gt 0 ]; then
      baseline="$count"
      log "VPX actif, baseline DudesCab=$baseline"
    else
      log "ATTENTION: VPX actif mais aucun DudesCab détecté"
    fi
  fi

  if [ -n "$baseline" ] && [ "$count" -lt "$baseline" ]; then
    log "ALERTE: DudesCab count $count < baseline $baseline pendant VPX. Arrêt sécurité VPX."
    pkill -TERM -u "$PINUSER" -f 'VPinballX|VPinballX_BGFX' || true
    sleep 2
    pkill -KILL -u "$PINUSER" -f 'VPinballX|VPinballX_BGFX' || true
    baseline=""
    systemctl start pincabos-vpinfe.service || true
    sleep 5
  fi

  sleep 1
done
