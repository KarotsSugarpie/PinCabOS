#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import pwd
import grp
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

TABLES_ROOT = Path("/home/pinball/Tables").resolve()
VPX_LAUNCHER = Path("/opt/pincabos/scripts/VPXlauncher.sh")
BACKUP_ROOT = Path("/opt/pincabos/backups/table-script-extract")


def fail(message: str, code: int = 1) -> int:
    print(f"ERREUR: {message}", file=sys.stderr)
    return code


def under_tables(path: Path) -> bool:
    try:
        path.resolve().relative_to(TABLES_ROOT)
        return True
    except ValueError:
        return False


def find_vpx_binary() -> Path:
    if VPX_LAUNCHER.is_file():
        text = VPX_LAUNCHER.read_text(encoding="utf-8", errors="replace")
        match = re.search(r'^\s*VPX_MAIN="([^"]+)"', text, re.MULTILINE)
        if match:
            candidate = Path(match.group(1))
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return candidate.resolve()

    candidates = sorted(
        Path("/home/pinball").glob("VPinballX_BGFX-*/VPinballX_BGFX"),
        key=lambda item: item.stat().st_mtime if item.exists() else 0,
        reverse=True,
    )

    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()

    raise RuntimeError("VPinballX_BGFX actif introuvable.")


def vpx_running() -> bool:
    result = subprocess.run(
        ["pgrep", "-af", "VPinballX"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return bool(result.stdout.strip())


def restore_previous(destination: Path, backup: Path | None) -> None:
    if backup and backup.is_file():
        shutil.copy2(backup, destination)


def backup_existing_script(script: Path, table_dir: Path) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    safe_table = re.sub(r"[^A-Za-z0-9._-]+", "_", table_dir.name).strip("_")
    destination = BACKUP_ROOT / stamp / safe_table / script.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(script, destination)
    return destination


def resolve_output(table: Path, replace: bool, if_missing: bool) -> int:
    table = table.expanduser().resolve()

    if table.suffix.lower() != ".vpx":
        return fail(f"ce n'est pas un fichier .vpx: {table}")

    if not table.is_file():
        return fail(f"table absente: {table}")

    if not under_tables(table):
        return fail(f"table hors de {TABLES_ROOT}: {table}")

    if vpx_running():
        return fail(
            "VPX est actif. Ferme la table avant d'extraire son script afin "
            "d'éviter tout conflit avec VPinballX."
        )

    table_dir = table.parent
    output = table.with_suffix(".vbs")

    if output.exists() and if_missing:
        print(f"SKIP: script existant conservé: {output}")
        return 0

    if output.exists() and not replace:
        return fail(
            f"script existant: {output}. Utilise --replace ou --if-missing."
        )

    old_backup: Path | None = None
    if output.exists():
        old_backup = backup_existing_script(output, table_dir)
        output.unlink()
        print(f"Backup script existant: {old_backup}")

    vpx = find_vpx_binary()

    env = os.environ.copy()
    env.update(
        {
            "HOME": "/home/pinball",
            "USER": "pinball",
            "LOGNAME": "pinball",
            "DISPLAY": ":0",
            "XAUTHORITY": "/home/pinball/.Xauthority",
            "XDG_RUNTIME_DIR": "/run/user/1000",
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
        }
    )

    started = time.time()

    try:
        result = subprocess.run(
            [str(vpx), "-ExtractVBS", str(table)],
            cwd=str(table_dir),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=180,
            check=False,
        )
    except subprocess.TimeoutExpired:
        restore_previous(output, old_backup)
        return fail("timeout pendant -ExtractVBS; ancien script restauré.")

    if result.stdout.strip():
        print(result.stdout.strip())

    if result.returncode != 0:
        restore_previous(output, old_backup)
        return fail(
            f"VPinballX -ExtractVBS a échoué (code {result.returncode}); "
            "ancien script restauré."
        )

    if not output.is_file():
        recent_scripts = sorted(
            [
                item
                for item in table_dir.glob("*.vbs")
                if item.is_file() and item.stat().st_mtime >= started - 2
            ],
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )

        if len(recent_scripts) == 1:
            recent_scripts[0].replace(output)

    if not output.is_file() or output.stat().st_size == 0:
        restore_previous(output, old_backup)
        return fail(
            "VPinballX n'a pas produit de script VBS valide; ancien script restauré."
        )

    try:
        uid = pwd.getpwnam("pinball").pw_uid
        gid = grp.getgrnam("pinball").gr_gid
        os.chown(output, uid, gid)
    except Exception:
        pass

    os.chmod(output, 0o644)

    matching_b2s = table.with_suffix(".directb2s")
    if matching_b2s.is_file():
        b2s_state = f"aligné: {matching_b2s.name}"
    else:
        b2s_files = sorted(table_dir.glob("*.directb2s"))
        if b2s_files:
            b2s_state = (
                "B2S non renommé: "
                + ", ".join(item.name for item in b2s_files)
            )
        else:
            b2s_state = "aucun .directb2s dans ce dossier"

    print(f"OK: script extrait: {output}")
    print(f"B2S: {b2s_state}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extrait le script embarqué d'une table VPX vers <table>.vbs."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--replace",
        action="store_true",
        help="sauvegarde et remplace un script existant",
    )
    mode.add_argument(
        "--if-missing",
        action="store_true",
        help="n'extrait que si le script n'existe pas",
    )
    parser.add_argument("table", help="chemin complet vers la table .vpx")
    args = parser.parse_args()

    return resolve_output(
        Path(args.table),
        replace=args.replace,
        if_missing=args.if_missing,
    )


if __name__ == "__main__":
    raise SystemExit(main())
