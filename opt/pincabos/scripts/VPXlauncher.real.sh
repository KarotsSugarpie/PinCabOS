#!/usr/bin/env bash
set -Eeuo pipefail

# PINCABOS_DMD_MODE_ROUTING_V8_PUP_SCOREVIEW_SPLIT

FULLDMD_POLICY="/opt/pincabos/bin/pincabos-native-fulldmd-policy.sh"
B2S_POLICY="/opt/pincabos/bin/pincabos-native-b2s-scoreview-prelaunch.sh"
PUP_FONTS="/opt/pincabos/bin/pincabos-pup-fonts-install.sh"
SCOREVIEW="/opt/pincabos/bin/pincabos-hybrid-scoreview-enable-prelaunch.py"

SPLIT_HELPER="/opt/pincabos/bin/pincabos-pup-scoreview-split.py"

RAW_MODE_POLICY="/opt/pincabos/bin/pincabos-score-mode-policy.py"

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

        # Le placement (y compris le mode split) est fait UNE fois par le
        # placeur one-shot pincabos-place-front-windows, qui herite des
        # variables PINCABOS_PUP_SPLIT_* / PINCABOS_SCOREVIEW_* exportees
        # ci-dessus. L'ancien layer-watch refaisait la meme pose 5 fois par
        # seconde pendant toute la partie.

        if [[ "${PINCABOS_DMD_PRELAUNCH_ONLY:-0}" == "1" ]]; then
            exit 0
        fi

        if [[ "$PINCABOS_PUP_SPLIT_ACTIVE" == "1" ]]; then
            # PINCABOS_PUP_SPLIT_NOROOT_V2
            # Le split (DMD reel de VPX incruste dans la video du pack sur le
            # FullDMD) remplacait le screens.pup du pack par un montage en
            # namespace — qui exige root, alors que la chaine tourne en
            # pinball : il n'a jamais fonctionne. Meme resultat sans root :
            # sauvegarde du screens.pup, copie du fichier prepare par le
            # helper, partie, restauration. Un reste (partie interrompue)
            # est remis en place par le helper au lancement suivant.
            SPLIT_BACKUP="${PINCABOS_PUP_SPLIT_TARGET}.pincabos-split-avant"

            cleanup_split(){
                if [[ -f "$SPLIT_BACKUP" ]]; then
                    mv -f -- "$SPLIT_BACKUP" "$PINCABOS_PUP_SPLIT_TARGET" 2>/dev/null || true
                fi
                if [[ -n "${PINCABOS_PUP_SPLIT_RUNTIME:-}" ]]; then
                    rm -rf -- "$PINCABOS_PUP_SPLIT_RUNTIME" 2>/dev/null || true
                fi
            }

            if cp -p -- "$PINCABOS_PUP_SPLIT_TARGET" "$SPLIT_BACKUP" \
               && cp -- "$PINCABOS_PUP_SPLIT_TEMP" "$PINCABOS_PUP_SPLIT_TARGET"; then
                trap cleanup_split EXIT INT TERM
                echo "PINCABOS [PUP SPLIT] screens.pup du pack remplace le temps de la partie (sauvegarde : ${SPLIT_BACKUP##*/})" >&2
            else
                echo "PINCABOS [PUP SPLIT] NOGO : impossible de remplacer le screens.pup du pack — lancement sans split" >&2
                rm -f -- "$SPLIT_BACKUP" 2>/dev/null || true
                export PINCABOS_PUP_SPLIT_ACTIVE=0
            fi

            set +e
            run_with_front_windows "$@"
            RC=$?
            set -e

            cleanup_split
            trap - EXIT INT TERM
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
