#!/usr/bin/env bash
# PinCabOS-File created by Karots Sugarpie
set +e

TS="$(date +%Y%m%d-%H%M%S)"
LOG_DIR="/opt/pincabos/logs"
LOG="${LOG_DIR}/go-safety-${TS}.log"

mkdir -p "$LOG_DIR" /opt/pincabos/config /opt/pincabos/backups

exec > >(tee -a "$LOG") 2>&1

echo "=================================================="
echo " PinCabOS GO SAFETY / ISO FIRSTBOOT RESCUE"
echo "=================================================="
date
hostname
echo "Log: $LOG"
echo

if [ "$(id -u)" -ne 0 ]; then
  echo "ERREUR: lance avec sudo:"
  echo "  sudo go.sh"
  exit 1
fi

echo "=== 1) Armer ISO FirstBoot Safe ==="
touch /opt/pincabos/config/iso-firstboot-safe.flag
rm -f /opt/pincabos/config/iso-firstboot-safe.done
touch /opt/pincabos/config/frontend-hold-firstboot.flag

cat > /opt/pincabos/config/pincabos-admin-mode.json <<EOFJSON
{
  "mode": "iso-firstboot-safe",
  "description": "Mode rescue activé par go.sh depuis console.",
  "set_at": "$(date -Iseconds)",
  "iso_flag": true,
  "frontend_hold": true
}
EOFJSON

echo "OK: iso-firstboot-safe.flag actif"
echo "OK: frontend-hold-firstboot.flag actif"
echo

echo "=== 2) Stopper frontend / VPinFE / Chrome si présents ==="
systemctl stop pincabos-vpinfe.service 2>/dev/null || true
systemctl disable pincabos-vpinfe.service 2>/dev/null || true

pkill -f -i "vpinfe" 2>/dev/null || true
pkill -f -i "chrome" 2>/dev/null || true
pkill -f -i "chromium" 2>/dev/null || true

echo "Frontend/VPinFE/Chrome stoppés ou absents."
echo

echo "=== 3) Neutraliser configs graphiques clonées dangereuses ==="
SAFE_DIR="/opt/pincabos/backups/go-safety-${TS}"
mkdir -p "$SAFE_DIR"

move_if_exists() {
  local p="$1"
  if [ -e "$p" ] || [ -L "$p" ]; then
    local safe_name
    safe_name="$(echo "$p" | sed 's#/#_#g')"
    echo "MOVE SAFE: $p -> $SAFE_DIR/$safe_name"
    mv "$p" "$SAFE_DIR/$safe_name" 2>/dev/null || true
  fi
}

move_if_exists /etc/X11/xorg.conf

if [ -d /etc/X11/xorg.conf.d ]; then
  mkdir -p "$SAFE_DIR/xorg.conf.d"
  find /etc/X11/xorg.conf.d -maxdepth 1 -type f \
    \( -iname '*nvidia*' -o -iname '*screen*' -o -iname '*monitor*' -o -iname '*pincabos*' \) \
    -print0 2>/dev/null |
  while IFS= read -r -d '' f; do
    echo "MOVE SAFE XORG: $f -> $SAFE_DIR/xorg.conf.d/"
    mv "$f" "$SAFE_DIR/xorg.conf.d/" 2>/dev/null || true
  done
fi

for p in \
  /opt/pincabos/config/screens/screens.json \
  /opt/pincabos/config/screens/roles.json \
  /opt/pincabos/config/screens/layout.json \
  /home/pinball/.config/monitors.xml \
  /home/pinball/.screenlayout/pincabos.sh
do
  move_if_exists "$p"
done

echo

echo "=== 4) Détecter GPU et neutraliser NVIDIA forcé si besoin ==="
GPU_INFO="$(lspci -nn 2>/dev/null | grep -Ei 'vga|3d|display' || true)"
echo "$GPU_INFO"

if echo "$GPU_INFO" | grep -qi nvidia; then
  GPU_VENDOR="nvidia"
elif echo "$GPU_INFO" | grep -qi amd; then
  GPU_VENDOR="amd"
elif echo "$GPU_INFO" | grep -qi intel; then
  GPU_VENDOR="intel"
else
  GPU_VENDOR="unknown"
fi

echo "GPU_VENDOR=$GPU_VENDOR"

if [ "$GPU_VENDOR" != "nvidia" ]; then
  for p in \
    /etc/modprobe.d/nvidia.conf \
    /etc/modprobe.d/blacklist-nouveau.conf \
    /etc/modprobe.d/pincabos-nvidia.conf
  do
    move_if_exists "$p"
  done
  echo "GPU non-NVIDIA: configs NVIDIA forcées neutralisées."
else
  echo "GPU NVIDIA détecté: on garde les paquets, mais les layouts forcés sont retirés."
fi

echo

echo "=== 5) Réparer permissions scripts PinCabOS ==="
chmod 755 /opt/pincabos 2>/dev/null || true
chmod 755 /opt/pincabos/tools 2>/dev/null || true
chmod 755 /opt/pincabos/bin 2>/dev/null || true

find /opt/pincabos/tools -type f -name "*.sh" -exec chmod 755 {} \; 2>/dev/null || true
find /opt/pincabos/tools -type f -name "*.py" -exec chmod 755 {} \; 2>/dev/null || true
find /opt/pincabos/bin -type f -name "*.sh" -exec chmod 755 {} \; 2>/dev/null || true
find /opt/pincabos/bin -type f -name "*.py" -exec chmod 755 {} \; 2>/dev/null || true
find /opt/pincabos/web/.venv/bin -maxdepth 1 -type f -exec chmod 755 {} \; 2>/dev/null || true

echo "Permissions réparées."
echo

echo "=== 6) Reset First Run obligatoire ==="
python3 - <<'PY'
import json
from pathlib import Path

p = Path("/opt/pincabos/config/first-run.json")
p.parent.mkdir(parents=True, exist_ok=True)

data = {}
if p.exists():
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        data = {}

for k in ["network", "gpu", "updates", "screens", "audio"]:
    data[k] = False

data["show_popup"] = True
data["iso_firstboot_safe"] = True
data["go_safety_ran"] = True

p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("First Run reset:", p)
PY

echo

echo "=== 7) Réseau DHCP / NetworkManager ==="
systemctl enable NetworkManager 2>/dev/null || true
systemctl restart NetworkManager 2>/dev/null || true

# Essai DHCP direct sur interfaces ethernet si NetworkManager est lent.
for iface in $(ls /sys/class/net 2>/dev/null | grep -Ev '^(lo|docker|veth|virbr|br-|tap)'); do
  echo "--- Interface: $iface ---"
  ip link set "$iface" up 2>/dev/null || true
  timeout 20 dhclient -v "$iface" 2>/dev/null || true
done

echo

echo "=== 8) Redémarrer WebApp / nginx ==="
systemctl enable nginx 2>/dev/null || true
systemctl enable pincabos-web.service 2>/dev/null || true

systemctl reset-failed pincabos-web.service 2>/dev/null || true
systemctl restart pincabos-web.service 2>/dev/null || true
systemctl restart nginx 2>/dev/null || true

sleep 3

echo

echo "=== 9) État services ==="
systemctl is-active NetworkManager 2>/dev/null || true
systemctl is-active pincabos-web.service 2>/dev/null || true
systemctl is-active nginx 2>/dev/null || true
echo

echo "=== 10) IP / accès WebApp ==="
IP_LIST="$(hostname -I 2>/dev/null | tr ' ' '\n' | grep -E '^[0-9]+\.' | paste -sd ' ' -)"
[ -z "$IP_LIST" ] && IP_LIST="IP non disponible encore"

echo "IPs détectées: $IP_LIST"
echo

cat > /etc/issue <<EOFISSUE
PinCabOS GO SAFETY MODE

WebApp:
  http://$IP_LIST/

Si plusieurs IP sont affichées, essaie chacune dans ton navigateur.

Commande utile:
  sudo go.sh
  sudo /opt/pincabos/tools/pincabos-exit-firstboot-safe.sh

EOFISSUE

for ip in $IP_LIST; do
  echo "Ouvre: http://$ip/"
  echo "First Run: http://$ip/first-run"
done

echo

echo "=== 11) Test HTTP local ==="
curl -sS -I --max-time 8 http://127.0.0.1/ || true
curl -sS -I --max-time 8 http://127.0.0.1/first-run || true

echo
echo "=================================================="
echo " GO SAFETY TERMINÉ"
echo "=================================================="
echo "Log: $LOG"
