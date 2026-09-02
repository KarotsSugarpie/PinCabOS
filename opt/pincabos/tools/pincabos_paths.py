#!/usr/bin/env python3
"""PinCabOS — chemins et identite machine, une seule fois.

PINCABOS_PATHS_V1

Le depot comptait 654 occurrences de /home/pinball, 51 uid/gid 1000 et 47
VPinballX/10.8 ecrits en dur : changer de version VPX, d'utilisateur ou de
disposition demandait une chasse au grep, et un chemin oublie cassait un
cabinet (le launcher exigeait libhidapi-libusb.so.0.15.0 par son nom).

Ce module est la source de verite. Les valeurs par defaut SONT la realite
d'un cabinet PinCabOS ; /opt/pincabos/config/pincabos-paths.json (schema
pincabos.paths/2) peut les surcharger, cle par cle. Un fichier a l'ancien
schema (celui ecrit par l'installateur historique, sans "schema") n'est lu
que pour les cles encore vraies : ses autres valeurs decrivaient des
emplacements qui n'existent pas (/opt/pincabos/apps/vpinball…).

Python :
    import sys; sys.path.insert(0, "/opt/pincabos/lib")
    from pincabos_paths import PATHS
    PATHS.tables, PATHS.vpx_ini, PATHS.uid …

Shell :
    . /opt/pincabos/tools/pincabos-paths.sh      # exporte PCO_TABLES, PCO_VPX_INI, PCO_UID …

CLI :
    pincabos_paths.py --shell | --json | get <cle>
"""
from __future__ import annotations

import json
import os
import pwd
import shlex
import sys

CONFIG = "/opt/pincabos/config/pincabos-paths.json"
SCHEMA = "pincabos.paths/2"

# Cles de l'ancien schema dont la valeur est encore vraie ; le reste de ce
# fichier (vpx_dir, vpx_bin, vpx_ini, vpinfe_dir, vpinfe_ini, roms) decrit
# des chemins qui n'ont jamais existe sur un cabinet livre.
LEGACY_KEYS_KEPT = ("root", "web", "web_venv", "tables", "logs", "config")


def _user(name: str) -> tuple[int, int, str]:
    try:
        entry = pwd.getpwnam(name)
        return entry.pw_uid, entry.pw_gid, entry.pw_dir
    except KeyError:
        return 1000, 1000, f"/home/{name}"


def defaults(user: str = "pinball") -> dict[str, str]:
    uid, gid, home = _user(user)
    root = "/opt/pincabos"
    config = f"{root}/config"
    vpx_link = f"{home}/vpx"
    vpx_pref = f"{home}/.pincabos/vpx"
    return {
        # identite
        "user": user,
        "uid": str(uid),
        "gid": str(gid),
        "home": home,
        "display": ":0",
        "xauthority": f"{home}/.Xauthority",
        "runtime_dir": f"/run/user/{uid}",
        "dbus_address": f"unix:path=/run/user/{uid}/bus",
        # PinCabOS
        "root": root,
        "config": config,
        "config_screens": f"{config}/screens",
        "screens_json": f"{config}/screens/screens.json",
        "bindings_json": f"{config}/screens/display-role-bindings.json",
        "aliases_env": f"{config}/display-aliases.env",
        "version_json": f"{config}/version.json",
        "bin": f"{root}/bin",
        "tools": f"{root}/tools",
        "scripts": f"{root}/scripts",
        "launchers": f"{root}/launchers",
        "lib": f"{root}/lib",
        "web": f"{root}/web",
        "web_venv": f"{root}/web/.venv",
        "overlays": f"{root}/overlays",
        "media": f"{root}/media",
        "logs": f"{root}/logs",
        "backups": f"{root}/backups",
        # joueur
        "tables": f"{home}/Tables",
        "downloads": f"{home}/Downloads",
        "network_drives": f"{home}/NetworkDrives",
        # VPX (BGFX standalone) : lien stable vers le dossier versionne,
        # preferences hors du dossier versionne de VPX (-PrefPath)
        "vpx_link": vpx_link,
        "vpx_bin": f"{vpx_link}/VPinballX_BGFX",
        "vpx_plugins": f"{vpx_link}/plugins",
        "vpx_pref": vpx_pref,
        "vpx_ini": f"{vpx_pref}/VPinballX.ini",
        "vpx_legacy_pref": f"{home}/.local/share/VPinballX/10.8",
        "dof_config": f"{vpx_pref}/directoutputconfig",
        "cabinet_xml": f"{vpx_pref}/directoutputconfig/cabinet.xml",
        # VPinFE
        "vpinfe_dir": f"{home}/vpinfe",
        "vpinfe_bin": f"{home}/vpinfe/vpinfe",
        "vpinfe_ini": f"{home}/.config/vpinfe/vpinfe.ini",
        "vpinfe_dmdutil": f"{home}/vpinfe/_internal/third-party/libdmdutil",
    }


def load(config_path: str = CONFIG) -> dict[str, str]:
    values = defaults()
    try:
        with open(config_path, encoding="utf-8") as handle:
            data = json.load(handle) or {}
    except (OSError, ValueError):
        return values
    if not isinstance(data, dict):
        return values
    paths = data.get("paths") if isinstance(data.get("paths"), dict) else {}
    if data.get("schema") == SCHEMA:
        if data.get("user") and data["user"] != values["user"]:
            values = defaults(str(data["user"]))
        for key, value in paths.items():
            if isinstance(value, str) and value:
                values[key] = value
    else:
        for key in LEGACY_KEYS_KEPT:
            value = paths.get(key)
            if isinstance(value, str) and value:
                values[key] = value
    return values


class _Paths:
    def __init__(self, values: dict[str, str]):
        self.__dict__["_values"] = values

    def __getattr__(self, name: str) -> str:
        try:
            return self._values[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value: str) -> None:
        raise AttributeError("les chemins ne se modifient pas a l'execution")

    def get(self, name: str, default: str | None = None) -> str | None:
        return self._values.get(name, default)

    def as_dict(self) -> dict[str, str]:
        return dict(self._values)

    @property
    def uid_int(self) -> int:
        return int(self._values["uid"])

    @property
    def gid_int(self) -> int:
        return int(self._values["gid"])


PATHS = _Paths(load())


def shell_exports(values: dict[str, str]) -> str:
    lines = [f"export PCO_{key.upper()}={shlex.quote(value)}" for key, value in values.items()]
    lines.append("export PCO_PATHS_LOADED=1")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    values = PATHS.as_dict()
    if len(argv) > 1 and argv[1] == "--shell":
        sys.stdout.write(shell_exports(values))
        return 0
    if len(argv) > 1 and argv[1] == "--json":
        json.dump(values, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0
    if len(argv) > 2 and argv[1] == "get":
        value = values.get(argv[2])
        if value is None:
            sys.stderr.write(f"cle inconnue : {argv[2]}\n")
            return 2
        print(value)
        return 0
    sys.stdout.write(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
