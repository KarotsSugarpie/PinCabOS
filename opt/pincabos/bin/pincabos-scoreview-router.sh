#!/usr/bin/env bash
set -u

RUNTIME_DIR="/run/pincabos-b2s-dmd-tuner"
mkdir -p "$RUNTIME_DIR"
chown pinball:pinball "$RUNTIME_DIR"
chmod 0770 "$RUNTIME_DIR"

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

while true; do
    if ! pgrep -u pinball -f 'VPinballX' >/dev/null 2>&1; then
        rm -f "$RUNTIME_DIR/command.env" "$RUNTIME_DIR/state.env"
        sleep 0.5
        continue
    fi

    geometry="$(run_x xrandr --query 2>/dev/null | awk '$1=="DP-2" && $2=="connected" {for(i=3;i<=NF;i++) if($i~/^[0-9]+x[0-9]+\+[0-9]+\+[0-9]+/){print $i;exit}}')"
    [[ -n "$geometry" ]] || { sleep 0.5; continue; }
    read -r width height pos_x pos_y < <(sed -E 's/^([0-9]+)x([0-9]+)\+([0-9]+)\+([0-9]+).*$/\1 \2 \3 \4/' <<< "$geometry")

    window="$(run_x wmctrl -lGx 2>/dev/null | awk '/Visual Pinball Score View$/ {print $1;exit}')"
    [[ -n "$window" ]] || { sleep 0.25; continue; }
    current="$(run_x wmctrl -lGx 2>/dev/null | awk -v id="$window" '$1==id{print $3","$4","$5","$6;exit}')"
    wanted="${pos_x},${pos_y},${width},${height}"

    if [[ "$current" != "$wanted" ]]; then
        run_x wmctrl -ir "$window" -b remove,maximized_vert,maximized_horz,fullscreen >/dev/null 2>&1 || true
        run_x wmctrl -ir "$window" -e "0,${pos_x},${pos_y},${width},${height}" >/dev/null 2>&1 || true
        run_x wmctrl -ir "$window" -b add,above >/dev/null 2>&1 || true
    fi
    sleep 0.5
done
