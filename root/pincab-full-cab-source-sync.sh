#!/usr/bin/env bash
set -Eeuo pipefail

clear

echo "==============================================================="
echo " PINCABOS — FULL CAB SOURCE SYNC"
echo " LIVE CAB -> REPO -> GITHUB MAIN"
echo " PINCAB RECORDER + SERVICES + FIXES LIVE"
echo "==============================================================="
echo

REPO="/opt/pincabos/tmp/pr-integration"
BRANCH="pincabos-pr-integration"
EXPECTED_HEAD="0f1a4a3c35a798aac12c7e8c2e77f290cffe09aa"

STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_LOCAL="backup/pre-full-cab-source-sync-$STAMP"
BACKUP_REMOTE="backup-main-before-full-cab-sync-$STAMP"
BACKUP_DIR="/opt/pincabos/backups/full-cab-source-sync-$STAMP"

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

[ "$(id -u)" -eq 0 ] ||
    fail "Root requis."

[ -d "$REPO/.git" ] ||
    fail "Repo absent."

cd "$REPO"

echo "=== 1. VALIDATION GIT ==="

CUR_BRANCH="$(git branch --show-current)"
CUR_HEAD="$(git rev-parse HEAD)"

echo "Branche : $CUR_BRANCH"
echo "HEAD    : $CUR_HEAD"

[ "$CUR_BRANCH" = "$BRANCH" ] ||
    fail "Mauvaise branche."

[ "$CUR_HEAD" = "$EXPECTED_HEAD" ] ||
    fail "HEAD inattendu. Audit requis avant sync."

[ -z "$(git status --porcelain)" ] ||
    fail "Working tree non propre."

ok "Repo local propre."

echo
echo "=== 2. VALIDATION GITHUB ==="

gh auth status >/dev/null 2>&1 ||
    fail "GitHub CLI non authentifie."

git fetch --prune origin

REMOTE_MAIN="$(git rev-parse refs/remotes/origin/main)"

echo "Local       : $CUR_HEAD"
echo "GitHub main : $REMOTE_MAIN"

[ "$REMOTE_MAIN" = "$CUR_HEAD" ] ||
    fail "GitHub main a change depuis le dernier push."

ok "Local == GitHub main."

echo
echo "=== 3. BACKUPS ==="

mkdir -p "$BACKUP_DIR"

git branch "$BACKUP_LOCAL"

git push \
    origin \
    "$REMOTE_MAIN:refs/heads/$BACKUP_REMOTE"

printf '%s\n' "$CUR_HEAD" \
    > "$BACKUP_DIR/head-before.txt"

git status --porcelain \
    > "$BACKUP_DIR/status-before.txt"

ok "Backup local  : $BACKUP_LOCAL"
ok "Backup GitHub : $BACKUP_REMOTE"
ok "Backup audit  : $BACKUP_DIR"

echo
echo "==============================================================="
echo " 4. SYNCHRONISATION DES SOURCES LIVE"
echo "==============================================================="

FILES=(
    "/opt/pincabos/web/recorder.py"
    "/opt/pincabos/web/pincabos_media_recorder.py"
    "/opt/pincabos/web/pincabos_media_recorder_worker.py"
    "/opt/pincabos/web/static/pincabos-assets/PCOSRecorder.png"

    "/opt/pincabos/web/tools.py"

    "/opt/pincabos/bin/pincabos-native-b2s-scoreview-prelaunch.sh"

    "/opt/pincabos/config/github-rootfs-exclude.txt"

    "/etc/systemd/system/pincabos-media-recorder-worker.service"
    "/etc/systemd/system/pincabos-firstboot-network-webapp-fix.service"
    "/etc/systemd/system/pincabos-firstboot-vpinfe-packaged-runtime-fix.service"
    "/etc/systemd/system/pincabos-firstboot-identity.service"
    "/etc/systemd/system/pincabos-firstboot-hardware-autoconfig.service"
    "/etc/systemd/system/pincabos-firstboot-initramfs-refresh.service"
    "/etc/systemd/system/pincabos-webapp-fallback.service"
    "/etc/systemd/system/pincabos-screen-topology-boot.service"

    "/usr/local/sbin/pincabos-firstboot-initramfs-refresh"
    "/usr/local/sbin/pincabos-firstboot-vpinfe-packaged-runtime-fix"
    "/usr/local/sbin/pincabos-firstboot-network-webapp-fix"
    "/usr/local/sbin/pincabos-webapp-fallback-start"
    "/usr/local/sbin/pincabos-firstboot-hardware-autoconfig"

    "/usr/local/sbin/pincabos-fix-backups-logs-perms"
    "/usr/local/sbin/pincabos-dashboard-admin"
)

RELS=()

for SRC in "${FILES[@]}"
do
    [ -e "$SRC" ] ||
        fail "Fichier live absent : $SRC"

    REL="${SRC#/}"
    DST="$REPO/$REL"

    mkdir -p "$(dirname "$DST")"

    cp -a \
        --remove-destination \
        "$SRC" \
        "$DST"

    RELS+=("$REL")

    echo "GO [SYNC] $REL"
done

echo
echo "=== 5. VERIFICATION DES EXCLUSIONS PRIVEES ==="

FORBIDDEN=(
    "opt/pincabos/config/webapp-secret.key"
    "opt/pincabos/config/screens/screens.json"
    "opt/pincabos/config/screens/wallpapers.json"
    "opt/pincabos/config/screens/display-role-bindings.json"
    "opt/pincabos/config/webapp-appearance/active.json"
)

for REL in "${FORBIDDEN[@]}"
do
    if git status --porcelain -- "$REL" | grep -q .
    then
        fail "Fichier prive/config cab modifie : $REL"
    fi
done

ok "Aucune configuration privee du cab incluse."

echo
echo "=== 6. AJOUT GIT CIBLE ==="

git add -- "${RELS[@]}"

git diff --cached --name-only \
    > "$BACKUP_DIR/staged-files.txt"

echo
cat "$BACKUP_DIR/staged-files.txt"

[ -s "$BACKUP_DIR/staged-files.txt" ] ||
    fail "Aucune modification detectee."

echo
echo "=== 7. GARDE-FOU VENV / BACKUP / CACHE ==="

if git diff --cached --name-only |
    grep -E \
    '(^|/)(venv|\.venv|__pycache__|backups|logs)(/|$)|\.pyc$|\.bak($|-)'
then
    fail "Un fichier runtime/backup a ete stage."
fi

ok "Aucun venv/cache/backup stage."

echo
echo "==============================================================="
echo " 8. SCAN SECRETS AVANT PUBLICATION"
echo "==============================================================="

git diff --cached --name-only -z \
    > "$BACKUP_DIR/staged-files.z"

python3 - "$REPO" "$BACKUP_DIR/staged-files.z" <<'PY'
from pathlib import Path
import re
import sys

repo = Path(sys.argv[1])
names = Path(sys.argv[2]).read_bytes().split(b"\0")

patterns = [
    (
        "GitHub token",
        re.compile(
            rb"\bgh[opusr]_[A-Za-z0-9]{20,}\b"
        ),
    ),
    (
        "GitHub PAT",
        re.compile(
            rb"\bgithub_pat_[A-Za-z0-9_]{20,}\b"
        ),
    ),
    (
        "Private key",
        re.compile(
            rb"-----BEGIN (?:OPENSSH |RSA |EC |DSA )?"
            rb"PRIVATE KEY-----"
        ),
    ),
    (
        "AWS access key",
        re.compile(
            rb"\bAKIA[A-Z0-9]{16}\b"
        ),
    ),
    (
        "Credential URL",
        re.compile(
            rb"://[^/\s:@]+:[^@\s/]+@"
        ),
    ),
]

assignment = re.compile(
    rb"""(?ix)
    \b(
        password |
        passwd |
        secret |
        token |
        api[_-]?key
    )\b
    \s*[:=]\s*
    ["']
    ([^"'\r\n]{6,})
    ["']
    """
)

issues = []

for raw in names:
    if not raw:
        continue

    rel = raw.decode("utf-8", "replace")
    path = repo / rel

    if not path.is_file():
        continue

    data = path.read_bytes()

    if b"\0" in data[:4096]:
        continue

    for label, pattern in patterns:
        if pattern.search(data):
            issues.append(
                (rel, label, None)
            )

    for number, line in enumerate(
        data.splitlines(),
        1,
    ):
        match = assignment.search(line)

        if not match:
            continue

        key = match.group(1).decode(
            "utf-8",
            "replace",
        )

        value = match.group(2).decode(
            "utf-8",
            "replace",
        )

        harmless = {
            "",
            "none",
            "null",
            "example",
            "placeholder",
            "changeme",
            "change-me",
        }

        if value.lower() in harmless:
            continue

        issues.append(
            (
                rel,
                f"literal {key}",
                number,
            )
        )

if issues:
    print()
    print(
        "NOGO : secret/credential potentiel "
        "dans les fichiers a publier:"
    )

    for rel, kind, line in issues:
        if line:
            print(
                f"  {rel}:{line} -> {kind} [VALEUR MASQUEE]"
            )
        else:
            print(
                f"  {rel} -> {kind} [VALEUR MASQUEE]"
            )

    raise SystemExit(2)

print("GO [OK] Aucun secret evident detecte.")
PY

echo
echo "=== 9. VALIDATION PYTHON ==="

for REL in \
    opt/pincabos/web/recorder.py \
    opt/pincabos/web/pincabos_media_recorder.py \
    opt/pincabos/web/pincabos_media_recorder_worker.py \
    opt/pincabos/web/tools.py
do
    python3 -m py_compile "$REPO/$REL" ||
        fail "Syntaxe Python : $REL"

    echo "GO [OK] $REL"
done

echo
echo "=== 10. VALIDATION RECORDER COMPLET ==="

for REL in \
    opt/pincabos/web/recorder.py \
    opt/pincabos/web/pincabos_media_recorder.py \
    opt/pincabos/web/pincabos_media_recorder_worker.py \
    opt/pincabos/web/static/pincabos-assets/PCOSRecorder.png \
    etc/systemd/system/pincabos-media-recorder-worker.service
do
    [ -e "$REPO/$REL" ] ||
        fail "Recorder incomplet : $REL"

    git ls-files --error-unmatch "$REL" >/dev/null ||
        fail "Recorder non suivi par Git : $REL"

    echo "GO [OK] $REL"
done

echo
echo "=== 11. DIFF FINAL AVANT COMMIT ==="

git diff --cached --stat

echo
git diff --cached --name-status

echo
echo "=== 12. COMMIT LOCAL ==="

git commit \
    -m "sync(cab): publish complete live PinCabOS source"

NEW_HEAD="$(git rev-parse HEAD)"

ok "Nouveau HEAD : $NEW_HEAD"

echo
echo "==============================================================="
echo " 13. PUSH GITHUB MAIN"
echo "==============================================================="

git push \
    origin \
    HEAD:refs/heads/main

ok "Push main termine."

echo
echo "=== 14. VERIFICATION GITHUB ==="

git fetch origin main

REMOTE_AFTER="$(
    git rev-parse refs/remotes/origin/main
)"

echo "Local       : $NEW_HEAD"
echo "GitHub main : $REMOTE_AFTER"

[ "$REMOTE_AFTER" = "$NEW_HEAD" ] ||
    fail "GitHub main != local."

ok "GitHub main == local."

echo
echo "=== 15. VERIFICATION PINCAB RECORDER SUR GITHUB ==="

RECORDER_LIST="$(
    git ls-tree \
        -r \
        --name-only \
        origin/main |
    grep -Ei \
        '(^|/)(recorder\.py|pincabos_media_recorder|PCOSRecorder|pincabos-media-recorder-worker)' \
        || true
)"

echo "$RECORDER_LIST"

echo "$RECORDER_LIST" |
    grep -q 'pincabos_media_recorder.py' ||
    fail "Recorder Web absent de GitHub."

echo "$RECORDER_LIST" |
    grep -q 'pincabos_media_recorder_worker.py' ||
    fail "Recorder Worker absent de GitHub."

echo "$RECORDER_LIST" |
    grep -q 'PCOSRecorder.png' ||
    fail "Image Recorder absente de GitHub."

echo "$RECORDER_LIST" |
    grep -q 'pincabos-media-recorder-worker.service' ||
    fail "Service Recorder absent de GitHub."

ok "PinCab Recorder complet sur GitHub."

echo
echo "=== 16. ETAT FINAL ==="

git status --short

[ -z "$(git status --porcelain)" ] ||
    fail "Git local non propre."

echo
echo "==============================================================="
echo " GO [OK] FULL CAB SOURCE PUBLIE SUR GITHUB"
echo "==============================================================="
echo
echo "Ancien HEAD : $CUR_HEAD"
echo "Nouveau HEAD: $NEW_HEAD"
echo
echo "Backup GitHub:"
echo "  $BACKUP_REMOTE"
echo
echo "Backup local:"
echo "  $BACKUP_LOCAL"
echo
echo "PinCab Recorder:"
echo "  Web       [OK]"
echo "  Worker    [OK]"
echo "  Image     [OK]"
echo "  systemd   [OK]"
echo
echo "EXCLUS VOLONTAIRES:"
echo "  secrets / webapp-secret.key"
echo "  configs ecrans propres au cab"
echo "  active appearance propre au cab"
echo "  venv / .venv"
echo "  __pycache__ / pyc"
echo "  backups / *.bak"
echo "  logs / runtime"
echo "  Tables / ROM / medias utilisateur"
echo
echo "==============================================================="
