#!/usr/bin/env bash
set -Eeuo pipefail

ENGINE="/opt/pincabos/tools/pincabos-gitpush-root.sh"
RELEASE="/opt/pincabos/tools/pincabos-gitpush-release-root.sh"

case "${1:-}" in

    "")
        sudo -n "$ENGINE"
        sudo -n "$RELEASE"
        ;;

    --audit)
        exec sudo -n "$ENGINE" --audit
        ;;

    *)
        echo "Usage:"
        echo "  gitpush"
        echo "  gitpush --audit"
        exit 2
        ;;
esac
