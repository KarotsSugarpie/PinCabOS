#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import subprocess
import threading
from pathlib import Path

from flask import jsonify, request

from pincabos_updates import _updates_body_html


ENGINE = Path("/opt/pincabos/tools/vpinfeupdate.py")
ENGINE_STATE = Path("/opt/pincabos/state/vpinfe-update-state.json")

RUNTIME = Path("/run/pincabos-vpinfe-updates")
WEBSTATE = RUNTIME / "update-web-state.json"
LOGFILE = RUNTIME / "update-web.log"

BACKUPS = Path("/opt/pincabos/backups/vpinfe-update")

RUNNER = "/usr/local/sbin/pincabos-vpinfe-update-web-runner"

REPOSITORY = "superhac/vpinfe"
CHANNEL = "stable"


def _load_json(path: Path, default=None):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else (default or {})
    except Exception:
        return {} if default is None else default


def _save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp = path.with_name(
        path.name + ".tmp." + str(os.getpid())
    )

    tmp.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False
        ) + "\n",
        encoding="utf-8"
    )

    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def _pid_alive(pid):
    try:
        pid = int(pid)

        if pid <= 0:
            return False

        os.kill(pid, 0)
        return True

    except PermissionError:
        return True

    except (
        ProcessLookupError,
        ValueError,
        TypeError,
    ):
        return False

    except Exception:
        return False


def _engine_payload():
    try:
        result = subprocess.run(
            [
                "/usr/bin/python3",
                str(ENGINE),
                "--status",
            ],
            text=True,
            capture_output=True,
            timeout=8,
        )

        payload = json.loads(
            (result.stdout or "").strip() or "{}"
        )

        return payload if isinstance(payload, dict) else {}

    except Exception:
        return {}


def _latest_backup():
    try:
        candidates = []

        for item in BACKUPS.iterdir():
            candidate = item / "vpinfe"

            if (
                item.is_dir()
                and (candidate / "vpinfe").is_file()
                and (candidate / "_internal").is_dir()
            ):
                candidates.append(candidate)

        if not candidates:
            return ""

        candidates.sort(
            key=lambda p: p.parent.name
        )

        return str(candidates[-1])

    except Exception:
        return ""


def _read_log():
    try:
        text = LOGFILE.read_text(
            encoding="utf-8",
            errors="replace"
        )

        return text[-200000:]

    except Exception:
        return ""


def _web_state():
    data = _load_json(WEBSTATE, {})

    if data.get("running"):
        pid = data.get("pid", 0)

        if not _pid_alive(pid):
            data["running"] = False

            if data.get("last_exit_code") is None:
                data["status"] = "error"
                data["message"] = (
                    "Le processus Update VPinFE "
                    "s'est interrompu."
                )

            _save_json(WEBSTATE, data)

    return data


def _fallback_operation(engine):
    operation = (
        engine.get("last_operation", {})
        if isinstance(engine, dict)
        else {}
    )

    if not isinstance(operation, dict):
        operation = {}

    if not operation:
        return {
            "running": False,
            "status": "idle",
            "action": "",
            "started_at": "",
            "finished_at": "",
            "last_exit_code": None,
            "message": "",
        }

    ok = operation.get("ok")

    return {
        "running": False,
        "status": (
            "success"
            if ok is True
            else "error"
            if ok is False
            else "idle"
        ),
        "action": operation.get("stage", ""),
        "started_at": operation.get("at", ""),
        "finished_at": operation.get("at", ""),
        "last_exit_code": (
            0
            if ok is True
            else 1
            if ok is False
            else None
        ),
        "message": operation.get("message", ""),
    }


def _status_payload():
    engine = _engine_payload()

    local = (
        engine.get("local", {})
        if isinstance(engine.get("local"), dict)
        else {}
    )

    remote = (
        engine.get("remote", {})
        if isinstance(engine.get("remote"), dict)
        else {}
    )

    ws = _web_state()

    if not ws:
        ws = _fallback_operation(engine)

    return {
        "repository": REPOSITORY,
        "channel": CHANNEL,

        "installed_version":
            local.get("display")
            or "non détectée",

        "available_version":
            remote.get("tag")
            or "non vérifiée",

        "release_url":
            remote.get("html_url")
            or "",

        "last_backup":
            _latest_backup(),

        "running":
            bool(ws.get("running")),

        "status":
            ws.get("status", "idle"),

        "action":
            ws.get("action", ""),

        "started_at":
            ws.get("started_at", ""),

        "finished_at":
            ws.get("finished_at", ""),

        "last_exit_code":
            ws.get("last_exit_code"),

        "message":
            ws.get("message", ""),

        # VPinFE est déjà relancé automatiquement
        # par le wrapper officiel.
        "reboot_after": True,
        "reboot_recommended": False,
        "reboot_scheduled": False,

        "log":
            _read_log(),

        "log_path":
            str(LOGFILE),
    }


def _run_action(action):
    subprocess.Popen(
        [
            "/usr/bin/sudo",
            "-n",
            RUNNER,
            action,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def _start_action(action):
    ws = _web_state()

    if ws.get("running"):
        return (
            False,
            "Une opération VPinFE est déjà en cours."
        )

    thread = threading.Thread(
        target=_run_action,
        args=(action,),
        daemon=True,
    )

    thread.start()

    return True, "Opération démarrée."


def _body():
    # On réutilise DIRECTEMENT la page PinCabOS Updates
    # actuellement installée. Même CSS, mêmes cartes,
    # mêmes boutons et même console.
    body = _updates_body_html()

    replacements = [
        (
            "PinCabOS Updates",
            "VPinFE Updates",
        ),
        (
            "Nouveau moteur propre basé sur les "
            "<strong>GitHub Releases officielles</strong>.",
            "Mises à jour du frontend VPinFE depuis les "
            "<strong>GitHub Releases officielles</strong>.",
        ),
        (
            "/api/updates/",
            "/api/vpinfe-updates/",
        ),
        (
            "Impossible de lire l’état du module Updates.",
            "Impossible de lire l’état du module VPinFE Updates.",
        ),
        (
            "Redémarrer automatiquement le cab après une "
            "<strong>mise à jour réussie</strong> si nécessaire.",
            "Relancer automatiquement VPinFE après une "
            "<strong>mise à jour réussie</strong>.",
        ),
        (
            "Après une mise à jour ou un rollback, "
            "un redémarrage peut être recommandé pour "
            "repartir sur une base propre.",
            "VPinFE est arrêté puis relancé de façon contrôlée. "
            "La configuration PinCabOS et le fichier vpinfe.ini "
            "restent protégés.",
        ),
        (
            '<input type="checkbox" id="rebootAfter">',
            '<input type="checkbox" id="rebootAfter" checked disabled>',
        ),
    ]

    for old, new in replacements:
        body = body.replace(old, new)

    body = body.replace(
        "<script>",
        "<!-- PINCABOS_VPINFE_UPDATE_ASYNC_UI_V1 -->\n"
        "<!-- PINCABOS_VPINFE_UPDATE_SPINNER_V2 -->\n"
        "<script>",
        1,
    )

    return body


def _page_response(page, title, body):
    try:
        return page(title, body)

    except TypeError:
        try:
            return page(
                title=title,
                body=body
            )

        except TypeError:
            return body


def register(app, page):
    @app.get("/tools/vpinfe/update")
    def pincabos_vpinfe_updates_page():
        return _page_response(
            page,
            "VPinFE Updates",
            _body(),
        )

    @app.get("/api/vpinfe-updates/state")
    def pincabos_vpinfe_updates_state():
        return jsonify(
            _status_payload()
        )

    @app.post("/api/vpinfe-updates/run")
    def pincabos_vpinfe_updates_run():
        data = request.get_json(
            silent=True
        ) or {}

        action = str(
            data.get("action", "")
        ).strip().lower()

        if action not in {
            "check",
            "update",
            "rollback",
        }:
            return jsonify(
                {
                    "ok": False,
                    "error": "Action invalide."
                }
            ), 400

        ok, msg = _start_action(action)

        if not ok:
            return jsonify(
                {
                    "ok": False,
                    "error": msg
                }
            ), 409

        return jsonify(
            {
                "ok": True,
                "message": msg
            }
        )

    @app.post("/api/vpinfe-updates/reboot")
    def pincabos_vpinfe_updates_reboot():
        return jsonify(
            {
                "ok": False,
                "error":
                    "Aucun reboot du cab n'est requis "
                    "pour une mise à jour VPinFE."
            }
        ), 409
