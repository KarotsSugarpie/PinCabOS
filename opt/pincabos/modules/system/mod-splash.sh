#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────
# PINCABOS_MODULE_NAME="mod-splash"
# PINCABOS_MODULE_VERSION="0.1.1"
# PINCABOS_MODULE_CATEGORY="system"
# PINCABOS_MODULE_PATH="/opt/pincabos/modules/system/mod-splash.sh"
# PINCABOS_MODULE_CREATED_BY="Karots Sugarpie"
# PINCABOS_MODULE_CREATED_FOR="PinCabOS"
# PINCABOS_MODULE_DESCRIPTION="Apply PinCabOS MOTD splash, hostname, root/pinball prompts, root password, and SSH root/password login."
#
# PINCABOS_MODULE_REQUIRES_ROOT="yes"
# PINCABOS_MODULE_REQUIRES_NETWORK="only_if_openssh_server_missing"
# PINCABOS_MODULE_REQUIRES_PACKAGES="bash coreutils sed grep tee openssh-server python3 systemd"
# PINCABOS_MODULE_REQUIRES_COMMANDS="/usr/bin/bash /usr/bin/sed /usr/bin/grep /usr/bin/tee /usr/bin/hostname /usr/bin/hostnamectl /usr/sbin/chpasswd /usr/bin/systemctl /usr/sbin/sshd /usr/bin/python3"
#
# PINCABOS_MODULE_TOUCHES="/etc/hostname /etc/hosts /etc/motd /root/.bashrc /home/pinball/.bashrc /etc/ssh/sshd_config"
# PINCABOS_MODULE_GENERATES="/opt/pincabos/logs/mod-splash-*.log /opt/pincabos/backups/*"
#
# PINCABOS_MODULE_STATUS_FORMAT="GO [√] / NOGO [***] ERR-REFERENCE"
# PINCABOS_MODULE_MANIFEST="/opt/pincabos/modules/modules.json"
# PINCABOS_MODULE_INSTALL_JSON="/opt/pincabos/install/install.json"
#
# Notes:
# - This module is intended to be idempotent.
# - It creates backups before changing existing files.
# - It should be called by /opt/pincabos/install/go-pincabos.sh as the first module.
# ────────────────────────────────────────────────────────────────
set -Eeuo pipefail

ORANGE="\033[38;5;208m"
PURPLE='\033[38;5;129m'
CYAN="\033[36m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
BLUE="\033[34m"
DIM="\033[2m"
NC="\033[0m"

ROOT="/opt/pincabos"
LOG_DIR="$ROOT/logs"
TMP_DIR="$ROOT/tmp"
BACKUP_DIR="$ROOT/backups"

HOSTNAME_TARGET="PinCabOs"
ROOT_PASSWORD='Ges43po3$'

LOG_FILE="$LOG_DIR/mod-splash-$(date +%Y%m%d-%H%M%S).log"
CURRENT_STEP="BOOT"

mkdir -p "$LOG_DIR" "$TMP_DIR" "$BACKUP_DIR"

exec > >(tee -a "$LOG_FILE") 2>&1

on_error() {
  local rc="$?"
  echo
  echo -e "${RED}NOGO [***] ERR-MOD-SPLASH-UNHANDLED-999${NC} Unexpected failure"
  echo -e "${RED}Step:${NC} $CURRENT_STEP"
  echo -e "${RED}Exit code:${NC} $rc"
  echo -e "${RED}Log:${NC} $LOG_FILE"
  exit "$rc"
}

trap on_error ERR

pco_title() {
  clear
  echo -e "${ORANGE}────────────────────────────────────────────────────────────────${NC}"
  echo -e "${ORANGE} PinCabOS Module - Splash / Hostname / Root SSH${NC}"
  echo -e "${ORANGE}────────────────────────────────────────────────────────────────${NC}"
  echo -e "${DIM}Log: $LOG_FILE${NC}"
}

pco_step() {
  CURRENT_STEP="$1 - $2"
  echo
  echo -e "${CYAN}─[$1]─► $2 ◄────────────────────────────────────────${NC}"
}

pco_go() {
  echo -e "${GREEN}GO [√]${NC} $1"
}

pco_warn() {
  echo -e "${YELLOW}WARN${NC} $1"
}

pco_info() {
  echo -e "${BLUE}INFO${NC} $1"
}

pco_nogo() {
  local ref="$1"
  local msg="$2"
  echo -e "${RED}NOGO [***] ${ref}${NC} $msg"
  echo -e "${RED}Log:${NC} $LOG_FILE"
  exit 1
}

run_spin() {
  local label="$1"
  shift

  local tmp_out
  tmp_out="$(mktemp "$TMP_DIR/mod-splash-spin.XXXXXX")"

  echo -ne "${CYAN}${label}${NC} "

  "$@" >"$tmp_out" 2>&1 &
  local pid="$!"

  local spin="|/-\\"
  local i=0

  while kill -0 "$pid" 2>/dev/null; do
    i=$(( (i + 1) % 4 ))
    printf "\r${CYAN}${label}${NC} [%c] " "${spin:$i:1}"
    sleep 0.12
  done

  wait "$pid"
  local rc="$?"

  if [ "$rc" -eq 0 ]; then
    printf "\r${GREEN}GO [√]${NC} ${label}\n"
    rm -f "$tmp_out"
    return 0
  fi

  printf "\r${RED}NOGO [***]${NC} ${label}\n"
  echo
  cat "$tmp_out"
  rm -f "$tmp_out"
  return "$rc"
}

run_spin_bash() {
  local label="$1"
  local command="$2"
  run_spin "$label" bash -lc "$command"
}

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    pco_nogo "ERR-MOD-SPLASH-ROOT-001" "This module must be run as root"
  fi
  pco_go "Root privileges confirmed"
}

backup_file() {
  local file="$1"

  if [ -e "$file" ]; then
    local safe_name
    safe_name="$(echo "$file" | sed "s#/#_#g" | sed "s#^_##")"
    local backup="$BACKUP_DIR/${safe_name}.backup-mod-splash-$(date +%Y%m%d-%H%M%S)"
    cp -a "$file" "$backup"
    pco_go "Backup created: $backup"
  else
    pco_warn "No existing file to backup: $file"
  fi
}

ensure_openssh_server() {
  pco_step "01" "Ensure OpenSSH server is installed"

  if command -v sshd >/dev/null 2>&1 || [ -x /usr/sbin/sshd ]; then
    pco_go "OpenSSH server already installed"
    return 0
  fi

  if ! command -v apt-get >/dev/null 2>&1; then
    pco_nogo "ERR-MOD-SPLASH-APT-001" "apt-get not found"
  fi

  run_spin_bash "APT update" "DEBIAN_FRONTEND=noninteractive apt-get update"
  run_spin_bash "Install openssh-server" "DEBIAN_FRONTEND=noninteractive apt-get install -y openssh-server"

  if command -v sshd >/dev/null 2>&1 || [ -x /usr/sbin/sshd ]; then
    pco_go "OpenSSH server installed"
  else
    pco_nogo "ERR-MOD-SPLASH-SSH-001" "OpenSSH server install failed"
  fi
}

apply_hostname() {
  pco_step "02" "Apply PinCabOS hostname"

  backup_file "/etc/hostname"
  backup_file "/etc/hosts"

  echo "$HOSTNAME_TARGET" > /etc/hostname

  if command -v hostnamectl >/dev/null 2>&1; then
    hostnamectl set-hostname "$HOSTNAME_TARGET" || true
    hostnamectl set-hostname --static "$HOSTNAME_TARGET" || true
    hostnamectl set-hostname --pretty "$HOSTNAME_TARGET" || true
  fi

  hostname "$HOSTNAME_TARGET" || true

  if grep -qE "^[[:space:]]*127\.0\.1\.1[[:space:]]+" /etc/hosts; then
    sed -i "s/^[[:space:]]*127\.0\.1\.1[[:space:]].*/127.0.1.1       ${HOSTNAME_TARGET}/" /etc/hosts
  else
    echo "127.0.1.1       ${HOSTNAME_TARGET}" >> /etc/hosts
  fi

  pco_go "Hostname applied: $HOSTNAME_TARGET"
}



apply_ascii_splash() {
  pco_step "03" "Apply PinCabOS colored ASCII splash"

  backup_file "/etc/motd"

  python3 > /etc/motd <<'PY_SPLASH'
ORANGE = "\033[38;5;208m"
DARKBLUE = "\033[38;5;20m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
PURPLE = "\033[38;5;129m"
NC = "\033[0m"

logo = [
    "██████╗ ██╗███╗   ██╗ ██████╗ █████╗ ██████╗  ██████╗ ███████╗",
    "██╔══██╗██║████╗  ██║██╔════╝██╔══██╗██╔══██╗██╔═══██╗██╔════╝",
    "██████╔╝██║██╔██╗ ██║██║     ███████║██████╔╝██║   ██║███████╗",
    "██╔═══╝ ██║██║╚██╗██║██║     ██╔══██║██╔══██╗██║   ██║╚════██║",
    "██║     ██║██║ ╚████║╚██████╗██║  ██║██████╔╝╚██████╔╝███████║",
    "╚═╝     ╚═╝╚═╝  ╚═══╝ ╚═════╝╚═╝  ╚═╝╚═════╝  ╚═════╝ ╚══════╝",
]

blue_chars = set("╚═╝╗║╔")
orange_chars = set("█")

def color_logo(line):
    out = []
    active = None

    for ch in line:
        if ch in orange_chars:
            wanted = ORANGE
        elif ch in blue_chars:
            wanted = DARKBLUE
        else:
            wanted = None

        if wanted != active:
            if active is not None:
                out.append(NC)
            if wanted is not None:
                out.append(wanted)
            active = wanted

        out.append(ch)

    if active is not None:
        out.append(NC)

    return "".join(out)

print()
print(f"{ORANGE}────────────────────────────────────────────────────────────────{NC}")

for line in logo:
    print(color_logo(line))

print(f"{ORANGE}────────────────────────────────────────────────────────────────{NC}")
print()
print(f"{CYAN}Ultimate VPinball Linux Cabinet System{NC}")
print(f"{PURPLE}Created by Karots Sugarpie{NC}")
print()
print(f"{YELLOW}Default console:{NC} root@PinCabOs")
print(f"{YELLOW}Help:{NC}            help-pincabos")
print(f"{YELLOW}Installer:{NC}       go-pincabos --resume")
print()
PY_SPLASH

  chmod 644 /etc/motd
  pco_go "Colored ASCII splash applied to /etc/motd"
}



apply_root_prompt() {
  pco_step "04" "Apply colored root and pinball prompts"

  mkdir -p /root
  touch /root/.bashrc
  backup_file "/root/.bashrc"

  sed -i '/# BEGIN PINCABOS COLORED PROMPT/,/# END PINCABOS COLORED PROMPT/d' /root/.bashrc
  sed -i '/# BEGIN PINCABOS ROOT PROMPT/,/# END PINCABOS ROOT PROMPT/d' /root/.bashrc

  cat >> /root/.bashrc <<'EOF'

# BEGIN PINCABOS COLORED PROMPT
# root@ color / PinCabOS color prompt
export PS1='\[\033[31m\]root@\[\033[38;5;129m\]PinCab\[\033[38;5;208m\]OS\[\033[36m\]:\w\[\033[0m\]# '
# END PINCABOS COLORED PROMPT
EOF

  pco_go "Root prompt applied"

  if id pinball >/dev/null 2>&1; then
    mkdir -p /home/pinball
    touch /home/pinball/.bashrc
    backup_file "/home/pinball/.bashrc"

    sed -i '/# BEGIN PINCABOS COLORED PROMPT/,/# END PINCABOS COLORED PROMPT/d' /home/pinball/.bashrc
    sed -i '/# BEGIN PINCABOS ROOT PROMPT/,/# END PINCABOS ROOT PROMPT/d' /home/pinball/.bashrc

    cat >> /home/pinball/.bashrc <<'EOF'

# BEGIN PINCABOS COLORED PROMPT
# pinball@ color / PinCabOS color prompt
export PS1='\[\033[32m\]pinball@\[\033[38;5;129m\]PinCab\[\033[38;5;208m\]OS\[\033[36m\]:\w\[\033[0m\]\$ '
# END PINCABOS COLORED PROMPT
EOF

    chown pinball:pinball /home/pinball/.bashrc
    pco_go "Pinball prompt applied"
  else
    pco_warn "User pinball does not exist yet"
  fi

  pco_go "Colored prompts applied"
}

set_root_password() {
  pco_step "05" "Set default root password"

  echo "root:${ROOT_PASSWORD}" | chpasswd

  pco_go "Root password configured"
}

configure_root_ssh() {
  pco_step "06" "Configure SSH root login with password"

  local sshd_config="/etc/ssh/sshd_config"

  if [ ! -f "$sshd_config" ]; then
    pco_nogo "ERR-MOD-SPLASH-SSHD-CONFIG-001" "Missing $sshd_config"
  fi

  backup_file "$sshd_config"

  cp -a "$sshd_config" "$sshd_config.pincabos-work"

  sed -i -E \
    -e "/^[#[:space:]]*PermitRootLogin[[:space:]]+/d" \
    -e "/^[#[:space:]]*PasswordAuthentication[[:space:]]+/d" \
    -e "/^[#[:space:]]*KbdInteractiveAuthentication[[:space:]]+/d" \
    -e "/^[#[:space:]]*UsePAM[[:space:]]+/d" \
    "$sshd_config.pincabos-work"

  cat >> "$sshd_config.pincabos-work" <<'EOF'

# BEGIN PINCABOS ROOT SSH
PermitRootLogin yes
PasswordAuthentication yes
KbdInteractiveAuthentication yes
UsePAM yes
# END PINCABOS ROOT SSH
EOF

  if [ -x /usr/sbin/sshd ]; then
    /usr/sbin/sshd -t -f "$sshd_config.pincabos-work"
  else
    sshd -t -f "$sshd_config.pincabos-work"
  fi

  mv "$sshd_config.pincabos-work" "$sshd_config"

  pco_go "SSH root/password configuration applied"
}

restart_ssh_service() {
  pco_step "07" "Enable and restart SSH service"

  if systemctl cat ssh.service >/dev/null 2>&1; then
    run_spin "Enable ssh.service" systemctl enable ssh.service
    run_spin "Restart ssh.service" systemctl restart ssh.service
    pco_go "ssh.service active"
    return 0
  fi

  if systemctl cat sshd.service >/dev/null 2>&1; then
    run_spin "Enable sshd.service" systemctl enable sshd.service
    run_spin "Restart sshd.service" systemctl restart sshd.service
    pco_go "sshd.service active"
    return 0
  fi

  if command -v service >/dev/null 2>&1 && service ssh status >/dev/null 2>&1; then
    run_spin "Restart ssh via service command" service ssh restart
    pco_go "ssh service restarted with service command"
    return 0
  fi

  if [ -x /usr/sbin/sshd ]; then
    pco_warn "No systemd unit detected, but /usr/sbin/sshd exists"
    pco_go "SSH daemon binary exists; skipping service restart"
    return 0
  fi

  pco_nogo "ERR-MOD-SPLASH-SERVICE-001" "No ssh or sshd service found"
}

verify_result() {
  pco_step "08" "Verify result"

  echo "Hostname command: $(hostname)"
  echo "Hostname file:    $(cat /etc/hostname 2>/dev/null || true)"

  if [ "$(cat /etc/hostname 2>/dev/null)" != "$HOSTNAME_TARGET" ]; then
    pco_nogo "ERR-MOD-SPLASH-HOSTNAME-VERIFY-001" "Hostname file is not $HOSTNAME_TARGET"
  fi

  if [ ! -f /etc/motd ]; then
    pco_nogo "ERR-MOD-SPLASH-MOTD-VERIFY-001" "/etc/motd missing"
  fi

  if ! grep -q "BEGIN PINCABOS COLORED PROMPT" /root/.bashrc; then
    pco_nogo "ERR-MOD-SPLASH-PROMPT-VERIFY-001" "Root prompt block missing"
  fi

  if ! grep -q "^PermitRootLogin yes" /etc/ssh/sshd_config; then
    pco_nogo "ERR-MOD-SPLASH-SSH-VERIFY-001" "PermitRootLogin yes missing"
  fi

  if ! grep -q "^PasswordAuthentication yes" /etc/ssh/sshd_config; then
    pco_nogo "ERR-MOD-SPLASH-SSH-VERIFY-002" "PasswordAuthentication yes missing"
  fi

  if ! grep -q "^KbdInteractiveAuthentication yes" /etc/ssh/sshd_config; then
    pco_nogo "ERR-MOD-SPLASH-SSH-VERIFY-003" "KbdInteractiveAuthentication yes missing"
  fi

  pco_go "Verification completed"
}

show_summary() {
  pco_step "09" "Final summary"

  echo "Hostname target:      $HOSTNAME_TARGET"
  echo "MOTD:                 /etc/motd"
  echo "Root prompt:          root@PinCabOS:#"
  echo "SSH root login:       enabled"
  echo "SSH password login:   enabled"
  echo "Root password:        Dev43po3$"
  echo "Log:                  $LOG_FILE"
  echo

  echo -e "${GREEN}GO [√] PinCabOS splash/root SSH module completed${NC}"
}

main() {
  pco_title
  require_root

  ensure_openssh_server
  apply_hostname
  apply_ascii_splash
  apply_root_prompt
  set_root_password
  configure_root_ssh
  restart_ssh_service
  verify_result
  show_summary
}

main "$@"
