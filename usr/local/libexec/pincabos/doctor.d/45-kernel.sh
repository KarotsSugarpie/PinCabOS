#!/usr/bin/env bash
# PINCABOS_DOCTOR_KERNEL_V1

pco_section "KERNEL"

running="$(uname -r)"
count="$(dpkg -l 'linux-image-[0-9]*' 2>/dev/null | grep -c '^ii')"
newest="$(dpkg -l 'linux-image-[0-9]*' 2>/dev/null | awk '/^ii/{sub(/^linux-image-/,"",$2); print $2}' | sort -V | tail -1)"

pco_go "Kernel actif" "$running (${count:-?} installe(s))"

if [[ -n "$newest" && "$newest" != "$running" ]]; then
    pco_warn "Kernel plus recent installe" "$newest — un redemarrage l'activera"
fi

if [[ -e /run/pincabos-kernel-reboot-required ]]; then
    pco_warn "Maintenance kernel" "redemarrage requis (drapeau pose par pincabos-kernel-maintenance)"
fi

if [[ "${count:-0}" -gt 2 ]]; then
    pco_warn "Anciens kernels" "$count versions installees — lancer : sudo pincabos-kernel-maintenance"
fi

# Pendant qu'on y est : detecter le rendu logiciel (cas reel du terrain, un
# cabinet peut tourner en llvmpipe sans qu'aucun signal ne remonte).
if command -v glxinfo >/dev/null 2>&1; then
    renderer="$(DISPLAY=:0 XAUTHORITY=/home/pinball/.Xauthority runuser -u pinball -- glxinfo 2>/dev/null | awk -F': ' '/OpenGL renderer/{print $2; exit}')"
    if [[ "$renderer" == *llvmpipe* || "$renderer" == *softpipe* ]]; then
        pco_fail "Rendu 3D LOGICIEL" "$renderer — aucun pilote GPU actif, performances et affichage degrades"
    elif [[ -n "$renderer" ]]; then
        pco_go "Rendu 3D" "$renderer"
    fi
fi
