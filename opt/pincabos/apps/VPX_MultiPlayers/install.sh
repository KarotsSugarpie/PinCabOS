#!/usr/bin/env bash
set -Eeuo pipefail

ROOT=/opt/pincabos/apps/VPX_MultiPlayers
AGENT="$ROOT/bin/pincabos-multiplayer-agent"
UNIT_SOURCE="$ROOT/systemd/pincabos-multiplayer-agent.service"
UNIT_TARGET=/etc/systemd/system/pincabos-multiplayer-agent.service
SUDOERS=/etc/sudoers.d/pincabos-multiplayer
SOURCE="${1:-}"

fail() {
    printf 'NOGO [!!] %s\n' "$*" >&2
    exit 1
}

[[ "$EUID" -eq 0 ]] || fail "Lance ce script avec sudo."
[[ -n "$SOURCE" && -d "$SOURCE" ]] || fail "Donne le dossier complet du runtime VPX source."
[[ -f "$AGENT" ]] || fail "Agent multijoueur absent."
[[ -f "$UNIT_SOURCE" ]] || fail "Unité systemd du LAB absente."
[[ ! -e "$ROOT/engine" ]] || fail "Un moteur isolé est déjà installé; aucun écrasement automatique."

chmod 0755 "$AGENT" "$ROOT/install.sh" "$ROOT/uninstall.sh"

printf 'GO: audit du dossier source en lecture seule.\n'
"$AGENT" install-engine "$SOURCE"

install -o root -g root -m 0644 "$UNIT_SOURCE" "$UNIT_TARGET"
install -d -o root -g root -m 0750 /etc/sudoers.d
printf '%s\n' \
    'pinball ALL=(root) NOPASSWD: /opt/pincabos/apps/VPX_MultiPlayers/bin/pincabos-multiplayer-agent' \
    > "$SUDOERS"
chmod 0440 "$SUDOERS"
visudo -cf "$SUDOERS" >/dev/null || fail "Règle sudo invalide."

for directory in home config data cache logs sessions tables-test; do
    chown -R pinball:pinball "$ROOT/$directory"
done

systemctl daemon-reload
systemctl enable --now pincabos-multiplayer-agent.service
systemctl is-active --quiet pincabos-multiplayer-agent.service \
    || fail "Le nouvel agent n'est pas actif."

printf 'GO: VPX MultiPlayers LAB installé sous %s.\n' "$ROOT"
printf 'GO: le VPX privé et VPinFE n’ont pas été modifiés.\n'
