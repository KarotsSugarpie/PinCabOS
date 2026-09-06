"""PINCABOS_ISO_ETAPES_V1 : iso.sh en etapes relancables."""
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from _charge import RACINE

R = Path(RACINE)
ISO = R / "opt/pincabos/script/iso.sh"
D = R / "opt/pincabos/script/iso"
ETAPES = ["10-audit-nettoyage", "20-outils-hote", "30-source", "40-payload", "50-plymouth-overlay",
          "60-validation-payload", "70-helper", "80-live-rootfs", "90-iso", "95-publication"]


class Etapes(unittest.TestCase):
    def test_fichiers_et_syntaxe(self):
        self.assertTrue((D / "00-lib.sh").is_file())
        for e in ETAPES:
            f = D / f"{e}.sh"
            self.assertTrue(f.is_file(), f)
            self.assertTrue(os.access(f, os.X_OK), f)
            self.assertEqual(subprocess.run(["bash", "-n", str(f)]).returncode, 0, f)
            s = f.read_text(encoding="utf-8")
            self.assertIn('. "$(dirname "$(readlink -f "$0")")/00-lib.sh"', s, e)
            self.assertIn("set -Eeuo pipefail", s, e)
        self.assertEqual(subprocess.run(["bash", "-n", str(ISO)]).returncode, 0)
        self.assertEqual(subprocess.run(["bash", "-n", str(D / "00-lib.sh")]).returncode, 0)

    def test_sections_dans_leur_etape(self):
        attendu = {"10-audit-nettoyage": ["=== 1) Safety audit", "=== 2) Cleanup"], "20-outils-hote": ["=== 3) Install"],
                   "30-source": ["=== 4) Validate source"], "40-payload": ["=== 5) Build lean", "PINCABOS_VPXTOOL_ISO_EMBED_V1", "PINCABOS_ISO_AUDIO_PRIVACY_V1"],
                   "50-plymouth-overlay": ["=== 6) Build Plymouth"], "60-validation-payload": ["=== 7) Validate payload"],
                   "70-helper": ["=== 8) Payload helper"], "80-live-rootfs": ["=== 9L)", "=== 12)", "=== 13)", "PINCABOS_LIVE_TTY_BOOT_NO_CYCLE_V1"],
                   "90-iso": ["=== 14L)", "iso-live.sh"], "95-publication": ["PINCABOS_OPTIONAL_WEB_PUBLISH_V1", "pincabos_offer_web_publish"]}
        for e, marqueurs in attendu.items():
            s = (D / f"{e}.sh").read_text(encoding="utf-8")
            for m in marqueurs:
                self.assertIn(m, s, f"{e} : {m}")

    def test_variables_partagees(self):
        lib = (D / "00-lib.sh").read_text(encoding="utf-8")
        for v in ("ARCHIVE=", "OVERLAY=", "MANIFEST=", "VPXTOOL_MANIFEST=", "WORK=", "PAYLOAD_FULL=", "LIVE_ROOTFS=", "INSTALLER_SRC="):
            self.assertIn(v, lib, v)
        self.assertIn("pco_etat_ecrire()", lib)
        self.assertIn("pco_etat_ecrire VPXTOOL_VERSION", (D / "40-payload.sh").read_text(encoding="utf-8"))
        self.assertIn('[ -n "${VPXTOOL_VERSION:-}" ] || die', (D / "60-validation-payload.sh").read_text(encoding="utf-8"))
        # plus aucune etape ne se sert de $0 pour trouver iso-live.sh ou l installateur
        for e in ETAPES:
            s = (D / f"{e}.sh").read_text(encoding="utf-8")
            for l in s.splitlines():
                if "$0" in l and "00-lib.sh" not in l:
                    self.assertIn("PCO_ISO_SCRIPT_DIR", l, f"{e} : {l}")
        self.assertIn('ROOTFS_DIR="$LIVE_ROOTFS"', (D / "90-iso.sh").read_text(encoding="utf-8"))
        self.assertIn('ROOTFS_DIR="$LIVE_ROOTFS"', (D / "80-live-rootfs.sh").read_text(encoding="utf-8"))

    def test_lib_sourcable_sous_set_e(self):
        # une ligne « [ -f x ] && ... » en fin de fichier source rend 1 sous set -e : chaque etape mourait a la ligne 4
        lib = (D / "00-lib.sh").read_text(encoding="utf-8")
        for l in lib.splitlines():
            self.assertFalse(l.startswith("[ ") and " && " in l, f"forme fatale sous set -e : {l}")
        self.assertNotIn('echo "ISO model', lib)
        r = subprocess.run(["bash", "-c", 'set -Eeuo pipefail; BUILD_BASE=x; . "$1"; echo SOURCE_OK', "_", str(D / "00-lib.sh")],
                           capture_output=True, text=True, env=dict(os.environ, PCO_ISO_SCRIPT_DIR=str(R / "opt/pincabos/script")))
        self.assertIn("SOURCE_OK", r.stdout, r.stderr)

    def test_orchestrateur_a_blanc(self):
        """Etapes factices : ordre, --liste, --etape, --depuis, --jusqua, NOGO qui arrete."""
        with tempfile.TemporaryDirectory() as d:
            racine = Path(d)
            (racine / "iso").mkdir()
            work = racine / "work"
            (racine / "iso/00-lib.sh").write_text(
                f'WORK="{work}"\nLOG_DIR="{work}/logs"\nPCO_ISO_MODEL="live"\ncleanup_mounts() {{ :; }}\ndie() {{ echo "ERROR: $*"; exit 1; }}\n', encoding="utf-8")
            for n in ("10-a", "20-b", "30-c"):
                # l etape 10 reelle fait rm -rf "$WORK" : les marqueurs GO doivent y survivre
                (racine / f"iso/{n}.sh").write_text(f'#!/bin/bash\n. "$(dirname "$0")/00-lib.sh"\n[ "{n}" = "10-a" ] && rm -rf "$WORK"\necho "RUN {n}"\n[ "{n}" = "20-b" ] && [ -n "${{CASSE:-}}" ] && exit 3\nexit 0\n', encoding="utf-8")
            orch = racine / "iso.sh"
            orch.write_text(ISO.read_text(encoding="utf-8"), encoding="utf-8")
            orch.chmod(0o755)
            env = dict(os.environ, CASSE="")
            if os.geteuid() != 0:
                self.skipTest("orchestrateur : root requis")
            r = subprocess.run(["bash", str(orch), "--liste"], capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual([l.split()[-1] for l in r.stdout.splitlines() if l.strip()], ["10-a", "20-b", "30-c"])
            r = subprocess.run(["bash", str(orch), "--etape", "20"], capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("RUN 20-b", r.stdout); self.assertNotIn("RUN 10-a", r.stdout)
            self.assertTrue((work / "logs/etat/20.go").is_file())
            self.assertTrue((work / "logs/etat/10.go").is_file())
            r = subprocess.run(["bash", str(orch), "--depuis", "20", "--jusqua", "20"], capture_output=True, text=True, env=env)
            self.assertIn("RUN 20-b", r.stdout); self.assertNotIn("RUN 30-c", r.stdout)
            r = subprocess.run(["bash", str(orch)], capture_output=True, text=True, env=dict(env, CASSE="1"))
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("NOGO [***] etape 20-b", r.stdout)
            self.assertIn("--etape 20", r.stdout)
            self.assertNotIn("RUN 30-c", r.stdout)
            self.assertFalse((work / "logs/etat/20.go").exists())
            r = subprocess.run(["bash", str(orch), "--classic"], capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
