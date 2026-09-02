# Lancement d'une table — la chaîne, et rien d'autre

Un seul chemin d'exécution, du frontend au binaire VPX. Chaque maillon a un
rôle précis ; il n'existe **aucun autre launcher** dans le dépôt.

```
vpinfe.ini  vpxbinpath = /opt/pincabos/launchers/pincabos-launch-hybrid.sh
   │
   ▼
launchers/pincabos-launch-hybrid.sh        3 lignes : exec launch-core hybrid
launchers/pincabos-launch-original.sh      3 lignes : exec launch-core original   (tests)
launchers/pincabos-launch-puppack.sh       3 lignes : exec launch-core pup        (tests)
   │
   ▼
launchers/pincabos-launch-core.sh          détecte les modes de la table (Original / PuP-Pack),
   │                                       affiche le chooser si les deux existent
   │                                       (launchers/pincabos-hybrid-chooser.py), verrou,
   │                                       masque/démasque le PuP local, puis :
   ▼
scripts/VPXlauncher.real.sh                politique DMD / FullDMD (pincabos-native-fulldmd-policy),
   │                                       placement des fenêtres (pincabos-place-front-windows),
   │                                       polices PuP, curtain VPinFE, puis :
   ▼
scripts/VPXlauncher.pincabos-original.sh   environnement d'exécution : lien stable ~/vpx,
   │                                       préférences -PrefPath ~/.pincabos/vpx, libdof et
   │                                       hidapi (LedWiz/DudesCab), exec VPinballX_BGFX
   ▼
VPinballX_BGFX -PrefPath /home/pinball/.pincabos/vpx -play <table.vpx>
```

`scripts/VPXlauncher.sh` (4 lignes) est l'**alias historique** : il exécute
`pincabos-launch-hybrid.sh`. Il reste parce que la WebApp, le doctor,
`tabletest` et `iso.sh` le citent ; ne rien y ajouter.

## Ce qui a été retiré, et pourquoi

- `opt/pincabos/bin/pincabos-hybrid-launch.sh` — ancien launcher hybride
  (V12), remplacé par `launchers/pincabos-launch-core.sh`. Plus référencé
  nulle part, mais son nom à une lettre près du vrai a coûté des heures de
  diagnostic.
- `opt/pincabos/bin/pincabos-hybrid-chooser.py` — ancienne copie du chooser,
  utilisée uniquement par ce launcher mort.
- `opt/pincabos/scripts/VPinFE.sh` — ancien lanceur du frontend, remplacé par
  `opt/pincabos/tools/run-vpinfe-systemd.sh` (service `pincabos-vpinfe`).

Les cabinets existants les perdent à la mise à jour suivante
(`remove.list` de la release, liste `legacy` dans
`opt/pincabos/update/build_release_v4.py`).

## Règles

- Un nouveau comportement au lancement va dans le maillon dont c'est le rôle
  (détection → `launch-core`, affichage → `VPXlauncher.real`, environnement
  → `VPXlauncher.pincabos-original`). Jamais un nouveau fichier « launcher ».
- Les chemins et versions (VPX, bibliothèques) ne sont pas figés : lien
  stable `~/vpx`, soname `.so.0`, jamais un nom de fichier versionné.
- Tout changement ici se valide **table par table sur un cabinet réel**
  (Original, PuP-Pack, hybride) avant fusion.
