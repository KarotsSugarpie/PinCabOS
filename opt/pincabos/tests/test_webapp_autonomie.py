"""Autonomie des modules historiques (PINCABOS_WEBAPP_AUTONOMIE_V1).

Avant : six modules recevaient `globals()` d'app.py à l'enregistrement, y lisaient leurs dépendances et y
republiaient leurs noms ; trois autres lisaient un dictionnaire de globals. Après : chaque module importe ce
dont il a besoin, app.py ne passe plus ses globals à personne et ne réexporte plus rien pour eux.
"""
import ast
import re
import unittest
from pathlib import Path

from _charge import RACINE
from test_webapp_modules import noms_libres

WEB = Path(RACINE) / "opt/pincabos/web"
HISTORIQUES = ("pincabos_webapp_audio.py", "pincabos_webapp_inputs.py", "pincabos_webapp_firstrun.py",
               "pincabos_webapp_dev_admin.py", "pincabos_webapp_exports.py", "pincabos_backupcfg.py")
DICTIONNAIRE = ("pincabos_impexp.py", "pincabos_batch_transfer.py", "PinCabOS-ExplorerInstall.py")
NOUVEAUX = ("pincabos_webapp_identifiants.py", "pincabos_webapp_supporters.py")


def src(nom):
    return (WEB / nom).read_text(encoding="utf-8")


class Autonomie(unittest.TestCase):
    def test_app_ne_passe_plus_ses_globals(self):
        app = src("app.py")
        for mot in ("globals()", "runtime_globals", "context_globals", "app_globals"):
            self.assertNotIn(mot, app, mot)
        for m in HISTORIQUES:
            self.assertIn("    _pco_module.register(app)", app)
        self.assertIn("register_pincabos_impexp_routes(app)", app)
        self.assertIn("register_pincabos_batch_transfer(app)", app)

    def test_modules_historiques_sans_nom_libre_ni_injection(self):
        for m in HISTORIQUES:
            texte = src(m)
            self.assertEqual(noms_libres(texte), set(), m)
            self.assertIn("def register(host_app, runtime_globals=None):", texte, m)
            self.assertNotIn("globals()[key] = value", texte, m)
            self.assertNotIn("runtime_globals[key] = value", texte, m)
            self.assertNotIn("runtime_globals.items()", texte, m)
            # les lectures dynamiques globals().get("X") visaient les globals injectés : X doit exister dans le module
            for nom in set(re.findall(r'globals\(\)\.get\(\s*"(\w+)"', texte)):
                self.assertRegex(texte, rf"(?m)^\s*{nom}\b|import [^\n]*\b{nom}\b|^\s+{nom},\s*$", f"{m} : {nom} lu par globals().get sans définition ni import")

    def test_plus_de_dictionnaire_de_globals(self):
        for m in DICTIONNAIRE:
            texte = src(m)
            self.assertNotRegex(texte, r"app_globals\[|_CTX\.get\(|runtime_globals\[", m)
        self.assertIn("from pincabos_webapp_gabarit import page", src("pincabos_impexp.py"))
        self.assertIn("from pincabos_webapp_export import (", src("pincabos_batch_transfer.py"))
        self.assertIn("from pincabos_webapp_import import pincabos_manifest_table_folder_from_archive", src("PinCabOS-ExplorerInstall.py"))

    def test_app_ne_reexporte_plus_pour_les_modules(self):
        app = src("app.py")
        for mot in ("from pincabos_webapp_gpu import", "from pincabos_webapp_import import pincabos_manifest",
                    "from pincabos_webapp_export import", "from pincabos_webapp_admin_pages import ("):
            self.assertNotIn(mot, app, mot)
        self.assertIn("from pincabos_webapp_gabarit import page, pincabos_firstrun_is_complete", app)

    def test_pas_de_cycle_d_import_entre_gabarit_admin_et_dev_admin(self):
        gabarit = src("pincabos_webapp_gabarit.py")
        self.assertNotIn("pincabos_webapp_admin_pages", gabarit)
        self.assertNotIn("pincabos_webapp_firstrun", gabarit)
        self.assertIn("from pincabos_webapp_supporters import pincabos_footer_supporters_inline_html", gabarit)
        self.assertIn("firstrun_load_cfg, firstrun_required_keys", gabarit)
        dev = src("pincabos_webapp_dev_admin.py")
        self.assertNotRegex(dev, r"(?m)^from pincabos_webapp_admin_pages import|^import pincabos_webapp_admin_pages")
        self.assertIn("from pincabos_webapp_admin_pages import pincabos_admin_page as page_admin_composee", dev, "import différé dans la route /admin")
        self.assertIn("return page_admin_composee()", dev)
        self.assertIn("from pincabos_webapp_identifiants import (", dev)
        for nom in ("ADMIN_LOGIN_PASS", "ADMIN_LOGIN_USER", "PINCABOS_ADMIN_CREDENTIALS_ARE_DEFAULT", "PINCABOS_ADMIN_UNREADABLE_SECRETS",
                    "PINCABOS_DEFAULT_DEV_PASS", "PINCABOS_DEFAULT_DEV_USER"):
            self.assertIn(f"    {nom},\n", dev, nom)
        for m in NOUVEAUX:
            texte = src(m)
            self.assertNotRegex(texte, r"(?m)^(from|import) pincabos_webapp_(admin_pages|dev_admin|gabarit|firstrun)")
            self.assertEqual(noms_libres(texte), set(), m)

    def test_configuration_premiere_execution_dans_le_noyau(self):
        core = src("pincabos_webapp_core.py")
        for nom in ("PINCABOS_FIRSTRUN_CFG = ", "def firstrun_default_cfg():", "def firstrun_required_keys():", "def firstrun_load_cfg():"):
            self.assertIn(nom, core, nom)
        firstrun = src("pincabos_webapp_firstrun.py")
        self.assertNotIn("def firstrun_load_cfg():", firstrun)
        self.assertIn("firstrun_load_cfg,", firstrun)
        self.assertIn("def screens_layout_text():", firstrun, "seul consommateur : le wizard")

    def test_chargement_reel_sans_globals(self):
        try:
            import flask
        except ImportError:
            self.skipTest("flask absent")
        if not (hasattr(flask, "Flask") and hasattr(flask, "current_app")):
            self.skipTest("bouchon flask")
        import sys
        sys.path.insert(0, str(WEB))
        sys.path.insert(0, str(Path(RACINE) / "opt/pincabos/tools"))  # pincabos_vpx_input, pincabos_ini (hors /opt)
        try:
            import importlib
            app = flask.Flask("test")
            for m in HISTORIQUES:
                mod = importlib.import_module(m[:-3])
                mod.register(app)  # sans globals : import et enregistrement doivent passer
            self.assertIn("/first-run", {r.rule for r in app.url_map.iter_rules()})
        finally:
            sys.path.remove(str(WEB))


if __name__ == "__main__":
    unittest.main()
