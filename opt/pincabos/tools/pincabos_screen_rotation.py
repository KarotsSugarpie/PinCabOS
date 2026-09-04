#!/usr/bin/env python3
"""Rotation du playfield : une seule couche, la physique (PINCABOS_ROTATION_PHYSIQUE_V1).

Source de vérité : `playfield_rotation` dans /opt/pincabos/config/screens/screens.json
(0, 90, 180 ou 270 degrés). Elle est appliquée UNE fois, par xrandr, sur la
sortie qui joue le playfield — au démarrage de la session (lightdm), au
branchement d'un écran (hotplug) et depuis la page Écran. Tout ce qui dessine
sur cet écran (VPinFE, VPX, l'appli web, le splash) le voit déjà dans le bon
sens et ne doit PAS tourner à nouveau : VPinFE reçoit toujours
`tablerotation = 0`, VPX n'a aucune clé à recevoir.

Avant : la page Écran tournait la sortie ET écrivait la même valeur dans
VPinFE, qui la rendait une seconde fois (retourné = à l'envers), et le script
lightdm remettait « normal » à chaque boot. Retex Flo, 3.55.

Les trois scripts xrandr importent ce module pour ne pas dupliquer la table.
"""
from __future__ import annotations

ROTATIONS = (0, 90, 180, 270)
XRANDR = {0: "normal", 90: "right", 180: "inverted", 270: "left"}
LIBELLES = {
    0: "À l'endroit",
    180: "À l'envers (retourné de 180°)",
    90: "Tourné de 90° (avancé)",
    270: "Tourné de 270° (avancé)",
}
ROLES = ("playfield", "backglass", "fulldmd", "topper")


def _degres(brut) -> int:
    try:
        valeur = int(str(brut).strip() or 0) % 360
    except (TypeError, ValueError):
        return 0
    return valeur if valeur in ROTATIONS else 0


def rotation(data) -> int:
    """Rotation du playfield lue dans screens.json, tolérante (« 180 », 180, vide)."""
    if not isinstance(data, dict):
        return 0
    return _degres(data.get("playfield_rotation", 0))


def xrandr_rotate(rot) -> str:
    """Mot-clé xrandr --rotate pour une rotation en degrés."""
    try:
        rot = int(rot) % 360
    except (TypeError, ValueError):
        return "normal"
    return XRANDR.get(rot, "normal")


def role_rotation(role: str, data) -> int:
    """Rotation physique d'un rôle : `playfield_rotation` pour le playfield,
    `<rôle>_rotation` pour les autres (absent = 0). Un backglass ou un DMD
    monté de travers se règle ainsi sans toucher aux consommateurs, qui
    passent tous par ici."""
    if role == "playfield":
        return rotation(data)
    if not isinstance(data, dict) or role not in ROLES:
        return 0
    return _degres(data.get(f"{role}_rotation", 0))


def tourne(largeur: int, hauteur: int, rot) -> tuple[int, int]:
    """Taille vue par X après rotation : 90 et 270 échangent largeur et hauteur."""
    try:
        rot = int(rot) % 360
    except (TypeError, ValueError):
        rot = 0
    return (hauteur, largeur) if rot in (90, 270) else (largeur, hauteur)


def modes_candidats(mode: str, rot) -> list:
    """Le mode xrandr est celui de la DALLE ; une géométrie mémorisée après une
    rotation de 90/270 est inversée. On propose le mode tel quel puis inversé."""
    mode = str(mode or "")
    if "x" not in mode:
        return [mode] if mode else []
    l, h = mode.split("x", 1)
    if not (l.isdigit() and h.isdigit()):
        return [mode]
    inverse = f"{h}x{l}"
    try:
        rot = int(rot) % 360
    except (TypeError, ValueError):
        rot = 0
    if rot in (90, 270) and inverse != mode:
        return [mode, inverse]
    return [mode]


def libelle(rot) -> str:
    try:
        return LIBELLES.get(int(rot) % 360, LIBELLES[0])
    except (TypeError, ValueError):
        return LIBELLES[0]


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    chemin = Path(sys.argv[1] if len(sys.argv) > 1 else "/opt/pincabos/config/screens/screens.json")
    try:
        data = json.loads(chemin.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"NOGO: {chemin} illisible : {exc}", file=sys.stderr)
        sys.exit(1)
    rot = rotation(data)
    print(f"playfield_rotation = {rot} ({libelle(rot)}) -> xrandr --rotate {xrandr_rotate(rot)} ; VPinFE tablerotation = 0")
