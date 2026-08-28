#!/usr/bin/env bash
set -uo pipefail
umask 077
clear 2>/dev/null || true

EXPECTED_USER="pinball"
WORKER_URL="https://pincabos-tester-upload.pincabos.workers.dev/v1/tester-report"

say() { printf '%s\n' "$*"; }
section() {
  printf '  [SECTION] %s\n' "$1"
  printf '\n================================================================\n %s\n================================================================\n' "$1" >>"$REPORT"
}
run() {
  local title="$1"; shift
  printf '  %-38s' "$title"
  {
    printf '\n--- %s ---\n' "$title"
    if command -v timeout >/dev/null 2>&1; then
      timeout 20s "$@" 2>&1 || true
    else
      "$@" 2>&1 || true
    fi
  } >>"$REPORT"
  printf 'OK\n'
}
slugify() {
  python3 - "$1" <<'PY'
import re, sys, unicodedata
s = unicodedata.normalize('NFKD', sys.argv[1]).encode('ascii','ignore').decode('ascii').lower()
s = re.sub(r'[^a-z0-9._-]+', '-', s)
s = re.sub(r'-{2,}', '-', s).strip('._-')
print((s or 'unknown')[:64])
PY
}

if [[ "$(id -un)" != "$EXPECTED_USER" ]]; then
  say "NOGO [PROTECTION] Ce script doit etre lance comme utilisateur pinball."
  say "Utilisateur actuel : $(id -un)"
  exit 1
fi
command -v python3 >/dev/null 2>&1 || { say "NOGO [PROTECTION] python3 est requis."; exit 1; }

say "================================================================"
say " PINFORGE-SAFE - PINCABOS TESTER SYSTEM AUDIT V4"
say " CLOUDFLARE GATEWAY -> GITHUB"
say " AUCUN TOKEN SUR LE CABINET"
say "================================================================"
say

TESTER_NAME="${PINCABOS_TESTER_NAME:-}"
if [[ -z "${TESTER_NAME//[[:space:]]/}" ]]; then
  while :; do
    IFS= read -r -p "Nom du testeur : " TESTER_NAME
    TESTER_NAME="${TESTER_NAME#${TESTER_NAME%%[![:space:]]*}}"
    TESTER_NAME="${TESTER_NAME%${TESTER_NAME##*[![:space:]]}}"
    [[ -n "$TESTER_NAME" ]] && break
    say "Le nom du testeur est obligatoire."
  done
fi

TESTER_SLUG="$(slugify "$TESTER_NAME")"
HOST_NAME="$(hostname 2>/dev/null || echo PinCabOS)"
HOST_SLUG="$(slugify "$HOST_NAME")"
STAMP="$(date +%Y%m%d-%H%M%S)"
REPORT="$HOME/${TESTER_SLUG}-${HOST_SLUG}-${STAMP}-system-audit.txt"

cat >"$REPORT" <<EOF_REPORT
================================================================
 PINFORGE-SAFE - PINCABOS TESTER SYSTEM AUDIT V4
 MATERIEL + SYSTEME + CONFIGURATION
 LECTURE SEULE - USER PINBALL
 TRANSPORT CLOUDFLARE WORKER -> GITHUB
================================================================

Testeur       : $TESTER_NAME
Hostname      : $HOST_NAME
Date locale   : $(date '+%Y-%m-%d %H:%M:%S %Z')
Utilisateur   : $(id -un)
UID           : $(id -u)
Nom local     : $(basename "$REPORT")

Confidentialite :
 - aucune cle SSH
 - aucun mot de passe
 - aucun token GitHub sur le cabinet
 - aucune adresse IP
 - aucune adresse MAC
 - aucun UUID/serial machine
 - aucun git remote
EOF_REPORT

say "Rapport local : $(basename "$REPORT")"
say
say "Collecte en cours..."

section "1. SYSTEME"
run "Distribution" bash -c 'cat /etc/os-release 2>/dev/null || true'
run "Kernel" uname -srvmo
run "Architecture" uname -m
run "Uptime" uptime
run "Dernier boot" who -b
command -v systemd-detect-virt >/dev/null 2>&1 && run "Virtualisation" systemd-detect-virt
command -v mokutil >/dev/null 2>&1 && run "Secure Boot" mokutil --sb-state

section "2. MACHINE / CARTE MERE / BIOS"
{
  for f in sys_vendor product_name product_version board_vendor board_name board_version bios_vendor bios_version bios_date; do
    p="/sys/class/dmi/id/$f"
    if [[ -r "$p" ]]; then printf '%-20s : ' "$f"; cat "$p" 2>/dev/null || true; fi
  done
} >>"$REPORT"

section "3. CPU"
command -v lscpu >/dev/null 2>&1 && run "CPU complet" lscpu
{
  echo
  echo "--- CPU governor ---"
  for p in /sys/devices/system/cpu/cpu0/cpufreq/scaling_driver /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor; do
    [[ -r "$p" ]] && echo "$(basename "$p") : $(cat "$p" 2>/dev/null || true)"
  done
} >>"$REPORT"

section "4. MEMOIRE"
command -v free >/dev/null 2>&1 && run "RAM" free -h
{
  echo
  grep -E 'MemTotal|MemFree|MemAvailable|Buffers|Cached|SwapTotal|SwapFree|HugePages' /proc/meminfo 2>/dev/null || true
} >>"$REPORT"

section "5. STOCKAGE"
command -v lsblk >/dev/null 2>&1 && run "Disques / partitions" lsblk -e7 -o NAME,TYPE,SIZE,FSTYPE,FSVER,LABEL,MOUNTPOINTS,MODEL,ROTA,TRAN
command -v df >/dev/null 2>&1 && run "Utilisation filesystem" df -hT
command -v swapon >/dev/null 2>&1 && run "Swap" swapon --show
command -v findmnt >/dev/null 2>&1 && run "Montages" findmnt -rn -o TARGET,SOURCE,FSTYPE,OPTIONS

section "6. GPU / VIDEO"
{
  lspci -nnk 2>/dev/null | grep -A4 -Ei 'VGA|3D controller|Display controller' | head -n 160 || true
} >>"$REPORT"
if command -v nvidia-smi >/dev/null 2>&1; then
  run "NVIDIA GPU" nvidia-smi --query-gpu=index,name,driver_version,memory.total,temperature.gpu,pstate --format=csv,noheader
  { echo; lsmod 2>/dev/null | grep -E '^nvidia' || true; } >>"$REPORT"
fi
command -v vulkaninfo >/dev/null 2>&1 && run "Vulkan summary" vulkaninfo --summary
if command -v glxinfo >/dev/null 2>&1 && [[ -n "${DISPLAY:-}" ]]; then run "OpenGL" glxinfo -B; fi

section "7. ECRANS / CONNECTEURS"
{
  for status in /sys/class/drm/card*-*/status; do
    [[ -r "$status" ]] || continue
    connector="${status%/status}"
    state="$(cat "$status" 2>/dev/null || true)"
    echo
    echo "$(basename "$connector") : $state"
    if [[ "$state" == "connected" ]]; then
      [[ -r "$connector/modes" ]] && { echo "Modes:"; sed 's/^/  /' "$connector/modes" 2>/dev/null || true; }
      [[ -r "$connector/enabled" ]] && echo "Enabled: $(cat "$connector/enabled" 2>/dev/null || true)"
    fi
  done
  echo
  echo "DISPLAY=${DISPLAY:-}"
  echo "WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-}"
  echo "XDG_SESSION_TYPE=${XDG_SESSION_TYPE:-}"
  echo "XDG_CURRENT_DESKTOP=${XDG_CURRENT_DESKTOP:-}"
} >>"$REPORT"
if command -v xrandr >/dev/null 2>&1 && [[ -n "${DISPLAY:-}" ]]; then run "XRANDR" xrandr --query; fi

section "8. AUDIO"
{
  lspci -nnk 2>/dev/null | grep -A4 -Ei 'Audio device|Multimedia audio' | head -n 180 || true
} >>"$REPORT"
command -v aplay >/dev/null 2>&1 && run "ALSA sorties" aplay -l
command -v arecord >/dev/null 2>&1 && run "ALSA entrees" arecord -l
if command -v pactl >/dev/null 2>&1; then
  run "Pulse/PipeWire info" pactl info
  run "Audio sinks" pactl list short sinks
  run "Audio sources" pactl list short sources
fi
command -v wpctl >/dev/null 2>&1 && run "WirePlumber" wpctl status

section "9. USB"
if command -v lsusb >/dev/null 2>&1; then
  run "USB devices" lsusb
  run "USB tree" lsusb -t
fi

section "10. ENTREES / BOUTONS"
{
  awk '
    /^I: / {info=$0}
    /^N: Name=/ {print info; print $0}
    /^H: Handlers=/ {print $0; print ""}
  ' /proc/bus/input/devices 2>/dev/null | head -n 500 || true
  echo
  echo "--- Device nodes input ---"
  find /dev/input -maxdepth 1 -type c -printf '%f\n' 2>/dev/null | sort || true
} >>"$REPORT"

section "11. PCI COMPLET"
command -v lspci >/dev/null 2>&1 && run "PCI devices" lspci -nn

section "12. RESEAU - MATERIEL SEULEMENT"
{
  for p in /sys/class/net/*; do
    [[ -d "$p" ]] || continue
    n="$(basename "$p")"
    [[ "$n" == "lo" ]] && continue
    echo
    echo "Interface : $n"
    [[ -r "$p/operstate" ]] && echo "  Etat    : $(cat "$p/operstate" 2>/dev/null || true)"
    [[ -r "$p/speed" ]] && echo "  Vitesse : $(cat "$p/speed" 2>/dev/null || true) Mb/s"
    [[ -r "$p/duplex" ]] && echo "  Duplex  : $(cat "$p/duplex" 2>/dev/null || true)"
    if [[ -L "$p/device/driver" ]]; then echo "  Driver  : $(basename "$(readlink -f "$p/device/driver" 2>/dev/null || true)")"; fi
  done
} >>"$REPORT"

section "13. SERVICES PINCABOS"
{
  systemctl --no-pager --no-legend --type=service --all 2>/dev/null \
    | grep -Ei 'pincabos|vpin|visual.?pinball|dof|pinball|vpx|bgfx|full.?dmd|recorder' \
    | head -n 400 || true
  echo
  echo "--- Unit files ---"
  systemctl list-unit-files --no-pager --no-legend 2>/dev/null \
    | grep -Ei 'pincabos|vpin|visual.?pinball|dof|pinball|vpx|bgfx|full.?dmd|recorder' \
    | head -n 400 || true
} >>"$REPORT"

section "14. PROCESSUS PINCABOS"
{
  ps -eo pid,user,comm --sort=comm 2>/dev/null \
    | grep -Ei 'vpin|vpx|pincabos|dof|wine|bgfx|python|node' \
    | head -n 400 || true
} >>"$REPORT"

section "15. PINCABOS / GIT LOCAL"
{
  for p in /opt/pincabos /opt/pincabos/.git-rootfs "$HOME/vpinfe" "$HOME/vpinball" "$HOME/Tables"; do
    if [[ -e "$p" ]]; then stat -c '%A %U:%G %s %y %n' "$p" 2>/dev/null || true; else echo "ABSENT : $p"; fi
  done
  if command -v git >/dev/null 2>&1 && [[ -d /opt/pincabos/.git-rootfs ]]; then
    echo
    echo "HEAD: $(git --git-dir=/opt/pincabos/.git-rootfs --work-tree=/ rev-parse HEAD 2>/dev/null || true)"
    echo "Branch: $(git --git-dir=/opt/pincabos/.git-rootfs --work-tree=/ branch --show-current 2>/dev/null || true)"
    echo "Tracked changes count: $(git --git-dir=/opt/pincabos/.git-rootfs --work-tree=/ status --porcelain 2>/dev/null | wc -l || true)"
  fi
} >>"$REPORT"

section "16. VERSIONS PINCABOS"
{
  for f in /etc/pincabos/version /etc/pincabos/VERSION /opt/pincabos/VERSION /opt/pincabos/version.json /opt/pincabos/VERSION.json; do
    if [[ -r "$f" ]]; then echo "--- $f ---"; head -n 100 "$f" 2>/dev/null || true; fi
  done
} >>"$REPORT"

section "17. BINAIRES VPX / VPINFE"
{
  find "$HOME" /opt/pincabos -maxdepth 5 -type f \
    \( -iname 'VPinballX*' -o -iname 'vpinfe' -o -iname '*dof*' \) \
    -executable -print 2>/dev/null | sort | head -n 300 || true
  echo
  for f in "$HOME/vpinfe/vpinfe" "$HOME/vpinball/VPinballX_GL" "$HOME/vpinball/VPinballX"; do
    if [[ -f "$f" ]]; then
      stat -c '%A %U:%G %s %y %n' "$f" 2>/dev/null || true
      sha256sum "$f" 2>/dev/null || true
    fi
  done
} >>"$REPORT"

section "18. TABLES"
if [[ -d "$HOME/Tables" ]]; then
  {
    echo "Dossiers: $(find "$HOME/Tables" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l || true)"
    echo "VPX: $(find "$HOME/Tables" -type f -iname '*.vpx' 2>/dev/null | wc -l || true)"
    echo "VBS: $(find "$HOME/Tables" -type f -iname '*.vbs' 2>/dev/null | wc -l || true)"
    echo "Taille: $(du -sh "$HOME/Tables" 2>/dev/null | awk '{print $1}' || true)"
    echo
    echo "Dossiers niveau 1:"
    find "$HOME/Tables" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2>/dev/null | sort | head -n 600 || true
  } >>"$REPORT"
fi

section "19. LOGICIELS / PAQUETS"
{
  for p in bash python3 git curl wget 7z unzip ffmpeg gcc cmake; do
    if command -v "$p" >/dev/null 2>&1; then
      printf '%-12s : ' "$p"
      { "$p" --version 2>/dev/null || "$p" 2>/dev/null || true; } | head -n 1 || true
    fi
  done
  if command -v dpkg-query >/dev/null 2>&1; then
    echo
    echo "--- Paquets graphiques/audio ---"
    dpkg-query -W -f='${binary:Package}\t${Version}\n' 2>/dev/null \
      | grep -Ei 'nvidia|vulkan|mesa|xserver|xorg|wayland|pipewire|wireplumber|pulseaudio|alsa|wine|linux-image|linux-headers' \
      | sort | head -n 600 || true
  fi
} >>"$REPORT"

section "20. MODULES KERNEL"
{
  lsmod 2>/dev/null | grep -Ei 'nvidia|nouveau|snd|hid|usb|joystick|uinput|serial|ftdi|cp210|ch341|xpad' | head -n 500 || true
} >>"$REPORT"

section "21. PORTS SERIE"
{
  find /dev -maxdepth 1 \( -name 'ttyUSB*' -o -name 'ttyACM*' \) -printf '%f\n' 2>/dev/null | sort || true
} >>"$REPORT"

section "22. TEMPERATURES"
command -v sensors >/dev/null 2>&1 && run "Sensors" sensors
{
  for z in /sys/class/thermal/thermal_zone*; do
    [[ -d "$z" ]] || continue
    t="$(cat "$z/type" 2>/dev/null || true)"
    v="$(cat "$z/temp" 2>/dev/null || true)"
    if [[ "$v" =~ ^[0-9]+$ ]]; then awk -v t="$t" -v v="$v" 'BEGIN {printf "%-25s : %.1f C\n",t,v/1000}'; fi
  done
} >>"$REPORT"

section "23. RESUME"
{
  echo "Testeur      : $TESTER_NAME"
  echo "Hostname     : $HOST_NAME"
  echo "Kernel       : $(uname -r 2>/dev/null || true)"
  echo "Architecture : $(uname -m 2>/dev/null || true)"
  if command -v lscpu >/dev/null 2>&1; then echo "CPU          : $(lscpu 2>/dev/null | awk -F: '/Model name/{gsub(/^[ \t]+/,"",$2); print $2; exit}' || true)"; fi
  if command -v free >/dev/null 2>&1; then echo "RAM          : $(free -h 2>/dev/null | awk '/^Mem:/{print $2}' || true)"; fi
  if command -v nvidia-smi >/dev/null 2>&1; then
    echo "GPU          : $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | paste -sd ',' - || true)"
    echo "NVIDIA       : $(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -n1 || true)"
  fi
  echo
  echo "Audit local termine."
} >>"$REPORT"

python3 - "$REPORT" <<'PY'
import re, sys
from pathlib import Path
p = Path(sys.argv[1])
text = p.read_text(encoding='utf-8', errors='replace')
text = re.sub(r'(?i)\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b', '[MAC-REDACTED]', text)
text = re.sub(r'(?<![0-9])(?:(?:25[0-5]|2[0-4][0-9]|1?[0-9]{1,2})\.){3}(?:25[0-5]|2[0-4][0-9]|1?[0-9]{1,2})(?![0-9])', '[IP-REDACTED]', text)
for pat in (
    r'github_pat_[A-Za-z0-9_]{20,}',
    r'gh[pousr]_[A-Za-z0-9]{20,}',
    r'-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----',
):
    text = re.sub(pat, '[SECRET-REDACTED]', text)
text = re.sub(r'(?im)^(\s*(?:token|password|passwd|secret|api[_-]?key)\s*[:=]\s*).*$', r'\1[SECRET-REDACTED]', text)
p.write_text(text, encoding='utf-8')
PY

REPORT_SHA="$(sha256sum "$REPORT" | awk '{print $1}')"

say
say "Collecte terminee."
say "Envoi via passerelle Cloudflare en cours..."

set +e
UPLOAD_OUTPUT="$(python3 - "$REPORT" "$REPORT_SHA" "$TESTER_NAME" "$HOST_NAME" "$WORKER_URL" <<'PY'
import base64, gzip, hashlib, json, os, stat, sys, urllib.error, urllib.request
from pathlib import Path

report_path = Path(sys.argv[1]).resolve()
report_sha = sys.argv[2]
tester_name = sys.argv[3]
host_name = sys.argv[4]
worker_url = sys.argv[5]
home = Path.home().resolve()

def fail(message):
    print('UPLOAD_ERROR=' + message)
    raise SystemExit(1)

if report_path.parent != home or not report_path.is_file():
    fail('invalid_report_path')
st = report_path.stat()
if st.st_uid != os.getuid() or st.st_size < 256 or st.st_size > 512 * 1024 or st.st_mode & stat.S_IWOTH:
    fail('unsafe_report_file')
report = report_path.read_bytes()
if hashlib.sha256(report).hexdigest() != report_sha:
    fail('report_hash_mismatch')
compressed = gzip.compress(report, compresslevel=9, mtime=0)
encoded = base64.b64encode(compressed).decode('ascii')
payload = {
    'schema_version': 4,
    'tester_name': tester_name,
    'host_name': host_name,
    'report_sha256': report_sha,
    'compression': 'gzip',
    'encoding': 'base64',
    'encoded_length': len(encoded),
    'payload': encoded,
}
raw = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
req = urllib.request.Request(
    worker_url,
    data=raw,
    method='POST',
    headers={
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'User-Agent': 'PinCabOS-Tester-System-Audit/4',
    },
)
try:
    with urllib.request.urlopen(req, timeout=90) as response:
        body = response.read().decode('utf-8', errors='replace')
        data = json.loads(body) if body else {}
except urllib.error.HTTPError as exc:
    detail = exc.read().decode('utf-8', errors='replace')[:500]
    fail('worker_http_' + str(exc.code) + ':' + detail)
except urllib.error.URLError as exc:
    fail('worker_unreachable:' + str(exc.reason))
except Exception as exc:
    fail(type(exc).__name__ + ':' + str(exc))
if not data.get('ok'):
    fail('worker_rejected:' + str(data.get('error') or 'unknown'))
print('UPLOAD_OK=1')
print('ISSUE_NUMBER=' + str(data.get('issue_number') or ''))
print('ISSUE_URL=' + str(data.get('issue_url') or ''))
PY
)"
UPLOAD_RC=$?
set -e

say
if [[ $UPLOAD_RC -eq 0 ]] && grep -q '^UPLOAD_OK=1$' <<<"$UPLOAD_OUTPUT"; then
  ISSUE_NUMBER="$(sed -n 's/^ISSUE_NUMBER=//p' <<<"$UPLOAD_OUTPUT" | head -n1)"
  ISSUE_URL="$(sed -n 's/^ISSUE_URL=//p' <<<"$UPLOAD_OUTPUT" | head -n1)"
  say "================================================================"
  say " GO [OK] RAPPORT TRANSMIS"
  say "================================================================"
  say "Testeur : $TESTER_NAME"
  say "Host    : $HOST_NAME"
  [[ -n "$ISSUE_NUMBER" ]] && say "Issue   : #$ISSUE_NUMBER"
  [[ -n "$ISSUE_URL" ]] && say "URL     : $ISSUE_URL"
  say "Cible   : GitHub DEV/config-testeur/"
  say "Copie locale : $REPORT"
  say "Aucun token GitHub n'est stocke sur ce cabinet."
  say "================================================================"
  exit 0
fi

ERROR="$(sed -n 's/^UPLOAD_ERROR=//p' <<<"$UPLOAD_OUTPUT" | head -n1)"
say "================================================================"
say " NOGO [ENVOI] RAPPORT NON TRANSMIS"
say "================================================================"
say "Erreur : ${ERROR:-inconnue}"
say "Rapport local conserve : $REPORT"
say "================================================================"
exit 2