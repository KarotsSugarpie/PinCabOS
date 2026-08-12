#!/usr/bin/env bash
set -Eeuo pipefail
clear

RELEASE_DIR="${1:-}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SSH_TARGET="${SSH_TARGET:-root@192.168.254.55}"
WEB_ROOT="${WEB_ROOT:-/var/www/html/updates}"

green=$'\033[1;32m'; red=$'\033[1;31m'; reset=$'\033[0m'
go(){ printf '%sGO [√]%s %s\n' "$green" "$reset" "$*"; }
fail(){ printf '%sERREUR%s %s\n' "$red" "$reset" "$*" >&2; exit 1; }

[[ -d "$RELEASE_DIR" ]] || fail "Usage: sudo publish-update.sh /chemin/release"
for f in pincabos-update.tar.zst files.list release.json audit.sha256; do
  [[ -f "$RELEASE_DIR/$f" ]] || fail "Fichier absent: $RELEASE_DIR/$f"
done

CLIENT_DIR="${CLIENT_DIR:-$SCRIPT_DIR/client}"
if [[ ! -f "$CLIENT_DIR/getpcos" && -f /opt/pincabos/update/client/getpcos ]]; then
  CLIENT_DIR="/opt/pincabos/update/client"
fi
[[ -f "$CLIENT_DIR/getpcos" ]] || fail "Client absent: $CLIENT_DIR/getpcos"
[[ -f "$CLIENT_DIR/install-getpcos.sh" ]] || fail "Installateur absent: $CLIENT_DIR/install-getpcos.sh"

(
  cd "$RELEASE_DIR"
  sha256sum -c audit.sha256
)
bash -n "$CLIENT_DIR/getpcos"
bash -n "$CLIENT_DIR/install-getpcos.sh"

VERSION="$(python3 - "$RELEASE_DIR/release.json" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as f:
    print(json.load(f)["version"])
PY
)"
CHANNEL="$(python3 - "$RELEASE_DIR/release.json" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as f:
    print(json.load(f)["channel"])
PY
)"
ARCHIVE_SHA="$(sha256sum "$RELEASE_DIR/pincabos-update.tar.zst" | awk '{print $1}')"
PUBLISHED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
TMP_LOCAL="$(mktemp -d)"
trap 'rm -rf "$TMP_LOCAL"' EXIT

cat > "$TMP_LOCAL/latest.json" <<EOF
{
  "schema": 1,
  "version": "$VERSION",
  "channel": "$CHANNEL",
  "archive": "releases/$VERSION/pincabos-update.tar.zst",
  "sha256": "$ARCHIVE_SHA",
  "files": "releases/$VERSION/files.list",
  "release": "releases/$VERSION/release.json",
  "published_at": "$PUBLISHED_AT"
}
EOF

cp "$CLIENT_DIR/getpcos" "$TMP_LOCAL/getpcos"
sha256sum "$TMP_LOCAL/getpcos" | sed 's#  .*/#  #' > "$TMP_LOCAL/getpcos.sha256"
cp "$CLIENT_DIR/install-getpcos.sh" "$TMP_LOCAL/install-getpcos.sh"

REMOTE_STAGE="$WEB_ROOT/.publish-$VERSION-$$"

ssh "$SSH_TARGET" "set -e; mkdir -p '$REMOTE_STAGE/release' '$WEB_ROOT/releases' '$WEB_ROOT/channels/$CHANNEL'"
scp -q \
  "$RELEASE_DIR/pincabos-update.tar.zst" \
  "$RELEASE_DIR/files.list" \
  "$RELEASE_DIR/release.json" \
  "$RELEASE_DIR/audit.sha256" \
  "$SSH_TARGET:$REMOTE_STAGE/release/"
scp -q \
  "$TMP_LOCAL/latest.json" \
  "$TMP_LOCAL/getpcos" \
  "$TMP_LOCAL/getpcos.sha256" \
  "$TMP_LOCAL/install-getpcos.sh" \
  "$SSH_TARGET:$REMOTE_STAGE/"

ssh "$SSH_TARGET" "set -Eeuo pipefail
  cd '$REMOTE_STAGE/release'
  sha256sum -c audit.sha256
  chmod 0644 pincabos-update.tar.zst files.list release.json audit.sha256
  chmod 0755 '$REMOTE_STAGE/getpcos' '$REMOTE_STAGE/install-getpcos.sh'
  chmod 0644 '$REMOTE_STAGE/getpcos.sha256' '$REMOTE_STAGE/latest.json'
  rm -rf '$WEB_ROOT/releases/$VERSION'
  mv '$REMOTE_STAGE/release' '$WEB_ROOT/releases/$VERSION'
  mv '$REMOTE_STAGE/latest.json' '$WEB_ROOT/channels/$CHANNEL/latest.json'
  mv '$REMOTE_STAGE/getpcos' '$WEB_ROOT/getpcos'
  mv '$REMOTE_STAGE/getpcos.sha256' '$WEB_ROOT/getpcos.sha256'
  mv '$REMOTE_STAGE/install-getpcos.sh' '$WEB_ROOT/install-getpcos.sh'
  rmdir '$REMOTE_STAGE'
"

go "Release publiée: https://pincabos.cc/updates/releases/$VERSION/"
go "Canal mis à jour: https://pincabos.cc/updates/channels/$CHANNEL/latest.json"
go "Commande utilisateur: sudo getpcos update"
