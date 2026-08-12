# PinCabOS-PackageIcon.py
# Associe le logo PCOSBallDec aux fichiers .PinCabOS dans PinCab Explorer.
# N'affecte pas les fichiers .PinCabOS.part.

from pathlib import Path
from flask import current_app, send_file, abort
import os
import re


ICON_NAME = "PCOSBallDec-20260607-054022.png"

ICON_CANDIDATES = [
    Path(__file__).resolve().parent / "static" / "pincabos-logo.png",
    Path("/opt/pincabos/media/images/balls") / ICON_NAME,
    Path("/home/pinball/images/ball") / ICON_NAME,
    Path("/home/pinball/Images/ball") / ICON_NAME,
    Path("/home/pinball/images/balls") / ICON_NAME,
    Path("/home/pinball/Images/balls") / ICON_NAME,
    Path("/home/pinball/.vpinball/images/ball") / ICON_NAME,
    Path("/home/pinball/.local/share/VPinballX/images/ball") / ICON_NAME,
    Path("/opt/pincabos/web/static/images/ball") / ICON_NAME,
    Path("/opt/pincabos/web/static/pincabos-assets") / ICON_NAME,
]


def _find_icon():
    for p in ICON_CANDIDATES:
        if p.exists() and p.is_file():
            return p

    try:
        for root in [
            Path("/home/pinball"),
            Path("/opt/pincabos/web/static"),
            Path("/opt/pincabos"),
        ]:
            if not root.exists():
                continue
            found = list(root.rglob(ICON_NAME))
            for p in found:
                if p.exists() and p.is_file():
                    return p
    except Exception:
        pass

    return None


def _icon_route():
    icon = _find_icon()
    if not icon:
        abort(404)

    return send_file(
        str(icon),
        mimetype="image/png",
        conditional=True,
        max_age=3600,
    )


def _is_full_pincabos_row(row):
    low = row.lower()
    if ".pincabos.part" in low:
        return False
    return ".pincabos" in low


def _icon_html():
    return (
        '<img class="pcx-pincabos-package-icon" '
        'src="/tools/commander/pincabos-package-icon?v=1" '
        'alt="PinCabOS" title="Package PinCabOS" '
        'style="width:20px;height:20px;object-fit:contain;vertical-align:-5px;'
        'margin-right:7px;border-radius:4px;filter:drop-shadow(0 0 5px rgba(255,176,0,.55));">'
    )


def _transform_row(row):
    if not _is_full_pincabos_row(row):
        return row

    icon = _icon_html()

    # Cas normal: PinCab Explorer utilise une icône fichier texte.
    if "📄" in row:
        return row.replace("📄", icon, 1)

    # Fallback si l’icône change: injecte le logo au début de la première cellule.
    return re.sub(
        r"(<td\b[^>]*>\s*)",
        r"\1" + icon,
        row,
        count=1,
        flags=re.I,
    )


def _transform_commander_html(body):
    css = """
<style id="pco-pincabos-package-icon-css">
.pcx-page .pcx-pincabos-package-icon {
  display:inline-block !important;
  width:20px !important;
  height:20px !important;
  object-fit:contain !important;
  vertical-align:-5px !important;
  margin-right:7px !important;
  border-radius:4px !important;
}
</style>
"""

    if "pco-pincabos-package-icon-css" not in body:
        body = body.replace("</head>", css + "\n</head>", 1)

    return re.sub(
        r"<tr\b[^>]*>.*?</tr>",
        lambda m: _transform_row(m.group(0)),
        body,
        flags=re.I | re.S,
    )


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

    if getattr(original, "_pco_pincabos_package_icon_wrapped", False):
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

    wrapped._pco_pincabos_package_icon_wrapped = True
    app.view_functions[endpoint] = wrapped
    return "wrapped"


def register(app):
    if "pincabos_package_icon_png_v1" not in app.view_functions:
        app.add_url_rule(
            "/tools/commander/pincabos-package-icon",
            endpoint="pincabos_package_icon_png_v1",
            view_func=_icon_route,
            methods=["GET"],
        )

    mode = _wrap_commander_view(app)
    icon = _find_icon()
    print(f"GO: PinCabOS PackageIcon module loaded commander={mode} icon={icon or 'missing'}")
