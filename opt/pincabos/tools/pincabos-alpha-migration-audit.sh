#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────
# PinCabOS - Alpha15 GL -> Alpha16 BGFX Migration Audit
# Created by Karots Sugarpie
# ────────────────────────────────────────────────────────────────
# Purpose:
#   Audit-only comparison between current Alpha16 BGFX install and an
#   optional mounted/exported Alpha15 GL reference tree.
#
# Dependencies/Requisites:
#   /usr/bin/bash
#   /usr/bin/find
#   /usr/bin/grep
#   /usr/bin/diff
#   /usr/bin/tar
#   /usr/bin/curl
#   /usr/bin/python3
#   /usr/bin/lsblk
#   /usr/bin/aplay         optional, from alsa-utils
#   /usr/bin/pactl         optional, from pulseaudio-utils / pipewire-pulse
#   /usr/bin/7z            optional, from 7zip or p7zip-full
#
# Safety:
#   This script does not patch, install, delete, move, or overwrite PinCabOS files.
#   It only reads files, runs diagnostics, and writes an audit report.
# ────────────────────────────────────────────────────────────────

set -u
set -o pipefail

ORANGE='\033[38;5;208m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

TS="$(date +%Y%m%d-%H%M%S)"
OUT="/opt/pincabos/logs/migration-audit-${TS}"
A15_ROOT="${1:-}"

mkdir -p "$OUT"/{alpha16,alpha15,diff,web,import,audio,external-disks,packages,configs,summary}

log() { echo -e "${ORANGE}$*${NC}"; }
ok() { echo -e "${GREEN}GO:${NC} $*"; }
warn() { echo -e "${YELLOW}WARN:${NC} $*"; }
bad() { echo -e "${RED}NOGOOD:${NC} $*"; }

run_capture() {
  local name="$1"
  shift
  {
    echo "### COMMAND"
    printf '%q ' "$@"
    echo
    echo
    echo "### OUTPUT"
    "$@" 2>&1
    echo
    echo "### EXIT=$?"
  } > "$OUT/$name" 2>&1 || true
}

copy_if_exists() {
  local src="$1"
  local dst="$2"
  if [ -e "$src" ]; then
    mkdir -p "$(dirname "$dst")"
    cp -a "$src" "$dst" 2>/dev/null || true
  fi
}

grep_tree() {
  local label="$1"
  local root="$2"
  local pattern="$3"
  local outfile="$4"

  if [ ! -d "$root" ]; then
    echo "Missing root: $root" > "$outfile"
    return 0
  fi

  {
    echo "### GREP: $label"
    echo "### ROOT: $root"
    echo "### PATTERN: $pattern"
    echo
    grep -RInE "$pattern" "$root" \
      --exclude-dir=.git \
      --exclude-dir=__pycache__ \
      --exclude-dir=venv \
      --exclude-dir=.venv \
      --exclude='*.pyc' \
      2>/dev/null || true
  } > "$outfile"
}

safe_diff_dir() {
  local old="$1"
  local new="$2"
  local name="$3"

  if [ ! -d "$old" ]; then
    echo "Alpha15 path missing: $old" > "$OUT/diff/${name}.diff"
    return 0
  fi
  if [ ! -d "$new" ]; then
    echo "Alpha16 path missing: $new" > "$OUT/diff/${name}.diff"
    return 0
  fi

  diff -ruN \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.git' \
    --exclude='venv' \
    --exclude='.venv' \
    --exclude='logs' \
    --exclude='backups' \
    "$old" "$new" > "$OUT/diff/${name}.diff" 2>&1 || true
}

clear
echo -e "${ORANGE}────────────────────────────────────────────────────────────────${NC}"
echo -e "${ORANGE} PinCabOS - Audit migration Alpha15 GL vers Alpha16 BGFX${NC}"
echo -e "${ORANGE}────────────────────────────────────────────────────────────────${NC}"
echo
echo "Report: $OUT"
echo "Alpha15 reference root: ${A15_ROOT:-not provided}"
echo

log "=== 1) État système Alpha16 ==="
run_capture "alpha16/os-release.txt" cat /etc/os-release
run_capture "alpha16/uname.txt" uname -a
run_capture "alpha16/whoami-id.txt" id
run_capture "alpha16/hostname-ip.txt" bash -lc 'hostnamectl; echo; ip -br a; echo; ip route'
run_capture "alpha16/services.txt" bash -lc 'systemctl --no-pager --full status pincabos-web.service pincabos-vpinfe.service nginx lightdm 2>&1 || true'
run_capture "alpha16/ports.txt" bash -lc 'ss -lntup 2>/dev/null || true'

log "=== 2) Packages critiques 7z / audio / web ==="
run_capture "packages/dpkg-critical.txt" bash -lc 'dpkg -l | grep -Ei "7zip|p7zip|alsa|pipewire|pulseaudio|flask|nginx|python3|vpin|chrome" || true'
run_capture "packages/which-critical.txt" bash -lc 'for b in 7z 7za 7zr python3 flask gunicorn aplay pactl wpctl lsblk blkid findmnt curl; do echo "--- $b"; command -v "$b" || true; done'
run_capture "packages/7z-version.txt" bash -lc '7z 2>&1 | head -40 || true; 7za 2>&1 | head -40 || true; 7zr 2>&1 | head -40 || true'

log "=== 3) Routes WebApp /external-disks / import ==="
APP="/opt/pincabos/web/app.py"
CORE="/opt/pincabos/web/pincabos_webapp_core.py"

copy_if_exists "$APP" "$OUT/web/app.py.alpha16"
copy_if_exists "$CORE" "$OUT/web/pincabos_webapp_core.py.alpha16"

run_capture "web/python-syntax-app.txt" bash -lc "python3 -m py_compile '$APP' 2>&1 || true"
run_capture "web/flask-route-grep.txt" bash -lc "grep -RInE '@app\\.route|external-disks|external_disks|import.*table|table.*import|7z|7za|7zr|archive|extract|upload|disk|lsblk|blkid|findmnt' /opt/pincabos/web /opt/pincabos/scripts /opt/pincabos/tools /opt/pincabos/bin 2>/dev/null || true"
run_capture "web/http-local-routes.txt" bash -lc '
for url in \
  http://127.0.0.1/ \
  http://127.0.0.1/admin \
  http://127.0.0.1/external-disks \
  http://127.0.0.1/external-disks/ \
  http://127.0.0.1/import \
  http://127.0.0.1/tables \
  http://127.0.0.1/about
do
  echo "===== $url ====="
  curl -ksS -o /tmp/pco-curl-body.txt -w "HTTP=%{http_code} SIZE=%{size_download} TIME=%{time_total}\n" "$url" || true
  head -80 /tmp/pco-curl-body.txt || true
  echo
done
'

log "=== 4) Audit disques externes ==="
run_capture "external-disks/lsblk.txt" bash -lc 'lsblk -o NAME,KNAME,TYPE,SIZE,FSTYPE,LABEL,UUID,MOUNTPOINTS,MODEL,SERIAL,TRAN,RM,HOTPLUG'
run_capture "external-disks/blkid.txt" bash -lc 'blkid || true'
run_capture "external-disks/findmnt.txt" bash -lc 'findmnt -R || true'
run_capture "external-disks/dev-disk.txt" bash -lc 'ls -la /dev/disk/by-id /dev/disk/by-uuid /dev/disk/by-label 2>/dev/null || true'
run_capture "external-disks/sudoers-disk.txt" bash -lc 'grep -RInE "external|disk|mount|umount|lsblk|blkid|findmnt|udisks|pincabos" /etc/sudoers /etc/sudoers.d /opt/pincabos/essentials/sudoers.d 2>/dev/null || true'

log "=== 5) Audit import tables / 7z ==="
grep_tree "alpha16 import/archive/table" "/opt/pincabos" "7z|7za|7zr|py7zr|patool|zipfile|tarfile|archive|extract|import|pincabos.*table|Tables|VPinballX|BGFX|GL" "$OUT/import/alpha16-import-grep.txt"
run_capture "import/tables-tree.txt" bash -lc 'find /home/pinball/Tables -maxdepth 3 -type f 2>/dev/null | sed "s#^#/##" | head -300 || true'
run_capture "import/import-related-files.txt" bash -lc 'find /opt/pincabos -type f \( -iname "*import*" -o -iname "*archive*" -o -iname "*table*" -o -iname "*7z*" \) 2>/dev/null | sort'

log "=== 6) Audit audio ALSA / PipeWire ==="
run_capture "audio/aplay-l.txt" bash -lc 'aplay -l 2>&1 || true'
run_capture "audio/aplay-L.txt" bash -lc 'aplay -L 2>&1 || true'
run_capture "audio/proc-asound.txt" bash -lc 'cat /proc/asound/cards 2>/dev/null || true; echo; cat /proc/asound/devices 2>/dev/null || true'
run_capture "audio/pactl.txt" bash -lc 'pactl info 2>&1 || true; echo; pactl list short sinks 2>&1 || true; echo; pactl list short sources 2>&1 || true'
run_capture "audio/wpctl.txt" bash -lc 'wpctl status 2>&1 || true'
run_capture "audio/vpx-ini-audio.txt" bash -lc 'grep -RInE "SoundDevice|MusicDevice|Sound3DDevice|Audio|ALSA|PipeWire|Pulse" /home/pinball/.vpinball /opt/pincabos/config /opt/pincabos/web /opt/pincabos/scripts 2>/dev/null || true'

log "=== 7) Audit migration GL -> BGFX ==="
grep_tree "alpha16 gl-bgfx references" "/opt/pincabos" "vpinball_gl|VPinballX_GL|VPinballX-BGFX|VPinballX_BGFX|BGFX|GL|vpxbinpath|vpx\\.sh|VPinballX\\.ini|\\.local/share/VPinballX|\\.config/vpinfe" "$OUT/alpha16/gl-bgfx-grep.txt"
run_capture "alpha16/vpx-files.txt" bash -lc 'find /opt/pincabos/apps/vpinball /opt/pincabos/bin /home/pinball/.vpinball /opt/pincabos/config -maxdepth 4 -type f -o -type l 2>/dev/null | sort | grep -Ei "VPinball|vpx|vpin|ini|BGFX|GL" || true'
run_capture "alpha16/vpx-wrapper.txt" bash -lc 'ls -la /opt/pincabos/bin/vpx.sh /opt/pincabos/apps/vpinball/VPinballX /opt/pincabos/apps/vpinball/VPinballX-BGFX /opt/pincabos/apps/vpinball/current/VPinballX-BGFX 2>/dev/null || true; echo; sed -n "1,220p" /opt/pincabos/bin/vpx.sh 2>/dev/null || true'

log "=== 8) Logs récents utiles ==="
run_capture "alpha16/recent-logs-list.txt" bash -lc 'find /opt/pincabos/logs /var/log/nginx -maxdepth 3 -type f 2>/dev/null | sort | tail -200'
run_capture "alpha16/web-journal.txt" bash -lc 'journalctl -u pincabos-web.service -n 300 --no-pager 2>&1 || true'
run_capture "alpha16/nginx-error.txt" bash -lc 'tail -300 /var/log/nginx/error.log 2>&1 || true'
run_capture "alpha16/nginx-access.txt" bash -lc 'tail -300 /var/log/nginx/access.log 2>&1 || true'

if [ -n "$A15_ROOT" ] && [ -d "$A15_ROOT" ]; then
  log "=== 9) Alpha15 référence fournie : collecte + diff ==="

  copy_if_exists "$A15_ROOT/opt/pincabos/web/app.py" "$OUT/web/app.py.alpha15"
  copy_if_exists "$A15_ROOT/opt/pincabos/web/pincabos_webapp_core.py" "$OUT/web/pincabos_webapp_core.py.alpha15"

  grep_tree "alpha15 external/import/audio/gl" "$A15_ROOT/opt/pincabos" "external-disks|external_disks|import.*table|table.*import|7z|7za|7zr|alsa|aplay|SoundDevice|VPinballX_GL|vpinball_gl|VPinballX-BGFX|vpxbinpath|lsblk|blkid|findmnt" "$OUT/alpha15/key-grep.txt"

  safe_diff_dir "$A15_ROOT/opt/pincabos/web" "/opt/pincabos/web" "web-alpha15-vs-alpha16"
  safe_diff_dir "$A15_ROOT/opt/pincabos/scripts" "/opt/pincabos/scripts" "scripts-alpha15-vs-alpha16"
  safe_diff_dir "$A15_ROOT/opt/pincabos/tools" "/opt/pincabos/tools" "tools-alpha15-vs-alpha16"
  safe_diff_dir "$A15_ROOT/opt/pincabos/bin" "/opt/pincabos/bin" "bin-alpha15-vs-alpha16"
  safe_diff_dir "$A15_ROOT/opt/pincabos/essentials/sudoers.d" "/opt/pincabos/essentials/sudoers.d" "sudoers-templates-alpha15-vs-alpha16"
  safe_diff_dir "$A15_ROOT/opt/pincabos/config" "/opt/pincabos/config" "config-alpha15-vs-alpha16"

  run_capture "diff/route-diff-focused.txt" bash -lc "diff -u '$OUT/web/app.py.alpha15' '$OUT/web/app.py.alpha16' 2>/dev/null | grep -Ei -C 8 'external-disks|external_disks|import|7z|audio|alsa|VPinballX|BGFX|GL|route' || true"
else
  warn "Aucun chemin Alpha15 fourni. Le rapport Alpha16 sera généré sans diff Alpha15."
fi

log "=== 10) Résumé automatique ==="
SUMMARY="$OUT/summary/SUMMARY.md"

{
  echo "# PinCabOS Migration Audit - $TS"
  echo
  echo "## Scope"
  echo "- Current system: Alpha16 BGFX"
  echo "- Reference Alpha15 root: ${A15_ROOT:-not provided}"
  echo "- Mode: audit-only, no patch"
  echo

  echo "## Quick findings to inspect"
  echo

  echo "### HTTP route status"
  if [ -f "$OUT/web/http-local-routes.txt" ]; then
    grep -E "=====|HTTP=" "$OUT/web/http-local-routes.txt" || true
  fi
  echo

  echo "### 7z availability"
  grep -H "7z\|7za\|7zr" "$OUT/packages/which-critical.txt" 2>/dev/null || true
  echo

  echo "### ALSA cards"
  cat "$OUT/audio/proc-asound.txt" 2>/dev/null || true
  echo

  echo "### Dangerous GL leftovers in Alpha16"
  grep -RInE "vpinball_gl|VPinballX_GL|\\.local/share/VPinballX|\\.config/vpinfe" "$OUT/alpha16" "$OUT/web" "$OUT/import" 2>/dev/null || true
  echo

  echo "### BGFX references in Alpha16"
  grep -RInE "VPinballX-BGFX|VPinballX_BGFX|BGFX" "$OUT/alpha16" "$OUT/web" "$OUT/import" 2>/dev/null | head -200 || true
  echo

  echo "## Main files"
  echo "- Web route grep: web/flask-route-grep.txt"
  echo "- External disks audit: external-disks/"
  echo "- Import/7z audit: import/"
  echo "- Audio audit: audio/"
  echo "- GL/BGFX audit: alpha16/gl-bgfx-grep.txt"
  echo "- Diffs: diff/"
} > "$SUMMARY"

log "=== 11) Archive du rapport ==="
tar -C "$(dirname "$OUT")" -czf "${OUT}.tar.gz" "$(basename "$OUT")" 2>/dev/null || true

echo
ok "Audit terminé"
echo "Dossier : $OUT"
echo "Archive : ${OUT}.tar.gz"
echo
echo -e "${YELLOW}Prochaine étape:${NC} envoie le contenu de:"
echo "  $SUMMARY"
echo "  $OUT/web/http-local-routes.txt"
echo "  $OUT/web/flask-route-grep.txt"
echo "  $OUT/import/alpha16-import-grep.txt"
echo "  $OUT/audio/proc-asound.txt"
echo "  $OUT/audio/aplay-l.txt"
echo "  $OUT/alpha16/gl-bgfx-grep.txt"
echo
if [ -n "$A15_ROOT" ] && [ -d "$A15_ROOT" ]; then
  echo "Et aussi:"
  echo "  $OUT/diff/route-diff-focused.txt"
  echo "  $OUT/diff/web-alpha15-vs-alpha16.diff"
fi
