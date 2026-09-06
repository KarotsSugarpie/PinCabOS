"""Import de tables de la WebApp PinCabOS : /tools/import-table (analyse, conflit de manifeste, installation) et /api/import (recherche VPSDB, analyse et choix d'un ZIP).

Code déplacé tel quel depuis app.py (PINCABOS_WEBAPP_MODULES_V1) ; les routes gardent
leurs chemins et leurs noms de fonction. `page()` (gabarit commun) est fourni par app.py
à l'enregistrement : `register(app, page)`.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, request

from pincabos_webapp_core import esc, pco_script, pincabos_vpx_tables_dir
from pincabos_webapp_import_metadata import pincabos_write_imported_table_metadata
from werkzeug.utils import secure_filename
import_bp = Blueprint("import", __name__)

page = None  # gabarit HTML commun, posé par register()


def pincabos_force_standard_table_name(name):
    """
    Force le format:
    Table Name (Manufacturer Year)

    Exemples:
    The Leprechaun King_Original_2019_ -> The Leprechaun King (Original 2019)
    Ramones _Original 2021_           -> Ramones (Original 2021)
    Ramones_Original_2021_            -> Ramones (Original 2021)
    """
    name = str(name or "").strip()

    name = name.replace("\\", " ").replace("/", " ")
    name = re.sub(r'[:"*?<>|]+', " ", name)
    name = re.sub(r"\s+", " ", name).strip()

    # Cas: Table_Manufacturer_Year_
    m = re.match(r"^(?P<table>.+?)_(?P<mfg>[^_()]+)_(?P<year>\d{4})_$", name)
    if m:
        table = re.sub(r"[_\s]+", " ", m.group("table")).strip()
        mfg = re.sub(r"[_\s]+", " ", m.group("mfg")).strip()
        year = m.group("year").strip()
        return f"{table} ({mfg} {year})"

    # Cas: Table _Manufacturer Year_
    m = re.match(r"^(?P<table>.+?)\s+_(?P<mfg>[^_()]+?)\s+(?P<year>\d{4})_$", name)
    if m:
        table = re.sub(r"[_\s]+", " ", m.group("table")).strip()
        mfg = re.sub(r"[_\s]+", " ", m.group("mfg")).strip()
        year = m.group("year").strip()
        return f"{table} ({mfg} {year})"

    # Cas: Table Manufacturer 2021, seulement si pas déjà avec parenthèses
    if "(" not in name and ")" not in name:
        m = re.match(r"^(?P<table>.+?)\s+(?P<mfg>Original|Williams|Stern|Bally|Gottlieb|Data East|Sega|HauntFreaks|MOD)\s+(?P<year>\d{4})$", name, re.I)
        if m:
            table = re.sub(r"[_\s]+", " ", m.group("table")).strip()
            mfg = re.sub(r"[_\s]+", " ", m.group("mfg")).strip()
            year = m.group("year").strip()
            return f"{table} ({mfg} {year})"

    return name or "Imported Table"


def pincabos_import_safe_job_id():
    import datetime
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]


def pincabos_list_archive_files(path):
    try:
        r = subprocess.run(
            ["7z", "l", "-slt", str(path)],
            capture_output=True,
            text=True,
            timeout=45
        )
        data = (r.stdout + "\n" + r.stderr)
        out = []
        for line in data.splitlines():
            line = line.strip()
            if line.startswith("Path = "):
                value = line.split("=", 1)[1].strip()
                if value and value != str(path):
                    out.append(value)
        return out
    except Exception:
        return []


def pincabos_is_zip_rom(path):
    if not str(path).lower().endswith(".zip"):
        return False

    files = [x.lower() for x in pincabos_list_archive_files(path)]
    joined = "\n".join(files)

    markers = [
        ".vpx",
        ".dif",
        ".directb2s",
        ".pov",
        ".vbs",
        "pinupplayer.ini",
        ".pup",
        ".ultradmd",
        "altsound.ini",
        "altsound.csv",
        ".ogg",
        ".wav",
        ".mp3",
        ".flac",
        ".pac",
        ".pal",
        ".vni",
        ".serum",
    ]

    if any(m in joined for m in markers):
        return False

    return True


def pincabos_detect_batch(batch_dir):
    import re
    from pathlib import Path

    batch = Path(batch_dir)
    files = [p for p in batch.rglob("*") if p.is_file()]
    archive_virtual_files = []

    for f in files:
        if f.suffix.lower() in [".zip", ".rar", ".7z"]:
            for inner in pincabos_list_archive_files(f):
                archive_virtual_files.append((f, inner))

    detected = {
        "main_vpx": "",
        "table_name": "",
        "has_vpu_patch": False,
        "vpu_patch_file": "",
        "rom": "",
        "has_b2s": False,
        "has_pov": False,
        "has_ini": False,
        "has_vbs": False,
        "has_rom": False,
        "has_altsound": False,
        "has_altcolor": False,
        "has_puppack": False,
        "has_ultradmd": False,
        "files": [str(x) for x in files],
    }

    vpx_files = [f for f in files if f.suffix.lower() == ".vpx"]
    if vpx_files:
        vpx_files.sort(key=lambda x: x.stat().st_size if x.exists() else 0, reverse=True)
        detected["main_vpx"] = str(vpx_files[0])
        detected["table_name"] = re.sub(r"[_]+", " ", vpx_files[0].stem).strip()

    if not detected["table_name"]:
        for archive, inner in archive_virtual_files:
            if inner.lower().endswith(".vpx"):
                detected["table_name"] = re.sub(r"[_]+", " ", Path(inner).stem).strip()
                detected["main_vpx"] = str(archive) + "::" + inner
                break

    dif_files = [f for f in files if f.suffix.lower() == ".dif"]

    if dif_files:
        detected["has_vpu_patch"] = True
        detected["vpu_patch_file"] = str(dif_files[0])

        if not detected["table_name"]:
            detected["table_name"] = re.sub(
                r"[_]+",
                " ",
                dif_files[0].stem,
            ).strip()

    for archive, inner in archive_virtual_files:
        if inner.lower().endswith(".dif"):
            detected["has_vpu_patch"] = True
            detected["vpu_patch_file"] = str(archive) + "::" + inner

            if not detected["table_name"]:
                detected["table_name"] = re.sub(
                    r"[_]+",
                    " ",
                    Path(inner).stem,
                ).strip()
            break

    for f in files:
        if pincabos_is_zip_rom(f):
            detected["rom"] = f.stem
            detected["has_rom"] = True
            break

    # Détection AltSound et indice ROM
    for f in files:
        if f.suffix.lower() in [".rar", ".7z", ".zip"]:
            inner_files = [x.lower() for x in pincabos_list_archive_files(f)]
            names = [Path(x).name.lower() for x in inner_files]
            if "altsound.ini" in names or "altsound.csv" in names or sum(1 for x in inner_files if x.endswith(".ogg")) > 10:
                detected["has_altsound"] = True
                if not detected["rom"]:
                    detected["rom"] = f.stem

    for f in files:
        suffix = f.suffix.lower()

        if suffix == ".directb2s":
            detected["has_b2s"] = True
        elif suffix == ".pov":
            detected["has_pov"] = True
        elif suffix == ".ini":
            detected["has_ini"] = True
        elif suffix == ".vbs":
            detected["has_vbs"] = True
        elif suffix in [".pac", ".pal", ".vni", ".serum"]:
            detected["has_altcolor"] = True

        if suffix in [".zip", ".rar", ".7z"]:
            inner = "\n".join([x.lower() for x in pincabos_list_archive_files(f)])
            if "pinupplayer.ini" in inner or ".pup" in inner or inner.count(".mp4") >= 3:
                detected["has_puppack"] = True
            if ".ultradmd" in inner:
                detected["has_ultradmd"] = True
            if ".directb2s" in inner:
                detected["has_b2s"] = True
            if ".pov" in inner:
                detected["has_pov"] = True
            if ".vbs" in inner:
                detected["has_vbs"] = True
            if ".dif" in inner:
                detected["has_vpu_patch"] = True
            if ".pac" in inner or ".pal" in inner or ".vni" in inner or ".serum" in inner:
                detected["has_altcolor"] = True

    if not detected["table_name"]:
        detected["table_name"] = batch.name

    return detected


def pincabos_vpsdb_matches(table_name, rom):
    try:
        helper = str(pco_script("vpinfe_vpsdb_match"))
        r = subprocess.run(
            [helper, table_name, rom or ""],
            capture_output=True,
            text=True,
            timeout=30
        )

        if r.returncode != 0:
            print(f"PCO VPSdb helper failed rc={r.returncode}: {helper} stderr={r.stderr[-1200:]}")
            return []

        raw = (r.stdout or "").strip()
        if not raw:
            print(f"PCO VPSdb helper returned empty output: {helper}")
            return []

        data = json.loads(raw)
        if not data.get("ok"):
            print(f"PCO VPSdb helper returned error: {data.get('error', 'unknown error')}")
            return []

        return data.get("matches", [])
    except Exception as exc:
        print(f"PCO VPSdb matcher exception: {exc}")
        return []


PINCABOS_SMART_IMPORT_RESOURCE_MANIFEST = (
    ".pincabos-smart-import-resources.json"
)


def pincabos_smart_import_resource_manifest_path(batch_dir):
    return (
        Path(batch_dir)
        / PINCABOS_SMART_IMPORT_RESOURCE_MANIFEST
    )


def pincabos_smart_import_file_sha256(path):
    digest = hashlib.sha256()

    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def pincabos_smart_import_exact_resource(vpsid):
    wanted = str(vpsid or "").strip()

    if not wanted:
        raise RuntimeError("VPS-ID vide.")

    matches = pincabos_vpsdb_matches(wanted, "")
    exact = [
        match
        for match in matches
        if str(match.get("id", "") or "").strip().casefold()
        == wanted.casefold()
    ]

    if not exact:
        raise RuntimeError(
            f"VPS-ID inconnu dans la base locale VPSDB: {wanted}"
        )

    if len(exact) != 1:
        raise RuntimeError(
            f"VPS-ID ambigu dans VPSDB: {wanted} ({len(exact)} résultats)"
        )

    resource = dict(exact[0])
    resource_type = str(resource.get("resource_type", "") or "").strip()

    if not resource_type or resource_type == "game":
        raise RuntimeError(
            f"{wanted} est l'ID général du jeu. Entre l'ID exact du fichier VPSDB."
        )

    if (
        resource_type == "tableFile"
        and str(resource.get("table_format", "") or "").strip()
        and str(resource.get("table_format", "") or "").strip().casefold()
        != "vpx"
    ):
        raise RuntimeError(
            f"VPS-ID {wanted}: format de table non VPX refusé "
            f"({resource.get('table_format')})."
        )

    return resource


def pincabos_smart_import_load_resource_manifest(batch_dir, required=False):
    path = pincabos_smart_import_resource_manifest_path(batch_dir)

    if not path.is_file():
        if required:
            raise RuntimeError(
                "Inventaire VPS-ID par fichier absent du batch Smart Import."
            )
        return {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(
            f"Inventaire VPS-ID illisible: {exc}"
        ) from exc

    if (
        not isinstance(payload, dict)
        or payload.get("format")
        != "PinCabOS Smart Import resources"
        or not isinstance(payload.get("resources"), list)
    ):
        raise RuntimeError("Inventaire VPS-ID Smart Import invalide.")

    return payload


def pincabos_try_manifest_import_from_saved_batch(batch_dir):
    """
    Import direct d'un package PinCabOS depuis /tools/import-table/analyze.

    Règle:
    - si le batch contient un .PinCabOs/.pincabos/.zip/.7z/.rar avec pincabos-export-manifest.json,
      on bypass complètement VPSdb/analyse;
    - on restaure selon le manifest;
    - si aucun manifest n'est trouvé, on retourne None et l'analyse normale continue.
    """
    batch_dir = Path(batch_dir)

    archive_exts = {".pincabos", ".zip", ".7z", ".rar"}

    archives = []
    try:
        for p in sorted(batch_dir.rglob("*")):
            if p.is_file() and p.suffix.lower() in archive_exts:
                archives.append(p)
    except Exception:
        archives = []

    for archive_path in archives:
        try:
            with tempfile.TemporaryDirectory(prefix="pincabos-json-found-") as td:
                extract_dir = Path(td) / "extract"
                extract_dir.mkdir(parents=True, exist_ok=True)

                r7 = subprocess.run(
                    ["7z", "x", "-y", f"-o{str(extract_dir)}", str(archive_path)],
                    capture_output=True,
                    text=True,
                    timeout=1800,
                    check=False,
                )

                if r7.returncode != 0:
                    continue

                has_manifest = any(
                    n.name == "pincabos-export-manifest.json"
                    for n in extract_dir.rglob("*")
                    if n.is_file()
                )

                if not has_manifest:
                    continue

                table_folder, _manifest_preview = pincabos_manifest_table_folder_from_archive(archive_path)
                if table_folder:
                    table_root = pincabos_vpx_tables_dir() / table_folder
                    if table_root.exists():
                        return pincabos_manifest_import_conflict_page(batch_dir, archive_path, table_folder)

                result = pincabos_import_from_manifest_dir(extract_dir, overwrite_existing=False)
                if result:
                    if result.get("skipped") and "CONFLICT_TABLE_EXISTS" in result.get("skipped", []):
                        return pincabos_manifest_import_conflict_page(batch_dir, archive_path, result.get("table_folder", table_folder or "Imported Table"))

                    result["message"] = "Package PinCabOS détecté — import direct par manifest, analyse VPSdb ignorée."

                    # Nettoyage du batch upload après import manifest.
                    try:
                        uploads_root = Path("/home/pinball/Downloads").resolve()
                        batch_real = Path(batch_dir).resolve()
                        if batch_real.exists() and uploads_root in batch_real.parents:
                            shutil.rmtree(batch_real)
                    except Exception as e:
                        result.setdefault("skipped", [])
                        result["skipped"].append(f"WARNING cleanup upload batch: {e}")

                    return pincabos_manifest_import_result_page(result)

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            try:
                log_dir = Path("/opt/pincabos/logs")
                log_dir.mkdir(parents=True, exist_ok=True)
                log_file = log_dir / "import-manifest-error.log"
                with log_file.open("a", encoding="utf-8") as lf:
                    lf.write("\n=== IMPORT_MANIFEST_TRACEBACK ===\n")
                    lf.write(f"archive_path={archive_path}\n")
                    lf.write(f"batch_dir={batch_dir}\n")
                    lf.write(tb)
                    lf.write("\n")
            except Exception:
                pass

            return page("Import PinCabOS", f"""
<div class="card">
  <h2>Import PinCabOS impossible</h2>
  <p class="bad">Package PinCabOS détecté, mais erreur pendant l’import manifest.</p>
  <pre>{esc(str(e))}</pre>
  <p class="warn">Traceback complet écrit dans <code>/opt/pincabos/logs/import-manifest-error.log</code></p>
  <p><a class="button" href="/tools">Retour aux outils</a></p>
</div>
""")

    return None


@import_bp.route("/tools/import-table/manifest-conflict", methods=["POST"])
def tools_import_table_manifest_conflict():
    batch_dir = Path(request.form.get("batch_dir", "")).resolve()
    archive_path = Path(request.form.get("archive_path", "")).resolve()
    action = request.form.get("conflict_action", "").strip().lower()
    new_table_name = request.form.get("new_table_name", "").strip()

    uploads_root = Path("/home/pinball/Downloads").resolve()

    if not batch_dir.exists() or uploads_root not in batch_dir.parents:
        return page("Import PinCabOS", """
<div class="card">
  <h2>Import impossible</h2>
  <p class="bad">Batch d’import invalide ou expiré.</p>
  <p><a class="button" href="/tools">Retour aux outils</a></p>
</div>
""")

    if not archive_path.exists() or batch_dir not in archive_path.parents:
        return page("Import PinCabOS", """
<div class="card">
  <h2>Import impossible</h2>
  <p class="bad">Package d’import invalide.</p>
  <p><a class="button" href="/tools">Retour aux outils</a></p>
</div>
""")

    if action not in ["replace", "rename"]:
        return page("Import PinCabOS", """
<div class="card">
  <h2>Import impossible</h2>
  <p class="bad">Action de conflit invalide.</p>
  <p><a class="button" href="/tools">Retour aux outils</a></p>
</div>
""")

    table_folder, _manifest_preview = pincabos_manifest_table_folder_from_archive(archive_path)
    if not table_folder:
        table_folder = "Imported Table"

    if action == "rename":
        if not new_table_name:
            return pincabos_manifest_import_conflict_page(batch_dir, archive_path, table_folder)
        final_table_name = pincabos_standard_table_folder_name(new_table_name) or table_folder
    else:
        final_table_name = table_folder

    try:
        with tempfile.TemporaryDirectory(prefix="pincabos-conflict-import-") as td:
            extract_dir = Path(td) / "extract"
            extract_dir.mkdir(parents=True, exist_ok=True)

            r7 = subprocess.run(
                ["7z", "x", "-y", f"-o{str(extract_dir)}", str(archive_path)],
                capture_output=True,
                text=True,
                timeout=1800,
                check=False,
            )

            if r7.returncode != 0:
                raise RuntimeError((r7.stdout + "\\n" + r7.stderr).strip())

            result = pincabos_import_from_manifest_dir(
                extract_dir,
                table_folder_override=final_table_name,
                overwrite_existing=True,
            )

        if result:
            if action == "replace":
                result["message"] = "Package PinCabOS importé en remplaçant la table existante."
            else:
                result["message"] = f"Package PinCabOS importé sous le nouveau nom: {final_table_name}"

            try:
                if batch_dir.exists() and uploads_root in batch_dir.parents:
                    shutil.rmtree(batch_dir)
            except Exception as e:
                result.setdefault("skipped", [])
                result["skipped"].append(f"WARNING cleanup upload batch: {e}")

            return pincabos_manifest_import_result_page(result)

    except Exception as e:
        return page("Import PinCabOS", f"""
<div class="card">
  <h2>Import impossible</h2>
  <p class="bad">Erreur pendant le traitement du conflit.</p>
  <pre>{esc(str(e))}</pre>
  <p><a class="button" href="/tools">Retour aux outils</a></p>
</div>
""")

    return page("Import PinCabOS", """
<div class="card">
  <h2>Import impossible</h2>
  <p class="bad">Aucun résultat d’import.</p>
  <p><a class="button" href="/tools">Retour aux outils</a></p>
</div>
""")


def pincabos_match_rom_value(m, detected=None):
    """
    Retourne la ROM depuis un match VPSdb/VPinFE si disponible.
    Fallback sur detected["rom"].
    """
    detected = detected or {}

    keys = [
        "rom", "Rom", "ROM",
        "romName", "RomName", "rom_name",
        "romFile", "RomFile", "rom_file",
        "bios", "Bios", "BIOS",
        "pinmame", "PinMAME",
    ]

    for k in keys:
        val = ""
        try:
            val = m.get(k, "")
        except Exception:
            val = ""
        val = str(val or "").strip()
        if val:
            val = Path(val).name
            if val.lower().endswith(".zip"):
                val = val[:-4]
            return val

    val = str(detected.get("rom", "") or "").strip()
    if val.lower().endswith(".zip"):
        val = val[:-4]
    return val


@import_bp.route("/api/import/vpsdb-search")
def api_import_vpsdb_search():
    q = request.args.get("q", "").strip()
    rom = request.args.get("rom", "").strip()
    wanted_vpsid = request.args.get("vpsid", "").strip()

    if not q and not rom and not wanted_vpsid:
        return jsonify({"ok": False, "matches": [], "error": "Recherche vide"})

    # Si un VPSId est fourni, on l'ajoute comme recherche forte.
    search_q = wanted_vpsid if wanted_vpsid else q

    matches = pincabos_vpsdb_matches(search_q, rom)

    # Si recherche par VPSId ne retourne rien, fallback sur le nom.
    if wanted_vpsid and q:
        by_name = pincabos_vpsdb_matches(q, rom)
        seen = set()
        merged = []
        for m in matches + by_name:
            mid = str(m.get("id", "") or "")
            key = mid or str(m)
            if key in seen:
                continue
            seen.add(key)
            merged.append(m)
        matches = merged

    out = []
    for m in matches[:30]:
        title = str(m.get("title", "") or "")
        manufacturer = str(m.get("manufacturer", "") or "")
        year = str(m.get("year", "") or "")
        vpsid = str(m.get("id", "") or "")
        score = str(m.get("score", "") or "")
        assoc_rom = pincabos_match_rom_value(m, {"rom": rom})

        # Si VPSId demandé, boost visuel exact.
        if wanted_vpsid and vpsid.lower() == wanted_vpsid.lower():
            score = "1.0000"

        final_table_name = title
        if manufacturer and year:
            final_table_name = f"{title} ({manufacturer} {year})"

        out.append({
            "title": title,
            "manufacturer": manufacturer,
            "year": year,
            "id": vpsid,
            "vpsid": vpsid,
            "game_vpsid": str(m.get("game_vpsid", "") or ""),
            "parent_vpsid": str(m.get("parent_vpsid", "") or ""),
            "parent_version": str(m.get("parent_version", "") or ""),
            "version": str(m.get("version", "") or ""),
            "features": list(m.get("features", []) or []),
            "resource_type": str(m.get("resource_type", "") or ""),
            "score": score,
            "rom": assoc_rom,
            "final_table_name": final_table_name,
        })

    return jsonify({"ok": True, "matches": out})


@import_bp.route("/tools/import-table/analyze", methods=["POST"])
def tools_import_table_analyze():
    uploads = request.files.getlist("packages")
    uploads = [u for u in uploads if u and u.filename]

    # PINCABOS_SMART_IMPORT_REAL_RECEIVE_GUARD_V1
    expected_count_raw = str(
        request.form.get("expected_count", "") or ""
    ).strip()

    expected_count = 0

    if expected_count_raw:
        try:
            expected_count = max(
                0,
                int(expected_count_raw),
            )
        except (TypeError, ValueError):
            expected_count = 0

    if expected_count and expected_count != len(uploads):
        return page("Outils", f"""
<div class="card">
  <h2>Analyse Smart Import annulée</h2>

  <p class="bad">
    La carte affichait {expected_count} fichier(s),
    mais le serveur en a reçu {len(uploads)}.
  </p>

  <p>
    Aucun import incomplet n’a été analysé.
  </p>

  <p>
    <a class="button" href="/tools/import-table">
      Retour Smart Import
    </a>
  </p>
</div>
""")

    try:
        submitted_vpsids = json.loads(
            request.form.get("file_vpsids_json", "[]")
            or "[]"
        )

        if not isinstance(submitted_vpsids, list):
            submitted_vpsids = []

    except Exception:
        submitted_vpsids = []

    submitted_vpsids = [
        str(value or "").strip()
        for value in submitted_vpsids
    ]

    if len(submitted_vpsids) != len(uploads):
        return page("Outils", """
<div class="card">
  <h2>Analyse Smart Import annulée</h2>
  <p class="bad">La liste des VPS-ID ne correspond pas aux fichiers reçus.</p>
  <p>Aucun fichier n’a été installé.</p>
  <p><a class="button" href="/tools/import-table">Retour Smart Import</a></p>
</div>
""")

    any_vpsids_present = any(submitted_vpsids)
    all_vpsids_present = bool(uploads) and all(submitted_vpsids)

    try:
        resolved_resources = [
            (
                pincabos_smart_import_exact_resource(vpsid)
                if vpsid
                else None
            )
            for vpsid in submitted_vpsids
        ]
    except Exception as exc:
        return page("Outils", f"""
<div class="card">
  <h2>Analyse Smart Import annulée</h2>
  <p class="bad">{html.escape(str(exc))}</p>
  <p>La base VPSDB n’a pas validé tous les fichiers. Aucun fichier n’a été installé.</p>
  <p><a class="button" href="/tools/import-table">Retour Smart Import</a></p>
</div>
""")

    game_vpsids = {
        str(resource.get("game_vpsid", "") or "").strip()
        for resource in resolved_resources
        if resource
        and str(resource.get("game_vpsid", "") or "").strip()
    }

    if len(game_vpsids) > 1 or (
        any_vpsids_present and len(game_vpsids) != 1
    ):
        detail = ", ".join(sorted(game_vpsids)) or "aucun"
        return page("Outils", f"""
<div class="card">
  <h2>Analyse Smart Import annulée</h2>
  <p class="bad">Les VPS-ID ne pointent pas tous vers la même table.</p>
  <p>Jeux VPSDB détectés : <code>{html.escape(detail)}</code></p>
  <p>Aucun fichier n’a été installé.</p>
  <p><a class="button" href="/tools/import-table">Retour Smart Import</a></p>
</div>
""")

    if not uploads:
        return page("Outils", """
<div class="card">
  <h2>Analyse impossible</h2>
  <p class="bad">Aucun fichier reçu.</p>
  <p><a class="button" href="/tools">Retour Outils</a></p>
</div>
""")

    job_id = pincabos_import_safe_job_id()
    batch_dir = Path("/home/pinball/Downloads") / f"batch-{job_id}"
    batch_dir.mkdir(parents=True, exist_ok=True)

    # PINCABOS_SMART_IMPORT_CLIENT_MTIME_V1
    # Le mtime temporaire serveur n'est jamais une preuve
    # de fraîcheur. File.lastModified vient du navigateur.
    try:
        client_mtimes = json.loads(
            request.form.get(
                "file_mtimes_json",
                "[]",
            )
            or "[]"
        )

        if not isinstance(
            client_mtimes,
            list,
        ):
            client_mtimes = []

    except Exception:
        client_mtimes = []

    if len(client_mtimes) != len(uploads):
        # JS ancien/cache:
        # date inconnue -> SHA-256 côté importeur.
        client_mtimes = [0] * len(uploads)

    saved = []
    resource_rows = []
    stored_names = set()

    for upload_index, upload in enumerate(uploads):
        filename = secure_filename(
            upload.filename
        )

        if not filename:
            shutil.rmtree(batch_dir, ignore_errors=True)
            return page("Outils", """
<div class="card">
  <h2>Analyse Smart Import annulée</h2>
  <p class="bad">Un nom de fichier est invalide après sécurisation.</p>
  <p>Aucun fichier n’a été installé.</p>
  <p><a class="button" href="/tools/import-table">Retour Smart Import</a></p>
</div>
""")

        filename_key = filename.casefold()

        if filename_key in stored_names:
            shutil.rmtree(batch_dir, ignore_errors=True)
            return page("Outils", f"""
<div class="card">
  <h2>Analyse Smart Import annulée</h2>
  <p class="bad">Deux fichiers portent le même nom sécurisé : {html.escape(filename)}</p>
  <p>Renomme un des fichiers pour éviter tout écrasement temporaire.</p>
  <p><a class="button" href="/tools/import-table">Retour Smart Import</a></p>
</div>
""")

        stored_names.add(filename_key)

        dest = batch_dir / filename
        upload.save(dest)

        try:
            mtime_ms = float(
                client_mtimes[
                    upload_index
                ]
                or 0
            )

            if mtime_ms > 0:
                mtime_seconds = (
                    mtime_ms / 1000.0
                )

                os.utime(
                    dest,
                    (
                        mtime_seconds,
                        mtime_seconds,
                    ),
                )

            else:
                os.utime(
                    dest,
                    (0, 0),
                )

        except Exception:
            try:
                os.utime(
                    dest,
                    (0, 0),
                )
            except Exception:
                pass

        saved.append(str(dest))

        # Aucun VPS-ID fourni dans le lot: le moteur historique reste la
        # source de vérité (VPX anchor, détection et sélection manuelle).
        if not any_vpsids_present:
            continue

        resolved_resource = resolved_resources[upload_index]
        archive_members = (
            pincabos_list_archive_files(dest)
            if dest.suffix.lower() in {".zip", ".rar", ".7z", ".pincabos"}
            else []
        )
        contains_vpu_patch = (
            dest.suffix.lower() == ".dif"
            or any(
                str(member).lower().endswith(".dif")
                for member in archive_members
            )
        )
        contains_vpx = (
            dest.suffix.lower() == ".vpx"
            or any(
                str(member).lower().endswith(".vpx")
                for member in archive_members
            )
        )

        # Un .dif reste l'exception stricte: son VPS-ID exact est nécessaire
        # afin de conserver parentId + parent_version et la sécurité vpxtool.
        if contains_vpu_patch and not resolved_resource:
            shutil.rmtree(batch_dir, ignore_errors=True)
            return page("Outils", f"""
<div class="card">
  <h2>Analyse Smart Import annulée</h2>
  <p class="bad">Le fichier {html.escape(filename)} contient un patch VPU Remix .dif. Son VPS-ID exact est requis pour valider le parent et sa version.</p>
  <p>Les autres fichiers peuvent rester sans VPS-ID.</p>
  <p>Aucun fichier n’a été installé.</p>
  <p><a class="button" href="/tools/import-table">Retour Smart Import</a></p>
</div>
""")

        if resolved_resource:
            resource = dict(resolved_resource)
        else:
            resource = {
                "vpsid": "",
                "game_vpsid": next(iter(game_vpsids)),
                "resource_type": "unresolved",
                "resource_key": "",
                "association": "inferred_game",
            }

        if (
            contains_vpu_patch
            and resource.get("resource_type") != "tableFile"
        ):
            shutil.rmtree(batch_dir, ignore_errors=True)
            return page("Outils", f"""
<div class="card">
  <h2>Analyse Smart Import annulée</h2>
  <p class="bad">Le fichier {html.escape(filename)} contient un patch .dif, mais son VPS-ID n’est pas un tableFile.</p>
  <p>Aucun fichier n’a été installé.</p>
  <p><a class="button" href="/tools/import-table">Retour Smart Import</a></p>
</div>
""")

        resource.update({
            "original_name": str(upload.filename or ""),
            "stored_name": filename,
            "sha256": pincabos_smart_import_file_sha256(dest),
            "size": dest.stat().st_size,
            "client_mtime_ms": client_mtimes[upload_index],
            "contains_vpu_patch": contains_vpu_patch,
            "contains_vpx": contains_vpx,
        })
        resource_rows.append(resource)

    if not any_vpsids_present:
        if request.headers.get("X-PCOS-Async") == "1":
            return jsonify({
                "ok": True,
                "next": "/tools/import-table/analyze-run?batch=" + batch_dir.name,
            })

        return _pcos_smart_analyze_render(batch_dir, saved)

    patch_resources = [
        resource
        for resource in resource_rows
        if resource.get("contains_vpu_patch")
    ]

    if len(patch_resources) > 1:
        shutil.rmtree(batch_dir, ignore_errors=True)
        return page("Outils", """
<div class="card">
  <h2>Analyse Smart Import annulée</h2>
  <p class="bad">Un seul patch VPU Remix .dif est permis par import.</p>
  <p>Aucun fichier n’a été installé.</p>
  <p><a class="button" href="/tools/import-table">Retour Smart Import</a></p>
</div>
""")

    vpx_resources = [
        resource
        for resource in resource_rows
        if resource.get("contains_vpx")
    ]

    if len(vpx_resources) > 1:
        shutil.rmtree(batch_dir, ignore_errors=True)
        return page("Outils", """
<div class="card">
  <h2>Analyse Smart Import annulée</h2>
  <p class="bad">Plusieurs sources VPX sont présentes dans le même lot. Smart Import refuse de choisir arbitrairement une table principale.</p>
  <p>Conserve un seul VPX principal dans ce lot, ou importe les variantes séparément.</p>
  <p>Aucun fichier n’a été installé.</p>
  <p><a class="button" href="/tools/import-table">Retour Smart Import</a></p>
</div>
""")

    table_resources = [
        resource
        for resource in resource_rows
        if resource.get("resource_type") == "tableFile"
    ]

    primary_table = patch_resources[0] if patch_resources else None

    if primary_table is None and len(table_resources) == 1:
        primary_table = table_resources[0]

    if primary_table is None and len(table_resources) > 1:
        table_ids = {
            str(resource.get("vpsid", "") or "").strip().casefold()
            for resource in table_resources
        }
        children = [
            resource
            for resource in table_resources
            if str(resource.get("parent_vpsid", "") or "").strip().casefold()
            in table_ids
        ]

        if len(children) == 1:
            primary_table = children[0]
        else:
            shutil.rmtree(batch_dir, ignore_errors=True)
            return page("Outils", """
<div class="card">
  <h2>Analyse Smart Import annulée</h2>
  <p class="bad">Plusieurs tableFile VPSDB sont présents et la table principale est ambiguë.</p>
  <p>Aucun fichier n’a été installé.</p>
  <p><a class="button" href="/tools/import-table">Retour Smart Import</a></p>
</div>
""")

    first_resource = next(
        (
            resource
            for resource in resource_rows
            if str(resource.get("vpsid", "") or "").strip()
        ),
        resource_rows[0],
    )
    detected_rom = next((
        str(resource.get("version", "") or "").strip()
        for resource in resource_rows
        if resource.get("resource_type") == "romFile"
        and str(resource.get("version", "") or "").strip()
    ), "")

    resource_manifest = {
        "format": "PinCabOS Smart Import resources",
        "format_version": 2,
        "association_mode": (
            "complete_vpsid"
            if all_vpsids_present
            else "partial_vpsid"
        ),
        "game_vpsid": next(iter(game_vpsids)),
        "title": str(first_resource.get("title", "") or "").strip(),
        "manufacturer": str(first_resource.get("manufacturer", "") or "").strip(),
        "year": str(first_resource.get("year", "") or "").strip(),
        "final_table_name": str(first_resource.get("final_table_name", "") or "").strip(),
        "rom": detected_rom,
        "primary_table_vpsid": (
            str(primary_table.get("vpsid", "") or "").strip()
            if primary_table
            else ""
        ),
        "parent_vpsid": (
            str(primary_table.get("parent_vpsid", "") or "").strip()
            if primary_table
            else ""
        ),
        "parent_version": (
            str(primary_table.get("parent_version", "") or "").strip()
            if primary_table
            else ""
        ),
        "target_version": (
            str(primary_table.get("version", "") or "").strip()
            if primary_table
            else ""
        ),
        "resources": resource_rows,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    resource_manifest_path = (
        pincabos_smart_import_resource_manifest_path(batch_dir)
    )
    resource_manifest_tmp = resource_manifest_path.with_suffix(".tmp")
    resource_manifest_tmp.write_text(
        json.dumps(resource_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(resource_manifest_tmp, resource_manifest_path)

    if request.headers.get("X-PCOS-Async") == "1":
        return jsonify({
            "ok": True,
            "next": "/tools/import-table/analyze-run?batch=" + batch_dir.name,
        })

    return _pcos_smart_analyze_render(batch_dir, saved)


@import_bp.route("/tools/import-table/analyze-run", methods=["GET"])
def tools_import_table_analyze_run():
    name = str(request.args.get("batch", "") or "")
    if not re.fullmatch(r"batch-[A-Za-z0-9-]+", name):
        return page("Outils", '<div class="card"><h2>Smart Import</h2><p class="bad">R\u00e9f\u00e9rence de batch invalide.</p><p><a class="button" href="/tools/import-table">Retour</a></p></div>')
    batch_dir = Path("/home/pinball/Downloads") / name
    if not batch_dir.is_dir():
        return page("Outils", '<div class="card"><h2>Smart Import</h2><p class="bad">Batch introuvable ou expir\u00e9.</p><p><a class="button" href="/tools/import-table">Retour</a></p></div>')
    saved = sorted(
        str(p)
        for p in batch_dir.iterdir()
        if p.is_file()
        and p.name != PINCABOS_SMART_IMPORT_RESOURCE_MANIFEST
    )
    return _pcos_smart_analyze_render(batch_dir, saved)


def _pcos_smart_analyze_render(batch_dir, saved):
    manifest_response = pincabos_try_manifest_import_from_saved_batch(batch_dir)
    if manifest_response is not None:
        return manifest_response

    try:
        resource_manifest = (
            pincabos_smart_import_load_resource_manifest(batch_dir)
        )
    except Exception as exc:
        return page("Outils", f"""
<div class="card">
  <h2>Analyse Smart Import annulée</h2>
  <p class="bad">{html.escape(str(exc))}</p>
  <p><a class="button" href="/tools/import-table">Retour Smart Import</a></p>
</div>
""")

    detected = pincabos_detect_batch(batch_dir)

    if resource_manifest:
        detected["table_name"] = str(
            resource_manifest.get("final_table_name", "")
            or resource_manifest.get("title", "")
            or detected.get("table_name", "")
        ).strip()

        if resource_manifest.get("rom"):
            detected["rom"] = str(resource_manifest.get("rom") or "").strip()

    # Validation directe des fichiers réellement reçus.
    received_paths = [
        Path(file_path)
        for file_path in saved
    ]

    direct_vpx = [
        file_path
        for file_path in received_paths
        if file_path.suffix.lower() == ".vpx"
    ]

    direct_b2s = [
        file_path
        for file_path in received_paths
        if file_path.name.lower().endswith(".directb2s")
    ]

    direct_pov = [
        file_path
        for file_path in received_paths
        if file_path.suffix.lower() == ".pov"
    ]

    direct_ini = [
        file_path
        for file_path in received_paths
        if file_path.suffix.lower() == ".ini"
    ]

    direct_vbs = [
        file_path
        for file_path in received_paths
        if file_path.suffix.lower() == ".vbs"
    ]

    detected_name = str(
        detected.get("table_name", "") or ""
    ).strip()

    false_batch_name = (
        detected_name == batch_dir.name
        or detected_name.lower().startswith("batch-")
    )

    if direct_vpx:
        detected["main_vpx"] = (
            detected.get("main_vpx")
            or direct_vpx[0].name
        )

        if not detected_name or false_batch_name:
            detected["table_name"] = direct_vpx[0].stem

    elif false_batch_name:
        detected["table_name"] = ""

    if direct_b2s:
        detected["has_b2s"] = True

    if direct_pov:
        detected["has_pov"] = True

    if direct_ini:
        detected["has_ini"] = True

    if direct_vbs:
        detected["has_vbs"] = True

    matches = pincabos_vpsdb_matches(
        detected.get("table_name", ""),
        detected.get("rom", ""),
    )

    if resource_manifest:
        matches = []

    # Le nom d'un .dif ne prouve pas quel tableFile VPSDB il représente.
    # Une association générique au jeu perdrait parentId et pourrait choisir
    # une mauvaise version source. Pour un patch, l'utilisateur doit donc
    # sélectionner le VPSId exact du mod dans la recherche dédiée.
    if detected.get("has_vpu_patch"):
        matches = []

    options = ""
    for m in matches[:10]:
        title = str(m.get("title", ""))
        manufacturer = str(m.get("manufacturer", ""))
        year = str(m.get("year", ""))
        vpsid = str(m.get("id", ""))
        score = str(m.get("score", ""))

        final_table_name = title
        if manufacturer and year:
            final_table_name = f"{title} ({manufacturer} {year})"

        assoc_rom = pincabos_match_rom_value(m, detected)

        value = html.escape(json.dumps({
            "mode": "vpsdb",
            "title": title,
            "manufacturer": manufacturer,
            "year": year,
            "vpsid": vpsid,
            "game_vpsid": str(m.get("game_vpsid", "") or ""),
            "parent_vpsid": str(m.get("parent_vpsid", "") or ""),
            "parent_version": str(m.get("parent_version", "") or ""),
            "version": str(m.get("version", "") or ""),
            "features": list(m.get("features", []) or []),
            "resource_type": str(m.get("resource_type", "") or ""),
            "rom": assoc_rom,
            "final_table_name": final_table_name,
        }, ensure_ascii=False))

        version_label = str(m.get("version", "") or "").strip()
        parent_label = str(m.get("parent_vpsid", "") or "").strip()
        label = html.escape(
            f"{title} — {manufacturer} — {year} — VPSId {vpsid}"
            + (f" — version {version_label}" if version_label else "")
            + (f" — parent {parent_label}" if parent_label else "")
            + f" — score {score}"
        )
        options += f'<option value="{value}">{label}</option>\\n'

    if not options.strip():
        if detected.get("has_vpu_patch"):
            options = (
                '<option value="">Patch .dif : recherchez le VPSId exact du mod</option>'
            )
        else:
            options = '<option value="">Aucune association auto-détectée VPSdb</option>'

    # PINCABOS_IMPORT_TECH_GO_COLORS_V1
    technical_items = [
        (
            "Table détectée",
            bool(detected.get("table_name")),
            detected.get("table_name", ""),
        ),
        (
            "Fichier VPX principal",
            bool(detected.get("main_vpx")),
            detected.get("main_vpx", ""),
        ),
        (
            "Patch VPU Remix (.dif)",
            bool(detected.get("has_vpu_patch")),
            detected.get("vpu_patch_file", ""),
        ),
        (
            "ROM détectée",
            bool(detected.get("rom")),
            detected.get("rom", ""),
        ),
        ("Archive ROM", bool(detected.get("has_rom")), ""),
        ("Backglass B2S", bool(detected.get("has_b2s")), ""),
        ("Fichier POV", bool(detected.get("has_pov")), ""),
        ("Fichier INI", bool(detected.get("has_ini")), ""),
        ("Script VBS", bool(detected.get("has_vbs")), ""),
        ("AltSound", bool(detected.get("has_altsound")), ""),
        ("AltColor / Serum", bool(detected.get("has_altcolor")), ""),
        ("PuP-Pack", bool(detected.get("has_puppack")), ""),
        ("UltraDMD", bool(detected.get("has_ultradmd")), ""),
    ]

    technical_rows = []

    for label, present, value in technical_items:
        status_html = (
            '<span class="pco-import-status '
            'pco-import-status-go">[✓] GO</span>'
            if present
            else
            '<span class="pco-import-status '
            'pco-import-status-off">[ ] NON DÉTECTÉ</span>'
        )

        value_html = (
            f'<span class="pco-import-tech-value">'
            f'{html.escape(str(value))}</span>'
            if value
            else
            '<span class="pco-import-tech-value '
            'pco-import-tech-empty">—</span>'
        )

        technical_rows.append(
            '<div class="pco-import-tech-row">'
            f'<span class="pco-import-tech-label">'
            f'{html.escape(str(label))}</span>'
            f'{status_html}'
            f'{value_html}'
            '</div>'
        )

    detected_html = "".join(technical_rows)

    file_rows = []

    resources_by_name = {
        str(resource.get("stored_name", "") or ""): resource
        for resource in resource_manifest.get("resources", [])
        if isinstance(resource, dict)
    }

    for file_path in saved:
        file_name = Path(file_path).name
        resource = resources_by_name.get(file_name, {})
        resource_detail = ""

        if resource:
            resource_vpsid = str(resource.get("vpsid", "") or "").strip()
            if resource_vpsid:
                detail_parts = [
                    f"VPS-ID {resource_vpsid}",
                    str(resource.get("resource_type", "") or ""),
                ]
            else:
                detail_parts = [
                    "VPS-ID non fourni",
                    "routage par ancre VPX/VPSDB",
                ]
            version = str(resource.get("version", "") or "").strip()
            if version:
                detail_parts.append(f"version {version}")

            resource_detail = (
                '<small class="pco-import-file-resource">'
                + html.escape(" · ".join(filter(None, detail_parts)))
                + "</small>"
            )

        file_rows.append(
            '<div class="pco-import-file-row">'
            '<span class="pco-import-file-go">[✓] GO</span>'
            f'<span class="pco-import-file-path">'
            f'<strong>{html.escape(file_name)}</strong>'
            f'{resource_detail}</span>'
            '</div>'
        )

    files_html = "".join(file_rows) or (
        '<div class="pco-import-file-row">'
        '<span class="pco-import-status '
        'pco-import-status-off">[ ] AUCUN</span>'
        '<span class="pco-import-file-path">'
        'Aucun fichier détecté</span>'
        '</div>'
    )

    default_title = html.escape(detected.get("table_name", ""))
    default_rom = html.escape(detected.get("rom", ""))
    legacy_association_style = (
        "display:none;"
        if resource_manifest
        else ""
    )
    resource_install_html = ""
    existing_target_html = ""

    partial_resource_manifest = (
        isinstance(resource_manifest, dict)
        and resource_manifest.get("association_mode") == "partial_vpsid"
    )
    needs_existing_target = (
        not detected.get("main_vpx")
        and not detected.get("has_vpu_patch")
        and (
            not resource_manifest
            or partial_resource_manifest
        )
    )

    if needs_existing_target:
        table_options = []

        try:
            tables_root = Path(pincabos_vpx_tables_dir()).resolve()
            candidates = sorted(
                tables_root.iterdir(),
                key=lambda item: item.name.casefold(),
            )

            for candidate in candidates:
                if (
                    not candidate.is_dir()
                    or candidate.is_symlink()
                    or candidate.name.startswith(".")
                ):
                    continue

                installed_vpxs = [
                    item
                    for item in candidate.glob("*.vpx")
                    if item.is_file() and not item.is_symlink()
                ]

                if len(installed_vpxs) != 1:
                    continue

                value = html.escape(candidate.name, quote=True)
                table_options.append(
                    f'<option value="{value}">{value}</option>'
                )

        except Exception:
            table_options = []

        if table_options:
            options_html = (
                '<option value="">Choisir une table installée</option>'
                + "".join(table_options)
            )

            existing_target_html = f"""
<div class="card" style="margin-top:20px; border-color:rgba(255,176,0,.62);">
  <h2>Choisir la table de destination</h2>
  <p>
    Smart Import ne peut pas associer tout ce lot avec certitude.
    Choisis la table installée qui doit le recevoir. Les VPS-ID déjà fournis,
    le routage et le renommage Smart Import existants seront conservés.
  </p>
  <form action="/tools/import-table/install" method="post"
        onsubmit="document.getElementById('installSpinnerExisting').style.display='block';">
    <input type="hidden" name="batch_dir" value="{html.escape(str(batch_dir))}">
    <input type="hidden" name="import_mode" value="existing">
    <label>Table de destination</label><br>
    <select name="existing_table" required style="width:95%; padding:8px; margin:8px 0;">
      {options_html}
    </select><br>
    <button class="button" type="submit">Installer dans cette table</button>
    <div id="installSpinnerExisting" class="card" style="display:none; margin-top:14px;">
      <h3>Installation en cours...</h3>
      <p>Le VPX installé est conservé; Smart Import route les fichiers reçus.</p>
    </div>
  </form>
</div>
"""
        else:
            existing_target_html = """
<div class="card" style="margin-top:20px;">
  <h2>Choisir la table de destination</h2>
  <p class="warn">Aucune table installée avec un VPX unique et fiable n’est disponible.</p>
</div>
"""

    if resource_manifest and not needs_existing_target:
        resource_count = len(resource_manifest.get("resources", []))
        provided_count = sum(
            1
            for resource in resource_manifest.get("resources", [])
            if isinstance(resource, dict)
            and str(resource.get("vpsid", "") or "").strip()
        )
        game_vpsid = html.escape(
            str(resource_manifest.get("game_vpsid", "") or "")
        )
        target_name = html.escape(
            str(
                resource_manifest.get("final_table_name", "")
                or resource_manifest.get("title", "")
                or ""
            )
        )
        if partial_resource_manifest:
            association_title = "Association mixte VPSDB + ancre Smart Import"
            association_summary = (
                f"{provided_count}/{resource_count} VPS-ID fourni(s) et validé(s) pour "
                f"<strong>{target_name}</strong> — jeu VPSDB <code>{game_vpsid}</code>."
            )
            routing_text = (
                "Les VPS-ID fournis gardent la priorité. Les fichiers sans ID "
                "restent liés au même jeu et sont classés par le moteur Smart Import."
            )
        else:
            association_title = "Association VPSDB validée par fichier"
            association_summary = (
                f"{resource_count} fichier(s) validé(s) pour "
                f"<strong>{target_name}</strong> — jeu VPSDB <code>{game_vpsid}</code>."
            )
            routing_text = (
                "PinCabOS utilisera le type VPSDB de chaque ID pour viser la table "
                "et conservera ces ressources dans le manifeste de la table."
            )

        resource_install_html = f"""
<div class="card" style="margin-top:20px; border-color:rgba(69,229,139,.55);">
  <h2>{association_title}</h2>
  <p class="ok">{association_summary}</p>
  <p>{routing_text}</p>
  <form action="/tools/import-table/install" method="post"
        onsubmit="document.getElementById('installSpinnerResources').style.display='block';">
    <input type="hidden" name="batch_dir" value="{html.escape(str(batch_dir))}">
    <input type="hidden" name="import_mode" value="resources">
    <button class="button" type="submit">Installer le lot analysé</button>
    <div id="installSpinnerResources" class="card" style="display:none; margin-top:14px;">
      <h3>Installation en cours...</h3>
      <p>Routage Smart Import, transaction, manifeste et validation.</p>
    </div>
  </form>
</div>
"""

    body = f"""
<style>
  .pco-import-files,
  .pco-import-details {{
    background:rgba(3,1,7,.94);
    border:1px solid rgba(255,166,0,.78);
    border-radius:12px;
    overflow:hidden;
    box-shadow:inset 0 0 0 1px rgba(255,255,255,.02);
  }}

  .pco-import-file-row,
  .pco-import-tech-row {{
    display:grid;
    align-items:center;
    gap:14px;
    padding:10px 14px;
    border-bottom:1px solid rgba(255,255,255,.075);
  }}

  .pco-import-file-row:last-child,
  .pco-import-tech-row:last-child {{
    border-bottom:0;
  }}

  .pco-import-file-row {{
    grid-template-columns:92px minmax(0,1fr);
  }}

  .pco-import-tech-row {{
    grid-template-columns:minmax(170px,230px) 155px minmax(0,1fr);
  }}

  .pco-import-status,
  .pco-import-file-go {{
    font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
    font-weight:900;
    letter-spacing:.03em;
    white-space:nowrap;
  }}

  .pco-import-status-go,
  .pco-import-file-go {{
    color:#45e58b;
    text-shadow:0 0 12px rgba(69,229,139,.28);
  }}

  .pco-import-status-off {{
    color:#858997;
  }}

  .pco-import-tech-label {{
    color:#ffb300;
    font-weight:800;
  }}

  .pco-import-tech-value,
  .pco-import-file-path {{
    min-width:0;
    color:#f2f3f5;
    overflow-wrap:anywhere;
    word-break:break-word;
    font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  }}

  .pco-import-tech-empty {{
    color:#686d79;
  }}

  .pco-import-file-path strong,
  .pco-import-file-resource {{
    display:block;
  }}

  .pco-import-file-resource {{
    margin-top:4px;
    color:#ffb04a;
    font-size:12px;
  }}

  @media (max-width:900px) {{
    .pco-import-tech-row {{
      grid-template-columns:1fr;
      gap:5px;
    }}

    .pco-import-file-row {{
      grid-template-columns:1fr;
      gap:5px;
    }}
  }}
</style>

<div class="card">
  <h2>Analyse Smart Import terminée</h2>

  <h3>Table détectée</h3>
  <p><strong>{html.escape(detected.get("table_name", ""))}</strong></p>

  <h3>ROM détectée</h3>
  <p><strong>{html.escape(detected.get("rom", "")) or "Aucune ROM détectée"}</strong></p>

  <h3>Fichiers détectés</h3>
  <div class="pco-import-files">{files_html}</div>

  <h3>Détails techniques</h3>
  <div class="pco-import-details">{detected_html}</div>
</div>

{resource_install_html}

{existing_target_html}

<div class="card" style="margin-top:20px;{legacy_association_style}">
  <h2>Association VPinFE / VPSdb</h2>

  <form action="/tools/import-table/install" method="post" onsubmit="document.getElementById('installSpinner').style.display='block';">
    <input type="hidden" name="batch_dir" value="{html.escape(str(batch_dir))}">
    <input type="hidden" name="import_mode" id="importMode" value="auto">

    <div class="card" style="margin-top:12px; border-color:rgba(255,122,0,.45);">
      <h3>1. Détection automatique VPSdb</h3>
      <p>PinCabOS propose ici les résultats VPSdb trouvés automatiquement.</p>

      <label>Choix auto-détecté VPSdb</label><br>
      <select name="association" id="autoAssociationSelect" style="width:95%; padding:8px; margin:8px 0;">
        {options}
      </select><br>

      <button class="button" type="submit" onclick="document.getElementById('importMode').value='auto';">
        Importer ce choix auto-détecté
      </button>
    </div>

    <div class="card" style="margin-top:20px; border-color:rgba(95,42,145,.55);">
      <h3>2. Recherche manuelle dans VPSdb</h3>
      <p>Recherche par nom ou par VPSId. Ensuite sélectionne le bon résultat et importe-le.</p>

      <label>Nom recherché</label><br>
      <input id="vpsdbSearchQuery" value="{default_title}" placeholder="Exemple : The Leprechaun King" style="width:90%; padding:8px;"><br><br>

      <label>VPSId optionnel</label><br>
      <input id="vpsdbSearchId" value="" placeholder="Exemple : VAx9weFV" style="width:90%; padding:8px;"><br><br>

      <button class="button secondary" type="button" id="vpsdbSearchButton" onclick="window.pincabosVpsdbSearch && window.pincabosVpsdbSearch();">
        Rechercher VPSdb
      </button>
      <span id="vpsdbSearchSpinner" style="display:none; margin-left:10px;">🔄</span>
      <span id="vpsdbSearchStatus" style="margin-left:10px; opacity:.85;"></span>

      <br><br>
      <label>Résultat de recherche VPSdb</label><br>
      <select name="search_association" id="searchAssociationSelect" style="width:95%; padding:8px; margin:8px 0;">
        <option value="">Aucun résultat de recherche sélectionné</option>
      </select><br>

      <button class="button" type="submit" onclick="document.getElementById('importMode').value='search';">
        Importer le résultat recherché
      </button>
    </div>

    <div class="card" style="margin-top:20px; border-color:rgba(255,122,0,.55); background:rgba(255,122,0,.06);">
      <h3>3. Import manuel complet</h3>
      <p>
        Si rien ne correspond dans VPSdb, remplis ces champs et importe la table avec tes informations.
        Exemple : <code>Demo Table (PinCabOS 2026)</code>.
      </p>

      <label>Nom de table VPinFE</label><br>
      <input name="manual_title" id="manualTitleInput" value="{default_title}" style="width:90%; padding:8px;" placeholder="Exemple : Demo Table (PinCabOS 2026)"><br><br>

      <label>Manufacturier</label><br>
      <input name="manual_manufacturer" id="manualManufacturerInput" value="" placeholder="Exemple : PinCabOS, Williams, Original, Stern" style="width:90%; padding:8px;"><br><br>

      <label>Année</label><br>
      <input name="manual_year" id="manualYearInput" value="" placeholder="Exemple : 2026" style="width:90%; padding:8px;"><br><br>

      <label>ROM</label><br>
      <input name="manual_rom" id="manualRomInput" value="{default_rom}" placeholder="Exemple : hurr_l2 ou laisser vide si aucune ROM" style="width:90%; padding:8px;"><br><br>

      <button class="button" type="submit" onclick="document.getElementById('importMode').value='manual';">
        Importer manuellement
      </button>
    </div>

    <script>
      (function() {{
        window.pincabosVpsdbSearch = async function() {{
          const searchQ = document.getElementById("vpsdbSearchQuery");
          const searchId = document.getElementById("vpsdbSearchId");
          const searchStatus = document.getElementById("vpsdbSearchStatus");
          const spinner = document.getElementById("vpsdbSearchSpinner");
          const searchSelect = document.getElementById("searchAssociationSelect");

          if (!searchSelect) {{
            alert("Erreur: champ résultat VPSdb introuvable.");
            return;
          }}

          const q = encodeURIComponent(searchQ ? searchQ.value.trim() : "");
          const vpsid = encodeURIComponent(searchId ? searchId.value.trim() : "");

          if (!q && !vpsid) {{
            searchSelect.innerHTML = '<option value="">Entre un nom ou un VPSId</option>';
            if (searchStatus) searchStatus.textContent = "Recherche vide";
            return;
          }}

          if (spinner) spinner.style.display = "inline-block";
          if (searchStatus) searchStatus.textContent = "Recherche en cours...";
          searchSelect.innerHTML = '<option value="">Recherche en cours...</option>';

          try {{
            const url = "/api/import/vpsdb-search?q=" + q + "&vpsid=" + vpsid + "&_=" + Date.now();
            const resp = await fetch(url, {{
              method: "GET",
              cache: "no-store",
              headers: {{ "Accept": "application/json" }}
            }});

            const raw = await resp.text();
            const data = JSON.parse(raw);

            searchSelect.innerHTML = "";

            if (!data.ok || !data.matches || data.matches.length === 0) {{
              searchSelect.innerHTML = '<option value="">Aucun résultat VPSdb trouvé</option>';
              if (searchStatus) searchStatus.textContent = "Aucun résultat";
              return;
            }}

            const empty = document.createElement("option");
            empty.value = "";
            empty.textContent = "Choisir un résultat de recherche VPSdb";
            searchSelect.appendChild(empty);

            data.matches.forEach(function(m) {{
              const opt = document.createElement("option");
              opt.value = JSON.stringify({{
                mode: "vpsdb",
                title: m.title || "",
                manufacturer: m.manufacturer || "",
                year: m.year || "",
                vpsid: m.id || "",
                game_vpsid: m.game_vpsid || "",
                parent_vpsid: m.parent_vpsid || "",
                parent_version: m.parent_version || "",
                version: m.version || "",
                features: m.features || [],
                resource_type: m.resource_type || "",
                rom: m.rom || "",
                final_table_name: m.final_table_name || ""
              }});

              opt.textContent =
                (m.title || "") + " — " +
                (m.manufacturer || "") + " — " +
                (m.year || "") + " — VPSId " +
                (m.id || "") +
                (m.version ? " — version " + m.version : "") +
                (m.parent_vpsid ? " — parent " + m.parent_vpsid : "") +
                " — score " +
                (m.score || "");

              searchSelect.appendChild(opt);
            }});

            if (searchStatus) searchStatus.textContent = data.matches.length + " résultat(s)";
          }} catch(e) {{
            searchSelect.innerHTML = '<option value="">Erreur recherche VPSdb</option>';
            if (searchStatus) searchStatus.textContent = "Erreur recherche";
            console.log("Erreur recherche VPSdb:", e);
          }} finally {{
            if (spinner) spinner.style.display = "none";
          }}
        }};
      }})();
    </script>

    <div id="installSpinner" class="card" style="display:none; margin-top:14px;">
      <h3>Installation en cours...</h3>
      <p>PinCabOS installe les fichiers, crée le .info compatible VPinFE et nettoie les temporaires.</p>
    </div>
  </form>

  <p style="margin-top:14px;"><a class="button secondary" href="/tools">Annuler</a></p>
</div>
"""
    return page("Outils", body)


def pincabos_safe_manifest_relpath(rel):
    rel = str(rel or "").replace("\\", "/").strip()
    if not rel:
        return None
    if rel.startswith("/") or rel.startswith("../") or "/../" in rel or rel == "..":
        return None
    return rel


def pincabos_manifest_dest_path(rel):
    """
    Destination import manifest PinCabOS v2:
    tout reste dans /opt/pincabos/tables/<table>/...
    Cette fonction garde un fallback pour les vieux manifests, mais évite
    les dossiers legacy globaux.
    """
    rel = pincabos_safe_manifest_relpath(rel)
    if not rel:
        return None

    parts = Path(rel).parts
    if not parts:
        return None

    # Manifest v2 exporte directement:
    # table/, media/, music/, roms/, pupvideos/, ...
    standard_dirs = {
        "table", "media", "music", "roms", "pupvideos", "altcolor",
        "altsound", "dmd", "b2s", "scripts", "config", "docs", "extras"
    }

    # La vraie table est déterminée dans pincabos_import_from_manifest_dir()
    # via PINCABOS_MANIFEST_IMPORT_TABLE_DIR.
    table_root = globals().get("PINCABOS_MANIFEST_IMPORT_TABLE_DIR", None)
    if table_root:
        table_root = Path(table_root)

        if parts[0] in standard_dirs:
            return table_root / rel

        # Vieux manifest avec Tables/<table>/...
        if len(parts) >= 3 and parts[0].lower() == "tables":
            return table_root / Path(*parts[2:])

        # Vieux manifest avec PupVideos/xxx, PinMAME/roms/xxx, etc.
        low0 = parts[0].lower()
        if low0 in ["pupvideos"]:
            return table_root / "pupvideos" / Path(*parts[1:])
        if low0 in ["ultradmd", "flexdmd"]:
            return table_root / "dmd" / Path(*parts[1:])
        if low0 == "pinmame" and len(parts) >= 2:
            low1 = parts[1].lower()
            if low1 == "roms":
                return table_root / "roms" / Path(*parts[2:])
            if low1 == "altcolor":
                return table_root / "altcolor" / Path(*parts[2:])
            if low1 == "altsound":
                return table_root / "altsound" / Path(*parts[2:])

        return table_root / "extras" / rel

    # Fallback ultra safe.
    return Path("/opt/pincabos/imported") / rel


def pincabos_find_manifest_root(extract_dir):
    extract_dir = Path(extract_dir)

    direct = extract_dir / "pincabos-export-manifest.json"
    if direct.exists():
        return extract_dir, direct

    matches = list(extract_dir.rglob("pincabos-export-manifest.json"))
    if not matches:
        return None, None

    manifest = matches[0]
    return manifest.parent, manifest


def pincabos_manifest_table_folder_from_archive(archive_path):
    """
    Lit le manifest d'un .PinCabOs/.zip/.7z/.rar et retourne le nom de table demandé.
    Retourne ("", "") si aucun manifest valide n'est trouvé.
    """
    archive_path = Path(archive_path)

    with tempfile.TemporaryDirectory(prefix="pincabos-manifest-preview-") as td:
        extract_dir = Path(td) / "extract"
        extract_dir.mkdir(parents=True, exist_ok=True)

        r7 = subprocess.run(
            ["7z", "x", "-y", f"-o{str(extract_dir)}", str(archive_path)],
            capture_output=True,
            text=True,
            timeout=1800,
            check=False,
        )

        if r7.returncode != 0:
            return "", ""

        root, manifest_path = pincabos_find_manifest_root(extract_dir)
        if not manifest_path:
            return "", ""

        try:
            manifest = json.loads(manifest_path.read_text(errors="replace"))
        except Exception:
            return "", str(manifest_path)

        if manifest.get("format") != "PinCabOS table export":
            return "", str(manifest_path)

        table_folder = str(manifest.get("table_folder") or "").strip()
        if not table_folder:
            table_folder = Path(root).name or "Imported Table"

        table_folder = pincabos_standard_table_folder_name(table_folder)
        return table_folder, str(manifest_path)


def pincabos_manifest_import_conflict_page(batch_dir, archive_path, table_folder):
    table_root = pincabos_vpx_tables_dir() / table_folder

    suggested = table_folder
    i = 2
    while (pincabos_vpx_tables_dir() / suggested).exists():
        suggested = f"{table_folder} ({i})"
        i += 1

    return page("Import PinCabOS", f"""
<div class="card">
  <h2>Table déjà présente</h2>
  <p class="warn">
    Le package <code>.PinCabOs</code> contient la table
    <strong>{esc(table_folder)}</strong>, mais ce dossier existe déjà.
  </p>

  <p><strong>Dossier existant :</strong> <code>{esc(str(table_root))}</code></p>

  <div class="card" style="margin-top:14px; border-color:rgba(255,122,0,.45);">
    <h3>Remplacer la table existante</h3>
    <p>Cette option supprime l’ancien dossier de table, puis restaure le package .PinCabOs.</p>

    <form action="/tools/import-table/manifest-conflict" method="post" onsubmit="document.getElementById('replaceSpinner').style.display='inline-block';">
      <input type="hidden" name="batch_dir" value="{esc(str(batch_dir))}">
      <input type="hidden" name="archive_path" value="{esc(str(archive_path))}">
      <input type="hidden" name="conflict_action" value="replace">
      <button class="button" type="submit">Remplacer la table existante</button>
      <span id="replaceSpinner" style="display:none; margin-left:10px; vertical-align:middle;"><svg width="20" height="20" viewBox="0 0 50 50" style="vertical-align:middle;"><circle cx="25" cy="25" r="20" fill="none" stroke="rgba(255,255,255,0.25)" stroke-width="6"></circle><path d="M25 5 A20 20 0 0 1 45 25" fill="none" stroke="#ff7a00" stroke-width="6" stroke-linecap="round"><animateTransform attributeName="transform" type="rotate" from="0 25 25" to="360 25 25" dur="0.75s" repeatCount="indefinite"/></path></svg></span>
    </form>
  </div>

  <div class="card" style="margin-top:14px; border-color:rgba(95,42,145,.55);">
    <h3>Installer sous un nouveau nom</h3>
    <p>Cette option garde la table existante et installe le package dans un nouveau dossier.</p>

    <form action="/tools/import-table/manifest-conflict" method="post" onsubmit="document.getElementById('renameSpinner').style.display='inline-block';">
      <input type="hidden" name="batch_dir" value="{esc(str(batch_dir))}">
      <input type="hidden" name="archive_path" value="{esc(str(archive_path))}">
      <input type="hidden" name="conflict_action" value="rename">

      <label>Nouveau nom de dossier</label><br>
      <input name="new_table_name" value="{esc(suggested)}" style="width:90%; padding:8px; margin:8px 0;"><br>

      <button class="button" type="submit">Installer avec ce nouveau nom</button>
      <span id="renameSpinner" style="display:none; margin-left:10px; vertical-align:middle;"><svg width="20" height="20" viewBox="0 0 50 50" style="vertical-align:middle;"><circle cx="25" cy="25" r="20" fill="none" stroke="rgba(255,255,255,0.25)" stroke-width="6"></circle><path d="M25 5 A20 20 0 0 1 45 25" fill="none" stroke="#ff7a00" stroke-width="6" stroke-linecap="round"><animateTransform attributeName="transform" type="rotate" from="0 25 25" to="360 25 25" dur="0.75s" repeatCount="indefinite"/></path></svg></span>
    </form>
  </div>

  <p style="margin-top:14px;">
    <a class="button secondary" href="/tools">Annuler</a>
  </p>
</div>
""")


def pincabos_standard_table_folder_name(name):
    return pincabos_force_standard_table_name(name)


# Moved to modular route file by PinCabOS refactor (original lines 15782-15833).


def pincabos_import_from_manifest_dir(extract_dir, table_folder_override=None, overwrite_existing=False):
    root, manifest_path = pincabos_find_manifest_root(extract_dir)

    if not manifest_path:
        return None

    manifest = json.loads(manifest_path.read_text(errors="replace"))

    if manifest.get("format") != "PinCabOS table export":
        return {
            "ok": False,
            "message": "Manifest trouvé, mais format non reconnu.",
            "manifest": str(manifest_path),
            "copied": [],
            "missing": [],
            "skipped": [],
        }

    table_folder = str(table_folder_override or manifest.get("table_folder") or "").strip()
    if not table_folder:
        table_folder = Path(root).name or "Imported Table"

    table_folder = pincabos_force_standard_table_name(table_folder)

    # Destination officielle PinCabOS portable.
    table_root = pincabos_vpx_tables_dir() / table_folder

    copied = []
    missing = []
    skipped = []

    model = str(manifest.get("model") or "").strip().lower()

    # Nouveau modèle export:
    # Le manifest est dans le dossier de table extrait.
    # On copie donc le dossier complet tel quel, sans reclassement.
    if model in ["full-table-folder-as-is", "single-folder-portable-table"] or manifest.get("format_version", 0) >= 7:
        try:
            if table_root.exists():
                if not overwrite_existing:
                    return {
                        "ok": False,
                        "message": "Table déjà présente. Remplacement ou renommage requis.",
                        "manifest": str(manifest_path),
                        "table_folder": table_folder,
                        "rom": manifest.get("rom") or "",
                        "copied": copied,
                        "missing": missing,
                        "skipped": ["CONFLICT_TABLE_EXISTS"],
                    }
                shutil.rmtree(table_root)

            table_root.mkdir(parents=True, exist_ok=True)

            for item in sorted(Path(root).iterdir()):
                dest = table_root / item.name

                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                    for f in dest.rglob("*"):
                        if f.is_file():
                            copied.append(str(f))
                elif item.is_file():
                    shutil.copy2(item, dest)
                    copied.append(str(dest))

            pincabos_write_imported_table_metadata(table_root, table_folder)

            try:
                subprocess.run(
                    ["/bin/chown", "-R", "pinball:pinball", str(table_root)],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
                subprocess.run(
                    ["/bin/chmod", "-R", "u+rwX,g+rwX,o+rX", str(table_root)],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
            except Exception:
                pass

            return {
                "ok": True,
                "message": "Import .PinCabOs full-folder terminé. Dossier de table copié tel quel.",
                "manifest": str(manifest_path),
                "table_folder": table_folder,
                "rom": manifest.get("rom") or "",
                "copied": copied,
                "missing": missing,
                "skipped": skipped,
            }

        except Exception as e:
            return {
                "ok": False,
                "message": f"Erreur pendant l'import full-folder: {e}",
                "manifest": str(manifest_path),
                "table_folder": table_folder,
                "rom": manifest.get("rom") or "",
                "copied": copied,
                "missing": missing,
                "skipped": skipped,
            }

    # Ancien modèle manifest:
    # Supporte files = ["path"] ET files = [{"path":"...", "size":...}]
    if table_root.exists() and not overwrite_existing:
        return {
            "ok": False,
            "message": "Table déjà présente. Remplacement ou renommage requis.",
            "manifest": str(manifest_path),
            "table_folder": table_folder,
            "rom": manifest.get("rom") or "",
            "copied": copied,
            "missing": missing,
            "skipped": ["CONFLICT_TABLE_EXISTS"],
        }

    if table_root.exists() and overwrite_existing:
        shutil.rmtree(table_root)

    table_root.mkdir(parents=True, exist_ok=True)

    standard_dirs = manifest.get("standard_dirs") or [
        "altsound", "cache", "medias", "music",
        "pinmame", "pinmame/roms", "pinmame/nvram", "pinmame/cfg", "pinmame/ini",
        "pupvideos", "scripts", "serum", "user", "vni", "extras"
    ]

    for sub in standard_dirs:
        (table_root / str(sub).strip("/")).mkdir(parents=True, exist_ok=True)

    globals()["PINCABOS_MANIFEST_IMPORT_TABLE_DIR"] = table_root

    for empty_dir in manifest.get("empty_dirs") or []:
        if isinstance(empty_dir, dict):
            empty_dir = empty_dir.get("path", "")
        rel_empty = pincabos_safe_manifest_relpath(empty_dir)
        if rel_empty:
            dest_empty = table_root / rel_empty
            dest_empty.mkdir(parents=True, exist_ok=True)

    files = manifest.get("files") or []

    for entry in files:
        if isinstance(entry, dict):
            rel = entry.get("path", "")
        else:
            rel = entry

        rel = pincabos_safe_manifest_relpath(rel)
        if not rel:
            skipped.append(str(entry))
            continue

        src = root / rel
        if not src.exists() or not src.is_file():
            missing.append(rel)
            continue

        dest = table_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied.append(str(dest))

    pincabos_write_imported_table_metadata(table_root, table_folder)

    try:
        subprocess.run(
            ["/bin/chown", "-R", "pinball:pinball", str(table_root)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        subprocess.run(
            ["/bin/chmod", "-R", "u+rwX,g+rwX,o+rX", str(table_root)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except Exception:
        pass

    return {
        "ok": True,
        "message": "Import basé sur manifest terminé.",
        "manifest": str(manifest_path),
        "table_folder": table_folder,
        "rom": manifest.get("rom") or "",
        "copied": copied,
        "missing": missing,
        "skipped": skipped,
    }


def pincabos_try_manifest_import_from_request():
    """
    Si l'utilisateur importe un ZIP PinCabOS contenant pincabos-export-manifest.json,
    on restaure exactement les fichiers listés dans le manifest.
    Si aucun manifest n'est trouvé, retourne None pour laisser l'ancien import continuer.
    """
    if not request:
        return None

    # 1) ZIP envoyé directement dans request.files
    for key in request.files:
        f = request.files.get(key)
        if not f or not f.filename:
            continue

        filename = f.filename.lower()
        if not (filename.endswith(".zip") or filename.endswith(".7z") or filename.endswith(".pincabos")):
            continue

        with tempfile.TemporaryDirectory(prefix="pincabos-import-manifest-") as td:
            zip_path = Path(td) / "upload.zip"
            extract_dir = Path(td) / "extract"
            extract_dir.mkdir(parents=True, exist_ok=True)

            f.save(str(zip_path))

            try:
                r7 = subprocess.run(
                    ["7z", "x", "-y", f"-o{str(extract_dir)}", str(zip_path)],
                    capture_output=True,
                    text=True,
                    timeout=300,
                    check=False,
                )
                if r7.returncode != 0:
                    raise RuntimeError((r7.stdout + "\n" + r7.stderr).strip())
            except Exception as e:
                return page("Import PinCabOS", f"""
<div class="card">
  <h2>Import impossible</h2>
  <p class="bad">Le package ne peut pas être ouvert avec 7z.</p>
  <pre>{esc(str(e))}</pre>
  <p><a class="button" href="/tools">Retour aux outils</a></p>
</div>
""")

            result = pincabos_import_from_manifest_dir(extract_dir)
            if result:
                return pincabos_manifest_import_result_page(result)

    # 2) Chemin temporaire/dossier transmis dans le formulaire
    for value in request.form.values():
        value = str(value or "").strip()
        if not value:
            continue

        candidate = Path(value)
        if not candidate.exists():
            continue

        # Sécurité : seulement chemins temporaires ou PinCabOS
        allowed_prefixes = (
            "/tmp/",
            "/var/tmp/",
            "/opt/pincabos/tmp/",
            "/opt/pincabos/uploads/",
            "/home/pinball/Downloads/",
        )

        if not any(str(candidate).startswith(prefix) for prefix in allowed_prefixes):
            continue

        if candidate.is_dir():
            result = pincabos_import_from_manifest_dir(candidate)
            if result:
                return pincabos_manifest_import_result_page(result)

        if candidate.is_file() and candidate.suffix.lower() in [".zip", ".7z", ".pincabos", ".pincabos".lower()]:
            with tempfile.TemporaryDirectory(prefix="pincabos-import-manifest-") as td:
                extract_dir = Path(td) / "extract"
                extract_dir.mkdir(parents=True, exist_ok=True)

                try:
                    r7 = subprocess.run(
                        ["7z", "x", "-y", f"-o{str(extract_dir)}", str(candidate)],
                        capture_output=True,
                        text=True,
                        timeout=300,
                        check=False,
                    )
                    if r7.returncode != 0:
                        continue
                except Exception:
                    continue

                result = pincabos_import_from_manifest_dir(extract_dir)
                if result:
                    return pincabos_manifest_import_result_page(result)

    return None


def pincabos_manifest_import_result_page(result):
    ok_class = "ok" if result.get("ok") else "bad"
    copied = result.get("copied") or []
    missing = result.get("missing") or []
    skipped = result.get("skipped") or []

    copied_preview = "\n".join(copied[:80])
    if len(copied) > 80:
        copied_preview += f"\n... {len(copied) - 80} autres fichiers copiés"

    missing_preview = "\n".join(missing[:80])
    skipped_preview = "\n".join(skipped[:80])

    return page("Import PinCabOS", f"""
<div class="card">
  <h2>Import PinCabOS basé sur manifest</h2>
  <p class="{ok_class}">{esc(result.get("message", ""))}</p>

  <p><strong>Table :</strong> <code>{esc(result.get("table_folder", ""))}</code></p>
  <p><strong>ROM :</strong> <code>{esc(result.get("rom", ""))}</code></p>
  <p><strong>Manifest :</strong> <code>{esc(result.get("manifest", ""))}</code></p>

  <p><strong>Fichiers copiés :</strong> {len(copied)}</p>
  <pre>{esc(copied_preview)}</pre>

  <p><strong>Fichiers manquants dans le ZIP :</strong> {len(missing)}</p>
  <pre>{esc(missing_preview)}</pre>

  <p><strong>Fichiers ignorés :</strong> {len(skipped)}</p>
  <pre>{esc(skipped_preview)}</pre>

  <p>
    <a class="button" href="/tools">Retour aux outils</a>
    <a class="button secondary" href="/">Dashboard</a>
  </p>
</div>
""")


def pincabos_run_vpinfe_vpx_standardizer():
    """
    Normalise les tables vers le layout portable VPinFE/VPX après import.
    Les dossiers globaux restent en fallback legacy.
    """
    try:
        subprocess.run(
            [str(pco_script("vpinfe_vpx_standard")), "--apply"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=180,
            check=False
        )
    except Exception:
        pass

@import_bp.route("/tools/import-table/install", methods=["POST"])
def tools_import_table_install():
    manifest_response = pincabos_try_manifest_import_from_request()
    if manifest_response is not None:
        return manifest_response

    batch_dir = Path(request.form.get("batch_dir", "")).resolve()
    imports_root = Path("/home/pinball/Downloads").resolve()

    if not batch_dir.exists() or imports_root not in batch_dir.parents:
        return page("Outils", """
<div class="card">
  <h2>Installation impossible</h2>
  <p class="bad">Dossier batch invalide.</p>
  <p><a class="button" href="/tools">Retour Outils</a></p>
</div>
""")

    import_mode = request.form.get("import_mode", "auto").strip().lower()
    if import_mode not in ["auto", "search", "manual", "resources", "existing"]:
        import_mode = "auto"

    ipdbid = ""
    table_title = ""
    title = ""
    manufacturer = ""
    year = ""
    rom = ""
    vpsid = ""
    parent_vpsid = ""
    game_vpsid = ""
    parent_version = ""
    target_version = ""
    assoc = {}
    resource_manifest = {}
    target_existing = False

    if import_mode == "existing":
        selected_name = str(
            request.form.get("existing_table", "") or ""
        ).strip()
        tables_root = Path(pincabos_vpx_tables_dir()).resolve()
        candidate = tables_root / selected_name

        if (
            not selected_name
            or Path(selected_name).name != selected_name
            or candidate.is_symlink()
        ):
            return page("Outils", """
<div class="card">
  <h2>Installation impossible</h2>
  <p class="bad">Table de destination invalide.</p>
  <p><a class="button" href="/tools/import-table">Retour Smart Import</a></p>
</div>
""")

        try:
            selected_dir = candidate.resolve(strict=True)
        except Exception:
            selected_dir = candidate

        if (
            not selected_dir.is_dir()
            or selected_dir.parent != tables_root
        ):
            return page("Outils", """
<div class="card">
  <h2>Installation impossible</h2>
  <p class="bad">La destination n’est pas une table directe valide de Tables.</p>
  <p><a class="button" href="/tools/import-table">Retour Smart Import</a></p>
</div>
""")

        installed_vpxs = [
            item
            for item in selected_dir.glob("*.vpx")
            if item.is_file() and not item.is_symlink()
        ]

        if len(installed_vpxs) != 1:
            return page("Outils", """
<div class="card">
  <h2>Installation impossible</h2>
  <p class="bad">La table choisie ne contient pas exactement un VPX fiable.</p>
  <p><a class="button" href="/tools/import-table">Retour Smart Import</a></p>
</div>
""")

        existing_manifest = {}
        existing_manifest_path = selected_dir / "pincabos-table-manifest.json"

        if existing_manifest_path.is_file():
            try:
                loaded_manifest = json.loads(
                    existing_manifest_path.read_text(
                        encoding="utf-8",
                        errors="replace",
                    )
                )
                if isinstance(loaded_manifest, dict):
                    existing_manifest = loaded_manifest
            except Exception:
                existing_manifest = {}

        title = selected_dir.name
        table_title = str(
            existing_manifest.get("title", "") or title
        ).strip()
        manufacturer = str(
            existing_manifest.get("manufacturer", "") or ""
        ).strip()
        year = str(existing_manifest.get("year", "") or "").strip()
        rom = str(existing_manifest.get("rom", "") or "").strip()
        vpsid = str(existing_manifest.get("vpsid", "") or "").strip()
        game_vpsid = str(
            existing_manifest.get("game_vpsid", "") or ""
        ).strip()
        parent_vpsid = ""
        parent_version = ""
        target_version = ""
        ipdbid = str(existing_manifest.get("ipdbid", "") or "").strip()
        target_existing = True

        # Conserver l'inventaire partiel après sélection explicite de table.
        try:
            incoming_resource_manifest = (
                pincabos_smart_import_load_resource_manifest(
                    batch_dir,
                    required=False,
                )
            )
        except Exception as exc:
            return page("Outils", f"""
<div class="card">
  <h2>Installation impossible</h2>
  <p class="bad">{html.escape(str(exc))}</p>
  <p><a class="button" href="/tools/import-table">Retour Smart Import</a></p>
</div>
""")

        if incoming_resource_manifest:
            incoming_game_vpsid = str(
                incoming_resource_manifest.get("game_vpsid", "") or ""
            ).strip()
            known_existing_game_vpsid = game_vpsid

            if not known_existing_game_vpsid and vpsid:
                try:
                    existing_resource_identity = (
                        pincabos_smart_import_exact_resource(vpsid)
                    )
                    known_existing_game_vpsid = str(
                        existing_resource_identity.get("game_vpsid", "") or ""
                    ).strip()
                except Exception:
                    known_existing_game_vpsid = ""

            if (
                known_existing_game_vpsid
                and incoming_game_vpsid
                and known_existing_game_vpsid.casefold()
                != incoming_game_vpsid.casefold()
            ):
                return page("Outils", """
<div class="card">
  <h2>Installation impossible</h2>
  <p class="bad">La table choisie appartient à un autre jeu VPSDB que les VPS-ID fournis.</p>
  <p><a class="button" href="/tools/import-table">Retour Smart Import</a></p>
</div>
""")

            resource_manifest = incoming_resource_manifest
            if incoming_game_vpsid:
                game_vpsid = incoming_game_vpsid

    elif import_mode == "resources":
        try:
            resource_manifest = (
                pincabos_smart_import_load_resource_manifest(
                    batch_dir,
                    required=True,
                )
            )
        except Exception as exc:
            return page("Outils", f"""
<div class="card">
  <h2>Installation impossible</h2>
  <p class="bad">{html.escape(str(exc))}</p>
  <p><a class="button" href="/tools/import-table">Retour Smart Import</a></p>
</div>
""")

        title = str(
            resource_manifest.get("final_table_name", "")
            or resource_manifest.get("title", "")
            or ""
        ).strip()
        table_title = str(resource_manifest.get("title", "") or "").strip()
        manufacturer = str(resource_manifest.get("manufacturer", "") or "").strip()
        year = str(resource_manifest.get("year", "") or "").strip()
        rom = str(resource_manifest.get("rom", "") or "").strip()
        vpsid = str(resource_manifest.get("primary_table_vpsid", "") or "").strip()
        game_vpsid = str(resource_manifest.get("game_vpsid", "") or "").strip()
        parent_vpsid = str(resource_manifest.get("parent_vpsid", "") or "").strip()
        parent_version = str(resource_manifest.get("parent_version", "") or "").strip()
        target_version = str(resource_manifest.get("target_version", "") or "").strip()
        ipdbid = ""

        if not title or not game_vpsid:
            return page("Outils", """
<div class="card">
  <h2>Installation impossible</h2>
  <p class="bad">L’inventaire VPS-ID ne contient pas de table cible fiable.</p>
  <p><a class="button" href="/tools/import-table">Retour Smart Import</a></p>
</div>
""")

    elif import_mode == "manual":
        title = request.form.get("manual_title", "").strip()
        table_title = title
        manufacturer = request.form.get("manual_manufacturer", "").strip()
        year = request.form.get("manual_year", "").strip()
        rom = request.form.get("manual_rom", "").strip()
        vpsid = ""
        parent_vpsid = ""
        game_vpsid = ""
        parent_version = ""
        target_version = ""
        ipdbid = ""

        if not title:
            return page("Outils", """
<div class="card">
  <h2>Installation impossible</h2>
  <p class="bad">Le nom de table manuel est vide.</p>
  <p>Entre un nom de table VPinFE, par exemple <code>Demo Table (PinCabOS 2026)</code>.</p>
  <p><a class="button" href="/tools">Retour Outils</a></p>
</div>
""")

    else:
        if import_mode == "search":
            assoc_raw = request.form.get("search_association", "{}")
        else:
            assoc_raw = request.form.get("association", "{}")

        try:
            assoc = json.loads(assoc_raw) if assoc_raw else {}
        except Exception:
            assoc = {}

        if assoc.get("mode") != "vpsdb":
            return page("Outils", """
<div class="card">
  <h2>Installation impossible</h2>
  <p class="bad">Aucune association VPSdb valide sélectionnée.</p>
  <p>Utilise une sélection auto, un résultat de recherche VPSdb, ou l’import manuel complet.</p>
  <p><a class="button" href="/tools">Retour Outils</a></p>
</div>
""")

        table_title = str(assoc.get("title", "")).strip()
        manufacturer = str(assoc.get("manufacturer", "")).strip()
        year = str(assoc.get("year", "")).strip()
        rom = str(assoc.get("rom", "")).strip()
        vpsid = str(assoc.get("vpsid", "")).strip()
        parent_vpsid = str(assoc.get("parent_vpsid", "")).strip()
        game_vpsid = str(assoc.get("game_vpsid", "")).strip()
        parent_version = str(assoc.get("parent_version", "")).strip()
        target_version = str(assoc.get("version", "")).strip()
        ipdbid = str(assoc.get("ipdbid", "")).strip()

        title = str(assoc.get("final_table_name", "")).strip()
        if not title:
            title = table_title
            if manufacturer and year:
                title = f"{table_title} ({manufacturer} {year})"

        if not title:
            return page("Outils", """
<div class="card">
  <h2>Installation impossible</h2>
  <p class="bad">Le résultat VPSdb sélectionné ne contient pas de nom de table valide.</p>
  <p><a class="button" href="/tools">Retour Outils</a></p>
</div>
""")

    # Si aucune ROM fournie par VPSdb/manuel, on reprend la ROM détectée pendant l'analyse du batch.
    if not rom:
        try:
            detected_again = pincabos_detect_batch(batch_dir)
            rom = str(detected_again.get("rom", "") or "").strip()
        except Exception:
            rom = ""

    cmd = [
        str(pco_script("smart_archive_import")),
        str(batch_dir),
        "--title", title,
        "--manufacturer", manufacturer,
        "--year", str(year),
        "--vpsid", vpsid,
        "--parent-vpsid", parent_vpsid,
        "--game-vpsid", game_vpsid,
        "--parent-version", parent_version,
        "--target-version", target_version,
        "--rom", rom,
        "--ipdbid", ipdbid,
    ]

    if target_existing:
        cmd.append("--target-existing")

    if resource_manifest:
        cmd.extend([
            "--resources-json",
            str(pincabos_smart_import_resource_manifest_path(batch_dir)),
        ])

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        output = (r.stdout + "\n" + r.stderr).strip()
        returncode = r.returncode
    except Exception as e:
        output = f"ERREUR lancement importeur: {e}"
        returncode = 1

    # PINCABOS_SMART_IMPORT_PRESERVE_FAILED_BATCH_V1
    #
    # Un batch réussi est supprimé.
    # Un batch en erreur reste disponible pour diagnostic / reprise.
    if returncode == 0:
        try:
            if (
                batch_dir.exists()
                and imports_root in batch_dir.parents
            ):
                shutil.rmtree(batch_dir)

        except Exception as e:
            output += (
                "\n\nWARNING: impossible de supprimer "
                f"le batch upload: {e}"
            )

    else:
        output += (
            "\n\nINFO: import en erreur — batch conservé "
            "pour diagnostic/reprise : "
            f"{batch_dir}"
        )

    try:
        for work_root in [Path("/home/pinball/Downloads/work"), Path("/home/pinball/Downloads/work")]:
            if work_root.exists():
                for item in work_root.iterdir():
                    if item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                    else:
                        try:
                            item.unlink()
                        except Exception:
                            pass
    except Exception as e:
        output += f"\n\nWARNING: cleanup work erreur: {e}"

    cls = "ok" if returncode == 0 else "bad"
    title_msg = "Installation terminée" if returncode == 0 else "Installation terminée avec erreur(s)"

    body = f"""
<div class="card">
  <h2>{esc(title_msg)}</h2>
  <p class="{cls}">Mode : <strong>{esc(import_mode)}</strong></p>
  <p class="{cls}">Association : <strong>{esc(title)}</strong> — {esc(manufacturer)} — {esc(str(year))} — VPSId {esc(vpsid)}</p>

  <h3>Rapport</h3>
  <pre>{esc(output)}</pre>

  <p>
    <a class="button" href="/tools">Retour Outils</a>
    <a class="button secondary" href="/tools/commander?root=Tables">Voir les tables</a>
  </p>
</div>
"""
    return page("Outils", body)


# PINCABOS_SAFE_PATH_CONTAINMENT_V1
def pincabos_path_inside(path, root):
    """Vrai uniquement si path est root ou demeure réellement sous root."""
    try:
        candidate = Path(path).resolve(strict=False)
        base = Path(root).resolve(strict=False)
        candidate.relative_to(base)
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def pincabos_import_classifier_unavailable(exc):
    return jsonify({
        "ok": False,
        "error": (
            "Moteur pincabos_import_classifier absent ou impossible à charger. "
            "Installe /opt/pincabos/tools/pincabos_import_classifier.py. "
            f"Détail: {exc}"
        ),
    }), 503
# PINCABOS_SAFE_PATH_CONTAINMENT_V1_END

@import_bp.route("/api/import/analyze-zip", methods=["POST"])
def api_import_analyze_zip():
    try:
        from pathlib import Path
        import sys

        tools_dir = "/opt/pincabos/tools"
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)

        try:
            from pincabos_import_classifier import analyze_zip
        except (ImportError, ModuleNotFoundError) as exc:
            return pincabos_import_classifier_unavailable(exc)

        data = request.get_json(silent=True) or {}
        zip_path = data.get("zip_path") or data.get("path") or ""

        if not zip_path:
            return jsonify({"ok": False, "error": "zip_path manquant"}), 400

        zp = Path(zip_path).resolve()

        allowed_roots = [
            Path("/home/pinball/Downloads").resolve(),
            Path("/opt/pincabos/uploads").resolve(),
            Path("/opt/pincabos/tmp").resolve(),
            Path(pincabos_vpx_tables_dir()).resolve(),
        ]

        if not any(pincabos_path_inside(zp, root) for root in allowed_roots):
            return jsonify({"ok": False, "error": "chemin zip non autorisé"}), 403

        return jsonify(analyze_zip(zp))

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@import_bp.route("/api/import/apply-zip-choice", methods=["POST"])
def api_import_apply_zip_choice():
    try:
        from pathlib import Path
        import sys

        tools_dir = "/opt/pincabos/tools"
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)

        try:
            from pincabos_import_classifier import import_zip_by_choice, normalize_table_layout
        except (ImportError, ModuleNotFoundError) as exc:
            return pincabos_import_classifier_unavailable(exc)

        data = request.get_json(silent=True) or {}
        zip_path = data.get("zip_path") or data.get("path") or ""
        table_dir = data.get("table_dir") or ""
        choice = data.get("choice") or ""

        if not zip_path:
            return jsonify({"ok": False, "error": "zip_path manquant"}), 400
        if not table_dir:
            return jsonify({"ok": False, "error": "table_dir manquant"}), 400
        if choice not in ("rom", "medias", "music", "ignore"):
            return jsonify({"ok": False, "error": "choice invalide"}), 400

        zp = Path(zip_path).resolve()
        td = Path(table_dir).resolve()

        allowed_zip_roots = [
            Path("/home/pinball/Downloads").resolve(),
            Path("/opt/pincabos/uploads").resolve(),
            Path("/opt/pincabos/tmp").resolve(),
            Path(pincabos_vpx_tables_dir()).resolve(),
        ]

        tables_root = Path(pincabos_vpx_tables_dir()).resolve()

        if not any(pincabos_path_inside(zp, root) for root in allowed_zip_roots):
            return jsonify({"ok": False, "error": "chemin zip non autorisé"}), 403

        if not pincabos_path_inside(td, tables_root):
            return jsonify({"ok": False, "error": "table_dir non autorisé"}), 403

        standard_dirs = [
            "table", "media", "music", "roms", "pupvideos", "altcolor",
            "altsound", "dmd", "b2s", "scripts", "config", "docs", "extras"
        ]

        for sub in standard_dirs:
            (td / sub).mkdir(parents=True, exist_ok=True)

        result = import_zip_by_choice(zp, td, choice)

        if result.get("ok"):
            result["normalize"] = normalize_table_layout(td)

            try:
                subprocess.run(
                    [str(pco_script("import_portable_normalize")), "--table", td.name],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=False,
                )
            except Exception:
                pass

        return jsonify(result)

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
# === /PinCabOS Import ZIP Analyzer API ===


def register(app, page_fn):
    """Enregistre les pages et l'API d'import de tables sur l'application."""
    global page
    page = page_fn
    app.register_blueprint(import_bp)
