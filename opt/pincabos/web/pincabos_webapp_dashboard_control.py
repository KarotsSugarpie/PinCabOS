# PinCabOS Dashboard Lobby V13 — server routes and privileged actions
from __future__ import annotations

import hmac
import os
import subprocess
from pathlib import Path
from urllib.parse import quote

from flask import abort, jsonify, redirect, request, send_file, session

from pincabos_dashboard_lobby import default_layout, load_layout, registry_for_request, save_layout, status_snapshot, network_traffic_snapshot

HELPER = "/usr/local/sbin/pincabos-dashboard-admin"
LIVE_DIR = Path("/run/pincabos-dashboard-live")
LIVE_LEASE = LIVE_DIR / "lease"
ALLOWED_SERVICES = {
    "vpinfe": {"start", "stop", "restart", "freeze", "thaw"},
    "webapp": {"restart"},
    "chrony": {"start", "restart"},
    "media_recorder": {"start", "stop", "restart"},
    "vpx": {"stop", "restart"},  # PINCABOS_DASHBOARD_VPX_SERVICE_V1
    "screens": {"apply"},
}


def notice(message):
    return redirect("/?dashboard_notice=" + quote(str(message)[:220]), code=303)


def csrf_ok():
    expected = str(session.get("pco_dashboard_lobby_csrf", ""))
    supplied = request.headers.get("X-CSRF-Token", "")
    if request.is_json:
        supplied = (request.get_json(silent=True) or {}).get("csrf", supplied)
    else:
        supplied = request.form.get("csrf", supplied)
    return bool(expected) and hmac.compare_digest(expected, str(supplied))


def helper(*args):
    try:
        result = subprocess.run(["sudo", "-n", HELPER, *args], text=True, capture_output=True, timeout=35)
        return result.returncode == 0, (result.stdout or result.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return False, "Délai dépassé."
    except Exception as error:
        return False, str(error)


def add_route_once(app, rule, endpoint, view, methods):
    # Idempotent by endpoint and URL; this prevents the V8 duplicate-endpoint failure.
    rules = {item.rule for item in app.url_map.iter_rules()}
    if endpoint in app.view_functions or rule in rules:
        return
    app.add_url_rule(rule, endpoint=endpoint, view_func=view, methods=methods)


def register_dashboard_control_routes(app):
    if app.extensions.get("pco_dashboard_lobby_routes"):
        return
    app.extensions["pco_dashboard_lobby_routes"] = True
    install_pco_menu_tools_fulldmd_v13_7(app)
    install_global_menu_cleanup(app)

    def layout_api():
        registry = registry_for_request()
        if request.method == "GET":
            return jsonify({"layout": load_layout(registry), "registry": registry})
        if not csrf_ok():
            return jsonify({"ok": False, "error": "Session Dashboard invalide."}), 403
        payload = request.get_json(silent=True) or {}
        layout = save_layout(payload.get("layout", []), registry)
        return jsonify({"ok": True, "layout": layout})

    def default_api():
        if not csrf_ok():
            return jsonify({"ok": False, "error": "Session Dashboard invalide."}), 403
        registry = registry_for_request()
        layout = save_layout(default_layout(registry), registry)
        return jsonify({"ok": True, "layout": layout})

    def status_api():
        return jsonify(status_snapshot())

    def update_live_lease(raw_slots):
        slots = []
        for value in raw_slots if isinstance(raw_slots, (list, tuple, set)) else []:
            try:
                slot = int(value)
            except (TypeError, ValueError):
                continue
            if slot in {0, 1, 2} and slot not in slots:
                slots.append(slot)
        if not slots:
            return []
        LIVE_DIR.mkdir(parents=True, exist_ok=True)
        temporary = LIVE_DIR / f".lease.{os.getpid()}.tmp"
        temporary.write_text(",".join(str(slot) for slot in sorted(slots)) + "\n", encoding="ascii")
        os.chmod(temporary, 0o644)
        try:
            os.chown(temporary, 1000, 1000)
        except OSError:
            pass
        os.replace(temporary, LIVE_LEASE)
        return slots

    # === PINCABOS_NETWORK_TRUECHART_API_V1 ===
    def network_traffic_api():
        return jsonify(network_traffic_snapshot())

    def live_heartbeat():
        if not csrf_ok():
            return jsonify({"ok": False, "error": "Session Dashboard invalide."}), 403
        payload = request.get_json(silent=True) or {}
        slots = update_live_lease(payload.get("slots", []))
        return jsonify({"ok": True, "slots": slots, "rate": "5 fps"})


    # === PINCABOS DASHBOARD LIVE WEBRTC V14 ===
    def live_webrtc_heartbeat():
        if not csrf_ok():
            return jsonify({"ok": False, "error": "Session Dashboard invalide."}), 403
        payload = request.get_json(silent=True) or {}
        try:
            slot = int(payload.get("slot"))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "Écran GPU invalide."}), 400
        if slot not in {0, 1, 2}:
            return jsonify({"ok": False, "error": "Écran GPU invalide."}), 400
        try:
            result = subprocess.run(
                ["sudo", "-n", "/usr/local/lib/pincabos/pincabos-dashboard-live-webrtc", "heartbeat", str(slot)],
                text=True, capture_output=True, timeout=10,
            )
        except subprocess.TimeoutExpired:
            return jsonify({"ok": False, "error": "Démarrage GPU WebRTC trop long."}), 504
        except Exception as error:
            return jsonify({"ok": False, "error": f"Moteur GPU WebRTC indisponible : {error}"}), 500
        state_lines = (result.stdout or result.stderr or "").strip().splitlines()
        state = state_lines[-1] if state_lines else "starting"
        if result.returncode != 0 or state.startswith("error:"):
            detail = state.split(":", 1)[-1] if ":" in state else state
            return jsonify({"ok": False, "error": f"Moteur GPU WebRTC : {detail}"}), 503
        parts = state.split(":")
        if len(parts) == 4 and parts[0] == "running":
            try:
                running_slot = int(parts[1])
            except ValueError:
                return jsonify({"ok": False, "error": "État GPU WebRTC illisible."}), 503
            return jsonify({"ok": True, "state": "running", "slot": running_slot, "output": parts[2], "path": parts[3]})
        return jsonify({"ok": True, "state": "starting", "slot": slot})

    def live_screen(slot):
        if slot not in {0, 1, 2}:
            abort(404)
        path = LIVE_DIR / f"screen{slot}.jpg"
        if not path.is_file() or path.stat().st_size < 64:
            return ("", 204)
        response = send_file(path, mimetype="image/jpeg", conditional=True, max_age=0)
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["X-PinCabOS-Capture"] = "live-lite"
        return response
    def service_action(service, action):
        if not csrf_ok():
            return notice("Action refusée : session Dashboard invalide.")
        if action not in ALLOWED_SERVICES.get(service, set()):
            return notice("Action de service refusée.")
        ok, output = helper("service", service, action)
        label = {
            "vpinfe": "VPinFE",
            "vpx": "Visual Pinball X",
            "webapp": "WebApp",
            "chrony": "Chrony",
            "media_recorder": "PinCab Recorder Worker",
        }.get(service, service)
        return notice(f"{label} : {action} demandé." if ok else f"Échec {label}/{action} : {output[-140:]}")

    def time_action(action):
        if not csrf_ok():
            return notice("Action heure refusée : session Dashboard invalide.")
        if action == "sync-google":
            ok, output = helper("time", "sync-google")
            return notice("Google NTP configuré et synchronisation demandée." if ok else f"Échec Google NTP : {output[-140:]}")
        if action == "timezone":
            zone = request.form.get("timezone", "").strip()
            ok, output = helper("time", "timezone", zone)
            return notice(f"Fuseau appliqué : {zone}" if ok else f"Échec fuseau : {output[-140:]}")
        if action == "set":
            value = request.form.get("value", "").strip()
            ok, output = helper("time", "set", value)
            return notice(f"Heure ajustée : {value}" if ok else f"Échec ajustement : {output[-140:]}")
        return notice("Action heure refusée.")

    for rule, endpoint, view, methods in (
        ("/dashboard/lobby/layout", "pco_lobby_layout", layout_api, ["GET", "POST"]),
        ("/dashboard/lobby/default", "pco_lobby_default", default_api, ["POST"]),
        ("/dashboard/lobby/status", "pco_lobby_status", status_api, ["GET"]),
        ("/dashboard/lobby/network/traffic", "pco_lobby_network_traffic", network_traffic_api, ["GET"]),
        ("/dashboard/lobby/live/heartbeat", "pco_lobby_live_heartbeat", live_heartbeat, ["POST"]),
        ("/dashboard/lobby/live/webrtc/heartbeat", "pco_lobby_live_webrtc_heartbeat", live_webrtc_heartbeat, ["POST"]),
        ("/dashboard/lobby/live/<int:slot>", "pco_lobby_live", live_screen, ["GET"]),
        ("/dashboard/control/service/<service>/<action>", "pco_lobby_service", service_action, ["POST"]),
        ("/dashboard/control/time/<action>", "pco_lobby_time", time_action, ["POST"]),
    ):
        add_route_once(app, rule, endpoint, view, methods)


# === PINCABOS GLOBAL MENU CLEANUP V13.6 ===
def install_global_menu_cleanup(app):
    if app.extensions.get("pco_global_menu_cleanup_v13_6"):
        return
    app.extensions["pco_global_menu_cleanup_v13_6"] = True

    @app.after_request
    def pco_global_menu_cleanup(response):
        if response.direct_passthrough or response.mimetype != "text/html":
            return response
        try:
            body = response.get_data(as_text=True)
            tag = '<script src="/static/pincabos-nav-cleanup-v13.6.js?v=menu-fulldmd-v13.6" defer></script>'
            if 'pincabos-nav-cleanup-v13.6.js' not in body:
                closing = body.lower().rfind("</body>")
                body = body[:closing] + tag + body[closing:] if closing >= 0 else body + tag
                response.set_data(body)
                response.headers.pop("Content-Length", None)
        except Exception:
            pass
        return response


# === PINCABOS MENU + TOOLS FULLDMD V13.7 ===
def install_pco_menu_tools_fulldmd_v13_7(app):
    if app.extensions.get("pco_menu_tools_fulldmd_v13_7"):
        return
    app.extensions["pco_menu_tools_fulldmd_v13_7"] = True

    @app.after_request
    def pco_menu_tools_fulldmd_v13_7(response):
        if response.direct_passthrough or response.mimetype != "text/html":
            return response
        try:
            body = response.get_data(as_text=True)
            tag = '<script src="/static/pincabos-nav-tools-fulldmd-v13.7.js?v=output-tools-fulldmd-v13.7" defer></script>'
            if 'pincabos-nav-tools-fulldmd-v13.7.js' not in body:
                index = body.lower().rfind("</body>")
                body = body[:index] + tag + body[index:] if index >= 0 else body + tag
                response.set_data(body)
                response.headers.pop("Content-Length", None)
        except Exception:
            pass
        return response
