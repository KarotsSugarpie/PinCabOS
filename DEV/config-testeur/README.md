# Config testeur PinCabOS

Ce répertoire reçoit les rapports matériels et de configuration générés par le script d'audit destiné aux testeurs PinCabOS.

## Nomenclature

`<testeur>-<hostname>-<YYYYMMDD-HHMMSS>-issue<numero>-system-audit.txt`

Exemple :

`jean-dupont-pincabos-20260828-163012-issue123-system-audit.txt`

Le nom du testeur est demandé au démarrage du script et est aussi écrit dans le rapport.

## Flux V3 — GitHub uniquement

Aucun composant `pincabos.cc` n'intervient dans ce flux.

1. `pincabos-system-audit.sh` collecte le matériel et la configuration en lecture seule.
2. Les IP, MAC, tokens, mots de passe, clés privées et credentials sont exclus ou masqués du rapport.
3. Le rapport est compressé en gzip et encodé en base64.
4. Un credential GitHub dédié, limité à `Issues: write`, crée un Issue transport et ses commentaires/chunks.
5. Le commentaire final `PINCABOS_TESTER_REPORT_COMPLETE_V3` déclenche `.github/workflows/pincabos-tester-report-ingest.yml`.
6. Le workflow valide l'auteur, le schéma, le nombre de chunks, la taille et le SHA-256.
7. Le workflow reconstruit le `.txt` et écrit uniquement sous `DEV/config-testeur/` avec son `GITHUB_TOKEN` temporaire.
8. L'Issue transport est ensuite fermé automatiquement.

Le credential distribué aux testeurs n'a pas besoin de `Contents: write` et ne doit jamais être un token principal donnant accès au code du dépôt.

## Commande d'audit

À exécuter dans la console comme utilisateur `pinball`, une fois le credential d'upload installé dans :

`/etc/pincabos/tester-report-issues.token`

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/KarotsSugarpie/PinCabOS/main/DEV/config-testeur/pincabos-system-audit.sh)
```

## Fichiers canoniques

- `pincabos-system-audit.sh` : client testeur GitHub-only V3.
- `pincabos-tester-report-ingest-v3.py` : validateur/reconstructeur exécuté par GitHub Actions.
- `.github/workflows/pincabos-tester-report-ingest.yml` : ingestion et commit automatique du rapport.
