# libdof canonique (source unique) — PinCabOS

Ce dossier contient **l'unique** `libdof.so.0.4.7` réellement chargé par PinCabOS,
pour DOF au **menu** (vpinfe) **et** en **jeu** (plugin DOF de VPX).

## Pourquoi

libdof est *vendored* par deux projets amont (vpinfe l'embarque dans `_internal`,
VPX dans `plugins/dof`). Pour patcher libdof sans modifier ces bundles, PinCabOS
détourne le chargement via des overlays (`LD_LIBRARY_PATH` / `LD_PRELOAD`). Ces
overlays avaient **divergé en deux copies** :

- `overlays/vpinfe-dof-ledwiz-hidraw-stable/` → chargé par vpinfe
  (`run-vpinfe-systemd.sh`, `LD_LIBRARY_PATH`).
- `overlays/libdof-ledwiz-hidraw-stable/` → chargé par VPX
  (`VPXlauncher.pincabos-original.sh`, `LD_PRELOAD` + `LD_LIBRARY_PATH`).

Rien ne les tenait synchronisées : un correctif appliqué à l'une (menu) laissait
l'autre (jeu) sur un libdof buggé. Symptôme concret : avec une **Dude's Cab + un
TeensyStripController**, la sortie de table plantait par intermittence
(`double free` / `free(): invalid pointer`) — use-after-free dans
`DudesCab::~DudesCab()` (le libdof en jeu n'avait jamais reçu le correctif).

## Solution

**Un seul binaire canonique**, et les deux overlays le **référencent par symlink** :

    overlays/vpinfe-dof-ledwiz-hidraw-stable/libdof.so.0.4.7  ->  ../libdof-canonical/libdof.so.0.4.7
    overlays/libdof-ledwiz-hidraw-stable/libdof.so.0.4.7      ->  ../libdof-canonical/libdof.so.0.4.7

Mettre à jour libdof = remplacer **ce seul fichier**. Menu et jeu sont toujours
d'accord ; plus de divergence possible. Les launchers sont inchangés (ils pointent
sur leur dossier overlay, dont le `libdof.so.0.4.7` est désormais un symlink).

Les autres fichiers des overlays (libdof_python.so, dof.py, libhidapi, libusb…)
restent propres à chaque consommateur : seul `libdof.so.0.4.7` est mutualisé.

## Provenance de ce binaire

- Source : https://github.com/vpinball/libdof, master `0383246`
  (**PR #66** — `dudescab: align Finish and destructor with c#`, qui corrige le
  use-after-free du teardown DudesCab ; alternative retenue à la PR #65).
- sha256 : `9e1753f6336a456683bfc7bd58ff375792f2a6ad67c8ff542036b4179adb03f1`
- Validé sur cab réel (Dude's Cab + Teensy backboard 144×16) : menu + en jeu,
  **0 crash** sur de nombreuses sorties de table (auparavant ~2-3 sur 16).
- Mise à jour future : quand une release libdof ≥ #66 est disponible, remplacer
  ce fichier par le `.so` officiel (le binaire custom devient inutile).
