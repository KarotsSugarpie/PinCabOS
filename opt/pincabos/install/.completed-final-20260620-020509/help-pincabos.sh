#!/usr/bin/env bash
# Created by Karots Sugarpie
# PINCABOS_SCRIPT_NAME="help-pincabos.sh"
# PINCABOS_SCRIPT_ROLE="PinCabOS installer help, workflow documentation, module order, flags, resume/reset usage, and support commands"
# PINCABOS_SCRIPT_REQUIRES_FILES="/opt/pincabos/install/go-pincabos.sh /opt/pincabos/install/01-install-system.sh /opt/pincabos/install/02-install-engine.sh /opt/pincabos/install/03-install-check.sh /opt/pincabos/modules/system/mod-splash.sh /opt/pincabos/modules/network/mod-dhcp4.sh /opt/pincabos/modules/network/mod-ssid.sh /opt/pincabos/install/install.json /opt/pincabos/modules/modules.json"
# PINCABOS_SCRIPT_REQUIRES_DIRS="/opt/pincabos/install /opt/pincabos/modules /opt/pincabos/flags /opt/pincabos/logs /opt/pincabos/backups"
# PINCABOS_SCRIPT_REQUIRES_COMMANDS="bash cat ls find grep sed awk df ip hostname python3 go-pincabos help-pincabos mod-splash mod-dhcp4 mod-ssid"
# PINCABOS_SCRIPT_LOG_DIR="/opt/pincabos/logs"
# PINCABOS_SCRIPT_MANIFEST="/opt/pincabos/install/install.json"

set -Eeuo pipefail

ORANGE="\033[38;5;208m"
CYAN="\033[36m"
GREEN="\033[32m"
YELLOW="\033[33m"
NC="\033[0m"

pco_title() {
  clear
  echo -e "${CYAN}────────────────────────────────────────────────────────────────${NC}"
  echo -e "${ORANGE} PinCabOS Installer Help${NC}"
  echo -e "${CYAN}────────────────────────────────────────────────────────────────${NC}"
}

pco_section() {
  echo
  echo -e "${CYAN}─► ${ORANGE}$1${CYAN} ◄────────────────────────────────────────${NC}"
}

pco_title


pco_section "Explicit install output mode"
cat <<'HELP_EXPLICIT_MODE'
Use explicit mode when you want to see every command output during installation.

Command:

  go-pincabos --explicit

Resume with full output:

  go-pincabos --resume --explicit

Reset and restart with full output:

  go-pincabos --reset --explicit

Behavior:

  - disables spinner-only display for package commands
  - shows full apt-get and command output in the terminal
  - still writes logs under /opt/pincabos/logs
  - exports PINCABOS_EXPLICIT=1 to child installers
  - useful for debugging APT, package, driver, GPU, X11, LightDM, Chrome, VPX, VPinFE, and DOF failures

Default mode keeps spinner output for cleaner end-user installation.
HELP_EXPLICIT_MODE


pco_section "Main commands"
cat <<'HELP_MAIN_COMMANDS'
Start a normal PinCabOS install:

  /opt/pincabos/install/go-pincabos.sh

Resume an interrupted install from workflow flags:

  /opt/pincabos/install/go-pincabos.sh --resume

Reset workflow flags and restart from zero:

  /opt/pincabos/install/go-pincabos.sh --reset

Show this help:

  /opt/pincabos/install/help-pincabos.sh
HELP_MAIN_COMMANDS


pco_section "Workflow flag ownership"
cat <<'HELP_FLAG_OWNERSHIP'
Workflow flags are managed only by:

  go-pincabos
  /opt/pincabos/install/go-pincabos.sh

Flags directory:

  /opt/pincabos/flags

Only go-pincabos may create, update, or delete these files:

  run-00
  end-run-00
  run-01
  end-run-01
  run-02
  end-run-02
  run-03
  end-run-03

Package scripts must not manage workflow flags.

These scripts should only return GO/NOGO exit codes and write their own logs:

  01-install-system.sh
  02-install-engine.sh
  03-install-check.sh
  pkg-*.sh

Resume mode:

  go-pincabos --resume

Reset mode:

  go-pincabos --reset
HELP_FLAG_OWNERSHIP


pco_section "Workflow flags"
cat <<'HELP_FLAGS'
PinCabOS workflow flags are stored here:

  /opt/pincabos/flags

Expected run flags:

  run-00       RUN_00 preflight started
  end-run-00   RUN_00 preflight completed

  run-01       01-install-system.sh started
  end-run-01   01-install-system.sh completed

  run-02       02-install-engine.sh started
  end-run-02   02-install-engine.sh completed

  run-03       03-install-check.sh started
  end-run-03   03-install-check.sh completed

Resume mode must read these flags and continue from the correct step.
Reset mode must remove workflow flags and restart from zero.
HELP_FLAGS


pco_section "mod-splash notes"
cat <<'HELP_MOD_SPLASH'
mod-splash applies:

  - PinCabOS hostname
  - /etc/motd splash
  - colored root prompt
  - colored pinball prompt when the pinball user exists
  - SSH root/password access

The prompt marker used by the module is:

  BEGIN PINCABOS COLORED PROMPT

The verification must check the same marker that the module writes.
HELP_MOD_SPLASH


pco_section "Module order"
cat <<'HELP_MODULES'
go-pincabos.sh must run modules in this order before the main installer flow:

  1) mod-splash.sh
     Path:
       /opt/pincabos/modules/system/mod-splash.sh

     Purpose:
       Apply PinCabOS splash, hostname, root SSH access, and shell prompts.

  2) mod-dhcp4.sh
     Path:
       /opt/pincabos/modules/network/mod-dhcp4.sh

     Purpose:
       Detect wired interfaces, reset DHCP4, validate IPv4, gateway, DNS, and connectivity.

  3) mod-ssid.sh
     Path:
       /opt/pincabos/modules/network/mod-ssid.sh

     Purpose:
       Run only when Wi-Fi hardware is detected.
       Scan valid SSIDs, allow manual hidden SSID mode, ask for Wi-Fi key securely,
       write Wi-Fi DHCP4 configuration, and validate network connectivity.
HELP_MODULES

pco_section "RUN_00 preflight"
cat <<'HELP_RUN00'
go-pincabos.sh must start with RUN_00 before calling 01-install-system.sh.

RUN_00 must:

  - create /opt/pincabos/flags/run-00
  - display a summary
  - show available disk space
  - validate root privileges
  - validate required install paths
  - validate that 01-install-system.sh is available
  - create /opt/pincabos/flags/end-run-00 with GO or NOGO status
  - block the install if RUN_00 is NOGO

Typical RUN_00 summary:

  Hostname
  Operating system
  IPv4 addresses
  Default route
  DNS servers
  Available disk space
  Install path
  Log path
  Flag path
HELP_RUN00

pco_section "Dependency rule"
cat <<'HELP_DEPS'
go-pincabos.sh must install all dependencies required by modules before running them.

Required module dependencies include:

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

Required module commands include:

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
HELP_DEPS

pco_section "Language rule"
cat <<'HELP_LANGUAGE'
All user-facing text displayed by PinCabOS modules and .sh scripts must be in English.

This includes:

  echo output
  read prompts
  menus
  summaries
  pco_step messages
  pco_go messages
  pco_warn messages
  pco_nogo messages
  installer messages
  validation messages
  error messages

French may be used in conversation, but scripts/modules should display English unless explicitly requested otherwise.
HELP_LANGUAGE

pco_section "Manifest rule"
cat <<'HELP_MANIFEST'
Every created or modified PinCabOS .sh script must also update the appropriate manifest JSON.

Install scripts:

  /opt/pincabos/install/install.json

Module scripts:

  /opt/pincabos/modules/modules.json

Each script header should include:

  Created by Karots Sugarpie
  PINCABOS_SCRIPT_NAME
  PINCABOS_SCRIPT_ROLE
  PINCABOS_SCRIPT_REQUIRES_FILES
  PINCABOS_SCRIPT_REQUIRES_DIRS when applicable
  PINCABOS_SCRIPT_REQUIRES_PACKAGES when applicable
  PINCABOS_SCRIPT_REQUIRES_COMMANDS
  PINCABOS_SCRIPT_LOG_DIR
  PINCABOS_SCRIPT_MANIFEST
HELP_MANIFEST

pco_section "No blind patch rule"
cat <<'HELP_PATCH'
Before changing a PinCabOS script:

  1) Audit the exact file
  2) Identify the exact block
  3) Explain the likely cause
  4) Create a backup
  5) Apply only targeted reversible changes
  6) Validate syntax with bash -n
  7) Refresh manifests
  8) Show proof

Do not use broad blind replacements.
HELP_PATCH

pco_section "Important paths"
cat <<'HELP_PATHS'
Installer path:

  /opt/pincabos/install

Modules path:

  /opt/pincabos/modules

Workflow flags:

  /opt/pincabos/flags

Logs:

  /opt/pincabos/logs

Backups:

  /opt/pincabos/backups

Install manifest:

  /opt/pincabos/install/install.json

Modules manifest:

  /opt/pincabos/modules/modules.json
HELP_PATHS


pco_section "PATH commands"
cat <<'HELP_PATH_COMMANDS'
PinCabOS shell scripts must be executable and available from PATH without typing .sh.

Main commands:

  go-pincabos
  help-pincabos
  01-install-system
  02-install-engine
  03-install-check

Module commands:

  mod-splash
  mod-dhcp4
  mod-ssid

Utility commands:

  pincabos-refresh-manifests

Command links are stored in:

  /usr/local/bin

Examples:

  go-pincabos
  go-pincabos --resume
  go-pincabos --reset
  help-pincabos
  mod-dhcp4
  mod-ssid
HELP_PATH_COMMANDS


pco_section "Quick diagnostics"
cat <<'HELP_DIAG'
Validate shell scripts:

  bash -n /opt/pincabos/install/go-pincabos.sh
  bash -n /opt/pincabos/install/help-pincabos.sh
  bash -n /opt/pincabos/modules/system/mod-splash.sh
  bash -n /opt/pincabos/modules/network/mod-dhcp4.sh
  bash -n /opt/pincabos/modules/network/mod-ssid.sh

Show workflow flags:

  find /opt/pincabos/flags -maxdepth 1 -type f -print | sort

Show recent logs:

  ls -lah /opt/pincabos/logs | tail -n 40

Validate manifests:

  python3 -m json.tool /opt/pincabos/install/install.json >/dev/null
  python3 -m json.tool /opt/pincabos/modules/modules.json >/dev/null
HELP_DIAG



pco_section "VPinball binary rule"
cat <<'HELP_VPX_BGFX_ONLY'
PinCabOS must use the BGFX VPinball binary only.

Required binary names:

  VPinballX-BGFX
  vpinballX-BGFX
  VPinballX_BGFX
  vpinballX_BGFX

Rule:

  - Use BGFX only.
  - Do not use generic VPinballX* discovery if it can select the wrong binary.
  - 02-install-engine.sh must select BGFX only.
  - Runtime fallback must point to VPinballX-BGFX.
HELP_VPX_BGFX_ONLY



pco_section "pkg-vpx-bgfx-runtime dependencies"
cat <<'HELP_PKG_BGFX_ZST'
The 01-install-system package pkg-vpx-bgfx-runtime installs runtime dependencies for VPinballX-BGFX.

Archive support included in this package:

  zstd
  libzstd1

This is for .zst / .tar.zst archive support and does not modify 02-install-engine.sh.
HELP_PKG_BGFX_ZST



pco_section "RUN_01 ISO pause and post-reboot flow"
cat <<'HELP_RUN01_ISO'
After RUN_01, go-pincabos performs the ISO/install transition phase.

RUN_01 transition behavior:

  - blocks graphical startup before the first reboot
  - stops/disables lightdm.service when present
  - stops openbox if it is already running
  - downloads installer wallpaper from ins.pincabos.cc/install when available
  - copies installer wallpaper into the PinCabOS Plymouth theme
  - sets GRUB to quiet splash
  - refreshes initramfs and GRUB when commands are available
  - pauses the ISO/install workflow until a key is pressed
  - creates the reboot-after-01 flag
  - reboots

After reboot with go-pincabos --resume:

  - re-runs DHCP4 module
  - re-runs optional SSID module when Wi-Fi is detected
  - refreshes installer files from ins.pincabos.cc/install
  - starts RUN_02 by calling 02-install-engine.sh

Scope rule:

  This flow is owned by go-pincabos.
  Package scripts do not manage workflow flags.
  02-install-engine.sh is called only when RUN_02 starts.
HELP_RUN01_ISO


pco_section "01-install-system modular packages"
cat <<'HELP_01_MODULAR'
01-install-system.sh is a local package orchestrator.

Important rules:

  - It does not manage workflow flags.
  - It does not create files in /opt/pincabos/flags.
  - It does not reboot.
  - It returns exit 0 for GO.
  - It returns exit 1 for NOGO.
  - go-pincabos is the only workflow flag and reboot manager.

Package order:

  01) pkg-apt-base
  02) pkg-monitoring
  03) pkg-python
  04) pkg-nginx (runtime disable guard)
  05) pkg-x11
  06) pkg-lightdm
  07) pkg-openbox
  08) pkg-chrome
  09) pkg-plymouth
  10) pkg-vpx-bgfx-runtime
  11) pkg-vpinfe-runtime
  12) pkg-libdof-runtime
  13) pkg-system-validation

Main command:

  01-install-system

Package commands:

  pkg-apt-base
  pkg-monitoring
  pkg-python
  pkg-nginx (runtime disable guard)
  pkg-x11
  pkg-lightdm
  pkg-openbox
  pkg-chrome
  pkg-plymouth
  pkg-vpx-bgfx-runtime
  pkg-vpinfe-runtime
  pkg-libdof-runtime
  pkg-system-validation
HELP_01_MODULAR


pco_section "Current expected go-pincabos.sh order"
cat <<'HELP_ORDER'
Current expected go-pincabos.sh order:

  Public install tree bootstrap from ins.pincabos.cc/install
  RUN_00 preflight summary
  Install required module dependencies
  mod-splash.sh
  mod-dhcp4.sh
  mod-ssid.sh if Wi-Fi hardware exists
  01-install-system.sh
  02-install-engine.sh
  03-install-check.sh
HELP_ORDER

echo


pco_section "BGFX clean public reinstall guarantees"
cat <<'HELP_BGFX_CLEAN'
Current clean reinstall guarantees:

  - go-pincabos refreshes the complete public install tree from install.json before RUN_00
  - required packages, package installers and network modules are downloaded before 01-install-system.sh
  - RUN_02 is not marked completed before it actually runs
  - the autoresume console performs DHCP4/SSID once, then go-pincabos skips duplicate 01F network reruns
  - 02-install-engine normalizes VPX BGFX paths:
      /opt/pincabos/apps/vpinball/current/VPinballX-BGFX
      /opt/pincabos/apps/vpinball/VPinballX-BGFX
      /opt/pincabos/apps/vpinball/VPinballX
      /opt/pincabos/bin/vpx.sh
  - PinCabOS uses direct ports: WebApp 80, ttyd 8090, VPinFE 8000/8001. is disabled at runtime.
  - WebApp service compatibility is provided by pincabos-webapp.service and legacy pincabos-web.service
  - 03-install-check creates/validates pincabos-frontend.service compatibility wrapper when missing
HELP_BGFX_CLEAN

echo -e "${GREEN}GO [√] PinCabOS help displayed${NC}"


pco_section "X11 package compatibility"
cat <<'HELP_X11_COMPAT'
pkg-x11 uses current Ubuntu-compatible policykit packages:

  polkitd
  pkexec

Do not use policykit-1 on releases where APT reports Candidate: (none).

The shared package helper checks APT Candidate availability before passing packages to apt-get install.
HELP_X11_COMPAT



pco_section "RUN_01 ISO pause flags"
cat <<'HELP_RUN01_FLAGS'
RUN_01 ISO transition flags:

  run-01
  end-run-01
  end-run-01E
  reboot-after-01

Rules:

  - end-run-01 means 01-install-system.sh completed.
  - end-run-01E means the ISO pause actions completed and reboot was requested.
  - reboot-after-01 means the next resume is post-reboot.
  - RUN_02 must not start until reboot-after-01 exists.
  - If RUN_02 flags exist before reboot-after-01, they are premature and must be removed.
HELP_RUN01_FLAGS



pco_section "02-install-engine Web package worker"
cat <<'HELP_02_WEB_PACKAGE'
02-install-engine.sh is called by go-pincabos during RUN_02.

It does not manage RUN flags.

Current package source:
  https://ins.pincabos.cc/install/pkg/pkg-pincabos-web.zst
  https://ins.pincabos.cc/install/pkg/pkg-pincabos-web.sha256
  https://ins.pincabos.cc/install/pkg/pkg-pincabos-web.manifest.json

Worker behavior:
  - downloads the official pkg-pincabos-web.zst package
  - verifies SHA256 when pkg-pincabos-web.sha256 is available
  - validates that the package contains no VPX runtime
  - validates that the package contains no VPinFE runtime
  - validates that the package contains no logs/backups
  - validates no active legacy GL usage
  - extracts the package to /
  - rebuilds Python venv
  - validates Nginx
  - reloads/restarts PinCabOS Web services
  - installs sudoers
  - recreates PATH commands and global default paths

go-pincabos remains the only workflow owner for RUN flags, resume, reset and reboot.
HELP_02_WEB_PACKAGE

# === PINCABOS MANAGED HELP: FINAL VALIDATION BEGIN ===
pco_section "Final validation and final reboot"
cat <<'HELP_FINAL_VALIDATION'
Final install stage:

  03-install-check

Role:

  - validates PinCabOS WebApp direct-port routes
  - validates and enables LightDM autologin for user pinball
  - ensures the PinCabOS Openbox session exists
  - enables pincabos-frontend.service and pincabos-vpinfe.service
  - applies the final PinCabOS Plymouth theme
  - hides the GRUB menu with timeout 0
  - normalizes GRUB_CMDLINE_LINUX_DEFAULT to "quiet splash"
  - writes a final GO/NOGO report under /opt/pincabos/logs

Workflow rule:

  - 03-install-check does not manage workflow run/end flags
  - go-pincabos owns workflow flags under /opt/pincabos/flags
  - after RUN_03 returns GO, go-pincabos performs the final reboot

Debug override:

  PINCABOS_NO_FINAL_REBOOT=1 go-pincabos --resume --explicit

This lets you inspect the final GO/NOGO report without rebooting.
HELP_FINAL_VALIDATION
# === PINCABOS MANAGED HELP: FINAL VALIDATION END ===


pco_section "Final root SSH policy"
cat <<'HELP_ROOT_SSH'
03-install-check.sh must finalize and validate:

  - root password reset to the PinCabOS default
  - sshd syntax valid
  - PermitRootLogin yes
  - PasswordAuthentication yes
  - ssh.service or sshd.service enabled and active
  - SSH port 22 listening when available

This is intentional for PinCabOS development/install access.
HELP_ROOT_SSH



pco_section "Plymouth ownership"
cat <<'HELP_PLYMOUTH_OWNER'
Plymouth ownership:

  - RUN_01 / installer pause uses the installer Plymouth theme.
  - RUN_02 must not apply the final loading Plymouth theme.
  - RUN_03 applies the final loading Plymouth theme once, near the end of final validation.

This avoids duplicate initramfs/theme application and keeps the final boot theme owned by 03-install-check.sh.
HELP_PLYMOUTH_OWNER



pco_section "Final graphical boot guard"
cat <<'HELP_GRAPHICAL_GUARD'
03-install-check.sh installs a final graphical boot guard:

  /usr/local/sbin/pincabos-final-graphical-guard.sh
  /etc/systemd/system/pincabos-final-graphical-guard.service

Purpose:

  - force graphical.target after install
  - enable/start LightDM if the machine falls back to console login
  - ensure VPinFE/WebApp/Console services are enabled
  - remove frontend hold flags
  - restart VPinFE once X is available

This protects the final boot path after go-pincabos returns GO and reboots.
HELP_GRAPHICAL_GUARD



pco_section "Final LightDM hard guard"
cat <<'HELP_LIGHTDM_HARDGUARD'
If final boot falls to text login, PinCabOS uses a hard guard:

  - pincabos-final-graphical-guard.service
  - pincabos-switch-graphical-vt.service
  - getty@tty1 ExecStartPre fallback

This forces display-manager.service to LightDM, starts LightDM, waits for X, switches to tty7, and restarts VPinFE.
HELP_LIGHTDM_HARDGUARD

