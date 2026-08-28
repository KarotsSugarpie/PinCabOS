"""PinCabOS B2S Configurator for VPX Standalone/Linux.

Canonical B2S configuration tool for PinCabOS.

Design rules
------------
* Edit only settings that are actually consumed by VPX B2S/B2SLegacy plugins.
* Never rewrite, patch or "enhance" a .directb2s file.
* Support the canonical global VPinballX.ini and VPX per-table override INI.
* Backup before every write, write atomically, validate after writing, and offer
  a one-click rollback for the last change made in the current web session.
* Refuse writes while VPinballX is running to avoid settings being overwritten
  by a live VPX process.
"""
from __future__ import annotations

import hashlib
import hmac
import html
import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlencode

from flask import redirect, request, session


VPX_INI = Path("/home/pinball/.local/share/VPinballX/10.8/VPinballX.ini")
TABLES_ROOT = Path("/home/pinball/Tables")
BACKUP_ROOT = Path("/home/pinball/.local/share/PinCabOS/backups/b2s-config")
LEGACY = "Plugin.B2SLegacy"
MODERN = "Plugin.B2S"
_PAGE = None

# VPX plugin source verified settings.
# B2SLegacy: B2SSettings.cpp + DMDOverlay.cpp
# B2S modern: B2SRenderer.cpp + B2SDMDOverlay.cpp
FIELDS = (
    # Legacy display settings
    ("legacy_hide_grill", LEGACY, "B2SHideGrill", "Grille / speaker panel", "Masque la grille intégrée au backglass Legacy.", "bool", "Afficher", "Masquer", "legacy"),
    ("legacy_hide_b2sdmd", LEGACY, "B2SHideB2SDMD", "DMD intégré au B2S", "Affiche ou masque le DMD/score intégré au B2S Legacy.", "bool", "Afficher", "Masquer", "legacy"),
    ("legacy_hide_backglass", LEGACY, "B2SHideB2SBackglass", "Image du backglass", "Affiche ou masque complètement le backglass Legacy.", "bool", "Afficher", "Masquer", "legacy"),
    ("legacy_hide_dmd", LEGACY, "B2SHideDMD", "Fenêtre DMD standard", "Affiche ou masque la fenêtre DMD standard du moteur Legacy.", "bool", "Afficher", "Masquer", "legacy"),
    ("legacy_dual_mode", LEGACY, "B2SDualMode", "Dual mode", "0 = auto/non défini, 1 = Authentic, 2 = Fantasy.", "dual", "", "", "legacy"),

    # Legacy DMD overlays - these are real B2SLegacy settings too.
    ("legacy_bg_overlay", LEGACY, "BackglassDMDOverlay", "DMD overlay sur Backglass", "Place le DMD comme overlay sur le backglass Legacy.", "bool", "Désactivé", "Activé", "legacy-overlay"),
    ("legacy_bg_autopos", LEGACY, "BackglassDMDAutoPos", "Position Backglass automatique", "Détecte automatiquement la zone DMD dans le backglass.", "bool", "Manuelle", "Automatique", "legacy-overlay"),
    ("legacy_bg_x", LEGACY, "BackglassDMDX", "Backglass DMD X", "Coordonnée X manuelle de l'overlay Backglass.", "int", "", "", "legacy-overlay"),
    ("legacy_bg_y", LEGACY, "BackglassDMDY", "Backglass DMD Y", "Coordonnée Y manuelle de l'overlay Backglass.", "int", "", "", "legacy-overlay"),
    ("legacy_bg_w", LEGACY, "BackglassDMDW", "Backglass DMD largeur", "Largeur manuelle de l'overlay Backglass.", "int", "", "", "legacy-overlay"),
    ("legacy_bg_h", LEGACY, "BackglassDMDH", "Backglass DMD hauteur", "Hauteur manuelle de l'overlay Backglass.", "int", "", "", "legacy-overlay"),
    ("legacy_score_overlay", LEGACY, "ScoreViewDMDOverlay", "DMD overlay sur ScoreView", "Place le DMD comme overlay sur le ScoreView / FullDMD.", "bool", "Désactivé", "Activé", "legacy-overlay"),
    ("legacy_score_autopos", LEGACY, "ScoreViewDMDAutoPos", "Position ScoreView automatique", "Détecte automatiquement la zone DMD dans le ScoreView.", "bool", "Manuelle", "Automatique", "legacy-overlay"),
    ("legacy_score_x", LEGACY, "ScoreViewDMDX", "ScoreView DMD X", "Coordonnée X manuelle de l'overlay ScoreView.", "int", "", "", "legacy-overlay"),
    ("legacy_score_y", LEGACY, "ScoreViewDMDY", "ScoreView DMD Y", "Coordonnée Y manuelle de l'overlay ScoreView.", "int", "", "", "legacy-overlay"),
    ("legacy_score_w", LEGACY, "ScoreViewDMDW", "ScoreView DMD largeur", "Largeur manuelle de l'overlay ScoreView.", "int", "", "", "legacy-overlay"),
    ("legacy_score_h", LEGACY, "ScoreViewDMDH", "ScoreView DMD hauteur", "Hauteur manuelle de l'overlay ScoreView.", "int", "", "", "legacy-overlay"),

    # Modern renderer
    ("modern_show_grill", MODERN, "ShowGrill", "Grille / speaker panel", "Affiche ou masque la grille avec le renderer B2S moderne.", "bool", "Masquer", "Afficher", "modern"),
    ("modern_bg_overlay", MODERN, "BackglassDMDOverlay", "DMD overlay sur Backglass", "Place le DMD comme overlay sur le backglass moderne.", "bool", "Désactivé", "Activé", "modern-overlay"),
    ("modern_bg_autopos", MODERN, "BackglassDMDAutoPos", "Position Backglass automatique", "Détecte automatiquement la zone DMD dans le backglass.", "bool", "Manuelle", "Automatique", "modern-overlay"),
    ("modern_bg_x", MODERN, "BackglassDMDX", "Backglass DMD X", "Coordonnée X manuelle de l'overlay Backglass.", "int", "", "", "modern-overlay"),
    ("modern_bg_y", MODERN, "BackglassDMDY", "Backglass DMD Y", "Coordonnée Y manuelle de l'overlay Backglass.", "int", "", "", "modern-overlay"),
    ("modern_bg_w", MODERN, "BackglassDMDW", "Backglass DMD largeur", "Largeur manuelle de l'overlay Backglass.", "int", "", "", "modern-overlay"),
    ("modern_bg_h", MODERN, "BackglassDMDH", "Backglass DMD hauteur", "Hauteur manuelle de l'overlay Backglass.", "int", "", "", "modern-overlay"),
    ("modern_score_overlay", MODERN, "ScoreViewDMDOverlay", "DMD overlay sur ScoreView", "Place le DMD comme overlay sur le ScoreView / FullDMD.", "bool", "Désactivé", "Activé", "modern-overlay"),
    ("modern_score_autopos", MODERN, "ScoreViewDMDAutoPos", "Position ScoreView automatique", "Détecte automatiquement la zone DMD dans le ScoreView.", "bool", "Manuelle", "Automatique", "modern-overlay"),
    ("modern_score_x", MODERN, "ScoreViewDMDX", "ScoreView DMD X", "Coordonnée X manuelle de l'overlay ScoreView.", "int", "", "", "modern-overlay"),
    ("modern_score_y", MODERN, "ScoreViewDMDY", "ScoreView DMD Y", "Coordonnée Y manuelle de l'overlay ScoreView.", "int", "", "", "modern-overlay"),
    ("modern_score_w", MODERN, "ScoreViewDMDW", "ScoreView DMD largeur", "Largeur manuelle de l'overlay ScoreView.", "int", "", "", "modern-overlay"),
    ("modern_score_h", MODERN, "ScoreViewDMDH", "ScoreView DMD hauteur", "Hauteur manuelle de l'overlay ScoreView.", "int", "", "", "modern-overlay"),
)

MANAGED = {
    LEGACY: tuple(dict.fromkeys(f[2] for f in FIELDS if f[1] == LEGACY)),
    MODERN: tuple(dict.fromkeys(f[2] for f in FIELDS if f[1] == MODERN)),
}
BOOL_KEYS = {f[2] for f in FIELDS if f[5] == "bool"}
INT_KEYS = {f[2] for f in FIELDS if f[5] == "int"}


def esc(value):
    return html.escape("" if value is None else str(value), quote=True)


def render(title, body):
    return _PAGE(title, body) if _PAGE else f"<html><body>{body}</body></html>"


def csrf():
    token = session.get("pco_b2s_csrf")
    if not isinstance(token, str) or len(token) < 20:
        token = secrets.token_urlsafe(32)
        session["pco_b2s_csrf"] = token
    return token


def csrf_ok():
    expected = session.get("pco_b2s_csrf")
    supplied = str(request.form.get("csrf", ""))
    return isinstance(expected, str) and bool(supplied) and hmac.compare_digest(supplied, expected)


def vpx_running():
    try:
        result = subprocess.run(
            ["/usr/bin/pgrep", "-u", "pinball", "-f", "VPinballX"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=4,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def lines(path):
    path = Path(path)
    return path.read_text(encoding="utf-8", errors="replace").splitlines() if path.exists() else []


def bounds(data, section):
    start = None
    for i, line in enumerate(data):
        text = line.strip()
        if text.startswith("[") and text.endswith("]"):
            if start is not None:
                return start, i
            if text[1:-1].strip().casefold() == section.casefold():
                start = i
    return start, len(data)


def getv_data(data, section, key):
    start, end = bounds(data, section)
    if start is None:
        return None
    for line in data[start + 1 : end]:
        text = line.strip()
        if not text or text.startswith(("#", ";")) or "=" not in line:
            continue
        current_key, value = line.split("=", 1)
        if current_key.strip().casefold() == key.casefold():
            return value.strip()
    return None


def getv(path, section, key):
    try:
        return getv_data(lines(path), section, key)
    except Exception:
        return None


def setv(data, section, key, value):
    out = list(data)
    start, end = bounds(out, section)
    marker = "; Modifié par PinCabOS fonction(B2S Configurator)"
    if start is not None:
        for i in range(start + 1, end):
            line = out[i]
            if "=" not in line or line.strip().startswith(("#", ";")):
                continue
            current_key, _ = line.split("=", 1)
            if current_key.strip().casefold() == key.casefold():
                match = re.match(r"^(\s*[^=]+?)(\s*=\s*)(.*)$", line)
                if i > start + 1 and "PinCabOS fonction(B2S Configurator)" in out[i - 1]:
                    out[i - 1] = marker
                else:
                    out.insert(i, marker)
                    i += 1
                out[i] = f"{match.group(1)}{match.group(2)}{value}" if match else f"{key} = {value}"
                return out
        out.insert(end, marker)
        out.insert(end + 1, f"{key} = {value}")
        return out
    if out and out[-1].strip():
        out.append("")
    out += [marker, f"[{section}]", f"{key} = {value}"]
    return out


def delv(data, section, key):
    out = list(data)
    start, end = bounds(out, section)
    if start is None:
        return out
    for i in range(start + 1, end):
        line = out[i]
        if "=" not in line or line.strip().startswith(("#", ";")):
            continue
        current_key, _ = line.split("=", 1)
        if current_key.strip().casefold() == key.casefold():
            del out[i]
            if i - 1 > start and i - 1 < len(out) and "PinCabOS fonction(B2S Configurator)" in out[i - 1]:
                del out[i - 1]
            break
    return out


def safe_table(rel):
    rel = str(rel or "").strip().replace("\\", "/")
    if not rel or rel.startswith("/") or "\x00" in rel:
        raise ValueError("Chemin de table invalide")
    root = TABLES_ROOT.resolve()
    target = (TABLES_ROOT / rel).resolve()
    if root not in target.parents or target.suffix.lower() != ".vpx" or not target.is_file():
        raise ValueError("Table VPX invalide")
    return target


def table_rows():
    result = []
    if not TABLES_ROOT.exists():
        return result
    for path in TABLES_ROOT.rglob("*.vpx"):
        try:
            rel = path.relative_to(TABLES_ROOT)
            if any(part.startswith(".") for part in rel.parts):
                continue
            result.append((rel.as_posix(), path.parent.name, path.stem))
            if len(result) >= 3000:
                break
        except Exception:
            pass
    return sorted(result, key=lambda row: (row[1].casefold(), row[2].casefold(), row[0].casefold()))


def b2s_files(vpx):
    found = []
    candidates = (vpx.with_suffix(".directb2s"), vpx.parent / f"{vpx.parent.name}.directb2s")
    for path in candidates:
        if path.exists() and path not in found:
            found.append(path)
    if not found:
        try:
            found = list(sorted(vpx.parent.glob("*.directb2s")))[:8]
        except Exception:
            pass
    return found


def engine(path=None):
    legacy_value = getv(VPX_INI, LEGACY, "Enable")
    modern_value = getv(VPX_INI, MODERN, "Enable")
    if path:
        table_legacy = getv(path, LEGACY, "Enable")
        table_modern = getv(path, MODERN, "Enable")
        legacy_value = table_legacy if table_legacy is not None else legacy_value
        modern_value = table_modern if table_modern is not None else modern_value
    legacy_on = legacy_value == "1"
    modern_on = modern_value == "1"
    if legacy_on and modern_on:
        return "both", "Conflit : Legacy + moderne actifs"
    if modern_on:
        return "modern", "B2S moderne"
    if legacy_on:
        return "legacy", "B2S Legacy"
    return "disabled", "B2S désactivé"


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def backup(target):
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    folder = BACKUP_ROOT / (time.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3))
    folder.mkdir(parents=True)
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", str(target).strip("/").replace("/", "__"))[-180:]
    before = folder / (safe_name + ".before")
    missing = folder / (safe_name + ".missing")
    meta = {
        "target": str(target),
        "backup": str(before),
        "missing": str(missing),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "sha256_before": None,
    }
    if target.exists():
        shutil.copy2(target, before)
        meta["sha256_before"] = sha256(before)
    else:
        missing.write_text("missing before save\n", encoding="utf-8")
    (folder / "manifest.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return meta


def _backup_path_allowed(path):
    root = BACKUP_ROOT.resolve()
    candidate = Path(path).resolve()
    return candidate == root or root in candidate.parents


def restore(meta):
    target_text = str(meta.get("target") or "").strip()
    before_text = str(meta.get("backup") or "").strip()
    missing_text = str(meta.get("missing") or "").strip()
    if not target_text:
        raise ValueError("Backup invalide")
    target = Path(target_text)
    before = Path(before_text) if before_text else None
    missing = Path(missing_text) if missing_text else None
    check = before or missing
    if check is None or not _backup_path_allowed(check):
        raise ValueError("Backup hors B2S Config")
    target.parent.mkdir(parents=True, exist_ok=True)
    if before and before.exists():
        expected = str(meta.get("sha256_before") or "")
        if expected and sha256(before) != expected:
            raise RuntimeError("Checksum du backup invalide")
        _atomic_copy(before, target)
    elif missing and missing.exists():
        target.unlink(missing_ok=True)
    else:
        raise FileNotFoundError("Backup introuvable")


def _atomic_copy(source, target):
    source = Path(source)
    target = Path(target)
    data = source.read_bytes()
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.restore-", dir=str(target.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            shutil.copymode(source, tmp)
        except OSError:
            pass
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)


def _write_atomic_text(target, text):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    old_mode = None
    if target.exists():
        try:
            old_mode = target.stat().st_mode & 0o777
        except OSError:
            pass
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.pincabos-b2s-", dir=str(target.parent), text=True)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, old_mode if old_mode is not None else 0o644)
        os.replace(tmp, target)
        try:
            dir_fd = os.open(str(target.parent), os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass
    finally:
        tmp.unlink(missing_ok=True)


def validate_update(section, key, value):
    if value is None:
        return
    if key in BOOL_KEYS or key == "Enable":
        if value not in {"0", "1"}:
            raise ValueError(f"Valeur booléenne invalide : {section}.{key}")
    if key == "B2SDualMode" and value not in {"0", "1", "2"}:
        raise ValueError("B2SDualMode doit valoir 0, 1 ou 2")
    if key in INT_KEYS:
        if not re.fullmatch(r"[0-9]{1,5}", value):
            raise ValueError(f"Valeur numérique invalide : {section}.{key}")
        if not 0 <= int(value) <= 65535:
            raise ValueError(f"Valeur hors limites : {section}.{key}")


def write_updates(target, updates):
    target = Path(target)
    old = lines(target)
    new = list(old)
    changed = []
    for section, key, value in updates:
        validate_update(section, key, value)
        before = getv_data(new, section, key)
        new = delv(new, section, key) if value is None else setv(new, section, key, value)
        after = getv_data(new, section, key)
        if before != after:
            changed.append((section, key, before, after))
    if old == new:
        return None, []

    if target == VPX_INI and not target.is_file():
        raise FileNotFoundError(f"VPinballX.ini officiel absent : {VPX_INI}")

    meta = backup(target)
    payload = "\n".join(new).rstrip("\n") + "\n"
    try:
        _write_atomic_text(target, payload)
        verify = lines(target)
        for section, key, value in updates:
            actual = getv_data(verify, section, key)
            if (value is None and actual is not None) or (value is not None and actual != value):
                raise RuntimeError(f"Validation échouée : {section}.{key}")
    except Exception:
        restore(meta)
        raise
    return meta, changed


def normalized(form, scope):
    is_table = scope == "table"
    selected_engine = str(form.get("engine", "")).strip()
    valid = {"legacy", "modern", "disabled"} | ({"inherit"} if is_table else set())
    if selected_engine not in valid:
        raise ValueError("Moteur B2S invalide")

    updates = []
    if selected_engine == "inherit":
        updates += [(LEGACY, "Enable", None), (MODERN, "Enable", None)]
    else:
        pair = {
            "legacy": ("1", "0"),
            "modern": ("0", "1"),
            "disabled": ("0", "0"),
        }[selected_engine]
        updates += [(LEGACY, "Enable", pair[0]), (MODERN, "Enable", pair[1])]

    sentinel = "inherit" if is_table else "default"
    for name, section, key, _title, _description, kind, _zero, _one, _group in FIELDS:
        value = str(form.get(name, sentinel)).strip()
        if kind == "bool" and value not in {"0", "1", sentinel}:
            raise ValueError(f"Valeur invalide : {key}")
        if kind == "dual" and value not in {"0", "1", "2", sentinel}:
            raise ValueError(f"Valeur invalide : {key}")
        if kind == "int":
            if value == "":
                value = sentinel
            elif value != sentinel and not re.fullmatch(r"[0-9]{1,5}", value):
                raise ValueError(f"Valeur invalide : {key}")
            elif value != sentinel and not 0 <= int(value) <= 65535:
                raise ValueError(f"Valeur hors limites : {key}")
        updates.append((section, key, None if value == sentinel else value))
    return updates


def reset_table_updates():
    updates = [(LEGACY, "Enable", None), (MODERN, "Enable", None)]
    for section, keys in MANAGED.items():
        updates.extend((section, key, None) for key in keys)
    seen = set()
    result = []
    for item in updates:
        identity = item[:2]
        if identity in seen:
            continue
        seen.add(identity)
        result.append(item)
    return result


def field_control(field, scope, ini):
    name, section, key, title, description, kind, zero, one, _group = field
    global_value = getv(VPX_INI, section, key)
    local_value = getv(ini, section, key) if ini else None
    effective = local_value if local_value is not None else global_value
    sentinel = "inherit" if scope == "table" else "default"
    selected = sentinel if (local_value is None if scope == "table" else global_value in {None, ""}) else (local_value if scope == "table" else global_value)

    if kind == "bool":
        options = [
            (sentinel, "Hériter du global" if scope == "table" else "Défaut du moteur"),
            ("0", zero),
            ("1", one),
        ]
        control = '<select name="' + esc(name) + '">' + "".join(
            f'<option value="{value}"{" selected" if value == selected else ""}>{esc(label)}</option>'
            for value, label in options
        ) + "</select>"
    elif kind == "dual":
        options = [
            (sentinel, "Hériter du global" if scope == "table" else "Défaut du moteur"),
            ("0", "Auto / non défini"),
            ("1", "Authentic"),
            ("2", "Fantasy"),
        ]
        control = '<select name="' + esc(name) + '">' + "".join(
            f'<option value="{value}"{" selected" if value == selected else ""}>{esc(label)}</option>'
            for value, label in options
        ) + "</select>"
    else:
        control = (
            f'<div class="b2s-int"><input type="number" min="0" max="65535" name="{esc(name)}" '
            f'value="{esc("" if selected == sentinel else selected)}" placeholder="{esc(sentinel)}">'
            f'<button type="button" class="button secondary mini" onclick="this.previousElementSibling.value=\'\'">'
            f'{"Hériter" if scope == "table" else "Défaut"}</button></div>'
        )

    source = "table" if local_value is not None else ("global" if effective is not None else "moteur")
    effective_label = effective if effective not in {None, ""} else "défaut"
    return (
        '<div class="b2s-row"><div>'
        f'<strong>{esc(title)}</strong><span>{esc(description)}</span>'
        f'<small><code>{esc(section)}.{esc(key)}</code> · effectif: <b>{esc(effective_label)}</b> · {source}</small>'
        f'</div><div>{control}</div></div>'
    )


def _group(fields, scope, ini):
    return "".join(field_control(field, scope, ini) for field in fields)


def _fields_for(group):
    return [field for field in FIELDS if field[8] == group]


def page(scope="global", rel="", error="", status=200):
    scope = scope if scope in {"global", "table"} else "global"
    table = None
    ini = None
    direct = []
    try:
        if scope == "table" and rel:
            table = safe_table(rel)
            ini = table.with_suffix(".ini")
            direct = b2s_files(table)
    except Exception as exc:
        error = error or str(exc)

    tables = table_rows()
    global_state, global_label = engine()
    state, label = engine(ini) if ini else (global_state, global_label)
    token = csrf()
    target = ini if ini else VPX_INI

    notices = []
    if request.args.get("saved"):
        notices.append(f'<div class="card note good">GO — configuration enregistrée et validée ({esc(request.args.get("count", "0"))} changement(s)).</div>')
    if request.args.get("nochange"):
        notices.append('<div class="card note warn">Aucun changement détecté.</div>')
    if request.args.get("rolledback"):
        notices.append('<div class="card note good">Rollback terminé. La configuration précédente a été restaurée.</div>')
    if request.args.get("reset"):
        notices.append('<div class="card note good">Overrides B2S de la table supprimés. La table hérite de nouveau des réglages globaux.</div>')
    if error:
        notices.append(f'<div class="card note bad">NOGO — {esc(error)}</div>')
    if global_state == "both":
        notices.append('<div class="card note bad"><strong>Conflit détecté :</strong> B2SLegacy et B2S moderne sont actifs globalement. Choisissez un seul moteur avant de jouer.</div>')

    tabs = (
        f'<div class="tabs"><a class="{"active" if scope == "global" else ""}" href="/tools/vpinballx/b2s?scope=global">Global</a>'
        f'<a class="{"active" if scope == "table" else ""}" href="/tools/vpinballx/b2s?scope=table">Par table</a></div>'
    )

    picker = ""
    if scope == "table":
        options = ['<option value="">— Choisir une table —</option>'] + [
            f'<option value="{esc(path)}"{" selected" if path == rel else ""}>{esc(folder)} · {esc(name)}</option>'
            for path, folder, name in tables
        ]
        picker = (
            '<div class="card"><h2>Choisir une table</h2><form method="get">'
            '<input type="hidden" name="scope" value="table">'
            f'<select name="table" onchange="this.form.submit()">{"".join(options)}</select></form></div>'
        )

    table_info = ""
    if table:
        direct_html = "<br>".join(f'<code>{esc(path)}</code>' for path in direct) or '<span class="muted">Aucun .directb2s détecté.</span>'
        table_info = (
            '<div class="card"><h2>Table sélectionnée</h2>'
            f'<p><code>{esc(table)}</code></p><p>Override VPX : <code>{esc(ini)}</code></p>'
            f'<p>Backglass : {direct_html}</p></div>'
        )

    editor = ""
    if scope == "global" or table:
        if scope == "table":
            local_legacy = getv(ini, LEGACY, "Enable")
            local_modern = getv(ini, MODERN, "Enable")
            if local_legacy is None and local_modern is None:
                engine_selected = "inherit"
            elif (local_legacy, local_modern) == ("1", "0"):
                engine_selected = "legacy"
            elif (local_legacy, local_modern) == ("0", "1"):
                engine_selected = "modern"
            elif (local_legacy, local_modern) == ("0", "0"):
                engine_selected = "disabled"
            else:
                engine_selected = state if state in {"legacy", "modern", "disabled"} else "inherit"
            engine_options = [
                ("inherit", "Hériter du moteur global"),
                ("legacy", "B2S Legacy — compatibilité"),
                ("modern", "B2S moderne — renderer natif VPX"),
                ("disabled", "Désactiver B2S pour cette table"),
            ]
        else:
            engine_selected = state if state in {"legacy", "modern", "disabled"} else "legacy"
            engine_options = [
                ("legacy", "B2S Legacy — compatibilité"),
                ("modern", "B2S moderne — renderer natif VPX"),
                ("disabled", "Désactiver B2S"),
            ]

        engine_html = '<select id="b2sEngine" name="engine">' + "".join(
            f'<option value="{value}"{" selected" if value == engine_selected else ""}>{esc(text)}</option>'
            for value, text in engine_options
        ) + "</select>"

        legacy_main = _group(_fields_for("legacy"), scope, ini)
        legacy_overlay = _group(_fields_for("legacy-overlay"), scope, ini)
        modern_main = _group(_fields_for("modern"), scope, ini)
        modern_overlay = _group(_fields_for("modern-overlay"), scope, ini)

        reset_button = ""
        if scope == "table":
            reset_button = (
                '<button class="button secondary" type="submit" formaction="/tools/vpinballx/b2s/reset-table" '
                'onclick="return confirm(\'Supprimer tous les overrides B2S de cette table et revenir aux valeurs globales ?\')">'
                'Réinitialiser cette table</button>'
            )

        editor = f'''<form id="b2sForm" method="post" action="/tools/vpinballx/b2s/save">
<input type="hidden" name="csrf" value="{esc(token)}"><input type="hidden" name="scope" value="{scope}"><input type="hidden" name="table" value="{esc(rel)}">
<div class="grid">
  <div class="card"><span class="kick">Moteur</span><h2>{esc(label)}</h2><p>Legacy privilégie la compatibilité. Moderne utilise le renderer B2S natif actuel de VPX.</p>{engine_html}
    <div class="actions"><button type="button" class="button secondary" onclick="pcoB2SCabinetPreset()">Preset cabinet propre</button></div>
  </div>
  <div class="card"><span class="kick">Qualité lumière</span><h2>Fidélité native maximale</h2><p>Le moteur Legacy initialise Lamps, GI, LED et Solenoids avec <strong>0 frame-skipping</strong>. PinCabOS conserve ce rendu maximal et n'invente pas de curseur de luminosité que VPX ignorerait.</p><p><strong>Les intensités et couleurs du .directb2s restent celles de l'auteur.</strong></p></div>
</div>
<div class="card engine-panel" data-engine-panel="legacy"><span class="kick">Compatibilité</span><h2>B2S Legacy</h2><div class="settings">{legacy_main}</div><details><summary>DMD overlays Legacy</summary><div class="settings">{legacy_overlay}</div></details></div>
<div class="card engine-panel" data-engine-panel="modern"><span class="kick">Renderer natif VPX</span><h2>B2S moderne</h2><div class="settings">{modern_main}</div><details><summary>DMD overlays modernes</summary><div class="settings">{modern_overlay}</div></details></div>
<div class="card save"><div><strong>Cible</strong><br><code>{esc(target)}</code><br><small>{"existe" if target and target.exists() else "sera créé si nécessaire"}</small></div><div class="actions"><a class="button secondary" href="/tools">Retour Outils</a>{reset_button}<button class="button" type="submit">Enregistrer B2S</button></div></div>
</form>'''
    else:
        editor = '<div class="card empty"><h2>Sélectionne une table</h2><p>L’override sera le fichier <code>.ini</code> de même nom que le <code>.vpx</code>. Aucun <code>.directb2s</code> ne sera modifié.</p></div>'

    backup_meta = session.get("pco_b2s_last_backup")
    rollback = ""
    if isinstance(backup_meta, dict):
        rollback = (
            '<div class="card save"><div><span class="kick">Sécurité</span><h2>Rollback dernière écriture</h2>'
            f'<code>{esc(backup_meta.get("target"))}</code></div>'
            '<form method="post" action="/tools/vpinballx/b2s/rollback" onsubmit="return confirm(\'Restaurer le backup précédent ?\')">'
            f'<input type="hidden" name="csrf" value="{esc(token)}"><button class="button secondary">Restaurer</button></form></div>'
        )

    body = f'''<style>
.b2s{{max-width:1500px;margin:auto;color:#f7f1ff}}.hero{{padding:24px;margin-bottom:16px;border:1px solid rgba(255,145,24,.35);border-radius:20px;background:radial-gradient(circle at 90% 0,rgba(255,138,22,.14),transparent 32%),radial-gradient(circle at 5% 100%,rgba(155,92,255,.16),transparent 35%),rgba(13,7,25,.84)}}.hero h1{{margin:3px 0;color:#fff;font-size:40px}}.hero h1 span{{color:#ff9621}}.badges,.actions,.tabs{{display:flex;gap:8px;flex-wrap:wrap}}.badges span,.tabs a{{padding:7px 10px;border:1px solid rgba(255,255,255,.13);border-radius:999px;background:rgba(255,255,255,.04)}}.tabs{{margin-bottom:16px}}.tabs a{{text-decoration:none;color:#e1d5ec;font-weight:800}}.tabs .active{{background:#ff8a16;color:#1b0a00}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}.kick{{color:#ffad3f;text-transform:uppercase;letter-spacing:.12em;font-size:11px;font-weight:900}}.settings{{margin-top:10px;border:1px solid rgba(255,255,255,.1);border-radius:14px;overflow:hidden}}.b2s-row{{display:grid;grid-template-columns:1.25fr .75fr;gap:14px;align-items:center;padding:13px;border-bottom:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.03)}}.b2s-row:last-child{{border-bottom:0}}.b2s-row strong,.b2s-row span,.b2s-row small{{display:block}}.b2s-row span{{color:#cbbdd8;font-size:13px;margin-top:3px}}.b2s-row small{{color:#aa9ab9;margin-top:5px}}.b2s-row select,.b2s-row input,.card select{{width:100%;min-height:40px}}.b2s-int{{display:grid;grid-template-columns:1fr auto;gap:6px}}.mini{{padding:7px 9px!important}}.save{{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap}}.note{{border-left:4px solid currentColor!important}}.good{{color:#71f2a6}}.warn{{color:#ffbe5b}}.bad{{color:#ff7c7c}}.muted{{opacity:.72}}.empty{{text-align:center;padding:30px!important}}details summary{{cursor:pointer;color:#d9b3ff;font-weight:800;padding:12px 0}}.engine-panel.pco-hidden{{display:none}}@media(max-width:950px){{.grid,.b2s-row{{grid-template-columns:1fr}}}}
</style>
<div class="b2s"><section class="hero"><span class="kick">PinCabOS · VPX Linux</span><h1><span>B2S</span> Configurator</h1><p>Configuration globale ou individuelle du moteur B2S Linux de VPX, avec backup, validation et rollback. Les fichiers <code>.directb2s</code> ne sont jamais réécrits.</p><div class="badges"><span>Global : {esc(global_label)}</span><span>{len(tables)} table(s)</span><span>INI global : {"présent" if VPX_INI.exists() else "absent"}</span><span>.directb2s lecture seule</span></div></section>{''.join(notices)}{tabs}{picker}{table_info}{editor}{rollback}</div>
<script>
function pcoB2SSelectedEngine(){{let e=document.getElementById('b2sEngine');if(!e)return '';let v=e.value;return v==='inherit'?'{esc(global_state)}':v;}}
function pcoB2SSyncPanels(){{let v=pcoB2SSelectedEngine();document.querySelectorAll('[data-engine-panel]').forEach(p=>p.classList.toggle('pco-hidden',p.dataset.enginePanel!==v));}}
function pcoSet(name,value){{let el=document.querySelector('[name="'+name+'"]');if(el)el.value=value;}}
function pcoB2SCabinetPreset(){{let v=pcoB2SSelectedEngine();if(v==='legacy'){{pcoSet('legacy_hide_grill','1');pcoSet('legacy_hide_backglass','0');pcoSet('legacy_hide_b2sdmd','0');pcoSet('legacy_hide_dmd','1');pcoSet('legacy_dual_mode','0');}}else if(v==='modern'){{pcoSet('modern_show_grill','0');}}}}
const eng=document.getElementById('b2sEngine');if(eng){{eng.addEventListener('change',pcoB2SSyncPanels);pcoB2SSyncPanels();}}
const form=document.getElementById('b2sForm');if(form)form.addEventListener('submit',e=>{{if(!confirm('Enregistrer ces réglages B2S ? Un backup sera créé avant écriture.'))e.preventDefault();}});
</script>'''
    return render("B2S Configurator", body), status


def register(app, page_helper):
    global _PAGE
    _PAGE = page_helper

    @app.route("/tools/vpinballx/b2s", methods=["GET"])
    def b2s_page():
        return page(str(request.args.get("scope", "global")), str(request.args.get("table", "")))

    @app.route("/tools/vpinballx/b2s/save", methods=["POST"])
    def b2s_save():
        scope = str(request.form.get("scope", "global"))
        rel = str(request.form.get("table", ""))
        if not csrf_ok():
            return page(scope, rel, "Jeton de session invalide. Rien n'a été modifié.", 403)
        if vpx_running():
            return page(scope, rel, "Une table VPX est ouverte. Ferme-la avant d'enregistrer.", 409)
        try:
            if scope not in {"global", "table"}:
                raise ValueError("Portée invalide")
            target = VPX_INI if scope == "global" else safe_table(rel).with_suffix(".ini")
            meta, changed = write_updates(target, normalized(request.form, scope))
            if meta:
                session["pco_b2s_last_backup"] = meta
            query = {"scope": scope, "saved": "1", "count": str(len(changed))} if changed else {"scope": scope, "nochange": "1"}
            if rel:
                query["table"] = rel
            return redirect("/tools/vpinballx/b2s?" + urlencode(query))
        except Exception as exc:
            return page(scope, rel, str(exc), 400)

    @app.route("/tools/vpinballx/b2s/reset-table", methods=["POST"])
    def b2s_reset_table():
        scope = str(request.form.get("scope", "table"))
        rel = str(request.form.get("table", ""))
        if scope != "table":
            return page("global", "", "Réinitialisation disponible uniquement par table.", 400)
        if not csrf_ok():
            return page(scope, rel, "Jeton de session invalide. Rien n'a été modifié.", 403)
        if vpx_running():
            return page(scope, rel, "Une table VPX est ouverte. Ferme-la avant de réinitialiser.", 409)
        try:
            target = safe_table(rel).with_suffix(".ini")
            if not target.exists():
                return redirect("/tools/vpinballx/b2s?" + urlencode({"scope": "table", "table": rel, "nochange": "1"}))
            meta, changed = write_updates(target, reset_table_updates())
            if meta:
                session["pco_b2s_last_backup"] = meta
            query = {"scope": "table", "table": rel, "reset": "1", "count": str(len(changed))}
            return redirect("/tools/vpinballx/b2s?" + urlencode(query))
        except Exception as exc:
            return page(scope, rel, str(exc), 400)

    @app.route("/tools/vpinballx/b2s/rollback", methods=["POST"])
    def b2s_rollback():
        if not csrf_ok():
            return page("global", "", "Jeton de session invalide.", 403)
        if vpx_running():
            return page("global", "", "Une table VPX est ouverte. Ferme-la avant le rollback.", 409)
        meta = session.get("pco_b2s_last_backup")
        if not isinstance(meta, dict):
            return page("global", "", "Aucun backup disponible dans cette session.", 400)
        try:
            restore(meta)
            session.pop("pco_b2s_last_backup", None)
            return redirect("/tools/vpinballx/b2s?rolledback=1")
        except Exception as exc:
            return page("global", "", f"Rollback impossible : {exc}", 500)


if __name__ == "__main__":
    state, label = engine()
    print("PinCabOS B2S Configurator — audit lecture seule")
    print(f"VPinballX.ini : {VPX_INI}")
    print(f"Moteur        : {label} ({state})")
    print(f"Tables        : {len(table_rows())}")
