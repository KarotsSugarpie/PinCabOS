"""Identifiants admin / dev de la WebApp PinCabOS (lecture fail-closed, défauts documentés, secrets illisibles).

Repris tels quels du module admin (PINCABOS_WEBAPP_AUTONOMIE_V1) dans un module sans dépendance, importable par les
pages d'administration comme par le module dev_admin sans cycle.
"""
from __future__ import annotations

import os
from pathlib import Path


# PINCABOS_ADMIN_CREDENTIALS_FAIL_CLOSED_V1
def _pco_read_auth_value(env_name, *paths):
    value = os.environ.get(env_name, "").strip()
    if value:
        return value
    for raw_path in paths:
        try:
            candidate = Path(raw_path)
            if candidate.is_file():
                value = candidate.read_text(encoding="utf-8").strip()
                if value:
                    return value
        except OSError:
            pass
    return ""


ADMIN_LOGIN_USER = _pco_read_auth_value(
    "PINCABOS_ADMIN_LOGIN",
    "/opt/pincabos/config/admin-login.txt",
    "/opt/pincabos/config/dev-login.txt",
)
ADMIN_LOGIN_PASS = _pco_read_auth_value(
    "PINCABOS_ADMIN_PASSWORD",
    "/opt/pincabos/config/admin-password.txt",
    "/opt/pincabos/config/dev-password.txt",
)
# PINCABOS_ADMIN_CREDENTIALS_FAIL_CLOSED_V1_END


# PINCABOS_ADMIN_DEFAULT_CREDENTIALS_V1
# Les fichiers de secrets ne sont pas versionnes : sur une image fraiche ils
# manquent et les pages /admin et /dev repondaient "identifiants non
# configures". On retombe sur un identifiant par DEFAUT documente, que
# `pincabos-admin-password` permet de remplacer, et les pages affichent un
# avertissement tant qu'il est en place.
PINCABOS_DEFAULT_ADMIN_USER = "admin"
PINCABOS_DEFAULT_ADMIN_PASS = "PinCabOS123$"

# La page /dev a ses PROPRES identifiants : deux acces distincts, deux secrets
# distincts. Les fichiers dev-login.txt / dev-password.txt restent maitres.
PINCABOS_DEFAULT_DEV_USER = "PinCabOsDev"
PINCABOS_DEFAULT_DEV_PASS = "PinCabOSDev123$"

PINCABOS_ADMIN_CREDENTIALS_ARE_DEFAULT = not (ADMIN_LOGIN_USER and ADMIN_LOGIN_PASS)

if not ADMIN_LOGIN_USER:
    ADMIN_LOGIN_USER = PINCABOS_DEFAULT_ADMIN_USER
if not ADMIN_LOGIN_PASS:
    ADMIN_LOGIN_PASS = PINCABOS_DEFAULT_ADMIN_PASS
# Fichier present mais illisible par la WebApp (proprietaire root) : sans ce
# controle, on retombe sur le defaut sans rien dire et l'ancien mot de passe
# continue de fonctionner.
PINCABOS_ADMIN_UNREADABLE_SECRETS = [
    candidate
    for candidate in (
        "/opt/pincabos/config/admin-password.txt",
        "/opt/pincabos/config/admin-login.txt",
        "/opt/pincabos/config/dev-password.txt",
    )
    if os.path.exists(candidate) and not os.access(candidate, os.R_OK)
]
# PINCABOS_ADMIN_DEFAULT_CREDENTIALS_V1_END
