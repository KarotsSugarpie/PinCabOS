#!/usr/bin/env python3
# PINCABOS_FULLDMD_AUTOARRANGE_V2
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

MANAGED = {
    "ScoreViewFullScreen": "0",
    "ScoreViewWndX": None,
    "ScoreViewWndY": None,
    "ScoreViewWidth": None,
    "ScoreViewHeight": None,
}

def fail(message: str) -> None:
    print(f"ERREUR: {message}", file=sys.stderr)
    raise SystemExit(1)

def valid_int(text: str, positive: bool = False) -> int:
    try:
        value = int(text)
    except ValueError:
        fail(f"valeur entiere invalide: {text!r}")
    if positive and value <= 0:
        fail(f"valeur positive requise: {value}")
    return value

def write_atomic(path: Path, content: str) -> None:
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".tmp.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass

def update_scoreview(text: str, values: dict[str, str]) -> str:
    # Preserve all user overrides. Only the five managed ScoreView keys are changed.
    lines = text.splitlines(keepends=True)
    section_rx = re.compile(r"^\s*\[([^\]]+)\]\s*(?:[;#].*)?$", re.IGNORECASE)
    key_rx = re.compile(r"^(\s*)(ScoreViewFullScreen|ScoreViewWndX|ScoreViewWndY|ScoreViewWidth|ScoreViewHeight)(\s*=).*$", re.IGNORECASE)

    start = end = None
    for index, line in enumerate(lines):
        match = section_rx.match(line.rstrip("\r\n"))
        if match and match.group(1).strip().casefold() == "scoreview":
            start = index
            end = len(lines)
            for later in range(index + 1, len(lines)):
                if section_rx.match(lines[later].rstrip("\r\n")):
                    end = later
                    break
            break

    managed_lower = {key.casefold(): key for key in values}

    if start is None:
        if lines and not lines[-1].endswith(("\n", "\r")):
            lines[-1] += "\n"
        if lines and lines[-1].strip():
            lines.append("\n")
        lines.append("[ScoreView]\n")
        for key in ("ScoreViewFullScreen", "ScoreViewWndX", "ScoreViewWndY", "ScoreViewWidth", "ScoreViewHeight"):
            lines.append(f"{key} = {values[key]}\n")
        return "".join(lines)

    seen: set[str] = set()
    rebuilt: list[str] = []
    for index, line in enumerate(lines):
        if start < index < end:
            match = key_rx.match(line.rstrip("\r\n"))
            if match:
                canonical = managed_lower[match.group(2).casefold()]
                if canonical in seen:
                    # Remove duplicate managed entries; keep one deterministic value.
                    continue
                newline = "\r\n" if line.endswith("\r\n") else "\n"
                rebuilt.append(f"{match.group(1)}{canonical}{match.group(3)} {values[canonical]}{newline}")
                seen.add(canonical)
                continue
        rebuilt.append(line)

    insert_at = start + 1
    # Account for kept/removed entries by finding ScoreView header again in rebuilt.
    for idx, line in enumerate(rebuilt):
        match = section_rx.match(line.rstrip("\r\n"))
        if match and match.group(1).strip().casefold() == "scoreview":
            insert_at = idx + 1
            break
    missing = [key for key in ("ScoreViewFullScreen", "ScoreViewWndX", "ScoreViewWndY", "ScoreViewWidth", "ScoreViewHeight") if key not in seen]
    for key in reversed(missing):
        rebuilt.insert(insert_at, f"{key} = {values[key]}\n")
    return "".join(rebuilt)

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ini", required=True)
    parser.add_argument("--x", required=True)
    parser.add_argument("--y", required=True)
    parser.add_argument("--width", required=True)
    parser.add_argument("--height", required=True)
    args = parser.parse_args()

    x = valid_int(args.x)
    y = valid_int(args.y)
    width = valid_int(args.width, positive=True)
    height = valid_int(args.height, positive=True)

    path = Path(args.ini)
    path.parent.mkdir(parents=True, exist_ok=True)

    original_exists = path.exists()
    original = path.read_text(encoding="utf-8", errors="surrogateescape") if original_exists else ""
    backup = path.with_name(path.name + ".pincabos-fulldmd-before-autoarrange.bak")
    if original_exists and not backup.exists():
        shutil.copy2(path, backup)

    values = dict(MANAGED)
    values.update({
        "ScoreViewWndX": str(x),
        "ScoreViewWndY": str(y),
        "ScoreViewWidth": str(width),
        "ScoreViewHeight": str(height),
    })
    updated = update_scoreview(original, values)
    if updated != original:
        write_atomic(path, updated)
        try:
            os.chmod(path, 0o644)
        except OSError:
            pass
    print(f"ScoreView INI synchronise : {path}")
    print(f"ScoreView : {width}x{height}+{x}+{y}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
