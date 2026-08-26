#!/usr/bin/env bash
set -Eeuo pipefail

clear

EXPECTED_HOST="pincabos"
EXPECTED_IP="192.168.254.237"

APP_DIR="/opt/pincabos/web"
APP_FILE="$APP_DIR/app.py"
MODULE_FILE="$APP_DIR/pincaboslink.py"
SERVICE="pincabos-webapp.service"

CLIENT="/opt/pincabos/bin/pincabos-link"
COMMAND_LINK="/usr/local/bin/pincabos-link"
HELPER="/usr/local/sbin/pincabos-link-web-pair"
SUDOERS="/etc/sudoers.d/pincabos-link-web-pair"

STATE="/var/lib/pincabos-link/device.json"

HEARTBEAT_CLIENT="/opt/pincabos/bin/pincabos-link-heartbeat"
HEARTBEAT_SERVICE="/etc/systemd/system/pincabos-link-heartbeat.service"
HEARTBEAT_TIMER="/etc/systemd/system/pincabos-link-heartbeat.timer"

STAMP="$(date -u +%Y%m%d-%H%M%S)"
BACKUP="/opt/pincabos/backups/pincabos-link-join-card-$STAMP"
ROLLBACK="$BACKUP/ROLLBACK_PINCABOS_LINK_JOIN_CARD.sh"
STAGE="$(mktemp -d /tmp/pincabos-link-join-card.XXXXXX)"
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
        echo "Rollback automatique en cours..."
        "$ROLLBACK" || true
    fi

    cleanup
    exit "$rc"
}

trap 'rc=$?; on_error "$rc" "$LINENO"' ERR
trap cleanup EXIT

echo "==============================================================="
echo " PINFORGE-SAFE-1A1-446"
echo " PINCABOS LINK - CARTE JOINDRE A PINCABOS.CC"
echo " CLE + BOUTON JOINDRE DIRECTEMENT DANS LA WEBAPP"
echo " BACKUP + ROLLBACK + VALIDATION"
echo " AUCUN JETON AFFICHE"
echo "==============================================================="

echo
echo "=== 1. GARDES CABINET ==="

[[ "$(id -u)" -eq 0 ]] || fail "Executer avec sudo."

HOST_NOW="$(hostname | tr '[:upper:]' '[:lower:]')"
[[ "$HOST_NOW" == "$EXPECTED_HOST" ]] ||     fail "Cabinet inattendu : $HOST_NOW"

hostname -I | tr ' ' '\n' | grep -Fxq "$EXPECTED_IP" ||     fail "IP cabinet $EXPECTED_IP absente."

[[ -f "$APP_FILE" ]] || fail "app.py absent."
[[ -f "$MODULE_FILE" ]] || fail "pincaboslink.py absent."
[[ -x "$CLIENT" ]] || fail "Client pincabos-link absent."
[[ "$(readlink -f "$COMMAND_LINK")" == "$CLIENT" ]] ||     fail "Lien /usr/local/bin/pincabos-link inattendu."

[[ "$(systemctl is-active "$SERVICE")" == "active" ]] ||     fail "WebApp inactive."

[[ "$(systemctl is-active pincabos-link-heartbeat.timer)" == "active" ]] ||     fail "Heartbeat timer inactif."

echo "GO [OK] Cabinet, WebApp et client Link confirmes."

echo
echo "=== 2. VALIDATION MODULE ACTUEL ==="

python3 - "$APP_FILE" "$MODULE_FILE" <<'PY'
import ast
import sys
from pathlib import Path

app = Path(sys.argv[1]).read_text(encoding="utf-8")
module = Path(sys.argv[2]).read_text(encoding="utf-8")

ast.parse(app)
ast.parse(module)

if "register_pincaboslink(app)" not in app:
    raise SystemExit("NOGO [ERREUR] Module PinCabOS Link non enregistre.")

if "/pincabos-link" not in module:
    raise SystemExit("NOGO [ERREUR] Route /pincabos-link absente.")

print("GO [OK] Integration PinCabOS Link actuelle valide.")
PY

echo
echo "=== 3. BACKUP + PREUVE JETON/HEARTBEAT ==="

install -d -m 2755 -o root -g pinball "$BACKUP"

cp -a "$MODULE_FILE" "$BACKUP/pincaboslink.py.before"

if [[ -f "$HELPER" ]]; then
    cp -a "$HELPER" "$BACKUP/pincabos-link-web-pair.before"
else
    touch "$BACKUP/helper-was-absent"
fi

if [[ -f "$SUDOERS" ]]; then
    cp -a "$SUDOERS" "$BACKUP/pincabos-link-web-pair.sudoers.before"
else
    touch "$BACKUP/sudoers-was-absent"
fi

sha256sum     "$HEARTBEAT_CLIENT"     "$HEARTBEAT_SERVICE"     "$HEARTBEAT_TIMER" > "$BACKUP/heartbeat-before.sha256"

if [[ -f "$STATE" ]]; then
    sha256sum "$STATE" > "$BACKUP/device-state-before.sha256"
    stat -c '%U:%G:%a %n' "$STATE" > "$BACKUP/device-state-before.stat"
else
    touch "$BACKUP/device-state-was-absent"
fi

cat > "$ROLLBACK" <<ROLLBACK
#!/usr/bin/env bash
set -Eeuo pipefail

clear

cp -a "$BACKUP/pincaboslink.py.before" "$MODULE_FILE"

if [[ -f "$BACKUP/helper-was-absent" ]]; then
    rm -f "$HELPER"
else
    cp -a "$BACKUP/pincabos-link-web-pair.before" "$HELPER"
fi

if [[ -f "$BACKUP/sudoers-was-absent" ]]; then
    rm -f "$SUDOERS"
else
    cp -a "$BACKUP/pincabos-link-web-pair.sudoers.before" "$SUDOERS"
fi

visudo -c
systemctl restart "$SERVICE"

for attempt in {1..30}; do
    if systemctl is-active --quiet "$SERVICE" &&
       curl -fsS --max-time 3 http://127.0.0.1/pincabos-link >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

systemctl is-active --quiet "$SERVICE"
echo "GO [OK] Rollback PinCabOS Link Join Card termine."
ROLLBACK

chmod 0750 "$ROLLBACK"

echo "Backup  : $BACKUP"
echo "Rollback: $ROLLBACK"
echo "GO [OK] Backup et rollback crees."

echo
echo "=== 4. STAGING MODULE WEB ==="

cat > "$STAGE/pincaboslink.py" <<'PYMODULE'
#!/usr/bin/env python3
"""Local PinCabOS Link page with secure pairing form."""

from __future__ import annotations

import hmac
import html
import re
import secrets
import shutil
import subprocess

from flask import Blueprint, Response, request


PINFORGE_MODULE = "PINCABOS_LINK_UI_V2_JOIN_CARD"
HEARTBEAT_TIMER = "pincabos-link-heartbeat.timer"
PAIR_HELPER = "/usr/local/sbin/pincabos-link-web-pair"
PAIR_PATTERN = re.compile(r"^[23456789ABCDEFGHJKLMNPQRSTUVWXYZ]{12}$")
CSRF_TOKEN = secrets.token_urlsafe(32)

pincaboslink_blueprint = Blueprint("pincaboslink_v1", __name__)


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


@pincaboslink_blueprint.route(
    "/pincabos-link",
    methods=["GET", "POST"],
)
def pincaboslink_page() -> Response:
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
                message = "Format invalide. Entrez la cle de liaison a 12 caracteres."
                message_class = "error"
            else:
                success, message = _join_cabinet(code)
                message_class = "success" if success else "error"

    message_html = ""
    if message:
        message_html = (
            '<div class="pair-message '
            + html.escape(message_class)
            + '">'
            + html.escape(message)
            + "</div>"
        )

    document = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PinCabOS Link</title>
<style>
:root{color-scheme:dark;--bg:#090a0f;--panel:#151722;--border:#303446;--text:#f4f4f6;--muted:#a8adbd;--orange:#ff7a18;--mauve:#a970ff;--green:#48d17b;--red:#ff6d6d}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;font-family:system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--text);background:radial-gradient(circle at top right,#2b1645 0,transparent 38%),radial-gradient(circle at top left,#46210c 0,transparent 35%),var(--bg)}
.wrap{width:min(920px,calc(100% - 32px));margin:0 auto}
header{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:24px 0}
.brand{font-size:1.35rem;font-weight:800}.pin{color:var(--orange)}.os{color:var(--mauve)}
nav{display:flex;flex-wrap:wrap;gap:10px}
a.button{display:inline-flex;align-items:center;min-height:42px;padding:10px 15px;border:1px solid var(--border);border-radius:10px;color:var(--text);background:#1b1e2a;text-decoration:none;font-weight:700}
a.primary{border-color:var(--orange);background:#3b210f}
main{padding:42px 0 72px}
.hero h1{margin:0 0 10px;font-size:clamp(2rem,6vw,4rem)}
.hero p{margin:0;color:var(--muted);font-size:1.08rem}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:18px;margin-top:30px}
.card{padding:22px;border:1px solid var(--border);border-radius:16px;background:var(--panel);box-shadow:0 18px 50px rgba(0,0,0,.25)}
.card h2{margin:0 0 12px;font-size:1.1rem}
.card p{color:var(--muted);line-height:1.55}
.join-card{grid-column:1/-1;border-color:#75441f;background:linear-gradient(135deg,#191722,#21180f)}
.pair-form{display:grid;grid-template-columns:1fr auto;gap:12px;margin-top:18px}
.pair-input{width:100%;min-height:50px;padding:12px 15px;border:1px solid #464b60;border-radius:11px;background:#0d0f16;color:#fff;font:700 1.1rem/1.2 ui-monospace,SFMono-Regular,Consolas,monospace;letter-spacing:.08em;text-transform:uppercase;outline:none}
.pair-input:focus{border-color:var(--orange);box-shadow:0 0 0 3px rgba(255,122,24,.16)}
.pair-button{min-height:50px;padding:0 24px;border:1px solid #ff9343;border-radius:11px;background:#d85d08;color:#fff;font-weight:900;cursor:pointer}
.pair-button:hover{background:#ee6a0d}
.pair-message{margin-top:14px;padding:12px 14px;border-radius:10px;font-weight:750}
.pair-message.success{color:#cbffdb;background:#123922;border:1px solid #28643b}
.pair-message.error{color:#ffd0d0;background:#421a1a;border:1px solid #743030}
.hint{margin-top:10px!important;font-size:.9rem}
.status{display:inline-flex;align-items:center;gap:9px;padding:8px 12px;border-radius:999px;font-weight:800}
.status.ok{color:#c8ffdc;background:#123922}
.status.warn{color:#fff0bd;background:#4a3510}
.dot{width:10px;height:10px;border-radius:50%;background:currentColor}
dl{display:grid;grid-template-columns:1fr auto;gap:12px;margin:20px 0 0}
dt{color:var(--muted)}dd{margin:0;font-weight:750}
.notice{margin-top:18px;color:var(--muted);line-height:1.55}
.notice strong{color:var(--text)}
@media(max-width:640px){
  header{align-items:flex-start;flex-direction:column}
  nav{width:100%}a.button{flex:1;justify-content:center}
  .pair-form{grid-template-columns:1fr}
}
</style></head><body><div class="wrap">
<header><div class="brand"><span class="pin">Pin</span>Cab<span class="os">OS</span> Link</div><nav>
<a class="button" href="/">Accueil</a><a class="button" href="/tools">Outils PinCabOS</a><a class="button primary" href="https://pincabos.cc/user/account">Mon compte PinCabOS.cc</a>
</nav></header>
<main>
<section class="hero"><h1>PinCabOS Link</h1><p>Liez ce cabinet a votre compte pincabos.cc directement depuis la WebApp.</p></section>
<section class="grid">
<article class="card join-card">
<h2>Joindre ce PinCab a pincabos.cc</h2>
<p>Generez une cle de liaison dans <strong>Mon compte</strong> sur pincabos.cc, entrez-la ici puis cliquez sur <strong>JOINDRE</strong>.</p>
<form class="pair-form" method="post" action="/pincabos-link" autocomplete="off">
<input type="hidden" name="csrf_token" value="__CSRF__">
<input class="pair-input" type="text" name="pairing_code" maxlength="24" required autofocus spellcheck="false" autocapitalize="characters" placeholder="XXXX-XXXX-XXXX" aria-label="Numero de liaison">
<button class="pair-button" type="submit">JOINDRE</button>
</form>
__MESSAGE__
<p class="hint">Les tirets et les espaces sont acceptes. La cle est a usage unique et n'est jamais conservee par cette page.</p>
</article>
<article class="card"><h2>Presence du cabinet</h2><div class="status __STATE_CLASS__"><span class="dot"></span>__STATE_TEXT__</div><dl>
<dt>Timer heartbeat</dt><dd>__ACTIVE__</dd><dt>Demarrage auto</dt><dd>__ENABLED__</dd><dt>Frequence</dt><dd>60 secondes</dd><dt>Hors ligne apres</dt><dd>180 secondes</dd></dl></article>
<article class="card"><h2>Securite</h2><p class="notice"><strong>Le jeton appareil demeure protege.</strong><br>Le WebApp ne lit et n'affiche jamais le jeton. Si une ancienne liaison locale existe, elle est conservee tant que la nouvelle liaison n'a pas reussi.</p></article>
</section>
</main></div></body></html>"""

    document = (
        document.replace("__CSRF__", html.escape(CSRF_TOKEN, quote=True))
        .replace("__MESSAGE__", message_html)
        .replace("__STATE_CLASS__", state_class)
        .replace("__STATE_TEXT__", html.escape(state_text))
        .replace("__ACTIVE__", html.escape(active))
        .replace("__ENABLED__", html.escape(enabled))
    )

    response = Response(
        document,
        status=200,
        content_type="text/html; charset=utf-8",
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; "
        "style-src 'unsafe-inline'; "
        "base-uri 'none'; "
        "form-action 'self'; "
        "frame-ancestors 'self'"
    )
    return response


def register_pincaboslink(app) -> None:
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
    'methods=["GET", "POST"]',
    'name="pairing_code"',
    '>JOINDRE<',
    'PAIR_HELPER',
    'csrf_token',
    'form-action \'self\'',
)

for marker in required:
    if marker not in text:
        raise SystemExit("NOGO [ERREUR] Marqueur module absent : " + marker)

print("GO [OK] Nouveau module Web valide.")
PY

echo
echo "=== 5. STAGING HELPER ROOT SECURISE ==="

cat > "$STAGE/pincabos-link-web-pair" <<'HELPER'
#!/usr/bin/env bash
set -Eeuo pipefail

CLIENT="/opt/pincabos/bin/pincabos-link"
STATE_DIR="/var/lib/pincabos-link"
STATE="$STATE_DIR/device.json"

[[ "$(id -u)" -eq 0 ]] || {
    echo "PAIR_FAILED"
    exit 70
}

[[ "$#" -eq 1 ]] || {
    echo "PAIR_INVALID"
    exit 64
}

CODE="${1^^}"
CODE="${CODE//-/}"
CODE="${CODE// /}"

[[ "$CODE" =~ ^[23456789ABCDEFGHJKLMNPQRSTUVWXYZ]{12}$ ]] || {
    echo "PAIR_INVALID"
    exit 64
}

[[ -x "$CLIENT" ]] || {
    echo "PAIR_FAILED"
    exit 69
}

OWNER_MODE="$(stat -c '%U:%G:%a' "$CLIENT" 2>/dev/null || true)"
[[ "$OWNER_MODE" == "root:root:755" ]] || {
    echo "PAIR_FAILED"
    exit 69
}

install -d -o root -g root -m 0700 "$STATE_DIR"

OLD=""
TMP="$(mktemp /run/pincabos-web-pair.XXXXXX)"
chmod 0600 "$TMP"

cleanup() {
    rm -f "$TMP"
    if [[ -n "$OLD" && -f "$OLD" ]]; then
        rm -f "$STATE"
        mv -f "$OLD" "$STATE"
        chmod 0600 "$STATE"
        chown root:root "$STATE"
    fi
}

trap cleanup EXIT

if [[ -f "$STATE" ]]; then
    OLD="$STATE_DIR/.device.json.webpair.$$"
    mv "$STATE" "$OLD"
    chmod 0600 "$OLD"
    chown root:root "$OLD"
fi

set +e
printf '%s\n' "$CODE" | "$CLIENT" pair >"$TMP" 2>&1
RC=$?
set -e

if [[ "$RC" -eq 0 && -f "$STATE" ]]; then
    chown root:root "$STATE"
    chmod 0600 "$STATE"

    if [[ -n "$OLD" && -f "$OLD" ]]; then
        rm -f "$OLD"
        OLD=""
    fi

    echo "PAIR_OK"
    exit 0
fi

rm -f "$STATE"

if grep -qiE \
    'expired|expire|invalid|invalide|deja utilise|already used|HTTP 400|HTTP 404|HTTP 409' \
    "$TMP"; then
    echo "PAIR_REJECTED"
elif grep -qiE \
    'url|network|reseau|TLS|certificate|certificat|timeout|timed out|connexion|connection' \
    "$TMP"; then
    echo "PAIR_NETWORK"
else
    echo "PAIR_FAILED"
fi

exit 1
HELPER

chmod 0755 "$STAGE/pincabos-link-web-pair"
bash -n "$STAGE/pincabos-link-web-pair"

echo "GO [OK] Helper root valide."

echo
echo "=== 6. SUDOERS MINIMAL POUR LE WEBAPP ==="

cat > "$STAGE/pincabos-link-web-pair.sudoers" <<'SUDOERS'
# PinCabOS Link Web pairing - least privilege
pinball ALL=(root) NOPASSWD: /usr/local/sbin/pincabos-link-web-pair *
SUDOERS

chmod 0440 "$STAGE/pincabos-link-web-pair.sudoers"
visudo -cf "$STAGE/pincabos-link-web-pair.sudoers"

echo "GO [OK] Sudoers limite au helper de pairing."

echo
echo "=== 7. DEPLOIEMENT ==="

DEPLOYED=1

install -o root -g root -m 0644     "$STAGE/pincaboslink.py"     "$MODULE_FILE"

install -o root -g root -m 0755     "$STAGE/pincabos-link-web-pair"     "$HELPER"

install -o root -g root -m 0440     "$STAGE/pincabos-link-web-pair.sudoers"     "$SUDOERS"

visudo -c

echo "GO [OK] Module, helper et sudoers installes."

echo
echo "=== 8. VALIDATION DROITS ==="

[[ "$(stat -c '%U:%G:%a' "$MODULE_FILE")" == "root:root:644" ]] ||     fail "Permissions module inattendues."

[[ "$(stat -c '%U:%G:%a' "$HELPER")" == "root:root:755" ]] ||     fail "Permissions helper inattendues."

[[ "$(stat -c '%U:%G:%a' "$SUDOERS")" == "root:root:440" ]] ||     fail "Permissions sudoers inattendues."

sudo -l -U pinball 2>/dev/null | grep -Fq "$HELPER" ||     fail "Permission sudo helper non visible pour pinball."

echo "GO [OK] WebApp peut uniquement appeler le helper autorise."

echo
echo "=== 9. REDEMARRAGE WEBAPP ==="

python3 - "$APP_FILE" "$MODULE_FILE" <<'PY'
import ast
import sys
from pathlib import Path

for item in sys.argv[1:]:
    path = Path(item)
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

print("GO [OK] Sources Python valides.")
PY

systemctl restart "$SERVICE"

READY=0

for attempt in {1..40}; do
    if systemctl is-active --quiet "$SERVICE" &&
       curl -fsS            --max-time 3            -o "$BACKUP/pincabos-link-after.html"            http://127.0.0.1/pincabos-link; then
        READY=1
        break
    fi

    sleep 1
done

[[ "$READY" -eq 1 ]] ||     fail "WebApp non disponible apres redemarrage."

echo "GO [OK] WebApp revenue et page accessible."

echo
echo "=== 10. VALIDATION CARTE JOINDRE ==="

python3 - "$BACKUP/pincabos-link-after.html" <<'PY'
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(
    encoding="utf-8",
    errors="replace",
)

required = (
    "Joindre ce PinCab a pincabos.cc",
    'name="pairing_code"',
    'name="csrf_token"',
    ">JOINDRE<",
    "XXXX-XXXX-XXXX",
    "Mon compte PinCabOS.cc",
)

for marker in required:
    if marker not in text:
        raise SystemExit(
            "NOGO [ERREUR] Element UI absent : " + marker
        )

print("GO [OK] Carte de liaison presente.")
print("GO [OK] Champ numero present.")
print("GO [OK] Bouton JOINDRE present.")
print("GO [OK] Protection CSRF presente.")
PY

echo
echo "=== 11. PREUVE AUCUN JETON MODIFIE PENDANT INSTALLATION ==="

if [[ -f "$BACKUP/device-state-before.sha256" ]]; then
    [[ -f "$STATE" ]] ||         fail "Etat liaison a disparu pendant l'installation."

    (cd / && sha256sum -c "$BACKUP/device-state-before.sha256")
    echo "GO [OK] Jeton local strictement inchange."
else
    [[ ! -f "$STATE" ]] ||         fail "Un jeton est apparu sans clic utilisateur."

    echo "GO [OK] Aucun jeton cree pendant l'installation."
fi

(cd / && sha256sum -c "$BACKUP/heartbeat-before.sha256")

echo "GO [OK] Heartbeat strictement inchange."

echo
echo "=== 12. VALIDATION FINALE ==="

[[ "$(systemctl is-active "$SERVICE")" == "active" ]] ||     fail "WebApp inactive."

[[ "$(systemctl is-active pincabos-link-heartbeat.timer)" == "active" ]] ||     fail "Heartbeat timer inactif."

[[ "$(systemctl is-enabled pincabos-link-heartbeat.timer)" == "enabled" ]] ||     fail "Heartbeat timer non enabled."

DEPLOYED=0
trap - ERR

echo
echo "==============================================================="
echo " GO [OK] CARTE JOINDRE PINCABOS.CC INSTALLEE"
echo "==============================================================="
echo " PAGE : http://192.168.254.237/pincabos-link"
echo
echo " UTILISATION :"
echo "  1. Generer la cle dans Mon compte sur pincabos.cc"
echo "  2. Coller la cle dans PinCabOS Link"
echo "  3. Cliquer JOINDRE"
echo "  4. Termine"
echo
echo " Si un ancien jeton local existe :"
echo "  - il est conserve pendant la tentative"
echo "  - il est remplace seulement si la nouvelle liaison reussit"
echo "  - il est restaure automatiquement si la liaison echoue"
echo
echo " Backup  : $BACKUP"
echo " Rollback: $ROLLBACK"
echo "==============================================================="
