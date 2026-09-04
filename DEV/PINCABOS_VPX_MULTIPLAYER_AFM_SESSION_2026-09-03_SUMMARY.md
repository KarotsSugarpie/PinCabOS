# PinCabOS Multiplayer — synthèse complète de la session AFM du 2026-09-03

> Rapport de clôture de session destiné au développement du mode multijoueur PinCabOS.
>
> **Projet :** PinCabOS VPX Multiplayer  
> **Dépôt :** `PinCabOs/PinCabOS`  
> **Branche :** `main`  
> **Safeword :** `PINFORGE-SAFE-VPX-LOBBY-MASTER-32`  
> **Table pilote :** Attack from Mars (Bally 1995)  
> **ROM :** `afm_113b`  
> **VPX testé :** BGFX 10.8.1 Rev 5231  
> **Cabinet pilote :** `PinCabOs` / utilisateur `pinball`  
> **VBS original SHA-256 :** `054d313de70f4467bf269e537a26e717964e879aad118458739380ce8c0d558c`

---

## 1. Conclusion de la session

La session du 2026-09-03 a permis de franchir le point de faisabilité le plus important du POC multijoueur local :

> **Une instance VPX locale peut servir de hot replica en recevant un état physique autoritaire enregistré et en appliquant avec succès la position, la vitesse et l'état mécanique des flippers, sans dépendre d'un lockstep déterministe et sans modifier le moteur VPX privé ni VPinFE.**

La voie architecturale recommandée est maintenant :

```text
CABINET DU JOUEUR ACTIF = MASTER
          |
          | deltas d'état autoritaires
          | + snapshots / checksums
          v
CABINETS SPECTATEURS = HOT REPLICAS
```

Le lockstep par inputs seulement n'est plus l'hypothèse principale. Il reste utile pour transporter les commandes du joueur actif, mais la réplication physique doit être autoritaire.

---

## 2. Contraintes de sécurité maintenues

Pendant toute l'étude :

- le VPX privé n'a pas été remplacé ni recompilé ;
- BGFX n'a pas été patché ;
- VPinFE n'a pas été utilisé comme transport ou orchestrateur multijoueur ;
- B2S, FullDMD et ScoreView n'ont pas été modifiés ;
- les hooks de laboratoire ont été limités au VBS AFM avec backup/rollback ;
- le VBS original a été protégé par SHA-256 ;
- aucun message réseau arbitraire n'a exécuté de Bash/Python/VBScript ;
- aucun `Controller.Switch()` supplémentaire n'a été ajouté pour V7 ;
- les contrôles Start/Plunger ont été injectés extérieurement par le runner de laboratoire ;
- les flippers V7 ont été répliqués comme état mécanique/visuel depuis PCOSREC, pas comme input flipper vers la ROM.

---

## 3. Source de vérité : PCOSREC TEST01

Enregistrement de référence :

```text
/home/pinball/.local/share/PinCabOS/multiplayer-lab/afm-test01/PCOSREC-v0-20260903-210610.log
```

Mesures validées :

| Mesure | Valeur |
|---|---:|
| Durée | 60004 ms |
| Frames `F` | 3000 |
| États de bille `B` | 2202 |
| Inputs bruts | 222 |
| Autres événements/callbacks | 64 |
| Cadence nominale | 20 ms / 50 Hz |
| Taille | ~308 KiB |

Le fichier contient notamment :

- Start ;
- Plunger ;
- flippers ;
- callbacks fonctionnels ;
- état frame ;
- ball count ;
- `X/Y/Z` ;
- `VelX/VelY/VelZ`.

Le RNG AFM n'est pas contrôlé (`Randomize`, `Randomize timer`, plunger `.Random 0.7`), donc la répétition des mêmes inputs ne garantit pas la même trajectoire.

---

## 4. Replay externe des inputs

Le replay externe a normalisé les 222 événements bruts vers 58 événements physiques utiles pour ce POC :

| DIK | Fonction |
|---:|---|
| 2 | Start |
| 28 | Plunger |
| 42 | Flipper gauche |
| 54 | Flipper droit |

Le replay V2 a été validé après ajout d'un readiness gate :

- processus VPX âgé d'au moins 20 s ;
- fenêtres Player/Backglass/ScoreView présentes ;
- stabilité des fenêtres >= 5 s.

Mesures :

```text
58 événements
59.758 s
retard moyen : 0.514 ms
retard max   : 14.968 ms
```

Conclusion : le transport temporel des inputs est suffisamment précis pour le POC, mais le jeu ne reproduit pas automatiquement une trajectoire identique à cause du RNG et de la physique.

---

## 5. V1 — State Replica initial : NOGO d'implémentation

Le premier loader State Replica n'a jamais atteint le test physique.

Cause prouvée : syntaxe VBScript invalide sur appels multilignes :

```vb
CreateObject(
    "Scripting.FileSystemObject"
)
```

et :

```vb
FSO.OpenTextFile(
    "...",
    1
)
```

VBScript exige une continuation explicite de ligne. Le script complet n'a donc pas compilé et `Table1_Init` n'a pas été atteint, expliquant :

- playfield seul ;
- ROM absente ;
- B2S absent ;
- FullDMD absent ;
- ScoreView absent.

Le rollback a restauré exactement le SHA original.

**Décision :** NOGO d'implémentation uniquement, aucune conclusion négative sur le modèle master/replica.

---

## 6. Canary V3 — hook différé : GO

Objectif : prouver qu'un hook extrêmement court peut vivre dans AFM sans casser l'initialisation.

Résultat :

```text
PCOSSTATE|CANARY_OK|GAMETIME|20000
```

Validations :

- Playfield normal ;
- ROM normale ;
- B2S normal ;
- FullDMD normal ;
- ScoreView normal ;
- aucune bille modifiée ;
- aucun input injecté ;
- aucun flipper modifié.

**GO :** un hook PinCabOS peut s'activer exactement après 20 s de `GameTime` sans perturber AFM.

---

## 7. Reader V4 — consommation PCOSREC temps réel : GO

Objectif : lire et parser le PCOSREC dans VPX sans appliquer aucun état.

Résultat complet :

```text
PCOSSTATE|READER_OK|T|60010|END|60004|FRAMES|3000|BALLS|2202|INPUTS|222|OTHER_E|64
```

Mesures :

- 3000/3000 frames ;
- 2202/2202 états de bille ;
- 222/222 inputs ;
- 64 autres événements ;
- END source = 60004 ms ;
- fin lecteur = 60010 ms ;
- écart cumulé d'environ 6 ms sur 60 s ;
- aucune mutation de la table.

**GO :** VPX peut consommer le flux PCOSREC complet en temps réel via le hook LAB.

Note : le V4 a écrit par erreur dans l'ancien log Canary V3 à cause d'un `source current.txt` qui a écrasé la variable `LOG`. Ce défaut est uniquement un bug de chemin de journalisation ; il n'a pas affecté le replay ni VPX.

---

## 8. V5 — X/Y/Z autoritaires : GO

Première mutation physique réelle.

Le runner a envoyé uniquement :

- Start à T=0 ;
- release Start à 272 ms ;
- Plunger à 3096 ms ;
- release Plunger à 3344 ms.

Le VBS a appliqué uniquement :

- `Ball.X` ;
- `Ball.Y` ;
- `Ball.Z`.

Aucune vélocité n'était imposée.

Résultat :

```text
PCOSSTATE|XYZ_DONE|T|10000|B_SEEN|463|APPLIED|456|MISSING|7
```

Soit :

- 463 états rencontrés ;
- 456 appliqués ;
- 7 absents ;
- 98.49 % appliqués.

Observation utilisateur : la bille suivait réellement la trajectoire enregistrée.

Les 7 absences ont été attribuées au décalage initial entre l'armement du hook, le T=0 du PCOSREC et la création/disponibilité effective de la bille.

**GO :** la position autoritaire enregistrée peut commander une bille de la réplique.

---

## 9. V6 — X/Y/Z + VelX/VelY/VelZ autoritaires : GO majeur

V6 a ajouté :

- `Ball.VelX` ;
- `Ball.VelY` ;
- `Ball.VelZ`.

Un `GOFLAG` a été introduit afin que le hook définisse son T=0 après l'armement, au moment du runner.

Timing observé :

```text
V6_ARMED      GAMETIME=20000
V6_SYNC_START GAMETIME=20140
```

Résultat :

```text
PCOSSTATE|V6_DONE|T|10000|B_SEEN|463|APPLIED|463|MISSING|0
```

Soit :

- 463/463 états appliqués ;
- 0 manquant ;
- 100 % d'application.

Observation utilisateur :

> très fluide, voire excellent

**GO majeur :** la combinaison position + vélocité autoritaire permet à la hot replica de suivre naturellement la trajectoire du maître.

---

## 10. V7 — Hot Replica physique de base : GO

V7 a conservé l'autorité de bille V6 et ajouté l'état des flippers depuis les frames `F` du PCOSREC :

- `LFO` ;
- `RFO` ;
- `LeftFlipper.RotateToEnd/Start` ;
- `RightFlipper.RotateToEnd/Start` ;
- `LeftFlipperOn` ;
- `RightFlipperOn`.

Important :

- aucun input flipper externe n'a été envoyé ;
- aucun `table1_KeyDown/KeyUp` flipper n'a été ajouté ;
- aucun `Controller.Switch()` supplémentaire n'a été ajouté par le hook.

Résultat :

```text
PCOSSTATE|V7_ARMED|GAMETIME|20000
PCOSSTATE|V7_SYNC_START|GAMETIME|20150
PCOSSTATE|V7_DONE|T|10000|FRAMES|500|B_SEEN|463|APPLIED|463|MISSING|0
PCOSSTATE|V7_FLIPPERS|LEFT_CHANGES|5|RIGHT_CHANGES|7
```

Mesures :

| Mesure | Résultat |
|---|---:|
| Frames traitées | 500 |
| États de bille vus | 463 |
| États appliqués | 463 |
| États manquants | 0 |
| Changements flipper gauche | 5 |
| Changements flipper droit | 7 |

Observation utilisateur :

> c'est parfait, je crois que c'est concluant, c'est très fluide

**GO physique de base :** bille + vélocité + flippers peuvent être répliqués autoritairement dans une instance VPX locale.

---

## 11. Architecture décidée à la suite des tests

### Master

Le cabinet du joueur actif reste l'autorité.

Il calcule localement :

- inputs ;
- VPX ;
- physique ;
- PinMAME ;
- table script ;
- score ;
- logique de jeu.

Les boutons du joueur actif ne doivent jamais dépendre d'un aller-retour Internet.

### Hot replicas

Les autres cabinets reçoivent des deltas d'état autoritaires.

État minimum actuellement prouvé :

```text
BALL_STATE
  ball identity/index expérimental
  X
  Y
  Z
  VX
  VY
  VZ

FLIPPER_STATE
  LEFT
  RIGHT
```

Les replicas rendent localement le playfield et appliquent l'état du maître.

### Ce qui n'est PAS encore prouvé

V7 ne constitue pas encore un multijoueur complet. Il reste notamment à tester :

- 60 secondes complètes au lieu de 10 s ;
- drain de bille ;
- nouvelle bille ;
- ball lifecycle ;
- multiball ;
- identité persistante des billes ;
- switches ROM ;
- timers ;
- lampes/flashers/solénoïdes ;
- objets dynamiques ;
- état PinMAME complet ;
- score/DMD synchronisé de façon cohérente ;
- snapshots ;
- checksums ;
- resynchronisation après perte ;
- handoff master entre deux cabinets ;
- vrai transport LAN cab-à-cab ;
- Internet/NAT/TURN ;
- sécurité protocolaire finale.

---

## 12. Problème technique à résoudre ensuite : identité des billes

Le PCOSREC v0 utilise actuellement l'index retourné par `GetBalls()`.

Cela suffit au POC de 10 s, mais ne garantit pas une identité stable lorsque :

- une bille est détruite ;
- une nouvelle bille apparaît ;
- plusieurs billes existent ;
- l'ordre de `GetBalls()` change.

Le futur format doit introduire un identifiant persistant :

```text
BALL_CREATE|tick|ball_id|...
BALL_STATE|tick|ball_id|X|...|VZ|...
BALL_DESTROY|tick|ball_id
```

Une table de correspondance locale devra lier `ball_id` réseau à l'objet Ball VPX de chaque réplique.

---

## 13. Étape suivante recommandée : V8

La prochaine expérience doit être une extension contrôlée de V7 sur les **60 secondes complètes du PCOSREC**.

### V8 doit garder

- readiness >= 20 s ;
- arm flag ;
- GO flag ;
- Start + Plunger externes ;
- XYZ ;
- VX/VY/VZ ;
- flippers LFO/RFO ;
- logs structurés ;
- backup + rollback ;
- aucune modification du VPX privé ou VPinFE.

### V8 doit mesurer

- nombre de frames ;
- nombre de ball states ;
- applied/missing ;
- changements de flippers ;
- changements de `BALLCOUNT` ;
- apparition/disparition des index `GetBalls()` ;
- premières divergences après drain ou nouvelle bille ;
- stabilité visuelle pendant 60 s.

### Critère de sortie V8

Le but de V8 n'est pas forcément d'obtenir 100 % jusqu'à la fin. Il doit surtout identifier précisément le premier point où l'index brut de `GetBalls()` ne suffit plus.

Cette preuve déterminera la conception de `PCOSREC v1` et du `BALL_ID` persistant.

---

## 14. Documents GitHub produits pendant la session

Documents de référence déjà créés :

- `DEV/PINCABOS_VPX_MULTIPLAYER_MASTER_REPLICA.md`
- `DEV/PINCABOS_VPX_MULTIPLAYER_AFM_RECORD_REPLAY_STUDY_2026-09-03.md`
- `DEV/PINCABOS_VPX_MULTIPLAYER_AFM_STATE_REPLICA_V1_NOGO_2026-09-03.md`
- document Canary V3 GO ;
- document PCOSREC Reader V4 GO ;
- document XYZ V5 GO ;
- document XYZ+VEL V6 GO ;
- `DEV/PINCABOS_VPX_MULTIPLAYER_AFM_HOT_REPLICA_V7_GO_2026-09-03.md`
- `DEV/PINCABOS_VPX_MULTIPLAYER_AFM_SESSION_2026-09-03_SUMMARY.md` (ce document).

Commits produits au cours de la documentation de cette étude :

```text
c34b7ed9b597283e275f08b0c603bb92c5a48820  étude AFM Record/Replay
28810a92eb27a8dc3b822f5cea13fe95036125c6  State Replica V1 NOGO
0ba1f2c74b1569971009875639b42aaf9ab39ef6  Canary V3 GO
560891ace8ec1eee5940065895a0272aec7102c3  Reader V4 GO
650d11f0fb7295603f8b3d0f983820edc11842fe  XYZ V5 GO
9961c1e3c91d2cf0dec0b9fc96a90f4be33d708b  XYZ+VEL V6 GO
17aa7ce4339014b5bcb7cb2446ffb1f86d9edd59  Hot Replica V7 GO
```

---

## 15. Verdict de clôture du 2026-09-03

### GO validés

- PCOSREC 50 Hz ;
- replay temporel externe ;
- readiness différé ;
- hook VBS minimal post-init ;
- lecture PCOSREC temps réel ;
- application X/Y/Z ;
- application VX/VY/VZ ;
- réplication flippers L/R ;
- hot replica fluide sur fenêtre de 10 secondes ;
- aucun état de bille manquant dans V6/V7 ;
- VPX privé/VPinFE non utilisés comme chemin de synchronisation.

### PENDING

- V8 60 secondes ;
- lifecycle de billes ;
- ball IDs ;
- états ROM/switch/timers ;
- snapshots/checksums ;
- réseau cab-à-cab ;
- handoff du master.

### Décision

> **Le POC local confirme la faisabilité du modèle PinCabOS Master → Hot Replicas au niveau physique de base. La prochaine phase doit étendre la durée et formaliser le cycle de vie/identité des billes avant toute généralisation réseau.**
