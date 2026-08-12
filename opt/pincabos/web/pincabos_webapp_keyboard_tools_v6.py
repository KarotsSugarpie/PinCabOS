"""PinCabOS: injects the keyboard tile only on the existing /tools page."""
from __future__ import annotations

from flask import request

MARKER = 'PCO-KEYBOARD-TOOLS-V6'
SCRIPT_TAG = '<script defer src="/static/pincabos-keyboard-tools-v6.js"></script>'


def register_keyboard_tools_v6(app):
    if getattr(app, '_pco_keyboard_tools_v6', False):
        return

    @app.after_request
    def pco_keyboard_tools_v6_after_request(response):
        try:
            content_type = (response.headers.get('Content-Type') or '').lower()
            if request.method != 'GET' or request.path != '/tools':
                return response
            if response.status_code != 200 or 'text/html' not in content_type:
                return response
            body = response.get_data(as_text=True)
            if MARKER in body or '/static/pincabos-keyboard-tools-v6.js' in body:
                return response
            if '</body>' not in body:
                return response
            body = body.replace('</body>', f'<!-- {MARKER} -->\n{SCRIPT_TAG}\n</body>', 1)
            response.set_data(body)
        except Exception:
            # Never break the existing tools page if its markup changes later.
            return response
        return response

    setattr(app, '_pco_keyboard_tools_v6', True)
