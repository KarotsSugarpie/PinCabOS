# Smart Import metadata helper.
# Aucun route ou moteur de mises a jour.

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


# PINCABOS_IMPORT_METADATA_LOCAL_NORMALIZER_V1
def _pincabos_import_metadata_standard_table_name(name):
    """Normalise le nom de table sans dépendre de app.py.

    Ce module est importé par app.py, donc il ne doit pas appeler une fonction
    définie plus bas dans app.py. La logique garde le même format courant:
    Table Name (Manufacturer Year).
    """
    name = str(name or "").strip()
    name = name.replace("\\", " ").replace("/", " ")
    name = re.sub(r'[:"*?<>|]+', " ", name)
    name = re.sub(r"\s+", " ", name).strip()

    match = re.match(r"^(?P<table>.+?)_(?P<mfg>[^_()]+)_(?P<year>\d{4})_$", name)
    if match:
        table = re.sub(r"[_\s]+", " ", match.group("table")).strip()
        mfg = re.sub(r"[_\s]+", " ", match.group("mfg")).strip()
        year = match.group("year").strip()
        return f"{table} ({mfg} {year})"

    match = re.match(r"^(?P<table>.+?)\s+_(?P<mfg>[^_()]+?)\s+(?P<year>\d{4})_$", name)
    if match:
        table = re.sub(r"[_\s]+", " ", match.group("table")).strip()
        mfg = re.sub(r"[_\s]+", " ", match.group("mfg")).strip()
        year = match.group("year").strip()
        return f"{table} ({mfg} {year})"

    if "(" not in name and ")" not in name:
        match = re.match(
            r"^(?P<table>.+?)\s+(?P<mfg>Original|Williams|Stern|Bally|Gottlieb|Data East|Sega|HauntFreaks|MOD)\s+(?P<year>\d{4})$",
            name,
            re.I,
        )
        if match:
            table = re.sub(r"[_\s]+", " ", match.group("table")).strip()
            mfg = re.sub(r"[_\s]+", " ", match.group("mfg")).strip()
            year = match.group("year").strip()
            return f"{table} ({mfg} {year})"

    return name or "Imported Table"

def pincabos_write_imported_table_metadata(table_root, table_folder):
    """
    Après import:
    - renomme le .info principal pour suivre le nom du dossier;
    - met à jour pincabos-export-manifest.json;
    - met à jour pincabos-table-manifest.json;
    - garde les autres fichiers intacts.
    """
    table_root = Path(table_root)
    table_folder = _pincabos_import_metadata_standard_table_name(table_folder)

    wanted_info = table_root / f"{table_folder}.info"

    try:
        info_files = sorted(table_root.glob("*.info"))
        if info_files:
            # Si le bon .info n'existe pas, renommer le premier .info trouvé.
            if not wanted_info.exists():
                info_files[0].rename(wanted_info)

            # Mettre à jour le Title si c'est du JSON.
            try:
                data = json.loads(wanted_info.read_text(errors="replace"))
                if isinstance(data, dict):
                    if isinstance(data.get("Info"), dict):
                        data["Info"]["Title"] = table_folder
                    elif "title" in data:
                        data["title"] = table_folder
                    wanted_info.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass
    except Exception:
        pass

    for mf_name in ["pincabos-export-manifest.json", "pincabos-table-manifest.json"]:
        mf = table_root / mf_name
        if not mf.exists():
            continue

        try:
            data = json.loads(mf.read_text(errors="replace"))
            if isinstance(data, dict):
                data["table_folder"] = table_folder
                data["table_dir"] = str(table_root)
                data["table_root"] = str(table_root)
                if "title" in data:
                    data["title"] = table_folder
                if "table_name" in data:
                    data["table_name"] = table_folder
                mf.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

