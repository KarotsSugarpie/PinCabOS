"""
PinCabOS — limites de requêtes V2.

- Importation de fichiers : jusqu'à 8 Gio.
- Champs texte comme les scripts VBS : jusqu'à 64 Mio.
- Waitress : jusqu'à 8 Gio.
"""

from __future__ import annotations

TOTAL_REQUEST_BYTES = 8589934592
FORM_FIELD_BYTES = 67108864
FORM_PARTS = 10000
UPLOAD_TIMEOUT_SECONDS = 7200


def patch_flask() -> None:
    from flask import Flask
    from flask import Request as FlaskRequest

    if getattr(Flask, "_pincabos_limits_8g_v2", False):
        return

    class PinCabOSRequest(FlaskRequest):
        """
        Requête PinCabOS.

        La taille totale autorise les gros fichiers.
        La limite mémoire des champs texte reste raisonnable.
        """

        max_content_length = TOTAL_REQUEST_BYTES
        max_form_memory_size = FORM_FIELD_BYTES
        max_form_parts = FORM_PARTS

    original_init = Flask.__init__

    def pincabos_flask_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)

        self.request_class = PinCabOSRequest

        self.config["MAX_CONTENT_LENGTH"] = (
            TOTAL_REQUEST_BYTES
        )

        self.config["MAX_FORM_MEMORY_SIZE"] = (
            FORM_FIELD_BYTES
        )

        self.config["MAX_FORM_PARTS"] = FORM_PARTS

    Flask.__init__ = pincabos_flask_init
    Flask.request_class = PinCabOSRequest
    Flask._pincabos_limits_8g_v2 = True


def patch_waitress() -> None:
    try:
        import waitress
        from waitress.adjustments import Adjustments
    except Exception:
        return

    Adjustments.max_request_body_size = (
        TOTAL_REQUEST_BYTES
    )

    Adjustments.channel_timeout = (
        UPLOAD_TIMEOUT_SECONDS
    )

    if getattr(
        waitress,
        "_pincabos_limits_8g_v2",
        False,
    ):
        return

    original_serve = waitress.serve

    def pincabos_serve(app, **kwargs):
        current_size = kwargs.get(
            "max_request_body_size",
            0,
        )

        try:
            current_size = int(current_size)
        except (TypeError, ValueError):
            current_size = 0

        if current_size < TOTAL_REQUEST_BYTES:
            kwargs["max_request_body_size"] = (
                TOTAL_REQUEST_BYTES
            )

        current_timeout = kwargs.get(
            "channel_timeout",
            0,
        )

        try:
            current_timeout = int(current_timeout)
        except (TypeError, ValueError):
            current_timeout = 0

        if current_timeout < UPLOAD_TIMEOUT_SECONDS:
            kwargs["channel_timeout"] = (
                UPLOAD_TIMEOUT_SECONDS
            )

        return original_serve(app, **kwargs)

    waitress.serve = pincabos_serve
    waitress._pincabos_limits_8g_v2 = True


patch_flask()
patch_waitress()
