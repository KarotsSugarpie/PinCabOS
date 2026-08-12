#!/usr/bin/env python3

from __future__ import annotations

import os
import pwd
import grp
import shutil
import sys
from datetime import datetime
from pathlib import Path


TABLES_ROOT = Path("/home/pinball/Tables")
SYNC_SCRIPT = Path("/usr/local/sbin/pincabos-table-rom-assets-sync.py")
LOG_ROOT = Path("/opt/pincabos/logs")

ASSET_NAMES = (
    "roms",
    "altcolor",
    "altsound",
)

timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
LOG_ROOT.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_ROOT / f"fix-table-pinmame-layout-{timestamp}.log"


def log(message: str = "") -> None:
    print(message)

    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(message + "\n")


def fail(message: str) -> None:
    log(f"ERREUR : {message}")
    sys.exit(1)


try:
    PINBALL_UID = pwd.getpwnam("pinball").pw_uid
    PINBALL_GID = grp.getgrnam("pinball").gr_gid
except KeyError:
    PINBALL_UID = -1
    PINBALL_GID = -1


def chown_pinball(path: Path) -> None:
    if PINBALL_UID < 0 or PINBALL_GID < 0:
        return

    try:
        os.chown(
            path,
            PINBALL_UID,
            PINBALL_GID,
            follow_symlinks=False,
        )
    except (FileNotFoundError, PermissionError, NotImplementedError):
        pass


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    chown_pinball(path)


def find_case_insensitive(parent: Path, name: str) -> Path | None:
    if not parent.is_dir():
        return None

    wanted = name.casefold()

    try:
        for child in parent.iterdir():
            if child.name.casefold() == wanted:
                return child
    except OSError:
        return None

    return None


def merge_asset_directory(
    source: Path,
    destination: Path,
) -> tuple[int, int]:
    moved = 0
    conflicts = 0

    ensure_directory(destination)

    for source_root, directories, files in os.walk(
        source,
        topdown=False,
        followlinks=False,
    ):
        source_root_path = Path(source_root)
        relative = source_root_path.relative_to(source)
        destination_root = destination / relative

        ensure_directory(destination_root)

        for filename in files:
            source_file = source_root_path / filename
            existing = find_case_insensitive(destination_root, filename)

            if existing is not None:
                conflicts += 1
                log(
                    f"      CONSERVÉ À LA SOURCE, destination existante : "
                    f"{source_file}"
                )
                continue

            destination_file = destination_root / filename
            log(f"      DÉPLACEMENT : {source_file} -> {destination_file}")

            shutil.move(
                str(source_file),
                str(destination_file),
            )

            chown_pinball(destination_file)
            moved += 1

        for directory_name in directories:
            source_directory = source_root_path / directory_name

            try:
                source_directory.rmdir()
            except OSError:
                pass

    try:
        source.rmdir()
    except OSError:
        pass

    return moved, conflicts


def fix_existing_table_layout() -> dict[str, int]:
    stats = {
        "tables": 0,
        "tables_corrected": 0,
        "files_moved": 0,
        "conflicts": 0,
    }

    table_directories = sorted(
        [
            item
            for item in TABLES_ROOT.iterdir()
            if item.is_dir()
        ],
        key=lambda item: item.name.casefold(),
    )

    for table_directory in table_directories:
        stats["tables"] += 1
        table_changed = False

        log("---------------------------------------------------------------")
        log(f"TABLE : {table_directory.name}")

        pinmame_root = table_directory / "pinmame"

        for asset_name in ASSET_NAMES:
            wrong_location = table_directory / asset_name
            correct_location = pinmame_root / asset_name

            if not wrong_location.is_dir():
                log(f"  {asset_name} : rien à déplacer.")
                continue

            table_changed = True
            ensure_directory(pinmame_root)

            log(
                f"  Correction : {wrong_location} "
                f"-> {correct_location}"
            )

            moved, conflicts = merge_asset_directory(
                wrong_location,
                correct_location,
            )

            stats["files_moved"] += moved
            stats["conflicts"] += conflicts

            log(f"    Fichiers déplacés : {moved}")
            log(f"    Conflits conservés : {conflicts}")

        if table_changed:
            stats["tables_corrected"] += 1

    return stats


def patch_sync_script() -> Path | None:
    if not SYNC_SCRIPT.is_file():
        log(
            f"AVERTISSEMENT : script de synchronisation absent : "
            f"{SYNC_SCRIPT}"
        )
        return None

    original = SYNC_SCRIPT.read_text(encoding="utf-8")

    replacements = {
        'destination_roms = table_directory / "roms"':
            'destination_roms = table_directory / "pinmame" / "roms"',

        'destination_altcolor = table_directory / "altcolor"':
            'destination_altcolor = '
            'table_directory / "pinmame" / "altcolor"',

        'destination_altsound = table_directory / "altsound"':
            'destination_altsound = '
            'table_directory / "pinmame" / "altsound"',
    }

    patched = original

    for old_text, new_text in replacements.items():
        count = patched.count(old_text)

        if count != 1:
            fail(
                f"Patch arrêté : expression attendue trouvée "
                f"{count} fois dans {SYNC_SCRIPT} : {old_text}"
            )

        patched = patched.replace(old_text, new_text, 1)

    backup = SYNC_SCRIPT.with_name(
        f"{SYNC_SCRIPT.name}.bak-pinmame-layout-{timestamp}"
    )

    shutil.copy2(SYNC_SCRIPT, backup)
    SYNC_SCRIPT.write_text(patched, encoding="utf-8")

    chown_pinball(SYNC_SCRIPT)

    log("")
    log(f"Sauvegarde du script : {backup}")
    log(f"Script corrigé       : {SYNC_SCRIPT}")

    return backup


def validate_layout() -> tuple[int, int]:
    wrong_directories = 0
    correct_directories = 0

    for table_directory in TABLES_ROOT.iterdir():
        if not table_directory.is_dir():
            continue

        for asset_name in ASSET_NAMES:
            wrong_path = table_directory / asset_name
            correct_path = table_directory / "pinmame" / asset_name

            if wrong_path.exists():
                wrong_directories += 1
                log(f"RESTE À VÉRIFIER : {wrong_path}")

            if correct_path.exists():
                correct_directories += 1

    return wrong_directories, correct_directories


def main() -> None:
    log("===============================================================")
    log(" PINCABOS — CORRECTION STRUCTURE PINMAME DES TABLES")
    log("===============================================================")
    log(f"Tables  : {TABLES_ROOT}")
    log(f"Journal : {LOG_FILE}")
    log("")

    if not TABLES_ROOT.is_dir():
        fail(f"Dossier absent : {TABLES_ROOT}")

    stats = fix_existing_table_layout()
    patch_sync_script()

    wrong_directories, correct_directories = validate_layout()

    log("")
    log("===============================================================")
    log(" RÉSUMÉ")
    log("===============================================================")
    log(f"Tables analysées             : {stats['tables']}")
    log(f"Tables corrigées             : {stats['tables_corrected']}")
    log(f"Fichiers déplacés            : {stats['files_moved']}")
    log(f"Conflits non écrasés         : {stats['conflicts']}")
    log(f"Dossiers PinMAME détectés    : {correct_directories}")
    log(f"Anciens dossiers encore là   : {wrong_directories}")
    log("")

    if wrong_directories:
        log(
            "À VÉRIFIER : certains anciens dossiers contiennent encore "
            "des fichiers en conflit."
        )
    else:
        log("OK : aucun ancien dossier ROM/AltColor/AltSound ne reste.")

    log(f"Journal complet : {LOG_FILE}")
    log("===============================================================")


if __name__ == "__main__":
    main()
