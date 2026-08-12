# PINCABOS_LIVE_TABLE_STATUS_CARD_V2
from __future__ import annotations

import hmac
import os
import pwd
import secrets
import signal
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

from flask import jsonify, request

_TOKEN_TTL_SECONDS = 30
_token_lock = threading.RLock()
_stop_tokens: dict[int, tuple[str, float]] = {}


def _read_cmdline(pid: int) -> list[str]:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        return []
    return [part.decode("utf-8", "replace") for part in raw.split(b"\0") if part]


def _read_comm(pid: int) -> str:
    try:
        return Path(f"/proc/{pid}/comm").read_text(encoding="utf-8", errors="replace").strip()
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        return ""


def _iter_pinball_processes():
    try:
        pinball_uid = pwd.getpwnam("pinball").pw_uid
    except KeyError:
        return

    for proc_dir in Path("/proc").glob("[0-9]*"):
        try:
            if proc_dir.stat().st_uid != pinball_uid:
                continue
            pid = int(proc_dir.name)
        except (FileNotFoundError, PermissionError, ValueError):
            continue

        argv = _read_cmdline(pid)
        comm = _read_comm(pid)
        if not argv and not comm:
            continue

        yield {
            "pid": pid,
            "argv": argv,
            "comm": comm,
            "joined": "\0".join(argv).lower(),
        }


def _extract_table_path(argv: list[str]) -> str | None:
    for arg in reversed(argv):
        candidate = arg.strip().strip('"').strip("'")
        lower = candidate.lower()
        if lower.endswith(".vpx"):
            return candidate
        if lower.startswith("--table=") and lower[8:].lower().endswith(".vpx"):
            return candidate[8:]
    return None


def _find_running_table() -> dict | None:
    processes = list(_iter_pinball_processes() or [])
    if not processes:
        return None

    vpx_processes = []
    table_candidates = []

    for proc in processes:
        comm_l = (proc["comm"] or "").lower()
        joined = proc["joined"]

        if "vpinballx" in joined or comm_l.startswith("vpinballx"):
            vpx_processes.append(proc)

        table_path = _extract_table_path(proc["argv"])
        if table_path:
            table_candidates.append((proc["pid"], table_path))

    if not vpx_processes:
        return None

    vpx = max(vpx_processes, key=lambda p: p["pid"])

    table_name = "Table en cours"
    table_path = _extract_table_path(vpx["argv"])

    if not table_path and table_candidates:
        table_path = max(table_candidates, key=lambda item: item[0])[1]

    if table_path:
        table_name = Path(table_path).stem

    return {
        "pid": vpx["pid"],
        "table_name": table_name,
    }


def _issue_token(pid: int) -> str:
    now = time.monotonic()
    with _token_lock:
        current = _stop_tokens.get(pid)
        if current and current[1] > now:
            return current[0]

        token = secrets.token_urlsafe(32)
        _stop_tokens.clear()
        _stop_tokens[pid] = (token, now + _TOKEN_TTL_SECONDS)
        return token


def _consume_valid_token(pid: int, supplied: str) -> bool:
    now = time.monotonic()
    with _token_lock:
        token_info = _stop_tokens.get(pid)
        if not token_info:
            return False

        expected, expires_at = token_info
        if expires_at <= now or not hmac.compare_digest(expected, supplied):
            return False

        del _stop_tokens[pid]
        return True


def _same_origin_request() -> bool:
    origin = request.headers.get("Origin")
    if not origin:
        return True
    parsed = urlparse(origin)
    return parsed.scheme in {"http", "https"} and parsed.netloc == request.host


def register_live_table_status(app) -> None:
    if app.extensions.get("pincabos_live_table_status_card"):
        return

    app.extensions["pincabos_live_table_status_card"] = True

    @app.route("/api/live-table-status", methods=["GET"])
    def pincabos_live_table_status():
        table = _find_running_table()
        if not table:
            return jsonify({"running": False})

        return jsonify(
            {
                "running": True,
                "pid": table["pid"],
                "table_name": table["table_name"],
                "stop_token": _issue_token(table["pid"]),
            }
        )

    @app.route("/api/live-table-status/stop", methods=["POST"])
    def pincabos_live_table_status_stop():
        if not _same_origin_request():
            return jsonify({"ok": False, "error": "origin_refused"}), 403

        if request.headers.get("X-Requested-With") != "PinCabOSLiveTableStatus":
            return jsonify({"ok": False, "error": "request_refused"}), 403

        payload = request.get_json(silent=True) or {}
        supplied_token = str(
            payload.get("stop_token")
            or request.headers.get("X-PinCabOS-Live-Stop-Token")
            or ""
        )

        table = _find_running_table()
        if not table:
            return jsonify({"ok": False, "error": "no_running_table"}), 409

        if not _consume_valid_token(table["pid"], supplied_token):
            return jsonify({"ok": False, "error": "invalid_or_expired_token"}), 403

        try:
            os.kill(table["pid"], signal.SIGTERM)
        except ProcessLookupError:
            return jsonify({"ok": True, "running": False})

        return jsonify(
            {
                "ok": True,
                "running": True,
                "table_name": table["table_name"],
                "message": "stop_requested",
            }
        )

    @app.after_request
    def pincabos_inject_live_table_status_card(response):
        if response.mimetype != "text/html" or response.status_code >= 400:
            return response

        if getattr(response, "direct_passthrough", False):
            return response

        try:
            body = response.get_data(as_text=True)
        except RuntimeError:
            return response

        if 'data-pincabos-live-table-status="1"' in body or "</body" not in body.lower():
            return response

        injection = (
            '<link rel="stylesheet" href="/static/pincabos-live-table-status.css?v=5">'
            '<div id="pincabos-live-table-status-root" data-pincabos-live-table-status="1" hidden></div>'
            '<script src="/static/pincabos-live-table-status.js?v=5"></script>'
        )

        idx = body.lower().rfind("</body")
        if idx == -1:
            return response

        response.set_data(body[:idx] + injection + body[idx:])
        return response
