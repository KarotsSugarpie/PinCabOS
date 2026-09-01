#!/usr/bin/env bash
# PINCABOS_DOCTOR_CONTROLLED_CLEANUP_V2

pco_section "NETTOYAGE CONTRÔLÉ"

obsolete_units=(
    pincabos-place-backbox.service
    pincabos-b2s-layer-guard.service
    pincabos-scoreview-router.service
    pincabos-display-roles.service
    pincabos-screen-topology.service
    pincabos-screen-topology.timer
    pincabos-screen-topology.path
    pincabos-web.service
)

obsolete_found=()

for unit in "${obsolete_units[@]}"; do
    load_state="$(
        systemctl show "$unit" \
            -p LoadState \
            --value 2>/dev/null || true
    )"

    active_state="$(
        systemctl show "$unit" \
            -p ActiveState \
            --value 2>/dev/null || true
    )"

    unit_state="$(
        systemctl show "$unit" \
            -p UnitFileState \
            --value 2>/dev/null || true
    )"

    # Une unité absente ou volontairement masquée n’est pas un zombie.
    if [[ "$load_state" == "not-found" ||
          "$load_state" == "masked" ||
          "$unit_state" == "masked" ]]; then
        continue
    fi

    # pincabos-web.service peut être un alias légitime du service principal.
    if [[ "$unit" == "pincabos-web.service" ]]; then
        names="$(
            systemctl show "$unit" \
                -p Names \
                --value 2>/dev/null || true
        )"

        legacy_fragment="$(
            systemctl show "$unit" \
                -p FragmentPath \
                --value 2>/dev/null || true
        )"

        main_fragment="$(
            systemctl show pincabos-webapp.service \
                -p FragmentPath \
                --value 2>/dev/null || true
        )"

        legacy_real=""
        main_real=""

        if [[ -n "$legacy_fragment" ]]; then
            legacy_real="$(
                readlink -f "$legacy_fragment" 2>/dev/null || true
            )"
        fi

        if [[ -n "$main_fragment" ]]; then
            main_real="$(
                readlink -f "$main_fragment" 2>/dev/null || true
            )"
        fi

        if grep -qw \
            'pincabos-webapp.service' \
            <<<"$names"; then
            continue
        fi

        if [[ -n "$legacy_real" &&
              -n "$main_real" &&
              "$legacy_real" == "$main_real" ]]; then
            continue
        fi
    fi

    obsolete=0

    if [[ "$active_state" == "active" ||
          "$active_state" == "activating" ]]; then
        obsolete=1
    fi

    case "$unit_state" in
        enabled|enabled-runtime|linked|linked-runtime)
            obsolete=1
            ;;
    esac

    # Une ancienne unité simplement présente mais désactivée et inactive
    # n’est pas considérée comme un service zombie.
    if [[ "$obsolete" -eq 0 ]]; then
        continue
    fi

    obsolete_found+=("$unit")

    if pco_repairing; then
        systemctl disable --now "$unit" \
            >/dev/null 2>&1 || true

        systemctl mask "$unit" \
            >/dev/null 2>&1 || true
    fi
done

if [[ "${#obsolete_found[@]}" -eq 0 ]]; then
    pco_go \
        "Services zombies" \
        "aucune ancienne unité indépendante active"

elif pco_repairing; then
    pco_go \
        "Services zombies" \
        "neutralisés : ${obsolete_found[*]}"

else
    pco_warn \
        "Services zombies" \
        "actifs : ${obsolete_found[*]}"
fi

root_artifacts="$(
    find / -maxdepth 1 -type f \
        \( \
            -name 'pincabos-rootfs-cab-*.tar.zst' -o \
            -name 'pincabos-rootfs-cab-*.tar.zst.part-*' -o \
            -name 'pincabos-plymouth-theme-overlay-*.tar.zst' -o \
            -name 'payload-file-list-python-webapp.txt' -o \
            -name 'MANIFEST.txt' \
        \) \
        -print 2>/dev/null || true
)"

if [[ -z "$root_artifacts" ]]; then
    pco_go \
        "Artefacts racine" \
        "aucun payload généré à la racine"

elif pco_repairing; then
    while IFS= read -r item; do
        [[ -n "$item" ]] && rm -f -- "$item"
    done <<<"$root_artifacts"

    pco_go \
        "Artefacts racine" \
        "supprimés"

else
    pco_warn \
        "Artefacts racine" \
        "$(tr '\n' ' ' <<<"$root_artifacts")"
fi

systemctl daemon-reload >/dev/null 2>&1 || true
systemctl reset-failed >/dev/null 2>&1 || true

pco_go \
    "Systemd reload" \
    "daemon-reload + reset-failed"
