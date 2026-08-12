#!/usr/bin/env bash
# PinCabOs-File created by Karots Sugarpie
set -u

TABLE_DIR="${1:-}"
PINMAME_ROOT="/opt/pincabos/apps/vpinball/PinMAME"
LOG_DIR="/opt/pincabos/logs"
LOG_FILE="$LOG_DIR/pinmame-table-overlay.log"

mkdir -p "$LOG_DIR"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

safe_link_file() {
  local src="$1"
  local dest_dir="$2"
  local dest="$dest_dir/$(basename "$src")"

  mkdir -p "$dest_dir"

  if [ -e "$dest" ] && [ ! -L "$dest" ]; then
    log "SKIP REAL FILE: $dest existe déjà, pas d'écrasement"
    return 0
  fi

  ln -sfn "$src" "$dest"
  log "LINK FILE: $dest -> $src"
}

safe_link_dir() {
  local src="$1"
  local dest_dir="$2"
  local dest="$dest_dir/$(basename "$src")"

  mkdir -p "$dest_dir"

  if [ -e "$dest" ] && [ ! -L "$dest" ]; then
    log "SKIP REAL DIR: $dest existe déjà, pas d'écrasement"
    return 0
  fi

  ln -sfn "$src" "$dest"
  log "LINK DIR: $dest -> $src"
}

if [ -z "$TABLE_DIR" ]; then
  log "INFO: aucun dossier table reçu"
  exit 0
fi

if [ ! -d "$TABLE_DIR" ]; then
  log "INFO: dossier table absent: $TABLE_DIR"
  exit 0
fi

TABLE_PINMAME="$TABLE_DIR/pinmame"

mkdir -p \
  "$PINMAME_ROOT/roms" \
  "$PINMAME_ROOT/altcolor" \
  "$PINMAME_ROOT/altsound" \
  "$PINMAME_ROOT/cfg" \
  "$PINMAME_ROOT/nvram" \
  "$PINMAME_ROOT/memcard" \
  "$PINMAME_ROOT/snap"

log "────────────────────────────────────────────────────────────────"
log "Overlay table: $TABLE_DIR"

if [ ! -d "$TABLE_PINMAME" ]; then
  log "INFO: aucun dossier table/pinmame: $TABLE_PINMAME"
  exit 0
fi

if [ -d "$TABLE_PINMAME/roms" ]; then
  find "$TABLE_PINMAME/roms" -maxdepth 1 -type f -iname "*.zip" -print0 | while IFS= read -r -d '' f; do
    safe_link_file "$f" "$PINMAME_ROOT/roms"
  done
fi

if [ -d "$TABLE_PINMAME/altcolor" ]; then
  find "$TABLE_PINMAME/altcolor" -mindepth 1 -maxdepth 1 \( -type d -o -type l \) -print0 | while IFS= read -r -d '' d; do
    safe_link_dir "$d" "$PINMAME_ROOT/altcolor"
  done
fi

if [ -d "$TABLE_PINMAME/altsound" ]; then
  find "$TABLE_PINMAME/altsound" -mindepth 1 -maxdepth 1 \( -type d -o -type l \) -print0 | while IFS= read -r -d '' d; do
    safe_link_dir "$d" "$PINMAME_ROOT/altsound"
  done
fi

chown -h pinball:pinball "$PINMAME_ROOT"/roms/* "$PINMAME_ROOT"/altcolor/* "$PINMAME_ROOT"/altsound/* 2>/dev/null || true
chown pinball:pinball "$LOG_FILE" 2>/dev/null || true

log "Overlay terminé"
exit 0
