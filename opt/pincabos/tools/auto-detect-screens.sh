#!/bin/bash
# PinCabOS-File created by Karots Sugarpie
set -Eeuo pipefail

LOG_DIR="/opt/pincabos/logs/screens"
CFG_DIR="/opt/pincabos/config/screens"
STATE_DIR="/opt/pincabos/state"
TS="$(date +%Y%m%d-%H%M%S)"
LOG="${LOG_DIR}/auto-detect-screens-${TS}.log"

mkdir -p "$LOG_DIR" "$CFG_DIR" "$STATE_DIR"

exec > >(tee -a "$LOG") 2>&1

echo "=================================================="
echo " PinCabOS - Écrans apply-all X11 / VPX / VPinFE"
echo " Log: $LOG"
echo " Début: $(date)"
echo "=================================================="
echo

runuser -u pinball -- bash --noprofile --norc -lc '
set -Eeuo pipefail

export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-/home/pinball/.Xauthority}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/1000}"

CFG_DIR="/opt/pincabos/config/screens"
mkdir -p "$CFG_DIR"

echo "=== 1) xrandr avant ==="
XRANDR_RAW="$(xrandr --query 2>/dev/null || true)"
echo "$XRANDR_RAW"

python3 <<PY
from pathlib import Path
from datetime import datetime
import json
import os
import re
import subprocess
import shlex

cfg_dir = Path("/opt/pincabos/config/screens")
cfg_dir.mkdir(parents=True, exist_ok=True)

raw = subprocess.run(
    ["xrandr", "--query"],
    capture_output=True,
    text=True,
    env={
        **os.environ,
        "DISPLAY": os.environ.get("DISPLAY", ":0"),
        "XAUTHORITY": os.environ.get("XAUTHORITY", "/home/pinball/.Xauthority"),
        "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000"),
    },
).stdout

screens = []
for line in raw.splitlines():
    if " connected" not in line:
        continue

    name = line.split()[0]
    if " disconnected" in line:
        continue

    m = re.search(r"(\\d+)x(\\d+)\\+(\\-?\\d+)\\+(\\-?\\d+)", line)
    if not m:
        # fallback: first available mode from following lines is hard to know here,
        # so skip outputs without active geometry
        continue

    width = int(m.group(1))
    height = int(m.group(2))
    old_x = int(m.group(3))
    old_y = int(m.group(4))

    screens.append({
        "name": name,
        "output": name,
        "width": width,
        "height": height,
        "old_x": old_x,
        "old_y": old_y,
        "area": width * height,
        "raw": line,
    })

if not screens:
    raise SystemExit("ERREUR: aucun écran connecté détecté par xrandr.")

# Règle PinCabOS simple:
# - Playfield = plus grand écran.
# - Backglass = deuxième plus grand.
# - DMD/FullDMD = troisième plus grand.
# - Tout aligné top y=0, à droite du playfield.
ordered = sorted(screens, key=lambda s: s["area"], reverse=True)

x = 0
roles = []
for idx, s in enumerate(ordered):
    role = "playfield" if idx == 0 else "backglass" if idx == 1 else "fulldmd" if idx == 2 else f"extra{idx}"
    item = dict(s)
    item.update({
        "id": idx,
        "role": role,
        "x": x,
        "y": 0,
        "is_primary": idx == 0,
        "position": f"{x}x0",
        "geometry": f"{s['width']}x{s['height']}+{x}+0",
    })
    roles.append(item)
    x += s["width"]

playfield = roles[0]
backglass = roles[1] if len(roles) >= 2 else None
fulldmd = roles[2] if len(roles) >= 3 else None

cmd = ["xrandr"]
for item in roles:
    cmd += [
        "--output", item["output"],
        "--mode", f"{item['width']}x{item['height']}",
        "--pos", f"{item['x']}x0",
    ]
    if item["is_primary"]:
        cmd += ["--primary"]

print()
print("=== 2) Commande X11 appliquée ===")
print(" ".join(shlex.quote(x) for x in cmd))
subprocess.run(cmd, check=True)

after = subprocess.run(["xrandr", "--query"], capture_output=True, text=True).stdout

layout = {
    "mode": "firstrun_auto_apply_all",
    "updated_at": datetime.now().isoformat(timespec="seconds"),
    "playfield": playfield,
    "backglass": backglass,
    "fulldmd": fulldmd,
    "all_screens": roles,
    "xrandr_command": cmd,
    "xrandr_raw_before": raw,
    "xrandr_raw": after,
}

(cfg_dir / "screens.json").write_text(json.dumps(layout, indent=2, ensure_ascii=False) + "\\n", encoding="utf-8")

detected = {
    "screens": [
        {
            "id": s["id"],
            "name": "Playfield" if s["role"] == "playfield" else "Backglass" if s["role"] == "backglass" else "DMD" if s["role"] == "fulldmd" else s["role"],
            "output": s["output"],
            "mode": f"{s['width']}x{s['height']}",
            "width": s["width"],
            "height": s["height"],
            "area": s["area"],
            "position": s["position"],
            "primary": s["is_primary"],
        }
        for s in roles[:3]
    ]
}
(cfg_dir / "screens-detected.json").write_text(json.dumps(detected, indent=2, ensure_ascii=False) + "\\n", encoding="utf-8")

env_lines = ["# PinCabOS official screen aliases", ""]
def add_env(prefix, label, item):
    if not item:
        return
    env_lines.extend([
        f"PCO_{prefix}_NAME=\\"{label}\\"",
        f"PCO_{prefix}_ID=\\"{item['id']}\\"",
        f"PCO_{prefix}_OUTPUT=\\"{item['output']}\\"",
        f"PCO_{prefix}_MODE=\\"{item['width']}x{item['height']}\\"",
        f"PCO_{prefix}_POS=\\"{item['position']}\\"",
        f"PCO_{prefix}_GEOMETRY=\\"{item['geometry']}\\"",
        "",
    ])

add_env("PLAYFIELD", "Playfield", playfield)
add_env("BACKGLASS", "Backglass", backglass)
add_env("DMD", "DMD", fulldmd)
(cfg_dir / "screens.env").write_text("\\n".join(env_lines), encoding="utf-8")

(cfg_dir / "layout.conf").write_text(
    "\\n".join([
        "# PinCabOS X11 layout",
        f"PLAYFIELD={playfield['output']}:{playfield['geometry']}",
        f"BACKGLASS={backglass['output']}:{backglass['geometry']}" if backglass else "BACKGLASS=",
        f"DMD={fulldmd['output']}:{fulldmd['geometry']}" if fulldmd else "DMD=",
        "",
    ]),
    encoding="utf-8",
)

print()
print("=== 3) Assignation PinCabOS ===")
print(f"Playfield: {playfield['output']} {playfield['geometry']}")
print(f"Backglass: {backglass['output']} {backglass['geometry']}" if backglass else "Backglass: non détecté")
print(f"DMD/FullDMD: {fulldmd['output']} {fulldmd['geometry']}" if fulldmd else "DMD/FullDMD: non détecté")

print()
print("=== 4) xrandr après ===")
print(after)
PY
'

chown -R pinball:pinball "$CFG_DIR" "$STATE_DIR" 2>/dev/null || true

date -Is > "${STATE_DIR}/screens-apply-last-success.flag"
chown pinball:pinball "${STATE_DIR}/screens-apply-last-success.flag" 2>/dev/null || true

echo
echo "=== 5) Wallpapers Openbox / feh ==="

runuser -u pinball -- bash --noprofile --norc -lc '
set -Eeuo pipefail

export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-/home/pinball/.Xauthority}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/1000}"

WALL_DIR="/opt/pincabos/media/wallpapers"
PF_WALL="${WALL_DIR}/PCOSPFWall.png"
BG_WALL="${WALL_DIR}/PCOSBGWall.png"
DMD_WALL="${WALL_DIR}/PCOSDMDWall.png"
CFG_DIR="/opt/pincabos/config/screens"
OPENBOX_DIR="/home/pinball/.config/openbox"
AUTOSTART="${OPENBOX_DIR}/autostart"

mkdir -p "$OPENBOX_DIR"

if ! command -v feh >/dev/null 2>&1; then
  echo "WARNING: feh non installé, wallpapers ignorés."
  exit 0
fi

if [ ! -f "$PF_WALL" ]; then
  echo "WARNING: wallpaper Playfield absent: $PF_WALL"
  exit 0
fi

WALL_CMD=(feh --no-fehbg)

# feh utilise l’ordre Xinerama/X11. On donne les wallpapers dans l’ordre logique PinCabOS:
# écran 0 = Playfield, écran 1 = Backglass, écran 2 = DMD/FullDMD.
WALL_CMD+=(--bg-fill "$PF_WALL")

if [ -f "$BG_WALL" ]; then
  WALL_CMD+=(--bg-fill "$BG_WALL")
fi

if [ -f "$DMD_WALL" ]; then
  WALL_CMD+=(--bg-fill "$DMD_WALL")
fi

echo "Commande wallpaper:"
printf "%q " "${WALL_CMD[@]}"
echo

"${WALL_CMD[@]}" || true

cat > /home/pinball/.fehbg-pincabos <<EOF
#!/bin/sh
export DISPLAY=:0
export XAUTHORITY=/home/pinball/.Xauthority
${WALL_CMD[*]}
EOF

chmod +x /home/pinball/.fehbg-pincabos

if [ -f "$AUTOSTART" ]; then
  cp -a "$AUTOSTART" "${AUTOSTART}.backup-wallpapers-$(date +%Y%m%d-%H%M%S)"
fi

grep -v "fehbg-pincabos" "$AUTOSTART" 2>/dev/null > "${AUTOSTART}.tmp" || true
cat "${AUTOSTART}.tmp" > "$AUTOSTART"
rm -f "${AUTOSTART}.tmp"

cat >> "$AUTOSTART" <<EOF

# PinCabOS wallpapers per screen
/home/pinball/.fehbg-pincabos &
EOF

echo "OK: wallpapers appliqués et autostart Openbox mis à jour."
'

echo
echo "=================================================="
echo " Écrans appliqués."
echo " Playfield = 0x0."
echo " Backglass/DMD = à droite, alignés top y=0."
echo " Wallpapers appliqués:"
echo "  Playfield: /opt/pincabos/media/wallpapers/PCOSPFWall.png"
echo "  Backglass: /opt/pincabos/media/wallpapers/PCOSBGWall.png"
echo "  DMD:       /opt/pincabos/media/wallpapers/PCOSDMDWall.png"
echo " Aucun reboot requis par xrandr."
echo " Fin: $(date)"
echo "=================================================="
