# PinCabOS Multiplayer — AFM Hot Replica V7 GO

> Validation expérimentale du noyau physique de réplication chaude pour le mode multijoueur PinCabOS.
>
> Date : 2026-09-03  
> Dépôt : `PinCabOs/PinCabOS`  
> Table pilote : `Attack from Mars (Bally 1995)`  
> ROM : `afm_113b`  
> Document maître : `DEV/PINCABOS_VPX_MULTIPLAYER_MASTER_REPLICA.md`  
> Rapport d'étude : `DEV/PINCABOS_VPX_MULTIPLAYER_AFM_RECORD_REPLAY_STUDY_2026-09-03.md`

## Résultat

**GO — noyau physique de hot replica validé sur AFM pour une fenêtre de 10 secondes.**

Le test V7 a démontré simultanément :

- réplication autoritaire de la position de bille `X/Y/Z` ;
- réplication autoritaire de la vitesse `VelX/VelY/VelZ` ;
- réplication des flippers depuis les états `LFO/RFO` enregistrés dans le PCOSREC ;
- aucune injection d'input flipper vers la ROM depuis le hook ;
- aucun `Controller.Switch()` ajouté par le code LAB ;
- aucune modification de VPX/BGFX/VPinFE/B2S/ScoreView ;
- table chargée normalement avant activation du hook ;
- synchronisation déclenchée après armement explicite.

## Preuve d'exécution

```text
PCOSSTATE|V7_ARMED|GAMETIME|20000
PCOSSTATE|V7_SYNC_START|GAMETIME|20150
PCOSSTATE|V7_PROGRESS|T|0|FRAMES|0|B|0|L|0|R|0
PCOSSTATE|V7_PROGRESS|T|2000|FRAMES|100|B|63|L|0|R|0
PCOSSTATE|V7_PROGRESS|T|4000|FRAMES|200|B|163|L|0|R|0
PCOSSTATE|V7_PROGRESS|T|6000|FRAMES|300|B|263|L|2|R|3
PCOSSTATE|V7_PROGRESS|T|8000|FRAMES|400|B|363|L|2|R|4
PCOSSTATE|V7_PROGRESS|T|10000|FRAMES|500|B|463|L|5|R|7
PCOSSTATE|V7_DONE|T|10000|FRAMES|500|B_SEEN|463|APPLIED|463|MISSING|0
PCOSSTATE|V7_FLIPPERS|LEFT_CHANGES|5|RIGHT_CHANGES|7
```

## Mesures

| Mesure | Résultat |
|---|---:|
| Durée test | 10.000 s |
| Frames PCOSREC traitées | 500 |
| États de bille vus | 463 |
| États de bille appliqués | 463 |
| États de bille manquants | 0 |
| Taux d'application bille | 100 % |
| Changements flipper gauche | 5 |
| Changements flipper droit | 7 |

## Validation visuelle

L'opérateur a confirmé que :

- la bille reste très fluide ;
- le comportement est comparable ou supérieur au test V6 ;
- les flippers bougent automatiquement selon l'enregistrement ;
- aucun bouton flipper n'a besoin d'être pressé ;
- le résultat est jugé « parfait », « concluant » et « très fluide ».

Cette observation complète les compteurs techniques : la réplication n'est pas seulement acceptée par le script, elle est visible de façon cohérente sur le playfield.

## Conclusion architecturale

Ce test valide expérimentalement la base du modèle :

```text
MASTER
  -> état bille XYZ
  -> vitesse bille VX/VY/VZ
  -> état flippers
  -> REPLICA
```

La conclusion est désormais plus forte que le simple replay d'inputs :

> une instance VPX peut être pilotée comme réplique chaude à partir d'un flux d'état autoritaire sans exiger que sa physique locale reproduise déterministiquement le maître.

Cela confirme le choix **Master/Replica + deltas/snapshots autoritaires** comme architecture principale du mode multijoueur PinCabOS.

## Ce que V7 ne valide pas encore

V7 ne permet pas encore de déclarer le multijoueur complet fonctionnel. Restent notamment à valider :

- réplication sur toute une minute et sur une partie complète ;
- identité persistante et cycle de vie des billes en multiball ;
- création/destruction des billes ;
- switches ROM et état PinMAME nécessaires à la cohérence logique ;
- objets de table dynamiques autres que bille/flippers ;
- lampes/flashers/solénoïdes utiles au rendu ;
- snapshots complets et restauration ;
- checksums de dérive ;
- deuxième cabinet réel ;
- transport réseau LAN puis Internet ;
- latence/jitter/perte de paquets ;
- transfert d'autorité entre joueurs ;
- prévention du split-brain ;
- runtime final isolé `VPX_MultiPlayers`.

## Décision de développement

**GO pour poursuivre la stratégie hot replica.**

Ordre recommandé :

1. étendre V7 à la durée complète du PCOSREC ;
2. mesurer les manquants lors des changements de bille/multiball ;
3. ajouter une identité de bille persistante et les événements `BALL_CREATE/BALL_DESTROY` ;
4. ajouter les états ROM/switch strictement nécessaires ;
5. introduire checksums et snapshots ;
6. reproduire le même flux sur un deuxième cabinet en LAN ;
7. tester ensuite le handoff du maître.

## Statut Phase 3

- Input replay externe : **GO transport**.
- PCOSREC temps réel : **GO**.
- XYZ autoritaire : **GO**.
- XYZ + vélocité : **GO**.
- Flippers répliqués : **GO**.
- Hot replica physique de base : **GO**.
- Partie complète / ROM / lifecycle / réseau / handoff : **PENDING**.
