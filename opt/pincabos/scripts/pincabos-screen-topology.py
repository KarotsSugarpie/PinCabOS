#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/opt/pincabos")
SCREENS = ROOT / "config/screens/screens.json"
BINDINGS = ROOT / "config/screens/display-role-bindings.json"
ALIASES = ROOT / "config/display-aliases.env"
RUNTIME = Path("/run/pincabos-screen-topology")
STATE = RUNTIME / "state.json"

VPINFE = Path("/home/pinball/.config/vpinfe/vpinfe.ini")
VPX = Path("/home/pinball/.local/share/VPinballX/10.8/VPinballX.ini")

ROLES = ("playfield", "backglass", "fulldmd")


def log(message):
    print(f"pincabos-screen-topology: {message}", flush=True)


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_write(path, content, mode=None):
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old == content:
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    old_stat = path.stat() if path.exists() else None
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())

        if old_stat:
            os.chmod(temp_name, old_stat.st_mode & 0o777)
            try:
                os.chown(temp_name, old_stat.st_uid, old_stat.st_gid)
            except PermissionError:
                pass
        elif mode is not None:
            os.chmod(temp_name, mode)

        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass

    return True


def load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def xrandr_as_pinball(*args):
    command = [
        "/usr/sbin/runuser", "-u", "pinball", "--",
        "/usr/bin/env",
        "DISPLAY=:0",
        "XAUTHORITY=/home/pinball/.Xauthority",
        "/usr/bin/xrandr",
        *args,
    ]
    return subprocess.check_output(
        command,
        text=True,
        stderr=subprocess.STDOUT,
        timeout=12,
    )


def parse_edids(properties):
    chunks = re.split(
        r"(?m)^(?=\S+\s+(?:connected|disconnected)\b)",
        properties,
    )

    result = {}

    for chunk in chunks:
        lines = chunk.splitlines()
        if not lines:
            continue

        first = lines[0]
        match = re.match(r"^(\S+)\s+(?:connected|disconnected)\b", first)
        if not match:
            continue

        output = match.group(1)

        edid = re.search(
            r"(?ms)^\s*EDID:\s*$\n((?:\s*[0-9A-Fa-f]{32}\s*\n)+)",
            chunk,
        )

        if not edid:
            continue

        hexdata = re.sub(r"\s+", "", edid.group(1))

        if len(hexdata) >= 256:
            result[output] = hashlib.sha256(
                bytes.fromhex(hexdata)
            ).hexdigest()

    return result


def discover_monitors():
    raw = xrandr_as_pinball("--query")
    props = xrandr_as_pinball("--prop")
    edids = parse_edids(props)

    connected = re.compile(
        r"^(?P<name>\S+)\s+connected(?:\s+primary)?\s+"
        r"(?P<w>\d+)x(?P<h>\d+)\+(?P<x>-?\d+)\+(?P<y>-?\d+)"
    )

    monitors = []

    for line in raw.splitlines():
        match = connected.match(line)
        if not match:
            continue

        item = match.groupdict()
        name = item["name"]

        monitors.append({
            "name": name,
            "x": int(item["x"]),
            "y": int(item["y"]),
            "width": int(item["w"]),
            "height": int(item["h"]),
            "area": int(item["w"]) * int(item["h"]),
            "is_primary": " connected primary " in f" {line}",
            "raw": line,
            "edid_sha256": edids.get(name, f"connector:{name}"),
        })

    return sorted(
        monitors,
        key=lambda item: (item["x"], item["y"], item["name"]),
    )


def infer_roles(monitors):
    """First install / entirely new machine heuristic."""

    if not monitors:
        return {role: None for role in ROLES}

    playfield = max(
        monitors,
        key=lambda item: (
            item["area"],
            item["is_primary"],
            -item["x"],
        ),
    )

    remaining = [
        item for item in monitors
        if item["name"] != playfield["name"]
    ]

    right = [
        item for item in remaining
        if item["x"] >= playfield["x"] + playfield["width"]
    ]

    pool = right or remaining

    backglass = min(
        pool,
        key=lambda item: (
            abs(item["x"] - (playfield["x"] + playfield["width"])),
            item["x"],
            item["y"],
        ),
    ) if pool else None

    remaining = [
        item for item in remaining
        if not backglass or item["name"] != backglass["name"]
    ]

    if backglass:
        right = [
            item for item in remaining
            if item["x"] >= backglass["x"] + backglass["width"]
        ]
        pool = right or remaining
    else:
        pool = remaining

    fulldmd = min(
        pool,
        key=lambda item: (item["x"], item["y"], item["name"]),
    ) if pool else None

    return {
        "playfield": playfield,
        "backglass": backglass,
        "fulldmd": fulldmd,
    }


def resolve_roles(monitors, bindings):
    bound = bindings.get("roles", {}) if isinstance(bindings, dict) else {}
    by_edid = {item["edid_sha256"]: item for item in monitors}

    known = {
        role: bound.get(role)
        for role in ROLES
        if bound.get(role)
    }

    match_count = sum(
        1 for fingerprint in known.values()
        if fingerprint in by_edid
    )

    # Aucun profil, ou migration complète vers une autre machine.
    # Une perte partielle d'écran ne réaffecte jamais un écran au hasard.
    new_machine = (
        not known
        or (match_count == 0 and len(monitors) >= 2)
    )

    if new_machine:
        return infer_roles(monitors), True

    return {
        role: by_edid.get(bound.get(role))
        for role in ROLES
    }, False


def role_object(monitor, app_id, expected_edid):
    if monitor is None:
        return {
            "id": None,
            "screen_id": None,
            "name": "",
            "available": False,
            "expected_edid_sha256": expected_edid or "",
        }

    result = dict(monitor)
    result["id"] = app_id
    result["screen_id"] = app_id
    result["available"] = True
    result["geometry"] = (
        f"{result['width']}x{result['height']}"
        f"+{result['x']}+{result['y']}"
    )

    return result


def update_section(text, section, values):
    header = re.compile(
        rf"(?mi)^[ \t]*\[{re.escape(section)}\][ \t]*$"
    )

    match = header.search(text)

    if not match:
        if not text.endswith("\n"):
            text += "\n"

        text += f"\n[{section}]\n"

        for key, value in values.items():
            text += f"{key} = {value}\n"

        return text

    start = match.end()
    following = re.search(
        r"(?m)^[ \t]*\[.+?\][ \t]*$",
        text[start:],
    )

    end = start + following.start() if following else len(text)
    block = text[start:end]

    for key, value in values.items():
        expression = re.compile(
            rf"(?mi)^([ \t]*{re.escape(key)}[ \t]*=[ \t]*).*$"
        )

        block, count = expression.subn(
            lambda found: found.group(1) + str(value),
            block,
        )

        if count == 0:
            if not block.endswith("\n"):
                block += "\n"

            block += f"{key} = {value}\n"

    return text[:start] + block + text[end:]


def update_global(text, key, value):
    expression = re.compile(
        rf"(?mi)^([ \t]*{re.escape(key)}[ \t]*=[ \t]*).*$"
    )

    output, count = expression.subn(
        lambda found: found.group(1) + str(value),
        text,
    )

    if count == 0:
        if not output.endswith("\n"):
            output += "\n"

        output += f"{key} = {value}\n"

    return output


def apply_consumers(roles):
    """Prépare les prochains démarrages, sans redémarrer aucun service."""

    playfield = roles["playfield"]

    if not playfield["available"]:
        log("Playfield absent : fichiers applicatifs conservés sans modification.")
        return

    backglass = (
        roles["backglass"]
        if roles["backglass"]["available"]
        else playfield
    )

    dmd = (
        roles["fulldmd"]
        if roles["fulldmd"]["available"]
        else backglass
    )

    full_enabled = "1" if roles["fulldmd"]["available"] else "0"

    if VPINFE.exists():
        config = VPINFE.read_text(encoding="utf-8")

        config = update_section(config, "Displays", {
            "tablescreenid": str(playfield["screen_id"]),
            "bgscreenid": str(backglass["screen_id"]),
            "dmdscreenid": str(dmd["screen_id"]),
            "fulldmdscreenid": str(dmd["screen_id"]),
        })

        config = update_section(config, "PinCabOs.FullDMD", {
            "enabled": full_enabled,
            "screen_id": str(dmd["screen_id"]),
        })

        config = update_section(config, "PinCabOs.Screens", {
            "fulldmd_id": str(dmd["screen_id"]),
            "dmd_id": str(dmd["screen_id"]),
        })

        config = update_section(config, "PinCabOs.DMD", {
            "enabled": "1",
            "screen_id": str(dmd["screen_id"]),
        })

        atomic_write(VPINFE, config)

    if VPX.exists():
        config = VPX.read_text(encoding="utf-8")

        config = update_global(
            config,
            "tablescreenid",
            str(playfield["screen_id"]),
        )

        config = update_global(
            config,
            "bgscreenid",
            str(backglass["screen_id"]),
        )

        config = update_global(
            config,
            "dmdscreenid",
            str(dmd["screen_id"]),
        )

        config = update_global(
            config,
            "fulldmdscreenid",
            str(dmd["screen_id"]),
        )

        atomic_write(VPX, config)


def refresh(prepare=False):
    try:
        prior = load_json(SCREENS, {})
        monitors = discover_monitors()
    except Exception as exc:
        log(
            "Découverte X11 indisponible; "
            f"configuration précédente conservée : {exc}"
        )
        return 0

    bindings = load_json(BINDINGS, {})
    selected, new_machine = resolve_roles(monitors, bindings)

    app_indexes = {
        monitor["name"]: index
        for index, monitor in enumerate(monitors)
    }

    expected = bindings.get("roles", {}) if isinstance(bindings, dict) else {}

    roles = {}

    for role in ROLES:
        monitor = selected.get(role)

        roles[role] = role_object(
            monitor,
            app_indexes.get(monitor["name"]) if monitor else None,
            expected.get(role),
        )

    if not roles["playfield"]["available"]:
        log("Aucun Playfield résolu; aucune configuration applicative modifiée.")
        return 0

    if new_machine:
        bindings = {
            "version": 1,
            "bound_at": now(),
            "source": "automatic-first-layout",
            "roles": {
                role: roles[role]["edid_sha256"]
                for role in ROLES
                if roles[role]["available"]
            },
        }

        atomic_write(
            BINDINGS,
            json.dumps(bindings, indent=2, ensure_ascii=False) + "\n",
            0o644,
        )

    document = prior if isinstance(prior, dict) else {}

    document["all_screens"] = [
        dict(
            monitor,
            id=index,
            screen_id=index,
            geometry=(
                f"{monitor['width']}x{monitor['height']}"
                f"+{monitor['x']}+{monitor['y']}"
            ),
        )
        for index, monitor in enumerate(monitors)
    ]

    document["playfield"] = roles["playfield"]
    document["backglass"] = roles["backglass"]
    document["fulldmd"] = roles["fulldmd"]

    selected_outputs = {
        roles[role].get("name", "")
        for role in ROLES
    }

    document["role_resolution"] = {
        "status": (
            "ready"
            if roles["playfield"]["available"]
            and roles["backglass"]["available"]
            else "degraded"
        ),
        "screen_count": len(monitors),
        "full_dmd_available": roles["fulldmd"]["available"],
        "extras": [
            monitor["name"]
            for monitor in monitors
            if monitor["name"] not in selected_outputs
        ],
        "binding_mode": (
            "automatic-new-system"
            if new_machine
            else "edid-bound"
        ),
        "updated_at": now(),
    }

    atomic_write(
        SCREENS,
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        0o644,
    )

    status = document["role_resolution"]["status"]

    aliases = (
        "# Generated by PinCabOS adaptive screen topology engine.\n"
        "# Source of truth: screens.json + EDID role bindings.\n"
        "# Do not edit manually.\n\n"
        f"PINCABOS_SCREEN_TOPOLOGY_STATUS='{status}'\n"
        f"PINCABOS_SCREEN_COUNT='{len(monitors)}'\n"
        f"PINCABOS_PLAYFIELD_AVAILABLE='{int(roles['playfield']['available'])}'\n"
        f"PINCABOS_BACKGLASS_AVAILABLE='{int(roles['backglass']['available'])}'\n"
        f"PINCABOS_FULLDMD_AVAILABLE='{int(roles['fulldmd']['available'])}'\n"
    )

    for role, label in (
        ("playfield", "PLAYFIELD"),
        ("backglass", "BACKGLASS"),
        ("fulldmd", "FULLDMD"),
    ):
        item = roles[role]

        aliases += (
            f"PINCABOS_{label}_OUTPUT='{item.get('name', '')}'\n"
        )

        aliases += (
            f"PINCABOS_{label}_SCREEN_ID="
            f"'{'' if item.get('screen_id') is None else item['screen_id']}'\n"
        )

        aliases += (
            f"PINCABOS_{label}_GEOMETRY="
            f"'{item.get('geometry', '')}'\n"
        )

    atomic_write(ALIASES, aliases, 0o644)

    RUNTIME.mkdir(parents=True, exist_ok=True)

    atomic_write(
        STATE,
        json.dumps(
            {
                "roles": roles,
                "resolution": document["role_resolution"],
            },
            indent=2,
            ensure_ascii=False,
        ) + "\n",
        0o644,
    )

    if prepare:
        apply_consumers(roles)

        log(
            "applications préparées sans redémarrage : "
            f"PF={roles['playfield']['name']} "
            f"BG={roles['backglass']['name'] or 'fallback'} "
            f"DMD={roles['fulldmd']['name'] or roles['backglass']['name']}"
        )
    else:
        log(
            f"topologie actualisée : {len(monitors)} écran(s), "
            f"mode={document['role_resolution']['binding_mode']}, "
            f"état={status}"
        )

    return 0


def adopt_current_roles():
    """Appelé par l'interface Écrans après un choix explicite."""

    try:
        document = load_json(SCREENS, {})
        monitors = discover_monitors()
    except Exception as exc:
        log(f"Adoption impossible : {exc}")
        return 0

    by_name = {
        monitor["name"]: monitor
        for monitor in monitors
    }

    adopted = {}

    for role in ROLES:
        item = document.get(role, {})

        name = (
            str(item.get("name", "")).strip()
            if isinstance(item, dict)
            else ""
        )

        if name in by_name:
            adopted[role] = by_name[name]["edid_sha256"]

    if "playfield" not in adopted:
        log("Adoption ignorée : Playfield absent des écrans connectés.")
        return 0

    atomic_write(
        BINDINGS,
        json.dumps(
            {
                "version": 1,
                "bound_at": now(),
                "source": "PinCabOS Screens explicit selection",
                "roles": adopted,
            },
            indent=2,
            ensure_ascii=False,
        ) + "\n",
        0o644,
    )

    log("Choix explicite de l'interface Écrans adopté.")
    return refresh(prepare=True)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--prepare",
        action="store_true",
        help="prépare VPX/VPinFE sans redémarrer les services",
    )

    parser.add_argument(
        "--adopt-current-roles",
        action="store_true",
        help="adopte les rôles explicitement définis dans screens.json",
    )

    args = parser.parse_args()

    if args.adopt_current_roles:
        return adopt_current_roles()

    return refresh(prepare=args.prepare)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        log(f"ERREUR : {exc}")
        raise SystemExit(1)
