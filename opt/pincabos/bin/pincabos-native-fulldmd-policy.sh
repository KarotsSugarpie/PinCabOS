#!/usr/bin/env bash
set -Eeuo pipefail

TABLES_ROOT="/home/pinball/Tables"
GLOBAL_INI="/home/pinball/.local/share/VPinballX/10.8/VPinballX.ini"

TARGET_VPX=""
for arg in "$@"; do
    case "$arg" in
        *.vpx|*.VPX)
            if [[ -f "$arg" ]]; then
                TARGET_VPX="$arg"
                break
            fi
            ;;
    esac
done

python3 -S - "$GLOBAL_INI" "$TABLES_ROOT" "$TARGET_VPX" <<'PY'
from __future__ import annotations

from pathlib import Path
import os
import pwd
import re
import sys

GLOBAL_INI = Path(sys.argv[1])
TABLES_ROOT = Path(sys.argv[2]).resolve()
TARGET_VPX = Path(sys.argv[3]).resolve() if sys.argv[3] else None

SCOREVIEW_WINDOW = {
    "ScoreViewOutput": "1",
    "ScoreViewDisplay": "",
    "ScoreViewFullScreen": "0",
    "ScoreViewWndX": "0",
    "ScoreViewWndY": "0",
    "ScoreViewWidth": "1920",
    "ScoreViewHeight": "1200",
    "ScoreViewFSWidth": "1920",
    "ScoreViewFSHeight": "1200",
}

SCOREVIEW_DISABLED_OUTPUT = dict(SCOREVIEW_WINDOW)
SCOREVIEW_DISABLED_OUTPUT["ScoreViewOutput"] = "0"

B2S_GEOMETRY = {
    "Enable": "1",
    "B2SHideGrill": "1",
    "B2SHideB2SBackglass": "0",
    "B2SDualMode": "0",
    "BackglassDMDOverlay": "0",
    "BackglassDMDAutoPos": "0",
    "B2SBackglassWidth": "1920",
    "B2SBackglassHeight": "1080",
    "B2SBackglassX": "3840",
    "B2SBackglassY": "0",
    "B2SDMDWidth": "1920",
    "B2SDMDHeight": "1200",
    "B2SDMDX": "5760",
    "B2SDMDY": "0",
    "B2SDMDRotation": "0",
}

B2S_FULLDMD = {
    **B2S_GEOMETRY,
    "B2SHideB2SDMD": "0",
    "B2SHideDMD": "1",
    "ScoreViewDMDOverlay": "1",
}

B2S_PUP = {
    **B2S_GEOMETRY,

    # PINCABOS_PUP_B2S_OFF_V9
    #
    # En mode PuP, le PuP-Pack possède les surfaces Backglass /
    # FullDMD. B2SLegacy doit être complètement neutralisé.
    "Enable": "0",
    "B2SHideB2SBackglass": "1",
    "B2SHideB2SDMD": "1",
    "B2SHideDMD": "1",
    "ScoreViewDMDOverlay": "0",
    "ScoreViewDMDAutoPos": "0",
}

DMD_DEFAULTS_ONLY = {
    "ScoreViewDMDAutoPos": "1",
    "ScoreViewDMDX": "0",
    "ScoreViewDMDY": "0",
    "ScoreViewDMDW": "0",
    "ScoreViewDMDH": "0",
}


def find_section(lines: list[str], section_name: str) -> tuple[int | None, int]:
    start = None
    end = len(lines)

    for index, line in enumerate(lines):
        match = re.match(r"^\s*\[([^\]]+)\]\s*$", line.strip())
        if match and match.group(1).strip().casefold() == section_name.casefold():
            start = index
            break

    if start is not None:
        for index in range(start + 1, len(lines)):
            if re.match(r"^\s*\[[^\]]+\]\s*$", lines[index].strip()):
                end = index
                break

    return start, end


def patch_ini(
    path: Path,
    overwrite: dict[str, dict[str, str]],
    ensure: dict[str, dict[str, str]] | None = None,
    remove_sections: tuple[str, ...] = (),
) -> None:
    raw = path.read_text(encoding="utf-8", errors="surrogateescape") if path.exists() else ""
    newline = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.splitlines(keepends=True)

    for section_name in remove_sections:
        start, end = find_section(lines, section_name)
        if start is not None:
            del lines[start:end]
            while start < len(lines) and not lines[start].strip():
                del lines[start]

    sections = [(section_name, values, False) for section_name, values in overwrite.items()]
    for section_name, values in (ensure or {}).items():
        sections.append((section_name, values, True))

    for section_name, values, ensure_only in sections:
        start, end = find_section(lines, section_name)

        if start is None:
            if lines and not lines[-1].endswith(("\n", "\r")):
                lines[-1] += newline
            if lines and lines[-1].strip():
                lines.append(newline)
            lines.append(f"[{section_name}]{newline}")
            for key, value in values.items():
                lines.append(f"{key} = {value}{newline}")
            continue

        found: set[str] = set()

        for index in range(start + 1, end):
            match = re.match(r"^(\s*)([^=;#]+?)\s*=.*?(\r?\n)?$", lines[index])
            if not match:
                continue

            current = match.group(2).strip()
            for key, value in values.items():
                if current.casefold() != key.casefold():
                    continue
                found.add(key.casefold())
                if not ensure_only:
                    ending = match.group(3) or newline
                    lines[index] = f"{match.group(1)}{key} = {value}{ending}"
                break

        additions = [
            f"{key} = {value}{newline}"
            for key, value in values.items()
            if key.casefold() not in found
        ]
        if additions:
            lines[end:end] = additions

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".pincabos-native-full-dmd.tmp")
    temporary.write_text("".join(lines), encoding="utf-8", errors="surrogateescape")
    os.replace(temporary, path)

    try:
        account = pwd.getpwnam("pinball")
        os.chown(path, account.pw_uid, account.pw_gid)
        os.chmod(path, 0o664)
    except (KeyError, PermissionError):
        pass


def find_directb2s(vpx: Path) -> Path | None:
    expected = vpx.with_suffix(".directb2s")
    if expected.is_file():
        return expected

    wanted = (vpx.stem + ".directb2s").casefold()
    try:
        for item in vpx.parent.iterdir():
            if item.is_file() and item.name.casefold() == wanted:
                return item
    except OSError:
        return None

    return None


def directb2s_has_fulldmd(path: Path | None) -> bool:
    if not path or not path.is_file():
        return False

    try:
        payload = path.read_bytes()
    except OSError:
        return False

    for encoding in ("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "latin-1"):
        try:
            text = payload.decode(encoding, errors="ignore")
        except Exception:
            continue

        match = re.search(
            r"<DMDType\b[^>]*\bValue\s*=\s*[\"']\s*([0-9]+)\s*[\"']",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if match and match.group(1) == "3":
            return True

        if re.search(r"<DMDImage\b", text, flags=re.IGNORECASE):
            return True

    return False


def has_table_local_pup(table_dir: Path) -> bool:
    try:
        entries = list(table_dir.iterdir())
    except OSError:
        return False

    for entry in entries:
        if not entry.is_dir() or entry.name.casefold() not in {"pupvideo", "pupvideos", "pinupvideo", "pinupvideos"}:
            continue
        try:
            return any(item.is_file() for item in entry.rglob("*"))
        except OSError:
            return True

    return False


# Base globale : la surface ScoreView existe, mais le plugin ScoreView distinct
# reste disponible seulement pour les tables qui n'ont pas de FullDMD B2S.
patch_ini(
    GLOBAL_INI,
    {
        "ScoreView": SCOREVIEW_WINDOW,
        "Plugin.B2SLegacy": B2S_GEOMETRY,
        "Plugin.ScoreView": {"Enable": "1"},
    },
)

if TARGET_VPX and TARGET_VPX.is_file():
    try:
        TARGET_VPX.relative_to(TABLES_ROOT)
    except ValueError:
        raise SystemExit("Chemin VPX hors du dossier Tables.")

    table_ini = TARGET_VPX.with_suffix(".ini")
    pup = has_table_local_pup(TARGET_VPX.parent)
    b2s = find_directb2s(TARGET_VPX)
    full_dmd = directb2s_has_fulldmd(b2s)

    if pup:
        patch_ini(
            table_ini,
            {
                "ScoreView": SCOREVIEW_DISABLED_OUTPUT,
                "Plugin.B2SLegacy": B2S_PUP,
                "Plugin.ScoreView": {"Enable": "0"},
            },
            remove_sections=("PinCabOS.ScoreViewWindow",),
        )
        mode = "PUP"
    elif full_dmd:
        patch_ini(
            table_ini,
            {
                "ScoreView": SCOREVIEW_WINDOW,
                "Plugin.B2SLegacy": B2S_FULLDMD,
                "Plugin.ScoreView": {"Enable": "0"},
            },
            ensure={"Plugin.B2SLegacy": DMD_DEFAULTS_ONLY},
            remove_sections=("PinCabOS.ScoreViewWindow",),
        )
        mode = "B2S_FULLDMD"
    else:
        # Aucune règle invasive pour les tables sans FullDMD directB2S.
        patch_ini(
            table_ini,
            {
                "Plugin.ScoreView": {"Enable": "1"},
            },
            remove_sections=("PinCabOS.ScoreViewWindow",),
        )
        mode = "STANDARD"

    print(f"MODE={mode}")
    print(f"TABLE={TARGET_VPX}")
    print(f"INI={table_ini}")
    print(f"DIRECTB2S={b2s or ''}")
PY

