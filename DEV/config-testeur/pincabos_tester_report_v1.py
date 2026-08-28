#!/usr/bin/env python3
"""PinCabOS tester report endpoint V1."""

import base64
import hashlib
import json
import os
import re
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from flask import jsonify, request

AUTH = "PinCabOS-Device"
MAX_BYTES = 512 * 1024
RATE_SECONDS = 60
REPO = "KarotsSugarpie/PinCabOS"
BRANCH = "main"
DEST = "DEV/config-testeur"
TOKEN_FILE = Path("/etc/pincabos-release-center/tester-report-github.token")
RATE_LOCK = threading.Lock()
LAST_UPLOAD = {}

MAC_RE = re.compile(r"(?i)\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b")
IPV4_RE = re.compile(
    r"(?<![0-9])(?:(?:25[0-5]|2[0-4][0-9]|1?[0-9]{1,2})\.){3}"
    r"(?:25[0-5]|2[0-4][0-9]|1?[0-9]{1,2})(?![0-9])"
)
SECRET_RES = (
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"(?i)PinCabOS-Device\s+[A-Za-z0-9._~+/=-]{20,}"),
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
)


def _json(payload, status=200):
    response = jsonify(payload)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response


def _token():
    value = str(request.headers.get("Authorization") or "").strip()
    prefix = AUTH + " "
    token = value[len(prefix):].strip() if value.startswith(prefix) else ""
    if not token:
        token = str(request.headers.get("X-PinCabOS-Device-Token") or "").strip()
    return token if 32 <= len(token) <= 256 else ""


def _github_token():
    token = str(os.environ.get("PINCABOS_TESTER_REPORT_GITHUB_TOKEN") or "").strip()
    if token:
        return token
    try:
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    return "" if "\n" in token or "\r" in token else token


def _slug(value):
    value = re.sub(r"[^a-z0-9._-]+", "-", str(value or "").lower())
    return re.sub(r"-{2,}", "-", value).strip("._-")[:64] or "cabinet"


def _sanitize(text):
    text = str(text).replace("\x00", "")
    text = MAC_RE.sub("[MAC-REDACTED]", text)
    text = IPV4_RE.sub("[IP-REDACTED]", text)
    for pattern in SECRET_RES:
        text = pattern.sub("[SECRET-REDACTED]", text)
    return re.sub(
        r"(?im)^(\s*(?:token|password|passwd|secret|api[_-]?key)\s*[:=]\s*).*$",
        r"\1[SECRET-REDACTED]",
        text,
    )


def _github_put(token, path, content, message):
    url = (
        f"https://api.github.com/repos/{REPO}/contents/"
        + urllib.parse.quote(path, safe="/")
    )
    body = json.dumps(
        {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "branch": BRANCH,
        },
        separators=(",", ":"),
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="PUT",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "User-Agent": "PinCabOS-Tester-Report/1",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"github_http_{exc.code}") from None
    except urllib.error.URLError:
        raise RuntimeError("github_unreachable") from None
    sha = str(((data.get("commit") or {}).get("sha") or ""))
    if not sha:
        raise RuntimeError("github_invalid_response")
    return sha


def register_tester_report_v1(app, db):
    if getattr(app, "_pincabos_tester_report_v1", False):
        return
    app._pincabos_tester_report_v1 = True

    @app.post("/api/device/tester-report", endpoint="pincabos_tester_report_v1")
    def tester_report_v1():
        if request.content_length and request.content_length > MAX_BYTES + 65536:
            return _json({"ok": False, "error": "request_too_large"}, 413)
        if not request.is_json:
            return _json({"ok": False, "error": "json_required"}, 415)

        token = _token()
        if not token:
            return _json({"ok": False, "error": "device_authentication_required"}, 401)

        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        con = db()
        try:
            cabinet = con.execute(
                """
                SELECT id, cabinet_name, device_token_hash
                FROM cabinets
                WHERE device_token_hash=? AND is_active=1
                LIMIT 1
                """,
                (digest,),
            ).fetchone()
        finally:
            con.close()

        if not cabinet or not secrets.compare_digest(
            str(cabinet["device_token_hash"] or ""), digest
        ):
            return _json({"ok": False, "error": "device_authentication_required"}, 401)

        cabinet_id = int(cabinet["id"])
        now = time.monotonic()
        with RATE_LOCK:
            previous = LAST_UPLOAD.get(cabinet_id, 0.0)
            if previous and now - previous < RATE_SECONDS:
                retry = max(1, int(RATE_SECONDS - (now - previous)))
                response = _json(
                    {"ok": False, "error": "rate_limited", "retry_after": retry},
                    429,
                )
                response.headers["Retry-After"] = str(retry)
                return response

        payload = request.get_json(silent=True) or {}
        report = payload.get("report")
        if not isinstance(report, str):
            return _json({"ok": False, "error": "report_required"}, 400)

        report = _sanitize(report)
        raw = report.encode("utf-8")
        if not 256 <= len(raw) <= MAX_BYTES:
            return _json({"ok": False, "error": "invalid_report_size"}, 400)
        if "PINFORGE-SAFE - PINCABOS TESTER SYSTEM AUDIT" not in report:
            return _json({"ok": False, "error": "invalid_report_marker"}, 400)

        github_token = _github_token()
        if not github_token:
            return _json({"ok": False, "error": "github_bridge_not_configured"}, 503)

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        cabinet_slug = _slug(cabinet["cabinet_name"])
        filename = f"{cabinet_slug}-{stamp}-{secrets.token_hex(3)}-system-audit.txt"
        path = f"{DEST}/{filename}"
        report_sha = hashlib.sha256(raw).hexdigest()
        content = (
            "PINCABOS TESTER REPORT - SERVER VERIFIED\n"
            f"Cabinet: {cabinet_slug}\n"
            f"Received UTC: {datetime.now(timezone.utc).isoformat()}\n"
            f"SHA256: {report_sha}\n"
            "Privacy filter: enabled\n"
            "============================================================\n\n"
            + report
        )
        try:
            commit_sha = _github_put(
                github_token,
                path,
                content,
                f"tester report: {cabinet_slug} {stamp}",
            )
        except RuntimeError as exc:
            return _json({"ok": False, "error": str(exc)}, 502)

        with RATE_LOCK:
            LAST_UPLOAD[cabinet_id] = time.monotonic()

        return _json(
            {"ok": True, "path": path, "commit_sha": commit_sha, "report_sha256": report_sha},
            201,
        )
