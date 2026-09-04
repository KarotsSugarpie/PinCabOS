# PinCabOS Multiplayer — AFM PCOSREC Reader V4 — GO

> Preuve de laboratoire pour la Phase 3 du mode multijoueur PinCabOS.
>
> **Date :** 2026-09-03  
> **Table pilote :** Attack from Mars (Bally 1995)  
> **ROM :** `afm_113b`  
> **PCOSREC :** `PCOSREC-v0-20260903-210610.log`  
> **Safeword :** `PINFORGE-SAFE-VPX-LOBBY-MASTER-32`

## Objectif

Vérifier qu'un hook VBS minimal, activé seulement après l'initialisation normale de la table, peut consommer en temps réel un enregistrement `PCOSREC v0` complet sans appliquer aucun input et sans modifier la physique VPX.

## Préconditions déjà validées

- AFM charge normalement avec ROM, directB2S, FullDMD et ScoreView.
- Le canari V3 s'active à `GameTime=20000` sans perturber la table.
- Aucun `ExecuteGlobal` supplémentaire n'est ajouté au VBS.
- Le VBS original de référence possède le SHA-256 :

```text
054d313de70f4467bf269e537a26e717964e879aad118458739380ce8c0d558c
```

## Résultat Reader V4

Le Reader V4 a été lancé à :

```text
PCOSSTATE|READER_START|GAMETIME|20000
```

Progression observée :

```text
PCOSSTATE|READER_PROGRESS|T|0|FRAMES|0|BALLS|0|INPUTS|2
PCOSSTATE|READER_PROGRESS|T|10000|FRAMES|500|BALLS|463|INPUTS|56
PCOSSTATE|READER_PROGRESS|T|20000|FRAMES|1000|BALLS|903|INPUTS|80
PCOSSTATE|READER_PROGRESS|T|30000|FRAMES|1500|BALLS|1245|INPUTS|128
PCOSSTATE|READER_PROGRESS|T|40000|FRAMES|2000|BALLS|1636|INPUTS|134
PCOSSTATE|READER_PROGRESS|T|50000|FRAMES|2500|BALLS|1935|INPUTS|166
PCOSSTATE|READER_PROGRESS|T|60000|FRAMES|3000|BALLS|2202|INPUTS|222
```

Fin validée :

```text
PCOSSTATE|READER_OK|T|60010|END|60004|FRAMES|3000|BALLS|2202|INPUTS|222|OTHER_E|64
```

## Mesures

| Mesure | Attendu | Lu | Résultat |
|---|---:|---:|---|
| Frames | 3000 | 3000 | GO |
| États bille | 2202 | 2202 | GO |
| Inputs | 222 | 222 | GO |
| Autres événements | 64 | 64 | GO |
| END | 60004 ms | 60004 ms | GO |
| Temps Reader | ~60004 ms | 60010 ms | GO |

Le Reader a donc consommé le flux avec environ 6 ms d'écart sur la durée totale du fichier, sans mutation volontaire de VPX.

## Observation fonctionnelle

Pendant toute l'expérience :

- AFM est restée normalement en attente de `Start` ;
- aucun Start n'a été injecté ;
- aucune bille n'a été déplacée ;
- aucun flipper n'a été actionné ;
- aucun switch PinMAME n'a été écrit par le Reader ;
- ROM/B2S/FullDMD/ScoreView sont restés fonctionnels.

## Défaut non bloquant découvert

Lors de l'installation V4, le `source` des métadonnées du Canary V3 a écrasé par erreur la variable shell `LOG`. Le Reader a donc écrit dans l'ancien fichier de log Canary V3.

Ce défaut concerne uniquement le chemin de journalisation du script d'installation. Il n'affecte ni le timing, ni le parsing PCOSREC, ni VPX. Il doit être corrigé dans la prochaine version en utilisant des noms de variables séparés (`PREV_LOG`, `READER_LOG`) et en évitant de sourcer des métadonnées non namespacées.

## Conclusion architecturale

**GO : un flux PCOSREC complet peut être consommé en temps réel dans une table VPX/PinMAME normalement initialisée, via un hook minimal activé après readiness, sans modifier la physique.**

Cette preuve valide la brique `transport/reader` locale nécessaire à une future réplique chaude.

Elle ne prouve pas encore qu'un état physique peut être appliqué sans conflit avec la physique locale ou la ROM.

## Prochaine expérience autorisée

Introduire une seule classe de mutation : **position de bille X/Y/Z uniquement**.

Contraintes :

1. conserver l'initialisation normale de ROM/B2S/ScoreView ;
2. utiliser le même PCOSREC ;
3. ne pas appliquer `VelX/VelY/VelZ` ;
4. ne pas piloter les flippers depuis le flux d'état ;
5. ne pas écrire les switches PinMAME ;
6. journaliser `BALL_APPLIED`, `BALL_MISSING` et le nombre d'états consommés ;
7. limiter d'abord la mutation à une courte fenêtre de test avant le replay complet ;
8. considérer l'index `GetBalls()` comme provisoire : une identité persistante de bille sera obligatoire pour le multiball.

Un GO à cette étape permettra ensuite d'ajouter les vélocités, puis les flippers, puis les événements/switches nécessaires.