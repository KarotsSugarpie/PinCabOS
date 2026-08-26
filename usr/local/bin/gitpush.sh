#!/usr/bin/env bash
set -Eeuo pipefail

exec sudo -n /opt/pincabos/tools/pincabos-gitpush-root.sh "$@"
