#!/usr/bin/env python3
"""pincabos_vpx_input : mapping des boutons VPX, section [Input] (PINCABOS_VPX_INPUT_V1).

Depuis la refonte des entrées de VPX (commit f6252e874 « Rewrite input system »,
2025-10-05), les boutons ne sont plus des clés DIK dans [Player] mais des
chaînes dans [Input] :

    Devices = Key;SDLJoy_<guid>_<n>
    Device.<id>.Name = ...        Device.<id>.Type = 1 (clavier) | 2 (joystick)
    Mapping.<Action> = <device>;<code>[;o|x;seuil] [& ...] [| ...]

  - « | » sépare des alternatives (l'une OU l'autre), « & » une combinaison ;
  - device « Key » = tous les claviers, code = scancode SDL (LSHIFT = 225) ;
  - device « SDLJoy_<guid>_<n> » : code = index de bouton SDL, 0x0100|hat*4+dir
    pour un chapeau, 0x0200|axe pour un axe utilisé comme bouton (appuyé si
    position >= seuil, ou <= seuil avec « x »).

Ce module fait la conversion evdev → SDL exactement comme SDL le fait sous
Linux (src/joystick/linux/SDL_sysjoystick.c, src/events/scancodes_linux.h,
SDL_CreateJoystickGUID) : scancode clavier, ordre des boutons (BTN_JOYSTICK..
KEY_MAX puis 0..BTN_JOYSTICK), ordre des axes (chapeaux numériques exclus),
GUID (bus, crc16 du nom, vendor, product, version).

Utilisable en module (webapp Map Commander) et en CLI (pincabos-vpx-input).
"""
from __future__ import annotations

import fcntl
import glob
import json
import os
import re
import select
import shutil
import struct
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

PREF_INI = Path("/home/pinball/.pincabos/vpx/VPinballX.ini")
LEGACY_INI = Path("/home/pinball/.local/share/VPinballX/10.8/VPinballX.ini")
BACKUP_DIR = Path("/opt/pincabos/backups/inputs-commander")
PINBALL_USER = "pinball"

KEY_DEVICE = "Key"
DEVICE_TYPE_KEYBOARD = 1
DEVICE_TYPE_JOYSTICK = 2

INPUT_SECTION = "Input"


def ini_path() -> Path:
    """Ini que VPX lit réellement (-PrefPath), repli sur l'ancien dossier versionné."""
    if PREF_INI.exists():
        return PREF_INI
    if LEGACY_INI.exists():
        return LEGACY_INI
    return PREF_INI


# ---------------------------------------------------------------------------
# Actions VPX (src/input/InputManager.cpp) : id de réglage, libellé, défaut
# clavier de VPX (scancodes SDL). Une valeur vide = action non mappée.
# ---------------------------------------------------------------------------
ACTIONS = [
    ("LeftFlipper", "Flipper gauche", "Key;225"),
    ("RightFlipper", "Flipper droit", "Key;229"),
    ("LeftStagedFlipper", "Flipper gauche staged / upper", "Key;225"),
    ("RightStagedFlipper", "Flipper droit staged / upper", "Key;229"),
    ("LeftMagna", "Magna Save gauche", "Key;224"),
    ("RightMagna", "Magna Save droit", "Key;228"),
    ("Start", "Start", "Key;30"),
    ("Credit1", "Coin / crédit 1", "Key;34"),
    ("Credit2", "Coin / crédit 2", "Key;33"),
    ("Credit3", "Coin / crédit 3", "Key;32"),
    ("Credit4", "Coin / crédit 4", "Key;35"),
    ("LaunchBall", "Plunger / Launch Ball", "Key;40"),
    ("Lockbar", "Lockbar Fire", "Key;226"),
    ("ExitGame", "Exit", "Key;41"),
    ("Pause", "Pause", "Key;19"),
    ("LeftNudge", "Nudge gauche digital", "Key;29"),
    ("RightNudge", "Nudge droite digital", "Key;56"),
    ("CenterNudge", "Nudge centre digital", "Key;44"),
    ("Tilt", "Tilt mécanique", "Key;23"),
    ("SlamTilt", "Slam Tilt", "Key;74"),
    ("ExtraBall", "Buy In / Extra Ball", "Key;5"),
    ("VolumeUp", "Volume +", "Key;46"),
    ("VolumeDown", "Volume -", "Key;45"),
    ("CoinDoor", "Coin Door", "Key;77"),
    ("Service1", "Service Cancel (1)", "Key;36"),
    ("Service2", "Service Down (2)", "Key;37"),
    ("Service3", "Service Up (3)", "Key;38"),
    ("Service4", "Service Enter (4)", "Key;39"),
    ("InGameUI", "Menu VPX en jeu", "Key;69"),
    ("PerfOverlay", "Compteur FPS", "Key;68"),
    ("Debugger", "Debugger", "Key;7"),
    ("UIUp", "Menu : élément suivant", "Key;224"),
    ("UIDown", "Menu : élément précédent", "Key;228"),
    ("UILeft", "Menu : diminuer / annuler", "Key;225"),
    ("UIRight", "Menu : augmenter / valider", "Key;229"),
    ("Custom1", "Custom 1", ""),
    ("Custom2", "Custom 2", ""),
    ("Custom3", "Custom 3", ""),
    ("Custom4", "Custom 4", ""),
]
ACTION_IDS = [a for a, _, _ in ACTIONS]
ACTION_LABELS = {a: label for a, label, _ in ACTIONS}
ACTION_DEFAULTS = {a: default for a, _, default in ACTIONS}

# Anciennes clés écrites par Map Commander (codes DIK, section [Keyboard]) :
# VPX ne les lit plus. Correspondance vers l'action VPX, et liste à purger.
LEGACY_KEYS = {
    "LeftFlipperKey": "LeftFlipper",
    "RightFlipperKey": "RightFlipper",
    "StagedLeftFlipperKey": "LeftStagedFlipper",
    "StagedRightFlipperKey": "RightStagedFlipper",
    "LeftMagnaSave": "LeftMagna",
    "RightMagnaSave": "RightMagna",
    "LeftMagnaSave2": "",
    "RightMagnaSave2": "",
    "StartGameKey": "Start",
    "StartGameKey2": "",
    "AddCreditKey": "Credit1",
    "AddCreditKey2": "Credit2",
    "PlungerKey": "LaunchBall",
    "LockbarKey": "Lockbar",
    "ExitGameKey": "ExitGame",
    "PauseKey": "Pause",
    "LeftTiltKey": "LeftNudge",
    "RightTiltKey": "RightNudge",
    "CenterTiltKey": "CenterNudge",
    "MechanicalTilt": "Tilt",
    "VolumeUpKey": "VolumeUp",
    "VolumeDownKey": "VolumeDown",
    "CoinDoorKey": "CoinDoor",
    "ServiceCancelKey": "Service1",
    "ServiceDownKey": "Service2",
    "ServiceUpKey": "Service3",
    "ServiceEnterKey": "Service4",
    "BuyInKey": "ExtraBall",
    "FrameCountKey": "PerfOverlay",
    "DebuggerKey": "Debugger",
    "Enable3DKey": "",
    "JoyCustom1Key": "Custom1",
    "JoyCustom2Key": "Custom2",
    "JoyCustom3Key": "Custom3",
    "JoyCustom4Key": "Custom4",
}
LEGACY_COMMENT = "PinCabOS fonction(Inputs Commander Keyboard"

# ---------------------------------------------------------------------------
# Tables SDL (générées depuis SDL3 : scancodes_linux.h et SDL_scancode.h)
# ---------------------------------------------------------------------------
EVDEV_TO_SCANCODE = {1: 41, 2: 30, 3: 31, 4: 32, 5: 33, 6: 34, 7: 35, 8: 36, 9: 37, 10: 38, 11: 39, 12: 45, 13: 46, 14: 42, 15: 43, 16: 20, 17: 26, 18: 8, 19: 21, 20: 23, 21: 28, 22: 24, 23: 12, 24: 18, 25: 19, 26: 47, 27: 48, 28: 40, 29: 224, 30: 4, 31: 22, 32: 7, 33: 9, 34: 10, 35: 11, 36: 13, 37: 14, 38: 15, 39: 51, 40: 52, 41: 53, 42: 225, 43: 49, 44: 29, 45: 27, 46: 6, 47: 25, 48: 5, 49: 17, 50: 16, 51: 54, 52: 55, 53: 56, 54: 229, 55: 85, 56: 226, 57: 44, 58: 57, 59: 58, 60: 59, 61: 60, 62: 61, 63: 62, 64: 63, 65: 64, 66: 65, 67: 66, 68: 67, 69: 83, 70: 71, 71: 95, 72: 96, 73: 97, 74: 86, 75: 92, 76: 93, 77: 94, 78: 87, 79: 89, 80: 90, 81: 91, 82: 98, 83: 99, 85: 148, 86: 100, 87: 68, 88: 69, 89: 135, 90: 146, 91: 147, 92: 138, 93: 136, 94: 139, 95: 140, 96: 88, 97: 228, 98: 84, 99: 154, 100: 230, 102: 74, 103: 82, 104: 75, 105: 80, 106: 79, 107: 77, 108: 81, 109: 78, 110: 73, 111: 76, 113: 127, 114: 129, 115: 128, 116: 102, 117: 103, 118: 215, 119: 72, 121: 133, 122: 144, 123: 145, 124: 137, 125: 227, 126: 231, 127: 101, 128: 120, 129: 121, 130: 279, 131: 122, 133: 124, 134: 274, 135: 125, 136: 126, 137: 123, 138: 117, 139: 118, 142: 258, 143: 259, 156: 286, 158: 282, 159: 283, 161: 270, 162: 270, 163: 267, 164: 271, 165: 268, 166: 269, 167: 264, 168: 266, 172: 281, 173: 285, 174: 276, 179: 182, 180: 183, 181: 273, 182: 121, 183: 104, 184: 105, 185: 106, 186: 107, 187: 108, 188: 109, 189: 110, 190: 111, 191: 112, 192: 113, 193: 114, 194: 115, 200: 262, 201: 263, 206: 275, 207: 262, 208: 265, 210: 70, 217: 280, 222: 153, 223: 155, 226: 272, 234: 277, 353: 119, 355: 156, 373: 257, 402: 260, 403: 261}
SCANCODE_NAMES = {0: 'UNKNOWN', 4: 'A', 5: 'B', 6: 'C', 7: 'D', 8: 'E', 9: 'F', 10: 'G', 11: 'H', 12: 'I', 13: 'J', 14: 'K', 15: 'L', 16: 'M', 17: 'N', 18: 'O', 19: 'P', 20: 'Q', 21: 'R', 22: 'S', 23: 'T', 24: 'U', 25: 'V', 26: 'W', 27: 'X', 28: 'Y', 29: 'Z', 30: '1', 31: '2', 32: '3', 33: '4', 34: '5', 35: '6', 36: '7', 37: '8', 38: '9', 39: '0', 40: 'RETURN', 41: 'ESCAPE', 42: 'BACKSPACE', 43: 'TAB', 44: 'SPACE', 45: 'MINUS', 46: 'EQUALS', 47: 'LEFTBRACKET', 48: 'RIGHTBRACKET', 49: 'BACKSLASH', 50: 'NONUSHASH', 51: 'SEMICOLON', 52: 'APOSTROPHE', 53: 'GRAVE', 54: 'COMMA', 55: 'PERIOD', 56: 'SLASH', 57: 'CAPSLOCK', 58: 'F1', 59: 'F2', 60: 'F3', 61: 'F4', 62: 'F5', 63: 'F6', 64: 'F7', 65: 'F8', 66: 'F9', 67: 'F10', 68: 'F11', 69: 'F12', 70: 'PRINTSCREEN', 71: 'SCROLLLOCK', 72: 'PAUSE', 73: 'INSERT', 74: 'HOME', 75: 'PAGEUP', 76: 'DELETE', 77: 'END', 78: 'PAGEDOWN', 79: 'RIGHT', 80: 'LEFT', 81: 'DOWN', 82: 'UP', 83: 'NUMLOCKCLEAR', 84: 'KP_DIVIDE', 85: 'KP_MULTIPLY', 86: 'KP_MINUS', 87: 'KP_PLUS', 88: 'KP_ENTER', 89: 'KP_1', 90: 'KP_2', 91: 'KP_3', 92: 'KP_4', 93: 'KP_5', 94: 'KP_6', 95: 'KP_7', 96: 'KP_8', 97: 'KP_9', 98: 'KP_0', 99: 'KP_PERIOD', 100: 'NONUSBACKSLASH', 101: 'APPLICATION', 102: 'POWER', 103: 'KP_EQUALS', 104: 'F13', 105: 'F14', 106: 'F15', 107: 'F16', 108: 'F17', 109: 'F18', 110: 'F19', 111: 'F20', 112: 'F21', 113: 'F22', 114: 'F23', 115: 'F24', 116: 'EXECUTE', 117: 'HELP', 118: 'MENU', 119: 'SELECT', 120: 'STOP', 121: 'AGAIN', 122: 'UNDO', 123: 'CUT', 124: 'COPY', 125: 'PASTE', 126: 'FIND', 127: 'MUTE', 128: 'VOLUMEUP', 129: 'VOLUMEDOWN', 130: 'LOCKINGCAPSLOCK', 131: 'LOCKINGNUMLOCK', 132: 'LOCKINGSCROLLLOCK', 133: 'KP_COMMA', 134: 'KP_EQUALSAS400', 135: 'INTERNATIONAL1', 136: 'INTERNATIONAL2', 137: 'INTERNATIONAL3', 138: 'INTERNATIONAL4', 139: 'INTERNATIONAL5', 140: 'INTERNATIONAL6', 141: 'INTERNATIONAL7', 142: 'INTERNATIONAL8', 143: 'INTERNATIONAL9', 144: 'LANG1', 145: 'LANG2', 146: 'LANG3', 147: 'LANG4', 148: 'LANG5', 149: 'LANG6', 150: 'LANG7', 151: 'LANG8', 152: 'LANG9', 153: 'ALTERASE', 154: 'SYSREQ', 155: 'CANCEL', 156: 'CLEAR', 157: 'PRIOR', 158: 'RETURN2', 159: 'SEPARATOR', 160: 'OUT', 161: 'OPER', 162: 'CLEARAGAIN', 163: 'CRSEL', 164: 'EXSEL', 176: 'KP_00', 177: 'KP_000', 178: 'THOUSANDSSEPARATOR', 179: 'DECIMALSEPARATOR', 180: 'CURRENCYUNIT', 181: 'CURRENCYSUBUNIT', 182: 'KP_LEFTPAREN', 183: 'KP_RIGHTPAREN', 184: 'KP_LEFTBRACE', 185: 'KP_RIGHTBRACE', 186: 'KP_TAB', 187: 'KP_BACKSPACE', 188: 'KP_A', 189: 'KP_B', 190: 'KP_C', 191: 'KP_D', 192: 'KP_E', 193: 'KP_F', 194: 'KP_XOR', 195: 'KP_POWER', 196: 'KP_PERCENT', 197: 'KP_LESS', 198: 'KP_GREATER', 199: 'KP_AMPERSAND', 200: 'KP_DBLAMPERSAND', 201: 'KP_VERTICALBAR', 202: 'KP_DBLVERTICALBAR', 203: 'KP_COLON', 204: 'KP_HASH', 205: 'KP_SPACE', 206: 'KP_AT', 207: 'KP_EXCLAM', 208: 'KP_MEMSTORE', 209: 'KP_MEMRECALL', 210: 'KP_MEMCLEAR', 211: 'KP_MEMADD', 212: 'KP_MEMSUBTRACT', 213: 'KP_MEMMULTIPLY', 214: 'KP_MEMDIVIDE', 215: 'KP_PLUSMINUS', 216: 'KP_CLEAR', 217: 'KP_CLEARENTRY', 218: 'KP_BINARY', 219: 'KP_OCTAL', 220: 'KP_DECIMAL', 221: 'KP_HEXADECIMAL', 224: 'LCTRL', 225: 'LSHIFT', 226: 'LALT', 227: 'LGUI', 228: 'RCTRL', 229: 'RSHIFT', 230: 'RALT', 231: 'RGUI', 257: 'MODE', 258: 'SLEEP', 259: 'WAKE', 260: 'CHANNEL_INCREMENT', 261: 'CHANNEL_DECREMENT', 262: 'MEDIA_PLAY', 263: 'MEDIA_PAUSE', 264: 'MEDIA_RECORD', 265: 'MEDIA_FAST_FORWARD', 266: 'MEDIA_REWIND', 267: 'MEDIA_NEXT_TRACK', 268: 'MEDIA_PREVIOUS_TRACK', 269: 'MEDIA_STOP', 270: 'MEDIA_EJECT', 271: 'MEDIA_PLAY_PAUSE', 272: 'MEDIA_SELECT', 273: 'AC_NEW', 274: 'AC_OPEN', 275: 'AC_CLOSE', 276: 'AC_EXIT', 277: 'AC_SAVE', 278: 'AC_PRINT', 279: 'AC_PROPERTIES', 280: 'AC_SEARCH', 281: 'AC_HOME', 282: 'AC_BACK', 283: 'AC_FORWARD', 284: 'AC_STOP', 285: 'AC_REFRESH', 286: 'AC_BOOKMARKS', 287: 'SOFTLEFT', 288: 'SOFTRIGHT', 289: 'CALL', 290: 'ENDCALL'}

KEY_LABELS = {
    225: "Shift gauche", 229: "Shift droit", 224: "Ctrl gauche", 228: "Ctrl droit",
    226: "Alt gauche", 230: "Alt droit", 227: "Windows gauche", 231: "Windows droit",
    40: "Entrée", 41: "Échap", 42: "Retour arrière", 43: "Tab", 44: "Espace",
    45: "-", 46: "=", 47: "[", 48: "]", 49: "\\", 51: ";", 52: "'", 53: "`",
    54: ",", 55: ".", 56: "/", 57: "Verr. maj",
    73: "Inser", 74: "Début (Home)", 75: "Page haut", 76: "Suppr", 77: "Fin (End)",
    78: "Page bas", 79: "Flèche droite", 80: "Flèche gauche", 81: "Flèche bas", 82: "Flèche haut",
    88: "Entrée (pavé)", 89: "Pavé 1", 90: "Pavé 2", 91: "Pavé 3", 92: "Pavé 4", 93: "Pavé 5",
    94: "Pavé 6", 95: "Pavé 7", 96: "Pavé 8", 97: "Pavé 9", 98: "Pavé 0",
}
for _i in range(26):
    KEY_LABELS.setdefault(4 + _i, chr(ord("A") + _i))
for _i in range(9):
    KEY_LABELS.setdefault(30 + _i, str(_i + 1))
KEY_LABELS.setdefault(39, "0")
for _i in range(12):
    KEY_LABELS.setdefault(58 + _i, "F%d" % (_i + 1))


def scancode_label(code: int) -> str:
    if code in KEY_LABELS:
        return KEY_LABELS[code]
    name = SCANCODE_NAMES.get(code)
    return name.replace("_", " ").title() if name else "scancode %d" % code


# ---------------------------------------------------------------------------
# Format des mappings VPX (InputAction::SetMapping / GetMappingString)
# ---------------------------------------------------------------------------
@dataclass
class Binding:
    device: str
    code: int
    reversed: bool = False
    threshold: float = 0.0

    def is_key(self) -> bool:
        return self.device == KEY_DEVICE

    def is_axis(self) -> bool:
        return 0x0200 <= self.code < 0x0300

    def is_hat(self) -> bool:
        return 0x0100 <= self.code < 0x0200

    def to_vpx(self) -> str:
        s = "%s;%d" % (self.device, self.code)
        if self.threshold != 0.0 or self.reversed:
            s += ";%s;%.6f" % ("x" if self.reversed else "o", self.threshold)
        return s


def parse_binding(token: str) -> Binding:
    parts = [p.strip() for p in token.strip().split(";")]
    if len(parts) < 2 or not parts[0]:
        raise ValueError("binding invalide : %r (attendu device;code)" % token)
    try:
        code = int(parts[1])
    except ValueError:
        raise ValueError("code invalide dans %r" % token) from None
    if not 0 <= code <= 0xFFFF:
        raise ValueError("code hors plage dans %r" % token)
    b = Binding(parts[0], code)
    if len(parts) >= 4:
        if parts[2] not in ("o", "x"):
            raise ValueError("sens d'axe invalide dans %r (o ou x)" % token)
        try:
            b.threshold = float(parts[3])
        except ValueError:
            raise ValueError("seuil invalide dans %r" % token) from None
        b.reversed = parts[2] == "x"
    elif len(parts) == 3:
        raise ValueError("seuil manquant dans %r" % token)
    return b


def parse_mapping(text: str) -> list[list[Binding]]:
    """'Key;225 | Joy;3 & Joy;4' → [[Key;225], [Joy;3, Joy;4]]. Vide → []."""
    alternatives = []
    for alt in (text or "").split("|"):
        if not alt.strip():
            continue
        alternatives.append([parse_binding(t) for t in alt.split("&")])
    return alternatives


def format_mapping(alternatives) -> str:
    return " | ".join(" & ".join(b.to_vpx() for b in alt) for alt in alternatives)


def normalize_mapping(text: str) -> str:
    """Valide et réécrit une chaîne saisie par l'utilisateur au format VPX."""
    return format_mapping(parse_mapping(text))


def devices_in_mapping(text: str) -> set:
    return {b.device for alt in parse_mapping(text) for b in alt if not b.is_key()}


def binding_label(b: Binding, device_names: dict | None = None) -> str:
    if b.is_key():
        return "Clavier : " + scancode_label(b.code)
    name = (device_names or {}).get(b.device) or short_device_id(b.device)
    if b.is_hat():
        hat, direction = (b.code & 0xFF) >> 2, b.code & 3
        return "%s : chapeau %d %s" % (name, hat, ("gauche", "droite", "haut", "bas")[direction])
    if b.is_axis():
        return "%s : axe %d %s %.2f" % (name, b.code & 0xFF, "<=" if b.reversed else ">=", b.threshold)
    return "%s : bouton %d" % (name, b.code)


def mapping_label(text: str, device_names: dict | None = None) -> str:
    try:
        alts = parse_mapping(text)
    except ValueError as exc:
        return "invalide (%s)" % exc
    if not alts:
        return "non mappé"
    return " ou ".join(" + ".join(binding_label(b, device_names) for b in alt) for alt in alts)


def short_device_id(device: str) -> str:
    m = re.match(r"^SDLJoy_([0-9a-f]{32})_(\d+)$", device)
    if m:
        return "joystick %s…_%s" % (m.group(1)[:8], m.group(2))
    return device


def merge_binding(current: str, binding: Binding) -> str:
    """Remplace, dans le mapping courant, les alternatives du même type
    (clavier / autre périphérique) par le binding détecté ; garde le reste.
    Idempotent : détecter deux fois le même bouton donne la même chaîne."""
    kept = [alt for alt in parse_mapping(current) if any(b.is_key() for b in alt) != binding.is_key()]
    kept.append([binding])
    return format_mapping(kept)


# ---------------------------------------------------------------------------
# Édition de VPinballX.ini (sections, clés « Cle = Valeur », commentaires « ; »)
# ---------------------------------------------------------------------------
class VpxIni:
    def __init__(self, path):
        self.path = Path(path)
        self.lines = self.path.read_text(errors="replace").splitlines() if self.path.exists() else []

    @staticmethod
    def _is_section(line: str) -> bool:
        s = line.strip()
        return s.startswith("[") and s.endswith("]")

    def section_bounds(self, name: str):
        """(début, fin) : indice de l'en-tête et indice de la section suivante."""
        for i, line in enumerate(self.lines):
            if self._is_section(line) and line.strip()[1:-1].lower() == name.lower():
                end = len(self.lines)
                for j in range(i + 1, len(self.lines)):
                    if self._is_section(self.lines[j]):
                        end = j
                        break
                return i, end
        return None

    @staticmethod
    def _split(line: str):
        s = line.strip()
        if not s or s.startswith((";", "#")) or "=" not in s:
            return None
        k, v = line.split("=", 1)
        return k.strip(), v.strip()

    def get(self, section: str, key: str):
        bounds = self.section_bounds(section)
        if not bounds:
            return None
        for line in self.lines[bounds[0] + 1:bounds[1]]:
            kv = self._split(line)
            if kv and kv[0].lower() == key.lower():
                return kv[1]
        return None

    def items(self, section: str) -> dict:
        bounds = self.section_bounds(section)
        out = {}
        if bounds:
            for line in self.lines[bounds[0] + 1:bounds[1]]:
                kv = self._split(line)
                if kv and kv[0] not in out:
                    out[kv[0]] = kv[1]
        return out

    def set(self, section: str, key: str, value: str) -> None:
        bounds = self.section_bounds(section)
        if not bounds:
            if self.lines and self.lines[-1].strip():
                self.lines.append("")
            self.lines.append("[%s]" % section)
            bounds = (len(self.lines) - 1, len(self.lines))
        start, end = bounds
        for i in range(start + 1, end):
            kv = self._split(self.lines[i])
            if kv and kv[0].lower() == key.lower():
                self.lines[i] = "%s = %s" % (kv[0], value)
                return
        insert = end
        while insert > start + 1 and not self.lines[insert - 1].strip():
            insert -= 1
        self.lines.insert(insert, "%s = %s" % (key, value))

    def delete(self, section: str, key: str) -> bool:
        bounds = self.section_bounds(section)
        if not bounds:
            return False
        for i in range(bounds[0] + 1, bounds[1]):
            kv = self._split(self.lines[i])
            if kv and kv[0].lower() == key.lower():
                del self.lines[i]
                return True
        return False

    def text(self) -> str:
        return "\n".join(self.lines) + "\n"

    def save(self, backup: bool = True, backup_dir: Path | None = None) -> str:
        backup_path = ""
        if backup and self.path.exists():
            bdir = Path(backup_dir or BACKUP_DIR)
            bdir.mkdir(parents=True, exist_ok=True)
            backup_path = str(bdir / ("VPinballX.ini.backup-map-commander-" + datetime.now().strftime("%Y%m%d-%H%M%S")))
            shutil.copy2(self.path, backup_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(self.text())
        try:
            shutil.chown(self.path, PINBALL_USER, PINBALL_USER)
        except Exception:
            pass
        return backup_path

    # --- section [Input] -------------------------------------------------
    def input_mappings(self) -> dict:
        return {k[len("Mapping."):]: v for k, v in self.items(INPUT_SECTION).items()
                if k.startswith("Mapping.") and "." not in k[len("Mapping."):]}

    def input_devices(self) -> list:
        raw = self.get(INPUT_SECTION, "Devices") or ""
        return [d.strip() for d in raw.split(";") if d.strip()]

    def device_names(self) -> dict:
        names = {}
        for k, v in self.items(INPUT_SECTION).items():
            m = re.match(r"^Device\.(.+)\.Name$", k)
            if m and v:
                names[m.group(1)] = v
        names.setdefault(KEY_DEVICE, "Clavier")
        return names

    def ensure_device(self, setting_id: str, name: str = "", dtype: int = DEVICE_TYPE_JOYSTICK) -> None:
        devices = self.input_devices()
        if setting_id not in devices:
            devices.append(setting_id)
            self.set(INPUT_SECTION, "Devices", ";".join(devices))
        if self.get(INPUT_SECTION, "Device.%s.Type" % setting_id) in (None, ""):
            self.set(INPUT_SECTION, "Device.%s.Type" % setting_id, str(dtype))
        if name and not self.get(INPUT_SECTION, "Device.%s.Name" % setting_id):
            self.set(INPUT_SECTION, "Device.%s.Name" % setting_id, name)

    def set_mapping(self, action: str, mapping: str) -> None:
        self.set(INPUT_SECTION, "Mapping." + action, normalize_mapping(mapping))

    def purge_legacy(self) -> int:
        """Retire ce que l'ancien Map Commander écrivait (codes DIK que VPX ne
        lit plus) : le bloc « ; Modifié … fonction(Inputs Commander Keyboard) »
        suivi de ses clés, où qu'il soit, plus les clés isolées de la section
        [Keyboard] (créée par lui). Les clés historiques de VPX dans [Player]
        ne sont pas touchées. Une section [Keyboard] vide est retirée.
        Renvoie le nombre de lignes retirées."""
        removed = 0
        out = []
        section = ""
        in_block = False
        for line in self.lines:
            if self._is_section(line):
                section = line.strip()[1:-1].lower()
                in_block = False
                out.append(line)
                continue
            kv = self._split(line)
            if LEGACY_COMMENT in line:
                in_block = True
                removed += 1
                continue
            if kv and kv[0] in LEGACY_KEYS and (in_block or section == "keyboard"):
                removed += 1
                continue
            in_block = False
            out.append(line)
        self.lines = out
        bounds = self.section_bounds("Keyboard")
        if bounds and not any(l.strip() for l in self.lines[bounds[0] + 1:bounds[1]]):
            del self.lines[bounds[0]:bounds[1]]
            removed += 1
        return removed


# ---------------------------------------------------------------------------
# Périphériques evdev, vus comme SDL les voit
# ---------------------------------------------------------------------------
EV_KEY, EV_ABS = 1, 3
BTN_MISC, BTN_MOUSE, BTN_JOYSTICK, BTN_GAMEPAD, BTN_TOUCH, BTN_TRIGGER_HAPPY = 0x100, 0x110, 0x120, 0x130, 0x14A, 0x2C0
KEY_MAX, ABS_MAX = 0x2FF, 0x3F
ABS_X, ABS_Y, ABS_HAT0X, ABS_HAT3Y = 0, 1, 0x10, 0x17
EVENT_FMT = "llHHi"
EVENT_SIZE = struct.calcsize(EVENT_FMT)


def _ioc(direction: int, typ: str, nr: int, size: int) -> int:
    return (direction << 30) | (size << 16) | (ord(typ) << 8) | nr


def EVIOCGNAME(n):
    return _ioc(2, "E", 0x06, n)


EVIOCGID = _ioc(2, "E", 0x02, 8)


def EVIOCGBIT(ev, n):
    return _ioc(2, "E", 0x20 + ev, n)


def EVIOCGABS(a):
    return _ioc(2, "E", 0x40 + a, 24)


def crc16(data: bytes, crc: int = 0) -> int:
    """SDL_crc16 (polynôme réfléchi 0xA001, init 0, sans xor final)."""
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc & 0xFFFF


def sdl_guid(bus: int, vendor: int, product: int, version: int, name: str) -> str:
    """SDL_CreateJoystickGUID(bus, vendor, product, version, NULL, name) en hexa."""
    crc = crc16(name.encode("utf-8", "replace"))
    if vendor:
        raw = struct.pack("<8H", bus, crc, vendor, 0, product, 0, version, 0)
    else:
        raw = struct.pack("<2H", bus, crc) + name.encode("utf-8", "replace")[:11].ljust(12, b"\0")
    return raw.hex()


class EvdevDevice:
    """Capacités d'un /dev/input/eventN (ou d'un faux périphérique pour les tests)."""

    def __init__(self, path: str, name: str, ids: tuple, keybits: bytes, absbits: bytes, absinfo: dict | None = None):
        self.path = path
        self.name = name
        self.bus, self.vendor, self.product, self.version = ids
        self.keybits = keybits
        self.absbits = absbits
        self._absinfo = dict(absinfo or {})
        m = re.search(r"event(\d+)$", path)
        self.number = int(m.group(1)) if m else 0

    @classmethod
    def open(cls, path: str) -> "EvdevDevice":
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        try:
            name = fcntl.ioctl(fd, EVIOCGNAME(256), b"\0" * 256).split(b"\0", 1)[0].decode("utf-8", "replace")
            ids = struct.unpack("4H", fcntl.ioctl(fd, EVIOCGID, b"\0" * 8))
            keybits = bytes(fcntl.ioctl(fd, EVIOCGBIT(EV_KEY, KEY_MAX // 8 + 1), b"\0" * (KEY_MAX // 8 + 1)))
            absbits = bytes(fcntl.ioctl(fd, EVIOCGBIT(EV_ABS, ABS_MAX // 8 + 1), b"\0" * (ABS_MAX // 8 + 1)))
            dev = cls(path, name, ids, keybits, absbits)
            for a in range(ABS_MAX):
                if dev.has_abs(a):
                    try:
                        dev._absinfo[a] = struct.unpack("6i", fcntl.ioctl(fd, EVIOCGABS(a), b"\0" * 24))
                    except OSError:
                        pass
            return dev
        finally:
            os.close(fd)

    @classmethod
    def fake(cls, path: str, name: str, ids: tuple, keys=(), axes: dict | None = None) -> "EvdevDevice":
        """axes : {code: (value, min, max)}."""
        keybits = bytearray(KEY_MAX // 8 + 1)
        for k in keys:
            keybits[k >> 3] |= 1 << (k & 7)
        absbits = bytearray(ABS_MAX // 8 + 1)
        absinfo = {}
        for a, (value, mn, mx) in (axes or {}).items():
            absbits[a >> 3] |= 1 << (a & 7)
            absinfo[a] = (value, mn, mx, 0, 0, 0)
        return cls(path, name, ids, bytes(keybits), bytes(absbits), absinfo)

    def has_key(self, code: int) -> bool:
        return code < len(self.keybits) * 8 and bool(self.keybits[code >> 3] & (1 << (code & 7)))

    def has_abs(self, code: int) -> bool:
        return code < len(self.absbits) * 8 and bool(self.absbits[code >> 3] & (1 << (code & 7)))

    def absinfo(self, code: int):
        return self._absinfo.get(code)

    @property
    def is_joystick(self) -> bool:
        if any(self.has_key(i) for i in range(BTN_JOYSTICK, BTN_GAMEPAD + 0x10)):
            return True
        if any(self.has_key(i) for i in range(BTN_TRIGGER_HAPPY, BTN_TRIGGER_HAPPY + 0x40)):
            return True
        return self.has_abs(ABS_X) and self.has_abs(ABS_Y) and not self.has_key(BTN_MOUSE) and not self.has_key(BTN_TOUCH)

    @property
    def is_keyboard(self) -> bool:
        return any(self.has_key(i) for i in range(1, 0x80))

    @property
    def guid(self) -> str:
        return sdl_guid(self.bus, self.vendor, self.product, self.version, self.name)

    def button_order(self) -> list:
        """Ordre d'attribution des index de bouton par SDL (linux)."""
        return [i for i in range(BTN_JOYSTICK, KEY_MAX) if self.has_key(i)] + \
               [i for i in range(0, BTN_JOYSTICK) if self.has_key(i)]

    def sdl_button_index(self, code: int) -> int:
        return self.button_order().index(code)

    def digital_hats(self) -> set:
        hats = set()
        for i in range(ABS_HAT0X, ABS_HAT3Y + 1, 2):
            infos = [self.absinfo(c) for c in (i, i + 1) if self.has_abs(c)]
            if infos and all(-1 <= info[1] <= 0 and 0 <= info[2] <= 1 for info in infos):
                hats.add((i - ABS_HAT0X) // 2)
        return hats

    def axis_order(self) -> list:
        hats = self.digital_hats()
        return [i for i in range(ABS_MAX) if self.has_abs(i)
                and not (ABS_HAT0X <= i <= ABS_HAT3Y and (i - ABS_HAT0X) // 2 in hats)]

    def sdl_axis_index(self, code: int) -> int:
        return self.axis_order().index(code)

    def normalized(self, code: int, value: int) -> float:
        info = self.absinfo(code)
        if not info or info[2] == info[1]:
            return 0.0
        v = (value - info[1]) / float(info[2] - info[1]) * 2.0 - 1.0
        return max(-1.0, min(1.0, v))


def list_devices() -> list:
    devices = []
    for path in sorted(glob.glob("/dev/input/event*"), key=lambda p: int(re.search(r"(\d+)$", p).group(1))):
        try:
            devices.append(EvdevDevice.open(path))
        except OSError:
            continue
    return devices


def joystick_setting_ids(devices) -> dict:
    """{chemin: (SDLJoy_<guid>_<n>, nom affiché par VPX)} pour les joysticks,
    numérotés comme VPX (n = rang parmi les GUID identiques, à partir de 1)."""
    out = {}
    seen_guid: dict = {}
    seen_name: dict = {}
    for dev in sorted((d for d in devices if d.is_joystick), key=lambda d: d.number):
        seen_guid[dev.guid] = seen_guid.get(dev.guid, 0) + 1
        seen_name[dev.name] = seen_name.get(dev.name, 0) + 1
        out[dev.path] = ("SDLJoy_%s_%d" % (dev.guid, seen_guid[dev.guid]), "%s #%d" % (dev.name, seen_name[dev.name]))
    return out


def event_to_binding(dev: EvdevDevice, setting_id: str, etype: int, code: int, value: int, rest: dict | None = None):
    """Traduit un événement evdev en binding VPX, ou None s'il n'est pas un appui."""
    if etype == EV_KEY:
        if value != 1:
            return None
        if dev.is_joystick:
            try:
                return Binding(setting_id, dev.sdl_button_index(code))
            except ValueError:
                return None
        sc = EVDEV_TO_SCANCODE.get(code)
        return Binding(KEY_DEVICE, sc) if sc else None
    if etype == EV_ABS and dev.is_joystick:
        if ABS_HAT0X <= code <= ABS_HAT3Y and (code - ABS_HAT0X) // 2 in dev.digital_hats():
            if value == 0:
                return None
            hat = (code - ABS_HAT0X) // 2
            direction = (0 if value < 0 else 1) if (code - ABS_HAT0X) % 2 == 0 else (2 if value < 0 else 3)
            return Binding(setting_id, 0x0100 | (hat * 4 + direction))
        if not dev.has_abs(code):
            return None
        v = dev.normalized(code, value)
        r = (rest or {}).get(code, 0.0)
        if abs(v - r) < 0.5:
            return None
        return Binding(setting_id, 0x0200 | dev.sdl_axis_index(code), reversed=v < r, threshold=round((v + r) / 2.0, 6))
    return None


def detect_once(timeout: float = 8.0):
    """Attend un appui sur n'importe quel périphérique. Renvoie un dict
    {binding, label, device, raw} ou None (timeout / aucun périphérique)."""
    devices = list_devices()
    ids = joystick_setting_ids(devices)
    handles = []
    rest = {}
    for dev in devices:
        try:
            fd = os.open(dev.path, os.O_RDONLY | os.O_NONBLOCK)
        except OSError:
            continue
        handles.append((dev, fd))
        rest[dev.path] = {a: dev.normalized(a, dev.absinfo(a)[0]) for a in dev.axis_order() if dev.absinfo(a)}
    if not handles:
        return {"error": "aucun /dev/input/event* lisible"}
    names = {sid: name for sid, name in ids.values()}
    try:
        deadline = time.time() + timeout
        while time.time() < deadline:
            ready, _, _ = select.select([fd for _, fd in handles], [], [], 0.25)
            for fd in ready:
                dev = next(d for d, f in handles if f == fd)
                try:
                    data = os.read(fd, EVENT_SIZE * 64)
                except OSError:
                    continue
                for off in range(0, len(data) - EVENT_SIZE + 1, EVENT_SIZE):
                    _, _, etype, code, value = struct.unpack(EVENT_FMT, data[off:off + EVENT_SIZE])
                    sid = ids.get(dev.path, ("", ""))[0]
                    b = event_to_binding(dev, sid, etype, code, value, rest.get(dev.path))
                    if b is None:
                        continue
                    return {
                        "binding": b.to_vpx(),
                        "label": binding_label(b, names),
                        "device": dev.name,
                        "device_id": sid if not b.is_key() else KEY_DEVICE,
                        "raw": "%s type=%d code=%d value=%d" % (os.path.basename(dev.path), etype, code, value),
                    }
        return None
    finally:
        for _, fd in handles:
            try:
                os.close(fd)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Écriture complète (webapp et CLI)
# ---------------------------------------------------------------------------
def write_mappings(mappings: dict, path=None, backup: bool = True, devices=None) -> dict:
    """Écrit Mapping.<Action> pour chaque action donnée, déclare les joysticks
    référencés (Devices / Device.<id>.Type / .Name) et purge les clés mortes."""
    ini = VpxIni(path or ini_path())
    known = {sid: name for sid, name in joystick_setting_ids(devices if devices is not None else _safe_list_devices()).values()}
    normalized = {}
    for action, text in mappings.items():
        if action not in ACTION_LABELS:
            raise ValueError("action VPX inconnue : %s" % action)
        normalized[action] = normalize_mapping(text)
    for action, text in normalized.items():
        ini.set_mapping(action, text)
        for sid in devices_in_mapping(text):
            ini.ensure_device(sid, known.get(sid, ""), DEVICE_TYPE_JOYSTICK)
    ini.ensure_device(KEY_DEVICE, "Keyboards", DEVICE_TYPE_KEYBOARD)
    purged = ini.purge_legacy()
    backup_path = ini.save(backup=backup)
    return {"path": str(ini.path), "backup": backup_path, "purged": purged, "mappings": normalized}


def _safe_list_devices():
    try:
        return list_devices()
    except Exception:
        return []


def current_state(path=None, devices=None) -> dict:
    ini = VpxIni(path or ini_path())
    names = ini.device_names()
    joysticks = joystick_setting_ids(devices if devices is not None else _safe_list_devices())
    for sid, name in joysticks.values():
        names.setdefault(sid, name)
    mappings = ini.input_mappings()
    actions = []
    for action, label, default in ACTIONS:
        present = action in mappings
        text = mappings.get(action, default)
        actions.append({
            "action": action, "label": label, "mapping": text, "present": present,
            "decoded": mapping_label(text, names), "default": default,
        })
    return {"path": str(ini.path), "actions": actions, "device_names": names,
            "joysticks": [{"path": p, "id": sid, "name": name} for p, (sid, name) in joysticks.items()],
            "declared": ini.input_devices()}


# ---------------------------------------------------------------------------
# VPinFE : même appui, même navigation (PINCABOS_VPX_INPUT_VPINFE_V1)
# vpinfe.ini [Input] : joy<fn> = index de bouton (API Gamepad du navigateur,
# ordre joydev = ordre SDL pour les codes >= BTN_MISC), key<fn> = liste de
# noms de touches DOM (event.code ou event.key, comparés en minuscules).
# ---------------------------------------------------------------------------
VPINFE_INI = Path("/home/pinball/.config/vpinfe/vpinfe.ini")

VPINFE_FUNCTIONS = [
    ("left", "Table précédente (gauche)"),
    ("right", "Table suivante (droite)"),
    ("select", "Lancer la table / valider"),
    ("menu", "Menu VPinFE"),
    ("back", "Retour"),
    ("exit", "Quitter VPinFE"),
    ("pageup", "Page précédente"),
    ("pagedown", "Page suivante"),
    ("up", "Haut"),
    ("down", "Bas"),
    ("tutorial", "Tutoriel"),
    ("collectionmenu", "Menu des collections"),
]
VPINFE_FUNCTION_LABELS = dict(VPINFE_FUNCTIONS)

# Politique PinCabOS : quelle action VPX pilote chaque fonction VPinFE.
VPINFE_DEFAULT_POLICY = {
    "left": "LeftFlipper", "right": "RightFlipper", "select": "Start", "menu": "LaunchBall",
    "back": "Credit1", "exit": "ExitGame", "pageup": "LeftMagna", "pagedown": "RightMagna",
    "up": "Custom1", "down": "Custom2", "tutorial": "Custom3", "collectionmenu": "Custom4",
}

# Défauts clavier de VPinFE (frontend/input_api.py) : toujours conservés.
VPINFE_KEY_DEFAULTS = {
    "left": "ArrowLeft,ShiftLeft", "right": "ArrowRight,ShiftRight", "up": "ArrowUp", "down": "ArrowDown",
    "pageup": "PageUp", "pagedown": "PageDown", "select": "Enter", "menu": "m", "back": "b",
    "tutorial": "t", "exit": "Escape,q", "collectionmenu": "c",
}

# scancode SDL -> KeyboardEvent.code (ce que VPinFE compare, en minuscules)
SCANCODE_TO_DOM = {
    40: "Enter", 41: "Escape", 42: "Backspace", 43: "Tab", 44: "Space", 45: "Minus", 46: "Equal",
    47: "BracketLeft", 48: "BracketRight", 49: "Backslash", 51: "Semicolon", 52: "Quote", 53: "Backquote",
    54: "Comma", 55: "Period", 56: "Slash", 57: "CapsLock", 73: "Insert", 74: "Home", 75: "PageUp",
    76: "Delete", 77: "End", 78: "PageDown", 79: "ArrowRight", 80: "ArrowLeft", 81: "ArrowDown", 82: "ArrowUp",
    88: "NumpadEnter", 98: "Numpad0", 224: "ControlLeft", 225: "ShiftLeft", 226: "AltLeft", 227: "MetaLeft",
    228: "ControlRight", 229: "ShiftRight", 230: "AltRight", 231: "MetaRight",
}
for _i in range(26):
    SCANCODE_TO_DOM[4 + _i] = "Key" + chr(ord("A") + _i)
for _i in range(9):
    SCANCODE_TO_DOM[30 + _i] = "Digit%d" % (_i + 1)
SCANCODE_TO_DOM[39] = "Digit0"
for _i in range(12):
    SCANCODE_TO_DOM[58 + _i] = "F%d" % (_i + 1)
for _i in range(9):
    SCANCODE_TO_DOM[89 + _i] = "Numpad%d" % (_i + 1)


def vpinfe_button_index(binding: Binding, devices=None) -> str:
    """Index de bouton tel que le navigateur (joydev) le numérote, à partir
    d'un binding VPX (index SDL). Identique sauf si le périphérique expose
    des touches < BTN_MISC (SDL les numérote en dernier, joydev les ignore)."""
    if binding.is_key() or binding.is_axis() or binding.is_hat():
        return ""
    ids = joystick_setting_ids(devices if devices is not None else _safe_list_devices())
    for dev_path, (sid, _name) in ids.items():
        if sid != binding.device:
            continue
        dev = next(d for d in (devices if devices is not None else _safe_list_devices()) if d.path == dev_path)
        order = dev.button_order()
        if binding.code >= len(order):
            return str(binding.code)
        code = order[binding.code]
        joydev = [i for i in order if i >= BTN_MISC]
        return str(joydev.index(code)) if code in joydev else ""
    return str(binding.code)


def vpinfe_values(mappings: dict, policy: dict | None = None, devices=None) -> dict:
    """Pour chaque fonction VPinFE : {'action', 'joy', 'keys', 'notes'}."""
    policy = dict(VPINFE_DEFAULT_POLICY, **(policy or {}))
    devices = devices if devices is not None else _safe_list_devices()
    out = {}
    for fn, _label in VPINFE_FUNCTIONS:
        action = policy.get(fn, "") or ""
        joy, notes = "", []
        keys = [k.strip() for k in VPINFE_KEY_DEFAULTS.get(fn, "").split(",") if k.strip()]
        if action:
            try:
                alts = parse_mapping(mappings.get(action, ACTION_DEFAULTS.get(action, "")))
            except ValueError:
                alts, notes = [], ["mapping VPX invalide"]
            for alt in alts:
                if len(alt) != 1:
                    notes.append("combinaison de touches ignorée (VPinFE ne les gère pas)")
                    continue
                b = alt[0]
                if b.is_key():
                    dom = SCANCODE_TO_DOM.get(b.code)
                    if dom and dom.lower() not in [k.lower() for k in keys]:
                        keys.append(dom)
                    elif not dom:
                        notes.append("touche %s sans nom DOM connu" % scancode_label(b.code))
                elif b.is_axis() or b.is_hat():
                    notes.append("axe/chapeau non exprimable pour VPinFE (bouton attendu)")
                elif not joy:
                    joy = vpinfe_button_index(b, devices)
        out[fn] = {"action": action, "joy": joy, "keys": ",".join(keys), "notes": notes}
    return out


def write_vpinfe(values: dict, path=None, backup: bool = True) -> dict:
    ini = VpxIni(path or VPINFE_INI)
    for fn, v in values.items():
        ini.set(INPUT_SECTION, "joy" + fn, v.get("joy", ""))
        ini.set(INPUT_SECTION, "key" + fn, v.get("keys", ""))
    backup_path = ""
    if backup and ini.path.exists():
        bdir = BACKUP_DIR
        bdir.mkdir(parents=True, exist_ok=True)
        backup_path = str(bdir / ("vpinfe.ini.backup-map-commander-" + datetime.now().strftime("%Y%m%d-%H%M%S")))
        shutil.copy2(ini.path, backup_path)
    ini.save(backup=False)
    return {"path": str(ini.path), "backup": backup_path}


def vpinfe_current(path=None) -> dict:
    ini = VpxIni(path or VPINFE_INI)
    return {fn: {"joy": ini.get(INPUT_SECTION, "joy" + fn) or "", "keys": ini.get(INPUT_SECTION, "key" + fn) or ""}
            for fn, _ in VPINFE_FUNCTIONS}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
USAGE = """usage : pincabos-vpx-input devices | show [--json] | detect [--timeout S] [--json]
                            | set <Action> "<mapping>" | defaults | purge-legacy | vpinfe-sync
  devices       périphériques evdev vus comme SDL (GUID, id VPX, boutons, axes)
  show          mappings actifs de %s
  detect        attend un appui et affiche le binding VPX correspondant
  set           écrit Mapping.<Action> (ex. set LeftFlipper "Key;225 | SDLJoy_…_1;3")
  defaults      remet les défauts clavier VPX pour toutes les actions
  purge-legacy  retire les anciennes clés DIK de Map Commander
  vpinfe-sync   recopie les boutons VPX vers la navigation VPinFE (politique PinCabOS)
"""


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(USAGE % ini_path())
        return 0
    cmd, args = argv[0], argv[1:]
    as_json = "--json" in args
    args = [a for a in args if a != "--json"]
    if cmd == "devices":
        devices = list_devices()
        ids = joystick_setting_ids(devices)
        rows = []
        for dev in devices:
            sid, vname = ids.get(dev.path, ("", ""))
            rows.append({"path": dev.path, "name": dev.name, "joystick": dev.is_joystick, "keyboard": dev.is_keyboard,
                         "guid": dev.guid, "id": sid, "vpx_name": vname,
                         "buttons": len(dev.button_order()) if dev.is_joystick else 0,
                         "axes": len(dev.axis_order()) if dev.is_joystick else 0, "hats": len(dev.digital_hats()) if dev.is_joystick else 0})
        if as_json:
            print(json.dumps(rows, indent=2, ensure_ascii=False))
        else:
            for r in rows:
                kind = "joystick" if r["joystick"] else ("clavier" if r["keyboard"] else "autre")
                print("%-18s %-9s %s" % (r["path"], kind, r["name"]))
                if r["joystick"]:
                    print("%18s id VPX %s  (%d boutons, %d axes, %d chapeaux)" % ("", r["id"], r["buttons"], r["axes"], r["hats"]))
        return 0
    if cmd == "show":
        state = current_state()
        if as_json:
            print(json.dumps(state, indent=2, ensure_ascii=False))
            return 0
        print("ini : %s" % state["path"])
        for j in state["joysticks"]:
            print("joystick : %s  ->  %s%s" % (j["name"], j["id"], "" if j["id"] in state["declared"] else "  (pas encore déclaré dans l'ini)"))
        for a in state["actions"]:
            print("%-20s %-34s %s%s" % (a["action"], a["decoded"], a["mapping"], "" if a["present"] else "   [défaut VPX]"))
        return 0
    if cmd == "detect":
        timeout = 8.0
        if "--timeout" in args:
            timeout = float(args[args.index("--timeout") + 1])
        if not as_json:
            print("Appuie sur un bouton ou une touche (%.0f s)..." % timeout, file=sys.stderr)
        res = detect_once(timeout)
        if as_json:
            print(json.dumps(res, ensure_ascii=False))
        elif not res:
            print("rien détecté")
        elif "error" in res:
            print("erreur : %s" % res["error"])
        else:
            print("%s   (%s ; %s)" % (res["binding"], res["label"], res["raw"]))
        return 0 if res and "error" not in res else 1
    if cmd == "set" and len(args) == 2:
        res = write_mappings({args[0]: args[1]})
        print("écrit : Mapping.%s = %s  (%s)" % (args[0], res["mappings"][args[0]], res["path"]))
        return 0
    if cmd == "defaults":
        res = write_mappings(dict(ACTION_DEFAULTS))
        print("défauts VPX écrits dans %s (sauvegarde %s)" % (res["path"], res["backup"] or "aucune"))
        return 0
    if cmd == "purge-legacy":
        ini = VpxIni(ini_path())
        n = ini.purge_legacy()
        if n:
            ini.save()
        print("%d ligne(s) retirée(s) de %s" % (n, ini.path))
        return 0
    if cmd == "vpinfe-sync":
        state = current_state()
        mappings = {a["action"]: a["mapping"] for a in state["actions"]}
        values = vpinfe_values(mappings)
        res = write_vpinfe(values)
        for fn, v in values.items():
            print("%-15s <- %-18s joy=%-3s keys=%s%s" % (fn, v["action"] or "-", v["joy"] or "-", v["keys"], ("  ! " + " ; ".join(v["notes"])) if v["notes"] else ""))
        print("écrit dans %s (sauvegarde %s) — redémarrer VPinFE pour appliquer" % (res["path"], res["backup"] or "aucune"))
        return 0
    print(USAGE % ini_path(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
