"""PINCABOS_VULKAN_SEGFAULT_FALLBACK_V1 : bascule en OpenGL apres un segfault au demarrage."""
import unittest

from _charge import charger

bf = charger("opt/pincabos/bin/pincabos-table-backend-fallback", "pco_backend_fallback")

LOG_CRASH = """2026-09-03 22:49:48 INFO [1] [PinTable::LoadGameFromFilename@1419] LoadGameFromFilename /home/pinball/Tables/Last Action Hero (Data East 1993)/Last Action Hero (Data East 1993).vpx
2026-09-03 22:50:07 INFO [1] [Renderer::RenderStaticPrepass@1723] Performing prerendering of static parts.
"""
LOG_OK = LOG_CRASH + "2026-09-03 22:50:20 INFO [1] [Player::Player@832] Startup done\n"


class Decision(unittest.TestCase):
    def test_segfault_au_demarrage_bascule(self):
        ok, motif = bf.decision("", LOG_CRASH, "Last Action Hero (Data East 1993).vpx")
        self.assertTrue(ok, motif)

    def test_plantage_en_jeu_ne_bascule_pas(self):
        ok, motif = bf.decision("", LOG_OK, "Last Action Hero (Data East 1993).vpx")
        self.assertFalse(ok, motif)

    def test_backend_deja_choisi_respecte(self):
        ok, _ = bf.decision("[Player]\nGfxBackend = Vulkan\n", LOG_CRASH, "x.vpx")
        self.assertFalse(ok)

    def test_journal_muet_bascule_quand_meme(self):
        ok, _ = bf.decision("", "rien", "x.vpx")
        self.assertTrue(ok)
        ok, _ = bf.decision("", None, "x.vpx")
        self.assertTrue(ok)


class Ecriture(unittest.TestCase):
    def test_ajoute_player_et_compat_sans_toucher_le_reste(self):
        ini = "[TableOverride]\nViewCabMode = 0\n\n[Player]\nSomething = 1\n\n[ScoreView]\nScoreViewOutput = 1\n"
        out = bf.basculer(ini, "test")
        self.assertEqual(bf.section_value(out, "Player", "GfxBackend"), "OpenGL")
        self.assertEqual(bf.section_value(out, "Player", "Something"), "1")
        self.assertEqual(bf.section_value(out, "ScoreView", "ScoreViewOutput"), "1")
        self.assertEqual(bf.section_value(out, "PinCabOS.Compat", "GfxBackendFallback"), "test")

    def test_ini_vide(self):
        out = bf.basculer("", "test")
        self.assertEqual(bf.section_value(out, "Player", "GfxBackend"), "OpenGL")

    def test_idempotent(self):
        once = bf.basculer("", "test")
        self.assertEqual(bf.basculer(once, "test"), once)


if __name__ == "__main__":
    unittest.main()
