from __future__ import annotations

import ctypes
from dataclasses import dataclass
from pathlib import Path


class DMDUtilError(RuntimeError):
    pass


@dataclass(slots=True)
class DisplayInfo:
    has_display: bool
    has_hd_display: bool
    width: int
    height: int


class _BridgeOptions(ctypes.Structure):
    _fields_ = [
        ("enable_zedmd_usb", ctypes.c_int),
        ("zedmd_device", ctypes.c_char_p),
        ("enable_zedmd_wifi", ctypes.c_int),
        ("zedmd_wifi_addr", ctypes.c_char_p),
        ("enable_pixelcade", ctypes.c_int),
        ("pixelcade_device", ctypes.c_char_p),
        ("enable_pin2dmd", ctypes.c_int),
        ("zedmd_brightness", ctypes.c_int),
        ("verbose", ctypes.c_int),
    ]


class _BridgeDisplayInfo(ctypes.Structure):
    _fields_ = [
        ("has_display", ctypes.c_int),
        ("has_hd_display", ctypes.c_int),
        ("width", ctypes.c_uint16),
        ("height", ctypes.c_uint16),
    ]


class _BridgeLibrary:
    def __init__(self, lib):
        self.lib = lib

    @classmethod
    def load(cls) -> "_BridgeLibrary":
        for candidate in _candidate_library_paths():
            if not candidate.exists():
                continue
            try:
                lib = ctypes.CDLL(str(candidate))
            except OSError:
                continue
            _configure_bridge(lib)
            return cls(lib)
        raise DMDUtilError(
            "Could not load libdmdutil bridge. Build it with: ./build_wrapper.sh"
        )


class DMDUtilConnection:
    def __init__(
        self,
        *,
        zedmd_device: str | None = None,
        zedmd_wifi_addr: str | None = None,
        pixelcade_device: str | None = None,
        enable_pin2dmd: bool = False,
        zedmd_brightness: int = -1,
        verbose: bool = False,
    ):
        self._bridge = _BridgeLibrary.load()
        options = _BridgeOptions(
            enable_zedmd_usb=1 if zedmd_device else 0,
            zedmd_device=_encode_optional(zedmd_device),
            enable_zedmd_wifi=1 if zedmd_wifi_addr else 0,
            zedmd_wifi_addr=_encode_optional(zedmd_wifi_addr),
            enable_pixelcade=1 if pixelcade_device else 0,
            pixelcade_device=_encode_optional(pixelcade_device),
            enable_pin2dmd=1 if enable_pin2dmd else 0,
            zedmd_brightness=zedmd_brightness,
            verbose=1 if verbose else 0,
        )
        self._handle = self._bridge.lib.vpindmd_dmdutil_create(ctypes.byref(options))
        if not self._handle:
            raise DMDUtilError("Failed to allocate libdmdutil context")

        info = self.get_info()
        if not info.has_display:
            raise DMDUtilError(self.last_error() or "libdmdutil found no displays")

    def close(self) -> None:
        if self._handle:
            self._bridge.lib.vpindmd_dmdutil_destroy(self._handle)
            self._handle = None

    def get_info(self) -> DisplayInfo:
        info = _BridgeDisplayInfo()
        if not self._bridge.lib.vpindmd_dmdutil_get_info(self._handle, ctypes.byref(info)):
            raise DMDUtilError(self.last_error() or "Failed to query display info")
        return DisplayInfo(
            has_display=bool(info.has_display),
            has_hd_display=bool(info.has_hd_display),
            width=int(info.width),
            height=int(info.height),
        )

    def send_rgb24(self, rgb_bytes: bytes, width: int, height: int, *, buffered: bool = False) -> None:
        payload = bytes(rgb_bytes)
        if len(payload) != width * height * 3:
            raise ValueError(f"Expected {width * height * 3} RGB bytes, got {len(payload)}")
        array_type = ctypes.c_uint8 * len(payload)
        payload_buffer = array_type.from_buffer_copy(payload)
        ok = self._bridge.lib.vpindmd_dmdutil_send_rgb24(
            self._handle,
            payload_buffer,
            width,
            height,
            1 if buffered else 0,
        )
        if not ok:
            raise DMDUtilError(self.last_error() or "Failed to send RGB24 frame")

    def clear(self, width: int, height: int) -> None:
        ok = self._bridge.lib.vpindmd_dmdutil_clear(self._handle, width, height)
        if not ok:
            raise DMDUtilError(self.last_error() or "Failed to clear display")

    def last_error(self) -> str:
        message = self._bridge.lib.vpindmd_dmdutil_last_error(self._handle)
        return message.decode("utf-8", errors="replace") if message else ""


def _candidate_library_paths() -> list[Path]:
    repo_root = Path(__file__).resolve().parent
    return [
        repo_root / "libdmdutil_python_bridge.so",
        repo_root / "libdmdutil_python_bridge.dylib",
        repo_root / "libdmdutil_python_bridge.dll",
        repo_root / "native" / "build" / "libdmdutil_python_bridge.so",
        repo_root / "native" / "build" / "Release" / "libdmdutil_python_bridge.so",
        repo_root / "native" / "build" / "libdmdutil_python_bridge.dylib",
        repo_root / "native" / "build" / "libdmdutil_python_bridge.dll",
        repo_root / "native" / "build" / "libvpindmd_dmdutil.so",
        repo_root / "native" / "build" / "Release" / "libvpindmd_dmdutil.so",
    ]


def _configure_bridge(lib) -> None:
    lib.vpindmd_dmdutil_create.argtypes = [ctypes.POINTER(_BridgeOptions)]
    lib.vpindmd_dmdutil_create.restype = ctypes.c_void_p
    lib.vpindmd_dmdutil_destroy.argtypes = [ctypes.c_void_p]
    lib.vpindmd_dmdutil_destroy.restype = None
    lib.vpindmd_dmdutil_get_info.argtypes = [ctypes.c_void_p, ctypes.POINTER(_BridgeDisplayInfo)]
    lib.vpindmd_dmdutil_get_info.restype = ctypes.c_int
    lib.vpindmd_dmdutil_send_rgb24.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint8), ctypes.c_uint16,
                                               ctypes.c_uint16, ctypes.c_int]
    lib.vpindmd_dmdutil_send_rgb24.restype = ctypes.c_int
    lib.vpindmd_dmdutil_clear.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_uint16]
    lib.vpindmd_dmdutil_clear.restype = ctypes.c_int
    lib.vpindmd_dmdutil_last_error.argtypes = [ctypes.c_void_p]
    lib.vpindmd_dmdutil_last_error.restype = ctypes.c_char_p


def _encode_optional(value: str | None) -> bytes | None:
    return value.encode("utf-8") if value else None
