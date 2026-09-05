# PinCabOS — Guide clé en main pour Yan : Claude for Open Source

**Destinataire : Yan — France**  
**Projet : PinCabOS**  
**Dépôt officiel :** https://github.com/PinCabOs/PinCabOS  
**Organisation GitHub :** https://github.com/PinCabOs  
**Programme visé :** Anthropic — Claude for Open Source  
**Dernière vérification : 5 septembre 2026**

---

# 1. Objectif

Ce document est uniquement destiné à la demande **Anthropic / Claude for Open Source** pour PinCabOS.

Yan utilise déjà Claude AI : il doit donc faire la demande avec **son propre compte Claude/Anthropic**, son vrai nom, son vrai courriel et son vrai profil GitHub.

Il ne faut pas utiliser la procédure OpenAI dans ce document.

Le programme officiel Claude for Open Source annonce actuellement **6 mois gratuits de Claude Max 20x** pour les candidats sélectionnés.

Lien officiel :

https://claude.com/contact-sales/claude-for-oss

---

# 2. Ce qu'Anthropic recherche

Anthropic indique que le programme vise notamment les profils suivants :

- mainteneurs de paquets utilisés par beaucoup d'autres projets ;
- contributeurs principaux de grands projets ou fondations open source ;
- contributeurs ayant fait beaucoup de PR fusionnées dans des dépôts qu'ils ne possèdent pas ;
- projets ayant beaucoup de contributeurs externes ;
- projets considérés comme infrastructure open source critique.

Les seuils publiés par Anthropic incluent notamment :

- 500 dépôts dépendants ou plus ;
- 100 paquets dépendants ou plus ;
- 200 000 téléchargements mensuels combinés ou plus ;
- 100 PR ou plus fusionnées dans des dépôts externes sur les 12 derniers mois ;
- 20 contributeurs externes uniques ou plus sur un dépôt ;
- ou un score OpenSSF criticality d'au moins 0,4.

**PinCabOS est encore jeune et ne doit surtout pas prétendre atteindre ces seuils si ce n'est pas vrai.**

Anthropic précise toutefois que les mainteneurs qui ne correspondent pas parfaitement à ces critères peuvent quand même déposer une demande s'ils maintiennent quelque chose d'important ou d'utile à leur écosystème.

C'est exactement l'angle recommandé pour PinCabOS.

---

# 3. Ce que Yan doit avoir sous la main avant de commencer

- [ ] être connecté au compte Claude qu'il utilise réellement ;
- [ ] utiliser l'adresse courriel liée à ce compte ;
- [ ] connaître son nom d'utilisateur GitHub ;
- [ ] avoir son profil GitHub public ;
- [ ] vérifier que le dépôt PinCabOS est public ;
- [ ] vérifier que `LICENSE` est présent ;
- [ ] vérifier que `THIRD_PARTY_NOTICES.md` est présent ;
- [ ] connaître son rôle réel dans PinCabOS ;
- [ ] garder ce document ouvert pour copier-coller les réponses.

Dépôt à fournir partout :

```text
https://github.com/PinCabOs/PinCabOS
```

---

# 4. Rôle de Yan

Yan doit utiliser la formulation correspondant réellement à son travail.

## Si Yan développe régulièrement PinCabOS

```text
Core maintainer and developer. I contribute to development, testing, validation and maintenance of PinCabOS, including real-world testing on physical virtual pinball cabinet hardware in France.
```

## Si Yan est surtout responsable des tests matériels en France

```text
Core contributor and hardware validation developer. I test PinCabOS on physical virtual pinball cabinet hardware in France and contribute to validation, regression testing, issue identification and development feedback.
```

Ne pas écrire `primary maintainer` si ce n'est pas réellement son rôle.

---

# 5. Description courte de PinCabOS

Si le formulaire demande une courte description du projet, copier :

```text
PinCabOS is an open-source Linux platform designed specifically for virtual pinball cabinets. It connects cabinet hardware, Visual Pinball X, VPinFE, displays, audio/SSF, physical controls, DOF devices, diagnostics, safe updates, backups and a browser-based management interface into one coherent and maintainable environment.
```

---

# 6. Description complète du projet

Si le formulaire permet une réponse plus longue, copier :

```text
PinCabOS is an open-source Linux-based platform designed specifically for virtual pinball cabinets.

Virtual pinball cabinets require many independent technologies to work together: Linux, GPUs, multiple displays, Visual Pinball X, frontend software, audio and surround sound feedback, USB controllers, physical buttons, analog plungers, accelerometers, force-feedback devices, addressable lighting, network storage, media libraries and table assets.

PinCabOS brings these components together into a coherent, reproducible and maintainable environment. The project includes a browser-based WebApp, hardware and display detection, audio/SSF configuration, input mapping, DOF hardware management, Smart Import/Export tools, diagnostics, backup and recovery systems, transactional updates with rollback, cabinet monitoring and integration with VPX and VPinFE.

The goal is to reduce the technical barrier to building and maintaining a virtual pinball cabinet while preserving compatibility with the existing virtual pinball ecosystem.
```

---

# 7. Réponse principale — Pourquoi PinCabOS devrait être accepté

C'est la réponse la plus importante du dossier.

Copier :

```text
PinCabOS is a young but highly active open-source Linux platform for virtual pinball cabinets. It solves a difficult integration problem across Linux, GPUs, multiple displays, audio/SSF, USB controls, force-feedback devices, lighting, Visual Pinball X and frontend software.

The project is developed and validated on real physical cabinets in Canada and France. It focuses strongly on safe configuration, diagnostics, backups, transactional updates and rollback because errors can affect expensive physical hardware.

We do not yet meet Anthropic's large adoption thresholds, and we do not want to overstate our current metrics. However, PinCabOS addresses a technically complex niche with very little integrated tooling, and it has the potential to become important infrastructure for Linux-based virtual pinball builders.

Claude support would directly increase the development capacity of a small distributed open-source team while keeping all final validation on real hardware in human hands.
```

---

# 8. Réponse — Comment Claude serait utilisé

Copier :

```text
Claude and Claude Code would be used as engineering tools for PinCabOS development: code review, debugging, regression analysis, installer validation, release workflows, documentation, log analysis, hardware compatibility work, WebApp development, multiplayer development and maintenance of safe backup/update/rollback procedures.

PinCabOS spans Linux system engineering, Python, web development, GPU/display configuration, audio, USB hardware and physical cabinet integration. Claude can significantly increase the capacity of a small open-source team while real-cabinet testing and final technical decisions remain performed by the maintainers.
```

---

# 9. Réponse — Pourquoi Claude est particulièrement utile à PinCabOS

Si le formulaire demande pourquoi Claude ou Claude Code est pertinent pour le projet, copier :

```text
PinCabOS has a very broad engineering surface for a small team. A single feature can involve Python, Bash, systemd, Linux permissions, web code, hardware detection, GPU/display configuration and real physical devices. Claude Code is particularly valuable for reviewing cross-component changes, tracing regressions, maintaining documentation and validating safer implementation paths before changes are tested on real cabinets.
```

---

# 10. Réponse — Impact attendu

Si le formulaire demande l'impact du programme, copier :

```text
Six months of Claude Max 20x would materially increase the amount of development, review and documentation work our small team can perform. It would help us spend less time on repetitive analysis and more time on architecture, physical hardware testing, community support and making PinCabOS easier to install and maintain for new virtual pinball builders.
```

---

# 11. Réponse — État actuel / maturité du projet

```text
PinCabOS is currently in active alpha development with frequent releases and continuous testing on real virtual pinball cabinets. The project is young, but development is very active and the system already covers installation, WebApp management, displays, audio/SSF, controls, DOF hardware, imports, diagnostics, updates, backups and recovery workflows.
```

---

# 12. Réponse — Équipe distribuée

Si le formulaire demande qui travaille sur le projet :

```text
PinCabOS is maintained by a small distributed team. Jean-Robert Letarte leads project direction, architecture, integration and real-cabinet validation in Canada. Yan contributes from France to development, testing, hardware validation, regression identification and development feedback. Additional work is contributed through GitHub pull requests and component-specific development.
```

Avant l'envoi, corriger ce texte si les rôles réels ont changé.

---

# 13. Procédure exacte pour Yan

## Étape 1 — Se connecter à Claude

Ouvrir :

https://claude.ai

Se connecter avec **le compte Claude que Yan utilise réellement**.

Il est préférable que l'adresse courriel utilisée dans la demande soit la même que celle de ce compte.

## Étape 2 — Ouvrir le programme officiel

Ouvrir dans le même navigateur :

https://claude.com/contact-sales/claude-for-oss

Vérifier que la page affiche bien :

**Claude for Open Source**

et l'offre de **6 months of Claude Max 20x**.

## Étape 3 — Commencer la candidature

Cliquer sur le bouton d'application de la page.

Le formulaire peut évoluer. Si le nom exact d'un champ diffère de ce guide, utiliser la réponse correspondant au sens du champ.

## Étape 4 — Identité

Utiliser uniquement les informations personnelles réelles de Yan :

- vrai prénom ;
- vrai nom ;
- vrai courriel ;
- vrai profil GitHub ;
- France comme pays si demandé.

## Étape 5 — Projet

Nom :

```text
PinCabOS
```

Repository URL :

```text
https://github.com/PinCabOs/PinCabOS
```

Project type :

```text
Open-source Linux platform / operating and management environment for virtual pinball cabinets
```

## Étape 6 — Rôle

Utiliser une des formulations de la section 4 selon le rôle réel de Yan.

## Étape 7 — Critères d'admissibilité

Si le formulaire demande lequel des grands critères Anthropic est atteint et qu'aucun n'est réellement atteint, **ne rien inventer**.

Choisir une option de type `Other`, `None of the above`, `Additional context` ou équivalent si elle existe, puis expliquer que PinCabOS est un projet jeune mais techniquement important pour son écosystème.

Utiliser la réponse de la section 7.

## Étape 8 — Usage de Claude

Utiliser la réponse de la section 8.

## Étape 9 — Informations supplémentaires

Si un champ libre apparaît, copier :

```text
PinCabOS is intentionally conservative around physical hardware. Important changes follow a backup -> targeted change -> validation -> log review -> real-hardware test -> rollback-capable workflow. Claude would help us strengthen this engineering process and improve maintainability without replacing human validation. The project is open source and tested on real cabinets in both Canada and France.
```

## Étape 10 — Vérification avant Submit

- [ ] le compte Claude connecté est bien celui de Yan ;
- [ ] le courriel est correct ;
- [ ] le profil GitHub est réel et public ;
- [ ] le dépôt est exactement `https://github.com/PinCabOs/PinCabOS` ;
- [ ] Yan n'a inventé aucune statistique ;
- [ ] le rôle indiqué correspond à son travail réel ;
- [ ] PinCabOS est présenté comme projet open source jeune mais très actif ;
- [ ] l'utilisation de Claude est clairement liée au développement open source ;
- [ ] une copie des réponses est conservée.

## Étape 11 — Envoyer

Cliquer sur Submit une seule fois.

Faire une capture ou conserver la confirmation affichée après l'envoi.

Noter la date de dépôt.

---

# 14. Si Yan possède déjà Claude Pro ou Max

Le programme Claude for Open Source annonce actuellement **6 mois de Claude Max 20x offerts** aux candidats sélectionnés.

Anthropic indique qu'à la fin de la période gratuite :

- si le compte possédait auparavant un abonnement payant, cet abonnement reprend à son plan et tarif antérieurs sauf annulation ;
- sinon le compte revient au plan gratuit.

Yan n'a donc pas besoin de créer un second compte Claude uniquement pour cette demande.

---

# 15. Ce qu'il ne faut surtout pas écrire

Ne pas écrire :

- que PinCabOS possède 200 000 téléchargements mensuels si ce n'est pas vrai ;
- que PinCabOS possède 500 dépôts dépendants ;
- que PinCabOS possède 20 contributeurs externes si ce n'est pas documenté ;
- que le projet a un score OpenSSF >= 0,4 sans l'avoir vérifié ;
- que Yan est le créateur principal si ce n'est pas son rôle ;
- que Claude remplacera les développeurs ;
- que l'avantage est un paiement en argent comptant.

Le dossier doit rester techniquement solide et totalement vérifiable.

---

# 16. Arguments PinCabOS à garder en tête

Les meilleurs arguments ne sont pas encore les statistiques de popularité du dépôt.

Les meilleurs arguments sont :

1. projet open source réel et public ;
2. système Linux spécialisé pour une niche matérielle complexe ;
3. intégration de nombreuses couches techniques dans un seul environnement ;
4. développement rapide et fréquent ;
5. tests sur de vrais cabinets ;
6. équipe distribuée Canada / France ;
7. procédures de backup, validation et rollback ;
8. réduction de la barrière technique pour les utilisateurs ;
9. Claude et Claude Code peuvent réellement multiplier la capacité d'une petite équipe ;
10. les décisions finales et les tests physiques restent faits par les mainteneurs.

---

# 17. Liens utiles pour Yan

## Claude AI

https://claude.ai

## Claude for Open Source — formulaire officiel

https://claude.com/contact-sales/claude-for-oss

## Dépôt PinCabOS

https://github.com/PinCabOs/PinCabOS

## Organisation PinCabOS

https://github.com/PinCabOs

## Licence PinCabOS

https://github.com/PinCabOs/PinCabOS/blob/main/LICENSE

## Avis sur les composants tiers

https://github.com/PinCabOs/PinCabOS/blob/main/THIRD_PARTY_NOTICES.md

---

# 18. Résumé ultra-court pour Yan

1. Connecte-toi à ton compte Claude habituel.
2. Va sur https://claude.com/contact-sales/claude-for-oss
3. Utilise ton vrai profil GitHub et ton vrai rôle dans PinCabOS.
4. Projet : `PinCabOS`.
5. Repo : `https://github.com/PinCabOs/PinCabOS`.
6. Ne prétends pas atteindre les grands seuils statistiques Anthropic.
7. Explique que PinCabOS est jeune, très actif, techniquement complexe et testé sur du vrai matériel.
8. Explique que Claude/Claude Code servira au code review, debugging, régressions, releases, documentation et diagnostics.
9. Relis tout.
10. Submit et garde la confirmation.

---

**Document préparé pour la candidature Anthropic Claude for Open Source de PinCabOS.**
