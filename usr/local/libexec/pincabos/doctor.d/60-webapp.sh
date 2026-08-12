pco_section "WEBAPP"

if [ -f /opt/pincabos/web/app.py ]; then
  pco_go "WebApp source" "/opt/pincabos/web/app.py"
else
  pco_fail "WebApp source" "app.py absent"
fi

web_python=""
for candidate in \
  /opt/pincabos/web/.venv/bin/python \
  /opt/pincabos/web/venv/bin/python \
  /usr/bin/python3
 do
  if [ -x "$candidate" ]; then
    web_python="$candidate"
    break
  fi
done

if [ -n "$web_python" ]; then
  if "$web_python" -c 'import flask' >/dev/null 2>&1; then
    pco_go "Python WebApp" "$web_python + Flask"
  else
    pco_warn "Python WebApp" "$web_python sans Flask importable"
  fi
else
  pco_fail "Python WebApp" "aucun interpréteur trouvé"
fi

if pco_service_exists pincabos-webapp.service; then
  if pco_service_active pincabos-webapp.service; then
    pco_go "WebApp service" "actif"
  elif pco_repairing; then
    pco_enable_service pincabos-webapp.service || true
    if pco_service_active pincabos-webapp.service; then
      pco_go "WebApp service" "activé et démarré"
    else
      pco_fail "WebApp service" "échec du démarrage"
    fi
  else
    pco_warn "WebApp service" "inactif"
  fi
else
  pco_fail "WebApp service" "unité absente"
fi

if pco_has_cmd curl && curl -fsS --max-time 5 http://127.0.0.1/ >/dev/null 2>&1; then
  pco_go "WebApp HTTP" "http://127.0.0.1 répond"
else
  pco_warn "WebApp HTTP" "port 80 sans réponse valide"
fi
