"""PINCABOS_SAMPLE_B2S_V1 : B2S generique des tables de demonstration."""
import subprocess
import unittest
from pathlib import Path

from _charge import charger, RACINE

b2s = charger("opt/pincabos/tools/pincabos-sample-b2s.py", "pco_sample_b2s")


class B2S(unittest.TestCase):
    def test_xml(self):
        t = b2s.xml_b2s('PinCabOS "Calibration" <Nudge>', "Qkc=", "RE1E", "VEg=")
        self.assertTrue(t.startswith('<DirectB2SData Version="1.26">'))
        self.assertIn('<Name Value="PinCabOS &quot;Calibration&quot; &lt;Nudge&gt;" />', t)
        self.assertIn('<TableType Value="3" />', t)
        self.assertIn('<DMDType Value="3" />', t)
        self.assertIn('<BackglassImage Value="Qkc=" FileName="pincabos-backglass.png" />', t)
        self.assertIn('<DMDImage Value="RE1E" FileName="pincabos-dmd.png" />', t)
        self.assertIn('<ThumbnailImage Value="VEg=" />', t)
        self.assertTrue(t.rstrip().endswith("</DirectB2SData>"))
        import xml.etree.ElementTree as ET
        racine = ET.fromstring(t)
        self.assertEqual(racine.tag, "DirectB2SData")
        self.assertEqual(racine.find("Images/BackglassImage").get("Value"), "Qkc=")

    def test_visuel_stable_par_cle(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            g = Path(d)
            for n in ("paysage0.png", "paysage1.jpg", "paysage2.jpg", "portrait0.png"):
                (g / n).write_bytes(b"x")
            a, b = b2s.visuel_pour("nudge", g), b2s.visuel_pour("nudge", g)
            self.assertEqual(a, b)
            self.assertTrue(a.name.startswith("paysage"))
            self.assertIsNone(b2s.visuel_pour("nudge", g / "vide"))

    def test_appel_par_les_tables_de_demonstration(self):
        s = (Path(RACINE) / "usr/local/sbin/pincabos-sample-tables").read_text(encoding="utf-8")
        self.assertIn('B2S_TOOL="/opt/pincabos/tools/pincabos-sample-b2s.py"', s)
        self.assertIn('python3 "$B2S_TOOL" --vpx "$dest/$name.vpx" --key "$key"', s)
        self.assertEqual(subprocess.run(["bash", "-n", str(Path(RACINE) / "usr/local/sbin/pincabos-sample-tables")]).returncode, 0)
        self.assertTrue((Path(RACINE) / "opt/pincabos/web/static/pincabos-assets/vpx-wordmark.png").is_file())
        self.assertTrue((Path(RACINE) / "opt/pincabos/web/static/pincabos-logo.png").is_file())


if __name__ == "__main__":
    unittest.main()
