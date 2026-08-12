#!/usr/bin/env python3
"""
PINCABOS_DISPLAY_ROLES_V1

Source de vérité :
  /opt/pincabos/config/screens/screens.json

Rôles persistants :
  playfield, backglass, fulldmd

Le script apprend l'EDID des écrans au premier passage. Ensuite,
un changement HDMI/DP peut être résolu sans dépendre du nom du port.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path


ROOT = Path("/opt/pincabos")
SCREENS_JSON = ROOT / "config/screens/screens.json"
ALIASES_ENV = ROOT / "config/display-aliases.env"
LOG_FILE = ROOT / "logs/display-roles.log"

ROLES = ("playfield", "backglass", "fulldmd")


def log(message: str) -> None:
    stamp = datetime.now().strftime("%F %T")
    line = f"{stamp} {message}"
    print(line, flush=True)

    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except Exception:
        pass


def run(command: list[str], env: dict[str, str], timeout: int = 12) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def x11_environment(wait_seconds: int) -> tuple[dict[str, str], str]:
    started = time.monotonic()

    auth_candidates = []

    supplied = os.environ.get("XAUTHORITY", "").strip()
    if supplied:
        auth_candidates.append(supplied)

    auth_candidates.extend([
        "/home/pinball/.Xauthority",
        "/run/lightdm/root/:0",
        "/var/run/lightdm/root/:0",
    ])

    seen = set()

    while True:
        for auth in auth_candidates:
            if not auth or auth in seen:
                continue

            seen.add(auth)

            env = os.environ.copy()
            env["DISPLAY"] = os.environ.get("DISPLAY", ":0") or ":0"
            env["XAUTHORITY"] = auth

            result = run(["/usr/bin/xrandr", "--query"], env)

            if result.returncode == 0 and " connected" in result.stdout:
                return env, result.stdout

        if time.monotonic() - started >= wait_seconds:
            break

        seen.clear()
        time.sleep(2)

    raise RuntimeError("Session X11 non disponible ou cookie XAUTHORITY invalide.")


def parse_outputs(raw: str) -> dict[str, dict]:
    outputs: dict[str, dict] = {}

    for line in raw.splitlines():
        match = re.match(
            r"^([A-Za-z0-9_.-]+)\s+connected(?:\s+primary)?(?:\s+([0-9]+x[0-9]+\+[0-9]+\+[0-9]+))?",
            line,
        )

        if not match:
            continue

        name = match.group(1)
        geometry = match.group(2) or ""

        width = height = xpos = ypos = 0

        if geometry:
            parsed = re.match(r"^(\d+)x(\d+)\+(\d+)\+(\d+)$", geometry)

            if parsed:
                width, height, xpos, ypos = map(int, parsed.groups())

        mm = re.search(r"(\d+)mm x (\d+)mm", line)

        outputs[name] = {
            "name": name,
            "geometry": geometry,
            "width": width,
            "height": height,
            "x": xpos,
            "y": ypos,
            "mm_width": int(mm.group(1)) if mm else 0,
            "mm_height": int(mm.group(2)) if mm else 0,
            "raw": line,
            "edid_sha256": "",
        }

    return outputs


def parse_edids(raw: str) -> dict[str, str]:
    found: dict[str, str] = {}
    current = ""
    collecting = False
    chunks: list[str] = []

    for line in raw.splitlines():
        header = re.match(r"^([A-Za-z0-9_.-]+)\s+connected", line)

        if header:
            if current and chunks:
                found[current] = hashlib.sha256(
                    "".join(chunks).encode("ascii", errors="ignore")
                ).hexdigest()

            current = header.group(1)
            collecting = False
            chunks = []
            continue

        if not current:
            continue

        if line.strip() == "EDID:":
            collecting = True
            chunks = []
            continue

        if collecting:
            value = line.strip()

            if re.fullmatch(r"[0-9A-Fa-f]{32}", value):
                chunks.append(value.lower())
                continue

            if chunks:
                found[current] = hashlib.sha256(
                    "".join(chunks).encode("ascii", errors="ignore")
                ).hexdigest()

            collecting = False
            chunks = []

    if current and chunks:
        found[current] = hashlib.sha256(
            "".join(chunks).encode("ascii", errors="ignore")
        ).hexdigest()

    return found


def read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))

        if isinstance(data, dict):
            return data
    except Exception as exc:
        raise RuntimeError(f"Lecture JSON impossible: {exc}") from exc

    raise RuntimeError("screens.json est invalide.")


def atomic_json_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")

        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def resolve_roles(config: dict, outputs: dict[str, dict]) -> dict[str, str]:
    assigned: set[str] = set()
    resolved: dict[str, str] = {}

    for role in ROLES:
        details = config.get(role)

        if not isinstance(details, dict):
            raise RuntimeError(f"Rôle absent ou invalide dans screens.json: {role}")

        expected_edid = str(details.get("edid_sha256", "") or "")
        expected_name = str(details.get("name", "") or "")
        expected_width = int(details.get("width", 0) or 0)
        expected_height = int(details.get("height", 0) or 0)

        candidates: list[str] = []

        if expected_edid:
            candidates = [
                name for name, output in outputs.items()
                if output.get("edid_sha256") == expected_edid and name not in assigned
            ]

        if not candidates and expected_name in outputs and expected_name not in assigned:
            candidates = [expected_name]

        if not candidates and expected_width and expected_height:
            candidates = [
                name for name, output in outputs.items()
                if output["width"] == expected_width
                and output["height"] == expected_height
                and name not in assigned
            ]

        if len(candidates) != 1:
            raise RuntimeError(
                f"Rôle ambigu ou introuvable: {role} "
                f"(candidats: {', '.join(candidates) or 'aucun'})"
            )

        chosen = candidates[0]
        resolved[role] = chosen
        assigned.add(chosen)

    if len(set(resolved.values())) != 3:
        raise RuntimeError("Les trois rôles ne pointent pas vers trois écrans distincts.")

    return resolved


def set_layout(env: dict[str, str], roles: dict[str, str], outputs: dict[str, dict]) -> dict[str, dict]:
    ordered = [
        roles["playfield"],
        roles["backglass"],
        roles["fulldmd"],
    ]

    enable_command = ["/usr/bin/xrandr"]

    for output in ordered:
        enable_command.extend(["--output", output, "--auto"])

    result = run(enable_command, env)

    if result.returncode != 0:
        raise RuntimeError(f"xrandr --auto échoué: {result.stderr.strip()}")

    fresh = parse_outputs(run(["/usr/bin/xrandr", "--query"], env).stdout)

    for output in ordered:
        if output not in fresh or not fresh[output]["geometry"]:
            raise RuntimeError(f"Écran actif invalide après --auto: {output}")

    pf = fresh[roles["playfield"]]
    bg = fresh[roles["backglass"]]

    positions = {
        roles["playfield"]: "0x0",
        roles["backglass"]: f"{pf['width']}x0",
        roles["fulldmd"]: f"{pf['width'] + bg['width']}x0",
    }

    layout_command = [
        "/usr/bin/xrandr",
        "--output", roles["playfield"], "--primary", "--pos", positions[roles["playfield"]],
        "--output", roles["backglass"], "--pos", positions[roles["backglass"]],
        "--output", roles["fulldmd"], "--pos", positions[roles["fulldmd"]],
    ]

    result = run(layout_command, env)

    if result.returncode != 0:
        raise RuntimeError(f"xrandr positionnement échoué: {result.stderr.strip()}")

    checked = parse_outputs(run(["/usr/bin/xrandr", "--query"], env).stdout)

    for output, expected_position in positions.items():
        expected_x, expected_y = map(int, expected_position.split("x"))
        actual = checked.get(output)

        if not actual:
            raise RuntimeError(f"Écran disparu après application: {output}")

        if actual["x"] != expected_x or actual["y"] != expected_y:
            raise RuntimeError(
                f"Position non appliquée pour {output}: "
                f"{actual['x']}x{actual['y']} attendu {expected_position}"
            )

    return checked


def monitor_ids(env: dict[str, str], outputs: dict[str, dict]) -> dict[str, int]:
    result = run(["/usr/bin/xrandr", "--listmonitors"], env)

    ids: dict[str, int] = {}

    if result.returncode == 0:
        for line in result.stdout.splitlines():
            match = re.match(r"^\s*(\d+):.*\s([A-Za-z0-9_.-]+)\s*$", line)

            if match:
                ids[match.group(2)] = int(match.group(1))

    if all(name in ids for name in outputs):
        return ids

    fallback = sorted(outputs.values(), key=lambda row: (row["x"], row["y"], row["name"]))

    return {
        output["name"]: index
        for index, output in enumerate(fallback)
    }


def update_screens_config(
    config: dict,
    roles: dict[str, str],
    outputs: dict[str, dict],
    ids: dict[str, int],
) -> None:
    changed = False

    for role, output_name in roles.items():
        current = config.get(role, {})

        if not isinstance(current, dict):
            current = {}

        output = outputs[output_name]

        update = {
            "id": ids[output_name],
            "screen_id": ids[output_name],
            "name": output_name,
            "width": output["width"],
            "height": output["height"],
            "x": output["x"],
            "y": output["y"],
            "geometry": output["geometry"],
            "raw": output["raw"],
            "edid_sha256": output.get("edid_sha256", ""),
        }

        if any(current.get(key) != value for key, value in update.items()):
            current.update(update)
            config[role] = current
            changed = True

    if changed:
        config["roles_updated_at"] = datetime.now().isoformat(timespec="seconds")
        atomic_json_write(SCREENS_JSON, config)
        log("screens.json synchronisé avec la session X11.")


def write_aliases(
    roles: dict[str, str],
    outputs: dict[str, dict],
    ids: dict[str, int],
) -> None:
    data = {
        "PINCABOS_PLAYFIELD_OUTPUT": roles["playfield"],
        "PINCABOS_BACKGLASS_OUTPUT": roles["backglass"],
        "PINCABOS_FULLDMD_OUTPUT": roles["fulldmd"],
        "PINCABOS_PLAYFIELD_SCREEN_ID": str(ids[roles["playfield"]]),
        "PINCABOS_BACKGLASS_SCREEN_ID": str(ids[roles["backglass"]]),
        "PINCABOS_FULLDMD_SCREEN_ID": str(ids[roles["fulldmd"]]),
        "PINCABOS_PLAYFIELD_GEOMETRY": outputs[roles["playfield"]]["geometry"],
        "PINCABOS_BACKGLASS_GEOMETRY": outputs[roles["backglass"]]["geometry"],
        "PINCABOS_FULLDMD_GEOMETRY": outputs[roles["fulldmd"]]["geometry"],
    }

    lines = [
        "# Généré automatiquement par pincabos-display-roles.py",
        "# Ne pas modifier les sorties ici : utiliser Écrans PinCabOS.",
        "",
    ]

    for key, value in data.items():
        escaped = value.replace("'", "'\"'\"'")
        lines.append(f"{key}='{escaped}'")

    content = "\n".join(lines) + "\n"

    if ALIASES_ENV.exists():
        old = ALIASES_ENV.read_text(encoding="utf-8", errors="replace")

        if old == content:
            return

    ALIASES_ENV.parent.mkdir(parents=True, exist_ok=True)
    ALIASES_ENV.write_text(content, encoding="utf-8")
    os.chmod(ALIASES_ENV, 0o644)

    log(
        "Alias synchronisés : "
        f"PF={roles['playfield']} BG={roles['backglass']} FD={roles['fulldmd']}"
    )


def update_ini_keys(path: Path, values: dict[str, str]) -> None:
    if not path.is_file():
        return

    text = path.read_text(encoding="utf-8", errors="replace")
    updated = text
    touched = 0

    for key, value in values.items():
        pattern = re.compile(rf"(?im)^(\s*{re.escape(key)}\s*=\s*).*$")

        updated, count = pattern.subn(rf"\g<1>{value}", updated)

        touched += count

    if touched and updated != text:
        path.write_text(updated, encoding="utf-8")
        log(f"IDs synchronisés : {path}")


def sync_frontends(ids: dict[str, int], roles: dict[str, str]) -> None:
    pf = str(ids[roles["playfield"]])
    bg = str(ids[roles["backglass"]])
    fd = str(ids[roles["fulldmd"]])

    update_ini_keys(
        Path("/home/pinball/.config/vpinfe/vpinfe.ini"),
        {
            "playfieldscreenid": pf,
            "backglassscreenid": bg,
            "dmdscreenid": fd,
            "fulldmdscreenid": fd,
        },
    )

    vpx_values = {
        "tablescreenid": pf,
        "bgscreenid": bg,
        "dmdscreenid": fd,
        "fulldmdscreenid": fd,
    }

    for path in (
        Path("/home/pinball/.local/share/VPinballX/10.8/VPinballX.ini"),
        Path("/home/pinball/.vpinball/VPinballX.ini"),
    ):
        update_ini_keys(path, vpx_values)


def print_state(roles: dict[str, str], outputs: dict[str, dict], ids: dict[str, int]) -> None:
    print()
    print("=== RÔLES RÉSOLUS ===")

    for role in ROLES:
        output_name = roles[role]
        output = outputs[output_name]

        print(
            f"{role:11} -> {output_name:8} | "
            f"id={ids[output_name]} | {output['geometry']} | "
            f"EDID={output.get('edid_sha256', '')[:12] or 'non lu'}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--wait", type=int, default=12)

    args = parser.parse_args()

    if not args.apply and not args.check:
        args.check = True

    config = read_json(SCREENS_JSON)
    env, query = x11_environment(max(0, args.wait))

    outputs = parse_outputs(query)

    verbose = run(["/usr/bin/xrandr", "--verbose"], env)
    edids = parse_edids(verbose.stdout) if verbose.returncode == 0 else {}

    for name, digest in edids.items():
        if name in outputs:
            outputs[name]["edid_sha256"] = digest

    roles = resolve_roles(config, outputs)

    if args.apply:
        outputs = set_layout(env, roles, outputs)

        verbose = run(["/usr/bin/xrandr", "--verbose"], env)
        edids = parse_edids(verbose.stdout) if verbose.returncode == 0 else {}

        for name, digest in edids.items():
            if name in outputs:
                outputs[name]["edid_sha256"] = digest

    ids = monitor_ids(
        env,
        {
            roles["playfield"]: outputs[roles["playfield"]],
            roles["backglass"]: outputs[roles["backglass"]],
            roles["fulldmd"]: outputs[roles["fulldmd"]],
        },
    )

    if args.apply:
        update_screens_config(config, roles, outputs, ids)
        write_aliases(roles, outputs, ids)
        sync_frontends(ids, roles)

    print_state(roles, outputs, ids)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        log(f"ERREUR: {exc}")
        raise SystemExit(1)
