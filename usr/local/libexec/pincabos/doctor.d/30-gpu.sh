pco_section "GPU / VULKAN"

gpu_line=""
if pco_has_cmd lspci; then
  gpu_line="$(lspci -nn | grep -Ei 'VGA|3D controller|Display controller' | head -1 || true)"
fi

if [ -n "$gpu_line" ]; then
  pco_go "GPU détecté" "$gpu_line"
else
  pco_warn "GPU détecté" "aucun contrôleur trouvé par lspci"
fi

if [ "$PCO_FIRSTBOOT" -eq 1 ] && pco_repairing && pco_service_exists pincabos-firstboot-hardware-autoconfig.service; then
  if ! pco_service_active pincabos-firstboot-hardware-autoconfig.service; then
    systemctl start pincabos-firstboot-hardware-autoconfig.service || true
  fi
fi

if echo "$gpu_line" | grep -qi nvidia; then
  if pco_has_cmd nvidia-smi && nvidia-smi -L >/dev/null 2>&1; then
    pco_go "Pilote NVIDIA" "$(nvidia-smi --query-gpu=name,driver_version --format=csv,noheader | head -1)"
  else
    pco_fail "Pilote NVIDIA" "nvidia-smi indisponible ou pilote non chargé"
  fi
elif echo "$gpu_line" | grep -Eqi 'AMD|ATI'; then
  if lsmod | grep -q '^amdgpu'; then
    pco_go "Pilote AMD" "amdgpu chargé"
  else
    pco_warn "Pilote AMD" "module amdgpu non détecté"
  fi
elif echo "$gpu_line" | grep -qi intel; then
  if lsmod | grep -Eq '^(i915|xe)'; then
    pco_go "Pilote Intel" "module graphique chargé"
  else
    pco_warn "Pilote Intel" "module i915/xe non détecté"
  fi
else
  pco_warn "Pilote GPU" "GPU virtuel ou fournisseur non classé"
fi

if [ -e /dev/dri/renderD128 ] || compgen -G '/dev/dri/renderD*' >/dev/null; then
  pco_go "Accès DRM" "render node présent"
else
  pco_warn "Accès DRM" "aucun /dev/dri/renderD*"
fi

if pco_has_cmd vulkaninfo; then
  if pco_as_pinball env XDG_RUNTIME_DIR=/run/user/"$(id -u pinball)" vulkaninfo --summary >/tmp/pincabos-vulkan-summary.txt 2>&1; then
    vk_device="$(grep -m1 -E 'deviceName|GPU id' /tmp/pincabos-vulkan-summary.txt | sed 's/^[[:space:]]*//' || true)"
    pco_go "Vulkan" "${vk_device:-vulkaninfo réussi}"
  else
    pco_warn "Vulkan" "vulkaninfo a échoué"
  fi
else
  pco_warn "Vulkan" "vulkaninfo absent"
fi
