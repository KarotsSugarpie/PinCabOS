# PinCabOS WebApp module: Audio / SSF V2, ALSA, PipeWire and SSF Commander.
# Generated from the monolithic app.py refactor.
# The host app injects legacy shared helpers during register().
from __future__ import annotations

import glob
import html
import json
import os
import re
import shlex
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import zipfile
from datetime import datetime
from pathlib import Path

from flask import jsonify, redirect, request, send_file, session, url_for

ROUTES: list[tuple[str, dict, object]] = []
BEFORE_REQUESTS: list[object] = []
AFTER_REQUESTS: list[object] = []

def route(rule: str, **options):
    """Record a Flask route locally; register() attaches it to the host app."""
    def decorator(func):
        ROUTES.append((rule, options, func))
        return func
    return decorator

def before_request(func):
    BEFORE_REQUESTS.append(func)
    return func

def after_request(func):
    AFTER_REQUESTS.append(func)
    return func

def register(host_app, runtime_globals: dict):
    """Bind shared helpers once, then register module-owned routes unchanged."""
    protected = {'ROUTES', 'route', 'register', '__name__', '__file__', '__package__'}
    for key, value in runtime_globals.items():
        if key not in protected:
            globals()[key] = value
    # Publish moved helpers back to the host namespace for legacy core pages that
    # still call them (for example page() -> firstrun_load_cfg()).
    prefixes = ("audio_", "ssf_", "inputs_", "firstrun_", "pincabos_", "PINCABOS_", "AUDIO_")
    for key, value in list(globals().items()):
        if key.startswith(prefixes):
            runtime_globals[key] = value
    for before_func in BEFORE_REQUESTS:
        host_app.before_request(before_func)
    for after_func in AFTER_REQUESTS:
        host_app.after_request(after_func)
    for rule, options, view_func in ROUTES:
        host_app.add_url_rule(rule, endpoint=view_func.__name__, view_func=view_func, **options)



AUDIO_ROUTER_CONFIG = Path("/opt/pincabos/config/audio-router.json")


AUDIO_ROUTER_DEFAULT_CONFIG = {
    "audio_mode": "dual",
    "audio_backend": "alsa",
    "backbox_device": "",
    "playfield_device": "",
    "surround_device": "",
    "bass_device": "",
    "ssf_mode": "7.1",
    "invert_lr": False,
    "invert_front_rear": False,
    "enable_bass": True,
    "night_mode": False
}


def audio_run_cmd(cmd, timeout=5):
    try:
        r = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return (r.stdout or "").strip()
    except Exception as e:
        return str(e)


def audio_load_config():
    cfg = AUDIO_ROUTER_DEFAULT_CONFIG.copy()

    if not AUDIO_ROUTER_CONFIG.exists():
        return cfg

    try:
        data = json.loads(AUDIO_ROUTER_CONFIG.read_text(errors="replace"))
        if isinstance(data, dict):
            cfg.update(data)
    except Exception:
        pass

    return cfg


def audio_save_config(cfg):
    pincabos_backup_config_file(AUDIO_ROUTER_CONFIG, "Audio / SSF V2 Save")
    pincabos_write_json_with_meta(AUDIO_ROUTER_CONFIG, cfg, "Audio / SSF V2 Save")


def audio_detect_alsa_devices():
    """
    Détection ALSA robuste pour PinCabOS.

    Supporte Ubuntu en anglais et en français:
      - anglais  : card X: NAME [LONG], device Y: DEV [LONGDEV]
      - français : carte X : NAME [LONG], périphérique Y : DEV [LONGDEV]

    Important:
    On force LC_ALL=C pour essayer d'obtenir une sortie anglaise stable.
    Si Ubuntu retourne quand même une sortie française, le regex FR la supporte.
    """
    devices = []
    output = audio_run_cmd("LC_ALL=C aplay -l 2>/dev/null || aplay -l 2>/dev/null || true")

    rx = re.compile(
        r"^(?:card|carte)\s+(\d+)\s*:\s*"
        r"(.+?)\s+\[(.+?)\]\s*,\s*"
        r"(?:device|périphérique|peripherique)\s+(\d+)\s*:\s*"
        r"(.+?)\s+\[(.+?)\]",
        re.IGNORECASE
    )

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        m = rx.match(line)
        if not m:
            continue

        card_num = m.group(1).strip()
        card_short = m.group(2).strip()
        card_name = m.group(3).strip()
        device_num = m.group(4).strip()
        device_short = m.group(5).strip()
        device_name = m.group(6).strip()

        devices.append({
            "id": f"hw:{card_num},{device_num}",
            "card": card_num,
            "device": device_num,
            "name": f"{card_name} / {device_name}",
            "description": f"{card_short} / {device_short}",
        })

    return devices, output


def audio_device_options(selected):
    devices, _raw = audio_detect_alsa_devices()
    rows = ['<option value="">Non configuré</option>']

    for dev in devices:
        dev_id = dev["id"]
        label = f'{dev["name"]} — {dev_id}'
        sel = "selected" if selected == dev_id else ""
        rows.append(f'<option value="{esc(dev_id)}" {sel}>{esc(label)}</option>')

    return "\n".join(rows)


def audio_bool_checked(cfg, key):
    return "checked" if cfg.get(key) else ""


def audio_selected(cfg, key, value):
    return "selected" if cfg.get(key) == value else ""


# PINCABOS_AUDIO_SSF_VPX_ROUTING_V2
PINCABOS_VPX_AUDIO_INI = Path(
    "/home/pinball/.local/share/VPinballX/10.8/VPinballX.ini"
)


def _pco_vpx_audio_values():
    path = str(PINCABOS_VPX_AUDIO_INI)

    return {
        key: (
            audio_ini_read_key(
                path,
                "Player",
                key,
            )
            or ""
        ).strip()
        for key in (
            "SoundDeviceBG",
            "SoundDevice",
            "Sound3D",
            "PlayMusic",
            "PlaySound",
            "MusicVolume",
            "SoundVolume",
        )
    }


def _pco_vpx_detect_output_names():
    import os as _os
    import subprocess as _subprocess

    values = _pco_vpx_audio_values()

    found = []
    seen = set()

    def add(value):
        value = str(value or "").strip()

        if (
            not value
            or "\n" in value
            or "\r" in value
        ):
            return

        folded = value.casefold()

        if folded in seen:
            return

        seen.add(folded)
        found.append(value)

    # Les valeurs déjà inscrites dans VPinballX.ini
    # restent toujours sélectionnables.
    add(values.get("SoundDeviceBG"))
    add(values.get("SoundDevice"))

    env = _os.environ.copy()

    env["XDG_RUNTIME_DIR"] = "/run/user/1000"
    env["DBUS_SESSION_BUS_ADDRESS"] = (
        "unix:path=/run/user/1000/bus"
    )

    try:
        result = _subprocess.run(
            [
                "/usr/bin/pactl",
                "list",
                "sinks",
            ],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
            env=env,
        )

        for raw_line in result.stdout.splitlines():
            line = raw_line.strip()

            if line.startswith("Description:"):
                add(line.split(":", 1)[1])

    except Exception:
        pass

    return found


def _pco_vpx_device_options(selected):
    selected = str(selected or "").strip()
    devices = _pco_vpx_detect_output_names()

    if selected and selected not in devices:
        devices.insert(0, selected)

    rows = [
        '<option value=""'
        + (" selected" if not selected else "")
        + ">Périphérique par défaut de VPX</option>"
    ]

    for device in devices:
        rows.append(
            f'<option value="{esc(device)}"'
            f'{" selected" if device == selected else ""}>'
            f'{esc(device)}</option>'
        )

    return "".join(rows)


def _pco_vpx_sound3d_options(selected):
    selected = str(selected or "0").strip()

    if selected not in {"0", "1", "2", "3", "4", "5"}:
        selected = "0"

    # PINCABOS_SOUND3D_LABELS_V1
    # Intitules repris de VPinball : les modes 4 et 5 sont des modes a SIX
    # canaux, pas du 7.1. Les annoncer en 7.1 fait passer un fonctionnement
    # normal pour une panne.
    modes = (
        (
            "0",
            "2 canaux — avant",
        ),
        (
            "1",
            "2 canaux — arrière",
        ),
        (
            "2",
            "Jusqu'à 6 canaux — arrière au lockbar",
        ),
        (
            "3",
            "Jusqu'à 6 canaux — avant au lockbar",
        ),
        (
            "4",
            "6 canaux — latéral et arrière au lockbar, mixage historique",
        ),
        (
            "5",
            "6 canaux — latéral et arrière au lockbar, nouveau mixage",
        ),
    )

    return "".join(
        f'<option value="{value}"'
        f'{" selected" if value == selected else ""}>'
        f'{esc(label)} — Sound3D={value}</option>'
        for value, label in modes
    )


def _pco_vpx_mode_from_sound3d(value):
    value = str(value or "0").strip()

    if value in {"2", "3"}:
        return "5.1"

    if value in {"4", "5"}:
        return "7.1"

    return "individual"


def _pco_vpx_validate_device(value):
    value = str(value or "").strip()

    if "\n" in value or "\r" in value:
        raise ValueError(
            "Nom de périphérique audio invalide."
        )

    if len(value) > 240:
        raise ValueError(
            "Nom de périphérique audio trop long."
        )

    available = set(
        _pco_vpx_detect_output_names()
    )

    if value and value not in available:
        raise ValueError(
            "Périphérique VPX/PipeWire non détecté : "
            + value
        )

    return value


def _pco_vpx_validate_sound3d(value):
    value = str(value or "0").strip()

    if value not in {"0", "1", "2", "3", "4", "5"}:
        raise ValueError(
            "Valeur [Player] Sound3D invalide : "
            + value
        )

    return value


def _pco_vpx_write_audio(
    backglass,
    playfield,
    sound3d,
):
    import os as _os

    path = PINCABOS_VPX_AUDIO_INI

    if not path.is_file():
        raise FileNotFoundError(
            f"VPinballX.ini absent : {path}"
        )

    backglass = _pco_vpx_validate_device(
        backglass
    )

    playfield = _pco_vpx_validate_device(
        playfield
    )

    sound3d = _pco_vpx_validate_sound3d(
        sound3d
    )

    backup = audio_backup_file(path)

    if backup is None:
        raise RuntimeError(
            "Sauvegarde de VPinballX.ini impossible."
        )

    lines = audio_read_lines(path)

    lines = audio_set_ini_key_with_comment(
        lines,
        "Player",
        "SoundDeviceBG",
        backglass,
        "Audio SSF VPX Routing V2",
    )

    lines = audio_set_ini_key_with_comment(
        lines,
        "Player",
        "SoundDevice",
        playfield,
        "Audio SSF VPX Routing V2",
    )

    lines = audio_set_ini_key_with_comment(
        lines,
        "Player",
        "Sound3D",
        sound3d,
        "Audio SSF VPX Routing V2",
    )

    audio_write_lines(path, lines)

    try:
        _os.chown(path, 1000, 1000)
        _os.chmod(path, 0o644)
    except OSError:
        pass

    expected = {
        "SoundDeviceBG": backglass,
        "SoundDevice": playfield,
        "Sound3D": sound3d,
    }

    for key, wanted in expected.items():
        actual = (
            audio_ini_read_key(
                str(path),
                "Player",
                key,
            )
            or ""
        ).strip()

        if actual != wanted:
            raise RuntimeError(
                f"Validation {key} échouée : "
                f"attendu={wanted!r}, "
                f"obtenu={actual!r}"
            )

    return [
        f"Backup VPX : {backup}",
        (
            "[Player] SoundDeviceBG = "
            + (backglass or "(défaut VPX)")
        ),
        (
            "[Player] SoundDevice = "
            + (playfield or "(défaut VPX)")
        ),
        f"[Player] Sound3D = {sound3d}",
    ]


def audio_config_rows():
    cfg = audio_load_config()
    values = _pco_vpx_audio_values()

    backglass = values.get(
        "SoundDeviceBG",
        "",
    )

    playfield = values.get(
        "SoundDevice",
        "",
    )

    sound3d = values.get(
        "Sound3D",
        "0",
    )

    legacy_rows = []

    # PINCABOS_AUDIO_DEAD_ROWS_V1
    # Les cles d'un routage audio anterieur ne sont plus affichees : rien ne
    # les lit, et posees au milieu des vrais reglages elles se lisaient comme
    # des reglages. « Mode nuit », elle, a de vrais consommateurs.
    for label, key in (
        (
            "Mode nuit",
            "night_mode",
        ),
    ):
        legacy_rows.append(
            f"<tr><td>{esc(label)}</td>"
            f"<td><code>"
            f"{esc(cfg.get(key, '-'))}"
            f"</code></td></tr>"
        )

    return f"""
<tr>
  <td>
    <strong>Backglass / ROM / musique</strong><br>
    <small>
      <code>[Player] SoundDeviceBG</code>
    </small>
  </td>
  <td>
    <select
      name="backbox_device"
      style="width:100%;max-width:720px;padding:8px;"
    >
      {_pco_vpx_device_options(backglass)}
    </select>
  </td>
</tr>

<tr>
  <td>
    <strong>Underplayfield / SoundFX / SSF</strong><br>
    <small>
      <code>[Player] SoundDevice</code>
    </small>
  </td>
  <td>
    <select
      name="playfield_device"
      style="width:100%;max-width:720px;padding:8px;"
    >
      {_pco_vpx_device_options(playfield)}
    </select>
  </td>
</tr>

<tr>
  <td>
    <strong>Mode de sortie VPX</strong><br>
    <small>
      <code>[Player] Sound3D</code>
    </small>
  </td>
  <td>
    <select
      name="sound3d"
      style="width:100%;max-width:720px;padding:8px;"
    >
      {_pco_vpx_sound3d_options(sound3d)}
    </select>
  </td>
</tr>

{''.join(legacy_rows)}
"""

def audio_test_device(device_id, channels=2):
    if not device_id:
        return

    cmd = f"speaker-test -D {shlex_quote(device_id)} -c {int(channels)} -t wav -l 1"
    subprocess.Popen(
        cmd,
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def audio_backup_file(src):
    if not src.exists():
        return None

    AUDIO_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = AUDIO_BACKUP_DIR / f"{src.name}.backup-{stamp}"
    shutil.copy2(src, dst)
    return dst


def audio_comment(function_name):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"; Modifié {stamp} par PinCabOS fonction({function_name})"


def audio_read_lines(path):
    if path.exists():
        return path.read_text(errors="replace").splitlines()
    return []


def audio_write_lines(path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n")


def audio_find_section(lines, section):
    section_header = f"[{section}]"
    start = None
    end = len(lines)

    for i, line in enumerate(lines):
        if line.strip().lower() == section_header.lower():
            start = i
            break

    if start is None:
        return None, None

    for j in range(start + 1, len(lines)):
        stripped = lines[j].strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            end = j
            break

    return start, end


def audio_set_ini_key_with_comment(lines, section, key, value, function_name):
    """
    Modifie une clé INI en conservant la structure existante.
    Ajoute toujours un commentaire timestamp juste au-dessus de la clé modifiée.
    """
    comment = audio_comment(function_name)
    start, end = audio_find_section(lines, section)

    if start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(comment)
        lines.append(f"[{section}]")
        lines.append(f"{key} = {value}")
        return lines

    key_lower = key.lower()
    key_index = None

    for i in range(start + 1, end):
        stripped = lines[i].strip()
        if not stripped or stripped.startswith("#") or stripped.startswith(";"):
            continue

        if "=" in stripped:
            existing_key = stripped.split("=", 1)[0].strip().lower()
            if existing_key == key_lower:
                key_index = i
                break

    if key_index is not None:
        # Retire uniquement l'ancien commentaire PinCabOS directement au-dessus,
        # pour éviter d'empiler 50 timestamps sur la même clé.
        if key_index > 0 and "par PinCabOS fonction(" in lines[key_index - 1]:
            lines[key_index - 1] = comment
        else:
            lines.insert(key_index, comment)
            key_index += 1

        lines[key_index] = f"{key} = {value}"
        return lines

    # Clé absente : ajoute en fin de section.
    insert_at = end
    lines.insert(insert_at, comment)
    lines.insert(insert_at + 1, f"{key} = {value}")
    return lines


def audio_set_pincabos_section(lines, section, values, function_name):
    """
    Section de suivi PinCabOS.
    Toutes les lignes écrites ont un commentaire timestamp avant le bloc.
    """
    comment = audio_comment(function_name)
    start, end = audio_find_section(lines, section)

    block = [comment, f"[{section}]"]
    for key, value in values.items():
        block.append(f"{key} = {value}")

    if start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(block)
        return lines

    # Remplace seulement la section PinCabOS dédiée.
    return lines[:start] + block + lines[end:]


def audio_vpx_sound3d_value(ssf_mode):
    """
    VPX possède Sound3D dans [Player].
    On garde une logique prudente :
    - off / 2.1 = 0
    - 4.1 / 5.1 / 7.1 = 1
    """
    ssf_mode = str(ssf_mode or "").strip().lower()
    if ssf_mode in ["4.1", "5.1", "7.1"]:
        return "1"
    return "0"


def audio_apply_to_vpx_vpinfe():
    """
    Application audio safe.

    Important:
      - on ne force plus SoundDevice/SoundDeviceBG/MusicDevice/Sound3DDevice avec hw:X,Y,
        car VPX semble utiliser des IDs numériques dans [Player].
      - on garde audio-router.json comme source UI PinCabOS.
      - on applique seulement VPinFE [Settings] muteaudio=false.
      - aucune section PinCabOS.Audio n'est créée.
    """
    results = []

    vpinfe_ini = AUDIO_VPINFE_INI
    vpinfe_home_ini = PINCABOS_VPINFE_INI

    def set_ini_key_native(lines, section, key, value):
        section_header = f"[{section}]"
        section_l = section.lower()
        key_l = key.lower()

        out = []
        in_section = False
        section_found = False
        key_written = False

        for line in lines:
            stripped = line.strip()

            if stripped.startswith("[") and stripped.endswith("]"):
                if in_section and not key_written:
                    out.append(f"{key} = {value}\n")
                    key_written = True

                in_section = stripped[1:-1].strip().lower() == section_l
                if in_section:
                    section_found = True

                out.append(line)
                continue

            if in_section and "=" in stripped:
                left = stripped.split("=", 1)[0].strip().lower()
                if left == key_l:
                    out.append(f"{key} = {value}\n")
                    key_written = True
                    continue

            out.append(line)

        if section_found and in_section and not key_written:
            out.append(f"{key} = {value}\n")

        if not section_found:
            out.append(f"\n{section_header}\n")
            out.append(f"{key} = {value}\n")

        return out

    results.append("VPX: SoundDevice/SoundDeviceBG/MusicDevice/Sound3DDevice non modifiés automatiquement.")
    results.append("Raison: VPX semble utiliser des IDs numériques dans [Player], pas hw:X,Y ALSA.")

    for ini in [vpinfe_ini, vpinfe_home_ini]:
        try:
            if not ini.exists():
                results.append(f"VPinFE absent: {ini}")
                continue

            audio_backup_file(ini)
            lines = audio_read_lines(ini)
            lines = set_ini_key_native(lines, "Settings", "muteaudio", "false")
            audio_write_lines(ini, lines)
            subprocess.run(["/bin/chown", "pinball:pinball", str(ini)], timeout=5)
            results.append(f"VPinFE [Settings] muteaudio = false dans {ini}")
        except Exception as e:
            results.append(f"ERREUR VPinFE native audio {ini}: {e}")

    try:
        log_path = Path("/opt/pincabos/logs/audio-ssf-apply.log")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("\n".join(results) + "\n", encoding="utf-8")
    except Exception:
        pass

    return results


def pincabos_safe_audio_alsa_card():
    try:
        return audio_alsa_test_card()
    except Exception as e:
        return f"""
<div class="card pco-audio-compact-card">
  <h2>Test audio ALSA rapide</h2>
  <p class="warn">Carte ALSA indisponible: {esc(str(e))}</p>
</div>
"""


def audio_alsa_test_card():
    devices, raw = audio_detect_alsa_devices()
    options = []

    for d in devices:
        hw = str(d.get("id", "") or "")
        card = str(d.get("card", "") or "")
        dev = str(d.get("device", "") or "")
        name = str(d.get("name", hw) or hw)
        desc = str(d.get("description", "") or "")

        plug = f"plughw:{card},{dev}" if card != "" and dev != "" else hw
        label = f"{name} — {desc} — {plug} recommandé"
        options.append(f'<option value="{esc(plug)}">{esc(label)}</option>')

    if not options:
        options.append('<option value="">Aucun périphérique ALSA détecté</option>')

    raw_html = esc(raw or "")

    return f"""
<div class="card pco-audio-compact-card" id="pincabos-alsa-test-card">
  <h2>Test audio ALSA rapide</h2>
  <p>
    Cette carte liste les sorties ALSA et lance un test court avec <code>speaker-test</code>.
    Utilise d’abord <code>plughw:X,Y</code>, plus compatible que <code>hw:X,Y</code>.
  </p>

  <table style="width:100%;">
    <tr>
      <td style="width:150px;">Périphérique ALSA</td>
      <td>
        <select name="device" style="width:100%;max-width:520px;padding:7px;">
          {''.join(options)}
        </select>
      </td>
    </tr>
    <tr>
      <td>Canaux</td>
      <td>
        <select name="channels" style="padding:7px;">
          <option value="2">2 canaux stéréo</option>
          <option value="4">4 canaux</option>
          <option value="6">6 canaux / 5.1</option>
          <option value="8">8 canaux / 7.1</option>
        </select>
      </td>
    </tr>
  </table>

  <form method="post" action="/audio-ssf/test-alsa-quick" target="pco-alsa-action-frame">
    <input type="hidden" name="device" id="pco-alsa-hidden-device" value="">
    <input type="hidden" name="channels" id="pco-alsa-hidden-channels" value="2">
    <p style="margin:6px 0 8px 0;">
      <button class="button" type="submit"
        onclick="
          const card=this.closest('.card');
          document.getElementById('pco-alsa-hidden-device').value=card.querySelector('select[name=device]').value;
          document.getElementById('pco-alsa-hidden-channels').value=card.querySelector('select[name=channels]').value;
        ">
        Tester 2 secondes
      </button>
      <a class="button secondary" href="/audio-ssf">Rafraîchir la page</a>
    </p>
  </form>

  <p><small>Si <code>hw:X,Y</code> retourne <code>Bad address</code>, essaie le même périphérique en <code>plughw:X,Y</code>.</small></p>

  <details style="margin-top:8px;" open>
    <summary>Log test audio</summary>
    <iframe name="pco-alsa-action-frame"
            style="width:100%;height:150px;background:rgba(0,0,0,.45);border:1px solid rgba(255,176,0,.25);border-radius:12px;"></iframe>
  </details>

  <details style="margin-top:8px;">
    <summary>Voir sortie brute <code>aplay -l</code></summary>
    <pre style="white-space:pre-wrap;max-height:260px;overflow:auto;background:rgba(0,0,0,.45);border:1px solid rgba(255,176,0,.25);border-radius:12px;padding:10px;">{raw_html}</pre>
  </details>
</div>
"""


def audio_wav_test_card():
    wav_dirs = [
        Path("/opt/pincabos/media/audio-tests"),
        Path("/opt/pincabos/media"),
        Path("/home/pinball/Share"),
    ]

    wav_files = []
    seen = set()

    for base in wav_dirs:
        try:
            if not base.exists() or not base.is_dir():
                continue
            for f in base.rglob("*"):
                if not f.is_file():
                    continue
                if f.suffix.lower() not in [".wav", ".wave"]:
                    continue
                real = str(f.resolve())
                if real in seen:
                    continue
                seen.add(real)
                wav_files.append(f.resolve())
        except Exception:
            continue

    wav_files = sorted(wav_files, key=lambda x: x.name.lower())

    wav_options = []
    for f in wav_files:
        label = f.name
        try:
            label = str(f.relative_to("/opt/pincabos/media"))
        except Exception:
            pass
        wav_options.append(f'<option value="{esc(str(f))}">{esc(label)}</option>')

    if not wav_options:
        wav_options.append('<option value="">Aucun fichier WAV installé</option>')

    devices, _raw = audio_detect_alsa_devices()
    device_options = []

    for d in devices:
        hw = str(d.get("id", "") or "")
        card = str(d.get("card", "") or "")
        dev = str(d.get("device", "") or "")
        name = str(d.get("name", hw) or hw)
        desc = str(d.get("description", "") or "")
        plug = f"plughw:{card},{dev}" if card != "" and dev != "" else hw
        selected = " selected" if plug == "plughw:2,0" else ""
        label = f"{name} — {desc} — {plug}"
        device_options.append(f'<option value="{esc(plug)}"{selected}>{esc(label)}</option>')

    if not device_options:
        device_options.append('<option value="">Aucune sortie ALSA détectée</option>')

    return f"""
<div class="card pco-audio-compact-card" id="pincabos-wav-test-card">
  <h2>Tests WAV PinCabOS</h2>
  <p>Tests WAV : bass shaker, sweep basses fréquences, gauche/droite et test 4 canaux.</p>

  <form id="pco-wav-real-form" method="post" target="pco-audio-action-frame">
    <table style="width:100%;margin-bottom:8px;">
      <tr>
        <td style="width:150px;">Fichier WAV</td>
        <td>
          <select name="wav_file" id="pco-real-wav-file" style="width:100%;max-width:520px;padding:7px;">
            {''.join(wav_options)}
          </select>
        </td>
      </tr>
      <tr>
        <td>Sortie ALSA</td>
        <td>
          <select name="device" id="pco-real-wav-device" style="width:100%;max-width:520px;padding:7px;">
            {''.join(device_options)}
          </select>
        </td>
      </tr>
    </table>

    <p style="margin:6px 0 8px 0;">
      <button class="button" type="submit" formaction="/audio-ssf/test-wav" formmethod="post">Jouer le WAV</button>
      <button class="button secondary" type="submit" formaction="/audio-ssf/test-wav-stop" formmethod="post">Stop audio</button>
    </p>

    <div class="pco-inline-volume"
         style="margin:8px 0;padding:8px;border:1px solid rgba(255,176,0,.22);border-radius:10px;background:rgba(0,0,0,.12);">
      <div style="font-weight:700;margin-bottom:6px;font-size:13px;">Volume / balance</div>

      <div style="display:grid;grid-template-columns:minmax(250px,1fr) 220px;gap:10px;align-items:start;">
        <div>
          <div style="display:grid;grid-template-columns:68px 150px 76px;gap:5px;align-items:center;font-size:11px;margin-bottom:5px;">
            <label>Volume</label>
            <input name="volume" id="pco-real-volume" type="range" min="0" max="100" value="70"
                   style="width:150px;margin:0;"
                   oninput="document.getElementById('pco-real-volume-val').textContent=this.value">
            <strong>&nbsp;&nbsp;&nbsp;<span id="pco-real-volume-val">70</span>%</strong>

            <label>Balance</label>
            <input name="balance" id="pco-real-balance" type="range" min="-100" max="100" value="0"
                   style="width:150px;margin:0;"
                   oninput="document.getElementById('pco-real-balance-val').textContent=(this.value==0?'centre':(this.value<0?'G '+Math.abs(this.value)+'%':'D '+this.value+'%'))">
            <strong>&nbsp;&nbsp;&nbsp;<span id="pco-real-balance-val">centre</span></strong>
          </div>

          <button class="button" type="submit" formaction="/audio-ssf/system-volume/apply" formmethod="post" style="padding:4px 8px;font-size:11px;">
            Appliquer
          </button>
          <button class="button secondary" type="submit" formaction="/audio-ssf/system-volume/get" formmethod="get" style="padding:4px 8px;font-size:11px;">
            Lire état
          </button>
        </div>
      </div>
    </div>
  </form>

  <details style="margin-top:8px;" open>
    <summary>Résultat des boutons</summary>
    <iframe name="pco-audio-action-frame"
            id="pco-audio-action-frame"
            style="width:100%;height:170px;background:rgba(0,0,0,.45);border:1px solid rgba(255,176,0,.25);border-radius:12px;color:white;"></iframe>
  </details>
</div>
"""


def audio_ini_read_key(path, section, key):
    """
    Lecture simple INI, sans modification.
    Retourne la valeur d'une clef dans une section.
    """
    p = Path(path)
    if not p.exists():
        return None

    current = None
    section_l = str(section).strip().lower()
    key_l = str(key).strip().lower()

    try:
        for line in p.read_text(errors="replace").splitlines():
            s = line.strip()

            if not s or s.startswith("#") or s.startswith(";"):
                continue

            if s.startswith("[") and s.endswith("]"):
                current = s[1:-1].strip().lower()
                continue

            if current == section_l and "=" in s:
                left, right = s.split("=", 1)
                if left.strip().lower() == key_l:
                    return right.strip()
    except Exception as e:
        return f"ERREUR lecture: {e}"

    return None


def audio_ini_value_cell(value):
    if value is None:
        return '<span class="warn">non trouvé</span>'
    if str(value).strip() == "":
        return '<span class="warn">vide</span>'
    return f'<code>{esc(str(value))}</code>'


def audio_ini_values_card():
    values = _pco_vpx_audio_values()

    rows = []

    for key, description in (
        (
            "SoundDeviceBG",
            "Backglass / ROM / musique",
        ),
        (
            "SoundDevice",
            "Underplayfield / SoundFX / SSF",
        ),
        (
            "Sound3D",
            "Mode de sortie VPX",
        ),
        (
            "PlayMusic",
            "Backglass / ROM activé",
        ),
        (
            "PlaySound",
            "SoundFX / playfield activé",
        ),
        (
            "MusicVolume",
            "Volume backglass",
        ),
        (
            "SoundVolume",
            "Volume playfield",
        ),
    ):
        rows.append(
            "<tr>"
            f"<td>{esc(description)}</td>"
            f"<td><code>[Player] {esc(key)}</code></td>"
            f"<td>"
            f"{audio_ini_value_cell(values.get(key))}"
            f"</td>"
            "</tr>"
        )

    muteaudio = audio_ini_read_key(
        "/home/pinball/.config/vpinfe/vpinfe.ini",
        "Settings",
        "muteaudio",
    )

    return f"""
<div
  class="card pco-audio-compact-card"
  id="pincabos-audio-ini-values-card"
>
  <h2>Valeurs audio réellement actives</h2>

  <p>
    Lecture directe de
    <code>{esc(str(PINCABOS_VPX_AUDIO_INI))}</code>
  </p>

  <table>
    <tr>
      <th>Fonction</th>
      <th>Clé exacte</th>
      <th>Valeur</th>
    </tr>
    {''.join(rows)}
  </table>

  <p>
    VPinFE :
    <code>[Settings] muteaudio</code>
    = {audio_ini_value_cell(muteaudio)}
  </p>
</div>
"""

def audio_system_run(cmd, timeout=8):
    # Keep PipeWire / Pulse commands functional when the WebApp runs as root.
    env = os.environ.copy()
    env.setdefault("XDG_RUNTIME_DIR", "/run/user/1000")
    try:
        r = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            timeout=timeout,
            env=env,
        )
        return r.returncode, (r.stdout or ""), (r.stderr or "")
    except Exception as e:
        return 99, "", str(e)


def audio_parse_alsa_hw(device):
    """
    Accepte hw:X,Y ou plughw:X,Y.
    Retourne (card, device) ou ("","").
    """
    import re
    m = re.search(r"(?:plug)?hw:(\d+),(\d+)", str(device or ""))
    if not m:
        return "", ""
    return m.group(1), m.group(2)


def audio_pactl_find_sink_for_alsa_card(card):
    """
    Trouve un sink PipeWire/PulseAudio correspondant à alsa.card = X.
    Important: pactl doit être lancé comme user pinball avec XDG_RUNTIME_DIR.
    """
    if str(card).strip() == "":
        return ""

    cmd = [
        "runuser", "-u", "pinball", "--",
        "bash", "-lc",
        "export XDG_RUNTIME_DIR=/run/user/1000; pactl list sinks 2>/dev/null"
    ]

    rc, out, err = audio_system_run(cmd, timeout=6)
    if rc != 0 or not out.strip():
        return ""

    current_name = ""
    current_card = ""

    for line in out.splitlines():
        s = line.strip()

        if s.startswith("Name:"):
            current_name = s.split(":", 1)[1].strip()
            current_card = ""

        if "alsa.card =" in s:
            current_card = s.split("=", 1)[1].strip().strip('"')

        if current_name and current_card == str(card):
            return current_name

    return ""


def audio_system_volume_get(device=""):
    """
    Lecture best-effort du volume système pour le périphérique choisi.
    """
    card, dev = audio_parse_alsa_hw(device)
    out = []

    out.append(f"Périphérique demandé: {device or 'défaut'}")
    if card != "":
        out.append(f"Carte ALSA ciblée: card {card}, device {dev}")

    sink = audio_pactl_find_sink_for_alsa_card(card) if card != "" else ""
    if sink:
        out.append(f"Sink pactl correspondant: {sink}")
        rc, stdout, stderr = audio_system_run(["bash", "-lc", f"pactl get-sink-volume {sink} 2>/dev/null | head -n1"])
        if rc == 0 and stdout.strip():
            out.append("pactl:")
            out.append(stdout.strip())
    else:
        rc, stdout, stderr = audio_system_run(["bash", "-lc", "pactl get-sink-volume @DEFAULT_SINK@ 2>/dev/null | head -n1"])
        if rc == 0 and stdout.strip():
            out.append("pactl default:")
            out.append(stdout.strip())

    if card != "":
        rc2, stdout2, stderr2 = audio_system_run(["bash", "-lc", f"amixer -c {card} get Master 2>/dev/null | sed -n '1,10p'"])
        if rc2 == 0 and stdout2.strip():
            out.append("amixer Master:")
            out.append(stdout2.strip())
        else:
            rc3, stdout3, stderr3 = audio_system_run(["bash", "-lc", f"amixer -c {card} get PCM 2>/dev/null | sed -n '1,10p'"])
            if rc3 == 0 and stdout3.strip():
                out.append("amixer PCM:")
                out.append(stdout3.strip())
    else:
        rc2, stdout2, stderr2 = audio_system_run(["bash", "-lc", "amixer get Master 2>/dev/null | sed -n '1,10p'"])
        if rc2 == 0 and stdout2.strip():
            out.append("amixer default Master:")
            out.append(stdout2.strip())

    if len(out) <= 2:
        out.append("Aucun mixer système détecté pour ce périphérique via pactl/amixer.")

    return "\n".join(out)


def audio_system_volume_apply(volume, balance, device=""):
    """
    Applique volume général + balance gauche/droite au périphérique ciblé.

    device: hw:X,Y ou plughw:X,Y.
    volume: 0-100.
    balance: -100 gauche à +100 droite.
    """
    try:
        volume = int(volume)
    except Exception:
        volume = 70

    try:
        balance = int(balance)
    except Exception:
        balance = 0

    volume = max(0, min(100, volume))
    balance = max(-100, min(100, balance))

    if balance < 0:
        left = volume
        right = round(volume * (100 + balance) / 100)
    elif balance > 0:
        left = round(volume * (100 - balance) / 100)
        right = volume
    else:
        left = volume
        right = volume

    card, dev = audio_parse_alsa_hw(device)
    results = []
    results.append(f"Périphérique demandé: {device or 'défaut'}")
    results.append(f"Volume={volume}% Balance={balance}")
    results.append(f"Calcul: gauche={left}% droite={right}%")

    # PipeWire/PulseAudio: définir le sink par défaut si on trouve la carte.
    sink = audio_pactl_find_sink_for_alsa_card(card) if card != "" else ""
    if sink:
        rc_def, out_def, err_def = audio_system_run(["bash", "-lc", f"pactl set-default-sink {sink} 2>&1"])
        if rc_def == 0:
            results.append(f"OK pactl: sink système par défaut = {sink}")
        else:
            results.append("pactl set-default-sink non appliqué: " + (err_def.strip() or out_def.strip() or str(rc_def)))

        rc, stdout, stderr = audio_system_run(["bash", "-lc", f"pactl set-sink-volume {sink} {left}% {right}% 2>&1"])
        if rc == 0:
            results.append("OK pactl: volume/balance appliqués sur le sink ciblé.")
        else:
            results.append("pactl volume non appliqué: " + (stderr.strip() or stdout.strip() or f"code {rc}"))
    else:
        rc, stdout, stderr = audio_system_run(["bash", "-lc", f"pactl set-sink-volume @DEFAULT_SINK@ {left}% {right}% 2>&1"])
        if rc == 0:
            results.append("OK pactl: volume/balance appliqués sur le sink par défaut.")
        else:
            results.append("pactl non appliqué: " + (stderr.strip() or stdout.strip() or f"code {rc}"))

    # ALSA: viser la carte par numéro si possible.
    if card != "":
        applied = False
        for control in ["Master", "PCM", "Speaker"]:
            rc2, stdout2, stderr2 = audio_system_run(["bash", "-lc", f"amixer -c {card} sset {control} {left}%,{right}% 2>&1"])
            if rc2 == 0:
                results.append(f"OK amixer: card {card} contrôle {control} gauche/droite appliqué.")
                applied = True
                break

        if not applied:
            for control in ["Master", "PCM", "Speaker"]:
                rc3, stdout3, stderr3 = audio_system_run(["bash", "-lc", f"amixer -c {card} sset {control} {volume}% 2>&1"])
                if rc3 == 0:
                    results.append(f"OK amixer: card {card} contrôle {control} volume général appliqué; balance non supportée.")
                    applied = True
                    break

        if not applied:
            results.append(f"amixer: aucun contrôle Master/PCM/Speaker utilisable sur card {card}.")
    else:
        rc2, stdout2, stderr2 = audio_system_run(["bash", "-lc", f"amixer sset Master {left}%,{right}% 2>&1"])
        if rc2 == 0:
            results.append("OK amixer: Master default gauche/droite appliqué.")
        else:
            results.append("amixer default non appliqué: " + (stderr2.strip() or stdout2.strip() or f"code {rc2}"))

    results.append("")
    results.append("État après application:")
    results.append(audio_system_volume_get(device))

    return "\n".join(results)


def audio_system_vu_meter(device=""):
    return '{"ok": false, "left_db": null, "right_db": null, "left_pct": 0, "right_pct": 0, "source": ""}'


def audio_system_volume_card():
    devices, raw = audio_detect_alsa_devices()
    cfg = audio_load_config()
    selected = cfg.get("playfield_device") or cfg.get("backbox_device") or ""

    options = []
    for d in devices:
        hw = str(d.get("id", "") or "")
        card = str(d.get("card", "") or "")
        dev = str(d.get("device", "") or "")
        name = str(d.get("name", hw) or hw)
        desc = str(d.get("description", "") or "")
        plug = f"plughw:{card},{dev}" if card != "" and dev != "" else hw

        for value, suffix in [(plug, "plughw recommandé"), (hw, "hw direct")]:
            sel = " selected" if value == selected else ""
            label = f"{name} — {desc} — {value} ({suffix})"
            options.append(f'<option value="{esc(value)}"{sel}>{esc(label)}</option>')

    if not options:
        options.append('<option value="">Aucun périphérique ALSA détecté</option>')

    return f"""
<div class="card pco-audio-compact-card" id="pincabos-system-volume-card">
  <h3>Volume système / balance</h3>
  <p>
    Contrôle le mixer du périphérique sélectionné et tente aussi de le définir comme sortie système.
    N’écrit rien dans <code>VPinballX.ini</code> ni <code>vpinfe.ini</code>.
  </p>

  <table style="width:100%;">
    <tr>
      <td>Périphérique à contrôler</td>
      <td>
        <select id="pco-system-audio-device" style="width:100%;max-width:520px;padding:8px;">
          {''.join(options)}
        </select>
      </td>
    </tr>
    <tr>
      <td>Volume général</td>
      <td>
        <input id="pco-system-volume" type="range" min="0" max="100" value="70" style="width:70%;">
        <strong><span id="pco-system-volume-val">70</span>%</strong>
      </td>
    </tr>
    <tr>
      <td>Balance gauche / droite</td>
      <td>
        <input id="pco-system-balance" type="range" min="-100" max="100" value="0" style="width:70%;">
        <strong><span id="pco-system-balance-val">centre</span></strong>
      </td>
    </tr>
  </table>

  <p>
    <button class="button" type="button" id="pco-system-volume-apply">Appliquer volume/balance</button>
    <button class="button secondary" type="button" id="pco-system-volume-read">Lire état mixer</button>
  </p>

  <h4>VU meter sortie système</h4>
  <div style="display:grid;grid-template-columns:80px 1fr 70px;gap:8px;align-items:center;">
    <div>Gauche</div>
    <div style="height:16px;background:rgba(0,0,0,.45);border-radius:8px;overflow:hidden;border:1px solid rgba(255,176,0,.25);">
      <div id="pco-vu-left-bar" style="height:100%;width:0%;background:linear-gradient(90deg,#22c55e,#eab308,#ef4444);"></div>
    </div>
    <div><code id="pco-vu-left-db">-- dB</code></div>

    <div>Droite</div>
    <div style="height:16px;background:rgba(0,0,0,.45);border-radius:8px;overflow:hidden;border:1px solid rgba(255,176,0,.25);">
      <div id="pco-vu-right-bar" style="height:100%;width:0%;background:linear-gradient(90deg,#22c55e,#eab308,#ef4444);"></div>
    </div>
    <div><code id="pco-vu-right-db">-- dB</code></div>
  </div>
  <p><small id="pco-vu-source">VU meter prêt. Lance un test audio pour voir bouger les niveaux.</small></p>

  <details style="margin-top:12px;">
    <summary>Log volume système</summary>
    <pre id="pco-system-volume-log" style="white-space:pre-wrap;max-height:260px;overflow:auto;background:rgba(0,0,0,.45);border:1px solid rgba(255,176,0,.25);border-radius:12px;padding:12px;">Prêt.</pre>
  </details>

  <script>
  (function() {{
    const dev = document.getElementById("pco-system-audio-device");
    const vol = document.getElementById("pco-system-volume");
    const bal = document.getElementById("pco-system-balance");
    const volVal = document.getElementById("pco-system-volume-val");
    const balVal = document.getElementById("pco-system-balance-val");
    const log = document.getElementById("pco-system-volume-log");

    const vuL = document.getElementById("pco-vu-left-bar");
    const vuR = document.getElementById("pco-vu-right-bar");
    const dbL = document.getElementById("pco-vu-left-db");
    const dbR = document.getElementById("pco-vu-right-db");
    const vuSource = document.getElementById("pco-vu-source");

    function findWavDeviceSelect() {{
      return document.getElementById("pco-wav-device")
        || document.querySelector('select[name="wav_device"]')
        || document.querySelector('select[name="device"]');
    }}

    function syncFromWavSelect() {{
      const wavSel = findWavDeviceSelect();
      if (wavSel && dev && wavSel.value) {{
        dev.value = wavSel.value;
      }}
    }}

    function updateLabels() {{
      if (volVal && vol) volVal.textContent = vol.value;

      if (balVal && bal) {{
        const v = parseInt(bal.value || "0", 10);
        if (v === 0) balVal.textContent = "centre";
        else if (v < 0) balVal.textContent = "gauche " + Math.abs(v) + "%";
        else balVal.textContent = "droite " + v + "%";
      }}
    }}

    async function applyVolume() {{
      if (log) log.textContent = "Application en cours...";

      try {{
        const r = await fetch("/audio-ssf/system-volume/apply", {{
          method: "POST",
          headers: {{"Content-Type": "application/x-www-form-urlencoded"}},
          body: new URLSearchParams({{
            device: dev ? dev.value : "",
            volume: vol ? vol.value : "70",
            balance: bal ? bal.value : "0"
          }})
        }});
        const t = await r.text();
        if (log) log.textContent = t;
      }} catch (e) {{
        if (log) log.textContent = "Erreur: " + e;
      }}
    }}

    async function readVolume() {{
      if (log) log.textContent = "Lecture en cours...";

      try {{
        const r = await fetch("/audio-ssf/system-volume/get?device=" + encodeURIComponent(dev ? dev.value : ""), {{method: "GET"}});
        const t = await r.text();
        if (log) log.textContent = t;
      }} catch (e) {{
        if (log) log.textContent = "Erreur: " + e;
      }}
    }}

    if (vol) vol.addEventListener("input", updateLabels);
    if (bal) bal.addEventListener("input", updateLabels);

    document.addEventListener("click", function(e) {{
      if (e.target && e.target.id === "pco-system-volume-apply") applyVolume();
      if (e.target && e.target.id === "pco-system-volume-read") readVolume();
    }});

    document.addEventListener("change", function(e) {{
      const wavSel = findWavDeviceSelect();
      if (wavSel && dev && e.target === wavSel && wavSel.value) {{
        dev.value = wavSel.value;
      }}
    }});

    syncFromWavSelect();
    updateLabels();
}})();
  </script>

</div>
"""


@route("/audio-ssf")
def pincabos_audio_ssf_page_fixed():
    cfg = audio_load_config()

    saved_rows = ""
    try:
        saved_rows = f"""
<table>
  <tr><td>Backend</td><td><code>{esc(cfg.get('audio_backend', ''))}</code></td></tr>
  <tr><td>Backbox / ROM / Musique</td><td><code>{esc(cfg.get('backbox_device', ''))}</code></td></tr>
  <tr><td>Playfield / SSF</td><td><code>{esc(cfg.get('playfield_device', ''))}</code></td></tr>
  <tr><td>Surround VPX</td><td><code>{esc(cfg.get('surround_device', ''))}</code></td></tr>
  <tr><td>Bass shaker</td><td><code>{esc(cfg.get('bass_device', ''))}</code></td></tr>
  <tr><td>Fichier</td><td><code>{esc(str(AUDIO_ROUTER_CONFIG))}</code></td></tr>
</table>
"""
    except Exception as e:
        saved_rows = f"<p class='warn'>Erreur lecture configuration sauvegardée: {esc(str(e))}</p>"

    body = f"""

<style id="pco-audio-ssf-layout-final-css">
  .pco-audio-grid-tests,
  .pco-audio-grid-config {{
    display: grid !important;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) !important;
    gap: 10px !important;
    align-items: start !important;
    width: 100% !important;
    margin-bottom: 10px !important;
  }}

  .pco-audio-grid-tests > .card,
  .pco-audio-grid-config > .card,
  .pco-audio-grid-tests > .pco-audio-compact-card,
  .pco-audio-grid-config > .pco-audio-compact-card {{
    width: 100% !important;
    max-width: none !important;
    box-sizing: border-box !important;
    margin: 0 !important;
  }}

  .pco-audio-grid-tests iframe,
  .pco-audio-grid-config iframe {{
    max-width: 100% !important;
  }}

  @media (max-width: 1100px) {{
    .pco-audio-grid-tests,
    .pco-audio-grid-config {{
      grid-template-columns: 1fr !important;
    }}
  }}
</style>


<style id="pco-audio-ssf-equal-4-cards-css">
  .pco-audio-grid-tests,
  .pco-audio-grid-config {{
    display: grid !important;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) !important;
    gap: 12px !important;
    align-items: stretch !important;
    width: 100% !important;
    margin-bottom: 12px !important;
  }}

  .pco-audio-grid-tests > .card,
  .pco-audio-grid-config > .card,
  .pco-audio-grid-tests > form.card,
  .pco-audio-grid-config > form.card,
  .pco-audio-grid-tests > .pco-audio-compact-card,
  .pco-audio-grid-config > .pco-audio-compact-card {{
    width: 100% !important;
    max-width: none !important;
    min-height: 520px !important;
    box-sizing: border-box !important;
    margin: 0 !important;
    display: flex !important;
    flex-direction: column !important;
  }}

  .pco-audio-grid-config > .card,
  .pco-audio-grid-config > form.card {{
    min-height: 430px !important;
  }}

  .pco-audio-compact-card h2,
  .pco-audio-saved-full h2,
  .pco-audio-grid-config h2 {{
    margin-top: 0 !important;
    margin-bottom: 8px !important;
  }}

  .pco-audio-compact-card p,
  .pco-audio-saved-full p,
  .pco-audio-grid-config p {{
    margin-top: 6px !important;
    margin-bottom: 8px !important;
  }}

  .pco-audio-compact-card table,
  .pco-audio-saved-full table,
  .pco-audio-grid-config table {{
    width: 100% !important;
    margin-top: 4px !important;
    margin-bottom: 8px !important;
  }}

  .pco-audio-compact-card td,
  .pco-audio-saved-full td,
  .pco-audio-grid-config td {{
    padding-top: 4px !important;
    padding-bottom: 4px !important;
    vertical-align: middle !important;
  }}

  .pco-audio-compact-card iframe {{
    max-width: 100% !important;
  }}

  #pincabos-alsa-test-card iframe,
  #pco-audio-action-frame {{
    height: 130px !important;
  }}

  #pincabos-wav-test-card .pco-inline-volume {{
    margin-top: 8px !important;
    margin-bottom: 8px !important;
  }}

  .pco-audio-saved-full {{
    overflow: hidden !important;
  }}

  .pco-audio-saved-full table {{
    font-size: 0.95em !important;
  }}

  @media (max-width: 1100px) {{
    .pco-audio-grid-tests,
    .pco-audio-grid-config {{
      grid-template-columns: 1fr !important;
    }}

    .pco-audio-grid-tests > .card,
    .pco-audio-grid-config > .card,
    .pco-audio-grid-tests > form.card,
    .pco-audio-grid-config > form.card {{
      min-height: auto !important;
    }}
  }}
</style>

<h1>Audio / SSF V2</h1>

<p>
  Configuration native PinCabOS pour le choix des cartes de son :
  Backbox / ROM / musique, effets sous playfield / SSF, surround VPX et bass shaker.
</p>

<p>
  <a class="button" href="/audio-ssf/commander">🎚️ Ouvrir SSF Commander</a>
  <a class="button secondary" href="/audio-ssf">Rafraîchir</a>
</p>

<p class="warn">
  Les réglages Sons seulement / Mécanique seulement / Sons + mécanique ne sont plus dans cette page.
  Ils sont maintenant dans SSF Commander.
</p>

<div class="grid pco-audio-grid-tests">
  {pincabos_safe_audio_alsa_card()}
  {audio_wav_test_card()}
</div>

<div class="pco-audio-grid-config">
  <form method="post" action="/audio-ssf/save" class="card pco-audio-compact-card">
    <h2>Mode audio</h2>
    <table>
      {audio_config_rows()}
    </table>
    <p>
      <button class="button" type="submit">Sauvegarder configuration audio</button>
      <a class="button secondary" href="/audio-ssf/commander">🎚️ SSF Commander</a>
      <a class="button secondary" href="/audio-ssf">Rafraîchir</a>
    </p>
  </form>

  <div class="card pco-audio-compact-card pco-audio-saved-full">
    <h2>Configuration sauvegardée</h2>
    {saved_rows}
  </div>
</div>

{audio_ini_values_card()}
"""
    return page("Audio / SSF V2", body)


@route("/audio-ssf/test-alsa-quick", methods=["POST"])
def audio_ssf_test_alsa_quick():
    device = request.form.get("device", "").strip()
    channels = request.form.get("channels", "2").strip()

    if not device:
        return "ERREUR: aucun périphérique ALSA sélectionné.", 400, {"Content-Type": "text/plain; charset=utf-8"}

    if channels not in ["2", "4", "6", "8"]:
        channels = "2"

    try:
        cmd = [
            "/usr/bin/timeout",
            "3",
            "/usr/bin/speaker-test",
            "-D",
            device,
            "-c",
            channels,
            "-t",
            "sine",
            "-f",
            "440",
            "-l",
            "1",
        ]

        r = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            timeout=5,
        )

        out = []
        out.append("Commande: " + " ".join(cmd))
        out.append("")
        out.append("Code retour: " + str(r.returncode))
        out.append("")
        if r.stdout:
            out.append("STDOUT:")
            out.append(r.stdout)
        if r.stderr:
            out.append("STDERR:")
            out.append(r.stderr)

        return "\n".join(out), 200, {"Content-Type": "text/plain; charset=utf-8"}

    except Exception as e:
        return "Erreur test ALSA: " + str(e), 500, {"Content-Type": "text/plain; charset=utf-8"}


@route("/audio-ssf/system-volume/get", methods=["GET"])
def audio_ssf_system_volume_get():
    device = request.args.get("device", "").strip()
    return audio_system_volume_get(device), 200, {"Content-Type": "text/plain; charset=utf-8"}


@route("/audio-ssf/system-volume/apply", methods=["POST"])
def audio_ssf_system_volume_apply():
    device = request.form.get("device", "").strip()
    volume = request.form.get("volume", "70")
    balance = request.form.get("balance", "0")
    return audio_system_volume_apply(volume, balance, device), 200, {"Content-Type": "text/plain; charset=utf-8"}


@route("/audio-ssf/system-volume/meter-html", methods=["GET", "POST"])
def audio_ssf_system_volume_meter_html():
    return "", 204


PINCABOS_SSF_CONTROLLER_INI = "/home/pinball/.local/share/VPinballX/10.8/VPinballX.ini"


PINCABOS_SSF_EFFECTS = [
    ("DOFKnocker", "Knocker"),
    ("DOFContactors", "Contacteurs"),
    ("DOFFlippers", "Flippers"),
    ("DOFShaker", "Shaker"),
    ("DOFTargets", "Targets"),
    ("DOFDropTargets", "Drop Targets"),
    ("DOFChimes", "Chimes"),
    ("DOFBell", "Bell"),
    ("DOFGear", "Gear Motor"),
]


PINCABOS_SSF_LABELS = {
    "": "Non configuré",
    "0": "Sons seulement",
    "1": "Mécanique seulement",
    "2": "Sons + mécanique",
}


def ssf_commander_escape(value):
    import html
    return html.escape(str(value), quote=True)


def ssf_commander_read_controller():
    from pathlib import Path

    ini = Path(PINCABOS_SSF_CONTROLLER_INI)
    values = {"ForceDisableB2S": ""}
    for key, label in PINCABOS_SSF_EFFECTS:
        values[key] = ""

    if not ini.exists():
        return values, f"Fichier introuvable: {ini}"

    lines = ini.read_text(errors="replace").splitlines()
    in_controller = False

    for line in lines:
        stripped = line.strip()
        if stripped.lower() == "[controller]":
            in_controller = True
            continue
        if stripped.startswith("[") and stripped.endswith("]") and in_controller:
            break
        if not in_controller:
            continue
        if "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if key in values:
            values[key] = raw_value.strip()

    return values, ""


def ssf_commander_write_controller(new_values, function_name="SSF Commander"):
    from pathlib import Path
    from datetime import datetime
    import shutil
    import subprocess

    ini = Path(PINCABOS_SSF_CONTROLLER_INI)
    if not ini.exists():
        raise FileNotFoundError(str(ini))

    backup_dir = Path("/opt/pincabos/backups/ssf-commander")
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = backup_dir / f"VPinballX.ini.backup-ssf-commander-{stamp}"
    shutil.copy2(ini, backup)

    lines = ini.read_text(errors="replace").splitlines()

    managed_keys = ["ForceDisableB2S"] + [key for key, label in PINCABOS_SSF_EFFECTS]
    allowed = {"", "0", "1", "2"}

    normalized = {}

    normalized["ForceDisableB2S"] = str(new_values.get("ForceDisableB2S", "0")).strip()
    if normalized["ForceDisableB2S"] not in {"0", "1"}:
        normalized["ForceDisableB2S"] = "0"

    for key, label in PINCABOS_SSF_EFFECTS:
        value = str(new_values.get(key, "")).strip()
        if value not in allowed:
            value = ""
        normalized[key] = value

    stamp_human = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    comment = f"; Modifié {stamp_human} par PinCabOS fonction({function_name})"

    start = None
    end = None

    for i, line in enumerate(lines):
        if line.strip().lower() == "[controller]":
            start = i
            end = len(lines)
            for j in range(i + 1, len(lines)):
                s = lines[j].strip()
                if s.startswith("[") and s.endswith("]"):
                    end = j
                    break
            break

    if start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append("[Controller]")
        start = len(lines) - 1
        end = len(lines)

    before = lines[:start + 1]
    section = lines[start + 1:end]
    after = lines[end:]

    cleaned = []

    for line in section:
        stripped = line.strip()

        if "PinCabOS fonction(SSF Commander" in line:
            continue

        if "=" in line and not stripped.startswith((";", "#")):
            key = line.split("=", 1)[0].strip()
            if key in managed_keys:
                continue

        cleaned.append(line)

    while cleaned and not cleaned[-1].strip():
        cleaned.pop()

    if cleaned:
        cleaned.append("")

    new_managed = [comment]

    for key in managed_keys:
        new_managed.append(f"{key} = {normalized[key]}")

    new_lines = before + cleaned + new_managed + after

    ini.write_text(chr(10).join(new_lines) + chr(10))

    try:
        subprocess.run(["chown", "pinball:pinball", str(ini)], timeout=10)
    except Exception:
        pass

    return str(backup)


def ssf_commander_select_html(key, current):
    current = str(current or "").strip()
    options = [
        ("", "Non configuré"),
        ("0", "Sons seulement"),
        ("1", "Mécanique seulement"),
        ("2", "Sons + mécanique"),
    ]
    html_options = []
    for value, label in options:
        selected = " selected" if value == current else ""
        html_options.append(f'<option value="{value}"{selected}>{label}</option>')
    return f'<select name="{ssf_commander_escape(key)}">' + "".join(html_options) + "</select>"


@route("/audio-ssf/test-wav", methods=["POST"])
def audio_ssf_test_wav():
    wav_file = (
        request.form.get("wav_file", "")
        or request.form.get("file", "")
        or request.form.get("wav", "")
    ).strip()

    device = (
        request.form.get("device", "")
        or request.form.get("alsa_device", "")
        or request.form.get("output", "")
    ).strip()

    if not wav_file:
        return "ERREUR: aucun fichier WAV sélectionné.", 400, {"Content-Type": "text/plain; charset=utf-8"}

    if not device:
        return "ERREUR: aucune sortie ALSA sélectionnée.", 400, {"Content-Type": "text/plain; charset=utf-8"}

    wav_path = Path(wav_file)

    try:
        resolved = wav_path.resolve()
    except Exception as e:
        return f"ERREUR chemin WAV invalide: {e}", 400, {"Content-Type": "text/plain; charset=utf-8"}

    allowed_roots = [
        Path("/opt/pincabos/media").resolve(),
        Path("/home/pinball/Share").resolve(),
    ]

    if not resolved.exists() or not resolved.is_file():
        return f"ERREUR fichier WAV absent: {resolved}", 404, {"Content-Type": "text/plain; charset=utf-8"}

    if resolved.suffix.lower() not in [".wav", ".wave"]:
        return f"ERREUR fichier non WAV: {resolved}", 400, {"Content-Type": "text/plain; charset=utf-8"}

    if not any(str(resolved).startswith(str(root) + "/") or resolved == root for root in allowed_roots):
        return f"ERREUR chemin WAV non autorisé: {resolved}", 403, {"Content-Type": "text/plain; charset=utf-8"}

    # Nettoie les anciens tests et les captures VU courtes avant lecture.
    for kill_cmd in [
        ["/usr/bin/pkill", "-x", "aplay"],
        ["/usr/bin/pkill", "-x", "pw-play"],
        ["/usr/bin/pkill", "-x", "parec"],
        ["/usr/bin/pkill", "-f", "pincabos-audio-wav-test"],
    ]:
        try:
            subprocess.run(kill_cmd, timeout=2)
        except Exception:
            pass

    card, dev = audio_parse_alsa_hw(device)
    sink = audio_pactl_find_sink_for_alsa_card(card) if card != "" else ""

    # Si PipeWire connaît cette carte, on utilise pw-play.
    # Ça évite le conflit "Device or resource busy" avec ALSA direct.
    if sink:
        cmd = [
            "runuser", "-u", "pinball", "--",
            "bash", "-lc",
            f"export XDG_RUNTIME_DIR=/run/user/1000; pw-play --target {sink} {shlex.quote(str(resolved))}"
        ]
        printable = f"pw-play --target {sink} {resolved}"
    else:
        cmd = ["/usr/bin/aplay", "-D", device, str(resolved)]
        printable = " ".join(cmd)

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            stdout, stderr = proc.communicate(timeout=1.0)
            out = [
                "Commande: " + printable,
                "Code retour: " + str(proc.returncode),
            ]
            if stdout:
                out += ["", "STDOUT:", stdout]
            if stderr:
                out += ["", "STDERR:", stderr]
            return "\n".join(out), 200, {"Content-Type": "text/plain; charset=utf-8"}

        except subprocess.TimeoutExpired:
            return (
                "Lecture WAV lancée.\n"
                f"PID: {proc.pid}\n"
                f"Fichier: {resolved}\n"
                f"Sortie: {device}\n"
                + (f"PipeWire sink: {sink}" if sink else "Mode: ALSA direct"),
                200,
                {"Content-Type": "text/plain; charset=utf-8"},
            )

    except Exception as e:
        return f"Erreur lancement WAV: {e}", 500, {"Content-Type": "text/plain; charset=utf-8"}


@route("/audio-ssf/test-wav-stop", methods=["POST"])
def audio_ssf_test_wav_stop_fixed():
    out = []
    for cmd in [
        ["/usr/bin/pkill", "-x", "aplay"],
        ["/usr/bin/pkill", "-x", "pw-play"],
        ["/usr/bin/pkill", "-x", "parec"],
        ["/usr/bin/pkill", "-f", "pincabos-audio-wav-test"],
    ]:
        try:
            r = subprocess.run(cmd, text=True, capture_output=True, timeout=3)
            out.append(" ".join(cmd) + f" => {r.returncode}")
        except Exception as e:
            out.append(" ".join(cmd) + f" => ERREUR {e}")
    return "Stop audio demandé.\n" + "\n".join(out), 200, {"Content-Type": "text/plain; charset=utf-8"}




# ---- Fixed routes that were referenced by the page but absent from the legacy app. ----
@route("/audio-ssf/save", methods=["POST"])
def audio_ssf_save():
    cfg = audio_load_config()

    backglass = request.form.get(
        "backbox_device",
        (
            audio_ini_read_key(
                str(PINCABOS_VPX_AUDIO_INI),
                "Player",
                "SoundDeviceBG",
            )
            or ""
        ),
    ).strip()

    playfield = request.form.get(
        "playfield_device",
        (
            audio_ini_read_key(
                str(PINCABOS_VPX_AUDIO_INI),
                "Player",
                "SoundDevice",
            )
            or ""
        ),
    ).strip()

    sound3d = request.form.get(
        "sound3d",
        (
            audio_ini_read_key(
                str(PINCABOS_VPX_AUDIO_INI),
                "Player",
                "Sound3D",
            )
            or "0"
        ),
    ).strip()

    try:
        backglass = _pco_vpx_validate_device(
            backglass
        )

        playfield = _pco_vpx_validate_device(
            playfield
        )

        sound3d = _pco_vpx_validate_sound3d(
            sound3d
        )

        # Préserve les anciens champs PinCabOS.
        for key in (
            "audio_mode",
            "audio_backend",
            "backbox_device",
            "playfield_device",
            "surround_device",
            "bass_device",
            "ssf_mode",
        ):
            if key in request.form:
                cfg[key] = request.form.get(
                    key,
                    "",
                ).strip()

        for key in (
            "invert_lr",
            "invert_front_rear",
            "enable_bass",
            "night_mode",
        ):
            if key in request.form:
                cfg[key] = (
                    request.form.get(key) == "1"
                )

        cfg["backbox_device"] = backglass
        cfg["playfield_device"] = playfield
        cfg["sound3d"] = sound3d

        cfg["ssf_mode"] = (
            _pco_vpx_mode_from_sound3d(sound3d)
        )

        audio_save_config(cfg)

        output_lines = []

        # Préserve l’ancien comportement PinCabOS,
        # notamment muteaudio=false dans VPinFE.
        try:
            legacy_output = (
                audio_apply_to_vpx_vpinfe()
            )

            if legacy_output:
                output_lines.append(
                    str(legacy_output).strip()
                )

        except Exception as legacy_error:
            output_lines.append(
                "AVERTISSEMENT application PinCabOS "
                "existante : "
                + str(legacy_error)
            )

        # Écriture finale exacte dans VPinballX.ini.
        output_lines.extend(
            _pco_vpx_write_audio(
                backglass,
                playfield,
                sound3d,
            )
        )

        return page(
            "Audio / SSF V2",
            """
<div class="card">
  <h2>Configuration audio VPX sauvegardée</h2>

  <p class="ok">
    Les clés officielles de VPinballX.ini ont été
    écrites et relues avec succès.
  </p>

  <pre>"""
            + esc(
                "\n".join(output_lines)
                or "GO"
            )
            + """</pre>

  <p class="warn">
    Ferme et relance VPX pour appliquer
    le nouveau routage.
  </p>

  <p>
    <a class="button" href="/audio-ssf">
      Retour Audio / SSF
    </a>
  </p>
</div>
""",
        )

    except Exception as exc:
        return page(
            "Audio / SSF V2",
            """
<div class="card">
  <h2>Erreur de sauvegarde audio VPX</h2>

  <p class="bad">
    <code>"""
            + esc(str(exc))
            + """</code>
  </p>

  <p>
    VPinballX.ini est sauvegardé avant
    chaque écriture.
  </p>

  <p>
    <a
      class="button secondary"
      href="/audio-ssf"
    >
      Retour Audio / SSF
    </a>
  </p>
</div>
""",
        ), 500

@route("/audio-ssf/commander", methods=["GET"])
def audio_ssf_commander_page():
    values, error = ssf_commander_read_controller()
    rows = []
    for key, label in PINCABOS_SSF_EFFECTS:
        rows.append(
            "<tr><td><strong>" + esc(label) + "</strong><br><code>" + esc(key) + "</code></td><td>" +
            ssf_commander_select_html(key, values.get(key, "")) + "</td></tr>"
        )
    force = str(values.get("ForceDisableB2S", "0")).strip()
    force0 = " selected" if force != "1" else ""
    force1 = " selected" if force == "1" else ""
    warning = ("<p class='warn'>" + esc(error) + "</p>") if error else ""
    return page("SSF Commander", """
<div class="card">
  <h1>🎚️ SSF Commander</h1>
  <p>Configure le comportement Sons / Mécanique pour les effets VPX dans <code>[Controller]</code>.</p>
  """ + warning + """
  <form method="post" action="/audio-ssf/commander/save">
    <table>
      <tr><th>Effet</th><th>Mode</th></tr>
      <tr><td><strong>Force Disable B2S</strong></td><td><select name="ForceDisableB2S"><option value="0""" + force0 + """>Non</option><option value="1""" + force1 + """>Oui</option></select></td></tr>
      """ + "".join(rows) + """
    </table>
    <p><button class="button" type="submit">Sauvegarder SSF Commander</button>
    <a class="button secondary" href="/audio-ssf">Retour Audio / SSF</a></p>
  </form>
</div>
""")


@route("/audio-ssf/commander/save", methods=["POST"])
def audio_ssf_commander_save():
    values = {"ForceDisableB2S": request.form.get("ForceDisableB2S", "0")}
    for key, _label in PINCABOS_SSF_EFFECTS:
        values[key] = request.form.get(key, "")
    try:
        backup = ssf_commander_write_controller(values)
        return page("SSF Commander", """
<div class="card"><h2>SSF Commander sauvegardé</h2>
<p class="ok">La section <code>[Controller]</code> a été mise à jour.</p>
<p>Backup : <code>""" + esc(backup) + """</code></p>
<p><a class="button" href="/audio-ssf/commander">Retour SSF Commander</a></p></div>
""")
    except Exception as exc:
        return page("SSF Commander", """
<div class="card"><h2>Erreur SSF Commander</h2>
<p class="bad"><code>""" + esc(str(exc)) + """</code></p>
<p><a class="button secondary" href="/audio-ssf/commander">Retour</a></p></div>
"""), 500


@route("/audio")
def pincabos_audio_page_alias():
    return redirect("/audio-ssf", code=302)
