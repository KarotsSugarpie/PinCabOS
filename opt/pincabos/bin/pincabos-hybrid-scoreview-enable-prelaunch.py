#!/usr/bin/env python3
# PINCABOS_HYBRID_SCOREVIEW_ENABLE_PRELAUNCH_V2
from __future__ import annotations

import os
import re
import shutil
import sys
import time
from pathlib import Path

GLOBAL_INI = Path("/home/pinball/.local/share/VPinballX/10.8/VPinballX.ini")

REQUIRED = {
    "Plugin.ScoreView": {
        "Enable": "1",
    },
    "ScoreView": {
        "ScoreViewOutput": "1",
        "ScoreViewFullScreen": "0",
        "Priority.ScoreView": "2",
        "Priority.B2SLegacyDMD": "0",
        "Priority.B2S": "0",
    },
    "Plugin.B2SLegacy": {
        "ScoreViewDMDOverlay": "1",
        "ScoreViewDMDAutoPos": "1",
    },
}


def find_table(args: list[str]) -> Path | None:
    for value in args:
        if value.lower().endswith(".vpx"):
            candidate = Path(value).expanduser().resolve()
            if candidate.is_file():
                return candidate
    return None


def patch_section(text: str, section: str, values: dict[str, str]) -> str:
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.replace("\r\n", "\n").split("\n")

    while lines and lines[-1] == "":
        lines.pop()

    header = f"[{section}]"
    start = None
    end = len(lines)

    for index, line in enumerate(lines):
        if line.strip().lower() == header.lower():
            start = index
            break

    if start is None:
        if lines:
            lines.append("")
        lines.append(header)
        for key, value in values.items():
            lines.append(f"{key} = {value}")
        return newline.join(lines) + newline

    for index in range(start + 1, len(lines)):
        stripped = lines[index].strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            end = index
            break

    positions: dict[str, int] = {}
    for index in range(start + 1, end):
        line = lines[index]
        if "=" not in line or line.lstrip().startswith(("#", ";")):
            continue
        key = line.split("=", 1)[0].strip().lower()
        positions[key] = index

    additions: list[str] = []
    for key, value in values.items():
        lookup = key.lower()
        if lookup in positions:
            lines[positions[lookup]] = f"{key} = {value}"
        else:
            additions.append(f"{key} = {value}")

    if additions:
        lines[end:end] = additions

    return newline.join(lines) + newline


def patch_file(path: Path, backup_dir: Path) -> bool:
    if not path.is_file():
        return False

    old = path.read_text(encoding="utf-8", errors="ignore")
    new = old

    for section, values in REQUIRED.items():
        new = patch_section(new, section, values)

    if new == old:
        return False

    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = backup_dir / f"{path.name}.{stamp}-{os.getpid()}.before"
    shutil.copy2(path, backup)

    temporary = path.with_name(path.name + f".tmp.{os.getpid()}")
    temporary.write_text(new, encoding="utf-8", newline="")
    temporary.replace(path)
    return True


def main() -> int:
    table = find_table(sys.argv[1:])
    backup_dir = (
        table.parent / "logs" / "hybrid-scoreview-prelaunch"
        if table is not None
        else Path("/var/lib/pincabos/hybrid-scoreview-prelaunch")
    )

    global_changed = patch_file(GLOBAL_INI, backup_dir)

    table_ini = table.with_suffix(".ini") if table is not None else None
    table_changed = False

    # Ne jamais créer un INI de table incomplet.
    # Un INI existant est corrigé; sinon le global reste la source.
    if table_ini is not None and table_ini.is_file():
        table_changed = patch_file(table_ini, backup_dir)

    print(
        "PINCABOS [SCOREVIEW ENABLE] "
        f"mode={os.environ.get('PINCABOS_GAME_CHOICE', 'original')} "
        f"global={'updated' if global_changed else 'ok'} "
        f"table_ini={'updated' if table_changed else ('ok' if table_ini and table_ini.is_file() else 'global')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
