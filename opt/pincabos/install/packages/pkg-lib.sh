#!/usr/bin/env bash
# PINCABOS_SCRIPT_MODES="default explicit-via-PINCABOS_EXPLICIT=1"
# Created by Karots Sugarpie
# PINCABOS_SCRIPT_NAME="pkg-lib.sh"
# PINCABOS_SCRIPT_ROLE="Shared helper library for PinCabOS package installers"
# PINCABOS_SCRIPT_REQUIRES_COMMANDS="bash apt-get apt-cache dpkg date tee grep awk sed command"
# PINCABOS_SCRIPT_LOG_DIR="/opt/pincabos/logs"
# PINCABOS_SCRIPT_MANIFEST="/opt/pincabos/install/install.json"

set -Eeuo pipefail

ORANGE="\033[38;5;208m"
CYAN="\033[36m"
GREEN="\033[32m"
RED="\033[31m"
YELLOW="\033[33m"
BLUE="\033[34m"
DIM="\033[2m"
NC="\033[0m"

PKG_NAME="${PKG_NAME:-$(basename "$0" .sh)}"
LOG_DIR="/opt/pincabos/logs"
LOG_FILE="${LOG_FILE:-$LOG_DIR/${PKG_NAME}-$(date +%Y%m%d-%H%M%S).log}"
CURRENT_STEP="init"

mkdir -p "$LOG_DIR"

pco_title() {
  echo -e "${CYAN}────────────────────────────────────────────────────────────────${NC}"
  echo -e "${ORANGE} PinCabOS Package - ${PKG_TITLE:-$PKG_NAME}${NC}"
  echo -e "${CYAN}────────────────────────────────────────────────────────────────${NC}"
  echo -e "${DIM}Log: $LOG_FILE${NC}"
}

pco_step() {
  CURRENT_STEP="$1 - $2"
  echo
  echo -e "${CYAN}─[$1]─► ${ORANGE}$2${CYAN} ◄────────────────────────────────────────${NC}"
}

pco_go() { echo -e "${GREEN}GO [√]${NC} $*"; }
pco_warn() { echo -e "${YELLOW}WARN${NC} $*"; }
pco_info() { echo -e "${BLUE}INFO${NC} $*"; }
pco_nogo() {
  local ref="$1"
  shift
  echo -e "${RED}NOGO [***] ${ref}${NC} $*"
  echo -e "${RED}Log:${NC} $LOG_FILE"
  exit 1
}

pco_on_error() {
  local rc="$?"
  echo
  echo -e "${RED}NOGO [***] ERR-${PKG_NAME^^}-UNHANDLED-999${NC} Unexpected failure"
  echo -e "${RED}Step:${NC} $CURRENT_STEP"
  echo -e "${RED}Exit code:${NC} $rc"
  echo -e "${RED}Log:${NC} $LOG_FILE"
  exit "$rc"
}

trap pco_on_error ERR

run_spin() {
  local label="$1"
  shift

  if [ "${PINCABOS_EXPLICIT:-0}" = "1" ]; then
    echo
    echo -e "${CYAN}${label}${NC}"
    echo -e "${YELLOW}Explicit mode:${NC} running command with full output"
    echo "+ $*"
    "$@" 2>&1 | tee -a "$LOG_FILE"
    local rc="${PIPESTATUS[0]}"
    if [ "$rc" -eq 0 ]; then
      echo -e "${GREEN}GO [√]${NC} ${label}"
      return 0
    fi
    echo -e "${RED}NOGO [***]${NC} ${label}"
    return "$rc"
  fi

  local spin='|/-\'
  local i=0
  echo -ne "${CYAN}${label}${NC} "
  "$@" >>"$LOG_FILE" 2>&1 &
  local pid=$!
  while kill -0 "$pid" 2>/dev/null; do
    printf "\r${CYAN}${label}${NC} [%c] " "${spin:$i:1}"
    i=$(( (i + 1) % 4 ))
    sleep 0.12
  done
  wait "$pid"
  local rc=$?
  if [ "$rc" -eq 0 ]; then
    printf "\r${GREEN}GO [√]${NC} ${label}\n"
    return 0
  fi
  printf "\r${RED}NOGO [***]${NC} ${label}\n"
  return "$rc"
}

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    pco_nogo "ERR-${PKG_NAME^^}-ROOT-001" "This package installer must be run as root"
  fi
  pco_go "Root privileges confirmed"
}

apt_update() {
  export DEBIAN_FRONTEND=noninteractive
  pco_wait_for_apt_locks
  run_spin "apt-get update" env DEBIAN_FRONTEND=noninteractive apt-get update
}

apt_repair() {
  export DEBIAN_FRONTEND=noninteractive
  pco_wait_for_apt_locks
  run_spin "dpkg configure pending packages" env DEBIAN_FRONTEND=noninteractive dpkg --configure -a
  pco_wait_for_apt_locks
  run_spin "apt-get fix broken packages" env DEBIAN_FRONTEND=noninteractive apt-get -f install -y
}

pco_wait_for_apt_locks() {
  local max_wait="${PINCABOS_APT_LOCK_WAIT:-300}"
  local waited=0
  local interval=5

  while true; do
    if ! fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 && \
       ! fuser /var/lib/dpkg/lock >/dev/null 2>&1 && \
       ! fuser /var/cache/apt/archives/lock >/dev/null 2>&1; then
      pco_go "APT/dpkg locks are clear"
      return 0
    fi

    if [ "$waited" -ge "$max_wait" ]; then
      pco_warn "APT locks still held after ${max_wait}s"
      ps -ef | grep -E 'apt|dpkg|unattended' | grep -v grep || true
      return 1
    fi

    pco_warn "APT/dpkg lock active; waiting ${interval}s (${waited}/${max_wait})"
    ps -ef | grep -E 'apt|dpkg|unattended' | grep -v grep || true
    sleep "$interval"
    waited=$((waited + interval))
  done
}

pco_repair_dpkg_state() {
  pco_wait_for_apt_locks || return 1
  DEBIAN_FRONTEND=noninteractive dpkg --configure -a
  pco_wait_for_apt_locks || return 1
  DEBIAN_FRONTEND=noninteractive apt-get -f install -y
}

apt_install_available() {
  export DEBIAN_FRONTEND=noninteractive

  local requested=("$@")
  local installable=()
  local skipped=()
  local pkg=""
  local candidate=""

  for pkg in "${requested[@]}"; do
    candidate="$(apt-cache policy "$pkg" 2>/dev/null | awk -F': ' '/Candidate:/ {print $2; exit}' || true)"

    if [ -n "$candidate" ] && [ "$candidate" != "(none)" ]; then
      installable+=("$pkg")
    else
      skipped+=("$pkg")
    fi
  done

  if [ "${#skipped[@]}" -gt 0 ]; then
    pco_warn "Some packages have no installation candidate and will be skipped:"
    printf '  - %s\n' "${skipped[@]}"
  fi

  if [ "${#installable[@]}" -eq 0 ]; then
    pco_warn "No installable package found for this package block"
    return 0
  fi

  pco_repair_dpkg_state
  pco_wait_for_apt_locks
  run_spin "Install packages: ${PKG_NAME}" env DEBIAN_FRONTEND=noninteractive apt-get install -y "${installable[@]}"
}

require_command() {
  local missing=0
  local cmd
  for cmd in "$@"; do
    if command -v "$cmd" >/dev/null 2>&1; then
      pco_go "Command available: $cmd"
    else
      pco_warn "Command missing: $cmd"
      missing=$((missing + 1))
    fi
  done

  if [ "$missing" -gt 0 ]; then
    pco_nogo "ERR-${PKG_NAME^^}-COMMANDS-001" "$missing required command(s) are missing"
  fi
}

optional_command() {
  local cmd
  for cmd in "$@"; do
    if command -v "$cmd" >/dev/null 2>&1; then
      pco_go "Optional command available: $cmd"
    else
      pco_warn "Optional command missing: $cmd"
    fi
  done
}

write_summary_line() {
  printf "${YELLOW}%-28s ----> %s${NC}\n" "$1" "$2"
}

pkg_start() {
  exec > >(tee -a "$LOG_FILE") 2>&1
  pco_title
  if [ "${PINCABOS_EXPLICIT:-0}" = "1" ]; then
    pco_warn "Explicit output mode enabled"
  fi
  require_root
}

pkg_done() {
  echo
  pco_go "${PKG_TITLE:-$PKG_NAME} completed"
  echo "Log: $LOG_FILE"
}
