"""Installation et lancement strictement confinés au runtime multijoueur."""

from __future__ import annotations

import hashlib
import json
import os
import pwd
import signal
import shutil
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


DEFAULT_ROOT = Path("/opt/pincabos/apps/VPX_MultiPlayers")
ENGINE_NAMES = ("VPinballX_BGFX", "VPinballX-BGFX", "VPinballX")
WRITABLE_NAMES = ("home", "config", "data", "cache", "logs", "sessions", "tables-test")
LAUNCH_WRITABLE_NAMES = ("home", "config", "data", "cache", "logs", "sessions")
DESKTOP_ENV_KEYS = (
    "DISPLAY",
    "WAYLAND_DISPLAY",
    "XAUTHORITY",
    "DBUS_SESSION_BUS_ADDRESS",
    "PULSE_SERVER",
)


class RuntimeIsolationError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class RuntimeLayout:
    root: Path

    @classmethod
    def configured(cls) -> "RuntimeLayout":
        return cls(Path(os.environ.get("PINCABOS_MULTIPLAYER_ROOT") or DEFAULT_ROOT).resolve())

    @property
    def engine(self) -> Path:
        return self.root / "engine"

    @property
    def tables(self) -> Path:
        return self.root / "tables-test"

    @property
    def session_state(self) -> Path:
        return self.root / "sessions" / "current.json"

    @property
    def game_pid(self) -> Path:
        return self.root / "sessions" / "game.pid"

    def prepare_writable_directories(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        for name in WRITABLE_NAMES:
            path = self.root / name
            path.mkdir(parents=True, exist_ok=True)
            path.chmod(0o750)

    def prepare_pinball_launch_paths(self, uid: int, gid: int) -> None:
        """Rend uniquement les données du LAB accessibles au processus VPX pinball."""
        if os.geteuid() != 0:
            return

        def grant_owner_access(path: Path, directory: bool) -> None:
            if path.is_symlink():
                return
            os.chown(path, uid, gid)
            mode = stat.S_IMODE(path.stat().st_mode) | stat.S_IRUSR | stat.S_IWUSR
            if directory:
                mode |= stat.S_IXUSR
            path.chmod(mode)

        for name in LAUNCH_WRITABLE_NAMES:
            root = self.root / name
            root.mkdir(parents=True, exist_ok=True)
            for directory, directories, files in os.walk(root, followlinks=False):
                current = Path(directory)
                grant_owner_access(current, True)
                directories[:] = [
                    item for item in directories if not (current / item).is_symlink()
                ]
                for filename in files:
                    grant_owner_access(current / filename, False)

    @staticmethod
    def desktop_environment(uid: int) -> dict[str, str]:
        """Découvre la session graphique pinball sans réutiliser HOME ni XDG privés."""
        best: dict[str, str] = {}
        best_score = -1
        proc_root = Path("/proc")
        if proc_root.is_dir():
            for process in proc_root.iterdir():
                if not process.name.isdigit():
                    continue
                try:
                    if process.stat().st_uid != uid:
                        continue
                    raw = (process / "environ").read_bytes()
                except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
                    continue
                values: dict[str, str] = {}
                for entry in raw.split(b"\0"):
                    if b"=" not in entry:
                        continue
                    key, value = entry.split(b"=", 1)
                    try:
                        name = key.decode("ascii")
                        decoded = value.decode("utf-8")
                    except UnicodeDecodeError:
                        continue
                    if name in DESKTOP_ENV_KEYS and decoded:
                        values[name] = decoded
                if not (values.get("DISPLAY") or values.get("WAYLAND_DISPLAY")):
                    continue
                score = sum(bool(values.get(key)) for key in DESKTOP_ENV_KEYS)
                if score > best_score:
                    best = values
                    best_score = score

        runtime_dir = f"/run/user/{uid}"
        best["XDG_RUNTIME_DIR"] = runtime_dir
        best.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path={runtime_dir}/bus")
        best["DISPLAY"] = os.environ.get(
            "PINCABOS_MULTIPLAYER_DISPLAY", best.get("DISPLAY", ":0")
        )

        if not best.get("XAUTHORITY"):
            for candidate in (
                Path(f"/run/user/{uid}/gdm/Xauthority"),
                Path(pwd.getpwuid(uid).pw_dir) / ".Xauthority",
            ):
                if candidate.is_file():
                    best["XAUTHORITY"] = str(candidate)
                    break
        return best

    def engine_binary(self) -> Path:
        if not self.engine.is_dir():
            raise RuntimeIsolationError("isolated_engine_missing")
        matches = sorted(
            path
            for path in self.engine.rglob("*")
            if path.is_file() and path.name in ENGINE_NAMES
        )
        if len(matches) != 1:
            raise RuntimeIsolationError("isolated_engine_ambiguous_or_missing")
        if not os.access(matches[0], os.X_OK):
            raise RuntimeIsolationError("isolated_engine_not_executable")
        return matches[0]

    def table(self, relative_name: str) -> Path:
        supplied = Path(str(relative_name or ""))
        if supplied.is_absolute() or supplied.suffix.lower() != ".vpx":
            raise RuntimeIsolationError("test_table_invalid")
        resolved = (self.tables / supplied).resolve()
        try:
            resolved.relative_to(self.tables.resolve())
        except ValueError as exc:
            raise RuntimeIsolationError("test_table_outside_runtime") from exc
        if not resolved.is_file():
            raise RuntimeIsolationError("test_table_missing")
        return resolved

    def isolated_environment(self, runtime_uid: int | None = None) -> dict[str, str]:
        if runtime_uid is None:
            runtime_uid = os.geteuid()
        environment = dict(os.environ)
        environment.update(self.desktop_environment(runtime_uid))
        environment.update(
            {
                "HOME": str(self.root / "home"),
                "XDG_CONFIG_HOME": str(self.root / "config"),
                "XDG_DATA_HOME": str(self.root / "data"),
                "XDG_CACHE_HOME": str(self.root / "cache"),
                "PINCABOS_MULTIPLAYER": "1",
            }
        )
        for key in tuple(environment):
            if key.upper().startswith("VPINFE"):
                environment.pop(key, None)
        return environment

    def launch_command(self, relative_table: str) -> list[str]:
        engine = self.engine_binary()
        table = self.table(relative_table)
        pref_path = self.root / "config" / "vpx"
        pref_path.mkdir(parents=True, exist_ok=True)
        return [str(engine), "-PrefPath", str(pref_path), "-play", str(table)]

    def status(self) -> dict[str, object]:
        try:
            binary = self.engine_binary()
            engine_ready = True
            engine_sha256 = sha256_file(binary)
        except RuntimeIsolationError:
            binary = None
            engine_ready = False
            engine_sha256 = None
        return {
            "root": str(self.root),
            "engine_ready": engine_ready,
            "engine_binary": str(binary) if binary else None,
            "engine_sha256": engine_sha256,
            "private_vpx_used": False,
            "vpinfe_used": False,
            "isolation": {
                "HOME": str(self.root / "home"),
                "XDG_CONFIG_HOME": str(self.root / "config"),
                "XDG_DATA_HOME": str(self.root / "data"),
                "XDG_CACHE_HOME": str(self.root / "cache"),
                "PrefPath": str(self.root / "config" / "vpx"),
            },
        }

    def write_session_state(self, value: dict) -> None:
        self.prepare_writable_directories()
        descriptor, temporary = tempfile.mkstemp(
            prefix=".current.", suffix=".json", dir=self.session_state.parent
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o640)
            os.replace(temporary, self.session_state)
        except Exception:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise

    def launch_detached(self, relative_table: str) -> int:
        if self.game_pid.is_file():
            try:
                existing = int(self.game_pid.read_text(encoding="ascii").strip())
                os.kill(existing, 0)
            except (OSError, ValueError):
                self.game_pid.unlink(missing_ok=True)
            else:
                raise RuntimeIsolationError("isolated_engine_already_running")

        command = self.launch_command(relative_table)
        options: dict[str, object] = {}
        runtime_uid = os.geteuid()
        if os.geteuid() == 0:
            account = pwd.getpwnam("pinball")
            runtime_uid = account.pw_uid
            self.prepare_pinball_launch_paths(account.pw_uid, account.pw_gid)
            options.update(
                user=account.pw_uid,
                group=account.pw_gid,
                extra_groups=os.getgrouplist(account.pw_name, account.pw_gid),
            )
        environment = self.isolated_environment(runtime_uid)
        log_path = self.root / "logs" / "vpx-multiplayer.log"
        log_handle = log_path.open("ab", buffering=0)
        try:
            process = subprocess.Popen(
                command,
                cwd=self.engine,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                **options,
            )
        finally:
            log_handle.close()
        self.game_pid.write_text(str(process.pid) + "\n", encoding="ascii")
        self.game_pid.chmod(0o640)
        return process.pid

    def stop_detached(self) -> bool:
        if not self.game_pid.is_file():
            return False
        try:
            pid = int(self.game_pid.read_text(encoding="ascii").strip())
            executable = Path(f"/proc/{pid}/exe").resolve()
            executable.relative_to(self.engine.resolve())
        except (OSError, ValueError):
            self.game_pid.unlink(missing_ok=True)
            return False
        os.kill(pid, signal.SIGTERM)
        self.game_pid.unlink(missing_ok=True)
        return True


def install_engine_copy(layout: RuntimeLayout, source: Path) -> dict[str, object]:
    source = source.resolve()
    if not source.is_dir():
        raise RuntimeIsolationError("source_engine_directory_missing")
    if source == layout.root or layout.root in source.parents:
        raise RuntimeIsolationError("source_engine_inside_runtime")
    if layout.engine.exists():
        raise RuntimeIsolationError("isolated_engine_already_installed")

    source_matches = sorted(
        path for path in source.rglob("*") if path.is_file() and path.name in ENGINE_NAMES
    )
    if len(source_matches) != 1 or not os.access(source_matches[0], os.X_OK):
        raise RuntimeIsolationError("source_engine_ambiguous_or_missing")
    try:
        source_matches[0].resolve().relative_to(source)
    except ValueError as exc:
        raise RuntimeIsolationError("source_engine_symlink_escape") from exc

    layout.prepare_writable_directories()
    staging = layout.root / f".engine-staging-{os.getpid()}"
    if staging.exists():
        raise RuntimeIsolationError("engine_staging_exists")
    try:
        shutil.copytree(source, staging, symlinks=True)
        os.replace(staging, layout.engine)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise

    copied = layout.engine_binary()
    result = {
        "source": str(source),
        "source_engine_sha256": sha256_file(source_matches[0]),
        "copied_engine_sha256": sha256_file(copied),
        "copied_engine": str(copied),
    }
    if result["source_engine_sha256"] != result["copied_engine_sha256"]:
        raise RuntimeIsolationError("engine_copy_hash_mismatch")
    layout.write_session_state({"ok": True, "installation": result})
    return result


def drop_to_pinball() -> None:
    if os.geteuid() != 0:
        return
    account = pwd.getpwnam("pinball")
    os.initgroups(account.pw_name, account.pw_gid)
    os.setgid(account.pw_gid)
    os.setuid(account.pw_uid)
