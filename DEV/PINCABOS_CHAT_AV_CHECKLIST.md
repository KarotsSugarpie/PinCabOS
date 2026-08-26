# PinCabOS Chat Audio/Vidéo — checklist de déploiement

> Document de référence vivant pour le Chat Audio/Vidéo PinCabOS. À mettre à jour après chaque étape réellement validée. Aucun `[x]` sans preuve technique reproductible.

## Référence de reprise

- **Safeword :** `PINFORGE-SAFE-CHAT-AV-28`
- **Dépôt :** `KarotsSugarpie/PinCabOS`
- **Fichier :** `DEV/PINCABOS_CHAT_AV_CHECKLIST.md`
- **Branche :** `main`
- **Dernière mise à jour :** 2026-08-26
- **État global :** LiveKit central et signaling HTTPS publics validés; chaîne cabinet Chat texte canonique prouvée bit-à-bit; correctif `NoNewPrivileges`/`runuser` validé; décision prise de garder le Chat texte séparé et de créer une fenêtre **Lobby A/V dédiée** avec topologie 6 zones; détection 2/3 écrans canonique prouvée; chaîne de preview par rôles auditée; source DMD seule et contrat exact du lobby serveur restent à prouver; média WAN réel pas encore prouvé.

## Règles non négociables

- [x] Aucun port entrant à ouvrir chez les utilisateurs/cabinets.
- [x] Aucun UPnP requis chez les utilisateurs.
- [x] Les cabinets initient uniquement des connexions sortantes vers l'infrastructure PinCabOS.
- [x] Le média A/V passe par l'infrastructure centrale PinCabOS; aucune dépendance à une connexion directe cabinet-à-cabinet.
- [x] Architecture SFU/TURN centrale retenue.
- [x] Maximum prévu : 4 participants simultanés.
- [x] VPX BGFX et VPinFE restent strictement intacts.
- [x] Le Chat A/V ne passe pas par VPinFE.
- [x] Aucun enregistrement audio/vidéo par défaut.
- [x] Caméra inactive par défaut; activation seulement après action/acceptation explicite.
- [x] Micro inactif par défaut; activation seulement après action/acceptation explicite.
- [x] Ne jamais journaliser mots de passe, cookies, secrets LiveKit, jetons de session, contenu des messages, audio ou vidéo.
- [x] Pas de patch/overlay temporaire : retrouver et modifier la source canonique.
- [x] Le Chat texte reste séparé de la fenêtre Lobby A/V.

## A. Cabinet — caméra et microphone

- [x] Webcam USB détectée : Logitech C270 (`046d:0825`).
- [x] Vidéo V4L2 détectée.
- [x] Micro de la webcam détecté via PipeWire.
- [x] PipeWire opérationnel.
- [ ] Prouver `getUserMedia()` vidéo dans le navigateur de la **fenêtre Lobby A/V dédiée**.
- [ ] Prouver `getUserMedia()` audio dans le navigateur de la fenêtre Lobby A/V dédiée.
- [ ] Prouver le choix explicite du périphérique caméra/micro dans l'UI.
- [ ] Vérifier que caméra et micro restent coupés avant acceptation d'un appel.

## B. Source canonique pincabos.cc / Control Hub

- [x] Application active identifiée : `/opt/pincabos-release-center`.
- [x] Service actif confirmé : `pincabos-release-center.service`, Gunicorn, `WorkingDirectory=/opt/pincabos-release-center`.
- [x] Module actif identifié : `/opt/pincabos-release-center/pincabos_control_hub_v27.py`.
- [x] Frontend actif identifié : `/opt/pincabos-release-center/pincabos-control-hub-v27.js`.
- [x] `app.py` importe et enregistre directement `register_control_hub_v27`.
- [x] Routes Control Hub actives confirmées sous `/api/control-hub/...`.
- [x] Chat texte actuel identifié : polling GET/POST toutes les 4 secondes, sans moteur WebRTC/SFU existant avant ce chantier.
- [x] Source active `.55` auditée et déclarée publiable.
- [x] Snapshot canonique créé depuis une whitelist exacte de 31 fichiers.
- [x] Manifest SHA256 31/31 validé.
- [x] SHA256 archive : `d201baf4250ea2614b2cc11c40ce8707c1e63d35d3a2c2890ea6237ab2caa8d7`.
- [x] Snapshot exclut DB, backups, bytecode, `.env`, clés/certificats, logs, caches et données utilisateur.
- [x] Non-régression après snapshot : Release Center et LiveKit actifs; HTTP site et LiveKit = `200`.
- [ ] Versionner le snapshot `.55` dans GitHub sous le chemin canonique prévu, sans doublon fonctionnel.
- [ ] Comparer les SHA du code déployé `.55` avec la source GitHub après import.
- [ ] Déclarer officiellement le chemin GitHub canonique du serveur pincabos.cc.
- [ ] Auditer le **contrat exact du lobby multijoueur serveur** : room, membres/sièges, owner/local identity, ready, table, état de partie, scores/progression disponibles.
- [ ] Documenter les routes exactes utilisées par la fenêtre Lobby A/V avant modification applicative.

## C. Moteur central LiveKit

- [x] LiveKit SFU self-hosted central retenu.
- [x] LiveKit `v1.13.5` installé nativement sur `192.168.254.55`.
- [x] Service `pincabos-livekit.service` actif/enabled.
- [x] Compte système dédié `pincabos-livekit`.
- [x] Limite prévue : 4 participants.
- [x] TCP `7880` signal/API actif.
- [x] TCP `7881` ICE/TCP actif.
- [x] UDP `7882` ICE/UDP actif.
- [x] TURN/UDP `443` actif.
- [x] IP publique annoncée : `142.112.59.9`.
- [x] Endpoint local HTTP `200`.
- [x] VPX/BGFX/VPinFE non modifiés par l'installation LiveKit.

## D. NPM / TLS / signaling public

- [x] NPM confirmé sur `192.168.254.6`, version `2.15.1`.
- [x] TCP `443` NPM conservé pour HTTPS.
- [x] `av.pincabos.cc` résout vers `142.112.59.9`.
- [x] Proxy NPM vers `192.168.254.55:7880`.
- [x] WebSocket activé.
- [x] Certificat Let's Encrypt valide.
- [x] `https://av.pincabos.cc/` retourne HTTP `200`.
- [x] Signaling public prévu via `wss://av.pincabos.cc`.

## E. NAT / média WAN central

- [x] Redirections uniquement sur l'infrastructure centrale, jamais chez les utilisateurs.
- [ ] Prouver depuis Internet que TCP `7881` atteint `.55:7881`.
- [ ] Prouver depuis Internet que UDP `7882` atteint `.55:7882`.
- [ ] Prouver depuis Internet que UDP `443` atteint TURN `.55:443`.
- [ ] Tester depuis un réseau externe réel.
- [ ] Prouver un échange média réel via ICE/UDP.
- [ ] Prouver fallback TURN/UDP.
- [ ] Tester derrière CGNAT.
- [ ] Tester pare-feu restrictif.
- [ ] Ajouter plus tard TURN/TLS TCP `443` sans casser NPM TCP443.

## F. Authentification et jetons LiveKit

- [x] Python 3.13, Flask et Gunicorn présents côté `.55`.
- [x] `jwt` et SDK LiveKit absents avant intégration.
- [ ] Choisir l'intégration SDK/API LiveKit la moins intrusive.
- [ ] Lire `LIVEKIT_API_KEY` et `LIVEKIT_API_SECRET` depuis le fichier protégé; jamais au navigateur.
- [ ] Générer des jetons LiveKit courts côté serveur uniquement.
- [ ] Lier chaque jeton à l'utilisateur authentifié et au lobby/appel exact.
- [ ] Interdire une room arbitraire choisie par le client.
- [ ] Limiter publish/subscribe aux besoins de l'appel.
- [ ] Ajouter TTL court et identifiant de session.
- [ ] Ne jamais journaliser le JWT complet.
- [ ] Tests positifs/négatifs d'autorisation.

## G. Appels / lobby A/V

- [x] Fenêtre A/V décidée **séparée du Chat texte** et liée au lobby.
- [x] Maximum 4 participants : 1 local + jusqu'à 3 invités.
- [x] Le joueur local de chaque cabinet reste toujours en bas-centre.
- [x] Les trois invités occupent les trois zones du haut dans un ordre déterministe de lobby.
- [x] Les cartes ne changent pas de place selon le speaker actif.
- [ ] Définir le contrat d'appel : `idle`, `ringing`, `accepted`, `connecting`, `connected`, `ended`, `declined`, `failed`.
- [ ] Définir mapping lobby-seat → Guest 1/2/3 après exclusion du local.
- [ ] Acceptation explicite avant caméra/micro.
- [ ] Refus d'appel.
- [ ] Hangup propre.
- [ ] Reconnexion média contrôlée.
- [ ] Empêcher un non-membre d'entrer dans la room.
- [ ] Maximum 4 appliqué côté serveur et UI.

## H. Cabinet — source canonique Chat texte et orchestration Backglass

- [x] WebApp cabinet : `/opt/pincabos/web`, `pincabos-webapp.service`.
- [x] Chat texte canonique : `/opt/pincabos/web/pincaboslink.py`.
- [x] Route Chat texte Backglass : `GET /pincabos-link/chat-backglass` → `_backglass_html()`.
- [x] Chaîne canonique : `pincabos-account-bridge` → `pincabos-chat-backglass-agent` → `pincabos-chat-backglass` → route locale WebApp.
- [x] Agent root et état `/var/lib/pincabos-link` `0700 root:root` prouvés.
- [x] **5/5 Git blobs** des composants actifs `.237` prouvés identiques à GitHub avant modification.
- [x] Bug `NoNewPrivileges=true` + `sudo -u pinball` identifié.
- [x] Correctif canonique appliqué : `/usr/sbin/runuser -u pinball --`, `NoNewPrivileges` conservé.
- [x] Correctif validé par vraie chaîne `backglass-set 1` → agent → OPEN puis restauration → CLOSED.
- [x] GitHub commit du correctif helper : `efa90148cd9658b65606785d0e23fc1ceb20dd8a`.
- [x] Nouveau Git blob helper : `88bf841f8f01c37d6f5f797cd018b91e4aa10234`.
- [ ] **Restaurer `pincaboslink.py` texte canonique** sur `.237` : la V1 locale A/V expérimentale injectée dans le Chat texte est désormais obsolète.
- [ ] Reprouver après restauration le SHA canonique `9eeaffd755fb84dac7bf68e415c1c7dcc6d2ce654a7b30965ff9ce33f6e71868` et la non-régression Chat texte.

## I. Fenêtre Lobby A/V — topologie 6 zones

- [x] Document de référence : `DEV/PINCABOS_CHAT_AV_LAYOUT_6_ZONES.md`.
- [x] Topologie fixe 2×3 décidée : Guest1 / Guest2 / Guest3 en haut; Lobby/Game / Local / B2S en bas.
- [x] Local toujours bas-centre sur son propre cabinet.
- [x] Zone bas-gauche réservée aux données réelles du lobby/game, sans données inventées.
- [x] Zone bas-droite réservée au miroir B2S local en lecture seule.
- [x] Cabinet 3 écrans : FullDMD reste physiquement séparé.
- [x] Cabinet 2 écrans : DMD intégré doit être rendu dans la fenêtre A/V.
- [x] Trois placements DMD 2-écrans décidés : zone B2S, zone Lobby/Game, overlay carte locale.
- [x] Préférence DMD locale/persistante par cabinet.
- [ ] Définir la route WebApp canonique dédiée Lobby A/V; ne pas réutiliser la route Chat texte.
- [ ] Créer l'orchestration dédiée ouverture/fermeture sans modifier VPinFE/VPX/BGFX.
- [ ] Ajouter LiveKit dans cette fenêtre dédiée seulement après validation du layout local.
- [ ] Micro OFF par défaut.
- [ ] Caméra OFF par défaut.
- [ ] Indicateurs caméra/micro visibles.
- [ ] Restaurer l'affichage normal du Backglass à la fermeture.

## J. Écrans / B2S / DMD miroir

- [x] `screens.json` identifié comme source canonique de topologie.
- [x] Cabinet `.237` prouvé 3 écrans : HDMI-0 Playfield, DP-1 Backglass, DP-2 FullDMD.
- [x] Détection 2/3 écrans déjà native : `fulldmd=None` si troisième écran absent.
- [x] `pincabos-dashboard-live.service` / `pincabos-dashboard-live-capture` identifié comme producteur des previews par rôle.
- [x] Mapping canonique preview : `screen0.jpg=Playfield`, `screen1.jpg=Backglass`, `screen2.jpg=FullDMD`.
- [x] Capture dashboard-live basée sur `display-aliases.env`, X11grab, 5 fps; largeurs 640/480/360.
- [x] `/api/fulldmd/dmd-overlay/preview` répond HTTP 200 JPEG/no-store sur `.237`.
- [x] HQ preview absente pendant l'audit; fallback actif = `screen2.jpg` FullDMD complet 360×226.
- [x] `pincabos-scoreview-x11-hq-preview.sh` audité : capture DP-2 plein écran à 4 fps; non adapté tel quel au mode 2 écrans.
- [x] `pincabos_dmd_tuner.py::_screen_geometry()` audité : hypothèse DP-2 + fallback `1920x1200+5760+0`; **NOGO comme fondation générique 2 écrans**.
- [x] `pincabos-dmd-bridge-helper` audité : helper de sauvegarde/configuration des coordonnées DMD, **pas un producteur de pixels**.
- [ ] Identifier une source DMD seule/crop fiable indépendante de la fenêtre A/V pour éviter une capture récursive du Backglass en mode 2 écrans.
- [ ] Clarifier les coordonnées DMD `local/real` et leur référentiel avant tout crop.
- [ ] Généraliser toute géométrie via `screens.json`/rôle d'écran, jamais `DP-2` codé en dur.
- [ ] Prouver le miroir B2S local sans modifier VPinFE/VPX/BGFX.

## K. Contrôles de développement

- [x] Clavier uniquement pendant le développement A/V.
- [ ] `Enter` : accepter/rejoindre.
- [ ] `Esc` : quitter/raccrocher.
- [ ] `M` : mute/unmute micro.
- [ ] `V` : caméra on/off.
- [ ] Flèches : navigation/réglages si nécessaire.
- [ ] Vérifier qu'aucune touche de développement n'interfère avec VPX pendant une partie.
- [ ] Intégration boutons physiques reportée jusqu'à audit réel des événements cabinet.

## L. Tests d'acceptation A/V

- [ ] Test navigateur local avec caméra C270 réelle dans fenêtre Lobby A/V dédiée.
- [ ] Test audio bidirectionnel 2 utilisateurs.
- [ ] Test vidéo bidirectionnel 2 utilisateurs.
- [ ] Test sur deux réseaux Internet distincts.
- [ ] Test 3 participants.
- [ ] Test 4 participants.
- [ ] Test TURN/UDP forcé.
- [ ] Test perte réseau/reconnexion.
- [ ] Test hangup/rejoin sans caméra/micro fantôme.
- [ ] Test mode 3 écrans : FullDMD séparé intact.
- [ ] Test mode 2 écrans : DMD dans chacune des 3 positions configurables.
- [ ] Test aucune capture récursive A/V dans la zone DMD/B2S.
- [ ] Test aucune écriture/modification VPX BGFX VPinFE.
- [ ] Test aucune donnée média enregistrée.
- [ ] Mesurer CPU/RAM/bande passante SFU à 2/3/4 participants.

## M. Prochaine étape autorisée

1. **Restaurer le Chat texte canonique sur `.237`** en retirant la V1 A/V expérimentale injectée dans `pincaboslink.py`, avec backup/rollback et preuve SHA.
2. Auditer sur `.237` le référentiel exact des coordonnées DMD runtime (`X/Y/W/H`) et la chaîne de capture possible pour obtenir un **DMD seul** sans recursion en mode 2 écrans.
3. Auditer sur `.55` le contrat exact du lobby multijoueur dans `pincabos_control_hub_v27.py` avant de définir les 3 slots invités et la zone Lobby/Game.
4. Terminer l'import canonique du snapshot `.55` dans GitHub avant toute modification serveur A/V.
5. Définir ensuite la route WebApp cabinet dédiée **Lobby A/V** et son orchestrateur canonique.
6. Valider localement la topologie 6 zones + B2S/DMD miroir sans LiveKit.
7. Prouver `getUserMedia()` caméra/micro dans cette fenêtre dédiée.
8. Ajouter JWT/LiveKit puis tester 2, 3 et 4 participants et le média WAN.

## Journal des validations

### 2026-08-26 — Infrastructure A/V centrale

- **GO** LiveKit `1.13.5`, services/sockets centraux et signaling HTTPS public validés.
- **GO** `av.pincabos.cc` TLS/WebSocket public validé.
- **À PROUVER** portée WAN réelle des transports média.

### 2026-08-26 — Source `.55`

- **GO** Control Hub actif identifié et audité.
- **GO** snapshot publiable exact 31 fichiers validé 31/31.
- **GO** archive SHA256 `d201baf4250ea2614b2cc11c40ce8707c1e63d35d3a2c2890ea6237ab2caa8d7`.
- **À FAIRE** import GitHub canonique et audit exact du contrat lobby.

### 2026-08-26 — Provenance cabinet Chat texte

- **GO** cinq composants/units canoniques présents dans GitHub et déployés.
- **GO** identité 5/5 Git blobs `.237` ↔ GitHub prouvée avant modification.
- **GO** route Chat texte HTTP 200 et services critiques actifs.

### 2026-08-26 — Correctif orchestration Chat Backglass

- **GO** cause `NoNewPrivileges=true` + `sudo -u pinball` reproduite.
- **GO** helper modifié canoniquement vers `runuser`; NNP conservé.
- **GO** agent ouvre et referme la fenêtre via le vrai `backglass-set`.
- **GO** VPinFE/VPX/BGFX intacts et services actifs.

### 2026-08-26 — Décision fenêtre Lobby A/V

- **DÉCISION** le Chat texte reste séparé.
- **DÉCISION** fenêtre A/V dédiée liée au lobby.
- **DÉCISION** topologie 6 zones : 3 invités en haut; Lobby/Game, Local, B2S en bas.
- **DÉCISION** joueur local toujours bas-centre.
- **DÉCISION** mode 2 écrans : DMD configurable B2S / Lobby / overlay local.

### 2026-08-26 — Audit topologie et preview DMD

- **GO** `screens.json` prouvé source de rôles et détection 2/3 écrans.
- **GO** cabinet actuel = 3 écrans; FullDMD DP-2 séparé.
- **GO** dashboard-live produit des previews role-aware `screen0/1/2` à 5 fps.
- **GO** preview DMD HTTP existante mais fallback actuel = FullDMD complet, pas DMD seul.
- **NOGO** `pincabos_dmd_tuner.py` et preview HQ actuels contiennent des hypothèses DP-2 spécifiques au cabinet actuel.
- **GO** `pincabos-dmd-bridge-helper` fournit/configure les coordonnées mais ne produit pas les pixels.
- **À PROUVER** source DMD seule non récursive pour mode 2 écrans.

---

### Politique de mise à jour

Après chaque étape :

1. Ajouter/mettre à jour les cases correspondantes.
2. Ajouter une note datée dans le journal si l'étape change l'état du projet.
3. Ne jamais cocher une étape uniquement parce qu'une configuration a été créée; une preuve fonctionnelle est requise.
4. Ne jamais ajouter de secret, token, mot de passe, cookie ou contenu utilisateur dans ce fichier.
5. Reprendre toujours à la première case pertinente non validée.
