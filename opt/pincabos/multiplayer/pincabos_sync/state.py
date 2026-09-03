"""Machine d'état locale; aucun transport et aucun lancement VPX."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .protocol import Envelope, ProtocolError


class Phase(str, Enum):
    IDLE = "idle"
    PREPARING = "preparing"
    READY = "ready"
    MASTER = "master"
    REPLICA = "replica"
    HANDOFF = "handoff"
    STOPPED = "stopped"


@dataclass
class AgentState:
    cabinet_id: str
    phase: Phase = Phase.IDLE
    session_id: str | None = None
    epoch: int = 0
    last_sequence: int = 0
    master_cabinet_id: str | None = None
    pending_master_cabinet_id: str | None = None
    seen_command_ids: set[str] = field(default_factory=set)

    def apply(self, command: Envelope) -> None:
        if command.target_cabinet_id != self.cabinet_id:
            raise ProtocolError("commande destinée à un autre cabinet")
        if command.command_id in self.seen_command_ids:
            raise ProtocolError("commande rejouée")
        if command.sequence <= self.last_sequence and command.session_id == self.session_id:
            raise ProtocolError("séquence périmée")

        if command.type == "SESSION_PREPARE":
            if self.phase not in {Phase.IDLE, Phase.STOPPED}:
                raise ProtocolError("session locale déjà active")
            self.session_id = command.session_id
            self.epoch = command.epoch
            self.master_cabinet_id = command.master_cabinet_id
            self.pending_master_cabinet_id = None
            self.phase = Phase.PREPARING
            self.seen_command_ids.clear()
        else:
            if command.session_id != self.session_id:
                raise ProtocolError("session inconnue")
            if command.epoch < self.epoch:
                raise ProtocolError("époque périmée")

        if command.type == "PACKAGE_VERIFY":
            if self.phase != Phase.PREPARING:
                raise ProtocolError("vérification de package hors séquence")
        elif command.type == "READY_COMMIT":
            if self.phase != Phase.PREPARING:
                raise ProtocolError("READY hors séquence")
            self.phase = Phase.READY
        elif command.type == "START_COMMIT":
            if self.phase != Phase.READY or command.epoch != self.epoch:
                raise ProtocolError("START hors séquence")
            self.master_cabinet_id = command.master_cabinet_id
            self.phase = Phase.MASTER if self.cabinet_id == command.master_cabinet_id else Phase.REPLICA
        elif command.type == "HANDOFF_PREPARE":
            if self.phase not in {Phase.MASTER, Phase.REPLICA}:
                raise ProtocolError("HANDOFF_PREPARE hors séquence")
            if command.epoch != self.epoch + 1:
                raise ProtocolError("nouvelle époque invalide")
            self.pending_master_cabinet_id = command.master_cabinet_id
            self.phase = Phase.HANDOFF
        elif command.type == "HANDOFF_COMMIT":
            if self.phase != Phase.HANDOFF:
                raise ProtocolError("HANDOFF_COMMIT hors séquence")
            if command.epoch != self.epoch + 1:
                raise ProtocolError("commit d'époque invalide")
            if command.master_cabinet_id != self.pending_master_cabinet_id:
                raise ProtocolError("maître de handoff incohérent")
            self.epoch = command.epoch
            self.master_cabinet_id = command.master_cabinet_id
            self.pending_master_cabinet_id = None
            self.phase = Phase.MASTER if self.cabinet_id == command.master_cabinet_id else Phase.REPLICA
        elif command.type == "SESSION_STOP":
            self.phase = Phase.STOPPED
            self.pending_master_cabinet_id = None

        self.last_sequence = command.sequence
        self.seen_command_ids.add(command.command_id)
        if len(self.seen_command_ids) > 4096:
            raise ProtocolError("trop de commandes dans la session")


def assert_single_master(states: list[AgentState]) -> None:
    active = [state for state in states if state.phase == Phase.MASTER]
    if len(active) > 1:
        raise ProtocolError("double maître détecté")
    session_ids = {state.session_id for state in states if state.session_id}
    if len(session_ids) > 1:
        raise ProtocolError("sessions incohérentes")
    authorities = {
        state.master_cabinet_id
        for state in states
        if state.phase in {Phase.MASTER, Phase.REPLICA}
    }
    if len(authorities) > 1:
        raise ProtocolError("autorités incohérentes")
