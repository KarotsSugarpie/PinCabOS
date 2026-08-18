#!/usr/bin/env bash
# PINCABOS_SCREEN_LIGHTDM_SAFE_V2
# Ne retourne jamais une erreur fatale a LightDM.

set -u
LOG="/var/log/pincabos-screen-layout.log"
CFG="/opt/pincabos/config/screens/screens.json"
TMP="$(mktemp)"
ITEMS="$(mktemp)"
trap 'rm -f "$TMP" "$ITEMS"' EXIT

exec >>"$LOG" 2>&1

get_xauth() {
  ps -eo args | sed -n 's/.*Xorg .* -auth \([^ ]*\).*/\1/p' | head -n1
}

AUTH="$(get_xauth)"
[ -r "$CFG" ] || exit 0
[ -n "${AUTH:-}" ] && [ -r "$AUTH" ] || exit 0

export DISPLAY=:0
export XAUTHORITY="$AUTH"

xrandr --query >"$TMP" 2>&1 || exit 0

# PINCABOS_PHANTOM_OUTPUT_GUARD_V1
# Une sortie annoncee « connected » mais sans EDID n'est pas un ecran : c'est
# un cable qui pend, un adaptateur seul ou un moniteur en veille profonde. Le
# pilote lui donne un mode de secours 640x480 et X la place a +0+0, donc
# par-dessus le playfield. On l'ecarte avant de composer quoi que ce soit.
drop_phantom_outputs() {
  local edid conn dropped=0
  for edid in /sys/class/drm/card*-*/edid; do
    [ -e "$edid" ] || continue
    [ -s "$edid" ] && continue
    conn="${edid%/edid}"
    conn="${conn##*/}"
    conn="${conn#card*-}"
    grep -q "^$conn connected" "$TMP" || continue
    echo "sortie sans EDID ignoree (cable sans ecran ?) : $conn"
    xrandr --output "$conn" --off 2>/dev/null || true
    dropped=1
  done
  [ "$dropped" = 1 ] && xrandr --query >"$TMP" 2>&1
  return 0
}
drop_phantom_outputs

python3 - "$CFG" >"$ITEMS" <<'PY'
import json, sys
try:
    with open(sys.argv[1], encoding="utf-8") as f:
        data = json.load(f)
    for role in ("playfield", "backglass", "fulldmd"):
        s = data.get(role) or {}
        if all(k in s for k in ("name", "width", "height", "x", "y")):
            print("\t".join(map(str, [
                s["name"], s["width"], s["height"],
                s["x"], s["y"], int(bool(s.get("is_primary")))
            ])))
except Exception:
    pass
PY

is_connected() {
  grep -q "^$1 connected" "$TMP"
}

has_mode() {
  awk -v out="$1" -v mode="$2" '
    $1 == out && $2 == "connected" { active=1; next }
    active && $2 ~ /^(connected|disconnected)$/ { active=0 }
    active && $1 == mode { found=1 }
    END { exit(found ? 0 : 1) }
  ' "$TMP"
}

while IFS=$'\t' read -r OUT W H X Y PRIMARY; do
  [ -n "${OUT:-}" ] || continue
  is_connected "$OUT" || continue

  MODE="${W}x${H}"
  ARGS=(--output "$OUT")

  if has_mode "$OUT" "$MODE"; then
    ARGS+=(--mode "$MODE")
  else
    ARGS+=(--auto)
    echo "WARN : $OUT ne fournit plus $MODE; mode natif conserve."
  fi

  ARGS+=(--pos "${X}x${Y}" --rotate normal)
  [ "$PRIMARY" = "1" ] && ARGS+=(--primary)

  xrandr "${ARGS[@]}" || true
done <"$ITEMS"

exit 0
