"""
PINCABOS_APPEARANCE_GLOBAL_INJECTOR_V1

Garantit que le thème actif est chargé sur chaque réponse HTML,
même lorsqu'une page spécialisée ne passe pas par le gabarit standard.
"""

from __future__ import annotations

import re

from flask import request


_MARKER = "data-pincabos-appearance-global-bridge"
_VARS_PATH = "/static/pincabos-appearance-vars.css?v=appearance-global-v1"
_BRIDGE_PATH = "/static/pincabos-appearance-dashboard-menu-v2.css?v=fullwidth-v2"


def install_appearance_global(app):
    if app.extensions.get("pincabos_appearance_global_v1"):
        return

    app.extensions["pincabos_appearance_global_v1"] = True

    @app.after_request
    def pincabos_appearance_global_after_request(response):
        try:
            # Le fichier généré doit toujours être relu après une application
            # de thème, même si son URL demeure la même.
            if request.path == "/static/pincabos-appearance-vars.css":
                response.headers["Cache-Control"] = "no-store, no-cache, max-age=0, must-revalidate"
                response.headers["Pragma"] = "no-cache"
                return response

            content_type = (response.headers.get("Content-Type") or "").lower()
            if "text/html" not in content_type or response.direct_passthrough:
                return response

            html = response.get_data(as_text=True)

            if _MARKER in html:
                return response

            links = []

            # Les pages globales chargent déjà les variables. Les pages
            # spécialisées qui ne les chargent pas les reçoivent ici.
            if "pincabos-appearance-vars.css" not in html:
                links.append(
                    f'<link rel="stylesheet" href="{_VARS_PATH}" '
                    'data-pincabos-appearance-vars-global="v1">'
                )

            # Ce pont est volontairement placé en dernier, après les CSS
            # locaux des modules, afin de leur fournir les couleurs actives.
            links.append(
                f'<link rel="stylesheet" href="{_BRIDGE_PATH}" '
                f'{_MARKER}="v1">'
            )

            injection = "\n" + "\n".join(links) + "\n"

            if re.search(r"</body\s*>", html, flags=re.IGNORECASE):
                html = re.sub(
                    r"</body\s*>",
                    lambda match: injection + match.group(0),
                    html,
                    count=1,
                    flags=re.IGNORECASE,
                )
            elif re.search(r"</head\s*>", html, flags=re.IGNORECASE):
                html = re.sub(
                    r"</head\s*>",
                    lambda match: injection + match.group(0),
                    html,
                    count=1,
                    flags=re.IGNORECASE,
                )
            else:
                html += injection

            response.set_data(html)
            response.headers["Content-Length"] = str(len(response.get_data()))
            response.headers.pop("Content-Encoding", None)

        except Exception:
            # Une page ne doit jamais être bloquée par la couche visuelle.
            pass

        return response
