#!/usr/bin/env bash
set -Eeuo pipefail

TABLE_ROOT="/home/pinball/Tables"
APPLY=0

usage() {
  cat <<EOF
Usage:
  restore-old-medias.sh --dry-run
  restore-old-medias.sh --apply

Action:
  medias/bg.png actuel      -> medias/bg.old.png
  medias/bg.png.old ancien  -> medias/bg.png

  medias/dmd.png actuel      -> medias/dmd.old.png
  medias/dmd.png.old ancien  -> medias/dmd.png
EOF
}

case "${1:-}" in
  --dry-run) APPLY=0 ;;
  --apply) APPLY=1 ;;
  -h|--help|"") usage; exit 0 ;;
  *) echo "Option inconnue: $1"; usage; exit 1 ;;
esac

backup_current_png() {
  local dir="$1"
  local base="$2"
  local current="$dir/$base.png"
  local backup="$dir/$base.old.png"

  if [ ! -f "$current" ]; then
    return 0
  fi

  if [ -f "$backup" ]; then
    local stamp
    stamp="$(date +%Y%m%d-%H%M%S)"
    backup="$dir/$base.old-$stamp.png"
  fi

  echo "BACKUP: $current -> $backup"
  if [ "$APPLY" = "1" ]; then
    mv -f "$current" "$backup"
  fi
}

find_old_source() {
  local dir="$1"
  local base="$2"

  for candidate in \
    "$dir/$base.png.old" \
    "$dir/$base.old" \
    "$dir/$base.old.png"
  do
    if [ -f "$candidate" ]; then
      echo "$candidate"
      return 0
    fi
  done

  # Si plusieurs anciens avec timestamp existent, prendre le plus récent.
  find "$dir" -maxdepth 1 -type f \( \
    -name "$base.png.old-*" -o \
    -name "$base.old-*.png" \
  \) -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n 1 | cut -d' ' -f2-
}

restore_one() {
  local dir="$1"
  local base="$2"
  local old_src
  local dest="$dir/$base.png"

  old_src="$(find_old_source "$dir" "$base" || true)"

  if [ -z "$old_src" ] || [ ! -f "$old_src" ]; then
    return 0
  fi

  echo
  echo "---------------------------------------------------------------"
  echo "TABLE : $(basename "$(dirname "$dir")")"
  echo "MEDIA : $dir"
  echo "TYPE  : $base"
  echo "OLD   : $old_src"
  echo "DEST  : $dest"

  backup_current_png "$dir" "$base"

  echo "RESTORE: $old_src -> $dest"
  if [ "$APPLY" = "1" ]; then
    mv -f "$old_src" "$dest"
    chown pinball:pinball "$dest" 2>/dev/null || true
    chmod u+rw,g+r "$dest" 2>/dev/null || true
  fi
}

echo "Racine tables : $TABLE_ROOT"
echo "Mode          : $([ "$APPLY" = "1" ] && echo "APPLY / MODIFICATION" || echo "DRY-RUN / AUCUNE MODIFICATION")"

COUNT=0

while IFS= read -r -d '' MEDIAS; do
  restore_one "$MEDIAS" "bg"
  restore_one "$MEDIAS" "dmd"
  COUNT=$((COUNT + 1))
done < <(find "$TABLE_ROOT" -mindepth 2 -maxdepth 2 -type d -name "medias" -print0 2>/dev/null)

echo
echo "==============================================================="
echo " TERMINÉ"
echo "Dossiers medias vérifiés : $COUNT"
echo "Mode : $([ "$APPLY" = "1" ] && echo "MODIFIÉ" || echo "DRY-RUN")"
echo "==============================================================="
