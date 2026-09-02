#!/usr/bin/env bash
# PINCABOS_BOOT_VIDEO_V1
# Video d'intro au demarrage du cab, jouee sur l'ecran playfield pendant que
# VPinFE se charge (ExecStartPre de pincabos-vpinfe.service), puis la DERNIERE
# IMAGE reste affichee jusqu'a ce que la fenetre VPinFE apparaisse : aucun
# ecran noir entre la fin de la video et le frontend.
#
# - Le proprietaire du cab depose SA video : /opt/pincabos/media/boot-video.mp4
#   (pas de fichier = demarrage normal, rien ne change).
# - Geometrie prise sur le ROLE playfield (display-aliases.env) : universel,
#   quel que soit le cablage ou le nombre d'ecrans du cabinet.
# - Une seule lecture par boot (flag dans /run) : le service VPinFE est en
#   Restart=always, sans ce verrou la video rejouerait a chaque relance.
# - N'importe quelle touche/bouton passe l'intro comme l'image finale.
# - Ce script ne doit JAMAIS bloquer le frontend : toute anomalie => exit 0,
#   lecture plafonnee par timeout, image finale tenue par un process detache
#   (systemd-run) avec garde-fou.
#
# Reglages optionnels dans /opt/pincabos/config/boot-video.conf :
#   BOOT_VIDEO_ENABLED=1|0      BOOT_VIDEO_FILE=/chemin/video.mp4
#   BOOT_VIDEO_ROTATE=auto|0|90|180|270   (auto : rotation anti-horaire si la
#                                          video et l'ecran n'ont pas la meme
#                                          orientation, comme les medias tables)
#   BOOT_VIDEO_MAX_SECONDS=60   BOOT_VIDEO_VOLUME=100
#   BOOT_VIDEO_HOLD_MAX_SECONDS=90   (duree max de l'image finale)
set -u
# PINCABOS_PATHS_CONSUMER_V1
. /opt/pincabos/lib/pincabos-paths.sh

BOOT_VIDEO_ENABLED=1
BOOT_VIDEO_FILE=/opt/pincabos/media/boot-video.mp4
BOOT_VIDEO_ROTATE=auto
BOOT_VIDEO_MAX_SECONDS=60
BOOT_VIDEO_VOLUME=100
BOOT_VIDEO_HOLD_MAX_SECONDS=90

CONF=/opt/pincabos/config/boot-video.conf
FLAG=/run/pincabos-boot-video.played
LASTFRAME=/run/pincabos-boot-video.lastframe.png
SELF=/opt/pincabos/bin/pincabos-boot-video.sh

# shellcheck disable=SC1090
[ -f "$CONF" ] && . "$CONF" 2>/dev/null

# environnement de session identique a run-vpinfe-systemd.sh (X + audio)
as_pinball() {
  /usr/sbin/runuser -u "$PCO_USER" -- /usr/bin/env \
    HOME="$PCO_HOME" \
    DISPLAY="$PCO_DISPLAY" \
    XAUTHORITY="$PCO_XAUTHORITY" \
    XDG_RUNTIME_DIR="$PCO_RUNTIME_DIR" \
    DBUS_SESSION_BUS_ADDRESS="$PCO_DBUS_ADDRESS" \
    "$@"
}

# --- geometrie du role playfield (source de verite topologie) ---------------
SW="" SH="" SX=0 SY=0
load_playfield_geometry() {
  local f geo=""
  for f in /run/pincabos/display-aliases.env "$PCO_ALIASES_ENV"; do
    if [ -f "$f" ]; then
      # shellcheck disable=SC1090
      . "$f" 2>/dev/null || true
      [ "${PINCABOS_PLAYFIELD_AVAILABLE:-0}" = "1" ] && geo="${PINCABOS_PLAYFIELD_GEOMETRY:-}"
      break
    fi
  done
  if [[ "$geo" =~ ^([0-9]+)x([0-9]+)\+(-?[0-9]+)\+(-?[0-9]+)$ ]]; then
    SW="${BASH_REMATCH[1]}" SH="${BASH_REMATCH[2]}"
    SX="${BASH_REMATCH[3]}" SY="${BASH_REMATCH[4]}"
  fi
}

place_args() {
  if [ -n "$SW" ]; then
    printf '%s ' -x "$SW" -y "$SH" -left "$SX" -top "$SY"
  else
    printf '%s ' -fs
  fi
}

# --- mode interne : tenir la derniere image jusqu'a la fenetre VPinFE -------
if [ "${1:-}" = "--hold" ]; then
  [ -s "$LASTFRAME" ] || exit 0
  load_playfield_geometry
  # shellcheck disable=SC2046
  as_pinball ffplay -hide_banner -loglevel error -noborder -alwaysontop \
    -loop 0 -an -exitonkeydown -exitonmousedown \
    $(place_args) "$LASTFRAME" >/dev/null 2>&1 &
  HOLD_PID=$!
  DEADLINE=$((SECONDS + BOOT_VIDEO_HOLD_MAX_SECONDS))
  while [ "$SECONDS" -lt "$DEADLINE" ]; do
    kill -0 "$HOLD_PID" 2>/dev/null || break
    if command -v wmctrl >/dev/null 2>&1 \
       && as_pinball wmctrl -l 2>/dev/null | grep -qi vpinfe; then
      # la fenetre existe : petite grace le temps qu'elle peigne son contenu
      sleep 3
      break
    fi
    sleep 1
  done
  kill "$HOLD_PID" 2>/dev/null || true
  rm -f "$LASTFRAME"
  exit 0
fi

FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1

[ "$BOOT_VIDEO_ENABLED" = "1" ] || exit 0
[ -f "$BOOT_VIDEO_FILE" ] || exit 0
command -v ffplay >/dev/null 2>&1 || exit 0

if [ "$FORCE" != "1" ]; then
  [ -e "$FLAG" ] && exit 0
fi
touch "$FLAG" 2>/dev/null || true

load_playfield_geometry

# --- rotation ----------------------------------------------------------------
ROT="$BOOT_VIDEO_ROTATE"
if [ "$ROT" = "auto" ]; then
  ROT=0
  if [ -n "$SW" ] && command -v ffprobe >/dev/null 2>&1; then
    IFS=, read -r VW VH < <(ffprobe -v error -select_streams v:0 \
      -show_entries stream=width,height -of csv=p=0 \
      "$BOOT_VIDEO_FILE" 2>/dev/null) || true
    if [ -n "${VW:-}" ] && [ -n "${VH:-}" ]; then
      SP=0; VP=0
      [ "$SH" -gt "$SW" ] && SP=1
      [ "$VH" -gt "$VW" ] && VP=1
      # 270 (anti-horaire) : meme convention que les medias playfield des
      # tables (haut de table a gauche de l'espace X, verifie sur cab reel)
      [ "$SP" != "$VP" ] && ROT=270
    fi
  fi
fi

case "$ROT" in
  90)  VF="transpose=1" ;;
  180) VF="transpose=1,transpose=1" ;;
  270) VF="transpose=2" ;;
  *)   VF="null" ;;
esac

# letterbox exact dans la fenetre playfield (jamais de deformation)
if [ -n "$SW" ]; then
  VF="$VF,scale=${SW}:${SH}:force_original_aspect_ratio=decrease"
  VF="$VF,pad=${SW}:${SH}:(ow-iw)/2:(oh-ih)/2:black"
fi

# timeout DANS le runuser : timeout(1) ne sait pas lancer une fonction shell
# shellcheck disable=SC2046
as_pinball timeout "$BOOT_VIDEO_MAX_SECONDS" \
  ffplay -hide_banner -loglevel error -noborder -alwaysontop \
    -autoexit -exitonkeydown -exitonmousedown \
    -volume "$BOOT_VIDEO_VOLUME" -vf "$VF" \
    $(place_args) "$BOOT_VIDEO_FILE" >/dev/null 2>&1 || true

# --- derniere image tenue jusqu'a ce que VPinFE soit pret -------------------
if command -v ffmpeg >/dev/null 2>&1 && command -v systemd-run >/dev/null 2>&1; then
  # le filtre inclut deja rotation + letterbox : l'image est prete a afficher
  ffmpeg -hide_banner -loglevel error -y -sseof -0.5 -i "$BOOT_VIDEO_FILE" \
    -frames:v 1 -update 1 -vf "$VF" "$LASTFRAME" >/dev/null 2>&1 || true
  if [ -s "$LASTFRAME" ]; then
    # detache dans son propre cgroup : ExecStartPre doit rendre la main pour
    # que VPinFE demarre pendant que l'image reste a l'ecran au-dessus de lui
    systemd-run --unit="pincabos-boot-video-hold-$$" --collect --no-block \
      "$SELF" --hold >/dev/null 2>&1 || rm -f "$LASTFRAME"
  fi
fi

exit 0
