#!/usr/bin/env bash
set -Eeuo pipefail

INI="/home/pinball/.config/vpinfe/vpinfe.ini"
LOG="/tmp/pincabos-vpinfe-launcher.log"

log() {
    printf '%s %s\n' \
        "$(date '+%Y-%m-%d %H:%M:%S')" \
        "$*" >> "$LOG"
}

[[ -f "$INI" ]] || {
    log "NOGO config absente: $INI"
    echo "PinCabOS: configuration VPinFE absente." >&2
    exit 20
}

VPX_EXECUTABLE="$(
python3 - "$INI" <<'PY'
from pathlib import Path
import json
import re
import sys

path = Path(sys.argv[1])
text = path.read_text(
    encoding="utf-8",
    errors="ignore",
)

def clean(value):
    return (
        str(value)
        .strip()
        .rstrip(",")
        .strip()
        .strip('"')
        .strip("'")
    )

values = []

patterns = (
    r'(?im)^\s*VPX\s+Executable\s+Path\s*[:=]\s*(.+?)\s*$',
    r'(?im)^\s*VPXExecutablePath\s*[:=]\s*(.+?)\s*$',
    r'(?im)^\s*vpx_executable_path\s*[:=]\s*(.+?)\s*$',
    r'(?im)^\s*vpxExecutablePath\s*[:=]\s*(.+?)\s*$',
    r'(?im)^\s*VPXPath\s*[:=]\s*(.+?)\s*$',
    r'(?im)^\s*vpx_path\s*[:=]\s*(.+?)\s*$',
    r'(?im)^\s*vpxPath\s*[:=]\s*(.+?)\s*$',
    r'(?im)["\'](?:VPX Executable Path|VPXExecutablePath|'
    r'vpx_executable_path|vpxExecutablePath|VPXPath|'
    r'vpx_path|vpxPath)["\']\s*:\s*["\']([^"\']+)["\']',
)

for pattern in patterns:
    for match in re.finditer(pattern, text):
        values.append(clean(match.group(1)))

try:
    data = json.loads(text)

    def walk(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                normalized = re.sub(
                    r'[^a-z0-9]',
                    '',
                    str(key).lower(),
                )

                if (
                    'vpx' in normalized
                    and (
                        'executable' in normalized
                        or 'path' in normalized
                        or 'launcher' in normalized
                    )
                    and isinstance(value, str)
                ):
                    values.append(clean(value))

                walk(value)

        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)

except Exception:
    pass

for match in re.finditer(
    r'(?i)(/[\w ./()_\-]+/'
    r'vpx(?:-[\w.-]+)?\.sh)',
    text,
):
    values.append(clean(match.group(1)))

seen = set()

for value in values:
    if not value or value in seen:
        continue

    seen.add(value)

    candidate = Path(value)

    if candidate.is_file() and candidate.stat().st_mode & 0o111:
        print(value)
        raise SystemExit(0)

raise SystemExit(1)
PY
)" || true

if [[ -z "$VPX_EXECUTABLE" ]]; then
    log "NOGO aucune valeur launcher dans $INI"
    echo "PinCabOS: launcher VPX VPinFE introuvable." >&2
    exit 21
fi

if [[ "$VPX_EXECUTABLE" == "$0" ]]; then
    log "NOGO boucle récursive"
    exit 22
fi

if [[ ! -x "$VPX_EXECUTABLE" ]]; then
    log "NOGO non exécutable: $VPX_EXECUTABLE"
    exit 23
fi

log "GO launcher=$VPX_EXECUTABLE args=$*"

exec "$VPX_EXECUTABLE" "$@"
