from pathlib import Path
import os
import re
import sys
import tempfile

path = Path(sys.argv[1])

updates = {
    "tablescreenid": "0",
    "bgscreenid": "",
    "dmdscreenid": "",
    "fulldmdscreenid": "",
    "tablewindowoverride": "",
    "bgwindowoverride": "",
    "dmdwindowoverride": "",
}

original = (
    path.read_text(encoding="utf-8", errors="replace")
    if path.exists()
    else ""
)

lines = original.splitlines()
output = []
section = ""
found_displays = False
written = set()


def append_missing():
    for key, value in updates.items():
        if key not in written:
            output.append(f"{key} = {value}")
            written.add(key)


for line in lines:
    match = re.match(r"^\s*\[([^\]]+)\]\s*$", line)

    if match:
        if section == "displays":
            append_missing()

        section = match.group(1).strip().lower()

        if section == "displays":
            found_displays = True

        output.append(line)
        continue

    if section == "displays" and "=" in line:
        key = line.split("=", 1)[0].strip().lower()

        if key in updates:
            if key not in written:
                output.append(f"{key} = {updates[key]}")
                written.add(key)
            continue

    output.append(line)


if found_displays:
    if section == "displays":
        append_missing()
else:
    if output and output[-1].strip():
        output.append("")

    output.append("[Displays]")
    append_missing()


content = "\n".join(output).rstrip() + "\n"

path.parent.mkdir(parents=True, exist_ok=True)

fd, temporary = tempfile.mkstemp(
    prefix=f".{path.name}.",
    dir=str(path.parent),
)

try:
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())

    if path.exists():
        stat = path.stat()
        os.chmod(temporary, stat.st_mode & 0o777)
        os.chown(temporary, stat.st_uid, stat.st_gid)
    else:
        os.chmod(temporary, 0o644)

    os.replace(temporary, path)
finally:
    try:
        os.unlink(temporary)
    except FileNotFoundError:
        pass

print("OK: identité écrans VPinFE source supprimée.")
