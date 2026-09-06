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


# PINCABOS_WEBAPP_MODULES_V1 : bille VPX (cabinet, simple, UserBalls) dans son module.
import pincabos_webapp_vpxball as pco_vpxball_routes

pco_vpxball_routes.register(app, page)


# === PINCABOS AUDIO WAV STOP ROUTE FIX START ===
# Moved to modular route file by PinCabOS refactor (original lines 14990-15004).
# === PINCABOS AUDIO WAV STOP ROUTE FIX END ===


# /tools route is registered from tools.py
# Moved to modular route file by PinCabOS refactor (original lines 15010-15044).


# PINCABOS_WEBAPP_MODULES_V1 : import de tables (pages et API) dans son module.
import pincabos_webapp_import as pco_import_routes

pco_import_routes.register(app, page)
# Lu dans les globals d'app.py par PinCabOS-ExplorerInstall (context_globals) : réexporté, même objet.
from pincabos_webapp_import import pincabos_manifest_table_folder_from_archive  # noqa: E402


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


# PINCABOS_WEBAPP_MODULES_V1 : export de tables dans son module.
import pincabos_webapp_export as pco_export_routes

pco_export_routes.register(app, page)


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
