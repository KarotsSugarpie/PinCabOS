#!/usr/bin/env bash
# PinCabOs-File
# install-dof-component.sh <famille|all>
#
# Prépare le support Linux d'une famille de contrôleurs DOF :
#   paquets (libusb/hidapi/pyserial), modules noyau, règles udev.
# Familles : ledwiz, pinscape-kl25z, pinscape-pico, dudes-esp, pacled,
#            ftdi, arduino, serial-usb, teensy, all
#
# Idempotent : peut être relancé sans risque. Les règles udev couvrent
# toutes les familles (une règle pour un VID absent est inoffensive),
# seule la partie paquets/modules dépend de la famille demandée.
set -u

COMPONENT="${1:-all}"
RULES_FILE="/etc/udev/rules.d/99-pincabos-dof-controllers.rules"
MODULES_FILE="/etc/modules-load.d/pincabos-dof.conf"

log() { echo "[install-dof-component] $*"; }

ensure_pkgs() {
    for p in "$@"; do
        if dpkg -s "$p" >/dev/null 2>&1; then
            log "paquet $p : déjà installé"
        else
            log "paquet $p : installation..."
            DEBIAN_FRONTEND=noninteractive apt-get install -y "$p" \
                || log "AVERTISSEMENT : paquet $p indisponible (système hors ligne ?)"
        fi
    done
}

ensure_modules() {
    touch "$MODULES_FILE"
    for m in "$@"; do
        modprobe "$m" 2>/dev/null || true
        if ! grep -qx "$m" "$MODULES_FILE" 2>/dev/null; then
            echo "$m" >> "$MODULES_FILE"
            log "module $m : ajouté à $MODULES_FILE"
        fi
    done
}

write_udev_rules() {
    cat > "$RULES_FILE" <<'EOF'
# PinCabOS — accès non-root aux contrôleurs DOF (généré par install-dof-component.sh)
# Une règle pour un périphérique absent est sans effet : on couvre toutes les familles.

# --- HID raw (LedWiz, Ultimarc, Pinscape, RP2040/DudesCab, Teensy) ---
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="fafa", MODE="0660", GROUP="plugdev", TAG+="uaccess"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="d209", MODE="0660", GROUP="plugdev", TAG+="uaccess"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="15a2", MODE="0660", GROUP="plugdev", TAG+="uaccess"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="1fc9", MODE="0660", GROUP="plugdev", TAG+="uaccess"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="1209", MODE="0660", GROUP="plugdev", TAG+="uaccess"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="2e8a", MODE="0660", GROUP="plugdev", TAG+="uaccess"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="16c0", MODE="0660", GROUP="plugdev", TAG+="uaccess"

# --- Série USB (Teensy, RP2040/DudesCab, FTDI, CH340, CP210x, ESP, Arduino) ---
SUBSYSTEM=="tty", ATTRS{idVendor}=="16c0", MODE="0660", GROUP="dialout"
SUBSYSTEM=="tty", ATTRS{idVendor}=="2e8a", MODE="0660", GROUP="dialout"
SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", MODE="0660", GROUP="dialout"
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", MODE="0660", GROUP="dialout"
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", MODE="0660", GROUP="dialout"
SUBSYSTEM=="tty", ATTRS{idVendor}=="303a", MODE="0660", GROUP="dialout"
SUBSYSTEM=="tty", ATTRS{idVendor}=="2341", MODE="0660", GROUP="dialout"
SUBSYSTEM=="tty", ATTRS{idVendor}=="2a03", MODE="0660", GROUP="dialout"
SUBSYSTEM=="tty", ATTRS{idVendor}=="1b4f", MODE="0660", GROUP="dialout"
EOF
    log "règles udev écrites : $RULES_FILE"
    udevadm control --reload-rules 2>/dev/null || true
    udevadm trigger 2>/dev/null || true
}

install_hid_family() {
    ensure_pkgs libusb-1.0-0 libhidapi-hidraw0
    ensure_modules usbhid
}

install_serial_family() {
    ensure_pkgs python3-serial
    ensure_modules usbserial cdc_acm
}

log "composant demandé : $COMPONENT"

case "$COMPONENT" in
    ledwiz|pacled)
        install_hid_family
        ;;
    pinscape-kl25z)
        install_hid_family
        ;;
    pinscape-pico)
        install_hid_family
        ensure_modules cdc_acm
        ;;
    teensy)
        install_serial_family
        ensure_modules usbhid
        ;;
    dudes-esp)
        install_serial_family
        ensure_modules ch341 cp210x
        ;;
    ftdi)
        install_serial_family
        ensure_modules ftdi_sio
        ;;
    arduino)
        install_serial_family
        ensure_modules usbhid
        ;;
    serial-usb)
        install_serial_family
        ensure_modules ch341 cp210x ftdi_sio
        ;;
    all)
        install_hid_family
        install_serial_family
        ensure_modules ch341 cp210x ftdi_sio
        ;;
    *)
        log "famille inconnue : $COMPONENT (familles : ledwiz pinscape-kl25z pinscape-pico teensy dudes-esp pacled ftdi arduino serial-usb all)"
        exit 1
        ;;
esac

write_udev_rules

# S'assure que l'utilisateur pinball a accès aux périphériques série/HID.
if id pinball >/dev/null 2>&1; then
    usermod -aG dialout,plugdev pinball 2>/dev/null || true
fi

log "terminé. Débrancher/rebrancher les cartes USB ou redémarrer si les droits ne s'appliquent pas."
exit 0
