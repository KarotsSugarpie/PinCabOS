#!/usr/bin/env python3
"""Validation statique complète de la WebApp modulaire PinCabOS."""
from __future__ import annotations

import ast
import collections
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXCLUDED_TOKENS = (".bak", ".before-", ".original", "__pycache__")
FILES = sorted(
    path for path in ROOT.glob("*.py")
    if not any(token in path.name for token in EXCLUDED_TOKENS)
)

errors: list[str] = []
warnings: list[str] = []
routes: list[tuple[str, tuple[str, ...], str, str, int]] = []


def decorator_route(node: ast.AST):
    for dec in getattr(node, "decorator_list", []):
        if not isinstance(dec, ast.Call) or not dec.args:
            continue
        if not isinstance(dec.args[0], ast.Constant) or not isinstance(dec.args[0].value, str):
            continue
        func = dec.func
        if not (
            (isinstance(func, ast.Attribute) and func.attr == "route")
            or (isinstance(func, ast.Name) and func.id == "route")
        ):
            continue
        methods = ("GET",)
        for keyword in dec.keywords:
            if keyword.arg == "methods":
                try:
                    methods = tuple(sorted(str(x).upper() for x in ast.literal_eval(keyword.value)))
                except Exception:
                    pass
        return dec.args[0].value, methods
    return None


for path in FILES:
    try:
        source = path.read_text(encoding="utf-8")
        compile(source, str(path), "exec")
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        errors.append(f"Syntaxe invalide dans {path.name}: {exc}")
        continue

    top_level = [
        node.name for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    for name, count in collections.Counter(top_level).items():
        if count > 1:
            errors.append(f"Fonction top-level dupliquée dans {path.name}: {name} ({count})")

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            route = decorator_route(node)
            if route:
                routes.append((route[0], route[1], node.name, path.name, node.lineno))

app_path = ROOT / "app.py"
app_text = app_path.read_text(encoding="utf-8")
if "str(zp).startswith(str(root))" in app_text or "str(td).startswith(str(tables_root))" in app_text:
    errors.append("Validation de chemin startswith encore présente dans app.py")
if 'tables_root = Path("/opt/pincabos/tables")' in app_text:
    errors.append("Ancien dossier /opt/pincabos/tables encore utilisé")
if "PINCABOS_MAIN_ENTRYPOINT_LAST_V1" not in app_text:
    errors.append("Entrypoint Flask final absent")
else:
    tree = ast.parse(app_text)
    if not tree.body or not isinstance(tree.body[-1], ast.If):
        errors.append("app.run() n’est pas la dernière instruction top-level")
if "PINCABOS_WEBAPP_SECURITY_V1_REGISTER" not in app_text:
    errors.append("Module sécurité CSRF non enregistré")

lock_default = "/var/lib/pincabos/batch-live/export.lock"
for name in (
    "pincabos_batch_transfer.py",
    "pincabos_batch_live.py",
    "pincabos_batch_import_queue_v2.py",
):
    text = (ROOT / name).read_text(encoding="utf-8")
    if lock_default not in text or "PINCABOS_BATCH_LIVE_SHARED_LOCK" not in text:
        errors.append(f"Verrou Batch partagé absent/incohérent dans {name}")

exports_text = (ROOT / "pincabos_webapp_exports.py").read_text(encoding="utf-8")
if 'methods=["GET", "POST"]' in exports_text:
    errors.append("Export V7 accepte encore GET")
if not (ROOT / "pincabos_webapp_security.py").is_file():
    errors.append("pincabos_webapp_security.py absent")

firstrun_text = (ROOT / "pincabos_webapp_firstrun.py").read_text(encoding="utf-8")
for marker in ("firstrun-gpu-state.json", "reboot_pending", "_firstrun_boot_id", "_firstrun_gpu_probe"):
    if marker not in firstrun_text:
        errors.append(f"First Run GPU incomplet: {marker} absent")

# Les deux GET Smart sont volontairement conditionnels dans tools.py et natifs
# dans pincabos_impexp.py. Toute autre collision exacte est signalée.
allowed_conditional = {
    ("/tools/import-table", ("GET",)),
    ("/tools/export-table", ("GET",)),
}
for key, count in collections.Counter((r[0], r[1]) for r in routes).items():
    if count > 1 and key not in allowed_conditional:
        origins = [f"{r[3]}:{r[4]}:{r[2]}" for r in routes if (r[0], r[1]) == key]
        errors.append(f"Route dupliquée {key[0]} {key[1]}: {origins}")

required_routes = {
    "/audio-ssf/save",
    "/audio-ssf/commander",
    "/tools/export-table/download-v7",
    "/dev/cleanup-nosnap",
    "/first-run/action/<action>",
    "/api/batch-import/live/create",
    "/api/batch-export/live/start",
    "/backupcfg",
    "/tools/backupcfg",
    "/api/backupcfg/backup",
    "/api/backupcfg/restore-upload",
    "/api/backupcfg/restore-local",
    "/api/backupcfg/status/<job_id>",
    "/api/backupcfg/download/<job_id>",
}
found_routes = {route for route, _methods, _name, _file, _line in routes}
for route in sorted(required_routes - found_routes):
    errors.append(f"Route critique absente: {route}")

backupcfg_helper = ROOT.parent / "tools" / "pincabos-backupcfg"
backupcfg_sudoers = ROOT.parents[2] / "etc" / "sudoers.d" / "pincabos-backupcfg"
if not backupcfg_helper.is_file():
    errors.append("Moteur privilégié Backup Config absent")
elif not (backupcfg_helper.stat().st_mode & 0o100):
    errors.append("Moteur privilégié Backup Config non exécutable")
if not backupcfg_sudoers.is_file():
    errors.append("Règle sudoers Backup Config absente")
if "PINCABOS_BACKUPCFG_CARD_V1" not in (ROOT / "tools.py").read_text(encoding="utf-8"):
    errors.append("Carte Backup Config absente de la page Tools")

classifier_candidates = (
    ROOT / "pincabos_import_classifier.py",
    Path("/opt/pincabos/tools/pincabos_import_classifier.py"),
)
if not any(path.is_file() for path in classifier_candidates):
    warnings.append(
        "Moteur optionnel pincabos_import_classifier absent; les API ZIP retourneront HTTP 503."
    )

if errors:
    print("NOGO: validation complète échouée")
    for error in errors:
        print(" -", error)
    for warning in warnings:
        print(" WARN:", warning)
    sys.exit(1)

print("GO: syntaxe et structure complètes validées")
print(f"GO: {len(FILES)} fichiers Python actifs contrôlés, {len(routes)} routes déclarées")
for warning in warnings:
    print("WARN:", warning)
