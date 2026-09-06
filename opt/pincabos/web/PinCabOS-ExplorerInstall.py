# PinCabOS-ExplorerInstall.py
# Remplace Vue par Installer dans PinCab Explorer pour les fichiers .PinCabOS complets.
# N'affecte pas les .PinCabOS.part.

from pathlib import Path
from flask import request, current_app
import html as _html
import os
import re
import shutil
import subprocess
import tempfile
import urllib.parse
import zipfile


TABLES_ROOT = Path("/home/pinball/Tables")

SAFE_ROOTS = {
    "Tables": Path("/home/pinball/Tables"),
    "Exports": Path("/home/pinball/Exports"),
    "Imports": Path("/home/pinball/Imports"),
    "Home Pinball": Path("/home/pinball"),
    "Logs": Path("/opt/pincabos/logs"),
    "Backups": Path("/opt/pincabos/web/backups"),
    "Medias": Path("/home/pinball/Medias"),
    "Media": Path("/home/pinball/Media"),
    "PinCabShare": Path("/home/pinball/PinCabShare"),
    "Clés USB": Path("/media/pinball"),
    "Lecteurs SMB": Path("/home/pinball/NetworkDrives"),
}

_CTX = {}


def _safe_join(base, rel):
    base = Path(base)
    rel = (rel or "").lstrip("/")

    target = base / rel

    base_abs = os.path.abspath(str(base))
    target_abs = os.path.abspath(str(target))

    try:
        if os.path.commonpath([base_abs, target_abs]) != base_abs:
            return None
    except Exception:
        return None

    return Path(target_abs)


def _source_from_request():
    root_name = request.args.get("root", "").strip()
    rel = request.args.get("path", "").strip()

    base = SAFE_ROOTS.get(root_name)
    if not base:
        return None, f"Racine PinCab Explorer non autorisée: {root_name or 'vide'}"

    src = _safe_join(base, rel)
    if src is None:
        return None, "Chemin invalide."

    if not src.exists() or not src.is_file():
        return None, f"Fichier introuvable: {src}"

    name = src.name.lower()
    if not name.endswith(".pincabos") or name.endswith(".pincabos.part"):
        return None, "Seuls les fichiers .PinCabOS complets peuvent être installés."

    return src, ""


def _safe_zip_members(zf):
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        if not name or name.startswith("/") or "/../" in ("/" + name):
            raise RuntimeError(f"Archive dangereuse: {info.filename}")
        yield info


def _guess_table_folder(archive_path):
    # Utilise le moteur manifest existant de app.py si disponible.
    from pincabos_webapp_import import pincabos_manifest_table_folder_from_archive as fn  # PINCABOS_WEBAPP_AUTONOMIE_V1
    if callable(fn):
        try:
            table_folder, _manifest = fn(Path(archive_path))
            if table_folder:
                return str(table_folder).strip().strip("/")
        except Exception:
            pass

    # Fallback: top-level unique du ZIP, sinon nom du fichier.
    with zipfile.ZipFile(archive_path) as zf:
        tops = []
        for info in _safe_zip_members(zf):
            name = info.filename.replace("\\", "/").strip("/")
            if not name:
                continue
            tops.append(name.split("/", 1)[0])

        unique = sorted(set(tops))
        if len(unique) == 1 and unique[0]:
            return unique[0]

    return Path(archive_path).name[:-len(".PinCabOS")]


def _copy_tree_contents(src_dir, dst_dir):
    dst_dir.mkdir(parents=True, exist_ok=True)

    for child in Path(src_dir).iterdir():
        target = dst_dir / child.name
        if child.is_dir():
            shutil.copytree(child, target, symlinks=True)
        else:
            shutil.copy2(child, target)


def _install_archive(page, esc):
    src, err = _source_from_request()
    if err:
        return page("Installer PinCabOS", f"""
<div class="card">
  <h2>Installation impossible</h2>
  <p class="bad">{esc(err)}</p>
  <p><a class="button" href="/tools/commander?root=Lecteurs%20SMB">Retour PinCab Explorer</a></p>
</div>
""")

    if not zipfile.is_zipfile(src):
        return page("Installer PinCabOS", f"""
<div class="card">
  <h2>Installation impossible</h2>
  <p class="bad">Le fichier n'est pas une archive PinCabOS valide.</p>
  <pre>{esc(str(src))}</pre>
  <p><a class="button" href="/tools/commander?root=Lecteurs%20SMB">Retour PinCab Explorer</a></p>
</div>
""")

    table_folder = _guess_table_folder(src)
    table_folder = table_folder.replace("\\", "/").strip("/")

    if not table_folder or "/" in table_folder or table_folder in {".", ".."}:
        table_folder = src.name[:-len(".PinCabOS")]

    dst = TABLES_ROOT / table_folder

    if dst.exists():
        return page("Installer PinCabOS", f"""
<div class="card">
  <h2>Table déjà présente</h2>
  <p class="bad">La table existe déjà dans <code>{esc(str(dst))}</code>.</p>
  <p>Pour l’instant, ce bouton installe seulement si la table n’existe pas déjà. Ça évite d’écraser une table par accident.</p>
  <p>
    <a class="button" href="/tools/commander?root=Tables&path={urllib.parse.quote(table_folder)}">Voir la table existante</a>
    <a class="button secondary" href="/tools/commander?root=Lecteurs%20SMB">Retour PinCab Explorer</a>
  </p>
</div>
""")

    tmp_root = Path(tempfile.mkdtemp(prefix="pincabos-explorer-install-"))

    try:
        with zipfile.ZipFile(src) as zf:
            members = list(_safe_zip_members(zf))
            zf.extractall(tmp_root, members=members)

        candidate = tmp_root / table_folder

        if candidate.exists() and candidate.is_dir():
            shutil.copytree(candidate, dst, symlinks=True)
        else:
            # Fallback si l’archive ne contient pas un dossier top-level direct.
            dst.mkdir(parents=True, exist_ok=False)
            _copy_tree_contents(tmp_root, dst)

        subprocess.run(["/usr/bin/chown", "-R", "pinball:pinball", str(dst)], timeout=60)
        subprocess.run(["/usr/bin/chmod", "-R", "u+rwX,g+rX", str(dst)], timeout=60)

    except Exception as e:
        if dst.exists():
            shutil.rmtree(dst, ignore_errors=True)

        return page("Installer PinCabOS", f"""
<div class="card">
  <h2>Installation échouée</h2>
  <p class="bad">{esc(str(e))}</p>
  <pre>{esc(str(src))}</pre>
  <p><a class="button" href="/tools/commander?root=Lecteurs%20SMB">Retour PinCab Explorer</a></p>
</div>
""")
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

    return page("Installer PinCabOS", f"""
<div class="card">
  <h2>Installation terminée</h2>
  <p class="ok">Table installée dans :</p>
  <pre>{esc(str(dst))}</pre>
  <p>
    <a class="button" href="/tools/commander?root=Tables&path={urllib.parse.quote(table_folder)}">Ouvrir la table installée</a>
    <a class="button secondary" href="/tools/commander?root=Lecteurs%20SMB">Retour Lecteurs SMB</a>
  </p>
</div>
""")


def _install_url_from_download_href(download_href):
    parsed = urllib.parse.urlparse(_html.unescape(download_href))
    qs = urllib.parse.parse_qs(parsed.query)

    root = (qs.get("root") or [""])[0]
    path = (qs.get("path") or [""])[0]

    low = path.lower()
    if not low.endswith(".pincabos") or low.endswith(".pincabos.part"):
        return None

    return (
        "/tools/commander/install-pincabos?"
        + "root=" + urllib.parse.quote(root, safe="")
        + "&path=" + urllib.parse.quote(path, safe="")
    )


def _transform_commander_html(body):
    def transform_row(match):
        row = match.group(0)

        href_match = re.search(
            r'href="([^"]*/tools/commander/download\?[^"]+)"',
            row,
            flags=re.I,
        )
        if not href_match:
            return row

        install_url = _install_url_from_download_href(href_match.group(1))
        if not install_url:
            return row

        install_btn = (
            '<a class="pcx-small" href="' + install_url + '" '
            'onclick="return confirm(\'Installer ce package PinCabOS dans /home/pinball/Tables ?\');">'
            'Installer</a>'
        )

        # Remplace le bouton/lien Vue existant dans la rangée.
        row2, count = re.subn(
            r'<a\b[^>]*>\s*(?:👁\s*)?Vue\s*</a>',
            install_btn,
            row,
            count=1,
            flags=re.I | re.S,
        )

        if count:
            return row2

        row2, count = re.subn(
            r'<button\b[^>]*>\s*(?:👁\s*)?Vue\s*</button>',
            install_btn,
            row,
            count=1,
            flags=re.I | re.S,
        )

        if count:
            return row2

        # Fallback: si la colonne Vue a changé de format, ajoute Installer après Télécharger.
        row2 = row.replace("</td>", " " + install_btn + "</td>", 1)
        return row2

    return re.sub(r"<tr\b[^>]*>.*?</tr>", transform_row, body, flags=re.I | re.S)


def _wrap_commander_view(app):
    endpoint = None

    for rule in app.url_map.iter_rules():
        if rule.rule == "/tools/commander" and "GET" in rule.methods:
            endpoint = rule.endpoint
            break

    if not endpoint:
        return "missing"

    original = app.view_functions.get(endpoint)
    if not original:
        return "missing"

    if getattr(original, "_pco_explorer_install_wrapped", False):
        return "already"

    def wrapped(*args, **kwargs):
        response = current_app.make_response(original(*args, **kwargs))

        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type:
            return response

        body = response.get_data(as_text=True)
        new_body = _transform_commander_html(body)

        if new_body != body:
            response.set_data(new_body)
            response.headers["Content-Length"] = str(len(response.get_data()))

        return response

    wrapped._pco_explorer_install_wrapped = True
    app.view_functions[endpoint] = wrapped
    return "wrapped"


def register(app, page, esc, context_globals=None):
    global _CTX
    _CTX = context_globals or {}

    app.add_url_rule(
        "/tools/commander/install-pincabos",
        endpoint="pincabos_explorer_install_pincabos_v1",
        view_func=lambda: _install_archive(page, esc),
        methods=["GET"],
    )

    mode = _wrap_commander_view(app)
    print(f"GO: PinCabOS ExplorerInstall module loaded commander={mode}")
