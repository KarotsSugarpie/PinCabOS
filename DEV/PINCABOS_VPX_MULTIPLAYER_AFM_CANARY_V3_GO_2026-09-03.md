# PinCabOS Multiplayer — AFM Canary V3 GO

> Preuve technique intermédiaire de la Phase 3 du mode multijoueur PinCabOS.
>
> **Date :** 2026-09-03  
> **Table pilote :** Attack from Mars (Bally 1995)  
> **ROM :** `afm_113b`  
> **VBS original SHA-256 :** `054d313de70f4467bf269e537a26e717964e879aad118458739380ce8c0d558c`  
> **VBS Canary V3 SHA-256 :** `3d59210e780682a03dedfdf12d609f8604a05bace01675db3f9ac588bd08aa2a`

## Objectif

Valider qu'un hook PinCabOS minimal peut être présent dans le script AFM, laisser l'initialisation normale VPX/PinMAME/B2S/ScoreView se terminer, puis s'activer tardivement sans modifier les inputs ni la physique.

## Conditions de test

Le Canary V3 :

- ajoute uniquement un appel `PCOS_LabTick` au `RealTime_Timer` existant ;
- n'ajoute aucun `ExecuteGlobal` supplémentaire ;
- n'injecte aucun bouton ;
- ne modifie aucune bille ;
- ne modifie aucun flipper ;
- ne modifie aucun switch ou état PinMAME ;
- attend `GameTime >= 20000` avant toute action ;
- écrit seulement un marqueur dans un fichier de log.

## Validation statique

Résultat :

```text
ExecuteGlobal original : 1
ExecuteGlobal avant : 1
ExecuteGlobal après : 1
GO [OK] Aucun ExecuteGlobal supplémentaire.
GO [OK] SHA CANARY V3 : 3d59210e780682a03dedfdf12d609f8604a05bace01675db3f9ac588bd08aa2a
```

Le `ExecuteGlobal` natif d'AFM reste inchangé. Aucun loader dynamique supplémentaire n'est introduit.

## Validation runtime

Pendant l'exécution, AFM a chargé normalement et est restée en attente du Start. Le hook n'a produit aucun mouvement volontaire sur le playfield.

Le log Canary contient :

```text
PCOSSTATE|CANARY_OK|GAMETIME|20000
```

Résultat :

```text
GO [OK] CANARY_OK reçu.
GameTime activation : 20000 ms
GO [OK] HOOK DIFFERÉ VALIDÉ
```

## Conclusion

**GO.**

Cette expérience prouve qu'un hook PinCabOS très léger peut :

1. être compilé avec la table AFM ;
2. laisser la table atteindre son état normal d'attente de Start ;
3. attendre un seuil déterministe de `GameTime` ;
4. exécuter du code PinCabOS après l'initialisation sans perturber la physique lorsque ce code reste non mutatif.

Cette preuve élimine le doute introduit par STATE REPLICA V1 : l'échec V1 provenait bien de la syntaxe VBScript du loader et non du principe d'un hook différé.

## Prochaine étape expérimentale

Créer un **Reader Canary** qui consomme progressivement le fichier `PCOSREC v0` pendant environ 60 secondes mais reste strictement en lecture seule.

Critères GO du Reader Canary :

- ROM/B2S/FullDMD/ScoreView restent opérationnels ;
- aucun input n'est injecté ;
- aucune propriété de bille/flipper/switch n'est modifiée ;
- 3000 frames `F` sont parsées ;
- 2202 états `B` sont parsés ;
- 222 inputs bruts sont identifiés ;
- `END|60004` est atteint ;
- le lecteur termine avec un marqueur `READER_OK` ;
- absence de stutter ou blocage visible important.

Après ce GO seulement, introduire les mutations par paliers : position `X/Y/Z`, puis vitesses `VX/VY/VZ`, puis flippers et enfin états ROM/switch nécessaires.
