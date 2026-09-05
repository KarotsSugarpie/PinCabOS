from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pincabos_multiplayer.control import (
    CabinetControlError,
    CabinetControlManager,
    VPINFE_SERVICE,
)
from pincabos_multiplayer.runtime import RuntimeLayout, sha256_file


class FakeSystemd:
    def __init__(self, active: bool) -> None:
        self.active = active
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        self.commands.append(list(command))
        if command[:3] == ["systemctl", "is-active", "--quiet"]:
            return subprocess.CompletedProcess(command, 0 if self.active else 3, "", "")
        if command == ["systemctl", "stop", VPINFE_SERVICE]:
            self.active = False
            return subprocess.CompletedProcess(command, 0, "", "")
        if command == ["systemctl", "start", VPINFE_SERVICE]:
            self.active = True
            return subprocess.CompletedProcess(command, 0, "", "")
        return subprocess.CompletedProcess(command, 1, "", "unexpected")


def session(phase: str, manifest_hash: str | None = None) -> dict:
    return {
        "session_id": "mp-test",
        "phase": phase,
        "is_this_cabinet_member": True,
        "room_code": "ABC123",
        "manifest_hash": manifest_hash,
        "topology": {"role": "replica"},
    }


def state(desired: str, phase: str, manifest_hash: str | None = None) -> dict:
    return {
        "session": session(phase, manifest_hash),
        "control": {"desired": desired, "generation": 7},
    }


class CabinetControlTests(unittest.TestCase):
    def test_missing_control_contract_fails_safe_and_keeps_vpinfe(self):
        with tempfile.TemporaryDirectory() as directory:
            layout = RuntimeLayout(Path(directory) / "VPX_MultiPlayers")
            layout.prepare_writable_directories()
            systemd = FakeSystemd(active=True)
            manager = CabinetControlManager(layout, runner=systemd)

            lease = manager.reconcile({"session": session("ready")})

            self.assertEqual(lease["state"], "released")
            self.assertTrue(systemd.active)
            self.assertNotIn(["systemctl", "stop", VPINFE_SERVICE], systemd.commands)

    def test_armed_acquires_control_and_stops_vpinfe(self):
        with tempfile.TemporaryDirectory() as directory:
            layout = RuntimeLayout(Path(directory) / "VPX_MultiPlayers")
            layout.prepare_writable_directories()
            systemd = FakeSystemd(active=True)
            manager = CabinetControlManager(layout, runner=systemd)

            lease = manager.reconcile(state("armed", "ready"))

            self.assertEqual(lease["owner"], "multiplayer")
            self.assertEqual(lease["state"], "armed")
            self.assertEqual(lease["generation"], 7)
            self.assertTrue(lease["vpinfe_was_active"])
            self.assertFalse(lease["vpinfe_active"])
            self.assertFalse(systemd.active)
            self.assertIn(["systemctl", "stop", VPINFE_SERVICE], systemd.commands)

    def test_video_desired_is_recorded_without_launching_vpx(self):
        with tempfile.TemporaryDirectory() as directory:
            layout = RuntimeLayout(Path(directory) / "VPX_MultiPlayers")
            layout.prepare_writable_directories()
            systemd = FakeSystemd(active=True)
            manager = CabinetControlManager(layout, runner=systemd)

            with mock.patch.object(RuntimeLayout, "launch_detached", autospec=True) as launch:
                lease = manager.reconcile(state("video", "ready"))

            launch.assert_not_called()
            self.assertEqual(lease["state"], "video")
            self.assertTrue(lease["video_desired"])
            self.assertEqual(lease["video_state"], "pending-hook")

    def test_running_launches_only_the_table_matching_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            layout = RuntimeLayout(Path(directory) / "VPX_MultiPlayers")
            layout.prepare_writable_directories()
            table = layout.tables / "poc.vpx"
            table.write_bytes(b"same-table")
            manifest = sha256_file(table)
            systemd = FakeSystemd(active=True)
            manager = CabinetControlManager(layout, runner=systemd)

            with mock.patch.object(
                RuntimeLayout,
                "launch_detached",
                autospec=True,
                return_value=4242,
            ) as launch:
                lease = manager.reconcile(state("running", "running", manifest))

            launch.assert_called_once_with(layout, "poc.vpx")
            self.assertEqual(lease["engine_pid"], 4242)
            self.assertEqual(lease["table"], "poc.vpx")
            self.assertEqual(lease["state"], "running")
            self.assertFalse(systemd.active)

    def test_running_is_rejected_if_server_session_is_not_running(self):
        with tempfile.TemporaryDirectory() as directory:
            layout = RuntimeLayout(Path(directory) / "VPX_MultiPlayers")
            layout.prepare_writable_directories()
            systemd = FakeSystemd(active=True)
            manager = CabinetControlManager(layout, runner=systemd)

            with self.assertRaises(CabinetControlError):
                manager.reconcile(state("running", "ready", "a" * 64))

            self.assertTrue(systemd.active)

    def test_server_release_restores_vpinfe(self):
        with tempfile.TemporaryDirectory() as directory:
            layout = RuntimeLayout(Path(directory) / "VPX_MultiPlayers")
            layout.prepare_writable_directories()
            systemd = FakeSystemd(active=True)
            manager = CabinetControlManager(layout, runner=systemd)

            manager.reconcile(state("armed", "ready"))
            self.assertFalse(systemd.active)

            lease = manager.reconcile(state("released", "stopped"))

            self.assertEqual(lease["state"], "released")
            self.assertTrue(lease["vpinfe_restored"])
            self.assertTrue(systemd.active)
            self.assertIn(["systemctl", "start", VPINFE_SERVICE], systemd.commands)

    def test_release_does_not_start_vpinfe_if_it_was_already_stopped(self):
        with tempfile.TemporaryDirectory() as directory:
            layout = RuntimeLayout(Path(directory) / "VPX_MultiPlayers")
            layout.prepare_writable_directories()
            systemd = FakeSystemd(active=False)
            manager = CabinetControlManager(layout, runner=systemd)

            manager.reconcile(state("armed", "ready"))
            lease = manager.reconcile(state("released", "stopped"))

            self.assertFalse(lease["vpinfe_restored"])
            self.assertFalse(systemd.active)
            self.assertNotIn(["systemctl", "start", VPINFE_SERVICE], systemd.commands)

    def test_running_rejects_unknown_table_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            layout = RuntimeLayout(Path(directory) / "VPX_MultiPlayers")
            layout.prepare_writable_directories()
            (layout.tables / "poc.vpx").write_bytes(b"table")
            systemd = FakeSystemd(active=True)
            manager = CabinetControlManager(layout, runner=systemd)

            with self.assertRaises(CabinetControlError):
                manager.reconcile(state("running", "running", "a" * 64))

            self.assertFalse(systemd.active)
            self.assertEqual(manager.lease()["owner"], "multiplayer")


if __name__ == "__main__":
    unittest.main()
