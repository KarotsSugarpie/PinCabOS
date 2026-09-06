"""Nettoyage (lot 13 du découpage) : plus de commentaires hérités des refontes, plus de code sans appelant."""
import re
import unittest
from pathlib import Path

from _charge import RACINE

R = Path(RACINE)
WEB = R / "opt/pincabos/web"
VERSIONS = ("_pincabos_vpinfe_status_payload", "pincabos_vpinfe_local_version", "pincabos_vpinfe_available_version",
            "pincabos_vpinball_local_version", "pincabos_vpinball_available_version", "pincabos_gpu_local_version",
            "pincabos_gpu_available_version", "pincabos_ubuntu_local_version", "pincabos_ubuntu_available_version")


def sources_web():
    return {p.name: p.read_text(encoding="utf-8") for p in WEB.glob("*.py")}


class Nettoyage(unittest.TestCase):
    def test_plus_de_commentaires_herites_dans_les_modules_web(self):
        for nom, texte in sources_web().items():
            self.assertNotIn("Moved to modular route file by PinCabOS refactor", texte, nom)
            self.assertNotIn("Removed obsolete duplicate route block", texte, nom)

    def test_marqueurs_de_section_encadrent_du_code(self):
        """Un marqueur START/BEGIN suivi directement (blancs et commentaires exclus) de son END n'encadre rien : retiré."""
        app = (WEB / "app.py").read_text(encoding="utf-8").split("\n")
        marqueur = re.compile(r"^# (=== .*(START|BEGIN|END) ===|PINCABOS_[A-Z0-9_]+_(BEGIN|END|START))\s*$")
        for i, l in enumerate(app):
            if marqueur.match(l) and ("START" in l or "BEGIN" in l):
                j = i + 1
                while j < len(app) and not app[j].strip() or (j < len(app) and app[j].lstrip().startswith("#") and not marqueur.match(app[j])):
                    j += 1
                if j < len(app) and marqueur.match(app[j]) and "END" in app[j]:
                    self.fail(f"marqueurs vides l.{i + 1}-{j + 1} : {l}")

    def test_helpers_de_versions_retires(self):
        for nom, texte in sources_web().items():
            for v in VERSIONS:
                self.assertNotRegex(texte, rf"\b{v}\b", (nom, v))

    def test_orphelins_usb_smb_retires(self):
        self.assertFalse((R / "usr/local/sbin/pincabos-usb-umount").exists())
        sud = (R / "etc/sudoers.d/pincabos-smb-mount").read_text(encoding="utf-8")
        self.assertNotIn("pincabos-usb-umount", sud)
        self.assertIn("/usr/local/sbin/pincabos-smb-umount *", sud, "la règle du démontage SMB reste")
        for nom, texte in sources_web().items():
            self.assertNotIn("pco_smb_mount_helper_command", texte, nom)
        # le démontage USB passe par pincabos-usb-disk, toujours sous sudoers
        self.assertIn("/usr/local/sbin/pincabos-usb-disk unmount *", (R / "etc/sudoers.d/pincabos-usb-disk").read_text(encoding="utf-8"))
        self.assertIn('USB_HELPER = "/usr/local/sbin/pincabos-usb-disk"', sources_web()["pincabos_webapp_disques.py"])

    def test_screens_layout_text_conserve_pour_la_premiere_execution(self):
        # lu dans les globals d'app.py par pincabos_webapp_firstrun : ce n'est pas du code mort
        self.assertNotIn("def screens_layout_text():", sources_web()["app.py"])
        self.assertIn("def screens_layout_text():", sources_web()["pincabos_webapp_firstrun.py"], "déplacée chez son seul consommateur")
        self.assertIn("screens_layout_text()", sources_web()["pincabos_webapp_firstrun.py"])


if __name__ == "__main__":
    unittest.main()
