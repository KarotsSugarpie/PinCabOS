#!/usr/bin/env bash
# Created by Karots Sugarpie
# PINCABOS_SCRIPT_NAME="pkg-apt-base.sh"
# PINCABOS_SCRIPT_ROLE="Repair APT/dpkg, update package metadata, and install base system tools"
# PINCABOS_SCRIPT_REQUIRES_FILES="/opt/pincabos/install/packages/pkg-lib.sh"
# PINCABOS_SCRIPT_REQUIRES_PACKAGES="ca-certificates curl wget gnupg lsb-release software-properties-common apt-transport-https jq unzip zip tar zstd xz-utils bzip2 rsync git sudo nano vim less htop net-tools bind9-dnsutils bind9-host iproute2 iputils-ping traceroute openssh-client openssh-server"
# PINCABOS_SCRIPT_REQUIRES_COMMANDS="apt-get dpkg curl wget git rsync ssh sshd"
# PINCABOS_SCRIPT_LOG_DIR="/opt/pincabos/logs"
# PINCABOS_SCRIPT_MANIFEST="/opt/pincabos/install/install.json"

PKG_NAME="pkg-apt-base"
PKG_TITLE="APT base and core tools"
source /opt/pincabos/install/packages/pkg-lib.sh

main() {
  pkg_start
  pco_step "01" "Repair package database"
  apt_repair

  pco_step "02" "Update package metadata"
  apt_update

  pco_step "03" "Install base tools"
  apt_install_available \
    ca-certificates curl wget gnupg lsb-release software-properties-common apt-transport-https \
    jq unzip zip tar zstd xz-utils bzip2 rsync git sudo nano vim less htop \
    net-tools bind9-dnsutils bind9-host iproute2 iputils-ping traceroute openssh-client openssh-server \
    build-essential pkg-config cmake make gcc g++ nasm yasm

  pco_step "04" "Validate base tools"
  require_command curl wget git rsync ssh
  optional_command jq zstd unzip

  pkg_done
}

main "$@"
