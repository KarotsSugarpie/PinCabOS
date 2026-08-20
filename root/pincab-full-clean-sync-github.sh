#!/usr/bin/env bash
set -Eeuo pipefail

clear

echo "==============================================================="
echo " PINCABOS — CLEAN + FULL CAB SOURCE SYNC"
echo " MENAGE LOGS / DEAD / BACKUPS"
echo " CAB -> STAGING -> GITHUB MAIN"
echo "==============================================================="
echo

REPO="/opt/pincabos/tmp/pr-integration"
BRANCH="pincabos-pr-integration"

STAMP="$(date +%Y%m%d-%H%M%S)"
SAFETY="/root/pincabos-final-safety-$STAMP"
REPORT="/root/pincabos-full-sync-$STAMP"

mkdir -p "$SAFETY" "$REPORT"

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
    fail "Repo absent : $REPO"

cd "$REPO"

echo "=== 1. VALIDATION GIT ==="

CUR_BRANCH="$(git branch --show-current)"
BASE_HEAD="$(git rev-parse HEAD)"

echo "Branche : $CUR_BRANCH"
echo "HEAD    : $BASE_HEAD"

[ "$CUR_BRANCH" = "$BRANCH" ] ||
    fail "Mauvaise branche."

[ -z "$(git status --porcelain)" ] ||
    fail "Repo local non propre."

gh auth status >/dev/null 2>&1 ||
    fail "GitHub CLI non authentifie."

git fetch --prune origin

REMOTE_HEAD="$(git rev-parse refs/remotes/origin/main)"

echo "Local       : $BASE_HEAD"
echo "GitHub main : $REMOTE_HEAD"

[ "$REMOTE_HEAD" = "$BASE_HEAD" ] ||
    fail "Local != GitHub main."

ok "Base Git locale/GitHub identique."

echo
echo "=== 2. GARDE VPX ==="

if pgrep -af 'VPinballX|VPinballX_BGFX' \
    > "$REPORT/vpx-active.txt"
then
    cat "$REPORT/vpx-active.txt"
    fail "VPX actif. Ferme la table avant le sync."
fi

ok "Aucune table VPX active."

echo
echo "=== 3. GARDE BATCH ==="

check_batch()
{
    local URL="$1"
    local LABEL="$2"
    local JSON

    JSON="$(
        curl \
            -fsS \
            --max-time 4 \
            "$URL" \
            2>/dev/null \
            || true
    )"

    [ -n "$JSON" ] || return 0

    if ! python3 -c '
import json,sys

try:
    data=json.load(sys.stdin)
except Exception:
    raise SystemExit(0)

job=data.get("job")

if not isinstance(job,dict):
    raise SystemExit(0)

state=str(job.get("state","")).lower()

busy={
    "queued",
    "uploading",
    "running",
    "processing",
    "pausing",
    "stopping",
}

raise SystemExit(
    1 if state in busy else 0
)
' <<< "$JSON"
    then
        echo "$JSON"
        fail "$LABEL actif."
    fi
}

check_batch \
    "http://127.0.0.1/api/batch-import/live/active" \
    "Batch Import"

check_batch \
    "http://127.0.0.1/api/batch-export/live/active" \
    "Batch Export"

ok "Aucun Batch actif."

echo
echo "==============================================================="
echo " 4. BACKUP D'URGENCE AVANT MENAGE"
echo "==============================================================="

git bundle create \
    "$SAFETY/repository-before-clean.bundle" \
    --all

git status --short \
    > "$SAFETY/git-status.txt"

git log \
    -30 \
    --oneline \
    --decorate \
    > "$SAFETY/git-history.txt"

printf '%s\n' "$BASE_HEAD" \
    > "$SAFETY/github-main-before.txt"

ok "Bundle : $SAFETY/repository-before-clean.bundle"

echo
echo "=== 5. AUDIT ESPACE AVANT MENAGE ==="

for P in \
    /opt/pincabos/backups \
    /opt/pincabos/logs \
    /opt/pincabos/web/backups \
    /home/pinball/.local/share/pincabos/editor-backups \
    /var/crash
do
    if [ -e "$P" ]
    then
        du -sh "$P" 2>/dev/null || true
    fi
done

df -h / /opt/pincabos

echo
echo "=== 6. AUDIT LIENS MORTS ==="

{
    find /opt/pincabos \
        -path '/opt/pincabos/tmp' -prune -o \
        -xtype l \
        -print \
        2>/dev/null || true

    find \
        /usr/local/bin \
        /usr/local/sbin \
        /usr/local/libexec \
        /etc/systemd/system \
        -xtype l \
        -name 'pincabos*' \
        -print \
        2>/dev/null || true
} | sort -u |
tee "$REPORT/dead-links.txt"

echo
echo "==============================================================="
echo " 7. MENAGE BACKUPS PINCABOS"
echo "==============================================================="

clean_directory_contents()
{
    local DIR="$1"

    [ -d "$DIR" ] || return 0

    echo "CLEAN $DIR"

    find "$DIR" \
        -mindepth 1 \
        -maxdepth 1 \
        -exec rm -rf -- {} +
}

#
# Backups de maintenance PinCabOS.
# Le bundle de securite reste dans /root.
#

clean_directory_contents \
    /opt/pincabos/backups

clean_directory_contents \
    /opt/pincabos/web/backups

clean_directory_contents \
    /home/pinball/.local/share/pincabos/editor-backups

for DIR in \
    /home/pinball/.local/share/VPinballX/*/backups
do
    [ -d "$DIR" ] || continue
    clean_directory_contents "$DIR"
done

#
# Copies .bak/.before/.old/.orig sous /opt/pincabos.
# On exclut tmp car le repo Git vit dedans.
#

find /opt/pincabos \
    -path '/opt/pincabos/tmp' -prune -o \
    -type f \
    \( \
        -name '*.bak' -o \
        -name '*.bak.*' -o \
        -name '*.bak-*' -o \
        -name '*.before-*' -o \
        -name '*.old' -o \
        -name '*.orig' \
    \) \
    -print \
    -delete \
    2>/dev/null \
    | tee "$REPORT/deleted-backup-files.txt"

ok "Backups PinCabOS nettoyes."

echo
echo "=== 8. PRESERVATION BACKUP LVM LOCAL ==="

for P in \
    /etc/lvm/backup \
    /etc/lvm/archive
do
    if [ -d "$P" ]
    then
        echo "PRESERVE $P"
        ls -lah "$P" \
            > "$REPORT/$(basename "$P")-lvm.txt" \
            2>/dev/null || true
    fi
done

ok "Metadonnees LVM locales conservees."

echo
echo "==============================================================="
echo " 9. MENAGE CRASH DUMPS"
echo "==============================================================="

if [ -d /var/crash ]
then
    find /var/crash \
        -mindepth 1 \
        -maxdepth 1 \
        -print \
        -exec rm -rf -- {} + \
        2>/dev/null \
        | tee "$REPORT/deleted-crash.txt"
fi

ok "/var/crash nettoye."

echo
echo "==============================================================="
echo " 10. MENAGE LOGS PINCABOS"
echo "==============================================================="

if [ -d /opt/pincabos/logs ]
then
    find /opt/pincabos/logs \
        -mindepth 1 \
        -type f \
        -print \
        -delete \
        2>/dev/null \
        | tee "$REPORT/deleted-pincabos-logs.txt"

    find /opt/pincabos/logs \
        -mindepth 1 \
        -type d \
        -empty \
        -delete \
        2>/dev/null || true
fi

#
# Logs PinCabOS sous /var/log :
# les logs courants sont tronques pour ne pas casser
# un service ayant le fichier ouvert.
#

find /var/log \
    -maxdepth 2 \
    -type f \
    \( \
        -name 'pincabos*.log' -o \
        -name 'pincabos*.log.*' -o \
        -path '*/pincabos/*.log' -o \
        -path '*/pincabos/*.log.*' \
    \) \
    -print0 \
    2>/dev/null |
while IFS= read -r -d '' LOG
do
    case "$LOG" in
        *.log)
            echo "TRUNCATE $LOG"
            truncate -s 0 "$LOG"
            ;;
        *)
            echo "DELETE $LOG"
            rm -f -- "$LOG"
            ;;
    esac
done

if command -v journalctl >/dev/null 2>&1
then
    journalctl \
        --vacuum-time=7d \
        >/dev/null 2>&1 \
        || true

    echo "GO [OK] Journald conserve 7 jours."
fi

ok "Logs PinCabOS nettoyes."

echo
echo "==============================================================="
echo " 11. SUPPRESSION LIENS SYMBOLIQUES MORTS"
echo "==============================================================="

if [ -s "$REPORT/dead-links.txt" ]
then
    while IFS= read -r LINK
    do
        [ -n "$LINK" ] || continue
        [ -L "$LINK" ] || continue
        [ -e "$LINK" ] && continue

        echo "DELETE DEAD LINK $LINK"
        rm -f -- "$LINK"
    done < "$REPORT/dead-links.txt"
fi

ok "Liens morts nettoyes."

echo
echo "=== 12. TMP PINCABOS ANCIENS > 7 JOURS ==="

find \
    /tmp \
    /var/tmp \
    -maxdepth 1 \
    -mindepth 1 \
    \( \
        -name 'pincabos-*' -o \
        -name 'pincab-*' \
    \) \
    -mtime +7 \
    -print \
    -exec rm -rf -- {} + \
    2>/dev/null \
    | tee "$REPORT/deleted-old-tmp.txt"

ok "TMP anciens nettoyes."

echo
echo "==============================================================="
echo " 13. SYNCHRONISATION CAB -> REPO"
echo "==============================================================="

python3 - "$REPO" "$REPORT" <<'PY'
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

repo = Path(sys.argv[1])
report = Path(sys.argv[2])

sync_log = report / "sync-files.txt"
skip_log = report / "skipped-historical.txt"
ignored_log = report / "ignored-live-files.txt"

sync_lines = []
skip_lines = []
ignored_lines = []

ALLOWED_TRACKED_PREFIXES = (
    "opt/pincabos/",
    "etc/systemd/system/",
    "etc/tmpfiles.d/",
    "etc/sudoers.d/",
    "etc/udev/rules.d/",
    "etc/modprobe.d/",
    "etc/lightdm/",
    "etc/X11/",
    "etc/pincabos/",
    "usr/local/",
    "usr/share/xsessions/",
    "usr/share/plymouth/themes/pincabos",
)

BLOCKED_PREFIXES = (
    "opt/pincabos/tmp/",
    "opt/pincabos/backups/",
    "opt/pincabos/logs/",
    "opt/pincabos/uploads/",
    "opt/pincabos/imports/",
    "opt/pincabos/config/screens/",
    "opt/pincabos/config/webapp-appearance/",
    "home/pinball/",
    "root/",
    "var/",
    "run/",
    "tmp/",
    "etc/lvm/backup/",
    "etc/lvm/archive/",
    "etc/ssh/",
    "etc/netplan/",
    "etc/NetworkManager/system-connections/",
)

BLOCKED_EXACT = {
    "opt/pincabos/config/webapp-secret.key",
    "etc/machine-id",
    "etc/hostname",
    "etc/hosts",
    "etc/shadow",
    "etc/gshadow",
    "etc/passwd",
}

BACKUP_SUFFIXES = (
    ".bak",
    ".old",
    ".orig",
)

def run(*args: str, check=True) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )

def blocked(rel: str) -> bool:
    if rel in BLOCKED_EXACT:
        return True

    if rel.startswith(BLOCKED_PREFIXES):
        return True

    name = Path(rel).name

    if (
        ".bak." in name
        or ".bak-" in name
        or ".before-" in name
        or name.endswith(BACKUP_SUFFIXES)
    ):
        return True

    if "__pycache__" in Path(rel).parts:
        return True

    if name.endswith(".pyc"):
        return True

    return False

def allowed_tracked(rel: str) -> bool:
    return rel.startswith(ALLOWED_TRACKED_PREFIXES)

def git_ignored(rel: str) -> bool:
    cp = subprocess.run(
        [
            "git",
            "check-ignore",
            "--no-index",
            "-q",
            "--",
            rel,
        ],
        cwd=repo,
    )
    return cp.returncode == 0

def historical_blob(path: Path) -> bool:
    cp = run(
        "git",
        "hash-object",
        str(path),
    )

    sha = cp.stdout.decode().strip()

    if not sha:
        return False

    probe = subprocess.run(
        [
            "git",
            "cat-file",
            "-e",
            f"{sha}^{{blob}}",
        ],
        cwd=repo,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return probe.returncode == 0

def copy_live(live: Path, rel: str) -> None:
    dst = repo / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(live, dst)
    sync_lines.append(rel)

# ------------------------------------------------------------
# A. Fichiers deja suivis :
#    - si identiques : rien
#    - si version live existe deja dans l'historique :
#      on considere le cab plus vieux et on NE retrograde PAS
#    - si version live est inconnue de Git :
#      c'est une modification locale nouvelle -> sync
# ------------------------------------------------------------

raw = run(
    "git",
    "ls-files",
    "-z",
).stdout

for item in raw.split(b"\0"):
    if not item:
        continue

    rel = item.decode(
        "utf-8",
        "surrogateescape",
    )

    if blocked(rel):
        continue

    if not allowed_tracked(rel):
        continue

    live = Path("/") / rel
    dst = repo / rel

    if not live.is_file():
        continue

    try:
        same = (
            dst.is_file()
            and live.read_bytes() == dst.read_bytes()
        )
    except OSError:
        continue

    if same:
        continue

    if historical_blob(live):
        skip_lines.append(rel)
        continue

    copy_live(live, rel)

# ------------------------------------------------------------
# B. Nouveaux fichiers sous /opt/pincabos.
# ------------------------------------------------------------

root = Path("/opt/pincabos")

PRUNE_DIRS = {
    "tmp",
    "backups",
    "logs",
    "uploads",
    "imports",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
}

for current, dirs, files in os.walk(root):
    cur = Path(current)

    dirs[:] = [
        d for d in dirs
        if d not in PRUNE_DIRS
        and not (
            cur == root / "build"
            and (
                d == "output"
                or d.startswith("live-")
            )
        )
    ]

    for name in files:
        live = cur / name

        try:
            rel = str(
                live.relative_to("/")
            )
        except ValueError:
            continue

        if blocked(rel):
            ignored_lines.append(rel)
            continue

        if (
            rel.startswith(
                "opt/pincabos/config/"
            )
            and rel
            != "opt/pincabos/config/github-rootfs-exclude.txt"
        ):
            #
            # Un nouveau fichier de config live peut contenir
            # l'identite du cab. On ne l'ajoute jamais
            # automatiquement.
            #
            if not (repo / rel).exists():
                ignored_lines.append(rel)
                continue

        tracked = subprocess.run(
            [
                "git",
                "ls-files",
                "--error-unmatch",
                "--",
                rel,
            ],
            cwd=repo,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode == 0

        if tracked:
            continue

        if git_ignored(rel):
            ignored_lines.append(rel)
            continue

        if not live.is_file():
            continue

        copy_live(live, rel)

# ------------------------------------------------------------
# C. Nouveaux fichiers systeme clairement PinCabOS.
# ------------------------------------------------------------

system_candidates = []

roots = [
    Path("/etc/systemd/system"),
    Path("/etc/tmpfiles.d"),
    Path("/etc/sudoers.d"),
    Path("/etc/udev/rules.d"),
    Path("/etc/modprobe.d"),
    Path("/etc/lightdm"),
    Path("/etc/X11"),
    Path("/etc/pincabos"),
    Path("/usr/local/bin"),
    Path("/usr/local/sbin"),
    Path("/usr/local/libexec"),
    Path("/usr/share/xsessions"),
    Path("/usr/share/plymouth/themes/pincabos"),
]

for base in roots:
    if not base.exists():
        continue

    if base.is_file():
        system_candidates.append(base)
        continue

    for current, dirs, files in os.walk(base):
        cur = Path(current)

        for name in files:
            live = cur / name
            low = str(live).lower()

            if (
                "pincabos" not in low
                and "pincab-" not in low
                and "/etc/pincabos/" not in low
                and "/usr/share/plymouth/themes/pincabos/" not in low
            ):
                continue

            system_candidates.append(live)

for live in system_candidates:
    try:
        rel = str(live.relative_to("/"))
    except ValueError:
        continue

    if blocked(rel):
        ignored_lines.append(rel)
        continue

    dst = repo / rel

    if dst.exists():
        continue

    if git_ignored(rel):
        ignored_lines.append(rel)
        continue

    if live.is_file():
        copy_live(live, rel)

sync_log.write_text(
    "\n".join(sorted(set(sync_lines))) + "\n",
    encoding="utf-8",
)

skip_log.write_text(
    "\n".join(sorted(set(skip_lines))) + "\n",
    encoding="utf-8",
)

ignored_log.write_text(
    "\n".join(sorted(set(ignored_lines))) + "\n",
    encoding="utf-8",
)

print(
    f"SYNC nouveaux/locaux : "
    f"{len(set(sync_lines))}"
)

print(
    f"SKIP anciennes versions Git : "
    f"{len(set(skip_lines))}"
)

print(
    f"IGNORE runtime/config : "
    f"{len(set(ignored_lines))}"
)
PY

echo
echo "=== 14. FICHIERS LIVE SYNCHRONISES ==="

cat "$REPORT/sync-files.txt" || true

echo
echo "=== 15. ANCIENNES VERSIONS LIVE NON REIMPORTEES ==="

cat "$REPORT/skipped-historical.txt" || true

echo
echo "=== 16. CONFIGS/RUNTIME VOLONTAIREMENT IGNORES ==="

cat "$REPORT/ignored-live-files.txt" || true

echo
echo "==============================================================="
echo " 17. AJOUT GIT"
echo "==============================================================="

git add -A

git diff \
    --cached \
    --name-status \
    | tee "$REPORT/staged-name-status.txt"

if git diff --cached --quiet
then
    echo
    echo "GO [OK] Aucun nouveau changement a publier."
    echo "Le cab utile correspond deja au depot."
    echo
    echo "Ménage effectue."
    echo
    echo "Backup securite:"
    echo "  $SAFETY"
    exit 0
fi

echo
echo "=== 18. GARDE FICHIERS INTERDITS ==="

FORBIDDEN_RE='(^|/)(webapp-secret\.key|ssh_host_|id_rsa|id_ed25519|shadow|gshadow)$|^home/pinball/Tables/|^var/crash/|^opt/pincabos/backups/|^opt/pincabos/logs/|^etc/lvm/(backup|archive)/'

if git diff \
    --cached \
    --name-only \
    | grep -E "$FORBIDDEN_RE"
then
    fail "Fichier prive/runtime stage."
fi

ok "Aucun fichier prive connu stage."

echo
echo "=== 19. LIMITE GITHUB 95 MiB ==="

TOO_BIG=0

while IFS= read -r REL
do
    [ -f "$REPO/$REL" ] || continue

    SIZE="$(stat -c %s "$REPO/$REL")"

    if [ "$SIZE" -gt 99614720 ]
    then
        echo "NOGO BIG FILE: $SIZE $REL"
        TOO_BIG=1
    fi
done < <(
    git diff \
        --cached \
        --name-only \
        --diff-filter=AM
)

[ "$TOO_BIG" -eq 0 ] ||
    fail "Fichier > 95 MiB."

ok "Aucun gros fichier problematique."

echo
echo "==============================================================="
echo " 20. SCAN SECRETS"
echo "==============================================================="

git diff \
    --cached \
    --name-only \
    --diff-filter=AM \
    -z \
    > "$REPORT/staged.z"

python3 - "$REPO" "$REPORT/staged.z" <<'PY'
from pathlib import Path
import re
import sys

repo = Path(sys.argv[1])
items = Path(sys.argv[2]).read_bytes().split(b"\0")

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
            rb"-----BEGIN "
            rb"(?:OPENSSH |RSA |EC |DSA )?"
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

issues=[]

for raw in items:
    if not raw:
        continue

    rel=raw.decode(
        "utf-8",
        "replace",
    )

    path=repo / rel

    if not path.is_file():
        continue

    data=path.read_bytes()

    if b"\0" in data[:4096]:
        continue

    for label, regex in patterns:
        if regex.search(data):
            issues.append(
                (rel, label)
            )

if issues:
    print(
        "NOGO : secret potentiel:"
    )

    for rel,label in issues:
        print(
            f"  {rel} -> "
            f"{label} [VALEUR MASQUEE]"
        )

    raise SystemExit(2)

print(
    "GO [OK] Aucun secret evident."
)
PY

echo
echo "=== 21. VALIDATION DES SCRIPTS MODIFIES ==="

while IFS= read -r REL
do
    [ -f "$REL" ] || continue

    case "$REL" in
        *.py)
            python3 -m py_compile "$REL" ||
                fail "Python invalide : $REL"

            echo "GO [PY] $REL"
            ;;

        *.sh)
            bash -n "$REL" ||
                fail "Shell invalide : $REL"

            echo "GO [SH] $REL"
            ;;
    esac
done < <(
    git diff \
        --cached \
        --name-only \
        --diff-filter=AM
)

git diff --cached --check ||
    fail "git diff --check."

ok "Validation source terminee."

echo
echo "==============================================================="
echo " 22. BACKUP GITHUB MAIN"
echo "==============================================================="

BACKUP_REMOTE="backup-main-before-full-cab-sync-$STAMP"

git push \
    origin \
    "$BASE_HEAD:refs/heads/$BACKUP_REMOTE"

ok "Backup GitHub : $BACKUP_REMOTE"

echo
echo "==============================================================="
echo " 23. COMMIT"
echo "==============================================================="

git commit \
    -m "sync(cab): full clean source sync"

NEW_HEAD="$(git rev-parse HEAD)"

echo "Ancien HEAD : $BASE_HEAD"
echo "Nouveau HEAD: $NEW_HEAD"

ok "Commit cree."

echo
echo "==============================================================="
echo " 24. PUSH GITHUB MAIN"
echo "==============================================================="

#
# On verifie une derniere fois que personne
# n'a modifie main entre-temps.
#

git fetch origin main

REMOTE_BEFORE_PUSH="$(
    git rev-parse refs/remotes/origin/main
)"

[ "$REMOTE_BEFORE_PUSH" = "$BASE_HEAD" ] ||
    fail "GitHub main a bouge pendant le sync."

git push \
    origin \
    HEAD:refs/heads/main

ok "Push termine."

echo
echo "=== 25. VERIFICATION FINALE ==="

git fetch origin main

REMOTE_AFTER="$(
    git rev-parse refs/remotes/origin/main
)"

LOCAL_AFTER="$(git rev-parse HEAD)"

echo "Local       : $LOCAL_AFTER"
echo "GitHub main : $REMOTE_AFTER"

[ "$LOCAL_AFTER" = "$REMOTE_AFTER" ] ||
    fail "GitHub main != local."

[ -z "$(git status --porcelain)" ] ||
    fail "Git local non propre."

ok "GitHub main == cab staging."

echo
echo "=== 26. ESPACE APRES MENAGE ==="

df -h / /opt/pincabos

echo
echo "==============================================================="
echo " GO [OK] CAB PINCABOS NETTOYE ET PUBLIE"
echo "==============================================================="
echo
echo "Ancien HEAD:"
echo "  $BASE_HEAD"
echo
echo "Nouveau HEAD:"
echo "  $LOCAL_AFTER"
echo
echo "Ménage:"
echo "  Logs PinCabOS       [OK]"
echo "  Crash dumps         [OK]"
echo "  Backups PinCabOS    [OK]"
echo "  *.bak/*.before      [OK]"
echo "  *.old/*.orig        [OK]"
echo "  Liens morts         [OK]"
echo "  TMP > 7 jours       [OK]"
echo
echo "Conserves volontairement:"
echo "  /etc/lvm/backup"
echo "  /etc/lvm/archive"
echo "  Tables / ROM / medias"
echo "  configs utilisateur"
echo "  configs ecrans/reseau"
echo "  secrets / SSH"
echo
echo "Backup d'urgence:"
echo "  $SAFETY"
echo
echo "Rapport complet:"
echo "  $REPORT"
echo
echo "Backup GitHub:"
echo "  $BACKUP_REMOTE"
echo "==============================================================="
