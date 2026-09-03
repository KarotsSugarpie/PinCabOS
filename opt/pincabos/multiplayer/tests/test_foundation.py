from __future__ import annotations

import json
import unittest

from pincabos_sync.pcosrec import encode_records, make_header, verify_bytes
from pincabos_sync.protocol import ProtocolError, build_envelope, verify_envelope
from pincabos_sync.state import AgentState, Phase, assert_single_master
from pincabos_sync.topology import validate_topology


SECRET = b"s" * 32
NOW = 1_800_000_000


def command(kind: str, target: str, sequence: int, epoch: int = 0, master: str = "cab-1"):
    raw = build_envelope(
        secret=SECRET,
        session_id="session-1",
        command_id=f"cmd-{target}-{sequence}",
        epoch=epoch,
        sequence=sequence,
        master_cabinet_id=master,
        target_cabinet_id=target,
        command_type=kind,
        payload={},
        issued_at=NOW,
    )
    return verify_envelope(raw, secret=SECRET, expected_target=target, now=NOW)


class ProtocolTests(unittest.TestCase):
    def test_signed_envelope_round_trip(self):
        envelope = command("SESSION_PREPARE", "cab-1", 1)
        self.assertEqual(envelope.type, "SESSION_PREPARE")

    def test_tampered_payload_is_rejected(self):
        raw = build_envelope(
            secret=SECRET,
            session_id="session-1",
            command_id="cmd-1",
            epoch=0,
            sequence=1,
            master_cabinet_id="cab-1",
            target_cabinet_id="cab-1",
            command_type="SESSION_PREPARE",
            payload={"table": "a"},
            issued_at=NOW,
        )
        raw["payload"]["table"] = "b"
        with self.assertRaises(ProtocolError):
            verify_envelope(raw, secret=SECRET, expected_target="cab-1", now=NOW)

    def test_unknown_command_is_rejected(self):
        with self.assertRaises(ProtocolError):
            build_envelope(
                secret=SECRET,
                session_id="session-1",
                command_id="cmd-1",
                epoch=0,
                sequence=1,
                master_cabinet_id="cab-1",
                target_cabinet_id="cab-1",
                command_type="RUN_BASH",
                issued_at=NOW,
            )


class StateTests(unittest.TestCase):
    def test_two_cabinets_have_one_master(self):
        states = [AgentState("cab-1"), AgentState("cab-2")]
        for state in states:
            state.apply(command("SESSION_PREPARE", state.cabinet_id, 1))
            state.apply(command("READY_COMMIT", state.cabinet_id, 2))
            state.apply(command("START_COMMIT", state.cabinet_id, 3))
        assert_single_master(states)
        self.assertEqual([state.phase for state in states], [Phase.MASTER, Phase.REPLICA])

    def test_handoff_changes_master_with_new_epoch(self):
        states = [AgentState("cab-1"), AgentState("cab-2")]
        for state in states:
            for item in (
                command("SESSION_PREPARE", state.cabinet_id, 1),
                command("READY_COMMIT", state.cabinet_id, 2),
                command("START_COMMIT", state.cabinet_id, 3),
                command("HANDOFF_PREPARE", state.cabinet_id, 4, epoch=1, master="cab-2"),
                command("HANDOFF_COMMIT", state.cabinet_id, 5, epoch=1, master="cab-2"),
            ):
                state.apply(item)
        assert_single_master(states)
        self.assertEqual([state.phase for state in states], [Phase.REPLICA, Phase.MASTER])

    def test_replay_is_rejected(self):
        state = AgentState("cab-1")
        item = command("SESSION_PREPARE", "cab-1", 1)
        state.apply(item)
        with self.assertRaises(ProtocolError):
            state.apply(item)


class PcosrecTests(unittest.TestCase):
    def test_record_chain_round_trip(self):
        header = make_header(
            session_id="session-1",
            table_sha256="a" * 64,
            protected_hashes={"vpx": "b" * 64},
        )
        content = encode_records(
            header,
            [
                {"tick": 0, "type": "SNAPSHOT", "payload": {"ball": [1, 2, 3]}},
                {"tick": 1, "type": "INPUT", "payload": {"left_flipper": True}},
                {"tick": 1, "type": "CHECKSUM", "payload": {"sha256": "c" * 64}},
            ],
        )
        result = verify_bytes(content)
        self.assertEqual(result["records"], 3)
        self.assertEqual(result["last_tick"], 1)

    def test_tampered_record_is_rejected(self):
        content = encode_records(
            make_header(session_id="session-1", table_sha256="a" * 64, protected_hashes={}),
            [{"tick": 0, "type": "MARKER", "payload": {"name": "start"}}],
        )
        rows = content.decode().splitlines()
        row = json.loads(rows[1])
        row["payload"]["name"] = "changed"
        tampered = (rows[0] + "\n" + json.dumps(row) + "\n").encode()
        with self.assertRaises(ProtocolError):
            verify_bytes(tampered)


class TopologyTests(unittest.TestCase):
    def test_cabinet_to_cabinet_plan_has_one_master(self):
        topology = validate_topology(
            {
                "protocol_version": "pcos-sync-control/1",
                "session_id": "session-1",
                "epoch": 0,
                "master_cabinet_id": "cab-1",
                "data_plane": "cabinet-to-cabinet",
                "transport": "pending-poc",
                "members": [
                    {"cabinet_id": "cab-1", "player_number": 1, "role": "master"},
                    {"cabinet_id": "cab-2", "player_number": 2, "role": "replica"},
                ],
            },
            local_cabinet_id="cab-2",
        )
        self.assertEqual(topology.master_cabinet_id, "cab-1")
        self.assertEqual(len(topology.peers), 2)



if __name__ == "__main__":
    unittest.main()
