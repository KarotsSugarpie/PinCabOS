#!/usr/bin/env bash
set -Eeuo pipefail

TABLES_ROOT="/home/pinball/Tables"
GLOBAL_INI="/home/pinball/.local/share/VPinballX/10.8/VPinballX.ini"

TARGET_VPX=""
for arg in "$@"; do
    case "$arg" in
        *.vpx|*.VPX)
            if [[ -f "$arg" ]]; then
                TARGET_VPX="$arg"
                break
            fi
            ;;
    esac
done

python3 -S - "$GLOBAL_INI" "$TABLES_ROOT" "$TARGET_VPX" <<'PY'
from __future__ import annotations

from pathlib import Path
import json
import os
import pwd
import re
import sys

GLOBAL_INI = Path(sys.argv[1])

# PINCABOS_BACKGLASS_GEOMETRY_V1
# Sans BackglassWidth/BackglassHeight, VPX dimensionne la fenetre backglass
# d'apres le playfield tourne en portrait — 960x1706 pour un playfield 4K —
# et fige cette taille par WM_NORMAL_HINTS (minimum == maximum). Aucun
# gestionnaire de fenetres ne peut la corriger ensuite : la seule fenetre de
# tir est ici, avant le lancement.
SCREENS_JSON = Path("/opt/pincabos/config/screens/screens.json")


def role_geometry(role: str) -> tuple[int, int, int, int] | None:
    """(x, y, largeur, hauteur) de l'ecran portant ce role, ou None."""
    try:
        data = json.loads(SCREENS_JSON.read_text(encoding="utf-8"))
    except Exception:
        return None
    entry = data.get(role)
    if not isinstance(entry, dict):
        return None
    m = re.match(r"^(\d+)x(\d+)\+(-?\d+)\+(-?\d+)$", str(entry.get("geometry") or ""))
    if not m:
        return None
    largeur, hauteur, x, y = (int(v) for v in m.groups())
    return x, y, largeur, hauteur


def backglass_window_geometry() -> dict[str, str]:
    """Dimensions a imposer, seulement si le fronton a deux ecrans distincts.

    Sur un cabinet a deux ecrans, backglass et fulldmd designent la meme
    dalle : on ne touche a rien et le comportement reste celui d'avant.
    """
    backglass = role_geometry("backglass")
    fulldmd = role_geometry("fulldmd")
    if not backglass or not fulldmd or backglass == fulldmd:
        return {}
    x, y, largeur, hauteur = backglass
    # PINCABOS_FRONT_WINDOWS_FROM_SCREENS_V1
    # La position compte autant que la taille : sans elle VPX ouvre la fenetre
    # sur le premier ecran et il faut la deplacer apres coup.
    return {
        "BackglassWidth": str(largeur),
        "BackglassHeight": str(hauteur),
        "BackglassWndX": str(x),
        "BackglassWndY": str(y),
    }


BACKGLASS_WINDOW = backglass_window_geometry()
TABLES_ROOT = Path(sys.argv[2]).resolve()
TARGET_VPX = Path(sys.argv[3]).resolve() if sys.argv[3] else None

def scoreview_window() -> dict[str, str]:
    """Fenetre Score View posee sur l'ecran qui porte le role fulldmd.

    PINCABOS_FRONT_WINDOWS_FROM_SCREENS_V1
    Les valeurs etaient ecrites en dur a (0,0) 1920x1200, donc sur le premier
    ecran : la fenetre atterrissait sur le playfield ou le backglass et devait
    etre deplacee ensuite. On la pose directement au bon endroit.

    Sur un fronton d'un seul ecran, ou si les roles manquent, on garde
    exactement les anciennes valeurs.
    """
    base = {
        "ScoreViewOutput": "1",
        "ScoreViewDisplay": "",
        "ScoreViewFullScreen": "0",
        "ScoreViewWndX": "0",
        "ScoreViewWndY": "0",
        "ScoreViewWidth": "1920",
        "ScoreViewHeight": "1200",
        "ScoreViewFSWidth": "1920",
        "ScoreViewFSHeight": "1200",
    }
    backglass = role_geometry("backglass")
    fulldmd = role_geometry("fulldmd")
    if not backglass or not fulldmd or backglass == fulldmd:
        return base
    x, y, largeur, hauteur = fulldmd
    base.update({
        "ScoreViewWndX": str(x),
        "ScoreViewWndY": str(y),
        "ScoreViewWidth": str(largeur),
        "ScoreViewHeight": str(hauteur),
        "ScoreViewFSWidth": str(largeur),
        "ScoreViewFSHeight": str(hauteur),
    })
    return base


SCOREVIEW_WINDOW = scoreview_window()

SCOREVIEW_DISABLED_OUTPUT = dict(SCOREVIEW_WINDOW)
SCOREVIEW_DISABLED_OUTPUT["ScoreViewOutput"] = "0"

def _b2s_geometry_from_screens() -> dict:
    """Positions backglass/DMD B2S derivees des roles reels de screens.json
    (au lieu de coords figees). Backglass -> role backglass ; DMD B2S -> role
    fulldmd. Repli sur d'anciennes valeurs si un role manque."""
    bg = role_geometry("backglass") or (3840, 0, 1920, 1080)
    fd = role_geometry("fulldmd") or (5760, 0, 1920, 1200)
    bgx, bgy, bgw, bgh = bg
    fdx, fdy, fdw, fdh = fd
    return {
        "Enable": "1",
        "B2SHideGrill": "1",
        "B2SHideB2SBackglass": "0",
        "B2SDualMode": "0",
        "BackglassDMDOverlay": "0",
        "BackglassDMDAutoPos": "0",
        "B2SBackglassWidth": str(bgw),
        "B2SBackglassHeight": str(bgh),
        "B2SBackglassX": str(bgx),
        "B2SBackglassY": str(bgy),
        "B2SDMDWidth": str(fdw),
        "B2SDMDHeight": str(fdh),
        "B2SDMDX": str(fdx),
        "B2SDMDY": str(fdy),
        "B2SDMDRotation": "0",
    }


B2S_GEOMETRY = _b2s_geometry_from_screens()

B2S_FULLDMD = {
    **B2S_GEOMETRY,
    "B2SHideB2SDMD": "0",
    "B2SHideDMD": "1",
    "ScoreViewDMDOverlay": "1",
}

B2S_PUP = {
    **B2S_GEOMETRY,

    # PINCABOS_PUP_B2S_OFF_V9
    #
    # En mode PuP, le PuP-Pack possède les surfaces Backglass /
    # FullDMD. B2SLegacy doit être complètement neutralisé.
    "Enable": "0",
    "B2SHideB2SBackglass": "1",
    "B2SHideB2SDMD": "1",
    "B2SHideDMD": "1",
    "ScoreViewDMDOverlay": "0",
    "ScoreViewDMDAutoPos": "0",
}

# PINCABOS_PUP_B2S_CONDITIONNEL_V1
#
# Toutes les dispositions de PuP-Pack ne prennent pas le fronton. Plusieurs
# posent le pack sur le FullDMD et attendent un B2S dans le backglass — leur
# notice le dit mot pour mot. Masquer le B2S dans ce cas laisse le fronton
# noir alors que le pack est correctement configure : c'est le defaut que
# l'on corrige. On garde donc B2SLegacy et son image de fronton, tout en
# neutralisant sa partie DMD, dont le pack se charge.
B2S_PUP_FRONTON_B2S = {
    **B2S_PUP,
    "Enable": "1",
    "B2SHideB2SBackglass": "0",
}


def pup_peint_le_fronton(table) -> bool:
    """Le PuP-Pack de cette table dessine-t-il lui-meme le backglass ?

    En l'absence de l'outil — ancienne installation, appel hors contexte —
    on repond oui, ce qui reconduit exactement le comportement anterieur.
    """
    import subprocess

    outil = Path("/opt/pincabos/bin/pincabos-puppack-option")
    if not outil.is_file():
        return True
    try:
        resultat = subprocess.run(
            ["python3", str(outil), "backglass", str(table)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20,
        )
    except Exception:
        return True
    return resultat.returncode == 0


DMD_DEFAULTS_ONLY = {
    "ScoreViewDMDAutoPos": "1",
    "ScoreViewDMDX": "0",
    "ScoreViewDMDY": "0",
    "ScoreViewDMDW": "0",
    "ScoreViewDMDH": "0",
}


# Un ecran FullDMD DEDIE existe-t-il ? (role fulldmd present ET distinct du
# backglass). Sur un cab a 2 ecrans (playfield+backglass, pas de FullDMD) le DMD
# ne doit PAS etre force ailleurs : on ne touche a rien dans ce cas.
_FULLDMD_ROLE = role_geometry("fulldmd")
_BACKGLASS_ROLE = role_geometry("backglass")
HAS_DEDICATED_FULLDMD = bool(_FULLDMD_ROLE) and _FULLDMD_ROLE != _BACKGLASS_ROLE

# Tables STANDARD (DMD reel PinMAME via B2SLegacy, pas de FullDMD directB2S) :
# si un FullDMD dedie existe, y placer le DMD explicitement (l'AutoPos rend un
# DMD reel 128x32 minuscule / mal place). Geometrie derivee du role fulldmd.
STANDARD_DMD_FILL = {
    "ScoreViewDMDOverlay": "1",
    "ScoreViewDMDAutoPos": "0",
    "ScoreViewDMDX": "0",
    "ScoreViewDMDY": "0",
    "ScoreViewDMDW": str(_FULLDMD_ROLE[2]),
    "ScoreViewDMDH": str(_FULLDMD_ROLE[3]),
} if HAS_DEDICATED_FULLDMD else {}


def find_section(lines: list[str], section_name: str) -> tuple[int | None, int]:
    start = None
    end = len(lines)

    for index, line in enumerate(lines):
        match = re.match(r"^\s*\[([^\]]+)\]\s*$", line.strip())
        if match and match.group(1).strip().casefold() == section_name.casefold():
            start = index
            break

    if start is not None:
        for index in range(start + 1, len(lines)):
            if re.match(r"^\s*\[[^\]]+\]\s*$", lines[index].strip()):
                end = index
                break

    return start, end


def patch_ini(
    path: Path,
    overwrite: dict[str, dict[str, str]],
    ensure: dict[str, dict[str, str]] | None = None,
    remove_sections: tuple[str, ...] = (),
) -> None:
    raw = path.read_text(encoding="utf-8", errors="surrogateescape") if path.exists() else ""
    newline = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.splitlines(keepends=True)

    for section_name in remove_sections:
        start, end = find_section(lines, section_name)
        if start is not None:
            del lines[start:end]
            while start < len(lines) and not lines[start].strip():
                del lines[start]

    sections = [(section_name, values, False) for section_name, values in overwrite.items()]
    for section_name, values in (ensure or {}).items():
        sections.append((section_name, values, True))

    for section_name, values, ensure_only in sections:
        start, end = find_section(lines, section_name)

        if start is None:
            if lines and not lines[-1].endswith(("\n", "\r")):
                lines[-1] += newline
            if lines and lines[-1].strip():
                lines.append(newline)
            lines.append(f"[{section_name}]{newline}")
            for key, value in values.items():
                lines.append(f"{key} = {value}{newline}")
            continue

        found: set[str] = set()

        for index in range(start + 1, end):
            match = re.match(r"^(\s*)([^=;#]+?)\s*=.*?(\r?\n)?$", lines[index])
            if not match:
                continue

            current = match.group(2).strip()
            for key, value in values.items():
                if current.casefold() != key.casefold():
                    continue
                found.add(key.casefold())
                if not ensure_only:
                    ending = match.group(3) or newline
                    lines[index] = f"{match.group(1)}{key} = {value}{ending}"
                break

        additions = [
            f"{key} = {value}{newline}"
            for key, value in values.items()
            if key.casefold() not in found
        ]
        if additions:
            lines[end:end] = additions

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".pincabos-native-full-dmd.tmp")
    temporary.write_text("".join(lines), encoding="utf-8", errors="surrogateescape")
    os.replace(temporary, path)

    try:
        account = pwd.getpwnam("pinball")
        os.chown(path, account.pw_uid, account.pw_gid)
        os.chmod(path, 0o664)
    except (KeyError, PermissionError):
        pass


def find_directb2s(vpx: Path) -> Path | None:
    expected = vpx.with_suffix(".directb2s")
    if expected.is_file():
        return expected

    wanted = (vpx.stem + ".directb2s").casefold()
    try:
        for item in vpx.parent.iterdir():
            if item.is_file() and item.name.casefold() == wanted:
                return item
    except OSError:
        return None

    return None


def directb2s_has_fulldmd(path: Path | None) -> bool:
    if not path or not path.is_file():
        return False

    try:
        payload = path.read_bytes()
    except OSError:
        return False

    for encoding in ("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "latin-1"):
        try:
            text = payload.decode(encoding, errors="ignore")
        except Exception:
            continue

        match = re.search(
            r"<DMDType\b[^>]*\bValue\s*=\s*[\"']\s*([0-9]+)\s*[\"']",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if match and match.group(1) == "3":
            return True

        if re.search(r"<DMDImage\b", text, flags=re.IGNORECASE):
            return True

    return False


def has_table_local_pup(table_dir: Path) -> bool:
    try:
        entries = list(table_dir.iterdir())
    except OSError:
        return False

    for entry in entries:
        if not entry.is_dir() or entry.name.casefold() not in {"pupvideo", "pupvideos", "pinupvideo", "pinupvideos"}:
            continue
        try:
            return any(item.is_file() for item in entry.rglob("*"))
        except OSError:
            return True

    return False


# Base globale : la surface ScoreView existe, mais le plugin ScoreView distinct
# reste disponible seulement pour les tables qui n'ont pas de FullDMD B2S.
patch_ini(
    GLOBAL_INI,
    {
        "ScoreView": SCOREVIEW_WINDOW,
        "Plugin.B2SLegacy": B2S_GEOMETRY,
        "Plugin.ScoreView": {"Enable": "1"},
        **({"Backglass": BACKGLASS_WINDOW} if BACKGLASS_WINDOW else {}),
    },
)

if TARGET_VPX and TARGET_VPX.is_file():
    try:
        TARGET_VPX.relative_to(TABLES_ROOT)
    except ValueError:
        raise SystemExit("Chemin VPX hors du dossier Tables.")

    table_ini = TARGET_VPX.with_suffix(".ini")
    pup = has_table_local_pup(TARGET_VPX.parent)
    b2s = find_directb2s(TARGET_VPX)
    full_dmd = directb2s_has_fulldmd(b2s)

    if pup:
        fronton_au_pack = pup_peint_le_fronton(TARGET_VPX)
        patch_ini(
            table_ini,
            {
                "ScoreView": SCOREVIEW_DISABLED_OUTPUT,
                "Plugin.B2SLegacy": B2S_PUP if fronton_au_pack else B2S_PUP_FRONTON_B2S,
                "Plugin.ScoreView": {"Enable": "0"},
            },
            remove_sections=("PinCabOS.ScoreViewWindow",),
        )
        mode = "PUP" if fronton_au_pack else "PUP_FRONTON_B2S"
    elif full_dmd:
        patch_ini(
            table_ini,
            {
                "ScoreView": SCOREVIEW_WINDOW,
                "Plugin.B2SLegacy": B2S_FULLDMD,
                "Plugin.ScoreView": {"Enable": "0"},
            },
            ensure={"Plugin.B2SLegacy": DMD_DEFAULTS_ONLY},
            remove_sections=("PinCabOS.ScoreViewWindow",),
        )
        mode = "B2S_FULLDMD"
    else:
        # Tables sans FullDMD directB2S. Si un ecran FullDMD dedie existe, on y
        # pose le DMD reel explicitement (sinon AutoPos -> DMD minuscule). Sur un
        # cab sans FullDMD, on garde le comportement minimal d'origine.
        overwrite = {"Plugin.ScoreView": {"Enable": "1"}}
        if STANDARD_DMD_FILL:
            overwrite["ScoreView"] = SCOREVIEW_WINDOW
            overwrite["Plugin.B2SLegacy"] = STANDARD_DMD_FILL
        patch_ini(
            table_ini,
            overwrite,
            remove_sections=("PinCabOS.ScoreViewWindow",),
        )
        mode = "STANDARD" if STANDARD_DMD_FILL else "STANDARD_NO_FULLDMD"

    print(f"MODE={mode}")
    print(f"TABLE={TARGET_VPX}")
    print(f"INI={table_ini}")
    print(f"DIRECTB2S={b2s or ''}")
PY

