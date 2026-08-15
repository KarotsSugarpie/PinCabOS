#!/usr/bin/env bash

set -Eeuo pipefail

OVERLAY="/opt/pincabos/bin/pincabos-pup-rawscore-overlay.py"

LOG="/tmp/pincabos-pup-rawscore-overlay.log"
PIDFILE="/tmp/pincabos-pup-rawscore-overlay.pid"

VPXPID="${1:-}"
TABLE="${2:-unknown}"


if [ -z "$VPXPID" ] || \
   ! kill -0 "$VPXPID" \
        2>/dev/null
then
    VPXPID="$(
        pgrep -u pinball \
            -f '[V]PinballX_BGFX' |
        head -n1 || true
    )"
fi


if [ -z "$VPXPID" ]; then
    echo "NOGO [X] Aucun VPX actif"
    exit 1
fi


if [ -f "$PIDFILE" ]; then

    OLD="$(
        cat "$PIDFILE" \
        2>/dev/null || true
    )"

    if [ -n "$OLD" ] && \
       kill -0 "$OLD" \
        2>/dev/null
    then
        kill "$OLD" \
            2>/dev/null || true

        sleep 0.2
    fi
fi


rm -f \
    "$PIDFILE" \
    "$LOG"


if [ "$(id -u)" -eq 0 ]; then

    PID="$(
        runuser -u pinball -- \
        sh -c '
            nohup env \
                HOME=/home/pinball \
                DISPLAY=:0 \
                XAUTHORITY=/home/pinball/.Xauthority \
                XDG_RUNTIME_DIR=/run/user/1000 \
                python3 "$1" "$2" "$3" \
                >"$4" 2>&1 &
            echo $!
        ' _ \
        "$OVERLAY" \
        "$VPXPID" \
        "$TABLE" \
        "$LOG"
    )"

else

    nohup env \
        HOME=/home/pinball \
        DISPLAY="${DISPLAY:-:0}" \
        XAUTHORITY="${XAUTHORITY:-/home/pinball/.Xauthority}" \
        XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/1000}" \
        python3 \
        "$OVERLAY" \
        "$VPXPID" \
        "$TABLE" \
        >"$LOG" 2>&1 &

    PID="$!"
fi


echo "$PID" > "$PIDFILE"

sleep 0.5


if kill -0 "$PID" \
    2>/dev/null
then
    echo "GO [√] RawScore actif"
    echo "OVERLAY_PID=$PID"
    echo "VPX_PID=$VPXPID"
    echo "TABLE=$TABLE"
else
    echo "NOGO [X] RawScore arrêté"

    cat "$LOG" \
        2>/dev/null || true

    exit 1
fi
