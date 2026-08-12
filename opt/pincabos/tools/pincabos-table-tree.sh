#!/usr/bin/env bash
set -Eeuo pipefail

TABLES_ROOT="/home/pinball/Tables"
STAMP="$(date +%Y%m%d-%H%M%S)"
LOCK="/tmp/pincabos-table-tree.lock"
MODE="audit"
QUIET=0

for arg in "$@"; do
  case "$arg" in
    --apply) MODE="apply" ;;
    --audit) MODE="audit" ;;
    --quiet) QUIET=1 ;;
  esac
done

mkdir -p "$TABLES_ROOT" /opt/pincabos/logs
exec 9>"$LOCK"
flock -x 9

# Politique PinCabOS demandée :
# - altsound et altcolor sont sous pinmame
# - Serum, PAL et VNI sont tous classés sous pinmame/altcolor
# - pupvideos demeure à la racine du dossier de table
ROOT_DIRS=(
  cache
  extras
  logs
  medias
  music
  pupvideos
  scripts
  user
)

PINMAME_DIRS=(
  roms
  nvram
  cfg
  ini
  memmaps
  altsound
  altcolor
)

find_ci_dir() {
  local parent="$1" name="$2"
  [[ -d "$parent" ]] || return 0
  find "$parent" -mindepth 1 -maxdepth 1 -type d -iname "$name" -print -quit 2>/dev/null || true
}

resolve_ci_rel_dir() {
  local table="$1" rel="$2"
  local parent_rel leaf parent exact found

  parent_rel="$(dirname "$rel")"
  leaf="$(basename "$rel")"

  if [[ "$parent_rel" == . ]]; then
    parent="$table"
  else
    parent="$table/$parent_rel"
  fi

  exact="$parent/$leaf"
  if [[ -d "$exact" ]]; then
    printf '%s\n' "$exact"
    return 0
  fi

  found="$(find_ci_dir "$parent" "$leaf")"
  [[ -n "$found" ]] && printf '%s\n' "$found"
}

ensure_dir() {
  local dir="$1"

  if [[ -d "$dir" ]]; then
    return 0
  fi

  if [[ -e "$dir" || -L "$dir" ]]; then
    echo "NOGO [X] Chemin non répertoire : $dir"
    return 1
  fi

  if [[ "$MODE" == apply ]]; then
    mkdir -p "$dir"
    chown pinball:pinball "$dir" 2>/dev/null || true
    chmod 0775 "$dir" 2>/dev/null || true
  fi

  [[ "$QUIET" -eq 1 ]] || echo "CREATE [=] $dir"
}

normalize_case_dir() {
  local parent="$1" wanted="$2" exact found
  exact="$parent/$wanted"

  [[ -d "$exact" ]] && return 0
  found="$(find_ci_dir "$parent" "$wanted")"

  if [[ -n "$found" && "$found" != "$exact" && "$MODE" == apply ]]; then
    mv "$found" "$exact"
    chown pinball:pinball "$exact" 2>/dev/null || true
    [[ "$QUIET" -eq 1 ]] || echo "CASE [√] $found -> $exact"
  fi

  ensure_dir "$exact"
}

safe_migrate_dir() {
  local table="$1" source_rel="$2" dest_rel="$3"
  local source destination journal conflict leftover rel target conflict_target n

  source="$(resolve_ci_rel_dir "$table" "$source_rel")"
  [[ -n "$source" && -d "$source" ]] || return 0

  destination="$table/$dest_rel"

  if [[ "$(readlink -f "$source")" == "$(readlink -f "$destination" 2>/dev/null || printf '%s' "$destination")" ]]; then
    return 0
  fi

  journal="$table/extras/legacy-layout-backup/$STAMP/migrations.log"
  conflict="$table/extras/legacy-layout-conflicts/$STAMP/$source_rel"
  leftover="$table/extras/legacy-layout-backup/$STAMP/leftovers/$source_rel"

  if [[ "$MODE" != apply ]]; then
    [[ "$QUIET" -eq 1 ]] || echo "LEGACY [!] $source -> $destination"
    return 0
  fi

  mkdir -p "$destination" "$(dirname "$journal")"
  printf '%s | %s -> %s
' "$(date -Is)" "$source" "$destination" >> "$journal"

  # Déplace les fichiers au lieu de les recopier afin de ne pas doubler
  # plusieurs gigaoctets de médias sur les grosses collections.
  while IFS= read -r -d '' item; do
    rel="${item#"$source"/}"
    target="$destination/$rel"

    if [[ -d "$item" ]]; then
      mkdir -p "$target"
      continue
    fi

    [[ -f "$item" || -L "$item" ]] || continue
    mkdir -p "$(dirname "$target")"

    if [[ ! -e "$target" && ! -L "$target" ]]; then
      mv "$item" "$target"
      printf 'MOVE | %s -> %s
' "$item" "$target" >> "$journal"
    elif cmp -s "$item" "$target" 2>/dev/null; then
      rm -f "$item"
      printf 'DUPLICATE-SUPPRIME | %s == %s
' "$item" "$target" >> "$journal"
    else
      conflict_target="$conflict/$rel"
      mkdir -p "$(dirname "$conflict_target")"
      n=1
      while [[ -e "$conflict_target" || -L "$conflict_target" ]]; do
        conflict_target="$conflict/$rel.$n"
        n=$((n + 1))
      done
      mv "$item" "$conflict_target"
      printf 'CONFLIT-CONSERVE | %s -> %s
' "$item" "$conflict_target" >> "$journal"
    fi
  done < <(find "$source" -mindepth 1 -print0)

  find "$source" -depth -type d -empty -delete 2>/dev/null || true

  # Tout objet spécial non traité reste conservé ici.
  if [[ -e "$source" || -L "$source" ]]; then
    mkdir -p "$(dirname "$leftover")"
    mv "$source" "$leftover"
    printf 'LEFTOVER | %s -> %s
' "$source" "$leftover" >> "$journal"
  fi

  chown -R pinball:pinball "$destination" "$(dirname "$journal")" 2>/dev/null || true
  [[ -d "$conflict" ]] && chown -R pinball:pinball "$conflict" 2>/dev/null || true

  [[ "$QUIET" -eq 1 ]] || echo "MOVE [√] $source -> $destination | journal=$journal"
}

is_table_dir() {
  find "$1" -maxdepth 1 -type f -iname '*.vpx' -print -quit 2>/dev/null | grep -q .
}

legacy_dir_exists() {
  local table="$1" rel="$2" found
  found="$(resolve_ci_rel_dir "$table" "$rel")"
  [[ -n "$found" && -d "$found" ]]
}

process_table() {
  local table="$1" dirty=0 alias ultradmd source

  # 1) Crée l'arborescence finale.
  for dir in "${ROOT_DIRS[@]}"; do
    normalize_case_dir "$table" "$dir" || dirty=1
  done

  normalize_case_dir "$table" pinmame || dirty=1

  for dir in "${PINMAME_DIRS[@]}"; do
    normalize_case_dir "$table/pinmame" "$dir" || dirty=1
  done

  ultradmd="$table/$(basename "$table").UltraDMD"
  ensure_dir "$ultradmd" || dirty=1

  alias="$table/pinmame/alias.txt"
  if [[ ! -f "$alias" ]]; then
    if [[ -e "$alias" || -L "$alias" ]]; then
      echo "NOGO [X] alias.txt n'est pas un fichier : $alias"
      dirty=1
    else
      if [[ "$MODE" == apply ]]; then
        : > "$alias"
        chown pinball:pinball "$alias" 2>/dev/null || true
        chmod 0664 "$alias" 2>/dev/null || true
      fi
      [[ "$QUIET" -eq 1 ]] || echo "CREATE [=] $alias"
    fi
  fi

  # 2) Anciennes structures PinCabOS / VPX vers la structure demandée.
  safe_migrate_dir "$table" roms pinmame/roms
  safe_migrate_dir "$table" nvram pinmame/nvram
  safe_migrate_dir "$table" cfg pinmame/cfg
  safe_migrate_dir "$table" ini pinmame/ini
  safe_migrate_dir "$table" memmaps pinmame/memmaps

  safe_migrate_dir "$table" altsound pinmame/altsound
  safe_migrate_dir "$table" altcolor pinmame/altcolor

  # Serum / PAL / VNI partagent maintenant la destination altcolor.
  safe_migrate_dir "$table" serum pinmame/altcolor
  safe_migrate_dir "$table" vni pinmame/altcolor
  safe_migrate_dir "$table" pinmame/serum pinmame/altcolor
  safe_migrate_dir "$table" pinmame/vni pinmame/altcolor

  # PuP reste à la racine du dossier de table, au pluriel.
  safe_migrate_dir "$table" pupvideo pupvideos
  safe_migrate_dir "$table" pinmame/pupvideo pupvideos
  safe_migrate_dir "$table" pinmame/pupvideos pupvideos

  # 3) Validation après correction.
  for dir in "${ROOT_DIRS[@]}"; do
    [[ -d "$table/$dir" ]] || dirty=1
  done

  for dir in "${PINMAME_DIRS[@]}"; do
    [[ -d "$table/pinmame/$dir" ]] || dirty=1
  done

  [[ -d "$ultradmd" && -f "$alias" ]] || dirty=1

  for source in \
    roms nvram cfg ini memmaps \
    altsound altcolor serum vni \
    pupvideo \
    pinmame/serum pinmame/vni \
    pinmame/pupvideo pinmame/pupvideos
  do
    legacy_dir_exists "$table" "$source" && dirty=1
  done

  if [[ "$dirty" -eq 0 ]]; then
    [[ "$QUIET" -eq 1 ]] || echo "GO [√] $table"
    return 0
  fi

  [[ "$QUIET" -eq 1 ]] || echo "NOGO [X] $table"
  return 1
}

TOTAL=0
DIRTY=0

while IFS= read -r -d '' table; do
  is_table_dir "$table" || continue
  TOTAL=$((TOTAL + 1))
  process_table "$table" || DIRTY=$((DIRTY + 1))
done < <(
  find "$TABLES_ROOT" \
    -mindepth 1 \
    -maxdepth 1 \
    -type d \
    ! -name '.*' \
    -print0 | sort -z
)

LOOSE="$(
  find "$TABLES_ROOT" \
    -mindepth 1 \
    -maxdepth 1 \
    -type f \
    -iname '*.vpx' \
    -print 2>/dev/null || true
)"

if [[ "$QUIET" -eq 0 ]]; then
  echo
  echo "Tables analysées      : $TOTAL"
  echo "Tables non conformes  : $DIRTY"

  if [[ -n "$LOOSE" ]]; then
    echo 'AVERTISSEMENT : fichiers VPX directement sous Tables; aucun déplacement automatique :'
    printf '%s\n' "$LOOSE"
  fi
fi

printf '%s | mode=%s | tables=%s | dirty=%s\n' \
  "$(date -Is)" "$MODE" "$TOTAL" "$DIRTY" \
  >> /opt/pincabos/logs/table-tree.log

[[ "$DIRTY" -eq 0 ]]
