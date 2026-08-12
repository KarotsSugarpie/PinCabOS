#!/usr/bin/env python3
"""Threaded DOF runners for embedding in other Python programs.

This reproduces the behavior of:
    python3 example.py --rom "pinupmenu" --random-e --random-interval-sec 1.1

Usage:
    from dof_runner import RandomDofRunner, SingleEventDofRunner

    runner = RandomDofRunner(rom="pinupmenu", random_interval_sec=1.1)
    runner.start()
    # ... do other work ...
    runner.stop()

    single = SingleEventDofRunner(rom="pinupmenu")
    single.start()
    single.send_event("E", 905)
    single.stop_event()
    single.stop()
"""

from __future__ import annotations

import os
import queue
import random
import sys
import threading
from typing import Callable, Optional

import dof


def _default_base_path() -> str:
    home = os.path.expanduser("~")
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", home)
        return os.path.join(appdata, "VPinballX", "10.8")
    if sys.platform == "darwin":
        return os.path.join(home, "Library", "Application Support", "VPinballX", "10.8")
    return os.path.join(home, ".local", "share", "VPinballX", "10.8")


def _default_log_handler(level: dof.LogLevel, message: str) -> None:
    tag = {
        dof.LogLevel.INFO: "[INFO ]",
        dof.LogLevel.WARN: "[WARN ]",
        dof.LogLevel.ERROR: "[ERROR]",
        dof.LogLevel.DEBUG: "[DEBUG]",
    }.get(level, "[?????]")
    print(f"{tag} {message}")


class RandomDofRunner:
    """Run random E-events in a dedicated thread with explicit start/stop control.

    Each `start()` creates a fresh DOF instance and calls `init()`.
    Each `stop()` signals the worker thread and ensures `finish()` + `destroy()`.
    """

    def __init__(
        self,
        rom: str,
        *,
        random_min: int = 901,
        random_max: int = 990,
        random_on_value: int = 1,
        random_interval_sec: float = 1.1,
        only_existing_pairs: bool = False,
        config_ini: str = "",
        base_path: str = "",
        debug: bool = False,
        log_callback: Optional[Callable[[dof.LogLevel, str], None]] = None,
    ) -> None:
        if random_min < 0:
            raise ValueError("random_min must be >= 0")
        if random_max < 0:
            raise ValueError("random_max must be >= 0")
        if random_min > random_max:
            raise ValueError("random_min must be <= random_max")
        if random_on_value < 0:
            raise ValueError("random_on_value must be >= 0")
        if random_interval_sec <= 0:
            raise ValueError("random_interval_sec must be > 0")

        self._rom_input = rom
        self._rom_key = rom.strip().replace(" ", "_")
        self._random_min = random_min
        self._random_max = random_max
        self._random_on_value = random_on_value
        self._random_interval_sec = random_interval_sec
        self._only_existing_pairs = only_existing_pairs
        self._config_ini = config_ini
        self._base_path = base_path if base_path else _default_base_path()
        self._debug = debug
        self._log_callback = log_callback or _default_log_handler

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_error: Optional[Exception] = None

    def start(self) -> bool:
        """Start the background runner.

        Returns:
            True if a new worker was started, False if already running.
        """
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            self._last_error = None
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._worker_main, daemon=True)
            self._thread.start()
            return True

    def stop(self, timeout: float = 10.0) -> bool:
        """Stop the background runner and release DOF resources.

        Returns:
            True if stopped cleanly within timeout (or already stopped), else False.
        """
        with self._lock:
            thread = self._thread
            if thread is None:
                return True
            self._stop_event.set()

        thread.join(timeout)
        stopped = not thread.is_alive()
        if stopped:
            with self._lock:
                if self._thread is thread:
                    self._thread = None
        return stopped

    def is_running(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def last_error(self) -> Optional[Exception]:
        with self._lock:
            return self._last_error

    def _worker_main(self) -> None:
        d: Optional[dof.DOF] = None
        last_number: Optional[int] = None
        try:
            dof.set_log_callback(self._log_callback)
            dof.set_log_level(dof.LogLevel.DEBUG if self._debug else dof.LogLevel.INFO)
            dof.set_base_path(self._base_path)

            d = dof.DOF()
            d.init(self._rom_key)
            while not self._stop_event.wait(self._random_interval_sec):
                number = random.randint(self._random_min, self._random_max)
                if last_number is not None:
                    d.data_receive("E", last_number, 0)
                d.data_receive("E", number, self._random_on_value)
                last_number = number
        except Exception as exc:
            with self._lock:
                self._last_error = exc
        finally:
            if d is not None:
                if last_number is not None:
                    try:
                        d.data_receive("E", last_number, 0)
                    except Exception:
                        pass
                try:
                    d.finish()
                except Exception:
                    pass
                try:
                    d.destroy()
                except Exception:
                    pass

            with self._lock:
                self._thread = None


class SingleEventDofRunner:
    """Run one active DOF event at a time in a dedicated thread.

    `start()` creates a DOF instance and keeps it ready for commands.
    `send_event()` turns on one event and keeps it active until replaced or stopped.
    `stop_event()` turns off the current event without destroying DOF.
    `stop()` shuts the worker down and releases DOF resources.
    """

    def __init__(
        self,
        rom: str,
        *,
        default_on_value: int = 1,
        base_path: str = "",
        debug: bool = False,
        log_callback: Optional[Callable[[dof.LogLevel, str], None]] = None,
    ) -> None:
        if default_on_value < 0:
            raise ValueError("default_on_value must be >= 0")

        self._rom_input = rom
        self._rom_key = rom.strip().replace(" ", "_")
        self._default_on_value = default_on_value
        self._base_path = base_path if base_path else _default_base_path()
        self._debug = debug
        self._log_callback = log_callback or _default_log_handler

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_error: Optional[Exception] = None
        self._command_queue: queue.Queue[tuple[str, str, int, int]] = queue.Queue()

    def start(self) -> bool:
        """Start the background event worker.

        Returns:
            True if a new worker was started, False if already running.
        """
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            self._last_error = None
            self._stop_event.clear()
            self._clear_pending_commands()
            self._thread = threading.Thread(target=self._worker_main, daemon=True)
            self._thread.start()
            return True

    def stop(self, timeout: float = 10.0) -> bool:
        """Stop the worker and release DOF resources."""
        with self._lock:
            thread = self._thread
            if thread is None:
                return True
            self._stop_event.set()
            self._command_queue.put(("shutdown", "", 0, 0))

        thread.join(timeout)
        stopped = not thread.is_alive()
        if stopped:
            with self._lock:
                if self._thread is thread:
                    self._thread = None
        return stopped

    def is_running(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def last_error(self) -> Optional[Exception]:
        with self._lock:
            return self._last_error

    def send_event(
        self,
        type_char: str,
        number: int,
        *,
        on_value: Optional[int] = None,
    ) -> None:
        """Turn on one event and keep it active until replaced or stopped."""
        if len(type_char) != 1:
            raise ValueError("type_char must be a single character such as 'E' or 'S'")
        if number < 0:
            raise ValueError("number must be >= 0")

        event_on_value = self._default_on_value if on_value is None else on_value

        if event_on_value < 0:
            raise ValueError("on_value must be >= 0")
        if not self.is_running():
            raise RuntimeError("SingleEventDofRunner is not running. Call start() first.")

        self._clear_pending_commands()
        self._command_queue.put(("event", type_char, number, event_on_value))

    def send_event_token(
        self,
        event_token: str,
        *,
        on_value: Optional[int] = None,
    ) -> None:
        """Turn on one event from a token like `E905`."""
        if len(event_token) < 2:
            raise ValueError("event_token must look like 'E905'")

        type_char = event_token[0]
        try:
            number = int(event_token[1:])
        except ValueError as exc:
            raise ValueError("event_token must look like 'E905'") from exc

        self.send_event(type_char, number, on_value=on_value)

    def stop_event(self) -> None:
        """Turn off the current active event and keep the runner alive."""
        if not self.is_running():
            raise RuntimeError("SingleEventDofRunner is not running. Call start() first.")

        self._clear_pending_commands()
        self._command_queue.put(("clear", "", 0, 0))

    def _clear_pending_commands(self) -> None:
        while True:
            try:
                self._command_queue.get_nowait()
            except queue.Empty:
                return

    def _worker_main(self) -> None:
        d: Optional[dof.DOF] = None
        active_event: Optional[tuple[str, int]] = None
        try:
            dof.set_log_callback(self._log_callback)
            dof.set_log_level(dof.LogLevel.DEBUG if self._debug else dof.LogLevel.INFO)
            dof.set_base_path(self._base_path)

            d = dof.DOF()
            d.init(self._rom_key)

            while not self._stop_event.is_set():
                try:
                    command, type_char, number, on_value = self._command_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                if command == "shutdown" or self._stop_event.is_set():
                    break

                if active_event is not None:
                    active_type_char, active_number = active_event
                    d.data_receive(active_type_char, active_number, 0)
                    active_event = None

                if command == "event":
                    d.data_receive(type_char, number, on_value)
                    active_event = (type_char, number)
        except Exception as exc:
            with self._lock:
                self._last_error = exc
        finally:
            if d is not None:
                if active_event is not None:
                    try:
                        active_type_char, active_number = active_event
                        d.data_receive(active_type_char, active_number, 0)
                    except Exception:
                        pass
                try:
                    d.finish()
                except Exception:
                    pass
                try:
                    d.destroy()
                except Exception:
                    pass

            with self._lock:
                self._thread = None
