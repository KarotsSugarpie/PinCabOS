#!/usr/bin/env bash
set -Eeuo pipefail

DISPLAY_VALUE="${DISPLAY:-:0.0}"
XAUTHORITY_VALUE="/run/lightdm/root/:0"
[[ -r "$XAUTHORITY_VALUE" ]] || XAUTHORITY_VALUE="/home/pinball/.Xauthority"
XDG_RUNTIME_VALUE="/run/user/$(id -u)"
OUT_DIR="/run/pincabos-scoreview-x11-hq"
OUT_FILE="$OUT_DIR/preview.jpg"

export DISPLAY="$DISPLAY_VALUE"
export XAUTHORITY="$XAUTHORITY_VALUE"
export XDG_RUNTIME_DIR="$XDG_RUNTIME_VALUE"

mkdir -p "$OUT_DIR"
chmod 0755 "$OUT_DIR"

while true; do
    geometry="$({ xrandr --query 2>/dev/null || true; } | awk '
        $1 == "DP-2" && $2 == "connected" {
            for (i = 3; i <= NF; i++) {
                if ($i ~ /^[0-9]+x[0-9]+\+[0-9]+\+[0-9]+/) {
                    print $i
                    exit
                }
            }
        }
    ')"

    if [[ -z "$geometry" ]]; then
        rm -f "$OUT_FILE"
        sleep 2
        continue
    fi

    read -r width height pos_x pos_y < <(
        sed -E 's/^([0-9]+)x([0-9]+)\+([0-9]+)\+([0-9]+).*$/\1 \2 \3 \4/' <<< "$geometry"
    )

    rm -f "$OUT_FILE"

    # Flux JPEG plein format, qualité élevée, 4 images/seconde.
    # -update 1 garde un seul fichier; -atomic_writing évite une lecture partielle.
    ffmpeg \
        -nostdin \
        -hide_banner \
        -loglevel error \
        -f x11grab \
        -draw_mouse 0 \
        -framerate 4 \
        -video_size "${width}x${height}" \
        -i "${DISPLAY_VALUE}+${pos_x},${pos_y}" \
        -an \
        -vf 'format=yuvj444p' \
        -q:v 2 \
        -f image2 \
        -update 1 \
        -atomic_writing 1 \
        "$OUT_FILE" || true

    sleep 1
 done
