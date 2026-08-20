#!/usr/bin/env bash
set -Eeuo pipefail

clear

REPO="/opt/pincabos/tmp/pr-integration"
REPORT="/root/pincab-full-source-audit-$(date +%Y%m%d-%H%M%S).txt"

exec > >(tee "$REPORT") 2>&1

echo "==============================================================="
echo " PINCABOS — AUDIT COMPLET CAB -> GITHUB"
echo " RECHERCHE DE TOUT LE CODE PINCABOS"
echo " AUCUNE MODIFICATION / AUCUN PUSH"
echo "==============================================================="
echo

[ "$(id -u)" -eq 0 ] || {
    echo "NOGO : root requis."
    exit 1
}

[ -d "$REPO/.git" ] || {
    echo "NOGO : repo absent : $REPO"
    exit 1
}

cd "$REPO"

echo "=== 1. ETAT GIT ==="
echo "Branche : $(git branch --show-current)"
echo "HEAD    : $(git rev-parse HEAD)"
git status --short
echo

echo "=== 2. RECHERCHE PINCAB RECORDER ==="

find \
    /opt \
    /usr/local \
    /etc/systemd \
    /home/pinball \
    -xdev \
    \( \
        -iname '*pincab*recorder*' -o \
        -iname '*recorder*pincab*' -o \
        -iname '*recorder*' \
    \) \
    -print 2>/dev/null \
    | sort

echo
echo "=== 3. SERVICES PINCABOS ==="

find \
    /etc/systemd/system \
    /usr/lib/systemd/system \
    /lib/systemd/system \
    -maxdepth 2 \
    -type f \
    \( \
        -iname 'pincabos*.service' -o \
        -iname 'pincab*.service' -o \
        -iname '*recorder*.service' \
    \) \
    -print 2>/dev/null \
    | sort

echo
echo "=== 4. EXECUTABLES PINCABOS / RECORDER ==="

find \
    /usr/local/bin \
    /usr/local/sbin \
    /opt/pincabos \
    -type f \
    \( \
        -iname 'pincabos*' -o \
        -iname 'pincab-*' -o \
        -iname '*recorder*' \
    \) \
    -print 2>/dev/null \
    | sort

echo
echo "=== 5. REPERTOIRES PRINCIPAUX /opt/pincabos ==="

du -h \
    --max-depth=2 \
    /opt/pincabos \
    2>/dev/null \
    | sort -h

echo
echo "=== 6. FICHIERS LIVE /opt/pincabos ABSENTS DU REPO ==="

find /opt/pincabos \
    -xdev \
    -type f \
    \
    ! -path '/opt/pincabos/tmp/*' \
    ! -path '/opt/pincabos/backups/*' \
    ! -path '/opt/pincabos/uploads/*' \
    ! -path '/opt/pincabos/imports/*' \
    ! -path '/opt/pincabos/build/output/*' \
    ! -path '/opt/pincabos/build/live-*/*' \
    ! -path '/opt/pincabos/logs/*' \
    ! -path '*/__pycache__/*' \
    ! -name '*.pyc' \
    -print0 |
while IFS= read -r -d '' SRC
do
    REL="${SRC#/}"

    if [ ! -e "$REPO/$REL" ]; then
        printf 'MISSING | %s\n' "$SRC"
    fi
done

echo
echo "=== 7. FICHIERS LIVE DIFFERENTS DU REPO ==="

find /opt/pincabos \
    -xdev \
    -type f \
    \
    ! -path '/opt/pincabos/tmp/*' \
    ! -path '/opt/pincabos/backups/*' \
    ! -path '/opt/pincabos/uploads/*' \
    ! -path '/opt/pincabos/imports/*' \
    ! -path '/opt/pincabos/build/output/*' \
    ! -path '/opt/pincabos/build/live-*/*' \
    ! -path '/opt/pincabos/logs/*' \
    ! -path '*/__pycache__/*' \
    ! -name '*.pyc' \
    -print0 |
while IFS= read -r -d '' SRC
do
    REL="${SRC#/}"
    DST="$REPO/$REL"

    if [ -f "$DST" ]; then
        if ! cmp -s "$SRC" "$DST"; then
            printf 'DIFFERENT | %s\n' "$SRC"
        fi
    fi
done

echo
echo "=== 8. FICHIERS SYSTEME PINCABOS ABSENTS DU REPO ==="

for ROOT in \
    /etc/systemd/system \
    /usr/local/bin \
    /usr/local/sbin
do
    find "$ROOT" \
        -maxdepth 2 \
        -type f \
        \( \
            -iname 'pincabos*' -o \
            -iname 'pincab-*' -o \
            -iname '*pincab*recorder*' \
        \) \
        -print0 2>/dev/null |
    while IFS= read -r -d '' SRC
    do
        REL="${SRC#/}"

        if [ ! -e "$REPO/$REL" ]; then
            printf 'MISSING | %s\n' "$SRC"
        elif ! cmp -s "$SRC" "$REPO/$REL"; then
            printf 'DIFFERENT | %s\n' "$SRC"
        fi
    done
done

echo
echo "=== 9. RECHERCHE DE SECRETS A NE PAS PUBLIER ==="

grep -RniE \
    --exclude-dir=.git \
    --exclude='*.pyc' \
    --exclude='*.log' \
    '(password|passwd|secret|token|api[_-]?key|private[_-]?key|BEGIN OPENSSH PRIVATE KEY|gho_[A-Za-z0-9]+)' \
    /opt/pincabos \
    /etc/systemd/system/pincabos* \
    2>/dev/null \
    | head -200 || true

echo
echo "=== 10. GROS FICHIERS PINCABOS > 50 MiB ==="

find /opt/pincabos \
    -xdev \
    -type f \
    -size +50M \
    ! -path '/opt/pincabos/tmp/*' \
    ! -path '/opt/pincabos/backups/*' \
    -printf '%12s  %p\n' \
    2>/dev/null \
    | sort -n

echo
echo "==============================================================="
echo " AUDIT TERMINE"
echo "==============================================================="
echo
echo "Rapport : $REPORT"
echo
echo "AUCUN FICHIER MODIFIE"
echo "AUCUN PUSH GITHUB"
echo "==============================================================="
