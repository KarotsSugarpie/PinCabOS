#!/usr/bin/env bash


# PINCABOS_INSTALLER_GUARD_SKIP
# Pendant une installation, cet outil ne doit rien faire : forcer
# graphical.target, (re)demarrer lightdm et changer de VT volerait l'ecran
# a l'installateur. Le test porte sur la ligne de commande du noyau, pas sur
# le marqueur live : en mode « essayer sans installer » la session
# graphique doit demarrer normalement.
if grep -qw 'pincabos.installer' /proc/cmdline 2>/dev/null; then
  echo 'PinCabOS: installation in progress, graphical guard skipped.'
  exit 0
fi

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

# PINCABOS_GUARD_FAST_PATH_V1
# Cette garde repare une installation (lien display-manager, cible graphique,
# services actives) : une fois faite, elle n'a plus rien a reparer. Elle
# rejouait pourtant a CHAQUE boot un daemon-reload, une rafale de systemctl
# enable et 15 s d'attentes fixes (mesure : 18,6 s sur le cab de Yann). Des
# que le marqueur existe et que les trois invariants tiennent, on sort tout
# de suite. `--force` rejoue la reparation complete et repose le marqueur.
MARKER="/opt/pincabos/flags/final-graphical-guard.done"
if [ "${1:-}" != "--force" ] && [ -e "$MARKER" ]; then
  LIGHTDM_UNIT="$(readlink -f /usr/lib/systemd/system/lightdm.service 2>/dev/null || readlink -f /lib/systemd/system/lightdm.service 2>/dev/null || true)"
  DM_LINK="$(readlink -f /etc/systemd/system/display-manager.service 2>/dev/null || true)"
  if [ -n "$LIGHTDM_UNIT" ] && [ "$DM_LINK" = "$LIGHTDM_UNIT" ] \
     && [ "$(systemctl get-default 2>/dev/null || true)" = "graphical.target" ] \
     && [ "$(systemctl is-enabled lightdm.service 2>/dev/null || true)" = "enabled" ]; then
    echo "GO: installation deja verifiee ($MARKER) : chemin rapide, rien a reparer"
    exit 0
  fi
  echo "WARN: marqueur present mais un invariant a bouge : reparation complete"
fi

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
  # PINCABOS_GRAPHICAL_VT_DYNAMIC_V1
  # Le terminal graphique n'est plus fige a 7 : LightDM reprend desormais
  # celui de Plymouth, pour que le splash cede la place a X sans laisser voir
  # la console. On bascule vers le terminal que Xorg utilise reellement.
  PCO_GVT="$(ps -eo args= | sed -n 's/.*Xorg .* vt\([0-9]\{1,\}\).*/\1/p' | head -n1)"
  [ -n "${PCO_GVT:-}" ] || PCO_GVT=7
  chvt "$PCO_GVT" || true
  sleep 2
  if command -v fgconsole >/dev/null 2>&1; then
    echo "VT after chvt$PCO_GVT: $(fgconsole 2>/dev/null || true)"
  fi
  echo "GO: chvt $PCO_GVT attempted"
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
mkdir -p "$(dirname "$MARKER")" 2>/dev/null || true
touch "$MARKER" 2>/dev/null && echo "GO: marqueur pose : $MARKER (les prochains boots prendront le chemin rapide)" || true
echo "GO: final LightDM hard graphical guard completed"
