from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pincabos_multiplayer.runtime import (
    RuntimeIsolationError,
    RuntimeLayout,
    install_engine_copy,
)


class RuntimeTests(unittest.TestCase):
    def test_engine_copy_is_complete_and_source_is_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = base / "private-source"
            source.mkdir()
            binary = source / "VPinballX_BGFX"
            binary.write_bytes(b"fake-vpx-binary")
            binary.chmod(0o755)
            (source / "libvpx-test.so").write_bytes(b"library")
            before = binary.read_bytes()

            layout = RuntimeLayout(base / "VPX_MultiPlayers")
            result = install_engine_copy(layout, source)

            self.assertEqual(binary.read_bytes(), before)
            self.assertEqual(
                result["source_engine_sha256"], result["copied_engine_sha256"]
            )
            self.assertTrue((layout.engine / "libvpx-test.so").is_file())
            with self.assertRaises(RuntimeIsolationError):
                install_engine_copy(layout, source)

    def test_launch_uses_only_isolated_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            layout = RuntimeLayout(Path(directory) / "VPX_MultiPlayers")
            layout.prepare_writable_directories()
            layout.engine.mkdir()
            binary = layout.engine / "VPinballX_BGFX"
            binary.write_bytes(b"engine")
            binary.chmod(0o755)
            table = layout.tables / "poc.vpx"
            table.write_bytes(b"table")

            command = layout.launch_command("poc.vpx")
            environment = layout.isolated_environment()

            self.assertEqual(command[0], str(binary))
            self.assertEqual(command[1:3], ["-PrefPath", str(layout.root / "config" / "vpx")])
            self.assertEqual(command[-2:], ["-play", str(table)])
            for key in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
                self.assertTrue(environment[key].startswith(str(layout.root)))

    def test_launch_environment_includes_pinball_desktop_session(self):
        with tempfile.TemporaryDirectory() as directory:
            layout = RuntimeLayout(Path(directory) / "VPX_MultiPlayers")
            layout.prepare_writable_directories()
            runtime_uid = os.geteuid()

            with mock.patch.dict(
                os.environ, {"PINCABOS_MULTIPLAYER_DISPLAY": ":9"}, clear=False
            ):
                environment = layout.isolated_environment(runtime_uid)

            self.assertEqual(environment["DISPLAY"], ":9")
            self.assertEqual(
                environment["XDG_RUNTIME_DIR"], f"/run/user/{runtime_uid}"
            )
            self.assertEqual(
                environment["DBUS_SESSION_BUS_ADDRESS"],
                f"unix:path=/run/user/{runtime_uid}/bus",
            )
            self.assertEqual(environment["HOME"], str(layout.root / "home"))
            self.assertEqual(
                environment["XDG_CONFIG_HOME"], str(layout.root / "config")
            )

    def test_table_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            layout = RuntimeLayout(Path(directory) / "VPX_MultiPlayers")
            layout.prepare_writable_directories()
            with self.assertRaises(RuntimeIsolationError):
                layout.table("../private.vpx")


if __name__ == "__main__":
    unittest.main()

