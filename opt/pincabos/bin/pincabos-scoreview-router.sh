#!/usr/bin/env bash
set -u

RUNTIME_DIR="/run/pincabos-b2s-dmd-tuner"
mkdir -p "$RUNTIME_DIR"
chown pinball:pinball "$RUNTIME_DIR"
chmod 0770 "$RUNTIME_DIR"

# PINCABOS_SCOREVIEW_ROUTER_V2
# La boucle V1 interrogeait xrandr + 2x wmctrl toutes les 0,5 s PENDANT le jeu
# et re-deplacait la fenetre a chaque tour des que la geometrie differait — or
# la table peut imposer une hauteur differente de l'ecran (1200 vs 1080), donc
# le combat ne cessait jamais. Cout constate : ~10 fps perdus a 60 comme a
# 144 Hz, FullDMD clignotant, Xorg a 80 % CPU.
# V2 : xrandr UNE fois par partie, placement UNE fois par fenetre (cle = id de
# fenetre), comparaison sur la position seule, cadence 3 s.
# V2.1 (PINCABOS_ROUTER_RERAISE_V21) : re-empilement periodique — insuffisant.
# V2.2 (PINCABOS_ROUTER_STACK_V22) : lecture de _NET_CLIENT_LIST_STACKING pour
# ne reagir que si le Score View est enterre — bonne detection, mais TOUTES
# les primitives d'empilement echouent : la fenetre DMD de VPinFE est
# _NET_WM_STATE_FULLSCREEN (couche superieure du WM) et le WM refuse les
# requetes de restack a travers les couches, dans les deux sens.
# V2.3 (PINCABOS_ROUTER_CURTAIN_V23) : on ne negocie plus avec le WM — quand
# le Score View est enterre sous le rideau noir fullscreen de VPinFE, on
# DEMAPPE le rideau (xdotool windowunmap, valide sur cab : effet instantane),
# et on le remappe des que la partie se termine pour rendre son DMD au menu.
# L'issue de la course au lancement de table (qui de VPinFE ou de VPX empile
# sa fenetre en dernier) ne decide plus rien.

choose_authority() {
    for candidate in /home/pinball/.Xauthority /run/lightdm/root/:0; do
        [[ -r "$candidate" ]] && { printf '%s\n' "$candidate"; return 0; }
    done
    return 1
}

AUTHORITY="$(choose_authority || true)"
[[ -n "$AUTHORITY" ]] || exit 1

run_x() {
    runuser -u pinball -- env HOME=/home/pinball DISPLAY=:0 XAUTHORITY="$AUTHORITY" XDG_RUNTIME_DIR=/run/user/1000 "$@"
}

routed_window=""
geometry=""
curtain=""
game_seen=0

# PINCABOS_ROUTER_FOCUS_V24
# Rendre le clavier au playfield : sans cela, la derniere fenetre mappee (le
# rideau DMD, sur l'ecran secondaire) garde le focus et le menu reste sourd.
focus_playfield() {
    local listing target
    listing="$(run_x wmctrl -lGx 2>/dev/null)" || return 0
    target="$(awk '/VPinFE Table$/ {print $1;exit}' <<< "$listing")"
    if [[ -z "$target" ]]; then
        target="$(awk '/VPinFE/ && !/VPinFE DMD$/ && !/VPinFE Backglass$/ {print $1;exit}' <<< "$listing")"
    fi
    [[ -n "$target" ]] || return 0
    run_x xdotool windowactivate "$target" >/dev/null 2>&1 \
        || run_x wmctrl -ia "$target" >/dev/null 2>&1 || true
}

restore_curtain() {
    if [[ -n "$curtain" ]]; then
        run_x xdotool windowmap "$curtain" >/dev/null 2>&1 || true
        curtain=""
    fi
}
trap restore_curtain EXIT TERM INT

sink_curtain_if_buried() {
    # $1 = fenetre Score View, $2 = listing wmctrl -lGx courant
    local win="$1" listing="$2" rival stacking w_dec r_dec pos_w pos_r i tok dec
    rival="$(awk '/VPinFE DMD$/ {print $1;exit}' <<< "$listing")"
    [[ -n "$rival" ]] || return 0
    stacking="$(run_x xprop -root -notype _NET_CLIENT_LIST_STACKING 2>/dev/null)"
    [[ -n "$stacking" ]] || return 0
    w_dec="$(printf '%d' "$win" 2>/dev/null)" || return 0
    r_dec="$(printf '%d' "$rival" 2>/dev/null)" || return 0
    pos_w=-1; pos_r=-1; i=0
    for tok in ${stacking#*\#}; do
        dec="$(printf '%d' "${tok%,}" 2>/dev/null)" || { i=$((i + 1)); continue; }
        [[ "$dec" = "$w_dec" ]] && pos_w=$i
        [[ "$dec" = "$r_dec" ]] && pos_r=$i
        i=$((i + 1))
    done
    # ordre bas -> haut : rival plus haut que nous = Score View enterre
    if [[ "$pos_w" -ge 0 && "$pos_r" -gt "$pos_w" ]]; then
        if run_x xdotool windowunmap "$rival" >/dev/null 2>&1; then
            curtain="$rival"
        fi
    fi
}

while true; do
    if ! pgrep -u pinball -f 'VPinballX' >/dev/null 2>&1; then
        rm -f "$RUNTIME_DIR/command.env" "$RUNTIME_DIR/state.env"
        routed_window=""
        geometry=""
        restore_curtain
        if [[ "$game_seen" = "1" ]]; then
            focus_playfield
            game_seen=0
        fi
        sleep 2
        continue
    fi

    game_seen=1

    if [[ -z "$geometry" ]]; then
        geometry="$(run_x xrandr --query 2>/dev/null | awk '$1=="DP-2" && $2=="connected" {for(i=3;i<=NF;i++) if($i~/^[0-9]+x[0-9]+\+[0-9]+\+[0-9]+/){print $i;exit}}')"
        [[ -n "$geometry" ]] || { sleep 3; continue; }
    fi
    read -r width height pos_x pos_y < <(sed -E 's/^([0-9]+)x([0-9]+)\+([0-9]+)\+([0-9]+).*$/\1 \2 \3 \4/' <<< "$geometry")

    listing="$(run_x wmctrl -lGx 2>/dev/null)"
    window="$(awk '/Visual Pinball Score View$/ {print $1;exit}' <<< "$listing")"
    [[ -n "$window" ]] || { sleep 1; continue; }

    if [[ "$window" != "$routed_window" ]]; then
        current_pos="$(awk -v id="$window" '$1==id{print $3","$4;exit}' <<< "$listing")"
        if [[ "$current_pos" != "${pos_x},${pos_y}" ]]; then
            run_x wmctrl -ir "$window" -b remove,maximized_vert,maximized_horz,fullscreen >/dev/null 2>&1 || true
            run_x wmctrl -ir "$window" -e "0,${pos_x},${pos_y},${width},${height}" >/dev/null 2>&1 || true
        fi
        run_x wmctrl -ir "$window" -b add,above >/dev/null 2>&1 || true
        routed_window="$window"
    fi
    sink_curtain_if_buried "$window" "$listing"
    sleep 3
done
