"""Pages d'administration (lot 10 du découpage, PINCABOS_WEBAPP_MODULES_V1) : page admin composée, sans enrobage.

Avant : deux blocs try réaffectaient `pincabos_admin_page` l'un après l'autre (carte supporters, puis carte
Version), et un troisième cherchait la route « À propos » avant qu'elle existe. Après :
`pincabos_webapp_admin_pages.py` compose la page en séquence ; app.py réexporte ce que dev_admin lit.
"""
import ast
import re
import unittest
from pathlib import Path

from _charge import RACINE

WEB = Path(RACINE) / "opt/pincabos/web"
APP = WEB / "app.py"
MOD = WEB / "pincabos_webapp_admin_pages.py"
CORE = WEB / "pincabos_webapp_core.py"
REEXPORTS = ("pincabos_admin_page", "pincabos_footer_supporters_inline_html", "ADMIN_LOGIN_USER", "ADMIN_LOGIN_PASS",
             "PINCABOS_DEFAULT_ADMIN_USER", "PINCABOS_DEFAULT_ADMIN_PASS", "PINCABOS_DEFAULT_DEV_USER",
             "PINCABOS_DEFAULT_DEV_PASS", "PINCABOS_ADMIN_CREDENTIALS_ARE_DEFAULT", "PINCABOS_ADMIN_UNREADABLE_SECRETS")


class PageAdminComposee(unittest.TestCase):
    def setUp(self):
        self.app = APP.read_text(encoding="utf-8")
        self.mod = MOD.read_text(encoding="utf-8")

    def test_composition_en_sequence_supporters_puis_version(self):
        i = self.mod.index("def pincabos_admin_page(*args, **kwargs):")
        corps = self.mod[i:i + 400]
        self.assertIn("pincabos_webapp_dev_admin.pco_admin_page_base(*args, **kwargs)", corps)
        i_sup = corps.index("_admin_page_avec_carte_supporters(html)")
        i_ver = corps.index("_admin_page_avec_carte_version(html)")
        self.assertLess(i_sup, i_ver, "les anciens enrobages posaient la carte supporters d'abord, la carte Version ensuite")
        self.assertIn("def _admin_page_avec_carte_supporters(html):", self.mod)
        self.assertIn("def _admin_page_avec_carte_version(html):", self.mod)
        # les marqueurs anti-doublon des anciens enrobages sont conservés
        self.assertIn('if "PINCABOS_ADMIN_ABOUT_SUPPORTERS_CARD" in str(html):', self.mod)
        self.assertIn('if "PINCABOS_ADMIN_VERSION_JSON_CARD" in str(html):', self.mod)

    def test_plus_aucun_enrobage_ni_recherche_de_route(self):
        for mot in ("_pincabos_admin_page_original", "_pincabos_about_original_endpoint", "pincabos_about_supporters_insert_public",
                    "pincabos_about_supporters_public_card", "def pincabos_admin_page", "def _pco_read_auth_value"):
            self.assertNotIn(mot, self.app, mot)
        for mot in ("view_functions", "url_map", "_pincabos_admin_page_original", "insert_public", "public_card"):
            self.assertNotIn(mot, self.mod, mot)
        self.assertEqual(self.mod.count("def pincabos_admin_page("), 1)

    def test_routes_admin_dans_le_module(self):
        for r in ("/admin/about-supporters/save", "/admin/version/save"):
            self.assertEqual(self.mod.count(f'@admin_pages_bp.route("{r}", methods=["POST"])'), 1, r)
            self.assertNotIn(f'route("{r}"', self.app, r)
        self.assertIn("guard = pincabos_admin_require_login()", self.mod)
        self.assertIn("from pincabos_webapp_dev_admin import pincabos_admin_require_login", self.mod)

    def test_identifiants_definis_dans_le_module_et_reexportes(self):
        for nom in ("ADMIN_LOGIN_USER = _pco_read_auth_value(", "ADMIN_LOGIN_PASS = _pco_read_auth_value(",
                    'PINCABOS_DEFAULT_ADMIN_USER = "admin"', "PINCABOS_ADMIN_CREDENTIALS_ARE_DEFAULT = not (ADMIN_LOGIN_USER and ADMIN_LOGIN_PASS)",
                    "PINCABOS_ADMIN_UNREADABLE_SECRETS = ["):
            self.assertIn(nom, self.mod, nom)
        i = self.app.index("from pincabos_webapp_admin_pages import (")
        bloc = self.app[i:self.app.index(")", i)]
        for nom in REEXPORTS:
            self.assertIn(f"    {nom},\n", bloc, nom)
        # dev_admin lit bien ces noms dans les globals qu'app.py lui passe
        dev = (WEB / "pincabos_webapp_dev_admin.py").read_text(encoding="utf-8")
        for nom in ("ADMIN_LOGIN_USER", "ADMIN_LOGIN_PASS", "PINCABOS_ADMIN_CREDENTIALS_ARE_DEFAULT", "pincabos_admin_page"):
            self.assertRegex(dev, rf"\b{nom}\b")

    def test_version_json_dans_le_noyau(self):
        core = CORE.read_text(encoding="utf-8")
        self.assertIn("\ndef pincabos_version(", core)
        self.assertNotIn("\ndef pincabos_version(", self.app)
        self.assertRegex(self.app, r"(?m)^    pincabos_version,$")
        self.assertIn("from pincabos_webapp_core import esc, pincabos_version", self.mod)

    def test_pied_de_page_supporters_toujours_appele_par_page(self):
        self.assertIn("supporters_html = pincabos_footer_supporters_inline_html()", self.app)
        self.assertIn("def pincabos_footer_supporters_inline_html():", self.mod)

    def test_module_sain(self):
        ast.parse(self.mod)
        self.assertIn("def register(app, page_fn):", self.mod)
        i_reg = self.app.index("pco_admin_pages_routes.register(app, page)")
        self.assertLess(self.app.index("pco_console_routes.register(app, page)"), i_reg)
        self.assertLess(i_reg, self.app.index("pco_vpxball_routes.register(app, page)"))
        # l'enregistrement des modules historiques (globals) vient après : dev_admin reçoit les réexports
        self.assertLess(i_reg, self.app.index("_pco_module.register(app, globals())"))


if __name__ == "__main__":
    unittest.main()
