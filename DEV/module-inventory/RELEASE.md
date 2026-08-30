# Point de release — inventaire des modules

Ce point de release publie l’inventaire statique ajouté par la PR #81.

## Contenu inclus

- 98 manifestes JSON pour les modules Python PinCabOS ;
- 10 manifestes JSON pour les modules Doctor ;
- 5 manifestes JSON pour les modules shell canoniques d’installation ;
- un index global et un schéma de validation ;
- un rapport séparé des éléments morts, dormants, dupliqués ou générés.

## État de sécurité

Les manifestes sont uniquement descriptifs pour cette étape :

- `lock_enabled` reste à `false` ;
- `repair_enabled` reste à `false` ;
- la propriété des fichiers reste en attente de validation manuelle.

Aucun verrou de réparation n’est donc activé par cette release.
