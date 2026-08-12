#!/usr/bin/env python3
# PINCABOS_EXPLORER_TABLE_TEST_CENTER_V1
# PINCABOS_TABLE_TEST_FIXED_LOG_V1
from __future__ import annotations

import json
import os
import pwd
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

STATE_FILE = Path("/var/lib/pincabos/table-test/state.json")
LAUNCHER = Path("/opt/pincabos/scripts/VPXlauncher.sh")
VPINFE_SERVICE = "pincabos-vpinfe.service"

LOG_NAME = "PinCabOS-Test.log"
LOG_HEADER = "PINCABOS_TABLE_TEST_LOG_V1"
RESULT_SEPARATOR = "===== PINCABOS RESULT ====="


def read_state() -> dict[str, Any]:
    try:
        value = json.loads(
            STATE_FILE.read_text(encoding="utf-8")
        )
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def write_state(value: dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = STATE_FILE.with_suffix(".tmp")
    temp.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temp, STATE_FILE)


def update(**changes: Any) -> dict[str, Any]:
    state = read_state()
    state.update(changes)
    state["updated_at"] = int(time.time())
    write_state(state)
    return state


def _clean_value(value: Any) -> str:
    return (
        str(value or "")
        .replace("\r", " ")
        .replace("\n", " ")
        .strip()
    )


def _log_path_from_state(state: dict[str, Any]) -> Path | None:
    raw_log = _clean_value(state.get("log_file"))

    if raw_log:
        return Path(raw_log)

    raw_vpx = _clean_value(state.get("vpx"))

    if not raw_vpx:
        return None

    return Path(raw_vpx).parent / LOG_NAME


def _set_pinball_ownership(path: Path) -> None:
    try:
        account = pwd.getpwnam("pinball")
        os.chown(path, account.pw_uid, account.pw_gid)
    except (KeyError, OSError):
        pass

    try:
        path.chmod(0o664)
    except OSError:
        pass


def _prepare_log(
    log_file: Path,
    state: dict[str, Any],
    vpx: Path,
) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)

    table_name = _clean_value(
        state.get("table_name") or vpx.parent.name
    )

    content = "\n".join(
        [
            LOG_HEADER,
            "PINCABOS_STATUS=RUNNING",
            "PINCABOS_FINAL=0",
            f"PINCABOS_TABLE={table_name}",
            f"PINCABOS_VPX={vpx}",
            "",
            "===== VPX OUTPUT =====",
            "",
        ]
    )

    log_file.write_text(content, encoding="utf-8")
    _set_pinball_ownership(log_file)


def _last_result(text: str) -> tuple[str, list[str], bool]:
    final = bool(
        re.findall(r"(?m)^PINCABOS_FINAL=1\s*$", text)
    )

    statuses = re.findall(
        r"(?m)^PINCABOS_STATUS=(RUNNING|GO|NOGO)\s*$",
        text,
    )

    status = statuses[-1] if statuses else ""

    if RESULT_SEPARATOR in text:
        result_text = text.rsplit(RESULT_SEPARATOR, 1)[-1]
    else:
        result_text = ""

    reasons = [
        match.strip()
        for match in re.findall(
            r"(?m)^PINCABOS_REASON=(.+)$",
            result_text,
        )
        if match.strip()
    ]

    return status, reasons, final


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        clean = _clean_value(value)

        if not clean:
            continue

        key = clean.casefold()

        if key in seen:
            continue

        seen.add(key)
        result.append(clean)

    return result


def _classify_output(
    text: str,
    exit_code: int | None,
    stop_requested: bool,
) -> tuple[str, list[str]]:
    if RESULT_SEPARATOR in text:
        output = text.split(RESULT_SEPARATOR, 1)[0]
    else:
        output = text

    lowered = output.casefold()
    reasons: list[str] = []

    blocking_patterns = (
        (
            "Erreur de script VPX/VBS",
            r"(?:script error|vbscript[^\n]{0,80}error|"
            r"syntax error[^\n]{0,80}(?:vbs|script)|"
            r"runtime error[^\n]{0,80}(?:vbs|script))",
        ),
        (
            "Objet COM requis impossible à créer",
            r"(?:unknown com object|"
            r"activex component[^\n]{0,80}create object|"
            r"class not registered|cannot create object|"
            r"unable to create object)",
        ),
        (
            "FlexDMD ou UltraDMD en erreur",
            r"(?:(?:flexdmd|ultradmd)[^\n]{0,140}"
            r"(?:failed|failure|error|not found|missing|cannot|unable)|"
            r"(?:failed|cannot|unable)[^\n]{0,140}"
            r"(?:flexdmd|ultradmd))",
        ),
        (
            "ROM PinMAME introuvable ou invalide",
            r"(?:(?:rom|romset)[^\n]{0,120}"
            r"(?:not found|missing|invalid|could not be loaded)|"
            r"(?:failed|unable|could not)[^\n]{0,120}"
            r"(?:rom|romset))",
        ),
        (
            "PuP-Pack introuvable ou impossible à charger",
            r"(?:(?:pup-pack|puppack|pupvideos)[^\n]{0,120}"
            r"(?:not found|missing|failed|cannot|unable))",
        ),
        (
            "VPX a subi un arrêt fatal",
            r"(?:segmentation fault|core dumped|fatal error|"
            r"unhandled exception|terminate called|aborted)",
        ),
        (
            "La table n’a pas pu être chargée",
            r"(?:(?:failed|unable|could not)[^\n]{0,80}"
            r"load (?:game|table)|load (?:game|table)[^\n]{0,80}"
            r"(?:failed|error))",
        ),
    )

    for label, pattern in blocking_patterns:
        if re.search(pattern, output, re.IGNORECASE):
            reasons.append(label)

    duplicate_dmd_lines = [
        line
        for line in output.splitlines()
        if "duplicate label" in line.casefold()
        and any(
            token in line.casefold()
            for token in (
                "pup",
                "fulldmd",
                "full dmd",
                "screennum=5",
                "screen=5",
                "screen 5",
            )
        )
    ]

    if duplicate_dmd_lines:
        reasons.append(
            "Labels PuP/FlexDMD dupliqués sur le FullDMD"
        )

    started = any(
        marker in lowered
        for marker in (
            "starting script",
            "creating main window",
            "initializing player",
            "starting vpx -",
        )
    )

    if not started:
        reasons.append(
            "La table n’a pas atteint le démarrage du joueur VPX"
        )

    if (
        exit_code not in {None, 0}
        and not stop_requested
        and exit_code not in {-15, 143}
    ):
        reasons.append(f"VPX a quitté avec le code {exit_code}")

    reasons = _unique(reasons)

    return ("NOGO" if reasons else "GO", reasons)


def _append_result(
    log_file: Path,
    status: str,
    reasons: list[str],
    exit_code: int | None,
    stop_requested: bool,
) -> None:
    lines = [
        "",
        RESULT_SEPARATOR,
        f"PINCABOS_STATUS={status}",
        "PINCABOS_FINAL=1",
        "PINCABOS_EXIT_CODE="
        + ("" if exit_code is None else str(exit_code)),
        "PINCABOS_STOP_REQUESTED="
        + ("1" if stop_requested else "0"),
    ]

    for reason in reasons:
        lines.append(f"PINCABOS_REASON={_clean_value(reason)}")

    lines.append("")

    with log_file.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
        handle.flush()

    _set_pinball_ownership(log_file)


def finalize_log(
    state: dict[str, Any],
) -> tuple[str, list[str], Path | None]:
    log_file = _log_path_from_state(state)

    if log_file is None or not log_file.is_file():
        return "NOGO", ["Journal d’exécution absent"], log_file

    try:
        text = log_file.read_text(
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return "NOGO", ["Journal d’exécution illisible"], log_file

    current_status, current_reasons, final = _last_result(text)

    if final and current_status in {"GO", "NOGO"}:
        return current_status, current_reasons, log_file

    exit_code_raw = state.get("exit_code")

    try:
        exit_code = (
            int(exit_code_raw)
            if exit_code_raw is not None
            else None
        )
    except (TypeError, ValueError):
        exit_code = None

    stop_requested = bool(state.get("stop_requested"))

    status, reasons = _classify_output(
        text,
        exit_code,
        stop_requested,
    )

    _append_result(
        log_file,
        status,
        reasons,
        exit_code,
        stop_requested,
    )

    return status, reasons, log_file


def run() -> int:
    state = read_state()
    vpx = Path(_clean_value(state.get("vpx")))

    if not vpx.is_file():
        update(
            phase="error",
            error=f"VPX absent: {vpx}",
            exit_code=2,
        )
        return 2

    if not LAUNCHER.is_file():
        update(
            phase="error",
            error=f"Lanceur absent: {LAUNCHER}",
            exit_code=3,
        )
        return 3

    log_file = vpx.parent / LOG_NAME

    _prepare_log(log_file, state, vpx)

    update(
        phase="launching",
        launcher=str(LAUNCHER),
        log_file=str(log_file),
        log_name=LOG_NAME,
        log_status="RUNNING",
        log_finalized=False,
        stop_requested=False,
        exit_code=None,
        error="",
    )

    try:
        process = subprocess.Popen(
            [str(LAUNCHER), str(vpx)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
    except Exception as exc:
        message = "Impossible de lancer VPX : " + _clean_value(exc)

        with log_file.open("a", encoding="utf-8") as handle:
            handle.write("\n" + message + "\n")

        update(phase="error", exit_code=4, error=message)

        state = read_state()
        status, reasons, _ = finalize_log(state)

        update(
            log_status=status,
            log_reasons=reasons,
            log_finalized=True,
        )

        return 4

    update(phase="running", child_pid=process.pid)

    with log_file.open(
        "a",
        encoding="utf-8",
        buffering=1,
    ) as handle:
        if process.stdout is not None:
            for line in process.stdout:
                handle.write(line)
                handle.flush()
                sys.stdout.write(line)
                sys.stdout.flush()

    code = process.wait()
    update(exit_code=code, ended_at=int(time.time()))

    state = read_state()
    status, reasons, _ = finalize_log(state)

    update(
        phase="finished" if status == "GO" else "error",
        log_status=status,
        log_reasons=reasons,
        log_finalized=True,
        error="" if status == "GO" else "; ".join(reasons),
    )

    return code


def finalize() -> int:
    state = read_state()
    status, reasons, log_file = finalize_log(state)

    phase = str(state.get("phase") or "")

    changes: dict[str, Any] = {
        "log_status": status,
        "log_reasons": reasons,
        "log_finalized": True,
        "ended_at": int(time.time()),
        "error": "" if status == "GO" else "; ".join(reasons),
    }

    if log_file is not None:
        changes["log_file"] = str(log_file)

    if phase not in {"finished", "error"}:
        changes["phase"] = "stopped"

    update(**changes)

    subprocess.run(
        [
            "systemctl",
            "start",
            "--no-block",
            VPINFE_SERVICE,
        ],
        check=False,
    )

    return 0


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "run"
    raise SystemExit(finalize() if mode == "finalize" else run())
