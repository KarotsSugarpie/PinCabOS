# PinCabOS Multiplayer — CURRENT STATUS

> Document de reprise rapide. Mettre ce fichier à jour après chaque GO/NOGO important.
>
> **Dernière mise à jour : 2026-09-05**

## Résumé en une phrase

Le Lobby `pincabos.cc` sait maintenant prendre réellement le contrôle de deux cabinets et arrêter VPinFE avec ACK 2/2; le stack LiveKit A/V a été validé manuellement sur les deux cabinets; le dernier gros bloc avant un vrai START reste le transport de jeu `MASTER -> REPLICA` puis l'automatisation de la phase vidéo.

## État global

| Bloc | État | Preuve / remarque |
|---|---|---|
| Lobby 2 joueurs | GO | room `C3NCWL`, joueurs 5 et 17 |
| Package commun | GO | `9Paf7-CL`, `lab-1` |
| Session Multiplayer | GO | `mp-e34278231052c8f8f480a218f5174bf3` |
| READY Lobby x2 | GO | slot 1 = 1, slot 2 = 1 |
| Control Lease `released` | GO | ACK baseline sur CAB1 + CAB10 |
| Control Lease `armed` | GO TERRAIN | génération 4, ACK 2/2 |
| Arrêt VPinFE | GO TERRAIN | inactive sur CAB1 + CAB10 |
| Aucun VPX LAB pendant ARM | GO | aucun processus isolé |
| LiveKit même room | GO | `pincabos-lobby-10` |
| LiveKit identités distinctes | GO | user 5 / user 17 |
| A/V CAB1 Backglass | GO TERRAIN | `.237`, Backglass dédié |
| A/V CAB10 single-screen | GO TERRAIN avant borderless | `.142`, overlay Playfield |
| Audio/vidéo bidirectionnels | GO TERRAIN | confirmation visuelle/audio utilisateur |
| Overlay borderless CAB10 | PENDING REVALIDATION | tentative tardive, reconnect post-fix à revalider |
| `control=linked` | NOGO/PENDING | transport réel encore `pending-poc` |
| `control=video` automatique | PENDING | stack manuel prouvé, hook lease à brancher |
| `control=running` complet | PENDING | garde présente, chaîne START non validée |
| Synchronisation physique live entre deux CABs | PENDING | modèle master/hot-replica prouvé localement, réseau réel non branché |
| Handoff joueur actif | PENDING | pas encore testé |

## Cabinets de référence

### CAB1

- cabinet_id : `1`
- IP : `192.168.254.237`
- hostname : `PinCabOs`
- rôle cible initial : `master`
- user_id Lobby : `5`
- identité LiveKit : `pincabos-user-5`
- écran A/V : Backglass dédié
- géométrie observée : `1920x1080+5760+0`

### CAB10

- cabinet_id : `10`
- IP : `192.168.254.142`
- hostname : `PinCabOs`
- rôle cible initial : `replica`
- user_id Lobby : `17`
- identité LiveKit : `pincabos-user-17`
- topologie : un seul écran
- écran A/V : overlay sur Playfield
- géométrie overlay validée : `869x489+398+13`

## Session de référence

```text
Lobby code       : C3NCWL
Lobby room id    : 10
Session id       : mp-e34278231052c8f8f480a218f5174bf3
Mode             : live-multiplayers-lab
Protocol         : pcos-sync-control/1
Transport jeu    : pending-poc
Package          : 9Paf7-CL
Package version  : lab-1
```

Hashes observés :

```text
manifest / ready : 4e2f52c7046eaa7a5e5530ef801682a3726070e2204e7865b9e17e3e8f82e43c
engine           : b19a1c81b55720e8dff4e978d37b0225b99b73dbd54ac35797754015c6fd0336
```

## Ce qui est réellement validé côté Control Lease

### Baseline `released`

Les deux cabinets avaient :

```text
Agent Multiplayer : active
VPinFE             : active
VPX LAB            : aucun
control            : released
```

Les deux cabinets ont ACK la génération baseline.

### Prise de contrôle `armed`

Après READY des deux joueurs :

```text
slot 1 user 5  ready=1
slot 2 user 17 ready=1

desired    = armed
generation = 4

cabinet 1  state=armed generation=4 ok=1
cabinet 10 state=armed generation=4 ok=1
```

Conséquence physique vérifiée :

```text
CAB1  VPinFE = inactive
CAB10 VPinFE = inactive
VPX LAB      = aucun sur les deux
```

**Conclusion : le Lobby possède réellement les cabinets.**

## Stack A/V validé

Le stack à réutiliser est déjà présent dans PinCabOS :

```text
/opt/pincabos/web/pincaboslink_lobby_av.py
/usr/local/sbin/pincabos-lobby-av-backglass
/usr/local/sbin/pincabos-lobby-av-runtime
/opt/pincabos/web/lobby-av-browser-guard/
```

Routes locales principales :

```text
/pincabos-link/lobby-av
/pincabos-link/api/lobby
/pincabos-link/api/lobby/av-token
/pincabos-link/api/lobby/window
/pincabos-link/api/lobby/control
```

Commandes A/V déjà supportées :

```text
join
microphone
camera
hangup
close
```

Validation LiveKit :

```text
URL       : wss://av.pincabos.cc
Room      : pincabos-lobby-10
CAB1      : pincabos-user-5
CAB10     : pincabos-user-17
RoomJoin  : True sur les deux
```

Le JOIN a été validé sur les deux cabinets et l'échange audio/vidéo bidirectionnel a été confirmé sur le terrain.

## Cas single-screen CAB10

CAB10 `.142` ne possède pas de Backglass physique. Le helper historique échouait donc sur `screens.json["backglass"]`.

Un correctif de laboratoire a ajouté un fallback :

```text
Backglass présent  -> plein écran Backglass
Backglass absent   -> overlay sur Playfield
```

Commits tardifs sur l'ancienne branche de #190 :

```text
9ae1d5b5a6578ccdf9ead4b102839e1942b657e6
  fallback single-screen / overlay

7563d4c0db27453401d493b5c59e72c45037c127
  suppression de la barre de titre / borderless
```

Le premier correctif a été validé sur CAB10 avec :

```text
OVERLAY 398 13 869 489
Window  : OPEN
LiveKit : CONNECTED
VPinFE  : inactive
VPX LAB : aucun
```

Après le correctif borderless, l'UI WebApp a montré la fenêtre comme ouverte mais l'appel comme déconnecté. Une procédure `close -> open -> join` a été préparée; le retour terrain final de cette procédure n'est pas encore enregistré dans ce document.

**Ne pas considérer le borderless comme GO release tant que cette revalidation n'est pas faite.**

## État Git important

PR #190 :

```text
feat(multiplayer): le Lobby prend réellement le contrôle des cabinets
```

- fusionnée sur `main` le 2026-09-05;
- head de la PR fusionnée : `eca560e3dd003162404a03e94851c5720a84a673`;
- publiée ensuite par PR #195 / Alpha 3.95.

Les commits `9ae1...` et `7563...` ont été ajoutés après la fusion sur la vieille branche `feat/multiplayer-cabinet-control-lease-v1`. Ils ne doivent pas être confondus avec le contenu déjà publié par #190/#195.

Avant release A/V single-screen : créer une nouvelle branche propre depuis `main`, porter uniquement les changements utiles, tester, puis PR.

## Architecture de synchronisation VPX décidée

Le modèle physique reste celui déjà prouvé dans les tests AFM :

```text
JOUEUR ACTIF = MASTER
       |
       | état autoritaire
       | snapshots / deltas / checksums
       v
AUTRES CABINETS = HOT REPLICAS
```

POC local déjà prouvé :

- lecture PCOSREC temps réel;
- X/Y/Z autoritaires;
- VelX/VelY/VelZ autoritaires;
- flippers gauche/droit répliqués;
- 463/463 états de bille appliqués sur le canary V6/V7;
- rendu jugé fluide sur le test local.

Ce POC ne constitue pas encore le transport réseau final.

## Ce qui manque avant START

### 1. Vrai `linked`

Construire le transport de session entre CAB1 master et CAB10 replica.

Le handshake doit au minimum vérifier :

```text
session_id
generation
protocol version
manifest hash
engine hash
master cabinet id
replica cabinet id
role
epoch / sequence
heartbeat
```

`ACK linked` doit être impossible tant que ce lien réel n'est pas établi.

### 2. Automatiser `video`

Quand `control=video` :

```text
ouvrir fenêtre si nécessaire
-> JOIN LiveKit
-> confirmer connected=true
-> appliquer politique micro/caméra
-> ACK video
```

Sur `released` :

```text
hangup
-> close
-> libérer runtime A/V
```

Le système doit gérer Backglass dédié et single-screen automatiquement.

### 3. Seulement après : `running`

```text
ACK linked 2/2
ACK video  2/2
countdown
session phase = running
control = running
launch VPX_MultiPlayers isolé
ACK running 2/2
Lobby = playing
```

Le START ne doit jamais contourner `linked` ou `video`.

## Sécurité non négociable

- ne jamais modifier le VPX privé;
- ne jamais modifier BGFX privé;
- ne jamais modifier VPinFE;
- VPinFE = seulement `systemctl stop/start pincabos-vpinfe.service`;
- ne jamais lancer Multiplayer via VPinFE;
- engine Multiplayer uniquement sous `/opt/pincabos/apps/VPX_MultiPlayers/engine`;
- tables de test uniquement sous `tables-test/` tant que le LAB n'est pas promu;
- PID isolé vérifié avant stop; pas de `killall VPinballX`;
- pas de sudo illimité pour l'agent;
- génération de lease obligatoire pour rejeter les ACK obsolètes;
- panne réseau : ne pas libérer aveuglément un lease actif.

## Ordre de reprise recommandé

1. revalider CAB10 après le fix borderless ou revenir temporairement au dernier overlay A/V connu GO;
2. porter le support single-screen proprement depuis `main` dans une nouvelle PR;
3. implémenter le vrai handshake/lien `MASTER <-> REPLICA`;
4. obtenir `ACK linked` CAB1 + CAB10;
5. brancher l'A/V validé sur `control=video`;
6. obtenir `ACK video` CAB1 + CAB10;
7. seulement ensuite tester START/countdown/running;
8. commencer la réplication physique live via le transport réel;
9. ensuite seulement travailler le handoff joueur 1 -> joueur 2.

## Documents liés

- `DEV/PINCABOS_MULTIPLAYER_CABINET_CONTROL_LEASE_V1.md`
- `DEV/PINCABOS_VPX_MULTIPLAYER_MASTER_REPLICA.md`
- `DEV/PINCABOS_VPX_MULTIPLAYER_AFM_SESSION_2026-09-03_SUMMARY.md`
- `DEV/PINCABOS_VPX_MULTIPLAYER_AFM_RECORD_REPLAY_STUDY_2026-09-03.md`
- `DEV/PINCABOS_CHAT_AV_CHECKLIST.md`
- `DEV/PINCABOS_CHAT_AV_LAYOUT_6_ZONES.md`
