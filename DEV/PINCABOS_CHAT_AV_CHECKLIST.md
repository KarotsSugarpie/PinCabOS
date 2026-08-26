# PinCabOS Chat Audio/Vidéo — checklist de déploiement

> Document de référence vivant pour le Chat Audio/Vidéo PinCabOS. À mettre à jour après chaque étape réellement validée. Aucun `[x]` sans preuve technique reproductible.

## Référence de reprise

- **Safeword :** `PINFORGE-SAFE-CHAT-AV-28`
- **Dépôt :** `KarotsSugarpie/PinCabOS`
- **Fichier :** `DEV/PINCABOS_CHAT_AV_CHECKLIST.md`
- **Branche :** `main`
- **Dernière mise à jour :** 2026-08-26
- **État global :** moteur SFU central et signaling HTTPS publics validés; source active du Control Hub auditée et déclarée publiable; snapshot canonique 31 fichiers créé et validé par SHA256 sans modification du runtime; chaîne cabinet Chat/Backglass canonique identifiée (`pincaboslink.py` + account bridge + agent + display helper) et présente dans GitHub; comparaison Git blob `.237` ↔ GitHub à terminer avant modification A/V; média WAN réel pas encore prouvé depuis un réseau externe.

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
- [x] Ne jamais journaliser mots de passe, cookies, secrets LiveKit, jetons de session, contenu des messages, audio ou vidéo.
- [x] Pas de patch/overlay temporaire : retrouver et modifier la source canonique.

## A. Cabinet — caméra et microphone

- [x] Webcam USB détectée : Logitech C270 (`046d:0825`).
- [x] Vidéo V4L2 détectée.
- [x] Micro de la webcam détecté via PipeWire.
- [x] PipeWire opérationnel.
- [ ] Prouver `getUserMedia()` vidéo dans le navigateur du cabinet.
- [ ] Prouver `getUserMedia()` audio dans le navigateur du cabinet.
- [ ] Prouver le choix explicite du périphérique caméra/micro dans l'UI.
- [ ] Vérifier que caméra et micro restent coupés avant acceptation d'un appel.

## B. Source canonique pincabos.cc / Control Hub

- [x] Application active identifiée : `/opt/pincabos-release-center`.
- [x] Service actif confirmé : `pincabos-release-center.service`, Gunicorn, `WorkingDirectory=/opt/pincabos-release-center`.
- [x] Module actif identifié : `/opt/pincabos-release-center/pincabos_control_hub_v27.py`.
- [x] Frontend actif identifié : `/opt/pincabos-release-center/pincabos-control-hub-v27.js`.
- [x] `app.py` importe et enregistre directement `register_control_hub_v27`.
- [x] Routes Control Hub actives confirmées sous `/api/control-hub/...`.
- [x] Chat texte actuel identifié : polling GET/POST périodique toutes les 4 secondes, sans moteur WebRTC/SFU existant avant ce chantier.
- [x] SHA déployés enregistrés : `app.py` = `b7398e5c092cc2e3ebcedd754fcc0634a995bb09a8a4a579fb5d420123bdd472`; module Hub = `0ee74053ddfd08569edb2629ddd60cff754b785517650c89ab81b533f6b95c0a`; JS = `38ae8bf8bf9dfecfe63b295042cd2449bf1720730b6711fec9962e12f5354bed`; CSS = `4fdc3eeba580ada0e0f7914885252117d6479fabd3af30a726fe65ddf8faf27f`.
- [x] `/opt/pincabos-release-center` confirmé comme **non-worktree Git**.
- [x] GitHub CLI (`gh`) absent sur `.55`; aucun besoin de l'installer pour l'audit.
- [x] Aucun paquet Debian ne revendique `app.py`, `pincabos_control_hub_v27.py` ou `pincabos-control-hub-v27.js`.
- [x] Recherche GitHub `main` : aucune copie de `pincabos-release-center`, `pincabos_control_hub_v27.py` ou du Control Hub actif retrouvée.
- [x] Provenance auditée : la source active de `.55` est actuellement la seule source complète prouvée pour ce Control Hub.
- [x] Liste candidate de fichiers source de premier niveau établie.
- [x] Exclusions permanentes établies : `backups/`, `__pycache__/`, `*.pyc`, DB/SQLite, `.env`, clés/certificats privés, logs, caches et données utilisateurs.
- [x] Runtime de données confirmé hors arbre source : `/var/lib/pincabos-release/...`.
- [x] Aucun marqueur de clé privée trouvé dans la source candidate.
- [x] Audit structurel Python : `app.secret_key` et mot de passe SMTP proviennent de l'environnement; tokens sensibles observés sont générés ou issus des requêtes, aucune valeur n'a été affichée.
- [x] Audit publication V1.2 : Python `HIGH=0`; les sept `MEDIUM` sont des comparaisons ou le fallback non secret `PINCABOS_BASE_URL`.
- [x] Audit publication V1.2 : aucun pattern de token connu détecté dans JS/HTML.
- [x] Les 14 `HIGH` JS/HTML ont été classés comme faux positifs de l’heuristique : identifiants de messages/validation UI tels que `current_password_invalid`, `password_mismatch`, `password_letter_required` et `invalid_or_expired_token`, pas des credentials.
- [x] Variables d’environnement sensibles `PINCABOS_TURNSTILE_SECRET` et `PINCABOS_SMTP_PASSWORD` confirmées sans fallback secret codé en dur.
- [x] Source candidate déclarée **publiable** à l’issue de l’audit V1.2.
- [x] Snapshot canonique créé depuis une whitelist exacte de **31 fichiers**.
- [x] Snapshot exclut DB, backups, bytecode, `.env`, clés/certificats, logs, caches et données utilisateur.
- [x] Manifest SHA256 contient 31 entrées et tous les fichiers extraits ont été validés `OK`.
- [x] SHA256 de l'archive : `d201baf4250ea2614b2cc11c40ce8707c1e63d35d3a2c2890ea6237ab2caa8d7`.
- [x] Non-régression après snapshot : SHA runtime inchangés; Release Center et LiveKit actifs; HTTP site et LiveKit = `200`.
- [ ] Versionner ce snapshot dans GitHub sans créer de doublon fonctionnel ni modifier le runtime `.55`.
- [ ] Comparer les SHA du code déployé avec la source GitHub canonique après import.
- [ ] Déclarer officiellement le chemin GitHub canonique du serveur pincabos.cc.
- [ ] Documenter la route/app d'intégration A/V exacte avant modification applicative.

> **Décision 2026-08-26 :** aucune nouvelle implémentation parallèle ne sera créée. La source actuellement exécutée sur `.55`, auditée, déclarée publiable et capturée dans un snapshot SHA-validé, doit être importée telle quelle dans GitHub et devenir la référence canonique avant toute modification A/V.

## C. Moteur central LiveKit

- [x] Architecture retenue : LiveKit SFU self-hosted central.
- [x] Déploiement natif retenu sur `PinCabOS.CC` / `192.168.254.55`; aucun Docker ajouté sur ce serveur.
- [x] LiveKit `v1.13.5` téléchargé depuis la release officielle.
- [x] Checksum officiel vérifié avant installation.
- [x] Service canonique créé : `pincabos-livekit.service`.
- [x] Service `active`.
- [x] Service `enabled`.
- [x] Compte système dédié `pincabos-livekit`.
- [x] Configuration limitée à IPv4 locale `192.168.254.55`.
- [x] Détection STUN de l'IP publique : `142.112.59.9`.
- [x] Validation externe STUN rendue non bloquante derrière NAT.
- [x] Limite LiveKit : 4 participants.
- [x] Signal/API local : TCP `7880` actif.
- [x] ICE/TCP : TCP `7881` actif.
- [x] ICE/UDP mux : UDP `7882` actif.
- [x] TURN/UDP : UDP `443` actif.
- [x] Endpoint LiveKit local retourne HTTP `200`.
- [x] Release Center non régressé après installation.
- [x] SHA `app.py` inchangé après installation.
- [x] VPX/BGFX/VPinFE non modifiés par l'installation LiveKit.

### Preuve validée — 2026-08-26

- `livekit-server version 1.13.5`
- `TCP7880=1 TCP7881=1 UDP7882=1 UDP443=1`
- LiveKit annonce `nodeIP: 142.112.59.9`.
- LiveKit annonce `rtc.portTCP: 7881`.
- LiveKit annonce `rtc.portUDP: 7882`.
- TURN annonce `turn.portUDP: 443`.
- `pincabos-livekit.service` : `active (running)`.

## D. NPM / TLS / signaling public

- [x] NPM confirmé sur `192.168.254.6`.
- [x] NPM `2.15.1` confirmé.
- [x] NPM conserve TCP `443` pour HTTPS.
- [x] Support Nginx `stream` / `ssl_preread` présent, sans modification nécessaire pour la V1.
- [x] `av.pincabos.cc` résout publiquement vers `142.112.59.9`.
- [x] Résolution confirmée via résolveur local `192.168.254.1`.
- [x] Résolution confirmée via `1.1.1.1`.
- [x] Résolution confirmée via `8.8.8.8`.
- [x] Proxy Host NPM canonique créé pour `av.pincabos.cc`.
- [x] Backend NPM : `http://192.168.254.55:7880`.
- [x] Support WebSocket activé dans NPM.
- [x] Certificat Let's Encrypt valide pour `av.pincabos.cc`.
- [x] HTTPS public `https://av.pincabos.cc/` retourne HTTP `200` avec TLS valide.
- [x] Signaling public peut utiliser `wss://av.pincabos.cc`.

## E. NAT / média WAN central

- [x] Principe fixé : les redirections de ports existent uniquement sur l'infrastructure centrale, jamais chez l'utilisateur.
- [ ] Prouver depuis Internet que TCP `7881` atteint `192.168.254.55:7881`.
- [ ] Prouver depuis Internet que UDP `7882` atteint `192.168.254.55:7882`.
- [ ] Prouver depuis Internet que UDP `443` atteint TURN sur `192.168.254.55:443`.
- [ ] Tester depuis un réseau externe réel, pas depuis le même LAN.
- [ ] Prouver un échange média réel via ICE/UDP.
- [ ] Prouver le fallback TURN/UDP.
- [ ] Tester un réseau derrière CGNAT.
- [ ] Tester un pare-feu réseau restrictif.
- [ ] Ajouter plus tard TURN/TLS sur TCP `443` pour le dernier niveau de compatibilité réseau, sans casser le TCP/443 NPM existant.

> **Important :** les sockets locaux LiveKit sont validés, mais la portée WAN des ports média n'est pas encore cochée tant qu'un client externe n'a pas réellement établi une session.

## F. Authentification et jetons LiveKit

- [x] Environnement Python actif audité : `/usr/bin/python3.13`, préfixe `/usr`.
- [x] Flask présent.
- [x] Gunicorn présent.
- [x] `jwt` absent avant intégration A/V.
- [x] `livekit` et `livekit.api` absents avant intégration A/V.
- [ ] Choisir l'intégration SDK/API LiveKit la moins intrusive dans la source canonique.
- [ ] Lire `LIVEKIT_API_KEY` et `LIVEKIT_API_SECRET` depuis le fichier protégé; ne jamais les exposer au navigateur.
- [ ] Générer des jetons LiveKit courts côté serveur uniquement.
- [ ] Lier chaque jeton à l'utilisateur authentifié PinCabOS.
- [ ] Lier chaque jeton à un lobby/appel précis.
- [ ] Interdire de rejoindre une room arbitraire choisie par le client.
- [ ] Limiter les permissions publish/subscribe aux besoins de l'appel.
- [ ] Ajouter expiration courte et identifiant de session.
- [ ] Ne jamais journaliser le jeton JWT complet.
- [ ] Ajouter tests positifs et négatifs d'autorisation.

## G. Appels individuels et de groupe

- [ ] Définir le contrat d'appel : `idle`, `ringing`, `accepted`, `connecting`, `connected`, `ended`, `declined`, `failed`.
- [ ] Appel individuel ami → ami.
- [ ] Appel de groupe lié au lobby.
- [ ] Acceptation explicite avant caméra/micro.
- [ ] Refus d'appel.
- [ ] Hangup propre.
- [ ] Reconnexion média contrôlée.
- [ ] Empêcher un utilisateur non membre d'entrer dans la room.
- [ ] Maximum 4 participants appliqué côté serveur et côté UI.

## H. Client navigateur / backglass

- [x] WebApp cabinet actif identifié : `/opt/pincabos/web`, service `pincabos-webapp.service` sous Waitress.
- [x] Frontend/route Chat cabinet canonique identifié : `/opt/pincabos/web/pincaboslink.py`.
- [x] Route Backglass canonique : `GET /pincabos-link/chat-backglass`, générée par `_backglass_html()`, HTTP local `200`, `Cache-Control: no-store`.
- [x] Chat texte cabinet existant identifié : contexte compte/amis, GET/POST chat, polling 4 s, bouton afficher/fermer Backglass.
- [x] Chaîne existante identifiée : `pincabos-account-bridge` → `pincabos-chat-backglass-agent` → `pincabos-chat-backglass` → route locale WebApp.
- [x] `pincabos-chat-backglass-agent.service` actif/enabled; processus réel UID/GID 0 (root).
- [x] État sécurisé `/var/lib/pincabos-link` confirmé `0700 root:root`; échec manuel `pinball` expliqué par permissions.
- [x] `backglass-get` et `status` réussissent dans le contexte root (`RC=0`).
- [x] Helper display ouvre `http://127.0.0.1/pincabos-link/chat-backglass` avec Chrome/Chromium positionné sur l'écran configuré.
- [x] Backglass physique confirmé : DP-1, `1920x1080+3840+0`; playfield HDMI-0 et FullDMD DP-2 restent séparés.
- [x] Les composants existent dans GitHub `main` aux chemins `opt/pincabos/web/pincaboslink.py`, `usr/local/sbin/pincabos-account-bridge`, `usr/local/sbin/pincabos-chat-backglass-agent`, `usr/local/sbin/pincabos-chat-backglass` et `etc/systemd/system/pincabos-chat-backglass-agent.service`.
- [ ] Prouver que les Git blob SHA des fichiers actifs `.237` correspondent exactement aux blobs GitHub `main` avant modification.
- [ ] Ajouter le client LiveKit dans la route/frontend cabinet canonique, sans nouveau frontend parallèle.
- [ ] Chat A/V affiché sur le Backglass.
- [ ] Playfield VPX non modifié.
- [ ] Micro OFF par défaut.
- [ ] Caméra OFF par défaut.
- [ ] Indicateurs caméra/micro visibles.
- [ ] Grille 2 participants.
- [ ] Grille 3 participants.
- [ ] Grille 4 participants.
- [ ] ScoreView reste indépendant; aucun score dupliqué dans le Chat.
- [ ] Restaurer l'affichage normal du Backglass à la fermeture de l'appel.

## I. Contrôles de développement

- [x] Décision temporaire : clavier uniquement pendant le développement A/V.
- [ ] `C` : ouvrir Chat.
- [ ] `Enter` : accepter/rejoindre.
- [ ] `Esc` : quitter/raccrocher.
- [ ] `M` : mute/unmute micro.
- [ ] `V` : caméra on/off.
- [ ] Flèches : navigation.
- [ ] Vérifier qu'aucune touche de développement n'interfère avec VPX pendant une partie.
- [ ] Intégration des boutons physiques reportée jusqu'à accès physique au cabinet.

## J. Tests d'acceptation A/V

- [ ] Test navigateur local avec caméra C270 réelle.
- [ ] Test audio bidirectionnel entre deux utilisateurs.
- [ ] Test vidéo bidirectionnel entre deux utilisateurs.
- [ ] Test sur deux réseaux Internet distincts.
- [ ] Test 3 participants.
- [ ] Test 4 participants.
- [ ] Test TURN/UDP forcé.
- [ ] Test perte momentanée de réseau et reconnexion.
- [ ] Test hangup/rejoin sans caméra fantôme ni micro restant ouvert.
- [ ] Test aucune écriture/modification de VPX BGFX et VPinFE.
- [ ] Test aucune donnée média enregistrée.
- [ ] Mesurer CPU/RAM/bande passante du SFU à 2, 3 et 4 participants.

## K. Prochaine étape autorisée

1. **Comparer les Git blob SHA des cinq composants cabinet actifs (`pincaboslink.py`, account bridge, Chat agent, display helper et unit systemd) avec GitHub `main`.**
2. Si les blobs concordent, déclarer officiellement cette chaîne comme source canonique cabinet et ne créer aucun doublon fonctionnel.
3. Terminer en parallèle l'import canonique du snapshot `.55` dans GitHub et comparer ses SHA.
4. Choisir ensuite la méthode de génération JWT/LiveKit côté serveur.
5. Ajouter l'API serveur A/V dans le vrai `pincabos_control_hub_v27.py` canonique.
6. Étendre la vraie route cabinet `/pincabos-link/chat-backglass` avec LiveKit et `getUserMedia()`, micro/caméra OFF par défaut.
7. Faire un premier test navigateur caméra/micro puis prouver le média WAN avec deux réseaux distincts.

## Journal des validations

### 2026-08-26 — Infrastructure A/V centrale

- **GO** LiveKit `1.13.5` installé nativement sur `192.168.254.55`.
- **GO** service `pincabos-livekit.service` actif/enabled.
- **GO** TCP 7880/7881 et UDP 7882/443 actifs localement.
- **GO** IP publique LiveKit détectée : `142.112.59.9`.
- **GO** `av.pincabos.cc` publié et résolu vers `142.112.59.9`.
- **GO** NPM proxifie `av.pincabos.cc` vers `.55:7880` avec TLS valide.
- **GO** signaling HTTPS public retourne `200`.
- **GO** Release Center et site PinCabOS non régressés.
- **À PROUVER** portée WAN réelle des transports média et session WebRTC depuis un réseau externe.

### 2026-08-26 — Provenance Control Hub

- **GO** service actif exécuté depuis `/opt/pincabos-release-center` sous Gunicorn.
- **GO** `app.py` charge directement `pincabos_control_hub_v27.py`.
- **GO** routes `/api/control-hub/...` et polling chat 4 s confirmés dans la source active.
- **GO** répertoire actif confirmé hors Git et fichiers non revendiqués par un paquet Debian.
- **GO** aucune source équivalente retrouvée dans `KarotsSugarpie/PinCabOS` `main`.
- **GO** SHA de référence du déploiement enregistrés.
- **GO** Python 3.13, Flask et Gunicorn présents; JWT et SDK LiveKit absents avant intégration.

### 2026-08-26 — Audit sécurité avant import GitHub

- **GO** liste candidate de source de premier niveau établie.
- **GO** exclusions permanentes : backups, bytecode, DB, `.env`, clés/certificats privés, logs, caches et données utilisateur.
- **GO** DB, avatars, cache VPS et clé worldmap confirmés sous `/var/lib/pincabos-release/`, hors arbre source à versionner.
- **GO** aucun marqueur de clé privée détecté.
- **GO** audit structurel Python : `app.secret_key` et SMTP password lus depuis l'environnement; tokens observés générés ou fournis par les requêtes.
- **GO** `gh` absent et `/opt/pincabos-release-center` toujours non-worktree Git.
- **GO** Release Center et LiveKit actifs; HTTP site et LiveKit = 200 après audit.

### 2026-08-26 — Audit publication V1.2

- **GO** Python : `HIGH=0`, `MEDIUM=7`; les `MEDIUM` correspondent à des comparaisons et au fallback non secret de `PINCABOS_BASE_URL`.
- **GO** JS/HTML : aucun pattern connu de token/credential détecté.
- **GO** les 14 `HIGH` JS/HTML sont des identifiants/messages de validation UI, pas des secrets opérationnels.
- **GO** `PINCABOS_TURNSTILE_SECRET` et `PINCABOS_SMTP_PASSWORD` sont lus depuis l’environnement sans fallback secret.
- **GO** aucun marqueur de clé privée.
- **GO** Release Center et LiveKit restent actifs; HTTP site et LiveKit = 200.
- **DÉCISION** source candidate approuvée pour préparation du snapshot et import GitHub canonique.

### 2026-08-26 — Snapshot source canonique V1

- **GO** whitelist exacte de 31 fichiers validée.
- **GO** aucun type interdit présent dans la whitelist.
- **GO** manifest SHA256 créé avec 31 entrées.
- **GO** archive contient exactement la whitelist.
- **GO** extraction temporaire validée : 31/31 fichiers `OK` contre le manifest.
- **GO** SHA256 archive : `d201baf4250ea2614b2cc11c40ce8707c1e63d35d3a2c2890ea6237ab2caa8d7`.
- **GO** aucun fichier runtime modifié, aucun service redémarré.
- **GO** Release Center et LiveKit actifs; HTTP site et LiveKit = 200 après snapshot.
- **PROCHAINE ÉTAPE** rapatrier l'archive et le manifest pour import GitHub canonique.

### 2026-08-26 — Provenance cabinet Chat / Backglass

- **GO** WebApp cabinet actif : `/opt/pincabos/web`, Waitress port 80.
- **GO** route canonique Chat Backglass : `/opt/pincabos/web/pincaboslink.py` → `GET /pincabos-link/chat-backglass` → `_backglass_html()`.
- **GO** route locale Backglass répond HTTP 200, `Content-Type: text/html`, `Cache-Control: no-store`.
- **GO** Chat texte cabinet existant : contexte compte/amis, polling GET chat 4 s, POST message, présence et contrôle Backglass.
- **GO** agent réel : `/usr/local/sbin/pincabos-chat-backglass-agent`, service actif/enabled, UID/GID 0.
- **GO** `/var/lib/pincabos-link` est `0700 root:root`; test `pinball` échoue par permission, même test root réussit.
- **GO** display helper : `/usr/local/sbin/pincabos-chat-backglass`, Chrome/Chromium sur route locale, positionnement écran configuré.
- **GO** DP-1 confirmé Backglass `1920x1080+3840+0`; HDMI-0 playfield et DP-2 FullDMD séparés.
- **GO** GitHub `main` contient déjà les cinq composants/units canoniques aux chemins correspondant au runtime.
- **À PROUVER** identité bit-à-bit via Git blob SHA `.237` ↔ GitHub avant modification.

---

### Politique de mise à jour

Après chaque étape :

1. Ajouter/mettre à jour les cases correspondantes.
2. Ajouter une note datée dans le journal si l'étape change l'état du projet.
3. Ne jamais cocher une étape uniquement parce qu'une configuration a été créée; une preuve fonctionnelle est requise.
4. Ne jamais ajouter de secret, token, mot de passe, cookie ou contenu utilisateur dans ce fichier.
5. Reprendre toujours à la première case pertinente non validée.