#!/usr/bin/env python3
# PinCabOS — synchronisation automatique des consommateurs d'écrans.
# Source des rôles : /opt/pincabos/config/screens/screens.json
# Les IDs VPX/VPinFE sont calculés selon la position X/Y, jamais selon
# l'ordre instable retourné par xrandr --listmonitors.

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCREENS_JSON = Path("/opt/pincabos/config/screens/screens.json")
ALIASES = Path("/opt/pincabos/config/display-aliases.env")
VPINFE = Path("/home/pinball/.config/vpinfe/vpinfe.ini")
VPX = Path("/home/pinball/.local/share/VPinballX/10.8/VPinballX.ini")
STATE = Path("/run/pincabos-display-role-app-sync.json")
PENDING = Path("/run/pincabos-display-role-app-sync-vpinfe.pending")

ROLE_LABELS = {
    "playfield": "PLAYFIELD",
    "backglass": "BACKGLASS",
    "fulldmd": "FULLDMD",
}

def log(message: str) -> None:
    print(f"pincabos-display-role-app-sync: {message}", flush=True)

def atomic_write_if_changed(path: Path, content: str) -> bool:
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old == content:
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    st = path.stat() if path.exists() else None
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        if st:
            os.chmod(temp_name, st.st_mode & 0o777)
            try:
                os.chown(temp_name, st.st_uid, st.st_gid)
            except PermissionError:
                pass
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
    return True

def section_update(text: str, section_name: str, updates: dict[str, str]) -> str:
    header_re = re.compile(
        rf"(?mi)^[ \t]*\[{re.escape(section_name)}\][ \t]*$"
    )
    match = header_re.search(text)
    if not match:
        raise RuntimeError(f"Section absente dans VPinFE : [{section_name}]")

    next_header = re.search(r"(?m)^[ \t]*\[.+?\][ \t]*$", text[match.end():])
    start = match.end()
    end = start + next_header.start() if next_header else len(text)
    block = text[start:end]

    for key, value in updates.items():
        key_re = re.compile(
            rf"(?mi)^([ \t]*{re.escape(key)}[ \t]*=[ \t]*).*$"
        )
        block, count = key_re.subn(lambda m: m.group(1) + value, block)
        if count == 0:
            if not block.endswith("\n"):
                block += "\n"
            block += f"{key} = {value}\n"

    return text[:start] + block + text[end:]

def global_update(text: str, key: str, value: str) -> str:
    key_re = re.compile(rf"(?mi)^([ \t]*{re.escape(key)}[ \t]*=[ \t]*).*$")
    updated, count = key_re.subn(lambda m: m.group(1) + value, text)
    if count == 0:
        raise RuntimeError(f"Clé VPX absente : {key}")
    return updated

def is_vpx_running() -> bool:
    probe = subprocess.run(
        ["pgrep", "-u", "pinball", "-f", r"VPinballX(_BGFX)?"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return probe.returncode == 0

def restart(unit: str) -> None:
    result = subprocess.run(
        ["systemctl", "try-restart", unit],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        log(f"service relancé : {unit}")
    else:
        log(f"attention, relance non appliquée : {unit}")

def main() -> int:
    if not SCREENS_JSON.exists():
        raise RuntimeError(f"Source absente : {SCREENS_JSON}")

    data = json.loads(SCREENS_JSON.read_text(encoding="utf-8"))
    all_screens = data.get("all_screens")
    if not isinstance(all_screens, list) or not all_screens:
        raise RuntimeError("all_screens absent ou vide dans screens.json")

    # ID applicatif stable : écrans triés selon leur vraie position physique.
    ordered = sorted(
        all_screens,
        key=lambda s: (
            int(s.get("x", 999999)),
            int(s.get("y", 999999)),
            str(s.get("name", "")),
        ),
    )

    screen_ids = {}
    for index, screen in enumerate(ordered):
        name = str(screen.get("name", "")).strip()
        if not name:
            raise RuntimeError("Un écran sans nom est présent dans all_screens")
        screen_ids[name] = index

    roles = {}
    for role in ROLE_LABELS:
        item = data.get(role)
        if not isinstance(item, dict):
            raise RuntimeError(f"Rôle absent : {role}")

        name = str(item.get("name", "")).strip()
        if name not in screen_ids:
            raise RuntimeError(
                f"{role}: sortie {name!r} absente des écrans X11 actuels"
            )

        width = int(item.get("width", 0))
        height = int(item.get("height", 0))
        x = int(item.get("x", 0))
        y = int(item.get("y", 0))
        if width <= 0 or height <= 0:
            raise RuntimeError(f"{role}: géométrie invalide")

        roles[role] = {
            "name": name,
            "id": screen_ids[name],
            "geometry": f"{width}x{height}+{x}+{y}",
        }

    pf = roles["playfield"]
    bg = roles["backglass"]
    fd = roles["fulldmd"]

    # Protection explicite : le FullDMD doit être à droite du Backglass.
    if not (pf["id"] == 0 and bg["id"] < fd["id"]):
        raise RuntimeError(
            "Ordre écran invalide : PF/BG/FullDMD ne correspondent plus "
            "à la topologie physique attendue."
        )

    aliases = (
        "# Généré automatiquement par PinCabOS.\n"
        "# Source : screens.json. IDs applicatifs : ordre physique gauche→droite.\n"
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

    changed = atomic_write_if_changed(ALIASES, aliases)

    if not VPINFE.exists():
        raise RuntimeError(f"VPinFE INI absent : {VPINFE}")
    vpinfe = VPINFE.read_text(encoding="utf-8")
    vpinfe = section_update(vpinfe, "Displays", {
        "tablescreenid": str(pf["id"]),
        "bgscreenid": str(bg["id"]),
        "dmdscreenid": str(fd["id"]),
        "fulldmdscreenid": str(fd["id"]),
    })
    vpinfe = section_update(vpinfe, "PinCabOs.FullDMD", {
        "screen_id": str(fd["id"]),
    })
    vpinfe = section_update(vpinfe, "PinCabOs.Screens", {
        "fulldmd_id": str(fd["id"]),
        "dmd_id": str(fd["id"]),
    })
    vpinfe = section_update(vpinfe, "PinCabOs.DMD", {
        "screen_id": str(fd["id"]),
    })
    changed = atomic_write_if_changed(VPINFE, vpinfe) or changed

    if not VPX.exists():
        raise RuntimeError(f"VPX INI absent : {VPX}")
    vpx = VPX.read_text(encoding="utf-8")
    vpx = global_update(vpx, "tablescreenid", str(pf["id"]))
    vpx = global_update(vpx, "bgscreenid", str(bg["id"]))
    vpx = global_update(vpx, "dmdscreenid", str(fd["id"]))
    vpx = global_update(vpx, "fulldmdscreenid", str(fd["id"]))
    changed = atomic_write_if_changed(VPX, vpx) or changed

    STATE.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_if_changed(
        STATE,
        json.dumps(
            {
                "playfield": pf,
                "backglass": bg,
                "fulldmd": fd,
                "changed": changed,
            },
            indent=2,
            ensure_ascii=False,
        ) + "\n",
    )

    log(
        "rôles publiés : "
        f"PF={pf['name']}#{pf['id']} | "
        f"BG={bg['name']}#{bg['id']} | "
        f"FullDMD={fd['name']}#{fd['id']}"
    )

    must_restart_vpinfe = changed or PENDING.exists()
    if changed:
        restart("pincabos-dashboard-live.service")
        restart("pincabos-scoreview-router.service")

    if must_restart_vpinfe:
        if is_vpx_running():
            PENDING.touch()
            log("VPX est en cours : VPinFE sera relancé automatiquement après la table.")
        else:
            restart("pincabos-vpinfe.service")
            try:
                PENDING.unlink()
            except FileNotFoundError:
                pass

    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        log(f"ERREUR : {exc}")
        raise SystemExit(1)
