#!/usr/bin/env bash
set -Eeuo pipefail
# PINCABOS_HYBRID_REMOTE_AUDIT_TEST_V1

clear 2>/dev/null || true
ACTION="${1:---test}"
TABLE_OVERRIDE="${2:-}"
TABLES_ROOT="/home/pinball/Tables"
LAUNCHER_DIR="/opt/pincabos/launchers"
DETECTOR="${LAUNCHER_DIR}/pincabos-detect-table-modes.py"
HYBRID="${LAUNCHER_DIR}/pincabos-launch-hybrid.sh"
ORIGINAL="${LAUNCHER_DIR}/pincabos-launch-original.sh"
PUP="${LAUNCHER_DIR}/pincabos-launch-puppack.sh"
PUBLIC="/opt/pincabos/scripts/VPXlauncher.sh"
CORE="${LAUNCHER_DIR}/pincabos-launch-core.sh"
HELPER="/usr/local/sbin/pincabos-hybrid-pup-mode"
STAMP="$(date +%Y%m%d-%H%M%S)"
REPORT="/root/pincabos-hybrid-remote-audit-test-${STAMP}.txt"
JSON_REPORT="/root/pincabos-hybrid-table-scan-${STAMP}.jsonl"
TSV_REPORT="/root/pincabos-hybrid-table-scan-${STAMP}.tsv"
WORK="/var/tmp/pincabos-hybrid-remote-test-${STAMP}"
MOCK="${WORK}/mock-vpx-launcher.sh"
MOCK_LOG="${WORK}/mock-vpx-launcher.log"
SELECTED_ENV="${WORK}/selected.env"
TEST_FAILURES=0

[[ "$EUID" -eq 0 ]] || { echo "NOGO [X] Exécute ce script comme root."; exit 1; }
mkdir -p "$WORK"
exec > >(tee -a "$REPORT") 2>&1

headline() {
    printf '\n===============================================================\n %s\n===============================================================\n' "$1"
}

go() { echo "GO [√] $*"; }
warn() { echo "AVERTISSEMENT [!] $*"; }
fail() { echo "NOGO [X] $*"; TEST_FAILURES=$((TEST_FAILURES + 1)); }

cleanup() {
    set +e
    if [[ -x "$HELPER" ]]; then
        "$HELPER" show >/dev/null 2>&1 || "$HELPER" recover >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT INT TERM HUP

require_file() {
    local path="$1"
    if [[ -x "$path" ]]; then
        go "$path"
    else
        fail "Fichier absent ou non exécutable : $path"
    fi
}

headline "PINCABOS — AUDIT ET TEST DISTANT DU LAUNCHER HYBRIDE"
echo "Date        : $(date -Is)"
echo "Action      : $ACTION"
echo "Rapport     : $REPORT"
echo "Scan JSONL  : $JSON_REPORT"
echo "Scan TSV    : $TSV_REPORT"
echo "Important   : aucun VPX réel ne sera lancé; un faux launcher est utilisé."

case "$ACTION" in
    --scan-only|--test) ;;
    *)
        echo "Usage : $0 --scan-only [TABLE.vpx] | --test [TABLE.vpx]"
        exit 64
        ;;
esac

headline "1. VALIDATION DU SYSTÈME"
require_file "$DETECTOR"
require_file "$HYBRID"
require_file "$ORIGINAL"
require_file "$PUP"
require_file "$PUBLIC"
require_file "$CORE"
require_file "$HELPER"

if grep -q 'PINCABOS_HYBRID_LAUNCH_CORE_V3_2' "$CORE" 2>/dev/null; then
    go "Core V3.2 détecté."
else
    fail "Le core V3.2 n'est pas installé. Installe d'abord le package V3.2."
fi
if grep -q 'PINCABOS_HYBRID_FORCE_CHOICE' "$CORE" 2>/dev/null; then
    go "Sélection forcée par script disponible."
else
    fail "Support PINCABOS_HYBRID_FORCE_CHOICE absent."
fi

bash -n "$CORE" "$HYBRID" "$ORIGINAL" "$PUP" "$PUBLIC" "$HELPER" \
    && go "Syntaxe Bash valide." \
    || fail "Erreur de syntaxe Bash."
python3 -m py_compile "$DETECTOR" \
    && go "Détecteur Python compilable." \
    || fail "Détecteur Python invalide."

if (( TEST_FAILURES > 0 )); then
    echo
    echo "NOGO [X] Prévalidation échouée : $TEST_FAILURES erreur(s)."
    exit 2
fi

if pgrep -af '(^|/)(VPinballX|VPinballX_BGFX|vpinball)([[:space:]]|$)' >/tmp/pincabos-vpx-running.$$ 2>/dev/null; then
    cat /tmp/pincabos-vpx-running.$$
    rm -f /tmp/pincabos-vpx-running.$$
    echo "NOGO [X] VPX semble actif. Ferme la table avant ce test afin de ne pas renommer un PuP-Pack en cours d'utilisation."
    exit 3
fi
rm -f /tmp/pincabos-vpx-running.$$
go "Aucun processus VPX actif."

"$HELPER" recover || true
if "$HELPER" status | grep -q '^STATE=clean$'; then
    go "État du helper PuP propre."
else
    fail "Le helper PuP conserve encore un état masqué."
    "$HELPER" status || true
fi

headline "2. RECHERCHE DES TABLES HYBRIDES"

python3 - "$DETECTOR" "$TABLES_ROOT" "$JSON_REPORT" "$TSV_REPORT" "$SELECTED_ENV" "$TABLE_OVERRIDE" <<'PY'
from __future__ import annotations
import importlib.util
import json
import os
import shlex
import sys
from pathlib import Path

path_detector = Path(sys.argv[1])
root = Path(sys.argv[2])
json_path = Path(sys.argv[3])
tsv_path = Path(sys.argv[4])
selected_env = Path(sys.argv[5])
override = sys.argv[6].strip()

spec = importlib.util.spec_from_file_location("pincabos_detector", path_detector)
if spec is None or spec.loader is None:
    raise SystemExit("Impossible de charger le détecteur")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Cache l'index des ROM globales pendant tout le scan des centaines de tables.
if hasattr(mod, "zip_index"):
    original_zip_index = mod.zip_index
    cache: dict[str, dict[str, Path]] = {}
    def cached_zip_index(directory: Path):
        key = str(directory)
        if key not in cache:
            cache[key] = original_zip_index(directory)
        return cache[key]
    mod.zip_index = cached_zip_index

def all_tables(folder: Path):
    for current, dirs, files in os.walk(folder):
        dirs.sort(key=str.casefold)
        for name in sorted(files, key=str.casefold):
            if name.casefold().endswith(".vpx"):
                yield Path(current) / name

def score(data: dict) -> int:
    value = 0
    if data.get("original_available") and data.get("pup_available"):
        value += 1000
    value += min(100, len(data.get("rom_files") or []) * 25)
    value += 80 if data.get("directb2s") else 0
    value += min(60, len(data.get("pup_packs") or []) * 10)
    cfg = Path(str(data.get("config") or ""))
    value += 10 if cfg.is_file() else 0
    return value

if override:
    candidates = [Path(override).expanduser()]
else:
    candidates = list(all_tables(root))

results: list[dict] = []
errors: list[dict] = []
total = len(candidates)
print(f"Tables VPX à analyser : {total}", flush=True)

for index, table in enumerate(candidates, 1):
    try:
        data = mod.detect(str(table))
        data["audit_score"] = score(data)
        results.append(data)
    except BaseException as exc:
        errors.append({"table": str(table), "error": str(exc)})
    if index == 1 or index % 25 == 0 or index == total:
        print(f"Progression : {index}/{total}", flush=True)

results.sort(key=lambda d: (-int(d.get("audit_score", 0)), str(d.get("table", "")).casefold()))

with json_path.open("w", encoding="utf-8") as handle:
    for item in results:
        handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    for item in errors:
        handle.write(json.dumps({"ok": False, **item}, ensure_ascii=False) + "\n")

with tsv_path.open("w", encoding="utf-8") as handle:
    handle.write("mode\tscore\ttable\tpup_root\troms\tdirectb2s\tconfig\n")
    for item in results:
        mode = item.get("detected_mode")
        if not mode:
            mode = "hybrid" if item.get("original_available") and item.get("pup_available") else ("pup" if item.get("pup_available") else "original")
        row = [
            str(mode),
            str(item.get("audit_score", 0)),
            str(item.get("table", "")),
            str(item.get("pup_root", "")),
            str(len(item.get("rom_files") or [])),
            str(item.get("directb2s", "")),
            str(item.get("config", "")),
        ]
        handle.write("\t".join(v.replace("\t", " ").replace("\n", " ") for v in row) + "\n")

hybrids = [r for r in results if r.get("original_available") and r.get("pup_available") and r.get("pup_root")]
originals = [r for r in results if r.get("original_available") and not r.get("pup_available")]
pups = [r for r in results if r.get("pup_available") and not r.get("original_available")]
print(f"Détection : hybrides={len(hybrids)} original={len(originals)} pup-seulement={len(pups)} erreurs={len(errors)}")

selected = hybrids[0] if hybrids else None
with selected_env.open("w", encoding="utf-8") as handle:
    if selected:
        values = {
            "SELECTED_TABLE": str(selected["table"]),
            "SELECTED_PUP_ROOT": str(selected["pup_root"]),
            "SELECTED_B2S": str(selected.get("directb2s") or ""),
            "SELECTED_ROMS": "\n".join(selected.get("rom_files") or []),
            "SELECTED_PACKS": "\n".join(selected.get("pup_packs") or []),
            "SELECTED_SCORE": str(selected.get("audit_score", 0)),
        }
        for key, value in values.items():
            handle.write(f"{key}={shlex.quote(value)}\n")
PY

[[ -f "$SELECTED_ENV" ]] || { echo "NOGO [X] Résultat de sélection absent."; exit 4; }
# shellcheck disable=SC1090
source "$SELECTED_ENV"

HYBRID_COUNT="$(awk -F '\t' 'NR>1 && $1=="hybrid"{n++} END{print n+0}' "$TSV_REPORT")"
ORIGINAL_COUNT="$(awk -F '\t' 'NR>1 && $1=="original"{n++} END{print n+0}' "$TSV_REPORT")"
PUP_COUNT="$(awk -F '\t' 'NR>1 && $1=="pup"{n++} END{print n+0}' "$TSV_REPORT")"

echo
echo "Résumé du scan :"
echo "  Tables hybrides       : $HYBRID_COUNT"
echo "  Tables Original       : $ORIGINAL_COUNT"
echo "  Tables PuP seulement  : $PUP_COUNT"

echo
echo "Premières tables hybrides détectées :"
if command -v column >/dev/null 2>&1; then
    awk -F '\t' 'NR==1 || $1=="hybrid"' "$TSV_REPORT" | head -n 11 | column -t -s $'\t'
else
    awk -F '\t' 'NR==1 || $1=="hybrid" {print $1 " | " $2 " | " $3}' "$TSV_REPORT" | head -n 11
fi

if [[ -z "${SELECTED_TABLE:-}" ]]; then
    echo "NOGO [X] Aucune table hybride confirmée par le détecteur."
    echo "Consulte : $TSV_REPORT"
    exit 10
fi

go "Table hybride choisie : $SELECTED_TABLE"
echo "Score       : $SELECTED_SCORE"
echo "PuP root    : $SELECTED_PUP_ROOT"
[[ -n "${SELECTED_B2S:-}" ]] && echo "directB2S   : $SELECTED_B2S"
[[ -n "${SELECTED_ROMS:-}" ]] && printf 'ROM(s)      :\n%s\n' "$SELECTED_ROMS"
[[ -n "${SELECTED_PACKS:-}" ]] && printf 'PuP-Pack(s) :\n%s\n' "$SELECTED_PACKS"

echo
echo "Détection JSON complète de la table choisie :"
python3 "$DETECTOR" "$SELECTED_TABLE"

if [[ "$ACTION" == "--scan-only" ]]; then
    headline "SCAN TERMINÉ"
    echo "Aucun launcher exécuté."
    echo "Rapport : $REPORT"
    exit 0
fi

headline "3. PRÉPARATION DU FAUX LAUNCHER VPX"
cat > "$MOCK" <<'MOCK'
#!/usr/bin/env bash
set -Eeuo pipefail
{
    echo "BEGIN_MOCK"
    echo "CHOICE=${PINCABOS_GAME_CHOICE:-ABSENT}"
    echo "PUP_ENABLED=${PINCABOS_PUP_ENABLED:-ABSENT}"
    echo "TABLE_EXPECTED=${PINCABOS_TEST_TABLE:-ABSENT}"
    active="${PINCABOS_TEST_PUP_ROOT:-}"
    hidden="${active}.__pincabos_original_disabled__"
    [[ -n "$active" && -d "$active" ]] && echo "PUP_ACTIVE=1" || echo "PUP_ACTIVE=0"
    [[ -n "$active" && -d "$hidden" ]] && echo "PUP_HIDDEN=1" || echo "PUP_HIDDEN=0"
    printf 'ARG=%q\n' "$@"
    echo "END_MOCK"
} >> "${PINCABOS_TEST_MOCK_LOG:?}"
exit 0
MOCK
chmod 0755 "$MOCK"
go "Faux launcher créé : $MOCK"

test_one() {
    local label="$1" expected_choice="$2" expected_enabled="$3" command_path="$4"
    shift 4
    : > "$MOCK_LOG"
    echo
    echo "--- TEST : $label ---"
    set +e
    env \
        PINCABOS_REAL_LAUNCHER="$MOCK" \
        PINCABOS_TEST_MOCK_LOG="$MOCK_LOG" \
        PINCABOS_TEST_TABLE="$SELECTED_TABLE" \
        PINCABOS_TEST_PUP_ROOT="$SELECTED_PUP_ROOT" \
        "$@" \
        "$command_path" "$SELECTED_TABLE"
    local rc=$?
    set -e

    cat "$MOCK_LOG" 2>/dev/null || true
    if [[ "$rc" -ne 0 ]]; then
        fail "$label : code retour $rc"
        return
    fi
    grep -q "^CHOICE=${expected_choice}$" "$MOCK_LOG" \
        && go "$label : choix transmis = $expected_choice" \
        || fail "$label : choix attendu $expected_choice non reçu"
    grep -q "^PUP_ENABLED=${expected_enabled}$" "$MOCK_LOG" \
        && go "$label : PINCABOS_PUP_ENABLED=$expected_enabled" \
        || fail "$label : PINCABOS_PUP_ENABLED incorrect"
    grep -Fq "ARG=$(printf '%q' "$SELECTED_TABLE")" "$MOCK_LOG" \
        && go "$label : chemin de table transmis intégralement" \
        || fail "$label : chemin de table absent ou altéré"

    if [[ "$expected_choice" == "original" ]]; then
        grep -q '^PUP_ACTIVE=0$' "$MOCK_LOG" \
            && grep -q '^PUP_HIDDEN=1$' "$MOCK_LOG" \
            && go "$label : PuP-Pack réellement masqué pendant l'appel" \
            || fail "$label : PuP-Pack non masqué pendant l'appel Original"
    else
        grep -q '^PUP_ACTIVE=1$' "$MOCK_LOG" \
            && grep -q '^PUP_HIDDEN=0$' "$MOCK_LOG" \
            && go "$label : PuP-Pack actif pendant l'appel" \
            || fail "$label : PuP-Pack non actif pendant l'appel PuP"
    fi

    if [[ -d "$SELECTED_PUP_ROOT" && ! -e "${SELECTED_PUP_ROOT}.__pincabos_original_disabled__" ]]; then
        go "$label : état PuP restauré après le test"
    else
        fail "$label : état PuP non restauré après le test"
        "$HELPER" show || true
    fi
}

headline "4. TESTS DES LAUNCHERS — SANS DÉMARRER VPX"

test_one "Launcher Original direct" original 0 "$ORIGINAL"
test_one "Launcher PuP-Pack direct" pup 1 "$PUP"
test_one "Launcher Hybride — choix Original forcé par script" original 0 "$HYBRID" PINCABOS_HYBRID_FORCE_CHOICE=original
test_one "Launcher Hybride — choix PuP forcé par script" pup 1 "$HYBRID" PINCABOS_HYBRID_FORCE_CHOICE=pup
test_one "Chemin exact VPinFE — choix Original forcé" original 0 "$PUBLIC" PINCABOS_HYBRID_FORCE_CHOICE=original
test_one "Chemin exact VPinFE — choix PuP forcé" pup 1 "$PUBLIC" PINCABOS_HYBRID_FORCE_CHOICE=pup

headline "5. VALIDATION FINALE"
"$HELPER" show || true
if [[ -d "$SELECTED_PUP_ROOT" && ! -e "${SELECTED_PUP_ROOT}.__pincabos_original_disabled__" ]]; then
    go "Le dossier PuP-Pack est actif et restauré."
else
    fail "État final du PuP-Pack incorrect."
fi

if "$HELPER" status | grep -q '^STATE=clean$'; then
    go "Le helper ne conserve aucun état résiduel."
else
    fail "État résiduel détecté dans le helper."
    "$HELPER" status || true
fi

if (( TEST_FAILURES == 0 )); then
    echo
    echo "GO [√] TOUS LES TESTS DISTANTS ONT RÉUSSI."
    echo "GO [√] Le launcher réel VPX n'a jamais été exécuté."
    echo "GO [√] Les choix Original et PuP ont été simulés par le script."
    echo "INFO [=] Ce test valide la logique des launchers et le masquage/restauration PuP."
    echo "INFO [=] Il ne valide pas physiquement les numéros de boutons du pincab."
    RC=0
else
    echo
    echo "NOGO [X] $TEST_FAILURES test(s) ont échoué."
    RC=20
fi

echo
echo "Rapport complet : $REPORT"
echo "Inventaire JSON : $JSON_REPORT"
echo "Inventaire TSV  : $TSV_REPORT"
exit "$RC"
