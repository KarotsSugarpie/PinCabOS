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

## Cabinets à 2 écrans — DMD intégré au Backglass

La topologie A/V doit détecter la configuration réelle du cabinet.

### Cabinet 3 écrans

Si le cabinet possède Playfield + Backglass + FullDMD séparé, le FullDMD reste sur son écran physique dédié et **n'est pas déplacé dans la fenêtre A/V**.

### Cabinet 2 écrans

Si le cabinet possède seulement Playfield + Backglass et que le DMD est normalement intégré au Backglass, la fenêtre A/V doit conserver le DMD visible à l'intérieur de la composition 6 zones.

Le propriétaire du cabinet choisit **où son DMD local apparaît** parmi trois placements :

1. **zone B2S** — le DMD est affiché dans/au-dessus de la zone bas-droite B2S ;
2. **zone Lobby/Game** — le DMD est affiché dans/au-dessus de la zone bas-gauche Lobby/Game ;
3. **overlay joueur local** — le DMD est affiché par-dessus la carte vidéo locale en bas-centre.

Cette préférence est **locale au cabinet**, persistante, et ne change pas la disposition des autres cabinets du lobby. Chaque joueur peut donc choisir un placement DMD différent sur son propre cabinet.

Le DMD intégré doit être un **miroir/flux visuel en lecture seule de l'affichage DMD déjà existant**. Il ne faut jamais modifier VPinFE, VPX, BGFX, le rendu DMD original ou la logique de jeu pour obtenir ce placement.

Le placement DMD doit pouvoir être modifié dans les réglages de la fenêtre A/V/lobby, sans clavier ni souris dans la version finale. Pendant le développement, le choix peut être exposé dans l'interface WebApp ou avec les contrôles clavier temporaires.

Si le DMD est placé en overlay sur la carte locale, il doit rester visuellement distinct de la vidéo et ne pas masquer les indicateurs essentiels micro/caméra/connexion.

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
8. sur un cabinet 2 écrans, le DMD local est rendu dans le placement choisi par le propriétaire ;
9. à la fin de l'appel, caméra/micro sont libérés et l'affichage Backglass normal est restauré.

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
3. auditer la source exacte du DMD/FullDMD et déterminer comment détecter proprement un cabinet 2 écrans versus 3 écrans ;
4. définir le mapping lobby-seat → slots invités ;
5. définir la préférence locale persistante de placement DMD (`B2S`, `Lobby/Game`, `overlay joueur local`) ;
6. créer la route/module A/V canonique dans le WebApp existant, séparée du Chat texte ;
7. valider la topologie 6 zones en local avant branchement LiveKit complet.
