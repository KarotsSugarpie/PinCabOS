#!/usr/bin/env bash
# PinCabOS - Test séquentiel de toutes les tables VPX
# Installez dans: /opt/pincabos/scripts/alltabletest.sh

set -Eeuo pipefail
IFS=$'\n\t'
umask 022

SCRIPT_VERSION="1.1.5"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TABLETEST="${PINCAB_TABLETEST_SCRIPT:-$SCRIPT_DIR/tabletest.sh}"
TABLES_ROOT="${PINCAB_TABLES_ROOT:-/home/pinball/Tables}"
SECONDS_PER_PASS="${PINCAB_TEST_RUN_SECONDS:-120}"
MODE="auto"
LAUNCHER="vpinfe"
STOP_ON_FAILURE=0
RESUME=1
STATE_DIR="${PINCAB_ALLTEST_STATE_DIR:-/var/lib/pincabos-tabletest}"
MASTER_LOG="${PINCAB_ALLTEST_MASTER_LOG:-/var/log/pincabos/alltabletest.log}"
SUMMARY="${PINCAB_ALLTEST_SUMMARY:-/var/log/pincabos/alltabletest-summary.txt}"
TEST_USER="${PINCAB_TEST_USER:-pinball}"
VPINFE_SERVICE_REQUESTED="${PINCAB_VPINFE_SERVICE:-}"
VPINFE_SERVICE_RESOLVED=""
VPINFE_WAS_ACTIVE=0
VPINFE_RUNTIME_MASK_APPLIED=0
VPINFE_RESTORE_DONE=0
VPINFE_INI_RESOLVED="${PINCAB_VPINFE_INI:-}"
MIN_FREE_GIB="${PINCAB_TEST_MIN_FREE_GIB:-50}"
[[ "$MIN_FREE_GIB" =~ ^[0-9]+$ ]] || MIN_FREE_GIB=50

usage() {
  cat <<USAGE
PinCabOS alltabletest.sh v${SCRIPT_VERSION}

Usage: alltabletest.sh [options]

Options:
  --tables-root CHEMIN
  --seconds N
  --mode auto|native|rom|pup
  --launcher vpinfe|auto|normal|lowlatency
  --restart                 Recommencer depuis la première table
  --stop-on-failure
  --help

Les tables sont testées une à la fois. Chaque table écrit dans:
  Tables/<dossier de la table>/logs/
USAGE
}

vpinfe_pids() {
  pgrep -u "$TEST_USER" -f '(^|/)(vpinfe)([[:space:]]|$)|vpinfe/.+main\.py' 2>/dev/null || true
}

detect_vpinfe_ini() {
  local home_dir candidate pid config_dir
  home_dir="$(getent passwd "$TEST_USER" | cut -d: -f6)"
  if [[ -n "$VPINFE_INI_RESOLVED" && -r "$VPINFE_INI_RESOLVED" ]]; then
    readlink -f -- "$VPINFE_INI_RESOLVED"
    return 0
  fi
  while IFS= read -r pid; do
    [[ -r "/proc/$pid/environ" ]] || continue
    config_dir="$(tr '\0' '\n' <"/proc/$pid/environ" 2>/dev/null | sed -n 's/^VPINFE_CONFIG_DIR=//p' | head -n1)"
    [[ -n "$config_dir" && -r "$config_dir/vpinfe.ini" ]] && { readlink -f -- "$config_dir/vpinfe.ini"; return 0; }
  done < <(vpinfe_pids)
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

prepare_vpinfe_for_all_tests() {
  printf '%s\n' '--- Isolation globale de VPinFE ---'
  [[ "$(id -u)" -eq 0 ]] || { printf 'ERREUR: lance alltabletest.sh avec sudo pour arrêter VPinFE.\n' >&2; return 1; }
  VPINFE_INI_RESOLVED="$(detect_vpinfe_ini || true)"
  printf 'VPinFE INI     : %s\n' "${VPINFE_INI_RESOLVED:-non détecté}"
  VPINFE_SERVICE_RESOLVED="$(detect_vpinfe_service || true)"
  if [[ -n "$VPINFE_SERVICE_RESOLVED" ]]; then
    systemctl is-active --quiet "$VPINFE_SERVICE_RESOLVED" 2>/dev/null && VPINFE_WAS_ACTIVE=1 || true
    printf 'Service VPinFE : %s\n' "$VPINFE_SERVICE_RESOLVED"
    printf 'État initial    : %s\n' "$([[ "$VPINFE_WAS_ACTIVE" == 1 ]] && echo actif || echo inactif)"
    systemctl stop "$VPINFE_SERVICE_RESOLVED" || return 1
    VPINFE_ENABLE_STATE="$(systemctl is-enabled "$VPINFE_SERVICE_RESOLVED" 2>/dev/null || true)"
    if [[ "$VPINFE_ENABLE_STATE" != masked* ]]; then
      systemctl mask --runtime "$VPINFE_SERVICE_RESOLVED" >/dev/null 2>&1 || return 1
      VPINFE_RUNTIME_MASK_APPLIED=1
    fi
  elif [[ -n "$(vpinfe_pids)" ]]; then
    printf 'ERREUR: processus VPinFE actif, mais service systemd introuvable. Définis PINCAB_VPINFE_SERVICE.\n' >&2
    return 1
  else
    printf 'INFO: aucun VPinFE actif détecté.\n'
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
    printf 'ERREUR: VPinFE est encore actif; aucun test ne sera lancé.\n' >&2
    return 1
  fi
  printf 'GO [√] VPinFE arrêté et masqué pendant toute la campagne.\n\n'
}

restore_vpinfe_after_all_tests() {
  [[ "$VPINFE_RESTORE_DONE" == 0 ]] || return 0
  VPINFE_RESTORE_DONE=1
  [[ -n "$VPINFE_SERVICE_RESOLVED" ]] || return 0
  printf '\n--- Restauration globale de VPinFE ---\n'
  if [[ "$VPINFE_RUNTIME_MASK_APPLIED" == 1 ]]; then
    systemctl unmask --runtime "$VPINFE_SERVICE_RESOLVED" >/dev/null 2>&1 || true
  fi
  if [[ "$VPINFE_WAS_ACTIVE" == 1 ]]; then
    systemctl start "$VPINFE_SERVICE_RESOLVED"
    if systemctl is-active --quiet "$VPINFE_SERVICE_RESOLVED"; then
      printf 'GO [√] VPinFE relancé: %s\n' "$VPINFE_SERVICE_RESOLVED"
    else
      printf 'ERREUR [x] VPinFE n’a pas pu être relancé: %s\n' "$VPINFE_SERVICE_RESOLVED" >&2
      return 1
    fi
  else
    printf 'INFO [i] VPinFE était déjà arrêté avant le lot; il reste arrêté.\n'
  fi
}

cleanup_alltabletest() {
  restore_vpinfe_after_all_tests || true
}
trap cleanup_alltabletest EXIT
trap 'exit 130' INT TERM HUP

while (($#)); do
  case "$1" in
    --tables-root) TABLES_ROOT="${2:-}"; shift 2 ;;
    --seconds) SECONDS_PER_PASS="${2:-}"; shift 2 ;;
    --mode) MODE="${2:-}"; shift 2 ;;
    --launcher) LAUNCHER="${2:-}"; shift 2 ;;
    --restart) RESUME=0; shift ;;
    --stop-on-failure) STOP_ON_FAILURE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'Option inconnue: %s\n' "$1" >&2; usage; exit 64 ;;
  esac
done

[[ "$SECONDS_PER_PASS" =~ ^[0-9]+$ ]] || { printf 'ERREUR: --seconds doit être numérique.\n' >&2; exit 64; }
[[ -x "$TABLETEST" ]] || { printf 'ERREUR: tabletest.sh absent/non exécutable: %s\n' "$TABLETEST" >&2; exit 66; }
[[ -d "$TABLES_ROOT" ]] || { printf 'ERREUR: racine des tables absente: %s\n' "$TABLES_ROOT" >&2; exit 66; }

mkdir -p -- "$STATE_DIR" "$(dirname "$MASTER_LOG")" "$(dirname "$SUMMARY")"
LOCK_FILE="$STATE_DIR/alltabletest.lock"
QUEUE_FILE="$STATE_DIR/queue.txt"
DONE_FILE="$STATE_DIR/done.txt"
CURRENT_FILE="$STATE_DIR/current.txt"
STOP_FILE="$STATE_DIR/STOP"
exec 9>"$LOCK_FILE"
flock -n 9 || { printf 'ERREUR: alltabletest.sh est déjà actif.\n' >&2; exit 75; }
rm -f -- "$STOP_FILE"

if (( RESUME == 0 )); then
  : >"$DONE_FILE"
fi
touch "$DONE_FILE"

# Reconstruire la file à chaque démarrage pour inclure les nouvelles tables,
# mais ignorer les tables déjà terminées lorsque --restart n'est pas utilisé.
find "$TABLES_ROOT" -type f -iname '*.vpx' \
  -not -path '*/logs/*' \
  -not -path '*/cache/*' \
  -not -path '*/backup*/*' \
  -not -path '*/backups/*' \
  -print0 | sort -z | tr '\0' '\n' >"$QUEUE_FILE"

TOTAL="$(wc -l <"$QUEUE_FILE")"
DONE_COUNT=0
PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0
START_EPOCH="$(date +%s)"

exec > >(tee -a "$MASTER_LOG") 2>&1

printf '===============================================================\n'
printf ' PINCABOS — TEST AUTOMATISÉ DE TOUTES LES TABLES\n'
printf '===============================================================\n'
printf 'Version       : %s\n' "$SCRIPT_VERSION"
printf 'Début         : %s\n' "$(date --iso-8601=seconds)"
printf 'Racine        : %s\n' "$TABLES_ROOT"
printf 'Tables        : %s\n' "$TOTAL"
printf 'Deux passages : oui, pour chaque mode détecté\n'
printf 'Launcher       : configuration VPinFE (vpinfe.ini + altlauncher)\n'
printf 'Durée/passage: %ss\n' "$SECONDS_PER_PASS"
printf 'Seuil disque   : arrêt sous %s GiB libres\n' "$MIN_FREE_GIB"
printf 'Résumé global : %s\n\n' "$SUMMARY"

if ! prepare_vpinfe_for_all_tests; then
  printf 'ÉCHEC: impossible d’isoler VPinFE; campagne annulée.\n'
  exit 2
fi

is_done() { grep -Fxq -- "$1" "$DONE_FILE" 2>/dev/null; }

free_gib() {
  df -Pk -- "$TABLES_ROOT" 2>/dev/null | awk 'NR==2 {printf "%d\n", $4/1024/1024}'
}

index=0
while IFS= read -r table; do
  [[ -n "$table" ]] || continue
  index=$((index + 1))
  if [[ -e "$STOP_FILE" ]]; then
    printf 'ARRÊT demandé par %s\n' "$STOP_FILE"
    break
  fi
  if (( RESUME == 1 )) && is_done "$table"; then
    SKIP_COUNT=$((SKIP_COUNT + 1))
    continue
  fi

  FREE_GIB_NOW="$(free_gib || echo 0)"
  [[ "$FREE_GIB_NOW" =~ ^[0-9]+$ ]] || FREE_GIB_NOW=0
  if (( FREE_GIB_NOW < MIN_FREE_GIB )); then
    printf 'ARRÊT DE SÉCURITÉ: seulement %s GiB libres; minimum configuré=%s GiB.\n' "$FREE_GIB_NOW" "$MIN_FREE_GIB"
    printf 'Nettoyez les snapshots avec /opt/pincabos/scripts/cleanup-tabletest-storage.sh --apply.\n'
    break
  fi

  printf '%s\n' "$table" >"$CURRENT_FILE"
  printf '\n===============================================================\n'
  printf ' TABLE %s/%s\n' "$index" "$TOTAL"
  printf ' %s\n' "$table"
  printf '===============================================================\n'

  set +e
  env PINCAB_VPINFE_MANAGED_EXTERNALLY=1 \
      PINCAB_VPINFE_SERVICE="$VPINFE_SERVICE_RESOLVED" \
      PINCAB_VPINFE_INI="$VPINFE_INI_RESOLVED" \
      "$TABLETEST" --tables-root "$TABLES_ROOT" --seconds "$SECONDS_PER_PASS" --mode "$MODE" --launcher "$LAUNCHER" "$table"
  rc=$?
  set -e

  case "$rc" in
    0) PASS_COUNT=$((PASS_COUNT + 1)); state="CERTIFIÉ_AUTOMATISÉ" ;;
    1) WARN_COUNT=$((WARN_COUNT + 1)); state="À VÉRIFIER" ;;
    *) FAIL_COUNT=$((FAIL_COUNT + 1)); state="ÉCHEC" ;;
  esac
  printf '%s\n' "$table" >>"$DONE_FILE"
  DONE_COUNT=$((DONE_COUNT + 1))

  {
    printf 'Dernière mise à jour : %s\n' "$(date --iso-8601=seconds)"
    printf 'Total détecté       : %s\n' "$TOTAL"
    printf 'Traitées cette passe: %s\n' "$DONE_COUNT"
    printf 'Déjà ignorées/reprise: %s\n' "$SKIP_COUNT"
    printf 'Certifiées          : %s\n' "$PASS_COUNT"
    printf 'À vérifier          : %s\n' "$WARN_COUNT"
    printf 'Échecs              : %s\n' "$FAIL_COUNT"
    printf 'Table courante      : %s\n' "$table"
    printf 'Dernier résultat    : %s\n' "$state"
    printf 'Temps écoulé        : %ss\n' "$(( $(date +%s) - START_EPOCH ))"
  } >"$SUMMARY"

  if (( STOP_ON_FAILURE == 1 && rc >= 2 )); then
    printf 'ARRÊT: --stop-on-failure demandé.\n'
    break
  fi
  sleep 5
done <"$QUEUE_FILE"

rm -f -- "$CURRENT_FILE"
VPINFE_RESTORE_ERROR=0
restore_vpinfe_after_all_tests || VPINFE_RESTORE_ERROR=1
{
  printf '===============================================================\n'
  printf ' PINCABOS — RÉSUMÉ FINAL ALLTABLETEST\n'
  printf '===============================================================\n'
  printf 'Fin                  : %s\n' "$(date --iso-8601=seconds)"
  printf 'Total détecté        : %s\n' "$TOTAL"
  printf 'Traitées cette passe : %s\n' "$DONE_COUNT"
  printf 'Ignorées (déjà faites): %s\n' "$SKIP_COUNT"
  printf 'Certifiées           : %s\n' "$PASS_COUNT"
  printf 'À vérifier           : %s\n' "$WARN_COUNT"
  printf 'Échecs               : %s\n' "$FAIL_COUNT"
  printf 'Durée totale         : %ss\n' "$(( $(date +%s) - START_EPOCH ))"
  printf '\nChaque résultat détaillé est dans Tables/<dossier table>/logs/.\n'
} | tee "$SUMMARY"

(( VPINFE_RESTORE_ERROR == 0 )) || exit 2
(( FAIL_COUNT == 0 )) || exit 2
(( WARN_COUNT == 0 )) || exit 1
exit 0
