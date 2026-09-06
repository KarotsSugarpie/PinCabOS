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

from pincabos_webapp_supporters import (
    pincabos_about_supporters_default,
    pincabos_about_supporters_load,
    pincabos_about_supporters_normalize_list,
    pincabos_about_supporters_save,
)

import pincabos_webapp_dev_admin
from pincabos_webapp_core import esc, pincabos_version
from pincabos_webapp_dev_admin import pincabos_admin_require_login

admin_pages_bp = Blueprint("admin_pages", __name__)

page = None  # gabarit HTML commun, posé par register()


# ---------------------------------------------------------------------------
# Identifiants admin / dev (repris d'app.py)
# ---------------------------------------------------------------------------
# === PINCABOS DEV REAL LOGIN START ===


# ---------------------------------------------------------------------------
# Testeurs / Soutiens fondateurs (repris d'app.py)
# ---------------------------------------------------------------------------

# === PINCABOS ABOUT SUPPORTERS ADMIN START ===


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
