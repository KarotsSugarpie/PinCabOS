#!/usr/bin/env bash
set -Eeuo pipefail

ORIGINAL="/home/pinball/PINCABOS_FULLWIDTH_AUTO_RELEASE.sh"
WORK="/home/pinball/pincabos-fullwidth-auto-release-20260822-093232"
SRC="$WORK/source"
BRANCH="feat/fullwidth-updates-auto-release-20260822-093232"
EXPECTED_MAIN="07df37b43762b5864b6fe73687910ff314693203"
STAMP="$(date +%Y%m%d-%H%M%S)"

echo "==============================================================="
echo " PINCABOS - CORRECTION FULLWIDTH + REPRISE"
echo " AUCUN RECLONE - AUCUN REBOOT"
echo "==============================================================="
echo

echo "=== 1. VALIDATION DU TRAVAIL EXISTANT ==="

[ -f "$ORIGINAL" ] || {
    echo "NOGO [!!] Script original absent."
    exit 1
}

[ -d "$SRC/.git" ] || {
    echo "NOGO [!!] Clone existant absent : $SRC"
    exit 1
}

CURRENT_BRANCH="$(git -C "$SRC" branch --show-current)"

echo "Branch attendu : $BRANCH"
echo "Branch actuel  : $CURRENT_BRANCH"

[ "$CURRENT_BRANCH" = "$BRANCH" ] || {
    echo "NOGO [!!] Mauvaise branche."
    exit 1
}

DIRTY="$(git -C "$SRC" status --porcelain)"

if [ -n "$DIRTY" ]; then
    echo "NOGO [!!] La source a deja des modifications :"
    echo "$DIRTY"
    exit 1
fi

git -C "$SRC" fetch origin main

CURRENT_MAIN="$(git -C "$SRC" rev-parse origin/main)"

echo "Main attendu : $EXPECTED_MAIN"
echo "Main actuel  : $CURRENT_MAIN"

[ "$CURRENT_MAIN" = "$EXPECTED_MAIN" ] || {
    echo "NOGO [!!] main a change depuis le premier audit."
    echo "On ne pousse rien."
    exit 1
}

echo "GO [OK] Travail existant intact."
echo

echo "=== 2. VERIFICATION DU VRAI CSS GLOBAL ==="

INJECTOR="$SRC/opt/pincabos/web/pincabos_appearance_global.py"
GLOBAL_CSS="$SRC/opt/pincabos/web/static/pincabos-appearance-dashboard-menu-v2.css"

[ -f "$INJECTOR" ] || {
    echo "NOGO [!!] Injecteur Appearance absent."
    exit 1
}

[ -f "$GLOBAL_CSS" ] || {
    echo "NOGO [!!] CSS global injecte absent."
    exit 1
}

grep -n \
    '_BRIDGE_PATH' \
    "$INJECTOR"

grep -q \
    'pincabos-appearance-dashboard-menu-v2.css' \
    "$INJECTOR" || {
        echo "NOGO [!!] Mauvais CSS global dans l'injecteur."
        exit 1
    }

echo
echo "=== 3. VALIDATION SUR UNE PAGE LIVE ==="

curl -sS \
    http://127.0.0.1/tools \
    -o /tmp/pincabos-fullwidth-live-page.html

if grep -q \
    'pincabos-appearance-dashboard-menu-v2.css' \
    /tmp/pincabos-fullwidth-live-page.html
then
    echo "GO [OK] CSS global réellement injecte dans le HTML."
else
    echo "NOGO [!!] Le CSS global n'est pas injecte dans /tools."
    echo
    echo "Aucune modification GitHub."
    exit 1
fi

echo

echo "=== 4. BACKUP DU SCRIPT ORIGINAL ==="

cp -a \
    "$ORIGINAL" \
    "${ORIGINAL}.bak-fix-fullwidth-$STAMP"

echo "GO [OK] Backup cree."
echo

echo "=== 5. CORRECTION DU SCRIPT ORIGINAL ==="

python3 - <<'PY'
from pathlib import Path
import re

p = Path("/home/pinball/PINCABOS_FULLWIDTH_AUTO_RELEASE.sh")
s = p.read_text(encoding="utf-8")

# ------------------------------------------------------------
# A. Reutiliser exactement le clone deja construit.
# ------------------------------------------------------------

old_header = '''STAMP="$(date +%Y%m%d-%H%M%S)"
WORK="/home/pinball/pincabos-fullwidth-auto-release-$STAMP"
SRC="$WORK/source"
BRANCH="feat/fullwidth-updates-auto-release-$STAMP"
DIST="$WORK/preflight-dist"
'''

new_header = '''STAMP="20260822-093232"
WORK="/home/pinball/pincabos-fullwidth-auto-release-20260822-093232"
SRC="$WORK/source"
BRANCH="feat/fullwidth-updates-auto-release-20260822-093232"
DIST="$WORK/preflight-dist"
'''

if old_header not in s:
    if new_header not in s:
        raise SystemExit(
            "NOGO [!!] Bloc WORK original introuvable."
        )
else:
    s = s.replace(
        old_header,
        new_header,
        1
    )

# ------------------------------------------------------------
# B. Remplacer le clone par une reprise du clone existant.
# ------------------------------------------------------------

pattern = re.compile(
    r'echo "=== 2\. CLONE SPARSE PROPRE DE MAIN ===".*?'
    r'echo "=== 3\. AUDIT LARGEUR DES PAGES GITHUB ==="',
    re.S
)

replacement = r'''echo "=== 2. REPRISE DU CLONE SPARSE EXISTANT ==="

if [ ! -d "$SRC/.git" ]; then
    echo "NOGO [!!] Clone existant absent : $SRC"
    exit 1
fi

CURRENT_BRANCH="$(git -C "$SRC" branch --show-current)"

if [ "$CURRENT_BRANCH" != "$BRANCH" ]; then
    echo "NOGO [!!] Branche inattendue : $CURRENT_BRANCH"
    exit 1
fi

if [ -n "$(git -C "$SRC" status --porcelain)" ]; then
    echo "NOGO [!!] Clone non propre avant reprise."
    git -C "$SRC" status --short
    exit 1
fi

git -C "$SRC" fetch origin main

BASE_SHA="$(git -C "$SRC" rev-parse origin/main)"

if [ "$BASE_SHA" != "07df37b43762b5864b6fe73687910ff314693203" ]; then
    echo "NOGO [!!] main a change depuis le preflight initial."
    echo "Main actuel : $BASE_SHA"
    exit 1
fi

echo "Main   : $BASE_SHA"
echo "Branch : $BRANCH"
echo "GO [OK] Clone existant reutilise."

echo

echo "=== 3. AUDIT LARGEUR DES PAGES GITHUB ==="'''

s2, count = pattern.subn(
    replacement,
    s,
    count=1
)

if count != 1:
    raise SystemExit(
        f"NOGO [!!] Bloc clone non remplace : {count}"
    )

s = s2

# ------------------------------------------------------------
# C. Corriger le faux test sur le CSS global.
# ------------------------------------------------------------

start = s.find('BRIDGE_REFS="$(')

if start < 0:
    raise SystemExit(
        "NOGO [!!] Ancien audit BRIDGE_REFS introuvable."
    )

end_marker = 'echo "GO [OK] Couche CSS globale detectee."'

end = s.find(
    end_marker,
    start
)

if end < 0:
    raise SystemExit(
        "NOGO [!!] Fin ancien audit CSS introuvable."
    )

end += len(end_marker)

correct = r'''INJECTOR="opt/pincabos/web/pincabos_appearance_global.py"
GLOBAL_BRIDGE="opt/pincabos/web/static/pincabos-appearance-dashboard-menu-v2.css"

if [ ! -f "$INJECTOR" ]; then
    echo "NOGO [!!] Injecteur Appearance absent."
    exit 1
fi

if [ ! -f "$GLOBAL_BRIDGE" ]; then
    echo "NOGO [!!] CSS global injecte absent."
    exit 1
fi

if ! grep -q \
    'pincabos-appearance-dashboard-menu-v2.css' \
    "$INJECTOR"
then
    echo "NOGO [!!] L'injecteur ne pointe pas vers le CSS global attendu."
    exit 1
fi

echo "Injecteur global : $INJECTOR"
echo "CSS global       : $GLOBAL_BRIDGE"
echo "GO [OK] Couche CSS globale detectee."'''

s = (
    s[:start]
    + correct
    + s[end:]
)

# ------------------------------------------------------------
# D. Utiliser le VRAI CSS injecte globalement.
# ------------------------------------------------------------

s = s.replace(
    "pincabos-appearance-global-bridge-v1.css",
    "pincabos-appearance-dashboard-menu-v2.css"
)

# ------------------------------------------------------------
# E. Rendre le bloc Full Width plus global.
# ------------------------------------------------------------

old_block = r'''html body main,
html body .container,
html body .container-fluid,
html body .main-content,
html body .page-content,
html body .content-wrapper {
  width: 100% !important;
  max-width: none !important;
  box-sizing: border-box !important;
}'''

new_block = r'''html body main,
html body > main,
html body > .container,
html body > .container-fluid,
html body > .main-content,
html body > .page-content,
html body > .content-wrapper,
html body main > .container,
html body main > .container-fluid,
html body main > .main-content,
html body main > .page-content,
html body main > .content-wrapper {
  width: 100% !important;
  max-width: none !important;
  box-sizing: border-box !important;
}'''

if old_block in s:
    s = s.replace(
        old_block,
        new_block,
        1
    )

# ------------------------------------------------------------
# F. Elargir les racines PinCabOS connues.
# ------------------------------------------------------------

old_roots = r'''html body .pco-tools-page,
html body .pco-up-wrap,
html body .pco-st-shell,
html body .dof-pro-shell,
html body .vpxbc-shell,
html body .pco-page,
html body .pco-page-wrap,
html body .pco-page-shell {'''

new_roots = r'''html body .pco-tools-page,
html body .pco-up-wrap,
html body .pco-st-shell,
html body .dof-pro-shell,
html body .vpxbc-shell,
html body .pco-page,
html body .pco-page-wrap,
html body .pco-page-shell,
html body .pco-tools-page,
html body .pco-dashboard-page,
html body .pco-settings-page,
html body .pco-admin-page,
html body .pco-network-page,
html body .pco-storage-page,
html body .pco-explorer-page,
html body .pco-import-page,
html body .pco-export-page {'''

if old_roots in s:
    s = s.replace(
        old_roots,
        new_roots,
        1
    )

# ------------------------------------------------------------
# G. Après merge, forcer aussi un workflow_dispatch.
# Cela valide le workflow même si GitHub ne déclenche pas le
# tout premier pull_request_target créé par cette même PR.
# ------------------------------------------------------------

needle = '''echo "GO [OK] PR #$PRNUM mergee."
echo

echo "=== 18. ATTENTE DE LA RELEASE AUTOMATIQUE ==="
'''

insert = '''echo "GO [OK] PR #$PRNUM mergee."
echo

echo "=== 17B. DECLENCHEMENT EXPLICITE DU WORKFLOW RELEASE ==="

DISPATCHED=0

for TRY in $(seq 1 12); do
    if gh workflow run \
        pincabos-release-v4.yml \
        --repo "$REPO" \
        -f pr_number="$PRNUM" \
        -f channel=beta
    then
        DISPATCHED=1
        break
    fi

    echo "Workflow pas encore disponible, attente 5 sec..."
    sleep 5
done

if [ "$DISPATCHED" = "1" ]; then
    echo "GO [OK] Workflow Release V4 declenche."
else
    echo "INFO [--] Dispatch manuel non confirme."
    echo "Le trigger automatique peut tout de meme etre actif."
fi

echo

echo "=== 18. ATTENTE DE LA RELEASE AUTOMATIQUE ==="
'''

if needle not in s:
    raise SystemExit(
        "NOGO [!!] Point insertion workflow introuvable."
    )

s = s.replace(
    needle,
    insert,
    1
)

p.write_text(
    s,
    encoding="utf-8"
)

print("GO [OK] Clone existant conserve.")
print("GO [OK] Audit CSS global corrige.")
print("GO [OK] Vrai CSS global utilise.")
print("GO [OK] Full Width global renforce.")
print("GO [OK] Workflow Release explicitement testable.")
PY

echo
echo "=== 6. VERIFICATION DES CORRECTIONS ==="

grep -n \
    'pincabos-appearance-dashboard-menu-v2.css' \
    "$ORIGINAL" \
    | head -10

echo

grep -n \
    'REPRISE DU CLONE SPARSE EXISTANT' \
    "$ORIGINAL"

grep -n \
    '17B. DECLENCHEMENT EXPLICITE' \
    "$ORIGINAL"

echo
echo "=== 7. VALIDATION BASH ==="

bash -n "$ORIGINAL"

echo "GO [OK] Script corrige valide."
echo

echo "==============================================================="
echo " GO [OK] CORRECTIF PRET"
echo " REPRISE SANS RECLONE"
echo "==============================================================="
echo

sudo -v

"$ORIGINAL"
