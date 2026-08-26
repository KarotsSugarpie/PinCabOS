#!/usr/bin/env bash
set -u

clear

EXPECTED_HOST="pincabos"
EXPECTED_IP="192.168.254.237"

APP="/opt/pincabos/web/app.py"
LINK="/opt/pincabos/web/pincaboslink.py"
STATE="/var/lib/pincabos-link/device.json"
HELPER="/usr/local/sbin/pincabos-link-web-pair"
SCREENS="/opt/pincabos/config/screens/screens.json"

echo "==============================================================="
echo " PINFORGE-SAFE-1A1-449B"
echo " PINCABOS - AUDIT MIRROR COMPTE + CHAT BACKGLASS"
echo " LECTURE SEULE - AUCUNE MODIFICATION"
echo " AUCUN TOKEN / MESSAGE / SECRET AFFICHE"
echo "==============================================================="

echo
echo "=== 1. GARDE CABINET ==="

HOST="$(hostname 2>/dev/null || true)"
echo "Hostname : $HOST"

[[ "${HOST,,}" == "$EXPECTED_HOST" ]] || {
    echo "NOGO [ERREUR] Cabinet inattendu."
    exit 1
}

hostname -I |
    tr ' ' '\n' |
    grep -Fxq "$EXPECTED_IP" || {
        echo "NOGO [ERREUR] IP $EXPECTED_IP absente."
        exit 1
    }

echo "GO [OK] Cabinet confirme."

echo
echo "=== 2. SERVICES ==="

for svc in \
    pincabos-webapp.service \
    pincabos-link-heartbeat.timer \
    pincabos-place-backbox.service \
    pincabos-screen-topology-boot.service
do
    printf '%-42s : %s\n' \
        "$svc" \
        "$(systemctl is-active "$svc" 2>/dev/null || true)"
done

echo
echo "=== 3. ETAT PINCABOS LINK ==="

for file in "$APP" "$LINK" "$HELPER"; do
    if [[ -e "$file" ]]; then
        stat -c '%U:%G %a %s %n' "$file"
    else
        echo "ABSENT : $file"
    fi
done

if [[ -f "$LINK" ]]; then
    grep -nE \
        'PINCABOS_LINK_UI_V[0-9]|PINCABOS_LINK_NATIVE_SHELL|register_pincaboslink|/pincabos-link' \
        "$LINK" \
        | sed -n '1,120p' \
        || true
fi

if [[ -f "$APP" ]]; then
    grep -nE \
        'register_pincaboslink|href="/pincabos-link"|def page\(' \
        "$APP" \
        | sed -n '1,120p' \
        || true
fi

echo
echo "=== 4. JETON LOCAL - METADONNEES UNIQUEMENT ==="

if [[ -f "$STATE" ]]; then
    stat -c 'state owner=%U:%G mode=%a size=%s' "$STATE"

python3 - "$STATE" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])

try:
    data = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    print("NOGO [INFO] device.json illisible.")
    raise SystemExit(0)

print("Cles JSON presentes :", ", ".join(sorted(data.keys())))
print("api_base present    :", bool(data.get("api_base")))
print("device_token present:", bool(data.get("device_token")))
print("cabinet present     :", bool(data.get("cabinet")))
PY
else
    echo "INFO [ABSENT] Aucun device.json."
fi

echo
echo "=== 5. CONNECTIVITE PINCABOS.CC ==="

for route in \
    / \
    /api/control-hub/context \
    /api/control-hub/chat/1
do
    curl -sS \
        --max-time 10 \
        -o /dev/null \
        -w "$route : HTTP %{http_code} | %{content_type}\n" \
        "https://pincabos.cc${route}" \
        || true
done

echo
echo "=== 6. TOPOLOGIE ECRANS ==="

if [[ -f "$SCREENS" ]]; then
    echo "screens.json : present"

python3 - "$SCREENS" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])

try:
    data = json.loads(path.read_text(encoding="utf-8"))
except Exception as exc:
    print("NOGO [INFO] screens.json invalide:", exc)
    raise SystemExit(0)

def walk(value, prefix=""):
    if isinstance(value, dict):
        for key, item in value.items():
            here = f"{prefix}.{key}" if prefix else str(key)
            key_l = str(key).lower()
            if any(word in key_l for word in (
                "playfield",
                "backglass",
                "fulldmd",
                "topper",
                "role",
                "output",
                "geometry",
                "width",
                "height",
                "x",
                "y",
            )):
                if isinstance(item, (str, int, float, bool)) or item is None:
                    print(f"{here} = {item}")
            walk(item, here)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            walk(item, f"{prefix}[{index}]")

walk(data)
PY
else
    echo "INFO [ABSENT] $SCREENS"
fi

echo
echo "--- xrandr connectes ---"

DISPLAY=:0 \
XAUTHORITY=/home/pinball/.Xauthority \
xrandr --query 2>/dev/null \
    | grep ' connected' \
    | sed -n '1,20p' \
    || true

echo
echo "=== 7. OUTILS EXISTANTS POUR AFFICHER UNE WEBAPP ==="

for file in \
    /opt/pincabos/tools/launch-webapp-screen.sh \
    /opt/pincabos/tools/close-webapp-screen.sh \
    /usr/local/sbin/launch-webapp-screen.sh \
    /usr/local/sbin/close-webapp-screen.sh
do
    if [[ -f "$file" ]]; then
        echo "--- $file ---"
        stat -c '%U:%G %a %s %n' "$file"
        grep -nE \
            'google-chrome|chromium|window-position|window-size|screen|geometry|url|user-data-dir' \
            "$file" \
            | sed -n '1,120p' \
            || true
    fi
done

echo
echo "=== 8. ROUTES BACKGLASS / TOGGLE ==="

if [[ -f "$APP" ]]; then
    grep -nE \
        'toggle-webapp-screen|backglass|launch-webapp-screen|close-webapp-screen|webapp_screen_toggle_html' \
        "$APP" \
        | sed -n '1,180p' \
        || true
fi

echo
echo "=== 9. NAVIGATEURS DISPONIBLES ==="

for bin in \
    /usr/bin/google-chrome \
    /usr/bin/google-chrome-stable \
    /usr/bin/chromium \
    /usr/bin/chromium-browser
do
    [[ -x "$bin" ]] && echo "GO [OK] $bin"
done

echo
echo "=== 10. PAGE PINCABOS LINK SERVIE ==="

curl -sS \
    --max-time 8 \
    -o /tmp/pincabos-449b-link.html \
    -w 'GET /pincabos-link : HTTP %{http_code} | %{content_type}\n' \
    http://127.0.0.1/pincabos-link \
    || true

if [[ -f /tmp/pincabos-449b-link.html ]]; then
    for marker in \
        'PinCabOS Link' \
        'JOINDRE' \
        'Ouvrir VPinFE' \
        'PinCab Explorer' \
        'Soutenir PinCabOS'
    do
        if grep -Fq "$marker" /tmp/pincabos-449b-link.html; then
            echo "GO [OK] $marker"
        else
            echo "INFO [ABSENT] $marker"
        fi
    done
fi

rm -f /tmp/pincabos-449b-link.html

echo
echo "==============================================================="
echo " AUDIT 449B TERMINE - AUCUNE MODIFICATION"
echo "==============================================================="
