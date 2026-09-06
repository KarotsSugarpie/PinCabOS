# PinCabOS-File created by Karots Sugarpie
import urllib.error
import urllib.request
import sqlite3
import tempfile
try:
    import pincabos_ini
except ImportError:   # hors /opt (tests, depot) : le module vit a cote des outils
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "tools"))
    import pincabos_ini
import zipfile
import mimetypes
import urllib.parse
from flask import send_file, request, redirect, session
from screen import screen_bp
from internal_disk import internal_disk_bp
import shutil
import uuid
import shlex
from werkzeug.utils import secure_filename
from dashboard_plus import render_dashboard
from pincabos_webapp_keyboard_tools_v6 import register_keyboard_tools_v6 as pco_register_keyboard_tools_v6
from pincabos_webapp_keyboard import register_keyboard_routes as pco_register_keyboard_routes
from pincabos_webapp_dashboard_control import register_dashboard_control_routes as pco_register_dashboard_control_routes
from flask import Flask, redirect, url_for, jsonify, request
from pathlib import Path
from tools import register_tools_routes

# === PINCABOS MODULAR ROUTES START ===
import pincabos_webapp_audio as pco_audio_routes
import pincabos_webapp_inputs as pco_inputs_routes
import pincabos_webapp_firstrun as pco_firstrun_routes
import pincabos_webapp_dev_admin as pco_dev_admin_routes
import pincabos_webapp_exports as pco_exports_routes
import pincabos_backupcfg as pco_backupcfg_routes
# === PINCABOS MODULAR ROUTES END ===
from pincabos_webapp_import_metadata import pincabos_write_imported_table_metadata

# === PINCABOS WEBAPP CORE CLEAN IMPORT START ===
from pincabos_webapp_core import (
    esc,
    run_cmd,
    shlex_quote,
    service_status,
    pincabos_meta,
    pincabos_backup_config_file,
    pincabos_write_json_with_meta,
    get_ip,
    pincabos_get_vpinfe_paths_for_tools,
    PCO_PATHS,
    PCO_SERVICES,
    pco_path,
    pco_script,
    pco_sudo_script_cmd,
    pco_systemctl_cmd,
    pco_service,
    pco_service_status,
    pco_vpinfe_service_name,
    pco_frontend_compat_service_name,
    pco_path_text,
    pco_script_text,
    pco_vpx_kill_pattern,
    pco_vpx_version_command,
    pco_vpinfe_version_command,
    pco_launch_webapp_screen_command,
    pco_smb_mount_helper_command,
    pincabos_vpx_executable_path,
    pincabos_vpx_tables_dir,
    pincabos_vpx_ini_path,
    pincabos_vpinfe_ini_path,
    pincabos_vpinfe_config_ini_path,
    PINCABOS_VPX_EXECUTABLE,
    PINCABOS_VPX_TABLES_DIR,
    PINCABOS_VPX_INI,
    PINCABOS_VPINFE_ROOT,
    PINCABOS_VPINFE_CURRENT,
    PINCABOS_VPINFE_INI,
    PINCABOS_VPINFE_CONFIG_INI,
    PINCABOS_VPINFE_TEMPLATE_INI,
    PINCABOS_VPINFE_BIN,
)
# === PINCABOS WEBAPP CORE CLEAN IMPORT END ===
# === PINCABOS WEBAPP ADMIN MODULE IMPORT START ===
from pincabos_webapp_admin import (
    pco_admin_cmd_for_script,
    pco_admin_cmd_for_systemctl,
    pco_admin_shell_join,
    pco_admin_run_capture,
    pco_admin_now_stamp,
    pco_admin_tail_text,
    pco_admin_existing_scripts,
    pco_admin_iframe_body,
)
# === PINCABOS WEBAPP ADMIN MODULE IMPORT END ===

# === PINCABOS OFFICIAL VPX PATHS START ===
# Stage2 clean:
# Les chemins VPX/VPinball sont centralises dans pincabos_webapp_core.py.
# VPX officiel: pco_path('vpx_dir')
# Wrapper officiel: pco_path('vpx_wrapper')
# Tables officielles: /home/pinball/Tables
PINNED_VPX_EXECUTABLE = PINCABOS_VPX_EXECUTABLE
PINNED_VPX_TABLES_DIR = PINCABOS_VPX_TABLES_DIR
PINNED_VPX_INI = PINCABOS_VPX_INI
# === PINCABOS OFFICIAL VPX PATHS END ===

# === PINCABOS OFFICIAL VPINFE PATHS START ===
# Stage2 clean:
# Les chemins VPinFE sont centralises dans pincabos_webapp_core.py.
# VPinFE current: pco_path('vpinfe_current')
# Runtime ini: chemin runtime officiel résolu depuis version.json / manifest PinCabOS
# Config ini: /home/pinball/.config/vpinfe/vpinfe.ini
# Template ini: /opt/pincabos/essentials/VPinFEfiles/vpinfe.ini
# === PINCABOS OFFICIAL VPINFE PATHS END ===


from datetime import datetime
import socket
import subprocess
import psutil
import json
import time
import os
import html
import re
import hashlib

def pincabos_force_standard_table_name(name):
    """
    Force le format:
    Table Name (Manufacturer Year)

    Exemples:
    The Leprechaun King_Original_2019_ -> The Leprechaun King (Original 2019)
    Ramones _Original 2021_           -> Ramones (Original 2021)
    Ramones_Original_2021_            -> Ramones (Original 2021)
    """
    name = str(name or "").strip()

    name = name.replace("\\", " ").replace("/", " ")
    name = re.sub(r'[:"*?<>|]+', " ", name)
    name = re.sub(r"\s+", " ", name).strip()

    # Cas: Table_Manufacturer_Year_
    m = re.match(r"^(?P<table>.+?)_(?P<mfg>[^_()]+)_(?P<year>\d{4})_$", name)
    if m:
        table = re.sub(r"[_\s]+", " ", m.group("table")).strip()
        mfg = re.sub(r"[_\s]+", " ", m.group("mfg")).strip()
        year = m.group("year").strip()
        return f"{table} ({mfg} {year})"

    # Cas: Table _Manufacturer Year_
    m = re.match(r"^(?P<table>.+?)\s+_(?P<mfg>[^_()]+?)\s+(?P<year>\d{4})_$", name)
    if m:
        table = re.sub(r"[_\s]+", " ", m.group("table")).strip()
        mfg = re.sub(r"[_\s]+", " ", m.group("mfg")).strip()
        year = m.group("year").strip()
        return f"{table} ({mfg} {year})"

    # Cas: Table Manufacturer 2021, seulement si pas déjà avec parenthèses
    if "(" not in name and ")" not in name:
        m = re.match(r"^(?P<table>.+?)\s+(?P<mfg>Original|Williams|Stern|Bally|Gottlieb|Data East|Sega|HauntFreaks|MOD)\s+(?P<year>\d{4})$", name, re.I)
        if m:
            table = re.sub(r"[_\s]+", " ", m.group("table")).strip()
            mfg = re.sub(r"[_\s]+", " ", m.group("mfg")).strip()
            year = m.group("year").strip()
            return f"{table} ({mfg} {year})"

    return name or "Imported Table"


# PINCABOS_WEBAPP_SCREEN_STATE_V3_BEGIN
PCO_WEBAPP_SCREEN_STATE_FILE = Path(
    "/opt/pincabos/config/webapp-screen-autostart.conf"
)


def pincabos_webapp_screen_state():
    """
    État mémorisé des écrans WebApp demandés par PinCabOS.
    Un bouton glow seulement lorsque sa valeur vaut 1.
    """
    state = {"playfield": "0", "backglass": "0"}

    try:
        if not PCO_WEBAPP_SCREEN_STATE_FILE.exists():
            return state

        for line in PCO_WEBAPP_SCREEN_STATE_FILE.read_text(
            errors="replace"
        ).splitlines():
            line = line.strip()

            if not line or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip().upper()
            value = "1" if value.strip() == "1" else "0"

            if key == "PLAYFIELD":
                state["playfield"] = value
            elif key == "BACKGLASS":
                state["backglass"] = value

    except Exception:
        return {"playfield": "0", "backglass": "0"}

    return state


def webapp_screen_toggle_html():
    state = pincabos_webapp_screen_state()

    pf_class = (
        "screen-toggle-on"
        if state["playfield"] == "1"
        else "screen-toggle-off"
    )
    bg_class = (
        "screen-toggle-on"
        if state["backglass"] == "1"
        else "screen-toggle-off"
    )

    pf_pressed = "true" if state["playfield"] == "1" else "false"
    bg_pressed = "true" if state["backglass"] == "1" else "false"

    return f"""
    <form action="/toggle-webapp-screen" method="post" class="nav-inline-form">
      <input type="hidden" name="screen" value="playfield">
      <button
        class="button nav-action screen-toggle-btn {pf_class}"
        type="submit"
        aria-pressed="{pf_pressed}"
        title="Afficher ou retirer PinCabOS du Playfield">
        PlayField
      </button>
    </form>

    <form action="/toggle-webapp-screen" method="post" class="nav-inline-form">
      <input type="hidden" name="screen" value="backglass">
      <button
        class="button nav-action screen-toggle-btn {bg_class}"
        type="submit"
        aria-pressed="{bg_pressed}"
        title="Afficher ou retirer PinCabOS du Backglass">
        BackGlass
      </button>
    </form>
"""
# PINCABOS_WEBAPP_SCREEN_STATE_V3_END
# PinCabOS config write audit helpers
def pincabos_modified_comment(function_name):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"; Modifié {stamp} par PinCabOS fonction({function_name})"


def pincabos_modified_hash_comment(function_name):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"# Modifié {stamp} par PinCabOS fonction({function_name})"


def pincabos_read_ini_lines(path):
    path = Path(path)
    if path.exists():
        return path.read_text(errors="replace").splitlines()
    return []


def pincabos_write_ini_lines(path, lines):
    # PINCABOS_INI_UNIQUE_V1 : ecriture atomique de l ecrivain unique (mode et proprietaire conserves)
    pincabos_ini.ecrire_texte(path, "\n".join(lines).rstrip() + "\n")


def pincabos_find_ini_section(lines, section):
    # PINCABOS_INI_UNIQUE_V1 : bornes de la section par l ecrivain unique
    return pincabos_ini.Ini("\n".join(lines)).bornes(section)


def pincabos_set_ini_key_with_comment(lines, section, key, value, function_name):
    # PINCABOS_INI_UNIQUE_V1 : la cle sous son commentaire date, un seul commentaire
    ini = pincabos_ini.Ini("\n".join(lines))
    ini.poser(section, key, value, pincabos_modified_comment(function_name))
    return ini.lignes


def pincabos_set_ini_section_with_comment(lines, section, values, function_name):
    # PINCABOS_INI_UNIQUE_V1 : chaque cle sous son commentaire date
    ini = pincabos_ini.Ini("\n".join(lines))
    ini.poser_section(section, dict(values), pincabos_modified_comment(function_name))
    return ini.lignes


def pincabos_webapp_secret_key():
    """Load a persistent session secret without falling back to a public value."""
    configured = os.environ.get("PINCABOS_SECRET_KEY", "").strip()
    if configured:
        if len(configured) < 32:
            raise RuntimeError("PINCABOS_SECRET_KEY doit contenir au moins 32 caractères.")
        return configured

    secret_path = Path("/opt/pincabos/config/webapp-secret.key")
    try:
        if secret_path.is_file():
            saved = secret_path.read_text(encoding="utf-8").strip()
            if len(saved) >= 32:
                return saved
            raise RuntimeError(f"Secret WebApp invalide: {secret_path}")

        import secrets
        secret_path.parent.mkdir(parents=True, exist_ok=True)
        generated = secrets.token_urlsafe(48)
        try:
            fd = os.open(str(secret_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            saved = secret_path.read_text(encoding="utf-8").strip()
            if len(saved) >= 32:
                return saved
            raise RuntimeError(f"Secret WebApp invalide: {secret_path}")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(generated + "\n")
        try:
            os.chmod(secret_path, 0o600)
        except OSError:
            pass
        return generated
    except OSError as exc:
        raise RuntimeError("Impossible de charger ou créer le secret de session PinCabOS.") from exc


# PINCABOS_STOCKAGE_LIBELLE_V1
app = Flask(__name__)
# === PINCABOS DASHBOARD V7 CONTROL ROUTES ===
pco_register_dashboard_control_routes(app)
# === PINCABOS DASHBOARD V7 CONTROL ROUTES END ===
app.register_blueprint(screen_bp)
app.register_blueprint(internal_disk_bp)

# PINCABOS_PUPPACK_PAGE_V1
# Page de choix de la disposition d'ecrans d'un PuP-Pack. Aucun privilege :
# les fichiers du pack appartiennent deja a pinball.
try:
    from puppack_options import puppack_bp as _pco_puppack_bp
    app.register_blueprint(_pco_puppack_bp)
except Exception as _pco_puppack_e:
    print("WARN: PinCabOS PuP-Pack module load failed:", _pco_puppack_e)
app.secret_key = pincabos_webapp_secret_key()
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
# PINCABOS_WEBAPP_SECURITY_V1_REGISTER
from pincabos_webapp_security import install_pincabos_security
install_pincabos_security(app)
# PINCABOS_WEBAPP_SECURITY_V1_REGISTER_END
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024 * 1024

BASE = Path("/opt/pincabos")
LOG_DIR = BASE / "logs" / "jobs"
JOB_DIR = LOG_DIR
LOG_DIR.mkdir(parents=True, exist_ok=True)
JOB_DIR.mkdir(parents=True, exist_ok=True)


def latest_job_file():
    jobs = sorted(JOB_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return jobs[0] if jobs else None

def read_job(job_file):
    if not job_file or not job_file.exists():
        return None
    try:
        return json.loads(job_file.read_text())
    except Exception:
        return None

def get_job_status():
    job_file = latest_job_file()
    job = read_job(job_file)

    if not job:
        return {
            "has_job": False,
            "status": "idle",
            "target": "",
            "progress": 0,
            "message": "Aucune mise à jour lancée.",
            "log": "",
            "log_name": "aucun"
        }

    log_file = Path(job.get("log_file", ""))
    exit_file = Path(job.get("exit_file", ""))

    log_text = ""
    if log_file.exists():
        try:
            log_text = log_file.read_text(errors="replace")[-20000:]
        except Exception as e:
            log_text = f"Erreur lecture log: {e}"

    started = float(job.get("started", time.time()))
    elapsed = max(0, time.time() - started)

    if exit_file.exists():
        try:
            code = int(exit_file.read_text().strip())
        except Exception:
            code = 999

        if code == 0:
            status = "complete"
            progress = 100
            message = "Tâche terminée avec succès."
        else:
            status = "error"
            progress = 100
            message = f"Tâche terminée avec erreur. Code: {code}"
    else:
        status = "running"
        progress = min(95, int(8 + elapsed * 2))
        message = "Tâche en cours..."

    payload = {
        "has_job": True,
        "status": status,
        "target": job.get("target", ""),
        "progress": progress,
        "message": message,
        "log": log_text,
        "log_name": log_file.name if log_file.exists() else "log en attente"
    }
    return payload


def pincabos_version():
    version_file = Path("/opt/pincabos/config/version.json")
    default = {
        "name": "PinCabOS",
        "version": "Development",
        "build": "dev",
        "author": "Karots Sugarpie",
    }

    try:
        if version_file.exists():
            data = json.loads(version_file.read_text())
            default.update(data)
    except Exception:
        pass

    return default


def safe_file_text(path, fallback=""):
    try:
        f = Path(path)
        if f.exists():
            return f.read_text(errors="replace")
    except Exception as e:
        return f"Erreur lecture {path}: {e}"
    return fallback
def pincabos_support_footer_html():
    ver = pincabos_version() if "pincabos_version" in globals() else {}
    qr_name = "pcbo_pay_qr_bbb5611b723f953dc3fad1e42e7dbd66fe9fa8d53de4293c.png"

    def v(key, fallback=""):
        try:
            return esc(str(ver.get(key, fallback) or fallback))
        except Exception:
            return esc(str(fallback))

    try:
        supporters_html = pincabos_footer_supporters_inline_html()
    except Exception:
        supporters_html = (
            '<section id="pincabos-footer-supporters-inline-v14" '
            'class="pincabos-footer-supporters-inline-v14">'
            '<h2>Testeurs / Soutiens fondateurs</h2>'
            '<p>Merci aux personnes qui soutiennent PinCabOS.</p>'
            '</section>'
        )

    return f"""
<!-- PINCABOS_FOOTER_LAYOUT_V14_1 -->
<div class="footer pincabos-support-footer-safe pco-footer-layout-v14"
     id="pincabos-support-footer-static">

  <!-- PINCABOS_FOOTER_QR_DIRECT_LEFT_V11 -->
  <div class="pincabos-support-qr-safe pco-footer-qr-direct-left-v11">
      <h3 class="pincabos-support-title-left-v3">Soutenir PinCabOS</h3>
    <img src="/static/pincabos-assets/{esc(qr_name)}" alt="QR Code PayPal PinCabOS">
    <div class="pincabos-support-qr-label-safe">QR Code PayPal PinCabOS</div>
  </div>


  <div class="pco-footer-main-v14">
    <div class="pincabos-release-notes-safe">
      <h2>Notes de version</h2>
      <div class="pincabos-release-grid-safe">
        <p><strong>Nom :</strong> {v("name", "PinCabOS")}</p>
        <p><strong>Version :</strong> {v("version", "Development")}</p>
        <p><strong>Build :</strong> {v("build", "dev")}</p>
        <p><strong>Canal :</strong> {v("channel", ver.get("update_channel", ""))}</p>
        <p><strong>Codename :</strong> {v("codename", "")}</p>
        <p><strong>Auteur :</strong> {v("author", "Karots Sugarpie")}</p>
        <p><strong>Site :</strong> pincabos.cc</p>
      </div>
    </div>

    <div class="pincabos-support-text-safe">
<p>Si vous aimez PinCabOS,<br>vous pouvez me le montrer en offrant ce que vous voulez.<br>Merci pour votre soutien.</p>
      <div class="pincabos-paypal-form-safe">
        <form action="https://www.paypal.com/ncp/payment/SE79XX45T2NBG" method="post" target="_blank">
          <input class="pp-SE79XX45T2NBG-safe" type="submit" value="Faire un don">
          <img class="pincabos-paypal-cards-safe" src="https://www.paypalobjects.com/images/Debit_Credit_APM.svg" alt="cards">
          <section class="pincabos-paypal-powered-safe">Optimisé par <img src="https://www.paypalobjects.com/paypal-ui/logos/svg/paypal-wordmark-color.svg" alt="paypal"></section>
        </form>
      </div>
    </div>
  </div>

  <aside class="pco-footer-right-v14" aria-label="Soutien et contributeurs">
    {supporters_html}
  </aside>
</div>
"""

def page(title, body):
    ip = get_ip()
    logo_html = ""
    if Path("/opt/pincabos/web/static/pincabos-logo.png").exists():
        logo_html = '<img src="/static/pincabos-logo.png" class="logo" alt="PinCabOS Logo">'

    return f"""<!doctype html>
<html>
<head>
  <title>PinCabOS - {esc(title)}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {{
      margin: 0;
      font-family: Arial, sans-serif;
      background:
        linear-gradient(rgba(0,0,0,0.72), rgba(0,0,0,0.72)),
        url('/static/pincabos-logo.png') center center / min(70vw, 760px) auto no-repeat fixed,
        #000000;
      color: #fff;
      padding: 30px;
    }}
    .top {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 20px;
      margin-bottom: 25px;
      background: rgba(29, 11, 46, 0.65);
      border: 1px solid rgba(255,122,0,0.65);
      border-radius: var(--pco-appearance-card-radius, 18px);
      padding: 14px 18px;
      box-shadow: 0 0 25px rgba(255, 122, 0, 0.20);
    }}
    .brand-left {{
      display: flex;
      align-items: center;
      gap: 16px;
      min-width: 0;
    }}
    .logo {{
      max-width: 190px;
      width: 190px;
      height: auto;
      filter: drop-shadow(0 0 20px rgba(255,122,0,0.6));
      flex-shrink: 0;
    }}
    .brand-title {{
      color: var(--pco-appearance-accent, #ffb000);
      font-size: 20px;
      font-weight: bold;
      text-shadow: 0 0 15px rgba(255,122,0,0.75);
      white-space: normal;
      line-height: 1.25;
    }}
    .brand-subtitle {{
      color: var(--pco-appearance-muted-text, #d8b8ff);
      font-size: 15px;
      font-weight: normal;
      margin-top: 4px;
      text-shadow: 0 0 12px rgba(216,184,255,0.55);
    }}
    h1 {{
      display: none;
    }}
    .subtitle {{
      display: none;
    }}
    .nav {{
      text-align: right;
      margin-bottom: 0;
      flex-shrink: 0;
    }}
    @media (max-width: 850px) {{
      .top {{
        flex-direction: column;
        align-items: center;
        text-align: center;
      }}
      .brand-left {{
        flex-direction: column;
      }}
      .nav {{
        text-align: center;
      }}
    }}
    .nav a, .button {{
      display: inline-block;
      background: var(--pco-appearance-button-bg, #ff7a00);
      color: var(--pco-appearance-button-text, #160020);
      padding: 10px 15px;
      border-radius: var(--pco-appearance-button-radius, 10px);
      text-decoration: none;
      font-weight: bold;
      margin: 5px;
      border: none;
      cursor: pointer;
    }}
    .secondary {{
      background: var(--pco-appearance-secondary-bg, #5f2a91) !important;
      color: var(--pco-appearance-secondary-text, white) !important;
      border: 1px solid var(--pco-appearance-accent2, #ff7a00) !important;
    }}
    .nav a.active {{
      background: var(--pco-appearance-nav-active-bg, #ff7a00) !important;
      color: var(--pco-appearance-nav-active-text, #160020) !important;
      border: 1px solid var(--pco-appearance-accent, #ffb000) !important;
      box-shadow: 0 0 18px rgba(255,122,0,0.8);
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 20px;
    }}
    .card {{
      background: var(--pco-appearance-card-bg, rgba(29, 11, 46, 0.76));
      border: 1px solid var(--pco-appearance-card-border, #ff7a00);
      border-radius: var(--pco-appearance-card-radius, 18px);
      padding: 22px;
      box-shadow: var(--pco-appearance-card-shadow, 0 0 25px rgba(255, 122, 0, 0.25));
    }}
    .card h2 {{
      margin-top: 0;
      color: var(--pco-appearance-accent, #ffb000);
    }}
    .ok {{ color: #00ff99; font-weight: bold; }}
    .bad {{ color: #ff5555; font-weight: bold; }}
    .warn {{ color: var(--pco-appearance-accent, #ffb000); font-weight: bold; }}
    code {{
      background: #000;
      color: var(--pco-appearance-accent, #ffb000);
      padding: 4px 8px;
      border-radius: 6px;
      display: inline-block;
      margin: 2px 0;
    }}
    pre {{
      white-space: pre-wrap;
      background: var(--pco-appearance-input-bg, #050007);
      color: var(--pco-appearance-input-text, #eee);
      padding: 15px;
      border-radius: 12px;
      border: 1px solid var(--pco-appearance-purple, #5f2a91);
      height: 520px;
      overflow-y: scroll;
      font-size: 13px;
    }}
    .progress-wrap {{
      background: var(--pco-appearance-input-bg, #050007);
      border: 1px solid var(--pco-appearance-card-border, #ff7a00);
      border-radius: 14px;
      overflow: hidden;
      height: 30px;
      margin: 15px 0;
      box-shadow: 0 0 15px rgba(255,122,0,0.4);
    }}
    .progress-bar {{
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, #ff7a00, #ff00cc, #00eaff);
      color: #000;
      font-weight: bold;
      text-align: center;
      line-height: 30px;
      transition: width 0.5s ease;
    }}
    .running {{
      animation: glow 1.2s infinite alternate;
    }}
    @keyframes glow {{
      from {{ filter: brightness(1); }}
      to {{ filter: brightness(1.5); }}
    }}
    .footer {{
      margin-top: 30px;
      color: var(--pco-appearance-accent, #ffb000);
      font-size: 14px;
      opacity: 0.9;
      text-align: center;
    }}

    .nav-tools form {{
      display: inline-flex;
      gap: 6px;
      align-items: center;
      margin: 0;
    }}

    .nav-tools select {{
      padding: 6px;
      border-radius: 8px;
      border: 1px solid var(--pco-appearance-card-border, #ff7a00);
      background: #160020;
      color: #fff;
    }}

    .pincabos-nav a,
    .pincabos-nav button {{
      min-height: 38px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      line-height: 1;
    }}


    .pincabos-nav {{
      margin: 18px auto 0 auto;
      max-width: 1220px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}

    .nav-row {{
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      align-items: center;
      gap: 8px;
    }}

    .nav-pages {{
      padding: 10px;
      border-radius: var(--pco-appearance-card-radius, 18px);
      background: rgba(12, 0, 22, 0.58);
      border: 1px solid rgba(255, 122, 0, 0.25);
      box-shadow: 0 0 22px rgba(95, 42, 145, 0.22);
    }}

    .nav-tools-clean {{
      padding: 10px;
      border-radius: var(--pco-appearance-card-radius, 18px);
      background: rgba(255, 122, 0, 0.07);
      border: 1px solid rgba(95, 42, 145, 0.45);
      box-shadow: inset 0 0 18px rgba(0, 0, 0, 0.18);
    }}

    .nav-inline-form {{
      margin: 0;
      display: inline-flex;
      align-items: center;
    }}

    .nav-label {{
      color: var(--pco-appearance-accent, #ffb000);
      font-weight: 800;
      padding: 0 4px;
      text-shadow: 0 0 10px rgba(255, 122, 0, 0.45);
    }}

    .nav-action {{
      white-space: nowrap;
    }}

    .pincabos-nav a,
    .pincabos-nav button {{
      min-height: 38px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      line-height: 1;
    }}


     .top-language-widget {{
      position: absolute;
      top: 18px;
      right: 22px;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: flex-end;
      gap: 8px;
      width: min(330px, calc(100vw - 44px));
      padding: 8px 10px;
      border-radius: 14px;
      background: rgba(10, 0, 20, 0.96);
      border: 1px solid rgba(255, 122, 0, 0.45);
      box-shadow: 0 0 18px rgba(255, 122, 0, 0.20);
      z-index: 999;
    }}

    /* PINCABOS_LIVE_STATUS_BODY_ROOT_V10 */
    /* The status host belongs directly under <body>, not inside the navigation.
       This avoids transformed/stacked parent containers and anchors the compact
       card directly below Language at the far right. */
    .pco-impexp-live-menu-row {{
      display:none !important;
    }}
    #pco-impexp-live-overlay-root {{
      display:none;
      position:fixed !important;
      z-index:2147483000 !important;
      top:78px !important;
      right:18px !important;
      width:min(440px, calc(100vw - 36px)) !important;
      margin:0 !important;
      padding:0 !important;
      background:transparent !important;
      border:0 !important;
      box-shadow:none !important;
      pointer-events:none !important;
    }}
    #pco-impexp-live-overlay-root.is-active {{
      display:block !important;
    }}
    #pco-impexp-live-overlay-root .pco-impexp-menu-status {{
      display:grid !important;
      grid-template-columns:minmax(0,1fr) auto;
      grid-template-areas:
        "title pct"
        "current counter"
        "track track";
      gap:4px 12px;
      align-items:center;
      width:100% !important;
      margin:0 !important;
      padding:11px 13px !important;
      min-height:0 !important;
      border:1px solid rgba(255,132,20,.58) !important;
      border-radius:16px !important;
      background:linear-gradient(180deg,rgba(132,61,10,.98),rgba(101,42,7,.98)) !important;
      box-shadow:0 10px 22px rgba(0,0,0,.38) !important;
      color:#fff;
      text-align:left;
      pointer-events:auto !important;
    }}
    #pco-impexp-live-overlay-root .pcos-bxp6-titleline,
    #pco-impexp-live-overlay-root .pcos-bip-global-head {{
      grid-area:title;
      display:flex;
      align-items:center;
      gap:7px;
      min-width:0;
    }}
    #pco-impexp-live-overlay-root .pcos-bxp6-pct,
    #pco-impexp-live-overlay-root .pcos-bip-global-pct {{
      grid-area:pct;
      justify-self:end;
      font-size:1.05rem;
      font-weight:900;
      line-height:1;
    }}
    #pco-impexp-live-overlay-root .pcos-bxp6-title,
    #pco-impexp-live-overlay-root .pcos-bip-global-title {{
      font-size:.88rem;
      font-weight:900;
      letter-spacing:.03em;
      text-transform:uppercase;
    }}
    #pco-impexp-live-overlay-root .pcos-bxp6-current,
    #pco-impexp-live-overlay-root .pcos-bip-global-current {{
      grid-area:current;
      display:block;
      min-width:0;
      margin:0;
      overflow:hidden;
      white-space:nowrap;
      text-overflow:ellipsis;
      font-size:.84rem;
      font-weight:700;
      line-height:1.2;
    }}
    #pco-impexp-live-overlay-root .pcos-bxp6-counter,
    #pco-impexp-live-overlay-root .pcos-bip-global-count {{
      grid-area:counter;
      display:block;
      justify-self:end;
      margin:0;
      white-space:nowrap;
      font-size:.77rem;
      font-weight:700;
      opacity:.95;
    }}
    #pco-impexp-live-overlay-root .pcos-bxp6-track,
    #pco-impexp-live-overlay-root .pcos-bip-global-track {{
      grid-area:track;
      display:block;
      width:100%;
      height:5px;
      margin:2px 0 0 !important;
      border-radius:999px;
      overflow:hidden;
    }}

    /* PINCABOS_LIVE_STOP_BUTTON_V11 */
    #pco-impexp-live-overlay-root .pcos-bxp6-actions,
    #pco-impexp-live-overlay-root .pcos-bip-global-actions {{
      grid-area:pct;
      display:flex;
      align-items:center;
      justify-self:end;
      gap:8px;
    }}
    #pco-impexp-live-overlay-root .pcos-live-stop {{
      border:1px solid rgba(255,216,160,.8);
      border-radius:8px;
      padding:4px 8px;
      background:rgba(53,14,7,.72);
      color:#fff3e1;
      font:inherit;
      font-size:.72rem;
      font-weight:900;
      line-height:1;
      cursor:pointer;
    }}
    #pco-impexp-live-overlay-root .pcos-live-stop:hover:not(:disabled) {{
      filter:brightness(1.18);
    }}
    #pco-impexp-live-overlay-root .pcos-live-stop:disabled {{
      opacity:.58;
      cursor:wait;
    }}

    @media (max-width:700px) {{
      #pco-impexp-live-overlay-root {{
        top:66px !important;
        right:10px !important;
        width:calc(100vw - 20px) !important;
      }}
    }}
    #pco-impexp-live-menu-slot .pco-impexp-menu-status {{
      width:100%;
    }}

    .top-language-widget span {{
      color: var(--pco-appearance-accent, #ffb000);
      font-weight: 800;
      font-size: 13px;
      white-space: nowrap;
      text-shadow: 0 0 10px rgba(255,122,0,0.45);
    }}

    .top-language-widget select {{
      padding: 7px 10px;
      border-radius: var(--pco-appearance-button-radius, 10px);
      border: 1px solid var(--pco-appearance-card-border, #ff7a00);
      background: #160020;
      color: #fff;
      font-weight: 700;
      outline: none;
    }}

    #google_translate_element {{
      display: none;
    }}

    .goog-te-banner-frame.skiptranslate,
    iframe.goog-te-banner-frame {{
      display: none !important;
    }}

    body {{
      top: 0 !important;
    }}

    .goog-logo-link,
    .goog-te-gadget span {{
      display: none !important;
    }}

    .goog-te-gadget {{
      color: transparent !important;
      font-size: 0 !important;
    }}


    .import-progress-box {{
      display: none;
      margin-top: 14px;
      padding: 12px;
      border-radius: 14px;
      border: 1px solid rgba(255, 122, 0, 0.45);
      background: rgba(10, 0, 20, 0.72);
      box-shadow: 0 0 18px rgba(255, 122, 0, 0.18);
    }}

    .import-progress-label {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      color: var(--pco-appearance-accent, #ffb000);
      font-weight: 800;
      margin-bottom: 8px;
    }}

    .import-progress-track {{
      height: 18px;
      background: #160020;
      border: 1px solid var(--pco-appearance-purple, #5f2a91);
      border-radius: 999px;
      overflow: hidden;
    }}

    .import-progress-bar {{
      height: 100%;
      width: 0%;
      background: var(--pco-appearance-button-bg, #ff7a00);
      box-shadow: 0 0 16px rgba(255,122,0,0.85);
      transition: width 0.25s ease;
    }}

    .import-progress-note {{
      margin-top: 8px;
      font-size: 13px;
      color: #ddd;
    }}

    .import-spinner {{
      display: inline-block;
      width: 14px;
      height: 14px;
      border: 2px solid rgba(255,255,255,0.25);
      border-top-color: #ff7a00;
      border-radius: 50%;
      animation: pincabSpin 0.9s linear infinite;
      vertical-align: middle;
      margin-right: 6px;
    }}

    @keyframes pincabSpin {{
      to {{ transform: rotate(360deg); }}
    }}


.np-grid-safe{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
.np-panel-safe{{border:1px solid rgba(255,176,0,.25);border-radius:16px;padding:16px;background:rgba(0,0,0,.18)}}
.np-panel-safe h3{{margin-top:0;color:#ffb000}}
.nudge-scope-safe{{position:relative;width:240px;height:240px;margin:10px auto;border-radius:50%;border:2px solid rgba(255,176,0,.6);background:radial-gradient(circle,rgba(255,176,0,.12),rgba(0,0,0,.25))}}
.nudge-scope-safe:before,.nudge-scope-safe:after{{content:"";position:absolute;background:rgba(255,176,0,.35)}}
.nudge-scope-safe:before{{left:50%;top:0;width:1px;height:100%}}
.nudge-scope-safe:after{{top:50%;left:0;height:1px;width:100%}}
.nudge-dot-safe{{position:absolute;left:50%;top:50%;width:16px;height:16px;transform:translate(-50%,-50%);border-radius:50%;background:#ff2b2b;box-shadow:0 0 12px rgba(255,43,43,.9)}}
.plunger-track-safe{{position:relative;height:28px;margin:36px 8px;border-radius:999px;border:1px solid rgba(255,176,0,.45);background:rgba(0,0,0,.35)}}
.plunger-pointer-safe{{position:absolute;left:50%;top:-9px;width:10px;height:46px;transform:translateX(-50%);border-radius:8px;background:#ff2b2b;box-shadow:0 0 12px rgba(255,43,43,.9)}}
.np-fields-safe{{display:grid;grid-template-columns:repeat(2,minmax(160px,1fr));gap:10px}}
.np-fields-safe label{{display:flex;flex-direction:column;gap:5px;font-weight:700}}
.np-fields-safe .checkline{{flex-direction:row;align-items:center}}
.np-fields-safe input,.np-fields-safe select{{max-width:100%}}
@media(max-width:950px){{.np-grid-safe{{grid-template-columns:1fr}}}}


.np-grid-safe{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
.np-panel-safe{{border:1px solid rgba(255,176,0,.25);border-radius:16px;padding:16px;background:rgba(0,0,0,.18)}}
.np-panel-safe h3{{margin-top:0;color:#ffb000}}
.nudge-scope-safe{{position:relative;width:240px;height:240px;margin:10px auto;border-radius:50%;border:2px solid rgba(255,176,0,.6);background:radial-gradient(circle,rgba(255,176,0,.12),rgba(0,0,0,.25))}}
.nudge-scope-safe:before,.nudge-scope-safe:after{{content:"";position:absolute;background:rgba(255,176,0,.35)}}
.nudge-scope-safe:before{{left:50%;top:0;width:1px;height:100%}}
.nudge-scope-safe:after{{top:50%;left:0;height:1px;width:100%}}
.nudge-dot-safe{{position:absolute;left:50%;top:50%;width:16px;height:16px;transform:translate(-50%,-50%);border-radius:50%;background:#ff2b2b;box-shadow:0 0 12px rgba(255,43,43,.9)}}
.plunger-track-safe{{position:relative;height:28px;margin:36px 8px;border-radius:999px;border:1px solid rgba(255,176,0,.45);background:rgba(0,0,0,.35)}}
.plunger-pointer-safe{{position:absolute;left:50%;top:-9px;width:10px;height:46px;transform:translateX(-50%);border-radius:8px;background:#ff2b2b;box-shadow:0 0 12px rgba(255,43,43,.9)}}
.np-fields-safe{{display:grid;grid-template-columns:repeat(2,minmax(160px,1fr));gap:10px}}
.np-fields-safe label{{display:flex;flex-direction:column;gap:5px;font-weight:700}}
.np-fields-safe .checkline{{flex-direction:row;align-items:center}}
.np-fields-safe input,.np-fields-safe select{{max-width:100%}}
@media(max-width:950px){{.np-grid-safe{{grid-template-columns:1fr}}}}


/* PINCABOS-LOG-NEWLINES-START */
pre,
#job-log,
.firstrun-log {{
  white-space: pre-wrap !important;
  overflow-wrap: anywhere !important;
  word-break: break-word !important;
}}
/* PINCABOS-LOG-NEWLINES-END */

</style>
<script 
  src="https://www.paypal.com/sdk/js?client-id=BAA5atlZ6zhL2iAHU4cMNpDOLyPpnZ4tBNxVfg_ZowsRSbQM5voDWVamM3F_Rw_vmwtMFrLxcT2kbgohM0&components=hosted-buttons&disable-funding=venmo&currency=CAD">
</script>

<script src="/static/pincabos-i18n.js?v=20260705-single-loader-v3"></script>
<script src="/static/pincabos-quick-access-i18n-v1.js?v=20260705-v1" defer></script>
<link rel="stylesheet" href="/static/pincabos-dashboard-compact.css">
<link rel="stylesheet" href="/static/pincabos-branding.css?v=branding">
<link rel="stylesheet" href="/static/pincabos-header-fix.css?v=20260515232444">
<link rel="stylesheet" href="/static/pincabos-menu-pro-v1.css?v=menu-logo-direct-v7">
<link rel="stylesheet" href="/static/pincabos-global-compact.css">
<link rel="stylesheet" href="/static/pincabos-footer.css">
<link rel="stylesheet" href="/static/pincabos-support-footer.css">
<link rel="stylesheet" href="/static/pincabos-footer-layout-v14.css?v=footer-layout-repair-v4">
<link rel="stylesheet" href="/static/pincabos-services-taskmanager.css">
<link rel="stylesheet" href="/static/pincabos-menu-icons.css">
<link rel="stylesheet" href="/static/pincabos-fulldmd-compact.css?v=20260515164207">
  <link rel="stylesheet" href="/static/pincabos-webapp-screen-toggle.css?v=20260705-glow-v3">
<link rel="stylesheet" href="/static/pincabos-appearance-vars.css?v=appearance">
<!-- PINCABOS_THEME_GLOBAL_LINK_V2 -->
<link rel="stylesheet" href="/static/pincabos-theme-global.css?v=20260701-theme-v2">

<link rel="icon" type="image/png" href="/static/branding/favicon.png?v=branding">
  <link rel="stylesheet" href="/static/pincabos-commander-purple-buttons-v1.css?v=1">
  <link rel="stylesheet" href="/static/pincabos-system-message-tray-v1.css?v=tray-tiny-text-x-v2-20260713-184235">
  <link rel="stylesheet" href="/static/pincabos-single-batch-status-v1.css?v=single-status-v1-20260715-170001"><!-- PINCABOS_SINGLE_BATCH_STATUS_OWNER_V1 -->
  <link rel="stylesheet" href="/static/pincabos-audio-widget-final-v1.css?v=1">
</head>
<body>

<div class="top-language-widget">
  <div id="google_translate_element"></div>
  <span>Langue :</span>
  <select id="pincabos_language_select" onchange="setPinCabOSLanguage(this.value)">
              <option value="fr">Français</option>
              <option value="en">English</option>
              <option value="es">Español</option>
              <option value="it">Italiano</option>
              <option value="de">Deutsch</option>
              <option value="nl">Nederlands</option>
            </select>
</div>

  <div class="top">
    <div class="brand-left">
      {logo_html}
      <div class="brand-title">
<div class="brand-subtitle"></div>
      </div>
    </div>

    <div class="nav">
    

<nav class="pincabos-nav">
  <!-- PINCABOS_MENU_LOGO_RAIL_V1 -->
  <div class="pco-menu-logo-rail" role="img" aria-label="PinCabOS">
    <img src="/static/pincabos-assets/PCOSMenuLogo.png?v=menu-logo-rail-v1"
         alt="PinCabOS">
  </div>
  <div class="nav-row nav-pages">
<a href="/" class="{ 'active' if title == 'Tableau de bord' else 'secondary' }"><span class="menu-ico">📊</span> Tableau de bord</a> 


    <a href="/inputs" class="{ 'active' if title == 'Inputs' else 'secondary' }"><span class="menu-ico">🎛️</span> Inputs</a>

<a href="/tools" class="{ 'active' if title == 'Outils' else 'secondary' }"><span class="menu-ico">🧰</span> Outils PinCabOS</a>


    <a href="/pincabos-link" class="{ 'active' if title == 'PinCabOS Link' else 'secondary' }"><span class="menu-ico">&#128279;</span> PinCabOS Link</a>
    <a href="/about" class="{ 'active' if title == 'À propos' else 'secondary' }"><span class="menu-ico">ℹ️</span> À propos</a>
    <span class="pco-menu-tools">
      <button type="button" id="pco-menu-pin-btn" class="pco-menu-tool-btn pco-menu-pin-btn" title="Épingler le menu" aria-label="Épingler le menu" onclick="return window.pcoMenuTogglePin(event);">📌</button>
      <button type="button" id="pco-menu-close-btn" class="pco-menu-tool-btn pco-menu-close-btn" title="Fermer la page" aria-label="Fermer la page" onclick="return window.pcoMenuClosePage(event);">X</button>
    </span>
    <link rel="stylesheet" href="/static/pincabos-menu-tools.css?v=20260615131347">
    <script src="/static/pincabos-menu-tools.js?v=20260615131347"></script>
 </div>

  <div class="nav-row nav-tools-clean">
    <span class="nav-vpinfe-vps-group" style="display:inline-flex;align-items:center;gap:8px;flex:0 0 auto;">
      <!-- PINCABOS_QUICK_ACCESS_I18N_V1 -->
      <span class="pco-quick-access-label" data-i18n="nav.quick_access" data-pco-i18n-quick-access="1">Accès rapides</span>
      <a href="http://{ip}:8001" target="_blank" class="secondary nav-action">Ouvrir VPinFE</a>
      <a href="https://virtualpinballspreadsheet.github.io/" target="_blank" rel="noopener noreferrer" class="secondary nav-action">Ouvrir VPS</a>
      <!-- PinCabOS topbar tools copy buttons -->
      <a class="button pco-topbar-tool-copy" href="/tools/commander">PinCab Explorer</a>
      <a class="button pco-topbar-tool-copy" href="/console">PinCab Console</a>
      <!-- /PinCabOS topbar tools copy buttons -->
    </span>

    <span class="nav-label" style="margin-left:auto;">Afficher PinCabOS WebApp sur :</span>

    {webapp_screen_toggle_html()}
  </div>

  <div class="nav-row pco-impexp-live-menu-row" aria-live="polite">
    <div id="pco-impexp-live-menu-slot"></div>
  </div>
</nav>
  </div>

  </div>
  </div>

  {body}

  
{pincabos_support_footer_html()}

<script src="/static/pincabos-progress-reset.js"></script>
<script src="/static/pincabos-dashboard-compact.js"></script>
<script src="/static/pincabos-explorer-same-tab-v2.js?v=20260716-vps-new-tab-v2"></script>
<script src="/static/pincabos-header-final.js?v=20260515232444"></script>
<!-- footer now rendered server-side; JS injection disabled -->
<script src="/static/pincabos-fulldmd-compact.js"></script>
<script src="/static/pincabos-fulldmd-layout-no-global-dmd-v1.js?v=20260802-101209"></script>

  <div id="firstrun-popup" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.72);z-index:999999;align-items:center;justify-content:center;">
    <div style="max-width:620px;width:92%;border:1px solid rgba(255,176,0,.55);border-radius:20px;padding:22px;background:rgba(18,0,30,.96);box-shadow:0 0 35px rgba(255,122,0,.35);">
      <div style="text-align:center;margin-bottom:14px;">
        <img src="/static/branding/firstrun-welcome.png?v=welcome"
             alt="Bienvenue PinCabOS"
             style="max-width:260px;width:70%;height:auto;border-radius:14px;box-shadow:0 0 22px rgba(255,122,0,.28);">
      </div>
      <h2>🚀 Bienvenue dans PinCabOS</h2>
      <p>Avant d’utiliser PinCabOS, Jarvis recommande de compléter l’assistant Premier Démarrage.</p>
      <p>Checklist : accès WebApp réseau, GPU/pilotes, puis détection et assignation des écrans.</p>
      <p>
        <a class="button" href="/first-run">🚀 Démarrer l’assistant</a>
        <button class="button secondary" onclick="closeFirstRunPopup()">Plus tard</button>
      </p>
      <label>
        <input type="checkbox" id="firstrun-disable">
        Ne plus afficher automatiquement
      </label>
    </div>
  </div>

  <script>
  async function closeFirstRunPopup(){{
    var chk = document.getElementById("firstrun-disable");
    var disable = chk ? chk.checked : false;
    if(disable){{
      await fetch("/first-run/popup-disable", {{method:"POST"}});
    }}
    var p = document.getElementById("firstrun-popup");
    if(p) p.style.display = "none";
  }}

  window.addEventListener("load", function(){{
    // PINCABOS_FIRSTRUN_3STEP_COMPLETE_V3
    var shouldShow = "{'1' if (title in ['Dashboard', 'Tableau de bord'] and firstrun_load_cfg().get('show_popup', True) and not pincabos_firstrun_is_complete()) else '0'}";
    if(shouldShow === "1"){{
      setTimeout(function(){{
        var p = document.getElementById("firstrun-popup");
        if(p) p.style.display = "flex";
      }}, 650);
    }}
  }});
  </script>

  <script defer src="/static/pincabos-system-message-tray-v1.js?v=menu-free-space-v4"></script>
  <script defer src="/static/pincabos-single-batch-status-v1.js?v=single-status-v1-20260715-170001"></script>
  <script defer src="/static/pincabos-audio-mute-icons-v1.js?v=2"></script>
</body>
</html>"""


# === FIRST RUN WIZARD - PINCABOS START ===
# Moved to modular route file by PinCabOS refactor (original lines 1123-1123).
# Tools hub routes are registered after the main page() layout helper is available.
# PINCABOS_IMPEXP_NATIVE_V1: native Import / Export Centers; no iframe and no response injection.
app.config["PINCABOS_IMPEXP_NATIVE_UI"] = True
register_tools_routes(app, page)
from pincabos_impexp import register_pincabos_impexp_routes
register_pincabos_impexp_routes(app, globals())

# Moved to modular route file by PinCabOS refactor (original lines 1127-1133).

# Moved to modular route file by PinCabOS refactor (original lines 1135-1136).

# Moved to modular route file by PinCabOS refactor (original lines 1138-1145).

# Moved to modular route file by PinCabOS refactor (original lines 1147-1178).

# Moved to modular route file by PinCabOS refactor (original lines 1180-1188).

# Moved to modular route file by PinCabOS refactor (original lines 1190-1207).

# Moved to modular route file by PinCabOS refactor (original lines 1209-1225).

# Moved to modular route file by PinCabOS refactor (original lines 1227-1256).

# Moved to modular route file by PinCabOS refactor (original lines 1258-1288).


# Moved to modular route file by PinCabOS refactor (original lines 1344-1753).


# Moved to modular route file by PinCabOS refactor (original lines 1756-1770).


# Moved to modular route file by PinCabOS refactor (original lines 1773-1832).


# Moved to modular route file by PinCabOS refactor (original lines 1835-1854).


# Moved to modular route file by PinCabOS refactor (original lines 1857-1878).
# === FIRST RUN WIZARD - PINCABOS END ===

# === PINCABOS FIRST RUN AUTO REDIRECT START ===


# === PINCABOS KEYBOARD TOOLS V6 BEGIN ===
pco_register_keyboard_tools_v6(app)
# === PINCABOS KEYBOARD TOOLS V6 END ===

# === PINCABOS KEYBOARD WIDGET ROUTES BEGIN ===
pco_register_keyboard_routes(app, page)
# === PINCABOS KEYBOARD WIDGET ROUTES END ===

def pincabos_firstrun_is_complete():
    # PINCABOS_FIRSTRUN_3STEP_COMPLETE_V3
    # Une fois les trois etapes sauvegardees, First Run est termine.
    # Un etat temporaire GPU ne doit jamais reactiver l'assistant.
    try:
        cfg = firstrun_load_cfg()
        keys = firstrun_required_keys()
        return bool(keys) and all(bool(cfg.get(key)) for key in keys)
    except Exception:
        return False


@app.before_request
def pincabos_first_run_auto_redirect():
    try:
        path = request.path or "/"

        allowed_prefixes = (
            "/first-run",
            "/static",
            "/api",
            "/admin",
            "/dev",
            "/service-control",
        )

        if path != "/":
            return None

        if any(path.startswith(p) for p in allowed_prefixes):
            return None

        if not pincabos_firstrun_is_complete():
            return redirect("/first-run")

        return None
    except Exception:
        return None
# === PINCABOS FIRST RUN AUTO REDIRECT END ===


# === PINCABOS_ABOUT_HELP_REFACTOR_V1 ===
# Route help_page déplacée vers /opt/pincabos/web/PinCabOS-AboutHelp.py


# Moved to modular route file by PinCabOS refactor (original lines 2196-2270).


# Moved to modular route file by PinCabOS refactor (original lines 2273-2279).


# Moved to modular route file by PinCabOS refactor (original lines 2283-2368).


# Moved to modular route file by PinCabOS refactor (original lines 2371-2377).


# Moved to modular route file by PinCabOS refactor (original lines 2381-2448).


# Moved to modular route file by PinCabOS refactor (original lines 2451-2458).


# Moved to modular route file by PinCabOS refactor (original lines 2461-2605).


# === PINCABOS_ABOUT_HELP_REFACTOR_V1 ===
# Route about_page déplacée vers /opt/pincabos/web/PinCabOS-AboutHelp.py


@app.route("/")
def dashboard():
    return render_dashboard(page, esc, get_ip, service_status, pincabos_version)


def screens_layout_text():
    try:
        f = Path("/opt/pincabos/config/screens/screens.json")
        if f.exists():
            return f.read_text(errors="replace")
    except Exception as e:
        return f"Erreur lecture screens.json: {e}"
    return "Aucune auto-détection écran sauvegardée pour le moment."


# PINCABOS_WEBAPP_MODULES_V1 : pages GPU / Écrans et DOF / Outputs dans leurs modules.
import pincabos_webapp_gpu as pco_gpu_routes
import pincabos_webapp_dof as pco_dof_routes

pco_gpu_routes.register(app, page)
pco_dof_routes.register(app, page)


@app.route("/service-control", methods=["POST"])
def service_control():
    """
    Contrôle sécurisé des services PinCabOS depuis le dashboard.
    Accepte: service + action.
    Actions supportées: start, stop, restart, reload, kill.
    """
    service = request.form.get("service", "").strip()
    action = request.form.get("action", "").strip().lower()

    allowed_services = {
        "pincabos-vpinfe.service",
        "pincabos-webapp.service",
        "pincabos-console.service",
    }

    action_map = {
        "start": "start",
        "stop": "stop",
        "restart": "restart",
        "reload": "restart",
        "kill": "kill",
    }

    if service not in allowed_services:
        return f"Service non autorisé: {esc(service)}", 400

    if action not in action_map:
        return f"Action non autorisée: {esc(action)}", 400

    cmd_action = action_map[action]

    try:
        if cmd_action == "kill":
            subprocess.Popen(
                ["/usr/bin/sudo", "/bin/systemctl", "kill", service],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                ["/usr/bin/sudo", "/bin/systemctl", cmd_action, service],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except Exception as e:
        return f"Erreur contrôle service: {esc(str(e))}", 500

    return redirect(request.referrer or "/")


@app.route("/service-control/<service_key>/<action>", methods=["GET", "POST"])
def service_control_path(service_key, action):
    """
    Route générique pour les boutons Services du dashboard PinCabOS.
    Supporte les URLs du genre:
      /service-control/web/start
      /service-control/web/restart
      /service-control/frontend/stop
      /service-control/frontend/reload
    """
    service_map = {
        # VPinFE / frontend
        "frontend": "pincabos-vpinfe.service",
        "vpinfe": "pincabos-vpinfe.service",
        "front": "pincabos-vpinfe.service",

        # Web manager
        "web": "pincabos-webapp.service",
        "web-manager": "pincabos-webapp.service",
        "manager": "pincabos-webapp.service",

        # Console Commander
        "console": "pincabos-console.service",
        "webconsole": "pincabos-console.service",
        "web-console": "pincabos-console.service",

        # Console web

        # Auto timezone
    }

    action_map = {
        "start": "start",
        "play": "start",
        "stop": "stop",
        "restart": "restart",
        "reload": "restart",
        "refresh": "restart",
        "kill": "kill",
    }

    service_key = str(service_key or "").strip().lower()
    action = str(action or "").strip().lower()

    if service_key not in service_map:
        return f"Service non autorisé: {esc(service_key)}", 400

    if action not in action_map:
        return f"Action non autorisée: {esc(action)}", 400

    service = service_map[service_key]
    systemctl_action = action_map[action]

    try:
        subprocess.Popen(
            ["/usr/bin/sudo", "/bin/systemctl", systemctl_action, service],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        return f"Erreur contrôle service: {esc(str(e))}", 500

    return redirect(request.referrer or "/")


# === PINCABOS DASHBOARD VPX PROCESS CONTROL START ===
@app.route("/process-control/vpx/<action>", methods=["POST"])
def process_control_vpx(action):
    """
    Contrôle prudent du processus VPX lancé par VPinFE.
    VPX n'est pas un service systemd direct, donc:
      - stop / kill : termine VPinballX seulement
      - restart     : termine VPinballX puis redémarre VPinFE
      - start       : redémarre VPinFE, car VPX part normalement via VPinFE/table
    """
    action = str(action or "").strip().lower()

    allowed = {"start", "stop", "restart", "kill", "play"}
    if action not in allowed:
        return f"Action VPX non autorisée: {esc(action)}", 400

    try:
        if action in {"stop", "kill"}:
            subprocess.Popen(
                ["/usr/bin/pkill", "-TERM", "-f", pco_vpx_kill_pattern()],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif action in {"restart", "start", "play"}:
            subprocess.Popen(
                ["/usr/bin/pkill", "-TERM", "-f", pco_vpx_kill_pattern()],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.Popen(
                ["/usr/bin/sudo", "/bin/systemctl", "restart", "pincabos-vpinfe.service"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except Exception as e:
        return f"Erreur contrôle VPX: {esc(str(e))}", 500

    return redirect(request.referrer or "/")
# === PINCABOS DASHBOARD VPX PROCESS CONTROL END ===


# === PINCABOS VPINFE VERSION HELPERS START ===
def _pincabos_vpinfe_status_payload(remote=False):
    script = Path("/opt/pincabos/tools/vpinfeupdate.py")
    command = ["/usr/bin/python3", str(script), "--status"]
    if remote:
        command.append("--remote")
    try:
        result = subprocess.run(command, text=True, capture_output=True, timeout=35)
        payload = json.loads((result.stdout or "").strip() or "{}")
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def pincabos_vpinfe_local_version():
    payload = _pincabos_vpinfe_status_payload(remote=False)
    local = payload.get("local", {}) if isinstance(payload.get("local"), dict) else {}
    return local.get("display") or "non détectée"


def pincabos_vpinfe_available_version():
    payload = _pincabos_vpinfe_status_payload(remote=True)
    remote = payload.get("remote", {}) if isinstance(payload.get("remote"), dict) else {}
    return remote.get("tag") or "non détectée"
# === PINCABOS VPINFE VERSION HELPERS END ===


def pincabos_vpinball_local_version():
    """
    Détection locale VPX/VPinball.
    On évite les faux positifs comme 0.115 provenant de libs/aide.
    Chemins officiels PinCabOS:
      /opt/pincabos/bin/vpx-vpinfe-default.sh
      /opt/pincabos/bin/vpx-vpinfe-default.sh
    """
    import re
    import subprocess
    from pathlib import Path

    candidates = [
        Path("/opt/pincabos/bin/vpx-vpinfe-default.sh"),
        Path("/home/pinball/vpx/VPinballX_BGFX"),
        Path("/opt/pincabos/bin/vpx-vpinfe-default.sh"),
    ]

    ignored_versions = {"0.115", "0.14", "0.14.0", "0.1.0", "0.4.1", "0.8.0", "0.9.0"}

    for exe in candidates:
        if exe.exists() and exe.is_file() and exe.stat().st_mode & 0o111:
            for arg in ("-version", "--version"):
                try:
                    r = subprocess.run(
                        [str(exe), arg],
                        text=True,
                        capture_output=True,
                        timeout=8,
                        cwd=str(exe.parent),
                        env={
                            "HOME": "/home/pinball",
                            "XDG_CONFIG_HOME": "/home/pinball/.config",
                            "XDG_DATA_HOME": "/home/pinball/.local/share",
                        },
                    )
                    out = ((r.stdout or "") + "\n" + (r.stderr or "")).strip()

                    # On accepte surtout les versions VPX connues 10.x.
                    m = re.search(r"\bv?10\.\d+(?:\.\d+){0,2}\b", out)
                    if m:
                        return m.group(0)

                    # Fallback général, mais ignore les versions de libs.
                    for m in re.finditer(r"\bv?\d+(?:\.\d+){1,3}\b", out):
                        val = m.group(0)
                        if val not in ignored_versions and not val.startswith("0."):
                            return val
                except Exception:
                    pass

            # Binaire présent, mais version exacte non fiable.
            if "BGFX" in exe.name.upper():
                return "VPX BGFX installé"
            return "VPX installé"

    if Path('/home/pinball/vpx').is_dir():
        return "VPX installé"

    return "non détectée"


def pincabos_vpinball_available_version():
    """
    Version disponible VPX/VPinball.
    Pour l'instant on tente GitHub officiel, sinon fallback local.
    """
    import json as _json
    import urllib.request
    import re
    import subprocess

    urls = [
        "https://api.github.com/repos/vpinball/vpinball/releases/latest",
        "https://api.github.com/repos/vpinball/vpinball/actions/artifacts",
    ]

    for url in urls:
        try:
            with urllib.request.urlopen(url, timeout=6) as r:
                data = _json.loads(r.read().decode("utf-8", errors="replace"))

            tag = (data.get("tag_name") or data.get("name") or "").strip()
            m = re.search(r"\bv?\d+(?:\.\d+){1,3}\b", tag)
            if m:
                return m.group(0)

            artifacts = data.get("artifacts") or []
            for a in artifacts:
                name = str(a.get("name") or "")
                if "linux" in name.lower() or "bgfx" in name.lower() or "vpinball" in name.lower():
                    m = re.search(r"\bv?\d+(?:\.\d+){1,3}\b", name)
                    if m:
                        return m.group(0)
        except Exception:
            pass

    # Fallback: ne pas afficher non détectée si VPX local est présent.
    local = pincabos_vpinball_local_version()
    if local != "non détectée":
        return local

    return "non détectée"


def pincabos_gpu_local_version():
    """
    État GPU/pilote local.
    Ne lance aucune installation.
    """
    import subprocess
    import re

    try:
        r = subprocess.run(
            ["/usr/bin/nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
            text=True,
            capture_output=True,
            timeout=4,
        )
        out = (r.stdout or "").strip().splitlines()
        if out and out[0].strip():
            return "NVIDIA " + out[0].strip()
    except Exception:
        pass

    try:
        r = subprocess.run(
            ["/sbin/modinfo", "nvidia"],
            text=True,
            capture_output=True,
            timeout=4,
        )
        out = (r.stdout or "") + "\\n" + (r.stderr or "")
        m = re.search(r"^version:\\s*(.+)$", out, re.M)
        if m:
            return "NVIDIA " + m.group(1).strip()
    except Exception:
        pass

    try:
        r = subprocess.run(
            ["/usr/bin/lspci"],
            text=True,
            capture_output=True,
            timeout=4,
        )
        out = r.stdout or ""
        lines = [
            x for x in out.splitlines()
            if "VGA" in x or "3D controller" in x or "Display controller" in x
        ]
        if lines:
            line = lines[0]
            up = line.upper()
            if "NVIDIA" in up:
                return "NVIDIA détectée"
            if "AMD" in up or "ATI" in up:
                return "AMD/Mesa détecté"
            if "INTEL" in up:
                return "Intel/Mesa détecté"
            if "RED HAT" in up or "VIRTIO" in up:
                return "Virtio/QEMU détecté"
            return "GPU détecté"
    except Exception:
        pass

    return "non détecté"


def pincabos_gpu_available_version():
    """
    Pilote GPU recommandé disponible.
    Ne lance aucune installation.
    """
    import subprocess
    import re

    try:
        r = subprocess.run(
            ["/usr/bin/ubuntu-drivers", "devices"],
            text=True,
            capture_output=True,
            timeout=8,
        )
        out = (r.stdout or "") + "\\n" + (r.stderr or "")
        m = re.search(r"(nvidia-driver-\\d+[^ \\n]*)\\s+.*recommended", out, re.I)
        if m:
            return m.group(1).strip()
        m = re.search(r"(nvidia-driver-\\d+[^ \\n]*)", out, re.I)
        if m:
            return m.group(1).strip()
    except Exception:
        pass

    local = pincabos_gpu_local_version()
    if local != "non détecté":
        return "à jour / auto"

    return "non détecté"


def pincabos_ubuntu_local_version():
    """
    Version Ubuntu locale.
    """
    from pathlib import Path

    osr = Path("/etc/os-release")
    if osr.is_file():
        data = {}
        for line in osr.read_text(errors="replace").splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                data[k] = v.strip().strip('"')
        return data.get("PRETTY_NAME") or data.get("VERSION") or data.get("VERSION_ID") or "Ubuntu détecté"

    return "non détectée"


def pincabos_ubuntu_available_version():
    """
    Résumé des paquets Ubuntu disponibles.
    Ne fait pas apt update; lit seulement l'état apt actuel.
    """
    import subprocess

    try:
        r = subprocess.run(
            ["/usr/bin/apt", "list", "--upgradable"],
            text=True,
            capture_output=True,
            timeout=8,
        )
        lines = []
        for line in (r.stdout or "").splitlines():
            line = line.strip()
            if not line or line.startswith("Listing"):
                continue
            if "/" in line and "[" in line:
                lines.append(line)

        if len(lines) == 0:
            return "à jour"
        if len(lines) == 1:
            return "1 paquet"
        return str(len(lines)) + " paquets"
    except Exception:
        pass

    return "vérifier"

# Moved to modular route file by PinCabOS refactor (original lines 7246-7515).


# Moved to modular route file by PinCabOS refactor (original lines 7518-7520).

# Moved to modular route file by PinCabOS refactor (original lines 7522-7627).


# PINCABOS_WEBAPP_MODULES_V1 : pages DMD / FullDMD dans leur module.
import pincabos_webapp_dmd as pco_dmd_routes

pco_dmd_routes.register(app, page)


# PINCABOS_WEBAPP_MODULES_V1 : console, réseau, écran WebApp et mot de passe root dans leur module.
import pincabos_webapp_console as pco_console_routes

pco_console_routes.register(app, page)


# Moved to modular route file by PinCabOS refactor (original lines 9709-9709).

# Moved to modular route file by PinCabOS refactor (original lines 9711-9723).


# Moved to modular route file by PinCabOS refactor (original lines 9726-9737).


# Moved to modular route file by PinCabOS refactor (original lines 9740-9753).


# Moved to modular route file by PinCabOS refactor (original lines 9756-9758).


# Moved to modular route file by PinCabOS refactor (original lines 9762-9809).


# Moved to modular route file by PinCabOS refactor (original lines 9813-9823).


# Moved to modular route file by PinCabOS refactor (original lines 9826-9827).


# Moved to modular route file by PinCabOS refactor (original lines 9830-9831).


# Moved to modular route file by PinCabOS refactor (original lines 9834-9855).


# Moved to modular route file by PinCabOS refactor (original lines 9858-9869).


AUDIO_VPX_INI = pincabos_vpx_ini_path()
AUDIO_VPINFE_INI = pincabos_vpinfe_ini_path()
AUDIO_BACKUP_DIR = Path("/opt/pincabos/backups/audio-ssf")


# Moved to modular route file by PinCabOS refactor (original lines 9877-9885).


# Moved to modular route file by PinCabOS refactor (original lines 9888-9890).


# Moved to modular route file by PinCabOS refactor (original lines 9893-9896).


# Moved to modular route file by PinCabOS refactor (original lines 9899-9901).


# Moved to modular route file by PinCabOS refactor (original lines 9904-9923).


# Moved to modular route file by PinCabOS refactor (original lines 9926-9972).


# Moved to modular route file by PinCabOS refactor (original lines 9975-9994).


# Moved to modular route file by PinCabOS refactor (original lines 9997-10007).


# Moved to modular route file by PinCabOS refactor (original lines 10010-10094).


# === PINCABOS AUDIO OPTIONAL ALSA CARD HELPER START ===
# Moved to modular route file by PinCabOS refactor (original lines 10098-10107).


# Moved to modular route file by PinCabOS refactor (original lines 10110-10189).


# Moved to modular route file by PinCabOS refactor (original lines 10192-10318).


# === PINCABOS AUDIO INI READ HELPERS RESTORE START ===
# Moved to modular route file by PinCabOS refactor (original lines 10325-10356).


# Moved to modular route file by PinCabOS refactor (original lines 10359-10364).
# === PINCABOS AUDIO INI READ HELPERS RESTORE END ===


# Moved to modular route file by PinCabOS refactor (original lines 10368-10442).
# === PINCABOS AUDIO INI VALUES CARD END ===


# === PINCABOS AUDIO SYSTEM VOLUME BALANCE START ===

# Moved to modular route file by PinCabOS refactor (original lines 10448-10459).


# Moved to modular route file by PinCabOS refactor (original lines 10462-10471).


# Moved to modular route file by PinCabOS refactor (original lines 10474-10508).


# Moved to modular route file by PinCabOS refactor (original lines 10511-10554).


# Moved to modular route file by PinCabOS refactor (original lines 10557-10646).


# Moved to modular route file by PinCabOS refactor (original lines 10649-10650).


# Moved to modular route file by PinCabOS refactor (original lines 10653-10826).


# === PINCABOS AUDIO SSF PAGE ROUTE FIX START ===
# Moved to modular route file by PinCabOS refactor (original lines 10830-11028).
# === PINCABOS AUDIO SSF PAGE ROUTE FIX END ===


# Moved to modular route file by PinCabOS refactor (original lines 11032-11082).


# Moved to modular route file by PinCabOS refactor (original lines 11085-11088).


# Moved to modular route file by PinCabOS refactor (original lines 11091-11096).


# === PINCABOS AUDIO VU HTML ROUTE START ===
# Moved to modular route file by PinCabOS refactor (original lines 11100-11102).


# Moved to modular route file by PinCabOS refactor (original lines 11105-11106).


# Moved to modular route file by PinCabOS refactor (original lines 11109-11131).


# === SSF COMMANDER V1 - PINCABOS START ===
# Moved to modular route file by PinCabOS refactor (original lines 11135-11135).

# Moved to modular route file by PinCabOS refactor (original lines 11137-11147).

# Moved to modular route file by PinCabOS refactor (original lines 11149-11154).

# Moved to modular route file by PinCabOS refactor (original lines 11156-11158).

# Moved to modular route file by PinCabOS refactor (original lines 11160-11190).

# Moved to modular route file by PinCabOS refactor (original lines 11192-11288).


# Moved to modular route file by PinCabOS refactor (original lines 11291-11303).

# === PINCABOS AUDIO WAV ROUTES REAL START ===
# Moved to modular route file by PinCabOS refactor (original lines 11306-11407).


# Moved to modular route file by PinCabOS refactor (original lines 11410-11450).


# Moved to modular route file by PinCabOS refactor (original lines 11453-11457).


# Moved to modular route file by PinCabOS refactor (original lines 11460-11554).


# Moved to modular route file by PinCabOS refactor (original lines 11557-11595).


# Moved to modular route file by PinCabOS refactor (original lines 11598-11627).


# === PINCABOS DEV REAL LOGIN START ===
# PINCABOS_ADMIN_CREDENTIALS_FAIL_CLOSED_V1
def _pco_read_auth_value(env_name, *paths):
    value = os.environ.get(env_name, "").strip()
    if value:
        return value
    for raw_path in paths:
        try:
            candidate = Path(raw_path)
            if candidate.is_file():
                value = candidate.read_text(encoding="utf-8").strip()
                if value:
                    return value
        except OSError:
            pass
    return ""


ADMIN_LOGIN_USER = _pco_read_auth_value(
    "PINCABOS_ADMIN_LOGIN",
    "/opt/pincabos/config/admin-login.txt",
    "/opt/pincabos/config/dev-login.txt",
)
ADMIN_LOGIN_PASS = _pco_read_auth_value(
    "PINCABOS_ADMIN_PASSWORD",
    "/opt/pincabos/config/admin-password.txt",
    "/opt/pincabos/config/dev-password.txt",
)
# PINCABOS_ADMIN_CREDENTIALS_FAIL_CLOSED_V1_END


# PINCABOS_ADMIN_DEFAULT_CREDENTIALS_V1
# Les fichiers de secrets ne sont pas versionnes : sur une image fraiche ils
# manquent et les pages /admin et /dev repondaient "identifiants non
# configures". On retombe sur un identifiant par DEFAUT documente, que
# `pincabos-admin-password` permet de remplacer, et les pages affichent un
# avertissement tant qu'il est en place.
PINCABOS_DEFAULT_ADMIN_USER = "admin"
PINCABOS_DEFAULT_ADMIN_PASS = "PinCabOS123$"

# La page /dev a ses PROPRES identifiants : deux acces distincts, deux secrets
# distincts. Les fichiers dev-login.txt / dev-password.txt restent maitres.
PINCABOS_DEFAULT_DEV_USER = "PinCabOsDev"
PINCABOS_DEFAULT_DEV_PASS = "PinCabOSDev123$"

PINCABOS_ADMIN_CREDENTIALS_ARE_DEFAULT = not (ADMIN_LOGIN_USER and ADMIN_LOGIN_PASS)

if not ADMIN_LOGIN_USER:
    ADMIN_LOGIN_USER = PINCABOS_DEFAULT_ADMIN_USER
if not ADMIN_LOGIN_PASS:
    ADMIN_LOGIN_PASS = PINCABOS_DEFAULT_ADMIN_PASS
# Fichier present mais illisible par la WebApp (proprietaire root) : sans ce
# controle, on retombe sur le defaut sans rien dire et l'ancien mot de passe
# continue de fonctionner.
PINCABOS_ADMIN_UNREADABLE_SECRETS = [
    candidate
    for candidate in (
        "/opt/pincabos/config/admin-password.txt",
        "/opt/pincabos/config/admin-login.txt",
        "/opt/pincabos/config/dev-password.txt",
    )
    if os.path.exists(candidate) and not os.access(candidate, os.R_OK)
]
# PINCABOS_ADMIN_DEFAULT_CREDENTIALS_V1_END


# Moved to modular route file by PinCabOS refactor (original lines 11637-11641).

# Moved to modular route file by PinCabOS refactor (original lines 11643-11661).

# === PINCABOS ADMIN HIDDEN PAGE START ===

# Moved to modular route file by PinCabOS refactor (original lines 11667-11671).

# Moved to modular route file by PinCabOS refactor (original lines 11673-11701).

# === PINCABOS ADMIN SIMPLE STATUS HELPERS START ===


# Moved to modular route file by PinCabOS refactor (original lines 11716-11767).

# Moved to modular route file by PinCabOS refactor (original lines 11769-11803).


# Moved to modular route file by PinCabOS refactor (original lines 11806-11868).


# Moved to modular route file by PinCabOS refactor (original lines 11871-11950).

# Moved to modular route file by PinCabOS refactor (original lines 11952-11987).

# Moved to modular route file by PinCabOS refactor (original lines 11989-12004).


# === PinCabOS managed block: admin-log-options-html BEGIN ===
# Moved to modular route file by PinCabOS refactor (original lines 12010-12033).
# === PinCabOS managed block: admin-log-options-html END ===


# Moved to modular route file by PinCabOS refactor (original lines 12037-12358).


# Moved to modular route file by PinCabOS refactor (original lines 12361-12362).


# Moved to modular route file by PinCabOS refactor (original lines 12365-12376).

# Moved to modular route file by PinCabOS refactor (original lines 12378-12383).

# === PINCABOS ADMIN RESTORE STABLE START ===

# Moved to modular route file by PinCabOS refactor (original lines 12389-12393).


# Moved to modular route file by PinCabOS refactor (original lines 12396-12402).

# Moved to modular route file by PinCabOS refactor (original lines 12404-12410).

# Moved to modular route file by PinCabOS refactor (original lines 12412-12418).

# Moved to modular route file by PinCabOS refactor (original lines 12420-12423).

# Moved to modular route file by PinCabOS refactor (original lines 12425-12441).

# Moved to modular route file by PinCabOS refactor (original lines 12443-12455).

# Moved to modular route file by PinCabOS refactor (original lines 12457-12460).
# === PINCABOS ADMIN RESTORE STABLE END ===


# Compatibility proxy: the following legacy Admin enhancements are applied before
# modular route registration. It delegates to the moved original admin page.
def pincabos_admin_page(*args, **kwargs):
    return pco_dev_admin_routes.pco_admin_page_base(*args, **kwargs)

# === PINCABOS ABOUT SUPPORTERS ADMIN START ===
ABOUT_SUPPORTERS_CONFIG = Path("/opt/pincabos/config/about-supporters.json")

def pincabos_about_supporters_default():
    return {
        "title": "Testeurs / Soutiens fondateurs",
        "intro": "Merci aux personnes qui aident à tester PinCabOS, rapporter les problèmes, proposer des idées et soutenir le développement du projet.",
        "supporters": [
            "Strung Flo",
            "Nicolas Prou",
            "Olivier Chéron",
        ],
        "founders_title": "Nom Fondateurs",
        "founders": [],
    }

def pincabos_about_supporters_normalize_list(value):
    if isinstance(value, str):
        return [x.strip() for x in value.splitlines() if x.strip()]
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return []

def pincabos_about_supporters_load():
    import json

    default = pincabos_about_supporters_default()

    try:
        if ABOUT_SUPPORTERS_CONFIG.exists():
            data = json.loads(ABOUT_SUPPORTERS_CONFIG.read_text(errors="replace"))
            if not isinstance(data, dict):
                data = {}
        else:
            data = {}
    except Exception:
        data = {}

    supporters = pincabos_about_supporters_normalize_list(data.get("supporters", default["supporters"]))
    founders = pincabos_about_supporters_normalize_list(data.get("founders", default["founders"]))

    if not supporters:
        supporters = default["supporters"]

    return {
        "title": str(data.get("title") or default["title"]).strip(),
        "intro": str(data.get("intro") or default["intro"]).strip(),
        "supporters": supporters,
        "founders_title": str(data.get("founders_title") or default["founders_title"]).strip(),
        "founders": founders,
    }

def pincabos_about_supporters_save(data):
    import json
    import datetime

    ABOUT_SUPPORTERS_CONFIG.parent.mkdir(parents=True, exist_ok=True)

    backup_dir = Path("/opt/pincabos/backups/about-supporters")
    backup_dir.mkdir(parents=True, exist_ok=True)

    try:
        backup_dir.chmod(0o775)
    except Exception:
        pass

    if ABOUT_SUPPORTERS_CONFIG.exists():
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = backup_dir / ("about-supporters.json.backup-admin-" + ts)
        backup.write_text(ABOUT_SUPPORTERS_CONFIG.read_text(errors="replace"), encoding="utf-8")

    ABOUT_SUPPORTERS_CONFIG.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8"
    )

    try:
        ABOUT_SUPPORTERS_CONFIG.chmod(0o664)
    except Exception:
        pass

def pincabos_about_supporters_public_card():
    data = pincabos_about_supporters_load()

    rows = []

    # Fusion visuelle des deux listes, puis tri alphabétique par nom.
    # role = "supporter" => une étoile
    # role = "founder"   => deux étoiles
    people = []

    for name in data.get("supporters", []):
        people.append({
            "name": str(name).strip(),
            "role": "supporter",
        })

    for name in data.get("founders", []):
        people.append({
            "name": str(name).strip(),
            "role": "founder",
        })

    people = [p for p in people if p.get("name")]

    # Déduplique en gardant le rôle fondateur prioritaire si le même nom est dans les deux listes.
    merged = {}
    for p in people:
        key = p["name"].casefold()
        if key not in merged:
            merged[key] = p
        elif p.get("role") == "founder":
            merged[key] = p

    people = sorted(
        merged.values(),
        key=lambda p: p.get("name", "").casefold()
    )

    for person in people:
        name = person.get("name", "")
        role = person.get("role", "supporter")

        if role == "founder":
            rows.append(
                '<div style="display:inline-flex;align-items:center;gap:8px;margin:6px 10px 6px 0;'
                'padding:10px 14px;border:1px solid rgba(255,176,0,.55);border-radius:999px;'
                'background:rgba(255,176,0,.08);box-shadow:0 0 16px rgba(255,176,0,.18);">'
                '<span style="color:#ffb000;">★★</span>'
                '<strong>' + esc(name) + '</strong>'
                '<span style="color:#ffb000;">★★</span>'
                '</div>'
            )
        else:
            rows.append(
                '<div style="display:inline-flex;align-items:center;gap:8px;margin:6px 10px 6px 0;'
                'padding:9px 12px;border:1px solid rgba(255,176,0,.35);border-radius:999px;'
                'background:rgba(0,0,0,.25);">'
                '<span style="color:#ffb000;">★</span>'
                '<strong>' + esc(name) + '</strong>'
                '<span style="color:#ffb000;">★</span>'
                '</div>'
            )

    if not rows:
        rows.append('<p class="warn">Aucun testeur/supporter configuré.</p>')

    return """
<!-- PINCABOS_ABOUT_SUPPORTERS_CARD -->
<div class="card" id="testeurs-soutiens-fondateurs">
  <h2>__TITLE__</h2>
  <p>__INTRO__</p>
  <div style="margin-top:10px;">__ROWS__</div>
</div>
""".replace("__TITLE__", esc(data.get("title", ""))) \
   .replace("__INTRO__", esc(data.get("intro", ""))) \
   .replace("__ROWS__", "\n".join(rows))

def pincabos_about_supporters_admin_card():
    data = pincabos_about_supporters_load()
    supporters_text = "\n".join(data.get("supporters", []))
    founders_text = "\n".join(data.get("founders", []))

    return """
<!-- PINCABOS_ADMIN_ABOUT_SUPPORTERS_CARD -->
<div class="card" id="about-supporters" style="margin-top:20px;">
  <h2>About - Testeurs / Soutiens fondateurs</h2>
  <p>Modifie la section affichée dans <code>/about</code>.</p>

  <form method="post" action="/admin/about-supporters/save">
    <label>Titre<br>
      <input name="title" value="__TITLE__" style="width:95%;padding:10px;">
    </label>

    <p>
      <label>Texte<br>
        <textarea name="intro" rows="3" style="width:95%;padding:10px;">__INTRO__</textarea>
      </label>
    </p>

    <p>
      <label>Noms Testeurs / Soutiens, un par ligne<br>
        <textarea name="supporters" rows="8" style="width:95%;padding:10px;">__SUPPORTERS__</textarea>
      </label>
    </p>

    <p>
      <label>Nom Fondateurs<br>
        <input name="founders_title" value="__FOUNDERS_TITLE__" style="width:95%;padding:10px;">
      </label>
    </p>

    <p>
      <label>Noms Fondateurs, un par ligne<br>
        <textarea name="founders" rows="6" style="width:95%;padding:10px;">__FOUNDERS__</textarea>
      </label>
      <small style="opacity:.75;">Dans About, ces noms restent dans la même section et apparaissent avec deux étoiles de chaque côté.</small>
    </p>

    <p>
      <button class="button" type="submit">💾 Sauvegarder Testeurs / Soutiens</button>
      <a class="button secondary" href="/about#testeurs-soutiens-fondateurs">👁️ Voir dans About</a>
    </p>
  </form>
</div>
""".replace("__TITLE__", esc(data.get("title", ""))) \
   .replace("__INTRO__", esc(data.get("intro", ""))) \
   .replace("__SUPPORTERS__", esc(supporters_text)) \
   .replace("__FOUNDERS_TITLE__", esc(data.get("founders_title", "Nom Fondateurs"))) \
   .replace("__FOUNDERS__", esc(founders_text))

def pincabos_about_supporters_insert_public(html):
    card = pincabos_about_supporters_public_card()
    body = str(html)

    if "PINCABOS_ABOUT_SUPPORTERS_CARD" in body:
        return body

    import re
    pattern = re.compile(
        r'<div class="card"[^>]*>\s*<h2>\s*Testeurs\s*/\s*Soutiens fondateurs\s*</h2>[\s\S]*?</div>',
        re.IGNORECASE
    )
    body, count = pattern.subn(card, body, count=1)
    if count:
        return body

    if "</main>" in body:
        return body.replace("</main>", card + "\n</main>", 1)
    if "</body>" in body:
        return body.replace("</body>", card + "\n</body>", 1)
    return body + "\n" + card

try:
    _pincabos_about_original_endpoint = None
    _pincabos_about_original_view = None

    for _rule in app.url_map.iter_rules():
        if getattr(_rule, "rule", "") == "/about":
            _pincabos_about_original_endpoint = _rule.endpoint
            _pincabos_about_original_view = app.view_functions.get(_rule.endpoint)
            break

    if _pincabos_about_original_endpoint and _pincabos_about_original_view:
        def _pincabos_about_supporters_wrapped_view(*args, **kwargs):
            result = _pincabos_about_original_view(*args, **kwargs)

            if isinstance(result, tuple):
                body = pincabos_about_supporters_insert_public(result[0])
                return (body,) + result[1:]

            return pincabos_about_supporters_insert_public(result)

        app.view_functions[_pincabos_about_original_endpoint] = _pincabos_about_supporters_wrapped_view
except Exception:
    pass

try:
    _pincabos_admin_page_original_for_about_supporters = pincabos_admin_page

    def pincabos_admin_page():
        html = _pincabos_admin_page_original_for_about_supporters()
        card = pincabos_about_supporters_admin_card()

        if "PINCABOS_ADMIN_ABOUT_SUPPORTERS_CARD" in str(html):
            return html

        def _pco_insert_before_footer(body, card):
            # Position voulue:
            # APRÈS la carte complète qui contient "Publish / Cleanup PinCabOS",
            # pas dans la carte, pas juste après les boutons, pas dans le footer.

            import re

            def _pco_find_matching_div_end(src, div_start):
                # Trouve le </div> correspondant au <div ...> de div_start.
                tag_re = re.compile(r'<(/?)div\b[^>]*>', re.IGNORECASE)
                depth = 0

                for m in tag_re.finditer(src, div_start):
                    closing = m.group(1) == "/"

                    if not closing:
                        depth += 1
                    else:
                        depth -= 1
                        if depth == 0:
                            return m.end()

                return -1

            title_idx = body.find("Publish / Cleanup PinCabOS")
            if title_idx != -1:
                # Trouver le début de la carte contenant ce titre.
                card_start = body.rfind('<div class="card"', 0, title_idx)
                if card_start == -1:
                    card_start = body.rfind("<div", 0, title_idx)

                if card_start != -1:
                    card_end = _pco_find_matching_div_end(body, card_start)
                    if card_end != -1:
                        return body[:card_end] + "\n" + card + body[card_end:]

            # Fallback: avant Version PinCabOS, pour rester dans la zone admin.
            version_idx = body.find("PINCABOS_ADMIN_VERSION_JSON_CARD")
            if version_idx != -1:
                version_card_start = body.rfind('<div class="card"', 0, version_idx)
                if version_card_start != -1:
                    return body[:version_card_start] + card + "\n" + body[version_card_start:]

            # Fallback: avant le footer parent complet.
            lower = body.lower()
            footer_parent = lower.find('id="pincabos-support-footer-static"')
            if footer_parent != -1:
                div_idx = lower.rfind("<div", 0, footer_parent)
                insert_idx = div_idx if div_idx != -1 else footer_parent
                return body[:insert_idx] + card + "\n" + body[insert_idx:]

            return body + "\n" + card


        if isinstance(html, tuple):
            body = str(html[0])
            rest = html[1:]
            body = _pco_insert_before_footer(body, card)
            return (body,) + rest

        body = str(html)
        body = _pco_insert_before_footer(body, card)
        return body

    @app.route("/admin/about-supporters/save", methods=["POST"])
    def pincabos_admin_about_supporters_save():
        guard = pincabos_admin_require_login()
        if guard:
            return guard

        default = pincabos_about_supporters_default()

        title = (request.form.get("title", "") or "").strip() or default["title"]
        intro = (request.form.get("intro", "") or "").strip() or default["intro"]
        supporters = pincabos_about_supporters_normalize_list(request.form.get("supporters", "") or "")
        founders_title = (request.form.get("founders_title", "") or "").strip() or default["founders_title"]
        founders = pincabos_about_supporters_normalize_list(request.form.get("founders", "") or "")

        data = {
            "title": title,
            "intro": intro,
            "supporters": supporters,
            "founders_title": founders_title,
            "founders": founders,
        }

        pincabos_about_supporters_save(data)
        return redirect("/admin#about-supporters")

except Exception:
    pass
# === PINCABOS ABOUT SUPPORTERS ADMIN END ===

# === PINCABOS FOOTER ABOUT SUPPORTERS START ===
# PINCABOS_FOOTER_LAYOUT_V14_1
# Les contributeurs sont rendus directement à droite du QR dans le footer.
def pincabos_footer_supporters_inline_html():
    try:
        data = pincabos_about_supporters_load()
    except Exception:
        data = {}

    title = esc(str(data.get("title") or "Testeurs / Soutiens fondateurs"))
    intro = esc(str(
        data.get("intro")
        or "Merci aux personnes qui aident à tester PinCabOS, rapporter les problèmes, proposer des idées et soutenir le développement du projet."
    ))

    founders = data.get("founders") or []
    supporters = data.get("supporters") or []

    entries = []
    seen = set()

    for name in founders:
        clean = str(name or "").strip()
        key = clean.casefold()
        if clean and key not in seen:
            seen.add(key)
            entries.append(("founder", clean))

    for name in supporters:
        clean = str(name or "").strip()
        key = clean.casefold()
        if clean and key not in seen:
            seen.add(key)
            entries.append(("supporter", clean))

    tags = []
    for kind, name in entries:
        stars = "★★" if kind == "founder" else "★"
        tags.append(
            '<span class="pco-footer-contributor-v14 ' + kind + '">'
            '<i>' + stars + '</i><strong>' + esc(name) + '</strong><i>' + stars + '</i>'
            '</span>'
        )

    if not tags:
        tags.append('<span class="pco-footer-contributors-empty-v14">Aucun testeur/supporter configuré.</span>')

    return (
        '<section id="pincabos-footer-supporters-inline-v14" '
        'class="pincabos-footer-supporters-inline-v14">'
        '<h2>★ ' + title + ' ★</h2>'
        '<p>' + intro + '</p>'
        '<div class="pco-footer-contributors-list-v14">' + "".join(tags) + '</div>'
        '</section>'
    )

# === PINCABOS FOOTER ABOUT SUPPORTERS END ===


# === PINCABOS ADMIN VERSION JSON CARD WRAPPER START ===
try:
    _pincabos_admin_page_original_for_version_json_card = pincabos_admin_page

    def pincabos_admin_version_json_card_html():
        return f"""
<!-- PINCABOS_ADMIN_VERSION_JSON_CARD -->
<div class="card" id="version-json" style="margin-top:20px;">
  <h2>Version PinCabOS</h2>
  <p>Cette section met à jour le fichier maître <code>/opt/pincabos/config/version.json</code>.</p>

  <form method="post" action="/admin/version/save">
    <div style="display:grid; grid-template-columns:repeat(2,minmax(220px,1fr)); gap:12px;">
      <label>Nom<br><input name="name" value="{esc(pincabos_version().get("name", "PinCabOS"))}" style="width:95%; padding:10px;"></label>
      <label>Version<br><input name="version" value="{esc(pincabos_version().get("version", ""))}" style="width:95%; padding:10px;"></label>
      <label>Build<br><input name="build" value="{esc(pincabos_version().get("build", ""))}" style="width:95%; padding:10px;"></label>
      <label>Canal<br><input name="channel" value="{esc(pincabos_version().get("channel", ""))}" style="width:95%; padding:10px;"></label>
      <label>Codename<br><input name="codename" value="{esc(pincabos_version().get("codename", ""))}" style="width:95%; padding:10px;"></label>
      <label>Auteur<br><input name="author" value="{esc(pincabos_version().get("author", "Karots Sugarpie"))}" style="width:95%; padding:10px;"></label>
      <label>Update channel<br><input name="update_channel" value="{esc(pincabos_version().get("update_channel", ""))}" style="width:95%; padding:10px;"></label>
      <label>Update base URL<br><input name="update_base_url" value="{esc(pincabos_version().get("update_base_url", ""))}" style="width:95%; padding:10px;"></label>
      <label>Latest JSON URL<br><input name="latest_json_url" value="{esc(pincabos_version().get("latest_json_url", ""))}" style="width:95%; padding:10px;"></label>
    </div>

    <p style="margin-top:14px;">
      <button class="button" type="submit">💾 Sauvegarder la version</button>
    </p>
  </form>
</div>
"""

    def pincabos_admin_page():
        html = _pincabos_admin_page_original_for_version_json_card()
        card = pincabos_admin_version_json_card_html()

        if "PINCABOS_ADMIN_VERSION_JSON_CARD" in str(html):
            return html

        if isinstance(html, tuple):
            body = str(html[0])
            rest = html[1:]
            if "<h1>Admin PinCabOS</h1>" in body:
                body = body.replace("<h1>Admin PinCabOS</h1>", "<h1>Admin PinCabOS</h1>\n" + card, 1)
            elif "</main>" in body:
                body = body.replace("</main>", card + "\n</main>", 1)
            else:
                body = card + "\n" + body
            return (body,) + rest

        body = str(html)
        if "<h1>Admin PinCabOS</h1>" in body:
            body = body.replace("<h1>Admin PinCabOS</h1>", "<h1>Admin PinCabOS</h1>\n" + card, 1)
        elif "</main>" in body:
            body = body.replace("</main>", card + "\n</main>", 1)
        else:
            body = card + "\n" + body
        return body

    @app.route("/admin/version/save", methods=["POST"])
    def pincabos_admin_version_save():
        guard = pincabos_admin_require_login()
        if guard:
            return guard

        import json
        import datetime
        from pathlib import Path

        version_path = Path("/opt/pincabos/config/version.json")
        backup_dir = Path("/opt/pincabos/backups/version-json")
        backup_dir.mkdir(parents=True, exist_ok=True)
        version_path.parent.mkdir(parents=True, exist_ok=True)

        if version_path.exists():
            ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = backup_dir / ("version.json.backup-admin-light-" + ts)
            backup.write_text(version_path.read_text(errors="replace"), encoding="utf-8")

        keys = [
            "name",
            "version",
            "build",
            "channel",
            "codename",
            "author",
            "update_channel",
            "update_base_url",
            "latest_json_url",
        ]

        clean = {}
        for key in keys:
            clean[key] = (request.form.get(key, "") or "").strip()

        clean["managed_by"] = "PinCabOS"
        clean["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        version_path.write_text(
            json.dumps(clean, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8"
        )

        return redirect("/admin#version-json")

except Exception as _pco_admin_version_json_card_error:
    pass
# === PINCABOS ADMIN VERSION JSON CARD WRAPPER END ===


# === PinCabOS managed block: admin-publy-webpass-secret BEGIN ===
# Moved to modular route file by PinCabOS refactor (original lines 13078-13079).


# Moved to modular route file by PinCabOS refactor (original lines 13082-13089).


# Moved to modular route file by PinCabOS refactor (original lines 13092-13099).
# === PinCabOS managed block: admin-publy-webpass-secret END ===

# === PINCABOS ADMIN PUBLISH IFRAME GET ROUTES START ===

# Moved to modular route file by PinCabOS refactor (original lines 13104-13118).


# === PinCabOS managed block: admin-publy-helper BEGIN ===
# Moved to modular route file by PinCabOS refactor (original lines 13123-13140).
# === PinCabOS managed block: admin-publy-helper END ===


# Moved to modular route file by PinCabOS refactor (original lines 13144-13150).


# Moved to modular route file by PinCabOS refactor (original lines 13153-13159).


# Moved to modular route file by PinCabOS refactor (original lines 13164-13177).

# Moved to modular route file by PinCabOS refactor (original lines 13179-13184).

# Moved to modular route file by PinCabOS refactor (original lines 13186-13191).


# === PinCabOS managed block: admin-log-helpers BEGIN ===
# Moved to modular route file by PinCabOS refactor (original lines 13196-13199).


# Moved to modular route file by PinCabOS refactor (original lines 13202-13219).


# Moved to modular route file by PinCabOS refactor (original lines 13222-13258).


# Moved to modular route file by PinCabOS refactor (original lines 13261-13283).
# === PinCabOS managed block: admin-log-helpers END ===


# Moved to modular route file by PinCabOS refactor (original lines 13287-13301).

# Moved to modular route file by PinCabOS refactor (original lines 13303-13348).

# Moved to modular route file by PinCabOS refactor (original lines 13350-13360).

# Moved to modular route file by PinCabOS refactor (original lines 13362-13375).

# Moved to modular route file by PinCabOS refactor (original lines 13377-13396).
# === PINCABOS ADMIN LOGS MANAGER END ===


# Stage5B.4B: legacy route disabled, real iframe route is pincabos_admin_frame_cleanup_dry_run.
# Moved to modular route file by PinCabOS refactor (original lines 13401-13406).

# Stage5B.4B: legacy route disabled, real iframe route is pincabos_admin_frame_cleanup_apply.
# Moved to modular route file by PinCabOS refactor (original lines 13409-13414).


# Moved to modular route file by PinCabOS refactor (original lines 13417-13420).

# Moved to modular route file by PinCabOS refactor (original lines 13422-13517).

# Moved to modular route file by PinCabOS refactor (original lines 13519-13559).

# Moved to modular route file by PinCabOS refactor (original lines 13561-13567).

# Moved to modular route file by PinCabOS refactor (original lines 13569-13575).

# Stage5B.4B: legacy route disabled, real iframe route is pincabos_admin_frame_cleanup_dry_run.
# Moved to modular route file by PinCabOS refactor (original lines 13578-13583).

# Stage5B.4B: legacy route disabled, real iframe route is pincabos_admin_frame_cleanup_apply.
# Moved to modular route file by PinCabOS refactor (original lines 13586-13591).

# Moved to modular route file by PinCabOS refactor (original lines 13593-13605).

# Moved to modular route file by PinCabOS refactor (original lines 13607-13615).
# === PINCABOS ADMIN HIDDEN PAGE END ===


# Moved to modular route file by PinCabOS refactor (original lines 13619-13631).


def pincabos_import_safe_job_id():
    import datetime
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]


def pincabos_list_archive_files(path):
    try:
        r = subprocess.run(
            ["7z", "l", "-slt", str(path)],
            capture_output=True,
            text=True,
            timeout=45
        )
        data = (r.stdout + "\n" + r.stderr)
        out = []
        for line in data.splitlines():
            line = line.strip()
            if line.startswith("Path = "):
                value = line.split("=", 1)[1].strip()
                if value and value != str(path):
                    out.append(value)
        return out
    except Exception:
        return []


def pincabos_is_zip_rom(path):
    if not str(path).lower().endswith(".zip"):
        return False

    files = [x.lower() for x in pincabos_list_archive_files(path)]
    joined = "\n".join(files)

    markers = [
        ".vpx",
        ".dif",
        ".directb2s",
        ".pov",
        ".vbs",
        "pinupplayer.ini",
        ".pup",
        ".ultradmd",
        "altsound.ini",
        "altsound.csv",
        ".ogg",
        ".wav",
        ".mp3",
        ".flac",
        ".pac",
        ".pal",
        ".vni",
        ".serum",
    ]

    if any(m in joined for m in markers):
        return False

    return True


def pincabos_detect_batch(batch_dir):
    import re
    from pathlib import Path

    batch = Path(batch_dir)
    files = [p for p in batch.rglob("*") if p.is_file()]
    archive_virtual_files = []

    for f in files:
        if f.suffix.lower() in [".zip", ".rar", ".7z"]:
            for inner in pincabos_list_archive_files(f):
                archive_virtual_files.append((f, inner))

    detected = {
        "main_vpx": "",
        "table_name": "",
        "has_vpu_patch": False,
        "vpu_patch_file": "",
        "rom": "",
        "has_b2s": False,
        "has_pov": False,
        "has_ini": False,
        "has_vbs": False,
        "has_rom": False,
        "has_altsound": False,
        "has_altcolor": False,
        "has_puppack": False,
        "has_ultradmd": False,
        "files": [str(x) for x in files],
    }

    vpx_files = [f for f in files if f.suffix.lower() == ".vpx"]
    if vpx_files:
        vpx_files.sort(key=lambda x: x.stat().st_size if x.exists() else 0, reverse=True)
        detected["main_vpx"] = str(vpx_files[0])
        detected["table_name"] = re.sub(r"[_]+", " ", vpx_files[0].stem).strip()

    if not detected["table_name"]:
        for archive, inner in archive_virtual_files:
            if inner.lower().endswith(".vpx"):
                detected["table_name"] = re.sub(r"[_]+", " ", Path(inner).stem).strip()
                detected["main_vpx"] = str(archive) + "::" + inner
                break

    dif_files = [f for f in files if f.suffix.lower() == ".dif"]

    if dif_files:
        detected["has_vpu_patch"] = True
        detected["vpu_patch_file"] = str(dif_files[0])

        if not detected["table_name"]:
            detected["table_name"] = re.sub(
                r"[_]+",
                " ",
                dif_files[0].stem,
            ).strip()

    for archive, inner in archive_virtual_files:
        if inner.lower().endswith(".dif"):
            detected["has_vpu_patch"] = True
            detected["vpu_patch_file"] = str(archive) + "::" + inner

            if not detected["table_name"]:
                detected["table_name"] = re.sub(
                    r"[_]+",
                    " ",
                    Path(inner).stem,
                ).strip()
            break

    for f in files:
        if pincabos_is_zip_rom(f):
            detected["rom"] = f.stem
            detected["has_rom"] = True
            break

    # Détection AltSound et indice ROM
    for f in files:
        if f.suffix.lower() in [".rar", ".7z", ".zip"]:
            inner_files = [x.lower() for x in pincabos_list_archive_files(f)]
            names = [Path(x).name.lower() for x in inner_files]
            if "altsound.ini" in names or "altsound.csv" in names or sum(1 for x in inner_files if x.endswith(".ogg")) > 10:
                detected["has_altsound"] = True
                if not detected["rom"]:
                    detected["rom"] = f.stem

    for f in files:
        suffix = f.suffix.lower()

        if suffix == ".directb2s":
            detected["has_b2s"] = True
        elif suffix == ".pov":
            detected["has_pov"] = True
        elif suffix == ".ini":
            detected["has_ini"] = True
        elif suffix == ".vbs":
            detected["has_vbs"] = True
        elif suffix in [".pac", ".pal", ".vni", ".serum"]:
            detected["has_altcolor"] = True

        if suffix in [".zip", ".rar", ".7z"]:
            inner = "\n".join([x.lower() for x in pincabos_list_archive_files(f)])
            if "pinupplayer.ini" in inner or ".pup" in inner or inner.count(".mp4") >= 3:
                detected["has_puppack"] = True
            if ".ultradmd" in inner:
                detected["has_ultradmd"] = True
            if ".directb2s" in inner:
                detected["has_b2s"] = True
            if ".pov" in inner:
                detected["has_pov"] = True
            if ".vbs" in inner:
                detected["has_vbs"] = True
            if ".dif" in inner:
                detected["has_vpu_patch"] = True
            if ".pac" in inner or ".pal" in inner or ".vni" in inner or ".serum" in inner:
                detected["has_altcolor"] = True

    if not detected["table_name"]:
        detected["table_name"] = batch.name

    return detected


def pincabos_vpsdb_matches(table_name, rom):
    try:
        helper = str(pco_script("vpinfe_vpsdb_match"))
        r = subprocess.run(
            [helper, table_name, rom or ""],
            capture_output=True,
            text=True,
            timeout=30
        )

        if r.returncode != 0:
            print(f"PCO VPSdb helper failed rc={r.returncode}: {helper} stderr={r.stderr[-1200:]}")
            return []

        raw = (r.stdout or "").strip()
        if not raw:
            print(f"PCO VPSdb helper returned empty output: {helper}")
            return []

        data = json.loads(raw)
        if not data.get("ok"):
            print(f"PCO VPSdb helper returned error: {data.get('error', 'unknown error')}")
            return []

        return data.get("matches", [])
    except Exception as exc:
        print(f"PCO VPSdb matcher exception: {exc}")
        return []


PINCABOS_SMART_IMPORT_RESOURCE_MANIFEST = (
    ".pincabos-smart-import-resources.json"
)


def pincabos_smart_import_resource_manifest_path(batch_dir):
    return (
        Path(batch_dir)
        / PINCABOS_SMART_IMPORT_RESOURCE_MANIFEST
    )


def pincabos_smart_import_file_sha256(path):
    digest = hashlib.sha256()

    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def pincabos_smart_import_exact_resource(vpsid):
    wanted = str(vpsid or "").strip()

    if not wanted:
        raise RuntimeError("VPS-ID vide.")

    matches = pincabos_vpsdb_matches(wanted, "")
    exact = [
        match
        for match in matches
        if str(match.get("id", "") or "").strip().casefold()
        == wanted.casefold()
    ]

    if not exact:
        raise RuntimeError(
            f"VPS-ID inconnu dans la base locale VPSDB: {wanted}"
        )

    if len(exact) != 1:
        raise RuntimeError(
            f"VPS-ID ambigu dans VPSDB: {wanted} ({len(exact)} résultats)"
        )

    resource = dict(exact[0])
    resource_type = str(resource.get("resource_type", "") or "").strip()

    if not resource_type or resource_type == "game":
        raise RuntimeError(
            f"{wanted} est l'ID général du jeu. Entre l'ID exact du fichier VPSDB."
        )

    if (
        resource_type == "tableFile"
        and str(resource.get("table_format", "") or "").strip()
        and str(resource.get("table_format", "") or "").strip().casefold()
        != "vpx"
    ):
        raise RuntimeError(
            f"VPS-ID {wanted}: format de table non VPX refusé "
            f"({resource.get('table_format')})."
        )

    return resource


def pincabos_smart_import_load_resource_manifest(batch_dir, required=False):
    path = pincabos_smart_import_resource_manifest_path(batch_dir)

    if not path.is_file():
        if required:
            raise RuntimeError(
                "Inventaire VPS-ID par fichier absent du batch Smart Import."
            )
        return {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(
            f"Inventaire VPS-ID illisible: {exc}"
        ) from exc

    if (
        not isinstance(payload, dict)
        or payload.get("format")
        != "PinCabOS Smart Import resources"
        or not isinstance(payload.get("resources"), list)
    ):
        raise RuntimeError("Inventaire VPS-ID Smart Import invalide.")

    return payload


def pincabos_list_installed_tables_for_export():
    """
    Liste les tables installées pour le menu Export.
    Une table = un dossier dans Tables qui contient au moins un fichier .vpx.
"""
    import json
    from pathlib import Path

    paths = pincabos_get_vpinfe_paths_for_tools()
    tables_root = Path(paths["tables"])

    tables = []

    if not tables_root.exists():
        return tables

    for folder in sorted([x for x in tables_root.iterdir() if x.is_dir()], key=lambda x: x.name.lower()):
        vpx_files = sorted(folder.glob("*.vpx"))

        if not vpx_files:
            continue

        info_files = sorted(folder.glob("*.info"))

        title = folder.name
        rom = ""
        vpsid = ""
        manufacturer = ""
        year = ""

        if info_files:
            try:
                data = json.loads(info_files[0].read_text(errors="replace"))
                info = data.get("Info", {})
                title = info.get("Title") or title
                rom = info.get("Rom") or ""
                vpsid = info.get("VPSId") or ""
                manufacturer = info.get("Manufacturer") or ""
                year = info.get("Year") or ""
            except Exception:
                pass

        extra = []
        if manufacturer:
            extra.append(str(manufacturer))
        if year:
            extra.append(str(year))
        if rom:
            extra.append("ROM " + str(rom))

        label = title
        if extra:
            label += " — " + " — ".join(extra)

        tables.append({
            "folder": folder.name,
            "title": title,
            "rom": rom,
            "vpsid": vpsid,
            "label": label,
        })

    return tables


# PINCABOS_WEBAPP_MODULES_V1 : bille VPX (cabinet, simple, UserBalls) dans son module.
import pincabos_webapp_vpxball as pco_vpxball_routes

pco_vpxball_routes.register(app, page)


# === PINCABOS AUDIO WAV STOP ROUTE FIX START ===
# Moved to modular route file by PinCabOS refactor (original lines 14990-15004).
# === PINCABOS AUDIO WAV STOP ROUTE FIX END ===


# /tools route is registered from tools.py
# Moved to modular route file by PinCabOS refactor (original lines 15010-15044).


def pincabos_try_manifest_import_from_saved_batch(batch_dir):
    """
    Import direct d'un package PinCabOS depuis /tools/import-table/analyze.

    Règle:
    - si le batch contient un .PinCabOs/.pincabos/.zip/.7z/.rar avec pincabos-export-manifest.json,
      on bypass complètement VPSdb/analyse;
    - on restaure selon le manifest;
    - si aucun manifest n'est trouvé, on retourne None et l'analyse normale continue.
    """
    batch_dir = Path(batch_dir)

    archive_exts = {".pincabos", ".zip", ".7z", ".rar"}

    archives = []
    try:
        for p in sorted(batch_dir.rglob("*")):
            if p.is_file() and p.suffix.lower() in archive_exts:
                archives.append(p)
    except Exception:
        archives = []

    for archive_path in archives:
        try:
            with tempfile.TemporaryDirectory(prefix="pincabos-json-found-") as td:
                extract_dir = Path(td) / "extract"
                extract_dir.mkdir(parents=True, exist_ok=True)

                r7 = subprocess.run(
                    ["7z", "x", "-y", f"-o{str(extract_dir)}", str(archive_path)],
                    capture_output=True,
                    text=True,
                    timeout=1800,
                    check=False,
                )

                if r7.returncode != 0:
                    continue

                has_manifest = any(
                    n.name == "pincabos-export-manifest.json"
                    for n in extract_dir.rglob("*")
                    if n.is_file()
                )

                if not has_manifest:
                    continue

                table_folder, _manifest_preview = pincabos_manifest_table_folder_from_archive(archive_path)
                if table_folder:
                    table_root = pincabos_vpx_tables_dir() / table_folder
                    if table_root.exists():
                        return pincabos_manifest_import_conflict_page(batch_dir, archive_path, table_folder)

                result = pincabos_import_from_manifest_dir(extract_dir, overwrite_existing=False)
                if result:
                    if result.get("skipped") and "CONFLICT_TABLE_EXISTS" in result.get("skipped", []):
                        return pincabos_manifest_import_conflict_page(batch_dir, archive_path, result.get("table_folder", table_folder or "Imported Table"))

                    result["message"] = "Package PinCabOS détecté — import direct par manifest, analyse VPSdb ignorée."

                    # Nettoyage du batch upload après import manifest.
                    try:
                        uploads_root = Path("/home/pinball/Downloads").resolve()
                        batch_real = Path(batch_dir).resolve()
                        if batch_real.exists() and uploads_root in batch_real.parents:
                            shutil.rmtree(batch_real)
                    except Exception as e:
                        result.setdefault("skipped", [])
                        result["skipped"].append(f"WARNING cleanup upload batch: {e}")

                    return pincabos_manifest_import_result_page(result)

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            try:
                log_dir = Path("/opt/pincabos/logs")
                log_dir.mkdir(parents=True, exist_ok=True)
                log_file = log_dir / "import-manifest-error.log"
                with log_file.open("a", encoding="utf-8") as lf:
                    lf.write("\n=== IMPORT_MANIFEST_TRACEBACK ===\n")
                    lf.write(f"archive_path={archive_path}\n")
                    lf.write(f"batch_dir={batch_dir}\n")
                    lf.write(tb)
                    lf.write("\n")
            except Exception:
                pass

            return page("Import PinCabOS", f"""
<div class="card">
  <h2>Import PinCabOS impossible</h2>
  <p class="bad">Package PinCabOS détecté, mais erreur pendant l’import manifest.</p>
  <pre>{esc(str(e))}</pre>
  <p class="warn">Traceback complet écrit dans <code>/opt/pincabos/logs/import-manifest-error.log</code></p>
  <p><a class="button" href="/tools">Retour aux outils</a></p>
</div>
""")

    return None


@app.route("/tools/import-table/manifest-conflict", methods=["POST"])
def tools_import_table_manifest_conflict():
    batch_dir = Path(request.form.get("batch_dir", "")).resolve()
    archive_path = Path(request.form.get("archive_path", "")).resolve()
    action = request.form.get("conflict_action", "").strip().lower()
    new_table_name = request.form.get("new_table_name", "").strip()

    uploads_root = Path("/home/pinball/Downloads").resolve()

    if not batch_dir.exists() or uploads_root not in batch_dir.parents:
        return page("Import PinCabOS", """
<div class="card">
  <h2>Import impossible</h2>
  <p class="bad">Batch d’import invalide ou expiré.</p>
  <p><a class="button" href="/tools">Retour aux outils</a></p>
</div>
""")

    if not archive_path.exists() or batch_dir not in archive_path.parents:
        return page("Import PinCabOS", """
<div class="card">
  <h2>Import impossible</h2>
  <p class="bad">Package d’import invalide.</p>
  <p><a class="button" href="/tools">Retour aux outils</a></p>
</div>
""")

    if action not in ["replace", "rename"]:
        return page("Import PinCabOS", """
<div class="card">
  <h2>Import impossible</h2>
  <p class="bad">Action de conflit invalide.</p>
  <p><a class="button" href="/tools">Retour aux outils</a></p>
</div>
""")

    table_folder, _manifest_preview = pincabos_manifest_table_folder_from_archive(archive_path)
    if not table_folder:
        table_folder = "Imported Table"

    if action == "rename":
        if not new_table_name:
            return pincabos_manifest_import_conflict_page(batch_dir, archive_path, table_folder)
        final_table_name = pincabos_standard_table_folder_name(new_table_name) or table_folder
    else:
        final_table_name = table_folder

    try:
        with tempfile.TemporaryDirectory(prefix="pincabos-conflict-import-") as td:
            extract_dir = Path(td) / "extract"
            extract_dir.mkdir(parents=True, exist_ok=True)

            r7 = subprocess.run(
                ["7z", "x", "-y", f"-o{str(extract_dir)}", str(archive_path)],
                capture_output=True,
                text=True,
                timeout=1800,
                check=False,
            )

            if r7.returncode != 0:
                raise RuntimeError((r7.stdout + "\\n" + r7.stderr).strip())

            result = pincabos_import_from_manifest_dir(
                extract_dir,
                table_folder_override=final_table_name,
                overwrite_existing=True,
            )

        if result:
            if action == "replace":
                result["message"] = "Package PinCabOS importé en remplaçant la table existante."
            else:
                result["message"] = f"Package PinCabOS importé sous le nouveau nom: {final_table_name}"

            try:
                if batch_dir.exists() and uploads_root in batch_dir.parents:
                    shutil.rmtree(batch_dir)
            except Exception as e:
                result.setdefault("skipped", [])
                result["skipped"].append(f"WARNING cleanup upload batch: {e}")

            return pincabos_manifest_import_result_page(result)

    except Exception as e:
        return page("Import PinCabOS", f"""
<div class="card">
  <h2>Import impossible</h2>
  <p class="bad">Erreur pendant le traitement du conflit.</p>
  <pre>{esc(str(e))}</pre>
  <p><a class="button" href="/tools">Retour aux outils</a></p>
</div>
""")

    return page("Import PinCabOS", """
<div class="card">
  <h2>Import impossible</h2>
  <p class="bad">Aucun résultat d’import.</p>
  <p><a class="button" href="/tools">Retour aux outils</a></p>
</div>
""")


def pincabos_match_rom_value(m, detected=None):
    """
    Retourne la ROM depuis un match VPSdb/VPinFE si disponible.
    Fallback sur detected["rom"].
    """
    detected = detected or {}

    keys = [
        "rom", "Rom", "ROM",
        "romName", "RomName", "rom_name",
        "romFile", "RomFile", "rom_file",
        "bios", "Bios", "BIOS",
        "pinmame", "PinMAME",
    ]

    for k in keys:
        val = ""
        try:
            val = m.get(k, "")
        except Exception:
            val = ""
        val = str(val or "").strip()
        if val:
            val = Path(val).name
            if val.lower().endswith(".zip"):
                val = val[:-4]
            return val

    val = str(detected.get("rom", "") or "").strip()
    if val.lower().endswith(".zip"):
        val = val[:-4]
    return val


@app.route("/api/import/vpsdb-search")
def api_import_vpsdb_search():
    q = request.args.get("q", "").strip()
    rom = request.args.get("rom", "").strip()
    wanted_vpsid = request.args.get("vpsid", "").strip()

    if not q and not rom and not wanted_vpsid:
        return jsonify({"ok": False, "matches": [], "error": "Recherche vide"})

    # Si un VPSId est fourni, on l'ajoute comme recherche forte.
    search_q = wanted_vpsid if wanted_vpsid else q

    matches = pincabos_vpsdb_matches(search_q, rom)

    # Si recherche par VPSId ne retourne rien, fallback sur le nom.
    if wanted_vpsid and q:
        by_name = pincabos_vpsdb_matches(q, rom)
        seen = set()
        merged = []
        for m in matches + by_name:
            mid = str(m.get("id", "") or "")
            key = mid or str(m)
            if key in seen:
                continue
            seen.add(key)
            merged.append(m)
        matches = merged

    out = []
    for m in matches[:30]:
        title = str(m.get("title", "") or "")
        manufacturer = str(m.get("manufacturer", "") or "")
        year = str(m.get("year", "") or "")
        vpsid = str(m.get("id", "") or "")
        score = str(m.get("score", "") or "")
        assoc_rom = pincabos_match_rom_value(m, {"rom": rom})

        # Si VPSId demandé, boost visuel exact.
        if wanted_vpsid and vpsid.lower() == wanted_vpsid.lower():
            score = "1.0000"

        final_table_name = title
        if manufacturer and year:
            final_table_name = f"{title} ({manufacturer} {year})"

        out.append({
            "title": title,
            "manufacturer": manufacturer,
            "year": year,
            "id": vpsid,
            "vpsid": vpsid,
            "game_vpsid": str(m.get("game_vpsid", "") or ""),
            "parent_vpsid": str(m.get("parent_vpsid", "") or ""),
            "parent_version": str(m.get("parent_version", "") or ""),
            "version": str(m.get("version", "") or ""),
            "features": list(m.get("features", []) or []),
            "resource_type": str(m.get("resource_type", "") or ""),
            "score": score,
            "rom": assoc_rom,
            "final_table_name": final_table_name,
        })

    return jsonify({"ok": True, "matches": out})


@app.route("/tools/import-table/analyze", methods=["POST"])
def tools_import_table_analyze():
    uploads = request.files.getlist("packages")
    uploads = [u for u in uploads if u and u.filename]

    # PINCABOS_SMART_IMPORT_REAL_RECEIVE_GUARD_V1
    expected_count_raw = str(
        request.form.get("expected_count", "") or ""
    ).strip()

    expected_count = 0

    if expected_count_raw:
        try:
            expected_count = max(
                0,
                int(expected_count_raw),
            )
        except (TypeError, ValueError):
            expected_count = 0

    if expected_count and expected_count != len(uploads):
        return page("Outils", f"""
<div class="card">
  <h2>Analyse Smart Import annulée</h2>

  <p class="bad">
    La carte affichait {expected_count} fichier(s),
    mais le serveur en a reçu {len(uploads)}.
  </p>

  <p>
    Aucun import incomplet n’a été analysé.
  </p>

  <p>
    <a class="button" href="/tools/import-table">
      Retour Smart Import
    </a>
  </p>
</div>
""")

    try:
        submitted_vpsids = json.loads(
            request.form.get("file_vpsids_json", "[]")
            or "[]"
        )

        if not isinstance(submitted_vpsids, list):
            submitted_vpsids = []

    except Exception:
        submitted_vpsids = []

    submitted_vpsids = [
        str(value or "").strip()
        for value in submitted_vpsids
    ]

    if len(submitted_vpsids) != len(uploads):
        return page("Outils", """
<div class="card">
  <h2>Analyse Smart Import annulée</h2>
  <p class="bad">La liste des VPS-ID ne correspond pas aux fichiers reçus.</p>
  <p>Aucun fichier n’a été installé.</p>
  <p><a class="button" href="/tools/import-table">Retour Smart Import</a></p>
</div>
""")

    any_vpsids_present = any(submitted_vpsids)
    all_vpsids_present = bool(uploads) and all(submitted_vpsids)

    try:
        resolved_resources = [
            (
                pincabos_smart_import_exact_resource(vpsid)
                if vpsid
                else None
            )
            for vpsid in submitted_vpsids
        ]
    except Exception as exc:
        return page("Outils", f"""
<div class="card">
  <h2>Analyse Smart Import annulée</h2>
  <p class="bad">{html.escape(str(exc))}</p>
  <p>La base VPSDB n’a pas validé tous les fichiers. Aucun fichier n’a été installé.</p>
  <p><a class="button" href="/tools/import-table">Retour Smart Import</a></p>
</div>
""")

    game_vpsids = {
        str(resource.get("game_vpsid", "") or "").strip()
        for resource in resolved_resources
        if resource
        and str(resource.get("game_vpsid", "") or "").strip()
    }

    if len(game_vpsids) > 1 or (
        any_vpsids_present and len(game_vpsids) != 1
    ):
        detail = ", ".join(sorted(game_vpsids)) or "aucun"
        return page("Outils", f"""
<div class="card">
  <h2>Analyse Smart Import annulée</h2>
  <p class="bad">Les VPS-ID ne pointent pas tous vers la même table.</p>
  <p>Jeux VPSDB détectés : <code>{html.escape(detail)}</code></p>
  <p>Aucun fichier n’a été installé.</p>
  <p><a class="button" href="/tools/import-table">Retour Smart Import</a></p>
</div>
""")

    if not uploads:
        return page("Outils", """
<div class="card">
  <h2>Analyse impossible</h2>
  <p class="bad">Aucun fichier reçu.</p>
  <p><a class="button" href="/tools">Retour Outils</a></p>
</div>
""")

    job_id = pincabos_import_safe_job_id()
    batch_dir = Path("/home/pinball/Downloads") / f"batch-{job_id}"
    batch_dir.mkdir(parents=True, exist_ok=True)

    # PINCABOS_SMART_IMPORT_CLIENT_MTIME_V1
    # Le mtime temporaire serveur n'est jamais une preuve
    # de fraîcheur. File.lastModified vient du navigateur.
    try:
        client_mtimes = json.loads(
            request.form.get(
                "file_mtimes_json",
                "[]",
            )
            or "[]"
        )

        if not isinstance(
            client_mtimes,
            list,
        ):
            client_mtimes = []

    except Exception:
        client_mtimes = []

    if len(client_mtimes) != len(uploads):
        # JS ancien/cache:
        # date inconnue -> SHA-256 côté importeur.
        client_mtimes = [0] * len(uploads)

    saved = []
    resource_rows = []
    stored_names = set()

    for upload_index, upload in enumerate(uploads):
        filename = secure_filename(
            upload.filename
        )

        if not filename:
            shutil.rmtree(batch_dir, ignore_errors=True)
            return page("Outils", """
<div class="card">
  <h2>Analyse Smart Import annulée</h2>
  <p class="bad">Un nom de fichier est invalide après sécurisation.</p>
  <p>Aucun fichier n’a été installé.</p>
  <p><a class="button" href="/tools/import-table">Retour Smart Import</a></p>
</div>
""")

        filename_key = filename.casefold()

        if filename_key in stored_names:
            shutil.rmtree(batch_dir, ignore_errors=True)
            return page("Outils", f"""
<div class="card">
  <h2>Analyse Smart Import annulée</h2>
  <p class="bad">Deux fichiers portent le même nom sécurisé : {html.escape(filename)}</p>
  <p>Renomme un des fichiers pour éviter tout écrasement temporaire.</p>
  <p><a class="button" href="/tools/import-table">Retour Smart Import</a></p>
</div>
""")

        stored_names.add(filename_key)

        dest = batch_dir / filename
        upload.save(dest)

        try:
            mtime_ms = float(
                client_mtimes[
                    upload_index
                ]
                or 0
            )

            if mtime_ms > 0:
                mtime_seconds = (
                    mtime_ms / 1000.0
                )

                os.utime(
                    dest,
                    (
                        mtime_seconds,
                        mtime_seconds,
                    ),
                )

            else:
                os.utime(
                    dest,
                    (0, 0),
                )

        except Exception:
            try:
                os.utime(
                    dest,
                    (0, 0),
                )
            except Exception:
                pass

        saved.append(str(dest))

        # Aucun VPS-ID fourni dans le lot: le moteur historique reste la
        # source de vérité (VPX anchor, détection et sélection manuelle).
        if not any_vpsids_present:
            continue

        resolved_resource = resolved_resources[upload_index]
        archive_members = (
            pincabos_list_archive_files(dest)
            if dest.suffix.lower() in {".zip", ".rar", ".7z", ".pincabos"}
            else []
        )
        contains_vpu_patch = (
            dest.suffix.lower() == ".dif"
            or any(
                str(member).lower().endswith(".dif")
                for member in archive_members
            )
        )
        contains_vpx = (
            dest.suffix.lower() == ".vpx"
            or any(
                str(member).lower().endswith(".vpx")
                for member in archive_members
            )
        )

        # Un .dif reste l'exception stricte: son VPS-ID exact est nécessaire
        # afin de conserver parentId + parent_version et la sécurité vpxtool.
        if contains_vpu_patch and not resolved_resource:
            shutil.rmtree(batch_dir, ignore_errors=True)
            return page("Outils", f"""
<div class="card">
  <h2>Analyse Smart Import annulée</h2>
  <p class="bad">Le fichier {html.escape(filename)} contient un patch VPU Remix .dif. Son VPS-ID exact est requis pour valider le parent et sa version.</p>
  <p>Les autres fichiers peuvent rester sans VPS-ID.</p>
  <p>Aucun fichier n’a été installé.</p>
  <p><a class="button" href="/tools/import-table">Retour Smart Import</a></p>
</div>
""")

        if resolved_resource:
            resource = dict(resolved_resource)
        else:
            resource = {
                "vpsid": "",
                "game_vpsid": next(iter(game_vpsids)),
                "resource_type": "unresolved",
                "resource_key": "",
                "association": "inferred_game",
            }

        if (
            contains_vpu_patch
            and resource.get("resource_type") != "tableFile"
        ):
            shutil.rmtree(batch_dir, ignore_errors=True)
            return page("Outils", f"""
<div class="card">
  <h2>Analyse Smart Import annulée</h2>
  <p class="bad">Le fichier {html.escape(filename)} contient un patch .dif, mais son VPS-ID n’est pas un tableFile.</p>
  <p>Aucun fichier n’a été installé.</p>
  <p><a class="button" href="/tools/import-table">Retour Smart Import</a></p>
</div>
""")

        resource.update({
            "original_name": str(upload.filename or ""),
            "stored_name": filename,
            "sha256": pincabos_smart_import_file_sha256(dest),
            "size": dest.stat().st_size,
            "client_mtime_ms": client_mtimes[upload_index],
            "contains_vpu_patch": contains_vpu_patch,
            "contains_vpx": contains_vpx,
        })
        resource_rows.append(resource)

    if not any_vpsids_present:
        if request.headers.get("X-PCOS-Async") == "1":
            return jsonify({
                "ok": True,
                "next": "/tools/import-table/analyze-run?batch=" + batch_dir.name,
            })

        return _pcos_smart_analyze_render(batch_dir, saved)

    patch_resources = [
        resource
        for resource in resource_rows
        if resource.get("contains_vpu_patch")
    ]

    if len(patch_resources) > 1:
        shutil.rmtree(batch_dir, ignore_errors=True)
        return page("Outils", """
<div class="card">
  <h2>Analyse Smart Import annulée</h2>
  <p class="bad">Un seul patch VPU Remix .dif est permis par import.</p>
  <p>Aucun fichier n’a été installé.</p>
  <p><a class="button" href="/tools/import-table">Retour Smart Import</a></p>
</div>
""")

    vpx_resources = [
        resource
        for resource in resource_rows
        if resource.get("contains_vpx")
    ]

    if len(vpx_resources) > 1:
        shutil.rmtree(batch_dir, ignore_errors=True)
        return page("Outils", """
<div class="card">
  <h2>Analyse Smart Import annulée</h2>
  <p class="bad">Plusieurs sources VPX sont présentes dans le même lot. Smart Import refuse de choisir arbitrairement une table principale.</p>
  <p>Conserve un seul VPX principal dans ce lot, ou importe les variantes séparément.</p>
  <p>Aucun fichier n’a été installé.</p>
  <p><a class="button" href="/tools/import-table">Retour Smart Import</a></p>
</div>
""")

    table_resources = [
        resource
        for resource in resource_rows
        if resource.get("resource_type") == "tableFile"
    ]

    primary_table = patch_resources[0] if patch_resources else None

    if primary_table is None and len(table_resources) == 1:
        primary_table = table_resources[0]

    if primary_table is None and len(table_resources) > 1:
        table_ids = {
            str(resource.get("vpsid", "") or "").strip().casefold()
            for resource in table_resources
        }
        children = [
            resource
            for resource in table_resources
            if str(resource.get("parent_vpsid", "") or "").strip().casefold()
            in table_ids
        ]

        if len(children) == 1:
            primary_table = children[0]
        else:
            shutil.rmtree(batch_dir, ignore_errors=True)
            return page("Outils", """
<div class="card">
  <h2>Analyse Smart Import annulée</h2>
  <p class="bad">Plusieurs tableFile VPSDB sont présents et la table principale est ambiguë.</p>
  <p>Aucun fichier n’a été installé.</p>
  <p><a class="button" href="/tools/import-table">Retour Smart Import</a></p>
</div>
""")

    first_resource = next(
        (
            resource
            for resource in resource_rows
            if str(resource.get("vpsid", "") or "").strip()
        ),
        resource_rows[0],
    )
    detected_rom = next((
        str(resource.get("version", "") or "").strip()
        for resource in resource_rows
        if resource.get("resource_type") == "romFile"
        and str(resource.get("version", "") or "").strip()
    ), "")

    resource_manifest = {
        "format": "PinCabOS Smart Import resources",
        "format_version": 2,
        "association_mode": (
            "complete_vpsid"
            if all_vpsids_present
            else "partial_vpsid"
        ),
        "game_vpsid": next(iter(game_vpsids)),
        "title": str(first_resource.get("title", "") or "").strip(),
        "manufacturer": str(first_resource.get("manufacturer", "") or "").strip(),
        "year": str(first_resource.get("year", "") or "").strip(),
        "final_table_name": str(first_resource.get("final_table_name", "") or "").strip(),
        "rom": detected_rom,
        "primary_table_vpsid": (
            str(primary_table.get("vpsid", "") or "").strip()
            if primary_table
            else ""
        ),
        "parent_vpsid": (
            str(primary_table.get("parent_vpsid", "") or "").strip()
            if primary_table
            else ""
        ),
        "parent_version": (
            str(primary_table.get("parent_version", "") or "").strip()
            if primary_table
            else ""
        ),
        "target_version": (
            str(primary_table.get("version", "") or "").strip()
            if primary_table
            else ""
        ),
        "resources": resource_rows,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    resource_manifest_path = (
        pincabos_smart_import_resource_manifest_path(batch_dir)
    )
    resource_manifest_tmp = resource_manifest_path.with_suffix(".tmp")
    resource_manifest_tmp.write_text(
        json.dumps(resource_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(resource_manifest_tmp, resource_manifest_path)

    if request.headers.get("X-PCOS-Async") == "1":
        return jsonify({
            "ok": True,
            "next": "/tools/import-table/analyze-run?batch=" + batch_dir.name,
        })

    return _pcos_smart_analyze_render(batch_dir, saved)


@app.route("/tools/import-table/analyze-run", methods=["GET"])
def tools_import_table_analyze_run():
    name = str(request.args.get("batch", "") or "")
    if not re.fullmatch(r"batch-[A-Za-z0-9-]+", name):
        return page("Outils", '<div class="card"><h2>Smart Import</h2><p class="bad">R\u00e9f\u00e9rence de batch invalide.</p><p><a class="button" href="/tools/import-table">Retour</a></p></div>')
    batch_dir = Path("/home/pinball/Downloads") / name
    if not batch_dir.is_dir():
        return page("Outils", '<div class="card"><h2>Smart Import</h2><p class="bad">Batch introuvable ou expir\u00e9.</p><p><a class="button" href="/tools/import-table">Retour</a></p></div>')
    saved = sorted(
        str(p)
        for p in batch_dir.iterdir()
        if p.is_file()
        and p.name != PINCABOS_SMART_IMPORT_RESOURCE_MANIFEST
    )
    return _pcos_smart_analyze_render(batch_dir, saved)


def _pcos_smart_analyze_render(batch_dir, saved):
    manifest_response = pincabos_try_manifest_import_from_saved_batch(batch_dir)
    if manifest_response is not None:
        return manifest_response

    try:
        resource_manifest = (
            pincabos_smart_import_load_resource_manifest(batch_dir)
        )
    except Exception as exc:
        return page("Outils", f"""
<div class="card">
  <h2>Analyse Smart Import annulée</h2>
  <p class="bad">{html.escape(str(exc))}</p>
  <p><a class="button" href="/tools/import-table">Retour Smart Import</a></p>
</div>
""")

    detected = pincabos_detect_batch(batch_dir)

    if resource_manifest:
        detected["table_name"] = str(
            resource_manifest.get("final_table_name", "")
            or resource_manifest.get("title", "")
            or detected.get("table_name", "")
        ).strip()

        if resource_manifest.get("rom"):
            detected["rom"] = str(resource_manifest.get("rom") or "").strip()

    # Validation directe des fichiers réellement reçus.
    received_paths = [
        Path(file_path)
        for file_path in saved
    ]

    direct_vpx = [
        file_path
        for file_path in received_paths
        if file_path.suffix.lower() == ".vpx"
    ]

    direct_b2s = [
        file_path
        for file_path in received_paths
        if file_path.name.lower().endswith(".directb2s")
    ]

    direct_pov = [
        file_path
        for file_path in received_paths
        if file_path.suffix.lower() == ".pov"
    ]

    direct_ini = [
        file_path
        for file_path in received_paths
        if file_path.suffix.lower() == ".ini"
    ]

    direct_vbs = [
        file_path
        for file_path in received_paths
        if file_path.suffix.lower() == ".vbs"
    ]

    detected_name = str(
        detected.get("table_name", "") or ""
    ).strip()

    false_batch_name = (
        detected_name == batch_dir.name
        or detected_name.lower().startswith("batch-")
    )

    if direct_vpx:
        detected["main_vpx"] = (
            detected.get("main_vpx")
            or direct_vpx[0].name
        )

        if not detected_name or false_batch_name:
            detected["table_name"] = direct_vpx[0].stem

    elif false_batch_name:
        detected["table_name"] = ""

    if direct_b2s:
        detected["has_b2s"] = True

    if direct_pov:
        detected["has_pov"] = True

    if direct_ini:
        detected["has_ini"] = True

    if direct_vbs:
        detected["has_vbs"] = True

    matches = pincabos_vpsdb_matches(
        detected.get("table_name", ""),
        detected.get("rom", ""),
    )

    if resource_manifest:
        matches = []

    # Le nom d'un .dif ne prouve pas quel tableFile VPSDB il représente.
    # Une association générique au jeu perdrait parentId et pourrait choisir
    # une mauvaise version source. Pour un patch, l'utilisateur doit donc
    # sélectionner le VPSId exact du mod dans la recherche dédiée.
    if detected.get("has_vpu_patch"):
        matches = []

    options = ""
    for m in matches[:10]:
        title = str(m.get("title", ""))
        manufacturer = str(m.get("manufacturer", ""))
        year = str(m.get("year", ""))
        vpsid = str(m.get("id", ""))
        score = str(m.get("score", ""))

        final_table_name = title
        if manufacturer and year:
            final_table_name = f"{title} ({manufacturer} {year})"

        assoc_rom = pincabos_match_rom_value(m, detected)

        value = html.escape(json.dumps({
            "mode": "vpsdb",
            "title": title,
            "manufacturer": manufacturer,
            "year": year,
            "vpsid": vpsid,
            "game_vpsid": str(m.get("game_vpsid", "") or ""),
            "parent_vpsid": str(m.get("parent_vpsid", "") or ""),
            "parent_version": str(m.get("parent_version", "") or ""),
            "version": str(m.get("version", "") or ""),
            "features": list(m.get("features", []) or []),
            "resource_type": str(m.get("resource_type", "") or ""),
            "rom": assoc_rom,
            "final_table_name": final_table_name,
        }, ensure_ascii=False))

        version_label = str(m.get("version", "") or "").strip()
        parent_label = str(m.get("parent_vpsid", "") or "").strip()
        label = html.escape(
            f"{title} — {manufacturer} — {year} — VPSId {vpsid}"
            + (f" — version {version_label}" if version_label else "")
            + (f" — parent {parent_label}" if parent_label else "")
            + f" — score {score}"
        )
        options += f'<option value="{value}">{label}</option>\\n'

    if not options.strip():
        if detected.get("has_vpu_patch"):
            options = (
                '<option value="">Patch .dif : recherchez le VPSId exact du mod</option>'
            )
        else:
            options = '<option value="">Aucune association auto-détectée VPSdb</option>'

    # PINCABOS_IMPORT_TECH_GO_COLORS_V1
    technical_items = [
        (
            "Table détectée",
            bool(detected.get("table_name")),
            detected.get("table_name", ""),
        ),
        (
            "Fichier VPX principal",
            bool(detected.get("main_vpx")),
            detected.get("main_vpx", ""),
        ),
        (
            "Patch VPU Remix (.dif)",
            bool(detected.get("has_vpu_patch")),
            detected.get("vpu_patch_file", ""),
        ),
        (
            "ROM détectée",
            bool(detected.get("rom")),
            detected.get("rom", ""),
        ),
        ("Archive ROM", bool(detected.get("has_rom")), ""),
        ("Backglass B2S", bool(detected.get("has_b2s")), ""),
        ("Fichier POV", bool(detected.get("has_pov")), ""),
        ("Fichier INI", bool(detected.get("has_ini")), ""),
        ("Script VBS", bool(detected.get("has_vbs")), ""),
        ("AltSound", bool(detected.get("has_altsound")), ""),
        ("AltColor / Serum", bool(detected.get("has_altcolor")), ""),
        ("PuP-Pack", bool(detected.get("has_puppack")), ""),
        ("UltraDMD", bool(detected.get("has_ultradmd")), ""),
    ]

    technical_rows = []

    for label, present, value in technical_items:
        status_html = (
            '<span class="pco-import-status '
            'pco-import-status-go">[✓] GO</span>'
            if present
            else
            '<span class="pco-import-status '
            'pco-import-status-off">[ ] NON DÉTECTÉ</span>'
        )

        value_html = (
            f'<span class="pco-import-tech-value">'
            f'{html.escape(str(value))}</span>'
            if value
            else
            '<span class="pco-import-tech-value '
            'pco-import-tech-empty">—</span>'
        )

        technical_rows.append(
            '<div class="pco-import-tech-row">'
            f'<span class="pco-import-tech-label">'
            f'{html.escape(str(label))}</span>'
            f'{status_html}'
            f'{value_html}'
            '</div>'
        )

    detected_html = "".join(technical_rows)

    file_rows = []

    resources_by_name = {
        str(resource.get("stored_name", "") or ""): resource
        for resource in resource_manifest.get("resources", [])
        if isinstance(resource, dict)
    }

    for file_path in saved:
        file_name = Path(file_path).name
        resource = resources_by_name.get(file_name, {})
        resource_detail = ""

        if resource:
            resource_vpsid = str(resource.get("vpsid", "") or "").strip()
            if resource_vpsid:
                detail_parts = [
                    f"VPS-ID {resource_vpsid}",
                    str(resource.get("resource_type", "") or ""),
                ]
            else:
                detail_parts = [
                    "VPS-ID non fourni",
                    "routage par ancre VPX/VPSDB",
                ]
            version = str(resource.get("version", "") or "").strip()
            if version:
                detail_parts.append(f"version {version}")

            resource_detail = (
                '<small class="pco-import-file-resource">'
                + html.escape(" · ".join(filter(None, detail_parts)))
                + "</small>"
            )

        file_rows.append(
            '<div class="pco-import-file-row">'
            '<span class="pco-import-file-go">[✓] GO</span>'
            f'<span class="pco-import-file-path">'
            f'<strong>{html.escape(file_name)}</strong>'
            f'{resource_detail}</span>'
            '</div>'
        )

    files_html = "".join(file_rows) or (
        '<div class="pco-import-file-row">'
        '<span class="pco-import-status '
        'pco-import-status-off">[ ] AUCUN</span>'
        '<span class="pco-import-file-path">'
        'Aucun fichier détecté</span>'
        '</div>'
    )

    default_title = html.escape(detected.get("table_name", ""))
    default_rom = html.escape(detected.get("rom", ""))
    legacy_association_style = (
        "display:none;"
        if resource_manifest
        else ""
    )
    resource_install_html = ""
    existing_target_html = ""

    partial_resource_manifest = (
        isinstance(resource_manifest, dict)
        and resource_manifest.get("association_mode") == "partial_vpsid"
    )
    needs_existing_target = (
        not detected.get("main_vpx")
        and not detected.get("has_vpu_patch")
        and (
            not resource_manifest
            or partial_resource_manifest
        )
    )

    if needs_existing_target:
        table_options = []

        try:
            tables_root = Path(pincabos_vpx_tables_dir()).resolve()
            candidates = sorted(
                tables_root.iterdir(),
                key=lambda item: item.name.casefold(),
            )

            for candidate in candidates:
                if (
                    not candidate.is_dir()
                    or candidate.is_symlink()
                    or candidate.name.startswith(".")
                ):
                    continue

                installed_vpxs = [
                    item
                    for item in candidate.glob("*.vpx")
                    if item.is_file() and not item.is_symlink()
                ]

                if len(installed_vpxs) != 1:
                    continue

                value = html.escape(candidate.name, quote=True)
                table_options.append(
                    f'<option value="{value}">{value}</option>'
                )

        except Exception:
            table_options = []

        if table_options:
            options_html = (
                '<option value="">Choisir une table installée</option>'
                + "".join(table_options)
            )

            existing_target_html = f"""
<div class="card" style="margin-top:20px; border-color:rgba(255,176,0,.62);">
  <h2>Choisir la table de destination</h2>
  <p>
    Smart Import ne peut pas associer tout ce lot avec certitude.
    Choisis la table installée qui doit le recevoir. Les VPS-ID déjà fournis,
    le routage et le renommage Smart Import existants seront conservés.
  </p>
  <form action="/tools/import-table/install" method="post"
        onsubmit="document.getElementById('installSpinnerExisting').style.display='block';">
    <input type="hidden" name="batch_dir" value="{html.escape(str(batch_dir))}">
    <input type="hidden" name="import_mode" value="existing">
    <label>Table de destination</label><br>
    <select name="existing_table" required style="width:95%; padding:8px; margin:8px 0;">
      {options_html}
    </select><br>
    <button class="button" type="submit">Installer dans cette table</button>
    <div id="installSpinnerExisting" class="card" style="display:none; margin-top:14px;">
      <h3>Installation en cours...</h3>
      <p>Le VPX installé est conservé; Smart Import route les fichiers reçus.</p>
    </div>
  </form>
</div>
"""
        else:
            existing_target_html = """
<div class="card" style="margin-top:20px;">
  <h2>Choisir la table de destination</h2>
  <p class="warn">Aucune table installée avec un VPX unique et fiable n’est disponible.</p>
</div>
"""

    if resource_manifest and not needs_existing_target:
        resource_count = len(resource_manifest.get("resources", []))
        provided_count = sum(
            1
            for resource in resource_manifest.get("resources", [])
            if isinstance(resource, dict)
            and str(resource.get("vpsid", "") or "").strip()
        )
        game_vpsid = html.escape(
            str(resource_manifest.get("game_vpsid", "") or "")
        )
        target_name = html.escape(
            str(
                resource_manifest.get("final_table_name", "")
                or resource_manifest.get("title", "")
                or ""
            )
        )
        if partial_resource_manifest:
            association_title = "Association mixte VPSDB + ancre Smart Import"
            association_summary = (
                f"{provided_count}/{resource_count} VPS-ID fourni(s) et validé(s) pour "
                f"<strong>{target_name}</strong> — jeu VPSDB <code>{game_vpsid}</code>."
            )
            routing_text = (
                "Les VPS-ID fournis gardent la priorité. Les fichiers sans ID "
                "restent liés au même jeu et sont classés par le moteur Smart Import."
            )
        else:
            association_title = "Association VPSDB validée par fichier"
            association_summary = (
                f"{resource_count} fichier(s) validé(s) pour "
                f"<strong>{target_name}</strong> — jeu VPSDB <code>{game_vpsid}</code>."
            )
            routing_text = (
                "PinCabOS utilisera le type VPSDB de chaque ID pour viser la table "
                "et conservera ces ressources dans le manifeste de la table."
            )

        resource_install_html = f"""
<div class="card" style="margin-top:20px; border-color:rgba(69,229,139,.55);">
  <h2>{association_title}</h2>
  <p class="ok">{association_summary}</p>
  <p>{routing_text}</p>
  <form action="/tools/import-table/install" method="post"
        onsubmit="document.getElementById('installSpinnerResources').style.display='block';">
    <input type="hidden" name="batch_dir" value="{html.escape(str(batch_dir))}">
    <input type="hidden" name="import_mode" value="resources">
    <button class="button" type="submit">Installer le lot analysé</button>
    <div id="installSpinnerResources" class="card" style="display:none; margin-top:14px;">
      <h3>Installation en cours...</h3>
      <p>Routage Smart Import, transaction, manifeste et validation.</p>
    </div>
  </form>
</div>
"""

    body = f"""
<style>
  .pco-import-files,
  .pco-import-details {{
    background:rgba(3,1,7,.94);
    border:1px solid rgba(255,166,0,.78);
    border-radius:12px;
    overflow:hidden;
    box-shadow:inset 0 0 0 1px rgba(255,255,255,.02);
  }}

  .pco-import-file-row,
  .pco-import-tech-row {{
    display:grid;
    align-items:center;
    gap:14px;
    padding:10px 14px;
    border-bottom:1px solid rgba(255,255,255,.075);
  }}

  .pco-import-file-row:last-child,
  .pco-import-tech-row:last-child {{
    border-bottom:0;
  }}

  .pco-import-file-row {{
    grid-template-columns:92px minmax(0,1fr);
  }}

  .pco-import-tech-row {{
    grid-template-columns:minmax(170px,230px) 155px minmax(0,1fr);
  }}

  .pco-import-status,
  .pco-import-file-go {{
    font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
    font-weight:900;
    letter-spacing:.03em;
    white-space:nowrap;
  }}

  .pco-import-status-go,
  .pco-import-file-go {{
    color:#45e58b;
    text-shadow:0 0 12px rgba(69,229,139,.28);
  }}

  .pco-import-status-off {{
    color:#858997;
  }}

  .pco-import-tech-label {{
    color:#ffb300;
    font-weight:800;
  }}

  .pco-import-tech-value,
  .pco-import-file-path {{
    min-width:0;
    color:#f2f3f5;
    overflow-wrap:anywhere;
    word-break:break-word;
    font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  }}

  .pco-import-tech-empty {{
    color:#686d79;
  }}

  .pco-import-file-path strong,
  .pco-import-file-resource {{
    display:block;
  }}

  .pco-import-file-resource {{
    margin-top:4px;
    color:#ffb04a;
    font-size:12px;
  }}

  @media (max-width:900px) {{
    .pco-import-tech-row {{
      grid-template-columns:1fr;
      gap:5px;
    }}

    .pco-import-file-row {{
      grid-template-columns:1fr;
      gap:5px;
    }}
  }}
</style>

<div class="card">
  <h2>Analyse Smart Import terminée</h2>

  <h3>Table détectée</h3>
  <p><strong>{html.escape(detected.get("table_name", ""))}</strong></p>

  <h3>ROM détectée</h3>
  <p><strong>{html.escape(detected.get("rom", "")) or "Aucune ROM détectée"}</strong></p>

  <h3>Fichiers détectés</h3>
  <div class="pco-import-files">{files_html}</div>

  <h3>Détails techniques</h3>
  <div class="pco-import-details">{detected_html}</div>
</div>

{resource_install_html}

{existing_target_html}

<div class="card" style="margin-top:20px;{legacy_association_style}">
  <h2>Association VPinFE / VPSdb</h2>

  <form action="/tools/import-table/install" method="post" onsubmit="document.getElementById('installSpinner').style.display='block';">
    <input type="hidden" name="batch_dir" value="{html.escape(str(batch_dir))}">
    <input type="hidden" name="import_mode" id="importMode" value="auto">

    <div class="card" style="margin-top:12px; border-color:rgba(255,122,0,.45);">
      <h3>1. Détection automatique VPSdb</h3>
      <p>PinCabOS propose ici les résultats VPSdb trouvés automatiquement.</p>

      <label>Choix auto-détecté VPSdb</label><br>
      <select name="association" id="autoAssociationSelect" style="width:95%; padding:8px; margin:8px 0;">
        {options}
      </select><br>

      <button class="button" type="submit" onclick="document.getElementById('importMode').value='auto';">
        Importer ce choix auto-détecté
      </button>
    </div>

    <div class="card" style="margin-top:20px; border-color:rgba(95,42,145,.55);">
      <h3>2. Recherche manuelle dans VPSdb</h3>
      <p>Recherche par nom ou par VPSId. Ensuite sélectionne le bon résultat et importe-le.</p>

      <label>Nom recherché</label><br>
      <input id="vpsdbSearchQuery" value="{default_title}" placeholder="Exemple : The Leprechaun King" style="width:90%; padding:8px;"><br><br>

      <label>VPSId optionnel</label><br>
      <input id="vpsdbSearchId" value="" placeholder="Exemple : VAx9weFV" style="width:90%; padding:8px;"><br><br>

      <button class="button secondary" type="button" id="vpsdbSearchButton" onclick="window.pincabosVpsdbSearch && window.pincabosVpsdbSearch();">
        Rechercher VPSdb
      </button>
      <span id="vpsdbSearchSpinner" style="display:none; margin-left:10px;">🔄</span>
      <span id="vpsdbSearchStatus" style="margin-left:10px; opacity:.85;"></span>

      <br><br>
      <label>Résultat de recherche VPSdb</label><br>
      <select name="search_association" id="searchAssociationSelect" style="width:95%; padding:8px; margin:8px 0;">
        <option value="">Aucun résultat de recherche sélectionné</option>
      </select><br>

      <button class="button" type="submit" onclick="document.getElementById('importMode').value='search';">
        Importer le résultat recherché
      </button>
    </div>

    <div class="card" style="margin-top:20px; border-color:rgba(255,122,0,.55); background:rgba(255,122,0,.06);">
      <h3>3. Import manuel complet</h3>
      <p>
        Si rien ne correspond dans VPSdb, remplis ces champs et importe la table avec tes informations.
        Exemple : <code>Demo Table (PinCabOS 2026)</code>.
      </p>

      <label>Nom de table VPinFE</label><br>
      <input name="manual_title" id="manualTitleInput" value="{default_title}" style="width:90%; padding:8px;" placeholder="Exemple : Demo Table (PinCabOS 2026)"><br><br>

      <label>Manufacturier</label><br>
      <input name="manual_manufacturer" id="manualManufacturerInput" value="" placeholder="Exemple : PinCabOS, Williams, Original, Stern" style="width:90%; padding:8px;"><br><br>

      <label>Année</label><br>
      <input name="manual_year" id="manualYearInput" value="" placeholder="Exemple : 2026" style="width:90%; padding:8px;"><br><br>

      <label>ROM</label><br>
      <input name="manual_rom" id="manualRomInput" value="{default_rom}" placeholder="Exemple : hurr_l2 ou laisser vide si aucune ROM" style="width:90%; padding:8px;"><br><br>

      <button class="button" type="submit" onclick="document.getElementById('importMode').value='manual';">
        Importer manuellement
      </button>
    </div>

    <script>
      (function() {{
        window.pincabosVpsdbSearch = async function() {{
          const searchQ = document.getElementById("vpsdbSearchQuery");
          const searchId = document.getElementById("vpsdbSearchId");
          const searchStatus = document.getElementById("vpsdbSearchStatus");
          const spinner = document.getElementById("vpsdbSearchSpinner");
          const searchSelect = document.getElementById("searchAssociationSelect");

          if (!searchSelect) {{
            alert("Erreur: champ résultat VPSdb introuvable.");
            return;
          }}

          const q = encodeURIComponent(searchQ ? searchQ.value.trim() : "");
          const vpsid = encodeURIComponent(searchId ? searchId.value.trim() : "");

          if (!q && !vpsid) {{
            searchSelect.innerHTML = '<option value="">Entre un nom ou un VPSId</option>';
            if (searchStatus) searchStatus.textContent = "Recherche vide";
            return;
          }}

          if (spinner) spinner.style.display = "inline-block";
          if (searchStatus) searchStatus.textContent = "Recherche en cours...";
          searchSelect.innerHTML = '<option value="">Recherche en cours...</option>';

          try {{
            const url = "/api/import/vpsdb-search?q=" + q + "&vpsid=" + vpsid + "&_=" + Date.now();
            const resp = await fetch(url, {{
              method: "GET",
              cache: "no-store",
              headers: {{ "Accept": "application/json" }}
            }});

            const raw = await resp.text();
            const data = JSON.parse(raw);

            searchSelect.innerHTML = "";

            if (!data.ok || !data.matches || data.matches.length === 0) {{
              searchSelect.innerHTML = '<option value="">Aucun résultat VPSdb trouvé</option>';
              if (searchStatus) searchStatus.textContent = "Aucun résultat";
              return;
            }}

            const empty = document.createElement("option");
            empty.value = "";
            empty.textContent = "Choisir un résultat de recherche VPSdb";
            searchSelect.appendChild(empty);

            data.matches.forEach(function(m) {{
              const opt = document.createElement("option");
              opt.value = JSON.stringify({{
                mode: "vpsdb",
                title: m.title || "",
                manufacturer: m.manufacturer || "",
                year: m.year || "",
                vpsid: m.id || "",
                game_vpsid: m.game_vpsid || "",
                parent_vpsid: m.parent_vpsid || "",
                parent_version: m.parent_version || "",
                version: m.version || "",
                features: m.features || [],
                resource_type: m.resource_type || "",
                rom: m.rom || "",
                final_table_name: m.final_table_name || ""
              }});

              opt.textContent =
                (m.title || "") + " — " +
                (m.manufacturer || "") + " — " +
                (m.year || "") + " — VPSId " +
                (m.id || "") +
                (m.version ? " — version " + m.version : "") +
                (m.parent_vpsid ? " — parent " + m.parent_vpsid : "") +
                " — score " +
                (m.score || "");

              searchSelect.appendChild(opt);
            }});

            if (searchStatus) searchStatus.textContent = data.matches.length + " résultat(s)";
          }} catch(e) {{
            searchSelect.innerHTML = '<option value="">Erreur recherche VPSdb</option>';
            if (searchStatus) searchStatus.textContent = "Erreur recherche";
            console.log("Erreur recherche VPSdb:", e);
          }} finally {{
            if (spinner) spinner.style.display = "none";
          }}
        }};
      }})();
    </script>

    <div id="installSpinner" class="card" style="display:none; margin-top:14px;">
      <h3>Installation en cours...</h3>
      <p>PinCabOS installe les fichiers, crée le .info compatible VPinFE et nettoie les temporaires.</p>
    </div>
  </form>

  <p style="margin-top:14px;"><a class="button secondary" href="/tools">Annuler</a></p>
</div>
"""
    return page("Outils", body)


def pincabos_safe_manifest_relpath(rel):
    rel = str(rel or "").replace("\\", "/").strip()
    if not rel:
        return None
    if rel.startswith("/") or rel.startswith("../") or "/../" in rel or rel == "..":
        return None
    return rel


def pincabos_manifest_dest_path(rel):
    """
    Destination import manifest PinCabOS v2:
    tout reste dans /opt/pincabos/tables/<table>/...
    Cette fonction garde un fallback pour les vieux manifests, mais évite
    les dossiers legacy globaux.
    """
    rel = pincabos_safe_manifest_relpath(rel)
    if not rel:
        return None

    parts = Path(rel).parts
    if not parts:
        return None

    # Manifest v2 exporte directement:
    # table/, media/, music/, roms/, pupvideos/, ...
    standard_dirs = {
        "table", "media", "music", "roms", "pupvideos", "altcolor",
        "altsound", "dmd", "b2s", "scripts", "config", "docs", "extras"
    }

    # La vraie table est déterminée dans pincabos_import_from_manifest_dir()
    # via PINCABOS_MANIFEST_IMPORT_TABLE_DIR.
    table_root = globals().get("PINCABOS_MANIFEST_IMPORT_TABLE_DIR", None)
    if table_root:
        table_root = Path(table_root)

        if parts[0] in standard_dirs:
            return table_root / rel

        # Vieux manifest avec Tables/<table>/...
        if len(parts) >= 3 and parts[0].lower() == "tables":
            return table_root / Path(*parts[2:])

        # Vieux manifest avec PupVideos/xxx, PinMAME/roms/xxx, etc.
        low0 = parts[0].lower()
        if low0 in ["pupvideos"]:
            return table_root / "pupvideos" / Path(*parts[1:])
        if low0 in ["ultradmd", "flexdmd"]:
            return table_root / "dmd" / Path(*parts[1:])
        if low0 == "pinmame" and len(parts) >= 2:
            low1 = parts[1].lower()
            if low1 == "roms":
                return table_root / "roms" / Path(*parts[2:])
            if low1 == "altcolor":
                return table_root / "altcolor" / Path(*parts[2:])
            if low1 == "altsound":
                return table_root / "altsound" / Path(*parts[2:])

        return table_root / "extras" / rel

    # Fallback ultra safe.
    return Path("/opt/pincabos/imported") / rel


def pincabos_find_manifest_root(extract_dir):
    extract_dir = Path(extract_dir)

    direct = extract_dir / "pincabos-export-manifest.json"
    if direct.exists():
        return extract_dir, direct

    matches = list(extract_dir.rglob("pincabos-export-manifest.json"))
    if not matches:
        return None, None

    manifest = matches[0]
    return manifest.parent, manifest


def pincabos_manifest_table_folder_from_archive(archive_path):
    """
    Lit le manifest d'un .PinCabOs/.zip/.7z/.rar et retourne le nom de table demandé.
    Retourne ("", "") si aucun manifest valide n'est trouvé.
    """
    archive_path = Path(archive_path)

    with tempfile.TemporaryDirectory(prefix="pincabos-manifest-preview-") as td:
        extract_dir = Path(td) / "extract"
        extract_dir.mkdir(parents=True, exist_ok=True)

        r7 = subprocess.run(
            ["7z", "x", "-y", f"-o{str(extract_dir)}", str(archive_path)],
            capture_output=True,
            text=True,
            timeout=1800,
            check=False,
        )

        if r7.returncode != 0:
            return "", ""

        root, manifest_path = pincabos_find_manifest_root(extract_dir)
        if not manifest_path:
            return "", ""

        try:
            manifest = json.loads(manifest_path.read_text(errors="replace"))
        except Exception:
            return "", str(manifest_path)

        if manifest.get("format") != "PinCabOS table export":
            return "", str(manifest_path)

        table_folder = str(manifest.get("table_folder") or "").strip()
        if not table_folder:
            table_folder = Path(root).name or "Imported Table"

        table_folder = pincabos_standard_table_folder_name(table_folder)
        return table_folder, str(manifest_path)


def pincabos_manifest_import_conflict_page(batch_dir, archive_path, table_folder):
    table_root = pincabos_vpx_tables_dir() / table_folder

    suggested = table_folder
    i = 2
    while (pincabos_vpx_tables_dir() / suggested).exists():
        suggested = f"{table_folder} ({i})"
        i += 1

    return page("Import PinCabOS", f"""
<div class="card">
  <h2>Table déjà présente</h2>
  <p class="warn">
    Le package <code>.PinCabOs</code> contient la table
    <strong>{esc(table_folder)}</strong>, mais ce dossier existe déjà.
  </p>

  <p><strong>Dossier existant :</strong> <code>{esc(str(table_root))}</code></p>

  <div class="card" style="margin-top:14px; border-color:rgba(255,122,0,.45);">
    <h3>Remplacer la table existante</h3>
    <p>Cette option supprime l’ancien dossier de table, puis restaure le package .PinCabOs.</p>

    <form action="/tools/import-table/manifest-conflict" method="post" onsubmit="document.getElementById('replaceSpinner').style.display='inline-block';">
      <input type="hidden" name="batch_dir" value="{esc(str(batch_dir))}">
      <input type="hidden" name="archive_path" value="{esc(str(archive_path))}">
      <input type="hidden" name="conflict_action" value="replace">
      <button class="button" type="submit">Remplacer la table existante</button>
      <span id="replaceSpinner" style="display:none; margin-left:10px; vertical-align:middle;"><svg width="20" height="20" viewBox="0 0 50 50" style="vertical-align:middle;"><circle cx="25" cy="25" r="20" fill="none" stroke="rgba(255,255,255,0.25)" stroke-width="6"></circle><path d="M25 5 A20 20 0 0 1 45 25" fill="none" stroke="#ff7a00" stroke-width="6" stroke-linecap="round"><animateTransform attributeName="transform" type="rotate" from="0 25 25" to="360 25 25" dur="0.75s" repeatCount="indefinite"/></path></svg></span>
    </form>
  </div>

  <div class="card" style="margin-top:14px; border-color:rgba(95,42,145,.55);">
    <h3>Installer sous un nouveau nom</h3>
    <p>Cette option garde la table existante et installe le package dans un nouveau dossier.</p>

    <form action="/tools/import-table/manifest-conflict" method="post" onsubmit="document.getElementById('renameSpinner').style.display='inline-block';">
      <input type="hidden" name="batch_dir" value="{esc(str(batch_dir))}">
      <input type="hidden" name="archive_path" value="{esc(str(archive_path))}">
      <input type="hidden" name="conflict_action" value="rename">

      <label>Nouveau nom de dossier</label><br>
      <input name="new_table_name" value="{esc(suggested)}" style="width:90%; padding:8px; margin:8px 0;"><br>

      <button class="button" type="submit">Installer avec ce nouveau nom</button>
      <span id="renameSpinner" style="display:none; margin-left:10px; vertical-align:middle;"><svg width="20" height="20" viewBox="0 0 50 50" style="vertical-align:middle;"><circle cx="25" cy="25" r="20" fill="none" stroke="rgba(255,255,255,0.25)" stroke-width="6"></circle><path d="M25 5 A20 20 0 0 1 45 25" fill="none" stroke="#ff7a00" stroke-width="6" stroke-linecap="round"><animateTransform attributeName="transform" type="rotate" from="0 25 25" to="360 25 25" dur="0.75s" repeatCount="indefinite"/></path></svg></span>
    </form>
  </div>

  <p style="margin-top:14px;">
    <a class="button secondary" href="/tools">Annuler</a>
  </p>
</div>
""")


def pincabos_standard_table_folder_name(name):
    return pincabos_force_standard_table_name(name)


# Moved to modular route file by PinCabOS refactor (original lines 15782-15833).


def pincabos_import_from_manifest_dir(extract_dir, table_folder_override=None, overwrite_existing=False):
    root, manifest_path = pincabos_find_manifest_root(extract_dir)

    if not manifest_path:
        return None

    manifest = json.loads(manifest_path.read_text(errors="replace"))

    if manifest.get("format") != "PinCabOS table export":
        return {
            "ok": False,
            "message": "Manifest trouvé, mais format non reconnu.",
            "manifest": str(manifest_path),
            "copied": [],
            "missing": [],
            "skipped": [],
        }

    table_folder = str(table_folder_override or manifest.get("table_folder") or "").strip()
    if not table_folder:
        table_folder = Path(root).name or "Imported Table"

    table_folder = pincabos_force_standard_table_name(table_folder)

    # Destination officielle PinCabOS portable.
    table_root = pincabos_vpx_tables_dir() / table_folder

    copied = []
    missing = []
    skipped = []

    model = str(manifest.get("model") or "").strip().lower()

    # Nouveau modèle export:
    # Le manifest est dans le dossier de table extrait.
    # On copie donc le dossier complet tel quel, sans reclassement.
    if model in ["full-table-folder-as-is", "single-folder-portable-table"] or manifest.get("format_version", 0) >= 7:
        try:
            if table_root.exists():
                if not overwrite_existing:
                    return {
                        "ok": False,
                        "message": "Table déjà présente. Remplacement ou renommage requis.",
                        "manifest": str(manifest_path),
                        "table_folder": table_folder,
                        "rom": manifest.get("rom") or "",
                        "copied": copied,
                        "missing": missing,
                        "skipped": ["CONFLICT_TABLE_EXISTS"],
                    }
                shutil.rmtree(table_root)

            table_root.mkdir(parents=True, exist_ok=True)

            for item in sorted(Path(root).iterdir()):
                dest = table_root / item.name

                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                    for f in dest.rglob("*"):
                        if f.is_file():
                            copied.append(str(f))
                elif item.is_file():
                    shutil.copy2(item, dest)
                    copied.append(str(dest))

            pincabos_write_imported_table_metadata(table_root, table_folder)

            try:
                subprocess.run(
                    ["/bin/chown", "-R", "pinball:pinball", str(table_root)],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
                subprocess.run(
                    ["/bin/chmod", "-R", "u+rwX,g+rwX,o+rX", str(table_root)],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
            except Exception:
                pass

            return {
                "ok": True,
                "message": "Import .PinCabOs full-folder terminé. Dossier de table copié tel quel.",
                "manifest": str(manifest_path),
                "table_folder": table_folder,
                "rom": manifest.get("rom") or "",
                "copied": copied,
                "missing": missing,
                "skipped": skipped,
            }

        except Exception as e:
            return {
                "ok": False,
                "message": f"Erreur pendant l'import full-folder: {e}",
                "manifest": str(manifest_path),
                "table_folder": table_folder,
                "rom": manifest.get("rom") or "",
                "copied": copied,
                "missing": missing,
                "skipped": skipped,
            }

    # Ancien modèle manifest:
    # Supporte files = ["path"] ET files = [{"path":"...", "size":...}]
    if table_root.exists() and not overwrite_existing:
        return {
            "ok": False,
            "message": "Table déjà présente. Remplacement ou renommage requis.",
            "manifest": str(manifest_path),
            "table_folder": table_folder,
            "rom": manifest.get("rom") or "",
            "copied": copied,
            "missing": missing,
            "skipped": ["CONFLICT_TABLE_EXISTS"],
        }

    if table_root.exists() and overwrite_existing:
        shutil.rmtree(table_root)

    table_root.mkdir(parents=True, exist_ok=True)

    standard_dirs = manifest.get("standard_dirs") or [
        "altsound", "cache", "medias", "music",
        "pinmame", "pinmame/roms", "pinmame/nvram", "pinmame/cfg", "pinmame/ini",
        "pupvideos", "scripts", "serum", "user", "vni", "extras"
    ]

    for sub in standard_dirs:
        (table_root / str(sub).strip("/")).mkdir(parents=True, exist_ok=True)

    globals()["PINCABOS_MANIFEST_IMPORT_TABLE_DIR"] = table_root

    for empty_dir in manifest.get("empty_dirs") or []:
        if isinstance(empty_dir, dict):
            empty_dir = empty_dir.get("path", "")
        rel_empty = pincabos_safe_manifest_relpath(empty_dir)
        if rel_empty:
            dest_empty = table_root / rel_empty
            dest_empty.mkdir(parents=True, exist_ok=True)

    files = manifest.get("files") or []

    for entry in files:
        if isinstance(entry, dict):
            rel = entry.get("path", "")
        else:
            rel = entry

        rel = pincabos_safe_manifest_relpath(rel)
        if not rel:
            skipped.append(str(entry))
            continue

        src = root / rel
        if not src.exists() or not src.is_file():
            missing.append(rel)
            continue

        dest = table_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied.append(str(dest))

    pincabos_write_imported_table_metadata(table_root, table_folder)

    try:
        subprocess.run(
            ["/bin/chown", "-R", "pinball:pinball", str(table_root)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        subprocess.run(
            ["/bin/chmod", "-R", "u+rwX,g+rwX,o+rX", str(table_root)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except Exception:
        pass

    return {
        "ok": True,
        "message": "Import basé sur manifest terminé.",
        "manifest": str(manifest_path),
        "table_folder": table_folder,
        "rom": manifest.get("rom") or "",
        "copied": copied,
        "missing": missing,
        "skipped": skipped,
    }


def pincabos_try_manifest_import_from_request():
    """
    Si l'utilisateur importe un ZIP PinCabOS contenant pincabos-export-manifest.json,
    on restaure exactement les fichiers listés dans le manifest.
    Si aucun manifest n'est trouvé, retourne None pour laisser l'ancien import continuer.
    """
    if not request:
        return None

    # 1) ZIP envoyé directement dans request.files
    for key in request.files:
        f = request.files.get(key)
        if not f or not f.filename:
            continue

        filename = f.filename.lower()
        if not (filename.endswith(".zip") or filename.endswith(".7z") or filename.endswith(".pincabos")):
            continue

        with tempfile.TemporaryDirectory(prefix="pincabos-import-manifest-") as td:
            zip_path = Path(td) / "upload.zip"
            extract_dir = Path(td) / "extract"
            extract_dir.mkdir(parents=True, exist_ok=True)

            f.save(str(zip_path))

            try:
                r7 = subprocess.run(
                    ["7z", "x", "-y", f"-o{str(extract_dir)}", str(zip_path)],
                    capture_output=True,
                    text=True,
                    timeout=300,
                    check=False,
                )
                if r7.returncode != 0:
                    raise RuntimeError((r7.stdout + "\n" + r7.stderr).strip())
            except Exception as e:
                return page("Import PinCabOS", f"""
<div class="card">
  <h2>Import impossible</h2>
  <p class="bad">Le package ne peut pas être ouvert avec 7z.</p>
  <pre>{esc(str(e))}</pre>
  <p><a class="button" href="/tools">Retour aux outils</a></p>
</div>
""")

            result = pincabos_import_from_manifest_dir(extract_dir)
            if result:
                return pincabos_manifest_import_result_page(result)

    # 2) Chemin temporaire/dossier transmis dans le formulaire
    for value in request.form.values():
        value = str(value or "").strip()
        if not value:
            continue

        candidate = Path(value)
        if not candidate.exists():
            continue

        # Sécurité : seulement chemins temporaires ou PinCabOS
        allowed_prefixes = (
            "/tmp/",
            "/var/tmp/",
            "/opt/pincabos/tmp/",
            "/opt/pincabos/uploads/",
            "/home/pinball/Downloads/",
        )

        if not any(str(candidate).startswith(prefix) for prefix in allowed_prefixes):
            continue

        if candidate.is_dir():
            result = pincabos_import_from_manifest_dir(candidate)
            if result:
                return pincabos_manifest_import_result_page(result)

        if candidate.is_file() and candidate.suffix.lower() in [".zip", ".7z", ".pincabos", ".pincabos".lower()]:
            with tempfile.TemporaryDirectory(prefix="pincabos-import-manifest-") as td:
                extract_dir = Path(td) / "extract"
                extract_dir.mkdir(parents=True, exist_ok=True)

                try:
                    r7 = subprocess.run(
                        ["7z", "x", "-y", f"-o{str(extract_dir)}", str(candidate)],
                        capture_output=True,
                        text=True,
                        timeout=300,
                        check=False,
                    )
                    if r7.returncode != 0:
                        continue
                except Exception:
                    continue

                result = pincabos_import_from_manifest_dir(extract_dir)
                if result:
                    return pincabos_manifest_import_result_page(result)

    return None


def pincabos_manifest_import_result_page(result):
    ok_class = "ok" if result.get("ok") else "bad"
    copied = result.get("copied") or []
    missing = result.get("missing") or []
    skipped = result.get("skipped") or []

    copied_preview = "\n".join(copied[:80])
    if len(copied) > 80:
        copied_preview += f"\n... {len(copied) - 80} autres fichiers copiés"

    missing_preview = "\n".join(missing[:80])
    skipped_preview = "\n".join(skipped[:80])

    return page("Import PinCabOS", f"""
<div class="card">
  <h2>Import PinCabOS basé sur manifest</h2>
  <p class="{ok_class}">{esc(result.get("message", ""))}</p>

  <p><strong>Table :</strong> <code>{esc(result.get("table_folder", ""))}</code></p>
  <p><strong>ROM :</strong> <code>{esc(result.get("rom", ""))}</code></p>
  <p><strong>Manifest :</strong> <code>{esc(result.get("manifest", ""))}</code></p>

  <p><strong>Fichiers copiés :</strong> {len(copied)}</p>
  <pre>{esc(copied_preview)}</pre>

  <p><strong>Fichiers manquants dans le ZIP :</strong> {len(missing)}</p>
  <pre>{esc(missing_preview)}</pre>

  <p><strong>Fichiers ignorés :</strong> {len(skipped)}</p>
  <pre>{esc(skipped_preview)}</pre>

  <p>
    <a class="button" href="/tools">Retour aux outils</a>
    <a class="button secondary" href="/">Dashboard</a>
  </p>
</div>
""")


def pincabos_run_vpinfe_vpx_standardizer():
    """
    Normalise les tables vers le layout portable VPinFE/VPX après import.
    Les dossiers globaux restent en fallback legacy.
    """
    try:
        subprocess.run(
            [str(pco_script("vpinfe_vpx_standard")), "--apply"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=180,
            check=False
        )
    except Exception:
        pass

@app.route("/tools/import-table/install", methods=["POST"])
def tools_import_table_install():
    manifest_response = pincabos_try_manifest_import_from_request()
    if manifest_response is not None:
        return manifest_response

    batch_dir = Path(request.form.get("batch_dir", "")).resolve()
    imports_root = Path("/home/pinball/Downloads").resolve()

    if not batch_dir.exists() or imports_root not in batch_dir.parents:
        return page("Outils", """
<div class="card">
  <h2>Installation impossible</h2>
  <p class="bad">Dossier batch invalide.</p>
  <p><a class="button" href="/tools">Retour Outils</a></p>
</div>
""")

    import_mode = request.form.get("import_mode", "auto").strip().lower()
    if import_mode not in ["auto", "search", "manual", "resources", "existing"]:
        import_mode = "auto"

    ipdbid = ""
    table_title = ""
    title = ""
    manufacturer = ""
    year = ""
    rom = ""
    vpsid = ""
    parent_vpsid = ""
    game_vpsid = ""
    parent_version = ""
    target_version = ""
    assoc = {}
    resource_manifest = {}
    target_existing = False

    if import_mode == "existing":
        selected_name = str(
            request.form.get("existing_table", "") or ""
        ).strip()
        tables_root = Path(pincabos_vpx_tables_dir()).resolve()
        candidate = tables_root / selected_name

        if (
            not selected_name
            or Path(selected_name).name != selected_name
            or candidate.is_symlink()
        ):
            return page("Outils", """
<div class="card">
  <h2>Installation impossible</h2>
  <p class="bad">Table de destination invalide.</p>
  <p><a class="button" href="/tools/import-table">Retour Smart Import</a></p>
</div>
""")

        try:
            selected_dir = candidate.resolve(strict=True)
        except Exception:
            selected_dir = candidate

        if (
            not selected_dir.is_dir()
            or selected_dir.parent != tables_root
        ):
            return page("Outils", """
<div class="card">
  <h2>Installation impossible</h2>
  <p class="bad">La destination n’est pas une table directe valide de Tables.</p>
  <p><a class="button" href="/tools/import-table">Retour Smart Import</a></p>
</div>
""")

        installed_vpxs = [
            item
            for item in selected_dir.glob("*.vpx")
            if item.is_file() and not item.is_symlink()
        ]

        if len(installed_vpxs) != 1:
            return page("Outils", """
<div class="card">
  <h2>Installation impossible</h2>
  <p class="bad">La table choisie ne contient pas exactement un VPX fiable.</p>
  <p><a class="button" href="/tools/import-table">Retour Smart Import</a></p>
</div>
""")

        existing_manifest = {}
        existing_manifest_path = selected_dir / "pincabos-table-manifest.json"

        if existing_manifest_path.is_file():
            try:
                loaded_manifest = json.loads(
                    existing_manifest_path.read_text(
                        encoding="utf-8",
                        errors="replace",
                    )
                )
                if isinstance(loaded_manifest, dict):
                    existing_manifest = loaded_manifest
            except Exception:
                existing_manifest = {}

        title = selected_dir.name
        table_title = str(
            existing_manifest.get("title", "") or title
        ).strip()
        manufacturer = str(
            existing_manifest.get("manufacturer", "") or ""
        ).strip()
        year = str(existing_manifest.get("year", "") or "").strip()
        rom = str(existing_manifest.get("rom", "") or "").strip()
        vpsid = str(existing_manifest.get("vpsid", "") or "").strip()
        game_vpsid = str(
            existing_manifest.get("game_vpsid", "") or ""
        ).strip()
        parent_vpsid = ""
        parent_version = ""
        target_version = ""
        ipdbid = str(existing_manifest.get("ipdbid", "") or "").strip()
        target_existing = True

        # Conserver l'inventaire partiel après sélection explicite de table.
        try:
            incoming_resource_manifest = (
                pincabos_smart_import_load_resource_manifest(
                    batch_dir,
                    required=False,
                )
            )
        except Exception as exc:
            return page("Outils", f"""
<div class="card">
  <h2>Installation impossible</h2>
  <p class="bad">{html.escape(str(exc))}</p>
  <p><a class="button" href="/tools/import-table">Retour Smart Import</a></p>
</div>
""")

        if incoming_resource_manifest:
            incoming_game_vpsid = str(
                incoming_resource_manifest.get("game_vpsid", "") or ""
            ).strip()
            known_existing_game_vpsid = game_vpsid

            if not known_existing_game_vpsid and vpsid:
                try:
                    existing_resource_identity = (
                        pincabos_smart_import_exact_resource(vpsid)
                    )
                    known_existing_game_vpsid = str(
                        existing_resource_identity.get("game_vpsid", "") or ""
                    ).strip()
                except Exception:
                    known_existing_game_vpsid = ""

            if (
                known_existing_game_vpsid
                and incoming_game_vpsid
                and known_existing_game_vpsid.casefold()
                != incoming_game_vpsid.casefold()
            ):
                return page("Outils", """
<div class="card">
  <h2>Installation impossible</h2>
  <p class="bad">La table choisie appartient à un autre jeu VPSDB que les VPS-ID fournis.</p>
  <p><a class="button" href="/tools/import-table">Retour Smart Import</a></p>
</div>
""")

            resource_manifest = incoming_resource_manifest
            if incoming_game_vpsid:
                game_vpsid = incoming_game_vpsid

    elif import_mode == "resources":
        try:
            resource_manifest = (
                pincabos_smart_import_load_resource_manifest(
                    batch_dir,
                    required=True,
                )
            )
        except Exception as exc:
            return page("Outils", f"""
<div class="card">
  <h2>Installation impossible</h2>
  <p class="bad">{html.escape(str(exc))}</p>
  <p><a class="button" href="/tools/import-table">Retour Smart Import</a></p>
</div>
""")

        title = str(
            resource_manifest.get("final_table_name", "")
            or resource_manifest.get("title", "")
            or ""
        ).strip()
        table_title = str(resource_manifest.get("title", "") or "").strip()
        manufacturer = str(resource_manifest.get("manufacturer", "") or "").strip()
        year = str(resource_manifest.get("year", "") or "").strip()
        rom = str(resource_manifest.get("rom", "") or "").strip()
        vpsid = str(resource_manifest.get("primary_table_vpsid", "") or "").strip()
        game_vpsid = str(resource_manifest.get("game_vpsid", "") or "").strip()
        parent_vpsid = str(resource_manifest.get("parent_vpsid", "") or "").strip()
        parent_version = str(resource_manifest.get("parent_version", "") or "").strip()
        target_version = str(resource_manifest.get("target_version", "") or "").strip()
        ipdbid = ""

        if not title or not game_vpsid:
            return page("Outils", """
<div class="card">
  <h2>Installation impossible</h2>
  <p class="bad">L’inventaire VPS-ID ne contient pas de table cible fiable.</p>
  <p><a class="button" href="/tools/import-table">Retour Smart Import</a></p>
</div>
""")

    elif import_mode == "manual":
        title = request.form.get("manual_title", "").strip()
        table_title = title
        manufacturer = request.form.get("manual_manufacturer", "").strip()
        year = request.form.get("manual_year", "").strip()
        rom = request.form.get("manual_rom", "").strip()
        vpsid = ""
        parent_vpsid = ""
        game_vpsid = ""
        parent_version = ""
        target_version = ""
        ipdbid = ""

        if not title:
            return page("Outils", """
<div class="card">
  <h2>Installation impossible</h2>
  <p class="bad">Le nom de table manuel est vide.</p>
  <p>Entre un nom de table VPinFE, par exemple <code>Demo Table (PinCabOS 2026)</code>.</p>
  <p><a class="button" href="/tools">Retour Outils</a></p>
</div>
""")

    else:
        if import_mode == "search":
            assoc_raw = request.form.get("search_association", "{}")
        else:
            assoc_raw = request.form.get("association", "{}")

        try:
            assoc = json.loads(assoc_raw) if assoc_raw else {}
        except Exception:
            assoc = {}

        if assoc.get("mode") != "vpsdb":
            return page("Outils", """
<div class="card">
  <h2>Installation impossible</h2>
  <p class="bad">Aucune association VPSdb valide sélectionnée.</p>
  <p>Utilise une sélection auto, un résultat de recherche VPSdb, ou l’import manuel complet.</p>
  <p><a class="button" href="/tools">Retour Outils</a></p>
</div>
""")

        table_title = str(assoc.get("title", "")).strip()
        manufacturer = str(assoc.get("manufacturer", "")).strip()
        year = str(assoc.get("year", "")).strip()
        rom = str(assoc.get("rom", "")).strip()
        vpsid = str(assoc.get("vpsid", "")).strip()
        parent_vpsid = str(assoc.get("parent_vpsid", "")).strip()
        game_vpsid = str(assoc.get("game_vpsid", "")).strip()
        parent_version = str(assoc.get("parent_version", "")).strip()
        target_version = str(assoc.get("version", "")).strip()
        ipdbid = str(assoc.get("ipdbid", "")).strip()

        title = str(assoc.get("final_table_name", "")).strip()
        if not title:
            title = table_title
            if manufacturer and year:
                title = f"{table_title} ({manufacturer} {year})"

        if not title:
            return page("Outils", """
<div class="card">
  <h2>Installation impossible</h2>
  <p class="bad">Le résultat VPSdb sélectionné ne contient pas de nom de table valide.</p>
  <p><a class="button" href="/tools">Retour Outils</a></p>
</div>
""")

    # Si aucune ROM fournie par VPSdb/manuel, on reprend la ROM détectée pendant l'analyse du batch.
    if not rom:
        try:
            detected_again = pincabos_detect_batch(batch_dir)
            rom = str(detected_again.get("rom", "") or "").strip()
        except Exception:
            rom = ""

    cmd = [
        str(pco_script("smart_archive_import")),
        str(batch_dir),
        "--title", title,
        "--manufacturer", manufacturer,
        "--year", str(year),
        "--vpsid", vpsid,
        "--parent-vpsid", parent_vpsid,
        "--game-vpsid", game_vpsid,
        "--parent-version", parent_version,
        "--target-version", target_version,
        "--rom", rom,
        "--ipdbid", ipdbid,
    ]

    if target_existing:
        cmd.append("--target-existing")

    if resource_manifest:
        cmd.extend([
            "--resources-json",
            str(pincabos_smart_import_resource_manifest_path(batch_dir)),
        ])

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        output = (r.stdout + "\n" + r.stderr).strip()
        returncode = r.returncode
    except Exception as e:
        output = f"ERREUR lancement importeur: {e}"
        returncode = 1

    # PINCABOS_SMART_IMPORT_PRESERVE_FAILED_BATCH_V1
    #
    # Un batch réussi est supprimé.
    # Un batch en erreur reste disponible pour diagnostic / reprise.
    if returncode == 0:
        try:
            if (
                batch_dir.exists()
                and imports_root in batch_dir.parents
            ):
                shutil.rmtree(batch_dir)

        except Exception as e:
            output += (
                "\n\nWARNING: impossible de supprimer "
                f"le batch upload: {e}"
            )

    else:
        output += (
            "\n\nINFO: import en erreur — batch conservé "
            "pour diagnostic/reprise : "
            f"{batch_dir}"
        )

    try:
        for work_root in [Path("/home/pinball/Downloads/work"), Path("/home/pinball/Downloads/work")]:
            if work_root.exists():
                for item in work_root.iterdir():
                    if item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                    else:
                        try:
                            item.unlink()
                        except Exception:
                            pass
    except Exception as e:
        output += f"\n\nWARNING: cleanup work erreur: {e}"

    cls = "ok" if returncode == 0 else "bad"
    title_msg = "Installation terminée" if returncode == 0 else "Installation terminée avec erreur(s)"

    body = f"""
<div class="card">
  <h2>{esc(title_msg)}</h2>
  <p class="{cls}">Mode : <strong>{esc(import_mode)}</strong></p>
  <p class="{cls}">Association : <strong>{esc(title)}</strong> — {esc(manufacturer)} — {esc(str(year))} — VPSId {esc(vpsid)}</p>

  <h3>Rapport</h3>
  <pre>{esc(output)}</pre>

  <p>
    <a class="button" href="/tools">Retour Outils</a>
    <a class="button secondary" href="/tools/commander?root=Tables">Voir les tables</a>
  </p>
</div>
"""
    return page("Outils", body)


@app.route("/tools/external-disks")
def tools_external_disks():
    from pathlib import Path

    network_root = Path("/home/pinball/NetworkDrives")
    network_root.mkdir(parents=True, exist_ok=True)

    usb_root = Path("/mnt/pincab-usb")
    usb_root.mkdir(parents=True, exist_ok=True)

    usb_list = ""
    try:
        for d in sorted(usb_root.iterdir(), key=lambda x: x.name.lower()):
            if d.is_dir():
                mounted = subprocess.run(
                    ["bash", "-lc", "mountpoint -q " + shlex_quote(str(d))],
                    capture_output=True,
                    text=True
                ).returncode == 0

                if mounted:
                    usb_list += f"""
<li style="margin-bottom:10px;">
  <strong>{esc(d.name)}</strong> —
  <span class="ok">Monté</span> —
  <code>{esc(str(d))}</code>
  <form action="/tools/external-disks/usb/unmount" method="post" style="display:inline; margin-left:10px;">
    <input type="hidden" name="usb_name" value="{esc(d.name)}">
    <button class="button secondary" type="submit">Démonter</button>
  </form>
</li>
"""
                else:
                    # Nettoyage automatique des dossiers USB ghost
                    try:
                        d.rmdir()
                    except Exception:
                        pass
    except Exception:
        pass

    if not usb_list:
        usb_list = "<li>Aucune clé USB montée.</li>"

    smb_list = ""
    try:
        for d in sorted(network_root.iterdir(), key=lambda x: x.name.lower()):
            if d.is_dir():
                mounted = subprocess.run(
                    ["bash", "-lc", "mountpoint -q " + shlex_quote(str(d))],
                    capture_output=True,
                    text=True
                ).returncode == 0

                cls = "ok" if mounted else "warn"
                status = "Monté" if mounted else "Non monté"

                action_button = ""
                disconnect_button = f"""
<form action="/tools/external-disks/smb/disconnect" method="post" style="display:inline; margin-left:8px;" onsubmit="return confirm('Confirmer la déconnexion de ce lecteur SMB ?');">
  <input type="hidden" name="drive_name" value="{esc(d.name)}">
  <button class="button secondary" type="submit">Déconnecter</button>
</form>
"""
                if mounted:
                    action_button = f"""
<form action="/tools/external-disks/smb/unmount" method="post" style="display:inline; margin-left:10px;">
  <input type="hidden" name="drive_name" value="{esc(d.name)}">
  <button class="button secondary" type="submit">Démonter</button>
</form>
{disconnect_button}
"""
                else:
                    action_button = f"""
<a class="button secondary" href="#connecter-smb" style="display:inline-block; margin-left:10px;">
  Monter / reconnecter
</a>
{disconnect_button}
"""
    except Exception:
        pass

    if not smb_list:
        smb_list = "<li>Aucun lecteur SMB monté/configuré.</li>"

    body = f"""
<!-- PINCABOS_STOCKAGE_INTERNE_V1 -->
<div class="card">
  <h2>Disque interne</h2>

  <p>
    Heberger la bibliotheque de tables sur un second disque interne, y compris
    un disque NTFS repris d'un ancien cabinet Windows. Le dossier des tables
    reste au choix, et le montage au demarrage est optionnel.
  </p>

  <p>
    <a class="button" href="/tools/internal-disk">Gerer le disque interne</a>
  </p>
</div>

<div class="card">
  <h2>Partages reseau</h2>

  <p>
    Ajoute un partage SMB / NAS / Windows à PinCabOS.
    Après montage, il apparaîtra dans <strong>PinCab Explorer → Lecteurs SMB</strong>.
  </p>

  <p>
    <a class="button secondary" href="/tools">Retour Outils</a>
    <a class="button" href="/tools/commander?root=Lecteurs%20SMB">Ouvrir Lecteurs SMB dans PinCab Explorer</a>
  </p>
</div>

<div class="card" style="margin-top:20px;">
  <h2 id="connecter-smb">Connecter un partage SMB</h2>

  <p>
    Étape 1 : entre les informations du serveur. PinCabOS va se connecter et détecter les partages disponibles.
  </p>

  <form action="/tools/external-disks/smb/detect" method="post">
    <label>Nom du lecteur dans PinCabOS</label><br>
    <input name="drive_name" placeholder="exemple: NAS-Tables" style="width:90%; padding:8px;"><br><br>

    <label>Adresse serveur ou IP</label><br>
    <input name="server" placeholder="exemple: 192.168.254.10 ou NAS-SYNOLOGY" style="width:90%; padding:8px;"><br><br>

    <label>Login</label><br>
    <input name="username" placeholder="utilisateur SMB" style="width:90%; padding:8px;"><br><br>

    <label>Password</label><br>
    <input name="password" type="password" placeholder="mot de passe SMB" style="width:90%; padding:8px;"><br><br>

    <label>Domaine / Workgroup optionnel</label><br>
    <input name="domain" placeholder="WORKGROUP" style="width:90%; padding:8px;"><br><br>

    <button class="button" type="submit">Connecter et détecter les partages</button>
  </form>
</div>

<div class="card" style="margin-top:20px;">
  <h2>Stockage USB</h2>

  <p>
    Les clés USB montées automatiquement apparaissent ici et dans
    <strong>PinCab Explorer → Stockage USB</strong>.
  </p>

  <ul>
    {usb_list}
  </ul>
</div>

<div class="card" style="margin-top:20px;">
  <h2>Lecteurs SMB</h2>
  <ul>
    {smb_list}
  </ul>
</div>
"""
    return page("Gestion du stockage", body)


@app.route("/tools/external-disks/smb/detect", methods=["POST"])
def tools_external_disks_smb_detect():
    import json
    import re
    import time
    import uuid
    import subprocess
    from pathlib import Path

    drive_name = request.form.get("drive_name", "").strip()
    server = request.form.get("server", "").strip()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    domain = request.form.get("domain", "").strip() or "WORKGROUP"

    if not server or not username:
        return page("Gestion du stockage", """
<div class="card">
  <h2>Erreur SMB</h2>
  <p class="bad">Serveur/IP et login requis.</p>
  <p><a class="button" href="/tools/external-disks">Retour</a></p>
</div>
""")

    safe_name = re.sub(r"[^A-Za-z0-9._ -]+", "_", drive_name).strip()
    if not safe_name:
        safe_name = server.replace(".", "-").replace("/", "-")

    session_id = uuid.uuid4().hex
    session_dir = Path("/home/pinball/.config/pincabos/smb-sessions")
    session_dir.mkdir(parents=True, exist_ok=True)

    session_file = session_dir / (session_id + ".json")
    session_file.write_text(json.dumps({
        "drive_name": safe_name,
        "server": server,
        "username": username,
        "password": password,
        "domain": domain,
        "created": time.time(),
    }, indent=2, ensure_ascii=False))
    session_file.chmod(0o600)

    cmd = ["smbclient", "-L", "//" + server, "-U", username + "%" + password, "-m", "SMB3", "-g"]

    if domain:
        cmd.extend(["-W", domain])

    shares = []
    error = ""

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
        output = (r.stdout + "\\n" + r.stderr)

        for line in output.splitlines():
            line = line.strip()

            # Format attendu avec -g : Disk|ShareName|Comment
            if line.startswith("Disk|"):
                parts = line.split("|")
                if len(parts) >= 2:
                    share = parts[1].strip()
                    if share and not share.endswith("$"):
                        shares.append(share)

        if r.returncode != 0 and not shares:
            error = output[-4000:]

    except Exception as e:
        error = str(e)

    if not shares:
        body = f"""
<div class="card">
  <h2>Aucun partage détecté</h2>

  <p class="bad">
    PinCabOS n’a pas réussi à détecter les partages disponibles.
    Vérifie l’adresse/IP, le login, le mot de passe et les permissions du compte.
  </p>

  <h3>Détail</h3>
  <pre>{esc(error)}</pre>

  <p>
    <a class="button" href="/tools/external-disks">Retour</a>
  </p>
</div>
"""
        return page("Partages SMB", body)

    options = ""
    for share in shares:
        options += f'<option value="{esc(share)}">{esc(share)}</option>'

    body = f"""
<div class="card">
  <h2>Partages SMB détectés</h2>

  <p>
    Connexion réussie au serveur : <strong>{esc(server)}</strong>
  </p>

  <form action="/tools/external-disks/smb/mount" method="post">
    <input type="hidden" name="session_id" value="{esc(session_id)}">

    <label>Choisir le partage à monter</label><br>
    <select name="share" style="width:90%; padding:8px; margin:8px 0;">
      {options}
    </select><br><br>

    <button class="button" type="submit">Monter le partage sélectionné</button>
    <a class="button secondary" href="/tools/external-disks">Annuler</a>
  </form>
</div>
"""
    return page("Partages SMB", body)


@app.route("/tools/external-disks/smb/mount", methods=["POST"])
def tools_external_disks_smb_mount():
    import json
    import re
    import subprocess
    from pathlib import Path

    session_id = request.form.get("session_id", "").strip()
    share = request.form.get("share", "").strip()

    session_file = Path("/home/pinball/.config/pincabos/smb-sessions") / (session_id + ".json")

    if not session_id or not share or not session_file.exists():
        return page("Gestion du stockage", """
<div class="card">
  <h2>Erreur SMB</h2>
  <p class="bad">Session SMB invalide ou expirée.</p>
  <p><a class="button" href="/tools/external-disks">Retour</a></p>
</div>
""")

    data = json.loads(session_file.read_text())

    drive_name = data["drive_name"]
    server = data["server"]
    username = data["username"]
    password = data["password"]
    domain = data.get("domain") or "WORKGROUP"

    safe_name = re.sub(r"[^A-Za-z0-9._ -]+", "_", drive_name).strip()
    if not safe_name:
        safe_name = share

    mount_root = Path("/home/pinball/NetworkDrives")
    mount_point = mount_root / safe_name

    cred_root = Path("/home/pinball/.config/pincabos/smb")
    cred_root.mkdir(parents=True, exist_ok=True)
    mount_point.mkdir(parents=True, exist_ok=True)

    cred_file = cred_root / (safe_name + ".cred")
    cred_file.write_text(
        "username=" + username + "\n" +
        "password=" + password + "\n" +
        "domain=" + domain + "\n"
    )
    cred_file.chmod(0o600)

    try:
        subprocess.run(["chown", "-R", "pinball:pinball", str(mount_root), str(cred_root)], timeout=30)
    except Exception:
        pass

    source = f"//{server}/{share}"

    # PINCABOS_SECURE_SMB_MOUNT_V1
    cmd = [
        "/usr/bin/sudo", "-n",
        "/usr/local/sbin/pincabos-smb-mount",
        source, str(mount_point), str(cred_file),
    ]

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=75)
        output = (r.stdout + "\\n" + r.stderr).strip()
    except subprocess.TimeoutExpired as e:
        output = "Le montage SMB a dépassé le délai. Le serveur NAS ne répond pas assez vite ou les options SMB sont incompatibles.\\n"
        output += "Commande: " + " ".join(str(part) for part in cmd)
        r = type("Result", (), {"returncode": 124})()

    try:
        session_file.unlink()
    except Exception:
        pass

    if r.returncode != 0:
        body = f"""
<div class="card">
  <h2>Montage SMB échoué</h2>

  <p class="bad">Le partage a été détecté, mais le montage a échoué.</p>

  <h3>Détail</h3>
  <pre>{esc(output)}</pre>

  <p>
    <a class="button" href="/tools/external-disks">Retour</a>
  </p>
</div>
"""
        return page("Gestion du stockage", body)

    body = f"""
<div class="card">
  <h2>Partage SMB monté</h2>

  <p class="ok">
    Le partage <strong>{esc(share)}</strong> est maintenant monté dans :
  </p>

  <pre>{esc(str(mount_point))}</pre>

  <p>
    <a class="button" href="/tools/commander?root=Lecteurs%20SMB">Ouvrir dans PinCab Explorer</a>
    <a class="button secondary" href="/tools/external-disks">Retour Gestion du stockage</a>
  </p>
</div>
"""
    return page("Gestion du stockage", body)


# PINCABOS_WEBAPP_MODULES_V1 : Commander (gestionnaire de fichiers, visionneuse live) dans son module.
import pincabos_webapp_commander as pco_commander_routes

pco_commander_routes.register(app, page)


def pincabos_find_value_deep(obj, wanted_keys):
    """
    Cherche récursivement une clé dans un dict/list JSON.
    """
    wanted = {str(k).lower() for k in wanted_keys}

    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() in wanted and v not in ("", None):
                return str(v).strip()
        for v in obj.values():
            found = pincabos_find_value_deep(v, wanted)
            if found:
                return found

    elif isinstance(obj, list):
        for item in obj:
            found = pincabos_find_value_deep(item, wanted)
            if found:
                return found

    return ""


def pincabos_export_safe_filename(name):
    name = str(name or "").strip()
    name = name.replace("\\", " ").replace("/", " ")
    name = re.sub(r'[:"*?<>|]+', " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name or "PinCabOS-Table"


def pincabos_table_export_dirs():
    """
    Modèle export PinCabOS:
    - aucune option;
    - aucun chemin legacy global;
    - on exporte le dossier complet de la table sélectionnée tel quel;
    - on ajoute/actualise seulement le manifest d'export;
    - on compresse au maximum;
    - extension finale .PinCabOs.
    """
    return {
        "tables_root": pincabos_vpx_tables_dir(),
        "exports_root": Path("/home/pinball/Exports"),
    }


def pincabos_export_should_exclude_relative(relative_path):
    """
    Exclusions techniques des packages portables PinCabOS.
    Les fichiers nécessaires à la table restent inclus.
    """
    rel = Path(relative_path)
    parts = rel.parts
    lower_parts = [part.lower() for part in parts]

    excluded_dirs = {
        ".pincabos-backups",
        ".pincabos-backup",
        ".pincabos-tmp",
        ".pincabos-cache",
        "cache",
        ".cache",
        "logs",
        "log",
        "__pycache__",
    }

    if any(part in excluded_dirs for part in lower_parts[:-1]):
        return True

    name = lower_parts[-1] if lower_parts else ""

    if name in {".ds_store", "thumbs.db"}:
        return True

    if name.endswith((".log", ".tmp", ".temp", ".pincabos-fulldmd-before-autoarrange.bak")):
        return True

    return False


def pincabos_write_full_folder_export_manifest(table_dir):
    table_dir = Path(table_dir)
    manifest_path = table_dir / "pincabos-export-manifest.json"

    files = []
    empty_dirs = []

    for p in sorted(table_dir.rglob("*")):
        rel_inside = p.relative_to(table_dir)

        if pincabos_export_should_exclude_relative(rel_inside):
            continue

        if p.is_symlink():
            continue

        if p.is_dir():
            try:
                included_children = [
                    child for child in p.iterdir()
                    if not pincabos_export_should_exclude_relative(
                        child.relative_to(table_dir)
                    )
                ]
                if not included_children:
                    empty_dirs.append(rel_inside.as_posix())
            except Exception:
                pass
            continue

        if p.is_file():
            try:
                files.append({
                    "path": rel_inside.as_posix(),
                    "size": p.stat().st_size,
                })
            except Exception:
                files.append({
                    "path": rel_inside.as_posix(),
                    "size": 0,
                })

    manifest = {
        "format": "PinCabOS table export",
        "format_version": 8,
        "model": "clean-portable-table-folder",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "table_folder": table_dir.name,
        "table_root": str(table_dir),
        "export_rule": (
            "Complete selected table directory excluding PinCabOS rollback "
            "backups, caches, temporary files and technical logs."
        ),
        "files": files,
        "empty_dirs": empty_dirs,
    }

    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    try:
        subprocess.run(
            ["/bin/chown", "pinball:pinball", str(manifest_path)],
            timeout=10,
            check=False,
        )
        subprocess.run(
            ["/bin/chmod", "664", str(manifest_path)],
            timeout=10,
            check=False,
        )
    except Exception:
        pass

    return manifest_path


def pincabos_zip_full_table_folder(table_dir, output_path):
    table_dir = Path(table_dir)
    output_path = Path(output_path)

    import zipfile

    with zipfile.ZipFile(
        output_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        allowZip64=True,
    ) as z:
        for p in sorted(table_dir.rglob("*")):
            rel_inside = p.relative_to(table_dir)

            if pincabos_export_should_exclude_relative(rel_inside):
                continue

            if p.is_symlink():
                continue

            rel = p.relative_to(table_dir.parent).as_posix()

            if p.is_dir():
                try:
                    included_children = [
                        child for child in p.iterdir()
                        if not pincabos_export_should_exclude_relative(
                            child.relative_to(table_dir)
                        )
                    ]
                    if not included_children:
                        z.writestr(rel.rstrip("/") + "/", "")
                except Exception:
                    pass
                continue

            if p.is_file():
                z.write(p, rel)

    return output_path


def pincabos_detect_vpsid_for_export(table_dir):
    """
    Détecte le VPSId pour nommer l'export.
    Sources:
    - *.info JSON
    - pincabos-table-manifest.json
    - pincabos-export-manifest.json
    """
    table_dir = Path(table_dir)

    keys = {
        "vpsid", "vps_id", "vpsdb", "vpsdbid", "vpsdb_id",
        "idvpsdb", "id_vpsdb", "id"
    }

    def find_deep(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                lk = str(k).strip().lower()
                if lk in keys and v not in ("", None):
                    val = str(v).strip()
                    # évite de prendre un id générique trop long ou un chemin
                    if val and "/" not in val and "\\" not in val and len(val) <= 64:
                        return val
            for v in obj.values():
                found = find_deep(v)
                if found:
                    return found

        if isinstance(obj, list):
            for item in obj:
                found = find_deep(item)
                if found:
                    return found

        return ""

    candidates = []
    candidates.extend(sorted(table_dir.glob("*.info")))
    candidates.append(table_dir / "pincabos-table-manifest.json")
    candidates.append(table_dir / "pincabos-export-manifest.json")

    for f in candidates:
        try:
            if not f.exists() or not f.is_file():
                continue
            data = json.loads(f.read_text(errors="replace"))
            found = find_deep(data)
            if found:
                return pincabos_export_safe_filename(found)
        except Exception:
            pass

    return ""


@app.route("/tools/export-table", methods=["POST"])
def tools_export_table():
    paths = pincabos_table_export_dirs()
    tables_root = paths["tables_root"].resolve()
    exports_root = paths["exports_root"]

    table_name = request.form.get("table_folder", "").strip()
    if not table_name:
        table_name = request.form.get("table", "").strip()
    if not table_name:
        table_name = request.form.get("table_name", "").strip()

    if not table_name:
        return page("Export PinCabOS", """
<div class="card">
  <h2>Export impossible</h2>
  <p class="bad">Aucune table sélectionnée.</p>
  <p><a class="button" href="/tools">Retour Outils</a></p>
</div>
""")

    table_dir = (tables_root / table_name).resolve()

    if not table_dir.exists() or not table_dir.is_dir() or tables_root not in table_dir.parents:
        return page("Export PinCabOS", f"""
<div class="card">
  <h2>Export impossible</h2>
  <p class="bad">Dossier de table invalide.</p>
  <p><code>{esc(str(table_dir))}</code></p>
  <p><a class="button" href="/tools">Retour Outils</a></p>
</div>
""")

    exports_root.mkdir(parents=True, exist_ok=True)

    manifest_path = pincabos_write_full_folder_export_manifest(table_dir)

    safe_table = pincabos_export_safe_filename(table_dir.name)
    vpsid = pincabos_detect_vpsid_for_export(table_dir)

    if vpsid:
        export_base = f"{safe_table} - VPSId {vpsid}"
    else:
        export_base = safe_table

    tmp_zip = exports_root / f"{export_base}.zip"
    final_pkg = exports_root / f"{export_base}.PinCabOs"

    if tmp_zip.exists():
        tmp_zip.unlink()
    if final_pkg.exists():
        final_pkg.unlink()

    pincabos_zip_full_table_folder(table_dir, tmp_zip)

    tmp_zip.rename(final_pkg)

    try:
        subprocess.run(["/bin/chown", "pinball:pinball", str(final_pkg)], timeout=10, check=False)
        subprocess.run(["/bin/chmod", "664", str(final_pkg)], timeout=10, check=False)
    except Exception:
        pass

    size_mb = final_pkg.stat().st_size / 1024 / 1024

    delete_after_export = request.form.get("delete_after_export") == "1"
    deleted_table = False
    delete_message = ""

    export_ok = False
    try:
        import zipfile
        export_ok = final_pkg.exists() and final_pkg.is_file() and final_pkg.stat().st_size > 0
        if export_ok:
            with zipfile.ZipFile(final_pkg, "r") as z:
                export_ok = z.testzip() is None
    except Exception as e:
        export_ok = False
        delete_message = f"Validation export échouée: {e}"

    if delete_after_export:
        if export_ok:
            try:
                if table_dir.exists() and table_dir.is_dir() and tables_root in table_dir.parents:
                    shutil.rmtree(table_dir)
                    deleted_table = True
                    delete_message = "Table locale supprimée après export validé."
            except Exception as e:
                delete_message = f"Export OK, mais suppression impossible: {e}"
        else:
            if not delete_message:
                delete_message = "Suppression annulée: le package exporté n’a pas passé la validation."

    delete_html = ""
    if delete_after_export:
        cls = "ok" if deleted_table else "warn"
        delete_html = f'<p class="{cls}"><strong>Suppression après export :</strong> {esc(delete_message)}</p>'

    return page("Export PinCabOS", f"""
<div class="card">
  <h2>Export terminé</h2>
  <p class="ok">Package portable créé avec les fichiers utiles de la table. Les backups, caches et journaux techniques sont exclus.</p>
  {delete_html}

  <p><strong>Table :</strong> <code>{esc(table_dir.name)}</code></p>
  <p><strong>VPSId :</strong> <code>{esc(vpsid or "non détecté")}</code></p>
  <p><strong>Manifest :</strong> <code>{esc(str(manifest_path))}</code></p>
  <p><strong>Package :</strong> <code>{esc(str(final_pkg))}</code></p>
  <p><strong>Taille :</strong> {size_mb:.2f} MiB</p>

  <p>
    <a class="button" href="/download-export?file={esc(final_pkg.name)}">Télécharger .PinCabOs</a>
    <a class="button secondary" href="/tools">Retour Outils</a>
  </p>
</div>
""")


@app.route("/download-export")
def download_export():
    paths = pincabos_table_export_dirs()
    exports_root = paths["exports_root"].resolve()

    filename = request.args.get("file", "").strip()
    if not filename:
        return "Fichier manquant", 400

    filename = Path(filename).name
    if not filename.lower().endswith(".pincabos"):
        return "Extension invalide", 400

    target = (exports_root / filename).resolve()

    if not target.exists() or not target.is_file() or exports_root not in target.parents:
        return "Fichier introuvable", 404

    return send_file(
        str(target),
        as_attachment=True,
        download_name=target.name,
        mimetype="application/octet-stream",
    )


# PINCABOS_SAFE_PATH_CONTAINMENT_V1
def pincabos_path_inside(path, root):
    """Vrai uniquement si path est root ou demeure réellement sous root."""
    try:
        candidate = Path(path).resolve(strict=False)
        base = Path(root).resolve(strict=False)
        candidate.relative_to(base)
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def pincabos_import_classifier_unavailable(exc):
    return jsonify({
        "ok": False,
        "error": (
            "Moteur pincabos_import_classifier absent ou impossible à charger. "
            "Installe /opt/pincabos/tools/pincabos_import_classifier.py. "
            f"Détail: {exc}"
        ),
    }), 503
# PINCABOS_SAFE_PATH_CONTAINMENT_V1_END

@app.route("/api/import/analyze-zip", methods=["POST"])
def api_import_analyze_zip():
    try:
        from pathlib import Path
        import sys

        tools_dir = "/opt/pincabos/tools"
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)

        try:
            from pincabos_import_classifier import analyze_zip
        except (ImportError, ModuleNotFoundError) as exc:
            return pincabos_import_classifier_unavailable(exc)

        data = request.get_json(silent=True) or {}
        zip_path = data.get("zip_path") or data.get("path") or ""

        if not zip_path:
            return jsonify({"ok": False, "error": "zip_path manquant"}), 400

        zp = Path(zip_path).resolve()

        allowed_roots = [
            Path("/home/pinball/Downloads").resolve(),
            Path("/opt/pincabos/uploads").resolve(),
            Path("/opt/pincabos/tmp").resolve(),
            Path(pincabos_vpx_tables_dir()).resolve(),
        ]

        if not any(pincabos_path_inside(zp, root) for root in allowed_roots):
            return jsonify({"ok": False, "error": "chemin zip non autorisé"}), 403

        return jsonify(analyze_zip(zp))

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/import/apply-zip-choice", methods=["POST"])
def api_import_apply_zip_choice():
    try:
        from pathlib import Path
        import sys

        tools_dir = "/opt/pincabos/tools"
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)

        try:
            from pincabos_import_classifier import import_zip_by_choice, normalize_table_layout
        except (ImportError, ModuleNotFoundError) as exc:
            return pincabos_import_classifier_unavailable(exc)

        data = request.get_json(silent=True) or {}
        zip_path = data.get("zip_path") or data.get("path") or ""
        table_dir = data.get("table_dir") or ""
        choice = data.get("choice") or ""

        if not zip_path:
            return jsonify({"ok": False, "error": "zip_path manquant"}), 400
        if not table_dir:
            return jsonify({"ok": False, "error": "table_dir manquant"}), 400
        if choice not in ("rom", "medias", "music", "ignore"):
            return jsonify({"ok": False, "error": "choice invalide"}), 400

        zp = Path(zip_path).resolve()
        td = Path(table_dir).resolve()

        allowed_zip_roots = [
            Path("/home/pinball/Downloads").resolve(),
            Path("/opt/pincabos/uploads").resolve(),
            Path("/opt/pincabos/tmp").resolve(),
            Path(pincabos_vpx_tables_dir()).resolve(),
        ]

        tables_root = Path(pincabos_vpx_tables_dir()).resolve()

        if not any(pincabos_path_inside(zp, root) for root in allowed_zip_roots):
            return jsonify({"ok": False, "error": "chemin zip non autorisé"}), 403

        if not pincabos_path_inside(td, tables_root):
            return jsonify({"ok": False, "error": "table_dir non autorisé"}), 403

        standard_dirs = [
            "table", "media", "music", "roms", "pupvideos", "altcolor",
            "altsound", "dmd", "b2s", "scripts", "config", "docs", "extras"
        ]

        for sub in standard_dirs:
            (td / sub).mkdir(parents=True, exist_ok=True)

        result = import_zip_by_choice(zp, td, choice)

        if result.get("ok"):
            result["normalize"] = normalize_table_layout(td)

            try:
                subprocess.run(
                    [str(pco_script("import_portable_normalize")), "--table", td.name],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=False,
                )
            except Exception:
                pass

        return jsonify(result)

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
# === /PinCabOS Import ZIP Analyzer API ===


# === INPUTS COMMANDER V1 - PINCABOS START ===
# Moved to modular route file by PinCabOS refactor (original lines 18659-18660).

# Moved to modular route file by PinCabOS refactor (original lines 18662-18698).

# Moved to modular route file by PinCabOS refactor (original lines 18700-18704).

# Moved to modular route file by PinCabOS refactor (original lines 18706-18729).

# Moved to modular route file by PinCabOS refactor (original lines 18731-18733).

# Moved to modular route file by PinCabOS refactor (original lines 18735-18741).

# Moved to modular route file by PinCabOS refactor (original lines 18743-18755).

# Moved to modular route file by PinCabOS refactor (original lines 18757-18767).

# Moved to modular route file by PinCabOS refactor (original lines 18769-18783).

# Moved to modular route file by PinCabOS refactor (original lines 18785-18795).

# Moved to modular route file by PinCabOS refactor (original lines 18797-18870).

# Moved to modular route file by PinCabOS refactor (original lines 18872-18878).

# Moved to modular route file by PinCabOS refactor (original lines 18880-18881).

# Moved to modular route file by PinCabOS refactor (original lines 18883-18924).


# Moved to modular route file by PinCabOS refactor (original lines 18927-18951).


# Moved to modular route file by PinCabOS refactor (original lines 18954-19312).


# Moved to modular route file by PinCabOS refactor (original lines 19315-19378).


# Moved to modular route file by PinCabOS refactor (original lines 19381-19419).


# Moved to modular route file by PinCabOS refactor (original lines 19422-19450).
# === INPUTS COMMANDER V1 - PINCABOS END ===


# Stage5A.3: route legacy retirée pour éviter doublon avec pcos_update_api_status.
# Moved to modular route file by PinCabOS refactor (original lines 19455-19488).


# Moved to modular route file by PinCabOS refactor (original lines 19491-19502).


# Moved to modular route file by PinCabOS refactor (original lines 19505-19541).


# Moved to modular route file by PinCabOS refactor (original lines 19544-19547).

# Moved to modular route file by PinCabOS refactor (original lines 19549-19784).


# Moved to modular route file by PinCabOS refactor (original lines 20218-20279).


# Moved to modular route file by PinCabOS refactor (original lines 20282-20286).


# Moved to modular route file by PinCabOS refactor (original lines 20289-20293).


# Stage5A.3: route legacy retirée pour éviter doublon avec pcos_update_api_reboot.
def pcos_update_clean_reboot():
    import os
    import subprocess
    import time
    from flask import jsonify

    unit = "pincabos-reboot-" + str(int(time.time()))

    cmd = [
        "/usr/bin/systemd-run",
        "--unit", unit,
        "--collect",
        "/bin/bash",
        "-lc",
        "sleep 1; /usr/bin/systemctl reboot"
    ]

    if os.geteuid() != 0:
        cmd = ["/usr/bin/sudo", "-n"] + cmd

    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return jsonify({"ok": True, "unit": unit, "message": "Redémarrage demandé"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# --- PinCabOS update channel check patch ---
# Moved to modular route file by PinCabOS refactor (original lines 20393-20476).


# Moved to modular route file by PinCabOS refactor (original lines 20479-20529).
# --- /PinCabOS update channel check patch ---


# Removed obsolete duplicate route block: # === PINCABOS VMTEST ROUTE ALIASES START ===


# Removed obsolete duplicate route block: # === PINCABOS VMTEST CONSOLE PAGE START ===


# === PinCabOS cab-current route aliases ===
# Compatibilité routes/menu après nettoyage Alpha 1.1.
# Ces routes ne remplacent pas les fonctions existantes; elles évitent les 404 de boutons/menu.

@app.route("/wifi")
def pincabos_alias_wifi():
    return redirect("/network", code=302)

@app.route("/screens")
def pincabos_alias_screens():
    # La vraie gestion écrans est maintenant dans GPU / Screens.
    try:
        return redirect("/gpu/screens", code=302)
    except Exception:
        return redirect("/gpu", code=302)

@app.route("/outputs")
def pincabos_alias_outputs():
    # Outputs = ancien DOF côté menu.
    return redirect("/dof", code=302)

# Moved to modular route file by PinCabOS refactor (original lines 20663-20674).


@app.route("/tools/external-disks/usb/unmount", methods=["POST"])
def pincabos_tools_usb_unmount_alias():
    # Route placeholder sûre: ne démonte rien à l’aveugle.
    return redirect("/tools", code=303)

@app.route("/tools/external-disks/smb/unmount", methods=["POST"])
def pincabos_tools_smb_unmount_alias():
    # Route placeholder sûre: ne démonte rien à l’aveugle.
    return redirect("/tools", code=303)

@app.route("/api/dof/manager/")
def pincabos_api_dof_manager_slash_alias():
    # Compatibilité avec fetch('/api/dof/manager/').
    return jsonify({"ok": True, "status": "available", "message": "DOF manager route alias active"})

# === PINCABOS LEGACY ROUTE ALIASES - BGFX MIGRATION ===
# Created by Karots Sugarpie
# Purpose:
#   Keep Alpha15/old menu URLs working after Alpha16 tools route migration.
# Safety:
#   Redirect-only aliases. No filesystem or config mutation.

@app.route("/external-disks")
@app.route("/external-disks/")
def pincabos_legacy_external_disks_alias():
    return redirect("/tools/external-disks", code=302)

@app.route("/import")
@app.route("/import/")
def pincabos_legacy_import_alias():
    return redirect("/tools", code=302)

@app.route("/tables")
@app.route("/tables/")
def pincabos_legacy_tables_alias():
    return redirect("/tools", code=302)

# === PINCABOS LEGACY ROUTE ALIASES - END ===


# === PINCABOS MENU CLOSE ACTIVE CHROME TAB START ===
@app.route("/api/menu/close-tab", methods=["POST"])
def pincabos_menu_close_tab_api():
    import os
    import subprocess
    from flask import jsonify

    helper = "/opt/pincabos/bin/pincabos-close-active-chrome-tab.sh"

    if not os.path.exists(helper):
        return jsonify({"ok": False, "error": "helper_missing", "helper": helper}), 500

    env = os.environ.copy()
    env.setdefault("DISPLAY", ":0")

    # Best effort Xauthority discovery for the pinball desktop session.
    for xa in (
        "/home/pinball/.Xauthority",
        "/var/run/lightdm/root/:0",
        "/run/user/1000/gdm/Xauthority",
        "/run/user/1000/Xauthority",
    ):
        if os.path.exists(xa):
            env.setdefault("XAUTHORITY", xa)
            break

    try:
        proc = subprocess.run(
            [helper],
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=3,
        )
        return jsonify({
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "output": proc.stdout[-2000:],
        }), (200 if proc.returncode == 0 else 500)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
# === PINCABOS MENU CLOSE ACTIVE CHROME TAB END ===


# PinCabOS dashboard-plus final display correction
# Corrects stale dashboard-plus display values without rewriting the whole dashboard.
def _pco_dashboard_plus_final_detect_vpx():
    import os
    import subprocess
    import re

    candidates = [
        "/opt/pincabos/bin/vpx-vpinfe-default.sh",
        "/home/pinball/vpx/VPinballX_BGFX",
        "/home/pinball/vpx/VPinballX_BGFX",
        "/home/pinball/vpx/VPinballX_BGFX",
        "/home/pinball/vpx/VPinballX_BGFX",
    ]

    existing = [x for x in candidates if os.path.exists(x)]
    if not existing:
        return "non détecté"

    for exe in existing:
        for arg in ("--version", "-version", "-h", "--help"):
            try:
                r = subprocess.run(
                    [exe, arg],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=3,
                    env=dict(os.environ, DISPLAY=os.environ.get("DISPLAY", ":0")),
                )
                out = (r.stdout or "").strip()
                if not out:
                    continue

                lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
                for ln in lines[:12]:
                    if re.search(r"(VPinball|Visual Pinball|VPX|VPinballX|version|standalone)", ln, re.I):
                        ln = re.sub(r"\s+", " ", ln)
                        if len(ln) > 96:
                            ln = ln[:93] + "..."
                        return ln

                # If command responded but no clear version line.
                return "installé / version non lisible"
            except Exception:
                continue

    if "/opt/pincabos/bin/vpx-vpinfe-default.sh" in existing:
        return "installé / wrapper vpx.sh"
    return "installé / version non lisible"


def _pco_dashboard_plus_final_audio_message():
    import os
    import subprocess

    cards = ""
    try:
        if os.path.exists("/proc/asound/cards"):
            cards = open("/proc/asound/cards", "r", errors="replace").read().strip()
    except Exception:
        cards = ""

    if cards and "no soundcards" not in cards.lower():
        try:
            r = subprocess.run(["aplay", "-l"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=3)
            out = (r.stdout or "").strip()
            if out and "no soundcards" not in out.lower():
                return None
        except Exception:
            return None

    return "Aucune carte audio ALSA détectée par Linux dans cette VM/session. Ce n’est pas une erreur PinCabOS si la VM n’a pas de périphérique audio attaché. Sur un cabinet réel, vérifier avec aplay -l, pactl list short sinks et wpctl status."


def _pco_dashboard_plus_final_html_fix(html):
    if not isinstance(html, str):
        return html

    vpx_label = _pco_dashboard_plus_final_detect_vpx()
    audio_msg = _pco_dashboard_plus_final_audio_message()

    # Correct stale service name.
    html = html.replace("pincabos-webapp.service", "pincabos-webapp.service")

    # Correct old VPX runtime path.
    html = html.replace("/opt/pincabos/apps/vpinball", "/opt/pincabos/apps/vpinball")

    # Correct rendered VPX version text.
    html = html.replace("VPX : non détecté", "VPX : " + vpx_label)
    html = html.replace("VPX&nbsp;: non détecté", "VPX&nbsp;: " + vpx_label)

    # Correct common HTML separated VPX value patterns.
    html = re.sub(
        r"(VPX\s*</[^>]+>\s*<[^>]+>)(non détecté|non detecte|not detected)(</[^>]+>)",
        r"\1" + vpx_label + r"\3",
        html,
        flags=re.I,
    )

    # Clarify audio if Linux has no audio device.
    if audio_msg:
        html = html.replace(
            "Aucune sortie audio ALSA détectée par le dashboard.",
            audio_msg,
        )
        html = html.replace(
            "Aucune configuration audio sauvegardée.",
            "Aucune configuration audio sauvegardée. Le dashboard ne peut pas mapper SSF V2 tant qu’aucune carte audio Linux n’est visible.",
        )

    # Make essential path labels current.
    html = html.replace("VPX runtime", "VPX runtime")
    html = html.replace("VPinFE runtime", "VPinFE runtime")

    return html


def _pco_dashboard_plus_final_install_wrapper():
    try:
        dashboard_rules = []
        for rule in list(app.url_map.iter_rules()):
            r = str(rule.rule).lower()
            if "dashboard" in r or "dashbord" in r or r == "/":
                dashboard_rules.append(rule)

        for rule in dashboard_rules:
            endpoint = rule.endpoint
            old_view = app.view_functions.get(endpoint)
            if not old_view or getattr(old_view, "_pco_dashboard_plus_final_wrapped", False):
                continue

            def _make_wrapper(fn):
                def _wrapped(*args, **kwargs):
                    resp = fn(*args, **kwargs)

                    try:
                        flask_resp = app.make_response(resp)
                        ctype = flask_resp.headers.get("Content-Type", "")
                        if "text/html" in ctype or ctype.startswith("text/") or ctype == "":
                            data = flask_resp.get_data(as_text=True)
                            fixed = _pco_dashboard_plus_final_html_fix(data)
                            if fixed != data:
                                flask_resp.set_data(fixed)
                                flask_resp.headers["Content-Length"] = str(len(flask_resp.get_data()))
                        return flask_resp
                    except Exception:
                        return resp

                _wrapped._pco_dashboard_plus_final_wrapped = True
                _wrapped.__name__ = getattr(fn, "__name__", "dashboard_plus_final_wrapped")
                return _wrapped

            app.view_functions[endpoint] = _make_wrapper(old_view)

        print("GO: dashboard-plus final correction wrapper installed")
    except Exception as exc:
        print("NOGO: dashboard-plus final correction wrapper failed:", exc)


_pco_dashboard_plus_final_install_wrapper()


# === PINCABOS MODULAR ROUTES REGISTRATION START ===
# Registration occurs after the core helpers are defined so modules can reuse the one canonical layout and services.
for _pco_module in (
    pco_audio_routes,
    pco_inputs_routes,
    pco_firstrun_routes,
    pco_dev_admin_routes,
    pco_exports_routes,
    pco_backupcfg_routes,
):
    _pco_module.register(app, globals())
del _pco_module
# === PINCABOS MODULAR ROUTES REGISTRATION END ===


# PINCABOS_LIVE_TABLE_STATUS_CARD_V2
from pincabos_live_table_status import register_live_table_status
register_live_table_status(app)


# PINCABOS_EXTERNAL_DISKS_MENU_V2
# Ajoute le lien sans recopier la classe active de Lecteurs SMB.
@app.after_request
def pincabos_external_disks_menu_link(response):
    try:
        from flask import request as _request
        import re as _re
        from html import escape as _html_escape

        if _request.path.rstrip("/") != "/tools/commander":
            return response

        if response.status_code != 200 or response.is_streamed:
            return response

        if response.mimetype != "text/html":
            return response

        body = response.get_data(as_text=True)

        if 'data-pcx-external-disks-menu="1"' in body:
            return response

        pattern = _re.compile(
            r'(?P<link>'
            r'<a\b'
            r'(?P<attrs>[^>]*\bhref\s*=\s*(?P<quote>["\'])'
            r'/tools/commander\?root=Lecteurs(?:%20|\+| )SMB[^"\']*(?P=quote)[^>]*)>'
            r'(?P<label>.*?)'
            r'</a>)',
            _re.IGNORECASE | _re.DOTALL,
        )

        match = pattern.search(body)
        if not match:
            return response

        visible = _re.sub(r"<[^>]+>", " ", match.group("label"))
        visible = " ".join(visible.split()).lower()

        if "lecteurs smb" not in visible:
            return response

        class_match = _re.search(
            r'\bclass\s*=\s*(["\'])(.*?)\1',
            match.group("attrs"),
            _re.IGNORECASE | _re.DOTALL,
        )

        css_class = class_match.group(2) if class_match else "pcx-btn"

        # Enleve toute classe de selection ou etat actif copiee du SMB.
        css_class = " ".join(
            token for token in css_class.split()
            if not any(
                flag in token.lower()
                for flag in ("active", "selected", "current")
            )
        )

        css_class = _html_escape(css_class or "pcx-btn", quote=True)

        link = (
            '\n<a class="' + css_class + '" '
            'href="/tools/external-disks" '
            'data-pcx-external-disks-menu="1" '
            'title="Gerer le stockage : disque interne, cles USB et partages SMB">'
            '💾 Stockage</a>'
        )

        response.set_data(body[:match.end()] + link + body[match.end():])
        return response

    except Exception:
        return response

# PINCABOS_SMB_SAFE_MOUNT_V3
# Ne modifie pas la route existante : surcharge seulement son helper et
# transforme toute exception non geree en page lisible avec journal detaille.
def pco_smb_mount_helper_command(source, mount_point, cred_file):
    return [
        "/usr/bin/sudo",
        "-n",
        "/usr/local/sbin/pincabos-smb-mount",
        str(source),
        str(mount_point),
        str(cred_file),
    ]


_pincabos_smb_mount_original = app.view_functions.get(
    "tools_external_disks_smb_mount"
)

if _pincabos_smb_mount_original is not None:
    def pincabos_smb_mount_safe_view():
        try:
            return _pincabos_smb_mount_original()
        except Exception as exc:
            app.logger.exception(
                "PINCABOS SMB: exception non geree dans la route de montage"
            )
            detail = f"{type(exc).__name__}: {exc}"
            return page("Montage SMB échoué", f"""
<div class="card">
  <h2>Montage SMB échoué</h2>
  <p class="bad">
    La page a intercepté une erreur interne au lieu de retourner une erreur 500.
  </p>
  <p><strong>Détail réel :</strong></p>
  <pre>{esc(detail)}</pre>
  <p>
    <a class="button" href="/tools/external-disks">Retour</a>
  </p>
</div>
""")

    app.view_functions["tools_external_disks_smb_mount"] = (
        pincabos_smb_mount_safe_view
    )


# PINCABOS_EXTERNAL_DISKS_UNMOUNT_V4
# Remplace seulement les endpoints de demontage, sans toucher au montage SMB.
def _pincabos_direct_mount_child(root_text, requested_name):
    from pathlib import Path

    name = (requested_name or "").strip()

    if (
        not name
        or name in {".", ".."}
        or "/" in name
        or "\\" in name
        or "\x00" in name
    ):
        return None

    root = Path(root_text).resolve()
    target = (root / name).resolve(strict=False)

    if target.parent != root:
        return None

    return target


def _pincabos_external_disk_result(title, ok, detail, back_url):
    cls = "ok" if ok else "bad"
    label = "Démontage réussi" if ok else "Démontage échoué"

    return page(title, f"""
<div class="card">
  <h2>{label}</h2>
  <p class="{cls}">{esc(detail)}</p>
  <p>
    <a class="button" href="{esc(back_url)}">Retour</a>
  </p>
</div>
""")


def _pincabos_replace_unmount_route(rule_path, form_key, root_path, helper_path, label):
    endpoint = None

    for rule in app.url_map.iter_rules():
        if rule.rule == rule_path and "POST" in rule.methods:
            endpoint = rule.endpoint
            break

    if endpoint is None:
        return

    def safe_unmount_view():
        import subprocess

        target = _pincabos_direct_mount_child(
            root_path,
            request.form.get(form_key, ""),
        )

        if target is None:
            return _pincabos_external_disk_result(
                "Gestion du stockage",
                False,
                f"Nom de lecteur {label} invalide.",
                "/tools/external-disks",
            )

        try:
            result = subprocess.run(
                [
                    "/usr/bin/sudo",
                    "-n",
                    helper_path,
                    str(target),
                ],
                capture_output=True,
                text=True,
                timeout=45,
            )

            output = (result.stdout + "\n" + result.stderr).strip()

        except subprocess.TimeoutExpired:
            return _pincabos_external_disk_result(
                "Gestion du stockage",
                False,
                f"Le démontage {label} a dépassé le délai.",
                "/tools/external-disks",
            )

        if result.returncode != 0:
            return page("Gestion du stockage", f"""
<div class="card">
  <h2>Démontage {esc(label)} échoué</h2>
  <p class="bad">Le lecteur est peut-être encore utilisé.</p>
  <h3>Détail</h3>
  <pre>{esc(output or "Aucun détail retourné.")}</pre>
  <p><a class="button" href="/tools/external-disks">Retour</a></p>
</div>
""")

        # Le mot de passe SMB ne reste pas apres un demontage reussi.
        if label == "SMB":
            try:
                cred = (
                    Path("/home/pinball/.config/pincabos/smb")
                    / (target.name + ".cred")
                )
                cred.unlink(missing_ok=True)
            except Exception:
                pass

        return _pincabos_external_disk_result(
            "Gestion du stockage",
            True,
            output or f"Lecteur {label} démonté.",
            "/tools/external-disks",
        )

    app.view_functions[endpoint] = safe_unmount_view


_pincabos_replace_unmount_route(
    "/tools/external-disks/smb/unmount",
    "drive_name",
    "/home/pinball/NetworkDrives",
    "/usr/local/sbin/pincabos-smb-umount",
    "SMB",
)


# PINCABOS_SMB_DISCONNECT_BUTTON_V1
@app.route("/tools/external-disks/smb/disconnect", methods=["POST"])
def pincabos_tools_smb_disconnect_button_v1():
    import datetime
    import shutil
    import subprocess

    target = _pincabos_direct_mount_child(
        "/home/pinball/NetworkDrives",
        request.form.get("drive_name", ""),
    )

    if target is None:
        return _pincabos_external_disk_result(
            "Gestion du stockage",
            False,
            "Nom de lecteur SMB invalide.",
            "/tools/external-disks",
        )

    messages = []

    try:
        mounted = subprocess.run(
            ["/usr/bin/mountpoint", "-q", str(target)],
            capture_output=True,
            text=True,
            timeout=10,
        ).returncode == 0
    except Exception:
        mounted = False

    if mounted:
        try:
            result = subprocess.run(
                [
                    "/usr/bin/sudo",
                    "-n",
                    "/usr/local/sbin/pincabos-smb-umount",
                    str(target),
                ],
                capture_output=True,
                text=True,
                timeout=45,
            )
            output = (result.stdout + "\n" + result.stderr).strip()
        except subprocess.TimeoutExpired:
            return _pincabos_external_disk_result(
                "Gestion du stockage",
                False,
                "La déconnexion SMB a dépassé le délai pendant le démontage.",
                "/tools/external-disks",
            )

        if result.returncode != 0:
            return page("Gestion du stockage", f"""
<div class="card">
  <h2>Déconnexion SMB échouée</h2>
  <p class="bad">Le lecteur est peut-être encore utilisé.</p>
  <h3>Détail</h3>
  <pre>{esc(output or "Aucun détail retourné.")}</pre>
  <p><a class="button" href="/tools/external-disks">Retour</a></p>
</div>
""")

        messages.append(output or "Montage SMB arrêté.")

    try:
        cred = Path("/home/pinball/.config/pincabos/smb") / (target.name + ".cred")
        if cred.exists():
            cred.unlink()
            messages.append("Identifiants SMB supprimés.")
    except Exception as e:
        messages.append(f"Identifiants SMB non supprimés: {e}")

    try:
        if target.exists() and target.is_dir():
            still_mounted = subprocess.run(
                ["/usr/bin/mountpoint", "-q", str(target)],
                capture_output=True,
                text=True,
                timeout=10,
            ).returncode == 0

            if still_mounted:
                return _pincabos_external_disk_result(
                    "Gestion du stockage",
                    False,
                    "Le lecteur SMB est encore monté, entrée conservée.",
                    "/tools/external-disks",
                )

            try:
                target.rmdir()
                messages.append("Entrée SMB retirée de la liste.")
            except OSError:
                archive_root = Path("/home/pinball/.config/pincabos/smb-disconnected")
                archive_root.mkdir(parents=True, exist_ok=True)
                stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
                archive_target = archive_root / f"{target.name}-{stamp}"
                shutil.move(str(target), str(archive_target))
                messages.append(f"Dossier local non vide déplacé vers {archive_target}.")
    except Exception as e:
        return _pincabos_external_disk_result(
            "Gestion du stockage",
            False,
            f"Déconnexion partielle: {e}",
            "/tools/external-disks",
        )

    return _pincabos_external_disk_result(
        "Gestion du stockage",
        True,
        "\n".join(messages) or "Lecteur SMB déconnecté.",
        "/tools/external-disks",
    )


_pincabos_replace_unmount_route(
    "/tools/external-disks/usb/unmount",
    "usb_name",
    "/mnt/pincab-usb",
    "/usr/local/sbin/pincabos-usb-umount",
    "USB",
)


# PINCABOS_PCX_LIVE_VIEWER_V1
# Vue en nouvelle fenetre + lecture media + editeur texte securise.


# PINCABOS_FULLDMD_EQUAL_CARDS_V1
# Rend les deux cartes Calibration FullDMD / DMD global égales.
@app.after_request
def pincabos_fulldmd_equal_calibration_cards(response):
    try:
        from flask import request as _request

        if _request.path.rstrip("/") != "/fulldmd":
            return response

        if response.status_code != 200 or response.is_streamed:
            return response

        if response.mimetype != "text/html":
            return response

        body = response.get_data(as_text=True)

        if 'id="pincabos-fulldmd-equal-cards-v1"' in body:
            return response

        style = """
<style id="pincabos-fulldmd-equal-cards-v1">
.fulldmd-calibration-grid {
  align-items: stretch !important;
}

.fulldmd-calibration-grid > .card {
  height: 100%;
  min-height: 100%;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
}

.fulldmd-calibration-grid > .card .fulldmd-actions-column {
  margin-top: auto;
}

@media (max-width: 900px) {
  .fulldmd-calibration-grid > .card {
    height: auto;
    min-height: 0;
  }
}
</style>
"""

        if "</head>" in body:
            body = body.replace("</head>", style + "\n</head>", 1)
        elif "</body>" in body:
            body = body.replace("</body>", style + "\n</body>", 1)
        else:
            body += style

        response.set_data(body)
        return response

    except Exception:
        return response

# PINCABOS_FOOTER_LAYOUT_V14_2

# PINCABOS_FULLDMD_AUTOARRANGE_WEB_V1
try:
    from pincabos_fulldmd_autoarrange import register_fulldmd_autoarrange
    register_fulldmd_autoarrange(app, page, esc)
except Exception as _pincabos_fulldmd_autoarrange_error:
    try:
        log(f"FullDMD AutoArrange routes unavailable: {_pincabos_fulldmd_autoarrange_error}")
    except Exception:
        pass
# PINCABOS_FULLDMD_AUTOARRANGE_WEB_V1_END

# PINCABOS_APPEARANCE_GLOBAL_INJECTOR_V1
from pincabos_appearance_global import install_appearance_global
install_appearance_global(app)


# PINCABOS_BATCH_TRANSFER_V1_REGISTER
try:
    from pincabos_batch_transfer import register_pincabos_batch_transfer
    register_pincabos_batch_transfer(app, globals())
except Exception:
    app.logger.exception("PinCabOS Batch Import/Export registration failed")


# PINCABOS_AUDIO_VOLUME_API_ONLY_V2 BEGIN
try:
    from pincabos_audio_volume_widget import register as _pincabos_audio_volume_widget_register
    _pincabos_audio_volume_widget_register(app)
except Exception as _pincabos_audio_volume_widget_error:
    try:
        app.logger.exception("PinCabOS audio volume API registration failed: %s", _pincabos_audio_volume_widget_error)
    except Exception:
        pass
# PINCABOS_AUDIO_VOLUME_API_ONLY_V2 END

# === PINCABOS WEBAPP MAIN ENTRYPOINT END-OF-FILE V1 ===

# === PINCABOS_IMAGE_STUDIO_V11_REGISTER START ===
try:
    from pincabos_image_studio import register as _pincabos_image_studio_register
    _pincabos_image_studio_register(app)
except Exception as _pincabos_image_studio_error:
    try:
        app.logger.exception("PinCabOS Image Studio registration failed: %s", _pincabos_image_studio_error)
    except Exception:
        pass
# === PINCABOS_IMAGE_STUDIO_V11_REGISTER END ===


# === PINCABOS_ABOUT_HELP_REFACTOR_V1_REGISTER START ===
try:
    import importlib.util as _pco_ah_importlib_util
    from pathlib import Path as _pco_ah_Path

    _pco_ah_path = _pco_ah_Path(__file__).with_name("PinCabOS-AboutHelp.py")
    _pco_ah_spec = _pco_ah_importlib_util.spec_from_file_location("pincabos_abouthelp", str(_pco_ah_path))

    if _pco_ah_spec and _pco_ah_spec.loader:
        _pco_ah_mod = _pco_ah_importlib_util.module_from_spec(_pco_ah_spec)
        _pco_ah_spec.loader.exec_module(_pco_ah_mod)
        _pco_ah_mod.register(
            app,
            page_func=page,
            esc_func=esc,
            pco_path_text_func=pco_path_text,
            pincabos_version_func=pincabos_version,
        )
    else:
        raise RuntimeError("Unable to load PinCabOS-AboutHelp.py")
except Exception as _pco_ah_error:
    try:
        app.logger.exception("PinCabOS About/Help registration failed: %s", _pco_ah_error)
    except Exception:
        pass
# === PINCABOS_ABOUT_HELP_REFACTOR_V1_REGISTER END ===

# PINCABOS_ZEDMD_REGISTER BEGIN
try:
    from pincabos_zedmd import register as _pincabos_zedmd_register
    _pincabos_zedmd_register(app, page, esc)
except Exception as _pincabos_zedmd_error:
    try:
        app.logger.exception("PinCabOS ZeDMD registration failed: %s", _pincabos_zedmd_error)
    except Exception:
        pass
# PINCABOS_ZEDMD_REGISTER END

# PINCABOS_VPS_REGISTER BEGIN
try:
    from pincabos_webapp_vps import register as _pincabos_vps_register
    _pincabos_vps_register(app, page, esc)
except Exception as _pincabos_vps_error:
    try:
        app.logger.exception("PinCabOS VPS registration failed: %s", _pincabos_vps_error)
    except Exception:
        pass
# PINCABOS_VPS_REGISTER END

# PINCABOS_RESEAU_REGISTER BEGIN
try:
    from pincabos_webapp_network import register as _pincabos_network_register
    _pincabos_network_register(app, page, esc)
except Exception as _pincabos_network_error:
    try:
        app.logger.exception("PinCabOS network registration failed: %s", _pincabos_network_error)
    except Exception:
        pass
# PINCABOS_RESEAU_REGISTER END

# PINCABOS_DUDESCAB_CONFIG_PAGE_V3_REGISTER BEGIN
try:
    from pincabos_dudescab_config import register as _pincabos_dudescab_config_register
    _pincabos_dudescab_config_register(app, page, esc)
    from pincabos_dudescab_protocol import register as _pincabos_dudescab_protocol_register
    _pincabos_dudescab_protocol_register(app)
except Exception as _pincabos_dudescab_config_error:
    try:
        app.logger.exception("PinCabOS DudesCabConfig V3 registration failed: %s", _pincabos_dudescab_config_error)
    except Exception:
        pass
# PINCABOS_DUDESCAB_CONFIG_PAGE_V3_REGISTER END

# PINCABOS_DOF_HARDWARE_PAGE_V1_REGISTER BEGIN
try:
    from pincabos_dof_hardware import register as _pincabos_dof_hardware_register
    _pincabos_dof_hardware_register(app, page, esc)
except Exception as _pincabos_dof_hardware_error:
    try:
        app.logger.exception("PinCabOS DOF hardware page registration failed: %s", _pincabos_dof_hardware_error)
    except Exception:
        pass
# PINCABOS_DOF_HARDWARE_PAGE_V1_REGISTER END


# PINCABOS_NTWKDRV_MODULE_LOADER_V1
try:
    import importlib.util as _pco_ntwkdrv_importlib_util
    from pathlib import Path as _pco_ntwkdrv_Path

    _pco_ntwkdrv_path = _pco_ntwkdrv_Path(__file__).with_name("PinCabOS-NtwkDRV.py")
    _pco_ntwkdrv_spec = _pco_ntwkdrv_importlib_util.spec_from_file_location(
        "pincabos_ntwkdrv_external",
        str(_pco_ntwkdrv_path),
    )
    _pco_ntwkdrv_mod = _pco_ntwkdrv_importlib_util.module_from_spec(_pco_ntwkdrv_spec)
    _pco_ntwkdrv_spec.loader.exec_module(_pco_ntwkdrv_mod)
    _pco_ntwkdrv_mod.register(app=app, page=page, esc=esc, shlex_quote=shlex_quote)
except Exception as _pco_ntwkdrv_e:
    print("WARN: PinCabOS-NtwkDRV module load failed:", _pco_ntwkdrv_e)

# PINCABOS_EXPLORER_INSTALL_PINCABOS_LOADER_V1
try:
    import importlib.util as _pco_explorer_install_importlib_util
    from pathlib import Path as _pco_explorer_install_Path

    _pco_explorer_install_path = _pco_explorer_install_Path(__file__).with_name("PinCabOS-ExplorerInstall.py")
    _pco_explorer_install_spec = _pco_explorer_install_importlib_util.spec_from_file_location(
        "pincabos_explorer_install_external",
        str(_pco_explorer_install_path),
    )
    _pco_explorer_install_mod = _pco_explorer_install_importlib_util.module_from_spec(_pco_explorer_install_spec)
    _pco_explorer_install_spec.loader.exec_module(_pco_explorer_install_mod)
    _pco_explorer_install_mod.register(
        app=app,
        page=page,
        esc=esc,
        context_globals=globals(),
    )
except Exception as _pco_explorer_install_e:
    print("WARN: PinCabOS ExplorerInstall module load failed:", _pco_explorer_install_e)

# PINCABOS_PUPPACK_EXPLORER_V1
# Bouton "Options d'ecrans", affiche uniquement dans un dossier de PuP-Pack.
# Pose apres l'Explorateur pour envelopper la vue deja enveloppee par lui.
try:
    from puppack_options import install_puppack_explorer_button as _pco_puppack_explorer
    print("GO: PinCabOS PuP-Pack explorer button", _pco_puppack_explorer(app))
except Exception as _pco_puppack_explorer_e:
    print("WARN: PinCabOS PuP-Pack explorer button failed:", _pco_puppack_explorer_e)

# PINCABOS_PACKAGE_ICON_LOADER_V1
try:
    import importlib.util as _pco_package_icon_importlib_util
    from pathlib import Path as _pco_package_icon_Path

    _pco_package_icon_path = _pco_package_icon_Path(__file__).with_name("PinCabOS-PackageIcon.py")
    _pco_package_icon_spec = _pco_package_icon_importlib_util.spec_from_file_location(
        "pincabos_package_icon_external",
        str(_pco_package_icon_path),
    )
    _pco_package_icon_mod = _pco_package_icon_importlib_util.module_from_spec(_pco_package_icon_spec)
    _pco_package_icon_spec.loader.exec_module(_pco_package_icon_mod)
    _pco_package_icon_mod.register(app)
except Exception as _pco_package_icon_e:
    print("WARN: PinCabOS PackageIcon module load failed:", _pco_package_icon_e)

# PINCABOS_EXPLORER_TABLE_TEST_CENTER_V1_REGISTER
try:
    import pincabos_explorer_table_test as _pco_explorer_table_test
    _pco_explorer_table_test.register(
        app,
        detect_batch=globals().get("pincabos_detect_batch"),
    )
except Exception as _pco_explorer_table_test_error:
    print(
        "WARN: Explorer Table Test Center load failed:",
        _pco_explorer_table_test_error,
    )

# PINCABOS_MAIN_ENTRYPOINT_LAST_V1

# PINCABOS_LINK_UI_V1_START
from pincaboslink import register_pincaboslink
register_pincaboslink(app, page)
# PINCABOS_LINK_UI_V1_END

if __name__ == "__main__":
    app.run(
        host=os.environ.get("PINCABOS_WEB_HOST", os.environ.get("PCO_WEB_HOST", "127.0.0.1")),
        port=int(os.environ.get("PINCABOS_WEB_PORT", os.environ.get("PCO_WEB_PORT", "5055"))),
        debug=False,
    )
