"""Moteur backboard (logos aerao au menu) : matching par nom, injection
idempotente dans la config DOF, remplissage non destructif des .info."""
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout

from _charge import charger

eng = charger("opt/pincabos/tools/backboard-menu/backboard-engine.py", "pco_backboard")

INI = """[Config DOF]
afm,S1 Red/S2 Green
pinupmenu,E900 Blue
autre,S3 Yellow
"""
CODE = "E2007 WHITE ABL0 ABT0 ABW232 ABH32 AAC6 ABF34 AAF1/E2039 WHITE ABL0 ABT0 ABW232 ABH32 AAC6 ABF428 AAF1"


class Matching(unittest.TestCase):
    def test_normalisation(self):
        self.assertEqual(eng.norm("Attack from Mars (Bally 1995)"), "attackfrommars")
        self.assertEqual(eng.norm("Pirates of the Caribbean (Stern 2006)"), "piratescaribbean")

    def test_lookup_exact_puis_prefixe(self):
        base = {"attackfrommars": "E2007", "piratescaribbean": "E2039"}
        self.assertEqual(eng.lookup(base, "Attack from Mars (Bally 1995)"), "E2007")
        self.assertEqual(eng.lookup(base, "Pirates of the Caribbean"), "E2039")
        self.assertIsNone(eng.lookup(base, "JP's Transformers (Original 2018)"))

    def test_preference_vpx(self):
        self.assertEqual(eng.best_event(["E4100", "E2100", "E6100"]), "E2100")


class Injection(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ini = os.path.join(self.tmp.name, "directoutputconfig30.ini")
        self.code = os.path.join(self.tmp.name, "code.txt")
        open(self.ini, "w").write(INI)
        open(self.code, "w").write(CODE)

    def tearDown(self):
        self.tmp.cleanup()

    def lire(self):
        return open(self.ini).read()

    def test_injecte_sur_la_ligne_pinupmenu_seulement(self):
        with redirect_stdout(io.StringIO()):
            eng.cmd_inject(self.ini, self.code)
        txt = self.lire()
        self.assertIn("pinupmenu,E900 Blue" + eng.INJECT_MARK + "/E2007 WHITE", txt)
        self.assertIn("afm,S1 Red/S2 Green\n", txt)
        self.assertIn("autre,S3 Yellow", txt)

    def test_idempotent_quel_que_soit_le_premier_effet_aerao(self):
        # le code de test commence par E2007, pas E2000 : l'ancien marqueur
        # ne l'aurait pas reconnu et aurait reinjecte a chaque appel
        with redirect_stdout(io.StringIO()):
            eng.cmd_inject(self.ini, self.code)
            eng.cmd_inject(self.ini, self.code)
        self.assertEqual(self.lire().count(eng.INJECT_MARK), 1)
        self.assertEqual(self.lire().count("E2039 WHITE"), 1)

    def test_ancien_marqueur_migre_sans_doublon(self):
        ancien = "E2000 WHITE ABL0 ABT0 ABW232 ABH32 AAC6 ABF1 AAF1/E2039 WHITE ABL0 ABT0 ABW232 ABH32 AAC6 ABF428 AAF1"
        open(self.ini, "w").write(INI.replace("pinupmenu,E900 Blue", "pinupmenu,E900 Blue/" + ancien))
        with redirect_stdout(io.StringIO()):
            eng.cmd_inject(self.ini, self.code)
        txt = self.lire()
        self.assertEqual(txt.count("E2039 WHITE"), 1)
        self.assertNotIn("ABF1 AAF1", txt)
        self.assertEqual(txt.count(eng.INJECT_MARK), 1)

    def test_uninject_restaure(self):
        with redirect_stdout(io.StringIO()):
            eng.cmd_inject(self.ini, self.code)
            eng.cmd_uninject(self.ini)
        self.assertEqual(self.lire(), INI)


class RemplissageDesInfo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tables = os.path.join(self.tmp.name, "Tables")
        self.map = os.path.join(self.tmp.name, "map.json")
        import json
        json.dump({"attackfrommars": "E2007", "piratescaribbean": "E2039"}, open(self.map, "w"))
        for nom, event in (("Attack from Mars (Bally 1995)", ""), ("Pirates of the Caribbean (Stern 2006)", "E2777")):
            d = os.path.join(self.tables, nom)
            os.makedirs(d)
            open(os.path.join(d, nom + ".info"), "w").write('{\n  "FrontendDOFEvent": "%s"\n}\n' % event)

    def tearDown(self):
        self.tmp.cleanup()

    def event(self, nom):
        import re
        txt = open(os.path.join(self.tables, nom, nom + ".info")).read()
        return re.search(r'"FrontendDOFEvent"\s*:\s*"([^"]*)"', txt).group(1)

    def test_fill_only_remplit_le_vide_et_respecte_la_personnalisation(self):
        with redirect_stdout(io.StringIO()):
            eng.cmd_map(self.map, self.tables, False, True)
        self.assertEqual(self.event("Attack from Mars (Bally 1995)"), "E2007")
        self.assertEqual(self.event("Pirates of the Caribbean (Stern 2006)"), "E2777")

    def test_overwrite_impose_la_base(self):
        with redirect_stdout(io.StringIO()):
            eng.cmd_map(self.map, self.tables, False, False)
        self.assertEqual(self.event("Pirates of the Caribbean (Stern 2006)"), "E2039")

    def test_dry_ne_touche_rien(self):
        with redirect_stdout(io.StringIO()):
            eng.cmd_map(self.map, self.tables, True, False)
        self.assertEqual(self.event("Attack from Mars (Bally 1995)"), "")


class Detection(unittest.TestCase):
    def test_backboard_present_ou_non(self):
        with tempfile.TemporaryDirectory() as d, redirect_stdout(io.StringIO()):
            self.assertEqual(eng.cmd_detect(d), 1)
            open(os.path.join(d, "cabinet.xml"), "w").write("<Cabinet><TeensyStripController/></Cabinet>")
            self.assertEqual(eng.cmd_detect(d), 1)
            open(os.path.join(d, "cabinet.xml"), "w").write("<Cabinet><TeensyStripController></TeensyStripController><LedStrip></LedStrip></Cabinet>")
            self.assertEqual(eng.cmd_detect(d), 0)


if __name__ == "__main__":
    unittest.main()
