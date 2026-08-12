#!/usr/bin/env bash
# PinCabOS-File created by Karots Sugarpie
set -u

mkdir -p /opt/pincabos/logs

echo "PinCabOS: fermeture Calibration DMD"

# Ne jamais tuer VPinFE. On cible seulement les profils/URLs/noms calibrateur.
pkill -f '/tmp/pincabos_dmd_calibrator_screen' 2>/dev/null || true
pkill -f 'pincabos-dmd-calibrator' 2>/dev/null || true
pkill -f '/dmd-screen' 2>/dev/null || true

rm -f /run/pincabos-dmd-calibrator.active 2>/dev/null || true
rm -rf /tmp/pincabos_dmd_calibrator_screen* 2>/dev/null || true

echo "$(date '+%F %T') - DMD calibrator closed" >> /opt/pincabos/logs/fulldmd-live.log
exit 0
