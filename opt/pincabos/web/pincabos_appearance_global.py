"""
PINCABOS_APPEARANCE_GLOBAL_INJECTOR_V2

Garantit que les variables Apparence et la meme couche visuelle commune sont
chargees sur chaque reponse HTML, y compris les pages specialisees qui ne
passent pas par le gabarit standard.

DudesCab reste volontairement une exception visuelle : son identite propre est
preservee, avec une feuille finale sombre/opaque chargee apres le theme global.
"""

from __future__ import annotations

import re

from flask import request


_MARKER = "data-pincabos-interface-unified"
_VARS_PATH = "/static/pincabos-appearance-vars.css?v=appearance-global-v2"
_THEME_PATH = "/static/pincabos-theme-global.css?v=appearance-global-v2"
_BRIDGE_PATH = "/static/pincabos-appearance-dashboard-menu-v2.css?v=appearance-global-v2"
_UNIFIED_PATH = "/static/pincabos-interface-unified-v1.css?v=appearance-global-v2"
_MODULES_PATH = "/static/pincabos-interface-unified-modules-v1.css?v=appearance-global-v2"
_DUDESCAB_PATH = "/static/pincabos-dudescab-dark-exception-v1.css?v=appearance-global-v2"
_BACKGROUND_PATH = "/static/pincabos-background-rotator-v1.js?v=background-rotator-v1"


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
            if "text/html" not in content_type:
                return response

            # Les reponses HTML envoyees via send_file peuvent etre en mode
            # direct_passthrough. On les rend lisibles ici uniquement si elles
            # ne sont pas des pieces jointes a telecharger.
            disposition = (response.headers.get("Content-Disposition") or "").lower()
            if response.direct_passthrough:
                if "attachment" in disposition:
                    return response
                response.direct_passthrough = False

            html = response.get_data(as_text=True)
            assets = []

            # 1) Apparence reste la source de verite. Les pages qui ne
            # chargent pas encore les variables les recoivent ici.
            if "pincabos-appearance-vars.css" not in html:
                assets.append(
                    f'<link rel="stylesheet" href="{_VARS_PATH}" '
                    'data-pincabos-appearance-vars-global="v2">'
                )

            # 2) Theme historique commun pour les primitives PinCabOS.
            if "pincabos-theme-global.css" not in html:
                assets.append(
                    f'<link rel="stylesheet" href="{_THEME_PATH}" '
                    'data-pincabos-theme-global="v2">'
                )

            # 3) Compatibilite Dashboard/Menu.
            if "pincabos-appearance-dashboard-menu-v2.css" not in html:
                assets.append(
                    f'<link rel="stylesheet" href="{_BRIDGE_PATH}" '
                    'data-pincabos-appearance-global-bridge="v2">'
                )

            # 4) Couche commune de toute la WebApp. Elle reste visuelle
            # seulement : aucune grille, position, largeur ou logique modifiee.
            if "pincabos-interface-unified-v1.css" not in html:
                assets.append(
                    f'<link rel="stylesheet" href="{_UNIFIED_PATH}" '
                    f'{_MARKER}="v1">'
                )

            # 5) Pont des modules specialises historiques (Lobby, Audio,
            # Explorer, Smart Import, FullDMD, DOF, Services, notifications,
            # Batch). Meme Apparence, layouts originaux conserves.
            if "pincabos-interface-unified-modules-v1.css" not in html:
                assets.append(
                    f'<link rel="stylesheet" href="{_MODULES_PATH}" '
                    'data-pincabos-interface-unified-modules="v1">'
                )

            # 6) DudesCab est une exception demandee : pas d'unification de son
            # identite. Cette feuille finale garde son UI propre mais remplace
            # les grandes surfaces roses/translucides par des fonds opaques et
            # tres sombres. Les selecteurs sont limites a .dc-app.
            if "pincabos-dudescab-dark-exception-v1.css" not in html:
                assets.append(
                    f'<link rel="stylesheet" href="{_DUDESCAB_PATH}" '
                    'data-pincabos-dudescab-dark-exception="v1">'
                )

            # 7) Background aleatoire global de la WebApp. Le script verifie
            # les assets avant de les appliquer et conserve le fond historique
            # lorsqu'aucun background n'est disponible.
            if "pincabos-background-rotator-v1.js" not in html:
                assets.append(
                    f'<script src="{_BACKGROUND_PATH}" '
                    'data-pincabos-background-rotator="v1"></script>'
                )

            if not assets:
                return response

            injection = "\n" + "\n".join(assets) + "\n"

            # Injection a la fin du document afin de passer apres les <style>
            # locaux et CSS propres aux modules.
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
