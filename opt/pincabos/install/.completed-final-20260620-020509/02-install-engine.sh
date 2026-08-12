#!/usr/bin/env bash
# =============================================================================
# PinCabOS - 02-install-engine.sh
# Role: Web package installer worker called by go-pincabos during RUN_02.
# Created by Karots Sugarpie
#
# This script does NOT manage workflow flags.
# go-pincabos is the only owner of RUN flags, resume, reset and reboot flow.
#
# Dependencies / requisites:
#   Required packages:
#     ca-certificates curl wget jq tar zstd rsync unzip xz-utils file sudo
#     python3 python3-venv python3-pip python3-requests python3-yaml
#     systemd
#
#   Required commands:
#     bash curl wget jq tar unzstd rsync python3 systemctl visudo
#
# Input official Web package:
#   https://ins.pincabos.cc/install/pkg/pkg-pincabos-web.zst
#
# Package checksum:
#   https://ins.pincabos.cc/install/pkg/pkg-pincabos-web.sha256
#
# Global default paths:
#   PinCabOS root:       /opt/pincabos
#   WebApp:             /opt/pincabos/web
#   WebApp venv:        /opt/pincabos/web/.venv
#   VPX runtime:        /opt/pincabos/apps/vpinball
#   VPX launcher:       /opt/pincabos/bin/vpx.sh
#   VPX INI:            /home/pinball/.vpinball/VPinballX.ini
#   Tables:             /home/pinball/Tables
#   VPinFE runtime:     /opt/pincabos/apps/frontend/vpinfe/current
#   VPinFE INI:         /opt/pincabos/config/vpinfe/vpinfe.ini
# # =============================================================================

set -Eeuo pipefail

ORANGE="\033[38;5;208m"
CYAN="\033[36m"
GREEN="\033[32m"
RED="\033[31m"
YELLOW="\033[33m"
NC="\033[0m"

TS="$(date +%Y%m%d-%H%M%S)"
LOG_DIR="/opt/pincabos/logs"
LOG_FILE="$LOG_DIR/02-install-engine-$TS.log"

PCO_ROOT="/opt/pincabos"
PCO_STAGE="${PCO_CLEAN_ENGINE_STAGE:-/tmp/pincabos-engine-audit/clean-bgfx-only-v2}"
PCO_QUAR="$PCO_STAGE/_quarantine_forbidden_gl"
PCO_BACKUP="/opt/pincabos/backups/run02-engine-$TS"

INSTALL_BASE="${PIN_INSTALL_BASE:-https://ins.pincabos.cc/install}"
UPDATE_BASE="${PIN_UPDATE_BASE:-https://ins.pincabos.cc/updates}"

WEB_PKG_URL="${PIN_WEB_PKG_URL:-$INSTALL_BASE/pkg/pkg-pincabos-web.zst}"
WEB_PKG_SHA_URL="${PIN_WEB_PKG_SHA_URL:-$INSTALL_BASE/pkg/pkg-pincabos-web.sha256}"
WEB_PKG_MANIFEST_URL="${PIN_WEB_PKG_MANIFEST_URL:-$INSTALL_BASE/pkg/pkg-pincabos-web.manifest.json}"
WEB_PKG_CACHE_DIR="/opt/pincabos/download/webpkg"
WEB_PKG_FILE="$WEB_PKG_CACHE_DIR/pkg-pincabos-web.zst"
WEB_PKG_SHA_FILE="$WEB_PKG_CACHE_DIR/pkg-pincabos-web.sha256"
WEB_PKG_MANIFEST_FILE="$WEB_PKG_CACHE_DIR/pkg-pincabos-web.manifest.json"
WEB_PKG_VERIFY_ROOT="/tmp/pincabos-webpkg-verify-$TS"

WEB_DIR="/opt/pincabos/web"
WEB_VENV="/opt/pincabos/web/.venv"

VPX_DIR="/opt/pincabos/apps/vpinball"
VPX_ALT_DIR="/opt/pincabos/apps/vpx"
VPX_BIN="/opt/pincabos/bin/vpx.sh"
VPX_INI="/home/pinball/.vpinball/VPinballX.ini"
TABLES_DIR="/home/pinball/Tables"
ROMS_DIR="/opt/pincabos/apps/vpinball/PinMAME/roms"

VPINFE_DIR="/opt/pincabos/apps/frontend/vpinfe/current"
VPINFE_INI="/opt/pincabos/config/vpinfe/vpinfe.ini"

mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG_FILE") 2>&1

pco_title() {
  echo -e "${CYAN}────────────────────────────────────────────────────────────────${NC}"
  echo -e "${ORANGE} PinCabOS - 02 Web package worker${NC}"
  echo -e "${CYAN}────────────────────────────────────────────────────────────────${NC}"
}

pco_step() {
  local id="${1:-??}"
  shift || true
  echo
  echo -e "${CYAN}─[${id}]─► ${ORANGE}${*:-Step}${CYAN} ◄────────────────────────────────────────${NC}"
}

pco_info() { echo -e "${CYAN:-}INFO ${*:-Info}${NC:-}"; }
pco_go() { echo -e "${GREEN}GO [√] ${*:-OK}${NC}"; }
pco_warn() { echo -e "${YELLOW}WARN ${*:-Warning}${NC}"; }
pco_nogo() {
  local code="${1:-ERR-02-UNKNOWN}"
  shift || true
  echo -e "${RED}NOGO [***] ${code}${NC} ${*:-No detail}"
  echo "Log: $LOG_FILE"
  exit 1
}

run_cmd() {
  echo "+ $*"
  "$@"
}

apt_install() {
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get -y autoremove
  apt-get install -y "$@"
}

assert_no_run_flags_management() {
  pco_step "00" "Workflow ownership guard"
  pco_go "go-pincabos owns RUN flags; 02 does not create or delete workflow flags"
}



pincabos_validate_webpkg_sha() {
  local pkg_file="$1"
  local sha_file="$2"
  local expected
  local actual

  if [ ! -s "$pkg_file" ]; then
    pco_nogo "ERR-02-WEBPKG-MISSING-001" "Downloaded Web package missing or empty: $pkg_file"
  fi

  if [ ! -s "$sha_file" ]; then
    pco_nogo "ERR-02-WEBPKG-SHA-MISSING-001" "Downloaded SHA256 file missing or empty: $sha_file"
  fi

  expected="$(awk 'NF {print $1; exit}' "$sha_file")"

  if ! printf '%s\n' "$expected" | grep -Eq '^[a-fA-F0-9]{64}$'; then
    pco_nogo "ERR-02-WEBPKG-SHA-FORMAT-001" "Invalid SHA256 format in $sha_file: $expected"
  fi

  actual="$(sha256sum "$pkg_file" | awk '{print $1}')"

  if [ "$actual" != "$expected" ]; then
    echo "Expected: $expected"
    echo "Actual:   $actual"
    pco_nogo "ERR-02-WEBPKG-SHA" "SHA256 validation failed"
  fi

  pco_go "SHA256 validation OK for $(basename "$pkg_file")"
}

fetch_official_web_package() {
  pco_step "01" "Fetch official PinCabOS Web package"

  mkdir -p "$WEB_PKG_CACHE_DIR"

  echo "Package URL:  $WEB_PKG_URL"
  echo "SHA URL:      $WEB_PKG_SHA_URL"
  echo "Manifest URL: $WEB_PKG_MANIFEST_URL"

  rm -f "$WEB_PKG_FILE.tmp" "$WEB_PKG_SHA_FILE.tmp" "$WEB_PKG_MANIFEST_FILE.tmp"

  curl -fL --retry 3 --connect-timeout 20 "$WEB_PKG_URL" -o "$WEB_PKG_FILE.tmp" \
    || pco_nogo "ERR-02-WEBPKG-DOWNLOAD" "Unable to download official Web package"

  mv -f "$WEB_PKG_FILE.tmp" "$WEB_PKG_FILE"

  if curl -fL --retry 2 --connect-timeout 15 "$WEB_PKG_SHA_URL" -o "$WEB_PKG_SHA_FILE.tmp"; then
    mv -f "$WEB_PKG_SHA_FILE.tmp" "$WEB_PKG_SHA_FILE"
    pincabos_validate_webpkg_sha "$WEB_PKG_FILE" "$WEB_PKG_SHA_FILE"
  else
    pco_warn "SHA file not available; package downloaded without SHA validation"
  fi

  if curl -fL --retry 2 --connect-timeout 15 "$WEB_PKG_MANIFEST_URL" -o "$WEB_PKG_MANIFEST_FILE.tmp"; then
    mv -f "$WEB_PKG_MANIFEST_FILE.tmp" "$WEB_PKG_MANIFEST_FILE"
    python3 -m json.tool "$WEB_PKG_MANIFEST_FILE" >/dev/null \
      && pco_go "Manifest JSON validation OK" \
      || pco_warn "Manifest downloaded but JSON validation failed"
  else
    pco_warn "Manifest not available"
  fi

  ls -lh "$WEB_PKG_FILE" "$WEB_PKG_SHA_FILE" "$WEB_PKG_MANIFEST_FILE" 2>/dev/null || true
  pco_go "Official Web package fetched"
}

validate_official_web_package() {
  pco_step "02" "Validate official Web package policy"

  [ -f "$WEB_PKG_FILE" ] || pco_nogo "ERR-02-WEBPKG-MISSING" "Missing package file: $WEB_PKG_FILE"

  echo
  echo "=== Package forbidden state/log/backup paths, must be empty ==="
  # Official engine WebPkg is allowed to ship VPX/VPinFE runtime assets under /opt/pincabos/apps.
  # It must not ship machine-local state, logs, backups, or user runtime config.
  if tar --zstd -tf "$WEB_PKG_FILE" | grep -E '(^\./|^)home/pinball/\.vpinball(/|$)|(^\./|^)home/pinball/\.config/vpinfe(/|$)|(^\./|^)opt/pincabos/logs(/|$)|(^\./|^)opt/pincabos/backups(/|$)|(^\./|^)opt/pincabos/config/backups(/|$)|(^\./|^)opt/pincabos/flags(/|$)|(^\./|^)opt/pincabos/state(/|$)'; then
    pco_nogo "ERR-02-WEBPKG-FORBIDDEN-PATH" "Official Web package contains forbidden machine-local state/log/backup paths"
  fi

  echo
  echo "=== Required Web package content ==="
  tar --zstd -tf "$WEB_PKG_FILE" | grep -E 'opt/pincabos/web/|opt/pincabos/media/|etc/sudoers.d/pincabos-|etc/systemd/system/pincabos-' | sed -n '1,180p' || true

  echo
  echo "=== Nginx package policy, must be absent in direct-port runtime ==="
  if tar --zstd -tf "$WEB_PKG_FILE" | grep -E '^\./?etc/nginx/'; then
    pco_nogo "ERR-02-WEBPKG-NGINX-FORBIDDEN-001" "Official direct-port Web package must not ship nginx files"
  fi

  rm -rf "$WEB_PKG_VERIFY_ROOT"
  mkdir -p "$WEB_PKG_VERIFY_ROOT"
  tar --zstd -xf "$WEB_PKG_FILE" -C "$WEB_PKG_VERIFY_ROOT"

  echo
  echo "=== Active forbidden GL usage in package, must be empty ==="
  if grep -RInE '/opt/pincabos/apps/vpinball/VPinballX[_]GL|exec .*VPinballX[_]GL|vpxbinpath.*VPinballX[_]GL|find .*VPinballX[_]GL' "$WEB_PKG_VERIFY_ROOT" 2>/dev/null; then
    pco_nogo "ERR-02-WEBPKG-GL" "Official Web package contains active forbidden GL usage"
  fi

  echo
  echo "=== WebApp Python syntax from package ==="
  if [ -f "$WEB_PKG_VERIFY_ROOT/opt/pincabos/web/app.py" ]; then
    python3 -m py_compile "$WEB_PKG_VERIFY_ROOT/opt/pincabos/web/app.py" \
      || pco_nogo "ERR-02-WEBPKG-APP-PY" "Package app.py failed Python compile"
    pco_go "Package app.py compile OK"
  else
    pco_nogo "ERR-02-WEBPKG-NO-APP" "Package missing /opt/pincabos/web/app.py"
  fi

  rm -rf "$WEB_PKG_VERIFY_ROOT"
  pco_go "Official Web package policy validation OK"
}

install_official_web_package() {
  pco_step "03" "Install official Web package to /"

  [ -f "$WEB_PKG_FILE" ] || pco_nogo "ERR-02-WEBPKG-MISSING" "Missing package file: $WEB_PKG_FILE"

  tar --zstd -xpf "$WEB_PKG_FILE" -C /

  pco_go "Official Web package extracted to /"
}

assert_stage_ready() {
  pco_step "01" "Validate clean engine module from /tmp"

  [ -d "$PCO_STAGE" ] || pco_nogo "ERR-02-STAGE-001" "Missing clean engine module: $PCO_STAGE"

  if [ -d "$PCO_QUAR" ]; then
    pco_go "Quarantine exists and will not be imported: $PCO_QUAR"
  else
    pco_warn "No quarantine directory found"
  fi

  if grep -RInE 'VPinballX[_]GL|vpinball[_]gl|VPinball[_]GL|VPINBALL[_]GL' "$PCO_STAGE" 2>/dev/null \
    | grep -v '/_quarantine_forbidden_gl/' >/tmp/pincabos-02-stage-gl-leftovers.txt; then
    sed -n '1,160p' /tmp/pincabos-02-stage-gl-leftovers.txt
    pco_nogo "ERR-02-STAGE-GL" "Forbidden GL reference found outside quarantine"
  fi

  pco_go "Clean engine module accepted: $PCO_STAGE"
  du -sh "$PCO_STAGE" || true
}

backup_live_system() {
  pco_step "02" "Backup live PinCabOS targets"

  mkdir -p "$PCO_BACKUP"

  for p in \
    "$WEB_DIR" \
    /opt/pincabos/media \
    /opt/pincabos/tools \
    /opt/pincabos/scripts \
    /opt/pincabos/bin \
    /opt/pincabos/config \
    "$VPX_INI" \
    "$VPINFE_INI" \
    /etc/nginx/sites-available/default \
    /etc/nginx/sites-enabled/default \
    /etc/nginx/sites-available/pincabos-web \
    /etc/nginx/sites-available/pincabos-web.conf \
    /etc/nginx/sites-enabled/pincabos-web \
    /etc/nginx/sites-enabled/pincabos-web.conf \
    /etc/systemd/system/pincabos-web.service \
    /etc/systemd/system/pincabos-console.service \
    /etc/systemd/system/pincabos-vpinfe.service \
    /etc/sudoers.d/pincabos-web
  do
    if [ -e "$p" ]; then
      mkdir -p "$PCO_BACKUP$(dirname "$p")"
      cp -a "$p" "$PCO_BACKUP$p" 2>/dev/null || true
      echo "BACKUP: $p"
    fi
  done

  pco_go "Backup root: $PCO_BACKUP"
}

import_engine_module() {
  pco_step "03" "Import engine module from /tmp"

  mkdir -p /opt/pincabos

  rsync -a "$PCO_STAGE"/ / \
    --exclude='_quarantine_forbidden_gl/***' \
    --exclude='opt/pincabos/apps/vpinball/***' \
    --exclude='opt/pincabos/apps/vpx/***' \
    --exclude='home/pinball/.vpinball/***' \
    --exclude='home/pinball/.config/vpinfe/***' \
    --exclude='opt/pincabos/config/vpinfe/***' \
    --exclude='opt/pincabos/config/dof/***' \
    --exclude='opt/pincabos/config/screens/***' \
    --exclude='opt/pincabos/config/backups/***' \
    --exclude='opt/pincabos/config/ssh-backup-*' \
    --exclude='opt/pincabos/config/*calibration*.json' \
    --exclude='opt/pincabos/config/*display*.json' \
    --exclude='opt/pincabos/config/vpx-engine.json' \
    --exclude='opt/pincabos/config/audio-router.json' \
    --exclude='opt/pincabos/config/firstrun.json' \
    --exclude='opt/pincabos/config/pincabos-update.json' \
    --exclude='usr/local/bin/00-install-admin.sh' \
    --exclude='usr/local/bin/01-install-system.sh' \
    --exclude='usr/local/bin/02-install-engine.sh' \
    --exclude='usr/local/bin/03-install-check.sh' \
    --exclude='usr/local/bin/update-vpx.sh' \
    --exclude='opt/pincabos/tools/update-vpx.sh' \
    --exclude='usr/local/bin/pincabos-run-vpx' \
    --exclude='opt/pincabos/bin/vpx.sh' \
    --exclude='opt/pincabos/bin/pincabos-vpx-launch-with-pinmame-overlay.sh' \
    --exclude='opt/pincabos/tools/pincabos-ensure-vpx-overlay-runtime.sh' \
    --exclude='opt/pincabos/web/app.py' \
    --exclude='opt/pincabos/tools/pincabos-apply-update.sh' \
    --exclude='opt/pincabos/tools/pincabos-smart-archive-import.py' \
    --exclude='usr/local/bin/pincabos-apply-update.sh'

  pco_go "Engine module imported without VPX runtime, user configs, old GL files or quarantine"
}

sanitize_file_from_quarantine() {
  local rel="$1"
  local dst="$2"
  local src="$PCO_QUAR/$rel"

  [ -f "$src" ] || return 1

  mkdir -p "$(dirname "$dst")"
  cp -a "$src" "$dst"

  sed -Ei \
    -e 's|VPinballX[_]GL|VPinballX-BGFX|g' \
    -e 's|vpinball[_]gl|vpinballX-BGFX|g' \
    -e 's|VPinball[_]GL|VPinballX-BGFX|g' \
    -e 's|VPINBALL[_]GL|VPINBALL_BGFX|g' \
    "$dst"

  if grep -qE 'VPinballX[_]GL|vpinball[_]gl|VPinball[_]GL|VPINBALL[_]GL' "$dst"; then
    rm -f "$dst"
    return 1
  fi

  return 0
}

restore_or_create_webapp() {
  pco_step "04" "Restore WebApp and sanitize app.py"

  mkdir -p "$WEB_DIR/static"

  if sanitize_file_from_quarantine "opt/pincabos/web/app.py" "$WEB_DIR/app.py"; then
    if python3 -m py_compile "$WEB_DIR/app.py"; then
      pco_go "Sanitized app.py restored from quarantine"
    else
      mv "$WEB_DIR/app.py" "$WEB_DIR/app.py.bad-sanitized-$TS" || true
      pco_warn "Sanitized app.py failed Python compile; creating minimal clean WebApp"
    fi
  fi

  if [ ! -f "$WEB_DIR/app.py" ]; then
    cat >"$WEB_DIR/app.py" <<'PYAPP'
#!/usr/bin/env python3
# PinCabOS minimal WebApp
# Created by Karots Sugarpie

import os
from flask import Flask, jsonify

app = Flask(__name__)

@app.get("/")
def index():
    return """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>PinCabOS</title>
  <style>
    body { background:#050008; color:#eee; font-family:Arial,sans-serif; padding:38px; }
    .card { border:1px solid #6d2f91; border-radius:16px; padding:24px; max-width:920px; }
    h1 { color:#ff9d2e; }
    code { color:#8fffd2; }
  </style>
</head>
<body>
  <div class="card">
    <h1>PinCabOS WebApp</h1>
    <p>Engine worker completed. WebApp is online.</p>
    <p>VPX runtime policy: <code>BGFX only</code>.</p>
    <p>GL runtime is forbidden.</p>
  </div>
</body>
</html>
"""

@app.get("/health")
def health():
    return jsonify(ok=True, service="pincabos-web", vpx_policy="BGFX only")
PYAPP
    pco_go "Minimal clean app.py created"
  fi

  chmod 755 "$WEB_DIR/app.py"
}

restore_sanitized_tools() {
  pco_step "05" "Restore sanitized optional tools from quarantine"

  if sanitize_file_from_quarantine "opt/pincabos/tools/pincabos-apply-update.sh" "/opt/pincabos/tools/pincabos-apply-update.sh"; then
    chmod 755 /opt/pincabos/tools/pincabos-apply-update.sh
    pco_go "Sanitized pincabos-apply-update.sh restored"
  else
    pco_warn "pincabos-apply-update.sh not restored"
  fi

  if sanitize_file_from_quarantine "opt/pincabos/tools/pincabos-smart-archive-import.py" "/opt/pincabos/tools/pincabos-smart-archive-import.py"; then
    chmod 755 /opt/pincabos/tools/pincabos-smart-archive-import.py
    pco_go "Sanitized pincabos-smart-archive-import.py restored"
  else
    pco_warn "pincabos-smart-archive-import.py not restored"
  fi
}

install_plymouth_and_wallpapers() {
  pco_go "RUN_02 skips final Plymouth; RUN_03 applies final loading theme once"
}

write_global_paths_config() {
  pco_step "07" "Write global default paths"

  mkdir -p /opt/pincabos/config /opt/pincabos/config/vpinfe "$(dirname "$VPX_INI")" "$TABLES_DIR" "$ROMS_DIR" "$VPX_DIR"

  cat >/opt/pincabos/config/pincabos-paths.json <<EOF_PATHS
{
  "created_by": "Karots Sugarpie",
  "paths": {
    "root": "/opt/pincabos",
    "web": "/opt/pincabos/web",
    "web_venv": "/opt/pincabos/web/.venv",
    "vpx_dir": "$VPX_DIR",
    "vpx_bin": "$VPX_BIN",
    "vpx_ini": "$VPX_INI",
    "tables": "$TABLES_DIR",
    "roms": "$ROMS_DIR",
    "vpinfe_dir": "$VPINFE_DIR",
    "vpinfe_ini": "$VPINFE_INI",
    "logs": "/opt/pincabos/logs",
    "config": "/opt/pincabos/config"
  },
  "vpx_policy": "BGFX only; VPinballX[_]GL forbidden"
}
EOF_PATHS

  pco_go "Global paths written: /opt/pincabos/config/pincabos-paths.json"
}


pco_import_golden_runtime_package() {
  pco_step "02G" "Golden runtime package"
  pco_info "Golden runtime package is deprecated for Alpha 1.6 dev."
  pco_info "Using normal BGFX/VPinFE runtime package flow instead."
  pco_go "Golden runtime skipped cleanly"
  return 0
}




ensure_vpx_runtime_paths() {
  pco_step "08" "Create VPX BGFX runtime paths and launcher"

  mkdir -p "$VPX_DIR" "$VPX_DIR/current" "$VPX_ALT_DIR" "$TABLES_DIR" "$ROMS_DIR" /opt/pincabos/bin
  ln -sfn "$VPX_DIR" "$VPX_ALT_DIR"

  local bgfx_bin=""
  bgfx_bin="$(find "$VPX_DIR" -type f \( -iname 'VPinballX-BGFX' -o -iname 'vpinballX-BGFX' -o -iname 'VPinballX_BGFX' -o -iname 'vpinballX_BGFX' \) -perm /111 2>/dev/null | head -n1 || true)"

  if [ -n "$bgfx_bin" ]; then
    canonical="$VPX_DIR/current/VPinballX-BGFX"

    mkdir -p "$VPX_DIR/current"

    # Never replace the real canonical binary with a symlink to itself.
    if [ "$bgfx_bin" != "$canonical" ]; then
      if [ ! -e "$canonical" ] || [ -L "$canonical" ]; then
        rm -f "$canonical"
        ln -sfn "$bgfx_bin" "$canonical"
      fi
    fi

    ln -sfn "$canonical" "$VPX_DIR/VPinballX-BGFX"
    ln -sfn "$VPX_DIR/VPinballX-BGFX" "$VPX_DIR/VPinballX"

    if [ -L "$canonical" ] && [ "$(readlink "$canonical")" = "$canonical" ]; then
      pco_nogo "ERR-02-VPX-SELF-SYMLINK" "Canonical VPX BGFX binary is a self-symlink: $canonical"
    fi

    pco_go "BGFX binary normalized: $bgfx_bin"
  fi

  cat >"$VPX_BIN" <<'EOF_VPX'
#!/usr/bin/env bash
set -Eeuo pipefail

export SDL_VIDEODRIVER="${SDL_VIDEODRIVER:-x11}"

for candidate in \
  /opt/pincabos/apps/vpinball/current/VPinballX-BGFX \
  /opt/pincabos/apps/vpinball/VPinballX-BGFX \
  /opt/pincabos/apps/vpinball/vpinballX-BGFX \
  /opt/pincabos/apps/vpinball/VPinballX_BGFX \
  /opt/pincabos/apps/vpinball/vpinballX_BGFX
do
  if [ -x "$candidate" ]; then
    exec "$candidate" "$@"
  fi
done

echo "NOGO: VPX BGFX binary not installed under /opt/pincabos/apps/vpinball" >&2
exit 127
EOF_VPX
  chmod 755 "$VPX_BIN"
  ln -sfn "$VPX_BIN" /usr/local/bin/pincabos-vpx
  ln -sfn "$VPX_BIN" /usr/local/bin/vpx-pincabos

  if [ -n "$bgfx_bin" ]; then
    pco_go "VPX launcher ready: $VPX_BIN"
  else
    pco_warn "No BGFX VPX binary found yet. Launcher is ready; pkg-vpx-bgfx-runtime.sh must install the runtime."
  fi
}

ensure_vpx_ini() {
  pco_step "09" "Ensure VPX INI defaults without destroying existing file"

  mkdir -p "$(dirname "$VPX_INI")"

  if [ ! -f "$VPX_INI" ]; then
    cat >"$VPX_INI" <<'EOF_INI'
; PinCabOS - VPinballX.ini minimal defaults
; Created by Karots Sugarpie

[Player]
FullScreen = 1

[Controller]
DOFPlugin = 1
B2SPlugins = 1

[Displays]
tablescreenid = 0
bgscreenid = 1
dmdscreenid = 2
EOF_INI
    pco_go "Created: $VPX_INI"
  else
    cp -a "$VPX_INI" "$VPX_INI.backup-run02-$TS" 2>/dev/null || true
    pco_go "Existing VPX INI preserved: $VPX_INI"
  fi
}

ensure_vpinfe_ini() {
  pco_step "10" "Ensure VPinFE INI global defaults"

  mkdir -p "$(dirname "$VPINFE_INI")"

  if [ ! -f "$VPINFE_INI" ]; then
    cat >"$VPINFE_INI" <<EOF_VPINFE
[Settings]
tablerootdir = $TABLES_DIR
vpxbinpath = $VPX_BIN
vpxinipath = $VPX_INI
themeassetsport = 8001
manageruiport = 8000

[PinCabOS]
vpxbinpath = $VPX_BIN
vpxinipath = $VPX_INI
vpxdir = $VPX_DIR
vpinfedir = $VPINFE_DIR
romsdir = $ROMS_DIR
EOF_VPINFE
    pco_go "Created: $VPINFE_INI"
  else
    cp -a "$VPINFE_INI" "$VPINFE_INI.backup-run02-$TS" 2>/dev/null || true

    python3 - "$VPINFE_INI" "$VPX_BIN" "$TABLES_DIR" "$VPX_INI" "$VPX_DIR" "$VPINFE_DIR" "$ROMS_DIR" <<'PY'
import configparser, sys
from pathlib import Path

ini = Path(sys.argv[1])
vpxbin, tables, vpxini, vpxdir, vpinfedir, roms = sys.argv[2:]

cp = configparser.ConfigParser()
cp.optionxform = str
cp.read(ini)

for sec in ("Settings", "PinCabOS"):
    if not cp.has_section(sec):
        cp.add_section(sec)

cp.set("Settings", "tablerootdir", tables)
cp.set("Settings", "vpxbinpath", vpxbin)
cp.set("Settings", "vpxinipath", vpxini)
cp.set("Settings", "themeassetsport", "8001")
cp.set("Settings", "manageruiport", "8000")

cp.set("PinCabOS", "vpxbinpath", vpxbin)
cp.set("PinCabOS", "vpxinipath", vpxini)
cp.set("PinCabOS", "vpxdir", vpxdir)
cp.set("PinCabOS", "vpinfedir", vpinfedir)
cp.set("PinCabOS", "romsdir", roms)

with ini.open("w") as f:
    cp.write(f)
PY
    pco_go "Merged VPinFE defaults into existing INI"
  fi
}

rebuild_python_venv() {
  pco_step "11" "Rebuild Python WebApp venv"

  mkdir -p "$WEB_DIR"

  rm -rf "$WEB_VENV"
  python3 -m venv "$WEB_VENV"
  "$WEB_VENV/bin/python" -m pip install --upgrade pip wheel setuptools

  if [ -f "$WEB_DIR/requirements.txt" ]; then
    "$WEB_VENV/bin/pip" install -r "$WEB_DIR/requirements.txt" || true
  fi

  "$WEB_VENV/bin/pip" install flask requests pyyaml psutil || true

  pco_go "Python venv rebuilt: $WEB_VENV"
}


write_nginx() {
  pco_step "12" "Disable nginx runtime for official direct ports"

  rm -f /etc/nginx/sites-enabled/default \
        /etc/nginx/sites-enabled/pincabos-web \
        /etc/nginx/sites-enabled/pincabos-web.conf 2>/dev/null || true

  if systemctl list-unit-files nginx.service >/dev/null 2>&1; then
    systemctl stop nginx.service 2>/dev/null || true
    systemctl disable nginx.service 2>/dev/null || true
    systemctl mask nginx.service 2>/dev/null || true
    pco_go "nginx disabled/masked; PinCabOS runtime uses direct ports"
  else
    pco_go "nginx.service absent; direct ports model OK"
  fi

  pco_go "PinCabOS direct ports OK: WebApp=80 Console=8090 VPinFE=8000 VPinFE-API=8001"
}


write_systemd() {
  pco_step "13" "Rewrite systemd services"

  mkdir -p /etc/systemd/system/pincabos-webapp.service.d /etc/systemd/system/pincabos-web.service.d /opt/pincabos/tools

  cat >/opt/pincabos/tools/run-vpinfe.sh <<'EOF_RUN_VPINFE'
#!/usr/bin/env bash
# PinCabOs-File created by Karots Sugarpie
# Created by Karots Sugarpie
# PINCABOS_SCRIPT_NAME="run-vpinfe.sh"
# PINCABOS_SCRIPT_ROLE="Launch VPinFE binary or Python main.py with PinCabOS config"
# PINCABOS_SCRIPT_REQUIRES_FILES="/opt/pincabos/apps/frontend/vpinfe/current/main.py /opt/pincabos/config/vpinfe/vpinfe.ini"
# PINCABOS_SCRIPT_REQUIRES_COMMANDS="bash"

set -Eeuo pipefail

export HOME="${HOME:-/home/pinball}"
export USER="${USER:-pinball}"
export LOGNAME="${LOGNAME:-pinball}"
export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-/home/pinball/.Xauthority}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/1000}"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/1000/bus}"
export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-/home/pinball/.config}"

ROOT="/opt/pincabos/apps/frontend/vpinfe"
CUR="$ROOT/current"
CFG="/opt/pincabos/config/vpinfe/vpinfe.ini"
LOG="/opt/pincabos/logs/vpinfe-launch.log"

mkdir -p /opt/pincabos/logs
touch "$LOG" 2>/dev/null || true
chown pinball:pinball "$LOG" 2>/dev/null || true

{
  echo "────────────────────────────────────────────────────────────────"
  echo "PinCabOS VPinFE launch $(date -Is)"
  echo "USER=$(id -un 2>/dev/null || true)"
  echo "DISPLAY=$DISPLAY"
  echo "XAUTHORITY=$XAUTHORITY"
  echo "XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR"
  echo "XDG_CONFIG_HOME=$XDG_CONFIG_HOME"
  echo "CFG=$CFG"
} >>"$LOG"

for candidate in \
  "$CUR/vpinfe" \
  "$CUR/VPinFE" \
  "$ROOT/vpinfe" \
  "$ROOT/VPinFE"
do
  if [ -x "$candidate" ]; then
    echo "BIN=$candidate" >>"$LOG"
    cd "$(dirname "$candidate")"
    exec "$candidate" "$@"
  fi
done

PY="$CUR/.venv/bin/python"
MAIN="$CUR/main.py"

if [ ! -x "$PY" ]; then
  echo "NOGOOD: VPinFE Python missing/executable: $PY" >>"$LOG"
  exit 1
fi

if [ ! -f "$MAIN" ]; then
  echo "NOGOOD: VPinFE main.py missing: $MAIN" >>"$LOG"
  exit 1
fi

if [ ! -f "$CFG" ]; then
  echo "NOGOOD: VPinFE config missing: $CFG" >>"$LOG"
  exit 1
fi

echo "PYTHON=$PY" >>"$LOG"
echo "MAIN=$MAIN" >>"$LOG"
echo "MODE=python-main-visible" >>"$LOG"

# Wait briefly for LightDM/Openbox X session so VPinFE can open Chromium frontend.
for i in $(seq 1 30); do
  if [ -S /tmp/.X11-unix/X0 ]; then
    break
  fi
  echo "WAIT_X=$i no /tmp/.X11-unix/X0 yet" >>"$LOG"
  sleep 1
done

# Prefer pinball Xauthority when available; fallback to LightDM root auth.
if [ -f /home/pinball/.Xauthority ]; then
  export XAUTHORITY=/home/pinball/.Xauthority
elif [ -f /var/run/lightdm/root/:0 ]; then
  export XAUTHORITY=/var/run/lightdm/root/:0
fi

echo "FINAL_DISPLAY=$DISPLAY" >>"$LOG"
echo "FINAL_XAUTHORITY=$XAUTHORITY" >>"$LOG"

cd "$CUR"
exec "$PY" "$MAIN" --configfile "$CFG"
EOF_RUN_VPINFE

  chmod 0755 /opt/pincabos/tools/run-vpinfe.sh
  chown pinball:pinball /opt/pincabos/tools/run-vpinfe.sh 2>/dev/null || true

  mkdir -p /home/pinball/.config/vpinfe
  touch /home/pinball/.config/vpinfe/vpinfe.log
  chown -R pinball:pinball /home/pinball/.config/vpinfe
  chmod 0755 /home/pinball/.config /home/pinball/.config/vpinfe
  chmod 0644 /home/pinball/.config/vpinfe/vpinfe.log

  pco_go "VPinFE Python runner and pinball config ownership prepared"

  cat >/etc/systemd/system/pincabos-webapp.service <<EOF_WEBAPP
[Unit]
Description=PinCabOS WebApp
Documentation=https://pincabos.cc/
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pinball
Group=pinball
WorkingDirectory=$WEB_DIR
Environment=PYTHONUNBUFFERED=1
Environment=PINCABOS_WEB_HOST=0.0.0.0
Environment=PINCABOS_WEB_PORT=80
Environment=PCO_WEB_HOST=0.0.0.0
Environment=PCO_WEB_PORT=80
AmbientCapabilities=CAP_NET_BIND_SERVICE
NoNewPrivileges=false
ExecStart=$WEB_VENV/bin/python $WEB_DIR/app.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF_WEBAPP

  cat >/etc/systemd/system/pincabos-web.service <<EOF_WEB_LEGACY
[Unit]
Description=PinCabOS WebApp Legacy Alias
After=pincabos-webapp.service
Requires=pincabos-webapp.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/true

[Install]
WantedBy=multi-user.target
EOF_WEB_LEGACY

  cat >/etc/systemd/system/pincabos-webapp.service.d/10-pincabos-web-port.conf <<'EOF_WEB_DROPIN'
[Service]
Environment=PINCABOS_WEB_HOST=0.0.0.0
Environment=PINCABOS_WEB_PORT=80
Environment=PCO_WEB_HOST=0.0.0.0
Environment=PCO_WEB_PORT=80
EOF_WEB_DROPIN

  cat >/etc/systemd/system/pincabos-web.service.d/10-pincabos-legacy.conf <<'EOF_WEB_LEGACY_DROPIN'
[Unit]
Documentation=https://pincabos.cc/
EOF_WEB_LEGACY_DROPIN

  cat >/etc/default/ttyd <<'EOF_TTYD_DEFAULT'
# /etc/default/ttyd
# PinCabOS official console backend.
TTYD_OPTIONS="-W -i lo -p 8090 -O login"
EOF_TTYD_DEFAULT

cat >/etc/systemd/system/pincabos-console.service <<'EOF_CONSOLE'
[Unit]
Description=PinCabOS Console ttyd
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/ttyd -p 8090 -W /bin/bash
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF_CONSOLE

  cat >/etc/systemd/system/pincabos-vpinfe.service <<EOF_VPINFE
[Unit]
Description=PinCabOS VPinFE
After=network-online.target lightdm.service graphical.target
Wants=network-online.target lightdm.service

[Service]
Type=simple
User=pinball
Group=pinball
WorkingDirectory=$VPINFE_DIR
ExecStart=/opt/pincabos/tools/run-vpinfe.sh
Restart=always
RestartSec=3

[Install]
WantedBy=graphical.target
EOF_VPINFE

  cat >/etc/systemd/system/pincabos-frontend.service <<EOF_FRONTEND
[Unit]
Description=PinCabOS Frontend Compatibility Wrapper
Documentation=https://pincabos.cc/
After=pincabos-vpinfe.service
Requires=pincabos-vpinfe.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/true

[Install]
WantedBy=graphical.target
EOF_FRONTEND

  systemctl daemon-reload
  systemctl enable pincabos-webapp.service pincabos-web.service >/dev/null 2>&1 || true
  # RUN_02 may execute from a detached WebApp child process.
  # Never restart its parent here: final reboot applies updated services safely.
  pco_go "WebApp restart deferred to final reboot"

  if command -v ttyd >/dev/null 2>&1; then
    systemctl enable pincabos-console.service >/dev/null 2>&1 || true
    systemctl restart pincabos-console.service || true


echo
echo "=== Disable raw ttyd.service; PinCabOS console owns ttyd on port 8090 ==="
systemctl stop ttyd.service >/dev/null 2>&1 || true
systemctl disable ttyd.service >/dev/null 2>&1 || true
systemctl mask ttyd.service >/dev/null 2>&1 || true
systemctl reset-failed ttyd.service >/dev/null 2>&1 || true
systemctl enable pincabos-console.service >/dev/null 2>&1 || true
systemctl restart pincabos-console.service >/dev/null 2>&1 || true

  else
    pco_warn "ttyd missing; console service created but not started"
  fi

  systemctl enable pincabos-vpinfe.service pincabos-frontend.service >/dev/null 2>&1 || true

  pco_go "Systemd services written: webapp, legacy web alias, console, vpinfe, frontend wrapper"
}

install_sudoers() {
  pco_step "14" "Install sudoers"

  mkdir -p /etc/sudoers.d

  if [ -d "$PCO_STAGE/etc/sudoers.d" ]; then
    find "$PCO_STAGE/etc/sudoers.d" -maxdepth 1 -type f ! -name README -print0 | while IFS= read -r -d '' f; do
      dst="/etc/sudoers.d/$(basename "$f")"
      cp -f "$f" "$dst"
      chmod 440 "$dst"
      if visudo -cf "$dst"; then
        echo "GO: sudoers OK: $dst"
      else
        rm -f "$dst"
        pco_nogo "ERR-02-SUDOERS" "Invalid sudoers rejected: $f"
      fi
    done
  fi

  if [ -x /opt/pincabos/tools/install-pincabos-sudoers.sh ]; then
    /opt/pincabos/tools/install-pincabos-sudoers.sh || true
  fi

  pco_go "Sudoers installed"
}

write_path_commands() {
  pco_step "15" "Recreate PATH commands"

  ln -sfn /opt/pincabos/bin/vpx.sh /usr/local/bin/pincabos-vpx
  ln -sfn /opt/pincabos/bin/vpx.sh /usr/local/bin/vpx-pincabos

  for f in /opt/pincabos/tools/*.sh /opt/pincabos/scripts/*.sh /opt/pincabos/bin/*.sh; do
    [ -f "$f" ] || continue
    chmod 755 "$f" || true
    base="$(basename "$f")"
    name="${base%.sh}"
    case "$name" in
      update-vpx|02-install-engine|01-install-system|00-install-admin|03-install-check)
        continue
        ;;
    esac
    ln -sfn "$f" "/usr/local/bin/$name" 2>/dev/null || true
  done

  ln -sfn /opt/pincabos/install/02-install-engine.sh /usr/local/bin/02-install-engine

  pco_go "PATH commands refreshed"
}

set_permissions() {
  pco_step "16" "Set permissions and ownership"

  mkdir -p /opt/pincabos/logs /opt/pincabos/config "$TABLES_DIR" "$ROMS_DIR"

  chmod 755 /opt/pincabos/bin/*.sh 2>/dev/null || true
  chmod 755 /opt/pincabos/tools/*.sh 2>/dev/null || true
  chmod 755 /opt/pincabos/scripts/*.sh 2>/dev/null || true

  chown -R pinball:pinball /opt/pincabos 2>/dev/null || true
  chown -R pinball:pinball /home/pinball 2>/dev/null || true

  pco_go "Permissions completed"
}

final_validation() {
  pco_step "17" "Final validation"

  echo
  echo "=== Forbidden GL scan in live PinCabOS critical files ==="
  if grep -RInE 'VPinballX[_]GL|vpinball[_]gl|VPinball[_]GL|VPINBALL[_]GL' \
    /opt/pincabos/bin \
    /opt/pincabos/tools \
    /opt/pincabos/web \
    /opt/pincabos/config \
    2>/dev/null | sed -n '1,160p'; then
    pco_warn "GL text still exists in live files. Review above."
  else
    pco_go "No forbidden GL text in live critical files"
  fi

  echo

  echo
  echo "=== Services ==="
    systemctl is-active pincabos-webapp.service 2>/dev/null || true
  systemctl is-active pincabos-web.service 2>/dev/null || true

  echo
  echo "=== Paths ==="
  echo "WebApp:       $WEB_DIR"
  echo "Web venv:     $WEB_VENV"
  echo "VPX dir:      $VPX_DIR"
  echo "VPX launcher: $VPX_BIN"
  echo "VPX INI:      $VPX_INI"
  echo "Tables:       $TABLES_DIR"
  echo "VPinFE INI:   $VPINFE_INI"
  echo "Log:          $LOG_FILE"

  pco_go "02 engine worker completed"
}



pincabos_write_nginx_canonical_vhost() {
  pco_go "nginx canonical vhost skipped; direct-port runtime owns WebApp=80"
}

pincabos_clean_nginx_enabled_sites() {
  rm -f /etc/nginx/sites-enabled/default \
        /etc/nginx/sites-enabled/pincabos-web \
        /etc/nginx/sites-enabled/pincabos-web.conf 2>/dev/null || true
  pco_go "nginx enabled sites removed if present; direct-port runtime owns WebApp=80"
}

pincabos_assert_nginx_no_active_default_server() {
  pco_go "nginx runtime disabled; no active nginx guard required"
}

main() {
  # Detached WebApp/systemd launches may not have a usable terminal.
  if [ -z "${TERM:-}" ] || [ "${TERM:-}" = "unknown" ]; then
    export TERM=xterm
  fi
  clear 2>/dev/null || true
  pco_title
  assert_no_run_flags_management

  pco_step "A1" "Install dependencies"
  apt_install \
    ca-certificates curl wget jq tar zstd rsync unzip xz-utils file sudo \
    python3 python3-venv python3-pip python3-requests python3-yaml \
    

  if apt-cache policy ttyd 2>/dev/null | awk '/Candidate:/ {print $2}' | grep -vqE '^(\(none\)|)$'; then
    apt-get install -y ttyd || pco_warn "Optional ttyd package install failed; console service will be created but may stay inactive"
  else
    pco_warn "Optional ttyd package has no APT candidate on this Ubuntu release"
  fi

  fetch_official_web_package
  validate_official_web_package
  backup_live_system
  install_official_web_package
  restore_or_create_webapp
  restore_sanitized_tools
  pco_go "RUN_02 skips final Plymouth; RUN_03 is the single owner"
  write_global_paths_config
  pco_import_golden_runtime_package || true
  ensure_vpx_runtime_paths
  ensure_vpx_ini
  ensure_vpinfe_ini
  rebuild_python_venv
  write_nginx
  write_systemd
  install_sudoers
  write_path_commands
  set_permissions
  final_validation
}

main "$@"
