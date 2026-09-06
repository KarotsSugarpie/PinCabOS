"""pincabos-iso-payload-top : tri des contributeurs du payload ISO (PINCABOS_ISO_PAYLOAD_TOP_V1).

Rejoue les exclusions exactes de iso.sh sur une racine factice : ce qui est
exclu ne pese rien, ce qui reste est classe par taille.
"""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _charge import RACINE

TOOL = Path(RACINE) / "opt/pincabos/tools/pincabos-iso-payload-top"
ISO = Path(RACINE) / "opt/pincabos/script/iso/40-payload.sh"   # PINCABOS_ISO_ETAPES_V1 : la commande tar est dans l etape 40
ORCHESTRATEUR = Path(RACINE) / "opt/pincabos/script/iso.sh"


def fichier(chemin: Path, mo: float):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("wb") as f:
        f.truncate(int(mo * 1024 * 1024))


class PayloadTop(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        # gardes : ce qui doit rester dans l'archive
        fichier(self.root / "usr/lib/x86_64-linux-gnu/libgros.so", 3)
        fichier(self.root / "home/pinball/.pincabos/vpx/pinmame/roms/t2_l8.zip", 2)
        fichier(self.root / "opt/pincabos/web/app.py", 0.5)
        # exclus par iso.sh : ne doivent peser pour rien
        fichier(self.root / "home/pinball/Tables/Une table/table.vpx", 50)
        fichier(self.root / "opt/pincabos/cache/gros.bin", 40)
        fichier(self.root / "opt/pincabos/tmp/worktree/VPinballX.ini", 1)
        fichier(self.root / "swap.img", 30)
        fichier(self.root / "var/log/journal/x.journal", 5)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def lancer(self, *args):
        return subprocess.run(["bash", str(TOOL), "--root", str(self.root), "--iso", str(ISO), *args],
                              capture_output=True, text=True, timeout=120)

    def test_exclusions_rejouees_et_classement(self):
        r = self.lancer("--top", "10")
        self.assertEqual(r.returncode, 0, r.stderr)
        lignes = r.stdout.splitlines()
        self.assertIn("exclusions rejouees : 1", lignes[0][:24])
        corps = "\n".join(lignes[1:])
        self.assertIn("usr/lib/x86_64-linux-gnu", corps)
        self.assertIn("home/pinball/.pincabos", corps)
        exclus = ["home/pinball/Tables", "opt/pincabos/cache", "swap.img", "var/log"]
        if "--exclude='./opt/pincabos/tmp'" in ISO.read_text(encoding="utf-8"):
            exclus.append("opt/pincabos/tmp")  # arrive avec la PR #156 de Karots
        for exclu in exclus:
            self.assertNotIn(exclu, corps, exclu)
        total = next(l for l in lignes if "TOTAL" in l)
        self.assertLess(float(total.split()[0]), 10, "quelques Mo restants, pas les 125 Mo exclus")
        # tri decroissant : la premiere ligne de repertoire est la plus grosse
        premiere = next(l for l in lignes[1:] if "TOTAL" not in l).split()
        self.assertIn("usr/lib/x86_64-linux-gnu", premiere[-1])

    def test_profondeur(self):
        r = self.lancer("--depth", "1", "--top", "5")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout, r"\n *[0-9]+ Mo  usr\n")

    def test_iso_sh_orchestrateur_redirige_vers_l_etape_40(self):
        # PINCABOS_ISO_ETAPES_V1 : --iso iso.sh (l ancien reflexe) doit encore marcher
        r = subprocess.run(["bash", str(TOOL), "--root", str(self.root), "--iso", str(ORCHESTRATEUR)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("40-payload.sh", r.stdout.splitlines()[0])

    def test_erreurs_claires(self):
        r = subprocess.run(["bash", str(TOOL), "--root", "/chemin/absent"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("racine introuvable", r.stderr)
        r = subprocess.run(["bash", str(TOOL), "--root", str(self.root), "--iso", str(self.root / "pas-iso.sh")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("iso.sh introuvable", r.stderr)
        self.assertTrue(os.access(TOOL, os.X_OK), "l'outil doit etre executable")


if __name__ == "__main__":
    unittest.main()
