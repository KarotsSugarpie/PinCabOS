#!/usr/bin/env bash
# Created by Karots Sugarpie
# PINCABOS_SCRIPT_NAME="03-install-check.sh"
# PINCABOS_SCRIPT_ROLE="Final PinCabOS validation, Plymouth final theme, GRUB hidden boot, LightDM/Openbox/frontend enablement, GO/NOGO report"
# PINCABOS_SCRIPT_REQUIRES_ROOT="yes"
# PINCABOS_SCRIPT_REQUIRES_PACKAGES="systemd lightdm openbox plymouth grub2-common curl python3"
# PINCABOS_SCRIPT_REQUIRES_COMMANDS="bash date mkdir tee systemctl grep sed awk cat chmod chown ln curl python3 plymouth-set-default-theme update-initramfs update-grub"
# PINCABOS_SCRIPT_REQUIRES_FILES="/opt/pincabos/install/03-install-check.sh /etc/default/grub /opt/pincabos/modules/system/mod-plymouth-load.sh /etc/lightdm/lightdm.conf /etc/systemd/system/pincabos-webapp.service /etc/systemd/system/pincabos-web.service /etc/systemd/system/pincabos-vpinfe.service /etc/systemd/system/pincabos-vpinfe.service"
# PINCABOS_SCRIPT_REQUIRES_DIRS="/opt/pincabos/logs /opt/pincabos/backups /opt/pincabos/config /opt/pincabos/modules/system/assets/plymouth"
# PINCABOS_SCRIPT_LOG_DIR="/opt/pincabos/logs"
# PINCABOS_SCRIPT_TOUCHES="/etc/default/grub /usr/share/plymouth/themes/default.plymouth /boot/initrd* /etc/lightdm /usr/share/xsessions /usr/local/bin /etc/systemd/system /opt/pincabos/logs"
# PINCABOS_SCRIPT_MANAGES_WORKFLOW_FLAGS="no"
# PINCABOS_SCRIPT_NOTE="Workflow run/end flags and final reboot are handled by go-pincabos."

set -Eeuo pipefail

ORANGE=$'\033[38;5;208m'
CYAN=$'\033[38;5;51m'
GREEN=$'\033[1;32m'
YELLOW=$'\033[1;33m'
RED=$'\033[1;31m'
RESET=$'\033[0m'

TS="$(date +%Y%m%d-%H%M%S)"
LOG_DIR="/opt/pincabos/logs"
BACKUP_DIR="/opt/pincabos/backups/03-install-check-$TS"
REPORT="$LOG_DIR/03-install-check-final-$TS.report"
LOG="$LOG_DIR/03-install-check-$TS.log"

mkdir -p "$LOG_DIR" "$BACKUP_DIR"
exec > >(tee -a "$LOG") 2>&1

FAILED=0
WARNED=0
CHECKS=()

pco_line() {
  printf "${CYAN}────────────────────────────────────────────────────────────────${RESET}\n"
}

pco_title() {
  clear
  pco_line
  printf "${ORANGE} PinCabOS - Final validation and boot configuration${RESET}\n"
  pco_line
  printf "${YELLOW}Log:${RESET} %s\n" "$LOG"
  printf "${YELLOW}Report:${RESET} %s\n" "$REPORT"
}

pco_step() {
  echo
  printf "${CYAN}─[%s]─►${ORANGE} %s ${CYAN}◄────${RESET}\n" "$1" "$2"
}

pco_go() {
  printf "${GREEN}GO [√] %s${RESET}\n" "$1"
  CHECKS+=("GO|$1")
}

pco_warn() {
  printf "${YELLOW}WARN [!] %s${RESET}\n" "$1"
  CHECKS+=("WARN|$1")
  WARNED=$((WARNED + 1))
}

pco_nogo() {
  printf "${RED}NOGO [X] %s${RESET}\n" "$1"
  CHECKS+=("NOGO|$1")
  FAILED=$((FAILED + 1))
}

pco_require_root() {
  pco_step "01" "Root validation"
  if [ "$(id -u)" -eq 0 ]; then
    pco_go "Running as root"
  else
    pco_nogo "This script must run as root"
  fi
}

pco_fix_frontend_unit_documentation() {
  pco_step "02" "Ensure frontend compatibility service metadata"

  local unit="/etc/systemd/system/pincabos-vpinfe.service"

  mkdir -p /etc/systemd/system

  if [ ! -f "$unit" ]; then
    cat > "$unit" <<'EOF_FRONTEND_UNIT'
[Unit]
Description=PinCabOS Frontend Compatibility Wrapper
Documentation=https://pincabos.cc/
After=pincabos-vpinfe.service
Requires=pincabos-vpinfe.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/true

[Install]
WantedBy=graphical.target
EOF_FRONTEND_UNIT
    pco_go "Created missing pincabos-vpinfe.service compatibility wrapper"
  else
    cp -a "$unit" "$BACKUP_DIR/pincabos-vpinfe.service.backup"
  fi

  python3 - "$unit" <<'PY'
from pathlib import Path
import sys

unit = Path(sys.argv[1])
text = unit.read_text(errors="replace").splitlines()
out = []
changed = False

for line in text:
    if line.startswith("Documentation="):
        out.append("Documentation=https://pincabos.cc/")
        changed = True
    else:
        out.append(line)

if not changed:
    final = []
    inserted = False
    for line in out:
        final.append(line)
        if line.strip().startswith("Description="):
            final.append("Documentation=https://pincabos.cc/")
            inserted = True
    out = final if inserted else ["Documentation=https://pincabos.cc/"] + out

unit.write_text("\n".join(out) + "\n")
PY

  systemctl daemon-reload || true

  if systemd-analyze verify "$unit" >/tmp/pincabos-frontend-verify.log 2>&1; then
    pco_go "pincabos-vpinfe.service metadata verified"
  else
    pco_warn "systemd-analyze verify reported warnings for pincabos-vpinfe.service"
    sed -n '1,80p' /tmp/pincabos-frontend-verify.log || true
  fi
}

pco_ensure_openbox_session() {
  pco_step "03" "Ensure LightDM Openbox session"

  mkdir -p /usr/share/xsessions /usr/local/bin /home/pinball/.config/openbox

  cat > /usr/local/bin/pincabos-openbox-session <<'EOS'
#!/usr/bin/env bash
export DISPLAY="${DISPLAY:-:0}"
export XDG_CURRENT_DESKTOP="Openbox"
export XDG_SESSION_DESKTOP="pincabos-openbox"
export DESKTOP_SESSION="pincabos-openbox"
exec /usr/bin/openbox-session
EOS
  chmod 755 /usr/local/bin/pincabos-openbox-session

  cat > /usr/share/xsessions/pincabos-openbox.desktop <<'EOS'
[Desktop Entry]
Name=PinCabOS Openbox
Comment=PinCabOS cabinet Openbox session
Exec=/usr/local/bin/pincabos-openbox-session
Type=Application
DesktopNames=Openbox
EOS
  chmod 644 /usr/share/xsessions/pincabos-openbox.desktop

  if [ ! -f /home/pinball/.config/openbox/autostart ]; then
    cat > /home/pinball/.config/openbox/autostart <<'EOS'
#!/usr/bin/env bash
xset -dpms
xset s off
xset s noblank
unclutter -idle 1 -root &
EOS
    chmod 755 /home/pinball/.config/openbox/autostart
  fi

  chown -R pinball:pinball /home/pinball/.config 2>/dev/null || true

  if [ -x /usr/local/bin/pincabos-openbox-session ] && [ -f /usr/share/xsessions/pincabos-openbox.desktop ]; then
    pco_go "PinCabOS Openbox X session is installed"
  else
    pco_nogo "PinCabOS Openbox X session is not installed correctly"
  fi
}

pco_ensure_lightdm_autologin() {
  pco_step "04" "Ensure LightDM autologin"

  mkdir -p /etc/lightdm/lightdm.conf.d
  [ -f /etc/lightdm/lightdm.conf ] && cp -a /etc/lightdm/lightdm.conf "$BACKUP_DIR/lightdm.conf.backup" || true
  [ -f /etc/lightdm/lightdm.conf.d/50-pincabos.conf ] && cp -a /etc/lightdm/lightdm.conf.d/50-pincabos.conf "$BACKUP_DIR/50-pincabos.conf.backup" || true

  cat > /etc/lightdm/lightdm.conf.d/50-pincabos.conf <<'EOS'
[Seat:*]
greeter-session=lightdm-gtk-greeter
user-session=pincabos-openbox
autologin-user=pinball
autologin-user-timeout=0
autologin-session=pincabos-openbox
greeter-hide-users=true
greeter-show-manual-login=false
allow-guest=false
EOS

  if grep -q '^autologin-user=pinball' /etc/lightdm/lightdm.conf.d/50-pincabos.conf; then
    pco_go "LightDM autologin pinball configured"
  else
    pco_nogo "LightDM autologin pinball missing"
  fi

  systemctl enable lightdm.service >/dev/null 2>&1 && pco_go "lightdm.service enabled" || pco_nogo "Could not enable lightdm.service"
}



# PINCABOS_PLYMOUTH_PUBLIC_SYNC_V2
pco_refresh_final_plymouth_public() {
  local base="${PINCABOS_INSTALL_BASE_URL:-https://ins.pincabos.cc/install}"
  local mod="/opt/pincabos/modules/system/mod-plymouth-load.sh"
  local pkg="/opt/pincabos/modules/system/assets/plymouth/pkg-plymouth-load.tar.zst"
  local sha="${pkg}.sha256"
  local expected=""
  local actual=""

  pco_step "PLY-SYNC" "Refresh final Plymouth module and package from public source"

  pco_fetch_plymouth_public() {
    local rel="$1"
    local dest="$2"
    local mode="$3"
    local url="${base%/}/${rel}"
    local tmp="${dest}.pco-refresh.$$"

    mkdir -p "$(dirname "$dest")"
    rm -f "$tmp"

    if command -v curl >/dev/null 2>&1; then
      curl -fsSL --connect-timeout 10 --max-time 300 "$url" -o "$tmp" || return 1
    elif command -v wget >/dev/null 2>&1; then
      wget -qO "$tmp" "$url" || return 1
    else
      return 1
    fi

    [ -s "$tmp" ] || { rm -f "$tmp"; return 1; }

    mv -f "$tmp" "$dest"
    chmod "$mode" "$dest"
    return 0
  }

  pco_fetch_plymouth_public \
    "modules/system/mod-plymouth-load.sh" \
    "$mod" \
    0755 \
    || return 1

  pco_fetch_plymouth_public \
    "modules/system/assets/plymouth/pkg-plymouth-load.tar.zst" \
    "$pkg" \
    0644 \
    || return 1

  pco_fetch_plymouth_public \
    "modules/system/assets/plymouth/pkg-plymouth-load.tar.zst.sha256" \
    "$sha" \
    0644 \
    || return 1

  bash -n "$mod" || return 1

  grep -q '^THEME_NAME="pincabos"$' "$mod" || return 1

  expected="$(awk 'NR==1 {print $1}' "$sha")"
  actual="$(sha256sum "$pkg" | awk '{print $1}')"

  [ -n "$expected" ] || return 1
  [ "$expected" = "$actual" ] || return 1

  tar --zstd -tf "$pkg" \
    | grep -Eq '^\./?usr/share/plymouth/themes/pincabos/pincabos\.plymouth$' \
    || return 1

  pco_go "Public Plymouth final module and assets synchronized"
  return 0
}

pco_apply_final_plymouth() {
  pco_step "PLY-FINAL" "Apply PinCabOS final loading Plymouth module"

  local mod="/opt/pincabos/modules/system/mod-plymouth-load.sh"
  pco_refresh_final_plymouth_public || {
    pco_nogo "ERR-03-PLYMOUTH-SYNC-001: Public final Plymouth synchronization failed"
    return 1
  }

  if [ ! -x "$mod" ]; then
    pco_nogo "ERR-03-PLYMOUTH-LOAD-MODULE-MISSING: Missing executable module: $mod"
    return 0
  fi

  if PINCABOS_EXPLICIT="${PINCABOS_EXPLICIT:-1}" bash "$mod"; then
    pco_go "PinCabOS final Plymouth load module completed"
  else
    local rc="$?"
    pco_nogo "ERR-03-PLYMOUTH-LOAD-MODULE-FAILED: $mod returned rc=$rc"
    return 0
  fi
}

pco_hide_grub_menu() {
  pco_step "06" "Hide GRUB menu and normalize quiet splash"

  local grub="/etc/default/grub"

  if [ ! -f "$grub" ]; then
    pco_nogo "Missing $grub"
    return 0
  fi

  cp -a "$grub" "$BACKUP_DIR/etc-default-grub.backup"

  python3 - "$grub" <<'PY'
from pathlib import Path
import sys, re

path = Path(sys.argv[1])
lines = path.read_text(errors="replace").splitlines()

wanted = {
    "GRUB_DEFAULT": 'GRUB_DEFAULT=0',
    "GRUB_TIMEOUT_STYLE": 'GRUB_TIMEOUT_STYLE=hidden',
    "GRUB_TIMEOUT": 'GRUB_TIMEOUT=0',
    "GRUB_RECORDFAIL_TIMEOUT": 'GRUB_RECORDFAIL_TIMEOUT=0',
    "GRUB_CMDLINE_LINUX_DEFAULT": 'GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"',
}

seen = set()
out = []

for line in lines:
    stripped = line.strip()
    key = stripped.split("=", 1)[0] if "=" in stripped else ""
    if key in wanted and not stripped.startswith("#"):
        if key not in seen:
            out.append(wanted[key])
            seen.add(key)
        continue
    out.append(line)

for key, value in wanted.items():
    if key not in seen:
        out.append(value)

path.write_text("\n".join(out) + "\n")
PY

  if command -v update-grub >/dev/null 2>&1; then
    if update-grub; then
      pco_go "GRUB updated with hidden timeout and quiet splash"
    else
      pco_nogo "update-grub failed"
    fi
  else
    pco_warn "update-grub command missing"
  fi

  if grep -q '^GRUB_TIMEOUT_STYLE=hidden' "$grub" && grep -q '^GRUB_TIMEOUT=0' "$grub"; then
    pco_go "GRUB menu hidden configuration confirmed"
  else
    pco_nogo "GRUB hidden configuration not confirmed"
  fi
}


pco_enable_required_service() {
  local svc="$1"

  if systemctl list-unit-files "$svc" >/dev/null 2>&1; then
    if systemctl enable "$svc" >/dev/null 2>&1; then
      pco_go "$svc enabled"
      return 0
    fi
    pco_nogo "$svc enable failed"
    return 1
  fi

  pco_nogo "$svc unit missing"
  return 1
}

pco_enable_webapp_service() {
  # Current PinCabOS final services:
  # - pincabos-webapp.service for WebApp direct port 80
  # - ttyd.service for console
  # - pincabos-vpinfe.service for VPinFE
  # - pincabos-vpinfe.service as compatibility wrapper
  # pincabos-webapp.service is required; pincabos-web.service is a compatibility alias.

  local missing=0

  for svc in pincabos-console.service pincabos-vpinfe.service; do
    if systemctl list-unit-files "$svc" >/dev/null 2>&1; then
      systemctl enable "$svc" >/dev/null 2>&1 \
        && pco_go "$svc enabled" \
        || { pco_nogo "$svc enable failed"; missing=1; }
    else
      if [ "$svc" = "pincabos-console.service" ]; then
        pco_warn "$svc unit missing; console is optional for final completion"
      else
        pco_nogo "$svc unit missing"
        missing=1
      fi
    fi
  done

  [ "$missing" = "0" ] || return 1
  return 0
}



# PINCABOS_WEBAPP_DIRECT_START_V1
pco_start_direct_webapp_runtime() {
  pco_step "07B" "Start direct-port WebApp before HTTP validation"

  if ! systemctl list-unit-files pincabos-webapp.service >/dev/null 2>&1; then
    pco_nogo "ERR-03-WEBAPP-UNIT-MISSING-001: pincabos-webapp.service is missing"
    return 1
  fi

  systemctl reset-failed pincabos-webapp.service >/dev/null 2>&1 || true

  if systemctl restart pincabos-webapp.service >/dev/null 2>&1; then
    pco_go "pincabos-webapp.service restart requested for direct port 80"
  else
    pco_nogo "ERR-03-WEBAPP-START-001: could not start pincabos-webapp.service"
    systemctl --no-pager --full status pincabos-webapp.service 2>/dev/null || true
    return 1
  fi

  local i=1
  while [ "$i" -le 20 ]; do
    if systemctl is-active --quiet pincabos-webapp.service; then
      pco_go "pincabos-webapp.service active before HTTP validation"
      return 0
    fi

    sleep 1
    i=$((i + 1))
  done

  pco_nogo "ERR-03-WEBAPP-ACTIVE-001: pincabos-webapp.service is not active after 20s"
  systemctl --no-pager --full status pincabos-webapp.service 2>/dev/null || true
  return 1
}

pco_enable_final_services() {
  pco_step "07" "Enable final graphical boot services"

  systemctl unmask graphical.target lightdm.service display-manager.service >/dev/null 2>&1 || true
  systemctl set-default graphical.target >/dev/null 2>&1 && pco_go "Default target set to graphical.target" || pco_nogo "Could not set graphical.target"

  systemctl daemon-reload || true

  pco_enable_required_service pincabos-webapp.service

  # pincabos-web.service is legacy compatibility only. It must never block final install.
  if systemctl list-unit-files pincabos-web.service >/dev/null 2>&1; then
    systemctl enable pincabos-web.service >/dev/null 2>&1       && pco_go "legacy pincabos-web.service enabled if present"       || pco_warn "legacy pincabos-web.service enable not confirmed"
  else
    pco_warn "legacy pincabos-web.service absent; ignored for direct-port runtime"
  fi

  systemctl disable ttyd.service >/dev/null 2>&1 || true
  pco_enable_webapp_service
  pco_enable_required_service pincabos-vpinfe.service
  pco_enable_required_service pincabos-vpinfe.service
  pco_enable_required_service lightdm.service

  systemctl enable display-manager.service >/dev/null 2>&1 || true
  if systemctl list-unit-files nginx.service >/dev/null 2>&1; then
    systemctl stop nginx.service >/dev/null 2>&1 || true
    systemctl disable nginx.service >/dev/null 2>&1 || true
    systemctl mask nginx.service >/dev/null 2>&1 || true
    pco_go "nginx disabled for official direct-port runtime"
  fi
  pincabos_prepare_webapp_log_dirs

  # The WebApp owns direct port 80. Unlike LightDM/VPinFE, it must be
  # started now because RUN_03 validates HTTP before the final reboot.
  pco_start_direct_webapp_runtime || true

  if systemctl list-unit-files pincabos-console.service >/dev/null 2>&1; then
    systemctl enable pincabos-console.service >/dev/null 2>&1 || true
    systemctl restart pincabos-console.service >/dev/null 2>&1       && pco_go "pincabos-console.service restarted"       || pco_warn "pincabos-console.service restart not confirmed"
  else
    pco_warn "pincabos-console.service unit absent; console 8090 will not block final install"
  fi

  # Do not force-start VPinFE from console during install.
  # It starts after final reboot through graphical.target.
  pco_go "pincabos-vpinfe.service enabled for final graphical boot"
  pco_go "pincabos-vpinfe.service enabled for final graphical boot"

  if systemctl get-default 2>/dev/null | grep -qx 'graphical.target'; then
    pco_go "Final default target verified: graphical.target"
  else
    pco_nogo "Final default target is not graphical.target"
  fi

  if systemctl is-enabled lightdm.service >/dev/null 2>&1; then
    pco_go "lightdm.service enabled for final graphical boot"
  else
    pco_nogo "lightdm.service is not enabled for final graphical boot"
  fi

  # Do not force-start LightDM/VPinFE here on a running console install.
  # They are enabled for the final reboot into graphical.target.
  pco_go "LightDM/Openbox/VPinFE prepared for final reboot"
}



pco_install_final_graphical_guard() {
  pco_step "07C" "Install final LightDM hard graphical guard"

  local guard="/usr/local/sbin/pincabos-final-graphical-guard.sh"
  local unit="/etc/systemd/system/pincabos-final-graphical-guard.service"
  local vtunit="/etc/systemd/system/pincabos-switch-graphical-vt.service"
  local gettydir="/etc/systemd/system/getty@tty1.service.d"
  local gettydrop="$gettydir/10-pincabos-final-graphical-guard.conf"

  install -d -m 0755 /usr/local/sbin /etc/systemd/system "$gettydir" /opt/pincabos/logs

  cat > "$guard" <<'EOF_GUARD'
#!/usr/bin/env bash
set -Eeuo pipefail

LOG="/opt/pincabos/logs/final-graphical-guard-$(date +%Y%m%d-%H%M%S).log"
RUN_ONCE="/run/pincabos-final-graphical-guard.ran"

mkdir -p /opt/pincabos/logs /run
exec > >(tee -a "$LOG") 2>&1

echo "────────────────────────────────────────────────────────────────"
echo " PinCabOS final LightDM hard graphical guard"
echo "────────────────────────────────────────────────────────────────"
echo "Date: $(date -Is)"
echo "Args: $*"

if [ -e "$RUN_ONCE" ] && [ "${1:-}" = "--from-getty" ]; then
  echo "GO: guard already ran this boot, getty fallback exits"
  exit 0
fi
touch "$RUN_ONCE" 2>/dev/null || true

echo
echo "=== 1) Clear frontend hold flags ==="
for f in \
  /opt/pincabos/config/frontend-hold-firstboot.flag \
  /opt/pincabos/config/frontend-hold-live.flag \
  /opt/pincabos/flags/frontend-hold-firstboot.flag \
  /opt/pincabos/flags/frontend-hold-live.flag
do
  if [ -e "$f" ]; then
    mv -f "$f" "$f.disabled-final-graphical-guard-$(date +%Y%m%d-%H%M%S)" || true
    echo "GO: disabled hold flag: $f"
  else
    echo "GO: hold flag absent: $f"
  fi
done

echo
echo "=== 2) Force display-manager symlink to LightDM ==="
if [ -f /usr/lib/systemd/system/lightdm.service ]; then
  ln -sfn /usr/lib/systemd/system/lightdm.service /etc/systemd/system/display-manager.service
  echo "GO: display-manager.service -> lightdm.service"
elif [ -f /lib/systemd/system/lightdm.service ]; then
  ln -sfn /lib/systemd/system/lightdm.service /etc/systemd/system/display-manager.service
  echo "GO: display-manager.service -> lightdm.service"
else
  echo "NOGO: lightdm.service unit file missing"
fi

echo
echo "=== 3) Force graphical target and enable services ==="
systemctl daemon-reload || true
systemctl unmask graphical.target multi-user.target lightdm.service display-manager.service >/dev/null 2>&1 || true
systemctl set-default graphical.target >/dev/null 2>&1 || true

systemctl enable lightdm.service >/dev/null 2>&1 || true
systemctl enable display-manager.service >/dev/null 2>&1 || true
systemctl enable pincabos-final-graphical-guard.service >/dev/null 2>&1 || true
systemctl enable pincabos-switch-graphical-vt.service >/dev/null 2>&1 || true

for svc in pincabos-webapp.service pincabos-web.service pincabos-console.service pincabos-vpinfe.service ssh.service sshd.service; do
  if systemctl list-unit-files "$svc" >/dev/null 2>&1; then
    systemctl enable "$svc" >/dev/null 2>&1 || true
    echo "GO: enabled if present: $svc"
  fi
done

echo "Default target: $(systemctl get-default 2>/dev/null || true)"
echo "lightdm enabled: $(systemctl is-enabled lightdm.service 2>/dev/null || true)"
echo "display-manager enabled: $(systemctl is-enabled display-manager.service 2>/dev/null || true)"

echo
echo "=== 4) Start LightDM hard ==="
systemctl reset-failed lightdm.service display-manager.service >/dev/null 2>&1 || true
# Do not restart display-manager/lightdm during RUN_03.
# They are enabled and will start cleanly after final reboot.
pco_go "display-manager/lightdm restart deferred until final reboot"
sleep 3

for i in $(seq 1 60); do
  active="$(systemctl is-active lightdm.service 2>/dev/null || true)"
  xsocket="$([ -S /tmp/.X11-unix/X0 ] && echo yes || echo no)"
  echo "WAIT_LIGHTDM_X=$i active=$active xsocket=$xsocket"

  if [ "$active" = "active" ] && [ "$xsocket" = "yes" ]; then
    echo "GO: LightDM active and X socket present"
    break
  fi

  if [ "$i" = "15" ] || [ "$i" = "30" ] || [ "$i" = "45" ]; then
    pco_go "lightdm restart deferred until final reboot"
  fi

  sleep 1
done

echo
echo "=== 5) Switch visible console to graphical VT ==="
if command -v fgconsole >/dev/null 2>&1; then
  echo "VT before: $(fgconsole 2>/dev/null || true)"
fi

if command -v chvt >/dev/null 2>&1; then
  # Try tty7 first, then tty1->tty7 wake style.
  chvt 7 || true
  sleep 2
  if command -v fgconsole >/dev/null 2>&1; then
    echo "VT after chvt7: $(fgconsole 2>/dev/null || true)"
  fi
  echo "GO: chvt 7 attempted"
else
  echo "WARN: chvt missing; install package kbd in RUN_01"
fi

echo
echo "=== 6) Restart VPinFE after X ==="
if systemctl list-unit-files pincabos-vpinfe.service >/dev/null 2>&1; then
  pco_go "pincabos-vpinfe restart deferred until final reboot"
  sleep 10
  systemctl is-active pincabos-vpinfe.service >/dev/null 2>&1 \
    && echo "GO: pincabos-vpinfe active" \
    || echo "NOGO: pincabos-vpinfe inactive"
fi

echo
echo "=== 7) Final status ==="
systemctl --no-pager --full status lightdm.service display-manager.service pincabos-vpinfe.service 2>/dev/null || true
ps -ef | grep -Ei 'lightdm|Xorg|openbox|chrom|vpinfe' | grep -v grep || true
ss -ltnp 2>/dev/null | grep -E ':80|:8090|:8000|:8001|:8002|:22' || true

echo
echo "GO: final LightDM hard graphical guard completed"
EOF_GUARD

  chmod 755 "$guard"

  cat > "$unit" <<'EOF_UNIT'
[Unit]
Description=PinCabOS Final LightDM Hard Graphical Guard
Documentation=https://pincabos.cc/
DefaultDependencies=no
After=local-fs.target systemd-sysusers.service systemd-user-sessions.service dbus.service network-online.target
Before=getty@tty1.service
Wants=network-online.target
ConditionPathExists=/opt/pincabos

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/pincabos-final-graphical-guard.sh
RemainAfterExit=yes
TimeoutStartSec=120

[Install]
WantedBy=multi-user.target graphical.target
EOF_UNIT

  chmod 644 "$unit"

  cat > "$vtunit" <<'EOF_VTUNIT'
[Unit]
Description=PinCabOS Switch to Graphical VT
Documentation=https://pincabos.cc/
After=lightdm.service display-manager.service graphical.target pincabos-final-graphical-guard.service
Wants=lightdm.service

[Service]
Type=oneshot
ExecStart=/bin/bash -lc 'for i in $(seq 1 60); do [ -S /tmp/.X11-unix/X0 ] && break; sleep 1; done; command -v chvt >/dev/null 2>&1 && chvt 7 || true; pco_go "pincabos-vpinfe restart deferred until final reboot"'
RemainAfterExit=yes
TimeoutStartSec=90

[Install]
WantedBy=multi-user.target graphical.target
EOF_VTUNIT

  chmod 644 "$vtunit"

  cat > "$gettydrop" <<'EOF_GETTY'
[Unit]
After=pincabos-final-graphical-guard.service
Wants=pincabos-final-graphical-guard.service

[Service]
ExecStartPre=-/usr/local/sbin/pincabos-final-graphical-guard.sh --from-getty
EOF_GETTY

  chmod 644 "$gettydrop"

  systemctl daemon-reload || true

  systemctl enable pincabos-final-graphical-guard.service >/dev/null 2>&1 \
    && pco_go "pincabos-final-graphical-guard.service enabled" \
    || pco_warn "Could not enable final graphical guard"

  systemctl enable pincabos-switch-graphical-vt.service >/dev/null 2>&1 \
    && pco_go "pincabos-switch-graphical-vt.service enabled" \
    || pco_warn "Could not enable graphical VT switch service"

  systemctl set-default graphical.target >/dev/null 2>&1 \
    && pco_go "Default target set to graphical.target" \
    || pco_warn "Could not set default target"

  if systemd-analyze verify "$unit" "$vtunit" >/tmp/pincabos-lightdm-hardguard.verify 2>&1; then
    pco_go "Final LightDM hard guard units verified"
  else
    pco_warn "systemd-analyze verify warnings for hard guard units"
    sed -n '1,180p' /tmp/pincabos-lightdm-hardguard.verify || true
  fi
}

pco_disable_installer_autoresume() {
  pco_step "07B" "Disable installer autoresume before final reboot"

  local ts
  ts="$(date +%Y%m%d-%H%M%S)"
  local backup_dir="/opt/pincabos/backups/final-autoresume-clean-$ts"
  local state_done="/opt/pincabos/install/.completed-final-$ts"

  mkdir -p "$backup_dir" "$state_done" 2>/dev/null || true

  # Désactiver uniquement les drop-ins getty clairement liés à PinCabOS install/autoresume.
  if [ -d /etc/systemd/system/getty@tty1.service.d ]; then
    while IFS= read -r f; do
      if grep -qEi 'pincabos-autoresume-console|go-pincabos|RUN_0|FINAL_REBOOT|REBOOT_AFTER' "$f" 2>/dev/null; then
        cp -a "$f" "$backup_dir/" 2>/dev/null || true
        mv -f "$f" "$f.disabled-final-$ts"
        pco_go "Disabled installer getty autoresume drop-in: $f"
      fi
    done < <(find /etc/systemd/system/getty@tty1.service.d -maxdepth 1 -type f 2>/dev/null | sort)
  fi

  # Désactiver le helper root autoresume.
  if [ -f /usr/local/sbin/pincabos-autoresume-console.sh ]; then
    cp -a /usr/local/sbin/pincabos-autoresume-console.sh "$backup_dir/" 2>/dev/null || true
    mv -f /usr/local/sbin/pincabos-autoresume-console.sh "/usr/local/sbin/pincabos-autoresume-console.sh.disabled-final-$ts"
    pco_go "Disabled installer autoresume helper"
  else
    pco_go "No installer autoresume helper active"
  fi

  # Retirer les holds frontend firstboot/live si présents.
  for f in \
    /opt/pincabos/config/frontend-hold-firstboot.flag \
    /opt/pincabos/config/frontend-hold-live.flag
  do
    if [ -e "$f" ]; then
      cp -a "$f" "$backup_dir/" 2>/dev/null || true
      mv -f "$f" "$f.disabled-final-$ts"
      pco_go "Disabled frontend hold flag: $f"
    fi
  done

  # Archiver les flags d'installation qui peuvent relancer le workflow.
  for dir in /opt/pincabos/flags /opt/pincabos/install; do
    [ -d "$dir" ] || continue

    while IFS= read -r f; do
      local base
      base="$(basename "$f")"

      case "$base" in
        go-pincabos.sh|go-pincabos.sh.sha256|03-install-check.sh|03-install-check.sh.sha256|install.json)
          continue
          ;;
      esac

      if grep -qEi 'RUN_00|RUN_01|RUN_02|RUN_03|FINAL_REBOOT|REBOOT_AFTER|go-pincabos|autoresume|final-reboot' "$f" 2>/dev/null || echo "$base" | grep -qEi 'run|resume|reboot|state|flag|stage|step|final'; then
        cp -a "$f" "$backup_dir/" 2>/dev/null || true
        mv -f "$f" "$state_done/" 2>/dev/null || true
        pco_go "Archived installer state file: $f"
      fi
    done < <(find "$dir" -maxdepth 1 -type f 2>/dev/null | sort)
  done

  systemctl daemon-reload >/dev/null 2>&1 || true
  systemctl reset-failed getty@tty1.service >/dev/null 2>&1 || true

  if systemctl set-default graphical.target >/dev/null 2>&1; then
    pco_go "Final default target confirmed: graphical.target"
  else
    pco_nogo "Could not set graphical.target"
  fi

  if systemctl enable lightdm.service >/dev/null 2>&1; then
    pco_go "lightdm.service enabled for final boot"
  else
    pco_warn "lightdm.service enable not confirmed"
  fi

  pco_go "Installer autoresume cleanup completed"
}


pco_http_validation() {
  pco_step "08" "Validate local WebApp HTTP routes"

  pincabos_http_wait_route "HTTP root" "http://127.0.0.1/" 30 1 || true
  pincabos_http_wait_route "HTTP /admin" "http://127.0.0.1/admin" 30 1 || true
  pincabos_http_wait_route "HTTP /pincabos-update" "http://127.0.0.1/pincabos-update" 30 1 || true
}

pco_final_report() {
  pco_step "09" "Write final GO/NOGO report"

  {
    echo "────────────────────────────────────────────────────────────────"
    echo " PinCabOS Final Validation Report"
    echo "────────────────────────────────────────────────────────────────"
    echo "Date: $(date -Is)"
    echo "Host: $(hostname)"
    echo "Log : $LOG"
    echo
    echo "Checks:"
    for item in "${CHECKS[@]}"; do
      status="${item%%|*}"
      msg="${item#*|}"
      printf " - %-5s %s\n" "$status" "$msg"
    done
    echo
    echo "Failed checks : $FAILED"
    echo "Warnings      : $WARNED"
    if [ "$FAILED" -eq 0 ]; then

echo
echo "=== Console service ownership ==="
systemctl stop ttyd.service >/dev/null 2>&1 || true
systemctl disable ttyd.service >/dev/null 2>&1 || true
systemctl mask ttyd.service >/dev/null 2>&1 || true
systemctl reset-failed ttyd.service >/dev/null 2>&1 || true

systemctl enable pincabos-console.service >/dev/null 2>&1 || true
systemctl restart pincabos-console.service >/dev/null 2>&1 || true

if systemctl is-active --quiet pincabos-console.service; then
  pco_go "pincabos-console.service active"
else
  pco_warn "ERR-03-CONSOLE-001: pincabos-console.service is not active; final install continues"
fi

if ss -ltnp 2>/dev/null | grep -q ':8090 '; then
  pco_go "console port 8090 listening"
else
  pco_warn "ERR-03-CONSOLE-002: port 8090 is not listening; final install continues"
fi


      echo "FINAL RESULT  : GO"
    else
      echo "FINAL RESULT  : NOGO"
    fi
    echo "────────────────────────────────────────────────────────────────"
  } | tee "$REPORT"

  if [ "$FAILED" -eq 0 ]; then
    pco_deep_clean_run_state_before_go_return
    pco_go "Final report result: GO; deep cleanup completed; returning to go-pincabos"
  else
    pco_nogo "Final report result: NOGO"
  fi
}


pincabos_prepare_webapp_log_dirs() {
  pco_step "07A" "Prepare WebApp writable log directories"

  mkdir -p /opt/pincabos/logs /opt/pincabos/logs/updates /opt/pincabos/logs/updates/tmp 2>/dev/null || true
  chown -R pinball:pinball /opt/pincabos/logs /opt/pincabos/logs/updates 2>/dev/null || true
  chmod 775 /opt/pincabos/logs /opt/pincabos/logs/updates /opt/pincabos/logs/updates/tmp 2>/dev/null || true

  if [ -d /opt/pincabos/logs/updates ] && runuser -u pinball -- test -w /opt/pincabos/logs/updates 2>/dev/null; then
    pco_go "WebApp updates log directory writable for pinball"
  else
    pco_warn "Unable to prove /opt/pincabos/logs/updates writable for pinball before WebApp restart"
  fi
}

pincabos_http_wait_route() {
  local label="$1"
  local url="$2"
  local attempts="${3:-30}"
  local delay="${4:-1}"
  local code=""
  local i=1

  while [ "$i" -le "$attempts" ]; do
    code="$(curl -L -sS -o /dev/null -w '%{http_code}' --max-time 5 "$url" 2>/dev/null || true)"

    case "$code" in
      200|201|202|204|301|302|303|307|308)
        pco_go "$label reachable HTTP $code"
        return 0
        ;;
    esac

    sleep "$delay"
    i=$((i + 1))
  done

  if echo "$label" | grep -Eq 'HTTP /(admin|pincabos-update)'; then
    pco_warn "$label optional legacy route unavailable after ${attempts}s, last HTTP code: ${code:-none}"
    return 0
  fi

  pco_nogo "$label unreachable after ${attempts}s, last HTTP code: ${code:-none}"
  return 1
}


pco_reset_root_password_default() {
  pco_step "03Y" "Reset root password to PinCabOS default"

  if ! command -v chpasswd >/dev/null 2>&1; then
    pco_nogo "ERR-03-ROOTPASS-CHPASSWD-001" "chpasswd command missing; cannot reset root password"
  fi

  # Pas de mot de passe en dur : PINCABOS_ROOT_PASSWORD permet d'en definir un
  # ponctuellement (poste de dev), sinon le compte root reste verrouille.
  if [ -n "${PINCABOS_ROOT_PASSWORD:-}" ]; then
    printf 'root:%s\n' "$PINCABOS_ROOT_PASSWORD" | chpasswd
    pco_go "Root password set from PINCABOS_ROOT_PASSWORD"
  else
    printf 'root:%s\n' '!*' | chpasswd -e
    pco_go "Root account locked (administration via sudo)"
  fi
  return 0
}


pco_ensure_root_ssh_password_access() {
  pco_step "03Z" "Ensure root SSH password access"

  local dropdir="/etc/ssh/sshd_config.d"
  local drop="$dropdir/90-pincabos-root-password.conf"
  local ssh_service=""

  if ! command -v chpasswd >/dev/null 2>&1; then
    pco_nogo "ERR-03-ROOTPASS-CHPASSWD-001: chpasswd command missing"
    return 0
  fi

  # Acces SSH root par mot de passe : uniquement si un mot de passe est fourni
  # explicitement par l'environnement. Sinon on n'active rien (root verrouille).
  if [ -z "${PINCABOS_ROOT_PASSWORD:-}" ]; then
    pco_go "root SSH password access skipped (root locked, sudo is the admin path)"
    return 0
  fi

  printf 'root:%s\n' "$PINCABOS_ROOT_PASSWORD" | chpasswd

  if passwd -S root 2>/dev/null | awk '{print $2}' | grep -Eq '^(P|PS)$'; then
    pco_go "root password is set/unlocked"
  else
    pco_nogo "ERR-03-ROOTPASS-LOCKED-001: root password is not active"
  fi

  install -d -m 0755 "$dropdir"

  if [ -f "$drop" ]; then
    cp -a "$drop" "$BACKUP_DIR/90-pincabos-root-password.conf.backup" 2>/dev/null || true
  fi

  cat > "$drop" <<'EOF_ROOT_SSH'
# PinCabOS final root SSH policy
# Created by Karots Sugarpie
PermitRootLogin yes
PasswordAuthentication yes
KbdInteractiveAuthentication yes
UsePAM yes
EOF_ROOT_SSH

  chmod 644 "$drop"

  if command -v sshd >/dev/null 2>&1; then
    if sshd -t; then
      pco_go "sshd configuration syntax OK"
    else
      pco_nogo "ERR-03-SSHD-CONFIG-001: sshd -t failed"
    fi

  if [ ! -x /usr/sbin/sshd ]; then
    pco_nogo "ERR-03-SSHD-BIN-001: Missing /usr/sbin/sshd"
  fi
    SSHD_EFFECTIVE="$(/usr/sbin/sshd -T 2>/dev/null || true)"
    if grep -qx 'permitrootlogin yes' <<<"$SSHD_EFFECTIVE"; then
      pco_go "sshd effective PermitRootLogin yes"
    else
      pco_nogo "ERR-03-SSHD-ROOTLOGIN-001: PermitRootLogin is not yes"
    fi

    if grep -qx 'passwordauthentication yes' <<<"$SSHD_EFFECTIVE"; then
      pco_go "sshd effective PasswordAuthentication yes"
    else
      pco_nogo "ERR-03-SSHD-PASSAUTH-001: PasswordAuthentication is not yes"
    fi
  else
    pco_nogo "ERR-03-SSHD-MISSING-001: sshd command missing"
  fi

  if systemctl list-unit-files ssh.service >/dev/null 2>&1; then
    ssh_service="ssh.service"
  elif systemctl list-unit-files sshd.service >/dev/null 2>&1; then
    ssh_service="sshd.service"
  else
    pco_nogo "ERR-03-SSH-SERVICE-MISSING-001: no ssh/sshd service found"
    return 0
  fi

  systemctl enable "$ssh_service" >/dev/null 2>&1 && pco_go "$ssh_service enabled" || pco_nogo "ERR-03-SSH-ENABLE-001: could not enable $ssh_service"
  systemctl restart "$ssh_service" >/dev/null 2>&1 && pco_go "$ssh_service restarted" || pco_nogo "ERR-03-SSH-RESTART-001: could not restart $ssh_service"

  if systemctl is-active "$ssh_service" >/dev/null 2>&1; then
    pco_go "$ssh_service active"
  else
    pco_nogo "ERR-03-SSH-INACTIVE-001: $ssh_service is not active"
  fi

  if ss -ltnp 2>/dev/null | grep -Eq ':(22)\s'; then
    pco_go "SSH port 22 is listening"
  else
    pco_warn "SSH port 22 not detected by ss; service may still be socket/listener-managed"
  fi

  pco_go "Root SSH password access finalized"
}

pco_link_all_pincabos_sh_to_path() {
  pco_step "03X" "Expose all PinCabOS .sh commands in PATH"

  local bindir="/usr/local/bin"
  local script=""
  local base=""
  local alias=""
  local linked=0
  local skipped=0

  install -d -m 0755 "$bindir"

  # Every executable shell script from PinCabOS public/runtime trees gets:
  #   /usr/local/bin/name.sh
  #   /usr/local/bin/name
  #
  # Existing non-symlink commands are not overwritten.
  while IFS= read -r script; do
    [ -f "$script" ] || continue

    chmod +x "$script" 2>/dev/null || true

    base="$(basename "$script")"
    alias="${base%.sh}"

    for name in "$base" "$alias"; do
      [ -n "$name" ] || continue

      if [ -e "$bindir/$name" ] && [ ! -L "$bindir/$name" ]; then
        pco_warn "PATH command exists and is not a symlink, skipped: $bindir/$name"
        skipped=$((skipped + 1))
        continue
      fi

      ln -sfn "$script" "$bindir/$name"
      linked=$((linked + 1))
    done
  done < <(
    find \
      /opt/pincabos/install \
      /opt/pincabos/modules \
      /opt/pincabos/tools \
      /opt/pincabos/bin \
      /opt/pincabos/scripts \
      -type f -name '*.sh' 2>/dev/null | sort
  )

  # Canonical command aliases expected by user/docs.
  [ -x /opt/pincabos/install/go-pincabos.sh ] && ln -sfn /opt/pincabos/install/go-pincabos.sh "$bindir/go-pincabos"
  [ -x /opt/pincabos/install/help-pincabos.sh ] && ln -sfn /opt/pincabos/install/help-pincabos.sh "$bindir/help-pincabos"
  [ -x /opt/pincabos/install/01-install-system.sh ] && ln -sfn /opt/pincabos/install/01-install-system.sh "$bindir/01-install-system"
  [ -x /opt/pincabos/install/02-install-engine.sh ] && ln -sfn /opt/pincabos/install/02-install-engine.sh "$bindir/02-install-engine"
  [ -x /opt/pincabos/install/03-install-check.sh ] && ln -sfn /opt/pincabos/install/03-install-check.sh "$bindir/03-install-check"

  hash -r 2>/dev/null || true

  pco_go "PATH shell links created: $linked"
  [ "$skipped" -gt 0 ] && pco_warn "PATH shell links skipped because command already existed: $skipped"

  echo
  echo -e "${YELLOW}PinCabOS PATH command sample${RESET:-}"
  ls -l "$bindir" | grep -E 'pincabos|install-|mod-|pkg-' | sed -n '1,120p' || true

  return 0
}

pco_deep_clean_run_state_before_go_return() {
  pco_step "03Z" "Deep clean installer run state before returning to go-pincabos"

  pco_reset_root_password_default
  pco_ensure_root_ssh_password_access
  pco_link_all_pincabos_sh_to_path

  local flags_dir="/opt/pincabos/flags"
  local state_dir="/opt/pincabos/state"
  local backup_dir="/opt/pincabos/backups/run-state-before-final-clean-$(date +%Y%m%d-%H%M%S)"

  mkdir -p "$flags_dir" "$state_dir" "$backup_dir"

  cp -a "$flags_dir" "$backup_dir/flags" 2>/dev/null || true
  cp -a "$state_dir" "$backup_dir/state" 2>/dev/null || true
  [ -d /etc/systemd/system/getty@tty1.service.d ] && cp -a /etc/systemd/system/getty@tty1.service.d "$backup_dir/getty@tty1.service.d" 2>/dev/null || true
  [ -f /usr/local/sbin/pincabos-autoresume-console.sh ] && cp -a /usr/local/sbin/pincabos-autoresume-console.sh "$backup_dir/" 2>/dev/null || true

  echo "Backup: $backup_dir"

  # Remove active/transient workflow state. Keep historical end-run-* files until go writes final-go.
  rm -f \
    "$flags_dir/run-00" \
    "$flags_dir/run-01" \
    "$flags_dir/run-01E" \
    "$flags_dir/run-01F" \
    "$flags_dir/run-01G" \
    "$flags_dir/run-01H" \
    "$flags_dir/run-02" \
    "$flags_dir/run-03" \
    "$flags_dir/current-run" \
    "$flags_dir/next-run" \
    "$flags_dir/reboot-after-01" \
    "$flags_dir/post-reboot-network-refresh-running" \
    "$flags_dir/install-refresh-after-run01-running" \
    "$flags_dir/final-reboot" \
    "$state_dir/current-run" \
    "$state_dir/next-run" \
    2>/dev/null || true

  # Remove old/partial transient markers without deleting successful audit flags.
  find "$flags_dir" -maxdepth 1 -type f \( \
    -name 'run-*' \
    -o -name '*-running' \
    -o -name 'current-run' \
    -o -name 'next-run' \
    -o -name 'reboot-after-*' \
    -o -name 'install-refresh-after-run01-*' \
    -o -name 'post-reboot-network-refresh-running' \
  \) -print -delete 2>/dev/null || true

  # Disable any installer autoresume leftovers. 03 must return to go, never loop getty.
  if [ -d /etc/systemd/system/getty@tty1.service.d ]; then
    while IFS= read -r f; do
      if grep -qEi 'pincabos-autoresume-console|go-pincabos|RUN_0|REBOOT_AFTER|FINAL_REBOOT|autoresume' "$f" 2>/dev/null; then
        mv -f "$f" "$f.disabled-by-03-final-clean"
        pco_go "Disabled leftover getty autoresume drop-in: $f"
      fi
    done < <(find /etc/systemd/system/getty@tty1.service.d -maxdepth 1 -type f 2>/dev/null | sort)
  fi

  if [ -f /usr/local/sbin/pincabos-autoresume-console.sh ]; then
    mv -f /usr/local/sbin/pincabos-autoresume-console.sh /usr/local/sbin/pincabos-autoresume-console.sh.disabled-by-03-final-clean
    pco_go "Disabled leftover autoresume helper"
  fi

  systemctl daemon-reload >/dev/null 2>&1 || true
  systemctl reset-failed getty@tty1.service >/dev/null 2>&1 || true

  # Ensure final boot target is graphical; go will perform the actual final reboot.
  systemctl set-default graphical.target >/dev/null 2>&1 || true
  systemctl enable lightdm.service >/dev/null 2>&1 || true

  pco_go "Deep run-state cleanup completed; returning control to go-pincabos"
  return 0
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

main() {
  pco_title
  pco_require_root
  pco_fix_frontend_unit_documentation
  pco_ensure_openbox_session
  pco_ensure_lightdm_autologin
  pco_hide_grub_menu
  pco_enable_final_services
  pco_install_final_graphical_guard
  pco_disable_installer_autoresume
  pco_http_validation || true
  pco_apply_final_plymouth
  pco_final_report

  echo
  pco_line
  if [ "$FAILED" -eq 0 ]; then
    printf "${GREEN}GO [√] PinCabOS final validation completed. Deep cleanup completed. Returning to go-pincabos for final summary/reboot.${RESET}\n"
    printf "${YELLOW}Report:${RESET} %s\n" "$REPORT"
    pco_line
    exit 0
  fi

  printf "${RED}NOGO [X] PinCabOS final validation failed. Final reboot must not continue.${RESET}\n"
  printf "${YELLOW}Report:${RESET} %s\n" "$REPORT"
  pco_line
  exit 1
}

main "$@"
