"""CLI et agent de contrôle du runtime VPX MultiPlayers — LAB."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from . import COMPONENT_VERSION, PROTOCOL_VERSION
from .client import MultiplayerClientError, ServerClient, load_credentials
from .runtime import (
    RuntimeIsolationError,
    RuntimeLayout,
    drop_to_pinball,
    install_engine_copy,
    sha256_file,
)


def output(value: dict) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))


def client() -> ServerClient:
    state_path = Path(
        os.environ.get("PINCABOS_LINK_DEVICE_STATE")
        or "/var/lib/pincabos-link/device.json"
    )
    return ServerClient(load_credentials(state_path))


def active_session(server: ServerClient) -> tuple[dict, dict]:
    state = server.state()
    session = state.get("session")
    if not isinstance(session, dict) or not session.get("session_id"):
        raise MultiplayerClientError("multiplayer_session_missing")
    return state, session


def session_action(server: ServerClient, action: str, **payload: object) -> dict:
    _state, session = active_session(server)
    return server.action(action, str(session["session_id"]), **payload)


def state_payload(server: ServerClient, layout: RuntimeLayout) -> dict:
    value = server.state()
    value["local_runtime"] = layout.status()
    value["component_version"] = COMPONENT_VERSION
    value["protocol_version"] = PROTOCOL_VERSION
    return value


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(prog="pincabos-multiplayer-agent")
    commands = value.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
    commands.add_parser("status")
    commands.add_parser("create")

    join = commands.add_parser("join")
    join.add_argument("room_code")

    for name in ("prepare", "ready", "launch"):
        item = commands.add_parser(name)
        item.add_argument("table", help="chemin relatif sous tables-test/")
        if name == "launch":
            item.add_argument("--dry-run", action="store_true")
            item.add_argument("--detach", action="store_true")

    commands.add_parser("start")
    commands.add_parser("stop")

    watch = commands.add_parser("watch")
    watch.add_argument("--interval", type=float, default=2.0)

    install = commands.add_parser("install-engine")
    install.add_argument("source")
    return value


def run(args: argparse.Namespace) -> dict | None:
    layout = RuntimeLayout.configured()
    layout.prepare_writable_directories()

    if args.command == "doctor":
        return {"ok": True, "local_runtime": layout.status()}
    if args.command == "install-engine":
        return {"ok": True, "installation": install_engine_copy(layout, Path(args.source))}

    server = client()
    if args.command == "status":
        return state_payload(server, layout)
    if args.command == "create":
        return server.join()
    if args.command == "join":
        return server.join(args.room_code)

    if args.command in {"prepare", "ready"}:
        layout.engine_binary()
        table = layout.table(args.table)
        manifest_hash = sha256_file(table)
        payload = {"manifest_hash": manifest_hash}
        if args.command == "prepare":
            payload["package_version"] = "lab-1"
        return session_action(server, args.command, **payload)

    if args.command in {"start", "stop"}:
        result = session_action(server, args.command)
        if args.command == "stop":
            result["local_engine_stopped"] = layout.stop_detached()
        return result

    if args.command == "launch":
        _state, session = active_session(server)
        if session.get("phase") != "running":
            raise RuntimeIsolationError("multiplayer_session_not_running")
        command = layout.launch_command(args.table)
        if args.dry_run:
            return {
                "ok": True,
                "dry_run": True,
                "command": command,
                "environment": layout.status()["isolation"],
            }
        if args.detach:
            return {"ok": True, "engine_pid": layout.launch_detached(args.table)}
        environment = layout.isolated_environment()
        drop_to_pinball()
        os.chdir(layout.engine)
        os.execve(command[0], command, environment)
        return None

    if args.command == "watch":
        if args.interval < 1.0 or args.interval > 60.0:
            raise RuntimeIsolationError("watch_interval_invalid")
        while True:
            try:
                value = state_payload(server, layout)
            except (MultiplayerClientError, RuntimeIsolationError) as exc:
                value = {"ok": False, "error": str(exc), "local_runtime": layout.status()}
            layout.write_session_state(value)
            time.sleep(args.interval)

    raise RuntimeIsolationError("command_not_allowed")


def main(argv: list[str] | None = None) -> int:
    try:
        result = run(parser().parse_args(argv))
        if result is not None:
            output(result)
        return 0
    except (MultiplayerClientError, RuntimeIsolationError, OSError, ValueError) as exc:
        output({"ok": False, "error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
