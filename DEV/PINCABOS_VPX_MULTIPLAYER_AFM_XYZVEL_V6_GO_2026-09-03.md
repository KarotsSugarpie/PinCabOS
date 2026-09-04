# PinCabOS Multiplayer — AFM XYZ+VEL V6 GO

> Validation laboratoire du noyau physique d’une hot replica PinCabOS.
>
> **Date :** 2026-09-03  
> **Table pilote :** Attack from Mars (Bally 1995)  
> **ROM :** `afm_113b`  
> **Source d’autorité :** `PCOSREC-v0-20260903-210610.log`  
> **Étude liée :** `DEV/PINCABOS_VPX_MULTIPLAYER_AFM_RECORD_REPLAY_STUDY_2026-09-03.md`

## Résultat

**GO — réplication physique XYZ + vélocité validée.**

Le test V6 a appliqué en temps réel les propriétés suivantes depuis l’enregistrement maître :

- `Ball.X`
- `Ball.Y`
- `Ball.Z`
- `Ball.VelX`
- `Ball.VelY`
- `Ball.VelZ`

Aucun flipper n’a été forcé par le hook. Aucun switch PinMAME/ROM n’a été écrit par le hook. Start et Plunger ont été injectés extérieurement via le runner déjà validé.

## Mesures observées

```text
PCOSSTATE|V6_ARMED|GAMETIME|20000
PCOSSTATE|V6_SYNC_START|GAMETIME|20140
PCOSSTATE|V6_PROGRESS|T|0|SEEN|0|APPLIED|0|MISSING|0
PCOSSTATE|V6_PROGRESS|T|2000|SEEN|63|APPLIED|63|MISSING|0
PCOSSTATE|V6_PROGRESS|T|4000|SEEN|163|APPLIED|163|MISSING|0
PCOSSTATE|V6_PROGRESS|T|6000|SEEN|263|APPLIED|263|MISSING|0
PCOSSTATE|V6_PROGRESS|T|8000|SEEN|363|APPLIED|363|MISSING|0
PCOSSTATE|V6_PROGRESS|T|10000|SEEN|463|APPLIED|463|MISSING|0
PCOSSTATE|V6_DONE|T|10000|B_SEEN|463|APPLIED|463|MISSING|0
```

Résumé :

| Mesure | Résultat |
|---|---:|
| États de bille vus | 463 |
| États appliqués | 463 |
| États manquants | 0 |
| Taux d’application | 100 % |
| Fenêtre test | 10 s |
| Hook armé | GameTime 20000 ms |
| Début synchronisé | GameTime 20140 ms |

Runner externe :

```text
Start KD   : 14.51 ms
Start KU   : 286.60 ms
Plunger KD : 3110.65 ms
Plunger KU : 3358.57 ms
```

## Validation visuelle

Le testeur confirme une trajectoire :

> « très fluide voir excellent »

Par rapport à V5, l’ajout des vitesses autoritaires supprime pratiquement la lutte visible entre la position imposée et la physique locale intermédiaire.

## Comparaison V5 → V6

### V5 — XYZ seulement

- 463 états vus ;
- 456 appliqués ;
- 7 manquants ;
- trajectoire imposée fonctionnelle mais corrections plus visibles.

### V6 — XYZ + VelXYZ

- 463 états vus ;
- 463 appliqués ;
- 0 manquant ;
- mouvement jugé très fluide ;
- synchronisation de départ améliorée par un `GOFLAG` externe avant fixation de `T=0`.

## Conclusion architecturale

Cette expérience valide directement le principe suivant :

> Une instance VPX réplique peut suivre de façon fluide une trajectoire de bille produite par une autre exécution en recevant périodiquement position + vitesse autoritaires.

C’est la première preuve forte que le modèle **Master → Hot Replica avec deltas physiques autoritaires** est techniquement viable pour PinCabOS sans exiger un lockstep déterministe.

Cette preuve ne valide pas encore une partie multijoueur complète. Restent notamment à synchroniser ou qualifier :

- flippers ;
- cycle de vie des billes ;
- multiball / identité persistante de chaque bille ;
- objets mobiles ;
- switches/solénoïdes nécessaires ;
- état PinMAME/ROM ;
- timers/script ;
- lampes/flashers ;
- checksum ;
- snapshots complets ;
- handoff d’autorité ;
- transport réseau réel.

## Décision pour la prochaine étape

### V7 — états visuels des flippers

Conserver :

- XYZ ;
- VelX/VelY/VelZ ;
- Start et Plunger externes.

Ajouter uniquement la réplication des états flipper provenant des frames `F` du PCOSREC :

- `LFO` ;
- `RFO` ;
- `LeftFlipper.RotateToEnd/RotateToStart` ;
- `RightFlipper.RotateToEnd/RotateToStart` ;
- variables `LeftFlipperOn` / `RightFlipperOn` si nécessaires au rendu de table.

Ne pas écrire les switches ROM et ne pas injecter les inputs flipper au contrôleur pendant ce test. L’objectif est d’abord de prouver la fidélité visuelle/mécanique de la réplique sans modifier son état ROM local.

## Statut Phase 3

- Record PCOSREC : **GO**
- Replay inputs externe : **GO transport**
- Lockstep déterministe : **non démontré / non retenu comme hypothèse principale**
- Hook différé : **GO**
- Lecture PCOSREC temps réel : **GO**
- Réplication XYZ : **GO**
- Réplication XYZ + vélocité : **GO**
- Flippers répliqués : **PENDING V7**
- Réplication état ROM/switches : **PENDING**
- Snapshot complet : **PENDING**
- Deux cabinets réels : **PENDING**
