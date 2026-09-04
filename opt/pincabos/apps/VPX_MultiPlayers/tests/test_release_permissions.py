"""Empêche les releases de retirer le droit d'exécution du runtime LAB."""
from __future__ import annotations

import stat
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINTS = (
    ROOT / "bin/pincabos-multiplayer-agent",
    ROOT / "install.sh",
    ROOT / "uninstall.sh",
)


class ReleasePermissionsTests(unittest.TestCase):
    def test_multiplayer_entrypoints_are_executable_in_git(self):
        for path in ENTRYPOINTS:
            with self.subTest(path=path.name):
                self.assertTrue(path.is_file(), f"fichier absent: {path}")
                mode = path.stat().st_mode
                self.assertTrue(
                    mode & stat.S_IXUSR,
                    f"{path} doit être versionné exécutable (100755)",
                )
                self.assertTrue(
                    mode & stat.S_IXGRP,
                    f"{path} doit être exécutable par le groupe",
                )
                self.assertTrue(
                    mode & stat.S_IXOTH,
                    f"{path} doit être exécutable par les autres",
                )


if __name__ == "__main__":
    unittest.main()
