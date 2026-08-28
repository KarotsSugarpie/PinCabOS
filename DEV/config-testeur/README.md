# Config testeur PinCabOS

Ce répertoire reçoit les rapports matériels et de configuration générés par le script d'audit destiné aux testeurs PinCabOS.

## Nomenclature

`<testeur>-<hostname>-<YYYYMMDD-HHMMSS>-<unique>-system-audit.txt`

Exemple :

`jean-dupont-pincabos-20260828-163012-a1b2c3-system-audit.txt`

Le nom du testeur est demandé au démarrage du script et est aussi écrit dans le rapport.

## Commande testeur

À exécuter dans la console comme utilisateur `pinball` :

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/KarotsSugarpie/PinCabOS/main/DEV/config-testeur/pincabos-system-audit.sh)
```

## Flux sécurisé

1. Le script collecte le matériel et la configuration en lecture seule.
2. Les IP, MAC, tokens, mots de passe, clés privées et credentials sont exclus ou masqués.
3. Le cabinet utilise son identité `PinCabOS-Device` déjà liée pour envoyer le rapport à `pincabos.cc`.
4. Le backend authentifie le cabinet et place le rapport dans un spool serveur.
5. Un service root côté serveur publie le fichier ici avec l'authentification GitHub du serveur.
6. Aucun credential GitHub n'est transmis au cabinet ou au processus web.

## Fichiers

- `pincabos-system-audit.sh` : client testeur V2.
- `pincabos_tester_report_v1.py` : endpoint backend compatible avec le contrat device existant.
- `pincabos-tester-report-publisher.py` : publisher GitHub exécuté en root.
- `PINFORGE-SAFE-INSTALL-TESTER-REPORT-V2.sh` : installation serveur avec backup et validations.
