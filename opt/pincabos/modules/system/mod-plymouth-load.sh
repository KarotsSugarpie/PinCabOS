#!/usr/bin/env bash
# PINCABOS_SCRIPT_NAME="mod-plymouth-load.sh"
# PINCABOS_SCRIPT_DESCRIPTION="Installe et applique le thème Plymouth final/loading PinCabOS depuis package .tar.zst"
# PINCABOS_SCRIPT_REQUIRES_PACKAGES="plymouth plymouth-themes zstd tar"
# PINCABOS_SCRIPT_REQUIRES_COMMANDS="/usr/bin/bash /usr/bin/tar /usr/bin/sha256sum /usr/bin/update-alternatives /usr/sbin/update-initramfs"
# PINCABOS_SCRIPT_REQUIRES_FILES="/opt/pincabos/modules/system/assets/plymouth/pkg-plymouth-load.tar.zst"
# PINCABOS_SCRIPT_REQUIRES_DIRS="/opt/pincabos/modules/system/assets/plymouth /usr/share/plymouth/themes /opt/pincabos/backups"
# PINCABOS_SCRIPT_TOUCHES="/usr/share/plymouth/themes/pincabos /usr/share/plymouth/themes/default.plymouth /boot/initrd*"
# Created by Karots Sugarpie

set +e

ORANGE="\033[38;5;208m"
YELLOW="\033[33m"
GREEN="\033[32m"
RED="\033[31m"
NC="\033[0m"

clear
echo -e "${ORANGE}────────────────────────────────────────────────────────────────${NC}"
echo -e "${ORANGE} PinCabOS - Module Plymouth LOADING FINAL${NC}"
echo -e "${ORANGE}────────────────────────────────────────────────────────────────${NC}"

THEME_NAME="pincabos"
PKG="/opt/pincabos/modules/system/assets/plymouth/pkg-plymouth-load.tar.zst"
SHA="$PKG.sha256"
BACKUP_DIR="/opt/pincabos/backups/plymouth-load-$(date +%Y%m%d-%H%M%S)"
THEME_DIR="/usr/share/plymouth/themes/$THEME_NAME"
THEME_FILE="$THEME_DIR/$THEME_NAME.plymouth"

mkdir -p "$BACKUP_DIR"

go() { echo -e "${GREEN}GO:${NC} $*"; }
warn() { echo -e "${YELLOW}WARN:${NC} $*"; }
nogo() { echo -e "${RED}NOGOOD:${NC} $*"; exit 1; }

ensure_plymouth_deps() {
  echo
  echo "=== Validate Plymouth dependencies already installed ==="

  local missing=0
  local cmd=""
  local pkg=""

  for cmd in bash tar sha256sum update-initramfs; do
    if command -v "$cmd" >/dev/null 2>&1; then
      go "Command available: $cmd"
    else
      warn "Command missing: $cmd"
      missing=$((missing + 1))
    fi
  done

  for pkg in tar zstd initramfs-tools plymouth plymouth-themes; do
    if dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q 'install ok installed'; then
      go "Package installed: $pkg"
    else
      warn "Package missing: $pkg"
      missing=$((missing + 1))
    fi
  done

  if [ "$missing" -gt 0 ]; then
    nogo "ERR-PLYMOUTH-DEPS-MISSING-001" "Plymouth dependencies must be installed by 01-install-system.sh before this module runs"
  fi

  go "Plymouth dependencies already installed"
}



find_cmd() {
  local c="$1"
  if command -v "$c" >/dev/null 2>&1; then
    command -v "$c"
    return 0
  fi
  if [ -x "/usr/sbin/$c" ]; then
    echo "/usr/sbin/$c"
    return 0
  fi
  if [ -x "/sbin/$c" ]; then
    echo "/sbin/$c"
    return 0
  fi
  return 1
}

echo
ensure_plymouth_deps

echo "=== 1) Validation package ==="

if [ ! -f "$PKG" ]; then
  nogo "Package absent: $PKG"
fi

tar --zstd -tf "$PKG" >/tmp/pco-plymouth-load-module-list.txt 2>/tmp/pco-plymouth-load-module.err
if [ $? -ne 0 ]; then
  cat /tmp/pco-plymouth-load-module.err
  nogo "Package illisible: $PKG"
fi

grep -Eq "^\\./?usr/share/plymouth/themes/$THEME_NAME/$THEME_NAME\\.plymouth$" /tmp/pco-plymouth-load-module-list.txt
if [ $? -ne 0 ]; then
  cat /tmp/pco-plymouth-load-module-list.txt
  nogo "Package incomplet: fichier .plymouth absent"
fi

if [ -f "$SHA" ]; then
  expected="$(awk '{print $1}' "$SHA")"
  actual="$(sha256sum "$PKG" | awk '{print $1}')"
  if [ "$expected" != "$actual" ]; then
    echo "Expected: $expected"
    echo "Actual:   $actual"
    nogo "SHA invalide pour $PKG"
  fi
  go "SHA valide"
else
  warn "SHA absent: $SHA"
fi

go "Package complet"

echo
echo "=== 2) Backup thème actuel ==="
if [ -d "$THEME_DIR" ]; then
  cp -a "$THEME_DIR" "$BACKUP_DIR/"
  go "Backup créé: $BACKUP_DIR"
else
  warn "Aucun ancien thème à sauvegarder"
fi

echo
echo "=== 3) Extraction thème ==="
if [ -d "$THEME_DIR" ]; then
  rm -rf "$THEME_DIR"
fi
tar --zstd -xpf "$PKG" -C /
if [ $? -ne 0 ]; then
  nogo "Extraction échouée"
fi

if [ ! -f "$THEME_FILE" ]; then
  nogo "Thème non installé: $THEME_FILE"
fi

chmod -R a+rX "$THEME_DIR"
go "Thème installé: $THEME_DIR"

echo
echo "=== 4) Application Plymouth ==="
echo
echo "=== 4) Activation Plymouth réelle ==="

if ! command -v update-alternatives >/dev/null 2>&1; then
  nogo "ERR-PLYMOUTH-ALT-MISSING-001" "update-alternatives missing; cannot activate Plymouth theme reliably"
fi

if [ ! -f "$THEME_FILE" ]; then
  nogo "ERR-PLYMOUTH-THEME-FILE-MISSING-001" "Theme file missing before activation: $THEME_FILE"
fi

update-alternatives --install /usr/share/plymouth/themes/default.plymouth default.plymouth "$THEME_FILE" 100
update-alternatives --set default.plymouth "$THEME_FILE"

ACTIVE_THEME="$(readlink -f /usr/share/plymouth/themes/default.plymouth || true)"
EXPECTED_THEME="$(readlink -f "$THEME_FILE" || true)"

echo "Active default.plymouth: $ACTIVE_THEME"
echo "Expected theme file:     $EXPECTED_THEME"

if [ "$ACTIVE_THEME" != "$EXPECTED_THEME" ]; then
  update-alternatives --display default.plymouth || true
  nogo "ERR-PLYMOUTH-THEME-NOT-ACTIVE-001" "Plymouth theme not active after update-alternatives"
fi

if update-alternatives --query default.plymouth >/tmp/pco-plymouth-alt-query.txt 2>/tmp/pco-plymouth-alt-query.err; then
  grep -q "^Value: $THEME_FILE$" /tmp/pco-plymouth-alt-query.txt || {
    cat /tmp/pco-plymouth-alt-query.txt || true
    nogo "ERR-PLYMOUTH-ALT-VALUE-001" "update-alternatives value is not the expected Plymouth theme"
  }
fi

go "Plymouth active theme: $THEME_NAME"

run_with_spinner() {
  local label="$1"
  shift

  local log="/tmp/pincabos-plymouth-initramfs-$(date +%Y%m%d-%H%M%S).log"
  local spin='|/-\\'
  local i=0
  local pid=""
  local rc=0

  echo -n "$label "

  "$@" >"$log" 2>&1 &
  pid=$!

  while kill -0 "$pid" 2>/dev/null; do
    i=$(( (i + 1) % 4 ))
    printf "\r%s %s" "$label" "${spin:$i:1}"
    sleep 0.2
  done

  wait "$pid"
  rc=$?

  if [ $rc -eq 0 ]; then
    printf "\r%s ${GREEN}OK${NC}        \n" "$label"
  else
    printf "\r%s ${RED}NOGOOD${NC}    \n" "$label"
    echo
    echo "=== Log update-initramfs ==="
    cat "$log"
  fi

  return $rc
}

echo
echo "=== 5) update-initramfs ==="
INITRAMFS_CMD="$(find_cmd update-initramfs)"
if [ -n "$INITRAMFS_CMD" ]; then
  run_with_spinner "update-initramfs - génération initrd" "$INITRAMFS_CMD" -u
  if [ $? -ne 0 ]; then
    warn "update-initramfs a retourné une erreur"
  else
    go "initramfs mis à jour"
  fi
else
  warn "update-initramfs introuvable"
fi

echo
echo -e "${YELLOW}Résumé Plymouth LOADING FINAL${NC}"
echo -e "${YELLOW}- Theme:${NC} $THEME_NAME"
echo -e "${YELLOW}- Dir:${NC} $THEME_DIR"
echo -e "${YELLOW}- Package:${NC} $PKG"
echo -e "${YELLOW}- Backup:${NC} $BACKUP_DIR"

echo
go "Module Plymouth LOADING FINAL terminé"
