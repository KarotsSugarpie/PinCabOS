#!/usr/bin/env python3

import atexit
import configparser
import os
import re
import subprocess
import sys
import time
import tkinter as tk

from pathlib import Path
from PIL import Image, ImageTk


FRAME = Path(
    "/dev/shm/pincabos-rawscore.ppm"
)

TEMP_FRAME = Path(
    "/dev/shm/pincabos-rawscore.ppm.tmp"
)

RUNTIME_DIR = Path(
    "/run/pincabos-b2s-dmd-tuner"
)

COMMAND_FILE = (
    RUNTIME_DIR /
    "command.env"
)

STATE_FILE = (
    RUNTIME_DIR /
    "state.env"
)

PIDFILE = Path(
    "/tmp/pincabos-pup-rawscore-overlay.pid"
)

RAWTAP_LOG = Path(
    "/tmp/pincabos-rawtap-v20.log"
)


VPX_PID = (
    int(sys.argv[1])
    if len(sys.argv) > 1
    else 0
)

TABLE = (
    Path(sys.argv[2])
    if len(sys.argv) > 2
    and sys.argv[2]
    and sys.argv[2] != "unknown"
    else None
)


def pid_alive(pid):

    if pid <= 0:
        return False

    try:
        os.kill(
            pid,
            0
        )

        return True

    except OSError:
        return False


def read_env(path):

    result = {}

    try:
        text = path.read_text(
            encoding="utf-8",
            errors="ignore"
        )

    except OSError:
        return result

    for raw in text.splitlines():

        if "=" not in raw:
            continue

        key, value = raw.split(
            "=",
            1
        )

        result[
            key.strip()
        ] = value.strip()

    return result


def integer(value, default):

    try:
        return int(value)

    except Exception:
        return default


def screen_geometry():

    env = os.environ.copy()

    try:
        result = subprocess.run(
            [
                "xrandr",
                "--listmonitors",
            ],
            env=env,
            text=True,
            capture_output=True,
            timeout=2,
            check=False,
        )

    except Exception:
        result = None


    monitors = []

    if result:

        for line in result.stdout.splitlines():

            match = re.search(
                r'(\d+)/\d+x(\d+)/\d+\+(-?\d+)\+(-?\d+)',
                line
            )

            if not match:
                continue

            w, h, x, y = map(
                int,
                match.groups()
            )

            monitors.append(
                {
                    "w": w,
                    "h": h,
                    "x": x,
                    "y": y,
                }
            )


    if monitors:

        exact = [
            m
            for m in monitors
            if m["w"] == 1920
            and m["h"] == 1200
        ]

        candidates = (
            exact
            if exact
            else monitors
        )

        return max(
            candidates,
            key=lambda m: (
                m["x"],
                m["y"]
            )
        )


    return {
        "x": 5760,
        "y": 0,
        "w": 1920,
        "h": 1200,
    }


def screen_geometry_from_roles():
    """Geometrie de l'ecran du role fulldmd, publiee par la topologie
    (display-aliases.env, derivee de screens.json). Prioritaire sur
    l'heuristique xrandr ci-dessus, qui cherchait "l'ecran 1920x1200 sinon le
    plus a droite" — c'est-a-dire l'ecran du cab de developpement."""
    try:
        values = {}
        with open("/opt/pincabos/config/display-aliases.env", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    values[key.strip()] = value.strip().strip("'\"")
        if values.get("PINCABOS_FULLDMD_AVAILABLE") == "1":
            match = re.match(
                r"^(\d+)x(\d+)\+(-?\d+)\+(-?\d+)$",
                values.get("PINCABOS_FULLDMD_GEOMETRY", ""),
            )
            if match:
                w, h, x, y = map(int, match.groups())
                return {"x": x, "y": y, "w": w, "h": h}
    except Exception:
        pass
    return None


SCREEN = screen_geometry_from_roles() or screen_geometry()


def load_table_layout():

    values = {
        "auto": 0,
        "x": 0,
        "y": 0,
        "w": 640,
        "h": 160,
    }


    if TABLE is None:
        return values


    ini = TABLE.with_suffix(
        ".ini"
    )

    if not ini.is_file():
        return values


    parser = configparser.ConfigParser(
        interpolation=None,
        strict=False,
    )

    parser.optionxform = str


    try:
        parser.read(
            ini,
            encoding="utf-8"
        )

    except Exception:
        return values


    section = next(
        (
            s
            for s in parser.sections()
            if s.casefold()
            ==
            "pincabos.rawscore"
        ),
        None
    )


    if not section:
        return values


    options = {
        key.casefold(): value
        for key, value
        in parser.items(section)
    }


    values["auto"] = integer(
        options.get("auto"),
        0
    )

    values["x"] = integer(
        options.get("x"),
        0
    )

    values["y"] = integer(
        options.get("y"),
        0
    )

    values["w"] = max(
        1,
        integer(
            options.get("width"),
            640
        )
    )

    values["h"] = max(
        1,
        integer(
            options.get("height"),
            160
        )
    )


    return values


layout = load_table_layout()


def rawtap_source():

    try:
        lines = RAWTAP_LOG.read_text(
            encoding="utf-8",
            errors="ignore"
        ).splitlines()

    except OSError:
        return "PinMAME"


    for line in reversed(
        lines[-100:]
    ):
        match = re.search(
            r'ACTIVE provider=([^\s]+)',
            line
        )

        if match:
            return match.group(1)


    return "PinMAME"


def write_state():

    RUNTIME_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    source = rawtap_source()

    payload = (
        f"PID={VPX_PID}\n"
        f"ENABLED=1\n"
        f"AUTO={1 if layout['auto'] else 0}\n"
        f"X={layout['x']}\n"
        f"Y={layout['y']}\n"
        f"W={layout['w']}\n"
        f"H={layout['h']}\n"
        f"OVERRIDE=1\n"
        f"BACKEND=RAWSCORE\n"
        f"SOURCE={source}\n"
    )

    temporary = STATE_FILE.with_name(
        f"state.env.tmp.{os.getpid()}"
    )

    temporary.write_text(
        payload,
        encoding="utf-8",
    )

    os.chmod(
        temporary,
        0o660
    )

    os.replace(
        temporary,
        STATE_FILE
    )


def remove_if_ours(path):

    if not path.exists():
        return

    if path == STATE_FILE:

        state = read_env(
            STATE_FILE
        )

        if integer(
            state.get("PID"),
            -1
        ) != VPX_PID:
            return


    try:
        path.unlink()

    except OSError:
        pass


def cleanup_runtime():

    remove_if_ours(
        STATE_FILE
    )

    remove_if_ours(
        COMMAND_FILE
    )

    for path in (
        FRAME,
        TEMP_FRAME,
        PIDFILE,
    ):
        try:
            path.unlink()

        except FileNotFoundError:
            pass

        except OSError:
            pass


atexit.register(
    cleanup_runtime
)


root = tk.Tk()

root.title(
    "PinCabOS PuP Score Overlay"
)

root.configure(
    background="black"
)

root.overrideredirect(
    True
)

try:
    root.attributes(
        "-topmost",
        True
    )

except tk.TclError:
    pass


def apply_geometry():

    absolute_x = (
        SCREEN["x"]
        +
        layout["x"]
    )

    absolute_y = (
        SCREEN["y"]
        +
        layout["y"]
    )

    root.geometry(
        f"{layout['w']}x{layout['h']}"
        f"+{absolute_x}+{absolute_y}"
    )


apply_geometry()


label = tk.Label(
    root,
    background="black",
    borderwidth=0,
    highlightthickness=0,
)

label.pack(
    fill="both",
    expand=True
)


current_image = None
last_frame_stamp = None
last_command_stamp = None
last_source = None
last_state_write = 0.0


def handle_command():

    global last_command_stamp


    try:
        stamp = COMMAND_FILE.stat().st_mtime_ns

    except FileNotFoundError:
        return


    if stamp == last_command_stamp:
        return


    command = read_env(
        COMMAND_FILE
    )


    if integer(
        command.get("PID"),
        -1
    ) != VPX_PID:
        return


    last_command_stamp = stamp


    layout["auto"] = (
        1
        if integer(
            command.get("AUTO"),
            0
        )
        else 0
    )

    layout["x"] = max(
        0,
        integer(
            command.get("X"),
            layout["x"]
        )
    )

    layout["y"] = max(
        0,
        integer(
            command.get("Y"),
            layout["y"]
        )
    )

    layout["w"] = max(
        1,
        integer(
            command.get("W"),
            layout["w"]
        )
    )

    layout["h"] = max(
        1,
        integer(
            command.get("H"),
            layout["h"]
        )
    )


    apply_geometry()

    write_state()


def update_frame():

    global current_image
    global last_frame_stamp


    try:
        stamp = FRAME.stat().st_mtime_ns

    except FileNotFoundError:
        return


    if stamp == last_frame_stamp:
        return


    try:
        with Image.open(
            FRAME
        ) as source:

            image = source.convert(
                "RGB"
            )

            if image.size != (
                layout["w"],
                layout["h"],
            ):
                image = image.resize(
                    (
                        layout["w"],
                        layout["h"],
                    ),
                    Image.Resampling.NEAREST,
                )


            current_image = (
                ImageTk.PhotoImage(
                    image
                )
            )


        label.configure(
            image=current_image
        )

        last_frame_stamp = stamp

    except Exception:
        pass


def refresh():

    global last_source
    global last_state_write


    if not pid_alive(
        VPX_PID
    ):
        cleanup_runtime()

        root.destroy()
        return


    handle_command()
    update_frame()


    source = rawtap_source()
    now = time.monotonic()


    if (
        source != last_source
        or
        now - last_state_write >= 1.0
    ):
        last_source = source
        last_state_write = now

        write_state()


    try:
        root.lift()

        root.attributes(
            "-topmost",
            True
        )

    except tk.TclError:
        pass


    root.after(
        16,
        refresh
    )


write_state()

root.after(
    10,
    refresh
)

root.mainloop()
