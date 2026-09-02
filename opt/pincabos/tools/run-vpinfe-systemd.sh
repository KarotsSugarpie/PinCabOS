#!/usr/bin/env bash
set -Eeuo pipefail

exec /usr/sbin/runuser -u pinball -- /usr/bin/env -u LD_PRELOAD \
  HOME=/home/pinball \
  USER=pinball \
  LOGNAME=pinball \
  PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  DISPLAY=:0 \
  XAUTHORITY=/home/pinball/.Xauthority \
  XDG_RUNTIME_DIR=/run/user/1000 \
  DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus \
  LD_LIBRARY_PATH=/opt/pincabos/overlays/vpinfe-dof-ledwiz-hidraw-stable \
  VPINFE_DOF_DIR=/opt/pincabos/overlays/vpinfe-dof-ledwiz-hidraw-stable \
  LIBDOF_LEDWIZ_HIDAPI_LIBUSB=/usr/lib/x86_64-linux-gnu/libhidapi-libusb.so.0 \
  /home/pinball/vpinfe/vpinfe
