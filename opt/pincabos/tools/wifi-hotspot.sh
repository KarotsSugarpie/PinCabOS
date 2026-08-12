#!/bin/bash
# PinCabOS-File created by Karots Sugarpie
set -e

SSID="$1"
PASS="$2"

if [ -z "$SSID" ] || [ -z "$PASS" ]; then
  echo "Usage: $0 SSID PASSWORD"
  echo "Mot de passe minimum recommandé: 8 caractères"
  exit 1
fi

if [ ${#PASS} -lt 8 ]; then
  echo "ERREUR: mot de passe hotspot trop court. Minimum 8 caractères."
  exit 1
fi

systemctl enable --now NetworkManager 2>/dev/null || true

WIFI_IFACE="$(nmcli -t -f DEVICE,TYPE device status | awk -F: '$2=="wifi" {print $1; exit}')"

if [ -z "$WIFI_IFACE" ]; then
  echo "ERREUR: aucune interface WiFi détectée."
  exit 1
fi

echo "Interface WiFi détectée: $WIFI_IFACE"
echo "Création hotspot: $SSID"

nmcli device wifi hotspot ifname "$WIFI_IFACE" ssid "$SSID" password "$PASS"

echo
echo "Hotspot créé."
nmcli connection show --active || true
ip -br a
