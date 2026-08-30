"""Fail-closed archive boundary for PinCabOS Smart Import."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

CORE = None
MAX_NESTED_PASSES = 6
AUTHORITATIVE_ROM_PATHS = set()

PASSWORD_MARKERS = (
    "wrong password",
    "password is incorrect",
    "incorrect password",
    "missing password",
    "password required",
    "can not open encrypted archive",
    "cannot open encrypted archive",
)

ROM_MEMBER_RE = re.compile(
    r"\.(?:bin|rom|cpu|prom|snd|sound|hex|u\d{1,3}|ic\d{1,3}|\d{3,4})$",
    re.IGNORECASE,
)

ROM_REJECT_SUFFIXES = {
    ".vpx", ".directb2s", ".vbs", ".scv", ".pov", ".res", ".dif",
    ".pup", ".ini", ".cfg", ".nv", ".nvram", ".pal", ".vni", ".crz",
    ".pac", ".mp4", ".avi", ".mov", ".mkv", ".webm", ".png", ".jpg",
    ".jpeg", ".webp", ".gif", ".apng", ".mp3", ".wav", ".ogg",
    ".flac", ".ttf", ".otf", ".woff", ".woff2", ".txt", ".pdf",
    ".doc", ".docx", ".rtf", ".nfo", ".md", ".json", ".xml", ".html",
    ".htm", ".js", ".py", ".sh", ".bat", ".cmd", ".ps1", ".dll",
    ".exe", ".so",
}


def _core():
    if CORE is None:
        raise RuntimeError("Smart Import archive hardening not installed")
    return CORE


def _parse_7z_paths(data, src):
    src_text = str(src)
    paths = []
    for raw_line in str(data or "").splitlines():
        line = raw_line.strip()
        if not line.startswith("Path = "):
            continue
        value = line.split("=", 1)[1].strip()
        if value and value != src_text:
            paths.append(value)
    return paths


def archive_probe_result(src):
    """Return (code, diagnostic, entries, engine) for an archive catalogue."""
    core = _core()
    src = Path(src)
    try:
        result = core.run(["7z", "l", "-slt", str(src)], timeout=180)
        diagnostic = (result.stdout or "") + "\n" + (result.stderr or "")
        entries = _parse_7z_paths(diagnostic, src)
        if result.returncode == 0:
            return 0, diagnostic, entries, "7-Zip"
        code = result.returncode
    except Exception as exc:
        diagnostic = str(exc)
        entries = []
        code = 255

    # RAR 7 may be catalogueable only by the official UnRAR installed by PinCabOS.
    if src.suffix.lower() == ".rar":
        unrar = Path("/usr/local/bin/pincabos-unrar")
        if unrar.is_file():
            try:
                fallback = core.run([str(unrar), "lb", "-p-", str(src)], timeout=180)
                fallback_text = (fallback.stdout or "") + "\n" + (fallback.stderr or "")
                if fallback.returncode == 0:
                    fallback_entries = [
                        line.strip()
                        for line in (fallback.stdout or "").splitlines()
                        if line.strip()
                    ]
                    return (
                        0,
                        diagnostic + "\n--- UnRAR fallback ---\n" + fallback_text,
                        fallback_entries,
                        "UnRAR",
                    )
                diagnostic += "\n--- UnRAR fallback ---\n" + fallback_text
                code = fallback.returncode
            except Exception as exc:
                diagnostic += f"\n--- UnRAR fallback exception ---\n{exc}"

    return code, diagnostic, entries, "7-Zip"


def archive_probe(src):
    return archive_probe_result(src)[1]


def archive_file_list(src, probe_result=None):
    if probe_result is None:
        probe_result = archive_probe_result(src)
    return list(probe_result[2])


def archive_is_passworded(src):
    data = archive_probe(src).lower()
    return any(marker in data for marker in PASSWORD_MARKERS)


def archive_validate(src):
    src = Path(src)
    code, diagnostic, entries, engine = archive_probe_result(src)
    lowered = diagnostic.lower()

    if code != 0:
        if any(marker in lowered for marker in PASSWORD_MARKERS):
            raise RuntimeError(
                f"ARCHIVE PASSWORD REFUSÉE: {src}\n"
                f"Probe: {engine} (code={code})\n{diagnostic.strip()}"
            )
        raise RuntimeError(
            f"ARCHIVE ILLISIBLE: {src}\n"
            "Le fichier porte une extension d'archive PinCabOS mais son "
            "conteneur ne peut pas être catalogué.\n"
            f"Probe: {engine} (code={code})\n{diagnostic.strip()}"
        )

    if not entries:
        raise RuntimeError(
            f"ARCHIVE VIDE: {src}\n"
            "Le conteneur est lisible mais ne contient aucune entrée exploitable."
        )

    return entries


def pincabos_zip_looks_like_rom(files):
    """Conservative legacy PinMAME ROM heuristic.

    VPSDB resources explicitly typed romFile bypass this heuristic after archive
    validation. Ambiguous legacy ZIPs therefore fail toward support_archive.
    """
    members = [
        Path(str(value).replace("\\", "/")).name
        for value in files
        if Path(str(value).replace("\\", "/")).name
    ]
    if not members:
        return False

    lowered = [name.casefold() for name in members]
    if any(name.startswith(("readme", "install", "license")) for name in lowered):
        return False
    if any(Path(name).suffix.casefold() in ROM_REJECT_SUFFIXES for name in lowered):
        return False
    return any(ROM_MEMBER_RE.search(name) for name in lowered)


def archive_kind(src):
    core = _core()
    src = Path(src)
    if src.suffix.lower() not in core.ARCHIVE_EXTS:
        return ""

    files = [value.lower().replace("\\", "/") for value in archive_validate(src)]

    try:
        authoritative_rom = src.resolve() in AUTHORITATIVE_ROM_PATHS
    except Exception:
        authoritative_rom = False
    if src.suffix.lower() == ".zip" and authoritative_rom:
        return "rom_zip"
    names = [Path(value).name.lower() for value in files]

    if any(value.endswith(".dif") for value in files):
        return "vpu_patch_archive"
    if any(value.endswith(".vpx") for value in files):
        return "table_archive"
    if "pinupplayer.ini" in names or any(value.endswith(".pup") for value in files):
        return "pup_archive"
    if (
        "altsound.ini" in names
        or "altsound.csv" in names
        or any("/altsound/" in value or value.startswith("altsound/") for value in files)
    ):
        return "altsound_archive"
    if any(value.endswith((".mp3", ".wav", ".ogg", ".flac")) for value in files):
        return "music_archive"
    if any(value.endswith(".crz") for value in files):
        return "serum_archive"
    if any(value.endswith((".pal", ".vni")) for value in files):
        return "vni_archive"
    if src.suffix.lower() == ".zip" and pincabos_zip_looks_like_rom(files):
        return "rom_zip"
    return "support_archive"


def pincabos_archive_extract_dir(parent, prefix, item):
    """Stable unique extraction directory; prevents same-stem collisions."""
    core = _core()
    item = Path(item)
    name_key = hashlib.sha256(item.name.encode("utf-8", errors="surrogatepass")).hexdigest()[:10]
    content_key = core.pincabos_file_sha256(item)[:12]
    suffix = item.suffix.lower().lstrip(".") or "archive"
    return Path(parent) / (
        f"{prefix}_{core.safe_name(item.stem)}_{suffix}_{name_key}_{content_key}"
    )


def _resource_type(resource):
    if not isinstance(resource, dict):
        return ""
    return str(resource.get("resource_type", "") or "").strip()


def extract_all_inputs(batch_dir, extract_root, resource_manifest=None):
    core = _core()
    batch_dir = Path(batch_dir)
    extract_root = Path(extract_root)
    extract_root.mkdir(parents=True, exist_ok=True)

    resources_by_name = {}
    if isinstance(resource_manifest, dict):
        for index, resource in enumerate(resource_manifest.get("resources", [])):
            if not isinstance(resource, dict):
                continue
            stored_name = str(resource.get("stored_name", "") or "").strip()
            resource_root = extract_root / (
                f"resource_{index:03d}_"
                f"{core.safe_name(resource.get('resource_type', 'file'))}_"
                f"{core.safe_name(resource.get('vpsid', 'unknown'))}"
            )
            resource_root.mkdir(parents=True, exist_ok=True)
            resource["_extract_root"] = str(resource_root)
            resource["_staged_installed"] = {}
            resources_by_name[stored_name.casefold()] = (resource, resource_root)

    raw_dir = extract_root / "_raw_files"
    if not resource_manifest:
        raw_dir.mkdir(parents=True, exist_ok=True)

    for item in sorted(batch_dir.rglob("*")):
        if not item.is_file() or item.name == core.PINCABOS_SMART_IMPORT_RESOURCE_MANIFEST:
            continue

        resource = None
        item_extract_root = extract_root
        item_raw_dir = raw_dir
        if resource_manifest:
            resolved = resources_by_name.get(item.name.casefold())
            if resolved is None:
                raise RuntimeError(
                    "NOGO: fichier absent de l’inventaire Smart Import analysé: "
                    f"{item.name}"
                )
            resource, item_extract_root = resolved
            item_raw_dir = item_extract_root / "_raw_files"
            item_raw_dir.mkdir(parents=True, exist_ok=True)

        suffix = item.suffix.lower()
        if suffix not in core.ARCHIVE_EXTS:
            core.copy_file(item, item_raw_dir)
            continue

        # A VPSDB romFile is authoritative, but the ZIP still has to be readable.
        if suffix == ".zip" and _resource_type(resource) == "romFile":
            archive_validate(item)
            copied_rom = core.copy_file(item, item_raw_dir)
            for candidate in (item, copied_rom):
                try:
                    AUTHORITATIVE_ROM_PATHS.add(Path(candidate).resolve())
                except Exception:
                    pass
            continue

        try:
            kind = archive_kind(item)
        except RuntimeError as exc:
            # Known auxiliary VPSDB resources may be encrypted; tableFile never is optional.
            if (
                core.is_password_protected_error(exc)
                and resource is not None
                and _resource_type(resource) not in {"", "tableFile"}
            ):
                core.log(
                    "WARNING: ARCHIVE VPSDB OPTIONNEL IGNORÉ — protégé par mot "
                    f"de passe: {item} | type={_resource_type(resource)}"
                )
                continue
            raise

        if kind == "rom_zip":
            core.copy_file(item, item_raw_dir)
            continue

        dest = pincabos_archive_extract_dir(item_extract_root, "archive", item)
        if dest.exists():
            raise RuntimeError(f"NOGO: collision de destination d'extraction: {dest}")

        core.log("")
        core.log("==================================================")
        core.log(f"ARCHIVE: {item}")
        core.log(f"TYPE: {kind}")
        core.log("==================================================")
        try:
            core.extract_archive(item, dest)
        except RuntimeError as exc:
            if core.is_password_protected_error(exc) and kind not in {
                "table_archive", "vpu_patch_archive",
            }:
                core.log(
                    "WARNING: ARCHIVE OPTIONNEL IGNORÉ — protégé par mot de passe: "
                    f"{item} | type={kind}"
                )
                continue
            raise

    changed = True
    loop = 0
    while changed and loop < MAX_NESTED_PASSES:
        changed = False
        loop += 1
        for item in sorted(extract_root.rglob("*")):
            if (
                not item.is_file()
                or item.suffix.lower() not in core.ARCHIVE_EXTS
                or item.name.startswith("already_extracted_")
            ):
                continue

            kind = archive_kind(item)
            if kind == "rom_zip":
                continue

            dest = pincabos_archive_extract_dir(item.parent, "nested", item)
            if dest.exists():
                raise RuntimeError(f"NOGO: collision archive interne: {item} -> {dest}")

            core.log("")
            core.log(f"ARCHIVE INTERNE: {item}")
            core.log(f"TYPE INTERNE: {kind}")
            try:
                core.extract_archive(item, dest)
            except RuntimeError as exc:
                if core.is_password_protected_error(exc) and kind not in {
                    "table_archive", "vpu_patch_archive",
                }:
                    core.log(
                        "WARNING: ARCHIVE INTERNE OPTIONNEL IGNORÉ — protégé "
                        f"par mot de passe: {item} | type={kind}"
                    )
                    item.rename(item.with_name("already_extracted_" + item.name))
                    changed = True
                    continue
                raise

            item.rename(item.with_name("already_extracted_" + item.name))
            changed = True

    pending = []
    for item in sorted(extract_root.rglob("*")):
        if (
            item.is_file()
            and item.suffix.lower() in core.ARCHIVE_EXTS
            and not item.name.startswith("already_extracted_")
            and archive_kind(item) != "rom_zip"
        ):
            pending.append(item)

    if pending:
        raise RuntimeError(
            "NOGO: limite d'imbrication des archives atteinte "
            f"({MAX_NESTED_PASSES} passes). Archives encore non traitées: "
            + " | ".join(str(item) for item in pending[:20])
        )


def install(core):
    global CORE
    CORE = core
    core.archive_probe_result = archive_probe_result
    core.archive_probe = archive_probe
    core.archive_file_list = archive_file_list
    core.archive_is_passworded = archive_is_passworded
    core.archive_kind = archive_kind
    core.extract_all_inputs = extract_all_inputs
    return {
        "archive_probe_result": archive_probe_result,
        "archive_probe": archive_probe,
        "archive_file_list": archive_file_list,
        "archive_is_passworded": archive_is_passworded,
        "archive_validate": archive_validate,
        "archive_kind": archive_kind,
        "pincabos_zip_looks_like_rom": pincabos_zip_looks_like_rom,
        "pincabos_archive_extract_dir": pincabos_archive_extract_dir,
        "extract_all_inputs": extract_all_inputs,
    }
