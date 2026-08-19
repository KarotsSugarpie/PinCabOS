#!/usr/bin/env bash
set -Eeuo pipefail
# PINCABOS_HYBRID_LAUNCH_CORE_V3_2_1
# PINCABOS_DIRECT_LAUNCH_MODES_V2

MODE="${1:-hybrid}"
shift || true

LAUNCHER_DIR="/opt/pincabos/launchers"
DETECTOR="${LAUNCHER_DIR}/pincabos-detect-table-modes.py"
CHOOSER="${LAUNCHER_DIR}/pincabos-hybrid-chooser.py"
ASSET="${LAUNCHER_DIR}/assets/PCOSGamesChoices.png"
MODE_HELPER="${PINCABOS_MODE_HELPER:-/usr/local/sbin/pincabos-hybrid-pup-mode}"
REAL_LAUNCHER="${PINCABOS_REAL_LAUNCHER:-/opt/pincabos/scripts/VPXlauncher.real.sh}"
PINBALL_UID="$(id -u pinball 2>/dev/null || echo 1000)"
CALLER_UID="$(id -u)"
SHARED_RUNTIME_DIR="/run/pincabos-hybrid-launcher"
USER_RUNTIME_BASE="${XDG_RUNTIME_DIR:-/run/user/${CALLER_UID}}"

# PINCABOS_HYBRID_RUNTIME_FIX_V1
# Le verrou partagé est préféré. Si ses droits sont incorrects ou si /run
# n'est pas encore préparé, le launcher utilise le runtime de l'utilisateur.
if [[ -d "$SHARED_RUNTIME_DIR" && -w "$SHARED_RUNTIME_DIR" ]]; then
    RUNTIME_DIR="$SHARED_RUNTIME_DIR"
elif [[ -d "$USER_RUNTIME_BASE" && -w "$USER_RUNTIME_BASE" ]]; then
    RUNTIME_DIR="${USER_RUNTIME_BASE}/pincabos-hybrid-launcher"
else
    RUNTIME_DIR="/tmp/pincabos-hybrid-launcher-${CALLER_UID}"
fi

SHARED_LOG_DIR="/var/log/pincabos-hybrid-launcher"
if [[ -d "$SHARED_LOG_DIR" && -w "$SHARED_LOG_DIR" ]]; then
    LOG_DIR="$SHARED_LOG_DIR"
else
    LOG_DIR="${RUNTIME_DIR}/logs"
fi

mkdir -p "$RUNTIME_DIR" "$LOG_DIR"
LOG="${LOG_DIR}/launcher.log"
LOCK="${RUNTIME_DIR}/launcher.lock"

if ! exec 8>"$LOCK"; then
    echo "NOGO [X] Impossible d'ouvrir le verrou du launcher : $LOCK" >&2
    exit 73
fi
flock -x 8

log() {
    local line="$*"
    printf '%s\n' "$line"
    printf '%s %s\n' "$(date -Is)" "$line" >> "$LOG" 2>/dev/null || true
    logger -t pincabos-hybrid-launcher -- "$line" 2>/dev/null || true
}

mode_helper() {
    if [[ "$EUID" -eq 0 ]]; then
        "$MODE_HELPER" "$@"
    else
        sudo -n "$MODE_HELPER" "$@"
    fi
}

find_table_argument() {
    local argument
    for argument in "$@"; do
        if [[ "${argument,,}" == *.vpx ]]; then
            printf '%s\n' "$argument"
            return 0
        fi
    done
    return 1
}

# PINCABOS_DIRECT_PUP_ROOT_V1
#
# Ce finder NE choisit PAS le mode de jeu.
# Il sert seulement au bouton Legacy afin de masquer un
# éventuel dossier PuP local pendant l'exécution Original.
find_local_pup_root() {
    local table="$1"
    local directory
    local child
    local name

    directory="$(dirname -- "$table")"

    [[ -d "$directory" ]] || return 1

    while IFS= read -r -d '' child; do
        [[ -d "$child" ]] || continue

        name="${child##*/}"

        case "${name,,}" in
            pupvideos|pupvideo|pinupvideo|pinupvideos)
                printf '%s\n' "$child"
                return 0
                ;;
        esac

    done < <(
        find "$directory" \
            -mindepth 1 \
            -maxdepth 1 \
            -type d \
            -print0 2>/dev/null
    )

    return 1
}


run_chooser() {
    local result="$1" default="$2" timeout="$3"
    local command=(python3 "$CHOOSER" "$ASSET" "$result" "$default" "$timeout")
    rm -f "$result"

    if [[ "$EUID" -eq 0 ]]; then
        runuser -u pinball -- env \
            HOME=/home/pinball \
            USER=pinball \
            LOGNAME=pinball \
            DISPLAY=:0 \
            XAUTHORITY=/home/pinball/.Xauthority \
            XDG_RUNTIME_DIR="/run/user/${PINBALL_UID}" \
            SDL_VIDEO_X11_WMCLASS=PinCabOSHybridChooser \
            "${command[@]}"
    else
        env \
            DISPLAY="${DISPLAY:-:0}" \
            XAUTHORITY="${XAUTHORITY:-/home/pinball/.Xauthority}" \
            XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/${PINBALL_UID}}" \
            SDL_VIDEO_X11_WMCLASS=PinCabOSHybridChooser \
            "${command[@]}"
    fi
}

read_choice() {
    python3 - "$1" "$2" <<'PY'
import json
import sys
from pathlib import Path
path = Path(sys.argv[1])
default = "pup" if sys.argv[2].startswith("pup") else "original"
try:
    choice = str(json.loads(path.read_text(encoding="utf-8")).get("choice", default)).lower()
except Exception:
    choice = default
print("pup" if choice.startswith("pup") else "original")
PY
}

if [[ "$MODE" != "hybrid" && "$MODE" != "original" && "$MODE" != "pup" ]]; then
    echo "Usage interne : $0 hybrid|original|pup [--detect-only] TABLE.vpx [arguments]" >&2
    exit 64
fi

DETECT_ONLY=0
FILTERED_ARGS=()
for argument in "$@"; do
    if [[ "$argument" == "--detect-only" ]]; then
        DETECT_ONLY=1
    else
        FILTERED_ARGS+=("$argument")
    fi
done

TABLE="$(find_table_argument "${FILTERED_ARGS[@]}")" || {
    log "NOGO [X] Aucun chemin .vpx reçu."
    exit 64
}

[[ -f "$TABLE" ]] || {
    log "NOGO [X] Table VPX absente : $TABLE"
    exit 65
}

[[ -x "$MODE_HELPER" ]] || {
    log "NOGO [X] Helper PuP absent : $MODE_HELPER"
    exit 65
}

[[ -x "$REAL_LAUNCHER" ]] || {
    log "NOGO [X] Launcher VPX réel absent : $REAL_LAUNCHER"
    exit 66
}

mode_helper recover >> "$LOG" 2>&1 || true


# =============================================================
# HYBRID = VPINFE = AUTODETECTION
# =============================================================

if [[ "$MODE" == "hybrid" ]]; then

    [[ -x "$DETECTOR" ]] || {
        log "NOGO [X] Détecteur absent : $DETECTOR"
        exit 65
    }

    eval "$(python3 "$DETECTOR" --shell "$TABLE")"

    log "TABLE=$DETECT_TABLE"
    log "MODE_DETECTE=$DETECT_MODE ORIGINAL=$DETECT_ORIGINAL PUP=$DETECT_PUP DEFAULT=$DETECT_DEFAULT"

    [[ -n "$DETECT_B2S" ]] && \
        log "B2S=$DETECT_B2S"

    [[ -n "$DETECT_PUP_ROOT" ]] && \
        log "PUP_ROOT=$DETECT_PUP_ROOT"

    if [[ "$DETECT_ONLY" == "1" ]]; then
        python3 "$DETECTOR" "$TABLE"
        exit 0
    fi

    # Le chooser n'est nécessaire que si la détection prouve
    # que les deux modes sont disponibles.
    if [[ "$DETECT_ORIGINAL" == "1" && "$DETECT_PUP" == "1" ]]; then

        [[ -x "$CHOOSER" ]] || {
            log "NOGO [X] Chooser absent : $CHOOSER"
            exit 65
        }

        [[ -f "$ASSET" ]] || {
            log "NOGO [X] Image absente : $ASSET"
            exit 65
        }
    fi

elif [[ "$DETECT_ONLY" == "1" ]]; then

    log "NOGO [X] --detect-only est reserve au mode Hybrid / VPinFE."
    exit 64
fi

SELECTED_MODE="$MODE"
FORCED_CHOICE="${PINCABOS_HYBRID_FORCE_CHOICE:-}"
FORCED_CHOICE="${FORCED_CHOICE,,}"
case "$FORCED_CHOICE" in
    puppack|pup-pack) FORCED_CHOICE="pup" ;;
esac

if [[ "$MODE" == "hybrid" ]]; then
    if [[ "$DETECT_ORIGINAL" == "1" && "$DETECT_PUP" == "1" ]]; then
        if [[ "$FORCED_CHOICE" == "original" || "$FORCED_CHOICE" == "pup" ]]; then
            SELECTED_MODE="$FORCED_CHOICE"
            log "HYBRID [TEST] Sélection forcée par script : $SELECTED_MODE (aucun chooser affiché)."
        else
            if [[ -n "$FORCED_CHOICE" ]]; then
                log "AVERTISSEMENT [!] PINCABOS_HYBRID_FORCE_CHOICE invalide : $FORCED_CHOICE"
            fi
            RESULT="${RUNTIME_DIR}/choice-$$.json"
            TIMEOUT="${PINCABOS_HYBRID_TIMEOUT:-$DETECT_TIMEOUT}"
            log "HYBRID [=] Original et PuP-Pack détectés : flippers pour sélectionner, Launch/Plunger pour confirmer."
            if run_chooser "$RESULT" "$DETECT_DEFAULT" "$TIMEOUT"; then
                SELECTED_MODE="$(read_choice "$RESULT" "$DETECT_DEFAULT")"
            else
                SELECTED_MODE="$DETECT_DEFAULT"
                log "AVERTISSEMENT [!] Le chooser a échoué; mode par défaut utilisé : $SELECTED_MODE"
            fi
            rm -f "$RESULT"
        fi
    elif [[ "$DETECT_PUP" == "1" ]]; then
        SELECTED_MODE="pup"
        log "HYBRID [√] PuP-Pack seulement : lancement direct."
    else
        SELECTED_MODE="original"
        log "HYBRID [√] Original seulement : lancement direct."
    fi
fi

case "$SELECTED_MODE" in
    original)
        # =====================================================
        # PINCAB EXPLORER : PLAY LEGACY
        # =====================================================
        #
        # Le mode est DEJA choisi par le bouton.
        # Aucune autodétection ne décide Original/PuP ici.
        #
        HIDDEN=0
        DIRECT_PUP_ROOT=""

        restore_pup() {
            if [[ "$HIDDEN" == "1" ]]; then
                mode_helper show >> "$LOG" 2>&1 || true
                HIDDEN=0
            fi
        }

        trap restore_pup EXIT INT TERM HUP

        DIRECT_PUP_ROOT="$(
            find_local_pup_root "$TABLE" || true
        )"

        if [[ -n "$DIRECT_PUP_ROOT" && -d "$DIRECT_PUP_ROOT" ]]; then

            log "LEGACY [=] PuP local masque : $DIRECT_PUP_ROOT"

            mode_helper hide \
                "$DIRECT_PUP_ROOT" \
                >> "$LOG" 2>&1

            HIDDEN=1

        else

            log "LEGACY [=] Aucun dossier PuP local a masquer."

        fi

        log "LEGACY [▶] Lancement Original direct."

        set +e

        env \
            PINCABOS_GAME_CHOICE=original \
            PINCABOS_PUP_ENABLED=0 \
            "$REAL_LAUNCHER" "${FILTERED_ARGS[@]}"

        RC=$?

        set -e

        restore_pup
        trap - EXIT INT TERM HUP

        exit "$RC"
        ;;
    pup)
        # =====================================================
        # PINCAB EXPLORER : PLAY PUPPACK
        # =====================================================
        #
        # Le mode est DEJA choisi par le bouton Play PUPPack.
        # Le détecteur n'a pas le droit de transformer ce choix
        # en NOGO.
        #
        # On restaure un éventuel PuP précédemment masqué puis
        # VPX/PuP applique la configuration réelle du pack :
        # vidéos, B2S éventuel, FullDMD, etc.
        #
        mode_helper show >> "$LOG" 2>&1 || true

        log "PUP [▶] Lancement PUPPack direct."

        exec env \
            PINCABOS_GAME_CHOICE=pup \
            PINCABOS_PUP_ENABLED=1 \
            "$REAL_LAUNCHER" "${FILTERED_ARGS[@]}"
        ;;
    *)
        log "NOGO [X] Mode final invalide : $SELECTED_MODE"
        exit 68
        ;;
esac
