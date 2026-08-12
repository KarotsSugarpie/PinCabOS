"""
PinCabOS — cache serveur PinCab Explorer.

Cache uniquement les requêtes GET de navigation et de liste.
Les modifications, sauvegardes, imports et commandes restent immédiats.
"""

from __future__ import annotations

import hashlib
import sys
import threading
import time
from collections import OrderedDict

from flask import Flask, request


CACHE_TTL_SECONDS = 8.0
SLOW_REQUEST_SECONDS = 0.300
MAX_CACHE_BODY_BYTES = 4 * 1024 * 1024
MAX_CACHE_TOTAL_BYTES = 64 * 1024 * 1024
MAX_CACHE_ENTRIES = 256


SAFE_KEYWORDS = (
    "explorer",
    "browse",
    "browser",
    "directory",
    "directories",
    "folder",
    "folders",
    "list",
    "listing",
    "tree",
    "tables",
    "table-list",
    "files",
    "file-list",
    "media-list",
)


BLOCKED_KEYWORDS = (
    "save",
    "write",
    "edit",
    "update",
    "delete",
    "remove",
    "trash",
    "move",
    "rename",
    "mkdir",
    "create",
    "upload",
    "import",
    "export",
    "extract",
    "install",
    "start",
    "stop",
    "restart",
    "service",
    "status",
    "launch",
    "play",
    "run",
    "test",
    "download",
    "stream",
    "live",
    "capture",
    "preview",
    "thumbnail",
    "logs",
    "logout",
    "login",
)


BLOCKED_EXTENSIONS = (
    ".vbs",
    ".vpx",
    ".directb2s",
    ".zip",
    ".7z",
    ".rar",
    ".tar",
    ".gz",
    ".rom",
    ".bin",
    ".exe",
    ".iso",
    ".mp4",
    ".mkv",
    ".avi",
    ".mp3",
    ".wav",
    ".flac",
)


_cache_lock = threading.RLock()
_cache = OrderedDict()
_cache_total_bytes = 0


def log_line(message: str) -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(
        f"{timestamp} PINCABOS-PERF {message}",
        file=sys.stderr,
        flush=True,
    )


def request_identity() -> str:
    identity = "|".join(
        (
            request.headers.get("Authorization", ""),
            request.headers.get("Cookie", ""),
        )
    )

    return hashlib.sha256(
        identity.encode("utf-8", errors="replace")
    ).hexdigest()[:16]


def cache_key() -> str:
    query = request.query_string.decode(
        "utf-8",
        errors="replace",
    )

    return "|".join(
        (
            request.method,
            request.path,
            query,
            request_identity(),
            request.headers.get("Accept", ""),
        )
    )


def is_safe_cache_request() -> bool:
    if request.method not in ("GET", "HEAD"):
        return False

    path = request.path.lower()

    if path.endswith(BLOCKED_EXTENSIONS):
        return False

    if any(word in path for word in BLOCKED_KEYWORDS):
        return False

    return any(word in path for word in SAFE_KEYWORDS)


def remove_expired(now: float) -> None:
    global _cache_total_bytes

    expired = []

    for key, entry in _cache.items():
        if entry["expires"] <= now:
            expired.append(key)

    for key in expired:
        entry = _cache.pop(key, None)

        if entry is not None:
            _cache_total_bytes -= entry["size"]


def enforce_limits() -> None:
    global _cache_total_bytes

    while (
        len(_cache) > MAX_CACHE_ENTRIES
        or _cache_total_bytes > MAX_CACHE_TOTAL_BYTES
    ):
        _, entry = _cache.popitem(last=False)
        _cache_total_bytes -= entry["size"]


def get_cached_response(app: Flask):
    now = time.monotonic()
    key = cache_key()

    with _cache_lock:
        remove_expired(now)

        entry = _cache.get(key)

        if entry is None:
            return None

        _cache.move_to_end(key)

        response = app.response_class(
            entry["body"],
            status=entry["status"],
            headers=entry["headers"],
        )

        response.headers[
            "X-PinCabOS-Server-Cache"
        ] = "HIT"

        response.headers[
            "X-PinCabOS-Server-Cache-Age"
        ] = f"{now - entry['created']:.3f}"

        return response


def store_response(app: Flask, response) -> None:
    global _cache_total_bytes

    if response.status_code != 200:
        return

    if response.is_streamed or response.direct_passthrough:
        return

    content_type = (
        response.headers.get("Content-Type", "")
        .split(";", 1)[0]
        .strip()
        .lower()
    )

    if content_type not in (
        "application/json",
        "text/html",
        "text/plain",
    ):
        return

    if "Set-Cookie" in response.headers:
        return

    body = response.get_data()

    if len(body) > MAX_CACHE_BODY_BYTES:
        return

    ignored_headers = {
        "content-length",
        "date",
        "server",
        "set-cookie",
        "connection",
        "transfer-encoding",
    }

    headers = [
        (name, value)
        for name, value in response.headers.items()
        if name.lower() not in ignored_headers
    ]

    now = time.monotonic()
    key = cache_key()

    entry = {
        "created": now,
        "expires": now + CACHE_TTL_SECONDS,
        "body": body,
        "status": response.status_code,
        "headers": headers,
        "size": len(body),
    }

    with _cache_lock:
        old_entry = _cache.pop(key, None)

        if old_entry is not None:
            _cache_total_bytes -= old_entry["size"]

        _cache[key] = entry
        _cache_total_bytes += entry["size"]

        enforce_limits()

    response.headers[
        "X-PinCabOS-Server-Cache"
    ] = "MISS-STORED"


def install_patch() -> None:
    if getattr(
        Flask,
        "_pincabos_explorer_performance_v2",
        False,
    ):
        return

    original_dispatch = Flask.full_dispatch_request

    def pincabos_dispatch(self):
        safe_request = False
        started = time.perf_counter()

        try:
            safe_request = is_safe_cache_request()

            if safe_request:
                cached = get_cached_response(self)

                if cached is not None:
                    return cached

            response = original_dispatch(self)

            if safe_request:
                store_response(self, response)

            return response

        finally:
            duration = time.perf_counter() - started

            if duration >= SLOW_REQUEST_SECONDS:
                try:
                    query = request.query_string.decode(
                        "utf-8",
                        errors="replace",
                    )

                    target = request.path

                    if query:
                        target = f"{target}?{query}"

                    log_line(
                        f"SLOW {duration:.3f}s "
                        f"{request.method} {target} "
                        f"cacheable={safe_request}"
                    )

                except Exception:
                    pass

    Flask.full_dispatch_request = pincabos_dispatch

    Flask._pincabos_explorer_performance_v2 = True

    log_line(
        "module chargé "
        f"ttl={CACHE_TTL_SECONDS}s "
        f"slow={SLOW_REQUEST_SECONDS}s"
    )


install_patch()
