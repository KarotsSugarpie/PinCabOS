#!/usr/bin/env bash
set -Eeuo pipefail

# PINCABOS_PUP_FONTS_AUTOINSTALL_V1
#
# Le plugin PUP de VPX Standalone charge ses polices depuis un dossier FONTS
# (en majuscules) du PuP-Pack — PAS depuis fontconfig. Or les packs livrent
# leurs .ttf dans Tables/<table>/fonts/ (convention Windows, ou l'utilisateur
# les installe a la main). Sans copie vers FONTS, PUPLabel echoue :
#   ERROR [PUPLabel::PUPLabel] Font not found: font=...
#   ERROR [PUPPinDisplay::LabelSet] Invalid label
# et tous les textes du pack restent invisibles (ex. les parchemins du pack
# Harry Potter).
#
# Ce script recopie les polices fournies par la table vers les dossiers FONTS
# de ses PuP-Packs. Il est appele au lancement de chaque table (idempotent,
# ne remplace jamais un fichier existant) : tout pack importe est repare a son
# premier lancement, sans intervention.

TARGET_VPX=""
for arg in "$@"; do
    case "$arg" in
        *.vpx|*.VPX)
            if [[ -f "$arg" ]]; then
                TARGET_VPX="$arg"
                break
            fi
            ;;
    esac
done
[[ -n "$TARGET_VPX" ]] || exit 0

TABLE_DIR="$(dirname "$TARGET_VPX")"

# 1) Polices fournies par la table : dossier fonts/ (toute casse), .ttf/.otf.
mapfile -t SOURCES < <(
    find "$TABLE_DIR" -maxdepth 1 -type d -iname fonts -print0 2>/dev/null |
    xargs -0 -r -I{} find "{}" -maxdepth 1 -type f \
        \( -iname '*.ttf' -o -iname '*.otf' \) 2>/dev/null
)
[[ ${#SOURCES[@]} -gt 0 ]] || exit 0

# 2) Racines PuP de la table (toutes les variantes rencontrees dans les packs).
mapfile -t PUP_ROOTS < <(
    find "$TABLE_DIR" -maxdepth 1 -type d \
        \( -iname pupvideo -o -iname pupvideos \
           -o -iname pinupvideo -o -iname pinupvideos \) 2>/dev/null
)
[[ ${#PUP_ROOTS[@]} -gt 0 ]] || exit 0

install_into() {
    local fonts_dir="$1/FONTS"
    local copied=0 src base

    mkdir -p "$fonts_dir"
    for src in "${SOURCES[@]}"; do
        base="$(basename "$src")"
        if [[ ! -e "$fonts_dir/$base" ]]; then
            cp -p "$src" "$fonts_dir/$base" && copied=$((copied + 1))
        fi
    done
    chown -R pinball:pinball "$fonts_dir" 2>/dev/null || true

    if [[ $copied -gt 0 ]]; then
        logger -t pincabos-pup-fonts \
            "$copied police(s) copiee(s) vers $fonts_dir" 2>/dev/null || true
    fi
}

for root in "${PUP_ROOTS[@]}"; do
    # FONTS a la racine pupvideos (packs sans sous-dossier / PUPFolder table).
    install_into "$root"
    # FONTS dans chaque pack (pupvideos/<rom>/FONTS, l'emplacement standard).
    while IFS= read -r -d '' pack; do
        [[ "$(basename "$pack")" == "FONTS" ]] && continue
        install_into "$pack"
    done < <(find "$root" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null)
done

exit 0
