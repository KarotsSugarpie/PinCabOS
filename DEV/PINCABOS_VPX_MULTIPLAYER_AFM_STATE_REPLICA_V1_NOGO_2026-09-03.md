# PinCabOS Multiplayer — AFM State Replica V1 — NOGO d’implémentation

> Addendum de preuve au rapport `DEV/PINCABOS_VPX_MULTIPLAYER_AFM_RECORD_REPLAY_STUDY_2026-09-03.md`.
>
> **Date :** 2026-09-03  
> **Table pilote :** Attack from Mars (Bally 1995)  
> **ROM :** `afm_113b`  
> **Statut :** NOGO d’implémentation du loader VBS; aucune conclusion négative sur l’architecture master→replica.

## Résumé

Le premier essai `AFM STATE REPLICA LAB V1` devait charger AFM normalement, attendre 20 secondes de `GameTime`, puis charger un moteur d’état externe destiné à appliquer les données PCOSREC : inputs, états de flippers et états de bille `X/Y/Z/VX/VY/VZ`.

Le test n’a jamais atteint cette étape. Visuellement, seul le playfield a été créé; ROM, directB2S, FullDMD et ScoreView ne se sont pas initialisés et aucune action de replay n’a eu lieu.

La cause a été identifiée de façon reproductible dans le VBS patché : le loader contenait des appels VBScript multilignes sans caractère de continuation `_` sur chaque ligne.

Exemple fautif observé :

```vbscript
Set FSO = _
    CreateObject(
        "Scripting.FileSystemObject"
    )
```

et :

```vbscript
Set TS = _
    FSO.OpenTextFile(
        "/home/pinball/.local/share/PinCabOS/multiplayer-lab/afm-state-replica/afm-state-replay-20260903-214536.vbs",
        1
    )
```

En VBScript, ces coupures de ligne exigent une continuation explicite. Le script principal n’a donc pas compilé entièrement et `Table1_Init` n’a pas été atteint. Par conséquent, PinMAME/ROM, directB2S, FullDMD et ScoreView n’ont jamais pu démarrer.

## Preuves

### VBS LAB fautif

SHA-256 :

```text
28dd0cdd4c1ffd2f882055ced4f8be4369f9a33dd7c73654c06b27d9f296d6f5
```

Copie conservée sur le cabinet :

```text
/home/pinball/.local/share/PinCabOS/backups/afm-state-replica-v1-failed/20260903-214938/
```

### VBS original restauré

SHA-256 :

```text
054d313de70f4467bf269e537a26e717964e879aad118458739380ce8c0d558c
```

Après rollback :

- aucun hook `PINCABOS_STATE_REPLICA_LOADER` restant;
- `Table1_Init` original présent;
- ROM `afm_113b` présente;
- `RealTime_Timer` original présent;
- restauration validée sans modification de VPX/BGFX/VPinFE/B2S/ScoreView.

## Classification

Ce résultat doit être classé :

**NOGO IMPLEMENTATION / LOADER COMPILE-TIME**

Il ne doit pas être classé :

- NOGO de réplication d’état;
- NOGO de `Ball.X/Y/Z`;
- NOGO de `VelX/VelY/VelZ`;
- NOGO de modèle master→replica;
- NOGO de PCOSREC comme source autoritaire.

Aucun de ces mécanismes n’a été exécuté pendant ce test.

## Conséquence pour la méthode de développement

Les prochaines versions doivent séparer les preuves :

1. **Canary loader** — prouver qu’un hook minimal compile et s’exécute après initialisation complète, sans input ni mutation physique.
2. **Input-only hook** — prouver que le hook peut déclencher une action connue sans toucher à la bille.
3. **Read-only state lookup** — lire le prochain état PCOSREC et le journaliser sans mutation.
4. **Single-ball position injection** — appliquer seulement `X/Y/Z`.
5. **Single-ball velocity injection** — ajouter `VX/VY/VZ`.
6. **Flipper authoritative correction** — ajouter états/angles de flippers.
7. **Lifecycle + switches + ROM state** — étendre PCOSREC et la réplique chaude.

Chaque niveau doit avoir son propre GO/NOGO afin qu’un défaut de syntaxe ou de chargement ne soit jamais confondu avec une limitation de l’architecture multijoueur.

## Prochaine preuve attendue

Installer un `STATE REPLICA CANARY V2` volontairement minimal :

- AFM originale comme base;
- une seule modification de `RealTime_Timer` pour appeler `PCOS_LabTick`;
- aucune fonction `ExecuteGlobal`;
- aucun chargement dynamique de gros script;
- aucun input;
- aucune écriture sur `Ball`, flippers, switches ou ROM;
- après `GameTime >= 20000`, écrire une seule ligne `PCOSSTATE|CANARY_OK|...` dans un log local;
- confirmer simultanément que playfield, ROM, directB2S, FullDMD et ScoreView sont tous actifs.

**GO Canary V2 :** table complètement normale + log `CANARY_OK` après 20 secondes. Seulement après ce GO, réintroduire progressivement la réplication d’état.
