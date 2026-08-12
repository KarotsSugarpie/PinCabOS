#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

TABLES_ROOT="${PINCAB_TABLES_ROOT:-/home/pinball/Tables}"
MODE="${1:---audit}"
STOP_FILE="/var/lib/pincabos-tabletest/STOP"

human_total() {
  local pattern="$1"
  local total
  total="$(find "$TABLES_ROOT" -type f -path "$pattern" -printf '%s\n' 2>/dev/null | awk '{s+=$1} END {printf "%.0f", s+0}')"
  numfmt --to=iec-i --suffix=B "${total:-0}" 2>/dev/null || printf '%s bytes\n' "${total:-0}"
}

count_files() {
  find "$TABLES_ROOT" -type f -path "$1" -printf '.' 2>/dev/null | wc -c
}

stop_tests() {
  mkdir -p "$(dirname "$STOP_FILE")"
  touch "$STOP_FILE"
  systemctl stop pincabos-alltabletest.service 2>/dev/null || true
  sleep 2
}

active_tests() {
  pgrep -af '/opt/pincabos/scripts/(alltabletest|tabletest)\.sh|VPinballX_(BGFX|GL)|/VPinballX([[:space:]]|$)' 2>/dev/null || true
}

printf '===============================================================\n'
printf ' PINCABOS — AUDIT ESPACE TABLETEST\n'
printf '===============================================================\n'
printf 'Racine tables : %s\n' "$TABLES_ROOT"
printf 'Mode           : %s\n\n' "$MODE"

df -hT -- "$TABLES_ROOT"
printf '\nSnapshots générés : %s fichier(s), %s\n' "$(count_files '*/logs/snapshots/*')" "$(human_total '*/logs/snapshots/*')"
printf 'Runtime généré   : %s fichier(s), %s\n' "$(count_files '*/logs/runtime/*')" "$(human_total '*/logs/runtime/*')"
printf 'Backups prélaunch: '
du -sh /root/pincabos-native-b2s-prelaunch-backups 2>/dev/null || printf 'absent\n'
printf '\nProcessus de test actifs :\n'
ACTIVE="$(active_tests)"
if [[ -n "$ACTIVE" ]]; then printf '%s\n' "$ACTIVE"; else printf '(aucun)\n'; fi

case "$MODE" in
  --audit)
    printf '\nAucune suppression effectuée.\n'
    printf 'Pour supprimer uniquement les captures générées : %s --apply\n' "$0"
    printf 'Pour supprimer captures + journaux runtime générés : %s --deep\n' "$0"
    ;;
  --apply|--deep)
    stop_tests
    ACTIVE="$(active_tests)"
    if [[ -n "$ACTIVE" ]]; then
      printf '\nERREUR: un test ou VPX est encore actif. Attendez sa fermeture puis relancez.\n%s\n' "$ACTIVE" >&2
      exit 75
    fi
    printf '\nSuppression des dossiers logs/snapshots générés...\n'
    while IFS= read -r -d '' dir; do rm -rf -- "$dir"; done < <(
      find "$TABLES_ROOT" -type d -path '*/logs/snapshots' -prune -print0 2>/dev/null
    )
    if [[ "$MODE" == "--deep" ]]; then
      printf 'Suppression des dossiers logs/runtime générés...\n'
      while IFS= read -r -d '' dir; do rm -rf -- "$dir"; done < <(
        find "$TABLES_ROOT" -type d -path '*/logs/runtime' -prune -print0 2>/dev/null
      )
    fi
    sync
    printf '\nÉtat disque après nettoyage :\n'
    df -hT -- "$TABLES_ROOT"
    printf '\nGO [√] Rapports *-report.txt et analyses *-analysis.txt conservés.\n'
    ;;
  *)
    printf 'Usage: %s --audit|--apply|--deep\n' "$0" >&2
    exit 64
    ;;
esac
