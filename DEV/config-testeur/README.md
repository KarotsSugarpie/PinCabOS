# Config testeur PinCabOS

Ce répertoire reçoit les rapports matériels et de configuration générés par le script d'audit destiné aux testeurs PinCabOS.

## Nomenclature

`<testeur>-<hostname>-<YYYYMMDD-HHMMSS>-issue<numero>-system-audit.txt`

Exemple :

`jean-dupont-pincabos-20260828-163012-issue123-system-audit.txt`

Le nom du testeur est demandé au démarrage du lanceur et est aussi écrit dans le rapport.

## Flux V4 — aucun token sur les cabinets

Aucun composant `pincabos.cc` n'intervient dans ce flux.

1. Le testeur exécute `pincabos-system-audit-launcher.sh` comme utilisateur `pinball`.
2. Le lanceur demande uniquement le nom du testeur, télécharge `pincabos-system-audit-v4.sh` depuis la source canonique GitHub et lance l'audit avec `nohup`.
3. Une coupure SSH n'interrompt donc pas la collecte ni l'envoi.
4. `pincabos-system-audit-v4.sh` collecte le matériel et la configuration en lecture seule.
5. Les IP, MAC, tokens, mots de passe, clés privées et credentials sont exclus ou masqués du rapport.
6. Le rapport est compressé en gzip, encodé en base64 et envoyé en HTTPS au Cloudflare Worker `pincabos-tester-upload`.
7. Aucun token GitHub, login GitHub ou secret d'upload n'est stocké sur le cabinet.
8. Le Worker possède le credential GitHub comme secret Cloudflare et crée l'Issue de transport avec ses commentaires/chunks.
9. Le commentaire final `PINCABOS_TESTER_REPORT_COMPLETE_V3` déclenche `.github/workflows/pincabos-tester-report-ingest.yml`.
10. Le workflow valide l'auteur, le schéma transport, le nombre de chunks, la taille et le SHA-256.
11. Le workflow reconstruit le `.txt` et écrit uniquement sous `DEV/config-testeur/` avec son `GITHUB_TOKEN` temporaire.
12. L'Issue transport est ensuite fermé automatiquement.

Le Worker applique aussi une limite de requêtes avant les appels à GitHub.

## Endpoint actif

`https://pincabos-tester-upload.pincabos.workers.dev/v1/tester-report`

La valeur canonique est également conservée dans `upload-endpoint.txt`.

## Commande officielle du testeur

À exécuter dans la console comme utilisateur `pinball` :

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/KarotsSugarpie/PinCabOS/main/DEV/config-testeur/pincabos-system-audit-launcher.sh)
```

Le testeur ne fournit que son nom.

Aucun token, login GitHub, mot de passe ou préparation du cabinet n'est demandé.

Le journal de suivi est conservé sous :

`/home/pinball/.cache/pincabos-tester-report/`

## Fichiers canoniques actifs

- `pincabos-system-audit-launcher.sh` : lanceur V4 résilient aux coupures SSH et sans credential local.
- `pincabos-system-audit-v4.sh` : audit matériel/configuration et transport HTTPS vers Cloudflare.
- `cloudflare-worker/src/index.js` : passerelle Cloudflare vers GitHub Issues.
- `cloudflare-worker/wrangler.toml` : configuration du Worker et rate limiter.
- `upload-endpoint.txt` : endpoint V4 actif.
- `pincabos-tester-report-ingest-v3.py` : validateur/reconstructeur exécuté par GitHub Actions.
- `.github/workflows/pincabos-tester-report-ingest.yml` : ingestion et commit automatique du rapport.

## Héritage V3

`pincabos-system-audit.sh` est conservé uniquement comme référence de l'ancien transport direct GitHub. Le lanceur officiel ne l'utilise plus.
