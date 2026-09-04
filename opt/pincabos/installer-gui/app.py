#!/usr/bin/env python3
"""PinCabOS GUI Installer — wizard Flask (charte WebApp).

Deux modes :
  PCO_DEMO=1  -> disques factices, installation simulee (demo navigateur / dev)
  reel        -> ecrit les reponses puis pilote le moteur d'install existant
                 (contrat "answers file" partage TUI/GUI).
"""
import json
import os
import re
import shlex
import subprocess
import time
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request

import screens as pco_screens  # PINCABOS_INSTALLEUR_ECRANS_V1

# PINCABOS_INSTALLEUR_RESEAU_V1 : le moteur réseau du cab (nmcli) sert aussi à
# l'assistant. Absent de la session (ISO au modèle classique) : l'étape se
# présente comme indisponible et laisse continuer.
import sys as _sys
if "/opt/pincabos/tools" not in _sys.path:
    _sys.path.insert(0, "/opt/pincabos/tools")
try:
    import pincabos_network as pco_net
except Exception:  # pragma: no cover
    pco_net = None

BASE = Path(__file__).resolve().parent
DEMO = os.environ.get("PCO_DEMO") == "1"
RUN_DIR = Path(os.environ.get("PCO_RUN_DIR", "/run/pincabos"))
ANSWERS = RUN_DIR / "gui-answers.env"
INSTALL_LOG = RUN_DIR / "install.log"
ENGINE = "/usr/local/sbin/pincabos-live-installer"

app = Flask(__name__)
I18N = json.loads((BASE / "i18n.json").read_text(encoding="utf-8"))

REGIONAL_DEFAULTS = {
    "fr": {"locale": "fr_FR.UTF-8", "xkb": "fr", "tz": "Europe/Paris"},
    "en": {"locale": "en_US.UTF-8", "xkb": "us", "tz": "America/New_York"},
    "de": {"locale": "de_DE.UTF-8", "xkb": "de", "tz": "Europe/Berlin"},
    "it": {"locale": "it_IT.UTF-8", "xkb": "it", "tz": "Europe/Rome"},
    "es": {"locale": "es_ES.UTF-8", "xkb": "es", "tz": "Europe/Madrid"},
}


@app.route("/")
def index():
    return render_template("wizard.html", i18n=json.dumps(I18N),
                           defaults=json.dumps(REGIONAL_DEFAULTS), demo=DEMO)


def disques_reels():
    """Disques que cette machine porte reellement.

    PINCABOS_WIZARD_LOCAL_ONLY_V1

    Sert a la fois a remplir la liste et a valider le choix : une expression
    reguliere accepte /dev/nvme0n1 sur une machine qui n'en a pas, une
    enumeration decrit la machine devant soi.
    """
    if DEMO:
        return [
            {"dev": "/dev/nvme0n1", "size": "931,5G", "model": "Samsung 980 PRO 1TB"},
            {"dev": "/dev/sda", "size": "223,6G", "model": "Crucial BX500 240GB"},
        ]
    out = subprocess.run(
        ["lsblk", "-J", "-d", "-o", "NAME,SIZE,TYPE,MODEL"],
        capture_output=True, text=True, timeout=10).stdout
    found = []
    for d in json.loads(out).get("blockdevices", []):
        if d.get("type") == "disk" and not d["name"].startswith(("loop", "sr", "zram")):
            found.append({"dev": "/dev/" + d["name"], "size": d.get("size", "?"),
                          "model": (d.get("model") or "").strip() or "Disque"})
    return found


@app.route("/api/disks")
def disks():
    return jsonify(disques_reels())


# PINCABOS_INSTALLEUR_ECRANS_V1
# L'étape Écrans : la session d'installation voit les mêmes dalles que le
# système installé. On les numérote, on attribue les rôles, on applique la
# disposition tout de suite (le propriétaire voit), et le résultat part sur la
# cible au format que lit tout PinCabOS (screens.json + liaisons EDID).
ECRANS_DEMO = [
    {"app_index": 0, "name": "HDMI-0", "x": 0, "y": 0, "width": 3840, "height": 2160, "area": 3840 * 2160, "is_primary": True,
     "raw": "HDMI-0 connected primary 3840x2160+0+0", "rotation": 0, "preferred": "3840x2160", "modes": ["3840x2160", "1920x1080"], "mm": (1600, 900), "edid_sha256": "demo-pf"},
    {"app_index": 1, "name": "DP-0", "x": 5760, "y": 0, "width": 1920, "height": 480, "area": 1920 * 480, "is_primary": False,
     "raw": "DP-0 connected 1920x480+5760+0", "rotation": 0, "preferred": "1920x480", "modes": ["1920x480"], "mm": (600, 150), "edid_sha256": "demo-dmd"},
    {"app_index": 2, "name": "DP-2", "x": 3840, "y": 0, "width": 1920, "height": 1080, "area": 1920 * 1080, "is_primary": False,
     "raw": "DP-2 connected 1920x1080+3840+0", "rotation": 0, "preferred": "1920x1080", "modes": ["1920x1080"], "mm": (600, 340), "edid_sha256": "demo-bg"},
]
KIOSK_TARGET = RUN_DIR / "kiosk-target"


def ecrans_detectes():
    if DEMO:
        return [dict(m) for m in ECRANS_DEMO]
    return pco_screens.decouvrir()


def _roles_depuis(a):
    roles = a.get("roles") if isinstance(a, dict) else None
    if not isinstance(roles, dict):
        return None
    return {r: str(roles.get(r) or "") for r in pco_screens.ROLES}


def _rotation_depuis(a):
    try:
        rot = int(a.get("rotation", 0))
    except (TypeError, ValueError):
        return None
    return rot if rot in pco_screens.ROTATIONS else None


@app.route("/api/screens")
def screens_list():
    try:
        mons = ecrans_detectes()
    except Exception as exc:
        return jsonify({"error": "no-x", "detail": str(exc), "monitors": [], "roles": {}}), 200
    roles = pco_screens.proposer_roles(mons)
    pf = next((m for m in mons if m["name"] == roles.get("playfield")), None)
    return jsonify({"monitors": mons, "roles": roles, "rotation": pf["rotation"] if pf else 0, "demo": DEMO})


@app.route("/api/screens/identify", methods=["POST"])
def screens_identify():
    a = request.get_json(force=True, silent=True) or {}
    roles = _roles_depuis(a) or {}
    try:
        mons = ecrans_detectes()
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 200
    if DEMO:
        return jsonify({"ok": True, "demo": True})
    libelles = a.get("labels") if isinstance(a.get("labels"), dict) else None
    res = pco_screens.identifier(mons, roles, int(a.get("seconds", 6)), libelles=libelles)
    return jsonify(res)


@app.route("/api/screens/apply", methods=["POST"])
def screens_apply():
    """Le bouton « Tester la disposition » : applique réellement, l'assistant suit le playfield."""
    a = request.get_json(force=True, silent=True) or {}
    roles, rotation = _roles_depuis(a), _rotation_depuis(a)
    if roles is None or rotation is None:
        return jsonify({"ok": False, "erreurs": ["rôles ou rotation invalides"]}), 400
    try:
        mons = ecrans_detectes()
    except Exception as exc:
        return jsonify({"ok": False, "erreurs": [str(exc)]}), 200
    erreurs = pco_screens.valider_roles(roles, mons)
    if erreurs:
        return jsonify({"ok": False, "erreurs": erreurs}), 200
    if DEMO:
        return jsonify({"ok": True, "demo": True, "disposition": pco_screens.disposition(mons, roles, rotation)})
    res = pco_screens.appliquer(mons, roles, rotation)
    if res.get("ok"):
        try:
            RUN_DIR.mkdir(parents=True, exist_ok=True)
            KIOSK_TARGET.write_text(roles["playfield"] + "\n", encoding="utf-8")
        except OSError:
            pass
    return jsonify(res)


# ---------------------------------------------------------------- Réseau
RESEAU_DEMO = {
    "interfaces": [
        {"device": "eno1", "type": "ethernet", "state": "100 (connected)", "method": "auto", "address": "172.18.40.80/24",
         "gateway": "172.18.40.254", "dns": ["172.18.41.254"], "hwaddr": "04:D4:C4:A8:65:ED",
         "proposition": {"address": "172.18.40.80/24", "gateway": "172.18.40.254", "dns": ["172.18.41.254"], "source": "dhcp"}},
        {"device": "wlp3s0", "type": "wifi", "state": "30 (disconnected)", "method": "", "address": "", "gateway": "", "dns": [], "hwaddr": "",
         "proposition": {"address": "", "gateway": "", "dns": ["9.9.9.9", "1.1.1.1"], "source": "aucune"}},
    ],
    "wifi": {"present": True, "radio": "enabled", "devices": ["wlp3s0"], "capacites": {"2ghz": True, "5ghz": False, "wpa2": True}},
    "hostname": "pincabos-installer", "legacy": False, "disponible": True,
}
RESEAU_SCAN_DEMO = [
    {"ssid": "Maison", "signal": 82, "security": "WPA2", "mode": "wpa-psk", "in_use": False, "freq": 2437, "compatible": True, "raison": ""},
    {"ssid": "Cafe", "signal": 70, "security": "", "mode": "open", "in_use": False, "freq": 2462, "compatible": True, "raison": ""},
    {"ssid": "Neuf", "signal": 66, "security": "WPA3", "mode": "sae", "in_use": False, "freq": 5240, "compatible": False, "raison": "réseau 5 GHz, carte 2,4 GHz seulement"},
]


def reseau_etat():
    if DEMO:
        return json.loads(json.dumps(RESEAU_DEMO))
    if pco_net is None:
        return {"interfaces": [], "wifi": {"present": False, "devices": []}, "hostname": "", "legacy": False, "disponible": False}
    r = pco_net.resume(run=pco_net.executer)
    r["disponible"] = True
    return r


@app.route("/api/network")
def network_status():
    try:
        return jsonify(reseau_etat())
    except Exception as exc:
        return jsonify({"interfaces": [], "wifi": {"present": False, "devices": []}, "disponible": False, "error": str(exc)})


@app.route("/api/network/wifi-scan")
def network_wifi_scan():
    if DEMO:
        return jsonify({"present": True, "reseaux": RESEAU_SCAN_DEMO})
    if pco_net is None:
        return jsonify({"present": False, "reseaux": []})
    mat = pco_net.wifi_materiel(run=pco_net.executer)
    if not mat["present"] or not mat["devices"]:
        return jsonify({"present": False, "reseaux": []})
    caps = pco_net.wifi_capacites(mat["devices"][0], run=pco_net.executer)
    return jsonify({"present": True, "reseaux": pco_net.wifi_scan(run=pco_net.executer, rescan=True, caps=caps), "capacites": caps})


@app.route("/api/network/apply", methods=["POST"])
def network_apply():
    """DHCP ou IP fixe, appliqué tout de suite dans la session : le résultat se voit."""
    a = request.get_json(force=True, silent=True) or {}
    iface = str(a.get("iface", "")).strip()
    mode = str(a.get("mode", "dhcp")).strip()
    if DEMO:
        if mode == "static":
            v = pco_net_valider(a)
            if v["erreurs"]:
                return jsonify({"ok": False, "journal": ["NOGO: " + e for e in v["erreurs"]]})
        return jsonify({"ok": True, "demo": True, "journal": [f"GO: {iface} en {'IP fixe' if mode == 'static' else 'DHCP'} (démo)"]})
    if pco_net is None:
        return jsonify({"ok": False, "journal": ["NOGO: réseau indisponible dans cette session"]})
    if iface not in [d["device"] for d in pco_net.peripheriques(run=pco_net.executer)]:
        return jsonify({"ok": False, "journal": [f"NOGO: interface inconnue : {iface or '(vide)'}"]})
    journal = []
    if pco_net.legacy_present(iface):
        journal += pco_net.legacy_takeover(iface)
    if mode == "static":
        v = pco_net_valider(a)
        if v["erreurs"]:
            return jsonify({"ok": False, "journal": journal + ["NOGO: " + e for e in v["erreurs"]]})
        journal += pco_net.appliquer_fixe(iface, v["address"], v["gateway"], v["dns"], run=pco_net.executer)
    else:
        journal += pco_net.appliquer_dhcp(iface, run=pco_net.executer)
    ok = not any(l.startswith("NOGO") for l in journal)
    etat = pco_net.etat(iface, run=pco_net.executer) if ok else {}
    return jsonify({"ok": ok, "journal": journal, "etat": etat})


def pco_net_valider(a):
    if pco_net is not None:
        return pco_net.valider_fixe(a.get("address", ""), a.get("gateway", ""), a.get("dns", ""))
    # démo sans module : validation minimale
    import ipaddress
    erreurs = []
    try:
        ipaddress.IPv4Interface(str(a.get("address", "")))
    except ValueError:
        erreurs.append("adresse invalide")
    if not str(a.get("gateway", "")).strip():
        erreurs.append("passerelle manquante")
    return {"erreurs": erreurs, "address": a.get("address", ""), "gateway": a.get("gateway", ""), "dns": a.get("dns", "")}


@app.route("/api/network/wifi-join", methods=["POST"])
def network_wifi_join():
    a = request.get_json(force=True, silent=True) or {}
    if DEMO:
        ssid = str(a.get("ssid", "")).strip()
        if not ssid:
            return jsonify({"ok": False, "journal": ["NOGO: SSID manquant"]})
        if ssid == "Neuf":
            return jsonify({"ok": False, "journal": ["NOGO: réseau « Neuf » incompatible avec la carte : réseau 5 GHz, carte 2,4 GHz seulement"]})
        return jsonify({"ok": True, "demo": True, "journal": [f"GO: connecté à « {ssid} » (démo)"]})
    if pco_net is None:
        return jsonify({"ok": False, "journal": ["NOGO: réseau indisponible dans cette session"]})
    journal = pco_net.wifi_join(str(a.get("ssid", "")), str(a.get("password", "")), str(a.get("security", "auto") or "auto"),
                                str(a.get("identity", "")), bool(a.get("hidden")), run=pco_net.executer)
    return jsonify({"ok": not any(l.startswith("NOGO") for l in journal), "journal": journal})


def reseau_vers_fichiers():
    """Photographie les profils NetworkManager de la session (netplan 90-NM-*.yaml,
    clés Wi-Fi comprises) et la liste des interfaces configurées, pour la cible."""
    import shutil
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    dossier = RUN_DIR / "gui-netplan"
    shutil.rmtree(dossier, ignore_errors=True)
    dossier.mkdir(parents=True)
    copies = []
    if not DEMO:
        for f in sorted(Path("/etc/netplan").glob("90-NM-*.yaml")):
            shutil.copy2(f, dossier / f.name)
            copies.append(f.name)
    etat = reseau_etat()
    data = {
        "source": "PinCabOS installer network step",
        "interfaces": [{"device": i["device"], "type": i["type"], "method": i.get("method", ""), "address": i.get("address", "")}
                       for i in etat.get("interfaces", [])],
        "netplan_files": copies,
        "wifi_present": bool(etat.get("wifi", {}).get("present")),
    }
    f = RUN_DIR / "gui-network.json"
    f.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"network_file": str(f), "netplan_dir": str(dossier)}


def ecrans_vers_fichiers(a):
    """Les choix validés deviennent screens.json + liaisons EDID, pour la cible."""
    roles, rotation = _roles_depuis(a), _rotation_depuis(a)
    if roles is None or rotation is None:
        return {"error": "bad-screens"}
    mons = ecrans_detectes()
    erreurs = pco_screens.valider_roles(roles, mons)
    if erreurs:
        return {"error": "bad-screens", "detail": erreurs}
    data = pco_screens.screens_json(mons, roles, rotation)
    liaisons = pco_screens.bindings_json(data)
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    f1 = RUN_DIR / "gui-screens.json"
    f2 = RUN_DIR / "gui-screens-bindings.json"
    f1.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    f2.write_text(json.dumps(liaisons, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"screens_file": str(f1), "bindings_file": str(f2), "orient": pco_screens.code_orient(rotation)}


@app.route("/api/keyboard", methods=["POST"])
def keyboard():
    """Applique le layout au serveur X du kiosk (l'utilisateur tape ce qu'il voit)."""
    a = request.get_json(force=True)
    xkb = a.get("xkb", "us")
    variant = a.get("variant", "")
    if not re.fullmatch(r"[a-z]{2,3}", xkb):
        return jsonify({"error": "bad-xkb"}), 400
    if DEMO:
        return jsonify({"ok": True, "demo": True})
    cmd = ["setxkbmap", "-display", ":1", xkb]
    if variant and re.fullmatch(r"[a-z0-9_-]+", variant):
        cmd += ["-variant", variant]
    subprocess.run(cmd, timeout=10, check=False)
    return jsonify({"ok": True})


# PINCABOS_ANSWERS_QUOTING_V1
# Ce que le moteur sait faire de chaque reponse. Une valeur hors de ce moule
# est refusee : la corriger reviendrait a deviner l'intention.
ANSWER_RULES = {
    "lang": re.compile(r"^[a-z]{2,3}$"),
    "locale": re.compile(r"^[A-Za-z][A-Za-z0-9._@-]{1,31}$"),
    # PINCABOS_ANSWERS_QUOTING_V2 — base.lst contient latam, brai, custom.
    "xkb": re.compile(r"^[a-z]{2,8}$"),
    "xkb_variant": re.compile(r"^[a-z0-9_-]{0,31}$"),
    "tz": re.compile(r"^[A-Za-z][A-Za-z0-9_+-]{0,31}(/[A-Za-z0-9_+-]{1,31}){0,2}$"),
    "orient": re.compile(r"^[1-4]$"),
    "mode": re.compile(r"^[1-3]$"),
    "disk": re.compile(r"^/dev/[a-z0-9]+$"),
    # PINCABOS_INSTALLEUR_ECRANS_V1 : fichiers produits ici même, chemins fixes
    # PINCABOS_INSTALLEUR_ECRANS_V1 : chemins fixes des fichiers produits par
    # l'étape Écrans (le vérificateur CI relit ces moules avec `re` seul).
    "screens_file": re.compile(r"^/run/pincabos/gui-screens\.json$"),
    "bindings_file": re.compile(r"^/run/pincabos/gui-screens-bindings\.json$"),
    # PINCABOS_INSTALLEUR_RESEAU_V1 : idem, produits par l'étape Réseau
    "network_file": re.compile(r"^/run/pincabos/gui-network\.json$"),
    "netplan_dir": re.compile(r"^/run/pincabos/gui-netplan$"),
}


ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]|\x1b[c()][0-9A-B]?")

# Barre de progression d'unsquashfs : [===|   ]  1234/5678  27%
UNSQUASHFS_RE = re.compile(r"\]\s+\d+\s*/\s*\d+\s+(\d+)%")
DEPLOY_FROM, DEPLOY_TO = 45, 72


@app.route("/api/install", methods=["POST"])
def install():
    a = request.get_json(force=True)
    if a.get("confirm", "").strip().upper() != "INSTALL PINCABOS":
        return jsonify({"error": "bad-confirm"}), 400
    # PINCABOS_WIZARD_LOCAL_ONLY_V1
    # Le disque demande doit figurer parmi ceux que la machine porte : la
    # forme seule ne dit pas si le disque existe.
    if a.get("disk", "") not in {d["dev"] for d in disques_reels()}:
        return jsonify({"error": "bad-disk"}), 400

    # PINCABOS_ANSWERS_QUOTING_V1
    # Toutes les reponses sont confrontees a leur moule, pas seulement le
    # disque : l'installateur charge ce fichier avec « . », en root.
    reponses = {}
    for cle, moule in ANSWER_RULES.items():
        if cle not in a:
            continue
        valeur = str(a[cle])
        if not moule.match(valeur):
            return jsonify({"error": f"bad-{cle.replace('_', '-')}"}), 400
        reponses[cle] = valeur

    # PINCABOS_INSTALLEUR_ECRANS_V1 : l'étape Écrans remplace la vignette
    # d'orientation ; le code « orient » du moteur (fbcon, splash) en dérive.
    if isinstance(a.get("screens"), dict):
        res = ecrans_vers_fichiers(a["screens"])
        if "error" in res:
            return jsonify(res), 400
        # Ces trois valeurs viennent d'ici, pas du client : les fichiers sont
        # écrits par ecrans_vers_fichiers() sous RUN_DIR, le code orient est
        # dérivé de la rotation ; shlex.quote les rend inertes comme le reste.
        for cle in ("screens_file", "bindings_file", "orient"):
            reponses[cle] = res[cle]

    # PINCABOS_INSTALLEUR_RESEAU_V1 : ce que la session a configuré part sur la cible
    if a.get("network") is not False:
        try:
            reponses.update(reseau_vers_fichiers())
        except Exception as exc:
            app.logger.warning("réseau non photographié : %s", exc)

    if "mode" not in reponses:
        return jsonify({"error": "bad-mode"}), 400

    RUN_DIR.mkdir(parents=True, exist_ok=True)
    # shlex.quote produit une chaine que le shell relit comme une donnee et
    # jamais comme du code : la seconde barriere, si la premiere cedait.
    ANSWERS.write_text("".join(
        f"PCO_ANS_{cle.upper()}={shlex.quote(valeur)}\n"
        for cle, valeur in reponses.items()), encoding="utf-8")
    if DEMO:
        return jsonify({"ok": True, "demo": True})
    subprocess.Popen(  # le moteur existant, en mode reponses (contrat partage TUI/GUI)
        ["systemd-run", "--unit=pincabos-gui-install", "--collect",
         f"--setenv=PCO_ANSWERS={ANSWERS}", "--setenv=TERM=linux",
         "sh", "-c", f"{ENGINE} >{INSTALL_LOG} 2>&1"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return jsonify({"ok": True})


# Jalons du moteur -> pourcentage (marqueurs reels de ses pco_step/pco_go)
PHASES = [
    ("Regional configuration accepted", 5),
    ("Unmounting target disk", 8),
    ("Partitioning disk GPT", 12),
    ("payload", 45),
    ("Payload PinCabOS install", 72),
    ("Final boot refresh", 85),
    ("GRUB", 92),
    ("PINCABOS_INSTALL_COMPLETE", 100),
]


@app.route("/api/progress")
def progress():
    def stream():
        if DEMO:
            steps = [(5, "Vérification du payload"), (14, "Partitionnement"),
                     (30, "Extraction du payload"), (55, "Extraction du payload"),
                     (72, "Configuration régionale"), (85, "Initramfs cible"),
                     (95, "GRUB"), (100, "Terminé")]
            for pct, label in steps:
                yield f"data: {json.dumps({'pct': pct, 'label': label})}\n\n"
                time.sleep(1.6)
            return
        pos = 0
        pct = 2
        envoye = 0
        while pct < 100:
            if INSTALL_LOG.exists():
                text = INSTALL_LOG.read_text(errors="replace")
                new, pos = text[pos:], len(text)
                for line in new.splitlines():
                    for marker, p in PHASES:
                        if marker.lower() in line.lower():
                            pct = max(pct, p)
                    # progression fine pendant l'extraction du rootfs
                    if DEPLOY_FROM <= pct < DEPLOY_TO:
                        m = UNSQUASHFS_RE.search(line)
                        if m:
                            part = min(100, int(m.group(1)))
                            pct = max(pct, DEPLOY_FROM
                                      + (DEPLOY_TO - DEPLOY_FROM) * part // 100)
                    # log lisible : sans ANSI, sans lignes decoratives ni art figlet
                    clean = ANSI_RE.sub("", line).strip()
                    if not clean:
                        continue
                    readable = sum(c.isalnum() or c in " ,.:;()/'\"-_" for c in clean)
                    if readable / len(clean) < 0.6:
                        continue
                    envoye = pct
                    yield f"data: {json.dumps({'pct': pct, 'log': clean})}\n\n"
            # la barre avance meme si aucune ligne lisible n'est apparue
            if pct != envoye:
                envoye = pct
                yield f"data: {json.dumps({'pct': pct})}\n\n"
            time.sleep(1)
        yield f"data: {json.dumps({'pct': 100, 'label': 'done'})}\n\n"
    return Response(stream(), mimetype="text/event-stream")


@app.route("/api/reboot", methods=["POST"])
def reboot():
    # PINCABOS_WIZARD_LOCAL_ONLY_V1
    # Un point d'entree qui redemarre la machine ne peut pas etre plus ouvert
    # que celui qui l'installe.
    a = request.get_json(force=True, silent=True) or {}
    if a.get("confirm", "").strip().upper() != "INSTALL PINCABOS":
        return jsonify({"error": "bad-confirm"}), 400
    if not DEMO:
        subprocess.Popen(["systemctl", "reboot"])
    return jsonify({"ok": True})


if __name__ == "__main__":
    # PINCABOS_WIZARD_LOCAL_ONLY_V1
    # Le kiosk qui affiche l'assistant tourne sur cette machine et interroge
    # 127.0.0.1. Ecouter partout exposait l'installation au reseau entier.
    # Une installation pilotee a distance reste possible, mais elle se demande.
    app.run(host=os.environ.get("PCO_WIZARD_BIND", "127.0.0.1"),
            port=8046, threaded=True)
