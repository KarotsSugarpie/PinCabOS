# PinCabOS Chat Audio/Vidéo — checkpoint de fin de journée

**Date :** 2026-08-26  
**Safeword de reprise :** `PINFORGE-SAFE-CHAT-AV-28`  
**Reprise exacte :** après `CHAT-AV-38B`, avant la première vraie modification serveur `CHAT-AV-39`.

Le module A/V n'est **pas terminé**. Ce document fige uniquement ce qui a été réellement prouvé aujourd'hui.

## 1. Règles non négociables

- VPX, BGFX et VPinFE restent strictement intacts, dans leur code et leur état fonctionnel.
- Le Chat A/V ne passe pas par VPinFE.
- Le Chat texte reste séparé de la future fenêtre Lobby A/V.
- Pas de patch/overlay temporaire : modifier uniquement les sources canoniques après audit.
- Maximum cible : **4 participants**.
- Caméra et micro OFF par défaut; activation seulement après action/acceptation explicite.
- Aucun secret LiveKit, JWT, mot de passe, cookie, message, audio ou vidéo dans GitHub ou dans les logs.
- Aucun port entrant à ouvrir sur les cabinets utilisateurs; les cabinets initient uniquement des connexions sortantes.

## 2. Infrastructure A/V centrale — GO

### Endpoint public

- Endpoint dédié : `av.pincabos.cc`.
- DNS A : `142.112.59.9`.
- Certificat Let's Encrypt public valide.
- URL client future : `wss://av.pincabos.cc`.

### Nginx Proxy Manager

- NPM : `192.168.254.6`.
- `av.pincabos.cc:443/TCP` -> NPM -> `192.168.254.55:7880`.
- WebSocket activé.
- Test public HTTPS : GO.

### LiveKit central

- Serveur : `PinCabOS.CC`, IPv4 `192.168.254.55`.
- LiveKit self-hosted `v1.13.5`.
- Service : `pincabos-livekit.service`, actif/enabled.
- Config canonique : `/etc/pincabos/livekit.yaml`.
- TCP `7880` : API/signaling.
- TCP `7881` : ICE/TCP.
- UDP `7882` : ICE/UDP.
- TURN/UDP `443` : actif.
- `use_external_ip: true`.
- `max_participants: 4`.
- HTTP local LiveKit : 200.

## 3. Credentials LiveKit — contrat prouvé, rotation encore NOGO

- `/etc/pincabos/livekit.yaml` : `0640 root:pincabos-livekit`.
- `/etc/pincabos/livekit.env` : `0640 root:www-data`.
- Variables présentes : `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `LIVEKIT_URL`.
- API key ENV == YAML : GO.
- API secret ENV == YAML : GO.
- `LIVEKIT_URL=http://127.0.0.1:7880` : **GO**, URL backend locale volontaire; ne pas la remplacer par l'URL publique.

Le secret LiveKit a été affiché accidentellement pendant `CHAT-AV-35`. Il doit donc être considéré compromis et **roté avant utilisation réelle**. Ne jamais faire une rotation isolée : elle doit être coordonnée avec le futur générateur JWT, avec backup + rollback + tests.

## 4. Backend pincabos.cc — baseline prouvée, A/V applicatif non implémenté

- Source live : `/opt/pincabos-release-center`.
- Service : `pincabos-release-center.service`.
- Gunicorn : `127.0.0.1:8787`.
- Release Center : actif / HTTP 200.
- Aucun générateur de token LiveKit existant.
- Aucune route LiveKit/token/call existante avant le chantier.
- `jwt` absent.
- SDK Python LiveKit absent.
- `cryptography`, Flask et Gunicorn présents.
- Le service charge seulement `/etc/pincabos-release-center/release-center.env`; `livekit.env` n'est pas encore raccordé.

## 5. Contrat Lobby serveur — GO

Le Lobby existant fournit déjà la fondation d'autorisation nécessaire :

- `lobby_rooms` + `lobby_members`;
- room `id` et `code`;
- `host_user_id`;
- `max_players` limité de 2 à 4;
- membres ordonnés par `slot`;
- `user_id`, `username`, `display_name`, `cab_name`;
- `ready`, `score`, `is_host`;
- identité locale `me`;
- table, statut, `start_at`, `server_time`;
- refus `room_full` lorsque les slots sont épuisés.

Décision : le navigateur **ne choisira jamais une room LiveKit arbitraire**. La future room A/V sera dérivée côté serveur du Lobby authentifié.

## 6. Snapshot canonique serveur `.55` — GO 31/31

Archive validée :

`/root/pincabos-release-center-source-20260826-163230.tar.gz`

SHA-256 :

`d201baf4250ea2614b2cc11c40ce8707c1e63d35d3a2c2890ea6237ab2caa8d7`

Validation `CHAT-AV-38B` :

- 31 fichiers attendus / 31 trouvés;
- 31 MATCH avec la source live;
- différent : 0;
- live absent : 0;
- archive-only : 0;
- aucun `.env`, DB, SQLite, certificat, clé, log, cache, backup ou runtime.

Dépôt serveur privé : `KarotsSugarpie/PinCabOS.CC`.

État GitHub au checkpoint :

- checkpoint serveur A/V versionné dans `PinCabOS.CC/docs/CHAT_AV_CHECKPOINT_2026-08-26.md`;
- manifeste SHA256 complet des 31 fichiers versionné dans `PinCabOS.CC/snapshots/pincabos-release-center-source-20260826-163230.sha256`;
- import navigable des 31 fichiers sous `opt/pincabos-release-center/` **pas encore effectué**; ne jamais reconstruire ces fichiers à partir de souvenirs ou snippets — utiliser uniquement le snapshot validé.

## 7. Cabinet `.237` — état validé et source texte restaurée

Cabinet : `PinCabOs`, IPv4 `192.168.254.237`.

### Caméra / micro

- Logitech C270 `046d:0825` détectée.
- `/dev/video0` et `/dev/video1` détectés.
- ACL `pinball` R/W validée.
- Micro C270 détecté via PipeWire.
- `getUserMedia()` réel dans la future fenêtre Lobby A/V : pas encore prouvé.

### Écrans

Source canonique : `/opt/pincabos/config/screens/screens.json`.

- HDMI-0 : Playfield 3840x2160 — jeu seulement.
- DP-1 : Backglass 1920x1080 — future UI Lobby A/V.
- DP-2 : FullDMD 1920x1200 — reste DMD, séparé et intact.

### Chaîne Backglass canonique

- `/opt/pincabos/web/pincaboslink.py`
- `/usr/local/sbin/pincabos-account-bridge`
- `/usr/local/sbin/pincabos-chat-backglass-agent`
- `/usr/local/sbin/pincabos-chat-backglass`

Bug `NoNewPrivileges=true` + `sudo -u pinball` corrigé par `/usr/sbin/runuser -u pinball --`.

Commit GitHub :

`efa90148cd9658b65606785d0e23fc1ceb20dd8a` — `fix(chat): launch BackGlass Chrome with runuser under NoNewPrivileges`.

La vraie chaîne `backglass-set 1 -> agent -> OPEN`, puis fermeture/restauration, a été validée.

### V1 A/V expérimentale dans le Chat texte — restaurée, pas active

Une V1 A/V locale avait été expérimentée dans `pincaboslink.py`, puis abandonnée au profit d'une fenêtre Lobby A/V dédiée.

Preuve finale retrouvée dans l'audit cabinet :

- `/opt/pincabos/backups/chat-av-local-v1-20260826-152720/pincaboslink.py` SHA `9eeaffd755fb84dac7bf68e415c1c7dcc6d2ce654a7b30965ff9ce33f6e71868`;
- `/opt/pincabos/web/pincaboslink.py` SHA `9eeaffd755fb84dac7bf68e415c1c7dcc6d2ce654a7b30965ff9ce33f6e71868`.

**GO : le Chat texte live est revenu au source canonique.** Il n'y a pas de V1 expérimentale active à restaurer demain.

## 8. Fenêtre Lobby A/V dédiée — décision figée

Document : `DEV/PINCABOS_CHAT_AV_LAYOUT_6_ZONES.md`.

Topologie 2 x 3 :

- haut : Guest 1 / Guest 2 / Guest 3;
- bas-gauche : Lobby/Game réel;
- bas-centre : Local;
- bas-droite : B2S local.

Le local reste toujours bas-centre. Les invités sont placés de manière déterministe selon les slots du Lobby après exclusion du local. Pas de réorganisation par active speaker.

Cabinet 3 écrans : FullDMD reste séparé.  
Cabinet 2 écrans : stratégie DMD documentée, mais source DMD seule/crop générique non récursive encore à prouver.

## 9. NOGO / non prouvé à la fermeture

- secret LiveKit non roté;
- générateur JWT absent;
- autorisation JWT positive/négative non testée;
- route WebApp cabinet dédiée Lobby A/V non créée;
- `getUserMedia()` C270 non prouvé;
- permissions Chrome caméra/micro non finalisées;
- média WAN réel non prouvé;
- TCP 7881 depuis Internet non prouvé;
- UDP 7882 depuis Internet non prouvé;
- TURN UDP 443 en vrai appel non prouvé;
- test CGNAT/firewall restrictif non fait;
- appel 2 cabinets non fait;
- appel 4 participants non fait;
- boutons physiques A/V non audités;
- source DMD seule générique 2-écrans non résolue.

## 10. Ordre de reprise

1. Importer bit-à-bit le snapshot validé `.55` dans `KarotsSugarpie/PinCabOS.CC/opt/pincabos-release-center/` et comparer les 31 SHA au manifeste.
2. `CHAT-AV-39` : backup + rotation coordonnée du credential LiveKit + raccordement sécurisé de `livekit.env` au backend + génération de JWT courts.
3. Lier chaque JWT à l'utilisateur authentifié et à sa vraie room Lobby; aucune room libre fournie par le navigateur.
4. Tests positifs/négatifs d'autorisation + TTL court + aucune fuite de JWT/secret dans les logs.
5. Créer la route WebApp cabinet dédiée Lobby A/V et son orchestration Backglass, séparées du Chat texte.
6. Intégrer LiveKit dans cette fenêtre dédiée; caméra/micro OFF par défaut.
7. Prouver `getUserMedia()` C270 vidéo + audio et les permissions Chrome.
8. Test média WAN réel : ICE/UDP puis TURN/UDP.
9. Test 2 cabinets, puis 4 participants.
10. Boutons physiques seulement après stabilité de l'UI, sans interaction avec VPX/VPinFE.

## 11. Non-régression

À la fin des audits :

- Release Center : active / HTTP 200;
- LiveKit : active / HTTP 200;
- nginx : active;
- aucune DB modifiée;
- aucun restart déclenché par les audits `CHAT-AV-34B` à `38B`;
- VPX/BGFX/VPinFE non modifiés.

---

**État de fin de journée : réseau/SFU/TLS/Lobby validés; cabinet Chat texte revenu canonique; baseline serveur figée 31/31 et manifestée dans le dépôt privé; intégration JWT + fenêtre Lobby A/V + média WAN restent à faire.**

## Reprise source synchronisée — 2026-09-02

Les sources PinCabOS Link contiennent maintenant :

- `pincaboslink_lobby_av.py`, fenêtre Backglass dédiée 6 zones;
- joueur local toujours bas-centre et invités ordonnés par slot après exclusion du local;
- zone Lobby/Game synchronisée toutes les 2 secondes depuis pincabos.cc;
- miroir JPEG B2S local en lecture seule;
- commandes cabinet JOIN, READY, START, SCORE et LEAVE dans `pincabos-account-bridge`;
- helper séparé `pincabos-lobby-av-backglass` utilisant l'écran `backglass` de `screens.json`;
- LiveKit client `2.22.2`, caméra et micro OFF jusqu'au clic explicite;
- contrôles clavier temporaires Enter/Esc/M/V;
- aucun changement à VPX, BGFX ou VPinFE.

Validation source effectuée : compilation Python, syntaxe JavaScript, `bash -n`, JSON et contrat JWT. Restent à prouver sur cabinet réel : permission C270/micro, média WAN ICE/TURN, affichage B2S vivant, test 2/4 participants et fermeture/restauration Backglass.
