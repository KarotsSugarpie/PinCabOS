"""L'unique écrivain INI (PINCABOS_INI_UNIQUE_V1).

Revue du 05/09/2026 : six copies de la même logique posaient des clés dans
VPinballX.ini et vpinfe.ini, chacune à sa façon. Ce module est le seul ; les
autres lui délèguent.
"""
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from _charge import RACINE

R = Path(RACINE)
sys.path.insert(0, str(R / "opt/pincabos/tools"))
import pincabos_ini as pi  # noqa: E402

VPX = """; commentaire d'en-tête
[Version]
VPinball = 10.8.1

[Player]
Sound3D = 0
PlayfieldFullScreen = 1

[Displays]
tablescreenid = 0
bgscreenid = 1
"""


class Moteur(unittest.TestCase):
    def test_remplace_sans_rien_perdre(self):
        ini = pi.Ini(VPX)
        self.assertTrue(ini.poser("Player", "sound3d", "5"))
        t = ini.texte()
        self.assertIn("; commentaire d'en-tête\n[Version]\nVPinball = 10.8.1\n\n[Player]\nSound3D = 5\nPlayfieldFullScreen = 1\n\n[Displays]", t, "casse de la clé et du reste conservés")
        self.assertEqual(ini.get("player", "SOUND3D"), "5")
        self.assertFalse(ini.poser("Player", "Sound3D", "5"), "rien à changer")

    def test_cle_nouvelle_en_fin_de_section_avant_les_lignes_vides(self):
        ini = pi.Ini(VPX)
        ini.poser("Player", "SoundDevice", "Carte")
        self.assertIn("PlayfieldFullScreen = 1\nSoundDevice = Carte\n\n[Displays]", ini.texte())

    def test_section_nouvelle_en_fin_de_fichier(self):
        ini = pi.Ini(VPX)
        ini.poser("Plugin.DOF", "Enable", "1")
        self.assertTrue(ini.texte().endswith("bgscreenid = 1\n\n[Plugin.DOF]\nEnable = 1\n"))
        self.assertEqual(ini.sections()[-1], "Plugin.DOF")

    def test_commentaire_pose_une_seule_fois(self):
        ini = pi.Ini(VPX)
        com = "; Modifié 2026-09-06 par PinCabOS fonction(Audio)"
        ini.poser("Player", "Sound3D", "3", commentaire=com)
        ini.poser("Player", "Sound3D", "4", commentaire=com.replace("09-06", "09-07"))
        t = ini.texte()
        self.assertEqual(t.count("par PinCabOS fonction("), 1)
        self.assertIn("[Player]\n; Modifié 2026-09-07 par PinCabOS fonction(Audio)\nSound3D = 4\n", t)
        ini.poser("Nouvelle", "k", "v", commentaire=com)
        self.assertIn("\n; Modifié 2026-09-06 par PinCabOS fonction(Audio)\n[Nouvelle]\nk = v\n", ini.texte(), "section nouvelle : commentaire avant l'en-tête")

    def test_poser_partout_et_supprimer(self):
        ini = pi.Ini("[A]\nx = 1\n[B]\nx = 2\ny = 0\n")
        self.assertTrue(ini.poser_partout("x", "9"))
        self.assertEqual(ini.texte(), "[A]\nx = 9\n[B]\nx = 9\ny = 0\n")
        ini.poser_partout("z", "1")
        self.assertTrue(ini.texte().endswith("y = 0\nz = 1\n"))
        self.assertTrue(ini.supprimer("B", "Y"))
        self.assertIsNone(ini.get("B", "y"))
        self.assertFalse(ini.supprimer("C", "y"))

    def test_fichier_vide_et_sans_fin_de_ligne(self):
        self.assertEqual(pi.Ini("").texte(), "")
        ini = pi.Ini("[A]\nx = 1")
        ini.poser("A", "y", "2")
        self.assertEqual(ini.texte(), "[A]\nx = 1\ny = 2")
        ini = pi.Ini("")
        ini.poser("A", "x", "1")
        self.assertEqual(ini.texte(), "[A]\nx = 1\n")

    def test_purge_du_commentaire_pincabos(self):
        ini = pi.Ini("[Player]\n; Modifié hier par PinCabOS fonction(Audio)\nSound3D = 0\n")
        self.assertTrue(ini.poser("Player", "Sound3D", "0", purger_commentaire=True))
        self.assertEqual(ini.texte(), "[Player]\nSound3D = 0\n")
        self.assertEqual(pi.Ini(VPX).bornes("Displays"), (8, 11))
        self.assertEqual(pi.Ini(VPX).bornes("Absente"), (None, None))

    def test_commentaires_ne_sont_pas_des_cles(self):
        ini = pi.Ini("[A]\n; x = vieux\nx = 1\n")
        ini.poser("A", "x", "2")
        self.assertEqual(ini.texte(), "[A]\n; x = vieux\nx = 2\n")
        self.assertEqual(ini.cles("A"), {"x": "2"})


class Fichiers(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.f = self.tmp / "VPinballX.ini"
        self.f.write_text(VPX, encoding="utf-8")
        os.chmod(self.f, 0o664)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_ecriture_atomique_et_mode_conserve(self):
        j = pi.appliquer(self.f, {"Player": {"Sound3D": "5", "SoundDevice": "Carte"}}, partout={"tablescreenid": "2"})
        self.assertTrue(any("[Player] Sound3D = 5" in l for l in j), j)
        self.assertTrue(any("écrit" in l for l in j), j)
        t = self.f.read_text(encoding="utf-8")
        self.assertIn("Sound3D = 5\nPlayfieldFullScreen = 1\nSoundDevice = Carte\n", t)
        self.assertIn("tablescreenid = 2", t)
        self.assertEqual(os.stat(self.f).st_mode & 0o777, 0o664)
        self.assertEqual([p.name for p in self.tmp.iterdir()], ["VPinballX.ini"], "pas de fichier temporaire abandonné")

    def test_rien_a_changer_rien_d_ecrit(self):
        avant = os.stat(self.f).st_mtime_ns
        j = pi.appliquer(self.f, {"Player": {"Sound3D": "0"}})
        self.assertTrue(any("déjà à jour" in l for l in j), j)
        self.assertEqual(os.stat(self.f).st_mtime_ns, avant)

    def test_fichier_absent_cree(self):
        g = self.tmp / "sous/dossier/vpinfe.ini"
        pi.appliquer(g, {"Displays": {"tablescreenid": "0"}})
        self.assertEqual(g.read_text(encoding="utf-8"), "[Displays]\ntablescreenid = 0\n")

    def test_cli(self):
        import subprocess
        r = subprocess.run([sys.executable, str(R / "opt/pincabos/tools/pincabos_ini.py"), str(self.f), "--set", "Player", "Sound3D", "3"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = subprocess.run([sys.executable, str(R / "opt/pincabos/tools/pincabos_ini.py"), str(self.f), "--get", "Player", "Sound3D"], capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), "3")


class EcrivainUnique(unittest.TestCase):
    """Les anciens éditeurs délèguent tous au module : aucune fonction d'écriture ne réimplémente la boucle."""

    DELEGUES = {
        "opt/pincabos/scripts/pincabos-screen-topology.py": ("update_section", "update_global", "atomic_write"),
        "opt/pincabos/web/app.py": ("pincabos_write_ini_lines", "pincabos_find_ini_section",
                                    "pincabos_set_ini_key_with_comment", "pincabos_set_ini_section_with_comment"),
        "opt/pincabos/web/pincabos_webapp_vpxball.py": ("vpx_ballcab_find_section", "vpx_simple_ball_find_section"),
        "opt/pincabos/web/pincabos_webapp_gpu.py": ("set_ini_key", "pincabos_gpu_ini_set_key_local"),
        "opt/pincabos/web/pincabos_webapp_dmd.py": ("pincabos_set_ini_key_plain",),
        "opt/pincabos/web/pincabos_webapp_audio.py": ("set_ini_key_native", "audio_find_section"),
        "opt/pincabos/tools/pincabos_audio.py": ("poser_cle",),
        "opt/pincabos/tools/pincabos_dof.py": ("poser_cle_ini",),
    }
    BOUCLE = re.compile(r'\.startswith\("\["\) and \w+\.endswith\("\]"\)')

    @staticmethod
    def _corps(src, nom):
        """Le corps de `nom` : de son def au premier dedent (fonction imbriquée comprise)."""
        lignes = src.split("\n")
        for i, l in enumerate(lignes):
            m = re.match(rf"^([ \t]*)def {re.escape(nom)}\(", l)
            if not m:
                continue
            indent = len(m.group(1))
            j = i + 1
            while j < len(lignes) and (not lignes[j].strip() or len(lignes[j]) - len(lignes[j].lstrip()) > indent):
                j += 1
            return "\n".join(lignes[i:j])
        return ""

    def test_delegation(self):
        for rel, fonctions in self.DELEGUES.items():
            src = (R / rel).read_text(encoding="utf-8")
            self.assertIn("import pincabos_ini", src, rel)
            for f in fonctions:
                corps = self._corps(src, f)
                self.assertTrue(corps, (rel, f))
                self.assertIn("pincabos_ini.", corps, f"{rel}:{f} ne délègue pas à l'écrivain unique")
                self.assertIsNone(self.BOUCLE.search(corps), f"{rel}:{f} réimplémente la boucle d'édition d'INI")
        # la page Ecran n ecrit plus d INI du tout : elle appelle la topologie (TOPOLOGIE_SOURCE_UNIQUE_V1)
        ecran = (R / "opt/pincabos/web/screen.py").read_text(encoding="utf-8")
        self.assertNotIn("import configparser", ecran)
        self.assertNotIn("pincabos_ini", ecran)
        self.assertIn("--adopt-current-roles", ecran)


if __name__ == "__main__":
    unittest.main()
