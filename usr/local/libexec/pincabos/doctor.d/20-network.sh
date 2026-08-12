pco_section "RÉSEAU"

if ip route show default | grep -q '^default '; then
  pco_go "Route réseau" "$(ip route show default | head -1)"
else
  pco_fail "Route réseau" "aucune route par défaut"
fi

if pco_service_exists NetworkManager.service; then
  if pco_service_active NetworkManager.service; then
    pco_go "NetworkManager" "actif"
  elif pco_repairing; then
    systemctl enable --now NetworkManager.service
    pco_go "NetworkManager" "activé"
  else
    pco_warn "NetworkManager" "installé mais inactif"
  fi
else
  pco_warn "NetworkManager" "service absent"
fi

if getent ahosts localhost >/dev/null 2>&1; then
  pco_go "Résolution locale" "fonctionnelle"
else
  pco_warn "Résolution locale" "échec getent"
fi

primary_ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
if [ -n "$primary_ip" ]; then
  pco_go "Adresse IP" "$primary_ip"
else
  pco_warn "Adresse IP" "aucune adresse détectée"
fi
