# PINCABOS_SCRIPT_PATH_V1
# Ajoute les scripts PinCabOS au PATH pour les shells login.

case ":$PATH:" in
  *:/opt/pincabos/script:*) ;;
  *) export PATH="/opt/pincabos/script:$PATH" ;;
esac
