#!/usr/bin/env bash
# Created by Karots Sugarpie
# PINCABOS_SCRIPT_NAME="mod-ssid.sh"
# PINCABOS_SCRIPT_ROLE="Professional Wi-Fi SSID scanner, manual SSID entry, WPA key capture, Netplan Wi-Fi writer, and DNS/gateway/ping validation"
# PINCABOS_SCRIPT_REQUIRES_FILES="/opt/pincabos/modules/modules.json /opt/pincabos/modules/network/mod-dhcp4.sh /opt/pincabos/modules/network/mod-ssid.sh"
# PINCABOS_SCRIPT_REQUIRES_PACKAGES="iproute2 iw rfkill netplan.io systemd iputils-ping python3 grep gawk sed coreutils findutils wpasupplicant wireless-regdb"
# PINCABOS_SCRIPT_REQUIRES_COMMANDS="ip iw netplan systemctl ping python3 grep awk sed cat readlink tee find timeout wpa_passphrase rfkill"
# PINCABOS_SCRIPT_LOG_DIR="/opt/pincabos/logs"
# PINCABOS_SCRIPT_MANIFEST="/opt/pincabos/modules/modules.json"

# ────────────────────────────────────────────────────────────────
# PINCABOS_MODULE_NAME="mod-ssid"
# PINCABOS_MODULE_VERSION="0.1.0"
# PINCABOS_MODULE_CATEGORY="network"
# PINCABOS_MODULE_PATH="/opt/pincabos/modules/network/mod-ssid.sh"
# PINCABOS_MODULE_CREATED_BY="Karots Sugarpie"
# PINCABOS_MODULE_CREATED_FOR="PinCabOS"
# PINCABOS_MODULE_DESCRIPTION="Detect Wi-Fi interfaces, scan valid SSIDs, allow manual hidden SSID mode, securely request Wi-Fi key, apply DHCP4 Wi-Fi configuration, and verify DNS/connectivity."
#
# PINCABOS_MODULE_REQUIRES_ROOT="yes"
# PINCABOS_MODULE_REQUIRES_NETWORK="optional_before_apply_yes_after_apply"
# PINCABOS_MODULE_REQUIRES_PACKAGES="bash coreutils iproute2 iputils-ping iw wpasupplicant rfkill netplan.io systemd python3"
# PINCABOS_MODULE_REQUIRES_COMMANDS="/usr/bin/bash /usr/sbin/ip /usr/bin/iw /usr/sbin/rfkill /usr/sbin/netplan /usr/bin/systemctl /usr/bin/resolvectl /usr/bin/ping /usr/bin/python3 /usr/bin/grep /usr/bin/awk /usr/bin/sed /usr/bin/cat /usr/bin/readlink /usr/bin/tee /usr/bin/find /usr/bin/timeout"
#
# PINCABOS_MODULE_TOUCHES="/etc/netplan/01-pincabos-wifi-dhcp4.yaml /run/systemd/netif/leases /var/lib/dhcp"
# PINCABOS_MODULE_GENERATES="/opt/pincabos/logs/mod-ssid-*.log /opt/pincabos/backups/* /opt/pincabos/state/network-ssid.env"
#
# PINCABOS_MODULE_SECURITY_NOTES="Wi-Fi password is requested with hidden input. The generated Netplan file is chmod 600. The password is not printed in logs or summaries."
# PINCABOS_MODULE_STATUS_FORMAT="GO [√] / NOGO [***] ERR-REFERENCE"
# PINCABOS_MODULE_MANIFEST="/opt/pincabos/modules/modules.json"
# PINCABOS_MODULE_INSTALL_JSON="/opt/pincabos/install/install.json"
#
# Notes:
# - This module is interactive because SSID/key selection may be required.
# - It exits cleanly if no Wi-Fi hardware is detected.
# - It supports visible SSID scan and manual hidden SSID mode.
# - It does not remove the wired DHCP4 configuration created by mod-dhcp4.sh.
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

LOG_FILE="$LOG_DIR/mod-ssid-$(date +%Y%m%d-%H%M%S).log"
CURRENT_STEP="BOOT"

WIFI_IFACE=""
WIFI_MAC=""
SELECTED_SSID=""
SELECTED_SECURITY=""
WIFI_IPV4=""
WIFI_GATEWAY=""
WIFI_DNS=""
PING_8888_RESULT="NOT_TESTED"
PING_GOOGLE_RESULT="NOT_TESTED"

mkdir -p "$LOG_DIR" "$TMP_DIR" "$BACKUP_DIR" "$STATE_DIR"

exec > >(tee -a "$LOG_FILE") 2>&1

on_error() {
  local rc="$?"
  echo
  echo -e "${RED}NOGO [***] ERR-MOD-SSID-UNHANDLED-999${NC} Unexpected failure"
  echo -e "${RED}Step:${NC} $CURRENT_STEP"
  echo -e "${RED}Exit code:${NC} $rc"
  echo -e "${RED}Log:${NC} $LOG_FILE"
  exit "$rc"
}

trap on_error ERR

pco_title() {
  clear
  echo -e "${ORANGE}────────────────────────────────────────────────────────────────${NC}"
  echo -e "${ORANGE} PinCabOS Module - Wi-Fi SSID Setup${NC}"
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
  tmp_out="$(mktemp "$TMP_DIR/mod-ssid-spin.XXXXXX")"

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
    pco_nogo "ERR-MOD-SSID-ROOT-001" "This module must be run as root"
  fi
  pco_go "Root privileges confirmed"
}

require_commands() {
  pco_step "01" "Validate required commands"

  local missing=0
  local required="ip iw netplan systemctl ping python3 grep awk sed cat readlink tee find timeout"

  for cmd in $required; do
    if command -v "$cmd" >/dev/null 2>&1; then
      pco_go "Command available: $cmd"
    else
      pco_warn "Command missing: $cmd"
      missing=1
    fi
  done

  if command -v rfkill >/dev/null 2>&1; then
    pco_go "Command available: rfkill"
  else
    pco_warn "rfkill missing; Wi-Fi unblock step will be skipped"
  fi

  if [ "$missing" -ne 0 ]; then
    pco_nogo "ERR-MOD-SSID-COMMANDS-001" "One or more required commands are missing"
  fi
}

detect_wifi_interfaces() {
  pco_step "02" "Detect Wi-Fi interfaces"

  local found=()

  for iface_path in /sys/class/net/*; do
    local iface
    iface="$(basename "$iface_path")"
    [ "$iface" = "lo" ] && continue

    if [ -d "$iface_path/wireless" ] || [[ "$iface" =~ ^(w|wl|wlan) ]]; then
      found+=("$iface")
    fi
  done

  if [ "${#found[@]}" -eq 0 ]; then
    echo 'PINCABOS_WIFI_DETECTED="no"' > "$STATE_DIR/network-ssid.env"
    echo "PINCABOS_WIFI_LOG=\"$LOG_FILE\"" >> "$STATE_DIR/network-ssid.env"
    chmod 644 "$STATE_DIR/network-ssid.env"
    pco_go "No Wi-Fi device detected; skipping SSID setup"
    exit 0
  fi

  echo "Detected Wi-Fi interfaces:"
  local idx=1
  for iface in "${found[@]}"; do
    local mac oper driver
    mac="$(cat "/sys/class/net/$iface/address" 2>/dev/null || echo unknown)"
    oper="$(cat "/sys/class/net/$iface/operstate" 2>/dev/null || echo unknown)"
    driver="$(basename "$(readlink -f "/sys/class/net/$iface/device/driver" 2>/dev/null || echo unknown)")"
    echo "  [$idx] $iface  mac=$mac  state=$oper  driver=$driver"
    idx=$((idx + 1))
  done

  if [ "${#found[@]}" -eq 1 ]; then
    WIFI_IFACE="${found[0]}"
  else
    echo
    read -r -p "Select Wi-Fi interface number [1]: " choice
    choice="${choice:-1}"

    if ! [[ "$choice" =~ ^[0-9]+$ ]]; then
      pco_nogo "ERR-MOD-SSID-IFACE-CHOICE-001" "Invalid Wi-Fi interface choice"
    fi

    local array_index=$((choice - 1))
    if [ "$array_index" -lt 0 ] || [ "$array_index" -ge "${#found[@]}" ]; then
      pco_nogo "ERR-MOD-SSID-IFACE-CHOICE-002" "Wi-Fi interface choice out of range"
    fi

    WIFI_IFACE="${found[$array_index]}"
  fi

  WIFI_MAC="$(cat "/sys/class/net/$WIFI_IFACE/address" 2>/dev/null || echo unknown)"

  pco_go "Selected Wi-Fi interface: $WIFI_IFACE"
  pco_info "Wi-Fi MAC address: $WIFI_MAC"
}

prepare_wifi_radio() {
  pco_step "03" "Prepare Wi-Fi radio"

  if command -v rfkill >/dev/null 2>&1; then
    rfkill unblock wifi || true
    pco_go "rfkill unblock wifi applied"
  else
    pco_warn "rfkill unavailable; skipped unblock"
  fi

  run_spin "Bring Wi-Fi interface up" ip link set "$WIFI_IFACE" up
}

scan_ssids() {
  pco_step "04" "Scan valid SSIDs"

  local scan_raw="$TMP_DIR/mod-ssid-scan.raw"
  local scan_tsv="$TMP_DIR/mod-ssid-scan.tsv"

  rm -f "$scan_raw" "$scan_tsv"

  if timeout 20 iw dev "$WIFI_IFACE" scan > "$scan_raw" 2>/dev/null; then
    pco_go "Wi-Fi scan completed"
  else
    pco_warn "Wi-Fi scan failed or timed out; manual mode still available"
    : > "$scan_raw"
  fi

  python3 - "$scan_raw" "$scan_tsv" <<'PYSCAN'
import sys
from pathlib import Path

raw = Path(sys.argv[1]).read_text(errors="replace").splitlines()
out = Path(sys.argv[2])

items = []
current = None

def commit(obj):
    if not obj:
        return
    ssid = obj.get("ssid", "").strip()
    if not ssid:
        return
    if any(ord(c) < 32 for c in ssid):
        return
    if ssid.lower() in {"<hidden>", "\\x00"}:
        return
    signal = obj.get("signal", "unknown")
    secure = obj.get("security", "OPEN")
    items.append((ssid, signal, secure))

for line in raw:
    stripped = line.strip()

    if stripped.startswith("BSS "):
      commit(current)
      current = {"ssid": "", "signal": "unknown", "security": "OPEN"}
      continue

    if current is None:
      continue

    if stripped.startswith("SSID:"):
      current["ssid"] = stripped.split("SSID:", 1)[1].strip()
      continue

    if stripped.startswith("signal:"):
      current["signal"] = stripped.split("signal:", 1)[1].strip()
      continue

    if "RSN:" in stripped or "WPA:" in stripped or "Authentication suites:" in stripped:
      if current.get("security") == "OPEN":
          current["security"] = "SECURED"

commit(current)

seen = set()
rows = []
for ssid, signal, security in items:
    key = ssid
    if key in seen:
        continue
    seen.add(key)
    rows.append((ssid, signal, security))

with out.open("w", encoding="utf-8") as fh:
    for ssid, signal, security in rows:
        fh.write(f"{ssid}\t{signal}\t{security}\n")
PYSCAN

  if [ -s "$scan_tsv" ]; then
    echo "Valid SSIDs detected:"
    local n=1
    while IFS=$'\t' read -r ssid signal security; do
      printf "  [%02d] %-32s signal=%-12s security=%s\n" "$n" "$ssid" "$signal" "$security"
      n=$((n + 1))
    done < "$scan_tsv"
    pco_go "Valid SSID list ready"
  else
    pco_warn "No visible valid SSID detected"
  fi
}

select_ssid() {
  pco_step "05" "Select SSID"

  local scan_tsv="$TMP_DIR/mod-ssid-scan.tsv"

  echo
  echo "Choose:"
  echo "  number = connect to visible SSID"
  echo "  M      = manual hidden SSID"
  echo "  S      = skip Wi-Fi setup"
  echo

  read -r -p "Selection [M]: " choice
  choice="${choice:-M}"

  if [[ "$choice" =~ ^[sS]$ ]]; then
    echo 'PINCABOS_WIFI_CONFIGURED="skipped"' > "$STATE_DIR/network-ssid.env"
    echo "PINCABOS_WIFI_LOG=\"$LOG_FILE\"" >> "$STATE_DIR/network-ssid.env"
    chmod 644 "$STATE_DIR/network-ssid.env"
    pco_go "Wi-Fi setup skipped by user"
    exit 0
  fi

  if [[ "$choice" =~ ^[mM]$ ]]; then
    read -r -p "Manual SSID: " SELECTED_SSID
    if [ -z "$SELECTED_SSID" ]; then
      pco_nogo "ERR-MOD-SSID-MANUAL-SSID-001" "Manual SSID cannot be empty"
    fi

    read -r -p "Is this network secured? [Y/n]: " secured
    secured="${secured:-Y}"

    if [[ "$secured" =~ ^[nN]$ ]]; then
      SELECTED_SECURITY="OPEN"
    else
      SELECTED_SECURITY="SECURED"
    fi

    pco_go "Manual SSID selected"
    return
  fi

  if ! [[ "$choice" =~ ^[0-9]+$ ]]; then
    pco_nogo "ERR-MOD-SSID-CHOICE-001" "Invalid SSID selection"
  fi

  if [ ! -s "$scan_tsv" ]; then
    pco_nogo "ERR-MOD-SSID-NO-SCAN-001" "No scan result available for numeric selection"
  fi

  local selected_line
  selected_line="$(sed -n "${choice}p" "$scan_tsv" || true)"

  if [ -z "$selected_line" ]; then
    pco_nogo "ERR-MOD-SSID-CHOICE-002" "SSID selection out of range"
  fi

  SELECTED_SSID="$(printf '%s' "$selected_line" | awk -F '\t' '{print $1}')"
  SELECTED_SECURITY="$(printf '%s' "$selected_line" | awk -F '\t' '{print $3}')"

  if [ -z "$SELECTED_SSID" ]; then
    pco_nogo "ERR-MOD-SSID-EMPTY-001" "Selected SSID is empty"
  fi

  pco_go "SSID selected: $SELECTED_SSID"
}

read_wifi_key() {
  pco_step "06" "Read Wi-Fi key"

  WIFI_PSK=""

  if [ "$SELECTED_SECURITY" = "OPEN" ]; then
    pco_warn "Selected network appears OPEN; no password will be written"
    return
  fi

  echo "Enter Wi-Fi key for SSID: $SELECTED_SSID"
  read -r -s -p "Wi-Fi key: " WIFI_PSK
  echo

  if [ -z "$WIFI_PSK" ]; then
    pco_nogo "ERR-MOD-SSID-KEY-EMPTY-001" "Wi-Fi key cannot be empty for secured network"
  fi

  if [ "${#WIFI_PSK}" -lt 8 ]; then
    pco_warn "Wi-Fi key is shorter than 8 characters; this may fail for WPA/WPA2"
  fi

  pco_go "Wi-Fi key received securely"
}

backup_wifi_netplan() {
  pco_step "07" "Backup existing Wi-Fi netplan"

  local target="/etc/netplan/01-pincabos-wifi-dhcp4.yaml"

  if [ -f "$target" ]; then
    local bk="$BACKUP_DIR/etc_netplan_01-pincabos-wifi-dhcp4.yaml.backup-mod-ssid-$(date +%Y%m%d-%H%M%S)"
    cp -a "$target" "$bk"
    pco_go "Backup created: $bk"
  else
    pco_go "No existing Wi-Fi netplan file"
  fi
}

yaml_quote() {
  python3 -c 'import sys; s=sys.stdin.read(); print("\"" + s.replace("\\", "\\\\").replace("\"", "\\\"") + "\"")'
}

write_wifi_netplan() {
  pco_step "08" "Write Wi-Fi DHCP4 netplan"

  mkdir -p /etc/netplan

  local ssid_q
  ssid_q="$(printf '%s' "$SELECTED_SSID" | yaml_quote)"

  {
    printf '%s\n' "# PinCabOS Wi-Fi DHCP4 network configuration"
    printf '%s\n' "# Generated by mod-ssid.sh"
    printf '%s\n' "# Created by Karots Sugarpie"
    printf '%s\n' "network:"
    printf '%s\n' "  version: 2"
    printf '%s\n' "  renderer: networkd"
    printf '%s\n' "  wifis:"
    printf '    %s:\n' "$WIFI_IFACE"
    printf '%s\n' "      optional: true"
    printf '%s\n' "      dhcp4: true"
    printf '%s\n' "      dhcp6: false"
    printf '%s\n' "      access-points:"
    printf '        %s:\n' "$ssid_q"

    if [ "$SELECTED_SECURITY" != "OPEN" ]; then
      local psk_q
      psk_q="$(printf '%s' "$WIFI_PSK" | yaml_quote)"
      printf '          password: %s\n' "$psk_q"
    fi
  } > /etc/netplan/01-pincabos-wifi-dhcp4.yaml

  chmod 600 /etc/netplan/01-pincabos-wifi-dhcp4.yaml

  pco_go "Wi-Fi netplan written: /etc/netplan/01-pincabos-wifi-dhcp4.yaml"
}

apply_wifi_netplan() {
  pco_step "09" "Apply Wi-Fi network configuration"

  run_spin "netplan generate" netplan generate
  run_spin "netplan apply" netplan apply

  sleep 6

  pco_go "Wi-Fi netplan applied"
}

collect_wifi_result() {
  pco_step "10" "Collect Wi-Fi IP / gateway / DNS"

  WIFI_IPV4="$(ip -4 -o addr show dev "$WIFI_IFACE" | awk '{print $4}' | head -n 1 || true)"
  WIFI_GATEWAY="$(ip route show default 0.0.0.0/0 | awk -v d="$WIFI_IFACE" '$0 ~ " dev " d {print $3 " dev " d; exit}' || true)"

  if command -v resolvectl >/dev/null 2>&1; then
    WIFI_DNS="$(resolvectl dns "$WIFI_IFACE" 2>/dev/null | sed 's/^.*: //' || true)"
  fi

  if [ -z "$WIFI_DNS" ]; then
    WIFI_DNS="$(grep -E '^nameserver ' /etc/resolv.conf 2>/dev/null | awk '{print $2}' | paste -sd ' ' - || true)"
  fi

  if [ -n "$WIFI_IPV4" ]; then
    pco_go "Wi-Fi IPv4 detected: $WIFI_IPV4"
  else
    pco_nogo "ERR-MOD-SSID-NO-IP-001" "No IPv4 address received on $WIFI_IFACE"
  fi
}

connectivity_tests() {
  pco_step "11" "Wi-Fi connectivity tests"

  if ping -I "$WIFI_IFACE" -c 2 -W 3 8.8.8.8 >/dev/null 2>&1; then
    PING_8888_RESULT="OK"
    pco_go "8.8.8.8 ----> OK"
  else
    PING_8888_RESULT="FAILED"
    pco_warn "8.8.8.8 ----> FAILED through $WIFI_IFACE"
  fi

  if ping -I "$WIFI_IFACE" -c 2 -W 4 google.com >/dev/null 2>&1; then
    PING_GOOGLE_RESULT="OK"
    pco_go "google.com ----> OK"
  else
    PING_GOOGLE_RESULT="FAILED"
    pco_warn "google.com ----> FAILED through $WIFI_IFACE; DNS or route may not be ready"
  fi
}

write_state() {
  {
    printf '%s\n' 'PINCABOS_WIFI_DETECTED="yes"'
    printf 'PINCABOS_WIFI_IFACE="%s"\n' "$WIFI_IFACE"
    printf 'PINCABOS_WIFI_MAC="%s"\n' "$WIFI_MAC"
    printf 'PINCABOS_WIFI_SSID="%s"\n' "$SELECTED_SSID"
    printf 'PINCABOS_WIFI_SECURITY="%s"\n' "$SELECTED_SECURITY"
    printf 'PINCABOS_WIFI_IPV4="%s"\n' "$WIFI_IPV4"
    printf 'PINCABOS_WIFI_GATEWAY="%s"\n' "$WIFI_GATEWAY"
    printf 'PINCABOS_WIFI_DNS="%s"\n' "$WIFI_DNS"
    printf 'PINCABOS_WIFI_PING_8888="%s"\n' "$PING_8888_RESULT"
    printf 'PINCABOS_WIFI_PING_GOOGLE="%s"\n' "$PING_GOOGLE_RESULT"
    printf 'PINCABOS_WIFI_LOG="%s"\n' "$LOG_FILE"
  } > "$STATE_DIR/network-ssid.env"

  chmod 600 "$STATE_DIR/network-ssid.env"
}

show_summary() {
  pco_step "12" "Final Wi-Fi summary"

  echo
  echo -e "${YELLOW}Wi-Fi card:        ${WIFI_IFACE}${NC}"
  echo -e "${YELLOW}MAC address:       ${WIFI_MAC}${NC}"
  echo -e "${YELLOW}SSID:              ${SELECTED_SSID}${NC}"
  echo -e "${YELLOW}Security:          ${SELECTED_SECURITY}${NC}"
  echo -e "${YELLOW}IPv4/subnet:       ${WIFI_IPV4:-none}${NC}"
  echo -e "${YELLOW}Gateway:           ${WIFI_GATEWAY:-none}${NC}"
  echo -e "${YELLOW}DNS:               ${WIFI_DNS:-none}${NC}"
  echo -e "${YELLOW}Ping 8.8.8.8:      8.8.8.8 ----> ${PING_8888_RESULT}${NC}"
  echo -e "${YELLOW}Ping google.com:   google.com ----> ${PING_GOOGLE_RESULT}${NC}"
  echo
  echo "State file:         $STATE_DIR/network-ssid.env"
  echo "Netplan file:       /etc/netplan/01-pincabos-wifi-dhcp4.yaml"
  echo "Log:                $LOG_FILE"
  echo

  echo -e "${GREEN}GO [√] PinCabOS Wi-Fi SSID module completed${NC}"
}

main() {
  pco_title
  require_root
  require_commands
  detect_wifi_interfaces
  prepare_wifi_radio
  scan_ssids
  select_ssid
  read_wifi_key
  backup_wifi_netplan
  write_wifi_netplan
  apply_wifi_netplan
  collect_wifi_result
  connectivity_tests
  write_state
  show_summary
}

main "$@"
