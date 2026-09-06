"""PINCABOS_TOPOLOGIE_VERROU_BOOT_V1 : le verrou de la topologie ne bloque plus VPinFE au boot.

Cab de Yann, 06/09/2026, 3e demarrage de l Alpha 4.29 : ecran noir. pincabos-screen-hotplug
(evenements drm des tetes NVIDIA) tenait le verrou pendant qu il appelait le preflight, qui
attend ce meme verrou 15 s ; le preflight de pincabos-screen-topology-boot expirait ->
exit 1 -> « Dependency failed for pincabos-vpinfe.service ».
"""
import subprocess
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[3]
HOTPLUG = R / "usr/local/libexec/pincabos/pincabos-screen-hotplug"
PREFLIGHT = R / "usr/local/libexec/pincabos/pincabos-screen-topology-preflight.sh"


class VerrouBoot(unittest.TestCase):
    def test_hotplug_rend_le_verrou_avant_le_preflight(self):
        s = HOTPLUG.read_text(encoding="utf-8")
        self.assertLess(s.index("exec 9>&-"), s.index('"$PREFLIGHT" >/dev/null'))

    def test_hotplug_apres_la_topologie_de_boot(self):
        u = (R / "etc/systemd/system/pincabos-screen-hotplug.service").read_text(encoding="utf-8")
        self.assertIn("After=display-manager.service pincabos-screen-topology-boot.service", u)

    def test_preflight_ne_meurt_pas_sur_le_verrou(self):
        s = PREFLIGHT.read_text(encoding="utf-8")
        self.assertIn('/usr/bin/flock -w 60 "$LOCK" "$ENGINE" --prepare || log', s)
        self.assertNotIn('flock -w 15 "$LOCK"', s)

    def test_syntaxe(self):
        for f in (HOTPLUG, PREFLIGHT):
            self.assertEqual(subprocess.run(["bash", "-n", str(f)]).returncode, 0, f)


if __name__ == "__main__":
    unittest.main()
