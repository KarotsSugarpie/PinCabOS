# Audit de nettoyage PinCabOS

Source auditée : `376944e1a4fea29df52ab5970ace0d1b509ffc9c`

Aucune suppression n’a été effectuée. Cette liste sépare les déchets certains, les composants dormants et les éléments qui exigent une validation d’usage.

## Priorité haute — hygiène du dépôt

- 5 fichiers d’état sous `root/` : historiques temporaires, BrowserMetrics, session D-Bus et rapports de sync vides.
- 9 fichiers d’état/cache sous `var/lib/pincabos`.
- 7 sauvegardes de configuration horodatées suivies par Git.
- 16 fichiers dans le snapshot d’exécution `opt/pincabos/install/.completed-final-*`.

## Code dormant ou non référencé

- Runtime patches : 5 fichiers Python avec 4 activateurs `.pth` désactivés. Aucun chargeur actif détecté.
- Ancienne pile display-role : 4 scripts Python encore présents alors que ses unités sont masquées vers `/dev/null`. À conserver jusqu’à validation de la pile screen-topology.
- 7 exécutables Python autonomes sans référence détectée. Vérifier l’usage manuel avant suppression.

## Duplications importantes

- Manifestes APT : 42 fichiers horodatés pour seulement 4 contenus uniques.
- Modules d’installation : 4 paires identiques entre `opt/pincabos/install/modules` et `opt/pincabos/modules`.
- Overlays DOF : 106 fichiers, 152.1 MiB, seulement 27 blobs uniques.
- 8 scripts root liés à d’anciens numéros de PR à déplacer vers DEV/archive ou supprimer après validation.

## À ne pas supprimer

- `opt/pincabos/web/pincabos_batch_import_worker_v2.py`, `opt/pincabos/web/pincabos_media_recorder_worker.py` — Both are activated by dedicated systemd services.
- `opt/pincabos/bin/pincabos-hybrid-chooser.py`, `opt/pincabos/launchers/pincabos-hybrid-chooser.py` — Both same-named variants are referenced by a launcher in their own directory and are not duplicates.
- `opt/pincabos/web/validate_refactor.py` — Standalone static validation script; absence of an importer does not make it dead.

Le détail exact de chaque chemin et le niveau de confiance sont dans `cleanup-candidates.json`.
