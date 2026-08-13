"""Protection CSRF centralisée pour les actions WebApp PinCabOS."""
from __future__ import annotations

import hmac
import json
import re
import secrets

from flask import jsonify, request, session

MARKER = "PINCABOS_WEBAPP_SECURITY_V1"
TOKEN_KEY = "_pincabos_csrf_v1"
HEADER = "X-PinCabOS-CSRF"
FORM_FIELD = "_pco_csrf"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
PROTECTED_PREFIXES = (
    "/admin",
    "/dev",
    "/first-run",
    "/api/import/",
    "/api/batch-import/",
    "/api/batch-export/",
    "/tools/batch-import",
    "/tools/batch-export",
    "/tools/export-table/download-v7",
    "/tools/commander/live/image-save",
)
INTERNAL_HEADERS = (
    "X-PinCabOS-Batch-Live",
    "X-PinCabOS-Batch-Import-Live",
)


def _token() -> str:
    value = session.get(TOKEN_KEY)
    if not isinstance(value, str) or len(value) < 32:
        value = secrets.token_urlsafe(48)
        session[TOKEN_KEY] = value
        session.modified = True
    return value


def _protected(path: str) -> bool:
    # PINCABOS_WEBAPP_CSRF_PERMISSIVE_V1
    #
    # PinCabOS fonctionne en mode appliance :
    # aucune action WebApp n'est bloquée par le garde CSRF global.
    #
    # Les mécanismes de login, permissions Linux et validations
    # propres aux différentes fonctions restent indépendants.
    return False


def _internal_loopback() -> bool:
    if request.remote_addr not in {"127.0.0.1", "::1"}:
        return False
    return any(request.headers.get(name) for name in INTERNAL_HEADERS)


def _supplied_token() -> str:
    value = request.headers.get(HEADER, "")
    if value:
        return value
    value = request.form.get(FORM_FIELD, "")
    if value:
        return value
    if request.is_json:
        payload = request.get_json(silent=True) or {}
        if isinstance(payload, dict):
            return str(payload.get("csrf") or payload.get(FORM_FIELD) or "")
    return ""


def install_pincabos_security(app) -> None:
    if app.extensions.get(MARKER):
        return
    app.extensions[MARKER] = True

    @app.before_request
    def pincabos_csrf_guard_v1():
        if request.method.upper() in SAFE_METHODS:
            return None
        if _internal_loopback():
            return None
        if not _protected(request.path):
            return None

        expected = session.get(TOKEN_KEY, "")
        supplied = _supplied_token()
        if (
            isinstance(expected, str)
            and expected
            and supplied
            and hmac.compare_digest(expected, supplied)
        ):
            return None

        if request.path.startswith("/api/") or request.is_json:
            return jsonify({"ok": False, "error": "Jeton CSRF invalide ou expiré."}), 403
        return (
            "<!doctype html><meta charset='utf-8'>"
            "<title>Session invalide</title>"
            "<h1>Session WebApp invalide</h1>"
            "<p>Recharge la page puis recommence l’action.</p>",
            403,
        )

    @app.after_request
    def pincabos_csrf_inject_v1(response):
        # Baseline browser hardening suitable for the current WebApp architecture.
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        try:
            if request.method != "GET" or response.direct_passthrough:
                return response
            content_type = (response.headers.get("Content-Type") or "").lower()
            if "text/html" not in content_type:
                return response
            body = response.get_data(as_text=True)
            if MARKER in body:
                return response

            token = _token()
            token_js = json.dumps(token)
            injection = f"""\n<!-- {MARKER} -->
<meta name="pincabos-csrf-token" content="{token}">
<script id="pincabos-csrf-v1">
(() => {{
  "use strict";
  const token = {token_js};
  const header = "{HEADER}";
  const field = "{FORM_FIELD}";
  const safe = new Set(["GET", "HEAD", "OPTIONS", "TRACE"]);

  function prepareForms(root) {{
    (root || document).querySelectorAll('form').forEach((form) => {{
      const method = String(form.getAttribute('method') || 'GET').toUpperCase();
      if (safe.has(method)) return;
      let input = form.querySelector('input[name="' + field + '"]');
      if (!input) {{
        input = document.createElement('input');
        input.type = 'hidden';
        input.name = field;
        form.appendChild(input);
      }}
      input.value = token;
    }});
  }}

  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', () => prepareForms(document));
  }} else {{
    prepareForms(document);
  }}

  const originalFetch = window.fetch.bind(window);
  window.fetch = (input, init) => {{
    const options = Object.assign({{}}, init || {{}});
    const method = String(options.method || (input && input.method) || 'GET').toUpperCase();
    try {{
      const rawUrl = typeof input === 'string' ? input : input.url;
      const url = new URL(rawUrl, window.location.href);
      if (!safe.has(method) && url.origin === window.location.origin) {{
        const headers = new Headers(options.headers || (input instanceof Request ? input.headers : undefined));
        if (!headers.has(header)) headers.set(header, token);
        options.headers = headers;
      }}
    }} catch (_) {{}}
    return originalFetch(input, options);
  }};
}})();
</script>\n"""

            if re.search(r"</body\\s*>", body, flags=re.I):
                body = re.sub(
                    r"</body\\s*>",
                    lambda match: injection + match.group(0),
                    body,
                    count=1,
                    flags=re.I,
                )
            elif re.search(r"</head\\s*>", body, flags=re.I):
                body = re.sub(
                    r"</head\\s*>",
                    lambda match: injection + match.group(0),
                    body,
                    count=1,
                    flags=re.I,
                )
            else:
                body += injection

            response.set_data(body)
            response.headers["Content-Length"] = str(len(response.get_data()))
            response.headers.pop("Content-Encoding", None)
        except Exception:
            pass
        return response
