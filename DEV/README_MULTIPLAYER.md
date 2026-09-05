# PinCabOS Multiplayer — point d'entrée DEV

> **START HERE** pour reprendre le développement Multiplayer.
>
> Dernière mise à jour : **2026-09-05**

## État courant

Lire d'abord :

1. [`PINCABOS_MULTIPLAYER_CURRENT_STATUS.md`](./PINCABOS_MULTIPLAYER_CURRENT_STATUS.md) — état exact terrain, cabinets, LiveKit, Control Lease, Git et prochaines étapes.
2. [`PINCABOS_MULTIPLAYER_CABINET_CONTROL_LEASE_V1.md`](./PINCABOS_MULTIPLAYER_CABINET_CONTROL_LEASE_V1.md) — contrat `released/armed/linked/video/running/handoff` et ACK serveur/cabinets.
3. [`PINCABOS_VPX_MULTIPLAYER_MASTER_REPLICA.md`](./PINCABOS_VPX_MULTIPLAYER_MASTER_REPLICA.md) — architecture durable MASTER / HOT REPLICA / handoff.

## Où on est rendu

```text
Lobby READY x2                         GO
        |
        v
control=armed generation 4             GO
        |
        +--> CAB1  ACK armed           GO
        +--> CAB10 ACK armed           GO
        |
        v
VPinFE arrêté sur les deux             GO
        |
        v
A/V LiveKit manuel CAB1 + CAB10        GO terrain
        |
        v
control=linked                         PENDING
        |
        v
vrai transport MASTER -> REPLICA       PENDING
        |
        v
control=video automatisé               PENDING
        |
        v
START / countdown / running            NE PAS DÉBLOQUER ENCORE
```

La priorité est maintenant le **vrai lien de jeu CAB1 master <-> CAB10 replica**. Le transport annoncé est toujours `pending-poc`.

## Cabinets de référence

| Cabinet | IP | Rôle initial | A/V |
|---|---|---|---|
| CAB1 | `192.168.254.237` | master | Backglass dédié |
| CAB10 | `192.168.254.142` | replica | single-screen, overlay Playfield |

Lobby de test : `C3NCWL`.

Session de référence : `mp-e34278231052c8f8f480a218f5174bf3`.

## Documents POC physique AFM

Ces documents prouvent la faisabilité du modèle hot-replica mais **pas encore le réseau réel** :

- [`PINCABOS_VPX_MULTIPLAYER_AFM_SESSION_2026-09-03_SUMMARY.md`](./PINCABOS_VPX_MULTIPLAYER_AFM_SESSION_2026-09-03_SUMMARY.md)
- [`PINCABOS_VPX_MULTIPLAYER_AFM_RECORD_REPLAY_STUDY_2026-09-03.md`](./PINCABOS_VPX_MULTIPLAYER_AFM_RECORD_REPLAY_STUDY_2026-09-03.md)
- [`PINCABOS_VPX_MULTIPLAYER_AFM_CANARY_V3_GO_2026-09-03.md`](./PINCABOS_VPX_MULTIPLAYER_AFM_CANARY_V3_GO_2026-09-03.md)
- [`PINCABOS_VPX_MULTIPLAYER_AFM_PCOSREC_READER_V4_GO_2026-09-03.md`](./PINCABOS_VPX_MULTIPLAYER_AFM_PCOSREC_READER_V4_GO_2026-09-03.md)
- [`PINCABOS_VPX_MULTIPLAYER_AFM_XYZ_V5_GO_2026-09-03.md`](./PINCABOS_VPX_MULTIPLAYER_AFM_XYZ_V5_GO_2026-09-03.md)
- [`PINCABOS_VPX_MULTIPLAYER_AFM_XYZVEL_V6_GO_2026-09-03.md`](./PINCABOS_VPX_MULTIPLAYER_AFM_XYZVEL_V6_GO_2026-09-03.md)
- [`PINCABOS_VPX_MULTIPLAYER_AFM_HOT_REPLICA_V7_GO_2026-09-03.md`](./PINCABOS_VPX_MULTIPLAYER_AFM_HOT_REPLICA_V7_GO_2026-09-03.md)

## Documents A/V liés au Multiplayer

- [`PINCABOS_CHAT_AV_CHECKLIST.md`](./PINCABOS_CHAT_AV_CHECKLIST.md)
- [`PINCABOS_CHAT_AV_LAYOUT_6_ZONES.md`](./PINCABOS_CHAT_AV_LAYOUT_6_ZONES.md)
- [`PINCABOS_CHAT_AV_CHECKPOINT_2026-08-26.md`](./PINCABOS_CHAT_AV_CHECKPOINT_2026-08-26.md)

Le stack A/V réel existe maintenant et a été validé sur CAB1/CAB10. Le document `PINCABOS_MULTIPLAYER_CURRENT_STATUS.md` prime sur les anciennes cases non mises à jour des checkpoints historiques.

## Git / releases

- PR #190 : Control Lease — fusionnée.
- PR #195 / Alpha 3.95 : publication de la base Control Lease.
- Correctifs A/V single-screen tardifs sur l'ancienne branche de #190 : `9ae1d5b...` puis `7563d4c...`; ils doivent être reportés proprement sur une nouvelle PR depuis `main` avant release.

## Règle de sécurité

Ne jamais toucher au VPX privé, BGFX privé ou aux fichiers/configurations VPinFE pour faire fonctionner Multiplayer. VPinFE peut seulement être arrêté/redémarré via systemd. Tout moteur Multiplayer reste isolé sous `/opt/pincabos/apps/VPX_MultiPlayers`.
