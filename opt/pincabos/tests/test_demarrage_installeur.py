"""ISO : un seul chemin de demarrage (PINCABOS_ISO_UN_SEUL_CHEMIN_V1).

Le menu GRUB ne propose que l'assistant graphique : pas de mode live, pas
d'installeur texte, pas de secours dessus. Si l'assistant ne s'affiche pas,
la panne est annoncee en clair (PINCABOS_INSTALLEUR_PANNE_FRANCHE_V1).
"""
import re
import subprocess
import unittest
from pathlib import Path

from _charge import RACINE

R = Path(RACINE)
ISO = R / "opt/pincabos/script/iso.sh"
ISO_LIVE = R / "opt/pincabos/script/iso-live.sh"
KIOSK = R / "etc/systemd/system/pincabos-gui-kiosk.service"
PANNE_SERVICE = R / "etc/systemd/system/pincabos-installer-failure.service"
PANNE = R / "usr/local/sbin/pincabos-installer-failure"
DISPATCH = R / "usr/local/sbin/pincabos-installer-dispatch"


def bloc_grub(script: Path, marqueur: str) -> str:
    """Le heredoc qui ecrit boot/grub/grub.cfg."""
    texte = script.read_text(encoding="utf-8")
    m = re.search(r"grub\.cfg\"? <<\s*'?" + marqueur + r"'?\n(.*?)\n" + marqueur + r"\n", texte, re.S)
    assert m, "bloc GRUB introuvable dans " + script.name
    return m.group(1)


def entrees(bloc: str):
    return re.findall(r'menuentry\s+"([^"]+)"', bloc)


class MenuGrub(unittest.TestCase):
    def test_iso_live_une_seule_entree(self):
        bloc = bloc_grub(ISO_LIVE, "GRUBCFG")
        self.assertEqual(entrees(bloc), ["Install PinCabOS"])
        self.assertIn("pincabos.installer=gui", bloc)
        self.assertIn("systemd.unit=pincabos-gui-install.target", bloc)

    def test_iso_classique_une_seule_entree(self):
        bloc = bloc_grub(ISO, "PINCABOS_GRUB")
        self.assertEqual(entrees(bloc), ["Install PinCabOS"])
        self.assertIn("pincabos.installer=gui", bloc)
        # la politique de boot d'iso.sh exige multi-user.target sur chaque entree
        self.assertIn("systemd.unit=multi-user.target", bloc)

    def test_ni_live_ni_texte_ni_secours(self):
        for script, marqueur in ((ISO_LIVE, "GRUBCFG"), (ISO, "PINCABOS_GRUB")):
            bloc = bloc_grub(script, marqueur)
            for interdit in ("installer=tui", "nomodeset", "pincabos.rescue", "Try ", "text", "safe", "rescue"):
                self.assertNotIn(interdit, bloc, script.name + " : " + interdit)

    def test_delai_court(self):
        for script, marqueur in ((ISO_LIVE, "GRUBCFG"), (ISO, "PINCABOS_GRUB")):
            bloc = bloc_grub(script, marqueur)
            m = re.search(r"set timeout=(\d+)", bloc)
            self.assertTrue(m and int(m.group(1)) <= 5, script.name + " : delai GRUB trop long")


class FondsGrub(unittest.TestCase):
    def test_galerie_tiree_par_l_horloge(self):
        # PINCABOS_GRUB_FONDS_ALEATOIRES_V1
        s = ISO_LIVE.read_text(encoding="utf-8")
        self.assertIn("opt/pincabos/media/splash/grub*.jpg", s)
        self.assertIn('echo "insmod datehook"', s)
        self.assertIn("SECOND", s)
        self.assertIn("insmod jpeg", s)
        self.assertIn("background_image /boot/grub/pincabos-grub.png", s)   # secours sans galerie

    def test_galerie_presente(self):
        fonds = sorted((R / "opt/pincabos/media/splash").glob("grub*.jpg"))
        self.assertGreaterEqual(len(fonds), 1)
        for f in fonds:
            # GRUB ne decode que le JPEG baseline : un JPEG progressif (SOF2) laisse le menu noir
            octets = f.read_bytes()
            self.assertIn(b"\xff\xc0", octets[:65536], f.name + " : pas de SOF0 (baseline)")
            self.assertNotIn(b"\xff\xc2", octets[:65536], f.name + " : JPEG progressif")


class PlusDeRepliTexte(unittest.TestCase):
    def test_fichiers_du_repli_absents(self):
        for rel in ("usr/local/sbin/pincabos-gui-fallback",
                    "etc/systemd/system/pincabos-tui-fallback.service"):
            self.assertFalse((R / rel).exists(), rel)

    def test_iso_ne_fabrique_plus_la_console(self):
        texte = ISO.read_text(encoding="utf-8")
        # iso.sh ne fabrique ni ne copie plus ces pieces (il ne fait que les effacer)
        self.assertNotIn("<<'PINCABOS_LIVE_CONSOLE'", texte)
        self.assertNotIn("<<'PINCBOS_DESKTOP'", texte)
        self.assertNotIn("install -m 755 /usr/local/sbin/pincabos-gui-fallback", texte)
        self.assertNotIn("cp /etc/systemd/system/pincabos-tui-fallback.service", texte)
        self.assertNotIn("ExecStart=/usr/local/sbin/pincabos-live-installer-console", texte)
        self.assertIn("install -m 755 /usr/local/sbin/pincabos-installer-failure", texte)

    def test_kiosque_relance_puis_panne_franche(self):
        unite = KIOSK.read_text(encoding="utf-8")
        self.assertNotIn("ExecStopPost", unite)
        self.assertIn("Restart=on-failure", unite)
        self.assertIn("StartLimitBurst=", unite)
        self.assertIn("OnFailure=pincabos-installer-failure.service", unite)

    def test_dispatch_sans_console(self):
        texte = DISPATCH.read_text(encoding="utf-8")
        self.assertNotIn("installer-console", texte)
        self.assertNotIn("installer=tui", texte)
        self.assertIn("exec /usr/local/sbin/pincabos-installer-failure", texte)

    def test_panne_franche(self):
        service = PANNE_SERVICE.read_text(encoding="utf-8")
        self.assertIn("TTYPath=/dev/tty1", service)
        self.assertIn("ExecStart=/usr/local/sbin/pincabos-installer-failure", service)
        texte = PANNE.read_text(encoding="utf-8")
        self.assertIn("systemctl reboot", texte)
        self.assertIn("installer-failure.log", texte)

    def test_syntaxe_shell(self):
        for f in (PANNE, DISPATCH):
            r = subprocess.run(["bash", "-n", str(f)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, f.name + " : " + r.stderr)


if __name__ == "__main__":
    unittest.main()
