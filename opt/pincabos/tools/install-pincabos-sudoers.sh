#!/usr/bin/env bash
# PinCabOS-File created by Karots Sugarpie
set -euo pipefail

echo "────────────────────────────────────────────────────────────────"
echo " PinCabOS - Installation sudoers ciblés"
echo "────────────────────────────────────────────────────────────────"

TPL_DIR="/opt/pincabos/essentials/sudoers.d"
DST_DIR="/etc/sudoers.d"

if [ ! -d "$TPL_DIR" ]; then
  echo "NOGOOD: dossier templates absent: $TPL_DIR"
  exit 1
fi

shopt -s nullglob
templates=("$TPL_DIR"/pincabos-*)

if [ "${#templates[@]}" -eq 0 ]; then
  echo "NOGOOD: aucun template sudoers pincabos-* trouvé dans $TPL_DIR"
  exit 1
fi

echo
echo "Templates détectés:"
for src in "${templates[@]}"; do
  echo " - $(basename "$src")"
done

echo
echo "=== Validation des templates avant installation ==="
for src in "${templates[@]}"; do
  if [ ! -f "$src" ]; then
    continue
  fi

  name="$(basename "$src")"

  # Sécurité: installer seulement les noms PinCabOS simples.
  case "$name" in
    pincabos-*) ;;
    *)
      echo "NOGOOD: nom template refusé: $name"
      exit 1
      ;;
  esac

  echo "Validation template: $name"
  visudo -cf "$src"
done

echo
echo "=== Installation vers /etc/sudoers.d ==="
for src in "${templates[@]}"; do
  if [ ! -f "$src" ]; then
    continue
  fi

  name="$(basename "$src")"
  dst="$DST_DIR/$name"

  echo
  echo "Installation sudoers: $name"
  install -m 440 -o root -g root "$src" "$dst"
  visudo -cf "$dst"
  echo "OK: $dst"
done

echo
echo "────────────────────────────────────────────────────────────────"
echo " OK: tous les sudoers PinCabOS templates ont été installés"
echo "────────────────────────────────────────────────────────────────"
