"""Pages DMD / FullDMD de la WebApp PinCabOS (/fulldmd, /dmd, calibrateurs, /api/fulldmd, /api/dmd).

Code déplacé tel quel depuis app.py (PINCABOS_WEBAPP_MODULES_V1) ; les routes gardent
leurs chemins et leurs noms de fonction. `page()` (gabarit commun) est fourni par app.py
à l'enregistrement : `register(app, page)`.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, redirect, request, url_for

from pincabos_webapp_core import esc, pco_script, pincabos_backup_config_file, pincabos_vpinfe_ini_path, pincabos_vpx_ini_path, pincabos_write_json_with_meta, run_cmd

try:
    import pincabos_ini
except ImportError:   # hors /opt (tests, depot) : le module vit a cote des outils
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "tools"))
    import pincabos_ini

dmd_bp = Blueprint("dmd", __name__)

page = None  # gabarit HTML commun, posé par register()


def load_fulldmd_calibration():
    cfg = Path("/opt/pincabos/config/fulldmd-calibration.json")
    default = {
        "screen_id": "",
        "x": 0,
        "y": 0,
        "width": 800,
        "height": 300,
        "note": "PinCabOS FullDMD calibration"
    }

    try:
        if cfg.exists():
            data = json.loads(cfg.read_text())
            default.update(data)
    except Exception:
        pass

    return default


def pincabos_set_ini_key_plain(lines, section, key, value):
    """
    Modifie/ajoute une clé INI sans ajouter de commentaire PinCabOS.
    Utilisé pour les INI officiels VPinFE/VPX afin de ne pas les polluer.
    PINCABOS_INI_UNIQUE_V1 : délégué à l'écrivain unique (commentaire PinCabOS au-dessus retiré).
    """
    ini = pincabos_ini.Ini("\n".join(lines))
    ini.poser(section, key, value, purger_commentaire=True)
    return ini.lignes


def save_fulldmd_to_configs(data):
    function_name = "FullDMD Save"

    raw_screen_id = str(data.get("screen_id", "")).strip()
    screen_id = raw_screen_id if raw_screen_id.isdigit() else "2"
    x = int(data.get("x", 0))
    y = int(data.get("y", 0))
    w = int(data.get("width", 0))
    h = int(data.get("height", 0))

    # Format attendu par les clés legacy VPinFE/VPinball.
    geometry = f"{x},{y},{w},{h}"
    geometry_x11 = f"{w}x{h}+{x}+{y}"

    Path("/opt/pincabos/config").mkdir(parents=True, exist_ok=True)

    # JSON PinCabOS seulement. Les détails avancés restent ici, pas dans les INI officiels.
    fulldmd_json = Path("/opt/pincabos/config/fulldmd-calibration.json")
    pincabos_backup_config_file(fulldmd_json, function_name)
    pincabos_write_json_with_meta(fulldmd_json, {
        "screen_id": screen_id,
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "geometry": geometry,
        "geometry_x11": geometry_x11,
        "note": "PinCabOS FullDMD visible area calibration"
    }, function_name)

    subprocess.run(["/bin/chown", "-R", "pinball:pinball", "/opt/pincabos/config"], timeout=5)

    # Un seul ecrivain pour les INI : la topologie ecran rederive
    # [Displays] / [PinCabOs.*] des deux INI depuis screens.json + cette
    # calibration (le shim sync-dmd-calibrations invoque la topologie).
    try:
        subprocess.run(
            ["/usr/bin/sudo", str(pco_script("sync_dmd_calibrations"))],
            timeout=20,
            check=False,
        )
    except Exception:
        pass


# === PINCABOS FULLDMD/DMD PAGE HELPERS START ===
def load_dmd_calibration():
    cfg = Path("/opt/pincabos/config/dmd-calibration.json")
    default = {"screen_id": 2, "x": 80, "y": 40, "width": 512, "height": 128, "geometry": "512x128+80+40"}
    try:
        if cfg.exists():
            data = json.loads(cfg.read_text(errors="replace"))
            for k, v in default.items():
                data.setdefault(k, v)
            return data
    except Exception:
        pass
    return default

def pincabos_ini_section_summary(path_str):
    path = Path(path_str)
    wanted = {"pincabos.fulldmd", "pincabos.dmd", "pincabos.screens", "displays"}   # sans la casse (INI_UNIQUE_V1)
    if not path.exists():
        return f"ABSENT: {path}"
    lines = path.read_text(errors="replace").splitlines()
    out = []
    keep = False
    for line in lines:
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            sec = s[1:-1]
            keep = sec.strip().lower() in wanted
            if keep:
                if out:
                    out.append("")
                out.append(line)
            continue
        if keep:
            low = s.lower()
            if "dmd" in low or "screen" in low or "width" in low or "height" in low or "geometry" in low or low.startswith(("x", "y", "enabled")):
                out.append(line)
    return "\n".join(out).strip() or "Aucune valeur DMD/FullDMD trouvée."
# === PINCABOS FULLDMD/DMD PAGE HELPERS END ===

@dmd_bp.route("/fulldmd")
def fulldmd_page():
    cal = load_fulldmd_calibration()
    vpx_ini_summary = pincabos_ini_section_summary("/home/pinball/.local/share/VPinballX/10.8/VPinballX.ini")
    vpinfe_ini_summary = pincabos_ini_section_summary("/home/pinball/.config/vpinfe/vpinfe.ini")
    dmd_cal = load_dmd_calibration()
    vpx_ini_summary = pincabos_ini_section_summary("/home/pinball/.local/share/VPinballX/10.8/VPinballX.ini")
    vpinfe_ini_summary = pincabos_ini_section_summary("/home/pinball/.config/vpinfe/vpinfe.ini")

    screens_json = "{}"
    try:
        f = Path("/opt/pincabos/config/screens/screens.json")
        if f.exists():
            screens_json = f.read_text(errors="replace")
    except Exception:
        pass

    body = """
<div class="grid fulldmd-calibration-grid" style="display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:20px;align-items:start;">
  <div class="card">
    <h2>Calibration FullDMD</h2>
    <p><a href="/fulldmd/style" style="font-weight:bold;">&#127912; Style d'affichage FullDMD par table (art du pack / grand DMD)</a></p>
    <!-- PINCABOS_FULLDMD_ZEDMD_BLOCK_V1 : le ZeDMD vit ici, avec le reste du DMD -->
    <div style="margin:10px 0 14px;padding:10px 12px;border:1px solid #5f2a91;border-radius:10px;">
      <p style="margin:0 0 6px;"><b>&#128225; DMD LED reel (ZeDMD)</b> — <span id="zedmdSummary" style="opacity:.9;">lecture de l'etat…</span></p>
      <p style="margin:0;"><a class="button" href="/dmd/zedmd">Configurer le ZeDMD (USB / Wi-Fi, VPX et VPinFE)</a></p>
    </div>
    <script>
    (async () => {
      const el = document.getElementById('zedmdSummary');
      try {
        const d = await (await fetch('/api/zedmd/status')).json();
        const c = d.config || {};
        if (c.mode === 'off' || !c.mode) { el.textContent = 'desactive'; return; }
        const lien = c.mode === 'pin2dmd' ? 'PIN2DMD (USB)'
          : c.mode === 'wifi' ? ('ZeDMD Wi-Fi ' + (c.wifi_addr || '?'))
          : ('ZeDMD USB ' + (c.device || 'auto'));
        const cible = c.targets === 'both' ? 'menu VPinFE + jeu' : 'en jeu seulement';
        const vpx = (d.vpx && d.vpx.zedmd) ? 'VPX actif' : 'VPX inactif';
        const fe = (d.vpinfe && d.vpinfe.enabled) ? 'VPinFE actif' : 'VPinFE inactif';
        el.textContent = lien + ' · ' + cible + ' · ' + vpx + ' · ' + fe;
      } catch (e) { el.textContent = 'etat indisponible'; }
    })();
    </script>
    <p>Déplace et étire le rectangle pour représenter la zone visible du FullDMD.</p>
    <p>Config sauvegardée dans :</p>
    <p><code>/opt/pincabos/config/fulldmd-calibration.json</code></p>
    <p><code>Chemin VPinFE officiel</code></p>
    <p><code>/home/pinball/.config/vpinfe/vpinfe.ini</code></p>
    <p><code>Chemin VPX officiel</code></p>
    <p><code>/home/pinball/.local/share/VPinballX/10.8/VPinballX.ini</code></p>

    <label class="fulldmd-section-label">Écran FullDMD / DMD Screen ID</label>

    <div class="fulldmd-config-layout">
      <div class="fulldmd-fields-row">
        <div class="fulldmd-field">
          <label for="screen_id">Écran / Screen ID</label>
          <input id="screen_id" type="text" value="__SCREEN_ID__">
        </div>

        <div class="fulldmd-field">
          <label for="x">X</label>
          <input id="x" type="number" value="__X__">
        </div>

        <div class="fulldmd-field">
          <label for="y">Y</label>
          <input id="y" type="number" value="__Y__">
        </div>

        <div class="fulldmd-field">
          <label for="w">Largeur</label>
          <input id="w" type="number" value="__W__">
        </div>

        <div class="fulldmd-field">
          <label for="h">Hauteur</label>
          <input id="h" type="number" value="__H__">
        </div>
      </div>

      <div class="fulldmd-actions-column">
        __FULLDMD_TOGGLE_BUTTON__

        <form action="/fulldmd/apply" method="post">
          <button class="button secondary fulldmd-action-btn" type="submit">Appliquer FullDMD</button>
        </form>

        <a class="button secondary fulldmd-action-btn" href="/fulldmd">Rafraîchir</a>

        <button class="button fulldmd-action-btn" onclick="saveCal()">Sauvegarder FullDMD</button>
      </div>
    </div>

    <p id="save-status" class="warn"></p>
  </div>

  <div class="card">
    <h2>Calibration DMD global</h2>
    <p>Déplace et étire le rectangle pour représenter la position globale des DMD.</p>
    <p>Config sauvegardée dans :</p>
    <p><code>/opt/pincabos/config/dmd-calibration.json</code></p>
    <p><code>/home/pinball/.config/vpinfe/vpinfe.ini</code></p>
    <p><code>/home/pinball/.local/share/VPinballX/10.8/VPinballX.ini</code></p>

    <label class="fulldmd-section-label">Écran DMD / Screen ID</label>

    <div class="fulldmd-config-layout">
      <div class="fulldmd-fields-row">
        <div class="fulldmd-field">
          <label for="dmd_screen_id">Écran / Screen ID</label>
          <input id="dmd_screen_id" type="text" value="__DMD_SCREEN_ID__">
        </div>

        <div class="fulldmd-field">
          <label for="dmd_x">X</label>
          <input id="dmd_x" type="number" value="__DMD_X__">
        </div>

        <div class="fulldmd-field">
          <label for="dmd_y">Y</label>
          <input id="dmd_y" type="number" value="__DMD_Y__">
        </div>

        <div class="fulldmd-field">
          <label for="dmd_w">Largeur</label>
          <input id="dmd_w" type="number" value="__DMD_W__">
        </div>

        <div class="fulldmd-field">
          <label for="dmd_h">Hauteur</label>
          <input id="dmd_h" type="number" value="__DMD_H__">
        </div>
      </div>

      <div class="fulldmd-actions-column">
        __DMD_TOGGLE_BUTTON__
<form action="/dmd/apply" method="post">
          <button class="button secondary fulldmd-action-btn" type="submit">Appliquer DMD</button>
        </form>

        <a class="button secondary fulldmd-action-btn" href="/fulldmd">Rafraîchir</a>

        <button class="button fulldmd-action-btn" onclick="saveDmdCal()">Sauvegarder DMD</button>
      </div>
    </div>

    <p id="dmd-save-status" class="warn"></p>
  </div>

  <div class="card fulldmd-info-card" style="height:720px;display:flex;flex-direction:column;min-width:0;padding:18px;box-sizing:border-box;overflow:hidden;">
    <h2 style="margin:0 0 12px 0;flex:0 0 auto;">Écrans détectés</h2>
    <pre style="flex:1 1 auto;height:100%;min-height:0;max-height:none !important;width:100%;box-sizing:border-box;margin:0;overflow:auto;white-space:pre-wrap;word-break:break-word;">__SCREENS_JSON__</pre>
  </div>


  <div class="card fulldmd-info-card" style="height:720px;display:flex;flex-direction:column;min-width:0;padding:18px;box-sizing:border-box;overflow:hidden;">
    <h2 style="margin:0 0 12px 0;flex:0 0 auto;">Valeurs actuelles VPX / VPinFE</h2>

    <h3>VPX officiel</h3>
    <p><code>/home/pinball/.local/share/VPinballX/10.8/VPinballX.ini</code></p>
    <pre style="height:250px;min-height:0;max-height:none !important;width:100%;box-sizing:border-box;margin:0 0 12px 0;overflow:auto;white-space:pre-wrap;word-break:break-word;">__VPX_INI_SUMMARY__</pre>

    <h3>VPinFE officiel</h3>
    <p><code>/home/pinball/.config/vpinfe/vpinfe.ini</code></p>
    <pre style="height:250px;min-height:0;max-height:none !important;width:100%;box-sizing:border-box;margin:0;overflow:auto;white-space:pre-wrap;word-break:break-word;">__VPINFE_INI_SUMMARY__</pre>
  </div>

</div>

<script>
const stage = document.getElementById('stage');
const rect = document.getElementById('rect');
const handle = document.getElementById('handle');

let dragging = false;
let resizing = false;
let startX = 0;
let startY = 0;
let startLeft = 0;
let startTop = 0;
let startW = 0;
let startH = 0;

function num(id) {
  return parseInt(document.getElementById(id).value || '0', 10);
}

function syncInputs() {
  document.getElementById('x').value = parseInt(rect.style.left, 10) || 0;
  document.getElementById('y').value = parseInt(rect.style.top, 10) || 0;
  document.getElementById('w').value = parseInt(rect.style.width, 10) || 0;
  document.getElementById('h').value = parseInt(rect.style.height, 10) || 0;
}

function applyInputs() {
  rect.style.left = num('x') + 'px';
  rect.style.top = num('y') + 'px';
  rect.style.width = num('w') + 'px';
  rect.style.height = num('h') + 'px';
}

['x','y','w','h'].forEach(id => {
  document.getElementById(id).addEventListener('input', applyInputs);
});

rect.addEventListener('mousedown', e => {
  if (e.target === handle) return;
  dragging = true;
  startX = e.clientX;
  startY = e.clientY;
  startLeft = parseInt(rect.style.left, 10) || 0;
  startTop = parseInt(rect.style.top, 10) || 0;
  e.preventDefault();
});

handle.addEventListener('mousedown', e => {
  resizing = true;
  startX = e.clientX;
  startY = e.clientY;
  startW = parseInt(rect.style.width, 10) || 0;
  startH = parseInt(rect.style.height, 10) || 0;
  e.preventDefault();
  e.stopPropagation();
});

document.addEventListener('mousemove', e => {
  if (dragging) {
    let left = startLeft + (e.clientX - startX);
    let top = startTop + (e.clientY - startY);
    left = Math.max(0, Math.min(left, stage.clientWidth - rect.offsetWidth));
    top = Math.max(0, Math.min(top, stage.clientHeight - rect.offsetHeight));
    rect.style.left = left + 'px';
    rect.style.top = top + 'px';
    syncInputs();
  }

  if (resizing) {
    let w = startW + (e.clientX - startX);
    let h = startH + (e.clientY - startY);
    w = Math.max(40, Math.min(w, stage.clientWidth - (parseInt(rect.style.left, 10) || 0)));
    h = Math.max(30, Math.min(h, stage.clientHeight - (parseInt(rect.style.top, 10) || 0)));
    rect.style.width = w + 'px';
    rect.style.height = h + 'px';
    syncInputs();
  }
});

document.addEventListener('mouseup', () => {
  dragging = false;
  resizing = false;
});

function centerRect() {
  const w = parseInt(rect.style.width, 10) || 800;
  const h = parseInt(rect.style.height, 10) || 300;
  rect.style.left = Math.max(0, Math.floor((stage.clientWidth - w) / 2)) + 'px';
  rect.style.top = Math.max(0, Math.floor((stage.clientHeight - h) / 2)) + 'px';
  syncInputs();
}

function fitRect() {
  rect.style.left = '0px';
  rect.style.top = '0px';
  rect.style.width = stage.clientWidth + 'px';
  rect.style.height = stage.clientHeight + 'px';
  syncInputs();
}

async function saveCal() {
  const payload = {
    screen_id: document.getElementById('screen_id').value,
    x: num('x'),
    y: num('y'),
    width: num('w'),
    height: num('h')
  };

  const r = await fetch('/api/fulldmd/save', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });

  const data = await r.json();
  document.getElementById('save-status').textContent = data.message || 'Sauvegardé';
}

async function saveDmdCal() {
  const payload = {
    screen_id: document.getElementById('dmd_screen_id').value,
    x: parseInt(document.getElementById('dmd_x').value || '0', 10),
    y: parseInt(document.getElementById('dmd_y').value || '0', 10),
    width: parseInt(document.getElementById('dmd_w').value || '0', 10),
    height: parseInt(document.getElementById('dmd_h').value || '0', 10)
  };

  const r = await fetch('/api/dmd/save', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });

  const data = await r.json();
  document.getElementById('dmd-save-status').textContent =
    data.ok ? 'Calibration DMD sauvegardée et synchronisée.' : ('Erreur DMD: ' + (data.error || 'unknown'));
}

</script>
</div>
"""
    body = body.replace("__SCREEN_ID__", esc(cal.get("screen_id", "")))
    body = body.replace("__X__", esc(cal.get("x", 0)))
    body = body.replace("__Y__", esc(cal.get("y", 0)))
    body = body.replace("__W__", esc(cal.get("width", 800)))
    body = body.replace("__H__", esc(cal.get("height", 300)))
    body = body.replace("__SCREENS_JSON__", esc(screens_json))
    body = body.replace("__FULLDMD_TOGGLE_BUTTON__", pincabos_fulldmd_toggle_button())
    body = body.replace("__DMD_TOGGLE_BUTTON__", pincabos_dmd_toggle_button())
    body = body.replace("__DMD_SCREEN_ID__", esc(dmd_cal.get("screen_id", "")))
    body = body.replace("__DMD_X__", esc(dmd_cal.get("x", 0)))
    body = body.replace("__DMD_Y__", esc(dmd_cal.get("y", 0)))
    body = body.replace("__DMD_W__", esc(dmd_cal.get("width", 512)))
    body = body.replace("__DMD_H__", esc(dmd_cal.get("height", 128)))
    body = body.replace("__VPX_INI_SUMMARY__", esc(vpx_ini_summary))
    body = body.replace("__VPINFE_INI_SUMMARY__", esc(vpinfe_ini_summary))

    return page("FullDMD", body)


# ---------------------------------------------------------------------------
# Style d'affichage FullDMD par table : art du pack vs grand DMD seul.
# Consomme par pincabos-native-fulldmd-policy.sh :
#   - sidecar <table>.pincabos-fulldmd.json  {"style": "art"|"dmd"}
#   - defaut global /opt/pincabos/config/fulldmd-style.conf ("art" ou "dmd")
# "auto" = aucun fichier -> defaut intelligent de la policy (art si la table
# fournit un DMDImage d'auteur, grand DMD si l'art ne serait qu'un panneau
# grill auto-genere). Applique au prochain lancement de la table.
# ---------------------------------------------------------------------------

PINCABOS_FULLDMD_STYLE_GLOBAL = Path("/opt/pincabos/config/fulldmd-style.conf")


def pincabos_fulldmd_style_tables():
    """Tables candidates (un .vpx + un .directb2s) et leur style choisi."""
    rows = []
    root = Path("/home/pinball/Tables")
    try:
        dirs = sorted(
            [d for d in root.iterdir() if d.is_dir()],
            key=lambda d: d.name.lower(),
        )
    except OSError:
        return rows
    for d in dirs:
        try:
            vpx = sorted(d.glob("*.vpx"))
            if not vpx:
                continue
            has_b2s = any(
                p.suffix.lower() == ".directb2s"
                for p in d.iterdir()
                if p.is_file()
            )
        except OSError:
            continue
        if not has_b2s:
            continue
        sidecar = vpx[0].with_suffix(".pincabos-fulldmd.json")
        style = "auto"
        try:
            value = str(
                json.loads(sidecar.read_text(encoding="utf-8")).get("style", "")
            ).lower()
            if value in ("art", "dmd"):
                style = value
        except Exception:
            pass
        rows.append({"name": d.name, "style": style})
    return rows


@dmd_bp.route("/fulldmd/style")
def fulldmd_style_page():
    global_style = "auto"
    try:
        value = PINCABOS_FULLDMD_STYLE_GLOBAL.read_text(encoding="utf-8").strip().lower()
        if value in ("art", "dmd"):
            global_style = value
    except Exception:
        pass

    def options_html(current):
        parts = []
        for value, label in (
            ("auto", "Auto"),
            ("art", "Art du pack"),
            ("dmd", "Grand DMD"),
        ):
            selected = " selected" if current == value else ""
            parts.append(f'<option value="{value}"{selected}>{label}</option>')
        return "".join(parts)

    rows_html = []
    for row in pincabos_fulldmd_style_tables():
        rows_html.append(
            "<tr>"
            f"<td style=\"padding:6px 10px;\">{esc(row['name'])}</td>"
            "<td style=\"padding:6px 10px;\">"
            f"<select class=\"fdstyle-select\" data-table=\"{esc(row['name'])}\" "
            "onchange=\"fdstyleSet(this, this.dataset.table)\" style=\"padding:6px;\">"
            f"{options_html(row['style'])}"
            "</select></td>"
            "<td class=\"fdstyle-status\" style=\"padding:6px 10px;min-width:180px;opacity:.85;\"></td>"
            "</tr>"
        )
    if not rows_html:
        rows_html.append(
            "<tr><td colspan=\"3\" style=\"padding:10px;\">"
            "Aucune table avec directb2s trouvée.</td></tr>"
        )

    body = """
<div class="card">
  <h2>Style d'affichage FullDMD</h2>
  <p>Pour chaque table B2S, choisis ce que l'écran FullDMD affiche :</p>
  <ul>
    <li><b>Art du pack</b> : l'art FullDMD du directb2s (image d'auteur, ou panneau
        haut-parleurs généré depuis le grill) avec le DMD posé dedans.</li>
    <li><b>Grand DMD</b> : uniquement le DMD, en grand (ratio 4:1, pleine largeur,
        fond noir).</li>
    <li><b>Auto</b> : art si la table fournit une vraie image FullDMD d'auteur,
        grand DMD sinon.</li>
  </ul>
  <p style="opacity:.8;">Le choix s'applique au <b>prochain lancement</b> de la table.</p>

  <h3>Défaut du cabinet</h3>
  <p>
    <select onchange="fdstyleSet(this, null)" style="padding:6px;">__GLOBAL_OPTIONS__</select>
    <span id="fdstyle-global-status" style="margin-left:10px;opacity:.85;"></span>
  </p>

  <h3>Par table</h3>
  <table style="border-collapse:collapse;width:100%;">
    <tr>
      <th style="text-align:left;padding:6px 10px;">Table</th>
      <th style="text-align:left;padding:6px 10px;">Style</th>
      <th></th>
    </tr>
    __ROWS__
  </table>

  <p style="margin-top:14px;"><a href="/fulldmd">&larr; Retour calibration FullDMD</a></p>
</div>

<script>
async function fdstyleSet(sel, table) {
  const status = table === null
    ? document.getElementById('fdstyle-global-status')
    : sel.closest('tr').querySelector('.fdstyle-status');
  status.textContent = '...';
  try {
    const r = await fetch('/api/fulldmd/style/set', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ table: table, style: sel.value })
    });
    const d = await r.json();
    status.textContent = d.ok
      ? 'Enregistré — appliqué au prochain lancement'
      : ('Erreur : ' + (d.error || '?'));
  } catch (e) {
    status.textContent = 'Erreur réseau';
  }
}
</script>
"""
    body = body.replace("__GLOBAL_OPTIONS__", options_html(global_style))
    body = body.replace("__ROWS__", "\n    ".join(rows_html))
    return page("Style FullDMD", body)


@dmd_bp.route("/api/fulldmd/style/set", methods=["POST"])
def api_fulldmd_style_set():
    data = request.get_json(silent=True) or {}
    style = str(data.get("style", "")).lower()
    if style not in ("auto", "art", "dmd"):
        return jsonify({"ok": False, "error": "style invalide"}), 400

    table = data.get("table")
    if table is None:
        try:
            if style == "auto":
                PINCABOS_FULLDMD_STYLE_GLOBAL.unlink(missing_ok=True)
            else:
                PINCABOS_FULLDMD_STYLE_GLOBAL.parent.mkdir(parents=True, exist_ok=True)
                PINCABOS_FULLDMD_STYLE_GLOBAL.write_text(style + "\n", encoding="utf-8")
        except OSError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500
        return jsonify({"ok": True, "scope": "global", "style": style})

    table = str(table)
    if "/" in table or "\\" in table or table.startswith("."):
        return jsonify({"ok": False, "error": "table invalide"}), 400
    table_dir = Path("/home/pinball/Tables") / table
    if not table_dir.is_dir():
        return jsonify({"ok": False, "error": "table introuvable"}), 404
    vpx = sorted(table_dir.glob("*.vpx"))
    if not vpx:
        return jsonify({"ok": False, "error": "vpx introuvable"}), 404

    sidecar = vpx[0].with_suffix(".pincabos-fulldmd.json")
    try:
        if style == "auto":
            sidecar.unlink(missing_ok=True)
        else:
            sidecar.write_text(json.dumps({"style": style}) + "\n", encoding="utf-8")
            shutil.chown(sidecar, "pinball", "pinball")
    except OSError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
    return jsonify({"ok": True, "table": table, "style": style})


@dmd_bp.route("/api/fulldmd/status")
def api_fulldmd_status():
    return jsonify({
        "ok": True,
        "log": "Log temps réel FullDMD désactivé.",
        "message": "Log temps réel désactivé."
    })


@dmd_bp.route("/api/fulldmd/save", methods=["POST"])
def api_fulldmd_save():
    try:
        data = request.get_json(force=True)
        save_fulldmd_to_configs(data)
        try:
            live_log = Path("/opt/pincabos/logs/fulldmd-live.log")
            live_log.parent.mkdir(parents=True, exist_ok=True)
            with live_log.open("a") as f:
                f.write("\n==================================================\n")
                f.write("Sauvegarde FullDMD depuis calibrateur Web\n")
                f.write(f"screen_id={data.get('screen_id', '')}\n")
                f.write(f"x={data.get('x', 0)}\n")
                f.write(f"y={data.get('y', 0)}\n")
                f.write(f"width={data.get('width', 0)}\n")
                f.write(f"height={data.get('height', 0)}\n")
                f.write(f"geometry={data.get('x', 0)},{data.get('y', 0)},{data.get('width', 0)},{data.get('height', 0)}\n")
                f.write("==================================================\n")
        except Exception:
            pass
        try:
            log = Path("/opt/pincabos/logs/fulldmd-calibration.log")
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text(
                "Dernière sauvegarde FullDMD\\n"
                f"screen_id={data.get('screen_id', '')}\\n"
                f"x={data.get('x', 0)}\\n"
                f"y={data.get('y', 0)}\\n"
                f"width={data.get('width', 0)}\\n"
                f"height={data.get('height', 0)}\\n"
                f"geometry={data.get('x', 0)},{data.get('y', 0)},{data.get('width', 0)},{data.get('height', 0)}\\n"
            )
        except Exception:
            pass
        return jsonify({"ok": True, "message": "Calibration FullDMD sauvegardée."})
    except Exception as e:
        return jsonify({"ok": False, "message": f"Erreur: {e}"}), 500


# === PINCABOS FULLDMD TOGGLE BUTTON START ===
FULLDMD_ACTIVE_STATE = Path("/run/pincabos-fulldmd-calibrator.active")

def pincabos_fulldmd_calibrator_running():
    """
    Détection calibrateur FullDMD.
    Important: le fichier /run peut devenir stale.
    Source de vérité: process Chrome avec profil/URL FullDMD.
    """
    import subprocess
    import time

    try:
        out = subprocess.check_output(
            ["/usr/bin/pgrep", "-af", "pincabos_fulldmd_calibrator_screen|pincabos-fulldmd-calibrator|/fulldmd-screen"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        lines = []
        for line in out.splitlines():
            low = line.lower()
            if "grep" in low:
                continue
            if "pincabos_fulldmd_calibrator_screen" in low or "pincabos-fulldmd-calibrator" in low or "/fulldmd-screen" in low:
                lines.append(line)
        if lines:
            try:
                FULLDMD_ACTIVE_STATE.write_text(str(time.time()) + "\n", encoding="utf-8")
                FULLDMD_ACTIVE_STATE.chmod(0o666)
            except Exception:
                pass
            return True
    except Exception:
        pass

    # Si aucun process réel, l'état /run est fantôme.
    try:
        FULLDMD_ACTIVE_STATE.unlink(missing_ok=True)
    except Exception:
        pass

    return False


def pincabos_fulldmd_toggle_button():
    if pincabos_fulldmd_calibrator_running():
        return """
        <form action="/close-fulldmd-calibrator" method="post">
          <button class="button fulldmd-action-btn fulldmd-toggle-active" type="submit"
                  style="background:#ff7a00 !important;color:#160020 !important;border:1px solid #ffb000 !important;box-shadow:0 0 18px rgba(255,122,0,.9),0 0 28px rgba(255,176,0,.45) !important;">
            Fermer Calibration FullDMD
          </button>
        </form>
        """
    return """
        <form action="/launch-fulldmd-calibrator" method="post">
          <button class="button secondary fulldmd-action-btn fulldmd-toggle-inactive" type="submit">
            Ouvrir Calibration FullDMD
          </button>
        </form>
        """


# === PINCABOS DMD CALIBRATOR TOGGLE START ===
def pincabos_dmd_calibrator_running():
    state_file = Path("/run/pincabos-dmd-calibrator.active")

    try:
        result = subprocess.run(
            ["/usr/bin/pgrep", "-af", "pincabos-dmd-calibrator|pincabos_dmd_calibrator|dmd-screen"],
            text=True,
            capture_output=True,
            timeout=3
        )
        process_running = result.returncode == 0 and bool(result.stdout.strip())
    except Exception:
        process_running = False

    return state_file.exists() or process_running

def pincabos_dmd_toggle_button():
    if pincabos_dmd_calibrator_running():
        return """
        <form action="/close-dmd-calibrator" method="post">
          <button class="button fulldmd-action-btn fulldmd-toggle-active" type="submit"
                  style="background:#ff7a00 !important;color:#160020 !important;border:1px solid #ffb000 !important;box-shadow:0 0 18px rgba(255,122,0,.9),0 0 28px rgba(255,176,0,.45) !important;">
            Fermer Calibration DMD
          </button>
        </form>
        """
    return """
        <form action="/launch-dmd-calibrator" method="post">
          <button class="button secondary fulldmd-action-btn fulldmd-toggle-inactive" type="submit">
            Ouvrir Calibration DMD
          </button>
        </form>
        """
# === PINCABOS DMD CALIBRATOR TOGGLE END ===

@dmd_bp.route("/close-fulldmd-calibrator", methods=["POST"])
def close_fulldmd_calibrator():
    import time
    import subprocess
    from pathlib import Path
    from datetime import datetime
    from flask import redirect, url_for

    live_log = Path("/opt/pincabos/logs/fulldmd-live.log")
    live_log.parent.mkdir(parents=True, exist_ok=True)

    try:
        with live_log.open("a") as f:
            f.write("\\n==================================================\\n")
            f.write(datetime.now().strftime("%F %T") + " - Fermeture calibration FullDMD demandée depuis WebApp\\n")
            f.write("==================================================\\n")
    except Exception:
        pass

    subprocess.run(
        ["/bin/bash", "--noprofile", "--norc", "-c",
         "pkill -f 'pincabos-fulldmd-calibrator|/fulldmd-screen' 2>/dev/null || true"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=8
    )

    try:
        FULLDMD_ACTIVE_STATE.unlink(missing_ok=True)
    except Exception:
        pass

    time.sleep(3)
    return redirect(url_for("dmd.fulldmd_page"))
# === PINCABOS FULLDMD TOGGLE BUTTON END ===


@dmd_bp.route("/launch-fulldmd-calibrator", methods=["POST"])
def launch_fulldmd_calibrator():
    import time
    from datetime import datetime
    subprocess.Popen(
        ["/usr/bin/sudo", str(pco_script("launch_fulldmd_calibrator"))],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        FULLDMD_ACTIVE_STATE.write_text(datetime.now().isoformat(timespec="seconds") + "\n", encoding="utf-8")
        FULLDMD_ACTIVE_STATE.chmod(0o666)
    except Exception:
        pass

    time.sleep(3)
    return redirect(url_for("dmd.fulldmd_page"))


@dmd_bp.route("/fulldmd-screen")
def fulldmd_screen():
    cal = load_fulldmd_calibration()

    body = """
<!doctype html>
<html>
<head>
  <title>PinCabOS FullDMD Calibration</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">

  <style>
    html, body {
      margin: 0;
      padding: 0;
      overflow: hidden;
      width: 100%;
      height: 100%;
      background: #000;
      font-family: Arial, sans-serif;
      color: white;
    }

    #stage {
      position: relative;
      width: 100vw;
      height: 100vh;
      overflow: hidden;
      background:
        linear-gradient(45deg, rgba(255,255,255,0.06) 25%, transparent 25%),
        linear-gradient(-45deg, rgba(255,255,255,0.06) 25%, transparent 25%),
        linear-gradient(45deg, transparent 75%, rgba(255,255,255,0.06) 75%),
        linear-gradient(-45deg, transparent 75%, rgba(255,255,255,0.06) 75%);
      background-size: 40px 40px;
      background-position: 0 0, 0 20px, 20px -20px, -20px 0px;
    }

    #stage::before {
      content: "";
      position: absolute;
      inset: 0;
      background-image: url('/static/pincabos-logo.png');
      background-repeat: no-repeat;
      background-position: center center;
      background-size: min(60vw, 700px) auto;
      opacity: 0.10;
      pointer-events: none;
      z-index: 1;
    }

    #rect {
      position: absolute;
      left: __X__px;
      top: __Y__px;
      width: __W__px;
      height: __H__px;
      min-width: 360px;
      min-height: 250px;
      border: 4px solid #00eaff;
      background: rgba(0,234,255,0.14);
      box-shadow: 0 0 28px rgba(0,234,255,0.95);
      cursor: move;
      box-sizing: border-box;
      z-index: 200;
      overflow: visible;
    }

    #edge-label {
      position: absolute;
      left: 10px;
      top: 10px;
      color: #fff;
      background: rgba(0,0,0,0.65);
      padding: 5px 8px;
      border-radius: 8px;
      font-weight: bold;
      border: 1px solid #00eaff;
      z-index: 220;
      pointer-events: none;
    }

    #inside-panel {
      position: absolute;
      left: 50%;
      top: 50%;
      transform: translate(-50%, -50%);
      min-width: 320px;
      max-width: 92%;
      background: rgba(10,0,20,0.88);
      border: 1px solid var(--pco-appearance-card-border, #ff7a00);
      border-radius: 14px;
      padding: 12px;
      box-shadow: 0 0 25px rgba(255,122,0,0.55);
      text-align: center;
      z-index: 230;
      cursor: default;
    }

    #title {
      font-weight: bold;
      color: var(--pco-appearance-accent, #ffb000);
      margin-bottom: 6px;
      text-shadow: 0 0 12px rgba(255,122,0,0.7);
    }

    #hint {
      font-size: 12px;
      color: var(--pco-appearance-muted-text, #d8b8ff);
      margin-bottom: 8px;
    }

    input {
      width: 70px;
      padding: 5px;
      margin: 3px;
      background: #111;
      color: #fff;
      border: 1px solid var(--pco-appearance-card-border, #ff7a00);
      border-radius: 6px;
      text-align: center;
    }

    button {
      background: var(--pco-appearance-button-bg, #ff7a00);
      color: var(--pco-appearance-button-text, #160020);
      border: none;
      padding: 8px 10px;
      margin: 4px 2px;
      border-radius: 8px;
      font-weight: bold;
      cursor: pointer;
    }

    button.secondary {
      background: #5f2a91;
      color: white;
      border: 1px solid var(--pco-appearance-card-border, #ff7a00);
    }

    #status {
      color: #00ff99;
      font-weight: bold;
      margin-top: 6px;
      min-height: 18px;
      font-size: 13px;
    }

    #handle {
      position:absolute;
      right:-12px;
      bottom:-12px;
      width:26px;
      height:26px;
      background:#ff7a00;
      border:3px solid white;
      border-radius:50%;
      cursor:nwse-resize;
      z-index: 250;
      box-shadow: 0 0 15px rgba(255,122,0,0.9);
    }
  </style>
<link rel="icon" type="image/png" href="/static/branding/favicon.png?v=branding">
</head>

<body>
  <div id="stage">
    <div id="rect">
      <div id="edge-label">FullDMD Visible Area</div>

<div class="card">
  <h2>Calibration DMD global</h2>
  <p>Cette section calibre la position globale des DMD. Elle écrit les valeurs dans :</p>
  <p><code>/opt/pincabos/config/dmd-calibration.json</code></p>
  <p><code>/home/pinball/.config/vpinfe/vpinfe.ini</code></p>
  <p><code>/home/pinball/.local/share/VPinballX/10.8/VPinballX.ini</code></p>
  <p>Fenêtre plus petite que FullDMD, par défaut sur écran ID <strong>2</strong>.</p>
  <form action="/launch-dmd-calibrator" method="post" style="display:inline-block">
    <button class="button" type="submit">Ouvrir calibration DMD</button>
  </form>
  <form action="/close-dmd-calibrator" method="post" style="display:inline-block;margin-left:8px">
    <button class="button secondary" type="submit">Fermer DMD</button>
  </form>
</div>


      <div id="inside-panel">
        <div id="title">PinCabOS FullDMD Calibration</div>
        <div id="hint">Déplace la zone bleue. Étire avec le point orange.</div>

        <div>
          X <input id="x" type="number" value="__X__">
          Y <input id="y" type="number" value="__Y__">
        </div>

        <div>
          W <input id="w" type="number" value="__W__">
          H <input id="h" type="number" value="__H__">
        </div>

        <div>
          Screen ID <input id="screen_id" type="text" value="__SCREEN_ID__">
        </div>

        <button onclick="saveCal()">Sauvegarder</button>
        <button class="secondary" onclick="centerRect()">Centrer</button>
        <button class="secondary" onclick="fitRect()">Plein écran</button>
        <button class="secondary" onclick="window.close()">Fermer</button>

        <div id="status"></div>
      </div>

      <div id="handle"></div>
    </div>
  </div>

<script>
const stage = document.getElementById('stage');
const rect = document.getElementById('rect');
const handle = document.getElementById('handle');
const panel = document.getElementById('inside-panel');

let dragging = false;
let resizing = false;
let startX = 0;
let startY = 0;
let startLeft = 0;
let startTop = 0;
let startW = 0;
let startH = 0;

function num(id) {
  return parseInt(document.getElementById(id).value || '0', 10);
}

function syncInputs() {
  document.getElementById('x').value = parseInt(rect.style.left, 10) || 0;
  document.getElementById('y').value = parseInt(rect.style.top, 10) || 0;
  document.getElementById('w').value = parseInt(rect.style.width, 10) || 0;
  document.getElementById('h').value = parseInt(rect.style.height, 10) || 0;
}

function applyInputs() {
  rect.style.left = num('x') + 'px';
  rect.style.top = num('y') + 'px';
  rect.style.width = num('w') + 'px';
  rect.style.height = num('h') + 'px';
}

['x','y','w','h'].forEach(id => {
  document.getElementById(id).addEventListener('input', applyInputs);
});

panel.addEventListener('mousedown', e => {
  e.stopPropagation();
});

rect.addEventListener('mousedown', e => {
  if (e.target === handle) return;
  if (panel.contains(e.target)) return;

  dragging = true;
  startX = e.clientX;
  startY = e.clientY;
  startLeft = parseInt(rect.style.left, 10) || 0;
  startTop = parseInt(rect.style.top, 10) || 0;
  e.preventDefault();
});

handle.addEventListener('mousedown', e => {
  resizing = true;
  startX = e.clientX;
  startY = e.clientY;
  startW = parseInt(rect.style.width, 10) || 0;
  startH = parseInt(rect.style.height, 10) || 0;
  e.preventDefault();
  e.stopPropagation();
});

document.addEventListener('mousemove', e => {
  if (dragging) {
    let left = startLeft + (e.clientX - startX);
    let top = startTop + (e.clientY - startY);

    left = Math.max(0, Math.min(left, stage.clientWidth - rect.offsetWidth));
    top = Math.max(0, Math.min(top, stage.clientHeight - rect.offsetHeight));

    rect.style.left = left + 'px';
    rect.style.top = top + 'px';
    syncInputs();
  }

  if (resizing) {
    let w = startW + (e.clientX - startX);
    let h = startH + (e.clientY - startY);

    w = Math.max(360, Math.min(w, stage.clientWidth - (parseInt(rect.style.left, 10) || 0)));
    h = Math.max(250, Math.min(h, stage.clientHeight - (parseInt(rect.style.top, 10) || 0)));

    rect.style.width = w + 'px';
    rect.style.height = h + 'px';
    syncInputs();
  }
});

document.addEventListener('mouseup', () => {
  dragging = false;
  resizing = false;
});

function centerRect() {
  const w = parseInt(rect.style.width, 10) || 800;
  const h = parseInt(rect.style.height, 10) || 300;

  rect.style.left = Math.max(0, Math.floor((stage.clientWidth - w) / 2)) + 'px';
  rect.style.top = Math.max(0, Math.floor((stage.clientHeight - h) / 2)) + 'px';

  syncInputs();
}

function fitRect() {
  rect.style.left = '0px';
  rect.style.top = '0px';
  rect.style.width = stage.clientWidth + 'px';
  rect.style.height = stage.clientHeight + 'px';

  syncInputs();
}

async function saveCal() {
  const payload = {
    screen_id: document.getElementById('screen_id').value,
    x: num('x'),
    y: num('y'),
    width: num('w'),
    height: num('h')
  };

  const r = await fetch('/api/fulldmd/save', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });

  const data = await r.json();

  document.getElementById('status').textContent =
    data.message || 'Calibration FullDMD sauvegardée.';
}
</script>
</body>
</html>
"""

    body = body.replace("__SCREEN_ID__", esc(cal.get("screen_id", "")))
    body = body.replace("__X__", esc(cal.get("x", 0)))
    body = body.replace("__Y__", esc(cal.get("y", 0)))
    body = body.replace("__W__", esc(cal.get("width", 800)))
    body = body.replace("__H__", esc(cal.get("height", 300)))

    return body


# === PINCABOS DMD CALIBRATION ROUTES START ===

@dmd_bp.route("/dmd/apply", methods=["POST"])
def pincabos_apply_dmd_calibration():
    try:
        subprocess.run(["/usr/bin/sudo", str(pco_script("sync_dmd_calibrations"))], timeout=8, check=False)
    except Exception:
        pass
    return redirect("/fulldmd")

@dmd_bp.route("/dmd-screen")
def pincabos_dmd_screen():
    body = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>PinCabOS DMD Calibration</title>
<style>
html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#050505;color:#ffb000;font-family:Arial,sans-serif;cursor:default;}
#stage{position:relative;width:100vw;height:100vh;background:
  linear-gradient(90deg,rgba(255,176,0,.10) 1px,transparent 1px),
  linear-gradient(rgba(255,176,0,.10) 1px,transparent 1px);
  background-size:40px 40px;
}
#rect{position:absolute;border:3px solid #ffb000;background:rgba(255,176,0,.18);box-shadow:0 0 18px rgba(255,176,0,.7);box-sizing:border-box;}
#rect:before{content:"DMD";position:absolute;left:8px;top:6px;color:#fff;font-weight:bold;text-shadow:0 0 8px #000;}
#handle{position:absolute;right:-8px;bottom:-8px;width:18px;height:18px;background:#ffb000;border:2px solid #fff;box-sizing:border-box;cursor:nwse-resize;}
#panel{position:absolute;left:12px;top:12px;background:rgba(0,0,0,.72);border:1px solid rgba(255,176,0,.45);padding:10px;border-radius:10px;font-size:13px;z-index:10;}
button{background:#ff7a00;color:#fff;border:1px solid #ffb000;border-radius:8px;padding:7px 10px;margin:3px;cursor:pointer;}
button.secondary{background:#222;}
code{color:#fff;}
</style>
</head>
<body>
<div id="stage">
  <div id="panel">
    <strong>PinCabOS DMD Calibration</strong><br>
    Fenêtre fixe fullscreen sur la surface FullDMD.<br>
    Déplace seulement le carré DMD.<br>
    <code id="info"></code><br>
    <button onclick="save()">Sauvegarder DMD</button>
    <button class="secondary" onclick="centerRect()">Centrer</button>
    <button class="secondary" onclick="fitTop()">Top DMD</button>
    <button class="secondary" onclick="window.close()">Fermer</button>
  </div>
  <div id="rect"><div id="handle"></div></div>
</div>

<script>
const qs = new URLSearchParams(location.search);

function parseNums(name, fallback) {
  const raw = qs.get(name) || "";
  const parts = raw.split(",").map(v => parseInt(v || "0", 10));
  if (parts.length >= fallback.length && parts.every(v => !Number.isNaN(v))) return parts;
  return fallback;
}

const override = parseNums("override", [80,40,512,128]);
const win = parseNums("window", [0,0,window.innerWidth,window.innerHeight]);
const screenId = qs.get("screen_id") || "0";

let x = override[0], y = override[1], w = override[2], h = override[3];

const rect = document.getElementById("rect");
const info = document.getElementById("info");

function clamp() {
  if (w < 64) w = 64;
  if (h < 32) h = 32;
  if (x < 0) x = 0;
  if (y < 0) y = 0;
  if (x + w > window.innerWidth) x = Math.max(0, window.innerWidth - w);
  if (y + h > window.innerHeight) y = Math.max(0, window.innerHeight - h);
}

function draw() {
  clamp();
  rect.style.left = x + "px";
  rect.style.top = y + "px";
  rect.style.width = w + "px";
  rect.style.height = h + "px";
  info.textContent =
    "local=" + x + "," + y + "," + w + "," + h +
    " | réel=" + (win[0]+x) + "," + (win[1]+y) + "," + w + "," + h +
    " | screen=" + screenId;
}

let mode = null, sx = 0, sy = 0, ox = 0, oy = 0, ow = 0, oh = 0;

rect.addEventListener("pointerdown", e => {
  if (e.target.id === "handle") return;
  mode = "move";
  sx = e.clientX; sy = e.clientY; ox = x; oy = y;
  rect.setPointerCapture(e.pointerId);
});

document.getElementById("handle").addEventListener("pointerdown", e => {
  mode = "resize";
  sx = e.clientX; sy = e.clientY; ow = w; oh = h;
  rect.setPointerCapture(e.pointerId);
  e.stopPropagation();
});

window.addEventListener("pointermove", e => {
  if (!mode) return;
  if (mode === "move") {
    x = ox + (e.clientX - sx);
    y = oy + (e.clientY - sy);
  } else if (mode === "resize") {
    w = ow + (e.clientX - sx);
    h = oh + (e.clientY - sy);
  }
  draw();
});

window.addEventListener("pointerup", () => { mode = null; });

window.addEventListener("keydown", e => {
  const step = e.shiftKey ? 10 : 1;
  if (e.key === "ArrowLeft") x -= step;
  if (e.key === "ArrowRight") x += step;
  if (e.key === "ArrowUp") y -= step;
  if (e.key === "ArrowDown") y += step;
  if (e.key === "+") { w += step; h += step; }
  if (e.key === "-") { w -= step; h -= step; }
  draw();
});

function centerRect() {
  x = Math.round((window.innerWidth - w) / 2);
  y = Math.round((window.innerHeight - h) / 2);
  draw();
}

function fitTop() {
  x = 0;
  y = 0;
  w = window.innerWidth;
  h = Math.max(80, Math.round(window.innerHeight * 0.18));
  draw();
}

async function save() {
  draw();
  const payload = {
    screen_id: screenId,
    x: x,
    y: y,
    width: w,
    height: h,
    window_x: win[0],
    window_y: win[1],
    window_width: win[2],
    window_height: win[3]
  };

  const r = await fetch("/api/dmd/save", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload)
  });

  const j = await r.json();
  alert(j.ok ? ("DMD sauvegardé. Réel: " + j.real_geometry) : ("Erreur: " + (j.error || "unknown")));
}

draw();
</script>
</body>
</html>
"""
    return body

@dmd_bp.route("/api/dmd/save", methods=["POST"])
def pincabos_api_dmd_save():
    try:
        import json
        import subprocess
        from pathlib import Path
        from datetime import datetime

        data = request.get_json(force=True, silent=True) or {}

        def as_int(name, default=0):
            try:
                return int(data.get(name, default))
            except Exception:
                return int(default)

        screen_id = str(data.get("screen_id", ""))
        local_x = as_int("x", 0)
        local_y = as_int("y", 0)
        width = as_int("width", 512)
        height = as_int("height", 128)

        window_x = as_int("window_x", 0)
        window_y = as_int("window_y", 0)
        window_width = as_int("window_width", 0)
        window_height = as_int("window_height", 0)

        real_x = window_x + local_x
        real_y = window_y + local_y

        clean = {
            "screen_id": screen_id,
            "x": real_x,
            "y": real_y,
            "width": width,
            "height": height,
            "geometry": f"{width}x{height}+{real_x}+{real_y}",
            "real": {
                "x": real_x,
                "y": real_y,
                "width": width,
                "height": height,
                "geometry": f"{width}x{height}+{real_x}+{real_y}",
            },
            "local": {
                "x": local_x,
                "y": local_y,
                "width": width,
                "height": height,
                "geometry": f"{width}x{height}+{local_x}+{local_y}",
            },
            "window": {
                "x": window_x,
                "y": window_y,
                "width": window_width,
                "height": window_height,
                "geometry": f"{window_width}x{window_height}+{window_x}+{window_y}",
            },
            "note": "PinCabOS global DMD position calibration. x/y top-level are real desktop coordinates.",
            "_pincabos_meta": {
                "modified_by": "PinCabOS",
                "function": "DMD Calibration",
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "formula": "real_x = window_x + local_x; real_y = window_y + local_y",
            },
        }

        cfg = Path("/opt/pincabos/config/dmd-calibration.json")
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text(json.dumps(clean, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        log = Path("/opt/pincabos/logs/dmd-calibration.log")
        with log.open("a", encoding="utf-8") as f:
            f.write(
                datetime.now().strftime("%F %T")
                + f" - DMD save local={local_x},{local_y},{width},{height} "
                + f"window={window_x},{window_y},{window_width},{window_height} "
                + f"real={real_x},{real_y},{width},{height}\n"
            )

        subprocess.run(
            ["/usr/bin/sudo", str(pco_script("sync_dmd_calibrations"))],
            timeout=8,
            check=False,
        )

        return jsonify({
            "ok": True,
            "message": "DMD sauvegardé et synchronisé.",
            "local_geometry": f"{width}x{height}+{local_x}+{local_y}",
            "window_geometry": f"{window_width}x{window_height}+{window_x}+{window_y}",
            "real_geometry": f"{width}x{height}+{real_x}+{real_y}",
        })

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@dmd_bp.route("/launch-dmd-calibrator", methods=["POST"])
def pincabos_launch_dmd_calibrator():
    try:
        Path("/run/pincabos-dmd-calibrator.active").write_text(
            datetime.now().isoformat(timespec="seconds") + "\n"
        )
    except Exception:
        pass

    subprocess.Popen(["/usr/bin/sudo", str(pco_script("launch_dmd_calibrator"))])
    return redirect("/fulldmd?dmd_calibration=open&ts=" + datetime.now().strftime("%Y%m%d%H%M%S"))


@dmd_bp.route("/close-dmd-calibrator", methods=["POST"])
def pincabos_close_dmd_calibrator():
    try:
        Path("/run/pincabos-dmd-calibrator.active").unlink(missing_ok=True)
    except Exception:
        pass

    try:
        subprocess.run(
            ["/usr/bin/sudo", str(pco_script("close_dmd_calibrator"))],
            timeout=5,
            check=False
        )
    except Exception:
        pass

    try:
        Path("/run/pincabos-dmd-calibrator.active").unlink(missing_ok=True)
    except Exception:
        pass

    return redirect("/fulldmd?dmd_calibration=closed&ts=" + datetime.now().strftime("%Y%m%d%H%M%S"))


@dmd_bp.route("/fulldmd-log-page-disabled")
def fulldmd_log_page():
    parts = []

    parts.append("===== Log temps réel désactivé FullDMD =====")
    live_log = Path("/opt/pincabos/logs/fulldmd-live.log")
    try:
        if live_log.exists():
            parts.append(live_log.read_text(errors="replace")[-12000:])
        else:
            parts.append("Aucun log live FullDMD trouvé.")
    except Exception as e:
        parts.append(f"Erreur lecture live log: {e}")

    parts.append("")
    parts.append("===== Calibration sauvegardée =====")
    cfg = Path("/opt/pincabos/config/fulldmd-calibration.json")
    try:
        if cfg.exists():
            parts.append(cfg.read_text(errors="replace"))
        else:
            parts.append("Aucune calibration FullDMD sauvegardée.")
    except Exception as e:
        parts.append(f"Erreur lecture calibration: {e}")

    parts.append("")
    parts.append("===== VPinFE Displays =====")
    try:
        ini = pincabos_vpinfe_ini_path()
        lines = ini.read_text(errors="replace").splitlines()
        in_displays = False
        for line in lines:
            s = line.strip()
            if s.lower() == "[displays]":
                in_displays = True
                parts.append(line)
                continue
            if in_displays and s.startswith("[") and s.endswith("]"):
                break
            if in_displays and any(k in line.lower() for k in ["dmdscreenid", "dmdwindowoverride", "bgscreenid", "tablescreenid", "cabmode"]):
                parts.append(line)
    except Exception as e:
        parts.append(f"Erreur lecture vpinfe.ini: {e}")

    parts.append("")
    parts.append("===== VPX PinCabOS.FullDMD =====")
    try:
        ini = pincabos_vpx_ini_path()
        lines = ini.read_text(errors="replace").splitlines()
        in_section = False
        for line in lines:
            s = line.strip()
            if s.lower() == "[pincabos.fulldmd]":
                in_section = True
                parts.append(line)
                continue
            if in_section and s.startswith("[") and s.endswith("]"):
                break
            if in_section:
                parts.append(line)
    except Exception as e:
        parts.append(f"Erreur lecture VPinballX.ini: {e}")

    parts.append("")
    parts.append("===== Process calibration =====")
    try:
        parts.append(run_cmd(["bash", "--noprofile", "--norc", "-c", "ps aux | grep -Ei 'pincabos-fulldmd-calibrator|fulldmd-screen' | grep -v grep || true"], timeout=5))
    except Exception as e:
        parts.append(f"Erreur process check: {e}")

    log_text = esc("\n".join(parts))

    return f"""<!doctype html>
<html>
<head>
  <meta http-equiv="refresh" content="1">
  <style>
    html, body {{
      margin: 0;
      padding: 0;
      background: var(--pco-appearance-input-bg, #050007);
      color: var(--pco-appearance-input-text, #eee);
      font-family: monospace;
      font-size: 13px;
    }}
    pre {{
      white-space: pre-wrap;
      margin: 0;
      padding: 15px;
    }}
    .top {{
      color: var(--pco-appearance-accent, #ffb000);
      padding: 8px 15px;
      border-bottom: 1px solid #5f2a91;
      font-family: Arial, sans-serif;
    }}
  </style>
<link rel="icon" type="image/png" href="/static/branding/favicon.png?v=branding">
</head>
<body>
  <div class="top">Dernier rafraîchissement automatique</div>
  <pre>{log_text}</pre>
</body>
</html>"""


# PINCABOS_FULLDMD_APPLY_ACTIVE_V1
# Applique le JSON FullDMD courant aux INI actifs, puis redémarre VPinFE.
@dmd_bp.route("/fulldmd/apply", methods=["POST"])
def pincabos_fulldmd_apply_active():
    import subprocess
    from datetime import datetime
    from flask import redirect

    try:
        data = load_fulldmd_calibration()

        screen_id = str(data.get("screen_id", "")).strip()
        if not screen_id.isdigit():
            return page("FullDMD", """
<div class="card">
  <h2>Application FullDMD refusée</h2>
  <p class="bad">Le Screen ID FullDMD doit être numérique.</p>
  <p><a class="button" href="/fulldmd">Retour</a></p>
</div>
"""), 400

        save_fulldmd_to_configs(data)

        result = subprocess.run(
            [
                "/usr/bin/sudo",
                "-n",
                "/usr/bin/systemctl",
                "restart",
                "pincabos-vpinfe.service",
            ],
            capture_output=True,
            text=True,
            timeout=35,
        )

        if result.returncode != 0:
            detail = (result.stdout + "\n" + result.stderr).strip()

            return page("FullDMD", f"""
<div class="card">
  <h2>INI sauvegardés, mais VPinFE n'a pas redémarré</h2>
  <pre>{esc(detail or "Aucun détail retourné.")}</pre>
  <p><a class="button" href="/fulldmd">Retour</a></p>
</div>
"""), 500

        return redirect(
            "/fulldmd?full_apply=ok&ts="
            + datetime.now().strftime("%Y%m%d%H%M%S")
        )

    except Exception as exc:
        return page("FullDMD", f"""
<div class="card">
  <h2>Application FullDMD échouée</h2>
  <pre>{esc(type(exc).__name__ + ": " + str(exc))}</pre>
  <p><a class="button" href="/fulldmd">Retour</a></p>
</div>
"""), 500


def register(app, page_fn):
    """Enregistre les pages DMD / FullDMD sur l'application."""
    global page
    page = page_fn
    app.register_blueprint(dmd_bp)
