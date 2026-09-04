# TEST REPRISE — PinCabOS VPX Multiplayer AFM

> **Checkpoint exact de reprise après la session du 2026-09-03.**  
> Lire ce fichier AVANT toute nouvelle commande ou modification liée au POC multijoueur AFM.

---

## 0. Safeword

```text
PINFORGE-SAFE-VPX-LOBBY-MASTER-32
```

Dans un nouveau chat :

1. donner le safeword ;
2. demander de lire `DEV/test_reprise.md` ;
3. demander de lire `DEV/PINCABOS_VPX_MULTIPLAYER_AFM_SESSION_2026-09-03_SUMMARY.md` ;
4. reprendre uniquement à la section **PROCHAINE ÉTAPE AUTORISÉE** de ce fichier.

---

# 1. ÉTAT EXACT AU MOMENT DE L'ARRÊT

La session s'est arrêtée immédiatement après un **GO réussi de HOT REPLICA V7 sur AFM pendant 10 secondes**.

Aucun test V8 n'a encore été lancé.

Aucune preuve cab-à-cab réseau n'a encore été réalisée.

Le dernier test confirmé par l'utilisateur est :

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

Observation utilisateur après V7 :

> « c'est parfait je crois que c'est concluant c'est très fluide »

### Verdict actuel

```text
HOT REPLICA PHYSIQUE DE BASE : GO
```

Cela signifie que le POC local a démontré avec succès :

- position bille autoritaire `X/Y/Z` ;
- vélocité autoritaire `VelX/VelY/VelZ` ;
- flipper gauche autoritaire ;
- flipper droit autoritaire ;
- 463/463 états de bille appliqués ;
- 0 missing ;
- rendu très fluide ;
- aucun input flipper envoyé à la ROM par le hook ;
- aucun `Controller.Switch()` ajouté par le hook V7.

---

# 2. ÉTAT LOCAL ATTENDU DU CABINET À LA REPRISE

Cabinet pilote :

```text
Host : PinCabOs
User : pinball
IP   : 192.168.254.237
```

Table :

```text
/home/pinball/Tables/Attack from Mars (Bally 1995)/Attack from Mars (Bally 1995).vpx
```

VBS :

```text
/home/pinball/Tables/Attack from Mars (Bally 1995)/Attack from Mars (Bally 1995).vbs
```

VBS original SHA-256 :

```text
054d313de70f4467bf269e537a26e717964e879aad118458739380ce8c0d558c
```

Source PCOSREC :

```text
/home/pinball/.local/share/PinCabOS/multiplayer-lab/afm-test01/PCOSREC-v0-20260903-210610.log
```

Métadonnées V7 :

```text
/home/pinball/.local/share/PinCabOS/multiplayer-lab/afm-hot-replica-v7/current.txt
```

### IMPORTANT — V7 est probablement encore installé

Après le GO V7, **aucun rollback/restauration n'a été exécuté dans la session avant l'arrêt**.

Donc, au redémarrage des travaux, il faut s'attendre à ce que le VBS AFM porte encore le hook V7.

NE PAS supposer son SHA exact à partir de ce document : le SHA V7 et le chemin de backup sont stockés dans :

```text
/home/pinball/.local/share/PinCabOS/multiplayer-lab/afm-hot-replica-v7/current.txt
```

Toujours les lire avant toute écriture.

---

# 3. PREFLIGHT OBLIGATOIRE À LA REPRISE

Avant V8, exécuter un audit lecture seule qui doit au minimum afficher :

```text
hostname
whoami
pgrep AFM/VPX
sha256sum du VBS AFM
cat current.txt V7
existence du backup V7
SHA du backup original
existence du PCOSREC
compteurs PCOSREC
```

## Conditions GO attendues

- utilisateur = `pinball` ;
- AFM fermée avant toute modification ;
- `current.txt` V7 présent ;
- si VBS actuel = `V7_SHA`, restaurer depuis `BACKUP` avant d'installer V8 ;
- backup V7 doit avoir le SHA original exact :

```text
054d313de70f4467bf269e537a26e717964e879aad118458739380ce8c0d558c
```

- PCOSREC doit encore contenir :

```text
FRAMES      = 3000
BALL STATES = 2202
INPUTS      = 222
OTHER EVENT = 64
END         = 60004 ms
```

Toute divergence = `NOGO` et aucune écriture.

---

# 4. CHRONOLOGIE VALIDÉE DES TESTS

## TEST01 — Recorder

### GO

Enregistrement réel d'une partie AFM pendant environ 60 s.

```text
3000 frames
2202 ball states
222 inputs
64 events
60004 ms
~50 Hz
```

Le PCOSREC devient la source de vérité du POC.

---

## Replay inputs externe V2

### GO transport / non déterminisme observé

```text
58 événements normalisés
59.758 s
retard moyen 0.514 ms
retard max 14.968 ms
```

Les inputs sont transportables avec précision, mais une nouvelle partie n'est pas physiquement identique à cause du RNG et de la physique.

Décision : ne pas baser le multijoueur uniquement sur un lockstep inputs-only.

---

## STATE REPLICA V1

### NOGO implémentation seulement

Cause : syntaxe VBScript invalide dans le loader multilignes.

Le test physique n'a jamais démarré.

Le VBS a été restauré exactement au SHA original.

---

## CANARY V3

### GO

```text
PCOSSTATE|CANARY_OK|GAMETIME|20000
```

Preuve qu'un hook minimal différé peut vivre dans AFM sans casser :

- ROM ;
- B2S ;
- FullDMD ;
- ScoreView ;
- playfield.

---

## READER V4

### GO

```text
PCOSSTATE|READER_OK|T|60010|END|60004|FRAMES|3000|BALLS|2202|INPUTS|222|OTHER_E|64
```

Le PCOSREC complet a été consommé en temps réel sans mutation.

---

## XYZ V5

### GO

```text
PCOSSTATE|XYZ_DONE|T|10000|B_SEEN|463|APPLIED|456|MISSING|7
```

Première preuve que la position du maître peut forcer la bille de la réplique.

Les 7 missing apparaissent au démarrage avant amélioration de la synchronisation.

---

## XYZ + VEL V6

### GO MAJEUR

```text
PCOSSTATE|V6_ARMED|GAMETIME|20000
PCOSSTATE|V6_SYNC_START|GAMETIME|20140
PCOSSTATE|V6_DONE|T|10000|B_SEEN|463|APPLIED|463|MISSING|0
```

Résultat :

```text
463 / 463 appliqués
0 missing
```

Observation utilisateur :

> « très fluide voir excellent »

Le `GOFLAG` a permis de synchroniser proprement T=0 et de supprimer les missing V5.

---

## HOT REPLICA V7

### GO PHYSIQUE DE BASE

Ajout de l'état flipper depuis les frames PCOSREC :

```text
LFO
RFO
```

Résultat :

```text
500 frames
463 ball states vus
463 appliqués
0 missing
5 changements flipper gauche
7 changements flipper droit
```

La bille reste très fluide et les flippers bougent seuls selon l'enregistrement.

---

# 5. DÉCISION D'ARCHITECTURE À NE PAS REVENIR EN ARRIÈRE SANS PREUVE

Architecture retenue après les tests :

```text
JOUEUR ACTIF
   |
   v
MASTER VPX LOCAL
   |
   | états autoritaires
   | deltas rapides
   | snapshots périodiques
   | checksums
   v
HOT REPLICAS
```

Le joueur actif garde son chemin local :

```text
bouton -> VPX local -> physique locale
```

Aucun aller-retour Internet pour ses flippers.

Les autres cabinets peuvent tolérer de la latence et recevoir l'état autoritaire du master.

---

# 6. CE QUI EST VALIDÉ

- [x] PCOSREC v0 à ~50 Hz.
- [x] Capture inputs + frames + états de bille.
- [x] Injection externe Start.
- [x] Injection externe Plunger.
- [x] Injection externe flippers testée séparément.
- [x] Replay complet d'inputs externe.
- [x] Readiness gate.
- [x] Hook différé à 20 s.
- [x] Lecture PCOSREC temps réel complète.
- [x] `X/Y/Z` autoritaires.
- [x] `VelX/VelY/VelZ` autoritaires.
- [x] Flippers visuels/mécaniques autoritaires.
- [x] 463/463 états appliqués en V6 et V7.
- [x] 0 missing en V6/V7.
- [x] Fluidité excellente confirmée visuellement.
- [x] VPX privé non remplacé.
- [x] VPinFE hors du chemin de sync.

---

# 7. CE QUI N'EST PAS ENCORE VALIDÉ

- [ ] replay autoritaire complet 60 s ;
- [ ] drain ;
- [ ] nouvelle bille ;
- [ ] cycle de vie des billes ;
- [ ] identité persistante de bille ;
- [ ] multiball ;
- [ ] `BALL_CREATE` ;
- [ ] `BALL_DESTROY` ;
- [ ] switches ROM ;
- [ ] timers importants ;
- [ ] lampes ;
- [ ] flashers ;
- [ ] solénoïdes ;
- [ ] objets dynamiques ;
- [ ] état PinMAME complet ;
- [ ] checksum par tick ;
- [ ] snapshots complets ;
- [ ] resync ;
- [ ] transport réseau entre deux cabs ;
- [ ] handoff de master ;
- [ ] tests Internet/NAT ;
- [ ] 2/3/4 joueurs réels.

---

# 8. PROCHAINE ÉTAPE AUTORISÉE

## V8 — HOT REPLICA 60 SECONDES

**Ne pas passer directement au réseau.**

Le prochain test doit reprendre exactement V7 mais sur les 60 secondes complètes du PCOSREC.

### Garder de V7

- `GameTime >= 20000` avant armement ;
- `ARMFLAG` ;
- `GOFLAG` ;
- runner externe ;
- Start externe ;
- Plunger externe ;
- `X/Y/Z` ;
- `VelX/VelY/VelZ` ;
- LFO/RFO ;
- aucune écriture `Controller.Switch()` ajoutée ;
- aucun input flipper envoyé à la ROM par le hook ;
- backup ;
- rollback ;
- log structuré.

### V8 doit ajouter des mesures, PAS encore un nouveau mécanisme complexe

Journaliser pendant 60 s :

- `FRAME_COUNT` ;
- `BALLCOUNT` ;
- index présents dans `GetBalls()` ;
- première apparition d'un nouvel index ;
- première disparition d'un index ;
- `B_SEEN` ;
- `APPLIED` ;
- `MISSING` ;
- flipper left/right changes ;
- premier timestamp où `MISSING > 0` ;
- état exact autour d'un drain ;
- état exact autour de la création de la bille suivante.

### But V8

Identifier précisément la première limite de :

```text
GetBalls() index == identité de bille
```

Le test ne doit pas masquer cette limite.

Si l'index cesse d'être fiable, c'est une preuve utile et non un échec du modèle master/replica.

---

# 9. ÉTAPE APRÈS V8

Seulement après analyse de V8 : concevoir `PCOSREC v1`.

Format cible proposé :

```text
PCOSREC|v1
SESSION|...
ENGINE_READY|...
ROM_READY|...
SYNC_READY|...

BALL_CREATE|tick|ball_id|...
BALL_STATE|tick|ball_id|X|...|Y|...|Z|...|VX|...|VY|...|VZ|...
BALL_DESTROY|tick|ball_id

FLIPPER_STATE|tick|LEFT|...
FLIPPER_STATE|tick|RIGHT|...

SWITCH_STATE|...
OBJECT_STATE|...
CHECKSUM|tick|...
SNAPSHOT|...
END|...
```

Le `ball_id` doit être persistant et indépendant de l'ordre de `GetBalls()`.

---

# 10. FRONTIÈRES NON NÉGOCIABLES POUR LA REPRISE

Ne jamais modifier pendant ces tests :

- VPX privé ;
- binaire BGFX privé ;
- VPinFE ;
- configuration VPinFE ;
- B2S global ;
- ScoreView global ;
- FullDMD global ;
- launcher privé normal.

Les expérimentations VBS restent temporaires et protégées par backup jusqu'à ce que le futur runtime isolé soit prêt sous :

```text
/opt/pincabos/apps/VPX_MultiPlayers/engine
```

Le futur multijoueur ne doit pas dépendre de VPinFE.

---

# 11. DOCUMENTS À LIRE À LA REPRISE

Ordre recommandé :

1. `DEV/test_reprise.md`
2. `DEV/PINCABOS_VPX_MULTIPLAYER_AFM_SESSION_2026-09-03_SUMMARY.md`
3. `DEV/PINCABOS_VPX_MULTIPLAYER_AFM_HOT_REPLICA_V7_GO_2026-09-03.md`
4. `DEV/PINCABOS_VPX_MULTIPLAYER_AFM_RECORD_REPLAY_STUDY_2026-09-03.md`
5. `DEV/PINCABOS_VPX_MULTIPLAYER_MASTER_REPLICA.md`

---

# 12. COMMITS DE PREUVE DE LA SESSION

```text
c34b7ed9b597283e275f08b0c603bb92c5a48820  étude AFM Record/Replay
28810a92eb27a8dc3b822f5cea13fe95036125c6  State Replica V1 NOGO
0ba1f2c74b1569971009875639b42aaf9ab39ef6  Canary V3 GO
560891ace8ec1eee5940065895a0272aec7102c3  Reader V4 GO
650d11f0fb7295603f8b3d0f983820edc11842fe  XYZ V5 GO
9961c1e3c91d2cf0dec0b9fc96a90f4be33d708b  XYZ+VEL V6 GO
17aa7ce4339014b5bcb7cb2446ffb1f86d9edd59  Hot Replica V7 GO
```

Le rapport de synthèse de clôture est :

```text
DEV/PINCABOS_VPX_MULTIPLAYER_AFM_SESSION_2026-09-03_SUMMARY.md
```

---

# 13. RÉSUMÉ EN UNE LIGNE POUR DEMAIN

> **Nous avons validé une hot replica AFM locale très fluide sur 10 secondes avec 463/463 états de bille appliqués, XYZ+vélocité+flippers et 0 missing. La prochaine étape est V8 sur 60 secondes pour étudier drain/nouvelle bille et déterminer comment remplacer l'index `GetBalls()` par un `BALL_ID` persistant avant de passer au réseau cab-à-cab.**
