"""Export de tables de la WebApp PinCabOS : /tools/export-table (dossier complet zippé avec manifeste) et /download-export.

Code déplacé tel quel depuis app.py (PINCABOS_WEBAPP_MODULES_V1) ; les routes gardent
leurs chemins et leurs noms de fonction. `page()` (gabarit commun) est fourni par app.py
à l'enregistrement : `register(app, page)`.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from pathlib import Path

from flask import Blueprint, request, send_file

from pincabos_webapp_core import esc, pincabos_get_vpinfe_paths_for_tools, pincabos_vpx_tables_dir

export_bp = Blueprint("export", __name__)

page = None  # gabarit HTML commun, posé par register()


def pincabos_list_installed_tables_for_export():
    """
    Liste les tables installées pour le menu Export.
    Une table = un dossier dans Tables qui contient au moins un fichier .vpx.
"""
    import json
    from pathlib import Path

    paths = pincabos_get_vpinfe_paths_for_tools()
    tables_root = Path(paths["tables"])

    tables = []

    if not tables_root.exists():
        return tables

    for folder in sorted([x for x in tables_root.iterdir() if x.is_dir()], key=lambda x: x.name.lower()):
        vpx_files = sorted(folder.glob("*.vpx"))

        if not vpx_files:
            continue

        info_files = sorted(folder.glob("*.info"))

        title = folder.name
        rom = ""
        vpsid = ""
        manufacturer = ""
        year = ""

        if info_files:
            try:
                data = json.loads(info_files[0].read_text(errors="replace"))
                info = data.get("Info", {})
                title = info.get("Title") or title
                rom = info.get("Rom") or ""
                vpsid = info.get("VPSId") or ""
                manufacturer = info.get("Manufacturer") or ""
                year = info.get("Year") or ""
            except Exception:
                pass

        extra = []
        if manufacturer:
            extra.append(str(manufacturer))
        if year:
            extra.append(str(year))
        if rom:
            extra.append("ROM " + str(rom))

        label = title
        if extra:
            label += " — " + " — ".join(extra)

        tables.append({
            "folder": folder.name,
            "title": title,
            "rom": rom,
            "vpsid": vpsid,
            "label": label,
        })

    return tables


def pincabos_find_value_deep(obj, wanted_keys):
    """
    Cherche récursivement une clé dans un dict/list JSON.
    """
    wanted = {str(k).lower() for k in wanted_keys}

    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() in wanted and v not in ("", None):
                return str(v).strip()
        for v in obj.values():
            found = pincabos_find_value_deep(v, wanted)
            if found:
                return found

    elif isinstance(obj, list):
        for item in obj:
            found = pincabos_find_value_deep(item, wanted)
            if found:
                return found

    return ""


def pincabos_export_safe_filename(name):
    name = str(name or "").strip()
    name = name.replace("\\", " ").replace("/", " ")
    name = re.sub(r'[:"*?<>|]+', " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name or "PinCabOS-Table"


def pincabos_table_export_dirs():
    """
    Modèle export PinCabOS:
    - aucune option;
    - aucun chemin legacy global;
    - on exporte le dossier complet de la table sélectionnée tel quel;
    - on ajoute/actualise seulement le manifest d'export;
    - on compresse au maximum;
    - extension finale .PinCabOs.
    """
    return {
        "tables_root": pincabos_vpx_tables_dir(),
        "exports_root": Path("/home/pinball/Exports"),
    }


def pincabos_export_should_exclude_relative(relative_path):
    """
    Exclusions techniques des packages portables PinCabOS.
    Les fichiers nécessaires à la table restent inclus.
    """
    rel = Path(relative_path)
    parts = rel.parts
    lower_parts = [part.lower() for part in parts]

    excluded_dirs = {
        ".pincabos-backups",
        ".pincabos-backup",
        ".pincabos-tmp",
        ".pincabos-cache",
        "cache",
        ".cache",
        "logs",
        "log",
        "__pycache__",
    }

    if any(part in excluded_dirs for part in lower_parts[:-1]):
        return True

    name = lower_parts[-1] if lower_parts else ""

    if name in {".ds_store", "thumbs.db"}:
        return True

    if name.endswith((".log", ".tmp", ".temp", ".pincabos-fulldmd-before-autoarrange.bak")):
        return True

    return False


def pincabos_write_full_folder_export_manifest(table_dir):
    table_dir = Path(table_dir)
    manifest_path = table_dir / "pincabos-export-manifest.json"

    files = []
    empty_dirs = []

    for p in sorted(table_dir.rglob("*")):
        rel_inside = p.relative_to(table_dir)

        if pincabos_export_should_exclude_relative(rel_inside):
            continue

        if p.is_symlink():
            continue

        if p.is_dir():
            try:
                included_children = [
                    child for child in p.iterdir()
                    if not pincabos_export_should_exclude_relative(
                        child.relative_to(table_dir)
                    )
                ]
                if not included_children:
                    empty_dirs.append(rel_inside.as_posix())
            except Exception:
                pass
            continue

        if p.is_file():
            try:
                files.append({
                    "path": rel_inside.as_posix(),
                    "size": p.stat().st_size,
                })
            except Exception:
                files.append({
                    "path": rel_inside.as_posix(),
                    "size": 0,
                })

    manifest = {
        "format": "PinCabOS table export",
        "format_version": 8,
        "model": "clean-portable-table-folder",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "table_folder": table_dir.name,
        "table_root": str(table_dir),
        "export_rule": (
            "Complete selected table directory excluding PinCabOS rollback "
            "backups, caches, temporary files and technical logs."
        ),
        "files": files,
        "empty_dirs": empty_dirs,
    }

    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    try:
        subprocess.run(
            ["/bin/chown", "pinball:pinball", str(manifest_path)],
            timeout=10,
            check=False,
        )
        subprocess.run(
            ["/bin/chmod", "664", str(manifest_path)],
            timeout=10,
            check=False,
        )
    except Exception:
        pass

    return manifest_path


def pincabos_zip_full_table_folder(table_dir, output_path):
    table_dir = Path(table_dir)
    output_path = Path(output_path)

    import zipfile

    with zipfile.ZipFile(
        output_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        allowZip64=True,
    ) as z:
        for p in sorted(table_dir.rglob("*")):
            rel_inside = p.relative_to(table_dir)

            if pincabos_export_should_exclude_relative(rel_inside):
                continue

            if p.is_symlink():
                continue

            rel = p.relative_to(table_dir.parent).as_posix()

            if p.is_dir():
                try:
                    included_children = [
                        child for child in p.iterdir()
                        if not pincabos_export_should_exclude_relative(
                            child.relative_to(table_dir)
                        )
                    ]
                    if not included_children:
                        z.writestr(rel.rstrip("/") + "/", "")
                except Exception:
                    pass
                continue

            if p.is_file():
                z.write(p, rel)

    return output_path


def pincabos_detect_vpsid_for_export(table_dir):
    """
    Détecte le VPSId pour nommer l'export.
    Sources:
    - *.info JSON
    - pincabos-table-manifest.json
    - pincabos-export-manifest.json
    """
    table_dir = Path(table_dir)

    keys = {
        "vpsid", "vps_id", "vpsdb", "vpsdbid", "vpsdb_id",
        "idvpsdb", "id_vpsdb", "id"
    }

    def find_deep(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                lk = str(k).strip().lower()
                if lk in keys and v not in ("", None):
                    val = str(v).strip()
                    # évite de prendre un id générique trop long ou un chemin
                    if val and "/" not in val and "\\" not in val and len(val) <= 64:
                        return val
            for v in obj.values():
                found = find_deep(v)
                if found:
                    return found

        if isinstance(obj, list):
            for item in obj:
                found = find_deep(item)
                if found:
                    return found

        return ""

    candidates = []
    candidates.extend(sorted(table_dir.glob("*.info")))
    candidates.append(table_dir / "pincabos-table-manifest.json")
    candidates.append(table_dir / "pincabos-export-manifest.json")

    for f in candidates:
        try:
            if not f.exists() or not f.is_file():
                continue
            data = json.loads(f.read_text(errors="replace"))
            found = find_deep(data)
            if found:
                return pincabos_export_safe_filename(found)
        except Exception:
            pass

    return ""


@export_bp.route("/tools/export-table", methods=["POST"])
def tools_export_table():
    paths = pincabos_table_export_dirs()
    tables_root = paths["tables_root"].resolve()
    exports_root = paths["exports_root"]

    table_name = request.form.get("table_folder", "").strip()
    if not table_name:
        table_name = request.form.get("table", "").strip()
    if not table_name:
        table_name = request.form.get("table_name", "").strip()

    if not table_name:
        return page("Export PinCabOS", """
<div class="card">
  <h2>Export impossible</h2>
  <p class="bad">Aucune table sélectionnée.</p>
  <p><a class="button" href="/tools">Retour Outils</a></p>
</div>
""")

    table_dir = (tables_root / table_name).resolve()

    if not table_dir.exists() or not table_dir.is_dir() or tables_root not in table_dir.parents:
        return page("Export PinCabOS", f"""
<div class="card">
  <h2>Export impossible</h2>
  <p class="bad">Dossier de table invalide.</p>
  <p><code>{esc(str(table_dir))}</code></p>
  <p><a class="button" href="/tools">Retour Outils</a></p>
</div>
""")

    exports_root.mkdir(parents=True, exist_ok=True)

    manifest_path = pincabos_write_full_folder_export_manifest(table_dir)

    safe_table = pincabos_export_safe_filename(table_dir.name)
    vpsid = pincabos_detect_vpsid_for_export(table_dir)

    if vpsid:
        export_base = f"{safe_table} - VPSId {vpsid}"
    else:
        export_base = safe_table

    tmp_zip = exports_root / f"{export_base}.zip"
    final_pkg = exports_root / f"{export_base}.PinCabOs"

    if tmp_zip.exists():
        tmp_zip.unlink()
    if final_pkg.exists():
        final_pkg.unlink()

    pincabos_zip_full_table_folder(table_dir, tmp_zip)

    tmp_zip.rename(final_pkg)

    try:
        subprocess.run(["/bin/chown", "pinball:pinball", str(final_pkg)], timeout=10, check=False)
        subprocess.run(["/bin/chmod", "664", str(final_pkg)], timeout=10, check=False)
    except Exception:
        pass

    size_mb = final_pkg.stat().st_size / 1024 / 1024

    delete_after_export = request.form.get("delete_after_export") == "1"
    deleted_table = False
    delete_message = ""

    export_ok = False
    try:
        import zipfile
        export_ok = final_pkg.exists() and final_pkg.is_file() and final_pkg.stat().st_size > 0
        if export_ok:
            with zipfile.ZipFile(final_pkg, "r") as z:
                export_ok = z.testzip() is None
    except Exception as e:
        export_ok = False
        delete_message = f"Validation export échouée: {e}"

    if delete_after_export:
        if export_ok:
            try:
                if table_dir.exists() and table_dir.is_dir() and tables_root in table_dir.parents:
                    shutil.rmtree(table_dir)
                    deleted_table = True
                    delete_message = "Table locale supprimée après export validé."
            except Exception as e:
                delete_message = f"Export OK, mais suppression impossible: {e}"
        else:
            if not delete_message:
                delete_message = "Suppression annulée: le package exporté n’a pas passé la validation."

    delete_html = ""
    if delete_after_export:
        cls = "ok" if deleted_table else "warn"
        delete_html = f'<p class="{cls}"><strong>Suppression après export :</strong> {esc(delete_message)}</p>'

    return page("Export PinCabOS", f"""
<div class="card">
  <h2>Export terminé</h2>
  <p class="ok">Package portable créé avec les fichiers utiles de la table. Les backups, caches et journaux techniques sont exclus.</p>
  {delete_html}

  <p><strong>Table :</strong> <code>{esc(table_dir.name)}</code></p>
  <p><strong>VPSId :</strong> <code>{esc(vpsid or "non détecté")}</code></p>
  <p><strong>Manifest :</strong> <code>{esc(str(manifest_path))}</code></p>
  <p><strong>Package :</strong> <code>{esc(str(final_pkg))}</code></p>
  <p><strong>Taille :</strong> {size_mb:.2f} MiB</p>

  <p>
    <a class="button" href="/download-export?file={esc(final_pkg.name)}">Télécharger .PinCabOs</a>
    <a class="button secondary" href="/tools">Retour Outils</a>
  </p>
</div>
""")


@export_bp.route("/download-export")
def download_export():
    paths = pincabos_table_export_dirs()
    exports_root = paths["exports_root"].resolve()

    filename = request.args.get("file", "").strip()
    if not filename:
        return "Fichier manquant", 400

    filename = Path(filename).name
    if not filename.lower().endswith(".pincabos"):
        return "Extension invalide", 400

    target = (exports_root / filename).resolve()

    if not target.exists() or not target.is_file() or exports_root not in target.parents:
        return "Fichier introuvable", 404

    return send_file(
        str(target),
        as_attachment=True,
        download_name=target.name,
        mimetype="application/octet-stream",
    )


def register(app, page_fn):
    """Enregistre l'export de tables sur l'application."""
    global page
    page = page_fn
    app.register_blueprint(export_bp)
