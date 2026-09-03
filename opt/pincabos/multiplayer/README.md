# PinCabOS Sync — fondation cabinet V1

Cette arborescence prépare l'agent externe prévu par
`DEV/PINCABOS_VPX_MULTIPLAYER_MASTER_REPLICA.md`.

État de cette PR : **inactif par défaut**.

- aucun listener réseau;
- aucun service systemd activé;
- aucun lancement de table;
- aucune écriture dans VPX BGFX, VPinFE ou leurs configurations;
- aucune modification du heartbeat ou du jeton PinCabOS Link;
- aucune commande arbitraire provenant du réseau.

Les seules fonctions livrées sont le décodage strict d'enveloppes signées,
la machine d'état locale anti-rejeu/anti-double-maître, le conteneur de preuve
`PCOSREC v0` et un audit en lecture seule des fichiers protégés.

## Tests hors cabinet

```bash
PYTHONPATH=opt/pincabos/multiplayer \
  python3 -m unittest discover -s opt/pincabos/multiplayer/tests -v
```

## Audit local en lecture seule

```bash
PYTHONPATH=/opt/pincabos/multiplayer \
  python3 -m pincabos_sync.cli audit --json
```

L'audit indique `transport_active: false` et `launcher_active: false` tant
qu'une étape ultérieure, testée sur deux cabinets, n'a pas explicitement
autorisé ces fonctions.
