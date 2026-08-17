#!/usr/bin/env bash
# PinCabOS - retour en DHCP (V2)
# Meme correction que network-set-static.sh (PINCABOS_NETWORK_V2) : fichier
# unique et prioritaire 99-pincabos-network.yaml, renderer detecte, conflits
# desactives, et bail DHCP VERIFIE apres application.
set -Eeuo pipefail
PATH="/usr/sbin:/usr/bin:/sbin:/bin"

CONF="/etc/netplan/99-pincabos-network.yaml"
LEGACY="/etc/netplan/00-pincabos-dhcp4.yaml"
BACKUP_DIR="/opt/pincabos/backups/network"

find_main_iface() {
  ip -4 route show default 2>/dev/null |
  awk '/^default/ { for (i=1;i<=NF;i++) if ($i=="dev") { print $(i+1); exit } }'
}

iface="${1:-}"
[[ -n "$iface" ]] || iface="$(find_main_iface || true)"

[[ -n "$iface" ]] || { echo "ERREUR: interface réseau introuvable."; exit 1; }
[[ -d "/sys/class/net/$iface" ]] || { echo "ERREUR: interface invalide: $iface"; exit 1; }

stamp="$(date +%F-%H%M%S)"
snapshot="${BACKUP_DIR}/netplan-${stamp}"
mkdir -p "$snapshot"
cp -a /etc/netplan/. "$snapshot/" 2>/dev/null || true

restore_netplan() {
  rm -f /etc/netplan/*.yaml
  cp -a "$snapshot/." /etc/netplan/ 2>/dev/null || true
  netplan generate >/dev/null 2>&1 || true
  netplan apply >/dev/null 2>&1 || true
}

renderer="networkd"
if systemctl is-active --quiet NetworkManager 2>/dev/null; then
  renderer="NetworkManager"
fi

for other in /etc/netplan/*.yaml; do
  [[ -e "$other" ]] || continue
  [[ "$other" == "$CONF" ]] && continue
  if grep -Eq "(^|[^[:alnum:]_-])${iface}([^[:alnum:]_-]|$)" "$other"; then
    mv -f "$other" "${other}.pincabos-disabled"
    echo "Désactivé (conflit sur ${iface}): $(basename "$other")"
  fi
done
[[ -f "$LEGACY" ]] && mv -f "$LEGACY" "${LEGACY}.pincabos-disabled" || true

tmp="$(mktemp /etc/netplan/.pincabos-network-dhcp.XXXXXX)"

cat > "$tmp" <<EOF_YAML
# PINCABOS_NETWORK_V2 — configuration réseau pilotée par la WebApp PinCabOS.
# Fichier unique et prioritaire : ne pas rétablir les fichiers .pincabos-disabled.
network:
  version: 2
  renderer: ${renderer}
  ethernets:
    ${iface}:
      dhcp4: true
      dhcp6: false
      optional: true
EOF_YAML

chmod 600 "$tmp"
mv -f "$tmp" "$CONF"

if ! netplan generate; then
  echo "ERREUR: Netplan refuse la configuration. Restauration automatique."
  restore_netplan
  exit 1
fi

if ! netplan apply; then
  echo "ERREUR: application Netplan échouée. Restauration automatique."
  restore_netplan
  exit 1
fi

ok=0
for _ in $(seq 1 15); do
  if ip -o -4 addr show dev "$iface" scope global 2>/dev/null | grep -q 'inet '; then
    ok=1
    break
  fi
  sleep 1
done

if [[ "$ok" -ne 1 ]]; then
  echo "ERREUR: aucune adresse obtenue en DHCP sur ${iface}."
  echo "Restauration de la configuration précédente."
  restore_netplan
  exit 1
fi

current="$(ip -o -4 addr show dev "$iface" scope global 2>/dev/null | awk '{print $4; exit}')"
echo "OK: DHCP appliqué et vérifié sur ${iface}."
echo "Adresse obtenue: ${current}"
echo "Renderer: ${renderer}"
echo "Sauvegarde: ${snapshot}"
echo "WebApp accessible sur: http://${current%%/*}/"
