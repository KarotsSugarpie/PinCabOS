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
PENDING = Path("/run/pincabos-display-role-normalizer-vpinfe.pending")

def log(message):
    print(f"pincabos-display-role-normalizer: {message}", flush=True)

def atomic_write(path, content):
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old == content:
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    old_stat = path.stat() if path.exists() else None
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())

        if old_stat:
            os.chmod(tmp, old_stat.st_mode & 0o777)
            try:
                os.chown(tmp, old_stat.st_uid, old_stat.st_gid)
            except PermissionError:
                pass

        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass

    return True

def set_section(text, section, values):
    header = re.compile(rf"(?mi)^[ \t]*\[{re.escape(section)}\][ \t]*$")
    match = header.search(text)

    if not match:
        if not text.endswith("\n"):
            text += "\n"
        text += f"\n[{section}]\n"
        for key, value in values.items():
            text += f"{key} = {value}\n"
        return text

    start = match.end()
    next_header = re.search(r"(?m)^[ \t]*\[.+?\][ \t]*$", text[start:])
    end = start + next_header.start() if next_header else len(text)
    block = text[start:end]

    for key, value in values.items():
        key_re = re.compile(
            rf"(?mi)^([ \t]*{re.escape(key)}[ \t]*=[ \t]*).*$"
        )
        block, count = key_re.subn(
            lambda found: found.group(1) + str(value),
            block,
        )
        if count == 0:
            if not block.endswith("\n"):
                block += "\n"
            block += f"{key} = {value}\n"

    return text[:start] + block + text[end:]

def set_global(text, key, value):
    key_re = re.compile(
        rf"(?mi)^([ \t]*{re.escape(key)}[ \t]*=[ \t]*).*$"
    )
    output, count = key_re.subn(
        lambda found: found.group(1) + str(value),
        text,
    )

    if count == 0:
        if not output.endswith("\n"):
            output += "\n"
        output += f"{key} = {value}\n"

    return output

def run_systemctl(*args):
    return subprocess.run(
        ["systemctl", *args],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode

def vpx_running():
    return subprocess.run(
        ["pgrep", "-u", "pinball", "-f", r"VPinballX(_BGFX)?"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode == 0

def vpinfe_state():
    result = subprocess.run(
        ["systemctl", "show", "-p", "ActiveState", "--value",
         "pincabos-vpinfe.service"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() or "unknown"

def main():
    if not SCREENS.exists():
        raise RuntimeError(f"Source absente : {SCREENS}")

    data = json.loads(SCREENS.read_text(encoding="utf-8"))
    all_screens = data.get("all_screens")

    if not isinstance(all_screens, list) or len(all_screens) < 3:
        raise RuntimeError("Moins de trois écrans actifs dans screens.json")

    physical = sorted(
        all_screens,
        key=lambda item: (
            int(item.get("x", 999999)),
            int(item.get("y", 999999)),
            str(item.get("name", "")),
        ),
    )

    names = []
    for index, item in enumerate(physical):
        name = str(item.get("name", "")).strip()
        if not name:
            raise RuntimeError("Un écran actif ne possède pas de nom")

        item["id"] = index
        item["screen_id"] = index
        names.append(name)

    mapping = {name: index for index, name in enumerate(names)}

    roles = {}
    for role in ("playfield", "backglass", "fulldmd"):
        item = data.get(role)
        if not isinstance(item, dict):
            raise RuntimeError(f"Rôle absent : {role}")

        name = str(item.get("name", "")).strip()
        if name not in mapping:
            raise RuntimeError(f"Sortie absente des écrans actifs : {role}={name}")

        width = int(item.get("width", 0))
        height = int(item.get("height", 0))
        x = int(item.get("x", 0))
        y = int(item.get("y", 0))

        if width <= 0 or height <= 0:
            raise RuntimeError(f"Géométrie invalide pour {role}")

        item["id"] = mapping[name]
        item["screen_id"] = mapping[name]

        roles[role] = {
            "name": name,
            "id": mapping[name],
            "geometry": f"{width}x{height}+{x}+{y}",
        }

    pf = roles["playfield"]
    bg = roles["backglass"]
    fd = roles["fulldmd"]

    if (pf["id"], bg["id"], fd["id"]) != (0, 1, 2):
        raise RuntimeError(
            "Topologie inattendue : "
            f"PF={pf['id']} BG={bg['id']} FullDMD={fd['id']}"
        )

    changed_json = atomic_write(
        SCREENS,
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
    )

    aliases = (
        "# Généré automatiquement par PinCabOS.\n"
        "# Source : screens.json | IDs : ordre physique gauche→droite.\n"
        "# Ne pas modifier ce fichier manuellement.\n\n"
        f"PINCABOS_PLAYFIELD_OUTPUT='{pf['name']}'\n"
        f"PINCABOS_BACKGLASS_OUTPUT='{bg['name']}'\n"
        f"PINCABOS_FULLDMD_OUTPUT='{fd['name']}'\n"
        f"PINCABOS_PLAYFIELD_SCREEN_ID='{pf['id']}'\n"
        f"PINCABOS_BACKGLASS_SCREEN_ID='{bg['id']}'\n"
        f"PINCABOS_FULLDMD_SCREEN_ID='{fd['id']}'\n"
        f"PINCABOS_PLAYFIELD_GEOMETRY='{pf['geometry']}'\n"
        f"PINCABOS_BACKGLASS_GEOMETRY='{bg['geometry']}'\n"
        f"PINCABOS_FULLDMD_GEOMETRY='{fd['geometry']}'\n"
    )
    changed_aliases = atomic_write(ALIASES, aliases)

    if not VPINFE.exists():
        raise RuntimeError(f"VPinFE INI absent : {VPINFE}")

    vpinfe = VPINFE.read_text(encoding="utf-8")
    vpinfe = set_section(vpinfe, "Displays", {
        "tablescreenid": pf["id"],
        "bgscreenid": bg["id"],
        "dmdscreenid": fd["id"],
        "fulldmdscreenid": fd["id"],
    })
    vpinfe = set_section(vpinfe, "PinCabOs.FullDMD", {
        "screen_id": fd["id"],
    })
    vpinfe = set_section(vpinfe, "PinCabOs.Screens", {
        "fulldmd_id": fd["id"],
        "dmd_id": fd["id"],
    })
    vpinfe = set_section(vpinfe, "PinCabOs.DMD", {
        "screen_id": fd["id"],
    })
    changed_vpinfe = atomic_write(VPINFE, vpinfe)

    if not VPX.exists():
        raise RuntimeError(f"VPX INI absent : {VPX}")

    vpx = VPX.read_text(encoding="utf-8")
    vpx = set_global(vpx, "tablescreenid", pf["id"])
    vpx = set_global(vpx, "bgscreenid", bg["id"])
    vpx = set_global(vpx, "dmdscreenid", fd["id"])
    vpx = set_global(vpx, "fulldmdscreenid", fd["id"])
    changed_vpx = atomic_write(VPX, vpx)

    changed = changed_json or changed_aliases or changed_vpinfe or changed_vpx

    log(
        f"appliqué : PF={pf['name']}#{pf['id']} | "
        f"BG={bg['name']}#{bg['id']} | "
        f"FullDMD={fd['name']}#{fd['id']}"
    )

    if changed:
        run_systemctl("try-restart", "--no-block",
                      "pincabos-dashboard-live.service")
        run_systemctl("try-restart", "--no-block",
                      "pincabos-scoreview-router.service")

    restart_needed = changed_vpinfe or PENDING.exists()
    if restart_needed:
        if vpx_running():
            PENDING.touch()
            log("VPX est actif : relance VPinFE reportée automatiquement.")
            return

        state = vpinfe_state()
        if state == "deactivating":
            PENDING.touch()
            log("VPinFE est encore en arrêt : relance reportée.")
        elif state == "active":
            run_systemctl("restart", "--no-block", "pincabos-vpinfe.service")
            PENDING.unlink(missing_ok=True)
            log("Relance VPinFE demandée.")
        else:
            run_systemctl("start", "--no-block", "pincabos-vpinfe.service")
            PENDING.unlink(missing_ok=True)
            log("Démarrage VPinFE demandé.")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log(f"ERREUR : {exc}")
        sys.exit(1)
