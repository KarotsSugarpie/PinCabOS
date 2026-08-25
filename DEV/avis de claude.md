# Avis de Claude — notes séparées sur le plan multijoueur PinCabOS

> **Statut : document d'information uniquement.**
>
> Ce fichier ne remplace pas, ne modifie pas et ne prévaut pas sur `DEV/PINCABOS_VPX_MULTIPLAYER_MASTER_REPLICA.md`.
> Le plan maître, ses règles non négociables, ses phases, ses GO/NOGO et ses décisions restent la référence officielle.
>
> Ce document conserve les objections et idées jugées intéressantes dans l'analyse de Claude reçue le 25 août 2026. Plusieurs affirmations techniques devront être démontrées par nos propres audits et POC avant d'être considérées comme vraies.

## 1. Pourquoi conserver cet avis

L'intérêt principal de l'analyse de Claude n'est pas de remplacer l'architecture PinCabOS, mais d'identifier des inconnues capables de rendre certaines phases impossibles ou très coûteuses.

La bonne utilisation de cet avis est donc :

- transformer les objections en **tests reproductibles**;
- faire remonter les inconnues critiques le plus tôt possible;
- documenter les scénarios de repli sans changer automatiquement la vision;
- conserver les règles PinCabOS tant qu'un GO/NOGO officiel ne justifie pas une décision différente.

---

## 2. Point le plus important : tester la réplication physique le plus tôt possible

Claude soulève une objection centrale : le plan demande éventuellement de capturer puis restaurer un état VPX complet — physique, objets dynamiques, script, timers, aléatoire et état ROM — tout en interdisant toute modification intrusive de VPX BGFX et VPinFE.

Cette objection mérite d'être traitée comme une **preuve de faisabilité prioritaire**.

### Test recommandé

Avant de consacrer beaucoup de travail au transport, au protocole, au TURN ou aux dépôts secondaires, produire un POC minimal qui répond à des questions simples :

1. Peut-on observer de manière externe et fiable la position et la vitesse d'une bille?
2. Peut-on observer l'état utile des flippers et objets dynamiques?
3. Peut-on reconstruire ou restaurer cet état sur une seconde instance sans modifier VPX BGFX?
4. Peut-on effectuer cette opération sans écrire dans la configuration VPX/VPinFE?
5. Peut-on répéter le test plusieurs fois avec le même résultat?

### Décision PinCabOS

Ce point **ne change pas le non-négociable actuel** : VPX BGFX et VPinFE restent intacts.

L'intérêt de la remarque de Claude est surtout de faire de cette capacité une inconnue à éliminer tôt. Si l'interface externe nécessaire n'existe réellement pas, il vaut mieux obtenir ce NOGO avant d'avoir construit tout le reste du moteur de réplication.

---

## 3. Tester immédiatement deux familles de tables

Claude recommande de ne pas limiter les premiers tests à une table Original sans ROM.

C'est pertinent.

Le premier banc d'essai devrait idéalement comporter :

- **une table Original sans ROM**, afin d'isoler VPX, la physique et le script;
- **une table avec ROM/PinMAME**, par exemple une table de référence connue, afin de mesurer immédiatement les effets de la ROM, des switches, lampes, solénoïdes, timings et échanges asynchrones.

### Pourquoi

Si le comportement d'une table Original peut être reproduit mais qu'une table à ROM diverge rapidement, cette différence devient une donnée d'architecture majeure.

Il serait inutile de découvrir cette limite seulement à la fin du projet.

### Critères à mesurer

Pour les deux familles de tables :

- même package et même SHA-256;
- mêmes entrées horodatées;
- même séquence de lancement;
- comparaison périodique des états observables;
- temps avant première divergence;
- nature exacte de la première divergence;
- répétabilité sur plusieurs exécutions.

---

## 4. Définir précisément le mot `tick`

Claude note que le plan utilise le terme `tick` sans lui donner encore une définition normative unique.

C'est un bon point à corriger **avant de figer un protocole réseau**.

Le futur protocole devra décider explicitement ce qu'est un tick PinCabOS Sync, par exemple :

- tick de physique VPX;
- tick logique propre à l'agent PinCabOS;
- compteur monotone de snapshot/delta;
- horloge dérivée du maître;
- ou autre définition démontrée par le POC.

Il faudra aussi définir :

- fréquence nominale;
- relation avec le temps monotone;
- comportement en cas de retard ou perte de paquet;
- comportement lors d'une pause de handoff;
- règle de comparaison des checksums;
- relation entre tick réseau, simulation VPX et événements PinMAME.

Aucun format de message ne devrait dépendre d'une notion de tick ambiguë.

---

## 5. Ajouter un budget de bande passante avant le protocole final

Le plan prévoit potentiellement des deltas fréquents comprenant billes, objets dynamiques, primitives animées, lampes, flashers, audio/événements et autres états.

Claude recommande de chiffrer ce trafic très tôt.

C'est pertinent.

### À mesurer durant le POC

Pour 2, 3 et 4 cabinets :

- octets moyens par delta;
- fréquence des deltas;
- fréquence des snapshots complets;
- débit moyen par cabinet;
- débit de pointe;
- overhead chiffrement/transport;
- pertes et retransmissions;
- CPU utilisé pour sérialisation, checksum et chiffrement;
- comportement avec 20, 50, 100 et 200 ms de RTT;
- comportement avec jitter et perte réalistes.

Le résultat doit permettre de définir un **budget réseau officiel** avant de choisir définitivement la représentation des objets et la fréquence d'envoi.

---

## 6. TURN : capacité, coût et scénario de relais

Claude rappelle qu'une connexion directe entre cabinets ne sera pas toujours possible, notamment selon le NAT ou le CGNAT.

Le plan prévoit déjà que le trafic vivant passe directement entre cabinets quand le réseau le permet. Il faut donc aussi documenter clairement le cas où ce n'est pas possible.

### Questions à ajouter à l'étude réseau

- Quel trafic peut devoir passer par TURN?
- Audio/Vidéo seulement, synchronisation VPX, ou les deux?
- Quel débit maximum par session à 4 joueurs?
- Quel coût mensuel à 10, 100 ou 1 000 sessions simultanées?
- Quelle limite impose le serveur TURN?
- Quel comportement si TURN devient indisponible?
- Le Lobby doit-il refuser le démarrage si aucun chemin réseau acceptable n'est obtenu?

Aucune décision n'est prise ici; ce sont des points à quantifier.

---

## 7. DOF et sorties physiques sur les cabinets répliques

C'est probablement l'un des meilleurs trous de sécurité signalés dans l'avis.

Si une réplique reçoit des états de lampes, solénoïdes, shaker, contacteurs ou autres sorties, il faut décider si elle est autorisée à les reproduire physiquement.

### Risques

Une donnée réseau erronée ou malveillante ne doit jamais pouvoir :

- maintenir un solénoïde activé trop longtemps;
- marteler une sortie à une fréquence dangereuse;
- déclencher une séquence incontrôlée;
- contourner les limites déjà prévues par le cabinet local.

### Garde-fous à prévoir si les sorties physiques sont un jour synchronisées

- allowlist stricte des sorties autorisées;
- durée maximale d'activation locale;
- fréquence maximale locale;
- rate limiting indépendant du maître;
- watchdog local;
- arrêt immédiat à la perte de session;
- aucune commande brute arbitraire reçue du réseau;
- possibilité de désactiver complètement les sorties physiques sur une réplique.

La sécurité finale doit rester sous l'autorité du cabinet local, jamais sous celle d'un paquet réseau.

---

## 8. Autorité Lobby versus autorité ROM/VPX

Claude signale un risque de double autorité sur l'ordre des joueurs.

Le plan maître dit que le Lobby orchestre la session et le changement de joueur, tandis que VPX/PinMAME possède lui aussi un état interne de joueur et de balle.

Ce point mérite une règle explicite.

### Question à résoudre

Qui constitue la vérité lorsqu'il y a désaccord entre :

- le joueur attendu par le Lobby;
- le joueur courant observé dans VPX/PinMAME;
- le cabinet qui possède actuellement le jeton de maître?

Une solution possible à tester serait que le Lobby orchestre les permissions et la correspondance `joueur ↔ cabinet`, mais qu'il ne force jamais un changement que l'état réel de la partie n'a pas confirmé.

Cette proposition reste à valider pendant les audits.

---

## 9. Le désaccord de Claude sur les plugins VPX

Claude recommande de distinguer :

- modification de VPX;
- utilisation d'un point d'extension/plugin officiel.

Il suggère qu'un plugin officiel pourrait être considéré comme une extension propre plutôt qu'une modification.

### Décision actuelle PinCabOS

**Cette suggestion ne modifie rien.**

Le plan maître actuellement accepté interdit l'injection d'un nouveau plugin dans VPX BGFX et exige que VPX BGFX et VPinFE restent dans leur état actuel, dans leur code comme dans leur fonctionnement.

La suggestion de Claude est simplement conservée ici comme **désaccord architectural documenté**.

Si les audits démontrent un NOGO absolu avec les interfaces externes permises, toute éventuelle réouverture de cette règle devra faire l'objet d'une décision humaine explicite et d'une modification séparée du plan maître. Elle ne doit jamais être déduite automatiquement de ce document.

---

## 10. Streaming vidéo : conserver uniquement comme scénario de repli théorique

Claude considère le streaming vidéo du playfield comme une solution beaucoup plus simple si la réplication locale devient impossible.

La vision PinCabOS actuelle exige cependant un rendu local de la table et exclut le streaming vidéo du playfield comme mécanisme principal de synchronisation.

### Décision actuelle

Aucun changement.

L'idée peut seulement être conservée comme scénario de comparaison ou de dernier recours en cas de NOGO définitif du moteur de réplication.

Elle ne fait pas partie de la V1 officielle tant que le plan maître n'en décide pas autrement.

---

## 11. Variante V1 simplifiée proposée par Claude

Claude propose une V1 beaucoup plus simple :

- Lobby, comptes, amis et vérification des packages;
- lancement coordonné;
- chaque joueur joue sa balle localement sur son cabinet;
- ScoreView et Chat A/V partagés;
- passage de main entre joueurs à la fin de la balle;
- pas de réplication physique continue du playfield sur les autres cabinets.

Cette variante ne réalise pas la vision complète des répliques chaudes, mais elle peut constituer un **plan de repli livrable** si la réplication physique obtient un NOGO.

Il est intéressant de la conserver sans l'adopter maintenant, car une partie importante de l'infrastructure — Lobby, identité, présence, table/hash, lancement, Chat A/V et handoff logique — resterait utile même si le moteur de réplication devait être reporté.

---

## 12. Licence et `remote-control`

Claude attire l'attention sur la licence du plugin `remote-control` et sur le risque de créer involontairement une implémentation dérivée si le protocole est copié directement depuis son code.

Ce point doit être vérifié juridiquement et techniquement avant toute réutilisation.

### Règle prudente proposée

- utiliser en priorité une documentation publique du protocole si elle existe;
- documenter la provenance de toute spécification réimplémentée;
- ne pas copier du code sans examen de licence;
- conserver les notices de licence nécessaires;
- faire valider toute dépendance GPL éventuelle avant de figer l'architecture de distribution.

Ce document ne constitue pas un avis juridique.

---

## 13. `clear` et les scripts CI

Claude recommande de ne pas mettre `clear` dans les scripts exécutés automatiquement en CI car cela n'apporte rien aux logs.

Cette remarque est compatible avec notre méthode de travail si on distingue :

- **commandes/scripts interactifs envoyés à l'utilisateur :** conserver `clear` en tête, selon la préférence de travail actuelle;
- **scripts persistants, services, CI/CD, cron et tests automatisés :** ne pas ajouter `clear` sauf raison particulière.

Il n'y a donc pas de conflit nécessaire entre les deux usages.

---

## 14. Ordre de priorité suggéré pour exploiter cet avis

Sans changer le plan maître, les remarques de Claude peuvent être transformées en sous-tests de Phase 1 / POC dans cet ordre :

1. **Preuve minimale lecture/écriture/restauration d'un état physique utile sans modifier VPX BGFX ni VPinFE.**
2. **Même test sur une table Original et une table avec ROM/PinMAME.**
3. **Mesure de divergence/déterminisme sur plusieurs exécutions.**
4. **Définition normative du `tick`.**
5. **Budget de bande passante et fréquence snapshot/delta.**
6. **Validation du modèle d'autorité Lobby ↔ maître ↔ état VPX/ROM.**
7. **Décision explicite sur DOF/sorties physiques des répliques et garde-fous locaux.**
8. **Mesure du besoin TURN et du coût du relais.**
9. **Vérification licences/API autour de `remote-control` et des interfaces étudiées.**
10. **Seulement après ces réponses : figer le protocole, le transport et les dépôts spécialisés.**

---

## 15. Conclusion

Les remarques de Claude les plus utiles sont celles qui permettent de **faire échouer tôt ce qui doit échouer**, plutôt que de découvrir un blocage après la construction du protocole et de l'infrastructure.

Les éléments à retenir en priorité sont :

- tester immédiatement la faisabilité de capture/restauration;
- inclure une table ROM très tôt;
- définir `tick` avant le protocole;
- chiffrer bande passante et TURN;
- régler l'autorité Lobby/ROM;
- protéger explicitement le matériel DOF des données réseau;
- conserver une V1 simplifiée comme plan de repli éventuel;
- traiter les affirmations de Claude comme des hypothèses à vérifier, pas comme des vérités acquises.

**Aucun de ces points ne modifie le plan maître existant.** Toute évolution du document de référence doit rester une décision séparée, explicite, testée et tracée.