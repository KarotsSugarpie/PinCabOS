"""Conteneur de preuve PCOSREC v0 avec chaîne SHA-256."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .protocol import ProtocolError, canonical_json

GENESIS_HASH = "0" * 64
RECORD_TYPES = frozenset({"SNAPSHOT", "INPUT", "STATE", "CHECKSUM", "MARKER"})


def make_header(*, session_id: str, table_sha256: str, protected_hashes: Mapping[str, str]) -> dict[str, Any]:
    if not session_id or len(session_id) > 128:
        raise ProtocolError("session PCOSREC invalide")
    if len(table_sha256) != 64:
        raise ProtocolError("hash de table invalide")
    return {
        "format": "PCOSREC",
        "version": 0,
        "session_id": session_id,
        "table_sha256": table_sha256,
        "protected_hashes": dict(sorted(protected_hashes.items())),
    }


def encode_records(header: Mapping[str, Any], records: Iterable[Mapping[str, Any]]) -> bytes:
    if header.get("format") != "PCOSREC" or header.get("version") != 0:
        raise ProtocolError("en-tête PCOSREC invalide")
    lines = [canonical_json(dict(header))]
    previous = hashlib.sha256(lines[0]).hexdigest()
    last_tick = -1
    for index, item in enumerate(records, start=1):
        tick = item.get("tick")
        kind = item.get("type")
        payload = item.get("payload")
        if isinstance(tick, bool) or not isinstance(tick, int) or tick < last_tick:
            raise ProtocolError("tick PCOSREC invalide")
        if kind not in RECORD_TYPES or not isinstance(payload, Mapping):
            raise ProtocolError("record PCOSREC invalide")
        unsigned = {
            "index": index,
            "payload": dict(payload),
            "previous_hash": previous,
            "tick": tick,
            "type": kind,
        }
        record_hash = hashlib.sha256(canonical_json(unsigned)).hexdigest()
        lines.append(canonical_json({**unsigned, "record_hash": record_hash}))
        previous = record_hash
        last_tick = tick
    return b"\n".join(lines) + b"\n"


def verify_bytes(content: bytes) -> dict[str, Any]:
    try:
        rows = [json.loads(line) for line in content.splitlines() if line.strip()]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError("PCOSREC illisible") from exc
    if not rows or rows[0].get("format") != "PCOSREC" or rows[0].get("version") != 0:
        raise ProtocolError("en-tête PCOSREC invalide")
    previous = hashlib.sha256(canonical_json(rows[0])).hexdigest()
    last_tick = -1
    for expected_index, row in enumerate(rows[1:], start=1):
        if set(row) != {"index", "payload", "previous_hash", "record_hash", "tick", "type"}:
            raise ProtocolError("champs PCOSREC invalides")
        if row["index"] != expected_index or row["previous_hash"] != previous:
            raise ProtocolError("chaîne PCOSREC brisée")
        if (
            row["type"] not in RECORD_TYPES
            or isinstance(row["tick"], bool)
            or not isinstance(row["tick"], int)
            or row["tick"] < last_tick
            or not isinstance(row["payload"], dict)
        ):
            raise ProtocolError("ordre PCOSREC invalide")
        unsigned = {key: row[key] for key in row if key != "record_hash"}
        actual = hashlib.sha256(canonical_json(unsigned)).hexdigest()
        if not hmac_compare(row["record_hash"], actual):
            raise ProtocolError("hash PCOSREC invalide")
        previous = actual
        last_tick = row["tick"]
    return {"records": len(rows) - 1, "last_tick": last_tick, "final_hash": previous}


def hmac_compare(left: Any, right: str) -> bool:
    import hmac

    return isinstance(left, str) and hmac.compare_digest(left, right)


def verify_file(path: str | Path) -> dict[str, Any]:
    return verify_bytes(Path(path).read_bytes())
