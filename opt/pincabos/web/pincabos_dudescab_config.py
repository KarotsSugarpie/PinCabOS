#!/usr/bin/env python3
# PinCabOs-File created by Karots Sugarpie
"""PinCabOS DudesCabConfig Web page V3.1 - faithful Web replica with documented HID bridge.

Provides a dedicated native Web UI at /DudesCabConfig and a safe firmware workflow.
The full HID configuration protocol is deliberately not guessed here: the
configuration tabs are present as a faithful shell while firmware and hardware
monitoring are implemented end-to-end.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import jsonify, request
from werkzeug.utils import secure_filename

MARKER = "PINCABOS_DUDESCAB_CONFIG_PAGE_V323_PERSISTENT_LOCK"
APP_VERSION = "2.0.11"
USER_AGENT = f"DudesCabConfigurator/{APP_VERSION}"

BASE_DIR = Path("/opt/pincabos/config/dudescab")
FIRMWARE_DIR = BASE_DIR / "firmwares"
CACHE_DIR = BASE_DIR / "cache"
LOG_DIR = Path("/opt/pincabos/logs/dudescab-firmware")
RUN_DIR = Path("/run/pincabos-dudescab")
JOBS_DIR = RUN_DIR / "jobs"
HELPER = Path("/usr/local/libexec/pincabos-dudescab-flash")

CHANNELS = {
    "stable": "https://dude.arnoz.com/DudesCab",
    "beta": "https://dude.arnoz.com/DudesCabBeta",
}

UF2_MAGIC_START0 = 0x0A324655
UF2_MAGIC_START1 = 0x9E5D5157
UF2_MAGIC_END = 0x0AB16F30
MAX_FIRMWARE_BYTES = 64 * 1024 * 1024

_lock = threading.RLock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_dirs() -> None:
    for path in (BASE_DIR, FIRMWARE_DIR, CACHE_DIR, LOG_DIR, JOBS_DIR):
        path.mkdir(parents=True, exist_ok=True)


def _atomic_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _run(command: list[str], timeout: int = 8) -> tuple[int, str]:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        output = (result.stdout + "\n" + result.stderr).strip()
        return result.returncode, output
    except Exception as exc:
        return 255, f"{type(exc).__name__}: {exc}"


def _sysfs_text(path: Path) -> str:
    try:
        return path.read_text(encoding="ascii", errors="ignore").strip().lower()
    except Exception:
        return ""


def _usb_devices() -> list[dict[str, str]]:
    devices: list[dict[str, str]] = []
    for node in sorted(Path("/sys/bus/usb/devices").glob("*")):
        vendor = _sysfs_text(node / "idVendor")
        product = _sysfs_text(node / "idProduct")
        if not vendor or not product:
            continue
        if vendor == "2e8a" and product == "106f":
            devices.append(
                {
                    "sysfs": str(node),
                    "vendor": vendor,
                    "product": product,
                    "manufacturer": _sysfs_text(node / "manufacturer"),
                    "name": _sysfs_text(node / "product"),
                    "serial": _sysfs_text(node / "serial"),
                }
            )
    return devices


def _hidraw_nodes() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for dev in sorted(Path("/dev").glob("hidraw*")):
        sys = Path("/sys/class/hidraw") / dev.name / "device" / "uevent"
        text = ""
        try:
            text = sys.read_text(encoding="ascii", errors="ignore").upper()
        except Exception:
            pass
        if "00002E8A:0000106F" not in text and "2E8A:106F" not in text:
            continue
        result.append(
            {
                "path": str(dev),
                "readable": os.access(dev, os.R_OK),
                "writable": os.access(dev, os.W_OK),
                "uevent": text.strip(),
            }
        )
    return result


def _tty_is_dudescab(path: Path) -> bool:
    try:
        name = path.resolve().name
    except Exception:
        name = path.name
    node = Path("/sys/class/tty") / name / "device"
    try:
        node = node.resolve()
    except Exception:
        return False
    for ancestor in [node, *node.parents]:
        if ancestor == Path("/"):
            break
        vendor = _sysfs_text(ancestor / "idVendor")
        product = _sysfs_text(ancestor / "idProduct")
        if vendor == "2e8a" and product == "106f":
            return True
    return False


def _serial_nodes() -> list[dict[str, Any]]:
    candidates: list[Path] = []
    for item in [Path("/dev/dudescab")]:
        if item.exists() or item.is_symlink():
            candidates.append(item)
    by_id = Path("/dev/serial/by-id")
    if by_id.exists():
        for item in sorted(by_id.iterdir()):
            name = item.name.lower()
            if "dudescab" in name or "atelier" in name or "arnoz" in name:
                candidates.append(item)
    candidates.extend(
        path for path in sorted(Path("/dev").glob("ttyACM*"))
        if _tty_is_dudescab(path)
    )

    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in candidates:
        try:
            resolved = str(path.resolve())
        except Exception:
            resolved = str(path)
        key = resolved
        if key in seen:
            continue
        seen.add(key)
        result.append(
            {
                "path": str(path),
                "resolved": resolved,
                "readable": os.access(path, os.R_OK),
                "writable": os.access(path, os.W_OK),
            }
        )
    return result


def _process_matches(pattern: str) -> list[str]:
    code, output = _run(["/usr/bin/pgrep", "-af", pattern], timeout=5)
    if code not in (0, 1):
        return []
    rows = []
    own_pid = os.getpid()
    for line in output.splitlines():
        if not line.strip():
            continue
        try:
            pid = int(line.split(maxsplit=1)[0])
        except Exception:
            pid = -1
        if pid == own_pid:
            continue
        rows.append(line.strip())
    return rows


def _service_active(name: str) -> bool:
    code, output = _run(["/usr/bin/systemctl", "is-active", name], timeout=5)
    return code == 0 and output.splitlines()[0:1] == ["active"]


def _space(path: str) -> dict[str, Any]:
    try:
        usage = shutil.disk_usage(path)
        stat = os.statvfs(path)
        return {
            "path": path,
            "free_bytes": usage.free,
            "free_mb": round(usage.free / 1024 / 1024, 1),
            "free_inodes": stat.f_favail,
        }
    except Exception as exc:
        return {"path": path, "error": f"{type(exc).__name__}: {exc}"}


def _hardware_status() -> dict[str, Any]:
    usb = _usb_devices()
    hidraw = _hidraw_nodes()
    serial = _serial_nodes()
    vpx = _process_matches(r"VPinballX|/opt/pincabos/bin/vpx\.sh")
    return {
        "timestamp": _utc_now(),
        "connected": bool(usb),
        "usb": usb,
        "hidraw": hidraw,
        "hid_count": len(hidraw),
        "serial": serial,
        "serial_ready": any(x.get("readable") and x.get("writable") for x in serial),
        "vpinfe_active": _service_active("pincabos-vpinfe.service"),
        "vpx_running": bool(vpx),
        "vpx_processes": vpx,
        "space": [_space("/"), _space("/run")],
        "firmware_helper": HELPER.exists() and os.access(HELPER, os.X_OK),
        "config_protocol": "documented-safe-v3",
    }


def _validate_uf2(path: Path) -> tuple[bool, str, dict[str, Any]]:
    try:
        size = path.stat().st_size
    except Exception as exc:
        return False, f"Impossible de lire le fichier: {exc}", {}
    if size <= 0:
        return False, "Le fichier UF2 est vide.", {}
    if size > MAX_FIRMWARE_BYTES:
        return False, "Le fichier UF2 dépasse 64 MiB.", {"size": size}
    if size % 512 != 0:
        return False, "La taille UF2 n'est pas un multiple de 512 octets.", {"size": size}

    blocks = size // 512
    sample_indexes = sorted({0, max(0, blocks // 2), max(0, blocks - 1)})
    try:
        with path.open("rb") as handle:
            for index in sample_indexes:
                handle.seek(index * 512)
                block = handle.read(512)
                if len(block) != 512:
                    return False, f"Bloc UF2 {index} incomplet.", {"size": size}
                start0 = int.from_bytes(block[0:4], "little")
                start1 = int.from_bytes(block[4:8], "little")
                end = int.from_bytes(block[508:512], "little")
                if (start0, start1, end) != (
                    UF2_MAGIC_START0,
                    UF2_MAGIC_START1,
                    UF2_MAGIC_END,
                ):
                    return False, f"Signature UF2 invalide au bloc {index}.", {"size": size}
    except Exception as exc:
        return False, f"Erreur de validation UF2: {exc}", {"size": size}

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return True, "UF2 valide", {"size": size, "blocks": blocks, "sha256": digest.hexdigest()}


def _normalise_manifest(channel: str, raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, dict):
        return []
    raw_ci = {str(k).lower(): v for k, v in raw.items()}
    values = raw_ci.get("firmwares", [])
    rows: list[dict[str, str]] = []
    if isinstance(values, dict):
        values = [
            {"version": str(version), "file": file_value}
            for version, file_value in values.items()
        ]
    if not isinstance(values, list):
        return []

    base = CHANNELS[channel].rstrip("/") + "/"
    for item in values:
        if isinstance(item, str):
            version = Path(item).stem
            file_value = item
        elif isinstance(item, dict):
            it = {str(k).lower(): v for k, v in item.items()}
            version = str(
                it.get("version")
                or it.get("name")
                or it.get("tag")
                or ""
            ).strip()
            file_value = str(
                it.get("file")
                or it.get("url")
                or it.get("firmware")
                or ""
            ).strip()
        else:
            continue
        if not version or not file_value:
            continue
        url = urllib.parse.urljoin(base, file_value)
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "dude.arnoz.com":
            continue
        rows.append(
            {
                "channel": channel,
                "version": version,
                "file": file_value,
                "url": url,
            }
        )
    return rows


def _cache_path(channel: str) -> Path:
    return CACHE_DIR / f"dude_versions-{channel}.json"


def _fetch_manifest(channel: str) -> dict[str, Any]:
    if channel not in CHANNELS:
        raise ValueError("Canal firmware invalide.")
    url = CHANNELS[channel].rstrip("/") + "/dude_versions.json"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Cache-Control": "no-cache",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            body = response.read(2 * 1024 * 1024 + 1)
            if len(body) > 2 * 1024 * 1024:
                raise RuntimeError("Le manifeste officiel dépasse 2 MiB.")
            raw = json.loads(body.decode("utf-8-sig"))
            result = {
                "channel": channel,
                "url": url,
                "fetched_at": _utc_now(),
                "http_status": getattr(response, "status", 200),
                "raw": raw,
                "firmwares": _normalise_manifest(channel, raw),
            }
            _atomic_json(_cache_path(channel), result)
            return result
    except urllib.error.HTTPError as exc:
        snippet = exc.read(512).decode("utf-8", errors="replace")
        raise RuntimeError(f"Serveur firmware HTTP {exc.code}: {snippet.strip()}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Serveur firmware inaccessible: {exc.reason}") from exc


def _cached_manifest(channel: str) -> dict[str, Any]:
    return _read_json(
        _cache_path(channel),
        {"channel": channel, "firmwares": [], "fetched_at": None},
    )


def _safe_firmware_path(relative: str) -> Path:
    relative = str(relative or "").strip().replace("\\", "/")
    if not relative:
        raise ValueError("Firmware manquant.")
    root = FIRMWARE_DIR.resolve()
    candidate = (FIRMWARE_DIR / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("Chemin firmware refusé.") from exc
    if candidate.suffix.lower() != ".uf2" or not candidate.is_file():
        raise ValueError("Fichier UF2 introuvable.")
    return candidate


def _list_local_firmwares() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not FIRMWARE_DIR.exists():
        return rows
    for path in sorted(FIRMWARE_DIR.rglob("*.uf2"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            relative = str(path.relative_to(FIRMWARE_DIR))
            valid, detail, metadata = _validate_uf2(path)
            rows.append(
                {
                    "relative": relative,
                    "name": path.name,
                    "valid": valid,
                    "detail": detail,
                    "size": metadata.get("size", path.stat().st_size),
                    "sha256": metadata.get("sha256", ""),
                    "modified_at": datetime.fromtimestamp(
                        path.stat().st_mtime, timezone.utc
                    ).isoformat(timespec="seconds"),
                }
            )
        except Exception:
            continue
    return rows


def _download_firmware(channel: str, version: str) -> dict[str, Any]:
    manifest = _cached_manifest(channel)
    rows = manifest.get("firmwares", []) if isinstance(manifest, dict) else []
    descriptor = next(
        (
            item
            for item in rows
            if isinstance(item, dict) and str(item.get("version")) == version
        ),
        None,
    )
    if descriptor is None:
        manifest = _fetch_manifest(channel)
        descriptor = next(
            (
                item
                for item in manifest.get("firmwares", [])
                if str(item.get("version")) == version
            ),
            None,
        )
    if descriptor is None:
        raise ValueError("Version firmware absente du manifeste officiel.")

    url = str(descriptor["url"])
    target_dir = FIRMWARE_DIR / channel / secure_filename(version)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "dude_firmware.uf2"
    temporary = target.with_suffix(".uf2.part")

    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/octet-stream"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as response, temporary.open("wb") as handle:
            total = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_FIRMWARE_BYTES:
                    raise RuntimeError("Le téléchargement dépasse 64 MiB.")
                handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

    valid, detail, metadata = _validate_uf2(temporary)
    if not valid:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(detail)
    os.replace(temporary, target)
    return {
        "relative": str(target.relative_to(FIRMWARE_DIR)),
        "version": version,
        "channel": channel,
        "source": url,
        **metadata,
    }


def _job_state(job_id: str) -> dict[str, Any]:
    if not re.fullmatch(r"[a-f0-9]{32}", job_id):
        raise ValueError("Identifiant de tâche invalide.")
    path = JOBS_DIR / job_id / "state.json"
    data = _read_json(path, {})
    if not data:
        raise FileNotFoundError("Tâche firmware introuvable.")
    log_path = JOBS_DIR / job_id / "flash.log"
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        data["log"] = "\n".join(lines[-250:])
    except Exception:
        data["log"] = ""
    return data


def _html_options(values: list[str], selected: str | None = None) -> str:
    rows = []
    for value in values:
        chosen = " selected" if value == selected else ""
        safe = value.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")
        rows.append(f'<option value="{safe}"{chosen}>{safe}</option>')
    return "".join(rows)


def _input_rows() -> str:
    names = [
        "Start", "Extra Ball", "Coin 1", "Coin 2", "Launch Ball", "Return", "Exit",
        "Flipper Left", "Flipper Right", "Magna Left", "Magna Right", "Tilt", "Fire",
        "Door", "ROM Exit", "ROM -", "ROM Enter", "VOL -", "VOL +", "DPAD Up",
        "DPAD Right", "DPAD Down", "DPAD Left", "Night Mode", "Spare 1", "Spare 2",
        "Spare 3", "Spare 4", "Spare 5", "Spare 6", "Calib Button", "Shift",
    ]
    defaults = [
        "Button 1", "Button 2", "Button 3", "Button 4", "Enter", "Escape", "Q",
        "Left Shift", "Right Shift", "Left Control", "Right Control", "T", "F", "End",
        "7", "8", "9", "0", "Volume Down", "Volume Up", "Arrow Up", "Arrow Right",
        "Arrow Down", "Arrow Left", "F24", "F13", "F14", "F15", "F16", "F17", "F19", "None",
    ]
    choices = ["None"] + [f"Button {i}" for i in range(1, 33)] + [
        "Enter", "Escape", "Q", "Left Shift", "Right Shift", "Left Control", "Right Control",
        "T", "F", "End", "7", "8", "9", "0", "Volume Down", "Volume Up", "Arrow Up",
        "Arrow Right", "Arrow Down", "Arrow Left", "F13", "F14", "F15", "F16", "F17", "F19", "F24",
    ]
    rows = []
    for index, (name, default) in enumerate(zip(names, defaults), start=1):
        optimal = name in {"Flipper Left", "Flipper Right", "Magna Left", "Magna Right", "Fire"}
        rows.append(f"""
        <div class="dc-input-row dc-config-field" data-input-index="{index}">
          <div class="dc-input-name"><span>{index:02d}</span><strong>{name}</strong></div>
          <label>Fonction<select data-config-key="input.{index}.primary">{_html_options(choices, default)}</select></label>
          <label class="dc-shifted-field">Shifted<select data-config-key="input.{index}.shifted">{_html_options(choices, "None")}</select></label>
          <label>Latence<select data-config-key="input.{index}.latency"><option{" selected" if optimal else ""}>Optimal</option><option{"" if optimal else " selected"}>Normale</option></select></label>
          <label>Délai<input type="number" min="0" max="100" value="0" data-config-key="input.{index}.debounce"><span>ms</span></label>
          <span class="dc-live-led" title="Entrée active"></span>
        </div>
        """)
    return "".join(rows)


def _output_selectors() -> str:
    return "".join(
        f'<button type="button" class="dc-output-selector{" is-active" if i == 1 else ""}" data-output-select="{i}">{i}</button>'
        for i in range(1, 17)
    )


def _output_cards() -> str:
    cards = []
    for index in range(1, 17):
        cards.append(f"""
        <section class="dc-output-card{" is-active" if index == 1 else ""}" data-output-card="{index}">
          <div class="dc-output-card-head">
            <label class="dc-check"><input type="checkbox" data-config-key="output.{index}.enabled" checked><span></span> Sortie {index}</label>
            <label>Nom<input type="text" value="Sortie {index}" data-config-key="output.{index}.name"></label>
            <label>Préréglage<select data-output-preset data-config-key="output.{index}.preset"><option>Custom</option><option>Flipper Logic</option><option>Contacteurs</option><option>Moteurs</option><option>Leds</option><option>Ampoules</option></select></label>
            <div class="dc-dof-number">DOF <strong>{index}</strong></div>
          </div>
          <div class="dc-output-options">
            <label class="dc-check"><input type="checkbox" data-config-key="output.{index}.night"><span></span>Sensible au Nightmode</label>
            <label class="dc-check"><input type="checkbox" data-config-key="output.{index}.digital"><span></span>Digital</label>
            <label class="dc-check"><input type="checkbox" data-config-key="output.{index}.gamma"><span></span>Correction Gamma</label>
            <label class="dc-check"><input type="checkbox" data-config-key="output.{index}.inverted"><span></span>Inversé</label>
          </div>
          <div class="dc-slider-grid">
            <label>Valeur max <input type="range" min="0" max="255" value="255" data-range-output="max-{index}" data-config-key="output.{index}.max"><output id="max-{index}">255</output></label>
            <label>Intensité <input type="range" min="0" max="100" value="100" data-range-output="intensity-{index}" data-config-key="output.{index}.intensity"><output id="intensity-{index}">100 %</output></label>
            <label>Valeur d'atténuation <input type="range" min="0" max="255" value="0" data-range-output="fall-{index}" data-config-key="output.{index}.falloff"><output id="fall-{index}">0</output></label>
            <label>Délai d'atténuation <input type="range" min="0" max="2000" value="0" data-range-output="fall-delay-{index}" data-config-key="output.{index}.falloff_delay"><output id="fall-delay-{index}">0 ms</output></label>
            <label>Durée d'activité minimum <input type="range" min="0" max="1000" value="0" data-range-output="min-{index}" data-config-key="output.{index}.minimum"><output id="min-{index}">0 ms</output></label>
            <label>Délai de sécurité <input type="range" min="0" max="10000" value="0" data-range-output="safe-{index}" data-config-key="output.{index}.safety"><output id="safe-{index}">0 ms</output></label>
          </div>
          <div class="dc-output-test">
            <label>Valeur PWM <input type="range" min="0" max="255" value="0" data-test-slider="{index}"><output>0</output></label>
            <button type="button" class="dc-dark-button" data-output-test="on" data-output="{index}" title="Le moteur de test HID sera activé après validation du protocole">ON</button>
            <button type="button" class="dc-dark-button" data-output-test="pulse" data-output="{index}" title="Le moteur de test HID sera activé après validation du protocole">PULSE</button>
          </div>
        </section>
        """)
    return "".join(cards)


def _mx_lanes() -> str:
    rows = []
    for lane in range(1, 9):
        rows.append(f"""
        <section class="dc-mx-lane" data-mx-lane="{lane}">
          <header><strong>Ligne {lane}</strong><span><b data-mx-count>0</b> Leds</span><button type="button" class="dc-icon-button" data-add-strip="{lane}" title="Ajouter un LED strip">+</button></header>
          <div class="dc-mx-empty">Aucun LED strip configuré sur cette sortie.</div>
          <div class="dc-mx-strips"></div>
        </section>
        """)
    return "".join(rows)


def _page_body() -> str:
    return f"""
<link rel="stylesheet" href="/static/pincabos-dudescab-config-v3.css?v=31">
<div id="dc-app" class="dc-app dc-windows-shell" data-marker="PINCABOS_DUDESCAB_CONFIG_PAGE_V31">
  <header class="dc-original-header">
    <div class="dc-header-brand">
      <img class="dc-arnoz-mark" src="/static/dudescabconfig/arnoz-white.png" alt="L'Atelier d'Arnoz">
      <div class="dc-title-stack"><span>DUDE'S CAB</span><strong>CONFIGURATOR</strong></div>
    </div>
    <div class="dc-language-flags" aria-label="Langue">
      <button type="button" data-lang="de"><img src="/static/dudescabconfig/flag-de.png" alt="Deutsch"></button>
      <button type="button" data-lang="en"><img src="/static/dudescabconfig/flag-en.png" alt="English"></button>
      <button type="button" data-lang="es"><img src="/static/dudescabconfig/flag-es.png" alt="Español"></button>
      <button type="button" class="is-active" data-lang="fr"><img src="/static/dudescabconfig/flag-fr.png" alt="Français"></button>
      <button type="button" data-lang="it"><img src="/static/dudescabconfig/flag-it.png" alt="Italiano"></button>
      <button type="button" data-lang="pt"><img src="/static/dudescabconfig/flag-pt.png" alt="Português"></button>
      <span class="dc-version-badge">v2.0.11 Web V3.2.3</span>
    </div>
  </header>

  <section class="dc-device-strip">
    <label>Carte disponible
      <select id="dc-device-select"><option>Recherche du Dude's Cab…</option></select>
    </label>
    <button id="dc-connect-btn" type="button" class="dc-small-button">Connecter</button>
    <span class="dc-connection-summary"><b id="dc-main-status">Détection…</b><small id="dc-main-detail">USB / HID / série</small></span>
    <a class="dc-small-button dc-link-button" href="/dof/commander">DOF Commander</a>
  </section>

  <section class="dc-command-strip">
    <div class="dc-command-group"><strong>Carte Dude</strong>
      <button type="button" data-card-action="read">Lire Config</button>
      <button type="button" data-card-action="send">Envoyer Config <i id="dc-send-dirty" hidden>●</i></button>
      <button type="button" data-card-action="monitor">Moniteur Config</button>
      <button type="button" data-card-action="reset">Reset le Dude</button>
    </div>
    <div class="dc-command-group"><strong>Mémoire Flash</strong>
      <button type="button" data-card-action="memory-read">Lire la mémoire</button>
      <button type="button" data-card-action="memory-save">Sauver en mémoire <i id="dc-memory-dirty" hidden>●</i></button>
      <button type="button" data-card-action="memory-reset">Réinitialiser la mémoire</button>
    </div>
  </section>

  <section class="dc-status-strip">
    <span>Carte Dude</span>
    <div class="dc-status-icon is-active" id="dc-status-idle" title="Dude connecté"><img src="/static/dudescabconfig/status-beer.png" alt="Connecté"></div>
    <div class="dc-status-icon" id="dc-status-admin" title="Mode administrateur"><img src="/static/dudescabconfig/status-admin.png" alt="Admin"></div>
    <div class="dc-status-icon" id="dc-status-calibration" title="Calibration"><img src="/static/dudescabconfig/status-calibration.png" alt="Calibration"></div>
    <div class="dc-status-icon" id="dc-status-night" title="Night Mode"><img src="/static/dudescabconfig/status-night.png" alt="Night Mode"></div>
    <div class="dc-status-icon" id="dc-status-shift" title="Shift"><img src="/static/dudescabconfig/status-shift.png" alt="Shift"></div>
    <div class="dc-status-icon" id="dc-status-warning" title="Avertissement"><img src="/static/dudescabconfig/status-warning.png" alt="Avertissement"></div>
    <div class="dc-status-icon" id="dc-status-error" title="Erreur"><img src="/static/dudescabconfig/status-error.png" alt="Erreur"></div>
    <strong id="dc-status-message">Rien à boire? Connecte ta Dude!</strong>
    <span class="dc-last-error">Dernière erreur: <b id="dc-last-error">Aucune</b></span>
  </section>

  <div class="dc-main-layout">
    <nav class="dc-side-tabs" aria-label="Sections du configurateur">
      <button class="is-active" data-dc-tab="general">Général</button>
      <button data-dc-tab="inputs">Entrées</button>
      <button data-dc-tab="accelerometer">Accéléromètre</button>
      <button data-dc-tab="plunger">Tire-Bille</button>
      <button data-dc-tab="outputs">Sorties</button>
      <button data-dc-tab="mx">Leds Adressables</button>
      <button data-dc-tab="monitor">Moniteur Debug</button>
    </nav>

    <main class="dc-content-area">
      <section class="dc-tab-panel is-active dc-general-panel" data-dc-panel="general">
        <div class="dc-watermark dc-watermark-dude"></div>
        <h1 class="dc-page-slogan" id="dc-page-slogan">C'est l'apéro !!</h1>
        <div class="dc-general-grid">
          <div class="dc-form-column">
            <label>Version du Firmware <output id="dc-firmware-installed">—</output></label>
            <label>Version de la configuration <output id="dc-config-version">—</output></label>
            <label>Nom de la Carte <input id="dc-card-name" type="text" value="Dude's Cab" data-config-key="general.name"></label>
            <label>ID de la Carte <span><input id="dc-card-id" type="range" min="1" max="5" value="1" data-range-output="dc-card-id-value" data-config-key="general.id"><output id="dc-card-id-value">1 (LedWiz 90)</output></span></label>
            <label>Fréquence CPU <span><input type="range" min="120" max="240" step="10" value="200" data-range-output="dc-cpu-value" data-config-key="general.cpu"><output id="dc-cpu-value">200 MHz</output></span></label>
            <label class="dc-check-row">Nightmode au démarrage <input type="checkbox" data-config-key="general.night_boot"><span class="dc-toggle"></span></label>
            <label>Délai du chien de garde <span><input type="range" min="0" max="120" value="0" data-range-output="dc-watchdog-value" data-config-key="general.watchdog"><output id="dc-watchdog-value">0 s</output></span></label>
            <div class="dc-inline-actions"><button type="button" class="dc-small-button" data-card-action="watchdog-test">Test Watchdog</button><button type="button" class="dc-small-button" id="dc-refresh-status">Actualiser le matériel</button></div>
          </div>

          <div class="dc-firmware-box">
            <h2>Firmware</h2>
            <label>Firmware disponible
              <select id="dc-firmware-select"><option value="">Clique sur Rechercher</option></select>
            </label>
            <label>Canal
              <select id="dc-channel"><option value="stable">Stable</option><option value="beta">Beta</option></select>
            </label>
            <div class="dc-inline-actions"><button id="dc-refresh-manifest" type="button">Rechercher</button><button id="dc-firmware-flash" type="button">Flasher le Firmware</button></div>
            <form id="dc-upload-form" enctype="multipart/form-data">
              <input id="dc-upload-file" name="firmware" type="file" accept=".uf2" required>
              <button type="submit">Flasher un fichier Firmware</button>
            </form>
            <small id="dc-manifest-age">Aucun manifeste chargé.</small>
            <div id="dc-local-list" class="dc-local-firmware-list"></div>
          </div>
        </div>

        <div class="dc-led-color-row">
          <strong>Couleurs de la led</strong>
          <label>Défaut<input type="color" value="#ff2ccf" data-config-key="color.default"></label>
          <label>Mode admin<input type="color" value="#ffe225" data-config-key="color.admin"></label>
          <label>Nightmode<input type="color" value="#2f60ff" data-config-key="color.night"></label>
          <label>Calibration<input type="color" value="#20e5df" data-config-key="color.calibration"></label>
          <label>Warning<input type="color" value="#ff9700" data-config-key="color.warning"></label>
          <label>Erreur<input type="color" value="#ff1f34" data-config-key="color.error"></label>
        </div>
        <div class="dc-file-actions">
          <button type="button" id="dc-load-dude">Charger un fichier DUDE</button>
          <button type="button" id="dc-save-dude">Sauver un fichier DUDE</button>
          <button type="button" data-dc-tab-jump="monitor">Ouvrir le fichier Log</button>
          <a href="/dof/commander" class="dc-small-button dc-link-button"><img src="/static/dudescabconfig/directoutput.png" alt="DirectOutput"> DirectOutput</a>
          <input id="dc-load-dude-input" type="file" accept=".dude,.json" hidden>
        </div>
        <div id="dc-space-warning" class="dc-warning-box" hidden></div>
      </section>

      <section class="dc-tab-panel" data-dc-panel="inputs">
        <div class="dc-panel-top-form">
          <label>Bouton Shift Mode<select id="dc-shift-button" data-config-key="inputs.shift"><option>Aucun</option>{_html_options([f"Bouton {i}" for i in range(1, 33)])}</select></label>
          <label>Bouton Night Mode<select data-config-key="inputs.night"><option>Night Mode</option>{_html_options([f"Bouton {i}" for i in range(1, 33)])}</select></label>
          <label>Type de clavier<select data-config-key="inputs.keyboard"><option>Azerty</option><option>Qwerty</option><option>Qwertz</option></select></label>
          <label>Entrée active <output id="dc-active-input">Aucune</output></label>
          <button type="button" class="dc-small-button" id="dc-force-inputs">Forcer les entrées</button>
        </div>
        <div class="dc-inputs-heading"><strong>Entrées</strong><span>Fonction</span><span>Shifted</span><span>Latence</span><span>Stabilisation</span></div>
        <div class="dc-input-list">{_input_rows()}</div>
      </section>

      <section class="dc-tab-panel" data-dc-panel="accelerometer">
        <div class="dc-accelerometer-layout">
          <div>
            <div class="dc-nudge-visual" id="dc-nudge-visual">
              <div class="dc-cross-h"></div><div class="dc-cross-v"></div>
              <div class="dc-dead-circle" id="dc-dead-circle"></div>
              <div class="dc-tilt-circle" id="dc-tilt-circle"></div>
              <div class="dc-nudge-dot" id="dc-nudge-dot"></div>
            </div>
            <div class="dc-axis-values"><span>X <b id="dc-axis-x">0</b></span><span>Y <b id="dc-axis-y">0</b></span></div>
          </div>
          <div class="dc-form-column">
            <label>Orientation de la Carte USB<select data-config-key="accelerometer.orientation"><option>Arrière</option><option>Droite</option><option>Avant</option><option>Gauche</option></select></label>
            <label>Précision de l'accéléromètre<select data-config-key="accelerometer.range"><option>±4g</option><option>±8g</option><option>±16g</option><option>±32g</option></select></label>
            <label>Intervalle d'échantillonnage <span><input type="range" min="1" max="33" value="8" data-range-output="dc-acc-poll" data-config-key="accelerometer.poll"><output id="dc-acc-poll">8 ms</output></span></label>
            <label>Taille du cache de valeurs <span><input type="range" min="1" max="64" value="1" data-range-output="dc-acc-cache" data-config-key="accelerometer.cache"><output id="dc-acc-cache">1</output></span></label>
            <label>Force du filtre interne <span><input type="range" min="0" max="100" value="60" data-range-output="dc-acc-filter" data-config-key="accelerometer.filter"><output id="dc-acc-filter">60 %</output></span></label>
            <label>Sensibilité X <span><input type="range" min="1" max="500" value="200" data-range-output="dc-acc-x" data-config-key="accelerometer.x"><output id="dc-acc-x">200</output></span></label>
            <label>Sensibilité Y <span><input type="range" min="1" max="500" value="200" data-range-output="dc-acc-y" data-config-key="accelerometer.y"><output id="dc-acc-y">200</output></span></label>
            <label>Zone Morte <span><input id="dc-dead-range" type="range" min="0" max="100" value="8" data-range-output="dc-dead-value" data-config-key="accelerometer.dead"><output id="dc-dead-value">8</output></span></label>
            <label>Limite de Tilt <span><input id="dc-tilt-range" type="range" min="10" max="100" value="72" data-range-output="dc-tilt-value" data-config-key="accelerometer.tilt"><output id="dc-tilt-value">72</output></span></label>
            <label>Bouton Tilt<select data-config-key="accelerometer.tilt_button"><option>Tilt</option>{_html_options([f"Bouton {i}" for i in range(1, 33)])}</select></label>
          </div>
        </div>
      </section>

      <section class="dc-tab-panel" data-dc-panel="plunger">
        <div class="dc-plunger-layout">
          <div class="dc-form-column">
            <label class="dc-check-row">Activé <input id="dc-plunger-enabled" type="checkbox" checked data-config-key="plunger.enabled"><span class="dc-toggle"></span></label>
            <label class="dc-check-row">Inversé <input type="checkbox" data-config-key="plunger.inverted"><span class="dc-toggle"></span></label>
            <label>Intervalle d'échantillonnage <span><input type="range" min="1" max="50" value="16" data-range-output="dc-plunger-poll" data-config-key="plunger.poll"><output id="dc-plunger-poll">16 ms</output></span></label>
            <label>Anti tremblement <span><input type="range" min="0" max="100" value="4" data-range-output="dc-plunger-shake" data-config-key="plunger.shake"><output id="dc-plunger-shake">4</output></span></label>
            <label>Durée de la Calibration <span><input type="range" min="1" max="30" value="10" data-range-output="dc-plunger-cal-time" data-config-key="plunger.calibration"><output id="dc-plunger-cal-time">10 s</output></span></label>
          </div>
          <div class="dc-plunger-preview">
            <div class="dc-plunger-track"><div id="dc-plunger-fill"></div><span id="dc-plunger-handle"></span></div>
            <output id="dc-plunger-position">0</output>
            <div class="dc-calibration-actions"><button type="button" id="dc-plunger-calibrate">Calibration</button><label class="dc-check"><input id="dc-plunger-calibrated" type="checkbox" disabled><span></span>Calibré</label></div>
          </div>
          <div class="dc-form-column">
            <label>Bouton de Calibration<select data-config-key="plunger.cal_button"><option>Calib Button</option>{_html_options([f"Bouton {i}" for i in range(1, 33)])}</select></label>
            <label>Bouton Poussé<select data-config-key="plunger.pushed"><option>Aucun</option><option>Launch Ball</option><option>Fire</option></select></label>
            <label>Bouton Tiré<select data-config-key="plunger.pulled"><option>Aucun</option><option>Launch Ball</option><option>Fire</option></select></label>
          </div>
        </div>
      </section>

      <section class="dc-tab-panel" data-dc-panel="outputs">
        <div class="dc-outputs-top">
          <label>Durée de la Pulsation <span><input type="range" min="10" max="2000" value="50" data-range-output="dc-pulse-duration" data-config-key="outputs.pulse"><output id="dc-pulse-duration">50 ms</output></span></label>
          <label>Extension<select id="dc-extension-select"><option value="0">Aucune extension lue</option></select></label>
          <button type="button" class="dc-small-button" id="dc-add-extension">Nouvelle Extension</button>
          <button type="button" class="dc-danger-button" id="dc-delete-extension">Supprimer l'extension</button>
          <label>Nom<input type="text" value="Extension 1" data-config-key="extension.1.name"></label>
          <label>Numéro d'ID <span><input type="range" min="1" max="8" value="1" data-range-output="dc-extension-id" data-config-key="extension.1.id"><output id="dc-extension-id">1</output></span></label>
          <label>Fréquence PWM <span><input type="range" min="100" max="5000" step="100" value="1000" data-range-output="dc-pwm-frequency" data-config-key="extension.1.pwm"><output id="dc-pwm-frequency">1000 Hz</output></span></label>
          <label>Puissance générale <span><input type="range" min="0" max="100" value="100" data-range-output="dc-general-power" data-config-key="extension.1.power"><output id="dc-general-power">100 %</output></span></label>
        </div>
        <div class="dc-output-selectors">{_output_selectors()}</div>
        <div class="dc-output-cards">{_output_cards()}</div>
        <div class="dc-safe-note">Les tests PWM documentés sont actifs avec arrêt automatique de sécurité. VPX doit être fermé. Les commandes Admin de lecture/écriture de configuration restent bloquées tant qu'elles ne sont pas documentées.</div>
      </section>

      <section class="dc-tab-panel" data-dc-panel="mx">
        <div class="dc-mx-settings">
          <label class="dc-check-row">Activé <input type="checkbox" data-config-key="mx.enabled"><span class="dc-toggle"></span></label>
          <label>Modèle de leds<select data-config-key="mx.model"><option>WS2812B</option><option>SK6812</option><option>APA102</option></select></label>
          <label>Équivalent LedWiz <input type="number" min="1" max="99" value="30" data-config-key="mx.ledwiz"></label>
          <label>Test au reset<select data-config-key="mx.reset_test"><option>Aucun</option><option>RGB</option><option>Couleurs</option><option>Laser</option></select></label>
          <label>Durée <span><input type="range" min="0" max="30" value="5" data-range-output="dc-mx-duration" data-config-key="mx.duration"><output id="dc-mx-duration">5 s</output></span></label>
          <label>Test à la connexion<select data-config-key="mx.connection_test"><option>Aucun</option><option>RGB</option><option>Couleurs</option><option>Laser</option></select></label>
          <label>Luminosité test <span><input type="range" min="0" max="100" value="50" data-range-output="dc-mx-brightness" data-config-key="mx.brightness"><output id="dc-mx-brightness">50 %</output></span></label>
          <label>Taux de compression <span><input type="range" min="0" max="100" value="78" data-range-output="dc-mx-compression" data-config-key="mx.compression"><output id="dc-mx-compression">78</output></span></label>
          <button type="button" id="dc-mx-test">Lancer Test MX</button>
        </div>
        <div class="dc-mx-lanes">{_mx_lanes()}</div>
      </section>

      <section class="dc-tab-panel" data-dc-panel="monitor">
        <div class="dc-monitor-toolbar">
          <label>Niveau de Log Dude<select id="dc-log-level"><option>None</option><option>Errors</option><option>Warnings</option><option selected>Info</option><option>Debug</option></select></label>
          <label class="dc-check"><input type="checkbox" id="dc-auto-scroll" checked><span></span>Activer le scrolling</label>
          <button type="button" id="dc-monitor-local" class="is-active">Local</button>
          <button type="button" id="dc-monitor-card">Dude's Cab</button>
          <button type="button" id="dc-monitor-refresh">Actualiser</button>
          <button type="button" id="dc-monitor-clear">Effacer</button>
        </div>
        <pre id="dc-monitor-json">Chargement du moniteur matériel…</pre>
        <div class="dc-monitor-devices"><div><strong>Interfaces HID</strong><span id="dc-hid-pill">—</span><div id="dc-hid-list"></div></div><div><strong>Interfaces série</strong><span id="dc-serial-pill">—</span><div id="dc-serial-list"></div></div></div>
      </section>
    </main>
  </div>

  <section id="dc-job-card" class="dc-job-overlay" hidden>
    <div class="dc-job-window">
      <header><strong>Installation du Firmware</strong><span id="dc-job-status">EN TEST</span></header>
      <div class="dc-progress"><div id="dc-job-bar" style="width:0%"></div></div>
      <p id="dc-job-detail">Préparation…</p>
      <pre id="dc-job-log"></pre>
      <button type="button" id="dc-job-close" disabled>Fermer</button>
    </div>
  </section>

  <div id="dc-toast" class="dc-toast" hidden></div>
</div>
<script src="/static/pincabos-dudescab-config-v3.js?v=323" defer></script>
"""


def _no_device_body() -> str:
    """Render a warning page without starting maintenance or loading the configurator."""
    return """
<style>
  .dc-device-warning-shell{
    min-height:calc(100vh - 80px);display:flex;align-items:center;justify-content:center;
    padding:30px;background:
      radial-gradient(circle at top,#3d174f 0,#190e22 38%,#09070c 100%);
    color:#fff;font-family:Arial,Helvetica,sans-serif
  }
  .dc-device-warning-card{
    width:min(680px,94vw);padding:34px;border:1px solid #8e50b5;border-radius:14px;
    background:linear-gradient(180deg,rgba(44,24,56,.98),rgba(18,12,23,.98));
    box-shadow:0 22px 70px rgba(0,0,0,.55);text-align:center
  }
  .dc-device-warning-icon{
    width:78px;height:78px;margin:0 auto 18px;border-radius:50%;display:grid;place-items:center;
    background:#5f2787;border:2px solid #d8a9ff;font-size:38px;font-weight:900
  }
  .dc-device-warning-card h1{margin:0 0 12px;font-size:28px;color:#fff}
  .dc-device-warning-card p{margin:8px auto;max-width:540px;color:#dfd4e7;line-height:1.55}
  .dc-device-warning-code{
    display:inline-block;margin:16px 0;padding:8px 12px;border-radius:7px;
    background:#100b14;border:1px solid #60406f;color:#e9cfff;font-family:monospace
  }
  .dc-device-warning-actions{
    display:flex;flex-wrap:wrap;justify-content:center;gap:12px;margin-top:22px
  }
  .dc-device-warning-actions a{
    min-height:44px;display:inline-flex;align-items:center;justify-content:center;
    padding:0 22px;border-radius:8px;text-decoration:none;font-weight:800;color:#fff;
    border:1px solid #d6b5eb;background:#6f2d9e
  }
  .dc-device-warning-actions a:hover{background:#8b43ba}
  .dc-device-warning-actions a.dc-secondary{background:#37213f}
  .dc-device-warning-actions a.dc-secondary:hover{background:#4c2c58}
</style>
<div class="dc-device-warning-shell">
  <section class="dc-device-warning-card">
    <div class="dc-device-warning-icon">!</div>
    <h1>Aucune Dude's Cab détectée</h1>
    <p>La page de configuration matérielle est disponible uniquement lorsqu'une carte Dude's Cab est branchée et détectée par PinCabOS.</p>
    <div class="dc-device-warning-code">USB attendu : 2e8a:106f</div>
    <p>VPinFE et VPX n'ont pas été arrêtés. Branche la carte, puis utilise Réessayer.</p>
    <div class="dc-device-warning-actions">
      <a href="/DudesCabConfig?v=322">Réessayer</a>
      <a class="dc-secondary" href="/dof/commander">Retour au DOF Commander</a>
    </div>
  </section>
</div>
"""


def register(app, page, esc) -> None:
    _ensure_dirs()

    def dudescabconfig_page():
        # V3.2.2: never expose the hardware controls when no physical Dude's
        # Cab is present. This warning path starts no maintenance and sends no
        # HID command.
        if not _hardware_status().get("connected"):
            return page("DudesCabConfig — carte absente", _no_device_body())
        return page("DudesCabConfig", _page_body())

    endpoint = "pincabos_dudescabconfig_page_v3"
    if endpoint not in app.view_functions:
        app.add_url_rule(
            "/DudesCabConfig",
            endpoint=endpoint,
            view_func=dudescabconfig_page,
            methods=["GET"],
        )

    @app.get("/api/dudescabconfig/status")
    def pincabos_dudescabconfig_status_v3():
        return jsonify({"ok": True, "status": _hardware_status()})

    @app.get("/api/dudescabconfig/firmwares")
    def pincabos_dudescabconfig_firmwares_v3():
        channel = str(request.args.get("channel", "stable")).lower()
        if channel not in CHANNELS:
            channel = "stable"
        return jsonify(
            {
                "ok": True,
                "channel": channel,
                "manifest": _cached_manifest(channel),
                "local": _list_local_firmwares(),
            }
        )

    @app.post("/api/dudescabconfig/firmwares/refresh")
    def pincabos_dudescabconfig_firmwares_refresh_v3():
        payload = request.get_json(silent=True) or {}
        channel = str(payload.get("channel", "stable")).lower()
        try:
            result = _fetch_manifest(channel)
            return jsonify({"ok": True, "manifest": result})
        except Exception as exc:
            app.logger.exception("DudesCab manifest refresh failed")
            cached = _cached_manifest(channel if channel in CHANNELS else "stable")
            return jsonify(
                {
                    "ok": False,
                    "error": str(exc),
                    "cached": cached,
                }
            ), 502

    @app.post("/api/dudescabconfig/firmwares/download")
    def pincabos_dudescabconfig_firmwares_download_v3():
        payload = request.get_json(silent=True) or {}
        channel = str(payload.get("channel", "stable")).lower()
        version = str(payload.get("version", "")).strip()
        if not version:
            return jsonify({"ok": False, "error": "Version manquante."}), 400
        try:
            with _lock:
                result = _download_firmware(channel, version)
            return jsonify({"ok": True, "firmware": result, "local": _list_local_firmwares()})
        except Exception as exc:
            app.logger.exception("DudesCab firmware download failed")
            return jsonify({"ok": False, "error": str(exc)}), 502

    @app.post("/api/dudescabconfig/firmwares/upload")
    def pincabos_dudescabconfig_firmwares_upload_v3():
        uploaded = request.files.get("firmware")
        if uploaded is None or not uploaded.filename:
            return jsonify({"ok": False, "error": "Fichier UF2 manquant."}), 400
        filename = secure_filename(uploaded.filename)
        if not filename.lower().endswith(".uf2"):
            return jsonify({"ok": False, "error": "Seuls les fichiers .uf2 sont acceptés."}), 400
        destination_dir = FIRMWARE_DIR / "manual" / datetime.now().strftime("%Y%m%d-%H%M%S")
        destination_dir.mkdir(parents=True, exist_ok=True)
        target = destination_dir / filename
        temporary = target.with_suffix(target.suffix + ".part")
        total = 0
        try:
            with temporary.open("wb") as handle:
                while True:
                    chunk = uploaded.stream.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_FIRMWARE_BYTES:
                        raise ValueError("Le fichier dépasse 64 MiB.")
                    handle.write(chunk)
                handle.flush()
                os.fsync(handle.fileno())
            valid, detail, metadata = _validate_uf2(temporary)
            if not valid:
                raise ValueError(detail)
            os.replace(temporary, target)
            return jsonify(
                {
                    "ok": True,
                    "firmware": {
                        "relative": str(target.relative_to(FIRMWARE_DIR)),
                        **metadata,
                    },
                    "local": _list_local_firmwares(),
                }
            )
        except Exception as exc:
            temporary.unlink(missing_ok=True)
            target.unlink(missing_ok=True)
            try:
                destination_dir.rmdir()
            except Exception:
                pass
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.post("/api/dudescabconfig/firmwares/flash")
    def pincabos_dudescabconfig_firmwares_flash_v3():
        payload = request.get_json(silent=True) or {}
        relative = str(payload.get("relative", ""))
        confirmed = bool(payload.get("confirmed"))
        if not confirmed:
            return jsonify({"ok": False, "error": "Confirmation de flash manquante."}), 400
        try:
            firmware = _safe_firmware_path(relative)
            valid, detail, metadata = _validate_uf2(firmware)
            if not valid:
                raise ValueError(detail)
            status = _hardware_status()
            if status["vpx_running"]:
                return jsonify(
                    {
                        "ok": False,
                        "error": "VPX est en jeu. Ferme la table avant le flash.",
                        "processes": status["vpx_processes"],
                    }
                ), 409
            if not status["connected"]:
                return jsonify({"ok": False, "error": "DudesCab non détecté en USB."}), 409
            if not status["serial_ready"]:
                return jsonify({"ok": False, "error": "Port série DudesCab non accessible."}), 409
            if not HELPER.exists() or not os.access(HELPER, os.X_OK):
                return jsonify({"ok": False, "error": "Moteur de flash absent."}), 500

            job_id = uuid.uuid4().hex
            job_dir = JOBS_DIR / job_id
            job_dir.mkdir(parents=True, exist_ok=False)
            _atomic_json(
                job_dir / "state.json",
                {
                    "job_id": job_id,
                    "status": "queued",
                    "stage": "queued",
                    "progress": 0,
                    "detail": "Tâche firmware mise en file.",
                    "firmware": relative,
                    "sha256": metadata.get("sha256"),
                    "created_at": _utc_now(),
                },
            )
            subprocess.Popen(
                ["/usr/bin/sudo", "-n", str(HELPER), job_id, str(firmware)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                close_fds=True,
            )
            return jsonify({"ok": True, "job_id": job_id}), 202
        except Exception as exc:
            app.logger.exception("DudesCab firmware flash start failed")
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.get("/api/dudescabconfig/jobs/<job_id>")
    def pincabos_dudescabconfig_job_v3(job_id: str):
        try:
            return jsonify({"ok": True, "job": _job_state(job_id)})
        except FileNotFoundError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 404
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
