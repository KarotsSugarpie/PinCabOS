from pathlib import Path
import re
import sys

target = Path(sys.argv[1])

vpx_hardware_keys = {
    "playfielddisplay",
    "playfieldx",
    "playfieldy",
    "playfieldwidth",
    "playfieldheight",
    "playfieldfswidth",
    "playfieldfsheight",
    "playfieldfsrefreshrate",
    "backglassdisplay",
    "backglassx",
    "backglassy",
    "backglasswidth",
    "backglassheight",
    "backglassfswidth",
    "backglassfsheight",
    "backglassfsrefreshrate",
    "scoreviewdisplay",
    "scoreviewx",
    "scoreviewy",
    "scoreviewwidth",
    "scoreviewheight",
    "scoreviewfswidth",
    "scoreviewfsheight",
    "scoreviewfsrefreshrate",
    "topperdisplay",
    "topperx",
    "toppery",
    "topperwidth",
    "topperheight",
    "topperfswidth",
    "topperfsheight",
    "previewdisplay",
    "previewx",
    "previewy",
    "previewwidth",
    "previewheight",
    "previewfswidth",
    "previewfsheight",
}

vpinfe_hardware_keys = {
    "tablescreenid",
    "bgscreenid",
    "dmdscreenid",
    "fulldmdscreenid",
    "tableorientation",
    "tablerotation",
    "cabmode",
}


def sanitize_ini(
    path,
    forbidden_keys,
    removed_sections,
):
    if not path.is_file():
        return False

    original = path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    output = []
    skip_section = False

    for line in original.splitlines(
        keepends=True
    ):
        section_match = re.match(
            r"^\s*\[([^\]]+)\]\s*$",
            line,
        )

        if section_match:
            section_name = (
                section_match.group(1)
                .strip()
                .lower()
            )

            skip_section = (
                section_name
                in removed_sections
            )

            if skip_section:
                continue

        if skip_section:
            continue

        key_match = re.match(
            r"^\s*([^;#][^=]*?)\s*=",
            line,
        )

        if key_match:
            key = (
                key_match.group(1)
                .strip()
                .lower()
            )

            if key in forbidden_keys:
                continue

        output.append(line)

    sanitized = "".join(output)

    if sanitized == original:
        return False

    path.write_text(
        sanitized,
        encoding="utf-8",
    )

    return True


vpx_updated = 0

vpx_roots = [
    target / "home/pinball/.pincabos/vpx",  # PINCABOS_VPX_PREF_PATH_V1
    target / "home/pinball/.local/share/VPinballX",
    target / "home/pinball/.vpinball",
]

for root in vpx_roots:
    if not root.exists():
        continue

    for ini in root.rglob("VPinballX.ini"):
        if sanitize_ini(
            ini,
            vpx_hardware_keys,
            {"pincabos.screens"},
        ):
            vpx_updated += 1

vpinfe = (
    target
    / "home/pinball/.config/vpinfe/vpinfe.ini"
)

vpinfe_updated = sanitize_ini(
    vpinfe,
    vpinfe_hardware_keys,
    {"pincabos.screens"},
)

print(
    "GO [√] VPX display identities removed:",
    vpx_updated,
)

print(
    "GO [√] VPinFE display identity removed:",
    int(vpinfe_updated),
)
