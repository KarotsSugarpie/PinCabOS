#!/usr/bin/env python3
"""pincabos_fronton : ce que le fronton du cabinet peut reellement afficher.

PINCABOS_FRONTON_V1

Source de verite :
  - /opt/pincabos/config/screens/screens.json  (roles playfield/backglass/fulldmd/topper)
  - /opt/pincabos/config/zedmd.json            (DMD materiel : ZeDMD USB/WiFi, PIN2DMD)

Pourquoi : les helpers de lancement (politique FullDMD, politique B2S, split
PuP, mode score) ecrivaient `ScoreViewOutput = 1` et une geometrie DMD B2S de
repli (+5760) meme sur un cabinet a DEUX ecrans (playfield + backglass, cas
Francois). VPX creait alors une fenetre Score View sans ecran, posee sur le
playfield ou le backglass. Ici, une seule reponse partagee : y a-t-il un
ecran FullDMD ? un DMD materiel ? et quelle politique INI en decoule.

Utilisation (helpers, tests) :
    sys.path.insert(0, "/opt/pincabos/tools"); import pincabos_fronton
    if pincabos_fronton.fulldmd_disponible() is False:
        sections = pincabos_fronton.politique_sans_fulldmd(pincabos_fronton.dmd_materiel())
"""
from __future__ import annotations

import json
from pathlib import Path

SCREENS_JSON = Path("/opt/pincabos/config/screens/screens.json")
ZEDMD_JSON = Path("/opt/pincabos/config/zedmd.json")

MODES_DMD_MATERIEL = ("usb", "wifi", "pin2dmd")


def _lire_json(chemin) -> dict | None:
    try:
        data = json.loads(Path(chemin).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def fulldmd_disponible(screens=SCREENS_JSON) -> bool | None:
    """Un ecran FullDMD dedie existe-t-il ?

    True / False d'apres screens.json ; None si screens.json est illisible ou
    absent : l'appelant conserve alors son comportement historique plutot que
    d'inventer une reponse.
    """
    data = _lire_json(screens)
    if data is None:
        return None
    resolution = data.get("role_resolution")
    if isinstance(resolution, dict) and "full_dmd_available" in resolution:
        return bool(resolution["full_dmd_available"])
    fulldmd = data.get("fulldmd")
    if not isinstance(fulldmd, dict):
        return False
    if "available" in fulldmd:
        return bool(fulldmd["available"])
    try:
        return int(fulldmd.get("width") or 0) > 0 and int(fulldmd.get("height") or 0) > 0
    except (TypeError, ValueError):
        return False


def dmd_materiel(zedmd=ZEDMD_JSON) -> bool:
    """Un DMD physique (ZeDMD USB/WiFi, PIN2DMD) est-il configure ?"""
    data = _lire_json(zedmd)
    if data is None:
        return False
    return str(data.get("mode", "off")).strip().lower() in MODES_DMD_MATERIEL


def politique_sans_fulldmd(dmd_materiel_present: bool) -> dict[str, dict[str, str]]:
    """Sections INI VPX a imposer sur un fronton SANS ecran FullDMD.

    - aucune fenetre Score View : elle n'aurait pas d'ecran, VPX la poserait
      sur le playfield ou le backglass ;
    - pas de fenetre DMD B2S separee ni de DMD PinMAME flottant ;
    - le DMD live est dessine SUR le backglass (BackglassDMDOverlay), sauf si
      un DMD materiel s'en charge deja.
    """
    return {
        "ScoreView": {"ScoreViewOutput": "0"},
        "Plugin.ScoreView": {"Enable": "0"},
        "Plugin.B2SLegacy": {
            "B2SHideB2SDMD": "1",
            "B2SHideDMD": "1",
            "ScoreViewDMDOverlay": "0",
            "BackglassDMDOverlay": "0" if dmd_materiel_present else "1",
            "BackglassDMDAutoPos": "1",
        },
    }


def fusionner(overwrite: dict, politique: dict) -> dict:
    """overwrite + politique, la politique ayant le dernier mot (copie)."""
    resultat = {section: dict(valeurs) for section, valeurs in overwrite.items()}
    for section, valeurs in politique.items():
        resultat.setdefault(section, {}).update(valeurs)
    return resultat


if __name__ == "__main__":
    fd = fulldmd_disponible()
    print(f"fulldmd_disponible={fd} dmd_materiel={dmd_materiel()}")
    if fd is False:
        print(json.dumps(politique_sans_fulldmd(dmd_materiel()), indent=2))
