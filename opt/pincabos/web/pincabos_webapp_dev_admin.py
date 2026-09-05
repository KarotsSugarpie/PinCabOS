# PinCabOS WebApp module: Developer feedback and administrator routes.
# Generated from the monolithic app.py refactor.
# The host app injects legacy shared helpers during register().
from __future__ import annotations

import glob
import hmac
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













@route("/dev/logout", methods=["GET", "POST"])
def pincabos_dev_logout_page_final():
    session.pop("pincabos_dev_logged", None)
    session.pop("pincabos_dev_auth", None)
    session.pop("dev_logged_in", None)
    session.pop("dev_auth", None)
    session.modified = True
    return redirect("/about")


@route("/dev", methods=["GET", "POST"])
def pincabos_dev_page_remote():
    if not pincabos_dev_is_logged():
        return pincabos_dev_login_page()

    info = pincabos_dev_sysinfo_remote()
    cfg = pincabos_feedback_config()
    feedback_online, feedback_status = pincabos_feedback_watchdog()
    feedback_color = "#00ff99" if feedback_online else "#ff4444"
    feedback_dot = "🟢" if feedback_online else "🔴"
    feedback_label = "Online" if feedback_online else "Offline"

    return page("Développeur", f"""
<div class="card">
  <h2>Rapport testeur PinCabOS</h2>

  <p>
    Utilise ce formulaire pour signaler un problème, partager une idée ou proposer une solution
    pendant les tests de PinCabOS.
  </p>

  <p class="warn">
    Les réponses sont envoyées vers le serveur central du projet.
    Aucune base de données de rapports n’est distribuée avec PinCabOS.
  </p>

  <p>
    <strong>Serveur feedback :</strong>
    <code>{esc(cfg.get("PINCABOS_FEEDBACK_URL", "non configuré"))}</code>
  </p>

  <div style="margin:12px 0; padding:12px; border-radius:12px; background:rgba(0,0,0,0.25); border:1px solid rgba(255,255,255,0.12);">
    <strong>État serveur :</strong>
    <span style="color:{feedback_color}; font-weight:bold;">
      {feedback_dot} {feedback_label}
    </span>
    <br>
    <small style="opacity:0.85;">{esc(feedback_status)}</small>
  </div>

  <p>
    <a class="button secondary" href="/about">Retour À propos</a>

    <form method="post" action="/dev/cleanup-nosnap" style="display:inline;" onsubmit="return confirm('Détruire les fichiers inutiles maintenant ? Aucun snapshot ne sera créé. Continuer ?');">
      <button class="button" type="submit" style="background:#b00020;border-color:#ff4d4d;color:white;">
        Détruire les fichiers inutiles
      </button>
    </form>
  </p>
</div>

<div class="card" style="margin-top:20px;">
  <h2>Informations système détectées</h2>

  <p><strong>Hostname :</strong> <code>{esc(info["hostname"])}</code></p>
  <p><strong>IP :</strong> <code>{esc(info["ip_address"])}</code></p>
  <p><strong>OS :</strong> <code>{esc(info["os_version"])}</code></p>
  <p><strong>Kernel :</strong> <code>{esc(info["kernel_version"])}</code></p>
  <p><strong>Uptime :</strong> <code>{esc(info["uptime"])}</code></p>
  <p><strong>Timezone :</strong> <code>{esc(info["timezone"])}</code></p>
  <p><strong>Heure locale :</strong> <code>{esc(info["local_time"])}</code></p>
  <p><strong>PinCabOS :</strong> <code>{esc(info["pincabos_version"])}</code></p>
  <p><strong>VPX :</strong> <code>{esc(info["vpx_version"])}</code></p>
  <p><strong>VPinFE :</strong> <code>{esc(info["vpinfe_version"])}</code></p>
</div>

<div class="card" style="margin-top:20px;">
  <h2>Formulaire</h2>

  <form method="post" action="/dev/submit">
    <label>Prénom réel *</label><br>
    <input name="first_name" required style="width:95%; padding:10px; margin:6px 0;"><br>

    <label>Nom réel *</label><br>
    <input name="last_name" required style="width:95%; padding:10px; margin:6px 0;"><br>

    <label>Surnom / pseudo optionnel</label><br>
    <input name="nickname" style="width:95%; padding:10px; margin:6px 0;"><br>

    <label>Courriel optionnel</label><br>
    <input name="email" type="email" style="width:95%; padding:10px; margin:6px 0;"><br>

    <label>Type de rapport</label><br>
    <select name="report_type" style="width:95%; padding:10px; margin:6px 0;">
      <option value="Problème">Problème</option>
      <option value="Idée">Idée</option>
      <option value="Amélioration">Amélioration</option>
      <option value="Solution">Solution</option>
      <option value="Autre">Autre</option>
    </select><br>

    <label>Fonction concernée</label><br>
    <select name="affected_area" style="width:95%; padding:10px; margin:6px 0;">
      <option value="Dashboard">Dashboard</option>
      <option value="Import table">Import table</option>
      <option value="Export table">Export table</option>
      <option value="PinCab Explorer">PinCab Explorer</option>
      <option value="FullDMD">FullDMD</option>
      <option value="GPU / Écrans">GPU / Écrans</option>
      <option value="DOF">DOF</option>
      <option value="Réseau">Réseau</option>
      <option value="VPinFE">VPinFE</option>
      <option value="VPX">VPX</option>
      <option value="Installation / Rufus">Installation / Rufus</option>
      <option value="Autre">Autre</option>
    </select><br>

    <label>Gravité</label><br>
    <select name="severity" style="width:95%; padding:10px; margin:6px 0;">
      <option value="Info">Info</option>
      <option value="Mineur">Mineur</option>
      <option value="Moyen">Moyen</option>
      <option value="Bloquant">Bloquant</option>
      <option value="Crash">Crash</option>
    </select><br>

    <label>Titre court *</label><br>
    <input name="title" required style="width:95%; padding:10px; margin:6px 0;"><br>

    <label>Commentaires / détails *</label><br>
    <textarea name="comments" required rows="8" style="width:95%; padding:10px; margin:6px 0;"></textarea><br>

    <label>
      <input type="checkbox" name="has_solution" value="1">
      J’ai une solution ou une piste pour ce problème
    </label><br><br>

    <label>Solution proposée / piste</label><br>
    <textarea name="solution_text" rows="5" style="width:95%; padding:10px; margin:6px 0;"></textarea><br>

    <label>
      <input type="checkbox" name="consent_alpha" value="1" required>
      Je comprends que PinCabOS est en développement Alpha, que certaines fonctions peuvent changer,
      et j’accepte que ce rapport technique soit envoyé au serveur central PinCabOS pour améliorer le projet.
    </label><br><br>

    <button class="button" type="submit">Envoyer le rapport</button>
  </form>
</div>

<div class="card" style="margin-top:20px;">
  <h2>Snapshot technique envoyé avec le rapport</h2>
  <pre>{esc(info["dashboard_snapshot"])}</pre>
</div>
""")




def pincabos_dev_login_page(error=""):
    return page("Connexion développeur", f"""
<div class="card">
  <h2>Connexion développeur PinCabOS</h2>

  <p>
    Cette section est réservée aux testeurs autorisés du projet PinCabOS.
  </p>

  <form method="post" action="/dev/login">
    <label>Login</label><br>
    <input name="username" autocomplete="username" required style="width:320px; max-width:95%; padding:10px; margin:6px 0;"><br>

    <label>Mot de passe</label><br>
    <input name="password" type="password" autocomplete="current-password" required style="width:320px; max-width:95%; padding:10px; margin:6px 0;"><br>

    <button class="button" type="submit">Entrer</button>
    <a class="button secondary" href="/about">Retour À propos</a>
  </form>

  <p class="bad">{esc(error)}</p>
</div>
""")


def pincabos_feedback_config():
    """
    Config feedback Dev.
    URL globale officielle: https://dev.pincabos.cc
    Garde les clefs historiques en MAJUSCULES car la page /dev les lit déjà.
    """
    cfg = {
        "PINCABOS_FEEDBACK_URL": "https://dev.pincabos.cc",
        "PINCABOS_FEEDBACK_STATUS_URL": "https://dev.pincabos.cc/",
        "PINCABOS_FEEDBACK_SUBMIT_URL": "https://dev.pincabos.cc/pincabos-feedback/submit",
    }

    try:
        local_cfg = Path("/opt/pincabos/config/feedback-server.json")
        if local_cfg.exists():
            d = json.loads(local_cfg.read_text(errors="replace"))

            # Supporte ancien format lower-case.
            if d.get("feedback_url"):
                cfg["PINCABOS_FEEDBACK_URL"] = str(d.get("feedback_url"))
            if d.get("status_url"):
                cfg["PINCABOS_FEEDBACK_STATUS_URL"] = str(d.get("status_url"))
            if d.get("submit_url"):
                cfg["PINCABOS_FEEDBACK_SUBMIT_URL"] = str(d.get("submit_url"))

            # Supporte aussi format historique uppercase.
            for k in list(cfg):
                if d.get(k):
                    cfg[k] = str(d.get(k))
    except Exception:
        pass

    # Forcer la globale demandée si la config est vide/non configurée.
    if not cfg.get("PINCABOS_FEEDBACK_URL") or cfg.get("PINCABOS_FEEDBACK_URL") == "non configuré":
        cfg["PINCABOS_FEEDBACK_URL"] = "https://dev.pincabos.cc"
    if not cfg.get("PINCABOS_FEEDBACK_STATUS_URL"):
        cfg["PINCABOS_FEEDBACK_STATUS_URL"] = cfg["PINCABOS_FEEDBACK_URL"].rstrip("/") + "/"
    if not cfg.get("PINCABOS_FEEDBACK_SUBMIT_URL"):
        cfg["PINCABOS_FEEDBACK_SUBMIT_URL"] = cfg["PINCABOS_FEEDBACK_URL"].rstrip("/") + "/pincabos-feedback/submit"

    return cfg


def pincabos_dev_cmd(c, timeout=8):
    try:
        return run_cmd(c, timeout=timeout).strip()
    except Exception as e:
        return f"Erreur: {e}"


def pincabos_dev_sysinfo_remote():
    os_version = ""
    try:
        os_release = Path("/etc/os-release").read_text(errors="replace")
        for line in os_release.splitlines():
            if line.startswith("PRETTY_NAME="):
                os_version = line.split("=", 1)[1].strip().strip('"')
                break
    except Exception:
        os_version = pincabos_dev_cmd(["lsb_release", "-ds"])

    hostname = pincabos_dev_cmd(["hostname"])
    ip_address = pincabos_dev_cmd(["hostname", "-I"])
    kernel_version = pincabos_dev_cmd(["uname", "-r"]) + " / " + pincabos_dev_cmd(["uname", "-m"])
    uptime = pincabos_dev_cmd(["uptime", "-p"])
    timezone = pincabos_dev_cmd(["timedatectl", "show", "-p", "Timezone", "--value"])
    local_time = pincabos_dev_cmd(["date"])

    ver = pincabos_version()
    pincabos_version_str = str(ver.get("version", "Development"))

    vpx_version = pincabos_dev_cmd([
        "bash", "-lc",
        pco_vpx_version_command()
    ])

    vpinfe_version = pincabos_dev_cmd([
        "bash", "-lc",
        pco_vpinfe_version_command()
    ])

    dof_status = pincabos_dev_cmd([
        "bash", "-lc",
        "find /opt/pincabos -iname '*dof*' -o -iname '*libdof*' 2>/dev/null | head -n 40"
    ])

    gpu_info = pincabos_dev_cmd([
        "bash", "-lc",
        "lspci | grep -Ei 'vga|3d|display' || echo 'non détecté'"
    ])

    screens_info = pincabos_dev_cmd([
        "bash", "-lc",
        "xrandr --query 2>/dev/null || cat /opt/pincabos/config/screens/screens.json 2>/dev/null || echo 'non détecté'"
    ])

    services_info = pincabos_dev_cmd([
        "bash", "-lc",
        "systemctl --no-pager --plain status pincabos-webapp.service 2>/dev/null | head -n 25"
    ])

    dashboard_snapshot = "\n".join([
        "=== PinCabOS Dashboard Snapshot ===",
        f"Hostname: {hostname}",
        f"IP: {ip_address}",
        f"OS: {os_version}",
        f"Kernel: {kernel_version}",
        f"Uptime: {uptime}",
        f"Timezone: {timezone}",
        f"Heure locale: {local_time}",
        "",
        "=== Versions ===",
        f"PinCabOS: {pincabos_version_str}",
        f"VPX: {vpx_version}",
        f"VPinFE: {vpinfe_version}",
        "",
        "=== GPU ===",
        gpu_info,
        "",
        "=== Écrans ===",
        screens_info,
        "",
        "=== DOF / libdof ===",
        dof_status,
        "",
        "=== Services ===",
        services_info,
    ])

    return {
        "hostname": hostname,
        "ip_address": ip_address,
        "os_version": os_version,
        "kernel_version": kernel_version,
        "uptime": uptime,
        "timezone": timezone,
        "local_time": local_time,
        "pincabos_version": pincabos_version_str,
        "vpx_version": vpx_version,
        "vpinfe_version": vpinfe_version,
        "dof_status": dof_status,
        "gpu_info": gpu_info,
        "screens_info": screens_info,
        "dashboard_snapshot": dashboard_snapshot,
    }


def pincabos_feedback_watchdog():
    """
    Retourne (online, status).
    Les codes HTTP 2xx/3xx sont considérés Online.
    dev.pincabos.cc retourne 302 vers /admin/reports, donc c'est OK.
    """
    cfg = pincabos_feedback_config()
    url = (
        cfg.get("PINCABOS_FEEDBACK_STATUS_URL")
        or cfg.get("PINCABOS_FEEDBACK_URL")
        or "https://dev.pincabos.cc/"
    )

    try:
        import urllib.request
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=5) as r:
            code = int(getattr(r, "status", 0) or 0)

        if 200 <= code < 400:
            return True, f"{url} répond HTTP {code}"

        return False, f"{url} répond HTTP {code}"

    except Exception as e:
        # Certains serveurs refusent HEAD. Essayer GET léger.
        try:
            import urllib.request
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as r:
                code = int(getattr(r, "status", 0) or 0)

            if 200 <= code < 400:
                return True, f"{url} répond HTTP {code}"

            return False, f"{url} répond HTTP {code}"

        except Exception as e2:
            return False, str(e2)


def pincabos_send_feedback_remote(payload):
    cfg = pincabos_feedback_config()
    url = cfg.get("PINCABOS_FEEDBACK_URL", "").strip()
    token = cfg.get("PINCABOS_FEEDBACK_TOKEN", "").strip()

    if not url:
        return False, "Aucune URL feedback configurée."

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"PinCabOS-Feedback-Agent/{str(pincabos_version().get('version', 'Development')).replace(' ', '-')} (+https://pincabos.cc)",
            "X-PinCabOS-Token": token,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return True, raw
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')}"
    except Exception as e:
        return False, str(e)


def pincabos_dev_is_logged():
    try:
        return bool(session.get("pincabos_dev_logged"))
    except Exception:
        return False


@before_request
def pincabos_dev_auth_guard():
    path = request.path or ""

    if not path.startswith("/dev"):
        return None

    allowed = [
        "/dev/login",
        "/dev/logout",
    ]

    if path in allowed:
        return None

    if pincabos_dev_is_logged():
        return None

    return redirect("/dev/login")






def pincabos_admin_curl_probe(url):
    import subprocess

    try:
        r = subprocess.run(
            [
                "/usr/bin/curl",
                "-k",
                "-L",
                "-sS",
                "-o",
                "/dev/null",
                "-w",
                "%{http_code} %{url_effective}",
                "--max-time",
                "8",
                url,
            ],
            text=True,
            capture_output=True,
            timeout=10,
        )

        raw = (r.stdout or "").strip()
        err = (r.stderr or "").strip()

        code = 0
        effective = url

        if raw:
            parts = raw.split(maxsplit=1)
            try:
                code = int(parts[0])
            except Exception:
                code = 0
            if len(parts) > 1:
                effective = parts[1]

        return {
            "returncode": r.returncode,
            "code": code,
            "effective": effective,
            "error": err,
        }

    except Exception as e:
        return {
            "returncode": 999,
            "code": 0,
            "effective": url,
            "error": str(e),
        }


def pincabos_admin_ping_probe(host):
    import subprocess

    if not host:
        return {
            "ok": False,
            "detail": "Aucun host fourni",
        }

    try:
        r = subprocess.run(
            ["/bin/ping", "-c", "1", "-W", "1", host],
            text=True,
            capture_output=True,
            timeout=3,
        )

        out = ((r.stdout or "") + "\n" + (r.stderr or "")).strip()

        if r.returncode == 0:
            return {
                "ok": True,
                "detail": f"Ping OK vers {host}",
            }

        return {
            "ok": False,
            "detail": f"Ping échoué vers {host}: {out}",
        }

    except Exception as e:
        return {
            "ok": False,
            "detail": f"Ping timeout/erreur vers {host}: {e}",
        }


def pincabos_admin_ssh_probe(host, user="root"):
    import subprocess

    if not host:
        return None

    # 1) Ping d'abord. Si ping OK, on considère la machine Online.
    ping = pincabos_admin_ping_probe(host)
    if ping.get("ok"):
        return {
            "ok": True,
            "auth": None,
            "detail": ping.get("detail", f"Ping OK vers {host}"),
        }

    # 2) Si ping échoue, tester SSH juste pour détecter "Permission denied".
    # Permission denied = machine joignable, donc Online.
    try:
        r = subprocess.run(
            [
                "/usr/bin/ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=3",
                "-o",
                "StrictHostKeyChecking=no",
                f"{user}@{host}",
                "true",
            ],
            text=True,
            capture_output=True,
            timeout=5,
        )

        out = ((r.stdout or "") + "\n" + (r.stderr or "")).strip()

        if r.returncode == 0:
            return {
                "ok": True,
                "auth": True,
                "detail": f"SSH OK vers {user}@{host}",
            }

        if "Permission denied" in out:
            return {
                "ok": True,
                "auth": False,
                "detail": f"SSH répond sur {host}, accès refusé pour {user}; machine Online",
            }

        return {
            "ok": False,
            "auth": False,
            "detail": f"{ping.get('detail', '')}; SSH code {r.returncode}: {out}",
        }

    except Exception as e:
        return {
            "ok": False,
            "auth": False,
            "detail": f"{ping.get('detail', '')}; SSH timeout/erreur: {e}",
        }


def pincabos_admin_http_status(label, url, ssh_host="", ssh_user="root", fallback_url=""):
    primary = pincabos_admin_curl_probe(url)

    if 200 <= primary["code"] < 400:
        return {
            "label": label,
            "target": url,
            "ok": True,
            "state": "🟢 Online",
            "detail": f"{url} répond HTTP {primary['code']} → {primary['effective']}",
        }

    if primary["code"] == 404:
        return {
            "label": label,
            "target": url,
            "ok": True,
            "state": "🟠 Web online / fichier absent",
            "detail": f"{url} répond HTTP 404 après redirection vers {primary['effective']}",
        }

    # Fallback pour updates global.
    if fallback_url:
        fb = pincabos_admin_curl_probe(fallback_url)

        if 200 <= fb["code"] < 400:
            return {
                "label": label,
                "target": url,
                "ok": True,
                "state": "🟢 Online via fallback",
                "detail": f"{url} indisponible ({primary['error'] or primary['code']}); fallback {fallback_url} répond HTTP {fb['code']} → {fb['effective']}",
            }

        if fb["code"] == 404:
            return {
                "label": label,
                "target": url,
                "ok": True,
                "state": "🟠 Web online / latest absent",
                "detail": f"{url} indisponible ({primary['error'] or primary['code']}); fallback {fallback_url} répond HTTP 404 → {fb['effective']}",
            }

        fallback_detail = f"; fallback {fallback_url}: HTTP {fb['code']} {fb['error']}".strip()
    else:
        fallback_detail = ""

    # SSH pour LAN / Calamares.
    if ssh_host:
        ssh = pincabos_admin_ssh_probe(ssh_host, ssh_user)

        if ssh and ssh.get("ok") and ssh.get("auth"):
            return {
                "label": label,
                "target": url,
                "ok": True,
                "state": "🟢 SSH Online",
                "detail": f"HTTP indisponible ({primary['error'] or primary['code']}); {ssh['detail']}",
            }

        if ssh and ssh.get("ok") and not ssh.get("auth"):
            return {
                "label": label,
                "target": url,
                "ok": True,
                "state": "🟢 Online",
                "detail": f"HTTP indisponible ({primary['error'] or primary['code']}); {ssh['detail']}",
            }

        ssh_detail = "; " + (ssh.get("detail") if ssh else "SSH non testé")
    else:
        ssh_detail = ""

    return {
        "label": label,
        "target": url,
        "ok": False,
        "state": "🔴 Offline",
        "detail": f"{primary['error'] or ('HTTP ' + str(primary['code']))}{fallback_detail}{ssh_detail}",
    }


def pincabos_admin_status_card_html(label, url, ssh_host="", ssh_user="root", fallback_url=""):
    st = pincabos_admin_http_status(label, url, ssh_host=ssh_host, ssh_user=ssh_user, fallback_url=fallback_url)

    if st["state"].startswith("🟢"):
        color = "#22c55e"
    elif st["state"].startswith("🟠"):
        color = "#f59e0b"
    else:
        color = "#ef4444"

    fallback_line = ""
    if fallback_url:
        fallback_line = f"<br><small>Fallback: <code>{esc(fallback_url)}</code></small>"

    ssh_line = ""
    if ssh_host:
        ssh_line = f"<br><small>SSH: <code>{esc(ssh_user)}@{esc(ssh_host)}</code></small>"

    return f"""
<div class="card pco-admin-status-simple-card" style="margin:0;">
  <h3 style="margin-top:0;">{esc(st['label'])}</h3>
  <p>
    <strong>Serveur :</strong><br>
    <code>{esc(st['target'])}</code>
    {fallback_line}
    {ssh_line}
  </p>
  <p>
    <strong>État serveur :</strong><br>
    <span style="color:{color}; font-weight:bold;">{esc(st['state'])}</span>
  </p>
  <p>
    <small style="opacity:0.85;">{esc(st['detail'])}</small>
  </p>
</div>
"""


def pincabos_admin_all_status_cards_html():
    cards = [
        ("Dev global", "https://dev.pincabos.cc/", "", "root", ""),
        ("Updates global", "https://ins.pincabos.cc/install/pkg/latest.json", "", "root", ""),
        ("Updates LAN", "http://192.168.254.55/install/pkg/latest.json", "192.168.254.55", "root", ""),
        ("Calamares LAN", "http://192.168.254.66/", "192.168.254.66", "root", ""),
    ]

    return """
<div class="pco-admin-status-grid">
""" + "\n".join(
        pincabos_admin_status_card_html(label, url, ssh_host=ssh_host, ssh_user=ssh_user, fallback_url=fallback_url)
        for label, url, ssh_host, ssh_user, fallback_url in cards
    ) + """
</div>
"""


def pincabos_admin_logs_options_html():
    import time

    try:
        rows = pincabos_admin_log_files()
    except Exception as e:
        return '<option value="">Erreur logs: ' + esc(str(e)) + '</option>'

    if not rows:
        return '<option value="">Aucun log dans /opt/pincabos/logs</option>'

    out = []
    for log in rows[:500]:
        try:
            name = str(log.get("name", ""))
            size = int(log.get("size", 0))
            mtime_raw = log.get("display_mtime", log.get("mtime", 0))
            mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(mtime_raw)))
            label = f"{mtime} — {name} ({round(size / 1024)} Ko)"
            out.append(f'<option value="{esc(name)}">{esc(label)}</option>')
        except Exception:
            continue

    return "\n".join(out) if out else '<option value="">Aucun log dans /opt/pincabos/logs</option>'


def pincabos_admin_page():
    status = pincabos_admin_all_status_cards_html() if "pincabos_admin_all_status_cards_html" in globals() else "<p>Cartes état indisponibles.</p>"

    iso_mode_active = Path("/opt/pincabos/config/iso-firstboot-safe.flag").exists()
    iso_glow = "box-shadow:0 0 18px rgba(34,197,94,.95),0 0 34px rgba(34,197,94,.45);" if iso_mode_active else ""
    game_glow = "box-shadow:0 0 18px rgba(34,197,94,.95),0 0 34px rgba(34,197,94,.45);" if not iso_mode_active else ""

    body = """
<h1>Admin PinCabOS</h1>

<style>
.pco-admin-status-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; }
.pco-admin-actions { display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin:10px 0; }
.pco-admin-action-frame { width:100%; height:560px; border:1px solid rgba(255,176,0,.28); border-radius:12px; background:#111; }
.pco-admin-log-select { min-width:320px; max-width:520px; padding:7px; background:#111; color:#eee; border:1px solid rgba(255,176,0,.35); border-radius:8px; }
.pco-admin-spinner-wrap {
  display:none;
  align-items:center;
  gap:10px;
  padding:8px 10px;
  border:1px solid rgba(255,176,0,.35);
  border-radius:10px;
  background:rgba(0,0,0,.38);
  color:#ffb000;
  font-weight:bold;
}
.pco-admin-spinner-wrap.is-active { display:flex; }
.pco-admin-spinner {
  width:18px;
  height:18px;
  border:3px solid rgba(255,176,0,.25);
  border-top-color:#ffb000;
  border-radius:50%;
  animation:pcoAdminSpin .8s linear infinite;
}
@keyframes pcoAdminSpin { to { transform:rotate(360deg); } }
button.pco-admin-busy {
  opacity:.65;
  cursor:wait;
}

@media (max-width:1400px) { .pco-admin-status-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } }
@media (max-width:800px) { .pco-admin-status-grid { grid-template-columns:1fr; } .pco-admin-log-select { min-width:220px; max-width:100%; } }
</style>

<div class="card" style="border-color:#ffb000;">
  <h2>État des serveurs</h2>
""" + status + """
</div>

<div class="card" style="border-color:#ffb000;">
  <h2>Publish / Cleanup PinCabOS</h2>

  <div class="pco-admin-actions">
    <form action="/admin/frame/cleanup-dry-run" method="get" target="pco-admin-action-frame" style="display:inline;margin:0;" onsubmit="return pcoAdminStartSpinner(this, 'Cleanup dry-run en cours...')">
      <button class="button" type="submit" onclick="pcoAdminStartSpinner(this.form, 'Cleanup dry-run en cours...')" style="background:#166534;border-color:#22c55e;color:white;">Cleanup dry-run</button>
    </form>
    <form action="/admin/frame/cleanup-apply" method="get" target="pco-admin-action-frame" style="display:inline;margin:0;" onsubmit="return confirm('Lancer cleanup réel ?') && pcoAdminStartSpinner(this, 'Cleanup réel en cours...');">
      <button class="button" type="submit" onclick="pcoAdminStartSpinner(this.form, 'Cleanup réel en cours...')" style="background:#991b1b;border-color:#ef4444;color:white;">Cleanup réel</button>
    </form>
    <form action="/admin/frame/publy-dry-run" method="get" target="pco-admin-action-frame" style="display:inline;margin:0;" onsubmit="return pcoAdminStartSpinner(this, 'Publy dry-run en cours...')">
      <button class="button" type="submit" onclick="pcoAdminStartSpinner(this.form, 'Publy dry-run en cours...')" style="background:#166534;border-color:#22c55e;color:white;">Publy dry-run</button>
    </form>
    <form action="/admin/frame/publy-apply" method="get" target="pco-admin-action-frame" style="display:inline;margin:0;" onsubmit="return confirm('Lancer Publy réel vers le serveur update ?') && pcoAdminStartSpinner(this, 'Publy réel en cours...');">
      <button class="button" type="submit" onclick="pcoAdminStartSpinner(this.form, 'Publy réel en cours...')" style="background:#991b1b;border-color:#ef4444;color:white;">Publy réel</button>
    </form>


    <div style="flex:1 1 260px;"></div>

          <div id="pco-admin-spinner-wrap" class="pco-admin-spinner-wrap">
        <span class="pco-admin-spinner"></span>
        <span id="pco-admin-spinner-text">Action en cours...</span>
      </div>

      <form method="get" target="pco-admin-action-frame" style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:0;" onsubmit="return pcoAdminStartSpinner(this, 'Action log en cours...')">
      <label style="display:flex;align-items:center;gap:6px;">
        Logs
        <select id="pco-admin-log-select" name="name" class="pco-admin-log-select">
          """ + pincabos_admin_logs_options_html() + """
        </select>
      </label>
      <button class="button secondary" type="submit" formaction="/admin/logs/view" onclick="pcoAdminStartSpinner(this.form, 'Affichage du log en cours...')">Afficher</button>
      <button class="button secondary" type="submit" formaction="/admin/logs/download" formtarget="_self" onclick="pcoAdminStartSpinner(this.form, 'Téléchargement du log en cours...')">Télécharger</button>
      <button class="button secondary" type="submit" formaction="/admin/logs/delete" formmethod="post" style="border-color:#ef4444;" onclick="if (!confirm('Supprimer ce log ?')) return false; pcoAdminStartSpinner(this.form, 'Suppression du log en cours...'); return true;">Supprimer</button>
    </form>

    <form method="post" action="/admin/logs/delete-all" target="pco-admin-action-frame" style="display:inline;margin:0;" onsubmit="return pcoAdminStartSpinner(this, 'Suppression des logs en cours...')">
      <button class="button secondary" type="submit" style="border-color:#ef4444;" onclick="if (!confirm('Supprimer TOUS les logs dans /opt/pincabos/logs ?')) return false; pcoAdminStartSpinner(this.form, 'Suppression de tous les logs en cours...'); return true;">Supprimer all</button>
    </form>

    <button class="button secondary" type="button" onclick="location.reload()">Rafraîchir logs</button>

  </div>

  <p><small>Protégés: <code>/home/pinball/Share</code>, <code>/home/pinball/Tables</code>, <code>/opt/pincabos/backups</code>, <code>/opt/pincabos/logs</code>.</small></p>

  <h3>Résultat des dry-run / actions réelles</h3>
  <iframe id="pco-admin-action-frame" name="pco-admin-action-frame" class="pco-admin-action-frame" src="/admin/action-empty"></iframe>
</div>

<script>
async function pcoAdminRunAction(url, label) {
  const frame = document.getElementById('pco-admin-action-frame');
  if (!frame) return;

  // Les routes /admin/frame/* se chargent comme vraie iframe.
  // Ça évite qu'un fetch suive une redirection /admin et injecte le dashboard dans srcdoc.
  if (url.startsWith('/admin/frame/')) {
    frame.removeAttribute('srcdoc');
    const sep = url.includes('?') ? '&' : '?';
    frame.src = url + sep + 'ts=' + Date.now();

    if (typeof pcoAdminRefreshLogs === 'function') {
      setTimeout(function(){ pcoAdminRefreshLogs(); }, 1500);
      setTimeout(function(){ pcoAdminRefreshLogs(); }, 5000);
    }
    return;
  }

  frame.srcdoc = '<body style="background:#111;color:#eee;font-family:monospace;padding:12px;"><h3>' + label + '</h3><pre>Exécution en cours...\n' + url + '</pre></body>';

  try {
    const res = await fetch(url, {method:'POST', credentials:'same-origin', redirect:'manual'});
    const txt = await res.text();
    frame.srcdoc = txt || '<body style="background:#111;color:#eee;font-family:monospace;padding:12px;"><pre>Réponse vide HTTP ' + res.status + '</pre></body>';

    if (typeof pcoAdminRefreshLogs === 'function') {
      await pcoAdminRefreshLogs();
    }
  } catch(e) {
    frame.srcdoc = '<body style="background:#111;color:#eee;font-family:monospace;padding:12px;"><pre>Erreur JS: ' + String(e) + '</pre></body>';
  }
}

async function pcoAdminRefreshLogs() {
  const select = document.getElementById('pco-admin-log-select');
  const frame = document.getElementById('pco-admin-action-frame');
  if (!select) return;

  select.innerHTML = '';
  const loading = document.createElement('option');
  loading.value = '';
  loading.textContent = 'Chargement logs...';
  select.appendChild(loading);

  try {
    const res = await fetch('/admin/logs/list?ts=' + Date.now(), {
      method: 'GET',
      credentials: 'same-origin',
      cache: 'no-store',
      headers: {'Accept': 'application/json'}
    });

    const txt = await res.text();

    if (!res.ok) {
      throw new Error('HTTP ' + res.status + ' ' + txt.slice(0, 180));
    }

    let data;
    try {
      data = JSON.parse(txt);
    } catch (e) {
      throw new Error('Réponse logs non JSON: ' + txt.slice(0, 180));
    }

    select.innerHTML = '';

    if (!data.logs || data.logs.length === 0) {
      const opt = document.createElement('option');
      opt.value = '';
      opt.textContent = 'Aucun log';
      select.appendChild(opt);
      return;
    }

    for (const log of data.logs) {
      const opt = document.createElement('option');
      opt.value = log.name;
      opt.textContent = log.mtime + ' — ' + log.name + ' (' + Math.round(log.size / 1024) + ' Ko)';
      select.appendChild(opt);
    }
  } catch (e) {
    select.innerHTML = '';
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = 'Erreur logs - voir frame';
    select.appendChild(opt);

    if (frame) {
      frame.srcdoc =
        '<body style="background:#111;color:#eee;font-family:monospace;padding:12px;"><h3>Erreur chargement logs</h3><pre>' +
        String(e).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])) +
        '</pre></body>';
    }
  }
}

function pcoAdminSelectedLog() {
  const select = document.getElementById('pco-admin-log-select');
  if (!select || !select.value) {
    alert('Choisis un log.');
    return '';
  }
  return select.value;
}

function pcoAdminViewLog() {
  const name = pcoAdminSelectedLog();
  if (!name) return;
  const frame = document.getElementById('pco-admin-action-frame');
  if (!frame) return;
  frame.removeAttribute('srcdoc');
  frame.src = '/admin/logs/view?name=' + encodeURIComponent(name) + '&ts=' + Date.now();
}

function pcoAdminDownloadLog() {
  const name = pcoAdminSelectedLog();
  if (!name) return;
  window.location = '/admin/logs/download?name=' + encodeURIComponent(name) + '&ts=' + Date.now();
}

async function pcoAdminDeleteLog() {
  const name = pcoAdminSelectedLog();
  if (!name) return;
  if (!confirm('Supprimer ce log ?\n' + name)) return;

  const body = new URLSearchParams();
  body.set('name', name);

  const res = await fetch('/admin/logs/delete', {
    method:'POST',
    credentials:'same-origin',
    headers:{'Content-Type':'application/x-www-form-urlencoded'},
    body:body.toString()
  });

  const txt = await res.text();
  document.getElementById('pco-admin-action-frame').srcdoc =
    '<body style="background:#111;color:#eee;font-family:monospace;padding:12px;"><pre>' +
    txt.replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])) +
    '</pre></body>';

  await pcoAdminRefreshLogs();
}

async function pcoAdminDeleteAllLogs() {
  if (!confirm('Supprimer TOUS les logs dans /opt/pincabos/logs ?')) return;

  const res = await fetch('/admin/logs/delete-all', {
    method:'POST',
    credentials:'same-origin'
  });

  const txt = await res.text();
  document.getElementById('pco-admin-action-frame').srcdoc =
    '<body style="background:#111;color:#eee;font-family:monospace;padding:12px;"><pre>' +
    txt.replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])) +
    '</pre></body>';

  await pcoAdminRefreshLogs();
}

document.addEventListener('DOMContentLoaded', function() {
  pcoAdminRefreshLogs();
});

function pcoAdminStartSpinner(form, label) {
  const wrap = document.getElementById('pco-admin-spinner-wrap');
  const text = document.getElementById('pco-admin-spinner-text');
  const frame = document.getElementById('pco-admin-action-frame');

  console.log('PinCabOS admin spinner:', label || 'Action en cours...');

  if (wrap) wrap.classList.add('is-active');
  if (text) text.textContent = label || 'Action en cours...';

  if (form) {
    const buttons = form.querySelectorAll('button');
    buttons.forEach(function(btn) {
      btn.classList.add('pco-admin-busy');
      btn.dataset.pcoOldText = btn.textContent;
      if (btn.type === 'submit') btn.textContent = 'En cours...';
    });
  }

  if (frame) {
    frame.srcdoc = '<!doctype html><html><head><meta charset="utf-8"><style>' +
      'body{margin:0;padding:18px;background:#0b0b0b;color:#eee;font-family:Arial,sans-serif;}' +
      '.box{border:1px solid rgba(255,176,0,.35);border-radius:12px;padding:14px;background:#111827;}' +
      '.spin{display:inline-block;width:20px;height:20px;border:3px solid rgba(255,176,0,.25);border-top-color:#ffb000;border-radius:50%;animation:s .8s linear infinite;vertical-align:middle;margin-right:10px;}' +
      '@keyframes s{to{transform:rotate(360deg)}}' +
      '</style></head><body><div class="box"><span class="spin"></span>' +
      String(label || 'Action en cours...') +
      '<br><small>Le résultat va apparaître ici quand la commande sera terminée.</small></div></body></html>';
  }

  return true;
}

document.addEventListener('DOMContentLoaded', function() {
  const frame = document.getElementById('pco-admin-action-frame');
  if (!frame) return;

  frame.addEventListener('load', function() {
    const wrap = document.getElementById('pco-admin-spinner-wrap');
    if (wrap) wrap.classList.remove('is-active');

    document.querySelectorAll('button.pco-admin-busy').forEach(function(btn) {
      btn.classList.remove('pco-admin-busy');
      if (btn.dataset.pcoOldText) {
        btn.textContent = btn.dataset.pcoOldText;
        delete btn.dataset.pcoOldText;
      }
    });
  });
});

</script>
"""
    return page("Admin PinCabOS", body)


def pincabos_admin_cmd_for_script(script, *args):
    return pco_admin_cmd_for_script(script, *args)


def pincabos_admin_write_action_log(title, output):
    import re
    import time

    base = pincabos_admin_log_dir() if "pincabos_admin_log_dir" in globals() else Path("/opt/pincabos/logs")
    base.mkdir(parents=True, exist_ok=True)

    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", title).strip("-").lower() or "admin-action"
    name = "pincabos-admin-" + slug + "-" + time.strftime("%Y%m%d-%H%M%S") + ".txt"
    path = base / name
    path.write_text(output, encoding="utf-8", errors="replace")
    return path


def pincabos_admin_iframe_result(title, cmd, timeout=1800):
    guard = pincabos_admin_require_login()
    if guard:
        return guard
    rc, body = pco_admin_iframe_body(title, cmd, timeout=timeout)
    return page(title, body)


def pincabos_admin_is_logged():
    try:
        return bool(session.get("pincabos_admin_logged"))
    except Exception:
        return False


@before_request
def pincabos_admin_auth_guard():
    path = request.path or ""
    if not path.startswith("/admin"):
        return None
    # /admin is both the login page and login POST. Logout is harmless without a session.
    if path in {"/admin", "/admin/logout"}:
        return None
    if pincabos_admin_is_logged():
        return None
    return redirect("/admin")


@route("/admin/action/iso-status", methods=["POST"])
def pincabos_admin_action_iso_status():
    return pincabos_admin_iframe_result(
        "État Mode ISO / Jeux",
        ["/usr/bin/sudo", "-n", str(pco_script("admin_iso_game_mode")), "status"],
        timeout=300,
    )


@route("/admin/action/iso-mode", methods=["POST"])
def pincabos_admin_action_iso_mode():
    return pincabos_admin_iframe_result(
        "Mode ISO - armement génération ISO",
        ["/usr/bin/sudo", "-n", str(pco_script("admin_iso_game_mode")), "iso"],
        timeout=600,
    )


@route("/admin/action/game-mode", methods=["POST"])
def pincabos_admin_action_game_mode():
    return pincabos_admin_iframe_result(
        "Mode Jeux - cab normal",
        ["/usr/bin/sudo", "-n", str(pco_script("admin_iso_game_mode")), "game"],
        timeout=600,
    )




def pincabos_credentials_default_notice(user, password, scope, command):
    """Avertissement affiche tant qu'une page utilise son identifiant par defaut."""
    notice = (
        f'<p class="warn">Identifiants par défaut en place pour <code>{esc(scope)}</code> : '
        f'<code>{esc(str(user))}</code> / <code>{esc(str(password))}</code>. '
        f'À changer avec <code>sudo {esc(command)}</code>.</p>'
    )
    unreadable = globals().get("PINCABOS_ADMIN_UNREADABLE_SECRETS") or []
    if unreadable:
        files = ", ".join(esc(str(item)) for item in unreadable)
        notice += (
            '<p class="bad">Fichier d\'identifiants présent mais illisible par '
            f'la WebApp : {files}. Corrige le propriétaire avec '
            '<code>sudo chown pinball:pinball</code>, ou repose-le avec '
            '<code>sudo pincabos-admin-password</code>.</p>'
        )
    return notice


def pincabos_admin_default_credentials_notice():
    """Page /admin : avertit tant que le mot de passe par defaut est en place."""
    if not globals().get("PINCABOS_ADMIN_CREDENTIALS_ARE_DEFAULT"):
        return ""
    return pincabos_credentials_default_notice(
        globals().get("ADMIN_LOGIN_USER", "admin"),
        globals().get("PINCABOS_DEFAULT_ADMIN_PASS", ""),
        "/admin",
        "pincabos-admin-password --set",
    )


def pincabos_admin_login_body(error=""):
    err = f'<p class="warn">{esc(error)}</p>' if error else ""
    err += pincabos_admin_default_credentials_notice()
    body = f"""
<h1>Admin PinCabOS</h1>
<div class="card" style="max-width:520px;">
  <h2>Connexion admin</h2>
  {err}
  <form method="post" action="/admin">
    <table style="width:100%;">
      <tr><td style="width:150px;">Utilisateur</td><td><input name="username" style="width:100%;padding:8px;" autofocus></td></tr>
      <tr><td>Mot de passe</td><td><input name="password" type="password" style="width:100%;padding:8px;"></td></tr>
    </table>
    <p><button class="button" type="submit">Connexion Admin</button></p>
  </form>
</div>
"""
    return page("Admin PinCabOS", body)


@route("/admin", methods=["GET", "POST"])
def pincabos_admin_index():
    expected_user = str(ADMIN_LOGIN_USER or "").strip()
    expected_pass = str(ADMIN_LOGIN_PASS or "")
    if not expected_user or not expected_pass:
        return page("Admin PinCabOS", """
<div class="card"><h2>Connexion admin indisponible</h2>
<p class="bad">Aucun identifiant Admin n’est configuré.</p>
<p>Crée <code>/opt/pincabos/config/admin-login.txt</code> et
<code>/opt/pincabos/config/admin-password.txt</code>, ou utilise les variables
<code>PINCABOS_ADMIN_LOGIN</code> et <code>PINCABOS_ADMIN_PASSWORD</code>.</p></div>
"""), 503

    if request.method == "POST":
        username = (request.form.get("username", "") or "").strip()
        password = request.form.get("password", "") or ""
        if hmac.compare_digest(username, expected_user) and hmac.compare_digest(password, expected_pass):
            session["pincabos_admin_logged"] = True
            session.modified = True
            return redirect("/admin")
        return pincabos_admin_login_body("Utilisateur ou mot de passe invalide.")

    if not pincabos_admin_is_logged():
        return pincabos_admin_login_body()
    return pincabos_admin_page()


@route("/admin/logout")
def pincabos_admin_logout():
    session.pop("pincabos_admin_logged", None)
    return redirect("/admin")


def pincabos_admin_publy_webpass_secret_path():
    return Path("/opt/pincabos/config/webserver-webpass.secret")


def pincabos_admin_publy_read_webpass_secret():
    try:
        path = pincabos_admin_publy_webpass_secret_path()
        if not path.exists() or not path.is_file():
            return ""
        return path.read_text(errors="replace").strip()
    except Exception:
        return ""


def pincabos_admin_publy_env():
    import os

    env = os.environ.copy()
    secret = pincabos_admin_publy_read_webpass_secret()
    if secret:
        env["WEB_PASS"] = secret
    return env


@route("/admin/action-empty")
def pincabos_admin_action_empty():
    return """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
body { margin:0; padding:12px; background:#111; color:#ccc; font-family:Arial, sans-serif; }
code { color:#ffb000; }
</style>
</head>
<body>
Action admin prête. Choisis <code>Cleanup</code>, <code>Publy</code> ou un log.
</body>
</html>""", 200, {"Content-Type": "text/html; charset=utf-8"}


def pincabos_admin_publy_script_path():
    candidates = [
        Path("/opt/pincabos/tools/publy.sh"),
        Path("/opt/pincabos/tools/pincabos-publy.sh"),
        Path("/opt/pincabos/bin/publy"),
        Path("/opt/pincabos/bin/pincabos-publy"),
        Path("/opt/pincabos/install/publy.sh"),
        Path("/opt/pincabos/install/pincabos-publy.sh"),
    ]

    for candidate in candidates:
        try:
            if candidate.exists() and candidate.is_file():
                return str(candidate)
        except Exception:
            continue

    raise RuntimeError("Script Publy introuvable: attendu /opt/pincabos/tools/publy.sh")


@route("/admin/frame/publy-dry-run", methods=["GET", "POST"])
def pincabos_admin_frame_publy_dry_run():
    return pincabos_admin_run_script(
        "Publy PinCabOS - dry-run",
        pincabos_admin_cmd_for_script(pincabos_admin_publy_script_path(), "--dry-run"),
        env=pincabos_admin_publy_env(),
    )


@route("/admin/frame/publy-apply", methods=["GET", "POST"])
def pincabos_admin_frame_publy_apply():
    return pincabos_admin_run_script(
        "Publy PinCabOS - réel",
        pincabos_admin_cmd_for_script(pincabos_admin_publy_script_path(), "--apply"),
        env=pincabos_admin_publy_env(),
    )


def pincabos_admin_clean_depot_script_path():
    candidates = [
        Path("/opt/pincabos/tools/pincabos-cleanup.sh"),
        Path("/opt/pincabos/install/99-clean-depot.sh"),
    ]

    for candidate in candidates:
        try:
            if candidate.exists() and candidate.is_file():
                return str(candidate)
        except Exception:
            continue

    raise RuntimeError("Script cleanup officiel introuvable: attendu /opt/pincabos/tools/pincabos-cleanup.sh")


@route("/admin/frame/cleanup-dry-run", methods=["GET", "POST"])
def pincabos_admin_frame_cleanup_dry_run():
    return pincabos_admin_run_script(
        "99-clean-depot PinCabOS - dry-run",
        pincabos_admin_cmd_for_script(pincabos_admin_clean_depot_script_path()),
    )


@route("/admin/frame/cleanup-apply", methods=["GET", "POST"])
def pincabos_admin_frame_cleanup_apply():
    return pincabos_admin_run_script(
        "99-clean-depot PinCabOS - réel",
        pincabos_admin_cmd_for_script(pincabos_admin_clean_depot_script_path(), "--apply"),
    )


def pincabos_admin_log_dir():
    base = Path("/opt/pincabos/logs")
    base.mkdir(parents=True, exist_ok=True)
    return base


def pincabos_admin_log_timestamp_from_name(name):
    import re
    import time

    raw = str(name or "")

    # Formats PinCabOS :
    # vmtest-...-20260610-165228.txt
    # dof-online-api-import-20260610-164646.log
    # go-pincabos-20260610-052957.log
    m = re.search(r'(20\\d{6})[-_](\\d{6})', raw)
    if not m:
        return None

    try:
        return time.mktime(time.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S"))
    except Exception:
        return None


def pincabos_admin_log_files():
    base = pincabos_admin_log_dir()
    rows = []

    for path in base.rglob("*"):
        try:
            if not path.is_file():
                continue
            if path.name.startswith("."):
                continue
            if path.is_symlink():
                continue

            st = path.stat()
            rel = path.relative_to(base).as_posix()
            name_ts = pincabos_admin_log_timestamp_from_name(rel)
            mtime = float(st.st_mtime)

            rows.append({
                "name": rel,
                "size": int(st.st_size),
                "mtime": mtime,
                "display_mtime": float(name_ts if name_ts else mtime),
                "sort_mtime": float(name_ts if name_ts else mtime),
            })
        except Exception:
            continue

    rows.sort(
        key=lambda x: (
            x.get("sort_mtime", x.get("mtime", 0)),
            x.get("mtime", 0),
            x.get("name", ""),
        ),
        reverse=True
    )
    return rows[:500]


def pincabos_admin_safe_log_path(name):
    if not name:
        return None

    name = str(name).replace("\\", "/").lstrip("/")
    if "\x00" in name:
        return None

    base = pincabos_admin_log_dir().resolve()
    candidate = (base / name).resolve()

    try:
        if candidate == base:
            return None
        if base not in candidate.parents:
            return None
        if not candidate.is_file():
            return None
        if candidate.is_symlink():
            return None
        return candidate
    except Exception:
        return None


@route("/admin/logs/list")
def pincabos_admin_logs_list():

    import json
    import time

    rows = []
    for it in pincabos_admin_log_files():
        rows.append({
            "name": it["name"],
            "size": it["size"],
            "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(it.get("display_mtime", it["mtime"]))),
        })

    return json.dumps({"ok": True, "logs": rows}, ensure_ascii=False), 200, {"Content-Type": "application/json; charset=utf-8"}


@route("/admin/logs/view")
def pincabos_admin_logs_view():

    name = request.args.get("name", "")
    path = pincabos_admin_safe_log_path(name)

    if not path:
        body = "Log introuvable ou invalide: " + str(name)
        title = "Log introuvable"
    else:
        title = "Log: " + path.name
        try:
            body = path.read_text(errors="replace")
        except Exception as e:
            body = "Erreur lecture log: " + str(e)

    html_out = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{
  margin:0;
  padding:12px;
  background:#111;
  color:#eee;
  font-family:ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size:12px;
}}
h3 {{
  margin:0 0 6px 0;
  color:#ffb000;
  font-family:system-ui, Arial, sans-serif;
}}
pre {{
  white-space:pre-wrap;
  margin:0;
}}
</style>
</head>
<body>
<h3>{esc(title)}</h3>
<pre>{esc(body)}</pre>
</body>
</html>"""
    return html_out, 200, {"Content-Type": "text/html; charset=utf-8"}


@route("/admin/logs/download")
def pincabos_admin_logs_download():

    name = request.args.get("name", "")
    path = pincabos_admin_safe_log_path(name)

    if not path:
        return "Log introuvable", 404

    from flask import send_file
    return send_file(str(path), as_attachment=True, download_name=path.name)


@route("/admin/logs/delete", methods=["POST"])
def pincabos_admin_logs_delete():

    name = request.form.get("name", "") or request.args.get("name", "")
    path = pincabos_admin_safe_log_path(name)

    if not path:
        return "Log introuvable", 404

    try:
        path.unlink()
        return "OK supprimé: " + path.name, 200
    except Exception as e:
        return "Erreur suppression: " + str(e), 500


@route("/admin/logs/delete-all", methods=["POST"])
def pincabos_admin_logs_delete_all():

    base = pincabos_admin_log_dir()
    deleted = 0
    errors = []

    for f in base.iterdir():
        if not f.is_file() or f.name.startswith("."):
            continue
        try:
            f.unlink()
            deleted += 1
        except Exception as e:
            errors.append(f.name + ": " + str(e))

    if errors:
        return "Supprimés: " + str(deleted) + "\\nErreurs:\\n" + "\\n".join(errors), 500

    return "OK supprimés: " + str(deleted), 200


def pincabos_admin_action_cleanup_dry_run():
    return pincabos_admin_iframe_result(
        "Cleanup PinCabOS - dry-run",
        ["/usr/bin/sudo", "-n", str(pco_script("cleanup"))],
        timeout=1800,
    )


def pincabos_admin_action_cleanup_apply():
    return pincabos_admin_iframe_result(
        "Cleanup PinCabOS - réel",
        ["/usr/bin/sudo", "-n", str(pco_script("cleanup")), "--apply"],
        timeout=1800,
    )


def pincabos_admin_require_login():
    if not pincabos_admin_is_logged():
        return redirect("/admin")
    return None


def pincabos_admin_run_script(title, cmd, timeout=1800, env=None):
    import subprocess
    import re
    import os

    ansi_re = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")

    env = os.environ.copy()
    env["TERM"] = "xterm"
    env["DEBIAN_FRONTEND"] = "noninteractive"

    try:
        proc = subprocess.run(
            cmd,
            cwd="/opt/pincabos/web",
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            env=env,
        )
        rc = proc.returncode
        output = proc.stdout or ""
    except subprocess.TimeoutExpired as e:
        rc = 124
        output = "TIMEOUT après " + str(timeout) + " secondes\n"
        if e.stdout:
            output += str(e.stdout)
    except Exception as e:
        rc = 1
        output = "Erreur lancement commande: " + str(e)

    output = ansi_re.sub("", output)
    output = output.replace("\r\n", "\n").replace("\r", "\n")

    status = "GO [√]" if rc == 0 else "NOGOOD [X]"
    safe_title = esc(title)
    safe_status = esc(status)
    safe_cmd = esc(" ".join(str(x) for x in cmd))
    safe_output = esc(output)

    html_out = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{safe_title}</title>
<style>
body {{
  margin:0;
  padding:12px;
  background:#0b0b0b;
  color:#e5e7eb;
  font-family:ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size:12px;
}}
.top {{
  margin-bottom:10px;
  padding:10px 12px;
  border:1px solid rgba(255,176,0,.45);
  border-radius:10px;
  background:#111827;
}}
h3 {{
  margin:0 0 6px 0;
  color:#ffb000;
  font-family:Arial, sans-serif;
}}
.status-ok {{ color:#22c55e; font-weight:bold; }}
.status-bad {{ color:#ef4444; font-weight:bold; }}
.cmd {{
  color:#93c5fd;
  white-space:pre-wrap;
  overflow-wrap:anywhere;
}}
pre {{
  white-space:pre-wrap;
  overflow-wrap:anywhere;
  margin:0;
  padding:12px;
  border-radius:10px;
  background:#050505;
  border:1px solid rgba(255,255,255,.12);
}}
</style>
</head>
<body>
<div class="top">
  <h3>{safe_title}</h3>
  <div class="{'status-ok' if rc == 0 else 'status-bad'}">{safe_status}</div>
  <div class="cmd">{safe_cmd}</div>
</div>
<pre>{safe_output}</pre>
</body>
</html>"""

    return html_out, 200, {"Content-Type": "text/html; charset=utf-8"}


def pincabos_admin_status_page(title, commands):
    import subprocess

    guard = pincabos_admin_require_login()
    if guard:
        return guard

    output = []

    for label, cmd in commands:
        output.append("=== " + label + " ===")
        output.append("Commande: " + " ".join(cmd))

        try:
            r = subprocess.run(cmd, text=True, capture_output=True, timeout=30)
            output.append("Code retour: " + str(r.returncode))

            if r.stdout:
                output.append("")
                output.append(r.stdout.rstrip())
            if r.stderr:
                output.append("")
                output.append("STDERR:")
                output.append(r.stderr.rstrip())

        except Exception as e:
            output.append("ERREUR: " + str(e))

        output.append("")

    body = f"""
<h1>{esc(title)}</h1>
<div class="card">
  <p>
    
    <a class="button secondary" href="/">Dashboard</a>
  </p>
  <pre style="white-space:pre-wrap;max-height:760px;overflow:auto;background:rgba(0,0,0,.45);border:1px solid rgba(255,176,0,.25);border-radius:12px;padding:12px;">{esc(chr(10).join(output))}</pre>
</div>
"""
    return page(title, body)


@route("/admin/publish-tree/dry-run", methods=["POST"])
def pincabos_admin_publish_tree_dry_run():
    return pincabos_admin_run_script(
        "Publish PinCabOS TREE - dry-run",
        pincabos_admin_cmd_for_script(str(pco_script("publish_tree"))),
        timeout=1800,
    )


@route("/admin/publish-tree/apply", methods=["POST"])
def pincabos_admin_publish_tree_apply():
    return pincabos_admin_run_script(
        "Publish PinCabOS TREE - réel",
        pincabos_admin_cmd_for_script(str(pco_script("publish_tree")), "--apply"),
        timeout=1800,
    )


def pincabos_admin_cleanup_dry_run():
    return pincabos_admin_run_script(
        "Cleanup PinCabOS - dry-run",
        ["/usr/bin/sudo", str(pco_script("cleanup"))],
        timeout=1800,
    )


def pincabos_admin_cleanup_apply():
    return pincabos_admin_run_script(
        "Cleanup PinCabOS - réel",
        ["/usr/bin/sudo", str(pco_script("cleanup")), "--apply"],
        timeout=1800,
    )


@route("/admin/status")
def pincabos_admin_status_local():
    return pincabos_admin_status_page("État serveur Dev PinCabOS", [
        ("HTTP local /", ["/usr/bin/curl", "-I", "--max-time", "5", "http://127.0.0.1/"]),
        ("HTTP local /admin", ["/usr/bin/curl", "-I", "--max-time", "5", "http://127.0.0.1/admin"]),
        ("HTTP local /dev", ["/usr/bin/curl", "-I", "--max-time", "5", "http://127.0.0.1/dev"]),
        ("Service WebApp", ["/usr/bin/systemctl", "--no-pager", "--full", "status", "pincabos-webapp.service"]),
        ("Service Console", ["/usr/bin/systemctl", "--no-pager", "--full", "status", "pincabos-console.service"]),
        ("Service Frontend", ["/usr/bin/systemctl", "--no-pager", "--full", "status", "pincabos-vpinfe.service"]),
        ("Espace disque", ["/bin/df", "-h", "/"]),
        ("Scripts Admin", ["/bin/bash", "-lc", "ls -l " + shlex_quote(str(pco_script("publish_tree"))) + " " + shlex_quote(str(pco_script("cleanup"))) + " 2>&1"]),
        ("Derniers logs / rapports", ["/bin/bash", "-lc", "ls -lt /opt/pincabos/logs/* 2>/dev/null | head -25"]),
    ])




@route("/admin/console-root")
def pincabos_admin_console_root():
    guard = pincabos_admin_require_login()
    if guard:
        return guard
    body = """
<h1> désactivée</h1>
<div class="card">
  <p class="warn">La console root a été retirée de la page admin.</p>
  <p><a class="button" href="/admin">Retour Admin</a></p>
</div>
"""
    return page(" désactivée", body)


try:
    pco_admin_page_base = pincabos_admin_page
except NameError:
    pco_admin_page_base = None

# ---- Resilient replacements for legacy dev actions. ----
# The old /dev/login route assumed credential files always existed and raised HTTP 500 when they did not.
@route("/dev/login", methods=["GET", "POST"])
def pincabos_dev_login_page_safe():
    import hmac
    credentials = {
        "username": Path("/opt/pincabos/config/dev-login.txt"),
        "password": Path("/opt/pincabos/config/dev-password.txt"),
    }
    # Fichiers de secrets absents d'une image fraiche : on retombe sur les
    # identifiants par defaut documentes plutot que de fermer la page.
    def _read(path, fallback):
        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError:
            value = ""
        return value or fallback

    dev_default_user = str(globals().get("PINCABOS_DEFAULT_DEV_USER", "PinCabOsDev"))
    dev_default_pass = str(globals().get("PINCABOS_DEFAULT_DEV_PASS", ""))
    expected_user = _read(credentials["username"], dev_default_user)
    expected_pass = _read(credentials["password"], dev_default_pass)
    dev_uses_default = not credentials["password"].is_file() or expected_pass == dev_default_pass

    if not expected_pass:
        return page("Connexion développeur", """
<div class="card"><h2>Connexion développeur indisponible</h2>
<p class="bad">Les identifiants développeur ne sont pas configurés sur ce cabinet.</p>
<p>Fichiers requis : <code>/opt/pincabos/config/dev-login.txt</code> et <code>/opt/pincabos/config/dev-password.txt</code>.</p>
<p><a class="button secondary" href="/about">Retour</a></p></div>
"""), 503

    error = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if hmac.compare_digest(username, expected_user) and hmac.compare_digest(password, expected_pass):
            session["pincabos_dev_logged"] = True
            session["pincabos_dev_auth"] = True
            session["dev_logged_in"] = True
            session["dev_auth"] = True
            session.modified = True
            return redirect("/dev")
        error = "Login ou mot de passe invalide."

    error_html = ("<p class='bad'>" + esc(error) + "</p>") if error else ""
    if dev_uses_default:
        error_html += pincabos_credentials_default_notice(
            expected_user, expected_pass, "/dev",
            "pincabos-admin-password --set-dev",
        )
    return page("Connexion développeur", """
<div class="card"><h1>🔐 Connexion développeur</h1>""" + error_html + """
<form method="post" action="/dev/login" autocomplete="off">
<label>Login<br><input type="text" name="username" autocomplete="username" required></label><br>
<label>Mot de passe<br><input type="password" name="password" autocomplete="current-password" required></label><br>
<button class="button" type="submit">Connexion</button>
<a class="button secondary" href="/about">Retour</a>
</form></div>
""")


@route("/dev/submit", methods=["POST"])
def pincabos_dev_submit():
    if not pincabos_dev_is_logged():
        return redirect("/dev/login")
    required = ["first_name", "last_name", "title", "comments"]
    missing = [key for key in required if not request.form.get(key, "").strip()]
    if missing or request.form.get("consent_alpha") != "1":
        return page("Rapport développeur", """
<div class="card"><h2>Rapport incomplet</h2>
<p class="bad">Les champs obligatoires et le consentement Alpha doivent être remplis.</p>
<p><a class="button secondary" href="/dev">Retour</a></p></div>
"""), 400

    payload = {key: request.form.get(key, "").strip() for key in [
        "first_name", "last_name", "nickname", "email", "report_type", "affected_area",
        "severity", "title", "comments", "solution_text",
    ]}
    payload["has_solution"] = request.form.get("has_solution") == "1"
    payload["source"] = "PinCabOS WebApp"
    payload["submitted_at"] = datetime.now().isoformat(timespec="seconds")
    try:
        ok, response_text = pincabos_send_feedback_remote(payload)
    except Exception as exc:
        ok, response_text = False, str(exc)

    css = "ok" if ok else "bad"
    heading = "Rapport envoyé" if ok else "Envoi impossible"
    message = esc(response_text or ("GO" if ok else "Le serveur n’a pas accepté le rapport."))
    body = (
        '<div class="card"><h2>' + esc(heading) + '</h2>'
        '<p class="' + css + '">' + message + '</p>'
        '<p><a class="button" href="/dev">Retour développeur</a></p></div>'
    )
    return page("Rapport développeur", body), (200 if ok else 502)


@route("/dev/cleanup-nosnap", methods=["POST"])
def pincabos_dev_cleanup_nosnap():
    if not pincabos_dev_is_logged():
        return redirect("/dev/login")
    script = Path("/opt/pincabos/tools/pincabos-cleanup-nosnap.sh")
    if not script.is_file() or not os.access(script, os.X_OK):
        return page("Nettoyage développeur", """
<div class="card"><h2>Nettoyage non lancé</h2>
<p class="warn">Aucun script de nettoyage explicite et exécutable n’est installé. Aucune suppression n’a été effectuée.</p>
<p><code>/opt/pincabos/tools/pincabos-cleanup-nosnap.sh</code></p>
<p><a class="button secondary" href="/dev">Retour</a></p></div>
"""), 409
    subprocess.Popen(["/usr/bin/sudo", "-n", str(script)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return page("Nettoyage développeur", """
<div class="card"><h2>Nettoyage lancé</h2><p class="ok">Le script de nettoyage configuré a été démarré.</p>
<p><a class="button" href="/dev">Retour</a></p></div>
""")
