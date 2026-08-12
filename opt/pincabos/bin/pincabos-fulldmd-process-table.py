#!/usr/bin/env python3
"""PinCabOS FullDMD : post-traitement sûr des tables importées ou existantes.

Lit uniquement les .directb2s, extrait les assets FullDMD dans Table/fulldmd,
calcule le layout avec la marge V3, puis synchronise le .ini homonyme de la table.
Ne modifie jamais les fichiers .vpx, .vbs ou .directb2s.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import pwd
import re
import subprocess
import sys
import time
from pathlib import Path

TABLES = Path('/home/pinball/Tables')
EXTRACTOR = Path('/opt/pincabos/bin/pincabos-fulldmd-extract-frame.py')
AUTO = Path('/opt/pincabos/bin/pincabos-fulldmd-autoarrange.py')
INI_HELPER = Path('/opt/pincabos/bin/pincabos-fulldmd-write-scoreview-ini.py')
LOG = Path('/opt/pincabos/logs/fulldmd-smart-import.log')
try:
    _pinball = pwd.getpwnam('pinball')
    PINBALL_UID = _pinball.pw_uid
    PINBALL_GID = _pinball.pw_gid
except KeyError:
    PINBALL_UID = PINBALL_GID = -1


def log(message: str) -> None:
    line = f'{time.strftime("%Y-%m-%d %H:%M:%S")} {message}'
    print(line, flush=True)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open('a', encoding='utf-8') as handle:
            handle.write(line + '\n')
    except OSError:
        pass


def is_fulldmd(b2s: Path) -> bool:
    try:
        raw = b2s.read_text(encoding='utf-8', errors='ignore')
    except OSError:
        return False
    attr = re.search(r'<DMDType\b[^>]*\bValue\s*=\s*["\']?3(?:["\'\s>/])', raw, re.I | re.S)
    element = re.search(r'<DMDType\b[^>]*>\s*3\s*</DMDType\s*>', raw, re.I | re.S)
    return bool(attr or element)


def same_name_vpx(table_dir: Path, b2s: Path) -> Path | None:
    wanted = b2s.stem.casefold()
    all_vpx = sorted((p for p in table_dir.iterdir() if p.is_file() and p.suffix.casefold() == '.vpx'), key=lambda p: p.name.casefold())
    for candidate in all_vpx:
        if candidate.stem.casefold() == wanted:
            return candidate
    return all_vpx[0] if len(all_vpx) == 1 else None


def env_value(path: Path, key: str) -> int | None:
    try:
        for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
            if line.startswith(key + '='):
                value = line.split('=', 1)[1].strip()
                return int(value)
    except (OSError, ValueError):
        return None
    return None


def chown_pinball(path: Path) -> None:
    if os.geteuid() != 0 or PINBALL_UID < 0:
        return
    try:
        os.chown(path, PINBALL_UID, PINBALL_GID)
    except OSError:
        pass


def process_b2s(b2s: Path, *, sync_ini: bool = True) -> tuple[bool, str]:
    if not b2s.is_file():
        return False, 'fichier B2S absent'
    if not is_fulldmd(b2s):
        return False, 'pas un FullDMD (DMDType=3 absent)'
    table_dir = b2s.parent
    assets = table_dir / 'fulldmd'
    png = assets / 'PinCabOS-FullDMD.png'
    frame = assets / 'PinCabOS-DMD-frame.env'
    manifest = assets / 'PinCabOS-FullDMD.sha256'
    layout = assets / 'PinCabOS-DMD-layout.env'
    try:
        digest = hashlib.sha256(b2s.read_bytes()).hexdigest()
    except OSError as exc:
        return False, f'lecture B2S impossible : {exc}'

    try:
        assets.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return False, f'création fulldmd impossible : {exc}'
    chown_pinball(assets)

    reusable = False
    try:
        reusable = png.is_file() and frame.is_file() and manifest.read_text(encoding='utf-8').strip() == digest
    except OSError:
        reusable = False

    if not reusable:
        result = subprocess.run(
            [str(EXTRACTOR), str(b2s), str(png), str(frame)],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode:
            return False, 'extraction impossible : ' + (result.stderr.strip() or result.stdout.strip() or 'sans détail')
        try:
            manifest.write_text(digest + '\n', encoding='utf-8')
        except OSError as exc:
            return False, f'écriture manifest impossible : {exc}'
        for item in (png, frame, manifest):
            chown_pinball(item)

    result = subprocess.run(
        [str(AUTO), '--image', str(png), '--table-dir', str(table_dir)],
        capture_output=True, text=True, timeout=150,
    )
    if result.returncode:
        return False, 'AutoArrange impossible : ' + (result.stderr.strip() or result.stdout.strip() or 'sans détail')
    if not layout.is_file():
        return False, 'AutoArrange n’a pas créé le layout ENV'

    x = env_value(layout, 'PINCABOS_DMD_X')
    y = env_value(layout, 'PINCABOS_DMD_Y')
    w = env_value(layout, 'PINCABOS_DMD_W')
    h = env_value(layout, 'PINCABOS_DMD_H')
    if x is None or y is None or not w or not h or w < 32 or h < 12:
        return False, 'layout DMD invalide'

    ini_result = 'sans INI associé'
    if sync_ini:
        vpx = same_name_vpx(table_dir, b2s)
        if vpx is not None:
            table_ini = vpx.with_suffix('.ini')
            result = subprocess.run(
                [str(INI_HELPER), '--ini', str(table_ini), '--x', str(x), '--y', str(y), '--width', str(w), '--height', str(h)],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode:
                return False, 'synchronisation INI impossible : ' + (result.stderr.strip() or result.stdout.strip() or 'sans détail')
            chown_pinball(table_ini)
            ini_result = table_ini.name

    return True, f'{"extrait" if not reusable else "réutilisé"}; layout {w}x{h}+{x}+{y}; INI {ini_result}'


def candidates_recent(minutes: int) -> list[Path]:
    cutoff = time.time() - max(1, minutes) * 60
    found: list[Path] = []
    for b2s in TABLES.rglob('*.directb2s'):
        try:
            if b2s.is_file() and b2s.stat().st_mtime >= cutoff and is_fulldmd(b2s):
                found.append(b2s)
        except OSError:
            continue
    return sorted(found, key=lambda p: str(p).casefold())


def candidates_all() -> list[Path]:
    return sorted((p for p in TABLES.rglob('*.directb2s') if p.is_file() and is_fulldmd(p)), key=lambda p: str(p).casefold())


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--all', action='store_true', help='Traite toutes les tables FullDMD déjà installées.')
    group.add_argument('--recent-minutes', type=int, help='Traite seulement les .directb2s FullDMD modifiés récemment.')
    group.add_argument('--b2s', type=Path, help='Traite un seul .directb2s FullDMD.')
    parser.add_argument('--no-sync-ini', action='store_true', help='N’écrit pas le .ini homonyme de la table.')
    args = parser.parse_args()

    if not TABLES.is_dir() or not EXTRACTOR.is_file() or not AUTO.is_file() or not INI_HELPER.is_file():
        log('ERREUR prérequis FullDMD absent.')
        return 2

    if args.all:
        rows = candidates_all()
        mode = 'tables existantes'
    elif args.recent_minutes is not None:
        rows = candidates_recent(args.recent_minutes)
        mode = f'récentes {args.recent_minutes} min'
    else:
        rows = [args.b2s.resolve()]
        mode = 'ciblée'

    log(f'FullDMD Smart Import : début {mode}, {len(rows)} table(s) candidate(s).')
    ok = failed = 0
    for b2s in rows:
        success, message = process_b2s(b2s, sync_ini=not args.no_sync_ini)
        name = str(b2s.relative_to(TABLES)) if b2s.is_relative_to(TABLES) else str(b2s)
        if success:
            ok += 1
            log(f'OK {name} — {message}')
        else:
            failed += 1
            log(f'ECHEC {name} — {message}')
    log(f'FullDMD Smart Import : terminé {ok} OK, {failed} échec(s).')
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
