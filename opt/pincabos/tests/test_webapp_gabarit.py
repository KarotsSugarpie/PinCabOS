"""Gabarit commun (lot 12 du découpage, PINCABOS_WEBAPP_MODULES_V1) : page() vit dans pincabos_webapp_gabarit.py.

app.py l'importe avant de créer l'application et la passe aux modules comme avant ; les modules historiques
la lisent toujours dans ses globals. Aucune route dans le gabarit.
"""
import ast
import re
import unittest
from pathlib import Path

from _charge import RACINE
from test_webapp_modules import noms_libres

WEB = Path(RACINE) / "opt/pincabos/web"
APP = WEB / "app.py"
MOD = WEB / "pincabos_webapp_gabarit.py"
NOMS = ("page", "pincabos_firstrun_is_complete", "pincabos_webapp_screen_state", "webapp_screen_toggle_html",
        "PCO_WEBAPP_SCREEN_STATE_FILE", "pincabos_support_footer_html")  # safe_file_text : retiré au lot 13 (sans appelant)


class Gabarit(unittest.TestCase):
    def setUp(self):
        self.app = APP.read_text(encoding="utf-8")
        self.mod = MOD.read_text(encoding="utf-8")

    def test_page_definie_une_fois_dans_le_gabarit(self):
        self.assertEqual(self.mod.count("\ndef page(title, body):"), 1)
        self.assertNotIn("def page(", self.app)
        for nom in NOMS:
            self.assertNotRegex(self.app, rf"(?m)^def {nom}\(|^{nom} = ")
            self.assertRegex(self.mod, rf"(?m)^def {nom}\(|^{nom} = ")

    def test_app_importe_le_gabarit_avant_l_application_et_le_reexporte(self):
        i = self.app.index("from pincabos_webapp_gabarit import (")
        bloc = self.app[i:self.app.index(")", i)]
        for nom in NOMS:
            self.assertIn(f"    {nom},\n", bloc, nom)
        self.assertLess(i, self.app.index("\napp = Flask("))
        # les modules reçoivent toujours page par register(app, page)
        self.assertGreaterEqual(self.app.count(".register(app, page)"), 10)
        self.assertIn("register_tools_routes(app, page)", self.app)

    def test_aucune_route_ni_application_dans_le_gabarit(self):
        for mot in ("@app.", "Blueprint(", "app.route", "def register("):
            self.assertNotIn(mot, self.mod, mot)

    def test_aucun_nom_libre_dans_le_gabarit(self):
        self.assertEqual(noms_libres(self.mod), set())

    def test_pied_de_page_support_voit_pincabos_version(self):
        # `pincabos_version() if "pincabos_version" in globals() else {}` : le nom doit exister dans le module
        self.assertIn("from pincabos_webapp_core import esc, get_ip, pincabos_version", self.mod)
        self.assertIn('if "pincabos_version" in globals()', self.mod)

    def test_page_lit_l_etat_du_wizard_par_import_direct(self):
        self.assertIn("from pincabos_webapp_firstrun import firstrun_load_cfg, firstrun_required_keys", self.mod)
        self.assertIn("firstrun_load_cfg().get('show_popup', True)", self.mod)
        self.assertIn("from pincabos_webapp_admin_pages import pincabos_footer_supporters_inline_html", self.mod)

    def test_module_sain(self):
        ast.parse(self.mod)


if __name__ == "__main__":
    unittest.main()
