"""pincabos_identity : le système s'appelle PinCabOS partout où un humain le lit (PINCABOS_IDENTITE_V1)."""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from _charge import charger, RACINE

m = charger("opt/pincabos/tools/pincabos_identity.py", "pco_identity")

OS_RELEASE_UBUNTU = '''PRETTY_NAME="Ubuntu 26.04.1 LTS"
NAME="Ubuntu"
VERSION_ID="26.04"
VERSION="26.04.1 LTS (Resolute Raccoon)"
VERSION_CODENAME=resolute
ID=ubuntu
ID_LIKE=debian
HOME_URL="https://www.ubuntu.com/"
SUPPORT_URL="https://help.ubuntu.com/"
BUG_REPORT_URL="https://bugs.launchpad.net/ubuntu/"
PRIVACY_POLICY_URL="https://www.ubuntu.com/legal/terms-and-policies/privacy-policy"
UBUNTU_CODENAME=resolute
LOGO=ubuntu-logo
'''
VERSION = {"version": "Alpha 3.60", "codename": "Stark"}
EFIBOOTMGR = """BootCurrent: 0000
Timeout: 1 seconds
BootOrder: 0000,0013,0003
Boot0000* Ubuntu\tHD(1,GPT,9cb0385d-1770-4dfe-be8f-6acef7171c20,0x800,0x113000)/\\EFI\\PINCABOS\\SHIMX64.EFI
Boot0001* UEFI: PXE IP4 Intel(R) Ethernet Connection (7) I219-V\tPciRoot(0x0)/Pci(0x1f,0x6)/MAC(04d4c4a865ed,0)/IPv4(0.0.0.0,0,DHCP,0.0.0.0,0.0.0.0,0.0.0.0)0000424f
Boot0003* Hard Drive\tBBS(HD,,0x0)0000474f
Boot0013* Windows Boot Manager\tHD(1,GPT,11111111-2222-3333-4444-555555555555,0x800,0x32000)/\\EFI\\Microsoft\\Boot\\bootmgfw.efi
"""


class OsRelease(unittest.TestCase):
    def test_reecriture(self):
        s = m.os_release_pincabos(OS_RELEASE_UBUNTU, VERSION)
        d = dict(m.parse_kv(s))
        self.assertEqual(d["NAME"], '"PinCabOS"')
        self.assertEqual(d["PRETTY_NAME"], '"PinCabOS Alpha 3.60 (Ubuntu 26.04.1 LTS)"')
        self.assertEqual(d["ID"], "ubuntu", "l'identifiant interne ne bouge pas : apt, ubuntu-drivers, dkms")
        self.assertEqual(d["ID_LIKE"], "debian")
        self.assertEqual(d["VERSION_CODENAME"], "resolute")
        self.assertEqual(d["VERSION_ID"], '"26.04"')
        self.assertEqual(d["HOME_URL"], '"https://pincabos.cc/"')
        self.assertEqual(d["PINCABOS_VERSION"], '"Alpha 3.60"')
        self.assertEqual(d["PINCABOS_CODENAME"], '"Stark"')
        self.assertEqual(d["PINCABOS_BASE"], '"Ubuntu 26.04.1 LTS"')
        self.assertNotIn("PRIVACY_POLICY_URL", d)
        self.assertEqual(s.splitlines()[0], 'PRETTY_NAME="PinCabOS Alpha 3.60 (Ubuntu 26.04.1 LTS)"')

    def test_idempotent_meme_depuis_un_fichier_deja_reecrit(self):
        une = m.os_release_pincabos(OS_RELEASE_UBUNTU, VERSION)
        deux = m.os_release_pincabos(une, VERSION)
        self.assertEqual(une, deux, "repartir d'un os-release PinCabOS ne double pas le libellé")
        self.assertNotIn("PinCabOS Alpha 3.60 (PinCabOS", deux)

    def test_sans_version(self):
        s = m.os_release_pincabos(OS_RELEASE_UBUNTU, {"version": "", "codename": ""})
        self.assertIn('PRETTY_NAME="PinCabOS (Ubuntu 26.04.1 LTS)"', s)

    def test_lsb_issue_grub(self):
        lsb = 'DISTRIB_ID=Ubuntu\nDISTRIB_RELEASE=26.04\nDISTRIB_CODENAME=resolute\nDISTRIB_DESCRIPTION="Ubuntu 26.04 LTS"\n'
        s = m.lsb_release_pincabos(lsb, VERSION, "Ubuntu 26.04.1 LTS")
        self.assertIn("DISTRIB_ID=Ubuntu\n", s, "DISTRIB_ID reste Ubuntu pour les scripts qui le testent")
        self.assertIn('DISTRIB_DESCRIPTION="PinCabOS Alpha 3.60 (Ubuntu 26.04.1 LTS)"', s)
        self.assertEqual(m.issue_pincabos(VERSION), "PinCabOS Alpha 3.60 \\n \\l\n\n")
        self.assertEqual(m.issue_net_pincabos(VERSION), "PinCabOS Alpha 3.60\n")
        g = 'GRUB_DEFAULT=0\nGRUB_TIMEOUT=0\nGRUB_DISTRIBUTOR=`( . /etc/os-release && echo ${NAME} )`\nGRUB_CMDLINE_LINUX=""\n'
        s = m.grub_default_pincabos(g)
        self.assertIn('GRUB_DISTRIBUTOR="PinCabOS"\n', s)
        self.assertNotIn("os-release", s)
        self.assertEqual(s.count("GRUB_DISTRIBUTOR"), 1)
        self.assertEqual(m.grub_default_pincabos(s), s, "idempotent")
        self.assertIn('GRUB_DISTRIBUTOR="PinCabOS"', m.grub_default_pincabos("GRUB_TIMEOUT=0\n"), "ligne ajoutée si absente")


class Uefi(unittest.TestCase):
    def test_lecture_des_entrees(self):
        e = m.entrees_efi(EFIBOOTMGR)
        self.assertEqual([x["entree"] for x in e], ["0000", "0013"])
        self.assertEqual(e[0], {"entree": "0000", "active": True, "libelle": "Ubuntu", "partition": 1,
                                "partuuid": "9cb0385d-1770-4dfe-be8f-6acef7171c20", "chargeur": "\\EFI\\PINCABOS\\SHIMX64.EFI"})
        self.assertEqual([x["entree"] for x in m.a_renommer(e)], ["0000"])
        self.assertEqual(m.deja_nommees(e), [])

    def test_renommage(self):
        appels = []
        apres = EFIBOOTMGR.replace("Boot0000* Ubuntu", "Boot0000* Ubuntu") + "Boot0014* PinCabOS\tHD(1,GPT,9cb0385d-1770-4dfe-be8f-6acef7171c20,0x800,0x113000)/\\EFI\\PINCABOS\\SHIMX64.EFI\n"

        def executer(cmd, **kw):
            appels.append(cmd)
            out = {("blkid",): "/dev/nvme1n1p1\n", ("lsblk", "-no", "PKNAME"): "nvme1n1\n", ("lsblk", "-no", "PARTN"): "1\n",
                   ("efibootmgr", "-v"): apres}
            for k, v in out.items():
                if tuple(cmd[:len(k)]) == k:
                    return type("R", (), {"returncode": 0, "stdout": v, "stderr": ""})()
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        e = m.entrees_efi(EFIBOOTMGR)[0]
        msg = m.renommer_entree_efi(e, executer)
        self.assertTrue(msg.startswith("GO:"), msg)
        creation = next(c for c in appels if c[:2] == ["efibootmgr", "-c"])
        self.assertEqual(creation, ["efibootmgr", "-c", "-d", "/dev/nvme1n1", "-p", "1", "-L", "PinCabOS", "-l", "\\EFI\\PINCABOS\\SHIMX64.EFI"])
        suppression = next(c for c in appels if c[:2] == ["efibootmgr", "-B"])
        self.assertEqual(suppression, ["efibootmgr", "-B", "-b", "0000"])
        self.assertLess(appels.index(creation), appels.index(suppression), "on cree avant de retirer")

    def test_pas_de_suppression_si_creation_ratee(self):
        appels = []

        def executer(cmd, **kw):
            appels.append(cmd)
            if cmd[0] == "blkid":
                return type("R", (), {"returncode": 0, "stdout": "/dev/sda1\n", "stderr": ""})()
            if cmd[:3] == ["lsblk", "-no", "PKNAME"]:
                return type("R", (), {"returncode": 0, "stdout": "sda\n", "stderr": ""})()
            if cmd[:3] == ["lsblk", "-no", "PARTN"]:
                return type("R", (), {"returncode": 0, "stdout": "1\n", "stderr": ""})()
            if cmd[:2] == ["efibootmgr", "-c"]:
                return type("R", (), {"returncode": 1, "stdout": "", "stderr": "Could not prepare Boot variable"})()
            return type("R", (), {"returncode": 0, "stdout": EFIBOOTMGR, "stderr": ""})()

        msg = m.renommer_entree_efi(m.entrees_efi(EFIBOOTMGR)[0], executer)
        self.assertTrue(msg.startswith("NOGO"), msg)
        self.assertFalse([c for c in appels if c[:2] == ["efibootmgr", "-B"]], "l'ancienne entree reste : le cab doit demarrer")

    def test_partition_introuvable(self):
        def executer(cmd, **kw):
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        msg = m.renommer_entree_efi(m.entrees_efi(EFIBOOTMGR)[0], executer)
        self.assertIn("introuvable", msg)


class Application(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "usr/lib").mkdir(parents=True)
        (self.root / "usr/lib/os-release").write_text(OS_RELEASE_UBUNTU, encoding="utf-8")
        (self.root / "etc/default").mkdir(parents=True)
        os.symlink("../usr/lib/os-release", self.root / "etc/os-release")
        (self.root / "etc/lsb-release").write_text('DISTRIB_ID=Ubuntu\nDISTRIB_DESCRIPTION="Ubuntu 26.04 LTS"\n', encoding="utf-8")
        (self.root / "etc/issue").write_text("Ubuntu 26.04.1 LTS \\n \\l\n\n", encoding="utf-8")
        (self.root / "etc/default/grub").write_text('GRUB_TIMEOUT=0\nGRUB_DISTRIBUTOR=`( . /etc/os-release && echo ${NAME} )`\n', encoding="utf-8")
        (self.root / "opt/pincabos/config").mkdir(parents=True)
        (self.root / "opt/pincabos/config/version.json").write_text(json.dumps({"name": "PinCabOS", "version": "Alpha 3.60", "codename": "Stark"}), encoding="utf-8")
        self.appels = []

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def executer(self, cmd, **kw):
        self.appels.append(cmd)
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    def test_application_sur_une_racine(self):
        res = m.appliquer(self.root, grub=True, efi=True, executer=self.executer)
        self.assertTrue(res["change"])
        self.assertFalse((self.root / "etc/os-release").is_symlink(), "un vrai fichier, que base-files ne reecrira pas")
        d = dict(m.parse_kv((self.root / "etc/os-release").read_text(encoding="utf-8")))
        self.assertEqual(d["NAME"], '"PinCabOS"')
        self.assertEqual(d["ID"], "ubuntu")
        self.assertEqual((self.root / "usr/lib/os-release").read_text(encoding="utf-8"), OS_RELEASE_UBUNTU, "la base Ubuntu n'est pas touchee")
        self.assertIn('DISTRIB_DESCRIPTION="PinCabOS Alpha 3.60 (Ubuntu 26.04.1 LTS)"', (self.root / "etc/lsb-release").read_text(encoding="utf-8"))
        self.assertEqual((self.root / "etc/issue").read_text(encoding="utf-8"), "PinCabOS Alpha 3.60 \\n \\l\n\n")
        self.assertEqual((self.root / "etc/issue.net").read_text(encoding="utf-8"), "PinCabOS Alpha 3.60\n")
        self.assertIn('GRUB_DISTRIBUTOR="PinCabOS"', (self.root / "etc/default/grub").read_text(encoding="utf-8"))
        self.assertEqual(self.appels, [], "racine differente de / : ni update-grub ni efibootmgr")
        self.assertEqual(res["libelle"], "PinCabOS Alpha 3.60 (Ubuntu 26.04.1 LTS)")
        # idempotent
        res2 = m.appliquer(self.root, grub=True, efi=True, executer=self.executer)
        self.assertFalse(res2["change"])
        self.assertTrue(all(l.startswith(("OK:", "INFO:")) for l in res2["journal"]), res2["journal"])

    def test_statut(self):
        lignes = m.statut(self.root, executer=self.executer)
        self.assertIn("version PinCabOS : Alpha 3.60 (Stark)", lignes[0])
        self.assertTrue(any("NAME=Ubuntu" in l and "lien symbolique" in l for l in lignes), lignes)
        m.appliquer(self.root, executer=self.executer)
        lignes = m.statut(self.root, executer=self.executer)
        self.assertTrue(any("NAME=PinCabOS" in l for l in lignes), lignes)
        self.assertTrue(any('GRUB_DISTRIBUTOR : "PinCabOS"' in l for l in lignes), lignes)


class Installation(unittest.TestCase):
    def test_iso_sh_applique_l_identite_sur_la_cible(self):
        s = (Path(RACINE) / "opt/pincabos/script/iso.sh").read_text(encoding="utf-8")
        self.assertIn("apply_target_identity() {", s)
        self.assertIn('pincabos_identity.py" apply --root "$TARGET" --no-grub', s)
        a, b, c = s.index("  apply_target_orientation\n"), s.index("  apply_target_identity\n"), s.index("  refresh_target_initrd_for_orientation\n")
        self.assertLess(a, b, "appelee apres l'orientation")
        self.assertLess(b, c, "et avant la regeneration de l'initrd")

    def test_unite_et_wrapper(self):
        u = (Path(RACINE) / "etc/systemd/system/pincabos-identity.service").read_text(encoding="utf-8")
        self.assertIn("ExecStart=/opt/pincabos/tools/pincabos-identity apply --efi", u)
        self.assertIn("ConditionPathExists=/opt/pincabos/config/version.json", u)
        lien = Path(RACINE) / "etc/systemd/system/multi-user.target.wants/pincabos-identity.service"
        self.assertTrue(lien.is_symlink() or lien.exists())
        w = Path(RACINE) / "opt/pincabos/tools/pincabos-identity"
        self.assertTrue(os.access(w, os.X_OK))
        self.assertIn("pincabos_identity.py", w.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
