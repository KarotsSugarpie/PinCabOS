#!/usr/bin/env python3
"""Confronte la liste de preservation a ce que la machine range vraiment.

PINCABOS_KEEP_INVENTORY_V1

Une liste de preservation ecrite de memoire oublie toujours quelque chose, et
l'oubli ne se voit qu'apres coup, quand un reglage a disparu. Ce controle
prend le probleme dans l'autre sens : il parcourt ce que la machine stocke et
signale ce qu'une mise a jour effacerait.

Il ne decide pas a la place de l'humain — il pose la question, fichier par
fichier, pour que l'absence soit un choix et non un oubli.

  pincabos-verifier-preservation.py [--racine /]   -> 0 si rien d'inattendu
"""
import argparse
import re
import sys
from pathlib import Path

MOTEUR = Path(__file__).resolve().parents[1] / "script/iso.sh"

# Ce que l'image sait refaire : gabarits, politiques, manifestes, caches. Leur
# absence de la liste est deliberee, pas un oubli.
ATTENDU_ABSENT = {
    "about-supporters.json",      # contenu editorial, livre par l'image
    "distribution",               # politiques de distribution, livrees
    "github-rootfs-exclude.txt",  # regle de build
    "pincabos-apt-essential-packages.txt",
    "pincabos-cleanup-policy.conf",
    "pincabos-publish-policy.conf",
    "pincabos-paths.json",        # chemins internes, livres
    "mimeapps.list",              # vide, regenere par la session
    "version.json",               # doit venir de la nouvelle image
    "firstrun.json",              # l'etat de premier demarrage se refait
    "feedback-server.json",       # adresse du service, livree
    "dev-feedback.env",           # outillage de developpement
    "dev-login.txt",              # outillage de developpement
    "screens",                    # deja couvert par une entree dediee
    "display-aliases.env",        # idem
    "audio/audio-baseline.txt",   # releve de la machine de construction
}


def liste_preservee():
    texte = MOTEUR.read_text(encoding="utf-8", errors="surrogateescape")
    bloc = re.search(r"PCO_KEEP_PATHS=\((.*?)\n\)", texte, re.S)
    if not bloc:
        raise SystemExit("NOGO: PCO_KEEP_PATHS introuvable")
    return {m.group(1) for m in re.finditer(r'"([^"]+)"', bloc.group(1))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--racine", default="/",
                        help="racine du systeme a inspecter")
    args = parser.parse_args()

    gardes = liste_preservee()
    config = Path(args.racine) / "opt/pincabos/config"

    if not config.is_dir():
        print("  " + str(config) + " absent : rien a verifier")
        return 0

    # PINCABOS_KEEP_INVENTORY_V2
    # On descend dans les sous-repertoires : s'arreter au premier niveau
    # revient a fermer les yeux sur tout ce qu'un repertoire contient.
    def candidats(base):
        for entree in sorted(base.iterdir()):
            nom = entree.relative_to(config).as_posix()
            if nom.endswith(".manifest") or nom.split("/")[-1].startswith("apt-"):
                continue
            if nom in ATTENDU_ABSENT:
                continue

            rel = "opt/pincabos/config/" + nom
            couvert = any(rel == g or rel.startswith(g + "/") for g in gardes)
            if couvert:
                continue
            # Un repertoire dont seule une partie est gardee doit etre ouvert :
            # sinon la partie non gardee reste invisible.
            if entree.is_dir() and any(g.startswith(rel + "/") for g in gardes):
                yield from candidats(entree)
                continue
            yield rel

    oublis = list(candidats(config))

    if oublis:
        print("  Une mise a jour effacerait ces reglages, et ils ne sont pas")
        print("  declares comme jetables :")
        for rel in oublis:
            print("    " + rel)
        print()
        print("  Ajoute-les a PCO_KEEP_PATHS, ou a ATTENDU_ABSENT si l'image")
        print("  sait les refaire.")
        return 1

    print("  " + str(len(gardes)) + " chemins preserves ; aucun reglage inattendu")
    print("  ne serait perdu par une mise a jour.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
