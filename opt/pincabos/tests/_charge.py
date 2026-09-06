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


# PINCABOS_CIBLE_FICHIERS_DU_DEPOT_V1 : ce que le helper ne reecrit plus, la cible le tient du depot porte dans l image
FICHIERS_CIBLE = (
    "etc/sudoers.d/99-pincabos-pinball-root",
    "etc/polkit-1/rules.d/49-pincabos-pinball-root.rules",
    "usr/local/sbin/pincabos-firstboot-network-webapp-fix",
    "etc/systemd/system/pincabos-firstboot-network-webapp-fix.service",
    "etc/systemd/system/pincabos-webapp.service.d/90-pincabos-stable-start.conf",
    "usr/local/sbin/pincabos-webapp-fallback-start",
    "etc/systemd/system/pincabos-webapp-fallback.service",
    "usr/local/sbin/pincabos-firstboot-hardware-autoconfig",
    "etc/systemd/system/pincabos-firstboot-hardware-autoconfig.service",
    "etc/systemd/system/pincabos-screen-topology-boot.service",
    "usr/local/libexec/pincabos/pincabos-vpinfe-display-sanitize",
    "usr/local/libexec/pincabos/pincabos-vpinfe-prestart-guard",
    "etc/systemd/system/pincabos-vpinfe.service.d/45-pincabos-vpinfe-prestart-guard.conf",
    "etc/systemd/system/pincabos-vpinfe.service.d/90-pincabos-iso-start.conf",
    "usr/local/sbin/pincabos-firstboot-vpinfe-packaged-runtime-fix",
    "etc/systemd/system/pincabos-firstboot-vpinfe-packaged-runtime-fix.service",
    "usr/local/sbin/pincabos-firstboot-initramfs-refresh",
    "etc/systemd/system/pincabos-firstboot-initramfs-refresh.service",
)


def texte_installateur():
    # PINCABOS_OUTILS_CIBLE_V1 : les outils Python appliques a la cible par le helper sont des fichiers (tools/cible/)
    import glob
    outils = sorted(glob.glob(os.path.join(RACINE, "opt/pincabos/tools/cible", "*.py")))
    return "\n".join(open(chemin, encoding="utf-8").read() for chemin in
                     [os.path.join(RACINE, rel) for rel in FICHIERS_INSTALLATEUR + FICHIERS_CIBLE] + outils)


def texte_fichier_livre(nom):
    """Le contenu d un fichier livre de l installateur (moteur, helper, attente, unite)."""
    return open(os.path.join(RACINE, "opt/pincabos/script/installer", nom), encoding="utf-8").read()
