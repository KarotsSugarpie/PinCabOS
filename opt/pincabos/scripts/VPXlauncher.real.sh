#!/usr/bin/env bash
set -Eeuo pipefail

# PINCABOS_DMD_MODE_ROUTING_V8_PUP_SCOREVIEW_SPLIT

FULLDMD_POLICY="/opt/pincabos/bin/pincabos-native-fulldmd-policy.sh"
B2S_POLICY="/opt/pincabos/bin/pincabos-native-b2s-scoreview-prelaunch.sh"
PUP_FONTS="/opt/pincabos/bin/pincabos-pup-fonts-install.sh"
SCOREVIEW="/opt/pincabos/bin/pincabos-hybrid-scoreview-enable-prelaunch.py"

SPLIT_HELPER="/opt/pincabos/bin/pincabos-pup-scoreview-split.py"
PUP_LAYER="/opt/pincabos/bin/pincabos-pup-scoreview-layer-watch.sh"

RAW_MODE_POLICY="/opt/pincabos/bin/pincabos-score-mode-policy.py"
RAW_OVERLAY_WATCH="/opt/pincabos/bin/pincabos-pup-rawscore-overlay-watch.sh"

REAL="/opt/pincabos/scripts/VPXlauncher.pincabos-original.sh"

# PINCABOS_PLACE_FRONT_WINDOWS_V1
# VPX ignore les positions demandees pour ses fenetres Backglass/Score View :
# un placeur ONE-SHOT les pose a leur ecran de role des leur apparition puis
# se termine (aucune boucle pendant le jeu) ; en fin de partie on remonte le
# rideau VPinFE et on rend le focus au playfield. Remplace les services
# place-backbox / b2s-layer-guard / scoreview-router.
PLACER="/opt/pincabos/bin/pincabos-place-front-windows"

run_with_front_windows() {
    if [[ -x "$PLACER" ]]; then
        "$PLACER" --place >/dev/null 2>&1 &
    fi
    local rc=0
    set +e
    "$REAL" "$@"
    rc=$?
    set -e
    if [[ -x "$PLACER" ]]; then
        "$PLACER" --restore >/dev/null 2>&1 || true
    fi
    return "$rc"
}

MODE="${PINCABOS_GAME_CHOICE:-original}"
MODE="${MODE,,}"

TABLE=""

for arg in "$@"; do
    if [[ "${arg,,}" == *.vpx ]]; then
        TABLE="$arg"
        break
    fi
done

case "$MODE" in

    pup|puppack|pup-pack)

        echo "PINCABOS [DMD ROUTER] MODE=PUP" >&2

        if [[ -x "$PUP_FONTS" ]]; then
            "$PUP_FONTS" "$@" || true
        fi

        if [[ -x "$FULLDMD_POLICY" ]]; then
            "$FULLDMD_POLICY" "$@" || true
        fi

        if [[ -x "$SCOREVIEW" ]]; then
            "$SCOREVIEW" "$@" || true
        fi

        PINCABOS_PUP_SPLIT_ACTIVE=0
        PINCABOS_PUP_SPLIT_REASON=""
        PINCABOS_PUP_SPLIT_PACK=""
        PINCABOS_PUP_SPLIT_TARGET=""
        PINCABOS_PUP_SPLIT_TEMP=""
        PINCABOS_PUP_SPLIT_RUNTIME=""

        PINCABOS_SCOREVIEW_REL_X=0
        PINCABOS_SCOREVIEW_REL_Y=0
        PINCABOS_SCOREVIEW_W=640
        PINCABOS_SCOREVIEW_H=160

        if [[ -n "$TABLE" && -x "$SPLIT_HELPER" ]]; then

            eval "$(
                "$SPLIT_HELPER" \
                    pup \
                    "$TABLE" \
                    --shell
            )"
        fi

        export \
            PINCABOS_PUP_SPLIT_ACTIVE \
            PINCABOS_PUP_SPLIT_REASON \
            PINCABOS_PUP_SPLIT_PACK \
            PINCABOS_PUP_SPLIT_TARGET \
            PINCABOS_PUP_SPLIT_TEMP \
            PINCABOS_PUP_SPLIT_RUNTIME \
            PINCABOS_SCOREVIEW_REL_X \
            PINCABOS_SCOREVIEW_REL_Y \
            PINCABOS_SCOREVIEW_W \
            PINCABOS_SCOREVIEW_H

        echo \
"PINCABOS [PUP SPLIT] active=$PINCABOS_PUP_SPLIT_ACTIVE reason=$PINCABOS_PUP_SPLIT_REASON" \
            >&2

        if [[ -x "$PUP_LAYER" ]]; then

    if [[ -x "$RAW_OVERLAY_WATCH" ]]; then
      "$RAW_OVERLAY_WATCH" "$$" "${TABLE:-unknown}" >/dev/null 2>&1 &
    fi

            "$PUP_LAYER" \
                "$$" \
                "${TABLE:-unknown}" \
                >/dev/null 2>&1 &
        fi

        if [[ "${PINCABOS_DMD_PRELAUNCH_ONLY:-0}" == "1" ]]; then
            exit 0
        fi

        if [[ "$PINCABOS_PUP_SPLIT_ACTIVE" == "1" ]]; then

            if [[ "$(id -u)" -ne 0 ]]; then
                echo \
"PINCABOS [PUP SPLIT] NOGO : namespace mount nécessite root" \
                    >&2

                run_with_front_windows "$@"
                exit "$?"
            fi

            cleanup_split(){

                if [[ -n "${PINCABOS_PUP_SPLIT_RUNTIME:-}" ]]; then
                    rm -rf -- \
                        "$PINCABOS_PUP_SPLIT_RUNTIME" \
                        2>/dev/null || true
                fi
            }

            trap cleanup_split EXIT INT TERM

            if [[ -x "$PLACER" ]]; then
                "$PLACER" --place >/dev/null 2>&1 &
            fi

            set +e

            unshare \
                --mount \
                --propagation private \
                bash -c '
                    set -Eeuo pipefail

                    TEMP="$1"
                    TARGET="$2"

                    shift 2

                    mount \
                        --bind \
                        "$TEMP" \
                        "$TARGET"

                    exec "$@"
                ' \
                bash \
                "$PINCABOS_PUP_SPLIT_TEMP" \
                "$PINCABOS_PUP_SPLIT_TARGET" \
                "$REAL" \
                "$@"

            RC=$?

            set -e

            if [[ -x "$PLACER" ]]; then
                "$PLACER" --restore >/dev/null 2>&1 || true
            fi

            exit "$RC"
        fi

        run_with_front_windows "$@"
        exit "$?"
        ;;

    *)

        echo "PINCABOS [DMD ROUTER] MODE=LEGACY" >&2

        if [[ -n "$TABLE" && -x "$SPLIT_HELPER" ]]; then

            "$SPLIT_HELPER" \
                legacy \
                "$TABLE" \
                >/dev/null 2>&1 || true
        fi

        if [[ -x "$PUP_FONTS" ]]; then
            "$PUP_FONTS" "$@" || true
        fi

        if [[ -x "$FULLDMD_POLICY" ]]; then
            "$FULLDMD_POLICY" "$@" || true
        fi

        if [[ -x "$B2S_POLICY" ]]; then
            "$B2S_POLICY" "$@" || true
        fi

        if [[ "${PINCABOS_DMD_PRELAUNCH_ONLY:-0}" == "1" ]]; then
            exit 0
        fi

        run_with_front_windows "$@"
        exit "$?"
        ;;
esac
