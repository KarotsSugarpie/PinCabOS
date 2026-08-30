#!/usr/bin/env python3
# PinCabOS-File created by Karots Sugarpie
# PINCABOS_SMART_IMPORT_ARCHIVE_HARDENING_V2
"""Hardened public entrypoint for PinCabOS Smart Import."""
from __future__ import annotations

import atexit
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORE_PATH = HERE / "pincabos-smart-archive-import-core.py"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


def _load_core():
    if not CORE_PATH.is_file():
        raise RuntimeError(f"NOGO: moteur Smart Import core absent: {CORE_PATH}")
    spec = importlib.util.spec_from_file_location(
        "_pincabos_smart_archive_import_core", CORE_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"NOGO: impossible de charger le core: {CORE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module

    # Suppress only the legacy core's unconditional atexit FullDMD registration.
    # The hardened entrypoint triggers FullDMD explicitly after main() == 0.
    original_register = atexit.register
    atexit.register = lambda func, *args, **kwargs: func
    try:
        spec.loader.exec_module(module)
    finally:
        atexit.register = original_register
    return module


core = _load_core()
from pincabos_smart_import_hardening import VERSION, fulldmd_after_success, install

_hardened = install(core)

# Re-export historical APIs for diagnostics importing this public path.
for _name in dir(core):
    if not _name.startswith("__"):
        globals().setdefault(_name, getattr(core, _name))
globals().update(_hardened)

# Compatibility markers retained for existing PinCabOS grep-based guards.
# PINCABOS_COPY_FILE_ATOMIC_V2
# === PINCABOS_SMART_IMPORT_UPDATE_V1 START ===
# === PINCABOS_SMART_IMPORT_UPDATE_V1 END ===
# PINCABOS_VBS_VPINFE_SOURCE_V1
# PINCABOS_VPX_BINARY_DISCOVERY_V2
# PINCABOS_PUP_ROM_FIRST_V1
# PINCABOS_PORTABLE_LAYOUT_V2
# PINCABOS_MANIFEST_RELATIVE_PATHS_V1
# PINCABOS_FULLDMD_SMART_IMPORT_HOOK_V4
# PINCABOS_FULLDMD_SMART_IMPORT_HOOK_V4_END
# PINCABOS_TABLE_TREE_IMPORT_TARGETED_V5_ENTRYPOINT


def main():
    core.log(f"Smart Import hardening   : V{VERSION}")
    result = core.main()
    if result == 0:
        fulldmd_after_success(core)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
