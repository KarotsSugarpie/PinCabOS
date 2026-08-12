#!/usr/bin/env bash
# PinCabOS-File created by Karots Sugarpie
# PINCABOS_SCRIPT_NAME="pincabos-cleanup.sh"
# PINCABOS_SCRIPT_ROLE="Safe aggressive cleanup for PinCabOS Admin"
# PINCABOS_SCRIPT_REQUIRES_FILES="/usr/bin/find /usr/bin/du /usr/bin/df /usr/bin/apt-get /usr/bin/journalctl"
# PINCABOS_SCRIPT_REQUIRES_DIRS="/opt/pincabos/logs /opt/pincabos/backups /tmp /var/tmp"
# PINCABOS_SCRIPT_PROTECTS="/home/pinball/Tables /home/pinball/Exports /home/pinball/Share /home/pinball/.vpinball /opt/pincabos/apps /opt/pincabos/config /opt/pincabos/web /opt/pincabos/bin /opt/pincabos/tools"

set -Eeuo pipefail

MODE="dry-run"
case "${1:-}" in
  ""|"--dry-run"|"dry-run") MODE="dry-run" ;;
  "--apply"|"apply") MODE="apply" ;;
  *)
    echo "Usage: $0 [--dry-run|--apply]"
    exit 2
    ;;
esac

BASE="/opt/pincabos"
LOG_DIR="$BASE/logs"
BK_DIR="$BASE/backups"
AGE_DAYS="${PINCABOS_CLEANUP_AGE_DAYS:-7}"
TS="$(date +%Y%m%d-%H%M%S)"
RUN_LOG="$LOG_DIR/pincabos-cleanup-${MODE}-${TS}.log"

mkdir -p "$LOG_DIR"

exec > >(tee -a "$RUN_LOG") 2>&1

say() { printf '%s\n' "$*"; }
section() { echo; echo "=== $* ==="; }

is_apply() {
  [ "$MODE" = "apply" ]
}

size_of() {
  for p in "$@"; do
    [ -e "$p" ] && du -sh "$p" 2>/dev/null || true
  done | sort -h || true
}

safe_rm_exact() {
  local p="$1"
  local reason="${2:-cleanup}"

  if [ -z "$p" ] || [ ! -e "$p" ]; then
    echo "Absent, skip: $p"
    return 0
  fi

  case "$p" in
    /opt/pincabos/download|/opt/pincabos/stage|/opt/pincabos/cache|/opt/pincabos/tmp|/opt/pincabos/work|/opt/pincabos/build|/opt/pincabos/uploads/tmp|/opt/pincabos/logs/tmp|/tmp/pincabos-*|/var/tmp/pincabos-*|/home/pinball/.cache/pincabos|/home/pinball/.cache/pip|/home/pinball/.cache/thumbnails|/home/pinball/.local/share/Trash/files|/home/pinball/.local/share/Trash/info)
      ;;
    *)
      echo "NOGOOD refus chemin exact non autorisé: $p"
      return 1
      ;;
  esac

  if is_apply; then
    echo "SUPPRESSION: $p"
    echo "  raison: $reason"
    rm -rf --one-file-system "$p"
  else
    echo "DRY-RUN supprimerait: $p"
    echo "  raison: $reason"
  fi
}

safe_delete_find_files() {
  local label="$1"
  local root="$2"
  shift 2

  section "$label"

  if [ ! -e "$root" ]; then
    echo "Absent, skip: $root"
    return 0
  fi

  echo "--- candidats"
  find "$root" "$@" -print 2>/dev/null | sed -n '1,300p' || true

  if is_apply; then
    find "$root" "$@" -delete 2>/dev/null || true
  fi
}

safe_delete_find_rmrf() {
  local label="$1"
  local root="$2"
  shift 2

  section "$label"

  if [ ! -e "$root" ]; then
    echo "Absent, skip: $root"
    return 0
  fi

  echo "--- candidats"
  find "$root" "$@" -print 2>/dev/null | sed -n '1,300p' || true

  if is_apply; then
    find "$root" "$@" -exec rm -rf --one-file-system {} + 2>/dev/null || true
  fi
}

echo "────────────────────────────────────────────────────────────────"
echo " PinCabOS Cleanup SAFE aggressive"
echo "────────────────────────────────────────────────────────────────"
echo "MODE=$MODE"
echo "AGE_DAYS=$AGE_DAYS"
echo "Log=$RUN_LOG"

section "Espace AVANT"
df -h /
echo
size_of \
  /opt/pincabos \
  /opt/pincabos/download \
  /opt/pincabos/stage \
  /opt/pincabos/backups \
  /opt/pincabos/logs \
  /tmp \
  /var/tmp \
  /var/log \
  /home/pinball/.cache \
  /home/pinball/Tables

section "Protections non négociables"
for p in \
  /home/pinball/Tables \
  /home/pinball/Exports \
  /home/pinball/Share \
  /home/pinball/.vpinball \
  /opt/pincabos/apps \
  /opt/pincabos/config \
  /opt/pincabos/web \
  /opt/pincabos/bin \
  /opt/pincabos/tools
do
  echo "PROTECT: $p"
done

section "Validation essentiels"
ESSENTIALS=(
  /opt/pincabos/web/app.py
  /opt/pincabos/web/.venv
  /opt/pincabos/tools
  /opt/pincabos/bin
  /opt/pincabos/config
  /opt/pincabos/apps/vpinball
  /opt/pincabos/apps/frontend/vpinfe
  /home/pinball/Tables
  /home/pinball/.vpinball
  /etc/systemd/system/pincabos-webapp.service
)

FAIL=0
for p in "${ESSENTIALS[@]}"; do
  if [ -e "$p" ]; then
    echo "OK: $p"
  else
    echo "ABSENT: $p"
    case "$p" in
      /opt/pincabos/web/app.py|/opt/pincabos/web/.venv|/opt/pincabos/tools|/opt/pincabos/config|/home/pinball/Tables|/etc/systemd/system/pincabos-webapp.service)
        FAIL=1
        ;;
    esac
  fi
done

if [ "$FAIL" -ne 0 ]; then
  echo "NOGOOD: essentiel critique absent. Cleanup annulé."
  exit 1
fi

section "APT autoremove / autoclean / clean"
if command -v apt-get >/dev/null 2>&1; then
  if is_apply; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get -y autoremove --purge || true
    apt-get -y autoclean || true
    apt-get -y clean || true
  else
    echo "DRY-RUN: apt-get -y autoremove --purge"
    apt-get -s autoremove --purge || true
    echo "DRY-RUN: apt-get -y autoclean"
    echo "DRY-RUN: apt-get -y clean"
  fi
else
  echo "apt-get absent, skip."
fi

section "Journal systemd vacuum"
if command -v journalctl >/dev/null 2>&1; then
  if is_apply; then
    journalctl --vacuum-time=7d || true
    journalctl --vacuum-size=100M || true
  else
    echo "DRY-RUN: journalctl --vacuum-time=7d"
    echo "DRY-RUN: journalctl --vacuum-size=100M"
  fi
fi

section "Dossiers morts / staging / downloads PinCabOS"
safe_rm_exact "/opt/pincabos/stage" "staging golden-runtime/repack; recréable"
safe_rm_exact "/opt/pincabos/download" "downloads packages/build payload; recréable"
safe_rm_exact "/opt/pincabos/cache" "cache PinCabOS; recréable"
safe_rm_exact "/opt/pincabos/tmp" "tmp PinCabOS; recréable"
safe_rm_exact "/opt/pincabos/work" "work PinCabOS; recréable"
safe_rm_exact "/opt/pincabos/build" "build PinCabOS; recréable"

section "Backups PinCabOS plus vieux que ${AGE_DAYS} jours"
if [ -e "$BK_DIR" ]; then
  echo "--- candidats"
  find "$BK_DIR" -mindepth 1 -maxdepth 1 -mtime +"$AGE_DAYS" \
    ! -name "*KEEP*" ! -name "*keep*" \
    -printf "%TY-%Tm-%Td %TH:%TM %s %p\n" 2>/dev/null | sort | sed -n '1,300p' || true

  if is_apply; then
    find "$BK_DIR" -mindepth 1 -maxdepth 1 -mtime +"$AGE_DAYS" \
      ! -name "*KEEP*" ! -name "*keep*" \
      -exec rm -rf --one-file-system {} + 2>/dev/null || true
  fi
else
  echo "Backups absent: $BK_DIR"
fi

section "Logs PinCabOS plus vieux que ${AGE_DAYS} jours"
if [ -e "$LOG_DIR" ]; then
  echo "--- fichiers candidats"
  find "$LOG_DIR" -type f -mtime +"$AGE_DAYS" \
    ! -name "*KEEP*" ! -name "*keep*" \
    -printf "%TY-%Tm-%Td %TH:%TM %s %p\n" 2>/dev/null | sort | sed -n '1,300p' || true

  echo "--- dossiers audit candidats"
  find "$LOG_DIR" -mindepth 1 -maxdepth 1 -type d -mtime +"$AGE_DAYS" \
    ! -name "*KEEP*" ! -name "*keep*" \
    -printf "%TY-%Tm-%Td %TH:%TM %s %p\n" 2>/dev/null | sort | sed -n '1,300p' || true

  if is_apply; then
    find "$LOG_DIR" -type f -mtime +"$AGE_DAYS" \
      ! -name "*KEEP*" ! -name "*keep*" \
      -delete 2>/dev/null || true

    find "$LOG_DIR" -mindepth 1 -maxdepth 1 -type d -mtime +"$AGE_DAYS" \
      ! -name "*KEEP*" ! -name "*keep*" \
      -exec rm -rf --one-file-system {} + 2>/dev/null || true
  fi
fi

section "Logs système rotated plus vieux que ${AGE_DAYS} jours"
safe_delete_find_files "Rotated /var/log" "/var/log" \
  -type f -mtime +"$AGE_DAYS" \
  \( -name "*.gz" -o -name "*.xz" -o -name "*.old" -o -name "*.1" -o -name "*.2" -o -name "*.log.*" \)

section "Caches Python / bytecode"
for root in /opt/pincabos/web /opt/pincabos/tools /opt/pincabos/install /root /home/pinball/.cache; do
  [ -e "$root" ] || continue
  safe_delete_find_rmrf "__pycache__ sous $root" "$root" \
    -xdev -type d -name "__pycache__"
  safe_delete_find_files "pyc/pyo sous $root" "$root" \
    -xdev -type f \( -name "*.pyc" -o -name "*.pyo" \)
done

section "Caches utilisateur sécuritaires"
safe_rm_exact "/home/pinball/.cache/pincabos" "cache PinCabOS utilisateur"
safe_rm_exact "/home/pinball/.cache/pip" "cache pip utilisateur"
safe_rm_exact "/home/pinball/.cache/thumbnails" "thumbnails utilisateur"
safe_rm_exact "/home/pinball/.local/share/Trash/files" "corbeille utilisateur"
safe_rm_exact "/home/pinball/.local/share/Trash/info" "corbeille metadata utilisateur"

section "Temp vieux"
safe_delete_find_rmrf "/tmp vieux PinCabOS > 2 jours" "/tmp" \
  -mindepth 1 -maxdepth 1 -mtime +2 -name "pincabos-*"

safe_delete_find_rmrf "/var/tmp vieux PinCabOS > 3 jours" "/var/tmp" \
  -mindepth 1 -maxdepth 1 -mtime +3 -name "pincabos-*"

section "Fichiers temporaires patterns sûrs"
for root in /tmp /var/tmp /opt/pincabos/install /opt/pincabos/tools; do
  [ -e "$root" ] || continue
  safe_delete_find_files "tmp/part/download sous $root" "$root" \
    -xdev -type f \( -name "*.tmp" -o -name "*.temp" -o -name "*.part" -o -name "*.download" \) -mtime +1
done

section "Liens morts"
for root in /opt/pincabos /home/pinball; do
  [ -e "$root" ] || continue
  echo "--- dead symlinks $root"
  find "$root" -xtype l -print 2>/dev/null | sed -n '1,300p' || true
  if is_apply; then
    find "$root" -xtype l -delete 2>/dev/null || true
  fi
done

section "Récréation dossiers vides requis"
if is_apply; then
  mkdir -p \
    /opt/pincabos/logs \
    /opt/pincabos/backups \
    /opt/pincabos/download \
    /opt/pincabos/tmp \
    /opt/pincabos/uploads \
    /tmp
  chown -R pinball:pinball /opt/pincabos/logs /opt/pincabos/backups /opt/pincabos/download /opt/pincabos/tmp /opt/pincabos/uploads 2>/dev/null || true
fi

section "Espace APRÈS"
df -h /
echo
size_of \
  /opt/pincabos \
  /opt/pincabos/download \
  /opt/pincabos/stage \
  /opt/pincabos/backups \
  /opt/pincabos/logs \
  /tmp \
  /var/tmp \
  /var/log \
  /home/pinball/.cache \
  /home/pinball/Tables

if is_apply; then
  section "Validation post-cleanup"

  echo "────────────────────────────────────────────────────────────────"
  echo " PinCabOS - Validation post-cleanup"
  echo "────────────────────────────────────────────────────────────────"

  echo
  echo "=== 1) Disk ==="
  df -h /
  du -sh /opt/pincabos /opt/pincabos/apps /opt/pincabos/config /opt/pincabos/web /opt/pincabos/tools /home/pinball/Tables 2>/dev/null | sort -h || true

  echo
  echo "=== 2) Services ==="
  systemctl is-active pincabos-webapp.service || true
  systemctl is-active pincabos-vpinfe.service || true
  systemctl is-active nginx || true

  echo
  echo "=== 3) HTTP ==="
  curl -ksS -o /dev/null -w "/admin HTTP=%{http_code}\n" http://127.0.0.1/admin || true
  curl -ksS -o /dev/null -w "/tools HTTP=%{http_code}\n" http://127.0.0.1/tools || true
  curl -ksS -o /dev/null -w "/admin/frame/cleanup-dry-run HTTP=%{http_code}\n" http://127.0.0.1/admin/frame/cleanup-dry-run || true

  echo
  echo "=== 4) Table importée toujours là ==="
  find "/home/pinball/Tables/Attack from Mars (Bally 1995)" -maxdepth 3 -type f \
    \( -iname "*.vpx" -o -iname "*.directb2s" -o -iname "*.vbs" -o -iname "*.zip" -o -iname "*.cRZ" -o -iname "altsound.ini" \) \
    -printf "%s %p\n" 2>/dev/null | sort -n | head -80 || true

  echo
  echo "=== 5) Dernier log cleanup ==="
  tail -80 "$RUN_LOG" 2>/dev/null || true
fi

section "Résumé"
if is_apply; then
  echo "FIN APPLY: cleanup agressif safe exécuté."
else
  echo "FIN DRY-RUN: rien supprimé."
fi
echo "Log: $RUN_LOG"
