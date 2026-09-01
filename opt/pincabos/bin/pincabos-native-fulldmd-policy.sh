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

# Rectangle DMD explicite : ratio ~4:1 (forme d'un vrai DMD 128x32) non
# deforme, largeur = ecran FullDMD, centre verticalement. Sert a poser le DMD a
# la bonne taille et au bon endroit quand l'auto-placement de B2S echoue.
# Coordonnees relatives a la fenetre ScoreView (rendue dans le contexte 2D de
# cette fenetre, elle-meme posee sur le FullDMD). Derive du role fulldmd de
# screens.json => universel : chaque cab obtient sa propre geometrie, aucune
# valeur figee. Sur un cab sans FullDMD dedie : vide (on ne force rien).
def _dmd_rect() -> dict[str, str]:
    if not HAS_DEDICATED_FULLDMD:
        return {}
    _, _, fw, fh = _FULLDMD_ROLE
    w = fw
    h = w // 4
    if h > fh:
        h, w = fh, fh * 4
    return {
        "ScoreViewDMDOverlay": "1",
        "ScoreViewDMDAutoPos": "0",
        "ScoreViewDMDX": str((fw - w) // 2),
        "ScoreViewDMDY": str((fh - h) // 2),
        "ScoreViewDMDW": str(w),
        "ScoreViewDMDH": str(h),
    }


DMD_RECT = _dmd_rect()

# DMD LIVE (PinMAME) a afficher sur le FullDMD : cas des tables sans image DMD
# cote B2S (directb2s FullDMD sans <DMDImage>, ou pas de directb2s du tout). Le
# defaut global masque le DMD live (B2SHideDMD=1) -> on le reaffiche et on masque
# l'eventuelle image DMD statique.
STANDARD_DMD_FILL = ({
    "B2SHideB2SDMD": "1",
    "B2SHideDMD": "0",
    **DMD_RECT,
} if DMD_RECT else {})

# FullDMD B2S natif AVEC image DMD mais dont l'auto-placement degenere
# (GrillHeight=0) : on garde l'affichage de l'image FullDMD B2S (DMD composite
# par B2S) mais on pose le DMD explicitement au lieu de l'AutoPos qui le rend
# minuscule.
B2S_FULLDMD_EXPLICIT = {**B2S_FULLDMD, **DMD_RECT} if DMD_RECT else dict(B2S_FULLDMD)


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


def directb2s_info(path: Path | None) -> dict:
    """Infos DMD lues DANS le directb2s de la table (rien de fige) :

      - type3        : DMDType=3 -> le directb2s declare un FullDMD.
      - has_dmdimage : une image <DMDImage> est fournie (le FullDMD a un visuel
                       propre a composer avec le DMD live).
      - grill        : <GrillHeight> ; 0 => l'auto-placement du DMD par B2S
                       degenere (DMD minuscule / mal place).

    Ces trois valeurs, toutes issues du fichier de la table, suffisent a router
    le DMD au bon endroit et a la bonne taille selon ce que la table fournit
    reellement (cf. l'arbre de decision plus bas)."""
    info = {"type3": False, "has_dmdimage": False, "grill": None}
    if not path or not path.is_file():
        return info

    try:
        payload = path.read_bytes()
    except OSError:
        return info

    for encoding in ("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "latin-1"):
        try:
            text = payload.decode(encoding, errors="ignore")
        except Exception:
            continue

        # Encodage retenu = celui qui expose l'en-tete XML du directb2s.
        if "<DMDType" not in text and "<DirectB2SData" not in text:
            continue

        match = re.search(
            r"<DMDType\b[^>]*\bValue\s*=\s*[\"']\s*([0-9]+)\s*[\"']",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        info["type3"] = bool(match and match.group(1) == "3")
        info["has_dmdimage"] = bool(re.search(r"<DMDImage\b", text, flags=re.IGNORECASE))
        grill = re.search(
            r"<GrillHeight\b[^>]*\bValue\s*=\s*[\"']\s*([0-9]+)\s*[\"']",
            text,
            flags=re.IGNORECASE,
        )
        info["grill"] = int(grill.group(1)) if grill else None
        return info

    return info


def generate_dmdimage_from_grill(path: Path) -> bool:
    """Fabrique le <DMDImage> manquant d'un directb2s FullDMD a partir du
    bandeau grill (les GrillHeight pixels du bas de la BackglassImage — le
    modele B2S classique : ce bandeau EST l'art FullDMD). Le plugin B2SLegacy
    standalone n'affiche l'art FullDMD que via <DMDImage> : sans lui, l'ecran
    FullDMD reste vide alors que l'art existe dans le fichier (cas Junk Yard).

    Tout est derive du directb2s lui-meme (GrillHeight + BackglassImage) :
    aucune valeur externe. Idempotent (ne fait rien si <DMDImage> existe),
    backup `.bak-grill2dmd` avant premiere modification, et toute erreur laisse
    le fichier intact (retour False -> la table suit la branche sans art)."""
    import base64
    import shutil
    import subprocess
    import tempfile

    try:
        raw = path.read_bytes()
    except OSError:
        return False

    encoding = None
    for candidate in ("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "latin-1"):
        try:
            text = raw.decode(candidate)
        except Exception:
            continue
        if "<DirectB2SData" in text:
            encoding = candidate
            break
    if not encoding:
        return False

    if re.search(r"<DMDImage\b", text, flags=re.IGNORECASE):
        return True

    grill_match = re.search(
        r"<GrillHeight\b[^>]*\bValue\s*=\s*[\"']\s*([0-9]+)\s*[\"']", text, flags=re.IGNORECASE
    )
    backglass = re.search(r'<BackglassImage\b[^>]*Value="([^"]+)"', text, flags=re.IGNORECASE)
    if not grill_match or not backglass:
        return False
    grill = int(grill_match.group(1))
    if grill <= 0:
        return False

    try:
        payload = backglass.group(1)
        for entity in ("&#xD;", "&#xA;", "&#13;", "&#10;"):
            payload = payload.replace(entity, "")
        payload = re.sub(r"\s+", "", payload)
        payload += "=" * ((4 - len(payload) % 4) % 4)
        image = base64.b64decode(payload)

        with tempfile.TemporaryDirectory(prefix="pincabos-grill2dmd-") as tmp:
            source = Path(tmp) / "backglass.img"
            strip = Path(tmp) / "grill.png"
            source.write_bytes(image)
            probe = subprocess.run(
                ["identify", "-format", "%w %h", str(source)],
                capture_output=True, text=True, timeout=60,
            )
            if probe.returncode != 0:
                return False
            width, height = (int(v) for v in probe.stdout.split()[:2])
            if grill >= height:
                return False
            crop = subprocess.run(
                ["convert", str(source), "-crop", f"{width}x{grill}+0+{height - grill}",
                 "+repage", str(strip)],
                capture_output=True, timeout=120,
            )
            if crop.returncode != 0 or not strip.is_file():
                return False
            # Letterbox au ratio de l'ecran FullDMD : B2S etire le DMDImage sur
            # toute la fenetre, donc un bandeau tres large (ex. 2560x625) serait
            # deforme verticalement (art ET DMD). Marges en quasi-noir :
            # invisibles a l'oeil mais exclues de la recherche de zone sombre,
            # l'AutoPos reste cale sur le bezel DMD de l'art.
            role = _FULLDMD_ROLE
            ratio = (role[3] / role[2]) if role else (9.0 / 16.0)
            canvas_h = int(round(width * ratio))
            if canvas_h > grill:
                pad = subprocess.run(
                    ["convert", str(strip), "-background", "rgb(46,48,52)",
                     "-gravity", "center", "-extent", f"{width}x{canvas_h}",
                     str(strip)],
                    capture_output=True, timeout=120,
                )
                if pad.returncode != 0:
                    return False
            strip64 = base64.b64encode(strip.read_bytes()).decode("ascii")
    except Exception:
        return False

    close = text.find("/>", backglass.end())
    if close < 0:
        return False
    close += 2
    tag = f'\r\n    <DMDImage Value="{strip64}" FileName="grill_auto.png" />'
    text = text[:close] + tag + text[close:]

    backup = path.with_name(path.name + ".bak-grill2dmd")
    try:
        if not backup.exists():
            shutil.copy2(path, backup)
        path.write_bytes(text.encode(encoding))
    except OSError:
        return False

    try:
        account = pwd.getpwnam("pinball")
        os.chown(path, account.pw_uid, account.pw_gid)
        if backup.exists():
            os.chown(backup, account.pw_uid, account.pw_gid)
    except (KeyError, PermissionError):
        pass
    return True


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
    info = directb2s_info(b2s)
    # FullDMD sans <DMDImage> mais avec grill : l'art FullDMD est le bandeau du
    # bas de la BackglassImage. On genere le <DMDImage> manquant (une fois,
    # backup .bak-grill2dmd) pour que B2S affiche cet art sur l'ecran FullDMD.
    if b2s and info["type3"] and not info["has_dmdimage"] and (info["grill"] or 0) > 0:
        if generate_dmdimage_from_grill(b2s):
            info = directb2s_info(b2s)
    grill = info["grill"] or 0
    # Le placement fin du DMD n'est PAS pilotable au pixel dans ce moteur : selon
    # le mode, le DMD est pose automatiquement (plein largeur, en haut si le
    # plugin ScoreView est off, centre s'il est on). On s'appuie donc sur ce
    # placement auto (universel, independant de la resolution) ; le calage precis
    # au cadre d'un art donne depend de l'art lui-meme (cf. AutoPos B2S).
    real_fill = STANDARD_DMD_FILL

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
    elif info["type3"] and (info["has_dmdimage"] or grill > 0) and not (
        info["has_dmdimage"] and grill == 0
    ):
        # Art FullDMD B2S disponible : soit une image DMD dediee (<DMDImage>),
        # soit le bandeau grill du bas de l'image backglass (GrillHeight>0, le
        # modele B2S classique : le bas de la BackglassImage EST l'art FullDMD,
        # cas Junk Yard). B2S affiche cet art sur l'ecran FullDMD et
        # l'auto-placement y pose le DMD live (cas T2, SW, Medieval Madness,
        # Junk Yard...). Comportement d'origine : on n'y touche pas. Universel
        # (B2S met a l'echelle selon la resolution). Seule exclusion : image DMD
        # avec GrillHeight=0, dont l'auto-placement degenere (branche suivante).
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
    elif info["type3"] and info["has_dmdimage"]:
        # FullDMD B2S avec image mais GrillHeight=0 : l'auto-placement B2S
        # degenere (DMD minuscule en haut, cas T3 Siggis). On active le plugin
        # ScoreView, qui affiche le DMD plein largeur CENTRE sur le FullDMD
        # (universel, independant de la resolution). Le placement fin n'est pas
        # pilotable : si l'art a son cadre DMD ailleurs qu'au centre, seul un
        # directb2s a cadre centre (ou GrillHeight>0) le calera parfaitement.
        patch_ini(
            table_ini,
            {
                "ScoreView": SCOREVIEW_WINDOW,
                "Plugin.B2SLegacy": B2S_FULLDMD_EXPLICIT,
                "Plugin.ScoreView": {"Enable": "1"},
            },
            remove_sections=("PinCabOS.ScoreViewWindow",),
        )
        mode = "B2S_FULLDMD_CENTRE" if DMD_RECT else "B2S_FULLDMD"
    elif info["type3"]:
        # DMDType=3 mais AUCUN art FullDMD (pas de <DMDImage> ET GrillHeight=0) :
        # rien a montrer cote B2S -> on affiche le VRAI DMD live sur le FullDMD
        # (4:1 centre), backglass B2S conserve.
        overwrite = {"Plugin.ScoreView": {"Enable": "1"}}
        if real_fill:
            overwrite["ScoreView"] = SCOREVIEW_WINDOW
            overwrite["Plugin.B2SLegacy"] = {**B2S_GEOMETRY, **real_fill}
        patch_ini(
            table_ini,
            overwrite,
            remove_sections=("PinCabOS.ScoreViewWindow",),
        )
        mode = "B2S_REALDMD" if real_fill else "B2S_FULLDMD_NOIMG"
    else:
        # Aucun FullDMD directb2s (DMDType != 3, ou pas de directb2s). DMD reel
        # classique : si un ecran FullDMD dedie existe, on l'y pose explicitement
        # (calage par-table sinon 4:1 centre) en reaffichant le DMD live. Sur un
        # cab sans FullDMD dedie, comportement minimal d'origine.
        overwrite = {"Plugin.ScoreView": {"Enable": "1"}}
        if real_fill:
            overwrite["ScoreView"] = SCOREVIEW_WINDOW
            overwrite["Plugin.B2SLegacy"] = real_fill
        patch_ini(
            table_ini,
            overwrite,
            remove_sections=("PinCabOS.ScoreViewWindow",),
        )
        mode = "REAL_DMD_FULLDMD" if real_fill else "STANDARD_NO_FULLDMD"

    print(f"MODE={mode}")
    print(f"DMD_INFO=type3={info['type3']} dmdimage={info['has_dmdimage']} grill={info['grill']}")
    print(f"TABLE={TARGET_VPX}")
    print(f"INI={table_ini}")
    print(f"DIRECTB2S={b2s or ''}")
PY

