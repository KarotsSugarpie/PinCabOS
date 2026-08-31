#!/usr/bin/env bash
# PinCabOS-File created by Karots Sugarpie
set -Eeuo pipefail

clear

# ────────────────────────────────────────────────────────────────
# PinCabOS Engine Publisher
# Compile sur VMDev et publie le package engine vers le WebServer
# Sans backup, sans archive timestampée.
# ────────────────────────────────────────────────────────────────

C_RESET=$'\033[0m'
C_CYAN=$'\033[36m'
C_ORANGE=$'\033[38;5;208m'
C_GREEN=$'\033[32m'
C_RED=$'\033[31m'
C_YELLOW=$'\033[33m'
C_WHITE=$'\033[97m'

PCO_TOTAL=0
PCO_GO=0
PCO_NOGOOD=0
PCO_CURRENT_STEP=""

DRY_RUN="${DRY_RUN:-0}"

pincabos_publy_presync_public_install_tree() {
  pco_step "0A" "Pre-sync install scripts publics depuis ins.pincabos.cc/install"

  local base="${PINCA_INSTALL_BASE_URL:-https://ins.pincabos.cc/install}"
  local dest="/opt/pincabos/install"

  mkdir -p "$dest" "$dest/packages" "$dest/modules/system" "$dest/modules/network"

  local required=(
    "go-pincabos.sh"
    "help-pincabos.sh"
    "01-install-system.sh"
    "02-install-engine.sh"
    "03-install-check.sh"
    "install.json"
  )

  local optional=(
    "PCOSInstallWP.png"
    "packages/pkg-lib.sh"
    "packages/pkg-apt-base.sh"
    "packages/pkg-monitoring.sh"
    "packages/pkg-python.sh"
    "packages/pkg-nginx.sh"
    "packages/pkg-x11.sh"
    "packages/pkg-lightdm.sh"
    "packages/pkg-openbox.sh"
    "packages/pkg-chrome.sh"
    "packages/pkg-plymouth.sh"
    "packages/pkg-vpx-bgfx-runtime.sh"
    "packages/pkg-vpinfe-runtime.sh"
    "packages/pkg-libdof-runtime.sh"
    "packages/pkg-system-validation.sh"
    "modules/modules.json"
    "modules/system/mod-splash.sh"
    "modules/network/mod-dhcp4.sh"
    "modules/network/mod-ssid.sh"
  )

  local rel dst fail=0

  for rel in "${required[@]}"; do
    dst="$dest/$rel"
    mkdir -p "$(dirname "$dst")"

    if curl -fsSL --connect-timeout 10 --retry 2 "$base/$rel" -o "$dst.tmp"; then
      mv -f "$dst.tmp" "$dst"
      case "$dst" in
        *.sh) chmod 0755 "$dst" ;;
        *) chmod 0644 "$dst" ;;
      esac
      echo "GO: pre-sync $rel"
    else
      rm -f "$dst.tmp"
      echo "NOGOOD: pre-sync requis absent: $rel"
      fail=$((fail+1))
    fi
  done

  for rel in "${optional[@]}"; do
    dst="$dest/$rel"
    mkdir -p "$(dirname "$dst")"

    if curl -fsSL --connect-timeout 10 --retry 2 "$base/$rel" -o "$dst.tmp"; then
      mv -f "$dst.tmp" "$dst"
      case "$dst" in
        *.sh) chmod 0755 "$dst" ;;
        *) chmod 0644 "$dst" ;;
      esac
      echo "GO: pre-sync $rel"
    else
      rm -f "$dst.tmp"
      echo "SKIP: pre-sync optionnel absent: $rel"
    fi
  done

  if [ "$fail" -ne 0 ]; then
    echo "NOGOOD: Pre-sync install public failed: $fail fichier(s) requis manquant(s)"
    return 1
  fi

  for f in \
    "$dest/go-pincabos.sh" \
    "$dest/01-install-system.sh" \
    "$dest/02-install-engine.sh" \
    "$dest/03-install-check.sh"
  do
    bash -n "$f" || {
      echo "NOGOOD: Syntaxe invalide après pre-sync: $f"
      return 1
    }
  done

  chown -R pinball:pinball "$dest" 2>/dev/null || true
  echo "GO: Pre-sync install public terminé"
}

pco_banner() {
  clear
  echo "${C_ORANGE}"
  cat <<'BANNER'
██████╗ ██╗███╗   ██╗ ██████╗ █████╗ ██████╗  ██████╗ ███████╗
██╔══██╗██║████╗  ██║██╔════╝██╔══██╗██╔══██╗██╔═══██╗██╔════╝
██████╔╝██║██╔██╗ ██║██║     ███████║██████╔╝██║   ██║███████╗
██╔═══╝ ██║██║╚██╗██║██║     ██╔══██║██╔══██╗██║   ██║╚════██║
██║     ██║██║ ╚████║╚██████╗██║  ██║██████╔╝╚██████╔╝███████║
╚═╝     ╚═╝╚═╝  ╚═══╝ ╚═════╝╚═╝  ╚═╝╚═════╝  ╚═════╝ ╚══════╝

        PinCabOS Engine Publisher
        Karots Sugarpie Edition
BANNER
  echo "${C_RESET}"
}

pco_line() {
  echo "${C_CYAN}────────────────────────────────────────────────────────────────${C_RESET}"
}

pco_title() {
  pco_line
  echo "${C_ORANGE} $* ${C_RESET}"
  pco_line
}

pco_step() {
  PCO_CURRENT_STEP="$1"
  echo
  echo "${C_CYAN}─[${PCO_CURRENT_STEP}]─► ${C_ORANGE}$2${C_CYAN} ◄────${C_RESET}"
}

pco_check() {
  PCO_TOTAL=$((PCO_TOTAL + 1))
  PCO_GO=$((PCO_GO + 1))
  echo "${C_CYAN}─[${PCO_CURRENT_STEP}]─► ${C_ORANGE}$1${C_CYAN} ◄──── ${C_GREEN}GO [√]${C_RESET}"
}

pco_fail() {
  PCO_TOTAL=$((PCO_TOTAL + 1))
  PCO_NOGOOD=$((PCO_NOGOOD + 1))
  echo "${C_CYAN}─[${PCO_CURRENT_STEP}]─► ${C_ORANGE}$1${C_CYAN} ◄── ${C_RED}NOGOOD [X]${C_RESET}"
  echo "${C_RED}$2${C_RESET}"
  pco_summary
  exit 1
}

pco_warn() {
  echo "${C_YELLOW}WARN:${C_RESET} $*"
}

pco_summary() {
  echo
  pco_line
  echo "${C_ORANGE}Résumé PUBLY PinCabOS${C_RESET}"
  pco_line
  echo "Checks total : $PCO_TOTAL"
  echo "${C_GREEN}GO         : $PCO_GO${C_RESET}"
  echo "${C_RED}NOGOOD     : $PCO_NOGOOD${C_RESET}"
  echo
  if [ "$PCO_NOGOOD" -eq 0 ]; then
    echo "${C_GREEN}Résultat final : GO [√]${C_RESET}"
    echo
    if [ "${DRY_RUN:-0}" -eq 1 ]; then
      echo "${C_GREEN}TU PEUX LANCER LE PUBLY REEL!!${C_RESET}"
    else
      echo "${C_GREEN}PUBLY REEL TERMINE AVEC SUCCES!!${C_RESET}"
    fi
  else
    echo "${C_RED}Résultat final : NOGOOD [X]${C_RESET}"
  fi
}

pco_on_error() {
  local line="$1"
  echo
  echo "${C_RED}NOGOOD: erreur ligne ${line}, étape ${PCO_CURRENT_STEP}${C_RESET}"
  PCO_TOTAL=$((PCO_TOTAL + 1))
  PCO_NOGOOD=$((PCO_NOGOOD + 1))
  pco_summary
  exit 1
}

trap 'pco_on_error "$LINENO"' ERR

pco_spinner_wait() {
  local pid="$1"
  local label="$2"
  local spin='|/-\'
  local i=0

  while kill -0 "$pid" 2>/dev/null; do
    i=$(( (i + 1) % 4 ))
    printf "\r${C_CYAN}[%c]${C_ORANGE} %s...${C_RESET}" "${spin:$i:1}" "$label"
    sleep 0.15
  done

  wait "$pid"
  local rc="$?"
  printf "\r%100s\r" " "
  return "$rc"
}

run_spin() {
  local label="$1"
  shift
  local tmp="/tmp/pincabos-publy-spin-${RANDOM}-${RANDOM}.log"

  "$@" >"$tmp" 2>&1 &
  local pid="$!"

  if pco_spinner_wait "$pid" "$label"; then
    cat "$tmp"
    rm -f "$tmp"
    return 0
  else
    local rc="$?"
    cat "$tmp"
    rm -f "$tmp"
    return "$rc"
  fi
}

run_spin_bash() {
  local label="$1"
  shift
  local tmp="/tmp/pincabos-publy-spin-${RANDOM}-${RANDOM}.log"

  bash -c "$*" >"$tmp" 2>&1 &
  local pid="$!"

  if pco_spinner_wait "$pid" "$label"; then
    cat "$tmp"
    rm -f "$tmp"
    return 0
  else
    local rc="$?"
    cat "$tmp"
    rm -f "$tmp"
    return "$rc"
  fi
}



pco_need_remote_password_if_needed() {
  if [ "$DRY_RUN" -eq 1 ]; then
    return 0
  fi

  local web_pass_file="${WEB_PASS_FILE:-/opt/pincabos/config/webserver-webpass.secret}"

  if [ -z "${WEB_PASS:-}" ] && [ -s "$web_pass_file" ]; then
    WEB_PASS="$(head -n 1 "$web_pass_file" | tr -d '\r\n')"
    export WEB_PASS
    echo "GO: WEB_PASS chargé depuis $web_pass_file"
  fi

  if [ -n "${WEB_PASS:-}" ]; then
    if ! command -v sshpass >/dev/null 2>&1; then
      pco_fail "sshpass manquant" "WEB_PASS est fourni mais sshpass est absent. Installe: apt-get install -y sshpass"
    fi
    return 0
  fi

  if ssh -o BatchMode=yes -o ConnectTimeout=5 "$WEB_REMOTE" "true" >/dev/null 2>&1; then
    return 0
  fi

  if ! command -v sshpass >/dev/null 2>&1; then
    pco_fail "sshpass manquant" "Aucune clé SSH disponible vers $WEB_REMOTE et sshpass est absent. Installe: apt-get install -y sshpass ou configure une clé SSH."
  fi

  echo
  echo "${C_YELLOW}SSH key non disponible pour ${WEB_REMOTE}.${C_RESET}"
  read -r -s -p "Mot de passe WebServer ${WEB_REMOTE}: " WEB_PASS
  echo

  if [ -z "$WEB_PASS" ]; then
    pco_fail "Mot de passe WebServer" "WEB_PASS vide et SSH key non disponible."
  fi
}

pco_ssh() {
  if [ -n "${WEB_PASS:-}" ]; then
    command -v sshpass >/dev/null 2>&1 || pco_fail "sshpass manquant" "Installe sshpass: apt-get install -y sshpass"
    sshpass -p "$WEB_PASS" ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 "$WEB_REMOTE" "$@"
  else
    ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 "$WEB_REMOTE" "$@"
  fi
}

pco_scp_to_remote_updates() {
  if [ -n "${WEB_PASS:-}" ]; then
    command -v sshpass >/dev/null 2>&1 || pco_fail "sshpass manquant" "Installe sshpass: apt-get install -y sshpass"
    sshpass -p "$WEB_PASS" scp -o StrictHostKeyChecking=accept-new "$@" "${WEB_REMOTE}:${WEB_REMOTE_UPDATES}/"
  else
    scp -o StrictHostKeyChecking=accept-new "$@" "${WEB_REMOTE}:${WEB_REMOTE_UPDATES}/"
  fi
}


# ────────────────────────────────────────────────────────────────
# Config
# ────────────────────────────────────────────────────────────────

WEB_UPDATES="/var/www/html/install/pkg"
WEB_HOST="${WEB_HOST:-192.168.254.55}"
WEB_USER="${WEB_USER:-root}"
WEB_REMOTE="${WEB_USER}@${WEB_HOST}"
WEB_REMOTE_UPDATES="${WEB_REMOTE_UPDATES:-/var/www/html/install/pkg}"

case "${1:-}" in
  --dry-run|-n|dry-run|dryrun)
    DRY_RUN=1
    ;;
esac

PKG_NAME="pkg-pincabos-web.zst"
WEBAPP_PKG_NAME="pkg-pincabos-webapp.zst"
LATEST_NAME="latest.json"
CHECKSUMS_NAME="checksums.sha256"
MANIFEST_NAME="manifest.txt"

PUBLIC_BASE_URL="https://ins.pincabos.cc/install/pkg"
INSTALL_BASE_URL="https://ins.pincabos.cc/install"

WORK="/tmp/pincabos-publy"
STAGE="${WORK}/stage"
PKG_STAGE="${STAGE}/${PKG_NAME}"
WEBAPP_PKG_STAGE="${STAGE}/${WEBAPP_PKG_NAME}"
LATEST_STAGE="${STAGE}/${LATEST_NAME}"
CHECKSUMS_STAGE="${STAGE}/${CHECKSUMS_NAME}"
PKG_SHA_NAME="pkg-pincabos-web.sha256"
PKG_MANIFEST_JSON_NAME="pkg-pincabos-web.manifest.json"

# WebApp/tools package metadata
WEBAPP_SHA_NAME="pkg-pincabos-webapp.sha256"
WEBAPP_MANIFEST_JSON_NAME="pkg-pincabos-webapp.manifest.json"
WEBAPP_MANIFEST_TXT_NAME="pkg-pincabos-webapp.manifest.txt"
PKG_SHA_STAGE="${STAGE}/${PKG_SHA_NAME}"
PKG_MANIFEST_JSON_STAGE="${STAGE}/${PKG_MANIFEST_JSON_NAME}"
MANIFEST_STAGE="${STAGE}/${MANIFEST_NAME}"

WEBAPP_SHA_STAGE="${STAGE}/${WEBAPP_SHA_NAME}"
WEBAPP_MANIFEST_JSON_STAGE="${STAGE}/${WEBAPP_MANIFEST_JSON_NAME}"
WEBAPP_MANIFEST_TXT_STAGE="${STAGE}/${WEBAPP_MANIFEST_TXT_NAME}"

INCLUDE_LIST="${WORK}/include-paths.txt"
FOUND_ROOTS="${WORK}/found-roots.txt"
ALL_FILES="${WORK}/all-files.txt"
ENGINE_FILES="${WORK}/engine-files.txt"
WEBAPP_FILES="${WORK}/webapp-files.txt"
EXCLUDE_LIST="${WORK}/exclude-patterns.txt"

PKG_FINAL="${WEB_UPDATES}/${PKG_NAME}"
WEBAPP_PKG_FINAL="${WEB_UPDATES}/${WEBAPP_PKG_NAME}"
LATEST_FINAL="${WEB_UPDATES}/${LATEST_NAME}"
CHECKSUMS_FINAL="${WEB_UPDATES}/${CHECKSUMS_NAME}"
MANIFEST_FINAL="${WEB_UPDATES}/${MANIFEST_NAME}"

pco_banner
pco_title "PinCabOS - Engine Publisher VMDev vers WebServer"

# ────────────────────────────────────────────────────────────────
# Étape 1
# ────────────────────────────────────────────────────────────────

pco_step "1" "WebServer remote: login SSH et nettoyage install/pkg"

if [ "$(id -u)" -ne 0 ]; then
  pco_fail "Root requis" "Lance publy.sh en root."
fi
pco_check "Root confirmé sur VMDev"

if [ "$WEB_REMOTE_UPDATES" != "/var/www/html/install/pkg" ]; then
  pco_fail "Sécurité chemin updates remote" "WEB_REMOTE_UPDATES inattendu: $WEB_REMOTE_UPDATES"
fi
pco_check "Chemin install/pkg remote sécurisé: $WEB_REMOTE_UPDATES"

echo "WebServer : $WEB_REMOTE"
echo "Updates   : $WEB_REMOTE_UPDATES"
echo "Dry-run   : $DRY_RUN"

if [ "$DRY_RUN" -eq 1 ]; then
  echo "${C_YELLOW}DRY-RUN:${C_RESET} connexion SSH WebServer ignorée."
  echo "${C_YELLOW}DRY-RUN:${C_RESET} nettoyage remote ignoré."
  pco_check "Dry-run local: remote non touché"
else

pco_need_remote_password_if_needed

run_spin "Connexion SSH WebServer" pco_ssh "hostname; mkdir -p '$WEB_REMOTE_UPDATES'; ls -lah '$WEB_REMOTE_UPDATES' >/dev/null"
pco_check "Connexion SSH WebServer OK"

if [ "$DRY_RUN" -eq 1 ]; then
  echo "${C_YELLOW}DRY-RUN:${C_RESET} ne supprime pas ${WEB_REMOTE}:${WEB_REMOTE_UPDATES}"
  pco_check "Dry-run nettoyage remote simulé"
else
  run_spin "Backup remote install/pkg" pco_ssh "set -e; bkroot=/var/www/html/install/pkg-backups; stamp=\$(date +%Y%m%d-%H%M%S); mkdir -p \"\$bkroot/\$stamp\"; if find \"$WEB_REMOTE_UPDATES\" -mindepth 1 -maxdepth 1 -print -quit | grep -q .; then cp -a \"$WEB_REMOTE_UPDATES\"/. \"\$bkroot/\$stamp/\"; fi; echo \"Backup remote: \$bkroot/\$stamp\""
  run_spin "Nettoyage remote /var/www/html/install/pkg" pco_ssh "find '$WEB_REMOTE_UPDATES' -mindepth 1 -maxdepth 1 -exec rm -rf {} +"
  pco_check "Contenu remote /var/www/html/install/pkg effacé sans backup"
fi

run_spin_bash "Nettoyage workspace local" "rm -rf \"$WORK\" && mkdir -p \"$WORK\" \"$STAGE\""
pco_check "Workspace local VMDev propre"

fi

# ────────────────────────────────────────────────────────────────
# Préparation workdir local
# ────────────────────────────────────────────────────────────────

rm -rf "$WORK"
mkdir -p "$WORK" "$STAGE"

# ────────────────────────────────────────────────────────────────
# Étape 2
# ────────────────────────────────────────────────────────────────

pincabos_publy_presync_public_install_tree
pco_step "2" "Scan liste essentielle + détection nouveaux fichiers + exclusions"

command -v tar >/dev/null 2>&1 || pco_fail "tar manquant" "Installe tar."
command -v zstd >/dev/null 2>&1 || pco_fail "zstd manquant" "Installe zstd avec apt-get install -y zstd."
command -v sha256sum >/dev/null 2>&1 || pco_fail "sha256sum manquant" "sha256sum est requis."
command -v python3 >/dev/null 2>&1 || pco_fail "python3 manquant" "python3 est requis pour créer latest.json proprement."
pco_check "Outils requis disponibles"

cat > "$INCLUDE_LIST" <<'LISTEOF'
opt/pincabos/web
opt/pincabos/apps/frontend/vpinfe
opt/pincabos/apps/vpinball
opt/pincabos/apps/dof
opt/pincabos/bin
opt/pincabos/scripts
opt/pincabos/tools
opt/pincabos/media
opt/pincabos/config
opt/pincabos/config/version.json
etc/systemd/system/pincabos-web.service
etc/systemd/system/pincabos-web.service.d
etc/systemd/system/pincabos-webapp.service
etc/systemd/system/pincabos-webapp.service.d
etc/systemd/system/pincabos-console.service
etc/systemd/system/pincabos-vpinfe.service
etc/systemd/system/pincabos-vpinfe.service
etc/sudoers.d
home/pinball/.config/openbox
etc/xdg/openbox
usr/share/xsessions/pincabos-openbox.desktop
usr/share/plymouth/themes/pincabos
etc/plymouth/plymouthd.conf
etc/lightdm
etc/lightdm/lightdm.conf
etc/lightdm/lightdm.conf.d
home/pinball/.local/share/applications
usr/share/icons
usr/share/pixmaps
etc/default/grub
usr/local/bin
usr/local/sbin
LISTEOF

cat > "$EXCLUDE_LIST" <<'EXCEOF'
opt/pincabos/install
opt/pincabos/install/*
opt/pincabos/logs
opt/pincabos/logs/*
opt/pincabos/stage
opt/pincabos/stage/*
opt/pincabos/download
opt/pincabos/download/*
opt/pincabos/out
opt/pincabos/out/*
opt/pincabos/essentials/publish-tree-staging
opt/pincabos/essentials/publish-tree-staging/*
opt/pincabos/essentials/publish-tree-out
opt/pincabos/essentials/publish-tree-out/*
opt/pincabos/essentials/publish-tree-work
opt/pincabos/essentials/publish-tree-work/*
boot/grub
boot/grub/*
etc/grub.d
etc/grub.d/*
etc/X11
etc/X11/*
usr/local/lib/python*
usr/lib/python*
usr/share/icons/*
snap
snap/*
var/lib/snapd
var/lib/snapd/*
opt/pincabos/.venv
opt/pincabos/.venv/*
opt/pincabos/web/.venv
opt/pincabos/web/.venv/*
.venv
.venv/*
*/.venv
*/.venv/*
__pycache__
*/__pycache__
*.pyc
*.pyo
*.backup
*.bak
*.old
*.tmp
*.BROKEN*
EXCEOF

pco_check "Listes include/exclude générées"

: > "$FOUND_ROOTS"

while IFS= read -r p; do
  [ -z "$p" ] && continue
  if [ -e "/$p" ] || [ -L "/$p" ]; then
    echo "$p" >> "$FOUND_ROOTS"
    echo "${C_GREEN}GO:${C_RESET} /$p"
  else
    pco_warn "Absent non bloquant: /$p"
  fi
done < "$INCLUDE_LIST"

if [ ! -s "$FOUND_ROOTS" ]; then
  pco_fail "Aucun chemin trouvé" "La liste essentielle ne retourne aucun fichier présent."
fi
pco_check "Chemins essentiels scannés"

: > "$ALL_FILES"

while IFS= read -r p; do
  [ -z "$p" ] && continue

  if [ -d "/$p" ] && [ ! -L "/$p" ]; then
    find "/$p" \
      \( \
        -path "/opt/pincabos/install" -o \
        -path "/opt/pincabos/install/*" -o \
        -path "/opt/pincabos/logs" -o \
        -path "/opt/pincabos/logs/*" -o \
        -path "/opt/pincabos/stage" -o \
        -path "/opt/pincabos/stage/*" -o \
        -path "/opt/pincabos/download" -o \
        -path "/opt/pincabos/download/*" -o \
        -path "/opt/pincabos/out" -o \
        -path "/opt/pincabos/out/*" -o \
        -path "/opt/pincabos/essentials/publish-tree-staging" -o \
        -path "/opt/pincabos/essentials/publish-tree-staging/*" -o \
        -path "/opt/pincabos/essentials/publish-tree-out" -o \
        -path "/opt/pincabos/essentials/publish-tree-out/*" -o \
        -path "/opt/pincabos/essentials/publish-tree-work" -o \
        -path "/opt/pincabos/essentials/publish-tree-work/*" -o \
        -path "*/.venv" -o \
        -path "*/.venv/*" -o \
        -path "*/__pycache__" -o \
        -path "*/__pycache__/*" \
      \) -prune -o -print
  else
    printf '/%s\n' "$p"
  fi
done < "$FOUND_ROOTS" \
  | sed 's#^/##' \
  | sort -u \
  > "$ALL_FILES"

grep -E '^(opt/pincabos/web(/|$)|etc/systemd/system/pincabos-web\.service($|/)|etc/systemd/system/pincabos-web\.service\.d(/|$)|etc/systemd/system/pincabos-webapp\.service($|/)|etc/systemd/system/pincabos-webapp\.service\.d(/|$)|etc/nginx/sites-available/pincabos-web(\.conf)?$|etc/nginx/sites-enabled/pincabos-web\.conf$)' "$ALL_FILES" > "$WEBAPP_FILES" || true
cp -a "$ALL_FILES" "$ENGINE_FILES"

pco_check "Nouveaux fichiers détectés dans les répertoires retenus"

if grep -E '(^|/)opt/pincabos/install(/|$)|(^|/)opt/pincabos/(logs|stage|download|out)(/|$)|(^|/)boot/grub(/|$)|(^|/)etc/grub.d(/|$)|(^|/)etc/X11(/|$)|(^|/)snap(/|$)|(^|/)\.venv(/|$)' "$ENGINE_FILES" >/dev/null; then
  echo "${C_RED}Fichiers interdits détectés:${C_RESET}"
  grep -E '(^|/)opt/pincabos/install(/|$)|(^|/)opt/pincabos/(logs|stage|download|out)(/|$)|(^|/)boot/grub(/|$)|(^|/)etc/grub.d(/|$)|(^|/)etc/X11(/|$)|(^|/)snap(/|$)|(^|/)\.venv(/|$)' "$ENGINE_FILES" || true
  pco_fail "Exclusions critiques" "Le scan contient encore des fichiers interdits."
fi
pco_check "Exclusions critiques confirmées"

# ────────────────────────────────────────────────────────────────
# Étape 3
# ────────────────────────────────────────────────────────────────



# === PINCABOS PUBLY PROTECT CAB CONFIGS START ===
pincabos_publy_policy_file() {
  echo "/tmp/pincabos-publy/protected-cab-config-patterns.clean.txt"
}

pincabos_publy_write_policy() {
  local work="/tmp/pincabos-publy"
  local protect_raw="$work/protected-cab-config-patterns.txt"
  local protect
  protect="$(pincabos_publy_policy_file)"

  mkdir -p "$work"

  cat > "$protect_raw" <<'EOF'
# ────────────────────────────────────────────────────────────────
# PinCabOS publish denylist permanente

# Secrets locaux / credentials VMDev / WebServer : JAMAIS publiés.
^opt/pincabos/config/dev-password\.txt$
^opt/pincabos/config/webserver-webpass\.secret$
^opt/pincabos/config/.*password.*$
^opt/pincabos/config/.*secret.*$
^opt/pincabos/config/.*api[-_]?key.*$

# Firmwares Dude's Cab (propriété d'Arnoz) : téléchargés à la volée depuis
# dude.arnoz.com par le configurateur, JAMAIS redistribués (ni cache, ni manifests).
^opt/pincabos/config/dudescab(/|$)

# DOF Config Tool / cabinet local : spécifique au cab, jamais dans l'engine public.
^opt/pincabos/config/dof/active-cabinet\.txt$
^opt/pincabos/config/dof/configtool-api-key\.txt$
^opt/pincabos/config/dof/.*api[-_]?key.*$
^opt/pincabos/config/dof/cabinets(/|$)
^opt/pincabos/config/dof/cabinet\.json$
^opt/pincabos/config/dof/.*\.json$

# Outils de rotation de mot de passe/root : dangereux hors VMDev.
^opt/pincabos/tools/change-root-password\.sh$
^usr/local/bin/change-root-password$
^usr/local/sbin/change-root-password$

# But: scan large automatique, mais ne jamais publier l'état local VM/cab.
# Les chemins sont relatifs à /, sans slash initial.
# ────────────────────────────────────────────────────────────────

# Backups / fichiers temporaires génériques.
(^|/).*\.bak$
(^|/).*\.backup($|[-_.].*)
(^|/).*\.backup-.*
(^|/).*~$
(^|/)\.DS_Store$
(^|/)Thumbs\.db$

# WebApp backups et fichiers de travail.
^opt/pincabos/web/.*\.bak$
^opt/pincabos/web/.*\.backup($|[-_.].*)
^opt/pincabos/web/.*\.backup-.*
^opt/pincabos/web/__pycache__(/|$)
^opt/pincabos/web/\.venv(/|$)

# Logs, stage, output, download, backups, updates, publish work.
^opt/pincabos/logs(/|$)
^opt/pincabos/out(/|$)
^opt/pincabos/stage(/|$)
^opt/pincabos/download(/|$)
^opt/pincabos/backups(/|$)
^opt/pincabos/install(/|$)
^opt/pincabos/essentials/publish-tree-(staging|out|work)(/|$)

# Configs runtime utilisateur/cab VPinFE.
^home/pinball/\.config/vpinfe/vpinfe\.ini($|[-_.].*)
^opt/pincabos/config/vpinfe/vpinfe\.ini($|[-_.].*)
^opt/pincabos/essentials/VPinFEfiles/vpinfe\.ini($|[-_.].*)

# Configs runtime utilisateur/cab VPinball / VPX.
^home/pinball/\.vpinball/VPinballX\.ini($|[-_.].*)
^opt/pincabos/config/vpinball/VPinballX\.ini($|[-_.].*)
^opt/pincabos/apps/vpinball/.*VPinballX.*\.ini$
^opt/pincabos/apps/vpinball/assets/Default_VPinballX\.ini$

# INI runtime dans l'app VPX/PinMAME : générés/ajustés par cab.
^opt/pincabos/apps/vpinball/.*\.ini$
^opt/pincabos/apps/frontend/vpinfe/.*\.ini$

# PinMAME runtime local/cab.
^opt/pincabos/apps/vpinball/PinMAME/(snap|cfg|nvram|memcard|hi)(/|$)
^opt/pincabos/apps/vpinball/PinMAME/.*\.(cfg|nv|nvram)$

# Caches Python/Node.
(^|/)__pycache__(/|$)
(^|/)\.pytest_cache(/|$)
(^|/)node_modules(/|$)

# OS/system non publiables par engine.
^boot/grub(/|$)
^etc/grub\.d(/|$)
^etc/X11(/|$)
^snap(/|$)
EOF

  grep -Ev '^[[:space:]]*($|#)' "$protect_raw" > "$protect"
}

pincabos_publy_filter_file_list() {
  local list="$1"
  local protect
  protect="$(pincabos_publy_policy_file)"

  [ -f "$list" ] || return 0
  [ -s "$protect" ] || pincabos_publy_write_policy

  local before after
  before="$(wc -l < "$list" | tr -d ' ')"
  cp -a "$list" "$list.before-cab-config-sanitize"
  grep -Ev -f "$protect" "$list.before-cab-config-sanitize" > "$list"
  after="$(wc -l < "$list" | tr -d ' ')"
  echo "Sanitized $(basename "$list"): $before -> $after"
}

pincabos_publy_sanitize_lists() {
  echo "=== Publy sanitizer: protection configs cab / VMDev ==="

  local work="/tmp/pincabos-publy"
  local protect
  pincabos_publy_write_policy
  protect="$(pincabos_publy_policy_file)"

  for list in "$work/engine-files.txt" "$work/webapp-files.txt" "$work/all-files.txt" "$work/stage/manifest.txt"; do
    pincabos_publy_filter_file_list "$list"
  done

  echo "--- Fichiers protégés encore présents après filtre, doit être vide ---"
  local bad=0
  for list in "$work/engine-files.txt" "$work/webapp-files.txt" "$work/all-files.txt" "$work/stage/manifest.txt"; do
    if [ -f "$list" ]; then
      if grep -En -f "$protect" "$list"; then
        bad=1
      fi
    fi
  done

  if [ "$bad" = "1" ]; then
    echo "NOGOOD: sanitizer Publy a encore des configs cab protégées."
    return 1
  fi

  if [ -f "$work/engine-files.txt" ] && [ "$(wc -l < "$work/engine-files.txt")" -lt 100 ]; then
    echo "NOGOOD: engine-files.txt trop petit après sanitizer."
    return 1
  fi

  if [ -f "$work/webapp-files.txt" ] && [ "$(wc -l < "$work/webapp-files.txt")" -lt 10 ]; then
    echo "NOGOOD: webapp-files.txt trop petit après sanitizer."
    return 1
  fi

  echo "OK: sanitizer Publy configs cab appliqué."
}

pincabos_publy_validate_no_protected_files() {
  echo "=== Publy validation finale policy denylist ==="

  local work="/tmp/pincabos-publy"
  local protect
  pincabos_publy_write_policy
  protect="$(pincabos_publy_policy_file)"

  local bad=0

  for f in "$work/stage/manifest.txt" "$work/stage/latest.json"; do
    if [ -f "$f" ]; then
      echo "--- Validation $f ---"
      if grep -En -f "$protect" "$f"; then
        bad=1
      else
        echo "OK: aucun fichier protégé dans $f"
      fi
    fi
  done

  if [ -f "$work/stage/pincabos-engine-latest.tar.zst" ]; then
    echo "--- Validation archive engine ---"
    if tar --use-compress-program=unzstd -tf "$work/stage/pincabos-engine-latest.tar.zst" | grep -En -f "$protect"; then
      bad=1
    else
      echo "OK: archive engine propre"
    fi
  fi

  if [ -f "$work/stage/pincabos-webapp-latest.tar.zst" ]; then
    echo "--- Validation archive WebApp ---"
    if tar --use-compress-program=unzstd -tf "$work/stage/pincabos-webapp-latest.tar.zst" | grep -En -f "$protect"; then
      bad=1
    else
      echo "OK: archive WebApp propre"
    fi
  fi

  if [ "$bad" = "1" ]; then
    echo "NOGOOD: Publy refuse de publier des fichiers protégés."
    return 1
  fi

  echo "OK: validation finale Publy policy."
}
# === PINCABOS PUBLY PROTECT CAB CONFIGS END ===



echo
pincabos_publy_sanitize_lists || {
  pco_check 2 "Sanitizer configs cab Publy" 1
  pco_final_summary
  exit 1
}
pco_check 2 "Sanitizer configs cab Publy" 0

pco_step "3" "Création latest.json avec arborescence complète et WebApp"

TOTAL_FILES="$(wc -l < "$ENGINE_FILES" | tr -d ' ')"
WEBAPP_TOTAL="$(wc -l < "$WEBAPP_FILES" | tr -d ' ')"

python3 - <<PY
import json
from pathlib import Path

engine_files = Path("$ENGINE_FILES").read_text().splitlines()
webapp_files = Path("$WEBAPP_FILES").read_text().splitlines()

data = {
    "name": "pincabos-engine",
    "version": "latest",
    "package": "$PKG_NAME",
    "url": "$PUBLIC_BASE_URL/$PKG_NAME",
    "install_base_url": "$INSTALL_BASE_URL",
    "policy": {
        "engine_excludes_install": True,
        "client_must_delete_opt_pincabos_install": True,
        "client_must_restore_install_from": "$INSTALL_BASE_URL",
        "excluded_paths": [
            "/opt/pincabos/install",
            "/opt/pincabos/logs",
            "/opt/pincabos/stage",
            "/opt/pincabos/download",
            "/opt/pincabos/out",
            "/opt/pincabos/essentials/publish-tree-staging",
            "/opt/pincabos/essentials/publish-tree-out",
            "/opt/pincabos/essentials/publish-tree-work",
            "/boot/grub",
            "/etc/grub.d",
            "/etc/X11",
            "/snap",
            "/var/lib/snapd",
            ".venv"
        ]
    },
    "manifest": {
        "total_files_and_dirs": len(engine_files),
        "webapp_files_and_dirs": len(webapp_files),
        "engine_tree": engine_files,
        "pincabos_webapp_tree": webapp_files
    }
}

Path("$LATEST_STAGE").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\\n")
PY

pco_check "latest.json créé avec arborescence engine + WebApp"
echo "Total engine: $TOTAL_FILES"
echo "Total WebApp: $WEBAPP_TOTAL"

if [ "$WEBAPP_TOTAL" -lt 10 ]; then
  pco_fail "Package WebApp vide" "WEBAPP_FILES contient seulement $WEBAPP_TOTAL éléments."
fi
pco_check "Liste package WebApp séparé prête"

# ────────────────────────────────────────────────────────────────
# Étape 4
# ────────────────────────────────────────────────────────────────

pco_step "4" "Création archive engine zstd -3 -T1"

rm -f "$PKG_STAGE"

run_spin_bash "Création archive engine zstd -3 -T1" "tar -C / --no-recursion -T \"$ENGINE_FILES\" -cf - | zstd -3 -T1 -o \"$PKG_STAGE\""

if [ ! -s "$PKG_STAGE" ]; then
  pco_fail "Archive engine vide" "$PKG_STAGE absent ou vide."
fi

pco_check "Archive temporaire créée: $PKG_STAGE"



# === PINCABOS PUBLY WEBAPP TOOLS SAFE LIST START ===
pco_step "4A2" "Sécurisation liste WebApp + tools"

: "${WEBAPP_FILES:?WEBAPP_FILES missing}"
: "${WEBAPP_PKG_STAGE:?WEBAPP_PKG_STAGE missing}"

WEBAPP_SAFE_TMP="${WEBAPP_FILES}.safe.tmp"
rm -f "$WEBAPP_SAFE_TMP"

if [ ! -d /opt/pincabos/web ]; then
  pco_fail "Source WebApp absente" "/opt/pincabos/web est introuvable"
fi

if [ ! -d /opt/pincabos/tools ]; then
  pco_fail "Source tools absente" "/opt/pincabos/tools est introuvable"
fi

# IMPORTANT:
# WebApp update package must transfer WebApp + tools only.
# It must never include install/RUN/go/modules/calamares/runtime/cache.
find /opt/pincabos/web /opt/pincabos/tools -xdev \
  \( \
    -path '*/.venv' -o \
    -path '*/.venv/*' -o \
    -path '*/__pycache__' -o \
    -path '*/__pycache__/*' -o \
    -path '*/.pytest_cache' -o \
    -path '*/.pytest_cache/*' -o \
    -name '*.pyc' -o \
    -name '*.pyo' -o \
    -name '*.bak' -o \
    -name '*.backup' -o \
    -name '*.orig' -o \
    -name '*.tmp' \
  \) -prune -o -print \
  | sed 's#^/##' \
  | sort > "$WEBAPP_SAFE_TMP"

if ! grep -q '^opt/pincabos/web/app.py$' "$WEBAPP_SAFE_TMP"; then
  pco_fail "WebApp app.py absent du package WebApp" "opt/pincabos/web/app.py absent de WEBAPP_FILES"
fi

if ! grep -q '^opt/pincabos/web/static' "$WEBAPP_SAFE_TMP"; then
  pco_fail "WebApp static absent du package WebApp" "opt/pincabos/web/static absent de WEBAPP_FILES"
fi

if ! grep -q '^opt/pincabos/tools' "$WEBAPP_SAFE_TMP"; then
  pco_fail "Tools absents du package WebApp" "opt/pincabos/tools absent de WEBAPP_FILES"
fi

WEBAPP_FORBIDDEN_RE='(^|/)(opt/pincabos/install(/|$)|var/www/html/install(/|$)|go-pincabos\.sh$|help-pincabos\.sh$|01-install-system\.sh$|02-install-engine\.sh$|03-install-check\.sh$|RUN_[0-9A-Z_ -]*|modules(/|$)|etc/calamares(/|$)|opt/pincabos/(logs|backups|flags|download|tmp)(/|$)|(^|/)\.venv(/|$)|(^|/)__pycache__(/|$)|\.pyc$)'

if grep -E "$WEBAPP_FORBIDDEN_RE" "$WEBAPP_SAFE_TMP" >/tmp/pincabos-publy-webapp-forbidden.txt; then
  echo "NOGOOD: Forbidden paths in WebApp/tools package:"
  sed -n '1,220p' /tmp/pincabos-publy-webapp-forbidden.txt
  pco_fail "Package WebApp unsafe" "WEBAPP_FILES contient install/RUN/modules/runtime/cache"
fi

mv -f "$WEBAPP_SAFE_TMP" "$WEBAPP_FILES"

echo "WebApp/tools entries: $(wc -l < "$WEBAPP_FILES")"
grep -E '^opt/pincabos/(web/app.py|web/static|tools)' "$WEBAPP_FILES" | sed -n '1,80p' || true
pco_check "Liste WebApp sécurisée: web + tools seulement"
# === PINCABOS PUBLY WEBAPP TOOLS SAFE LIST END ===


pco_step "4B" "Création archive WebApp zstd -3 -T1"

rm -f "$WEBAPP_PKG_STAGE"

run_spin_bash "Création archive WebApp zstd -3 -T1" "tar -C / --no-recursion -T \"$WEBAPP_FILES\" -cf - | zstd -3 -T1 -o \"$WEBAPP_PKG_STAGE\""

if [ ! -s "$WEBAPP_PKG_STAGE" ]; then
  pco_fail "Archive WebApp vide" "$WEBAPP_PKG_STAGE absent ou vide."
fi

pco_check "Archive WebApp créée"


pco_step "5" "Validation archive et manifest final"

run_spin "Validation zstd package engine" zstd -t "$PKG_STAGE"
run_spin "Validation zstd package WebApp" zstd -t "$WEBAPP_PKG_STAGE"
run_spin_bash "Lecture manifest archive" "tar --use-compress-program=unzstd -tf \"$PKG_STAGE\" > \"$MANIFEST_STAGE\""


pincabos_publy_validate_no_protected_files || {
  pco_check "Validation policy publish denylist" 1
  pco_final_summary
  exit 1
}
pco_check "Validation policy publish denylist" 0

if grep -E '(^|/)opt/pincabos/install(/|$)|(^|/)opt/pincabos/(logs|stage|download|out)(/|$)|(^|/)opt/pincabos/essentials/publish-tree-(staging|out|work)(/|$)|(^|/)boot/grub(/|$)|(^|/)etc/grub.d(/|$)|(^|/)etc/X11(/|$)|(^|/)snap(/|$)|(^|/)\.venv(/|$)' "$MANIFEST_STAGE" >/dev/null; then
  echo "${C_RED}Contenu interdit dans archive:${C_RESET}"
  grep -E '(^|/)opt/pincabos/install(/|$)|(^|/)opt/pincabos/(logs|stage|download|out)(/|$)|(^|/)opt/pincabos/essentials/publish-tree-(staging|out|work)(/|$)|(^|/)boot/grub(/|$)|(^|/)etc/grub.d(/|$)|(^|/)etc/X11(/|$)|(^|/)snap(/|$)|(^|/)\.venv(/|$)' "$MANIFEST_STAGE" || true
  pco_fail "Validation archive" "L’archive contient des chemins interdits."
fi

SHA256="$(sha256sum "$PKG_STAGE" | awk '{print $1}')"
SIZE_BYTES="$(stat -c '%s' "$PKG_STAGE")"

python3 - <<PY
import json
from pathlib import Path

p = Path("$LATEST_STAGE")
data = json.loads(p.read_text())
data["sha256"] = "$SHA256"
data["size_bytes"] = int("$SIZE_BYTES")
data["compression"] = "zstd"
data["tar"] = True
p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\\n")
PY

printf "%s  %s\n" "$SHA256" "$PKG_NAME" > "$CHECKSUMS_STAGE"
printf "%s  %s\n" "$SHA256" "$PKG_NAME" > "$PKG_SHA_STAGE"

python3 - "$PKG_MANIFEST_JSON_STAGE" "$PKG_NAME" "$SHA256" "$SIZE_BYTES" "$MANIFEST_STAGE" <<'PY_MANIFEST_PUBLIC'
import json
import sys
from pathlib import Path

out, pkg_name, sha, size, manifest_txt = sys.argv[1:]
manifest_path = Path(manifest_txt)

files = []
if manifest_path.exists():
    files = [line.strip() for line in manifest_path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]

data = {
    "name": "PinCabOS public web package",
    "file": pkg_name,
    "sha256": sha,
    "size_bytes": int(size),
    "compression": "zstd",
    "tar": True,
    "created_by": "Karots Sugarpie",
    "files": [{"path": x} for x in files],
}
Path(out).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY_MANIFEST_PUBLIC

pco_check "Archive validée, SHA256 ajouté au latest.json"


# === PINCABOS PUBLY PACKAGES JSON START ===
pco_step "5B" "Ajout packages engine + WebApp dans latest.json"

ENGINE_SHA="$(sha256sum "$PKG_STAGE" | awk '{print $1}')"
ENGINE_SIZE="$(stat -c '%s' "$PKG_STAGE")"
WEBAPP_SHA="$(sha256sum "$WEBAPP_PKG_STAGE" | awk '{print $1}')"
WEBAPP_SIZE="$(stat -c '%s' "$WEBAPP_PKG_STAGE")"

python3 - "$LATEST_STAGE" "$PKG_NAME" "$WEBAPP_PKG_NAME" "$PUBLIC_BASE_URL" "$ENGINE_SHA" "$ENGINE_SIZE" "$WEBAPP_SHA" "$WEBAPP_SIZE" <<'PY_PKG'
import json
import sys
from pathlib import Path

latest, engine_name, webapp_name, public_base, engine_sha, engine_size, webapp_sha, webapp_size = sys.argv[1:]
p = Path(latest)
data = json.loads(p.read_text(encoding="utf-8"))

data["package"] = engine_name
data["url"] = f"{public_base}/{engine_name}"
data["sha256"] = engine_sha
data["size_bytes"] = int(engine_size)
data["compression"] = "zstd"
data["tar"] = True

data["packages"] = {
    "engine": {
        "file": engine_name,
        "url": f"{public_base}/{engine_name}",
        "sha256": engine_sha,
        "size": int(engine_size),
        "size_bytes": int(engine_size),
        "compression": "zstd",
        "tar": True
    },
    "webapp": {
        "file": webapp_name,
        "url": f"{public_base}/{webapp_name}",
        "sha256": webapp_sha,
        "size": int(webapp_size),
        "size_bytes": int(webapp_size),
        "compression": "zstd",
        "tar": True,
        "contains": [
            "/opt/pincabos/web",
            "/etc/systemd/system/pincabos-web.service",
            "/etc/systemd/system/pincabos-web.service.d",
            "/etc/systemd/system/pincabos-webapp.service",
            "/etc/systemd/system/pincabos-webapp.service.d"
        ]
    }
}

p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY_PKG

{
  printf "%s  %s\n" "$ENGINE_SHA" "$PKG_NAME"
  printf "%s  %s\n" "$WEBAPP_SHA" "$WEBAPP_PKG_NAME"
} > "$CHECKSUMS_STAGE"

python3 -m json.tool "$LATEST_STAGE" >/dev/null

echo "Engine package : $PKG_NAME $ENGINE_SIZE bytes"
echo "WebApp package : $WEBAPP_PKG_NAME $WEBAPP_SIZE bytes"
pco_check "latest.json packages.engine/packages.webapp + checksums OK"
# === PINCABOS PUBLY PACKAGES JSON END ===

# ────────────────────────────────────────────────────────────────
# Étape 6
# ────────────────────────────────────────────────────────────────


# === PINCABOS PUBLY WEBAPP PACKAGE METADATA START ===
pco_step "5B" "Validation metadata package WebApp/tools"

: "${WEBAPP_PKG_STAGE:?WEBAPP_PKG_STAGE missing}"
: "${WEBAPP_SHA_STAGE:?WEBAPP_SHA_STAGE missing}"
: "${WEBAPP_MANIFEST_JSON_STAGE:?WEBAPP_MANIFEST_JSON_STAGE missing}"
: "${WEBAPP_MANIFEST_TXT_STAGE:?WEBAPP_MANIFEST_TXT_STAGE missing}"

run_spin_bash "Lecture manifest archive WebApp" "tar --use-compress-program=unzstd -tf \"$WEBAPP_PKG_STAGE\" | sed 's#^\\./##' | sort > \"$WEBAPP_MANIFEST_TXT_STAGE\""

if ! grep -q '^opt/pincabos/web/app.py$' "$WEBAPP_MANIFEST_TXT_STAGE"; then
  pco_fail "Archive WebApp invalide" "opt/pincabos/web/app.py absent de pkg-pincabos-webapp.zst"
fi

if ! grep -q '^opt/pincabos/web/static' "$WEBAPP_MANIFEST_TXT_STAGE"; then
  pco_fail "Archive WebApp invalide" "opt/pincabos/web/static absent de pkg-pincabos-webapp.zst"
fi

if ! grep -q '^opt/pincabos/tools' "$WEBAPP_MANIFEST_TXT_STAGE"; then
  pco_fail "Archive WebApp invalide" "opt/pincabos/tools absent de pkg-pincabos-webapp.zst"
fi

WEBAPP_FORBIDDEN_RE='(^|/)(opt/pincabos/install(/|$)|var/www/html/install(/|$)|go-pincabos\.sh$|help-pincabos\.sh$|01-install-system\.sh$|02-install-engine\.sh$|03-install-check\.sh$|RUN_[0-9A-Z_ -]*|modules(/|$)|etc/calamares(/|$)|opt/pincabos/(logs|backups|flags|download|tmp)(/|$)|(^|/)\.venv(/|$)|(^|/)__pycache__(/|$)|\.pyc$)'

if grep -E "$WEBAPP_FORBIDDEN_RE" "$WEBAPP_MANIFEST_TXT_STAGE" >/tmp/pincabos-publy-webapp-archive-forbidden.txt; then
  echo "NOGOOD: Forbidden paths in WebApp/tools archive:"
  sed -n '1,220p' /tmp/pincabos-publy-webapp-archive-forbidden.txt
  pco_fail "Archive WebApp unsafe" "pkg-pincabos-webapp.zst contient install/RUN/modules/runtime/cache"
fi

WEBAPP_SHA256="$(sha256sum "$WEBAPP_PKG_STAGE" | awk '{print $1}')"
WEBAPP_SIZE_BYTES="$(stat -c '%s' "$WEBAPP_PKG_STAGE")"

printf "%s  %s\n" "$WEBAPP_SHA256" "$WEBAPP_PKG_NAME" > "$WEBAPP_SHA_STAGE"

# Keep checksums.sha256 compatible but include WebApp too.
if [ -f "$CHECKSUMS_STAGE" ]; then
  grep -v "  ${WEBAPP_PKG_NAME}$" "$CHECKSUMS_STAGE" > "${CHECKSUMS_STAGE}.tmp" || true
  mv -f "${CHECKSUMS_STAGE}.tmp" "$CHECKSUMS_STAGE"
  printf "%s  %s\n" "$WEBAPP_SHA256" "$WEBAPP_PKG_NAME" >> "$CHECKSUMS_STAGE"
fi

python3 - "$WEBAPP_MANIFEST_JSON_STAGE" "$WEBAPP_PKG_NAME" "$WEBAPP_SHA256" "$WEBAPP_SIZE_BYTES" "$WEBAPP_MANIFEST_TXT_STAGE" <<'PY_WEBAPP_MANIFEST'
import json, sys, time
from pathlib import Path

out, pkg_name, sha, size, manifest_txt = sys.argv[1:]
files = []
p = Path(manifest_txt)
if p.exists():
    files = [line.strip() for line in p.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]

data = {
    "name": "pkg-pincabos-webapp",
    "created_by": "Karots Sugarpie",
    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "package": pkg_name,
    "sha256": sha,
    "size_bytes": int(size),
    "compression": "zstd",
    "tar": True,
    "policy": {
        "contains_webapp": True,
        "contains_tools": True,
        "must_not_contain_install_or_run_scripts": True,
        "must_not_contain_modules": True,
        "must_not_contain_calamares": True,
        "must_not_contain_runtime_cache_logs_backups": True
    },
    "files": files,
}
Path(out).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY_WEBAPP_MANIFEST

python3 -m json.tool "$WEBAPP_MANIFEST_JSON_STAGE" >/dev/null
pco_check "Metadata WebApp/tools: SHA + manifest JSON générés"
# === PINCABOS PUBLY WEBAPP PACKAGE METADATA END ===


pco_step "6" "Transfert archive/json/checksums/manifest vers WebServer remote"

if [ "$DRY_RUN" -eq 1 ]; then
  echo "${C_YELLOW}DRY-RUN:${C_RESET} aucun transfert vers ${WEB_REMOTE}:${WEB_REMOTE_UPDATES}"
  echo "Fichiers qui seraient transférés:"
  ls -lah "$PKG_STAGE" "$WEBAPP_PKG_STAGE" "$LATEST_STAGE" "$CHECKSUMS_STAGE" "$MANIFEST_STAGE" "$PKG_SHA_STAGE" "$PKG_MANIFEST_JSON_STAGE" "$WEBAPP_SHA_STAGE" "$WEBAPP_MANIFEST_JSON_STAGE" "$WEBAPP_MANIFEST_TXT_STAGE"
  pco_check "Dry-run transfert remote simulé"
else
  run_spin "Transfert fichiers vers WebServer" pco_scp_to_remote_updates "$PKG_STAGE" "$WEBAPP_PKG_STAGE" "$LATEST_STAGE" "$CHECKSUMS_STAGE" "$MANIFEST_STAGE" "$PKG_SHA_STAGE" "$PKG_MANIFEST_JSON_STAGE" "$WEBAPP_SHA_STAGE" "$WEBAPP_MANIFEST_JSON_STAGE" "$WEBAPP_MANIFEST_TXT_STAGE"

  run_spin "Validation fichiers remote" pco_ssh "
    chmod 0644 '${WEB_REMOTE_UPDATES}/${PKG_NAME}' '${WEB_REMOTE_UPDATES}/${WEBAPP_PKG_NAME}' '${WEB_REMOTE_UPDATES}/${LATEST_NAME}' '${WEB_REMOTE_UPDATES}/${CHECKSUMS_NAME}' '${WEB_REMOTE_UPDATES}/${MANIFEST_NAME}' '${WEB_REMOTE_UPDATES}/${PKG_SHA_NAME}' '${WEB_REMOTE_UPDATES}/${PKG_MANIFEST_JSON_NAME}' '${WEB_REMOTE_UPDATES}/${WEBAPP_SHA_NAME}' '${WEB_REMOTE_UPDATES}/${WEBAPP_MANIFEST_JSON_NAME}' '${WEB_REMOTE_UPDATES}/${WEBAPP_MANIFEST_TXT_NAME}' &&
    ls -lah '${WEB_REMOTE_UPDATES}'
  "

  pco_check "Fichiers transférés vers ${WEB_REMOTE}:${WEB_REMOTE_UPDATES}"

  echo
  echo "Nettoyage local après transfert réussi..."
  run_spin "Suppression fichiers temporaires locaux" rm -f "$PKG_STAGE" "$WEBAPP_PKG_STAGE" "$LATEST_STAGE" "$CHECKSUMS_STAGE" "$MANIFEST_STAGE" "$PKG_SHA_STAGE" "$PKG_MANIFEST_JSON_STAGE" "$WEBAPP_SHA_STAGE" "$WEBAPP_MANIFEST_JSON_STAGE" "$WEBAPP_MANIFEST_TXT_STAGE"
  pco_check "Archives temporaires locales supprimées"
fi

# ────────────────────────────────────────────────────────────────
# Étape 7
# ────────────────────────────────────────────────────────────────

pco_step "7" "Résumé GO/NOGOOD"

echo
echo "${C_WHITE}Package officiel:${C_RESET} ${WEB_REMOTE}:${WEB_REMOTE_UPDATES}/${PKG_NAME}"
echo "${C_WHITE}latest    :${C_RESET} ${WEB_REMOTE}:${WEB_REMOTE_UPDATES}/${LATEST_NAME}"
echo "${C_WHITE}checksums :${C_RESET} ${WEB_REMOTE}:${WEB_REMOTE_UPDATES}/${CHECKSUMS_NAME}"
echo "${C_WHITE}manifest  :${C_RESET} ${WEB_REMOTE}:${WEB_REMOTE_UPDATES}/${MANIFEST_NAME}"
echo "${C_WHITE}SHA256    :${C_RESET} $SHA256"
echo "${C_WHITE}Size      :${C_RESET} $SIZE_BYTES bytes"
echo "${C_WHITE}Dry-run   :${C_RESET} $DRY_RUN"
echo "${C_WHITE}Engine    :${C_RESET} $TOTAL_FILES fichiers/répertoires retenus"
echo "${C_WHITE}WebApp    :${C_RESET} $WEBAPP_TOTAL fichiers/répertoires WebApp retenus"
echo "${C_WHITE}WebApp pkg extra:${C_RESET} ${WEB_REMOTE}:${WEB_REMOTE_UPDATES}/${WEBAPP_PKG_NAME}"
echo "${C_WHITE}SHA officiel:${C_RESET} ${WEB_REMOTE}:${WEB_REMOTE_UPDATES}/${PKG_SHA_NAME}"
echo "${C_WHITE}Manifest officiel:${C_RESET} ${WEB_REMOTE}:${WEB_REMOTE_UPDATES}/${PKG_MANIFEST_JSON_NAME}"

pco_check "PUBLY terminé"

pco_summary
exit 0
