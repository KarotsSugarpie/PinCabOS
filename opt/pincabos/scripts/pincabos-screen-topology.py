#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
try:
    import pincabos_ini
except ImportError:   # hors /opt (tests, depot) : le module vit a cote des outils
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "tools"))
    import pincabos_ini
from datetime import datetime, timezone
from pathlib import Path
# PINCABOS_PATHS_CONSUMER_V1
# pincabos_paths vit dans /opt/pincabos/tools ; hors cabinet (tests, CI), on
# le trouve a cote, dans le depot.
import os as _pco_os
import sys as _pco_sys
for _pco_dir in ("/opt/pincabos/tools",
                 _pco_os.path.join(_pco_os.path.dirname(_pco_os.path.abspath(__file__)), "..", "tools")):
    if _pco_dir not in _pco_sys.path:
        _pco_sys.path.insert(0, _pco_dir)
from pincabos_paths import PATHS

ROOT = Path("/opt/pincabos")
SCREENS = ROOT / "config/screens/screens.json"
BINDINGS = ROOT / "config/screens/display-role-bindings.json"
ALIASES = ROOT / "config/display-aliases.env"
RUNTIME = Path("/run/pincabos-screen-topology")
STATE = RUNTIME / "state.json"

VPINFE = Path(PATHS.vpinfe_ini)
# Avant le premier lancement, les preferences VPX sont encore dans le dossier
# versionne (le launcher les migre vers -PrefPath) : on suit le fichier present.
VPX = Path(PATHS.vpx_ini) if Path(PATHS.vpx_ini).exists() else Path(PATHS.vpx_legacy_pref) / "VPinballX.ini"
CAL_FULLDMD = ROOT / "config/fulldmd-calibration.json"
CAL_DMD = ROOT / "config/dmd-calibration.json"

ROLES = ("playfield", "backglass", "fulldmd", "topper")


def log(message):
    print(f"pincabos-screen-topology: {message}", flush=True)


def now():
    return datetime.now(timezone.utc).isoformat()


def restore_owner(path):
    """PINCABOS_OWNER_RESTORE_V1 : les fichiers config/appli appartiennent a
    pinball meme quand le moteur tourne en root (preflight, sudo adopt)."""
    try:
        import pwd
        info = pwd.getpwnam("pinball")
        os.chown(path, info.pw_uid, info.pw_gid)
    except Exception:
        pass


def atomic_write(path, content, mode=None):
    # PINCABOS_INI_UNIQUE_V1 : ecriture atomique de l ecrivain unique (mode
    # conserve, proprietaire du fichier conserve, rien si identique).
    changed = pincabos_ini.ecrire_texte(path, content)
    if changed and mode is not None:
        os.chmod(path, mode)
    return changed



def load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def xrandr_as_pinball(*args):
    command = [
        "/usr/sbin/runuser", "-u", "pinball", "--",
        "/usr/bin/env",
        "DISPLAY=:0",
        f"XAUTHORITY={PATHS.xauthority}",
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
            # PINCABOS_APP_SCREEN_INDEX_V1
            # Rang de la sortie tel que le serveur X la declare : c'est ce
            # rang que VPinFE utilise comme identifiant d'ecran.
            "app_index": len(monitors),
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

    # Un ecran ENTIEREMENT au-dessus du playfield est un topper : on le sort
    # du jeu avant de choisir backglass/fulldmd, sinon le tri geometrique le
    # prendrait pour le backglass.
    above = [
        item for item in remaining
        if item["y"] + item["height"] <= playfield["y"]
    ]
    topper = min(
        above,
        key=lambda item: (item["y"], item["x"], item["name"]),
    ) if above else None
    remaining = [
        item for item in remaining
        if not topper or item["name"] != topper["name"]
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

    # Pas d'ecran au-dessus mais un 4e ecran restant (topper pose a droite) :
    # l'ecran non attribue devient le topper.
    if topper is None:
        leftover = [
            item for item in remaining
            if not fulldmd or item["name"] != fulldmd["name"]
        ]
        topper = min(
            leftover,
            key=lambda item: (item["y"], item["x"], item["name"]),
        ) if leftover else None

    return {
        "playfield": playfield,
        "backglass": backglass,
        "fulldmd": fulldmd,
        "topper": topper,
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
    # match_count == 0 signifie qu AUCUN ecran attendu n est present :
    # c est une autre machine, quel que soit le nombre d ecrans (y compris 1).
    # La protection "perte partielle" repose sur match_count >= 1 et reste intacte.
    new_machine = not known or match_count == 0

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
    # PINCABOS_INI_UNIQUE_V1 : l ecrivain INI unique pose les cles (casse et
    # commentaires conserves, cle nouvelle en fin de section).
    ini = pincabos_ini.Ini(text)
    ini.poser_section(section, values)
    return ini.texte()


def update_global(text, key, value):
    # PINCABOS_INI_UNIQUE_V1 : la cle dans toutes les sections ou elle existe
    ini = pincabos_ini.Ini(text)
    ini.poser_partout(key, value)
    return ini.texte()


# PINCABOS_TOPOLOGY_CALIBRATIONS_V1
# La topologie est l'UNIQUE ecrivain des sections d'affichage des deux INI.
# Les rectangles calibres par l'utilisateur (zone visible du FullDMD, fenetre
# DMD) restent stockes dans les JSON de calibration — la topologie les relit
# et les ecrit avec les identifiants de roles, en une seule passe atomique.
# Avant, trois ecrivains (topologie, sync-dmd-calibrations, WebApp) posaient
# chacun leur morceau dans les memes sections, a des moments differents.
def load_calibration(path):
    """Rectangle calibre {x, y, width, height}, ou None si absent/invalide."""
    data = load_json(path, {})
    try:
        x = int(data.get("x"))
        y = int(data.get("y"))
        width = int(data.get("width"))
        height = int(data.get("height"))
    except (TypeError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    return {"x": x, "y": y, "width": width, "height": height}


def calibration_sections(cal_full, cal_dmd, stamp):
    """Cles derivees des calibrations pour [Displays] / [PinCabOs.*]."""
    displays = {}
    fulldmd = {}
    dmd = {}
    screens = {}
    if cal_full:
        x, y, w, h = cal_full["x"], cal_full["y"], cal_full["width"], cal_full["height"]
        x11 = f"{w}x{h}+{x}+{y}"
        displays.update({
            "fulldmdx": str(x), "fulldmdy": str(y),
            "fulldmdwidth": str(w), "fulldmdheight": str(h),
            "dmdwindowoverride": f"{x},{y},{w},{h}",
        })
        fulldmd.update({
            "x": str(x), "y": str(y), "width": str(w), "height": str(h),
            "geometry": x11, "updated_at": stamp,
        })
        screens.update({
            "fulldmd_x": str(x), "fulldmd_y": str(y),
            "fulldmd_width": str(w), "fulldmd_height": str(h),
            "fulldmd_geometry": x11,
        })
    if cal_dmd:
        x, y, w, h = cal_dmd["x"], cal_dmd["y"], cal_dmd["width"], cal_dmd["height"]
        x11 = f"{w}x{h}+{x}+{y}"
        displays.update({
            "dmdx": str(x), "dmdy": str(y),
            "dmdwidth": str(w), "dmdheight": str(h),
        })
        dmd.update({
            "x": str(x), "y": str(y), "width": str(w), "height": str(h),
            "geometry": x11, "updated_at": stamp,
        })
        screens.update({
            "dmd_x": str(x), "dmd_y": str(y),
            "dmd_width": str(w), "dmd_height": str(h),
            "dmd_geometry": x11,
        })
    return displays, fulldmd, dmd, screens


def apply_consumers(roles):
    """Prépare les prochains démarrages, sans redémarrer aucun service."""

    playfield = roles["playfield"]

    if not playfield["available"]:
        log("Playfield absent : fichiers applicatifs conservés sans modification.")
        return

    # Un role absent est DESACTIVE (id vide, convention du sanitize installeur),
    # jamais rabattu sur le playfield : le B2S par-dessus la table coute 10-20 fps.
    backglass = (
        roles["backglass"]
        if roles["backglass"]["available"]
        else None
    )

    dmd = (
        roles["fulldmd"]
        if roles["fulldmd"]["available"]
        else backglass
    )

    bg_id = str(backglass["screen_id"]) if backglass else ""
    dmd_id = str(dmd["screen_id"]) if dmd else ""

    full_enabled = "1" if roles["fulldmd"]["available"] else "0"

    cal_full = load_calibration(CAL_FULLDMD)
    cal_dmd = load_calibration(CAL_DMD)
    displays_cal, fulldmd_cal, dmd_cal, screens_cal = calibration_sections(
        cal_full, cal_dmd, now()
    )

    if VPINFE.exists():
        config = VPINFE.read_text(encoding="utf-8")

        config = update_section(config, "Displays", {
            "tablescreenid": str(playfield["screen_id"]),
            "bgscreenid": bg_id,
            "dmdscreenid": dmd_id,
            "fulldmdscreenid": dmd_id,
            **displays_cal,
        })

        config = update_section(config, "PinCabOs.FullDMD", {
            "enabled": full_enabled,
            "screen_id": dmd_id,
            **fulldmd_cal,
        })

        config = update_section(config, "PinCabOs.Screens", {
            "fulldmd_id": dmd_id,
            "dmd_id": dmd_id,
            **screens_cal,
        })

        config = update_section(config, "PinCabOs.DMD", {
            "enabled": full_enabled,
            "screen_id": dmd_id,
            **dmd_cal,
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
            bg_id,
        )

        config = update_global(
            config,
            "dmdscreenid",
            dmd_id,
        )

        config = update_global(
            config,
            "fulldmdscreenid",
            dmd_id,
        )

        # PINCABOS_VPX_REAL_KEYS_V1 : VPX 10.8.1 ignore les cles *screenid
        # (vocabulaire VPinFE) et pilote ses fenetres par sections nommees.
        # Role absent -> Output 0 (Disabled), sinon 1 (Floating).
        config = update_section(config, "Backglass", {
            "BackglassOutput": "1" if backglass else "0",
        })

        # PINCABOS_FRONTON_SANS_FULLDMD_V1 : `dmd` retombe sur le backglass pour
        # les identifiants VPinFE, mais la fenetre Score View n'existe que si un
        # ecran FullDMD est reellement la (deux ecrans : aucune fenetre).
        config = update_section(config, "ScoreView", {
            "ScoreViewOutput": "1" if roles["fulldmd"]["available"] else "0",
        })

        # Cabinet a 4 ecrans : la fenetre Topper de VPX suit le role topper
        # (le placeur one-shot la posera a sa geometrie, VPX ignorant les
        # positions demandees comme pour les autres fenetres secondaires).
        config = update_section(config, "Topper", {
            "TopperOutput": "1" if roles["topper"]["available"] else "0",
        })

        # Les memes sections que VPinFE : le moteur VPX les ignore, mais la
        # WebApp (resume de la page FullDMD) et les outils les lisent.
        config = update_section(config, "Displays", {
            "tablescreenid": str(playfield["screen_id"]),
            "bgscreenid": bg_id,
            "dmdscreenid": dmd_id,
            "fulldmdscreenid": dmd_id,
            **displays_cal,
        })
        config = update_section(config, "PinCabOs.FullDMD", {
            "enabled": full_enabled,
            "screen_id": dmd_id,
            **fulldmd_cal,
        })
        config = update_section(config, "PinCabOs.Screens", {
            "fulldmd_id": dmd_id,
            "dmd_id": dmd_id,
            **screens_cal,
        })
        config = update_section(config, "PinCabOs.DMD", {
            "enabled": full_enabled,
            "screen_id": dmd_id,
            **dmd_cal,
        })

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

    # Un role volontairement laisse vide dans l'interface Ecrans le RESTE.
    disabled = set()
    if isinstance(bindings, dict):
        disabled = {
            role for role in bindings.get("disabled_roles", [])
            if role != "playfield"
        }
    for role in disabled:
        selected[role] = None

    # Adoption progressive : un ecran present mais lie a aucun role, alors que
    # des roles sont vacants (ex: backglass branche apres une installation
    # mono-ecran) est adopte via l heuristique geometrique, et les bindings
    # sont etendus. Une perte d ecran ne re-affecte toujours rien.
    adopted = False
    if not new_machine and selected.get("playfield") is not None:
        bound_map = bindings.get("roles", {}) if isinstance(bindings, dict) else {}
        bound_edids = set(bound_map.values())
        unmatched = [
            m for m in monitors
            if m["edid_sha256"] not in bound_edids
        ]
        missing = [
            r for r in ROLES
            if selected.get(r) is None and r not in disabled
        ]
        if unmatched and missing:
            guess = infer_roles([selected["playfield"]] + unmatched)
            for r in missing:
                cand = guess.get(r)
                if cand and cand["name"] != selected["playfield"]["name"]:
                    selected[r] = cand
                    adopted = True
                    log(f"Adoption: {cand['name']} -> {r}")


    # PINCABOS_APP_SCREEN_INDEX_V1
    # Surtout pas enumerate(monitors) : monitors est trie de gauche a droite,
    # ce qui redonnerait 0/1/2 dans l'ordre du cabinet et non dans celui des
    # sorties. VPinFE lit l'ordre des sorties.
    app_indexes = {
        monitor["name"]: monitor["app_index"]
        for monitor in monitors
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

    if new_machine or adopted:
        bindings = {
            "version": 1,
            "bound_at": now(),
            "source": (
                "automatic-first-layout"
                if new_machine
                else "automatic-adopted-screen"
            ),
            "roles": {
                role: roles[role]["edid_sha256"]
                for role in ROLES
                if roles[role]["available"]
            },
            "disabled_roles": sorted(disabled),
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
    document["topper"] = roles["topper"]

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
        f"PINCABOS_TOPPER_AVAILABLE='{int(roles['topper']['available'])}'\n"
    )

    for role, label in (
        ("playfield", "PLAYFIELD"),
        ("backglass", "BACKGLASS"),
        ("fulldmd", "FULLDMD"),
        ("topper", "TOPPER"),
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
                "disabled_roles": [
                    role for role in ROLES if role not in adopted
                ],
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
