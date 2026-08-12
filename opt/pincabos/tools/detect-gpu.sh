#!/bin/bash
# PinCabOS-File created by Karots Sugarpie
set -Eeuo pipefail

echo "=================================================="
echo " PinCabOS - Détection GPU universelle"
echo " Date: $(date)"
echo "=================================================="
echo

GPU_LINES="$(lspci -Dnn 2>/dev/null | grep -Ei 'VGA compatible controller|3D controller|Display controller' || true)"

echo "[Résumé GPU PCI]"
if [ -n "$GPU_LINES" ]; then
  echo "$GPU_LINES"
else
  echo "Aucun GPU PCI détecté par lspci."
fi
echo

echo "[Classification PinCabOS]"
FOUND=0

if echo "$GPU_LINES" | grep -Eqi '\[10de:'; then
  echo "Famille détectée: NVIDIA [10de]"
  FOUND=1
fi

if echo "$GPU_LINES" | grep -Eqi '\[(1002|1022):'; then
  echo "Famille détectée: AMD / ATI [1002/1022]"
  FOUND=1
fi

if echo "$GPU_LINES" | grep -Eqi '\[8086:'; then
  echo "Famille détectée: Intel [8086]"
  FOUND=1
fi

if echo "$GPU_LINES" | grep -Eqi '\[1af4:'; then
  echo "Famille détectée: Virtio / VM [1af4]"
  FOUND=1
fi

if [ "$FOUND" = "0" ]; then
  echo "Famille détectée: inconnue/autre"
fi
echo

echo "[Détails GPU PCI + kernel driver]"
lspci -Dnnk 2>/dev/null | awk '
BEGIN { keep=0 }
/VGA compatible controller|3D controller|Display controller/ { keep=1; print; next }
keep && /^[[:space:]]/ { print; next }
keep && !/^[[:space:]]/ { keep=0 }
' || true
echo

echo "[Modules GPU chargés]"
lsmod | grep -Ei "nvidia|amdgpu|radeon|i915|xe|nouveau|virtio_gpu|qxl|vmwgfx" || true
echo

echo "[DRM devices]"
ls -lah /dev/dri 2>/dev/null || true
echo

echo "[OpenGL]"
if command -v glxinfo >/dev/null 2>&1; then
  glxinfo -B 2>/dev/null || true
else
  echo "glxinfo non installé"
fi
echo

echo "[Vulkan]"
if command -v vulkaninfo >/dev/null 2>&1; then
  vulkaninfo --summary 2>/dev/null || true
else
  echo "vulkaninfo non installé"
fi
echo

echo "[Écrans XRandR]"
DISPLAY="${DISPLAY:-:0}" XAUTHORITY="${XAUTHORITY:-/home/pinball/.Xauthority}" xrandr --query 2>/dev/null || true
