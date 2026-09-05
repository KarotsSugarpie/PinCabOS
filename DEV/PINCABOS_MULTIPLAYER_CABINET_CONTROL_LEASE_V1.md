# PinCabOS Multiplayer — Cabinet Control Lease V1

## But

Faire de `pincabos.cc` l'autorité qui réserve, arme, linke, ouvre l'A/V puis lance les cabinets Multiplayer, sans modifier VPX privé, BGFX privé ni VPinFE.

> **Mise à jour terrain : 2026-09-05.** La phase `armed` est maintenant validée en conditions réelles sur deux cabinets. Le transport de jeu `master -> replica` reste volontairement bloqué en `pending-poc`; le bouton START ne doit donc pas encore déclencher une partie complète.

## Contrat serveur -> cabinet

`GET /api/device/multiplayer/state` inclut la session Multiplayer et le lease de contrôle :

```json
{
  "session": {
    "session_id": "mp-...",
    "phase": "ready",
    "room_code": "C3NCWL",
    "manifest_hash": "...",
    "is_this_cabinet_member": true,
    "topology": {
      "members": []
    }
  },
  "control": {
    "generation": 4,
    "desired": "armed",
    "acked": 2,
    "required": 2
  }
}
```

`control.desired` accepte uniquement :

- `released` : restituer le cabinet au mode normal;
- `armed` : arrêter `pincabos-vpinfe.service` et réserver le cabinet;
- `linked` : conserver le lease et appliquer la topologie master/replica;
- `video` : conserver le lease et ouvrir/rejoindre le Lobby A/V;
- `running` : lancer le VPX isolé associé au manifest;
- `handoff` : conserver la possession pendant un changement de maître.

Le cabinet ne doit jamais déduire la prise de contrôle de `session.phase` seule.

## État validé au 2026-09-05

Session de validation :

- Lobby : `C3NCWL`;
- session Multiplayer : `mp-e34278231052c8f8f480a218f5174bf3`;
- CAB1 : cabinet `1`, IP `192.168.254.237`, rôle prévu `master`, utilisateur LiveKit `pincabos-user-5`;
- CAB10 : cabinet `10`, IP `192.168.254.142`, rôle prévu `replica`, utilisateur LiveKit `pincabos-user-17`;
- package : `9Paf7-CL`, version `lab-1`;
- transport de jeu annoncé : `pending-poc`.

Preuve de prise de contrôle :

```text
Lobby READY
slot 1 / user 5  = 1
slot 2 / user 17 = 1

control.desired    = armed
control.generation = 4

ACK cabinet 1  = armed / generation 4 / ok=1
ACK cabinet 10 = armed / generation 4 / ok=1
```

Résultat physique :

- `pincabos-multiplayer-agent.service` actif sur CAB1 et CAB10;
- `pincabos-vpinfe.service` inactif sur CAB1 et CAB10 après `armed`;
- aucun VPX LAB lancé pendant la validation `armed`;
- aucun VPX privé, BGFX privé ou fichier VPinFE modifié.

**GO phase `armed`.**

## Contrat cabinet -> serveur

L'endpoint est désormais déployé côté PinCabOS.CC :

`POST /api/device/multiplayer/control-ack`

Payload :

```json
{
  "session_id": "mp-...",
  "generation": 4,
  "state": "armed",
  "ok": true,
  "detail": null
}
```

Le serveur conserve les ACK par cabinet et génération. Une phase ne doit progresser que lorsque tous les membres requis ont ACK la génération courante.

Le test réel a validé `acked=2 / required=2` pour `armed`.

## Règles locales cabinet

### released — validé

1. arrêter uniquement le VPX isolé `VPX_MultiPlayers` si son PID appartient réellement à l'engine isolé;
2. fermer le hook A/V Multiplayer;
3. redémarrer `pincabos-vpinfe.service` seulement si VPinFE était actif avant la prise de lease;
4. écrire `sessions/control-lease.json` avec `state=released`;
5. ACK `released` avec la génération courante.

Baseline réelle validée avant le test : CAB1 + CAB10 `released`, VPinFE actif, aucun VPX LAB.

### armed — validé terrain

1. vérifier que le cabinet est membre de la session;
2. mémoriser si VPinFE était actif;
3. `systemctl stop pincabos-vpinfe.service`;
4. vérifier que VPinFE est inactif;
5. écrire `state=armed`;
6. ACK `armed` uniquement après validation locale.

**GO réel sur CAB1 + CAB10, génération 4.**

### linked — pas encore GO

1. conserver VPinFE arrêté;
2. conserver `session_id`, `generation`, rôle et topologie;
3. établir un vrai lien de session cabinet-à-cabinet;
4. vérifier un heartbeat/session handshake portant au minimum `session_id`, génération, manifest hash, cabinet IDs et rôles;
5. n'ACK `linked` que lorsque le transport réel est prêt.

Le code actuel garde `link_state=pending-transport`; c'est intentionnel. Il ne faut pas transformer artificiellement cette phase en GO.

### video — A/V prouvé manuellement, automatisation lease à terminer

Le stack existant doit être réutilisé :

- page locale : `/pincabos-link/lobby-av`;
- helper : `/usr/local/sbin/pincabos-lobby-av-backglass`;
- LiveKit : `wss://av.pincabos.cc`;
- commandes locales : `join`, `microphone`, `camera`, `hangup`, `close`.

Validation terrain :

- CAB1 `.237` : fenêtre A/V sur le Backglass physique, géométrie `1920x1080+5760+0`;
- CAB10 `.142` : cabinet un écran, A/V validé en overlay sur le Playfield;
- room LiveKit commune : `pincabos-lobby-10`;
- identité CAB1 : `pincabos-user-5`;
- identité CAB10 : `pincabos-user-17`;
- `roomJoin=True` sur les deux;
- audio et vidéo bidirectionnels confirmés sur le terrain.

Ce qui reste à faire : intégrer automatiquement `OPEN -> JOIN -> caméra/micro selon politique -> ACK video` dans le Control Lease, puis tester la fermeture/restauration sur `released`.

### running — code de garde présent, pas encore validé dans la séquence complète

1. exiger `session.phase == running`;
2. exiger un manifest SHA-256 de 64 caractères;
3. trouver exactement une table `.vpx` sous `tables-test/` dont le SHA-256 correspond;
4. lancer uniquement `/opt/pincabos/apps/VPX_MultiPlayers/engine/...` avec `HOME`, XDG et `PrefPath` isolés;
5. ne pas relancer si le PID isolé est déjà valide;
6. ne jamais atteindre cette phase tant que `linked` et `video` ne sont pas réellement ACK.

Le lancement manuel de l'engine isolé a déjà été prouvé antérieurement, mais **le lancement par la chaîne START complète n'est pas encore GO**.

## Séquence cible actuelle

```text
Lobby READY x N
    -> control=armed
    -> ACK armed x N                 [GO terrain]
    -> Host START
    -> control=linked
    -> vrai handshake MASTER/REPLICA [À FAIRE]
    -> ACK linked x N
    -> control=video
    -> A/V OPEN + JOIN automatique   [À INTÉGRER]
    -> ACK video x N
    -> countdown 10
    -> session RUNNING
    -> control=running
    -> lancement VPX_MultiPlayers
    -> ACK running x N
    -> Lobby PLAYING
```

## Sortie / erreur / RESET

```text
control=released
    -> stop VPX MultiPlayers isolé
    -> close A/V
    -> release lien réseau de jeu
    -> restore VPinFE si nécessaire
    -> ACK released
    -> Lobby OPEN
```

Cette restauration doit rester idempotente. Une perte réseau ne doit pas provoquer une libération aveugle d'un lease actif.

## État Git / publication

- PR #190 `feat(multiplayer): le Lobby prend réellement le contrôle des cabinets` : fusionnée le 2026-09-05;
- PR #195 / Alpha 3.95 : a publié la base Control Lease issue de #190;
- la branche historique `feat/multiplayer-cabinet-control-lease-v1` a ensuite reçu des correctifs A/V single-screen après la fusion de #190;
- commit `9ae1d5b5a6578ccdf9ead4b102839e1942b657e6` : fallback A/V single-screen / overlay;
- commit `7563d4c0db27453401d493b5c59e72c45037c127` : tentative borderless pour l'overlay CAB10.

**Important : ces deux commits A/V tardifs ne font pas partie du merge original de #190 sur `main`. Ils doivent être portés proprement sur une nouvelle branche/PR avant d'être considérés comme livrés par une release normale.**

Après la tentative borderless, CAB10 a affiché `FENÊTRE A/V OUVERTE` mais `DÉCONNECTÉ · REJOINDRE`; une procédure de fermeture/réouverture + rejoin LiveKit a été préparée, mais sa validation post-borderless n'a pas encore été rapportée. Le fonctionnement A/V bidirectionnel avait été confirmé avant ce dernier ajustement visuel.

## Frontières non négociables

- VPX privé : non lancé, non modifié;
- BGFX privé : non modifié;
- VPinFE : non modifié, seulement stop/start de son service;
- VPinFE n'est jamais le transport Multiplayer;
- transport cab-à-cab réel : reste à implémenter tant que la capacité annonce `pending-poc`;
- LiveKit/backglass : réutiliser le stack existant, pas de deuxième stack vidéo;
- ne jamais `killall VPinballX`; les arrêts doivent cibler uniquement le PID de l'engine isolé;
- ne pas donner de sudo illimité à l'agent Multiplayer.

## Prochaine étape autorisée

1. ne plus modifier la phase `armed` sauf bug reproductible;
2. porter proprement les correctifs A/V single-screen nécessaires vers `main`;
3. implémenter le vrai lien `MASTER CAB1 <-> REPLICA CAB10` et son ACK `linked`;
4. brancher le stack A/V existant sur `control=video` et obtenir ACK vidéo 2/2;
5. seulement ensuite tester `START -> countdown -> running` avec le VPX isolé.
