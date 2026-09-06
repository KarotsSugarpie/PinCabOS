"""Console système, réseau (hotspot Wi-Fi), écran WebApp et mot de passe root de la WebApp PinCabOS.

Code déplacé tel quel depuis app.py (PINCABOS_WEBAPP_MODULES_V1) ; les routes gardent
leurs chemins et leurs noms de fonction. `page()` (gabarit commun) est fourni par app.py
à l'enregistrement : `register(app, page)`.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from flask import Blueprint, redirect, request, url_for

from pincabos_webapp_core import esc, get_ip, pco_script, run_cmd
from pincabos_webapp_dev_admin import pincabos_admin_require_login

console_bp = Blueprint("console", __name__)

page = None  # gabarit HTML commun, posé par register()


@console_bp.route("/console")
@console_bp.route("/console/")
def console_page():
    ip = get_ip()
    console_url = f"http://{ip}:8090"

    body = f"""
<style>
  body {{
    background:
      radial-gradient(circle at top, rgba(16,0,28,.16), transparent 34%),
      linear-gradient(180deg, #000000 0%, #010003 55%, #000000 100%) !important;
  }}

  .pco-console-card {{
      background: rgba(29, 11, 46, 0.76) !important;
      border: 1px solid var(--pco-appearance-accent2, #ff7a00) !important;
      border-radius: var(--pco-appearance-card-radius, 18px);
      box-shadow: var(--pco-appearance-card-shadow, 0 0 25px rgba(255, 122, 0, 0.25));
    }}

    .pco-console-frame-wrap {{
    background: #000;
    border: 1px solid rgba(42, 14, 70, .42);
    border-radius: 14px;
    padding: 8px;
    box-shadow:
      inset 0 0 36px rgba(0, 0, 0, 1),
      0 0 42px rgba(0, 0, 0, .95);
  }}

  #pincabos-console-frame {{
    background: #000 !important;
    filter: brightness(.66) contrast(1.18) saturate(.82);
  }}

  /* PINCABOS_CONSOLE_DOCTOR_HELP_V1 */
  /* PINCABOS_CONSOLE_DOCTOR_COMPACT_V2 */

  .pco-console-top-grid {{
    display: grid;
    grid-template-columns:
      minmax(300px, .54fr)
      minmax(0, 1.46fr);
    gap: 12px;
    align-items: start;
    margin-bottom: 8px;
  }}

  .pco-console-top-grid .pco-console-info {{
    margin: 0 !important;
    padding: 10px 14px !important;
    min-width: 0;
    height: auto !important;
    box-sizing: border-box;
  }}

  .pco-console-top-grid .pco-console-info h2 {{
    margin: 0 0 3px !important;
    font-size: 17px;
    line-height: 1.2;
  }}

  .pco-console-top-grid .pco-console-info p {{
    margin: 0 0 3px !important;
    line-height: 1.25;
  }}

  .pco-doctor-help-card {{
    min-width: 0;
    padding: 10px 14px;
    box-sizing: border-box;
    border-radius: var(--pco-appearance-card-radius, 18px);
    border: 1px solid rgba(153, 82, 211, .72);
    background:
      linear-gradient(
        135deg,
        rgba(53, 19, 82, .94),
        rgba(20, 7, 34, .96)
      );
    box-shadow:
      inset 0 0 18px rgba(139, 68, 194, .08),
      0 0 18px rgba(95, 42, 145, .16);
    color: #fff;
  }}

  .pco-doctor-help-card h2 {{
    margin: 0 0 3px;
    color: #ffb000;
    font-size: 17px;
    line-height: 1.2;
  }}

  .pco-doctor-help-intro {{
    margin: 0 0 6px;
    color: #e3d6ec;
    font-size: 11px;
    line-height: 1.25;
  }}

  .pco-doctor-command-grid {{
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    column-gap: 22px;
    row-gap: 1px;
  }}

  .pco-doctor-command {{
    display: grid;
    grid-template-columns: max-content minmax(0, 1fr);
    gap: 8px;
    align-items: center;
    min-width: 0;
    padding: 2px 0;
    border: 0;
    border-radius: 0;
    background: none;
    box-shadow: none;
  }}

  .pco-doctor-command code {{
    display: inline-block;
    width: auto;
    max-width: 100%;
    margin: 0;
    padding: 2px 6px;
    border: 1px solid rgba(255, 122, 0, .72);
    border-radius: 6px;
    background: #050007;
    color: #fff;
    font-size: 11px;
    font-weight: 800;
    line-height: 1.15;
    white-space: nowrap;
  }}

  .pco-doctor-command span {{
    display: block;
    min-width: 0;
    margin: 0;
    color: #ddd0e7;
    font-size: 10.5px;
    line-height: 1.2;
  }}

  .pco-doctor-system-option {{
    border: 0;
    background: none;
  }}

  .pco-doctor-system-note {{
    display: inline;
    margin-left: 4px;
    color: #ffb000;
    font-size: 8px;
    font-weight: 800;
    text-transform: uppercase;
  }}

  @media (max-width: 1320px) {{
    .pco-console-top-grid {{
      grid-template-columns: 1fr;
    }}
  }}

  @media (max-width: 900px) {{
    .pco-doctor-command-grid {{
      grid-template-columns: 1fr;
    }}
  }}

</style>

<div class="card pco-console-card">
  <!-- PINCABOS_CONSOLE_DOCTOR_HELP_V1 -->
  <div class="pco-console-top-grid">
    <div class="pco-console-info" style="
  margin: 0 0 14px 0;
  padding: 14px 16px;
  border-radius: var(--pco-appearance-card-radius, 18px);
  background: var(--pco-appearance-card-bg, rgba(29, 11, 46, 0.76));
  border: 1px solid var(--pco-appearance-card-border, #ff7a00);
  box-shadow: 0 0 25px rgba(255, 122, 0, 0.18);
  color: #fff;
  line-height: 1.45;
">
  <h2 style="margin:0 0 5px 0;color:#ffb000;">PinCab Console</h2>
  <p style="margin:0 0 8px 0;">Terminal Web PinCabOS.</p>

  <p style="margin:0 0 8px 0;">La console est protégée par un identifiant séparé.</p>

  <p style="margin:0 0 5px 0;"><strong>URL directe :</strong></p>
  <p style="margin:0 0 8px 0;">
    <a href="{console_url}" target="_blank" rel="noopener" style="color:#ffb000;">
      {console_url}
    </a>
  </p>

  <p style="margin:0 0 10px 0;">
    <a class="button" href="{console_url}" target="_blank" rel="noopener">
      Ouvrir la console dans un nouvel onglet
    </a>
  </p>

  <div style="
    display:inline-flex;
    align-items:center;
    gap:7px;
    margin:0;
    padding:4px 7px;
    border-radius:999px;
    border:1px solid rgba(255,176,0,.35);
    background:rgba(255,176,0,.08);
    color:#fff;
    font-size:12px;
    line-height:1.1;
  ">
    <span style="color:#ffb000;font-weight:700;">Root :</span>
    <code style="
      display:inline-block;
      margin:0;
      padding:2px 6px;
      border-radius:6px;
      background:#050007;
      color:#00ff99;
      font-size:12px;
      line-height:1.1;
      font-weight:700;
      border:1px solid #5f2a91;
    ">sudo -i</code>
  </div>
</div>

  <section
    class="pco-doctor-help-card"
    aria-labelledby="pco-doctor-help-title">

    <h2 id="pco-doctor-help-title">
      PinCabOS Doctor — commandes
    </h2>

    <p class="pco-doctor-help-intro">
      La commande installée est
      <code class="notranslate" translate="no">pincabos</code>.
      Elle exécute le System Doctor et enregistre ses rapports dans
      <code class="notranslate" translate="no">/var/log/pincabos</code>.
    </p>

    <div class="pco-doctor-command-grid">

      <div class="pco-doctor-command">
        <code class="notranslate" translate="no">pincabos</code>
        <span>
          Audit complet et réparations sécuritaires autorisées.
        </span>
      </div>

      <div class="pco-doctor-command">
        <code class="notranslate" translate="no">
          pincabos --check
        </code>
        <span>
          Vérifie tout le système sans effectuer de modification.
        </span>
      </div>

      <div class="pco-doctor-command">
        <code class="notranslate" translate="no">
          pincabos --repair
        </code>
        <span>
          Lance explicitement l’audit avec réparations sécuritaires.
        </span>
      </div>

      <div class="pco-doctor-command">
        <code class="notranslate" translate="no">
          pincabos --report
        </code>
        <span>
          Affiche le dernier rapport Doctor enregistré.
        </span>
      </div>

      <div class="pco-doctor-command">
        <code class="notranslate" translate="no">
          pincabos --repair --no-restart
        </code>
        <span>
          Répare sans redémarrer les services pendant l’audit.
        </span>
      </div>

      <div class="pco-doctor-command pco-doctor-system-option">
        <code class="notranslate" translate="no">
          pincabos --firstboot
        </code>
        <span>
          Finalisation automatique du premier démarrage.
          <b class="pco-doctor-system-note">système</b>
        </span>
      </div>

      <div class="pco-doctor-command">
        <code class="notranslate" translate="no">
          pincabos --help
        </code>
        <span>
          Affiche toutes les commandes disponibles.
        </span>
      </div>

      <div class="pco-doctor-command">
        <code class="notranslate" translate="no">
          pincabos -h
        </code>
        <span>
          Forme courte de la commande d’aide.
        </span>
      </div>

    </div>
  </section>
  </div>

<iframe
      id="pincabos-console-frame"
      src="{console_url}"
      allowfullscreen
      style="width:100%; height:78vh; min-height:720px; border:0; border-radius:10px; background:#000;">
    </iframe>
  </div>
</div>

<script>
function openPinCabConsoleFullscreen() {{
  const url = "{console_url}";
  const w = screen.availWidth || window.innerWidth || 1280;
  const h = screen.availHeight || window.innerHeight || 720;

  window.open(
    url,
    "PinCabOSConsoleCommander",
    "popup=yes,width=" + w + ",height=" + h + ",left=0,top=0,menubar=no,toolbar=no,location=no,status=no,scrollbars=no,resizable=yes"
  );
}}
</script>
"""
    return page("Console", body)

@console_bp.route("/root-password", methods=["POST"])
def root_password():
    guard = pincabos_admin_require_login()
    if guard:
        return guard

    p1 = request.form.get("password1", "")
    p2 = request.form.get("password2", "")

    if not p1 or not p2:
        body = """
<div class="card">
  <h2>Erreur</h2>
  <p class="bad">Le mot de passe ne peut pas être vide.</p>
  <p><a class="button" href="/console">Retour console</a></p>
</div>
"""
        return page("Console", body)

    if p1 != p2:
        body = """
<div class="card">
  <h2>Erreur</h2>
  <p class="bad">Les deux mots de passe ne correspondent pas.</p>
  <p><a class="button" href="/console">Retour console</a></p>
</div>
"""
        return page("Console", body)

    try:
        r = subprocess.run(
            ["/usr/bin/sudo", str(pco_script("change_root_password"))],
            input=p1 + "\\n",
            capture_output=True,
            text=True,
            timeout=10
        )

        if r.returncode == 0:
            msg = esc(r.stdout.strip() or "Mot de passe root changé.")
            body = f"""
<div class="card">
  <h2>Mot de passe root</h2>
  <p class="ok">{msg}</p>
  <p><a class="button" href="/console">Retour console</a></p>
</div>
"""
        else:
            msg = esc((r.stdout + r.stderr).strip())
            body = f"""
<div class="card">
  <h2>Erreur</h2>
  <p class="bad">Impossible de changer le mot de passe root.</p>
  <pre>{msg}</pre>
  <p><a class="button" href="/console">Retour console</a></p>
</div>
"""

    except Exception as e:
        body = f"""
<div class="card">
  <h2>Erreur</h2>
  <p class="bad">{esc(str(e))}</p>
  <p><a class="button" href="/console">Retour console</a></p>
</div>
"""

    return page("Console", body)


def network_info_text():
    return run_cmd(["/usr/bin/sudo", str(pco_script("network_info"))], timeout=15)


def network_current_mode():
    out = run_cmd(["/usr/bin/sudo", str(pco_script("network_current_mode"))], timeout=8)
    data = {}
    for line in out.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()
    return data


def network_main_iface():
    data = network_current_mode()
    return data.get("interface", "") or "non détectée"


def wifi_options_html():
    out = run_cmd(["/usr/bin/sudo", str(pco_script("wifi_scan"))], timeout=15)
    rows = []

    if not out.strip():
        return '<option value="">Aucun réseau WiFi détecté</option>'

    seen = set()
    for line in out.splitlines():
        parts = line.split("|")
        ssid = parts[0].strip() if len(parts) >= 1 else ""
        signal = parts[1].strip() if len(parts) >= 2 else ""
        security = parts[2].strip() if len(parts) >= 3 else ""

        if not ssid or ssid in seen:
            continue

        seen.add(ssid)
        label = ssid
        if signal:
            label += f" — signal {signal}%"
        if security:
            label += f" — {security}"

        rows.append(f'<option value="{esc(ssid)}">{esc(label)}</option>')

    return "\n".join(rows) if rows else '<option value="">Aucun réseau WiFi détecté</option>'


# PINCABOS_RESEAU_V1 : /network, /network/apply-mode, /network/wifi-join et
# /network/hostname vivent dans pincabos_webapp_network.py (module pincabos_network).
def network_action_result(title, output):
    body = f"""
<div class="card">
  <h2>{esc(title)}</h2>
  <pre>{esc(output)}</pre>
  <p><a class="button" href="/network">Retour Réseau</a></p>
</div>
"""
    return page("Réseau", body)


@console_bp.route("/network/wifi-hotspot", methods=["POST"])
def network_wifi_hotspot():
    ssid = request.form.get("ssid", "PinCabOS_WiFi").strip() or "PinCabOS_WiFi"
    password = (request.form.get("password", "") or "").strip()

    out = run_cmd(
        ["/usr/bin/sudo", str(pco_script("wifi_hotspot")), ssid, password],
        timeout=40
    )
    return network_action_result("Hotspot WiFi — activation", out)


@console_bp.route("/network/wifi-hotspot-stop", methods=["POST"])
def network_wifi_hotspot_stop():
    out = run_cmd(
        ["/usr/bin/sudo", str(pco_script("wifi_hotspot_stop"))],
        timeout=30
    )
    return network_action_result("Hotspot WiFi — désactivation", out)


@console_bp.route("/toggle-webapp-screen", methods=["POST"])
def toggle_webapp_screen():
    try:
        screen = request.form.get("screen", "").strip().lower()

        if screen not in ["playfield", "backglass"]:
            return redirect(request.referrer or url_for("dashboard"))

        conf_path = Path("/opt/pincabos/config/webapp-screen-autostart.conf")
        conf_path.parent.mkdir(parents=True, exist_ok=True)

        state = {"playfield": "0", "backglass": "0"}

        if conf_path.exists():
            for line in conf_path.read_text(errors="replace").splitlines():
                line = line.strip()
                if "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip().upper()
                v = "1" if v.strip() == "1" else "0"

                if k == "PLAYFIELD":
                    state["playfield"] = v
                elif k == "BACKGLASS":
                    state["backglass"] = v

        state[screen] = "0" if state.get(screen) == "1" else "1"

        conf_path.write_text(
            f"PLAYFIELD={state['playfield']}\nBACKGLASS={state['backglass']}\n"
        )

        subprocess.Popen(
            ["/usr/bin/sudo", str(pco_script("close_webapp_screen"))],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        if state["playfield"] == "1":
            subprocess.Popen(
                ["/usr/bin/sudo", str(pco_script("launch_webapp_screen")), "0", "http://127.0.0.1/"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

        if state["backglass"] == "1":
            subprocess.Popen(
                ["/usr/bin/sudo", str(pco_script("launch_webapp_screen")), "1", "http://127.0.0.1/"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

        return redirect(request.referrer or url_for("dashboard"))

    except Exception as e:
        return f"Erreur toggle écran WebApp: {e}", 500


@console_bp.route("/launch-webapp-screen", methods=["POST"])
def launch_webapp_screen():
    screen = request.form.get("screen", "0").strip()

    if screen not in ["0", "1", "2"]:
        screen = "0"

    subprocess.Popen(
        ["/usr/bin/sudo", str(pco_script("launch_webapp_screen")), screen, "http://127.0.0.1/"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    return redirect(request.referrer or url_for("dashboard"))


@console_bp.route("/close-webapp-screen", methods=["POST"])
def close_webapp_screen():
    subprocess.Popen(
        ["/usr/bin/sudo", str(pco_script("close_webapp_screen"))],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    return redirect(request.referrer or url_for("dashboard"))


def register(app, page_fn):
    """Enregistre la console, le réseau, l'écran WebApp et le mot de passe root sur l'application."""
    global page
    page = page_fn
    app.register_blueprint(console_bp)
