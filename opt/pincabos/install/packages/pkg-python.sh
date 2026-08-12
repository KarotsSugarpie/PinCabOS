#!/usr/bin/env bash
# Created by Karots Sugarpie
# PINCABOS_SCRIPT_NAME="pkg-python.sh"
# PINCABOS_SCRIPT_ROLE="Install Python runtime and modules used by PinCabOS WebApp, tools, USB/LED-Wiz, YAML, and diagnostics"
# PINCABOS_SCRIPT_REQUIRES_FILES="/opt/pincabos/install/packages/pkg-lib.sh"
# PINCABOS_SCRIPT_REQUIRES_PACKAGES="python3 python3-venv python3-pip python3-dev python3-flask python3-requests python3-yaml python3-psutil python3-usb python3-serial"
# PINCABOS_SCRIPT_REQUIRES_COMMANDS="python3 pip3"
# PINCABOS_SCRIPT_LOG_DIR="/opt/pincabos/logs"
# PINCABOS_SCRIPT_MANIFEST="/opt/pincabos/install/install.json"

PKG_NAME="pkg-python"
PKG_TITLE="Python runtime"
source /opt/pincabos/install/packages/pkg-lib.sh

main() {
  pkg_start
  pco_step "01" "Install Python packages"
  apt_install_available \
    python3 python3-venv python3-pip python3-dev \
    python3-flask python3-requests python3-yaml python3-psutil python3-usb python3-serial

  pco_step "02" "Validate Python imports"
  python3 - <<'PYTEST'
import sys
mods = ["flask", "requests", "yaml", "psutil"]
missing = []
for mod in mods:
    try:
        __import__(mod)
    except Exception:
        missing.append(mod)
if missing:
    print("Missing Python modules:", ", ".join(missing))
    sys.exit(1)
print("Python imports OK")
PYTEST
  pco_go "Python runtime validated"
  pkg_done
}

main "$@"
