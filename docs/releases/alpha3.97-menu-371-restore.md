# PinCabOS Alpha 3.97

Release ciblée — restauration du menu principal au comportement Alpha 3.71.

## Périmètre

- `opt/pincabos/web/static/pincabos-menu-tools.js` restauré à l’état Alpha 3.71.
- `opt/pincabos/web/static/pincabos-menu-tools.css` restauré à l’état Alpha 3.71.
- Retrait de la couche additionnelle `pincabos-menu-pin-viewport-v7.js`.
- Retrait uniquement de son injection globale.

## Conservation

- Toutes les autres fonctions de la WebApp restent sur leur version actuelle.
- Aucun rollback des modules, thèmes, pages, mises à jour ou fonctions ajoutés après Alpha 3.71.
- VPX / BGFX / VPinFE non touchés.

Correctif source : `41f626a013532863630c6bcfe1acf291875cc789`.
