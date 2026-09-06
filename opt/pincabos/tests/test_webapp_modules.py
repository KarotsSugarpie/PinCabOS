"""Modules de pages de la WebApp (PINCABOS_WEBAPP_MODULES_V1).

Les pages GPU / Écrans et DOF / Outputs vivent dans `pincabos_webapp_gpu.py` et
`pincabos_webapp_dof.py` : mêmes chemins, mêmes noms de fonction, code déplacé tel quel.
Ce test verrouille le découpage : routes au bon endroit, aucun nom libre non résolu
dans les modules (un import oublié serait une page en erreur 500 sur le cab), helpers
partagés définis une seule fois dans le noyau, enregistrement au bon moment dans app.py.
"""
import ast
import builtins
import re
import sys
import types
import unittest
from pathlib import Path

from _charge import RACINE

WEB = Path(RACINE) / "opt/pincabos/web"
APP = WEB / "app.py"
CORE = WEB / "pincabos_webapp_core.py"
MODULES = {
    "gpu": WEB / "pincabos_webapp_gpu.py",
    "dof": WEB / "pincabos_webapp_dof.py",
    "dmd": WEB / "pincabos_webapp_dmd.py",
    "console": WEB / "pincabos_webapp_console.py",
}
ROUTES = {
    "gpu": {
        "/gpu", "/gpu/screens", "/gpu/wallpaper/file/<path:filename>", "/gpu/wallpaper/select",
        "/gpu/wallpaper/apply", "/gpu/apply-screens", "/gpu/apply-vpinfe", "/gpu/apply-vpx",
        "/restart-vpinfe", "/auto-screens",
    },
    "dof": {
        "/dof", "/dof/commander", "/dof/install-utils", "/dof/install-utils/<component>",
        "/dof/import-api", "/dof/import-config", "/dof/import-cabinet-json", "/api/dof/commander/test",
    },
    "dmd": {
        "/fulldmd", "/fulldmd/style", "/fulldmd/apply", "/api/fulldmd/style/set", "/api/fulldmd/status",
        "/api/fulldmd/save", "/close-fulldmd-calibrator", "/launch-fulldmd-calibrator", "/fulldmd-screen",
        "/dmd/apply", "/dmd-screen", "/api/dmd/save", "/launch-dmd-calibrator", "/close-dmd-calibrator",
        "/fulldmd-log-page-disabled",
    },
    "console": {
        "/console", "/console/", "/root-password", "/network/wifi-hotspot", "/network/wifi-hotspot-stop",
        "/toggle-webapp-screen", "/launch-webapp-screen", "/close-webapp-screen",
    },
}
HELPERS = ("esc", "run_cmd", "shlex_quote", "service_status",
           "pincabos_meta", "pincabos_backup_config_file", "pincabos_write_json_with_meta", "get_ip")


def routes_de(texte, decorateur):
    return set(re.findall(rf'^@{decorateur}\.route\("([^"]+)"', texte, re.M))


def noms_definis(tree):
    """Noms posés au niveau du module, blocs try/except compris."""
    definis = set()

    def visiter(noeuds):
        for n in noeuds:
            if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
                definis.add(n.name)
            elif isinstance(n, ast.Assign):
                for t in n.targets:
                    for e in ast.walk(t):
                        if isinstance(e, ast.Name):
                            definis.add(e.id)
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                for a in n.names:
                    definis.add((a.asname or a.name).split(".")[0])
            elif isinstance(n, ast.Try):
                visiter(n.body)
                for h in n.handlers:
                    visiter(h.body)

    visiter(tree.body)
    return definis


def noms_libres(texte):
    """Noms lus dans les fonctions du module sans être locaux, ni builtins, ni définis au niveau du module."""
    tree = ast.parse(texte)
    definis = noms_definis(tree)
    libres = set()
    for n in tree.body:
        if not isinstance(n, ast.FunctionDef):
            continue
        loc = {a.arg for a in ast.walk(n) if isinstance(a, ast.arg)}
        for e in ast.walk(n):
            if isinstance(e, ast.Name) and isinstance(e.ctx, ast.Store):
                loc.add(e.id)
            elif isinstance(e, (ast.FunctionDef, ast.ClassDef)):
                loc.add(e.name)
            elif isinstance(e, ast.ExceptHandler) and e.name:
                loc.add(e.name)
            elif isinstance(e, (ast.Import, ast.ImportFrom)):
                for a in e.names:
                    loc.add((a.asname or a.name).split(".")[0])
        for e in ast.walk(n):
            if isinstance(e, ast.Name) and isinstance(e.ctx, ast.Load) and e.id not in loc and not hasattr(builtins, e.id):
                libres.add(e.id)
    return libres - definis


class Decoupage(unittest.TestCase):
    def setUp(self):
        self.app = APP.read_text(encoding="utf-8")
        self.textes = {k: p.read_text(encoding="utf-8") for k, p in MODULES.items()}

    def test_routes_dans_les_modules_et_plus_dans_app(self):
        for cle, attendues in ROUTES.items():
            self.assertEqual(routes_de(self.textes[cle], f"{cle}_bp"), attendues, cle)
            for r in attendues:
                self.assertNotIn(f'@app.route("{r}"', self.app, r)
        self.assertNotIn("@app.route(", self.textes["gpu"])
        self.assertNotIn("@app.route(", self.textes["dof"])

    def test_aucun_nom_libre_dans_les_modules(self):
        for cle, texte in self.textes.items():
            self.assertEqual(noms_libres(texte), set(), cle)

    def test_endpoint_prefixe_par_le_blueprint(self):
        self.assertIn('url_for("gpu.gpu_page")', self.textes["gpu"])
        self.assertNotIn('url_for("gpu_page")', self.textes["gpu"])
        self.assertIn('url_for("dmd.fulldmd_page")', self.textes["dmd"])
        self.assertNotIn('url_for("fulldmd_page")', self.textes["dmd"])
        # l'application n'est pas un global des modules : current_app
        for texte in self.textes.values():
            self.assertNotRegex(texte, r"(?<![\w.])app\.(logger|response_class|config)")

    def test_fonctions_deplacees_absentes_d_app(self):
        for cle, texte in self.textes.items():
            for nom in re.findall(r"^def (\w+)\(", texte, re.M):
                if nom == "register":
                    continue
                self.assertNotIn(f"def {nom}(", self.app, f"{nom} existe encore dans app.py")
                self.assertNotRegex(self.app, rf"\b{nom}\(", f"{nom} appelé depuis app.py")

    def test_helpers_partages_une_seule_fois_dans_le_noyau(self):
        core = CORE.read_text(encoding="utf-8")
        for nom in HELPERS:
            self.assertIn(f"\ndef {nom}(", core, nom)
            self.assertNotIn(f"\ndef {nom}(", self.app, nom)
            self.assertRegex(self.app, rf"(?m)^    {nom},$", f"{nom} importé du noyau par app.py")
            for cle, texte in self.textes.items():
                self.assertNotIn(f"\ndef {nom}(", texte, (cle, nom))

    def test_enregistrement_apres_page_et_avant_les_enrobages(self):
        i_page = self.app.index("\ndef page(title, body):")
        i_reg = self.app.index("pco_gpu_routes.register(app, page)")
        i_dof = self.app.index("pco_dof_routes.register(app, page)")
        i_dmd = self.app.index("pco_dmd_routes.register(app, page)")
        i_console = self.app.index("pco_console_routes.register(app, page)")
        i_wrap = self.app.index("def _pco_dashboard_plus_final_install_wrapper")
        self.assertLess(i_page, i_reg)
        self.assertLess(i_reg, i_dof)
        self.assertLess(i_dof, i_dmd)
        self.assertLess(i_dmd, i_console)
        self.assertLess(i_console, i_wrap)

    def test_register_pose_page_et_le_blueprint(self):
        for cle, texte in self.textes.items():
            self.assertIn("\npage = None", texte, cle)
            self.assertIn("def register(app, page_fn):", texte, cle)
            self.assertIn(f"app.register_blueprint({cle}_bp)", texte, cle)


class Chargement(unittest.TestCase):
    """Les modules s'importent seuls (Flask présent) et exposent leurs routes sur une app vierge."""

    def test_import_et_enregistrement(self):
        try:
            import flask
        except ImportError:
            self.skipTest("flask absent")
        if not (hasattr(flask, "Flask") and hasattr(flask, "current_app")):
            self.skipTest("flask remplacé par un bouchon (test_rotation_physique) : pas de vrai Flask ici")
        sys.path.insert(0, str(WEB))
        try:
            for cle in MODULES:
                sys.modules.pop(f"pincabos_webapp_{cle}", None)
            import pincabos_webapp_gpu as gpu
            import pincabos_webapp_dof as dof
            import pincabos_webapp_dmd as dmd
            import pincabos_webapp_console as console
            app = flask.Flask("test")
            gpu.register(app, lambda t, b: f"<p>{t}</p>{b}")
            dof.register(app, lambda t, b: f"<p>{t}</p>{b}")
            dmd.register(app, lambda t, b: f"<p>{t}</p>{b}")
            console.register(app, lambda t, b: f"<p>{t}</p>{b}")
            regles = {r.rule for r in app.url_map.iter_rules()}
            for attendues in ROUTES.values():
                self.assertTrue(attendues <= regles, attendues - regles)
            self.assertIn("gpu.gpu_page", app.view_functions)
            self.assertIn("dof.dof_page", app.view_functions)
            self.assertIn("dmd.fulldmd_page", app.view_functions)
            self.assertIn("console.console_page", app.view_functions)
            self.assertEqual(gpu.page("x", "y"), "<p>x</p>y")  # page posée par register
            self.assertEqual(dof.page("x", "y"), "<p>x</p>y")
        finally:
            sys.path.remove(str(WEB))


if __name__ == "__main__":
    unittest.main()
