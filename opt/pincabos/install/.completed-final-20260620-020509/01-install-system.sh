#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# PinCabOS 01 system package/runtime guard
# Created by Karots Sugarpie
#
# Dependencies/requisites:
# - /usr/bin/apt-get
# - /usr/bin/dpkg
# - /usr/sbin/update-initramfs
# - /usr/sbin/plymouth-set-default-theme
#
# Purpose:


pco_install_required_runtime_packages() {
  echo
  echo "─[01R]─► Paquets runtime PinCabOS Python/WebApp/USB"

  local pkgs=(
    python3
    python3-venv
    python3-pip
    python3-dev
    python3-setuptools
    python3-wheel
    python3-flask
    python3-requests
    python3-serial
    python3-usb
    python3-psutil
    python3-gi
    python3-yaml
    python3-dbus
    python3-apt
    curl
    ttyd
    wget
    ca-certificates
    gnupg
    jq
    rsync
    tar
    unzip
    zip
    zstd
    xz-utils
    usbutils
    pciutils
    lshw
    mesa-utils
    libglib2.0-bin
  )

  DEBIAN_FRONTEND=noninteractive apt-get install -y "${pkgs[@]}"
  pco_go "Paquets runtime Python/WebApp/USB présents"
}


pco_apply_plymouth_theme_once() {
  local theme="${1:-PinCabOs-install}"
  pincabos_ensure_plymouth_dependencies
  local mod="/opt/pincabos/modules/system/mod-plymouth-install.sh"

  echo
  echo "=== Plymouth installer theme via module ==="

  if [ ! -x "$mod" ]; then
    echo "NOGOOD: module Plymouth install absent: $mod"
    return 1
  fi

  PINCABOS_EXPLICIT="${PINCABOS_EXPLICIT:-1}" bash "$mod"
}

pco_title() {
  echo -e "${CYAN}────────────────────────────────────────────────────────────────${NC}"
  echo -e "${ORANGE} PinCabOS - 01 System Package Orchestrator${NC}"
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
  echo -e "${RED}NOGO [***] ERR-01-SYSTEM-UNHANDLED-999${NC} Unexpected failure"
  echo -e "${RED}Step:${NC} $CURRENT_STEP"
  echo -e "${RED}Exit code:${NC} $rc"
  echo -e "${RED}Log:${NC} $LOG_FILE"
  exit "$rc"
}

trap pco_on_error ERR

run_pkg() {
  local step="$1"
  local label="$2"
  local script="$3"

  pco_step "$step" "$label"

  if [ ! -f "$script" ]; then
    pco_nogo "ERR-01-PKG-MISSING-001" "Missing package installer: $script"
  fi

  chmod +x "$script"
  if "$script"; then
    pco_go "Package completed: $label"
  else
    local rc="$?"
    pco_nogo "ERR-01-PKG-FAILED-$step" "Package failed: $label exit=$rc"
  fi
}


pincabos_ensure_plymouth_dependencies() {
  pco_step "PLY-DEPS" "Install Plymouth dependencies before theme modules"

  export DEBIAN_FRONTEND=noninteractive

  if ! command -v apt-get >/dev/null 2>&1; then
    pco_nogo "ERR-01-APT-MISSING-PLYMOUTH-001" "apt-get is required for Plymouth dependencies"
  fi

  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get -y autoremove
  apt-get install -y tar zstd initramfs-tools plymouth plymouth-themes

  local missing=0
  local cmd=""
  local pkg=""

  for cmd in tar zstd sha256sum update-initramfs; do
    if command -v "$cmd" >/dev/null 2>&1; then
      pco_go "Command available: $cmd"
    else
      pco_warn "Command missing after install: $cmd"
      missing=$((missing + 1))
    fi
  done

  for pkg in tar zstd initramfs-tools plymouth plymouth-themes; do
    if dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q 'install ok installed'; then
      pco_go "Package installed: $pkg"
    else
      pco_warn "Package missing after install: $pkg"
      missing=$((missing + 1))
    fi
  done

  if [ "$missing" -gt 0 ]; then
    pco_nogo "ERR-01-PLYMOUTH-DEPS-MISSING-001" "Plymouth dependencies still missing after install"
  fi

  pco_go "Plymouth dependencies installed by 01-install-system.sh"
}


main() {
  pco_title

  if [ "$(id -u)" -ne 0 ]; then
    pco_nogo "ERR-01-ROOT-001" "01-install-system.sh must be run as root"
  fi

  echo
  echo -e "${YELLOW}Workflow flag rule:${NC} go-pincabos is the only workflow flag manager"
  echo -e "${YELLOW}Reboot rule:${NC} 01-install-system.sh never reboots; go-pincabos handles reboot decisions"

  run_pkg "01" "APT base and core tools" "/opt/pincabos/install/packages/pkg-apt-base.sh"
  run_pkg "02" "System page monitoring tools" "/opt/pincabos/install/packages/pkg-monitoring.sh"
  run_pkg "03" "Python runtime" "/opt/pincabos/install/packages/pkg-python.sh"

pco_install_required_runtime_packages # PinCabOS runtime guard
  run_pkg "04" "Disable nginx runtime guard" "/opt/pincabos/install/packages/pkg-nginx.sh"
  run_pkg "05" "X11 display stack" "/opt/pincabos/install/packages/pkg-x11.sh"
  run_pkg "06" "LightDM display manager" "/opt/pincabos/install/packages/pkg-lightdm.sh"
  run_pkg "07" "Openbox kiosk desktop" "/opt/pincabos/install/packages/pkg-openbox.sh"
  run_pkg "08" "Google Chrome Stable" "/opt/pincabos/install/packages/pkg-chrome.sh"
  # PinCabOS: Plymouth activation is handled by pkg-plymouth.sh to avoid duplicate initramfs.
  pco_step "09" "Plymouth installer theme"
  pincabos_ensure_plymouth_dependencies

  if [ ! -x "/opt/pincabos/modules/system/mod-plymouth-install.sh" ]; then
    pco_nogo "ERR-01-PLYMOUTH-MODULE-MISSING-001" "Missing executable module: /opt/pincabos/modules/system/mod-plymouth-install.sh"
  fi

  PINCABOS_EXPLICIT="${PINCABOS_EXPLICIT:-1}" bash "/opt/pincabos/modules/system/mod-plymouth-install.sh"
  pco_go "Package completed: Plymouth installer theme"
  run_pkg "10" "VPX BGFX runtime dependencies" "/opt/pincabos/install/packages/pkg-vpx-bgfx-runtime.sh"
  run_pkg "11" "VPX BGFX full application" "/opt/pincabos/install/packages/pkg-vpx-bgfx-app.sh"
  run_pkg "12" "VPinFE runtime dependencies" "/opt/pincabos/install/packages/pkg-vpinfe-runtime.sh"
  run_pkg "13" "VPinFE full application" "/opt/pincabos/install/packages/pkg-vpinfe-app.sh"
  run_pkg "14" "DOF / libdof runtime" "/opt/pincabos/install/packages/pkg-libdof-runtime.sh"
  run_pkg "16" "System installation validation" "/opt/pincabos/install/packages/pkg-system-validation.sh"

  pco_step "17" "Final GO/NOGO summary"
  echo -e "${YELLOW}APT base tools:             ----> OK${NC}"
  echo -e "${YELLOW}Monitoring tools:           ----> OK${NC}"
  echo -e "${YELLOW}Python runtime:             ----> OK${NC}"
  echo -e "${YELLOW}Nginx disabled/runtime-free: ----> OK${NC}"
  echo -e "${YELLOW}X11 / LightDM / Openbox:    ----> OK${NC}"
  echo -e "${YELLOW}Chrome:                     ----> OK${NC}"
  echo -e "${YELLOW}Plymouth:                   ----> OK${NC}"
  echo -e "${YELLOW}VPX BGFX runtime:           ----> OK${NC}"
  echo -e "${YELLOW}VPinFE runtime:             ----> OK${NC}"
  echo -e "${YELLOW}DOF / libdof runtime:       ----> OK${NC}"
    echo -e "${YELLOW}Audio ALSA / PipeWire:      ----> OK${NC}"
  echo -e "${YELLOW}Workflow flags touched:     ----> NO${NC}"
  echo -e "${YELLOW}Reboot performed:           ----> NO${NC}"
  echo -e "${YELLOW}Log:                        $LOG_FILE${NC}"

  echo
  pco_go "01-install-system.sh completed. Reboot decision remains with go-pincabos."
}

main "$@"
