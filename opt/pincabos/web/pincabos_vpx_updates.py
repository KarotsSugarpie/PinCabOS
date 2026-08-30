"""Interface canonique de mise à jour VPX-BGFX.

PINCABOS_VPX_UPDATE_UI_V2

Cette page réutilise directement le corps de la page PinCabOS Updates afin que
PinCabOS, VPinFE et VPX aient la même interface. Le moteur reste
/opt/pincabos/tools/pincabos-vpx-update : il audite les GitHub Releases
officielles vpinball/vpinball, ignore les releases « DO NOT USE », choisit
l'asset BGFX Linux x64, conserve la version précédente et sait faire un
rollback.

La WebApp tourne déjà avec l'utilisateur pinball. Les opérations VPX restent
donc dans /home/pinball et ne demandent pas de privilèges root. Le statut
GitHub est mis en cache pour éviter qu'un polling UI toutes les deux secondes
ne frappe l'API GitHub à chaque requête.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from flask import jsonify, request

from pincabos_updates import _updates_body_html


UPDATER = "/opt/pincabos/tools/pincabos-vpx-update"
AGGREGATOR = "/opt/pincabos/tools/pincabos-updates-check"
HOME = Path("/home/pinball")
VPX_LINK = HOME / "vpx"

RUNTIME = HOME / ".cache" / "pincabos" / "vpx-updates"
WEBSTATE = RUNTIME / "update-web-state.json"
LOGFILE = RUNTIME / "update-web.log"

REPOSITORY = "vpinball/vpinball"
CHANNEL = "BGFX · Linux x64"
STATUS_TTL = 60.0

_STATUS_LOCK = threading.Lock()
_STATUS_CACHE: dict = {}
_STATUS_CACHE_AT = 0.0

_ACTION_FLAGS = {
    "check": "--status",
    "update": "--install",
    "rollback": "--rollback",
}


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_json(path: Path, default=None):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else (default or {})
    except Exception:
        return {} if default is None else default


def _save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp." + str(os.getpid()))
    tmp.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
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
    except (ProcessLookupError, ValueError, TypeError):
        return False
    except Exception:
        return False


def _read_log():
    try:
        return LOGFILE.read_text(
            encoding="utf-8",
            errors="replace",
        )[-200000:]
    except Exception:
        return ""


def _engine_status(force=False):
    global _STATUS_CACHE, _STATUS_CACHE_AT

    now = time.monotonic()
    with _STATUS_LOCK:
        if (
            not force
            and _STATUS_CACHE
            and now - _STATUS_CACHE_AT < STATUS_TTL
        ):
            return dict(_STATUS_CACHE)

        try:
            result = subprocess.run(
                [UPDATER, "--status"],
                text=True,
                capture_output=True,
                timeout=40,
            )
            payload = json.loads((result.stdout or "").strip() or "{}")
            if not isinstance(payload, dict):
                payload = {}
        except Exception as exc:
            payload = {
                "installed": _installed_from_link(),
                "available": None,
                "up_to_date": None,
                "release_url": "",
                "ok": False,
                "error": str(exc),
            }

        _STATUS_CACHE = dict(payload)
        _STATUS_CACHE_AT = time.monotonic()
        return dict(payload)


def _invalidate_engine_cache():
    global _STATUS_CACHE_AT
    with _STATUS_LOCK:
        _STATUS_CACHE_AT = 0.0


def _version_from_name(name):
    prefix = "VPinballX_BGFX-"
    suffix = "-linux-x64"
    text = str(name or "")
    if text.startswith(prefix) and text.endswith(suffix):
        return text[len(prefix):-len(suffix)]
    return text


def _installed_from_link():
    try:
        if not (VPX_LINK.is_symlink() or VPX_LINK.exists()):
            return None
        return _version_from_name(Path(os.path.realpath(str(VPX_LINK))).name)
    except Exception:
        return None


def _previous_version():
    try:
        current = Path(os.path.realpath(str(VPX_LINK))) if VPX_LINK.exists() or VPX_LINK.is_symlink() else None
        candidates = []
        for item in HOME.glob("VPinballX_BGFX-*-linux-x64"):
            if not item.is_dir() or item.is_symlink():
                continue
            if not (item / "VPinballX_BGFX").is_file():
                continue
            if current is not None and item.resolve() == current.resolve():
                continue
            candidates.append(item)

        if not candidates:
            return ""

        candidates.sort(key=lambda p: p.stat().st_mtime)
        return _version_from_name(candidates[-1].name)
    except Exception:
        return ""


def _web_state():
    data = _load_json(WEBSTATE, {})

    if data.get("running"):
        pid = data.get("pid", 0)
        # pid=0 est l'état très bref entre le clic et le démarrage du child.
        if pid and not _pid_alive(pid):
            data["running"] = False
            if data.get("last_exit_code") is None:
                data["status"] = "error"
                data["message"] = "Le processus Update VPX s'est interrompu."
                data["finished_at"] = _now()
            _save_json(WEBSTATE, data)

    return data


def _idle_state(engine):
    ok = bool(engine.get("ok"))
    installed = engine.get("installed")
    available = engine.get("available")
    current = engine.get("up_to_date")

    if not ok:
        message = "Impossible d'auditer les releases GitHub VPX pour le moment."
    elif current is True:
        message = f"VPX-BGFX {installed or '—'} est à jour."
    elif installed and available:
        message = f"Mise à jour VPX disponible : {available}."
    elif available:
        message = f"Release VPX disponible : {available}."
    else:
        message = "État VPX prêt."

    return {
        "running": False,
        "status": "idle",
        "action": "",
        "started_at": "",
        "finished_at": "",
        "last_exit_code": None,
        "message": message,
    }


def _status_payload():
    engine = _engine_status()
    ws = _web_state() or _idle_state(engine)

    available = engine.get("available") or "non vérifiée"
    channel = f"{CHANNEL} · latest {available}"

    return {
        "repository": REPOSITORY,
        "channel": channel,
        "installed_version": engine.get("installed") or "non détectée",
        "available_version": engine.get("available") or "non vérifiée",
        "release_url": engine.get("release_url") or "",
        "last_backup": _previous_version(),
        "up_to_date": engine.get("up_to_date"),
        "running": bool(ws.get("running")),
        "status": ws.get("status", "idle"),
        "action": ws.get("action", ""),
        "started_at": ws.get("started_at", ""),
        "finished_at": ws.get("finished_at", ""),
        "last_exit_code": ws.get("last_exit_code"),
        "message": ws.get("message", ""),
        "reboot_after": False,
        "reboot_recommended": False,
        "reboot_scheduled": False,
        "log": _read_log(),
        "log_path": str(LOGFILE),
    }


def _refresh_updates_aggregate():
    """Synchronise immédiatement le Dashboard après une opération VPX."""
    try:
        result = subprocess.run(
            [AGGREGATOR],
            text=True,
            capture_output=True,
            timeout=180,
            check=False,
        )

        with LOGFILE.open("a", encoding="utf-8") as output:
            output.write(
                "\n==================================================\n"
                " Refresh Dashboard Updates state\n"
                "==================================================\n"
            )

            if result.stdout:
                output.write(result.stdout)

            if result.stderr:
                output.write(result.stderr)

            output.write(
                f"Aggregate exit code: {result.returncode}\n"
            )

        return result.returncode == 0

    except Exception as exc:
        try:
            with LOGFILE.open("a", encoding="utf-8") as output:
                output.write(
                    "\nWARN Dashboard aggregate refresh: "
                    + str(exc)
                    + "\n"
                )
        except Exception:
            pass

        return False


def _operation_message(action, rc, engine):
    if rc != 0:
        if action == "rollback":
            return "Le rollback VPX a échoué. Consultez la console."
        if action == "update":
            return "La mise à jour VPX a échoué. Consultez la console."
        return "La vérification VPX a échoué. Consultez la console."

    installed = engine.get("installed") or "—"
    available = engine.get("available") or "—"

    if action == "check":
        if engine.get("up_to_date") is True:
            return f"Vérification terminée : VPX-BGFX {installed} est à jour."
        if available != "—":
            return f"Vérification terminée : mise à jour {available} disponible."
        return "Vérification VPX terminée."

    if action == "update":
        return f"Mise à jour VPX terminée : version active {installed}."

    return f"Rollback VPX terminé : version active {installed}."


def _worker(action):
    flag = _ACTION_FLAGS[action]
    RUNTIME.mkdir(parents=True, exist_ok=True)
    LOGFILE.write_text("", encoding="utf-8")

    state = _load_json(WEBSTATE, {})
    rc = 1

    try:
        with LOGFILE.open("a", encoding="utf-8") as output:
            output.write("==================================================\n")
            output.write(" PinCabOS VPX Updates\n")
            output.write("==================================================\n")
            output.write(f"Repository : {REPOSITORY}\n")
            output.write(f"Action     : {action}\n")
            output.write(f"Commande   : {UPDATER} {flag}\n\n")
            output.flush()

            process = subprocess.Popen(
                [UPDATER, flag],
                stdout=output,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True,
            )

            state["pid"] = process.pid
            _save_json(WEBSTATE, state)
            rc = process.wait()

        _invalidate_engine_cache()
        engine = _engine_status(force=True)

        # --status retourne 0 même lorsque l'audit GitHub est impossible.
        # Pour le bouton "Vérifier", un audit non fiable doit donc être une
        # erreur visible et non un faux succès.
        if action == "check" and not engine.get("ok"):
            rc = 1

        # Une opération réussie doit synchroniser immédiatement
        # /opt/pincabos/state/updates-available.json afin que la tuile
        # Dashboard et le hub Updates affichent le même état que cette page.
        if rc == 0:
            _refresh_updates_aggregate()

        state.update({
            "running": False,
            "pid": 0,
            "finished_at": _now(),
            "last_exit_code": rc,
            "status": "success" if rc == 0 else "error",
            "message": _operation_message(action, rc, engine),
        })
        _save_json(WEBSTATE, state)

    except Exception as exc:
        try:
            with LOGFILE.open("a", encoding="utf-8") as output:
                output.write("\nERREUR : " + str(exc) + "\n")
        except Exception:
            pass

        state.update({
            "running": False,
            "pid": 0,
            "finished_at": _now(),
            "last_exit_code": rc,
            "status": "error",
            "message": "Erreur Update VPX : " + str(exc),
        })
        _save_json(WEBSTATE, state)
        _invalidate_engine_cache()


def _start_action(action):
    ws = _web_state()
    if ws.get("running"):
        return False, "Une opération VPX est déjà en cours."

    if action not in _ACTION_FLAGS:
        return False, "Action VPX invalide."

    state = {
        "running": True,
        "pid": 0,
        "action": action,
        "status": "running",
        "message": "Opération VPX démarrée.",
        "started_at": _now(),
        "finished_at": "",
        "last_exit_code": None,
    }
    _save_json(WEBSTATE, state)

    thread = threading.Thread(
        target=_worker,
        args=(action,),
        daemon=True,
    )
    thread.start()
    return True, "Opération VPX démarrée."


def _body():
    # Même source HTML/CSS/JS que PinCabOS Updates et VPinFE Updates.
    body = _updates_body_html()

    replacements = [
        (
            "PinCabOS Updates",
            "VPX Updates",
        ),
        (
            "Nouveau moteur propre basé sur les "
            "<strong>GitHub Releases officielles</strong>.",
            "Mises à jour de Visual Pinball X BGFX depuis les "
            "<strong>GitHub Releases officielles</strong>.",
        ),
        (
            "/api/updates/",
            "/api/vpx-updates/",
        ),
        (
            "Impossible de lire l’état du module Updates.",
            "Impossible de lire l’état du module VPX Updates.",
        ),
        (
            '<div class="pco-card-label">Channel</div>',
            '<div class="pco-card-label">Channel / Latest</div>',
        ),
        (
            '<div class="pco-card-label">Last backup</div>',
            '<div class="pco-card-label">Previous version</div>',
        ),
        (
            "Redémarrer automatiquement le cab après une "
            "<strong>mise à jour réussie</strong> si nécessaire.",
            "Aucun redémarrage du cab n'est requis après une "
            "<strong>mise à jour VPX</strong>.",
        ),
        (
            '<input type="checkbox" id="rebootAfter">',
            '<input type="checkbox" id="rebootAfter" disabled>',
        ),
        (
            "Après une mise à jour ou un rollback, "
            "un redémarrage peut être recommandé pour "
            "repartir sur une base propre.",
            "La version VPX précédente est conservée pour le rollback. "
            "Les releases « DO NOT USE » sont ignorées.",
        ),
        (
            "Console des mises à jour",
            "Console VPX",
        ),
        (
            "L’opération a démarré. Le WebApp peut être indisponible quelques secondes.",
            "L’opération VPX a démarré en arrière-plan. La WebApp reste disponible.",
        ),
    ]

    for old, new in replacements:
        body = body.replace(old, new)

    return body


def _page_response(page, title, body):
    try:
        return page(title, body)
    except TypeError:
        try:
            return page(title=title, body=body)
        except TypeError:
            return body


def register(app, page):
    @app.get("/tools/vpx/update")
    def pincabos_vpx_updates_page():
        return _page_response(page, "VPX Updates", _body())

    @app.get("/api/vpx-updates/state")
    def pincabos_vpx_updates_state():
        return jsonify(_status_payload())

    @app.post("/api/vpx-updates/run")
    def pincabos_vpx_updates_run():
        data = request.get_json(silent=True) or {}
        action = str(data.get("action", "")).strip().lower()

        if action not in {"check", "update", "rollback"}:
            return jsonify({"ok": False, "error": "Action invalide."}), 400

        ok, msg = _start_action(action)
        if not ok:
            return jsonify({"ok": False, "error": msg}), 409

        return jsonify({"ok": True, "message": msg})

    @app.post("/api/vpx-updates/reboot")
    def pincabos_vpx_updates_reboot():
        return jsonify({
            "ok": False,
            "error": "Aucun reboot du cab n'est requis pour une mise à jour VPX.",
        }), 409
