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

# PINCABOS_DOCTOR_MENAGEMENT_V1 (Yann, cab 06/09/2026) : le doctor ne coupe jamais une
# partie ni un frontend sain. Le finaliseur de premier demarrage tournait 45 s apres le
# boot en mode reparation : la topologie (Requires de VPinFE) etait redemarree et VPinFE
# relance -> VPX tue en pleine table de calibration (ecran noir).
pco_partie_en_cours() {
  pgrep -x VPinballX_BGFX >/dev/null 2>&1 || pgrep -f '/VPinballX' >/dev/null 2>&1
}

pco_peut_redemarrer() {
  # un service ACTIF n'est redemarre que si le mode le demande, hors partie, hors premier demarrage
  [ "$PCO_SERVICE_RESTART" -eq 1 ] && [ "$PCO_FIRSTBOOT" -ne 1 ] && ! pco_partie_en_cours
}

pco_enable_service() {
  local unit="$1"
  systemctl unmask "$unit" >/dev/null 2>&1 || true
  systemctl enable "$unit" >/dev/null 2>&1 || true

  if systemctl is-active --quiet "$unit"; then
    if pco_peut_redemarrer; then
      systemctl restart "$unit"
    fi
    return 0
  fi
  if pco_partie_en_cours; then
    echo "  $unit inactif : partie en cours, aucun demarrage pendant le jeu"
    return 0
  fi
  systemctl start "$unit"
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
