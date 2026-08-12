#!/bin/bash
# PinCabOS-File created by Karots Sugarpie
set -e

systemctl enable --now NetworkManager 2>/dev/null || true

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
