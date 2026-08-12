#!/usr/bin/env bash
# PinCabOS-File created by Karots Sugarpie
set -Eeuo pipefail

MODE="${1:-status}"

LOG_DIR="/opt/pincabos/logs"
CONFIG_DIR="/opt/pincabos/config"

ISO_FLAG="${CONFIG_DIR}/iso-firstboot-safe.flag"
ISO_DONE="${CONFIG_DIR}/iso-firstboot-safe.done"
FRONTEND_HOLD="${CONFIG_DIR}/frontend-hold-firstboot.flag"
MODE_FILE="${CONFIG_DIR}/pincabos-admin-mode.json"

mkdir -p "$LOG_DIR" "$CONFIG_DIR"

echo "=== PinCabOS Admin ISO/Game Mode ==="
date
echo "Mode demandé: $MODE"
echo

show_status() {
  echo "=== État actuel ==="

  if [ -f "$ISO_FLAG" ]; then
    echo "ISO_FLAG: présent -> $ISO_FLAG"
  else
    echo "ISO_FLAG: absent"
  fi

  if [ -f "$ISO_DONE" ]; then
    echo "ISO_DONE: présent -> $ISO_DONE"
  else
    echo "ISO_DONE: absent"
  fi

  if [ -f "$FRONTEND_HOLD" ]; then
    echo "FRONTEND_HOLD: présent -> ATTENTION frontend bloqué"
  else
    echo "FRONTEND_HOLD: absent"
  fi

  echo
  echo "--- Service firstboot safe ---"
  systemctl is-enabled pincabos-iso-firstboot-safe.service 2>/dev/null || true

  echo
  echo "--- Services cab ---"
  systemctl is-active pincabos-web.service 2>/dev/null || true
  systemctl is-active pincabos-vpinfe.service 2>/dev/null || true

  echo
  echo "--- Fichier mode ---"
  if [ -f "$MODE_FILE" ]; then
    cat "$MODE_FILE"
  else
    echo "Aucun fichier mode."
  fi
}

case "$MODE" in
  iso|iso-mode|mode-iso)
    echo "=== Passage en Mode ISO ARMÉ ==="
    echo
    echo "Ce mode prépare le cab pour génération ISO."
    echo "IMPORTANT: il n'exécute PAS le safe-mode sur le cab live."
    echo

    touch "$ISO_FLAG"
    rm -f "$ISO_DONE"

    # Très important : ne pas bloquer le frontend du cab live.
    rm -f "$FRONTEND_HOLD"

    # Très important : le service reste désactivé sur le cab live.
    systemctl disable pincabos-iso-firstboot-safe.service 2>/dev/null || true

    python3 - <<PY
import json, datetime
from pathlib import Path

p = Path("$MODE_FILE")
data = {
    "mode": "iso",
    "description": "Cab armé pour génération ISO. Le flag iso-firstboot-safe sera copié dans l'image ISO.",
    "armed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "iso_flag": "$ISO_FLAG",
    "live_safe_service_enabled": False,
    "frontend_hold_live": False
}
p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\\n", encoding="utf-8")
print("Mode file écrit:", p)
PY

    echo
    echo "Mode ISO armé."
    echo "Le prochain ISO copiera:"
    echo "  $ISO_FLAG"
    echo
    show_status
    ;;

  game|game-mode|mode-jeux|jeux)
    echo "=== Passage en Mode Jeux NORMAL ==="
    echo

    rm -f "$ISO_FLAG"
    rm -f "$FRONTEND_HOLD"
    touch "$ISO_DONE"

    systemctl disable pincabos-iso-firstboot-safe.service 2>/dev/null || true

    python3 - <<PY
import json, datetime
from pathlib import Path

p = Path("$MODE_FILE")
data = {
    "mode": "game",
    "description": "Cab normal / mode jeux. Aucun flag ISO actif.",
    "set_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "iso_flag": False,
    "frontend_hold_live": False
}
p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\\n", encoding="utf-8")
print("Mode file écrit:", p)
PY

    systemctl enable pincabos-vpinfe.service 2>/dev/null || true
    systemctl restart pincabos-web.service 2>/dev/null || true
    systemctl restart pincabos-vpinfe.service 2>/dev/null || true

    echo
    echo "Mode Jeux actif."
    echo
    show_status
    ;;

  status)
    show_status
    ;;

  *)
    echo "Usage: $0 iso|game|status"
    exit 2
    ;;
esac
