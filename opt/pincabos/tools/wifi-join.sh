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
# PINCABOS_WIFI_JOIN_VERIFY_V1
# nmcli rend la main avant que l'association soit etablie : sans cette
# verification, un mot de passe refuse ressemble a une reussite.
etat=""
for _ in $(seq 1 15); do
  etat="$(nmcli -t -f DEVICE,STATE,CONNECTION dev status 2>/dev/null \
          | awk -F: -v s="$SSID" '$3 == s && $2 == "connected" {print $1}')"
  [ -n "$etat" ] && break
  sleep 1
done
if [ -n "$etat" ]; then
  echo "CONNECTE: $SSID sur $etat"
  nmcli -t -f IP4.ADDRESS,IP4.GATEWAY dev show "$etat" 2>/dev/null | sed 's/^/  /'
else
  echo "ECHEC: association a $SSID non etablie apres 15 s." >&2
  echo "Verifiez le mot de passe et la portee du reseau." >&2
  nmcli device status || true
  exit 1
fi

nmcli device status || true
ip -br a
