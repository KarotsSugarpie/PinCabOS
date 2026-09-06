"""Pages d'administration de la WebApp PinCabOS : identifiants admin, page admin composée, testeurs et soutiens
(« À propos »), fichier maître version.json.

Aplatissement (PINCABOS_WEBAPP_MODULES_V1, lot 10) : la page admin était le résultat de deux enrobages successifs
posés par réaffectation du nom `pincabos_admin_page` dans des blocs try (carte supporters, puis carte Version) ;
elle est ici composée en séquence, sans remplacement de vue. L'enrobage de la page « À propos » ne trouvait jamais
sa route (déclarée plus tard par PinCabOS-AboutHelp) : retiré avec ses deux helpers morts. Le reste est repris
tel quel d'app.py. Les identifiants et `pincabos_admin_page` restent réexportés par app.py pour le module
dev_admin, qui les lit dans ses globals.
"""
from __future__ import annotations

import os
from pathlib import Path

from flask import Blueprint, redirect, request

import pincabos_webapp_dev_admin
from pincabos_webapp_core import esc, pincabos_version
from pincabos_webapp_dev_admin import pincabos_admin_require_login

admin_pages_bp = Blueprint("admin_pages", __name__)

page = None  # gabarit HTML commun, posé par register()


# ---------------------------------------------------------------------------
# Identifiants admin / dev (repris d'app.py)
# ---------------------------------------------------------------------------
# === PINCABOS DEV REAL LOGIN START ===
# PINCABOS_ADMIN_CREDENTIALS_FAIL_CLOSED_V1
def _pco_read_auth_value(env_name, *paths):
    value = os.environ.get(env_name, "").strip()
    if value:
        return value
    for raw_path in paths:
        try:
            candidate = Path(raw_path)
            if candidate.is_file():
                value = candidate.read_text(encoding="utf-8").strip()
                if value:
                    return value
        except OSError:
            pass
    return ""


ADMIN_LOGIN_USER = _pco_read_auth_value(
    "PINCABOS_ADMIN_LOGIN",
    "/opt/pincabos/config/admin-login.txt",
    "/opt/pincabos/config/dev-login.txt",
)
ADMIN_LOGIN_PASS = _pco_read_auth_value(
    "PINCABOS_ADMIN_PASSWORD",
    "/opt/pincabos/config/admin-password.txt",
    "/opt/pincabos/config/dev-password.txt",
)
# PINCABOS_ADMIN_CREDENTIALS_FAIL_CLOSED_V1_END


# PINCABOS_ADMIN_DEFAULT_CREDENTIALS_V1
# Les fichiers de secrets ne sont pas versionnes : sur une image fraiche ils
# manquent et les pages /admin et /dev repondaient "identifiants non
# configures". On retombe sur un identifiant par DEFAUT documente, que
# `pincabos-admin-password` permet de remplacer, et les pages affichent un
# avertissement tant qu'il est en place.
PINCABOS_DEFAULT_ADMIN_USER = "admin"
PINCABOS_DEFAULT_ADMIN_PASS = "PinCabOS123$"

# La page /dev a ses PROPRES identifiants : deux acces distincts, deux secrets
# distincts. Les fichiers dev-login.txt / dev-password.txt restent maitres.
PINCABOS_DEFAULT_DEV_USER = "PinCabOsDev"
PINCABOS_DEFAULT_DEV_PASS = "PinCabOSDev123$"

PINCABOS_ADMIN_CREDENTIALS_ARE_DEFAULT = not (ADMIN_LOGIN_USER and ADMIN_LOGIN_PASS)

if not ADMIN_LOGIN_USER:
    ADMIN_LOGIN_USER = PINCABOS_DEFAULT_ADMIN_USER
if not ADMIN_LOGIN_PASS:
    ADMIN_LOGIN_PASS = PINCABOS_DEFAULT_ADMIN_PASS
# Fichier present mais illisible par la WebApp (proprietaire root) : sans ce
# controle, on retombe sur le defaut sans rien dire et l'ancien mot de passe
# continue de fonctionner.
PINCABOS_ADMIN_UNREADABLE_SECRETS = [
    candidate
    for candidate in (
        "/opt/pincabos/config/admin-password.txt",
        "/opt/pincabos/config/admin-login.txt",
        "/opt/pincabos/config/dev-password.txt",
    )
    if os.path.exists(candidate) and not os.access(candidate, os.R_OK)
]
# PINCABOS_ADMIN_DEFAULT_CREDENTIALS_V1_END


# ---------------------------------------------------------------------------
# Testeurs / Soutiens fondateurs (repris d'app.py)
# ---------------------------------------------------------------------------

# === PINCABOS ABOUT SUPPORTERS ADMIN START ===
ABOUT_SUPPORTERS_CONFIG = Path("/opt/pincabos/config/about-supporters.json")

def pincabos_about_supporters_default():
    return {
        "title": "Testeurs / Soutiens fondateurs",
        "intro": "Merci aux personnes qui aident à tester PinCabOS, rapporter les problèmes, proposer des idées et soutenir le développement du projet.",
        "supporters": [
            "Strung Flo",
            "Nicolas Prou",
            "Olivier Chéron",
        ],
        "founders_title": "Nom Fondateurs",
        "founders": [],
    }

def pincabos_about_supporters_normalize_list(value):
    if isinstance(value, str):
        return [x.strip() for x in value.splitlines() if x.strip()]
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return []

def pincabos_about_supporters_load():
    import json

    default = pincabos_about_supporters_default()

    try:
        if ABOUT_SUPPORTERS_CONFIG.exists():
            data = json.loads(ABOUT_SUPPORTERS_CONFIG.read_text(errors="replace"))
            if not isinstance(data, dict):
                data = {}
        else:
            data = {}
    except Exception:
        data = {}

    supporters = pincabos_about_supporters_normalize_list(data.get("supporters", default["supporters"]))
    founders = pincabos_about_supporters_normalize_list(data.get("founders", default["founders"]))

    if not supporters:
        supporters = default["supporters"]

    return {
        "title": str(data.get("title") or default["title"]).strip(),
        "intro": str(data.get("intro") or default["intro"]).strip(),
        "supporters": supporters,
        "founders_title": str(data.get("founders_title") or default["founders_title"]).strip(),
        "founders": founders,
    }

def pincabos_about_supporters_save(data):
    import json
    import datetime

    ABOUT_SUPPORTERS_CONFIG.parent.mkdir(parents=True, exist_ok=True)

    backup_dir = Path("/opt/pincabos/backups/about-supporters")
    backup_dir.mkdir(parents=True, exist_ok=True)

    try:
        backup_dir.chmod(0o775)
    except Exception:
        pass

    if ABOUT_SUPPORTERS_CONFIG.exists():
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = backup_dir / ("about-supporters.json.backup-admin-" + ts)
        backup.write_text(ABOUT_SUPPORTERS_CONFIG.read_text(errors="replace"), encoding="utf-8")

    ABOUT_SUPPORTERS_CONFIG.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8"
    )

    try:
        ABOUT_SUPPORTERS_CONFIG.chmod(0o664)
    except Exception:
        pass


def pincabos_about_supporters_admin_card():
    data = pincabos_about_supporters_load()
    supporters_text = "\n".join(data.get("supporters", []))
    founders_text = "\n".join(data.get("founders", []))

    return """
<!-- PINCABOS_ADMIN_ABOUT_SUPPORTERS_CARD -->
<div class="card" id="about-supporters" style="margin-top:20px;">
  <h2>About - Testeurs / Soutiens fondateurs</h2>
  <p>Modifie la section affichée dans <code>/about</code>.</p>

  <form method="post" action="/admin/about-supporters/save">
    <label>Titre<br>
      <input name="title" value="__TITLE__" style="width:95%;padding:10px;">
    </label>

    <p>
      <label>Texte<br>
        <textarea name="intro" rows="3" style="width:95%;padding:10px;">__INTRO__</textarea>
      </label>
    </p>

    <p>
      <label>Noms Testeurs / Soutiens, un par ligne<br>
        <textarea name="supporters" rows="8" style="width:95%;padding:10px;">__SUPPORTERS__</textarea>
      </label>
    </p>

    <p>
      <label>Nom Fondateurs<br>
        <input name="founders_title" value="__FOUNDERS_TITLE__" style="width:95%;padding:10px;">
      </label>
    </p>

    <p>
      <label>Noms Fondateurs, un par ligne<br>
        <textarea name="founders" rows="6" style="width:95%;padding:10px;">__FOUNDERS__</textarea>
      </label>
      <small style="opacity:.75;">Dans About, ces noms restent dans la même section et apparaissent avec deux étoiles de chaque côté.</small>
    </p>

    <p>
      <button class="button" type="submit">💾 Sauvegarder Testeurs / Soutiens</button>
      <a class="button secondary" href="/about#testeurs-soutiens-fondateurs">👁️ Voir dans About</a>
    </p>
  </form>
</div>
""".replace("__TITLE__", esc(data.get("title", ""))) \
   .replace("__INTRO__", esc(data.get("intro", ""))) \
   .replace("__SUPPORTERS__", esc(supporters_text)) \
   .replace("__FOUNDERS_TITLE__", esc(data.get("founders_title", "Nom Fondateurs"))) \
   .replace("__FOUNDERS__", esc(founders_text))


# === PINCABOS FOOTER ABOUT SUPPORTERS START ===
# PINCABOS_FOOTER_LAYOUT_V14_1
# Les contributeurs sont rendus directement à droite du QR dans le footer.
def pincabos_footer_supporters_inline_html():
    try:
        data = pincabos_about_supporters_load()
    except Exception:
        data = {}

    title = esc(str(data.get("title") or "Testeurs / Soutiens fondateurs"))
    intro = esc(str(
        data.get("intro")
        or "Merci aux personnes qui aident à tester PinCabOS, rapporter les problèmes, proposer des idées et soutenir le développement du projet."
    ))

    founders = data.get("founders") or []
    supporters = data.get("supporters") or []

    entries = []
    seen = set()

    for name in founders:
        clean = str(name or "").strip()
        key = clean.casefold()
        if clean and key not in seen:
            seen.add(key)
            entries.append(("founder", clean))

    for name in supporters:
        clean = str(name or "").strip()
        key = clean.casefold()
        if clean and key not in seen:
            seen.add(key)
            entries.append(("supporter", clean))

    tags = []
    for kind, name in entries:
        stars = "★★" if kind == "founder" else "★"
        tags.append(
            '<span class="pco-footer-contributor-v14 ' + kind + '">'
            '<i>' + stars + '</i><strong>' + esc(name) + '</strong><i>' + stars + '</i>'
            '</span>'
        )

    if not tags:
        tags.append('<span class="pco-footer-contributors-empty-v14">Aucun testeur/supporter configuré.</span>')

    return (
        '<section id="pincabos-footer-supporters-inline-v14" '
        'class="pincabos-footer-supporters-inline-v14">'
        '<h2>★ ' + title + ' ★</h2>'
        '<p>' + intro + '</p>'
        '<div class="pco-footer-contributors-list-v14">' + "".join(tags) + '</div>'
        '</section>'
    )


def _admin_page_avec_carte_supporters(html):
    """Insère la carte « Testeurs / Soutiens fondateurs » après la carte Publish / Cleanup (ex-enrobage 1)."""
    card = pincabos_about_supporters_admin_card()

    if "PINCABOS_ADMIN_ABOUT_SUPPORTERS_CARD" in str(html):
        return html

    def _pco_insert_before_footer(body, card):
        # Position voulue:
        # APRÈS la carte complète qui contient "Publish / Cleanup PinCabOS",
        # pas dans la carte, pas juste après les boutons, pas dans le footer.

        import re

        def _pco_find_matching_div_end(src, div_start):
            # Trouve le </div> correspondant au <div ...> de div_start.
            tag_re = re.compile(r'<(/?)div\b[^>]*>', re.IGNORECASE)
            depth = 0

            for m in tag_re.finditer(src, div_start):
                closing = m.group(1) == "/"

                if not closing:
                    depth += 1
                else:
                    depth -= 1
                    if depth == 0:
                        return m.end()

            return -1

        title_idx = body.find("Publish / Cleanup PinCabOS")
        if title_idx != -1:
            # Trouver le début de la carte contenant ce titre.
            card_start = body.rfind('<div class="card"', 0, title_idx)
            if card_start == -1:
                card_start = body.rfind("<div", 0, title_idx)

            if card_start != -1:
                card_end = _pco_find_matching_div_end(body, card_start)
                if card_end != -1:
                    return body[:card_end] + "\n" + card + body[card_end:]

        # Fallback: avant Version PinCabOS, pour rester dans la zone admin.
        version_idx = body.find("PINCABOS_ADMIN_VERSION_JSON_CARD")
        if version_idx != -1:
            version_card_start = body.rfind('<div class="card"', 0, version_idx)
            if version_card_start != -1:
                return body[:version_card_start] + card + "\n" + body[version_card_start:]

        # Fallback: avant le footer parent complet.
        lower = body.lower()
        footer_parent = lower.find('id="pincabos-support-footer-static"')
        if footer_parent != -1:
            div_idx = lower.rfind("<div", 0, footer_parent)
            insert_idx = div_idx if div_idx != -1 else footer_parent
            return body[:insert_idx] + card + "\n" + body[insert_idx:]

        return body + "\n" + card


    if isinstance(html, tuple):
        body = str(html[0])
        rest = html[1:]
        body = _pco_insert_before_footer(body, card)
        return (body,) + rest

    body = str(html)
    body = _pco_insert_before_footer(body, card)
    return body

@admin_pages_bp.route("/admin/about-supporters/save", methods=["POST"])
def pincabos_admin_about_supporters_save():
    guard = pincabos_admin_require_login()
    if guard:
        return guard

    default = pincabos_about_supporters_default()

    title = (request.form.get("title", "") or "").strip() or default["title"]
    intro = (request.form.get("intro", "") or "").strip() or default["intro"]
    supporters = pincabos_about_supporters_normalize_list(request.form.get("supporters", "") or "")
    founders_title = (request.form.get("founders_title", "") or "").strip() or default["founders_title"]
    founders = pincabos_about_supporters_normalize_list(request.form.get("founders", "") or "")

    data = {
        "title": title,
        "intro": intro,
        "supporters": supporters,
        "founders_title": founders_title,
        "founders": founders,
    }

    pincabos_about_supporters_save(data)
    return redirect("/admin#about-supporters")


def pincabos_admin_version_json_card_html():
    return f"""
<!-- PINCABOS_ADMIN_VERSION_JSON_CARD -->
<div class="card" id="version-json" style="margin-top:20px;">
  <h2>Version PinCabOS</h2>
  <p>Cette section met à jour le fichier maître <code>/opt/pincabos/config/version.json</code>.</p>

  <form method="post" action="/admin/version/save">
    <div style="display:grid; grid-template-columns:repeat(2,minmax(220px,1fr)); gap:12px;">
      <label>Nom<br><input name="name" value="{esc(pincabos_version().get("name", "PinCabOS"))}" style="width:95%; padding:10px;"></label>
      <label>Version<br><input name="version" value="{esc(pincabos_version().get("version", ""))}" style="width:95%; padding:10px;"></label>
      <label>Build<br><input name="build" value="{esc(pincabos_version().get("build", ""))}" style="width:95%; padding:10px;"></label>
      <label>Canal<br><input name="channel" value="{esc(pincabos_version().get("channel", ""))}" style="width:95%; padding:10px;"></label>
      <label>Codename<br><input name="codename" value="{esc(pincabos_version().get("codename", ""))}" style="width:95%; padding:10px;"></label>
      <label>Auteur<br><input name="author" value="{esc(pincabos_version().get("author", "Karots Sugarpie"))}" style="width:95%; padding:10px;"></label>
      <label>Update channel<br><input name="update_channel" value="{esc(pincabos_version().get("update_channel", ""))}" style="width:95%; padding:10px;"></label>
      <label>Update base URL<br><input name="update_base_url" value="{esc(pincabos_version().get("update_base_url", ""))}" style="width:95%; padding:10px;"></label>
      <label>Latest JSON URL<br><input name="latest_json_url" value="{esc(pincabos_version().get("latest_json_url", ""))}" style="width:95%; padding:10px;"></label>
    </div>

    <p style="margin-top:14px;">
      <button class="button" type="submit">💾 Sauvegarder la version</button>
    </p>
  </form>
</div>
"""

def _admin_page_avec_carte_version(html):
    """Insère la carte « Version PinCabOS » sous le titre (ex-enrobage 2)."""
    card = pincabos_admin_version_json_card_html()

    if "PINCABOS_ADMIN_VERSION_JSON_CARD" in str(html):
        return html

    if isinstance(html, tuple):
        body = str(html[0])
        rest = html[1:]
        if "<h1>Admin PinCabOS</h1>" in body:
            body = body.replace("<h1>Admin PinCabOS</h1>", "<h1>Admin PinCabOS</h1>\n" + card, 1)
        elif "</main>" in body:
            body = body.replace("</main>", card + "\n</main>", 1)
        else:
            body = card + "\n" + body
        return (body,) + rest

    body = str(html)
    if "<h1>Admin PinCabOS</h1>" in body:
        body = body.replace("<h1>Admin PinCabOS</h1>", "<h1>Admin PinCabOS</h1>\n" + card, 1)
    elif "</main>" in body:
        body = body.replace("</main>", card + "\n</main>", 1)
    else:
        body = card + "\n" + body
    return body

@admin_pages_bp.route("/admin/version/save", methods=["POST"])
def pincabos_admin_version_save():
    guard = pincabos_admin_require_login()
    if guard:
        return guard

    import json
    import datetime
    from pathlib import Path

    version_path = Path("/opt/pincabos/config/version.json")
    backup_dir = Path("/opt/pincabos/backups/version-json")
    backup_dir.mkdir(parents=True, exist_ok=True)
    version_path.parent.mkdir(parents=True, exist_ok=True)

    if version_path.exists():
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = backup_dir / ("version.json.backup-admin-light-" + ts)
        backup.write_text(version_path.read_text(errors="replace"), encoding="utf-8")

    keys = [
        "name",
        "version",
        "build",
        "channel",
        "codename",
        "author",
        "update_channel",
        "update_base_url",
        "latest_json_url",
    ]

    clean = {}
    for key in keys:
        clean[key] = (request.form.get(key, "") or "").strip()

    clean["managed_by"] = "PinCabOS"
    clean["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    version_path.write_text(
        json.dumps(clean, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8"
    )

    return redirect("/admin#version-json")

# ---------------------------------------------------------------------------
# Page admin : base du module dev_admin, puis les deux cartes, dans l'ordre où
# les anciens enrobages successifs les posaient (supporters, puis Version).
# ---------------------------------------------------------------------------

def pincabos_admin_page(*args, **kwargs):
    html = pincabos_webapp_dev_admin.pco_admin_page_base(*args, **kwargs)
    html = _admin_page_avec_carte_supporters(html)
    return _admin_page_avec_carte_version(html)


def register(app, page_fn):
    """Enregistre les actions d'administration (supporters, version.json) sur l'application."""
    global page
    page = page_fn
    app.register_blueprint(admin_pages_bp)
