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
