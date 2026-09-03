"""Validation du plan logique cabinet-à-cabinet, sans ouvrir de socket."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from . import PROTOCOL_VERSION
from .protocol import ID_PATTERN, ProtocolError


@dataclass(frozen=True)
class Peer:
    cabinet_id: str
    player_number: int
    role: str


@dataclass(frozen=True)
class Topology:
    session_id: str
    epoch: int
    master_cabinet_id: str
    local_cabinet_id: str
    peers: tuple[Peer, ...]
    transport: str


def validate_topology(raw: Mapping[str, Any], *, local_cabinet_id: str) -> Topology:
    fields = {
        "protocol_version",
        "session_id",
        "epoch",
        "master_cabinet_id",
        "data_plane",
        "transport",
        "members",
    }
    if not isinstance(raw, Mapping) or set(raw) != fields:
        raise ProtocolError("champs de topologie invalides")
    if raw["protocol_version"] != PROTOCOL_VERSION:
        raise ProtocolError("version de topologie incompatible")
    if raw["data_plane"] != "cabinet-to-cabinet":
        raise ProtocolError("plan de données invalide")
    if raw["transport"] != "pending-poc":
        raise ProtocolError("transport non autorisé à cette phase")
    session_id = raw["session_id"]
    master = raw["master_cabinet_id"]
    if not isinstance(session_id, str) or not ID_PATTERN.fullmatch(session_id):
        raise ProtocolError("session de topologie invalide")
    if not isinstance(master, str) or not ID_PATTERN.fullmatch(master):
        raise ProtocolError("maître de topologie invalide")
    epoch = raw["epoch"]
    if isinstance(epoch, bool) or not isinstance(epoch, int) or epoch < 0:
        raise ProtocolError("époque de topologie invalide")
    members = raw["members"]
    if not isinstance(members, list) or not 2 <= len(members) <= 4:
        raise ProtocolError("deux à quatre membres requis")
    peers = []
    cabinets: set[str] = set()
    players: set[int] = set()
    masters = 0
    for item in members:
        if not isinstance(item, Mapping) or set(item) != {"cabinet_id", "player_number", "role"}:
            raise ProtocolError("membre de topologie invalide")
        cabinet_id = item["cabinet_id"]
        player = item["player_number"]
        role = item["role"]
        if not isinstance(cabinet_id, str) or not ID_PATTERN.fullmatch(cabinet_id):
            raise ProtocolError("cabinet de topologie invalide")
        if isinstance(player, bool) or not isinstance(player, int) or not 1 <= player <= 4:
            raise ProtocolError("numéro de joueur invalide")
        if role not in {"master", "replica"}:
            raise ProtocolError("rôle de pair invalide")
        if cabinet_id in cabinets or player in players:
            raise ProtocolError("pair dupliqué")
        if role == "master":
            masters += 1
            if cabinet_id != master:
                raise ProtocolError("maître incohérent")
        cabinets.add(cabinet_id)
        players.add(player)
        peers.append(Peer(cabinet_id, player, role))
    if masters != 1 or master not in cabinets:
        raise ProtocolError("un seul maître est requis")
    if local_cabinet_id not in cabinets:
        raise ProtocolError("cabinet local absent de la topologie")
    return Topology(session_id, epoch, master, local_cabinet_id, tuple(peers), "pending-poc")
