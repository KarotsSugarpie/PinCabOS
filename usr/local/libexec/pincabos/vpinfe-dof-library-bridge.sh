#!/usr/bin/env bash
set -Eeuo pipefail

OVERLAY="/opt/pincabos/overlays/vpinfe-dof-ledwiz-hidraw-stable/libdof.so.0.4.7"
INTERNAL="/home/pinball/vpinfe/_internal"

[ -f "$OVERLAY" ] || exit 1
[ -d "$INTERNAL" ] || exit 1

for NAME in libdof.so libdof.so.0 libdof.so.0.4.7; do
  rm -f "$INTERNAL/$NAME"
  ln -s "$OVERLAY" "$INTERNAL/$NAME"
done
