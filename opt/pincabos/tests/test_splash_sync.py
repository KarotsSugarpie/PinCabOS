"""Splash de demarrage par ecran (PINCABOS_SPLASH_FROM_SCREENS_V3).

Portrait sur le playfield, pre-tourne dans le sens de la dalle ; paysage sur
backglass, full DMD et topper ; surfaces ecartees dans l espace virtuel de
Plymouth. Aucune commande executee : un faux executeur enregistre.
"""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from _charge import charger, RACINE

ss = charger("usr/local/sbin/pincabos-splash-sync", "pco_splash_sync")

ECRANS_YANN = {"playfield": (3840, 2160), "backglass": (1920, 1080), "fulldmd": (1920, 1080)}


class SensDuJoueur(unittest.TestCase):
    def test_dalle_paysage_haut_de_table_a_gauche(self):
        # PINCABOS_SPLASH_SENS_JOUEUR_V1 : convention verifiee sur cab reel
        self.assertEqual(ss.rotation_effective(0), 270)
        self.assertEqual(ss.rotation_effective(180), 90)

    def test_dalle_tournee_par_x11(self):
        self.assertEqual(ss.rotation_effective(90), 90)
        self.assertEqual(ss.rotation_effective(270), 270)

    def test_resolution_physique(self):
        self.assertEqual(ss.resolution_physique((2160, 3840), 90), (3840, 2160))
        self.assertEqual(ss.resolution_physique((3840, 2160), 180), (3840, 2160))


class Images(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.theme = self.tmp / "theme"; self.theme.mkdir()
        (self.theme / "pincabos.png").write_bytes(b"HISTORIQUE")
        self.portrait = self.tmp / "portrait.png"; self.portrait.write_bytes(b"PORTRAIT")
        self.paysage = self.tmp / "paysage.png"; self.paysage.write_bytes(b"PAYSAGE")
        self.appels = []

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_ok(self, args, timeout=120):
        self.appels.append(list(args))
        Path(args[-1]).write_bytes(b"TOURNE")
        return 0, ""

    def test_portrait_pre_tourne_pour_le_playfield(self):
        r = ss.preparer_images(0, theme_dir=self.theme, run=self.run_ok, portrait=self.portrait, paysage=self.paysage)
        self.assertEqual((r["genre_playfield"], r["genre_autres"], r["rot"], r["pre_tourne"]), ("portrait", "paysage", 270, 1))
        self.assertEqual(len(self.appels), 1)
        cmd = self.appels[0]
        self.assertIn(cmd[0], ("ffmpeg", "convert"))
        if cmd[0] == "ffmpeg":
            self.assertIn("transpose=2", cmd)      # 270 = anti-horaire
        else:
            self.assertEqual(cmd[cmd.index("-rotate") + 1], "270")
        self.assertEqual((self.theme / ss.IMAGE_PLAYFIELD).read_bytes(), b"TOURNE")
        self.assertEqual((self.theme / ss.IMAGE_AUTRES).read_bytes(), b"PAYSAGE")

    def test_dalle_a_l_envers(self):
        r = ss.preparer_images(180, theme_dir=self.theme, run=self.run_ok, portrait=self.portrait, paysage=self.paysage)
        self.assertEqual(r["rot"], 90)
        self.assertTrue("transpose=1" in self.appels[0] or "90" in self.appels[0])

    def test_sans_visuels_karots_comportement_historique(self):
        r = ss.preparer_images(0, theme_dir=self.theme, run=self.run_ok,
                               portrait=self.tmp / "absent.png", paysage=self.tmp / "absent2.png")
        self.assertEqual((r["genre_playfield"], r["genre_autres"], r["rot"]), ("historique", "historique", 0))
        self.assertEqual(self.appels, [])   # rotation 0 : simple copie
        self.assertEqual((self.theme / ss.IMAGE_PLAYFIELD).read_bytes(), b"HISTORIQUE")
        r = ss.preparer_images(180, theme_dir=self.theme, run=self.run_ok,
                               portrait=self.tmp / "absent.png", paysage=self.tmp / "absent2.png")
        self.assertEqual(r["rot"], 180)    # l historique suit X11, jamais plus

    def test_outil_de_rotation_en_panne(self):
        def run_ko(args, timeout=120):
            return 1, "boom"
        r = ss.preparer_images(0, theme_dir=self.theme, run=run_ko, portrait=self.portrait, paysage=self.paysage)
        self.assertEqual(r["pre_tourne"], 0)
        self.assertEqual((self.theme / ss.IMAGE_PLAYFIELD).read_bytes(), b"PORTRAIT")

    def test_galerie_aleatoire(self):
        # portrait0.png + portrait1.jpg + paysage.jpg : tout devient PNG numerote, tire au sort au boot
        (self.tmp / "portrait0.png").write_bytes(b"P0"); (self.tmp / "portrait1.jpg").write_bytes(b"P1")
        (self.tmp / "paysage.jpg").write_bytes(b"L0"); self.portrait.unlink(); self.paysage.unlink()
        r = ss.preparer_images(0, theme_dir=self.theme, run=self.run_ok, portrait=self.tmp / "portrait.png", paysage=self.tmp / "paysage.png")
        self.assertEqual((r["n_playfield"], r["n_autres"], r["genre_playfield"], r["genre_autres"]), (2, 1, "portrait", "paysage"))
        self.assertEqual(sorted(p.name for p in self.theme.glob("pincabos-*-*.png")),
                         ["pincabos-autres-0.png", "pincabos-playfield-0.png", "pincabos-playfield-1.png"])
        # le jpg est converti (ffmpeg/convert) : trois commandes (2 rotations + 1 conversion)
        self.assertEqual(len(self.appels), 3)
        t = ss.theme(ECRANS_YANN, 0, dict(r, rot=270))
        self.assertIn("k_pf = Math.Int(Math.Random() * 2);", t)
        self.assertIn('if (k_pf == 1) img_pf = Image("pincabos-playfield-1.png");', t)
        self.assertIn("k_autres = Math.Int(Math.Random() * 1);", t)

    def test_purge_des_anciennes_images(self):
        (self.theme / "pincabos-playfield-7.png").write_bytes(b"vieux")
        ss.preparer_images(0, theme_dir=self.theme, run=self.run_ok, portrait=self.portrait, paysage=self.paysage)
        self.assertFalse((self.theme / "pincabos-playfield-7.png").exists())

    def test_commande_rotation(self):
        self.assertIsNone(ss.commande_rotation(Path("a"), Path("b"), 0))
        self.assertIsNone(ss.commande_rotation(Path("a"), Path("b"), 360))


class Theme(unittest.TestCase):
    IMAGES = {"genre_playfield": "portrait", "genre_autres": "paysage", "rot": 270, "pre_tourne": 1}

    def test_contenu(self):
        t = ss.theme(ECRANS_YANN, 0, self.IMAGES)
        self.assertIn("PINCABOS_SPLASH_FROM_SCREENS_V3", t)
        self.assertIn("rot = 270;", t)
        self.assertIn("pf_w = 3840;", t)
        self.assertIn('Image("pincabos-playfield-0.png")', t)
        self.assertIn('Image("pincabos-autres-0.png")', t)
        self.assertIn("Window.SetX(i, cx);", t)          # surfaces ecartees
        self.assertIn("fun placer()", t)
        self.assertIn("placer();\n    if (pf_place != 1) return;", t)   # re-applique a chaque rafraichissement
        self.assertIn("Window.GetWidth(i) * 2 == pf_w", t)   # HiDPI
        self.assertNotIn("Rotate(rot * PI / 180);\n    }\n  }", t)
        self.assertIn(f"bar_width = bw * {ss.BARRE['portrait']['w']};", t)
        self.assertIn(f"bh * {ss.BARRE['portrait']['y']};", t)

    def test_playfield_tourne_par_x11(self):
        images = dict(self.IMAGES, rot=90)
        t = ss.theme({"playfield": (2160, 3840), "backglass": (1920, 1080)}, 90, images)
        self.assertIn("pf_w = 3840;", t)   # dalle vue par Plymouth : native
        self.assertIn("pf_h = 2160;", t)
        self.assertIn("rot = 90;", t)

    def test_historique(self):
        images = {"genre_playfield": "historique", "genre_autres": "historique", "rot": 0, "pre_tourne": 1}
        t = ss.theme(ECRANS_YANN, 0, images)
        self.assertIn(f"bar_width = bw * {ss.BARRE['historique']['w']};", t)

    def test_accolades_equilibrees(self):
        t = ss.theme(ECRANS_YANN, 0, self.IMAGES)
        self.assertEqual(t.count("{"), t.count("}"))
        self.assertNotIn("{{", t)


class Perimetre(unittest.TestCase):
    def test_visuels_dans_le_perimetre_de_l_updater(self):
        src = (Path(RACINE) / "opt/pincabos/update/pincabos_updates.py").read_text(encoding="utf-8")
        self.assertIn("'opt/pincabos/media/splash/'", src)

    def test_sources_declarees(self):
        self.assertEqual(str(ss.PORTRAIT), "/opt/pincabos/media/splash/portrait.png")
        self.assertEqual(str(ss.PAYSAGE), "/opt/pincabos/media/splash/paysage.png")


if __name__ == "__main__":
    unittest.main()
