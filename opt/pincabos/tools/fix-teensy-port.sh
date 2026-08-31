#!/bin/bash
# PinCabOs-File
# fix-teensy-port.sh — recale le <ComPortName> de CHAQUE contrôleur de strips
# (TeensyStripController / WemosD1MPStripController) dans cabinet.xml selon le
# vrai /dev/tty* de la carte : l'énumération USB peut changer à chaque boot.
#
# Multi-cartes : chaque bloc est résolu par NUMÉRO DE SÉRIE via l'inventaire
# (/opt/pincabos/config/dof/hardware-inventory.json, entrée par Name).
# Fallback : s'il n'y a qu'UN seul bloc et qu'UN seul Teensy branché, on prend
# son port. Sans matériel ou sans cabinet.xml : sortie 0, rien n'est modifié.
set -u
CFGDIR="${1:-}"
if [ -z "$CFGDIR" ]; then
  CFGDIR=$(ls -d /home/pinball/.local/share/VPinballX/*/directoutputconfig 2>/dev/null | sort -V | tail -1)
fi
CAB="$CFGDIR/cabinet.xml"
[ -f "$CAB" ] || { echo "cabinet.xml introuvable ($CAB)"; exit 0; }

python3 - "$CAB" <<'PYEOF'
import glob, json, re, subprocess, sys

cab_path = sys.argv[1]
INVENTORY = "/opt/pincabos/config/dof/hardware-inventory.json"


def udev(dev):
    try:
        out = subprocess.run(["udevadm", "info", "-q", "property", "-n", dev],
                             capture_output=True, text=True, timeout=5).stdout
    except Exception:
        return {}
    return dict(line.split("=", 1) for line in out.splitlines() if "=" in line)


ttys = {}
teensy_ports = []
for dev in sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*")):
    p = udev(dev)
    serial = p.get("ID_SERIAL_SHORT", "")
    if serial:
        ttys[serial] = dev
    if "teensy" in (p.get("ID_SERIAL", "") + p.get("ID_MODEL", "")).lower():
        teensy_ports.append(dev)

serial_by_name = {}
try:
    inv = json.load(open(INVENTORY, encoding="utf-8"))
    for d in inv.get("devices", []):
        if d.get("type") in ("TeensyStripController", "WemosD1MPStripController"):
            if d.get("label") and d.get("serial"):
                serial_by_name[d["label"]] = d["serial"]
except Exception:
    pass

src = open(cab_path, encoding="utf-8").read()
block_re = re.compile(
    r"<(TeensyStripController|WemosD1MPStripController)>.*?</\1>", re.S)
blocks = list(block_re.finditer(src))
if not blocks:
    print("aucun controleur de strips declare — rien a faire")
    sys.exit(0)

changed = False
out = []
last = 0
for m in blocks:
    block = m.group(0)
    name_m = re.search(r"<Name>([^<]*)</Name>", block)
    port_m = re.search(r"<ComPortName>([^<]*)</ComPortName>", block)
    name = name_m.group(1) if name_m else "?"
    cur = port_m.group(1) if port_m else ""
    new = None
    serial = serial_by_name.get(name)
    if serial and serial in ttys:
        new = ttys[serial]
    elif len(blocks) == 1 and len(teensy_ports) == 1:
        new = teensy_ports[0]
    if new and port_m and new != cur:
        block = block.replace("<ComPortName>%s</ComPortName>" % cur,
                              "<ComPortName>%s</ComPortName>" % new, 1)
        print("%s : %s -> %s" % (name, cur, new))
        changed = True
    elif new:
        print("%s : deja correct (%s)" % (name, cur))
    else:
        print("%s : carte introuvable (serie inconnue ?) — port %s conserve" % (name, cur))
    out.append(src[last:m.start()])
    out.append(block)
    last = m.end()
out.append(src[last:])

if changed:
    open(cab_path, "w", encoding="utf-8").write("".join(out))
    print("cabinet.xml mis a jour")
PYEOF
exit 0
