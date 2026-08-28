#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
clear 2>/dev/null || true

EXPECTED_USER="pinball"
API_URL="https://pincabos.cc/api/device/tester-report"

say() { printf '%s\n' "$*"; }
slugify() {
  python3 - "$1" <<'PY'
import re, sys, unicodedata
s = unicodedata.normalize('NFKD', sys.argv[1]).encode('ascii','ignore').decode('ascii').lower()
s = re.sub(r'[^a-z0-9._-]+', '-', s)
s = re.sub(r'-{2,}', '-', s).strip('._-')
print((s or 'testeur')[:64])
PY
}
section() {
  printf '\n================================================================\n %s\n================================================================\n' "$1" >>"$REPORT"
}
run() {
  local title="$1"; shift
  printf '  %-36s' "$title"
  {
    printf '\n--- %s ---\n' "$title"
    timeout 20s "$@" 2>&1 || true
  } >>"$REPORT"
  printf 'OK\n'
}

if [[ "$(id -un)" != "$EXPECTED_USER" ]]; then
  say "NOGO [PROTECTION] Ce script doit etre lance comme utilisateur pinball."
  say "Utilisateur actuel : $(id -un)"
  exit 1
fi

command -v python3 >/dev/null 2>&1 || { say "NOGO [PROTECTION] python3 est requis."; exit 1; }
command -v sudo >/dev/null 2>&1 || { say "NOGO [PROTECTION] sudo est requis."; exit 1; }

say "================================================================"
say " PINFORGE-SAFE - PINCABOS TESTER SYSTEM AUDIT V2"
say "================================================================"
say
while :; do
  read -r -p "Nom du testeur : " TESTER_NAME
  TESTER_NAME="${TESTER_NAME#${TESTER_NAME%%[![:space:]]*}}"
  TESTER_NAME="${TESTER_NAME%${TESTER_NAME##*[![:space:]]}}"
  [[ -n "$TESTER_NAME" ]] && break
  say "Le nom du testeur est obligatoire."
done

TESTER_SLUG="$(slugify "$TESTER_NAME")"
HOST_NAME="$(hostname 2>/dev/null || echo pincabos)"
HOST_SLUG="$(slugify "$HOST_NAME")"
STAMP="$(date +%Y%m%d-%H%M%S)"
REPORT="$HOME/${TESTER_SLUG}-${HOST_SLUG}-${STAMP}-system-audit.txt"

cat >"$REPORT" <<EOF_HEADER
================================================================
 PINFORGE-SAFE - PINCABOS TESTER SYSTEM AUDIT V2
 MATERIEL + SYSTEME + CONFIGURATION
 LECTURE SEULE - USER PINBALL
 RAPPORT DESTINE A DEV/config-testeur
================================================================

Testeur       : $TESTER_NAME
Hostname      : $HOST_NAME
Date locale   : $(date '+%Y-%m-%d %H:%M:%S %Z')
Utilisateur   : $(id -un)
UID           : $(id -u)
Nom du fichier: $(basename "$REPORT")

Confidentialite :
 - aucune cle SSH
 - aucun mot de passe
 - aucun token
 - aucune adresse IP
 - aucune adresse MAC
 - aucun UUID/serial machine
 - aucun git remote
EOF_HEADER

say
say "Rapport : $(basename "$REPORT")"
say "Collecte en cours..."

section "1. SYSTEME"
run "Distribution" bash -c 'cat /etc/os-release 2>/dev/null || true'
run "Kernel" uname -srvmo
run "Architecture" uname -m
run "Uptime" uptime
run "Dernier boot" who -b
run "Virtualisation" systemd-detect-virt
command -v mokutil >/dev/null 2>&1 && run "Secure Boot" mokutil --sb-state
{
  echo
  echo "--- Kernel cmdline ---"
  cat /proc/cmdline 2>/dev/null || true
} >>"$REPORT"

section "2. MACHINE / CARTE MERE / BIOS"
{
  for f in sys_vendor product_name product_version board_vendor board_name board_version bios_vendor bios_version bios_date; do
    p="/sys/class/dmi/id/$f"
    if [[ -r "$p" ]]; then printf '%-20s : ' "$f"; cat "$p"; fi
  done
  echo "NOTE : serials et UUID DMI volontairement exclus."
} >>"$REPORT"

section "3. CPU"
run "CPU complet" lscpu
{
  echo
  echo "--- CPU governor / driver ---"
  for p in /sys/devices/system/cpu/cpu0/cpufreq/scaling_driver /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor; do
    [[ -r "$p" ]] && echo "$(basename "$p") : $(cat "$p")"
  done
} >>"$REPORT"

section "4. MEMOIRE"
run "RAM" free -h
{
  echo
  echo "--- Meminfo resume ---"
  grep -E 'MemTotal|MemFree|MemAvailable|Buffers|Cached|SwapTotal|SwapFree|HugePages' /proc/meminfo 2>/dev/null || true
} >>"$REPORT"

section "5. STOCKAGE"
command -v lsblk >/dev/null 2>&1 && run "Disques / partitions" lsblk -e7 -o NAME,TYPE,SIZE,FSTYPE,FSVER,LABEL,MOUNTPOINTS,MODEL,ROTA,TRAN
run "Utilisation filesystem" df -hT
command -v swapon >/dev/null 2>&1 && run "Swap" swapon --show
if command -v findmnt >/dev/null 2>&1; then
  {
    echo
    echo "--- Montages principaux ---"
    findmnt -rn -o TARGET,SOURCE,FSTYPE,OPTIONS 2>/dev/null | head -n 200 || true
  } >>"$REPORT"
fi

section "6. GPU / VIDEO"
if command -v lspci >/dev/null 2>&1; then
  {
    echo "--- GPU PCI + drivers ---"
    lspci -nnk 2>/dev/null | grep -A4 -Ei 'VGA|3D controller|Display controller' | head -n 120 || true
  } >>"$REPORT"
fi
if command -v nvidia-smi >/dev/null 2>&1; then
  run "NVIDIA GPU" nvidia-smi --query-gpu=index,name,driver_version,memory.total,temperature.gpu,pstate --format=csv,noheader
  {
    echo
    echo "--- Modules NVIDIA ---"
    lsmod 2>/dev/null | grep -E '^nvidia' || true
  } >>"$REPORT"
fi
command -v vulkaninfo >/dev/null 2>&1 && run "Vulkan summary" vulkaninfo --summary
if command -v glxinfo >/dev/null 2>&1 && [[ -n "${DISPLAY:-}" ]]; then run "OpenGL" glxinfo -B; fi

section "7. ECRANS / CONNECTEURS"
{
  echo "--- DRM connecteurs ---"
  for status in /sys/class/drm/card*-*/status; do
    [[ -r "$status" ]] || continue
    connector="${status%/status}"
    state="$(cat "$status" 2>/dev/null || true)"
    echo
    echo "$(basename "$connector") : $state"
    if [[ "$state" == "connected" ]]; then
      if [[ -r "$connector/modes" ]]; then echo "Modes:"; sed 's/^/  /' "$connector/modes"; fi
      [[ -r "$connector/enabled" ]] && echo "Enabled: $(cat "$connector/enabled")"
    fi
  done
  echo
  echo "--- Session graphique ---"
  echo "DISPLAY=${DISPLAY:-}"
  echo "WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-}"
  echo "XDG_SESSION_TYPE=${XDG_SESSION_TYPE:-}"
  echo "XDG_CURRENT_DESKTOP=${XDG_CURRENT_DESKTOP:-}"
} >>"$REPORT"
if command -v xrandr >/dev/null 2>&1 && [[ -n "${DISPLAY:-}" ]]; then run "XRANDR" xrandr --query; fi

section "8. AUDIO"
if command -v lspci >/dev/null 2>&1; then
  {
    echo "--- Audio PCI ---"
    lspci -nnk 2>/dev/null | grep -A4 -Ei 'Audio device|Multimedia audio' | head -n 160 || true
  } >>"$REPORT"
fi
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
  echo "--- Input devices ---"
  grep -E '^(I:|N: Name=|H: Handlers=)' /proc/bus/input/devices 2>/dev/null | head -n 500 || true
  echo
  echo "--- Device nodes ---"
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
    [[ -r "$p/operstate" ]] && echo "  Etat    : $(cat "$p/operstate")"
    [[ -r "$p/speed" ]] && echo "  Vitesse : $(cat "$p/speed" 2>/dev/null || true) Mb/s"
    [[ -r "$p/duplex" ]] && echo "  Duplex  : $(cat "$p/duplex" 2>/dev/null || true)"
    if [[ -L "$p/device/driver" ]]; then echo "  Driver  : $(basename "$(readlink -f "$p/device/driver")")"; fi
  done
  echo
  echo "NOTE : IP et MAC volontairement exclues."
} >>"$REPORT"

section "13. SERVICES PINCABOS"
{
  echo "--- Services ---"
  systemctl --no-pager --no-legend --type=service --all 2>/dev/null | grep -Ei 'pincabos|vpin|visual.?pinball|dof|pinball|vpx|bgfx|full.?dmd|recorder' | head -n 300 || true
  echo
  echo "--- Unit files ---"
  systemctl list-unit-files --no-pager --no-legend 2>/dev/null | grep -Ei 'pincabos|vpin|visual.?pinball|dof|pinball|vpx|bgfx|full.?dmd|recorder' | head -n 300 || true
} >>"$REPORT"

section "14. PROCESSUS PINCABOS"
{
  ps -eo pid,user,comm --sort=comm 2>/dev/null | grep -Ei 'vpin|vpx|pincabos|dof|wine|bgfx|python|node' | head -n 300 || true
} >>"$REPORT"

section "15. PINCABOS / GIT LOCAL"
{
  echo "--- Repertoires principaux ---"
  for p in /opt/pincabos /opt/pincabos/.git-rootfs "$HOME/vpinfe" "$HOME/vpinball" "$HOME/Tables"; do
    if [[ -e "$p" ]]; then stat -c '%A %U:%G %s %y %n' "$p" 2>/dev/null || true; else echo "ABSENT : $p"; fi
  done
  if command -v git >/dev/null 2>&1 && [[ -d /opt/pincabos/.git-rootfs ]]; then
    echo
    echo "--- Git ---"
    echo "HEAD: $(git --git-dir=/opt/pincabos/.git-rootfs --work-tree=/ rev-parse HEAD 2>/dev/null || true)"
    echo "Branch: $(git --git-dir=/opt/pincabos/.git-rootfs --work-tree=/ branch --show-current 2>/dev/null || true)"
    echo "Tracked changes count: $(git --git-dir=/opt/pincabos/.git-rootfs --work-tree=/ status --porcelain 2>/dev/null | wc -l)"
    echo "Remote: volontairement exclu"
  fi
} >>"$REPORT"

section "16. VERSIONS PINCABOS"
{
  for f in /etc/pincabos/version /etc/pincabos/VERSION /opt/pincabos/VERSION /opt/pincabos/version.json /opt/pincabos/VERSION.json; do
    if [[ -r "$f" ]]; then echo "--- $f ---"; head -n 80 "$f"; fi
  done
} >>"$REPORT"

section "17. BINAIRES VPX / VPINFE"
{
  echo "--- Executables pertinents ---"
  find "$HOME" /opt/pincabos -maxdepth 5 -type f \( -iname 'VPinballX*' -o -iname 'vpinfe' -o -iname '*dof*' \) -executable -print 2>/dev/null | sort | head -n 200 || true
  echo
  echo "--- Hashes connus ---"
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
    echo "Dossiers : $(find "$HOME/Tables" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)"
    echo "VPX      : $(find "$HOME/Tables" -type f -iname '*.vpx' 2>/dev/null | wc -l)"
    echo "VBS      : $(find "$HOME/Tables" -type f -iname '*.vbs' 2>/dev/null | wc -l)"
    echo "Taille   : $(du -sh "$HOME/Tables" 2>/dev/null | awk '{print $1}')"
    echo
    echo "--- Dossiers niveau 1 ---"
    find "$HOME/Tables" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2>/dev/null | sort | head -n 500 || true
  } >>"$REPORT"
fi

section "19. LOGICIELS / PAQUETS"
{
  echo "--- Versions outils ---"
  for p in bash python3 git curl wget 7z unzip ffmpeg gcc cmake; do
    if command -v "$p" >/dev/null 2>&1; then printf '%-12s : ' "$p"; "$p" --version 2>/dev/null | head -n 1; fi
  done
  if command -v dpkg-query >/dev/null 2>&1; then
    echo
    echo "--- Paquets graphiques/audio ---"
    dpkg-query -W -f='${binary:Package}\t${Version}\n' 2>/dev/null | grep -Ei 'nvidia|vulkan|mesa|xserver|xorg|wayland|pipewire|wireplumber|pulseaudio|alsa|wine|linux-image|linux-headers' | sort | head -n 500 || true
  fi
} >>"$REPORT"

section "20. MODULES KERNEL"
{
  lsmod 2>/dev/null | grep -Ei 'nvidia|nouveau|snd|hid|usb|joystick|uinput|serial|ftdi|cp210|ch341|xpad' | head -n 400 || true
} >>"$REPORT"

section "21. PORTS SERIE"
{
  find /dev -maxdepth 1 \( -name 'ttyUSB*' -o -name 'ttyACM*' \) -printf '%f\n' 2>/dev/null | sort || true
} >>"$REPORT"

section "22. TEMPERATURES"
command -v sensors >/dev/null 2>&1 && run "Sensors" sensors
{
  echo
  echo "--- Thermal zones ---"
  for z in /sys/class/thermal/thermal_zone*; do
    [[ -d "$z" ]] || continue
    t="$(cat "$z/type" 2>/dev/null || true)"
    v="$(cat "$z/temp" 2>/dev/null || true)"
    if [[ "$v" =~ ^[0-9]+$ ]]; then awk -v t="$t" -v v="$v" 'BEGIN { printf "%-25s : %.1f C\n", t, v/1000 }'; fi
  done
} >>"$REPORT"

section "23. RESUME"
{
  echo "Testeur      : $TESTER_NAME"
  echo "Hostname     : $HOST_NAME"
  echo "Kernel       : $(uname -r 2>/dev/null)"
  echo "Architecture : $(uname -m 2>/dev/null)"
  if command -v lscpu >/dev/null 2>&1; then echo "CPU          : $(lscpu 2>/dev/null | awk -F: '/Model name/{gsub(/^[ \t]+/,"",$2); print $2; exit}')"; fi
  echo "RAM          : $(free -h 2>/dev/null | awk '/^Mem:/{print $2}')"
  if command -v nvidia-smi >/dev/null 2>&1; then
    echo "GPU          : $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | paste -sd ',' -)"
    echo "NVIDIA       : $(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -n1)"
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
    r'(?i)PinCabOS-Device\s+[A-Za-z0-9._~+/=-]{20,}',
    r'-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----',
):
    text = re.sub(pat, '[SECRET-REDACTED]', text)
text = re.sub(r'(?im)^(\s*(?:token|password|passwd|secret|api[_-]?key)\s*[:=]\s*).*$', r'\1[SECRET-REDACTED]', text)
p.write_text(text, encoding='utf-8')
PY

REPORT_SHA="$(sha256sum "$REPORT" | awk '{print $1}')"
say
say "Collecte terminee."
say "Envoi securise vers pincabos.cc..."

set +e
UPLOAD_OUTPUT="$(sudo -n python3 - "$REPORT" "$REPORT_SHA" "$TESTER_NAME" "$HOST_NAME" <<'PY'
import hashlib, json, os, pwd, ssl, stat, sys, urllib.error, urllib.request
from pathlib import Path
report_path = Path(sys.argv[1]).resolve()
report_sha = sys.argv[2]
tester_name = sys.argv[3]
host_name = sys.argv[4]
home = Path('/home/pinball').resolve()
state_dir = Path('/var/lib/pincabos-link')
state_file = state_dir / 'device.json'
def fail(msg):
    print('UPLOAD_ERROR=' + msg)
    raise SystemExit(1)
if os.geteuid() != 0:
    fail('root_helper_required')
try:
    pinball_uid = pwd.getpwnam('pinball').pw_uid
except KeyError:
    fail('pinball_user_missing')
if report_path.parent != home or not report_path.is_file():
    fail('invalid_report_path')
st = report_path.stat()
if st.st_uid != pinball_uid or st.st_size < 256 or st.st_size > 512 * 1024 or st.st_mode & stat.S_IWOTH:
    fail('unsafe_report_file')
try:
    ds = state_dir.stat()
    fs = state_file.stat()
except OSError:
    fail('cabinet_not_linked')
if ds.st_uid != 0 or ds.st_gid != 0 or stat.S_IMODE(ds.st_mode) != 0o700:
    fail('unsafe_link_state_directory')
if fs.st_uid != 0 or fs.st_gid != 0 or stat.S_IMODE(fs.st_mode) != 0o600:
    fail('unsafe_link_state_file')
try:
    state = json.loads(state_file.read_text(encoding='utf-8'))
except Exception:
    fail('invalid_link_state')
if str(state.get('api_base') or '').rstrip('/') != 'https://pincabos.cc':
    fail('unexpected_api_base')
if str(state.get('token_type') or '') != 'PinCabOS-Device':
    fail('unexpected_token_type')
token = str(state.get('device_token') or '').strip()
if not 32 <= len(token) <= 256:
    fail('device_token_missing')
report = report_path.read_text(encoding='utf-8', errors='replace')
if hashlib.sha256(report.encode()).hexdigest() != report_sha:
    fail('report_hash_mismatch')
body = json.dumps({
    'schema_version': 2,
    'client_version': '2.0',
    'tester_name': tester_name,
    'host_name': host_name,
    'report': report,
    'report_sha256': report_sha,
}, ensure_ascii=False, separators=(',', ':')).encode()
ctx = ssl.create_default_context()
if hasattr(ssl, 'TLSVersion'):
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
req = urllib.request.Request(
    'https://pincabos.cc/api/device/tester-report',
    data=body,
    method='POST',
    headers={
        'Accept': 'application/json',
        'Authorization': 'PinCabOS-Device ' + token,
        'Content-Type': 'application/json; charset=utf-8',
        'User-Agent': 'PinCabOS-Tester-System-Audit/2.0',
    },
)
try:
    with urllib.request.urlopen(req, timeout=45, context=ctx) as response:
        payload = json.loads(response.read().decode('utf-8', errors='replace'))
except urllib.error.HTTPError as exc:
    try:
        reason = str(json.loads(exc.read().decode('utf-8', errors='replace')).get('error') or ('http_' + str(exc.code)))
    except Exception:
        reason = 'http_' + str(exc.code)
    fail(reason)
except Exception:
    fail('server_unreachable')
if not isinstance(payload, dict) or payload.get('ok') is not True:
    fail(str((payload or {}).get('error') or 'invalid_server_response'))
print('UPLOAD_OK=1')
print('GITHUB_PATH=' + str(payload.get('path') or ''))
print('COMMIT_SHA=' + str(payload.get('commit_sha') or ''))
PY
)"
UPLOAD_RC=$?
set -e

say
if [[ $UPLOAD_RC -eq 0 ]] && grep -q '^UPLOAD_OK=1$' <<<"$UPLOAD_OUTPUT"; then
  GITHUB_PATH="$(sed -n 's/^GITHUB_PATH=//p' <<<"$UPLOAD_OUTPUT" | head -n1)"
  COMMIT_SHA="$(sed -n 's/^COMMIT_SHA=//p' <<<"$UPLOAD_OUTPUT" | head -n1)"
  say "================================================================"
  say " GO [OK] RAPPORT ENVOYE AUTOMATIQUEMENT"
  say "================================================================"
  say "Testeur : $TESTER_NAME"
  say "Host    : $HOST_NAME"
  say "GitHub  : ${GITHUB_PATH:-DEV/config-testeur/}"
  [[ -n "$COMMIT_SHA" ]] && say "Commit  : $COMMIT_SHA"
  say "Le testeur n'a rien d'autre a faire."
  say "Copie locale de secours : $REPORT"
  say "================================================================"
  exit 0
fi

ERROR="$(sed -n 's/^UPLOAD_ERROR=//p' <<<"$UPLOAD_OUTPUT" | head -n1)"
say "================================================================"
say " NOGO [ENVOI] RAPPORT NON ENVOYE"
say "================================================================"
say "Erreur : ${ERROR:-inconnue}"
say "Rapport local conserve : $REPORT"
say "Aucun token n'a ete affiche."
say "================================================================"
exit 2
