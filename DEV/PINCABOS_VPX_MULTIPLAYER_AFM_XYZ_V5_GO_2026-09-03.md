# PinCabOS Multiplayer — AFM XYZ V5 GO

> Preuve de laboratoire — réplication physique autoritaire de position uniquement.
>
> Date : 2026-09-03  
> Projet : PinCabOS Multiplayer Sync  
> Table pilote : Attack from Mars (Bally 1995)  
> ROM : `afm_113b`  
> Document maître : `DEV/PINCABOS_VPX_MULTIPLAYER_MASTER_REPLICA.md`  
> Safeword : `PINFORGE-SAFE-VPX-LOBBY-MASTER-32`

## Objectif

Valider expérimentalement qu'une réplique VPX peut recevoir et appliquer un état physique autoritaire de bille provenant d'un enregistrement PCOSREC, sans modifier le moteur VPX/BGFX, VPinFE, B2S, ScoreView ni les switches ROM.

La mutation autorisée pour ce test était strictement limitée à :

- `Ball.X`
- `Ball.Y`
- `Ball.Z`

Les éléments suivants restaient locaux et non forcés :

- `VelX`
- `VelY`
- `VelZ`
- flippers
- switches ROM
- autres objets de table

## Architecture de test

1. AFM est lancée normalement par le launcher PinCabOS.
2. La table et la ROM s'initialisent normalement.
3. Le hook LAB attend `GameTime >= 20000`.
4. Le runner externe attend le drapeau `XYZ_ARMED`.
5. Le runner injecte uniquement Start puis Plunger depuis X11.
6. Le hook lit le PCOSREC original.
7. Pendant les 10 premières secondes du flux, les coordonnées X/Y/Z des billes présentes sont appliquées à environ 50 Hz.
8. Aucune vitesse enregistrée n'est réinjectée dans ce test.

## Résultat brut

```text
PCOSSTATE|XYZ_ARMED|GAMETIME|20000
PCOSSTATE|XYZ_PROGRESS|T|0|SEEN|0|APPLIED|0|MISSING|0
PCOSSTATE|XYZ_PROGRESS|T|2000|SEEN|63|APPLIED|56|MISSING|7
PCOSSTATE|XYZ_PROGRESS|T|4000|SEEN|163|APPLIED|156|MISSING|7
PCOSSTATE|XYZ_PROGRESS|T|6000|SEEN|263|APPLIED|256|MISSING|7
PCOSSTATE|XYZ_PROGRESS|T|8000|SEEN|363|APPLIED|356|MISSING|7
PCOSSTATE|XYZ_PROGRESS|T|10000|SEEN|463|APPLIED|456|MISSING|7
PCOSSTATE|XYZ_DONE|T|10000|B_SEEN|463|APPLIED|456|MISSING|7
```

Runner externe :

```text
GO keydown 1        ACT=   14.57 ms
GO keyup   1        ACT=  286.56 ms
GO keydown Return   ACT= 3110.79 ms
GO keyup   Return   ACT= 3358.23 ms
```

## Mesures

| Mesure | Résultat |
|---|---:|
| Fenêtre test physique | 10.000 s |
| États de bille vus | 463 |
| États appliqués | 456 |
| États non appliqués | 7 |
| Taux appliqué | 98.49 % |
| Cadence source | ~50 Hz |
| VelX/Y/Z forcés | non |
| Flippers forcés | non |
| Switches ROM forcés | non |

Les 7 états manquants ont été observés au début de la fenêtre puis le compteur `MISSING` est resté stable, ce qui indique que la bille correspondante n'était pas encore disponible dans `GetBalls` au moment de ces premiers états. Cela devra être remplacé par une identité de bille stable dans PCOSREC V1 plutôt que par un simple index de tableau.

## Observation visuelle

Validation utilisateur : **la réplication X/Y/Z fonctionne visuellement**.

La bille suit la trajectoire imposée par l'enregistrement. Le mouvement peut rester saccadé ou lutter contre la physique locale, ce qui est attendu puisque les vitesses locales ne sont pas encore écrasées.

## Conclusion

**GO PHYSIQUE PARTIEL.**

Ce test démontre pour la première fois dans le POC AFM qu'un état physique autoritaire enregistré peut commander directement une bille d'une instance VPX réplique.

Cela renforce fortement l'architecture :

```text
MASTER VPX
   -> BALL_STATE X/Y/Z/VX/VY/VZ
   -> transport PinCabOS Sync
   -> HOT REPLICA
   -> application locale de l'état autoritaire
```

Le résultat n'établit pas encore qu'une partie complète peut être répliquée fidèlement. Il prouve uniquement l'écriture autoritaire de position sur une bille existante.

## Prochaine étape

V6 doit ajouter uniquement :

- `VelX`
- `VelY`
- `VelZ`

aux coordonnées déjà validées.

Objectifs V6 :

1. rendre la trajectoire plus naturelle ;
2. réduire le combat entre correction de position et physique locale ;
3. conserver ROM/B2S/FullDMD/ScoreView fonctionnels ;
4. mesurer `SEEN/APPLIED/MISSING` ;
5. ne pas encore forcer les flippers ni les switches ROM.

Si V6 est stable, la phase suivante pourra ajouter les flippers enregistrés et comparer la fidélité d'une séquence complète.
