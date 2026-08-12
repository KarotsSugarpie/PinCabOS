#!/usr/bin/env bash
set -Eeuo pipefail
clear

VERSION="${1:-}"
CHANNEL="${2:-beta}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
MANAGED_PATHS="${MANAGED_PATHS:-/opt/pincabos/update/managed-paths.conf}"
[[ -f "$MANAGED_PATHS" ]] || MANAGED_PATHS="$SCRIPT_DIR/managed-paths.conf"

OUTPUT_ROOT="${OUTPUT_ROOT:-/opt/pincabos/build/updates/releases}"
RELEASE_DIR="$OUTPUT_ROOT/$VERSION"
STAGE="$RELEASE_DIR/rootfs"
FILES="$RELEASE_DIR/files.list"
ARCHIVE="$RELEASE_DIR/pincabos-update.tar.zst"

green=$'\033[1;32m'; orange=$'\033[1;33m'; red=$'\033[1;31m'; reset=$'\033[0m'
go(){ printf '%sGO [√]%s %s\n' "$green" "$reset" "$*"; }
warn(){ printf '%sAVERTISSEMENT%s %s\n' "$orange" "$reset" "$*" >&2; }
fail(){ printf '%sERREUR%s %s\n' "$red" "$reset" "$*" >&2; exit 1; }

[[ ${EUID:-$(id -u)} -eq 0 ]] || fail "Exécute ce script avec sudo."
[[ -n "$VERSION" ]] || fail "Usage: sudo build-update.sh VERSION [canal]"
[[ "$VERSION" =~ ^[A-Za-z0-9._+-]+$ ]] || fail "Version invalide."
[[ "$CHANNEL" =~ ^[A-Za-z0-9._-]+$ ]] || fail "Canal invalide."
[[ -s "$MANAGED_PATHS" ]] || fail "managed-paths.conf absent ou vide."
command -v zstd >/dev/null 2>&1 || fail "zstd est requis."
tar --help 2>/dev/null | grep -q -- '--zstd' || fail "GNU tar avec support zstd est requis."

rm -rf "$RELEASE_DIR"
mkdir -p "$STAGE"
: > "$FILES"

is_forbidden() {
  local p="$1"
  case "$p" in
    home/pinball/Tables/*|home/pinball/.vpinball/*|home/pinball/.config/vpinfe/*|\
    opt/pincabos/build/*|opt/pincabos/backups/*|opt/pincabos/logs/*|\
    opt/pincabos/web/.venv/*|opt/pincabos/web/backups/*|\
    opt/pincabos/cache/*|*/__pycache__/*|*.pyc|*.pyo)
      return 0 ;;
  esac
  return 1
}

add_item() {
  local absolute="$1" rel
  [[ "$absolute" == /* ]] || fail "Chemin non absolu dans managed-paths.conf: $absolute"
  if [[ -d "$absolute" && ! -L "$absolute" ]]; then
    while IFS= read -r -d '' item; do
      rel="${item#/}"
      is_forbidden "$rel" && continue
      printf '%s\n' "$rel" >> "$FILES"
    done < <(find "$absolute" -xdev \( -type f -o -type l \) -print0)
  elif [[ -f "$absolute" || -L "$absolute" ]]; then
    rel="${absolute#/}"
    is_forbidden "$rel" || printf '%s\n' "$rel" >> "$FILES"
  fi
}

while IFS= read -r pattern || [[ -n "$pattern" ]]; do
  pattern="${pattern%%#*}"
  pattern="${pattern#"${pattern%%[![:space:]]*}"}"
  pattern="${pattern%"${pattern##*[![:space:]]}"}"
  [[ -n "$pattern" ]] || continue

  matched=0
  while IFS= read -r match; do
    [[ -n "$match" ]] || continue
    matched=1
    add_item "$match"
  done < <(compgen -G "$pattern" || true)

  if (( matched == 0 )) && [[ -e "$pattern" || -L "$pattern" ]]; then
    add_item "$pattern"
    matched=1
  fi

  # Une entrée facultative absente n'est pas une erreur.
  :
done < "$MANAGED_PATHS"

sort -u "$FILES" -o "$FILES"
[[ -s "$FILES" ]] || fail "Aucun fichier à distribuer."

while IFS= read -r rel || [[ -n "$rel" ]]; do
  [[ -n "$rel" ]] || continue
  mkdir -p "$STAGE/$(dirname "$rel")"
  cp -a -- "/$rel" "$STAGE/$rel"
done < "$FILES"

while IFS= read -r rel || [[ -n "$rel" ]]; do
  case "$rel" in
    *.sh) bash -n "$STAGE/$rel" ;;
    *.py) python3 -m py_compile "$STAGE/$rel" ;;
  esac
done < "$FILES"
find "$STAGE" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$STAGE" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete

python3 - "$FILES" "$STAGE" <<'PY2'
from pathlib import Path
import sys

manifest = Path(sys.argv[1])
stage = Path(sys.argv[2])
kept = []

for raw in manifest.read_text(encoding="utf-8").splitlines():
    rel = raw.strip()
    if not rel:
        continue
    if "__pycache__" in Path(rel).parts:
        continue
    if rel.endswith((".pyc", ".pyo")):
        continue
    if (stage / rel).exists() or (stage / rel).is_symlink():
        kept.append(rel)

manifest.write_text(
    "".join(f"{item}\n" for item in sorted(set(kept))),
    encoding="utf-8",
)
PY2

[[ -s "$FILES" ]] || fail "Le manifeste est vide après nettoyage."

tar --zstd -cpf "$ARCHIVE" -C "$STAGE" -T "$FILES"
ARCHIVE_SHA="$(sha256sum "$ARCHIVE" | awk '{print $1}')"
FILE_COUNT="$(wc -l < "$FILES" | tr -d ' ')"
BUILT_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

cat > "$RELEASE_DIR/release.json" <<EOF
{
  "schema": 1,
  "version": "$VERSION",
  "channel": "$CHANNEL",
  "archive": "pincabos-update.tar.zst",
  "sha256": "$ARCHIVE_SHA",
  "files": "files.list",
  "file_count": $FILE_COUNT,
  "built_at": "$BUILT_AT"
}
EOF

(
  cd "$RELEASE_DIR"
  sha256sum pincabos-update.tar.zst files.list release.json > audit.sha256
)

rm -rf "$STAGE"

go "Scripts Bash et Python validés."
go "Paquet construit: $RELEASE_DIR"
go "Version: $VERSION"
go "Canal: $CHANNEL"
go "Fichiers distribués: $FILE_COUNT"
go "SHA256: $ARCHIVE_SHA"
printf '\nAudit obligatoire avant publication:\n  less %q\n' "$FILES"
printf '\nPublication:\n  sudo publish-update.sh %q\n' "$RELEASE_DIR"
