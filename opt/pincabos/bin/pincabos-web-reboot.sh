#!/usr/bin/env bash
set -Eeuo pipefail

case "${1:-}" in
  --check)
    test -x /usr/bin/systemctl
    exit 0
    ;;
  "")
    sleep 2
    exec /usr/bin/systemctl reboot
    ;;
  *)
    echo "Usage: pincabos-web-reboot.sh [--check]" >&2
    exit 64
    ;;
esac
