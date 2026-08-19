#!/bin/bash
# PinCabOS-File created by Karots Sugarpie
set -e

systemctl enable --now NetworkManager 2>/dev/null || true

# PINCABOS_WIFI_RESCAN_V1
# Sans rescan explicite, nmcli rend la derniere liste connue : au premier
# appel apres le demarrage elle est vide, ce qui donne l'impression que la
# carte ne fonctionne pas.
nmcli dev wifi rescan >/dev/null 2>&1 || true
sleep 3

nmcli -t -f SSID,SIGNAL,SECURITY dev wifi list 2>/dev/null | awk -F: '
  $1 != "" {
    ssid=$1
    signal=$2
    security=$3
    if (!seen[ssid]++) {
      print ssid "|" signal "|" security
    }
  }
'
