"""Chargement des moteurs PinCabOS pour les tests.

Les moteurs sont des executables sans extension ou avec un tiret dans le nom
(pincabos-screen-topology.py, pincabos-zedmd, backboard-engine.py) : on les
charge par chemin, sans les executer (leur main() est garde par __name__).
"""
import importlib.machinery
import importlib.util
import os
import sys

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def charger(rel, nom):
    chemin = os.path.join(RACINE, rel)
    loader = importlib.machinery.SourceFileLoader(nom, chemin)
    spec = importlib.util.spec_from_loader(nom, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[nom] = module
    loader.exec_module(module)
    return module


# PINCABOS_INSTALLEUR_FICHIERS_V1 : le moteur d installation, le helper de payload,
# l attente et l unite tty sont des fichiers livres (opt/pincabos/script/installer/).
# Les tests qui verifiaient « ce qu iso.sh installe » lisent l ensemble, iso.sh d abord.
FICHIERS_INSTALLATEUR = (
    "opt/pincabos/script/iso.sh",
    "opt/pincabos/script/installer/pincabos-install-payload",
    "opt/pincabos/script/installer/pincabos-live-installer",
    "opt/pincabos/script/installer/pincabos-live-installer-wait",
    "opt/pincabos/script/installer/pincabos-live-installer-tty.service",
)


def texte_installateur():
    return "\n".join(open(os.path.join(RACINE, rel), encoding="utf-8").read() for rel in FICHIERS_INSTALLATEUR)


def texte_fichier_livre(nom):
    """Le contenu d un fichier livre de l installateur (moteur, helper, attente, unite)."""
    return open(os.path.join(RACINE, "opt/pincabos/script/installer", nom), encoding="utf-8").read()
