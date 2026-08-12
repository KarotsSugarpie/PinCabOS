"""
Charge les correctifs WebApp PinCabOS seulement dans un
environnement où Flask est réellement installé.

Ce module ne doit pas être exécuté directement.
"""

from __future__ import annotations

import importlib
import sys


PATCH_MODULES = (
    "pincabos_request_limits",
    "pincabos_browser_cache",
    "pincabos_explorer_performance",
    "pincabos_table_analysis_cache",
)


for module_name in PATCH_MODULES:
    try:
        importlib.import_module(module_name)

    except ModuleNotFoundError as exc:
        print(
            "PINCABOS-WEB-RUNTIME "
            f"module ignoré={module_name} "
            f"dépendance absente={exc.name}",
            file=sys.stderr,
        )

    except Exception as exc:
        print(
            "PINCABOS-WEB-RUNTIME "
            f"erreur module={module_name} "
            f"détail={exc!r}",
            file=sys.stderr,
        )
