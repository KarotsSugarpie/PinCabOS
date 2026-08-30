#!/bin/bash
# fix-teensy-port.sh — fixe le <ComPortName> du TeensyStripController (backboard HD)
# dans cabinet.xml selon le vrai /dev/ttyACM* du Teensy (le numero peut changer a
# chaque reboot selon l'ordre d'enumeration USB). Lance en ExecStartPre de vpinfe.
set -u
CFGDIR="${1:-}"
if [ -z "$CFGDIR" ]; then
  CFGDIR=$(ls -d /home/pinball/.local/share/VPinballX/*/directoutputconfig 2>/dev/null | sort -V | tail -1)
fi
CAB="$CFGDIR/cabinet.xml"
[ -f "$CAB" ] || { echo "cabinet.xml introuvable ($CAB)"; exit 0; }

PORT=""
for d in /dev/ttyACM*; do
  [ -e "$d" ] || continue
  if udevadm info -q property -n "$d" 2>/dev/null | grep -qi "Teensyduino"; then
    PORT="$d"; break
  fi
done
[ -z "$PORT" ] && { echo "Teensy (backboard) absent de /dev/ttyACM* — cabinet.xml inchange"; exit 0; }

CUR=$(grep -oE "<ComPortName>[^<]*</ComPortName>" "$CAB" | head -1 | sed -E "s#</?ComPortName>##g")
if [ "$CUR" = "$PORT" ]; then echo "cabinet.xml deja correct: $PORT"; exit 0; fi
sed -i "s#<ComPortName>[^<]*</ComPortName>#<ComPortName>$PORT</ComPortName>#" "$CAB"
echo "Teensy backboard: $CUR -> $PORT (cabinet.xml mis a jour)"
