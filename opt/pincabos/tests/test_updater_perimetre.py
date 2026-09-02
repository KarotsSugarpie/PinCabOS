"""Updater : perimetre d'une release (allowed) et alias du depot.

allowed() decide ce qu'une mise a jour a le droit d'ecraser sur un cabinet ;
une regression ici efface une donnee du joueur ou laisse passer un fichier
qui n'arrivera jamais. canonical_repo() est ce qui a debloque le parc
apres le transfert du depot.
"""
import unittest

from _charge import charger

up = charger("opt/pincabos/update/pincabos_updates.py", "pco_updater")


class Alias(unittest.TestCase):
    def test_ancien_nom_equivaut_au_nouveau(self):
        self.assertEqual(up.canonical_repo("KarotsSugarpie/PinCabOS"), "PinCabOS/PinCabOS")
        self.assertEqual(up.canonical_repo("PinCabOS/PinCabOS"), "PinCabOS/PinCabOS")

    def test_autre_depot_inchange(self):
        self.assertEqual(up.canonical_repo("Quelqun/Autre"), "Quelqun/Autre")


class PerimetreAutorise(unittest.TestCase):
    def test_fichiers_pincabos(self):
        for rel in (
            "opt/pincabos/web/app.py",
            "opt/pincabos/tools/backboard-menu/pincabos-backboard-menu.sh",
            "opt/pincabos/bin/pincabos-boot-video.sh",
            "usr/local/sbin/pincabos-kernel-maintenance",
            "usr/local/libexec/pincabos/pincabos-screen-hotplug",
            "usr/local/sbin/getpcos",
            "opt/pincabos/tools/pincabos_paths.py",
            "opt/pincabos/tools/pincabos-paths.sh",
            "home/pinball/.config/vpinfe/themes/PinCabOS/theme.js",
        ):
            self.assertTrue(up.allowed(rel), rel)

    def test_unites_systemd_trois_formes(self):
        for rel in (
            "etc/systemd/system/pincabos-vpinfe.service",
            "etc/systemd/system/pincabos-vpinfe.service.d/20-boot-video.conf",
            "etc/systemd/system/multi-user.target.wants/pincabos-sample-tables.path",
            "etc/systemd/system/timers.target.wants/pincabos-kernel-maintenance.timer",
        ):
            self.assertTrue(up.allowed(rel), rel)

    def test_surcharge_d_un_service_tiers_refusee(self):
        self.assertFalse(up.allowed("etc/systemd/system/lightdm.service.d/pincabos-x.conf"))
        self.assertFalse(up.allowed("etc/systemd/system/getty@tty1.service.d/override.conf"))
        self.assertFalse(up.allowed("etc/systemd/system/multi-user.target.wants/ssh.service"))

    def test_repertoires_sensibles_par_nom(self):
        self.assertTrue(up.allowed("etc/udev/rules.d/99-pincabos-pin2dmd.rules"))
        self.assertTrue(up.allowed("etc/sudoers.d/pincabos-zedmd"))
        self.assertTrue(up.allowed("etc/sudoers.d/91-pincabos-dashboard-admin"))
        self.assertTrue(up.allowed("etc/udev/rules.d/99-pincab-ledwiz.rules"))
        self.assertFalse(up.allowed("etc/sudoers.d/README"))
        self.assertFalse(up.allowed("etc/udev/rules.d/70-snap.core.rules"))
        self.assertFalse(up.allowed("etc/udev/rules.d/sub/99-pincabos.rules"))

    def test_donnees_du_joueur_et_etat_machine_jamais(self):
        for rel in (
            "etc/fstab", "etc/passwd", "etc/machine-id", "etc/shadow",
            "home/pinball/Tables/Attack from Mars (Bally 1995)/table.vpx",
            "home/pinball/.config/vpinfe/vpinfe.ini",
            "home/pinball/.pincabos/vpx/VPinballX.ini",
            "opt/pincabos/config/zedmd.json",
            "opt/pincabos/config/screens/screens.json",
            "opt/pincabos/media/boot-video.mp4",
            "var/lib/pincabos/updates/state.json",
        ):
            self.assertFalse(up.allowed(rel), rel)

    def test_chemins_dangereux(self):
        self.assertFalse(up.allowed(""))
        self.assertFalse(up.allowed("/opt/pincabos/web/app.py"))
        self.assertFalse(up.allowed("opt/pincabos/web/../../../etc/passwd"))
        self.assertFalse(up.allowed("opt/pincabos/web/.venv/lib/x.py"))
        self.assertFalse(up.allowed("opt/pincabos/web/__pycache__/app.cpython-312.pyc"))
        self.assertFalse(up.allowed("opt/pincabos/logs/x.log"))
        # nouveau prefixe = piege du parc (voir PINCABOS_UPDATE_SCOPE_PREFIX_TRAP)
        self.assertFalse(up.allowed("opt/pincabos/lib/pincabos_paths.py"))


class PrefixesEnAttente(unittest.TestCase):
    def test_le_client_accepte_le_constructeur_n_embarque_pas(self):
        rel = "opt/pincabos/launchers/pincabos-launch-core.sh"
        self.assertIn("opt/pincabos/launchers/", up.PENDING_PREFIXES)
        self.assertTrue(up.allowed(rel))
        self.assertFalse(up.allowed_for_build(rel))

    def test_le_reste_du_perimetre_est_inchange_pour_le_constructeur(self):
        self.assertTrue(up.allowed_for_build("opt/pincabos/tools/pincabos_paths.py"))
        self.assertFalse(up.allowed_for_build("etc/fstab"))
        self.assertFalse(up.allowed("opt/pincabos/launchers/__pycache__/x.pyc"))


if __name__ == "__main__":
    unittest.main()
