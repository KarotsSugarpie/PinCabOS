pco_section "VPINFE"

runtime="/home/pinball/vpinfe"
launcher="/opt/pincabos/tools/run-vpinfe-systemd.sh"

if [ -x "$runtime/vpinfe" ] && [ -d "$runtime/_internal" ]; then
  pco_go "VPinFE runtime" "exécutable + _internal présents"
else
  pco_fail "VPinFE runtime" "runtime incomplet dans $runtime"
fi

if [ -x "$launcher" ]; then
  pco_go "VPinFE launcher" "$launcher"
else
  pco_fail "VPinFE launcher" "absent ou non exécutable"
fi

old_dropin="/etc/systemd/system/pincabos-vpinfe.service.d/55-pincabos-screen-topology.conf"
if [ -e "$old_dropin" ]; then
  if pco_repairing; then
    rm -f "$old_dropin"
    systemctl daemon-reload
    pco_go "VPinFE drop-in" "ancien 55 supprimé"
  else
    pco_warn "VPinFE drop-in" "ancien 55 encore présent"
  fi
else
  pco_go "VPinFE drop-in" "aucun ancien 55"
fi

sanitizer="/usr/local/libexec/pincabos/pincabos-vpinfe-display-sanitize"
if pco_repairing && [ -x "$sanitizer" ]; then
  "$sanitizer" >/tmp/pincabos-vpinfe-sanitize.log 2>&1 || true
fi

if pco_service_exists pincabos-vpinfe.service; then
  if pco_repairing; then
    pco_enable_service pincabos-vpinfe.service || true
  fi

  if pco_service_active pincabos-vpinfe.service; then
    pco_go "VPinFE service" "actif"
  else
    pco_fail "VPinFE service" "état : $(pco_unit_state pincabos-vpinfe.service)"
  fi
else
  pco_fail "VPinFE service" "unité absente"
fi

# PINCABOS_DOCTOR_VPINFE_PORT_8001_V1
if ss -lnt 2>/dev/null | awk '{print $4}' | grep -Eq '(:|\])8001$'; then
  pco_go "VPinFE port" "8001 en écoute"
else
  pco_warn "VPinFE port" "8001 non détecté"
fi
