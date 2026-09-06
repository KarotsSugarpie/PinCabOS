#!/usr/bin/env python3
"""Modèles du compte du joueur (PINCABOS_MODELES_JOUEUR_V1).

Ce que PinCabOS attend dans /home/pinball et qui n'est pas une donnée du joueur
vit dans /opt/pincabos/templates/home (miroir de l'arborescence du compte) :
vpinfe.ini et ses bases de départ, thème Revolution, réglages du tableau de
bord, unités PipeWire de la session, Sunshine, l'ini VPX de référence et sa
configuration DOF, gamecontrollerdb. L'installateur les pose dans la cible,
le premier démarrage complète ce qui manque : un fichier déjà présent n'est
jamais écrasé (sauf --force), ce sont les fichiers du joueur.

Restent livrés directement dans le compte par la mise à jour OTA (chemins
exacts de pincabos_updates.allowed) : .config/openbox/autostart et le thème
VPinFE PinCabOS, mis à jour à chaud à chaque release.

  pincabos-home-templates apply [--root DIR] [--force] [--dry-run]
"""
import argparse
import os
import shutil
import sys
from pathlib import Path

TEMPLATES = Path("/opt/pincabos/templates/home")
HOME = Path("/home/pinball")
UID, GID = 1000, 1000


def _proprietaire(chemin: Path, uid: int, gid: int):
    if os.geteuid() != 0:
        return
    try:
        os.chown(chemin, uid, gid, follow_symlinks=False)
    except OSError:
        pass


def poser(templates: Path = TEMPLATES, home: Path = HOME, force: bool = False, dry_run: bool = False,
          uid: int = UID, gid: int = GID) -> list:
    """Copie chaque modèle absent du compte (tous si force). Journal GO/WARN par ligne."""
    journal = []
    if not templates.is_dir():
        return [f"WARN: modeles absents : {templates}"]
    poses = gardes = 0
    for src in sorted(p for p in templates.rglob("*") if p.is_file() or p.is_symlink()):
        rel = src.relative_to(templates)
        dst = home / rel
        if dst.exists() or dst.is_symlink():
            if not force:
                gardes += 1
                continue
        if dry_run:
            journal.append(f"GO: poserait {rel}")
            poses += 1
            continue
        for d in reversed(list(dst.relative_to(home).parents)[:-1]):
            dossier = home / d
            if not dossier.exists():
                dossier.mkdir(parents=True, exist_ok=True)
                _proprietaire(dossier, uid, gid)
        if src.is_symlink():
            if dst.is_symlink() or dst.exists():
                dst.unlink()
            os.symlink(os.readlink(src), dst)
        else:
            shutil.copy2(src, dst)
        _proprietaire(dst, uid, gid)
        poses += 1
    journal.append(f"GO: modeles du joueur : {poses} pose(s), {gardes} deja present(s) (gardes)")
    return journal


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Pose les modeles du compte du joueur")
    sub = ap.add_subparsers(dest="cmd")
    a = sub.add_parser("apply", help="pose ce qui manque dans /home/pinball")
    a.add_argument("--root", default="/", help="racine d une cible d installation (les chemins /opt et /home sont pris sous cette racine)")
    a.add_argument("--force", action="store_true", help="ecrase les fichiers existants (jamais par defaut)")
    a.add_argument("--dry-run", action="store_true")
    sub.add_parser("list", help="liste les modeles")
    args = ap.parse_args(argv)
    if args.cmd == "list":
        for p in sorted(x for x in TEMPLATES.rglob("*") if x.is_file()):
            print(p.relative_to(TEMPLATES))
        return 0
    if args.cmd != "apply":
        ap.print_help()
        return 2
    root = Path(args.root)
    templates = root / TEMPLATES.relative_to("/")
    home = root / HOME.relative_to("/")
    journal = poser(templates, home, force=args.force, dry_run=args.dry_run)
    print("\n".join(journal))
    return 0 if not any(l.startswith("NOGO") for l in journal) else 1


if __name__ == "__main__":
    sys.exit(main())
