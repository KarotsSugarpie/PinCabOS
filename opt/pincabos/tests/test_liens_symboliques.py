"""Liens symboliques du depot (PINCABOS_DEPOT_LIENS_V1).

Revue du 05/09/2026 : 1 261 liens suivis, 138 absolus vers une cible du depot
(casses dans tout clone, donc invisibles aux tests et au lint) et 7 liens morts
vers un dossier d'installation date. Les liens PinCabOS sont relatifs et
resolvent dans le depot ; l'ISO (copie du depot dans le rootfs) et l'OTA
(l'archive transporte les liens tels quels) les voient identiques.
"""
import os
import subprocess
import unittest

from _charge import RACINE

PERIMETRE = ("opt/pincabos/", "usr/local/", "etc/systemd/system/", "home/pinball/")
# liens de l OS dans le perimetre, cible hors depot par construction
HORS_DEPOT = {"usr/local/man"}


def _liens():
    out = subprocess.run(["git", "-C", RACINE, "ls-files", "-s", "-z"], capture_output=True).stdout.decode("utf-8", "surrogateescape")
    return [l.split("\t", 1)[1] for l in out.split("\0") if l.startswith("120000")]


class LiensDuDepot(unittest.TestCase):
    def setUp(self):
        self.liens = [p for p in _liens() if p.startswith(PERIMETRE) and p not in HORS_DEPOT]
        self.assertGreater(len(self.liens), 100, "git ls-files doit voir les liens")

    def test_aucun_lien_absolu_vers_le_depot(self):
        fautifs = []
        for p in self.liens:
            t = os.readlink(os.path.join(RACINE, p))
            if t.startswith("/") and os.path.exists(os.path.join(RACINE, t.lstrip("/"))):
                fautifs.append(f"{p} -> {t}")
        self.assertEqual(fautifs, [], "un lien vers un fichier du depot doit etre relatif")

    def test_aucun_lien_mort(self):
        fautifs = []
        for p in self.liens:
            t = os.readlink(os.path.join(RACINE, p))
            if t.startswith("/") or t == "/dev/null":
                continue   # cible systeme (ou unite masquee) : hors depot par construction
            if not os.path.exists(os.path.join(RACINE, os.path.dirname(p), t)):
                fautifs.append(f"{p} -> {t}")
        self.assertEqual(fautifs, [])

    def test_liens_systeme_absolus_recenses(self):
        """Les liens PinCabOS vers l'exterieur du depot sont peu nombreux et connus."""
        hors = sorted(f"{p} -> {os.readlink(os.path.join(RACINE, p))}" for p in self.liens
                      if os.readlink(os.path.join(RACINE, p)).startswith("/")
                      and not os.path.exists(os.path.join(RACINE, os.readlink(os.path.join(RACINE, p)).lstrip("/"))))
        self.assertLessEqual(len(hors), 160, hors[:10])


if __name__ == "__main__":
    unittest.main()
