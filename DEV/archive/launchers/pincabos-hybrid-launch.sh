#!/usr/bin/env bash
set -Eeuo pipefail
# PINCABOS_HYBRID_SAME_TABLE_PUP_TOGGLE_V12

REAL_LAUNCHER="/opt/pincabos/scripts/VPXlauncher.real.sh"
CHOOSER="/opt/pincabos/bin/pincabos-hybrid-chooser.py"
CFG_ROOT="/opt/pincabos/config/hybrid-launcher"
ASSET="/opt/pincabos/media/assets/PCOSGamesChoices.png"
RUNTIME_DIR="/run/pincabos-hybrid-launcher"
RUNTIME_JSON="${RUNTIME_DIR}/choice.json"
LOCK_FILE="/run/lock/pincabos-hybrid-launch.lock"
RECOVER="/usr/local/sbin/pincabos-hybrid-pup-recover"
LOG="/root/pincabos-hybrid-launcher-last.log"
DISABLED_SUFFIX=".__pincabos_hybrid_disabled__"

mkdir -p "$RUNTIME_DIR"
chmod 1777 "$RUNTIME_DIR" 2>/dev/null || true

exec 9>"$LOCK_FILE"
flock 9

"$RECOVER" >> "$LOG" 2>&1 || true

{
    echo
    echo "==============================================================="
    echo "$(date -Is)"
    printf 'ARGS='
    printf ' %q' "$@"
    echo
} >> "$LOG" 2>/dev/null || true

if [[ ! -x "$REAL_LAUNCHER" ]]; then
    echo "NOGO [X] Launcher réel absent : $REAL_LAUNCHER" >> "$LOG"
    exit 127
fi

if [[ "${PINCABOS_HYBRID_BYPASS:-0}" == "1" ]]; then
    exec "$REAL_LAUNCHER" "$@"
fi

ARGS=("$@")
REQUESTED_TABLE=""

for arg in "${ARGS[@]}"; do
    if [[ "$arg" == *.vpx ]]; then
        REQUESTED_TABLE="$arg"
        break
    fi
done

if [[ -z "$REQUESTED_TABLE" ]]; then
    exec env PINCABOS_HYBRID_BYPASS=1 "$REAL_LAUNCHER" "$@"
fi

TABLE_DIR="$(dirname "$REQUESTED_TABLE")"
CFG_FILE="${TABLE_DIR}/PinCabOS-Hybrid.json"

if [[ ! -f "$CFG_FILE" ]]; then
    ALT_CFG="${CFG_ROOT}/$(basename "$TABLE_DIR").json"
    [[ -f "$ALT_CFG" ]] && CFG_FILE="$ALT_CFG"
fi

if [[ ! -f "$CFG_FILE" ]]; then
    exec env PINCABOS_HYBRID_BYPASS=1 "$REAL_LAUNCHER" "$@"
fi

mapfile -t CFG < <(
python3 - "$CFG_FILE" "$TABLE_DIR" <<'PY'
import json
import sys
from pathlib import Path

cfg_path = Path(sys.argv[1])
table_dir = Path(sys.argv[2])
data = json.loads(cfg_path.read_text(encoding="utf-8"))

def resolve(value):
    value = str(value or "").strip()
    if not value:
        return ""
    path = Path(value)
    if not path.is_absolute():
        path = table_dir / path
    return str(path)

print("1" if data.get("enabled", True) else "0")
print(str(data.get("default", "original")).strip().lower())
print(int(data.get("timeout", 20)))
print(resolve(data.get("pup_folder")))

choices = data.get("choices") or {}

for name in ("original", "pup"):
    node = choices.get(name) or {}
    print(resolve(node.get("table")))
    print(str(node.get("mode", "")).strip().lower())
    print(json.dumps(node.get("env") or {}, ensure_ascii=False, separators=(",", ":")))
PY
)

ENABLED="${CFG[0]:-0}"
DEFAULT_CHOICE="${CFG[1]:-original}"
TIMEOUT="${CFG[2]:-20}"
PUP_FOLDER="${CFG[3]:-}"

ORIGINAL_TABLE="${CFG[4]:-$REQUESTED_TABLE}"
ORIGINAL_MODE="${CFG[5]:-disable_pup}"
ORIGINAL_ENV_JSON="${CFG[6]:-\{\}}"

PUP_TABLE="${CFG[7]:-$REQUESTED_TABLE}"
PUP_MODE="${CFG[8]:-enable_pup}"
PUP_ENV_JSON="${CFG[9]:-\{\}}"

if [[ "$ENABLED" != "1" ]]; then
    exec env PINCABOS_HYBRID_BYPASS=1 "$REAL_LAUNCHER" "$@"
fi

[[ -n "$ORIGINAL_TABLE" ]] || ORIGINAL_TABLE="$REQUESTED_TABLE"
[[ -n "$PUP_TABLE" ]] || PUP_TABLE="$REQUESTED_TABLE"

if [[ -z "$PUP_FOLDER" ]]; then
    echo "NOGO [X] pup_folder absent dans $CFG_FILE" >> "$LOG"
    exit 65
fi

PUP_HIDDEN="${PUP_FOLDER}${DISABLED_SUFFIX}"

rm -f "$RUNTIME_JSON"

runuser -u pinball -- \
    env \
    HOME=/home/pinball \
    USER=pinball \
    LOGNAME=pinball \
    DISPLAY=:0 \
    XAUTHORITY=/home/pinball/.Xauthority \
    XDG_RUNTIME_DIR=/run/user/1000 \
    SDL_VIDEO_X11_WMCLASS=PinCabOSHybridChooser \
    python3 "$CHOOSER" "$ASSET" "$RUNTIME_JSON" "$DEFAULT_CHOICE" "$TIMEOUT"

CHOICE="$(
python3 - "$RUNTIME_JSON" "$DEFAULT_CHOICE" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
default = sys.argv[2]

try:
    value = json.loads(path.read_text(encoding="utf-8")).get("choice", default)
except Exception:
    value = default

value = str(value).strip().lower()
print("pup" if value.startswith("pup") else "original")
PY
)"

if [[ "$CHOICE" == "pup" ]]; then
    TARGET_TABLE="$PUP_TABLE"
    MODE="$PUP_MODE"
    ENV_JSON="$PUP_ENV_JSON"
else
    TARGET_TABLE="$ORIGINAL_TABLE"
    MODE="$ORIGINAL_MODE"
    ENV_JSON="$ORIGINAL_ENV_JSON"
fi

mapfile -t FINAL_ARGS < <(
python3 - "$REQUESTED_TABLE" "$TARGET_TABLE" "${ARGS[@]}" <<'PY'
import sys

requested = sys.argv[1]
target = sys.argv[2]
args = sys.argv[3:]
replaced = False

for arg in args:
    if not replaced and arg == requested:
        print(target)
        replaced = True
    else:
        print(arg)

if not replaced:
    print(target)
PY
)

mapfile -t ENV_EXPORTS < <(
python3 - "$ENV_JSON" <<'PY'
import json
import sys

for key, value in json.loads(sys.argv[1] or "{}").items():
    key = str(key).strip()
    if not key or "=" in key or "\x00" in key:
        continue
    print(f"{key}={value}")
PY
)

restore_pack() {
    if [[ -d "$PUP_HIDDEN" && ! -e "$PUP_FOLDER" ]]; then
        mv -- "$PUP_HIDDEN" "$PUP_FOLDER"
        chown -R pinball:pinball "$PUP_FOLDER" 2>/dev/null || true
        echo "RESTORE [√] PuP-Pack restauré : $PUP_FOLDER" >> "$LOG"
    fi
}

hide_pack() {
    restore_pack

    if [[ ! -d "$PUP_FOLDER" ]]; then
        echo "NOGO [X] PuP-Pack absent : $PUP_FOLDER" >> "$LOG"
        return 1
    fi

    if [[ -e "$PUP_HIDDEN" ]]; then
        echo "NOGO [X] Cible temporaire déjà présente : $PUP_HIDDEN" >> "$LOG"
        return 1
    fi

    mv -- "$PUP_FOLDER" "$PUP_HIDDEN"
    echo "ORIGINAL [√] PuP-Pack masqué temporairement : $PUP_HIDDEN" >> "$LOG"
}

{
    echo "CFG_FILE=$CFG_FILE"
    echo "CHOICE=$CHOICE"
    echo "MODE=$MODE"
    echo "PUP_FOLDER=$PUP_FOLDER"
    echo "REQUESTED_TABLE=$REQUESTED_TABLE"
    echo "TARGET_TABLE=$TARGET_TABLE"
    printf 'FINAL_ARGS='
    printf ' %q' "${FINAL_ARGS[@]}"
    echo
} >> "$LOG" 2>/dev/null || true

case "$MODE" in
    disable_pup|original)
        hide_pack
        trap restore_pack EXIT INT TERM HUP

        set +e
        env \
            PINCABOS_HYBRID_BYPASS=1 \
            PINCABOS_GAME_CHOICE=original \
            PINCABOS_PUP_ENABLED=0 \
            "${ENV_EXPORTS[@]}" \
            "$REAL_LAUNCHER" "${FINAL_ARGS[@]}"
        rc=$?
        set -e

        restore_pack
        trap - EXIT INT TERM HUP
        exit "$rc"
        ;;

    enable_pup|pup)
        restore_pack
        exec env \
            PINCABOS_HYBRID_BYPASS=1 \
            PINCABOS_GAME_CHOICE=pup \
            PINCABOS_PUP_ENABLED=1 \
            "${ENV_EXPORTS[@]}" \
            "$REAL_LAUNCHER" "${FINAL_ARGS[@]}"
        ;;

    *)
        echo "NOGO [X] Mode hybride inconnu : $MODE" >> "$LOG"
        exit 64
        ;;
esac
