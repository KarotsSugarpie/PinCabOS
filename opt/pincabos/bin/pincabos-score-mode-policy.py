#!/usr/bin/env python3

from pathlib import Path
import sys

# PINCABOS_FRONTON_SANS_FULLDMD_V1 : sur un cabinet sans ecran FullDMD (deux
# ecrans, cas Francois), ne jamais inventer une fenetre Score View ni une
# geometrie DMD de repli. Reponse partagee : opt/pincabos/tools/pincabos_fronton.py
sys.path.insert(0, "/opt/pincabos/tools")
try:
    import pincabos_fronton as _fronton
except ImportError:  # mise a jour partielle : comportement historique
    _fronton = None
# Sans ecran FullDMD, le retour au mode Legacy ne recree pas de fenetre Score View.
SCOREVIEW_LEGACY = "0" if _fronton is not None and _fronton.fulldmd_disponible() is False else "1"


def find_table(args):

    for arg in args:
        if arg.lower().endswith(".vpx"):
            return Path(arg)

    return None


def patch_section(
    text,
    section,
    values,
):
    lines = text.splitlines()

    start = None
    end = None

    for i, raw in enumerate(lines):

        s = raw.strip()

        if (
            s.startswith("[")
            and s.endswith("]")
        ):
            name = s[1:-1].strip()

            if (
                name.casefold()
                == section.casefold()
            ):
                start = i
                continue

            if start is not None:
                end = i
                break

    if start is None:

        if (
            lines
            and lines[-1].strip()
        ):
            lines.append("")

        lines.append(
            f"[{section}]"
        )

        for key, value in values.items():
            lines.append(
                f"{key} = {value}"
            )

        return "\n".join(lines) + "\n"

    if end is None:
        end = len(lines)

    existing = {}

    for i in range(
        start + 1,
        end
    ):
        s = lines[i].strip()

        if (
            not s
            or s.startswith((";", "#"))
            or "=" not in s
        ):
            continue

        key = (
            s.split("=", 1)[0]
            .strip()
            .casefold()
        )

        existing[key] = i

    additions = []

    for key, value in values.items():

        folded = key.casefold()

        if folded in existing:

            lines[
                existing[folded]
            ] = (
                f"{key} = {value}"
            )

        else:

            additions.append(
                f"{key} = {value}"
            )

    if additions:
        lines[end:end] = additions

    return "\n".join(lines) + "\n"


if len(sys.argv) < 2:
    raise SystemExit(0)

mode = sys.argv[1].strip().lower()

table = find_table(
    sys.argv[2:]
)

if table is None:
    print(
        "PINCABOS [SCORE POLICY] "
        "Aucune table VPX"
    )
    raise SystemExit(0)

ini = table.with_suffix(
    ".ini"
)

if ini.exists():
    text = ini.read_text(
        encoding="utf-8",
        errors="ignore",
    )
else:
    text = ""


common = {
    "Plugin.PinCabRawScore": {
        "Enable": "0",
    },

    "Plugin.DMDUtil": {
        "Enable": "0",
        "DMDServer": "0",
        "FindDisplays": "0",
        "DumpDMDTxt": "0",
        "DumpDMDRaw": "0",
    },

    #
    # REMISE DES COULEURS ROM
    #
    "Plugin.VNI": {
        "Enable": "1",
    },

    "Plugin.Serum": {
        "Enable": "1",
    },
}


for section, values in common.items():
    text = patch_section(
        text,
        section,
        values,
    )


if mode in (
    "pup",
    "puppack",
    "pup-pack",
):
    #
    # PuP :
    # aucune fenêtre ScoreView VPX.
    # Le score externe est utilisé.
    #
    text = patch_section(
        text,
        "Plugin.PinCabRawTap",
        {
            "Enable": "1",
        },
    )

    text = patch_section(
        text,
        "Plugin.B2SLegacy",
        {
            "Enable": "0",
        },
    )

    text = patch_section(
        text,
        "ScoreView",
        {
            "ScoreViewOutput": "0",
        },
    )

    print(
        "PINCABOS [SCORE POLICY] "
        "PUP -> External score ON"
    )

    print(
        "PINCABOS [SCORE POLICY] "
        "VPX ScoreView OFF"
    )

else:
    #
    # Legacy :
    # revient au fonctionnement VPX/B2S.
    #
    text = patch_section(
        text,
        "Plugin.PinCabRawTap",
        {
            "Enable": "1",
        },
    )

    text = patch_section(
        text,
        "ScoreView",
        {
            "ScoreViewOutput": SCOREVIEW_LEGACY,
        },
    )

    print(
        "PINCABOS [SCORE POLICY] "
        "LEGACY -> External score OFF"
    )

    print(
        "PINCABOS [SCORE POLICY] "
        "VPX ScoreView restored"
    )


ini.write_text(
    text,
    encoding="utf-8",
)

print(
    "PINCABOS [SCORE POLICY] "
    "VNI=ON Serum=ON"
)
