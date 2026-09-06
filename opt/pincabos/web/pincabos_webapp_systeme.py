"""Système de la WebApp PinCabOS : contrôle des services (/service-control), du processus VPX (/process-control/vpx).

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


# === PINCABOS VPINFE VERSION HELPERS END ===


def register(app, page_fn):
    """Enregistre le contrôle des services et du processus VPX sur l'application."""
    global page
    page = page_fn
    app.register_blueprint(systeme_bp)
