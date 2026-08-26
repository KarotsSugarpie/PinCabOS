# PinCabOS — état de synchronisation cabinet — 25 août 2026

## Objectif

Figer l'état **réel et vérifié** des modifications faites sur le cabinet après le dernier sync cabinet GitHub, sans reconstruire du code de mémoire et sans toucher aux composants non négociables.

## Base GitHub vérifiée

Dernier sync cabinet complet déjà présent dans `main` avant ce document :

- commit `f063928ccae554b3d50bc1ddee44ce1ef9d53fc7`
- message : `feat(cabinet): sync PinCabOS Link and validated live fixes`
- date : 24 août 2026

Ce commit contient notamment PinCabOS Link, le heartbeat, le bridge de compte, le chat/backglass et leurs unités systemd.

## Modification cabinet appliquée après ce sync et absente de `main`

### VPinFE — statut PinCabOS.cc intégré dans la carte existante

Le cabinet contient maintenant un module PinCabOS-owned de statut intégré à la carte du thème PinCabOS :

- `/usr/local/sbin/pincabos-vpinfe-card-status`
- `/etc/systemd/system/pincabos-vpinfe-card-status.service`
- `/etc/systemd/system/pincabos-vpinfe-card-status.timer`
- `/home/pinball/.config/vpinfe/themes/PinCabOS/pincabos-status.json`
- modifications PinCabOS dans :
  - `/home/pinball/.config/vpinfe/themes/PinCabOS/index_table.html`
  - `/home/pinball/.config/vpinfe/themes/PinCabOS/style.css`
  - `/home/pinball/.config/vpinfe/themes/PinCabOS/theme.js`

L'audit live du cabinet confirme que `pincabos-vpinfe-card-status.timer` est installé et actif périodiquement et que `pincabos-vpinfe-card-status.service` existe comme service one-shot associé.

### Contrat visuel appliqué

Le bloc se trouve **dans la carte existante**, sous les compteurs, avec le titre `PinCabOS Info:`. Le vieux libellé `Powered By PinCabOS` n'est plus la cible du design.

États/couleurs à préserver lors du futur sync exact :

- connecté : vert ;
- hors ligne : rouge ;
- non lié : orange ;
- demandes en attente : orange/rouge ;
- utilisateur et nom du PinCab : mauve ;
- IP : jaune.

Les informations existantes de la carte (ratings, runtime, start count, etc.) doivent rester intactes.

## NOGO — ne pas fabriquer le patch

Les traces archivées confirment la présence et le fonctionnement du module, mais ne contiennent pas le corps complet de tous les fichiers ci-dessus.

**Règle : ne pas reconstituer ces fichiers au jugé.**

Avant de les ajouter au rootfs GitHub, récupérer les octets exacts depuis le cabinet et comparer leurs SHA-256. Le futur commit runtime doit être un miroir de l'état validé sur le cabinet, pas une réécriture approximative.

## Changements examinés mais volontairement exclus de ce sync

- changements du serveur `pincabos-feedback` / `pincabos.cc` : hors périmètre cabinet ;
- correctifs Table Manager du site : hors périmètre cabinet ;
- audits Media Recorder on-demand : audit seulement dans les traces vérifiées, pas de modification confirmée ;
- propositions de changement du verrou `pincabos-table-tree.sh` / import VPX : non déployées dans les traces vérifiées ;
- fichiers temporaires, backups, worktrees et données runtime : jamais à versionner comme source.

## Non négociables

- **VPX : aucune modification de son code/fonctionnement interne.**
- **BGFX : aucune modification de son code/fonctionnement interne.**
- **VPinFE : aucune modification du moteur/core.** Le thème PinCabOS et les helpers PinCabOS autour de VPinFE sont séparés et doivent le rester.
- Le multijoueur ne doit pas passer par VPinFE ; le Lobby PinCabOS.cc reste l'orchestrateur prévu.

## Prochaine synchronisation runtime

Quand l'état exact du cabinet est de nouveau lisible, capturer au minimum :

```text
/usr/local/sbin/pincabos-vpinfe-card-status
/etc/systemd/system/pincabos-vpinfe-card-status.service
/etc/systemd/system/pincabos-vpinfe-card-status.timer
/home/pinball/.config/vpinfe/themes/PinCabOS/index_table.html
/home/pinball/.config/vpinfe/themes/PinCabOS/style.css
/home/pinball/.config/vpinfe/themes/PinCabOS/theme.js
```

Puis comparer avec `main`, valider les SHA-256 et committer seulement les deltas exacts.

---

**Statut au 25 août 2026 :** GitHub documente désormais sans ambiguïté la divergence connue du cabinet. Le code runtime V2 lui-même reste volontairement NOGO tant que son contenu exact n'a pas été recapturé.