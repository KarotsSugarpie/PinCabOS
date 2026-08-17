#!/usr/bin/env bash
# PinCabOS - configuration IP fixe (V2)
#
# La V1 ecrivait /etc/netplan/00-pincabos-dhcp4.yaml, le fichier le MOINS
# prioritaire : 01-pincabos-dhcp.yaml (pose par l'installeur) et le profil
# 90-NM-<uuid>.yaml de NetworkManager le supplantaient, donc l'IP fixe
# n'etait jamais appliquee — l'interface restait en DHCP pendant que la page
# affichait "static". Elle ecrivait aussi renderer: networkd alors que
# NetworkManager gere l'interface sur le systeme installe.
#
# V2 (PINCABOS_NETWORK_V2) :
#   - fichier unique 99-pincabos-network.yaml, prioritaire sur tous les autres ;
#   - les definitions concurrentes de CETTE interface sont desactivees
#     (convention .pincabos-disabled deja utilisee par PinCabOS) ;
#   - renderer detecte a l'execution (NetworkManager s'il gere la machine) ;
#   - l'adresse obtenue est VERIFIEE apres application : en cas d'echec, la
#     configuration precedente est restauree et l'erreur est annoncee, au lieu
#     de repondre OK sur une configuration sans effet.
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
ipcidr="${2:-}"
gateway="${3:-}"
dns="${4:-}"

[[ -n "$iface" ]] || iface="$(find_main_iface || true)"
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
    if route not in address.network:
        print(f"AVERTISSEMENT: la passerelle {route} est hors du réseau {address.network}.")
except ValueError as exc:
    print(f"ERREUR: valeurs réseau invalides: {exc}")
    raise SystemExit(1)
PY

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

# Renderer effectif : NetworkManager pilote l'interface sur le systeme
# installe ; ecrire "networkd" produit une configuration ignoree.
renderer="networkd"
if systemctl is-active --quiet NetworkManager 2>/dev/null; then
  renderer="NetworkManager"
fi

# Desactive toute autre definition de CETTE interface (sinon la precedence
# netplan ou un profil NM concurrent reimpose le DHCP).
for other in /etc/netplan/*.yaml; do
  [[ -e "$other" ]] || continue
  [[ "$other" == "$CONF" ]] && continue
  if grep -Eq "(^|[^[:alnum:]_-])${iface}([^[:alnum:]_-]|$)" "$other"; then
    mv -f "$other" "${other}.pincabos-disabled"
    echo "Désactivé (conflit sur ${iface}): $(basename "$other")"
  fi
done
[[ -f "$LEGACY" ]] && mv -f "$LEGACY" "${LEGACY}.pincabos-disabled" || true

tmp="$(mktemp /etc/netplan/.pincabos-network-static.XXXXXX)"
dns_yaml="$(printf '%s' "$dns" | sed 's/,/, /g')"

cat > "$tmp" <<EOF_YAML
# PINCABOS_NETWORK_V2 — configuration réseau pilotée par la WebApp PinCabOS.
# Fichier unique et prioritaire : ne pas rétablir les fichiers .pincabos-disabled.
network:
  version: 2
  renderer: ${renderer}
  ethernets:
    ${iface}:
      dhcp4: false
      dhcp6: false
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
  restore_netplan
  exit 1
fi

if ! netplan apply; then
  echo "ERREUR: application Netplan échouée. Restauration automatique."
  restore_netplan
  exit 1
fi

# Verification REELLE : l'adresse demandee doit etre portee par l'interface.
wanted="${ipcidr%%/*}"
ok=0
for _ in $(seq 1 12); do
  if ip -o -4 addr show dev "$iface" 2>/dev/null | grep -qw "$ipcidr"; then
    ok=1
    break
  fi
  sleep 1
done

if [[ "$ok" -ne 1 ]]; then
  echo "ERREUR: l'adresse ${ipcidr} n'a pas été appliquée sur ${iface}."
  echo "Adresses actuelles: $(ip -br -4 addr show dev "$iface" 2>/dev/null | awk '{$1="";$2="";print}')"
  echo "Restauration de la configuration précédente."
  restore_netplan
  exit 1
fi

echo "OK: IP fixe appliquée et vérifiée sur ${iface}."
echo "IP/CIDR: ${ipcidr}"
echo "Passerelle: ${gateway}"
echo "DNS: ${dns}"
echo "Renderer: ${renderer}"
echo "Sauvegarde: ${snapshot}"
echo "WebApp accessible sur: http://${wanted}/"
