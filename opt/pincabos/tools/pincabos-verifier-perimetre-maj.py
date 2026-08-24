#!/usr/bin/env python3
"""Verifie ce qu'une mise a jour GitHub laisse passer, et ce qu'elle refuse.

PINCABOS_UPDATE_SCOPE_V2

Le filtre de chemins decide, fichier par fichier, de ce qu'une release
installe. Trop etroit, il livre une fonction a moitie — une unite sans son
binaire, un binaire sans son activation — ce qui est plus mauvais que ne rien
livrer. Trop large, il autorise une release a ecraser les tables et les
reglages du joueur.

Ce controle verifie les deux bords a la fois, contre la fonction reellement
presente dans le moteur de mise a jour.

  pincabos-verifier-perimetre-maj.py   -> 0 si le perimetre est juste
"""
import importlib.util
import sys
from pathlib import Path

MOTEUR = Path(__file__).resolve().parents[1] / "update/pincabos_updates.py"

DOIT_PASSER = [
    "opt/pincabos/web/app.py",
    "opt/pincabos/scripts/pincabos-screen-topology.py",
    "opt/pincabos/tools/pincabos-generer-voix-audio.py",
    "opt/pincabos/media/audio-voix/fr/side-left.opus",
    "opt/pincabos/installer-gui/app.py",
    "usr/local/lib/pincabos/pincabos-dashboard-live-webrtc",
    "usr/local/libexec/pincabos/pincabos-vpinfe-focus-playfield",
    "usr/local/sbin/pincabos-audio-surround",
    "etc/systemd/system/pincabos-audio-surround.service",
    "etc/systemd/system/multi-user.target.wants/pincabos-audio-surround.service",
    "etc/systemd/system/pincabos-vpinfe.service.wants/pincabos-vpinfe-focus.service",
    "etc/systemd/system/pincabos-gui-kiosk.service.d/10-wait-for-wizard.conf",
    "etc/sudoers.d/pincabos-audio-surround",
    # Prefixe numerique d'ordonnancement : la moitie des fichiers livres
    # dans ces repertoires en portent un.
    "etc/sudoers.d/91-pincabos-dashboard-admin",
    "etc/polkit-1/rules.d/49-pincabos-pinball-root.rules",
    "etc/udev/rules.d/99-pincab-ledwiz.rules",
    "etc/lightdm/lightdm.conf.d/50-pincabos.conf",
    "etc/tmpfiles.d/pincabos-dudescab.conf",
    "home/pinball/.config/openbox/autostart",
    "home/pinball/.config/vpinfe/themes/PinCabOS/theme.js",
    # Surcharge d'une unite PinCabOS : le drop-in ne porte pas notre nom,
    # mais le repertoire qui l'accueille, si.
    "etc/systemd/system/pincabos-vpinfe.service.d/50-dof.conf",
]

DOIT_BLOQUER = [
    # Donnees du joueur : une release n'a rien a y ecrire.
    "home/pinball/Tables/ma-table.vpx",
    "home/pinball/.config/vpinfe/vpinfe.ini",
    "home/pinball/.local/share/VPinballX/10.8/VPinballX.ini",
    # Unites qui ne sont pas a PinCabOS. Notre nom dans le nom du FICHIER
    # ne suffit pas : ce qui compte est l'unite reellement surchargee.
    "etc/systemd/system/getty@tty1.service.d/override.conf",
    "etc/systemd/system/multi-user.target.wants/ssh.service",
    "etc/systemd/system/ssh.service.d/pincabos-backdoor.conf",
    "etc/systemd/system/getty@tty1.service.d/pincabos-tty.conf",
    "etc/systemd/system/a/b/pincabos-profond.conf",
    # Un theme qui n'est pas le notre reste la propriete du joueur.
    "home/pinball/.config/vpinfe/themes/Revolution/theme.js",
    # Repertoires de /etc ou un fichier de trop donne les pleins pouvoirs.
    # Y etre range ne suffit pas : le fichier doit etre a nous.
    "etc/sudoers.d/00-porte-derobee",
    "etc/sudoers.d/README",
    "etc/polkit-1/rules.d/10-tout-permis.rules",
    "etc/udev/rules.d/ubuntu--vg-ubuntu--lv.rules",
    "etc/lightdm/lightdm.conf.d/01_debian.conf",
    "etc/sudoers.d/sous/pincabos-x",
    # Systeme.
    "etc/passwd",
    "etc/shadow",
    # Sorties d'echappement.
    "../../etc/shadow",
    "/etc/shadow",
    # Repertoires exclus de longue date.
    "opt/pincabos/web/.venv/lib/x.py",
    "opt/pincabos/logs/hier.log",
    # Media hors annonces : les tables et videos ne passent pas par la.
    "opt/pincabos/media/tables/gros.mp4",
]


def charger():
    spec = importlib.util.spec_from_file_location("pco_updates", MOTEUR)
    module = importlib.util.module_from_spec(spec)
    garde = sys.argv
    sys.argv = ["pincabos-verifier-perimetre-maj"]
    try:
        spec.loader.exec_module(module)
    except SystemExit:
        pass
    finally:
        sys.argv = garde
    return module.allowed


def main() -> int:
    allowed = charger()
    echecs = 0

    for chemin in DOIT_PASSER:
        if not allowed(chemin):
            echecs += 1
            print("  ECHEC  devrait passer  : " + chemin)

    for chemin in DOIT_BLOQUER:
        if allowed(chemin):
            echecs += 1
            print("  ECHEC  devrait bloquer : " + chemin)

    total = len(DOIT_PASSER) + len(DOIT_BLOQUER)
    if echecs:
        print()
        print("  " + str(echecs) + " erreur(s) sur " + str(total) + " cas")
        return 1

    print("  " + str(total) + " cas verifies : perimetre juste des deux cotes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
