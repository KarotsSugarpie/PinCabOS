#!/usr/bin/env bash
set -u

MARKER="PINCABOS_DUDESCAB_NO_AUTOSUSPEND_V1"
FOUND=0

for DEV in /sys/bus/usb/devices/*; do
    [ -r "$DEV/idVendor" ] || continue
    [ -r "$DEV/idProduct" ] || continue

    VENDOR="$(tr '[:upper:]' '[:lower:]' < "$DEV/idVendor")"
    PRODUCT="$(tr '[:upper:]' '[:lower:]' < "$DEV/idProduct")"

    if [ "$VENDOR" != "2e8a" ] || [ "$PRODUCT" != "106f" ]; then
        continue
    fi

    FOUND=1

    if [ -w "$DEV/power/control" ]; then
        printf '%s\n' "on" > "$DEV/power/control"
    fi

    if [ -w "$DEV/power/autosuspend_delay_ms" ]; then
        printf '%s\n' "-1" > "$DEV/power/autosuspend_delay_ms"
    fi

    CONTROL="$(cat "$DEV/power/control" 2>/dev/null || echo n/a)"
    DELAY="$(
        cat "$DEV/power/autosuspend_delay_ms" \
            2>/dev/null || echo n/a
    )"

    logger -t pincabos-dudescab-power \
        "$MARKER device=$DEV control=$CONTROL delay=$DELAY"

    echo "$DEV control=$CONTROL autosuspend_delay_ms=$DELAY"
done

if [ "$FOUND" -eq 0 ]; then
    echo "DudesCab 2e8a:106f non présent."
fi

exit 0
