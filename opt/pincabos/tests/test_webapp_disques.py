"""Gestion du stockage (lot 8 du découpage, PINCABOS_WEBAPP_MODULES_V1) : une seule vue par chemin.

Avant : trois couches se remplaçaient au démarrage (routes d'origine d'app.py, remplacements à chaud
par chemin, module externe PinCabOS-NtwkDRV). Après : `pincabos_webapp_disques.py` porte la vue qui
répondait réellement, et plus rien ne remplace de vue dans la table de l'application.
"""
import ast
import re
import unittest
from pathlib import Path

from _charge import RACINE

WEB = Path(RACINE) / "opt/pincabos/web"
APP = WEB / "app.py"
MOD = WEB / "pincabos_webapp_disques.py"
CHEMINS = {
    "/tools/external-disks": "tools_external_disks",
    "/tools/external-disks/smb/detect": "tools_external_disks_smb_detect",
    "/tools/external-disks/smb/mount": "tools_external_disks_smb_mount",
    "/tools/external-disks/smb/unmount": "tools_external_disks_smb_unmount",
    "/tools/external-disks/smb/disconnect": "tools_external_disks_smb_disconnect",
    "/tools/external-disks/usb/mount": "tools_external_disks_usb_mount",
    "/tools/external-disks/usb/unmount": "tools_external_disks_usb_unmount",
}


class UneVueParChemin(unittest.TestCase):
    def setUp(self):
        self.app = APP.read_text(encoding="utf-8")
        self.mod = MOD.read_text(encoding="utf-8")

    def test_chaque_chemin_a_exactement_une_route_dans_le_module(self):
        routes = re.findall(r'^@disques_bp\.route\("([^"]+)"[^\n]*\n(?:@[^\n]*\n)*def (\w+)\(', self.mod, re.M)
        self.assertEqual(dict(routes), CHEMINS)
        for chemin in CHEMINS:
            self.assertEqual(self.mod.count(f'route("{chemin}"'), 1, chemin)
            self.assertNotIn(f'route("{chemin}"', self.app, chemin)

    def test_plus_aucun_remplacement_de_vue_pour_le_stockage(self):
        for mot in ("_pincabos_replace_unmount_route", "pincabos_smb_mount_safe_view", "_pincabos_smb_mount_original",
                    "NtwkDRV", "ntwkdrv", "pincabos_tools_smb_disconnect_button_v1", "pincabos_tools_usb_unmount_alias",
                    "pincabos_tools_smb_unmount_alias"):
            self.assertNotIn(mot, self.app, mot)
        self.assertNotIn("view_functions[", self.mod)
        self.assertNotIn("_replace_or_add_route", self.mod)
        self.assertFalse((WEB / "PinCabOS-NtwkDRV.py").exists(), "le module externe est fondu dans pincabos_webapp_disques")
        for p in WEB.glob("*.py"):
            if p == MOD:  # son en-tête crédite l'origine du code
                continue
            self.assertNotIn("NtwkDRV", p.read_text(encoding="utf-8"), p.name)

    def test_montage_smb_garde_l_enveloppe_sure(self):
        # l'ancienne enveloppe interceptait toute exception et rendait une page lisible : conservée dans la vue elle-même
        i = self.mod.index("def tools_external_disks_smb_mount():")
        corps = self.mod[i:self.mod.index("\ndef ", i + 10)]
        self.assertIn("return _smb_mount_impl()", corps)
        self.assertIn("except Exception as exc:", corps)
        self.assertIn("Montage SMB échoué", corps)
        self.assertIn("/usr/local/sbin/pincabos-smb-mount", self.mod)

    def test_demontage_smb_sur_specialise(self):
        i = self.mod.index("def tools_external_disks_smb_unmount():")
        corps = self.mod[i:self.mod.index("\n\n\n", i)]
        self.assertIn("SMB_UMOUNT_HELPER", corps)
        self.assertIn('request.form.get("drive_name", "")', corps)
        self.assertIn(".cred", corps, "le mot de passe SMB ne reste pas après un démontage réussi")
        for mot in ("label", "form_key", "helper_path", "root_path"):
            self.assertNotRegex(corps, rf"\b{mot}\b")

    def test_usb_passe_par_le_helper_sudoers(self):
        self.assertIn('USB_HELPER = "/usr/local/sbin/pincabos-usb-disk"', self.mod)
        self.assertIn('_run(["/usr/bin/sudo", "-n", USB_HELPER, action, uuid], timeout=90)', self.mod)

    def test_lien_menu_commander_conserve(self):
        self.assertIn("@disques_bp.after_app_request\ndef pincabos_external_disks_menu_link(response):", self.mod)
        self.assertNotIn("pincabos_external_disks_menu_link", self.app)

    def test_module_sain(self):
        ast.parse(self.mod)
        self.assertIn("def register(app, page_fn):", self.mod)
        self.assertIn("app.register_blueprint(disques_bp)", self.mod)
        i_reg = self.app.index("pco_disques_routes.register(app, page)")
        self.assertLess(self.app.index("pco_import_routes.register(app, page)"), i_reg)
        self.assertLess(i_reg, self.app.index("pco_commander_routes.register(app, page)"))


if __name__ == "__main__":
    unittest.main()
