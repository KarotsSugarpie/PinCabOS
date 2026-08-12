#!/usr/bin/env bash
set -Eeuo pipefail

LOG="/var/log/pincabos/usb-secure-lock.log"
mkdir -p "$(dirname "$LOG")"

{
  echo
  echo "===== $(date '+%F %T') USB SECURE LOCK APPLY ====="

  if [ -w /sys/module/usbcore/parameters/autosuspend ]; then
    echo -1 >/sys/module/usbcore/parameters/autosuspend || true
    echo "usbcore autosuspend=-1 appliqué"
  fi

  for dev in /sys/bus/usb/devices/*; do
    [ -d "$dev" ] || continue

    product="$(cat "$dev/product" 2>/dev/null || true)"
    manufacturer="$(cat "$dev/manufacturer" 2>/dev/null || true)"
    serial="$(cat "$dev/serial" 2>/dev/null || true)"
    label="$manufacturer $product $serial"

    if echo "$label" | grep -Eiq 'DudesCab|Ultimate VPinball|LED.?Wiz|LedWiz|Pinscape'; then
      echo "USB lock: $(basename "$dev") :: $label"

      [ -w "$dev/power/control" ] && echo on >"$dev/power/control" || true
      [ -w "$dev/power/autosuspend" ] && echo -1 >"$dev/power/autosuspend" || true
      [ -w "$dev/power/autosuspend_delay_ms" ] && echo -1 >"$dev/power/autosuspend_delay_ms" || true
      [ -w "$dev/power/wakeup" ] && echo disabled >"$dev/power/wakeup" || true
      [ -w "$dev/power/persist" ] && echo 1 >"$dev/power/persist" || true
    fi
  done

  echo "--- USB devices toys détectés ---"
  for dev in /sys/bus/usb/devices/*; do
    [ -d "$dev" ] || continue
    product="$(cat "$dev/product" 2>/dev/null || true)"
    manufacturer="$(cat "$dev/manufacturer" 2>/dev/null || true)"
    if echo "$manufacturer $product" | grep -Eiq 'DudesCab|Ultimate VPinball|LED.?Wiz|LedWiz|Pinscape'; then
      printf '%s | manufacturer=%s | product=%s | control=%s | autosuspend=%s\n' \
        "$(basename "$dev")" \
        "$manufacturer" \
        "$product" \
        "$(cat "$dev/power/control" 2>/dev/null || echo '?')" \
        "$(cat "$dev/power/autosuspend_delay_ms" 2>/dev/null || cat "$dev/power/autosuspend" 2>/dev/null || echo '?')"
    fi
  done
} >>"$LOG" 2>&1
