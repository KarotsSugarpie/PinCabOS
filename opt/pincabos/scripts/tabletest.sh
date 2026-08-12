#!/usr/bin/env bash
# PinCabOS - Test individuel d'une table VPX
# Installez dans: /opt/pincabos/scripts/tabletest.sh
# Usage: sudo -u pinball /opt/pincabos/scripts/tabletest.sh "/home/pinball/Tables/Nom table/Nom table.vpx"

set -Eeuo pipefail
IFS=$'\n\t'
umask 022

SCRIPT_VERSION="1.1.5"
DEFAULT_TABLES_ROOT="/home/pinball/Tables"
DEFAULT_LAUNCHER="/opt/pincabos/bin/vpx.sh"
DEFAULT_LOWLATENCY_LAUNCHER="/opt/pincabos/bin/vpx-lowlatency.sh"

TABLES_ROOT="${PINCAB_TABLES_ROOT:-$DEFAULT_TABLES_ROOT}"
LAUNCHER="${PINCAB_VPX_LAUNCHER:-$DEFAULT_LAUNCHER}"
LOWLATENCY_LAUNCHER="${PINCAB_VPX_LOWLATENCY_LAUNCHER:-$DEFAULT_LOWLATENCY_LAUNCHER}"
VPINFE_INI="${PINCAB_VPINFE_INI:-}"
RUN_SECONDS="${PINCAB_TEST_RUN_SECONDS:-120}"
STARTUP_TIMEOUT="${PINCAB_TEST_STARTUP_TIMEOUT:-60}"
EXIT_TIMEOUT="${PINCAB_TEST_EXIT_TIMEOUT:-15}"
DISPLAY_VALUE="${DISPLAY:-:0}"
XAUTHORITY_VALUE="${XAUTHORITY:-}"
DISPLAY_ALIASES_FILE="${PINCAB_DISPLAY_ALIASES_FILE:-/opt/pincabos/config/display-aliases.env}"
CAPTURE_MAX_WIDTH="${PINCAB_TEST_CAPTURE_MAX_WIDTH:-960}"
CAPTURE_JPEG_QUALITY="${PINCAB_TEST_CAPTURE_JPEG_QUALITY:-6}"
CAPTURE_ALL_SCREENS="${PINCAB_TEST_CAPTURE_ALL_SCREENS:-0}"
[[ "$CAPTURE_MAX_WIDTH" =~ ^[0-9]+$ ]] || CAPTURE_MAX_WIDTH=960
[[ "$CAPTURE_JPEG_QUALITY" =~ ^[0-9]+$ ]] || CAPTURE_JPEG_QUALITY=6
(( CAPTURE_MAX_WIDTH >= 320 )) || CAPTURE_MAX_WIDTH=960
(( CAPTURE_JPEG_QUALITY >= 2 && CAPTURE_JPEG_QUALITY <= 31 )) || CAPTURE_JPEG_QUALITY=6

# La topologie PinCabOS générée depuis screens.json/EDID est la source de vérité.
# Les variables PINCAB_* gardent la priorité pour permettre un test ciblé.
if [[ -r "$DISPLAY_ALIASES_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$DISPLAY_ALIASES_FILE"
fi

PLAYFIELD_OUTPUT="${PINCAB_PLAYFIELD_OUTPUT:-${PINCABOS_PLAYFIELD_OUTPUT:-HDMI-0}}"
BACKGLASS_OUTPUT="${PINCAB_BACKGLASS_OUTPUT:-${PINCABOS_BACKGLASS_OUTPUT:-DP-1}}"
FULLDMD_OUTPUT="${PINCAB_FULLDMD_OUTPUT:-${PINCABOS_FULLDMD_OUTPUT:-DP-3}}"
PLAYFIELD_GEOMETRY="${PINCAB_PLAYFIELD_GEOMETRY:-${PINCABOS_PLAYFIELD_GEOMETRY:-}}"
BACKGLASS_GEOMETRY="${PINCAB_BACKGLASS_GEOMETRY:-${PINCABOS_BACKGLASS_GEOMETRY:-}}"
FULLDMD_GEOMETRY="${PINCAB_FULLDMD_GEOMETRY:-${PINCABOS_FULLDMD_GEOMETRY:-}}"
if [[ -n "${PINCAB_TEST_USER:-}" ]]; then
  TEST_USER="$PINCAB_TEST_USER"
elif [[ -n "${SUDO_USER:-}" && "$SUDO_USER" != root ]]; then
  TEST_USER="$SUDO_USER"
elif [[ "$(id -u)" -eq 0 ]] && id pinball >/dev/null 2>&1; then
  TEST_USER="pinball"
else
  TEST_USER="$(id -un)"
fi
FORCE_LAUNCHER="vpinfe"
MODE_REQUEST="auto"
KEEP_EXISTING_VBS=1
VPINFE_MANAGED_EXTERNALLY="${PINCAB_VPINFE_MANAGED_EXTERNALLY:-0}"
VPINFE_SERVICE_REQUESTED="${PINCAB_VPINFE_SERVICE:-}"
VPINFE_SERVICE_RESOLVED=""
VPINFE_WAS_ACTIVE=0
VPINFE_RUNTIME_MASK_APPLIED=0
VPINFE_RESTORE_DONE=0

TABLE=""
TABLE_DIR=""
TABLE_FILE=""
TABLE_STEM=""
LOG_DIR=""
REPORT=""
ANALYSIS=""
RUNTIME_ROOT=""
SNAP_ROOT=""
LOCK_FILE=""
VPX_BIN=""
VPINFE_VPXBINPATH=""
VPINFE_VPXLAUNCHENV=""
VPINFE_GLOBAL_INI=""
VPINFE_TABLEINI_ENABLED="false"
VPINFE_TABLEINI_MASK=""
VPINFE_VPXINIPATH=""
TABLE_INFO_FILE=""
TABLE_ALT_LAUNCHER=""
TABLE_INFO_ROM=""
SELECTED_LAUNCHER=""
LAUNCH_SOURCE=""
VPX_LAUNCH_ENV=()
VPX_LAUNCH_ARGS=()
VPX_LAUNCH_CMD=()
PINMAME_USED=0
HYBRID_DETECTOR="/opt/pincabos/launchers/pincabos-detect-table-modes.py"
HYBRID_RUNTIME_DIR="/run/pincabos-hybrid-launchers"
HYBRID_LOG="/var/log/pincabos-hybrid-launchers.log"
NATIVE_B2S_PRELAUNCH="/opt/pincabos/bin/pincabos-native-b2s-scoreview-prelaunch.sh"
ORIGINAL_REAL_LAUNCHER="${PINCABOS_REAL_LAUNCHER:-}"
DETECTOR_ORIGINAL=""
DETECTOR_PUP=""
DETECTOR_B2S=""
DETECTOR_PUP_ROOT=""
DETECTOR_ROM_FILES=()
DETECTOR_PUP_PACKS=()

CURRENT_PID=""
CURRENT_PGID=""
DISABLED_PUP_DIRS=()
TEMP_FILES=()
WARNINGS=()
FAILURES=()
PASSES=()
ROM_NAMES=()
PUP_DIRS=()

usage() {
  cat <<USAGE
PinCabOS tabletest.sh v${SCRIPT_VERSION}

Usage:
  tabletest.sh [options] "/chemin/table.vpx"
  tabletest.sh [options] "Nom ou partie du nom"

Options:
  --mode auto|native|rom|pup     Modes à tester (défaut: auto)
  --launcher vpinfe|auto|normal|lowlatency
  --seconds N                    Durée de chaque passage (défaut: ${RUN_SECONDS}s)
  --startup-timeout N            Attente maximale de démarrage
  --tables-root CHEMIN           Racine des tables
  --help

Chaque mode disponible est exécuté deux fois. Les résultats sont placés dans:
  Tables/<dossier de la table>/logs/
USAGE
}

log_console() { printf '%s\n' "$*"; }
now_iso() { date --iso-8601=seconds; }
add_warning() { WARNINGS+=("$*"); }
add_failure() { FAILURES+=("$*"); }
add_pass() { PASSES+=("$*"); }

cleanup_process() {
  local own_pgid
  own_pgid="$(ps -o pgid= -p $$ 2>/dev/null | tr -d ' ' || true)"
  if [[ -n "${CURRENT_PGID:-}" && "$CURRENT_PGID" != "$own_pgid" && "$CURRENT_PGID" =~ ^[0-9]+$ && "$CURRENT_PGID" -gt 1 ]]; then
    kill -TERM -- "-${CURRENT_PGID}" 2>/dev/null || true
    sleep 2
    kill -KILL -- "-${CURRENT_PGID}" 2>/dev/null || true
  elif [[ -n "${CURRENT_PID:-}" && "$CURRENT_PID" =~ ^[0-9]+$ ]] && kill -0 "$CURRENT_PID" 2>/dev/null; then
    kill -TERM "$CURRENT_PID" 2>/dev/null || true
    sleep 2
    kill -KILL "$CURRENT_PID" 2>/dev/null || true
  fi
  CURRENT_PID=""
  CURRENT_PGID=""
}

restore_pup_dirs() {
  local disabled original
  for disabled in "${DISABLED_PUP_DIRS[@]:-}"; do
    [[ -n "$disabled" ]] || continue
    original="${disabled%.pincabos-tabletest-disabled}"
    if [[ -e "$disabled" && ! -e "$original" ]]; then
      mv -- "$disabled" "$original" 2>/dev/null || true
    fi
  done
  DISABLED_PUP_DIRS=()
}

vpinfe_pids() {
  pgrep -u "$TEST_USER" -f '(^|/)(vpinfe)([[:space:]]|$)|vpinfe/.+main\.py' 2>/dev/null || true
}

detect_vpinfe_service() {
  local candidate pid unit
  if [[ -n "$VPINFE_SERVICE_REQUESTED" ]]; then
    candidate="$VPINFE_SERVICE_REQUESTED"
    [[ "$candidate" == *.service ]] || candidate="${candidate}.service"
    if systemctl show "$candidate" -p LoadState --value 2>/dev/null | grep -qxv 'not-found'; then
      printf '%s\n' "$candidate"
      return 0
    fi
  fi

  while IFS= read -r pid; do
    [[ -r "/proc/$pid/cgroup" ]] || continue
    unit="$(grep -Eo '[^/]+\.service' "/proc/$pid/cgroup" 2>/dev/null | tail -n1 || true)"
    if [[ -n "$unit" ]] && systemctl show "$unit" -p LoadState --value 2>/dev/null | grep -qxv 'not-found'; then
      printf '%s\n' "$unit"
      return 0
    fi
  done < <(vpinfe_pids)

  for candidate in pincabos-vpinfe.service vpinfe.service; do
    if systemctl show "$candidate" -p LoadState --value 2>/dev/null | grep -qxv 'not-found'; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

wait_vpinfe_stopped() {
  local deadline=$((SECONDS + 25))
  while (( SECONDS < deadline )); do
    if [[ -n "$VPINFE_SERVICE_RESOLVED" ]] && systemctl is-active --quiet "$VPINFE_SERVICE_RESOLVED" 2>/dev/null; then
      sleep 1
      continue
    fi
    [[ -z "$(vpinfe_pids)" ]] && return 0
    sleep 1
  done
  return 1
}

prepare_vpinfe_for_tests() {
  printf '%s\n' '--- 0. Isolation de VPinFE ---'
  if [[ "$VPINFE_MANAGED_EXTERNALLY" == 1 ]]; then
    VPINFE_SERVICE_RESOLVED="${VPINFE_SERVICE_REQUESTED:-$(detect_vpinfe_service || true)}"
    if { [[ -n "$VPINFE_SERVICE_RESOLVED" ]] && systemctl is-active --quiet "$VPINFE_SERVICE_RESOLVED" 2>/dev/null; } || [[ -n "$(vpinfe_pids)" ]]; then
      add_failure "VPinFE est encore actif malgré la gestion externe du lot"
      printf 'ERREUR [x] VPinFE doit être arrêté avant le test.\n\n'
      return 1
    fi
    printf 'GO [√] VPinFE est déjà arrêté et géré par alltabletest.sh.\n'
    printf 'Service VPinFE : %s\n\n' "${VPINFE_SERVICE_RESOLVED:-non détecté}"
    return 0
  fi

  if [[ "$(id -u)" -ne 0 ]]; then
    add_failure "Le test doit être lancé avec sudo afin d'arrêter VPinFE"
    printf 'ERREUR [x] Privilèges root requis pour arrêter VPinFE.\n\n'
    return 1
  fi

  VPINFE_SERVICE_RESOLVED="$(detect_vpinfe_service || true)"
  if [[ -n "$VPINFE_SERVICE_RESOLVED" ]]; then
    systemctl is-active --quiet "$VPINFE_SERVICE_RESOLVED" 2>/dev/null && VPINFE_WAS_ACTIVE=1 || true
    printf 'Service VPinFE : %s\n' "$VPINFE_SERVICE_RESOLVED"
    printf 'État initial    : %s\n' "$([[ "$VPINFE_WAS_ACTIVE" == 1 ]] && echo actif || echo inactif)"
    systemctl stop "$VPINFE_SERVICE_RESOLVED" || {
      add_failure "Impossible d'arrêter $VPINFE_SERVICE_RESOLVED"
      return 1
    }
    VPINFE_ENABLE_STATE="$(systemctl is-enabled "$VPINFE_SERVICE_RESOLVED" 2>/dev/null || true)"
    if [[ "$VPINFE_ENABLE_STATE" != masked* ]]; then
      if systemctl mask --runtime "$VPINFE_SERVICE_RESOLVED" >/dev/null 2>&1; then
        VPINFE_RUNTIME_MASK_APPLIED=1
      else
        add_failure "Impossible de masquer temporairement $VPINFE_SERVICE_RESOLVED"
        return 1
      fi
    fi
  elif [[ -n "$(vpinfe_pids)" ]]; then
    add_failure "Processus VPinFE trouvé, mais service systemd introuvable; définis PINCAB_VPINFE_SERVICE"
    printf 'ERREUR [x] Service systemd VPinFE introuvable; arrêt/restauration sûrs impossibles.\n\n'
    return 1
  else
    printf 'INFO [i] Aucun service ni processus VPinFE actif détecté.\n'
  fi

  if ! wait_vpinfe_stopped; then
    local pids
    pids="$(vpinfe_pids)"
    [[ -n "$pids" ]] && kill -TERM $pids 2>/dev/null || true
    sleep 3
    pids="$(vpinfe_pids)"
    [[ -n "$pids" ]] && kill -KILL $pids 2>/dev/null || true
  fi

  if { [[ -n "$VPINFE_SERVICE_RESOLVED" ]] && systemctl is-active --quiet "$VPINFE_SERVICE_RESOLVED" 2>/dev/null; } || [[ -n "$(vpinfe_pids)" ]]; then
    add_failure "VPinFE n'a pas pu être complètement arrêté"
    printf 'ERREUR [x] VPinFE est encore actif; tests VPX bloqués.\n\n'
    return 1
  fi
  printf 'GO [√] VPinFE est complètement arrêté et verrouillé pendant le test.\n\n'
}

restore_vpinfe() {
  [[ "$VPINFE_RESTORE_DONE" == 0 ]] || return 0
  VPINFE_RESTORE_DONE=1
  [[ "$VPINFE_MANAGED_EXTERNALLY" == 0 ]] || return 0
  [[ -n "$VPINFE_SERVICE_RESOLVED" ]] || return 0

  printf '\n--- Restauration de VPinFE ---\n'
  if [[ "$VPINFE_RUNTIME_MASK_APPLIED" == 1 ]]; then
    systemctl unmask --runtime "$VPINFE_SERVICE_RESOLVED" >/dev/null 2>&1 || true
  fi
  if [[ "$VPINFE_WAS_ACTIVE" == 1 ]]; then
    if systemctl start "$VPINFE_SERVICE_RESOLVED" && systemctl is-active --quiet "$VPINFE_SERVICE_RESOLVED"; then
      printf 'GO [√] VPinFE relancé: %s\n' "$VPINFE_SERVICE_RESOLVED"
    else
      printf 'ERREUR [x] VPinFE n’a pas pu être relancé: %s\n' "$VPINFE_SERVICE_RESOLVED"
      return 1
    fi
  else
    printf 'INFO [i] VPinFE était déjà arrêté avant le test; il reste arrêté.\n'
  fi
}

cleanup() {
  cleanup_process
  restore_pup_dirs
  local f
  for f in "${TEMP_FILES[@]:-}"; do
    [[ -n "$f" ]] && rm -f -- "$f" 2>/dev/null || true
  done
  restore_vpinfe || true
}
trap cleanup EXIT
trap 'exit 130' INT TERM HUP

require_uint() {
  [[ "$2" =~ ^[0-9]+$ ]] || { printf 'ERREUR: %s doit être numérique.\n' "$1" >&2; exit 64; }
}

while (($#)); do
  case "$1" in
    --mode) MODE_REQUEST="${2:-}"; shift 2 ;;
    --launcher) FORCE_LAUNCHER="${2:-}"; shift 2 ;;
    --seconds) RUN_SECONDS="${2:-}"; require_uint --seconds "$RUN_SECONDS"; shift 2 ;;
    --startup-timeout) STARTUP_TIMEOUT="${2:-}"; require_uint --startup-timeout "$STARTUP_TIMEOUT"; shift 2 ;;
    --tables-root) TABLES_ROOT="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    --*) printf 'Option inconnue: %s\n' "$1" >&2; usage; exit 64 ;;
    *) [[ -z "$TABLE" ]] || { printf 'Une seule table peut être fournie.\n' >&2; exit 64; }; TABLE="$1"; shift ;;
  esac
done

case "$MODE_REQUEST" in auto|native|rom|pup) ;; *) printf 'Mode invalide: %s\n' "$MODE_REQUEST" >&2; exit 64 ;; esac
case "$FORCE_LAUNCHER" in vpinfe|auto|normal|lowlatency) ;; *) printf 'Launcher invalide: %s\n' "$FORCE_LAUNCHER" >&2; exit 64 ;; esac
[[ -n "$TABLE" ]] || { usage; exit 64; }

resolve_table() {
  local input="$1" match_count=0
  if [[ -f "$input" ]]; then
    readlink -f -- "$input"
    return
  fi
  [[ -d "$TABLES_ROOT" ]] || return 1
  mapfile -d '' matches < <(find "$TABLES_ROOT" -type f -iname '*.vpx' \
    -not -path '*/logs/*' -not -path '*/cache/*' -not -path '*/backup*/*' \
    -ipath "*${input}*" -print0 2>/dev/null | sort -z)
  match_count="${#matches[@]}"
  if (( match_count == 1 )); then
    readlink -f -- "${matches[0]}"
  elif (( match_count == 0 )); then
    return 1
  else
    printf 'ERREUR: plusieurs tables correspondent à "%s":\n' "$input" >&2
    printf '  %s\n' "${matches[@]}" >&2
    return 2
  fi
}

if ! TABLE="$(resolve_table "$TABLE")"; then
  printf 'ERREUR: table introuvable ou ambiguë.\n' >&2
  exit 66
fi

TABLE_DIR="$(dirname -- "$TABLE")"
TABLE_FILE="$(basename -- "$TABLE")"
TABLE_STEM="${TABLE_FILE%.*}"
LOG_DIR="$TABLE_DIR/logs"
REPORT="$LOG_DIR/${TABLE_STEM}-report.txt"
ANALYSIS="$LOG_DIR/${TABLE_STEM}-analysis.txt"
RUNTIME_ROOT="$LOG_DIR/runtime/${TABLE_STEM}"
SNAP_ROOT="$LOG_DIR/snapshots/${TABLE_STEM}"
LOCK_FILE="$LOG_DIR/.${TABLE_STEM}.tabletest.lock"

mkdir -p -- "$LOG_DIR" "$RUNTIME_ROOT" "$SNAP_ROOT"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  printf 'ERREUR: un test est déjà actif pour cette table.\n' >&2
  exit 75
fi

GLOBAL_LOCK_FILE="/var/lock/pincabos-tabletest-runtime.lock"
if ! ( mkdir -p /var/lock && : >"$GLOBAL_LOCK_FILE" ) 2>/dev/null; then
  GLOBAL_LOCK_FILE="/tmp/pincabos-tabletest-runtime.lock"
fi
exec 8>"$GLOBAL_LOCK_FILE"
if ! flock -n 8; then
  printf 'ERREUR: un autre test VPX PinCabOS est déjà actif.\n' >&2
  exit 75
fi

# Le dernier résultat remplace le précédent, sans dossier de date.
rm -rf -- "$RUNTIME_ROOT" "$SNAP_ROOT"
mkdir -p -- "$RUNTIME_ROOT" "$SNAP_ROOT"
: >"$REPORT"
: >"$ANALYSIS"

exec > >(tee -a "$REPORT") 2>&1

printf '===============================================================\n'
printf ' PINCABOS — TEST AUTOMATISÉ VPX INDIVIDUEL\n'
printf '===============================================================\n'
printf 'Version script : %s\n' "$SCRIPT_VERSION"
printf 'Début          : %s\n' "$(now_iso)"
printf 'Table          : %s\n' "$TABLE"
printf 'Dossier logs   : %s\n' "$LOG_DIR"
printf 'Rapport        : %s\n' "$REPORT"
printf 'Snapshots      : %s\n\n' "$SNAP_ROOT"

if [[ -z "$XAUTHORITY_VALUE" ]]; then
  for candidate in "/home/$TEST_USER/.Xauthority" "/run/user/$(id -u "$TEST_USER" 2>/dev/null || echo 1000)/gdm/Xauthority"; do
    if [[ -r "$candidate" ]]; then XAUTHORITY_VALUE="$candidate"; break; fi
  done
fi

run_as_test_user() {
  if [[ "$(id -un)" == "$TEST_USER" ]]; then
    env DISPLAY="$DISPLAY_VALUE" XAUTHORITY="$XAUTHORITY_VALUE" HOME="$(getent passwd "$TEST_USER" | cut -d: -f6)" "$@"
  elif command -v runuser >/dev/null 2>&1 && id "$TEST_USER" >/dev/null 2>&1; then
    runuser -u "$TEST_USER" -- env DISPLAY="$DISPLAY_VALUE" XAUTHORITY="$XAUTHORITY_VALUE" HOME="$(getent passwd "$TEST_USER" | cut -d: -f6)" "$@"
  else
    env DISPLAY="$DISPLAY_VALUE" XAUTHORITY="$XAUTHORITY_VALUE" "$@"
  fi
}

test_user_home() {
  getent passwd "$TEST_USER" | cut -d: -f6
}

prepare_hybrid_runtime() {
  local group
  group="$(id -gn "$TEST_USER")"
  if [[ "$(id -u)" -eq 0 ]]; then
    install -d -o "$TEST_USER" -g "$group" -m 0775 "$HYBRID_RUNTIME_DIR"
    touch "$HYBRID_LOG"
    chown "$TEST_USER:$group" "$HYBRID_LOG"
    chmod 0664 "$HYBRID_LOG"
  fi
  [[ -d "$HYBRID_RUNTIME_DIR" && -w "$HYBRID_RUNTIME_DIR" ]] || {
    add_failure "Runtime hybride absent ou non inscriptible: $HYBRID_RUNTIME_DIR"
    return 1
  }
  printf 'Runtime hybride  : %s\n' "$(stat -c '%U:%G %a %n' "$HYBRID_RUNTIME_DIR" 2>/dev/null || echo "$HYBRID_RUNTIME_DIR")"
  printf 'Journal hybride  : %s\n' "$(stat -c '%U:%G %a %n' "$HYBRID_LOG" 2>/dev/null || echo "$HYBRID_LOG")"
}

detect_with_pincabos_detector() {
  [[ -x "$HYBRID_DETECTOR" ]] || return 0
  local output
  output="$(python3 "$HYBRID_DETECTOR" --shell "$TABLE" 2>>"$ANALYSIS" || true)"
  [[ -n "$output" ]] || return 0
  # Détecteur local PinCabOS de confiance; ses valeurs sont protégées avec shlex.quote.
  eval "$output"
  DETECTOR_ORIGINAL="${DETECT_ORIGINAL:-}"
  DETECTOR_PUP="${DETECT_PUP:-}"
  DETECTOR_B2S="${DETECT_B2S:-}"
  DETECTOR_PUP_ROOT="${DETECT_PUP_ROOT:-}"
  if [[ -n "${DETECT_ROM_FILES:-}" ]]; then
    while IFS= read -r value; do [[ -n "$value" ]] && DETECTOR_ROM_FILES+=("$value"); done <<<"$DETECT_ROM_FILES"
  fi
  if [[ -n "${DETECT_PUP_PACKS:-}" ]]; then
    while IFS= read -r value; do [[ -n "$value" ]] && DETECTOR_PUP_PACKS+=("$value"); done <<<"$DETECT_PUP_PACKS"
  fi
  printf '\n[Détecteur PinCabOS]\n%s\n' "$output" >>"$ANALYSIS"
}

record_vpx_log_baseline() {
  local output="$1" home_dir f
  home_dir="$(test_user_home)"
  : >"$output"
  while IFS= read -r -d '' f; do
    printf '%s\t%s\n' "$f" "$(stat -c %s "$f" 2>/dev/null || echo 0)" >>"$output"
  done < <(find "$home_dir/.local/share/VPinballX" -type f \( -iname 'vpinball.log' -o -iname '*vpinball*.log' \) -print0 2>/dev/null)
}

copy_new_vpx_logs() {
  local dest="$1" baseline="$2" home_dir f old_size current_size start safe_name
  home_dir="$(test_user_home)"
  mkdir -p -- "$dest"
  while IFS= read -r -d '' f; do
    old_size="$(awk -F '\t' -v p="$f" '$1==p{print $2; exit}' "$baseline" 2>/dev/null || true)"
    [[ "$old_size" =~ ^[0-9]+$ ]] || old_size=0
    current_size="$(stat -c %s "$f" 2>/dev/null || echo 0)"
    safe_name="$(basename "$(dirname "$f")")-$(basename "$f")"
    if (( current_size >= old_size )); then
      start=$((old_size + 1))
      tail -c +"$start" -- "$f" >"$dest/$safe_name" 2>/dev/null || true
    else
      cp -a -- "$f" "$dest/$safe_name" 2>/dev/null || true
    fi
  done < <(find "$home_dir/.local/share/VPinballX" -type f \( -iname 'vpinball.log' -o -iname '*vpinball*.log' \) -print0 2>/dev/null)
}

run_native_b2s_prelaunch() {
  local mode="$1" pass_dir="$2"
  [[ "$mode" == rom || "$mode" == native ]] || return 0
  [[ -x "$NATIVE_B2S_PRELAUNCH" ]] || return 0
  if [[ "$(id -u)" -eq 0 ]] && "$NATIVE_B2S_PRELAUNCH" "$TABLE" >"$pass_dir/prelaunch.log" 2>&1; then
    printf 'GO [√] Prélaunch B2S/ScoreView exécuté comme root.\n'
  else
    add_warning "$TABLE_STEM [$mode] prélaunch B2S/ScoreView en avertissement"
    printf 'WARN [!] Prélaunch B2S/ScoreView non bloquant; voir %s\n' "$pass_dir/prelaunch.log"
  fi
}

build_mode_launch() {
  local mode="$1" first="${VPX_LAUNCH_CMD[0]:-}"
  MODE_LAUNCH_ENV=("${VPX_LAUNCH_ENV[@]}")
  MODE_LAUNCH_CMD=("${VPX_LAUNCH_CMD[@]}")
  case "$first" in
    /opt/pincabos/launchers/pincabos-launch-hybrid.sh|/opt/pincabos/launchers/pincabos-launch-original.sh|/opt/pincabos/launchers/pincabos-launch-puppack.sh)
      if [[ "$mode" == pup ]]; then
        MODE_LAUNCH_CMD[0]="/opt/pincabos/launchers/pincabos-launch-puppack.sh"
      else
        MODE_LAUNCH_CMD[0]="/opt/pincabos/launchers/pincabos-launch-original.sh"
      fi
      [[ -x "$ORIGINAL_REAL_LAUNCHER" ]] && MODE_LAUNCH_ENV+=("PINCABOS_REAL_LAUNCHER=$ORIGINAL_REAL_LAUNCHER")
      ;;
  esac
  if [[ "$mode" == pup ]]; then
    MODE_LAUNCH_ENV+=("PINCABOS_GAME_CHOICE=pup" "PINCABOS_PUP_ENABLED=1")
  else
    MODE_LAUNCH_ENV+=("PINCABOS_GAME_CHOICE=original" "PINCABOS_PUP_ENABLED=0")
  fi
}

resolve_user_path() {
  local raw="$1" preferred_base="${2:-}" home_dir candidate
  [[ -n "$raw" ]] || return 1
  home_dir="$(test_user_home)"
  raw="${raw/#\~/$home_dir}"
  raw="${raw//\$HOME/$home_dir}"
  if [[ "$raw" == /* ]]; then
    printf '%s\n' "$raw"
    return 0
  fi
  for candidate in \
    "$preferred_base/$raw" \
    "$(dirname -- "$VPINFE_INI")/$raw" \
    "$home_dir/vpinfe/$raw" \
    "$home_dir/$raw"; do
    [[ -e "$candidate" ]] && { readlink -f -- "$candidate"; return 0; }
  done
  printf '%s\n' "${preferred_base:-$(dirname -- "$VPINFE_INI")}/$raw"
}

detect_vpinfe_ini() {
  local home_dir candidate pid config_dir
  home_dir="$(test_user_home)"
  if [[ -n "$VPINFE_INI" ]]; then
    [[ -r "$VPINFE_INI" ]] && { readlink -f -- "$VPINFE_INI"; return 0; }
    return 1
  fi

  # D'abord le répertoire réellement utilisé par un VPinFE actif.
  while IFS= read -r pid; do
    [[ -r "/proc/$pid/environ" ]] || continue
    config_dir="$(tr '\0' '\n' <"/proc/$pid/environ" 2>/dev/null | sed -n 's/^VPINFE_CONFIG_DIR=//p' | head -n1)"
    [[ -n "$config_dir" && -r "$config_dir/vpinfe.ini" ]] && { readlink -f -- "$config_dir/vpinfe.ini"; return 0; }
  done < <(pgrep -u "$TEST_USER" -f '(^|/)(vpinfe)([[:space:]]|$)|vpinfe/.+main\.py' 2>/dev/null || true)

  for candidate in \
    "$home_dir/.config/vpinfe/vpinfe.ini" \
    "$home_dir/vpinfe/vpinfe.ini" \
    "$home_dir/.local/share/vpinfe/vpinfe.ini" \
    "/opt/pincabos/vpinfe/vpinfe.ini" \
    "/opt/vpinfe/vpinfe.ini"; do
    [[ -r "$candidate" ]] && { readlink -f -- "$candidate"; return 0; }
  done

  candidate="$(find "$home_dir" /opt/pincabos /opt/vpinfe -maxdepth 5 -type f -name vpinfe.ini -readable -print -quit 2>/dev/null || true)"
  [[ -n "$candidate" ]] && { readlink -f -- "$candidate"; return 0; }
  return 1
}

read_vpinfe_config() {
  local values=()
  mapfile -d '' values < <(python3 - "$VPINFE_INI" "$TABLE" <<'PYCFG'
import configparser
import json
import sys
from pathlib import Path

ini = Path(sys.argv[1])
table = Path(sys.argv[2])
cfg = configparser.ConfigParser(interpolation=None)
cfg.read(ini, encoding="utf-8")

def setting(*names, default=""):
    for name in names:
        if cfg.has_option("Settings", name):
            return cfg.get("Settings", name, fallback=default).strip()
    return default

info_file = ""
altlauncher = ""
info_rom = ""
infos = sorted(table.parent.glob("*.info"))
chosen = None
for path in infos:
    try:
        data = json.loads(path.read_text(errors="ignore"))
    except Exception:
        continue
    filename = str(data.get("VPXFile", {}).get("filename", ""))
    if filename and filename.casefold() == table.name.casefold():
        chosen = (path, data)
        break
    if chosen is None:
        chosen = (path, data)
if chosen:
    path, data = chosen
    info_file = str(path)
    vpinfe = data.get("VPinFE", {}) or {}
    altlauncher = str(vpinfe.get("altlauncher", "") or "").strip()
    info_rom = str((data.get("VPXFile", {}) or {}).get("rom", "") or (data.get("Info", {}) or {}).get("Rom", "") or "").strip()

values = [
    setting("vpxbinpath"),
    setting("vpxlaunchenv"),
    setting("globalinioverride"),
    setting("globaltableinioverrideenabled", "globaltableinioverride", "tableinioverrideenabled", default="false"),
    setting("globaltableinioverridemask", "tableinioverridemask"),
    setting("vpxinipath"),
    info_file,
    altlauncher,
    info_rom,
]
for value in values:
    sys.stdout.buffer.write(value.encode("utf-8", errors="replace") + b"\0")
PYCFG
  )
  VPINFE_VPXBINPATH="${values[0]:-}"
  VPINFE_VPXLAUNCHENV="${values[1]:-}"
  VPINFE_GLOBAL_INI="${values[2]:-}"
  VPINFE_TABLEINI_ENABLED="${values[3]:-false}"
  VPINFE_TABLEINI_MASK="${values[4]:-}"
  VPINFE_VPXINIPATH="${values[5]:-}"
  TABLE_INFO_FILE="${values[6]:-}"
  TABLE_ALT_LAUNCHER="${values[7]:-}"
  TABLE_INFO_ROM="${values[8]:-}"
}

parse_vpinfe_launch_env() {
  VPX_LAUNCH_ENV=()
  [[ -n "$VPINFE_VPXLAUNCHENV" ]] || return 0
  mapfile -d '' VPX_LAUNCH_ENV < <(python3 - "$VPINFE_VPXLAUNCHENV" <<'PYENV'
import re
import sys
raw = sys.argv[1]
for item in re.split(r"[;\r\n]+", raw):
    item = item.strip()
    if not item or "=" not in item:
        continue
    key, value = item.split("=", 1)
    key = key.strip()
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
        sys.stdout.buffer.write(f"{key}={value.strip()}".encode() + b"\0")
PYENV
  )
}

truthy() {
  case "${1,,}" in 1|true|yes|on|enabled) return 0 ;; *) return 1 ;; esac
}

configure_vpinfe_launcher() {
  local raw_launcher tableini candidate
  VPINFE_INI="$(detect_vpinfe_ini || true)"
  if [[ -z "$VPINFE_INI" ]]; then
    add_failure "vpinfe.ini introuvable pour l'utilisateur $TEST_USER"
    return 1
  fi
  read_vpinfe_config
  parse_vpinfe_launch_env

  if [[ -n "$TABLE_ALT_LAUNCHER" ]]; then
    raw_launcher="$TABLE_ALT_LAUNCHER"
    LAUNCH_SOURCE="VPinFE .info / VPinFE.altlauncher"
    SELECTED_LAUNCHER="$(resolve_user_path "$raw_launcher" "$TABLE_DIR")"
  else
    raw_launcher="$VPINFE_VPXBINPATH"
    LAUNCH_SOURCE="vpinfe.ini / Settings.vpxbinpath"
    SELECTED_LAUNCHER="$(resolve_user_path "$raw_launcher" "$(dirname -- "$VPINFE_INI")")"
  fi

  [[ -n "$raw_launcher" ]] || { add_failure "Settings.vpxbinpath est vide dans $VPINFE_INI"; return 1; }
  [[ -x "$SELECTED_LAUNCHER" ]] || add_failure "Launcher VPinFE absent ou non exécutable: $SELECTED_LAUNCHER"

  VPX_LAUNCH_ARGS=()
  if [[ -n "$VPINFE_GLOBAL_INI" ]]; then
    VPINFE_GLOBAL_INI="$(resolve_user_path "$VPINFE_GLOBAL_INI" "$(dirname -- "$VPINFE_INI")")"
    if [[ -r "$VPINFE_GLOBAL_INI" ]]; then
      VPX_LAUNCH_ARGS+=("-ini" "$VPINFE_GLOBAL_INI")
    else
      add_failure "Global ini configuré dans VPinFE mais introuvable: $VPINFE_GLOBAL_INI"
    fi
  fi

  if truthy "$VPINFE_TABLEINI_ENABLED" && [[ -n "$VPINFE_TABLEINI_MASK" ]]; then
    candidate="$TABLE_DIR/${TABLE_STEM}.${VPINFE_TABLEINI_MASK}.ini"
    if [[ -r "$candidate" ]]; then
      VPX_LAUNCH_ARGS+=("-tableini" "$candidate")
    fi
  fi
  VPX_LAUNCH_CMD=("$SELECTED_LAUNCHER" "${VPX_LAUNCH_ARGS[@]}" "$TABLE")
}

choose_legacy_launcher() {
  case "$FORCE_LAUNCHER" in
    normal) printf '%s\n' "$LAUNCHER" ;;
    lowlatency) printf '%s\n' "$LOWLATENCY_LAUNCHER" ;;
  esac
}

if [[ "$FORCE_LAUNCHER" == vpinfe || "$FORCE_LAUNCHER" == auto ]]; then
  configure_vpinfe_launcher || true
else
  SELECTED_LAUNCHER="$(choose_legacy_launcher)"
  LAUNCH_SOURCE="option legacy --launcher $FORCE_LAUNCHER"
  VPX_LAUNCH_CMD=("$SELECTED_LAUNCHER" "$TABLE")
  [[ -x "$SELECTED_LAUNCHER" ]] || add_failure "Launcher VPX absent ou non exécutable: $SELECTED_LAUNCHER"
fi

find_vpx_bin() {
  local c target
  for c in "${PINCAB_VPX_BIN:-}" \
    "$SELECTED_LAUNCHER" \
    /opt/pincabos/bin/VPinballX_BGFX \
    /opt/pincabos/bin/VPinballX_GL \
    /opt/vpinball/VPinballX_BGFX \
    /opt/vpinball/VPinballX_GL \
    /usr/local/bin/VPinballX_BGFX \
    /usr/local/bin/VPinballX_GL \
    "$(command -v VPinballX_BGFX 2>/dev/null || true)" \
    "$(command -v VPinballX_GL 2>/dev/null || true)"; do
    [[ -n "$c" && -x "$c" && "$(basename -- "$c")" =~ ^VPinballX_(BGFX|GL)$ ]] && { printf '%s\n' "$c"; return 0; }
  done
  if [[ -r "$SELECTED_LAUNCHER" ]]; then
    while IFS= read -r target; do
      [[ -x "$target" ]] && { printf '%s\n' "$target"; return 0; }
    done < <(grep -Eo '/[^"[:space:]]*/VPinballX_(BGFX|GL)' "$SELECTED_LAUNCHER" 2>/dev/null | sort -u)
  fi
  return 1
}

resolve_real_launcher() {
  local candidate
  for candidate in \
    "${PINCABOS_REAL_LAUNCHER:-}" \
    "/opt/pincabos/scripts/VPXlauncher.real.sh" \
    "/opt/pincabos/scripts/VPXlauncher.pincabos-original.sh" \
    "/opt/pincabos/scripts/VPXlauncher.sh"; do
    [[ -n "$candidate" && -x "$candidate" ]] || continue
    if [[ "$candidate" == "/opt/pincabos/scripts/VPXlauncher.sh" ]] && \
       grep -Eqi 'pincabos-hybrid-launch|/opt/pincabos/launchers/pincabos-launch' "$candidate" 2>/dev/null; then
      continue
    fi
    printf '%s\n' "$candidate"
    return 0
  done
  return 1
}

VPX_BIN="$(find_vpx_bin || true)"
ORIGINAL_REAL_LAUNCHER="$(resolve_real_launcher || true)"
[[ -n "$ORIGINAL_REAL_LAUNCHER" ]] || add_failure "Launcher VPX réel introuvable pour les launchers PinCabOS"

prepare_vpinfe_for_tests || true
prepare_hybrid_runtime || true
printf '%s\n' '--- 1. Prévol ---'
printf 'Utilisateur test : %s\n' "$TEST_USER"
printf 'DISPLAY          : %s\n' "$DISPLAY_VALUE"
printf 'XAUTHORITY       : %s\n' "${XAUTHORITY_VALUE:-non détecté}"
printf 'Topologie écrans : %s\n' "${DISPLAY_ALIASES_FILE:-non configurée}"
printf 'Playfield        : %s | %s\n' "$PLAYFIELD_OUTPUT" "${PLAYFIELD_GEOMETRY:-géométrie XRandR}"
printf 'Backglass        : %s | %s\n' "$BACKGLASS_OUTPUT" "${BACKGLASS_GEOMETRY:-géométrie XRandR}"
printf 'FullDMD          : %s | %s\n' "$FULLDMD_OUTPUT" "${FULLDMD_GEOMETRY:-géométrie XRandR}"
printf 'VPinFE INI       : %s\n' "${VPINFE_INI:-non détecté}"
printf 'Source launcher  : %s\n' "${LAUNCH_SOURCE:-non détectée}"
printf 'Launcher         : %s\n' "${SELECTED_LAUNCHER:-non détecté}"
printf 'Table .info      : %s\n' "${TABLE_INFO_FILE:-aucun}"
printf 'Binaire VPX      : %s\n' "${VPX_BIN:-non détecté}"
printf 'Launcher réel    : %s\n' "${ORIGINAL_REAL_LAUNCHER:-non détecté}"
printf 'Commande exacte  : '
printf '%q ' "${VPX_LAUNCH_CMD[@]:-}"
printf '\n'
if ((${#VPX_LAUNCH_ENV[@]})); then
  printf 'Environnement VPX: %s\n' "${VPX_LAUNCH_ENV[*]}"
else
  printf 'Environnement VPX: (aucun override VPinFE)\n'
fi
printf 'Durée/passage    : %ss\n' "$RUN_SECONDS"
printf 'Captures         : JPEG compact, largeur max %spx, qualité %s, bureau complet=%s\n' \
  "$CAPTURE_MAX_WIDTH" "$CAPTURE_JPEG_QUALITY" "$CAPTURE_ALL_SCREENS"

for cmd in find grep sed awk sha256sum timeout flock setsid; do
  command -v "$cmd" >/dev/null 2>&1 || add_failure "Commande obligatoire absente: $cmd"
done
for cmd in xdotool xrandr ffmpeg; do
  command -v "$cmd" >/dev/null 2>&1 || add_warning "Commande recommandée absente: $cmd"
done

printf '\n%s\n' '--- 2. VBS latéral ---'
VBS="$TABLE_DIR/${TABLE_STEM}.vbs"
if [[ -s "$VBS" ]]; then
  printf 'GO [√] VBS existant conservé : %s\n' "$VBS"
  add_pass "VBS présent à côté du VPX"
else
  if [[ -n "$VPX_BIN" ]]; then
    printf 'INFO [i] Extraction du script VBS intégré...\n'
    before_list="$(mktemp)"; TEMP_FILES+=("$before_list")
    find "$TABLE_DIR" -maxdepth 1 -type f -iname '*.vbs' -printf '%f\n' | sort >"$before_list"
    if (cd "$TABLE_DIR" && run_as_test_user "$VPX_BIN" -extractvbs "$TABLE") >>"$RUNTIME_ROOT/extractvbs.log" 2>&1; then
      if [[ -s "$VBS" ]]; then
        chmod 0644 "$VBS" 2>/dev/null || true
        printf 'GO [√] VBS créé : %s\n' "$VBS"
        add_pass "VBS extrait et créé à côté du VPX"
      else
        extracted="$(find "$TABLE_DIR" -maxdepth 1 -type f -iname '*.vbs' -printf '%p\n' | while read -r f; do grep -Fxq "$(basename "$f")" "$before_list" || printf '%s\n' "$f"; done | head -n1)"
        if [[ -n "$extracted" && -s "$extracted" ]]; then
          cp -a -- "$extracted" "$VBS"
          printf 'GO [√] VBS extrait puis normalisé : %s\n' "$VBS"
          add_pass "VBS extrait et normalisé au nom du VPX"
        else
          printf 'ERREUR [x] VPX n’a produit aucun VBS exploitable.\n'
          add_failure "Extraction VBS échouée"
        fi
      fi
    else
      printf 'ERREUR [x] Échec de -extractvbs; voir %s\n' "$RUNTIME_ROOT/extractvbs.log"
      add_failure "VPX -extractvbs a retourné une erreur"
    fi
  else
    printf 'ERREUR [x] Impossible d’extraire le VBS: binaire VPX introuvable.\n'
    add_failure "VBS manquant et binaire VPX introuvable"
  fi
fi

printf '\n%s\n' '--- 3. Analyse statique de la table et du VBS ---'
{
  printf 'Analyse créée : %s\n' "$(now_iso)"
  printf 'Table : %s\n' "$TABLE"
  printf 'Taille VPX : %s octets\n' "$(stat -c %s "$TABLE")"
  printf 'SHA256 VPX : %s\n\n' "$(sha256sum "$TABLE" | awk '{print $1}')"
  printf '[Fichiers du dossier]\n'
  find "$TABLE_DIR" -maxdepth 3 -mindepth 1 -not -path "$LOG_DIR/*" -printf '%y %P\n' | sort
} >"$ANALYSIS"

if [[ -s "$VBS" ]]; then
  {
    printf '\n[VBS]\nChemin : %s\nTaille : %s octets\nSHA256 : %s\n' "$VBS" "$(stat -c %s "$VBS")" "$(sha256sum "$VBS" | awk '{print $1}')"
    printf '\n[ROM détectées]\n'
  } >>"$ANALYSIS"

  mapfile -t ROM_NAMES < <(
    if command -v python3 >/dev/null 2>&1; then
      python3 - "$VBS" <<'PYROM'
import re
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(errors="ignore")
patterns = [
    r"\b(?:cGameName|GameName|Controller\.GameName)\s*=\s*[\"']([^\"']+)[\"']",
]
roms = set()
for pattern in patterns:
    for value in re.findall(pattern, text, flags=re.IGNORECASE):
        value = re.sub(r"\s+", "", value).removesuffix(".zip")
        if value.lower().endswith(".vbs"):
            continue
        if re.fullmatch(r"[A-Za-z0-9_.-]+", value):
            roms.add(value)
for rom in sorted(roms):
    print(rom)
PYROM
    else
      grep -Eio '(cGameName|GameName|Controller\.GameName)[[:space:]]*=[[:space:]]*"[A-Za-z0-9_.-]+"' "$VBS" 2>/dev/null \
        | sed -E 's/.*"([A-Za-z0-9_.-]+)"/\1/' | sort -u
    fi
  )
  if grep -Eiq "VPinMAME[.]Controller|CreateObject[[:space:]]*\\([[:space:]]*['\"]VPinMAME[.]Controller|Controller[.]Run([[:space:]]|$)" "$VBS" 2>/dev/null; then
    PINMAME_USED=1
  fi
  if (( PINMAME_USED == 1 )) && ((${#ROM_NAMES[@]} == 0)) && [[ -n "$TABLE_INFO_ROM" && ! "$TABLE_INFO_ROM" =~ [.]vbs$ ]]; then
    ROM_NAMES+=("${TABLE_INFO_ROM%.zip}")
  fi
  if ((${#ROM_NAMES[@]})); then printf '%s\n' "${ROM_NAMES[@]}" | tee -a "$ANALYSIS"; else printf '(aucune)\n' | tee -a "$ANALYSIS"; fi
  printf 'PinMAME réellement utilisé : %s\n' "$([[ $PINMAME_USED -eq 1 ]] && echo oui || echo non)" >>"$ANALYSIS"

  {
    printf '\n[Scripts appelés]\n'
    grep -Eio '(LoadVBS|GetTextFile|ExecuteGlobal)[^\r\n]+' "$VBS" 2>/dev/null | sort -u || true
    printf '\n[Références PuP/FlexDMD/UltraDMD/B2S]\n'
    grep -Ein 'pup|pinup|flexdmd|ultradmd|directb2s|b2s' "$VBS" 2>/dev/null | head -n 300 || true
    printf '\n[Références médias/musique possibles]\n'
    grep -Eio '[A-Za-z0-9_ ./()&+,-]+\.(mp3|ogg|wav|flac|mp4|webm|avi|mkv|png|jpg|jpeg)' "$VBS" 2>/dev/null | sort -u | head -n 500 || true
  } >>"$ANALYSIS"
else
  add_failure "Analyse VBS impossible: VBS absent"
fi

find_rom_file() {
  local rom="$1" root f
  local home_dir
  home_dir="$(getent passwd "$TEST_USER" | cut -d: -f6)"
  for root in \
    "$TABLE_DIR/pinmame/roms" \
    "$TABLE_DIR/roms" \
    "$TABLES_ROOT/pinmame/roms" \
    "$home_dir/.local/share/VPinballX/pinmame/roms" \
    "$home_dir/.local/share/VPinballX/10.8/pinmame/roms" \
    "$home_dir/.vpinball/pinmame/roms" \
    "/opt/pincabos/pinmame/roms"; do
    [[ -d "$root" ]] || continue
    f="$(find "$root" -maxdepth 1 -type f \( -iname "${rom}.zip" -o -iname "${rom}.7z" \) -print -quit 2>/dev/null || true)"
    [[ -n "$f" ]] && { printf '%s\n' "$f"; return 0; }
  done
  return 1
}

detect_with_pincabos_detector
if ((${#DETECTOR_ROM_FILES[@]})); then
  PINMAME_USED=1
  for detector_rom in "${DETECTOR_ROM_FILES[@]}"; do
    detector_name="$(basename "$detector_rom")"
    detector_name="${detector_name%.*}"
    found_name=0
    for existing_name in "${ROM_NAMES[@]:-}"; do
      [[ "$existing_name" == "$detector_name" ]] && found_name=1
    done
    (( found_name == 1 )) || ROM_NAMES+=("$detector_name")
  done
fi

printf '\n%s\n' '--- 4. Dépendances détectées ---'
ROM_OK=1
ROM_EXPECTED=0
ROM_FOUND_COUNT=0
ROM_MISSING_COUNT=0
ROM_ACTIVE_CANDIDATE=""
ROM_MISSING_NAMES=()
if (( PINMAME_USED == 1 )); then
  ROM_EXPECTED=1
  if ((${#ROM_NAMES[@]})); then
    ROM_OK=0
    for rom in "${ROM_NAMES[@]}"; do
      if romfile="$(find_rom_file "$rom" || true)"; [[ -n "$romfile" ]]; then
        ROM_FOUND_COUNT=$((ROM_FOUND_COUNT + 1))
        [[ -n "$ROM_ACTIVE_CANDIDATE" ]] || ROM_ACTIVE_CANDIDATE="$rom"
        printf 'GO [√] ROM candidate %-16s : %s\n' "$rom" "$romfile"
        add_pass "ROM candidate trouvée: $rom"
      else
        ROM_MISSING_COUNT=$((ROM_MISSING_COUNT + 1))
        ROM_MISSING_NAMES+=("$rom")
        printf 'OPTION ABSENTE [!] ROM candidate : %s.zip\n' "$rom"
      fi
    done

    if (( ROM_FOUND_COUNT > 0 )); then
      ROM_OK=1
      printf 'GO [√] Au moins une ROM utilisable est présente; le test runtime déterminera celle réellement sélectionnée.\n'
      if (( ROM_MISSING_COUNT > 0 )); then
        add_warning "ROM alternative(s) absente(s), non bloquantes: ${ROM_MISSING_NAMES[*]}"
      fi
    else
      ROM_OK=0
      printf 'MANQUE [x] Aucune des ROM candidates n’est disponible.\n'
      add_failure "Aucune ROM candidate disponible: ${ROM_NAMES[*]}"
    fi
  else
    # Nom dynamique: le lancement réel et le journal PinMAME feront foi.
    ROM_OK=1
    printf 'WARN [!] PinMAME est utilisé, mais le nom statique de la ROM n’a pas été déterminé; validation au runtime.\n'
    add_warning "PinMAME détecté mais nom de ROM dynamique/inconnu"
  fi
elif ((${#ROM_NAMES[@]})); then
  printf 'INFO [i] Identifiant(s) cGameName détecté(s), mais aucun contrôleur PinMAME: pas traité comme ROM obligatoire.\n'
else
  printf 'INFO [i] Aucune ROM PinMAME requise détectée dans le VBS.\n'
fi

# DirectB2S correspondant au fichier ou au dossier.
B2S_FILE=""
for candidate in "$TABLE_DIR/${TABLE_STEM}.directb2s" "$TABLE_DIR/$(basename "$TABLE_DIR").directb2s"; do
  [[ -s "$candidate" ]] && { B2S_FILE="$candidate"; break; }
done
if [[ -n "$B2S_FILE" ]]; then
  printf 'GO [√] DirectB2S : %s\n' "$B2S_FILE"
else
  printf 'INFO [i] Aucun DirectB2S correspondant trouvé.\n'
fi

# Détection des PuP-Packs locaux et connus.
mapfile -d '' PUP_DIRS < <(
  {
    find "$TABLE_DIR/pupvideos" -mindepth 1 -maxdepth 2 -type d -print0 2>/dev/null || true
    pup_aliases=("${ROM_NAMES[@]:-}")
    [[ -n "$TABLE_INFO_ROM" ]] && pup_aliases+=("${TABLE_INFO_ROM%.zip}")
    for rom in "${pup_aliases[@]:-}"; do
      [[ -n "$rom" ]] || continue
      for root in "$TABLES_ROOT/pupvideos" "/home/$TEST_USER/pupvideos" "/opt/pincabos/pupvideos" "/home/$TEST_USER/PinUPSystem/PUPVideos"; do
        [[ -d "$root/$rom" ]] && printf '%s\0' "$root/$rom"
      done
    done
  } | sort -zu
)
if [[ -n "$DETECTOR_PUP_ROOT" && -d "$DETECTOR_PUP_ROOT" ]]; then
  PUP_DIRS+=("$DETECTOR_PUP_ROOT")
fi
for detector_pack in "${DETECTOR_PUP_PACKS[@]:-}"; do
  [[ -d "$detector_pack" ]] && PUP_DIRS+=("$detector_pack")
done
# Garder seulement les dossiers semblant être un pack.
filtered_pup=()
for p in "${PUP_DIRS[@]:-}"; do
  [[ -n "$p" ]] || continue
  if [[ -f "$p/screens.pup" ]] || find "$p" -maxdepth 1 -type f \( -iname '*.mp4' -o -iname '*.webm' -o -iname '*.avi' -o -iname '*.mkv' \) -print -quit 2>/dev/null | grep -q .; then
    filtered_pup+=("$p")
  fi
done
PUP_DIRS=("${filtered_pup[@]}")
PUP_EXPECTED=0
if ((${#PUP_DIRS[@]})); then
  PUP_EXPECTED=1
  printf 'GO [√] PuP-Pack(s) détecté(s):\n'
  printf '  %s\n' "${PUP_DIRS[@]}"
  for p in "${PUP_DIRS[@]}"; do
    if [[ -s "$p/screens.pup" ]]; then
      printf '\n[Écran PuP: %s]\n' "$p/screens.pup" >>"$ANALYSIS"
      awk -F',' 'BEGIN{OFS=" | "} /^[[:space:]]*($|#)/{next} {print NR,$1,$2,$3,$4}' "$p/screens.pup" >>"$ANALYSIS" 2>/dev/null || true
    else
      add_warning "PuP-Pack sans screens.pup: $p"
    fi
  done
else
  printf 'INFO [i] Aucun PuP-Pack détecté.\n'
fi

for kind in serum vni altsound altcolor music scripts; do
  count="$(find "$TABLE_DIR" -type f -path "*/$kind/*" 2>/dev/null | wc -l)"
  (( count > 0 )) && printf 'GO [√] %-10s : %s fichier(s)\n' "$kind" "$count"
done

# Liste des modes à tester.
MODES=()
if [[ "$MODE_REQUEST" != auto ]]; then
  MODES=("$MODE_REQUEST")
elif (( ROM_EXPECTED == 1 && PUP_EXPECTED == 1 )); then
  MODES=(rom pup)
elif (( PUP_EXPECTED == 1 )); then
  MODES=(pup)
elif (( ROM_EXPECTED == 1 )); then
  MODES=(rom)
else
  MODES=(native)
fi
printf 'Modes retenus : %s\n' "${MODES[*]}"

recover_stale_disabled_pup() {
  local root disabled original
  for root in "$TABLE_DIR/pupvideos" "$TABLES_ROOT/pupvideos" "/home/$TEST_USER/pupvideos" "/opt/pincabos/pupvideos" "/home/$TEST_USER/PinUPSystem/PUPVideos"; do
    [[ -d "$root" ]] || continue
    while IFS= read -r -d '' disabled; do
      original="${disabled%.pincabos-tabletest-disabled}"
      if [[ ! -e "$original" ]]; then
        mv -- "$disabled" "$original" 2>/dev/null || true
      fi
    done < <(find "$root" -maxdepth 3 -type d -name '*.pincabos-tabletest-disabled' -print0 2>/dev/null)
  done
}
recover_stale_disabled_pup

suspend_pup_for_rom_mode() {
  restore_pup_dirs
  local p disabled
  for p in "${PUP_DIRS[@]:-}"; do
    [[ -d "$p" ]] || continue
    disabled="${p}.pincabos-tabletest-disabled"
    if [[ -e "$disabled" && ! -e "$p" ]]; then
      mv -- "$disabled" "$p"
    fi
    if [[ -e "$disabled" ]]; then
      add_failure "Impossible de désactiver temporairement le PuP-Pack; destination déjà présente: $disabled"
      continue
    fi
    if mv -- "$p" "$disabled"; then
      DISABLED_PUP_DIRS+=("$disabled")
    else
      add_failure "Permission refusée pour désactiver temporairement le PuP-Pack: $p"
    fi
  done
}

get_output_geometry() {
  local output="$1"
  command -v xrandr >/dev/null 2>&1 || return 1
  run_as_test_user xrandr --query 2>/dev/null | awk -v o="$output" '
    $1==o && $2=="connected" {
      for(i=3;i<=NF;i++) if($i ~ /^[0-9]+x[0-9]+[+-][0-9]+[+-][0-9]+$/) {print $i; exit}
    }'
}

resolve_capture_geometry() {
  local output="$1" configured_geometry="${2:-}" live_geometry=""
  live_geometry="$(get_output_geometry "$output" || true)"
  if [[ -n "$live_geometry" ]]; then
    printf '%s\n' "$live_geometry"
  elif [[ -n "$configured_geometry" ]]; then
    # Le connecteur peut avoir changé de nom; la géométrie EDID reste utilisable.
    printf '%s\n' "$configured_geometry"
  else
    return 1
  fi
}

capture_output() {
  local output="$1" configured_geometry="$2" destination="$3" geom size x y input
  mkdir -p -- "$(dirname "$destination")"
  geom="$(resolve_capture_geometry "$output" "$configured_geometry" || true)"
  if [[ -z "$geom" || ! "$geom" =~ ^([0-9]+x[0-9]+)([+-][0-9]+)([+-][0-9]+)$ ]]; then
    printf 'Capture impossible pour sortie %s (géométrie non détectée: %s).\n' "$output" "${configured_geometry:-aucune}" >>"$RUNTIME_ROOT/capture-errors.log"
    return 1
  fi
  size="${BASH_REMATCH[1]}"
  x=$(( ${BASH_REMATCH[2]} ))
  y=$(( ${BASH_REMATCH[3]} ))
  input="${DISPLAY_VALUE}.0"
  (( x >= 0 )) && input+="+${x}" || input+="${x}"
  (( y >= 0 )) && input+="+${y}" || input+="${y}"
  if command -v ffmpeg >/dev/null 2>&1; then
    local source_width filter
    source_width="${size%x*}"
    if [[ "$source_width" =~ ^[0-9]+$ ]] && (( source_width > CAPTURE_MAX_WIDTH )); then
      filter="scale=${CAPTURE_MAX_WIDTH}:-2:flags=fast_bilinear,format=yuvj420p"
    else
      filter="format=yuvj420p"
    fi
    run_as_test_user ffmpeg -hide_banner -loglevel error -y \
      -f x11grab -video_size "$size" -i "$input" -frames:v 1 \
      -vf "$filter" -q:v "$CAPTURE_JPEG_QUALITY" "$destination" \
      >>"$RUNTIME_ROOT/capture-errors.log" 2>&1
  else
    return 1
  fi
}

capture_all() {
  local dest="$1"
  mkdir -p -- "$dest"
  capture_output "$PLAYFIELD_OUTPUT" "$PLAYFIELD_GEOMETRY" "$dest/playfield.jpg" || true
  capture_output "$BACKGLASS_OUTPUT" "$BACKGLASS_GEOMETRY" "$dest/backglass.jpg" || true
  capture_output "$FULLDMD_OUTPUT" "$FULLDMD_GEOMETRY" "$dest/fulldmd.jpg" || true
  if [[ "$CAPTURE_ALL_SCREENS" == "1" ]] && command -v ffmpeg >/dev/null 2>&1; then
    run_as_test_user ffmpeg -hide_banner -loglevel error -y \
      -f x11grab -i "${DISPLAY_VALUE}.0" -frames:v 1 \
      -vf "scale=1280:-2:flags=fast_bilinear,format=yuvj420p" \
      -q:v "$CAPTURE_JPEG_QUALITY" "$dest/all-screens.jpg" \
      >>"$RUNTIME_ROOT/capture-errors.log" 2>&1 || true
  fi
}

focus_vpx_and_send() {
  local key="$1" wid
  command -v xdotool >/dev/null 2>&1 || return 1
  wid="$(run_as_test_user xdotool search --onlyvisible --class 'VPinball|VPinballX' 2>/dev/null | tail -n1 || true)"
  if [[ -z "$wid" ]]; then
    wid="$(run_as_test_user xdotool search --onlyvisible --name 'Visual Pinball|VPinball|VPX' 2>/dev/null | tail -n1 || true)"
  fi
  [[ -n "$wid" ]] || return 1
  run_as_test_user xdotool windowactivate --sync "$wid" key --clearmodifiers "$key" >/dev/null 2>&1 || true
}

accept_initial_dialogs() {
  local wid title
  command -v xdotool >/dev/null 2>&1 || return 0
  while IFS= read -r wid; do
    [[ -n "$wid" ]] || continue
    title="$(run_as_test_user xdotool getwindowname "$wid" 2>/dev/null || true)"
    if [[ "$title" =~ (PinMAME|Game[[:space:]]*Options|Legal|Disclaimer|Information|Warning|Attention|Configuration|Erreur|Error) ]]; then
      printf 'Dialogue détecté et validé: %s\n' "$title" >>"$RUNTIME_ROOT/dialogs.log"
      run_as_test_user xdotool windowactivate --sync "$wid" key --clearmodifiers Return >/dev/null 2>&1 || true
    fi
  done < <(run_as_test_user xdotool search --onlyvisible --name '.*' 2>/dev/null || true)
}

find_vpx_pid() {
  local p exe name
  for name in VPinballX_BGFX VPinballX_GL VPinballX; do
    p="$(pgrep -u "$TEST_USER" -n -x "$name" 2>/dev/null || true)"
    [[ -n "$p" ]] || continue
    exe="$(basename "$(readlink -f "/proc/$p/exe" 2>/dev/null || true)")"
    if [[ "$exe" == VPinballX_BGFX || "$exe" == VPinballX_GL || "$exe" == VPinballX ]]; then
      printf '%s
' "$p"
      return 0
    fi
  done
  return 1
}

screen_activity_count() {
  local directory="$1" role="$2"
  find "$directory" -type f -name "${role}.jpg" -print0 2>/dev/null | xargs -0 -r sha256sum 2>/dev/null | awk '{print $1}' | sort -u | wc -l
}

image_luma() {
  local image="$1" value=""
  [[ -s "$image" ]] || { printf '0\n'; return; }
  if command -v ffmpeg >/dev/null 2>&1 && command -v od >/dev/null 2>&1; then
    value="$(ffmpeg -hide_banner -loglevel error -i "$image" -vf 'scale=1:1,format=gray' -f rawvideo - 2>/dev/null       | od -An -tu1 2>/dev/null | awk 'NF{print $1; exit}' || true)"
  fi
  [[ "$value" =~ ^[0-9]+$ ]] || value=0
  printf '%s\n' "$value"
}

screen_max_luma() {
  local directory="$1" role="$2" image value max=0
  while IFS= read -r -d '' image; do
    value="$(image_luma "$image")"
    (( value > max )) && max="$value"
  done < <(find "$directory" -type f -name "${role}.jpg" -print0 2>/dev/null)
  printf '%s\n' "$max"
}

fatal_log_matches() {
  local dir="$1"
  grep -RniE --binary-files=without-match \
    --exclude='vpx-log-baseline.tsv' --exclude='prelaunch.log' \
    '(script[[:space:]_-]*error|compile[[:space:]_-]*error|syntax[[:space:]_-]*error|runtime[[:space:]_-]*error|cannot[[:space:]]+load|failed[[:space:]]+to[[:space:]]+load|rom[^[:alnum:]]+(not[[:space:]]+found|missing)|no[[:space:]]+such[[:space:]]+file|segmentation[[:space:]]+fault|assertion.*failed|fatal[[:space:]]+error|object[[:space:]]+required|type[[:space:]]+mismatch|overflow|permission[[:space:]]+denied)' \
    "$dir" 2>/dev/null \
    | grep -Eiv 'ShowTitle is deprecated|ShowDMDOnly is deprecated|ShowFrame is deprecated|Driver did not report any supported backbuffer format|pincabos-native-b2s-prelaunch-backups|pincabos-native-b2s-scoreview-prelaunch' \
    || true
}

run_one_pass() {
  local mode="$1" pass="$2"
  local pass_dir="$RUNTIME_ROOT/$mode/pass-$pass"
  local snap_dir="$SNAP_ROOT/$mode/pass-$pass"
  local stdout_log="$pass_dir/launcher.log"
  local result_file="$pass_dir/result.txt"
  local start_epoch elapsed vpx_pid="" ended_early=0 fatal_file="$pass_dir/fatal-matches.txt"
  local baseline_file="$pass_dir/vpx-log-baseline.tsv"
  local minimum_healthy
  local MODE_LAUNCH_ENV=() MODE_LAUNCH_CMD=()
  minimum_healthy=$(( RUN_SECONDS < 20 ? RUN_SECONDS : 20 ))
  mkdir -p -- "$pass_dir" "$snap_dir"

  restore_pup_dirs
  if [[ "$mode" == rom && "$PUP_EXPECTED" == 1 ]]; then
    suspend_pup_for_rom_mode
    printf 'PuP-Pack temporairement masqué pour le test ROM original.\n' >"$pass_dir/pup-state.txt"
  else
    printf 'PuP-Pack disponible normalement.\n' >"$pass_dir/pup-state.txt"
  fi

  printf '\n>>> Mode=%s | Passage=%s/2 | Début=%s\n' "$mode" "$pass" "$(now_iso)"

  if { [[ -n "$VPINFE_SERVICE_RESOLVED" ]] && systemctl is-active --quiet "$VPINFE_SERVICE_RESOLVED" 2>/dev/null; } || [[ -n "$(vpinfe_pids)" ]]; then
    printf 'ERREUR [x] VPinFE s’est relancé pendant la campagne; passage bloqué.\n'
    add_failure "$TABLE_STEM [$mode passage $pass] VPinFE actif pendant le test"
    printf 'FAIL\n' >"$pass_dir/status"
    restore_pup_dirs
    return 0
  fi

  build_mode_launch "$mode"
  printf 'Commande effective: '
  printf '%q ' "${MODE_LAUNCH_CMD[@]}"
  printf '\n'
  run_native_b2s_prelaunch "$mode" "$pass_dir"
  record_vpx_log_baseline "$baseline_file"

  # Ne jamais fermer une partie lancée hors du test.
  if [[ -n "$(find_vpx_pid || true)" ]]; then
    printf 'ERREUR [x] Une instance VPX est déjà active. Fermez-la avant le test.\n'
    add_failure "$TABLE_STEM [$mode passage $pass] instance VPX déjà active"
    printf 'FAIL\n' >"$pass_dir/status"
    restore_pup_dirs
    return 0
  fi

  start_epoch="$(date +%s)"

  if [[ "$(id -un)" == "$TEST_USER" ]]; then
    setsid env DISPLAY="$DISPLAY_VALUE" XAUTHORITY="$XAUTHORITY_VALUE" HOME="$(test_user_home)" \
      XDG_RUNTIME_DIR="/run/user/$(id -u "$TEST_USER")" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u "$TEST_USER")/bus" \
      "${MODE_LAUNCH_ENV[@]}" "${MODE_LAUNCH_CMD[@]}" >"$stdout_log" 2>&1 &
  else
    setsid runuser -u "$TEST_USER" -- env DISPLAY="$DISPLAY_VALUE" XAUTHORITY="$XAUTHORITY_VALUE" HOME="$(test_user_home)" \
      XDG_RUNTIME_DIR="/run/user/$(id -u "$TEST_USER")" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u "$TEST_USER")/bus" \
      "${MODE_LAUNCH_ENV[@]}" "${MODE_LAUNCH_CMD[@]}" >"$stdout_log" 2>&1 &
  fi
  CURRENT_PID=$!
  CURRENT_PGID="$(ps -o pgid= -p "$CURRENT_PID" 2>/dev/null | tr -d ' ' || true)"

  # Attendre VPX ou constater un arrêt précoce.
  while (( $(date +%s) - start_epoch < STARTUP_TIMEOUT )); do
    accept_initial_dialogs
    vpx_pid="$(find_vpx_pid || true)"
    [[ -n "$vpx_pid" ]] && break
    if ! kill -0 "$CURRENT_PID" 2>/dev/null; then ended_early=1; break; fi
    sleep 2
  done

  capture_all "$snap_dir/00-startup"
  if [[ -z "$vpx_pid" ]]; then
    add_failure "$TABLE_STEM [$mode passage $pass] VPX non détecté après ${STARTUP_TIMEOUT}s"
  else
    printf 'GO [√] Processus VPX détecté: PID %s\n' "$vpx_pid"
  fi

  # Séquence d'entrée répétable: crédit, start, plunger, flippers.
  local checkpoints=(15 35 60 90)
  local checkpoint next_idx=0
  for checkpoint in "${checkpoints[@]}"; do
    (( checkpoint > RUN_SECONDS )) && continue
    while (( $(date +%s) - start_epoch < checkpoint )); do
      accept_initial_dialogs
      if ! kill -0 "$CURRENT_PID" 2>/dev/null && [[ -z "$(find_vpx_pid || true)" ]]; then ended_early=1; break 2; fi
      sleep 2
    done
    case "$checkpoint" in
      15)
        focus_vpx_and_send 5 || true; sleep 1
        focus_vpx_and_send 5 || true; sleep 1
        focus_vpx_and_send 1 || true
        ;;
      35)
        focus_vpx_and_send Return || true
        focus_vpx_and_send space || true
        ;;
      60)
        focus_vpx_and_send Shift_L || true
        focus_vpx_and_send Shift_R || true
        focus_vpx_and_send z || true
        focus_vpx_and_send slash || true
        ;;
      90)
        focus_vpx_and_send 5 || true
        focus_vpx_and_send 1 || true
        focus_vpx_and_send Return || true
        ;;
    esac
    capture_all "$snap_dir/$(printf '%02d' "$checkpoint")s"
    next_idx=$((next_idx + 1))
  done

  while (( $(date +%s) - start_epoch < RUN_SECONDS )); do
    accept_initial_dialogs
    if ! kill -0 "$CURRENT_PID" 2>/dev/null && [[ -z "$(find_vpx_pid || true)" ]]; then ended_early=1; break; fi
    sleep 2
  done
  capture_all "$snap_dir/final"

  focus_vpx_and_send Escape || true
  local exit_start="$(date +%s)"
  while kill -0 "$CURRENT_PID" 2>/dev/null && (( $(date +%s) - exit_start < EXIT_TIMEOUT )); do sleep 1; done
  cleanup_process
  restore_pup_dirs
  copy_new_vpx_logs "$pass_dir/vpx-logs" "$baseline_file"

  elapsed=$(( $(date +%s) - start_epoch ))
  fatal_log_matches "$pass_dir" >"$fatal_file"
  pf_activity="$(screen_activity_count "$snap_dir" playfield)"
  bg_activity="$(screen_activity_count "$snap_dir" backglass)"
  dmd_activity="$(screen_activity_count "$snap_dir" fulldmd)"
  pf_luma="$(screen_max_luma "$snap_dir" playfield)"
  bg_luma="$(screen_max_luma "$snap_dir" backglass)"
  dmd_luma="$(screen_max_luma "$snap_dir" fulldmd)"
  snapshot_count="$(find "$snap_dir" -type f -name '*.jpg' | wc -l)"

  {
    printf 'Mode=%s\nPassage=%s\nDurée=%s\nArrêtPrécoce=%s\n' "$mode" "$pass" "$elapsed" "$ended_early"
    printf 'Snapshots=%s\nPlayfieldImagesUniques=%s\nBackglassImagesUniques=%s\nFullDMDImagesUniques=%s\n' "$snapshot_count" "$pf_activity" "$bg_activity" "$dmd_activity"
    printf 'PlayfieldLumaMax=%s\nBackglassLumaMax=%s\nFullDMDLumaMax=%s\n' "$pf_luma" "$bg_luma" "$dmd_luma"
    printf 'ErreursFatales=%s\n' "$(wc -l <"$fatal_file")"
  } >"$result_file"

  local pass_status="PASS"
  if (( ended_early == 1 )) || (( elapsed < minimum_healthy )); then
    pass_status="FAIL"
    add_failure "$TABLE_STEM [$mode passage $pass] arrêt prématuré après ${elapsed}s"
  fi
  if [[ -s "$fatal_file" ]]; then
    pass_status="FAIL"
    add_failure "$TABLE_STEM [$mode passage $pass] erreur(s) fatale(s) détectée(s)"
  fi
  if (( snapshot_count < 4 )); then
    pass_status="WARN"
    add_warning "$TABLE_STEM [$mode passage $pass] snapshots incomplets"
  fi
  if (( pf_activity < 2 )); then
    [[ "$pass_status" == PASS ]] && pass_status="WARN"
    add_warning "$TABLE_STEM [$mode passage $pass] aucune activité visuelle prouvée sur le playfield"
  fi
  pf_visible=0; bg_visible=0; dmd_visible=0
  (( pf_activity >= 2 || pf_luma >= 3 )) && pf_visible=1
  (( bg_activity >= 2 || bg_luma >= 3 )) && bg_visible=1
  (( dmd_activity >= 2 || dmd_luma >= 3 )) && dmd_visible=1

  if [[ "$mode" == rom && "$ROM_EXPECTED" == 1 ]]; then
    if (( ROM_OK == 0 )); then
      pass_status="FAIL"
    fi
    if (( dmd_visible == 0 )); then
      pass_status="FAIL"
      add_failure "$TABLE_STEM [rom passage $pass] aucun DMD visible sur le FullDMD"
    elif (( dmd_activity < 2 )); then
      [[ "$pass_status" == PASS ]] && pass_status="WARN"
      add_warning "$TABLE_STEM [rom passage $pass] FullDMD visible mais activité DMD non prouvée"
    fi
  fi

  if [[ "$mode" == pup ]]; then
    if (( ROM_EXPECTED == 1 )); then
      if (( dmd_visible == 0 )); then
        pass_status="FAIL"
        add_failure "$TABLE_STEM [pup passage $pass] ROM+PuP: DMD absent du FullDMD"
      fi
      if (( bg_visible == 0 )); then
        pass_status="FAIL"
        add_failure "$TABLE_STEM [pup passage $pass] ROM+PuP: vidéo PuP absente du Backglass"
      elif (( bg_activity < 2 )); then
        [[ "$pass_status" == PASS ]] && pass_status="WARN"
        add_warning "$TABLE_STEM [pup passage $pass] Backglass visible mais animation PuP non prouvée"
      fi
    else
      if (( dmd_visible == 0 )); then
        pass_status="FAIL"
        add_failure "$TABLE_STEM [pup passage $pass] PuP seul: contenu absent du FullDMD"
      elif (( dmd_activity < 2 )); then
        [[ "$pass_status" == PASS ]] && pass_status="WARN"
        add_warning "$TABLE_STEM [pup passage $pass] PuP FullDMD visible mais animation non prouvée"
      fi
    fi
  fi

  printf 'Résultat passage : %s | PF uniques=%s | BG uniques=%s | FullDMD uniques=%s | luma=%s/%s/%s\n'     "$pass_status" "$pf_activity" "$bg_activity" "$dmd_activity" "$pf_luma" "$bg_luma" "$dmd_luma"
  printf '%s\n' "$pass_status" >"$pass_dir/status"
}

printf '\n%s\n' '--- 5. Tests VPX réels — deux passages par mode ---'
if ((${#FAILURES[@]} == 0)); then
  for mode in "${MODES[@]}"; do
    run_one_pass "$mode" 1
    sleep 5
    run_one_pass "$mode" 2
    sleep 5
  done
else
  printf 'TESTS NON LANCÉS: le prévol contient déjà une erreur bloquante.\n'
fi

if ! restore_vpinfe; then
  add_failure "Échec de restauration de VPinFE"
fi

printf '\n%s\n' '--- 6. Résumé de certification automatisée ---'
MODE_FAILURE=0
MODE_WARNING=0
for mode in "${MODES[@]}"; do
  s1="$(cat "$RUNTIME_ROOT/$mode/pass-1/status" 2>/dev/null || echo NOTRUN)"
  s2="$(cat "$RUNTIME_ROOT/$mode/pass-2/status" 2>/dev/null || echo NOTRUN)"
  printf '%-10s : passage 1=%-7s passage 2=%-7s\n' "$mode" "$s1" "$s2"
  [[ "$s1" == FAIL || "$s2" == FAIL || "$s1" == NOTRUN || "$s2" == NOTRUN ]] && MODE_FAILURE=1
  [[ "$s1" == WARN || "$s2" == WARN ]] && MODE_WARNING=1
done

FINAL_STATUS="CERTIFIÉ_AUTOMATISÉ"
EXIT_CODE=0
if (( MODE_FAILURE == 1 || ${#FAILURES[@]} > 0 )); then
  FINAL_STATUS="ÉCHEC"
  EXIT_CODE=2
elif (( MODE_WARNING == 1 || ${#WARNINGS[@]} > 0 )); then
  FINAL_STATUS="À VÉRIFIER"
  EXIT_CODE=1
fi

printf '\nÉTAT FINAL : %s\n' "$FINAL_STATUS"
printf 'Fin        : %s\n' "$(now_iso)"

printf '\n[CE QUI PASSE]\n'
if ((${#PASSES[@]})); then printf 'GO [√] %s\n' "${PASSES[@]}"; else printf '(aucun élément statique confirmé)\n'; fi
printf '\n[AVERTISSEMENTS]\n'
if ((${#WARNINGS[@]})); then printf 'WARN [!] %s\n' "${WARNINGS[@]}"; else printf '(aucun)\n'; fi
printf '\n[CE QUI MANQUE / ÉCHECS]\n'
if ((${#FAILURES[@]})); then printf 'ERREUR [x] %s\n' "${FAILURES[@]}"; else printf '(aucun)\n'; fi

printf '\nEmplacements:\n'
printf '  Rapport complet : %s\n' "$REPORT"
printf '  Analyse statique : %s\n' "$ANALYSIS"
printf '  Journaux runtime : %s\n' "$RUNTIME_ROOT"
printf '  Snapshots        : %s\n' "$SNAP_ROOT"
printf '\nNOTE: ce test certifie le chargement, la stabilité observée, les dépendances détectables,\n'
printf 'les deux démarrages via la configuration VPinFE et l’activité visuelle. Il ne peut pas prouver automatiquement\n'
printf 'chaque mission, switch, multiball ou règle de jeu interne sans scénario propre à la table.\n'

if [[ "$(id -u)" -eq 0 ]] && id "$TEST_USER" >/dev/null 2>&1; then
  chown -R "$TEST_USER":"$(id -gn "$TEST_USER")" "$LOG_DIR" 2>/dev/null || true
  [[ -e "$VBS" ]] && chown "$TEST_USER":"$(id -gn "$TEST_USER")" "$VBS" 2>/dev/null || true
fi

exit "$EXIT_CODE"
