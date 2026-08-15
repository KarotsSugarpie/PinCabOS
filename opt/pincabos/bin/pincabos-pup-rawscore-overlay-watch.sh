#!/usr/bin/env bash

set -Eeuo pipefail

LAUNCH_PID="${1:-0}"
TABLE="${2:-unknown}"

STARTER="/opt/pincabos/bin/pincabos-pup-rawscore-overlay-start.sh"

PIDFILE="/tmp/pincabos-pup-rawscore-overlay.pid"

FRAME="/dev/shm/pincabos-rawscore.ppm"
TEMP="${FRAME}.tmp"

STATE="/run/pincabos-b2s-dmd-tuner/state.env"
COMMAND="/run/pincabos-b2s-dmd-tuner/command.env"

LOG="/tmp/pincabos-pup-rawscore-watch.log"

OVERLAY_PID=""
VPXPID=""
CLEANED=0


exec >>"$LOG" 2>&1


cleanup()
{
    if [ "$CLEANED" -eq 1 ]; then
        return
    fi

    CLEANED=1

    trap - \
        EXIT INT TERM HUP

    set +e

    echo
    echo "PINCABOS [RAWSCORE] CLEANUP V21"


    if [ -z "$OVERLAY_PID" ] && \
       [ -f "$PIDFILE" ]
    then
        OVERLAY_PID="$(
            cat "$PIDFILE" \
            2>/dev/null || true
        )"
    fi


    if [ -n "$OVERLAY_PID" ] && \
       kill -0 "$OVERLAY_PID" \
        2>/dev/null
    then
        kill "$OVERLAY_PID" \
            2>/dev/null || true
    fi


    rm -f \
        "$PIDFILE" \
        "$FRAME" \
        "$TEMP"


    for F in \
        "$STATE" \
        "$COMMAND"
    do
        if [ -f "$F" ] && \
           grep -q "^PID=${VPXPID}$" \
            "$F" \
            2>/dev/null
        then
            rm -f "$F"
        fi
    done


    echo "GO [√] RawScore nettoyé"
}


trap cleanup \
    EXIT INT TERM HUP


echo
echo "==============================================================="
echo "PINCABOS RAWSCORE WATCH V21"
echo "Launcher PID=$LAUNCH_PID"
echo "Table=$TABLE"
echo "==============================================================="


for _ in $(seq 1 300); do

    if [ "$LAUNCH_PID" -gt 0 ] && \
       kill -0 "$LAUNCH_PID" \
        2>/dev/null
    then

        EXE="$(
            readlink \
                "/proc/$LAUNCH_PID/exe" \
                2>/dev/null || true
        )"


        if [[ "$EXE" == *VPinballX_BGFX* ]]; then
            VPXPID="$LAUNCH_PID"
            break
        fi
    fi


    while read -r P; do

        [ -z "$P" ] && continue

        if tr '\0' '\n' \
            < "/proc/$P/environ" \
            2>/dev/null |
           grep -q \
            '^PINCABOS_GAME_CHOICE=pup$'
        then
            VPXPID="$P"
            break 2
        fi

    done < <(
        pgrep -u pinball \
            -f '[V]PinballX_BGFX' \
        2>/dev/null || true
    )


    sleep 0.1
done


if [ -z "$VPXPID" ]; then
    echo "NOGO [X] VPX PuP non trouvé"
    exit 0
fi


echo "GO [√] VPX PID=$VPXPID"


"$STARTER" \
    "$VPXPID" \
    "$TABLE" \
|| true


OVERLAY_PID="$(
    cat "$PIDFILE" \
    2>/dev/null || true
)"


echo "Overlay PID=$OVERLAY_PID"


while kill -0 "$VPXPID" \
    2>/dev/null
do
    sleep 0.25
done


echo "GO [√] VPX terminé"

cleanup

exit 0
