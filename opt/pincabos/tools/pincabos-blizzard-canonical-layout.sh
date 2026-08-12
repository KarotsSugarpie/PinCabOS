#!/usr/bin/env bash
set -Eeuo pipefail
shopt -s nullglob

MODE="${1:---check}"

TABLE="/home/pinball/Tables/The Blizzard Of Ozz (Original 2025)"
BASE="$(basename "$TABLE")"
VPX="$TABLE/$BASE.vpx"
VBS="$TABLE/$BASE.vbs"
B2S="$TABLE/$BASE.directb2s"

MUSIC_ROOT="$TABLE/music"
MUSIC_DEST="$MUSIC_ROOT/BLIZZARD"

PUP="$TABLE/pupvideos/BlizzardOfOzz"
PUP_BG_DIR="$PUP/Backglass"
PUP_BG="$PUP_BG_DIR/Backglass.mp4"
PUP_OVERLAYS="$PUP/PuPOverlays"
PUP_FONTS="$PUP/FONTS"

ROOT_FONTS="$TABLE/fonts"
PROFILE="$PUP/PuP-Pack_Options/3 Screen - FullDMD"

case "$MODE" in
  --check|--apply) ;;
  *)
    echo "Usage : $0 [--check|--apply]"
    exit 2
    ;;
esac

echo "==============================================================="
echo " BLIZZARD OF OZZ — STRUCTURE CANONIQUE TABLE / PUP / B2S"
echo " Mode : $MODE"
echo "==============================================================="

if pgrep -af 'VPinballX_BGFX.*The Blizzard Of Ozz.*\.vpx' >/dev/null; then
  echo "ERREUR : Blizzard est ouvert. Ferme la table avant de continuer."
  exit 1
fi

for p in "$TABLE" "$VPX" "$VBS" "$MUSIC_ROOT" "$PUP" "$PROFILE"; do
  [[ -e "$p" ]] || { echo "ERREUR : introuvable : $p"; exit 1; }
done

BACKUP=""
if [[ "$MODE" == "--apply" ]]; then
  STAMP="$(date +%Y%m%d-%H%M%S)"
  BACKUP="$TABLE/.pincabos-backups/blizzard-canonical-layout-$STAMP"
  mkdir -p "$BACKUP"

  for f in screens.pup playlists.pup triggers.pup; do
    [[ -f "$PUP/$f" ]] && cp -a "$PUP/$f" "$BACKUP/$f.before"
  done

  {
    echo "Date : $(date -Is)"
    echo "B2S attendu : $B2S"
    echo "PuP Backglass attendu : $PUP_BG"
    echo "PuP overlays attendus : $PUP_OVERLAYS"
    echo "Musique attendue : $MUSIC_DEST"
    echo "Polices attendues : $PUP_FONTS"
  } >"$BACKUP/manifest.txt"

  echo "Sauvegarde : $BACKUP"
fi

echo
echo "--- B2S statique ---"
if [[ -f "$B2S" ]]; then
  echo "OK : B2S déjà au chemin canonique."
else
  mapfile -t B2S_CANDIDATES < <(
    find "$TABLE" -path "$TABLE/.pincabos-backups" -prune -o \
      -type f -iname '*.directb2s' -print
  )

  if [[ "${#B2S_CANDIDATES[@]}" -ne 1 ]]; then
    echo "ERREUR : B2S attendu introuvable et candidats ambigus : ${#B2S_CANDIDATES[@]}"
    printf '  %s\n' "${B2S_CANDIDATES[@]:-}"
    exit 1
  fi

  echo "B2S à replacer : ${B2S_CANDIDATES[0]}"
  [[ "$MODE" == "--apply" ]] && mv -v "${B2S_CANDIDATES[0]}" "$B2S"
fi

echo
echo "--- PuP Backglass ---"
if [[ -f "$PUP_BG" ]]; then
  echo "OK : Backglass.mp4 déjà au chemin canonique."
else
  mapfile -t BG_CANDIDATES < <(
    find "$TABLE" -path "$TABLE/.pincabos-backups" -prune -o \
      -type f -iname 'Backglass.mp4' -print
  )

  if [[ "${#BG_CANDIDATES[@]}" -ne 1 ]]; then
    echo "ERREUR : Backglass.mp4 introuvable ou ambigu : ${#BG_CANDIDATES[@]}"
    printf '  %s\n' "${BG_CANDIDATES[@]:-}"
    exit 1
  fi

  echo "Backglass PuP à replacer : ${BG_CANDIDATES[0]}"
  if [[ "$MODE" == "--apply" ]]; then
    mkdir -p "$PUP_BG_DIR"
    mv -v "${BG_CANDIDATES[0]}" "$PUP_BG"
  fi
fi

echo
echo "--- PuP overlays / rule cards ---"
if [[ -d "$PUP_OVERLAYS" ]]; then
  echo "OK : PuPOverlays déjà au chemin canonique."
else
  mapfile -t OVERLAY_CANDIDATES < <(
    find "$TABLE" -path "$TABLE/.pincabos-backups" -prune -o \
      -type d -iname 'PuPOverlays' -print
  )

  if [[ "${#OVERLAY_CANDIDATES[@]}" -ne 1 ]]; then
    echo "ERREUR : PuPOverlays introuvable ou ambigu : ${#OVERLAY_CANDIDATES[@]}"
    printf '  %s\n' "${OVERLAY_CANDIDATES[@]:-}"
    exit 1
  fi

  echo "PuPOverlays à replacer : ${OVERLAY_CANDIDATES[0]}"
  [[ "$MODE" == "--apply" ]] && mv -v "${OVERLAY_CANDIDATES[0]}" "$PUP_OVERLAYS"
fi

CARD_COUNT="$(find "$PUP_OVERLAYS" -maxdepth 1 -type f -iname 'card*.png' | wc -l)"
echo "Rule cards détectées : $CARD_COUNT"

echo
echo "--- Musique originale BLIZZARD ---"
ROOT_MP3=( "$MUSIC_ROOT"/*.mp3 )
DEST_MP3=( "$MUSIC_DEST"/*.mp3 )

if (( ${#DEST_MP3[@]} == 57 && ${#ROOT_MP3[@]} == 0 )); then
  echo "OK : 57 MP3 déjà dans music/BLIZZARD/."
elif (( ${#ROOT_MP3[@]} == 57 && ${#DEST_MP3[@]} == 0 )); then
  echo "57 MP3 à replacer dans music/BLIZZARD/."
  if [[ "$MODE" == "--apply" ]]; then
    mkdir -p "$MUSIC_DEST"
    mv -v "$MUSIC_ROOT"/*.mp3 "$MUSIC_DEST/"
  fi
else
  echo "ERREUR : état MP3 ambigu."
  echo "music/ : ${#ROOT_MP3[@]} | music/BLIZZARD/ : ${#DEST_MP3[@]}"
  exit 1
fi

echo
echo "--- Polices PuP ---"
ROOT_TTF=( "$ROOT_FONTS"/*.ttf )
PUP_TTF=( "$PUP_FONTS"/*.ttf )

if [[ -d "$PUP_FONTS" && ! -L "$PUP_FONTS" && ${#PUP_TTF[@]} -ge 12 ]]; then
  echo "OK : polices déjà dans PuP/FONTS/."
elif [[ -L "$PUP_FONTS" && "$(readlink -f "$PUP_FONTS")" == "$ROOT_FONTS" && ${#ROOT_TTF[@]} -ge 12 ]]; then
  echo "Polices à déplacer de fonts/ vers PuP/FONTS/."
  if [[ "$MODE" == "--apply" ]]; then
    rm "$PUP_FONTS"
    mkdir -p "$PUP_FONTS"
    mv -v "$ROOT_FONTS"/*.ttf "$PUP_FONTS/"
    rmdir "$ROOT_FONTS" 2>/dev/null || true
  fi
elif [[ ! -e "$PUP_FONTS" && ${#ROOT_TTF[@]} -ge 12 ]]; then
  echo "Polices à déplacer de fonts/ vers PuP/FONTS/."
  if [[ "$MODE" == "--apply" ]]; then
    mkdir -p "$PUP_FONTS"
    mv -v "$ROOT_FONTS"/*.ttf "$PUP_FONTS/"
    rmdir "$ROOT_FONTS" 2>/dev/null || true
  fi
else
  echo "ERREUR : état polices ambigu."
  echo "fonts/ : ${#ROOT_TTF[@]} | PuP/FONTS/ : ${#PUP_TTF[@]}"
  exit 1
fi

echo
echo "--- Profil PuP actif : 3 Screen - FullDMD ---"
for f in screens.pup playlists.pup triggers.pup; do
  [[ -f "$PROFILE/$f" ]] || { echo "ERREUR : profil incomplet : $PROFILE/$f"; exit 1; }

  if [[ "$MODE" == "--apply" ]]; then
    install -m 644 "$PROFILE/$f" "$PUP/$f"
  fi
  echo "OK : $f synchronisé depuis le profil 3 écrans."
done

if [[ "$MODE" == "--apply" ]]; then
  python3 - "$PUP/screens.pup" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
raw = path.read_bytes()
nl = b"\r\n" if b"\r\n" in raw else b"\n"
rows = raw.splitlines(keepends=True)

exists = any(
    row.rstrip(b"\r\n").split(b",", 1)[0].strip() == b"0"
    for row in rows[1:]
)

if not exists:
    rows.insert(1, b"0,Topper,,,0,ForcePopBack,," + nl)
    path.write_bytes(b"".join(rows))
    print("OK : screen 0 Topper ajouté pour compatibilité PuP Linux.")
else:
    print("OK : screen 0 déjà présent.")
PY
fi

echo
echo "--- Validation finale ---"
test -f "$B2S"
test -f "$PUP_BG"
test -d "$PUP_OVERLAYS"
test -f "$PUP_FONTS/Calvera Personal Use Only.ttf"
test -f "$MUSIC_DEST/01 - I Don_t Wanna Stop.mp3"
grep -qE '^2,Backglass,' "$PUP/screens.pup"
grep -qE '^5,FullDMD,' "$PUP/screens.pup"
grep -qE '^0,Topper,' "$PUP/screens.pup"

echo "OK : B2S statique, PuP Backglass, overlays, musique, polices et profil actifs validés."

if [[ "$MODE" == "--apply" ]]; then
  echo "Sauvegarde : $BACKUP"
fi

echo "==============================================================="
echo " TERMINÉ"
echo "==============================================================="
