"""PINCABOS_ISO_SOURCE_V1 (lot D) : le payload se photographie sur un rootfs prepare, sans cab source."""
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from _charge import RACINE

R = Path(RACINE)
D = R / "opt/pincabos/script/iso"
ISO = R / "opt/pincabos/script/iso.sh"


class Source(unittest.TestCase):
    def test_lib(self):
        s = (D / "00-lib.sh").read_text(encoding="utf-8")
        self.assertIn('PCO_ISO_SOURCE="${PCO_ISO_SOURCE:-/}"', s)
        self.assertIn('/) SRC="" ;;', s)
        self.assertIn('VPXTOOL_MANIFEST="$SRC/opt/pincabos/update/vpxtool-release.json"', s)

    def test_etapes_lisent_la_source(self):
        s30 = (D / "30-source.sh").read_text(encoding="utf-8")
        self.assertIn('test -d "$SRC/boot"', s30)
        self.assertIn('test -d "$SRC/opt/pincabos"', s30)
        s40 = (D / "40-payload.sh").read_text(encoding="utf-8")
        self.assertIn('-C "$PCO_ISO_SOURCE" . \\', s40)
        self.assertIn('source_root = Path(sys.argv[3]', s40)
        self.assertIn('relative = source.relative_to(source_root)', s40)
        self.assertIn('source_root / "home/pinball/.pincabos/vpx"', s40)
        self.assertIn('cat "$SRC/etc/default/grub"', s40)
        s50 = (D / "50-plymouth-overlay.sh").read_text(encoding="utf-8")
        self.assertIn('-C "$PCO_ISO_SOURCE" \\', s50)
        # plus aucune photo du systeme hote en dur
        for e in ("30-source", "40-payload", "50-plymouth-overlay"):
            s = (D / f"{e}.sh").read_text(encoding="utf-8")
            for l in s.splitlines():
                if l.strip().startswith("#") or "--exclude=" in l:
                    continue
                self.assertNotRegex(l, r"-C / ", f"{e} : {l}")
                self.assertNotRegex(l, r"(^|\s)(test|ls|cat|find) (-[a-z]+ )*/(boot|lib|etc|usr)\b", f"{e} : {l}")

    def test_modele_vpx_sans_carte_audio(self):
        # PINCABOS_ISO_AUDIO_PRIVACY_MODELE_V1 : execution reelle du lot B sur VM : l archive refusee
        # a cause du modele de #204 (SoundDevice = Built-in Audio Analog Stereo)
        m = (R / "opt/pincabos/templates/home/.local/share/VPinballX/10.8/VPinballX.ini").read_text(encoding="utf-8", errors="replace")
        for l in m.splitlines():
            if re.match(r"^\s*(SoundDevice|SoundDeviceBG)\s*=", l):
                self.assertEqual(l.split("=", 1)[1].strip(), "", l)
        s40 = (D / "40-payload.sh").read_text(encoding="utf-8")
        self.assertIn('source_root / "opt/pincabos/templates/home/.local/share/VPinballX"', s40)
        self.assertIn("--exclude='./opt/pincabos/templates/home/.local/share/VPinballX/*/VPinballX.ini'", s40)

    def test_point_de_montage_du_cache_apt(self):
        # PINCABOS_ISO_APT_CACHE_MOUNTPOINT_V1 : var/cache/* est exclu du payload
        s80 = (D / "80-live-rootfs.sh").read_text(encoding="utf-8")
        self.assertLess(s80.index('mkdir -p "$ROOTFS_DIR/var/cache/apt/archives/partial"'),
                        s80.index('mount --bind "$CACHE_DIR/apt-archives"'))

    def test_etape_80_copie_depuis_la_source(self):
        # lot D (execution reelle sur le banc) : theme Plymouth, plugin script.so, dispatch/kiosque/unites
        # du live etaient copies depuis l hote (« cannot stat /usr/share/plymouth/themes/pincabos »)
        s80 = (D / "80-live-rootfs.sh").read_text(encoding="utf-8")
        self.assertIn('cp -a "$SRC/usr/share/plymouth/themes/pincabos"', s80)
        self.assertIn('cp "$SRC/$PLY_LIB/script.so"', s80)
        self.assertIn('install -m 755 "$SRC"/usr/local/sbin/pincabos-installer-dispatch', s80)
        self.assertIn('"$SRC"/etc/systemd/system/pincabos-gui-wizard.service', s80)
        for l in s80.splitlines():
            if re.match(r"^\s*(cp|install) ", l) and "chroot" not in l and "resolv.conf" not in l:   # resolv.conf : celui de l hote, par nature
                self.assertNotRegex(l, r"(cp|install)( -[-a-zA-Z0-9 ]+)? /(usr|etc|opt|boot|lib)/", l)

    def test_orchestrateur_source(self):
        s = ISO.read_text(encoding="utf-8")
        self.assertIn('--source) SOURCE="${2:-}"; shift ;;', s)
        self.assertIn('export PCO_ISO_SOURCE="$SOURCE"', s)
        self.assertEqual(subprocess.run(["bash", "-n", str(ISO)]).returncode, 0)
        if os.geteuid() != 0:
            self.skipTest("orchestrateur : root requis")
        with tempfile.TemporaryDirectory() as d:
            racine = Path(d); (racine / "iso").mkdir(); work = racine / "work"
            (racine / "iso/00-lib.sh").write_text(f'WORK="{work}"\nLOG_DIR="{work}/logs"\nPCO_ISO_MODEL="live"\nPCO_ISO_SOURCE="${{PCO_ISO_SOURCE:-/}}"\ncleanup_mounts() {{ :; }}\n', encoding="utf-8")
            (racine / "iso/10-a.sh").write_text('#!/bin/bash\n. "$(dirname "$0")/00-lib.sh"\necho "SOURCE=$PCO_ISO_SOURCE"\n', encoding="utf-8")
            orch = racine / "iso.sh"; orch.write_text(s, encoding="utf-8")
            src = racine / "master"; (src / "opt/pincabos").mkdir(parents=True)
            r = subprocess.run(["bash", str(orch), "--source", str(src)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn(f"SOURCE={src}", r.stdout)
            self.assertIn(f"Source: {src}", r.stdout)
            r = subprocess.run(["bash", str(orch), "--source", str(racine / "pas-un-rootfs")], capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("pas un rootfs PinCabOS", r.stdout + r.stderr)
            r = subprocess.run(["bash", str(orch)], capture_output=True, text=True)
            self.assertIn("SOURCE=/", r.stdout)


if __name__ == "__main__":
    unittest.main()
