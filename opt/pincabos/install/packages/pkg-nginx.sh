#!/usr/bin/env bash
set -Eeuo pipefail

echo "────────────────────────────────────────────────────────────────"
echo " PinCabOS - disabled in official direct-port runtime"
echo "────────────────────────────────────────────────────────────────"

if command -v systemctl >/dev/null 2>&1; then
  if systemctl list-unit-files nginx.service >/dev/null 2>&1; then
    systemctl stop nginx.service 2>/dev/null || true
    systemctl disable nginx.service 2>/dev/null || true
    systemctl mask nginx.service 2>/dev/null || true
    echo "GO: service stopped/disabled/masked"
  else
    echo "GO: service not installed; nothing to disable"
  fi
else
  echo "GO: systemctl unavailable; guard skipped"
fi

echo "GO: not required; PinCabOS uses WebApp=80 ttyd=8090 VPinFE=8000/8001"
