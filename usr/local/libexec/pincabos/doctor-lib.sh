#!/usr/bin/env bash

: "${PCO_MODE:=repair}"
: "${PCO_FIRSTBOOT:=0}"
: "${PCO_SERVICE_RESTART:=1}"
: "${PCO_STATE_TSV:=/run/pincabos-doctor-state.tsv}"

PCO_GO=0
PCO_WARN=0
PCO_FAIL=0

pco_record() {
  local key="$1"
  local status="$2"
  shift 2
  local detail="$*"

  detail="${detail//$'\t'/ }"
  detail="${detail//$'\n'/ }"

  printf '%s\t%s\t%s\n' "$key" "$status" "$detail" >> "$PCO_STATE_TSV"

  case "$status" in
    GO)
      PCO_GO=$((PCO_GO + 1))
      printf '\033[32mGO [√]\033[0m %-26s %s\n' "$key" "$detail"
      ;;
    WARN)
      PCO_WARN=$((PCO_WARN + 1))
      printf '\033[33mWARN [!]\033[0m %-24s %s\n' "$key" "$detail"
      ;;
    NOGO)
      PCO_FAIL=$((PCO_FAIL + 1))
      printf '\033[31mNOGO [***]\033[0m %-21s %s\n' "$key" "$detail"
      ;;
  esac
}

pco_go()   { pco_record "$1" GO "${*:2}"; }
pco_warn() { pco_record "$1" WARN "${*:2}"; }
pco_fail() { pco_record "$1" NOGO "${*:2}"; }

pco_repairing() {
  [ "$PCO_MODE" = "repair" ]
}

pco_service_exists() {
  systemctl cat "$1" >/dev/null 2>&1
}

pco_service_active() {
  systemctl is-active --quiet "$1"
}

pco_enable_service() {
  local unit="$1"
  systemctl unmask "$unit" >/dev/null 2>&1 || true
  systemctl enable "$unit" >/dev/null 2>&1 || true

  if [ "$PCO_SERVICE_RESTART" -eq 1 ]; then
    systemctl restart "$unit"
  else
    systemctl start "$unit"
  fi
}

pco_as_pinball() {
  if command -v runuser >/dev/null 2>&1; then
    runuser -u pinball -- "$@"
  else
    sudo -u pinball -- "$@"
  fi
}

pco_has_cmd() {
  command -v "$1" >/dev/null 2>&1
}

pco_unit_state() {
  systemctl is-active "$1" 2>/dev/null || true
}

pco_section() {
  echo
  echo "---------------------------------------------------------------"
  echo " $*"
  echo "---------------------------------------------------------------"
}
