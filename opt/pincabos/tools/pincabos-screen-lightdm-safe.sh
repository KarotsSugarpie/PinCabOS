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
