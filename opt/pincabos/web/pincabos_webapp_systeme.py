"""Système de la WebApp PinCabOS : contrôle des services (/service-control), du processus VPX (/process-control/vpx) et versions locales / disponibles (VPinFE, VPX, GPU, Ubuntu).

Code déplacé tel quel depuis app.py (PINCABOS_WEBAPP_MODULES_V1) ; les routes gardent
leurs chemins et leurs noms de fonction. `page()` (gabarit commun) est fourni par app.py
à l'enregistrement : `register(app, page)`.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from flask import Blueprint, redirect, request

from pincabos_webapp_core import esc, pco_vpx_kill_pattern

systeme_bp = Blueprint("systeme", __name__)

page = None  # gabarit HTML commun, posé par register()


@systeme_bp.route("/service-control", methods=["POST"])
def service_control():
    """
    Contrôle sécurisé des services PinCabOS depuis le dashboard.
    Accepte: service + action.
    Actions supportées: start, stop, restart, reload, kill.
    """
    service = request.form.get("service", "").strip()
    action = request.form.get("action", "").strip().lower()

    allowed_services = {
        "pincabos-vpinfe.service",
        "pincabos-webapp.service",
        "pincabos-console.service",
    }

    action_map = {
        "start": "start",
        "stop": "stop",
        "restart": "restart",
        "reload": "restart",
        "kill": "kill",
    }

    if service not in allowed_services:
        return f"Service non autorisé: {esc(service)}", 400

    if action not in action_map:
        return f"Action non autorisée: {esc(action)}", 400

    cmd_action = action_map[action]

    try:
        if cmd_action == "kill":
            subprocess.Popen(
                ["/usr/bin/sudo", "/bin/systemctl", "kill", service],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                ["/usr/bin/sudo", "/bin/systemctl", cmd_action, service],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except Exception as e:
        return f"Erreur contrôle service: {esc(str(e))}", 500

    return redirect(request.referrer or "/")


@systeme_bp.route("/service-control/<service_key>/<action>", methods=["GET", "POST"])
def service_control_path(service_key, action):
    """
    Route générique pour les boutons Services du dashboard PinCabOS.
    Supporte les URLs du genre:
      /service-control/web/start
      /service-control/web/restart
      /service-control/frontend/stop
      /service-control/frontend/reload
    """
    service_map = {
        # VPinFE / frontend
        "frontend": "pincabos-vpinfe.service",
        "vpinfe": "pincabos-vpinfe.service",
        "front": "pincabos-vpinfe.service",

        # Web manager
        "web": "pincabos-webapp.service",
        "web-manager": "pincabos-webapp.service",
        "manager": "pincabos-webapp.service",

        # Console Commander
        "console": "pincabos-console.service",
        "webconsole": "pincabos-console.service",
        "web-console": "pincabos-console.service",

        # Console web

        # Auto timezone
    }

    action_map = {
        "start": "start",
        "play": "start",
        "stop": "stop",
        "restart": "restart",
        "reload": "restart",
        "refresh": "restart",
        "kill": "kill",
    }

    service_key = str(service_key or "").strip().lower()
    action = str(action or "").strip().lower()

    if service_key not in service_map:
        return f"Service non autorisé: {esc(service_key)}", 400

    if action not in action_map:
        return f"Action non autorisée: {esc(action)}", 400

    service = service_map[service_key]
    systemctl_action = action_map[action]

    try:
        subprocess.Popen(
            ["/usr/bin/sudo", "/bin/systemctl", systemctl_action, service],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        return f"Erreur contrôle service: {esc(str(e))}", 500

    return redirect(request.referrer or "/")


# === PINCABOS DASHBOARD VPX PROCESS CONTROL START ===
@systeme_bp.route("/process-control/vpx/<action>", methods=["POST"])
def process_control_vpx(action):
    """
    Contrôle prudent du processus VPX lancé par VPinFE.
    VPX n'est pas un service systemd direct, donc:
      - stop / kill : termine VPinballX seulement
      - restart     : termine VPinballX puis redémarre VPinFE
      - start       : redémarre VPinFE, car VPX part normalement via VPinFE/table
    """
    action = str(action or "").strip().lower()

    allowed = {"start", "stop", "restart", "kill", "play"}
    if action not in allowed:
        return f"Action VPX non autorisée: {esc(action)}", 400

    try:
        if action in {"stop", "kill"}:
            subprocess.Popen(
                ["/usr/bin/pkill", "-TERM", "-f", pco_vpx_kill_pattern()],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif action in {"restart", "start", "play"}:
            subprocess.Popen(
                ["/usr/bin/pkill", "-TERM", "-f", pco_vpx_kill_pattern()],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.Popen(
                ["/usr/bin/sudo", "/bin/systemctl", "restart", "pincabos-vpinfe.service"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except Exception as e:
        return f"Erreur contrôle VPX: {esc(str(e))}", 500

    return redirect(request.referrer or "/")
# === PINCABOS DASHBOARD VPX PROCESS CONTROL END ===


# === PINCABOS VPINFE VERSION HELPERS START ===
def _pincabos_vpinfe_status_payload(remote=False):
    script = Path("/opt/pincabos/tools/vpinfeupdate.py")
    command = ["/usr/bin/python3", str(script), "--status"]
    if remote:
        command.append("--remote")
    try:
        result = subprocess.run(command, text=True, capture_output=True, timeout=35)
        payload = json.loads((result.stdout or "").strip() or "{}")
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def pincabos_vpinfe_local_version():
    payload = _pincabos_vpinfe_status_payload(remote=False)
    local = payload.get("local", {}) if isinstance(payload.get("local"), dict) else {}
    return local.get("display") or "non détectée"


def pincabos_vpinfe_available_version():
    payload = _pincabos_vpinfe_status_payload(remote=True)
    remote = payload.get("remote", {}) if isinstance(payload.get("remote"), dict) else {}
    return remote.get("tag") or "non détectée"
# === PINCABOS VPINFE VERSION HELPERS END ===


def pincabos_vpinball_local_version():
    """
    Détection locale VPX/VPinball.
    On évite les faux positifs comme 0.115 provenant de libs/aide.
    Chemins officiels PinCabOS:
      /opt/pincabos/bin/vpx-vpinfe-default.sh
      /opt/pincabos/bin/vpx-vpinfe-default.sh
    """
    import re
    import subprocess
    from pathlib import Path

    candidates = [
        Path("/opt/pincabos/bin/vpx-vpinfe-default.sh"),
        Path("/home/pinball/vpx/VPinballX_BGFX"),
        Path("/opt/pincabos/bin/vpx-vpinfe-default.sh"),
    ]

    ignored_versions = {"0.115", "0.14", "0.14.0", "0.1.0", "0.4.1", "0.8.0", "0.9.0"}

    for exe in candidates:
        if exe.exists() and exe.is_file() and exe.stat().st_mode & 0o111:
            for arg in ("-version", "--version"):
                try:
                    r = subprocess.run(
                        [str(exe), arg],
                        text=True,
                        capture_output=True,
                        timeout=8,
                        cwd=str(exe.parent),
                        env={
                            "HOME": "/home/pinball",
                            "XDG_CONFIG_HOME": "/home/pinball/.config",
                            "XDG_DATA_HOME": "/home/pinball/.local/share",
                        },
                    )
                    out = ((r.stdout or "") + "\n" + (r.stderr or "")).strip()

                    # On accepte surtout les versions VPX connues 10.x.
                    m = re.search(r"\bv?10\.\d+(?:\.\d+){0,2}\b", out)
                    if m:
                        return m.group(0)

                    # Fallback général, mais ignore les versions de libs.
                    for m in re.finditer(r"\bv?\d+(?:\.\d+){1,3}\b", out):
                        val = m.group(0)
                        if val not in ignored_versions and not val.startswith("0."):
                            return val
                except Exception:
                    pass

            # Binaire présent, mais version exacte non fiable.
            if "BGFX" in exe.name.upper():
                return "VPX BGFX installé"
            return "VPX installé"

    if Path('/home/pinball/vpx').is_dir():
        return "VPX installé"

    return "non détectée"


def pincabos_vpinball_available_version():
    """
    Version disponible VPX/VPinball.
    Pour l'instant on tente GitHub officiel, sinon fallback local.
    """
    import json as _json
    import urllib.request
    import re
    import subprocess

    urls = [
        "https://api.github.com/repos/vpinball/vpinball/releases/latest",
        "https://api.github.com/repos/vpinball/vpinball/actions/artifacts",
    ]

    for url in urls:
        try:
            with urllib.request.urlopen(url, timeout=6) as r:
                data = _json.loads(r.read().decode("utf-8", errors="replace"))

            tag = (data.get("tag_name") or data.get("name") or "").strip()
            m = re.search(r"\bv?\d+(?:\.\d+){1,3}\b", tag)
            if m:
                return m.group(0)

            artifacts = data.get("artifacts") or []
            for a in artifacts:
                name = str(a.get("name") or "")
                if "linux" in name.lower() or "bgfx" in name.lower() or "vpinball" in name.lower():
                    m = re.search(r"\bv?\d+(?:\.\d+){1,3}\b", name)
                    if m:
                        return m.group(0)
        except Exception:
            pass

    # Fallback: ne pas afficher non détectée si VPX local est présent.
    local = pincabos_vpinball_local_version()
    if local != "non détectée":
        return local

    return "non détectée"


def pincabos_gpu_local_version():
    """
    État GPU/pilote local.
    Ne lance aucune installation.
    """
    import subprocess
    import re

    try:
        r = subprocess.run(
            ["/usr/bin/nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
            text=True,
            capture_output=True,
            timeout=4,
        )
        out = (r.stdout or "").strip().splitlines()
        if out and out[0].strip():
            return "NVIDIA " + out[0].strip()
    except Exception:
        pass

    try:
        r = subprocess.run(
            ["/sbin/modinfo", "nvidia"],
            text=True,
            capture_output=True,
            timeout=4,
        )
        out = (r.stdout or "") + "\\n" + (r.stderr or "")
        m = re.search(r"^version:\\s*(.+)$", out, re.M)
        if m:
            return "NVIDIA " + m.group(1).strip()
    except Exception:
        pass

    try:
        r = subprocess.run(
            ["/usr/bin/lspci"],
            text=True,
            capture_output=True,
            timeout=4,
        )
        out = r.stdout or ""
        lines = [
            x for x in out.splitlines()
            if "VGA" in x or "3D controller" in x or "Display controller" in x
        ]
        if lines:
            line = lines[0]
            up = line.upper()
            if "NVIDIA" in up:
                return "NVIDIA détectée"
            if "AMD" in up or "ATI" in up:
                return "AMD/Mesa détecté"
            if "INTEL" in up:
                return "Intel/Mesa détecté"
            if "RED HAT" in up or "VIRTIO" in up:
                return "Virtio/QEMU détecté"
            return "GPU détecté"
    except Exception:
        pass

    return "non détecté"


def pincabos_gpu_available_version():
    """
    Pilote GPU recommandé disponible.
    Ne lance aucune installation.
    """
    import subprocess
    import re

    try:
        r = subprocess.run(
            ["/usr/bin/ubuntu-drivers", "devices"],
            text=True,
            capture_output=True,
            timeout=8,
        )
        out = (r.stdout or "") + "\\n" + (r.stderr or "")
        m = re.search(r"(nvidia-driver-\\d+[^ \\n]*)\\s+.*recommended", out, re.I)
        if m:
            return m.group(1).strip()
        m = re.search(r"(nvidia-driver-\\d+[^ \\n]*)", out, re.I)
        if m:
            return m.group(1).strip()
    except Exception:
        pass

    local = pincabos_gpu_local_version()
    if local != "non détecté":
        return "à jour / auto"

    return "non détecté"


def pincabos_ubuntu_local_version():
    """
    Version Ubuntu locale.
    """
    from pathlib import Path

    osr = Path("/etc/os-release")
    if osr.is_file():
        data = {}
        for line in osr.read_text(errors="replace").splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                data[k] = v.strip().strip('"')
        return data.get("PRETTY_NAME") or data.get("VERSION") or data.get("VERSION_ID") or "Ubuntu détecté"

    return "non détectée"


def pincabos_ubuntu_available_version():
    """
    Résumé des paquets Ubuntu disponibles.
    Ne fait pas apt update; lit seulement l'état apt actuel.
    """
    import subprocess

    try:
        r = subprocess.run(
            ["/usr/bin/apt", "list", "--upgradable"],
            text=True,
            capture_output=True,
            timeout=8,
        )
        lines = []
        for line in (r.stdout or "").splitlines():
            line = line.strip()
            if not line or line.startswith("Listing"):
                continue
            if "/" in line and "[" in line:
                lines.append(line)

        if len(lines) == 0:
            return "à jour"
        if len(lines) == 1:
            return "1 paquet"
        return str(len(lines)) + " paquets"
    except Exception:
        pass

    return "vérifier"


def register(app, page_fn):
    """Enregistre le contrôle des services et du processus VPX sur l'application."""
    global page
    page = page_fn
    app.register_blueprint(systeme_bp)
