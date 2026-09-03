"""Enveloppes de contrôle strictes, sans exécution de code arbitraire."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Mapping

from . import PROTOCOL_VERSION

MAX_PAYLOAD_BYTES = 65_536
MAX_COMMAND_LIFETIME_SECONDS = 60
MAX_FUTURE_SKEW_SECONDS = 5
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")

COMMAND_TYPES = frozenset(
    {
        "SESSION_PREPARE",
        "PACKAGE_VERIFY",
        "READY_COMMIT",
        "START_COMMIT",
        "HANDOFF_PREPARE",
        "HANDOFF_COMMIT",
        "SESSION_STOP",
    }
)


class ProtocolError(ValueError):
    """Message invalide, expiré, rejoué ou non authentifié."""


def canonical_json(value: Any) -> bytes:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ProtocolError("JSON non canonique") from exc
    return encoded


def payload_digest(payload: Mapping[str, Any]) -> str:
    encoded = canonical_json(payload)
    if len(encoded) > MAX_PAYLOAD_BYTES:
        raise ProtocolError("payload trop volumineux")
    return hashlib.sha256(encoded).hexdigest()


def _require_id(name: str, value: Any) -> str:
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        raise ProtocolError(f"{name} invalide")
    return value


def _require_int(name: str, value: Any, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ProtocolError(f"{name} invalide")
    return value


def _validate_tree(value: Any, depth: int = 0) -> None:
    if depth > 8:
        raise ProtocolError("payload trop profond")
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise ProtocolError("nombre non fini")
        return
    if isinstance(value, list):
        if len(value) > 1024:
            raise ProtocolError("liste trop longue")
        for item in value:
            _validate_tree(item, depth + 1)
        return
    if isinstance(value, dict):
        if len(value) > 256:
            raise ProtocolError("objet trop grand")
        for key, item in value.items():
            if not isinstance(key, str) or len(key) > 128:
                raise ProtocolError("clé de payload invalide")
            _validate_tree(item, depth + 1)
        return
    raise ProtocolError("type de payload interdit")


@dataclass(frozen=True)
class Envelope:
    protocol_version: str
    session_id: str
    command_id: str
    issued_at: int
    expires_at: int
    epoch: int
    sequence: int
    master_cabinet_id: str
    target_cabinet_id: str
    type: str
    payload: Mapping[str, Any]
    payload_hash: str
    signature: str

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "command_id": self.command_id,
            "epoch": self.epoch,
            "expires_at": self.expires_at,
            "issued_at": self.issued_at,
            "master_cabinet_id": self.master_cabinet_id,
            "payload": dict(self.payload),
            "payload_hash": self.payload_hash,
            "protocol_version": self.protocol_version,
            "sequence": self.sequence,
            "session_id": self.session_id,
            "target_cabinet_id": self.target_cabinet_id,
            "type": self.type,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.unsigned_dict(), "signature": self.signature}


def build_envelope(
    *,
    secret: bytes,
    session_id: str,
    command_id: str,
    epoch: int,
    sequence: int,
    master_cabinet_id: str,
    target_cabinet_id: str,
    command_type: str,
    payload: Mapping[str, Any] | None = None,
    issued_at: int | None = None,
    lifetime_seconds: int = 30,
) -> dict[str, Any]:
    if len(secret) < 32:
        raise ProtocolError("secret de session trop court")
    issued = int(time.time()) if issued_at is None else issued_at
    if not 1 <= lifetime_seconds <= MAX_COMMAND_LIFETIME_SECONDS:
        raise ProtocolError("durée de commande invalide")
    body = dict(payload or {})
    _validate_tree(body)
    envelope = Envelope(
        protocol_version=PROTOCOL_VERSION,
        session_id=_require_id("session_id", session_id),
        command_id=_require_id("command_id", command_id),
        issued_at=_require_int("issued_at", issued),
        expires_at=issued + lifetime_seconds,
        epoch=_require_int("epoch", epoch),
        sequence=_require_int("sequence", sequence, 1),
        master_cabinet_id=_require_id("master_cabinet_id", master_cabinet_id),
        target_cabinet_id=_require_id("target_cabinet_id", target_cabinet_id),
        type=command_type,
        payload=body,
        payload_hash=payload_digest(body),
        signature="",
    )
    if command_type not in COMMAND_TYPES:
        raise ProtocolError("type de commande interdit")
    signature = hmac.new(secret, canonical_json(envelope.unsigned_dict()), hashlib.sha256).hexdigest()
    return {**envelope.unsigned_dict(), "signature": signature}


def verify_envelope(
    raw: Mapping[str, Any],
    *,
    secret: bytes,
    expected_target: str,
    now: int | None = None,
) -> Envelope:
    expected_fields = {
        "protocol_version",
        "session_id",
        "command_id",
        "issued_at",
        "expires_at",
        "epoch",
        "sequence",
        "master_cabinet_id",
        "target_cabinet_id",
        "type",
        "payload",
        "payload_hash",
        "signature",
    }
    if not isinstance(raw, Mapping) or set(raw) != expected_fields:
        raise ProtocolError("champs d'enveloppe invalides")
    if len(secret) < 32:
        raise ProtocolError("secret de session trop court")
    payload = raw["payload"]
    if not isinstance(payload, Mapping):
        raise ProtocolError("payload invalide")
    _validate_tree(payload)
    envelope = Envelope(
        protocol_version=str(raw["protocol_version"]),
        session_id=_require_id("session_id", raw["session_id"]),
        command_id=_require_id("command_id", raw["command_id"]),
        issued_at=_require_int("issued_at", raw["issued_at"]),
        expires_at=_require_int("expires_at", raw["expires_at"]),
        epoch=_require_int("epoch", raw["epoch"]),
        sequence=_require_int("sequence", raw["sequence"], 1),
        master_cabinet_id=_require_id("master_cabinet_id", raw["master_cabinet_id"]),
        target_cabinet_id=_require_id("target_cabinet_id", raw["target_cabinet_id"]),
        type=str(raw["type"]),
        payload=dict(payload),
        payload_hash=str(raw["payload_hash"]),
        signature=str(raw["signature"]),
    )
    if envelope.protocol_version != PROTOCOL_VERSION:
        raise ProtocolError("version de protocole incompatible")
    if envelope.type not in COMMAND_TYPES:
        raise ProtocolError("type de commande interdit")
    if envelope.target_cabinet_id != _require_id("expected_target", expected_target):
        raise ProtocolError("mauvais cabinet cible")
    if envelope.expires_at <= envelope.issued_at:
        raise ProtocolError("fenêtre temporelle invalide")
    if envelope.expires_at - envelope.issued_at > MAX_COMMAND_LIFETIME_SECONDS:
        raise ProtocolError("fenêtre temporelle trop longue")
    current = int(time.time()) if now is None else now
    if envelope.issued_at > current + MAX_FUTURE_SKEW_SECONDS:
        raise ProtocolError("commande datée dans le futur")
    if envelope.expires_at < current:
        raise ProtocolError("commande expirée")
    actual_payload_hash = payload_digest(envelope.payload)
    if not hmac.compare_digest(envelope.payload_hash, actual_payload_hash):
        raise ProtocolError("hash de payload invalide")
    if not re.fullmatch(r"[0-9a-f]{64}", envelope.signature):
        raise ProtocolError("signature invalide")
    expected_signature = hmac.new(
        secret, canonical_json(envelope.unsigned_dict()), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(envelope.signature, expected_signature):
        raise ProtocolError("signature invalide")
    return envelope
