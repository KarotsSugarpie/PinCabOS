#!/usr/bin/env bash
set -Eeuo pipefail

[[ "$EUID" -eq 0 ]] || {
    printf 'NOGO [!!] Lance ce script avec sudo.\n' >&2
    exit 1
}

systemctl disable --now pincabos-multiplayer-agent.service 2>/dev/null || true
rm -f /etc/systemd/system/pincabos-multiplayer-agent.service
rm -f /etc/sudoers.d/pincabos-multiplayer
systemctl daemon-reload

printf '%s\n' 'GO: intégration VPX MultiPlayers LAB désactivée.'
printf '%s\n' 'Les fichiers isolés sont conservés sous /opt/pincabos/apps/VPX_MultiPlayers.'
printf '%s\n' 'Le VPX privé et VPinFE n’ont pas été modifiés.'

