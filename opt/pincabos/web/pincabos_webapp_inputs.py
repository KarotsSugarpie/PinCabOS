# PinCabOS WebApp module: Inputs / HID / Map Commander.
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

from pincabos_webapp_gabarit import page

ROUTES: list[tuple[str, dict, object]] = []
BEFORE_REQUESTS: list[object] = []
AFTER_REQUESTS: list[object] = []

# PINCABOS_MAP_COMMANDER_ICON_FILEMAP_V1
MAP_COMMANDER_ICON_FILES = {
    "LeftFlipperKey": "Flipper_gauche-LeftFlipperKey.png",
    "RightFlipperKey": "Flipper_droit-RightFlipperKey.png",
    "StagedLeftFlipperKey": "Flipper_gauche_staged_upper-StagedLeftFlipperKey.png",
    "StagedRightFlipperKey": "Flipper_droit_staged_upper-StagedRightFlipperKey.png",
    "LeftMagnaSave": "Magna_Save_gauche-LeftMagnaSave.png",
    "RightMagnaSave": "Magna_Save_droit-RightMagnaSave.png",
    "LeftMagnaSave2": "Magna_Save_gauche_2-LeftMagnaSave2.png",
    "RightMagnaSave2": "Magna_Save_droit_2-RightMagnaSave2.png",
    "StartGameKey": "Start-StartGameKey.png",
    "StartGameKey2": "Start_2-StartGameKey2.png",
    "AddCreditKey": "Coin_credit-AddCreditKey.png",
    "AddCreditKey2": "Coin_credit_2-AddCreditKey2.png",
    "PlungerKey": "Plunger_Launch_Ball-PlungerKey.png",
    "LockbarKey": "Lockbar_Fire-LockbarKey.png",
    "ExitGameKey": "Exit-ExitGameKey.png",
    "PauseKey": "Pause-PauseKey.png",
    "LeftTiltKey": "Nudge_gauche_digital-LeftTiltKey.png",
    "RightTiltKey": "Nudge_droite_digital-RightTiltKey.png",
    "CenterTiltKey": "Nudge_centre_digital-CenterTiltKey.png",
    "MechanicalTilt": "Tilt_mecanique-MechanicalTilt.png",
    "VolumeUpKey": "Volume_plus-VolumeUpKey.png",
    "VolumeDownKey": "Volume_moins-VolumeDownKey.png",
    "CoinDoorKey": "Coin_Door-CoinDoorKey.png",
    "ServiceCancelKey": "Service_Cancel-ServiceCancelKey.png",
    "ServiceDownKey": "Service_Down-ServiceDownKey.png",
    "ServiceUpKey": "Service_Up-ServiceUpKey.png",
    "ServiceEnterKey": "Service_Enter-ServiceEnterKey.png",
    "BuyInKey": "Buy_In_Extra_Ball-BuyInKey.png",
    "FrameCountKey": "Frame_Counter_FPS-FrameCountKey.png",
    "DebuggerKey": "Debugger-DebuggerKey.png",
    "Enable3DKey": "Activer_3D-Enable3DKey.png",
    "JoyCustom1Key": "Custom_1-JoyCustom1Key.png",
    "JoyCustom2Key": "Custom_2-JoyCustom2Key.png",
    "JoyCustom3Key": "Custom_3-JoyCustom3Key.png",
    "JoyCustom4Key": "Custom_4-JoyCustom4Key.png"
}


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

def register(host_app, runtime_globals=None):
    """Enregistre les routes et crochets du module. Autonome : ses dépendances sont importées en tête
    (PINCABOS_WEBAPP_AUTONOMIE_V1) ; `runtime_globals` n'est plus lu."""
    for before_func in BEFORE_REQUESTS:
        host_app.before_request(before_func)
    for after_func in AFTER_REQUESTS:
        host_app.after_request(after_func)
    for rule, options, view_func in ROUTES:
        host_app.add_url_rule(rule, endpoint=view_func.__name__, view_func=view_func, **options)



# PINCABOS_VPX_INPUT_V1 : depuis la refonte des entrées de VPX (oct. 2025) les
# boutons vivent dans [Input] (Mapping.<Action> = Key;<scancode> | SDLJoy_<guid>_<n>;<bouton>).
# La conversion evdev -> SDL, l'écriture de l'ini et la recopie VPinFE sont dans
# /opt/pincabos/tools/pincabos_vpx_input.py (CLI : pincabos-vpx-input).
import sys as _sys
if "/opt/pincabos/tools" not in _sys.path:
    _sys.path.insert(0, "/opt/pincabos/tools")
import pincabos_vpx_input as vpxin  # noqa: E402
PINCABOS_INPUTS_INI = str(vpxin.ini_path())
# action VPX -> ancienne clé (pour retrouver l'icône livrée avec Map Commander)
MAP_COMMANDER_LEGACY_KEY_BY_ACTION = {v: k for k, v in vpxin.LEGACY_KEYS.items() if v}


PINCABOS_INPUTS_CFG = "/opt/pincabos/config/inputs-commander.json"


# Ancienne table (codes DIK) : VPX ne lit plus ces clés ; voir vpxin.ACTIONS.
PINCABOS_INPUT_KEYMAP = [
    ("LeftFlipperKey", "Flipper gauche", "42"),
    ("RightFlipperKey", "Flipper droit", "54"),
    ("StagedLeftFlipperKey", "Flipper gauche staged / upper", ""),
    ("StagedRightFlipperKey", "Flipper droit staged / upper", ""),
    ("LeftMagnaSave", "Magna Save gauche", "29"),
    ("RightMagnaSave", "Magna Save droit", "97"),
    ("LeftMagnaSave2", "Magna Save gauche 2", ""),
    ("RightMagnaSave2", "Magna Save droit 2", ""),
    ("StartGameKey", "Start", "2"),
    ("StartGameKey2", "Start 2", ""),
    ("AddCreditKey", "Coin / crédit", "6"),
    ("AddCreditKey2", "Coin / crédit 2", ""),
    ("PlungerKey", "Plunger / Launch Ball", "28"),
    ("LockbarKey", "Lockbar Fire", ""),
    ("ExitGameKey", "Exit", "1"),
    ("PauseKey", "Pause", ""),
    ("LeftTiltKey", "Nudge gauche digital", "44"),
    ("RightTiltKey", "Nudge droite digital", "53"),
    ("CenterTiltKey", "Nudge centre digital", "57"),
    ("MechanicalTilt", "Tilt mécanique", "20"),
    ("VolumeUpKey", "Volume +", ""),
    ("VolumeDownKey", "Volume -", ""),
    ("CoinDoorKey", "Coin Door", ""),
    ("ServiceCancelKey", "Service Cancel", ""),
    ("ServiceDownKey", "Service Down", ""),
    ("ServiceUpKey", "Service Up", ""),
    ("ServiceEnterKey", "Service Enter", ""),
    ("BuyInKey", "Buy In / Extra Ball", ""),
    ("FrameCountKey", "Frame Counter / FPS", ""),
    ("DebuggerKey", "Debugger", ""),
    ("Enable3DKey", "Activer 3D", ""),
    ("JoyCustom1Key", "Custom 1", "22"),
    ("JoyCustom2Key", "Custom 2", "23"),
    ("JoyCustom3Key", "Custom 3", "24"),
    ("JoyCustom4Key", "Custom 4", "25"),
]


PINCABOS_INPUT_PLAYERMAP = [
    ("PBWEnabled", "Nudge analogique VPX activé", "0"),
    ("NudgeStrength", "Force visuelle du nudge", "0.01"),
    ("LRAxis", "Axe nudge gauche / droite", ""),
    ("UDAxis", "Axe nudge avant / arrière", ""),
    ("LRAxisFlip", "Inverser axe gauche / droite", "0"),
    ("UDAxisFlip", "Inverser axe avant / arrière", "0"),
    ("PBWAccelGainX", "Gain accélération X", "1.00"),
    ("PBWAccelGainY", "Gain accélération Y", "1.00"),
    ("PlungerAxis", "Axe plunger VPX", ""),
    ("ReversePlungerAxis", "Inverser axe plunger", "0"),
]


PINCABOS_INPUTS_DEFAULT_CFG = {
    "input_mode": "auto",
    "capture_backend": "evdev",
    "preferred_device": "",
    "dudes_profile": "off",
    "dudes_shift_enabled": False,
    "dudes_shift_input": "",
    "dudes_nightmode_input": "",
    "stabilization_delay_ms": 20,
    "nudge_axis_x": "",
    "nudge_axis_y": "",
    "nudge_axis_z": "",
    "nudge_deadzone": "0.08",
    "nudge_gain_x": "1.0",
    "nudge_gain_y": "1.0",
    "nudge_invert_x": False,
    "nudge_invert_y": False,
    "virtual_tilt_enabled": False,
    "virtual_tilt_threshold": "0.85",
    "plunger_min": "0",
    "plunger_max": "65535",
    "plunger_deadzone": "0.03",
    "plunger_maxfield": "1.00",
    "nudge_maxfield": "1.00",
    "plunger_invert": False,
    "launch_ball_emulation": "off",
}


def inputs_esc(value):
    import html
    return html.escape(str(value if value is not None else ""), quote=True)


def inputs_cmd(cmd, timeout=5):
    import subprocess
    try:
        r = subprocess.run(cmd, shell=True, text=True, capture_output=True, timeout=timeout)
        return ((r.stdout or "") + (r.stderr or "")).strip()
    except Exception as e:
        return str(e)


def inputs_load_cfg():
    from pathlib import Path
    import json
    cfg = dict(PINCABOS_INPUTS_DEFAULT_CFG)
    p = Path(PINCABOS_INPUTS_CFG)
    if p.exists():
        try:
            data = json.loads(p.read_text(errors="replace"))
            if isinstance(data, dict):
                cfg.update(data)
        except Exception:
            pass
    return cfg


def inputs_save_cfg(cfg):
    from pathlib import Path
    import json
    import subprocess
    p = Path(PINCABOS_INPUTS_CFG)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + chr(10))
    try:
        subprocess.run(["chown", "pinball:pinball", str(p)], timeout=10)
    except Exception:
        pass


def inputs_read_ini():
    from pathlib import Path
    p = Path(PINCABOS_INPUTS_INI)
    lines = p.read_text(errors="replace").splitlines() if p.exists() else []
    found = {}
    section = ""
    for line in lines:
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            section = s.strip("[]")
            continue
        if "=" in line and not s.startswith((";", "#")):
            k, v = line.split("=", 1)
            found[k.strip()] = {"value": v.strip(), "section": section}
    return lines, found


def inputs_find_section(lines, wanted):
    for i, line in enumerate(lines):
        if line.strip().lower() == "[" + wanted.lower() + "]":
            end = len(lines)
            for j in range(i + 1, len(lines)):
                s = lines[j].strip()
                if s.startswith("[") and s.endswith("]"):
                    end = j
                    break
            return i, end
    return None, None


def _inputs_rewrite_section(lines, section_name, values, managed_keys, label):
    """Réécrit les clés gérées d'une section (bloc daté), sans toucher au reste."""
    from datetime import datetime
    start, end = inputs_find_section(lines, section_name)
    if start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append("[" + section_name + "]")
        start = len(lines) - 1
        end = len(lines)
    before = lines[:start + 1]
    section = lines[start + 1:end]
    after = lines[end:]
    cleaned = []
    for line in section:
        stripped = line.strip()
        if "PinCabOS fonction(" + label + ")" in line:
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
    comment = "; Modifié " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " par PinCabOS fonction(" + label + ")"
    new_part = [comment] + [key + " = " + str(values.get(key, "")) for key in managed_keys]
    return before + cleaned + new_part + after


def inputs_rewrite_ini(mappings, player_values, vpinfe_policy=None):
    """PINCABOS_VPX_INPUT_V1 : écrit les boutons dans [Input] au format que VPX lit,
    purge les anciennes clés DIK, conserve l'écriture des paramètres nudge de
    [Player], puis recopie la navigation VPinFE. Renvoie un compte rendu."""
    ini_file = vpxin.ini_path()
    if not ini_file.exists():
        raise FileNotFoundError(str(ini_file))
    report = vpxin.write_mappings(mappings, path=ini_file, backup=True)
    ini = vpxin.VpxIni(ini_file)
    player_keys = [k for k, label, default in PINCABOS_INPUT_PLAYERMAP]
    ini.lines = _inputs_rewrite_section(ini.lines, "Player", player_values, player_keys, "Inputs Commander Nudge")
    ini.save(backup=False)
    all_mappings = dict(vpxin.ACTION_DEFAULTS)
    all_mappings.update(vpxin.VpxIni(ini_file).input_mappings())
    report["decoded"] = {a: vpxin.mapping_label(t, vpxin.VpxIni(ini_file).device_names()) for a, t in report["mappings"].items()}
    vpinfe = {}
    if vpxin.VPINFE_INI.exists():
        values = vpxin.vpinfe_values(all_mappings, vpinfe_policy)
        vpinfe = vpxin.write_vpinfe(values)
        vpinfe["values"] = values
    report["vpinfe"] = vpinfe
    return report


def inputs_vpx_running():
    try:
        r = subprocess.run(["pgrep", "-f", "VPinballX"], capture_output=True, text=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def inputs_report_html(title, report, intro=""):
    """Compte rendu après écriture : ce qui est dans l'ini VPX, ce qui est dans VPinFE."""
    rows = []
    for action, text in report.get("mappings", {}).items():
        rows.append("<tr><td>" + inputs_esc(vpxin.ACTION_LABELS.get(action, action)) + "</td><td><code>" + inputs_esc(action)
                    + "</code></td><td>" + inputs_esc(report.get("decoded", {}).get(action, "")) + "</td><td><code>" + inputs_esc(text or "—") + "</code></td></tr>")
    vp = report.get("vpinfe") or {}
    vp_rows = []
    for fn, label in vpxin.VPINFE_FUNCTIONS:
        v = (vp.get("values") or {}).get(fn)
        if not v:
            continue
        notes = " ; ".join(v.get("notes", []))
        vp_rows.append("<tr><td>" + inputs_esc(label) + "</td><td><code>" + inputs_esc(v.get("action") or "—") + "</code></td><td><code>"
                       + inputs_esc(v.get("joy") or "—") + "</code></td><td><code>" + inputs_esc(v.get("keys") or "—") + "</code></td><td class='warn'>" + inputs_esc(notes) + "</td></tr>")
    running = inputs_vpx_running()
    if vp:
        restart = ("<p class='warn'>Une table VPX est en cours : redémarre VPinFE plus tard pour ne pas l'interrompre.</p>" if running else
                   "<form method='post' action='/inputs/vpinfe-restart' style='display:inline'><button class='button' type='submit'>Redémarrer VPinFE maintenant</button></form>")
        vp_block = ("<h2>Navigation VPinFE</h2><p>Écrit dans <code>" + inputs_esc(vp.get("path", "")) + "</code>. VPinFE lit ce fichier au démarrage : "
                    "il faut le redémarrer pour appliquer.</p><table class='map-table'><tr><th>Fonction VPinFE</th><th>Action VPX</th><th>Bouton</th><th>Touches</th><th>Remarque</th></tr>"
                    + "".join(vp_rows) + "</table><p>" + restart + "</p>")
    else:
        vp_block = "<p class='warn'>VPinFE non installé sur ce cab (pas de vpinfe.ini) : navigation non recopiée.</p>"
    body = """
<div class="card">
  <h1>""" + inputs_esc(title) + """</h1>
  """ + intro + """
  <p class="good">Mapping écrit dans <code>""" + inputs_esc(report.get("path", "")) + """</code>, section <code>[Input]</code>.
  VPX le prend en compte au prochain lancement de table.</p>
  <p>Sauvegarde : <code>""" + inputs_esc(report.get("backup") or "aucune") + """</code>""" + (
        " · anciennes clés DIK retirées : " + str(report.get("purged")) if report.get("purged") else "") + """</p>
  <div class="map-table-wrap"><table class="map-table"><tr><th>Fonction</th><th>Action VPX</th><th>Lecture</th><th>Valeur écrite</th></tr>""" + "".join(rows) + """</table></div>
  """ + vp_block + """
  <p><a class="button" href="/inputs/map-commander">Retour Map Commander</a></p>
</div>
"""
    return page("Inputs", body)


@route("/inputs/vpinfe-restart", methods=["POST"])
def inputs_vpinfe_restart():
    if inputs_vpx_running():
        body = "<div class='card'><h1>VPinFE non redémarré</h1><p class='warn'>Une table VPX est en cours.</p><p><a class='button' href='/inputs/map-commander'>Retour Map Commander</a></p></div>"
        return page("Inputs", body)
    try:
        subprocess.run(["/usr/bin/sudo", "-n", "/usr/bin/systemctl", "restart", "pincabos-vpinfe.service"], timeout=30, check=False)
        body = "<div class='card'><h1>VPinFE redémarré</h1><p class='good'>La navigation utilise les nouveaux boutons.</p><p><a class='button' href='/inputs/map-commander'>Retour Map Commander</a></p></div>"
    except Exception as exc:
        body = "<div class='card'><h1>Erreur</h1><p class='bad'><code>" + inputs_esc(exc) + "</code></p><p><a class='button' href='/inputs/map-commander'>Retour</a></p></div>"
    return page("Inputs", body)

def inputs_select(name, current, choices):
    out = ['<select name="' + inputs_esc(name) + '">']
    for value, label in choices:
        sel = " selected" if str(current) == str(value) else ""
        out.append('<option value="' + inputs_esc(value) + '"' + sel + ">" + inputs_esc(label) + "</option>")
    out.append("</select>")
    return "".join(out)


def inputs_checked(cfg, key):
    return "checked" if cfg.get(key) else ""


def inputs_devices_html():
    raw_proc = inputs_cmd("cat /proc/bus/input/devices 2>/dev/null || true", 5)
    raw_byid = inputs_cmd("ls -lah /dev/input/by-id 2>/dev/null || true", 5)
    raw_dev = inputs_cmd("ls -lah /dev/input/event* /dev/input/js* 2>/dev/null || true", 5)
    raw_usb = inputs_cmd("lsusb 2>/dev/null || true", 5)

    rows = []
    block = []
    for line in raw_proc.splitlines() + [""]:
        if line.strip():
            block.append(line)
            continue
        if not block:
            continue
        name = ""
        handlers = ""
        phys = ""
        for b in block:
            if b.startswith("N: Name="):
                name = b.split("=", 1)[1].strip().strip('"')
            elif b.startswith("H: Handlers="):
                handlers = b.split("=", 1)[1].strip()
            elif b.startswith("P: Phys="):
                phys = b.split("=", 1)[1].strip()
        if name or handlers:
            rows.append("<tr><td>" + inputs_esc(name) + "</td><td><code>" + inputs_esc(handlers) + "</code></td><td><code>" + inputs_esc(phys) + "</code></td></tr>")
        block = []

    table = "<p class='warn'>Aucun périphérique input détecté.</p>"
    if rows:
        table = "<table><tr><th>Périphérique</th><th>Handlers</th><th>Phys</th></tr>" + "".join(rows) + "</table>"

    return """
<div class="card">
  <h2>Périphériques HID / evdev détectés</h2>
  """ + table + """
  <details><summary>Voir /dev/input/by-id</summary><pre>""" + inputs_esc(raw_byid) + """</pre></details>
  <details><summary>Voir /dev/input/event* et js*</summary><pre>""" + inputs_esc(raw_dev) + """</pre></details>
  <details><summary>Voir lsusb</summary><pre>""" + inputs_esc(raw_usb) + """</pre></details>
  <details><summary>Voir /proc/bus/input/devices complet</summary><pre>""" + inputs_esc(raw_proc) + """</pre></details>
</div>
"""


@route("/inputs")
def inputs_page():
    # Page Inputs principale : Map Commander.
    return inputs_map_commander_page()

@route("/inputs/map-commander")
def inputs_map_commander_page():
    cfg = inputs_load_cfg()
    lines, found = inputs_read_ini()

    # PINCABOS_VPX_INPUT_V1 : état lu dans [Input], décodé, avec le rôle VPinFE de chaque action
    state = vpxin.current_state()
    policy = dict(vpxin.VPINFE_DEFAULT_POLICY, **(cfg.get("vpinfe_policy") or {}))
    role_by_action = {}
    for fn, fn_label in vpxin.VPINFE_FUNCTIONS:
        if policy.get(fn):
            role_by_action.setdefault(policy[fn], []).append(fn_label)
    key_rows = []
    for a in state["actions"]:
        action = a["action"]
        icon = MAP_COMMANDER_ICON_FILES.get(MAP_COMMANDER_LEGACY_KEY_BY_ACTION.get(action, ""), "")
        icon_html = ('<img class="map-function-icon" src="/static/pincabos-assets/icons/' + inputs_esc(icon) + '" alt="" loading="lazy">') if icon else ""
        status = "Défini" if a["present"] else "Défaut VPX"
        status_class = "good" if a["present"] else "warn"
        roles = " · ".join(role_by_action.get(action, [])) or "—"
        key_rows.append("""
<tr>
  <td class="map-func"><div class="map-function-cell">""" + icon_html + """<strong>""" + inputs_esc(a["label"]) + """</strong></div></td>
  <td class="map-key"><code>""" + inputs_esc(action) + """</code></td>
  <td class="map-raw"><input id="raw_""" + inputs_esc(action) + """" class="map-raw-input" value=\"""" + inputs_esc(a["decoded"]) + """\" readonly></td>
  <td class="map-value"><input id="key_""" + inputs_esc(action) + """" name="map_""" + inputs_esc(action) + """" value=\"""" + inputs_esc(a["mapping"]) + """\" class="map-code-input" spellcheck="false"></td>
  <td class="map-section">""" + inputs_esc(roles) + """</td>
  <td class="map-state"><span class=\"""" + status_class + """\">""" + inputs_esc(status) + """</span></td>
  <td class="map-actions"><button class="button secondary map-mini-btn" type="button" onclick="detectInput('key_""" + inputs_esc(action) + """')">Détecter</button><button class="button secondary map-mini-btn" type="button" onclick="clearInput('key_""" + inputs_esc(action) + """')">Vider</button></td>
</tr>
""")

    vpinfe_preview = vpxin.vpinfe_values({a["action"]: a["mapping"] for a in state["actions"]}, policy)
    vpinfe_installed = vpxin.VPINFE_INI.exists()
    vpinfe_rows = []
    for fn, fn_label in vpxin.VPINFE_FUNCTIONS:
        options = ['<option value=""' + (" selected" if not policy.get(fn) else "") + '>— aucune —</option>']
        for act, act_label, _d in vpxin.ACTIONS:
            options.append('<option value="' + inputs_esc(act) + '"' + (" selected" if policy.get(fn) == act else "") + '>' + inputs_esc(act_label) + '</option>')
        pv = vpinfe_preview.get(fn, {})
        note = " ; ".join(pv.get("notes", []))
        vpinfe_rows.append("<tr><td>" + inputs_esc(fn_label) + "</td><td><code>joy" + inputs_esc(fn) + "</code></td><td><select name=\"vpinfe_" + inputs_esc(fn) + "\" class=\"map-code-input\">"
                           + "".join(options) + "</select></td><td><code>" + inputs_esc(pv.get("joy") or "—") + "</code></td><td><code>" + inputs_esc(pv.get("keys") or "—")
                           + "</code></td><td class=\"warn\">" + inputs_esc(note) + "</td></tr>")

    player_rows = []
    for key, label, default in PINCABOS_INPUT_PLAYERMAP:
        current = found.get(key, {}).get("value", default)
        section = found.get(key, {}).get("section", "Player")
        status = "Détecté" if key in found else "Défaut"
        status_class = "good" if key in found else "warn"
        player_rows.append("""
<tr>
  <td class="map-func"><strong>""" + inputs_esc(label) + """</strong></td>
  <td class="map-key"><code>""" + inputs_esc(key) + """</code></td>
  <td class="map-value"><input name="player_""" + inputs_esc(key) + """" value=\"""" + inputs_esc(current) + """" class="map-code-input"></td>
  <td class="map-section"><code>""" + inputs_esc(section) + """</code></td>
  <td class="map-state"><span class=\"""" + status_class + """\">""" + inputs_esc(status) + """</span></td>
</tr>
""")


    # PINCABOS_VPX_ANALOG_EDITABLE_V1
    vpx_analog_keys = [
        ("PBWEnabled", "Nudge analogique activé", "toggle"),
        ("NudgeStrength", "Force visuelle du nudge", "number"),
        ("LRAxis", "Axe nudge gauche / droite", "axis"),
        ("UDAxis", "Axe nudge avant / arrière", "axis"),
        ("LRAxisFlip", "Inverser nudge gauche / droite", "toggle"),
        ("UDAxisFlip", "Inverser nudge avant / arrière", "toggle"),
        ("PBWAccelGainX", "Gain accélération X", "number"),
        ("PBWAccelGainY", "Gain accélération Y", "number"),
        ("PlungerAxis", "Axe plunger", "axis"),
        ("ReversePlungerAxis", "Inverser plunger", "toggle"),
    ]

    vpx_analog_rows = []

    for key, label, field_type in vpx_analog_keys:
        item = found.get(key, {})
        value = str(item.get("value", "")).strip()
        present = key in found
        state = "Actif" if present else "Absent"
        state_class = "good" if present else "warn"

        field_name = "vpx_player_" + key

        if field_type == "toggle":
            selected_zero = " selected" if value in ("", "0", "false", "False") else ""
            selected_one = " selected" if value not in ("", "0", "false", "False") else ""

            control = (
                '<select name="' + inputs_esc(field_name) + '" class="vpx-analog-input">'
                '<option value="0"' + selected_zero + '>Désactivé (0)</option>'
                '<option value="1"' + selected_one + '>Activé (1)</option>'
                '</select>'
            )

        elif field_type == "axis":
            control = (
                '<input class="vpx-analog-input" '
                'name="' + inputs_esc(field_name) + '" '
                'type="number" min="1" max="8" step="1" '
                'value="' + inputs_esc(value) + '" '
                'placeholder="Axe VPX 1 à 8">'
            )

        else:
            control = (
                '<input class="vpx-analog-input" '
                'name="' + inputs_esc(field_name) + '" '
                'type="number" min="0" max="10" step="0.01" '
                'value="' + inputs_esc(value) + '">'
            )

        vpx_analog_rows.append(
            "<tr>"
            "<td>" + inputs_esc(label) + "</td>"
            "<td><code>" + inputs_esc(key) + "</code></td>"
            "<td>" + control + "</td>"
            "<td><span class='" + state_class + "'>" + inputs_esc(state) + "</span></td>"
            "</tr>"
        )

    body = """
<style>
.map-grid {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) minmax(260px, 1fr);
  gap: 14px;
}
.map-key-columns {
  display: grid;
  grid-template-columns: minmax(480px, 1fr) minmax(480px, 1fr);
  gap: 14px;
  align-items: start;
}
.map-key-column {
  border: 1px solid rgba(255,176,0,.22);
  border-radius: 14px;
  padding: 10px;
  background: rgba(0,0,0,.14);
}
.map-key-column h3 {
  margin-top: 0;
  color: var(--pco-appearance-accent, #ffb000);
}
.map-box {
  border: 1px solid rgba(255,176,0,.25);
  border-radius: 14px;
  padding: 14px;
  background: rgba(0,0,0,.18);
}
.map-table-wrap { overflow-x: auto; }
.map-table {
  width: 100%;
  border-collapse: collapse;
}



/* PINCABOS_MAP_COMMANDER_ICON_ROWS_V2 */
.map-table {
  border-collapse: separate !important;
  border-spacing: 0 3px !important;
  background: transparent !important;
}

.map-table .map-table-header th,
.map-table thead th {
  color: #ffd64a !important;
  background: linear-gradient(180deg, #25200e 0%, #151309 100%) !important;
  border-top: 1px solid rgba(255, 202, 45, .58) !important;
  border-bottom: 1px solid rgba(255, 202, 45, .42) !important;
  font-size: 1.22rem !important;
  font-weight: 900 !important;
  letter-spacing: .045em !important;
  text-transform: uppercase !important;
  padding: 12px 10px !important;
}

.map-table tbody tr td {
  border-top: 1px solid rgba(255,255,255,.055) !important;
  border-bottom: 1px solid rgba(0,0,0,.72) !important;
  color: #e9edf2 !important;
  padding-top: 7px !important;
  padding-bottom: 7px !important;
}

.map-table tbody tr:nth-child(odd) td {
  background: #10141a !important;
}

.map-table tbody tr:nth-child(even) td {
  background: #171d24 !important;
}

.map-table tbody tr:hover td {
  background: #262312 !important;
  border-top-color: rgba(255, 207, 62, .45) !important;
  border-bottom-color: rgba(255, 207, 62, .32) !important;
}

.map-function-cell {
  display: flex !important;
  align-items: center !important;
  gap: 12px !important;
  min-width: 260px !important;
}

.map-function-icon {
  display: block !important;
  width: 46px !important;
  height: 46px !important;
  min-width: 46px !important;
  object-fit: contain !important;
  border-radius: 8px !important;
  background: #080a0d !important;
  box-shadow: 0 2px 7px rgba(0,0,0,.62) !important;
}

.map-func strong {
  color: #f5f7fa !important;
  font-size: 1.03rem !important;
  font-weight: 800 !important;
}


.map-table th, .map-table td {
  vertical-align: middle;
  padding: 10px;
}
.map-table th { text-align:left; color:#ffb000; }
/* PCO_MAPCOMMANDER_EXCEL_GRID_V1 */
.map-table:has(.map-actions) {
  border-collapse: separate;
  border-spacing: 0;
  border: 1px solid rgba(255, 190, 0, .48);
  border-radius: 12px;
  overflow: hidden;
  background: rgba(0, 0, 0, .20);
}

.map-table:has(.map-actions) th,
.map-table:has(.map-actions) td {
  vertical-align: middle;
  border-bottom: 1px solid rgba(255, 190, 0, .16);
}

.map-table:has(.map-actions) tr:first-child th {
  color: #ffe36b;
  font-weight: 900;
  letter-spacing: .015em;
  background: linear-gradient(
    90deg,
    rgba(255, 176, 0, .34),
    rgba(117, 62, 0, .34)
  );
  border-bottom: 2px solid rgba(255, 220, 85, .90);
  padding-top: 13px;
  padding-bottom: 13px;
  white-space: nowrap;
  text-shadow: 0 0 12px rgba(255, 210, 0, .34);
}

.map-table:has(.map-actions) tr:not(:first-child):nth-child(even) {
  background: rgba(255, 176, 0, .075);
}

.map-table:has(.map-actions) tr:not(:first-child):nth-child(odd) {
  background: rgba(95, 42, 145, .18);
}

.map-table:has(.map-actions) tr:not(:first-child):hover {
  background: rgba(255, 190, 0, .17);
  box-shadow: inset 4px 0 0 rgba(255, 220, 85, .92);
}

.map-table:has(.map-actions) tr:last-child td {
  border-bottom: 0;
}

.map-func { min-width: 210px; }
.map-key { min-width: 190px; }
.map-value { width: 120px; text-align:center; }
.map-section { width: 100px; text-align:center; }
.map-state { width: 100px; text-align:center; }
.map-actions { width: 190px; white-space:nowrap; text-align:right; }
.map-code-input {
  width: 90px;
  text-align: center;
  font-family: monospace;
}
.map-mini-btn {
  min-width: 76px !important;
  font-size: 12px !important;
  padding: 4px 7px !important;
  margin-left: 5px !important;
}
#map-detect-status {
  margin-top: 10px;
  padding: 8px 10px;
  border-radius: var(--pco-appearance-button-radius, 10px);
  background: rgba(255,176,0,.08);
  border: 1px solid rgba(255,176,0,.25);
}
@media (max-width: 850px) {


  /* PINCABOS_LIVE_PLUNGER_GUIDES_V2 */
  .plunger-track-safe {
    position: relative !important;
    overflow: visible !important;
    touch-action: none;
    cursor: crosshair;
  }

  .plunger-guide-safe {
    position: absolute !important;
    top: -13px !important;
    bottom: -13px !important;
    width: 7px !important;
    margin-left: -3px !important;
    border-radius: 999px;
    z-index: 12 !important;
    cursor: ew-resize !important;
    pointer-events: auto !important;
    transition: left .05s linear;
  }

  .plunger-guide-safe.deadzone {
    background: linear-gradient(180deg, #49d9ff 0%, #1477d4 100%);
    box-shadow: 0 0 13px rgba(73, 217, 255, .88);
  }

  .plunger-guide-safe.maxfield {
    background: linear-gradient(180deg, #fff197 0%, #ffb800 100%);
    box-shadow: 0 0 13px rgba(255, 184, 0, .82);
  }

  .plunger-guide-safe:active {
    transform: scaleX(1.45);
  }

  .plunger-guide-label-safe {
    position: absolute;
    left: 50%;
    top: -28px;
    transform: translateX(-50%);
    padding: 2px 5px;
    border: 1px solid rgba(255,255,255,.26);
    border-radius: 5px;
    color: #f8fafc;
    background: rgba(8,10,14,.92);
    font-size: .68rem;
    font-weight: 900;
    line-height: 1.1;
    white-space: nowrap;
    user-select: none;
  }

  .plunger-pointer-safe {
    z-index: 20 !important;
  }

  .plunger-apply-row {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
  }

  .plunger-apply-note {
    color: #9aa7b4;
    font-size: .9rem;
  }

  /* PINCABOS_LIVE_PLUNGER_CSS_V1 */
  .plunger-track-safe {
    position: relative !important;
    overflow: hidden;
  }

  .plunger-pointer-safe {
    position: absolute !important;
    left: 0%;
    transition: left .07s linear;
    will-change: left;
  }

  .plunger-live-readout,
  .plunger-live-values {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 10px;
    color: #c9d1d9;
    font-size: .9rem;
  }

  .plunger-live-values {
    justify-content: space-between;
    color: #9aa7b4;
  }

  .plunger-live-values strong {
    color: #ffd64a;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  }

  .plunger-live-led {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    display: inline-block;
    background: #59636f;
    box-shadow: 0 0 0 2px rgba(255,255,255,.05);
  }

  .plunger-live-led.online {
    background: #7fd85b;
    box-shadow: 0 0 8px rgba(127,216,91,.65);
  }

  .plunger-live-led.offline {
    background: #d95b5b;
    box-shadow: 0 0 8px rgba(217,91,91,.45);
  }



  /* PINCABOS_MAP_COMMANDER_RIGHT_ANALOG_V1 */
  .map-commander-layout {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(410px, 31%);
    align-items: start;
    gap: 16px;
  }

  .map-buttons-column,
  .map-analog-column {
    min-width: 0;
  }

  .map-analog-column {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .map-analog-card {
    margin: 0 !important;
    padding: 12px !important;
  }

  .map-analog-card > h2,
  .map-analog-card > p {
    display: none !important;
  }

  .map-analog-card .np-grid-safe {
    display: flex !important;
    flex-direction: column !important;
    gap: 14px !important;
  }

  .map-analog-card .np-panel-safe {
    width: auto !important;
    min-width: 0 !important;
    order: 2;
  }

  .map-analog-card .np-panel-safe:nth-child(2) {
    order: 1;
  }

  .map-analog-card .np-panel-safe h3 {
    margin-top: 0;
  }

  /* Plunger: rouge = live, vert = deadzone, jaune = max field */
  .plunger-track-safe {
    position: relative !important;
    min-height: 34px !important;
    overflow: visible !important;
    touch-action: none;
  }

  .plunger-guide-safe {
    position: absolute !important;
    top: -12px !important;
    bottom: -12px !important;
    display: block !important;
    visibility: visible !important;
    width: 7px !important;
    margin-left: -3px !important;
    border-radius: 999px !important;
    cursor: ew-resize !important;
    pointer-events: auto !important;
    z-index: 30 !important;
  }

  .plunger-guide-safe.deadzone {
    background: #42dc78 !important;
    box-shadow: 0 0 12px rgba(66, 220, 120, .95) !important;
  }

  .plunger-guide-safe.maxfield {
    background: #ffd84d !important;
    box-shadow: 0 0 12px rgba(255, 216, 77, .95) !important;
  }

  .plunger-guide-label-safe {
    position: absolute;
    top: -25px;
    left: 50%;
    transform: translateX(-50%);
    padding: 2px 5px;
    border-radius: 5px;
    background: rgba(8, 10, 14, .96);
    border: 1px solid rgba(255,255,255,.22);
    color: #f7f9fb;
    font-size: .66rem;
    font-weight: 800;
    line-height: 1.1;
    white-space: nowrap;
    user-select: none;
    pointer-events: none;
  }

  .plunger-pointer-safe {
    z-index: 40 !important;
  }

  @media (max-width: 1250px) {
    .map-commander-layout {
      grid-template-columns: 1fr;
    }
  }


  .map-grid { grid-template-columns: 1fr; }
  .map-key-columns { grid-template-columns: 1fr; }
}

.map-raw { width: 170px; text-align:center; }
.map-raw-input { width:155px; text-align:center; font-family:monospace; opacity:.9; }
.map-detect-modal { position:fixed; inset:0; background:rgba(0,0,0,.72); z-index:99999; display:none; align-items:center; justify-content:center; }
.map-detect-box { width:min(520px,92vw); border:1px solid rgba(255,176,0,.55); border-radius:18px; padding:22px; background:rgba(20,0,30,.96); box-shadow:0 0 35px rgba(255,122,0,.28); text-align:center; }
.map-detect-count { font-size:54px; font-weight:900; color:#ffb000; margin:12px 0; }
.map-detect-raw { margin-top:12px; padding:10px; border-radius:10px; background:rgba(0,0,0,.35); font-family:monospace; }


  /* PINCABOS_MAP_COMMANDER_RIGHT_VISUAL_V2 */
  .map-command-layout-v2 {
    display: grid !important;
    grid-template-columns: minmax(0, 1fr) 465px !important;
    gap: 16px !important;
    align-items: start !important;
  }

  .map-command-left-v2,
  .map-command-right-v2 {
    min-width: 0 !important;
  }

  .map-command-right-v2 {
    position: sticky !important;
    top: 12px !important;
  }

  .map-command-right-v2 > .card {
    margin: 0 !important;
    padding: 12px !important;
  }

  .map-command-right-v2 > .card > h2,
  .map-command-right-v2 > .card > p {
    display: none !important;
  }

  .map-command-right-v2 .np-grid-safe {
    display: flex !important;
    flex-direction: column !important;
    gap: 14px !important;
  }

  .map-command-right-v2 .np-panel-safe {
    width: 100% !important;
    min-width: 0 !important;
    padding: 14px !important;
    border: 1px solid rgba(255,176,0,.28) !important;
    border-radius: 14px !important;
    background: rgba(4,7,11,.54) !important;
  }

  .map-command-right-v2 .np-panel-safe h3 {
    margin: 0 0 12px 0 !important;
    color: #ffd64a !important;
    font-size: 1.10rem !important;
  }

  .map-command-right-v2 .np-fields-safe {
    grid-template-columns: 1fr 1fr !important;
    gap: 9px 12px !important;
  }

  .map-command-right-v2 .plunger-track-safe {
    position: relative !important;
    min-height: 42px !important;
    overflow: visible !important;
    touch-action: none !important;
  }

  /* Rouge : position live */
  .map-command-right-v2 .plunger-pointer-safe {
    position: absolute !important;
    top: -11px !important;
    bottom: -11px !important;
    width: 9px !important;
    margin-left: -4px !important;
    border-radius: 999px !important;
    background: #ff3f3f !important;
    box-shadow: 0 0 15px rgba(255,63,63,.96) !important;
    z-index: 60 !important;
  }

  /* Vert : deadzone | Jaune : max field */
  .map-command-right-v2 .plunger-guide-safe {
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
    position: absolute !important;
    top: -12px !important;
    bottom: -12px !important;
    width: 8px !important;
    margin-left: -4px !important;
    border-radius: 999px !important;
    cursor: ew-resize !important;
    pointer-events: auto !important;
    z-index: 50 !important;
  }

  .map-command-right-v2 .plunger-guide-safe.deadzone {
    background: #42dc78 !important;
    box-shadow: 0 0 14px rgba(66,220,120,.98) !important;
  }

  .map-command-right-v2 .plunger-guide-safe.maxfield {
    background: #ffd84d !important;
    box-shadow: 0 0 14px rgba(255,216,77,.98) !important;
  }

  .map-command-right-v2 .plunger-guide-label-safe {
    position: absolute !important;
    left: 50% !important;
    top: -29px !important;
    transform: translateX(-50%) !important;
    padding: 3px 6px !important;
    border: 1px solid rgba(255,255,255,.30) !important;
    border-radius: 5px !important;
    background: #090b0f !important;
    color: #f5f7fa !important;
    font-size: .67rem !important;
    font-weight: 900 !important;
    line-height: 1.1 !important;
    white-space: nowrap !important;
    pointer-events: none !important;
  }

  @media (max-width: 1380px) {
    .map-command-layout-v2 {
      grid-template-columns: 1fr !important;
    }

    .map-command-right-v2 {
      position: static !important;
    }
  }

  @media (max-width: 650px) {
    .map-command-right-v2 .np-fields-safe {
      grid-template-columns: 1fr !important;
    }
  }


  /* PINCABOS_MAP_COMMANDER_EQUAL_HEIGHT_V1 */
  .map-eq-layout {
    display: grid !important;
    grid-template-columns: minmax(0, 1fr) 540px !important;
    gap: 16px !important;
    align-items: stretch !important;
  }

  .map-eq-left,
  .map-eq-right {
    min-width: 0 !important;
  }

  .map-eq-left > .card,
  .map-eq-right > .card {
    margin: 0 !important;
  }

  .map-eq-right {
    display: flex !important;
    align-items: stretch !important;
  }

  .map-eq-right > .card {
    width: 100% !important;
    display: flex !important;
    flex-direction: column !important;
    min-height: 100% !important;
    overflow: hidden !important;
    padding: 12px !important;
  }

  .map-eq-right > .card > h2,
  .map-eq-right > .card > p {
    display: none !important;
  }

  .map-eq-right .np-grid-safe {
    display: flex !important;
    flex-direction: column !important;
    gap: 14px !important;
    flex: 1 1 auto !important;
    min-height: 0 !important;
  }

  .map-eq-right .np-panel-safe {
    width: 100% !important;
    min-width: 0 !important;
    display: flex !important;
    flex-direction: column !important;
    overflow: hidden !important;
    padding: 14px !important;
    border: 1px solid rgba(255,176,0,.26) !important;
    border-radius: 14px !important;
    background: rgba(4,7,11,.50) !important;
  }

  .map-eq-right .np-panel-safe[data-analog-panel="plunger"] {
    flex: 0 0 42% !important;
  }

  .map-eq-right .np-panel-safe[data-analog-panel="nudge"] {
    flex: 1 1 58% !important;
  }

  .map-eq-right .np-panel-safe h3 {
    margin: 0 0 12px 0 !important;
    color: #ffd64a !important;
    font-size: 1.08rem !important;
  }

  .map-eq-right .np-fields-safe {
    display: grid !important;
    grid-template-columns: minmax(0,1fr) minmax(0,1fr) !important;
    gap: 9px 12px !important;
  }

  .map-eq-right label,
  .map-eq-right input,
  .map-eq-right select {
    min-width: 0 !important;
    box-sizing: border-box !important;
  }

  .map-eq-right .plunger-track-safe {
    position: relative !important;
    min-height: 42px !important;
    overflow: visible !important;
    touch-action: none !important;
  }

  .map-eq-right .plunger-pointer-safe {
    z-index: 60 !important;
  }

  .map-eq-right .plunger-guide-safe {
    z-index: 50 !important;
  }

  .map-eq-right .nudge-scope-safe {
    margin-left: auto !important;
    margin-right: auto !important;
    max-width: 100% !important;
  }

  @media (max-width: 1600px) {
    .map-eq-layout {
      grid-template-columns: minmax(0, 1fr) 500px !important;
    }
  }

  @media (max-width: 1380px) {
    .map-eq-layout {
      grid-template-columns: 1fr !important;
    }

    .map-eq-right {
      display: block !important;
    }

    .map-eq-right > .card {
      min-height: auto !important;
      height: auto !important;
    }

    .map-eq-right .np-panel-safe[data-analog-panel="plunger"],
    .map-eq-right .np-panel-safe[data-analog-panel="nudge"] {
      flex: none !important;
    }
  }

  @media (max-width: 700px) {
    .map-eq-right .np-fields-safe {
      grid-template-columns: 1fr !important;
    }
  }


  /* PINCABOS_MAP_COMMANDER_SINGLE_CARD_V1 */
  .pco-map-single-card-layout {
    display: grid !important;
    grid-template-columns: minmax(0, 1fr) 500px !important;
    gap: 16px !important;
    align-items: start !important;
    margin-top: 10px !important;
  }

  .pco-map-single-card-left,
  .pco-map-single-card-right {
    min-width: 0 !important;
  }

  .pco-map-single-card-right {
    display: flex !important;
    flex-direction: column !important;
    gap: 14px !important;
  }

  .pco-map-single-card-right .np-panel-safe {
    width: 100% !important;
    min-width: 0 !important;
    padding: 14px !important;
    border: 1px solid rgba(255,176,0,.26) !important;
    border-radius: 14px !important;
    background: rgba(4,7,11,.50) !important;
    overflow: hidden !important;
  }

  .pco-map-single-card-right .np-panel-safe h3 {
    margin: 0 0 12px 0 !important;
    color: #ffd64a !important;
    font-size: 1.08rem !important;
  }

  .pco-map-single-card-right .np-fields-safe {
    display: grid !important;
    grid-template-columns: minmax(0,1fr) minmax(0,1fr) !important;
    gap: 9px 12px !important;
  }

  .pco-map-single-card-right label,
  .pco-map-single-card-right input,
  .pco-map-single-card-right select {
    min-width: 0 !important;
    box-sizing: border-box !important;
  }

  .pco-map-single-card-right .plunger-track-safe {
    position: relative !important;
    min-height: 42px !important;
    overflow: visible !important;
    touch-action: none !important;
  }

  .pco-map-single-card-right .nudge-scope-safe {
    margin-left: auto !important;
    margin-right: auto !important;
    max-width: 100% !important;
  }

  .pco-map-single-card-hidden-source {
    display: none !important;
  }

  @media (max-width: 1500px) {
    .pco-map-single-card-layout {
      grid-template-columns: minmax(0, 1fr) 460px !important;
    }
  }

  @media (max-width: 1320px) {
    .pco-map-single-card-layout {
      grid-template-columns: 1fr !important;
    }
  }

  @media (max-width: 700px) {
    .pco-map-single-card-right .np-fields-safe {
      grid-template-columns: 1fr !important;
    }
  }


  /* PINCABOS_MAP_COMMANDER_LAYOUT_POLISH_V1 */

  /* Carte principale: largeur propre comme les autres */
  .pco-map-master-card {
    width: 100% !important;
    max-width: 100% !important;
    min-width: 0 !important;
    box-sizing: border-box !important;
    overflow: hidden !important;
  }

  /* Layout principal 2/3 + 1/3 */
  .pco-map-single-card-layout,
  .map-eq-layout,
  .map-command-layout-v2,
  .map-command-center-layout {
    display: grid !important;
    grid-template-columns: minmax(0, 2fr) minmax(400px, 1fr) !important;
    gap: 18px !important;
    align-items: stretch !important;
    width: 100% !important;
    max-width: 100% !important;
    box-sizing: border-box !important;
  }

  .pco-map-single-card-left,
  .pco-map-single-card-right,
  .map-eq-left,
  .map-eq-right,
  .map-command-left-v2,
  .map-command-right-v2 {
    min-width: 0 !important;
    box-sizing: border-box !important;
  }

  /* Colonne de droite */
  .pco-map-single-card-right,
  .map-eq-right,
  .map-command-right-v2 {
    display: flex !important;
    flex-direction: column !important;
    gap: 16px !important;
    height: 100% !important;
    align-self: stretch !important;
  }

  /* Supprime les largeurs fixes trop petites imposées avant */
  .pco-map-single-card-layout {
    grid-template-columns: minmax(0, 2fr) minmax(400px, 1fr) !important;
  }

  /* Les 2 panneaux de droite occupent toute la hauteur disponible */
  .pco-map-single-card-right .np-panel-safe,
  .map-eq-right .np-panel-safe,
  .map-command-right-v2 .np-panel-safe {
    flex: 1 1 0 !important;
    min-height: 0 !important;
    width: 100% !important;
    display: flex !important;
    flex-direction: column !important;
    overflow: hidden !important;
    padding: 14px !important;
    border: 1px solid rgba(255,176,0,.26) !important;
    border-radius: 14px !important;
    background: rgba(4,7,11,.50) !important;
    box-sizing: border-box !important;
  }

  /* Plunger en haut, Nudge en dessous */
  .pco-map-single-card-right .np-panel-safe[data-analog-panel="plunger"],
  .map-eq-right .np-panel-safe[data-analog-panel="plunger"],
  .map-command-right-v2 .np-panel-safe[data-analog-panel="plunger"] {
    flex: 1 1 0 !important;
  }

  .pco-map-single-card-right .np-panel-safe[data-analog-panel="nudge"],
  .map-eq-right .np-panel-safe[data-analog-panel="nudge"],
  .map-command-right-v2 .np-panel-safe[data-analog-panel="nudge"] {
    flex: 1 1 0 !important;
  }

  /* Titres panneaux analogiques */
  .pco-map-single-card-right .np-panel-safe h3,
  .map-eq-right .np-panel-safe h3,
  .map-command-right-v2 .np-panel-safe h3 {
    margin: 0 0 12px 0 !important;
    color: #ffd64a !important;
    font-size: 1.08rem !important;
  }

  /* Champs mieux répartis */
  .pco-map-single-card-right .np-fields-safe,
  .map-eq-right .np-fields-safe,
  .map-command-right-v2 .np-fields-safe {
    display: grid !important;
    grid-template-columns: minmax(0,1fr) minmax(0,1fr) !important;
    gap: 9px 12px !important;
    align-items: start !important;
  }

  .pco-map-single-card-right label,
  .pco-map-single-card-right input,
  .pco-map-single-card-right select,
  .map-eq-right label,
  .map-eq-right input,
  .map-eq-right select,
  .map-command-right-v2 label,
  .map-command-right-v2 input,
  .map-command-right-v2 select {
    min-width: 0 !important;
    width: 100% !important;
    box-sizing: border-box !important;
  }

  /* Track plunger propre */
  .pco-map-single-card-right .plunger-track-safe,
  .map-eq-right .plunger-track-safe,
  .map-command-right-v2 .plunger-track-safe {
    position: relative !important;
    min-height: 42px !important;
    overflow: visible !important;
    touch-action: none !important;
  }

  /* Visuel nudge centré */
  .pco-map-single-card-right .nudge-scope-safe,
  .map-eq-right .nudge-scope-safe,
  .map-command-right-v2 .nudge-scope-safe {
    margin-left: auto !important;
    margin-right: auto !important;
    max-width: 100% !important;
  }

  /* Nettoyage général largeur */
  .pco-map-master-card .map-table-wrap,
  .pco-map-master-card .map-table {
    width: 100% !important;
    max-width: 100% !important;
    box-sizing: border-box !important;
  }

  /* Responsive */
  @media (max-width: 1650px) {
    .pco-map-single-card-layout,
    .map-eq-layout,
    .map-command-layout-v2,
    .map-command-center-layout {
      grid-template-columns: minmax(0, 2fr) minmax(360px, 1fr) !important;
    }
  }

  @media (max-width: 1380px) {
    .pco-map-single-card-layout,
    .map-eq-layout,
    .map-command-layout-v2,
    .map-command-center-layout {
      grid-template-columns: 1fr !important;
    }

    .pco-map-single-card-right,
    .map-eq-right,
    .map-command-right-v2 {
      height: auto !important;
    }

    .pco-map-single-card-right .np-panel-safe,
    .map-eq-right .np-panel-safe,
    .map-command-right-v2 .np-panel-safe {
      flex: none !important;
    }
  }

  @media (max-width: 760px) {
    .pco-map-single-card-right .np-fields-safe,
    .map-eq-right .np-fields-safe,
    .map-command-right-v2 .np-fields-safe {
      grid-template-columns: 1fr !important;
    }
  }


  /* PINCABOS_MAP_COMMANDER_MASTER_FULLWIDTH_FIX_V1 */

  /* La carte maître doit occuper toute la largeur utile */
  .pco-map-master-card {
    width: 100% !important;
    max-width: none !important;
    min-width: 0 !important;
    box-sizing: border-box !important;
    display: block !important;
    grid-column: 1 / -1 !important;
  }

  /* Son layout interne doit aussi remplir toute la largeur */
  .pco-map-master-card .pco-map-single-card-layout,
  .pco-map-master-card .map-eq-layout,
  .pco-map-master-card .map-command-layout-v2,
  .pco-map-master-card .map-command-center-layout {
    width: 100% !important;
    max-width: none !important;
    min-width: 0 !important;
    box-sizing: border-box !important;
  }

  /* Évite qu'un ancien wrapper limite encore la largeur */
  .map-eq-layout > .map-eq-left > .pco-map-master-card,
  .map-command-layout-v2 > .map-command-left-v2 > .pco-map-master-card,
  .map-command-center-layout > .map-command-center-left > .pco-map-master-card {
    width: 100% !important;
    max-width: none !important;
    grid-column: 1 / -1 !important;
  }

  /* La table et ses conteneurs doivent suivre la pleine largeur */
  .pco-map-master-card .map-table-wrap,
  .pco-map-master-card .map-table,
  .pco-map-master-card .pco-map-single-card-left,
  .pco-map-master-card .pco-map-single-card-right {
    width: 100% !important;
    max-width: none !important;
    min-width: 0 !important;
    box-sizing: border-box !important;
  }


  /* PINCABOS_MAP_COMMANDER_TRUE_SINGLE_CARD_V1 */
  .map-master-card-v3 {
    width: 100% !important;
    max-width: none !important;
    min-width: 0 !important;
    box-sizing: border-box !important;
  }

  .map-master-grid-v3 {
    display: grid !important;
    grid-template-columns: minmax(0, 2fr) minmax(380px, 1fr) !important;
    gap: 16px !important;
    align-items: stretch !important;
    width: 100% !important;
    min-width: 0 !important;
  }

  .map-master-left-v3,
  .map-master-right-v3 {
    min-width: 0 !important;
  }

  .map-master-left-v3 {
    display: flex !important;
    flex-direction: column !important;
  }

  .map-master-right-v3 {
    display: flex !important;
    flex-direction: column !important;
    gap: 12px !important;
    min-height: 0 !important;
  }

  .map-master-right-v3 > .np-grid-safe {
    display: grid !important;
    grid-template-rows: minmax(0, .85fr) minmax(0, 1.15fr) !important;
    gap: 12px !important;
    flex: 1 1 auto !important;
    min-height: 0 !important;
  }

  .map-master-right-v3 .np-panel-safe {
    width: 100% !important;
    min-width: 0 !important;
    min-height: 0 !important;
    display: flex !important;
    flex-direction: column !important;
    overflow: hidden !important;
    padding: 14px !important;
    border: 1px solid rgba(255,176,0,.27) !important;
    border-radius: 14px !important;
    background: rgba(5,8,13,.52) !important;
    box-sizing: border-box !important;
  }

  /* Nudge est premier dans le HTML, mais Plunger devient premier visuellement */
  .map-master-right-v3 .np-panel-safe:nth-child(1) {
    order: 2 !important;
  }

  .map-master-right-v3 .np-panel-safe:nth-child(2) {
    order: 1 !important;
  }

  .map-master-right-v3 .np-panel-safe h3 {
    margin: 0 0 11px 0 !important;
    color: #ffd64a !important;
    font-size: 1.08rem !important;
  }

  .map-master-right-v3 .np-fields-safe {
    display: grid !important;
    grid-template-columns: minmax(0,1fr) minmax(0,1fr) !important;
    gap: 8px 10px !important;
  }

  .map-master-right-v3 label,
  .map-master-right-v3 input,
  .map-master-right-v3 select {
    min-width: 0 !important;
    width: 100% !important;
    box-sizing: border-box !important;
  }

  .map-master-right-v3 .plunger-track-safe {
    position: relative !important;
    min-height: 42px !important;
    margin: 7px 0 8px !important;
    overflow: visible !important;
  }

  .map-master-right-v3 .nudge-scope-safe {
    margin: 3px auto 12px !important;
    max-width: 100% !important;
  }

  .map-master-right-v3 > details {
    margin-top: 0 !important;
    flex: 0 0 auto !important;
  }

  @media (max-width: 1360px) {
    .map-master-grid-v3 {
      grid-template-columns: 1fr !important;
    }

    .map-master-right-v3 > .np-grid-safe {
      grid-template-rows: auto auto !important;
    }
  }

  @media (max-width: 720px) {
    .map-master-right-v3 .np-fields-safe {
      grid-template-columns: 1fr !important;
    }
  }


  /* PINCABOS_MAP_COMMANDER_STACK_ANALOG_V1 */
  .map-master-right-v3 {
    display: flex !important;
    flex-direction: column !important;
    min-width: 0 !important;
    min-height: 0 !important;
  }

  .map-master-right-v3 > .np-grid-safe {
    display: flex !important;
    flex-direction: column !important;
    grid-template-columns: 1fr !important;
    grid-template-rows: none !important;
    gap: 12px !important;
    width: 100% !important;
    min-width: 0 !important;
    min-height: 0 !important;
  }

  .map-master-right-v3 > .np-grid-safe > .np-panel-safe {
    width: 100% !important;
    min-width: 0 !important;
    flex: 0 0 auto !important;
  }

  .map-master-right-v3 > .np-grid-safe > .np-panel-safe[data-analog-panel="plunger"] {
    order: 1 !important;
  }

  .map-master-right-v3 > .np-grid-safe > .np-panel-safe[data-analog-panel="nudge"] {
    order: 2 !important;
  }

  @media (max-width: 1360px) {
    .map-master-right-v3 > .np-grid-safe {
      display: flex !important;
      flex-direction: column !important;
    }
  }


  /* PINCABOS_MAP_COMMANDER_EQUAL_ANALOG_HEIGHT_V1 */

  /* La grille principale adopte la hauteur du Mapping */
  .map-master-grid-v3 {
    align-items: stretch !important;
  }

  /* Colonne analogique = hauteur complète de la grande carte */
  .map-master-right-v3 {
    height: 100% !important;
    min-height: 0 !important;
    align-self: stretch !important;
    display: flex !important;
    flex-direction: column !important;
  }

  /* Deux panneaux verticaux égaux */
  .map-master-right-v3 > .np-grid-safe {
    flex: 1 1 auto !important;
    height: 100% !important;
    min-height: 0 !important;
    display: grid !important;
    grid-template-columns: 1fr !important;
    grid-template-rows: repeat(2, minmax(0, 1fr)) !important;
    gap: 14px !important;
  }

  .map-master-right-v3 > .np-grid-safe > .np-panel-safe {
    width: 100% !important;
    min-width: 0 !important;
    min-height: 0 !important;
    height: auto !important;
    overflow: hidden !important;
    display: flex !important;
    flex-direction: column !important;
  }

  /* Plunger premier, Nudge deuxième */
  .map-master-right-v3 > .np-grid-safe > .np-panel-safe[data-analog-panel="plunger"] {
    order: 1 !important;
  }

  .map-master-right-v3 > .np-grid-safe > .np-panel-safe[data-analog-panel="nudge"] {
    order: 2 !important;
  }

  /* Nudge : conserve le cercle centré sans étirer les champs */
  .map-master-right-v3 .nudge-scope-safe {
    margin: 10px auto 16px !important;
  }

  /* Plunger : garde les contrôles en haut de son demi-panneau */
  .map-master-right-v3 .plunger-track-safe {
    margin-top: 12px !important;
  }

  @media (max-width: 1360px) {
    .map-master-right-v3 {
      height: auto !important;
    }

    .map-master-right-v3 > .np-grid-safe {
      height: auto !important;
      grid-template-rows: auto auto !important;
    }

    .map-master-right-v3 > .np-grid-safe > .np-panel-safe {
      min-height: 0 !important;
    }
  }


  /* PINCABOS_PLUNGER_NUDGE_VERTICAL_GUIDES_V1 */

  /* Colonne de droite : panneaux empilés */
  .map-master-right-v3 {
    display: flex !important;
    flex-direction: column !important;
    gap: 14px !important;
    min-width: 0 !important;
    min-height: 0 !important;
  }

  .map-master-right-v3 > .np-grid-safe {
    display: flex !important;
    flex-direction: column !important;
    gap: 14px !important;
    width: 100% !important;
    min-width: 0 !important;
  }

  .map-master-right-v3 > .np-grid-safe > .np-panel-safe {
    width: 100% !important;
    min-width: 0 !important;
    overflow: hidden !important;
  }

  /* Plunger en haut, Nudge en dessous */
  .map-master-right-v3 > .np-grid-safe > .np-panel-safe[data-analog-panel="plunger"] {
    order: 1 !important;
  }

  .map-master-right-v3 > .np-grid-safe > .np-panel-safe[data-analog-panel="nudge"] {
    order: 2 !important;
  }

  /* Tous les champs un en dessous de l’autre */
  .map-master-right-v3 .np-fields-safe {
    display: grid !important;
    grid-template-columns: 1fr !important;
    gap: 10px !important;
    width: 100% !important;
    min-width: 0 !important;
  }

  .map-master-right-v3 .np-fields-safe label {
    display: flex !important;
    flex-direction: column !important;
    align-items: stretch !important;
    gap: 6px !important;
    width: 100% !important;
    min-width: 0 !important;
    box-sizing: border-box !important;
  }

  .map-master-right-v3 .np-fields-safe input,
  .map-master-right-v3 .np-fields-safe select {
    width: 100% !important;
    min-width: 0 !important;
    box-sizing: border-box !important;
  }

  /* Lignes checkbox mieux alignées */
  .map-master-right-v3 .checkline {
    display: flex !important;
    flex-direction: row !important;
    align-items: center !important;
    justify-content: flex-start !important;
    gap: 10px !important;
  }

  .map-master-right-v3 .checkline input[type="checkbox"] {
    width: 18px !important;
    min-width: 18px !important;
    height: 18px !important;
  }

  /* Track Plunger */
  .map-master-right-v3 .plunger-track-safe {
    position: relative !important;
    min-height: 44px !important;
    margin: 10px 0 14px !important;
    overflow: visible !important;
    touch-action: none !important;
  }

  /* Ligne rouge live */
  .map-master-right-v3 .plunger-pointer-safe {
    position: absolute !important;
    top: -11px !important;
    bottom: -11px !important;
    width: 9px !important;
    margin-left: -4px !important;
    border-radius: 999px !important;
    background: #ff3f3f !important;
    box-shadow: 0 0 14px rgba(255,63,63,.96) !important;
    z-index: 60 !important;
  }

  /* Ligne verte / jaune */
  .map-master-right-v3 .plunger-guide-safe {
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
    position: absolute !important;
    top: -12px !important;
    bottom: -12px !important;
    width: 8px !important;
    margin-left: -4px !important;
    border-radius: 999px !important;
    z-index: 50 !important;
    pointer-events: auto !important;
    cursor: ew-resize !important;
  }

  .map-master-right-v3 .plunger-guide-safe.deadzone {
    background: #42dc78 !important;
    box-shadow: 0 0 14px rgba(66,220,120,.96) !important;
  }

  .map-master-right-v3 .plunger-guide-safe.maxfield {
    background: #ffd84d !important;
    box-shadow: 0 0 14px rgba(255,216,77,.96) !important;
  }

  .map-master-right-v3 .plunger-guide-label-safe {
    position: absolute !important;
    top: -28px !important;
    left: 50% !important;
    transform: translateX(-50%) !important;
    padding: 3px 6px !important;
    border-radius: 5px !important;
    border: 1px solid rgba(255,255,255,.26) !important;
    background: rgba(8,10,14,.96) !important;
    color: #f5f7fa !important;
    font-size: .68rem !important;
    font-weight: 900 !important;
    line-height: 1.1 !important;
    white-space: nowrap !important;
    pointer-events: none !important;
  }

  /* Nudge */
  .map-master-right-v3 .nudge-scope-safe {
    margin: 8px auto 14px !important;
    max-width: 100% !important;
  }


  /* PINCABOS_VPX_ANALOG_CARD_V2 */
  .map-master-right-v3 > details {
    display: none !important;
  }

  .map-master-right-v3 .vpx-analog-card-v2 {
    width: 100% !important;
    min-width: 0 !important;
    box-sizing: border-box !important;
    padding: 14px !important;
    border: 1px solid rgba(255,176,0,.28) !important;
    border-radius: 14px !important;
    background: rgba(5,8,13,.54) !important;
  }

  .map-master-right-v3 .vpx-analog-card-v2 h3 {
    margin: 0 0 6px 0 !important;
    color: #ffd64a !important;
    font-size: 1.04rem !important;
  }

  .vpx-analog-note-v2 {
    margin: 0 0 12px 0 !important;
    color: #aeb8c3 !important;
    font-size: .85rem !important;
  }

  .vpx-analog-table-wrap-v2 {
    overflow-x: auto !important;
  }

  .vpx-analog-table-v2 {
    width: 100% !important;
    border-collapse: separate !important;
    border-spacing: 0 4px !important;
    font-size: .84rem !important;
  }

  .vpx-analog-table-v2 th {
    color: #ffd64a !important;
    text-align: left !important;
    padding: 7px 8px !important;
    background: rgba(255,176,0,.10) !important;
  }

  .vpx-analog-table-v2 td {
    padding: 7px 8px !important;
    background: rgba(16,20,26,.88) !important;
    border-top: 1px solid rgba(255,255,255,.05) !important;
    border-bottom: 1px solid rgba(0,0,0,.50) !important;
  }

  .vpx-analog-table-v2 code {
    white-space: nowrap !important;
  }


  /* PINCABOS_PLUNGER_REDLINE_FIX_V1 */

  /* On ne change pas la hauteur de la carte, seulement le marqueur live rouge */
  .map-master-right-v3 .plunger-track-safe {
    position: relative !important;
    overflow: visible !important;
  }

  /* Base commune : rouge = même hauteur que vert/jaune */
  .map-master-right-v3 .plunger-pointer-safe,
  .map-master-right-v3 .plunger-guide-safe {
    position: absolute !important;
    top: -12px !important;
    bottom: -12px !important;
    height: auto !important;
    width: 8px !important;
    margin-left: -4px !important;
    border-radius: 999px !important;
  }

  /* Ligne live rouge */
  .map-master-right-v3 .plunger-pointer-safe {
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
    background: #ff3f3f !important;
    box-shadow: 0 0 14px rgba(255,63,63,.96) !important;
    z-index: 60 !important;
    transform: none !important;
  }

  /* Guides vert / jaune conservés à la même hauteur */
  .map-master-right-v3 .plunger-guide-safe {
    z-index: 50 !important;
  }


  /* PINCABOS_VPX_ANALOG_EDITABLE_V1 */
  .vpx-analog-input {
    width: 100% !important;
    min-width: 92px !important;
    min-height: 34px !important;
    padding: 6px 8px !important;
    box-sizing: border-box !important;
    color: #f5f7fa !important;
    background: #080a0e !important;
    border: 1px solid rgba(255,176,0,.78) !important;
    border-radius: 8px !important;
  }

  .vpx-analog-input:focus {
    outline: none !important;
    border-color: #ffd64a !important;
    box-shadow: 0 0 0 2px rgba(255,214,74,.16) !important;
  }

  .vpx-analog-actions {
    display: flex !important;
    align-items: center !important;
    flex-wrap: wrap !important;
    gap: 10px !important;
    margin-top: 14px !important;
    color: #aeb8c3 !important;
    font-size: .84rem !important;
  }

  .vpx-analog-actions code {
    white-space: nowrap !important;
  }


  /* PINCABOS_NUDGE_AXIS_USB_SELECTORS_V1 */
  .nudge-axis-device-select {
    width: 100% !important;
    min-height: 42px !important;
    padding: 8px 10px !important;
    color: #f4f6f8 !important;
    background: #090b0f !important;
    border: 1px solid rgba(255,176,0,.78) !important;
    border-radius: 9px !important;
    font-weight: 650 !important;
    box-sizing: border-box !important;
  }

  .nudge-axis-device-select:focus {
    outline: none !important;
    border-color: #ffd64a !important;
    box-shadow: 0 0 0 2px rgba(255,214,74,.18) !important;
  }


  /* PINCABOS_AXIS_HELP_TEXT_V1 */
  .axis-help-text {
    display: block !important;
    margin-top: 6px !important;
    color: #aeb8c3 !important;
    font-size: .82rem !important;
    font-weight: 600 !important;
    line-height: 1.25 !important;
  }

  .axis-help-text::before {
    content: "ℹ ";
    color: #ffd64a;
  }

</style>
  <script>
  /* PINCABOS_PLUNGER_NUDGE_VERTICAL_GUIDES_V1 */
  (function () {
    function ready(fn) {
      if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", fn, { once: true });
      } else {
        fn();
      }
    }

    function norm(value) {
      return String(value || "").replace(/\\s+/g, " ").trim().toLowerCase();
    }

    function clamp(value, min, max) {
      return Math.max(min, Math.min(max, value));
    }

    ready(function () {
      const grid = document.querySelector(".map-master-right-v3 > .np-grid-safe");
      if (!grid) return;

      const panels = Array.from(grid.querySelectorAll(":scope > .np-panel-safe"));

      const plunger = panels.find(function (panel) {
        const h = panel.querySelector("h3");
        return h && norm(h.textContent).includes("plunger");
      });

      const nudge = panels.find(function (panel) {
        const h = panel.querySelector("h3");
        return h && norm(h.textContent).includes("nudge");
      });

      if (plunger) {
        plunger.dataset.analogPanel = "plunger";
        grid.insertBefore(plunger, grid.firstChild);
      }

      if (nudge) {
        nudge.dataset.analogPanel = "nudge";
        grid.appendChild(nudge);
      }

      const track = document.getElementById("plunger_live_track")
        || document.querySelector(".plunger-track-safe");

      if (!track) return;

      let deadzoneMarker = document.getElementById("plunger_deadzone_marker");
      let maxfieldMarker = document.getElementById("plunger_maxfield_marker");
      const deadzoneInput = document.querySelector('input[name="plunger_deadzone"]');
      const maxfieldInput = document.querySelector('input[name="plunger_maxfield"]');
      const invertInput = document.querySelector('input[name="plunger_invert"]');

      if (!deadzoneInput || !maxfieldInput) return;

      if (!deadzoneMarker) {
        deadzoneMarker = document.createElement("div");
        deadzoneMarker.id = "plunger_deadzone_marker";
        deadzoneMarker.className = "plunger-guide-safe deadzone";
        track.appendChild(deadzoneMarker);
      }

      if (!maxfieldMarker) {
        maxfieldMarker = document.createElement("div");
        maxfieldMarker.id = "plunger_maxfield_marker";
        maxfieldMarker.className = "plunger-guide-safe maxfield";
        track.appendChild(maxfieldMarker);
      }

      function ensureLabel(marker) {
        let label = marker.querySelector(".plunger-guide-label-safe");
        if (!label) {
          label = document.createElement("span");
          label.className = "plunger-guide-label-safe";
          marker.appendChild(label);
        }
        return label;
      }

      const dzLabel = ensureLabel(deadzoneMarker);
      const mxLabel = ensureLabel(maxfieldMarker);

      function inverted() {
        return !!(invertInput && invertInput.checked);
      }

      function toPosition(value) {
        const clean = clamp(value, 0, 1);
        return inverted() ? (1 - clean) : clean;
      }

      function toValue(position) {
        const clean = clamp(position, 0, 1);
        return inverted() ? (1 - clean) : clean;
      }

      function numberValue(input, fallback) {
        const value = parseFloat(input.value);
        return Number.isFinite(value) ? value : fallback;
      }

      function refreshGuides() {
        const dz = clamp(numberValue(deadzoneInput, 0.03), 0, 1);
        const mx = clamp(numberValue(maxfieldInput, 1.00), 0, 1);

        deadzoneMarker.style.left = (toPosition(dz) * 100).toFixed(2) + "%";
        maxfieldMarker.style.left = (toPosition(mx) * 100).toFixed(2) + "%";

        dzLabel.textContent = "DZ " + dz.toFixed(3);
        mxLabel.textContent = "MAX " + mx.toFixed(3);
      }

      let dragging = null;

      function beginDrag(event) {
        if (event.currentTarget === deadzoneMarker) dragging = "deadzone";
        if (event.currentTarget === maxfieldMarker) dragging = "maxfield";
        event.preventDefault();
        event.currentTarget.setPointerCapture(event.pointerId);
        moveDrag(event);
      }

      function moveDrag(event) {
        if (!dragging) return;
        const rect = track.getBoundingClientRect();
        if (!rect.width) return;

        const ratio = clamp((event.clientX - rect.left) / rect.width, 0, 1);
        const value = toValue(ratio).toFixed(3);

        if (dragging === "deadzone") {
          deadzoneInput.value = value;
          deadzoneInput.dispatchEvent(new Event("input", { bubbles: true }));
        } else if (dragging === "maxfield") {
          maxfieldInput.value = value;
          maxfieldInput.dispatchEvent(new Event("input", { bubbles: true }));
        }

        refreshGuides();
      }

      function endDrag() {
        dragging = null;
      }

      deadzoneMarker.addEventListener("pointerdown", beginDrag);
      maxfieldMarker.addEventListener("pointerdown", beginDrag);
      window.addEventListener("pointermove", moveDrag);
      window.addEventListener("pointerup", endDrag);
      window.addEventListener("pointercancel", endDrag);

      ["input", "change"].forEach(function (evt) {
        deadzoneInput.addEventListener(evt, refreshGuides);
        maxfieldInput.addEventListener(evt, refreshGuides);
        if (invertInput) invertInput.addEventListener(evt, refreshGuides);
      });

      refreshGuides();
    });
  })();
  </script>

  <script>
  /* PINCABOS_MAP_COMMANDER_EQUAL_ANALOG_HEIGHT_V1 */
  (function () {
    function norm(value) {
      return String(value || "")
        .replace(/\\s+/g, " ")
        .trim()
        .toLowerCase();
    }

    function apply() {
      const grid = document.querySelector(".map-master-right-v3 > .np-grid-safe");
      if (!grid) return;

      const panels = Array.from(
        grid.querySelectorAll(":scope > .np-panel-safe")
      );

      const plunger = panels.find(function (panel) {
        const title = panel.querySelector("h3");
        return title && norm(title.textContent).includes("plunger");
      });

      const nudge = panels.find(function (panel) {
        const title = panel.querySelector("h3");
        return title && norm(title.textContent).includes("nudge");
      });

      if (!plunger || !nudge) return;

      plunger.dataset.analogPanel = "plunger";
      nudge.dataset.analogPanel = "nudge";

      /* Réordonne physiquement : Plunger, ensuite Nudge */
      if (grid.firstElementChild !== plunger) {
        grid.insertBefore(plunger, grid.firstChild);
      }

      if (plunger.nextElementSibling !== nudge) {
        grid.insertBefore(nudge, plunger.nextElementSibling);
      }
    }

    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", apply, { once: true });
    } else {
      apply();
    }
  })();
  </script>

  <script>
  /* PINCABOS_MAP_COMMANDER_STACK_ANALOG_V1 */
  (function () {
    function ready(fn) {
      if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", fn, { once: true });
      } else {
        fn();
      }
    }

    function norm(value) {
      return String(value || "")
        .replace(/\\s+/g, " ")
        .trim()
        .toLowerCase();
    }

    ready(function () {
      const grid = document.querySelector(".map-master-right-v3 > .np-grid-safe");
      if (!grid) return;

      const panels = Array.from(grid.querySelectorAll(":scope > .np-panel-safe"));
      if (!panels.length) return;

      const plunger = panels.find(function (panel) {
        const h = panel.querySelector("h3");
        return h && norm(h.textContent).includes("plunger");
      });

      const nudge = panels.find(function (panel) {
        const h = panel.querySelector("h3");
        return h && norm(h.textContent).includes("nudge");
      });

      if (plunger) {
        plunger.dataset.analogPanel = "plunger";
      }

      if (nudge) {
        nudge.dataset.analogPanel = "nudge";
      }

      if (plunger) {
        grid.appendChild(plunger);
      }

      if (nudge) {
        grid.appendChild(nudge);
      }
    });
  })();
  </script>

  <script>
  /* PINCABOS_MAP_COMMANDER_MASTER_FULLWIDTH_FIX_V1 */
  (function () {
    function norm(value) {
      return String(value || "").replace(/\\s+/g, " ").trim().toLowerCase();
    }

    function ready(fn) {
      if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", fn, { once: true });
      } else {
        fn();
      }
    }

    ready(function () {
      const cards = Array.from(document.querySelectorAll(".card"));

      const mappingCard = cards.find(function (card) {
        const h = card.querySelector("h1, h2, h3");
        return h && norm(h.textContent).includes("mapping boutons vpx");
      });

      if (!mappingCard) return;

      mappingCard.classList.add("pco-map-master-card");

      /* Si la carte est encore dans un ancien wrapper gauche/droite,
         on la remonte hors du wrapper pour enlever le grand vide à droite. */
      const leftWrapper = mappingCard.parentElement;
      const legacyLayout = leftWrapper ? leftWrapper.parentElement : null;

      if (
        legacyLayout &&
        (
          legacyLayout.classList.contains("map-eq-layout") ||
          legacyLayout.classList.contains("map-command-layout-v2") ||
          legacyLayout.classList.contains("map-command-center-layout")
        )
      ) {
        const host = legacyLayout.parentElement;
        if (host) {
          host.insertBefore(mappingCard, legacyLayout);
          legacyLayout.remove();
        }
      }

      /* Si la carte est déjà dans la bonne structure,
         on s'assure juste qu'elle reste pleine largeur. */
      mappingCard.style.width = "100%";
      mappingCard.style.maxWidth = "none";
      mappingCard.style.gridColumn = "1 / -1";
    });
  })();
  </script>

  <script>
  /* PINCABOS_MAP_COMMANDER_LAYOUT_POLISH_V1 */
  (function () {
    function ready(fn) {
      if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", fn, { once: true });
      } else {
        fn();
      }
    }

    function norm(value) {
      return String(value || "").replace(/\\s+/g, " ").trim().toLowerCase();
    }

    ready(function () {
      const cards = Array.from(document.querySelectorAll(".card"));

      const mappingCard = cards.find(function (card) {
        const h = card.querySelector("h1, h2, h3");
        return h && norm(h.textContent).includes("mapping boutons vpx");
      });

      const analogCard = cards.find(function (card) {
        const h = card.querySelector("h1, h2, h3");
        return h && norm(h.textContent).includes("nudge analogique / plunger");
      });

      if (mappingCard) {
        mappingCard.classList.add("pco-map-master-card");
      }

      /* Si le layout "une seule carte" existe, on le calibre */
      const singleRight = mappingCard
        ? mappingCard.querySelector(".pco-map-single-card-right")
        : null;

      if (singleRight) {
        const panels = Array.from(singleRight.querySelectorAll(".np-panel-safe"));

        const plunger = panels.find(function (panel) {
          const h = panel.querySelector("h3");
          return h && norm(h.textContent).includes("plunger");
        });

        const nudge = panels.find(function (panel) {
          const h = panel.querySelector("h3");
          return h && norm(h.textContent).includes("nudge");
        });

        if (plunger) {
          plunger.dataset.analogPanel = "plunger";
          if (singleRight.firstElementChild !== plunger) {
            singleRight.insertBefore(plunger, singleRight.firstChild);
          }
        }

        if (nudge) {
          nudge.dataset.analogPanel = "nudge";
          if (plunger && plunger.nextElementSibling !== nudge) {
            singleRight.appendChild(nudge);
          }
        }
      }

      /* Si ancien layout gauche/droite existe encore, on le calibre aussi */
      const legacyRight = document.querySelector(".map-eq-right, .map-command-right-v2");
      if (legacyRight) {
        const panels = Array.from(legacyRight.querySelectorAll(".np-panel-safe"));

        panels.forEach(function (panel) {
          const h = panel.querySelector("h3");
          const title = h ? norm(h.textContent) : "";

          if (title.includes("plunger")) panel.dataset.analogPanel = "plunger";
          if (title.includes("nudge")) panel.dataset.analogPanel = "nudge";
        });
      }
    });
  })();
  </script>

  <script>
  /* PINCABOS_MAP_COMMANDER_SINGLE_CARD_V1 */
  (function () {
    function norm(value) {
      return String(value || "").replace(/\\s+/g, " ").trim().toLowerCase();
    }

    function ready(fn) {
      if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", fn, { once: true });
      } else {
        fn();
      }
    }

    ready(function () {
      const cards = Array.from(document.querySelectorAll(".card"));

      const mappingCard = cards.find(function (card) {
        const title = card.querySelector("h1, h2, h3");
        return title && norm(title.textContent).includes("mapping boutons vpx");
      });

      const analogCard = cards.find(function (card) {
        const title = card.querySelector("h1, h2, h3");
        return title && norm(title.textContent).includes("nudge analogique / plunger");
      });

      if (!mappingCard || !analogCard) return;
      if (mappingCard.querySelector(".pco-map-single-card-layout")) return;

      const mappingHeading = mappingCard.querySelector("h1, h2, h3");
      const mappingIntro = mappingHeading ? mappingHeading.nextElementSibling : null;

      const layout = document.createElement("div");
      const left = document.createElement("div");
      const right = document.createElement("aside");

      layout.className = "pco-map-single-card-layout";
      left.className = "pco-map-single-card-left";
      right.className = "pco-map-single-card-right";

      const insertAfter = mappingIntro || mappingHeading;
      if (insertAfter && insertAfter.parentNode === mappingCard) {
        insertAfter.insertAdjacentElement("afterend", layout);
      } else {
        mappingCard.appendChild(layout);
      }

      layout.appendChild(left);
      layout.appendChild(right);

      const toMove = [];
      let startCollect = false;
      Array.from(mappingCard.children).forEach(function (child) {
        if (child === layout) return;

        if (!startCollect) {
          if (child === mappingHeading || child === mappingIntro) {
            return;
          }
          startCollect = true;
        }

        if (startCollect) toMove.push(child);
      });

      toMove.forEach(function (node) {
        left.appendChild(node);
      });

      const grid = analogCard.querySelector(".np-grid-safe");
      if (!grid) return;

      const panels = Array.from(grid.querySelectorAll(":scope > .np-panel-safe"));

      let plungerPanel = panels.find(function (panel) {
        const h = panel.querySelector("h3");
        return h && norm(h.textContent).includes("plunger");
      });

      let nudgePanel = panels.find(function (panel) {
        const h = panel.querySelector("h3");
        return h && norm(h.textContent).includes("nudge");
      });

      if (plungerPanel) right.appendChild(plungerPanel);
      if (nudgePanel) right.appendChild(nudgePanel);

      analogCard.classList.add("pco-map-single-card-hidden-source");
    });
  })();
  </script>

  <script>
  /* PINCABOS_MAP_COMMANDER_EQUAL_HEIGHT_V1 */
  (function () {
    function norm(value) {
      return String(value || "").replace(/\\s+/g, " ").trim().toLowerCase();
    }

    function onceReady(fn) {
      if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", fn, { once: true });
      } else {
        fn();
      }
    }

    onceReady(function () {
      const cards = Array.from(document.querySelectorAll(".card"));

      const mappingCard = cards.find(function (card) {
        const title = card.querySelector("h1, h2, h3");
        return title && norm(title.textContent).includes("mapping boutons vpx");
      });

      const analogCard = cards.find(function (card) {
        const title = card.querySelector("h1, h2, h3");
        return title && norm(title.textContent).includes("nudge analogique / plunger");
      });

      if (!mappingCard || !analogCard) return;

      let layout = document.querySelector(".map-eq-layout");
      let left = document.querySelector(".map-eq-left");
      let right = document.querySelector(".map-eq-right");

      if (!layout || !left || !right) {
        const parentLeft = mappingCard.parentElement;
        const parentRight = analogCard.parentElement;
        const sameParent = parentLeft && parentRight && parentLeft === parentRight;

        layout = document.createElement("div");
        left = document.createElement("div");
        right = document.createElement("aside");

        layout.className = "map-eq-layout";
        left.className = "map-eq-left";
        right.className = "map-eq-right";

        if (sameParent) {
          parentLeft.insertBefore(layout, mappingCard);
        } else {
          mappingCard.parentElement.insertBefore(layout, mappingCard);
        }

        layout.appendChild(left);
        layout.appendChild(right);
        left.appendChild(mappingCard);
        right.appendChild(analogCard);
      }

      const grid = analogCard.querySelector(".np-grid-safe");
      if (grid) {
        const panels = Array.from(grid.querySelectorAll(":scope > .np-panel-safe"));

        let plungerPanel = panels.find(function (panel) {
          const h = panel.querySelector("h3");
          return h && norm(h.textContent).includes("plunger");
        });

        let nudgePanel = panels.find(function (panel) {
          const h = panel.querySelector("h3");
          return h && norm(h.textContent).includes("nudge");
        });

        if (plungerPanel && nudgePanel) {
          plungerPanel.dataset.analogPanel = "plunger";
          nudgePanel.dataset.analogPanel = "nudge";

          if (grid.firstElementChild !== plungerPanel) {
            grid.insertBefore(plungerPanel, grid.firstChild);
          }
        }
      }

      function syncHeights() {
        if (window.innerWidth <= 1380) {
          right.style.height = "auto";
          analogCard.style.height = "auto";
          return;
        }

        const leftHeight = mappingCard.getBoundingClientRect().height;
        if (leftHeight > 100) {
          right.style.height = leftHeight + "px";
          analogCard.style.height = "100%";
        }
      }

      syncHeights();
      window.addEventListener("resize", syncHeights);

      const obs = new ResizeObserver(function () {
        syncHeights();
      });

      obs.observe(mappingCard);
      obs.observe(analogCard);
    });
  })();
  </script>

  <script>
  /* PINCABOS_MAP_COMMANDER_RIGHT_VISUAL_V2 */
  (function () {
    function normal(value) {
      return String(value || "").replace(/\\s+/g, " ").trim().toLowerCase();
    }

    function clamp(value, min, max) {
      return Math.max(min, Math.min(max, value));
    }

    function start() {
      const cards = Array.from(document.querySelectorAll(".card"));

      const mappingCard = cards.find(function(card) {
        const title = card.querySelector("h1, h2, h3");
        return title && normal(title.textContent).includes("mapping boutons vpx");
      });

      const analogCard = cards.find(function(card) {
        const title = card.querySelector("h1, h2, h3");
        return title && normal(title.textContent).includes("nudge analogique / plunger");
      });

      if (mappingCard && analogCard &&
          !mappingCard.parentElement.classList.contains("map-command-left-v2")) {
        const layout = document.createElement("div");
        const left = document.createElement("div");
        const right = document.createElement("aside");

        layout.className = "map-command-layout-v2";
        left.className = "map-command-left-v2";
        right.className = "map-command-right-v2";

        mappingCard.parentNode.insertBefore(layout, mappingCard);
        layout.appendChild(left);
        layout.appendChild(right);
        left.appendChild(mappingCard);
        right.appendChild(analogCard);
      }

      const analog = document.querySelector(".map-command-right-v2 .card");
      const grid = analog ? analog.querySelector(".np-grid-safe") : null;

      if (grid) {
        const panels = Array.from(grid.querySelectorAll(":scope > .np-panel-safe"));
        const plunger = panels.find(function(panel) {
          const h = panel.querySelector("h3");
          return h && normal(h.textContent).includes("plunger");
        });

        if (plunger) {
          grid.insertBefore(plunger, grid.firstChild);
        }
      }

      const track = document.getElementById("plunger_live_track");
      const pointer = document.querySelector(".plunger-pointer-safe");
      const deadzoneMarker = document.getElementById("plunger_deadzone_marker");
      const maxfieldMarker = document.getElementById("plunger_maxfield_marker");
      const deadzoneInput = document.querySelector('input[name="plunger_deadzone"]');
      const maxfieldInput = document.querySelector('input[name="plunger_maxfield"]');
      const invertInput = document.querySelector('input[name="plunger_invert"]');

      if (!track || !deadzoneMarker || !maxfieldMarker ||
          !deadzoneInput || !maxfieldInput) {
        return;
      }

      [deadzoneMarker, maxfieldMarker].forEach(function(marker) {
        if (!marker.querySelector(".plunger-guide-label-safe")) {
          const label = document.createElement("span");
          label.className = "plunger-guide-label-safe";
          marker.appendChild(label);
        }
      });

      let dragging = null;

      function number(input, fallback) {
        const value = parseFloat(input.value);
        return Number.isFinite(value) ? value : fallback;
      }

      function inverse() {
        return !!(invertInput && invertInput.checked);
      }

      function toPosition(value) {
        const clean = clamp(value, 0, 1);
        return inverse() ? 1 - clean : clean;
      }

      function toValue(position) {
        const clean = clamp(position, 0, 1);
        return inverse() ? 1 - clean : clean;
      }

      function label(marker, value, prefix) {
        const node = marker.querySelector(".plunger-guide-label-safe");
        if (node) node.textContent = prefix + " " + value.toFixed(3);
      }

      function refresh() {
        const dz = clamp(number(deadzoneInput, 0.03), 0, 1);
        const mx = clamp(number(maxfieldInput, 1.00), 0, 1);

        deadzoneMarker.style.left = (toPosition(dz) * 100).toFixed(2) + "%";
        maxfieldMarker.style.left = (toPosition(mx) * 100).toFixed(2) + "%";

        label(deadzoneMarker, dz, "DZ");
        label(maxfieldMarker, mx, "MAX");

        if (pointer) pointer.style.zIndex = "60";
      }

      function move(event) {
        if (!dragging) return;

        const rect = track.getBoundingClientRect();
        if (!rect.width) return;

        const position = clamp((event.clientX - rect.left) / rect.width, 0, 1);
        const value = toValue(position);
        const field = dragging === deadzoneMarker
          ? deadzoneInput
          : maxfieldInput;

        field.value = value.toFixed(3);
        field.dispatchEvent(new Event("input", { bubbles: true }));
        refresh();
      }

      function begin(event) {
        event.preventDefault();
        dragging = event.currentTarget;
        dragging.setPointerCapture(event.pointerId);
        move(event);
      }

      function end() {
        dragging = null;
      }

      deadzoneMarker.addEventListener("pointerdown", begin);
      maxfieldMarker.addEventListener("pointerdown", begin);
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", end);
      window.addEventListener("pointercancel", end);

      ["input", "change"].forEach(function(name) {
        deadzoneInput.addEventListener(name, refresh);
        maxfieldInput.addEventListener(name, refresh);
        if (invertInput) invertInput.addEventListener(name, refresh);
      });

      refresh();
    }

    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", start, {once:true});
    } else {
      start();
    }
  })();
  </script>


<div class="card">
  <h1>Map Commander</h1>
  <p>
    Mapping des boutons, du nudge analogique et du plunger vers VPX Standalone.
  </p>
  <p>
    Fichier VPX : <code>""" + inputs_esc(PINCABOS_INPUTS_INI) + """</code><br>
    Config PinCabOS : <code>""" + inputs_esc(PINCABOS_INPUTS_CFG) + """</code>
  </p>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:14px 0;">
    <div style="border:1px solid rgba(255,176,0,.45);border-radius:14px;padding:12px;background:rgba(255,176,0,.08);box-shadow:0 0 18px rgba(255,122,0,.12);">
      <strong>⚠️ Configuration recommandée sur le cab</strong><br>
      PinCabOS suggère de faire la configuration Map Commander directement sur le cab,
      en utilisant les boutons <strong>Afficher sur le cab</strong> pour valider les entrées réelles.
    </div>

    <div style="border:1px solid rgba(255,176,0,.45);border-radius:14px;padding:12px;background:rgba(255,176,0,.08);box-shadow:0 0 18px rgba(255,122,0,.12);">
      <strong>⚡ Conseil performance / latence</strong><br>
      PinCabOS suggère, si possible, d’utiliser un mapping <strong>clavier</strong>
      plutôt qu’un mapping joystick, surtout pour réduire la latence des boutons critiques.
    </div>
  </div>

  <p><a class="button secondary" href="/inputs">← Retour Inputs</a></p>
</div>

<form method="post" action="/inputs/save">

<!-- PINCABOS_MAP_COMMANDER_TRUE_SINGLE_CARD_V1 -->
  <div class="card map-master-card-v3">
    <div class="map-master-grid-v3">

      <section class="map-master-left-v3">

  <h2>Mapping boutons VPX</h2>
  <p>
    <strong>Détecter</strong> puis appuie sur le bouton du cab (ou une touche) : la valeur est écrite au format que VPX lit
    (<code>[Input]</code>, <code>Mapping.&lt;Action&gt;</code>). Un bouton joystick remplace le bouton joystick précédent
    de la fonction et <em>conserve</em> la touche clavier ; une touche remplace la touche. Plusieurs entrées se cumulent avec <code>|</code>.
    Les mêmes boutons pilotent la navigation VPinFE (carte ci-dessous).
  </p>
  <div class="map-table-wrap">
    <table class="map-table">
      <tr class="map-table-header"><th>Fonction</th><th>Action VPX</th><th>Mapping actif</th><th>Valeur VPX ([Input])</th><th>Rôle VPinFE</th><th>État</th><th>Actions</th></tr>
      """ + "".join(key_rows) + """
    </table>
  </div>

<div class="map-detect-modal" id="mapDetectModal">
  <div class="map-detect-box">
    <h2>Détection en cours</h2>
    <p>Appuie sur une touche clavier dans cette page ou sur un bouton joystick.</p>
    <div class="map-detect-count" id="mapDetectCountdown">30</div>
    <div class="map-detect-raw" id="mapDetectRaw">En attente...</div>
    <p><button class="button secondary" type="button" onclick="closeDetectPopup()">Annuler</button></p>
  </div>
</div>

<script>
let mapDetectTimer = null;
let mapDetectKeyHandler = null;
let mapDetectActive = false;

function clearInput(id) {
  const el = document.getElementById(id);
  const rawEl = document.getElementById(id.replace("key_", "raw_"));
  if (el) {
    el.value = "";
    el.dispatchEvent(new Event("input", {bubbles:true}));
    el.focus();
  }
  if (rawEl) rawEl.value = "";
}

function closeDetectPopup() {
  mapDetectActive = false;

  const modal = document.getElementById("mapDetectModal");
  if (modal) modal.style.display = "none";

  if (mapDetectTimer) {
    clearInterval(mapDetectTimer);
    mapDetectTimer = null;
  }

  if (mapDetectKeyHandler) {
    window.removeEventListener("keydown", mapDetectKeyHandler, true);
    mapDetectKeyHandler = null;
  }
}

function mergeBinding(current, binding) {
  // même règle que côté serveur (pincabos_vpx_input.merge_binding) : un bouton
  // joystick remplace les boutons joystick, une touche remplace les touches
  const isKey = binding.startsWith("Key;");
  const alts = String(current || "").split("|").map(s => s.trim()).filter(Boolean);
  const kept = alts.filter(a => a.startsWith("Key;") !== isKey);
  kept.push(binding);
  return kept.join(" | ");
}

async function detectInput(id) {
  const el = document.getElementById(id);
  const rawEl = document.getElementById(id.replace("key_", "raw_"));
  const modal = document.getElementById("mapDetectModal");
  const countdown = document.getElementById("mapDetectCountdown");
  const rawBox = document.getElementById("mapDetectRaw");

  if (!el) return;

  // KeyboardEvent.code -> scancode SDL (VPX écrit "Key;<scancode>")
  const keyMap = {
    Escape:41, Enter:40, Space:44, Tab:43, Backspace:42, Minus:45, Equal:46,
    BracketLeft:47, BracketRight:48, Backslash:49, Semicolon:51, Quote:52, Backquote:53,
    Comma:54, Period:55, Slash:56, CapsLock:57,
    ShiftLeft:225, ShiftRight:229, ControlLeft:224, ControlRight:228, AltLeft:226, AltRight:230,
    ArrowRight:79, ArrowLeft:80, ArrowDown:81, ArrowUp:82,
    Insert:73, Home:74, PageUp:75, Delete:76, End:77, PageDown:78, NumpadEnter:88
  };
  for (let i = 0; i < 26; i++) keyMap["Key" + String.fromCharCode(65 + i)] = 4 + i;
  for (let i = 1; i <= 9; i++) keyMap["Digit" + i] = 29 + i;
  keyMap.Digit0 = 39;
  for (let i = 1; i <= 12; i++) keyMap["F" + i] = 57 + i;

  mapDetectActive = true;
  let seconds = 30;

  if (modal) modal.style.display = "flex";
  if (countdown) countdown.textContent = seconds;
  if (rawBox) rawBox.textContent = "En attente...";
  el.focus();

  if (mapDetectTimer) clearInterval(mapDetectTimer);
  mapDetectTimer = setInterval(() => {
    seconds--;
    if (countdown) countdown.textContent = seconds;
    if (seconds <= 0) {
      if (rawBox) rawBox.textContent = "Timeout : aucune entrée détectée.";
      setTimeout(closeDetectPopup, 800);
    }
  }, 1000);

  function finish(binding, label, raw) {
    if (!mapDetectActive) return;
    el.value = mergeBinding(el.value, binding);
    el.dispatchEvent(new Event("input", {bubbles:true}));
    if (rawEl) rawEl.value = label;
    if (rawBox) rawBox.textContent = label + "  →  " + el.value + "   (" + raw + ")";
    setTimeout(closeDetectPopup, 900);
  }

  mapDetectKeyHandler = function(e) {
    if (!mapDetectActive) return;
    e.preventDefault();
    e.stopPropagation();
    const sc = keyMap[e.code];
    if (sc !== undefined) {
      finish("Key;" + sc, "Clavier : " + e.code, "clavier du navigateur code=" + e.code);
    } else if (rawBox) {
      rawBox.textContent = "Touche non gérée : " + e.code;
    }
  };

  window.addEventListener("keydown", mapDetectKeyHandler, true);

  // Côté cab : /dev/input (boutons du cab, clavier branché au cab). Le serveur
  // attend 8 s par appel ; on relance tant que la fenêtre est ouverte.
  try {
    while (mapDetectActive) {
      const r = await fetch("/inputs/detect-once", {method:"POST"});
      const data = await r.json();
      if (!mapDetectActive) break;
      if (data.ok) { finish(data.binding, data.label, data.raw); break; }
      if (data.error && data.error !== "timeout") { if (rawBox) rawBox.textContent = data.error; break; }
    }
  } catch(e) {
    if (rawBox) rawBox.textContent = "evdev non disponible, clavier du navigateur actif.";
  }
}
</script>


      </section>

      <aside class="map-master-right-v3">
<div class="np-grid-safe">
    <div class="np-panel-safe">
      <h3>🎯 Nudge X / Y</h3>
      <div class="nudge-scope-safe"><div class="nudge-dot-safe"></div></div>

      <div class="np-fields-safe">
        <label>Axe X """ + inputs_nudge_axis_select("nudge_axis_x", 0, "ABS_X", cfg.get("nudge_axis_x", "")) + """<span class="axis-help-text">VPX Axe 1 · ABS_X · mouvement gauche / droite</span></label>
        <label class="checkline"><input type="checkbox" name="nudge_invert_x" value="1" """ + inputs_checked(cfg, "nudge_invert_x") + """> Inverser X</label>

        <label>Axe Y """ + inputs_nudge_axis_select("nudge_axis_y", 1, "ABS_Y", cfg.get("nudge_axis_y", "")) + """<span class="axis-help-text">VPX Axe 2 · ABS_Y · mouvement avant / arrière</span></label>
        <label class="checkline"><input type="checkbox" name="nudge_invert_y" value="1" """ + inputs_checked(cfg, "nudge_invert_y") + """> Inverser Y</label>

        <label>Deadzone <input name="nudge_deadzone" value=\"""" + inputs_esc(cfg.get("nudge_deadzone", "0.08")) + """\"></label>
        <label>Max field <input name="nudge_maxfield" value=\"""" + inputs_esc(cfg.get("nudge_maxfield", "1.00")) + """\"></label>

        <label>Gain X <input name="nudge_gain_x" value=\"""" + inputs_esc(cfg.get("nudge_gain_x", "1.0")) + """\"></label>
        <label>Gain Y <input name="nudge_gain_y" value=\"""" + inputs_esc(cfg.get("nudge_gain_y", "1.0")) + """\"></label>

        <label class="checkline"><input type="checkbox" name="virtual_tilt_enabled" value="1" """ + inputs_checked(cfg, "virtual_tilt_enabled") + """> Virtual tilt</label>
        <label>Seuil tilt <input name="virtual_tilt_threshold" value=\"""" + inputs_esc(cfg.get("virtual_tilt_threshold", "0.85")) + """\"></label>
      </div>

      <p><button class="button" type="submit">Appliquer Nudge</button></p>
    </div>

    <div class="np-panel-safe">
      <h3>🕹️ Plunger Z</h3>
      <div class="plunger-track-safe" id="plunger_live_track">
          <div class="plunger-guide-safe deadzone"
               id="plunger_deadzone_marker"
               data-guide="deadzone"
               title="Deadzone : glisser pour ajuster">
            <span class="plunger-guide-label-safe">DZ</span>
          </div>
          <div class="plunger-guide-safe maxfield"
               id="plunger_maxfield_marker"
               data-guide="maxfield"
               title="Max field : glisser pour ajuster">
            <span class="plunger-guide-label-safe">MAX</span>
          </div>
          <div class="plunger-pointer-safe"></div>
        </div>

        <div class="plunger-live-readout" id="plunger_live_readout">
          <span class="plunger-live-led" id="plunger_live_led"></span>
          <span id="plunger_live_text">Connexion au DudesCab…</span>
        </div>
        <div class="plunger-live-values">
          <span>Brut : <strong id="plunger_live_raw">—</strong></span>
          <span>Position : <strong id="plunger_live_percent">—</strong></span>
        </div>
        <script>
        /* PINCABOS_LIVE_PLUNGER_UI_V1 */
        (function () {
          const pointer = document.querySelector(".plunger-pointer-safe");
          const readout = document.getElementById("plunger_live_readout");
          const led = document.getElementById("plunger_live_led");
          const text = document.getElementById("plunger_live_text");
          const raw = document.getElementById("plunger_live_raw");
          const percent = document.getElementById("plunger_live_percent");

          if (!pointer || !readout || !led || !text || !raw || !percent) return;

          let busy = false;

          function setState(ok, message) {
            led.classList.toggle("online", !!ok);
            led.classList.toggle("offline", !ok);
            text.textContent = message;
          }

          async function refreshPlunger() {
            if (busy) return;
            busy = true;

            try {
              const deviceSelect = document.querySelector(
                'select[name="nudge_axis_z"]'
              );
              const selectedDevice = deviceSelect ? deviceSelect.value : "";
              const response = await fetch(
                "/inputs/realtime-state?device="
                + encodeURIComponent(selectedDevice),
                { cache: "no-store" }
              );
              const data = await response.json();

              if (!data.ok) {
                setState(false, data.error || "DudesCab non disponible.");
                return;
              }

              const z = Number(data.axes.z);
              const min = Number(data.limits.z.min);
              const max = Number(data.limits.z.max);
              const ratio = max > min
                ? Math.max(0, Math.min(1, (z - min) / (max - min)))
                : 0;

              pointer.style.left = (ratio * 100).toFixed(2) + "%";
              raw.textContent = z;
              percent.textContent = (ratio * 100).toFixed(1) + "%";
              setState(true, "DudesCab live · " + data.device + " · ABS_Z");
            } catch (error) {
              setState(false, "Lecture live indisponible.");
            } finally {
              busy = false;
            }
          }

          refreshPlunger();

          window.setInterval(refreshPlunger, 100);
        })();
        </script>

        <script>
        /* PINCABOS_LIVE_PLUNGER_GUIDES_V3 */
        (function () {
          const track = document.getElementById("plunger_live_track");
          const deadzone = document.getElementById("plunger_deadzone_marker");
          const maxfield = document.getElementById("plunger_maxfield_marker");
          const deadzoneInput = document.querySelector('input[name="plunger_deadzone"]');
          const maxfieldInput = document.querySelector('input[name="plunger_maxfield"]');
          const invert = document.querySelector('input[name="plunger_invert"]');

          if (!track || !deadzone || !maxfield || !deadzoneInput || !maxfieldInput) return;

          let dragged = null;

          function clamp(value, low, high) {
            return Math.max(low, Math.min(high, value));
          }

          function inputNumber(input, fallback) {
            const value = parseFloat(input.value);
            return Number.isFinite(value) ? value : fallback;
          }

          function reversed() {
            return !!(invert && invert.checked);
          }

          function positionFor(value) {
            value = clamp(value, 0, 1);
            return reversed() ? 1 - value : value;
          }

          function valueFor(position) {
            position = clamp(position, 0, 1);
            return reversed() ? 1 - position : position;
          }

          function label(marker, text) {
            const node = marker.querySelector(".plunger-guide-label-safe");
            if (node) node.textContent = text;
          }

          function refresh() {
            const dz = clamp(inputNumber(deadzoneInput, 0), 0, 1);
            const mx = clamp(inputNumber(maxfieldInput, 1), 0, 1);

            deadzone.style.left = (positionFor(dz) * 100).toFixed(2) + "%";
            maxfield.style.left = (positionFor(mx) * 100).toFixed(2) + "%";

            label(deadzone, "DZ " + dz.toFixed(3));
            label(maxfield, "MAX " + mx.toFixed(3));
          }

          function move(event) {
            if (!dragged) return;

            const rect = track.getBoundingClientRect();
            if (!rect.width) return;

            const position = clamp((event.clientX - rect.left) / rect.width, 0, 1);
            const value = valueFor(position);
            const target = dragged === deadzone ? deadzoneInput : maxfieldInput;

            target.value = value.toFixed(3);
            target.dispatchEvent(new Event("input", { bubbles: true }));
            refresh();
          }

          function start(event) {
            event.preventDefault();
            dragged = event.currentTarget;
            dragged.setPointerCapture(event.pointerId);
            move(event);
          }

          function stop() {
            dragged = null;
          }

          deadzone.addEventListener("pointerdown", start);
          maxfield.addEventListener("pointerdown", start);
          window.addEventListener("pointermove", move);
          window.addEventListener("pointerup", stop);
          window.addEventListener("pointercancel", stop);

          ["input", "change"].forEach(function(eventName) {
            deadzoneInput.addEventListener(eventName, refresh);
            maxfieldInput.addEventListener(eventName, refresh);
            if (invert) invert.addEventListener(eventName, refresh);
          });

          refresh();
        })();
        </script>


      <div class="np-fields-safe">
        <label>Axe Z / Plunger """ + inputs_plunger_device_select(cfg.get("nudge_axis_z", "")) + """<span class="axis-help-text">VPX Axe 3 · ABS_Z · plunger analogique</span></label>
        <label>Deadzone plunger <input name="plunger_deadzone" value=\"""" + inputs_esc(cfg.get("plunger_deadzone", "0.03")) + """\"></label>

        <label>Min calibration <input name="plunger_min" value=\"""" + inputs_esc(cfg.get("plunger_min", "0")) + """\"></label>
        <label>Max calibration <input name="plunger_max" value=\"""" + inputs_esc(cfg.get("plunger_max", "65535")) + """\"></label>

        <label>Max field plunger <input name="plunger_maxfield" value=\"""" + inputs_esc(cfg.get("plunger_maxfield", "1.00")) + """\"></label>
        <label class="checkline"><input type="checkbox" name="plunger_invert" value="1" """ + inputs_checked(cfg, "plunger_invert") + """> Inverser plunger</label>

        <label>Émulation Launch Ball """ + inputs_select("launch_ball_emulation", cfg.get("launch_ball_emulation", "off"), [
          ("off", "Désactivée"),
          ("push", "Pousser à fond = Launch Ball"),
          ("pull", "Tirer à fond = Launch Ball"),
          ("both", "Pousser ou tirer = Launch Ball"),
      ]) + """</label>
      </div>

      <p class="plunger-apply-row">
          <button class="button" id="plunger_apply_button" type="submit"
                  name="apply_target" value="plunger">Appliquer Plunger</button>
          <span class="plunger-apply-note" id="plunger_apply_note">
            Sauvegarde le périphérique et les réglages ci-dessus.
          </span>
        </p>
    </div>
  </div>
        <!-- PINCABOS_VPX_ANALOG_CARD_V2 -->
        <section class="vpx-analog-card-v2">
          <h3>⚙️ Paramètres VPX — Plunger &amp; Nudge</h3>
          <p class="vpx-analog-note-v2">
            Valeurs actives lues dans <code>VPinballX.ini</code>, section <code>[Player]</code>.
          </p>
          <div class="vpx-analog-table-wrap-v2">
            <table class="vpx-analog-table-v2">
              <thead>
                <tr>
                  <th>Fonction</th>
                  <th>Clé VPX</th>
                  <th>Valeur</th>
                  <th>État</th>
                </tr>
              </thead>
              <tbody>
                """ + "".join(vpx_analog_rows) + """
              </tbody>
            </table>
          </div>

          <div class="vpx-analog-actions">
            <button class="button" type="submit"
                    formaction="/inputs/save-vpx-analog"
                    formmethod="post">
              Appliquer paramètres VPX
            </button>
            <span>Écrit seulement les paramètres Plunger/Nudge dans <code>[Player]</code>.</span>
          </div>
        </section>


  <details style="margin-top:16px;">
    <summary>Paramètres VPX dans [Player]</summary>
    <div class="map-table-wrap">
      <table class="map-table">
        <tr><th>Paramètre</th><th>Clé VPX</th><th>Valeur</th><th>Section</th><th>État</th></tr>
        """ + "".join(player_rows) + """
      </table>
    </div>
  </details>

      </aside>

    </div>
  </div>



<div class="card">
  <h2>Navigation VPinFE</h2>
  <p>Chaque fonction de VPinFE suit une action VPX : le bouton détecté ci-dessus sert aussi à choisir les tables.
  Les touches par défaut de VPinFE (flèches, Entrée, Échap…) sont conservées.""" + ("" if vpinfe_installed else " <span class='warn'>vpinfe.ini absent : rien ne sera écrit.</span>") + """</p>
  <div class="map-table-wrap">
    <table class="map-table">
      <tr class="map-table-header"><th>Fonction VPinFE</th><th>Clé</th><th>Suit l'action VPX</th><th>Bouton</th><th>Touches</th><th>Remarque</th></tr>
      """ + "".join(vpinfe_rows) + """
    </table>
  </div>
  <p class="warn">VPinFE lit sa configuration au démarrage : après sauvegarde, un bouton propose de le redémarrer.</p>
</div>

<div class="card">
  <button class="button" type="submit">Sauvegarder Map Commander</button>
  
</div>

</form>
"""
    return page("Map Commander", body)



# PINCABOS_LIVE_PLUNGER_ROUTE_V1

# PINCABOS_PLUNGER_USB_SELECTOR_V2

# PINCABOS_NUDGE_AXIS_USB_SELECTORS_V1
def inputs_usb_axis_devices(axis_number, axis_label):
    """Liste les périphériques evdev compatibles avec un axe ABS."""
    from pathlib import Path
    import glob
    import fcntl
    import struct

    def ev_iocgabs(axis):
        return 0x80184540 + int(axis)

    devices = []

    for path in sorted(glob.glob("/dev/input/event*")):
        name_file = Path(
            "/sys/class/input/" + Path(path).name + "/device/name"
        )

        try:
            name = name_file.read_text(errors="replace").strip()
        except Exception:
            continue

        try:
            with open(path, "rb", buffering=0) as dev:
                raw = fcntl.ioctl(
                    dev.fileno(),
                    ev_iocgabs(axis_number),
                    bytes(24),
                )

            value, minimum, maximum, fuzz, flat, resolution = struct.unpack(
                "6i", raw
            )

            if minimum == maximum:
                continue

            devices.append({
                "path": path,
                "name": name,
                "axis": axis_label,
                "minimum": minimum,
                "maximum": maximum,
            })

        except Exception:
            continue

    return devices


def inputs_nudge_axis_select(field_name, axis_number, axis_label, current):
    current = str(current or "").strip()
    devices = inputs_usb_axis_devices(axis_number, axis_label)

    parts = [
        '<select id="' + inputs_esc(field_name) + '" '
        'name="' + inputs_esc(field_name) + '" '
        'class="nudge-axis-device-select">',
        '<option value="">Auto — premier périphérique compatible</option>',
    ]

    current_found = False

    for item in devices:
        # On sauvegarde device + axe dans une seule valeur lisible.
        value = item["path"] + "|" + item["axis"]
        selected = " selected" if value == current else ""

        if selected:
            current_found = True

        label = (
            item["name"]
            + " · "
            + item["path"]
            + " · "
            + item["axis"]
            + " ["
            + str(item["minimum"])
            + " à "
            + str(item["maximum"])
            + "]"
        )

        parts.append(
            '<option value="'
            + inputs_esc(value)
            + '"'
            + selected
            + '>'
            + inputs_esc(label)
            + '</option>'
        )

    if current and not current_found:
        parts.append(
            '<option value="'
            + inputs_esc(current)
            + '" selected>Indisponible actuellement · '
            + inputs_esc(current)
            + '</option>'
        )

    parts.append("</select>")
    return "".join(parts)


def inputs_plunger_usb_devices():
    """Liste les périphériques input Linux possédant ABS_Z."""
    from pathlib import Path
    import glob
    import fcntl
    import struct

    def ev_iocgabs(axis):
        return 0x80184540 + int(axis)

    devices = []

    for path in sorted(glob.glob("/dev/input/event*")):
        name_file = Path("/sys/class/input/" + Path(path).name + "/device/name")

        try:
            name = name_file.read_text(errors="replace").strip()
        except Exception:
            continue

        try:
            with open(path, "rb", buffering=0) as dev:
                raw = fcntl.ioctl(dev.fileno(), ev_iocgabs(2), bytes(24))
                value, minimum, maximum, fuzz, flat, resolution = struct.unpack(
                    "6i", raw
                )

            if minimum == maximum:
                continue

            devices.append({
                "path": path,
                "name": name,
                "axis": "ABS_Z",
                "minimum": minimum,
                "maximum": maximum,
            })
        except Exception:
            continue

    return devices


def inputs_plunger_device_select(current):
    current = str(current or "").strip()
    devices = inputs_plunger_usb_devices()

    rows = [
        '<select id="nudge_axis_z" name="nudge_axis_z" class="plunger-device-select">',
        '<option value="">Auto — premier plunger USB détecté</option>',
    ]

    current_found = False

    for item in devices:
        selected = " selected" if item["path"] == current else ""

        if selected:
            current_found = True

        label = (
            item["name"]
            + " · "
            + item["path"]
            + " · ABS_Z ["
            + str(item["minimum"])
            + " à "
            + str(item["maximum"])
            + "]"
        )

        rows.append(
            '<option value="'
            + inputs_esc(item["path"])
            + '"'
            + selected
            + '>'
            + inputs_esc(label)
            + '</option>'
        )

    if current and not current_found:
        rows.append(
            '<option value="'
            + inputs_esc(current)
            + '" selected>Indisponible actuellement · '
            + inputs_esc(current)
            + '</option>'
        )

    rows.append("</select>")
    return "".join(rows)


def inputs_dudescab_gamepad_path(preferred_path=""):
    """Retourne le périphérique USB choisi ou le premier ABS_Z."""
    preferred_path = str(preferred_path or "").strip()
    devices = inputs_plunger_usb_devices()

    if preferred_path:
        for item in devices:
            if item["path"] == preferred_path:
                return item["path"], item["name"]

    if devices:
        return devices[0]["path"], devices[0]["name"]

    return "", ""


def inputs_dudescab_live_state(preferred_path=""):
    """Lit la position actuelle des axes sans consommer les events VPX."""
    import fcntl
    import struct
    import time

    def ev_iocgabs(axis):
        return 0x80184540 + int(axis)

    path, name = inputs_dudescab_gamepad_path(preferred_path)
    if not path:
        return {
            "ok": False,
            "error": "Interface gamepad DudesCab introuvable.",
        }

    try:
        axes = {}
        limits = {}

        with open(path, "rb", buffering=0) as dev:
            for axis_number, axis_name in ((0, "x"), (1, "y"), (2, "z")):
                raw = fcntl.ioctl(
                    dev.fileno(),
                    ev_iocgabs(axis_number),
                    bytes(24),
                )
                value, minimum, maximum, fuzz, flat, resolution = struct.unpack(
                    "6i", raw
                )
                axes[axis_name] = value
                limits[axis_name] = {
                    "min": minimum,
                    "max": maximum,
                    "flat": flat,
                }

        return {
            "ok": True,
            "device": path,
            "name": name,
            "axes": axes,
            "limits": limits,
            "timestamp": int(time.time() * 1000),
        }

    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
        }


@route("/inputs/realtime-state")
def inputs_realtime_state():
    preferred_path = request.args.get("device", "").strip()

    if not preferred_path:
        preferred_path = str(
            inputs_load_cfg().get("nudge_axis_z", "")
        ).strip()

    return jsonify(inputs_dudescab_live_state(preferred_path))



# PINCABOS_VPX_ANALOG_EDITABLE_V1
def inputs_rewrite_player_only(player_values):
    from pathlib import Path
    from datetime import datetime
    import shutil
    import subprocess

    ini = Path(PINCABOS_INPUTS_INI)

    if not ini.exists():
        raise FileNotFoundError(str(ini))

    backup_dir = Path("/opt/pincabos/backups/inputs-commander")
    backup_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = backup_dir / (
        "VPinballX.ini.backup-vpx-analog-" + stamp
    )

    shutil.copy2(ini, backup)

    lines, found = inputs_read_ini()
    start, end = inputs_find_section(lines, "Player")

    if start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append("[Player]")
        start = len(lines) - 1
        end = len(lines)

    managed_keys = [key for key, label, default in PINCABOS_INPUT_PLAYERMAP]

    before = lines[:start + 1]
    section = lines[start + 1:end]
    after = lines[end:]

    cleaned = []

    for line in section:
        stripped = line.strip()

        if "PinCabOS fonction(VPX Analog" in line:
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

    comment = (
        "; Modifié "
        + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        + " par PinCabOS fonction(VPX Analog Plunger/Nudge)"
    )

    new_section = [comment]

    for key in managed_keys:
        new_section.append(
            key + " = " + str(player_values.get(key, "")).strip()
        )

    ini.write_text(
        chr(10).join(before + cleaned + new_section + after) + chr(10)
    )

    try:
        subprocess.run(
            ["chown", "pinball:pinball", str(ini)],
            timeout=10,
            check=False,
        )
    except Exception:
        pass

    return str(backup)


@route("/inputs/save-vpx-analog", methods=["POST"])
def inputs_save_vpx_analog():
    allowed = {
        "PBWEnabled": "toggle",
        "NudgeStrength": "number",
        "LRAxis": "axis",
        "UDAxis": "axis",
        "LRAxisFlip": "toggle",
        "UDAxisFlip": "toggle",
        "PBWAccelGainX": "number",
        "PBWAccelGainY": "number",
        "PlungerAxis": "axis",
        "ReversePlungerAxis": "toggle",
    }

    values = {}

    for key, kind in allowed.items():
        raw = request.form.get("vpx_player_" + key, "").strip()

        if kind == "toggle":
            values[key] = "1" if raw == "1" else "0"
            continue

        if kind == "axis":
            if not raw:
                values[key] = ""
                continue

            axis = int(raw)

            if axis < 1 or axis > 8:
                raise ValueError(
                    key + " doit être entre 1 et 8."
                )

            values[key] = str(axis)
            continue

        if not raw:
            values[key] = ""
            continue

        number = float(raw)

        if number < 0 or number > 10:
            raise ValueError(
                key + " doit être entre 0 et 10."
            )

        values[key] = f"{number:.2f}"

    try:
        backup = inputs_rewrite_player_only(values)

        body = """
<div class="card">
  <h1>Paramètres VPX appliqués</h1>
  <p class="good">
    Les paramètres Plunger/Nudge ont été écrits dans
    <code>""" + inputs_esc(PINCABOS_INPUTS_INI) + """</code>.
  </p>
  <p>
    Backup :
    <code>""" + inputs_esc(backup) + """</code>
  </p>
  <a class="button" href="/inputs/map-commander">
    Retour Map Commander
  </a>
</div>
"""

        return page("Paramètres VPX", body)

    except Exception as exc:
        body = """
<div class="card">
  <h1>Erreur paramètres VPX</h1>
  <p class="warn">""" + inputs_esc(str(exc)) + """</p>
  <a class="button secondary" href="/inputs/map-commander">
    Retour Map Commander
  </a>
</div>
"""

        return page("Erreur paramètres VPX", body), 400


@route("/inputs/save", methods=["POST"])
def inputs_save():
    cfg = inputs_load_cfg()

    for key in [
        "input_mode",
        "capture_backend",
        "preferred_device",
        "dudes_profile",
        "dudes_shift_input",
        "dudes_nightmode_input",
        "nudge_axis_x",
        "nudge_axis_y",
        "nudge_axis_z",
        "nudge_deadzone",
        "nudge_gain_x",
        "nudge_gain_y",
        "virtual_tilt_threshold",
        "nudge_maxfield",
        "plunger_min",
        "plunger_max",
        "plunger_deadzone",
        "plunger_maxfield",
        "launch_ball_emulation",
        "stabilization_delay_ms",
    ]:
        cfg[key] = request.form.get(key, "").strip()

    for key in [
        "dudes_shift_enabled",
        "nudge_invert_x",
        "nudge_invert_y",
        "virtual_tilt_enabled",
        "plunger_invert",
    ]:
        cfg[key] = request.form.get(key) == "1"

    mappings = {}
    for action in vpxin.ACTION_IDS:
        if "map_" + action in request.form:
            mappings[action] = request.form.get("map_" + action, "").strip()
    policy = {}
    for fn, _label in vpxin.VPINFE_FUNCTIONS:
        if "vpinfe_" + fn in request.form:
            policy[fn] = request.form.get("vpinfe_" + fn, "").strip()
    if policy:
        cfg["vpinfe_policy"] = policy

    player_values = {}
    for key, label, default in PINCABOS_INPUT_PLAYERMAP:
        player_values[key] = request.form.get("player_" + key, "").strip()

    try:
        report = inputs_rewrite_ini(mappings, player_values, cfg.get("vpinfe_policy"))
        inputs_save_cfg(cfg)
        return inputs_report_html("Map Commander sauvegardé", report)
    except ValueError as e:
        body = """
<div class="card">
  <h1>Mapping refusé</h1>
  <p class="bad">""" + inputs_esc(e) + """</p>
  <p>Format attendu : <code>Key;&lt;scancode&gt;</code> ou <code>SDLJoy_&lt;guid&gt;_&lt;n&gt;;&lt;bouton&gt;</code>, alternatives séparées par <code>|</code>. Rien n'a été écrit.</p>
  <a class="button" href="/inputs/map-commander">Retour Map Commander</a>
</div>
"""
        return page("Inputs", body)
    except Exception as e:
        body = """
<div class="card">
  <h1>Erreur Inputs Commander</h1>
  <p class="bad"><code>""" + inputs_esc(e) + """</code></p>
  <a class="button" href="/inputs">Retour</a>
</div>
"""
        return page("Inputs", body)


@route("/inputs/detect-once", methods=["POST"])
def inputs_detect_once():
    """Un appui sur le cab -> binding VPX ("Key;225", "SDLJoy_<guid>_1;3"), décodé."""
    try:
        res = vpxin.detect_once(timeout=8.0)
    except Exception as exc:
        return jsonify({"ok": False, "error": "détection impossible : " + str(exc)})
    if not res:
        return jsonify({"ok": False, "error": "timeout"})
    if "error" in res:
        return jsonify({"ok": False, "error": res["error"] + " — vérifie les permissions du service PinCabOS."})
    res["ok"] = True
    return jsonify(res)


@route("/inputs/defaults", methods=["POST"])
def inputs_defaults():
    cfg = dict(PINCABOS_INPUTS_DEFAULT_CFG)
    inputs_save_cfg(cfg)

    mappings = dict(vpxin.ACTION_DEFAULTS)
    player_values = {key: default for key, label, default in PINCABOS_INPUT_PLAYERMAP}

    try:
        report = inputs_rewrite_ini(mappings, player_values, cfg.get("vpinfe_policy"))
        return inputs_report_html("Défauts VPX appliqués", report, "<p>Boutons remis aux défauts clavier de VPX (Shift gauche/droit, 1, 5, Entrée…).</p>")
    except Exception as e:
        body = """
<div class="card">
  <h1>Erreur preset Inputs</h1>
  <p class="bad"><code>""" + inputs_esc(e) + """</code></p>
  <a class="button" href="/inputs">Retour</a>
</div>
"""
        return page("Inputs", body)

# ===============================================================
# PINCABOS_DUDESCAB_INPUTS_STUDIO_V2
# ===============================================================

STUDIO_AXIS_LABELS = {
    1: "X Axis",
    2: "Y Axis",
    3: "Z Axis",
    4: "RX Axis",
    5: "RY Axis",
    6: "RZ Axis",
    7: "Slider 1",
    8: "Slider 2",
}

STUDIO_ABS_LABELS = {
    0: "ABS_X",
    1: "ABS_Y",
    2: "ABS_Z",
    3: "ABS_RX",
    4: "ABS_RY",
    5: "ABS_RZ",
    6: "ABS_THROTTLE",
    7: "ABS_RUDDER",
    8: "ABS_WHEEL",
    9: "ABS_GAS",
    10: "ABS_BRAKE",
    16: "ABS_HAT0X",
    17: "ABS_HAT0Y",
}


def studio_vpx_ini():
    candidates = []

    vpinfe_ini = Path("/home/pinball/.config/vpinfe/vpinfe.ini")
    if vpinfe_ini.exists():
        for line in vpinfe_ini.read_text(errors="replace").splitlines():
            text = line.strip()
            if text.lower().startswith("vpxinipath") and "=" in text:
                value = text.split("=", 1)[1].strip()
                if value:
                    candidates.append(Path(value))

    candidates.extend([
        Path(vpxin.PREF_INI),
        Path(vpxin.LEGACY_INI),
    ])

    seen = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        if candidate.exists():
            return candidate

    return candidates[0]


def studio_player_values():
    ini = studio_vpx_ini()
    values = {}

    if not ini.exists():
        return values

    section = ""
    for line in ini.read_text(errors="replace").splitlines():
        text = line.strip()

        if text.startswith("[") and text.endswith("]"):
            section = text[1:-1].strip()
            continue

        if section.lower() != "player":
            continue

        if "=" not in text or text.startswith((";", "#")):
            continue

        key, value = text.split("=", 1)
        values[key.strip()] = value.strip()

    return values


def studio_event_name(device):
    try:
        path = Path("/sys/class/input") / Path(device).name / "device" / "name"
        if path.exists():
            return path.read_text(errors="replace").strip()
    except Exception:
        pass

    return Path(device).name


def studio_event_properties(device):
    try:
        result = subprocess.run(
            ["udevadm", "info", "--query=property", "--name", device],
            text=True,
            capture_output=True,
            timeout=3,
            check=False,
        )

        props = {}
        for line in (result.stdout or "").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                props[key.strip()] = value.strip()

        return props
    except Exception:
        return {}


def studio_devices():
    devices = []

    for device in sorted(glob.glob("/dev/input/event*")):
        props = studio_event_properties(device)
        name = studio_event_name(device)

        vendor_id = props.get("ID_VENDOR_ID", "").lower()
        model_id = props.get("ID_MODEL_ID", "").lower()

        searchable = " ".join([
            name,
            props.get("ID_VENDOR", ""),
            props.get("ID_MODEL", ""),
            props.get("ID_VENDOR_FROM_DATABASE", ""),
            props.get("ID_MODEL_FROM_DATABASE", ""),
        ]).lower()

        is_dudescab = (
            "dude" in searchable
            or "arnoz" in searchable
            or (vendor_id == "2e8a" and model_id == "106f")
        )

        devices.append({
            "path": device,
            "name": name,
            "vendor_id": vendor_id,
            "model_id": model_id,
            "is_dudescab": is_dudescab,
        })

    return devices


def studio_capture_nodes(selected_device):
    selected_device = str(selected_device or "auto")
    devices = studio_devices()

    if selected_device != "auto":
        if not re.fullmatch(r"/dev/input/event\d+", selected_device):
            raise ValueError("Périphérique input invalide.")

        if not any(item["path"] == selected_device for item in devices):
            raise ValueError("Périphérique input non trouvé.")

        return [selected_device]

    dudes = [item["path"] for item in devices if item["is_dudescab"]]
    if dudes:
        return dudes

    return [item["path"] for item in devices]


def studio_abs_to_vpx_axis(abs_code):
    if 0 <= int(abs_code) <= 7:
        return int(abs_code) + 1
    return None


def studio_capture_axes(selected_device, seconds=12):
    import select

    seconds = max(3, min(int(seconds), 15))
    nodes = studio_capture_nodes(selected_device)

    event_format = "llHHI"
    event_size = struct.calcsize(event_format)

    opened = []
    fd_to_node = {}
    stats = {}

    try:
        for node in nodes:
            try:
                fd = os.open(node, os.O_RDONLY | os.O_NONBLOCK)
                opened.append((node, fd))
                fd_to_node[fd] = node
            except OSError:
                pass

        if not opened:
            raise RuntimeError(
                "Aucun périphérique evdev lisible. Vérifie les permissions de la WebApp."
            )

        deadline = time.time() + seconds

        while time.time() < deadline:
            ready, _, _ = select.select(
                [fd for _, fd in opened],
                [],
                [],
                0.25,
            )

            for fd in ready:
                try:
                    raw = os.read(fd, event_size)
                except OSError:
                    continue

                if len(raw) != event_size:
                    continue

                _, _, event_type, code, value = struct.unpack(event_format, raw)

                if event_type != 3 or code not in STUDIO_ABS_LABELS:
                    continue

                key = (fd, int(code))

                if key not in stats:
                    stats[key] = {
                        "minimum": int(value),
                        "maximum": int(value),
                        "current": int(value),
                        "samples": 1,
                    }
                else:
                    stats[key]["minimum"] = min(stats[key]["minimum"], int(value))
                    stats[key]["maximum"] = max(stats[key]["maximum"], int(value))
                    stats[key]["current"] = int(value)
                    stats[key]["samples"] += 1

    finally:
        for _, fd in opened:
            try:
                os.close(fd)
            except Exception:
                pass

    axes = []

    for (fd, abs_code), data in stats.items():
        spread = data["maximum"] - data["minimum"]

        if spread <= 0:
            continue

        axes.append({
            "device": fd_to_node.get(fd, "event"),
            "abs_code": abs_code,
            "abs_name": STUDIO_ABS_LABELS.get(abs_code, f"ABS_{abs_code}"),
            "vpx_axis": studio_abs_to_vpx_axis(abs_code),
            "minimum": data["minimum"],
            "maximum": data["maximum"],
            "current": data["current"],
            "samples": data["samples"],
            "spread": spread,
        })

    axes.sort(key=lambda item: item["spread"], reverse=True)

    return {
        "nodes": nodes,
        "axes": axes,
    }


def studio_write_player(values, label):
    ini = studio_vpx_ini()

    if not ini.exists():
        raise FileNotFoundError(f"VPinballX.ini introuvable: {ini}")

    backup_dir = Path("/opt/pincabos/backups/inputs-commander")
    backup_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = backup_dir / f"VPinballX.ini.backup-dudescab-{label}-{stamp}"

    shutil.copy2(ini, backup)

    file_mode = ini.stat().st_mode & 0o777
    lines = ini.read_text(errors="replace").splitlines()

    start, end = inputs_find_section(lines, "Player")

    if start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append("[Player]")
        start = len(lines) - 1
        end = len(lines)

    managed_keys = set(values.keys())
    kept = []

    for line in lines[start + 1:end]:
        stripped = line.strip()

        if "PinCabOS fonction(Dude's Cab Inputs Studio" in line:
            continue

        if "=" in line and not stripped.startswith((";", "#")):
            key = line.split("=", 1)[0].strip()
            if key in managed_keys:
                continue

        kept.append(line)

    while kept and not kept[-1].strip():
        kept.pop()

    if kept:
        kept.append("")

    comment = (
        "; Modifié "
        + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        + " par PinCabOS fonction(Dude's Cab Inputs Studio - "
        + label
        + ")"
    )

    updated = (
        lines[:start + 1]
        + kept
        + [comment]
        + [f"{key} = {value}" for key, value in values.items()]
        + lines[end:]
    )

    temporary = ini.with_name(ini.name + ".pincabos-inputs-tmp")
    temporary.write_text("\n".join(updated) + "\n", encoding="utf-8")
    os.chmod(temporary, file_mode)
    os.replace(temporary, ini)

    try:
        subprocess.run(
            ["chown", "pinball:pinball", str(ini)],
            timeout=5,
            check=False,
        )
    except Exception:
        pass

    return str(backup), str(ini)


def studio_axis(payload, key):
    raw = str(payload.get(key, "")).strip()

    if not raw:
        raise ValueError(f"Axe VPX manquant: {key}")

    value = int(raw)

    if value < 1 or value > 8:
        raise ValueError(f"Axe VPX invalide: {key}")

    return value


def studio_gain(payload, key):
    value = float(str(payload.get(key, "1.00")).strip())

    if value < 0.01 or value > 10:
        raise ValueError(f"Gain invalide: {key}")

    return f"{value:.2f}"


def studio_enabled(payload, key):
    return str(payload.get(key, "")).lower() in (
        "1", "true", "yes", "on"
    )


def studio_axis_options(current):
    current = str(current or "")
    html_parts = ['<option value="">Sélectionner un axe</option>']

    for number, label in STUDIO_AXIS_LABELS.items():
        selected = " selected" if current == str(number) else ""
        html_parts.append(
            '<option value="'
            + str(number)
            + '"'
            + selected
            + ">"
            + "Axe VPX "
            + str(number)
            + " — "
            + label
            + "</option>"
        )

    return "".join(html_parts)


def studio_device_options(devices, current):
    current = str(current or "auto")

    html_parts = [
        '<option value="auto">Auto — interfaces Dude’s Cab détectées</option>'
    ]

    for item in devices:
        selected = " selected" if item["path"] == current else ""
        category = "Dude’s Cab" if item["is_dudescab"] else "Autre périphérique"
        label = f"{category} · {item['name']} · {item['path']}"

        html_parts.append(
            '<option value="'
            + inputs_esc(item["path"])
            + '"'
            + selected
            + ">"
            + inputs_esc(label)
            + "</option>"
        )

    return "".join(html_parts)


@route("/inputs/studio/capture", methods=["POST"])
def inputs_studio_capture_v2():
    payload = request.get_json(silent=True) or {}

    try:
        result = studio_capture_axes(
            payload.get("device", "auto"),
            payload.get("seconds", 12),
        )
        result["ok"] = True
        return jsonify(result)

    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@route("/inputs/studio/apply", methods=["POST"])
def inputs_studio_apply_v2():
    payload = request.get_json(silent=True) or {}
    kind = str(payload.get("kind", "")).strip().lower()

    try:
        cfg = inputs_load_cfg()

        if kind == "nudge":
            values = {
                "LRAxis": studio_axis(payload, "lr_axis"),
                "UDAxis": studio_axis(payload, "ud_axis"),
                "LRAxisFlip": 1 if studio_enabled(payload, "lr_flip") else 0,
                "UDAxisFlip": 1 if studio_enabled(payload, "ud_flip") else 0,
                "PBWEnabled": 1 if studio_enabled(payload, "enabled") else 0,
                "PBWAccelGainX": studio_gain(payload, "gain_x"),
                "PBWAccelGainY": studio_gain(payload, "gain_y"),
            }

            backup, ini = studio_write_player(values, "Nudge")

            cfg["dudescab_nudge"] = {
                "device": str(payload.get("device", "auto")),
                "lr_axis": values["LRAxis"],
                "ud_axis": values["UDAxis"],
                "lr_flip": bool(values["LRAxisFlip"]),
                "ud_flip": bool(values["UDAxisFlip"]),
                "gain_x": values["PBWAccelGainX"],
                "gain_y": values["PBWAccelGainY"],
            }

            inputs_save_cfg(cfg)

            return jsonify({
                "ok": True,
                "backup": backup,
                "ini": ini,
                "values": values,
            })

        if kind == "plunger":
            values = {
                "PlungerAxis": studio_axis(payload, "plunger_axis"),
                "ReversePlungerAxis": 1 if studio_enabled(payload, "reverse") else 0,
            }

            backup, ini = studio_write_player(values, "Plunger")

            cfg["dudescab_plunger"] = {
                "device": str(payload.get("device", "auto")),
                "axis": values["PlungerAxis"],
                "reverse": bool(values["ReversePlungerAxis"]),
                "minimum": str(payload.get("minimum", "")).strip(),
                "maximum": str(payload.get("maximum", "")).strip(),
            }

            inputs_save_cfg(cfg)

            return jsonify({
                "ok": True,
                "backup": backup,
                "ini": ini,
                "values": values,
            })

        raise ValueError("Type d’application invalide.")

    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


def inputs_studio_page_v2():
    cfg = inputs_load_cfg()
    player = studio_player_values()
    devices = studio_devices()

    nudge_cfg = cfg.get("dudescab_nudge", {})
    plunger_cfg = cfg.get("dudescab_plunger", {})

    if not isinstance(nudge_cfg, dict):
        nudge_cfg = {}

    if not isinstance(plunger_cfg, dict):
        plunger_cfg = {}

    dude_devices = [item for item in devices if item["is_dudescab"]]

    current_device = nudge_cfg.get("device", "auto")
    lr_axis = player.get("LRAxis", nudge_cfg.get("lr_axis", ""))
    ud_axis = player.get("UDAxis", nudge_cfg.get("ud_axis", ""))
    plunger_axis = player.get("PlungerAxis", plunger_cfg.get("axis", ""))

    def checked(value):
        return "checked" if str(value) == "1" else ""

    template = """
<style>
.inputs-studio { max-width:1660px; margin:0 auto; color:#111; }
.inputs-studio * { box-sizing:border-box; }
.studio-shell { background:#efefef; border:1px solid #999; border-radius:14px; padding:18px; box-shadow:0 8px 32px rgba(0,0,0,.35); }
.studio-titlebar { display:flex; justify-content:space-between; gap:16px; align-items:center; padding-bottom:14px; border-bottom:1px solid #bebebe; }
.studio-titlebar h1 { font-size:25px; margin:0; }
.studio-titlebar p { margin:5px 0 0; color:#444; }
.studio-badge { border-radius:7px; padding:9px 13px; font-weight:800; white-space:nowrap; border:1px solid #777; }
.studio-badge.ok { color:#083a1b; background:#a9ecbc; }
.studio-badge.warn { color:#4b2e00; background:#ffe29a; }
.studio-grid { display:grid; grid-template-columns:minmax(280px,.7fr) minmax(560px,1.5fr) minmax(280px,.7fr); gap:14px; margin-top:14px; }
.studio-panel { border:1px solid #9b9b9b; background:#fafafa; min-width:0; }
.studio-panel h2 { margin:0; padding:10px 12px; font-size:17px; background:#dedede; border-bottom:1px solid #aaa; }
.studio-body { padding:12px; }
.studio-note { margin:0 0 12px; line-height:1.45; color:#444; }
.studio-label { display:grid; gap:5px; font-weight:700; font-size:13px; margin-bottom:10px; }
.studio-input,.studio-select { width:100%; min-height:36px; padding:6px 8px; background:#fff; color:#111; border:1px solid #777; }
.studio-btn { min-height:36px; padding:7px 12px; cursor:pointer; font-weight:800; border:1px solid #555; color:#111; background:linear-gradient(#fff,#d8d8d8); border-radius:4px; }
.studio-btn:hover { background:linear-gradient(#fff5ca,#ecc269); }
.studio-btn.primary { background:linear-gradient(#fff2b0,#e7b440); }
.studio-btn-row { display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }
.studio-fieldset { border:1px solid #aaa; padding:10px; margin:12px 0 0; }
.studio-fieldset legend { padding:0 6px; font-weight:800; }
.studio-axis-grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
.studio-check { display:flex; align-items:center; gap:8px; margin-top:10px; font-weight:700; }
.studio-check input { width:18px; height:18px; }
.studio-live { min-height:148px; max-height:220px; overflow:auto; white-space:pre-wrap; font:12px/1.45 monospace; color:#d7ffd9; background:#141414; border:1px solid #555; padding:10px; }
.studio-status { min-height:22px; margin-top:10px; font-weight:800; }
.studio-mini-table { width:100%; border-collapse:collapse; font-size:13px; }
.studio-mini-table td { border-bottom:1px solid #d0d0d0; padding:8px 4px; }
.studio-mini-table td:last-child { text-align:right; font-family:monospace; }
.studio-link { display:inline-block; margin-top:12px; text-decoration:none; }
.studio-toast { display:none; position:fixed; z-index:99999; right:20px; bottom:20px; max-width:600px; padding:14px; color:#fff; background:#1e1e1e; border:2px solid #e5b441; box-shadow:0 8px 30px rgba(0,0,0,.5); }
@media(max-width:1150px){ .studio-grid{ grid-template-columns:1fr; } }
</style>

<div class="inputs-studio">
  <div class="studio-shell">
    <div class="studio-titlebar">
      <div>
        <h1>Keys, Nudge and Plunger</h1>
        <p>Configuration VPX du Dude’s Cab. Les boutons numériques restent dans Map Commander.</p>
      </div>
      <div class="studio-badge __DEVICE_CLASS__">__DEVICE_TEXT__</div>
    </div>

    <div class="studio-grid">
      <section class="studio-panel">
        <h2>Button Assignments</h2>
        <div class="studio-body">
          <p class="studio-note">Les flippers, Start, Coin, Magna Save, Exit et les autres boutons restent configurés dans Map Commander.</p>

          <table class="studio-mini-table">
            <tr><td>Flipper gauche</td><td>Map Commander</td></tr>
            <tr><td>Flipper droit</td><td>Map Commander</td></tr>
            <tr><td>Start / Coin</td><td>Map Commander</td></tr>
            <tr><td>Magna Save</td><td>Map Commander</td></tr>
            <tr><td>Exit / Pause</td><td>Map Commander</td></tr>
          </table>

          <a class="studio-btn studio-link" href="/inputs/map-commander">Ouvrir Map Commander</a>

          <fieldset class="studio-fieldset">
            <legend>Fichier VPX actif</legend>
            <label class="studio-label">
              VPinballX.ini
              <input class="studio-input" readonly value="__INI_PATH__">
            </label>
            <p class="studio-note">Un backup est créé avant chaque application.</p>
          </fieldset>
        </div>
      </section>

      <section class="studio-panel">
        <h2>Nudge, Plumb, Plunger</h2>
        <div class="studio-body">
          <label class="studio-label">
            Interface à écouter
            <select id="studio-device" class="studio-select">__DEVICE_OPTIONS__</select>
          </label>

          <div class="studio-btn-row">
            <button class="studio-btn" type="button" onclick="studioCapture('nudge', this)">Détecter les axes Nudge</button>
            <button class="studio-btn" type="button" onclick="studioCapture('plunger', this)">Calibrer le Plunger</button>
          </div>

          <fieldset class="studio-fieldset">
            <legend>Nudge analogique</legend>

            <div class="studio-axis-grid">
              <label class="studio-label">
                X Axis (L/R)
                <select id="nudge-lr-axis" class="studio-select">__LR_OPTIONS__</select>
              </label>

              <label class="studio-label">
                Y Axis (U/D)
                <select id="nudge-ud-axis" class="studio-select">__UD_OPTIONS__</select>
              </label>

              <label class="studio-label">
                X Gain
                <input id="nudge-gain-x" class="studio-input" type="number" min="0.01" max="10" step="0.01" value="__GAIN_X__">
              </label>

              <label class="studio-label">
                Y Gain
                <input id="nudge-gain-y" class="studio-input" type="number" min="0.01" max="10" step="0.01" value="__GAIN_Y__">
              </label>
            </div>

            <label class="studio-check"><input id="nudge-enable" type="checkbox" __NUDGE_ENABLE__> Enable Analog Nudge</label>
            <label class="studio-check"><input id="nudge-lr-flip" type="checkbox" __LR_FLIP__> Reverse X Axis</label>
            <label class="studio-check"><input id="nudge-ud-flip" type="checkbox" __UD_FLIP__> Reverse Y Axis</label>

            <div class="studio-btn-row">
              <button class="studio-btn primary" type="button" onclick="studioApply('nudge', this)">Appliquer Nudge à VPX</button>
            </div>

            <div id="nudge-status" class="studio-status"></div>
          </fieldset>

          <fieldset class="studio-fieldset">
            <legend>Plunger</legend>

            <div class="studio-axis-grid">
              <label class="studio-label">
                Plunger Axis
                <select id="plunger-axis" class="studio-select">__PLUNGER_OPTIONS__</select>
              </label>

              <label class="studio-label">
                Course détectée
                <input id="plunger-range" class="studio-input" readonly value="__PLUNGER_RANGE__">
              </label>
            </div>

            <label class="studio-check"><input id="plunger-reverse" type="checkbox" __PLUNGER_REVERSE__> Reverse Plunger Axis</label>

            <div class="studio-btn-row">
              <button class="studio-btn primary" type="button" onclick="studioApply('plunger', this)">Appliquer Plunger à VPX</button>
            </div>

            <div id="plunger-status" class="studio-status"></div>
          </fieldset>

          <fieldset class="studio-fieldset">
            <legend>Détection réelle</legend>
            <div id="studio-live" class="studio-live">Clique Détecter les axes Nudge, puis bouge le cabinet gauche/droite et avant/arrière.

Clique Calibrer le Plunger, puis tire et pousse le plunger complètement.</div>
          </fieldset>
        </div>
      </section>

      <section class="studio-panel">
        <h2>Controller Status</h2>
        <div class="studio-body">
          <table class="studio-mini-table">
            <tr><td>USB Dude’s Cab</td><td>__USB_STATE__</td></tr>
            <tr><td>Interface(s) input</td><td>__EVENT_COUNT__</td></tr>
            <tr><td>Nudge X Axis</td><td>__CURRENT_LR__</td></tr>
            <tr><td>Nudge Y Axis</td><td>__CURRENT_UD__</td></tr>
            <tr><td>Plunger Axis</td><td>__CURRENT_PLUNGER__</td></tr>
            <tr><td>Input API</td><td>VPX DirectInput</td></tr>
          </table>

          <fieldset class="studio-fieldset">
            <legend>Utilisation</legend>
            <p class="studio-note">
              1. Détecte les axes.<br>
              2. Vérifie X, Y et Plunger.<br>
              3. Applique à VPX.<br>
              4. Redémarre la table VPX.
            </p>
          </fieldset>

          <fieldset class="studio-fieldset">
            <legend>Sécurité</legend>
            <p class="studio-note">Cette page ne modifie pas VPinFE, DOF, les tables ou les fichiers DirectOutputConfig.</p>
          </fieldset>
        </div>
      </section>
    </div>
  </div>
</div>

<div id="studio-toast" class="studio-toast"></div>

<script>
function studioToast(message, error) {
  const toast = document.getElementById("studio-toast");
  toast.textContent = message;
  toast.style.display = "block";
  toast.style.borderColor = error ? "#ff4c4c" : "#e5b441";
  window.setTimeout(() => { toast.style.display = "none"; }, 8000);
}

function studioAxesText(axes) {
  if (!axes || axes.length === 0) {
    return "Aucun axe ABS n’a bougé. Vérifie l’interface choisie puis recommence.";
  }

  return axes.map((axis, index) => {
    const vpx = axis.vpx_axis ? ("VPX Axis " + axis.vpx_axis) : "non attribuable";
    return (
      (index + 1) + ". " + axis.device + " · " + axis.abs_name
      + " → " + vpx
      + " · min=" + axis.minimum
      + " max=" + axis.maximum
      + " · " + axis.samples + " événements"
    );
  }).join("\\n");
}

function studioSuggest(kind, axes) {
  const usable = (axes || []).filter(axis => axis.vpx_axis);

  if (kind === "nudge") {
    if (usable[0]) document.getElementById("nudge-lr-axis").value = usable[0].vpx_axis;
    if (usable[1]) document.getElementById("nudge-ud-axis").value = usable[1].vpx_axis;
  }

  if (kind === "plunger" && usable[0]) {
    document.getElementById("plunger-axis").value = usable[0].vpx_axis;
    document.getElementById("plunger-range").value =
      usable[0].minimum + " → " + usable[0].maximum;
  }
}

async function studioCapture(kind, button) {
  const live = document.getElementById("studio-live");
  const device = document.getElementById("studio-device").value;

  button.disabled = true;

  live.textContent = kind === "nudge"
    ? "Détection active pendant 12 secondes...\\nBouge maintenant le cabinet gauche/droite et avant/arrière."
    : "Calibration active pendant 12 secondes...\\nTire puis pousse complètement le plunger.";

  try {
    const response = await fetch("/inputs/studio/capture", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({device: device, seconds: 12})
    });

    const result = await response.json();

    if (!result.ok) throw new Error(result.error || "Détection impossible.");

    live.textContent = studioAxesText(result.axes);
    studioSuggest(kind, result.axes);
    studioToast("Détection terminée. Vérifie les axes avant l’application.", false);

  } catch (error) {
    live.textContent = "Erreur: " + String(error.message || error);
    studioToast("Détection impossible: " + String(error.message || error), true);

  } finally {
    button.disabled = false;
  }
}

async function studioApply(kind, button) {
  const device = document.getElementById("studio-device").value;
  const status = document.getElementById(kind + "-status");

  const payload = {kind: kind, device: device};

  if (kind === "nudge") {
    payload.lr_axis = document.getElementById("nudge-lr-axis").value;
    payload.ud_axis = document.getElementById("nudge-ud-axis").value;
    payload.lr_flip = document.getElementById("nudge-lr-flip").checked;
    payload.ud_flip = document.getElementById("nudge-ud-flip").checked;
    payload.enabled = document.getElementById("nudge-enable").checked;
    payload.gain_x = document.getElementById("nudge-gain-x").value;
    payload.gain_y = document.getElementById("nudge-gain-y").value;
  } else {
    payload.plunger_axis = document.getElementById("plunger-axis").value;
    payload.reverse = document.getElementById("plunger-reverse").checked;

    const range = document.getElementById("plunger-range").value.split("→");
    payload.minimum = (range[0] || "").trim();
    payload.maximum = (range[1] || "").trim();
  }

  button.disabled = true;
  status.textContent = "Écriture de VPinballX.ini et backup...";

  try {
    const response = await fetch("/inputs/studio/apply", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload)
    });

    const result = await response.json();

    if (!result.ok) throw new Error(result.error || "Application impossible.");

    status.textContent = "Appliqué. Redémarre une table VPX pour charger les nouveaux paramètres.";
    studioToast("VPX mis à jour. Backup: " + result.backup, false);

  } catch (error) {
    status.textContent = "Erreur: " + String(error.message || error);
    studioToast("Application impossible: " + String(error.message || error), true);

  } finally {
    button.disabled = false;
  }
}
</script>
"""

    plunger_range = (
        str(plunger_cfg.get("minimum", ""))
        + (
            " → "
            if plunger_cfg.get("minimum", "") or plunger_cfg.get("maximum", "")
            else ""
        )
        + str(plunger_cfg.get("maximum", ""))
    )

    rendered = (
        template
        .replace("__DEVICE_CLASS__", "ok" if dude_devices else "warn")
        .replace(
            "__DEVICE_TEXT__",
            inputs_esc("Dude’s Cab détecté" if dude_devices else "Dude’s Cab non détecté"),
        )
        .replace("__INI_PATH__", inputs_esc(str(studio_vpx_ini())))
        .replace("__DEVICE_OPTIONS__", studio_device_options(devices, current_device))
        .replace("__LR_OPTIONS__", studio_axis_options(lr_axis))
        .replace("__UD_OPTIONS__", studio_axis_options(ud_axis))
        .replace("__PLUNGER_OPTIONS__", studio_axis_options(plunger_axis))
        .replace("__GAIN_X__", inputs_esc(player.get("PBWAccelGainX", "1.00")))
        .replace("__GAIN_Y__", inputs_esc(player.get("PBWAccelGainY", "1.00")))
        .replace("__NUDGE_ENABLE__", checked(player.get("PBWEnabled", "0")))
        .replace("__LR_FLIP__", checked(player.get("LRAxisFlip", "0")))
        .replace("__UD_FLIP__", checked(player.get("UDAxisFlip", "0")))
        .replace("__PLUNGER_REVERSE__", checked(player.get("ReversePlungerAxis", "0")))
        .replace("__PLUNGER_RANGE__", inputs_esc(plunger_range))
        .replace("__USB_STATE__", "2e8a:106f" if dude_devices else "à détecter")
        .replace("__EVENT_COUNT__", str(len(dude_devices)))
        .replace("__CURRENT_LR__", inputs_esc(str(lr_axis or "non configuré")))
        .replace("__CURRENT_UD__", inputs_esc(str(ud_axis or "non configuré")))
        .replace("__CURRENT_PLUNGER__", inputs_esc(str(plunger_axis or "non configuré")))
    )

    return page("Keys, Nudge and Plunger", rendered)


ROUTES[:] = [
    (rule, options, inputs_map_commander_page if rule == "/inputs" else view_func)
    for rule, options, view_func in ROUTES
]

# ===============================================================
# END PINCABOS_DUDESCAB_INPUTS_STUDIO_V2
# ===============================================================
