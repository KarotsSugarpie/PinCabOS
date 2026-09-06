"""PINCABOS_VOILE_VISUELS_V1 : le voile avant VPinFE prolonge le splash."""
import subprocess
import unittest
from pathlib import Path

from _charge import charger, RACINE

v = charger("usr/local/bin/pincabos-voile-ecrans", "pco_voile")

SCREENS = """{"playfield": {"name": "HDMI-0", "geometry": "3840x2160+0+0"},
 "backglass": {"name": "DP-2", "geometry": "1920x1080+5760+0"},
 "fulldmd": {"name": "DP-0", "geometry": "1920x1080+3840+0"}, "topper": {"name": "", "geometry": ""}}"""


class Voile(unittest.TestCase):
    def test_geometries_avec_role(self):
        self.assertEqual(v.geometries(SCREENS), [("playfield", 0, 0, 3840, 2160), ("backglass", 5760, 0, 1920, 1080), ("fulldmd", 3840, 0, 1920, 1080)])
        self.assertEqual(v.geometries("pas du json"), [])
        self.assertEqual(v.geometries(""), [])

    def test_genre_et_rotation(self):
        self.assertEqual(v.genre_visuel("playfield", 3840, 2160), ("portrait", 270))   # dalle paysage : haut de table a gauche
        self.assertEqual(v.genre_visuel("playfield", 2160, 3840), ("portrait", 0))     # dalle tournee par xrandr
        self.assertEqual(v.genre_visuel("backglass", 1920, 1080), ("paysage", 0))
        self.assertEqual(v.genre_visuel("fulldmd", 1080, 1920), ("portrait", 0))

    def test_bgrx(self):
        # 2 x 1 pixels RGB : rouge, vert ; rowstride avec un octet de bourrage
        out = v.bgrx(bytes([255, 0, 0, 0, 255, 0, 9]), 2, 1, 7, 3)
        self.assertEqual(bytes(out), bytes([0, 0, 255, 0, 0, 255, 0, 0]))
        out = v.bgrx(bytes([1, 2, 3, 4, 5, 6, 7, 8]), 1, 2, 4, 4)         # RGBA, deux lignes
        self.assertEqual(bytes(out), bytes([3, 2, 1, 0, 7, 6, 5, 0]))

    def test_sources(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            for n in ("paysage0.png", "paysage1.jpg", "portrait0.png", "grub0.jpg", "paysage9.txt"):
                Path(d, n).write_bytes(b"x")
            self.assertEqual([Path(p).name for p in v.sources("paysage", d)], ["paysage0.png", "paysage1.jpg"])
            self.assertEqual([Path(p).name for p in v.sources("portrait", d)], ["portrait0.png"])

    def test_unite_et_syntaxe(self):
        self.assertEqual(subprocess.run(["python3", "-m", "py_compile", str(Path(RACINE) / "usr/local/bin/pincabos-voile-ecrans")]).returncode, 0)
        u = (Path(RACINE) / "etc/systemd/system/pincabos-voile-ecrans.service").read_text(encoding="utf-8")
        self.assertIn("ExecStart=/usr/local/bin/pincabos-voile-ecrans --delai 3.5 --max 40", u)
        self.assertIn("Before=pincabos-vpinfe.service", u)


if __name__ == "__main__":
    unittest.main()
