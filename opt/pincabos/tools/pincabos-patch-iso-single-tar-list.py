#!/usr/bin/env python3
"""Patch ciblé du builder ISO PinCabOS pour ne lister le gros payload TAR qu'une fois.

Ce script ne touche jamais au VPX actif, BGFX ni VPinFE. Il modifie uniquement
/opt/pincabos/script/iso.sh (ou le chemin fourni en argument), crée un backup,
valide la syntaxe Bash et restaure automatiquement en cas d'échec.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import os
import shutil
import subprocess
import sys

MARKER = "PINCABOS_PAYLOAD_SINGLE_TAR_LIST_V1"
DEFAULT = Path("/opt/pincabos/script/iso.sh")


def fail(message: str) -> None:
    raise SystemExit(f"NOGO [X] {message}")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        fail(f"bloc {label}: attendu 1 occurrence, trouvé {count}")
    return text.replace(old, new, 1)


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    if not path.is_file():
        fail(f"iso.sh introuvable: {path}")

    original = path.read_text(encoding="utf-8", errors="strict")
    if MARKER in original:
        print("GO [OK] Correctif single TAR list déjà présent.")
        return 0

    text = original

    text = replace_once(
        text,
        'echo "--- TAR stream readability test ---"\n'
        'tar -I zstd -tf "$ARCHIVE" >/dev/null\n',
        'echo "--- TAR stream readability + reusable payload index ---"\n'
        f'echo "{MARKER}"\n'
        'ARCHIVE_LIST_PYWEB="$WORK/payload-file-list-python-webapp.txt"\n'
        'echo "Creating payload file list once:"\n'
        'echo "$ARCHIVE_LIST_PYWEB"\n'
        'tar --checkpoint=250000 \\\n'
        "  --checkpoint-action=echo='validated %u entries...' \\\n"
        '  -I zstd -tf "$ARCHIVE" > "$ARCHIVE_LIST_PYWEB"\n'
        '[ -s "$ARCHIVE_LIST_PYWEB" ] || die "Payload TAR file list is empty"\n'
        'echo "GO [OK] TAR stream readable; payload index cached"\n',
        "readability",
    )

    text = replace_once(
        text,
        'AUDIO_PRIVACY_FOUND="$(\n'
        '  tar -I zstd -tf "$ARCHIVE" |\n'
        '  grep -E "$AUDIO_PRIVACY_FORBIDDEN_RE" ||\n'
        '  true\n'
        ')"',
        'AUDIO_PRIVACY_FOUND="$(\n'
        '  grep -E "$AUDIO_PRIVACY_FORBIDDEN_RE" "$ARCHIVE_LIST_PYWEB" ||\n'
        '  true\n'
        ')"',
        "audio privacy list",
    )

    text = replace_once(
        text,
        'done < <(\n'
        '  tar -I zstd -tf "$ARCHIVE" |\n'
        "  grep -E '/VPinballX\\.ini$' ||\n"
        '  true\n'
        ')',
        'done < <(\n'
        "  grep -E '/VPinballX\\.ini$' \"$ARCHIVE_LIST_PYWEB\" ||\n"
        '  true\n'
        ')',
        "VPX ini list",
    )

    section7_old = '''echo "=== 7) Validate payload exclusions and boot contents ==="
tar -I zstd -tf "$ARCHIVE" \\
  | grep -E '^./boot/(vmlinuz|initrd.img|grub)|^./lib/modules/' \\
  | sed -n '1,120p'

if tar -I zstd -tf "$ARCHIVE" | grep -q '^./home/pinball/Tables/'; then
  die "Tables included in payload"
fi
echo "OK: Tables excluded"

if tar -I zstd -tf "$ARCHIVE" | grep -q '^./opt/pincabos/build/'; then
  die "/opt/pincabos/build included in payload"
fi
echo "OK: /opt/pincabos/build excluded"


# PINCABOS_PAYLOAD_TRANSIENT_VALIDATION_V1
echo "=== Validation fichiers transitoires exclus ==="

if tar -I zstd -tf "$ARCHIVE" | grep -E -q \\
'^\\./opt/pincabos/(\\.git-rootfs(/|$)|backups(/|$)|script/.*\\.(bak|before)-|web/.*\\.(bak|before)-)'
then
    die "Fichiers transitoires PinCabOS inclus dans le payload"
fi

echo "OK: .git-rootfs excluded"
echo "OK: /opt/pincabos/backups excluded"
echo "OK: script/web backups excluded"


if tar -I zstd -tf "$ARCHIVE" | grep -Eq '^\\./swap\\.img$|^\\./swapfile$'; then
  echo "Bad swap entries:"
  tar -I zstd -tf "$ARCHIVE" | grep -E '^\\./swap\\.img$|^\\./swapfile$' | sed -n '1,80p'
  die "swap included in payload"
fi
echo "OK: swap excluded"

if tar -I zstd -tf "$ARCHIVE" | grep -Eq '/(venv|\\.venv|virtualenv)(/|$)'; then
  echo "NOTICE: venv/virtualenv entries present in payload; allowed for WebApp runtime"
  tar -I zstd -tf "$ARCHIVE" | grep -E '/(venv|\\.venv|virtualenv)(/|$)' | sed -n '1,80p'
else
  echo "NOTICE: no venv/virtualenv entries found; WebApp must use system Python or fallback"
fi

if tar -I zstd -tf "$ARCHIVE" | grep -q '^./root/pincabos-v8'; then
  die "old /root payload included"
fi
echo "OK: old root payloads excluded"
'''

    section7_new = '''echo "=== 7) Validate payload exclusions and boot contents ==="
grep -E '^./boot/(vmlinuz|initrd.img|grub)|^./lib/modules/' "$ARCHIVE_LIST_PYWEB" \\
  | sed -n '1,120p'

if grep -q '^./home/pinball/Tables/' "$ARCHIVE_LIST_PYWEB"; then
  die "Tables included in payload"
fi
echo "OK: Tables excluded"

if grep -q '^./opt/pincabos/build/' "$ARCHIVE_LIST_PYWEB"; then
  die "/opt/pincabos/build included in payload"
fi
echo "OK: /opt/pincabos/build excluded"


# PINCABOS_PAYLOAD_TRANSIENT_VALIDATION_V1
echo "=== Validation fichiers transitoires exclus ==="

if grep -E -q \\
'^\\./opt/pincabos/(\\.git-rootfs(/|$)|backups(/|$)|script/.*\\.(bak|before)-|web/.*\\.(bak|before)-)' \\
"$ARCHIVE_LIST_PYWEB"
then
    die "Fichiers transitoires PinCabOS inclus dans le payload"
fi

echo "OK: .git-rootfs excluded"
echo "OK: /opt/pincabos/backups excluded"
echo "OK: script/web backups excluded"


if grep -Eq '^\\./swap\\.img$|^\\./swapfile$' "$ARCHIVE_LIST_PYWEB"; then
  echo "Bad swap entries:"
  grep -E '^\\./swap\\.img$|^\\./swapfile$' "$ARCHIVE_LIST_PYWEB" | sed -n '1,80p'
  die "swap included in payload"
fi
echo "OK: swap excluded"

if grep -Eq '/(venv|\\.venv|virtualenv)(/|$)' "$ARCHIVE_LIST_PYWEB"; then
  echo "NOTICE: venv/virtualenv entries present in payload; allowed for WebApp runtime"
  grep -E '/(venv|\\.venv|virtualenv)(/|$)' "$ARCHIVE_LIST_PYWEB" | sed -n '1,80p'
else
  echo "NOTICE: no venv/virtualenv entries found; WebApp must use system Python or fallback"
fi

if grep -q '^./root/pincabos-v8' "$ARCHIVE_LIST_PYWEB"; then
  die "old /root payload included"
fi
echo "OK: old root payloads excluded"
'''

    text = replace_once(text, section7_old, section7_new, "section 7 scans")

    text = replace_once(
        text,
        'ARCHIVE_LIST_PYWEB="$WORK/payload-file-list-python-webapp.txt"\n'
        'echo "Creating payload file list:"\n'
        'echo "$ARCHIVE_LIST_PYWEB"\n'
        'tar -I zstd -tf "$ARCHIVE" > "$ARCHIVE_LIST_PYWEB"\n',
        'echo "Reusing cached payload file list:"\n'
        'echo "$ARCHIVE_LIST_PYWEB"\n'
        '[ -s "$ARCHIVE_LIST_PYWEB" ] || die "Cached payload file list missing"\n',
        "python webapp list reuse",
    )

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.name}.before-single-tar-list-{stamp}")
    shutil.copy2(path, backup)

    tmp = path.with_name(f".{path.name}.single-tar-list.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.chmod(tmp, path.stat().st_mode & 0o7777)

    syntax = subprocess.run(
        ["bash", "-n", str(tmp)],
        text=True,
        capture_output=True,
    )
    if syntax.returncode != 0:
        tmp.unlink(missing_ok=True)
        print(syntax.stderr, file=sys.stderr)
        fail("syntaxe Bash invalide; iso.sh original conservé")

    os.replace(tmp, path)

    final = path.read_text(encoding="utf-8")
    if MARKER not in final:
        shutil.copy2(backup, path)
        fail("marker final absent; rollback effectué")

    print(f"GO [OK] iso.sh corrigé: {path}")
    print(f"GO [OK] backup: {backup}")
    print("GO [OK] un seul inventaire TAR sera créé puis réutilisé.")
    print("GO [OK] VPX / BGFX / VPinFE non touchés.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
