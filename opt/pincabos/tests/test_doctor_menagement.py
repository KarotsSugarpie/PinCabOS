"""PINCABOS_DOCTOR_MENAGEMENT_V1 : le doctor ne coupe jamais une partie ni un frontend sain.

Cab de Yann, 06/09/2026, installation neuve 4.29 : le finaliseur de premier demarrage
(45 s apres le boot, mode reparation) redemarrait la topologie, Requires de VPinFE ->
VPinFE et la table de calibration Nudge tues (ecran noir).
"""
import subprocess
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[3]
LIB = R / "usr/local/libexec/pincabos/doctor-lib.sh"
D = R / "usr/local/libexec/pincabos/doctor.d"


class Menagement(unittest.TestCase):
    def test_bibliotheque(self):
        s = LIB.read_text(encoding="utf-8")
        self.assertIn("pco_partie_en_cours()", s)
        self.assertIn("pco_peut_redemarrer()", s)
        self.assertIn('[ "$PCO_FIRSTBOOT" -ne 1 ]', s)
        self.assertIn('if systemctl is-active --quiet "$unit"; then\n    if pco_peut_redemarrer; then\n      systemctl restart "$unit"', s)

    def test_topologie_active_non_touchee(self):
        s = (D / "40-displays.sh").read_text(encoding="utf-8")
        self.assertIn('pco_repairing && ! pco_service_active "$TOPOLOGY_SERVICE" && ! pco_partie_en_cours', s)
        self.assertNotIn("  if pco_repairing; then\n    systemctl restart", s)

    def test_premier_demarrage_sans_restart(self):
        s = (R / "etc/systemd/system/pincabos-finalize-firstboot.service").read_text(encoding="utf-8")
        self.assertIn("--repair --firstboot --no-restart", s)

    def test_syntaxe(self):
        for f in [LIB, *sorted(D.glob("*.sh")), R / "usr/local/sbin/pincabos"]:
            self.assertEqual(subprocess.run(["bash", "-n", str(f)]).returncode, 0, f)


if __name__ == "__main__":
    unittest.main()
