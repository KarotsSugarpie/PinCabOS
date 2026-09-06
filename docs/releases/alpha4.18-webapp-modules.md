# PinCabOS Alpha 4.18

Release de publication : livre à la flotte le découpage de la WebApp mergé après le hotfix #217 (les PR #212 à #216, plus anciennes que #217, n'ont pas produit de release).

## Périmètre

- Hotfix #217 (déjà livré en 4.17) : actions GPU du wizard de première exécution réparées.
- #212 : console système, mot de passe root, hotspot Wi-Fi, écran WebApp dans `pincabos_webapp_console.py`.
- #213 : bille VPX (réglages cabinet, carte simple, images UserBalls) dans `pincabos_webapp_vpxball.py`.
- #214 : Commander (gestionnaire de fichiers) et visionneuse live dans `pincabos_webapp_commander.py`.
- #215 : import de tables (pages et API) dans `pincabos_webapp_import.py`.
- #216 : export de tables dans `pincabos_webapp_export.py` ; réexport des helpers lus par d'autres modules dans les globals d'app.py.

## Ce que voit l'utilisateur

- Rien de nouveau, rien de retiré : mêmes pages, mêmes chemins, mêmes réponses (relevé de 80 pages identique au byte près en VM à chaque lot).
- `app.py` passe de 12 128 à 4 277 lignes ; huit modules de pages au total depuis la 4.10.

## Conservation

- VPX / BGFX / VPinFE, installeur, audio, DOF, réseau non touchés.
- Périmètre OTA : `opt/pincabos/web/` et `opt/pincabos/tests/` uniquement.
