#!/usr/bin/env bash

pco_go() {
  printf 'GO: %s\n' "$*"
}

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

for svc in pincabos-webapp.service pincabos-web.service pincabos-console.service pincabos-vpinfe.service pincabos-frontend.service ssh.service sshd.service; do
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
systemctl --no-pager --full status lightdm.service display-manager.service pincabos-vpinfe.service pincabos-frontend.service 2>/dev/null || true
ps -ef | grep -Ei 'lightdm|Xorg|openbox|chrom|vpinfe' | grep -v grep || true
ss -ltnp 2>/dev/null | grep -E ':80|:8090|:8000|:8001|:8002|:22' || true

echo
echo "GO: final LightDM hard graphical guard completed"
