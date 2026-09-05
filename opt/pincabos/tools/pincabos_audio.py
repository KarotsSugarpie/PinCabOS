"""Son du cab : sorties ALSA, test, mode VPX, application au premier démarrage.

PINCABOS_AUDIO_MODULE_V1

Module importable par l'assistant d'installation (session live, root, ALSA
seul) et par le premier démarrage (PipeWire de la session pinball). Une seule
source de vérité, celle de la page Audio du cab : /opt/pincabos/config/audio-router.json
(clés playfield_device / backbox_device en identifiants ALSA hw:C,D). L'installeur
y ajoute une clé « installer » (mode Sound3D, volume, noms ALSA) que le premier
démarrage traduit en noms de sorties VPX (VPX nomme ses sorties comme PipeWire,
pas comme ALSA) et en volume de session.

Écrit dans VPinballX.ini les mêmes clés que la page Audio, avec le même
commentaire daté : [Player] SoundDeviceBG, SoundDevice, Sound3D.
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

CONFIG = Path("/opt/pincabos/config/audio-router.json")
VPX_INI = Path("/home/pinball/.pincabos/vpx/VPinballX.ini")
FONCTION = "Audio SSF VPX Routing V2"          # même signature que la page Audio du cab
DEFAUTS = {
    "audio_mode": "dual", "audio_backend": "alsa", "backbox_device": "", "playfield_device": "",
    "surround_device": "", "bass_device": "", "ssf_mode": "7.1", "invert_lr": False,
    "invert_front_rear": False, "enable_bass": True, "night_mode": False,
}
# Intitulés VPinball : 4 et 5 sont des modes à six canaux, pas du 7.1.
SOUND3D = (
    ("0", "2 canaux, avant"), ("1", "2 canaux, arrière"),
    ("2", "jusqu'à 6 canaux, arrière au lockbar"), ("3", "jusqu'à 6 canaux, avant au lockbar"),
    ("4", "6 canaux, latéral et arrière, mixage historique"), ("5", "6 canaux, latéral et arrière, nouveau mixage"),
)
APLAY_RE = re.compile(r"^(?:card|carte)\s+(\d+)\s*:\s*(.+?)\s+\[(.+?)\]\s*,\s*(?:device|périphérique|peripherique)\s+(\d+)\s*:\s*(.+?)\s+\[(.+?)\]", re.IGNORECASE)
HW_RE = re.compile(r"^hw:(\d+),(\d+)$")


def executer(args, timeout=20, **kw):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout, **kw)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.SubprocessError) as exc:
        return 99, str(exc)


# ---------------------------------------------------------------- détection
PILOTES = ("snd_hda_intel", "snd_usb_audio")


def charger_pilotes(run=executer, pilotes=PILOTES) -> list:
    """Charge les pilotes son absents (media d installation : snd_hda_intel est
    sur liste noire au demarrage). Best effort, attend que les cartes remontent."""
    charges = []
    for p in pilotes:
        rc, _ = run(["modprobe", p], timeout=20)
        if rc == 0:
            charges.append(p)
    if charges:
        import time
        time.sleep(1.5)
    return charges


def peripheriques_alsa(texte: str) -> list:
    """Sorties de `aplay -l` (anglais ou français)."""
    out = []
    for ligne in texte.splitlines():
        m = APLAY_RE.match(ligne.strip())
        if not m:
            continue
        card, card_short, card_name, dev, dev_short, dev_name = m.groups()
        out.append({
            "id": f"hw:{card},{dev}", "card": int(card), "device": int(dev),
            "card_name": card_name.strip(), "device_name": dev_name.strip(),
            "label": f"{card_name.strip()} · {dev_name.strip()}",
            "hdmi": "hdmi" in dev_name.lower() or "hdmi" in dev_short.lower(),
            "digital": "digital" in dev_name.lower() or "iec958" in dev_name.lower(),
        })
    return out


def detecter(run=executer) -> list:
    rc, out = run(["aplay", "-l"], env={"LC_ALL": "C", "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"})
    return peripheriques_alsa(out) if rc == 0 else []


def proposer(devs: list) -> dict:
    """Première sortie analogique, sinon première HDMI, sinon la première ; backglass = la même."""
    choix = next((d for d in devs if not d["hdmi"] and not d["digital"]), None) \
        or next((d for d in devs if d["hdmi"]), None) or (devs[0] if devs else None)
    ident = choix["id"] if choix else ""
    return {"playfield": ident, "backbox": ident, "sound3d": "0", "volume": 70}


# ---------------------------------------------------------------- validation / config
def valider(choix, devs: list | None = None) -> tuple[list, dict]:
    erreurs = []
    if not isinstance(choix, dict):
        return ["choix audio invalide"], {}
    connus = {d["id"] for d in devs} if devs is not None else None
    ok = {}
    for cle in ("playfield", "backbox"):
        v = str(choix.get(cle) or "").strip()
        if v and not HW_RE.match(v):
            erreurs.append(f"{cle} : identifiant ALSA invalide {v}")
        elif v and connus is not None and v not in connus:
            erreurs.append(f"{cle} : sortie absente de la machine {v}")
        ok[cle] = v
    s3 = str(choix.get("sound3d", "0")).strip()
    if s3 not in {s for s, _ in SOUND3D}:
        erreurs.append(f"mode Sound3D inconnu {s3}")
    ok["sound3d"] = s3 if s3 in {s for s, _ in SOUND3D} else "0"
    try:
        vol = int(choix.get("volume", 70))
    except (TypeError, ValueError):
        vol = -1
    if not 0 <= vol <= 100:
        erreurs.append("volume hors de 0..100")
    ok["volume"] = max(0, min(100, vol))
    return erreurs, ok


def config_json(choix: dict, devs: list | None = None) -> dict:
    """Le audio-router.json de la cible (clés de la page Audio + section installer)."""
    par_id = {d["id"]: d for d in (devs or [])}
    cfg = dict(DEFAUTS)
    cfg["playfield_device"] = choix.get("playfield", "")
    cfg["backbox_device"] = choix.get("backbox", "") or choix.get("playfield", "")
    cfg["audio_mode"] = "dual" if cfg["backbox_device"] and cfg["backbox_device"] != cfg["playfield_device"] else "single"
    cfg["installer"] = {
        "sound3d": choix.get("sound3d", "0"), "volume": int(choix.get("volume", 70)),
        "playfield": par_id.get(cfg["playfield_device"], {}), "backbox": par_id.get(cfg["backbox_device"], {}),
        "written_at": datetime.now().isoformat(timespec="seconds"),
    }
    return cfg


# ---------------------------------------------------------------- test et volume (session live, ALSA)
def tester(ident: str, run=executer, canaux: int = 2) -> dict:
    if not HW_RE.match(ident or ""):
        return {"ok": False, "sortie": "identifiant ALSA invalide"}
    rc, out = run(["speaker-test", "-D", ident, "-c", str(canaux), "-t", "wav", "-l", "1"], timeout=40)
    return {"ok": rc == 0, "sortie": out.strip()[-300:]}


def volume_alsa(ident: str, pourcent: int, run=executer) -> dict:
    """Volume de la carte (amixer), best effort : premier contrôle utile de la carte."""
    m = HW_RE.match(ident or "")
    if not m:
        return {"ok": False, "sortie": "identifiant ALSA invalide"}
    carte = m.group(1)
    rc, out = run(["amixer", "-c", carte, "scontrols"])
    controles = re.findall(r"Simple mixer control '([^']+)'", out) if rc == 0 else []
    nom = next((c for c in ("Master", "PCM", "Headphone", "Speaker", "IEC958") if c in controles), controles[0] if controles else "")
    if not nom:
        return {"ok": False, "sortie": "aucun contrôle de volume sur cette carte"}
    rc, out = run(["amixer", "-c", carte, "sset", nom, f"{int(pourcent)}%", "unmute"])
    return {"ok": rc == 0, "sortie": (nom + " : " + out.strip()[-200:]) if rc == 0 else out.strip()[-200:]}


# ---------------------------------------------------------------- premier démarrage (PipeWire de la session)
def sinks_pactl(texte: str) -> list:
    """[{name, description, card, device}] depuis `pactl list sinks`."""
    sinks, cur = [], None
    for ligne in texte.splitlines():
        s = ligne.strip()
        if s.startswith("Name:"):
            cur = {"name": s.split(":", 1)[1].strip(), "description": "", "card": "", "device": ""}
            sinks.append(cur)
        elif cur is not None and s.startswith("Description:"):
            cur["description"] = s.split(":", 1)[1].strip()
        elif cur is not None and s.startswith("alsa.card ="):
            cur["card"] = s.split("=", 1)[1].strip().strip('"')
        elif cur is not None and s.startswith("alsa.device ="):
            cur["device"] = s.split("=", 1)[1].strip().strip('"')
    return sinks


def sink_pour(ident: str, sinks: list) -> dict | None:
    """Le sink PipeWire d'une sortie ALSA hw:C,D : carte ET device, sinon la carte."""
    m = HW_RE.match(ident or "")
    if not m:
        return None
    card, dev = m.group(1), m.group(2)
    return next((s for s in sinks if s["card"] == card and s["device"] == dev), None) \
        or next((s for s in sinks if s["card"] == card), None)


def commentaire() -> str:
    return f"; Modifié {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} par PinCabOS fonction({FONCTION})"


def poser_cle(lines: list, section: str, cle: str, valeur: str) -> list:
    """Même contrat que la page Audio : la clé sous un commentaire daté, un seul commentaire."""
    com = commentaire()
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
        lines += [com, f"[{section}]", f"{cle} = {valeur}"]
        return lines
    if fin is None:
        fin = len(lines)
    for i in range(debut + 1, fin):
        s = lines[i].strip()
        if s and not s.startswith((";", "#")) and "=" in s and s.split("=", 1)[0].strip().lower() == cle.lower():
            if i > 0 and "par PinCabOS fonction(" in lines[i - 1]:
                lines[i - 1] = com
            else:
                lines.insert(i, com)
                i += 1
            lines[i] = f"{cle} = {valeur}"
            return lines
    lines.insert(fin, com)
    lines.insert(fin + 1, f"{cle} = {valeur}")
    return lines


def ecrire_vpx(texte: str, backglass: str, playfield: str, sound3d: str) -> str:
    lines = texte.split("\n")
    for cle, val in (("SoundDeviceBG", backglass), ("SoundDevice", playfield), ("Sound3D", sound3d)):
        lines = poser_cle(lines, "Player", cle, val)
    return "\n".join(lines)


def commande_pinball(args: list) -> list:
    return ["runuser", "-u", "pinball", "--", "env", "XDG_RUNTIME_DIR=/run/user/1000",
            "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus", *args]


def appliquer_premier_demarrage(cfg: dict, run=executer, vpx_ini: Path = VPX_INI) -> list:
    """Traduit le choix de l'installeur (ALSA) en réglages de la session : VPX, sortie par défaut, volume."""
    journal = []
    inst = cfg.get("installer") or {}
    rc, out = run(commande_pinball(["/usr/bin/pactl", "list", "sinks"]), timeout=15)
    sinks = sinks_pactl(out) if rc == 0 else []
    if not sinks:
        journal.append("pactl : aucun sink (session PipeWire absente ?), VPX garde ses sorties par défaut")
    pf = sink_pour(cfg.get("playfield_device", ""), sinks)
    bg = sink_pour(cfg.get("backbox_device", ""), sinks) or pf
    if vpx_ini.is_file():
        texte = vpx_ini.read_text(encoding="utf-8", errors="replace")
        nouveau = ecrire_vpx(texte, bg["description"] if bg else "", pf["description"] if pf else "", str(inst.get("sound3d", "0")))
        if nouveau != texte:
            vpx_ini.write_text(nouveau, encoding="utf-8")
        journal.append(f"VPX : SoundDevice={pf['description'] if pf else '(défaut)'} ; SoundDeviceBG={bg['description'] if bg else '(défaut)'} ; Sound3D={inst.get('sound3d', '0')}")
    else:
        journal.append(f"VPX : {vpx_ini} absent, rien écrit")
    if pf:
        rc, out = run(commande_pinball(["/usr/bin/wpctl", "set-default", pf["name"]]), timeout=10)
        journal.append(f"sortie par défaut : {pf['name']} ({'ok' if rc == 0 else out.strip()[-80:]})")
        vol = int(inst.get("volume", 70))
        rc, out = run(commande_pinball(["/usr/bin/wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{vol}%"]), timeout=10)
        journal.append(f"volume : {vol} % ({'ok' if rc == 0 else out.strip()[-80:]})")
    return journal


def charger(chemin: Path = CONFIG) -> dict:
    try:
        data = json.loads(chemin.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}
