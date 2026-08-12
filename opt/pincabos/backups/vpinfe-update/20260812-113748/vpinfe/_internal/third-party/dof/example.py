#!/usr/bin/env python3
"""Minimal DOF runner: init ROM and keep running until 'q' is pressed."""

import argparse
import glob
import os
import random
import re
import select
import sys
import threading

import dof


def log_handler(level: dof.LogLevel, message: str) -> None:
    tag = {
        dof.LogLevel.INFO: '[INFO ]',
        dof.LogLevel.WARN: '[WARN ]',
        dof.LogLevel.ERROR: '[ERROR]',
        dof.LogLevel.DEBUG: '[DEBUG]',
    }.get(level, '[?????]')
    print(f'{tag} {message}')


def _default_base_path() -> str:
    home = os.path.expanduser('~')
    if sys.platform == 'win32':
        appdata = os.environ.get('APPDATA', home)
        return os.path.join(appdata, 'VPinballX', '10.8')
    if sys.platform == 'darwin':
        return os.path.join(home, 'Library', 'Application Support', 'VPinballX', '10.8')
    return os.path.join(home, '.local', 'share', 'VPinballX', '10.8')


def _wait_for_quit_key() -> None:
    if not sys.stdin.isatty() or os.name != 'posix':
        while True:
            if input("Type 'q' then Enter to quit: ").strip().lower() == 'q':
                return

    import termios
    import tty

    fd = sys.stdin.fileno()
    old_attrs = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        print("Press 'q' to quit.")
        while True:
            ready, _, _ = select.select([sys.stdin], [], [], 0.2)
            if not ready:
                continue
            ch = sys.stdin.read(1)
            if ch.lower() == 'q':
                return
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)


def _run_random_e_effects(
    d: dof.DOF,
    stop_event: threading.Event,
    random_min: int,
    random_max: int,
    on_value: int,
    interval_sec: float,
) -> None:
    last_number: int | None = None
    try:
        while not stop_event.wait(interval_sec):
            number = random.randint(random_min, random_max)
            if last_number is not None:
                d.data_receive('E', last_number, 0)
            d.data_receive('E', number, on_value)
            last_number = number
    finally:
        if last_number is not None:
            d.data_receive('E', last_number, 0)


def _parse_trigger_tokens(token_expr: str) -> list[tuple[str, int]]:
    settings = [s.strip() for s in token_expr.split('/') if s.strip()]
    out: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for setting in settings:
        if setting.startswith('('):
            continue
        trigger = setting.split(' ', 1)[0].strip()
        trigger_parts = [p.strip() for p in trigger.split('|') if p.strip()]
        for part in trigger_parts:
            m = re.fullmatch(r'([A-Za-z])(\d+)', part)
            if not m:
                continue
            event = (m.group(1).upper(), int(m.group(2)))
            if event not in seen:
                seen.add(event)
                out.append(event)
    return out


def _split_csv_with_paren_guard(line: str) -> list[str]:
    parts = []
    depth = 0
    start = 0
    for idx, ch in enumerate(line):
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth = max(0, depth - 1)
        elif ch == ',' and depth == 0:
            parts.append(line[start:idx].strip())
            start = idx + 1
    parts.append(line[start:].strip())
    return parts


def _resolve_config_ini(base_path: str) -> str:
    cfg_dir = os.path.join(base_path, 'directoutputconfig')
    if not os.path.isdir(cfg_dir):
        raise FileNotFoundError(f'Config directory not found: {cfg_dir}')

    preferred = [
        os.path.join(cfg_dir, 'directoutputconfig30.ini'),
        os.path.join(cfg_dir, 'directoutputconfig40.ini'),
        os.path.join(cfg_dir, 'directoutputconfig.ini'),
        os.path.join(cfg_dir, 'ledcontrol.ini'),
    ]
    for path in preferred:
        if os.path.isfile(path):
            return path

    candidates = sorted(glob.glob(os.path.join(cfg_dir, 'directoutputconfig*.ini')))
    if not candidates:
        candidates = sorted(glob.glob(os.path.join(cfg_dir, 'ledcontrol*.ini')))
    if not candidates:
        raise FileNotFoundError(f'No directoutputconfig*.ini or ledcontrol*.ini found in {cfg_dir}')
    return candidates[0]


def _find_rom_row(ini_path: str, rom_key: str) -> list[str]:
    in_config = False
    with open(ini_path, 'r', encoding='utf-8', errors='ignore') as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            if line.startswith('[') and line.endswith(']'):
                section = line.lower()
                in_config = section in ('[config dof]', '[config outs]')
                continue
            if not in_config or line.startswith('#'):
                continue
            cols = _split_csv_with_paren_guard(line)
            if cols and cols[0].strip().strip('"').lower() == rom_key.lower():
                return cols
    raise ValueError(f'ROM "{rom_key}" not found in {ini_path} [Config DOF]/[Config outs]')


def _collect_rom_tokens(ini_path: str, rom_key: str) -> list[tuple[str, int]]:
    row = _find_rom_row(ini_path, rom_key)
    out: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for col_expr in row[1:]:
        for event in _parse_trigger_tokens(col_expr):
            if event not in seen:
                seen.add(event)
                out.append(event)
    return out


def _run_token_sequence(
    d: dof.DOF,
    stop_event: threading.Event,
    tokens: list[tuple[str, int]],
    on_value: int,
    on_sec: float,
    off_sec: float,
    loop: bool,
) -> None:
    try:
        while not stop_event.is_set():
            for type_char, number in tokens:
                if stop_event.is_set():
                    return
                d.data_receive(type_char, number, on_value)
                if stop_event.wait(on_sec):
                    d.data_receive(type_char, number, 0)
                    return
                d.data_receive(type_char, number, 0)
                if stop_event.wait(off_sec):
                    return
            if not loop:
                return
    finally:
        # Best-effort cleanup: force all parsed events OFF.
        for type_char, number in tokens:
            try:
                d.data_receive(type_char, number, 0)
            except Exception:
                pass


def _run_event_range_sequence(
    d: dof.DOF,
    stop_event: threading.Event,
    type_char: str,
    start_number: int,
    end_number: int,
    on_value: int,
    on_sec: float,
    off_sec: float,
    loop: bool,
) -> None:
    try:
        while not stop_event.is_set():
            for number in range(start_number, end_number + 1):
                if stop_event.is_set():
                    return
                d.data_receive(type_char, number, on_value)
                if stop_event.wait(on_sec):
                    d.data_receive(type_char, number, 0)
                    return
                d.data_receive(type_char, number, 0)
                if stop_event.wait(off_sec):
                    return
            if not loop:
                return
    finally:
        # Best-effort cleanup: force the full range OFF.
        for number in range(start_number, end_number + 1):
            try:
                d.data_receive(type_char, number, 0)
            except Exception:
                pass


def _parse_event_arg(event_text: str) -> tuple[str, int]:
    event = event_text.strip().upper()
    m = re.fullmatch(r'([A-Z])(\d+)', event)
    if not m:
        raise ValueError(
            f'Invalid event "{event_text}". Expected format like E905, S27, or W1.'
        )
    return m.group(1), int(m.group(2))


def _parse_event_range_arg(range_text: str) -> tuple[str, int, int]:
    text = range_text.strip().upper()
    m = re.fullmatch(r'([A-Z])(\d+)\s*-\s*([A-Z])(\d+)', text)
    if not m:
        raise ValueError(
            f'Invalid event range "{range_text}". Expected format like E900-E990.'
        )
    start_type, start_number, end_type, end_number = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
    if start_type != end_type:
        raise ValueError(
            f'Invalid event range "{range_text}". Start and end event types must match.'
        )
    if start_number > end_number:
        raise ValueError(
            f'Invalid event range "{range_text}". Start number must be <= end number.'
        )
    return start_type, start_number, end_number


def main() -> None:
    parser = argparse.ArgumentParser(description='Initialize DOF for a ROM and hold until quit key.')
    parser.add_argument('--rom', required=True, help='ROM name/key (spaces are normalized to underscores)')
    parser.add_argument('--base-path', default='', help='DOF base path (default: platform VPinballX/10.8)')
    parser.add_argument('--debug', action='store_true', help='Enable DEBUG-level logging')
    parser.add_argument(
        '--random-e',
        action='store_true',
        help='Continuously fire random E events until quit (JS-style random fallback behavior).',
    )
    parser.add_argument(
        '--random-min',
        type=int,
        default=901,
        help='Minimum E number for --random-e (default: 901, matching the JS snippet behavior).',
    )
    parser.add_argument(
        '--random-max',
        type=int,
        default=990,
        help='Maximum E number for --random-e (default: 990).',
    )
    parser.add_argument(
        '--random-on-value',
        type=int,
        default=1,
        help='ON value used for each random E event (default: 1).',
    )
    parser.add_argument(
        '--random-interval-sec',
        type=float,
        default=0.25,
        help='Seconds between random E updates (default: 0.25).',
    )
    parser.add_argument(
        '--play-rom-tokens',
        action='store_true',
        help='Parse tokens from the ROM row in directoutputconfig*.ini and play them sequentially.',
    )
    parser.add_argument(
        '--event-range',
        default='',
        help='Play a numeric event range in sequence, like E900-E990.',
    )
    parser.add_argument(
        '--event',
        default='',
        help='Fire one event once, like E905 or S27, then exit.',
    )
    parser.add_argument(
        '--event-on-sec',
        type=float,
        default=0.5,
        help='Seconds the one-shot --event stays ON before turning OFF (default: 0.5).',
    )
    parser.add_argument(
        '--event-on-value',
        type=int,
        default=1,
        help='ON value used for one-shot --event mode (default: 1).',
    )
    parser.add_argument('--config-ini', default='', help='Optional explicit ini path for --play-rom-tokens')
    parser.add_argument(
        '--token-on-sec',
        type=float,
        default=0.6,
        help='Seconds each parsed token stays ON in --play-rom-tokens mode (default: 0.6).',
    )
    parser.add_argument(
        '--token-off-sec',
        type=float,
        default=0.2,
        help='Seconds to wait after each token turns OFF in --play-rom-tokens mode (default: 0.2).',
    )
    parser.add_argument(
        '--token-on-value',
        type=int,
        default=255,
        help='ON value used in --play-rom-tokens mode (default: 255).',
    )
    parser.add_argument(
        '--token-loop',
        action='store_true',
        help='Loop parsed tokens continuously in --play-rom-tokens mode until quit.',
    )
    parser.add_argument(
        '--range-on-sec',
        type=float,
        default=0.2,
        help='Seconds each event stays ON in --event-range mode (default: 0.2).',
    )
    parser.add_argument(
        '--range-off-sec',
        type=float,
        default=0.0,
        help='Seconds to wait after each event turns OFF in --event-range mode (default: 0.0).',
    )
    parser.add_argument(
        '--range-on-value',
        type=int,
        default=1,
        help='ON value used in --event-range mode (default: 1).',
    )
    parser.add_argument(
        '--range-loop',
        action='store_true',
        help='Loop the --event-range continuously until quit.',
    )
    args = parser.parse_args()
    enabled_modes = sum(bool(mode) for mode in (args.random_e, args.play_rom_tokens, args.event_range, args.event))
    if enabled_modes > 1:
        parser.error('--random-e, --play-rom-tokens, --event-range, and --event are mutually exclusive')
    if args.random_min < 0:
        parser.error('--random-min must be >= 0')
    if args.random_max < 0:
        parser.error('--random-max must be >= 0')
    if args.random_min > args.random_max:
        parser.error('--random-min must be <= --random-max')
    if args.random_on_value < 0:
        parser.error('--random-on-value must be >= 0')
    if args.random_interval_sec <= 0:
        parser.error('--random-interval-sec must be > 0')
    if args.event_on_sec <= 0:
        parser.error('--event-on-sec must be > 0')
    if args.event_on_value < 0:
        parser.error('--event-on-value must be >= 0')
    if args.token_on_sec <= 0:
        parser.error('--token-on-sec must be > 0')
    if args.token_off_sec < 0:
        parser.error('--token-off-sec must be >= 0')
    if args.token_on_value < 0:
        parser.error('--token-on-value must be >= 0')
    if args.range_on_sec <= 0:
        parser.error('--range-on-sec must be > 0')
    if args.range_off_sec < 0:
        parser.error('--range-off-sec must be >= 0')
    if args.range_on_value < 0:
        parser.error('--range-on-value must be >= 0')

    dof.set_log_callback(log_handler)
    dof.set_log_level(dof.LogLevel.DEBUG if args.debug else dof.LogLevel.INFO)
    dof.set_base_path(args.base_path if args.base_path else _default_base_path())

    rom_key = args.rom.strip().replace(' ', '_')

    with dof.DOF() as d:
        print(f'Initializing ROM: {args.rom} (key={rom_key})')
        d.init(rom_key)
        if args.event:
            try:
                type_char, number = _parse_event_arg(args.event)
            except ValueError as exc:
                parser.error(str(exc))
            print(
                'One-shot event mode enabled: '
                f'event={type_char}{number}, on_value={args.event_on_value}, '
                f'on_sec={args.event_on_sec:.3f}'
            )
            d.data_receive(type_char, number, args.event_on_value)
            try:
                threading.Event().wait(args.event_on_sec)
            finally:
                d.data_receive(type_char, number, 0)
                d.finish()
            print('Done.')
            return
        random_thread: threading.Thread | None = None
        random_stop_event = threading.Event()
        token_thread: threading.Thread | None = None
        token_stop_event = threading.Event()
        range_thread: threading.Thread | None = None
        range_stop_event = threading.Event()
        if args.random_e:
            print(
                'Random E mode enabled: '
                f'E{args.random_min}-E{args.random_max}, '
                f'on_value={args.random_on_value}, '
                f'interval={args.random_interval_sec:.3f}s'
            )
            random_thread = threading.Thread(
                target=_run_random_e_effects,
                args=(
                    d,
                    random_stop_event,
                    args.random_min,
                    args.random_max,
                    args.random_on_value,
                    args.random_interval_sec,
                ),
                daemon=True,
            )
            random_thread.start()
        elif args.play_rom_tokens:
            base_path = args.base_path if args.base_path else _default_base_path()
            ini_path = args.config_ini if args.config_ini else _resolve_config_ini(base_path)
            tokens = _collect_rom_tokens(ini_path, rom_key)
            if not tokens:
                parser.error(f'No valid trigger tokens found for ROM "{rom_key}" in {ini_path}')
            token_text = ', '.join(f'{t}{n}' for t, n in tokens)
            print(
                'Token sequence mode enabled: '
                f'ini={ini_path}, tokens=[{token_text}], on_value={args.token_on_value}, '
                f'on_sec={args.token_on_sec:.3f}, off_sec={args.token_off_sec:.3f}, '
                f'loop={"yes" if args.token_loop else "no"}'
            )
            token_thread = threading.Thread(
                target=_run_token_sequence,
                args=(
                    d,
                    token_stop_event,
                    tokens,
                    args.token_on_value,
                    args.token_on_sec,
                    args.token_off_sec,
                    args.token_loop,
                ),
                daemon=True,
            )
            token_thread.start()
        elif args.event_range:
            try:
                type_char, start_number, end_number = _parse_event_range_arg(args.event_range)
            except ValueError as exc:
                parser.error(str(exc))
            print(
                'Event range mode enabled: '
                f'range={type_char}{start_number}-{type_char}{end_number}, '
                f'on_value={args.range_on_value}, on_sec={args.range_on_sec:.3f}, '
                f'off_sec={args.range_off_sec:.3f}, loop={"yes" if args.range_loop else "no"}'
            )
            range_thread = threading.Thread(
                target=_run_event_range_sequence,
                args=(
                    d,
                    range_stop_event,
                    type_char,
                    start_number,
                    end_number,
                    args.range_on_value,
                    args.range_on_sec,
                    args.range_off_sec,
                    args.range_loop,
                ),
                daemon=True,
            )
            range_thread.start()
        try:
            _wait_for_quit_key()
        except KeyboardInterrupt:
            pass
        finally:
            if random_thread is not None:
                random_stop_event.set()
                random_thread.join(timeout=max(1.0, args.random_interval_sec * 4.0))
            if token_thread is not None:
                token_stop_event.set()
                token_thread.join(timeout=max(1.0, (args.token_on_sec + args.token_off_sec) * 2.0))
            if range_thread is not None:
                range_stop_event.set()
                range_thread.join(timeout=max(1.0, (args.range_on_sec + args.range_off_sec) * 2.0))
            d.finish()

    print('Done.')


if __name__ == '__main__':
    main()
