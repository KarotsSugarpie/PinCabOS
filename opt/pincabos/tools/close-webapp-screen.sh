#!/usr/bin/env bash
# PinCabOS-File created by Karots Sugarpie
set -u

mkdir -p /opt/pincabos/logs

echo "PinCabOS: fermeture fenêtres WebApp Playfield/Backglass"

# Ne pas tuer VPinFE. Cibler seulement les profils/fenêtres WebApp screen.
pkill -f '/tmp/pincabos_webapp_screen_' 2>/dev/null || true
pkill -f 'pincabos-webapp-screen-' 2>/dev/null || true

rm -f /run/pincabos-webapp-screen-*.active 2>/dev/null || true
rm -rf /tmp/pincabos_webapp_screen_* 2>/dev/null || true

echo "$(date '+%F %T') - WebApp screen windows closed" >> /opt/pincabos/logs/menu-webapp-screen-close.log
exit 0
