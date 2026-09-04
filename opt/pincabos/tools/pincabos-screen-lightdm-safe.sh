#!/usr/bin/env bash
# PINCABOS_SCREEN_LIGHTDM_SAFE_V2
# Ne retourne jamais une erreur fatale a LightDM.
# PINCABOS_ROTATION_PHYSIQUE_V1 : la rotation de chaque role (screens.json)
# est appliquee ici a chaque demarrage de session. Avant, ce script forcait
# « normal » sur toutes les sorties et la rotation etait perdue au boot.

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
[ -n "${AUTH:-}" ] && [ -r "$AUTH" ] || exit 0

export DISPLAY=:0
export XAUTHORITY="$AUTH"

xrandr --query >"$TMP" 2>&1 || exit 0

if [ -r "$CFG" ]; then
python3 - "$CFG" >"$ITEMS" <<'PY'
import json, sys
sys.path.insert(0, "/opt/pincabos/tools")
try:
    import pincabos_screen_rotation as rotation_pf
    with open(sys.argv[1], encoding="utf-8") as f:
        data = json.load(f)
    prefs = data.get("roles") if isinstance(data.get("roles"), dict) else {}
    for role in ("playfield", "backglass", "fulldmd", "topper"):
        s = data.get(role) or {}
        if all(k in s for k in ("name", "width", "height", "x", "y")):
            pref = prefs.get(role) if isinstance(prefs.get(role), dict) else {}
            rot = rotation_pf.role_rotation(role, data)
            # colonnes : sortie, largeur, hauteur, x, y, primaire, rate,
            # mot-cle xrandr de rotation, mode inverse a essayer (90/270)
            candidats = rotation_pf.modes_candidats(f'{s["width"]}x{s["height"]}', rot)
            print("\t".join(map(str, [
                s["name"], s["width"], s["height"],
                s["x"], s["y"], int(bool(s.get("is_primary"))),
                str(pref.get("rate") or ""),
                rotation_pf.xrandr_rotate(rot),
                candidats[1] if len(candidats) > 1 else "",
            ])))
except Exception:
    pass
PY
else
# premier boot : pas de configuration -> layout par defaut deterministe.
# Le plus grand ecran (prefere) devient primaire en 0+0, les autres s etendent
# a droite. Evite le mode clone/empilement du serveur X sur machine vierge.
python3 - "$TMP" >"$ITEMS" <<'PY'
import re, sys
text = open(sys.argv[1], encoding="utf-8", errors="replace").read()
outs = []
current = None
for line in text.splitlines():
    m = re.match(r"^(\S+) connected( primary)?", line)
    if m:
        current = {"name": m.group(1), "primary": bool(m.group(2)), "w": 0, "h": 0}
        outs.append(current)
        continue
    if current is not None:
        mm = re.match(r"^\s+(\d+)x(\d+)", line)
        if mm and current["w"] == 0:
            current["w"], current["h"] = int(mm.group(1)), int(mm.group(2))
outs = [o for o in outs if o["w"]]
outs.sort(key=lambda o: (not o["primary"], -(o["w"] * o["h"]), o["name"]))
x = 0
for i, o in enumerate(outs):
    print("\t".join(map(str, [o["name"], o["w"], o["h"], x, 0, 1 if i == 0 else 0])))
    x += o["w"]
PY
fi

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

while IFS=$'\t' read -r OUT W H X Y PRIMARY RATE_CFG ROTATE MODE_ALT; do
  [ -n "${OUT:-}" ] || continue
  is_connected "$OUT" || continue

  MODE="${W}x${H}"
  ARGS=(--output "$OUT")
  ROTATE="${ROTATE:-normal}"
  # geometrie memorisee tournee (90/270) : le mode de la dalle est l'inverse
  if ! has_mode "$OUT" "$MODE" && [ -n "${MODE_ALT:-}" ] && has_mode "$OUT" "$MODE_ALT"; then
    MODE="$MODE_ALT"
  fi

  if has_mode "$OUT" "$MODE"; then
    ARGS+=(--mode "$MODE")
    # PINCABOS_RATE_MAX_V1 : sans --rate, X retombe sur le refresh
    # "preferred" de l'EDID (souvent 60 Hz) ; on prend le max du mode.
    if [ -n "${RATE_CFG:-}" ]; then
      RATE="$RATE_CFG"
    else
    RATE=$(awk -v out="$OUT" -v mode="$MODE" '
      $1 == out && $2 == "connected" { active=1; next }
      active && $2 ~ /^(connected|disconnected)$/ { active=0 }
      active && $1 == mode {
        for (i = 2; i <= NF; i++) { v = $i; gsub(/[*+]/, "", v); if (v + 0 > best) best = v + 0 }
      }
      END { if (best > 0) printf "%.2f", best }
    ' "$TMP")
    fi
    if [ -n "$RATE" ]; then
      ARGS+=(--rate "$RATE")
    fi
  else
    ARGS+=(--auto)
    echo "WARN : $OUT ne fournit plus $MODE; mode natif conserve."
  fi

  ARGS+=(--pos "${X}x${Y}" --rotate "$ROTATE")
  [ "$PRIMARY" = "1" ] && ARGS+=(--primary)

  xrandr "${ARGS[@]}" || true
done <"$ITEMS"

exit 0
