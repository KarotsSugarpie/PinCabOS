"""pincabos_fronton : un cab a deux ecrans ne doit jamais inventer un FullDMD."""
import json
import os
import tempfile
import unittest

from _charge import charger

fr = charger("opt/pincabos/tools/pincabos_fronton.py", "pco_fronton")


def fichier(data):
    d = tempfile.mkdtemp()
    p = os.path.join(d, "x.json")
    with open(p, "w", encoding="utf-8") as f:
        f.write(data if isinstance(data, str) else json.dumps(data))
    return p


class FullDmd(unittest.TestCase):
    def test_deux_ecrans_role_resolution(self):
        p = fichier({"role_resolution": {"full_dmd_available": False}, "fulldmd": {"available": False, "width": None}})
        self.assertIs(fr.fulldmd_disponible(p), False)

    def test_trois_ecrans(self):
        p = fichier({"role_resolution": {"full_dmd_available": True}, "fulldmd": {"available": True, "width": 1920, "height": 1080}})
        self.assertIs(fr.fulldmd_disponible(p), True)

    def test_ancien_schema_sans_role_resolution(self):
        self.assertIs(fr.fulldmd_disponible(fichier({"fulldmd": {"width": 1920, "height": 1200}})), True)
        self.assertIs(fr.fulldmd_disponible(fichier({"fulldmd": {"width": None, "height": None}})), False)
        self.assertIs(fr.fulldmd_disponible(fichier({"backglass": {}})), False)

    def test_illisible_ne_repond_pas(self):
        self.assertIsNone(fr.fulldmd_disponible("/nulle/part.json"))
        self.assertIsNone(fr.fulldmd_disponible(fichier("{pas du json")))


class DmdMateriel(unittest.TestCase):
    def test_modes(self):
        for mode, attendu in (("off", False), ("usb", True), ("wifi", True), ("pin2dmd", True), ("PIN2DMD", True)):
            self.assertEqual(fr.dmd_materiel(fichier({"mode": mode})), attendu, mode)
        self.assertFalse(fr.dmd_materiel("/nulle/part.json"))


class Politique(unittest.TestCase):
    def test_sans_fulldmd_pas_de_scoreview(self):
        p = fr.politique_sans_fulldmd(False)
        self.assertEqual(p["ScoreView"]["ScoreViewOutput"], "0")
        self.assertEqual(p["Plugin.ScoreView"]["Enable"], "0")
        self.assertEqual(p["Plugin.B2SLegacy"]["B2SHideB2SDMD"], "1")
        self.assertEqual(p["Plugin.B2SLegacy"]["BackglassDMDOverlay"], "1", "sans DMD materiel : DMD dessine sur le backglass")

    def test_dmd_materiel_pas_d_overlay(self):
        self.assertEqual(fr.politique_sans_fulldmd(True)["Plugin.B2SLegacy"]["BackglassDMDOverlay"], "0")

    def test_fusion_la_politique_prime_et_ne_modifie_pas_l_original(self):
        base = {"ScoreView": {"ScoreViewOutput": "1", "ScoreViewWndX": "5760"}, "Plugin.B2SLegacy": {"B2SHideB2SDMD": "0"}}
        out = fr.fusionner(base, fr.politique_sans_fulldmd(False))
        self.assertEqual(out["ScoreView"], {"ScoreViewOutput": "0", "ScoreViewWndX": "5760"})
        self.assertEqual(out["Plugin.B2SLegacy"]["B2SHideB2SDMD"], "1")
        self.assertEqual(out["Plugin.ScoreView"], {"Enable": "0"})
        self.assertEqual(base["ScoreView"]["ScoreViewOutput"], "1")


class PlacementDmdParVpx(unittest.TestCase):
    """PINCABOS_DMD_PLACEMENT_PAR_VPX_V1 : VPX (plugin B2S, DMDOverlay AutoPos)
    trouve seul le cadre DMD dans l'art du directb2s. Aucun helper de lancement
    ne doit ecrire de coordonnees DMD (ScoreViewDMDX/Y/W/H) ni forcer AutoPos=0
    en Original ; seul le split PuP positionne (et restaure) le sien."""

    def test_aucun_helper_n_ecrit_de_coordonnees_dmd(self):
        import re
        from _charge import RACINE
        motif = re.compile(r"""["']ScoreViewDMD[XYWH]["']\s*:|["']ScoreViewDMDAutoPos["']\s*:\s*["']0["']""")
        fautifs = []
        for dossier in ("opt/pincabos/bin", "opt/pincabos/scripts", "opt/pincabos/tools"):
            for racine, _, fichiers in os.walk(os.path.join(RACINE, dossier)):
                for nom in fichiers:
                    if nom == "pincabos-pup-scoreview-split.py":
                        continue
                    chemin = os.path.join(racine, nom)
                    try:
                        with open(chemin, encoding="utf-8", errors="ignore") as f:
                            for num, ligne in enumerate(f, 1):
                                if motif.search(ligne):
                                    fautifs.append(f"{os.path.relpath(chemin, RACINE)}:{num}: {ligne.strip()}")
                    except OSError:
                        continue
        self.assertEqual(fautifs, [])


if __name__ == "__main__":
    unittest.main()
