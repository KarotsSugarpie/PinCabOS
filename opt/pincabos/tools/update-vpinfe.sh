#!/usr/bin/env bash
# PINCABOS_VPINFE_CONFIG_GUARD_V1
#
# Protège la configuration utilisateur pendant une mise à jour VPinFE.
# Le binaire VPinFE est mis à jour par l'updater officiel PinCabOS,
# mais vpinfe.ini est restauré avant le redémarrage final de VPinFE.

set -Euo pipefail
umask 077

UPDATER="/opt/pincabos/tools/vpinfeupdate.py"
INI="/home/pinball/.config/vpinfe/vpinfe.ini"
CONFIG_DIR="/home/pinball/.config/vpinfe"

VPINFE_SERVICE="pincabos-vpinfe.service"
LIVE_SERVICE="pincabos-dashboard-live.service"
LIVE_DIR="/run/pincabos-dashboard-live"

BACKUP_ROOT="/opt/pincabos/backups/vpinfe-config-guard"
STAMP="$(date +%Y%m%d-%H%M%S)"
RUN_BACKUP="$BACKUP_ROOT/update-$STAMP"
INI_BACKUP="$RUN_BACKUP/vpinfe.ini.before"

WAS_VPINFE_ACTIVE=0
WAS_LIVE_ACTIVE=0
HAD_INI=0

systemctl is-active --quiet "$VPINFE_SERVICE" \
    && WAS_VPINFE_ACTIVE=1 || true

systemctl is-active --quiet "$LIVE_SERVICE" \
    && WAS_LIVE_ACTIVE=1 || true

install -d -o root -g root -m 0755 \
    "$BACKUP_ROOT" \
    "$RUN_BACKUP"

if [[ -f "$INI" ]]; then
    HAD_INI=1

    install -o root -g root -m 0600 \
        "$INI" \
        "$INI_BACKUP"

    sha256sum "$INI_BACKUP" \
        > "$RUN_BACKUP/vpinfe.ini.before.sha256"

    echo "Configuration VPinFE protégée : $INI_BACKUP"
else
    echo "AVERTISSEMENT : aucun vpinfe.ini présent avant la mise à jour."
fi

restore_and_restart() {
    local original_rc="$1"
    local final_rc="$original_rc"
    local temporary_ini=""

    trap - EXIT INT TERM
    set +e

    echo
    echo "=== Finalisation PinCabOS de la mise à jour VPinFE ==="

    if [[ "$HAD_INI" -eq 1 && -f "$INI_BACKUP" ]]; then
        echo "Arrêt contrôlé de VPinFE avant restauration de l'INI..."
        systemctl stop "$VPINFE_SERVICE"

        install -d -o pinball -g pinball -m 0700 \
            "$CONFIG_DIR"

        temporary_ini="${CONFIG_DIR}/.vpinfe.ini.restore.$$"

        install -o pinball -g pinball -m 0600 \
            "$INI_BACKUP" \
            "$temporary_ini"

        if mv -f "$temporary_ini" "$INI"; then
            chown pinball:pinball "$INI"
            chmod 0600 "$INI"

            echo "OK : vpinfe.ini original restauré."

            sha256sum "$INI" \
                > "$RUN_BACKUP/vpinfe.ini.restored.sha256"
        else
            echo "ERREUR : restauration de vpinfe.ini impossible." >&2
            rm -f "$temporary_ini"
            final_rc=70
        fi
    fi

    if [[ "$WAS_VPINFE_ACTIVE" -eq 1 ]]; then
        echo "Redémarrage de VPinFE avec l'INI restauré..."
        systemctl restart "$VPINFE_SERVICE"

        if systemctl is-active --quiet "$VPINFE_SERVICE"; then
            echo "OK : VPinFE actif."
        else
            echo "ERREUR : VPinFE n'est pas actif après restauration." >&2
            final_rc=71
        fi
    else
        systemctl stop "$VPINFE_SERVICE" >/dev/null 2>&1 || true
        echo "VPinFE était arrêté avant la mise à jour : état conservé."
    fi

    echo "Nettoyage et redémarrage du moteur Dashboard Live..."

    if [[ -d "$LIVE_DIR" ]]; then
        find "$LIVE_DIR" \
            -maxdepth 1 \
            -type f \
            \( -name "*.tmp" -o -size 0 \) \
            -delete 2>/dev/null || true
    fi

    if [[ "$WAS_LIVE_ACTIVE" -eq 1 ]] \
        || systemctl is-enabled --quiet "$LIVE_SERVICE" 2>/dev/null; then

        systemctl restart "$LIVE_SERVICE"

        if systemctl is-active --quiet "$LIVE_SERVICE"; then
            echo "OK : moteur des écrans Live relancé."
        else
            echo "AVERTISSEMENT : moteur Live non actif." >&2
        fi
    fi

    if [[ "$original_rc" -ne 0 ]]; then
        echo "La mise à jour VPinFE avait retourné le code : $original_rc"
    fi

    echo "Backup de cette mise à jour : $RUN_BACKUP"
    exit "$final_rc"
}

trap 'restore_and_restart $?' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

echo
echo "=== Exécution de l'updater VPinFE officiel PinCabOS ==="

/usr/bin/python3 \
    "$UPDATER" \
    --update
