"""Rotation du playfield : une seule couche, la physique (PINCABOS_ROTATION_PHYSIQUE_V1).

Contrat : screens.json porte `playfield_rotation` ; xrandr l'applique (session,
hotplug, page Ecran) ; VPinFE recoit toujours tablerotation = 0 ; VPX rien.
Les blocs Python embarques dans les scripts shell sont extraits et executes
tels quels, pour que le test couvre le code qui tourne sur le cab.
"""
import contextlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path

from _charge import charger, RACINE

rot = charger("opt/pincabos/tools/pincabos_screen_rotation.py", "pco_rotation")
sys.modules["pincabos_screen_rotation"] = rot  # les scripts l'importent sous ce nom

XRANDR_SH = Path(RACINE) / "opt/pincabos/tools/pincabos-screen-xrandr.sh"
LIGHTDM_SH = Path(RACINE) / "opt/pincabos/tools/pincabos-screen-lightdm-safe.sh"
HOTPLUG_SH = Path(RACINE) / "usr/local/libexec/pincabos/pincabos-screen-hotplug"
SCREEN_PY = Path(RACINE) / "opt/pincabos/web/screen.py"
APP_PY = Path(RACINE) / "opt/pincabos/web/app.py"

QUERY = """Screen 0: minimum 8 x 8, current 7680 x 2160, maximum 32767 x 32767
HDMI-0 connected primary 3840x2160+0+0 (normal left inverted right x axis y axis) 708mm x 398mm
   3840x2160     60.00*+  30.00
   1920x1080     60.00
DP-1 connected 1920x1080+3840+0 (normal left inverted right x axis y axis) 600mm x 340mm
   1920x1080     60.00*+
DP-2 connected 1920x1080+5760+0 (normal left inverted right x axis y axis) 600mm x 340mm
   1920x1080     60.00*+
DP-3 disconnected (normal left inverted right x axis y axis)
"""


def bloc_python(script: Path, debut: str) -> str:
    """Le bloc heredoc Python qui suit `debut` dans un script shell."""
    texte = script.read_text(encoding="utf-8")
    a = texte.index(debut) + len(debut)
    b = texte.index("\nPY\n", a)
    return texte[a:b]


def config(rotation="0", roles=True, geometrie_tournee=False):
    pf = {"name": "HDMI-0", "x": 0, "y": 0, "width": 3840, "height": 2160, "is_primary": True,
          "available": True, "geometry": "3840x2160+0+0"}
    if geometrie_tournee:
        pf.update({"width": 2160, "height": 3840, "geometry": "2160x3840+0+0"})
    data = {
        "mode": "manual", "cabinet_mode": True, "playfield_orientation": "landscape",
        "playfield_rotation": rotation,
        "playfield": pf,
        "backglass": {"name": "DP-1", "x": 3840, "y": 0, "width": 1920, "height": 1080, "is_primary": False,
                      "available": True, "geometry": "1920x1080+3840+0"},
        "fulldmd": {"name": "DP-2", "x": 5760, "y": 0, "width": 1920, "height": 1080, "is_primary": False,
                    "available": True, "geometry": "1920x1080+5760+0"},
    }
    if roles:
        data["roles"] = {"playfield": {"output": "HDMI-0", "mode": "3840x2160", "rate": "60.00"},
                         "backglass": {"output": "DP-1", "mode": "1920x1080", "rate": ""},
                         "fulldmd": {"output": "DP-2", "mode": "1920x1080", "rate": ""}}
    return data


class Module(unittest.TestCase):
    def test_lecture_tolerante(self):
        for brut, attendu in (("180", 180), (180, 180), ("0", 0), ("", 0), (None, 0), ("45", 0), ("abc", 0), ("270", 270), ("450", 90)):
            self.assertEqual(rot.rotation({"playfield_rotation": brut}), attendu, repr(brut))
        self.assertEqual(rot.rotation({}), 0)
        self.assertEqual(rot.rotation(None), 0)

    def test_mots_cles_xrandr(self):
        self.assertEqual([rot.xrandr_rotate(r) for r in (0, 90, 180, 270)], ["normal", "right", "inverted", "left"])
        self.assertEqual(rot.xrandr_rotate("180"), "inverted")
        self.assertEqual(rot.xrandr_rotate("n'importe"), "normal")

    def test_rotation_par_role(self):
        data = {"playfield_rotation": "180"}
        self.assertEqual(rot.role_rotation("playfield", data), 180)
        for role in ("backglass", "fulldmd", "topper"):
            self.assertEqual(rot.role_rotation(role, data), 0, "absent = 0, le fronton ne tourne pas par defaut")
        data["backglass_rotation"] = "90"
        data["topper_rotation"] = 180
        self.assertEqual(rot.role_rotation("backglass", data), 90)
        self.assertEqual(rot.role_rotation("topper", data), 180)
        self.assertEqual(rot.role_rotation("fulldmd", data), 0)
        self.assertEqual(rot.role_rotation("inconnu", data), 0)

    def test_taille_tournee_et_modes(self):
        self.assertEqual(rot.tourne(3840, 2160, 90), (2160, 3840))
        self.assertEqual(rot.tourne(3840, 2160, 180), (3840, 2160))
        self.assertEqual(rot.modes_candidats("2160x3840", 90), ["2160x3840", "3840x2160"])
        self.assertEqual(rot.modes_candidats("3840x2160", 180), ["3840x2160"])
        self.assertEqual(rot.modes_candidats("", 90), [])
        self.assertEqual(rot.modes_candidats("1080x1080", 270), ["1080x1080"])

    def test_libelles(self):
        self.assertEqual(rot.libelle(180), "À l'envers (retourné de 180°)")
        self.assertEqual(rot.libelle("0"), "À l'endroit")


class FauxSubprocess:
    """Remplace subprocess pour le bloc de pincabos-screen-xrandr.sh : xrandr
    --query renvoie une sortie fixe, les autres commandes sont enregistrees."""

    def __init__(self, query):
        self.query = query
        self.commandes = []

    def run(self, cmd, **kwargs):
        if list(cmd)[:2] == ["xrandr", "--query"]:
            return types.SimpleNamespace(stdout=self.query, returncode=0)
        self.commandes.append(list(cmd))
        return types.SimpleNamespace(stdout="", returncode=0)


class ScriptXrandr(unittest.TestCase):
    """Le bloc Python de `pincabos-screen-xrandr.sh apply`, execute avec un faux xrandr."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def appliquer(self, data, query=QUERY):
        cfg = Path(self.tmp) / "screens.json"
        cfg.write_text(json.dumps(data), encoding="utf-8")
        code = bloc_python(XRANDR_SH, 'python3 - "$CFG" <<\'PY\'\n')
        faux = FauxSubprocess(query)
        vrai = sys.modules.get("subprocess")
        argv = sys.argv
        sortie = io.StringIO()
        try:
            sys.modules["subprocess"] = faux
            sys.argv = ["apply", str(cfg)]
            with contextlib.redirect_stdout(sortie):
                exec(compile(code, str(XRANDR_SH), "exec"), {"__name__": "__main__"})
        finally:
            sys.modules["subprocess"] = vrai
            sys.argv = argv
        return faux.commandes, sortie.getvalue()

    def commande(self, commandes, output):
        return next(c for c in commandes if "--output" in c and c[c.index("--output") + 1] == output and "--mode" in c)

    def test_retourne_180(self):
        commandes, _ = self.appliquer(config("180"))
        pf = self.commande(commandes, "HDMI-0")
        self.assertEqual(pf[pf.index("--rotate") + 1], "inverted")
        self.assertEqual(pf[pf.index("--mode") + 1], "3840x2160")
        bg = self.commande(commandes, "DP-1")
        self.assertEqual(bg[bg.index("--rotate") + 1], "normal", "les ecrans de fronton ne tournent pas")
        self.assertEqual(bg[bg.index("--pos") + 1], "3840x0")

    def test_a_l_endroit(self):
        commandes, _ = self.appliquer(config("0"))
        pf = self.commande(commandes, "HDMI-0")
        self.assertEqual(pf[pf.index("--rotate") + 1], "normal")

    def test_90_degres_largeur_tournee(self):
        data = config("90")
        for role in ("playfield", "backglass", "fulldmd"):
            data[role].pop("geometry")  # pas de position memorisee : position calculee
        commandes, _ = self.appliquer(data)
        pf = self.commande(commandes, "HDMI-0")
        self.assertEqual(pf[pf.index("--rotate") + 1], "right")
        self.assertEqual(pf[pf.index("--mode") + 1], "3840x2160", "le mode reste celui de la dalle")
        bg = self.commande(commandes, "DP-1")
        self.assertEqual(bg[bg.index("--pos") + 1], "2160x0", "le fronton se pose apres la HAUTEUR de la dalle tournee")
        fd = self.commande(commandes, "DP-2")
        self.assertEqual(fd[fd.index("--pos") + 1], "4080x0")

    def test_playfield_seul(self):
        data = config("270")
        for role in ("backglass", "fulldmd"):
            data.pop(role)
            data["roles"].pop(role)
        commandes, sortie = self.appliquer(data)
        self.assertEqual(len([c for c in commandes if "--mode" in c]), 1)
        pf = self.commande(commandes, "HDMI-0")
        self.assertEqual(pf[pf.index("--rotate") + 1], "left")
        self.assertIn("--primary", pf)

    def test_deux_ecrans_sans_fulldmd(self):
        data = config("180")
        data.pop("fulldmd"); data["roles"].pop("fulldmd")
        data["backglass"].pop("geometry")
        commandes, _ = self.appliquer(data)
        self.assertEqual(sorted(c[c.index("--output") + 1] for c in commandes if "--mode" in c), ["DP-1", "HDMI-0"])
        bg = self.commande(commandes, "DP-1")
        self.assertEqual(bg[bg.index("--pos") + 1], "3840x0")
        self.assertEqual(bg[bg.index("--rotate") + 1], "normal")

    def test_quatre_ecrans_topper_au_dessus_du_fronton(self):
        data = config("90")
        data["topper"] = {"name": "DP-3", "x": 3840, "y": -1080, "width": 1920, "height": 1080, "is_primary": False,
                          "available": True, "geometry": "1920x1080+3840+-1080"}
        data["roles"]["topper"] = {"output": "DP-3", "mode": "1920x1080", "rate": ""}
        query = QUERY.replace("DP-3 disconnected (normal left inverted right x axis y axis)",
                              "DP-3 connected 1920x1080+3840+-1080 (normal left inverted right x axis y axis) 600mm x 340mm\n   1920x1080     60.00*+")
        commandes, _ = self.appliquer(data, query)
        tp = self.commande(commandes, "DP-3")
        self.assertEqual(tp[tp.index("--pos") + 1], "3840x-1080", "la geometrie du role prime")
        self.assertEqual(tp[tp.index("--rotate") + 1], "normal")
        pf = self.commande(commandes, "HDMI-0")
        self.assertEqual(pf[pf.index("--rotate") + 1], "right")

    def test_backglass_tourne_lui_aussi(self):
        data = config("0")
        data["backglass_rotation"] = "180"
        commandes, _ = self.appliquer(data)
        bg = self.commande(commandes, "DP-1")
        self.assertEqual(bg[bg.index("--rotate") + 1], "inverted")
        pf = self.commande(commandes, "HDMI-0")
        self.assertEqual(pf[pf.index("--rotate") + 1], "normal")

    def test_geometrie_memorisee_tournee_sans_roles(self):
        # screens.json enregistre apres une rotation : 2160x3840, et pas de cle roles
        data = config("90", roles=False, geometrie_tournee=True)
        commandes, _ = self.appliquer(data)
        pf = self.commande(commandes, "HDMI-0")
        self.assertEqual(pf[pf.index("--mode") + 1], "3840x2160", "mode inverse retrouve dans la liste xrandr")
        self.assertEqual(pf[pf.index("--rotate") + 1], "right")


class ScriptLightdm(unittest.TestCase):
    """Le bloc Python de pincabos-screen-lightdm-safe.sh : une ligne par role,
    avec le mot-cle de rotation et le mode inverse a essayer."""

    def lignes(self, data):
        tmp = tempfile.mkdtemp()
        try:
            cfg = Path(tmp) / "screens.json"
            cfg.write_text(json.dumps(data), encoding="utf-8")
            code = bloc_python(LIGHTDM_SH, 'python3 - "$CFG" >"$ITEMS" <<\'PY\'\n')
            argv = sys.argv
            sortie = io.StringIO()
            try:
                sys.argv = ["lightdm", str(cfg)]
                with contextlib.redirect_stdout(sortie):
                    exec(compile(code, str(LIGHTDM_SH), "exec"), {"__name__": "__main__"})
            finally:
                sys.argv = argv
            return {l.split("\t")[0]: l.split("\t") for l in sortie.getvalue().splitlines()}
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_rotation_reappliquee_au_demarrage(self):
        lignes = self.lignes(config("180"))
        self.assertEqual(lignes["HDMI-0"][7], "inverted")
        self.assertEqual(lignes["DP-1"][7], "normal")
        self.assertEqual(lignes["DP-2"][7], "normal")
        self.assertEqual(lignes["HDMI-0"][8], "-", "pas de mode inverse a 180 (champ vide = « - »)")

    def test_90_propose_le_mode_inverse(self):
        lignes = self.lignes(config("90", geometrie_tournee=True))
        self.assertEqual(lignes["HDMI-0"][1:3], ["2160", "3840"])
        self.assertEqual(lignes["HDMI-0"][7], "right")
        self.assertEqual(lignes["HDMI-0"][8], "3840x2160")

    def test_sans_rotation(self):
        lignes = self.lignes(config("0"))
        self.assertEqual(lignes["HDMI-0"][7], "normal")

    def test_quatre_roles_et_rotation_du_fronton(self):
        data = config("0")
        data["topper"] = {"name": "DP-3", "x": 3840, "y": -1080, "width": 1920, "height": 1080, "is_primary": False, "available": True}
        data["fulldmd_rotation"] = "180"
        lignes = self.lignes(data)
        self.assertEqual(sorted(lignes), ["DP-1", "DP-2", "DP-3", "HDMI-0"])
        self.assertEqual(lignes["DP-2"][7], "inverted")
        self.assertEqual(lignes["DP-3"][3:5], ["3840", "-1080"])

    def test_aucun_champ_vide(self):
        """PINCABOS_LIGHTDM_CHAMPS_VIDES_V1 : pour `read`, deux tabulations collees ne font
        qu'un separateur ; un rate vide decalait les colonnes (--rate normal) et xrandr
        refusait la sortie. Un champ vide s'ecrit « - »."""
        lignes = self.lignes(config("0"))
        for nom, cols in lignes.items():
            self.assertEqual(len(cols), 9, nom)
            self.assertTrue(all(c != "" for c in cols), (nom, cols))
        self.assertEqual(lignes["HDMI-0"][8], "-")

    def test_le_shell_utilise_la_colonne(self):
        s = LIGHTDM_SH.read_text(encoding="utf-8")
        self.assertIn('[ "${RATE_CFG:-}" = "-" ] && RATE_CFG=""', s)
        self.assertIn('[ "${MODE_ALT:-}" = "-" ] && MODE_ALT=""', s)
        self.assertIn('--rotate "$ROTATE"', s)
        self.assertNotIn("--rotate normal)", s, "plus de « normal » force")
        self.assertIn("read -r OUT W H X Y PRIMARY RATE_CFG ROTATE MODE_ALT", s)
        self.assertIn('has_mode "$OUT" "$MODE_ALT"', s)


class ScriptHotplug(unittest.TestCase):
    def lignes(self, data):
        code = bloc_python(HOTPLUG_SH, "python3 - <<'PY' 2>/dev/null | while read -r output mode pos rotate mode_alt; do\n")
        code = code.replace('json.load(open("/opt/pincabos/config/screens/screens.json"))', "json.loads(%r)" % json.dumps(data))
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            try:
                exec(compile(code, str(HOTPLUG_SH), "exec"), {"__name__": "__main__"})
            except SystemExit:
                pass
        return {l.split()[0]: l.split() for l in sortie.getvalue().splitlines()}

    def test_rallumage_avec_rotation(self):
        lignes = self.lignes(config("180"))
        self.assertEqual(lignes["HDMI-0"], ["HDMI-0", "3840x2160", "0x0", "inverted", "-"])
        self.assertEqual(lignes["DP-1"][3], "normal")

    def test_90_mode_inverse(self):
        lignes = self.lignes(config("90", geometrie_tournee=True))
        self.assertEqual(lignes["HDMI-0"], ["HDMI-0", "2160x3840", "0x0", "right", "3840x2160"])

    def test_le_shell_passe_la_rotation(self):
        s = HOTPLUG_SH.read_text(encoding="utf-8")
        self.assertIn('--rotate "${rotate:-normal}"', s)
        self.assertIn('--mode "$mode_alt"', s)


def stub_flask():
    if "flask" in sys.modules:
        return
    try:
        import flask  # noqa: F401
        return
    except ImportError:
        pass
    m = types.ModuleType("flask")

    class Blueprint:
        def __init__(self, *a, **k):
            pass

        def route(self, *a, **k):
            return lambda f: f

    m.Blueprint = Blueprint
    m.redirect = lambda *a, **k: None
    m.url_for = lambda *a, **k: ""
    m.request = types.SimpleNamespace(form={})
    sys.modules["flask"] = m


class PageEcran(unittest.TestCase):
    """apply_vpinfe() de screen.py : la rotation ne part plus dans VPinFE."""

    def setUp(self):
        stub_flask()
        self.scr = charger("opt/pincabos/web/screen.py", "pco_screen")
        self.tmp = tempfile.mkdtemp()
        self.scr.CFG_DIR = Path(self.tmp)
        self.scr.CFG_FILE = Path(self.tmp) / "screens.json"
        self.scr.VPINFE_INI = Path(self.tmp) / "vpinfe.ini"
        self.scr.xrandr_query = lambda: QUERY
        shutil.copy(Path(RACINE) / "opt/pincabos/templates/home/.config/vpinfe/vpinfe.ini", self.scr.VPINFE_INI)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_vpinfe_recoit_toujours_zero(self):
        """PINCABOS_TOPOLOGIE_SOURCE_UNIQUE_V1 : la page n'écrit plus de clés ; elle appelle la
        topologie, seule à poser les sections d'affichage (tablerotation = 0 y compris)."""
        self.scr.CFG_FILE.write_text(json.dumps(config("180")), encoding="utf-8")
        appels = []
        self.scr.run_cmd = lambda cmd, timeout=30: (appels.append(list(cmd)), (0, "ok\n"))[1]
        avant = self.scr.VPINFE_INI.read_text(encoding="utf-8")
        r = self.scr.apply_vpinfe()
        self.assertTrue(r.startswith("GO:"), r)
        self.assertEqual(appels[-1][-2:], ["/opt/pincabos/scripts/pincabos-screen-topology.py", "--adopt-current-roles"])
        self.assertEqual(self.scr.VPINFE_INI.read_text(encoding="utf-8"), avant, "la page ne touche plus l'ini")
        self.assertTrue(self.scr.apply_vpx().startswith("GO:"))
        self.scr.run_cmd = lambda cmd, timeout=30: (1, "boum")
        self.assertTrue(self.scr.apply_vpinfe().startswith("NOGO:"))
        self.assertEqual(json.loads(self.scr.CFG_FILE.read_text())["playfield_rotation"], "180",
                         "screens.json garde la rotation physique, c'est la topologie qui la lit")

    def test_libelles_de_la_page(self):
        s = SCREEN_PY.read_text(encoding="utf-8")
        self.assertIn("Sens du playfield", s)
        self.assertIn("À l'envers (retourné de 180°)", s)
        self.assertNotIn("<label>Playfield Rotation</label>", s)


class Coherence(unittest.TestCase):
    """Les consommateurs partagent le module : aucune table de rotation recopiee."""

    def test_les_trois_scripts_importent_le_module(self):
        for script in (XRANDR_SH, LIGHTDM_SH, HOTPLUG_SH):
            self.assertIn("import pincabos_screen_rotation", script.read_text(encoding="utf-8"), script.name)

    def test_aucune_table_recopiee(self):
        for script in (XRANDR_SH, LIGHTDM_SH, HOTPLUG_SH):
            self.assertNotIn('"inverted"', script.read_text(encoding="utf-8"), script.name)

    def test_app_py_n_envoie_plus_la_rotation_a_vpinfe(self):
        s = APP_PY.read_text(encoding="utf-8")
        self.assertNotIn('"Displays", "tablerotation", playfield_rotation)', s)
        # PINCABOS_TOPOLOGIE_SOURCE_UNIQUE_V1 : la page GPU ne pose plus les cles VPinFE elle-meme,
        # seul le formulaire des roles manuels ecrit encore tablerotation = 0 ; la topologie le pose aussi.
        self.assertEqual(s.count('"Displays", "tablerotation", "0")'), 1)
        self.assertIn("pincabos_gpu_rejouer_topologie", s)
        topo = Path(RACINE, "opt/pincabos/scripts/pincabos-screen-topology.py").read_text(encoding="utf-8")
        self.assertIn('"tablerotation": "0",', topo)
        self.assertIn('"playfield_rotation": rotation,', topo, "la valeur physique reste tracee, par la topologie")

    def test_module_executable_seul(self):
        tmp = tempfile.mkdtemp()
        try:
            cfg = Path(tmp) / "screens.json"
            cfg.write_text(json.dumps(config("180")), encoding="utf-8")
            import subprocess
            r = subprocess.run([sys.executable, str(Path(RACINE) / "opt/pincabos/tools/pincabos_screen_rotation.py"), str(cfg)],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("--rotate inverted", r.stdout)
            self.assertIn("tablerotation = 0", r.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
