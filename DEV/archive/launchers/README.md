# Launchers archives

Hors perimetre de release (`DEV/` n'est jamais livre) ; les cabinets les
perdent via `remove.list`. Conserves ici pour reference, avec leur historique
git (`git log --follow`).

- `pincabos-hybrid-launch.sh` — ancien launcher hybride (V12, Original / PuP
  au choix). Remplace par `opt/pincabos/launchers/pincabos-launch-core.sh`
  (mode `hybrid`), qui est ce que `vpinfe.ini` appelle.
- `pincabos-hybrid-chooser.py` (+ inventaire) — ancienne copie du chooser,
  utilisee uniquement par ce launcher ; la copie vivante est
  `opt/pincabos/launchers/pincabos-hybrid-chooser.py`.
- `VPinFE.sh` — ancien lanceur du frontend, remplace par
  `opt/pincabos/tools/run-vpinfe-systemd.sh` (service `pincabos-vpinfe`).

La chaine de lancement en vigueur est decrite dans
`opt/pincabos/launchers/README.md`.
