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
ipcidr="${2:-}"
gateway="${3:-}"
dns="${4:-}"

if [[ -z "$iface" ]]; then
  iface="$(find_main_iface || true)"
fi

dns="$(printf '%s' "$dns" | tr -d '[:space:]')"

[[ -n "$iface" ]] || { echo "ERREUR: interface réseau introuvable."; exit 1; }
[[ -d "/sys/class/net/$iface" ]] || { echo "ERREUR: interface invalide: $iface"; exit 1; }
[[ -n "$ipcidr" ]] || { echo "ERREUR: adresse IP/CIDR manquante."; exit 1; }
[[ -n "$gateway" ]] || { echo "ERREUR: passerelle manquante."; exit 1; }
[[ -n "$dns" ]] || { echo "ERREUR: DNS manquant."; exit 1; }

python3 - "$ipcidr" "$gateway" "$dns" <<'PY'
import ipaddress
import sys

ipcidr, gateway, dns = sys.argv[1:]

try:
    address = ipaddress.ip_interface(ipcidr)
    if address.version != 4:
        raise ValueError("IPv4 requis")
    route = ipaddress.ip_address(gateway)
    if route.version != 4:
        raise ValueError("Passerelle IPv4 requise")
    servers = [item for item in dns.split(",") if item]
    if not servers:
        raise ValueError("DNS manquant")
    for server in servers:
        ipaddress.ip_address(server)
except ValueError as exc:
    print(f"ERREUR: valeurs réseau invalides: {exc}")
    raise SystemExit(1)
PY

mkdir -p "$BACKUP_DIR"
stamp="$(date +%F-%H%M%S)"
backup="${BACKUP_DIR}/00-pincabos-dhcp4.yaml.before-static-${stamp}"

if [[ -f "$CONF" ]]; then
  cp -a "$CONF" "$backup"
fi

tmp="$(mktemp /etc/netplan/.pincabos-network-static.XXXXXX)"
dns_yaml="$(printf '%s' "$dns" | sed 's/,/, /g')"

cat > "$tmp" <<EOF_YAML
network:
  version: 2
  renderer: networkd
  ethernets:
    ${iface}:
      dhcp4: false
      addresses:
        - ${ipcidr}
      routes:
        - to: default
          via: ${gateway}
      nameservers:
        addresses: [${dns_yaml}]
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

echo "OK: IP fixe appliquée sur ${iface}."
echo "IP/CIDR: ${ipcidr}"
echo "Passerelle: ${gateway}"
echo "DNS: ${dns}"
echo "Sauvegarde: ${backup}"
