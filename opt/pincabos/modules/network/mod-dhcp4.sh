#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────
# PINCABOS_MODULE_NAME="mod-dhcp4"
# PINCABOS_MODULE_VERSION="0.1.1"
# PINCABOS_MODULE_CATEGORY="network"
# PINCABOS_MODULE_PATH="/opt/pincabos/modules/network/mod-dhcp4.sh"
# PINCABOS_MODULE_CREATED_BY="Karots Sugarpie"
# PINCABOS_MODULE_CREATED_FOR="PinCabOS"
# PINCABOS_MODULE_DESCRIPTION="Reset network configuration, detect wired/wifi interfaces, select active wired interface, apply DHCP4, and verify IP/gateway/DNS/connectivity."
#
# PINCABOS_MODULE_REQUIRES_ROOT="yes"
# PINCABOS_MODULE_REQUIRES_NETWORK="no_before_apply_yes_after_apply"
# PINCABOS_MODULE_REQUIRES_PACKAGES="bash coreutils iproute2 iputils-ping netplan.io systemd python3 network-manager wpasupplicant"
# PINCABOS_MODULE_REQUIRES_COMMANDS="/usr/bin/bash /usr/bin/sed /usr/bin/grep /usr/bin/awk /usr/bin/tee /usr/sbin/ip /usr/bin/find /usr/bin/cat /usr/bin/readlink /usr/bin/systemctl /usr/sbin/netplan /usr/bin/resolvectl /usr/bin/ping /usr/bin/python3"
#
# PINCABOS_MODULE_TOUCHES="/etc/netplan/00-pincabos-dhcp4.yaml /etc/netplan/*.yaml.pincabos-disabled /var/lib/dhcp /run/systemd/netif/leases"
# PINCABOS_MODULE_GENERATES="/opt/pincabos/logs/mod-dhcp4-*.log /opt/pincabos/backups/* /opt/pincabos/state/network-dhcp4.env"
#
# PINCABOS_MODULE_STATUS_FORMAT="GO [√] / NOGO [***] ERR-REFERENCE"
# PINCABOS_MODULE_MANIFEST="/opt/pincabos/modules/modules.json"
# PINCABOS_MODULE_INSTALL_JSON="/opt/pincabos/install/install.json"
#
# Notes:
# - This module is non-interactive.
# - It prefers a physical wired interface with carrier=1.
# - It does not spoof or modify hardware MAC addresses.
# - It cleans IP addresses and DHCP leases, not hardware MAC identity.
# - Running this module over SSH may briefly interrupt connectivity.
# ────────────────────────────────────────────────────────────────
set -Eeuo pipefail

ORANGE='\033[38;5;208m'
CYAN='\033[36m'
GREEN='\033[32m'
YELLOW='\033[33m'
RED='\033[31m'
BLUE='\033[34m'
DIM='\033[2m'
NC='\033[0m'

ROOT="/opt/pincabos"
LOG_DIR="$ROOT/logs"
TMP_DIR="$ROOT/tmp"
BACKUP_DIR="$ROOT/backups"
STATE_DIR="$ROOT/state"

LOG_FILE="$LOG_DIR/mod-dhcp4-$(date +%Y%m%d-%H%M%S).log"
CURRENT_STEP="BOOT"

SELECTED_IFACE=""
SELECTED_MAC=""
SELECTED_IP=""
SELECTED_GW=""
SELECTED_DNS=""
PING_8888_RESULT="NOT_TESTED"
PING_GOOGLE_RESULT="NOT_TESTED"

mkdir -p "$LOG_DIR" "$TMP_DIR" "$BACKUP_DIR" "$STATE_DIR"

exec > >(tee -a "$LOG_FILE") 2>&1

on_error() {
  local rc="$?"
  echo
  echo -e "${RED}NOGO [***] ERR-MOD-DHCP4-UNHANDLED-999${NC} Unexpected failure"
  echo -e "${RED}Step:${NC} $CURRENT_STEP"
  echo -e "${RED}Exit code:${NC} $rc"
  echo -e "${RED}Log:${NC} $LOG_FILE"
  exit "$rc"
}

trap on_error ERR

pco_title() {
  clear
  echo -e "${ORANGE}────────────────────────────────────────────────────────────────${NC}"
  echo -e "${ORANGE} PinCabOS Module - DHCP4 Network Reset${NC}"
  echo -e "${ORANGE}────────────────────────────────────────────────────────────────${NC}"
  echo -e "${DIM}Log: $LOG_FILE${NC}"
}

pco_step() {
  CURRENT_STEP="$1 - $2"
  echo
  echo -e "${CYAN}─[$1]─► $2 ◄────────────────────────────────────────${NC}"
}

pco_go() { echo -e "${GREEN}GO [√]${NC} $1"; }
pco_warn() { echo -e "${YELLOW}WARN${NC} $1"; }
pco_info() { echo -e "${BLUE}INFO${NC} $1"; }

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
  tmp_out="$(mktemp "$TMP_DIR/mod-dhcp4-spin.XXXXXX")"

  echo -ne "${CYAN}${label}${NC} "

  "$@" >"$tmp_out" 2>&1 &
  local pid="$!"
  local spin='|/-\'
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

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    pco_nogo "ERR-MOD-DHCP4-ROOT-001" "This module must be run as root"
  fi
  pco_go "Root privileges confirmed"
}

require_commands() {
  pco_step "01" "Validate required commands"

  local missing=0
  local required="ip grep awk sed find cat readlink systemctl ping python3"

  for cmd in $required; do
    if command -v "$cmd" >/dev/null 2>&1; then
      pco_go "Command available: $cmd"
    else
      pco_warn "Command missing: $cmd"
      missing=1
    fi
  done

  if command -v netplan >/dev/null 2>&1; then
    pco_go "Command available: netplan"
  else
    pco_warn "netplan missing; fallback will be attempted"
  fi

  if [ "$missing" -ne 0 ]; then
    pco_nogo "ERR-MOD-DHCP4-COMMANDS-001" "One or more required commands are missing"
  fi
}

show_interfaces() {
  pco_step "02" "Detect network interfaces"

  echo "All interfaces:"
  ip -br link show || true

  echo
  echo "Wired candidates:"
  for iface_path in /sys/class/net/*; do
    local iface mac carrier oper driver
    iface="$(basename "$iface_path")"
    [ "$iface" = "lo" ] && continue

    if [[ "$iface" =~ ^(e|en|eth) ]]; then
      mac="$(cat "$iface_path/address" 2>/dev/null || echo unknown)"
      carrier="$(cat "$iface_path/carrier" 2>/dev/null || echo unknown)"
      oper="$(cat "$iface_path/operstate" 2>/dev/null || echo unknown)"
      driver="$(basename "$(readlink -f "$iface_path/device/driver" 2>/dev/null || echo unknown)")"
      echo "  $iface  mac=$mac  carrier=$carrier  state=$oper  driver=$driver"
    fi
  done

  echo
  echo "Wi-Fi candidates:"
  for iface_path in /sys/class/net/*; do
    local iface mac oper driver
    iface="$(basename "$iface_path")"
    [ "$iface" = "lo" ] && continue

    if [ -d "$iface_path/wireless" ] || [[ "$iface" =~ ^(w|wl|wlan) ]]; then
      mac="$(cat "$iface_path/address" 2>/dev/null || echo unknown)"
      oper="$(cat "$iface_path/operstate" 2>/dev/null || echo unknown)"
      driver="$(basename "$(readlink -f "$iface_path/device/driver" 2>/dev/null || echo unknown)")"
      echo "  $iface  mac=$mac  state=$oper  driver=$driver"
    fi
  done

  pco_go "Interface detection completed"
}

select_wired_interface() {
  pco_step "03" "Select active wired interface"

  local candidate=""

  for iface_path in /sys/class/net/*; do
    local iface carrier
    iface="$(basename "$iface_path")"
    [ "$iface" = "lo" ] && continue

    if [[ "$iface" =~ ^(e|en|eth) ]]; then
      carrier="$(cat "$iface_path/carrier" 2>/dev/null || echo 0)"
      if [ "$carrier" = "1" ]; then
        candidate="$iface"
        break
      fi
    fi
  done

  if [ -z "$candidate" ]; then
    pco_warn "No wired interface with carrier=1 found; selecting first wired interface"
    for iface_path in /sys/class/net/*; do
      local iface
      iface="$(basename "$iface_path")"
      [ "$iface" = "lo" ] && continue

      if [[ "$iface" =~ ^(e|en|eth) ]]; then
        candidate="$iface"
        break
      fi
    done
  fi

  if [ -z "$candidate" ]; then
    pco_nogo "ERR-MOD-DHCP4-NO-WIRED-001" "No wired interface found"
  fi

  SELECTED_IFACE="$candidate"
  SELECTED_MAC="$(cat "/sys/class/net/$SELECTED_IFACE/address" 2>/dev/null || echo unknown)"

  pco_go "Selected wired interface: $SELECTED_IFACE"
  pco_info "MAC address: $SELECTED_MAC"
}

backup_netplan() {
  pco_step "04" "Backup existing netplan files"

  local np_bk="$BACKUP_DIR/netplan-mod-dhcp4-$(date +%Y%m%d-%H%M%S)"
  mkdir -p "$np_bk"

  if compgen -G "/etc/netplan/*.yaml" >/dev/null; then
    cp -a /etc/netplan/*.yaml "$np_bk"/
    pco_go "Netplan backup created: $np_bk"
  else
    pco_warn "No existing netplan YAML files found"
  fi
}

clean_dhcp_leases() {
  pco_step "05" "Clean DHCP leases"
  rm -f /var/lib/dhcp/dhclient*.leases 2>/dev/null || true
  rm -f /var/lib/NetworkManager/dhclient*.lease 2>/dev/null || true
  rm -f /run/systemd/netif/leases/* 2>/dev/null || true
  pco_go "DHCP leases cleaned"
}

clean_interface_addresses() {
  pco_step "06" "Clean current IP addresses on selected interface"

  pco_info "Interface before cleanup:"
  ip -br addr show "$SELECTED_IFACE" || true

  run_spin "Bring interface up" ip link set "$SELECTED_IFACE" up
  run_spin "Flush IPv4 addresses" ip -4 addr flush dev "$SELECTED_IFACE"
  run_spin "Flush IPv6 addresses" ip -6 addr flush dev "$SELECTED_IFACE"

  pco_info "Interface after cleanup:"
  ip -br addr show "$SELECTED_IFACE" || true

  pco_go "Interface addresses cleaned"
}

write_netplan_dhcp4() {
  pco_step "07" "Write DHCP4 netplan config"

  mkdir -p /etc/netplan

  for f in /etc/netplan/*.yaml; do
    [ -e "$f" ] || continue
    case "$f" in
      /etc/netplan/00-pincabos-dhcp4.yaml) ;;
      *)
        if [ ! -f "$f.pincabos-disabled" ]; then
          mv "$f" "$f.pincabos-disabled"
          pco_go "Disabled old netplan file: $f"
        fi
        ;;
    esac
  done

  printf '%s\n' \
    "# PinCabOS DHCP4 network configuration" \
    "# Generated by mod-dhcp4.sh" \
    "network:" \
    "  version: 2" \
    "  renderer: networkd" \
    "  ethernets:" \
    "    ${SELECTED_IFACE}:" \
    "      dhcp4: true" \
    "      dhcp6: false" \
    "      optional: true" \
    > /etc/netplan/00-pincabos-dhcp4.yaml

  chmod 600 /etc/netplan/00-pincabos-dhcp4.yaml
  pco_go "Netplan DHCP4 config written"
}

apply_network_config() {
  pco_step "08" "Apply DHCP4 network configuration"

  if command -v netplan >/dev/null 2>&1; then
    run_spin "netplan generate" netplan generate
    run_spin "netplan apply" netplan apply
    pco_go "Netplan applied"
  elif command -v networkctl >/dev/null 2>&1; then
    run_spin "networkctl reconfigure" networkctl reconfigure "$SELECTED_IFACE"
    pco_go "Network reconfigured with networkctl"
  else
    pco_nogo "ERR-MOD-DHCP4-APPLY-001" "No netplan or networkctl available"
  fi

  sleep 4
}

collect_network_result() {
  pco_step "09" "Collect IP / gateway / DNS result"

  SELECTED_IP="$(ip -4 -o addr show dev "$SELECTED_IFACE" | awk '{print $4}' | head -n 1 || true)"
  SELECTED_GW="$(ip route show default 0.0.0.0/0 | awk '{print $3 " dev " $5}' | head -n 1 || true)"

  if command -v resolvectl >/dev/null 2>&1; then
    SELECTED_DNS="$(resolvectl dns "$SELECTED_IFACE" 2>/dev/null | sed 's/^.*: //' || true)"
  fi

  if [ -z "$SELECTED_DNS" ]; then
    SELECTED_DNS="$(grep -E '^nameserver ' /etc/resolv.conf 2>/dev/null | awk '{print $2}' | paste -sd ' ' - || true)"
  fi

  echo "Selected interface: $SELECTED_IFACE"
  echo "MAC address:        $SELECTED_MAC"
  echo "IPv4 address:       ${SELECTED_IP:-none}"
  echo "Default gateway:    ${SELECTED_GW:-none}"
  echo "DNS servers:        ${SELECTED_DNS:-none}"
  echo

  ip -br addr show "$SELECTED_IFACE" || true
  ip route || true

  printf '%s\n' \
    "PINCABOS_NETWORK_IFACE=\"$SELECTED_IFACE\"" \
    "PINCABOS_NETWORK_MAC=\"$SELECTED_MAC\"" \
    "PINCABOS_NETWORK_IPV4=\"$SELECTED_IP\"" \
    "PINCABOS_NETWORK_GATEWAY=\"$SELECTED_GW\"" \
    "PINCABOS_NETWORK_DNS=\"$SELECTED_DNS\"" \
    "PINCABOS_NETWORK_LOG=\"$LOG_FILE\"" \
    > "$STATE_DIR/network-dhcp4.env"

  chmod 644 "$STATE_DIR/network-dhcp4.env"

  if [ -n "$SELECTED_IP" ]; then
    pco_go "IPv4 address detected: $SELECTED_IP"
  else
    pco_nogo "ERR-MOD-DHCP4-NO-IP-001" "No IPv4 address received on $SELECTED_IFACE"
  fi
}

connectivity_tests() {
  pco_step "10" "Connectivity tests"

  if ping -c 2 -W 2 8.8.8.8 >/dev/null 2>&1; then
    PING_8888_RESULT="OK"
    pco_go "8.8.8.8 ----> OK"
  else
    PING_8888_RESULT="FAILED"
    pco_nogo "ERR-MOD-DHCP4-PING-8888-001" "8.8.8.8 ----> FAILED"
  fi

  if ping -c 2 -W 3 google.com >/dev/null 2>&1; then
    PING_GOOGLE_RESULT="OK"
    pco_go "google.com ----> OK"
  else
    PING_GOOGLE_RESULT="FAILED"
    pco_warn "google.com ----> FAILED; DNS may not be ready"
  fi
}

show_summary() {
  pco_step "11" "Final summary"

  echo
  echo -e "${YELLOW}Network card:      ${SELECTED_IFACE}${NC}"
  echo -e "${YELLOW}MAC address:       ${SELECTED_MAC}${NC}"
  echo -e "${YELLOW}IPv4/subnet:       ${SELECTED_IP:-none}${NC}"
  echo -e "${YELLOW}Gateway:           ${SELECTED_GW:-none}${NC}"
  echo -e "${YELLOW}DNS:               ${SELECTED_DNS:-none}${NC}"
  echo -e "${YELLOW}Ping 8.8.8.8:      8.8.8.8 ----> ${PING_8888_RESULT}${NC}"
  echo -e "${YELLOW}Ping google.com:   google.com ----> ${PING_GOOGLE_RESULT}${NC}"
  echo
  echo "State file:         $STATE_DIR/network-dhcp4.env"
  echo "Netplan file:       /etc/netplan/00-pincabos-dhcp4.yaml"
  echo "Log:                $LOG_FILE"
  echo

  echo -e "${GREEN}GO [√] PinCabOS DHCP4 network module completed${NC}"
}

main() {
  pco_title
  require_root
  require_commands
  show_interfaces
  select_wired_interface
  backup_netplan
  clean_dhcp_leases
  clean_interface_addresses
  write_netplan_dhcp4
  apply_network_config
  collect_network_result
  connectivity_tests
  show_summary
}

main "$@"
