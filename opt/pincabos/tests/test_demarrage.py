"""Lot « démarrage » (PINCABOS_DEMARRAGE_V1) : le frontend n'attend que ce qui lui sert.

Mesure sur le cab de Yann (3.55) : 56 s de boot, frontend visible vers 33 s.
Entre X (3 s) et VPinFE : vidéo de boot en série (10,8 s), suppression en
ligne de 401 Mo de profils Chrome (3,4 s), balayages bash de /proc (~1,5 s),
attente d'X par pas d'une seconde, et une garde de réparation qui rejouait
18,6 s de systemctl à chaque boot.
"""
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from _charge import RACINE

R = Path(RACINE)
GUARD = R / "usr/local/sbin/pincabos-final-graphical-guard.sh"
GUARD_UNIT = R / "etc/systemd/system/pincabos-final-graphical-guard.service"
CLEANUP = R / "usr/local/libexec/pincabos/vpinfe-chromium-profile-cleanup.sh"
PRESTART = R / "usr/local/libexec/pincabos/pincabos-vpinfe-prestart-guard"
PREFLIGHT = R / "usr/local/libexec/pincabos/pincabos-screen-topology-preflight.sh"
VPINFE_UNIT = R / "etc/systemd/system/pincabos-vpinfe.service"
VPINFE_DROPIN = R / "etc/systemd/system/pincabos-vpinfe.service.d/90-pincabos-iso-start.conf"


def profil(root: Path, nom: str, ko: int = 64) -> Path:
    d = root / nom
    (d / "Default" / "Cache").mkdir(parents=True)
    for i in range(8):
        (d / "Default" / "Cache" / f"f_{i:06x}").write_bytes(os.urandom(ko * 1024 // 8))
    return d


class GardeGraphique(unittest.TestCase):
    def test_chemin_rapide_avant_toute_reparation(self):
        s = GUARD.read_text(encoding="utf-8")
        self.assertIn("PINCABOS_GUARD_FAST_PATH_V1", s)
        self.assertLess(s.index("chemin rapide, rien a reparer"), s.index("systemctl daemon-reload"),
                        "le chemin rapide doit sortir avant le daemon-reload et les attentes")
        self.assertIn('"${1:-}" != "--force"', s)
        self.assertIn("final-graphical-guard.done", s)
        self.assertLess(s.index("touch \"$MARKER\""), s.index("final LightDM hard graphical guard completed"))

    def test_la_garde_n_attend_plus_le_reseau(self):
        u = GUARD_UNIT.read_text(encoding="utf-8")
        self.assertNotIn("network-online", u)
        self.assertIn("Before=getty@tty1.service", u)

    def test_syntaxe(self):
        for f in (GUARD, CLEANUP, PRESTART, PREFLIGHT):
            r = subprocess.run(["bash", "-n", str(f)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, f"{f.name}: {r.stderr}")


class NettoyageProfils(unittest.TestCase):
    """vpinfe-chromium-profile-cleanup.sh prestart, sans Chrome en cours : les profils
    fermes sont mis au rebut instantanement puis supprimes (en ligne ici, PINCABOS_GC_SYNC=1)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.tmpdir = self.tmp / "tmp"
        self.root = self.tmp / "profiles"
        self.tmpdir.mkdir()
        self.root.mkdir()
        self.env = dict(os.environ, PINCABOS_VPINFE_PROFILE_ROOT=str(self.root), PINCABOS_VPINFE_TMP=str(self.tmpdir), PINCABOS_GC_SYNC="1")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def lancer(self, mode="prestart"):
        return subprocess.run(["bash", str(CLEANUP), mode], env=self.env, capture_output=True, text=True, timeout=60)

    def test_profils_fermes_supprimes(self):
        profil(self.root, "vpinfe_chromium_bg")
        profil(self.root, "vpinfe_chromium_table")
        profil(self.tmpdir, "vpinfe_chromium_old")
        (self.root / ".gc-vpinfe_chromium_dmd-1-2").mkdir()  # rebut d'une coupure de courant
        (self.root / "autre_chose").mkdir()
        os.symlink(self.root / "autre_chose", self.root / "vpinfe_chromium_lien")
        r = self.lancer()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("MIS AU REBUT", r.stdout)
        self.assertIn("REBUT REPRIS", r.stdout)
        restes = sorted(p.name for p in self.root.iterdir())
        self.assertEqual(restes, ["autre_chose", "vpinfe_chromium_lien"], "seuls les profils reels partent ; lien et autres dossiers restent")
        self.assertEqual([p.name for p in self.tmpdir.iterdir()], [])
        self.assertIn("termine", r.stdout)

    def test_rien_a_faire(self):
        r = self.lancer("poststop")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("REBUT", r.stdout)

    def test_le_rebut_sort_du_motif(self):
        s = CLEANUP.read_text(encoding="utf-8")
        self.assertIn(".gc-$(basename", s)
        self.assertIn("systemd-run", s)
        self.assertIn("IOSchedulingClass=idle", s)
        self.assertIn("pgrep -x chrome", s)
        self.assertNotIn("for proc in /proc/[0-9]*", s)


class GardePrestart(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.tmpdir = self.tmp / "tmp"
        self.root = self.tmp / "profiles"
        self.tmpdir.mkdir()
        import getpass
        self.env = dict(os.environ, PINCABOS_VPINFE_PROFILE_ROOT=str(self.root), PINCABOS_VPINFE_TMP=str(self.tmpdir),
                        PINCABOS_GC_SYNC="1", PINCABOS_PINBALL_USER=getpass.getuser())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_profils_perimes_et_racine_recreee(self):
        self.root.mkdir()
        profil(self.root, "vpinfe_chromium_stale")
        profil(self.tmpdir, "vpinfe_chromium_stale2")
        debut = time.time()
        r = subprocess.run(["bash", str(PRESTART)], env=self.env, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(self.root.is_dir(), "la racine des profils est recreee")
        self.assertEqual([p.name for p in self.root.iterdir()], [])
        self.assertEqual([p.name for p in self.tmpdir.iterdir()], [])
        self.assertIn("completed", r.stdout)
        self.assertLess(time.time() - debut, 5, "aucune attente fixe quand rien ne tourne")

    def test_sans_balayage_de_proc(self):
        s = PRESTART.read_text(encoding="utf-8")
        self.assertNotIn("for proc in /proc/[0-9]*", s)
        self.assertIn("pgrep -U", s)
        self.assertIn("gc_async", s)


class AttenteDeX(unittest.TestCase):
    def test_pas_d_une_seconde_remplace_par_un_quart(self):
        s = PREFLIGHT.read_text(encoding="utf-8")
        self.assertIn("sleep 0.25", s)
        self.assertNotIn("\n  sleep 1\n", s)
        self.assertIn("seq 1 360", s, "meme horizon de 90 s")


class Reseau(unittest.TestCase):
    def test_vpinfe_n_attend_pas_network_online(self):
        for f in (VPINFE_UNIT, VPINFE_DROPIN):
            for line in f.read_text(encoding="utf-8").splitlines():
                if line.startswith("After="):
                    self.assertNotIn("network-online", line, f.name)
        self.assertIn("After=display-manager.service network.target", VPINFE_UNIT.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
