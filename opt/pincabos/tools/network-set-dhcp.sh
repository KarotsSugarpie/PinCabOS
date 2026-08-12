#!/usr/bin/env bash
set -Eeuo pipefail
PATH="/usr/sbin:/usr/bin:/sbin:/bin"

CONF="/etc/netplan/00-pincabos-dhcp4.yaml"
BACKUP_DIR="/opt/pincabos/backups/network"

find_main_iface() {
  ip -4 route show default 2>/dev/null |
  awk '/^default/ {
    for (i=1; i<=NF; i++) {
      if ($i == "dev") {
        print $(i+1)
        exit
      }
    }
  }'
}

iface="${1:-}"

if [[ -z "$iface" ]]; then
  iface="$(find_main_iface || true)"
fi

[[ -n "$iface" ]] || { echo "ERREUR: interface réseau introuvable."; exit 1; }
[[ -d "/sys/class/net/$iface" ]] || { echo "ERREUR: interface invalide: $iface"; exit 1; }

mkdir -p "$BACKUP_DIR"
stamp="$(date +%F-%H%M%S)"
backup="${BACKUP_DIR}/00-pincabos-dhcp4.yaml.before-dhcp-${stamp}"

if [[ -f "$CONF" ]]; then
  cp -a "$CONF" "$backup"
fi

tmp="$(mktemp /etc/netplan/.pincabos-network-dhcp.XXXXXX)"

cat > "$tmp" <<EOF_YAML
network:
  version: 2
  renderer: networkd
  ethernets:
    ${iface}:
      dhcp4: true
      optional: true
EOF_YAML

chmod 600 "$tmp"
mv -f "$tmp" "$CONF"

if ! netplan generate; then
  echo "ERREUR: Netplan refuse la configuration. Restauration automatique."
  [[ -f "$backup" ]] && cp -a "$backup" "$CONF"
  netplan generate || true
  exit 1
fi

if ! netplan apply; then
  echo "ERREUR: application Netplan échouée. Restauration automatique."
  [[ -f "$backup" ]] && cp -a "$backup" "$CONF"
  netplan generate || true
  netplan apply || true
  exit 1
fi

echo "OK: DHCP appliqué sur ${iface}."
echo "Sauvegarde: ${backup}"
