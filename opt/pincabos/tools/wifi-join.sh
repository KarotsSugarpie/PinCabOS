#!/bin/bash
# PinCabOS-File created by Karots Sugarpie
set -e

SSID="$1"
PASS="$2"

if [ -z "$SSID" ]; then
  echo "Usage: $0 SSID PASSWORD"
  exit 1
fi

systemctl enable --now NetworkManager 2>/dev/null || true

echo "Réseaux WiFi visibles:"
nmcli dev wifi list || true

echo
echo "Connexion au WiFi: $SSID"

if [ -z "$PASS" ]; then
  nmcli dev wifi connect "$SSID"
else
  nmcli dev wifi connect "$SSID" password "$PASS"
fi

echo
echo "État réseau:"
nmcli device status || true
ip -br a
