#!/usr/bin/env bash
set -Eeuo pipefail

clear

echo "==============================================================="
echo " PINCABOS — BATCH CONTROLS V3.1"
echo " FIX PAUSE DURANT TELEVERSEMENT + WIDGET FANTOME"
echo " AUCUN PUSH GITHUB"
echo "==============================================================="
echo

REPO="/opt/pincabos/tmp/pr-integration"
WEB="$REPO/opt/pincabos/web"

DASH_REL="opt/pincabos/web/pincabos_dashboard_lobby.py"
IMPORT_REL="opt/pincabos/web/pincabos_batch_import_live.py"
STATIC_REL="opt/pincabos/web/static/pincabos-system-message-tray-v1.js"

DASH="$REPO/$DASH_REL"
IMPORT="$REPO/$IMPORT_REL"
STATIC="$REPO/$STATIC_REL"

LIVE_DASH="/$DASH_REL"
LIVE_IMPORT="/$IMPORT_REL"
LIVE_STATIC="/$STATIC_REL"

STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="/opt/pincabos/backups/batch-controls-v31-$STAMP"
BACKUP_BRANCH="backup/pre-batch-controls-v31-$STAMP"

fail()
{
    echo
    echo "==============================================================="
    echo " NOGO [ERREUR] $*"
    echo "==============================================================="
    exit 1
}

ok()
{
    echo "GO [OK] $*"
}

echo "=== 1. VALIDATION ROOT / GIT ==="

[ "$(id -u)" -eq 0 ] || fail "Execution root requise."
[ -d "$REPO/.git" ] || fail "Repo absent : $REPO"

cd "$REPO"

echo "Branche : $(git branch --show-current)"
echo "HEAD    : $(git rev-parse HEAD)"

[ "$(git branch --show-current)" = "pincabos-pr-integration" ] ||
    fail "Mauvaise branche."

[ -z "$(git status --porcelain)" ] ||
    fail "Git non propre."

grep -q 'PINCABOS_DASHBOARD_BATCH_CONTROLS_V3' "$DASH" ||
    fail "Dashboard Batch Controls V3 absent."

grep -q 'PINCABOS_BATCH_CONTROLS_V3' \
    "$REPO/opt/pincabos/web/pincabos_batch_import_queue_v2.py" ||
    fail "Backend Import V3 absent."

ok "Base V3 detectee et Git propre."

echo
echo "=== 2. VERIFICATION AUCUN BATCH ACTIF ==="

IMPORT_ACTIVE="$(
curl -s --max-time 5 \
    http://127.0.0.1/api/batch-import/live/active |
python3 -c '
import json,sys
try:
    d=json.load(sys.stdin)
    print(((d.get("job") or {}).get("id")) or "")
except Exception:
    print("API_ERROR")
'
)"

[ "$IMPORT_ACTIVE" != "API_ERROR" ] ||
    fail "API Import indisponible."

if [ -n "$IMPORT_ACTIVE" ]; then
    fail "Import encore actif : $IMPORT_ACTIVE"
fi

EXPORT_ACTIVE="$(
curl -s --max-time 5 \
    http://127.0.0.1/api/batch-export/live/history |
python3 -c '
import json,sys
try:
    d=json.load(sys.stdin)
    print(d.get("active_job_id") or "")
except Exception:
    print("API_ERROR")
'
)"

[ "$EXPORT_ACTIVE" != "API_ERROR" ] ||
    fail "API Export indisponible."

if [ -n "$EXPORT_ACTIVE" ]; then
    fail "Export encore actif : $EXPORT_ACTIVE"
fi

ok "Aucun Batch actif."

echo
echo "=== 3. VALIDATION STAGING / LIVE ==="

for REL in "$DASH_REL" "$IMPORT_REL"
do
    SRC="$REPO/$REL"
    DST="/$REL"

    [ -f "$SRC" ] || fail "Source absente : $SRC"
    [ -f "$DST" ] || fail "LIVE absent : $DST"

    SH="$(sha256sum "$SRC" | awk '{print $1}')"
    LH="$(sha256sum "$DST" | awk '{print $1}')"

    echo "$REL"
    echo "  staging : $SH"
    echo "  live    : $LH"

    [ "$SH" = "$LH" ] ||
        fail "Staging/LIVE different pour $REL"
done

ok "Dashboard + Import identiques staging/live."

echo
echo "=== 4. BACKUP ==="

mkdir -p "$BACKUP"

git branch "$BACKUP_BRANCH"

cp -a "$LIVE_DASH" \
    "$BACKUP/pincabos_dashboard_lobby.py.before"

cp -a "$LIVE_IMPORT" \
    "$BACKUP/pincabos_batch_import_live.py.before"

if [ -f "$LIVE_STATIC" ]; then
    cp -a "$LIVE_STATIC" \
        "$BACKUP/pincabos-system-message-tray-v1.js.before"
fi

git bundle create \
    "$BACKUP/staging-before.bundle" \
    --all

ok "Backup : $BACKUP"
ok "Branche : $BACKUP_BRANCH"

echo
echo "==============================================================="
echo " 5. PATCH SOURCE V3.1"
echo "==============================================================="

python3 - \
    "$DASH" \
    "$IMPORT" \
    "$STATIC" <<'PY'
from pathlib import Path
import re
import sys

dash = Path(sys.argv[1])
imp = Path(sys.argv[2])
static = Path(sys.argv[3])

MARKER = "PINCABOS_BATCH_PAUSE_UPLOAD_V31"


def fail(msg):
    raise SystemExit("NOGO PATCH: " + msg)


# ============================================================
# A. DASHBOARD
# ============================================================

text = dash.read_text(encoding="utf-8")

if MARKER not in text:

    old = 'const canPause = ["queued", "running"].includes(state);'
    new = (
        '/* PINCABOS_BATCH_PAUSE_UPLOAD_V31 */\n'
        '    const canPause = '
        '["uploading", "queued", "running"].includes(state);'
    )

    if text.count(old) != 1:
        fail(
            "Dashboard: canPause attendu une fois, trouve "
            + str(text.count(old))
        )

    text = text.replace(old, new, 1)

    # Le Dashboard V3 utilisait l'historique comme fallback même si
    # /active disait qu'aucun Import n'existait. Cela affichait un
    # ancien job uploading/running comme s'il etait encore actif.
    pattern = re.compile(
        r'  async function load\(kind\) \{.*?'
        r'\n  \}\n\n  function render\(kind, packet, error = ""\) \{',
        re.S,
    )

    match = pattern.search(text)

    if not match:
        fail("Dashboard: fonction load(kind) V3 introuvable")

    replacement = r'''  async function load(kind) {
    if (kind === "import") {
      const active = await json(
        "/api/batch-import/live/active"
      );

      if (active.job) {
        return {
          id: String(active.job.id || ""),
          job: active.job,
          resumable: Boolean(active.resumable),
          remaining: Number(active.remaining || 0)
        };
      }

      /*
       * PINCABOS_BATCH_IMPORT_STALE_WIDGET_V31
       *
       * /active est la source de verite pour Import.
       * Si aucun job n'est rattache mais que le dernier historique
       * porte encore un etat transitoire, il s'agit d'un etat
       * orphelin/stale et non d'un job actuellement pilotable.
       */
      const history = await json(
        "/api/batch-import/live/history"
      );

      const latest = (history.jobs || [])[0] || null;

      if (!latest) {
        return {
          id: "",
          job: null,
          resumable: false,
          remaining: 0
        };
      }

      const latestState = String(
        latest.state || ""
      ).toLowerCase();

      const staleStates = new Set([
        "uploading",
        "queued",
        "running",
        "pausing",
        "paused",
        "stopping"
      ]);

      if (staleStates.has(latestState)) {
        return {
          id: "",
          job: null,
          resumable: false,
          remaining: 0
        };
      }

      return {
        id: String(latest.id || ""),
        job: latest,
        resumable: false,
        remaining: 0
      };
    }

    const history = await json(
      api(kind, "history")
    );

    const activeId = String(
      history.active_job_id || ""
    );

    if (activeId) {
      const status = await json(
        api(
          kind,
          `status/${encodeURIComponent(activeId)}`
        )
      );

      return {
        id: activeId,
        job: status.job || null,
        resumable: Boolean(status.job?.resumable)
      };
    }

    const latest = (history.jobs || [])[0] || null;

    return {
      id: String(latest?.id || ""),
      job: latest,
      resumable: Boolean(latest?.resumable)
    };
  }

  function render(kind, packet, error = "") {'''

    text = (
        text[:match.start()]
        + replacement
        + text[match.end():]
    )

    dash.write_text(text, encoding="utf-8")

    print("GO [PATCH] Dashboard Pause uploading + stale job")
else:
    print("GO [DEJA] Dashboard V3.1")


# ============================================================
# B. IMPORT LIVE
# ============================================================

text = imp.read_text(encoding="utf-8")

if "PINCABOS_BATCH_IMPORT_UPLOAD_PAUSED_V31" not in text:

    pattern = re.compile(
        r'if str\(job\.get\("state"\)\) not in '
        r'\{([^}]*)\} or job\.get\("uploads_complete"\):'
    )

    matches = list(pattern.finditer(text))

    target = None

    for m in matches:
        values = m.group(1)
        if (
            '"uploading"' in values
            and '"running"' in values
            and '"queued"' in values
        ):
            target = m
            break

    if target is None:
        fail(
            "Import: validation des etats de _save_one_upload "
            "introuvable"
        )

    replacement = (
        '# PINCABOS_BATCH_IMPORT_UPLOAD_PAUSED_V31\n'
        '        if str(job.get("state")) not in '
        '{"uploading", "running", "queued", "paused", "pausing"} '
        'or job.get("uploads_complete"):'
    )

    text = (
        text[:target.start()]
        + replacement
        + text[target.end():]
    )

    imp.write_text(text, encoding="utf-8")

    print(
        "GO [PATCH] Upload courant accepte pendant Pause"
    )
else:
    print("GO [DEJA] Import Upload V3.1")


# ============================================================
# C. ANCIEN POLLER UNIQUE V3
# ============================================================

if static.is_file():
    text = static.read_text(
        encoding="utf-8",
        errors="replace",
    )

    old_marker = (
        "PINCABOS_BATCH_SERVICE_WIDGET_SINGLE_POLLER_V3"
    )
    disabled_marker = (
        "PINCABOS_BATCH_SERVICE_WIDGET_SINGLE_POLLER_V3_DISABLED_V31"
    )

    if old_marker in text and disabled_marker not in text:

        guard = (
            "if "
            "(window.__pcosBatchServiceWidgetSinglePollerV3) "
            "return;"
        )

        pos = text.find(guard)

        if pos < 0:
            fail(
                "Static: poller V3 present mais guard introuvable"
            )

        assignment = (
            "window.__pcosBatchServiceWidgetSinglePollerV3 "
            "= true;"
        )

        apos = text.find(assignment, pos)

        if apos < 0:
            fail(
                "Static: assignment poller V3 introuvable"
            )

        insert_at = apos + len(assignment)

        payload = (
            "\n\n  /* "
            + disabled_marker
            + " */\n"
            + "  return;"
        )

        text = (
            text[:insert_at]
            + payload
            + text[insert_at:]
        )

        static.write_text(text, encoding="utf-8")

        print(
            "GO [PATCH] Ancien poller static V3 desactive"
        )

    elif disabled_marker in text:
        print(
            "GO [DEJA] Ancien poller static deja desactive"
        )
    else:
        print(
            "INFO [ABSENT] Aucun ancien poller static V3"
        )
else:
    print(
        "INFO [ABSENT] Fichier static non present dans staging"
    )
PY

echo
echo "=== 6. VALIDATION SYNTAXE ==="

python3 -m py_compile "$DASH" ||
    fail "Syntaxe Dashboard Python"

python3 -m py_compile "$IMPORT" ||
    fail "Syntaxe Import Python"

if command -v node >/dev/null 2>&1
then
    if [ -f "$STATIC" ]; then
        node --check "$STATIC" ||
            fail "Syntaxe JS static"
    fi
fi

git diff --check ||
    fail "git diff --check"

ok "Syntaxes valides."

echo
echo "=== 7. DIFF ==="

git --no-pager diff --stat
echo

git --no-pager diff \
    -- "$DASH_REL" \
       "$IMPORT_REL" \
       "$STATIC_REL" \
    | head -260

echo
echo "=== 8. COMMIT LOCAL ==="

git add "$DASH_REL" "$IMPORT_REL"

if [ -f "$STATIC" ] &&
   ! git diff --quiet -- "$STATIC_REL"
then
    git add "$STATIC_REL"
fi

git commit \
    -m "fix(batch): pause safely during upload and ignore stale jobs"

NEW_HEAD="$(git rev-parse HEAD)"

ok "Commit local : $NEW_HEAD"
echo "GITHUB : AUCUN PUSH"

echo
echo "=== 9. DEPLOIEMENT LIVE ==="

deploy()
{
    REL="$1"
    SRC="$REPO/$REL"
    DST="/$REL"

    [ -f "$SRC" ] || fail "Source absente : $SRC"
    [ -f "$DST" ] || fail "LIVE absent : $DST"

    U="$(stat -c %u "$DST")"
    G="$(stat -c %g "$DST")"
    M="$(stat -c %a "$DST")"

    TMP="${DST}.v31.$$"

    install \
        -o "$U" \
        -g "$G" \
        -m "$M" \
        "$SRC" \
        "$TMP"

    mv -f "$TMP" "$DST"

    echo "GO [DEPLOY] $DST"
}

deploy "$DASH_REL"
deploy "$IMPORT_REL"

if [ -f "$STATIC" ] && [ -f "$LIVE_STATIC" ]
then
    deploy "$STATIC_REL"
fi

echo
echo "=== 10. VALIDATION STAGING == LIVE ==="

for REL in "$DASH_REL" "$IMPORT_REL"
do
    SH="$(sha256sum "$REPO/$REL" | awk '{print $1}')"
    LH="$(sha256sum "/$REL" | awk '{print $1}')"

    [ "$SH" = "$LH" ] ||
        fail "Mismatch $REL"

    echo "GO [OK] $REL"
done

echo
echo "=== 11. RESTART WEBAPP ==="

systemctl restart pincabos-webapp.service
sleep 3

systemctl is-active --quiet pincabos-webapp.service ||
    fail "WebApp inactive."

ok "WebApp active."

echo
echo "=== 12. VALIDATION HTTP ==="

curl -fsS \
    --max-time 10 \
    http://127.0.0.1/dashboard \
    > /tmp/pco-v31-dashboard.html

grep -q \
    'PINCABOS_BATCH_PAUSE_UPLOAD_V31' \
    /tmp/pco-v31-dashboard.html ||
    fail "Dashboard V3.1 non servi."

ok "Dashboard V3.1 servi."

echo
echo "=== 13. ETAT IMPORT REEL ==="

echo "--- /active ---"

curl -s \
    --max-time 5 \
    http://127.0.0.1/api/batch-import/live/active |
python3 -m json.tool || true

echo
echo "--- dernier historique ---"

curl -s \
    --max-time 5 \
    http://127.0.0.1/api/batch-import/live/history |
python3 -c '
import json,sys
d=json.load(sys.stdin)
j=(d.get("jobs") or [None])[0]

if not j:
    print("Aucun historique.")
else:
    print("id        :", j.get("id"))
    print("state     :", j.get("state"))
    print("uploaded  :", j.get("uploaded_archives"))
    print("processed :", j.get("processed_archives"))
    print("current   :", j.get("current_item"))
    print("error     :", j.get("error"))
'

echo
echo "=== 14. GIT FINAL ==="

cd "$REPO"

echo "Branche : $(git branch --show-current)"
echo "HEAD    : $(git rev-parse HEAD)"

[ -z "$(git status --porcelain)" ] ||
    fail "Git non propre."

ok "Git propre."

echo
echo "==============================================================="
echo " GO [OK] BATCH PAUSE V3.1 INSTALLE"
echo "==============================================================="
echo
echo "Pause pendant Upload : GO"
echo "Upload courant finit proprement : GO"
echo "Traitement suivant bloque en Pause : GO"
echo "Widget fantome sans /active : CORRIGE"
echo "Ancien poller concurrent : DESACTIVE SI PRESENT"
echo
echo "Backup : $BACKUP"
echo "HEAD   : $NEW_HEAD"
echo
echo "GITHUB : PAS ENCORE PUSH"
echo
echo "==============================================================="
