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
        }

    return {"output": "", "mode": "", "rate": ""}

def run(cmd):
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)

pf = role_from_data("playfield")
bg = role_from_data("backglass")
fd = role_from_data("fulldmd")

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
        "--pos", "0x0",
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
        "--pos", f"{x}x0",
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
        "--pos", f"{x}x0",
        "--rotate", "normal",
    ]
    if fd.get("rate"):
        cmd += ["--rate", fd["rate"]]
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

print("GO: xrandr layout appliqué")
PY
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
