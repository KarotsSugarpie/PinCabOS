pco_section "PRÊT À IMPORTER ET JOUER"

TABLES="/home/pinball/Tables"
if [ -d "$TABLES" ]; then
  testfile="$TABLES/.pincabos-doctor-write-test-$$"
  if pco_as_pinball sh -c "umask 022; : > '$testfile'; rm -f '$testfile'"; then
    pco_go "Import de tables" "$TABLES est inscriptible par pinball"
  else
    pco_fail "Import de tables" "$TABLES non inscriptible"
  fi
else
  pco_fail "Import de tables" "$TABLES absent"
fi

cycle_lines="$(journalctl -b --no-pager 2>/dev/null | grep -Ei 'ordering cycle|dependency cycle' | tail -n 10 || true)"
if [ -z "$cycle_lines" ]; then
  pco_go "Cycles systemd" "aucun cycle détecté ce boot"
else
  pco_warn "Cycles systemd" "messages de cycle présents dans le journal"
fi

required_services=(
  pincabos-webapp.service
  pincabos-screen-topology-boot.service
  pincabos-vpinfe.service
)

inactive=()
for unit in "${required_services[@]}"; do
  pco_service_exists "$unit" || continue
  pco_service_active "$unit" || inactive+=("$unit")
done

if [ "${#inactive[@]}" -eq 0 ]; then
  pco_go "Services essentiels" "WebApp, topologie et VPinFE actifs"
else
  pco_fail "Services essentiels" "inactifs : ${inactive[*]}"
fi
