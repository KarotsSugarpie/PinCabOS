# PinCabOS WebApp module: Secure PinCabOS table export V7 download endpoint.
# Generated from the monolithic app.py refactor.
# The host app injects legacy shared helpers during register().
from __future__ import annotations

import glob
import html
import json
import os
import re
import shlex
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import zipfile
from datetime import datetime
from pathlib import Path

from flask import jsonify, redirect, request, send_file, session, url_for

ROUTES: list[tuple[str, dict, object]] = []
BEFORE_REQUESTS: list[object] = []
AFTER_REQUESTS: list[object] = []

def route(rule: str, **options):
    """Record a Flask route locally; register() attaches it to the host app."""
    def decorator(func):
        ROUTES.append((rule, options, func))
        return func
    return decorator

def before_request(func):
    BEFORE_REQUESTS.append(func)
    return func

def after_request(func):
    AFTER_REQUESTS.append(func)
    return func

def register(host_app, runtime_globals: dict):
    """Bind shared helpers once, then register module-owned routes unchanged."""
    protected = {'ROUTES', 'route', 'register', '__name__', '__file__', '__package__'}
    for key, value in runtime_globals.items():
        if key not in protected:
            globals()[key] = value
    # Publish moved helpers back to the host namespace for legacy core pages that
    # still call them (for example page() -> firstrun_load_cfg()).
    prefixes = ("audio_", "ssf_", "inputs_", "firstrun_", "pincabos_", "PINCABOS_", "AUDIO_")
    for key, value in list(globals().items()):
        if key.startswith(prefixes):
            runtime_globals[key] = value
    for before_func in BEFORE_REQUESTS:
        host_app.before_request(before_func)
    for after_func in AFTER_REQUESTS:
        host_app.after_request(after_func)
    for rule, options, view_func in ROUTES:
        host_app.add_url_rule(rule, endpoint=view_func.__name__, view_func=view_func, **options)


def pincabos_export_table_package_v7(table_folder):
    paths = pincabos_table_export_dirs()
    tables_root = Path(paths["tables_root"]).resolve()
    exports_root = Path(paths["exports_root"]).resolve()

    requested = Path(str(table_folder or "")).name
    if not requested or requested in {".", ".."}:
        raise ValueError("Nom de dossier de table invalide.")

    table_dir = (tables_root / requested).resolve()
    if not table_dir.is_dir() or tables_root not in table_dir.parents:
        raise ValueError("Dossier de table invalide ou hors du répertoire Tables.")

    exports_root.mkdir(parents=True, exist_ok=True)
    pincabos_write_full_folder_export_manifest(table_dir)

    safe_name = pincabos_export_safe_filename(table_dir.name)
    vpsid = pincabos_detect_vpsid_for_export(table_dir)
    base_name = f"{safe_name} - VPSId {vpsid}" if vpsid else safe_name
    final_pkg = exports_root / f"{base_name}.PinCabOs"
    temp_zip = exports_root / f".{base_name}.building.zip"

    for path in (temp_zip, final_pkg):
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    try:
        pincabos_zip_full_table_folder(table_dir, temp_zip)
        if not temp_zip.is_file() or temp_zip.stat().st_size <= 0:
            raise RuntimeError("Le package temporaire est vide.")
        with zipfile.ZipFile(temp_zip, "r") as archive:
            broken = archive.testzip()
            if broken:
                raise RuntimeError(f"Archive invalide, premier fichier en erreur : {broken}")
        temp_zip.replace(final_pkg)
        try:
            subprocess.run(["/bin/chown", "pinball:pinball", str(final_pkg)], timeout=10, check=False)
            subprocess.run(["/bin/chmod", "664", str(final_pkg)], timeout=10, check=False)
        except Exception:
            pass
        return final_pkg
    finally:
        try:
            temp_zip.unlink()
        except FileNotFoundError:
            pass


@route("/tools/export-table/download-v7", methods=["POST"])
def tools_export_table_download_v7():
    table_folder = (
        request.form.get("table_folder")
        or request.form.get("table")
        or request.form.get("name")
        or ""
    ).strip()
    if not table_folder:
        return page("Export PinCabOS", """
<div class="card"><h2>Export PinCabOS v7</h2>
<p class="bad">Aucune table sélectionnée.</p>
<p><a class="button secondary" href="/tools">Retour</a></p></div>
"""), 400
    try:
        package = pincabos_export_table_package_v7(table_folder)
        return send_file(str(package), as_attachment=True, download_name=package.name, mimetype="application/octet-stream")
    except Exception as exc:
        return page("Export PinCabOS", """
<div class="card"><h2>Export PinCabOS v7</h2>
<p class="bad">Erreur export: """ + esc(str(exc)) + """</p>
<p><code>""" + esc(table_folder) + """</code></p>
<p><a class="button secondary" href="/tools">Retour</a></p></div>
"""), 500
