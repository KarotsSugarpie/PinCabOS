"""
PinCabOS — cache adaptatif pour l'analyse des tables.

Le moteur reconnaît les réponses contenant les résultats
VPX/B2S/ROM/PuP/Serum/AltSound/AltColor/VPS.

Les opérations d'écriture ne sont jamais mises en cache.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import threading
import time
from pathlib import Path
from typing import Any

from flask import Flask, request


CACHE_VERSION = 3
CACHE_TTL_SECONDS = 300
SLOW_SECONDS = 0.500

CACHE_DIR = Path(
    os.environ.get(
        "PINCABOS_TABLE_CACHE_DIR",
        "/var/cache/pincabos/table-analysis",
    )
)

MAX_RESPONSE_BYTES = 32 * 1024 * 1024
MAX_POST_BODY_BYTES = 1024 * 1024
MAX_CACHE_BYTES = 256 * 1024 * 1024
MAX_CACHE_ENTRIES = 1024


ANALYSIS_MARKERS = (
    "vpx",
    "b2s",
    "rom",
    "pup",
    "serum",
    "altsound",
    "altcolor",
    "vps",
)


ANALYSIS_PATH_WORDS = (
    "explorer",
    "table",
    "tables",
    "analyse",
    "analysis",
    "analyze",
    "scan",
    "inventory",
    "browse",
    "folder",
    "files",
)


MUTATION_PATH_WORDS = (
    "save",
    "write",
    "edit",
    "delete",
    "remove",
    "trash",
    "rename",
    "move",
    "mkdir",
    "create",
    "upload",
    "import",
    "export",
    "extract",
    "install",
    "launch",
    "play",
    "start",
    "stop",
    "restart",
    "rollback",
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
    ".iso",
    ".rom",
    ".bin",
    ".mp4",
    ".mkv",
    ".avi",
    ".mp3",
    ".wav",
    ".flac",
)


ACTION_PATTERN = re.compile(
    rb'["\'](?:action|operation|command)["\']'
    rb'\s*[:=]\s*["\']'
    rb'(?:save|write|edit|delete|remove|rename|move|'
    rb'create|upload|import|export|start|stop|launch)',
    re.IGNORECASE,
)


_lock = threading.RLock()


def log(message: str) -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    print(
        f"{timestamp} PINCABOS-TABLE-CACHE {message}",
        file=sys.stderr,
        flush=True,
    )


def target_text() -> str:
    query = request.query_string.decode(
        "utf-8",
        errors="replace",
    )

    if query:
        return f"{request.path}?{query}".lower()

    return request.path.lower()


def request_body_small() -> bytes:
    content_length = request.content_length

    if content_length is not None:
        if content_length > MAX_POST_BODY_BYTES:
            return b""

    try:
        data = request.get_data(
            cache=True,
            as_text=False,
        )
    except Exception:
        return b""

    if len(data) > MAX_POST_BODY_BYTES:
        return b""

    return data


def is_mutation_request() -> bool:
    method = request.method.upper()
    target = target_text()

    if method in ("PUT", "PATCH", "DELETE"):
        return True

    if any(word in target for word in MUTATION_PATH_WORDS):
        return True

    if method == "POST":
        body = request_body_small()

        if body and ACTION_PATTERN.search(body):
            return True

    return False


def request_is_cache_candidate() -> bool:
    method = request.method.upper()
    target = target_text()

    if method not in ("GET", "HEAD", "POST"):
        return False

    if is_mutation_request():
        return False

    if target.endswith(BLOCKED_EXTENSIONS):
        return False

    if any(ext in target for ext in BLOCKED_EXTENSIONS):
        return False

    if method == "POST":
        content_length = request.content_length

        if (
            content_length is not None
            and content_length > MAX_POST_BODY_BYTES
        ):
            return False

    return any(
        word in target
        for word in ANALYSIS_PATH_WORDS
    )


def bypass_requested() -> bool:
    cache_control = request.headers.get(
        "Cache-Control",
        "",
    ).lower()

    pragma = request.headers.get(
        "Pragma",
        "",
    ).lower()

    if "no-cache" in cache_control:
        return True

    if "no-cache" in pragma:
        return True

    for key in (
        "refresh",
        "force",
        "force_refresh",
        "nocache",
        "_refresh",
    ):
        value = request.args.get(key)

        if value is not None:
            if str(value).lower() in (
                "1",
                "true",
                "yes",
                "on",
            ):
                return True

    return False


def identity_digest() -> str:
    identity = "\n".join(
        (
            request.headers.get("Authorization", ""),
            request.headers.get("Cookie", ""),
        )
    )

    return hashlib.sha256(
        identity.encode(
            "utf-8",
            errors="replace",
        )
    ).hexdigest()[:24]


def request_key() -> str | None:
    method = request.method.upper()

    body_hash = ""

    if method == "POST":
        body = request_body_small()

        if not body and request.content_length:
            return None

        body_hash = hashlib.sha256(body).hexdigest()

    source = "\n".join(
        (
            str(CACHE_VERSION),
            method,
            request.path,
            request.query_string.decode(
                "utf-8",
                errors="replace",
            ),
            body_hash,
            identity_digest(),
            request.headers.get("Accept", ""),
        )
    )

    return hashlib.sha256(
        source.encode(
            "utf-8",
            errors="replace",
        )
    ).hexdigest()


def paths_for_key(key: str) -> tuple[Path, Path]:
    return (
        CACHE_DIR / f"{key}.json",
        CACHE_DIR / f"{key}.body",
    )


def remove_entry(key: str) -> None:
    metadata_path, body_path = paths_for_key(key)

    for path in (metadata_path, body_path):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass


def clear_cache(reason: str) -> None:
    CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    removed = 0

    with _lock:
        for path in CACHE_DIR.iterdir():
            if path.suffix not in (
                ".json",
                ".body",
                ".tmp",
            ):
                continue

            try:
                path.unlink()
                removed += 1
            except FileNotFoundError:
                pass
            except OSError:
                pass

    log(
        f"INVALIDATE reason={reason!r} "
        f"files={removed}"
    )


def load_cached_response(app: Flask, key: str):
    metadata_path, body_path = paths_for_key(key)

    try:
        metadata = json.loads(
            metadata_path.read_text(
                encoding="utf-8",
            )
        )

        if metadata.get("version") != CACHE_VERSION:
            remove_entry(key)
            return None

        created = float(metadata["created"])
        age = time.time() - created

        if age < 0 or age > CACHE_TTL_SECONDS:
            remove_entry(key)
            return None

        body = body_path.read_bytes()

        expected_size = int(metadata["size"])

        if len(body) != expected_size:
            remove_entry(key)
            return None

        response = app.response_class(
            body,
            status=int(metadata["status"]),
            headers=metadata["headers"],
        )

        response.headers[
            "X-PinCabOS-Table-Analysis-Cache"
        ] = "HIT"

        response.headers[
            "X-PinCabOS-Table-Analysis-Cache-Age"
        ] = str(int(age))

        return response

    except FileNotFoundError:
        return None

    except Exception as exc:
        remove_entry(key)

        log(
            f"CACHE-READ-ERROR "
            f"key={key[:12]} "
            f"error={exc!r}"
        )

        return None


def response_marker_count(body: bytes) -> int:
    sample = body[: 4 * 1024 * 1024].lower()

    return sum(
        1
        for marker in ANALYSIS_MARKERS
        if marker.encode("ascii") in sample
    )


def response_is_analysis(
    response,
    body: bytes,
    duration: float,
) -> bool:
    if response.status_code != 200:
        return False

    if response.is_streamed:
        return False

    if response.direct_passthrough:
        return False

    if len(body) > MAX_RESPONSE_BYTES:
        return False

    if "Set-Cookie" in response.headers:
        return False

    content_type = (
        response.headers.get(
            "Content-Type",
            "",
        )
        .split(";", 1)[0]
        .strip()
        .lower()
    )

    if content_type not in (
        "application/json",
        "text/html",
        "text/plain",
    ):
        return False

    marker_count = response_marker_count(body)

    target = target_text()

    path_looks_relevant = any(
        word in target
        for word in ANALYSIS_PATH_WORDS
    )

    if marker_count >= 3:
        return True

    return (
        duration >= SLOW_SECONDS
        and path_looks_relevant
        and marker_count >= 1
    )


def response_headers_for_cache(response) -> list[list[str]]:
    ignored = {
        "content-length",
        "date",
        "server",
        "connection",
        "transfer-encoding",
        "set-cookie",
        "x-pincabos-table-analysis-cache",
        "x-pincabos-table-analysis-cache-age",
    }

    return [
        [name, value]
        for name, value in response.headers.items()
        if name.lower() not in ignored
    ]


def store_response(
    key: str,
    response,
    body: bytes,
) -> None:
    CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    metadata_path, body_path = paths_for_key(key)

    unique = (
        f"{os.getpid()}-"
        f"{threading.get_ident()}-"
        f"{time.time_ns()}"
    )

    metadata_tmp = CACHE_DIR / (
        f"{key}.{unique}.json.tmp"
    )

    body_tmp = CACHE_DIR / (
        f"{key}.{unique}.body.tmp"
    )

    metadata: dict[str, Any] = {
        "version": CACHE_VERSION,
        "created": time.time(),
        "status": int(response.status_code),
        "headers": response_headers_for_cache(
            response
        ),
        "size": len(body),
        "target": target_text()[:500],
    }

    with _lock:
        body_tmp.write_bytes(body)

        metadata_tmp.write_text(
            json.dumps(
                metadata,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )

        os.replace(body_tmp, body_path)
        os.replace(metadata_tmp, metadata_path)

    response.headers[
        "X-PinCabOS-Table-Analysis-Cache"
    ] = "MISS-STORED"


def prune_cache() -> None:
    CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    metadata_files = []

    for path in CACHE_DIR.glob("*.json"):
        try:
            stat = path.stat()

            body_path = path.with_suffix(".body")

            body_size = (
                body_path.stat().st_size
                if body_path.exists()
                else 0
            )

            metadata_files.append(
                (
                    stat.st_mtime,
                    path,
                    body_path,
                    stat.st_size + body_size,
                )
            )

        except OSError:
            continue

    metadata_files.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    total_size = 0

    for index, item in enumerate(metadata_files):
        _, metadata_path, body_path, size = item

        total_size += size

        remove = (
            index >= MAX_CACHE_ENTRIES
            or total_size > MAX_CACHE_BYTES
        )

        if remove:
            for path in (
                metadata_path,
                body_path,
            ):
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
                except OSError:
                    pass


def install_patch() -> None:
    flag_name = (
        "_pincabos_table_analysis_cache_v3"
    )

    if getattr(Flask, flag_name, False):
        return

    CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    prune_cache()

    original_dispatch = (
        Flask.full_dispatch_request
    )

    def cached_dispatch(self):
        started = time.perf_counter()
        method = request.method.upper()
        target = target_text()
        mutation = is_mutation_request()
        candidate = (
            request_is_cache_candidate()
            and not bypass_requested()
        )

        key = None

        if candidate:
            key = request_key()

            if key:
                cached = load_cached_response(
                    self,
                    key,
                )

                if cached is not None:
                    duration = (
                        time.perf_counter()
                        - started
                    )

                    log(
                        f"HIT {duration:.4f}s "
                        f"{method} {target[:500]}"
                    )

                    return cached

        response = original_dispatch(self)

        duration = (
            time.perf_counter()
            - started
        )

        if (
            mutation
            and response.status_code < 400
        ):
            clear_cache(
                f"{method} {target[:300]}"
            )

            return response

        if candidate and key:
            try:
                body = response.get_data()

                if response_is_analysis(
                    response,
                    body,
                    duration,
                ):
                    store_response(
                        key,
                        response,
                        body,
                    )

                    prune_cache()

                    log(
                        f"MISS-STORED "
                        f"{duration:.3f}s "
                        f"{method} {target[:500]} "
                        f"bytes={len(body)}"
                    )

                    return response

            except Exception as exc:
                log(
                    f"CACHE-WRITE-ERROR "
                    f"{method} {target[:300]} "
                    f"error={exc!r}"
                )

        if duration >= SLOW_SECONDS:
            log(
                f"SLOW {duration:.3f}s "
                f"{method} {target[:500]} "
                f"candidate={candidate}"
            )

        return response

    Flask.full_dispatch_request = (
        cached_dispatch
    )

    setattr(
        Flask,
        flag_name,
        True,
    )

    log(
        "module chargé "
        f"version={CACHE_VERSION} "
        f"ttl={CACHE_TTL_SECONDS}s "
        f"directory={CACHE_DIR}"
    )


install_patch()
