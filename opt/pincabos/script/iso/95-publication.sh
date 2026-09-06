#!/usr/bin/env bash
# PINCABOS_ISO_ETAPES_V1 — etape 95-publication d iso.sh (texte de l ancienne section, inchange)
set -Eeuo pipefail
. "$(dirname "$(readlink -f "$0")")/00-lib.sh"
trap cleanup_mounts EXIT

ROOTFS_DIR="$LIVE_ROOTFS"   # pose par l etape 80 (9L) dans l ancien flux
# PINCABOS_OPTIONAL_WEB_PUBLISH_V1
# Publication optionnelle de l'ISO apres un build reussi.
# Demande IP/login/password une seule fois.
# Met a jour automatiquement les index du serveur Web.
# ======================================================================

pincabos_offer_web_publish() {
    local ANSWER=""
    local WEB_IP=""
    local WEB_USER=""
    local WEB_PASS=""
    local ISO_FILE=""
    local ISO_NAME=""
    local ISO_SHA=""
    local ISO_SIZE_BYTES=""
    local PUB_DATE=""
    local REMOTE_ROOT="/var/www/html/updates"
    local REMOTE_ISO_DIR="${REMOTE_ROOT}/iso"
    local REMOTE_SHA=""

    echo
    echo "==============================================================="
    echo " PINCABOS — PUBLICATION ISO"
    echo "==============================================================="
    echo

    read -rp "Publier l'ISO sur le serveur Web ? [o/N] : " ANSWER || true

    case "${ANSWER,,}" in
        o|oui|y|yes)
            ;;
        *)
            echo "INFO : publication Web ignoree."
            return 0
            ;;
    esac

    echo
    echo "=== Configuration serveur Web ==="

    while [ -z "$WEB_IP" ]; do
        read -rp "Adresse IP du serveur Web : " WEB_IP
    done

    while [ -z "$WEB_USER" ]; do
        read -rp "Login SSH : " WEB_USER
    done

    while [ -z "$WEB_PASS" ]; do
        read -rsp "Mot de passe SSH : " WEB_PASS
        echo
    done

    echo
    echo "=== Recherche ISO produite ==="

    ISO_FILE="/opt/pincabos/build/output/PinCabOS-beta-Installer.iso"

    if [ ! -s "$ISO_FILE" ]; then
        ISO_FILE="$(
            find /opt/pincabos/build/output \
                -maxdepth 1 \
                -type f \
                -name '*.iso' \
                -printf '%T@ %p\n' 2>/dev/null \
            | sort -nr \
            | head -1 \
            | cut -d' ' -f2-
        )"
    fi

    if [ -z "${ISO_FILE:-}" ] || [ ! -s "$ISO_FILE" ]; then
        echo "ERREUR [X] aucune ISO valide trouvee."
        WEB_PASS=""
        return 1
    fi

    ISO_NAME="$(basename "$ISO_FILE")"
    ISO_SHA="$(sha256sum "$ISO_FILE" | awk '{print $1}')"
    ISO_SIZE_BYTES="$(stat -c '%s' "$ISO_FILE")"
    PUB_DATE="$(date '+%Y-%m-%dT%H:%M:%S%z')"

    printf '%s  %s\n' \
        "$ISO_SHA" \
        "$ISO_NAME" \
        > "${ISO_FILE}.sha256"

    echo "ISO    : $ISO_FILE"
    echo "Taille : $(du -h "$ISO_FILE" | awk '{print $1}')"
    echo "SHA256 : $ISO_SHA"

    echo
    echo "=== Outils de publication ==="

    if ! command -v sshpass >/dev/null 2>&1; then
        echo "INFO : installation de sshpass..."

        apt-get update
        DEBIAN_FRONTEND=noninteractive \
            apt-get install -y sshpass
    fi

    if ! command -v rsync >/dev/null 2>&1; then
        echo "INFO : installation de rsync..."

        apt-get update
        DEBIAN_FRONTEND=noninteractive \
            apt-get install -y rsync
    fi

    command -v sshpass >/dev/null
    command -v rsync >/dev/null

    export SSHPASS="$WEB_PASS"

    local SSH_OPTS=(
        -o StrictHostKeyChecking=accept-new
        -o ConnectTimeout=15
        -o ServerAliveInterval=30
        -o ServerAliveCountMax=6
    )

    echo
    echo "=== Test connexion SSH ==="

    if ! sshpass -e ssh \
        "${SSH_OPTS[@]}" \
        "${WEB_USER}@${WEB_IP}" \
        'echo "GO [OK] connexion SSH"'
    then
        echo "ERREUR [X] connexion SSH impossible."
        unset SSHPASS
        WEB_PASS=""
        return 1
    fi

    echo
    echo "=== Preparation serveur Web ==="

    if ! sshpass -e ssh \
        "${SSH_OPTS[@]}" \
        "${WEB_USER}@${WEB_IP}" \
        "mkdir -p '$REMOTE_ISO_DIR' && test -w '$REMOTE_ISO_DIR'"
    then
        echo
        echo "ERREUR [X] impossible d'ecrire dans :"
        echo "$REMOTE_ISO_DIR"
        echo
        echo "Le compte SSH doit avoir acces en ecriture a /var/www/html/updates."
        unset SSHPASS
        WEB_PASS=""
        return 1
    fi

    echo
    echo "=== Transfert ISO + SHA256 ==="

# PINCABOS_WEB_RSYNC_SAFE_V3
    if ! sshpass -e rsync \
        -avhP \
        --checksum \
        -e "ssh -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 -o ServerAliveCountMax=6" \
        "$ISO_FILE" \
        "${ISO_FILE}.sha256" \
        "${WEB_USER}@${WEB_IP}:${REMOTE_ISO_DIR}/"
    then
        echo "ERREUR [X] transfert rsync."
        unset SSHPASS
        WEB_PASS=""
        return 1
    fi

    echo
    echo "=== Validation SHA256 distant ==="

    REMOTE_SHA="$(
        sshpass -e ssh \
            "${SSH_OPTS[@]}" \
            "${WEB_USER}@${WEB_IP}" \
            "sha256sum '$REMOTE_ISO_DIR/$ISO_NAME' | awk '{print \$1}'"
    )"

    echo "Local   : $ISO_SHA"
    echo "Distant : $REMOTE_SHA"

    if [ "$REMOTE_SHA" != "$ISO_SHA" ]; then
        echo "ERREUR [X] SHA256 distant different."
        unset SSHPASS
        WEB_PASS=""
        return 1
    fi

    echo "GO [OK] ISO distante identique"

    echo
    echo "=== INDEX WEB CANONIQUE ==="

    # ==============================================================
    # PINCABOS_CANONICAL_WEB_INDEX_V6
    #
    # IMPORTANT :
    # - réécrit complètement /updates/index.html
    # - réécrit complètement /updates/iso/index.html
    # - n'ajoute jamais de bloc dans un ancien HTML
    # - une seule ISO affichée : ISO_NAME
    # ==============================================================

    if ! sshpass -e ssh \
        "${SSH_OPTS[@]}" \
        "${WEB_USER}@${WEB_IP}" \
        bash -s -- \
        "$REMOTE_ROOT" \
        "$ISO_NAME" \
        "$ISO_SHA" \
        "$ISO_SIZE_BYTES" <<'PINCABOS_CANONICAL_INDEX_V6'
set -Eeuo pipefail

ROOT="$1"
ISO_NAME="$2"
EXPECTED_SHA="$3"
EXPECTED_SIZE="$4"

ISO_DIR="$ROOT/iso"
ISO_FILE="$ISO_DIR/$ISO_NAME"

echo
echo "---------------------------------------------------------------"
echo " PINCABOS — GENERATION INDEX CANONIQUE V6"
echo "---------------------------------------------------------------"

test -d "$ROOT" || {
    echo "ERREUR [X] racine Web absente : $ROOT"
    exit 1
}

test -s "$ISO_FILE" || {
    echo "ERREUR [X] ISO distante absente : $ISO_FILE"
    exit 1
}

ACTUAL_SHA="$(sha256sum "$ISO_FILE" | awk '{print $1}')"
ACTUAL_SIZE="$(stat -c '%s' "$ISO_FILE")"

echo
echo "SHA attendu : $EXPECTED_SHA"
echo "SHA distant : $ACTUAL_SHA"

if [ "$ACTUAL_SHA" != "$EXPECTED_SHA" ]; then
    echo "ERREUR [X] SHA ISO distant différent"
    exit 1
fi

if [ "$ACTUAL_SIZE" != "$EXPECTED_SIZE" ]; then
    echo "ERREUR [X] taille ISO distante différente"
    exit 1
fi

echo "GO [OK] ISO distante validée"

PUB_DATE="$(date '+%Y-%m-%d %H:%M:%S %Z')"

STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="/var/backups/pincabos-web-index/$STAMP"

mkdir -p "$BACKUP_DIR"

echo
echo "--- Backup anciens index ---"

for FILE in \
    "$ROOT/index.html" \
    "$ISO_DIR/index.html"
do
    if [ -f "$FILE" ]; then
        cp -a "$FILE" "$BACKUP_DIR/"
        echo "GO [OK] backup : $FILE"
    fi
done

echo
echo "--- SHA256 officiel ---"

printf '%s  %s\n' \
    "$ACTUAL_SHA" \
    "$ISO_NAME" \
    > "$ISO_FILE.sha256"

chmod 0644 \
    "$ISO_FILE" \
    "$ISO_FILE.sha256"

echo
echo "--- Liens de compatibilité ---"

ln -sfn \
    "$ISO_NAME" \
    "$ISO_DIR/PinCabOS-Installer.iso"

ln -sfn \
    "$ISO_NAME.sha256" \
    "$ISO_DIR/PinCabOS-Installer.iso.sha256"

echo "GO [OK] liens"

echo
echo "--- Génération HTML complète ---"

python3 - \
    "$ROOT" \
    "$ISO_NAME" \
    "$ACTUAL_SHA" \
    "$ACTUAL_SIZE" \
    "$PUB_DATE" <<'PYHTML'
from pathlib import Path
import html
import sys

root = Path(sys.argv[1])
iso_name = sys.argv[2]
sha = sys.argv[3]
size_bytes = int(sys.argv[4])
pub_date = sys.argv[5]


def human_size(value):
    value = float(value)

    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            if unit in ("GiB", "TiB"):
                return f"{value:.2f} {unit}"
            if unit == "MiB":
                return f"{value:.1f} {unit}"
            return f"{value:.0f} {unit}"

        value /= 1024


filename = html.escape(iso_name)
checksum = html.escape(sha)
size = html.escape(human_size(size_bytes))
published = html.escape(pub_date)

byte_text = f"{size_bytes:,}".replace(",", " ")


def render(prefix):
    iso_url = html.escape(prefix + iso_name)
    sha_url = html.escape(prefix + iso_name + ".sha256")

    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta
    name="viewport"
    content="width=device-width,initial-scale=1"
>

<title>PinCabOS Installer</title>

<style>
:root {{
    color-scheme: dark;

    --bg: #070a0f;
    --panel: #111822;
    --panel2: #0d131c;
    --border: #2d3948;

    --text: #f6f8fb;
    --muted: #9bacc0;

    --orange: #ff9700;
    --orange-light: #ffb32d;

    --green: #36df8c;
    --blue: #58baff;
}}

* {{
    box-sizing: border-box;
}}

html {{
    min-height: 100%;
    background: var(--bg);
}}

body {{
    margin: 0;
    min-height: 100vh;

    background:
        radial-gradient(
            circle at 50% -160px,
            rgba(73, 45, 107, .38) 0,
            rgba(24, 18, 40, .20) 300px,
            transparent 650px
        ),
        var(--bg);

    color: var(--text);

    font-family:
        Inter,
        "Segoe UI",
        Roboto,
        Helvetica,
        Arial,
        sans-serif;

    -webkit-font-smoothing: antialiased;
}}

.wrapper {{
    width: min(760px, calc(100% - 36px));
    margin: 0 auto;
    padding: 72px 0 50px;
}}

.status {{
    display: flex;
    align-items: center;
    gap: 8px;

    margin-bottom: 12px;

    color: var(--green);
    font-size: 14px;
    font-weight: 750;
}}

.status-dot {{
    width: 7px;
    height: 7px;

    border-radius: 50%;
    background: var(--green);

    box-shadow:
        0 0 10px rgba(54, 223, 140, .8);
}}

h1 {{
    margin: 0;

    font-size: clamp(34px, 6vw, 48px);
    line-height: 1.08;
    letter-spacing: -.8px;
}}

.subtitle {{
    margin: 13px 0 30px;

    color: var(--muted);
    font-size: 15px;
    line-height: 1.6;
}}

.download {{
    display: inline-flex;
    align-items: center;
    justify-content: center;

    min-height: 48px;
    padding: 0 25px;

    border: 0;
    border-radius: 9px;

    background:
        linear-gradient(
            180deg,
            var(--orange-light),
            var(--orange)
        );

    color: #111;
    text-decoration: none;

    font-size: 14px;
    font-weight: 800;

    box-shadow:
        0 10px 25px rgba(0, 0, 0, .35);

    transition:
        transform .12s ease,
        filter .12s ease;
}}

.download:hover {{
    filter: brightness(1.08);
    transform: translateY(-1px);
}}

.card {{
    margin-top: 30px;

    overflow: hidden;

    border: 1px solid var(--border);
    border-radius: 13px;

    background:
        linear-gradient(
            180deg,
            rgba(19, 27, 38, .96),
            rgba(13, 19, 28, .96)
        );

    box-shadow:
        0 20px 55px rgba(0, 0, 0, .33);
}}

.row {{
    display: grid;

    grid-template-columns:
        135px
        minmax(0, 1fr);

    gap: 20px;

    padding: 16px 19px;

    border-bottom:
        1px solid var(--border);
}}

.row:last-child {{
    border-bottom: 0;
}}

.label {{
    color: var(--muted);
    font-size: 14px;
}}

.value {{
    min-width: 0;

    color: var(--text);
    font-size: 14px;
    font-weight: 650;

    overflow-wrap: anywhere;
}}

code {{
    font-family:
        Consolas,
        "SFMono-Regular",
        Monaco,
        monospace;

    font-size: 12px;
    line-height: 1.55;

    color: #e5edf7;
}}

.sha-link {{
    color: var(--blue);
    text-decoration: none;
}}

.sha-link:hover {{
    text-decoration: underline;
}}

footer {{
    margin-top: 29px;

    color: #718398;

    font-size: 12px;
}}

@media (max-width: 600px) {{

    .wrapper {{
        width: min(100% - 24px, 760px);
        padding-top: 38px;
    }}

    .row {{
        grid-template-columns: 1fr;
        gap: 6px;
    }}

    h1 {{
        font-size: 34px;
    }}

    .download {{
        width: 100%;
    }}
}}
</style>
</head>

<body>

<main class="wrapper">

    <div class="status">
        <span class="status-dot"></span>
        <span>ISO disponible</span>
    </div>

    <h1>PinCabOS Installer</h1>

    <p class="subtitle">
        Dernière image d'installation officielle de PinCabOS.
    </p>

    <a
        class="download"
        href="{iso_url}"
    >
        Télécharger PinCabOS
    </a>

    <section class="card">

        <div class="row">
            <div class="label">Fichier</div>

            <div class="value">
                <code>{filename}</code>
            </div>
        </div>

        <div class="row">
            <div class="label">Taille</div>

            <div class="value">
                {size} — {byte_text} octets
            </div>
        </div>

        <div class="row">
            <div class="label">SHA-256</div>

            <div class="value">
                <code>{checksum}</code>
            </div>
        </div>

        <div class="row">
            <div class="label">Somme</div>

            <div class="value">
                <a
                    class="sha-link"
                    href="{sha_url}"
                >
                    {filename}.sha256
                </a>
            </div>
        </div>

        <div class="row">
            <div class="label">Publication</div>

            <div class="value">
                {published}
            </div>
        </div>

    </section>

    <footer>
        PinCabOS — Linux Virtual Pinball Cabinet OS
    </footer>

</main>

<!-- PINCABOS_CANONICAL_INDEX_V6 -->

</body>
</html>
"""


# /updates/
(root / "index.html").write_text(
    render("iso/"),
    encoding="utf-8",
)

# /updates/iso/
(root / "iso" / "index.html").write_text(
    render(""),
    encoding="utf-8",
)

print("GO [OK] /updates/index.html")
print("GO [OK] /updates/iso/index.html")
PYHTML

chmod 0644 \
    "$ROOT/index.html" \
    "$ISO_DIR/index.html"

echo
echo "--- Validation HTML ---"

for INDEX in \
    "$ROOT/index.html" \
    "$ISO_DIR/index.html"
do
    test -s "$INDEX"

    COUNT="$(
        grep -c \
            'PINCABOS_CANONICAL_INDEX_V6' \
            "$INDEX" || true
    )"

    if [ "$COUNT" != "1" ]; then
        echo "ERREUR [X] marker HTML invalide : $INDEX"
        exit 1
    fi

    # Ces anciens blocs ne doivent PLUS exister.
    if grep -qE \
        'PINCABOS_(PUBLISH_INFO|AUTO_ISO|ISO_SECTION)_(START|END)' \
        "$INDEX"
    then
        echo "ERREUR [X] ancien bloc HTML détecté : $INDEX"
        exit 1
    fi

    echo "GO [OK] index canonique : $INDEX"
done

echo
echo "--- Validation checksum ---"

cd "$ISO_DIR"
sha256sum -c "$ISO_NAME.sha256"

if command -v nginx >/dev/null 2>&1; then
    echo
    echo "--- Validation Nginx ---"
    nginx -t
fi

echo
echo "GO [OK] INDEX WEB CANONIQUE V6"
PINCABOS_CANONICAL_INDEX_V6

    then
        echo "ERREUR [X] génération index canonique."
        unset SSHPASS
        WEB_PASS=""
        return 1
    fi

    echo "GO [OK] index Web canonique terminé"


    unset SSHPASS
    WEB_PASS=""

    echo
    echo "==============================================================="
    echo " GO [OK] PUBLICATION WEB TERMINEE"
    echo "==============================================================="
    echo
    echo "Serveur : $WEB_IP"
    echo "ISO     : $ISO_NAME"
    echo "SHA256  : $ISO_SHA"
    echo
    echo "Index mis a jour :"
    echo "  $REMOTE_ROOT/index.html"
    echo "  $REMOTE_ISO_DIR/index.html"

    return 0
}


# Le build a atteint la fin de iso.sh : l'ISO est donc consideree reussie.
if ! pincabos_offer_web_publish; then
    echo
    echo "WARNING: le build ISO est reussi, mais la publication Web a echoue."
    echo "L'ISO locale est conservee."
fi
