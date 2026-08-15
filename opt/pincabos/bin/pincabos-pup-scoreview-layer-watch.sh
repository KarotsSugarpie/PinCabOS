#!/usr/bin/env bash
set -Eeuo pipefail

# PINCABOS_PUP_SCOREVIEW_LAYER_WATCH_V5_SPLIT

PARENT="${1:-0}"
TABLE="${2:-unknown}"

DISPLAY="${DISPLAY:-:0}"
XAUTHORITY="${XAUTHORITY:-/home/pinball/.Xauthority}"

VPX_USER="${PINCABOS_VPX_USER:-pinball}"
VPX_UID="$(id -u "$VPX_USER")"
VPX_HOME="$(getent passwd "$VPX_USER" | cut -d: -f6)"

[[ -n "$VPX_HOME" ]] || VPX_HOME="/home/pinball"

FULL_X=5760
FULL_Y=0
FULL_W=1920
FULL_H=1200

SPLIT="${PINCABOS_PUP_SPLIT_ACTIVE:-0}"

REL_X="${PINCABOS_SCOREVIEW_REL_X:-0}"
REL_Y="${PINCABOS_SCOREVIEW_REL_Y:-0}"
SCORE_W="${PINCABOS_SCOREVIEW_W:-640}"
SCORE_H="${PINCABOS_SCOREVIEW_H:-160}"

if [[ "$SPLIT" == "1" ]]; then
    SCORE_X=$((FULL_X + REL_X))
    SCORE_Y=$((FULL_Y + REL_Y))
else
    SCORE_X="$FULL_X"
    SCORE_Y="$FULL_Y"
    SCORE_W="$FULL_W"
    SCORE_H="$FULL_H"
fi

RUNTIME="/run/user/${VPX_UID}/pincabos-pup-scoreview-layer"

mkdir -p "$RUNTIME" 2>/dev/null || true

LOG="/var/log/pincabos-hybrid-launcher/pup-scoreview-layer.log"

if [[ ! -w "$(dirname "$LOG")" ]]; then
    LOG="$RUNTIME/pup-scoreview-layer.log"
fi

log(){
    printf '%s %s\n' \
        "$(date -Is)" \
        "$*" \
        >> "$LOG" 2>/dev/null || true
}

run_x(){

    if [[ "$(id -u)" -eq 0 ]]; then

        runuser -u "$VPX_USER" -- \
            env \
            HOME="$VPX_HOME" \
            USER="$VPX_USER" \
            LOGNAME="$VPX_USER" \
            DISPLAY="$DISPLAY" \
            XAUTHORITY="$XAUTHORITY" \
            XDG_RUNTIME_DIR="/run/user/${VPX_UID}" \
            "$@"

    else

        env \
            DISPLAY="$DISPLAY" \
            XAUTHORITY="$XAUTHORITY" \
            XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/${VPX_UID}}" \
            "$@"

    fi
}

find_score(){

    run_x wmctrl -lx 2>/dev/null |
    awk '
        BEGIN { IGNORECASE=1 }
        /Visual Pinball Score View/ {
            print $1
            exit
        }
    '
}

find_topper(){

    run_x wmctrl -lx 2>/dev/null |
    awk '
        BEGIN { IGNORECASE=1 }
        /Visual Pinball Topper/ {
            print $1
            exit
        }
    '
}

vpx_active(){

    pgrep \
        -u "$VPX_USER" \
        -f '[V]PinballX' \
        >/dev/null 2>&1
}

apply_topper(){

    local id="$1"

    run_x wmctrl \
        -i -r "$id" \
        -e "0,${FULL_X},${FULL_Y},${FULL_W},${FULL_H}" \
        >/dev/null 2>&1 || true

    run_x wmctrl \
        -i -r "$id" \
        -b remove,above \
        >/dev/null 2>&1 || true

    run_x wmctrl \
        -i -r "$id" \
        -b add,skip_taskbar \
        >/dev/null 2>&1 || true

    run_x wmctrl \
        -i -r "$id" \
        -b add,skip_pager \
        >/dev/null 2>&1 || true
}

apply_score(){

    local id="$1"

    run_x wmctrl \
        -i -r "$id" \
        -e "0,${SCORE_X},${SCORE_Y},${SCORE_W},${SCORE_H}" \
        >/dev/null 2>&1 || true

    run_x wmctrl \
        -i -r "$id" \
        -b add,above \
        >/dev/null 2>&1 || true

    run_x wmctrl \
        -i -r "$id" \
        -b add,skip_taskbar \
        >/dev/null 2>&1 || true

    run_x wmctrl \
        -i -r "$id" \
        -b add,skip_pager \
        >/dev/null 2>&1 || true

    if command -v xdotool >/dev/null 2>&1; then

        run_x xdotool \
            windowraise "$id" \
            >/dev/null 2>&1 || true
    fi
}

log \
"START table=$TABLE parent=$PARENT split=$SPLIT score=${SCORE_W}x${SCORE_H}+${SCORE_X}+${SCORE_Y}"

SCORE_SEEN=0
TOPPER_SEEN=0

while true; do

    PARENT_ALIVE=0

    if [[ "$PARENT" =~ ^[0-9]+$ ]] \
       && kill -0 "$PARENT" 2>/dev/null; then

        PARENT_ALIVE=1
    fi

    if [[ "$PARENT_ALIVE" != "1" ]] \
       && ! vpx_active; then

        break
    fi

    if [[ "$SPLIT" == "1" ]]; then

        TOPPER="$(find_topper || true)"

        if [[ -n "$TOPPER" ]]; then

            apply_topper "$TOPPER"

            if [[ "$TOPPER_SEEN" != "1" ]]; then

                log \
"TOPPER_FOUND id=$TOPPER geometry=${FULL_W}x${FULL_H}+${FULL_X}+${FULL_Y}"

                TOPPER_SEEN=1
            fi
        fi
    fi

    SCORE="$(find_score || true)"

    if [[ -n "$SCORE" ]]; then

        apply_score "$SCORE"

        if [[ "$SCORE_SEEN" != "1" ]]; then

            log \
"SCOREVIEW_FOUND id=$SCORE geometry=${SCORE_W}x${SCORE_H}+${SCORE_X}+${SCORE_Y} state=above"

            SCORE_SEEN=1
        fi
    fi

    sleep 0.20
done

log \
"STOP topper_seen=$TOPPER_SEEN scoreview_seen=$SCORE_SEEN split=$SPLIT"
