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


@app.route("/api/disks")
def disks():
    if DEMO:
        return jsonify([
            {"dev": "/dev/nvme0n1", "size": "931,5G", "model": "Samsung 980 PRO 1TB"},
            {"dev": "/dev/sda", "size": "223,6G", "model": "Crucial BX500 240GB"},
        ])
    out = subprocess.run(
        ["lsblk", "-J", "-d", "-o", "NAME,SIZE,TYPE,MODEL"],
        capture_output=True, text=True, timeout=10).stdout
    found = []
    for d in json.loads(out).get("blockdevices", []):
        if d.get("type") == "disk" and not d["name"].startswith(("loop", "sr", "zram")):
            found.append({"dev": "/dev/" + d["name"], "size": d.get("size", "?"),
                          "model": (d.get("model") or "").strip() or "Disque"})
    return jsonify(found)


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
    "xkb": re.compile(r"^[a-z]{2,3}$"),
    "xkb_variant": re.compile(r"^[a-z0-9_-]{0,31}$"),
    "tz": re.compile(r"^[A-Za-z][A-Za-z0-9_+-]{0,31}(/[A-Za-z0-9_+-]{1,31}){0,2}$"),
    "orient": re.compile(r"^[1-4]$"),
    "mode": re.compile(r"^[1-3]$"),
    "disk": re.compile(r"^/dev/[a-z0-9]+$"),
}


ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]|\x1b[c()][0-9A-B]?")


@app.route("/api/install", methods=["POST"])
def install():
    a = request.get_json(force=True)
    if a.get("confirm", "").strip().upper() != "INSTALL PINCABOS":
        return jsonify({"error": "bad-confirm"}), 400
    if not re.fullmatch(r"/dev/[a-z0-9]+", a.get("disk", "")) and not DEMO:
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
        while pct < 100:
            if INSTALL_LOG.exists():
                text = INSTALL_LOG.read_text(errors="replace")
                new, pos = text[pos:], len(text)
                for line in new.splitlines():
                    for marker, p in PHASES:
                        if marker.lower() in line.lower():
                            pct = max(pct, p)
                    # log lisible : sans ANSI, sans lignes decoratives ni art figlet
                    clean = ANSI_RE.sub("", line).strip()
                    if not clean:
                        continue
                    readable = sum(c.isalnum() or c in " ,.:;()/'\"-_" for c in clean)
                    if readable / len(clean) < 0.6:
                        continue
                    yield f"data: {json.dumps({'pct': pct, 'log': clean})}\n\n"
            time.sleep(1)
        yield f"data: {json.dumps({'pct': 100, 'label': 'done'})}\n\n"
    return Response(stream(), mimetype="text/event-stream")


@app.route("/api/reboot", methods=["POST"])
def reboot():
    if not DEMO:
        subprocess.Popen(["systemctl", "reboot"])
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8046, threaded=True)
