# PinCabOS Chat Audio/Vidéo — checkpoint de fin de journée

**Date :** 2026-08-26  
**Safeword de reprise :** `PINFORGE-SAFE-CHAT-AV-28`  
**Reprise exacte :** après `CHAT-AV-38B`, avant la première modification serveur `CHAT-AV-39`.

Ce document fige l'état réellement prouvé à la fin de la séance. Le module A/V n'est **pas terminé**. Aucun item ci-dessous ne doit être interprété comme validé s'il n'est pas explicitement marqué GO.

## 1. Règles non négociables

- VPX, BGFX et VPinFE restent strictement intacts, dans leur code et dans leur état fonctionnel.
- Le Chat A/V ne passe pas par VPinFE.
- Le Chat texte reste séparé de la future fenêtre Lobby A/V.
- Pas de patch/overlay temporaire : modifier uniquement les sources canoniques après audit.
- Maximum cible : **4 participants**.
- Caméra et micro OFF par défaut; activation seulement après action/acceptation explicite.
- Aucun secret LiveKit, JWT, mot de passe, cookie, message, audio ou vidéo dans GitHub ou dans les logs.
- Aucun port entrant à ouvrir sur les cabinets utilisateurs; les cabinets initient uniquement des connexions sortantes.

## 2. Infrastructure publique A/V — GO

### DNS / endpoint

- `av.pincabos.cc` est l'endpoint A/V dédié.
- DNS A prouvé vers `142.112.59.9`.
- Certificat Let's Encrypt public valide pour `av.pincabos.cc`.

### Nginx Proxy Manager

- NPM : `192.168.254.6`.
- `av.pincabos.cc:443/TCP` est terminé par NPM.
- Proxy prouvé vers `192.168.254.55:7880`.
- WebSocket activé.
- Chaîne publique de signaling retenue : `wss://av.pincabos.cc`.

### LiveKit central

- Serveur : `PinCabOS.CC`, IPv4 `192.168.254.55`.
- LiveKit self-hosted `v1.13.5`.
- Service : `pincabos-livekit.service`, actif/enabled.
- Compte système dédié : `pincabos-livekit`.
- Config canonique : `/etc/pincabos/livekit.yaml`.
- TCP `7880` : API / signaling.
- TCP `7881` : ICE/TCP.
- UDP `7882` : ICE/UDP.
- TURN/UDP `443` : actif.
- `use_external_ip: true`.
- Limite LiveKit : `max_participants: 4`.
- HTTP local LiveKit `127.0.0.1:7880` : 200.

## 3. Credentials LiveKit — contrat prouvé, rotation encore à faire

Fichiers :

- `/etc/pincabos/livekit.yaml` : `0640 root:pincabos-livekit`.
- `/etc/pincabos/livekit.env` : `0640 root:www-data`.

`livekit.env` contient uniquement les variables attendues :

- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`
- `LIVEKIT_URL`

Audit prouvé :

- API key ENV == API key YAML : **GO**.
- API secret ENV == API secret YAML : **GO**.
- `LIVEKIT_URL=http://127.0.0.1:7880` : **GO**, URL backend locale volontaire; ne pas la remplacer par l'URL publique.
- URL client future : `wss://av.pincabos.cc`.

### NOGO sécurité restant

Le secret LiveKit a été affiché accidentellement pendant `CHAT-AV-35`. Il doit donc être considéré compromis et **roté avant utilisation réelle en production**.

Ne pas faire une rotation isolée. La rotation doit être coordonnée avec le futur générateur de JWT, avec backup + rollback + tests positifs/négatifs.

## 4. Backend pincabos.cc — GO pour la baseline, A/V non implémenté

Source live :

- Application : `/opt/pincabos-release-center`.
- Service : `pincabos-release-center.service`.
- Gunicorn : `127.0.0.1:8787`.
- `WorkingDirectory=/opt/pincabos-release-center`.
- Release Center actif et HTTP 200 au checkpoint.

État A/V backend :

- Aucun générateur de token LiveKit existant.
- Aucune route LiveKit/token/call existante avant le chantier.
- `jwt` absent.
- SDK Python LiveKit absent.
- `cryptography`, Flask et Gunicorn présents.
- `pincabos-release-center.service` charge actuellement seulement `/etc/pincabos-release-center/release-center.env`; il ne charge pas encore `/etc/pincabos/livekit.env`.

## 5. Contrat Lobby serveur déjà disponible — GO

Le Lobby existant fournit déjà la fondation nécessaire pour lier l'A/V à une vraie room serveur :

- routes `/api/lobby/...` authentifiées;
- `lobby_rooms` + `lobby_members`;
- room `id` et `code`;
- `host_user_id`;
- `max_players` limité de 2 à 4;
- membres ordonnés par `slot`;
- `user_id`, `username`, `display_name`, `cab_name`;
- `ready`, `score`, `is_host`;
- identité locale `me`;
- statut, table, start_at et server_time;
- refus `room_full` lorsque les slots sont épuisés.

Décision : le navigateur **ne choisira jamais une room LiveKit arbitraire**. La future room A/V sera dérivée du Lobby authentifié côté serveur.

## 6. Snapshot canonique serveur `.55` — GO 31/31

Archive validée :

`/root/pincabos-release-center-source-20260826-163230.tar.gz`

SHA-256 :

`d201baf4250ea2614b2cc11c40ce8707c1e63d35d3a2c2890ea6237ab2caa8d7`

Validation `CHAT-AV-38B` :

- archive lisible : GO;
- 31 fichiers attendus : 31;
- aucun `.env`, DB, SQLite, certificat, clé, log, cache, backup ou runtime : GO;
- comparaison archive -> source live : **31 MATCH**;
- différent : 0;
- live absent : 0;
- archive-only : 0.

Destination canonique du backend : dépôt privé `KarotsSugarpie/PinCabOS.CC`, miroir de `/opt/pincabos-release-center/` sous `opt/pincabos-release-center/`.

## 7. Cabinet `.237` — état validé

Cabinet : `PinCabOs`, IPv4 `192.168.254.237`.

### Caméra / micro

- Logitech C270 `046d:0825` détectée.
- `/dev/video0` et `/dev/video1` détectés.
- ACL `pinball` R/W validée.
- Micro C270 détecté et utilisable via PipeWire.
- `getUserMedia()` réel dans la future fenêtre Lobby A/V : **pas encore prouvé**.

### Écrans

Source canonique : `/opt/pincabos/config/screens/screens.json`.

Cabinet actuel 3 écrans :

- HDMI-0 : Playfield 3840x2160 — jeu seulement.
- DP-1 : Backglass 1920x1080 — future UI Lobby A/V.
- DP-2 : FullDMD 1920x1200 — reste DMD, séparé et intact.

Aucune intégration DMD au Chat A/V sur ce cabinet 3 écrans.

### Chaîne Backglass canonique

- `/opt/pincabos/web/pincaboslink.py`
- `/usr/local/sbin/pincabos-account-bridge`
- `/usr/local/sbin/pincabos-chat-backglass-agent`
- `/usr/local/sbin/pincabos-chat-backglass`

Bug `NoNewPrivileges=true` + `sudo -u pinball` corrigé de façon canonique par `/usr/sbin/runuser -u pinball --`.

Commit GitHub déjà publié :

`efa90148cd9658b65606785d0e23fc1ceb20dd8a` — `fix(chat): launch BackGlass Chrome with runuser under NoNewPrivileges`.

La vraie chaîne `backglass-set 1 -> agent -> OPEN`, puis fermeture/restauration, a été validée.

### Code expérimental local à ne pas promouvoir comme architecture finale

Une V1 A/V expérimentale a été injectée localement dans le Chat texte `pincaboslink.py`. Cette direction a ensuite été abandonnée au profit d'une **fenêtre Lobby A/V dédiée**. Elle est donc un état de développement/expérience, pas la source canonique finale.

À la reprise : restaurer/reprouver le Chat texte canonique avant d'introduire la route dédiée Lobby A/V.

## 8. Fenêtre Lobby A/V dédiée — décision figée

Document de layout : `DEV/PINCABOS_CHAT_AV_LAYOUT_6_ZONES.md`.

Topologie décidée : 2 x 3 zones :

- haut : Guest 1 / Guest 2 / Guest 3;
- bas-gauche : Lobby / Game réel;
- bas-centre : Local;
- bas-droite : B2S local.

Le joueur local reste toujours bas-centre sur son propre cabinet. Les invités sont placés de manière déterministe selon les slots du Lobby après exclusion du local. Pas de réorganisation par active speaker.

Pour un cabinet 3 écrans : FullDMD reste physiquement séparé.  
Pour un cabinet 2 écrans : la stratégie DMD est documentée mais la source DMD seule/crop générique non récursive reste à prouver.

## 9. Ce qui reste NOGO / non prouvé

- Secret LiveKit non roté.
- Générateur JWT LiveKit non créé.
- Autorisation JWT positive/négative non testée.
- Route WebApp cabinet dédiée Lobby A/V non créée.
- `getUserMedia()` C270 dans la future fenêtre non prouvé.
- Permissions Chrome caméra/micro persistantes non finalisées.
- Média WAN réel non prouvé.
- TCP 7881 depuis Internet non prouvé.
- UDP 7882 depuis Internet non prouvé.
- TURN UDP 443 en vrai appel non prouvé.
- Test derrière CGNAT / firewall restrictif non fait.
- Appel 2 cabinets non fait.
- Appel 4 participants non fait.
- Boutons physiques Start/Launch/flippers non audités pour l'A/V.
- Source DMD seule générique pour cabinet 2 écrans non résolue.

## 10. Ordre de reprise recommandé

1. Vérifier que la baseline serveur `.55` est bien synchronisée dans le dépôt privé `KarotsSugarpie/PinCabOS.CC`.
2. Reprouver l'état canonique du Chat texte cabinet et conserver la V1 expérimentale uniquement comme historique si nécessaire.
3. `CHAT-AV-39` : backup + rotation coordonnée des credentials LiveKit + raccordement sécurisé de `livekit.env` au backend + génération de JWT courts côté serveur.
4. Lier le JWT à l'utilisateur authentifié et à la room Lobby réelle; aucun nom de room fourni librement par le navigateur.
5. Tests d'autorisation positifs/négatifs, TTL court, aucune fuite de secret/JWT dans les logs.
6. Créer la route WebApp cabinet dédiée Lobby A/V et son orchestration Backglass, séparées du Chat texte.
7. Intégrer LiveKit dans cette fenêtre dédiée; caméra/micro OFF par défaut.
8. Prouver `getUserMedia()` C270 vidéo + audio et les permissions Chrome.
9. Test média WAN réel, ICE/UDP puis TURN/UDP.
10. Test 2 cabinets, puis 4 participants.
11. Audit/binding des boutons physiques seulement après stabilité de l'UI et hors interaction avec VPX/VPinFE.

## 11. Non-régression au checkpoint

À la fin des audits serveur :

- Release Center : active / HTTP 200.
- LiveKit : active / HTTP 200.
- nginx : active.
- aucune DB modifiée par les audits;
- aucun restart déclenché par `CHAT-AV-34B` à `38B`;
- VPX/BGFX/VPinFE non modifiés.

---

**État de fin de journée : fondation réseau/SFU/TLS/Lobby validée; sécurité et source canonique prouvées; intégration JWT + fenêtre Lobby A/V + média réel restent à faire.**
