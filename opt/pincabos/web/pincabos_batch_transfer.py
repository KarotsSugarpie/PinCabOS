# PINCABOS_BATCH_TRANSFER_V1
# Batch Import / Batch Export portable PinCabOS.
# Les opérations sont séquentielles et refusées lorsqu'une table VPX est active.

from __future__ import annotations

import contextlib
import datetime
import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import traceback
import zipfile
from pathlib import Path

from flask import request


def register_pincabos_batch_transfer(app, app_globals):
    page = app_globals["page"]
    esc = app_globals["esc"]
    tables_dir_fn = app_globals["pincabos_vpx_tables_dir"]
    write_manifest_fn = app_globals["pincabos_write_full_folder_export_manifest"]
    zip_table_fn = app_globals["pincabos_zip_full_table_folder"]
    safe_filename_fn = app_globals["pincabos_export_safe_filename"]
    detect_vpsid_fn = app_globals["pincabos_detect_vpsid_for_export"]

    LOCAL_EXPORTS = Path("/home/pinball/Exports")
    IMPORT_ROOT = Path("/opt/pincabos/uploads/batch-import")
    LOG_ROOT = Path("/opt/pincabos/logs")
    IMPORT_BACKUP_ROOT = Path("/home/pinball/Backups/PinCabOS-BatchImport")
    LOCK_PATH = Path(os.environ.get(
        "PINCABOS_BATCH_LIVE_SHARED_LOCK",
        "/var/lib/pincabos/batch-live/export.lock",
    ))

    def _inside(path, root):
        try:
            Path(path).resolve().relative_to(Path(root).resolve())
            return True
        except Exception:
            return False

    def _safe_table_name(value):
        name = Path(str(value or "")).name.strip()
        name = name.replace("\x00", "")
        if not name or name in {".", ".."}:
            raise ValueError("Nom de table invalide.")
        return name

    def _format_size(size):
        size = float(size or 0)
        units = ("o", "KiB", "MiB", "GiB", "TiB")
        index = 0
        while size >= 1024 and index < len(units) - 1:
            size /= 1024
            index += 1
        return f"{size:.2f} {units[index]}"

    def _sha256(path):
        digest = hashlib.sha256()
        with Path(path).open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def _disk_free(path):
        current = Path(path)
        while not current.exists() and current != current.parent:
            current = current.parent
        return shutil.disk_usage(current).free

    def _write_log(log_path, message):
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with Path(log_path).open("a", encoding="utf-8") as handle:
            handle.write(f"[{stamp}] {message}\n")

    def _active_vpx_processes():
        try:
            proc = subprocess.run(
                ["/usr/bin/pgrep", "-fa", "VPinballX"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=5,
                check=False,
            )
            return (proc.stdout or "").strip()
        except Exception:
            return ""

    @contextlib.contextmanager
    def _batch_lock():
        LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOCK_PATH.open("w", encoding="utf-8") as handle:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError(
                    "Un Batch Import ou Batch Export est déjà en cours."
                ) from exc
            handle.write(f"pid={os.getpid()}\n")
            handle.flush()
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _mounted_destinations():
        """
        Retourne seulement des destinations réellement montées:
        - USB / disques externes sous /media, /run/media ou /mnt;
        - SMB/CIFS/NFS/SSHFS montés.
        """
        allowed_prefixes = ("/media/", "/run/media/", "/mnt/")
        network_types = {
            "cifs", "smb3", "smbfs", "nfs", "nfs4", "fuse.sshfs",
            "sshfs", "davfs", "fuse.davfs",
        }
        rows = []

        try:
            proc = subprocess.run(
                [
                    "/usr/bin/findmnt",
                    "-rn",
                    "-o",
                    "TARGET,SOURCE,FSTYPE",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=10,
                check=False,
            )
        except Exception:
            return rows

        seen = set()
        for raw_line in (proc.stdout or "").splitlines():
            fields = raw_line.split()
            if len(fields) < 3:
                continue

            target, source, fstype = fields[0], fields[1], fields[2].lower()
            target_path = Path(target)

            if target in seen:
                continue

            is_network = fstype in network_types
            is_removable_location = target == "/mnt" or target.startswith(allowed_prefixes)

            if not is_network and not is_removable_location:
                continue

            if not target_path.is_dir() or not os.path.ismount(target):
                continue

            kind = "SMB / réseau" if is_network else "USB / disque monté"
            rows.append({
                "target": target,
                "source": source,
                "fstype": fstype,
                "kind": kind,
                "label": f"{kind} — {target} ({source}, {fstype})",
            })
            seen.add(target)

        return sorted(rows, key=lambda item: item["target"].lower())


    # PINCABOS_BATCH_DESTINATION_BROWSER_V3_REGISTER
    # PINCABOS_BATCH_LIVE_V1_REGISTER
    try:
        from pincabos_batch_live import register_batch_live
        register_batch_live(app)
        # PINCABOS_BATCH_IMPORT_LIVE_PRO_V1_REGISTER
        from pincabos_batch_import_live import register_batch_import_live
        register_batch_import_live(app)

    except Exception as exc:
        app.logger.warning('PinCabOS Batch Live disabled: %s', exc)

    from pincabos_batch_destination_browser import (
        register_pincabos_batch_destination_browser,
    )
    batch_destination_browser = register_pincabos_batch_destination_browser(
        app,
        _mounted_destinations,
        _inside,
        LOCAL_EXPORTS,
    )

    def _tree_size(table_dir):
        total = 0
        table_dir = Path(table_dir)

        for current, dirs, files in os.walk(table_dir, topdown=True, followlinks=False):
            current_path = Path(current)
            dirs[:] = [
                name for name in dirs
                if not app_globals["pincabos_export_should_exclude_relative"](
                    (current_path / name).relative_to(table_dir)
                )
            ]

            for name in files:
                file_path = current_path / name
                rel = file_path.relative_to(table_dir)

                if app_globals["pincabos_export_should_exclude_relative"](rel):
                    continue

                try:
                    if not file_path.is_symlink():
                        total += file_path.stat().st_size
                except OSError:
                    pass

        return total

    def _validate_zip(package_path):
        package_path = Path(package_path)

        with zipfile.ZipFile(package_path, "r") as archive:
            bad = archive.testzip()
            if bad:
                raise ValueError(f"Archive corrompue: {bad}")

            if not archive.namelist():
                raise ValueError("Archive vide.")

            for info in archive.infolist():
                raw_name = info.filename.replace("\\", "/")
                candidate = Path(raw_name)

                if raw_name.startswith("/") or raw_name.startswith("../"):
                    raise ValueError(f"Chemin ZIP dangereux: {info.filename}")

                if ".." in candidate.parts:
                    raise ValueError(f"Chemin ZIP dangereux: {info.filename}")

                # Refuse les liens symboliques ZIP.
                mode = (info.external_attr >> 16) & 0o170000
                if mode == stat.S_IFLNK:
                    raise ValueError(f"Lien symbolique ZIP refusé: {info.filename}")

    def _safe_extract_zip(package_path, extract_root):
        package_path = Path(package_path)
        extract_root = Path(extract_root)
        extract_root.mkdir(parents=True, exist_ok=True)

        _validate_zip(package_path)

        with zipfile.ZipFile(package_path, "r") as archive:
            for info in archive.infolist():
                raw_name = info.filename.replace("\\", "/")
                if not raw_name:
                    continue

                destination = (extract_root / raw_name).resolve()
                if not _inside(destination, extract_root):
                    raise ValueError(f"Extraction hors dossier refusée: {info.filename}")

                if info.is_dir() or raw_name.endswith("/"):
                    destination.mkdir(parents=True, exist_ok=True)
                    continue

                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info, "r") as source, destination.open("wb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)

    def _portable_table_root(extract_root):
        extract_root = Path(extract_root)
        manifests = sorted(extract_root.glob("*/pincabos-export-manifest.json"))

        if len(manifests) != 1:
            raise ValueError(
                "Le package doit contenir exactement un dossier de table "
                "avec pincabos-export-manifest.json."
            )

        manifest_path = manifests[0]
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ValueError(f"Manifest export illisible: {exc}") from exc

        if manifest.get("format") != "PinCabOS table export":
            raise ValueError("Le package n'est pas un export portable PinCabOS.")

        table_root = manifest_path.parent
        _safe_table_name(table_root.name)
        return table_root, manifest

    def _normalize_imported_tree(root):
        root = Path(root)

        for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
            current_path = Path(current)
            try:
                mode = stat.S_IMODE(current_path.stat().st_mode)
                os.chmod(current_path, mode | 0o770)
            except OSError:
                pass

            for filename in files:
                file_path = current_path / filename
                try:
                    if file_path.is_symlink():
                        continue
                    mode = stat.S_IMODE(file_path.stat().st_mode)
                    os.chmod(file_path, mode | 0o660)
                except OSError:
                    pass

    def _next_renamed_target(tables_root, original_name, stamp):
        tables_root = Path(tables_root)
        base = f"{original_name} (import {stamp})"
        candidate = tables_root / base
        sequence = 2

        while candidate.exists():
            candidate = tables_root / f"{base} #{sequence}"
            sequence += 1

        return candidate

    def _render_results(title, subtitle, rows, log_path, back_href):
        row_html = []

        for item in rows:
            status_class = item.get("class", "warn")
            row_html.append(
                "<tr>"
                f"<td><code>{esc(item.get('name', ''))}</code></td>"
                f"<td class='{status_class}'><strong>{esc(item.get('status', ''))}</strong></td>"
                f"<td>{esc(item.get('detail', ''))}</td>"
                "</tr>"
            )

        return page(title, f"""
<style>
.pco-batch-result-table {{
  width: 100%;
  border-collapse: collapse;
  margin-top: 16px;
}}
.pco-batch-result-table th,
.pco-batch-result-table td {{
  padding: 10px;
  border-bottom: 1px solid rgba(255,255,255,.14);
  text-align: left;
  vertical-align: top;
}}
.pco-batch-result-table th {{
  color: #fff;
}}
</style>
<div class="card">
  <h2>{esc(title)}</h2>
  <p>{esc(subtitle)}</p>
  <p><strong>Journal :</strong> <code>{esc(str(log_path))}</code></p>
  <table class="pco-batch-result-table">
    <thead>
      <tr><th>Élément</th><th>Résultat</th><th>Détail</th></tr>
    </thead>
    <tbody>{''.join(row_html)}</tbody>
  </table>
  <p style="margin-top:18px;">
    <a class="button" href="{esc(back_href)}">Retour</a>
    <a class="button secondary" href="/tools">Outils</a>
  </p>
</div>
""")

    @app.route("/tools/batch-export", methods=["GET"])
    def pincabos_batch_export_page():
        tables_root = Path(tables_dir_fn()).resolve()
        LOCAL_EXPORTS.mkdir(parents=True, exist_ok=True)

        tables = []
        if tables_root.is_dir():
            for child in sorted(tables_root.iterdir(), key=lambda item: item.name.lower()):
                if child.is_dir() and not child.name.startswith("."):
                    tables.append(child.name)

        mounts = _mounted_destinations()

        table_rows = "".join(
            f"""
<label class="pco-batch-table-row">
  <input type="checkbox" name="table_folder" value="{esc(name)}">
  <span>{esc(name)}</span>
</label>
"""
            for name in tables
        ) or "<p class='warn'>Aucune table installée détectée.</p>"

        mount_options = "".join(
            f'<option value="{esc(item["target"])}">{esc(item["label"])}</option>'
            for item in mounts
        )

        return page("Batch Export PinCabOS", f"""
<style>
.pco-batch-page {{ max-width: 1160px; margin: 0 auto; }}
.pco-batch-panel {{
  background: rgba(17, 13, 29, .9);
  border: 1px solid rgba(160, 104, 255, .42);
  border-radius: 16px;
  padding: 20px;
  margin: 16px 0;
}}
.pco-batch-table-list {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(290px, 1fr));
  gap: 8px;
  max-height: 480px;
  overflow: auto;
  padding: 12px;
  border: 1px solid rgba(255,255,255,.12);
  border-radius: 12px;
}}
.pco-batch-table-row {{
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 8px 10px;
  border-radius: 9px;
  background: rgba(255,255,255,.035);
}}
.pco-batch-note {{
  padding: 12px;
  border-left: 4px solid #a068ff;
  background: rgba(160,104,255,.09);
  border-radius: 8px;
}}
</style>

<div class="pco-batch-page">
  <div class="card">
    <h2>Batch Export</h2>
    <p>Crée un package <code>.PinCabOs</code> par table, une seule à la fois.</p>
    <p class="pco-batch-note">
      Les exports excluent automatiquement <code>.pincabos-backups</code>,
      caches, fichiers temporaires et journaux techniques.
      Les tables sources ne sont jamais supprimées par cette fonction.
    </p>
  </div>

  <form method="post" action="/tools/batch-export/run">
    <div class="pco-batch-panel">
      <h3>1. Tables à exporter</h3>
      <p>
        <button type="button" class="button secondary" onclick="pcoBatchToggle(true)">Tout sélectionner</button>
        <button type="button" class="button secondary" onclick="pcoBatchToggle(false)">Tout désélectionner</button>
      </p>
      <div class="pco-batch-table-list">{table_rows}</div>
    </div>

    <div class="pco-batch-panel">
      <h3>2. Destination</h3>

      <label style="display:block; margin:10px 0;">
        <input type="radio" name="destination_kind" value="local" checked>
        Dossier local : <code>/home/pinball/Exports</code>
      </label>

      <label style="display:block; margin:10px 0;">
        <input type="radio" name="destination_kind" value="mount">
        USB ou SMB déjà monté :
      </label>

      <select name="mount_target" style="width:100%; max-width:900px;">
        <option value="">Sélectionner un montage détecté</option>
        {mount_options}
      </select>

      <p class="pco-batch-note">
        Insère la clé USB ou monte le partage SMB, puis recharge cette page.
        Chaque package copié est vérifié par SHA-256 après la copie.
      </p>
    </div>

    <div class="pco-batch-panel">
      <h3>3. Exécution</h3>
      <p>
        Le préflight vérifie l'espace disponible avant le premier export.
        Le Batch refuse de démarrer lorsqu'une table VPX est active.
      </p>
      <button class="button" type="submit"
        onclick="this.disabled=true; this.textContent='Batch Export en cours…';">
        Lancer Batch Export
      </button>
      <a class="button secondary" href="/tools/export-table">Retour Smart Export</a>
    </div>
  </form>
</div>

<script>
function pcoBatchToggle(state) {{
  document.querySelectorAll('input[name="table_folder"]').forEach(function(box) {{
    box.checked = state;
  }});
}}
</script>
""")

    @app.route("/tools/batch-export/run", methods=["POST"])
    def pincabos_batch_export_run():
        selected = []
        seen = set()

        for raw_name in request.form.getlist("table_folder"):
            try:
                name = _safe_table_name(raw_name)
            except ValueError:
                continue
            if name not in seen:
                selected.append(name)
                seen.add(name)

        if not selected:
            return page("Batch Export PinCabOS", """
<div class="card">
  <h2>Batch Export impossible</h2>
  <p class="bad">Aucune table sélectionnée.</p>
  <p><a class="button" href="/tools/batch-export">Retour Batch Export</a></p>
</div>
""")

        active_vpx = _active_vpx_processes()
        if active_vpx:
            return page("Batch Export PinCabOS", f"""
<div class="card">
  <h2>Batch Export bloqué</h2>
  <p class="warn">Ferme la table VPX actuellement lancée avant de démarrer un batch.</p>
  <pre>{esc(active_vpx)}</pre>
  <p><a class="button" href="/tools/batch-export">Retour Batch Export</a></p>
</div>
""")

        tables_root = Path(tables_dir_fn()).resolve()
        destination_kind = request.form.get("destination_kind", "local")
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

        LOG_ROOT.mkdir(parents=True, exist_ok=True)
        log_path = LOG_ROOT / f"batch-export-{stamp}.log"
        _write_log(log_path, "==================================================")
        _write_log(log_path, "PinCabOS Batch Export")
        _write_log(log_path, f"Tables demandées: {selected}")

        try:
            with _batch_lock():
                # PINCABOS_BATCH_DESTINATION_BROWSER_V3_RUNNER
                destination_root = batch_destination_browser.destination_root(
                    destination_kind,
                    request.form.get("mount_target", "").strip(),
                    request.form.get("destination_subpath", "").strip(),
                )

                # PINCABOS_BATCH_DIRECT_DESTINATION_V1
                # Écrit directement dans le dossier choisi par l’utilisateur.
                destination_batch = destination_root
                if not destination_batch.is_dir():
                    raise RuntimeError(f"Dossier de destination indisponible: {destination_batch}")

                source_tables = []
                estimated_size = 0

                for name in selected:
                    table_dir = (tables_root / name).resolve()
                    if not table_dir.is_dir() or not _inside(table_dir, tables_root):
                        raise RuntimeError(f"Dossier de table invalide: {name}")
                    source_tables.append(table_dir)
                    estimated_size += _tree_size(table_dir)

                free_space = _disk_free(destination_batch)
                required_space = int(estimated_size * 1.05) + (64 * 1024 * 1024)

                _write_log(log_path, f"Destination: {destination_batch}")
                _write_log(log_path, f"Estimation brute: {_format_size(estimated_size)}")
                _write_log(log_path, f"Espace libre: {_format_size(free_space)}")

                if free_space < required_space:
                    raise RuntimeError(
                        "Espace insuffisant sur la destination. "
                        f"Requis au minimum: {_format_size(required_space)}; "
                        f"libre: {_format_size(free_space)}."
                    )

                remote_destination = destination_kind == "mount"
                staging_root = destination_batch

                if remote_destination:
                    LOCAL_EXPORTS.mkdir(parents=True, exist_ok=True)
                    staging_root = Path(tempfile.mkdtemp(
                        prefix=f".batch-export-stage-{stamp}-",
                        dir=str(LOCAL_EXPORTS),
                    ))

                rows = []
                copy_failed = False

                for table_dir in source_tables:
                    table_name = table_dir.name
                    _write_log(log_path, f"EXPORT START: {table_name}")

                    try:
                        manifest_path = write_manifest_fn(table_dir)
                        safe_name = safe_filename_fn(table_dir.name)
                        vpsid = detect_vpsid_fn(table_dir)
                        base = f"{safe_name} - VPSId {vpsid}" if vpsid else safe_name

                        package_path = staging_root / f"{base}.PinCabOs"
                        temp_zip = staging_root / f"{base}.zip"

                        sequence = 2
                        # PINCABOS_BATCH_DIRECT_DESTINATION_COLLISION_V1
                        # Preserve an existing package in a direct USB/SMB destination.
                        while (
                            package_path.exists()
                            or temp_zip.exists()
                            or (
                                remote_destination
                                and (
                                    (destination_batch / package_path.name).exists()
                                    or (destination_batch / f".{package_path.name}.part").exists()
                                )
                            )
                        ):
                            package_path = staging_root / f"{base} #{sequence}.PinCabOs"
                            temp_zip = staging_root / f"{base} #{sequence}.zip"
                            sequence += 1

                        zip_table_fn(table_dir, temp_zip)
                        temp_zip.replace(package_path)

                        with zipfile.ZipFile(package_path, "r") as archive:
                            bad_member = archive.testzip()
                            if bad_member:
                                raise RuntimeError(f"ZIP invalide: {bad_member}")

                        source_hash = _sha256(package_path)
                        final_path = package_path

                        if remote_destination:
                            final_path = destination_batch / package_path.name
                            partial_path = destination_batch / f".{package_path.name}.part"

                            if partial_path.exists():
                                partial_path.unlink()

                            shutil.copy2(package_path, partial_path)
                            destination_hash = _sha256(partial_path)

                            if source_hash != destination_hash:
                                partial_path.unlink(missing_ok=True)
                                raise RuntimeError("SHA-256 différent après copie USB/SMB.")

                            partial_path.replace(final_path)

                        _write_log(log_path, f"EXPORT OK: {table_name} -> {final_path}")
                        _write_log(log_path, f"SHA256: {source_hash}")

                        rows.append({
                            "name": table_name,
                            "status": "Succès",
                            "class": "ok",
                            "detail": (
                                f"{_format_size(final_path.stat().st_size)} — "
                                f"{final_path} — SHA-256 vérifié"
                            ),
                        })

                    except Exception as exc:
                        copy_failed = True
                        _write_log(log_path, f"EXPORT ERROR: {table_name}: {exc}")
                        _write_log(log_path, traceback.format_exc())
                        rows.append({
                            "name": table_name,
                            "status": "Erreur",
                            "class": "bad",
                            "detail": str(exc),
                        })

                if remote_destination and not copy_failed:
                    shutil.rmtree(staging_root, ignore_errors=True)
                    _write_log(log_path, "Staging local supprimé après copie validée.")
                elif remote_destination:
                    _write_log(log_path, f"Staging conservé après erreur: {staging_root}")
                    rows.append({
                        "name": "Staging local",
                        "status": "Conservé",
                        "class": "warn",
                        "detail": f"Archives locales conservées: {staging_root}",
                    })

                return _render_results(
                    "Batch Export terminé",
                    f"Destination: {destination_batch}",
                    rows,
                    log_path,
                    "/tools/batch-export",
                )

        except Exception as exc:
            _write_log(log_path, f"BATCH EXPORT ERROR: {exc}")
            _write_log(log_path, traceback.format_exc())
            return _render_results(
                "Batch Export interrompu",
                str(exc),
                [],
                log_path,
                "/tools/batch-export",
            )

    @app.route("/tools/batch-import", methods=["GET"])
    def pincabos_batch_import_page():
        return page("Batch Import PinCabOS", """
<style>
.pco-batch-page { max-width: 980px; margin: 0 auto; }
.pco-batch-panel {
  background: rgba(17, 13, 29, .9);
  border: 1px solid rgba(160, 104, 255, .42);
  border-radius: 16px;
  padding: 20px;
  margin: 16px 0;
}
.pco-batch-note {
  padding: 12px;
  border-left: 4px solid #a068ff;
  background: rgba(160,104,255,.09);
  border-radius: 8px;
}
</style>

<div class="pco-batch-page">
  <div class="card">
    <h2>Batch Import</h2>
    <p>Importe plusieurs packages portables <code>.PinCabOs</code>, une table à la fois.</p>
    <p class="pco-batch-note">
      Les archives sont validées avant extraction. Une archive malveillante,
      corrompue ou sans manifest PinCabOS est refusée.
    </p>
  </div>

  <form method="post" action="/tools/batch-import/run" enctype="multipart/form-data">
    <div class="pco-batch-panel">
      <h3>1. Packages portables</h3>
      <input type="file" name="archives" multiple required
             accept=".pincabos,.PinCabOs,.zip"
             style="width:100%;">
      <p>
        Utilise Batch Import pour les exports portables PinCabOS.
        Smart Import individuel reste disponible pour les archives non standard.
      </p>
    </div>

    <div class="pco-batch-panel">
      <h3>2. Conflit avec une table déjà installée</h3>
      <label style="display:block; margin:10px 0;">
        <input type="radio" name="conflict_mode" value="skip" checked>
        Ignorer la table existante
      </label>
      <label style="display:block; margin:10px 0;">
        <input type="radio" name="conflict_mode" value="rename">
        Importer sous un nouveau nom
      </label>
      <label style="display:block; margin:10px 0;">
        <input type="radio" name="conflict_mode" value="replace">
        Remplacer après backup local automatique
      </label>
      <p class="pco-batch-note">
        Les remplacements sont sauvegardés dans
        <code>/home/pinball/Backups/PinCabOS-BatchImport/</code>.
      </p>
    </div>

    <div class="pco-batch-panel">
      <h3>3. Exécution</h3>
      <p>
        Le Batch refuse de démarrer lorsqu'une table VPX est active.
        Les imports ne sont jamais effectués en parallèle.
      </p>
      <button class="button" type="submit"
        onclick="this.disabled=true; this.textContent='Batch Import en cours…';">
        Lancer Batch Import
      </button>
      <a class="button secondary" href="/tools/import-table">Retour Smart Import</a>
    </div>
  </form>
</div>
""")

    @app.route("/tools/batch-import/run", methods=["POST"])
    def pincabos_batch_import_run():
        uploaded_archives = [
            item for item in request.files.getlist("archives")
            if item and item.filename
        ]

        if not uploaded_archives:
            return page("Batch Import PinCabOS", """
<div class="card">
  <h2>Batch Import impossible</h2>
  <p class="bad">Aucune archive reçue.</p>
  <p><a class="button" href="/tools/batch-import">Retour Batch Import</a></p>
</div>
""")

        active_vpx = _active_vpx_processes()
        if active_vpx:
            return page("Batch Import PinCabOS", f"""
<div class="card">
  <h2>Batch Import bloqué</h2>
  <p class="warn">Ferme la table VPX actuellement lancée avant de démarrer un batch.</p>
  <pre>{esc(active_vpx)}</pre>
  <p><a class="button" href="/tools/batch-import">Retour Batch Import</a></p>
</div>
""")

        conflict_mode = request.form.get("conflict_mode", "skip").strip().lower()
        if conflict_mode not in {"skip", "rename", "replace"}:
            conflict_mode = "skip"

        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        job_id = f"{stamp}-{os.getpid()}"
        job_root = IMPORT_ROOT / job_id
        archives_root = job_root / "archives"
        extracts_root = job_root / "extracts"

        tables_root = Path(tables_dir_fn()).resolve()
        IMPORT_BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
        backup_root = IMPORT_BACKUP_ROOT / job_id

        LOG_ROOT.mkdir(parents=True, exist_ok=True)
        log_path = LOG_ROOT / f"batch-import-{stamp}.log"
        _write_log(log_path, "==================================================")
        _write_log(log_path, "PinCabOS Batch Import")
        _write_log(log_path, f"Conflit: {conflict_mode}")

        rows = []

        try:
            with _batch_lock():
                archives_root.mkdir(parents=True, exist_ok=True)
                extracts_root.mkdir(parents=True, exist_ok=True)
                backup_root.mkdir(parents=True, exist_ok=True)

                used_names = set()

                for position, uploaded in enumerate(uploaded_archives, start=1):
                    raw_name = Path(uploaded.filename).name
                    safe_upload_name = re.sub(r"[^A-Za-z0-9._ ()\-\[\]]+", "_", raw_name).strip(" ._")
                    safe_upload_name = safe_upload_name or f"package-{position}.PinCabOs"

                    suffix = Path(safe_upload_name).suffix.lower()
                    if suffix not in {".pincabos", ".zip"}:
                        rows.append({
                            "name": raw_name,
                            "status": "Refusé",
                            "class": "bad",
                            "detail": "Extension acceptée: .PinCabOs ou .zip",
                        })
                        continue

                    candidate_name = safe_upload_name
                    sequence = 2
                    while candidate_name.lower() in used_names:
                        candidate_name = f"{Path(safe_upload_name).stem} #{sequence}{suffix}"
                        sequence += 1
                    used_names.add(candidate_name.lower())

                    archive_path = archives_root / candidate_name
                    extract_root = extracts_root / f"{position:03d}"

                    _write_log(log_path, f"IMPORT START: {raw_name}")

                    try:
                        uploaded.save(str(archive_path))
                        _validate_zip(archive_path)
                        _safe_extract_zip(archive_path, extract_root)

                        source_table, manifest = _portable_table_root(extract_root)
                        table_name = _safe_table_name(source_table.name)
                        destination = (tables_root / table_name).resolve()

                        if not _inside(destination, tables_root):
                            raise RuntimeError("Destination de table refusée.")

                        backup_path = None

                        if destination.exists():
                            if conflict_mode == "skip":
                                rows.append({
                                    "name": table_name,
                                    "status": "Ignoré",
                                    "class": "warn",
                                    "detail": "Table déjà installée.",
                                })
                                _write_log(log_path, f"IMPORT SKIP: {table_name} existe déjà")
                                continue

                            if conflict_mode == "rename":
                                destination = _next_renamed_target(
                                    tables_root,
                                    table_name,
                                    stamp,
                                )

                            elif conflict_mode == "replace":
                                backup_path = backup_root / table_name
                                sequence = 2
                                while backup_path.exists():
                                    backup_path = backup_root / f"{table_name} #{sequence}"
                                    sequence += 1

                                try:
                                    destination.replace(backup_path)
                                except OSError:
                                    shutil.move(str(destination), str(backup_path))

                                _write_log(
                                    log_path,
                                    f"BACKUP EXISTANT: {table_name} -> {backup_path}",
                                )

                        try:
                            shutil.copytree(source_table, destination, symlinks=False)
                            _normalize_imported_tree(destination)
                        except Exception:
                            if backup_path and backup_path.exists() and not destination.exists():
                                try:
                                    backup_path.replace(destination)
                                except OSError:
                                    shutil.move(str(backup_path), str(destination))
                            raise

                        _write_log(log_path, f"IMPORT OK: {table_name} -> {destination}")
                        detail = f"Importé dans {destination}"

                        if backup_path:
                            detail += f" — backup: {backup_path}"

                        rows.append({
                            "name": table_name,
                            "status": "Succès",
                            "class": "ok",
                            "detail": detail,
                        })

                    except Exception as exc:
                        _write_log(log_path, f"IMPORT ERROR: {raw_name}: {exc}")
                        _write_log(log_path, traceback.format_exc())
                        rows.append({
                            "name": raw_name,
                            "status": "Erreur",
                            "class": "bad",
                            "detail": str(exc),
                        })

                return _render_results(
                    "Batch Import terminé",
                    f"Mode de conflit: {conflict_mode}",
                    rows,
                    log_path,
                    "/tools/batch-import",
                )

        except Exception as exc:
            _write_log(log_path, f"BATCH IMPORT ERROR: {exc}")
            _write_log(log_path, traceback.format_exc())
            return _render_results(
                "Batch Import interrompu",
                str(exc),
                rows,
                log_path,
                "/tools/batch-import",
            )

    @app.after_request
    def pincabos_batch_cards_in_smart_pages(response):
        """
        Legacy card injection. Disabled when native Import/Export Center is enabled.
        """
        if app.config.get("PINCABOS_IMPEXP_NATIVE_UI"):
            return response
        if request.method != "GET":
            return response

        if request.path not in {"/tools/import-table", "/tools/export-table"}:
            return response

        if response.direct_passthrough:
            return response

        if "text/html" not in (response.content_type or ""):
            return response

        try:
            body = response.get_data(as_text=True)
        except Exception:
            return response

        if "PINCABOS_BATCH_CARD_V1" in body:
            return response

        if request.path == "/tools/import-table":
            title = "Batch Import"
            text = (
                "Importer plusieurs packages portables PinCabOS, "
                "un à la fois, avec gestion des conflits et backups."
            )
            href = ""
            button = ""
        else:
            title = "Batch Export"
            text = (
                "Exporter plusieurs tables vers le stockage local, "
                "une clé USB ou un partage SMB déjà monté."
            )
            href = ""
            button = ""
        injection = f"""
<!-- PINCABOS_BATCH_CARD_V1 -->
<style>
.pco-batch-smart-card {{
  margin: 22px 0 0;
  padding: 18px;
  border: 1px solid rgba(160,104,255,.54);
  border-radius: 16px;
  background: linear-gradient(130deg, rgba(99,44,170,.19), rgba(19,15,34,.88));
  box-shadow: 0 10px 28px rgba(0,0,0,.22);
}}
.pco-batch-smart-card h3 {{
  margin: 0 0 8px;
}}
.pco-batch-smart-card p {{
  margin: 0 0 14px;
  opacity: .92;
}}
</style>
<script>
(function() {{
  var root = document.querySelector('.pco-smart-transfer');
  if (!root || document.getElementById('pincabos-batch-smart-card')) return;

  var card = document.createElement('section');
  card.id = 'pincabos-batch-smart-card';
  card.className = 'pco-batch-smart-card';
  card.innerHTML =
    '<h3>{title}</h3>' +
    '<p>{text}</p>' +
    '<a class="button" href="{href}">{button}</a>';

  root.appendChild(card);
}})();
</script>
"""

        if "</body>" in body:
            body = body.replace("</body>", injection + "</body>", 1)
        else:
            body += injection

        response.set_data(body)
        response.headers.pop("Content-Length", None)
        return response
