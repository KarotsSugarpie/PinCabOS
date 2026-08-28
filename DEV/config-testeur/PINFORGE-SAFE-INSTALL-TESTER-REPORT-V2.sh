#!/usr/bin/env bash
clear
set -Eeuo pipefail
umask 077

APP="/opt/pincabos-release-center/app.py"
MOD="/opt/pincabos-release-center/pincabos_tester_report_v1.py"
PUB="/usr/local/sbin/pincabos-tester-report-publisher"
SERVICE="pincabos-release-center.service"
PATH_UNIT="/etc/systemd/system/pincabos-tester-report.path"
PUB_UNIT="/etc/systemd/system/pincabos-tester-report.service"
SPOOL="/var/lib/pincabos-release/tester-reports"
RAW_BASE="https://raw.githubusercontent.com/KarotsSugarpie/PinCabOS/main/DEV/config-testeur"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="/opt/pincabos-release-center/backups/tester-report-v2-$STAMP"

ok(){ echo "GO [OK] $*"; }
nogo(){ echo "NOGO [ERREUR] $*" >&2; exit 1; }

[[ "$(id -u)" -eq 0 ]] || nogo "Lance ce script en root."
HOST="$(hostname)"
case "${HOST,,}" in
  pincabos.cc|pincabos-feedback) ;;
  *) nogo "Serveur inattendu : $HOST" ;;
esac
[[ -f "$APP" ]] || nogo "Backend canonique absent : $APP"
command -v curl >/dev/null 2>&1 || nogo "curl absent"
command -v python3 >/dev/null 2>&1 || nogo "python3 absent"
command -v gh >/dev/null 2>&1 || nogo "GitHub CLI gh absent"
gh auth status -h github.com >/dev/null 2>&1 || nogo "GitHub CLI root non authentifie"
PERM="$(gh repo view KarotsSugarpie/PinCabOS --json viewerPermission --jq '.viewerPermission' 2>/dev/null || true)"
case "$PERM" in ADMIN|MAINTAIN|WRITE) ;; *) nogo "Permission GitHub insuffisante : ${PERM:-inconnue}" ;; esac

mkdir -p "$BACKUP"
cp -a "$APP" "$BACKUP/app.py.before"
[[ -f "$MOD" ]] && cp -a "$MOD" "$BACKUP/pincabos_tester_report_v1.py.before" || true
[[ -f "$PUB" ]] && cp -a "$PUB" "$BACKUP/publisher.before" || true
[[ -f "$PATH_UNIT" ]] && cp -a "$PATH_UNIT" "$BACKUP/path-unit.before" || true
[[ -f "$PUB_UNIT" ]] && cp -a "$PUB_UNIT" "$BACKUP/service-unit.before" || true
ok "Backup cree : $BACKUP"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
curl -fsSL "$RAW_BASE/pincabos_tester_report_v1.py" -o "$TMP/module.py"
curl -fsSL "$RAW_BASE/pincabos-tester-report-publisher.py" -o "$TMP/publisher.py"
python3 -m py_compile "$TMP/module.py" "$TMP/publisher.py"
ok "Sources GitHub valides"

install -m 0644 -o root -g root "$TMP/module.py" "$MOD"
install -m 0755 -o root -g root "$TMP/publisher.py" "$PUB"
install -d -m 0750 -o www-data -g www-data "$SPOOL/incoming"
install -d -m 0750 -o root -g root "$SPOOL/sent" "$SPOOL/failed"

python3 - "$APP" <<'PY'
import ast, re, sys
from pathlib import Path
p=Path(sys.argv[1]); text=p.read_text(encoding='utf-8')
start='# PINCABOS_TESTER_REPORT_V1_REGISTER_START'
end='# PINCABOS_TESTER_REPORT_V1_REGISTER_END'
block=("\n"+start+"\n"
       "from pincabos_tester_report_v1 import register_tester_report_v1 as _register_pincabos_tester_report_v1\n"
       "_register_pincabos_tester_report_v1(app, db)\n"
       +end+"\n")
if start not in text:
    pat=re.compile(r'^([ \t]*)_register_pincabos_device_presence_v1\(app,\s*db\)\s*$', re.M)
    m=pat.search(text)
    if not m:
        raise SystemExit('NOGO: registration device presence introuvable')
    text=text[:m.end()]+block+text[m.end():]
ast.parse(text, filename=str(p))
p.write_text(text, encoding='utf-8')
PY
python3 -m py_compile "$APP" "$MOD"
ok "Backend enregistre proprement"

cat >"$PUB_UNIT" <<EOF_UNIT
[Unit]
Description=PinCabOS Tester Report GitHub Publisher
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=root
Group=root
Environment=HOME=/root
Environment=GH_PROMPT_DISABLED=1
ExecStart=$PUB
Nice=10
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=$SPOOL

EOF_UNIT

cat >"$PATH_UNIT" <<EOF_PATH
[Unit]
Description=Watch PinCabOS Tester Reports

[Path]
PathExistsGlob=$SPOOL/incoming/*.txt
Unit=pincabos-tester-report.service

[Install]
WantedBy=multi-user.target
EOF_PATH

systemctl daemon-reload
systemctl enable --now pincabos-tester-report.path >/dev/null
systemctl restart "$SERVICE"
systemctl is-active --quiet "$SERVICE" || nogo "Release Center inactif"
systemctl is-active --quiet pincabos-tester-report.path || nogo "Watcher inactif"

HTTP="$(curl -sS -o "$TMP/test.json" -w '%{http_code}' -X POST -H 'Content-Type: application/json' --data '{}' https://pincabos.cc/api/device/tester-report || true)"
echo "HTTP endpoint sans auth : $HTTP"
[[ "$HTTP" == "401" ]] || nogo "Endpoint tester-report non joignable correctement"

ok "Endpoint actif"
ok "Publisher root GitHub actif"
echo
echo "==============================================================="
echo " PINFORGE-SAFE - TESTER REPORT V2 DEPLOYE"
echo "==============================================================="
echo "Route  : https://pincabos.cc/api/device/tester-report"
echo "GitHub : DEV/config-testeur/"
echo "Secret GitHub dans le webapp : NON"
echo "Publication GitHub via root gh : OUI"
echo "==============================================================="
