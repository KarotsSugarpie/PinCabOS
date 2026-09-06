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
    pincabos_version,
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
# Helpers GPU lus dans les globals d'app.py par pincabos_webapp_firstrun (runtime_globals,
# actions de la première exécution) : réexportés ici, même nom, même objet.
from pincabos_webapp_gpu import (  # noqa: E402
    gpu_info_text,
    pincabos_gpu_apply_config_to_vpinfe,
    pincabos_gpu_apply_config_to_vpx,
)


# PINCABOS_WEBAPP_MODULES_V1 : contrôle des services, du processus VPX et versions dans leur module.
import pincabos_webapp_systeme as pco_systeme_routes

pco_systeme_routes.register(app, page)


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


# PINCABOS_WEBAPP_MODULES_V1 : identifiants admin, page admin composée, supporters, version.json dans leur module.
import pincabos_webapp_admin_pages as pco_admin_pages_routes

pco_admin_pages_routes.register(app, page)
# Lus dans les globals d'app.py par pincabos_webapp_dev_admin (runtime_globals) et par page() : réexportés, mêmes objets.
from pincabos_webapp_admin_pages import (  # noqa: E402
    pincabos_admin_page,
    pincabos_footer_supporters_inline_html,
    ADMIN_LOGIN_USER,
    ADMIN_LOGIN_PASS,
    PINCABOS_DEFAULT_ADMIN_USER,
    PINCABOS_DEFAULT_ADMIN_PASS,
    PINCABOS_DEFAULT_DEV_USER,
    PINCABOS_DEFAULT_DEV_PASS,
    PINCABOS_ADMIN_CREDENTIALS_ARE_DEFAULT,
    PINCABOS_ADMIN_UNREADABLE_SECRETS,
)


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


# === PINCABOS FOOTER ABOUT SUPPORTERS END ===


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


# PINCABOS_WEBAPP_MODULES_V1 : gestion du stockage (USB, SMB) dans son module, une seule vue par chemin.
import pincabos_webapp_disques as pco_disques_routes

pco_disques_routes.register(app, page)


# PINCABOS_WEBAPP_MODULES_V1 : Commander (gestionnaire de fichiers, visionneuse live) dans son module.
import pincabos_webapp_commander as pco_commander_routes

pco_commander_routes.register(app, page)


# PINCABOS_WEBAPP_MODULES_V1 : export de tables dans son module.
import pincabos_webapp_export as pco_export_routes

pco_export_routes.register(app, page)
# Helpers d'export lus dans les globals d'app.py par pincabos_batch_transfer (app_globals[...])
# et pincabos_webapp_exports (runtime_globals) : réexportés ici, même nom, même objet.
from pincabos_webapp_export import (  # noqa: E402
    pincabos_write_full_folder_export_manifest,
    pincabos_zip_full_table_folder,
    pincabos_export_safe_filename,
    pincabos_detect_vpsid_for_export,
    pincabos_table_export_dirs,
    pincabos_export_should_exclude_relative,
)


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


# --- PinCabOS update channel check patch ---
# Moved to modular route file by PinCabOS refactor (original lines 20393-20476).


# Moved to modular route file by PinCabOS refactor (original lines 20479-20529).
# --- /PinCabOS update channel check patch ---


# Removed obsolete duplicate route block: # === PINCABOS VMTEST ROUTE ALIASES START ===


# Removed obsolete duplicate route block: # === PINCABOS VMTEST CONSOLE PAGE START ===


# === PinCabOS cab-current route aliases ===
# Compatibilité routes/menu après nettoyage Alpha 1.1.
# Ces routes ne remplacent pas les fonctions existantes; elles évitent les 404 de boutons/menu.

# PINCABOS_WEBAPP_MODULES_V1 : alias historiques et fermeture d'onglet dans leur module.
import pincabos_webapp_alias as pco_alias_routes

pco_alias_routes.register(app, page)


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
