#!/usr/bin/env python3
from __future__ import annotations

import os
import json
import re
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

TABLES_ROOT = Path('/home/pinball/Tables').resolve()
BACKUP_ROOT = Path('/var/lib/pincabos/native-b2s-prelaunch-backups')
SCREEN_CONFIG = Path('/opt/pincabos/config/screens/screens.json')


def screen_geometry(
    role: str,
    fallback_x: int,
    fallback_y: int,
    fallback_width: int,
    fallback_height: int,
) -> tuple[int, int, int, int]:
    """
    Retourne x, y, width, height pour un rôle PinCabOS.

    Source officielle:
      /opt/pincabos/config/screens/screens.json

    Si la configuration est absente ou invalide, l'ancien comportement
    reste disponible comme fallback.
    """
    fallback = (
        fallback_x,
        fallback_y,
        fallback_width,
        fallback_height,
    )

    try:
        config = json.loads(
            SCREEN_CONFIG.read_text(
                encoding='utf-8',
                errors='replace',
            )
        )

        screen = config.get(role)

        if not isinstance(screen, dict):
            raise ValueError(
                f"rôle {role!r} absent de screens.json"
            )

        x = int(screen.get('x'))
        y = int(screen.get('y'))
        width = int(screen.get('width'))
        height = int(screen.get('height'))

        if width <= 0 or height <= 0:
            raise ValueError(
                f"géométrie invalide {width}x{height}"
            )

        print(
            f"PINCABOS [B2S SCREEN] "
            f"{role}={width}x{height}+{x}+{y}"
        )

        return x, y, width, height

    except Exception as exc:
        x, y, width, height = fallback

        print(
            f"PINCABOS [B2S SCREEN] "
            f"AVERTISSEMENT {role}: {exc}; "
            f"fallback={width}x{height}+{x}+{y}"
        )

        return fallback


def find_table(argv: list[str]) -> Path | None:
    for raw in argv:
        if raw.casefold().endswith('.vpx'):
            table = Path(raw).resolve()
            try:
                table.relative_to(TABLES_ROOT)
            except ValueError:
                continue
            if table.is_file():
                return table
    return None


def has_pup(table: Path) -> bool:
    try:
        return any(child.is_dir() and child.name.casefold() in {'pupvideo', 'pupvideos', 'pinupvideo', 'pinupvideos'} for child in table.parent.iterdir())
    except OSError:
        return False


def is_native_fulldmd(table: Path) -> bool:
    b2s = table.with_suffix('.directb2s')
    if not b2s.is_file():
        return False
    data = b2s.read_bytes()
    for encoding in ('utf-8-sig', 'utf-16', 'utf-16-le', 'utf-16-be', 'latin-1'):
        text = data.decode(encoding, errors='ignore')
        kind = re.search(r'<DMDType\b[^>]*\bValue\s*=\s*["\']([^"\']+)', text, re.I | re.S)
        image = re.search(r'<DMDImage\b', text, re.I)
        if kind and kind.group(1).strip() in {'3', '4'} and image:
            return True
    return False


def patch_section(text: str, section: str, forced: dict[str, str], defaults: dict[str, str] | None = None) -> str:
    defaults = defaults or {}
    newline = '\r\n' if '\r\n' in text else '\n'
    lines = text.splitlines(keepends=True)
    start = None
    end = len(lines)
    for index, line in enumerate(lines):
        match = re.match(r'^\s*\[([^]]+)\]\s*$', line.strip())
        if match and match.group(1).strip().casefold() == section.casefold():
            start = index
            break
    if start is None:
        if lines and not lines[-1].endswith(('\n', '\r')):
            lines[-1] += newline
        if lines and lines[-1].strip():
            lines.append(newline)
        lines.append(f'[{section}]{newline}')
        values = {**forced, **defaults}
        lines.extend(f'{key} = {value}{newline}' for key, value in values.items())
        return ''.join(lines)
    for index in range(start + 1, len(lines)):
        if re.match(r'^\s*\[[^]]+\]\s*$', lines[index].strip()):
            end = index
            break
    existing: set[str] = set()
    for index in range(start + 1, end):
        item = re.match(r'^(\s*)([^;#][^=]*?)\s*=.*?(\r?\n)?$', lines[index])
        if not item:
            continue
        key = item.group(2).strip()
        existing.add(key.casefold())
        for wanted, value in forced.items():
            if key.casefold() == wanted.casefold():
                lines[index] = f'{item.group(1)}{wanted} = {value}{item.group(3) or newline}'
                break
    additions = [f'{key} = {value}{newline}' for key, value in forced.items() if key.casefold() not in existing]
    additions += [f'{key} = {value}{newline}' for key, value in defaults.items() if key.casefold() not in existing]
    if additions:
        lines[end:end] = additions
    return ''.join(lines)


def main() -> int:
    table = find_table(sys.argv[1:])

    if table is None:
        return 0

    # ---------------------------------------------------------
    # Le simple fait qu'un PuP-Pack existe ne doit PAS désactiver
    # le B2S lorsqu'on lance explicitement le mode Original.
    # ---------------------------------------------------------

    game_choice = (
        os.environ.get('PINCABOS_GAME_CHOICE', 'original')
        .strip()
        .casefold()
    )

    pup_enabled = (
        os.environ.get('PINCABOS_PUP_ENABLED', '0')
        .strip()
        .casefold()
    )

    actual_pup_mode = (
        game_choice in {'pup', 'puppack', 'pup-pack'}
        or pup_enabled in {'1', 'true', 'yes', 'on'}
    )

    if actual_pup_mode:
        print(
            f'PINCABOS [PUP] Mode PuP actif; '
            f'politique B2S native ignorée : {table.name}'
        )
        return 0

    b2s = table.with_suffix('.directb2s')

    if not b2s.is_file():
        print(
            f'PINCABOS [B2S] Aucun directb2s : {table.name}'
        )
        return 0

    # ---------------------------------------------------------
    # Géométrie officielle PinCabOS
    # ---------------------------------------------------------

    backglass_x, backglass_y, backglass_width, backglass_height = (
        screen_geometry(
            'backglass',
            3840,
            0,
            1920,
            1080,
        )
    )

    fulldmd_x, fulldmd_y, fulldmd_width, fulldmd_height = (
        screen_geometry(
            'fulldmd',
            5760,
            0,
            1920,
            1200,
        )
    )

    ini = table.with_suffix('.ini')

    text = (
        ini.read_text(
            encoding='utf-8',
            errors='surrogateescape',
        )
        if ini.is_file()
        else ''
    )

    original = text

    # ---------------------------------------------------------
    # TOUS les directB2S :
    # positionner correctement le backglass physique.
    #
    # On prépare aussi la géométrie DMD. Si le B2S n'a pas de
    # DMD intégré, ces valeurs restent simplement inutilisées.
    # ---------------------------------------------------------

    text = patch_section(
        text,
        'Plugin.B2SLegacy',
        {
            'Enable': '1',

            'B2SBackglassWidth': str(backglass_width),
            'B2SBackglassHeight': str(backglass_height),
            'B2SBackglassX': str(backglass_x),
            'B2SBackglassY': str(backglass_y),

            'B2SDMDWidth': str(fulldmd_width),
            'B2SDMDHeight': str(fulldmd_height),
            'B2SDMDX': str(fulldmd_x),
            'B2SDMDY': str(fulldmd_y),

            'B2SDMDRotation': '0',
        },
    )

    native_fulldmd = is_native_fulldmd(table)

    # ---------------------------------------------------------
    # Seulement pour les directB2S FullDMD natifs type 3/4 :
    # politique ScoreView / B2SLegacy avancée.
    # ---------------------------------------------------------

    if native_fulldmd:

        text = patch_section(
            text,
            'ScoreView',
            {
                'ScoreViewOutput': '1',
                'ScoreViewDisplay': '',
                'ScoreViewFullScreen': '0',

                'ScoreViewWndX': '0',
                'ScoreViewWndY': '0',
                'ScoreViewWidth': '1920',
                'ScoreViewHeight': '1200',

                'ScoreViewFSWidth': '1920',
                'ScoreViewFSHeight': '1200',

                'Priority.ScoreView': '0',
                'Priority.B2SLegacyDMD': '2',
            },
        )

        text = patch_section(
            text,
            'Plugin.ScoreView',
            {
                'Enable': '0',
            },
        )

        text = patch_section(
            text,
            'Plugin.B2SLegacy',
            {
                'Enable': '1',

                'B2SHideGrill': '1',
                'B2SHideB2SBackglass': '0',
                'B2SHideB2SDMD': '0',
                'B2SHideDMD': '1',
                'B2SDualMode': '0',

                'ScoreViewDMDOverlay': '1',

                'B2SBackglassWidth': str(backglass_width),
                'B2SBackglassHeight': str(backglass_height),
                'B2SBackglassX': str(backglass_x),
                'B2SBackglassY': str(backglass_y),

                'B2SDMDWidth': str(fulldmd_width),
                'B2SDMDHeight': str(fulldmd_height),
                'B2SDMDX': str(fulldmd_x),
                'B2SDMDY': str(fulldmd_y),

                'B2SDMDRotation': '0',
            },
            {
                'ScoreViewDMDAutoPos': '1',
                'ScoreViewDMDX': '0',
                'ScoreViewDMDY': '0',
                'ScoreViewDMDW': '640',
                'ScoreViewDMDH': '160',
            },
        )

    # ---------------------------------------------------------
    # Rien à écrire
    # ---------------------------------------------------------

    if text == original:

        if native_fulldmd:
            print(
                f'PINCABOS [B2S FULLDMD] '
                f'Configuration déjà correcte : {table.name}'
            )
        else:
            print(
                f'PINCABOS [B2S] '
                f'Géométrie déjà correcte : {table.name}'
            )

        return 0

    # ---------------------------------------------------------
    # Backup
    # ---------------------------------------------------------

    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')

    safe = (
        re.sub(
            r'[^A-Za-z0-9._-]+',
            '_',
            table.stem,
        ).strip('_')
        or 'table'
    )

    backup = BACKUP_ROOT / f'{stamp}-{safe}'
    backup.mkdir(parents=True, exist_ok=False)

    if ini.is_file():
        shutil.copy2(
            ini,
            backup / 'table.ini',
        )
    else:
        (
            backup / 'table.ini.absent'
        ).write_text(
            'absent\n',
            encoding='utf-8',
        )

    # ---------------------------------------------------------
    # Écriture atomique
    # ---------------------------------------------------------

    fd, temporary = tempfile.mkstemp(
        prefix=f'.{ini.name}.tmp.',
        dir=ini.parent,
    )

    try:
        with os.fdopen(
            fd,
            'w',
            encoding='utf-8',
            errors='surrogateescape',
        ) as handle:
            handle.write(text)

        os.chown(
            temporary,
            1000,
            1000,
        )

        os.chmod(
            temporary,
            0o664,
        )

        os.replace(
            temporary,
            ini,
        )

    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass

    if native_fulldmd:
        kind = 'B2S FULLDMD'
    else:
        kind = 'B2S'

    print(
        f'PINCABOS [{kind}] '
        f'Backglass={backglass_width}x{backglass_height}'
        f'+{backglass_x}+{backglass_y} '
        f'FullDMD={fulldmd_width}x{fulldmd_height}'
        f'+{fulldmd_x}+{fulldmd_y} '
        f'table={table.name} '
        f'backup={backup}'
    )

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
