pco_section "AUDIO"

if pco_has_cmd aplay; then
  card_count="$(aplay -l 2>/dev/null | grep -c '^card ' || true)"
  if [ "${card_count:-0}" -gt 0 ]; then
    pco_go "ALSA" "$card_count périphérique(s) PCM"
  else
    pco_warn "ALSA" "aucun périphérique de lecture"
  fi
else
  pco_warn "ALSA" "aplay absent"
fi

if pco_has_cmd pactl; then
  sinks="$(pco_as_pinball env XDG_RUNTIME_DIR=/run/user/"$(id -u pinball)" pactl list short sinks 2>/dev/null | wc -l || true)"
  if [ "${sinks:-0}" -gt 0 ]; then
    pco_go "Pulse/PipeWire" "$sinks sortie(s)"
  else
    pco_warn "Pulse/PipeWire" "aucune sortie visible pour pinball"
  fi
fi
