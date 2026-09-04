#!/usr/bin/env python3
"""Exclut /opt/pincabos/tmp du payload ISO PinCabOS.

Correctif ciblé après le test cabinet du 2026-09-04 : un ancien worktree de PR
sous /opt/pincabos/tmp contenait un VPinballX.ini avec des noms de périphériques
audio. Ce répertoire est du temporaire/dev et ne doit jamais entrer dans une ISO.

Le script ne touche jamais VPX, BGFX ni VPinFE. Il modifie uniquement iso.sh,
crée un backup, valide la syntaxe Bash et restaure automatiquement en cas
d'échec. S'il est lancé par pinball, il se relance automatiquement via sudo.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import os
import shutil
import subprocess
import sys

DEFAULT = Path("/opt/pincabos/script/iso.sh")
EXCLUDE_DIR = "  --exclude='./opt/pincabos/tmp' \\\n"
EXCLUDE_CONTENT = "  --exclude='./opt/pincabos/tmp/*' \\\n"


def fail(message: str) -> None:
    raise SystemExit(f"NOGO [X] {message}")


def ensure_root() -> None:
    if os.geteuid() == 0:
        return

    print("INFO: droits root requis pour modifier /opt/pincabos/script/iso.sh")
    print("INFO: relance automatique avec sudo...")

    script = str(Path(__file__).resolve())
    argv = ["sudo", sys.executable, script, *sys.argv[1:]]

    try:
        os.execvp("sudo", argv)
    except FileNotFoundError:
        fail("sudo introuvable; relancer ce patch en root")


def main() -> int:
    ensure_root()

    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT

    if not path.is_file():
        fail(f"iso.sh introuvable: {path}")

    original = path.read_text(encoding="utf-8", errors="strict")
    text = original
    changed = False

    # 1) Exclusion TAR du répertoire temporaire complet.
    if EXCLUDE_DIR not in text or EXCLUDE_CONTENT not in text:
        anchor = "  --exclude='./opt/pincabos/build/*' \\\n"
        if text.count(anchor) != 1:
            fail(
                "ancre d'exclusion /opt/pincabos/build/* absente ou non unique "
                f"({text.count(anchor)} occurrence(s))"
            )

        text = text.replace(
            anchor,
            anchor + EXCLUDE_DIR + EXCLUDE_CONTENT,
            1,
        )
        changed = True

    # 2) La validation des fichiers transitoires doit également refuser tmp
    #    si une future régression retire l'exclusion TAR.
    old_regex = (
        r"'^\./opt/pincabos/(\.git-rootfs(/|$)|backups(/|$)|"
        r"script/.*\.(bak|before)-|web/.*\.(bak|before)-)'"
    )
    new_regex = (
        r"'^\./opt/pincabos/(\.git-rootfs(/|$)|backups(/|$)|tmp(/|$)|"
        r"script/.*\.(bak|before)-|web/.*\.(bak|before)-)'"
    )

    if new_regex not in text:
        if text.count(old_regex) != 1:
            fail(
                "regex de validation transitoire absente ou non unique "
                f"({text.count(old_regex)} occurrence(s))"
            )
        text = text.replace(old_regex, new_regex, 1)
        changed = True

    # 3) Message explicite dans le log de validation.
    tmp_ok = 'echo "OK: /opt/pincabos/tmp excluded"\n'
    if tmp_ok not in text:
        echo_anchor = 'echo "OK: /opt/pincabos/backups excluded"\n'
        if text.count(echo_anchor) != 1:
            fail(
                "ancre de message backups absente ou non unique "
                f"({text.count(echo_anchor)} occurrence(s))"
            )
        text = text.replace(
            echo_anchor,
            echo_anchor + tmp_ok,
            1,
        )
        changed = True

    if not changed:
        print("GO [OK] Exclusion /opt/pincabos/tmp déjà présente.")
        print("GO [OK] VPX / BGFX / VPinFE non touchés.")
        return 0

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.name}.before-exclude-pincabos-tmp-{stamp}")
    shutil.copy2(path, backup)

    tmp = path.with_name(f".{path.name}.exclude-pincabos-tmp.tmp")
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

    final = path.read_text(encoding="utf-8", errors="strict")

    required = (
        "--exclude='./opt/pincabos/tmp'",
        "--exclude='./opt/pincabos/tmp/*'",
        "tmp(/|$)",
        'OK: /opt/pincabos/tmp excluded',
    )

    missing = [item for item in required if item not in final]
    if missing:
        shutil.copy2(backup, path)
        fail(f"validation finale échouée; rollback effectué: {missing}")

    print(f"GO [OK] iso.sh corrigé: {path}")
    print(f"GO [OK] backup: {backup}")
    print("GO [OK] /opt/pincabos/tmp exclu du payload et gardé par validation.")
    print("GO [OK] VPX / BGFX / VPinFE non touchés.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
