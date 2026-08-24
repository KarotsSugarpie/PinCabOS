#!/usr/bin/env python3
"""Verifie que le fichier de reponses de l'installeur reste inerte.

PINCABOS_ANSWERS_QUOTING_V1

L'installateur charge le fichier de reponses du wizard avec « . », en root. Si
une valeur venue du reseau y arrive telle quelle, elle s'execute : $(...) est
developpe meme entre guillemets doubles.

Ce controle rejoue de vraies tentatives contre les regles reellement presentes
dans app.py — elles ne sont pas recopiees ici, elles en sont extraites — puis
charge le fichier produit dans un shell pour verifier qu'il ne s'y passe rien.

A lancer apres toute modification de /api/install.

  pincabos-verifier-reponses-installeur.py   -> 0 si tout est bloque
"""
import ast
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "installer-gui/app.py"


def regles():
    """Regles de validation telles qu'elles sont ecrites dans app.py."""
    source = APP.read_text(encoding="utf-8")
    for noeud in ast.parse(source).body:
        if isinstance(noeud, ast.Assign) and \
                getattr(noeud.targets[0], "id", "") == "ANSWER_RULES":
            espace = {"re": re}
            exec(ast.get_source_segment(source, noeud), espace)
            return espace["ANSWER_RULES"]
    raise SystemExit("NOGO: ANSWER_RULES introuvable dans app.py")


def install(rules, reponse):
    """Rejoue la validation puis l'ecriture de /api/install."""
    retenues = {}
    for cle, moule in rules.items():
        if cle not in reponse:
            continue
        valeur = str(reponse[cle])
        if not moule.match(valeur):
            return None, "refuse (" + cle + ")"
        retenues[cle] = valeur

    if "mode" not in retenues:
        return None, "refuse (mode)"

    return "".join(
        "PCO_ANS_" + cle.upper() + "=" + shlex.quote(valeur) + "\n"
        for cle, valeur in retenues.items()
    ), "accepte"


def execute_quelque_chose(contenu, dossier):
    """Charge le fichier comme le fait l'installateur, et guette une trace."""
    fichier = dossier / "answers.env"
    trace = dossier / "trace"
    fichier.write_text(contenu, encoding="utf-8")
    trace.unlink(missing_ok=True)

    subprocess.run(
        ["bash", "-c", "set -Eeuo pipefail; . " + shlex.quote(str(fichier))],
        check=False, capture_output=True,
    )
    return trace.exists()


def main() -> int:
    rules = regles()

    with tempfile.TemporaryDirectory() as brut:
        dossier = Path(brut)
        marque = "id -un > " + shlex.quote(str(dossier / "trace"))

        correct = {
            "lang": "fr", "locale": "fr_FR.UTF-8", "xkb": "fr",
            "xkb_variant": "azerty", "tz": "Europe/Paris",
            "orient": "3", "mode": "1", "disk": "/dev/sda",
        }

        essais = [
            ("substitution de commande", {**correct, "tz": "$(" + marque + ")"}),
            ("sortie des guillemets", {**correct, "lang": 'fr"; ' + marque + '; x="'}),
            ("backticks", {**correct, "locale": "`" + marque + "`"}),
            ("separateur dans orient", {**correct, "orient": "1; " + marque}),
            ("chemin disque detourne", {**correct, "disk": "/dev/sda; " + marque}),
            ("retour a la ligne", {**correct, "xkb_variant": "az\n" + marque}),
            ("valeurs legitimes", correct),
        ]

        # PINCABOS_ANSWERS_QUOTING_V2
        # Le second bord : des valeurs exotiques mais reelles doivent passer.
        # Un moule trop etroit ne protege de rien, il refuse l'utilisateur.
        LEGITIMES = [
            ("clavier latino-americain", {**correct, "xkb": "latam"}),
            ("clavier braille", {**correct, "xkb": "brai"}),
            ("fuseau a trois segments",
             {**correct, "tz": "America/Argentina/Buenos_Aires"}),
            ("fuseau avec decalage", {**correct, "tz": "Etc/GMT+1"}),
            ("locale minimale", {**correct, "locale": "C.UTF-8"}),
            ("variante de disposition",
             {**correct, "xkb_variant": "nodeadkeys"}),
            ("orientation 180", {**correct, "orient": "4"}),
            ("mode mise a jour", {**correct, "mode": "3"}),
        ]

        echecs = 0
        for nom, reponse in LEGITIMES:
            contenu, verdict = install(rules, reponse)
            if contenu is None:
                echecs += 1
                print("  " + nom.ljust(28) + " -> REFUSE A TORT — ECHEC")
            elif execute_quelque_chose(contenu, dossier):
                echecs += 1
                print("  " + nom.ljust(28) + " -> ACCEPTE ET EXECUTE — ECHEC")
            else:
                print("  " + nom.ljust(28) + " -> accepte, inerte")

        for nom, reponse in essais:
            contenu, verdict = install(rules, reponse)
            if contenu is None:
                print("  " + nom.ljust(28) + " -> " + verdict)
                continue
            if execute_quelque_chose(contenu, dossier):
                echecs += 1
                print("  " + nom.ljust(28) + " -> ACCEPTE ET EXECUTE — ECHEC")
            else:
                print("  " + nom.ljust(28) + " -> " + verdict + ", inerte")

        # Seconde barriere seule : si une validation cedait un jour.
        contenu = "PCO_ANS_TZ=" + shlex.quote("$(" + marque + ")") + "\n"
        if execute_quelque_chose(contenu, dossier):
            echecs += 1
            print("  citation seule               -> EXECUTE — ECHEC")
        else:
            print("  citation seule               -> inerte")

    print()
    print("  " + ("tout est bloque" if not echecs else str(echecs) + " echec(s)"))
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
