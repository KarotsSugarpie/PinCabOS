# PinCabOS Chat A/V — topologie Backglass 6 zones

Date de décision : 2026-08-26
Référence : `PINFORGE-SAFE-CHAT-AV-28`

## Décision

Le Chat texte existant reste séparé et inchangé dans son rôle.

Le Chat Audio/Vidéo doit utiliser une fenêtre Backglass dédiée, liée au lobby et indépendante du Chat texte. Cette fenêtre A/V utilise une topologie fixe de **6 zones (2 rangées × 3 colonnes)**.

```text
┌────────────────────┬────────────────────┬────────────────────┐
│ INVITÉ 1           │ INVITÉ 2           │ INVITÉ 3           │
│ vidéo + état A/V   │ vidéo + état A/V   │ vidéo + état A/V   │
├────────────────────┼────────────────────┼────────────────────┤
│ STATS LOBBY / GAME │ JOUEUR LOCAL        │ B2S LOCAL           │
│ lobby + partie     │ vidéo + état A/V    │ miroir live lecture │
│                    │                    │ seule               │
└────────────────────┴────────────────────┴────────────────────┘
```

## Règle d'identité locale

Sur **chaque cabinet**, la carte du joueur propriétaire/local de ce cabinet est toujours placée **en bas au centre**.

Les trois autres participants possibles sont placés dans les trois zones du haut.

Le maximum reste donc de **4 participants** :

- 1 joueur local ;
- jusqu'à 3 invités distants.

La topologie ne doit pas être réorganisée selon le speaker actif. Un participant qui parle peut être mis en évidence visuellement (bordure/glow/indicateur), mais les cartes ne changent pas de position pendant l'appel.

## Ordre des invités

Les trois invités doivent être remplis de façon déterministe à partir de l'ordre des sièges/membres du lobby, en excluant le joueur local. Les zones inoccupées restent des emplacements neutres/attente afin que la géométrie ne saute pas quand un participant rejoint ou quitte.

## Zone bas-gauche — Lobby / Game

Cette zone est réservée aux informations réellement disponibles depuis le lobby et l'état de partie, par exemple :

- nom / ID du lobby ;
- table sélectionnée ;
- état de la session ;
- joueurs connectés / prêts ;
- ordre de jeu ;
- scores / progression / état de manche lorsque ces données sont réellement disponibles ;
- état de synchronisation et connexion utile au diagnostic.

Aucune donnée de jeu ne doit être inventée si elle n'est pas exposée par la chaîne multijoueur.

## Zone bas-centre — joueur local

Toujours le propriétaire/local du cabinet courant.

Cette carte contient :

- vidéo locale ;
- nom utilisateur / nom du cabinet ;
- état micro ;
- état caméra ;
- état connexion ;
- indicateur mute/caméra ;
- éventuellement état prêt / tour courant lorsque fourni par le lobby.

La caméra et le micro restent **OFF par défaut** jusqu'à acceptation/activation explicite.

## Zone bas-droite — B2S local

Cette zone doit afficher un **miroir live en lecture seule du B2S/backglass local existant**.

Non négociable :

- ne pas modifier VPinFE ;
- ne pas modifier VPX ;
- ne pas modifier BGFX ;
- ne pas recréer un moteur B2S parallèle ;
- ne pas injecter de logique dans le B2S existant.

La source doit être auditée avant implémentation. Si possible, réutiliser la chaîne de capture X11/preview déjà canonique dans PinCabOS afin d'afficher une copie visuelle du B2S dans la zone A/V.

## Fenêtre A/V dédiée

La fenêtre A/V est distincte de la fenêtre Chat texte.

Comportement cible :

1. le lobby crée/rejoint une session A/V ;
2. l'appel entrant est présenté ;
3. l'utilisateur accepte/refuse ;
4. après acceptation, la fenêtre A/V dédiée s'ouvre sur le Backglass ;
5. LiveKit remplit les 3 slots invités + le slot local ;
6. la zone Lobby/Game reçoit les données de session ;
7. la zone B2S affiche le miroir live local ;
8. à la fin de l'appel, caméra/micro sont libérés et l'affichage Backglass normal est restauré.

## Contrôles de développement

Pendant le développement clavier :

- `Enter` : accepter/rejoindre ;
- `Esc` : raccrocher/quitter ;
- `M` : micro ON/OFF ;
- `V` : caméra ON/OFF ;
- navigation par flèches si nécessaire.

L'intégration des boutons physiques reste reportée jusqu'à audit réel des événements du cabinet.

## Contraintes réseau

- aucun port entrant chez les utilisateurs ;
- aucun UPnP ;
- cabinets en connexions sortantes uniquement ;
- LiveKit SFU/TURN central ;
- maximum 4 participants ;
- aucune dépendance P2P directe obligatoire.

## Prochaine preuve avant code UI final

1. auditer la source canonique du lobby cabinet et son contrat de données ;
2. auditer la source exacte permettant un miroir B2S local sans modifier VPinFE/VPX/BGFX ;
3. définir le mapping lobby-seat → slots invités ;
4. créer la route/module A/V canonique dans le WebApp existant, séparée du Chat texte ;
5. valider la topologie 6 zones en local avant branchement LiveKit complet.
