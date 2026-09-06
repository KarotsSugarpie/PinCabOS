"""Pages GPU / Écrans / fonds d'écran de la WebApp PinCabOS (/gpu, /restart-vpinfe, /auto-screens).

Code déplacé tel quel depuis app.py (PINCABOS_WEBAPP_MODULES_V1) ; les routes gardent
leurs chemins et leurs noms de fonction. `page()` (gabarit commun) est fourni par app.py
à l'enregistrement : `register(app, page)`.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

from flask import Blueprint, redirect, request, url_for

from pincabos_webapp_core import esc, pco_script, pincabos_vpx_ini_path, run_cmd

try:
    import pincabos_ini
except ImportError:   # hors /opt (tests, depot) : le module vit a cote des outils
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "tools"))
    import pincabos_ini

gpu_bp = Blueprint("gpu", __name__)

page = None  # gabarit HTML commun, posé par register()


def gpu_info_text():
    return run_cmd(["/usr/bin/sudo", str(pco_script("detect_gpu"))], timeout=15)


# PinCabOS GPU per-screen wallpapers
# Created by Karots Sugarpie
# Dependencies:
# - python3: /usr/bin/python3
# - optional wallpaper tools: feh, xwallpaper, nitrogen, gsettings
# Paths:
# - /opt/pincabos/media/wallpapers
# - /opt/pincabos/config/screens/wallpapers.json

PINCABOS_WALLPAPER_DIR = Path("/opt/pincabos/media/wallpapers")
PINCABOS_WALLPAPER_CFG = Path("/opt/pincabos/config/screens/wallpapers.json")

def pco_wallpaper_role_label(role):
    return {
        "playfield": "Playfield",
        "backglass": "Backglass",
        "fulldmd": "FullDMD",
    }.get(str(role or ""), str(role or ""))

def pco_wallpaper_role_icon(role):
    return {
        "playfield": "🎮",
        "backglass": "🖼️",
        "fulldmd": "📺",
    }.get(str(role or ""), "🖼️")

def pco_wallpaper_load_cfg():
    try:
        if PINCABOS_WALLPAPER_CFG.exists():
            data = json.loads(PINCABOS_WALLPAPER_CFG.read_text(errors="replace") or "{}")
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {"roles": {}}

def pco_wallpaper_save_cfg(data):
    PINCABOS_WALLPAPER_CFG.parent.mkdir(parents=True, exist_ok=True)
    data["updated_by"] = "PinCabOS WebApp GPU wallpapers"
    data["updated_at"] = datetime.now().isoformat(timespec="seconds")
    PINCABOS_WALLPAPER_CFG.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

def pco_wallpaper_safe_ext(filename):
    ext = Path(str(filename or "")).suffix.lower()
    if ext not in [".png", ".jpg", ".jpeg", ".webp", ".bmp"]:
        return ""
    return ext

def pco_wallpaper_public_url(path):
    try:
        path = Path(path).resolve()
        base = PINCABOS_WALLPAPER_DIR.resolve()
        if path == base or base not in path.parents:
            return ""
        return "/gpu/wallpaper/file/" + urllib.parse.quote(path.name)
    except Exception:
        return ""

@gpu_bp.route("/gpu/wallpaper/file/<path:filename>")
def gpu_wallpaper_file(filename):
    from flask import send_from_directory
    safe = Path(filename).name
    return send_from_directory(str(PINCABOS_WALLPAPER_DIR), safe)

def pco_wallpaper_apply_image(role, path):
    """
    Applique les trois wallpapers simultanément,
    un fichier différent par écran Xinerama.
    """
    import subprocess

    role = str(role or "").strip().lower()
    path = str(path or "").strip()

    if role not in ("playfield", "backglass", "fulldmd"):
        return False, "NOGO: rôle wallpaper invalide."

    if not path:
        return False, "NOGO: chemin wallpaper vide."

    helper = '/opt/pincabos/bin/pincabos-wallpaper-per-screen.py'

    try:
        result = subprocess.run(
            [
                helper,
                "--trigger-role",
                role,
                "--trigger-image",
                path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=20,
            check=False,
        )
    except Exception as error:
        return False, (
            "NOGO: exécution du helper wallpaper impossible : "
            + str(error)
        )

    output = (result.stdout or "").strip()

    if result.returncode == 0:
        return True, output or (
            "GO: wallpapers appliqués séparément."
        )

    return False, output or (
        "NOGO: application des wallpapers échouée."
    )


def pco_gpu_wallpaper_section_html():
    cfg = pco_wallpaper_load_cfg()
    roles_cfg = cfg.get("roles", {}) if isinstance(cfg.get("roles", {}), dict) else {}

    try:
        screen_roles = pincabos_load_screen_roles()
    except Exception:
        screen_roles = {}

    try:
        wallpaper_screens, _ = pincabos_parse_xrandr_screens()
    except Exception:
        wallpaper_screens = []

    cards = ""
    for role in ["playfield", "backglass", "fulldmd"]:
        label = pco_wallpaper_role_label(role)
        icon = pco_wallpaper_role_icon(role)
        data = roles_cfg.get(role, {}) if isinstance(roles_cfg.get(role, {}), dict) else {}
        img_path = data.get("path", "")
        img_url = pco_wallpaper_public_url(img_path) if img_path else ""
        status = data.get("last_status", "Aucun wallpaper choisi.")
        output = ""

        try:
            selected = screen_roles.get(role)

            if isinstance(selected, dict):
                output = str(
                    selected.get("output")
                    or selected.get("name")
                    or ""
                )

                selected_id = str(
                    selected.get("id")
                    if selected.get("id") is not None
                    else ""
                )
            else:
                selected_id = str(
                    selected
                    if selected is not None
                    else ""
                )

            if not output:
                for screen in wallpaper_screens:
                    screen_id = str(
                        screen.get("id")
                        if screen.get("id") is not None
                        else ""
                    )

                    screen_name = str(
                        screen.get("name")
                        or screen.get("output")
                        or ""
                    )

                    if (
                        screen_id == selected_id
                        or screen_name == selected_id
                    ):
                        output = screen_name
                        break
        except Exception:
            output = ""

        preview = (
            '<img class="pco-wallpaper-preview-img" src="' + esc(img_url) + '?v=' + esc(str(time.time())) + '" alt="' + esc(label) + '">'
            if img_url else
            '<div class="pco-wallpaper-empty">Aucun aperçu</div>'
        )

        cards += f"""
        <div class="card pco-wallpaper-card">
          <h3>{icon} Wallpaper {esc(label)}</h3>
          <p><small>Écran assigné : <code>{esc(output or "non assigné")}</code></small></p>
          <div class="pco-wallpaper-preview">{preview}</div>

          <form action="/gpu/wallpaper/select" method="post" enctype="multipart/form-data" class="pco-wallpaper-form">
            <input type="hidden" name="role" value="{esc(role)}">
            <label>Image</label>
            <input type="file" name="wallpaper" accept=".png,.jpg,.jpeg,.webp,.bmp,image/*" required>
            <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:10px;">
              <button type="submit">Parcourir / Sauvegarder</button>
            </div>
          </form>

          <form action="/gpu/wallpaper/apply" method="post" class="pco-wallpaper-form">
            <input type="hidden" name="role" value="{esc(role)}">
            <button type="submit" class="secondary">Appliquer {esc(label)}</button>
          </form>

          <p><small>{esc(status)}</small></p>
          <p><small>Fichier : <code>{esc(img_path or "-")}</code></small></p>
        </div>
        """

    return f"""
    <style>
      .pco-wallpaper-grid {{
        display:grid;
        grid-template-columns:repeat(auto-fit,minmax(260px,1fr));
        gap:16px;
      }}
      .pco-wallpaper-card input[type=file] {{
        width:100%;
        box-sizing:border-box;
        margin-top:6px;
      }}
      .pco-wallpaper-preview {{
        min-height:150px;
        border:1px solid rgba(255,176,0,.35);
        border-radius:14px;
        background:rgba(0,0,0,.35);
        display:flex;
        align-items:center;
        justify-content:center;
        overflow:hidden;
        margin:12px 0;
      }}
      .pco-wallpaper-preview-img {{
        width:100%;
        height:180px;
        object-fit:cover;
        display:block;
      }}
      .pco-wallpaper-empty {{
        opacity:.75;
        color:#ffb000;
        font-weight:800;
      }}
      .pco-wallpaper-form {{
        margin:10px 0;
      }}
    </style>

    <div class="card">
      <h2>Wallpapers par écran</h2>
      <p>Choisis une image pour chaque écran. Chaque carte garde son aperçu et son bouton Appliquer.</p>
      <div class="pco-wallpaper-grid">
        {cards}
      </div>
    </div>
    """

@gpu_bp.route("/gpu/wallpaper/select", methods=["POST"])
def gpu_wallpaper_select():
    role = request.form.get("role", "").strip().lower()
    if role not in ("playfield", "backglass", "fulldmd"):
        return "Rôle wallpaper invalide.", 400

    f = request.files.get("wallpaper")
    if not f or not f.filename:
        return redirect(url_for("gpu_page", gpu_action="wallpaper", gpu_cls="bad", gpu_title="Aucune image sélectionnée."), code=303)

    ext = pco_wallpaper_safe_ext(f.filename)
    if not ext:
        return redirect(url_for("gpu_page", gpu_action="wallpaper", gpu_cls="bad", gpu_title="Format image non supporté."), code=303)

    PINCABOS_WALLPAPER_DIR.mkdir(parents=True, exist_ok=True)
    dst = PINCABOS_WALLPAPER_DIR / (role + ext)

    # Nettoyer anciennes extensions du même rôle.
    for old in PINCABOS_WALLPAPER_DIR.glob(role + ".*"):
        try:
            old.unlink()
        except Exception:
            pass

    f.save(str(dst))
    try:
        dst.chmod(0o664)
    except Exception:
        pass

    cfg = pco_wallpaper_load_cfg()
    roles = cfg.get("roles", {}) if isinstance(cfg.get("roles", {}), dict) else {}
    roles[role] = {
        "path": str(dst),
        "original_name": f.filename,
        "last_status": "Image sauvegardée. Clique Appliquer pour l’envoyer au bureau.",
        "selected_at": datetime.now().isoformat(timespec="seconds"),
    }
    cfg["roles"] = roles
    pco_wallpaper_save_cfg(cfg)

    return redirect(url_for("gpu_page", gpu_action="wallpaper", gpu_cls="ok", gpu_title="Wallpaper " + pco_wallpaper_role_label(role) + " sauvegardé."), code=303)

@gpu_bp.route("/gpu/wallpaper/apply", methods=["POST"])
def gpu_wallpaper_apply():
    role = request.form.get("role", "").strip().lower()
    if role not in ("playfield", "backglass", "fulldmd"):
        return "Rôle wallpaper invalide.", 400

    cfg = pco_wallpaper_load_cfg()
    roles = cfg.get("roles", {}) if isinstance(cfg.get("roles", {}), dict) else {}
    item = roles.get(role, {}) if isinstance(roles.get(role, {}), dict) else {}
    path = item.get("path", "")

    ok, msg = pco_wallpaper_apply_image(role, path)

    item["last_status"] = msg
    item["applied_at"] = datetime.now().isoformat(timespec="seconds")
    roles[role] = item
    cfg["roles"] = roles
    pco_wallpaper_save_cfg(cfg)

    cls = "ok" if ok else "warn"
    return redirect(url_for("gpu_page", gpu_action="wallpaper", gpu_cls=cls, gpu_title=msg.splitlines()[0]), code=303)


@gpu_bp.route("/gpu")
def gpu_page():
    from pathlib import Path

    gpu_text = gpu_info_text()
    screens, raw = pincabos_parse_xrandr_screens()
    roles = pincabos_load_screen_roles()

    gpu_opts = {
        "cabinet_mode": True,
        "playfield_orientation": "landscape",
        "playfield_rotation": "0",
    }

    try:
        import json
        cfg_opts = Path("/opt/pincabos/config/screens/screens.json")
        if cfg_opts.exists():
            data_opts = json.loads(cfg_opts.read_text(errors="replace"))
            gpu_opts["cabinet_mode"] = bool(data_opts.get("cabinet_mode", True))
            gpu_opts["playfield_orientation"] = str(data_opts.get("playfield_orientation", "landscape")).lower()
            gpu_opts["playfield_rotation"] = str(data_opts.get("playfield_rotation", "0"))
    except Exception:
        pass

    if gpu_opts["playfield_orientation"] not in ("landscape", "portrait"):
        gpu_opts["playfield_orientation"] = "landscape"
    if gpu_opts["playfield_rotation"] not in ("0", "90", "180", "270"):
        gpu_opts["playfield_rotation"] = "0"

    cabmode_checked = "checked" if gpu_opts.get("cabinet_mode", True) else ""
    orientation_landscape_selected = "selected" if gpu_opts.get("playfield_orientation") == "landscape" else ""
    orientation_portrait_selected = "selected" if gpu_opts.get("playfield_orientation") == "portrait" else ""
    rotation_0_selected = "selected" if gpu_opts.get("playfield_rotation") == "0" else ""
    rotation_90_selected = "selected" if gpu_opts.get("playfield_rotation") == "90" else ""
    rotation_180_selected = "selected" if gpu_opts.get("playfield_rotation") == "180" else ""
    rotation_270_selected = "selected" if gpu_opts.get("playfield_rotation") == "270" else ""

    def pco_gpu_saved_mode(role_name):
        try:
            cfg_modes = Path("/opt/pincabos/config/screens/screens.json")
            if cfg_modes.exists():
                data_modes = json.loads(cfg_modes.read_text(errors="replace") or "{}")
                role_data = (data_modes.get("roles") or {}).get(role_name) or {}
                return str(role_data.get("mode") or ""), str(role_data.get("rate") or "")
        except Exception:
            pass
        return "", ""

    def pco_gpu_screen_name_from_selected(selected):
        selected = str(selected or "")
        for item in screens:
            if str(item.get("id")) == selected:
                return str(item.get("name") or item.get("output") or "")
            if str(item.get("name") or item.get("output") or "") == selected:
                return str(item.get("name") or item.get("output") or "")
        return ""

    def pco_gpu_modes_from_raw(selected):
        wanted = pco_gpu_screen_name_from_selected(selected)
        if not wanted:
            return []

        modes = []
        active = False

        try:
            for line in str(raw or "").splitlines():
                m = re.match(r"^([A-Za-z0-9_.:-]+)\s+connected\b.*$", line)
                if m:
                    active = (m.group(1) == wanted)
                    continue

                if not active:
                    continue

                mm = re.match(r"^\s+(\d+x\d+)\s+(.+)$", line)
                if not mm:
                    continue

                mode = mm.group(1)
                tail = mm.group(2)

                rates = []
                for r in re.findall(r"(\d+(?:\.\d+)?)\*?\+?", tail):
                    if r not in rates:
                        rates.append(r)

                if not rates:
                    rates = [""]

                modes.append({"mode": mode, "rates": rates})
        except Exception:
            return []

        return modes

    def pco_gpu_mode_select(role_name, selected):
        selected_mode, selected_rate = pco_gpu_saved_mode(role_name)
        modes = pco_gpu_modes_from_raw(selected)

        opts = ['<option value="">-- Auto / inchangé --</option>']

        for item in modes:
            mode = str(item.get("mode") or "")
            rates = item.get("rates") or [""]

            if not mode:
                continue

            for rate in rates:
                rate = str(rate or "").replace("*", "").replace("+", "")
                value = mode + (("@" + rate) if rate else "")
                label = mode + ((" " + rate + "Hz") if rate else "")
                sel = "selected" if mode == selected_mode and (not selected_rate or selected_rate == rate) else ""
                opts.append('<option value="' + esc(value) + '" ' + sel + '>' + esc(label) + '</option>')

        return (
            '<select name="' + esc(role_name) + '_mode" style="width:100%; padding:8px; margin:6px 0;">'
            + "\\n".join(opts) +
            '</select>'
        )


    def role_select(name, selected):
        html = f'<select name="{name}" style="width:95%; padding:8px; margin:6px 0;">'
        html += '<option value="">-- Aucun --</option>'

        for sc in screens:
            sel = (
                "selected"
                if str(selected)
                and str(selected) in (str(sc["name"]), str(sc["id"]))
                else ""
            )
            label = f'{sc["name"]} — {sc["width"]}x{sc["height"]}+{sc["x"]}+{sc["y"]}'
            if sc.get("is_primary"):
                label += " — primary X11"
            # PINCABOS_SCREEN_IDENTITY_V2 : le NOM du connecteur, pas le rang
            # xrandr, qui se decale des qu'une sortie change d'etat.
            html += f'<option value="{esc(sc["name"])}" {sel}>{esc(label)}</option>'

        html += "</select>"
        return html

    rows = ""
    for sc in screens:
        rows += f"""
<tr>
  <td><code>{esc(sc["id"])}</code></td>
  <td><strong>{esc(sc["name"])}</strong></td>
  <td>{esc(sc["width"])}x{esc(sc["height"])}</td>
  <td>{esc(sc["x"])},{esc(sc["y"])}</td>
  <td>{'oui' if sc.get("is_primary") else 'non'}</td>
</tr>
"""

    if not rows:
        rows = '<tr><td colspan="5" class="bad">Aucun écran détecté par xrandr. Vérifie que la session X11 est active.</td></tr>'

    screens_json = "{}"
    try:
        cfg = Path("/opt/pincabos/config/screens/screens.json")
        if cfg.exists():
            screens_json = cfg.read_text(errors="replace")
    except Exception as e:
        screens_json = f"Erreur lecture screens.json: {e}"

    gpu_status_rows = ""
    gpu_status_rows += (
        '<tr><td><strong>xrandr / X11</strong></td><td>'
        + ('<span class="ok">OK — ' + esc(str(len(screens))) + ' écran(s) détecté(s)</span>' if screens else '<span class="bad">Aucun écran détecté</span>')
        + '</td></tr>'
    )
    gpu_status_rows += (
        '<tr><td><strong>screens.json</strong></td><td>'
        + ('<span class="ok">présent / lisible</span>' if screens_json and screens_json.strip() not in ("{}", "") and not screens_json.startswith("Erreur") else '<span class="warn">vide ou absent</span>')
        + '</td></tr>'
    )
    role_count = len([v for v in roles.values() if str(v).strip()])
    gpu_status_rows += (
        '<tr><td><strong>Rôles assignés</strong></td><td>'
        + ('<span class="ok">' + esc(str(role_count)) + ' rôle(s) sauvegardé(s)</span>' if role_count else '<span class="warn">aucun rôle sauvegardé</span>')
        + '</td></tr>'
    )

    gpu_quick_tools = """
      <div style="display:flex; gap:10px; flex-wrap:wrap; margin-top:12px;">
        <form action="/auto-screens" method="post" style="display:inline;" onsubmit="return confirm('Lancer auto-détection écrans et mettre à jour screens.json ?');">
          <button class="button" type="submit">Auto-détecter écrans</button>
        </form>
        <a class="button secondary" href="/gpu">Rafraîchir Écrans / GPU</a>
      </div>
    """

    vpinfe_buttons = ""
    if "gpu_apply_vpinfe" in globals():
        vpinfe_buttons += """
      <form action="/gpu/apply-vpinfe" method="post" onsubmit="return confirm('Appliquer la configuration écran actuelle à VPinFE ?');">
        <button class="button secondary" type="submit" title="Dépannage : réécrit le vpinfe.ini depuis la configuration déjà enregistrée. Inutile en usage normal, le bouton « Appliquer assignation écrans » le fait déjà.">Re-synchroniser VPinFE (dépannage)</button>
      </form>
"""
    if "gpu_apply_vpx" in globals():
        vpinfe_buttons += """
      <form action="/gpu/apply-vpx" method="post" onsubmit="return confirm('Appliquer la configuration écran actuelle à VPX / VPinballX.ini ?');">
        <button class="button secondary" type="submit" title="Dépannage : réécrit le VPinballX.ini depuis la configuration déjà enregistrée. Inutile en usage normal.">Re-synchroniser VPX (dépannage)</button>
      </form>


"""

    wallpaper_html = pco_gpu_wallpaper_section_html()

    body = f"""
<div class="card" style="margin-top:0;">
  <h2>Écrans détectés</h2>

  <style>
    .pincabos-screen-table-wrap {{{{
      width: 100%;
      overflow-x: auto;
      margin-top: 10px;
    }}}}

    .pincabos-screen-table {{{{
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
      font-size: 0.95rem;
    }}}}

    .pincabos-screen-table th,
    .pincabos-screen-table td {{{{
      padding: 10px 12px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.12);
      vertical-align: middle;
      white-space: nowrap;
    }}}}

    .pincabos-screen-table th {{{{
      color: var(--pco-appearance-accent, #ffb000);
      text-align: left;
      font-weight: 700;
    }}}}

    .pincabos-screen-table th:nth-child(1),
    .pincabos-screen-table td:nth-child(1) {{{{
      width: 70px;
      text-align: center;
    }}}}

    .pincabos-screen-table th:nth-child(2),
    .pincabos-screen-table td:nth-child(2) {{{{
      width: 34%;
      text-align: left;
    }}}}

    .pincabos-screen-table th:nth-child(3),
    .pincabos-screen-table td:nth-child(3),
    .pincabos-screen-table th:nth-child(4),
    .pincabos-screen-table td:nth-child(4),
    .pincabos-screen-table th:nth-child(5),
    .pincabos-screen-table td:nth-child(5) {{{{
      text-align: center;
    }}}}

    .pincabos-screen-table code {{{{
      display: inline-block;
      min-width: 28px;
      text-align: center;
    }}}}
</style>

  <div class="pincabos-screen-table-wrap">
    <table class="pincabos-screen-table">
      <tr>
        <th>ID</th>
        <th>Nom xrandr</th>
        <th>Résolution</th>
        <th>Position X,Y</th>
        <th>Primary X11</th>
      </tr>
      {rows}
    </table>
  </div>
</div>

  <div class="card" style="margin-top:20px;">
    <h2>Statut rapide Écrans / GPU</h2>
    <div class="pincabos-screen-table-wrap">
      <table class="pincabos-screen-table">
        {gpu_status_rows}
      </table>
    </div>
    {gpu_quick_tools}
  </div>

<div class="grid">
  <div class="card pco-gpu-driver-card">
    <h2>GPU / Carte vidéo</h2>

    <p>
      Cette section affiche le modèle GPU, le driver actif et les informations utiles
      pour installer ou mettre à jour les pilotes NVIDIA, AMD ou Intel.
    </p>

    <form action="/restart-vpinfe" method="post" style="display:inline;">
      <button class="button secondary" type="submit">Redémarrer VPinFE</button>
    </form>

    <h3 style="margin-top:18px;">Détection GPU / driver</h3>
    <style>
      .pco-gpu-driver-card {{
        display: flex;
        flex-direction: column;
        min-height: 980px;
      }}
      .pco-gpu-driver-log {{
        flex: 1 1 auto;
        min-height: 760px;
        max-height: none;
        overflow: auto;
        resize: vertical;
        white-space: pre;
      }}
    </style>
<pre class="pco-gpu-driver-log" style="height:75vh !important; min-height:760px !important; max-height:none !important; overflow:auto !important; resize:vertical !important; white-space:pre !important;">{esc(gpu_text)}</pre>
  </div>

  <div class="card">
    <!-- PINCABOS_GPU_SCREENS_RENVOI_V1 : l'assignation des ecrans n'existe
         plus qu'a UN seul endroit. Cette page dupliquait la page Ecrans avec
         son propre chemin d'ecriture de screens.json : deux interfaces
         concurrentes pour la meme verite. -->
    <h2>Assignation écrans</h2>
    <p>L'assignation des rôles (Playfield, Backglass, FullDMD, Topper), les
    résolutions et l'application au système se font désormais sur une seule
    page&nbsp;:</p>
    <p><a class="button" href="/screen">Ouvrir la page Écrans</a></p>
  </div>

  <div class="card">
    <h2>Configuration écran PinCabOS actuelle</h2>
    <p>Source : <code>/opt/pincabos/config/screens/screens.json</code></p>
    <pre>{esc(screens_json)}</pre>
  </div>

  <div class="card">
    <h2>xrandr brut</h2>
    <pre>{esc(raw)}</pre>
  </div>
</div>
"""
    return page("GPU", body)


def pincabos_parse_xrandr_screens():
    """
    Détecte les écrans connectés via xrandr.
    Retourne une liste stable avec id, name, x, y, width, height, primary.
    """
    import subprocess
    import re

    env = os.environ.copy()
    env.setdefault("DISPLAY", ":0")
    env.setdefault("XAUTHORITY", "/home/pinball/.Xauthority")
    env.setdefault("XDG_RUNTIME_DIR", "/run/user/1000")

    cmd = [
        "bash",
        "--noprofile",
        "--norc",
        "-lc",
        "DISPLAY=:0 XAUTHORITY=/home/pinball/.Xauthority xrandr --query"
    ]

    r = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
    text = (r.stdout or "") + "\n" + (r.stderr or "")

    screens = []
    idx = 0

    # Exemples:
    # HDMI-1 connected primary 1920x1080+0+0 ...
    # DP-1 connected 1280x720+1920+0 ...
    pat = re.compile(r'^(?P<name>\S+)\s+connected(?P<primary>\s+primary)?\s+(?P<w>\d+)x(?P<h>\d+)\+(?P<x>-?\d+)\+(?P<y>-?\d+)')

    for line in text.splitlines():
        m = pat.search(line.strip())
        if not m:
            continue

        w = int(m.group("w"))
        h = int(m.group("h"))
        x = int(m.group("x"))
        y = int(m.group("y"))

        screens.append({
            "id": idx,
            "name": m.group("name"),
            "x": x,
            "y": y,
            "width": w,
            "height": h,
            "area": w * h,
            "is_primary": bool(m.group("primary")),
            "raw": line.strip(),
        })
        idx += 1

    return screens, text


def pincabos_load_screen_roles():
    """
    Lit /opt/pincabos/config/screens/screens.json et retourne les ids déjà assignés.
    """
    import json
    from pathlib import Path

    cfg = Path("/opt/pincabos/config/screens/screens.json")
    roles = {"playfield": "", "backglass": "", "fulldmd": ""}

    try:
        data = json.loads(cfg.read_text(errors="replace"))
        for role in roles:
            item = data.get(role)
            if isinstance(item, dict):
                # le nom de connecteur est stable ; l'id positionnel ne l'est pas
                roles[role] = str(item.get("name") or item.get("id") or "")
    except Exception:
        pass

    return roles


def pincabos_write_manual_screen_roles(playfield_id, backglass_id, fulldmd_id, cabinet_mode=True, playfield_orientation="landscape", playfield_rotation="0"):
    """
    Sauvegarde les rôles écran dans screens.json et met à jour VPinFE [Displays].
    """
    import json
    import subprocess
    from pathlib import Path

    screens, raw = pincabos_parse_xrandr_screens()

    cabinet_mode = bool(cabinet_mode)

    playfield_orientation = str(playfield_orientation or "landscape").strip().lower()
    if playfield_orientation not in ("landscape", "portrait"):
        playfield_orientation = "landscape"

    playfield_rotation = str(playfield_rotation or "0").strip()
    if playfield_rotation not in ("0", "90", "180", "270"):
        playfield_rotation = "0"

    # PINCABOS_SCREEN_IDENTITY_V2 : resolution par NOM de connecteur, avec
    # tolerance pour les anciennes sauvegardes exprimees en rang xrandr.
    by_id = {}
    for screen in screens:
        by_id[str(screen["name"])] = screen
        by_id.setdefault(str(screen["id"]), screen)

    if str(playfield_id) not in by_id:
        raise ValueError("Playfield invalide ou non sélectionné.")

    playfield = by_id.get(str(playfield_id))
    backglass = by_id.get(str(backglass_id)) if str(backglass_id) in by_id else None
    fulldmd = by_id.get(str(fulldmd_id)) if str(fulldmd_id) in by_id else None

    # Deux roles sur le meme ecran donnent un affichage clone : on refuse
    # plutot que de le laisser s'installer silencieusement.
    assigned = [
        (role, screen["name"])
        for role, screen in (
            ("Playfield", playfield),
            ("Backglass", backglass),
            ("FullDMD", fulldmd),
        )
        if screen
    ]
    # Backglass et FullDMD PEUVENT partager un ecran : le DMD occupe alors une
    # zone de l ecran du backglass, c est la configuration courante. Seul le
    # playfield doit rester seul : le partager produit un affichage clone et
    # fait rendre le B2S par-dessus la table (10 a 20 fps perdus).
    if playfield:
        for role, output in assigned:
            if role != "Playfield" and output == playfield["name"]:
                raise ValueError(
                    f"{role} est réglé sur l écran du Playfield ({output}). "
                    "Le playfield doit rester seul : choisissez un autre écran, ou « Aucun »."
                )

    layout = {
        "mode": "manual",
        "cabinet_mode": cabinet_mode,
        "playfield_orientation": playfield_orientation,
        "playfield_rotation": playfield_rotation,
        "playfield": playfield,
        "backglass": backglass,
        "fulldmd": fulldmd,
        "all_screens": screens,
        "xrandr_raw": raw,
    }

    cfg = Path("/opt/pincabos/config/screens/screens.json")
    cfg.parent.mkdir(parents=True, exist_ok=True)
    # PINCABOS_SCREENS_MERGE_V1
    # Les resolutions choisies sont enregistrees dans screens.json AVANT cette
    # ecriture (section "roles"). En reecrivant le fichier a partir d'un
    # dictionnaire neuf, on les effacait a chaque application : le menu
    # revenait donc toujours a "Auto / inchange". On conserve les sections
    # existantes que cette fonction ne gere pas.
    try:
        if cfg.exists():
            previous = json.loads(cfg.read_text(errors="replace") or "{}")
            if isinstance(previous, dict):
                for key, value in previous.items():
                    if key not in layout:
                        layout[key] = value
    except Exception:
        pass

    cfg.write_text(json.dumps(layout, indent=2, ensure_ascii=False), encoding="utf-8")

    # Mettre à jour VPinFE [Displays] sans toucher au reste.
    ini = pincabos_vpx_ini_path()
    lines = ini.read_text(errors="replace").splitlines() if ini.exists() else []

    def set_ini_key(lines, section, key, value):
        # PINCABOS_INI_UNIQUE_V1 : delegue a l ecrivain INI unique
        ini = pincabos_ini.Ini("\n".join(lines))
        ini.poser(section, key, value)
        return ini.lignes

    lines = set_ini_key(lines, "Displays", "tablescreenid", str(playfield["id"]))

    if backglass:
        lines = set_ini_key(lines, "Displays", "bgscreenid", str(backglass["id"]))
    else:
        lines = set_ini_key(lines, "Displays", "bgscreenid", "")

    if fulldmd:
        lines = set_ini_key(lines, "Displays", "dmdscreenid", str(fulldmd["id"]))
    else:
        lines = set_ini_key(lines, "Displays", "dmdscreenid", "")

    lines = set_ini_key(lines, "Displays", "cabmode", "true" if cabinet_mode else "false")
    lines = set_ini_key(lines, "Displays", "tableorientation", playfield_orientation)
    # PINCABOS_ROTATION_PHYSIQUE_V1 : la rotation est faite par xrandr ; VPinFE recoit 0.
    lines = set_ini_key(lines, "Displays", "tablerotation", "0")

    ini.parent.mkdir(parents=True, exist_ok=True)
    ini.write_text("\n".join(lines) + "\n", encoding="utf-8")

    try:
        subprocess.run(["/bin/chown", "pinball:pinball", str(cfg), str(ini)], timeout=5, check=False)
    except Exception:
        pass

    return layout

@gpu_bp.route("/gpu/screens")
def gpu_screens_page():
    return redirect(url_for("gpu.gpu_page"), code=302)



def pco_gpu_save_resolution_modes_to_screens_json():
    try:
        cfg = Path("/opt/pincabos/config/screens/screens.json")
        data = {}
        if cfg.exists():
            data = json.loads(cfg.read_text(errors="replace") or "{}")
        if not isinstance(data, dict):
            data = {}

        roles_data = data.get("roles")
        if not isinstance(roles_data, dict):
            roles_data = {}
            data["roles"] = roles_data

        for role in ("playfield", "backglass", "fulldmd"):
            value = (request.form.get(role + "_mode") or "").strip()
            if role not in roles_data or not isinstance(roles_data.get(role), dict):
                roles_data[role] = {}

            if value:
                if "@" in value:
                    mode, rate = value.split("@", 1)
                else:
                    mode, rate = value, ""
                roles_data[role]["mode"] = mode
                roles_data[role]["rate"] = rate
            else:
                roles_data[role].pop("mode", None)
                roles_data[role].pop("rate", None)

        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        return "GO: résolutions sauvegardées dans screens.json"
    except Exception as e:
        return "WARN: impossible de sauvegarder les résolutions: " + str(e)



def pco_gpu_apply_system_resolution_modes():
    helper = Path("/opt/pincabos/tools/pincabos-screen-xrandr.sh")
    if not helper.exists():
        return "WARN: helper système absent: " + str(helper)
    try:
        return run_cmd(["/usr/bin/sudo", "-n", str(helper), "apply"], timeout=30)
    except Exception as e:
        return "WARN: application système échouée: " + str(e)


@gpu_bp.route("/gpu/apply-screens", methods=["POST"])
def gpu_screens_apply():
    res_modes_out = pco_gpu_save_resolution_modes_to_screens_json()
    system_modes_out = pco_gpu_apply_system_resolution_modes()
    playfield = request.form.get("playfield", "").strip()
    backglass = request.form.get("backglass", "").strip()
    fulldmd = request.form.get("fulldmd", "").strip()
    cabinet_mode = request.form.get("cabinet_mode", "") == "1"
    playfield_orientation = request.form.get("playfield_orientation", "landscape").strip().lower()
    playfield_rotation = request.form.get("playfield_rotation", "0").strip()

    try:
        layout = pincabos_write_manual_screen_roles(playfield, backglass, fulldmd, cabinet_mode, playfield_orientation, playfield_rotation)
        # le choix explicite devient la verite durable du moteur de topologie
        subprocess.run(
            ["/usr/bin/sudo", "-n", "/usr/bin/python3",
             "/opt/pincabos/scripts/pincabos-screen-topology.py",
             "--adopt-current-roles"],
            timeout=30, check=False)
        output = json.dumps(layout, indent=2, ensure_ascii=False)
        cls = "ok"

        # PINCABOS_VPINFE_AUTORESTART_V1
        # VPinFE lit sa configuration au demarrage : sans redemarrage, le menu
        # continue d'afficher l'ancienne disposition. On ne le redemarre que
        # si aucune table ne tourne, pour ne jamais couper une partie.
        table_running = subprocess.run(
            ["/usr/bin/pgrep", "-u", "pinball", "-f", "VPinballX"],
            capture_output=True, timeout=5, check=False).returncode == 0

        if table_running:
            msg = ("Assignation écran enregistrée. Une table est en cours : "
                   "elle sera appliquée au prochain démarrage du frontend.")
        else:
            restart = subprocess.run(
                ["/usr/bin/sudo", "-n", "/usr/bin/systemctl", "restart",
                 "pincabos-vpinfe.service"],
                capture_output=True, text=True, timeout=60, check=False)
            if restart.returncode == 0:
                msg = "Assignation écran appliquée (frontend redémarré)."
            else:
                msg = ("Assignation écran enregistrée, mais le redémarrage du "
                       "frontend a échoué : elle sera appliquée au prochain "
                       "démarrage.")
                output += "\n\nRedémarrage VPinFE: " + (
                    (restart.stderr or restart.stdout or "").strip() or "échec")
    except Exception as e:
        output = str(e)
        cls = "bad"
        msg = "Erreur assignation écran."

    try:
        log_path = Path("/opt/pincabos/logs/gpu-last-action.log")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(msg + "\n\n" + output + "\n", encoding="utf-8")
        subprocess.run(["/bin/chown", "pinball:pinball", str(log_path)], timeout=5, check=False)
    except Exception:
        pass

    return redirect(url_for("gpu_page", gpu_action="screens", gpu_cls=cls, gpu_title=msg), code=303)


def pincabos_gpu_read_screens_config_for_apply():
    import json
    from pathlib import Path

    cfg = Path("/opt/pincabos/config/screens/screens.json")
    if not cfg.exists():
        raise ValueError("screens.json introuvable. Choisis d’abord les écrans dans GPU / Écrans.")

    data = json.loads(cfg.read_text(errors="replace"))

    playfield = data.get("playfield")
    backglass = data.get("backglass")
    fulldmd = data.get("fulldmd")

    if not isinstance(playfield, dict):
        raise ValueError("Playfield absent dans screens.json.")

    if not isinstance(backglass, dict):
        backglass = None

    if not isinstance(fulldmd, dict):
        fulldmd = None

    return data, playfield, backglass, fulldmd


def pincabos_gpu_ini_set_key_local(lines, section, key, value):
    # PINCABOS_INI_UNIQUE_V1 : delegue a l ecrivain INI unique
    ini = pincabos_ini.Ini("\n".join(lines))
    ini.poser(section, key, value)
    return ini.lignes


def pincabos_gpu_apply_config_to_vpinfe():
    # PINCABOS_TOPOLOGIE_SOURCE_UNIQUE_V1 : plus d ecriture directe ; screens.json est
    # la verite et la topologie (seule a poser les sections d affichage) l applique.
    return pincabos_gpu_rejouer_topologie("VPinFE")


def pincabos_gpu_rejouer_topologie(cible):
    import subprocess
    r = subprocess.run(
        ["/usr/bin/sudo", "-n", "/usr/bin/python3", "/opt/pincabos/scripts/pincabos-screen-topology.py", "--adopt-current-roles"],
        capture_output=True, text=True, timeout=60, check=False)
    queue = "\n".join(((r.stdout or "") + (r.stderr or "")).strip().splitlines()[-6:])
    etat = "appliqué" if r.returncode == 0 else f"ERREUR (code {r.returncode})"
    return f"""{cible} : {etat} par la topologie depuis screens.json.

La topologie est la seule à poser les sections d'affichage ([Displays], [PinCabOs.*],
sorties Backglass / ScoreView / Topper de VPX) : mode cabinet, orientation, identifiants
d'écrans et calibrations FullDMD / DMD, en une passe, pour VPinFE et VPX.

{queue}
"""


def pincabos_gpu_apply_config_to_vpx():
    # PINCABOS_TOPOLOGIE_SOURCE_UNIQUE_V1 : idem VPinFE, une seule source.
    return pincabos_gpu_rejouer_topologie("VPX")


@gpu_bp.route("/gpu/apply-vpinfe", methods=["POST"])
def gpu_apply_vpinfe():
    try:
        output = pincabos_gpu_apply_config_to_vpinfe()
        cls = "ok"
        title = "Configuration appliquée à VPinFE"
    except Exception as e:
        output = f"ERREUR: {e}"
        cls = "bad"
        title = "Erreur application VPinFE"

    body = f"""
<div class="card">
  <h2>{esc(title)}</h2>
  <pre class="{cls}">{esc(output)}</pre>
  <p>
    <a class="button" href="/gpu">Retour GPU / Écrans</a>
    <a class="button secondary" href="/gpu">Retour GPU / Écrans</a>
  </p>
</div>
"""
    return page("GPU", body)


@gpu_bp.route("/gpu/apply-vpx", methods=["POST"])
def gpu_apply_vpx():
    try:
        output = pincabos_gpu_apply_config_to_vpx()
        cls = "ok"
        title = "Configuration appliquée à VPX"
    except Exception as e:
        output = f"ERREUR: {e}"
        cls = "bad"
        title = "Erreur application VPX"

    body = f"""
<div class="card">
  <h2>{esc(title)}</h2>
  <pre class="{cls}">{esc(output)}</pre>
  <p>
    <a class="button" href="/gpu">Retour GPU / Écrans</a>
    <a class="button secondary" href="/gpu">Retour GPU / Écrans</a>
  </p>
</div>
"""
    return page("GPU", body)


@gpu_bp.route("/restart-vpinfe", methods=["POST"])
def restart_vpinfe():
    subprocess.Popen(
        ["/usr/bin/sudo", "/bin/systemctl", "restart", "pincabos-vpinfe.service"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return redirect(url_for("gpu.gpu_page"))

@gpu_bp.route("/auto-screens", methods=["POST"])
def auto_screens():
    subprocess.Popen(
        ["/usr/bin/sudo", str(pco_script("auto_detect_screens"))],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return redirect(url_for("gpu.gpu_page"))


def register(app, page_fn):
    """Enregistre les pages GPU / Écrans sur l'application."""
    global page
    page = page_fn
    app.register_blueprint(gpu_bp)
