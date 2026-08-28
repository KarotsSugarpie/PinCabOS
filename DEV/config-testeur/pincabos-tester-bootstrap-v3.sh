#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
clear 2>/dev/null || true

TOKEN_B64="${PINCABOS_ISSUES_TOKEN_B64:-}"
TOKEN_FILE="/etc/pincabos/tester-report-issues.token"
AUDIT_URL="https://raw.githubusercontent.com/KarotsSugarpie/PinCabOS/main/DEV/config-testeur/pincabos-system-audit.sh"

fail() { echo "NOGO [ERREUR] $*" >&2; exit 1; }
ok() { echo "GO [OK] $*"; }

[[ "$(id -un)" == "pinball" ]] || fail "Lance comme utilisateur pinball."
command -v base64 >/dev/null 2>&1 || fail "base64 absent"
command -v curl >/dev/null 2>&1 || fail "curl absent"
command -v sudo >/dev/null 2>&1 || fail "sudo absent"
sudo -n true >/dev/null 2>&1 || fail "sudo NOPASSWD PinCabOS indisponible"
[[ -n "$TOKEN_B64" ]] || fail "Credential d'upload absent"

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
printf '%s' "$TOKEN_B64" | base64 -d >"$TMP" 2>/dev/null || fail "Credential encode invalide"
printf '\n' >>"$TMP"
TOKEN="$(tr -d '\r\n' <"$TMP")"
[[ "$TOKEN" == github_pat_* ]] || fail "Un token GitHub fine-grained dedie est requis"
[[ ${#TOKEN} -ge 40 && ${#TOKEN} -le 512 ]] || fail "Longueur du token invalide"

HTTP="$(curl -sS -o /dev/null -w '%{http_code}' \
  -H 'Accept: application/vnd.github+json' \
  -H "Authorization: Bearer $TOKEN" \
  -H 'X-GitHub-Api-Version: 2022-11-28' \
  https://api.github.com/repos/KarotsSugarpie/PinCabOS || true)"
[[ "$HTTP" == "200" ]] || fail "Credential GitHub refuse (HTTP ${HTTP:-000})"

sudo -n install -d -m 0755 -o root -g root /etc/pincabos
sudo -n install -m 0600 -o root -g root "$TMP" "$TOKEN_FILE"
unset TOKEN TOKEN_B64 PINCABOS_ISSUES_TOKEN_B64
ok "Credential d'upload GitHub installe en root:root 0600"

echo
echo "Lancement de l'audit PinCabOS V3..."
echo
exec bash <(curl -fsSL "$AUDIT_URL")
