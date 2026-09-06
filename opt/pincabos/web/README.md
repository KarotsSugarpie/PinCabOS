# PinCabOS WebApp modulaire

## Validation obligatoire

Avant tout redémarrage :

```bash
cd /opt/pincabos/web
python3 -m py_compile *.py
python3 validate_refactor.py
```

Le validateur couvre tous les fichiers Python actifs du répertoire, les fonctions
top-level dupliquées, les routes critiques, les chemins Tables, le verrou Batch,
l’ordre de `app.run()`, la protection CSRF et l’état First Run GPU.

## Modules principaux

- `app.py` : noyau Flask et enregistrement des modules.
- `tools.py` : centre Outils et ConfigTools.
- `pincabos_impexp.py` : centres Import/Export natifs.
- `pincabos_batch_transfer.py` : moteurs Batch directs.
- `pincabos_batch_live.py` : export Batch en arrière-plan.
- `pincabos_batch_import_live.py`, `pincabos_batch_import_queue_v2.py`,
  `pincabos_batch_import_worker_v2.py` : import séquentiel persistant.
- `pincabos_webapp_audio.py`, `pincabos_webapp_inputs.py`,
  `pincabos_webapp_firstrun.py`, `pincabos_webapp_dev_admin.py`,
  `pincabos_webapp_exports.py` : modules fonctionnels extraits.
- `pincabos_webapp_security.py` : protection CSRF des actions sensibles.
- `pincabos_dashboard_lobby.py` et `pincabos_webapp_dashboard_control.py` : Dashboard.
- `PinCabOS-AboutHelp.py`,
  `PinCabOS-ExplorerInstall.py`, `PinCabOS-PackageIcon.py` : modules dynamiques.

## Dépendance Import ZIP

Les API `/api/import/analyze-zip` et `/api/import/apply-zip-choice` utilisent :

```text
/opt/pincabos/tools/pincabos_import_classifier.py
```

Si ce moteur est absent, la WebApp demeure fonctionnelle et ces deux API
retournent explicitement HTTP 503 au lieu d’une erreur interne 500.

## Identifiants Admin

Aucun mot de passe Admin n’est codé dans les sources. Configurer :

```text
/opt/pincabos/config/admin-login.txt
/opt/pincabos/config/admin-password.txt
```

Les fichiers `dev-login.txt` et `dev-password.txt` servent de repli compatible.
Les variables `PINCABOS_ADMIN_LOGIN` et `PINCABOS_ADMIN_PASSWORD` ont priorité.
