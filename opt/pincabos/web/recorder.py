#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PinCabOS recorder.py
====================

Moteur autonome de capture automatique des médias d'une table VPX.

Fonctions V1:
- une ou plusieurs tables (--table répété)
- lancement via le launcher officiel PinCabOS / VPinFE
- détection automatique Original / PuP / Hybrid sans laisser le chooser bloquer le batch
- attente configurable APRÈS apparition de la fenêtre VPX
- capture Playfield / Backglass / FullDMD / Topper
- image PNG ou vidéo MP4
- qualité vidéo prédéfinie
- NVENC automatique si disponible, sinon libx264
- capture simultanée des écrans sélectionnés
- validation ffprobe avant remplacement
- backup des médias existants
- remplacement atomique
- journal par table
- fermeture propre/forcée du VPX lancé par recorder.py
- mode --no-launch pour tester sur une table déjà ouverte
- mode --dry-run

Exemples:
  sudo -u pinball /opt/pincabos/web/.venv/bin/python /opt/pincabos/web/recorder.py \
      --table "/home/pinball/Tables/Attack from Mars/Attack from Mars.vpx" \
      --screens playfield,backglass,fulldmd \
      --type image \
      --wait 20

  sudo -u pinball /opt/pincabos/web/.venv/bin/python /opt/pincabos/web/recorder.py \
      --table "/home/pinball/Tables/Attack from Mars/Attack from Mars.vpx" \
      --screens playfield,backglass,fulldmd,topper \
      --type video \
      --wait 20 \
      --duration 12 \
      --fps 30 \
      --quality high

IMPORTANT:
- Le dossier média ciblé est: <dossier table>/medias
- Noms PinCabOS/VPinFE:
    playfield -> table.png / table.mp4
    backglass -> bg.png / bg.mp4
    fulldmd   -> dmd.png / dmd.mp4
    topper    -> topper.png / topper.mp4
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


VERSION = "1.0.0"

TABLES_ROOT = Path("/home/pinball/Tables")
SCREEN_CONFIG = Path("/opt/pincabos/config/screens/screens.json")
VPX_LAUNCHER = Path("/opt/pincabos/bin/vpx-lowlatency.sh")
MODE_DETECTOR = Path("/opt/pincabos/launchers/pincabos-detect-table-modes.py")

DISPLAY = os.environ.get("DISPLAY", ":0")
XAUTHORITY = os.environ.get("XAUTHORITY", "/home/pinball/.Xauthority")
PINBALL_HOME = Path("/home/pinball")

VALID_SCREENS = ("playfield", "backglass", "fulldmd", "topper")

MEDIA_BASENAME = {
    "playfield": "table",
    "backglass": "bg",
    "fulldmd": "dmd",
    "topper": "topper",
}

WINDOW_PATTERNS = {
    "playfield": (
        r"PinCabOs Visual Pinball Player",
        r"Visual Pinball Player",
    ),
    "backglass": (
        r"PinCabOs Visual Pinball Backglass",
        r"Visual Pinball Backglass",
    ),
    "fulldmd": (
        r"PinCabOs Visual Pinball Score View",
        r"Visual Pinball Score View",
        r"Score View",
    ),
    "topper": (
        r"PinCabOs Visual Pinball Topper",
        r"Visual Pinball Topper",
    ),
}

QUALITY_X264_CRF = {
    "low": 30,
    "medium": 25,
    "high": 20,
    "max": 16,
}

QUALITY_NVENC_CQ = {
    "low": 30,
    "medium": 25,
    "high": 20,
    "max": 16,
}


class RecorderError(RuntimeError):
    pass


@dataclass(frozen=True)
class Geometry:
    x: int
    y: int
    width: int
    height: int
    output: str = ""


@dataclass(frozen=True)
class WindowInfo:
    window_id: str
    desktop: str
    x: int
    y: int
    width: int
    height: int
    wm_class: str
    title: str


@dataclass(frozen=True)
class CaptureSource:
    role: str
    kind: str  # screen | window
    geometry: Geometry | None = None
    window: WindowInfo | None = None

    @property
    def description(self) -> str:
        if self.kind == "window" and self.window:
            return (
                f"window {self.window.window_id} "
                f"{self.window.width}x{self.window.height} "
                f"'{self.window.title}'"
            )
        if self.kind == "screen" and self.geometry:
            g = self.geometry
            return f"screen {g.output or '?'} {g.width}x{g.height}+{g.x}+{g.y}"
        return self.kind


def setup_logging(verbose: bool) -> logging.Logger:
    logger = logging.getLogger("pincabos-recorder")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
    logger.addHandler(handler)
    return logger


LOG = setup_logging(False)


def now_stamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def ensure_command(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RecorderError(f"Commande requise absente: {name}")
    return path


def run(
    cmd: Sequence[str],
    *,
    timeout: float = 30,
    check: bool = False,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    LOG.debug("CMD: %s", shlex.join(str(x) for x in cmd))
    proc = subprocess.run(
        [str(x) for x in cmd],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        env=env,
    )
    if check and proc.returncode != 0:
        raise RecorderError(
            f"Commande échouée ({proc.returncode}): {shlex.join(str(x) for x in cmd)}\n"
            f"{proc.stdout[-4000:]}"
        )
    return proc


def atomic_json_write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass


def table_log_path(table: Path) -> Path:
    return table.parent / "logs" / "media-capture" / "recorder.log"


def append_table_log(table: Path, message: str) -> None:
    try:
        path = table_log_path(table)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    except OSError:
        pass


def normalize_table(value: str) -> Path:
    path = Path(value).expanduser()

    if path.is_dir():
        candidates = sorted(
            (p for p in path.iterdir() if p.is_file() and p.suffix.casefold() == ".vpx"),
            key=lambda p: p.name.casefold(),
        )
        if len(candidates) == 1:
            path = candidates[0]
        elif not candidates:
            raise RecorderError(f"Aucune table .vpx dans: {path}")
        else:
            raise RecorderError(
                f"Plusieurs .vpx dans {path}; donne le fichier exact avec --table."
            )

    try:
        path = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise RecorderError(f"Table introuvable: {path}") from exc

    if not path.is_file() or path.suffix.casefold() != ".vpx":
        raise RecorderError(f"Ce n'est pas une table VPX: {path}")

    try:
        path.relative_to(TABLES_ROOT.resolve())
    except Exception:
        LOG.warning("Table hors de %s: %s", TABLES_ROOT, path)

    return path


def parse_screens(value: str) -> list[str]:
    raw = [part.strip().casefold() for part in value.split(",") if part.strip()]
    if not raw:
        raise RecorderError("Aucun écran sélectionné.")

    unknown = [item for item in raw if item not in VALID_SCREENS]
    if unknown:
        raise RecorderError(
            f"Écran(s) invalide(s): {', '.join(unknown)}. "
            f"Valeurs: {', '.join(VALID_SCREENS)}"
        )

    out: list[str] = []
    for item in raw:
        if item not in out:
            out.append(item)
    return out


def load_screen_config() -> dict:
    try:
        data = json.loads(SCREEN_CONFIG.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


XRANDR_LINE_RE = re.compile(
    r"^([A-Za-z0-9_.:-]+)\s+connected(?:\s+primary)?\s+"
    r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)"
)


def xrandr_geometries() -> dict[str, Geometry]:
    env = os.environ.copy()
    env["DISPLAY"] = DISPLAY
    env["XAUTHORITY"] = XAUTHORITY

    proc = run(["xrandr", "--query"], timeout=15, env=env)
    if proc.returncode != 0:
        raise RecorderError(f"xrandr a échoué:\n{proc.stdout}")

    result: dict[str, Geometry] = {}
    for line in proc.stdout.splitlines():
        match = XRANDR_LINE_RE.match(line)
        if not match:
            continue
        output, width, height, x, y = match.groups()
        result[output] = Geometry(
            x=int(x),
            y=int(y),
            width=int(width),
            height=int(height),
            output=output,
        )
    return result


def role_screen_geometry(role: str) -> Geometry | None:
    if role == "topper":
        return None

    cfg = load_screen_config()
    roles = cfg.get("roles")
    if not isinstance(roles, dict):
        return None

    role_data = roles.get(role)
    if not isinstance(role_data, dict):
        return None

    output = str(role_data.get("output") or "").strip()
    if not output:
        return None

    geoms = xrandr_geometries()
    return geoms.get(output)


def list_windows() -> list[WindowInfo]:
    env = os.environ.copy()
    env["DISPLAY"] = DISPLAY
    env["XAUTHORITY"] = XAUTHORITY

    proc = run(["wmctrl", "-lGx"], timeout=10, env=env)
    if proc.returncode != 0:
        return []

    windows: list[WindowInfo] = []
    for raw_line in proc.stdout.splitlines():
        # Format observé sur PinCabOS:
        # ID DESKTOP X Y W H WM_CLASS TITLE...
        parts = raw_line.strip().split(None, 7)
        if len(parts) < 8:
            continue

        wid, desktop, x, y, width, height, wm_class, title = parts
        if not re.fullmatch(r"0x[0-9A-Fa-f]+", wid):
            continue

        try:
            windows.append(
                WindowInfo(
                    window_id=wid,
                    desktop=desktop,
                    x=int(x),
                    y=int(y),
                    width=int(width),
                    height=int(height),
                    wm_class=wm_class,
                    title=title.strip(),
                )
            )
        except ValueError:
            continue

    return windows


def find_window(role: str, windows: Iterable[WindowInfo] | None = None) -> WindowInfo | None:
    if windows is None:
        windows = list_windows()

    candidates: list[tuple[int, WindowInfo]] = []
    patterns = WINDOW_PATTERNS[role]

    for window in windows:
        blob = f"{window.wm_class} {window.title}"
        for rank, pattern in enumerate(patterns):
            if re.search(pattern, blob, flags=re.IGNORECASE):
                # pattern le plus précis + plus grande fenêtre
                score = (len(patterns) - rank) * 10_000_000 + window.width * window.height
                candidates.append((score, window))
                break

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def resolve_capture_sources(
    roles: Sequence[str],
    source_mode: str,
) -> dict[str, CaptureSource]:
    """
    Résout toutes les sources en un seul passage.

    Important pour un cab NVIDIA:
    - un seul xrandr
    - un seul wmctrl
    - cette fonction doit être appelée AVANT l'attente de capture afin que
      l'enregistrement ne commence pas immédiatement après un probe X11.
    """
    cfg = load_screen_config()

    # PinCabOS supporte deux formats de screens.json:
    #
    # Ancien:
    #   {
    #     "roles": {
    #       "playfield": {"output": "HDMI-0"}
    #     }
    #   }
    #
    # Actuel:
    #   {
    #     "playfield": {
    #       "name": "HDMI-0",
    #       "x": 0,
    #       "y": 0,
    #       "width": 3840,
    #       "height": 2160
    #     }
    #   }
    #
    cfg_roles = cfg.get("roles")
    if not isinstance(cfg_roles, dict):
        cfg_roles = {}

    geoms: dict[str, Geometry] = {}
    if source_mode != "window":
        try:
            geoms = xrandr_geometries()
        except Exception as exc:
            LOG.debug("xrandr groupé indisponible: %s", exc)

    windows: list[WindowInfo] = []
    if source_mode != "screen" or "topper" in roles:
        try:
            windows = list_windows()
        except Exception as exc:
            LOG.debug("wmctrl groupé indisponible: %s", exc)

    resolved: dict[str, CaptureSource] = {}

    for role in roles:
        geometry: Geometry | None = None
        window = find_window(role, windows)

        if role != "topper":
            # Ancien format: roles.<role>.output
            role_data = cfg_roles.get(role)

            # Nouveau format PinCabOS:
            # playfield.name / backglass.name / fulldmd.name
            if not isinstance(role_data, dict):
                candidate = cfg.get(role)
                if isinstance(candidate, dict):
                    role_data = candidate

            if isinstance(role_data, dict):
                output = str(
                    role_data.get("output")
                    or role_data.get("name")
                    or ""
                ).strip()

                if output:
                    geometry = geoms.get(output)

                # Fallback direct sur la geometrie mémorisée.
                # Très utile si xrandr change son ordre d'énumération.
                if geometry is None:
                    try:
                        x = int(role_data.get("x"))
                        y = int(role_data.get("y"))
                        width = int(role_data.get("width"))
                        height = int(role_data.get("height"))

                        if width > 0 and height > 0:
                            geometry = Geometry(
                                x=x,
                                y=y,
                                width=width,
                                height=height,
                                output=output,
                            )
                    except (TypeError, ValueError):
                        pass

        if source_mode == "screen":
            if geometry:
                resolved[role] = CaptureSource(
                    role=role,
                    kind="screen",
                    geometry=geometry,
                )
                continue
            if role == "topper" and window:
                resolved[role] = CaptureSource(
                    role=role,
                    kind="window",
                    window=window,
                )
                continue
            raise RecorderError(f"Aucun écran configuré/résolu pour {role}.")

        if source_mode == "window":
            if window:
                resolved[role] = CaptureSource(
                    role=role,
                    kind="window",
                    window=window,
                )
                continue
            raise RecorderError(f"Aucune fenêtre VPX trouvée pour {role}.")

        # auto
        if role == "topper":
            if window:
                resolved[role] = CaptureSource(
                    role=role,
                    kind="window",
                    window=window,
                )
                continue
            if geometry:
                resolved[role] = CaptureSource(
                    role=role,
                    kind="screen",
                    geometry=geometry,
                )
                continue
        else:
            if geometry:
                resolved[role] = CaptureSource(
                    role=role,
                    kind="screen",
                    geometry=geometry,
                )
                continue
            if window:
                resolved[role] = CaptureSource(
                    role=role,
                    kind="window",
                    window=window,
                )
                continue

        raise RecorderError(f"Aucune source de capture trouvée pour {role}.")

    return resolved


def resolve_capture_source(role: str, source_mode: str) -> CaptureSource:
    """
    auto:
      - playfield/backglass/fulldmd: écran physique configuré d'abord
      - topper: fenêtre VPX d'abord
      - fallback fenêtre / écran selon disponibilité

    Ce choix donne pour FullDMD la composition réellement visible sur l'écran,
    incluant le fond + Score View/overlay si présent.
    """
    geometry = None
    window = None

    try:
        geometry = role_screen_geometry(role)
    except Exception as exc:
        LOG.debug("Géométrie écran %s indisponible: %s", role, exc)

    try:
        window = find_window(role)
    except Exception as exc:
        LOG.debug("Fenêtre %s indisponible: %s", role, exc)

    if source_mode == "screen":
        if geometry:
            return CaptureSource(role=role, kind="screen", geometry=geometry)
        if role == "topper" and window:
            return CaptureSource(role=role, kind="window", window=window)
        raise RecorderError(f"Aucun écran configuré/résolu pour {role}.")

    if source_mode == "window":
        if window:
            return CaptureSource(role=role, kind="window", window=window)
        raise RecorderError(f"Aucune fenêtre VPX trouvée pour {role}.")

    # auto
    if role == "topper":
        if window:
            return CaptureSource(role=role, kind="window", window=window)
        if geometry:
            return CaptureSource(role=role, kind="screen", geometry=geometry)
    else:
        if geometry:
            return CaptureSource(role=role, kind="screen", geometry=geometry)
        if window:
            return CaptureSource(role=role, kind="window", window=window)

    raise RecorderError(f"Aucune source de capture trouvée pour {role}.")


def detector_info(table: Path) -> dict:
    if not MODE_DETECTOR.is_file():
        return {
            "detected_mode": "original",
            "default": "original",
            "original_available": True,
            "pup_available": False,
        }

    proc = run([sys.executable, str(MODE_DETECTOR), str(table)], timeout=30)
    if proc.returncode != 0:
        raise RecorderError(
            f"Détection Original/PuP impossible pour {table.name}:\n{proc.stdout[-3000:]}"
        )

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RecorderError(f"Réponse invalide du détecteur pour {table.name}") from exc

    return data if isinstance(data, dict) else {}


def choose_game_mode(table: Path, requested: str) -> str:
    info = detector_info(table)
    original_ok = bool(info.get("original_available"))
    pup_ok = bool(info.get("pup_available"))
    detected = str(info.get("detected_mode") or "original")
    default = str(info.get("default") or "original")
    default = "pup" if default.startswith("pup") else "original"

    if requested == "original":
        if not original_ok:
            raise RecorderError(f"{table.name}: mode Original non disponible.")
        return "original"

    if requested == "pup":
        if not pup_ok:
            raise RecorderError(f"{table.name}: mode PuP non disponible.")
        return "pup"

    # auto sans interaction: on ne doit jamais laisser le chooser bloquer un batch.
    if detected == "hybrid":
        if default == "pup" and pup_ok:
            return "pup"
        if original_ok:
            return "original"
        return "pup"

    if detected == "pup":
        return "pup"

    return "original"


def launcher_environment(mode: str) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(PINBALL_HOME),
            "USER": "pinball",
            "LOGNAME": "pinball",
            "DISPLAY": DISPLAY,
            "XAUTHORITY": XAUTHORITY,
            "PINCABOS_HYBRID_FORCE_CHOICE": mode,
        }
    )

    try:
        uid = int(run(["id", "-u", "pinball"], timeout=5, check=True).stdout.strip())
        env["XDG_RUNTIME_DIR"] = f"/run/user/{uid}"
    except Exception:
        env.setdefault("XDG_RUNTIME_DIR", "/run/user/1000")

    return env


def launch_table(table: Path, mode: str) -> subprocess.Popen[str]:
    if not VPX_LAUNCHER.is_file():
        raise RecorderError(f"Launcher PinCabOS absent: {VPX_LAUNCHER}")

    env = launcher_environment(mode)

    if os.geteuid() == 0:
        cmd = [
            "runuser",
            "-u",
            "pinball",
            "--",
            "env",
            f"HOME={env['HOME']}",
            f"USER={env['USER']}",
            f"LOGNAME={env['LOGNAME']}",
            f"DISPLAY={env['DISPLAY']}",
            f"XAUTHORITY={env['XAUTHORITY']}",
            f"XDG_RUNTIME_DIR={env['XDG_RUNTIME_DIR']}",
            f"PINCABOS_HYBRID_FORCE_CHOICE={mode}",
            str(VPX_LAUNCHER),
            str(table),
        ]
        popen_env = os.environ.copy()
    else:
        cmd = [str(VPX_LAUNCHER), str(table)]
        popen_env = env

    LOG.info("Lancement %s [%s]", table.name, mode)
    append_table_log(table, f"START mode={mode} launcher={shlex.join(cmd)}")

    launch_log = (
        table.parent
        / "logs"
        / "media-capture"
        / f"vpx-launch-{now_stamp()}.log"
    )
    launch_log.parent.mkdir(parents=True, exist_ok=True)
    launch_handle = launch_log.open("w", encoding="utf-8")

    proc = subprocess.Popen(
        cmd,
        stdout=launch_handle,
        stderr=subprocess.STDOUT,
        text=True,
        env=popen_env,
        start_new_session=True,
    )
    setattr(proc, "_pincabos_launch_log", launch_log)
    setattr(proc, "_pincabos_launch_handle", launch_handle)
    return proc


def wait_for_vpx_ready(
    proc: subprocess.Popen[str] | None,
    *,
    timeout: float,
) -> WindowInfo:
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if proc is not None and proc.poll() is not None:
            output = ""
            try:
                log_path = getattr(proc, "_pincabos_launch_log", None)
                if log_path:
                    output = Path(log_path).read_text(
                        encoding="utf-8",
                        errors="replace",
                    )[-4000:]
            except Exception:
                pass
            raise RecorderError(
                f"VPX s'est fermé avant d'être prêt (code {proc.returncode}).\n{output}"
            )

        player = find_window("playfield")
        if player and player.width >= 320 and player.height >= 240:
            return player

        time.sleep(0.5)

    raise RecorderError(
        f"Timeout: fenêtre Playfield VPX non détectée après {timeout:.0f} secondes."
    )


def ffmpeg_has_encoder(encoder: str) -> bool:
    proc = run(["ffmpeg", "-hide_banner", "-encoders"], timeout=20)
    return proc.returncode == 0 and re.search(
        rf"^\s*[A-Z.]+\s+{re.escape(encoder)}\s",
        proc.stdout,
        flags=re.MULTILINE,
    ) is not None


def select_encoder(requested: str) -> str:
    if requested == "x264":
        if not ffmpeg_has_encoder("libx264"):
            raise RecorderError("Encodeur libx264 absent de ffmpeg.")
        return "libx264"

    if requested == "nvenc":
        if not ffmpeg_has_encoder("h264_nvenc"):
            raise RecorderError("Encodeur h264_nvenc absent de ffmpeg.")
        return "h264_nvenc"

    if ffmpeg_has_encoder("h264_nvenc"):
        return "h264_nvenc"
    if ffmpeg_has_encoder("libx264"):
        return "libx264"

    raise RecorderError("Aucun encodeur H.264 utilisable (h264_nvenc/libx264).")


def x11_input_args(source: CaptureSource, fps: int) -> list[str]:
    args = [
        "-f",
        "x11grab",
        "-draw_mouse",
        "0",
        "-framerate",
        str(fps),
    ]

    if source.kind == "window" and source.window:
        args += [
            "-window_id",
            source.window.window_id,
            "-i",
            DISPLAY,
        ]
        return args

    if source.kind == "screen" and source.geometry:
        g = source.geometry
        args += [
            "-video_size",
            f"{g.width}x{g.height}",
            "-i",
            f"{DISPLAY}+{g.x},{g.y}",
        ]
        return args

    raise RecorderError(f"Source X11 invalide pour {source.role}")


def ffmpeg_capture_command(
    source: CaptureSource,
    temp_file: Path,
    *,
    media_type: str,
    duration: float,
    fps: int,
    quality: str,
    encoder: str,
) -> list[str]:
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-nostdin",
        "-loglevel",
        "error",
    ]

    cmd += x11_input_args(source, 1 if media_type == "image" else fps)

    if media_type == "image":
        cmd += [
            "-frames:v",
            "1",
            "-c:v",
            "png",
            "-compression_level",
            "4",
            str(temp_file),
        ]
        return cmd

    if encoder == "h264_nvenc":
        cmd += [
            "-t",
            f"{duration:.3f}",
            "-an",
            "-c:v",
            "h264_nvenc",
            "-preset",
            "p4",
            "-rc",
            "vbr",
            "-cq",
            str(QUALITY_NVENC_CQ[quality]),
            "-b:v",
            "0",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(temp_file),
        ]
    else:
        cmd += [
            "-t",
            f"{duration:.3f}",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            str(QUALITY_X264_CRF[quality]),
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(temp_file),
        ]

    return cmd


def probe_media(path: Path) -> dict:
    proc = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,width,height,nb_frames",
            "-of",
            "json",
            str(path),
        ],
        timeout=30,
    )
    if proc.returncode != 0:
        raise RecorderError(f"ffprobe refuse {path.name}:\n{proc.stdout[-2000:]}")

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RecorderError(f"ffprobe JSON invalide pour {path.name}") from exc

    return data


def validate_capture(
    path: Path,
    *,
    media_type: str,
    expected_duration: float,
) -> dict:
    if not path.is_file():
        raise RecorderError(f"Capture absente: {path}")
    if path.stat().st_size < 1024:
        raise RecorderError(f"Capture trop petite/invalide: {path} ({path.stat().st_size} octets)")

    data = probe_media(path)
    streams = data.get("streams")
    if not isinstance(streams, list):
        streams = []

    video = next(
        (
            stream
            for stream in streams
            if isinstance(stream, dict) and stream.get("codec_type") == "video"
        ),
        None,
    )
    if not video:
        raise RecorderError(f"Aucun flux vidéo/image valide dans {path.name}")

    width = int(video.get("width") or 0)
    height = int(video.get("height") or 0)
    if width < 32 or height < 32:
        raise RecorderError(f"Résolution invalide {width}x{height} pour {path.name}")

    duration = 0.0
    try:
        duration = float((data.get("format") or {}).get("duration") or 0.0)
    except Exception:
        duration = 0.0

    if media_type == "video" and expected_duration > 0:
        minimum = max(1.0, expected_duration * 0.75)
        if duration and duration < minimum:
            raise RecorderError(
                f"Vidéo trop courte: {duration:.2f}s < minimum {minimum:.2f}s ({path.name})"
            )

    return {
        "width": width,
        "height": height,
        "duration": duration,
        "size": path.stat().st_size,
    }


def media_target(table: Path, role: str, media_type: str) -> Path:
    ext = ".png" if media_type == "image" else ".mp4"
    return table.parent / "medias" / f"{MEDIA_BASENAME[role]}{ext}"


def counterpart_candidates(table: Path, role: str, media_type: str) -> list[Path]:
    media_dir = table.parent / "medias"
    base = MEDIA_BASENAME[role]

    if media_type == "image":
        return [
            media_dir / f"{base}.mp4",
            media_dir / f"{base}.webm",
            media_dir / f"{base}.mkv",
            media_dir / f"{base}.avi",
        ]

    return [
        media_dir / f"{base}.png",
        media_dir / f"{base}.jpg",
        media_dir / f"{base}.jpeg",
        media_dir / f"{base}.webp",
    ]


def backup_existing(
    table: Path,
    files: Iterable[Path],
    *,
    stamp: str,
) -> list[Path]:
    existing = [path for path in files if path.is_file()]
    if not existing:
        return []

    backup_dir = (
        table.parent
        / "logs"
        / "media-capture"
        / "backups"
        / stamp
    )
    backup_dir.mkdir(parents=True, exist_ok=True)

    backed_up: list[Path] = []
    for path in existing:
        destination = backup_dir / path.name
        shutil.copy2(path, destination)
        backed_up.append(destination)
        LOG.info("Backup: %s -> %s", path.name, destination)

    return backed_up


def install_capture(
    table: Path,
    role: str,
    temp_file: Path,
    *,
    media_type: str,
    backup: bool,
    keep_other_type: bool,
    stamp: str,
) -> Path:
    target = media_target(table, role, media_type)
    target.parent.mkdir(parents=True, exist_ok=True)

    candidates = [target]
    if not keep_other_type:
        candidates.extend(counterpart_candidates(table, role, media_type))

    if backup:
        backup_existing(table, candidates, stamp=stamp)

    # Temp déjà dans le dossier medias si possible: os.replace reste atomique.
    os.replace(temp_file, target)

    if not keep_other_type:
        for path in counterpart_candidates(table, role, media_type):
            if path != target:
                try:
                    path.unlink()
                    LOG.info("Ancien format retiré: %s", path)
                except FileNotFoundError:
                    pass

    return target


def create_temp_capture_path(table: Path, role: str, media_type: str) -> Path:
    media_dir = table.parent / "medias"
    media_dir.mkdir(parents=True, exist_ok=True)
    suffix = ".png" if media_type == "image" else ".mp4"

    fd, temp_name = tempfile.mkstemp(
        prefix=f".recorder-{role}-",
        suffix=suffix,
        dir=str(media_dir),
    )
    os.close(fd)
    path = Path(temp_name)
    # ffmpeg -y doit pouvoir créer le fichier depuis zéro.
    path.unlink(missing_ok=True)
    return path


def terminate_launched_table(proc: subprocess.Popen[str] | None, timeout: float = 12.0) -> None:
    if proc is None or proc.poll() is not None:
        return

    LOG.info("Fermeture de la table lancée par recorder.py...")
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except Exception as exc:
        LOG.warning("SIGTERM process-group impossible: %s", exc)
        try:
            proc.terminate()
        except Exception:
            pass

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return
        time.sleep(0.25)

    LOG.warning("VPX ne s'est pas fermé; SIGKILL du groupe lancé par recorder.py.")
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    finally:
        handle = getattr(proc, "_pincabos_launch_handle", None)
        if handle and not handle.closed:
            handle.close()


def capture_selected(
    table: Path,
    screens: list[str],
    *,
    media_type: str,
    duration: float,
    fps: int,
    quality: str,
    source_mode: str,
    encoder: str,
    backup: bool,
    keep_other_type: bool,
    dry_run: bool,
    resolved_sources: dict[str, CaptureSource] | None = None,
) -> dict:
    stamp = now_stamp()
    sources = resolved_sources or resolve_capture_sources(screens, source_mode)

    for role in screens:
        source = sources[role]
        LOG.info("%s -> %s", role, source.description)

    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "sources": {role: src.description for role, src in sources.items()},
        }

    temp_files: dict[str, Path] = {}
    processes: dict[str, subprocess.Popen[str]] = {}
    stderr_files: dict[str, Path] = {}

    try:
        for role, source in sources.items():
            temp_file = create_temp_capture_path(table, role, media_type)
            stderr_file = temp_file.with_suffix(temp_file.suffix + ".ffmpeg.log")
            temp_files[role] = temp_file
            stderr_files[role] = stderr_file

            cmd = ffmpeg_capture_command(
                source,
                temp_file,
                media_type=media_type,
                duration=duration,
                fps=fps,
                quality=quality,
                encoder=encoder,
            )
            LOG.debug("%s ffmpeg: %s", role, shlex.join(cmd))
            log_handle = stderr_file.open("w", encoding="utf-8")
            capture_env = os.environ.copy()
            capture_env["DISPLAY"] = DISPLAY
            capture_env["XAUTHORITY"] = XAUTHORITY

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=log_handle,
                text=True,
                env=capture_env,
                start_new_session=True,
            )
            # On garde la référence sur le handle via l'objet pour fermeture plus bas.
            setattr(proc, "_pincabos_log_handle", log_handle)
            processes[role] = proc

        failed: list[str] = []
        for role, proc in processes.items():
            rc = proc.wait(timeout=max(30.0, duration + 30.0))
            handle = getattr(proc, "_pincabos_log_handle", None)
            if handle:
                handle.close()

            if rc != 0:
                detail = ""
                try:
                    detail = stderr_files[role].read_text(errors="replace")[-3000:]
                except Exception:
                    pass
                failed.append(f"{role}: ffmpeg rc={rc}\n{detail}")

        if failed:
            raise RecorderError("Échec capture:\n" + "\n".join(failed))

        validation: dict[str, dict] = {}
        for role, path in temp_files.items():
            validation[role] = validate_capture(
                path,
                media_type=media_type,
                expected_duration=duration,
            )
            info = validation[role]
            LOG.info(
                "%s validé: %sx%s %.2fs %.1f MiB",
                role,
                info["width"],
                info["height"],
                info["duration"],
                info["size"] / 1024 / 1024,
            )

        installed: dict[str, str] = {}
        for role, path in temp_files.items():
            target = install_capture(
                table,
                role,
                path,
                media_type=media_type,
                backup=backup,
                keep_other_type=keep_other_type,
                stamp=stamp,
            )
            installed[role] = str(target)
            LOG.info("INSTALLÉ %s -> %s", role, target)

        return {
            "ok": True,
            "table": str(table),
            "type": media_type,
            "installed": installed,
            "validation": validation,
            "sources": {role: src.description for role, src in sources.items()},
        }

    finally:
        for proc in processes.values():
            if proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except Exception:
                    try:
                        proc.terminate()
                    except Exception:
                        pass
            handle = getattr(proc, "_pincabos_log_handle", None)
            if handle and not handle.closed:
                handle.close()

        for path in temp_files.values():
            try:
                path.unlink()
            except FileNotFoundError:
                pass

        for path in stderr_files.values():
            try:
                path.unlink()
            except FileNotFoundError:
                pass


def process_table(table: Path, args: argparse.Namespace, encoder: str) -> dict:
    start = time.monotonic()
    proc: subprocess.Popen[str] | None = None

    append_table_log(
        table,
        (
            f"JOB type={args.media_type} screens={','.join(args.screens_list)} "
            f"wait={args.wait} duration={args.duration} fps={args.fps} "
            f"quality={args.quality} source={args.source}"
        ),
    )

    try:
        if args.no_launch:
            LOG.info("%s: --no-launch, utilisation du VPX déjà ouvert.", table.name)
            wait_for_vpx_ready(None, timeout=args.launch_timeout)
            mode = "existing"
        else:
            mode = choose_game_mode(table, args.mode)
            proc = launch_table(table, mode)
            wait_for_vpx_ready(proc, timeout=args.launch_timeout)

        # Résolution X11 AVANT l'attente:
        # évite qu'un probe xrandr tombe juste au début de la vidéo.
        resolved_sources = resolve_capture_sources(
            args.screens_list,
            args.source,
        )
        for role in args.screens_list:
            LOG.info(
                "Source préparée %s -> %s",
                role,
                resolved_sources[role].description,
            )

        LOG.info("VPX prêt. Attente capture: %.1f seconde(s)", args.wait)
        if not args.dry_run and args.wait > 0:
            deadline = time.monotonic() + args.wait
            while time.monotonic() < deadline:
                if proc is not None and proc.poll() is not None:
                    raise RecorderError(
                        f"{table.name}: VPX s'est fermé pendant l'attente avant capture."
                    )
                time.sleep(min(0.5, max(0.05, deadline - time.monotonic())))

        result = capture_selected(
            table,
            args.screens_list,
            media_type=args.media_type,
            duration=args.duration,
            fps=args.fps,
            quality=args.quality,
            source_mode=args.source,
            encoder=encoder,
            backup=not args.no_backup,
            keep_other_type=args.keep_other_type,
            dry_run=args.dry_run,
            resolved_sources=resolved_sources,
        )
        result["mode"] = mode
        result["elapsed"] = round(time.monotonic() - start, 3)
        append_table_log(table, f"GO {json.dumps(result, ensure_ascii=False)}")
        return result

    except Exception as exc:
        append_table_log(table, f"NOGO {type(exc).__name__}: {exc}")
        raise

    finally:
        if proc is not None and not args.keep_vpx_open:
            terminate_launched_table(proc)

        if proc is not None:
            handle = getattr(proc, "_pincabos_launch_handle", None)
            if handle and not handle.closed:
                handle.close()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PinCabOS - capture automatique des médias VPX",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--table",
        action="append",
        default=[],
        help="Table .vpx à traiter. Peut être répété.",
    )
    parser.add_argument(
        "--tables-file",
        help="Fichier texte contenant un chemin .vpx par ligne.",
    )
    parser.add_argument(
        "--screens",
        default="playfield,backglass,fulldmd",
        help="Liste séparée par virgules: playfield,backglass,fulldmd,topper",
    )
    parser.add_argument(
        "--type",
        dest="media_type",
        choices=("image", "video"),
        default="image",
        help="Type de média créé.",
    )
    parser.add_argument(
        "--wait",
        type=float,
        default=15.0,
        help="Secondes à attendre APRÈS détection de la fenêtre VPX.",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=10.0,
        help="Durée de la vidéo en secondes.",
    )
    parser.add_argument(
        "--fps",
        type=int,
        choices=(15, 24, 25, 30, 50, 60),
        default=30,
        help="Images/seconde pour la vidéo.",
    )
    parser.add_argument(
        "--quality",
        choices=("low", "medium", "high", "max"),
        default="high",
        help="Qualité d'encodage vidéo.",
    )
    parser.add_argument(
        "--encoder",
        choices=("auto", "nvenc", "x264"),
        default="auto",
        help="Encodeur vidéo.",
    )
    parser.add_argument(
        "--source",
        choices=("auto", "screen", "window"),
        default="auto",
        help="Source de capture X11.",
    )
    parser.add_argument(
        "--mode",
        choices=("auto", "original", "pup"),
        default="auto",
        help="Mode de table. auto choisit sans afficher le chooser Hybrid.",
    )
    parser.add_argument(
        "--launch-timeout",
        type=float,
        default=60.0,
        help="Timeout pour détecter la fenêtre VPX.",
    )
    parser.add_argument(
        "--no-launch",
        action="store_true",
        help="Ne lance pas VPX; capture la table actuellement ouverte.",
    )
    parser.add_argument(
        "--keep-vpx-open",
        action="store_true",
        help="Ne ferme pas la table lancée à la fin.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Ne sauvegarde pas les médias remplacés.",
    )
    parser.add_argument(
        "--keep-other-type",
        action="store_true",
        help="Conserve l'ancien média de l'autre type (image/vidéo).",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue avec la table suivante après une erreur.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Résout lancement/sources sans écrire les médias.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Affiche le bilan JSON final.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Logs détaillés.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {VERSION}",
    )

    args = parser.parse_args(argv)

    if args.wait < 0:
        parser.error("--wait doit être >= 0")
    if args.duration <= 0:
        parser.error("--duration doit être > 0")
    if args.launch_timeout <= 0:
        parser.error("--launch-timeout doit être > 0")

    try:
        args.screens_list = parse_screens(args.screens)
    except RecorderError as exc:
        parser.error(str(exc))

    paths = list(args.table)

    if args.tables_file:
        file_path = Path(args.tables_file).expanduser()
        if not file_path.is_file():
            parser.error(f"--tables-file introuvable: {file_path}")
        for line in file_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                paths.append(line)

    if not paths:
        parser.error("Ajoute au moins un --table ou --tables-file.")

    try:
        args.tables = [normalize_table(item) for item in paths]
    except RecorderError as exc:
        parser.error(str(exc))

    # dédoublonnage en gardant l'ordre
    seen: set[str] = set()
    unique_tables: list[Path] = []
    for table in args.tables:
        key = str(table).casefold()
        if key not in seen:
            seen.add(key)
            unique_tables.append(table)
    args.tables = unique_tables

    return args


def preflight(args: argparse.Namespace) -> str:
    ensure_command("ffmpeg")
    ensure_command("ffprobe")
    ensure_command("wmctrl")
    ensure_command("xrandr")

    if not args.no_launch:
        ensure_command("runuser")
        if not VPX_LAUNCHER.is_file():
            raise RecorderError(f"Launcher absent: {VPX_LAUNCHER}")

    if args.media_type == "video":
        encoder = select_encoder(args.encoder)
    else:
        encoder = "png"

    LOG.info("PinCabOS recorder.py %s", VERSION)
    LOG.info("DISPLAY=%s XAUTHORITY=%s", DISPLAY, XAUTHORITY)
    LOG.info("Tables: %d", len(args.tables))
    LOG.info("Écrans: %s", ", ".join(args.screens_list))
    LOG.info("Type: %s", args.media_type)
    if args.media_type == "video":
        LOG.info(
            "Vidéo: %.1fs @ %dfps, qualité=%s, encodeur=%s",
            args.duration,
            args.fps,
            args.quality,
            encoder,
        )
    return encoder


def main(argv: Sequence[str] | None = None) -> int:
    global LOG
    args = parse_args(argv)
    LOG = setup_logging(args.verbose)

    try:
        encoder = preflight(args)
    except Exception as exc:
        LOG.error("PREFLIGHT NOGO: %s", exc)
        return 2

    results: list[dict] = []
    errors = 0

    for index, table in enumerate(args.tables, start=1):
        LOG.info("=" * 72)
        LOG.info("[%d/%d] %s", index, len(args.tables), table)
        LOG.info("=" * 72)

        try:
            result = process_table(table, args, encoder)
            results.append(result)
            LOG.info("GO [OK] %s", table.name)
        except KeyboardInterrupt:
            LOG.warning("Interruption demandée.")
            return 130
        except Exception as exc:
            errors += 1
            failure = {
                "ok": False,
                "table": str(table),
                "error": str(exc),
            }
            results.append(failure)
            LOG.error("NOGO [X] %s: %s", table.name, exc)
            if not args.continue_on_error:
                break

    summary = {
        "version": VERSION,
        "ok": errors == 0,
        "processed": len(results),
        "total": len(args.tables),
        "errors": errors,
        "results": results,
    }

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))

    LOG.info("=" * 72)
    LOG.info(
        "TERMINÉ: %d/%d traité(s), %d erreur(s)",
        len(results),
        len(args.tables),
        errors,
    )
    LOG.info("=" * 72)

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
