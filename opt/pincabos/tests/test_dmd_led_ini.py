"""DMD LED reel (ZeDMD / PIN2DMD) : ce que l'outil ecrit dans les INI de VPX
et de VPinFE pour chaque mode, et ce qu'il refuse."""
import json
import os
import tempfile
import unittest

from _charge import charger

z = charger("opt/pincabos/tools/pincabos-zedmd", "pco_zedmd")

VPX_INI = """[Plugin.B2SLegacy]
Enable = 1

[Plugin.DMDUtil]
; Enable: Enable DMDUtil plugin [Default: 0]
Enable =
ZeDMD =
PIN2DMD =
ZeDMDDevice =
Pixelcade =

[Plugin.FlexDMD]
Enable = 1
"""


def cfg(**k):
    base = {"mode": "off", "device": "", "wifi_addr": "", "brightness": -1, "targets": "game"}
    base.update(k)
    return base


class LectureEcritureIni(unittest.TestCase):
    def test_lecture_section(self):
        s = z.read_section(VPX_INI, "Plugin.DMDUtil")
        self.assertEqual(s["enable"], "")
        self.assertNotIn("Plugin.FlexDMD", s)

    def test_ecriture_conserve_commentaires_et_autres_sections(self):
        out = z.update_section(VPX_INI, "Plugin.DMDUtil", {"Enable": "1", "ZeDMDWiFiAddr": "10.0.0.5"})
        self.assertIn("; Enable: Enable DMDUtil plugin", out)
        self.assertIn("Enable = 1\nZeDMD =", out)
        self.assertIn("ZeDMDWiFiAddr = 10.0.0.5", out)
        self.assertIn("[Plugin.FlexDMD]\nEnable = 1", out)
        self.assertIn("[Plugin.B2SLegacy]\nEnable = 1", out)

    def test_cle_ajoutee_dans_la_bonne_section(self):
        out = z.update_section(VPX_INI, "Plugin.DMDUtil", {"ZeDMDBrightness": "7"})
        avant_flex = out.index("[Plugin.FlexDMD]")
        self.assertLess(out.index("ZeDMDBrightness = 7"), avant_flex)


class ValeursVpx(unittest.TestCase):
    def test_zedmd_usb(self):
        v = z.desired_vpx_values(cfg(mode="usb", device="/dev/ttyUSB0", brightness=8), {})
        self.assertEqual((v["Enable"], v["ZeDMD"], v["PIN2DMD"], v["ZeDMDWiFiEnabled"]), ("1", "1", "0", "0"))
        self.assertEqual(v["ZeDMDDevice"], "/dev/ttyUSB0")
        self.assertEqual(v["ZeDMDBrightness"], "8")

    def test_zedmd_wifi(self):
        v = z.desired_vpx_values(cfg(mode="wifi", wifi_addr="192.168.1.50"), {})
        self.assertEqual((v["ZeDMD"], v["ZeDMDWiFiEnabled"], v["ZeDMDWiFiAddr"]), ("1", "1", "192.168.1.50"))
        self.assertEqual(v["ZeDMDDevice"], "")

    def test_pin2dmd(self):
        v = z.desired_vpx_values(cfg(mode="pin2dmd"), {})
        self.assertEqual((v["Enable"], v["PIN2DMD"], v["ZeDMD"]), ("1", "1", "0"))

    def test_off_garde_le_plugin_si_pixelcade_actif(self):
        self.assertEqual(z.desired_vpx_values(cfg(), {"pixelcade": "1"})["Enable"], "1")
        self.assertEqual(z.desired_vpx_values(cfg(), {"pixelcade": "0"})["Enable"], "0")


class ValeursVpinfe(unittest.TestCase):
    def test_menu_seulement_pour_zedmd_avec_cible_both(self):
        self.assertEqual(z.desired_vpinfe_values(cfg(mode="wifi", wifi_addr="a", targets="both"))["enabled"], "true")
        self.assertEqual(z.desired_vpinfe_values(cfg(mode="usb", device="/dev/x", targets="game"))["enabled"], "false")
        self.assertEqual(z.desired_vpinfe_values(cfg(mode="pin2dmd", targets="both"))["enabled"], "false")


class Validation(unittest.TestCase):
    def test_refus(self):
        self.assertTrue(z.validate(cfg(mode="wifi")))
        self.assertTrue(z.validate(cfg(mode="usb", targets="both")))
        self.assertTrue(z.validate(cfg(mode="pin2dmd", targets="both")))
        self.assertTrue(z.validate(cfg(mode="usb", device="ttyUSB0")))

    def test_accepte(self):
        self.assertEqual(z.validate(cfg(mode="usb")), [])
        self.assertEqual(z.validate(cfg(mode="wifi", wifi_addr="zedmd.local", targets="both")), [])
        self.assertEqual(z.validate(cfg(mode="pin2dmd")), [])


class Normalisation(unittest.TestCase):
    def test_config_invalide_retombe_sur_des_valeurs_sures(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "zedmd.json")
            json.dump({"mode": "laser", "brightness": 99, "targets": "partout"}, open(p, "w"))
            ancien = z.CONFIG
            z.CONFIG = p
            try:
                c = z.load_config()
            finally:
                z.CONFIG = ancien
        self.assertEqual(c["mode"], "off")
        self.assertEqual(c["brightness"], -1)
        self.assertIn(c["targets"], ("game", "both"))


if __name__ == "__main__":
    unittest.main()
