"""Prise de contrôle locale sûre du cabinet pour VPX MultiPlayers."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Callable, Iterable

from .runtime import RuntimeIsolationError, RuntimeLayout, sha256_file


VPINFE_SERVICE = "pincabos-vpinfe.service"
ACTIVE_PHASES = {"ready", "running", "handoff"}
RUNNING_PHASES = {"running", "handoff"}


class CabinetControlError(RuntimeError):
    pass


def _default_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o640)
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return value if isinstance(value, dict) else {}


def _engine_pid(layout: RuntimeLayout) -> int | None:
    if not layout.game_pid.is_file():
        return None
    try:
        pid = int(layout.game_pid.read_text(encoding="ascii").strip())
        executable = Path(f"/proc/{pid}/exe").resolve()
        executable.relative_to(layout.engine.resolve())
        os.kill(pid, 0)
    except (OSError, ValueError):
        layout.game_pid.unlink(missing_ok=True)
        return None
    return pid


def _matching_table(layout: RuntimeLayout, manifest_hash: str) -> str:
    expected = str(manifest_hash or "").strip().lower()
    if len(expected) != 64:
        raise CabinetControlError("multiplayer_manifest_invalid")

    matches: list[Path] = []
    for path in sorted(layout.tables.rglob("*.vpx")):
        if not path.is_file():
            continue
        if sha256_file(path).lower() == expected:
            matches.append(path)

    if len(matches) != 1:
        raise CabinetControlError("multiplayer_table_hash_ambiguous_or_missing")

    return str(matches[0].resolve().relative_to(layout.tables.resolve()))


class CabinetControlManager:
    """Fait de la phase serveur l'autorité de possession du cabinet.

    READY   -> arrête VPinFE et prend le lease.
    RUNNING -> garde VPinFE arrêté et lance le VPX isolé une seule fois.
    STOPPED/WAITING/PREPARING/aucune session -> libère le lease et restaure
    VPinFE seulement s'il était actif avant la prise de contrôle.
    """

    def __init__(
        self,
        layout: RuntimeLayout,
        runner: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None,
    ) -> None:
        self.layout = layout
        self.runner = runner or _default_runner
        self.lease_path = layout.root / "sessions" / "control-lease.json"

    def _run(self, *command: str) -> subprocess.CompletedProcess[str]:
        return self.runner(list(command))

    def service_active(self, service: str = VPINFE_SERVICE) -> bool:
        return self._run("systemctl", "is-active", "--quiet", service).returncode == 0

    def stop_service(self, service: str = VPINFE_SERVICE) -> None:
        result = self._run("systemctl", "stop", service)
        if result.returncode != 0:
            raise CabinetControlError(
                f"service_stop_failed:{service}:{(result.stderr or '').strip()}"
            )
        if self.service_active(service):
            raise CabinetControlError(f"service_still_active:{service}")

    def start_service(self, service: str = VPINFE_SERVICE) -> None:
        result = self._run("systemctl", "start", service)
        if result.returncode != 0:
            raise CabinetControlError(
                f"service_start_failed:{service}:{(result.stderr or '').strip()}"
            )
        if not self.service_active(service):
            raise CabinetControlError(f"service_not_active:{service}")

    def lease(self) -> dict:
        return _read_json(self.lease_path)

    def _write_lease(self, value: dict) -> dict:
        value = dict(value)
        value["updated_at"] = time.time()
        _atomic_json(self.lease_path, value)
        return value

    @staticmethod
    def _member(session: dict) -> bool:
        return bool(session.get("is_this_cabinet_member"))

    @staticmethod
    def _phase(session: dict) -> str:
        return str(session.get("phase") or "").strip().lower()

    def acquire(self, session: dict) -> dict:
        session_id = str(session.get("session_id") or "")
        if not session_id:
            raise CabinetControlError("multiplayer_session_missing")
        if not self._member(session):
            raise CabinetControlError("cabinet_not_member")

        current = self.lease()
        same_lease = (
            current.get("owner") == "multiplayer"
            and current.get("session_id") == session_id
            and current.get("state") in {"armed", "running", "handoff"}
        )

        if same_lease:
            was_active = bool(current.get("vpinfe_was_active"))
        else:
            was_active = self.service_active()

        if self.service_active():
            self.stop_service()

        topology = session.get("topology")
        role = None
        if isinstance(topology, dict):
            role = topology.get("role") or topology.get("local_role")

        phase = self._phase(session)
        state = "running" if phase == "running" else phase or "armed"
        if state not in {"ready", "running", "handoff"}:
            state = "armed"
        if state == "ready":
            state = "armed"

        return self._write_lease(
            {
                "owner": "multiplayer",
                "session_id": session_id,
                "state": state,
                "phase": phase,
                "role": role,
                "room_code": session.get("room_code"),
                "manifest_hash": session.get("manifest_hash"),
                "vpinfe_service": VPINFE_SERVICE,
                "vpinfe_was_active": was_active,
                "vpinfe_active": self.service_active(),
                "video_desired": phase in ACTIVE_PHASES,
                "video_state": "pending-hook",
            }
        )

    def ensure_running(self, session: dict) -> dict:
        lease = self.acquire(session)
        phase = self._phase(session)
        if phase not in RUNNING_PHASES:
            return lease

        pid = _engine_pid(self.layout)
        table = None
        if phase == "running" and pid is None:
            table = _matching_table(self.layout, str(session.get("manifest_hash") or ""))
            pid = self.layout.launch_detached(table)

        lease.update(
            {
                "state": phase,
                "phase": phase,
                "engine_pid": pid,
                "table": table or lease.get("table"),
                "vpinfe_active": self.service_active(),
            }
        )
        return self._write_lease(lease)

    def release(self, reason: str) -> dict:
        current = self.lease()
        stopped = self.layout.stop_detached()

        restore_vpinfe = bool(
            current.get("owner") == "multiplayer"
            and current.get("vpinfe_was_active")
        )
        if restore_vpinfe and not self.service_active():
            self.start_service()

        return self._write_lease(
            {
                "owner": None,
                "session_id": current.get("session_id"),
                "state": "released",
                "reason": reason,
                "engine_stopped": stopped,
                "vpinfe_service": VPINFE_SERVICE,
                "vpinfe_restored": restore_vpinfe,
                "vpinfe_active": self.service_active(),
                "video_desired": False,
                "video_state": "released",
            }
        )

    def reconcile(self, state: dict) -> dict:
        session = state.get("session")
        if not isinstance(session, dict) or not session.get("session_id"):
            return self.release("no-session")
        if not self._member(session):
            return self.release("cabinet-not-member")

        phase = self._phase(session)
        if phase in ACTIVE_PHASES:
            return self.ensure_running(session)
        return self.release(f"phase-{phase or 'unknown'}")
