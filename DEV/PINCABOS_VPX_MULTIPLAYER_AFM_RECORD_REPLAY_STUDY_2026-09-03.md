# PinCabOS Multiplayer — étude AFM Record/Replay et réplication d’état

> Rapport technique de laboratoire destiné au développement du mode multijoueur PinCabOS.
>
> **Date :** 2026-09-03  
> **Dépôt :** `PinCabOs/PinCabOS`  
> **Branche :** `main`  
> **Document maître :** `DEV/PINCABOS_VPX_MULTIPLAYER_MASTER_REPLICA.md`  
> **Safeword projet :** `PINFORGE-SAFE-VPX-LOBBY-MASTER-32`  
> **Table pilote :** Attack from Mars (Bally 1995)  
> **ROM :** `afm_113b`  
> **Moteur testé :** VPX BGFX 10.8.1 Rev 5231  
> **Statut au moment de ce rapport :** enregistrement d’état validé, injection externe d’inputs validée, replay d’inputs complet validé comme mécanisme de transport, lockstep déterministe non démontré, test de réplication d’état autoritaire préparé mais pas encore validé.

---

## 1. But de l’étude

Cette étude vise à répondre expérimentalement à la question centrale de la Phase 3 du plan multijoueur PinCabOS :

> Deux cabinets peuvent-ils reproduire la même partie VPX à partir des mêmes inputs, ou faut-il transmettre un état autoritaire du maître vers des répliques chaudes ?

L’étude ne cherche pas à fabriquer immédiatement le protocole réseau final. Elle cherche d’abord à déterminer **quelle information doit réellement circuler entre les cabinets**.

Trois modèles sont évalués :

1. **Lockstep par inputs uniquement**  
   Tous les cabinets exécutent la même table et reçoivent exactement les mêmes entrées au même moment.

2. **Master/Replica par états autoritaires**  
   Le cabinet maître exécute la physique réelle et diffuse périodiquement positions, vitesses, flippers, switches, timers et autres états nécessaires.

3. **Snapshot complet + deltas**  
   Le maître diffuse des deltas rapides pendant la balle et un snapshot complet aux moments critiques : resynchronisation, perte de paquet, changement de joueur, changement de maître.

Le résultat de cette étude doit guider l’architecture de `PinCabOS Sync` et empêcher de développer un protocole réseau basé sur une hypothèse de déterminisme qui ne serait pas vraie dans VPX/PinMAME.

---

## 2. Contraintes non négociables appliquées pendant l’étude

Les tests ont été conduits avec les protections suivantes :

- le VPX privé actif n’est pas remplacé ;
- BGFX n’est pas recompilé ni patché ;
- VPinFE n’est pas utilisé pour transporter ou synchroniser la partie ;
- B2S, ScoreView et FullDMD ne sont pas modifiés ;
- le launcher normal reste utilisable ;
- les essais destructifs sont précédés d’un backup ;
- chaque patch VBS expérimental possède un hash attendu et un rollback ;
- la table AFM originale peut être restaurée exactement par SHA-256 ;
- aucune commande réseau arbitraire n’est exécutée ;
- aucun transport Internet n’est encore introduit dans la boucle physique.

### Hash AFM VBS original de référence

```text
054d313de70f4467bf269e537a26e717964e879aad118458739380ce8c0d558c
```

Ce hash est utilisé comme garde de restauration et comme preuve que les essais de replay externe peuvent se faire sur la table originale.

---

## 3. Environnement de test

### Cabinet

- Host : `PinCabOs`
- Utilisateur runtime : `pinball`
- Table : `/home/pinball/Tables/Attack from Mars (Bally 1995)/Attack from Mars (Bally 1995).vpx`
- VBS : `/home/pinball/Tables/Attack from Mars (Bally 1995)/Attack from Mars (Bally 1995).vbs`
- ROM : `afm_113b`
- VPX : `/home/pinball/vpx/VPinballX_BGFX`
- PrefPath : `/home/pinball/.pincabos/vpx`
- Display X11 : `:0`

### Fenêtres VPX observées pendant un lancement normal

```text
Visual Pinball Player
Visual Pinball Backglass
Visual Pinball Score View
```

Ces trois fenêtres sont utilisées comme garde de « table visuellement chargée ». Elles ne suffisent toutefois pas à elles seules pour prouver que la ROM a terminé son initialisation ; ce point a été découvert pendant le replay complet V1.

---

## 4. Analyse préalable de la table AFM

L’étude du script AFM a révélé plusieurs éléments importants pour la synchronisation.

### 4.1 Initialisation PinMAME/ROM

`Table1_Init` :

- initialise `Controller` avec `cGameName = "afm_113b"` ;
- lance PinMAME ;
- initialise le trough ;
- initialise les mécanismes ;
- configure le plunger ;
- démarre les timers VPX/PinMAME ;
- active `RealTime`.

Conclusion : **une table peut être visuellement ouverte alors que la logique ROM n’est pas encore prête à accepter le Start de façon fiable**.

### 4.2 Plunger non déterministe

Le plunger utilise :

```vb
.Random 0.7
```

Cela introduit explicitement une composante aléatoire dans l’impulsion de lancement.

### 4.3 Génération aléatoire dans le script

La table contient également :

```vb
Randomize
```

et :

```vb
Randomize timer
```

notamment dans `RndNbr`.

Cela signifie qu’un replay avec les mêmes inputs n’est pas garanti de reproduire les mêmes décisions internes ou la même trajectoire physique.

### 4.4 État physique accessible dans le script

Le code AFM utilise déjà `GetBalls` et accède aux propriétés :

- `X`
- `Y`
- `Z`
- `VelX`
- `VelY`
- `VelZ`

Le script agit également sur les flippers avec :

- `RotateToEnd`
- `RotateToStart`
- `LeftFlipperOn`
- `RightFlipperOn`

Conclusion : **un POC de réplication d’état au niveau script est techniquement possible sans modifier le moteur VPX**, au moins pour position/vitesse de bille et état des flippers.

---

## 5. TEST01 — Enregistrement PCOSREC

### Objectif

Enregistrer pendant une minute une vraie partie manuelle AFM afin de créer une source de vérité indépendante du futur transport réseau.

### Format initial

Le format expérimental a été nommé :

```text
PCOSREC|v0
```

### Données enregistrées

#### Métadonnées

- table ;
- ROM ;
- SHA du VBS original ;
- durée ;
- cadence d’échantillonnage ;
- état RNG connu/inconnu ;
- `START_GAMETIME`.

#### Inputs

Chaque KeyDown/KeyUp a été journalisé avec :

- timestamp monotone relatif ;
- type `KD` ou `KU` ;
- keycode brut.

#### Événements fonctionnels

Ont également été enregistrés :

- callbacks flipper gauche ;
- callbacks flipper droit ;
- auto-plunger.

#### Frames physiques

À environ 50 Hz :

```text
F|t|LF|...|RF|...|LFO|...|RFO|...|BALLCOUNT|...
```

#### États des billes

```text
B|t|index|X|...|Y|...|Z|...|VX|...|VY|...|VZ|...
```

### Résultat TEST01

Fichier :

```text
/home/pinball/.local/share/PinCabOS/multiplayer-lab/afm-test01/PCOSREC-v0-20260903-210610.log
```

Mesures :

| Mesure | Résultat |
|---|---:|
| Durée | 60.004 s |
| Frames | 3000 |
| Cadence nominale | 20 ms / 50 Hz |
| États de billes | 2202 |
| Inputs bruts | 222 |
| Événements/callbacks | 64 |
| Taille fichier | ~308 KiB |
| FLIP_L | 32 callbacks |
| FLIP_R | 26 callbacks |
| Auto-plunger | 6 callbacks |

Fin du fichier :

```text
END|60004|SAMPLES|3000|INPUTS|222|EVENTS|64
```

### Premier constat de latence locale

- plunger KD : `t=3096 ms` ;
- callback auto-plunger : environ `t=3114 ms` ;
- délai observé : environ 18 ms ;
- les premiers callbacks de flippers ont été observés au même timestamp que les entrées correspondantes.

Ce test ne constitue pas un benchmark CPU complet, mais ne montre pas de latence fonctionnelle visible créée par le recorder.

---

## 6. Découverte importante — keycodes physiques et alias

Le recorder a capturé plusieurs keycodes pour une même action physique.

Exemples observés :

```text
65536
65538
65544
42
```

et :

```text
65537
65539
65545
54
```

Le replay externe a permis d’identifier les keycodes bas réellement utiles à l’injection X11 :

| Fonction | Keycode PCOSREC | Injection X11 validée |
|---|---:|---|
| Start | 2 | `1` |
| Plunger | 28 | `Return` |
| Flipper gauche | 42 | `Shift_L` |
| Flipper droit | 54 | `Shift_R` |

Sur 222 événements bruts :

- 164 étaient des codes `655xx` considérés comme alias/événements doublons pour ce POC ;
- 58 événements normalisés étaient nécessaires pour Start, plunger et flippers.

Répartition des 58 événements normalisés :

| Keycode | Fonction | Événements KD/KU |
|---:|---|---:|
| 2 | Start | 2 |
| 28 | Plunger | 4 |
| 42 | Flipper gauche | 28 |
| 54 | Flipper droit | 24 |

### Décision temporaire

Pour le POC externe AFM :

- conserver le PCOSREC brut comme preuve ;
- normaliser uniquement dans l’adaptateur d’input ;
- **ne pas supprimer les alias du format brut** tant que leur origine SDL/VPX/périphérique n’est pas documentée pour toutes les configurations de cabinets.

---

## 7. Échecs utiles — replay injecté dans le VBS

Plusieurs tentatives ont été faites pour intégrer directement le replay dans le script AFM.

Elles ont été volontairement abandonnées.

### V3 — arrays d’inputs intégrés au VBS

Le VBS généré contenait des lignes de plus de 1000 caractères :

```text
ligne maximale : 1282 caractères
3 lignes > 1000 caractères
```

Symptôme :

- playfield visible ;
- ROM non chargée correctement ;
- directB2S absent ;
- FullDMD absent ;
- ScoreView absent.

La restauration du VBS précédent a immédiatement restauré tous les composants.

### V4 — streaming PCOSREC depuis le VBS

Même si les lignes VBS étaient courtes, l’intégration précoce du moteur de replay dans le script a de nouveau perturbé l’initialisation globale de la table.

### Conclusion de ces échecs

Pour le développement PinCabOS :

> Le transport des inputs ne doit pas dépendre d’une modification spécifique de chaque VBS de table.

Le mode multijoueur doit privilégier :

- un agent externe ;
- un adaptateur moteur générique ;
- éventuellement un hook LAB minimal et générique seulement pour l’état physique non accessible de l’extérieur ;
- jamais un gros moteur de replay injecté dans chaque table.

Ces échecs ont directement conduit au test d’injection externe.

---

## 8. Validation de l’injection externe sur table originale

AFM a été restaurée exactement au VBS original.

Une instance normale a été lancée avec :

```text
/home/pinball/vpx/VPinballX_BGFX \
  -PrefPath /home/pinball/.pincabos/vpx \
  -play "/home/pinball/Tables/Attack from Mars (Bally 1995)/Attack from Mars (Bally 1995).vpx"
```

### Tests unitaires manuels

Les commandes suivantes ont été injectées depuis un agent externe X11 avec `xdotool` :

1. Start ;
2. Plunger ;
3. Flipper gauche ;
4. Flipper droit ;
5. Deux flippers ensemble.

La table était déjà complètement ouverte avec ROM/B2S/ScoreView.

Résultat : **les primitives de contrôle nécessaires au POC ont été validées sans modifier le VBS**.

### Importance architecturale

Cela prouve qu’un futur `pincabos-multiplayer-agent` peut :

- laisser la table et la ROM se charger normalement ;
- attendre un état `READY` ;
- injecter les actions du protocole sans appeler VPinFE ;
- garder le code multijoueur hors du script de table pour les contrôles standards.

---

## 9. Replay externe complet V1

### Objectif

Rejouer automatiquement les 58 événements normalisés à partir du launcher normal.

### Mesures transport

```text
Events envoyés : 58
Durée replay   : 59.760 s
Retard moyen   : 0.598 ms
Retard max     : 17.365 ms
```

### Échec fonctionnel

Le Start a été envoyé trop tôt : les fenêtres VPX étaient présentes, mais la ROM n’avait pas terminé son initialisation.

### Conclusion

**La présence des fenêtres n’est pas un critère de readiness suffisant.**

Le futur agent doit posséder une véritable machine d’état de lancement :

```text
PROCESS_STARTED
  -> WINDOWS_PRESENT
  -> ROM_INITIALIZING
  -> TABLE_READY
  -> SESSION_ARMED
  -> PLAYING
```

Le critère `TABLE_READY` devra idéalement venir d’une preuve explicite du runtime et non d’un simple délai fixe.

---

## 10. Replay externe complet V2

### Correction

Avant d’envoyer Start :

- âge minimum du processus VPX : 20 secondes ;
- Player + Backglass + ScoreView présents ;
- fenêtres stables pendant au moins 5 secondes.

### Résultats mesurés

```text
Events      : 58
Durée       : 59.758 s
Retard moy. : 0.514 ms
Retard max  : 14.968 ms
```

Le replay complet a été envoyé avec succès depuis l’agent externe.

### Interprétation du retard maximum

Les maxima autour de 15 ms se sont produits lorsque deux événements étaient prévus au même timestamp. L’appel séquentiel à `xdotool` impose alors un petit délai entre les deux commandes.

Pour le protocole final, les événements partageant le même tick doivent pouvoir être appliqués en **batch atomique logique** ou dans une même boucle d’input interne afin de réduire ce décalage.

### Conclusion transport

**GO : injection d’inputs externe fonctionnelle.**

Le mécanisme est suffisamment précis pour continuer l’étude.

Il ne prouve pas que deux simulations VPX resteront identiques.

---

## 11. Résultat déterminisme / lockstep

L’observation de la partie rejouée confirme que le jeu n’est pas visuellement/physiquement identique au RUN A malgré le replay temporel des mêmes commandes normalisées.

Cette divergence est cohérente avec :

- le plunger aléatoire ;
- `Randomize` ;
- `Randomize timer` ;
- les différences potentielles d’ordonnancement physique/timers ;
- l’état interne de la ROM et du moteur de script.

### État de la conclusion

**Le lockstep par inputs uniquement ne doit plus être considéré comme l’hypothèse principale.**

Cependant, le test actuel ne constitue pas encore une preuve quantitative complète de la dérive, car RUN B externe n’a pas encore enregistré simultanément toutes ses positions de billes pour comparer mathématiquement RUN A ↔ RUN B.

### Décision de développement provisoire

Architecture à privilégier :

```text
ACTIVE CABINET = MASTER

local physical inputs
        |
        v
      VPX
        |
        +--> state snapshots/deltas
        |
        +--> authoritative events
        v
REMOTE CABINETS = HOT REPLICAS
```

Le replay d’inputs peut rester utile pour :

- prédiction locale ;
- animation ;
- réduction du volume réseau ;
- validation ;
- reconstruction d’événements simples.

Mais l’état du maître doit pouvoir corriger la réplique.

---

## 12. Prochaine expérience — STATE REPLICA LAB V1

Au moment de la rédaction de ce rapport, le test suivant est préparé mais n’est **pas encore déclaré GO**.

### Objectif

Utiliser le RUN A comme autorité locale et, toutes les ~20 ms :

- appliquer Start/plunger/flippers ;
- appliquer `X/Y/Z` de la bille ;
- appliquer `VelX/VelY/VelZ` ;
- corriger l’état des flippers.

### Principe

La table charge normalement :

```text
VPX
ROM
B2S
ScoreView
```

Après une période d’initialisation, un hook LAB minimal charge le moteur de réplication d’état.

### Ce que le test doit prouver

Si la bille suit fidèlement la trajectoire enregistrée malgré la physique locale :

**GO conceptuel pour master/replica autoritaire au niveau état physique.**

Si la bille ne peut pas être maintenue correctement :

- mesurer l’erreur ;
- déterminer si le problème vient de l’indexation des billes ;
- déterminer si VPX réapplique immédiatement une physique conflictuelle ;
- passer si nécessaire à une interface dédiée du moteur LAB isolé.

### Important

Le test ne doit pas être interprété comme le protocole final.

Il s’agit d’un POC permettant de savoir si l’état enregistré peut piloter une réplique.

---

## 13. Limites actuelles de PCOSREC v0

PCOSREC v0 est volontairement incomplet.

Il contient :

- inputs ;
- callbacks de flippers ;
- auto-plunger ;
- angles/états de flippers ;
- nombre de billes ;
- position/vitesse des billes visibles.

Il ne contient pas encore de façon complète :

- identité persistante de chaque bille ;
- création/destruction de bille ;
- orientation/spin complet ;
- switches PinMAME ;
- solénoïdes ;
- lampes ;
- flashers ;
- gates ;
- spinners ;
- cibles ;
- état des troughs ;
- timers VBScript ;
- file d’événements VPX ;
- état RNG ;
- variables script critiques ;
- état complet PinMAME/ROM ;
- mécanismes physiques complexes ;
- audio ;
- état DMD/ScoreView ;
- checksum canonique d’un tick.

Par conséquent, **un replay d’état de bille réussi ne signifie pas encore qu’une partie complète peut changer de maître sans perte d’état**.

---

## 14. PCOSREC V1 recommandé

Le prochain format doit séparer plusieurs familles de messages.

### 14.1 Header

```text
session_id
recording_id
protocol_version
package_hash
vpx_hash
vbs_hash
rom_id
rom_hash_if_available
engine_build
start_monotonic_ns
tick_rate
```

### 14.2 INPUT

```text
tick
sequence
player
control
state
source_device
```

Exemple conceptuel :

```text
INPUT|tick=12345|player=1|control=LEFT_FLIPPER|state=DOWN
```

Ne pas transporter des keycodes Linux/X11 comme contrat réseau public. Les keycodes doivent rester dans l’adaptateur local.

### 14.3 BALL_CREATE

```text
ball_id
position
velocity
angular_momentum
radius
mass
```

### 14.4 BALL_STATE

```text
ball_id
x y z
vx vy vz
angular_state
surface/context
```

### 14.5 BALL_DESTROY

Permet d’éviter l’ambiguïté actuelle de `GetBalls(index)`.

### 14.6 OBJECT_STATE

Pour :

- flippers ;
- gates ;
- spinners ;
- targets ;
- saucers ;
- diverters ;
- ramps dynamiques ;
- toys.

### 14.7 ROM/SWITCH_STATE

À définir après étude PinMAME :

- matrice de switches ;
- solénoïdes ;
- lampes ;
- états minimaux nécessaires à une reprise de partie.

### 14.8 CHECKSUM

Chaque tick ou groupe de ticks doit disposer d’un checksum canonique permettant :

- détection de dérive ;
- demande de resync ;
- validation avant handoff.

---

## 15. Identité de bille — problème à résoudre avant réseau

PCOSREC v0 utilise l’index retourné par `GetBalls`.

Ce n’est pas suffisant pour un protocole réseau robuste.

L’index peut changer lors de :

- création d’une bille ;
- destruction ;
- multiball ;
- verrouillage ;
- trough ;
- kicker ;
- remplacement interne d’objet.

### Recommandation

Créer un `ball_id` PinCabOS stable pendant la durée de vie logique de la bille.

Le mapping local peut être construit à partir :

- création/destruction observée ;
- proximité spatiale entre ticks ;
- identifiant interne VPX si une interface fiable est disponible dans le moteur LAB.

---

## 16. Readiness de la ROM — dette technique identifiée

Le V1 du replay a prouvé qu’un timer arbitraire est fragile.

Le V2 utilise 20 secondes pour le LAB, mais ce n’est pas une solution finale.

### Besoin pour PinCabOS Multiplayer Agent

Définir un signal de readiness structuré :

```text
ENGINE_READY
TABLE_SCRIPT_READY
ROM_READY
DISPLAY_READY
SYNC_READY
```

Le Start multijoueur ne doit être autorisé que lorsque tous les cabinets annoncent :

```text
READY_FOR_SESSION
```

Le lobby peut ensuite émettre :

```text
SESSION_START(epoch, tick0)
```

---

## 17. Conséquence pour le futur transport réseau

Les essais locaux montrent que la précision d’input n’est pas le principal problème.

Le problème principal devient :

> maintenir une représentation suffisamment fidèle de l’état du maître sur les autres cabinets.

### Trafic recommandé

#### Inputs

Faible volume, événements immédiats.

#### Deltas physiques

Fréquents, par exemple 50–120 Hz selon mesure réelle.

#### Snapshot complet

Moins fréquent :

- join ;
- resync ;
- dérive ;
- handoff ;
- changement de balle/joueur.

#### Checksums

Fréquents et légers.

---

## 18. Latence et autorité

Un principe du plan maître est confirmé par l’étude :

> Le joueur actif ne doit jamais attendre le réseau pour ses flippers.

Les inputs doivent être appliqués localement sur le maître.

Ensuite :

```text
input local
  -> physics master
  -> state delta
  -> network
  -> replica correction
```

La réplique peut être légèrement en retard visuellement.

Le cabinet qui reçoit le prochain tour doit être resynchronisé complètement avant le handoff.

---

## 19. Handoff futur — implication de l’étude AFM

Le handoff ne peut pas être simplement :

```text
change master IP
```

Il doit être :

```text
1. freeze tick N
2. flush pending events
3. emit full authoritative snapshot
4. replica applies snapshot
5. replica computes checksum
6. master/checkers confirm checksum
7. authority token changes epoch
8. new master enables local physics/input
9. old master becomes replica
```

Si l’état ROM/script ne peut pas être transféré fidèlement par les interfaces publiques, la capacité de handoff devra être ajoutée **uniquement au moteur LAB isolé**.

---

## 20. Sécurité du protocole

Aucun enseignement du LAB ne doit conduire à envoyer du code VBScript sur le réseau.

Le prototype local peut charger un script de test depuis un fichier local contrôlé, mais le protocole final doit transporter uniquement des structures typées.

Interdits sur le réseau :

- Bash ;
- Python arbitraire ;
- VBScript arbitraire ;
- chemins de fichiers fournis par un pair ;
- commandes shell ;
- DLL/SO provenant d’un autre joueur.

Autorisé :

```text
INPUT
BALL_STATE
OBJECT_STATE
ROM_STATE
SNAPSHOT
CHECKSUM
HANDOFF_PREPARE
HANDOFF_COMMIT
RESYNC_REQUEST
METRICS
```

Chaque message doit être :

- versionné ;
- borné en taille ;
- validé ;
- associé à `session_id` ;
- associé à `epoch` ;
- séquencé ;
- authentifié.

---

## 21. Métriques obligatoires pour les prochains tests

Chaque test réseau ou local doit produire automatiquement :

### Transport

- input latency moyenne ;
- p50 ;
- p95 ;
- p99 ;
- maximum ;
- jitter ;
- événements en retard ;
- événements perdus ;
- événements réordonnés.

### Physique

Pour chaque bille :

```text
position_error = sqrt(dx² + dy² + dz²)
velocity_error = sqrt(dvx² + dvy² + dvz²)
```

Rapporter :

- médiane ;
- p95 ;
- max ;
- premier tick > 1 unité ;
- premier tick > 5 ;
- premier tick > 10 ;
- premier tick > 25.

### États

- mismatch flipper ;
- mismatch switches ;
- mismatch solenoids ;
- mismatch ROM checksum ;
- mismatch snapshot hash.

### Ressources

- CPU maître ;
- CPU réplique ;
- mémoire ;
- débit réseau ;
- packets/s ;
- taille delta moyenne ;
- taille snapshot ;
- temps de handoff.

---

## 22. Critères GO/NOGO révisés pour Phase 3

### GO — input transport

Déjà obtenu localement :

- [x] Start externe sur table originale.
- [x] Plunger externe.
- [x] Flipper gauche externe.
- [x] Flipper droit externe.
- [x] Replay temporel complet ~60 s.
- [x] Retard moyen inférieur à 1 ms dans ce POC local.

### PENDING — réplication d’état

- [ ] la bille d’une réplique suit le PCOSREC enregistré ;
- [ ] les flippers suivent l’état enregistré ;
- [ ] création/destruction de billes maîtrisée ;
- [ ] multiball testé ;
- [ ] switches essentiels répliqués ;
- [ ] checksum stable disponible ;
- [ ] deuxième instance/cabinet réel testé.

### NOGO lockstep strict

Le lockstep strict ne doit pas être déclaré supporté tant que :

- les deux simulations ne sont pas comparées quantitativement ;
- RNG/ROM/timers ne sont pas déterministes ou synchronisés ;
- les trajectoires ne restent pas sous un seuil d’erreur défini.

L’observation actuelle indique déjà que les inputs seuls ne suffisent pas à garantir une partie identique.

---

## 23. Plan de développement dérivé de cette étude

### Étape A — terminer STATE REPLICA local

- rejouer RUN A ;
- appliquer les états de bille ;
- mesurer visuellement puis quantitativement ;
- ne pas encore introduire le réseau.

### Étape B — PCOSREC V1

- identité stable des billes ;
- événements de cycle de vie ;
- objet/flipper/switch ;
- checksum ;
- sérialisation binaire.

### Étape C — deux processus LAB locaux

- master ;
- replica ;
- transport localhost ;
- injection des deltas ;
- comparaison automatique.

### Étape D — deux cabinets LAN

- même package/hash ;
- master réel ;
- replica réelle ;
- latence/jitter ;
- resync.

### Étape E — handoff de balle

- freeze ;
- snapshot ;
- checksum ;
- transfert epoch ;
- reprise locale.

### Étape F — intégration Lobby

Seulement après validation locale/LAN :

- readiness ;
- autorité ;
- session token ;
- table manifest ;
- orchestration 2–4 joueurs.

---

## 24. Décisions architecturales retenues à ce stade

1. **Conserver l’agent multijoueur externe.**
2. **Ne pas utiliser VPinFE dans le chemin multijoueur.**
3. **Ne pas dépendre d’une modification VBS spécifique à chaque table pour les inputs.**
4. **Utiliser un adaptateur local abstrait pour les contrôles.**
5. **Considérer les keycodes comme détail local, pas comme protocole.**
6. **Le lockstep inputs-only n’est plus la stratégie principale.**
7. **Prioriser master + hot replicas + corrections d’état.**
8. **Ajouter snapshot + checksum pour resync/handoff.**
9. **Conserver le joueur actif comme maître afin qu’aucune latence réseau n’affecte ses boutons.**
10. **Si une interface moteur supplémentaire devient nécessaire, elle doit rester confinée au runtime `VPX_MultiPlayers/engine`.**

---

## 25. Résumé exécutif

L’étude AFM a fait progresser la Phase 3 d’un plan théorique à un POC mesuré.

### Ce qui est prouvé

- une partie réelle peut être enregistrée à 50 Hz dans PCOSREC ;
- les inputs utiles peuvent être normalisés ;
- Start, plunger et flippers peuvent être injectés depuis un agent externe ;
- la table peut rester originale pendant l’injection externe ;
- un replay d’environ 60 secondes peut respecter les timestamps avec un retard moyen local d’environ 0.5 ms ;
- la readiness ROM doit être explicitement gérée ;
- les inputs seuls ne garantissent pas visuellement une partie identique.

### Ce qui reste à prouver

- qu’une réplique peut être maintenue sur la trajectoire autoritaire du maître ;
- que les états PinMAME/script essentiels peuvent être transférés ;
- qu’un snapshot complet est suffisant pour un handoff ;
- que le modèle tient entre deux cabinets physiques ;
- que le débit et la latence restent acceptables en réseau réel.

### Orientation recommandée

Le développement doit maintenant viser :

```text
LOCAL INPUTS
    |
    v
MASTER VPX
    |
    +---- INPUT EVENTS ---------->
    +---- STATE DELTAS ----------> HOT REPLICA
    +---- CHECKSUMS ------------->
    +---- SNAPSHOTS ------------->
                                  |
                                  v
                         CORRECTED LOCAL RENDER
```

Le test AFM supporte donc fortement l’architecture déjà prévue dans le document maître : **maître migratoire + répliques chaudes + snapshots/deltas autoritaires**, plutôt qu’un lockstep basé uniquement sur les inputs.

---

## 26. Journal de preuves

| Date | Test | Résultat | Preuve principale |
|---|---|---|---|
| 2026-09-03 | TEST01 PCOSREC | GO | 60.004 s, 3000 frames, 2202 états bille, 222 inputs, 64 événements |
| 2026-09-03 | Replay VBS V3 | NOGO utile | lignes VBS géantes, ROM/B2S/ScoreView non initialisés |
| 2026-09-03 | Replay VBS V4 | NOGO utile | intégration VBS encore trop intrusive pour le chemin de lancement normal |
| 2026-09-03 | Injection externe Start | GO | Start accepté par AFM originale déjà chargée |
| 2026-09-03 | Injection externe Plunger | GO | plunger injecté depuis X11 |
| 2026-09-03 | Injection externe flippers | GO | gauche, droite et combinaison testés |
| 2026-09-03 | Full Replay externe V1 | PARTIAL | transport OK, Start trop tôt avant ROM ready |
| 2026-09-03 | Full Replay externe V2 | GO transport | 58 événements, 59.758 s, retard moyen 0.514 ms, max 14.968 ms |
| 2026-09-03 | Lockstep inputs-only | NON VALIDÉ | partie observée non identique ; analyse quantitative encore à faire |
| 2026-09-03 | State Replica LAB V1 | PENDING | script préparé, résultat matériel attendu |

---

## 27. Règle de mise à jour de ce rapport

Après chaque nouveau test multijoueur :

1. ne modifier les conclusions que sur preuve mesurée ;
2. ajouter les nouveaux résultats au journal ;
3. conserver les NOGO utiles ;
4. distinguer clairement :
   - validé ;
   - observé ;
   - inféré ;
   - planifié ;
5. reporter dans le document maître uniquement les décisions architecturales réellement confirmées.

Ce rapport devient la référence expérimentale AFM de la Phase 3.