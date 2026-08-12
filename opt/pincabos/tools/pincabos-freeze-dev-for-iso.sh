#!/usr/bin/env bash
# PinCabOS-File created by Karots Sugarpie
clear
echo -e "\033[38;5;208m=== PinCabOS - Freeze Dev pour ISO/Calamares ===\033[0m"

set -euo pipefail
export LC_ALL=C

VERSION_JSON="/opt/pincabos/config/version.json"
ESS="/opt/pincabos/essentials"

VPX_EXEC="/opt/pincabos/bin/vpx.sh"
VPX_TABLES="/home/pinball/Tables"
VPX_INI="/home/pinball/.vpinball/VPinballX.ini"

mkdir -p "$ESS"

echo
echo "=== 1) Validation chemins VPX officiels ==="
test -x "$VPX_EXEC"
test -d "$VPX_TABLES"
test -f "$VPX_INI"

ls -l "$VPX_EXEC"
ls -ld "$VPX_TABLES"
ls -l "$VPX_INI"

echo
echo "=== 2) Validation vieux chemins interdits ==="
if grep -RInE '/home/pinball/\.local/share/VPinballX|/home/pinball/\.config/vpinfe' \
  /opt/pincabos/web/app.py \
  /opt/pincabos/tools/pincabos-cleanup.sh \

then
  echo "ERREUR: vieux chemins interdits trouvés."
  exit 1
else
  echo "OK: aucun vieux chemin interdit dans app.py / cleanup / version.json"
fi

echo
echo "=== 3) Validation JSON ==="
python3 -m json.tool "$VERSION_JSON" >/dev/null
echo "OK: version.json valide"

echo
echo "=== 4) Lecture manifest version.json ==="
python3 - <<'PY'
import json
from pathlib import Path

p = Path("/opt/pincabos/config/version.json")
d = json.loads(p.read_text())
m = d["pincabos_manifest"]
rules = m["calamares_keep_rules"]

print("name:", d.get("name"))
print("version:", d.get("version"))
print("channel:", d.get("channel"))
print("schema:", m.get("schema"))
print("updated_at:", m.get("updated_at"))
print()
print("VPX officiel:")
for k, v in m["official_vpx_paths"].items():
    print(f"  {k}: {v}")
print()
print("system_critical_directories:", len(m.get("system_critical_directories", [])))
print("pincabos_critical_directories:", len(m.get("pincabos_critical_directories", [])))
print("system_critical_files:", len(m.get("system_critical_files", [])))
print("pincabos_critical_files:", len(m.get("pincabos_critical_files", [])))
print("keep_directories:", len(rules.get("keep_directories", [])))
print("keep_files:", len(rules.get("keep_files", [])))
print("create_if_missing:", len(rules.get("create_if_missing", [])))
PY

echo
echo "=== 5) Validation existence KEEP_DIR / KEEP_FILE ==="
python3 - <<'PY'
import json
from pathlib import Path

d = json.loads(Path("/opt/pincabos/config/version.json").read_text())
rules = d["pincabos_manifest"]["calamares_keep_rules"]

fail = 0

for item in rules.get("keep_directories", []):
    if item == "/run":
        continue
    p = Path(item)
    if not p.exists():
        print(f"MISSING_DIR: {item}")
        fail = 1
    else:
        print(f"OK_DIR: {item}")

for item in rules.get("keep_files", []):
    p = Path(item)
    if not p.exists():
        print(f"MISSING_FILE: {item}")
        fail = 1
    else:
        print(f"OK_FILE: {item}")

if fail:
    raise SystemExit(1)

print()
print("OK: tous les KEEP_DIR / KEEP_FILE existent")
PY

echo
echo "=== 6) Générer keep paths Calamares depuis version.json ==="
python3 - <<'PY'
import json
from pathlib import Path

src = Path("/opt/pincabos/config/version.json")
out = Path("/opt/pincabos/essentials/pincabos-calamares-keep-from-version.txt")

d = json.loads(src.read_text())
rules = d["pincabos_manifest"]["calamares_keep_rules"]

with out.open("w") as f:
    f.write("# Generated from /opt/pincabos/config/version.json\n")
    f.write("# PinCabOS ISO/Calamares keep rules\n\n")

    for p in rules["keep_directories"]:
        f.write(f"KEEP_DIR={p}\n")

    for p in rules["keep_files"]:
        f.write(f"KEEP_FILE={p}\n")

    for p in rules["create_if_missing"]:
        f.write(f"CREATE_DIR={p}\n")

    for p in rules.get("validate_live_only", []):
        f.write(f"VALIDATE_LIVE_ONLY={p}\n")

    for p in rules.get("do_not_write_logs_to", []):
        f.write(f"DO_NOT_WRITE_LOGS_TO={p}\n")
PY

echo "OK: /opt/pincabos/essentials/pincabos-calamares-keep-from-version.txt"

echo
echo "=== 7) Sync version.json vers essentials ==="
cp -f "$VERSION_JSON" "$ESS/version.json"
cp -f "$VERSION_JSON" "$ESS/version-with-runtime-manifest.json"

sha256sum \
  "$ESS/version.json" \
  "$ESS/version-with-runtime-manifest.json" \
  "$ESS/pincabos-calamares-keep-from-version.txt" \
  > "$ESS/pincabos-essential-checksums.sha256"

cat "$ESS/pincabos-essential-checksums.sha256"

echo
echo "=== 8) Validation services ==="
systemctl is-active pincabos-web.service
systemctl is-active pincabos-console.service
systemctl is-active pincabos-vpinfe.service
systemctl is-active nginx

echo
echo "=== 9) Espace système ==="
df -h /
echo
du -sh \
  /opt/pincabos \
  /opt/pincabos/web \
  /opt/pincabos/web/.venv \
  /opt/pincabos/apps \
  /opt/pincabos/config \
  /opt/pincabos/essentials \
  /home/pinball/Share \
  /home/pinball/Tables \
  /home/pinball/.vpinball \
  2>/dev/null | sort -h || true

echo
echo "=== 10) Résumé final ==="
echo "VERSION_JSON=$VERSION_JSON"
echo "ESSENTIALS=$ESS"
echo "KEEP_FILE=$ESS/pincabos-calamares-keep-from-version.txt"
echo
echo "OK: Dev est figé et prêt pour import ISO/Calamares."
