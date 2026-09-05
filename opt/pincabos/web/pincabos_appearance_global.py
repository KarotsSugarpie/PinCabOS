"""
PINCABOS_APPEARANCE_GLOBAL_INJECTOR_V2

Garantit que les variables Apparence et la meme couche visuelle commune sont
chargees sur chaque reponse HTML, y compris les pages specialisees qui ne
passent pas par le gabarit standard.
"""

from __future__ import annotations

import re

from flask import request


_MARKER = "data-pincabos-interface-unified"
_VARS_PATH = "/static/pincabos-appearance-vars.css?v=appearance-global-v2"
_THEME_PATH = "/static/pincabos-theme-global.css?v=appearance-global-v2"
_BRIDGE_PATH = "/static/pincabos-appearance-dashboard-menu-v2.css?v=appearance-global-v2"
_UNIFIED_PATH = "/static/pincabos-interface-unified-v1.css?v=appearance-global-v2"


def install_appearance_global(app):
    if app.extensions.get("pincabos_appearance_global_v2"):
        return

    app.extensions["pincabos_appearance_global_v2"] = True

    @app.after_request
    def pincabos_appearance_global_after_request(response):
        try:
            # Le fichier genere doit toujours etre relu apres une application
            # de theme, meme si son URL demeure la meme.
            if request.path == "/static/pincabos-appearance-vars.css":
                response.headers["Cache-Control"] = (
                    "no-store, no-cache, max-age=0, must-revalidate"
                )
                response.headers["Pragma"] = "no-cache"
                return response

            content_type = (response.headers.get("Content-Type") or "").lower()
            if "text/html" not in content_type or response.direct_passthrough:
                return response

            html = response.get_data(as_text=True)

            if _MARKER in html:
                return response

            links = []

            # 1) Apparence reste la source de verite. Les pages qui ne
            # chargent pas encore les variables les recoivent ici.
            if "pincabos-appearance-vars.css" not in html:
                links.append(
                    f'<link rel="stylesheet" href="{_VARS_PATH}" '
                    'data-pincabos-appearance-vars-global="v2">'
                )

            # 2) Le theme historique commun couvre les primitives PinCabOS
            # deja normalisees. Il est injecte aussi sur les pages specialisees.
            if "pincabos-theme-global.css" not in html:
                links.append(
                    f'<link rel="stylesheet" href="{_THEME_PATH}" '
                    'data-pincabos-theme-global="v2">'
                )

            # 3) Le bridge conserve les compatibilites Dashboard/Menu et les
            # protections full-width existantes.
            if "pincabos-appearance-dashboard-menu-v2.css" not in html:
                links.append(
                    f'<link rel="stylesheet" href="{_BRIDGE_PATH}" '
                    'data-pincabos-appearance-global-bridge="v2">'
                )

            # 4) La couche unifiee est TOUJOURS la derniere feuille chargee.
            # Elle ne change pas les grilles/positions/densites : elle convertit
            # le chrome visuel des modules vers les variables Apparence.
            if "pincabos-interface-unified-v1.css" not in html:
                links.append(
                    f'<link rel="stylesheet" href="{_UNIFIED_PATH}" '
                    f'{_MARKER}="v1">'
                )

            if not links:
                return response

            injection = "\n" + "\n".join(links) + "\n"

            # Injection a la fin du document, comme le bridge historique, afin
            # de passer apres les <style> locaux et les CSS propres aux modules.
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
            # Une page ne doit jamais etre bloquee par la couche visuelle.
            pass

        return response
