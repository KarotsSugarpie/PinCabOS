#!/usr/bin/env python3
# PinCabOs-File created by Karots Sugarpie
"""PinCabOS DudesCab protocol bridge V3.2.3 persistent maintenance lock.

Implements only commands documented in the DudesCab Developer Guide:
- Common protocol: handshake, admin mode, version, status, log level, reset,
  status monitoring and watchdog test.
- PWM outputs: get config, all-off and bounded output tests.
- MX outputs: handshake, infos, get config, all-off and built-in tests.
- TinyUSB serial log reading.

Admin GetConfig (command 100) is enabled read-only from the official configurator DLL metadata. Admin write and Flash-memory commands remain absent.
"""

from __future__ import annotations

import base64
import ctypes
import errno
import json
import os
import re
import struct
import subprocess
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any

from flask import jsonify, request

MARKER = "PINCABOS_DUDESCAB_PROTOCOL_V323_PERSISTENT_MAINTENANCE"
VID = 0x2E8A
PID = 0x106F
PACKET_SIZE = 64
PREFIX_SIZE = 5
MAX_PART_DATA = PACKET_SIZE - PREFIX_SIZE

REPORT_GAMEPAD = 1
REPORT_KEYBOARD = 2
REPORT_OUTPUTS = 3
REPORT_ADMIN = 4
REPORT_MX = 5

ERROR_CODES = {
    0: "Aucune",
    1: "Init CPU Frequency",
    2: "Init Inputs Multiplex",
    3: "Init Admin device",
    4: "Init Pwm outputs device",
    5: "Init ALed outputs device",
    6: "Init Walter drivers",
    7: "Init Keyboard device",
    8: "Init Gamepad device",
    9: "Init Accelerometer",
    10: "Init Plunger",
    11: "Flash memory save",
    12: "Flash memory load",
    13: "Send config to Admin",
    14: "Incoming communication overflow",
    15: "Incoming command ignored",
    16: "Plunger calibration",
    17: "PWM Output on non configured Walter",
    18: "PWM Output on disabled Walter output",
    19: "PWM Output security reset",
    20: "Comm buffer invalid size",
    21: "Comm buffer write overflow",
    22: "Comm buffer missing data",
    23: "Comm buffer invalid seek",
    24: "Watchdog causes DudesCab reboot",
}
STATUS_NAMES = {0: "Init", 1: "Calibration", 2: "Idle", 3: "Warning", 4: "Error"}
LOG_LEVELS = {"none": 0, "errors": 1, "warning": 2, "warnings": 2, "infos": 3, "info": 3, "debug": 4}
MX_TESTS = {"none": 0, "rgb": 1, "colors": 2, "couleurs": 2, "laser": 3}

_io_lock = threading.RLock()
_operation_lock = threading.RLock()
_state_lock = threading.RLock()
_admin_enabled = False
_last_probe: dict[str, Any] = {}
_output_timers: dict[tuple[int, int], threading.Timer] = {}
_serial_lines: deque[str] = deque(maxlen=1200)
_serial_partial = ""

MAINTENANCE_HELPER = "/usr/local/sbin/pincabos-dudescab-maintenance"
MAINTENANCE_TIMEOUT = 0


class DudesCabProtocolError(RuntimeError):
    pass


class _HidApi:
    """Small ctypes wrapper around libhidapi-hidraw already present in PinCabOS."""

    def __init__(self) -> None:
        candidates = (
            "libhidapi-hidraw.so.0",
            "libhidapi-hidraw.so",
            "/usr/lib/x86_64-linux-gnu/libhidapi-hidraw.so.0",
        )
        last: Exception | None = None
        self.lib = None
        for candidate in candidates:
            try:
                self.lib = ctypes.CDLL(candidate)
                break
            except OSError as exc:
                last = exc
        if self.lib is None:
            raise DudesCabProtocolError(f"libhidapi-hidraw introuvable: {last}")

        self.lib.hid_init.argtypes = []
        self.lib.hid_init.restype = ctypes.c_int
        self.lib.hid_open_path.argtypes = [ctypes.c_char_p]
        self.lib.hid_open_path.restype = ctypes.c_void_p
        self.lib.hid_write.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_size_t]
        self.lib.hid_write.restype = ctypes.c_int
        self.lib.hid_read_timeout.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_size_t, ctypes.c_int]
        self.lib.hid_read_timeout.restype = ctypes.c_int
        self.lib.hid_set_nonblocking.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.lib.hid_set_nonblocking.restype = ctypes.c_int
        self.lib.hid_close.argtypes = [ctypes.c_void_p]
        self.lib.hid_close.restype = None
        self.lib.hid_error.argtypes = [ctypes.c_void_p]
        self.lib.hid_error.restype = ctypes.c_wchar_p
        if self.lib.hid_init() != 0:
            raise DudesCabProtocolError("hid_init a échoué")

    def open(self, path: str) -> ctypes.c_void_p:
        handle = self.lib.hid_open_path(os.fsencode(path))
        if not handle:
            raise DudesCabProtocolError(f"Impossible d'ouvrir {path} avec hidapi")
        return handle

    def error(self, handle: ctypes.c_void_p) -> str:
        try:
            return self.lib.hid_error(handle) or "erreur HID inconnue"
        except Exception:
            return "erreur HID inconnue"


_hidapi_instance: _HidApi | None = None


def _hidapi() -> _HidApi:
    global _hidapi_instance
    if _hidapi_instance is None:
        _hidapi_instance = _HidApi()
    return _hidapi_instance


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="ascii", errors="ignore").strip()
    except Exception:
        return ""


def _interface_number(dev: Path) -> int | None:
    try:
        node = (Path("/sys/class/hidraw") / dev.name / "device").resolve()
    except Exception:
        return None
    for parent in (node, *node.parents):
        raw = _read_text(parent / "bInterfaceNumber")
        if raw:
            try:
                return int(raw, 16)
            except ValueError:
                return None
    return None


def _report_ids(dev: Path) -> list[int]:
    descriptor = Path("/sys/class/hidraw") / dev.name / "device" / "report_descriptor"
    ids: set[int] = set()
    try:
        raw = descriptor.read_bytes()
        for index in range(len(raw) - 1):
            if raw[index] == 0x85:  # HID Report ID item
                ids.add(raw[index + 1])
    except Exception:
        pass
    if not ids:
        # Fallback matching the composite USB interface order visible on DudesCab.
        interface = _interface_number(dev)
        fallback = {2: REPORT_GAMEPAD, 3: REPORT_KEYBOARD, 4: REPORT_OUTPUTS, 5: REPORT_ADMIN, 6: REPORT_MX}
        if interface in fallback:
            ids.add(fallback[interface])
    return sorted(ids)


def _is_dudescab_hidraw(dev: Path) -> bool:
    try:
        uevent = (Path("/sys/class/hidraw") / dev.name / "device" / "uevent").read_text(
            encoding="ascii", errors="ignore"
        ).upper()
    except Exception:
        return False
    return "00002E8A:0000106F" in uevent or "2E8A:106F" in uevent


def hid_nodes() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for dev in sorted(Path("/dev").glob("hidraw*")):
        if not _is_dudescab_hidraw(dev):
            continue
        rows.append(
            {
                "path": str(dev),
                "interface": _interface_number(dev),
                "report_ids": _report_ids(dev),
                "readable": os.access(dev, os.R_OK),
                "writable": os.access(dev, os.W_OK),
            }
        )
    return rows


def _node_for_report(report_id: int) -> str:
    for row in hid_nodes():
        if report_id in row["report_ids"]:
            if not row["readable"] or not row["writable"]:
                raise DudesCabProtocolError(f"Permissions HID refusées sur {row['path']}")
            return str(row["path"])
    raise DudesCabProtocolError(f"Interface HID ReportID {report_id} introuvable")


def _frame_parts(report_id: int, command: int, payload: bytes) -> list[bytes]:
    if not (1 <= report_id <= 255 and 0 <= command <= 255):
        raise ValueError("ReportID ou commande invalide")
    chunks = [payload[i : i + MAX_PART_DATA] for i in range(0, len(payload), MAX_PART_DATA)] or [b""]
    if len(chunks) > 255:
        raise ValueError("Message HID trop volumineux")
    frames: list[bytes] = []
    for index, chunk in enumerate(chunks):
        prefix = bytes((report_id, command, index, len(chunks), len(chunk)))
        frames.append((prefix + chunk).ljust(PACKET_SIZE, b"\x00"))
    return frames


def _normalize_read(raw: bytes, report_id: int) -> bytes:
    # hidapi normally returns the ReportID as byte zero. Some backends may add a
    # zero placeholder before it; accept both forms without guessing payload.
    if len(raw) >= PREFIX_SIZE and raw[0] == report_id:
        return raw
    if len(raw) >= PREFIX_SIZE + 1 and raw[0] == 0 and raw[1] == report_id:
        return raw[1:]
    return raw


def hid_command(
    report_id: int,
    command: int,
    payload: bytes = b"",
    *,
    expect_response: bool,
    timeout_ms: int = 1400,
) -> bytes:
    """Send one documented multipart command and optionally reassemble reply."""

    path = _node_for_report(report_id)
    api = _hidapi()
    with _io_lock:
        handle = api.open(path)
        try:
            api.lib.hid_set_nonblocking(handle, 1)
            drain = (ctypes.c_ubyte * (PACKET_SIZE + 1))()
            for _ in range(16):
                if api.lib.hid_read_timeout(handle, drain, len(drain), 0) <= 0:
                    break
            api.lib.hid_set_nonblocking(handle, 0)

            for frame in _frame_parts(report_id, command, payload):
                buf = (ctypes.c_ubyte * len(frame)).from_buffer_copy(frame)
                written = api.lib.hid_write(handle, buf, len(frame))
                if written < 0:
                    raise DudesCabProtocolError(
                        f"Écriture HID échouée sur {path}: {api.error(handle)}"
                    )
                if written != len(frame):
                    raise DudesCabProtocolError(
                        f"Écriture HID incomplète sur {path}: {written}/{len(frame)}"
                    )

            if not expect_response:
                return b""

            deadline = time.monotonic() + timeout_ms / 1000.0
            parts: dict[int, bytes] = {}
            expected_parts: int | None = None
            seen: list[str] = []
            while time.monotonic() < deadline:
                remaining = max(1, int((deadline - time.monotonic()) * 1000))
                timeout = min(160, remaining)
                buffer = (ctypes.c_ubyte * (PACKET_SIZE + 1))()
                count = api.lib.hid_read_timeout(handle, buffer, len(buffer), timeout)
                if count < 0:
                    raise DudesCabProtocolError(
                        f"Lecture HID échouée sur {path}: {api.error(handle)}"
                    )
                if count == 0:
                    continue
                raw = _normalize_read(bytes(buffer[:count]), report_id)
                seen.append(raw[:12].hex())
                if len(raw) < PREFIX_SIZE:
                    continue
                rid, response_command, part_number, nb_parts, size = raw[:PREFIX_SIZE]
                if rid != report_id or response_command != command:
                    continue
                if nb_parts < 1 or part_number >= nb_parts or size > MAX_PART_DATA:
                    continue
                if PREFIX_SIZE + size > len(raw):
                    continue
                if expected_parts is None:
                    expected_parts = nb_parts
                elif expected_parts != nb_parts:
                    parts.clear()
                    expected_parts = nb_parts
                parts[part_number] = raw[PREFIX_SIZE : PREFIX_SIZE + size]
                if expected_parts is not None and len(parts) == expected_parts:
                    return b"".join(parts[i] for i in range(expected_parts))

            detail = f"; trames vues={','.join(seen[-5:])}" if seen else ""
            raise DudesCabProtocolError(
                f"Délai dépassé pour ReportID {report_id}, commande {command}{detail}"
            )
        finally:
            api.lib.hid_close(handle)


def _ascii(data: bytes) -> str:
    return data.rstrip(b"\x00").decode("utf-8", errors="replace")


def _parse_version(data: bytes) -> dict[str, Any]:
    if len(data) < 5:
        raise DudesCabProtocolError(f"Réponse GetVersion trop courte: {data.hex()}")
    result = {
        "major": data[0],
        "minor": data[1],
        "revision": data[2],
        "unit_number": data[3],
        "max_extensions": data[4],
        "config_version": data[5] if len(data) >= 6 else None,
        "raw_hex": data.hex(),
    }
    result["text"] = f"{result['major']}.{result['minor']}.{result['revision']}"
    return result


def _parse_status(data: bytes) -> dict[str, Any]:
    if len(data) < 3:
        raise DudesCabProtocolError(f"Réponse GetStatus trop courte: {data.hex()}")
    status, flags, error = data[:3]
    return {
        "code": status,
        "name": STATUS_NAMES.get(status, f"Inconnu ({status})"),
        "flags": flags,
        "night_mode": bool(flags & 0x01),
        "admin_mode": bool(flags & 0x02),
        "shift_active": bool(flags & 0x04),
        "last_error": error,
        "last_error_text": ERROR_CODES.get(error, f"Code inconnu {error}"),
        "raw_hex": data.hex(),
    }


def _parse_pwm_config(data: bytes) -> dict[str, Any]:
    if len(data) < 4:
        raise DudesCabProtocolError(f"Réponse PWM GetConfig trop courte: {data.hex()}")
    max_outputs, extension_mask, nb_extensions, bytes_per_extension = data[:4]
    offset = 4
    extensions = []
    active_addresses = [bit + 1 for bit in range(8) if extension_mask & (1 << bit)]
    for index in range(nb_extensions):
        if offset + bytes_per_extension > len(data):
            raise DudesCabProtocolError("Réponse PWM GetConfig tronquée")
        raw = data[offset : offset + bytes_per_extension]
        offset += bytes_per_extension
        enabled_mask = int.from_bytes(raw, "little")
        address = active_addresses[index] if index < len(active_addresses) else index + 1
        extensions.append(
            {
                "address": address,
                "enabled_mask": enabled_mask,
                "enabled_outputs": [
                    output + 1 for output in range(max_outputs) if enabled_mask & (1 << output)
                ],
            }
        )
    return {
        "max_outputs_per_extension": max_outputs,
        "extension_mask": extension_mask,
        "nb_extensions": nb_extensions,
        "bytes_per_extension": bytes_per_extension,
        "extensions": extensions,
        "raw_hex": data.hex(),
    }


class _Reader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.offset = 0

    def take(self, size: int) -> bytes:
        if size < 0 or self.offset + size > len(self.data):
            raise DudesCabProtocolError("Configuration MX tronquée")
        result = self.data[self.offset : self.offset + size]
        self.offset += size
        return result

    def u8(self) -> int:
        return self.take(1)[0]

    def u16(self) -> int:
        return int.from_bytes(self.take(2), "little")

    def string(self) -> str:
        size = self.u8()
        return self.take(size).decode("utf-8", errors="replace")


def _parse_mx_config(data: bytes) -> dict[str, Any]:
    reader = _Reader(data)
    result: dict[str, Any] = {
        "enabled": bool(reader.u8()),
        "led_chipset": reader.u8(),
        "ledwiz_equivalent": reader.u8(),
        "test_on_reset": reader.u8(),
        "test_on_reset_duration": reader.u8(),
        "test_on_connect": reader.u8(),
        "test_on_connect_duration": reader.u8(),
        "test_brightness": reader.u8(),
        "compression_ratio": reader.u8(),
    }
    strip_count = reader.u8()
    strips = []
    for _ in range(strip_count):
        strip = {
            "name": reader.string(),
            "width": reader.u16(),
            "height": reader.u16(),
            "dof_output_num": reader.u8(),
            "fading_curve": reader.u8(),
            "led_arrangement": reader.u8(),
            "color_order": reader.u8(),
            "brightness": reader.u8(),
        }
        split_count = reader.u8()
        strip["splits"] = [
            {"data_output_num": reader.u8(), "nb_leds": reader.u16()}
            for _ in range(split_count)
        ]
        strips.append(strip)
    result["nb_ledstrips"] = strip_count
    result["ledstrips"] = strips
    result["remaining_bytes"] = len(data) - reader.offset
    result["raw_hex"] = data.hex()
    return result




class _ConfigReader:
    """Strict reader for the Dude's Cab configuration returned by Admin GetConfig."""

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.offset = 0

    @property
    def remaining(self) -> int:
        return len(self.data) - self.offset

    def take(self, size: int, label: str = "donnée") -> bytes:
        if size < 0 or self.offset + size > len(self.data):
            raise DudesCabProtocolError(
                f"Configuration tronquée à {self.offset} pour {label} "
                f"({size} octet(s), {self.remaining} restant(s))"
            )
        out = self.data[self.offset : self.offset + size]
        self.offset += size
        return out

    def u8(self, label: str = "octet") -> int:
        return self.take(1, label)[0]

    def u16(self, label: str = "mot") -> int:
        return int.from_bytes(self.take(2, label), "little")

    def boolean(self, label: str = "booléen") -> bool:
        return bool(self.u8(label))

    def string(self, label: str = "chaîne") -> str:
        size = self.u8(f"taille {label}")
        # The original BufferUtils.ReadString casts every byte directly to char.
        return self.take(size, label).decode("latin-1", errors="replace")

    def pin(self, label: str = "bouton") -> int:
        raw = self.u8(label)
        # BufferUtils.ReadButton : 33 = aucun bouton. Certaines cartes renvoient
        # 0xFF (255) ou un autre octet > 31 pour un bouton non initialise :
        # on traite tout octet > 31 comme "aucun bouton" (0).
        if raw > 31:
            return 0
        return raw + 1

    def color(self, label: str) -> dict[str, Any]:
        red, green, blue = self.take(3, label)
        return {
            "r": red,
            "g": green,
            "b": blue,
            "hex": f"#{red:02x}{green:02x}{blue:02x}",
        }


def _parse_admin_config(data: bytes) -> dict[str, Any]:
    """Parse the exact read buffer used by DudesCabConfig 2.0.11 / Config v11."""

    if not data:
        raise DudesCabProtocolError("GetConfig a retourné une configuration vide")
    if len(data) > 256 * 1024:
        raise DudesCabProtocolError(f"Configuration anormalement grande: {len(data)} octets")

    reader = _ConfigReader(data)
    magic = reader.u8("Magic Zizidur")
    if magic != 111:
        raise DudesCabProtocolError(
            f"Magic Zizidur invalide: {magic}, 111 attendu. Aucun paramètre n'a été appliqué."
        )
    version = reader.u8("version de configuration")
    if not 1 <= version <= 11:
        raise DudesCabProtocolError(
            f"Version de configuration {version} non supportée par le lecteur V3.1 (1..11)"
        )

    general: dict[str, Any] = {
        "name": reader.string("nom de carte"),
        "usb_orientation": reader.u8("orientation USB"),
        "keyboard_layout": reader.u8("type de clavier"),
        "log_level": reader.u8("niveau de log"),
        "default_night_mode": reader.boolean("Night Mode au démarrage"),
        "card_id": reader.u8("ID de carte"),
    }
    general["ledwiz_number"] = 89 + general["card_id"]
    general["cpu_frequency"] = reader.u16("fréquence CPU") if version >= 3 else None
    if version >= 8:
        general["colors"] = {
            "default": reader.color("couleur défaut"),
            "admin": reader.color("couleur admin"),
            "night": reader.color("couleur Night Mode"),
            "calibration": reader.color("couleur calibration"),
        }
    else:
        general["colors"] = None
    general["watchdog_delay"] = reader.u8("délai watchdog") if version >= 11 else None

    inputs: list[dict[str, Any]] = []
    for index in range(1, 33):
        item = {
            "pin": index,
            "default": {
                "type": reader.u8(f"entrée {index} type"),
                "function": reader.u8(f"entrée {index} fonction"),
            },
            "shifted": {
                "type": reader.u8(f"entrée {index} type shifted"),
                "function": reader.u8(f"entrée {index} fonction shifted"),
            },
            "latency": reader.u8(f"entrée {index} latence"),
            "debounce_delay": reader.u8(f"entrée {index} stabilisation") if version >= 2 else 0,
        }
        inputs.append(item)

    input_settings = {
        "items": inputs,
        "shift_button_pin": reader.pin("bouton Shift"),
        "night_mode_button_pin": reader.pin("bouton Night Mode"),
    }

    extension_count = reader.u8("nombre d'extensions Walter")
    if extension_count > 8:
        raise DudesCabProtocolError(f"Nombre d'extensions Walter invalide: {extension_count}")
    extensions: list[dict[str, Any]] = []
    for card_index in range(extension_count):
        address = reader.u8(f"extension {card_index + 1} adresse")
        extension: dict[str, Any] = {
            "index": card_index,
            "address": address,
            "name": reader.string(f"extension {card_index + 1} nom"),
            "pwm_frequency": reader.u16(f"extension {card_index + 1} fréquence PWM") if version >= 4 else None,
            "legacy_card_security_delay": reader.u16(f"extension {card_index + 1} sécurité v5") if version == 5 else None,
            "outputs": [],
        }
        for output_index in range(1, 17):
            flags = None
            output = {
                "number": output_index,
                "dof_number": (max(address, 1) - 1) * 16 + output_index,
                "name": reader.string(f"extension {card_index + 1} sortie {output_index} nom"),
                "preset": reader.u8(f"extension {card_index + 1} sortie {output_index} preset"),
            }
            flags = reader.u8(f"extension {card_index + 1} sortie {output_index} flags")
            output.update(
                {
                    "flags": flags,
                    "enabled": bool(flags & 0x80),
                    "night_mode_affected": bool(flags & 0x01),
                    "analog": bool(flags & 0x02),
                    "digital": not bool(flags & 0x02),
                    "gamma_correct": bool(flags & 0x04),
                    "inverted": bool(flags & 0x08),
                    "max_value": reader.u8(f"extension {card_index + 1} sortie {output_index} max"),
                    "intensity": reader.u8(f"extension {card_index + 1} sortie {output_index} intensité"),
                    "falloff_value": reader.u8(f"extension {card_index + 1} sortie {output_index} atténuation"),
                    "min_active_time": reader.u16(f"extension {card_index + 1} sortie {output_index} activité minimum"),
                    "falloff_delay": reader.u16(f"extension {card_index + 1} sortie {output_index} délai atténuation"),
                    "security_delay": reader.u16(f"extension {card_index + 1} sortie {output_index} délai sécurité") if version >= 6 else 0,
                }
            )
            extension["outputs"].append(output)
        extensions.append(extension)

    accelerometer: dict[str, Any] = {
        "report_delay": reader.u16("accéléromètre intervalle"),
        "reset_delay": reader.u16("accéléromètre recalibrage"),
        "x_sensitivity": reader.u16("accéléromètre sensibilité X"),
        "y_sensitivity": reader.u16("accéléromètre sensibilité Y"),
        "dead_zone": reader.u8("accéléromètre zone morte"),
        "tilt_range": reader.u8("accéléromètre limite Tilt"),
        "tilt_button_pin": reader.pin("accéléromètre bouton Tilt"),
        "precision": reader.u8("accéléromètre précision") if version >= 8 else None,
        "history_buffer": reader.u8("accéléromètre cache") if version >= 9 else None,
        "filter_strength": reader.u8("accéléromètre filtre") if version >= 10 else None,
    }

    plunger: dict[str, Any] = {
        "enabled": reader.boolean("tire-bille activé"),
        "inverted": reader.boolean("tire-bille inversé"),
        "report_delay": reader.u16("tire-bille intervalle"),
        "calibration_button_pin": reader.pin("tire-bille bouton calibration"),
        "calibration_duration": reader.u8("tire-bille durée calibration"),
        "calibrated": reader.boolean("tire-bille calibré"),
        "calibration_pull_max": reader.u16("tire-bille maximum tiré"),
        "calibration_still": reader.u16("tire-bille repos"),
        "calibration_push_max": reader.u16("tire-bille maximum poussé"),
        "jitter_window": reader.u16("tire-bille anti-tremblement"),
        "pull_button_pin": reader.pin("tire-bille bouton tiré"),
        "push_button_pin": reader.pin("tire-bille bouton poussé"),
        "physical_range_min": reader.u16("tire-bille plage physique minimum"),
        "physical_range_max": reader.u16("tire-bille plage physique maximum"),
    }

    mx: dict[str, Any] | None = None
    if version >= 2:
        mx = {
            "enabled": reader.boolean("MX activé"),
            "led_chipset": reader.u8("MX modèle de LED"),
            "ledwiz_equivalent": reader.u8("MX équivalent LedWiz"),
            "test_on_reset": reader.u8("MX test au reset"),
            "test_on_reset_duration": reader.u8("MX durée test au reset"),
            "test_on_connect": reader.u8("MX test à la connexion"),
            "test_on_connect_duration": reader.u8("MX durée test à la connexion"),
            "test_brightness": reader.u8("MX luminosité test"),
            "compression_ratio": reader.u8("MX compression") if version >= 7 else None,
            "ledstrips": [],
        }
        ledstrip_count = reader.u8("MX nombre de LED strips")
        if ledstrip_count > 128:
            raise DudesCabProtocolError(f"Nombre de LED strips MX invalide: {ledstrip_count}")
        for strip_index in range(ledstrip_count):
            strip = {
                "index": strip_index,
                "name": reader.string(f"MX strip {strip_index + 1} nom"),
                "width": reader.u16(f"MX strip {strip_index + 1} largeur"),
                "height": reader.u16(f"MX strip {strip_index + 1} hauteur"),
                "dof_output_num": reader.u8(f"MX strip {strip_index + 1} sortie DOF"),
                "fading_curve": reader.u8(f"MX strip {strip_index + 1} courbe"),
                "led_arrangement": reader.u8(f"MX strip {strip_index + 1} arrangement"),
                "color_order": reader.u8(f"MX strip {strip_index + 1} ordre couleur"),
                "brightness": reader.u8(f"MX strip {strip_index + 1} luminosité"),
                "splits": [],
            }
            split_count = reader.u8(f"MX strip {strip_index + 1} nombre de splits")
            if split_count > 8:
                raise DudesCabProtocolError(
                    f"Nombre de splits MX invalide pour {strip['name']!r}: {split_count}"
                )
            for split_index in range(split_count):
                strip["splits"].append(
                    {
                        "data_output_num": reader.u8(
                            f"MX strip {strip_index + 1} split {split_index + 1} ligne"
                        ),
                        "nb_leds": reader.u16(
                            f"MX strip {strip_index + 1} split {split_index + 1} LEDs"
                        ),
                    }
                )
            mx["ledstrips"].append(strip)
        mx["nb_ledstrips"] = ledstrip_count

    trailing = reader.take(reader.remaining, "octets supplémentaires") if reader.remaining else b""
    return {
        "magic": magic,
        "raw_hex": data.hex(),
        "version": version,
        "general": general,
        "inputs": input_settings,
        "extensions": extensions,
        "accelerometer": accelerometer,
        "plunger": plunger,
        "mx": mx,
        "raw_size": len(data),
        "parsed_size": reader.offset - len(trailing),
        "remaining_bytes": len(trailing),
        "remaining_hex": trailing.hex(),
        "raw_sha256": __import__("hashlib").sha256(data).hexdigest(),
    }


class _ConfigWriter:
    """Serialiseur miroir de _ConfigReader : reconstruit le buffer Admin
    SetConfig (code 101) octet-pour-octet, avec les memes encodages que le
    configurateur .NET d'Arnoz (WriteShort=u16 LE, WriteColor=RGB, WriteButton,
    WriteString=1 octet longueur + donnees)."""

    def __init__(self) -> None:
        self.buf = bytearray()

    def u8(self, value: Any) -> None:
        self.buf.append(int(value or 0) & 0xFF)

    def u16(self, value: Any) -> None:
        self.buf += (int(value or 0) & 0xFFFF).to_bytes(2, "little")

    def boolean(self, value: Any) -> None:
        self.u8(1 if value else 0)

    def string(self, value: Any) -> None:
        raw = (value or "").encode("latin-1", errors="replace")
        if len(raw) > 255:
            raise DudesCabProtocolError(f"Chaine trop longue ({len(raw)} > 255)")
        self.u8(len(raw))
        self.buf += raw

    def pin(self, value: Any) -> None:
        # Boutons Shift/NightMode (WriteButton) : 0/None -> 33 ; 1..32 -> valeur-1
        pin = int(value or 0)
        if pin <= 0:
            self.u8(33)
            return
        if pin > 32:
            raise DudesCabProtocolError(f"Bouton invalide: {pin}")
        self.u8(pin - 1)

    def pin_raw(self, value: Any) -> None:
        # Pins plunger/accelerometre (octet brut) : 0/None -> 255 (0xFF) ; 1..32 -> valeur-1
        pin = int(value or 0)
        if pin <= 0:
            self.u8(255)
            return
        if pin > 32:
            raise DudesCabProtocolError(f"Bouton invalide: {pin}")
        self.u8(pin - 1)

    def color(self, value: dict[str, Any]) -> None:
        value = value or {}
        self.u8(value.get("r", 0))
        self.u8(value.get("g", 0))
        self.u8(value.get("b", 0))


def _build_admin_config(config: dict[str, Any]) -> bytes:
    """Inverse exact de _parse_admin_config : structure -> buffer Admin SetConfig.

    Attend une structure au meme format que celle renvoyee par _parse_admin_config
    (lire -> modifier -> reecrire). Respecte le gating par version de config.
    """
    version = int(config.get("version") or 0)
    if not 1 <= version <= 11:
        raise DudesCabProtocolError(
            f"Version de configuration {version} non supportee (1..11)"
        )

    w = _ConfigWriter()
    w.u8(111)  # Magic Zizidur
    w.u8(version)

    general = config.get("general") or {}
    w.string(general.get("name"))
    w.u8(general.get("usb_orientation"))
    w.u8(general.get("keyboard_layout"))
    w.u8(general.get("log_level"))
    w.boolean(general.get("default_night_mode"))
    w.u8(general.get("card_id"))
    if version >= 3:
        w.u16(general.get("cpu_frequency"))
    if version >= 8:
        colors = general.get("colors") or {}
        for key in ("default", "admin", "night", "calibration"):
            w.color(colors.get(key) or {})
    if version >= 11:
        w.u8(general.get("watchdog_delay"))

    inputs = config.get("inputs") or {}
    items = inputs.get("items") or []
    if len(items) != 32:
        raise DudesCabProtocolError(
            f"32 entrees attendues, {len(items)} recues"
        )
    for item in items:
        default = item.get("default") or {}
        shifted = item.get("shifted") or {}
        w.u8(default.get("type"))
        w.u8(default.get("function"))
        w.u8(shifted.get("type"))
        w.u8(shifted.get("function"))
        w.u8(item.get("latency"))
        if version >= 2:
            w.u8(item.get("debounce_delay"))
    w.pin(inputs.get("shift_button_pin"))
    w.pin(inputs.get("night_mode_button_pin"))

    extensions = config.get("extensions") or []
    if len(extensions) > 8:
        raise DudesCabProtocolError("Trop d'extensions Walter (max 8)")
    w.u8(len(extensions))
    for ext in extensions:
        w.u8(ext.get("address"))
        w.string(ext.get("name"))
        if version >= 4:
            w.u16(ext.get("pwm_frequency"))
        if version == 5:
            w.u16(ext.get("legacy_card_security_delay"))
        outputs = ext.get("outputs") or []
        if len(outputs) != 16:
            raise DudesCabProtocolError(
                f"16 sorties attendues par extension, {len(outputs)} recues"
            )
        for out in outputs:
            w.string(out.get("name"))
            w.u8(out.get("preset"))
            w.u8(out.get("flags"))
            w.u8(out.get("max_value"))
            w.u8(out.get("intensity"))
            w.u8(out.get("falloff_value"))
            w.u16(out.get("min_active_time"))
            w.u16(out.get("falloff_delay"))
            if version >= 6:
                w.u16(out.get("security_delay"))

    accel = config.get("accelerometer") or {}
    w.u16(accel.get("report_delay"))
    w.u16(accel.get("reset_delay"))
    w.u16(accel.get("x_sensitivity"))
    w.u16(accel.get("y_sensitivity"))
    w.u8(accel.get("dead_zone"))
    w.u8(accel.get("tilt_range"))
    w.pin_raw(accel.get("tilt_button_pin"))
    if version >= 8:
        w.u8(accel.get("precision"))
    if version >= 9:
        w.u8(accel.get("history_buffer"))
    if version >= 10:
        w.u8(accel.get("filter_strength"))

    plunger = config.get("plunger") or {}
    w.boolean(plunger.get("enabled"))
    w.boolean(plunger.get("inverted"))
    w.u16(plunger.get("report_delay"))
    w.pin_raw(plunger.get("calibration_button_pin"))
    w.u8(plunger.get("calibration_duration"))
    w.boolean(plunger.get("calibrated"))
    w.u16(plunger.get("calibration_pull_max"))
    w.u16(plunger.get("calibration_still"))
    w.u16(plunger.get("calibration_push_max"))
    w.u16(plunger.get("jitter_window"))
    w.pin_raw(plunger.get("pull_button_pin"))
    w.pin_raw(plunger.get("push_button_pin"))
    w.u16(plunger.get("physical_range_min"))
    w.u16(plunger.get("physical_range_max"))

    if version >= 2:
        mx = config.get("mx") or {}
        w.boolean(mx.get("enabled"))
        w.u8(mx.get("led_chipset"))
        w.u8(mx.get("ledwiz_equivalent"))
        w.u8(mx.get("test_on_reset"))
        w.u8(mx.get("test_on_reset_duration"))
        w.u8(mx.get("test_on_connect"))
        w.u8(mx.get("test_on_connect_duration"))
        w.u8(mx.get("test_brightness"))
        if version >= 7:
            w.u8(mx.get("compression_ratio"))
        strips = mx.get("ledstrips") or []
        if len(strips) > 128:
            raise DudesCabProtocolError("Trop de LED strips MX (max 128)")
        w.u8(len(strips))
        for strip in strips:
            w.string(strip.get("name"))
            w.u16(strip.get("width"))
            w.u16(strip.get("height"))
            w.u8(strip.get("dof_output_num"))
            w.u8(strip.get("fading_curve"))
            w.u8(strip.get("led_arrangement"))
            w.u8(strip.get("color_order"))
            w.u8(strip.get("brightness"))
            splits = strip.get("splits") or []
            if len(splits) > 8:
                raise DudesCabProtocolError("Trop de splits MX (max 8)")
            w.u8(len(splits))
            for split in splits:
                w.u8(split.get("data_output_num"))
                w.u16(split.get("nb_leds"))

    return bytes(w.buf)


def _verify_config_roundtrip() -> dict[str, Any]:
    """Auto-test SANS ECRITURE : lit la config (GetConfig 100), la re-serialise
    et compare octet-pour-octet au buffer brut de la carte. Prouve l'exactitude
    du serialiseur avant toute ecriture reelle."""
    config = _read_admin_config()
    raw = bytes.fromhex(config["raw_hex"]) if config.get("raw_hex") else b""
    rebuilt = _build_admin_config(config)
    # Le buffer carte peut avoir des octets de padding en fin ; on compare le prefixe utile.
    match = raw[: len(rebuilt)] == rebuilt
    return {
        "match": bool(match),
        "raw_size": len(raw),
        "rebuilt_size": len(rebuilt),
        "first_diff": next((i for i in range(min(len(raw), len(rebuilt))) if raw[i] != rebuilt[i]), None),
        "rebuilt_sha256": __import__("hashlib").sha256(rebuilt).hexdigest(),
    }


# Champs rapportes par GetConfig mais GERES PAR LE FIRMWARE : SetConfig les ignore
# (declencheurs de test MX). Les exclure de la verification post-ecriture, sinon
# faux positif a chaque ecriture. Confirme experimentalement (cab reel, fw 2.0.6).
_DEVICE_MANAGED_FIELDS = {
    "mx.test_on_reset",
    "mx.test_on_reset_duration",
    "mx.test_on_connect",
    "mx.test_on_connect_duration",
}
# Sections REELLES de la config carte : on ne compare QUE celles-ci. Tout le
# reste (parsed_size, raw_size, raw_hex, raw_sha256, firmware, version_match,
# announced_config_version...) est du meta ajoute par la lecture -> ignore.
_CONFIG_SECTIONS = {
    "version", "general", "inputs", "extensions",
    "accelerometer", "plunger", "mx",
}


def _flatten_config(value: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(value, dict):
        for k, v in value.items():
            out.update(_flatten_config(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            out.update(_flatten_config(v, f"{prefix}[{i}]"))
    else:
        out[prefix] = value
    return out


def _config_write_diff(intended: dict[str, Any], readback: dict[str, Any]) -> dict[str, Any]:
    """Champs qui different entre la config voulue et la config relue apres
    SetConfig, hors champs meta et champs geres par le firmware."""
    fa = _flatten_config(intended)
    fb = _flatten_config(readback)
    diffs: dict[str, Any] = {}
    for key in set(fa) | set(fb):
        top = key.split(".", 1)[0].split("[", 1)[0]
        if top not in _CONFIG_SECTIONS:
            continue  # champ meta (tailles, hash, firmware...) -> non compare
        base = key.split("[", 1)[0]
        if base in _DEVICE_MANAGED_FIELDS:
            continue  # champ gere par le firmware (test MX) -> non inscriptible
        if fa.get(key) != fb.get(key):
            diffs[key] = {"intended": fa.get(key), "device": fb.get(key)}
    return diffs


def _write_admin_config(config: dict[str, Any], save: bool = True, verify: bool = True) -> dict[str, Any]:
    """Ecrit la config : SetConfig (101), VERIFICATION SEMANTIQUE post-ecriture
    (relit GetConfig 100, compare champ par champ), puis SaveToFlash (114) SEULEMENT
    si tout a bien ete applique.

    La carte n'accuse pas reception de SetConfig. Sans verification, une config
    partiellement rejetee (ex. mapping non applique sur un firmware different)
    passe pour un succes. On compare donc la config voulue a la config relue, en
    excluant les champs meta et les champs geres par le firmware (declencheurs de
    test MX, non inscriptibles). En cas d'ecart REEL, on ne sauvegarde pas en
    flash et on liste les champs fautifs."""
    with _state_lock:
        admin = _admin_enabled
    if not admin:
        raise DudesCabProtocolError(
            "Mode admin inactif : appelle /protocol/connect avant d'ecrire."
        )
    buffer = _build_admin_config(config)
    result: dict[str, Any] = {"sent_bytes": len(buffer), "saved": False, "verified": None, "diff": {}}
    with _operation_lock:
        hid_command(REPORT_ADMIN, 101, buffer, expect_response=False)
        if verify:
            raw = hid_command(
                REPORT_ADMIN, 100, bytes((1,)), expect_response=True, timeout_ms=12000
            )
            readback = _parse_admin_config(raw)
            diffs = _config_write_diff(config, readback)
            result["verified"] = not diffs
            result["diff"] = diffs
            if diffs:
                sample = ", ".join(
                    f"{k} (voulu={d['intended']}, carte={d['device']})"
                    for k, d in list(diffs.items())[:6]
                )
                more = " ..." if len(diffs) > 6 else ""
                raise DudesCabProtocolError(
                    "La carte n'a pas applique certains champs (rien sauvegarde en "
                    f"flash) : {sample}{more}. Cause possible : version de "
                    "config/firmware differente, ou champ non inscriptible."
                )
        if save:
            hid_command(REPORT_ADMIN, 114, expect_response=False)
            result["saved"] = True
    return result



def _read_admin_config() -> dict[str, Any]:
    # Keep Version + GetConfig as one exclusive transaction. The original
    # configurator sends one request byte (0x01) with Admin GetConfig (100).
    with _operation_lock:
        with _state_lock:
            admin = _admin_enabled
        if not admin:
            raise DudesCabProtocolError(
                "Connecte d'abord la Dude's Cab en mode administrateur avant Lire Config."
            )
        version = _version()
        if not _is_new_firmware(version):
            raise DudesCabProtocolError(
                "Lire Config V3.1.2 est limité au firmware 2.0 ou plus récent."
            )
        raw = hid_command(
            REPORT_ADMIN,
            100,
            bytes((1,)),
            expect_response=True,
            timeout_ms=12000,
        )
        config = _parse_admin_config(raw)
        config["firmware"] = version
        announced = version.get("config_version")
        config["announced_config_version"] = announced
        config["version_match"] = announced is None or int(announced) == int(config["version"])
        return config

def _version() -> dict[str, Any]:
    return _parse_version(
        hid_command(REPORT_ADMIN, 3, expect_response=True, timeout_ms=1400)
    )


def _is_new_firmware(version: dict[str, Any]) -> bool:
    return int(version.get("major", 0)) >= 2


def _pwm_command_numbers(version: dict[str, Any]) -> tuple[int, int, int]:
    return (100, 101, 102) if _is_new_firmware(version) else (3, 4, 5)


def _probe_inner() -> dict[str, Any]:
    global _last_probe
    result: dict[str, Any] = {
        "timestamp": time.time(),
        "marker": MARKER,
        "hid_nodes": hid_nodes(),
        "capabilities": {
            "admin_config_read": True,
            "admin_config_write": True,
            "flash_memory_commands": False,
            "firmware": False,
            "common": True,
            "pwm_outputs": True,
            "mx_outputs": True,
            "serial_logs": True,
        },
    }
    errors: list[str] = []

    try:
        result["handshake"] = _ascii(
            hid_command(REPORT_ADMIN, 1, expect_response=True, timeout_ms=1500)
        )
    except Exception as exc:
        errors.append(f"Handshake Admin: {exc}")

    version: dict[str, Any] | None = None
    try:
        version = _version()
        result["version"] = version
    except Exception as exc:
        errors.append(f"Version: {exc}")

    # SAFE V3.1.5:
    # Do not send Common GetStatus (Admin ReportID 4, command 4) from the web
    # bridge. On this Linux raw-hid implementation that command answers
    # intermittently and can leave the board in a warning/error state, whereas
    # Handshake, GetVersion and Admin GetConfig are stable and fully validated.
    result["status"] = {
        "supported": False,
        "safe_mode": True,
        "command_disabled": 4,
        "reason": "Statut HID désactivé en mode Web SAFE",
    }

    if version:
        try:
            get_config, _, _ = _pwm_command_numbers(version)
            result["pwm"] = _parse_pwm_config(
                hid_command(REPORT_OUTPUTS, get_config, expect_response=True, timeout_ms=1600)
            )
        except Exception as exc:
            errors.append(f"PWM GetConfig: {exc}")

    if any(REPORT_MX in row["report_ids"] for row in result["hid_nodes"]):
        mx: dict[str, Any] = {"present": True}
        try:
            mx["handshake"] = _ascii(
                hid_command(REPORT_MX, 100, expect_response=True, timeout_ms=1500)
            )
        except Exception as exc:
            errors.append(f"MX Handshake: {exc}")
        try:
            raw = hid_command(REPORT_MX, 101, expect_response=True, timeout_ms=1500)
            if len(raw) < 6:
                raise DudesCabProtocolError(f"UMX GetInfos trop court: {raw.hex()}")
            mx["infos"] = {
                "version": f"{raw[0]}.{raw[1]}.{raw[2]}",
                "major": raw[0],
                "minor": raw[1],
                "revision": raw[2],
                "max_output_lines": raw[3],
                "max_supported_leds": int.from_bytes(raw[4:6], "little"),
                "raw_hex": raw.hex(),
            }
        except Exception as exc:
            errors.append(f"MX Infos: {exc}")
        try:
            mx["config"] = _parse_mx_config(
                hid_command(REPORT_MX, 102, expect_response=True, timeout_ms=2200)
            )
        except Exception as exc:
            errors.append(f"MX Config: {exc}")
        result["mx"] = mx
    else:
        result["mx"] = {"present": False}

    result["ok"] = "version" in result
    result["errors"] = errors
    with _state_lock:
        _last_probe = result
    return result


def _probe() -> dict[str, Any]:
    # Prevent status/live polling from interleaving with a multipart probe.
    with _operation_lock:
        return _probe_inner()


def _vpx_processes() -> list[str]:
    try:
        proc = subprocess.run(
            ["/usr/bin/pgrep", "-af", r"VPinballX|/opt/pincabos/bin/vpx\.sh"],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
    except Exception:
        return []
    if proc.returncode not in (0, 1):
        return []
    current = os.getpid()
    rows = []
    for line in proc.stdout.splitlines():
        try:
            pid = int(line.split(maxsplit=1)[0])
        except Exception:
            pid = -1
        if pid != current and line.strip():
            rows.append(line.strip())
    return rows


def _require_idle() -> None:
    processes = _vpx_processes()
    if processes:
        raise DudesCabProtocolError(
            "VPX est en cours d'exécution; commande physique refusée. " + " | ".join(processes[:3])
        )


def _send_admin(enabled: bool) -> dict[str, Any]:
    """Enable or disable Admin mode without probing after it is disabled.

    The original V3.1.2 performed a complete probe immediately after SetAdmin(0).
    The card can reject subsequent Admin reads once Admin mode is off and retain
    error 22.  Connecting still performs the complete documented probe; a
    disconnect returns the last safe probe with Admin cleared locally.
    """
    global _admin_enabled
    with _operation_lock:
        hid_command(REPORT_ADMIN, 2, bytes((1 if enabled else 0,)), expect_response=False)
        time.sleep(0.12)
        with _state_lock:
            _admin_enabled = enabled

        if enabled:
            probe = _probe()
        else:
            with _state_lock:
                probe = json.loads(json.dumps(_last_probe)) if _last_probe else {}
            status = probe.get("status")
            if isinstance(status, dict):
                status["admin_mode"] = False
                flags = int(status.get("flags", 0))
                status["flags"] = flags & ~0x02

        probe["admin_requested"] = enabled
        return probe


def _cancel_timer(extension: int, output: int) -> None:
    with _state_lock:
        timer = _output_timers.pop((extension, output), None)
    if timer:
        timer.cancel()


def _send_pwm_value(extension: int, output: int, value: int) -> None:
    version = _version()
    _, _, send_outputs = _pwm_command_numbers(version)
    extension_mask = 1 << (extension - 1)
    output_mask = 1 << (output - 1)
    payload = bytes((extension_mask,)) + struct.pack("<H", output_mask) + bytes((value,))
    hid_command(REPORT_OUTPUTS, send_outputs, payload, expect_response=False)


def _safe_output_off(extension: int, output: int) -> None:
    try:
        _send_pwm_value(extension, output, 0)
    except Exception:
        pass
    finally:
        _cancel_timer(extension, output)


def _all_off() -> dict[str, Any]:
    version = _version()
    _, all_off, _ = _pwm_command_numbers(version)
    with _state_lock:
        timers = list(_output_timers.values())
        _output_timers.clear()
    for timer in timers:
        timer.cancel()
    hid_command(REPORT_OUTPUTS, all_off, expect_response=False)
    return {"version": version["text"], "all_off": True}


def _test_output(extension: int, output: int, value: int, duration_ms: int) -> dict[str, Any]:
    _require_idle()
    if not 1 <= extension <= 8:
        raise ValueError("Extension hors plage 1..8")
    if not 1 <= output <= 16:
        raise ValueError("Sortie hors plage 1..16")
    if not 0 <= value <= 255:
        raise ValueError("Valeur PWM hors plage 0..255")
    if not 10 <= duration_ms <= 15000:
        raise ValueError("Durée hors plage 10..15000 ms")

    version = _version()
    get_config, _, _ = _pwm_command_numbers(version)
    config = _parse_pwm_config(
        hid_command(REPORT_OUTPUTS, get_config, expect_response=True, timeout_ms=1600)
    )
    ext = next((item for item in config["extensions"] if item["address"] == extension), None)
    if not ext:
        raise DudesCabProtocolError(f"Extension Walter {extension} non configurée")
    if output not in ext["enabled_outputs"]:
        raise DudesCabProtocolError(f"Sortie {output} désactivée sur l'extension {extension}")

    _cancel_timer(extension, output)
    _send_pwm_value(extension, output, value)
    timer = threading.Timer(duration_ms / 1000.0, _safe_output_off, args=(extension, output))
    timer.daemon = True
    with _state_lock:
        _output_timers[(extension, output)] = timer
    timer.start()
    return {
        "extension": extension,
        "output": output,
        "value": value,
        "auto_off_ms": duration_ms,
        "config": config,
    }


def _serial_path() -> Path | None:
    candidates = [Path("/dev/dudescab")]
    by_id = Path("/dev/serial/by-id")
    if by_id.exists():
        candidates.extend(sorted(by_id.glob("*DudesCab*")))
    candidates.extend(sorted(Path("/dev").glob("ttyACM*")))
    for path in candidates:
        if path.exists() and os.access(path, os.R_OK):
            return path
    return None


def _read_serial() -> list[str]:
    global _serial_partial
    path = _serial_path()
    if not path:
        raise DudesCabProtocolError("Port série DudesCab introuvable")
    chunks = bytearray()
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOCTTY)
    try:
        for _ in range(64):
            try:
                data = os.read(fd, 4096)
            except OSError as exc:
                if exc.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                    break
                raise
            if not data:
                break
            chunks.extend(data)
            if len(chunks) >= 65536:
                break
    finally:
        os.close(fd)
    if chunks:
        text = _serial_partial + chunks.decode("utf-8", errors="replace")
        pieces = text.splitlines(keepends=True)
        _serial_partial = ""
        if pieces and not pieces[-1].endswith(("\n", "\r")):
            _serial_partial = pieces.pop()
        for line in pieces:
            clean = line.rstrip("\r\n")
            if clean:
                _serial_lines.append(clean)
    return list(_serial_lines)


def _json_body() -> dict[str, Any]:
    return request.get_json(silent=True) or {}


def _maintenance_token() -> str:
    token = str(_json_body().get("token", "")).strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", token):
        raise ValueError("Jeton de maintenance invalide")
    return token


def _maintenance_call(action: str, token: str = "", timeout: int = 30) -> dict[str, Any]:
    cmd = ["/usr/bin/sudo", "-n", MAINTENANCE_HELPER, action, "--timeout", str(MAINTENANCE_TIMEOUT)]
    if token:
        cmd.extend(["--token", token])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise DudesCabProtocolError(f"Mode maintenance trop long: {exc}") from exc
    raw = (result.stdout or result.stderr or "").strip()
    try:
        payload = json.loads(raw.splitlines()[-1] if raw else "{}")
    except Exception as exc:
        raise DudesCabProtocolError(f"Réponse maintenance illisible: {raw[-500:]}") from exc
    if result.returncode != 0 or payload.get("ok") is False:
        raise DudesCabProtocolError(str(payload.get("error") or raw or "Échec maintenance"))
    return payload


def _maintenance_public(payload: dict[str, Any]) -> dict[str, Any]:
    public = dict(payload)
    public.pop("token", None)
    return public


def _require_maintenance() -> dict[str, Any]:
    status = _maintenance_call("status", timeout=8)
    supplied = str(request.headers.get("X-DudesCab-Maintenance", "")).strip()
    if not status.get("active"):
        raise DudesCabProtocolError("Mode maintenance DudesCabConfig inactif. Recharge la page.")
    if not supplied or supplied != str(status.get("token") or ""):
        raise DudesCabProtocolError("Cette page ne possède pas la session maintenance active.")
    if status.get("vpinfe_active_now") or status.get("vpx_processes_now"):
        raise DudesCabProtocolError("VPinFE ou VPX est encore actif; commande DudesCab refusée.")
    return status


def _error_response(exc: Exception, status: int = 400):
    return jsonify({"ok": False, "error": str(exc), "type": type(exc).__name__}), status


def register(app) -> None:
    """Register documented DudesCab protocol endpoints once."""

    if "pincabos_dudescab_protocol_status_v3" in app.view_functions:
        return

    @app.get("/api/dudescabconfig/protocol/status")
    def pincabos_dudescab_protocol_status_v3():
        with _state_lock:
            cached = dict(_last_probe)
            admin = _admin_enabled
        try:
            maintenance = _maintenance_public(_maintenance_call("status", timeout=8))
        except Exception as exc:
            maintenance = {"ok": False, "active": False, "error": str(exc)}
        return jsonify(
            {
                "ok": True,
                "marker": MARKER,
                "maintenance": maintenance,
                "hid_nodes": hid_nodes(),
                "admin_enabled": admin,
                "last_probe": cached,
                "vpx_running": bool(_vpx_processes()),
                "vpx_processes": _vpx_processes(),
                "serial": str(_serial_path() or ""),
                "capabilities": {
                    "handshake": True,
                    "version": True,
                    "status": False,
                    "admin_mode": True,
                    "status_command_disabled": 4,
                    "reset": True,
                    "watchdog": True,
                    "pwm_get_config": True,
                    "pwm_test": True,
                    "pwm_all_off": True,
                    "mx_info": True,
                    "mx_get_config": True,
                    "mx_test": True,
                    "serial_logs": True,
                    "admin_config_read": True,
                    "admin_config_write": True,
                    "flash_memory": False,
                    "firmware": False,
                    "background_hid_polling": False,
                    "safe_manual_mode": True,
                    "maintenance_mode": True,
                    "auto_stop_vpinfe_vpx": True,
                    "maintenance_persistent": True,
                    "maintenance_auto_expiry": False,
                },
            }
        )

    @app.get("/api/dudescabconfig/maintenance/status")
    def pincabos_dudescab_maintenance_status_v320():
        try:
            return jsonify(_maintenance_public(_maintenance_call("status", timeout=8)))
        except Exception as exc:
            return _error_response(exc, 503)

    @app.post("/api/dudescabconfig/maintenance/enter")
    def pincabos_dudescab_maintenance_enter_v320():
        try:
            return jsonify(_maintenance_public(_maintenance_call("enter", _maintenance_token(), timeout=35)))
        except Exception as exc:
            app.logger.exception("DudesCab maintenance enter failed")
            return _error_response(exc, 409)

    @app.post("/api/dudescabconfig/maintenance/heartbeat")
    def pincabos_dudescab_maintenance_heartbeat_v320():
        try:
            return jsonify(_maintenance_public(_maintenance_call("heartbeat", _maintenance_token(), timeout=25)))
        except Exception as exc:
            return _error_response(exc, 409)

    @app.post("/api/dudescabconfig/maintenance/exit")
    def pincabos_dudescab_maintenance_exit_v320():
        global _admin_enabled
        try:
            token = _maintenance_token()
            try:
                if _admin_enabled:
                    _send_admin(False)
            except Exception:
                app.logger.exception("DudesCab Admin disconnect during maintenance exit failed")
            with _state_lock:
                _admin_enabled = False
            return jsonify(_maintenance_public(_maintenance_call("exit", token, timeout=35)))
        except Exception as exc:
            app.logger.exception("DudesCab maintenance exit failed")
            return _error_response(exc, 409)

    @app.post("/api/dudescabconfig/maintenance/recover")
    def pincabos_dudescab_maintenance_recover_v320():
        try:
            body = _json_body()
            if body.get("confirmation") != "RESTORE VPINFE":
                raise ValueError("Confirmation RESTORE VPINFE requise")
            return jsonify(_maintenance_public(_maintenance_call("recover", timeout=35)))
        except Exception as exc:
            return _error_response(exc, 400)

    @app.post("/api/dudescabconfig/protocol/connect")
    def pincabos_dudescab_protocol_connect_v3():
        try:
            _require_maintenance()
            probe = _send_admin(True)
            return jsonify({"ok": True, "probe": probe})
        except Exception as exc:
            app.logger.exception("DudesCab protocol connect failed")
            return _error_response(exc)

    @app.post("/api/dudescabconfig/protocol/disconnect")
    def pincabos_dudescab_protocol_disconnect_v3():
        try:
            probe = _send_admin(False)
            return jsonify({"ok": True, "probe": probe})
        except Exception as exc:
            app.logger.exception("DudesCab protocol disconnect failed")
            return _error_response(exc)

    @app.get("/api/dudescabconfig/protocol/probe")
    def pincabos_dudescab_protocol_probe_v3():
        try:
            _require_maintenance()
            return jsonify({"ok": True, "probe": _probe()})
        except Exception as exc:
            app.logger.exception("DudesCab protocol probe failed")
            return _error_response(exc)

    @app.get("/api/dudescabconfig/protocol/config")
    def pincabos_dudescab_protocol_config_read_v31():
        try:
            _require_maintenance()
            config = _read_admin_config()
            return jsonify({"ok": True, "config": config})
        except Exception as exc:
            app.logger.exception("DudesCab Admin GetConfig failed")
            return _error_response(exc)

    @app.get("/api/dudescabconfig/protocol/config/verify")
    def pincabos_dudescab_protocol_config_verify_v3():
        try:
            _require_maintenance()
            return jsonify({"ok": True, "verify": _verify_config_roundtrip()})
        except Exception as exc:
            app.logger.exception("DudesCab config verify failed")
            return _error_response(exc)

    @app.post("/api/dudescabconfig/protocol/config/write")
    def pincabos_dudescab_protocol_config_write_v3():
        try:
            _require_maintenance()
            body = _json_body()
            config = body.get("config")
            if not isinstance(config, dict):
                raise ValueError("Champ 'config' (objet) requis.")
            if body.get("dry_run"):
                buf = _build_admin_config(config)
                return jsonify({"ok": True, "dry_run": True, "bytes": len(buf), "hex": buf.hex()})
            result = _write_admin_config(
                config,
                save=bool(body.get("save", True)),
                verify=bool(body.get("verify", True)),
            )
            return jsonify({"ok": True, **result})
        except Exception as exc:
            app.logger.exception("DudesCab config write failed")
            return _error_response(exc)

    @app.post("/api/dudescabconfig/protocol/plunger/calibrate")
    def pincabos_dudescab_protocol_plunger_calibrate_v3():
        try:
            _require_maintenance()
            with _state_lock:
                admin = _admin_enabled
            if not admin:
                raise DudesCabProtocolError("Mode admin inactif : /protocol/connect d'abord.")
            hid_command(REPORT_ADMIN, 110, expect_response=False)
            return jsonify({"ok": True, "command": 110, "detail": "Calibration du plunger declenchee"})
        except Exception as exc:
            app.logger.exception("DudesCab plunger calibrate failed")
            return _error_response(exc)

    @app.post("/api/dudescabconfig/protocol/inputs/force")
    def pincabos_dudescab_protocol_inputs_force_v3():
        try:
            _require_maintenance()
            with _state_lock:
                admin = _admin_enabled
            if not admin:
                raise DudesCabProtocolError("Mode admin inactif : /protocol/connect d'abord.")
            payload = bytes.fromhex(str((_json_body() or {}).get("payload_hex", "")))
            hid_command(REPORT_ADMIN, 107, payload, expect_response=False)
            return jsonify({"ok": True, "command": 107, "sent_bytes": len(payload)})
        except Exception as exc:
            app.logger.exception("DudesCab force inputs failed")
            return _error_response(exc)

    @app.post("/api/dudescabconfig/protocol/flash/read")
    def pincabos_dudescab_protocol_flash_read_v3():
        try:
            _require_maintenance()
            with _state_lock:
                admin = _admin_enabled
            if not admin:
                raise DudesCabProtocolError("Mode admin inactif : /protocol/connect d'abord.")
            payload = bytes.fromhex(str((_json_body() or {}).get("payload_hex", "")))
            resp = hid_command(REPORT_ADMIN, 105, payload, expect_response=True, timeout_ms=8000)
            return jsonify({"ok": True, "command": 105, "response_hex": resp.hex(), "size": len(resp)})
        except Exception as exc:
            app.logger.exception("DudesCab flash read failed")
            return _error_response(exc)

    @app.post("/api/dudescabconfig/protocol/flash/write")
    def pincabos_dudescab_protocol_flash_write_v3():
        try:
            _require_maintenance()
            with _state_lock:
                admin = _admin_enabled
            if not admin:
                raise DudesCabProtocolError("Mode admin inactif : /protocol/connect d'abord.")
            body = _json_body() or {}
            if not body.get("confirmed"):
                raise ValueError("Confirmation requise (confirmed:true) : ecriture flash brute.")
            data = bytes.fromhex(str(body.get("data_hex", "")))
            if not data:
                raise ValueError("data_hex requis.")
            hid_command(REPORT_ADMIN, 106, data, expect_response=False)
            return jsonify({"ok": True, "command": 106, "written": len(data)})
        except Exception as exc:
            app.logger.exception("DudesCab flash write failed")
            return _error_response(exc)

    @app.post("/api/dudescabconfig/protocol/flash/reset")
    def pincabos_dudescab_protocol_flash_reset_v3():
        try:
            _require_maintenance()
            with _state_lock:
                admin = _admin_enabled
            if not admin:
                raise DudesCabProtocolError("Mode admin inactif : /protocol/connect d'abord.")
            if not (_json_body() or {}).get("confirmed"):
                raise ValueError("Confirmation requise (confirmed:true) : reset de la memoire flash.")
            hid_command(REPORT_ADMIN, 104, expect_response=False)
            return jsonify({"ok": True, "command": 104})
        except Exception as exc:
            app.logger.exception("DudesCab flash reset failed")
            return _error_response(exc)

    @app.get("/api/dudescabconfig/protocol/live")
    def pincabos_dudescab_protocol_live_v3():
        """SAFE V3.1.4: never touch HID from background browser polling.

        Old cached JavaScript tabs may continue calling this route every few
        seconds. Returning only the last documented probe guarantees that those
        tabs cannot generate USB traffic or firmware communication errors.
        """
        with _state_lock:
            cached = json.loads(json.dumps(_last_probe)) if _last_probe else {}
            admin = _admin_enabled
        live: dict[str, Any] = {
            "cached": True,
            "admin_enabled": admin,
            "safe_mode": True,
        }
        if isinstance(cached.get("version"), dict):
            live["version"] = cached["version"]
        if isinstance(cached.get("status"), dict):
            live["status"] = cached["status"]
        return jsonify({"ok": True, "live": live})

    @app.post("/api/dudescabconfig/protocol/log-level")
    def pincabos_dudescab_protocol_log_level_v3():
        try:
            _require_maintenance()
            body = _json_body()
            name = str(body.get("level", "none")).strip().lower()
            if name not in LOG_LEVELS:
                raise ValueError("Niveau de log invalide")
            hid_command(REPORT_ADMIN, 5, bytes((LOG_LEVELS[name],)), expect_response=False)
            return jsonify({"ok": True, "level": name, "value": LOG_LEVELS[name]})
        except Exception as exc:
            return _error_response(exc)

    @app.get("/api/dudescabconfig/protocol/logs")
    def pincabos_dudescab_protocol_logs_v3():
        try:
            lines = _read_serial()
            return jsonify({"ok": True, "lines": lines, "serial": str(_serial_path() or "")})
        except Exception as exc:
            return _error_response(exc)

    @app.post("/api/dudescabconfig/protocol/logs/clear")
    def pincabos_dudescab_protocol_logs_clear_v3():
        _serial_lines.clear()
        return jsonify({"ok": True})

    @app.post("/api/dudescabconfig/protocol/reset")
    def pincabos_dudescab_protocol_reset_v3():
        try:
            _require_maintenance()
            body = _json_body()
            if body.get("confirmation") != "RESET DUDE":
                raise ValueError("Confirmation RESET DUDE requise")
            _require_idle()
            hid_command(REPORT_ADMIN, 6, expect_response=False)
            return jsonify({"ok": True, "reconnecting": True})
        except Exception as exc:
            return _error_response(exc)

    @app.post("/api/dudescabconfig/protocol/watchdog")
    def pincabos_dudescab_protocol_watchdog_v3():
        try:
            _require_maintenance()
            body = _json_body()
            if body.get("confirmation") != "TEST WATCHDOG":
                raise ValueError("Confirmation TEST WATCHDOG requise")
            _require_idle()
            hid_command(REPORT_ADMIN, 10, expect_response=False)
            return jsonify({"ok": True, "reconnecting": True})
        except Exception as exc:
            return _error_response(exc)

    @app.get("/api/dudescabconfig/protocol/outputs")
    def pincabos_dudescab_protocol_outputs_v3():
        try:
            _require_maintenance()
            version = _version()
            get_config, _, _ = _pwm_command_numbers(version)
            config = _parse_pwm_config(
                hid_command(REPORT_OUTPUTS, get_config, expect_response=True, timeout_ms=1600)
            )
            return jsonify({"ok": True, "version": version, "config": config})
        except Exception as exc:
            return _error_response(exc)

    @app.post("/api/dudescabconfig/protocol/outputs/test")
    def pincabos_dudescab_protocol_outputs_test_v3():
        try:
            _require_maintenance()
            body = _json_body()
            extension = int(body.get("extension", 1))
            output = int(body.get("output", 0))
            operation = str(body.get("operation", "pulse")).lower()
            value = int(body.get("value", 255))
            if operation == "off":
                _cancel_timer(extension, output)
                _send_pwm_value(extension, output, 0)
                result = {"extension": extension, "output": output, "value": 0, "auto_off_ms": 0}
            else:
                duration = int(body.get("duration_ms", 50 if operation == "pulse" else 10000))
                result = _test_output(extension, output, value, duration)
            return jsonify({"ok": True, "result": result})
        except Exception as exc:
            app.logger.exception("DudesCab PWM test failed")
            return _error_response(exc)

    @app.post("/api/dudescabconfig/protocol/outputs/alloff")
    def pincabos_dudescab_protocol_outputs_alloff_v3():
        try:
            _require_maintenance()
            _require_idle()
            return jsonify({"ok": True, "result": _all_off()})
        except Exception as exc:
            return _error_response(exc)

    @app.get("/api/dudescabconfig/protocol/mx")
    def pincabos_dudescab_protocol_mx_v3():
        try:
            _require_maintenance()
            probe = _probe()
            return jsonify({"ok": True, "mx": probe.get("mx"), "errors": probe.get("errors", [])})
        except Exception as exc:
            return _error_response(exc)

    @app.post("/api/dudescabconfig/protocol/mx/test")
    def pincabos_dudescab_protocol_mx_test_v3():
        try:
            _require_maintenance()
            _require_idle()
            body = _json_body()
            test_name = str(body.get("test", "rgb")).strip().lower()
            if test_name not in MX_TESTS or MX_TESTS[test_name] == 0:
                raise ValueError("Test MX invalide")
            duration = int(body.get("duration", 5))
            if not 1 <= duration <= 30:
                raise ValueError("Durée MX hors plage 1..30 secondes")
            hid_command(
                REPORT_MX,
                105,
                bytes((MX_TESTS[test_name], duration)),
                expect_response=False,
            )
            return jsonify({"ok": True, "test": test_name, "duration": duration})
        except Exception as exc:
            return _error_response(exc)

    @app.post("/api/dudescabconfig/protocol/mx/alloff")
    def pincabos_dudescab_protocol_mx_alloff_v3():
        try:
            _require_maintenance()
            _require_idle()
            hid_command(REPORT_MX, 103, expect_response=False)
            return jsonify({"ok": True, "all_off": True})
        except Exception as exc:
            return _error_response(exc)
