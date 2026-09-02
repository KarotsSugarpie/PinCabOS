#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path


DETECTOR = Path(
    "/opt/pincabos/launchers/pincabos-detect-table-modes.py"
)

# PINCABOS_PUP_SPLIT_RUNTIME_V1
# /run appartient a root et ce script tourne en pinball : sans le repertoire
# cree par tmpfiles.d (etc/tmpfiles.d/pincabos-pup-scoreview-split.conf), le
# mkdir echouait en PermissionError a chaque table PuP et le split restait
# silencieusement inactif. Repli : XDG_RUNTIME_DIR, puis /tmp.
def _runtime_root() -> Path:
    candidates = [Path("/run/pincabos-pup-scoreview-split")]
    xdg = os.environ.get("XDG_RUNTIME_DIR")
    if xdg:
        candidates.append(Path(xdg) / "pincabos-pup-scoreview-split")
    candidates.append(Path("/tmp") / f"pincabos-pup-scoreview-split-{os.getuid()}")
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            if os.access(candidate, os.W_OK):
                return candidate
        except OSError:
            continue
    return candidates[-1]


RUNTIME_ROOT = _runtime_root()


def q(value: object) -> str:
    return shlex.quote(str(value))


def read_sections(text: str) -> dict[str, dict[str, str]]:
    data: dict[str, dict[str, str]] = {}
    section = ""

    for raw in text.splitlines():
        line = raw.strip()

        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().casefold()
            data.setdefault(section, {})
            continue

        if (
            not line
            or line.startswith("#")
            or line.startswith(";")
            or "=" not in line
        ):
            continue

        key, value = line.split("=", 1)

        data.setdefault(section, {})[
            key.strip().casefold()
        ] = value.strip()

    return data


def patch_section(
    text: str,
    section: str,
    values: dict[str, str],
) -> str:

    lines = text.splitlines()
    wanted = section.casefold()

    start = None
    end = None

    for i, raw in enumerate(lines):
        line = raw.strip()

        if not (
            line.startswith("[")
            and line.endswith("]")
        ):
            continue

        name = line[1:-1].strip().casefold()

        if name == wanted:
            start = i
            continue

        if start is not None:
            end = i
            break

    if start is None:
        if lines and lines[-1].strip():
            lines.append("")

        lines.append(f"[{section}]")

        for key, value in values.items():
            lines.append(f"{key} = {value}")

        return "\n".join(lines) + "\n"

    if end is None:
        end = len(lines)

    existing: dict[str, int] = {}

    for i in range(start + 1, end):
        line = lines[i].strip()

        if (
            not line
            or line.startswith("#")
            or line.startswith(";")
            or "=" not in line
        ):
            continue

        key = line.split("=", 1)[0].strip().casefold()
        existing[key] = i

    additions: list[str] = []

    for key, value in values.items():
        folded = key.casefold()

        if folded in existing:
            lines[existing[folded]] = f"{key} = {value}"
        else:
            additions.append(f"{key} = {value}")

    if additions:
        lines[end:end] = additions

    return "\n".join(lines) + "\n"


def detect(table: Path) -> dict:
    raw = subprocess.check_output(
        [str(DETECTOR), str(table)],
        text=True,
    )
    return json.loads(raw)


def find_ini(table: Path) -> Path:
    return table.with_suffix(".ini")


def patch_ini(
    table: Path,
    mode: str,
    score_x: int,
    score_y: int,
    score_w: int,
    score_h: int,
) -> None:

    ini = find_ini(table)

    text = (
        ini.read_text(
            encoding="utf-8",
            errors="ignore",
        )
        if ini.is_file()
        else ""
    )

    if mode == "legacy":

        text = patch_section(
            text,
            "Topper",
            {
                "TopperOutput": "0",
            },
        )

        text = patch_section(
            text,
            "ScoreView",
            {
                "ScoreViewOutput": "1",
                "ScoreViewFullScreen": "0",
                "ScoreViewWndX": "0",
                "ScoreViewWndY": "0",
                "ScoreViewWidth": "1920",
                "ScoreViewHeight": "1200",
                "ScoreViewFSWidth": "1920",
                "ScoreViewFSHeight": "1200",
            },
        )

    else:

        text = patch_section(
            text,
            "Topper",
            {
                "TopperOutput": "1",
                "TopperFullScreen": "0",
                "TopperWndX": "0",
                "TopperWndY": "0",
                "TopperWidth": "1920",
                "TopperHeight": "1200",
                "TopperFSWidth": "1920",
                "TopperFSHeight": "1200",
                "Priority.PUP": "3",
            },
        )

        text = patch_section(
            text,
            "ScoreView",
            {
                "ScoreViewOutput": "1",
                "ScoreViewFullScreen": "0",
                "ScoreViewWndX": "0",
                "ScoreViewWndY": "0",
                "ScoreViewWidth": str(score_w),
                "ScoreViewHeight": str(score_h),
                "ScoreViewFSWidth": str(score_w),
                "ScoreViewFSHeight": str(score_h),
                "Priority.ScoreView": "2",
                "Priority.PUP": "3",
            },
        )

    # PINCABOS_PUP_B2S_FINAL_GUARD_V9
    # PINCABOS_PUP_SCOREVIEW_PRIORITY_V16
    # ScoreView possède exclusivement la fenêtre ScoreView.
    # Le contenu PuP FullDMD est routé dans Topper.

    #
    # Ce bloc est volontairement appliqué APRES la préparation
    # ScoreView. Le script ScoreView peut modifier certaines clés
    # B2SLegacy; en mode PuP nous imposons ici l'état final.
    if mode == "pup":

        text = patch_section(
            text,
            "Plugin.B2SLegacy",
            {
                "Enable": "0",
                "B2SHideB2SBackglass": "1",
                "B2SHideB2SDMD": "1",
                "B2SHideDMD": "1",
                "ScoreViewDMDOverlay": "0",
                "ScoreViewDMDAutoPos": "0",
            },
        )

        text = patch_section(
            text,
            "Plugin.ScoreView",
            {
                "Enable": "1",
            },
        )

        text = patch_section(
            text,
            "ScoreView",
            {
                "ScoreViewOutput": "1",
                "Priority.ScoreView": "3",
                "Priority.PUP": "0",
            },
        )

    ini.write_text(
        text,
        encoding="utf-8",
    )


def trigger_uses_screen(
    path: Path,
    screen_num: int,
) -> bool:

    if not path.is_file():
        return False

    with path.open(
        "r",
        encoding="utf-8-sig",
        errors="replace",
        newline="",
    ) as fh:

        for row in csv.reader(fh):
            if not row:
                continue

            try:
                value = int(row[0].strip())
            except Exception:
                continue

            if value == screen_num:
                return True

    return False


def make_split(table: Path) -> dict[str, str]:
    # PINCABOS_PUP_SPLIT_ROOT_GATE_V1
    # Le montage en namespace qui applique le split exige root ; la chaine de
    # lancement tourne en pinball. Tant qu'un helper privilegie n'existe pas,
    # le split est declare inactif ICI, avant que la politique DMD/FullDMD et
    # le placeur ne lisent la reponse — sinon ils appliquent la geometrie
    # split a des ecrans PuP qui n'ont pas ete remappes.
    if os.geteuid() != 0:
        return {
            "active": "0",
            "reason": "requiert root (namespace mount)",
        }


    info = detect(table)

    packs = [
        Path(p)
        for p in info.get("pup_packs", [])
    ]

    pack = next(
        (
            p
            for p in packs
            if (p / "screens.pup").is_file()
        ),
        None,
    )

    if pack is None:
        return {
            "active": "0",
            "reason": "Aucun screens.pup",
        }

    screens = pack / "screens.pup"
    triggers = pack / "triggers.pup"

    with screens.open(
        "r",
        encoding="utf-8-sig",
        errors="replace",
        newline="",
    ) as fh:
        rows = list(csv.reader(fh))

    if not rows:
        return {
            "active": "0",
            "reason": "screens.pup vide",
        }

    screen0 = None
    moved = []

    for row in rows[1:]:

        if not row:
            continue

        while len(row) < 8:
            row.append("")

        try:
            num = int(row[0].strip())
        except Exception:
            continue

        if num == 0:
            screen0 = row

    if screen0 is None:
        return {
            "active": "0",
            "reason": "screen 0 Topper absent",
        }

    while len(screen0) < 8:
        screen0.append("")

    #
    # Pour utiliser le Topper comme surface FullDMD,
    # le screen 0 doit être libre.
    #
    if (
        screen0[2].strip()
        or screen0[3].strip()
        or trigger_uses_screen(triggers, 0)
    ):
        return {
            "active": "0",
            "reason": "screen 0 déjà utilisé",
        }

    #
    # VPX rend normalement screen 5 puis screen 1
    # dans la fenêtre ScoreView.
    #
    # En les transformant en enfants de screen 0,
    # ils seront rendus dans la fenêtre Topper.
    #
    for row in rows[1:]:

        if not row:
            continue

        while len(row) < 8:
            row.append("")

        try:
            num = int(row[0].strip())
        except Exception:
            continue

        if num in {1, 5}:
            row[7] = "0,0,0,100,100"
            moved.append(num)

    if not moved:
        return {
            "active": "0",
            "reason": "screen 1/5 absent",
        }

    RUNTIME_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        os.chmod(
            RUNTIME_ROOT,
            0o755,
        )
    except OSError:
        pass

    digest = hashlib.sha1(
        str(table).encode()
    ).hexdigest()[:12]

    runtime = (
        RUNTIME_ROOT
        / f"{os.getpid()}-{digest}"
    )

    runtime.mkdir(
        parents=True,
        exist_ok=True,
    )

    os.chmod(
        runtime,
        0o755,
    )

    temp_screens = runtime / "screens.pup"

    output = io.StringIO()

    writer = csv.writer(
        output,
        lineterminator="\n",
    )

    writer.writerows(rows)

    temp_screens.write_text(
        output.getvalue(),
        encoding="utf-8",
    )

    os.chmod(
        temp_screens,
        0o644,
    )

    #
    # Réutiliser le rectangle connu du ScoreView B2S
    # quand il existe.
    #
    ini = find_ini(table)

    score_x = 0
    score_y = 0
    score_w = 640
    score_h = 160

    if ini.is_file():
        sections = read_sections(
            ini.read_text(
                encoding="utf-8",
                errors="ignore",
            )
        )

        b2s = sections.get(
            "plugin.b2slegacy",
            {},
        )

        def intval(key: str, default: int) -> int:
            try:
                value = int(b2s.get(key, default))
                return value if value >= 0 else default
            except Exception:
                return default

        score_x = intval(
            "scoreviewdmdx",
            score_x,
        )

        score_y = intval(
            "scoreviewdmdy",
            score_y,
        )

        score_w = intval(
            "scoreviewdmdw",
            score_w,
        )

        score_h = intval(
            "scoreviewdmdh",
            score_h,
        )

        if score_w <= 0:
            score_w = 640

        if score_h <= 0:
            score_h = 160

    patch_ini(
        table,
        "pup",
        score_x,
        score_y,
        score_w,
        score_h,
    )

    return {
        "active": "1",
        "pack": str(pack),
        "target": str(screens),
        "temp": str(temp_screens),
        "runtime": str(runtime),
        "moved": ",".join(
            str(x)
            for x in moved
        ),
        "score_x": str(score_x),
        "score_y": str(score_y),
        "score_w": str(score_w),
        "score_h": str(score_h),
        "reason": "OK",
    }


def print_shell(data: dict[str, str]) -> None:

    mapping = {
        "PINCABOS_PUP_SPLIT_ACTIVE":
            data.get("active", "0"),

        "PINCABOS_PUP_SPLIT_REASON":
            data.get("reason", ""),

        "PINCABOS_PUP_SPLIT_PACK":
            data.get("pack", ""),

        "PINCABOS_PUP_SPLIT_TARGET":
            data.get("target", ""),

        "PINCABOS_PUP_SPLIT_TEMP":
            data.get("temp", ""),

        "PINCABOS_PUP_SPLIT_RUNTIME":
            data.get("runtime", ""),

        "PINCABOS_SCOREVIEW_REL_X":
            data.get("score_x", "0"),

        "PINCABOS_SCOREVIEW_REL_Y":
            data.get("score_y", "0"),

        "PINCABOS_SCOREVIEW_W":
            data.get("score_w", "640"),

        "PINCABOS_SCOREVIEW_H":
            data.get("score_h", "160"),
    }

    for key, value in mapping.items():
        print(
            f"{key}={q(value)}"
        )


def main() -> int:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "mode",
        choices=(
            "pup",
            "legacy",
        ),
    )

    parser.add_argument(
        "table",
    )

    parser.add_argument(
        "--shell",
        action="store_true",
    )

    args = parser.parse_args()

    table = Path(args.table).resolve()

    if not table.is_file():
        print(
            f"NOGO [X] Table absente : {table}",
            file=sys.stderr,
        )
        return 1

    if args.mode == "legacy":

        patch_ini(
            table,
            "legacy",
            0,
            0,
            640,
            160,
        )

        data = {
            "active": "0",
            "reason": "Legacy",
        }

    else:
        data = make_split(table)

    if args.shell:
        print_shell(data)
    else:
        print(
            json.dumps(
                data,
                indent=2,
                ensure_ascii=False,
            )
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
