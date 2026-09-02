#!/usr/bin/env python3
# PINCABOS_HYBRID_MODE_DETECTOR_V3
from __future__ import annotations

import argparse
import json
import re
import shlex
from pathlib import Path
from typing import Any, Iterable

MEDIA_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v",
    ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".mp3", ".ogg", ".wav", ".flac",
}
PUP_DIR_NAMES = {"pupvideos", "pupvideo", "pinupvideo", "pinupvideos"}
GLOBAL_ROM_DIRS = [
    Path("/home/pinball/.local/share/VPinballX/10.8/pinmame/roms"),
    Path("/home/pinball/.local/share/VPinballX/pinmame/roms"),
    Path("/home/pinball/.local/share/vpinball/pinmame/roms"),
    Path("/home/pinball/pinmame/roms"),
    Path("/home/pinball/Tables/pinmame/roms"),
]


def normalize_name(value: str) -> str:
    value = value.strip().strip("\"'")
    return re.sub(r"[^A-Za-z0-9_.-]+", "", value)


def unique(values: Iterable[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = normalize_name(value)
        if not clean:
            continue
        key = clean.casefold()
        if key in seen:
            continue
        seen.add(key)
        output.append(clean)
    return output


def load_config(table_dir: Path) -> tuple[Path, dict[str, Any]]:
    path = table_dir / "PinCabOS-Hybrid.json"
    if not path.is_file():
        return path, {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return path, {}
    return path, data if isinstance(data, dict) else {}


def find_casefold_file(directory: Path, stem: str, suffix: str) -> Path | None:
    if not directory.is_dir():
        return None
    target_stem = stem.casefold()
    target_suffix = suffix.casefold()
    try:
        for item in directory.iterdir():
            if item.is_file() and item.suffix.casefold() == target_suffix and item.stem.casefold() == target_stem:
                return item
    except OSError:
        pass
    return None


def pup_root_candidates(table_dir: Path) -> list[Path]:
    roots: list[Path] = []
    try:
        for child in table_dir.iterdir():
            if child.is_dir() and child.name.casefold() in PUP_DIR_NAMES:
                roots.append(child)
    except OSError:
        pass
    return sorted(roots, key=lambda path: str(path).casefold())


def pack_has_content(pack: Path) -> bool:
    if (pack / "screens.pup").is_file():
        return True
    visited = 0
    try:
        for item in pack.rglob("*"):
            visited += 1
            if item.is_file() and item.suffix.casefold() in MEDIA_EXTENSIONS:
                return True
            if visited >= 1500:
                break
    except OSError:
        pass
    return False


def inspect_pup_root(root: Path) -> list[Path]:
    packs: list[Path] = []
    if not root.is_dir():
        return packs
    if (root / "screens.pup").is_file():
        return [root]
    try:
        children = list(root.iterdir())
    except OSError:
        return packs
    for child in children:
        if child.is_dir() and pack_has_content(child):
            packs.append(child)
    if not packs and any(
        child.is_file() and child.suffix.casefold() in MEDIA_EXTENSIONS
        for child in children
    ):
        packs.append(root)
    return sorted(packs, key=lambda path: str(path).casefold())


def candidate_script_files(table: Path) -> list[Path]:
    files: list[Path] = []
    same_name = find_casefold_file(table.parent, table.stem, ".vbs")
    if same_name:
        files.append(same_name)
    try:
        for item in table.parent.iterdir():
            if item.is_file() and item.suffix.casefold() == ".vbs" and item not in files:
                files.append(item)
                if len(files) >= 6:
                    break
    except OSError:
        pass
    return files


def extract_rom_candidates(table: Path, pup_packs: list[Path], config: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    configured_rom = config.get("rom")
    if isinstance(configured_rom, str):
        candidates.append(configured_rom)
    candidates.extend(pack.name for pack in pup_packs if pack != pack.parent)

    regexes = [
        re.compile(r'''(?im)\b(?:cGameName|GameName)\s*=\s*["']([^"']+)["']'''),
        re.compile(r'''(?im)\bController\.GameName\s*=\s*["']([^"']+)["']'''),
        re.compile(r'''(?im)\bROM(?:NAME)?\s*[:=]\s*["']?([A-Za-z0-9_.-]+)'''),
    ]
    for path in candidate_script_files(table):
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as handle:
                text = handle.read(16 * 1024 * 1024)
        except OSError:
            continue
        for regex in regexes:
            candidates.extend(match.group(1) for match in regex.finditer(text))
    return unique(candidates)


def local_rom_dirs(table_dir: Path) -> list[Path]:
    return [
        table_dir / "pinmame" / "roms",
        table_dir / "roms",
        table_dir.parent / "pinmame" / "roms",
    ]


def zip_index(directory: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    if not directory.is_dir():
        return index
    try:
        for item in directory.iterdir():
            if item.is_file() and item.suffix.casefold() == ".zip":
                index.setdefault(item.stem.casefold(), item)
    except OSError:
        pass
    return index


def find_roms(table_dir: Path, candidates: list[str]) -> list[Path]:
    directories = local_rom_dirs(table_dir) + GLOBAL_ROM_DIRS
    indexes = [(directory, zip_index(directory)) for directory in directories]
    found: list[Path] = []
    seen: set[str] = set()

    for candidate in candidates:
        key = Path(candidate).stem.casefold()
        for _, index in indexes:
            match = index.get(key)
            if not match:
                continue
            identity = str(match).casefold()
            if identity not in seen:
                seen.add(identity)
                found.append(match)

    if not found:
        local_archives: list[Path] = []
        for directory, index in indexes[:3]:
            del directory
            local_archives.extend(index.values())
        unique_local = {str(path).casefold(): path for path in local_archives}
        if len(unique_local) == 1:
            found.append(next(iter(unique_local.values())))

    return found


def detect(table_value: str) -> dict[str, Any]:
    table = Path(table_value).expanduser()
    try:
        table = table.resolve(strict=True)
    except FileNotFoundError:
        raise SystemExit(f"Table introuvable : {table}")
    if table.suffix.casefold() != ".vpx":
        raise SystemExit(f"Le fichier n'est pas une table VPX : {table}")

    table_dir = table.parent
    config_path, config = load_config(table_dir)
    default = str(config.get("default", "original")).strip().casefold()
    default = "pup" if default.startswith("pup") else "original"
    try:
        timeout = max(0, int(config.get("timeout", 0)))
    except (TypeError, ValueError):
        timeout = 0

    root_details: list[tuple[Path, list[Path]]] = []
    for root in pup_root_candidates(table_dir):
        packs = inspect_pup_root(root)
        if packs:
            root_details.append((root, packs))

    pup_root = root_details[0][0] if root_details else None
    pup_packs = root_details[0][1] if root_details else []
    pup_available = bool(pup_root and pup_packs)

    rom_candidates = extract_rom_candidates(table, pup_packs, config)
    rom_files = find_roms(table_dir, rom_candidates)
    directb2s = find_casefold_file(table_dir, table.stem, ".directb2s")

    # Sans PuP-Pack, une table VPX est considérée Original.
    # Avec PuP-Pack, une ROM ou un directB2S confirme qu'un mode Original existe aussi.
    original_available = not pup_available or bool(rom_files or directb2s)

    configured = config.get("availability")
    if isinstance(configured, dict):
        if isinstance(configured.get("original"), bool):
            original_available = configured["original"]
        if isinstance(configured.get("pup"), bool):
            pup_available = configured["pup"]

    if original_available and pup_available:
        detected_mode = "hybrid"
    elif pup_available:
        detected_mode = "pup"
    else:
        detected_mode = "original"

    return {
        "ok": True,
        "table": str(table),
        "table_dir": str(table_dir),
        "config": str(config_path),
        "default": default,
        "timeout": timeout,
        "detected_mode": detected_mode,
        "original_available": original_available,
        "pup_available": pup_available,
        "directb2s": str(directb2s) if directb2s else "",
        "rom_candidates": rom_candidates,
        "rom_files": [str(path) for path in rom_files],
        "pup_root": str(pup_root) if pup_root else "",
        "pup_packs": [str(path) for path in pup_packs],
    }


def shell_output(data: dict[str, Any]) -> str:
    fields = {
        "DETECT_TABLE": data["table"],
        "DETECT_TABLE_DIR": data["table_dir"],
        "DETECT_CONFIG": data["config"],
        "DETECT_DEFAULT": data["default"],
        "DETECT_TIMEOUT": str(data["timeout"]),
        "DETECT_MODE": data["detected_mode"],
        "DETECT_ORIGINAL": "1" if data["original_available"] else "0",
        "DETECT_PUP": "1" if data["pup_available"] else "0",
        "DETECT_B2S": data["directb2s"],
        "DETECT_PUP_ROOT": data["pup_root"],
        "DETECT_ROM_FILES": "\n".join(data["rom_files"]),
        "DETECT_PUP_PACKS": "\n".join(data["pup_packs"]),
    }
    return "\n".join(f"{key}={shlex.quote(value)}" for key, value in fields.items())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("table")
    parser.add_argument("--shell", action="store_true")
    args = parser.parse_args()
    data = detect(args.table)
    print(shell_output(data) if args.shell else json.dumps(data, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
