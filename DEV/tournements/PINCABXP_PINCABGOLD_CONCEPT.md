# PinCabXP et PinCabGold

## Concept fonctionnel, expérience joueur, architecture technique et préparation réglementaire

- **Projet :** PinCabOS / PinCabOS.cc
- **Statut :** document de conception — aucune récompense de valeur ne doit être activée sur la seule base de ce document
- **Territoires étudiés :** Canada, Québec, France et cadre européen applicable aux données
- **Dernière vérification des sources :** 4 septembre 2026

> Ce document décrit une architecture prudente et des contrôles à prévoir. Il ne constitue pas un avis juridique, fiscal ou comptable. Avant d'activer des cartes-cadeaux, des frais de participation ou une récompense ayant une valeur réelle, PinCabOS doit obtenir une validation écrite adaptée aux pays visés et l'accord du processeur de paiement.

---

## 1. Résumé exécutif

PinCabOS peut créer un système de progression motivant sans transformer le multijoueur en jeu d'argent. La solution recommandée repose sur deux unités complètement séparées :

- **PinCabXP** mesure la performance compétitive. Il détermine les niveaux, classements, badges et positions de départ dans les tournois. Il n'a aucune valeur monétaire.
- **PinCabGold** récompense la participation gratuite et vérifiée. Il peut éventuellement être échangé dans une boutique régionale contre une récompense déterminée, sous réserve des validations juridiques, fiscales et contractuelles requises.

La séparation n'est pas seulement visuelle. Elle doit exister dans les règles, la base de données, les API, les journaux comptables et l'expérience utilisateur.

### Décision de principe

| Fonction | Décision proposée |
|---|---|
| PinCabXP fondé sur les résultats | **GO** |
| Classements, saisons, badges et éliminations | **GO** |
| PinCabGold gratuit, non achetable et non transférable | **GO en environnement de test** |
| Récompenses purement numériques sans valeur de revente | **GO après règles publiées** |
| Cartes-cadeaux contre PinCabGold | **GO conditionnel après validation territoriale** |
| Achat direct de PinCabGold | **NOGO** |
| Bonus de Gold réservé aux abonnés payants | **NOGO** |
| Frais d'entrée servant à financer les prix | **NOGO sans opérateur et avis juridique spécialisés** |
| Conversion du Gold en argent | **NOGO** |
| Transfert ou revente de Gold entre joueurs | **NOGO** |

Le lancement recommandé est progressif : XP d'abord, Gold numérique ensuite, puis un pilote limité de cartes-cadeaux dans un seul territoire après validation.

---

## 2. Objectif du système

Le système vise à :

1. donner une progression visible aux joueurs;
2. encourager des matchs terminés et vérifiables;
3. valoriser la victoire sans punir excessivement la défaite;
4. soutenir des saisons et des tournois à élimination;
5. récompenser une participation saine sans créer de mise;
6. éviter le *pay-to-win* et l'achat d'un avantage compétitif;
7. protéger PinCabOS contre la fraude, le farming et les doubles paiements;
8. permettre un déploiement différent selon le pays du joueur.

Le système ne doit jamais être présenté comme une manière de « gagner de l'argent en jouant ». PinCabGold est une récompense promotionnelle contrôlée, pas un placement, un salaire, une cryptomonnaie ni une monnaie convertible.

---

## 3. Les deux unités

### 3.1 PinCabXP : la réputation compétitive

PinCabXP répond à la question : **quelle est la progression sportive du joueur?**

Caractéristiques obligatoires :

- gagné principalement selon les résultats;
- visible dans le profil, les classements et les tableaux de tournoi;
- utilisable pour le niveau, le seeding et les badges;
- impossible à acheter, vendre, donner ou échanger;
- aucune conversion en Gold, argent, carte-cadeau ou marchandise;
- remise à zéro saisonnière possible, avec conservation d'un historique;
- correction possible lors d'une fraude ou d'un résultat annulé.

Exemples d'utilisation :

- niveau Débutant, Challenger, Pro, Maître ou Grand Champion;
- classement global et classement par table;
- qualification pour une division;
- attribution du seeding dans un bracket;
- badges « série de cinq victoires », « finaliste » ou « champion de saison »;
- statistiques personnelles et historiques.

### 3.2 PinCabGold : la fidélisation

PinCabGold répond à la question : **quelle participation admissible le joueur a-t-il accumulée?**

Caractéristiques obligatoires :

- gagné gratuitement par des activités clairement définies;
- quantité déterministe, jamais attribuée par tirage ou multiplicateur aléatoire;
- même montant de base pour les joueurs qui terminent le même type de match;
- plafonné par jour ou par semaine;
- impossible à acheter;
- impossible à transférer entre comptes;
- impossible à convertir en argent;
- utilisable uniquement par le titulaire du compte dans la boutique PinCabOS;
- solde et historique consultables;
- aucune expiration par défaut;
- aucune valeur garantie en dehors du programme.

Lorsque PinCabGold peut être échangé contre une carte-cadeau, il devient une **unité ayant une valeur d'échange dans un programme de récompenses**. PinCabOS doit alors le gérer comme une obligation réelle envers l'utilisateur, et non comme un simple compteur décoratif.

---

## 4. Pourquoi ne pas donner plus de Gold au gagnant?

Le concept initial prévoyait que tous les joueurs gagnent du Gold, mais que le gagnant en reçoive davantage. Cette mécanique est motivante, mais elle rapproche la valeur économique du résultat d'une partie où la bille conserve une part d'imprévisibilité.

La version recommandée déplace l'avantage du gagnant vers PinCabXP :

- le gagnant reçoit beaucoup plus de XP;
- le perdant reçoit un peu de XP pour sa participation;
- les deux joueurs reçoivent le même Gold de base si le match est terminé et admissible;
- les récompenses liées au podium sont des titres et badges sans valeur monétaire.

Cette séparation conserve le plaisir compétitif tout en réduisant le lien entre le hasard potentiel de la partie et la récompense échangeable.

---

## 5. Exemple concret : match multijoueur

Julie et Marc jouent un match homologué sur la même table.

### Conditions d'admissibilité

- les deux comptes sont vérifiés;
- les deux cabinets sont liés à PinCabOS.cc;
- la même version de table et les mêmes paramètres de compétition sont utilisés;
- le match est lancé par le service multijoueur;
- le résultat est signé et reçu par le serveur;
- la durée minimale et les contrôles anti-abus sont respectés;
- le match se trouve dans le quota hebdomadaire donnant droit au Gold.

### Résultat proposé

| Joueur | Résultat | PinCabXP | PinCabGold |
|---|---:|---:|---:|
| Julie | Victoire | 100 XP | 10 Gold |
| Marc | Défaite | 30 XP | 10 Gold |

Julie progresse plus rapidement dans le classement. Marc ne repart pas les mains vides : il progresse légèrement et sa participation admissible est reconnue.

Si Julie et Marc rejouent vingt fois dans la même soirée, les XP peuvent continuer d'être calculés selon les règles sportives, mais le Gold cesse d'être attribué lorsque le plafond est atteint.

---

## 6. Exemple concret : plafond et prévention du farming

Configuration illustrative, à recalibrer après une simulation économique :

- 10 Gold par match admissible terminé;
- maximum de 10 matchs récompensés par semaine;
- maximum hebdomadaire : 100 Gold;
- au-delà du plafond : XP et statistiques seulement;
- répétitions excessives contre le même adversaire : Gold suspendu ou soumis à révision;
- aucun Gold pour un abandon rapide, un résultat incomplet ou un match non signé.

### Exemple

Sophie termine douze matchs admissibles pendant la semaine :

- ses dix premiers matchs produisent 100 Gold;
- les matchs 11 et 12 produisent des XP et des statistiques, mais aucun Gold;
- son solde de Gold n'est jamais réduit parce qu'elle a perdu;
- elle ne peut pas payer pour relever son plafond.

Le plafond protège le budget et réduit la création de faux matchs sans empêcher les joueurs de continuer à jouer pour leur classement.

---

## 7. Exemple concret : tournoi à élimination

Un tournoi gratuit de seize joueurs utilise un bracket à élimination simple.

### Récompenses compétitives

| Position | PinCabXP illustratif | Récompense de prestige |
|---|---:|---|
| Champion | 1 000 XP | Badge Champion de saison |
| Finaliste | 600 XP | Badge Finaliste |
| Demi-finalistes | 350 XP | Badge Top 4 |
| Autres joueurs | XP des matchs | Badge Participant |

### PinCabGold

Chaque match admissible terminé accorde le même Gold de participation aux deux joueurs, dans la limite du plafond hebdomadaire. Le champion ne reçoit pas une grosse quantité additionnelle de Gold en raison de sa victoire.

Cette structure distingue :

- la reconnaissance du mérite, portée par XP;
- la récompense de fidélité, portée par Gold;
- le prix de prestige, sans valeur de revente;
- la boutique, qui fonctionne indépendamment du podium.

---

## 8. Exemple concret : boutique de récompenses

Le catalogue doit être régional. Les cartes disponibles au Canada ne sont pas automatiquement offertes en France, et inversement.

Exemple illustratif :

| SKU | Région | Récompense | Coût |
|---|---|---|---:|
| `CA-GIFT-010` | Canada | Carte-cadeau numérique de 10 $ CA | 2 000 Gold |
| `FR-GIFT-005` | France | Carte-cadeau numérique de 5 € | 2 000 Gold |
| `GLOBAL-BADGE-001` | Régions admissibles | Badge cosmétique exclusif | 300 Gold |

Les valeurs ci-dessus ne sont pas définitives. Chaque SKU doit être tarifé selon son coût réel, le budget du programme, les taxes et les conditions du fournisseur.

### Déroulement d'un échange

1. Le joueur ouvre la boutique correspondant à son territoire vérifié.
2. Le serveur vérifie l'âge, le territoire, le solde, le stock et les indicateurs de fraude.
3. Le joueur confirme l'échange et accepte la version courante des conditions.
4. Une réservation atomique retire le Gold une seule fois.
5. La carte est commandée auprès du fournisseur autorisé.
6. Le code est livré dans un coffre sécurisé ou par un canal approuvé.
7. La commande passe à l'état `delivered` seulement après confirmation technique.
8. En cas d'échec permanent, une écriture compensatoire recrédite le Gold.

Le Gold ne doit jamais être déduit par une simple modification du champ `balance`. Chaque mouvement doit être une écriture immuable et auditable.

---

## 9. Ce qui peut être payant sur PinCabOS.cc

PinCabOS peut monétiser le **service hébergé** sans vendre un avantage économique dans la compétition.

Fonctions potentiellement incluses dans une offre payante :

- création de ligues privées;
- outils avancés pour les organisateurs;
- tableaux personnalisés;
- statistiques et historique étendus;
- export des résultats;
- thèmes visuels et éléments cosmétiques;
- capacité accrue pour les événements privés;
- accompagnement administratif d'un événement.

L'offre payante ne doit pas :

- donner plus de Gold;
- augmenter le plafond de Gold;
- permettre d'acheter du Gold;
- réserver les matchs générateurs de Gold aux abonnés;
- améliorer les résultats, le seeding ou les multiplicateurs XP;
- donner davantage de chances d'obtenir une carte-cadeau.

Pour garder le lien propre, les activités génératrices de Gold doivent être accessibles gratuitement selon des conditions équivalentes.

---

## 10. Architecture technique recommandée

### 10.1 Composants

1. **Identity Service** — compte, âge, territoire, consentements et cabinet lié.
2. **Match Service** — création, état, joueurs, table, version, règles et résultat signé.
3. **Tournament Service** — brackets, seeding, manches, délais et arbitrage.
4. **XP Ledger** — écritures de progression compétitive.
5. **Gold Ledger** — écritures de récompense et d'échange.
6. **Eligibility Engine** — règles territoriales, quotas et admissibilité.
7. **Fraud Engine** — détection, suspension et révision.
8. **Reward Catalog** — SKU, région, stock, coût en Gold et fournisseur.
9. **Redemption Service** — réservation, commande, livraison et remboursement.
10. **Compliance Console** — règles publiées, versions acceptées, audits et export.

### 10.2 Séparation des registres

Les tables XP et Gold ne doivent pas partager une balance générique.

Exemple conceptuel :

```text
xp_ledger
  id, user_id, season_id, match_id, reason, delta, created_at

gold_ledger
  id, user_id, match_id, redemption_id, reason, delta, region, created_at

reward_redemptions
  id, user_id, sku, gold_cost, region, status, provider_ref, created_at
```

Contraintes importantes :

- clé d'idempotence unique par match et par type de récompense;
- aucune balance négative;
- aucune suppression d'écriture;
- corrections par écriture compensatoire;
- transaction atomique pour réserver le Gold et créer la commande;
- accès administrateur journalisé;
- secrets du fournisseur uniquement dans un coffre, jamais dans GitHub;
- calcul de balance reproductible depuis le registre.

### 10.3 Exemple d'événement serveur

```json
{
  "event": "match.settled",
  "match_id": "m_2026_000184",
  "ruleset": "ranked-v1",
  "territory": "CA-QC",
  "players": [
    {
      "user_id": "u_1042",
      "result": "win",
      "xp_delta": 100,
      "gold_delta": 10
    },
    {
      "user_id": "u_2088",
      "result": "loss",
      "xp_delta": 30,
      "gold_delta": 10
    }
  ],
  "gold_policy": "participation-weekly-cap-v1",
  "server_verified": true
}
```

Dans cet exemple, le résultat influence XP, mais pas le Gold de base.

---

## 11. Intégrité et anti-fraude

Les cartes-cadeaux créent une motivation financière à simuler des parties. La sécurité doit être prévue avant la boutique.

Contrôles recommandés :

- compte confirmé et cabinet lié;
- âge et territoire vérifiés avant le premier échange;
- identifiant unique de match généré par le serveur;
- nonce et horodatage empêchant la réutilisation d'un résultat;
- signature des événements transmis par les agents PinCabOS;
- validation croisée entre capitaine, autres cabinets et serveur;
- version exacte de la table, du ruleset et du module multijoueur;
- durée minimale cohérente;
- impossibilité d'obtenir du Gold en mode hors ligne;
- plafond par compte, cabinet, adversaire et période;
- détection de scores ou durées anormales;
- limitation des matchs répétés entre les mêmes comptes;
- délai de sécurité avant livraison des récompenses à risque;
- révision manuelle des échanges importants;
- droit d'appel documenté;
- journal d'administration immuable.

Il faut éviter une empreinte matérielle intrusive. Le cabinet lié, les événements signés et les indicateurs nécessaires à la fraude doivent être privilégiés. Toute donnée collectée doit avoir une finalité documentée et une durée de conservation définie.

---

## 12. Canada — cadre de préparation

### 12.1 Jeux, hasard et contrepartie

L'article 206 du Code criminel canadien encadre notamment l'attribution de biens par un jeu de chance ou un jeu mêlant chance et habileté lorsqu'un participant paie de l'argent ou une autre contrepartie de valeur.

Le pinball comporte une compétence réelle, mais aussi des rebonds et événements physiques partiellement imprévisibles. PinCabOS ne doit donc pas présumer qu'il sera toujours considéré comme un jeu de pure habileté.

Conséquence de conception :

- aucune mise;
- aucune perte de Gold;
- aucun achat de tentatives génératrices de Gold;
- aucune cagnotte alimentée par les joueurs;
- aucune carte-cadeau dépendant directement du podium;
- participation gratuite équivalente pour gagner du Gold.

Source : [Code criminel, article 206 — Justice Canada](https://laws-lois.justice.gc.ca/eng/acts/c-46/section-206.html).

### 12.2 Concours promotionnels

Lorsqu'une opération fait la promotion d'une entreprise et attribue un avantage selon le hasard, l'habileté ou une combinaison des deux, les règles de la Loi sur la concurrence peuvent imposer la divulgation claire des renseignements importants : nombre et valeur des prix, répartition régionale, éléments influençant les chances, dates et méthode de sélection.

Même si PinCabGold est conçu comme fidélisation, toute campagne spéciale avec tirage, bonus aléatoire ou nombre limité de gagnants doit recevoir un règlement distinct.

Source : [Promotional Contests — Competition Bureau Canada](https://competition-bureau.canada.ca/en/promotional-contests-enforcement-guidelines).

### 12.3 Vie privée au Canada

Les comptes, résultats, adresses IP, identifiants de cabinet, historiques de récompenses et signaux antifraude peuvent être des renseignements personnels.

À prévoir :

- finalité précise pour chaque champ;
- collecte limitée au nécessaire;
- consentement et transparence;
- mesures de sécurité adaptées;
- politique de conservation et destruction;
- procédure d'accès et de correction;
- contrats avec les fournisseurs de cartes et d'hébergement;
- registre des communications à des tiers.

Sources : [principes de la LPRPDE](https://www.priv.gc.ca/fr/sujets-lies-a-la-protection-de-la-vie-privee/lois-sur-la-protection-des-renseignements-personnels-au-canada/la-loi-sur-la-protection-des-renseignements-personnels-et-les-documents-electroniques-lprpde/p_principle/) et [LPRPDE — Commissariat à la protection de la vie privée du Canada](https://www.priv.gc.ca/fr/sujets-lies-a-la-protection-de-la-vie-privee/lois-sur-la-protection-des-renseignements-personnels-au-canada/la-loi-sur-la-protection-des-renseignements-personnels-et-les-documents-electroniques-lprpde/).

---

## 13. Québec — exigences additionnelles

### 13.1 Programme de fidélisation

La Loi sur la protection du consommateur définit un programme de fidélisation comme un programme où le consommateur reçoit des unités d'échange permettant d'obtenir gratuitement ou à prix réduit des biens ou services. PinCabGold peut entrer dans cette logique dès qu'il possède une utilité dans une boutique de récompenses.

Avant l'adhésion, les conditions doivent notamment expliquer par écrit :

- comment le Gold est obtenu;
- comment il est échangé;
- son facteur de conversion, s'il existe;
- les limites par période;
- les motifs de suspension ou d'annulation;
- le traitement d'un échange échoué;
- les règles d'inactivité ou d'expiration, s'il y en a.

Sources : [Loi sur la protection du consommateur, articles 187.6 et suivants](https://www.legisquebec.gouv.qc.ca/fr/document/lc/p-40.1) et [renseignements préalables — Office de la protection du consommateur](https://www.opc.gouv.qc.ca/consommateur/bien-service/carte-prepayee/recompenses/entente/renseignements-prealables/).

### 13.2 Expiration et modification

Le choix le plus simple pour PinCabOS est : **aucune expiration du Gold pendant le projet pilote**.

Au Québec, les unités ne peuvent généralement pas expirer à une date fixe ou seulement parce qu'une période s'est écoulée. Une expiration liée à l'inactivité est possible dans certaines conditions, notamment avec une période d'au moins un an, une clause prévue et un avis conforme.

Les règles encadrent également la modification d'un élément essentiel. Il ne faut pas réduire rétroactivement le solde déjà gagné ni dévaluer arbitrairement le facteur de conversion des unités déjà reçues.

Sources : [expiration des unités — OPC](https://www.opc.gouv.qc.ca/consommateur/bien-service/carte-prepayee/recompenses/expiration/) et [modification d'une entente — OPC](https://www.opc.gouv.qc.ca/consommateur/bien-service/carte-prepayee/recompenses/entente/duree-indeterminee/).

### 13.3 Protection des renseignements personnels

PinCabOS doit désigner la personne responsable de la protection des renseignements personnels et documenter la nécessité de chaque donnée. La Commission d'accès à l'information rappelle qu'une entreprise doit déterminer ses objectifs et ne recueillir que les renseignements nécessaires.

Source : [collecte de renseignements personnels — Commission d'accès à l'information du Québec](https://www.cai.gouv.qc.ca/protection-renseignements-personnels/information-entreprises-privees/collecte-renseignements-personnels_entreprises).

### 13.4 Langue et documents

Pour le lancement québécois, les conditions d'utilisation, règles du programme, politique de récompenses et écrans transactionnels doivent être disponibles en français. Une version anglaise peut être ajoutée, mais la version française ne doit pas être secondaire ou incomplète.

Une validation juridique spécifique est requise avant de choisir quelle version linguistique prévaut et comment recueillir l'acceptation des documents.

---

## 14. France — cadre de préparation

### 14.1 Définition large du jeu d'argent et de hasard

L'article L320-1 du Code de la sécurité intérieure vise les opérations offertes au public qui réunissent :

1. une espérance de gain;
2. un sacrifice financier exigé du participant;
3. une part de hasard, même partielle.

Le texte précise que l'interdiction peut couvrir des jeux reposant sur le savoir-faire des joueurs. Il serait donc particulièrement risqué d'offrir en France des parties payantes donnant accès à des cartes-cadeaux, même sous la forme intermédiaire de Gold.

Source : [Code de la sécurité intérieure, article L320-1 — Légifrance](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000039182525).

La liste des jeux d'argent en ligne légalement autorisés en France est limitée. PinCabOS ne doit pas se présenter comme un opérateur de jeu d'argent ni supposer qu'une compétition de pinball payante entre dans une catégorie autorisée.

Source : [offre de jeu légale et illégale — Autorité nationale des jeux](https://anj.fr/foire-aux-questions/offre-de-jeu-legale-et-illegale/quels-sont-les-jeux-dargent-et-paris-sportifs).

### 14.2 Conséquence pour PinCabGold en France

Le modèle France doit retirer clairement le sacrifice financier :

- Gold gagné par un parcours gratuit;
- aucun achat de Gold;
- aucune entrée payante nécessaire pour gagner du Gold;
- aucune amélioration du rendement Gold pour les abonnés;
- aucune perte ou mise de Gold;
- boutique séparée des résultats du tournoi;
- Gold de participation déterministe et plafonné;
- victoire récompensée principalement par XP et prestige.

Si une opération promotionnelle particulière utilise un élément aléatoire, elle doit être analysée séparément au regard du droit de la consommation. La DGCCRF indique notamment qu'un achat éventuellement associé à une loterie publicitaire doit porter sur le produit ou service, et non sur l'accès au jeu publicitaire.

Source : [loteries publicitaires — DGCCRF](https://www.economie.gouv.fr/dgccrf/les-fiches-pratiques/loterie-des-pratiques-commerciales-reglementees).

### 14.3 Mineurs

Pour un premier pilote avec cartes-cadeaux, la règle opérationnelle recommandée est de limiter le programme Gold échangeable aux comptes de **18 ans et plus**. Les comptes plus jeunes peuvent utiliser XP, les classements adaptés et les récompenses purement cosmétiques.

Cette mesure simplifie la protection des mineurs, mais ne remplace pas une analyse juridique ni un mécanisme raisonnable de vérification de l'âge.

### 14.4 Protection des données en France et dans l'Union européenne

Le RGPD s'applique aux traitements concernant les utilisateurs de l'Union européenne. Les données de matchs et d'antifraude doivent respecter notamment la limitation des finalités, la minimisation, l'exactitude, la sécurité et la limitation de conservation.

À prévoir :

- base juridique documentée pour chaque traitement;
- information claire au moment de la collecte;
- export, rectification et suppression lorsque applicables;
- durée distincte pour comptes, matchs, litiges et journaux de sécurité;
- analyse des transferts internationaux;
- contrats de sous-traitance;
- protection dès la conception;
- intervention humaine pour les sanctions importantes fondées sur un score antifraude.

Source : [Règlement général sur la protection des données — EUR-Lex](https://eur-lex.europa.eu/eli/reg/2016/679/oj).

---

## 15. Régionalisation obligatoire

Le lieu du serveur ne détermine pas à lui seul le droit applicable. PinCabOS doit tenir compte au minimum :

- du pays et de la province ou région de résidence;
- du pays depuis lequel le service est offert;
- de l'entité qui exploite le programme;
- du fournisseur de paiement;
- du fournisseur de cartes-cadeaux;
- de la monnaie de facturation;
- du lieu de traitement des données;
- des territoires ciblés par la publicité.

### Profil territorial

Le compte devrait contenir un `legal_region` vérifié au moment du premier échange :

```text
CA-QC  Canada / Québec
CA-XX  Canada / autre province admissible
FR     France métropolitaine et territoires explicitement admis
EU-XX  Autre État de l'Union européenne, après ouverture officielle
BLOCKED Territoire non pris en charge
```

L'adresse IP peut signaler une incohérence, mais elle ne doit pas être l'unique preuve de résidence. Un changement de territoire doit déclencher une révision avant l'accès à un autre catalogue.

### Catalogue régional

- chaque SKU est limité à une ou plusieurs régions;
- chaque région possède sa devise, son fournisseur et son budget;
- aucune promesse de disponibilité mondiale;
- aucune substitution non prévue;
- conditions fiscales et commerciales vérifiées par région;
- aucune carte dont les conditions interdisent les programmes de récompenses.

---

## 16. Processeurs de paiement et fournisseurs

Une activité légalement structurée peut tout de même être refusée par un processeur. Stripe classe notamment comme activités restreintes certains jeux d'habileté avec prix monétaire ou matériel, les frais d'entrée promettant un prix, ainsi que certaines activités liées aux crédits stockés et monnaies de jeu.

Source : [activités interdites et restreintes — Stripe](https://stripe.com/legal/restricted-businesses).

Avant le lancement :

1. transmettre au processeur une description honnête du modèle;
2. préciser que Gold n'est ni vendu, ni transférable, ni encaissable;
3. expliquer que l'abonnement ne multiplie pas Gold;
4. obtenir une acceptation écrite pour l'activité exacte;
5. vérifier séparément le fournisseur de cartes-cadeaux;
6. conserver les conditions et confirmations applicables;
7. prévoir un arrêt immédiat des échanges si le fournisseur suspend le service.

Contourner la classification d'un processeur par un libellé trompeur est interdit. Le mot « Gold » ne doit jamais masquer la réalité économique du programme.

### 16.1 Compatibilité avec un projet open source

Le caractère open source de PinCabOS n'empêche pas de financer le service hébergé, l'infrastructure, les événements, la modération ou l'administration de la boutique. La licence du code et les conditions du service sont deux sujets distincts.

Le dépôt public peut documenter :

- les règles XP et Gold;
- les formules de progression;
- le format des événements;
- le modèle de registre;
- les principes antifraude;
- les interfaces du fournisseur.

Le dépôt ne doit jamais contenir :

- les clés API de paiement ou de cartes-cadeaux;
- les codes de cartes non livrés;
- les données personnelles des joueurs;
- les preuves d'identité;
- les secrets de signature des cabinets;
- les seuils antifraude opérationnels qui faciliteraient un contournement immédiat.

Les licences des composants doivent être respectées individuellement. Le programme de récompenses ne doit jamais monétiser ni redistribuer des tables, ROMs, PuP-Packs, musiques, vidéos ou marques appartenant à des tiers. Le module de tournoi doit s'intégrer autour de VPX, BGFX et VPinFE sans modifier leur code ou leur état lorsque cette modification n'est pas autorisée ou nécessaire.

---

## 17. Comptabilité et budget

Même si PinCabGold n'est pas de l'argent, un solde échangeable peut représenter une obligation économique future.

Le tableau de bord administratif doit suivre :

- Gold émis;
- Gold utilisé;
- Gold annulé par écriture compensatoire;
- Gold en circulation;
- coût maximal théorique des échanges;
- coût réel des cartes livrées;
- budget par région;
- commandes en attente;
- taux d'échange;
- fraude évitée;
- taxes et factures des fournisseurs.

### Règle budgétaire proposée

Le système ne doit jamais promettre plus de récompenses que le budget approuvé. Avant chaque période :

1. définir un budget régional;
2. calculer le Gold maximal pouvant être émis;
3. réserver une marge pour les soldes existants;
4. publier la disponibilité réelle du catalogue;
5. suspendre l'émission de nouvelles promotions avant de manquer aux engagements existants.

Un comptable doit déterminer le traitement des cartes-cadeaux, des commandites, des taxes et des soldes de points dans chaque territoire.

---

## 18. Expérience responsable

L'objectif doit être de donner envie de participer, pas de « forcer » un joueur à répéter des parties pour récupérer une perte.

Principes :

- aucune perte de Gold pendant une partie;
- aucune dette ni balance négative;
- aucune possibilité de miser le Gold;
- aucun multiplicateur aléatoire;
- aucune roue de fortune, coffre surprise ou récompense cachée;
- progression et plafonds visibles avant de jouer;
- estimation claire du temps requis;
- rappels de pause lors de sessions prolongées;
- outils d'auto-exclusion du programme de récompenses;
- possibilité de jouer au multijoueur sans participer à Gold;
- aucune notification agressive annonçant une récompense « presque gagnée ».

La rétention doit venir des saisons, rivalités amicales, statistiques et badges, non d'une pression financière.

---

## 19. Documents à rédiger avant le lancement

Le code ne doit pas passer en production avec de simples textes génériques. Il faut préparer :

1. Conditions d'utilisation de PinCabOS.cc.
2. Règlement du programme PinCabGold.
3. Règlement des tournois et règles de déconnexion.
4. Politique de confidentialité Canada/Québec.
5. Information RGPD France/UE.
6. Politique antifraude et procédure d'appel.
7. Conditions de la boutique et des cartes-cadeaux.
8. Politique d'âge et de territoire.
9. Conditions des commanditaires.
10. Politique de fermeture ou modification du programme.
11. Plan de conservation et destruction des données.
12. Procédure d'incident et de notification.

Chaque acceptation importante doit être enregistrée avec : version du document, date, utilisateur, territoire et preuve technique raisonnable.

---

## 20. Plan de livraison

### Phase 0 — décisions et validations

- confirmer les pays du pilote;
- choisir l'entité exploitante;
- établir le modèle économique;
- consulter un avocat au Québec;
- consulter un avocat ou conseil spécialisé en France;
- obtenir l'accord du processeur et du fournisseur de cartes;
- approuver les règles et le budget.

### Phase 1 — PinCabXP seulement

- matchs vérifiés;
- registre XP;
- saisons;
- classement;
- badges;
- élimination simple;
- arbitrage et contestations;
- aucun Gold ni prix de valeur.

### Phase 2 — Gold sans valeur réelle

- registre Gold séparé;
- quotas;
- anti-fraude;
- boutique de badges et cosmétiques;
- conditions du programme;
- tests de charge et d'idempotence.

### Phase 3 — pilote de cartes-cadeaux

- un seul territoire;
- adultes seulement;
- petit budget fermé;
- récompenses de faible valeur;
- fournisseur approuvé;
- livraison manuelle ou semi-automatique;
- révision de chaque échange;
- audit après le pilote.

### Phase 4 — extension territoriale

- avis juridique séparé;
- nouveaux documents localisés;
- catalogue régional;
- fiscalité et fournisseurs validés;
- contrôles de résidence;
- surveillance continue.

### Phase 5 — tournois payants éventuels

Cette phase reste indépendante. Si PinCabOS veut un jour facturer l'entrée d'une compétition offrant un prix de valeur, il faudra soit :

- un avis juridique explicite couvrant le modèle exact;
- un processeur l'acceptant par écrit;
- les licences ou autorisations nécessaires;
- ou un opérateur tiers spécialisé qui devient réellement responsable de l'encaissement, des règles et des récompenses.

Un simple hébergement à l'étranger ne répond pas à ces exigences.

---

## 21. Critères GO / NOGO avant les cartes-cadeaux

### GO seulement si

- Gold est impossible à acheter et à transférer;
- le parcours générateur de Gold est gratuit;
- la victoire ne détermine pas la valeur échangeable principale;
- les plafonds et règles sont publics;
- le registre est auditable et idempotent;
- les contrôles antifraude fonctionnent;
- les comptes admissibles sont territorialisés;
- les conditions locales sont publiées;
- le budget couvre les obligations;
- le fournisseur de cartes autorise l'usage;
- le processeur de paiement a accepté le modèle;
- les avis juridiques Canada/Québec et France sont obtenus pour les régions ouvertes;
- la confidentialité et la sécurité ont été validées.

### NOGO immédiat si

- le joueur doit payer pour gagner du Gold;
- un abonnement augmente le rendement Gold;
- Gold peut être misé ou perdu;
- Gold peut être revendu ou transféré;
- une carte-cadeau dépend directement d'un résultat aléatoire;
- une région est ouverte sans analyse locale;
- les points existants sont dévalués rétroactivement;
- les soldes peuvent être modifiés sans écriture de registre;
- les secrets sont présents dans le dépôt;
- le fournisseur ou le processeur refuse l'activité;
- le programme cible ou encourage les mineurs à jouer pour une récompense de valeur.

---

## 22. Positionnement public proposé

> **PinCabXP récompense la performance. PinCabGold reconnaît la participation.**
>
> Jouez, progressez dans les classements et participez à la communauté PinCabOS. PinCabXP détermine votre parcours compétitif. PinCabGold est une récompense de fidélité gratuite, plafonnée et non transférable, utilisable uniquement selon les conditions et le catalogue disponibles dans votre région.

À éviter dans les communications :

- « gagnez de l'argent en jouant »;
- « rejouez jusqu'à récupérer votre mise »;
- « achetez plus de chances »;
- « transformez vos Gold en cash »;
- « prix garanti » lorsque le stock ou l'admissibilité ne le permet pas;
- toute présentation laissant croire que PinCabGold est une cryptomonnaie.

---

## 23. Conclusion

PinCabXP et PinCabGold peuvent former un excellent moteur de progression pour PinCabOS à condition que leurs rôles restent strictement séparés.

- **XP porte la compétition.**
- **Gold porte la fidélisation gratuite.**
- **La boutique reste régionale et contrôlée.**
- **La monétisation paie les services, jamais les chances de gagner.**
- **Les cartes-cadeaux ne sont activées qu'après validation.**

La meilleure première version est un mode tournoi gratuit avec XP, saisons, classements et badges. Gold peut ensuite être testé avec des récompenses numériques. Les cartes-cadeaux constituent une troisième étape, jamais un raccourci destiné à rendre acceptable un tournoi payant.

---

## 24. Sources principales

### Canada et Québec

- [Code criminel, article 206 — Justice Canada](https://laws-lois.justice.gc.ca/eng/acts/c-46/section-206.html)
- [Promotional Contests — Competition Bureau Canada](https://competition-bureau.canada.ca/en/promotional-contests-enforcement-guidelines)
- [Loi sur la protection du consommateur — Légis Québec](https://www.legisquebec.gouv.qc.ca/fr/document/lc/p-40.1)
- [Programmes de récompenses — Office de la protection du consommateur](https://www.opc.gouv.qc.ca/consommateur/bien-service/carte-prepayee/recompenses/definition/)
- [Expiration des unités d'échange — OPC](https://www.opc.gouv.qc.ca/consommateur/bien-service/carte-prepayee/recompenses/expiration/)
- [Collecte des renseignements personnels — CAI Québec](https://www.cai.gouv.qc.ca/protection-renseignements-personnels/information-entreprises-privees/collecte-renseignements-personnels_entreprises)
- [LPRPDE — Commissariat à la protection de la vie privée du Canada](https://www.priv.gc.ca/fr/sujets-lies-a-la-protection-de-la-vie-privee/lois-sur-la-protection-des-renseignements-personnels-au-canada/la-loi-sur-la-protection-des-renseignements-personnels-et-les-documents-electroniques-lprpde/)

### France et Union européenne

- [Code de la sécurité intérieure, article L320-1 — Légifrance](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000039182525)
- [Jeux autorisés en France — Autorité nationale des jeux](https://anj.fr/foire-aux-questions/offre-de-jeu-legale-et-illegale/quels-sont-les-jeux-dargent-et-paris-sportifs)
- [Loteries et pratiques commerciales — DGCCRF](https://www.economie.gouv.fr/dgccrf/les-fiches-pratiques/loterie-des-pratiques-commerciales-reglementees)
- [RGPD — EUR-Lex](https://eur-lex.europa.eu/eli/reg/2016/679/oj)

### Paiement

- [Activités interdites et restreintes — Stripe](https://stripe.com/legal/restricted-businesses)

---

**Prochaine décision recommandée :** approuver d'abord les règles PinCabXP et le format du tournoi à élimination, puis construire le registre XP sans aucune dépendance à Gold.
