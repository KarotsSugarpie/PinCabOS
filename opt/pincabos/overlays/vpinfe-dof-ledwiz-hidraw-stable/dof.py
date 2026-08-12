"""
dof.py — Python wrapper for libdof (https://github.com/jsm174/libdof)

Requires libdof_python shared library built from dof_c_api.cpp
(`.so` on Linux, `.dylib` on macOS, `.dll` on Windows).

Quick start:
    import dof

    dof.set_base_path('/home/user/.vpinball/')
    dof.set_log_callback(lambda level, msg: print(f'[DOF] {msg}'))

    with dof.DOF() as d:
        d.init('afm')                        # Attack From Mars ROM
        d.data_receive('S', 27, 1)           # solenoid 27 on
        import time; time.sleep(0.5)
        d.data_receive('S', 27, 0)           # solenoid 27 off
        # finish() is called automatically on context-manager exit
"""

import ctypes
import ctypes.util
import os
import sys
from enum import IntEnum
from typing import Callable, Optional


# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

class LogLevel(IntEnum):
    INFO  = 0
    WARN  = 1
    ERROR = 2
    DEBUG = 3


# ---------------------------------------------------------------------------
# Internal ctypes state (module-level singleton pattern mirrors C singleton)
# ---------------------------------------------------------------------------

_lib: Optional[ctypes.CDLL] = None
_log_callback_ref = None          # Prevent the ctypes wrapper from being GC'd

# ctypes function type for the C-level log callback
_LogCallbackType = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_char_p)


def _library_candidates(script_dir: str) -> list[str]:
    """Return platform-appropriate shared library candidates."""
    if sys.platform.startswith('win'):
        names = ['libdof_python.dll', 'dof_python.dll']
    elif sys.platform == 'darwin':
        names = ['libdof_python.dylib', 'libdof_python.so']
    else:
        names = ['libdof_python.so', 'libdof_python.dylib']
    return [os.path.join(script_dir, name) for name in names] + names


def _prepare_windows_dll_search(script_dir: str) -> None:
    """Ensure dependent DLLs in this folder are discoverable on Python 3.8+."""
    if not sys.platform.startswith('win'):
        return
    add_dir = getattr(os, 'add_dll_directory', None)
    if add_dir:
        add_dir(script_dir)


def _load_lib(lib_path: Optional[str] = None) -> ctypes.CDLL:
    """Load (or return the already-loaded) wrapper shared library."""
    global _lib
    if _lib is not None:
        return _lib

    script_dir = os.path.dirname(os.path.abspath(__file__))
    if lib_path is None:
        candidates = _library_candidates(script_dir)
        for c in candidates:
            if os.path.exists(c):
                lib_path = c
                break

    if lib_path is None:
        raise FileNotFoundError(
            "Cannot find libdof_python shared library (.so/.dylib/.dll). "
            "Ensure release files are in the same folder, or pass lib_path= explicitly."
        )

    _prepare_windows_dll_search(script_dir)
    _lib = ctypes.CDLL(lib_path)
    _setup_api(_lib)
    return _lib


def _setup_api(lib: ctypes.CDLL) -> None:
    """Declare argtypes / restype for every C function we expose."""

    # --- Config ---
    lib.dof_config_set_base_path.restype  = None
    lib.dof_config_set_base_path.argtypes = [ctypes.c_char_p]

    lib.dof_config_set_log_level.restype  = None
    lib.dof_config_set_log_level.argtypes = [ctypes.c_int]

    lib.dof_config_set_log_callback.restype  = None
    lib.dof_config_set_log_callback.argtypes = [ctypes.c_void_p]

    # --- Lifecycle ---
    lib.dof_create.restype  = ctypes.c_void_p
    lib.dof_create.argtypes = []

    lib.dof_destroy.restype  = None
    lib.dof_destroy.argtypes = [ctypes.c_void_p]

    # --- Operations ---
    lib.dof_init.restype  = None
    lib.dof_init.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]

    lib.dof_data_receive.restype  = None
    lib.dof_data_receive.argtypes = [ctypes.c_void_p, ctypes.c_char,
                                      ctypes.c_int, ctypes.c_int]

    lib.dof_finish.restype  = None
    lib.dof_finish.argtypes = [ctypes.c_void_p]


# ---------------------------------------------------------------------------
# Module-level configuration helpers (wrap the DOF::Config singleton)
# ---------------------------------------------------------------------------

def load_lib(lib_path: Optional[str] = None) -> None:
    """
    Explicitly load the shared library.
    Optional — the library is loaded lazily on first use if not called.

    Args:
        lib_path: Path to libdof_python shared library.
                  Defaults to a platform-specific filename in this module dir.
    """
    _load_lib(lib_path)


def set_base_path(path: str, lib_path: Optional[str] = None) -> None:
    """
    Set the root directory where DOF searches for its configuration files
    (GlobalConfig_B2SServer.xml, directoutputconfig/, etc.).

    On Linux/macOS the default is ~/.vpinball/.
    A trailing slash is added automatically if missing.

    Args:
        path: Absolute or relative directory path.
    """
    lib = _load_lib(lib_path)
    if not path.endswith(('/', '\\')):
        path += '/'
    lib.dof_config_set_base_path(path.encode())


def set_log_level(level: LogLevel, lib_path: Optional[str] = None) -> None:
    """
    Set the minimum log level.

    Args:
        level: A LogLevel enum value (INFO, WARN, ERROR, DEBUG).
    """
    lib = _load_lib(lib_path)
    lib.dof_config_set_log_level(int(level))


def set_log_callback(
    callback: Optional[Callable[[LogLevel, str], None]],
    lib_path: Optional[str] = None,
) -> None:
    """
    Register a Python function to receive log messages from libdof.
    Pass None to disable the callback.

    The callback signature is:  callback(level: LogLevel, message: str)

    Example:
        def my_log(level, msg):
            print(f'[{level.name}] {msg}')

        dof.set_log_callback(my_log)
    """
    global _log_callback_ref
    lib = _load_lib(lib_path)

    if callback is None:
        _log_callback_ref = None
        lib.dof_config_set_log_callback(None)
        return

    def _c_callback(level_int: int, raw_msg: bytes) -> None:
        try:
            callback(LogLevel(level_int),
                     raw_msg.decode('utf-8', errors='replace') if raw_msg else '')
        except Exception as exc:
            # Never let Python exceptions propagate into C code
            print(f'[dof.py] log callback raised: {exc}')

    _log_callback_ref = _LogCallbackType(_c_callback)
    lib.dof_config_set_log_callback(_log_callback_ref)


# ---------------------------------------------------------------------------
# DOF class
# ---------------------------------------------------------------------------

class DOF:
    """
    Python wrapper around the libdof DOF object.

    Typical usage:

        import dof

        dof.set_base_path('/home/user/.vpinball/')

        with dof.DOF() as d:
            d.init('afm')
            d.data_receive('S', 27, 1)   # solenoid on
            ...                          # do stuff
            # d.finish() called automatically on exit

    If you prefer manual management:

        d = dof.DOF()
        d.init('afm')
        d.data_receive('S', 27, 1)
        d.finish()
        d.destroy()
    """

    def __init__(self, lib_path: Optional[str] = None) -> None:
        self._lib = _load_lib(lib_path)
        self._handle: Optional[int] = self._lib.dof_create()
        if not self._handle:
            raise RuntimeError("dof_create() returned NULL")

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def init(self, rom_name: str, table_filename: str = '') -> None:
        """
        Initialise DOF for a specific ROM.

        Must be called before the first data_receive().
        Can be called again (after finish()) to switch to a different ROM.

        Args:
            rom_name:       Short ROM identifier, e.g. 'afm', 'tna', 'ij_l7'.
            table_filename: Optional path to the table file.  Leave empty
                            to let DOF locate it automatically.
        """
        self._require_handle()
        self._lib.dof_init(
            self._handle,
            (table_filename or '').encode(),
            rom_name.encode(),
        )

    def data_receive(self,
                     type_char: 'str | bytes | int',
                     number: int,
                     value: int) -> None:
        """
        Send a game event to DOF.

        Args:
            type_char: Element type.  Common values:
                         'S' – solenoid / coil
                         'L' – lamp
                         'W' – switch / GI
                         'E' – named element (VPX-style)
                       Can be a single-character str, a bytes object, or
                       the raw ASCII integer.
            number:    Element number (table-specific).
            value:     0 = off, 1 = on, or an analogue level 0-255.
        """
        self._require_handle()
        if isinstance(type_char, str):
            type_char = type_char.encode()
        elif isinstance(type_char, int):
            type_char = bytes([type_char])
        self._lib.dof_data_receive(self._handle, type_char, number, value)

    def finish(self) -> None:
        """
        End the current DOF session (turns off all outputs, etc.).
        Safe to call multiple times.  Call init() again to start a new session.
        """
        if self._handle:
            self._lib.dof_finish(self._handle)

    def destroy(self) -> None:
        """Free the underlying C++ DOF object. Do not use the instance after this."""
        if self._handle:
            self._lib.dof_destroy(self._handle)
            self._handle = None

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> 'DOF':
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.finish()
        self.destroy()
        return False   # do not suppress exceptions

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_handle(self) -> None:
        if not self._handle:
            raise RuntimeError("DOF instance has been destroyed.")

    def __del__(self) -> None:
        if getattr(self, '_handle', None):
            try:
                self._lib.dof_destroy(self._handle)
            except Exception:
                pass
            self._handle = None
