#!/usr/bin/env bash
set -Eeuo pipefail

ENGINE="/opt/pincabos/scripts/pincabos-screen-topology.py"
ALIASES="/opt/pincabos/config/display-aliases.env"
LOCK="/run/pincabos-screen-topology.lock"

log() {
  echo "pincabos-screen-topology-preflight: $*" >&2
}

# PINCABOS_DEMARRAGE_V1 : X est pret en general au premier ou deuxieme tick ;
# une attente par pas d'une seconde coutait jusqu'a 1 s pour rien.
for TICK in $(seq 1 360); do
  SECOND=$(( (TICK + 3) / 4 ))
  XRANDR="$(
    /usr/sbin/runuser -u pinball -- \
      /usr/bin/env \
        DISPLAY=:0 \
        XAUTHORITY=/home/pinball/.Xauthority \
        /usr/bin/xrandr --query 2>/dev/null || true
  )"

  if grep -Eq '^[^[:space:]]+ connected( primary)? [0-9]+x[0-9]+' <<<"$XRANDR"; then
    log "X11 prêt après ${SECOND}s (tick ${TICK}) : préparation des rôles."

    /usr/bin/flock -w 15 "$LOCK" "$ENGINE" --prepare

    if grep -q "^PINCABOS_PLAYFIELD_AVAILABLE='1'$" "$ALIASES" 2>/dev/null; then
      log "topologie valide, VPinFE peut démarrer."
      exit 0
    fi

    log "X11 présent, mais aucun Playfield résolu."
  fi

  sleep 0.25
done

log "X11/topologie indisponible après 90 secondes."
exit 1
