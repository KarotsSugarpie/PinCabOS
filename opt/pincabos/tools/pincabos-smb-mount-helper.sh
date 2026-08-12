#!/usr/bin/env bash
# PinCabOS-File created by Karots Sugarpie
set -euo pipefail

SOURCE="${1:-}"
MOUNTPOINT="${2:-}"
CREDFILE="${3:-}"

BASE="/home/pinball/NetworkDrives"

if [[ -z "$SOURCE" || -z "$MOUNTPOINT" || -z "$CREDFILE" ]]; then
  echo "Usage: $0 //<server>/<share> /home/pinball/NetworkDrives/name /path/credfile" >&2
  exit 2
fi

case "$SOURCE" in
  //*/*) ;;
  *)
    echo "Source SMB invalide: $SOURCE" >&2
    exit 3
    ;;
esac

MOUNT_REAL="$(readlink -m "$MOUNTPOINT")"
BASE_REAL="$(readlink -m "$BASE")"
CRED_REAL="$(readlink -m "$CREDFILE")"

case "$MOUNT_REAL" in
  "$BASE_REAL"/*) ;;
  *)
    echo "Mountpoint interdit: $MOUNT_REAL" >&2
    exit 4
    ;;
esac

case "$CRED_REAL" in
  /home/pinball/.config/pincabos/smb/*) ;;
  *)
    echo "Fichier credentials interdit: $CRED_REAL" >&2
    exit 5
    ;;
esac

chmod 600 "$CRED_REAL"
mkdir -p "$MOUNT_REAL"

if mountpoint -q "$MOUNT_REAL"; then
  echo "Déjà monté: $MOUNT_REAL"
  exit 0
fi

COMMON_OPTS="credentials=$CRED_REAL,uid=1000,gid=1000,iocharset=utf8,file_mode=0664,dir_mode=0775,noperm,noserverino,soft,actimeo=1"

attempt_mount() {
  local extra_opts="$1"
  echo "Essai montage avec options: $extra_opts"
  timeout 25s mount -t cifs "$SOURCE" "$MOUNT_REAL" -o "$COMMON_OPTS,$extra_opts"
}

if attempt_mount "vers=3.1.1,sec=ntlmssp"; then
  echo "Monté avec SMB 3.1.1"
elif attempt_mount "vers=3.0,sec=ntlmssp"; then
  echo "Monté avec SMB 3.0"
elif attempt_mount "vers=3.0"; then
  echo "Monté avec SMB 3.0 sans sec forcé"
elif attempt_mount "vers=2.1,sec=ntlmssp"; then
  echo "Monté avec SMB 2.1"
elif attempt_mount "vers=2.1"; then
  echo "Monté avec SMB 2.1 sans sec forcé"
else
  echo "Échec montage SMB. Derniers messages kernel:" >&2
  dmesg | tail -n 40 >&2
  exit 13
fi

# Ne PAS faire de chown -R sur un partage SMB : ça peut bloquer très longtemps.
echo "Monté: $SOURCE -> $MOUNT_REAL"
exit 0
