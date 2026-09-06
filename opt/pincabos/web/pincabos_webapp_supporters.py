"""Testeurs et soutiens fondateurs de PinCabOS : fichier de configuration, lecture / écriture, pied de page commun.

Repris tels quels du module admin (PINCABOS_WEBAPP_AUTONOMIE_V1) : le gabarit et les pages d'administration
l'importent tous deux, sans cycle.
"""
from __future__ import annotations

from pathlib import Path

from pincabos_webapp_core import esc


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
