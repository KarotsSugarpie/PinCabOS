"""Topologie ecrans : inference des roles et reconnaissance par EDID.

Ces cas sont ceux qui ont produit des incidents reels : topper pris pour un
backglass, cabinet range playfield->fulldmd->backglass, ecran manquant.
"""
import unittest

from _charge import charger

topo = charger("opt/pincabos/scripts/pincabos-screen-topology.py", "pco_topologie")


def ecran(nom, x, y, w, h, primaire=False, edid=None):
    return {
        "app_index": 0, "name": nom, "x": x, "y": y, "width": w, "height": h,
        "area": w * h, "is_primary": primaire, "raw": "",
        "edid_sha256": edid or f"edid-{nom}",
    }


PF = ecran("HDMI-0", 0, 0, 3840, 2160, primaire=True)
BG = ecran("DP-2", 3840, 0, 1920, 1080)
FD = ecran("DP-0", 5760, 0, 1920, 1080)


class Inference(unittest.TestCase):
    def test_trois_ecrans_ordre_canonique(self):
        roles = topo.infer_roles([PF, BG, FD])
        self.assertEqual(roles["playfield"]["name"], "HDMI-0")
        self.assertEqual(roles["backglass"]["name"], "DP-2")
        self.assertEqual(roles["fulldmd"]["name"], "DP-0")
        self.assertIsNone(roles["topper"])

    def test_playfield_est_le_plus_grand_meme_sans_primaire(self):
        roles = topo.infer_roles([ecran("A", 0, 0, 1920, 1080, primaire=True), ecran("B", 1920, 0, 3840, 2160)])
        self.assertEqual(roles["playfield"]["name"], "B")

    def test_topper_au_dessus_du_playfield_ne_vole_pas_le_backglass(self):
        topper = ecran("DP-4", 0, -1080, 1920, 1080)
        roles = topo.infer_roles([PF, BG, FD, topper])
        self.assertEqual(roles["topper"]["name"], "DP-4")
        self.assertEqual(roles["backglass"]["name"], "DP-2")
        self.assertEqual(roles["fulldmd"]["name"], "DP-0")

    def test_quatre_ecrans_en_ligne_le_dernier_devient_topper(self):
        quatrieme = ecran("DP-4", 7680, 0, 1920, 1080)
        roles = topo.infer_roles([PF, BG, FD, quatrieme])
        self.assertEqual(roles["topper"]["name"], "DP-4")

    def test_deux_ecrans_pas_de_fulldmd(self):
        roles = topo.infer_roles([PF, BG])
        self.assertEqual(roles["backglass"]["name"], "DP-2")
        self.assertIsNone(roles["fulldmd"])
        self.assertIsNone(roles["topper"])

    def test_un_seul_ecran(self):
        roles = topo.infer_roles([PF])
        self.assertEqual(roles["playfield"]["name"], "HDMI-0")
        self.assertIsNone(roles["backglass"])
        self.assertIsNone(roles["fulldmd"])

    def test_aucun_ecran(self):
        roles = topo.infer_roles([])
        self.assertEqual(set(roles), set(topo.ROLES))
        self.assertTrue(all(v is None for v in roles.values()))


class ReconnaissanceParEdid(unittest.TestCase):
    liaisons = {"roles": {"playfield": "edid-HDMI-0", "backglass": "edid-DP-2", "fulldmd": "edid-DP-0"}}

    def test_machine_connue_les_roles_suivent_l_edid_pas_la_position(self):
        # cabinet range playfield -> fulldmd -> backglass : l'EDID doit gagner
        bg_deplace = ecran("DP-2", 5760, 0, 1920, 1080)
        fd_deplace = ecran("DP-0", 3840, 0, 1920, 1080)
        roles, nouvelle = topo.resolve_roles([PF, fd_deplace, bg_deplace], self.liaisons)
        self.assertFalse(nouvelle)
        self.assertEqual(roles["backglass"]["name"], "DP-2")
        self.assertEqual(roles["fulldmd"]["name"], "DP-0")

    def test_ecran_manquant_jamais_reaffecte_au_hasard(self):
        roles, nouvelle = topo.resolve_roles([PF, BG], self.liaisons)
        self.assertFalse(nouvelle)
        self.assertEqual(roles["backglass"]["name"], "DP-2")
        self.assertIsNone(roles["fulldmd"])

    def test_aucun_edid_connu_c_est_une_autre_machine(self):
        autres = [ecran("X", 0, 0, 3840, 2160, edid="e1"), ecran("Y", 3840, 0, 1920, 1080, edid="e2")]
        roles, nouvelle = topo.resolve_roles(autres, self.liaisons)
        self.assertTrue(nouvelle)
        self.assertEqual(roles["playfield"]["name"], "X")

    def test_sans_profil_on_infere(self):
        roles, nouvelle = topo.resolve_roles([PF, BG, FD], {})
        self.assertTrue(nouvelle)
        self.assertEqual(roles["fulldmd"]["name"], "DP-0")


class EcritureIni(unittest.TestCase):
    ini = "[Displays]\ntablescreenid = 0\nbgscreenid = 9\n\n[Autre]\nkey = v\n"

    def test_met_a_jour_et_ajoute_sans_toucher_le_reste(self):
        out = topo.update_section(self.ini, "Displays", {"bgscreenid": "1", "dmdscreenid": "2"})
        self.assertIn("bgscreenid = 1", out)
        self.assertIn("dmdscreenid = 2", out)
        self.assertNotIn("bgscreenid = 9", out)
        self.assertIn("[Autre]\nkey = v", out)

    def test_section_absente_creee(self):
        out = topo.update_section("[Autre]\nkey = v\n", "Displays", {"tablescreenid": "0"})
        self.assertIn("[Displays]", out)
        self.assertIn("tablescreenid = 0", out)

    def test_idempotent(self):
        une = topo.update_section(self.ini, "Displays", {"bgscreenid": "1"})
        deux = topo.update_section(une, "Displays", {"bgscreenid": "1"})
        self.assertEqual(une, deux)


class SourceUnique(unittest.TestCase):
    """PINCABOS_TOPOLOGIE_SOURCE_UNIQUE_V1 : apply_consumers pose mode cabinet, orientation,
    rotation (toujours 0 pour VPinFE) et le suivi PinCabOs.Screens depuis screens.json."""

    def setUp(self):
        import tempfile, json
        from pathlib import Path
        self.tmp = Path(tempfile.mkdtemp())
        self.sauve = {k: getattr(topo, k) for k in ("SCREENS", "VPINFE", "VPX", "CAL_FULLDMD", "CAL_DMD")}
        topo.SCREENS = self.tmp / "screens.json"
        topo.VPINFE = self.tmp / "vpinfe.ini"
        topo.VPX = self.tmp / "VPinballX.ini"
        topo.CAL_FULLDMD = self.tmp / "fulldmd.json"
        topo.CAL_DMD = self.tmp / "dmd.json"
        topo.VPINFE.write_text("[Displays]\ncabmode = false\ntablerotation = 270\n\n[Autre]\nk = v\n", encoding="utf-8")
        topo.VPX.write_text("[Player]\nBGSet = 1\n", encoding="utf-8")
        self.json = json

    def tearDown(self):
        import shutil
        for k, v in self.sauve.items():
            setattr(topo, k, v)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def roles(self):
        def r(name, sid, dispo=True):
            return {"available": dispo, "screen_id": sid, "name": name, "edid_sha256": "x" + name}
        return {"playfield": r("HDMI-0", 0), "backglass": r("DP-0", 1), "fulldmd": r("DP-2", 2), "topper": r("", None, False)}

    def test_mode_cabinet_orientation_rotation_depuis_screens_json(self):
        topo.SCREENS.write_text(self.json.dumps({"cabinet_mode": True, "playfield_orientation": "landscape", "playfield_rotation": "180"}), encoding="utf-8")
        topo.apply_consumers(self.roles())
        fe = topo.VPINFE.read_text(encoding="utf-8")
        self.assertIn("cabmode = true\n", fe)
        self.assertIn("tableorientation = landscape\n", fe)
        self.assertIn("tablerotation = 0\n", fe, "VPinFE recoit toujours 0 (rotation physique par xrandr)")
        self.assertIn("tablescreenid = 0\n", fe); self.assertIn("bgscreenid = 1\n", fe); self.assertIn("fulldmdscreenid = 2\n", fe)
        self.assertIn("[Autre]\nk = v", fe, "le reste du fichier est conserve")
        self.assertIn("playfield_rotation = 180", fe); self.assertIn("managed_by = PinCabOS topology", fe)
        self.assertIn("playfield_name = HDMI-0", fe); self.assertIn("fulldmd_name = DP-2", fe)
        vpx = topo.VPX.read_text(encoding="utf-8")
        self.assertIn("BackglassOutput = 1", vpx); self.assertIn("ScoreViewOutput = 1", vpx); self.assertIn("cabinet_mode = true", vpx)

    def test_sans_screens_json_valeurs_par_defaut(self):
        topo.apply_consumers(self.roles())
        fe = topo.VPINFE.read_text(encoding="utf-8")
        self.assertIn("cabmode = true\n", fe); self.assertIn("tableorientation = landscape\n", fe); self.assertIn("playfield_rotation = 0", fe)

    def test_mode_bureau(self):
        topo.SCREENS.write_text(self.json.dumps({"cabinet_mode": False, "playfield_orientation": "portrait"}), encoding="utf-8")
        topo.apply_consumers(self.roles())
        fe = topo.VPINFE.read_text(encoding="utf-8")
        self.assertIn("cabmode = false\n", fe); self.assertIn("tableorientation = portrait\n", fe)


if __name__ == "__main__":
    unittest.main()
