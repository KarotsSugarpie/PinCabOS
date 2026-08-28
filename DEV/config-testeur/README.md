# Config testeur PinCabOS

Ce répertoire reçoit les rapports matériels et de configuration générés par le script d'audit destiné aux testeurs PinCabOS.

## Nomenclature

`<testeur>-<hostname>-<YYYYMMDD-HHMMSS>-issue<numero>-system-audit.txt`

Exemple :

`jean-dupont-pincabos-20260828-163012-issue123-system-audit.txt`

Le nom du testeur est demandé au démarrage du script et est aussi écrit dans le rapport.

## Flux V3.2 — GitHub uniquement

Aucun composant `pincabos.cc` n'intervient dans ce flux.

1. `pincabos-system-audit-launcher.sh` demande le nom du testeur, télécharge la source canonique de l'audit et lance le travail avec `nohup` dans une tâche détachée.
2. Une coupure SSH ne doit donc pas interrompre la collecte ni l'upload GitHub.
3. `pincabos-system-audit.sh` collecte le matériel et la configuration en lecture seule.
4. Les IP, MAC, tokens, mots de passe, clés privées et credentials sont exclus ou masqués du rapport.
5. Le rapport est compressé en gzip et encodé en base64.
6. Un credential GitHub dédié, limité à `Issues: write`, crée un Issue transport et ses commentaires/chunks.
7. Le commentaire final `PINCABOS_TESTER_REPORT_COMPLETE_V3` déclenche `.github/workflows/pincabos-tester-report-ingest.yml`.
8. Le workflow valide l'auteur, le schéma, le nombre de chunks, la taille et le SHA-256.
9. Le workflow reconstruit le `.txt` et écrit uniquement sous `DEV/config-testeur/` avec son `GITHUB_TOKEN` temporaire.
10. L'Issue transport est ensuite fermé automatiquement.
11. Le credential local reste installé sur le cabinet pour les prochains audits.

Le credential distribué aux testeurs n'a pas besoin de `Contents: write` et ne doit jamais être un token principal donnant accès au code du dépôt.

## Credential persistant

Le credential d'upload est installé une seule fois dans :

`/etc/pincabos/tester-report-issues.token`

avec propriétaire `root:root` et mode `0600`.

Le lanceur V3.2 vérifie ces permissions mais ne supprime plus le token à la fin du job.

## Commande officielle du testeur

À exécuter dans la console comme utilisateur `pinball` :

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/KarotsSugarpie/PinCabOS/main/DEV/config-testeur/pincabos-system-audit-launcher.sh)
```

Le testeur ne fournit que son nom. Aucun token, login GitHub ou mot de passe ne lui est demandé.

Le journal de suivi est conservé sous :

`/home/pinball/.cache/pincabos-tester-report/`

## Fichiers canoniques

- `pincabos-system-audit-launcher.sh` : lanceur V3.2 résilient aux coupures SSH, credential persistant.
- `pincabos-system-audit.sh` : client d'audit GitHub-only V3.
- `pincabos-tester-report-ingest-v3.py` : validateur/reconstructeur exécuté par GitHub Actions.
- `.github/workflows/pincabos-tester-report-ingest.yml` : ingestion et commit automatique du rapport.
