"""Commander (gestionnaire de fichiers) de la WebApp PinCabOS : /tools/commander et ses actions, visionneuse / éditeur « live ».

Code déplacé tel quel depuis app.py (PINCABOS_WEBAPP_MODULES_V1) ; les routes gardent
leurs chemins et leurs noms de fonction. `page()` (gabarit commun) est fourni par app.py
à l'enregistrement : `register(app, page)`.
"""
from __future__ import annotations

import json
import shutil
import urllib.parse
import zipfile
from datetime import datetime
from pathlib import Path

from flask import Blueprint, redirect, request, send_file

from pincabos_webapp_core import esc, pincabos_get_vpinfe_paths_for_tools, pincabos_vpx_tables_dir, pincabos_write_json_with_meta
from werkzeug.utils import secure_filename
commander_bp = Blueprint("commander", __name__)

page = None  # gabarit HTML commun, posé par register()


def pincabos_commander_roots():
    paths = pincabos_get_vpinfe_paths_for_tools()

    roots = {
        "Tables": Path(paths["tables"]),
        "AltSound": Path(paths["altsound"]),
        "AltColor": Path(paths["altcolor"]),
        "PupVideos": Path(paths["pupvideos"]),
        "UltraDMD": Path(paths["ultradmd"]),
        "Exports": Path("/home/pinball/Exports"),
        "Imports temporaires": Path("/home/pinball/Downloads"),
        "Home Pinball": Path("/home/pinball"),
        "Partage PinCabOS": Path("/home/pinball/Share"),
        "Stockage USB": Path("/mnt/pincab-usb"),
        "Lecteurs SMB": Path("/home/pinball/NetworkDrives"),
    }

    clean = {}
    for name, path in roots.items():
        try:
            path.mkdir(parents=True, exist_ok=True)
            clean[name] = path.resolve()
        except Exception:
            clean[name] = path.resolve()

    return clean


def pincabos_commander_resolve(root_name, rel_path=""):
    roots = pincabos_commander_roots()

    if root_name not in roots:
        raise ValueError("Racine invalide.")

    root = roots[root_name]
    target = (root / rel_path).resolve()

    if target != root and root not in target.parents:
        raise ValueError("Chemin interdit.")

    return root, target


def pincabos_size_human(size):
    try:
        size = float(size)
        for unit in ["o", "Ko", "Mo", "Go", "To"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} Po"
    except Exception:
        return ""


def pcx_roots():
    return {
        "Tables": pincabos_vpx_tables_dir(),
        "Exports": Path("/home/pinball/Exports"),
        "Imports": Path("/home/pinball/Downloads"),
        "Home Pinball": Path("/home/pinball"),
        "Logs": Path("/opt/pincabos/logs"),
        "Backups": Path("/opt/pincabos/backups"),
        "Medias": Path("/opt/pincabos/media"),
        "PinCabShare": Path("/home/pinball/Share"),
        "Stockage USB": Path("/mnt/pincab-usb"),
        "Lecteurs SMB": Path("/home/pinball/NetworkDrives"),
    }


def pcx_resolve(root_name, rel_path=""):
    roots = pcx_roots()

    if root_name not in roots:
        root_name = "Tables"

    root = roots[root_name].resolve()
    root.mkdir(parents=True, exist_ok=True)

    target = (root / (rel_path or "")).resolve()

    if target != root and root not in target.parents:
        raise ValueError("Chemin interdit.")

    return root_name, root, target


def pcx_back(root_name, rel_path=""):
    return redirect(
        "/tools/commander?root="
        + urllib.parse.quote(root_name or "Tables")
        + "&path="
        + urllib.parse.quote(rel_path or "")
    )


def pcx_size(size):
    try:
        size = float(size)
        for unit in ["o", "Ko", "Mo", "Go", "To"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} Po"
    except Exception:
        return ""


def pcx_selected():
    try:
        data = request.form.get("selected_json", "[]")
        items = json.loads(data)
        if not isinstance(items, list):
            return []
        return [str(x).strip() for x in items if str(x).strip()]
    except Exception:
        return []


def pcx_clean_name(name):
    name = str(name or "").strip().replace("\\", "/").split("/")[-1]
    name = name.replace("\x00", "")
    if name in ["", ".", ".."]:
        raise ValueError("Nom invalide.")
    return name


def pcx_unique(path):
    path = Path(path)
    if not path.exists():
        return path

    parent = path.parent
    stem = path.stem
    suffix = path.suffix

    for i in range(1, 500):
        candidate = parent / f"{stem} - copie {i}{suffix}"
        if not candidate.exists():
            return candidate

    raise ValueError("Impossible de créer un nom unique.")


def pcx_copy_any(src, dst):
    src = Path(src)
    dst = Path(dst)

    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)


@commander_bp.route("/tools/commander")
def tools_commander():
    import time

    root_name = request.args.get("root") or "Tables"
    rel = request.args.get("path") or ""

    try:
        root_name, root, current = pcx_resolve(root_name, rel)
    except Exception:
        root_name, root, current = pcx_resolve("Tables", "")
        rel = ""

    roots = pcx_roots()
    encoded_root = urllib.parse.quote(root_name)
    encoded_rel = urllib.parse.quote(rel)
    current_rel = "/" if current == root else "/" + str(current.relative_to(root))

    sidebar = ""
    for name in roots:
        cls = "pcx-root active" if name == root_name else "pcx-root"
        icon = "📁"
        if name == "Tables":
            icon = "🎮"
        elif "ROM" in name:
            icon = "💾"
        elif "AltSound" in name:
            icon = "🔊"
        elif "AltColor" in name:
            icon = "🎨"
        elif "Pup" in name:
            icon = "🎬"
        elif "Ultra" in name:
            icon = "🖥️"
        elif "Export" in name:
            icon = "📦"
        elif "Import" in name:
            icon = "📥"
        elif "Home" in name:
            icon = "🏠"
        elif name == "Logs":
            icon = "📋"
        elif name == "Backups":
            icon = "🗄️"
        elif name == "Medias":
            icon = "🎞️"
        elif name == "PinCabShare":
            icon = "📌"
        elif "USB" in name or "Clés" in name:
            icon = "🔌"
        elif "SMB" in name:
            icon = "🌐"

        sidebar += (
            '<a class="' + cls + '" href="/tools/commander?root=' + urllib.parse.quote(name) + '">' +
            icon + " " + esc(name) + "</a>"
        )

    parent_button = ""
    if current != root:
        parent_rel = str(current.parent.relative_to(root))
        parent_button = '<a class="pcx-btn" href="/tools/commander?root=' + encoded_root + '&path=' + urllib.parse.quote(parent_rel) + '">⬅ Parent</a>'

    rows = ""
    cards = ""

    # PINCABOS_EXPLORER_NATIVE_TABLES_V1_ROUTE
    pco_native_root = (
        root_name == "Tables"
        and current == root
    )

    # PINCABOS_EXPLORER_CONTROLS_IN_TABLE_V41
    pco_table_header_tools = ""
    pco_direct_table = (
        root_name == "Tables"
        and current != root
        and current.parent == root
    )

    if pco_direct_table:
        try:
            from pincabos_explorer_table_test import (
                native_catalog_context,
                native_controls_html,
            )

            pco_table_rel = str(
                current.relative_to(root)
            ).replace("\\", "/")

            pco_table_header_tools = native_controls_html(
                pco_table_rel,
                native_catalog_context(),
            )
        except Exception:
            pco_table_header_tools = ""

    parent_row = ""
    if current != root:
        parent_rel_for_row = str(current.parent.relative_to(root))
        parent_href_for_row = "/tools/commander?root=" + encoded_root + "&path=" + urllib.parse.quote(parent_rel_for_row)
        parent_row = (
            '<tr class="pcx-parent-row" data-name=".. parent" data-size="-1" data-mtime="-1">' +
            '<td colspan="4"><a class="pcx-name pcx-parent-link" href="' + parent_href_for_row + '">📁 .. Parent</a></td>' +
            '</tr>'
        )
    else:
        parent_row = (
            '<tr class="pcx-parent-row" data-name=".. parent" data-size="-1" data-mtime="-1">' +
            '<td colspan="4"><span class="pcx-parent-disabled">📁 .. Parent — racine actuelle</span></td>' +
            '</tr>'
        )

    try:
        entries = sorted(current.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
    except Exception:
        entries = []

    # PINCABOS_EXPLORER_TABLE_PAGINATION_V1
    # Pagination native côté Flask : seules les tables de la racine Tables
    # sont découpées. Les dossiers internes et les autres racines Explorer
    # conservent leur comportement historique.
    pco_pagination_html = ""

    if pco_native_root:
        pco_per_page_choices = (25, 50, 100, 200)

        try:
            pco_per_page = int(request.args.get("per_page", "50"))
        except (TypeError, ValueError):
            pco_per_page = 50

        if pco_per_page not in pco_per_page_choices:
            pco_per_page = 50

        try:
            pco_page_number = int(request.args.get("page", "1"))
        except (TypeError, ValueError):
            pco_page_number = 1

        pco_page_number = max(1, pco_page_number)
        pco_total_entries = len(entries)
        pco_total_pages = max(
            1,
            (pco_total_entries + pco_per_page - 1) // pco_per_page,
        )
        pco_page_number = min(pco_page_number, pco_total_pages)
        pco_slice_start = (pco_page_number - 1) * pco_per_page
        pco_slice_end = min(
            pco_slice_start + pco_per_page,
            pco_total_entries,
        )

        def pco_pagination_url(page_number):
            return (
                "/tools/commander?"
                + urllib.parse.urlencode({
                    "root": root_name,
                    "path": rel,
                    "page": max(1, min(int(page_number), pco_total_pages)),
                    "per_page": pco_per_page,
                })
            )

        def pco_pagination_link(label, page_number, disabled=False, current_page=False):
            classes = ["pcx-page-link"]
            if disabled:
                classes.append("is-disabled")
            if current_page:
                classes.append("is-current")

            class_attr = " ".join(classes)

            if disabled or current_page:
                return (
                    '<span class="' + class_attr + '">'
                    + label
                    + "</span>"
                )

            return (
                '<a class="' + class_attr + '" href="'
                + pco_pagination_url(page_number)
                + '">'
                + label
                + "</a>"
            )

        pco_page_links = []
        pco_page_links.append(
            pco_pagination_link(
                "« Première",
                1,
                disabled=pco_page_number <= 1,
            )
        )
        pco_page_links.append(
            pco_pagination_link(
                "‹ Préc.",
                pco_page_number - 1,
                disabled=pco_page_number <= 1,
            )
        )

        pco_window_start = max(1, pco_page_number - 2)
        pco_window_end = min(pco_total_pages, pco_page_number + 2)

        for pco_visible_page in range(pco_window_start, pco_window_end + 1):
            pco_page_links.append(
                pco_pagination_link(
                    str(pco_visible_page),
                    pco_visible_page,
                    current_page=(pco_visible_page == pco_page_number),
                )
            )

        pco_page_links.append(
            pco_pagination_link(
                "Suiv. ›",
                pco_page_number + 1,
                disabled=pco_page_number >= pco_total_pages,
            )
        )
        pco_page_links.append(
            pco_pagination_link(
                "Dernière »",
                pco_total_pages,
                disabled=pco_page_number >= pco_total_pages,
            )
        )

        pco_per_page_options = "".join(
            '<option value="'
            + str(pco_choice)
            + ('" selected>' if pco_choice == pco_per_page else '">')
            + str(pco_choice)
            + "</option>"
            for pco_choice in pco_per_page_choices
        )

        if pco_total_entries:
            pco_range_text = (
                str(pco_slice_start + 1)
                + "–"
                + str(pco_slice_end)
                + " sur "
                + str(pco_total_entries)
                + " tables"
            )
        else:
            pco_range_text = "0 table"

        pco_pagination_html = (
            '<nav class="pcx-pagination" aria-label="Navigation des tables">'
            '<div class="pcx-pagination-summary">'
            + pco_range_text
            + " · Page "
            + str(pco_page_number)
            + "/"
            + str(pco_total_pages)
            + "</div>"
            '<div class="pcx-pagination-links">'
            + "".join(pco_page_links)
            + "</div>"
            '<form class="pcx-pagination-size" method="get" action="/tools/commander">'
            '<input type="hidden" name="root" value="'
            + esc(root_name)
            + '">'
            '<input type="hidden" name="path" value="'
            + esc(rel)
            + '">'
            '<input type="hidden" name="page" value="1">'
            '<label>Tables par page '
            '<select name="per_page">'
            + pco_per_page_options
            + "</select></label>"
            '<button type="submit" class="pcx-small">Appliquer</button>'
            "</form>"
            "</nav>"
        )

        entries = entries[pco_slice_start:pco_slice_end]

    for item in entries:
        try:
            item_rel = str(item.relative_to(root))
            item_url = urllib.parse.quote(item_rel)
            modified = time.strftime("%Y-%m-%d %H:%M", time.localtime(item.stat().st_mtime))
            is_dir = item.is_dir()
            size = "-" if is_dir else pcx_size(item.stat().st_size)

            icon = "📁" if is_dir else "📄"
            suffix = item.suffix.lower()

            if not is_dir:
                if suffix in [".zip", ".rar", ".7z"]:
                    icon = "📦"
                elif suffix == ".vpx":
                    icon = "🎱"
                elif suffix == ".directb2s":
                    icon = "🖼️"
                elif suffix in [".png", ".jpg", ".jpeg", ".webp", ".gif"]:
                    icon = "🌄"
                elif suffix in [".mp4", ".avi", ".mov"]:
                    icon = "🎬"
                elif suffix in [".ogg", ".wav", ".mp3"]:
                    icon = "🔊"
                elif suffix in [".json", ".txt", ".ini", ".vbs", ".pov"]:
                    icon = "📝"

            if is_dir:
                open_href = "/tools/commander?root=" + encoded_root + "&path=" + item_url
                name_html = '<a class="pcx-name" href="' + open_href + '">' + esc(item.name) + '</a>'
                action = '<a class="pcx-small" href="' + open_href + '">Ouvrir</a>'
            else:
                download_href = "/tools/commander/download?root=" + encoded_root + "&path=" + item_url
                name_html = esc(item.name)
                # PINCABOS_PCX_NATIVE_FILE_ACTIONS_V2
                live_href = (
                    "/tools/commander/live?root="
                    + encoded_root
                    + "&path="
                    + item_url
                )

                pcx_text_exts = {
                    ".ini", ".cfg", ".conf",
                    ".txt", ".log",
                    ".vbs", ".vbe",
                    ".json", ".xml",
                    ".yaml", ".yml",
                    ".csv", ".tsv",
                    ".md", ".pov",
                }

                pcx_image_exts = {
                    ".png", ".jpg", ".jpeg",
                    ".gif", ".webp", ".bmp", ".svg",
                }

                pcx_media_exts = {
                    ".mp3", ".wav", ".ogg", ".flac",
                    ".mp4", ".webm", ".mkv",
                }

                if suffix in pcx_text_exts:
                    action = (
                        '<a class="pcx-small pcx-live-action" href="'
                        + live_href
                        + '">✏ Modifier</a> '
                        + '<a class="pcx-small" href="'
                        + download_href
                        + '">Télécharger</a>'
                    )

                elif suffix in pcx_image_exts:
                    action = (
                        '<a class="pcx-small pcx-live-action" href="'
                        + live_href
                        + '">👁 Voir</a> '
                        + '<a class="pcx-small" href="'
                        + download_href
                        + '">Télécharger</a>'
                    )

                elif suffix in pcx_media_exts:
                    action = (
                        '<a class="pcx-small pcx-live-action" href="'
                        + live_href
                        + '">▶ Ouvrir</a> '
                        + '<a class="pcx-small" href="'
                        + download_href
                        + '">Télécharger</a>'
                    )

                else:
                    action = (
                        '<a class="pcx-small" href="'
                        + download_href
                        + '">Télécharger</a>'
                    )

            item_stat = item.stat()
            rows += (
                '<tr class="pcx-row" data-name="' + esc(item.name.lower()) + '" data-size="' + esc(item_stat.st_size if item.is_file() else 0) + '" data-mtime="' + esc(item_stat.st_mtime) + '" data-rel="' + esc(item_rel) + '">' +
                '<td><input type="checkbox" class="pcx-check" value="' + esc(item_rel) + '"> ' +
                '<span class="pcx-icon">' + icon + '</span> ' + name_html + '</td>' +
                '<td>' + esc(size) + '</td>' +
                '<td>' + esc(modified) + '</td>' +
                '<td>' + action + '</td>' +
                '</tr>'
            )

            cards += (
                '<div class="pcx-card" data-name="' + esc(item.name.lower()) + '">' +
                '<div class="pcx-card-icon">' + icon + '</div>' +
                '<div class="pcx-card-name">' + name_html + '</div>' +
                '<div class="pcx-card-meta">' + esc(size) + '</div>' +
                '</div>'
            )
        except Exception:
            pass

    body = """
<style>
.pcx-page {
  font-size:13px;
}
.pcx-layout {
  display:grid;
  grid-template-columns:250px 1fr;
  gap:18px;
}
.pcx-top, .pcx-side, .pcx-main {
  background:#111418;
  border:1px solid #242a31;
  border-radius:18px;
  padding:16px;
}
.pcx-actions-title {
  color:#ffb000;
  font-weight:900;
  font-size:18px;
  margin-top:14px;
  margin-bottom:8px;
  text-shadow:0 0 12px rgba(255,140,0,.45);
}
.pcx-toolbar {
  display:flex;
  flex-wrap:wrap;
  gap:9px;
  margin-top:8px;
}
.pcx-btn {
  display:inline-block;
  padding:8px 11px;
  border-radius:8px;
  background:#1b2027;
  color:inherit;
  text-decoration:none;
  border:0;
  cursor:pointer;
  font-size:13px;
}
.pcx-btn:hover {
  background:rgba(255,140,0,.25);
}
.pcx-root {
  display:block;
  padding:9px 11px;
  margin-bottom:7px;
  border-radius:8px;
  background:#181c22;
  text-decoration:none;
  color:inherit;
}
.pcx-root:hover {
  background:rgba(255,140,0,.18);
}
.pcx-root.active {
  background:#ff8c00;
  color:#111;
  font-weight:800;
}
.pcx-path {
  margin-top:12px;
  padding:11px 13px;
  border-radius:8px;
  background:#0b0d10;
}
.pcx-path-label {
  color:#ffb000;
  font-weight:800;
  margin-bottom:6px;
}
.pcx-real-path,
.pcx-main-path {
  margin:6px 0 0 0;
  color:#ffb000;
  font-size:18px;
  line-height:1.25;
  word-break:break-all;
  text-shadow:0 0 12px rgba(255,140,0,.35);
}
.pcx-main-path {
  font-size:16px;
  color:#ffffff;
  opacity:.95;
}
.pcx-select-all {
  display:inline-flex;
  align-items:center;
  gap:6px;
  cursor:pointer;
}
.pcx-head {
  display:flex;
  justify-content:space-between;
  gap:12px;
  align-items:center;
  flex-wrap:wrap;
  margin-bottom:14px;
}
.pcx-search {
  padding:9px;
  border-radius:8px;
  border:1px solid #333a44;
  background:#0b0d10;
  color:inherit;
  min-width:260px;
}
/* PINCABOS_EXPLORER_TABLE_PAGINATION_V1_CSS */
.pcx-pagination {
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:12px;
  flex-wrap:wrap;
  margin:10px 0 14px;
  padding:10px 12px;
  border:1px solid #2e3540;
  border-radius:10px;
  background:#0b0d10;
}
.pcx-pagination-summary {
  color:#d7dbe2;
  font-weight:700;
  white-space:nowrap;
}
.pcx-pagination-links {
  display:flex;
  align-items:center;
  justify-content:center;
  gap:6px;
  flex-wrap:wrap;
}
.pcx-page-link {
  display:inline-flex;
  align-items:center;
  justify-content:center;
  min-width:34px;
  min-height:32px;
  padding:5px 9px;
  border:1px solid #343b46;
  border-radius:8px;
  background:#181c22;
  color:#fff;
  text-decoration:none;
  font-weight:800;
}
.pcx-page-link:hover {
  border-color:#ff8c00;
  background:rgba(255,140,0,.20);
}
.pcx-page-link.is-current {
  border-color:#ffb000;
  background:#ff8c00;
  color:#111;
}
.pcx-page-link.is-disabled {
  opacity:.38;
  cursor:default;
}
.pcx-pagination-size {
  display:flex;
  align-items:center;
  gap:7px;
  white-space:nowrap;
}
.pcx-pagination-size select {
  padding:6px 8px;
  border:1px solid #5f2a91;
  border-radius:8px;
  background:#0b0d10;
  color:#fff;
}
@media(max-width:900px) {
  .pcx-pagination {
    align-items:stretch;
  }
  .pcx-pagination-summary,
  .pcx-pagination-links,
  .pcx-pagination-size {
    width:100%;
    justify-content:center;
  }
}

.pcx-table {
  width:100%;
  border-collapse:collapse;
}
.pcx-table th {
  text-align:left;
  padding:8px 10px;
  border-bottom:1px solid #333a44;
  font-size:12px;
}
.pcx-sortable {
  cursor:pointer;
  user-select:none;
}
.pcx-sortable:hover {
  color:#ffb000;
  text-decoration:underline;
}
.pcx-parent-row td {
  background:rgba(255,140,0,.08);
  border-bottom:1px solid rgba(255,140,0,.25);
}
.pcx-parent-link {
  display:inline-block;
  padding:6px 0;
  font-weight:900;
}
.pcx-parent-disabled {
  display:inline-block;
  padding:6px 0;
  opacity:.55;
  font-weight:800;
}
.pcx-table td {
  padding:7px 10px;
  border-bottom:1px solid #232831;
}
.pcx-row:hover {
  background:rgba(255,140,0,.12);
}
.pcx-row.selected {
  background:rgba(255,140,0,.24);
}
.pcx-icon {
  font-size:18px;
  margin-right:8px;
}
.pcx-name {
  font-weight:800;
  text-decoration:none;
}
.pcx-small {
  display:inline-block;
  padding:5px 8px;
  border-radius:8px;
  background:#1b2027;
  color:inherit;
  text-decoration:none;
  font-size:12px;
}
.pcx-grid {
  display:none;
  grid-template-columns:repeat(auto-fill,minmax(150px,1fr));
  gap:12px;
}
.pcx-card {
  background:#161a20;
  border:1px solid #242a31;
  border-radius:16px;
  padding:12px;
  min-height:110px;
}
.pcx-card-icon {
  font-size:34px;
}
.pcx-card-name {
  margin-top:6px;
  font-weight:700;
  word-break:break-word;
}
.pcx-card-meta {
  margin-top:5px;
  opacity:.75;
  font-size:12px;
}
@media(max-width:900px) {
  .pcx-layout {
    grid-template-columns:1fr;
  }
}
</style>

<div class="pcx-page">
  <div class="pcx-top">
    <h2>PinCab Explorer</h2>
    <div class="pcx-actions-title">Actions</div>

<script>
document.addEventListener("DOMContentLoaded", function () {
  const page = document.querySelector(".pcx-page");
  if (!page) return;

  if (page.querySelector(".pcx-refresh-btn")) return;

  const buttons = Array.from(page.querySelectorAll("button, a.pcx-btn, input[type='submit'], input[type='button']"));

  const gridBtn = buttons.find(function (el) {
    const txt = (el.innerText || el.value || "").trim();
    return txt.includes("Vue grille");
  });

  if (!gridBtn) return;

  const refresh = document.createElement("a");
  refresh.href = window.location.pathname + window.location.search;
  refresh.className = "pcx-btn pcx-refresh-btn";
  refresh.innerHTML = '<span class="pcx-btn-icon">🔄</span>Rafraîchir';

  if (gridBtn.nextSibling) {
    gridBtn.parentNode.insertBefore(refresh, gridBtn.nextSibling);
  } else {
    gridBtn.parentNode.appendChild(refresh);
  }
});
</script>


<style>
/* PinCab Explorer : bouton Supprimer rouge foncé */
.pcx-page .pcx-delete-danger,
.pcx-page button.pcx-delete-danger,
.pcx-page a.pcx-delete-danger,
.pcx-page input.pcx-delete-danger {
  background: #7a0000 !important;
  color: #ffffff !important;
  border: 1px solid #ff4444 !important;
  box-shadow: 0 0 12px rgba(255,0,0,0.35) !important;
}

.pcx-page .pcx-delete-danger:hover,
.pcx-page button.pcx-delete-danger:hover,
.pcx-page a.pcx-delete-danger:hover,
.pcx-page input.pcx-delete-danger:hover {
  background: #a00000 !important;
  color: #ffffff !important;
}

.pcx-page .pcx-btn-icon {
  display: inline-block !important;
  margin-right: 6px !important;
  font-size: 1.05em !important;
  line-height: 1 !important;
}
</style>

<script>
document.addEventListener("DOMContentLoaded", function () {
  const page = document.querySelector(".pcx-page");
  if (!page) return;

  const icons = [
    { label: "Vue liste", icon: "📋" },
    { label: "Vue grille", icon: "▦" },
    { label: "Créer dossier", icon: "📁" },
    { label: "Upload", icon: "⬆️" },
    { label: "Renommer", icon: "✏️" },
    { label: "Copier", icon: "📄" },
    { label: "Couper", icon: "✂️" },
    { label: "Coller", icon: "📋" },
    { label: "Dupliquer", icon: "📑" },
    { label: "Extraire ZIP", icon: "📦" },
    { label: "Archiver sélection", icon: "🗜️" },
    { label: "Infos", icon: "ℹ️" },
    { label: "Supprimer", icon: "🗑️", danger: true }
  ];

  const candidates = page.querySelectorAll("button, a.pcx-btn, input[type='submit'], input[type='button']");

  candidates.forEach(function (el) {
    const raw = (el.innerText || el.value || "").trim();
    if (!raw) return;

    icons.forEach(function (item) {
      if (!raw.includes(item.label)) return;

      if (item.danger) {
        el.classList.add("pcx-delete-danger");
      }

      if (el.dataset.pcxIconDone === "1") return;

      if (el.tagName.toLowerCase() === "input") {
        el.value = item.icon + " " + raw;
      } else {
        el.innerHTML = '<span class="pcx-btn-icon">' + item.icon + '</span>' + raw;
      }

      el.dataset.pcxIconDone = "1";
    });
  });
});
</script>


<style>
/* PinCab Explorer : bouton Retour Outils orange seulement */
.pcx-page a.pcx-btn[href="/tools"],
.pcx-page a.pcx-btn[href="/tools"]:visited {
  background: var(--pco-appearance-nav-active-bg, #ff7a00) !important;
  color: var(--pco-appearance-nav-active-text, #160020) !important;
  border: 1px solid var(--pco-appearance-accent, #ffb000) !important;
  box-shadow: 0 0 14px rgba(255,122,0,0.45) !important;
}

.pcx-page a.pcx-btn[href="/tools"]:hover {
  background: #ffb000 !important;
  color: var(--pco-appearance-nav-active-text, #160020) !important;
}
</style>


<style>
/* PinCab Explorer : liens fichiers/dossiers en blanc */
.pcx-page a:not(.button):not(.pcx-btn),
.pcx-page a:not(.button):not(.pcx-btn):visited,
.pcx-page table a:not(.button):not(.pcx-btn),
.pcx-page table a:not(.button):not(.pcx-btn):visited,
.pcx-page td a:not(.button):not(.pcx-btn),
.pcx-page td a:not(.button):not(.pcx-btn):visited {
  color: #ffffff !important;
  text-decoration: none !important;
}

.pcx-page a:not(.button):not(.pcx-btn):hover,
.pcx-page table a:not(.button):not(.pcx-btn):hover,
.pcx-page td a:not(.button):not(.pcx-btn):hover {
  color: #ffb000 !important;
  text-decoration: underline !important;
}
</style>


    <div class="pcx-toolbar">
      <a class="pcx-btn" href="/tools">Retour Outils</a>
      __PARENT_BUTTON__
      <button class="pcx-btn" onclick="pcxView('list')">Vue liste</button>
      <button class="pcx-btn" onclick="pcxView('grid')">Vue grille</button>
      <button class="pcx-btn" onclick="pcxCreateFolder()">Créer dossier</button>
      <button class="pcx-btn" onclick="document.getElementById('pcxUploadInput').click()">Upload</button>
      <button class="pcx-btn" onclick="pcxRename()">Renommer</button>
      <button class="pcx-btn" onclick="pcxCopy()">Copier</button>
      <button class="pcx-btn" onclick="pcxCut()">Couper</button>
      <button class="pcx-btn" onclick="pcxPaste()">Coller</button>
        <button class="pcx-btn" onclick="pcxDuplicate()">Dupliquer</button>
        <button class="pcx-btn" onclick="pcxExtractZip()">Extraire ZIP</button>
        <button class="pcx-btn" onclick="pcxArchiveSelection()">Archiver sélection</button>
        <button class="pcx-btn" onclick="pcxInfo()">Infos</button>
        <button class="pcx-btn" onclick="pcxExtractScript()">📜 Extraire script</button>
        <button class="pcx-btn" onclick="pcxDelete()">Supprimer</button>
    </div>

    <form id="pcxUploadForm" action="/tools/commander/upload" method="post" enctype="multipart/form-data" style="display:none;">
      <input type="hidden" name="root" value="__ROOT_NAME__">
      <input type="hidden" name="path" value="__REL_RAW__">
      <input id="pcxUploadInput" type="file" name="files" multiple onchange="document.getElementById('pcxUploadForm').submit()">
    </form>

  </div>

  <div class="pcx-layout" style="margin-top:18px;">
    <div class="pcx-side">
      <h3>Emplacements</h3>
      __SIDEBAR__
    </div>

    <div class="pcx-main">
      <div class="pcx-head">
        <div>
          <h3 class="pcx-main-root-title" style="margin:0;">__ROOT_NAME__</h3>
          <small>__CURRENT_REL__</small>
          <h2 class="pcx-main-path">__CURRENT_ABS_PATH__</h2>
        </div>
        <input id="pcxSearch" class="pcx-search" placeholder="Rechercher..." oninput="pcxFilter()">
      </div>

      __PAGINATION_TOP__

      <div id="pcxList">
        <table class="pcx-table">
          <thead>
            <tr>
              <th class="pcx-sortable" onclick="pcxSortTable('name')"><label class="pcx-select-all" onclick="event.stopPropagation();"><input id="pcxSelectAll" type="checkbox" onchange="pcxToggleAll(this)"> Nom</label> <span id="pcxSortName"></span></th>
              <th class="pcx-sortable" onclick="pcxSortTable('size')">Taille <span id="pcxSortSize"></span></th>
              <th class="pcx-sortable" onclick="pcxSortTable('mtime')">Modifié <span id="pcxSortMtime"></span></th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            __PARENT_ROW__
            __ROWS__
          </tbody>
        </table>
      </div>

      <div id="pcxGrid" class="pcx-grid">
        __CARDS__
      </div>

      __PAGINATION_BOTTOM__
    </div>
  </div>
</div>

<script>
function pcxSelected() {
  return Array.from(document.querySelectorAll('.pcx-check:checked')).map(cb => cb.value);
}

function pcxPost(action, extra = {}) {
  // PINCABOS_PCX_CSRF_POST_V1
  // Les formulaires Explorer sont créés dynamiquement.
  // On doit donc recopier explicitement le jeton CSRF global.
  const csrfMeta = document.querySelector(
    'meta[name="pincabos-csrf-token"]'
  );
  const csrf = csrfMeta ? String(csrfMeta.content || '') : '';

  if (!csrf) {
    alert(
      'Session WebApp invalide ou expirée. ' +
      'Recharge la page puis recommence l’action.'
    );
    return;
  }

  const form = document.createElement('form');
  form.method = 'POST';
  form.action = action;

  const fields = {
    root: "__ROOT_NAME_JS__",
    path: "__REL_RAW_JS__",
    selected_json: JSON.stringify(pcxSelected()),
    ...extra,
    _pco_csrf: csrf
  };

  Object.entries(fields).forEach(([key, value]) => {
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = key;
    input.value = value;
    form.appendChild(input);
  });

  document.body.appendChild(form);
  form.submit();
}

function pcxCreateFolder() {
  const name = prompt('Nom du nouveau dossier :');
  if (!name) return;
  pcxPost('/tools/commander/create-folder', {folder_name: name});
}

function pcxRename() {
  const selected = pcxSelected();
  if (selected.length !== 1) {
    alert('Sélectionne un seul élément à renommer.');
    return;
  }

  const currentName = selected[0].split('/').pop();
  const name = prompt('Nouveau nom :', currentName);
  if (!name || name === currentName) return;

  pcxPost('/tools/commander/rename', {new_name: name});
}

function pcxDelete() {
  const selected = pcxSelected();
  if (!selected.length) {
    alert('Sélectionne au moins un élément à supprimer.');
    return;
  }

  if (!confirm('Supprimer définitivement ' + selected.length + ' élément(s) ?')) return;
  pcxPost('/tools/commander/delete');
}

function pcxCopy() {
  const selected = pcxSelected();
  if (!selected.length) {
    alert('Sélectionne au moins un élément à copier.');
    return;
  }
  pcxPost('/tools/commander/clipboard', {mode: 'copy'});
}

function pcxCut() {
  const selected = pcxSelected();
  if (!selected.length) {
    alert('Sélectionne au moins un élément à couper.');
    return;
  }
  pcxPost('/tools/commander/clipboard', {mode: 'cut'});
}

function pcxPaste() {
  pcxPost('/tools/commander/paste');
}

function pcxDuplicate() {
  const selected = pcxSelected();
  if (!selected.length) {
    alert('Sélectionne au moins un fichier ou dossier à dupliquer.');
    return;
  }

  pcxPost('/tools/commander/duplicate');
}

function pcxExtractZip() {
  const selected = pcxSelected();
  if (!selected.length) {
    alert('Sélectionne au moins une archive ZIP à extraire.');
    return;
  }

  const bad = selected.filter(x => !x.toLowerCase().endsWith('.zip'));
  if (bad.length) {
    alert('Extraction ZIP seulement. Élément non ZIP: ' + bad[0]);
    return;
  }

  pcxPost('/tools/commander/extract-zip');
}


function pcxArchiveSelection() {
  const selected = pcxSelected();

  if (!selected.length) {
    alert('Sélectionne au moins un fichier ou dossier à archiver.');
    return;
  }

  const suggested = selected.length === 1
    ? selected[0].replace(/\\/+$/g, '').split('/').pop().replace(/\\.zip$/i, '')
    : 'selection-pincabos';

  const archiveName = prompt("Nom de l'archive ZIP :", suggested);

  if (archiveName === null) {
    return;
  }

  const cleaned = archiveName.trim();

  if (!cleaned) {
    alert("Nom d'archive vide. Opération annulée.");
    return;
  }

  pcxPost('/tools/commander/archive-selection', { archive_name: cleaned });
}


  // PINCABOS_PCX_EXTRACT_SCRIPT_BUTTON_V5
  function pcxExtractScript() {
    const selected = pcxSelected();

    if (selected.length !== 1) {
      alert('Sélectionne exactement une table .vpx.');
      return;
    }

    if (!selected[0].toLowerCase().endsWith('.vpx')) {
      alert('Extraction possible seulement pour un fichier .vpx.');
      return;
    }

    if (!confirm('Extraire et sauvegarder le script VBS de cette table ?')) {
      return;
    }

    pcxPost('/tools/commander/extract-script');
  }

function pcxInfo() {
  const selected = pcxSelected();
  if (selected.length > 1) {
    alert('Sélectionne un seul élément pour voir les infos.');
    return;
  }

  pcxPost('/tools/commander/info');
}

function pcxView(mode) {
  const list = document.getElementById('pcxList');
  const grid = document.getElementById('pcxGrid');

  if (mode === 'grid') {
    list.style.display = 'none';
    grid.style.display = 'grid';
    localStorage.setItem('pincabosPcxView', 'grid');
  } else {
    list.style.display = 'block';
    grid.style.display = 'none';
    localStorage.setItem('pincabosPcxView', 'list');
  }
}

function pcxFilter() {
  const q = document.getElementById('pcxSearch').value.toLowerCase();

  document.querySelectorAll('.pcx-row').forEach(row => {
    row.style.display = (row.dataset.name || '').includes(q) ? '' : 'none';
  });

  document.querySelectorAll('.pcx-card').forEach(card => {
    card.style.display = (card.dataset.name || '').includes(q) ? '' : 'none';
  });
}

let pcxSortState = { key: "", dir: "asc" };

function pcxSortTable(type) {
  const tbody = document.querySelector(".pcx-table tbody");
  if (!tbody) return;

  const parentRow = tbody.querySelector(".pcx-parent-row");
  const rows = Array.from(tbody.querySelectorAll("tr.pcx-row"));

  const dir = pcxSortState.key === type && pcxSortState.dir === "asc" ? "desc" : "asc";
  pcxSortState = { key: type, dir: dir };

  rows.sort((a, b) => {
    let av;
    let bv;

    if (type === "name") {
      av = (a.dataset.name || "").toLowerCase();
      bv = (b.dataset.name || "").toLowerCase();
    } else if (type === "size") {
      av = parseFloat(a.dataset.size || "0") || 0;
      bv = parseFloat(b.dataset.size || "0") || 0;
    } else if (type === "mtime") {
      av = parseFloat(a.dataset.mtime || "0") || 0;
      bv = parseFloat(b.dataset.mtime || "0") || 0;
    } else {
      return 0;
    }

    if (av < bv) return dir === "asc" ? -1 : 1;
    if (av > bv) return dir === "asc" ? 1 : -1;
    return 0;
  });

  tbody.innerHTML = "";
  if (parentRow) tbody.appendChild(parentRow);
  rows.forEach(row => tbody.appendChild(row));

  ["pcxSortName", "pcxSortSize", "pcxSortMtime"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.textContent = "";
  });

  const arrow = dir === "asc" ? "▲" : "▼";

  if (type === "name") {
    const el = document.getElementById("pcxSortName");
    if (el) el.textContent = arrow;
  }

  if (type === "size") {
    const el = document.getElementById("pcxSortSize");
    if (el) el.textContent = arrow;
  }

  if (type === "mtime") {
    const el = document.getElementById("pcxSortMtime");
    if (el) el.textContent = arrow;
  }
}


function pcxUpdateSelectAllState() {
  const master = document.getElementById('pcxSelectAll');
  if (!master) return;

  const checks = Array.from(document.querySelectorAll('.pcx-check'));
  const visibleChecks = checks.filter(cb => {
    const row = cb.closest('.pcx-row');
    return row && row.style.display !== 'none';
  });

  if (!visibleChecks.length) {
    master.checked = false;
    master.indeterminate = false;
    return;
  }

  const selectedCount = visibleChecks.filter(cb => cb.checked).length;
  master.checked = selectedCount === visibleChecks.length;
  master.indeterminate = selectedCount > 0 && selectedCount < visibleChecks.length;
}

function pcxToggleAll(master) {
  const checks = Array.from(document.querySelectorAll('.pcx-check'));

  checks.forEach(cb => {
    const row = cb.closest('.pcx-row');
    if (!row || row.style.display === 'none') return;

    cb.checked = master.checked;
    if (cb.checked) row.classList.add('selected');
    else row.classList.remove('selected');
  });

  pcxUpdateSelectAllState();
}

document.querySelectorAll('.pcx-check').forEach(cb => {
  cb.addEventListener('change', () => {
    const row = cb.closest('.pcx-row');
    if (cb.checked) row.classList.add('selected');
    else row.classList.remove('selected');
    pcxUpdateSelectAllState();
  });
});

pcxUpdateSelectAllState();

pcxView(localStorage.getItem('pincabosPcxView') || 'list');
</script>
"""

    body = body.replace("__PARENT_BUTTON__", parent_button)
    body = body.replace("__ROOT_NAME__", esc(root_name))
    body = body.replace("__ROOT_NAME_JS__", esc(root_name))
    body = body.replace("__REL_RAW__", esc(rel))
    body = body.replace("__REL_RAW_JS__", esc(rel))
    current_rel_display = "" if str(current_rel).strip("/") == "" else current_rel
    body = body.replace("__CURRENT_REL__", esc(current_rel_display))
    body = body.replace("__CURRENT_ABS_PATH__", esc(str(current)))
    body = body.replace("__SIDEBAR__", sidebar)
    body = body.replace("__PAGINATION_TOP__", pco_pagination_html)
    body = body.replace("__PAGINATION_BOTTOM__", pco_pagination_html)
    body = body.replace("__PARENT_ROW__", parent_row)
    body = body.replace("__ROWS__", rows)
    body = body.replace("__CARDS__", cards)

    if pco_table_header_tools:
        pco_header_slot = (
            '<div class="pco-table-header-slot">'
            + pco_table_header_tools
            + "</div>"
        )

        pco_search_candidates = [
            body.find('<input id="pcxSearch"'),
            body.find(
                '<form class="pco-native-search-form"'
            ),
        ]
        pco_search_candidates = [
            position
            for position in pco_search_candidates
            if position >= 0
        ]

        if not pco_search_candidates:
            raise RuntimeError(
                "Champ Rechercher introuvable dans PinCab Explorer."
            )

        pco_search_position = min(pco_search_candidates)
        body = (
            body[:pco_search_position]
            + pco_header_slot
            + body[pco_search_position:]
        )

    # PINCABOS_COMMANDER_ZERO_BACKGROUND_V1_NATIVE_COUNT
    # Le compteur est rendu par Flask avec la page, sans fetch JS.
    if root_name == "Tables" and current == root:
        try:
            pco_installed_count = sum(
                1
                for pco_entry in root.iterdir()
                if pco_entry.is_dir()
            )
        except OSError:
            pco_installed_count = 0

        pco_count_label = (
            "table installée"
            if pco_installed_count == 1
            else "tables installées"
        )

        pco_native_badge = (
            '<div id="pco-explorer-installed-table-count" '
            'class="pco-explorer-installed-table-count '
            'pco-native-count-badge" role="status">'
            '<span class="pco-explorer-table-count-icon" '
            'aria-hidden="true">🎮</span>'
            '<span class="pco-explorer-table-count-value">'
            + str(pco_installed_count)
            + "</span>"
            '<span class="pco-explorer-table-count-label">'
            + pco_count_label
            + "</span>"
            "</div>"
        )

        pco_heading = "<h2>PinCab Explorer</h2>"

        if (
            pco_heading in body
            and 'id="pco-explorer-installed-table-count"' not in body
        ):
            body = body.replace(
                pco_heading,
                '<div class="pco-explorer-native-heading">'
                + pco_heading
                + pco_native_badge
                + "</div>",
                1,
            )

    return page("PinCab Explorer", body)


@commander_bp.route("/tools/commander/download")
def tools_commander_download():
    root_name = request.args.get("root") or "Tables"
    rel = request.args.get("path") or ""

    try:
        root_name, root, target = pcx_resolve(root_name, rel)
    except Exception:
        return "Chemin invalide", 400

    if not target.exists() or not target.is_file():
        return "Fichier introuvable", 404

    return send_file(target, as_attachment=True, download_name=target.name)


@commander_bp.route("/tools/commander/duplicate", methods=["POST"])
def tools_commander_duplicate():
    root_name = request.form.get("root") or "Tables"
    rel = request.form.get("path") or ""

    try:
        root_name, root, current = pcx_resolve(root_name, rel)
        selected = pcx_selected()

        for item_rel in selected:
            name = pcx_clean_name(item_rel)
            src = (current / name).resolve()

            if not src.exists():
                continue
            if src != root and root not in src.parents:
                continue

            dst = pcx_unique(current / (src.stem + " - copie" + src.suffix))
            pcx_copy_any(src, dst)

            try:
                shutil.chown(dst, user="pinball", group="pinball")
                if dst.is_dir():
                    for p in dst.rglob("*"):
                        try:
                            shutil.chown(p, user="pinball", group="pinball")
                        except Exception:
                            pass
            except Exception:
                pass

    except Exception as e:
        print("PCX duplicate error:", e)

    return pcx_back(root_name, rel)


@commander_bp.route("/tools/commander/extract-zip", methods=["POST"])
def tools_commander_extract_zip():
    root_name = request.form.get("root") or "Tables"
    rel = request.form.get("path") or ""

    try:
        root_name, root, current = pcx_resolve(root_name, rel)
        selected = pcx_selected()

        for item_rel in selected:
            name = pcx_clean_name(item_rel)
            src = (current / name).resolve()

            if not src.exists() or not src.is_file():
                continue
            if src.suffix.lower() != ".zip":
                continue
            if src != root and root not in src.parents:
                continue

            dest = pcx_unique(current / src.stem)
            dest.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(src, "r") as z:
                for member in z.infolist():
                    member_name = str(member.filename or "").replace("\\", "/")
                    member_path = Path(member_name)

                    if not member_name or member_name.startswith("/") or ".." in member_path.parts:
                        continue

                    z.extract(member, dest)

            try:
                shutil.chown(dest, user="pinball", group="pinball")
                for p in dest.rglob("*"):
                    try:
                        shutil.chown(p, user="pinball", group="pinball")
                    except Exception:
                        pass
            except Exception:
                pass

    except Exception as e:
        print("PCX extract zip error:", e)

    return pcx_back(root_name, rel)


@commander_bp.route("/tools/commander/archive-selection", methods=["POST"])
def tools_commander_archive_selection():
    import zipfile
    from pathlib import Path
    from datetime import datetime

    root_name = request.form.get("root") or "Tables"
    rel = request.form.get("path") or ""

    try:
        root_name, root, current = pcx_resolve(root_name, rel)
        selected = pcx_selected()

        if not selected:
            return pcx_back(root_name, rel)

        archive_name = (request.form.get("archive_name") or "").strip()
        if archive_name.lower().endswith(".zip"):
            archive_name = archive_name[:-4].strip()

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

        if archive_name:
            safe_archive_name = "".join(
                c if c.isalnum() or c in ("-", "_", ".", " ") else "-"
                for c in archive_name
            )
            safe_archive_name = "-".join(safe_archive_name.split()).strip(".-_") or "pincabos-selection"
        else:
            safe_root_name = "".join(
                c if c.isalnum() or c in ("-", "_") else "-"
                for c in root_name
            ).strip("-") or "PinCabOS"
            safe_archive_name = f"pincabos-selection-{safe_root_name}"

        zip_name = f"{safe_archive_name}-{stamp}.zip"
        zip_path = pcx_unique(current / zip_name)

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            added = 0

            for item_rel in selected:
                name = pcx_clean_name(item_rel)
                src = (current / name).resolve()

                if not src.exists():
                    continue

                if src != root and root not in src.parents:
                    continue

                if src == zip_path:
                    continue

                if src.is_file():
                    z.write(src, src.name)
                    added += 1
                    continue

                if src.is_dir():
                    folder_name = src.name
                    z.writestr(folder_name.rstrip("/") + "/", "")

                    for p in sorted(src.rglob("*")):
                        try:
                            if not p.exists():
                                continue

                            if p.resolve() == zip_path:
                                continue

                            arc = Path(folder_name) / p.relative_to(src)
                            arc_name = str(arc).replace("\\", "/")

                            if p.is_dir():
                                z.writestr(arc_name.rstrip("/") + "/", "")
                            elif p.is_file():
                                z.write(p, arc_name)
                                added += 1
                        except Exception as e:
                            print("PCX archive skip:", p, e)

            if added == 0:
                z.writestr("README.txt", "Aucun fichier valide dans la sélection PinCabOS.\n")

        try:
            import shutil
            shutil.chown(zip_path, user="pinball", group="pinball")
        except Exception:
            pass

        print("PCX archive created:", zip_path)

    except Exception as e:
        print("PCX archive selection error:", e)

    return pcx_back(root_name, rel)


@commander_bp.route("/tools/commander/info", methods=["POST"])
def tools_commander_info():
    import stat

    root_name = request.form.get("root") or "Tables"
    rel = request.form.get("path") or ""

    try:
        root_name, root, current = pcx_resolve(root_name, rel)
        selected = pcx_selected()

        if selected:
            name = pcx_clean_name(selected[0])
            target = (current / name).resolve()
        else:
            target = current.resolve()

        if not target.exists():
            raise ValueError("Élément introuvable.")

        if target != root and root not in target.parents:
            raise ValueError("Chemin interdit.")

        st = target.stat()
        kind = "Dossier" if target.is_dir() else "Fichier"

        total_size = st.st_size
        files = 0
        folders = 0

        if target.is_dir():
            total_size = 0
            for p in target.rglob("*"):
                try:
                    if p.is_file():
                        files += 1
                        total_size += p.stat().st_size
                    elif p.is_dir():
                        folders += 1
                except Exception:
                    pass

        modified = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        permissions = stat.filemode(st.st_mode)

        body = f"""
<div class="card">
  <h2>Infos PinCab Explorer</h2>

  <p><strong>Type :</strong> {esc(kind)}</p>
  <p><strong>Nom :</strong> <code>{esc(target.name)}</code></p>
  <p><strong>Racine :</strong> <code>{esc(root_name)}</code></p>
  <p><strong>Chemin :</strong> <code>{esc(str(target))}</code></p>
  <p><strong>Taille :</strong> <code>{esc(pcx_size(total_size))}</code></p>
  <p><strong>Contenu :</strong> <code>{files} fichiers / {folders} dossiers</code></p>
  <p><strong>Permissions :</strong> <code>{esc(permissions)}</code></p>
  <p><strong>UID/GID :</strong> <code>{st.st_uid}:{st.st_gid}</code></p>
  <p><strong>Modifié :</strong> <code>{esc(modified)}</code></p>

  <p>
    <a class="button" href="/tools/commander?root={urllib.parse.quote(root_name)}&path={urllib.parse.quote(rel)}">Retour PinCab Explorer</a>
  </p>
</div>
"""
        return page("Infos PinCab Explorer", body)

    except Exception as e:
        body = f"""
<div class="card">
  <h2>Erreur infos PinCab Explorer</h2>
  <p class="bad">{esc(e)}</p>
  <p>
    <a class="button" href="/tools/commander?root={urllib.parse.quote(root_name)}&path={urllib.parse.quote(rel)}">Retour PinCab Explorer</a>
  </p>
</div>
"""
        return page("Infos PinCab Explorer", body)


@commander_bp.route("/tools/commander/create-folder", methods=["POST"])
def tools_commander_create_folder():
    root_name = request.form.get("root") or "Tables"
    rel = request.form.get("path") or ""
    folder_name = request.form.get("folder_name") or ""

    try:
        root_name, root, current = pcx_resolve(root_name, rel)
        folder_name = pcx_clean_name(folder_name)
        target = (current / folder_name).resolve()

        if target != root and root not in target.parents:
            raise ValueError("Chemin interdit.")

        target.mkdir(parents=False, exist_ok=False)
    except Exception as e:
        print("PCX create-folder error:", e)

    return pcx_back(root_name, rel)


@commander_bp.route("/tools/commander/upload", methods=["POST"])
def tools_commander_upload():
    root_name = request.form.get("root") or "Tables"
    rel = request.form.get("path") or ""

    try:
        root_name, root, current = pcx_resolve(root_name, rel)

        files = request.files.getlist("files")
        for upload in files:
            if not upload or not upload.filename:
                continue

            filename = secure_filename(upload.filename)
            if not filename:
                continue

            target = (current / filename).resolve()

            if target != root and root not in target.parents:
                raise ValueError("Chemin interdit.")

            if target.exists():
                target = pcx_unique(target)

            upload.save(target)
    except Exception as e:
        print("PCX upload error:", e)

    return pcx_back(root_name, rel)


# PINCABOS_PCX_EXTRACT_SCRIPT_ROUTE_V5
@commander_bp.route("/tools/commander/extract-script", methods=["POST"])
def tools_commander_extract_script():
    import os
    import re
    import shutil
    import subprocess
    import time
    from pathlib import Path

    root_name = request.form.get("root") or "Tables"
    rel = request.form.get("path") or ""
    target = None
    expected_vbs = None
    backup_vbs = None
    status = 400
    title = "Extraction du script refusée"
    output = ""
    started = time.time()

    try:
        root_name, root, current = pcx_resolve(root_name, rel)

        if root_name != "Tables":
            raise ValueError("L'extraction est permise seulement dans Tables.")

        selected = pcx_selected()

        if len(selected) != 1:
            raise ValueError("Sélectionne exactement une table .vpx.")

        target = (root / selected[0]).resolve()

        if target == root or root not in target.parents:
            raise ValueError("Chemin de table interdit.")

        if not target.is_file() or target.suffix.lower() != ".vpx":
            raise ValueError("Sélectionne un fichier .vpx.")

        running = subprocess.run(
            ["pgrep", "-u", "pinball", "-f", "VPinballX|VPinballX_BGFX"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

        if running.returncode == 0:
            raise ValueError(
                "VPX est actif. Ferme la table avant d'extraire son script."
            )

        launcher_cfg = Path("/opt/pincabos/scripts/VPXlauncher.sh")

        if not launcher_cfg.is_file():
            raise RuntimeError("Configuration VPXlauncher absente.")

        launcher_text = launcher_cfg.read_text(
            encoding="utf-8",
            errors="replace",
        )

        match = re.search(
            r'^\s*VPX_MAIN="([^"]+)"',
            launcher_text,
            re.MULTILINE,
        )

        if not match:
            raise RuntimeError("VPX_MAIN introuvable dans VPXlauncher.")

        vpx_binary = Path(match.group(1)).expanduser()

        if not vpx_binary.is_file() or not os.access(vpx_binary, os.X_OK):
            raise RuntimeError(
                f"Binaire VPX direct introuvable: {vpx_binary}"
            )

        direct_cmd = [str(vpx_binary), "-ExtractVBS", str(target)]
        run_env = None

        if os.geteuid() == 0:
            runuser = shutil.which("runuser")

            if not runuser:
                raise RuntimeError("runuser absent.")

            cmd = [
                runuser,
                "-u",
                "pinball",
                "--",
                "/usr/bin/env",
                "HOME=/home/pinball",
                "USER=pinball",
                "LOGNAME=pinball",
                "DISPLAY=:0",
                "XAUTHORITY=/home/pinball/.Xauthority",
                "XDG_RUNTIME_DIR=/run/user/1000",
                "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus",
            ] + direct_cmd
        else:
            cmd = direct_cmd
            run_env = os.environ.copy()
            run_env.update(
                {
                    "HOME": "/home/pinball",
                    "USER": "pinball",
                    "LOGNAME": "pinball",
                    "DISPLAY": ":0",
                    "XAUTHORITY": "/home/pinball/.Xauthority",
                    "XDG_RUNTIME_DIR": "/run/user/1000",
                    "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
                }
            )

        expected_vbs = target.with_suffix(".vbs")

        if expected_vbs.exists():
            backup_vbs = (
                Path("/opt/pincabos/backups/pcx-script-extract")
                / time.strftime("%Y%m%d-%H%M%S")
                / target.parent.name
                / expected_vbs.name
            )
            backup_vbs.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(expected_vbs, backup_vbs)

        result = subprocess.run(
            cmd,
            cwd=str(target.parent),
            env=run_env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=180,
            check=False,
        )

        command_output = (result.stdout or "").strip()[-12000:]

        if result.returncode != 0:
            raise RuntimeError(
                command_output
                or f"VPinballX a retourné le code {result.returncode}."
            )

        if not expected_vbs.is_file() or expected_vbs.stat().st_size < 1000:
            raise RuntimeError(
                "VPinballX n'a pas produit de script VBS valide."
            )

        try:
            shutil.chown(expected_vbs, user="pinball", group="pinball")
            expected_vbs.chmod(0o664)
        except Exception:
            pass

        status = 200
        title = "Script extrait"
        output = (
            f"OK: {expected_vbs}\n"
            f"Taille: {expected_vbs.stat().st_size} octets\n"
            f"Backup VBS précédent: {backup_vbs or '(aucun)'}\n"
            "B2S: non modifié\n\n"
            f"{command_output}"
        )

    except ValueError as exc:
        output = str(exc)

    except subprocess.TimeoutExpired:
        status = 504
        title = "Extraction expirée"
        output = "VPX a dépassé le délai prévu pendant l'extraction."

    except Exception as exc:
        status = 500
        title = "Extraction du script en erreur"
        output = str(exc)

        try:
            if backup_vbs and backup_vbs.is_file() and expected_vbs:
                shutil.copy2(backup_vbs, expected_vbs)
            elif (
                expected_vbs
                and expected_vbs.exists()
                and expected_vbs.stat().st_mtime >= started - 1
            ):
                expected_vbs.unlink()
        except Exception:
            pass

    back_url = (
        "/tools/commander?root="
        + urllib.parse.quote(root_name)
        + "&path="
        + urllib.parse.quote(rel)
    )

    target_text = str(target) if target else "Aucune table valide"

    body = (
        '<div class="card">'
        '<h2>' + esc(title) + '</h2>'
        '<p><strong>Table :</strong> <code>'
        + esc(target_text)
        + '</code></p>'
        '<pre style="white-space:pre-wrap;max-height:55vh;overflow:auto;">'
        + esc(output or "Aucune sortie.")
        + '</pre>'
        '<p><a class="button secondary" href="'
        + back_url
        + '">Retour PinCab Explorer</a></p>'
        '</div>'
    )

    return page(title, body), status


@commander_bp.route("/tools/commander/delete", methods=["POST"])
def tools_commander_delete():
    root_name = request.form.get("root") or "Tables"
    rel = request.form.get("path") or ""
    selected = pcx_selected()

    try:
        root_name, root, current = pcx_resolve(root_name, rel)

        for item_rel in selected:
            target = (root / item_rel).resolve()

            if target == root or root not in target.parents:
                continue

            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
    except Exception as e:
        print("PCX delete error:", e)

    return pcx_back(root_name, rel)


@commander_bp.route("/tools/commander/rename", methods=["POST"])
def tools_commander_rename():
    root_name = request.form.get("root") or "Tables"
    rel = request.form.get("path") or ""
    selected = pcx_selected()
    new_name = request.form.get("new_name") or ""

    try:
        if len(selected) != 1:
            raise ValueError("Sélectionne un seul élément.")

        root_name, root, current = pcx_resolve(root_name, rel)

        src = (root / selected[0]).resolve()
        if src == root or root not in src.parents or not src.exists():
            raise ValueError("Source invalide.")

        new_name = pcx_clean_name(new_name)
        dst = (src.parent / new_name).resolve()

        if dst == root or root not in dst.parents:
            raise ValueError("Destination invalide.")

        if dst.exists():
            raise ValueError("Existe déjà.")

        src.rename(dst)
    except Exception as e:
        print("PCX rename error:", e)

    return pcx_back(root_name, rel)


@commander_bp.route("/tools/commander/clipboard", methods=["POST"])
def tools_commander_clipboard():
    root_name = request.form.get("root") or "Tables"
    rel = request.form.get("path") or ""
    mode = request.form.get("mode") or "copy"
    selected = pcx_selected()

    try:
        if mode not in ["copy", "cut"]:
            mode = "copy"

        root_name, root, current = pcx_resolve(root_name, rel)

        valid = []
        for item_rel in selected:
            target = (root / item_rel).resolve()
            if target != root and root in target.parents and target.exists():
                valid.append(item_rel)

        clip = {
            "mode": mode,
            "root": root_name,
            "items": valid,
        }

        clip_path = Path("/home/pinball/Downloads/commander-clipboard.json")
        clip_path.parent.mkdir(parents=True, exist_ok=True)
        pincabos_write_json_with_meta(clip_path, clip, "Commander Clipboard")
    except Exception as e:
        print("PCX clipboard error:", e)

    return pcx_back(root_name, rel)


@commander_bp.route("/tools/commander/paste", methods=["POST"])
def tools_commander_paste():
    root_name = request.form.get("root") or "Tables"
    rel = request.form.get("path") or ""

    try:
        dst_root_name, dst_root, dst_current = pcx_resolve(root_name, rel)

        clip_path = Path("/home/pinball/Downloads/commander-clipboard.json")
        if not clip_path.exists():
            raise ValueError("Clipboard vide.")

        clip = json.loads(clip_path.read_text())
        src_root_name = clip.get("root")
        mode = clip.get("mode", "copy")
        items = clip.get("items", [])

        src_root_name, src_root, _ = pcx_resolve(src_root_name, "")

        for item_rel in items:
            src = (src_root / item_rel).resolve()

            if src == src_root or src_root not in src.parents or not src.exists():
                continue

            dst = (dst_current / src.name).resolve()

            if dst == dst_root or dst_root not in dst.parents:
                continue

            if dst.exists():
                dst = pcx_unique(dst)

            if mode == "cut":
                shutil.move(str(src), str(dst))
            else:
                pcx_copy_any(src, dst)

        if mode == "cut":
            clip_path.unlink(missing_ok=True)
    except Exception as e:
        print("PCX paste error:", e)

    return pcx_back(root_name, rel)


def _pcx_lv_html(value):
    from html import escape
    return escape(str(value), quote=True)


def _pcx_lv_url(endpoint, root_name, rel_path, extra=None):
    from urllib.parse import urlencode

    query = {
        "root": str(root_name),
        "path": str(rel_path),
    }

    if extra:
        query.update(extra)

    return endpoint + "?" + urlencode(query)


def _pcx_lv_resolve(root_name, rel_path):
    from pathlib import Path

    resolved_root_name, root, target = pcx_resolve(root_name, rel_path)

    if not target.exists() or not target.is_file():
        raise FileNotFoundError("Fichier introuvable.")

    if target.is_symlink():
        raise PermissionError("Les liens symboliques ne sont pas ouverts.")

    root_real = Path(root).resolve(strict=True)
    target_real = Path(target).resolve(strict=True)

    try:
        target_real.relative_to(root_real)
    except ValueError as exc:
        raise PermissionError("Fichier hors racine PinCab Explorer.") from exc

    rel_clean = str(target_real.relative_to(root_real))

    return resolved_root_name, root_real, target_real, rel_clean


def _pcx_lv_sha256(raw):
    import hashlib
    return hashlib.sha256(raw).hexdigest()


def _pcx_lv_newline(raw):
    if b"\r\n" in raw:
        return "CRLF"
    return "LF"


def _pcx_lv_decode(raw):
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig"), "utf-8-sig"

    try:
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        pass

    try:
        return raw.decode("cp1252"), "cp1252"
    except UnicodeDecodeError:
        return raw.decode("latin-1"), "latin-1"


def _pcx_lv_encode(text, encoding, newline):
    allowed = {"utf-8", "utf-8-sig", "cp1252", "latin-1"}

    if encoding not in allowed:
        encoding = "utf-8"

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")

    if newline == "CRLF":
        normalized = normalized.replace("\n", "\r\n")

    return normalized.encode(encoding)


def _pcx_lv_is_text(target):
    text_ext = {
        ".ini", ".cfg", ".conf", ".txt", ".log", ".vbs", ".vbe",
        ".json", ".xml", ".yaml", ".yml", ".csv", ".tsv", ".md",
        ".py", ".sh", ".bash", ".zsh", ".bat", ".cmd", ".ps1",
        ".info", ".pup", ".pupplaylist", ".puptriggers", ".html",
        ".htm", ".css", ".js", ".lua", ".sql", ".m3u", ".m3u8",
    }

    blocked_ext = {
        ".vpx", ".directb2s", ".zip", ".7z", ".rar", ".tar",
        ".gz", ".xz", ".iso", ".img", ".exe", ".dll", ".so",
        ".bin", ".rom", ".nv", ".dat",
    }

    suffix = target.suffix.lower()

    if suffix in blocked_ext:
        return False

    try:
        if target.stat().st_size > 4 * 1024 * 1024:
            return False

        head = target.read_bytes()[:8192]
    except Exception:
        return False

    if b"\x00" in head:
        return False

    if suffix in text_ext:
        return True

    try:
        head.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def _pcx_lv_kind(target):
    suffix = target.suffix.lower()

    images = {
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg",
    }

    audio = {
        ".mp3", ".wav", ".ogg", ".oga", ".m4a", ".aac", ".flac",
    }

    video = {
        ".mp4", ".webm", ".ogv", ".mov", ".mkv", ".avi",
    }

    if suffix in images:
        return "image"

    if suffix in audio:
        return "audio"

    if suffix in video:
        return "video"

    if suffix == ".pdf":
        return "pdf"

    if _pcx_lv_is_text(target):
        return "text"

    return "binary"


def _pcx_lv_backup(root_name, rel_clean, old_bytes):
    from datetime import datetime
    from pathlib import Path

    safe_root = "".join(
        char if char.isalnum() or char in " ._-"
        else "_"
        for char in str(root_name)
    ).strip() or "Root"

    backup_root = (
        Path("/home/pinball/.local/share/pincabos/editor-backups")
        / safe_root
    )

    rel_path = Path(rel_clean)
    backup_dir = backup_root / rel_path.parent
    backup_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_file = backup_dir / f"{rel_path.name}.{stamp}.bak"

    backup_file.write_bytes(old_bytes)
    backup_file.chmod(0o600)

    return backup_file


def _pcx_lv_atomic_write(target, root_name, rel_clean, old_bytes, new_bytes):
    import os
    import stat
    import uuid

    file_stat = target.stat()

    if file_stat.st_uid != os.geteuid():
        raise PermissionError(
            "Le fichier n'appartient pas au compte pinball; "
            "son proprietaire est conserve par securite."
        )

    if not os.access(target, os.W_OK):
        raise PermissionError("Le fichier n'est pas inscriptible par pinball.")

    backup_file = _pcx_lv_backup(root_name, rel_clean, old_bytes)

    temp_file = target.parent / (
        "." + target.name + ".pincabos-edit-" + uuid.uuid4().hex
    )

    try:
        with open(temp_file, "xb") as handle:
            handle.write(new_bytes)
            handle.flush()
            os.fsync(handle.fileno())

        os.chmod(temp_file, stat.S_IMODE(file_stat.st_mode))
        os.replace(temp_file, target)

    except Exception:
        try:
            temp_file.unlink(missing_ok=True)
        except Exception:
            pass
        raise

    return backup_file


def _pcx_lv_render_editor(
    root_name,
    root,
    target,
    rel_clean,
    content,
    encoding,
    newline,
    sha256,
    notice="",
    error="",
    allow_save=True,
):
    view_url = _pcx_lv_url(
        "/tools/commander/live",
        root_name,
        rel_clean,
    )

    back_url = (
        "/tools/commander?"
        + _pcx_lv_url("", root_name, str(target.parent.relative_to(root))).lstrip("?")
    )

    save_disabled = "" if allow_save else "disabled"

    notice_html = ""
    if notice:
        notice_html = (
            '<p class="ok pcx-lv-message">'
            + _pcx_lv_html(notice)
            + "</p>"
        )

    error_html = ""
    if error:
        error_html = (
            '<p class="bad pcx-lv-message">'
            + _pcx_lv_html(error)
            + "</p>"
        )

    body = (
        '<div class="card pcx-live-editor">'
        '<div class="pcx-live-title">'
        '<div>'
        '<h2>📝 Éditeur direct</h2>'
        '<p><strong>' + _pcx_lv_html(target.name) + '</strong></p>'
        '<p class="muted"><code>' + _pcx_lv_html(str(target)) + '</code></p>'
        '</div>'
        '<div class="pcx-live-actions">'
        '<a class="button secondary" href="' + _pcx_lv_html(back_url) + '">← Retour</a>'
        '<a class="button secondary" href="' + _pcx_lv_html(view_url) + '">↻ Recharger</a>'
        '</div>'
        '</div>'
        + notice_html
        + error_html
        + '<form method="post" action="/tools/commander/live/save" id="pcx-live-form">'
        '<input type="hidden" name="root" value="' + _pcx_lv_html(root_name) + '">'
        '<input type="hidden" name="path" value="' + _pcx_lv_html(rel_clean) + '">'
        '<input type="hidden" name="sha256" value="' + _pcx_lv_html(sha256) + '">'
        '<input type="hidden" name="encoding" value="' + _pcx_lv_html(encoding) + '">'
        '<input type="hidden" name="newline" value="' + _pcx_lv_html(newline) + '">'
        '<div class="pcx-live-toolbar">'
        '<button class="button" type="submit" ' + save_disabled + '>💾 Enregistrer</button>'
        '<button class="button secondary" type="button" id="pcx-lv-select">☑ Tout sélectionner</button>'
        '<button class="button secondary" type="button" id="pcx-lv-copy">📋 Copier tout</button>'
        '<button class="button secondary" type="button" id="pcx-lv-paste">📌 Coller</button>'
        '<input id="pcx-lv-find" type="search" placeholder="Rechercher…">'
        '<button class="button secondary" type="button" id="pcx-lv-next">🔎 Suivant</button>'
        '<input id="pcx-lv-replace" type="text" placeholder="Remplacer par…">'
        '<button class="button secondary" type="button" id="pcx-lv-replace-one">↪ Remplacer</button>'
        '<button class="button secondary" type="button" id="pcx-lv-replace-all">⇄ Tout remplacer</button>'
        '</div>'
        '<textarea id="pcx-live-content" name="content" spellcheck="false">'
        + _pcx_lv_html(content)
        + '</textarea>'
        '<p class="muted">'
        'Ctrl+S : enregistrer · Ctrl+F : rechercher · '
        'Ctrl+C / Ctrl+V : copier-coller · '
        'Une sauvegarde est créée avant chaque enregistrement.'
        '</p>'
        '</form>'
        '</div>'
        '<style>'
        '.pcx-live-editor{max-width:1800px;margin:20px auto;}'
        '.pcx-live-title{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;flex-wrap:wrap;}'
        '.pcx-live-actions,.pcx-live-toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;}'
        '.pcx-live-toolbar{margin:18px 0;}'
        '.pcx-live-toolbar input{background:#0c0d10;color:#fff;border:1px solid #5d3a08;border-radius:7px;padding:9px 10px;min-width:150px;}'
        '#pcx-live-content{width:100%;min-height:68vh;box-sizing:border-box;resize:vertical;'
        'background:#07080a;color:#e9edf2;border:1px solid #614009;border-radius:8px;'
        'padding:16px;font:15px/1.45 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;tab-size:4;}'
        '.pcx-lv-message{padding:10px 12px;border-radius:8px;}'
        '.muted{opacity:.78;word-break:break-word;}'
        '@media(max-width:900px){.pcx-live-toolbar input{min-width:120px}.pcx-live-toolbar .button{font-size:.9em}}'
        '</style>'
        '<script>'
        '(function(){'
        'const area=document.getElementById("pcx-live-content");'
        'const find=document.getElementById("pcx-lv-find");'
        'const replace=document.getElementById("pcx-lv-replace");'
        'let lastIndex=-1;'
        'function selectRange(start,end){area.focus();area.setSelectionRange(start,end);area.scrollTop=Math.max(0,(start/Math.max(1,area.value.length))*area.scrollHeight-180);}'
        'function findNext(){const needle=find.value;if(!needle){find.focus();return false;}const value=area.value;let start=area.selectionEnd;if(start===lastIndex){start=lastIndex+needle.length;}let pos=value.indexOf(needle,start);if(pos<0){pos=value.indexOf(needle,0);}if(pos<0){alert("Texte introuvable.");return false;}lastIndex=pos;selectRange(pos,pos+needle.length);return true;}'
        'document.getElementById("pcx-lv-select").onclick=function(){area.focus();area.select();};'
        'document.getElementById("pcx-lv-copy").onclick=function(){area.focus();area.select();try{document.execCommand("copy");}catch(e){};};'
        'document.getElementById("pcx-lv-paste").onclick=async function(){area.focus();try{if(navigator.clipboard&&navigator.clipboard.readText){const t=await navigator.clipboard.readText();const a=area.selectionStart,b=area.selectionEnd;area.setRangeText(t,a,b,"end");}else{alert("Utilise Ctrl+V dans la zone de texte.");}}catch(e){alert("Utilise Ctrl+V dans la zone de texte.");}};'
        'document.getElementById("pcx-lv-next").onclick=findNext;'
        'document.getElementById("pcx-lv-replace-one").onclick=function(){const needle=find.value;if(!needle){find.focus();return;}const a=area.selectionStart,b=area.selectionEnd;if(area.value.slice(a,b)!==needle&&!findNext()){return;}area.setRangeText(replace.value,area.selectionStart,area.selectionEnd,"end");lastIndex=-1;};'
        'document.getElementById("pcx-lv-replace-all").onclick=function(){const needle=find.value;if(!needle){find.focus();return;}area.value=area.value.split(needle).join(replace.value);lastIndex=-1;};'
        'document.addEventListener("keydown",function(e){if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="s"){e.preventDefault();document.getElementById("pcx-live-form").requestSubmit();}if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="f"){e.preventDefault();find.focus();find.select();}});'
        '})();'
        '</script>'
    )

    return page("Éditeur PinCab Explorer", body)


@commander_bp.route("/tools/commander/live")
def tools_commander_live():
    from flask import abort, request

    root_name = request.args.get("root") or "Tables"
    rel_path = request.args.get("path") or ""

    try:
        root_name, root, target, rel_clean = _pcx_lv_resolve(
            root_name,
            rel_path,
        )
    except FileNotFoundError:
        abort(404)
    except Exception:
        abort(403)

    kind = _pcx_lv_kind(target)

    stream_url = _pcx_lv_url(
        "/tools/commander/live/file",
        root_name,
        rel_clean,
    )

    download_url = _pcx_lv_url(
        "/tools/commander/download",
        root_name,
        rel_clean,
    )

    back_rel = str(target.parent.relative_to(root))
    back_url = (
        "/tools/commander?"
        + _pcx_lv_url("", root_name, back_rel).lstrip("?")
    )

    if kind == "text":
        raw = target.read_bytes()
        content, encoding = _pcx_lv_decode(raw)

        return _pcx_lv_render_editor(
            root_name,
            root,
            target,
            rel_clean,
            content,
            encoding,
            _pcx_lv_newline(raw),
            _pcx_lv_sha256(raw),
            notice=(
                "Fichier enregistré."
                if request.args.get("saved") == "1"
                else ""
            ),
        )

    title = _pcx_lv_html(target.name)
    file_path = _pcx_lv_html(str(target))

    viewer = (
        '<div class="card" style="max-width:1800px;margin:20px auto;">'
        '<p><a class="button secondary" href="' + _pcx_lv_html(back_url) + '">← Retour Explorer</a> '
        '<a class="button secondary" href="' + _pcx_lv_html(download_url) + '">⬇ Télécharger</a></p>'
        '<h2>👁 Vue : ' + title + '</h2>'
        '<p class="muted"><code>' + file_path + '</code></p>'
    )

    if kind == "image":
        viewer += (
            '<div style="text-align:center;background:#050506;padding:15px;border-radius:10px;">'
            '<img src="' + _pcx_lv_html(stream_url) + '" '
            'style="max-width:100%;max-height:78vh;object-fit:contain;" '
            'alt="' + title + '">'
            '</div>'
        )

    elif kind == "audio":
        viewer += (
            '<audio controls preload="metadata" style="width:100%;margin-top:20px;">'
            '<source src="' + _pcx_lv_html(stream_url) + '">'
            'Lecture audio non supportée par ce navigateur.'
            '</audio>'
        )

    elif kind == "video":
        viewer += (
            '<video controls preload="metadata" playsinline '
            'style="width:100%;max-height:78vh;background:#000;border-radius:10px;">'
            '<source src="' + _pcx_lv_html(stream_url) + '">'
            'Lecture vidéo non supportée par ce navigateur.'
            '</video>'
        )

    elif kind == "pdf":
        viewer += (
            '<iframe src="' + _pcx_lv_html(stream_url) + '" '
            'style="width:100%;height:78vh;border:1px solid #5d3a08;border-radius:10px;"></iframe>'
        )

    else:
        viewer += (
            '<div class="card" style="margin-top:18px;">'
            '<h3>Fichier binaire</h3>'
            '<p>Ce type de fichier ne peut pas être édité de façon sécuritaire dans PinCab Explorer.</p>'
            '<p>Utilise Télécharger pour l’ouvrir avec un outil adapté.</p>'
            '</div>'
        )

    viewer += '</div>'

    return page("Vue PinCab Explorer", viewer)


@commander_bp.route("/tools/commander/live/file")
def tools_commander_live_file():
    import mimetypes
    from flask import abort, request, send_file

    root_name = request.args.get("root") or "Tables"
    rel_path = request.args.get("path") or ""

    try:
        _, _, target, _ = _pcx_lv_resolve(root_name, rel_path)
    except FileNotFoundError:
        abort(404)
    except Exception:
        abort(403)

    mime_type = mimetypes.guess_type(str(target))[0]

    if target.suffix.lower() in {".ini", ".cfg", ".conf", ".vbs", ".vbe"}:
        mime_type = "text/plain; charset=utf-8"

    return send_file(
        str(target),
        mimetype=mime_type or "application/octet-stream",
        as_attachment=False,
        conditional=True,
    )


@commander_bp.route("/tools/commander/live/save", methods=["POST"])
def tools_commander_live_save():
    from flask import abort, request, redirect

    root_name = request.form.get("root") or "Tables"
    rel_path = request.form.get("path") or ""
    expected_sha = request.form.get("sha256") or ""
    encoding = request.form.get("encoding") or "utf-8"
    newline = request.form.get("newline") or "LF"
    content = request.form.get("content") or ""

    try:
        root_name, root, target, rel_clean = _pcx_lv_resolve(
            root_name,
            rel_path,
        )
    except FileNotFoundError:
        abort(404)
    except Exception:
        abort(403)

    if not _pcx_lv_is_text(target):
        abort(403)

    old_bytes = target.read_bytes()
    actual_sha = _pcx_lv_sha256(old_bytes)

    if actual_sha != expected_sha:
        return _pcx_lv_render_editor(
            root_name,
            root,
            target,
            rel_clean,
            content,
            encoding,
            newline,
            actual_sha,
            error=(
                "Le fichier a été modifié depuis son ouverture. "
                "Ton texte est conservé ci-dessous, mais l'enregistrement "
                "est bloqué pour éviter d'écraser une modification externe. "
                "Copie ton texte, puis recharge le fichier."
            ),
            allow_save=False,
        ), 409

    try:
        new_bytes = _pcx_lv_encode(content, encoding, newline)
    except UnicodeEncodeError as exc:
        return _pcx_lv_render_editor(
            root_name,
            root,
            target,
            rel_clean,
            content,
            encoding,
            newline,
            actual_sha,
            error="Encodage impossible : " + str(exc),
            allow_save=False,
        ), 400

    if len(new_bytes) > 4 * 1024 * 1024:
        return _pcx_lv_render_editor(
            root_name,
            root,
            target,
            rel_clean,
            content,
            encoding,
            newline,
            actual_sha,
            error="Le fichier dépasse la limite d'édition de 4 Mo.",
            allow_save=False,
        ), 413

    try:
        _pcx_lv_atomic_write(
            target,
            root_name,
            rel_clean,
            old_bytes,
            new_bytes,
        )
    except Exception as exc:
        return _pcx_lv_render_editor(
            root_name,
            root,
            target,
            rel_clean,
            content,
            encoding,
            newline,
            actual_sha,
            error="Enregistrement refusé : " + str(exc),
            allow_save=False,
        ), 403

    return redirect(
        _pcx_lv_url(
            "/tools/commander/live",
            root_name,
            rel_clean,
            {"saved": "1"},
        )
    )


@commander_bp.after_app_request
def pincabos_pcx_live_view_column(response):
    # PINCABOS_COMMANDER_ZERO_BACKGROUND_V1_NO_DOM_ENHANCER
    # Les boutons ajoutés après le rendu sont désactivés.
    return response
    try:
        from flask import request as _request

        if _request.path.rstrip("/") != "/tools/commander":
            return response

        if response.status_code != 200 or response.is_streamed:
            return response

        if response.mimetype != "text/html":
            return response

        body = response.get_data(as_text=True)

        if 'data-pcx-live-view-script="1"' in body:
            return response

        script = r'''
<script data-pcx-live-view-script="1">
(function() {
  function buildViewUrl(downloadLink) {
    try {
      const parsed = new URL(downloadLink.href, window.location.href);
      const root = parsed.searchParams.get("root");
      const path = parsed.searchParams.get("path");

      if (!root || path === null) {
        return null;
      }

      return "/tools/commander/live?root="
        + encodeURIComponent(root)
        + "&path="
        + encodeURIComponent(path);
    } catch (error) {
      return null;
    }
  }

  function openViewer(url) {
    const popup = window.open(url, "_blank", "noopener,noreferrer");

    if (!popup) {
      window.location.href = url;
    }
  }

  function makeButton(url) {
    const button = document.createElement("button");

    button.type = "button";
    button.className = "button secondary";
    button.textContent = "👁 Vue";
    button.title = "Ouvrir aperçu, lecteur média ou éditeur";
    button.style.whiteSpace = "nowrap";

    button.addEventListener("click", function() {
      openViewer(url);
    });

    return button;
  }

  function addTableColumn() {
    const tables = Array.from(document.querySelectorAll("table"));

    const table = tables.find(function(candidate) {
      return /actions/i.test(candidate.textContent || "");
    });

    if (!table) {
      return;
    }

    const headerRow =
      table.querySelector("thead tr")
      || table.querySelector("tr");

    if (!headerRow || headerRow.querySelector("[data-pcx-live-view-head]")) {
      return;
    }

    const header = document.createElement("th");
    header.textContent = "Vue";
    header.setAttribute("data-pcx-live-view-head", "1");
    header.style.whiteSpace = "nowrap";
    headerRow.appendChild(header);

    let rows = Array.from(table.querySelectorAll("tbody tr"));

    if (!rows.length) {
      rows = Array.from(table.querySelectorAll("tr"))
        .filter(function(row) {
          return row !== headerRow;
        });
    }

    rows.forEach(function(row) {
      if (row.querySelector("[data-pcx-live-view-cell]")) {
        return;
      }

      const cell = document.createElement("td");
      cell.setAttribute("data-pcx-live-view-cell", "1");
      cell.style.whiteSpace = "nowrap";

      const download = row.querySelector(
        'a[href*="/tools/commander/download"]'
      );

      if (download) {
        const url = buildViewUrl(download);

        if (url) {
          cell.appendChild(makeButton(url));
        }
      }

      row.appendChild(cell);
    });
  }

  function addGridButtons() {
    document.querySelectorAll(
      'a[href*="/tools/commander/download"]'
    ).forEach(function(download) {
      if (download.closest("table")) {
        return;
      }

      if (download.parentElement.querySelector("[data-pcx-live-grid-button]")) {
        return;
      }

      const url = buildViewUrl(download);

      if (!url) {
        return;
      }

      const button = makeButton(url);
      button.setAttribute("data-pcx-live-grid-button", "1");
      button.style.marginLeft = "7px";
      download.insertAdjacentElement("afterend", button);
    });
  }

  function install() {
    addTableColumn();
    addGridButtons();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", install);
  } else {
    install();
  }
})();
</script>
'''

        if "</body>" in body:
            body = body.replace("</body>", script + "\n</body>", 1)
        else:
            body += script

        response.set_data(body)
        return response

    except Exception:
        return response


def register(app, page_fn):
    """Enregistre le Commander et sa visionneuse live sur l'application."""
    global page
    page = page_fn
    app.register_blueprint(commander_bp)
