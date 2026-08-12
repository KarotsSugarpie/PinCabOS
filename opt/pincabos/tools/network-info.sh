#!/bin/bash
# PinCabOS-File created by Karots Sugarpie

MAIN_IFACE="$(ip route | awk '/default/ {print $5; exit}')"
[ -z "$MAIN_IFACE" ] && MAIN_IFACE="$(ip -br link | awk 'NR==1 {print $1}')"

echo "=================================================="
echo " PinCabOS - Configuration réseau actuelle"
echo "=================================================="
echo

echo "[Interface principale]"
echo "${MAIN_IFACE:-non détectée}"
echo

if [ -n "$MAIN_IFACE" ]; then
  echo "[IPv4]"
  ip -4 addr show "$MAIN_IFACE" | awk '/inet / {print "Adresse/CIDR : "$2}'
  echo

  echo "[IPv6]"
  if ip -6 addr show "$MAIN_IFACE" | grep -q "inet6"; then
    echo "IPv6 actif : oui"
    ip -6 addr show "$MAIN_IFACE" | awk '/inet6 / {print "Adresse IPv6 : "$2" "$3" "$4}'
  else
    echo "IPv6 actif : non"
  fi
  echo

  echo "[Passerelle]"
  ip route | awk '/default/ {print "Gateway : "$3" via "$5}'
  echo

  echo "[DNS]"
  resolvectl dns "$MAIN_IFACE" 2>/dev/null || cat /etc/resolv.conf 2>/dev/null || true
  echo

  echo "[Mode DHCP/IP fixe - détection]"
  if command -v networkctl >/dev/null 2>&1; then
    networkctl status "$MAIN_IFACE" 2>/dev/null | grep -Ei "DHCP|Address|Gateway|DNS" || true
  fi

  if [ -f /etc/netplan/99-pincabos-network.yaml ]; then
    echo
    echo "[Netplan PinCabOS]"
    cat /etc/netplan/99-pincabos-network.yaml
  else
    echo
    echo "Netplan PinCabOS : aucun fichier /etc/netplan/99-pincabos-network.yaml"
  fi
  echo

  echo "[Lien interface]"
  ip -br link show "$MAIN_IFACE"
fi

echo
echo "=================================================="
echo " Interfaces réseau"
echo "=================================================="
ip -br a
echo

echo "=================================================="
echo " Routes"
echo "=================================================="
ip route
echo

echo "=================================================="
echo " Interfaces WiFi / NetworkManager"
echo "=================================================="
if command -v nmcli >/dev/null 2>&1; then
  nmcli device status || true
  echo

  WIFI_IFACES="$(nmcli -t -f DEVICE,TYPE device status | awk -F: '$2=="wifi" {print $1}')"

  if [ -n "$WIFI_IFACES" ]; then
    for WIFI in $WIFI_IFACES; do
      echo "[WiFi: $WIFI]"
      nmcli -f GENERAL.DEVICE,GENERAL.TYPE,GENERAL.STATE,GENERAL.CONNECTION,IP4.ADDRESS,IP4.GATEWAY,IP4.DNS,IP6.ADDRESS device show "$WIFI" 2>/dev/null || true
      echo
    done
  else
    echo "Aucune interface WiFi détectée par NetworkManager."
  fi

  echo
  echo "[Réseaux WiFi visibles]"
  nmcli -t -f SSID,SIGNAL,SECURITY dev wifi list 2>/dev/null | head -n 40 || true
else
  echo "NetworkManager / nmcli non disponible."
fi

echo
echo "=================================================="
echo " Matériel réseau"
echo "=================================================="
lspci -nn | grep -Ei "ethernet|network|wireless|wifi" || true
lsusb | grep -Ei "wifi|wireless|802.11|realtek|mediatek|ralink|ath|intel" || true
