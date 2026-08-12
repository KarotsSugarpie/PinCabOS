#!/usr/bin/env bash

set -u
IFS=$'\n\t'

export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-/home/pinball/.Xauthority}"

LAST_STATUS=''

log_status() {
    local status="$1"
    local message="$2"

    if [[ "$LAST_STATUS" != "$status" ]]; then
        printf '%s %s\n' \
            "$(date --iso-8601=seconds)" \
            "$message"

        LAST_STATUS="$status"
    fi
}

find_b2s_window() {
    local window_id
    local desktop
    local x
    local y
    local width
    local height
    local class
    local title

    while read -r \
        window_id \
        desktop \
        x \
        y \
        width \
        height \
        class \
        title
    do
        if [[ "$title" == *"Visual Pinball Backglass"* ]]; then
            printf '%s\n' "$window_id"
            return 0
        fi
    done < <(wmctrl -lxG 2>/dev/null)

    return 1
}

detect_vpx_mode() {
    local pid
    local environment
    local found_vpx=0

    while read -r pid; do
        [[ -n "$pid" ]] || continue
        [[ -r "/proc/${pid}/environ" ]] || continue

        found_vpx=1

        environment="$(
            tr '\0' '\n' <"/proc/${pid}/environ" 2>/dev/null ||
            true
        )"

        if grep -qx \
            'PINCABOS_PUP_ENABLED=1' \
            <<<"$environment"
        then
            printf '%s\n' 'pup'
            return 0
        fi

        if grep -qx \
            'PINCABOS_GAME_CHOICE=pup' \
            <<<"$environment"
        then
            printf '%s\n' 'pup'
            return 0
        fi

        if grep -qx \
            'PINCABOS_PUP_ENABLED=0' \
            <<<"$environment"
        then
            printf '%s\n' 'original'
            return 0
        fi

        if grep -qx \
            'PINCABOS_GAME_CHOICE=original' \
            <<<"$environment"
        then
            printf '%s\n' 'original'
            return 0
        fi
    done < <(
        pgrep \
            -u pinball \
            -f 'VPinballX_BGFX.*-play' \
            2>/dev/null ||
        true
    )

    if (( found_vpx == 1 )); then
        printf '%s\n' 'unknown'
    else
        printf '%s\n' 'stopped'
    fi
}

raise_b2s() {
    local window_id="$1"

    wmctrl \
        -i \
        -r "$window_id" \
        -b remove,hidden \
        >/dev/null 2>&1 ||
        true

    wmctrl \
        -i \
        -r "$window_id" \
        -b remove,below \
        >/dev/null 2>&1 ||
        true

    wmctrl \
        -i \
        -r "$window_id" \
        -b add,above \
        >/dev/null 2>&1 ||
        true

    if command -v xdotool >/dev/null 2>&1; then
        xdotool \
            windowmap "$window_id" \
            >/dev/null 2>&1 ||
            true

        xdotool \
            windowraise "$window_id" \
            >/dev/null 2>&1 ||
            true
    fi
}

normalize_b2s() {
    local window_id="$1"

    wmctrl \
        -i \
        -r "$window_id" \
        -b remove,above \
        >/dev/null 2>&1 ||
        true
}

printf '%s\n' \
    "$(date --iso-8601=seconds) B2S Layer Guard démarré."

while true; do
    MODE="$(detect_vpx_mode)"
    B2S_WINDOW="$(find_b2s_window || true)"

    if [[ -n "$B2S_WINDOW" ]]; then
        case "$MODE" in
            original)
                raise_b2s "$B2S_WINDOW"

                log_status \
                    "original:${B2S_WINDOW}" \
                    "ORIGINAL [√] B2S placé au-dessus : ${B2S_WINDOW}"
                ;;

            pup)
                normalize_b2s "$B2S_WINDOW"

                log_status \
                    "pup:${B2S_WINDOW}" \
                    "PUP [√] État ABOVE retiré du B2S : ${B2S_WINDOW}"
                ;;

            unknown)
                log_status \
                    "unknown:${B2S_WINDOW}" \
                    "INFO [=] VPX actif sans mode confirmé; aucune action."
                ;;

            stopped)
                normalize_b2s "$B2S_WINDOW"

                log_status \
                    "stopped:${B2S_WINDOW}" \
                    "INFO [=] VPX arrêté; état ABOVE retiré."
                ;;
        esac
    else
        log_status \
            "no-window:${MODE}" \
            "INFO [=] Aucune fenêtre B2S active."
    fi

    sleep 1
done
