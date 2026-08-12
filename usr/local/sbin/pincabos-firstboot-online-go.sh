#!/usr/bin/env bash
set -Eeuo pipefail

clear 2>/dev/null || true

LOG_DIR="/opt/pincabos/logs"
INSTALL_DIR="/opt/pincabos/install"
STATE_DIR="/opt/pincabos/state"
FLAGS_DIR="/opt/pincabos/flags"
TMP_DIR="/opt/pincabos/tmp"
BASE_URL="${PINCABOS_INSTALL_URL:-https://ins.pincabos.cc/install}"
LOG="$LOG_DIR/firstboot-online-go-$(date +%Y%m%d-%H%M%S).log"

mkdir -p "$LOG_DIR" "$INSTALL_DIR" "$STATE_DIR" "$FLAGS_DIR" "$TMP_DIR"

exec > >(tee -a "$LOG") 2>&1

echo "────────────────────────────────────────────────────────────────"
echo " PinCabOS - Firstboot Online GO Bootstrap"
echo "────────────────────────────────────────────────────────────────"
echo "Log: $LOG"
echo "Base URL: $BASE_URL"

if [ "$(id -u)" -ne 0 ]; then
  echo "NOGO: must run as root"
  exit 1
fi

echo
echo "=== 1) Network sanity ==="
ip -4 -br addr show scope global 2>/dev/null || true
ip route 2>/dev/null | sed -n '1,20p' || true
grep -h '^nameserver ' /etc/resolv.conf 2>/dev/null || true

echo
echo "=== 2) Downloader detection ==="
if command -v curl >/dev/null 2>&1; then
  DL="curl"
  echo "GO: curl available"
elif command -v wget >/dev/null 2>&1; then
  DL="wget"
  echo "GO: wget available"
else
  echo "NOGO: curl/wget absent"
  exit 1
fi

download() {
  local url="$1"
  local dest="$2"
  local tmp="$dest.tmp"

  mkdir -p "$(dirname "$dest")"
  rm -f "$tmp"

  echo "+ download $url"

  if [ "$DL" = "curl" ]; then
    curl -fsSL --retry 5 --connect-timeout 20 "$url" -o "$tmp"
  else
    wget -qO "$tmp" "$url"
  fi

  if [ ! -s "$tmp" ]; then
    echo "NOGO: downloaded file empty: $url"
    rm -f "$tmp"
    return 1
  fi

  mv -f "$tmp" "$dest"
  chmod +x "$dest" 2>/dev/null || true
}

echo
echo "=== 3) Download latest online installer files ==="
download "$BASE_URL/go-pincabos.sh" "$INSTALL_DIR/go-pincabos.sh"
download "$BASE_URL/help-pincabos.sh" "$INSTALL_DIR/help-pincabos.sh" || true
download "$BASE_URL/01-install-system.sh" "$INSTALL_DIR/01-install-system.sh" || true
download "$BASE_URL/02-install-engine.sh" "$INSTALL_DIR/02-install-engine.sh" || true
download "$BASE_URL/03-install-check.sh" "$INSTALL_DIR/03-install-check.sh" || true
download "$BASE_URL/install.json" "$INSTALL_DIR/install.json" || true
download "$BASE_URL/version.json" "$INSTALL_DIR/version.json" || true

echo
echo "=== 4) Syntax validation latest go ==="
bash -n "$INSTALL_DIR/go-pincabos.sh"

echo
echo "=== 5) Command links ==="
ln -sfn "$INSTALL_DIR/go-pincabos.sh" /usr/local/bin/go-pincabos
ln -sfn "$INSTALL_DIR/help-pincabos.sh" /usr/local/bin/help-pincabos 2>/dev/null || true
ln -sfn "$INSTALL_DIR/01-install-system.sh" /usr/local/bin/01-install-system 2>/dev/null || true
ln -sfn "$INSTALL_DIR/02-install-engine.sh" /usr/local/bin/02-install-engine 2>/dev/null || true
ln -sfn "$INSTALL_DIR/03-install-check.sh" /usr/local/bin/03-install-check 2>/dev/null || true
hash -r 2>/dev/null || true

echo
echo "=== 6) devISO flag status ==="
if [ -f "$STATE_DIR/deviso-base-installed" ]; then
  echo "GO: devISO base flag present: $STATE_DIR/deviso-base-installed"
elif [ -f "$FLAGS_DIR/deviso-base-installed" ]; then
  echo "GO: devISO base flag present: $FLAGS_DIR/deviso-base-installed"
else
  echo "INFO: no devISO flag found; online go will run full Ubuntu Server flow"
fi

echo
echo "=== 7) Execute latest online go ==="
exec bash "$INSTALL_DIR/go-pincabos.sh"
