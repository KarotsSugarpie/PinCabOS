# PinCabOS Multiplayer — Cabinet Control Lease V1

## But

Faire de `pincabos.cc` l'autorité qui réserve, arme, linke, ouvre l'A/V puis lance les cabinets Multiplayer, sans modifier VPX privé, BGFX privé ni VPinFE.

## Contrat serveur -> cabinet

`GET /api/device/multiplayer/state` doit inclure :

```json
{
  "session": {
    "session_id": "mp-...",
    "phase": "ready",
    "room_code": "C3NCWL",
    "manifest_hash": "...",
    "is_this_cabinet_member": true,
    "topology": {
      "role": "master"
    }
  },
  "control": {
    "generation": 12,
    "desired": "armed"
  }
}
```

`control.desired` accepte uniquement :

- `released` : restituer le cabinet au mode normal;
- `armed` : arrêter `pincabos-vpinfe.service` et réserver le cabinet;
- `linked` : conserver le lease et appliquer la topologie master/replica;
- `video` : conserver le lease et ouvrir le chat A/V sur le backglass;
- `running` : lancer le VPX isolé associé au manifest;
- `handoff` : conserver la possession pendant un changement de master.

Le cabinet ne doit jamais déduire la prise de contrôle de `session.phase` seule.

## Règles locales cabinet

### released

1. arrêter uniquement le VPX isolé `VPX_MultiPlayers` si son PID appartient réellement à l'engine isolé;
2. fermer le hook A/V Multiplayer;
3. redémarrer `pincabos-vpinfe.service` seulement si VPinFE était actif avant la prise de lease;
4. écrire `sessions/control-lease.json` avec `state=released`.

### armed

1. vérifier que le cabinet est membre de la session;
2. mémoriser si VPinFE était actif;
3. `systemctl stop pincabos-vpinfe.service`;
4. vérifier que VPinFE est inactif;
5. écrire `state=armed`.

### linked

1. conserver VPinFE arrêté;
2. conserver `session_id`, `generation`, `role` et `topology`;
3. ne jamais lancer le VPX privé;
4. le transport réel cab-à-cab reste séparé du lease.

### video

1. conserver VPinFE arrêté;
2. demander l'ouverture du hook LiveKit/backglass;
3. ne pas lancer VPX tant que `desired != running`.

### running

1. exiger `session.phase == running`;
2. exiger un manifest SHA-256 de 64 caractères;
3. trouver exactement une table `.vpx` sous `tables-test/` dont le SHA-256 correspond;
4. lancer uniquement `/opt/pincabos/apps/VPX_MultiPlayers/engine/...` avec `HOME`, XDG et `PrefPath` isolés;
5. ne pas relancer si le PID isolé est déjà valide.

## Contrat cabinet -> serveur à ajouter sur PinCabOS.CC

Endpoint prévu :

`POST /api/device/multiplayer/control-ack`

Payload :

```json
{
  "session_id": "mp-...",
  "generation": 12,
  "state": "armed",
  "ok": true,
  "detail": null
}
```

Le serveur ne doit avancer qu'après ACK de tous les membres pour la génération courante.

## Séquence cible

```text
Lobby READY x N
    -> control=armed
    -> ACK armed x N
    -> Host START
    -> control=linked
    -> ACK linked x N
    -> control=video
    -> ACK video x N
    -> countdown 10
    -> session RUNNING
    -> control=running
    -> ACK running x N
    -> Lobby PLAYING
```

## Sortie / erreur / RESET

```text
control=released
    -> stop VPX MultiPlayers isolé
    -> close A/V
    -> restore VPinFE si nécessaire
    -> ACK released
    -> Lobby OPEN
```

## Frontières

- VPX privé : non lancé, non modifié;
- BGFX privé : non modifié;
- VPinFE : non modifié, seulement stop/start de son service;
- transport cab-à-cab réel : reste à implémenter séparément tant que la capacité serveur annonce `pending-poc`;
- LiveKit/backglass : doit réutiliser le mécanisme A/V déjà déployé, sans inventer un deuxième stack vidéo.
