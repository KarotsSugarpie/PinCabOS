#!/usr/bin/env python3
"""Compatibilité WebApp : délègue les imports récents au moteur FullDMD V4."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

DISPATCHER = Path('/opt/pincabos/bin/pincabos-fulldmd-process-table.py')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--recent-minutes', type=int, default=30)
    args = parser.parse_args()
    result = subprocess.run([str(DISPATCHER), '--recent-minutes', str(max(1, args.recent_minutes))])
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
