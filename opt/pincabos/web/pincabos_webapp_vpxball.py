"""Bille VPX de la WebApp PinCabOS : réglages cabinet (/tools/vpx-ball-cabinet), carte simple (/tools/vpx-ball-simple), images UserBalls.

Code déplacé tel quel depuis app.py (PINCABOS_WEBAPP_MODULES_V1) ; les routes gardent
leurs chemins et leurs noms de fonction. `page()` (gabarit commun) est fourni par app.py
à l'enregistrement : `register(app, page)`.
"""
from __future__ import annotations

import os
import re
import shutil
from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, request

from pincabos_webapp_core import esc, pincabos_vpx_ini_path

try:
    import pincabos_ini
except ImportError:   # hors /opt (tests, depot) : le module vit a cote des outils
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "tools"))
    import pincabos_ini

vpxball_bp = Blueprint("vpxball", __name__)

page = None  # gabarit HTML commun, posé par register()


# # # # === PINCABOS VPX BALL CABINET TOOLS START ===
# PINCABOS_VPX_BALLCAB_V11 — cible unique, backup pinball, miniatures et navigateur image/decal sécurisé.
VPX_BALLCAB_OFFICIAL_INI = Path("/home/pinball/.local/share/VPinballX/10.8/VPinballX.ini")
VPX_BALLCAB_BACKUP_DIR = Path("/home/pinball/.local/share/VPinballX/10.8/pincabos-backups/vpx-ball-cabinet")
VPX_BALLCAB_MARKER = "PinCabOS fonction(VPX Ball / Cabinet)"

VPX_BALLCAB_KEYS = {
    "Player": [
        ("CabinetAutofitMode", "Mode Cabinet Autofit"),
        ("CabinetAutofitPos", "Position Cabinet Autofit"),
        ("BallAntiStretch", "Ball Anti-Stretch"),
        ("DisableLightingForBalls", "Désactiver lighting sur les billes"),
        ("BallTrail", "Ball Trail"),
        ("BallTrailStrength", "Force Ball Trail"),
        ("OverwriteBallImage", "Utiliser image personnalisée de bille"),
        ("BallImage", "Nom image bille"),
        ("DecalImage", "Nom image décalque"),
        ("TouchOverlay", "Touch Overlay"),
    ],
    "DefaultProps\\Ball": [
        ("ForceReflection", "Force Reflection"),
        ("DecalMode", "Decal Mode"),
        ("Image", "Image bille par défaut"),
        ("DecalImage", "Décalque bille par défaut"),
        ("BulbIntensityScale", "Bulb Intensity Scale"),
        ("PFReflStrength", "Playfield Reflection Strength"),
        ("Color", "Couleur"),
        ("SphereMap", "Sphere Map"),
        ("ReflectionEnabled", "Reflection Enabled"),
    ],
}

VPX_BALLCAB_BOOLEAN_KEYS = {
    "BallAntiStretch", "DisableLightingForBalls", "BallTrail", "OverwriteBallImage",
    "TouchOverlay", "ForceReflection", "ReflectionEnabled",
}
VPX_BALLCAB_NUMERIC_KEYS = {"BallTrailStrength", "BulbIntensityScale", "PFReflStrength"}
VPX_BALLCAB_IMAGE_KEYS = {"BallImage", "DecalImage", "Image", "SphereMap"}


def vpx_ballcab_ini_path():
    """La page ne peut jamais basculer vers un second INI ou un chemin détecté."""
    return VPX_BALLCAB_OFFICIAL_INI


def vpx_ballcab_read_lines(path=None):
    path = Path(path or vpx_ballcab_ini_path())
    if not path.is_file():
        raise FileNotFoundError(f"VPinballX.ini officiel absent : {path}")
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def vpx_ballcab_write_lines(path, lines):
    """Écriture atomique qui conserve propriétaire et permissions du vrai VPinballX.ini."""
    import tempfile
    path = Path(path)
    if path.resolve() != VPX_BALLCAB_OFFICIAL_INI.resolve():
        raise RuntimeError("Refus : écriture hors du VPinballX.ini officiel.")
    if not path.is_file():
        raise FileNotFoundError(f"VPinballX.ini officiel absent : {path}")
    stat = path.stat()
    payload = "\n".join(lines).rstrip() + "\n"
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, stat.st_mode & 0o777)
        try:
            os.chown(temporary, stat.st_uid, stat.st_gid)
        except PermissionError:
            pass
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def vpx_ballcab_backup(path):
    path = Path(path)
    if path.resolve() != VPX_BALLCAB_OFFICIAL_INI.resolve():
        raise RuntimeError("Refus : backup demandé hors du VPinballX.ini officiel.")
    if not path.is_file():
        raise FileNotFoundError(f"VPinballX.ini officiel absent : {path}")
    VPX_BALLCAB_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = VPX_BALLCAB_BACKUP_DIR / f"VPinballX.ini.backup-vpx-ball-cabinet-{stamp}"
    shutil.copy2(path, dst)
    return dst


def vpx_ballcab_find_section(lines, section):
    # PINCABOS_INI_UNIQUE_V1 : bornes de section par l ecrivain unique
    return pincabos_ini.Ini("\n".join(lines)).bornes(section)


def vpx_ballcab_get_value(lines, section, key):
    start, end = vpx_ballcab_find_section(lines, section)
    if start is None:
        return ""
    target = key.lower()
    for line in lines[start + 1:end]:
        text = line.strip()
        if not text or text.startswith((";", "#")) or "=" not in text:
            continue
        existing_key, value = text.split("=", 1)
        if existing_key.strip().lower() == target:
            return value.strip()
    return ""


def vpx_ballcab_set_value(lines, section, key, value):
    """Met à jour uniquement une clé qui diffère; conserve les autres réglages intacts."""
    start, end = vpx_ballcab_find_section(lines, section)
    new_line = f"{key} = {value}"
    comment = "; Modifié " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " par " + VPX_BALLCAB_MARKER
    if start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend([comment, f"[{section}]", new_line])
        return lines
    target = key.lower()
    for index in range(start + 1, end):
        text = lines[index].strip()
        if not text or text.startswith((";", "#")) or "=" not in text:
            continue
        existing_key = text.split("=", 1)[0].strip().lower()
        if existing_key != target:
            continue
        if index > 0 and VPX_BALLCAB_MARKER in lines[index - 1]:
            lines[index - 1] = comment
        else:
            lines.insert(index, comment)
            index += 1
        lines[index] = new_line
        return lines
    lines.insert(end, comment)
    lines.insert(end + 1, new_line)
    return lines


def vpx_ballcab_form_name(section, key):
    return section.replace("\\", "__BS__").replace(" ", "__SP__") + "___" + key


def vpx_ballcab_validate_value(key, value):
    value = str(value or "").strip()
    if len(value) > 1024 or "\x00" in value or "\n" in value or "\r" in value:
        raise ValueError(f"{key} : valeur invalide.")
    if key in VPX_BALLCAB_BOOLEAN_KEYS and value not in ("", "0", "1"):
        raise ValueError(f"{key} : utilise seulement 0 ou 1.")
    if key in VPX_BALLCAB_NUMERIC_KEYS and value and not re.fullmatch(r"-?(?:\d+(?:\.\d+)?|\.\d+)", value):
        raise ValueError(f"{key} : nombre attendu.")
    if key == "CabinetAutofitMode" and value not in ("", "0", "1", "2"):
        raise ValueError("CabinetAutofitMode : valeurs autorisées : vide, 0, 1 ou 2.")
    if key in VPX_BALLCAB_IMAGE_KEYS and value and ("[" in value or "]" in value):
        raise ValueError(f"{key} : nom ou chemin image invalide.")
    return value


def vpx_ballcab_select(name, value, options):
    value = str(value or "")
    if value not in {code for code, _label in options}:
        options = [(value, value or "vide / défaut")] + options
    html_options = []
    for code, label in options:
        selected = " selected" if code == value else ""
        html_options.append(f'<option value="{esc(code)}"{selected}>{esc(label)}</option>')
    return f'<select name="{esc(name)}">{"".join(html_options)}</select>'


def vpx_ballcab_preview_url(value):
    """URL interne qui ne sert que les assets présents dans les racines autorisées."""
    from urllib.parse import quote
    return "/tools/vpx-ball-cabinet/image-preview?path=" + quote(str(value), safe="")


def vpx_ballcab_field(section, key, label, value):
    name = vpx_ballcab_form_name(section, key)
    control = ""
    current = f'<div class="vpxbc-current"><span>Actuelle</span><code>{esc(value if value else "vide")}</code></div>'
    if key in VPX_BALLCAB_BOOLEAN_KEYS:
        control = vpx_ballcab_select(name, value, [("", "vide / défaut"), ("0", "0 — Désactivé"), ("1", "1 — Activé")])
    elif key == "CabinetAutofitMode":
        control = vpx_ballcab_select(name, value, [("", "vide / défaut"), ("0", "0 — Désactivé"), ("1", "1 — Standard"), ("2", "2 — Cabinet")])
    elif key in VPX_BALLCAB_NUMERIC_KEYS:
        control = f'<input type="number" step="any" name="{esc(name)}" value="{esc(value)}" placeholder="nombre">'
    elif key in VPX_BALLCAB_IMAGE_KEYS:
        kind = "decal" if "Decal" in key else "ball"
        preview_id = f"vpxbc-preview-{name}"
        preview_src = vpx_ballcab_preview_url(value) if value else ""
        image_class = "" if preview_src else "vpxbc-no-image"
        current = (
            f'<div class="vpxbc-current vpxbc-current-image" id="{esc(preview_id)}">'
            f'<span>Miniature actuelle</span>'
            f'<div class="vpxbc-current-image-row">'
            f'<img alt="" src="{esc(preview_src)}" class="{image_class}" loading="lazy" '
            f'onerror="this.classList.add(\'vpxbc-no-image\')">'
            f'<code>{esc(value if value else "vide")}</code></div></div>'
        )
        control = (
            f'<div class="vpxbc-image-input"><input id="vpxbc-{esc(name)}" name="{esc(name)}" value="{esc(value)}" '
            f'data-preview="{esc(preview_id)}" autocomplete="off" placeholder="nom ou chemin image VPX">'
            f'<button class="button secondary vpxbc-browse" type="button" aria-label="Parcourir les images pour {esc(label)}" '
            f'title="Choisir une image locale" data-target="vpxbc-{esc(name)}" data-kind="{kind}"><span aria-hidden="true">▣</span> Parcourir</button></div>'
        )
    else:
        placeholder = "vide / défaut" if key == "CabinetAutofitPos" else "valeur VPX"
        control = f'<input name="{esc(name)}" value="{esc(value)}" placeholder="{placeholder}">'
    return (
        '<div class="vpxbc-row">'
        f'<div class="vpxbc-label"><strong>{esc(label)}</strong><code>{esc(key)}</code></div>'
        f'<div class="vpxbc-control">{control}</div>'
        f'{current}'
        '</div>'
    )

def vpx_ballcab_rows(lines):
    blocks = []
    for section, keys in VPX_BALLCAB_KEYS.items():
        fields = "".join(vpx_ballcab_field(section, key, label, vpx_ballcab_get_value(lines, section, key)) for key, label in keys)
        blocks.append(f'<section class="vpxbc-section"><h2>[{esc(section)}]</h2>{fields}</section>')
    return "".join(blocks)


def vpx_ballcab_current_preview(lines):
    out = []
    for section, keys in VPX_BALLCAB_KEYS.items():
        out.append(f"[{section}]")
        for key, _label in keys:
            out.append(f"{key} = {vpx_ballcab_get_value(lines, section, key)}")
        out.append("")
    return "\n".join(out).strip()


VPX_BALLCAB_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def vpx_ballcab_asset_roots(kind="all"):
    """Racines locales autorisées pour les images de billes et les décalques."""
    candidates = [
        Path("/home/pinball/.vpinball/UserBalls"),
        Path("/home/pinball/.local/share/VPinballX/10.8/UserBalls"),
        Path("/opt/pincabos/media/images"),
        Path("/opt/pincabos/media/image"),
    ]
    roots = []
    for candidate in candidates:
        try:
            root = candidate.resolve()
        except OSError:
            continue
        if root.is_dir() and root not in roots:
            roots.append(root)
    return roots


def vpx_ballcab_safe_image_path(raw):
    """Résout un fichier image seulement s’il appartient à une racine autorisée."""
    try:
        candidate = Path(str(raw or "")).expanduser().resolve()
    except (OSError, RuntimeError, ValueError):
        return None
    if not candidate.is_file() or candidate.suffix.lower() not in VPX_BALLCAB_IMAGE_SUFFIXES:
        return None
    for root in vpx_ballcab_asset_roots("all"):
        if candidate == root or root in candidate.parents:
            return candidate
    return None


def vpx_ballcab_image_rank(path, kind):
    words = "/".join(part.lower() for part in path.parts)
    if kind == "decal":
        return (0 if any(token in words for token in ("/decal", "/decals", "/overlay", "/sticker")) else 1, str(path).lower())
    if kind == "ball":
        return (0 if any(token in words for token in ("/ball", "/balls", "/sphere")) else 1, str(path).lower())
    return (0, str(path).lower())


def vpx_ballcab_list_images(kind="all"):
    """Liste dédupliquée; les décalques voient d’abord leurs dossiers dédiés, puis tous les PNG compatibles."""
    found = {}
    for root in vpx_ballcab_asset_roots(kind):
        try:
            candidates = root.rglob("*")
        except OSError:
            continue
        for candidate in candidates:
            try:
                resolved = candidate.resolve()
            except (OSError, RuntimeError):
                continue
            if root not in resolved.parents or not resolved.is_file() or resolved.suffix.lower() not in VPX_BALLCAB_IMAGE_SUFFIXES:
                continue
            found.setdefault(str(resolved), (resolved, root))
    ordered = sorted(found.values(), key=lambda item: vpx_ballcab_image_rank(item[0], kind))
    images = []
    for resolved, root in ordered[:600]:
        try:
            relative = resolved.relative_to(root)
        except ValueError:
            relative = resolved.name
        category = "Décalque" if "decal" in str(resolved).lower() else "Image compatible"
        images.append({
            "value": str(resolved),
            "label": f"{category} · {root.name} / {relative}",
        })
    return images


@vpxball_bp.route("/tools/vpx-ball-cabinet/images.json")
def tools_vpx_ball_cabinet_images_json():
    kind = str(request.args.get("kind", "all")).lower()
    if kind not in {"all", "ball", "decal"}:
        return jsonify({"ok": False, "error": "Type image invalide.", "images": []}), 400
    return jsonify({"ok": True, "kind": kind, "images": vpx_ballcab_list_images(kind)})


@vpxball_bp.route("/tools/vpx-ball-cabinet/image-preview")
def tools_vpx_ball_cabinet_image_preview():
    image = vpx_ballcab_safe_image_path(request.args.get("path", ""))
    if image is None:
        from flask import abort
        abort(404)
    from flask import send_file
    response = send_file(str(image), conditional=True, max_age=300)
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

def vpx_ballcab_render_result(title, status_class, message, changes, ini, backup=None, status=200):
    lines = "\n".join(changes) if changes else "Aucune valeur différente détectée."
    backup_row = f'<tr><td>Backup</td><td><code>{esc(str(backup))}</code></td></tr>' if backup else ""
    body = f'''
<style>
.vpxbc-result pre{{white-space:pre-wrap;max-height:430px;overflow:auto;background:rgba(0,0,0,.45);border:1px solid rgba(255,176,0,.25);border-radius:12px;padding:12px}}
</style>
<div class="card vpxbc-result"><h2>{esc(title)}</h2><p class="{esc(status_class)}">{esc(message)}</p>
<table><tr><td>Fichier officiel</td><td><code>{esc(str(ini))}</code></td></tr>{backup_row}</table>
<h3>Changements</h3><pre>{esc(lines)}</pre>
<p><a class="button" href="/tools/vpx-ball-cabinet">Retour VPX Ball / Cabinet</a><a class="button secondary" href="/tools">Retour Outils</a></p></div>'''
    return page("Outils", body), status


def vpx_ballcab_process(dry_run=False):
    ini = vpx_ballcab_ini_path()
    try:
        lines = vpx_ballcab_read_lines(ini)
        updated = list(lines)
        changes = []
        for section, keys in VPX_BALLCAB_KEYS.items():
            for key, _label in keys:
                form_name = vpx_ballcab_form_name(section, key)
                if form_name not in request.form:
                    continue
                value = vpx_ballcab_validate_value(key, request.form.get(form_name, ""))
                old_value = vpx_ballcab_get_value(updated, section, key)
                if value != old_value:
                    updated = vpx_ballcab_set_value(updated, section, key, value)
                    changes.append(f"[{section}] {key} : {old_value or 'vide'} -> {value or 'vide'}")
    except (ValueError, FileNotFoundError, RuntimeError) as error:
        return vpx_ballcab_render_result("Validation refusée", "bad", str(error), [], ini, status=400)

    if dry_run:
        message = "Validation réussie : aucune écriture et aucun backup n’ont été effectués."
        return vpx_ballcab_render_result("Validation VPX Ball / Cabinet", "ok", message, changes, ini)
    if not changes:
        return vpx_ballcab_render_result("Aucun changement", "ok", "Les valeurs sont déjà identiques dans le VPinballX.ini officiel.", [], ini)

    try:
        backup = vpx_ballcab_backup(ini)
        updated = vpx_ballcab_set_value(updated, "PinCabOS.BallCabinet", "managed_by", "PinCabOS VPX Ball / Cabinet")
        updated = vpx_ballcab_set_value(updated, "PinCabOS.BallCabinet", "updated_at", datetime.now().isoformat(timespec="seconds"))
        vpx_ballcab_write_lines(ini, updated)
    except (OSError, RuntimeError, FileNotFoundError) as error:
        return vpx_ballcab_render_result("Écriture refusée", "bad", str(error), changes, ini, status=500)

    return vpx_ballcab_render_result("VPX Ball / Cabinet appliqué", "ok", "Configuration écrite uniquement dans le VPinballX.ini officiel.", changes, ini, backup=backup)


@vpxball_bp.route("/tools/vpx-ball-cabinet/validate", methods=["POST"])
def tools_vpx_ball_cabinet_validate():
    return vpx_ballcab_process(dry_run=True)


@vpxball_bp.route("/tools/vpx-ball-cabinet/apply", methods=["POST"])
def tools_vpx_ball_cabinet_apply():
    return vpx_ballcab_process(dry_run=False)


@vpxball_bp.route("/tools/vpx-ball-cabinet")
def tools_vpx_ball_cabinet():
    ini = vpx_ballcab_ini_path()
    try:
        lines = vpx_ballcab_read_lines(ini)
    except FileNotFoundError as error:
        return vpx_ballcab_render_result("VPinballX.ini introuvable", "bad", str(error), [], ini, status=500)
    body = f'''
<style>
.vpxbc-shell{{max-width:1780px;margin:0 auto;padding:0 2px 26px}}.vpxbc-hero,.vpxbc-section,.vpxbc-picker{{background:linear-gradient(145deg,rgba(38,14,60,.94),rgba(20,7,34,.92));border:1px solid rgba(255,143,0,.55);border-radius:16px;box-shadow:0 12px 32px rgba(0,0,0,.24)}}
.vpxbc-hero{{padding:20px 22px;margin-bottom:14px}}.vpxbc-hero h1{{margin:0;color:#ffb000;font-size:1.5rem;letter-spacing:.01em}}.vpxbc-hero p{{margin:8px 0;color:#eadff1;max-width:1000px}}.vpxbc-ini{{display:block;margin-top:5px;word-break:break-all;color:#ffd36a;font-size:.92rem}}
.vpxbc-actions{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:16px 0}}.vpxbc-actions .button{{margin:0;min-height:40px;display:inline-flex;align-items:center;justify-content:center}}.vpxbc-section{{padding:0;margin:16px 0;overflow:hidden}}.vpxbc-section h2{{margin:0;padding:12px 18px;background:linear-gradient(90deg,rgba(255,176,0,.18),rgba(255,176,0,.06));border-bottom:1px solid rgba(255,176,0,.30);font-size:1rem;color:#ffbd00}}
.vpxbc-row{{display:grid;grid-template-columns:minmax(250px,.85fr) minmax(500px,1.55fr) minmax(210px,.65fr);gap:20px;align-items:center;padding:14px 18px;border-bottom:1px solid rgba(255,255,255,.08)}}.vpxbc-row:last-child{{border-bottom:0}}.vpxbc-label strong{{display:block;color:#fff;line-height:1.25}}.vpxbc-label code{{display:block;margin-top:4px;color:#cfa7ff;font-size:.8rem}}.vpxbc-control{{min-width:0}}.vpxbc-control input,.vpxbc-control select{{box-sizing:border-box;width:100%;min-height:42px;padding:9px 11px;border-radius:10px;border:1px solid rgba(255,153,0,.75);background:#0d0615;color:#fff;box-shadow:inset 0 1px 0 rgba(255,255,255,.04)}}.vpxbc-control input:focus,.vpxbc-control select:focus{{outline:2px solid rgba(168,87,255,.56);outline-offset:1px}}
.vpxbc-image-input{{display:grid;grid-template-columns:minmax(0,1fr) 142px;gap:10px;align-items:stretch;width:100%}}.vpxbc-image-input input{{min-width:0}}.vpxbc-image-input .vpxbc-browse{{width:142px;min-width:142px;min-height:42px;margin:0!important;white-space:nowrap;display:inline-flex;align-items:center;justify-content:center;gap:7px;border-radius:10px;line-height:1}}.vpxbc-image-input .vpxbc-browse span{{font-size:1rem;line-height:1}}
.vpxbc-current{{align-self:stretch;display:flex;flex-direction:column;justify-content:center;padding-left:2px;min-width:0}}.vpxbc-current span{{display:block;color:#bba8c6;font-size:.72rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase}}.vpxbc-current code{{display:block;margin-top:5px;padding:7px 9px;border-radius:8px;background:rgba(0,0,0,.34);word-break:break-word;color:#fff;line-height:1.25;min-height:30px;box-sizing:border-box}}
.vpxbc-current-image-row{{display:flex;gap:10px;align-items:center;margin-top:6px;min-width:0}}.vpxbc-current-image-row img{{width:58px;height:58px;object-fit:cover;border-radius:9px;background:#08040e;border:1px solid rgba(255,176,0,.42);flex:0 0 58px}}.vpxbc-current-image-row img.vpxbc-no-image{{display:none}}.vpxbc-current-image-row code{{margin:0;min-height:44px;max-height:64px;overflow:auto;flex:1}}
.vpxbc-picker{{position:fixed;z-index:2000;left:50%;top:50%;transform:translate(-50%,-50%);width:min(1080px,calc(100vw - 32px));max-height:calc(100vh - 32px);padding:20px;display:none;overflow:auto}}.vpxbc-picker.open{{display:block}}.vpxbc-picker-head{{display:flex;justify-content:space-between;gap:12px;align-items:center}}.vpxbc-picker h2{{margin:0;color:#ffbd00;font-size:1.1rem}}.vpxbc-picker-meta{{color:#cfbed8;margin:10px 0;font-size:.9rem}}.vpxbc-picker-filter{{box-sizing:border-box;width:100%;min-height:42px;border-radius:10px;background:#100817;color:#fff;border:1px solid rgba(255,153,0,.72);padding:9px 11px;margin:0 0 12px}}.vpxbc-gallery{{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:11px;max-height:52vh;overflow:auto;padding:2px}}.vpxbc-thumb{{display:grid;grid-template-rows:112px auto;gap:8px;text-align:left;border:1px solid rgba(137,78,188,.58);border-radius:11px;background:rgba(9,4,16,.78);padding:8px;color:#fff;cursor:pointer;min-width:0}}.vpxbc-thumb:hover,.vpxbc-thumb.active{{border-color:#ffb000;box-shadow:0 0 0 2px rgba(255,176,0,.16)}}.vpxbc-thumb img{{display:block;width:100%;height:112px;object-fit:contain;border-radius:8px;background:#050208}}.vpxbc-thumb strong{{display:block;font-size:.8rem;line-height:1.25;word-break:break-word}}.vpxbc-thumb small{{display:block;color:#cbb8d8;font-size:.7rem;margin-top:3px;word-break:break-word}}.vpxbc-empty{{grid-column:1/-1;padding:22px;border:1px dashed rgba(255,176,0,.4);border-radius:10px;color:#d6c5e0;text-align:center}}.vpxbc-overlay{{position:fixed;inset:0;background:rgba(0,0,0,.66);display:none;z-index:1999}}.vpxbc-overlay.open{{display:block}}.vpxbc-preview{{margin-top:16px;padding:14px 16px;border:1px solid rgba(255,176,0,.25);border-radius:12px;background:rgba(0,0,0,.25)}}.vpxbc-preview summary{{cursor:pointer;color:#ffbd00}}.vpxbc-preview pre{{margin:10px 0 0;white-space:pre-wrap;max-height:320px;overflow:auto}}
@media(max-width:1180px){{.vpxbc-row{{grid-template-columns:minmax(220px,.8fr) minmax(360px,1.35fr) minmax(180px,.65fr);gap:14px;padding:13px 15px}}.vpxbc-image-input{{grid-template-columns:minmax(0,1fr) 128px}}.vpxbc-image-input .vpxbc-browse{{width:128px;min-width:128px;font-size:.9rem}}}}@media(max-width:900px){{.vpxbc-row{{grid-template-columns:1fr;gap:8px}}.vpxbc-current{{padding:0}}.vpxbc-current-image-row img{{width:52px;height:52px;flex-basis:52px}}}}@media(max-width:560px){{.vpxbc-shell{{padding:0 0 20px}}.vpxbc-hero{{padding:16px}}.vpxbc-actions{{gap:8px}}.vpxbc-actions .button{{width:100%}}.vpxbc-row{{padding:13px}}.vpxbc-image-input{{grid-template-columns:1fr}}.vpxbc-image-input .vpxbc-browse{{width:100%;min-width:0}}.vpxbc-picker{{width:calc(100vw - 20px);padding:14px}}.vpxbc-gallery{{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}}.vpxbc-thumb{{grid-template-rows:90px auto}}.vpxbc-thumb img{{height:90px}}}}
</style>
<div class="vpxbc-shell" data-vpxbc="1"><section class="vpxbc-hero"><h1>VPX Ball / Cabinet</h1><p>Réglages globaux liés à la bille, aux images, au trail et au mode cabinet. Les miniatures et les choix Décalque sont maintenant affichés directement dans le navigateur.</p><strong>VPinballX.ini officiel</strong><code class="vpxbc-ini">{esc(str(ini))}</code><p>La validation n’écrit rien. Lors d’un changement, un backup PinCabOS est créé dans le dossier VPX de <code>pinball</code> avant l’écriture atomique.</p></section>
<form method="post"><div class="vpxbc-actions"><button class="button secondary" type="submit" formaction="/tools/vpx-ball-cabinet/validate">Valider sans écrire</button><button class="button" type="submit" formaction="/tools/vpx-ball-cabinet/apply">Appliquer dans VPinballX.ini officiel</button><a class="button secondary" href="/tools">Retour Outils</a></div>{vpx_ballcab_rows(lines)}</form>
<details class="vpxbc-preview"><summary>Résumé technique actuel</summary><pre>{esc(vpx_ballcab_current_preview(lines))}</pre></details></div>
<div class="vpxbc-overlay" id="vpxbc-overlay"></div><section class="vpxbc-picker" id="vpxbc-picker" aria-hidden="true"><div class="vpxbc-picker-head"><h2 id="vpxbc-picker-title">Choisir une image</h2><button class="button secondary" id="vpxbc-close" type="button">Fermer</button></div><p class="vpxbc-picker-meta" id="vpxbc-meta">Chargement…</p><input class="vpxbc-picker-filter" id="vpxbc-filter" type="search" placeholder="Filtrer les fichiers affichés…"><div class="vpxbc-gallery" id="vpxbc-gallery"></div><div class="vpxbc-actions"><button class="button" id="vpxbc-use" type="button" disabled>Utiliser cette image</button></div></section>
<script>
(()=>{{const root=document.querySelector('[data-vpxbc]');if(!root)return;const picker=document.getElementById('vpxbc-picker'),overlay=document.getElementById('vpxbc-overlay'),gallery=document.getElementById('vpxbc-gallery'),meta=document.getElementById('vpxbc-meta'),filter=document.getElementById('vpxbc-filter'),use=document.getElementById('vpxbc-use'),title=document.getElementById('vpxbc-picker-title');let target=null,images=[],selected='';const previewUrl=value=>'/tools/vpx-ball-cabinet/image-preview?path='+encodeURIComponent(value);const setPreview=(input,value)=>{{const pane=input&&input.dataset.preview?document.getElementById(input.dataset.preview):null;if(!pane)return;const img=pane.querySelector('img'),code=pane.querySelector('code');if(code)code.textContent=value||'vide';if(img){{if(value){{img.src=previewUrl(value);img.classList.remove('vpxbc-no-image');}}else{{img.removeAttribute('src');img.classList.add('vpxbc-no-image');}}}}}};const close=()=>{{picker.classList.remove('open');overlay.classList.remove('open');picker.setAttribute('aria-hidden','true');target=null;images=[];selected='';use.disabled=true;}};const choose=value=>{{selected=value;use.disabled=!selected;gallery.querySelectorAll('.vpxbc-thumb').forEach(card=>card.classList.toggle('active',card.dataset.value===selected));}};const render=()=>{{const query=(filter.value||'').trim().toLowerCase();gallery.innerHTML='';const shown=images.filter(image=>!query||(image.label+' '+image.value).toLowerCase().includes(query));if(!shown.length){{gallery.innerHTML='<div class="vpxbc-empty">Aucune image ne correspond au filtre.</div>';return;}}for(const image of shown){{const card=document.createElement('button');card.type='button';card.className='vpxbc-thumb';card.dataset.value=image.value;const img=document.createElement('img');img.loading='lazy';img.src=previewUrl(image.value);img.alt='';img.onerror=()=>img.remove();const text=document.createElement('div');const strong=document.createElement('strong');strong.textContent=image.label;const small=document.createElement('small');small.textContent=image.value;text.append(strong,small);card.append(img,text);card.addEventListener('click',()=>choose(image.value));card.addEventListener('dblclick',()=>{{choose(image.value);if(target){{target.value=image.value;setPreview(target,image.value);close();}}}});gallery.appendChild(card);}}}};document.getElementById('vpxbc-close').addEventListener('click',close);overlay.addEventListener('click',close);filter.addEventListener('input',render);document.querySelectorAll('.vpxbc-browse').forEach(button=>button.addEventListener('click',async()=>{{target=document.getElementById(button.dataset.target);images=[];selected='';filter.value='';use.disabled=true;gallery.innerHTML='';title.textContent=button.dataset.kind==='decal'?'Choisir un décalque':'Choisir une image de bille';meta.textContent='Chargement des miniatures…';picker.classList.add('open');overlay.classList.add('open');picker.setAttribute('aria-hidden','false');try{{const response=await fetch('/tools/vpx-ball-cabinet/images.json?kind='+encodeURIComponent(button.dataset.kind),{{cache:'no-store'}});const data=await response.json();if(!response.ok||!data.ok)throw new Error(data.error||'Impossible de lire les images.');images=data.images||[];meta.textContent=images.length+' image(s) compatible(s) disponible(s). Les dossiers Décalque sont affichés en premier.';render();}}catch(error){{meta.textContent=error.message||String(error);gallery.innerHTML='<div class="vpxbc-empty">Le navigateur d’images n’a pas pu être chargé.</div>';}}}}));use.addEventListener('click',()=>{{if(target&&selected){{target.value=selected;setPreview(target,selected);close();}}}});}})();
</script>'''
    return page("Outils", body)
# === PINCABOS VPX BALL CABINET TOOLS END ===


# === PINCABOS SIMPLE VPX BALL CARD START ===
VPX_SIMPLE_BALL_INI = pincabos_vpx_ini_path()
VPX_SIMPLE_BALL_USERBALLS_DIR = Path("/home/pinball/.vpinball/UserBalls")
VPX_SIMPLE_BALL_IMAGE_DIR = VPX_SIMPLE_BALL_USERBALLS_DIR / "balls"
VPX_SIMPLE_BALL_DECAL_DIR = VPX_SIMPLE_BALL_USERBALLS_DIR / "decals"
VPX_SIMPLE_BALL_BACKUP_DIR = Path("/opt/pincabos/backups/vpx-ball-cabinet")

def vpx_simple_ball_read_lines():
    if VPX_SIMPLE_BALL_INI.exists():
        return VPX_SIMPLE_BALL_INI.read_text(errors="replace").splitlines()
    return []

def vpx_simple_ball_write_lines(lines):
    VPX_SIMPLE_BALL_INI.parent.mkdir(parents=True, exist_ok=True)
    VPX_SIMPLE_BALL_INI.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

def vpx_simple_ball_find_section(lines, section):
    # PINCABOS_INI_UNIQUE_V1 : bornes de section par l ecrivain unique
    return pincabos_ini.Ini("\n".join(lines)).bornes(section)

def vpx_simple_ball_get(lines, section, key):
    start, end = vpx_simple_ball_find_section(lines, section)
    if start is None:
        return ""

    key_l = key.lower()
    for line in lines[start + 1:end]:
        s = line.strip()
        if not s or s.startswith(";") or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        if k.strip().lower() == key_l:
            return v.strip()
    return ""

def vpx_simple_ball_set(lines, section, key, value):
    comment = "; Modifié " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " par PinCabOS fonction(VPX Ball Image)"
    header = "[" + section + "]"
    start, end = vpx_simple_ball_find_section(lines, section)

    if start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(header)
        lines.append(comment)
        lines.append(key + " = " + value)
        return lines

    key_l = key.lower()
    key_index = None

    for i in range(start + 1, end):
        s = lines[i].strip()
        if not s or s.startswith(";") or s.startswith("#") or "=" not in s:
            continue
        k, _v = s.split("=", 1)
        if k.strip().lower() == key_l:
            key_index = i
            break

    if key_index is not None:
        if key_index > 0 and "par PinCabOS fonction(VPX Ball Image)" in lines[key_index - 1]:
            lines[key_index - 1] = comment
        else:
            lines.insert(key_index, comment)
            key_index += 1
        lines[key_index] = key + " = " + value
        return lines

    insert_at = end
    lines.insert(insert_at, comment)
    lines.insert(insert_at + 1, key + " = " + value)
    return lines

def vpx_simple_ball_backup():
    VPX_SIMPLE_BALL_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = VPX_SIMPLE_BALL_BACKUP_DIR / ("VPinballX.ini.backup-simple-ball-" + stamp)
    if VPX_SIMPLE_BALL_INI.exists():
        shutil.copy2(VPX_SIMPLE_BALL_INI, dst)
        return dst
    return None

def vpx_simple_ball_image_options(selected, folder=None):
    from urllib.parse import quote

    if folder is None:
        folder = VPX_SIMPLE_BALL_IMAGE_DIR

    folder.mkdir(parents=True, exist_ok=True)
    files = []
    for ext in ["*.png", "*.jpg", "*.jpeg", "*.webp", "*.bmp"]:
        files.extend(folder.glob(ext))

    files = sorted(set(files), key=lambda x: x.name.lower())

    opts = ['<option value="" data-url="">Ne pas changer / vide</option>']
    for f in files:
        val = str(f)
        sel = " selected" if val == selected else ""
        kind = "decals" if str(folder).endswith("/decals") else "balls"
        url = "/userdata/UserBalls/" + kind + "/" + quote(f.name, safe="")
        opts.append(
            '<option value="' + esc(val) + '" data-url="' + esc(url) + '"' + sel + '>' + esc(f.name) + '</option>'
        )

    return "\n".join(opts)

def vpx_simple_ball_card():
    lines = vpx_simple_ball_read_lines()

    overwrite = vpx_simple_ball_get(lines, "Player", "OverwriteBallImage")
    ball = vpx_simple_ball_get(lines, "Player", "BallImage")
    decal = vpx_simple_ball_get(lines, "Player", "DecalImage")

    ball_trail = vpx_simple_ball_get(lines, "Player", "BallTrail")
    ball_trail_strength = vpx_simple_ball_get(lines, "Player", "BallTrailStrength")
    cabinet_autofit_mode = vpx_simple_ball_get(lines, "Player", "CabinetAutofitMode")
    cabinet_autofit_pos = vpx_simple_ball_get(lines, "Player", "CabinetAutofitPos")
    ball_antistretch = vpx_simple_ball_get(lines, "Player", "BallAntiStretch")

    checked = "checked" if overwrite == "1" else ""

    html = """
<div class="card" style="margin-top:20px;">
  <h2>VPX Ball / Cabinet</h2>

  <p>
    Carte simple pour appliquer une image personnalisée de bille et un décalque dans
    <code>[Player]</code> du fichier <code>VPinballX.ini</code>.
  </p>

  <p>
    Fichier INI : <code>__INI__</code><br>
    Dossier billes : <code>__BALL_DIR__</code><br>\n    Dossier décalques : <code>__DECAL_DIR__</code>
  </p>

  <form method="post" action="/tools/vpx-ball-simple/apply" enctype="multipart/form-data">
    <table style="width:100%;">
      <tr>
        <td>Activer image personnalisée</td>
        <td>
          <label>
            <input type="checkbox" name="overwrite_ball_image" value="1" __CHECKED__>
            Écrire <code>OverwriteBallImage = 1</code>
          </label>
        </td>
      </tr>

      <tr>
        <td>Importer image bille</td>
        <td>
          <input type="file" id="pco-ball-upload" name="ball_upload" accept=".png,.jpg,.jpeg,.webp,.bmp" onchange="pcoUserBallUploadPreview(this, 'pco-ball-preview')">
        </td>
      </tr>

      <tr>
        <td>Ou choisir image bille existante</td>
        <td>
          <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
            <select name="ball_existing" id="pco-ball-existing" onchange="pcoUserBallPreview('pco-ball-existing','pco-ball-preview')" style="width:50%;max-width:420px;min-width:240px;padding:8px;">
              __BALL_OPTIONS__
            </select>
            <div style="width:74px;height:74px;border:1px solid rgba(255,122,0,.45);border-radius:12px;background:rgba(0,0,0,.35);display:flex;align-items:center;justify-content:center;overflow:hidden;">
              <img id="pco-ball-preview" alt="Aperçu bille" style="max-width:72px;max-height:72px;display:none;">
              <span id="pco-ball-preview-empty" style="font-size:11px;color:#aaa;text-align:center;padding:4px;">Aperçu</span>
            </div>
          </div>
        </td>
      </tr>

      <tr>
        <td>Importer image décalque</td>
        <td>
          <input type="file" id="pco-decal-upload" name="decal_upload" accept=".png,.jpg,.jpeg,.webp,.bmp" onchange="pcoUserBallUploadPreview(this, 'pco-decal-preview')">
        </td>
      </tr>

      <tr>
        <td>Ou choisir décalque existant</td>
        <td>
          <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
            <select name="decal_existing" id="pco-decal-existing" onchange="pcoUserBallPreview('pco-decal-existing','pco-decal-preview')" style="width:50%;max-width:420px;min-width:240px;padding:8px;">
              __DECAL_OPTIONS__
            </select>
            <div style="width:74px;height:74px;border:1px solid rgba(255,122,0,.45);border-radius:12px;background:rgba(0,0,0,.35);display:flex;align-items:center;justify-content:center;overflow:hidden;">
              <img id="pco-decal-preview" alt="Aperçu décalque" style="max-width:72px;max-height:72px;display:none;">
              <span id="pco-decal-preview-empty" style="font-size:11px;color:#aaa;text-align:center;padding:4px;">Aperçu</span>
            </div>
          </div>
        </td>
      </tr>

      <tr>
        <td colspan="2"><h3 style="margin-top:18px;">Trail / effet de traînée</h3></td>
      </tr>

      <tr>
        <td>Ball Trail</td>
        <td>
          <select name="ball_trail" style="width:220px;padding:8px;">
            <option value="">Ne pas changer / vide</option>
            <option value="0" __BALL_TRAIL_0__>Désactivé</option>
            <option value="1" __BALL_TRAIL_1__>Activé</option>
          </select>
        </td>
      </tr>

      <tr>
        <td>Force Ball Trail</td>
        <td>
          <input name="ball_trail_strength" value="__BALL_TRAIL_STRENGTH__" placeholder="ex: 0.5, 1.0, 2.0" style="width:220px;padding:8px;">
        </td>
      </tr>

      <tr>
        <td colspan="2"><h3 style="margin-top:18px;">Cabinet / déformation bille</h3></td>
      </tr>

      <tr>
        <td>Cabinet Autofit Mode</td>
        <td>
          <input name="cabinet_autofit_mode" value="__CABINET_AUTOFIT_MODE__" placeholder="valeur VPX" style="width:220px;padding:8px;">
        </td>
      </tr>

      <tr>
        <td>Cabinet Autofit Pos</td>
        <td>
          <input name="cabinet_autofit_pos" value="__CABINET_AUTOFIT_POS__" placeholder="valeur VPX" style="width:220px;padding:8px;">
        </td>
      </tr>

      <tr>
        <td>Ball Anti-Stretch</td>
        <td>
          <select name="ball_antistretch" style="width:220px;padding:8px;">
            <option value="">Ne pas changer / vide</option>
            <option value="0" __BALL_ANTISTRETCH_0__>Désactivé</option>
            <option value="1" __BALL_ANTISTRETCH_1__>Activé</option>
          </select>
          <p class="warn" style="margin:6px 0 0 0;">
            Utile si la bille semble étirée/déformée en mode cabinet.
          </p>
        </td>
      </tr>
    </table>

    <p style="margin-top:14px;">
      <button class="button" type="submit">Appliquer dans VPinballX.ini</button>
    </p>
  </form>


<script>
function pcoUserBallSetPreview(imgId, url) {
  const img = document.getElementById(imgId);
  const empty = document.getElementById(imgId + "-empty");

  if (!img) return;

  if (!url) {
    img.removeAttribute("src");
    img.style.display = "none";
    if (empty) {
      empty.style.display = "block";
      empty.textContent = "Aperçu";
    }
    return;
  }

  img.onload = function() {
    img.style.display = "block";
    if (empty) empty.style.display = "none";
  };

  img.onerror = function() {
    img.removeAttribute("src");
    img.style.display = "none";
    if (empty) {
      empty.style.display = "block";
      empty.textContent = "Aperçu indisponible";
    }
  };

  img.src = url + (url.includes("?") ? "&" : "?") + "v=" + Date.now();
}

function pcoUserBallPreview(selectId, imgId) {
  const sel = document.getElementById(selectId);
  if (!sel) return;

  const opt = sel.options[sel.selectedIndex];
  const url = opt ? (opt.getAttribute("data-url") || "") : "";

  pcoUserBallSetPreview(imgId, url);
}

function pcoUserBallUploadPreview(input, imgId) {
  if (!input || !input.files || !input.files[0]) return;

  const url = URL.createObjectURL(input.files[0]);
  pcoUserBallSetPreview(imgId, url);
}

document.addEventListener("DOMContentLoaded", function() {
  pcoUserBallPreview("pco-ball-existing", "pco-ball-preview");
  pcoUserBallPreview("pco-decal-existing", "pco-decal-preview");
});
</script>

  <details style="margin-top:12px;">
    <summary>Valeurs actuelles [Player]</summary>
    <pre style="white-space:pre-wrap;max-height:260px;overflow:auto;background:rgba(0,0,0,.45);border:1px solid rgba(255,176,0,.25);border-radius:12px;padding:12px;">OverwriteBallImage = __OVERWRITE__
BallImage = __BALL__
DecalImage = __DECAL__
BallTrail = __BALL_TRAIL_VALUE__
BallTrailStrength = __BALL_TRAIL_STRENGTH_VALUE__
CabinetAutofitMode = __CABINET_AUTOFIT_MODE_VALUE__
CabinetAutofitPos = __CABINET_AUTOFIT_POS_VALUE__
BallAntiStretch = __BALL_ANTISTRETCH_VALUE__</pre>
  </details>
</div>
"""
    html = html.replace("__INI__", esc(str(VPX_SIMPLE_BALL_INI)))
    html = html.replace("__BALL_DIR__", esc(str(VPX_SIMPLE_BALL_IMAGE_DIR)))
    html = html.replace("__DECAL_DIR__", esc(str(VPX_SIMPLE_BALL_DECAL_DIR)))
    html = html.replace("__CHECKED__", checked)
    html = html.replace("__BALL_OPTIONS__", vpx_simple_ball_image_options(ball, VPX_SIMPLE_BALL_IMAGE_DIR))
    html = html.replace("__DECAL_OPTIONS__", vpx_simple_ball_image_options(decal, VPX_SIMPLE_BALL_DECAL_DIR))
    html = html.replace("__OVERWRITE__", esc(overwrite if overwrite else ""))
    html = html.replace("__BALL__", esc(ball if ball else ""))
    html = html.replace("__DECAL__", esc(decal if decal else ""))

    html = html.replace("__BALL_TRAIL_0__", "selected" if ball_trail == "0" else "")
    html = html.replace("__BALL_TRAIL_1__", "selected" if ball_trail == "1" else "")
    html = html.replace("__BALL_TRAIL_STRENGTH__", esc(ball_trail_strength if ball_trail_strength else ""))
    html = html.replace("__CABINET_AUTOFIT_MODE__", esc(cabinet_autofit_mode if cabinet_autofit_mode else ""))
    html = html.replace("__CABINET_AUTOFIT_POS__", esc(cabinet_autofit_pos if cabinet_autofit_pos else ""))
    html = html.replace("__BALL_ANTISTRETCH_0__", "selected" if ball_antistretch == "0" else "")
    html = html.replace("__BALL_ANTISTRETCH_1__", "selected" if ball_antistretch == "1" else "")

    html = html.replace("__BALL_TRAIL_VALUE__", esc(ball_trail if ball_trail else ""))
    html = html.replace("__BALL_TRAIL_STRENGTH_VALUE__", esc(ball_trail_strength if ball_trail_strength else ""))
    html = html.replace("__CABINET_AUTOFIT_MODE_VALUE__", esc(cabinet_autofit_mode if cabinet_autofit_mode else ""))
    html = html.replace("__CABINET_AUTOFIT_POS_VALUE__", esc(cabinet_autofit_pos if cabinet_autofit_pos else ""))
    html = html.replace("__BALL_ANTISTRETCH_VALUE__", esc(ball_antistretch if ball_antistretch else ""))

    return html


@vpxball_bp.route("/userdata/UserBalls/<kind>/<path:filename>")
def pincabos_userballs_static(kind, filename):
    from flask import send_from_directory, abort

    if kind not in ["balls", "decals"]:
        abort(404)

    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        abort(404)

    base = VPX_SIMPLE_BALL_IMAGE_DIR if kind == "balls" else VPX_SIMPLE_BALL_DECAL_DIR
    f = base / filename

    if not f.exists() or not f.is_file():
        abort(404)

    return send_from_directory(str(base), filename)

@vpxball_bp.route("/tools/vpx-ball-simple/apply", methods=["POST"])
def tools_vpx_ball_simple_apply():
    from werkzeug.utils import secure_filename

    allowed = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    VPX_SIMPLE_BALL_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    VPX_SIMPLE_BALL_DECAL_DIR.mkdir(parents=True, exist_ok=True)

    lines = vpx_simple_ball_read_lines()
    backup = vpx_simple_ball_backup()

    overwrite = "1" if request.form.get("overwrite_ball_image") == "1" else "0"

    ball_path = request.form.get("ball_existing", "").strip()
    decal_path = request.form.get("decal_existing", "").strip()

    def save_upload(field, folder):
        f = request.files.get(field)
        if not f or not f.filename:
            return ""
        name = secure_filename(f.filename)
        ext = Path(name).suffix.lower()
        if ext not in allowed:
            raise ValueError("Extension non supportée: " + ext)
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        final = folder / (Path(name).stem + "-" + stamp + ext)
        f.save(final)
        final.chmod(0o644)
        try:
            shutil.chown(final, user="pinball", group="pinball")
        except Exception:
            pass
        return str(final)

    try:
        uploaded_ball = save_upload("ball_upload", VPX_SIMPLE_BALL_IMAGE_DIR)
        uploaded_decal = save_upload("decal_upload", VPX_SIMPLE_BALL_DECAL_DIR)
    except Exception as e:
        return page("Outils", """
<div class="card">
  <h2>Erreur import image VPX Ball</h2>
  <p class="bad">__ERR__</p>
  <p><a class="button" href="/tools">Retour Outils</a></p>
</div>
""".replace("__ERR__", esc(str(e))))

    if uploaded_ball:
        ball_path = uploaded_ball
    if uploaded_decal:
        decal_path = uploaded_decal

    ball_trail = request.form.get("ball_trail", "").strip()
    ball_trail_strength = request.form.get("ball_trail_strength", "").strip()
    cabinet_autofit_mode = request.form.get("cabinet_autofit_mode", "").strip()
    cabinet_autofit_pos = request.form.get("cabinet_autofit_pos", "").strip()
    ball_antistretch = request.form.get("ball_antistretch", "").strip()

    lines = vpx_simple_ball_set(lines, "Player", "OverwriteBallImage", overwrite)

    if ball_path:
        lines = vpx_simple_ball_set(lines, "Player", "BallImage", ball_path)

    if decal_path:
        lines = vpx_simple_ball_set(lines, "Player", "DecalImage", decal_path)

    if ball_trail in ["0", "1"]:
        lines = vpx_simple_ball_set(lines, "Player", "BallTrail", ball_trail)

    if ball_trail_strength:
        lines = vpx_simple_ball_set(lines, "Player", "BallTrailStrength", ball_trail_strength)

    if cabinet_autofit_mode:
        lines = vpx_simple_ball_set(lines, "Player", "CabinetAutofitMode", cabinet_autofit_mode)

    if cabinet_autofit_pos:
        lines = vpx_simple_ball_set(lines, "Player", "CabinetAutofitPos", cabinet_autofit_pos)

    if ball_antistretch in ["0", "1"]:
        lines = vpx_simple_ball_set(lines, "Player", "BallAntiStretch", ball_antistretch)

    lines = vpx_simple_ball_set(lines, "PinCabOS.BallCabinet", "managed_by", "PinCabOS VPX Ball Image")
    lines = vpx_simple_ball_set(lines, "PinCabOS.BallCabinet", "ball_dir", str(VPX_SIMPLE_BALL_IMAGE_DIR))
    lines = vpx_simple_ball_set(lines, "PinCabOS.BallCabinet", "decal_dir", str(VPX_SIMPLE_BALL_DECAL_DIR))
    lines = vpx_simple_ball_set(lines, "PinCabOS.BallCabinet", "updated_at", datetime.now().isoformat(timespec="seconds"))

    vpx_simple_ball_write_lines(lines)

    backup_txt = str(backup) if backup else "Aucun backup, fichier créé."

    body = """
<div class="card">
  <h2>VPX Ball / Cabinet appliqué</h2>
  <p class="ok">Les valeurs ont été écrites dans <code>[Player]</code>.</p>

  <table>
    <tr><td>INI</td><td><code>__INI__</code></td></tr>
    <tr><td>Backup</td><td><code>__BACKUP__</code></td></tr>
    <tr><td>OverwriteBallImage</td><td><code>__OVERWRITE__</code></td></tr>
    <tr><td>BallImage</td><td><code>__BALL__</code></td></tr>
    <tr><td>DecalImage</td><td><code>__DECAL__</code></td></tr>
    <tr><td>BallTrail</td><td><code>__BALL_TRAIL_RESULT__</code></td></tr>
    <tr><td>BallTrailStrength</td><td><code>__BALL_TRAIL_STRENGTH_RESULT__</code></td></tr>
    <tr><td>CabinetAutofitMode</td><td><code>__CABINET_AUTOFIT_MODE_RESULT__</code></td></tr>
    <tr><td>CabinetAutofitPos</td><td><code>__CABINET_AUTOFIT_POS_RESULT__</code></td></tr>
    <tr><td>BallAntiStretch</td><td><code>__BALL_ANTISTRETCH_RESULT__</code></td></tr>
  </table>

  <p>
    <a class="button" href="/tools">Retour Outils</a>
  </p>
</div>
"""
    body = body.replace("__INI__", esc(str(VPX_SIMPLE_BALL_INI)))
    body = body.replace("__BACKUP__", esc(backup_txt))
    body = body.replace("__OVERWRITE__", esc(overwrite))
    body = body.replace("__BALL__", esc(ball_path))
    body = body.replace("__DECAL__", esc(decal_path))
    body = body.replace("__BALL_TRAIL_RESULT__", esc(ball_trail))
    body = body.replace("__BALL_TRAIL_STRENGTH_RESULT__", esc(ball_trail_strength))
    body = body.replace("__CABINET_AUTOFIT_MODE_RESULT__", esc(cabinet_autofit_mode))
    body = body.replace("__CABINET_AUTOFIT_POS_RESULT__", esc(cabinet_autofit_pos))
    body = body.replace("__BALL_ANTISTRETCH_RESULT__", esc(ball_antistretch))

    return page("Outils", body)
# === PINCABOS SIMPLE VPX BALL CARD END ===


def register(app, page_fn):
    """Enregistre les pages de la bille VPX sur l'application."""
    global page
    page = page_fn
    app.register_blueprint(vpxball_bp)
