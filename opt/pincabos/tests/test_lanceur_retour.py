"""Lanceur : au retour d'une table Original, le frontend est reveille (PINCABOS_RETOUR_FRONTEND_V1).

Alpha 3.77 (Yann, playfield 4K NVIDIA) : apres avoir quitte la table de test,
l'ecran restait noir alors que VPinFE tournait toujours. Le lanceur rend le
focus a la fenetre VPinFE et force un rafraichissement X ; sans effet quand
tout va deja bien.
"""
import subprocess
import unittest
from pathlib import Path

from _charge import RACINE

CORE = Path(RACINE) / "opt/pincabos/launchers/pincabos-launch-core.sh"


class RetourFrontend(unittest.TestCase):
    def test_syntaxe(self):
        self.assertEqual(subprocess.run(["bash", "-n", str(CORE)]).returncode, 0)

    def test_reveil_apres_la_table_originale(self):
        s = CORE.read_text(encoding="utf-8")
        self.assertIn("PINCABOS_RETOUR_FRONTEND_V1", s)
        self.assertIn("reveiller_frontend() {", s)
        # apres la fin de VPX (RC releve, PuP restaure), avant la sortie du lanceur
        bloc = s[s.index("RC=$?"):]
        self.assertLess(bloc.index("restore_pup\n"), bloc.index("reveiller_frontend\n"))
        self.assertLess(bloc.index("reveiller_frontend\n"), bloc.index('exit "$RC"'))
        # sans DISPLAY ni xdotool : rien, jamais d'erreur
        self.assertIn('[[ -n "${DISPLAY:-}" ]] || return 0', s)
        self.assertIn("command -v xdotool >/dev/null 2>&1", s)
        # PINCABOS_RETOUR_FRONTEND_V2 : la fenetre principale d'abord (BG/DMD recevaient le clavier)
        self.assertIn("xdotool search --onlyvisible --name '^VPinFE Table$'", s)
        self.assertIn("xdotool search --onlyvisible --name '^VPinFE'", s)
        self.assertLess(s.index("'^VPinFE Table$'"), s.index("'^VPinFE' 2>/dev/null"))

    def test_le_reveil_ne_fait_rien_sans_serveur_x(self):
        s = CORE.read_text(encoding="utf-8")
        a = s.index("reveiller_frontend() {")
        b = s.index("\n        }\n", a) + len("\n        }\n")
        fonction = s[a:b].replace("\n        ", "\n")
        script = "set -u\nlog(){ echo \"$*\"; }\n" + fonction + "\nreveiller_frontend\necho FIN\n"
        r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "FIN")


if __name__ == "__main__":
    unittest.main()
