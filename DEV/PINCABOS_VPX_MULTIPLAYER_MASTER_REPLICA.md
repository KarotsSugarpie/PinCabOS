# PinCabOS Multiplayer Sync — plan maître migratoire

> Document de référence durable pour PinCabOS, pincabos.cc, le Lobby, le Chat Audio/Vidéo et la synchronisation VPX entre deux à quatre cabinets.

## Référence de reprise

- **Safeword :** `PINFORGE-SAFE-VPX-LOBBY-MASTER-32`
- **Dépôt de référence :** `KarotsSugarpie/PinCabOS`
- **Fichier de référence :** `DEV/PINCABOS_VPX_MULTIPLAYER_MASTER_REPLICA.md`
- **Branche de référence :** `main`
- **Date de création :** 2026-08-24
- **État :** plan fonctionnel accepté; inventaire initial terminé; document publié sur GitHub; aucune implémentation du moteur de synchronisation commencée.
- **Prochaine étape autorisée :** Phase 1 — audits en lecture seule et preuve de faisabilité locale.

### Règle de reprise dans un nouveau chat

Au début d'un nouveau chat :

1. Donner le safeword `PINFORGE-SAFE-VPX-LOBBY-MASTER-32`.
2. Demander de lire la dernière version de ce fichier sur GitHub avant toute commande ou modification.
3. Vérifier les cases cochées, les preuves et le dernier commit.
4. Reprendre uniquement la première étape non terminée.
5. Mettre ce fichier à jour après chaque étape réellement validée.
6. Ne jamais cocher une étape sans preuve technique reproductible.

## Légende

- `[ ]` À faire.
- `[~]` En cours — ne pas utiliser ce marqueur dans GitHub sans ajouter une note datée.
- `[x]` Terminé et validé avec preuve.
- **GO** : critère nécessaire pour continuer.
- **NOGO** : arrêt; aucun déploiement et retour à l'architecture ou à l'étape précédente.

## Vision validée

### Objectif

Permettre à deux, trois ou quatre utilisateurs PinCabOS de rejoindre un lobby et de jouer la même partie VPX sur leurs propres cabinets. Chaque cabinet rend localement la table avec son GPU. Il ne reçoit pas une vidéo du playfield : il reçoit le **code de synchronisation**, c'est-à-dire des messages binaires validés décrivant l'état de la partie.

### Règles non négociables

- Le créateur du lobby est le **capitaine** pour toute la session.
- Le capitaine choisit une table disponible dans le catalogue pincabos.cc.
- Tous les cabinets doivent utiliser le même package et le même hash SHA-256 du fichier `.vpx` et de ses ressources obligatoires.
- **VPX BGFX et VPinFE sont intouchables.** Leurs sources, binaires, bibliothèques, plugins fournis, configurations et fonctions existantes doivent rester strictement intacts.
- Aucun patch, fork, recompilation, remplacement, injection intrusive ou modification de VPX BGFX ou VPinFE n'est autorisé, même pour un POC.
- Le multijoueur doit être fourni par un agent PinCabOS externe, isolé, installable et supprimable sans écrire dans VPX BGFX, VPinFE ou leurs fichiers de configuration.
- VPinFE ne doit jamais transporter, orchestrer, lancer ni contrôler une session multijoueur. Il demeure uniquement le frontend local normal du cabinet.
- Le Lobby de pincabos.cc est l'unique point d'entrée et l'unique autorité d'orchestration du multijoueur : création, joueurs, table, état `PRÊT`, démarrage, changement de joueur et fermeture.
- Le capitaine administre le lobby, mais le **maître VPX** est toujours le cabinet du joueur actif.
- Le cabinet maître calcule localement VPX, la physique, la logique de table et PinMAME.
- Les boutons du joueur actif sont lus et appliqués localement. Aucun aller-retour Internet n'est permis entre le bouton et le flipper actif.
- Les autres cabinets sont des **répliques chaudes**. Ils mettent continuellement leur copie de la partie à jour et peuvent tolérer une latence visuelle.
- Au changement de joueur, l'état complet et l'autorité passent au cabinet suivant avant que sa balle commence.
- Une courte pause de synchronisation est permise entre deux joueurs; aucune latence réseau ajoutée n'est permise pendant la balle du joueur actif.
- pincabos.cc gère les comptes, amis, présences, fichiers, lobby, chat texte, signalisation et autorisations. Après l'autorisation et la mise en relation par le Lobby, le trafic vivant de la partie doit passer directement entre les cabinets quand le réseau le permet.
- WebRTC Audio/Vidéo est séparé du protocole de synchronisation VPX.
- ScoreView demeure l'unique source d'affichage du score et du DMD. Le Chat ne duplique pas les scores.
- Aucun message réseau ne doit permettre d'exécuter arbitrairement du Bash, Python, VBScript ou un binaire fourni par un autre joueur. Le terme « code de synchronisation » signifie un protocole binaire strictement typé et validé.

## Fonctionnement d'une session

1. Le capitaine crée le lobby.
2. Il choisit une table dans pincabos.cc.
3. pincabos.cc fournit un manifeste signé : identifiant, version, hashes, ressources, compatibilité VPX/PinMAME et profil multijoueur.
4. Chaque cabinet vérifie son cache et télécharge seulement les fichiers absents ou différents.
5. Chaque cabinet retourne `PRÊT — VERSION IDENTIQUE`.
6. Le Lobby ordonne aux agents PinCabOS locaux de lancer la même table avec le launcher PinCabOS existant, sans passer par VPinFE et sans modifier VPX BGFX.
7. Le cabinet du joueur 1 devient maître; les autres deviennent répliques chaudes.
8. Le maître transmet snapshots, deltas, événements et checksums.
9. À la fin de la balle, tous figent le même tick et valident le même état.
10. Le cabinet du joueur suivant reçoit le jeton d'autorité, reprend la simulation localement et devient la nouvelle source des mises à jour.
11. Les anciens maîtres redeviennent répliques.
12. À la fin de la partie, chaque cabinet ferme le mode réseau et restaure son affichage normal.

## Maître migratoire

| Joueur actif | Maître VPX | Répliques chaudes |
|---|---|---|
| Joueur 1 | Cab 1 | Cab 2, Cab 3, Cab 4 |
| Joueur 2 | Cab 2 | Cab 1, Cab 3, Cab 4 |
| Joueur 3 | Cab 3 | Cab 1, Cab 2, Cab 4 |
| Joueur 4 | Cab 4 | Cab 1, Cab 2, Cab 3 |

### Transfert d'autorité obligatoire

1. Le maître annonce `HANDOFF_PREPARE` avec un nouveau numéro d'époque.
2. La simulation se fige à un tick précis après la fin de la balle.
3. Le maître émet un snapshot complet fiable avec hash.
4. Le prochain cabinet charge et vérifie le snapshot.
5. Les autres répliques confirment le même checksum.
6. Un seul jeton d'autorité signé est attribué au nouveau maître.
7. Le nouveau maître annonce `HANDOFF_COMMIT`.
8. La simulation reprend localement sur le cabinet du joueur actif.
9. L'ancien maître passe en mode réplique.

Le protocole doit empêcher deux maîtres simultanés. Chaque message porte au minimum `session_id`, `epoch`, `master_cabinet_id`, `tick`, `sequence`, `type`, `payload_hash` et une authentification de session.

## Données à synchroniser

### Deltas fréquents pendant la balle

- Position, rotation, vitesse et état des billes.
- Flippers, plongeur, slingshots, bumpers, gates, spinners et cibles.
- Primitives animées, matériaux variables et objets dynamiques.
- Lampes, flashers, solénoïdes et sorties nécessaires au rendu.
- Événements audio de table et de ROM.
- Trames ou événements DMD nécessaires à ScoreView.
- Numéro de tick, séquence, checksum et horodatage monotone.

### Snapshot complet pour resynchronisation et changement de maître

- État physique VPX complet.
- État de tous les objets de table.
- État du moteur de script et variables VBScript pertinentes.
- Timers, files d'événements et générateurs aléatoires.
- État complet PinMAME/ROM requis pour reprendre la partie.
- État des plugins qui influencent la logique ou l'affichage.
- Joueur actif, balle courante et état interne de la partie, sans dupliquer les scores dans l'interface Chat.

## Package de table pincabos.cc

Chaque package multijoueur doit contenir un manifeste versionné, par exemple `pincabos-multiplayer.json` :

- `package_id` et `package_version`.
- Hash SHA-256 du `.vpx`.
- Hashes des scripts et ressources obligatoires.
- Version minimale/maximale du VPX BGFX officiel et intact, ainsi que de l'agent PinCabOS Sync externe.
- Version de protocole.
- Mode Original/PuP-Pack et ressources requises.
- Hash de ROM requis lorsque permis, sans copier automatiquement une ROM non distribuable.
- Profil de compatibilité multijoueur commun, validé sans modifier VPX BGFX ou VPinFE.
- Signature du manifeste.

Le module multijoueur ne doit jamais modifier ni remplacer `VPinballX.ini` ou la configuration VPinFE. Le manifeste vérifie les prérequis; en cas d'incompatibilité, le cabinet reste `NON PRÊT` et la correction demeure une action locale séparée. Les écrans, l'audio, les contrôleurs, le POV et le matériel restent locaux.

## Chat Audio/Vidéo sur le backglass

### Deux joueurs

| Haut gauche | Haut droite |
|---|---|
| Joueur 1 | Joueur 2 |
| Lobby et statistiques de connexion | Image du backglass |

### Trois joueurs

| Haut gauche | Haut droite |
|---|---|
| Joueur 1 | Joueur 2 |
| Joueur 3 | Image du backglass |

L'image du lobby disparaît; les informations techniques essentielles restent dans une barre compacte.

### Quatre joueurs

| Haut gauche | Haut droite |
|---|---|
| Joueur 1 | Joueur 2 |
| Joueur 3 | Joueur 4 |

L'image du backglass disparaît. Le titre de la table peut rester dans la barre supérieure.

### Joueur actif

- Les fenêtres demeurent associées à leur numéro de joueur.
- Un cadre orange et l'étiquette `JOUEUR EN COURS — MAÎTRE VPX` se déplacent vers la bonne fenêtre.
- Pendant le transfert : `TRANSFERT AU JOUEUR N`, `SYNCHRONISATION`, puis `JOUEUR N PRÊT`.
- Aucun score n'est affiché dans le Chat; ScoreView conserve ce rôle.

## Inventaire initial — 2026-08-24

### Briques déjà présentes dans `KarotsSugarpie/PinCabOS`

- [x] Dépôt principal confirmé : `KarotsSugarpie/PinCabOS`, branche `main`.
- [x] Version du dépôt observée : PinCabOS `Alpha 2.47` au moment de l'inventaire.
- [x] Client sécurisé existant : `opt/pincabos/bin/pincabos-link`.
- [x] Heartbeat existant : `opt/pincabos/bin/pincabos-link-heartbeat`.
- [x] Interface WebApp PinCabOS Link : `opt/pincabos/web/pincaboslink.py`.
- [x] Module de lobby cabinet : `opt/pincabos/web/pincabos_dashboard_lobby.py`.
- [x] Launcher central VPX : `opt/pincabos/launchers/pincabos-launch-core.sh`.
- [x] Intégration ScoreView et FullDMD existante dans `opt/pincabos/bin` et `opt/pincabos/web`.
- [x] Outils d'entrées cabinet existants : `pincabos_webapp_inputs.py`, `evtest`, `input-utils`, SDL et udev.
- [x] PipeWire, FFmpeg, Chrome, CMake, Ninja, GCC/G++, GDB, Git et GitHub CLI déjà inventoriés dans l'image PinCabOS.
- [x] Environnement Python Flask/Waitress existant pour la WebApp locale.
- [x] Aucune implémentation de synchronisation physique VPX trouvée dans le dépôt PinCabOS actuel.
- [x] Aucun dépôt distinct de code source pincabos.cc identifié pendant l'inventaire initial.

## Dépôts nécessaires ou candidats

| Dépôt | Rôle | État/décision |
|---|---|---|
| [`KarotsSugarpie/PinCabOS`](https://github.com/KarotsSugarpie/PinCabOS) | Intégration OS, WebApp locale, launchers, services et publication | Existant, obligatoire |
| `KarotsSugarpie/PinCabOS-Sync` | Protocole, schémas, agent externe, adaptateurs non intrusifs, tests réseau et paquets | À créer après la Phase 1; recommandé séparé du gros dépôt rootfs |
| `KarotsSugarpie/PinCabOS-Server` | APIs pincabos.cc, lobby, signalisation, manifestes et migrations DB | À créer ou identifier; visibilité et secrets à décider; aucun secret dans Git |
| [`vpinball/vpinball`](https://github.com/vpinball/vpinball) | Référence en lecture seule pour comprendre les interfaces déjà disponibles | Aucun fork, patch, recompilation ou remplacement autorisé |
| [`vpinball/pinmame`](https://github.com/vpinball/pinmame) | Référence en lecture seule pour les interfaces d'état ROM déjà exposées | Aucun remplacement de la version utilisée par VPX BGFX |

Les forks et modifications de VPX BGFX et VPinFE sont interdits. Si les interfaces externes déjà disponibles ne suffisent pas, le résultat est NOGO et l'architecture de l'agent PinCabOS doit être revue sans toucher à ces composants.

## Outils et bibliothèques à évaluer

| Outil/dépôt | Usage envisagé | Licence observée | Décision actuelle |
|---|---|---|---|
| Plugin [`remote-control`](https://github.com/vpinball/vpinball/tree/master/plugins/remote-control) de VPX | Référence technique pour comprendre la réplication d'entrées | Fichier plugin GPLv3+ | Étudier son protocole et son comportement sans l'installer, le modifier ou en faire dépendre VPX BGFX |
| API plugins VPX | Inventaire des interfaces publiques déjà présentes | Licence VPX mixte, majoritairement GPLv3+ mais certains fichiers restent sous ancienne licence MAME | Audit en lecture seule; aucun nouveau plugin injecté dans VPX BGFX |
| Infrastructure [`state.c/state.h`](https://github.com/vpinball/pinmame/blob/master/src/state.c) de PinMAME | Comprendre les possibilités déjà exposées de sauvegarde/restauration ROM | Licence PinMAME mixte ancienne MAME/BSD-3-Clause | Audit en lecture seule; ne pas remplacer la bibliothèque utilisée par VPX BGFX |
| [`microsoft/msquic`](https://github.com/microsoft/msquic) | Transport QUIC chiffré C/C++ pour contrôle, snapshots et deltas | MIT | Candidat recommandé; comparer au DataChannel pendant le POC |
| [`google/flatbuffers`](https://github.com/google/flatbuffers) | Schéma binaire versionné et lecture efficace | Apache-2.0 | Candidat recommandé |
| [`paullouisageneau/libjuice`](https://github.com/paullouisageneau/libjuice) | ICE/STUN/TURN et traversée NAT sans ouvrir de port sur les routeurs des cabinets | MPL-2.0 | Candidat; valider son intégration au transport choisi |
| [`coturn/coturn`](https://github.com/coturn/coturn) | Relais TURN de secours lorsque la liaison directe échoue | BSD-3-Clause | Probablement requis pour Internet réel |
| [`paullouisageneau/libdatachannel`](https://github.com/paullouisageneau/libdatachannel) | Audio/Vidéo natif ou transport de données alternatif | MPL-2.0 | Candidat A/V; non obligatoire pour VPX Sync |
| [`PipeWire/pipewire`](https://github.com/PipeWire/pipewire) | Caméra, micro, casque et routage audio local | MIT/X11 pour le cœur, autres composants à auditer | Déjà présent; réutiliser |
| FFmpeg | Encodage/décodage A/V et diagnostic | LGPL/GPL selon la construction | Déjà présent; vérifier les options de build |
| WebRTC navigateur | Caméra/micro et grille Chat dans Chrome local | APIs navigateur | Candidat privilégié pour la première version A/V |

### Avertissements de licence et de contenu

- VPX est en transition d'une ancienne licence de type MAME vers GPLv3+. Aucune distribution VPX modifiée n'est prévue; la licence reste à vérifier avant de réutiliser du code dans un agent séparé.
- PinMAME est en transition de l'ancienne licence MAME vers BSD-3-Clause. Les modifications et distributions doivent respecter la licence applicable à chaque fichier.
- Les ROMs sont fournies par l'utilisateur et plusieurs ne peuvent pas être redistribuées librement. Le manifeste peut valider un hash sans héberger le fichier.
- Les tables, médias et PuP-Packs doivent avoir une autorisation de distribution compatible avec pincabos.cc.

## Outils de développement et de validation à prévoir

- CMake, Ninja, GCC/G++ et GDB — déjà présents.
- Git, GitHub CLI et GitHub Actions — déjà présents.
- `clang-format`, `clang-tidy` et sanitizers ASan/UBSan — à vérifier/ajouter dans l'environnement DEV.
- Wireshark ou `tshark`, `tcpdump` — à vérifier pour le diagnostic de protocole.
- `iperf3` — à vérifier pour les mesures réseau.
- `tc netem` — fourni par iproute2, pour simuler latence, perte, duplication et réordonnancement.
- `turnutils_uclient` — à prévoir avec coturn pour valider le relais.
- Tests unitaires C++ et fuzzing des messages réseau — framework à choisir après le POC.
- Tests Python `pytest` pour les APIs, manifestes et contrôles du lobby — à ajouter au dépôt serveur.
- Horloges monotones et journaux structurés sans jetons, secrets, conversations ou contenus privés.

## Checklist d'exécution

### Phase 0 — figer le plan

- [x] Valider le capitaine permanent du lobby.
- [x] Valider le maître VPX migratoire selon le joueur actif.
- [x] Valider les répliques chaudes.
- [x] Valider l'absence de streaming vidéo du playfield.
- [x] Valider la latence réseau tolérée uniquement pour les spectateurs.
- [x] Valider la grille Chat backglass 2/3/4 joueurs.
- [x] Valider ScoreView comme seul affichage du score.
- [x] Figer VPX BGFX et VPinFE comme composants intouchables.
- [x] Figer le Lobby pincabos.cc comme unique point d'entrée et autorité d'orchestration multijoueur.
- [x] Interdire tout passage du multijoueur par VPinFE.
- [x] Créer le document de référence et le safeword.
- [x] Publier ce document dans `DEV/` sur la branche `main` et confirmer son SHA.

**GO Phase 0 :** document publié sur GitHub et relisible depuis un nouveau chat.

### Phase 1 — audits en lecture seule

- [ ] Auditer les versions réellement actives sur le cabinet : PinCabOS, VPX BGFX, plugins, PinMAME/libPinMAME, VPinFE et ScoreView.
- [ ] Relever les commits et hashes exacts des binaires VPX/PinMAME utilisés par PinCabOS.
- [ ] Auditer en lecture seule les interfaces externes déjà disponibles pour observer les entrées, ticks, objets dynamiques, rendu, DMD, audio et cycle de vie, sans charger de nouveau code dans VPX BGFX.
- [ ] Auditer le source du plugin VPX `remote-control` comme référence seulement, sans l'installer ni modifier VPX BGFX.
- [ ] Auditer les possibilités externes de pause/reprise et export/import de l'état physique sans patch, fork ou recompilation.
- [ ] Déterminer si l'état VBScript peut être observé ou reconstruit par une interface externe existante.
- [ ] Auditer `state.c/state.h` PinMAME et les APIs déjà exposées sans remplacer la bibliothèque utilisée par VPX BGFX.
- [ ] Prouver que VPinFE est absent du chemin multijoueur et identifier le chemin Lobby pincabos.cc → agent local → launcher PinCabOS existant → VPX BGFX intact.
- [ ] Auditer le code actif de pincabos.cc : comptes, amis, chat, lobby, tables et APIs cabinet.
- [ ] Identifier où le code serveur pincabos.cc doit être versionné.
- [ ] Produire une matrice de licences pour chaque fichier susceptible d'être réutilisé dans l'agent externe; aucun fichier VPX BGFX ou VPinFE ne sera modifié.
- [ ] Aucun changement de service, heartbeat, token, table ou configuration pendant cette phase.

**GO Phase 1 :** rapport prouvant qu'un agent externe peut fonctionner avec VPX BGFX et VPinFE intacts, et que VPinFE est totalement absent du chemin multijoueur. Toute nécessité de fork ou de patch constitue un NOGO.

### Phase 2 — stratégie de dépôts et environnement DEV

- [ ] Décider si `PinCabOS-Sync` est créé comme dépôt séparé.
- [ ] Créer/identifier le dépôt serveur pincabos.cc sans y placer de secret ni de dump utilisateur.
- [ ] Ajouter une règle de dépôt et de CI qui interdit tout fork, patch ou remplacement de VPX BGFX et VPinFE.
- [ ] Créer une branche DEV dédiée et une stratégie de versions du protocole.
- [ ] Ajouter compilation reproductible, tests et artefacts GitHub Actions.
- [ ] Ajouter SBOM et inventaire de licences.
- [ ] Définir un agent PinCabOS Sync installable et supprimable sans modifier VPX BGFX, VPinFE, leurs binaires, leurs plugins fournis ou leurs configurations.

**GO Phase 2 :** environnement isolé qui compile uniquement les composants PinCabOS et ne touche jamais à VPX BGFX ou VPinFE.

### Phase 3 — POC VPX local, sans réseau Internet

- [ ] Depuis le Lobby pincabos.cc, lancer deux instances isolées et intactes de VPX BGFX avec une table originale de test sans ROM; VPinFE ne doit pas être invoqué.
- [ ] Reproduire dans l'agent PinCabOS externe le principe de réplication observé dans `remote-control`, sans installer ou modifier ce plugin dans VPX BGFX.
- [ ] Exporter au minimum un tick, une bille et un flipper depuis l'instance maître au moyen d'une interface externe déjà disponible.
- [ ] Appliquer ces états dans l'instance réplique uniquement par une interface externe supportée, sans patcher VPX BGFX.
- [ ] Jouer manuellement une courte partie instrumentée et enregistrer les entrées avec leur tick monotone : Start, flippers, plunger et nudge.
- [ ] Enregistrer simultanément depuis l'agent externe un flux `PCOSREC v0` contenant le snapshot initial, les seeds aléatoires, les événements, les états physiques essentiels et un checksum par tick.
- [ ] Relancer la même table dans une instance VPX neuve à partir du même snapshot et réinjecter uniquement les entrées enregistrées.
- [ ] Comparer à chaque tick la position et la vitesse des billes, les angles des flippers, les switches, les timers et les checksums pour mesurer toute dérive déterministe.
- [ ] Effectuer un second replay en injectant directement le flux d'états enregistré dans une instance réplique dont la physique contradictoire est désactivée ou neutralisée.
- [ ] Afficher en direct l'exécution originale enregistrée et le replay côte à côte, ou avec un overlay fantôme, ainsi qu'un compteur de dérive.
- [ ] Conserver le fichier d'enregistrement, les logs de comparaison, les versions, les hashes de la table et de la configuration, et une courte capture vidéo comme artefacts de preuve.
- [ ] Mesurer le coût CPU, le temps par tick et la stabilité du rendu.
- [ ] Vérifier qu'aucun message arbitraire ne peut exécuter du code.

**Décision d'architecture après replay :**

- Si le replay des entrées reste identique, le lockstep déterministe peut rester candidat.
- Si les entrées divergent mais que le replay des états est fidèle, retenir le modèle maître/réplique avec deltas et snapshots autoritaires.
- Si le replay des états diverge ou exige un patch/fork, déclarer NOGO et revoir l'agent ou le protocole sans modifier VPX BGFX ou VPinFE.

**GO Phase 3 :** deux VPX BGFX intacts affichent la même bille et le même flipper à partir d'un maître unique, une nouvelle instance rejoue l'enregistrement avec une dérive acceptable, VPinFE n'est jamais invoqué, et les hashes des binaires/configurations protégés restent identiques avant et après.

### Phase 4 — protocole PinCabOS Sync V1

- [ ] Définir les schémas versionnés : contrôle, delta, snapshot, autorité, erreur et métriques.
- [ ] Comparer QUIC/MsQuic à un DataChannel uniquement comme transport de données.
- [ ] Choisir le transport avec preuve de latence, perte, chiffrement et traversée NAT.
- [ ] Séparer canal fiable de contrôle/snapshot et canal faible latence de deltas.
- [ ] Ajouter séquences, epochs, ticks, checksums, limites de taille et validation stricte.
- [ ] Ajouter snapshot périodique et récupération après perte de paquets.
- [ ] Fuzzer le décodeur avant toute exposition Internet.

**GO Phase 4 :** protocole binaire versionné, chiffré, testé et incapable d'exécuter du code arbitraire.

### Phase 5 — manifeste et cache de tables

- [ ] Définir `pincabos-multiplayer.json`.
- [ ] Ajouter signature serveur et vérification côté cabinet.
- [ ] Comparer tous les hashes avant le statut `PRÊT`.
- [ ] Télécharger de façon reprenable les ressources absentes.
- [ ] Refuser un package incomplet ou incompatible.
- [ ] Conserver les réglages matériels locaux de chaque cabinet.
- [ ] Appliquer les règles de licences des tables, médias, PuP-Packs et ROMs.

**GO Phase 5 :** deux cabinets prouvent qu'ils possèdent exactement le même package compatible.

### Phase 6 — lancement coordonné de deux cabinets

- [ ] Le capitaine choisit une table du catalogue pincabos.cc.
- [ ] Le lobby réserve les places Joueur 1 et Joueur 2.
- [ ] Les deux cabinets valident le manifeste.
- [ ] Le Lobby pincabos.cc ordonne aux agents PinCabOS locaux de lancer automatiquement la même table dans des modes maître/réplique distincts.
- [ ] Prouver dans les logs que VPinFE n'est jamais invoqué et ne reçoit aucun message multijoueur.
- [ ] Un arrêt du lobby ferme proprement les deux instances.
- [ ] Utiliser le launcher PinCabOS existant sans le remplacer et vérifier que VPX BGFX/VPinFE conservent leurs hashes et configurations.

**GO Phase 6 :** même table lancée automatiquement sur deux cabinets exclusivement depuis le Lobby pincabos.cc, avec VPX BGFX intact et sans passage par VPinFE.

### Phase 7 — réplication chaude pendant une balle

- [ ] Synchroniser billes, flippers et objets mobiles.
- [ ] Synchroniser lampes, flashers, sorties et animations nécessaires.
- [ ] Synchroniser DMD/ScoreView sans afficher le score dans le Chat.
- [ ] Synchroniser les événements audio nécessaires.
- [ ] Ajouter interpolation limitée sur les répliques seulement.
- [ ] Tolérer perte, réordonnancement et snapshots de correction.
- [ ] Vérifier que la réplique ne modifie jamais l'état officiel.

**GO Phase 7 :** la réplique suit une partie complète avec retard tolérable et sans influencer le maître.

### Phase 8 — faisabilité du snapshot complet

- [ ] Capturer puis restaurer l'état physique VPX uniquement par une interface externe déjà supportée.
- [ ] Capturer puis restaurer les objets dynamiques sans modifier le code, le binaire ou la configuration VPX BGFX.
- [ ] Capturer puis restaurer l'état VBScript/timers/aléatoire par une interface externe, ou démontrer une stratégie équivalente sûre.
- [ ] Capturer puis restaurer l'état PinMAME/ROM depuis une API déjà documentée ou exposée, sans remplacer la bibliothèque active.
- [ ] Restaurer l'état de l'agent PinCabOS Sync et ses files d'événements sans ajouter de plugin dans VPX BGFX.
- [ ] Comparer les checksums après restauration.
- [ ] Reprendre la partie sans changement visible de bille, règle, ROM ou joueur.
- [ ] Vérifier que les hashes de VPX BGFX, VPinFE et de leurs configurations sont strictement identiques avant et après le test.

**GO/NOGO CRITIQUE :** sans snapshot complet et restaurable par des interfaces externes, le maître migratoire ne peut pas être déclaré fonctionnel. En cas de NOGO, documenter l'écart et revoir l'agent ou le protocole; ne jamais corriger le problème en patchant VPX BGFX ou VPinFE.

### Phase 9 — maître migratoire à deux joueurs

- [ ] Détecter de façon fiable la fin de balle et le prochain joueur.
- [ ] Figer un tick commun.
- [ ] Transmettre et valider le snapshot final.
- [ ] Attribuer un jeton d'autorité unique avec nouvel `epoch`.
- [ ] Faire passer Cab 1 maître → réplique et Cab 2 réplique → maître.
- [ ] Bloquer les entrées de jeu sur les cabinets non actifs.
- [ ] Vérifier le chemin local bouton → VPX → flipper du nouveau maître.
- [ ] Prévoir retry, annulation ou saut d'un joueur si le transfert échoue.

**GO Phase 9 :** chaque joueur joue localement sur son cabinet, sans latence réseau ajoutée à ses flippers.

### Phase 10 — trois et quatre joueurs

- [ ] Généraliser slots, autorité et ordre de jeu jusqu'à quatre cabinets.
- [ ] Vérifier les transferts 1→2→3→4→1.
- [ ] Tester un joueur déconnecté, reconnecté ou volontairement retiré.
- [ ] Tester différents CPU/GPU, fréquences d'écran et contrôleurs.
- [ ] Empêcher le split-brain et les anciens messages d'une époque précédente.

**GO Phase 10 :** partie stable à quatre joueurs avec maître unique à chaque tour.

### Phase 11 — Chat Audio/Vidéo et backglass

- [ ] Choisir caméra et microphone/casque USB localement.
- [ ] Ajouter mute, volume, push-to-talk et indicateurs de confidentialité.
- [ ] Implémenter la grille deux joueurs avec Lobby + Backglass.
- [ ] Implémenter la grille trois joueurs avec Backglass.
- [ ] Implémenter la grille quatre joueurs sans Backglass.
- [ ] Déplacer le cadre `JOUEUR EN COURS — MAÎTRE VPX` après `HANDOFF_COMMIT` seulement.
- [ ] Garder ScoreView indépendant et sans duplication du score.
- [ ] Restaurer automatiquement le backglass normal à la fermeture.

**GO Phase 11 :** grille correcte en 2/3/4 joueurs et transfert visuel du joueur actif synchronisé avec l'autorité VPX.

### Phase 12 — Internet, NAT et relais

- [ ] Tester d'abord le protocole sur LAN.
- [ ] Ajouter découverte de chemin direct et hole punching.
- [ ] Valider qu'aucune redirection de port n'est nécessaire sur le routeur des cabinets.
- [ ] Installer un STUN/TURN contrôlé par PinCabOS.
- [ ] Utiliser le relais uniquement si la liaison directe échoue.
- [ ] Tester NAT symétrique, CGNAT et pare-feu restrictif.
- [ ] Mesurer latence, jitter, perte et bande passante.

**GO Phase 12 :** deux cabinets sur deux réseaux Internet distincts se connectent sans configuration manuelle du routeur.

### Phase 13 — sécurité et vie privée

- [ ] Authentifier utilisateur, cabinet, lobby et rôle.
- [ ] Utiliser des jetons courts, révocables et limités à une session.
- [ ] Chiffrer tous les canaux.
- [ ] Rejeter replay, epoch périmé, taille excessive et type inconnu.
- [ ] Limiter débits, snapshots et tentatives de connexion.
- [ ] Ne jamais journaliser jetons, conversations, audio, vidéo ou données privées.
- [ ] Activer caméra/micro uniquement avec indicateur visible et consentement local.
- [ ] Effectuer une revue de sécurité avant exposition publique.

**GO Phase 13 :** aucun cabinet ne peut lancer du code arbitraire, usurper le maître ou rejoindre un lobby non autorisé.

### Phase 14 — résilience

- [ ] Perte momentanée d'un paquet ou d'une connexion.
- [ ] Resynchronisation automatique par snapshot.
- [ ] Déconnexion du maître pendant sa balle.
- [ ] Échec du prochain maître pendant le handoff.
- [ ] Fermeture VPX ou reboot d'un cabinet.
- [ ] Reconnexion au lobby sans corrompre la partie.
- [ ] Retour à l'affichage local normal dans tous les cas.

**GO Phase 14 :** aucun échec réseau ne laisse VPX, le backglass ou les entrées dans un état dangereux ou bloqué.

### Phase 15 — tests de performance et critères d'acceptation

- [ ] Mesurer la latence locale des flippers avant et après activation du module.
- [ ] Prouver aucune dépendance réseau sur le chemin d'entrée du joueur actif.
- [ ] Viser 50–200 ms maximum pour les répliques, sans en faire une dépendance de la simulation.
- [ ] Viser un transfert d'autorité inférieur à une seconde lorsque le réseau et le matériel le permettent.
- [ ] Tester 30 minutes sans divergence sur une table originale.
- [ ] Tester 30 minutes avec une table PinMAME autorisée, notamment AFM pour le pilote fonctionnel.
- [ ] Simuler latence, jitter, pertes, duplication et réordonnancement avec `tc netem`.
- [ ] Tester deux, trois puis quatre cabinets.
- [ ] Produire des preuves reproductibles sans secrets.

### Phase 16 — packaging, pilote et publication

- [ ] Créer services systemd isolés pour le daemon Sync et le Chat local.
- [ ] Créer configuration, logs minimaux, désinstallation et rollback.
- [ ] Intégrer l'installation aux releases PinCabOS sans remplacer silencieusement les réglages utilisateur.
- [ ] Maintenir compatibilité de protocole et migration des manifestes.
- [ ] Déployer d'abord sur deux cabinets de test.
- [ ] Étendre à quatre cabinets après validation.
- [ ] Documenter limites, licences, ports, confidentialité et diagnostic.
- [ ] Mettre cette checklist à jour à chaque release.

## Règles PINFORGE-SAFE pour chaque étape

- Audit en lecture seule avant modification.
- Garde de cible, hostname, utilisateur, services et versions.
- Sauvegarde horodatée avant toute modification.
- Rollback autonome et testé.
- Aucun secret ou jeton affiché.
- Aucune modification du heartbeat ou du jeton PinCabOS Link sans étape explicitement dédiée.
- VPX BGFX et VPinFE sont intouchables dans tous les environnements : aucun patch, fork, remplacement, recompilation, injection intrusive ou modification de configuration.
- VPinFE est interdit dans le chemin de création, orchestration, lancement, transport ou contrôle du multijoueur.
- Le Lobby pincabos.cc est la seule autorité de session; l'agent local ne peut agir qu'après une commande de lobby authentifiée.
- Vérification des hashes de VPX BGFX, VPinFE et de leurs configurations avant et après chaque POC.
- Tests de régression sur VPX, VPinFE, ScoreView, DOF, B2S, PuP et WebApp.
- `clear` au début de chaque script Bash fourni pour exécution interactive.
- GO/NOGO explicite et arrêt immédiat en cas d'échec.
- Mise à jour de ce fichier uniquement après validation réelle.

## Journal des progrès

| Date | Étape | Résultat | Preuve/commit |
|---|---|---|---|
| 2026-08-24 | Phase 0 — architecture | GO — plan maître migratoire accepté | Brouillon initial |
| 2026-08-24 | Inventaire GitHub initial | GO — dépôt PinCabOS et briques existantes confirmés | Publication bloquée par GitHub `403 Resource not accessible by integration`; aucun commit créé |
| 2026-08-24 | Reconnexion GitHub | GO — accès `push` et `admin` confirmé sur `KarotsSugarpie/PinCabOS` | Checklist publiée dans `DEV/` sur `main` |
| 2026-08-24 | Phase 3 — scénario Record/Replay | Planifié — test local d'enregistrement, réinjection et comparaison live ajouté; non exécuté | Mise à jour du document de référence |
| 2026-08-24 | Non négociables VPX/VPinFE/Lobby | GO — VPX BGFX et VPinFE figés; VPinFE exclu du multijoueur; Lobby pincabos.cc déclaré seule autorité | Plan et phases contradictoires corrigés |

## Prochaine action

Préparer un audit PINFORGE-SAFE entièrement en lecture seule de la Phase 1. Cet audit doit comparer le dépôt avec les binaires réellement actifs, inventorier uniquement les interfaces externes déjà disponibles, prouver que VPinFE est absent du chemin multijoueur et confirmer qu'un agent PinCabOS séparé peut fonctionner sans modifier VPX BGFX ou VPinFE. Toute nécessité de patch ou de fork est un NOGO.
