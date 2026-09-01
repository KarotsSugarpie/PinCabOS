#!/usr/bin/env bash
set -Eeuo pipefail

TABLES_ROOT="/home/pinball/Tables"
PINBALL_UID="$(id -u)"
RUNTIME="/run/user/$PINBALL_UID/pincabos-backglass-bridge"

CHROME="$(command -v google-chrome || command -v google-chrome-stable || command -v chromium || true)"
[[ -n "$CHROME" ]] || {
  logger -t pincabos-backglass-bridge "ERREUR : Chrome/Chromium introuvable."
  exit 1
}

export HOME="/home/pinball"
export USER="pinball"
export LOGNAME="pinball"
export DISPLAY=":0"
export XDG_RUNTIME_DIR="/run/user/$PINBALL_UID"

active_cfg=""
active_profile=""

cfg_get() {
  local cfg="$1"
  local wanted="$2"

  awk -v wanted="$wanted" '
    BEGIN { inside=0 }
    /^[[:space:]]*\[PinCabOSBackglass\][[:space:]]*$/ { inside=1; next }
    /^[[:space:]]*\[/ { inside=0 }
    inside && index($0, "=") {
      key=substr($0, 1, index($0, "=")-1)
      value=substr($0, index($0, "=")+1)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", key)
      gsub(/[[:space:]]*[#;].*$/, "", value)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
      if (key == wanted) {
        print value
        exit
      }
    }
  ' "$cfg"
}

vpx_cmdline_contains() {
  local pid="$1"
  local expected="$2"

  [[ -r "/proc/$pid/cmdline" ]] || return 1
  tr '\0' '\n' <"/proc/$pid/cmdline" | grep -Fqx -- "$expected"
}

find_matching_config() {
  MATCH_CFG=""
  MATCH_PID=""

  while IFS= read -r -d '' cfg; do
    local enabled vpx_file table_dir expected pid

    enabled="$(cfg_get "$cfg" "Enabled")"
    [[ "$enabled" == "1" ]] || continue

    vpx_file="$(cfg_get "$cfg" "VPXFile")"
    [[ -n "$vpx_file" ]] || continue

    table_dir="$(dirname "$cfg")"
    expected="$table_dir/$vpx_file"

    while IFS= read -r pid; do
      [[ -n "$pid" ]] || continue
      if vpx_cmdline_contains "$pid" "$expected"; then
        MATCH_CFG="$cfg"
        MATCH_PID="$pid"
        return 0
      fi
    done < <(pgrep -u "$PINBALL_UID" -f 'VPinballX_BGFX.*\.vpx' || true)
  done < <(
    find "$TABLES_ROOT" \
      -path '*/.pincabos-backups' -prune -o \
      -type f -name 'PinCabOS-Backglass.ini' -print0
  )

  return 1
}

geometry_for_output() {
  local output="$1"

  xrandr --query 2>/dev/null |
  awk -v output="$output" '
    $1 == output && $2 == "connected" {
      for (i = 3; i <= NF; i++) {
        if ($i ~ /^[0-9]+x[0-9]+\+[0-9]+\+[0-9]+$/) {
          print $i
          exit
        }
      }
    }
  '
}

# PINCABOS_BACKGLASS_ROLE_FROM_SCREENS_V1
# Geometrie d'un role d'ecran (backglass/fulldmd) depuis display-aliases.env,
# lui-meme genere depuis screens.json (source de verite du cab). Vide si absent.
role_geometry() {
  local role="$1"
  local env_file="/opt/pincabos/config/display-aliases.env"

  [[ -f "$env_file" ]] || return 0
  (
    # shellcheck disable=SC1090
    . "$env_file" 2>/dev/null || exit 0
    case "$role" in
      backglass)
        [[ "${PINCABOS_BACKGLASS_AVAILABLE:-0}" == "1" ]] &&
          printf '%s\n' "${PINCABOS_BACKGLASS_GEOMETRY:-}"
        ;;
      fulldmd)
        [[ "${PINCABOS_FULLDMD_AVAILABLE:-0}" == "1" ]] &&
          printf '%s\n' "${PINCABOS_FULLDMD_GEOMETRY:-}"
        ;;
    esac
  ) || true
}

# Resolution de la geometrie cible du backglass :
#   1. DisplayOutput peut nommer un ROLE (backglass/fulldmd) -> screens.json ;
#   2. sinon, la sortie X11 nommee, SEULEMENT si elle existe sur CE cab (le
#      nom ecrit dans la table vient de la machine de l'auteur, ex. DP-1) ;
#   3. sinon, le role backglass reel de ce cab ;
#   4. en dernier recours, l'ancien repli historique.
resolve_backglass_geometry() {
  local output="$1"
  local geometry=""

  case "${output,,}" in
    backglass|fulldmd)
      geometry="$(role_geometry "${output,,}")"
      ;;
    *)
      geometry="$(geometry_for_output "$output")"
      ;;
  esac

  [[ -n "$geometry" ]] || geometry="$(role_geometry backglass)"
  echo "${geometry:-1920x1080+3840+0}"
}

close_active() {
  [[ -n "$active_profile" ]] || return 0
  pkill -u "$PINBALL_UID" -f -- "--user-data-dir=$active_profile" 2>/dev/null || true
  active_cfg=""
  active_profile=""
}

hide_vpx_backglass() {
  local window_id

  window_id="$(
    wmctrl -lGx 2>/dev/null |
    awk '/Visual Pinball Backglass$/ { print $1; exit }'
  )"

  [[ -n "$window_id" ]] &&
    wmctrl -i -r "$window_id" -b add,hidden 2>/dev/null || true
}

write_html() {
  local html="$1"
  local title="$2"
  local media_url="$3"
  local ext="${media_url##*.}"

  case "${ext,,}" in
    mp4|webm|mkv|avi|mov)
      cat >"$html" <<EOF
<!doctype html>
<html><head><meta charset="utf-8"><title>$title</title>
<style>html,body,video{margin:0;width:100%;height:100%;overflow:hidden;background:#000}video{object-fit:cover}</style>
</head><body><video autoplay loop muted playsinline><source src="$media_url"></video></body></html>
EOF
      ;;
    *)
      cat >"$html" <<EOF
<!doctype html>
<html><head><meta charset="utf-8"><title>$title</title>
<style>html,body,img{margin:0;width:100%;height:100%;overflow:hidden;background:#000}img{object-fit:cover}</style>
</head><body><img src="$media_url"></body></html>
EOF
      ;;
  esac
}

start_for_config() {
  local cfg="$1"
  local table_dir media_setting media output title geometry
  local width height pos_x pos_y key root profile html media_url window_id

  table_dir="$(dirname "$cfg")"
  media_setting="$(cfg_get "$cfg" "Media")"
  output="$(cfg_get "$cfg" "DisplayOutput")"
  title="$(cfg_get "$cfg" "WindowTitle")"

  [[ -n "$output" ]] || output="DP-1"
  [[ -n "$title" ]] || title="PinCabOS Backglass"

  [[ -n "$media_setting" ]] || {
    logger -t pincabos-backglass-bridge "ERREUR : Media absent dans $cfg"
    return 1
  }

  if [[ "$media_setting" == /* ]]; then
    media="$media_setting"
  else
    media="$table_dir/$media_setting"
  fi

  [[ -f "$media" ]] || {
    logger -t pincabos-backglass-bridge "ERREUR : média absent : $media"
    return 1
  }

  geometry="$(resolve_backglass_geometry "$output")"

  if [[ "$geometry" =~ ^([0-9]+)x([0-9]+)\+([0-9]+)\+([0-9]+)$ ]]; then
    width="${BASH_REMATCH[1]}"
    height="${BASH_REMATCH[2]}"
    pos_x="${BASH_REMATCH[3]}"
    pos_y="${BASH_REMATCH[4]}"
  else
    width=1920
    height=1080
    pos_x=3840
    pos_y=0
  fi

  key="$(printf '%s' "$cfg" | sha256sum | awk '{print $1}')"
  root="$RUNTIME/$key"
  profile="$root/profile"
  html="$root/index.html"

  rm -rf "$root"
  install -d -m 700 "$profile"

  media_url="$(python3 - "$media" <<'PY'
from pathlib import Path
import sys
print(Path(sys.argv[1]).resolve().as_uri())
PY
)"

  write_html "$html" "$title" "$media_url"

  if [[ "$(cfg_get "$cfg" "HideVPXBackglass")" == "1" ]]; then
    hide_vpx_backglass
  fi

  "$CHROME" \
    --user-data-dir="$profile" \
    --no-first-run \
    --disable-session-crashed-bubble \
    --disable-infobars \
    --autoplay-policy=no-user-gesture-required \
    --kiosk \
    --app="file://$html" \
    --window-position="$pos_x,$pos_y" \
    --window-size="$width,$height" \
    >/tmp/pincabos-backglass-bridge.log 2>&1 &

  window_id=""
  for _ in $(seq 1 25); do
    window_id="$(
      wmctrl -lGx 2>/dev/null |
      grep -F "$title" |
      awk '{print $1; exit}'
    )"
    [[ -n "$window_id" ]] && break
    sleep 1
  done

  [[ -n "$window_id" ]] || {
    logger -t pincabos-backglass-bridge "ERREUR : fenêtre Chrome absente pour $cfg"
    return 1
  }

  wmctrl -i -r "$window_id" -e "0,$pos_x,$pos_y,$width,$height" 2>/dev/null || true
  wmctrl -i -r "$window_id" -b add,fullscreen,above 2>/dev/null || true

  active_cfg="$cfg"
  active_profile="$profile"

  logger -t pincabos-backglass-bridge \
    "Actif : $(basename "$(dirname "$cfg")") sur $output ($geometry)"
}

cleanup() {
  close_active
}
trap cleanup EXIT INT TERM

logger -t pincabos-backglass-bridge "Service démarré"

while true; do
  if find_matching_config; then
    if [[ "$MATCH_CFG" != "$active_cfg" ]]; then
      close_active
      start_for_config "$MATCH_CFG" || true
    fi

    if [[ "$(cfg_get "$MATCH_CFG" "HideVPXBackglass")" == "1" ]]; then
      hide_vpx_backglass
    fi

    sleep 1
  else
    close_active
    sleep 2
  fi
done
