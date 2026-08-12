pco_section "SYSTÈME"

if [ -r /etc/os-release ]; then
  . /etc/os-release
  pco_go "OS" "${PRETTY_NAME:-Linux} — kernel $(uname -r)"
else
  pco_warn "OS" "Impossible de lire /etc/os-release"
fi

if id pinball >/dev/null 2>&1; then
  pco_go "Utilisateur" "pinball présent"
else
  pco_fail "Utilisateur" "pinball absent"
fi

if id pinball >/dev/null 2>&1; then
  missing_groups=()
  for group in video render audio input dialout plugdev; do
    getent group "$group" >/dev/null 2>&1 || continue
    id -nG pinball | tr ' ' '\n' | grep -qx "$group" || missing_groups+=("$group")
  done

  if [ "${#missing_groups[@]}" -eq 0 ]; then
    pco_go "Groupes matériels" "video/render/audio/input/dialout disponibles"
  elif pco_repairing; then
    usermod -aG "$(IFS=,; echo "${missing_groups[*]}")" pinball
    pco_go "Groupes matériels" "ajoutés : ${missing_groups[*]}"
  else
    pco_warn "Groupes matériels" "manquants : ${missing_groups[*]}"
  fi
fi

for dir in /opt/pincabos /var/log/pincabos /var/lib/pincabos /home/pinball/Tables; do
  if [ -d "$dir" ]; then
    pco_go "Dossier $(basename "$dir")" "$dir"
  elif pco_repairing && [ "$dir" = "/home/pinball/Tables" ]; then
    install -d -o pinball -g pinball -m 0755 "$dir"
    pco_go "Dossier Tables" "créé : $dir"
  else
    pco_fail "Dossier $(basename "$dir")" "absent : $dir"
  fi
done

available_kib="$(df -Pk / | awk 'NR==2 {print $4}')"
if [ "${available_kib:-0}" -ge 10485760 ]; then
  pco_go "Espace disque" "$(df -h / | awk 'NR==2 {print $4 " libres"}')"
else
  pco_warn "Espace disque" "moins de 10 Gio libres"
fi

failed_units="$(systemctl --failed --no-legend 2>/dev/null | awk '{print $1}' | grep -v '^pincabos-finalize-firstboot.service$' || true)"
if [ -z "$failed_units" ]; then
  pco_go "Systemd failed" "aucune unité échouée"
else
  pco_warn "Systemd failed" "$(echo "$failed_units" | tr '\n' ' ')"
fi
