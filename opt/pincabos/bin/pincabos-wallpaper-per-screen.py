#!/usr/bin/env python3
# PINCABOS_WALLPAPERS_PER_SCREEN_V1

from __future__ import annotations

import argparse
import json
import os
import pwd
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROLES = (
    "playfield",
    "backglass",
    "fulldmd",
)

SCREENS_CONFIG = Path(
    "/opt/pincabos/config/screens/screens.json"
)

WALLPAPERS_CONFIG = Path(
    "/opt/pincabos/config/screens/wallpapers.json"
)

PINBALL_HOME = Path(
    "/home/pinball"
)


def fail(message: str) -> None:
    print(
        f"NOGO: {message}",
        file=sys.stderr,
    )
    raise SystemExit(1)


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(
            path.read_text(
                encoding="utf-8",
                errors="replace",
            )
            or "{}"
        )
    except Exception as error:
        fail(
            f"lecture JSON impossible : "
            f"{path} : {error}"
        )

    if not isinstance(data, dict):
        fail(
            f"contenu JSON invalide : {path}"
        )

    return data


def x_environment() -> dict[str, str]:
    environment = os.environ.copy()

    environment["HOME"] = str(
        PINBALL_HOME
    )

    environment["DISPLAY"] = (
        environment.get("DISPLAY")
        or ":0"
    )

    environment["XAUTHORITY"] = (
        environment.get("XAUTHORITY")
        or str(PINBALL_HOME / ".Xauthority")
    )

    try:
        account = pwd.getpwnam("pinball")
        runtime = Path(
            f"/run/user/{account.pw_uid}"
        )
    except KeyError:
        runtime = Path("/run/user/1000")

    environment["XDG_RUNTIME_DIR"] = str(
        runtime
    )

    return environment


def detect_monitors(
    environment: dict[str, str],
) -> list[str]:
    try:
        result = subprocess.run(
            [
                "xrandr",
                "--listmonitors",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=8,
            env=environment,
            check=False,
        )
    except Exception as error:
        fail(
            f"xrandr --listmonitors impossible : "
            f"{error}"
        )

    if result.returncode != 0:
        fail(
            "xrandr --listmonitors a échoué :\n"
            + (result.stdout or "")
        )

    monitors: list[str] = []

    for line in (
        result.stdout or ""
    ).splitlines()[1:]:
        parts = line.split()

        if len(parts) < 3:
            continue

        # La dernière colonne est le nom de sortie,
        # par exemple HDMI-0, DP-1 ou DP-2.
        output = parts[-1].strip()

        if (
            output
            and output not in monitors
        ):
            monitors.append(output)

    if not monitors:
        fail(
            "aucun moniteur X11 actif détecté."
        )

    return monitors


def role_item(
    screens: dict[str, Any],
    role: str,
) -> dict[str, Any]:
    sources = [
        screens,
        screens.get("roles", {}),
    ]

    for source in sources:
        if not isinstance(source, dict):
            continue

        item = source.get(role)

        if isinstance(item, dict):
            return item

        if isinstance(item, (str, int)):
            return {
                "id": item,
            }

    return {}


def resolve_role_output(
    screens: dict[str, Any],
    monitors: list[str],
    role: str,
) -> str:
    item = role_item(
        screens,
        role,
    )

    for key in (
        "output",
        "name",
        "connector",
    ):
        candidate = str(
            item.get(key) or ""
        ).strip()

        if candidate in monitors:
            return candidate

    raw_id = item.get("id")

    try:
        screen_id = int(raw_id)
    except (TypeError, ValueError):
        screen_id = -1

    if 0 <= screen_id < len(monitors):
        return monitors[screen_id]

    fail(
        f"écran non assigné pour le rôle {role}. "
        f"Moniteurs détectés : {', '.join(monitors)}"
    )


def role_wallpaper(
    wallpaper_config: dict[str, Any],
    role: str,
) -> Path:
    roles = wallpaper_config.get(
        "roles",
        {},
    )

    if not isinstance(roles, dict):
        fail(
            "section roles absente de "
            f"{WALLPAPERS_CONFIG}"
        )

    item = roles.get(role)

    if not isinstance(item, dict):
        fail(
            f"wallpaper non configuré pour {role}"
        )

    path_text = str(
        item.get("path") or ""
    ).strip()

    if not path_text:
        fail(
            f"chemin wallpaper vide pour {role}"
        )

    image = Path(
        path_text
    ).expanduser().resolve()

    if not image.is_file():
        fail(
            f"image absente pour {role} : {image}"
        )

    return image


def build_mapping() -> tuple[
    list[str],
    dict[str, str],
    dict[str, Path],
]:
    environment = x_environment()
    monitors = detect_monitors(
        environment
    )

    screens = load_json(
        SCREENS_CONFIG
    )

    wallpapers = load_json(
        WALLPAPERS_CONFIG
    )

    outputs: dict[str, str] = {}
    images: dict[str, Path] = {}

    for role in ROLES:
        outputs[role] = resolve_role_output(
            screens,
            monitors,
            role,
        )

        images[role] = role_wallpaper(
            wallpapers,
            role,
        )

    if len(set(outputs.values())) != len(ROLES):
        fail(
            "plusieurs rôles utilisent le même écran : "
            + ", ".join(
                f"{role}={output}"
                for role, output
                in outputs.items()
            )
        )

    assigned_by_output = {
        output: role
        for role, output in outputs.items()
    }

    unassigned = [
        monitor
        for monitor in monitors
        if monitor not in assigned_by_output
    ]

    if unassigned:
        fail(
            "moniteur actif sans rôle PinCabOS : "
            + ", ".join(unassigned)
        )

    return monitors, outputs, images


def feh_command(
    monitors: list[str],
    outputs: dict[str, str],
    images: dict[str, Path],
) -> list[str]:
    feh = shutil.which("feh")

    if not feh:
        fail(
            "commande feh absente."
        )

    role_by_output = {
        output: role
        for role, output in outputs.items()
    }

    ordered_images: list[str] = []

    for monitor in monitors:
        role = role_by_output.get(
            monitor
        )

        if not role:
            fail(
                f"aucune image assignée à {monitor}"
            )

        ordered_images.append(
            str(images[role])
        )

    return [
        feh,
        "--bg-fill",
        *ordered_images,
    ]


def run_as_pinball(
    command: list[str],
    environment: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    if os.geteuid() == 0:
        full_command = [
            "runuser",
            "-u",
            "pinball",
            "--",
            "env",
            f"HOME={environment['HOME']}",
            f"DISPLAY={environment['DISPLAY']}",
            f"XAUTHORITY={environment['XAUTHORITY']}",
            f"XDG_RUNTIME_DIR={environment['XDG_RUNTIME_DIR']}",
            *command,
        ]

        process_environment = os.environ.copy()

    else:
        full_command = command
        process_environment = environment

    return subprocess.run(
        full_command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=15,
        env=process_environment,
        check=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Applique un wallpaper distinct "
            "sur chaque écran PinCabOS."
        )
    )

    parser.add_argument(
        "--check",
        action="store_true",
        help="Valide seulement la configuration.",
    )

    parser.add_argument(
        "--trigger-role",
        choices=ROLES,
        default="",
    )

    parser.add_argument(
        "--trigger-image",
        default="",
    )

    args = parser.parse_args()

    monitors, outputs, images = (
        build_mapping()
    )

    if args.trigger_role:
        expected = images[
            args.trigger_role
        ]

        if args.trigger_image:
            supplied = Path(
                args.trigger_image
            ).expanduser().resolve()

            if supplied != expected:
                fail(
                    "le chemin soumis par la WebApp "
                    "ne correspond pas au fichier configuré : "
                    f"{supplied} != {expected}"
                )

    role_by_output = {
        output: role
        for role, output in outputs.items()
    }

    print(
        "Configuration des wallpapers :"
    )

    for index, monitor in enumerate(
        monitors
    ):
        role = role_by_output[monitor]

        print(
            f"  Écran {index} {monitor}"
            f" <- {role}"
            f" <- {images[role]}"
        )

    if args.check:
        print(
            "GO: configuration multiécran valide."
        )
        return

    environment = x_environment()

    command = feh_command(
        monitors,
        outputs,
        images,
    )

    result = run_as_pinball(
        command,
        environment,
    )

    output = (
        result.stdout or ""
    ).strip()

    if result.returncode != 0:
        fail(
            "application avec feh échouée.\n"
            + "Commande : "
            + " ".join(command)
            + "\n"
            + output
        )

    fehbg = (
        PINBALL_HOME / ".fehbg"
    )

    if fehbg.exists():
        try:
            account = pwd.getpwnam(
                "pinball"
            )

            os.chown(
                fehbg,
                account.pw_uid,
                account.pw_gid,
            )

            os.chmod(
                fehbg,
                0o755,
            )
        except Exception:
            pass

    print(
        "GO: wallpapers appliqués séparément "
        "sur les écrans PinCabOS."
    )

    print(
        "Commande : "
        + " ".join(command)
    )

    if output:
        print(output)


if __name__ == "__main__":
    main()
