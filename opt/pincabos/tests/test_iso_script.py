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
        argument « \\ » (le vrai rend « Failed to prepare filename \\ »). Avec set -e,
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


if __name__ == "__main__":
    unittest.main()
