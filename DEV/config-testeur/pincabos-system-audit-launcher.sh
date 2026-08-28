#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
clear 2>/dev/null || true

EXPECTED_USER="pinball"
TOKEN_FILE="/etc/pincabos/tester-report-issues.token"
RAW_AUDIT="https://raw.githubusercontent.com/KarotsSugarpie/PinCabOS/main/DEV/config-testeur/pincabos-system-audit.sh"
WORK_DIR="$HOME/.cache/pincabos-tester-report"
AUDIT_SCRIPT="$WORK_DIR/pincabos-system-audit.sh"
RUNNER="$WORK_DIR/pincabos-system-audit-runner.sh"
STAMP="$(date +%Y%m%d-%H%M%S)"
LOG_FILE="$WORK_DIR/audit-$STAMP.log"
STATUS_FILE="$WORK_DIR/audit-$STAMP.status"

say(){ printf '%s\n' "$*"; }

if [[ "$(id -un)" != "$EXPECTED_USER" ]]; then
  say "NOGO [PROTECTION] Ce lanceur doit etre execute comme utilisateur pinball."
  exit 1
fi
command -v curl >/dev/null 2>&1 || { say "NOGO [PROTECTION] curl absent."; exit 1; }
command -v bash >/dev/null 2>&1 || { say "NOGO [PROTECTION] bash absent."; exit 1; }
command -v sudo >/dev/null 2>&1 || { say "NOGO [PROTECTION] sudo absent."; exit 1; }
command -v nohup >/dev/null 2>&1 || { say "NOGO [PROTECTION] nohup absent."; exit 1; }
if ! sudo -n true >/dev/null 2>&1; then
  say "NOGO [PROTECTION] sudo NOPASSWD PinCabOS indisponible."
  exit 1
fi

TOKEN_META="$(sudo -n stat -c '%u:%g:%a' "$TOKEN_FILE" 2>/dev/null || true)"
if [[ "$TOKEN_META" != "0:0:600" ]]; then
  say "NOGO [PROTECTION] Credential GitHub absent ou permissions incorrectes."
  say "Attendu : $TOKEN_FILE en root:root 0600"
  say "Le token doit etre installe une seule fois sur ce PinCabOS."
  exit 1
fi

say "================================================================"
say " PINFORGE-SAFE - PINCABOS TESTER SYSTEM AUDIT V3.2"
say " MODE RESILIENT SSH - GITHUB ONLY"
say " CREDENTIAL PERSISTANT"
say "================================================================"
say
while :; do
  IFS= read -r -p "Nom du testeur : " TESTER_NAME
  TESTER_NAME="${TESTER_NAME#${TESTER_NAME%%[![:space:]]*}}"
  TESTER_NAME="${TESTER_NAME%${TESTER_NAME##*[![:space:]]}}"
  [[ -n "$TESTER_NAME" ]] && break
  say "Le nom du testeur est obligatoire."
done

mkdir -p "$WORK_DIR"
chmod 700 "$WORK_DIR"
TMP_SCRIPT="$WORK_DIR/.audit-$STAMP.tmp"
curl -fsSL "$RAW_AUDIT" -o "$TMP_SCRIPT"
bash -n "$TMP_SCRIPT"
mv -f "$TMP_SCRIPT" "$AUDIT_SCRIPT"
chmod 700 "$AUDIT_SCRIPT"

cat > "$RUNNER" <<'RUNNER_EOF'
#!/usr/bin/env bash
set +e
umask 077
printf '%s\n' "$PINCABOS_TESTER_NAME" | bash "$PINCABOS_AUDIT_SCRIPT"
RC=$?
printf '%s\n' "$RC" > "$PINCABOS_STATUS_FILE"
exit "$RC"
RUNNER_EOF
chmod 700 "$RUNNER"
rm -f "$STATUS_FILE"

PINCABOS_TESTER_NAME="$TESTER_NAME" \
PINCABOS_AUDIT_SCRIPT="$AUDIT_SCRIPT" \
PINCABOS_STATUS_FILE="$STATUS_FILE" \
nohup "$RUNNER" >"$LOG_FILE" 2>&1 </dev/null &
PID=$!

say
say "GO [OK] Audit lance en tache detachee."
say "PID     : $PID"
say "Journal : $LOG_FILE"
say "Credential GitHub : conserve dans $TOKEN_FILE"
say "SSH peut maintenant se couper sans interrompre l'audit."
say
say "Suivi en direct :"
say "----------------------------------------------------------------"

tail --pid="$PID" -n +1 -f "$LOG_FILE" 2>/dev/null || true

say "----------------------------------------------------------------"
if [[ -f "$STATUS_FILE" ]]; then
  RC="$(cat "$STATUS_FILE" 2>/dev/null || echo 1)"
  if [[ "$RC" == "0" ]]; then
    say "GO [OK] Audit termine et transmis."
  else
    say "NOGO [AUDIT] Le job a termine avec le code $RC."
  fi
else
  say "INFO Le suivi SSH s'est termine avant le job. Le job detache continue."
fi
say "Journal conserve : $LOG_FILE"
