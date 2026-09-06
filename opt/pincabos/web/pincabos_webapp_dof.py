"""Pages DOF / Outputs de la WebApp PinCabOS (/dof, /api/dof/commander/test).

Code déplacé tel quel depuis app.py (PINCABOS_WEBAPP_MODULES_V1) ; les routes gardent
leurs chemins et leurs noms de fonction. `page()` (gabarit commun) est fourni par app.py
à l'enregistrement : `register(app, page)`.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from flask import Blueprint, current_app, request

from pincabos_webapp_core import esc, pco_path_text, pco_script, run_cmd, service_status, shlex_quote

dof_bp = Blueprint("dof", __name__)

page = None  # gabarit HTML commun, posé par register()


def dof_file_status():
    cfg = Path("/home/pinball/.local/share/VPinballX/10.8/directoutputconfig")

    files = [
        "GlobalConfig_B2SServer.xml",
        "cabinet.xml",
        "directoutputconfig.ini",
    ]

    rows = []
    for name in files:
        f = cfg / name
        if f.exists():
            size = f.stat().st_size
            rows.append(
                f'<tr><td><code>{esc(name)}</code></td>'
                f'<td><span class="ok">présent</span></td>'
                f'<td>{size} bytes</td></tr>'
            )
        else:
            rows.append(
                f'<tr><td><code>{esc(name)}</code></td>'
                f'<td><span class="bad">absent</span></td>'
                f'<td>-</td></tr>'
            )

    try:
        extra = sorted(cfg.glob("directoutputconfig*.ini"))
        for f in extra:
            if f.name == "directoutputconfig.ini":
                continue
            rows.append(
                f'<tr><td><code>{esc(f.name)}</code></td>'
                f'<td><span class="ok">présent</span></td>'
                f'<td>{f.stat().st_size} bytes</td></tr>'
            )
    except Exception:
        pass

    return str(cfg), "\n".join(rows)


def detect_dof_devices():
    """Détection réelle par VID/PID udev (outil dof-cabinet). Seul le matériel
    effectivement branché est listé — plus de familles « probables » déduites
    de mots-clés. Les extensions portées par une carte (Walter, MOSLight sur
    la Dude's Cab) ne sont pas des périphériques USB séparés."""
    usb = run_cmd(["bash", "--noprofile", "--norc", "-c", "lsusb 2>/dev/null || true"], timeout=5)
    tty = run_cmd(["bash", "--noprofile", "--norc", "-c", "ls -lah /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || true"], timeout=5)
    hid = run_cmd(["bash", "--noprofile", "--norc", "-c", "ls -lah /dev/hidraw* 2>/dev/null || true"], timeout=5)

    devices = []
    try:
        import pincabos_dof_hardware as _pco_dofhw
        devices = _pco_dofhw._detect()
    except Exception:
        devices = []

    rows = []
    for d in devices:
        if d.get("auto_config"):
            badge = '<span class="ok">AutoConfig — géré tout seul par DOF</span>'
        else:
            badge = '<span class="warn">à déclarer dans cabinet.xml</span>'
        rows.append(
            f'<tr><td><strong>{esc(d.get("kind", "?"))}</strong></td>'
            f'<td><code>{esc(d.get("dev", ""))}</code> · série <code>{esc(d.get("serial") or "-")}</code></td>'
            f'<td>{badge}</td></tr>'
        )
    if devices:
        summary = f'<span class="ok">{len(devices)} contrôleur(s) DOF branché(s).</span>'
    else:
        rows.append('<tr><td colspan="3"><span class="warn">aucun contrôleur DOF détecté</span></td></tr>')
        summary = '<span class="warn">Aucun contrôleur DOF détecté.</span>'

    raw = f"""===== lsusb =====
{usb}

===== Serial devices =====
{tty}

===== HID raw devices =====
{hid}
"""
    return summary, "\n".join(rows), raw


def dof_logs():
    log = run_cmd(
        [
            "bash",
            "--noprofile",
            "--norc",
            "-c",
            "journalctl -u pincabos-vpinfe.service -n 260 --no-pager | "
            "grep -iE 'dof|directoutput|global config|cabinet|ini|framework|device|pinscape|pacled|pacdrive|dudes|ftdi|pinone' || true"
        ],
        timeout=8
    )
    return log[-20000:] if log else "Aucun log DOF trouvé."



def dof_check_cmd(cmd, timeout=6):
    try:
        r = subprocess.run(
            ["bash", "-lc", cmd],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return (r.stdout or "").strip()
    except Exception:
        return ""


def dof_pkg_ok(pkg):
    return dof_check_cmd(f"dpkg -s {shlex_quote(pkg)} >/dev/null 2>&1 && echo yes || echo no") == "yes"


def dof_module_ok(module):
    return dof_check_cmd(f"lsmod | awk '{{print $1}}' | grep -qx {shlex_quote(module)} && echo yes || modinfo {shlex_quote(module)} >/dev/null 2>&1 && echo yes || echo no") == "yes"


def dof_udev_ok(pattern):
    return dof_check_cmd(f"grep -qi {shlex_quote(pattern)} /etc/udev/rules.d/99-pincabos-dof-controllers.rules 2>/dev/null && echo yes || echo no") == "yes"


def dof_component_definitions():
    return [
        {
            "key": "ledwiz",
            "name": "LedWiz32",
            "check": [
                ("Package libusb", lambda: dof_pkg_ok("libusb-1.0-0")),
                ("Package HIDAPI", lambda: dof_pkg_ok("libhidapi-hidraw0")),
                ("Module usbhid", lambda: dof_module_ok("usbhid")),
                ("udev LedWiz fafa", lambda: dof_udev_ok("fafa")),
            ],
            "notes": "libusb / hidraw / règles udev"
        },
        {
            "key": "pinscape-kl25z",
            "name": "Pinscape / KL25Z / NXP",
            "check": [
                ("Package libusb", lambda: dof_pkg_ok("libusb-1.0-0")),
                ("Package HIDAPI", lambda: dof_pkg_ok("libhidapi-hidraw0")),
                ("Module usbhid", lambda: dof_module_ok("usbhid")),
                ("udev NXP 15a2/1fc9", lambda: dof_udev_ok("15a2") or dof_udev_ok("1fc9")),
            ],
            "notes": "libusb / hidraw / udev"
        },
        {
            "key": "pinscape-pico",
            "name": "Pinscape Pico / RP2040",
            "check": [
                ("Package libusb", lambda: dof_pkg_ok("libusb-1.0-0")),
                ("Package HIDAPI", lambda: dof_pkg_ok("libhidapi-hidraw0")),
                ("Module usbhid", lambda: dof_module_ok("usbhid")),
                ("Module cdc_acm", lambda: dof_module_ok("cdc_acm")),
                ("udev RP2040 2e8a/1209", lambda: dof_udev_ok("2e8a") or dof_udev_ok("1209")),
            ],
            "notes": "libusb / hidraw / serial"
        },
        {
            "key": "teensy",
            "name": "Teensy / PJRC (strips adressables)",
            "check": [
                ("Package python3-serial", lambda: dof_pkg_ok("python3-serial")),
                ("Module usbhid", lambda: dof_module_ok("usbhid")),
                ("Module cdc_acm", lambda: dof_module_ok("cdc_acm")),
                ("udev Teensy 16c0", lambda: dof_udev_ok("16c0")),
            ],
            "notes": "serial USB / TeensyStripController / backboard adressable"
        },
        {
            "key": "dudes-esp",
            "name": "Dude's Cab / Wemos / ESP",
            "check": [
                ("Package python3-serial", lambda: dof_pkg_ok("python3-serial")),
                ("Module usbserial", lambda: dof_module_ok("usbserial")),
                ("Module ch341", lambda: dof_module_ok("ch341")),
                ("Module cp210x", lambda: dof_module_ok("cp210x")),
                ("udev ESP/CH340/CP210x", lambda: dof_udev_ok("303a") or dof_udev_ok("1a86") or dof_udev_ok("10c4")),
            ],
            "notes": "serial USB / CH340 / CP210x / ESP"
        },
        {
            "key": "pacled",
            "name": "PacLed / Ultimarc",
            "check": [
                ("Package libusb", lambda: dof_pkg_ok("libusb-1.0-0")),
                ("Package HIDAPI", lambda: dof_pkg_ok("libhidapi-hidraw0")),
                ("Module usbhid", lambda: dof_module_ok("usbhid")),
                ("udev Ultimarc d209", lambda: dof_udev_ok("d209")),
            ],
            "notes": "libusb / hidraw / udev"
        },
        {
            "key": "ftdi",
            "name": "FTDI",
            "check": [
                ("Package python3-serial", lambda: dof_pkg_ok("python3-serial")),
                ("Module usbserial", lambda: dof_module_ok("usbserial")),
                ("Module ftdi_sio", lambda: dof_module_ok("ftdi_sio")),
                ("udev FTDI 0403", lambda: dof_udev_ok("0403")),
            ],
            "notes": "serial USB / dialout / udev"
        },
        {
            "key": "arduino",
            "name": "Arduino / Leonardo / Micro",
            "check": [
                ("Package python3-serial", lambda: dof_pkg_ok("python3-serial")),
                ("Module cdc_acm", lambda: dof_module_ok("cdc_acm")),
                ("Module usbhid", lambda: dof_module_ok("usbhid")),
                ("udev Arduino 2341/2a03/1b4f", lambda: dof_udev_ok("2341") or dof_udev_ok("2a03") or dof_udev_ok("1b4f")),
            ],
            "notes": "serial USB / hidraw / udev"
        },
        {
            "key": "serial-usb",
            "name": "Serial USB détecté",
            "check": [
                ("Package python3-serial", lambda: dof_pkg_ok("python3-serial")),
                ("Module usbserial", lambda: dof_module_ok("usbserial")),
                ("Module cdc_acm", lambda: dof_module_ok("cdc_acm")),
                ("Module ch341", lambda: dof_module_ok("ch341")),
                ("Module cp210x", lambda: dof_module_ok("cp210x")),
                ("Module ftdi_sio", lambda: dof_module_ok("ftdi_sio")),
            ],
            "notes": "ttyACM / ttyUSB / serial"
        },
    ]


def dof_component_status_html(component):
    results = []
    ok_count = 0

    for label, fn in component["check"]:
        try:
            ok = bool(fn())
        except Exception:
            ok = False

        if ok:
            ok_count += 1
            results.append(f'<div><span style="color:#2fff7f;">●</span> {esc(label)}</div>')
        else:
            results.append(f'<div><span style="color:#ff3333;">●</span> {esc(label)}</div>')

    total = len(component["check"])
    installed = ok_count == total

    dot = '<span style="color:#2fff7f; font-size:22px;">●</span>' if installed else '<span style="color:#ff3333; font-size:22px;">●</span>'
    state = "installé / prêt" if installed else f"incomplet ({ok_count}/{total})"

    return dot, state, "".join(results)


def dof_utils_card_html():
    rows = []

    for comp in dof_component_definitions():
        dot, state, details = dof_component_status_html(comp)

        rows.append(f"""
        <tr>
          <td>{dot}</td>
          <td>
            <strong>{esc(comp["name"])}</strong><br>
            <small>{esc(comp["notes"])}</small>
          </td>
          <td>{esc(state)}<br><small>{details}</small></td>
          <td style="white-space:nowrap;">
            <form method="post" action="/dof/install-utils/{esc(comp["key"])}" style="display:inline;">
              <button class="button secondary" type="submit">Installer</button>
            </form>
            <a class="button secondary" href="/dof">Vérifier</a>
          </td>
        </tr>
        """)

    return f"""
<div class="card" style="margin-top:20px;">
  <h2>Utilitaires / Drivers DOF</h2>

  <p>
    Installe et vérifie les dépendances Linux nécessaires pour les contrôleurs DOF :
    LedWiz32, Pinscape / KL25Z / NXP, Pinscape Pico / RP2040, Teensy / PJRC,
    Dude's Cab / Wemos / ESP, PacLed / Ultimarc, FTDI, Arduino / Leonardo / Micro
    et Serial USB. Chaque famille est indépendante : n'installe que ce qui
    correspond aux cartes réellement présentes dans ton cab.
  </p>

  <table style="width:100%; border-collapse:collapse;">
    <tr>
      <th style="text-align:left;">État</th>
      <th style="text-align:left;">Famille</th>
      <th style="text-align:left;">Vérification noyau / paquets / udev</th>
      <th style="text-align:left;">Action</th>
    </tr>
    {''.join(rows)}
  </table>

  <form method="post" action="/dof/install-utils/all" style="margin-top:14px;">
    <button class="button" type="submit">Tout installer / mettre à jour</button>
  </form>

  <p class="warn">
    Après installation : débranche/rebranche les cartes USB ou redémarre PinCabOS.
  </p>
</div>
"""


@dof_bp.route("/dof/install-utils", methods=["POST"])
@dof_bp.route("/dof/install-utils/<component>", methods=["POST"])
def dof_install_utils(component="all"):
    allowed = {c["key"] for c in dof_component_definitions()}
    allowed.add("all")

    component = (component or "all").strip()

    if component not in allowed:
        component = "all"

    job_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file = Path(f"/opt/pincabos/logs/dof-utils-install-{component}-{job_id}.log")
    script = str(pco_script("install_dof_component"))

    cmd = f"sudo {script} {shlex_quote(component)} > {log_file} 2>&1"

    subprocess.Popen(
        ["bash", "-lc", cmd],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )

    body = f"""
<div class="card">
  <h2>Installation DOF lancée</h2>
  <p class="ok">Installation / mise à jour lancée pour : <code>{esc(component)}</code></p>

  <table>
    <tr><td>Script</td><td><code>{esc(script)}</code></td></tr>
    <tr><td>Composant</td><td><code>{esc(component)}</code></td></tr>
    <tr><td>Log</td><td><code>{esc(log_file)}</code></td></tr>
    <tr><td>Règles udev</td><td><code>/etc/udev/rules.d/99-pincabos-dof-controllers.rules</code></td></tr>
  </table>

  <p>
    <a class="button" href="/dof">Retour DOF / Vérifier</a>
    <a class="button secondary" href="/tools/commander">Ouvrir Commander</a>
  </p>

  <p class="warn">
    Après l’installation, débranche/rebranche les cartes USB ou redémarre PinCabOS.
  </p>
</div>
"""
    return page("Outputs", body)


def dof_simple_cmd(cmd, timeout=6):
    try:
        r = subprocess.run(
            ["bash", "-lc", cmd],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return (r.stdout or "").strip()
    except Exception:
        return ""


def dof_detection_summary_card(summary, raw_devices, logs, file_rows):
    usb_count = dof_simple_cmd("lsusb | grep -vc 'root hub' || true")
    hid_count = dof_simple_cmd("ls /dev/hidraw* 2>/dev/null | wc -l || true")
    serial_count = dof_simple_cmd("ls /dev/ttyACM* /dev/ttyUSB* 2>/dev/null | wc -l || true")

    return f"""
<div class="grid" style="margin-top:20px;">
  <div class="card">
    <h2>Résumé détection DOF</h2>
    <p>État : {summary}</p>
    <table>
      <tr><td>USB non-root détectés</td><td><code>{esc(usb_count)}</code></td></tr>
      <tr><td>HID raw</td><td><code>{esc(hid_count)}</code></td></tr>
      <tr><td>Serial USB</td><td><code>{esc(serial_count)}</code></td></tr>
    </table>
  </div>

  <div class="card">
    <h2>Chemins DOF</h2>
    <table style="width:100%; border-collapse:collapse;">
      <tr><th style="text-align:left;">Fichier</th><th style="text-align:left;">État</th><th style="text-align:left;">Taille</th></tr>
      {file_rows}
    </table>
  </div>
</div>

<div class="card" style="margin-top:20px;">
  <h2>Détails techniques DOF</h2>

  <details>
    <summary>Périphériques bruts USB / HID / Serial</summary>
    <pre>{esc(raw_devices)}</pre>
  </details>

  <details style="margin-top:12px;">
    <summary>Logs DOF / VPinFE</summary>
    <pre>{esc(logs)}</pre>
  </details>

  <details style="margin-top:12px;">
    <summary>Informations utiles</summary>
    <p>
      Dossier outils : <code>{esc(pco_path_text('dof_tools'))}</code><br>
      Règles udev : <code>/etc/udev/rules.d/99-pincabos-dof-controllers.rules</code><br>
      Log actions : <code>/opt/pincabos/logs/dof-manager-action.log</code>
    </p>
  </details>
</div>
"""


PINCABOS_DOF_API_KEY_FILE = Path("/opt/pincabos/config/dof/configtool-api-key.txt")

# PINCABOS_BACKBOARD_MENU_REAPPLY_V1
# Un import du DOF Config Tool ecrase directoutputconfigNN.ini : on re-applique
# (detache) le contenu menu du backboard HD s'il est installe. L'outil sort
# immediatement si le cab n'a pas de backboard ou si l'auto est desactive.
def pincabos_backboard_menu_reapply():
    import subprocess
    try:
        subprocess.Popen(
            ["/opt/pincabos/tools/backboard-menu/pincabos-backboard-menu.sh", "apply"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        pass


def pincabos_dof_get_saved_api_key():
    try:
        return PINCABOS_DOF_API_KEY_FILE.read_text(errors="replace").strip()
    except Exception:
        return ""

def pincabos_dof_save_api_key(api_key):
    api_key = (api_key or "").strip()
    if not api_key:
        return
    try:
        PINCABOS_DOF_API_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        PINCABOS_DOF_API_KEY_FILE.write_text(api_key + "\n")
        os.chmod(PINCABOS_DOF_API_KEY_FILE, 0o600)
        try:
            shutil.chown(str(PINCABOS_DOF_API_KEY_FILE), user="pinball", group="pinball")
        except Exception:
            pass
    except Exception as e:
        try:
            current_app.logger.warning("Unable to save DOF API key: %s", e)
        except Exception:
            pass


DOF_CONFIG_DIRS = [
    Path("/home/pinball/.local/share/VPinballX/10.8/directoutputconfig"),
    Path("/opt/pincabos/config/dof"),
    Path("/home/pinball/.local/share/VPinballX/10.8/directoutputconfig"),
]


def dof_commander_find_configs():
    files = []

    for base in DOF_CONFIG_DIRS:
        if not base.exists():
            continue

        for pattern in ["*.xml", "*.ini", "*.cab", "*.json"]:
            for f in base.glob(pattern):
                if f.is_file():
                    files.append(f)

    return sorted(set(files), key=lambda p: str(p).lower())


def dof_commander_read_text(path):
    try:
        return Path(path).read_text(errors="replace")
    except Exception:
        return ""


def dof_commander_parse_xml_outputs(path):
    import xml.etree.ElementTree as ET

    outputs = []
    controllers = set()

    try:
        root = ET.parse(path).getroot()
    except Exception as e:
        return [], [], f"Erreur XML: {e}"

    # Recherche large : DOF XML peut avoir plusieurs structures.
    # On extrait tout élément qui ressemble à Controller / Toy / Output.
    for elem in root.iter():
        tag = elem.tag.split("}")[-1].lower()
        attrs = {k.lower(): v for k, v in elem.attrib.items()}

        if "controller" in tag or "ledwiz" in tag or "pacled" in tag or "pinscape" in tag:
            name = attrs.get("name") or attrs.get("id") or attrs.get("number") or elem.tag
            controllers.add(str(name))

        if any(word in tag for word in ["output", "toy", "led", "contact", "flasher", "solenoid"]):
            name = attrs.get("name") or attrs.get("id") or attrs.get("number") or attrs.get("output") or elem.tag
            number = attrs.get("number") or attrs.get("output") or attrs.get("led") or attrs.get("id") or ""
            controller = attrs.get("controller") or attrs.get("ledwiznumber") or attrs.get("device") or ""

            text_value = (elem.text or "").strip()
            outputs.append({
                "source": str(path),
                "type": elem.tag.split("}")[-1],
                "name": str(name),
                "number": str(number),
                "controller": str(controller),
                "value": text_value[:120],
            })

    return sorted(controllers), outputs, ""


def dof_commander_parse_ini_outputs(path):
    outputs = []
    controllers = set()

    raw = dof_commander_read_text(path)
    for idx, line in enumerate(raw.splitlines(), start=1):
        s = line.strip()
        if not s or s.startswith("#") or s.startswith(";"):
            continue

        # directoutputconfig.ini est souvent table=value,value,value...
        if "=" in s:
            key, value = s.split("=", 1)
            key = key.strip()
            value = value.strip()

            # Crée un résumé par table/config, pas 300 colonnes détaillées.
            outputs.append({
                "source": str(path),
                "type": "INI",
                "name": key,
                "number": str(idx),
                "controller": "directoutputconfig",
                "value": value[:160],
            })
            controllers.add("directoutputconfig")

    return sorted(controllers), outputs, ""


def dof_commander_load_inventory():
    configs = dof_commander_find_configs()

    all_controllers = set()
    all_outputs = []
    errors = []

    for f in configs:
        suffix = f.suffix.lower()

        if suffix == ".xml":
            controllers, outputs, err = dof_commander_parse_xml_outputs(f)
        elif suffix == ".ini":
            controllers, outputs, err = dof_commander_parse_ini_outputs(f)
        else:
            controllers, outputs, err = [], [], ""

        for c in controllers:
            all_controllers.add(c)

        all_outputs.extend(outputs)

        if err:
            errors.append(f"{f}: {err}")

    return configs, sorted(all_controllers), all_outputs, errors


PINCABOS_DOF_CABINET_DIR = Path("/opt/pincabos/config/dof/cabinets")
PINCABOS_DOF_ACTIVE_CABINET = Path("/opt/pincabos/config/dof/active-cabinet.txt")


def dof_commander_get_active_cabinet_json_path_pcb():
    PINCABOS_DOF_CABINET_DIR.mkdir(parents=True, exist_ok=True)

    # Source prioritaire : pointeur actif.
    if PINCABOS_DOF_ACTIVE_CABINET.exists():
        raw = PINCABOS_DOF_ACTIVE_CABINET.read_text(errors="replace").strip()
        if raw:
            p = Path(raw)
            if p.exists() and p.suffix.lower() == ".json":
                return p

    # Fallback : dernier JSON importé avec nom original.
    candidates = sorted(
        PINCABOS_DOF_CABINET_DIR.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    if candidates:
        return candidates[0]

    # Ancien fallback : ancien cabinet.json, si encore présent.
    old = Path("/opt/pincabos/config/dof/cabinet.json")
    if old.exists():
        return old

    return None


def dof_commander_load_cabinet_json_pcb():
    p = dof_commander_get_active_cabinet_json_path_pcb()

    if not p:
        return None, "Aucun cabinet JSON importé."

    try:
        raw = p.read_text(errors="replace").strip()
        data = json.loads(raw)
        return data, ""
    except Exception as e:
        return None, f"Erreur lecture JSON cabinet actif {p}: {e}"


def dof_commander_inventory_from_cabinet_json_pcb(data):
    cabinet_name = str(data.get("name") or data.get("Name") or "Cabinet sans nom")

    controllers = []
    outputs = []

    combos = data.get("combos") or {}
    devices = data.get("devices") or []

    if isinstance(devices, dict):
        devices = list(devices.values())

    def device_type_from_controller_id(controller_id, dev_name):
        cid = str(controller_id)
        name_l = str(dev_name).lower()

        if cid == "1" or "ledwiz" in name_l:
            return "LedWiz"
        if cid == "30" or "ws2811" in name_l or "ws2812" in name_l:
            return "Addressable LED / MX"
        if cid == "90" or "dude" in name_l:
            return "Dude's Cab"
        return f"Controller {cid}"

    def combo_label(toy_id):
        toy_key = str(toy_id)

        if toy_key in combos and isinstance(combos[toy_key], dict):
            combo = combos[toy_key]
            combo_name = combo.get("name") or combo.get("Name") or f"Combo {toy_id}"
            combo_toys = combo.get("toys") or []

            if combo_toys:
                return f"Combo {toy_id} — {combo_name} / toys={combo_toys}"

            return f"Combo {toy_id} — {combo_name}"

        return f"Toy ID {toy_id}"

    for dev in devices:
        if not isinstance(dev, dict):
            continue

        dev_name = str(dev.get("name") or dev.get("Name") or "Device")
        controller_id = dev.get("controller_id") or dev.get("ControllerId") or dev.get("id") or ""
        total_outputs = dev.get("outputs") or dev.get("Outputs") or ""
        assignments = dev.get("assignments") or dev.get("Assignments") or {}

        if not isinstance(assignments, dict):
            assignments = {}

        device_type = device_type_from_controller_id(controller_id, dev_name)
        assigned_count = len(assignments)

        controllers.append(
            f"{dev_name} — {device_type} — controller_id={controller_id}, outputs={total_outputs}, assignés={assigned_count}"
        )

        outputs.append({
            "source": "cabinet-json-original",
            "type": "Device Summary",
            "name": dev_name,
            "number": "",
            "controller": dev_name,
            "value": f"{device_type} / controller_id={controller_id} / outputs={total_outputs} / assignés={assigned_count}",
            "testable": False,
            "device_name": dev_name,
            "device_type": device_type,
            "controller_id": str(controller_id),
            "local_output": "",
            "assigned_toy": "",
        })

        if not assignments:
            outputs.append({
                "source": "cabinet-json-original",
                "type": "No Assignment",
                "name": f"{dev_name} — aucun toy assigné",
                "number": "",
                "controller": dev_name,
                "value": f"{device_type} présent dans le JSON, mais aucun output assigné",
                "testable": False,
                "device_name": dev_name,
                "device_type": device_type,
                "controller_id": str(controller_id),
                "local_output": "",
                "assigned_toy": "",
            })
            continue

        for local_output, toy_id in sorted(assignments.items(), key=lambda kv: int(kv[0]) if str(kv[0]).isdigit() else str(kv[0])):
            label = combo_label(toy_id)

            outputs.append({
                "source": "cabinet-json-original",
                "type": "Physical Output",
                "name": label,
                "number": str(local_output),
                "controller": dev_name,
                "value": f"{device_type} / controller_id={controller_id} / output local={local_output} / toy={toy_id}",
                "testable": True,
                "device_name": dev_name,
                "device_type": device_type,
                "controller_id": str(controller_id),
                "local_output": str(local_output),
                "assigned_toy": str(toy_id),
            })

    return cabinet_name, controllers, outputs


def dof_commander_load_inventory_active_pcb():
    configs = dof_commander_find_configs()
    errors = []

    active_path = dof_commander_get_active_cabinet_json_path_pcb()
    data, err = dof_commander_load_cabinet_json_pcb()

    if data:
        cabinet_name, controllers, outputs = dof_commander_inventory_from_cabinet_json_pcb(data)
        source = str(active_path) if active_path else "cabinet json"
        return configs, controllers, outputs, errors, source, cabinet_name

    errors.append(err)

    # Important : on ne retombe plus sur directoutputconfig.ini pour les tests.
    return configs, [], [], errors, "aucun cabinet JSON actif", "Cabinet non importé"


@dof_bp.route("/dof/import-api", methods=["POST"])
def dof_import_api_pincabos():
    import subprocess

    submitted_api_key = (request.form.get("apikey") or "").strip()
    saved_api_key = pincabos_dof_get_saved_api_key()
    api_key = submitted_api_key or saved_api_key
    force = "force" if request.form.get("force") == "1" else "noforce"

    if submitted_api_key:
        pincabos_dof_save_api_key(submitted_api_key)

    if not api_key:
        body = """
<div class="card">
  <h2>Import DOF via API échoué</h2>
  <p class="warn">La clé API est vide.</p>
  <p><a class="button" href="/dof">Retour DOF</a></p>
</div>
"""
        return page("DOF", body)

    try:
        helper = Path("/usr/local/sbin/pincabos-dof-online-api-import")
        if not helper.exists():
            body = """
<div class="card">
  <h2>Import DOF via API indisponible</h2>
  <p class="warn">
    Le helper API PinCabOS est absent :<br>
    <code>/usr/local/sbin/pincabos-dof-online-api-import</code>
  </p>
  <p>
    Pour importer le <strong>cabinet JSON</strong>, utilise plutôt DOF Commander :
  </p>
  <p>
    <a class="button" href="/dof/commander">Importer cabinet JSON dans DOF Commander</a>
    <a class="button secondary" href="/dof">Retour DOF</a>
  </p>
  <p>
    Pour importer les fichiers DOF Config Tool, utilise l’import ZIP manuel.
  </p>
</div>
"""
            return page("DOF", body)

        cmd = [str(helper), api_key, force]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=420)

        ok = proc.returncode == 0
        if ok:
            pincabos_backboard_menu_reapply()
        status = "Import DOF via API terminé" if ok else "Import DOF via API échoué"
        cls = "" if ok else "warn"
        safe_cmd = "/usr/local/sbin/pincabos-dof-online-api-import ****** " + force
        out = esc(proc.stdout or "")

        body = f"""
<div class="card">
  <h2>{esc(status)}</h2>
  <p class="{cls}">Commande : <code>{esc(safe_cmd)}</code></p>
  <pre style="max-height:560px; overflow:auto; background:#050007; border:1px solid #5f2a91; border-radius:12px; padding:12px;">{out}</pre>
  <p><a class="button" href="/dof">Retour DOF</a></p>
</div>
"""
        return page("DOF", body)

    except Exception as e:
        body = f"""
<div class="card">
  <h2>Import DOF via API échoué</h2>
  <p class="warn">{esc(str(e))}</p>
  <p><a class="button" href="/dof">Retour DOF</a></p>
</div>
"""
        return page("DOF", body)

@dof_bp.route("/dof/import-config", methods=["POST"])
def dof_import_config():
    import zipfile
    import shutil
    import traceback
    from werkzeug.utils import secure_filename

    target_dir = Path("/home/pinball/.local/share/VPinballX/10.8/directoutputconfig")
    upload_dir = Path("/opt/pincabos/uploads/dof")
    backup_dir = Path("/opt/pincabos/backups/dof-import")
    log_dir = Path("/opt/pincabos/logs")

    target_dir.mkdir(parents=True, exist_ok=True)
    upload_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file = log_dir / f"dof-import-{stamp}.log"

    def log(line):
        with log_file.open("a", encoding="utf-8") as f:
            f.write(str(line) + "\n")

    def response_card(title, message, ok=False, extra=""):
        css = "ok" if ok else "bad"
        body = f"""
<div class="card">
  <h2>{esc(title)}</h2>
  <p class="{css}">{message}</p>

  {extra}

  <p>Log import : <code>{esc(str(log_file))}</code></p>

  <p>
    <a class="button" href="/dof/commander">Retour DOF Commander</a>
    <a class="button secondary" href="/dof">Retour DOF</a>
  </p>
</div>
"""
        return page("DOF Commander", body)

    try:
        log("==================================================")
        log(f"# Modifié {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} par PinCabOS fonction(DOF Import Config Tool)")
        log("Import configuration DOF Config Tool")
        log("==================================================")

        log(f"request.files keys = {list(request.files.keys())}")

        upload_key = None
        if "dof_file" in request.files:
            upload_key = "dof_file"
        elif "dofzip" in request.files:
            # Compatibilité avec ancien formulaire PinCabOS.
            upload_key = "dofzip"
        elif len(request.files.keys()) > 0:
            # Fallback safe : premier fichier envoyé.
            upload_key = list(request.files.keys())[0]

        if not upload_key:
            log("ERREUR: aucun fichier uploadé.")
            return response_card("Import DOF", "Aucun fichier reçu. Le champ attendu est <code>dof_file</code>.", ok=False)

        log(f"Champ upload utilisé : {upload_key}")
        uploaded = request.files[upload_key]

        if uploaded is None or not uploaded.filename:
            log("ERREUR: fichier vide ou nom absent.")
            return response_card("Import DOF", "Nom de fichier invalide ou fichier vide.", ok=False)

        original_name = uploaded.filename
        filename = secure_filename(original_name)
        suffix = Path(filename).suffix.lower()

        log(f"Nom original : {original_name}")
        log(f"Nom sécurisé : {filename}")
        log(f"Extension : {suffix}")

        if suffix not in [".zip", ".ini", ".xml"]:
            log(f"ERREUR: format non supporté : {suffix}")
            return response_card(
                "Import DOF",
                f"Format non supporté : <code>{esc(filename)}</code><br>Formats acceptés : <code>.zip</code>, <code>.ini</code>, <code>.xml</code>.",
                ok=False
            )

        upload_path = upload_dir / f"{stamp}-{filename}"
        uploaded.save(str(upload_path))

        log(f"Fichier reçu : {upload_path}")
        log(f"Taille : {upload_path.stat().st_size if upload_path.exists() else 0} octets")

        backup_path = backup_dir / f"directoutputconfig.backup-{stamp}"

        if target_dir.exists():
            shutil.copytree(target_dir, backup_path, dirs_exist_ok=True)
            log(f"Backup créé : {backup_path}")

        imported = []

        def safe_copy(src, dest_name=None):
            src = Path(src)
            dest_name = dest_name or src.name

            # Empêche les chemins dangereux.
            dest_name = Path(dest_name).name

            dest = target_dir / dest_name
            dest.parent.mkdir(parents=True, exist_ok=True)

            shutil.copy2(src, dest)
            imported.append(dest)
            log(f"Copié : {src} -> {dest}")

        if suffix == ".zip":
            extract_dir = upload_dir / f"extract-{stamp}"
            extract_dir.mkdir(parents=True, exist_ok=True)

            try:
                with zipfile.ZipFile(upload_path, "r") as z:
                    bad = z.testzip()
                    if bad:
                        log(f"ERREUR ZIP: fichier corrompu : {bad}")
                        return response_card("Import DOF", f"ZIP invalide ou corrompu : <code>{esc(bad)}</code>", ok=False)

                    for member in z.namelist():
                        log(f"ZIP contient : {member}")

                    z.extractall(extract_dir)

            except Exception as e:
                log("ERREUR extraction ZIP:")
                log(traceback.format_exc())
                return response_card("Import DOF", f"Erreur extraction ZIP : <code>{esc(str(e))}</code>", ok=False)

            log(f"ZIP extrait dans : {extract_dir}")

            for f in extract_dir.rglob("*"):
                if not f.is_file():
                    continue

                name_l = f.name.lower()

                # On importe seulement les fichiers DOF utiles.
                if name_l.endswith(".xml") or name_l.endswith(".ini"):
                    safe_copy(f, f.name)

        elif suffix == ".ini":
            # Le fichier principal attendu par DOF.
            dest_name = "directoutputconfig.ini" if filename.lower() != "directoutputconfig.ini" else filename
            safe_copy(upload_path, dest_name)

        elif suffix == ".xml":
            safe_copy(upload_path, filename)

        try:
            subprocess.run(["chown", "-R", "pinball:pinball", str(target_dir)], timeout=15)
        except Exception as e:
            log(f"WARNING chown target_dir: {e}")

        meta = target_dir / "pincabos-dof-import.json"
        meta.write_text(json.dumps({
            "modified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "modified_by": "PinCabOS",
            "function": "DOF Import Config Tool",
            "uploaded_file": filename,
            "target_dir": str(target_dir),
            "imported": [str(p) for p in imported],
            "backup": str(backup_path),
            "log": str(log_file)
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        try:
            subprocess.run(["chown", "pinball:pinball", str(meta)], timeout=10)
        except Exception:
            pass

        rows = ""
        for p in imported:
            size = p.stat().st_size if p.exists() else 0
            rows += f"<tr><td><code>{esc(str(p))}</code></td><td>{size} octets</td></tr>"

        if not rows:
            rows = '<tr><td colspan="2"><span class="warn">Aucun fichier .ini/.xml importé depuis ce fichier.</span></td></tr>'

        extra = f"""
<table>
  <tr><td>Fichier envoyé</td><td><code>{esc(filename)}</code></td></tr>
  <tr><td>Dossier cible</td><td><code>{esc(str(target_dir))}</code></td></tr>
  <tr><td>Backup</td><td><code>{esc(str(backup_path))}</code></td></tr>
</table>

<h3>Fichiers importés</h3>
<table>
  <tr>
    <th style="text-align:left;">Fichier</th>
    <th style="text-align:left;">Taille</th>
  </tr>
  {rows}
</table>
"""
        log("Import terminé OK.")
        pincabos_backboard_menu_reapply()
        return response_card("Import DOF terminé", "Configuration DOF importée vers le dossier VPX.", ok=True, extra=extra)

    except Exception as e:
        log("ERREUR INTERNE IMPORT DOF:")
        log(traceback.format_exc())

        return response_card(
            "Import DOF — erreur",
            f"Erreur interne : <code>{esc(str(e))}</code>",
            ok=False,
            extra="<p>Le détail complet est dans le log ci-dessous.</p>"
        )


@dof_bp.route("/dof/import-cabinet-json", methods=["POST"])
def dof_import_cabinet_json():
    import shutil
    import traceback

    cabinet_dir = PINCABOS_DOF_CABINET_DIR
    active_pointer = PINCABOS_DOF_ACTIVE_CABINET
    upload_dir = Path("/opt/pincabos/uploads/dof")
    backup_dir = Path("/opt/pincabos/backups/dof-import")
    log_dir = Path("/opt/pincabos/logs")

    cabinet_dir.mkdir(parents=True, exist_ok=True)
    active_pointer.parent.mkdir(parents=True, exist_ok=True)
    upload_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file = log_dir / f"dof-import-cabinet-json-{stamp}.log"

    def log(line):
        with log_file.open("a", encoding="utf-8") as f:
            f.write(str(line) + "\n")

    def page_msg(title, msg, ok=False, extra=""):
        css = "ok" if ok else "bad"
        body = f"""
<div class="card">
  <h2>{esc(title)}</h2>
  <p class="{css}">{msg}</p>
  {extra}
  <p>Log : <code>{esc(str(log_file))}</code></p>
  <p>
    <a class="button" href="/dof/commander">Retour DOF Commander</a>
    <a class="button secondary" href="/dof">Retour DOF</a>
  </p>
</div>
"""
        return page("DOF Commander", body)

    try:
        log("==================================================")
        log(f"# Modifié {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} par PinCabOS fonction(DOF Import Cabinet JSON)")
        log("Import cabinet JSON robuste : extraction devices seulement")
        log("==================================================")

        if "cabinet_json_file" not in request.files:
            return page_msg("Import cabinet JSON", "Aucun fichier reçu.", ok=False)

        uploaded = request.files["cabinet_json_file"]
        original_name = Path(uploaded.filename or "").name

        if not original_name.lower().endswith(".json"):
            return page_msg("Import cabinet JSON", f"Format invalide : <code>{esc(original_name)}</code>", ok=False)

        upload_path = upload_dir / f"{stamp}-{original_name}"
        uploaded.save(str(upload_path))

        raw = upload_path.read_text(errors="replace").lstrip()

        # Important : raw_decode lit le premier objet JSON valide et permet d'ignorer le texte en trop.
        decoder = json.JSONDecoder()
        data, end = decoder.raw_decode(raw)
        extra = raw[end:].strip()

        if extra:
            log(f"WARNING: contenu en trop ignoré après le premier JSON valide : {len(extra)} caractères")
            log("Début extra:")
            log(repr(extra[:500]))

        cab_type = str(data.get("type") or "").lower()
        cab_name = str(data.get("name") or "Cabinet sans nom")
        devices = data.get("devices") or []

        if cab_type and cab_type != "cabinet":
            log(f"WARNING: type JSON inattendu: {cab_type}")

        if not isinstance(devices, list):
            return page_msg(
                "Import cabinet JSON",
                "Le JSON ne contient pas une liste <code>devices</code> valide.",
                ok=False
            )

        # On garde seulement les champs utiles au DOF Commander local.
        clean = {
            "type": data.get("type", "cabinet"),
            "name": cab_name,
            "created": data.get("created", ""),
            "devices": [],
            "combos": data.get("combos") or {},
            "variables": data.get("variables") or {},
            "mx": data.get("mx") or [],
            "pincabos_import": {
                "modified_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "modified_by": "PinCabOS",
                "function": "DOF Import Cabinet JSON",
                "source_file": original_name,
                "ignored_extra_after_json": bool(extra),
                "ignored_extra_chars": len(extra),
            }
        }

        for dev in devices:
            if not isinstance(dev, dict):
                continue

            clean["devices"].append({
                "name": dev.get("name") or dev.get("Name") or "Device",
                "outputs": dev.get("outputs") or dev.get("Outputs") or 0,
                "controller_id": dev.get("controller_id") or dev.get("ControllerId") or dev.get("id") or "",
                "assignments": dev.get("assignments") or dev.get("Assignments") or {},
            })

        cabinet_name, controllers, outputs = dof_commander_inventory_from_cabinet_json_pcb(clean)

        target = cabinet_dir / original_name

        if target.exists():
            backup = backup_dir / f"{original_name}.backup-{stamp}"
            shutil.copy2(target, backup)
            log(f"Backup ancien JSON : {backup}")

        # Écriture propre : un seul JSON valide.
        target.write_text(json.dumps(clean, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        active_pointer.write_text(str(target) + "\n", encoding="utf-8")

        try:
            subprocess.run(["chown", "pinball:pinball", str(target), str(active_pointer)], timeout=10)
        except Exception:
            pass

        log(f"Nom original : {original_name}")
        log(f"Cabinet : {cabinet_name}")
        log(f"Fichier actif : {target}")
        log(f"Pointeur actif : {active_pointer}")
        log(f"Devices reconnus : {len(clean['devices'])}")
        log(f"Outputs/Toys reconnus : {len(outputs)}")

        rows = ""
        for d in clean["devices"]:
            assignments = d.get("assignments") or {}
            rows += f"""
<tr>
  <td><code>{esc(str(d.get("name")))}</code></td>
  <td><code>{esc(str(d.get("controller_id")))}</code></td>
  <td><code>{esc(str(d.get("outputs")))}</code></td>
  <td><code>{len(assignments)}</code></td>
</tr>
"""

        warning = ""
        if extra:
            warning = f"""
<p class="warn">
  Le fichier contenait du texte en trop après le JSON principal.
  PinCabOS l’a ignoré et a sauvegardé une version propre.
</p>
"""

        extra_html = f"""
{warning}
<table>
  <tr><td>Nom du cab</td><td><code>{esc(cabinet_name)}</code></td></tr>
  <tr><td>Nom du fichier conservé</td><td><code>{esc(original_name)}</code></td></tr>
  <tr><td>Fichier PinCabOS</td><td><code>{esc(str(target))}</code></td></tr>
  <tr><td>Contenu extra ignoré</td><td><code>{len(extra)} caractères</code></td></tr>
</table>

<h3>Périphériques importés</h3>
<table>
  <tr>
    <th style="text-align:left;">Device</th>
    <th style="text-align:left;">Controller ID</th>
    <th style="text-align:left;">Outputs</th>
    <th style="text-align:left;">Assignments</th>
  </tr>
  {rows}
</table>
"""
        return page_msg(
            "Cabinet JSON importé",
            "La configuration du cabinet a été analysée et nettoyée pour DOF Commander.",
            ok=True,
            extra=extra_html
        )

    except Exception as e:
        log("ERREUR IMPORT CABINET JSON:")
        log(traceback.format_exc())

        return page_msg(
            "Erreur import Cabinet JSON",
            f"Erreur : <code>{esc(str(e))}</code>",
            ok=False
        )


@dof_bp.route("/dof/commander")
def dof_commander_page():
    # PINCABOS_DOF_COMMANDER_SIMPLE_V1 : le matériel branché est listé sur
    # /dof et géré dans /dof/hardware ; cette page se concentre sur les outputs.
    configs, controllers, outputs, errors, inventory_source, cabinet_name = dof_commander_load_inventory_active_pcb()

    config_rows = []
    for f in configs:
        config_rows.append(f"""
        <tr>
          <td><code>{esc(str(f))}</code></td>
          <td>{esc(f.suffix.lower())}</td>
          <td>{f.stat().st_size if f.exists() else 0} octets</td>
        </tr>
        """)

    if not config_rows:
        config_rows.append("""
        <tr><td colspan="3"><span class="warn">Aucun fichier DOF XML/INI trouvé.</span></td></tr>
        """)

    controller_rows = []
    for c in controllers:
        controller_rows.append(f"<tr><td><code>{esc(c)}</code></td></tr>")

    if not controller_rows:
        controller_rows.append('<tr><td><span class="warn">Aucun contrôleur trouvé dans les configs.</span></td></tr>')

    output_rows = []
    max_rows = 250

    for i, o in enumerate(outputs[:max_rows], start=1):
        output_id = o.get("local_output") or o.get("number") or ""
        controller = o.get("controller") or "auto"
        testable = bool(o.get("testable", True))

        device_type = o.get("device_type", "")
        assigned_toy = o.get("assigned_toy", "")

        if testable:
            action_html = f"""
            <label class="dof-toggle-wrap">
              <input class="dof-output-toggle"
                type="checkbox"
                data-controller="{esc(controller)}"
                data-output="{esc(str(output_id))}"
                data-name="{esc(o.get("name", ""))}">
              <span class="dof-toggle-slider"></span>
              <span class="dof-toggle-label">OFF</span>
            </label>
            """
        else:
            action_html = '<span class="warn">non testable</span>'

        output_rows.append(f"""
        <tr>
          <td><span class="dof-output-code">{esc(str(i))}</span></td>
          <td>
            <span class="dof-badge {('dof-badge-testable' if testable else 'dof-badge-info')}">{esc(o.get("type", ""))}</span>
          </td>
          <td>
            <span class="dof-output-name">{esc(o.get("name", ""))}</span>
            <span class="dof-output-meta">{esc(device_type)}</span>
          </td>
          <td><span class="dof-output-code">{esc(str(output_id))}</span></td>
          <td>
            <span class="dof-device-name">{esc(controller)}</span>
            <span class="dof-device-sub">{esc(o.get("source", ""))}</span>
          </td>
          <td>
            <span class="dof-output-meta">{esc(o.get("value", ""))}</span>
            {('<span class="dof-output-meta">Assigned toy : <code>' + esc(str(assigned_toy)) + '</code></span>') if assigned_toy else ''}
          </td>
          <td style="white-space:nowrap;">{action_html}</td>
        </tr>
        """)

    if not output_rows:
        output_rows.append('<tr><td colspan="7"><span class="warn">Aucun output/toy trouvé dans les configs.</span></td></tr>')

    error_html = ""
    if errors:
        error_html = "<div class='card' style='margin-top:20px;'><h2>Erreurs lecture config</h2><pre>" + esc("\\n".join(errors)) + "</pre></div>"

    more_note = ""
    if len(outputs) > max_rows:
        more_note = f"<p class='warn'>Affichage limité à {max_rows} outputs sur {len(outputs)} trouvés.</p>"

    body = f"""
<div class="grid">
  <div class="card">
    <h2>DOF Commander</h2>
    <p>
      Analyse la configuration réelle du cabinet, affiche les contrôleurs et outputs physiques,
      puis permet de lancer des tests contrôlés.
    </p>
    <table>
      <tr><td>Cabinet actif</td><td><code>{esc(cabinet_name)}</code></td></tr>
      <tr><td>Source inventaire outputs</td><td><code>{esc(inventory_source)}</code></td></tr>
    </table>

    <p>
      <a class="button" href="https://configtool.vpuniverse.com/" target="_blank">Ouvrir DOF Config Tool</a>
      <!-- PINCABOS_DUDESCAB_CONFIG_BUTTON_V3 BEGIN -->
      <a class="button" href="/DudesCabConfig">DudesCabConfig</a>
      <!-- PINCABOS_DUDESCAB_CONFIG_BUTTON_V3 END -->
      <a class="button" href="/dof/hardware">Mat&eacute;riel &amp; cabinet.xml</a>
      <a class="button secondary" href="/dof">Retour DOF</a>
    </p>

    <p class="warn">
      Les tests sont limités en durée pour éviter de laisser un toy activé trop longtemps.
    </p>
    <p><small>
      Le matériel branché est listé sur <a href="/dof">la page DOF</a> et géré dans
      <a href="/dof/hardware">Matériel &amp; cabinet.xml</a> ; cette page sert à
      tester les <strong>outputs</strong>.
    </small></p>
  </div>
</div>

<details style="margin-top:20px;">
  <summary>Avancé : contrôleurs et fichiers des configs DOF</summary>
  <div class="card" style="margin-top:10px;">
    <h2>Contrôleurs dans les configs</h2>
    <table>
      {''.join(controller_rows)}
    </table>
  </div>
  <div class="card" style="margin-top:10px;">
    <h2>Fichiers DOF trouvés</h2>
    <p>Dossier cible : <code>/home/pinball/.local/share/VPinballX/10.8/directoutputconfig</code></p>
    <table>
      <tr><th style="text-align:left;">Fichier</th><th style="text-align:left;">Type</th><th style="text-align:left;">Taille</th></tr>
      {''.join(config_rows)}
    </table>
  </div>
</details>

<div class="card" style="margin-top:20px;">
  <div class="dof-section-title">
    <h2>Outputs / Toys configurés — {esc(cabinet_name)}</h2>
    <span class="dof-badge dof-badge-info">{esc(inventory_source)}</span>
  </div>

  <div class="dof-test-panel dof-cabinet-json-import">
    <h3>Importer cabinet JSON</h3>

    <p>
      Le fichier <code>.json</code> du cabinet sert à associer les tests DOF Commander
      aux bonnes sorties physiques de vos périphériques : LedWiz, WS2811, Dude’s Cab,
      Pinscape, PacLed, etc.
    </p>

    <p><strong>Pour le télécharger depuis DOF Config Tool V3 :</strong></p>

    <ol>
      <li>Va sur <a href="https://configtool.vpuniverse.com/app/cabinets" target="_blank">DOF Config Tool V3 — Cabinets</a>.</li>
      <li>Sélectionne ton cabinet.</li>
      <li>Clique sur <strong>Action</strong>.</li>
      <li>Clique sur <strong>Export Cabinet</strong>.</li>
      <li>Importe le fichier <code>.json</code> ici.</li>
    </ol>

    <form method="post" action="/dof/import-cabinet-json" enctype="multipart/form-data">
      <input type="file" name="cabinet_json_file" accept=".json" required>
      <button class="button secondary" type="submit">Importer cabinet JSON</button>
    </form>
  </div>


  


  {more_note}
<div class="dof-test-panel dof-test-panel-compact">
    <div class="dof-test-head">
      <div>
        <h3>Réglages de test</h3>
        <span class="dof-muted">Appliqués aux toggles ON. OFF coupe immédiatement.</span>
      </div>
    </div>

    <div class="dof-test-controls">
      <div class="dof-control">
        <label>Durée</label>
        <div class="dof-range-line">
          <input id="dof-test-duration" type="range" min="50" max="5000" value="500" step="50"
            oninput="document.getElementById('dof-test-duration-label').textContent=this.value + ' ms'">
          <code id="dof-test-duration-label">500 ms</code>
        </div>
      </div>

      <div class="dof-control dof-control-small">
        <label>Mode</label>
        <select id="dof-test-mode">
          <option value="onoff">ON / OFF</option>
          <option value="pulse">Pulse / Strobe</option>
          <option value="doublepulse">Double Pulse</option>
          <option value="fadein">Fade in</option>
          <option value="fadeout">Fade out</option>
          <option value="sine">Sine</option>
        </select>
      </div>

      <div class="dof-control dof-control-auto">
        <label>Auto repeat</label>
        <label class="dof-mini-check">
          <input id="dof-test-auto-repeat" type="checkbox">
          <span>Répéter tant que le toggle est ON</span>
        </label>
      </div>

      <div class="dof-control">
        <label>Pause repeat</label>
        <div class="dof-range-line">
          <input id="dof-test-repeat-delay" type="range" min="50" max="5000" value="500" step="50"
            oninput="document.getElementById('dof-test-repeat-delay-label').textContent=this.value + ' ms'">
          <code id="dof-test-repeat-delay-label">500 ms</code>
        </div>
      </div>

      <div class="dof-control">
        <label>Intensité</label>
        <div class="dof-range-line">
          <input id="dof-test-intensity" type="range" min="1" max="255" value="255" step="1"
            oninput="document.getElementById('dof-test-intensity-label').textContent=this.value">
          <code id="dof-test-intensity-label">255</code>
        </div>
      </div>
    </div>
  </div>

  <table class="dof-output-table">
    <tr>
      <th style="text-align:left;">#</th>
      <th style="text-align:left;">Type</th>
      <th style="text-align:left;">Nom</th>
      <th style="text-align:left;">Output local</th>
      <th style="text-align:left;">Périphérique</th>
      <th style="text-align:left;">Association JSON</th>
      <th style="text-align:left;">Action</th>
    </tr>
    {''.join(output_rows)}
  </table>
</div>

<div id="dof-commander-log-panel" class="card" style="margin-top:20px; display:none; border-color:#ffb000;">
  <h2>Log test output</h2>
  <table>
    <tr><td>Contrôleur</td><td><code id="dof-cmd-controller">-</code></td></tr>
    <tr><td>Output</td><td><code id="dof-cmd-output">-</code></td></tr>
    <tr><td>Action</td><td><code id="dof-cmd-action">-</code></td></tr>
    <tr><td>Mode</td><td><code id="dof-cmd-mode">-</code></td></tr>
    <tr><td>Durée</td><td><code id="dof-cmd-duration">-</code></td></tr>
  </table>
  <pre id="dof-commander-log" style="max-height:360px; overflow:auto; background:#050007; border:1px solid #5f2a91; border-radius:12px; padding:12px;">Aucun test lancé.</pre>
</div>

{error_html}

<link rel="stylesheet" href="/static/dof-commander-pro.css?v=20260518-toggle-css-pure">
<script src="/static/dof-commander-onoff.js?v=20260518-toggle-css-pure"></script>
"""
    return page("DOF Commander", body)


@dof_bp.route("/api/dof/commander/test", methods=["POST"])
def api_dof_commander_test():
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        data = {}

    controller = str(data.get("controller", "auto"))[:80]
    output = str(data.get("output", "0"))[:80]
    action = str(data.get("action", "on"))[:20]
    mode = str(data.get("mode", "onoff"))[:40]
    duration_ms = str(data.get("duration_ms", "500"))[:20]
    intensity = str(data.get("intensity", "255"))[:20]

    if action not in ["on", "off"]:
        action = "on"

    script = str(pco_script("dof_commander_test_output"))
    cmd = [
        script,
        controller,
        output,
        action,
        mode,
        duration_ms,
        intensity,
    ]

    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )
        log = (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        log = f"Erreur exécution test: {e}"

    payload = {
        "ok": True,
        "controller": controller,
        "output": output,
        "action": action,
        "mode": mode,
        "duration_ms": duration_ms,
        "intensity": intensity,
        "log": log,
    }

    return current_app.response_class(json.dumps(payload), mimetype="application/json")


@dof_bp.route("/dof")
def dof_page():
    # PINCABOS_DOF_PAGE_SIMPLE_V1
    cfg_path, file_rows = dof_file_status()
    summary, device_rows, raw_devices = detect_dof_devices()
    logs = dof_logs()

    if pincabos_dof_get_saved_api_key():
        key_hint = "clé enregistrée — laisser vide pour la réutiliser"
    else:
        key_hint = "coller ici ta clé API DOF Config Tool"

    body = f"""
<div class="grid">
  <div class="card">
    <h2>DOF — Sorties &amp; feedback</h2>
    <p>Service VPinFE : <code>{esc(service_status("pincabos-vpinfe.service"))}</code></p>
    <p>{summary}</p>
    <table>
      <tr><th style="text-align:left;">Carte</th><th style="text-align:left;">Périphérique</th><th style="text-align:left;">cabinet.xml</th></tr>
      {device_rows}
    </table>
    <p><small>
      Les extensions branchées <em>sur</em> une carte (Walter, MOSLight... sur la Dude's Cab)
      ne sont pas des périphériques USB séparés : elles se configurent dans
      <a href="/DudesCabConfig">DudesCabConfig</a> et le DOF Config Tool.
    </small></p>
    <p>
      <a class="button" href="/dof/hardware">Mat&eacute;riel &amp; cabinet.xml</a>
      <a class="button secondary" href="/dof/commander">DOF Commander</a>
    </p>
  </div>

  <div class="card">
    <h2>Import DOF Config Tool</h2>
    <p>
      Les effets par table (<code>directoutputconfigNN.ini</code>) viennent de
      <a href="https://configtool.vpuniverse.com/" target="_blank">DOF Config Tool</a>.<br>
      Destination : <code>{esc(cfg_path)}</code>
    </p>

    <form method="post" action="/dof/import-config" enctype="multipart/form-data">
      <input type="hidden" name="mode" value="upload">
      <input type="file" name="dof_file" accept=".zip,.ini,.xml" style="display:block; margin:8px 0; width:100%;">
      <button class="button" type="submit">Importer un ZIP DOF</button>
    </form>

    <form method="post" action="/dof/import-api" style="margin-top:14px;">
      <label for="dof-api-key"><strong>Import automatique par clé API</strong></label>
      <input id="dof-api-key" type="password" name="apikey" value="" placeholder="{esc(key_hint)}" autocomplete="off" style="display:block; margin:8px 0; width:100%; padding:10px; border-radius:10px; border:1px solid #5f2a91; background:#050007; color:white;">
      <label style="display:block; margin:8px 0;">
        <input type="checkbox" name="force" value="1" checked>
        Forcer le téléchargement / remplacement
      </label>
      <button class="button" type="submit">Importer via API</button>
    </form>

    <form method="post" action="/dof/import-config" style="margin-top:10px;">
      <input type="hidden" name="mode" value="share">
      <button class="button secondary" type="submit">Importer le dernier ZIP depuis /home/pinball/Share</button>
    </form>
  </div>
</div>

<details style="margin-top:20px;">
  <summary>Avancé : dépendances par famille de cartes, fichiers et logs</summary>
  {dof_utils_card_html()}
  {dof_detection_summary_card(summary, raw_devices, logs, file_rows)}
</details>
"""
    return page("Outputs", body)


def register(app, page_fn):
    """Enregistre les pages DOF / Outputs sur l'application."""
    global page
    page = page_fn
    app.register_blueprint(dof_bp)
