#!/usr/bin/env bash
# PINCABOS_NATIVE_FULLDMD_POLICY_BEGIN
if [[ -x '/opt/pincabos/bin/pincabos-native-fulldmd-policy.sh' ]]; then
    '/opt/pincabos/bin/pincabos-native-fulldmd-policy.sh' "$@" || true
fi
# PINCABOS_NATIVE_FULLDMD_POLICY_END
# PINCABOS_FULLDMD_AUTOARRANGE_V2_WRAPPER
# Le lanceur productif VPinFE reste la base. Cette couche synchronise
# seulement les valeurs ScoreView du layout FullDMD AVANT VPX.

set -Eeuo pipefail
IFS=$'\n\t'

BASE='/opt/pincabos/bin/vpx-lowlatency.sh.pincabos-fulldmd-base'
HELPER='/opt/pincabos/bin/pincabos-fulldmd-write-scoreview-ini.py'

table=''
for arg in "$@"; do
  case "${arg,,}" in
    *.vpx) table="$arg" ;;
  esac
done

if [ -n "$table" ] && [ -r "$table" ]; then
  table_dir="$(dirname -- "$table")"
  layout="${table_dir}/fulldmd/PinCabOS-DMD-layout.env"
  if [ -r "$layout" ] && [ -x "$HELPER" ]; then
    get_value() {
      awk -F= -v key="$2" '$1 == key { gsub(/\r/, "", $2); print $2; exit }' "$1"
    }
    x="$(get_value "$layout" PINCABOS_DMD_X)"
    y="$(get_value "$layout" PINCABOS_DMD_Y)"
    w="$(get_value "$layout" PINCABOS_DMD_W)"
    h="$(get_value "$layout" PINCABOS_DMD_H)"
    if [[ "$x" =~ ^-?[0-9]+$ && "$y" =~ ^-?[0-9]+$ && "$w" =~ ^[1-9][0-9]*$ && "$h" =~ ^[1-9][0-9]*$ ]]; then
      table_ini="${table%.*}.ini"
      "$HELPER" --ini "$table_ini" --x "$x" --y "$y" --width "$w" --height "$h" >&2 || true
    fi
  fi
fi

exec "$BASE" "$@"
