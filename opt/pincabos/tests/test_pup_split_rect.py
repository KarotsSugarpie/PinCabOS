"""Split PuP : detection de la zone sombre (le cadre DMD dessine par l'auteur du pack)
et choix du rectangle du ScoreView."""
import unittest

from _charge import charger

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None

sp = charger("opt/pincabos/bin/pincabos-pup-scoreview-split.py", "pco_split")


@unittest.skipIf(np is None, "numpy absent")
class ZoneSombre(unittest.TestCase):
    def image(self, w=480, h=270, fond=200):
        return np.full((h, w), fond, dtype=np.uint8)

    def test_trouve_le_cadre_dmd(self):
        img = self.image()
        img[150:200, 100:300] = 10          # 200 x 50 : ratio 4, plein
        x, y, w, h = sp.find_dark_zone(img)
        self.assertAlmostEqual(x, 100 / 480, places=3)
        self.assertAlmostEqual(y, 150 / 270, places=3)
        self.assertAlmostEqual(w, 200 / 480, places=3)
        self.assertAlmostEqual(h, 50 / 270, places=3)

    def test_ignore_les_formes_qui_ne_sont_pas_un_dmd(self):
        img = self.image()
        img[20:220, 40:80] = 5             # haut et etroit : pas un DMD
        self.assertIsNone(sp.find_dark_zone(img))
        img = self.image()
        img[:, :] = 5                       # image entierement noire
        self.assertIsNone(sp.find_dark_zone(img))

    def test_prefere_la_plus_grande_zone(self):
        img = self.image()
        img[30:50, 20:100] = 5              # petit cadre 80 x 20
        img[150:210, 100:340] = 5           # grand cadre 240 x 60
        x, y, w, h = sp.find_dark_zone(img)
        self.assertAlmostEqual(y, 150 / 270, places=3)
        self.assertAlmostEqual(w, 240 / 480, places=3)

    def test_zone_trop_petite_ignoree(self):
        img = self.image()
        img[100:104, 100:116] = 5           # 16 x 4 = negligeable
        self.assertIsNone(sp.find_dark_zone(img))


class CustomPos(unittest.TestCase):
    def test_lecture(self):
        self.assertEqual(sp._custom_pos(["1", "DMD", "", "", "0", "show", "", "5,14.4,13.6,71.2,68.6"]), (5, 14.4, 13.6, 71.2, 68.6))
        self.assertIsNone(sp._custom_pos(["1", "DMD", "", "", "0", "show", "", ""]))
        self.assertIsNone(sp._custom_pos(["1", "DMD"]))


if __name__ == "__main__":
    unittest.main()
