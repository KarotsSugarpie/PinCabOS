#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-query}"
CFG="/opt/pincabos/config/screens/screens.json"

find_env_and_run() {
  local action="$1"

  local displays=()
  [ -n "${DISPLAY:-}" ] && displays+=("$DISPLAY")
  displays+=(":0" ":1")

  local auths=()
  [ -n "${XAUTHORITY:-}" ] && auths+=("$XAUTHORITY")
  auths+=(
    "/home/pinball/.Xauthority"
    "/run/user/1000/gdm/Xauthority"
    "/run/user/1000/.mutter-Xwaylandauth.*"
    "/run/lightdm/root/:0"
    "/var/run/lightdm/root/:0"
  )

  local d xa realxa
  for d in "${displays[@]}"; do
    for xa in "${auths[@]}"; do
      for realxa in $xa; do
        [ -e "$realxa" ] || continue

        if env DISPLAY="$d" XAUTHORITY="$realxa" xrandr --query >/tmp/pincabos-xrandr-test.$$ 2>/tmp/pincabos-xrandr-err.$$; then
          if [ "$action" = "query" ]; then
            cat /tmp/pincabos-xrandr-test.$$
            rm -f /tmp/pincabos-xrandr-test.$$ /tmp/pincabos-xrandr-err.$$
            return 0
          fi

          if [ "$action" = "apply" ]; then
            env DISPLAY="$d" XAUTHORITY="$realxa" python3 - "$CFG" <<'PY'
import json, re, subprocess, sys
from pathlib import Path

cfg_path = Path(sys.argv[1])
if not cfg_path.exists():
    raise SystemExit(f"NOGO: config absente: {cfg_path}")

data = json.loads(cfg_path.read_text(errors="replace") or "{}")

def clean_rate(rate):
    return str(rate or "").replace("*", "").replace("+", "").strip()

def mode_width(mode):
    m = re.match(r"^(\d+)x(\d+)$", str(mode or ""))
    return int(m.group(1)) if m else 0

def mode_height(mode):
    m = re.match(r"^(\d+)x(\d+)$", str(mode or ""))
    return int(m.group(2)) if m else 0

# PINCABOS_APPLY_ROLE_POSITIONS_V1
# La position de chaque sortie vient de la GEOMETRIE du role (objets de
# premier niveau de screens.json, la source de verite), plus jamais d'un
# ordre canonique playfield->backglass->fulldmd : cet ordre correspondait au
# cablage du cab de developpement et PERMUTAIT physiquement les ecrans de
# tout cabinet range differemment (ex. playfield->fulldmd->backglass) a
# chaque application.
def role_position(role, output):
    top = data.get(role)
    if not isinstance(top, dict):
        return ""
    name = str(top.get("output") or top.get("name") or "")
    if output and name and name != output:
        return ""
    m = re.match(r"^\d+x\d+\+(-?\d+)\+(-?\d+)$", str(top.get("geometry") or ""))
    if m:
        return f"{m.group(1)}x{m.group(2)}"
    return ""

def role_from_data(role):
    roles = data.get("roles") if isinstance(data.get("roles"), dict) else {}
    r = roles.get(role)
    if isinstance(r, dict) and (r.get("output") or r.get("name") or r.get("mode")):
        out = str(r.get("output") or r.get("name") or "")
        mode = str(r.get("mode") or "")
        rate = clean_rate(r.get("rate"))
        return {
            "output": out,
            "mode": mode,
            "rate": rate,
            "pos": role_position(role, out),
        }

    top = data.get(role)
    if isinstance(top, dict):
        out = str(top.get("output") or top.get("name") or "")
        mode = str(top.get("mode") or "")
        if not mode and top.get("width") and top.get("height"):
            mode = f"{top.get('width')}x{top.get('height')}"
        rate = clean_rate(top.get("rate"))
        return {
            "output": out,
            "mode": mode,
            "rate": rate,
            "pos": role_position(role, out),
        }

    return {"output": "", "mode": "", "rate": "", "pos": ""}

def run(cmd):
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)

pf = role_from_data("playfield")
bg = role_from_data("backglass")
fd = role_from_data("fulldmd")
# PINCABOS_APPLY_TOPPER_V1 : cabinets a 4 ecrans
tp = role_from_data("topper")

pfw = mode_width(pf.get("mode"))
bgw = mode_width(bg.get("mode"))

items = []

if pf.get("output") and pf.get("mode"):
    rot = str(data.get("playfield_rotation", "0"))
    rotate = {
        "0": "normal",
        "90": "right",
        "180": "inverted",
        "270": "left",
    }.get(rot, "normal")

    cmd = [
        "xrandr",
        "--output", pf["output"],
        "--mode", pf["mode"],
        "--pos", pf.get("pos") or "0x0",
        "--rotate", rotate,
        "--primary",
    ]
    if pf.get("rate"):
        cmd += ["--rate", pf["rate"]]
    items.append(cmd)

if bg.get("output") and bg.get("mode"):
    x = pfw
    cmd = [
        "xrandr",
        "--output", bg["output"],
        "--mode", bg["mode"],
        "--pos", bg.get("pos") or f"{x}x0",
        "--rotate", "normal",
    ]
    if bg.get("rate"):
        cmd += ["--rate", bg["rate"]]
    items.append(cmd)

if fd.get("output") and fd.get("mode"):
    x = pfw + bgw
    cmd = [
        "xrandr",
        "--output", fd["output"],
        "--mode", fd["mode"],
        "--pos", fd.get("pos") or f"{x}x0",
        "--rotate", "normal",
    ]
    if fd.get("rate"):
        cmd += ["--rate", fd["rate"]]
    items.append(cmd)

if tp.get("output") and tp.get("mode"):
    # Pas d'ordre canonique pour le topper : uniquement la geometrie de son
    # role (typiquement au-dessus du fronton, y negatif). Sans geometrie, on
    # le place a droite de tout le reste plutot que d'inventer une position.
    x = pfw + bgw + mode_width(fd.get("mode"))
    cmd = [
        "xrandr",
        "--output", tp["output"],
        "--mode", tp["mode"],
        "--pos", tp.get("pos") or f"{x}x0",
        "--rotate", "normal",
    ]
    if tp.get("rate"):
        cmd += ["--rate", tp["rate"]]
    items.append(cmd)

if not items:
    print("DEBUG data roles/top-level:")
    print(json.dumps({
        "roles": data.get("roles"),
        "playfield": data.get("playfield"),
        "backglass": data.get("backglass"),
        "fulldmd": data.get("fulldmd"),
    }, indent=2, ensure_ascii=False))
    raise SystemExit("NOGO: aucune sortie/résolution à appliquer")

for cmd in items:
    run(cmd)

# PINCABOS_LAYOUT_NO_OVERLAP_V2
# Les positions ci-dessus derivent de la largeur du MODE configure. Un role
# laisse sur "Auto / inchange" donne une largeur nulle, et l'ecran suivant se
# retrouve pose sur le precedent : X accepte sans broncher deux zones qui se
# recouvrent, l'affichage devient incoherent, et rien ne le signale.
# On relit donc les largeurs REELLEMENT appliquees et on recale de gauche a
# droite — dans l'ordre des POSITIONS APPLIQUEES. La V1 recalait dans
# l'ordre canonique playfield->backglass->fulldmd : sur un cabinet range
# autrement (ex. playfield->fulldmd->backglass), elle PERMUTAIT physiquement
# les deux ecrans de fronton juste apres qu'ils aient ete poses au bon
# endroit.
import subprocess as _sp

_geo = {}
try:
    _brut = _sp.run(["xrandr", "--query"], text=True, capture_output=True).stdout
except Exception:
    _brut = ""
for _ligne in _brut.splitlines():
    _m = re.match(r"^(\S+) connected.*?(\d+)x(\d+)\+(-?\d+)\+(-?\d+)", _ligne)
    if _m:
        _geo[_m.group(1)] = (int(_m.group(2)), int(_m.group(4)), int(_m.group(5)))

# seuls les ecrans de la rangee principale (y=0) sont recales : un topper
# au-dessus du fronton (y negatif) garde sa position de role.
_ordre = sorted(
    [
        r.get("output")
        for r in (pf, bg, fd, tp)
        if r.get("output") and r.get("output") in _geo and _geo[r.get("output")][2] == 0
    ],
    key=lambda s: _geo[s][1],
)

_x = 0
_recale = []
for _sortie in _ordre:
    _largeur, _pos, _y = _geo[_sortie]
    if _pos != _x:
        _recale += ["--output", _sortie, "--pos", f"{_x}x0"]
    _x += _largeur

if _recale:
    run(["xrandr"] + _recale)
    print(f"GO: positions recalees ({len(_recale)//4} ecran(s)) — chevauchement evite")

print("GO: xrandr layout appliqué")
PY

            # La topologie doit revoir le monde APRES un changement de
            # layout : un repositionnement xrandr n'emet aucun evenement drm
            # (le hotplug ne le voit pas) et, sans resynchronisation,
            # screens.json / display-aliases gardent les anciennes geometries
            # — le placement des fenetres de jeu part alors au mauvais ecran
            # jusqu'au prochain redemarrage.
            if [ -x /usr/local/libexec/pincabos/pincabos-screen-topology-preflight.sh ]; then
              flock -w 15 /run/pincabos-screen-topology.lock \
                /usr/local/libexec/pincabos/pincabos-screen-topology-preflight.sh \
                >/dev/null 2>&1 || true
            fi
            return 0
          fi
        fi
      done
    done
  done

  echo "NOGO: impossible d'accéder à xrandr avec DISPLAY/XAUTHORITY connus" >&2
  [ -f /tmp/pincabos-xrandr-err.$$ ] && cat /tmp/pincabos-xrandr-err.$$ >&2 || true
  rm -f /tmp/pincabos-xrandr-test.$$ /tmp/pincabos-xrandr-err.$$
  return 1
}

case "$ACTION" in
  query) find_env_and_run query ;;
  apply) find_env_and_run apply ;;
  *) echo "Usage: $0 query|apply" >&2; exit 2 ;;
esac
