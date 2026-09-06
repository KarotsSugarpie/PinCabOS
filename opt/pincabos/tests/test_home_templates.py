"""Modèles du compte du joueur (PINCABOS_MODELES_JOUEUR_V1).

Revue du 05/09/2026, étape 3 point 2 : ce que PinCabOS attend dans /home/pinball
et qui n'est pas une donnée du joueur vit sous opt/pincabos/templates/home ;
l'installateur les pose dans la cible, le premier démarrage complète, jamais
d'écrasement sans --force.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _charge import RACINE, texte_installateur

R = Path(RACINE)
sys.path.insert(0, str(R / "opt/pincabos/tools"))
import pincabos_home_templates as ht  # noqa: E402

TEMPLATES = R / "opt/pincabos/templates/home"


class Arborescence(unittest.TestCase):
    def test_les_modeles_attendus_sont_la(self):
        for rel in (".config/vpinfe/vpinfe.ini", ".config/vpinfe/collections.ini", ".config/vpinfe/themes/Revolution/theme.json",
                    ".config/pincabos/dashboard-layout.json", ".config/systemd/user/pipewire-session-manager.service",
                    ".local/share/VPinballX/10.8/VPinballX.ini", ".local/share/VPinballX/10.8/directoutputconfig/directoutputconfig30.ini",
                    ".vpinball/gamecontrollerdb.txt", ".config/sunshine/sunshine.conf"):
            self.assertTrue(os.path.lexists(TEMPLATES / rel), rel)

    def test_ce_qui_reste_livre_a_chaud_par_l_ota_reste_dans_le_compte(self):
        # chemins exacts / prefixe de pincabos_updates.allowed : ils ne sont pas des modeles
        self.assertTrue((R / "home/pinball/.config/openbox/autostart").is_file())
        self.assertTrue((R / "home/pinball/.config/vpinfe/themes/PinCabOS/theme.json").is_file())
        self.assertFalse((TEMPLATES / ".config/openbox/autostart").exists())
        self.assertFalse((TEMPLATES / ".config/vpinfe/themes/PinCabOS").exists())
        # et plus aucun doublon : un fichier est soit modele, soit livre a chaud
        for p in TEMPLATES.rglob("*"):
            if p.is_file():
                self.assertFalse((R / "home/pinball" / p.relative_to(TEMPLATES)).exists(), p)

    def test_plus_de_sauvegarde_datee(self):
        self.assertEqual([p.name for p in (R / "home/pinball/.config/vpinfe").glob("vpinfe.ini.*")], [])


class Pose(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.t = self.tmp / "opt/pincabos/templates/home"
        (self.t / ".config/vpinfe").mkdir(parents=True)
        (self.t / ".config/vpinfe/vpinfe.ini").write_text("[Displays]\n", encoding="utf-8")
        (self.t / ".vpinball").mkdir()
        (self.t / ".vpinball/gamecontrollerdb.txt").write_text("db\n", encoding="utf-8")
        self.h = self.tmp / "home/pinball"
        self.h.mkdir(parents=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_pose_ce_qui_manque_et_garde_le_reste(self):
        (self.h / ".config/vpinfe").mkdir(parents=True)
        (self.h / ".config/vpinfe/vpinfe.ini").write_text("[Displays]\ntablescreenid = 2\n", encoding="utf-8")
        j = ht.poser(self.t, self.h)
        self.assertEqual((self.h / ".config/vpinfe/vpinfe.ini").read_text(encoding="utf-8"), "[Displays]\ntablescreenid = 2\n", "fichier du joueur garde")
        self.assertEqual((self.h / ".vpinball/gamecontrollerdb.txt").read_text(encoding="utf-8"), "db\n")
        self.assertTrue(any("1 pose(s), 1 deja present(s)" in l for l in j), j)

    def test_force_ecrase(self):
        (self.h / ".vpinball").mkdir()
        (self.h / ".vpinball/gamecontrollerdb.txt").write_text("vieux\n", encoding="utf-8")
        ht.poser(self.t, self.h, force=True)
        self.assertEqual((self.h / ".vpinball/gamecontrollerdb.txt").read_text(encoding="utf-8"), "db\n")

    def test_dry_run_n_ecrit_rien(self):
        j = ht.poser(self.t, self.h, dry_run=True)
        self.assertFalse((self.h / ".vpinball").exists())
        self.assertTrue(any("poserait" in l for l in j), j)

    def test_modeles_absents(self):
        self.assertTrue(ht.poser(self.tmp / "nulle-part", self.h)[0].startswith("WARN"))

    def test_cli_sur_une_cible(self):
        r = subprocess.run([sys.executable, str(R / "opt/pincabos/tools/pincabos_home_templates.py"), "apply", "--root", str(self.tmp)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("2 pose(s)", r.stdout)
        self.assertTrue((self.h / ".config/vpinfe/vpinfe.ini").is_file())


class Integration(unittest.TestCase):
    def test_iso_pose_les_modeles_dans_la_cible(self):
        s = texte_installateur()
        self.assertIn("apply_target_home_templates() {", s)
        self.assertIn('local outil="$TARGET/opt/pincabos/tools/pincabos_home_templates.py"', s)
        self.assertIn('python3 "$outil" apply --root "$TARGET"', s)
        self.assertIn("  ensure_target_vpx_link\n  apply_target_home_templates\n  apply_target_identity\n", s)

    def test_premier_demarrage_complete(self):
        s = (R / "usr/local/sbin/pincabos-installer-firstboot").read_text(encoding="utf-8")
        self.assertIn("pincabos_home_templates.py", s)
        self.assertEqual(subprocess.run(["bash", "-n", str(R / "usr/local/sbin/pincabos-installer-firstboot")]).returncode, 0)

    def test_prefixe_en_attente_dans_l_updater(self):
        sys.path.insert(0, str(R / "opt/pincabos/update"))
        import pincabos_updates as up
        # deuxieme temps de la regle des deux releases : le parc connait le prefixe depuis 4.04, les fichiers partent
        self.assertNotIn("opt/pincabos/templates/", up.PENDING_PREFIXES)
        self.assertTrue(up.allowed("opt/pincabos/templates/home/.config/vpinfe/vpinfe.ini"))
        self.assertTrue(up.allowed_for_build("opt/pincabos/templates/home/.config/vpinfe/vpinfe.ini"))
        self.assertFalse(up.allowed("opt/pincabos/templates/home/.config/vpinfe/__pycache__/x.pyc"))


if __name__ == "__main__":
    unittest.main()
