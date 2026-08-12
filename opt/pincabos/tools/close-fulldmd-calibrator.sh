#!/usr/bin/env bash
# PinCabOS-File created by Karots Sugarpie
set -u

mkdir -p /opt/pincabos/logs

echo "PinCabOS: fermeture Calibration FullDMD"

# Ne jamais tuer VPinFE. On cible seulement les profils/URLs/noms calibrateur.
pkill -f '/tmp/pincabos_fulldmd_calibrator_screen' 2>/dev/null || true
pkill -f 'pincabos-fulldmd-calibrator' 2>/dev/null || true
pkill -f '/fulldmd-screen' 2>/dev/null || true

rm -f /run/pincabos-fulldmd-calibrator.active 2>/dev/null || true
rm -rf /tmp/pincabos_fulldmd_calibrator_screen* 2>/dev/null || true

echo "$(date '+%F %T') - FullDMD calibrator closed" >> /opt/pincabos/logs/fulldmd-live.log
exit 0
