# PINCABOS_IMAGE_STUDIO_V11
from __future__ import annotations

import base64
import grp
import html
import json
import os
import re
import shutil
import time
import urllib.parse
from pathlib import Path

from flask import jsonify, request, send_file


_ALLOWED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def _json_response(payload, status=200):
    return jsonify(payload), status


def _fail(message, status=400):
    return _json_response({"ok": False, "error": str(message)}, status)


def _allowed_global_bases() -> list[Path]:
    # Racines autorisées pour Image Studio.
    # Pas de /etc, /usr, /root, etc. On reste dans les zones PinCabOS/médias.
    candidates = [
        "/home/pinball",
        "/opt/pincabos",
        "/media/pinball",
        "/run/media/pinball",
        "/mnt",
    ]
    return [Path(x).resolve() for x in candidates if Path(x).exists()]


def _is_under_allowed_base(target: Path) -> bool:
    target = target.resolve()
    for base in _allowed_global_bases():
        try:
            target.relative_to(base)
            return True
        except ValueError:
            pass
    return False


def _root_base(root_name: str) -> Path:
    # Racines PinCab Explorer connues + alias humains.
    fallback = {
        "PinCabOS Media": "/opt/pincabos/media",
        "Tables": "/home/pinball/Tables",
        "Backups": "/home/pinball/Backups",
        "Exports": "/home/pinball/Exports",
        "Lecteurs SMB": "/home/pinball/NetworkDrives",
        "Clés USB": "/media/pinball",
        "USB": "/media/pinball",
        "Home pinball": "/home/pinball",
        "Pinball Home": "/home/pinball",

        # V1.6: racines PinCabOS globales.
        "PinCabOS": "/opt/pincabos",
        "Root PinCabOS": "/opt/pincabos",
        "Racine PinCabOS": "/opt/pincabos",
        "Système PinCabOS": "/opt/pincabos",
        "Systeme PinCabOS": "/opt/pincabos",
        "Médias PinCabOS": "/opt/pincabos/media",
        "Medias PinCabOS": "/opt/pincabos/media",
        "Images PinCabOS": "/opt/pincabos/media/images",
        "Billes PinCabOS": "/opt/pincabos/media/images/balls",
        "Balls PinCabOS": "/opt/pincabos/media/images/balls",
        "Config PinCabOS": "/opt/pincabos/config",
        "Static WebApp": "/opt/pincabos/web/static",
    }

    if root_name in fallback:
        return Path(fallback[root_name])

    # Si le root lui-même est un chemin absolu fourni par PinCab Explorer,
    # on l'accepte seulement s'il reste sous une racine globale autorisée.
    maybe = Path(str(root_name))
    if maybe.is_absolute() and _is_under_allowed_base(maybe):
        return maybe

    raise PermissionError("Racine PinCab Explorer non supportée par Image Studio: " + str(root_name))


def _safe_target(root_name: str, rel_path: str) -> Path:
    raw_rel = str(rel_path or "")

    # V1.6B: accepte les chemins absolus sous /opt/pincabos/media et autres racines médias autorisées.
    if Path(raw_rel).is_absolute():
        target = Path(raw_rel).resolve()
        if not _is_under_allowed_base(target):
            raise PermissionError("Fichier hors racines médias PinCabOS autorisées.")
    else:
        base = _root_base(root_name).resolve()
        target = (base / raw_rel.lstrip("/")).resolve()
        try:
            target.relative_to(base)
        except ValueError as exc:
            raise PermissionError("Fichier hors racine PinCab Explorer.") from exc

        if not _is_under_allowed_base(target):
            raise PermissionError("Fichier hors racines médias PinCabOS autorisées.")

    if target.suffix.lower() not in _ALLOWED_SUFFIXES:
        raise PermissionError("Extension image non supportée par Image Studio.")

    return target

def _is_image_live_request() -> bool:
    if request.path.rstrip("/") != "/tools/commander/live":
        return False
    rel = request.args.get("path") or ""
    return Path(rel).suffix.lower() in _ALLOWED_SUFFIXES


def _studio_html(root_name: str, rel_path: str) -> str:
    cache_v = str(int(time.time()))
    root_q = urllib.parse.quote(root_name, safe="")
    path_q = urllib.parse.quote(rel_path, safe="")
    file_url = "/tools/commander/live/image-studio-file?root=" + root_q + "&path=" + path_q
    save_url = "/tools/commander/live/image-save"

    root_e = html.escape(root_name, quote=True)
    rel_e = html.escape(rel_path, quote=True)
    file_e = html.escape(file_url, quote=True)
    save_e = html.escape(save_url, quote=True)

    return f"""
<link rel="stylesheet" href="/static/pincabos-image-studio-v1.css?v={cache_v}">
<section class="pcx-imgstudio"
         data-pcx-image-studio="1"
         data-root-name="{root_e}"
         data-rel-path="{rel_e}"
         data-file-url="{file_e}"
         data-save-url="{save_e}">
  <div class="pcx-imgstudio-head">
    <div>
      <h2>🎨 PinCabOS Image Studio</h2>
      <p>Édition directe PNG / JPG / WEBP dans PinCab Explorer. Sauvegarde avec backup automatique.</p>
    </div>
    <div class="pcx-imgstudio-status" data-pcx-img-status>Chargement…</div>
  </div>

  <div class="pcx-imgstudio-toolbar">
    <div class="pcx-imgstudio-group">
      <label>Outil</label>
      <select data-pcx-img-tool>
        <option value="brush">Pinceau</option>
        <option value="eraser">Gomme</option>
        <option value="text">Texte</option>
        <option value="line">Ligne</option>
        <option value="rect">Rectangle</option>
        <option value="ellipse">Cercle / ellipse</option>
        <option value="crop">Sélection crop</option>
      </select>
    </div>

    <div class="pcx-imgstudio-group">
      <label>Couleur / taille</label>
      <div class="pcx-imgstudio-row">
        <input type="color" value="#ffbd00" data-pcx-img-color>
        <input type="number" min="1" max="220" value="8" data-pcx-img-size title="Taille pinceau">
      </div>
    </div>

    <div class="pcx-imgstudio-group">
      <label>Texte</label>
      <div class="pcx-imgstudio-row">
        <input type="text" value="PinCabOS" data-pcx-img-text>
        <input type="number" min="6" max="300" value="48" data-pcx-img-text-size title="Taille texte">
      </div>
    </div>

    <div class="pcx-imgstudio-group">
      <label>Historique</label>
      <div class="pcx-imgstudio-row">
        <button type="button" data-pcx-action="undo">Undo</button>
        <button type="button" data-pcx-action="redo">Redo</button>
        <button type="button" class="warn" data-pcx-action="reset">Reset</button>
      </div>
    </div>

    <div class="pcx-imgstudio-group">
      <label>Zoom</label>
      <div class="pcx-imgstudio-row">
        <button type="button" data-pcx-action="zoom-out">−</button>
        <button type="button" data-pcx-action="zoom-fit">Fit</button>
        <button type="button" data-pcx-action="zoom-in">+</button>
      </div>
    </div>

    <div class="pcx-imgstudio-group">
      <label>Transformer</label>
      <div class="pcx-imgstudio-row">
        <button type="button" data-pcx-action="rotate-left">⟲</button>
        <button type="button" data-pcx-action="rotate-right">⟳</button>
        <button type="button" data-pcx-action="flip-h">Flip H</button>
        <button type="button" data-pcx-action="flip-v">Flip V</button>
      </div>
    </div>

    <div class="pcx-imgstudio-group">
      <label>Resize / crop</label>
      <div class="pcx-imgstudio-row">
        <input type="number" min="1" placeholder="Largeur" data-pcx-img-width>
        <input type="number" min="1" placeholder="Hauteur" data-pcx-img-height>
        <button type="button" data-pcx-img-use-current>Actuel</button>
        <button type="button" data-pcx-action="resize">Resize</button>
        <button type="button" data-pcx-action="crop">Appliquer crop</button>
      </div>
    </div>

    <div class="pcx-imgstudio-group">
      <label>Sauvegarde</label>
      <div class="pcx-imgstudio-row">
        <button type="button" class="good" data-pcx-action="save">Sauvegarder</button>
        <input type="text" placeholder="nouveau-nom.png" data-pcx-img-new-name>
        <button type="button" class="primary" data-pcx-action="save-copy">Sauver sous</button>
      </div>
    </div>
  </div>

  <div class="pcx-imgstudio-stage-wrap">
    <canvas class="pcx-imgstudio-canvas" data-pcx-img-canvas></canvas>
  </div>

  <div class="pcx-imgstudio-meta">
    <span>Fichier: <code>{rel_e}</code></span>
    <span>Dimensions: <code data-pcx-img-dim>-</code></span>
    <span>Zoom: <code data-pcx-img-zoom>-</code></span>
  </div>
</section>
<script src="/static/pincabos-image-studio-v1.js?v={cache_v}" defer></script>
"""


def _extract_absolute_image_from_body(body: str) -> str:
    # V1.7: récupère le chemin absolu affiché par PinCab Explorer.
    # Exemple: /opt/pincabos/media/images/balls/file.png
    m = re.search(
        r'(/opt/pincabos/media/[^<>"\'\s]+?\.(?:png|jpg|jpeg|webp))',
        body,
        flags=re.I,
    )
    if not m:
        m = re.search(
            r'(/home/pinball/[^<>"\'\s]+?\.(?:png|jpg|jpeg|webp))',
            body,
            flags=re.I,
        )
    if not m:
        m = re.search(
            r'(/media/pinball/[^<>"\'\s]+?\.(?:png|jpg|jpeg|webp))',
            body,
            flags=re.I,
        )
    if not m:
        return ""
    try:
        return html.unescape(urllib.parse.unquote(m.group(1)))
    except Exception:
        return m.group(1)


def _inject_image_studio(response):
    try:
        if request.path.rstrip("/") != "/tools/commander/live":
            return response
        if response.mimetype != "text/html":
            return response

        body = response.get_data(as_text=True)
        if "data-pcx-image-studio=\"1\"" in body:
            return response

        root_name = request.args.get("root") or "Tables"
        rel_path = request.args.get("path") or ""

        # Cas normal: root/path reconnu.
        inject_root = root_name
        inject_path = rel_path

        # Cas robuste V1.7: la page affiche une image absolue sous /opt/pincabos/media,
        # mais le root PinCab Explorer n'est pas un alias connu du module.
        absolute_from_body = _extract_absolute_image_from_body(body)

        target = None
        try:
            target = _safe_target(root_name, rel_path)
        except Exception:
            if absolute_from_body:
                try:
                    target = _safe_target("/opt/pincabos/media", absolute_from_body)
                    inject_root = "/opt/pincabos/media"
                    inject_path = absolute_from_body
                except Exception:
                    target = None

        if target is None:
            return response

        if not target.exists() or not target.is_file():
            return response

        if target.suffix.lower() not in _ALLOWED_SUFFIXES:
            return response

        studio = _studio_html(inject_root, inject_path)

        # Injection avant fin body. Les scripts V1.3 le replacent ensuite sous l'image.
        if "</body>" in body:
            body = body.replace("</body>", studio + "\n</body>", 1)
        else:
            body = body + studio

        response.set_data(body)
        try:
            response.headers["Content-Length"] = str(len(body.encode(response.charset or "utf-8")))
        except Exception:
            response.headers.pop("Content-Length", None)
        return response
    except Exception:
        return response


def _serve_image_file():
    try:
        import mimetypes

        root_name = request.args.get("root") or "Tables"
        rel_path = request.args.get("path") or ""

        target = _safe_target(str(root_name), str(rel_path))
        if not target.exists() or not target.is_file():
            return _fail("Image introuvable.", 404)

        mime_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        response = send_file(
            str(target),
            mimetype=mime_type,
            conditional=True,
            max_age=0,
            as_attachment=False,
            download_name=target.name,
        )
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    except PermissionError as exc:
        return _fail(str(exc), 403)
    except Exception as exc:
        return _fail("Erreur lecture Image Studio: " + str(exc), 500)

def _save_image():
    try:
        payload = request.get_json(force=True, silent=True) or {}
        root_name = str(payload.get("root") or "Tables")
        rel_path = str(payload.get("path") or "")
        new_name = str(payload.get("new_name") or "").strip()
        image_data = str(payload.get("image_data") or "")

        target = _safe_target(root_name, rel_path)
        if not target.exists() or not target.is_file():
            return _fail("Fichier source introuvable.", 404)

        dest = target
        if new_name:
            clean = Path(new_name).name
            if clean != new_name or not clean:
                return _fail("Nom de fichier invalide.")
            if Path(clean).suffix.lower() not in _ALLOWED_SUFFIXES:
                return _fail("Le nouveau nom doit finir par .png, .jpg, .jpeg ou .webp.")
            dest = target.with_name(clean)
            dest.resolve().relative_to(target.parent.resolve())

        match = re.match(r"^data:(image/(?:png|jpeg|webp));base64,(.+)$", image_data, flags=re.S)
        if not match:
            return _fail("Payload image invalide.")

        mime = match.group(1)
        raw = base64.b64decode(match.group(2), validate=True)

        if len(raw) > 220 * 1024 * 1024:
            return _fail("Image trop grosse pour sauvegarde WebApp.")

        suffix = dest.suffix.lower()
        if suffix == ".png":
            if mime != "image/png" or not raw.startswith(b"\x89PNG\r\n\x1a\n"):
                return _fail("Le contenu reçu n’est pas un PNG valide.")
        elif suffix in {".jpg", ".jpeg"}:
            if mime != "image/jpeg" or not raw.startswith(b"\xff\xd8\xff"):
                return _fail("Le contenu reçu n’est pas un JPEG valide.")
        elif suffix == ".webp":
            if mime != "image/webp" or not (raw.startswith(b"RIFF") and raw[8:12] == b"WEBP"):
                return _fail("Le contenu reçu n’est pas un WEBP valide.")

        backup_name = ""
        if dest.exists():
            stamp = time.strftime("%Y%m%d-%H%M%S")
            backup = dest.with_name(dest.name + ".before-image-studio-" + stamp)
            shutil.copy2(dest, backup)
            backup_name = backup.name

        tmp = dest.with_name(dest.name + ".pincabos-image-studio.part")
        tmp.write_bytes(raw)
        os.replace(tmp, dest)

        try:
            import pwd
            uid = pwd.getpwnam("pinball").pw_uid
            gid = grp.getgrnam("pinball").gr_gid
            os.chown(dest, uid, gid)
            os.chmod(dest, 0o664)
        except Exception:
            pass

        return jsonify({
            "ok": True,
            "saved": dest.name,
            "path": str(dest),
            "backup": backup_name,
            "bytes": len(raw),
        })
    except PermissionError as exc:
        return _fail(str(exc), 403)
    except Exception as exc:
        return _fail("Erreur sauvegarde Image Studio: " + str(exc), 500)


def register(app):
    if not getattr(app, "_pincabos_image_studio_v11_registered", False):
        app.after_request(_inject_image_studio)
        app.add_url_rule(
            "/tools/commander/live/image-studio-file",
            "tools_commander_live_image_file_v18",
            _serve_image_file,
            methods=["GET"],
        )
        app.add_url_rule(
            "/tools/commander/live/image-save",
            "tools_commander_live_image_save_v11",
            _save_image,
            methods=["POST"],
        )
        app._pincabos_image_studio_v11_registered = True
