"""pincabos_vpx_input : mapping des boutons VPX, section [Input] (PINCABOS_VPX_INPUT_V1)."""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from _charge import charger

m = charger("opt/pincabos/tools/pincabos_vpx_input.py", "pco_vpx_input")

REPO = Path(__file__).resolve().parents[3]
REF_INI = REPO / "opt/pincabos/templates/home/.local/share/VPinballX/10.8/VPinballX.ini"
DUDES = "SDLJoy_0300a1eb8a2e00006f10000011010000_1"


def pinscape(path="/dev/input/event7"):
    """KL25Z Pinscape : 32 boutons joystick (16 BTN_JOYSTICK + 16 TRIGGER_HAPPY),
    6 axes, un chapeau numerique, plus un bit clavier exotique < BTN_JOYSTICK."""
    keys = list(range(0x120, 0x130)) + list(range(0x2C0, 0x2D0)) + [0x100]
    axes = {0: (0, -32767, 32767), 1: (0, -32767, 32767), 2: (-32767, -32767, 32767),
            3: (0, -32767, 32767), 4: (0, -32767, 32767), 5: (0, -32767, 32767),
            0x10: (0, -1, 1), 0x11: (0, -1, 1)}
    return m.EvdevDevice.fake(path, "mjrnet Pinscape Controller", (3, 0x1209, 0xEAEA, 0x0100), keys, axes)


class Format(unittest.TestCase):
    def test_aller_retour_sur_les_chaines_de_vpx(self):
        for s in ["Key;225 | %s;514;o;-0.300000" % DUDES, "Key;226 & Key;30", "Key;41", "%s;258" % DUDES, ""]:
            self.assertEqual(m.normalize_mapping(s), s)

    def test_chaines_invalides(self):
        for s in ["Key", "Key;abc", "Key;225;o", "Key;225;z;0.5", "Key;70000"]:
            with self.assertRaises(ValueError):
                m.parse_mapping(s)

    def test_libelles(self):
        names = {DUDES: "DudesCab #1"}
        self.assertEqual(m.mapping_label("Key;225", names), "Clavier : Shift gauche")
        self.assertEqual(m.mapping_label("%s;3" % DUDES, names), "DudesCab #1 : bouton 3")
        self.assertEqual(m.mapping_label("%s;258" % DUDES, names), "DudesCab #1 : chapeau 0 haut")
        self.assertIn("axe 2 >= -0.30", m.mapping_label("%s;514;o;-0.300000" % DUDES, names))
        self.assertEqual(m.mapping_label("", names), "non mappé")
        self.assertIn("invalide", m.mapping_label("n'importe quoi", names))

    def test_fusion_remplace_le_meme_type_et_garde_l_autre(self):
        cur = "Key;225 | %s;514;o;-0.300000" % DUDES
        self.assertEqual(m.merge_binding(cur, m.Binding("SDLJoy_X_1", 3)), "Key;225 | SDLJoy_X_1;3")
        self.assertEqual(m.merge_binding(cur, m.Binding("Key", 30)), "%s;514;o;-0.300000 | Key;30" % DUDES)
        once = m.merge_binding(cur, m.Binding("SDLJoy_X_1", 3))
        self.assertEqual(m.merge_binding(once, m.Binding("SDLJoy_X_1", 3)), once, "idempotent")


class Sdl(unittest.TestCase):
    def test_guid_identique_a_celui_que_vpx_a_ecrit_pour_la_dudescab(self):
        self.assertEqual(m.sdl_guid(3, 0x2E8A, 0x106F, 0x0111, "L'atelier d'Arnoz DudesCab"),
                         "0300a1eb8a2e00006f10000011010000")

    def test_scancodes_evdev(self):
        self.assertEqual(m.EVDEV_TO_SCANCODE[42], 225)   # KEY_LEFTSHIFT
        self.assertEqual(m.EVDEV_TO_SCANCODE[54], 229)   # KEY_RIGHTSHIFT
        self.assertEqual(m.EVDEV_TO_SCANCODE[2], 30)     # KEY_1
        self.assertEqual(m.EVDEV_TO_SCANCODE[28], 40)    # KEY_ENTER
        self.assertEqual(m.EVDEV_TO_SCANCODE[1], 41)     # KEY_ESC
        self.assertEqual(m.EVDEV_TO_SCANCODE[88], 69)    # KEY_F12
        self.assertEqual(m.scancode_label(225), "Shift gauche")
        self.assertEqual(m.scancode_label(4), "A")

    def test_ordre_des_boutons_comme_sdl_linux(self):
        dev = pinscape()
        self.assertTrue(dev.is_joystick)
        self.assertEqual(dev.sdl_button_index(0x120), 0)
        self.assertEqual(dev.sdl_button_index(0x12F), 15)
        self.assertEqual(dev.sdl_button_index(0x2C0), 16)
        self.assertEqual(dev.sdl_button_index(0x100), 32, "les bits sous BTN_JOYSTICK passent en dernier")
        self.assertEqual(len(dev.button_order()), 33)

    def test_axes_sans_le_chapeau_numerique(self):
        dev = pinscape()
        self.assertEqual(dev.digital_hats(), {0})
        self.assertEqual(dev.axis_order(), [0, 1, 2, 3, 4, 5])
        self.assertEqual(dev.sdl_axis_index(2), 2)

    def test_numerotation_vpx_des_joysticks(self):
        a = pinscape("/dev/input/event5")
        b = pinscape("/dev/input/event9")
        kb = m.EvdevDevice.fake("/dev/input/event3", "AT Keyboard", (0x11, 1, 1, 0xAB41), [1, 2, 28, 42])
        ids = m.joystick_setting_ids([b, kb, a])
        self.assertNotIn(kb.path, ids)
        self.assertEqual(ids[a.path][0], "SDLJoy_%s_1" % a.guid)
        self.assertEqual(ids[b.path][0], "SDLJoy_%s_2" % b.guid)
        self.assertEqual(ids[a.path][1], "mjrnet Pinscape Controller #1")
        self.assertEqual(ids[b.path][1], "mjrnet Pinscape Controller #2")


class Evenements(unittest.TestCase):
    def test_bouton_joystick(self):
        dev = pinscape()
        b = m.event_to_binding(dev, "SDLJoy_G_1", m.EV_KEY, 0x121, 1)
        self.assertEqual(b.to_vpx(), "SDLJoy_G_1;1")
        self.assertIsNone(m.event_to_binding(dev, "SDLJoy_G_1", m.EV_KEY, 0x121, 0), "relachement ignore")

    def test_touche_clavier(self):
        kb = m.EvdevDevice.fake("/dev/input/event3", "AT Keyboard", (0x11, 1, 1, 0xAB41), [1, 2, 28, 42])
        self.assertFalse(kb.is_joystick)
        self.assertEqual(m.event_to_binding(kb, "", m.EV_KEY, 42, 1).to_vpx(), "Key;225")
        self.assertIsNone(m.event_to_binding(kb, "", m.EV_KEY, 0x2FE, 1), "code sans scancode")

    def test_chapeau_et_axe_en_bouton(self):
        dev = pinscape()
        self.assertEqual(m.event_to_binding(dev, "J", m.EV_ABS, 0x11, -1).to_vpx(), "J;258")  # haut
        self.assertEqual(m.event_to_binding(dev, "J", m.EV_ABS, 0x10, 1).to_vpx(), "J;257")   # droite
        rest = {2: -1.0}
        self.assertIsNone(m.event_to_binding(dev, "J", m.EV_ABS, 2, -20000, rest), "petit mouvement")
        b = m.event_to_binding(dev, "J", m.EV_ABS, 2, 32767, rest)
        self.assertEqual(b.to_vpx(), "J;514", "seuil 0 non reverse : VPX omet aussi le suffixe")
        b = m.event_to_binding(dev, "J", m.EV_ABS, 0, -32767, {0: 0.0})
        self.assertEqual(b.to_vpx(), "J;512;x;-0.500000")


class Ini(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.ini = Path(self.tmp) / "VPinballX.ini"
        shutil.copy(REF_INI, self.ini)
        self.backups = Path(self.tmp) / "backups"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_lecture_de_l_ini_de_reference(self):
        ini = m.VpxIni(self.ini)
        self.assertEqual(ini.input_mappings()["LeftFlipper"], "Key;225 | %s;514;o;-0.300000" % DUDES)
        self.assertEqual(ini.input_devices(), ["Key", DUDES])
        self.assertEqual(ini.device_names()[DUDES], "L'atelier d'Arnoz DudesCab #1")

    def test_ecriture_en_place_sans_toucher_au_reste(self):
        before = self.ini.read_text().splitlines()
        pin = "SDLJoy_0300abcd0912000000ea000000010000_1"
        res = m.write_mappings({"LeftFlipper": "Key;225 | %s;1" % pin, "Start": "%s;5" % pin}, path=self.ini, backup=False, devices=[])
        after = self.ini.read_text().splitlines()
        ini = m.VpxIni(self.ini)
        self.assertEqual(ini.input_mappings()["LeftFlipper"], "Key;225 | %s;1" % pin)
        self.assertEqual(ini.input_devices(), ["Key", DUDES, pin])
        self.assertEqual(ini.get("Input", "Device.%s.Type" % pin), "2")
        self.assertEqual(res["purged"], 36, "l'ini de reference contient le bloc DIK de l'ancien Map Commander")
        self.assertEqual(len(after), len(before) + 1 - 36, "une seule ligne ajoutee (Device.<id>.Type), bloc mort retire")
        self.assertNotIn("LeftFlipperKey", self.ini.read_text())
        idx_b = next(i for i, l in enumerate(before) if l.startswith("Mapping.Start "))
        idx_a = next(i for i, l in enumerate(after) if l.startswith("Mapping.Start "))
        self.assertEqual(idx_a, idx_b)
        ref = m.VpxIni(REF_INI)
        ref.purge_legacy()
        outside_b = [l for l in ref.lines if not l.startswith(("Mapping.", "Devices", "Device."))]
        outside_a = [l for l in after if not l.startswith(("Mapping.", "Devices", "Device."))]
        self.assertEqual(outside_a, outside_b, "hors [Input] et bloc mort, rien ne bouge")
        # idempotent
        m.write_mappings({"LeftFlipper": "Key;225 | %s;1" % pin, "Start": "%s;5" % pin}, path=self.ini, backup=False, devices=[])
        self.assertEqual(self.ini.read_text().splitlines(), after)

    def test_valeur_vide_demappe_et_defauts(self):
        m.write_mappings({"Custom1": ""}, path=self.ini, backup=False, devices=[])
        self.assertEqual(m.VpxIni(self.ini).input_mappings()["Custom1"], "")
        m.write_mappings(dict(m.ACTION_DEFAULTS), path=self.ini, backup=False, devices=[])
        self.assertEqual(m.VpxIni(self.ini).input_mappings()["LeftFlipper"], "Key;225")

    def test_action_inconnue_et_mapping_invalide_refuses(self):
        with self.assertRaises(ValueError):
            m.write_mappings({"Bidule": "Key;1"}, path=self.ini, backup=False, devices=[])
        with self.assertRaises(ValueError):
            m.write_mappings({"Start": "Key"}, path=self.ini, backup=False, devices=[])
        self.assertEqual(self.ini.read_text(), REF_INI.read_text(), "rien n'est ecrit en cas d'erreur")

    def test_purge_des_anciennes_cles_map_commander(self):
        text = self.ini.read_text() + "\n[Keyboard]\n; Modifié 2026-07-02 par PinCabOS fonction(Inputs Commander Keyboard)\nLeftFlipperKey = 42\nRightFlipperKey = 54\nStartGameKey = 2\n"
        self.ini.write_text(text)
        ini = m.VpxIni(self.ini)
        self.assertEqual(ini.purge_legacy(), 36 + 4)
        self.assertNotIn("LeftFlipperKey", ini.text())
        self.assertNotIn("Inputs Commander Keyboard", ini.text())
        self.assertIsNotNone(ini.section_bounds("Keyboard"), "la section garde ce que d'autres fonctions y ont ecrit")
        self.assertIn("VPX Ball / Cabinet", ini.text())
        self.assertIn("PBWEnabled", ini.text(), "les cles nudge de [Player] restent")
        self.assertIsNotNone(ini.get("Player", "PBWEnabled"))

    def test_purge_ne_touche_pas_aux_cles_historiques_de_vpx(self):
        self.ini.write_text("[Player]\nPauseKey = 25\nLockbarKey = 56\nJoyCustom1Key = 22\n\n[Keyboard]\nStartGameKey = 2\n")
        ini = m.VpxIni(self.ini)
        self.assertEqual(ini.purge_legacy(), 2, "cle isolee de [Keyboard] + section vide")
        self.assertEqual(ini.get("Player", "PauseKey"), "25")
        self.assertIsNone(ini.section_bounds("Keyboard"))

    def test_section_input_creee_si_absente(self):
        self.ini.write_text("[Player]\nPBWEnabled = 0\n")
        m.write_mappings({"Start": "Key;30"}, path=self.ini, backup=False, devices=[])
        ini = m.VpxIni(self.ini)
        self.assertEqual(ini.get("Input", "Mapping.Start"), "Key;30")
        self.assertEqual(ini.input_devices(), ["Key"])
        self.assertEqual(ini.get("Player", "PBWEnabled"), "0")

    def test_sauvegarde_avant_ecriture(self):
        ini = m.VpxIni(self.ini)
        ini.set_mapping("Start", "Key;30")
        backup = ini.save(backup=True, backup_dir=self.backups)
        self.assertTrue(Path(backup).exists())
        self.assertEqual(Path(backup).read_text(), REF_INI.read_text())

    def test_chemin_de_l_ini(self):
        old_pref, old_legacy = m.PREF_INI, m.LEGACY_INI
        try:
            m.PREF_INI = Path(self.tmp) / "absent" / "VPinballX.ini"
            m.LEGACY_INI = self.ini
            self.assertEqual(m.ini_path(), self.ini)
            m.PREF_INI = self.ini
            self.assertEqual(m.ini_path(), self.ini)
        finally:
            m.PREF_INI, m.LEGACY_INI = old_pref, old_legacy


class EtatCourant(unittest.TestCase):
    def test_etat_pour_la_page(self):
        state = m.current_state(path=REF_INI, devices=[pinscape()])
        actions = {a["action"]: a for a in state["actions"]}
        self.assertTrue(actions["LeftFlipper"]["present"])
        self.assertIn("DudesCab #1", actions["LeftFlipper"]["decoded"])
        self.assertEqual(len(state["joysticks"]), 1)
        self.assertEqual(state["joysticks"][0]["name"], "mjrnet Pinscape Controller #1")
        self.assertNotIn(state["joysticks"][0]["id"], state["declared"])


class Vpinfe(unittest.TestCase):
    """Le même appui doit naviguer dans VPinFE (vpinfe.ini [Input] joy*/key*)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.ini = Path(self.tmp) / "vpinfe.ini"
        shutil.copy(REPO / "opt/pincabos/templates/home/.config/vpinfe/vpinfe.ini", self.ini)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_index_joydev_egal_sdl_sans_touches_basses(self):
        dev = pinscape()
        sid = m.joystick_setting_ids([dev])[dev.path][0]
        self.assertEqual(m.vpinfe_button_index(m.Binding(sid, 1), [dev]), "1")
        self.assertEqual(m.vpinfe_button_index(m.Binding(sid, 16), [dev]), "16", "TRIGGER_HAPPY suit les 16 premiers")
        self.assertEqual(m.vpinfe_button_index(m.Binding(sid, 32), [dev]), "32", "BTN_MISC (0x100) : vu par joydev, en dernier comme SDL")
        low = m.EvdevDevice.fake("/dev/input/event8", "Bidule", (3, 0x1234, 0x0001, 1), list(range(0x120, 0x124)) + [30], {0: (0, -1, 1), 1: (0, -1, 1)})
        sid2 = m.joystick_setting_ids([low])[low.path][0]
        self.assertEqual(low.sdl_button_index(30), 4)
        self.assertEqual(m.vpinfe_button_index(m.Binding(sid2, 4), [low]), "", "touche < BTN_MISC : SDL la numerote, joydev ne la voit pas")
        self.assertEqual(m.vpinfe_button_index(m.Binding("SDLJoy_inconnu_1", 4), [dev]), "4", "peripherique absent : index SDL conserve")
        self.assertEqual(m.vpinfe_button_index(m.Binding("Key", 225), [dev]), "")

    def test_politique_par_defaut(self):
        dev = pinscape()
        sid = m.joystick_setting_ids([dev])[dev.path][0]
        mappings = dict(m.ACTION_DEFAULTS)
        mappings["LeftFlipper"] = "Key;225 | %s;1" % sid
        mappings["RightFlipper"] = "Key;229 | %s;2" % sid
        mappings["Start"] = "%s;5" % sid
        mappings["ExitGame"] = "Key;41 | %s;9" % sid
        v = m.vpinfe_values(mappings, devices=[dev])
        self.assertEqual(v["left"]["joy"], "1")
        self.assertEqual(v["left"]["keys"], "ArrowLeft,ShiftLeft", "defauts VPinFE conserves, doublon evite")
        self.assertEqual(v["right"]["joy"], "2")
        self.assertEqual(v["select"]["joy"], "5")
        self.assertEqual(v["select"]["keys"], "Enter")
        self.assertEqual(v["exit"]["joy"], "9")
        self.assertEqual(v["exit"]["keys"], "Escape,q")
        self.assertEqual(v["menu"]["action"], "LaunchBall")
        self.assertEqual(v["menu"]["keys"], "m,Enter", "Entree (LaunchBall) s'ajoute au defaut")
        self.assertEqual(v["up"]["joy"], "", "Custom1 non mappe")

    def test_politique_personnalisee_et_notes(self):
        mappings = {"LeftMagna": "SDLJoy_X_1;514;o;-0.300000", "Custom1": "Key;226 & Key;30"}
        v = m.vpinfe_values(mappings, {"menu": "LeftMagna", "back": "Custom1", "left": ""})
        self.assertEqual(v["menu"]["joy"], "")
        self.assertIn("axe/chapeau", v["menu"]["notes"][0])
        self.assertIn("combinaison", v["back"]["notes"][0])
        self.assertEqual(v["left"]["action"], "")
        self.assertEqual(v["left"]["keys"], "ArrowLeft,ShiftLeft")

    def test_ecriture_vpinfe_ini(self):
        v = m.vpinfe_values({"LeftFlipper": "Key;225 | SDLJoy_X_1;1", "Start": "SDLJoy_X_1;5"}, devices=[])
        m.write_vpinfe(v, path=self.ini, backup=False)
        cur = m.vpinfe_current(self.ini)
        self.assertEqual(cur["left"], {"joy": "1", "keys": "ArrowLeft,ShiftLeft"})
        self.assertEqual(cur["select"], {"joy": "5", "keys": "Enter"})
        text = self.ini.read_text()
        self.assertIn("[Displays]", text)
        self.assertIn("[PinCabOs.FullDMD]", text, "les autres sections restent")
        self.assertEqual(text.count("joyleft ="), 1)
        # idempotent
        m.write_vpinfe(v, path=self.ini, backup=False)
        self.assertEqual(self.ini.read_text(), text)

    def test_noms_dom(self):
        self.assertEqual(m.SCANCODE_TO_DOM[225], "ShiftLeft")
        self.assertEqual(m.SCANCODE_TO_DOM[30], "Digit1")
        self.assertEqual(m.SCANCODE_TO_DOM[4], "KeyA")
        self.assertEqual(m.SCANCODE_TO_DOM[69], "F12")


if __name__ == "__main__":
    unittest.main()
