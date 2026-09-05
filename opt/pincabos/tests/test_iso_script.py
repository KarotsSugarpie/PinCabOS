"""iso.sh : le helper d'installation genere doit rester executable de bout en bout.

Regression Alpha 3.12-3.46 (commit adf4c1e) : une continuation de ligne
doublee (`\\\\`) dans le bloc `systemd-analyze verify` du helper coupait la
commande ; avec `set -euo pipefail` le helper s'arretait et l'installateur
rendait « Payload extraction/install failed (code 1) ». Karots ne pouvait
plus installer une ISO ; les ISO construites depuis le 01/09 etaient
inutilisables.
"""
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from _charge import RACINE

ISO = os.path.join(RACINE, "opt/pincabos/script/iso.sh")


def _texte():
    with open(ISO, encoding="utf-8", errors="ignore") as f:
        return f.read()


def _bloc_verify():
    s = _texte()
    a = s.index("systemd-analyze --root=")
    b = s.index("|| true", a) + len("|| true")
    return s[a:b]


class Continuations(unittest.TestCase):
    def test_aucune_ligne_ne_finit_par_un_double_backslash(self):
        fautives = [f"{i}: {l}" for i, l in enumerate(_texte().splitlines(), 1) if l.endswith("\\\\")]
        self.assertEqual(fautives, [])

    def test_le_bloc_verify_est_une_seule_commande(self):
        """Simule le helper : systemd-analyze remplace par un stub qui echoue sur un
        argument « \\ » (le vrai rend « Failed to prepare filename \\: Invalid argument' »). Avec set -e,
        le bloc doit rendre 0 grace au `|| true` rattache a la vraie commande."""
        bloc = _bloc_verify()
        script = (
            "set -euo pipefail\nTARGET=/nonexistent\nSYSTEMD_VERIFY_LOG=$(mktemp)\n"
            "systemd-analyze() { for a in \"$@\"; do [ \"$a\" = '\\' ] && { echo 'Failed to prepare filename \\: Invalid argument' >&2; return 1; }; done; return 3; }\n"
            + bloc + "\necho FIN\n"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as f:
            f.write(script)
        r = subprocess.run(["bash", f.name], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("FIN", r.stdout)

    def test_les_unites_verifiees_existent(self):
        unites = re.findall(r"(pincabos-[a-z0-9-]+\.service)", _bloc_verify())
        self.assertTrue(unites)
        absentes = [u for u in unites if not os.path.exists(os.path.join(RACINE, "etc/systemd/system", u))]
        self.assertEqual(absentes, [])

    def test_garde_de_construction_presente(self):
        self.assertIn("PINCABOS_ISO_HELPER_CONTINUATION_GUARD_V1", _texte())


class DropIns(unittest.TestCase):
    def test_les_drop_ins_ne_sont_pas_executables(self):
        d = os.path.join(RACINE, "etc/systemd/system/pincabos-vpinfe.service.d")
        out = subprocess.run(["git", "-C", RACINE, "ls-files", "-s", d], capture_output=True, text=True).stdout
        exec_ = [l.split()[3] for l in out.splitlines() if l.startswith("100755")]
        self.assertEqual(exec_, [])


class PreferencesVpx(unittest.TestCase):
    """PINCABOS_VPX_PREF_PATH_V1 : les preferences VPX vivent sous ~/.pincabos/vpx
    (-PrefPath). iso.sh doit traiter ce chemin partout ou il traitait les anciens :
    sans cela le VPinballX.ini du master (noms de cartes audio) partait dans la
    photo et la garde audio de Karots refusait l'ISO (04/09/2026)."""

    NOUVEAU = "home/pinball/.pincabos/vpx"

    def test_exclu_du_tar_neutralise_et_conserve(self):
        s = _texte()
        self.assertIn("--exclude='./home/pinball/.pincabos/vpx/VPinballX.ini'", s)
        self.assertGreaterEqual(s.count('Path("/home/pinball/.pincabos/vpx")'), 1)
        self.assertEqual(s.count('target / "home/pinball/.pincabos/vpx"'), 2)
        self.assertIn('"home/pinball/.pincabos/vpx/VPinballX.ini"', s)

    def test_partout_ou_l_ancien_chemin_est_traite(self):
        """Chaque bloc qui cite ~/.vpinball/VPinballX.ini cite aussi le nouveau chemin."""
        lignes = _texte().splitlines()
        for i, l in enumerate(lignes):
            if ".vpinball" in l and "VPinballX" in l or 'target / "home/pinball/.vpinball"' in l or 'Path("/home/pinball/.vpinball")' in l:
                voisinage = "\n".join(lignes[max(0, i - 8): i + 4])
                self.assertIn(".pincabos/vpx", voisinage, f"ligne {i + 1}: {l.strip()}")

    def test_regex_archive_prefpath_est_exacte(self):
        """La regex doit matcher './home/...' et ne jamais chercher un backslash litteral."""
        s = _texte()
        bonne = r"^\./home/pinball/\.pincabos/vpx/VPinballX\.ini$"
        mauvaise = r"^\\\./home/pinball/\\\.pincabos/vpx/VPinballX\\\.ini$"
        self.assertIn(bonne, s)
        self.assertNotIn(mauvaise, s)


if __name__ == "__main__":
    unittest.main()


class ModeleLive(unittest.TestCase):
    """PINCABOS_ISO_MODELE_LIVE_V1 : iso.sh --live confie l ISO a iso-live.sh."""

    def setUp(self):
        self.s = (Path(RACINE) / "opt/pincabos/script/iso.sh").read_text(encoding="utf-8")

    def test_drapeau_et_defaut(self):
        self.assertIn('PCO_ISO_MODEL="${PCO_ISO_MODEL:-live}"', self.s)   # le live est le defaut
        self.assertIn('--live) PCO_ISO_MODEL="live" ;;', self.s)
        self.assertIn('--classic) PCO_ISO_MODEL="classic" ;;', self.s)   # roue de secours, une release

    def test_branches_equilibrees(self):
        # sections 9-11 (base Ubuntu) et 14-20 (repack, GRUB, xorriso) sont dans la branche classic
        s = self.s
        self.assertLess(s.index('if [ "$PCO_ISO_MODEL" = "live" ]; then\n  echo\n  echo "=== 9L)'), s.index('echo "=== 9) Download'))
        self.assertLess(s.index('echo "=== 11) Locate'), s.index("fi   # PCO_ISO_MODEL classic (sections 9-11)"))
        self.assertLess(s.index("fi   # PCO_ISO_MODEL classic (sections 9-11)"), s.index('echo "=== 12) Ensure'))
        self.assertLess(s.index('echo "=== 14L) Live model'), s.index('echo "=== 14) No live desktop'))
        self.assertLess(s.index('echo "=== 20) Final ISO validation'), s.index("fi   # PCO_ISO_MODEL classic (sections 14-20)"))
        self.assertLess(s.index("fi   # PCO_ISO_MODEL classic (sections 14-20)"), s.index("pincabos_offer_web_publish() {"))

    def test_live_utilise_le_payload_et_iso_live(self):
        self.assertIn('tar --zstd -xpf "$ARCHIVE" -C "$LIVE_ROOTFS" --numeric-owner', self.s)
        self.assertIn('ROOTFS_DIR="$LIVE_ROOTFS"', self.s)
        self.assertIn('bash "$LIVE_SH" --rootfs "$ROOTFS_DIR" --payload "$PAYLOAD_FULL" --out "$OUT_ISO"', self.s)
        # les montages du chroot (section 12) sont defaits avant iso-live.sh, qui monte les siens
        bloc = self.s[self.s.index('echo "=== 14L)'):self.s.index('bash "$LIVE_SH"')]
        self.assertIn("cleanup_mounts", bloc)

    def test_syntaxe_bash(self):
        import subprocess
        for f in ("opt/pincabos/script/iso.sh", "opt/pincabos/script/iso-live.sh"):
            r = subprocess.run(["bash", "-n", str(Path(RACINE) / f)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, f + " : " + r.stderr)

    def test_iso_live_installe_les_outils_manquants(self):
        l = (Path(RACINE) / "opt/pincabos/script/iso-live.sh").read_text(encoding="utf-8")
        for outil in ("grub-efi-amd64-bin", "grub-pc-bin", "xorriso", "mtools", "casper"):
            self.assertIn(outil, l)


class FichiersVivants(unittest.TestCase):
    """PINCABOS_KEEP_PATHS_V2 : ce qui est propre au cab survit a la mise a jour."""

    def test_liste_de_conservation(self):
        s = Path(RACINE, "opt/pincabos/script/iso.sh").read_text(encoding="utf-8")
        bloc = s.split("PCO_KEEP_PATHS=(")[1].split("\n)\n")[0]   # une parenthese dans un commentaire ne ferme pas le tableau
        for p in ("opt/pincabos/config/screens", "home/pinball/.config/vpinfe/vpinfe.ini",
                  "home/pinball/.local/share/VPinballX/10.8/directoutputconfig", "home/pinball/.config/pincabos",
                  "opt/pincabos/config/dof", "opt/pincabos/config/zedmd.json", "opt/pincabos/config/splash.json",
                  "opt/pincabos/flags", "etc/netplan", "etc/ssh", "etc/machine-id", "var/lib/NetworkManager"):
            self.assertIn(f'"{p}"', bloc, p)
        self.assertNotIn('"opt/pincabos/config/version.json"', bloc)   # la version, elle, doit changer


class LienVpx(unittest.TestCase):
    """PINCABOS_VPX_LINK_V1 : ~/vpx existe sur la cible et a l execution."""

    def test_cible_et_filet(self):
        s = Path(RACINE, "opt/pincabos/script/iso.sh").read_text(encoding="utf-8")
        self.assertIn("ensure_target_vpx_link() {", s)
        self.assertLess(s.index("  ensure_target_vpx_link\n"), s.index("  apply_target_identity\n"))
        self.assertIn('ln -sfn "$(basename "$plus_recent")" "$h/vpx"', s)
        p = Path(RACINE, "opt/pincabos/tools/pincabos-paths.sh").read_text(encoding="utf-8")
        self.assertIn("PINCABOS_VPX_LINK_V1", p)
        self.assertIn('ln -sfn "$(basename "$_pco_vpx_dir")" /home/pinball/vpx', p)

