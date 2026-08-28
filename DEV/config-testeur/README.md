# Config testeur PinCabOS

Ce répertoire reçoit les rapports matériels et de configuration générés par le script d'audit destiné aux testeurs PinCabOS.

## Règles

- Rapports texte uniquement (`.txt`).
- Aucun mot de passe, token, clé SSH, cookie ou credential ne doit être collecté.
- Le testeur ne doit jamais recevoir de credential GitHub.
- L'envoi doit passer par le point d'entrée serveur PinCabOS prévu à cet effet, puis être publié ici côté serveur.
- Les noms de rapports doivent être uniques et inclure au minimum le hostname et un horodatage.

## Format de nom recommandé

`<hostname>-<YYYYMMDD-HHMMSS>-system-audit.txt`
