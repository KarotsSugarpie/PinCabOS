"""
PinCabOS — cache navigateur sécuritaire.

Seuls les fichiers statiques sont mis en cache.
Les API, scripts VBS, tables et données dynamiques restent non cachés.
"""

from flask import Flask, request


STATIC_EXTENSIONS = (
    ".css",
    ".js",
    ".mjs",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".webp",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".map",
)

CACHE_HEADER = (
    "public, max-age=3600, stale-while-revalidate=86400"
)


def install_patch():
    if getattr(Flask, "_pincabos_browser_cache_v1", False):
        return

    original_process_response = Flask.process_response

    def pincabos_process_response(self, response):
        response = original_process_response(self, response)

        try:
            path = request.path.lower()

            is_static = (
                request.method in ("GET", "HEAD")
                and response.status_code in (
                    200,
                    203,
                    206,
                    304,
                )
                and path.endswith(STATIC_EXTENSIONS)
            )

            if is_static:
                response.headers["Cache-Control"] = CACHE_HEADER
                response.headers[
                    "X-PinCabOS-Cache"
                ] = "static-browser-cache-v1"

        except RuntimeError:
            # Aucun contexte HTTP actif.
            pass

        return response

    Flask.process_response = pincabos_process_response
    Flask._pincabos_browser_cache_v1 = True


install_patch()
