#!/bin/bash
# PinCabOS-File created by Karots Sugarpie
set -e

systemctl enable --now NetworkManager 2>/dev/null || true

echo "Arrêt des connexions hotspot PinCabOS..."

nmcli -t -f NAME,TYPE connection show --active | awk -F: '$2=="wifi" {print $1}' | while read -r con; do
  if echo "$con" | grep -qiE "Hotspot|PinCabOS|PinCabOS_WiFi"; then
    nmcli connection down "$con" || true
  fi
done

nmcli -t -f NAME connection show | grep -iE "Hotspot|PinCabOS|PinCabOS_WiFi" | while read -r con; do
  nmcli connection delete "$con" || true
done

echo "Hotspot désactivé."
nmcli device status || true
