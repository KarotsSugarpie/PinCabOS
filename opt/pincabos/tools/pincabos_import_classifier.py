#!/usr/bin/env python3
# PinCabOS Import ZIP Classifier
# Reconstruction compatible avec la version historique PinCabOS.
from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp'}
VIDEO_EXTS = {'.mp4', '.webm', '.avi', '.mov', '.mkv'}
AUDIO_EXTS = {'.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac', '.wma', '.mid', '.midi'}
ROM_EXTS = {'.zip'}
TABLE_EXTS = {'.vpx', '.directb2s', '.info'}

MEDIA_NAMES = {
    'audio.mp3', 'audio.wav',
    'bg.png', 'bg.jpg', 'bg.jpeg', 'bg.webp',
    'cab.png', 'cab.jpg', 'cab.jpeg', 'cab.webp',
    'dmd.png', 'dmd.jpg', 'dmd.jpeg', 'dmd.webp',
    'flyer.png', 'flyer.jpg', 'flyer.jpeg', 'flyer.webp',
    'realdmd.png', 'realdmd.jpg', 'realdmd.jpeg', 'realdmd.webp',
    'table.png', 'table.jpg', 'table.jpeg', 'table.webp', 'table.mp4', 'table.webm',
    'wheel.png', 'wheel.jpg', 'wheel.jpeg', 'wheel.webp',
    'logo.png', 'logo.jpg', 'logo.jpeg', 'logo.webp',
}

MEDIA_KEYWORDS = {
    'wheel', 'backglass', 'playfield', 'table', 'dmd', 'fulldmd',
    'realdmd', 'flyer', 'logo', 'topper', 'bg', 'cab', 'media'
}


def _safe_members(zip_path: Path) -> list[str]:
    with zipfile.ZipFile(zip_path, 'r') as archive:
        return [
            name for name in archive.namelist()
            if name
            and not name.endswith('/')
            and '__MACOSX/' not in name
            and not Path(name).name.startswith('._')
        ]


def analyze_zip(zip_path: str | Path) -> dict:
    zp = Path(zip_path)
    if not zp.exists() or not zp.is_file():
        return {'ok': False, 'error': f'zip introuvable: {zp}'}

    try:
        members = _safe_members(zp)
    except Exception as error:
        return {'ok': False, 'error': f'zip illisible: {error}'}

    counts = {
        'total': len(members),
        'audio': 0,
        'image': 0,
        'video': 0,
        'media_named': 0,
        'media_keyword': 0,
        'nested_zip': 0,
        'table': 0,
        'other': 0,
    }

    samples = {
        'audio': [],
        'image': [],
        'video': [],
        'media_named': [],
        'nested_zip': [],
        'table': [],
        'other': [],
    }

    for member in members:
        name = Path(member).name
        lower_name = name.lower()
        lower_path = member.lower()
        ext = Path(name).suffix.lower()
        matched = False

        if ext in AUDIO_EXTS:
            counts['audio'] += 1
            if len(samples['audio']) < 8:
                samples['audio'].append(member)
            matched = True

        if ext in IMAGE_EXTS:
            counts['image'] += 1
            if len(samples['image']) < 8:
                samples['image'].append(member)
            matched = True

        if ext in VIDEO_EXTS:
            counts['video'] += 1
            if len(samples['video']) < 8:
                samples['video'].append(member)
            matched = True

        if lower_name in MEDIA_NAMES:
            counts['media_named'] += 1
            if len(samples['media_named']) < 8:
                samples['media_named'].append(member)
            matched = True

        if any(keyword in lower_path for keyword in MEDIA_KEYWORDS):
            counts['media_keyword'] += 1
            matched = True

        if ext in ROM_EXTS:
            counts['nested_zip'] += 1
            if len(samples['nested_zip']) < 8:
                samples['nested_zip'].append(member)
            matched = True

        if ext in TABLE_EXTS:
            counts['table'] += 1
            if len(samples['table']) < 8:
                samples['table'].append(member)
            matched = True

        if not matched:
            counts['other'] += 1
            if len(samples['other']) < 8:
                samples['other'].append(member)

    recommendation = 'ask'
    reason = 'contenu ambigu'

    if (
        counts['nested_zip'] == 0
        and counts['audio'] >= 2
        and counts['image'] == 0
        and counts['video'] == 0
        and counts['table'] == 0
    ):
        recommendation = 'music'
        reason = 'plusieurs fichiers audio, pas de médias frontend/table'
    elif (
        counts['audio'] >= 2
        and counts['media_named'] == 0
        and counts['table'] == 0
        and counts['image'] <= 2
    ):
        recommendation = 'music'
        reason = 'pack audio probablement music'
    elif (
        counts['media_named'] >= 1
        or counts['media_keyword'] >= 2
        or counts['image'] + counts['video'] >= 3
    ):
        recommendation = 'medias'
        reason = 'fichiers médias frontend reconnus'
    elif counts['nested_zip'] == 0 and counts['total'] == 1 and zp.suffix.lower() == '.zip':
        recommendation = 'rom'
        reason = 'zip unique externe possiblement ROM PinMAME'
    elif counts['nested_zip'] >= 1 and counts['audio'] == 0 and counts['image'] == 0:
        recommendation = 'rom'
        reason = 'zip contenant zip(s), possiblement pack ROM'
    elif counts['table'] >= 1:
        recommendation = 'ask'
        reason = 'zip contient une table ou des fichiers mixtes'

    return {
        'ok': True,
        'zip': str(zp),
        'recommendation': recommendation,
        'reason': reason,
        'counts': counts,
        'samples': samples,
        'choices': ['rom', 'medias', 'music', 'ignore'],
    }


def ensure_table_layout(table_dir: str | Path) -> None:
    table = Path(table_dir)
    (table / 'medias').mkdir(parents=True, exist_ok=True)
    (table / 'music').mkdir(parents=True, exist_ok=True)
    (table / 'pinmame' / 'roms').mkdir(parents=True, exist_ok=True)
    (table / 'pinmame' / 'cfg').mkdir(parents=True, exist_ok=True)
    (table / 'pinmame' / 'ini').mkdir(parents=True, exist_ok=True)
    (table / 'pinmame' / 'nvram').mkdir(parents=True, exist_ok=True)


def import_zip_by_choice(zip_path: str | Path, table_dir: str | Path, choice: str) -> dict:
    zp = Path(zip_path)
    table = Path(table_dir)
    choice = (choice or '').strip().lower()

    if choice not in {'rom', 'medias', 'music', 'ignore'}:
        return {'ok': False, 'error': f'choix invalide: {choice}'}

    if not zp.exists() or not zp.is_file():
        return {'ok': False, 'error': f'zip introuvable: {zp}'}

    ensure_table_layout(table)

    if choice == 'ignore':
        return {'ok': True, 'choice': choice, 'imported': []}

    imported: list[str] = []

    if choice == 'rom':
        destination = table / 'pinmame' / 'roms' / zp.name
        if destination.exists():
            destination.unlink()
        shutil.copy2(zp, destination)
        imported.append(str(destination))
        return {'ok': True, 'choice': choice, 'imported': imported}

    target_dir = table / choice
    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(zp, 'r') as archive:
            for member in archive.namelist():
                if not member or member.endswith('/') or '__MACOSX/' in member:
                    continue

                name = Path(member).name
                if not name or name.startswith('._'):
                    continue

                destination = target_dir / name
                with archive.open(member) as source, destination.open('wb') as output:
                    shutil.copyfileobj(source, output)
                imported.append(str(destination))
    except Exception as error:
        return {'ok': False, 'error': str(error)}

    return {'ok': True, 'choice': choice, 'imported': imported}


def normalize_table_layout(table_dir: str | Path) -> dict:
    table = Path(table_dir)
    ensure_table_layout(table)
    moved: list[list[str]] = []

    known_frontend_audio = {'audio.mp3', 'audio.wav', 'bgmusic.mp3', 'background.mp3'}

    for source in list(table.rglob('*')):
        if not source.is_file():
            continue

        relative = source.relative_to(table)
        parts = set(relative.parts[:-1])
        ext = source.suffix.lower()
        name = source.name.lower()

        if 'pinmame' in parts or 'medias' in parts or 'music' in parts:
            continue

        destination = None
        if ext == '.zip':
            destination = table / 'pinmame' / 'roms' / source.name
        elif ext in AUDIO_EXTS:
            destination = (
                table / 'medias' / source.name
                if name in known_frontend_audio
                else table / 'music' / source.name
            )

        if destination:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                destination.unlink()
            shutil.move(str(source), str(destination))
            moved.append([str(source), str(destination)])

    for directory in sorted(table.rglob('*'), key=lambda item: len(str(item)), reverse=True):
        if directory.is_dir():
            try:
                directory.rmdir()
            except Exception:
                pass

    return {'ok': True, 'moved': moved}


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description='Analyse un ZIP pour Smart Import PinCabOS.')
    parser.add_argument('zip')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()

    result = analyze_zip(args.zip)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get('ok') else 1



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

if __name__ == '__main__':
    raise SystemExit(main())
