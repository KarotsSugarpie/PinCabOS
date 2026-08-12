#!/usr/bin/env bash
# PinCabOS-File created by Karots Sugarpie
set -e

mkdir -p /opt/pincabos/logs
LOG="/opt/pincabos/logs/exit-firstboot-safe-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1

echo "=== PinCabOS - Exit FirstBoot Safe / Mode Jeux ==="
date

rm -f /opt/pincabos/config/frontend-hold-firstboot.flag
rm -f /opt/pincabos/config/iso-firstboot-safe.flag
touch /opt/pincabos/config/iso-firstboot-safe.done

python3 - <<'PY'
import json, datetime
from pathlib import Path

p = Path("/opt/pincabos/config/pincabos-admin-mode.json")
p.parent.mkdir(parents=True, exist_ok=True)
data = {
    "mode": "game",
    "description": "Mode jeux restauré depuis pincabos-exit-firstboot-safe.sh",
    "set_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "iso_flag": False,
    "frontend_hold": False
}
p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY

systemctl enable pincabos-vpinfe.service 2>/dev/null || true
systemctl restart pincabos-web.service 2>/dev/null || true
systemctl restart nginx 2>/dev/null || true
systemctl restart pincabos-vpinfe.service 2>/dev/null || true

echo "Safe mode désactivé. Mode jeux restauré."
echo "Log: $LOG"
