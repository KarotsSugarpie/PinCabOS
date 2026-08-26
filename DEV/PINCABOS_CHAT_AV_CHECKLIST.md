# PinCabOS Chat Audio/Vidéo — checklist de déploiement

> Document de référence vivant pour le Chat Audio/Vidéo PinCabOS. À mettre à jour après chaque étape réellement validée. Aucun `[x]` sans preuve technique reproductible.

## Référence de reprise

- **Safeword :** `PINFORGE-SAFE-CHAT-AV-28`
- **Dépôt :** `KarotsSugarpie/PinCabOS`
- **Fichier :** `DEV/PINCABOS_CHAT_AV_CHECKLIST.md`
- **Branche :** `main`
- **Dernière mise à jour :** 2026-08-26
- **État global :** moteur SFU central et signaling HTTPS publics validés; intégration applicative Control Hub à faire; média WAN réel pas encore prouvé depuis un réseau externe.

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
- [x] Module actif identifié : `/opt/pincabos-release-center/pincabos_control_hub_v27.py`.
- [x] Frontend actif identifié : `/opt/pincabos-release-center/pincabos-control-hub-v27.js`.
- [x] Chat texte actuel identifié : polling GET/POST périodique, sans moteur WebRTC/SFU existant avant ce chantier.
- [ ] Retrouver/versionner la source serveur pincabos.cc dans GitHub sans créer de doublon parallèle.
- [ ] Comparer les SHA du code déployé avec la future source GitHub canonique.
- [ ] Documenter la route/app d'intégration A/V exacte avant modification.

> **Écart actuel GitHub :** `pincabos_control_hub_v27.py` n'a pas été retrouvé dans `main` lors de la recherche GitHub du 2026-08-26. Ne pas inventer un autre composant; auditer et réconcilier la source déployée avant l'intégration A/V.

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

- [ ] Auditer l'environnement Python actuel du Release Center et ses dépendances avant toute installation.
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

- [ ] Ajouter le client LiveKit à la source frontend canonique du Control Hub.
- [ ] Aucun nouveau frontend parallèle ou overlay ajouté par-dessus le Control Hub.
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

1. **Auditer la source canonique du Control Hub déployé et la réconcilier avec GitHub.**
2. Auditer les dépendances Python actives du Release Center.
3. Ajouter ensuite seulement l'API serveur de génération de jetons LiveKit.
4. Faire un premier test navigateur caméra/micro.
5. Prouver le média WAN avec deux réseaux distincts.

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

---

### Politique de mise à jour

Après chaque étape :

1. Ajouter/mettre à jour les cases correspondantes.
2. Ajouter une note datée dans le journal si l'étape change l'état du projet.
3. Ne jamais cocher une étape uniquement parce qu'une configuration a été créée; une preuve fonctionnelle est requise.
4. Ne jamais ajouter de secret, token, mot de passe, cookie ou contenu utilisateur dans ce fichier.
5. Reprendre toujours à la première case pertinente non validée.