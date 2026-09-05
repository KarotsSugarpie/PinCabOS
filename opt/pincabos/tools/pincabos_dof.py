"""DOF du cab : cartes de sortie détectées, activation, application au premier démarrage.

PINCABOS_DOF_MODULE_V1

Détection par l'outil dof-cabinet (identifiants USB des contrôleurs : DudesCab,
LedWiz, Pinscape, Ultimarc, Teensy et Wemos pour les rubans adressables).
L'installeur enregistre le choix « DOF activé » et les cartes vues dans
/opt/pincabos/config/dof/installer.json ; le premier démarrage pose les deux
interrupteurs que PinCabOS connaît : [Plugin.DOF] Enable de VPinballX.ini et
[DOF] enabledof de vpinfe.ini. Les toys carte par carte viennent à l'étape
Toys / LED (lot 2c) et sur la page /dof/hardware du cab.
"""
from __future__ import annotations

import importlib.util
import json
import re
from datetime import datetime
from pathlib import Path

OUTIL = Path("/opt/pincabos/tools/dof-cabinet/dof-cabinet.py")
CONFIG = Path("/opt/pincabos/config/dof/installer.json")
VPX_INI = Path("/home/pinball/.pincabos/vpx/VPinballX.ini")
VPINFE_INI = Path("/home/pinball/.config/vpinfe/vpinfe.ini")

_outil = None


def outil(chemin: Path = OUTIL):
    """Le module dof-cabinet.py chargé une fois (None s'il manque)."""
    global _outil
    if _outil is not None:
        return _outil
    if not chemin.is_file():
        return None
    spec = importlib.util.spec_from_file_location("pincabos_dofcab_outil", str(chemin))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _outil = mod
    return mod


def detecter(mod=None) -> list:
    mod = mod or outil()
    if mod is None:
        return []
    try:
        return [d for d in mod.detect() if isinstance(d, dict)]
    except Exception:
        return []


def resume(detectes: list) -> list:
    """Une ligne lisible par carte, et si DOF sait la configurer seul."""
    out = []
    for d in detectes:
        out.append({
            "dev": d.get("dev", ""), "kind": d.get("kind", ""), "model": d.get("model", ""),
            "serial": d.get("serial", ""), "vid": d.get("vid", ""),
            "auto_config": bool(d.get("auto_config")),
            "strip": d.get("auto_config") is False,          # Teensy / Wemos : rubans a declarer (lot 2c)
        })
    return out


def proposer(detectes: list) -> dict:
    return {"enabled": bool(detectes)}


def valider(choix) -> tuple[list, dict]:
    if not isinstance(choix, dict):
        return ["choix DOF invalide"], {}
    return [], {"enabled": bool(choix.get("enabled"))}


def config_json(choix: dict, detectes: list) -> dict:
    return {"enabled": bool(choix.get("enabled")), "detected": resume(detectes),
            "written_at": datetime.now().isoformat(timespec="seconds"), "source": "PinCabOS installer"}


# ---------------------------------------------------------------- interrupteurs
def poser_cle_ini(texte: str, section: str, cle: str, valeur: str) -> str:
    """Pose `cle = valeur` dans [section] (créée en fin de fichier si absente), sans rien d'autre."""
    lines = texte.split("\n")
    debut = fin = None
    for i, l in enumerate(lines):
        s = l.strip()
        if s.startswith("[") and s.endswith("]"):
            if debut is not None:
                fin = i
                break
            if s[1:-1].strip().lower() == section.lower():
                debut = i
    if debut is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines += [f"[{section}]", f"{cle} = {valeur}"]
        return "\n".join(lines)
    if fin is None:
        fin = len(lines)
    for i in range(debut + 1, fin):
        s = lines[i].strip()
        if s and not s.startswith((";", "#")) and "=" in s and s.split("=", 1)[0].strip().lower() == cle.lower():
            lines[i] = f"{cle} = {valeur}"
            return "\n".join(lines)
    # fin de section : avant les lignes vides qui la terminent
    j = fin
    while j > debut + 1 and not lines[j - 1].strip():
        j -= 1
    lines.insert(j, f"{cle} = {valeur}")
    return "\n".join(lines)


def appliquer_premier_demarrage(cfg: dict, vpx_ini: Path = VPX_INI, vpinfe_ini: Path = VPINFE_INI) -> list:
    actif = bool(cfg.get("enabled"))
    journal = []
    for chemin, section, cle, val in ((vpx_ini, "Plugin.DOF", "Enable", "1" if actif else "0"),
                                      (vpinfe_ini, "DOF", "enabledof", "true" if actif else "false")):
        if not chemin.is_file():
            journal.append(f"{chemin.name} absent, rien écrit")
            continue
        texte = chemin.read_text(encoding="utf-8", errors="replace")
        nouveau = poser_cle_ini(texte, section, cle, val)
        if nouveau != texte:
            chemin.write_text(nouveau, encoding="utf-8")
        journal.append(f"{chemin.name} : [{section}] {cle} = {val}")
    return journal


def charger(chemin: Path = CONFIG) -> dict:
    try:
        data = json.loads(chemin.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}
