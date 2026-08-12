#!/usr/bin/env bash
# PinCabOS-File created by Karots Sugarpie
set -euo pipefail

FULL_JSON="/opt/pincabos/config/fulldmd-calibration.json"
DMD_JSON="/opt/pincabos/config/dmd-calibration.json"
VPINFE_INI="/home/pinball/.config/vpinfe/vpinfe.ini"
VPX_INI="/home/pinball/.local/share/VPinballX/10.8/VPinballX.ini"

mkdir -p "$(dirname "$VPINFE_INI")" "$(dirname "$VPX_INI")"

python3 - <<'PY'
import json
from pathlib import Path
from datetime import datetime, timezone

full_json = Path("/opt/pincabos/config/fulldmd-calibration.json")
dmd_json = Path("/opt/pincabos/config/dmd-calibration.json")
vpinfe_ini = Path("/home/pinball/.config/vpinfe/vpinfe.ini")
vpx_ini = Path("/home/pinball/.local/share/VPinballX/10.8/VPinballX.ini")

def load_cal(path, defaults):
    try:
        d = json.loads(path.read_text(errors="replace"))
    except Exception:
        d = {}
    out = {}
    for k, v in defaults.items():
        out[k] = int(d.get(k, v)) if k in ("screen_id", "x", "y", "width", "height") else d.get(k, v)
    out["geometry"] = f'{out["width"]}x{out["height"]}+{out["x"]}+{out["y"]}'
    return out

full = load_cal(full_json, {"screen_id": 2, "x": 80, "y": 160, "width": 1100, "height": 520})
dmd = load_cal(dmd_json, {"screen_id": 2, "x": 80, "y": 40, "width": 512, "height": 128})

updated_at = datetime.now(timezone.utc).isoformat()

def read_lines(path):
    if path.exists():
        return path.read_text(errors="replace").splitlines()
    return []

def set_ini_key(lines, section, key, value):
    section_header = f"[{section}]"
    out = []
    in_section = False
    section_found = False
    key_done = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("[") and stripped.endswith("]"):
            if in_section and not key_done:
                out.append(f"{key} = {value}")
                key_done = True
            in_section = stripped == section_header
            if in_section:
                section_found = True
            out.append(line)
            continue

        if in_section and "=" in stripped:
            left = stripped.split("=", 1)[0].strip().lower()
            if left == key.lower():
                if not key_done:
                    out.append(f"{key} = {value}")
                    key_done = True
                continue

        out.append(line)

    if section_found and in_section and not key_done:
        out.append(f"{key} = {value}")
        key_done = True

    if not section_found:
        if out and out[-1].strip():
            out.append("")
        out.append(section_header)
        out.append(f"{key} = {value}")

    return out

def apply_cal(lines, section, prefix, cal):
    for key, value in [
        ("enabled", "1"),
        ("screen_id", cal["screen_id"]),
        ("x", cal["x"]),
        ("y", cal["y"]),
        ("width", cal["width"]),
        ("height", cal["height"]),
        ("geometry", cal["geometry"]),
        ("updated_at", updated_at),
    ]:
        lines = set_ini_key(lines, section, key, value)

    # Section globale PinCabOS.Screens
    for key, value in [
        (f"{prefix}_id", cal["screen_id"]),
        (f"{prefix}_x", cal["x"]),
        (f"{prefix}_y", cal["y"]),
        (f"{prefix}_width", cal["width"]),
        (f"{prefix}_height", cal["height"]),
        (f"{prefix}_geometry", cal["geometry"]),
    ]:
        lines = set_ini_key(lines, "PinCabOS.Screens", key, value)

    return lines

def apply_ini(path):
    lines = read_lines(path)

    lines = apply_cal(lines, "PinCabOS.FullDMD", "fulldmd", full)
    lines = apply_cal(lines, "PinCabOS.DMD", "dmd", dmd)

    # Section Displays compatible PinCabOS/VPX/VPinFE
    for key, value in [
        ("fulldmdscreenid", full["screen_id"]),
        ("fulldmdx", full["x"]),
        ("fulldmdy", full["y"]),
        ("fulldmdwidth", full["width"]),
        ("fulldmdheight", full["height"]),
        ("dmdscreenid", dmd["screen_id"]),
        ("dmdx", dmd["x"]),
        ("dmdy", dmd["y"]),
        ("dmdwidth", dmd["width"]),
        ("dmdheight", dmd["height"]),
    ]:
        lines = set_ini_key(lines, "Displays", key, value)

    path.write_text("\n".join(lines).rstrip() + "\n")

apply_ini(vpinfe_ini)
apply_ini(vpx_ini)

print("OK sync FullDMD + DMD")
print(f"VPinFE={vpinfe_ini}")
print(f"VPX={vpx_ini}")
print(f"FullDMD={full}")
print(f"DMD={dmd}")
PY

chown pinball:pinball "$VPX_INI" 2>/dev/null || true
chmod 600 "$VPINFE_INI" "$VPX_INI" 2>/dev/null || true
