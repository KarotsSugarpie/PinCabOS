"""Étape Écrans de l'assistant : le DMD matériel quand il n'y a pas de full DMD.

PINCABOS_INSTALLEUR_DMD_V1

Le propriétaire a décoché « Full DMD » : son DMD est alors une matrice LED
(ZeDMD en USB ou Wi-Fi, PIN2DMD en USB) ou rien, auquel cas VPX dessine le DMD
sur le backglass (politique « sans full DMD » de pincabos_fronton).

Une seule source de vérité, celle de la page DMD du cab :
/opt/pincabos/config/zedmd.json, appliqué aux INI de VPX et VPinFE par
/opt/pincabos/tools/pincabos-zedmd, l'unique écrivain de ces sections. Ici on
détecte (même outil), on propose, on valide, on produit le JSON ; iso.sh le pose
sur la cible et lance `apply`, le premier démarrage le rejoue si besoin.

Ajouter un type de DMD = une entrée dans TYPES + sa prise en charge dans
pincabos-zedmd. Les cartes du marché (Arnoz : ZeDMD sur ESP32 WROOM ou S3,
PIN2DMD sur STM32 Nucleo) tiennent dans ces trois familles.
"""
from __future__ import annotations

import json
import re
import subprocess

TOOL = "/opt/pincabos/tools/pincabos-zedmd"
from pathlib import Path as _Path
DECOR_DMD = _Path(__file__).resolve().parent / "static" / "decor" / "dmd.jpg"   # PINCABOS_INSTALLEUR_DECOR_ROLES_V1

# id → mode de zedmd.json, famille, mode de détection, cible par défaut.
#  detection : "serie" = port série candidat (ESP32 natif ou pont CP210x/CH340),
#              "usb"   = périphérique USB brut (VID:PID connu de l'outil),
#              "manuel" = rien à détecter (adresse à saisir), None = rien.
TYPES = (
    {"id": "zedmd_usb", "mode": "usb", "famille": "zedmd", "detection": "serie", "targets": "game"},
    {"id": "zedmd_wifi", "mode": "wifi", "famille": "zedmd", "detection": "manuel", "targets": "both"},
    {"id": "pin2dmd", "mode": "pin2dmd", "famille": "pin2dmd", "detection": "usb", "targets": "game"},
    {"id": "none", "mode": "off", "famille": "", "detection": None, "targets": ""},
)
PAR_ID = {t["id"]: t for t in TYPES}

ADRESSE_RE = re.compile(r"^(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}"
                        r"|[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*)$")
PORT_RE = re.compile(r"^/dev/(?:tty(?:ACM|USB)\d+|serial/by-id/[A-Za-z0-9_.:-]+)$")


def executer(args, timeout=30):
    """(rc, sortie) de pincabos-zedmd ; rc 99 si l'outil manque."""
    try:
        p = subprocess.run([TOOL, *args], capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.SubprocessError) as exc:
        return 99, f"ERREUR: {exc}"


def _json(texte, defaut):
    try:
        return json.loads(texte)
    except ValueError:
        return defaut


def detecter(run=executer) -> dict:
    """Ports série classés par l'outil + PIN2DMD USB, et la proposition qui en découle."""
    rc, out = run(["detect"])
    serie = _json(out, []) if rc == 0 else []
    if not isinstance(serie, list):
        serie = []
    rc, out = run(["status"])
    st = _json(out, {}) if rc == 0 else {}
    pin2dmd = (st.get("pin2dmd") or {}).get("devices") or [] if isinstance(st, dict) else []
    candidats = [p for p in serie if isinstance(p, dict) and p.get("candidate")]
    return {
        "serie": [p for p in serie if isinstance(p, dict)],
        "candidats": candidats,
        "pin2dmd": pin2dmd,
        "disponible": rc != 99,
        "proposition": proposer(candidats, pin2dmd),
    }


def port_prefere(p: dict) -> str:
    """Le lien /dev/serial/by-id survit à l'ordre d'énumération ; sinon le nœud."""
    return p.get("by_id") or p.get("device") or ""


def proposer(candidats: list, pin2dmd: list) -> dict:
    """Ce qui est branché est proposé ; sans matériel, « aucun » (DMD sur le backglass)."""
    if pin2dmd:
        return {"type": "pin2dmd", "device": "", "wifi_addr": ""}
    if candidats:
        natifs = [p for p in candidats if p.get("family") == "esp32"] or candidats
        return {"type": "zedmd_usb", "device": port_prefere(natifs[0]), "wifi_addr": ""}
    return {"type": "none", "device": "", "wifi_addr": ""}


def valider(choix, detection: dict | None = None) -> tuple[list, dict]:
    """Erreurs + choix normalisé. Le port USB doit être un port série plausible ;
    s'il est vide, VPX cherche lui-même le ZeDMD (VPinFE n'aura pas le menu)."""
    erreurs = []
    if not isinstance(choix, dict):
        return ["choix DMD invalide"], {}
    t = PAR_ID.get(str(choix.get("type") or "none"))
    if t is None:
        return [f"type de DMD inconnu : {choix.get('type')!r}"], {}
    device = str(choix.get("device") or "").strip()
    addr = str(choix.get("wifi_addr") or "").strip()
    if t["id"] == "zedmd_usb":
        if device and not PORT_RE.match(device):
            erreurs.append(f"port série invalide : {device}")
        if device and detection is not None:
            connus = {p.get("device") for p in detection.get("serie", [])} | {p.get("by_id") for p in detection.get("serie", [])}
            if device not in connus:
                erreurs.append(f"port série absent de la machine : {device}")
    else:
        device = ""
    if t["id"] == "zedmd_wifi":
        if not addr or not ADRESSE_RE.match(addr) or len(addr) > 253:
            erreurs.append("adresse Wi-Fi du ZeDMD manquante ou invalide")
    else:
        addr = ""
    return erreurs, {"type": t["id"], "device": device, "wifi_addr": addr}


def config_json(choix: dict) -> dict:
    """Le zedmd.json que lisent pincabos-zedmd et la politique sans full DMD."""
    t = PAR_ID[choix["type"]]
    return {
        "mode": t["mode"],
        "device": choix.get("device", "") if t["id"] == "zedmd_usb" else "",
        "wifi_addr": choix.get("wifi_addr", "") if t["id"] == "zedmd_wifi" else "",
        "brightness": -1,
        "targets": t["targets"],
    }


def tester(choix: dict, run=executer, secondes: int = 3) -> dict:
    """Enregistre le choix dans la session live puis affiche la mire (ZeDMD seulement)."""
    erreurs, ok = valider(choix)
    if erreurs:
        return {"ok": False, "sortie": " ; ".join(erreurs)}
    if PAR_ID[ok["type"]]["famille"] != "zedmd":
        return {"ok": False, "sortie": "test disponible pour le ZeDMD seulement"}
    rc, out = run(["set", json.dumps(config_json(ok), ensure_ascii=False)])
    if rc != 0:
        return {"ok": False, "sortie": out.strip()}
    # PINCABOS_INSTALLEUR_DECOR_ROLES_V1 : le visuel « DMD » de l assistant plutot qu une mire
    visuel = DECOR_DMD if DECOR_DMD.is_file() else None
    if visuel is not None:
        rc, out = run(["image", str(visuel), str(int(secondes))], timeout=secondes + 30)
        if rc == 2 and "commande inconnue" in out:   # ancien pincabos-zedmd
            rc, out = run(["test", str(int(secondes))], timeout=secondes + 30)
    else:
        rc, out = run(["test", str(int(secondes))], timeout=secondes + 30)
    return {"ok": rc == 0, "sortie": out.strip()}
