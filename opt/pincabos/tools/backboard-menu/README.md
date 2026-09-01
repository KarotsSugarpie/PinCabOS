# pincabos-backboard-menu

Logos animés **par table** sur le backboard HD (matrice adressable pilotée par DOF)
**au menu vpinfe**, à partir du contenu communautaire **aerao.net / PinUP Menu**.

## Automatique

Si un backboard HD est déclaré dans `cabinet.xml` (`TeensyStripController` + toy
`LedStrip`), tout est automatique :

- au premier démarrage avec le matériel, le contenu s'installe tout seul
  (base aerao + `pinupmenu.gif`, injection dans la config DOF de la matrice,
  mapping des tables) ;
- à chaque démarrage, les **tables nouvellement installées** reçoivent leur logo
  si la base aerao les connaît (matching par nom) ;
- après un **import du DOF Config Tool** (qui écrase la config), le contenu est
  ré-appliqué automatiquement.

Sans backboard : l'outil ne touche à rien (sortie immédiate) — sans risque sur
toutes les installs.

## Comment ça marche

vpinfe, au survol d'une table dans le menu, envoie à DOF l'événement du champ
`FrontendDOFEvent` du `.info` de la table (la plage aléatoire `E900-E990` est
volontairement silencieuse ; tout le reste passe). L'outil :

1. injecte le code Custom MX1 aerao (événements `E2000+`) dans la ligne
   `pinupmenu` de la config DOF de la matrice et pose `pinupmenu.gif` ;
2. remplit `FrontendDOFEvent` de chaque table avec **son** événement aerao.

Les mappings automatiques ne remplissent **que les champs vides** : une
personnalisation manuelle n'est jamais écrasée (`map --overwrite` pour forcer).

## Commandes

| Commande | Effet |
|---|---|
| `auto` | Mode automatique (branché en `ExecStartPre` de vpinfe). |
| `install [version\|auto]` | Installe tout ; réactive après un `disable`. |
| `update [version\|auto]` | Re-télécharge gif + base aerao, ré-applique. |
| `apply` | Ré-applique après un pull du DOF Config Tool. |
| `map [--dry] [--overwrite]` | (Re)mappe les tables (`--dry` simulation). |
| `disable` | Retire le contenu **et** désactive le mode auto. |
| `status` | État : injection, base, événement de chaque table. |

Option globale `--force` : passer outre l'absence de backboard HD.

## État runtime

`/home/pinball/.pincabos/backboard/` : `aerao.csv`, `aerao_code.txt`,
`aerao_map.json`, `version.txt`, flag `disabled`.

## Limites

- Matching **par nom** (la base aerao n'expose pas les roms) : tables originales
  ou aux noms exotiques possibles sans logo (listées par `status`).
- Contenu 232×32 redimensionné par DOF vers la taille réelle de la matrice.
- Spécifique au frontend vpinfe (champ `FrontendDOFEvent`).
