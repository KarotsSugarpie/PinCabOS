from __future__ import annotations

import threading
import time

from dmdutil_backend import DMDUtilConnection, DisplayInfo
from media import iter_gif_frames, load_image_frame


class DMDController:
    ONE_SHOT_SETTLE_SECONDS = 0.12

    def __init__(
        self,
        *,
        host: str | None = None,
        device: str | None = None,
        pixelcade_device: str | None = None,
        pin2dmd: bool = False,
        width: int | None = None,
        height: int | None = None,
        brightness: int = -1,
        verbose: bool = False,
    ):
        if not any([host, device, pixelcade_device, pin2dmd]):
            raise ValueError("At least one display target must be provided")
        self.host = host
        self.device = device
        self.pixelcade_device = pixelcade_device
        self.pin2dmd = pin2dmd
        self.brightness = brightness
        self.verbose = verbose
        self._preferred_width = width
        self._preferred_height = height

        self._lock = threading.RLock()
        self._playback_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._connection: DMDUtilConnection | None = None
        self._info: DisplayInfo | None = None
        self._previous_frame: bytes | None = None

    def load(self) -> DisplayInfo:
        with self._lock:
            if self._connection is None or self._info is None:
                self._connection = DMDUtilConnection(
                    zedmd_device=self.device,
                    zedmd_wifi_addr=self.host,
                    pixelcade_device=self.pixelcade_device,
                    enable_pin2dmd=self.pin2dmd,
                    zedmd_brightness=self.brightness,
                    verbose=self.verbose,
                )
                backend_info = self._connection.get_info()
                self._info = DisplayInfo(
                    has_display=backend_info.has_display,
                    has_hd_display=backend_info.has_hd_display,
                    width=self._preferred_width or backend_info.width,
                    height=self._preferred_height or backend_info.height,
                )
            return self._info

    def unload(self) -> None:
        self.stop(clear=False)
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None
            self._info = None
            self._previous_frame = None

    def info(self) -> DisplayInfo:
        return self.load()

    def hold_image(self, path: str, *, fit_mode: str = "stretch") -> None:
        self.stop(clear=False)
        with self._lock:
            info = self.load()
            frame = load_image_frame(path, info.width, info.height, fit_mode=fit_mode)
            self._send_rgb_frame(frame.rgb_bytes)
            self._settle()

    def send_rgb_frame(self, rgb_bytes: bytes) -> bool:
        self.stop(clear=False)
        with self._lock:
            self.load()
            return self._send_rgb_frame(rgb_bytes)

    def clear(self) -> None:
        self.stop(clear=False)
        with self._lock:
            info = self.load()
            self._connection.clear(info.width, info.height)
            self._previous_frame = bytes(info.width * info.height * 3)
            self._settle()

    def stop(self, *, clear: bool = False) -> None:
        thread = None
        with self._lock:
            self._stop_event.set()
            thread = self._playback_thread
            self._playback_thread = None
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)
        self._stop_event.clear()
        if clear:
            with self._lock:
                info = self.load()
                self._connection.clear(info.width, info.height)
                self._previous_frame = bytes(info.width * info.height * 3)
                self._settle()

    def play_video(
        self,
        path: str,
        *,
        loop: bool | None = None,
        loops: int | None = None,
        fit_mode: str = "stretch",
    ) -> None:
        self.stop(clear=False)
        self.load()
        if loops is not None and loops < 1:
            raise ValueError("loops must be >= 1")
        if loops is None:
            loops = 0 if (loop is True) else 1
        with self._lock:
            self._stop_event.clear()
            self._playback_thread = threading.Thread(
                target=self._playback_worker,
                args=(path, loops, fit_mode),
                daemon=True,
            )
            self._playback_thread.start()

    def wait(self, timeout: float | None = None) -> None:
        with self._lock:
            thread = self._playback_thread
        if thread is None or not thread.is_alive():
            return
        if threading.current_thread() is thread:
            return
        thread.join(timeout=timeout)

    def _playback_worker(self, path: str, loops: int, fit_mode: str) -> None:
        completed_loops = 0
        while not self._stop_event.is_set():
            info = self.info()
            for frame in iter_gif_frames(path, info.width, info.height, fit_mode=fit_mode):
                if self._stop_event.is_set():
                    return
                started = time.monotonic()
                with self._lock:
                    self._send_rgb_frame(frame.rgb_bytes)
                elapsed_ms = (time.monotonic() - started) * 1000.0
                remaining = max(frame.duration_ms - elapsed_ms, 0.0) / 1000.0
                if self._stop_event.wait(remaining):
                    return
            completed_loops += 1
            if loops != 0 and completed_loops >= loops:
                return

    def _send_rgb_frame(self, rgb_bytes: bytes) -> bool:
        info = self._info
        expected = info.width * info.height * 3
        if len(rgb_bytes) != expected:
            raise ValueError(f"Expected {expected} RGB bytes, got {len(rgb_bytes)}")
        if self._previous_frame == rgb_bytes:
            return False
        self._connection.send_rgb24(rgb_bytes, info.width, info.height)
        self._previous_frame = bytes(rgb_bytes)
        return True

    def _settle(self, seconds: float | None = None) -> None:
        time.sleep(self.ONE_SHOT_SETTLE_SECONDS if seconds is None else max(seconds, 0.0))


__all__ = ["DMDController", "DisplayInfo"]
