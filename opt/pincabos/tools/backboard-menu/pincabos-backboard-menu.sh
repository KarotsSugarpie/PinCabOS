#!/usr/bin/env bash
#
# pincabos-backboard-menu — logos animes par table sur le backboard HD au menu vpinfe
# (contenu communautaire aerao.net / PinUP Menu). AUTOMATIQUE : si un backboard HD est
# declare dans cabinet.xml, le contenu s'installe et se met a jour tout seul ; sans
# backboard, l'outil ne touche a rien.
#
# Principe : vpinfe envoie l'event du champ .info "FrontendDOFEvent" de la table survolee
# (hors plage E900-E990 qui est volontairement silencieuse). On remplit ce champ par
# matching de nom avec la base aerao, et on injecte le code Custom MX1 aerao (+ pinupmenu.gif)
# dans la config DOF de la matrice.
#
# Usage :
#   pincabos-backboard-menu.sh auto                     Mode automatique (ExecStartPre vpinfe) :
#                                                       mappe les nouvelles tables avant le menu,
#                                                       ou lance l'installation detachee la 1re fois.
#   pincabos-backboard-menu.sh install [version|auto]   Installe tout (assets + injection + mapping)
#   pincabos-backboard-menu.sh update  [version|auto]   Re-telecharge gif+base, re-applique
#   pincabos-backboard-menu.sh apply                    Re-applique apres un pull du config tool
#   pincabos-backboard-menu.sh map     [--dry] [--overwrite]   (Re)mappe FrontendDOFEvent des tables
#   pincabos-backboard-menu.sh disable                  Retire le contenu menu ET desactive l'auto
#   pincabos-backboard-menu.sh status                   Etat
#   (option globale : --force pour ignorer l'absence de backboard HD)
#
# Les mappings automatiques ne remplissent QUE les champs vides : une personnalisation
# manuelle de FrontendDOFEvent n'est jamais ecrasee ("map --overwrite" pour forcer).
#
set -euo pipefail
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE="$SELF_DIR/backboard-engine.py"

STATE_DIR="/home/pinball/.pincabos/backboard"
TABLES_DIR="/home/pinball/Tables"
AERAO="https://www.aerao.net/pinupmenugif"
SHEET_CSV="https://docs.google.com/spreadsheets/d/1PVf0FaC0g2aR5zbGekggJGZkZ1V4F_BX4cy-gSG823U/export?format=csv"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
SERVICE="pincabos-vpinfe.service"
DISABLED_FLAG="$STATE_DIR/disabled"
AUTOSETUP_FLAG="/run/pincabos-backboard-menu.autosetup"
# sentinelle du code injecte (alignee sur INJECT_MARK du moteur) ; l'ancien
# marqueur est encore reconnu pour ne pas reinjecter sur une install existante
INJECT_MARK="E1999 Black"
LEGACY_MARK="E2000 WHITE ABL0 ABT0 ABW232"

log(){ echo "[backboard-menu] $*"; }
die(){ echo "[backboard-menu] ERREUR: $*" >&2; exit 1; }

detect_cfgdir(){
  local d
  d=$(ls -d /home/pinball/.local/share/VPinballX/*/directoutputconfig 2>/dev/null | sort -V | tail -1)
  [ -n "$d" ] || die "dossier directoutputconfig introuvable (VPinballX non installe ?)"
  echo "$d"
}
matrix_ini(){ python3 "$ENGINE" matrix-ini "$1"; }

require_backboard(){ # $1=cfgdir ; sort proprement si pas de backboard HD (sauf --force)
  local cfgdir="$1" out
  out=$(python3 "$ENGINE" detect "$cfgdir" 2>&1) && { return 0; }
  if [ "${FORCE:-0}" = "1" ]; then log "backboard HD non detecte ($out) mais --force → on continue"; return 0; fi
  log "Pas de backboard HD sur cette install ($out)."
  log "TeensyStripController + LedStrip absents de cabinet.xml → outil sans effet ici. (--force pour passer outre)"
  exit 0
}

detect_version(){
  local v
  v=$(curl -s -L -A "$UA" "$AERAO/" 2>/dev/null | grep -oE "download\.php\?v=[0-9]+" | grep -oE "[0-9]+" | sort -n | tail -1)
  echo "${v:-55}"
}

fetch_assets(){ # $1=cfgdir  $2=version|auto
  local cfgdir="$1" ver="$2"
  [ "$ver" = "auto" ] && ver=$(detect_version)
  mkdir -p "$STATE_DIR"
  log "base aerao (CSV)..."
  curl -s -L -A "$UA" "$SHEET_CSV" -o "$STATE_DIR/aerao.csv" || die "telechargement CSV echoue"
  [ -s "$STATE_DIR/aerao.csv" ] || die "CSV vide"
  log "pinupmenu.gif (v.$ver)..."
  curl -s -L -A "$UA" -e "$AERAO/" "$AERAO/download.php?v=$ver" -o "$cfgdir/pinupmenu.gif" || die "telechargement gif echoue"
  head -c6 "$cfgdir/pinupmenu.gif" | grep -q "GIF8" || die "pinupmenu.gif invalide"
  echo "$ver" > "$STATE_DIR/version.txt"
  log "assets OK (gif $(wc -c <"$cfgdir/pinupmenu.gif") octets, v.$ver)"
}

build(){ python3 "$ENGINE" build-code "$STATE_DIR/aerao.csv" "$STATE_DIR/aerao_code.txt" "$STATE_DIR/aerao_map.json"; }
inject(){ python3 "$ENGINE" inject "$1" "$STATE_DIR/aerao_code.txt"; }
maptables(){ python3 "$ENGINE" map "$STATE_DIR/aerao_map.json" "$TABLES_DIR" "$@"; }

fix_owner(){ # les modes automatiques tournent en root : rendre l'etat a pinball
  chown -R pinball:pinball "$STATE_DIR" 2>/dev/null || true
  [ -n "${1:-}" ] && chown pinball:pinball "$1/pinupmenu.gif" 2>/dev/null || true
}

assets_ready(){ # $1=cfgdir
  [ -s "$STATE_DIR/aerao_code.txt" ] && [ -s "$STATE_DIR/aerao_map.json" ] && [ -s "$1/pinupmenu.gif" ]
}

restart(){ sudo systemctl restart "$SERVICE"; log "vpinfe redemarre"; }

cmd_install(){
  local ver="${1:-auto}" cfgdir ini
  cfgdir=$(detect_cfgdir); require_backboard "$cfgdir"; ini=$(matrix_ini "$cfgdir")
  log "cfgdir=$cfgdir"; log "matrix ini=$ini"
  rm -f "$DISABLED_FLAG"
  fetch_assets "$cfgdir" "$ver"
  build; inject "$ini"; maptables --fill-only; fix_owner "$cfgdir"; restart
  log "INSTALL termine. (status: $0 status)"
}
cmd_update(){
  local ver="${1:-auto}" cfgdir ini
  cfgdir=$(detect_cfgdir); require_backboard "$cfgdir"; ini=$(matrix_ini "$cfgdir")
  rm -f "$DISABLED_FLAG"
  fetch_assets "$cfgdir" "$ver"; build; inject "$ini"; maptables --fill-only; fix_owner "$cfgdir"; restart
  log "UPDATE termine."
}
cmd_apply(){
  local cfgdir ini
  cfgdir=$(detect_cfgdir); require_backboard "$cfgdir"; ini=$(matrix_ini "$cfgdir")
  [ -f "$DISABLED_FLAG" ] && { log "desactive (flag $DISABLED_FLAG) — rien a appliquer"; exit 0; }
  [ -f "$STATE_DIR/aerao_code.txt" ] || die "pas d'assets — lance 'install' d'abord"
  inject "$ini"; maptables --fill-only; fix_owner "$cfgdir"; restart
  log "APPLY termine."
}
cmd_map(){ local cfgdir; cfgdir=$(detect_cfgdir); require_backboard "$cfgdir"; [ -f "$STATE_DIR/aerao_map.json" ] || build
  local flags=(--fill-only)
  for a in "$@"; do
    [ "$a" = "--overwrite" ] && flags=() && continue
    flags+=("$a")
  done
  maptables ${flags[@]+"${flags[@]}"}
}
cmd_disable(){
  local cfgdir ini; cfgdir=$(detect_cfgdir); ini=$(matrix_ini "$cfgdir")
  python3 "$ENGINE" uninject "$ini"
  [ -f "$STATE_DIR/aerao_map.json" ] && python3 "$ENGINE" unmap "$STATE_DIR/aerao_map.json" "$TABLES_DIR" || true
  mkdir -p "$STATE_DIR"; touch "$DISABLED_FLAG"; fix_owner "$cfgdir"
  restart
  log "DISABLE termine (contenu menu retire, mode auto desactive ; 'install' pour reactiver)."
}
cmd_status(){
  local cfgdir ini; cfgdir=$(detect_cfgdir); ini=$(matrix_ini "$cfgdir")
  [ -f "$DISABLED_FLAG" ] && echo "mode auto      : DESACTIVE ($DISABLED_FLAG)" || echo "mode auto      : actif"
  python3 "$ENGINE" status "$ini" "$STATE_DIR/aerao_map.json" "$TABLES_DIR"
}

# PINCABOS_BACKBOARD_MENU_AUTO_V1
# Mode automatique (ExecStartPre de pincabos-vpinfe.service) : ne doit JAMAIS
# bloquer ni faire echouer le demarrage du frontend, et ne JAMAIS redemarrer
# vpinfe depuis son propre ExecStartPre (le restart n'a lieu que dans le setup
# detache de premiere installation).
cmd_auto(){
  [ -f "$DISABLED_FLAG" ] && exit 0
  local cfgdir ini
  cfgdir=$(ls -d /home/pinball/.local/share/VPinballX/*/directoutputconfig 2>/dev/null | sort -V | tail -1) || true
  [ -n "${cfgdir:-}" ] || exit 0
  python3 "$ENGINE" detect "$cfgdir" >/dev/null 2>&1 || exit 0

  if assets_ready "$cfgdir"; then
    # regime de croisiere : injection si perdue (pull config tool hors web) et
    # mapping des tables nouvellement installees, avant que vpinfe lise les .info
    ini=$(matrix_ini "$cfgdir" 2>/dev/null) || exit 0
    [ -n "$ini" ] && [ -f "$ini" ] || exit 0
    grep -qF "$INJECT_MARK" "$ini" 2>/dev/null || grep -qF "$LEGACY_MARK" "$ini" 2>/dev/null || inject "$ini" || true
    maptables --fill-only >/dev/null 2>&1 || true
    fix_owner "$cfgdir"
    exit 0
  fi

  # premiere fois (backboard present, rien d'installe) : setup complet detache
  # (telechargements aerao + injection + mapping + restart vpinfe a la fin).
  # Une seule tentative par boot.
  [ -e "$AUTOSETUP_FLAG" ] && exit 0
  touch "$AUTOSETUP_FLAG" 2>/dev/null || true
  command -v systemd-run >/dev/null 2>&1 || exit 0
  log "backboard HD detecte, contenu menu absent → installation automatique detachee"
  systemd-run --unit="pincabos-backboard-menu-setup-$$" --collect --no-block \
    "$SELF_DIR/pincabos-backboard-menu.sh" install auto >/dev/null 2>&1 || true
  exit 0
}

FORCE=0; _args=()
for _a in "$@"; do if [ "$_a" = "--force" ]; then FORCE=1; else _args+=("$_a"); fi; done
set -- ${_args[@]+"${_args[@]}"}

case "${1:-}" in
  auto)    shift; cmd_auto "$@";;
  install) shift; cmd_install "$@";;
  update)  shift; cmd_update "$@";;
  apply)   shift; cmd_apply "$@";;
  map)     shift; cmd_map "$@";;
  disable) shift; cmd_disable;;
  status)  shift; cmd_status "$@";;
  *) grep -E "^#( |$)" "$0" | sed "s/^# \{0,1\}//"; exit 1;;
esac
