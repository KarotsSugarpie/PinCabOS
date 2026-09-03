#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import shlex
import subprocess

# PINCABOS_PATHS_CONSUMER_V1
import sys as _pco_sys
for _pco_dir in ("/opt/pincabos/tools", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools")):
    if _pco_dir not in _pco_sys.path:
        _pco_sys.path.insert(0, _pco_dir)
from pincabos_paths import PATHS
import sys
from pathlib import Path


DETECTOR = Path(
    "/opt/pincabos/launchers/pincabos-detect-table-modes.py"
)

# PINCABOS_PUP_SPLIT_RUNTIME_V1
# /run appartient a root et ce script tourne en pinball : sans le repertoire
# cree par tmpfiles.d (etc/tmpfiles.d/pincabos-pup-scoreview-split.conf), le
# mkdir echouait en PermissionError a chaque table PuP et le split restait
# silencieusement inactif. Repli : XDG_RUNTIME_DIR, puis /tmp.
def _runtime_root() -> Path:
    candidates = [Path("/run/pincabos-pup-scoreview-split")]
    xdg = os.environ.get("XDG_RUNTIME_DIR")
    if xdg:
        candidates.append(Path(xdg) / "pincabos-pup-scoreview-split")
    candidates.append(Path("/tmp") / f"pincabos-pup-scoreview-split-{os.getuid()}")
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            if os.access(candidate, os.W_OK):
                return candidate
        except OSError:
            continue
    return candidates[-1]


RUNTIME_ROOT = _runtime_root()

# Suffixe de la sauvegarde du screens.pup d'origine pendant une partie en
# split (pose par VPXlauncher.real.sh, restaure a la sortie ou au lancement
# suivant). Distinct de ".pincabos-origine" (choix de layout de
# pincabos-puppack-option) : le split part de l'etat CHOISI, pas de l'usine.
SPLIT_BACKUP_SUFFIX = ".pincabos-split-avant"


def q(value: object) -> str:
    return shlex.quote(str(value))


def read_sections(text: str) -> dict[str, dict[str, str]]:
    data: dict[str, dict[str, str]] = {}
    section = ""

    for raw in text.splitlines():
        line = raw.strip()

        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().casefold()
            data.setdefault(section, {})
            continue

        if (
            not line
            or line.startswith("#")
            or line.startswith(";")
            or "=" not in line
        ):
            continue

        key, value = line.split("=", 1)

        data.setdefault(section, {})[
            key.strip().casefold()
        ] = value.strip()

    return data


def patch_section(
    text: str,
    section: str,
    values: dict[str, str],
) -> str:

    lines = text.splitlines()
    wanted = section.casefold()

    start = None
    end = None

    for i, raw in enumerate(lines):
        line = raw.strip()

        if not (
            line.startswith("[")
            and line.endswith("]")
        ):
            continue

        name = line[1:-1].strip().casefold()

        if name == wanted:
            start = i
            continue

        if start is not None:
            end = i
            break

    if start is None:
        if lines and lines[-1].strip():
            lines.append("")

        lines.append(f"[{section}]")

        for key, value in values.items():
            lines.append(f"{key} = {value}")

        return "\n".join(lines) + "\n"

    if end is None:
        end = len(lines)

    existing: dict[str, int] = {}

    for i in range(start + 1, end):
        line = lines[i].strip()

        if (
            not line
            or line.startswith("#")
            or line.startswith(";")
            or "=" not in line
        ):
            continue

        key = line.split("=", 1)[0].strip().casefold()
        existing[key] = i

    additions: list[str] = []

    for key, value in values.items():
        folded = key.casefold()

        if folded in existing:
            lines[existing[folded]] = f"{key} = {value}"
        else:
            additions.append(f"{key} = {value}")

    if additions:
        lines[end:end] = additions

    return "\n".join(lines) + "\n"


def detect(table: Path) -> dict:
    raw = subprocess.check_output(
        [str(DETECTOR), str(table)],
        text=True,
    )
    return json.loads(raw)


def find_ini(table: Path) -> Path:
    return table.with_suffix(".ini")


def patch_ini(
    table: Path,
    mode: str,
    score_x: int,
    score_y: int,
    score_w: int,
    score_h: int,
) -> None:

    ini = find_ini(table)

    text = (
        ini.read_text(
            encoding="utf-8",
            errors="ignore",
        )
        if ini.is_file()
        else ""
    )

    if mode == "legacy":

        text = patch_section(
            text,
            "Topper",
            {
                "TopperOutput": "0",
            },
        )

        text = patch_section(
            text,
            "ScoreView",
            {
                "ScoreViewOutput": "1",
                "ScoreViewFullScreen": "0",
                "ScoreViewWndX": "0",
                "ScoreViewWndY": "0",
                "ScoreViewWidth": "1920",
                "ScoreViewHeight": "1200",
                "ScoreViewFSWidth": "1920",
                "ScoreViewFSHeight": "1200",
            },
        )

    else:

        text = patch_section(
            text,
            "Topper",
            {
                "TopperOutput": "1",
                "TopperFullScreen": "0",
                "TopperWndX": "0",
                "TopperWndY": "0",
                "TopperWidth": "1920",
                "TopperHeight": "1200",
                "TopperFSWidth": "1920",
                "TopperFSHeight": "1200",
                "Priority.PUP": "3",
            },
        )

        text = patch_section(
            text,
            "ScoreView",
            {
                "ScoreViewOutput": "1",
                "ScoreViewFullScreen": "0",
                "ScoreViewWndX": "0",
                "ScoreViewWndY": "0",
                "ScoreViewWidth": str(score_w),
                "ScoreViewHeight": str(score_h),
                "ScoreViewFSWidth": str(score_w),
                "ScoreViewFSHeight": str(score_h),
                "Priority.ScoreView": "2",
                "Priority.PUP": "3",
            },
        )

    # PINCABOS_PUP_B2S_FINAL_GUARD_V9
    # PINCABOS_PUP_SCOREVIEW_PRIORITY_V16
    # ScoreView possède exclusivement la fenêtre ScoreView.
    # Le contenu PuP FullDMD est routé dans Topper.

    #
    # Ce bloc est volontairement appliqué APRES la préparation
    # ScoreView. Le script ScoreView peut modifier certaines clés
    # B2SLegacy; en mode PuP nous imposons ici l'état final.
    if mode == "pup":

        text = patch_section(
            text,
            "Plugin.B2SLegacy",
            {
                "Enable": "0",
                "B2SHideB2SBackglass": "1",
                "B2SHideB2SDMD": "1",
                "B2SHideDMD": "1",
                "ScoreViewDMDOverlay": "0",
                "ScoreViewDMDAutoPos": "0",
            },
        )

        text = patch_section(
            text,
            "Plugin.ScoreView",
            {
                "Enable": "1",
            },
        )

        text = patch_section(
            text,
            "ScoreView",
            {
                "ScoreViewOutput": "1",
                "Priority.ScoreView": "3",
                "Priority.PUP": "0",
            },
        )

    ini.write_text(
        text,
        encoding="utf-8",
    )


def trigger_uses_screen(
    path: Path,
    screen_num: int,
) -> bool:

    if not path.is_file():
        return False

    with path.open(
        "r",
        encoding="utf-8-sig",
        errors="replace",
        newline="",
    ) as fh:

        for row in csv.reader(fh):
            if not row:
                continue

            try:
                value = int(row[0].strip())
            except Exception:
                continue

            if value == screen_num:
                return True

    return False


# PINCABOS_PUP_SPLIT_RECT_V1
# Ou poser le DMD reel de VPX sur le FullDMD pendant un PuP-Pack ? La reponse
# est dans le pack, pas dans une coordonnee figee (la douleur d'origine :
# un ScoreView place au pixel pour l'Original, faux pour chaque pack).
# Priorite :
#   1. l'ecran PuP 1 (DMD) si le pack le positionne sur l'ecran 5 (CustomPos) ;
#   2. la ZONE SOMBRE de la video / image FullDMD du pack — le cadre DMD dessine
#      par l'auteur (meme principe que l'AutoPos B2S : contenu, pas pixels),
#      mise en cache a cote du screens.pup ;
#   3. la calibration DMD de l'utilisateur (dmd-calibration.json) ;
#   4. les valeurs B2S de la table, puis un defaut.
DMD_ZONE_CACHE = ".pincabos-dmdzone.json"
DMD_ZONE_VERSION = 1


def _fulldmd_geometry() -> tuple[int, int, int, int] | None:
    """Geometrie du role FullDMD (w, h, x, y) d'apres display-aliases.env."""
    try:
        text = Path(PATHS.aliases_env).read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.search(r"PINCABOS_FULLDMD_GEOMETRY='(\d+)x(\d+)\+(-?\d+)\+(-?\d+)'", text)
    if not m or not re.search(r"PINCABOS_FULLDMD_AVAILABLE='1'", text):
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))


def _custom_pos(row: list[str]) -> tuple[int, float, float, float, float] | None:
    """CustomPos PuP : 'ecran,x%,y%,w%,h%'."""
    try:
        parts = [float(v) for v in (row[7] if len(row) > 7 else "").split(",")]
    except ValueError:
        return None
    if len(parts) != 5:
        return None
    return int(parts[0]), parts[1], parts[2], parts[3], parts[4]


def _pack_media_for_fulldmd(pack: Path, rows: list[list[str]]) -> Path | None:
    """Fichier dont on lira une image : la video de l'ecran 5, sinon le fond DMD."""
    for row in rows[1:]:
        try:
            if int(row[0]) != 5:
                continue
        except (ValueError, IndexError):
            continue
        playlist = row[2].strip() if len(row) > 2 else ""
        playfile = row[3].strip().strip('"') if len(row) > 3 else ""
        if playlist and playfile and (pack / playlist / playfile).is_file():
            return pack / playlist / playfile
    for folder in ("DMDBackground", "FullDMD", "PuPOverlays"):
        d = pack / folder
        if d.is_dir():
            for f in sorted(d.iterdir()):
                if f.suffix.lower() in (".mp4", ".mkv", ".avi", ".mov", ".png", ".jpg", ".jpeg", ".gif"):
                    return f
    return None


def _raw_to_gray(raw: bytes, w: int, h: int):
    try:
        import numpy as np
    except ImportError:
        return None
    if len(raw) != w * h:
        return None
    return np.frombuffer(raw, dtype=np.uint8).reshape(h, w)


def _gray_frame(media: Path, w: int = 480, h: int = 270, at: float = 2.0):
    """Image en niveaux de gris (numpy, h x w) d'une video (a `at` secondes) ou d'une image."""
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin"]
    if media.suffix.lower() in (".mp4", ".mkv", ".avi", ".mov"):
        cmd += ["-ss", str(at)]
    cmd += ["-i", str(media), "-frames:v", "1", "-vf", f"scale={w}:{h}", "-pix_fmt", "gray", "-f", "rawvideo", "-"]
    try:
        raw = subprocess.run(cmd, capture_output=True, timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return _raw_to_gray(raw, w, h)


def _gray_frames(media: Path):
    """Plusieurs instants d'une video : un fondu au noir a 2 s ne doit pas
    faire conclure qu'il n'y a pas de cadre."""
    if media.suffix.lower() not in (".mp4", ".mkv", ".avi", ".mov"):
        g = _gray_frame(media)
        return [g] if g is not None else []
    frames = []
    for at in (2.0, 8.0, 20.0, 45.0):
        g = _gray_frame(media, at=at)
        if g is not None and g.mean() > 24:
            frames.append(g)
    return frames


# PINCABOS_PUP_SPLIT_LIVE_V1
# Quand les medias du pack ne disent pas ou est le cadre DMD (Oz : la scene
# affichee est composee a l'execution), on regarde l'ECRAN FullDMD lui-meme
# une fois le pack lance — ce qu'il affiche vraiment — et on met en cache.
def _gray_screen(x: int, y: int, w: int, h: int, sw: int = 480, sh: int = 270):
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
           "-f", "x11grab", "-video_size", f"{w}x{h}", "-i", f"{os.environ.get('DISPLAY', ':0')}+{x},{y}",
           "-frames:v", "1", "-vf", f"scale={sw}:{sh}", "-pix_fmt", "gray", "-f", "rawvideo", "-"]
    try:
        raw = subprocess.run(cmd, capture_output=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return _raw_to_gray(raw, sw, sh)


def zone_from_screen(pack: Path, tries: int = 6, pause: float = 2.0) -> dict | None:
    """Detection sur l'ecran FullDMD reel (retentee tant que l'ecran est noir),
    resultat mis en cache a cote du screens.pup."""
    import time
    geom = _fulldmd_geometry()
    if geom is None:
        return None
    fd_w, fd_h, fd_x, fd_y = geom
    zone = None
    for _ in range(tries):
        gray = _gray_screen(fd_x, fd_y, fd_w, fd_h)
        if gray is not None and gray.mean() > 24:
            zone = find_dark_zone(gray)
            if zone:
                break
        time.sleep(pause)
    if not zone:
        return None
    fx, fy, fw, fh = zone
    data = {"version": DMD_ZONE_VERSION, "fd": [fd_w, fd_h], "media": "", "found": True,
            "x": int(round(fx * fd_w)), "y": int(round(fy * fd_h)),
            "w": int(round(fw * fd_w)), "h": int(round(fh * fd_h)), "source": "ecran-reel"}
    try:
        (pack / ("screens.pup" + DMD_ZONE_CACHE)).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass
    return data


def find_dark_zone(gray, threshold: int = 32, min_area: float = 0.015, min_fill: float = 0.6):
    """Rectangle (x, y, w, h en fraction 0..1) de la plus grande zone sombre
    compacte a la forme d'un DMD (largeur 2 a 8 fois la hauteur), ou None.
    Pur numpy + parcours de composantes : pas de dependance."""
    import numpy as np
    h, w = gray.shape
    mask = gray < threshold
    seen = np.zeros_like(mask, dtype=bool)
    best = None
    for y0 in range(h):
        for x0 in range(w):
            if not mask[y0, x0] or seen[y0, x0]:
                continue
            stack = [(y0, x0)]
            seen[y0, x0] = True
            minx = maxx = x0
            miny = maxy = y0
            area = 0
            while stack:
                y, x = stack.pop()
                area += 1
                minx, maxx = min(minx, x), max(maxx, x)
                miny, maxy = min(miny, y), max(maxy, y)
                for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            bw, bh = maxx - minx + 1, maxy - miny + 1
            if area < min_area * w * h or bh == 0:
                continue
            ratio = bw / bh
            fill = area / (bw * bh)
            # un cadre DMD : rectangle plein (>= 80 %), bien plus large que haut,
            # et pas le fond entier de l'image
            # remplissage tolerant : un cadre DMD contient du texte anime (clair)
            if ratio < 2.0 or ratio > 8.0 or fill < min_fill or bw > 0.95 * w:
                continue
            if best is None or area > best[4]:
                best = (minx / w, miny / h, bw / w, bh / h, area)
    if best is None:
        return None
    return best[:4]


def dmd_zone_from_pack(pack: Path, rows: list[list[str]], fd_w: int, fd_h: int) -> dict | None:
    """Rectangle du DMD (relatif au FullDMD, en pixels) detecte dans le pack,
    avec cache a cote du screens.pup (recalcule si la version change)."""
    cache = pack / ("screens.pup" + DMD_ZONE_CACHE)
    try:
        data = json.loads(cache.read_text(encoding="utf-8"))
        if data.get("version") == DMD_ZONE_VERSION and data.get("fd") == [fd_w, fd_h]:
            return data if data.get("found") else None
    except (OSError, ValueError):
        pass
    media = _pack_media_for_fulldmd(pack, rows)
    zone = None
    for gray in (_gray_frames(media) if media else []):
        zone = find_dark_zone(gray)
        if zone:
            break
    if not zone:
        return None
    fx, fy, fw, fh = zone
    data = {"version": DMD_ZONE_VERSION, "fd": [fd_w, fd_h], "media": media.name if media else "",
            "found": True, "x": int(round(fx * fd_w)), "y": int(round(fy * fd_h)),
            "w": int(round(fw * fd_w)), "h": int(round(fh * fd_h)), "source": "zone-sombre"}
    try:
        cache.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass
    return data


def _user_dmd_calibration(fd_x: int, fd_y: int) -> dict | None:
    """Calibration DMD de l'utilisateur (coordonnees ecran absolues) -> relative au FullDMD."""
    try:
        d = json.loads(Path(PATHS.config, "dmd-calibration.json").read_text(encoding="utf-8"))
        x, y, w, h = int(d["x"]), int(d["y"]), int(d["width"]), int(d["height"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if w <= 0 or h <= 0:
        return None
    return {"x": x - fd_x, "y": y - fd_y, "w": w, "h": h, "source": "calibration-dmd"}


def split_rectangle(pack: Path, rows: list[list[str]]) -> tuple[int, int, int, int, str]:
    """(x, y, w, h, source) du ScoreView, relatif au FullDMD."""
    geom = _fulldmd_geometry()
    if geom is None:
        return 0, 0, 640, 160, "defaut (pas de role fulldmd)"
    fd_w, fd_h, fd_x, fd_y = geom
    for row in rows[1:]:
        try:
            if int(row[0]) != 1:
                continue
        except (ValueError, IndexError):
            continue
        pos = _custom_pos(row)
        if pos and pos[0] == 5 and pos[3] > 0 and pos[4] > 0:
            return (int(fd_w * pos[1] / 100), int(fd_h * pos[2] / 100),
                    int(fd_w * pos[3] / 100), int(fd_h * pos[4] / 100), "ecran 1 du pack")
    zone = dmd_zone_from_pack(pack, rows, fd_w, fd_h)
    if zone:
        return zone["x"], zone["y"], zone["w"], zone["h"], "zone sombre de la video du pack"
    cal = _user_dmd_calibration(fd_x, fd_y)
    if cal and 0 <= cal["x"] < fd_w and 0 <= cal["y"] < fd_h:
        return cal["x"], cal["y"], cal["w"], cal["h"], "calibration DMD"
    return 0, 0, 640, 160, "defaut"


def table_has_pinmame(table: Path, info: dict | None = None) -> bool:
    """La table emule-t-elle vraiment une ROM PinMAME ?

    PINCABOS_PUP_SPLIT_SANS_PINMAME_V1 — sans PinMAME (tables « originales » a
    DMD FlexDMD ou PuP : Blizzard of Ozz, Matrix, TNA...), le pack dessine
    lui-meme son DMD sur le FullDMD ; y superposer le Score View de VPX double
    le texte (Oz : « ecritures en double qui se chevauchent »). Le critere est
    la presence d'une ROM (detecteur de modes) : Oz declare un cGameName pour
    son pack et son DOF sans emuler quoi que ce soit."""
    if info is not None:
        return bool(info.get("rom_files"))
    try:
        data = table.read_bytes()
    except OSError:
        return True  # doute : comportement historique
    # une ligne NON commentee « Set Controller = CreateObject("VPinMAME.Controller") »
    motif = re.compile(r"(?im)^[^'\r\n]*Set\s+Controller\s*=\s*CreateObject\(\s*[\"']VPinMAME\.Controller")
    for enc in ("utf-16-le", "latin-1"):
        if motif.search(data.decode(enc, "ignore")):
            return True
    return False


def make_split(table: Path) -> dict[str, str]:
    # PINCABOS_PUP_SPLIT_ROOT_GATE_V1
    # Le montage en namespace qui applique le split exige root ; la chaine de
    # lancement tourne en pinball. Tant qu'un helper privilegie n'existe pas,
    # le split est declare inactif ICI, avant que la politique DMD/FullDMD et
    # le placeur ne lisent la reponse — sinon ils appliquent la geometrie
    # split a des ecrans PuP qui n'ont pas ete remappes.
    # PINCABOS_PUP_SPLIT_NOROOT_V2
    # Plus de montage en namespace (qui exigeait root) : le launcher remplace
    # le screens.pup du pack le temps de la partie et le restaure a la sortie
    # (sauvegarde SPLIT_BACKUP_SUFFIX). Ce helper tourne donc en pinball.
    info = detect(table)

    if not table_has_pinmame(table, info):
        return {
            "active": "0",
            "reason": "table sans PinMAME : le pack dessine son DMD",
        }

    packs = [
        Path(p)
        for p in info.get("pup_packs", [])
    ]

    pack = next(
        (
            p
            for p in packs
            if (p / "screens.pup").is_file()
        ),
        None,
    )

    if pack is None:
        return {
            "active": "0",
            "reason": "Aucun screens.pup",
        }

    screens = pack / "screens.pup"
    triggers = pack / "triggers.pup"

    # Reste d'une partie interrompue (VPX tue, coupure) : la sauvegarde est
    # encore la, le pack porte le screens.pup modifie. On remet l'original
    # AVANT de le lire, sinon on empilerait un split sur un split.
    stale = screens.with_name(screens.name + SPLIT_BACKUP_SUFFIX)
    if stale.is_file():
        os.replace(stale, screens)

    with screens.open(
        "r",
        encoding="utf-8-sig",
        errors="replace",
        newline="",
    ) as fh:
        rows = list(csv.reader(fh))

    if not rows:
        return {
            "active": "0",
            "reason": "screens.pup vide",
        }

    screen0 = None
    moved = []

    for row in rows[1:]:

        if not row:
            continue

        while len(row) < 8:
            row.append("")

        try:
            num = int(row[0].strip())
        except Exception:
            continue

        if num == 0:
            screen0 = row

    if screen0 is None:
        return {
            "active": "0",
            "reason": "screen 0 Topper absent",
        }

    while len(screen0) < 8:
        screen0.append("")

    #
    # Pour utiliser le Topper comme surface FullDMD,
    # le screen 0 doit être libre.
    #
    if (
        screen0[2].strip()
        or screen0[3].strip()
        or trigger_uses_screen(triggers, 0)
    ):
        return {
            "active": "0",
            "reason": "screen 0 déjà utilisé",
        }

    #
    # VPX rend normalement screen 5 puis screen 1
    # dans la fenêtre ScoreView.
    #
    # En les transformant en enfants de screen 0,
    # ils seront rendus dans la fenêtre Topper.
    #
    for row in rows[1:]:

        if not row:
            continue

        while len(row) < 8:
            row.append("")

        try:
            num = int(row[0].strip())
        except Exception:
            continue

        if num in {1, 5}:
            row[7] = "0,0,0,100,100"
            moved.append(num)

    if not moved:
        return {
            "active": "0",
            "reason": "screen 1/5 absent",
        }

    RUNTIME_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        os.chmod(
            RUNTIME_ROOT,
            0o755,
        )
    except OSError:
        pass

    digest = hashlib.sha1(
        str(table).encode()
    ).hexdigest()[:12]

    runtime = (
        RUNTIME_ROOT
        / f"{os.getpid()}-{digest}"
    )

    runtime.mkdir(
        parents=True,
        exist_ok=True,
    )

    os.chmod(
        runtime,
        0o755,
    )

    temp_screens = runtime / "screens.pup"

    output = io.StringIO()

    writer = csv.writer(
        output,
        lineterminator="\n",
    )

    writer.writerows(rows)

    temp_screens.write_text(
        output.getvalue(),
        encoding="utf-8",
    )

    os.chmod(
        temp_screens,
        0o644,
    )

    score_x, score_y, score_w, score_h, score_source = split_rectangle(pack, rows)

    if score_w <= 0:
        score_w = 640

    if score_h <= 0:
        score_h = 160

    patch_ini(
        table,
        "pup",
        score_x,
        score_y,
        score_w,
        score_h,
    )

    return {
        "active": "1",
        "pack": str(pack),
        "target": str(screens),
        "temp": str(temp_screens),
        "runtime": str(runtime),
        "moved": ",".join(
            str(x)
            for x in moved
        ),
        "score_x": str(score_x),
        "score_y": str(score_y),
        "score_w": str(score_w),
        "score_h": str(score_h),
        "reason": "OK (" + score_source + ")",
    }


def print_shell(data: dict[str, str]) -> None:

    mapping = {
        "PINCABOS_PUP_SPLIT_ACTIVE":
            data.get("active", "0"),

        "PINCABOS_PUP_SPLIT_REASON":
            data.get("reason", ""),

        "PINCABOS_PUP_SPLIT_PACK":
            data.get("pack", ""),

        "PINCABOS_PUP_SPLIT_TARGET":
            data.get("target", ""),

        "PINCABOS_PUP_SPLIT_TEMP":
            data.get("temp", ""),

        "PINCABOS_PUP_SPLIT_RUNTIME":
            data.get("runtime", ""),

        "PINCABOS_SCOREVIEW_REL_X":
            data.get("score_x", "0"),

        "PINCABOS_SCOREVIEW_REL_Y":
            data.get("score_y", "0"),

        "PINCABOS_SCOREVIEW_W":
            data.get("score_w", "640"),

        "PINCABOS_SCOREVIEW_H":
            data.get("score_h", "160"),
    }

    for key, value in mapping.items():
        print(
            f"{key}={q(value)}"
        )


def main() -> int:
    if len(sys.argv) >= 3 and sys.argv[1] == "zone":
        # placeur : "ou est le cadre DMD sur l'ecran reel ?" -> "x y w h" (relatif au FullDMD) ou rien
        pack = Path(sys.argv[2])
        cache = pack / ("screens.pup" + DMD_ZONE_CACHE)
        try:
            d = json.loads(cache.read_text(encoding="utf-8"))
            if d.get("found") and d.get("version") == DMD_ZONE_VERSION:
                print(d["x"], d["y"], d["w"], d["h"], d.get("source", ""))
                return 0
        except (OSError, ValueError, KeyError):
            pass
        d = zone_from_screen(pack)
        if d:
            print(d["x"], d["y"], d["w"], d["h"], d["source"])
            return 0
        return 1

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "mode",
        choices=(
            "pup",
            "legacy",
        ),
    )

    parser.add_argument(
        "table",
    )

    parser.add_argument(
        "--shell",
        action="store_true",
    )

    args = parser.parse_args()

    table = Path(args.table).resolve()

    if not table.is_file():
        print(
            f"NOGO [X] Table absente : {table}",
            file=sys.stderr,
        )
        return 1

    if args.mode == "legacy":

        patch_ini(
            table,
            "legacy",
            0,
            0,
            640,
            160,
        )

        data = {
            "active": "0",
            "reason": "Legacy",
        }

    else:
        data = make_split(table)

    if args.shell:
        print_shell(data)
    else:
        print(
            json.dumps(
                data,
                indent=2,
                ensure_ascii=False,
            )
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
