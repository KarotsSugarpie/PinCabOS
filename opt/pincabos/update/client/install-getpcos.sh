#!/usr/bin/env bash
set -Eeuo pipefail

REPO_BASE="https://pincabos.cc/updates"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

[[ ${EUID:-$(id -u)} -eq 0 ]] || {
  echo "ERREUR: lance cette commande avec sudo." >&2
  exit 1
}

for cmd in curl sha256sum install; do
  command -v "$cmd" >/dev/null 2>&1 || {
    echo "ERREUR: commande absente: $cmd" >&2
    exit 1
  }
done

curl -fL --retry 3 "$REPO_BASE/getpcos" -o "$TMP/getpcos"
curl -fL --retry 3 "$REPO_BASE/getpcos.sha256" -o "$TMP/getpcos.sha256"

(
  cd "$TMP"
  sha256sum -c getpcos.sha256
)

install -d -m 0755 /etc/pincabos
cat > /etc/pincabos/getpcos.conf <<'EOF'
REPO_BASE="https://pincabos.cc/updates"
CHANNEL="beta"
EOF
chmod 0644 /etc/pincabos/getpcos.conf

install -m 0755 "$TMP/getpcos" /usr/local/sbin/getpcos
ln -sfn /usr/local/sbin/getpcos /usr/local/bin/getpcos

echo "GO [√] getpcos installé."
echo "Commande de mise à jour: sudo getpcos update"
