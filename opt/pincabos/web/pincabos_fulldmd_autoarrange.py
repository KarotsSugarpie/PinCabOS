"""Compatibilité PinCabOS — tuner DMD interne uniquement."""
from pincabos_dmd_tuner import register_dmd_tuner


def register_fulldmd_autoarrange(app, page, esc) -> None:
    register_dmd_tuner(app, page, esc)
