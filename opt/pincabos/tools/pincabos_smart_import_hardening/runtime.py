"""Post-commit runtime hardening for PinCabOS Smart Import."""
from __future__ import annotations

import subprocess as _subprocess
from pathlib import Path

CORE = None


class _SubprocessProxy:
    def __init__(self, core):
        self.core = core

    def __getattr__(self, name):
        return getattr(_subprocess, name)

    def run(self, command, *args, **kwargs):
        try:
            result = _subprocess.run(command, *args, **kwargs)
        except FileNotFoundError as exc:
            executable = ""
            if isinstance(command, (list, tuple)) and command:
                executable = Path(str(command[0])).name
            if executable == "find":
                self.core.log(f"WARNING: rapport find impossible après commit: {exc}")
                return _subprocess.CompletedProcess(command, 127, "", str(exc))
            raise

        executable = ""
        if isinstance(command, (list, tuple)) and command:
            executable = Path(str(command[0])).name
        if executable in {"chown", "chmod"} and result.returncode != 0:
            detail = ""
            for value in (getattr(result, "stderr", None), getattr(result, "stdout", None)):
                if value:
                    detail = str(value).strip()
                    if detail:
                        break
            self.core.log(
                "WARNING: normalisation permissions non appliquée "
                f"({executable}, code={result.returncode})"
                + (f": {detail[-1000:]}" if detail else "")
            )
        return result

    @staticmethod
    def Popen(*args, **kwargs):
        return _subprocess.Popen(*args, **kwargs)


def write_import_tree_log(table_dir, title, rom, installed):
    """Best-effort post-commit log; a logging failure cannot invalidate commit."""
    core = CORE
    try:
        core.IMPORT_LOGS_ROOT.mkdir(parents=True, exist_ok=True)
        stamp = core.time.strftime("%Y%m%d-%H%M%S")
        log_name = core.safe_name(title).replace(" ", "_")
        log_path = core.IMPORT_LOGS_ROOT / f"import-{stamp}-{log_name}.txt"

        try:
            tree = core.subprocess.run(
                ["find", str(table_dir), "-maxdepth", "8", "-print"],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            tree_output = (tree.stdout or "").strip()
            tree_error = (tree.stderr or "").strip()
        except Exception as exc:
            tree_output = ""
            tree_error = str(exc)

        lines = [
            "======================================================================",
            " PinCabOS - Import table log",
            "======================================================================",
            f"Date       : {core.time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Title      : {title}",
            f"ROM        : {rom or '(aucune)'}",
            f"Table dir  : {table_dir}",
            "",
            "======================================================================",
            " Résumé install",
            "======================================================================",
        ]
        for key, values in installed.items():
            lines.append(f"{key}: {len(values)}")

        lines.extend([
            "",
            "======================================================================",
            " Fichiers installés par catégorie",
            "======================================================================",
        ])
        for key, values in installed.items():
            lines.extend(["", f"--- {key} ({len(values)}) ---"])
            lines.extend(str(item) for item in values)

        lines.extend([
            "",
            "======================================================================",
            " Résultat find",
            "======================================================================",
            tree_output,
        ])
        if tree_error:
            lines.extend([
                "",
                "======================================================================",
                " Erreurs find",
                "======================================================================",
                tree_error,
            ])
        lines.extend([
            "",
            "======================================================================",
            " FIN",
            "======================================================================",
        ])

        # Real LF characters; the historical implementation wrote literal "\\n".
        log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        core.subprocess.run(
            ["chown", "pinball:pinball", str(log_path)],
            timeout=10,
            check=False,
            capture_output=True,
            text=True,
        )
        core.subprocess.run(
            ["chmod", "664", str(log_path)],
            timeout=10,
            check=False,
            capture_output=True,
            text=True,
        )
        core.log(f"IMPORT LOG: {log_path}")
        return log_path
    except Exception as exc:
        core.log(
            "WARNING: journal d'import non écrit après commit; "
            f"la table reste installée: {exc}"
        )
        return "(journal non écrit)"


def fulldmd_after_success(core):
    """Launch FullDMD only after transactional Smart Import returned success."""
    dispatcher = Path("/opt/pincabos/bin/pincabos-fulldmd-process-table.py")
    if not dispatcher.is_file():
        return
    try:
        _subprocess.Popen(
            [str(dispatcher), "--recent-minutes", "20"],
            stdin=_subprocess.DEVNULL,
            stdout=_subprocess.DEVNULL,
            stderr=_subprocess.DEVNULL,
            start_new_session=True,
        )
        core.log("FullDMD post-import      : déclenché après succès")
    except Exception as exc:
        core.log(f"WARNING: FullDMD post-import impossible: {exc}")


def install(core):
    global CORE
    CORE = core
    core.subprocess = _SubprocessProxy(core)
    core.write_import_tree_log = write_import_tree_log
    return {"write_import_tree_log": write_import_tree_log}
