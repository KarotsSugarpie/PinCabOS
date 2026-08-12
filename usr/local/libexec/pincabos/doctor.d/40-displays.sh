pco_section "ÉCRANS / TOPOLOGIE"

TOPOLOGY_SERVICE="pincabos-screen-topology-boot.service"
SCREENS_JSON="/opt/pincabos/config/screens/screens.json"

if pco_service_exists "$TOPOLOGY_SERVICE"; then
  if pco_repairing; then
    systemctl restart "$TOPOLOGY_SERVICE" || true
  fi

  if pco_service_active "$TOPOLOGY_SERVICE"; then
    pco_go "Topologie service" "actif"
  else
    state="$(pco_unit_state "$TOPOLOGY_SERVICE")"
    pco_warn "Topologie service" "état : ${state:-inconnu}"
  fi
else
  pco_fail "Topologie service" "$TOPOLOGY_SERVICE absent"
fi

if [ -s "$SCREENS_JSON" ]; then
  roles="$(python3 - "$SCREENS_JSON" <<'PY' 2>/dev/null || true
import json, sys
p=sys.argv[1]
d=json.load(open(p, encoding='utf-8'))
items=[]
for key in ('playfield','backglass','fulldmd','dmd'):
    v=d.get(key)
    if isinstance(v, dict):
        name=v.get('output') or v.get('name') or v.get('connector')
        if name:
            items.append(f"{key}={name}")
print(' '.join(items))
PY
)"
  pco_go "screens.json" "${roles:-présent et lisible}"
else
  pco_warn "screens.json" "absent ou vide : $SCREENS_JSON"
fi

if pco_has_cmd xrandr; then
  connected="$(pco_as_pinball env DISPLAY=:0 XAUTHORITY=/home/pinball/.Xauthority xrandr --query 2>/dev/null | grep ' connected' | wc -l || true)"
  if [ "${connected:-0}" -gt 0 ]; then
    pco_go "Écrans X11" "$connected écran(s) connecté(s)"
  else
    pco_warn "Écrans X11" "xrandr n’a détecté aucun écran sur :0"
  fi
fi
