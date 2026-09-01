#!/usr/bin/env bash
set -Eeuo pipefail

# PINCABOS_SYNC_SHIM_V3
#
# Historiquement, ce script reecrivait lui-meme les sections [PinCabOs.*] et
# [Displays] de vpinfe.ini / VPinballX.ini a partir des JSON de calibration —
# en parallele de la topologie ecran, qui ecrivait les memes sections avec
# d'autres valeurs (trois ecrivains au total avec la WebApp : incoherences et
# valeurs perimees garanties).
#
# Il ne reste qu'un point d'entree stable (les appels sudo de la WebApp et le
# sudoers existants pointent ici) : la topologie est desormais l'UNIQUE
# ecrivain, elle relit les JSON de calibration et ecrit tout en une passe
# atomique, sous le meme verrou que le boot.

exec /usr/bin/flock -w 15 /run/pincabos-screen-topology.lock \
    /opt/pincabos/scripts/pincabos-screen-topology.py --prepare
