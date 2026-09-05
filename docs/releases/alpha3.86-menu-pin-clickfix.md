# PinCabOS Alpha 3.86

Correctif WebApp du menu principal épinglé.

- le menu reste fixe au viewport;
- la surface fixe du NAV est transparente aux clics;
- seuls les liens, boutons et contrôles interactifs captent les événements;
- suppression du forçage sticky/z-index des blocs INI dans le mécanisme d’épinglage;
- z-index ramenés à des valeurs raisonnables;
- restauration propre au désépinglage.

Correctifs principaux sur `main` :
- `40f6bf3330c0f2ba9833da15db7f09b1e73f1da3`
- `c892a7237005478e9f79ffa51164bdb5060df13c`
