#!/usr/bin/env bash
set -Eeuo pipefail

MODE="${1:-}"
# PINCABOS_PROFILE_GC_ASYNC_V1 : chemins surchargeables pour les tests
PROFILE_ROOT="${PINCABOS_VPINFE_PROFILE_ROOT:-/var/tmp/pincabos-vpinfe}"
TMP_DIR="${PINCABOS_VPINFE_TMP:-/tmp}"
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
    *"--user-data-dir=${TMP_DIR}/vpinfe_chromium_"*) return 0 ;;
    *"--user-data-dir=${PROFILE_ROOT}/vpinfe_chromium_"*) return 0 ;;
    *) return 1 ;;
  esac
}

target_pids() {
  local proc pid

  # pgrep restreint aux processus « chrome » : le balayage bash de tout /proc
  # (deux lectures par processus, repete a chaque attente) coutait ~1 s au boot.
  for pid in $(pgrep -x chrome 2>/dev/null || true); do
    is_vpinfe_chrome "$pid" && printf '%s\n' "$pid"
  done | sort -nu
}

gc_async() {
  # PINCABOS_PROFILE_GC_ASYNC_V1 : renommer (instantane, sort du motif
  # vpinfe_chromium_*) puis supprimer en arriere-plan, hors du cgroup du
  # service, en priorite E/S « idle ». PINCABOS_GC_SYNC=1 (tests, systeme
  # sans systemd-run) supprime en ligne.
  local dir="$1" rebut
  rebut="$(dirname -- "$dir")/.gc-$(basename -- "$dir")-$$-$RANDOM"
  mv -- "$dir" "$rebut" 2>/dev/null || rebut="$dir"
  if [ "${PINCABOS_GC_SYNC:-0}" = "1" ] || ! command -v systemd-run >/dev/null 2>&1; then
    rm -rf --one-file-system -- "$rebut"
    return 0
  fi
  systemd-run --quiet --collect --no-block \
    --unit="pincabos-vpinfe-gc-$(date +%s%N)-$RANDOM" \
    --nice=19 --property=IOSchedulingClass=idle \
    /bin/rm -rf --one-file-system -- "$rebut" >/dev/null 2>&1 \
    || rm -rf --one-file-system -- "$rebut"
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
  local root dir realdir rebut

  for root in "$TMP_DIR" "$PROFILE_ROOT"; do
    [ -d "$root" ] || continue

    shopt -s nullglob
    # rebuts d'une suppression interrompue (coupure de courant) : on reprend
    for rebut in "$root"/.gc-vpinfe_chromium_*; do
      [ -d "$rebut" ] || continue
      echo "REBUT REPRIS : $rebut"
      gc_async "$rebut"
    done
    for dir in "$root"/vpinfe_chromium_*; do
      [ -d "$dir" ] || continue
      [ ! -L "$dir" ] || continue

      realdir="$(readlink -f -- "$dir" 2>/dev/null || true)"

      case "$realdir" in
        "$TMP_DIR"/vpinfe_chromium_*|"$PROFILE_ROOT"/vpinfe_chromium_*) ;;
        *) continue ;;
      esac

      # Un profil ferme pese des centaines de Mo (401 Mo mesures) : le
      # supprimer en ligne coutait 3,4 s a chaque demarrage du frontend.
      echo "PROFIL FERME MIS AU REBUT : $realdir (suppression en arriere-plan)"
      gc_async "$realdir"
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
