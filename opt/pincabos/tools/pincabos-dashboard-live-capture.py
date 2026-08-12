#!/usr/bin/env python3
# PINCABOS_DASHBOARD_LIVE_CAPTURE_V1
# Capture X11 légère, pilotée par lease Dashboard, sans modifier les écrans.

from __future__ import annotations

import json
import os
import pwd
import re
import subprocess
import time
from pathlib import Path

CFG = Path("/opt/pincabos/config/screens/screens.json")
LIVE_DIR = Path("/run/pincabos-dashboard-live")
LEASE = LIVE_DIR / "lease"
IMPORT = "/usr/bin/import"
XRANDR = "/usr/bin/xrandr"

LEASE_SECONDS = 6.0
LOOP_SECONDS = 0.20
RESIZE = "960x540>"
QUALITY = "60"

PINBALL = pwd.getpwnam("pinball")
PINBALL_UID = PINBALL.pw_uid
PINBALL_GID = PINBALL.pw_gid
LAST_MESSAGE: dict[str, str] = {}


def log_once(key: str, message: str) -> None:
    if LAST_MESSAGE.get(key) == message:
        return
    LAST_MESSAGE[key] = message
    print(message, flush=True)


def xauth_path() -> str:
    try:
        result = subprocess.run(
            ["ps", "-eo", "args="],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except Exception:
        return ""

    match = re.search(r"Xorg .* -auth ([^ ]+)", result.stdout)
    return match.group(1) if match else ""


def requested_slots() -> list[int]:
    try:
        if not LEASE.is_file():
            return []
        if time.time() - LEASE.stat().st_mtime > LEASE_SECONDS:
            return []
        raw = LEASE.read_text(encoding="ascii", errors="ignore")
    except OSError:
        return []

    result = []
    for value in raw.replace("\n", ",").split(","):
        try:
            slot = int(value.strip())
        except ValueError:
            continue
        if slot in (0, 1, 2) and slot not in result:
            result.append(slot)
    return result


def configured_outputs() -> dict[int, str]:
    try:
        data = json.loads(CFG.read_text(encoding="utf-8"))
    except Exception as error:
        log_once("cfg", f"WARN: screens.json illisible: {error}")
        return {}

    result = {}
    for slot, role in enumerate(("playfield", "backglass", "fulldmd")):
        item = data.get(role) or {}
        name = str(item.get("name") or "").strip()
        if name:
            result[slot] = name
    return result


def active_outputs(auth: str) -> dict[str, tuple[int, int, int, int]]:
    if not auth or not os.path.isfile(auth):
        return {}

    env = os.environ.copy()
    env["DISPLAY"] = ":0"
    env["XAUTHORITY"] = auth

    try:
        result = subprocess.run(
            [XRANDR, "--query"],
            env=env,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception as error:
        log_once("xrandr", f"WARN: xrandr indisponible: {error}")
        return {}

    if result.returncode != 0:
        log_once("xrandr", "WARN: xrandr retourne une erreur.")
        return {}

    outputs = {}
    pattern = re.compile(
        r"^(\S+)\s+connected(?:\s+primary)?\s+"
        r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)"
    )

    for line in result.stdout.splitlines():
        match = pattern.match(line)
        if not match:
            continue
        name, width, height, x, y = match.groups()
        outputs[name] = (int(width), int(height), int(x), int(y))

    return outputs


def remove_frame(slot: int) -> None:
    path = LIVE_DIR / f"screen{slot}.jpg"
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass


def capture(slot: int, geometry: tuple[int, int, int, int], auth: str) -> None:
    width, height, x, y = geometry
    target = LIVE_DIR / f"screen{slot}.jpg"
    temp = LIVE_DIR / f".screen{slot}.{os.getpid()}.jpg"
    crop = f"{width}x{height}{x:+d}{y:+d}"

    env = os.environ.copy()
    env["DISPLAY"] = ":0"
    env["XAUTHORITY"] = auth

    try:
        temp.unlink()
    except FileNotFoundError:
        pass

    try:
        result = subprocess.run(
            [
                IMPORT,
                "-silent",
                "-window", "root",
                "-crop", crop,
                "-resize", RESIZE,
                "-strip",
                "-quality", QUALITY,
                str(temp),
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=12,
            check=False,
        )

        if result.returncode != 0 or not temp.is_file() or temp.stat().st_size < 64:
            message = (result.stderr or result.stdout or "capture vide").strip()[:180]
            log_once(f"capture-{slot}", f"WARN: capture slot {slot} échouée: {message}")
            remove_frame(slot)
            return

        os.chown(temp, PINBALL_UID, PINBALL_GID)
        os.chmod(temp, 0o644)
        os.replace(temp, target)
        LAST_MESSAGE.pop(f"capture-{slot}", None)

    except Exception as error:
        log_once(f"capture-{slot}", f"WARN: capture slot {slot} échouée: {error}")
        remove_frame(slot)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass


def main() -> None:
    print("GO: Dashboard Live capture worker started.", flush=True)

    while True:
        slots = requested_slots()
        if not slots:
            time.sleep(0.5)
            continue

        auth = xauth_path()
        outputs = active_outputs(auth)
        configured = configured_outputs()

        if not auth or not outputs or not configured:
            time.sleep(0.5)
            continue

        for slot in slots:
            output_name = configured.get(slot, "")
            geometry = outputs.get(output_name)

            if not output_name or geometry is None:
                remove_frame(slot)
                log_once(
                    f"missing-{slot}",
                    f"WARN: slot {slot} absent ou non actif ({output_name or 'sans sortie'}).",
                )
                continue

            LAST_MESSAGE.pop(f"missing-{slot}", None)
            capture(slot, geometry, auth)

        time.sleep(LOOP_SECONDS)


if __name__ == "__main__":
    main()
