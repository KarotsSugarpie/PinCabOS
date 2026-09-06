from pathlib import Path
import re
import sys

target = Path(sys.argv[1])

roots = [
    target / "home/pinball/.pincabos/vpx",  # PINCABOS_VPX_PREF_PATH_V1
    target / "home/pinball/.local/share/VPinballX",
    target / "home/pinball/.vpinball",
]

hardware_audio_key = re.compile(
    r"^\s*("
    r"SoundDevice|"
    r"SoundDeviceBG|"
    r"MusicDevice|"
    r"Sound3DDevice|"
    r"AudioDevice|"
    r"AudioDeviceBG"
    r")\s*=.*$",
    re.IGNORECASE,
)

updated = 0

for root in roots:
    if not root.exists():
        continue

    for ini in root.rglob("VPinballX.ini"):
        if not ini.is_file() or ini.is_symlink():
            continue

        original = ini.read_text(
            encoding="utf-8",
            errors="replace",
        )

        sanitized = "".join(
            line
            for line in original.splitlines(keepends=True)
            if not hardware_audio_key.match(line)
        )

        if sanitized != original:
            ini.write_text(
                sanitized,
                encoding="utf-8",
            )
            updated += 1

print(
    f"GO [√] Target VPX audio mappings removed: {updated}"
)
