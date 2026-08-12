#!/usr/bin/env python3
# PinCabOS-File created by Karots Sugarpie
import os
import re
import shutil
from pathlib import Path

BASE = Path("/opt/pincabos")
TABLES = BASE / "vpinball" / "Tables"

STANDARD_DIRS = [
    "table",
    "media",
    "music",
    "roms",
    "pupvideos",
    "altcolor",
    "altsound",
    "pinmame",
    "pinmame/roms",
    "pinmame/altcolor",
    "pinmame/altsound",
    "pinmame/cfg",
    "pinmame/nvram",
    "pinmame/ini",
    "dmd",
    "b2s",
    "scripts",
    "config",
    "docs",
    "extras",
]

MUSIC_EXTS = {".mp3", ".wav", ".ogg", ".flac", ".mid", ".midi"}
MEDIA_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".avi", ".mov", ".mkv"}
SCRIPT_EXTS = {".vbs"}
CONFIG_EXTS = {".ini", ".pov", ".res", ".cfg"}
ALTCOLOR_EXTS = {".pac", ".pal", ".vni", ".serum"}


def safe_name(value):
    value = str(value or "").strip()
    value = re.sub(r'[\\/:"*?<>|]+', " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value or "Imported Table"


def ensure_table(table_name):
    table_dir = TABLES / safe_name(table_name)
    table_dir.mkdir(parents=True, exist_ok=True)

    for d in STANDARD_DIRS:
        (table_dir / d).mkdir(parents=True, exist_ok=True)

    return table_dir


def copy_or_move(src, dst):
    src = Path(src)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)

    if dst.exists():
        stem = dst.stem
        suffix = dst.suffix
        i = 1
        while True:
            candidate = dst.with_name(f"{stem}-{i}{suffix}")
            if not candidate.exists():
                dst = candidate
                break
            i += 1

    shutil.move(str(src), str(dst))
    return dst


def latest_table_dir():
    if not TABLES.exists():
        return None

    dirs = [p for p in TABLES.iterdir() if p.is_dir()]
    if not dirs:
        return None

    return max(dirs, key=lambda p: p.stat().st_mtime)


def classify_file(path):
    p = Path(path)
    s = p.suffix.lower()
    name = p.name.lower()

    if s == ".vpx":
        return "table"
    if s == ".directb2s":
        return "b2s"
    if s == ".zip":
        return "roms"
    if s in ALTCOLOR_EXTS:
        return "altcolor"
    if s in MUSIC_EXTS:
        return "music"
    if s in MEDIA_EXTS:
        return "media"
    if s in SCRIPT_EXTS:
        return "scripts"
    if s in CONFIG_EXTS:
        return "config"
    if "ultradmd" in name or p.parent.name.lower().endswith(".ultradmd"):
        return "dmd"

    return "extras"


def move_legacy_into_table(table_dir):
    moved = []

    legacy_roots = [
        (BASE / "pupvideos", table_dir / "pupvideos"),
        (BASE / "vpinball" / "PinMAME" / "roms", table_dir / "pinmame" / "roms"),
        (BASE / "vpinball" / "PinMAME" / "altcolor", table_dir / "pinmame" / "altcolor"),
        (BASE / "vpinball" / "PinMAME" / "altsound", table_dir / "pinmame" / "altsound"),
        (BASE / "vpinball" / "Music", table_dir / "music"),
        (BASE / "ultradmd", table_dir / "dmd"),
        (BASE / "flexdmd", table_dir / "dmd"),
    ]

    for src_root, dst_root in legacy_roots:
        if not src_root.exists():
            continue

        for item in sorted(src_root.iterdir()):
            # Ne pas déplacer les dossiers système vides sans contenu utile.
            try:
                if item.is_dir() and not any(item.rglob("*")):
                    continue
            except Exception:
                pass

            dest = dst_root / item.name
            final = copy_or_move(item, dest)
            moved.append((str(item), str(final)))

    # Nettoyer les legacy vides uniquement.
    for src_root, _ in legacy_roots:
        try:
            if src_root.exists() and src_root.is_dir() and not any(src_root.iterdir()):
                src_root.rmdir()
        except Exception:
            pass

    return moved



def cleanup_import_work():
    """
    Nettoie les dossiers temporaires d'import après normalisation.

    Chemins autorisés uniquement:
    - /home/pinball/Downloads/work
    - /home/pinball/Downloads/work
    """
    work_roots = [
        BASE / "import" / "work",
        BASE / "imports" / "work",
    ]

    allowed = {
        "/home/pinball/Downloads/work",
        "/home/pinball/Downloads/work",
    }

    removed = []

    for work in work_roots:
        if not work.exists() or not work.is_dir():
            continue

        if str(work) not in allowed:
            print(f"REFUS cleanup_import_work chemin inattendu: {work}")
            continue

        for item in sorted(work.iterdir()):
            removed.append(str(item))
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            else:
                try:
                    item.unlink()
                except FileNotFoundError:
                    pass
                except IsADirectoryError:
                    shutil.rmtree(item, ignore_errors=True)

    return removed


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", default="")
    args = ap.parse_args()

    table_dir = ensure_table(args.table) if args.table else latest_table_dir()

    if not table_dir:
        print("Aucune table portable trouvée.")
        return 0

    for d in STANDARD_DIRS:
        (table_dir / d).mkdir(parents=True, exist_ok=True)

    moved = move_legacy_into_table(table_dir)
    cleaned_work = cleanup_import_work()

    print("============================================================")
    print(" PinCabOS post-import portable normalize")
    print("============================================================")
    print(f"Table: {table_dir}")

    if moved:
        print()
        print("Déplacements legacy -> portable:")
        for src, dst in moved:
            print(f" - {src} -> {dst}")
    else:
        print("Aucun legacy à déplacer.")

    print()
    if cleaned_work:
        print("Nettoyage /home/pinball/Downloads/work:")
        for item in cleaned_work:
            print(f" - supprimé: {item}")
    else:
        print("Nettoyage /home/pinball/Downloads/work: rien à supprimer.")

    try:
        shutil.chown(table_dir, user="pinball", group="pinball")
    except Exception:
        pass

    os.system(f"chown -R pinball:pinball {str(table_dir)!r}")
    os.system(f"chmod -R u+rwX,g+rwX,o+rX {str(table_dir)!r}")

    return 0



# PINCABOS_TABLE_TREE_IMPORT_HOOK_V3
import atexit as _pco_tree_atexit
import subprocess as _pco_tree_subprocess


def _pco_tree_after_import():
    try:
        _pco_tree_subprocess.run(
            ['/opt/pincabos/tools/pincabos-table-tree.sh', "--apply", "--quiet"],
            timeout=600,
            check=False,
        )
    except Exception:
        pass


_pco_tree_atexit.register(_pco_tree_after_import)

if __name__ == "__main__":
    raise SystemExit(main())
