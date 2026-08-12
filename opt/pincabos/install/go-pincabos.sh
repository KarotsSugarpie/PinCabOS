#!/usr/bin/env bash
# PINCABOS_SCRIPT_MODES="default --resume --reset --explicit --help"
# PINCABOS_SCRIPT_REQUIRES_PACKAGES="iproute2 netplan.io systemd iputils-ping python3 grep gawk sed coreutils findutils openssh-server iw rfkill wpasupplicant wireless-regdb network-manager"
# Created by Karots Sugarpie
# PINCABOS_SCRIPT_REQUIRES_DIRS="/opt/pincabos/flags /opt/pincabos/logs /opt/pincabos/backups /opt/pincabos/install /opt/pincabos/modules"
# ────────────────────────────────────────────────────────────────
# PINCABOS_SCRIPT_NAME="go-pincabos"
# PINCABOS_SCRIPT_PATH="/opt/pincabos/install/go-pincabos.sh"
# PINCABOS_SCRIPT_CREATED_BY="Karots Sugarpie"
# PINCABOS_SCRIPT_DESCRIPTION="PinCabOS installer orchestrator. Creates local structure, downloads install scripts/modules, installs module dependencies, and runs first boot modules."
# PINCABOS_SCRIPT_REQUIRES_ROOT="yes"
# PINCABOS_SCRIPT_REQUIRES_COMMANDS="bash date hostname df ip awk sed grep cat mkdir rm touch tee python3 apt-get curl wget sha256sum"
# PINCABOS_SCRIPT_REQUIRES_FILES="/opt/pincabos/install/go-pincabos.sh /opt/pincabos/install/01-install-system.sh /opt/pincabos/install/install.json /opt/pincabos/modules/system/mod-splash.sh /opt/pincabos/modules/system/mod-plymouth-install.sh /opt/pincabos/modules/system/mod-plymouth-load.sh /opt/pincabos/modules/system/assets/plymouth/pkg-plymouth-install.tar.zst /opt/pincabos/modules/system/assets/plymouth/pkg-plymouth-install.tar.zst.sha256 /opt/pincabos/modules/system/assets/plymouth/pkg-plymouth-load.tar.zst /opt/pincabos/modules/system/assets/plymouth/pkg-plymouth-load.tar.zst.sha256 /opt/pincabos/modules/network/mod-dhcp4.sh /opt/pincabos/modules/network/mod-ssid.sh /opt/pincabos/modules/modules.json"
# PINCABOS_SCRIPT_TOUCHES="/opt/pincabos/install /opt/pincabos/modules /opt/pincabos/logs /opt/pincabos/state /opt/pincabos/config /opt/pincabos/backups"
# ────────────────────────────────────────────────────────────────
set -Eeuo pipefail

# ────────────────────────────────────────────────────────────────
# PinCabOS - Clean Modular Installer
#
# Status:
#   GO [√]
#   NOGO [***] ERR-REFERENCE
# ────────────────────────────────────────────────────────────────

ORANGE='\033[38;5;208m'
CYAN='\033[36m'
GREEN='\033[32m'
YELLOW='\033[33m'
RED='\033[31m'
BLUE='\033[34m'
DIM='\033[2m'
NC='\033[0m'

ROOT="/opt/pincabos"
INSTALL_DIR="$ROOT/install"
MODULES_DIR="$ROOT/modules"
LOG_DIR="$ROOT/logs"
STATE_DIR="$ROOT/state"
CONFIG_DIR="$ROOT/config"
BACKUP_DIR="$ROOT/backups"
DOWNLOAD_DIR="$ROOT/download"
TMP_DIR="$ROOT/tmp"

BASE_URL="${PINCABOS_INSTALL_URL:-https://ins.pincabos.cc/install}"

LOG_FILE="$LOG_DIR/go-pincabos-$(date +%Y%m%d-%H%M%S).log"
CURRENT_STEP="BOOT"

mkdir -p "$INSTALL_DIR" "$MODULES_DIR" "$LOG_DIR" "$STATE_DIR" "$CONFIG_DIR" "$BACKUP_DIR" "$DOWNLOAD_DIR" "$TMP_DIR"

exec > >(tee -a "$LOG_FILE") 2>&1

on_error() {
  local rc="$?"
  echo
  echo -e "${RED}NOGO [***] ERR-UNHANDLED-999${NC} Unexpected failure"
  echo -e "${RED}Step:${NC} $CURRENT_STEP"
  echo -e "${RED}Exit code:${NC} $rc"
  echo -e "${RED}Log:${NC} $LOG_FILE"
  exit "$rc"
}

trap on_error ERR

pco_title() {
  clear
  echo -e "${ORANGE}────────────────────────────────────────────────────────────────${NC}"
  echo -e "${ORANGE} PinCabOS - Clean Modular Installer${NC}"
  echo -e "${ORANGE}────────────────────────────────────────────────────────────────${NC}"
  echo -e "${DIM}Log: $LOG_FILE${NC}"
}

pco_step() {
  local step_id="${1:-??}"
  shift || true
  local step_msg="${*:-No step description}"
  echo
  echo -e "${CYAN}─[${step_id}]─► ${ORANGE}${step_msg}${CYAN} ◄────────────────────────────────────────${NC}"
}

pco_go() {
  echo -e "${GREEN}GO [√] ${*:-OK}${NC}"
}

pco_warn() {
  echo -e "${YELLOW}WARN ${*:-Warning}${NC}"
}

pco_info() {
  echo -e "${BLUE}INFO${NC} $1"
}

pco_nogo() {
  local ref="${1:-ERR-GO-UNKNOWN-000}"
  shift || true
  local msg="${*:-No details provided}"
  echo -e "${RED}NOGO [***] ${ref}${NC} ${msg}"
  exit 1
}

run_spin() {
  local label="$1"
  shift

  local tmp_out
  tmp_out="$(mktemp "$TMP_DIR/run-spin.XXXXXX")"

  echo -ne "${CYAN}${label}${NC} "

  "$@" >"$tmp_out" 2>&1 &
  local pid="$!"

  local spin='|/-\'
  local i=0

  while kill -0 "$pid" 2>/dev/null; do
    i=$(( (i + 1) % 4 ))
    printf "\r${CYAN}${label}${NC} [%c] " "${spin:$i:1}"
    sleep 0.12
  done

  wait "$pid"
  local rc="$?"

  if [ "$rc" -eq 0 ]; then
    printf "\r${GREEN}GO [√]${NC} ${label}\n"
    rm -f "$tmp_out"
    return 0
  fi

  printf "\r${RED}NOGO [***]${NC} ${label}\n"
  echo
  cat "$tmp_out"
  rm -f "$tmp_out"
  return "$rc"
}

run_spin_bash() {
  local label="$1"
  local command="$2"
  run_spin "$label" bash -lc "$command"
}

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    pco_nogo "ERR-ROOT-001" "This script must be run as root"
  fi

  pco_go "Root privileges confirmed"
}

detect_downloader() {
  if command -v curl >/dev/null 2>&1; then
    DOWNLOADER="curl"
    pco_go "Downloader detected: curl"
    return 0
  fi

  if command -v wget >/dev/null 2>&1; then
    DOWNLOADER="wget"
    pco_go "Downloader detected: wget"
    return 0
  fi

  pco_nogo "ERR-DOWNLOADER-001" "curl or wget is required"
}


# === PINCABOS CURL6 DHCP4 SAFETY START ===
pincabos_curl6_network_recover_once() {
  pco_warn "curl/wget DNS failure detected; forcing DHCP4/network recovery once before retry"

  if [ -x /opt/pincabos/modules/network/mod-dhcp4.sh ]; then
    PINCABOS_EXPLICIT="${PINCABOS_EXPLICIT:-0}" bash /opt/pincabos/modules/network/mod-dhcp4.sh || true
  elif [ -x /opt/pincabos/install/modules/network/mod-dhcp4.sh ]; then
    PINCABOS_EXPLICIT="${PINCABOS_EXPLICIT:-0}" bash /opt/pincabos/install/modules/network/mod-dhcp4.sh || true
  else
    pco_warn "mod-dhcp4 missing; using service restart fallback"
  fi

  systemctl restart systemd-resolved.service 2>/dev/null || true
  systemctl restart NetworkManager.service 2>/dev/null || true
  systemctl restart systemd-networkd.service 2>/dev/null || true

  sleep 3

  echo "--- Network after curl(6) recovery ---"
  ip -4 -br addr show scope global 2>/dev/null || true
  ip route 2>/dev/null | sed -n '1,12p' || true
  resolvectl dns 2>/dev/null || true
}
# === PINCABOS CURL6 DHCP4 SAFETY END ===

download_file() {
  local url="$1"
  local dest="$2"
  local rc=0
  local err=""

  mkdir -p "$(dirname "$dest")"

  err="$(mktemp /tmp/pincabos-download-error.XXXXXX 2>/dev/null || echo "/tmp/pincabos-download-error.$$")"

  if [ "$DOWNLOADER" = "curl" ]; then
    curl -fsSL "$url" -o "$dest" 2>"$err" && { rm -f "$err"; return 0; }
    rc=$?
  else
    wget -qO "$dest" "$url" 2>"$err" && { rm -f "$err"; return 0; }
    rc=$?
  fi

  if [ "$rc" = "6" ] || grep -qiE 'Could not resolve|Temporary failure in name resolution|Name or service not known|unable to resolve host address' "$err" 2>/dev/null; then
    echo
    echo "NOGO/WARN: DNS resolution failed while downloading: $url"
    sed -n '1,20p' "$err" 2>/dev/null || true

    pincabos_curl6_network_recover_once

    echo "Retry download after DHCP4/DNS recovery: $url"
    if [ "$DOWNLOADER" = "curl" ]; then
      curl -fsSL "$url" -o "$dest" 2>"$err" && { rm -f "$err"; return 0; }
      rc=$?
    else
      wget -qO "$dest" "$url" 2>"$err" && { rm -f "$err"; return 0; }
      rc=$?
    fi
  fi

  sed -n '1,20p' "$err" 2>/dev/null || true
  rm -f "$err"
  return "$rc"
}

try_download() {
  local remote="$1"
  local dest="$2"
  local url="$BASE_URL/$remote"

  pco_info "Fetch: $url"

  if download_file "$url" "$dest.tmp"; then
    mv "$dest.tmp" "$dest"
    chmod +x "$dest"
    pco_go "$remote downloaded"
    return 0
  fi

  rm -f "$dest.tmp"
  pco_warn "$remote not available yet"
  return 0
}

create_structure() {
  pco_step "01" "Create local PinCabOS structure"

  mkdir -p \
    "$INSTALL_DIR" \
    "$MODULES_DIR/core" \
    "$MODULES_DIR/system" \
    "$MODULES_DIR/network" \
    "$MODULES_DIR/gpu" \
    "$MODULES_DIR/engine" \
    "$MODULES_DIR/webapp" \
    "$MODULES_DIR/display" \
    "$MODULES_DIR/dof" \
    "$MODULES_DIR/services" \
    "$MODULES_DIR/cleanup" \
    "$MODULES_DIR/disabled" \
    "$LOG_DIR" \
    "$STATE_DIR" \
    "$CONFIG_DIR" \
    "$BACKUP_DIR" \
    "$DOWNLOAD_DIR" \
    "$TMP_DIR"

  pco_go "Base structure ready"
}

write_default_config() {
  pco_step "02" "Write default installer config"

  cat > "$CONFIG_DIR/install-defaults.env" <<'__PINCABOS_DEFAULTS__'
# PinCabOS default install config

PINCABOS_INSTALL_URL="https://ins.pincabos.cc/install"

PINCABOS_ROOT="/opt/pincabos"
PINCABOS_INSTALL_DIR="/opt/pincabos/install"
PINCABOS_MODULES_DIR="/opt/pincabos/modules"
PINCABOS_LOG_DIR="/opt/pincabos/logs"

PINCABOS_WEB_PORT="80"
PINCABOS_CONSOLE_PORT="8090"
PINCABOS_VPINFE_PORT="8000"
PINCABOS_VPINFE_API_PORT="8001"

PINCABOS_USER="pinball"
PINCABOS_ENGINE_PACKAGE="pincabos-engine-latest.tar.zst"
PINCABOS_UPDATE_JSON="latest.json"
__PINCABOS_DEFAULTS__

  chmod 644 "$CONFIG_DIR/install-defaults.env"
  pco_go "Default config written"
}

write_module_policy() {
  pco_step "03" "Write module policy"

  cat > "$MODULES_DIR/README-MODULES.txt" <<'__PINCABOS_MODULE_POLICY__'
PinCabOS - Module Policy

Purpose:
- Modules are reusable shell blocks.
- Main scripts may call modules.
- Modules must not be edited during an install run.
- A module should be replaced by a new version, not patched in place.

Rules:
1. One module = one task family.
2. Modules should be idempotent when possible.
3. Modules must log to /opt/pincabos/logs when they do heavy work.
4. Modules must not download other modules directly.
5. Critical modules must create backups before changing files.
6. Modules must not modify go-pincabos.sh.
7. Modules must be auditable alone.
8. Modules should return clean exit codes.

Status format:
- GO [√] success
- NOGO [***] ERR-REFERENCE failure
__PINCABOS_MODULE_POLICY__

  chmod 444 "$MODULES_DIR/README-MODULES.txt"
  pco_go "Module policy written and locked"
}

write_module_order() {
  pco_step "04" "Write default module order"

  cat > "$INSTALL_DIR/modules.order" <<'__PINCABOS_MODULE_ORDER__'
# PinCabOS default module execution order
# One line = relative path under /opt/pincabos/modules
# Commented lines are not executed yet.

# core/00-core-functions.sh

# system/10-system-base.sh
# system/11-users-ssh.sh
# system/12-lightdm-openbox.sh
# system/13-chrome-python.sh

# network/15-network-dhcp4.sh

# gpu/20-detect-gpu.sh
# gpu/21-update-gpu-drivers.sh

# engine/30-engine-layout.sh
# engine/31-vpx-install.sh
# engine/32-vpinfe-install.sh

# webapp/40-webapp-install.sh
# webapp/42-update-api.sh

# display/50-display-detect.sh
# display/51-display-apply.sh
# display/52-fulldmd-calibrator.sh

# dof/60-dof-base.sh
# dof/61-ledwiz-tools.sh
# dof/62-pinmame-portable.sh

# services/70-systemd-services.sh
# services/71-sudoers.sh
# services/72-console-ttyd.sh

# cleanup/90-clean-temp.sh
__PINCABOS_MODULE_ORDER__

  chmod 644 "$INSTALL_DIR/modules.order"
  pco_go "Module order written"
}

write_module_manifest() {
  pco_step "05" "Write module manifest"

  cat > "$INSTALL_DIR/modules.manifest" <<'__PINCABOS_MODULE_MANIFEST__'
# PinCabOS module manifest
# Format:
# remote_path destination_relative_path

modules/core/00-core-functions.sh core/00-core-functions.sh

modules/system/10-system-base.sh system/10-system-base.sh
modules/system/mod-plymouth-install.sh system/mod-plymouth-install.sh
modules/system/mod-plymouth-load.sh system/mod-plymouth-load.sh
modules/system/assets/plymouth/pkg-plymouth-install.tar.zst system/assets/plymouth/pkg-plymouth-install.tar.zst
modules/system/assets/plymouth/pkg-plymouth-install.tar.zst.sha256 system/assets/plymouth/pkg-plymouth-install.tar.zst.sha256
modules/system/assets/plymouth/pkg-plymouth-load.tar.zst system/assets/plymouth/pkg-plymouth-load.tar.zst
modules/system/assets/plymouth/pkg-plymouth-load.tar.zst.sha256 system/assets/plymouth/pkg-plymouth-load.tar.zst.sha256
modules/system/11-users-ssh.sh system/11-users-ssh.sh
modules/system/12-lightdm-openbox.sh system/12-lightdm-openbox.sh
modules/system/13-chrome-python.sh system/13-chrome-python.sh

modules/network/15-network-dhcp4.sh network/15-network-dhcp4.sh

modules/gpu/20-detect-gpu.sh gpu/20-detect-gpu.sh
modules/gpu/21-update-gpu-drivers.sh gpu/21-update-gpu-drivers.sh

modules/engine/30-engine-layout.sh engine/30-engine-layout.sh
modules/engine/31-vpx-install.sh engine/31-vpx-install.sh
modules/engine/32-vpinfe-install.sh engine/32-vpinfe-install.sh

modules/webapp/40-webapp-install.sh webapp/40-webapp-install.sh
modules/webapp/42-update-api.sh webapp/42-update-api.sh

modules/display/50-display-detect.sh display/50-display-detect.sh
modules/display/51-display-apply.sh display/51-display-apply.sh
modules/display/52-fulldmd-calibrator.sh display/52-fulldmd-calibrator.sh

modules/dof/60-dof-base.sh dof/60-dof-base.sh
modules/dof/61-ledwiz-tools.sh dof/61-ledwiz-tools.sh
modules/dof/62-pinmame-portable.sh dof/62-pinmame-portable.sh

modules/services/70-systemd-services.sh services/70-systemd-services.sh
modules/services/71-sudoers.sh services/71-sudoers.sh
modules/services/72-console-ttyd.sh services/72-console-ttyd.sh

modules/cleanup/90-clean-temp.sh cleanup/90-clean-temp.sh
__PINCABOS_MODULE_MANIFEST__

  chmod 644 "$INSTALL_DIR/modules.manifest"
  pco_go "Module manifest written"
}

download_main_scripts() {
  pco_step "06" "Download main install scripts"

  try_download "01-install-system.sh" "$INSTALL_DIR/01-install-system.sh"
  try_download "02-install-engine.sh" "$INSTALL_DIR/02-install-engine.sh"

  pco_go "Main script download pass completed"
}

download_modules() {
  pco_step "07" "Download modules from manifest"

  local remote
  local relative
  local dest

  while read -r remote relative; do
    [ -z "${remote:-}" ] && continue
    [[ "$remote" =~ ^# ]] && continue

    dest="$MODULES_DIR/$relative"
    try_download "$remote" "$dest"
  done < "$INSTALL_DIR/modules.manifest"

  pco_go "Module download pass completed"
}

validate_shell_files() {
  pco_step "08" "Validate shell syntax"

  local file
  local failed=0

  while IFS= read -r file; do
    if bash -n "$file"; then
      echo -e "${GREEN}GO [√]${NC} Syntax OK: $file"
    else
      echo -e "${RED}NOGO [***] ERR-SYNTAX-001${NC} Syntax failed: $file"
      failed=1
    fi
  done < <(find "$INSTALL_DIR" "$MODULES_DIR" -type f -name "*.sh" | sort)

  if [ "$failed" -ne 0 ]; then
    pco_nogo "ERR-SYNTAX-002" "One or more shell files failed syntax validation"
  fi

  pco_go "Shell syntax validation completed"
}

lock_module_permissions() {
  pco_step "09" "Lock module permissions"

  find "$MODULES_DIR" -type d -exec chmod 755 {} \;
  find "$MODULES_DIR" -type f -name "*.sh" -exec chmod 555 {} \;
  find "$MODULES_DIR" -type f ! -name "*.sh" -exec chmod 444 {} \;

  pco_go "Module permissions locked"
}

show_summary() {
  pco_step "10" "Final summary"

  echo "Root:      $ROOT"
  echo "Install:   $INSTALL_DIR"
  echo "Modules:   $MODULES_DIR"
  echo "Config:    $CONFIG_DIR/install-defaults.env"
  echo "Order:     $INSTALL_DIR/modules.order"
  echo "Manifest:  $INSTALL_DIR/modules.manifest"
  echo "Base URL:  $BASE_URL"
  echo "Log:       $LOG_FILE"
  echo

  find "$ROOT" -maxdepth 3 -type d | sort

  echo
  echo -e "${GREEN}GO [√] PinCabOS clean modular base is ready${NC}"
}

# ── PINCABOS FIRST MODULE: mod-splash ──
run_first_module_mod_splash() {
  pco_step "00A" "Run first module: mod-splash"

  local mod="/opt/pincabos/modules/system/mod-splash.sh"

  if [ ! -f "$mod" ]; then
    pco_nogo "ERR-GO-MOD-SPLASH-MISSING-001" "Missing required first module: $mod"
  fi

  if [ ! -x "$mod" ]; then
    chmod +x "$mod"
  fi

  if ! bash -n "$mod"; then
    pco_nogo "ERR-GO-MOD-SPLASH-SYNTAX-001" "Syntax failed: $mod"
  fi

  "$mod"

  pco_go "First module completed: mod-splash"
}

# ── PINCABOS MODULE DEPENDENCIES: mod-dhcp4 ──
install_mod_dhcp4_dependencies() {
  pco_step "00B" "Install dependencies for mod-dhcp4"

  local manifest="/opt/pincabos/modules/modules.json"
  local module_key="network/mod-dhcp4.sh"

  if [ ! -f "$manifest" ]; then
    pco_nogo "ERR-GO-MOD-DHCP4-MANIFEST-MISSING-001" "Missing modules manifest: $manifest"
  fi

  local pkgs
  pkgs="$(python3 - "$manifest" "$module_key" <<'PYCODE'
import json
import sys
from pathlib import Path

manifest = Path(sys.argv[1])
module_key = sys.argv[2]

data = json.loads(manifest.read_text(encoding="utf-8"))

pkgs = []

deps = data.get("module_dependencies", {})
entry = deps.get(module_key) or deps.get("/opt/pincabos/modules/network/mod-dhcp4.sh") or {}

for key in ("install_dependencies", "required_packages"):
    value = entry.get(key, [])
    if isinstance(value, list):
        pkgs.extend(str(x) for x in value if str(x).strip())

# Fallback if the manifest layout changes or the explicit section is missing.
if not pkgs:
    pkgs = [
        "iputils-ping",
        "iproute2",
        "netplan.io",
        "systemd",
        "python3",
        "coreutils",
        "grep",
        "sed",
        "gawk",
    ]

seen = []
for pkg in pkgs:
    if pkg not in seen:
        seen.append(pkg)

print(" ".join(seen))
PYCODE
)"

  if [ -z "$pkgs" ]; then
    pco_nogo "ERR-GO-MOD-DHCP4-DEPS-EMPTY-001" "No dependencies found for mod-dhcp4"
  fi

  pco_go "Dependencies resolved: $pkgs"

  export DEBIAN_FRONTEND=noninteractive

  if command -v apt-get >/dev/null 2>&1; then
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get -y autoremove
    apt-get install -y $pkgs
  else
    pco_nogo "ERR-GO-APT-MISSING-001" "apt-get is required to install module dependencies"
  fi

  if command -v ping >/dev/null 2>&1; then
    pco_go "ping available: $(command -v ping)"
  else
    pco_nogo "ERR-GO-PING-MISSING-AFTER-INSTALL-001" "ping still missing after dependency install"
  fi

  pco_go "mod-dhcp4 dependencies installed"
}

# ── PINCABOS SECOND MODULE: mod-dhcp4 ──
run_second_module_mod_dhcp4() {
  pco_step "00C" "Run second module: mod-dhcp4"

  local mod="/opt/pincabos/modules/network/mod-dhcp4.sh"

  if [ ! -f "$mod" ]; then
    pco_nogo "ERR-GO-MOD-DHCP4-MISSING-001" "Missing required second module: $mod"
  fi

  if [ ! -x "$mod" ]; then
    chmod +x "$mod"
  fi

  if ! bash -n "$mod"; then
    pco_nogo "ERR-GO-MOD-DHCP4-SYNTAX-001" "Syntax failed: $mod"
  fi

  "$mod"

  pco_go "Second module completed: mod-dhcp4"
}

# ── PINCABOS THIRD MODULE: mod-ssid (conditional Wi-Fi) ──
pincabos_wifi_device_exists() {
  local iface iface_path type_path

  if [ ! -d /sys/class/net ]; then
    return 1
  fi

  for iface_path in /sys/class/net/*; do
    [ -e "$iface_path" ] || continue
    iface="$(basename "$iface_path")"

    case "$iface" in
      lo|docker*|br-*|veth*|virbr*|tap*|tun*)
        continue
        ;;
    esac

    if [ -d "$iface_path/wireless" ]; then
      return 0
    fi

    if [ -e "$iface_path/uevent" ] && grep -qiE 'DEVTYPE=wlan|INTERFACE=.*wlan|INTERFACE=.*wl' "$iface_path/uevent" 2>/dev/null; then
      return 0
    fi

    type_path="$iface_path/type"
    if [ -r "$type_path" ] && [ "$(cat "$type_path" 2>/dev/null || true)" = "801" ]; then
      return 0
    fi

    case "$iface" in
      wl*|wlan*)
        return 0
        ;;
    esac
  done

  return 1
}

pincabos_install_mod_ssid_deps() {
  pco_step "00D" "Install dependencies for mod-ssid"

  if ! pincabos_wifi_device_exists; then
    pco_go "No Wi-Fi device detected; skipping mod-ssid dependencies"
    return 0
  fi

  if ! command -v apt-get >/dev/null 2>&1; then
    pco_nogo "ERR-GO-APT-MISSING-SSID-001" "apt-get is required to install mod-ssid dependencies"
  fi

  local deps
  deps="iproute2 iw wpasupplicant rfkill netplan.io systemd iputils-ping python3 grep gawk sed coreutils findutils wireless-regdb network-manager"

  DEBIAN_FRONTEND=noninteractive apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y $deps

  pco_go "mod-ssid dependencies installed"
}

pincabos_run_mod_ssid() {
  pco_step "00E" "Run third module: mod-ssid if Wi-Fi exists"

  local mod="/opt/pincabos/modules/network/mod-ssid.sh"

  if ! pincabos_wifi_device_exists; then
    pco_go "No Wi-Fi device detected; skipping mod-ssid"
    return 0
  fi

  if [ ! -x "$mod" ]; then
    pco_warn "mod-ssid not executable or missing: $mod"
    return 0
  fi

  pco_go "Wi-Fi device detected; mod-ssid will run"

  if ! PINCABOS_EXPLICIT="${PINCABOS_EXPLICIT:-0}" bash "$mod"; then
    pco_warn "mod-ssid failed; wired DHCP4 remains active, continuing installation"
    return 0
  fi

  pco_go "Third module completed: mod-ssid"
}

# ── PINCABOS MODULE DEPENDENCY INSTALLER ──
install_all_module_dependencies() {
  pco_step "00A" "Install required module dependencies"

  local packages=(
    iproute2
    netplan.io
    systemd
    iputils-ping
    python3
    grep
    gawk
    sed
    coreutils
    findutils
    openssh-server
    iw
    rfkill
    wpasupplicant
    wireless-regdb
  )

  if ! command -v apt-get >/dev/null 2>&1; then
    pco_nogo "ERR-GO-MODULE-DEPS-APT-001" "apt-get is required to install module dependencies"
  fi

  export DEBIAN_FRONTEND=noninteractive

  pco_go "Module dependency list prepared"
  printf '%s\n' "${packages[@]}" | sed 's/^/  - /'

  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get -y autoremove
  apt-get install -y "${packages[@]}"

  local missing=0
  local commands=(
    ip
    netplan
    systemctl
    ping
    python3
    grep
    awk
    sed
    cat
    readlink
    tee
    find
    timeout
    sshd
    iw
    rfkill
    wpa_passphrase
  )

  echo
  echo "Module dependency command validation:"
  local cmd
  for cmd in "${commands[@]}"; do
    if command -v "$cmd" >/dev/null 2>&1; then
      pco_go "Command available: $cmd"
    else
      pco_warn "Command missing after dependency install: $cmd"
      missing=$((missing + 1))
    fi
  done

  if [ "$missing" -gt 0 ]; then
    pco_nogo "ERR-GO-MODULE-DEPS-COMMANDS-001" "${missing} required module commands are missing"
  fi

  pco_go "All required module dependencies installed"
}



# ── PINCABOS PUBLIC INSTALL TREE BOOTSTRAP ──
pincabos_bootstrap_public_install_tree() {
  pco_step "00P" "Bootstrap complete public install tree from ins.pincabos.cc"

  require_root
  detect_downloader

  mkdir -p \
    "$INSTALL_DIR" \
    "$MODULES_DIR/system" \
    "$MODULES_DIR/network" \
    "$INSTALL_DIR/packages" \
    "$INSTALL_DIR/pkg" \
    "$INSTALL_DIR/tools" \
    "$LOG_DIR" \
    "$STATE_DIR" \
    "$CONFIG_DIR" \
    "$BACKUP_DIR"

  local manifest="$INSTALL_DIR/install.json"
  local manifest_url="$BASE_URL/install.json"

  if download_file "$manifest_url" "$manifest.tmp"; then
    mv -f "$manifest.tmp" "$manifest"
    chmod 0644 "$manifest"
    pco_go "Public install manifest downloaded: $manifest"
  else
    rm -f "$manifest.tmp"
    pco_warn "Public install manifest not available; using built-in essential file list"
  fi

  local list_file="$TMP_DIR/public-install-files.$$.list"

  if [ -s "$manifest" ]; then
    python3 - "$manifest" > "$list_file" <<'PY'
import json, sys
from pathlib import Path

manifest = Path(sys.argv[1])
data = json.loads(manifest.read_text(encoding="utf-8"))
files = []

def forbidden_public_state_path(path):
    parts = path.split("/")
    base = parts[0] if parts else path

    if base.startswith(".completed"):
        return True

    if len(parts) == 1 and (
        base in {
            "current-run",
            "next-run",
            "post-reboot-network-refresh-done",
        }
        or base.startswith("end-run-")
        or base.startswith("reboot-after-")
        or base.startswith("install-refresh-after-")
        or (base.startswith("run-") and len(base) > 4 and base[4].isdigit())
    ):
        return True

    return False

for item in data.get("files", []):
    path = item.get("path")
    if isinstance(path, str) and path.strip():
        clean = path.strip()
        if not forbidden_public_state_path(clean):
            files.append(clean)

# Runtime package may be large, but the user explicitly wants the public tree
# complete on the WebServer/client side. Keep it in the list when present.
seen = set()
for path in files:
    if path not in seen:
        seen.add(path)
        print(path)
PY
  else
    cat > "$list_file" <<'EOF_LIST'
go-pincabos.sh
help-pincabos.sh
01-install-system.sh
02-install-engine.sh
03-install-check.sh
install.json
version.json
modules/modules.json
modules/system/mod-splash.sh
modules/network/mod-dhcp4.sh
modules/network/mod-ssid.sh
packages/pkg-lib.sh
packages/pkg-apt-base.sh
packages/pkg-monitoring.sh
packages/pkg-python.sh
packages/pkg-nginx.sh
packages/pkg-x11.sh
packages/pkg-lightdm.sh
packages/pkg-openbox.sh
packages/pkg-chrome.sh
packages/pkg-plymouth.sh
packages/pkg-vpx-bgfx-runtime.sh
packages/pkg-vpinfe-runtime.sh
packages/pkg-libdof-runtime.sh
packages/pkg-system-validation.sh
pkg/pkg-pincabos-web.zst
pkg/pkg-pincabos-web.sha256
pkg/pkg-pincabos-web.manifest.json
PCOSInstallWP.png
EOF_LIST
  fi

  # PINCABOS_MANIFEST_MODULE_SYNC_V5
  # Keep every modules/** file listed in install.json, including assets,
  # archives and SHA files. Large runtime packages remain owned by RUN_02.
  if [ -s "$list_file" ]; then
    local filtered_list="$TMP_DIR/public-install-files-fast.$$.list"

    python3 - "$list_file" > "$filtered_list" <<'PY_FAST_BOOTSTRAP'
import sys
from pathlib import Path

src = Path(sys.argv[1])
items = [
    line.strip()
    for line in src.read_text(encoding="utf-8", errors="ignore").splitlines()
    if line.strip()
]

allow_exact = {
    "go-pincabos.sh",
    "help-pincabos.sh",
    "01-install-system.sh",
    "02-install-engine.sh",
    "03-install-check.sh",
    "install.json",
    "version.json",
    "PCOSInstallWP.png",
}

seen = set()

for item in items:
    if item in seen:
        continue
    seen.add(item)

    # Modules are the authoritative complete tree.
    # Never exclude a module asset because of a generic package filter.
    if item.startswith("modules/"):
        print(item)
        continue

    if item.startswith("packages/"):
        print(item)
        continue

    if item in allow_exact:
        print(item)
PY_FAST_BOOTSTRAP

    mv -f "$filtered_list" "$list_file"
    pco_go "Manifest filter applied: all declared modules/assets retained; large runtime packages skipped from RUN_00"
  fi


  local rel=""
  local dest=""
  local downloaded=0
  local skipped=0
  local failed=0

  while IFS= read -r rel; do
    [ -n "${rel:-}" ] || continue
    case "$rel" in
      /*|*'..'*)
        pco_warn "Unsafe manifest path skipped: $rel"
        skipped=$((skipped + 1))
        continue
        ;;
      .completed*|.completed*/*|current-run|next-run|post-reboot-network-refresh-done|end-run-*|reboot-after-*|install-refresh-after-*|run-[0-9]*)
        pco_warn "Runtime workflow state path skipped from public bootstrap: $rel"
        skipped=$((skipped + 1))
        continue
        ;;
    esac

    case "$rel" in
      modules/*)
        dest="$MODULES_DIR/${rel#modules/}"
        ;;
      *)
        dest="$INSTALL_DIR/$rel"
        ;;
    esac
    mkdir -p "$(dirname "$dest")"

    if download_file "$BASE_URL/$rel" "$dest.tmp"; then
      mv -f "$dest.tmp" "$dest"
      case "$dest" in
        *.sh) chmod 0755 "$dest" ;;
        *) chmod 0644 "$dest" ;;
      esac
      downloaded=$((downloaded + 1))
    else
      rm -f "$dest.tmp"
      # Optional files are allowed to be absent, but core installers/packages/modules are not.
      case "$rel" in
        go-pincabos.sh|help-pincabos.sh|01-install-system.sh|02-install-engine.sh|03-install-check.sh|install.json|packages/*.sh|modules/*)
          pco_warn "Required public file could not be downloaded: $rel"
          failed=$((failed + 1))
          ;;
        *)
          pco_warn "Optional public file skipped: $rel"
          skipped=$((skipped + 1))
          ;;
      esac
    fi
  done < "$list_file"

  rm -f "$list_file"

  # Recreate canonical PATH commands each time so a fresh VM can use short commands immediately.
  ln -sfn "$INSTALL_DIR/go-pincabos.sh" /usr/local/bin/go-pincabos 2>/dev/null || true
  ln -sfn "$INSTALL_DIR/help-pincabos.sh" /usr/local/bin/help-pincabos 2>/dev/null || true
  ln -sfn "$MODULES_DIR/system/mod-splash.sh" /usr/local/bin/mod-splash 2>/dev/null || true
  ln -sfn "$MODULES_DIR/network/mod-dhcp4.sh" /usr/local/bin/mod-dhcp4 2>/dev/null || true
  ln -sfn "$MODULES_DIR/network/mod-ssid.sh" /usr/local/bin/mod-ssid 2>/dev/null || true


  echo
  echo -e "${YELLOW}Public tree bootstrap summary${NC}"
  echo -e "${YELLOW}Downloaded: $downloaded${NC}"
  echo -e "${YELLOW}Optional skipped: $skipped${NC}"
  echo -e "${YELLOW}Required failed: $failed${NC}"

  if [ "$failed" -gt 0 ]; then
    pco_nogo "ERR-GO-PUBLIC-TREE-001" "Required public install files are missing from $BASE_URL"
  fi

  # Syntax check critical scripts after refresh, before RUN_00/01.
  local critical
  for critical in \
    "$INSTALL_DIR/go-pincabos.sh" \
    "$INSTALL_DIR/help-pincabos.sh" \
    "$INSTALL_DIR/01-install-system.sh" \
    "$INSTALL_DIR/02-install-engine.sh" \
    "$INSTALL_DIR/03-install-check.sh" \
    "$MODULES_DIR/system/mod-splash.sh" \
    "$MODULES_DIR/network/mod-dhcp4.sh" \
    "$MODULES_DIR/network/mod-ssid.sh"
  do
    if [ -f "$critical" ]; then
      bash -n "$critical" && pco_go "Syntax OK: $critical" || pco_nogo "ERR-GO-PUBLIC-SYNTAX-001" "Syntax failed: $critical"
    fi
  done

  pco_go "Public install tree bootstrap completed"
}



# ── PINCABOS RUN_00 VERSION.JSON LOCAL ──
pincabos_run00_install_version_json() {
  pco_step "00V" "Install local version.json"

  local src_url="${BASE_URL}/version.json"
  local tmp="/opt/pincabos/tmp/version.json.$$"
  local dst_root="/opt/pincabos/version.json"
  local dst_install="/opt/pincabos/install/version.json"
  local dst_config="/opt/pincabos/config/version.json"

  mkdir -p /opt/pincabos/tmp /opt/pincabos/install /opt/pincabos/config

  if download_file "$src_url" "$tmp"; then
    if python3 -m json.tool "$tmp" >/dev/null 2>&1; then
      install -m 0644 "$tmp" "$dst_root"
      install -m 0644 "$tmp" "$dst_install"
      install -m 0644 "$tmp" "$dst_config"
      rm -f "$tmp"
      pco_go "version.json installed locally: $dst_root"
      pco_go "version.json installed locally: $dst_install"
      pco_go "version.json installed locally: $dst_config"
      return 0
    fi

    rm -f "$tmp"
    pco_warn "Downloaded version.json is invalid JSON; writing local fallback"
  else
    rm -f "$tmp"
    pco_warn "Public version.json unavailable; writing local fallback"
  fi

  cat > "$dst_root" <<'EOF_VERSION_LOCAL'
{
  "product": "PinCabOS",
  "version": "Alpha 1.6",
  "build": "dev",
  "channel": "local-fallback",
  "source": "go-pincabos RUN_00",
  "created_by": "Karots Sugarpie"
}
EOF_VERSION_LOCAL

  install -m 0644 "$dst_root" "$dst_install"
  install -m 0644 "$dst_root" "$dst_config"

  python3 -m json.tool "$dst_root" >/dev/null \
    && pco_go "Fallback version.json installed locally" \
    || pco_nogo "ERR-GO-VERSION-JSON-001" "Local version.json fallback invalid"

  return 0
}


# ── PINCABOS RUN_00 PREFLIGHT SUMMARY ──
run_00_preflight_summary() {
  local nogo_count=0
  local ip_summary=""
  local default_route=""
  local dns_summary=""
  local free_root=""
  local os_summary="unknown"

  pco_step "00" "RUN_00 preflight summary"

  mkdir -p /opt/pincabos/logs /opt/pincabos/flags
  pincabos_run00_install_version_json

  if [ -r /etc/os-release ]; then
    os_summary="$(. /etc/os-release && printf '%s %s' "${NAME:-unknown}" "${VERSION_ID:-}")"
  fi

  free_root="$(df -h / 2>/dev/null | awk 'NR==2 {print $4}' || true)"
  ip_summary="$(ip -4 -br addr show scope global 2>/dev/null | awk '{print $1 "=" ${3:-}}' | paste -sd ', ' - || true)"
  default_route="$(ip route show default 2>/dev/null | head -n1 || true)"
  dns_summary="$(grep -h '^nameserver ' /etc/resolv.conf 2>/dev/null | awk '{print $2}' | paste -sd ', ' - || true)"

  [ -n "$ip_summary" ] || ip_summary="none"
  [ -n "$default_route" ] || default_route="none"
  [ -n "$dns_summary" ] || dns_summary="none"
  [ -n "$free_root" ] || free_root="unknown"

  echo
  echo -e "${YELLOW}RUN_00 summary${NC}"
  echo -e "${YELLOW}Hostname:              $(hostname 2>/dev/null || echo unknown)${NC}"
  echo -e "${YELLOW}Operating system:      $os_summary${NC}"
  echo -e "${YELLOW}IPv4 addresses:        $ip_summary${NC}"
  echo -e "${YELLOW}Default route:         $default_route${NC}"
  echo -e "${YELLOW}DNS servers:           $dns_summary${NC}"
  echo -e "${YELLOW}Available disk space:  $free_root${NC}"
  echo -e "${YELLOW}Install path:          /opt/pincabos/install${NC}"
  echo -e "${YELLOW}Log path:              /opt/pincabos/logs${NC}"
  echo -e "${YELLOW}Flag path:             /opt/pincabos/flags${NC}"

  echo
  echo "RUN_00 GO/NOGO checks:"

  if [ "$(id -u)" -eq 0 ]; then
    pco_go "Root privileges confirmed"
  else
    pco_warn "Root privileges missing"
    nogo_count=$((nogo_count + 1))
  fi

  if [ -d /opt/pincabos/install ]; then
    pco_go "Install directory exists"
  else
    pco_warn "Install directory missing"
    nogo_count=$((nogo_count + 1))
  fi

  if [ -f /opt/pincabos/install/01-install-system.sh ]; then
    chmod +x /opt/pincabos/install/01-install-system.sh 2>/dev/null || true
    pco_go "01-install-system.sh available"
  else
    pco_warn "01-install-system.sh missing"
    nogo_count=$((nogo_count + 1))
  fi

  if [ "$free_root" != "unknown" ]; then
    pco_go "Disk space check collected: $free_root available"
  else
    pco_warn "Unable to collect available disk space"
    nogo_count=$((nogo_count + 1))
  fi

  if [ "$nogo_count" -eq 0 ]; then
    pco_go "RUN_00 preflight summary completed"
    return 0
  fi

  pco_warn "RUN_00 found $nogo_count issues"
  return 1
}





pincabos_install_root_autoresume_console() {
  local target_stage="${1:-RUN_02}"
  local helper="/usr/local/sbin/pincabos-autoresume-console.sh"
  local override_dir="/etc/systemd/system/getty@tty1.service.d"
  local override_file="${override_dir}/10-pincabos-root-autoresume.conf"

  pco_step "BOOT" "Prepare hidden root autologin autoresume console"

  install -d -m 0755 /usr/local/sbin
  cat > "$helper" <<'EOS'
#!/usr/bin/env bash
# Created by Karots Sugarpie
# PINCABOS_SCRIPT_NAME="pincabos-autoresume-console.sh"
# PINCABOS_SCRIPT_ROLE="Hidden root console autoresume after RUN_01 reboot"
# PINCABOS_SCRIPT_REQUIRES_FILES="/opt/pincabos/install/go-pincabos.sh /opt/pincabos/install/01-install-system.sh /opt/pincabos/install/install.json /opt/pincabos/modules/system/mod-splash.sh /opt/pincabos/modules/system/mod-plymouth-install.sh /opt/pincabos/modules/system/mod-plymouth-load.sh /opt/pincabos/modules/system/assets/plymouth/pkg-plymouth-install.tar.zst /opt/pincabos/modules/system/assets/plymouth/pkg-plymouth-install.tar.zst.sha256 /opt/pincabos/modules/system/assets/plymouth/pkg-plymouth-load.tar.zst /opt/pincabos/modules/system/assets/plymouth/pkg-plymouth-load.tar.zst.sha256 /opt/pincabos/modules/network/mod-dhcp4.sh /opt/pincabos/modules/network/mod-ssid.sh /opt/pincabos/modules/modules.json"
# PINCABOS_SCRIPT_REQUIRES_COMMANDS="bash exec"

set -Eeuo pipefail

export TERM="${TERM:-linux}"
export PINCABOS_EXPLICIT="${PINCABOS_EXPLICIT:-0}"

exec </dev/tty1 >/dev/tty1 2>&1 || true

clear
ORANGE='\033[38;5;208m'
RESET='\033[0m'

echo -e "${ORANGE}────────────────────────────────────────────────────────────────${RESET}"
echo -e "${ORANGE} PinCabOS - Root autoresume console${RESET}"
echo -e "${ORANGE}────────────────────────────────────────────────────────────────${RESET}"
echo
echo "GO [√] Root autologin console active"
echo "GO [√] Login prompt hidden by getty override"
echo "GO [√] Network is owned directly by go-pincabos, not by autoresume helper or any RUN stage"
echo
echo "=== Continue PinCabOS workflow ==="

if [ -x /opt/pincabos/install/go-pincabos.sh ]; then
  exec /opt/pincabos/install/go-pincabos.sh --resume
fi

if command -v go-pincabos >/dev/null 2>&1; then
  exec go-pincabos --resume
fi

echo "NOGO [X] go-pincabos not found for autoresume"
exec /bin/bash -l
EOS

  chmod 0755 "$helper"
  chown root:root "$helper"

  install -d -m 0755 "$override_dir"
  cat > "$override_file" <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin root --noclear --noissue --login-program ${helper} %I \$TERM
Type=idle
EOF

  chmod 0644 "$override_file"
  chown root:root "$override_file"

  systemctl daemon-reload || true
  systemctl enable getty@tty1.service >/dev/null 2>&1 || true

  pco_go "Root autoresume console installed for ${target_stage}"
  pco_go "TTY1 will autologin root, hide login prompt, then resume go-pincabos; DHCP4/SSID owned directly by go-pincabos"
}


# ── PINCABOS WORKFLOW FLAGS - MANAGED BY GO-PINCABOS ONLY ──
pincabos_flags_dir() {
  printf '%s\n' "/opt/pincabos/flags"
}

pincabos_ensure_flags_dir() {
  mkdir -p "$(pincabos_flags_dir)"
}

pincabos_flag_path() {
  local name="$1"
  printf '%s/%s\n' "$(pincabos_flags_dir)" "$name"
}

pincabos_write_flag() {
  local name="$1"
  local status="$2"
  local label="${3:-}"
  local rc="${4:-0}"
  local path
  path="$(pincabos_flag_path "$name")"
  pincabos_ensure_flags_dir
  {
    printf 'name=%s\n' "$name"
    printf 'status=%s\n' "$status"
    printf 'label=%s\n' "$label"
    printf 'exit_code=%s\n' "$rc"
    printf 'timestamp=%s\n' "$(date '+%Y-%m-%d %H:%M:%S')"
  } > "$path"
}

pincabos_reset_flags() {
  pco_step "RESET" "Reset PinCabOS workflow flags"
  pincabos_ensure_flags_dir
  rm -f \
    "$(pincabos_flags_dir)"/run-* \
    "$(pincabos_flags_dir)"/end-run-* \
    "$(pincabos_flags_dir)"/current-run \
    "$(pincabos_flags_dir)"/next-run \
    "$(pincabos_flags_dir)"/reboot-after-01 \
    "$(pincabos_flags_dir)"/post-reboot-network-refresh-* \
    "$(pincabos_flags_dir)"/install-refresh-after-run01-* \
    "$(pincabos_flags_dir)"/final-go \
    "$(pincabos_flags_dir)"/final-reboot \
    2>/dev/null || true
  rm -f /opt/pincabos/state/current-run /opt/pincabos/state/next-run 2>/dev/null || true
  pco_go "Workflow, resume, reboot and transient flags removed from $(pincabos_flags_dir)"
}

pincabos_show_flags() {
  pco_step "FLAGS" "Current workflow flags"
  pincabos_ensure_flags_dir
  find "$(pincabos_flags_dir)" -maxdepth 1 -type f \( -name 'run-*' -o -name 'end-run-*' \) -print | sort || true
}

pincabos_stage_completed() {
  local stage="$1"
  local flag
  flag="$(pincabos_flag_path "end-run-$stage")"
  [ -f "$flag" ] && grep -q '^status=GO$' "$flag"
}

pincabos_run_stage() {
  local stage="$1"
  local label="$2"
  shift 2

  if [ "${PINCABOS_RESUME_MODE:-0}" = "1" ] && pincabos_stage_completed "$stage"; then
    pco_go "Stage already completed, skipping: RUN_$stage - $label"
    return 0
  fi

  CURRENT_STEP="RUN_$stage - $label"
  pco_step "$stage" "$label"
  pincabos_write_flag "run-$stage" "RUNNING" "$label" "0"

  if "$@"; then
    pincabos_write_flag "end-run-$stage" "GO" "$label" "0"
    pco_go "Stage completed: RUN_$stage - $label"
    return 0
  else
    local rc="$?"
    pincabos_write_flag "end-run-$stage" "NOGO" "$label" "$rc"
    pco_nogo "ERR-GO-STAGE-$stage-001 Stage failed: RUN_$stage - $label"
  fi
}

pincabos_run_script_if_present() {
  local script="$1"

  if [ ! -f "$script" ]; then
    pco_nogo "ERR-GO-SCRIPT-MISSING-001" "Missing script: $script"
  fi

  chmod +x "$script" 2>/dev/null || true

  if [ "${PINCABOS_EXPLICIT_MODE:-0}" = "1" ]; then
    PINCABOS_EXPLICIT=1 "$script"
  else
    "$script"
  fi
}

pincabos_mode_from_args() {
  PINCABOS_RESUME_MODE=0
  PINCABOS_RESET_MODE=0
  PINCABOS_EXPLICIT_MODE=0

  while [ "$#" -gt 0 ]; do
    case "${1:-}" in
      --resume)
        PINCABOS_RESUME_MODE=1
        ;;
      --reset)
        PINCABOS_RESET_MODE=1
        ;;
      --explicit)
        PINCABOS_EXPLICIT_MODE=1
        export PINCABOS_EXPLICIT=1
        ;;
      --help|-h)
        if command -v help-pincabos >/dev/null 2>&1; then
          help-pincabos
        elif [ -x /opt/pincabos/install/help-pincabos.sh ]; then
          /opt/pincabos/install/help-pincabos.sh
        else
          echo "Usage: go-pincabos [--resume] [--reset] [--explicit] [--help]"
        fi
        exit 0
        ;;
      "")
        ;;
      *)
        pco_nogo "ERR-GO-ARGS-001" "Unknown option: ${1:-}"
        ;;
    esac
    shift || true
  done

  if [ "${PINCABOS_EXPLICIT_MODE:-0}" = "1" ]; then
    pco_warn "Explicit mode enabled: spinner output is disabled and full command output is shown"
  fi
}



pincabos_block_graphical_startup_after_01() {
  pco_step "01A" "Block LightDM and Openbox startup before ISO reboot"

  pco_warn "Blocking graphical startup until engine stage is ready"

  if command -v systemctl >/dev/null 2>&1; then
    systemctl set-default multi-user.target >/dev/null 2>&1 || true
    systemctl stop lightdm.service >/dev/null 2>&1 || true
    systemctl disable lightdm.service >/dev/null 2>&1 || true
    pco_go "Default boot target set to multi-user.target"
    pco_go "lightdm.service stopped/disabled when present"
  else
    pco_warn "systemctl not available; graphical startup block skipped"
  fi

  pkill -x openbox >/dev/null 2>&1 || true
  pco_go "Openbox process stopped if it was running"

  return 0
}

pincabos_download_install_wallpaper() {
  pco_step "01B" "Download installer wallpaper from ins.pincabos.cc"

  local dest_dir="/opt/pincabos/media/installer"
  local dest="$dest_dir/PCOSInstallWP.png"
  local base="https://ins.pincabos.cc/install"
  local candidates=(
    "$base/PCOSInstallWP.png"
    "$base/pincabos-install-wallpaper.png"
    "$base/pincabos-wallpaper.png"
    "$base/wallpaper.png"
    "$base/assets/PCOSInstallWP.png"
    "$base/assets/pincabos-install-wallpaper.png"
  )

  mkdir -p "$dest_dir"

  local url=""
  for url in "${candidates[@]}"; do
    if command -v curl >/dev/null 2>&1 && curl -fsSL "$url" -o "$dest"; then
      pco_go "Wallpaper downloaded: $url"
      printf '%s\n' "$dest"
      return 0
    fi
  done

  pco_warn "Installer wallpaper not downloaded from known paths"
  pco_warn "Continuing without wallpaper download"
  return 0
}



pincabos_apply_installer_plymouth_wallpaper() {
  pco_step "PLY-INSTALL" "Apply PinCabOS installer Plymouth module"

  local mod="/opt/pincabos/modules/system/mod-plymouth-install.sh"

  if [ ! -x "$mod" ]; then
    pco_nogo "ERR-GO-PLYMOUTH-INSTALL-MODULE-MISSING" "Missing executable module: $mod"
    return 1
  fi

  PINCABOS_EXPLICIT="${PINCABOS_EXPLICIT:-0}" bash "$mod"
}

pincabos_apply_plymouth_install_wallpaper() {
  pincabos_apply_installer_plymouth_wallpaper "$@"
}

pincabos_apply_grub_quiet_splash() {
  pco_step "01D" "Apply hidden GRUB quiet splash"

  local grub="/etc/default/grub"
  local backup="/opt/pincabos/backups/etc_default_grub.backup-go-pincabos-$(date +%Y%m%d-%H%M%S)"

  if [ ! -f "$grub" ]; then
    pco_warn "Missing $grub; skipping GRUB hidden quiet splash"
    return 0
  fi

  mkdir -p /opt/pincabos/backups
  cp -a "$grub" "$backup"
  pco_go "Backup created: $backup"

  set_grub_kv() {
    local key="$1"
    local value="$2"

    if grep -qE "^${key}=" "$grub"; then
      sed -i "s|^${key}=.*|${key}=${value}|" "$grub"
    else
      printf '
%s=%s
' "$key" "$value" >> "$grub"
    fi
  }

  # Hide GRUB menu after ISO install and keep only the PinCabOS splash.
  set_grub_kv "GRUB_TIMEOUT_STYLE" "hidden"
  set_grub_kv "GRUB_TIMEOUT" "0"
  set_grub_kv "GRUB_RECORDFAIL_TIMEOUT" "0"
  set_grub_kv "GRUB_CMDLINE_LINUX_DEFAULT" '"quiet splash loglevel=3 vt.global_cursor_default=0"'

  # Do not let os-prober create a visible multi-boot menu during cabinet boot.
  set_grub_kv "GRUB_DISABLE_OS_PROBER" "true"

  if command -v update-grub >/dev/null 2>&1; then
    if [ "${PINCABOS_EXPLICIT:-0}" = "1" ]; then
      update-grub
    else
      update-grub >/dev/null 2>&1 || true
    fi
    pco_go "GRUB updated with hidden menu + quiet splash"
  else
    pco_warn "update-grub not available"
  fi

  return 0
}


pincabos_wait_for_iso_reboot_key() {
  local key=""
  local tty_candidate=""

  echo -e "${YELLOW}Waiting for a real keyboard input before reboot...${NC}"

  for tty_candidate in /dev/tty /dev/console /dev/tty1; do
    if [ -r "$tty_candidate" ] && [ -w "$tty_candidate" ]; then
      echo -e "${YELLOW}Input device: $tty_candidate${NC}"
      if read -r -n 1 -s key < "$tty_candidate"; then
        echo
        pco_go "Key press detected from $tty_candidate"
        return 0
      fi
    fi
  done

  pco_nogo "ERR-GO-ISO-PAUSE-TTY-001" "Unable to read a key from /dev/tty, /dev/console, or /dev/tty1"
}



pincabos_prepare_clean_run02_transition_before_iso_pause() {
  pco_step "01D" "Prepare clean RUN_02 transition before ISO pause"

  local flags_dir=""
  local state_dir=""
  local backup_root=""
  local stamp=""

  flags_dir="$(pincabos_flags_dir)"
  state_dir="/opt/pincabos/state"
  stamp="$(date +%Y%m%d-%H%M%S)"
  backup_root="/opt/pincabos/backups/network-before-run02-$stamp"

  mkdir -p "$flags_dir" "$state_dir" "$backup_root"

  pco_step "01D.1" "Write RUN_01 end and RUN_02 next-run state"

  pincabos_write_flag "end-run-01" "GO" "RUN_01 completed before ISO pause" "0"

  cat > "$flags_dir/current-run" <<STATE
status=GO
run=RUN_02
stage=02
message=RUN_02 selected before ISO pause
timestamp=$(date -Is)
STATE

  cat > "$flags_dir/next-run" <<STATE
status=GO
run=RUN_02
stage=02
message=Next boot must resume RUN_02
timestamp=$(date -Is)
STATE

  cat > "$state_dir/current-run" <<STATE
RUN_02
STATE

  cat > "$state_dir/next-run" <<STATE
RUN_02
STATE

  pco_go "RUN_01 end written; RUN_02 selected as next run"

  pco_step "01D.2" "Force text boot only before ISO reboot"

  if command -v systemctl >/dev/null 2>&1; then
    systemctl set-default multi-user.target >/dev/null 2>&1 || true
    systemctl disable lightdm.service >/dev/null 2>&1 || true
    systemctl stop lightdm.service >/dev/null 2>&1 || true
    systemctl disable display-manager.service >/dev/null 2>&1 || true
    systemctl stop display-manager.service >/dev/null 2>&1 || true

    # RUN_02 must boot directly to hidden root autoresume.
    # RUN_01 clears netplan/MAC/interface identity before reboot,
    # so wait-online must not block boot on stale network state.
    systemctl stop systemd-networkd-wait-online.service >/dev/null 2>&1 || true
    systemctl disable systemd-networkd-wait-online.service >/dev/null 2>&1 || true
    systemctl mask systemd-networkd-wait-online.service >/dev/null 2>&1 || true
    systemctl stop NetworkManager-wait-online.service >/dev/null 2>&1 || true
    systemctl disable NetworkManager-wait-online.service >/dev/null 2>&1 || true
    systemctl mask NetworkManager-wait-online.service >/dev/null 2>&1 || true
    systemctl reset-failed systemd-networkd-wait-online.service >/dev/null 2>&1 || true
    systemctl reset-failed NetworkManager-wait-online.service >/dev/null 2>&1 || true

    pco_go "Graphical boot disabled before RUN_02 resume"
    pco_go "Network wait-online services disabled/masked before RUN_02 resume"
  else
    pco_warn "systemctl unavailable; graphical boot/wait-online guard skipped"
  fi

  pco_step "01D.3" "Backup and clear network identity before ISO reboot"

  mkdir -p "$backup_root/etc-netplan" \
           "$backup_root/networkmanager-system-connections" \
           "$backup_root/udev-rules" \
           "$backup_root/systemd-network"

  if [ -d /etc/netplan ]; then
    cp -a /etc/netplan/. "$backup_root/etc-netplan/" 2>/dev/null || true
    find /etc/netplan -maxdepth 1 -type f \( -name '*.yaml' -o -name '*.yml' \) -print -delete 2>/dev/null || true
    pco_go "Netplan YAML cleared; backup: $backup_root/etc-netplan"
  else
    pco_warn "/etc/netplan missing; skipped"
  fi

  if [ -d /etc/NetworkManager/system-connections ]; then
    cp -a /etc/NetworkManager/system-connections/. "$backup_root/networkmanager-system-connections/" 2>/dev/null || true
    find /etc/NetworkManager/system-connections -maxdepth 1 -type f -print -delete 2>/dev/null || true
    pco_go "NetworkManager saved connections cleared"
  else
    pco_warn "NetworkManager system-connections not present; skipped"
  fi

  for f in \
    /etc/udev/rules.d/70-persistent-net.rules \
    /etc/udev/rules.d/80-net-setup-link.rules \
    /etc/udev/rules.d/99-pincabos-net.rules
  do
    if [ -e "$f" ]; then
      cp -a "$f" "$backup_root/udev-rules/" 2>/dev/null || true
      rm -f "$f" 2>/dev/null || true
      pco_go "Removed persistent network rule: $f"
    fi
  done

  if [ -d /etc/systemd/network ]; then
    find /etc/systemd/network -maxdepth 1 -type f \( -name '*pincabos*.link' -o -name '*pincabos*.network' -o -name '*installer*.link' -o -name '*installer*.network' \) -print \
      -exec cp -a {} "$backup_root/systemd-network/" \; \
      -exec rm -f {} \; 2>/dev/null || true
    pco_go "PinCabOS/systemd network identity overrides cleared"
  fi

  rm -f /run/systemd/network/*.network 2>/dev/null || true
  rm -f /run/NetworkManager/system-connections/*.nmconnection 2>/dev/null || true

  pco_go "Network config, saved MAC bindings, and interface-name overrides cleared before ISO pause"

  pco_step "01D.4" "Install hidden root autoresume console for RUN_02"

  pincabos_install_root_autoresume_console "RUN_02"

  pco_go "RUN_02 transition is ready; ISO pause can be displayed"
}


pincabos_prepare_iso_reboot_phase_after_01() {
  pco_step "01E" "Prepare ISO reboot pause after RUN_01"

  pincabos_block_graphical_startup_after_01
  pincabos_download_install_wallpaper >/dev/null || true
  pincabos_apply_plymouth_install_wallpaper
  pincabos_apply_grub_quiet_splash
  pincabos_prepare_clean_run02_transition_before_iso_pause

  echo
  echo -e "${YELLOW}RUN_01 completed.${NC}"
  echo -e "${YELLOW}RUN_02 transition is already prepared before this pause.${NC}"
  echo -e "${YELLOW}Network identity was cleared, GRUB hidden splash was applied, and autoresume is installed.${NC}"
  echo -e "${YELLOW}Press any key: the only remaining action is immediate reboot.${NC}"
  echo
  pincabos_wait_for_iso_reboot_key

  # After keypress, do not prepare anything else. Only mark the pause/reboot and reboot.
  pincabos_write_flag "end-run-01E" "GO" "RUN_01 ISO pause completed; reboot requested" "0"
  pincabos_write_flag "reboot-after-01" "GO" "reboot requested after RUN_01 ISO pause" "0"

  echo
  pco_go "Key pressed. Plymouth was already applied before the ISO pause; no duplicate Plymouth module run before reboot."

  if [ -L /usr/share/plymouth/themes/default.plymouth ]; then
    active_plymouth="$(readlink -f /usr/share/plymouth/themes/default.plymouth || true)"
    expected_plymouth="/usr/share/plymouth/themes/pincabos-install/pincabos-install.plymouth"

    echo "Active Plymouth:   $active_plymouth"
    echo "Expected Plymouth: $expected_plymouth"

    if [ "$active_plymouth" = "$expected_plymouth" ]; then
      pco_go "Plymouth default confirmed before reboot: pincabos-install"
    else
      pco_nogo "ERR-GO-PLYMOUTH-INSTALL-NOT-ACTIVE" "Plymouth default is not pincabos-install before RUN_02 reboot"
    fi
  else
    pco_nogo "ERR-GO-PLYMOUTH-DEFAULT-MISSING" "Missing /usr/share/plymouth/themes/default.plymouth before RUN_02 reboot"
  fi

  pco_go "No more RUN_01 work. Rebooting directly to RUN_02 autoresume now."

  if command -v systemctl >/dev/null 2>&1; then
    systemctl reboot
  else
    reboot
  fi

  exit 0
}

pincabos_post_reboot_network_refresh() {
  pco_step "GO-NET" "go-pincabos owned DHCP4 and optional SSID refresh"

  local done_flag=""
  local running_flag=""
  local wifi_found="0"

  done_flag="$(pincabos_flag_path post-reboot-network-refresh-done)"
  running_flag="$(pincabos_flag_path post-reboot-network-refresh-running)"

  if [ -f "$done_flag" ] && grep -q '^status=GO$' "$done_flag" 2>/dev/null; then
    pco_go "Post-reboot DHCP4/SSID refresh already completed once; skipping"
    return 0
  fi

  if [ -f "$running_flag" ]; then
    pco_warn "Stale post-reboot network refresh running flag found; clearing it"
    rm -f "$running_flag" 2>/dev/null || true
  fi

  pincabos_write_flag "post-reboot-network-refresh-running" "GO" "DHCP4/SSID refresh started directly by go-pincabos after RUN_01 reboot" "0"

  echo
  echo -e "${YELLOW}go-pincabos network owner${NC}"
  echo -e "${YELLOW}DHCP4/SSID are executed directly by go-pincabos, not inside any RUN script or getty helper.${NC}"

  if [ -x /opt/pincabos/modules/network/mod-dhcp4.sh ]; then
    pco_go "Running DHCP4 module after reboot"
    PINCABOS_EXPLICIT="${PINCABOS_EXPLICIT:-0}" bash /opt/pincabos/modules/network/mod-dhcp4.sh
  else
    pco_warn "DHCP4 module missing; using safe network restart fallback"
    systemctl restart systemd-networkd 2>/dev/null || true
    systemctl restart NetworkManager 2>/dev/null || true
  fi

  if command -v iw >/dev/null 2>&1 && iw dev 2>/dev/null | grep -q 'Interface '; then
    wifi_found="1"
  fi

  if command -v nmcli >/dev/null 2>&1 && nmcli -t -f TYPE device 2>/dev/null | grep -q '^wifi$'; then
    wifi_found="1"
  fi

  if ls /sys/class/net 2>/dev/null | grep -Eq '^(wl|wlan)'; then
    wifi_found="1"
  fi

  if [ "$wifi_found" = "1" ] && [ -x /opt/pincabos/modules/network/mod-ssid.sh ]; then
    pco_go "Wi-Fi detected; running SSID module after reboot"
    PINCABOS_EXPLICIT="${PINCABOS_EXPLICIT:-0}" bash /opt/pincabos/modules/network/mod-ssid.sh
  else
    pco_go "No Wi-Fi module required or no Wi-Fi hardware detected"
  fi

  echo
  echo -e "${YELLOW}Post-reboot network summary${NC}"
  ip -4 -br addr show scope global 2>/dev/null || true
  ip route 2>/dev/null | sed -n '1,20p' || true

  pincabos_write_flag "post-reboot-network-refresh-done" "GO" "DHCP4/SSID refresh completed once directly by go-pincabos after RUN_01 reboot" "0"
  rm -f "$running_flag" 2>/dev/null || true

  pco_go "go-pincabos DHCP4/SSID refresh completed"
  return 0
}


# === PINCABOS RUN_02 NETWORK READY GATE START ===
pincabos_wait_install_network_ready() {
  pco_step "01F" "Validate DHCP4/IP before installer refresh and RUN_02"

  local base="${PINCA_INSTALL_BASE_URL:-https://ins.pincabos.cc/install}"
  local url="${base%/}/go-pincabos.sh"
  local i=""
  local ip_ok="0"
  local route_ok="0"
  local http_ok="0"

  for i in $(seq 1 90); do
    ip_ok="0"
    route_ok="0"
    http_ok="0"

    if ip -4 addr show scope global 2>/dev/null | grep -q 'inet '; then
      ip_ok="1"
    fi

    if ip -4 route show default 2>/dev/null | grep -q '^default '; then
      route_ok="1"
    fi

    if command -v curl >/dev/null 2>&1; then
      if curl -fsSL --connect-timeout 3 --max-time 6 "$url" >/dev/null 2>&1; then
        http_ok="1"
      fi
    elif command -v wget >/dev/null 2>&1; then
      if wget -q --spider --timeout=6 "$url" >/dev/null 2>&1; then
        http_ok="1"
      fi
    else
      pco_warn "No curl/wget available for install server reachability test"
    fi

    if [ "$ip_ok" = "1" ] && [ "$route_ok" = "1" ] && [ "$http_ok" = "1" ]; then
      pco_go "Network ready for 01G/RUN_02: IP + default route + install server reachable"
      ip -4 -br addr show scope global 2>/dev/null || true
      ip route 2>/dev/null | sed -n '1,12p' || true
      return 0
    fi

    if [ "$i" = "1" ] || [ $((i % 10)) -eq 0 ]; then
      echo "WAIT 01F network gate: try=$i ip_ok=$ip_ok route_ok=$route_ok http_ok=$http_ok url=$url"
      ip -4 -br addr show scope global 2>/dev/null || true
      ip route 2>/dev/null | sed -n '1,8p' || true
    fi

    sleep 2
  done

  echo
  echo "NOGO: Network not ready after DHCP4 refresh"
  echo "Expected before 01G/RUN_02:"
  echo "  - IPv4 global address"
  echo "  - default route"
  echo "  - HTTP access to $url"
  echo
  echo "--- IPv4 ---"
  ip -4 addr show 2>/dev/null || true
  echo
  echo "--- Routes ---"
  ip route 2>/dev/null || true
  echo
  echo "--- Netplan ---"
  ls -lah /etc/netplan 2>/dev/null || true
  sed -n '1,180p' /etc/netplan/*.yaml 2>/dev/null || true
  echo
  echo "--- Services ---"
  systemctl --no-pager --full status NetworkManager.service 2>/dev/null | sed -n '1,20p' || true
  systemctl --no-pager --full status systemd-networkd.service 2>/dev/null | sed -n '1,20p' || true

  pco_nogo "ERR-GO-RUN02-NETWORK-NOT-READY-001" "RUN_02 blocked: DHCP4 did not produce working install network"
}
# === PINCABOS RUN_02 NETWORK READY GATE END ===

pincabos_refresh_install_files_from_ins() {
  pco_step "01G" "Refresh complete installer and module tree from ins.pincabos.cc"

  local done_flag=""
  local running_flag=""

  done_flag="$(pincabos_flag_path install-refresh-after-run01-done)"
  running_flag="$(pincabos_flag_path install-refresh-after-run01-running)"

  if [ -f "$done_flag" ]; then
    pco_go "Installer refresh after RUN_01 already completed once; skipping to avoid loop"
    return 0
  fi

  if [ -f "$running_flag" ]; then
    pco_warn "Installer refresh after RUN_01 was already marked running; clearing stale running flag"
    rm -f "$running_flag" 2>/dev/null || true
  fi

  pincabos_write_flag "install-refresh-after-run01-running" "GO" "Complete manifest refresh after RUN_01 started" "0"

  # One authoritative source:
  # install.json -> all declared files -> /opt/pincabos.
  # This includes every modules/** script, asset, archive and checksum.
  if ! pincabos_bootstrap_public_install_tree; then
    rm -f "$running_flag" 2>/dev/null || true
    pco_nogo "ERR-GO-01G-PUBLIC-TREE-001" "Complete public manifest refresh failed after RUN_01"
    return 1
  fi

  pco_go "Installer and complete module tree refresh completed from public manifest"

  rm -f "$running_flag" 2>/dev/null || true
  pincabos_write_flag "install-refresh-after-run01-done" "GO" "Complete manifest refresh after RUN_01 completed once" "0"

  return 0
}

pincabos_validate_local_02_sha_fix() {
  pco_step "01H" "Validate local 02-install-engine SHA fix"

  local script="/opt/pincabos/install/02-install-engine.sh"

  if [ ! -f "$script" ]; then
    pco_nogo "ERR-GO-02-MISSING-001" "Missing script: $script"
  fi

  chmod +x "$script" 2>/dev/null || true

  if grep -q 'sha256sum -c' "$script"; then
    pco_nogo "ERR-GO-02-SHA-OLD-001" "Old broken sha256sum -c validation still present in 02-install-engine.sh"
  fi

  if ! grep -q 'pincabos_validate_webpkg_sha "$WEB_PKG_FILE" "$WEB_PKG_SHA_FILE"' "$script"; then
    pco_nogo "ERR-GO-02-SHA-FIX-MISSING-001" "Expected fixed WEB package SHA validation not found in 02-install-engine.sh"
  fi

  if ! grep -q 'expected_sha=.*awk' "$script" && ! grep -Fq 'awk '"'"'{print $1}'"'"'' "$script"; then
    pco_warn "Unable to prove awk first-field SHA extraction by simple grep"
  else
    pco_go "SHA file first-field extraction detected"
  fi

  bash -n "$script"
  pco_go "Local 02-install-engine.sh SHA fix validated"
}



pincabos_disable_installer_autoresume_before_run03() {
  pco_step "02Z" "Disable installer autoresume before RUN_03"

  local ts=""
  local backup_dir=""

  ts="$(date +%Y%m%d-%H%M%S)"
  backup_dir="/opt/pincabos/backups/run03-autoresume-disabled-$ts"
  mkdir -p "$backup_dir"

  if [ -d /etc/systemd/system/getty@tty1.service.d ]; then
    cp -a /etc/systemd/system/getty@tty1.service.d "$backup_dir/getty@tty1.service.d" 2>/dev/null || true

    while IFS= read -r f; do
      if grep -qEi 'pincabos-autoresume-console|go-pincabos|RUN_0|REBOOT_AFTER|FINAL_REBOOT|autoresume' "$f" 2>/dev/null; then
        mv -f "$f" "$f.disabled-before-run03-$ts"
        pco_go "Disabled installer getty autoresume drop-in: $f"
      fi
    done < <(find /etc/systemd/system/getty@tty1.service.d -maxdepth 1 -type f 2>/dev/null | sort)
  fi

  if [ -f /usr/local/sbin/pincabos-autoresume-console.sh ]; then
    cp -a /usr/local/sbin/pincabos-autoresume-console.sh "$backup_dir/" 2>/dev/null || true
    mv -f /usr/local/sbin/pincabos-autoresume-console.sh "/usr/local/sbin/pincabos-autoresume-console.sh.disabled-before-run03-$ts"
    pco_go "Disabled installer autoresume helper before RUN_03"
  else
    pco_go "No installer autoresume helper active before RUN_03"
  fi

  systemctl daemon-reload >/dev/null 2>&1 || true
  systemctl reset-failed getty@tty1.service >/dev/null 2>&1 || true

  pco_go "RUN_03 cannot be auto-looped by getty autoresume"
  return 0
}

pincabos_refresh_03_before_run03() {
  pco_step "02F" "Refresh RUN_03 script and WebPkg before final validation"

  local base="${PIN_INSTALL_BASE:-https://ins.pincabos.cc/install}"
  local dst="/opt/pincabos/install/03-install-check.sh"
  local tmp="${dst}.tmp"
  local pkg_dir="/opt/pincabos/install/pkg"
  local dl_dir="/opt/pincabos/download/webpkg"
  local pkg=""
  local sha=""
  local manifest=""
  local expected=""
  local actual=""
  local name=""
  local rel=""

  mkdir -p /opt/pincabos/install "$pkg_dir" "$dl_dir"

  if ! command -v curl >/dev/null 2>&1; then
    pco_nogo "ERR-GO-RUN03-REFRESH-NOCURL" "curl is required to refresh 03-install-check.sh and WebPkg"
  fi

  if curl -fsSL --retry 3 --connect-timeout 15 "${base}/03-install-check.sh" -o "$tmp"; then
    mv -f "$tmp" "$dst"
    chmod +x "$dst"

    if bash -n "$dst"; then
      pco_go "RUN_03 script refreshed from ${base}/03-install-check.sh"
    else
      pco_nogo "ERR-GO-RUN03-REFRESH-SYNTAX" "Downloaded 03-install-check.sh failed syntax validation"
    fi
  else
    rm -f "$tmp"
    pco_nogo "ERR-GO-RUN03-REFRESH-DOWNLOAD" "Unable to refresh 03-install-check.sh from ${base}"
  fi

  for rel in \
    "pkg/pkg-pincabos-web.zst" \
    "pkg/pkg-pincabos-web.sha256" \
    "pkg/pkg-pincabos-web.manifest.json"
  do
    name="$(basename "$rel")"

    if curl -fsSL --retry 3 --connect-timeout 15 "${base}/${rel}" -o "${pkg_dir}/${name}.tmp"; then
      mv -f "${pkg_dir}/${name}.tmp" "${pkg_dir}/${name}"
      cp -a "${pkg_dir}/${name}" "${dl_dir}/${name}" 2>/dev/null || true
      pco_go "WebPkg refreshed: ${rel}"
    else
      rm -f "${pkg_dir}/${name}.tmp"
      pco_nogo "ERR-GO-RUN03-WEBPKG-REFRESH" "Unable to refresh ${rel} from ${base}"
    fi
  done

  pkg="${pkg_dir}/pkg-pincabos-web.zst"
  sha="${pkg_dir}/pkg-pincabos-web.sha256"
  manifest="${pkg_dir}/pkg-pincabos-web.manifest.json"

  [ -f "$pkg" ] || pco_nogo "ERR-GO-RUN03-WEBPKG-MISSING" "Missing refreshed WebPkg: $pkg"
  [ -f "$sha" ] || pco_nogo "ERR-GO-RUN03-WEBPKG-SHA-MISSING" "Missing refreshed WebPkg SHA: $sha"
  [ -f "$manifest" ] || pco_nogo "ERR-GO-RUN03-WEBPKG-MANIFEST-MISSING" "Missing refreshed WebPkg manifest: $manifest"

  expected="$(awk 'NF {print $1; exit}' "$sha")"
  actual="$(sha256sum "$pkg" | awk '{print $1}')"

  if [ "$expected" != "$actual" ]; then
    echo "expected=$expected"
    echo "actual  =$actual"
    pco_nogo "ERR-GO-RUN03-WEBPKG-SHA" "Refreshed WebPkg SHA mismatch"
  fi

  python3 -m json.tool "$manifest" >/dev/null \
    && pco_go "Refreshed WebPkg manifest JSON OK" \
    || pco_nogo "ERR-GO-RUN03-WEBPKG-MANIFEST-JSON" "Refreshed WebPkg manifest JSON invalid"

  if pincabos_webpkg_has_plymouth_theme "$pkg"; then
    pco_go "Refreshed WebPkg contains Plymouth final theme"
  else
    pco_nogo "ERR-GO-RUN03-WEBPKG-PLYMOUTH" "Refreshed WebPkg missing usr/share/plymouth/themes/pincabos"
  fi

  # Official engine WebPkg is allowed to ship VPX/VPinFE runtime assets under /opt/pincabos/apps.
  # It must not ship machine-local state, logs, backups, or user runtime config.
  if tar --zstd -tf "$pkg" | grep -E '(^\./|^)home/pinball/\.vpinball(/|$)|(^\./|^)home/pinball/\.config/vpinfe(/|$)|(^\./|^)opt/pincabos/logs(/|$)|(^\./|^)opt/pincabos/backups(/|$)|(^\./|^)opt/pincabos/config/backups(/|$)|(^\./|^)opt/pincabos/flags(/|$)|(^\./|^)opt/pincabos/state(/|$)' >/dev/null; then
    pco_nogo "ERR-GO-RUN03-WEBPKG-FORBIDDEN" "Refreshed WebPkg contains forbidden machine-local state/log/backup paths"
  fi

  pco_go "RUN_03 script and WebPkg refresh completed"
  return 0
}


pincabos_final_summary_countdown_reboot() {
  pco_step "FINAL" "Final summary, IP address and reboot countdown"

  local ip_summary=""
  local primary_ip=""
  local default_route=""
  local dns_summary=""
  local web_url=""
  local admin_url=""
  local console_url=""
  local flag_dir=""
  local i=""

  flag_dir="$(pincabos_flags_dir)"

  ip_summary="$(ip -4 -br addr show scope global 2>/dev/null | awk '{print $1 "=" $3}' | paste -sd ', ' - || true)"
  primary_ip="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i=1;i<=NF;i++) if ($i=="src") {print $(i+1); exit}}' || true)"
  default_route="$(ip route show default 2>/dev/null | head -n1 || true)"
  dns_summary="$(grep -h '^nameserver ' /etc/resolv.conf 2>/dev/null | awk '{print $2}' | paste -sd ', ' - || true)"

  [ -n "$ip_summary" ] || ip_summary="none"
  [ -n "$primary_ip" ] || primary_ip="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
  [ -n "$primary_ip" ] || primary_ip="unknown"
  [ -n "$default_route" ] || default_route="none"
  [ -n "$dns_summary" ] || dns_summary="none"

  if [ "$primary_ip" != "unknown" ]; then
    web_url="http://${primary_ip}/"
    admin_url="http://${primary_ip}/admin"
    console_url="http://${primary_ip}/console"
  else
    web_url="http://<ip>/"
    admin_url="http://<ip>/admin"
    console_url="http://<ip>/console"
  fi

  echo
  echo -e "${ORANGE}────────────────────────────────────────────────────────────────${NC}"
  echo -e "${ORANGE} PinCabOS - Installation completed${NC}"
  echo -e "${ORANGE}────────────────────────────────────────────────────────────────${NC}"
  echo
  echo -e "${GREEN}GO [√] RUN_03 returned GO to go-pincabos${NC}"
  echo -e "${GREEN}GO [√] Deep run cleanup completed by 03-install-check.sh${NC}"
  echo -e "${GREEN}GO [√] Final reboot is owned by go-pincabos.sh${NC}"
  echo
  echo -e "${YELLOW}System summary${NC}"
  echo -e "${YELLOW}Hostname:        $(hostname 2>/dev/null || echo unknown)${NC}"
  echo -e "${YELLOW}Primary IP:      ${primary_ip}${NC}"
  echo -e "${YELLOW}IPv4 addresses:  ${ip_summary}${NC}"
  echo -e "${YELLOW}Default route:   ${default_route}${NC}"
  echo -e "${YELLOW}DNS servers:     ${dns_summary}${NC}"
  echo
  echo -e "${YELLOW}PinCabOS access after reboot${NC}"
  echo -e "${YELLOW}WebApp:          ${web_url}${NC}"
  echo -e "${YELLOW}Admin:           ${admin_url}${NC}"
  echo -e "${YELLOW}Console:         ${console_url}${NC}"
  echo
  echo -e "${YELLOW}Final workflow flags${NC}"
  for f in \
    "$flag_dir/end-run-00" \
    "$flag_dir/end-run-01" \
    "$flag_dir/end-run-01G" \
    "$flag_dir/end-run-01H" \
    "$flag_dir/end-run-02" \
    "$flag_dir/end-run-03" \
    "$flag_dir/final-go"
  do
    if [ -f "$f" ]; then
      echo "----- $(basename "$f") -----"
      sed -n '1,10p' "$f" 2>/dev/null || true
    fi
  done

  if [ "${PINCABOS_NO_FINAL_REBOOT:-0}" = "1" ] || [ "${PINCABOS_FINAL_SUMMARY_ONLY:-0}" = "1" ]; then
    pco_warn "Final reboot skipped by PINCABOS_NO_FINAL_REBOOT/PINCABOS_FINAL_SUMMARY_ONLY"
    return 0
  fi

  pincabos_assert_final_graphical_boot_ready

  echo
  echo -e "${GREEN}GO [√] Final reboot will start after countdown${NC}"
  echo -e "${YELLOW}Press Ctrl+C only if you intentionally want to stop the final reboot.${NC}"
  echo

  for i in 10 9 8 7 6 5 4 3 2 1; do
    echo -ne "${ORANGE}Final reboot in ${i} seconds...${NC}\r"
    sleep 1
  done

  echo
  echo -e "${GREEN}GO [√] Rebooting now${NC}"

  pincabos_write_flag "final-reboot" "GO" "final reboot started by go-pincabos after final summary countdown" "0"

  sync || true

  if command -v systemctl >/dev/null 2>&1; then
    systemctl reboot
  else
    reboot
  fi

  exit 0
}


pincabos_webpkg_has_plymouth_theme() {
  local pkg="$1"
  local list_file=""

  [ -f "$pkg" ] || return 1

  list_file="$(mktemp /tmp/pincabos-webpkg-plymouth-list.XXXXXX)"
  if ! tar --zstd -tf "$pkg" > "$list_file" 2>/dev/null; then
    rm -f "$list_file"
    return 1
  fi

  if sed 's#^\./##' "$list_file" | grep -E '^usr/share/plymouth/themes/pincabos(/|$)' >/dev/null; then
    rm -f "$list_file"
    return 0
  fi

  rm -f "$list_file"
  return 1
}

pincabos_assert_final_graphical_boot_ready() {
  pco_step "FINAL-GRAPHICAL" "Assert final graphical boot before reboot"

  if command -v systemctl >/dev/null 2>&1; then
    systemctl unmask graphical.target lightdm.service display-manager.service >/dev/null 2>&1 || true
    systemctl daemon-reload >/dev/null 2>&1 || true

    systemctl set-default graphical.target >/dev/null 2>&1       && pco_go "Final default target set to graphical.target"       || pco_nogo "ERR-GO-FINAL-GRAPHICAL-TARGET" "Could not set graphical.target before final reboot"

    systemctl enable lightdm.service >/dev/null 2>&1       && pco_go "lightdm.service enabled before final reboot"       || pco_nogo "ERR-GO-FINAL-LIGHTDM-ENABLE" "Could not enable lightdm.service before final reboot"

    systemctl enable display-manager.service >/dev/null 2>&1 || true

    if systemctl get-default 2>/dev/null | grep -qx 'graphical.target'; then
      pco_go "Verified default target: graphical.target"
    else
      pco_nogo "ERR-GO-FINAL-TARGET-NOT-GRAPHICAL" "Default target is not graphical.target before final reboot"
    fi

    if systemctl is-enabled lightdm.service >/dev/null 2>&1; then
      pco_go "Verified lightdm.service enabled"
    else
      pco_nogo "ERR-GO-FINAL-LIGHTDM-NOT-ENABLED" "lightdm.service is not enabled before final reboot"
    fi
  else
    pco_warn "systemctl missing; final graphical boot readiness cannot be asserted"
  fi
}


main() {
  pco_title

  pincabos_mode_from_args "$@"

  if [ "${PINCABOS_RESET_MODE:-0}" = "1" ]; then
    pincabos_reset_flags
  fi

  if [ "${PINCABOS_RESUME_MODE:-0}" = "1" ]; then
    pincabos_show_flags
  fi

  local deviso_base=0
  local resume_after_run02=0

  if [ -f /opt/pincabos/state/deviso-base-installed ] || [ -f "$(pincabos_flag_path deviso-base-installed)" ]; then
    deviso_base=1
  fi

  if [ "${PINCABOS_SKIP_PUBLIC_BOOTSTRAP:-0}" != "1" ]; then
    pincabos_bootstrap_public_install_tree
  else
    pco_warn "PINCABOS_SKIP_PUBLIC_BOOTSTRAP=1 set; public install tree refresh skipped"
  fi

  pincabos_run_stage "00" "RUN_00 preflight summary" run_00_preflight_summary

  if [ "$deviso_base" = "1" ]; then
    pco_step "DEVISO" "PinCabOS devISO preinstalled base detected"
    pco_go "Flag detected: /opt/pincabos/state/deviso-base-installed or /opt/pincabos/flags/deviso-base-installed"
    pco_go "Heavy RUN_01 is skipped"
    pincabos_write_flag "end-run-01" "GO" "RUN_01 skipped: devISO base already installed" "0"
  else
    pco_step "ONLINE" "No devISO base flag detected; full online Ubuntu Server install"
    pco_go "RUN_01 will install base packages, dependencies, X11/LightDM/Openbox and installer Plymouth"
    pco_go "No intermediate reboot will be requested after RUN_01"

    if declare -F install_all_module_dependencies >/dev/null 2>&1; then
      install_all_module_dependencies
    fi

    if declare -F run_first_module_mod_splash >/dev/null 2>&1; then
      run_first_module_mod_splash
    fi

    if [ -f "$(pincabos_flags_dir)/dhcp4-initial-done" ]; then
      pco_go "Initial DHCP4 already completed once; skipping"
    elif declare -F run_second_module_mod_dhcp4 >/dev/null 2>&1; then
      run_second_module_mod_dhcp4
      pincabos_write_flag "dhcp4-initial-done" "GO" "Initial DHCP4 completed once before RUN_01" "0"
    else
      pco_warn "run_second_module_mod_dhcp4 missing; skipped"
    fi

    if declare -F run_third_module_mod_ssid_if_wifi >/dev/null 2>&1; then
      run_third_module_mod_ssid_if_wifi
    elif declare -F pincabos_run_mod_ssid >/dev/null 2>&1; then
      pincabos_run_mod_ssid
    fi

    pincabos_run_stage "01" "01-install-system.sh" pincabos_run_script_if_present "/opt/pincabos/install/01-install-system.sh"
    pincabos_write_flag "end-run-01" "GO" "RUN_01 completed without intermediate reboot" "0"
  fi

  # Before RUN_02, always refresh network and validate access to ins.pincabos.cc.
  # This replaces the old reboot-after-01 / autoresume path.
  if [ "${PINCABOS_RESUME_MODE:-0}" = "1" ] && { [ -f "$(pincabos_flag_path end-run-02)" ] || [ -f "$(pincabos_flag_path end-run-02Z)" ]; }; then
    resume_after_run02=1
    pco_go "RUN_02 end marker detected in resume mode; 02-install-engine.sh will not be executed again"
  else
    pco_step "01F" "Network refresh before RUN_02"
    pincabos_post_reboot_network_refresh
    pincabos_wait_install_network_ready

    pincabos_run_stage "01G" "Refresh installer files from ins.pincabos.cc" pincabos_refresh_install_files_from_ins
    pincabos_run_stage "01H" "Validate local 02 SHA fix before RUN_02" pincabos_validate_local_02_sha_fix
  fi

  if [ "$resume_after_run02" = "1" ]; then
    pco_go "RUN_02 skipped because end-run-02 already exists and --resume was used"
  elif [ -f /opt/pincabos/install/02-install-engine.sh ]; then
    pincabos_run_stage "02" "02-install-engine.sh" pincabos_run_script_if_present "/opt/pincabos/install/02-install-engine.sh"
  else
    pco_warn "02-install-engine.sh missing; RUN_02 skipped for now"
  fi

  if [ -f /opt/pincabos/install/03-install-check.sh ]; then
    pincabos_disable_installer_autoresume_before_run03
    pincabos_refresh_03_before_run03
    pincabos_run_stage "03" "03-install-check.sh" pincabos_run_script_if_present "/opt/pincabos/install/03-install-check.sh"
  else
    pco_warn "03-install-check.sh missing; RUN_03 skipped for now"
    return 1
  fi

  pincabos_write_flag "final-go" "GO" "RUN_03 returned GO; final summary and reboot requested" "0"
  pco_go "PinCabOS workflow completed with final GO report"

  pincabos_final_summary_countdown_reboot
  return 0
}

main "$@"
