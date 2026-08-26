#!/usr/bin/env bash
set -Eeuo pipefail

clear

EXPECTED_HOST="pincabos"
EXPECTED_IP="192.168.254.237"

APP_DIR="/opt/pincabos/web"
APP_FILE="$APP_DIR/app.py"
MODULE_FILE="$APP_DIR/pincaboslink.py"
SERVICE="pincabos-webapp.service"

HELPER="/usr/local/sbin/pincabos-link-web-pair"
SUDOERS="/etc/sudoers.d/pincabos-link-web-pair"
STATE="/var/lib/pincabos-link/device.json"

HEARTBEAT_CLIENT="/opt/pincabos/bin/pincabos-link-heartbeat"
HEARTBEAT_SERVICE="/etc/systemd/system/pincabos-link-heartbeat.service"
HEARTBEAT_TIMER="/etc/systemd/system/pincabos-link-heartbeat.timer"

STAMP="$(date -u +%Y%m%d-%H%M%S)"
BACKUP="/opt/pincabos/backups/pincabos-link-native-shell-$STAMP"
ROLLBACK="$BACKUP/ROLLBACK_PINCABOS_LINK_NATIVE_SHELL.sh"
STAGE="$(mktemp -d /tmp/pincabos-link-native-shell.XXXXXX)"

DEPLOYED=0

fail() {
    echo
    echo "==============================================================="
    echo " NOGO [ERREUR] $1"
    echo "==============================================================="
    exit 1
}

cleanup() {
    rm -rf "$STAGE"
}

on_error() {
    local rc="$1"
    local line="$2"

    trap - ERR

    echo
    echo "==============================================================="
    echo " NOGO [ERREUR] ECHEC A LA LIGNE $line"
    echo " CODE RETOUR : $rc"
    echo "==============================================================="

    if [[ "$DEPLOYED" -eq 1 && -x "$ROLLBACK" ]]; then
        echo "Rollback automatique..."
        "$ROLLBACK" || true
    fi

    cleanup
    exit "$rc"
}

trap 'rc=$?; on_error "$rc" "$LINENO"' ERR
trap cleanup EXIT

echo "==============================================================="
echo " PINFORGE-SAFE-1A1-447"
echo " PINCABOS LINK - INTERFACE NATIVE WEBAPP"
echo " MEME HEADER + MENU + ACCES RAPIDES + FOOTER"
echo " CARTE JOINDRE CONSERVEE"
echo "==============================================================="

echo
echo "=== 1. GARDES CABINET ==="

[[ "$(id -u)" -eq 0 ]] || fail "Executer avec sudo."

HOST_NOW="$(hostname | tr '[:upper:]' '[:lower:]')"

[[ "$HOST_NOW" == "$EXPECTED_HOST" ]] || \
    fail "Cabinet inattendu : $HOST_NOW"

hostname -I |
    tr ' ' '\n' |
    grep -Fxq "$EXPECTED_IP" || \
    fail "IP cabinet $EXPECTED_IP absente."

[[ -f "$APP_FILE" ]] || fail "app.py absent."
[[ -f "$MODULE_FILE" ]] || fail "pincaboslink.py absent."
[[ -x "$HELPER" ]] || fail "Helper Web pairing absent."
[[ -f "$SUDOERS" ]] || fail "Sudoers Web pairing absent."

systemctl is-active --quiet "$SERVICE" || \
    fail "WebApp inactive."

echo "GO [OK] Cabinet et WebApp confirmes."

echo
echo "=== 2. VALIDATION DU SHELL NATIF DISPONIBLE ==="

python3 - "$APP_FILE" "$MODULE_FILE" <<'PY'
import ast
import sys
from pathlib import Path

app = Path(sys.argv[1]).read_text(
    encoding="utf-8",
    errors="replace",
)

module = Path(sys.argv[2]).read_text(
    encoding="utf-8",
    errors="replace",
)

ast.parse(app)
ast.parse(module)

required_app = (
    "def page(",
    "pincabos_support_footer_html()",
    'href="/tools"',
    'href="/about"',
    'href="/pincabos-link"',
    "register_pincaboslink(app)",
)

for marker in required_app:
    if marker not in app:
        raise SystemExit(
            "NOGO [ERREUR] Marqueur shell absent : "
            + marker
        )

if "PINCABOS_LINK_UI_V2_JOIN_CARD" not in module:
    raise SystemExit(
        "NOGO [ERREUR] Le module 446 attendu n'est pas actif."
    )

print("GO [OK] Renderer page() present.")
print("GO [OK] Footer officiel present.")
print("GO [OK] Menu WebApp incluant PinCabOS Link present.")
print("GO [OK] Module 446 confirme.")
PY

echo
echo "=== 3. BACKUP + PREUVES INCHANGEES ==="

install -d -m 2755 -o root -g pinball "$BACKUP"

cp -a "$APP_FILE" "$BACKUP/app.py.before"
cp -a "$MODULE_FILE" "$BACKUP/pincaboslink.py.before"

sha256sum \
    "$HELPER" \
    "$SUDOERS" \
    "$HEARTBEAT_CLIENT" \
    "$HEARTBEAT_SERVICE" \
    "$HEARTBEAT_TIMER" > "$BACKUP/infrastructure-before.sha256"

if [[ -f "$STATE" ]]; then
    sha256sum "$STATE" > "$BACKUP/device-state-before.sha256"
else
    touch "$BACKUP/device-state-was-absent"
fi

cat > "$ROLLBACK" <<ROLLBACK
#!/usr/bin/env bash
set -Eeuo pipefail

clear

cp -a "$BACKUP/app.py.before" "$APP_FILE"
cp -a "$BACKUP/pincaboslink.py.before" "$MODULE_FILE"

python3 -m py_compile "$APP_FILE" "$MODULE_FILE"

systemctl restart "$SERVICE"

for attempt in {1..40}; do
    if systemctl is-active --quiet "$SERVICE" &&
       curl -fsS --max-time 3 \
           http://127.0.0.1/pincabos-link >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

systemctl is-active --quiet "$SERVICE"

echo "GO [OK] Rollback PinCabOS Link Native Shell termine."
ROLLBACK

chmod 0750 "$ROLLBACK"

echo "Backup  : $BACKUP"
echo "Rollback: $ROLLBACK"
echo "GO [OK] Backup cree."

echo
echo "=== 4. STAGING NOUVEAU MODULE ==="

cat > "$STAGE/pincaboslink.py" <<'PYMODULE'
#!/usr/bin/env python3
"""PinCabOS Link integrated in the native PinCabOS WebApp shell."""

from __future__ import annotations

import hmac
import html
import re
import secrets
import shutil
import subprocess
from typing import Callable, Optional

from flask import Response, Blueprint, make_response, request


PINFORGE_MODULE = "PINCABOS_LINK_UI_V3_NATIVE_SHELL"
HEARTBEAT_TIMER = "pincabos-link-heartbeat.timer"
PAIR_HELPER = "/usr/local/sbin/pincabos-link-web-pair"
PAIR_PATTERN = re.compile(r"^[23456789ABCDEFGHJKLMNPQRSTUVWXYZ]{12}$")
CSRF_TOKEN = secrets.token_urlsafe(32)

pincaboslink_blueprint = Blueprint("pincaboslink_v1", __name__)
_page_renderer: Optional[Callable[[str, str], str]] = None


def _systemctl(action: str) -> str:
    executable = shutil.which("systemctl")
    if not executable:
        return "indisponible"

    try:
        result = subprocess.run(
            [executable, action, HEARTBEAT_TIMER],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return "indisponible"

    values = result.stdout.strip().splitlines()
    return values[0][:40] if values else "indisponible"


def _normalize_pairing_code(value: str) -> str:
    return "".join(
        character
        for character in str(value or "").upper()
        if character not in " -\t\r\n"
    )


def _join_cabinet(code: str) -> tuple[bool, str]:
    sudo = shutil.which("sudo")
    if not sudo:
        return False, "sudo est indisponible sur ce PinCab."

    try:
        result = subprocess.run(
            [sudo, "-n", PAIR_HELPER, code],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=45,
        )
    except subprocess.TimeoutExpired:
        return False, "La liaison a expire. Verifiez Internet et reessayez."
    except OSError:
        return False, "Impossible de lancer le service de liaison."

    status = result.stdout.strip().splitlines()
    marker = status[-1].strip() if status else "PAIR_FAILED"

    if result.returncode == 0 and marker == "PAIR_OK":
        return True, "PinCab associe avec succes a pincabos.cc."

    messages = {
        "PAIR_INVALID": "Le numero de liaison est invalide.",
        "PAIR_NETWORK": "Impossible de joindre pincabos.cc. Verifiez Internet.",
        "PAIR_REJECTED": "Numero refuse, expire ou deja utilise. Generez une nouvelle cle.",
        "PAIR_FAILED": "La liaison a echoue. Generez une nouvelle cle et reessayez.",
    }

    return False, messages.get(
        marker,
        "La liaison a echoue. Generez une nouvelle cle et reessayez.",
    )


def _body_html(
    active: str,
    enabled: str,
    state_class: str,
    state_text: str,
    message: str,
    message_class: str,
) -> str:
    message_html = ""

    if message:
        message_html = (
            '<div class="pco-link-message '
            + html.escape(message_class)
            + '">'
            + html.escape(message)
            + "</div>"
        )

    body = r"""
<style>
/* PINCABOS_LINK_NATIVE_SHELL_V1 */
.pco-link-native {
    width: 100%;
    margin: 0 auto;
}

.pco-link-native .pco-link-heading {
    margin-bottom: 18px;
}

.pco-link-native .pco-link-heading h1 {
    margin-bottom: 6px;
}

.pco-link-native .pco-link-heading p {
    margin: 0;
    opacity: .78;
}

.pco-link-native .pco-link-main-card {
    border-color: var(--pco-appearance-accent2, #ff7a00);
}

.pco-link-native .pco-link-form {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 12px;
    align-items: center;
    margin-top: 16px;
}

.pco-link-native .pco-link-input {
    width: 100%;
    min-height: 46px;
    padding: 10px 14px;
    border: 1px solid rgba(255, 122, 0, .85);
    border-radius: 10px;
    background: rgba(5, 5, 12, .92);
    color: #fff;
    font: 700 1rem/1.2 ui-monospace, SFMono-Regular, Consolas, monospace;
    letter-spacing: .08em;
    text-transform: uppercase;
    outline: none;
    box-shadow: inset 0 0 0 1px rgba(255, 122, 0, .10);
}

.pco-link-native .pco-link-input:focus {
    border-color: #ff9b45;
    box-shadow:
        0 0 0 2px rgba(255, 122, 0, .18),
        inset 0 0 0 1px rgba(255, 122, 0, .12);
}

.pco-link-native .pco-link-join {
    min-height: 46px;
    padding: 0 24px;
    white-space: nowrap;
    font-weight: 900;
}

.pco-link-native .pco-link-hint {
    margin-top: 10px;
    opacity: .72;
    font-size: .92rem;
}

.pco-link-native .pco-link-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 16px;
    margin-top: 16px;
}

.pco-link-native .pco-link-status {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    margin: 4px 0 14px;
    padding: 7px 11px;
    border-radius: 999px;
    font-weight: 800;
}

.pco-link-native .pco-link-status.ok {
    color: #c8ffdc;
    background: rgba(18, 57, 34, .92);
}

.pco-link-native .pco-link-status.warn {
    color: #fff0bd;
    background: rgba(74, 53, 16, .92);
}

.pco-link-native .pco-link-dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    background: currentColor;
}

.pco-link-native .pco-link-kv {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 9px 18px;
    margin: 0;
}

.pco-link-native .pco-link-kv dt {
    opacity: .72;
}

.pco-link-native .pco-link-kv dd {
    margin: 0;
    font-weight: 750;
}

.pco-link-native .pco-link-message {
    margin-top: 14px;
    padding: 12px 14px;
    border-radius: 10px;
    font-weight: 750;
}

.pco-link-native .pco-link-message.success {
    color: #cbffdb;
    background: rgba(18, 57, 34, .88);
    border: 1px solid #28643b;
}

.pco-link-native .pco-link-message.error {
    color: #ffd0d0;
    background: rgba(66, 26, 26, .90);
    border: 1px solid #743030;
}

.pco-link-native .pco-link-security {
    line-height: 1.55;
}

@media (max-width: 800px) {
    .pco-link-native .pco-link-form,
    .pco-link-native .pco-link-grid {
        grid-template-columns: 1fr;
    }

    .pco-link-native .pco-link-join {
        width: 100%;
    }
}
</style>

<section class="pco-link-native" data-marker="PINCABOS_LINK_NATIVE_SHELL_V1">
    <div class="pco-link-heading">
        <h1>PinCabOS Link</h1>
        <p>
            Liez ce cabinet a votre compte pincabos.cc directement
            depuis la WebApp PinCabOS.
        </p>
    </div>

    <div class="card pco-link-main-card">
        <h2>Joindre ce PinCab a pincabos.cc</h2>
        <p>
            Generez une cle de liaison dans
            <strong>Mon compte</strong> sur pincabos.cc,
            entrez-la ici puis cliquez sur <strong>JOINDRE</strong>.
        </p>

        <form
            class="pco-link-form"
            method="post"
            action="/pincabos-link"
            autocomplete="off"
        >
            <input
                type="hidden"
                name="csrf_token"
                value="__CSRF__"
            >

            <input
                class="pco-link-input"
                type="text"
                name="pairing_code"
                maxlength="24"
                required
                spellcheck="false"
                autocapitalize="characters"
                placeholder="XXXX-XXXX-XXXX"
                aria-label="Numero de liaison"
            >

            <button
                class="button pco-link-join"
                type="submit"
            >
                JOINDRE
            </button>
        </form>

        __MESSAGE__

        <p class="pco-link-hint">
            Les tirets et les espaces sont acceptes.
            La cle est a usage unique et n'est jamais conservee
            par cette page.
        </p>
    </div>

    <div class="pco-link-grid">
        <div class="card">
            <h2>Presence du cabinet</h2>

            <div class="pco-link-status __STATE_CLASS__">
                <span class="pco-link-dot"></span>
                __STATE_TEXT__
            </div>

            <dl class="pco-link-kv">
                <dt>Timer heartbeat</dt>
                <dd>__ACTIVE__</dd>

                <dt>Demarrage auto</dt>
                <dd>__ENABLED__</dd>

                <dt>Frequence</dt>
                <dd>60 secondes</dd>

                <dt>Hors ligne apres</dt>
                <dd>180 secondes</dd>
            </dl>
        </div>

        <div class="card">
            <h2>Securite</h2>

            <p class="pco-link-security">
                <strong>Le jeton appareil demeure protege.</strong><br>
                La WebApp ne lit et n'affiche jamais le jeton.
                Si une ancienne liaison locale existe, elle est conservee
                tant que la nouvelle liaison n'a pas reussi.
            </p>
        </div>
    </div>
</section>
"""

    return (
        body.replace("__CSRF__", html.escape(CSRF_TOKEN, quote=True))
        .replace("__MESSAGE__", message_html)
        .replace("__STATE_CLASS__", html.escape(state_class))
        .replace("__STATE_TEXT__", html.escape(state_text))
        .replace("__ACTIVE__", html.escape(active))
        .replace("__ENABLED__", html.escape(enabled))
    )


@pincaboslink_blueprint.route(
    "/pincabos-link",
    methods=["GET", "POST"],
)
def pincaboslink_page() -> Response:
    if _page_renderer is None:
        return Response(
            "PinCabOS WebApp renderer unavailable.",
            status=500,
            content_type="text/plain; charset=utf-8",
        )

    active = _systemctl("is-active")
    enabled = _systemctl("is-enabled")

    healthy = active == "active" and enabled == "enabled"
    state_class = "ok" if healthy else "warn"
    state_text = "Liaison active" if healthy else "Liaison a verifier"

    message = ""
    message_class = ""

    if request.method == "POST":
        submitted_csrf = str(request.form.get("csrf_token") or "")

        if not hmac.compare_digest(submitted_csrf, CSRF_TOKEN):
            message = "Requete refusee. Rechargez la page et reessayez."
            message_class = "error"
        else:
            code = _normalize_pairing_code(
                request.form.get("pairing_code") or ""
            )

            if not PAIR_PATTERN.fullmatch(code):
                message = (
                    "Format invalide. Entrez la cle de liaison "
                    "a 12 caracteres."
                )
                message_class = "error"
            else:
                success, message = _join_cabinet(code)
                message_class = "success" if success else "error"

    body = _body_html(
        active=active,
        enabled=enabled,
        state_class=state_class,
        state_text=state_text,
        message=message,
        message_class=message_class,
    )

    rendered = _page_renderer("PinCabOS Link", body)
    response = make_response(rendered)

    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"

    return response


def register_pincaboslink(
    app,
    page_renderer: Callable[[str, str], str],
) -> None:
    global _page_renderer

    _page_renderer = page_renderer

    if pincaboslink_blueprint.name not in app.blueprints:
        app.register_blueprint(pincaboslink_blueprint)

PYMODULE

python3 - "$STAGE/pincaboslink.py" <<'PY'
import ast
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")

ast.parse(text, filename=str(path))

required = (
    "PINCABOS_LINK_UI_V3_NATIVE_SHELL",
    "PINCABOS_LINK_NATIVE_SHELL_V1",
    "_page_renderer",
    'methods=["GET", "POST"]',
    'name="pairing_code"',
    ">JOINDRE<",
)

for marker in required:
    if marker not in text:
        raise SystemExit(
            "NOGO [ERREUR] Marqueur module absent : "
            + marker
        )

print("GO [OK] Module V3 Native Shell valide.")
PY

echo
echo "=== 5. STAGING APP.PY ==="

python3 - "$APP_FILE" "$STAGE/app.py" <<'PY'
import ast
import sys
from pathlib import Path

source = Path(sys.argv[1])
target = Path(sys.argv[2])

text = source.read_text(
    encoding="utf-8",
    errors="replace",
)

old_register = "register_pincaboslink(app)"
new_register = "register_pincaboslink(app, page)"

if text.count(old_register) != 1:
    raise SystemExit(
        "NOGO [ERREUR] Appel register_pincaboslink(app) inattendu : "
        + str(text.count(old_register))
    )

text = text.replace(
    old_register,
    new_register,
    1,
)

old_button = (
    '<a href="/pincabos-link" class="secondary">'
    '<span class="menu-ico">&#128279;</span> PinCabOS Link</a>'
)

new_button = (
    '<a href="/pincabos-link" '
    'class="{ \\'active\\' if title == \\'PinCabOS Link\\' else \\'secondary\\' }">'
    '<span class="menu-ico">&#128279;</span> PinCabOS Link</a>'
)

if old_button in text:
    text = text.replace(
        old_button,
        new_button,
        1,
    )
elif new_button not in text:
    raise SystemExit(
        "NOGO [ERREUR] Bouton menu PinCabOS Link inattendu."
    )

ast.parse(text, filename=str(target))

if text.count(new_register) != 1:
    raise SystemExit(
        "NOGO [ERREUR] Enregistrement V3 non unique."
    )

if text.count('href="/pincabos-link"') != 1:
    raise SystemExit(
        "NOGO [ERREUR] Bouton PinCabOS Link non unique."
    )

target.write_text(
    text,
    encoding="utf-8",
)

print("GO [OK] page() transmise au module.")
print("GO [OK] Bouton PinCabOS Link actif sur sa page.")
PY

echo
echo "=== 6. VALIDATION COMPLETE DU STAGING ==="

python3 - "$STAGE/app.py" "$STAGE/pincaboslink.py" <<'PY'
import ast
import sys
from pathlib import Path

for item in sys.argv[1:]:
    path = Path(item)
    ast.parse(
        path.read_text(encoding="utf-8"),
        filename=str(path),
    )

print("GO [OK] Sources Python staged valides.")
PY

echo
echo "=== 7. DEPLOIEMENT CIBLE ==="

DEPLOYED=1

install -o root -g root -m 0644 \
    "$STAGE/pincaboslink.py" \
    "$MODULE_FILE"

install -o root -g root -m 0644 \
    "$STAGE/app.py" \
    "$APP_FILE"

python3 -m py_compile "$APP_FILE" "$MODULE_FILE"

echo "GO [OK] App et module installes."

echo
echo "=== 8. REDEMARRAGE WEBAPP ==="

systemctl restart "$SERVICE"

READY=0

for attempt in {1..40}; do
    if systemctl is-active --quiet "$SERVICE" &&
       curl -fsS \
           --max-time 3 \
           -o "$BACKUP/pincabos-link-native.html" \
           http://127.0.0.1/pincabos-link; then
        READY=1
        break
    fi

    sleep 1
done

[[ "$READY" -eq 1 ]] || \
    fail "WebApp non disponible apres redemarrage."

echo "GO [OK] WebApp revenue."

echo
echo "=== 9. VALIDATION MEME HEADER / MENU / FOOTER ==="

python3 - "$BACKUP/pincabos-link-native.html" <<'PY'
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(
    encoding="utf-8",
    errors="replace",
)

required = (
    "PINCABOS_LINK_NATIVE_SHELL_V1",
    "PinCabOS Link",
    "JOINDRE",
    "Ouvrir VPinFE",
    "Ouvrir VPS",
    "PinCab Explorer",
    "PinCab Console",
    "PlayField",
    "BackGlass",
    "Soutenir PinCabOS",
    "Notes de version",
)

missing = [
    marker
    for marker in required
    if marker not in text
]

if missing:
    raise SystemExit(
        "NOGO [ERREUR] Elements du shell WebApp absents : "
        + ", ".join(missing)
    )

if (
    "Accès rapides" not in text
    and "Acces rapides" not in text
):
    raise SystemExit(
        "NOGO [ERREUR] Acces rapides absent."
    )

print("GO [OK] Header WebApp present.")
print("GO [OK] Menu principal WebApp present.")
print("GO [OK] Acces rapides presents.")
print("GO [OK] PlayField / BackGlass presents.")
print("GO [OK] Carte JOINDRE presente.")
print("GO [OK] Footer officiel PinCabOS present.")
PY

echo
echo "=== 10. VALIDATION BOUTON MENU ACTIF ==="

grep -Fq \
    "title == 'PinCabOS Link'" \
    "$APP_FILE" || \
    fail "Etat actif du bouton PinCabOS Link absent."

echo "GO [OK] PinCabOS Link devient actif dans le menu."

echo
echo "=== 11. PREUVE HELPER / HEARTBEAT / JETON INCHANGES ==="

(
    cd /
    sha256sum -c "$BACKUP/infrastructure-before.sha256"
)

if [[ -f "$BACKUP/device-state-before.sha256" ]]; then
    [[ -f "$STATE" ]] || \
        fail "Jeton local disparu."

    (
        cd /
        sha256sum -c "$BACKUP/device-state-before.sha256"
    )

    echo "GO [OK] Jeton local strictement inchange."
else
    [[ ! -f "$STATE" ]] || \
        fail "Un jeton est apparu sans clic utilisateur."

    echo "GO [OK] Aucun jeton cree."
fi

echo "GO [OK] Helper pairing inchange."
echo "GO [OK] Sudoers inchange."
echo "GO [OK] Heartbeat inchange."

echo
echo "=== 12. VALIDATION FINALE ==="

systemctl is-active --quiet "$SERVICE" || \
    fail "WebApp inactive."

systemctl is-active --quiet pincabos-link-heartbeat.timer || \
    fail "Heartbeat timer inactif."

systemctl is-enabled --quiet pincabos-link-heartbeat.timer || \
    fail "Heartbeat timer non enabled."

DEPLOYED=0
trap - ERR

echo
echo "==============================================================="
echo " GO [OK] PINCABOS LINK = INTERFACE NATIVE WEBAPP"
echo "==============================================================="
echo
echo " Maintenant /pincabos-link utilise exactement le meme :"
echo " - header / logo"
echo " - menu principal"
echo " - acces rapides"
echo " - boutons PlayField / BackGlass"
echo " - langue"
echo " - boutons Pin / X"
echo " - footer Soutenir PinCabOS"
echo " - footer Testeurs / Soutiens"
echo " - Notes de version"
echo
echo " La carte CLE + JOINDRE est conservee."
echo
echo " PAGE     : http://192.168.254.237/pincabos-link"
echo " Backup   : $BACKUP"
echo " Rollback : $ROLLBACK"
echo "==============================================================="
