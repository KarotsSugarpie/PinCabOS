#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCREENS = Path("/opt/pincabos/config/screens/screens.json")
ALIASES = Path("/opt/pincabos/config/display-aliases.env")
VPINFE = Path("/home/pinball/.config/vpinfe/vpinfe.ini")
VPX = Path("/home/pinball/.local/share/VPinballX/10.8/VPinballX.ini")
PENDING = Path("/run/pincabos-display-role-finalizer-vpinfe.pending")

def log(msg):
    print(f"pincabos-display-role-finalizer: {msg}", flush=True)

def atomic_write(path, content):
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old == content:
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    stat = path.stat() if path.exists() else None
    fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        if stat:
            os.chmod(temp, stat.st_mode & 0o777)
            try:
                os.chown(temp, stat.st_uid, stat.st_gid)
            except PermissionError:
                pass
        os.replace(temp, path)
    finally:
        try:
            os.unlink(temp)
        except FileNotFoundError:
            pass
    return True

def update_section(text, section, pairs):
    header = re.compile(rf"(?mi)^[ \t]*\[{re.escape(section)}\][ \t]*$")
    hit = header.search(text)
    if not hit:
        raise RuntimeError(f"section absente : [{section}]")

    start = hit.end()
    next_header = re.search(r"(?m)^[ \t]*\[.+?\][ \t]*$", text[start:])
    end = start + next_header.start() if next_header else len(text)
    block = text[start:end]

    for key, value in pairs.items():
        key_re = re.compile(rf"(?mi)^([ \t]*{re.escape(key)}[ \t]*=[ \t]*).*$")
        block, count = key_re.subn(lambda m: m.group(1) + str(value), block)
        if count == 0:
            if not block.endswith("\n"):
                block += "\n"
            block += f"{key} = {value}\n"

    return text[:start] + block + text[end:]

def update_global_key(text, key, value):
    key_re = re.compile(rf"(?mi)^([ \t]*{re.escape(key)}[ \t]*=[ \t]*).*$")
    result, count = key_re.subn(lambda m: m.group(1) + str(value), text)
    if count == 0:
        raise RuntimeError(f"clé VPX absente : {key}")
    return result

def is_vpx_running():
    return subprocess.run(
        ["pgrep", "-u", "pinball", "-f", r"VPinballX(_BGFX)?"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode == 0

def try_restart(unit):
    result = subprocess.run(
        ["systemctl", "try-restart", unit],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        log(f"relancé : {unit}")
    else:
        log(f"non relancé : {unit}")

def main():
    if not SCREENS.exists():
        raise RuntimeError(f"source absente : {SCREENS}")

    data = json.loads(SCREENS.read_text(encoding="utf-8"))
    all_screens = data.get("all_screens", [])
    if not isinstance(all_screens, list) or len(all_screens) < 3:
        raise RuntimeError("moins de trois écrans actifs dans screens.json")

    # ID applicatif = ordre physique X11, jamais l'ordre instable de listmonitors.
    physical = sorted(
        all_screens,
        key=lambda item: (
            int(item.get("x", 999999)),
            int(item.get("y", 999999)),
            str(item.get("name", "")),
        ),
    )
    ids = {str(item["name"]): index for index, item in enumerate(physical)}

    roles = {}
    for role in ("playfield", "backglass", "fulldmd"):
        item = data.get(role)
        if not isinstance(item, dict):
            raise RuntimeError(f"rôle absent : {role}")

        output = str(item.get("name", "")).strip()
        if output not in ids:
            raise RuntimeError(f"sortie introuvable : {role}={output}")

        width = int(item.get("width", 0))
        height = int(item.get("height", 0))
        x = int(item.get("x", 0))
        y = int(item.get("y", 0))
        if width <= 0 or height <= 0:
            raise RuntimeError(f"géométrie invalide : {role}")

        roles[role] = {
            "output": output,
            "id": ids[output],
            "geometry": f"{width}x{height}+{x}+{y}",
        }

    pf = roles["playfield"]
    bg = roles["backglass"]
    fd = roles["fulldmd"]

    if (pf["id"], bg["id"], fd["id"]) != (0, 1, 2):
        raise RuntimeError(
            "topologie inattendue : "
            f"PF={pf['id']} BG={bg['id']} FullDMD={fd['id']}"
        )

    aliases = (
        "# Généré automatiquement par PinCabOS.\n"
        "# Source : screens.json | IDs : ordre physique gauche→droite.\n"
        "# Ne pas modifier ce fichier manuellement.\n\n"
        f"PINCABOS_PLAYFIELD_OUTPUT='{pf['output']}'\n"
        f"PINCABOS_BACKGLASS_OUTPUT='{bg['output']}'\n"
        f"PINCABOS_FULLDMD_OUTPUT='{fd['output']}'\n"
        f"PINCABOS_PLAYFIELD_SCREEN_ID='{pf['id']}'\n"
        f"PINCABOS_BACKGLASS_SCREEN_ID='{bg['id']}'\n"
        f"PINCABOS_FULLDMD_SCREEN_ID='{fd['id']}'\n"
        f"PINCABOS_PLAYFIELD_GEOMETRY='{pf['geometry']}'\n"
        f"PINCABOS_BACKGLASS_GEOMETRY='{bg['geometry']}'\n"
        f"PINCABOS_FULLDMD_GEOMETRY='{fd['geometry']}'\n"
    )

    changed = atomic_write(ALIASES, aliases)

    vpinfe = VPINFE.read_text(encoding="utf-8")
    vpinfe = update_section(vpinfe, "Displays", {
        "tablescreenid": pf["id"],
        "bgscreenid": bg["id"],
        "dmdscreenid": fd["id"],
        "fulldmdscreenid": fd["id"],
    })
    vpinfe = update_section(vpinfe, "PinCabOs.FullDMD", {
        "screen_id": fd["id"],
    })
    vpinfe = update_section(vpinfe, "PinCabOs.Screens", {
        "fulldmd_id": fd["id"],
        "dmd_id": fd["id"],
    })
    vpinfe = update_section(vpinfe, "PinCabOs.DMD", {
        "screen_id": fd["id"],
    })
    changed = atomic_write(VPINFE, vpinfe) or changed

    vpx = VPX.read_text(encoding="utf-8")
    vpx = update_global_key(vpx, "tablescreenid", pf["id"])
    vpx = update_global_key(vpx, "bgscreenid", bg["id"])
    vpx = update_global_key(vpx, "dmdscreenid", fd["id"])
    vpx = update_global_key(vpx, "fulldmdscreenid", fd["id"])
    changed = atomic_write(VPX, vpx) or changed

    log(
        f"publié : PF={pf['output']}#{pf['id']} | "
        f"BG={bg['output']}#{bg['id']} | "
        f"FullDMD={fd['output']}#{fd['id']}"
    )

    if changed:
        try_restart("pincabos-dashboard-live.service")
        try_restart("pincabos-scoreview-router.service")

    if changed or PENDING.exists():
        if is_vpx_running():
            PENDING.touch()
            log("table VPX détectée : redémarrage VPinFE reporté automatiquement.")
        else:
            subprocess.run(
                ["systemctl", "restart", "pincabos-vpinfe.service"],
                check=False,
            )
            try:
                PENDING.unlink()
            except FileNotFoundError:
                pass
            log("VPinFE redémarré avec les rôles corrigés.")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log(f"ERREUR : {exc}")
        sys.exit(1)
