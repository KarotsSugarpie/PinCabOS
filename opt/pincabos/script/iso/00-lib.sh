#!/usr/bin/env bash
# PINCABOS_ISO_ETAPES_V1 — bibliotheque commune des etapes d iso.sh
#
# Variables et fonctions de l ancien en-tete d iso.sh, texte inchange. Chaque
# etape (opt/pincabos/iso/NN-*.sh) la source ; l orchestrateur (iso.sh) aussi.
# L orchestrateur fixe PCO_ISO_LOG (un journal par build) et PCO_ISO_SCRIPT_DIR
# (dossier d iso.sh : moteur d installation et iso-live.sh a cote).



VERSION="v8.1g"
VERSION_UPPER="V8.1G"

CACHE_DIR="/opt/pincabos/cache/iso-base"

BUILD_BASE="/opt/pincabos/build"
WORK="$BUILD_BASE/live-v8.1g-english"
PAYLOAD_FULL="$WORK/payload-full"
ISO_DIR="$WORK/iso"
ROOTFS_DIR="$WORK/squashfs-root"

OUT_DIR="$BUILD_BASE/output"
OUT_ISO="$OUT_DIR/PinCabOS-beta-Installer.iso"

# PINCABOS_ISO_MODELE_LIVE_V2
# Le modele live est LE modele (decision Yann + Karots 05/09/2026) : le payload
# EST le systeme live (casper/filesystem.squashfs), meme noyau, memes pilotes,
# memes outils que le cab installe ; l assistant graphique y voit le vrai
# materiel. L ISO est produite par iso-live.sh. Le modele classique (base Ubuntu
# live-server + payload en morceaux, sections 9-11 et 14-20) a ete retire :
# --classic refuse, --live reste accepte par compatibilite.
PCO_ISO_MODEL="live"
LIVE_ROOTFS="$WORK/live-rootfs"
# PINCABOS_INSTALLEUR_FICHIERS_V1 : le moteur d installation, le helper de payload,
# l attente du media et l unite tty sont des fichiers du depot (opt/pincabos/script/installer/),
# installes tels quels ; plus de heredoc.
INSTALLER_SRC="${PCO_ISO_SCRIPT_DIR:-$(dirname "$(readlink -f "$0")")}/installer"
[ -d "$INSTALLER_SRC" ] || INSTALLER_SRC="/opt/pincabos/script/installer"

LOG_DIR="$BUILD_BASE/logs"
mkdir -p "$LOG_DIR"
LOG="${PCO_ISO_LOG:-$LOG_DIR/iso-v8.1g-$(date +%Y%m%d-%H%M%S).log}"


die() {
  echo "ERROR: $*"
  exit 1
}

run() {
  echo ">>> $*"
  "$@"
}

cleanup_mounts() {
  set +e
  for p in "$ROOTFS_DIR/dev" "$ROOTFS_DIR/proc" "$ROOTFS_DIR/sys" "$ROOTFS_DIR/run"; do
    mountpoint -q "$p" && umount -R "$p"
  done
  set -e
}
trap cleanup_mounts EXIT

# PINCABOS_ISO_ETAPES_V1 : definitions partagees par plusieurs etapes (avant : posees
# au fil du script). Memes valeurs, meme ordre d evaluation relatif.
ARCHIVE="$PAYLOAD_FULL/pincabos-rootfs-cab-v8.1g.tar.zst"
OVERLAY="$PAYLOAD_FULL/pincabos-plymouth-theme-overlay-v8.1g.tar.zst"
MANIFEST="$PAYLOAD_FULL/pincabos-rootfs-cab-v8.1g.manifest.txt"
VPXTOOL_MANIFEST="/opt/pincabos/update/vpxtool-release.json"

# PINCABOS_ISO_ETAPES_V1 : ce qu une etape calcule et qu une autre relit (avant : une
# variable du meme shell). Ecrit par pco_etat_ecrire VAR, relu ici par chaque etape.
ETAT_ENV="$WORK/iso-etat.env"
pco_etat_ecrire() {
  local v="$1"
  mkdir -p "$WORK"
  { [ -f "$ETAT_ENV" ] && grep -v "^$v=" "$ETAT_ENV" || true; printf '%s=%q\n' "$v" "${!v}"; } > "$ETAT_ENV.tmp"
  mv -f "$ETAT_ENV.tmp" "$ETAT_ENV"
}
# shellcheck disable=SC1090
if [ -f "$ETAT_ENV" ]; then . "$ETAT_ENV"; fi
