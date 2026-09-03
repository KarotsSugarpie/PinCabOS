"""PINCABOS_UPDATER_SELF_UPDATE_V1 : l'updater de la release s'installe d'abord."""
import os
import shutil
import subprocess
import tempfile
import unittest

from _charge import charger

up = charger("opt/pincabos/update/pincabos_updates.py", "pco_updater_self")


def fichier(d, nom, contenu, mode=0o755):
    p = os.path.join(d, nom)
    with open(p, "w", encoding="utf-8") as f:
        f.write(contenu)
    os.chmod(p, mode)
    return p


class Installation(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.courant = fichier(self.d, "courant.py", "VERSION = 1\n")
        self.backup = os.path.join(self.d, "sauvegarde", "avant.py")

    def test_identique_ne_differe_pas(self):
        meme = fichier(self.d, "meme.py", "VERSION = 1\n")
        self.assertFalse(up.updater_differs(meme, self.courant))
        autre = fichier(self.d, "autre.py", "VERSION = 2\n")
        self.assertTrue(up.updater_differs(autre, self.courant))

    def test_remplacement_atomique_avec_sauvegarde_et_mode(self):
        nouveau = fichier(self.d, "nouveau.py", "VERSION = 2\n", mode=0o644)
        up.install_updater(nouveau, self.courant, self.backup)
        self.assertEqual(open(self.courant).read(), "VERSION = 2\n")
        self.assertEqual(open(self.backup).read(), "VERSION = 1\n")
        self.assertEqual(os.stat(self.courant).st_mode & 0o777, 0o755, "le mode de l'updater en place est conserve")
        self.assertFalse(os.path.exists(self.courant + ".new"))

    def test_fichier_invalide_n_est_pas_installe(self):
        casse = fichier(self.d, "casse.py", "def (\n")
        with self.assertRaises(SyntaxError):
            up.install_updater(casse, self.courant, self.backup)
        self.assertEqual(open(self.courant).read(), "VERSION = 1\n")
        self.assertFalse(os.path.exists(self.backup))

    def test_chemin_de_l_updater_dans_le_perimetre(self):
        self.assertTrue(up.allowed(up.UPDATER_REL))
        self.assertTrue(up.allowed_for_build(up.UPDATER_REL))


@unittest.skipUnless(shutil.which("zstd") and shutil.which("tar"), "tar --zstd indisponible")
class Extraction(unittest.TestCase):
    def test_extrait_seulement_l_updater_de_l_archive(self):
        d = tempfile.mkdtemp()
        racine = os.path.join(d, "racine"); os.makedirs(os.path.join(racine, "opt/pincabos/update"))
        os.makedirs(os.path.join(racine, "opt/pincabos/bin"))
        fichier(racine, "opt/pincabos/update/pincabos_updates.py", "VERSION = 9\n")
        fichier(racine, "opt/pincabos/bin/autre", "x\n")
        archive = os.path.join(d, "u.tar.zst")
        subprocess.run(["tar", "--zstd", "-cf", archive, "-C", racine, "opt"], check=True)
        work = os.path.join(d, "work"); os.makedirs(work)
        c = up.updater_candidate(archive, work)
        self.assertIsNotNone(c)
        self.assertEqual(open(c).read(), "VERSION = 9\n")
        self.assertFalse(os.path.exists(os.path.join(work, "opt/pincabos/bin/autre")), "seul l'updater est extrait")

    def test_archive_sans_updater(self):
        d = tempfile.mkdtemp()
        racine = os.path.join(d, "racine"); os.makedirs(os.path.join(racine, "opt/pincabos/bin"))
        fichier(racine, "opt/pincabos/bin/autre", "x\n")
        archive = os.path.join(d, "u.tar.zst")
        subprocess.run(["tar", "--zstd", "-cf", archive, "-C", racine, "opt"], check=True)
        work = os.path.join(d, "work"); os.makedirs(work)
        self.assertIsNone(up.updater_candidate(archive, work))


if __name__ == "__main__":
    unittest.main()
