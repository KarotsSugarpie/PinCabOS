"""Étape Disque de l'assistant : disques de la machine et PinCabOS déjà installés.

PINCABOS_INSTALLEUR_DISQUE_V1

Le moteur sait réinstaller par-dessus une installation existante en gardant
tables, médias et réglages (mode « mise à jour », liste PCO_KEEP_PATHS). Ici on
regarde, disque par disque, s'il porte un PinCabOS : une partition ext4 montée
en lecture seule qui contient /opt/pincabos et /home/pinball, avec la version
lue dans /opt/pincabos/config/version.json. La page propose alors la mise à
jour d'office, et n'offre pas ce mode sur un disque qui n'a rien.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile

IGNORES = ("loop", "sr", "zram", "ram")
FS_RACINE = ("ext4", "ext3", "btrfs", "xfs")


def executer(args, timeout=20):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.SubprocessError) as exc:
        return 99, str(exc)


def disques(lsblk_json: str) -> list:
    """Disques réels et leurs partitions, depuis `lsblk -J -o NAME,SIZE,TYPE,MODEL,FSTYPE,PATH`."""
    try:
        data = json.loads(lsblk_json)
    except ValueError:
        return []
    out = []
    for d in data.get("blockdevices", []):
        if d.get("type") != "disk" or str(d.get("name", "")).startswith(IGNORES):
            continue
        parts = []
        for c in d.get("children", []) or []:
            if c.get("type") == "part":
                parts.append({"dev": c.get("path") or "/dev/" + c["name"], "fstype": c.get("fstype") or "", "size": c.get("size", "?")})
        out.append({"dev": d.get("path") or "/dev/" + d["name"], "size": d.get("size", "?"),
                    "model": (d.get("model") or "").strip() or "Disque", "partitions": parts})
    return out


def version_pincabos(racine: str) -> str | None:
    """« Alpha 3.66 » si `racine` est une racine PinCabOS (mêmes critères que le moteur), sinon None."""
    if not (os.path.isdir(os.path.join(racine, "opt/pincabos")) and os.path.isdir(os.path.join(racine, "home/pinball"))):
        return None
    try:
        with open(os.path.join(racine, "opt/pincabos/config/version.json"), encoding="utf-8") as f:
            v = json.load(f).get("version")
        return str(v) if v else "?"
    except (OSError, ValueError):
        return "?"


def chercher_pincabos(disque: dict, run=executer, sonde=version_pincabos) -> dict | None:
    """Monte en lecture seule chaque partition « racine » du disque et cherche un PinCabOS."""
    for p in disque.get("partitions", []):
        if p.get("fstype") not in FS_RACINE:
            continue
        point = tempfile.mkdtemp(prefix="pco-sonde-")
        try:
            rc, _ = run(["mount", "-o", "ro", p["dev"], point])
            if rc != 0:
                continue
            try:
                version = sonde(point)
            finally:
                run(["umount", point])
            if version:
                return {"version": version, "partition": p["dev"]}
        finally:
            try:
                os.rmdir(point)
            except OSError:
                pass
    return None


def detecter(run=executer, sonde=version_pincabos) -> list:
    rc, out = run(["lsblk", "-J", "-o", "NAME,SIZE,TYPE,MODEL,FSTYPE,PATH"])
    liste = disques(out) if rc == 0 else []
    for d in liste:
        d["pincabos"] = chercher_pincabos(d, run=run, sonde=sonde)
    return liste


def modes_possibles(disque: dict) -> list:
    """1 = effacer, 2 = espace libre, 3 = mise à jour (seulement si un PinCabOS est là)."""
    return ["1", "2", "3"] if disque.get("pincabos") else ["1", "2"]


def mode_propose(disque: dict) -> str:
    return "3" if disque.get("pincabos") else "1"
