#!/usr/bin/env bash
set -Eeuo pipefail

MODE="${1:-}"
PROFILE_ROOT="/var/tmp/pincabos-vpinfe"
PINBALL_UID="1000"
PINBALL_USER="pinball"
RUNTIME_DIR="/run/user/${PINBALL_UID}"
USER_BUS="unix:path=${RUNTIME_DIR}/bus"

case "$MODE" in
  prestart|poststop) ;;
  *)
    echo "ERREUR : mode invalide : $MODE"
    exit 2
    ;;
esac

is_vpinfe_chrome() {
  local pid="$1"
  local comm cmd

  [ -r "/proc/$pid/comm" ] || return 1
  comm="$(cat "/proc/$pid/comm" 2>/dev/null || true)"
  [ "$comm" = "chrome" ] || return 1

  cmd="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"

  case "$cmd" in
    *"--user-data-dir=/tmp/vpinfe_chromium_"*) return 0 ;;
    *"--user-data-dir=${PROFILE_ROOT}/vpinfe_chromium_"*) return 0 ;;
    *) return 1 ;;
  esac
}

target_pids() {
  local proc pid

  for proc in /proc/[0-9]*; do
    pid="${proc##*/}"
    is_vpinfe_chrome "$pid" && printf '%s\n' "$pid"
  done | sort -nu
}

scope_for_pid() {
  local pid="$1"

  awk -F/ '
    /app-com\.google\.Chrome-[0-9]+\.scope$/ {
      print $NF
      exit
    }
  ' "/proc/$pid/cgroup" 2>/dev/null || true
}

wait_until_gone() {
  local loops="$1"
  local i
  local -a pids=()

  for ((i=1; i<=loops; i++)); do
    mapfile -t pids < <(target_pids || true)

    [ "${#pids[@]}" -eq 0 ] && return 0
    sleep 1
  done

  return 1
}

stop_scopes() {
  local -a pids=()
  local pid scope
  declare -A seen=()

  mapfile -t pids < <(target_pids || true)

  for pid in "${pids[@]}"; do
    scope="$(scope_for_pid "$pid")"
    [ -n "$scope" ] || continue
    [ -n "${seen[$scope]+x}" ] && continue
    seen["$scope"]=1

    echo "ARRET SCOPE : $scope"

    runuser -u "$PINBALL_USER" -- \
      env XDG_RUNTIME_DIR="$RUNTIME_DIR" \
      DBUS_SESSION_BUS_ADDRESS="$USER_BUS" \
      timeout 8 systemctl --user stop "$scope" \
      >/dev/null 2>&1 || true
  done
}

signal_remaining() {
  local signal="$1"
  local -a pids=()

  mapfile -t pids < <(target_pids || true)

  [ "${#pids[@]}" -eq 0 ] && return 0

  echo "SIGNAL $signal : ${pids[*]}"
  kill "-$signal" "${pids[@]}" 2>/dev/null || true
}

cleanup_profiles() {
  local root dir realdir

  for root in /tmp "$PROFILE_ROOT"; do
    [ -d "$root" ] || continue

    shopt -s nullglob
    for dir in "$root"/vpinfe_chromium_*; do
      [ -d "$dir" ] || continue
      [ ! -L "$dir" ] || continue

      realdir="$(readlink -f -- "$dir" 2>/dev/null || true)"

      case "$realdir" in
        /tmp/vpinfe_chromium_*|"$PROFILE_ROOT"/vpinfe_chromium_*) ;;
        *) continue ;;
      esac

      echo "SUPPRIME PROFIL FERME : $realdir"
      rm -rf --one-file-system -- "$realdir"
    done
  done
}

echo "=== VPinFE Chrome scope cleanup : $MODE ==="

stop_scopes
wait_until_gone 5 || true

signal_remaining TERM
wait_until_gone 5 || true

if ! wait_until_gone 1; then
  signal_remaining KILL
  wait_until_gone 3 || true
fi

mapfile -t LEFT < <(target_pids || true)

if [ "${#LEFT[@]}" -ne 0 ]; then
  echo "ERREUR : Chrome VPinFE encore presents : ${LEFT[*]}"
  echo "Les profils ne sont pas supprimes par securite."
  exit 1
fi

cleanup_profiles

echo "VPinFE Chrome scope cleanup : termine"
