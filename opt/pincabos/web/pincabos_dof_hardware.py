#!/usr/bin/env python3
# PinCabOs-File
"""PinCabOS — Matériel DOF & cabinet.xml (/dof/hardware).

Page web de gestion matérielle DOF :
  - détection réelle des contrôleurs par VID/PID (udevadm), toutes familles :
    Teensy, Dude's Cab/RP2040, LedWiz, Pinscape KL25Z/Pico, PacLed/Ultimarc,
    FTDI... avec distinction AutoConfig / à déclarer dans cabinet.xml ;
  - lecture du cabinet.xml actuel (contrôleurs déclarés, toys, strips) ;
  - assistant de génération de cabinet.xml (conforme au parseur libdof),
    avec aperçu, sauvegarde automatique de l'ancien fichier et restauration.

Modulable par construction : un cab sans strip adressable obtient un
cabinet.xml AutoConfig seul (DOF détecte tout seul DudesCab, LedWiz, KL25Z,
Pico, PacLed...). Les strips Teensy/Wemos ne sont déclarés que s'ils existent.

La logique détection/génération vit dans /opt/pincabos/tools/dof-cabinet/
(partagée avec la CLI) ; cette page n'est qu'une façade web.
"""

import glob
import importlib.util
import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from flask import request, redirect, jsonify

MARKER = "PINCABOS_DOF_HARDWARE_PAGE_V1"

TOOL_PATH = Path(os.environ.get(
    "PINCABOS_DOF_CABINET_TOOL",
    "/opt/pincabos/tools/dof-cabinet/dof-cabinet.py"
))
STATE_DIR = Path("/opt/pincabos/config/dof/cabinet-wizard")
BACKUP_DIR = Path("/opt/pincabos/backups/dof-cabinet")
GENERATED_XML = STATE_DIR / "cabinet-generated.xml"
GENERATED_CFG = STATE_DIR / "config.json"

_tool = None


def _load_tool():
    """Charge dof-cabinet.py comme module (source unique de vérité CLI + web)."""
    global _tool
    if _tool is not None:
        return _tool
    if not TOOL_PATH.exists():
        return None
    spec = importlib.util.spec_from_file_location("pincabos_dofcab_tool", str(TOOL_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _tool = mod
    return mod


def _cfgdir():
    """Dossier directoutputconfig de la version VPX la plus récente."""
    dirs = sorted(glob.glob("/home/pinball/.local/share/VPinballX/*/directoutputconfig"))
    return Path(dirs[-1]) if dirs else None


def _cabinet_path():
    d = _cfgdir()
    return (d / "cabinet.xml") if d else None


def _run(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return "erreur: %s" % e


def _parse_cabinet(path):
    """Résumé du cabinet.xml actuel selon le schéma réellement lu par libdof."""
    import xml.etree.ElementTree as ET
    info = {"name": "", "auto_config": None, "controllers": [], "toys": [], "error": ""}
    try:
        root = ET.parse(str(path)).getroot()
    except Exception as e:
        info["error"] = str(e)
        return info
    info["name"] = (root.findtext("Name") or "").strip()
    ac = (root.findtext("AutoConfigEnabled") or "").strip().lower()
    info["auto_config"] = (ac == "true") if ac else None
    oc = root.find("OutputControllers")
    if oc is not None:
        for c in oc:
            info["controllers"].append({
                "type": c.tag,
                "name": (c.findtext("Name") or "").strip(),
                "port": (c.findtext("ComPortName") or "").strip(),
            })
    toys = root.find("Toys")
    if toys is not None:
        for t in toys:
            entry = {"type": t.tag, "name": (t.findtext("Name") or "").strip()}
            if t.tag == "LedStrip":
                entry["detail"] = "%sx%s LEDs, %s, %s, luminosité %s" % (
                    t.findtext("Width") or "?", t.findtext("Height") or "?",
                    (t.findtext("LedStripArrangement") or "?"),
                    (t.findtext("ColorOrder") or "?"),
                    (t.findtext("Brightness") or "?"))
            elif t.tag == "LedWizEquivalent":
                outs = t.find("Outputs")
                entry["detail"] = "LedWiz n°%s, %d sorties" % (
                    (t.findtext("LedWizNumber") or "?").strip(),
                    len(list(outs)) if outs is not None else 0)
            else:
                entry["detail"] = ""
            info["toys"].append(entry)
    return info


def _config_from_form(form):
    """Construit la config déclarative (format dof-cabinet) depuis le formulaire."""
    raw = (form.get("raw_json") or "").strip()
    if raw:
        return json.loads(raw)

    cfg = {
        "name": (form.get("cab_name") or "PinCabOS Cabinet").strip(),
        "auto_config": form.get("auto_config", "1") == "1",
        "strips": [], "artnet": [], "pinone": [],
    }
    if form.get("has_strip") == "1":
        leds = []
        for i in range(1, 9):
            try:
                leds.append(max(0, int(form.get("leds_%d" % i, "0") or "0")))
            except ValueError:
                leds.append(0)
        try:
            brightness = min(100, max(1, int(form.get("brightness", "25") or "25")))
        except ValueError:
            brightness = 25
        strip = {
            "controller": form.get("strip_controller") or "TeensyStripController",
            "name": (form.get("strip_name") or "TeensyStripController 1").strip(),
            "com_port": (form.get("com_port") or "auto").strip() or "auto",
            "baud": 9600,
            "leds_per_strip": leds,
            "test_on_connect": False,
            "toy": {
                "name": (form.get("toy_name") or "Backboard").strip(),
                "width": int(form.get("toy_width", "144") or "144"),
                "height": int(form.get("toy_height", "16") or "16"),
                "arrangement": form.get("arrangement") or "TopDownAlternateLeftRight",
                "color_order": form.get("color_order") or "GRB",
                "first_led": 1,
                "brightness": brightness,
                "fading_curve": "Linear",
            },
            "ledwiz_number": int(form.get("ledwiz_number", "30") or "30"),
            "ledwiz_outputs": int(form.get("ledwiz_outputs", "9") or "9"),
        }
        if strip["controller"] == "WemosD1MPStripController" and form.get("wemos_host"):
            strip["host"] = form.get("wemos_host").strip()
        cfg["strips"].append(strip)
    return cfg


def register(app, page, esc):
    """Enregistre les routes /dof/hardware sur l'app Flask PinCabOS."""

    def detection_rows():
        tool = _load_tool()
        if tool is None:
            return None, '<tr><td colspan="5"><span class="bad">Outil dof-cabinet absent (%s)</span></td></tr>' % esc(str(TOOL_PATH))
        try:
            devices = tool.detect()
        except Exception as e:
            return None, '<tr><td colspan="5"><span class="bad">Erreur détection : %s</span></td></tr>' % esc(str(e))
        rows = []
        for d in devices:
            if d["auto_config"]:
                badge = '<span class="ok">AutoConfig — rien à déclarer</span>'
            else:
                badge = '<span class="warn">à déclarer dans cabinet.xml</span>'
            rows.append(
                "<tr><td><code>%s</code></td><td>%s</td><td><code>%s</code></td>"
                "<td><code>%s</code></td><td>%s</td></tr>" % (
                    esc(d["dev"]), esc(d["kind"]), esc(d["vid"]),
                    esc(d["serial"] or "-"), badge))
        if not rows:
            rows.append('<tr><td colspan="5"><span class="warn">Aucun contrôleur DOF détecté '
                        '(cartes débranchées, ou machine de dev).</span></td></tr>')
        return devices, "".join(rows)

    def current_cabinet_card():
        cab = _cabinet_path()
        if cab is None or not cab.exists():
            return """
<div class="card" style="margin-top:20px;">
  <h2>cabinet.xml actuel</h2>
  <p class="warn">Aucun cabinet.xml trouvé. L'assistant ci-dessous peut en générer un.</p>
</div>"""
        info = _parse_cabinet(cab)
        if info["error"]:
            body = '<p class="bad">XML invalide : %s</p>' % esc(info["error"])
        else:
            ctr_rows = "".join(
                "<tr><td><code>%s</code></td><td>%s</td><td><code>%s</code></td></tr>" % (
                    esc(c["type"]), esc(c["name"]), esc(c["port"] or "-"))
                for c in info["controllers"]) or '<tr><td colspan="3">aucun contrôleur déclaré (AutoConfig seul)</td></tr>'
            toy_rows = "".join(
                "<tr><td><code>%s</code></td><td>%s</td><td>%s</td></tr>" % (
                    esc(t["type"]), esc(t["name"]), esc(t["detail"]))
                for t in info["toys"]) or '<tr><td colspan="3">aucun toy déclaré</td></tr>'
            ac = info["auto_config"]
            ac_html = '<span class="ok">activé</span>' if ac else (
                '<span class="warn">désactivé</span>' if ac is False else "?")
            body = """
    <table>
      <tr><td>Nom</td><td><code>%s</code></td></tr>
      <tr><td>AutoConfig (DudesCab, LedWiz, Pinscape, PacLed...)</td><td>%s</td></tr>
    </table>
    <h3>Contrôleurs déclarés</h3>
    <table>
      <tr><th style="text-align:left;">Type</th><th style="text-align:left;">Nom</th><th style="text-align:left;">Port</th></tr>
      %s
    </table>
    <h3>Toys déclarés</h3>
    <table>
      <tr><th style="text-align:left;">Type</th><th style="text-align:left;">Nom</th><th style="text-align:left;">Détail</th></tr>
      %s
    </table>""" % (esc(info["name"]), ac_html, ctr_rows, toy_rows)
        raw = ""
        try:
            raw = cab.read_text(errors="replace")
        except Exception:
            pass
        backups = sorted(BACKUP_DIR.glob("cabinet.xml.bak-*"), reverse=True)
        restore_html = ""
        if backups:
            restore_html = """
    <form method="post" action="/dof/hardware/restore" style="margin-top:10px;"
          onsubmit="return confirm('Restaurer la dernière sauvegarde du cabinet.xml ?');">
      <button class="button secondary" type="submit">Restaurer la dernière sauvegarde (%s)</button>
    </form>""" % esc(backups[0].name)
        return """
<div class="card" style="margin-top:20px;">
  <h2>cabinet.xml actuel</h2>
  <p><code>%s</code></p>
  %s
  <details style="margin-top:10px;"><summary>Contenu brut</summary><pre style="max-height:400px;overflow:auto;">%s</pre></details>
  %s
</div>""" % (esc(str(cab)), body, esc(raw), restore_html)

    def wizard_card(devices):
        tool = _load_tool()
        arrangements = getattr(tool, "ADDRESSABLE_ARRANGEMENTS", []) if tool else []
        color_orders = getattr(tool, "COLOR_ORDERS", ["RGB", "GRB"]) if tool else ["RGB", "GRB"]
        teensy_detected = any(
            (d.get("auto_config") is False and "Teensy" in d.get("kind", ""))
            for d in (devices or []))
        arr_opts = "".join(
            '<option value="%s"%s>%s</option>' % (
                a, ' selected' if a == "TopDownAlternateLeftRight" else "", a)
            for a in arrangements)
        co_opts = "".join(
            '<option value="%s"%s>%s</option>' % (
                c, ' selected' if c == "GRB" else "", c)
            for c in color_orders)
        strip_checked = "checked" if teensy_detected else ""
        hint = ('<p class="ok">Un Teensy (strips adressables) est détecté : '
                'la section strip est pré-cochée.</p>' if teensy_detected else
                '<p>Pas de strip adressable détecté. Sans strip, le cabinet.xml généré '
                'contient uniquement AutoConfig : DOF détectera tout seul les DudesCab, '
                'LedWiz, Pinscape (KL25Z/Pico), PacLed branchés — rien d\'autre à faire.</p>')
        led_inputs = "".join(
            '<label style="display:inline-block;margin:4px 8px 4px 0;">Sortie %d '
            '<input type="number" name="leds_%d" value="%s" min="0" max="1100" style="width:80px;"></label>' % (
                i, i, "512" if i <= 4 else ("256" if i == 5 else "0"))
            for i in range(1, 9))
        return """
<div class="card" style="margin-top:20px;">
  <h2>Assistant cabinet.xml</h2>
  <p>
    Génère un <code>cabinet.xml</code> conforme à ce que lit réellement libdof.
    L'ancien fichier est sauvegardé automatiquement avant tout remplacement.
  </p>
  %s
  <form method="post" action="/dof/hardware/generate">
    <table>
      <tr><td>Nom du cabinet</td>
          <td><input type="text" name="cab_name" value="PinCabOS Cabinet"></td></tr>
      <tr><td>AutoConfig (recommandé)</td>
          <td><label><input type="checkbox" name="auto_config" value="1" checked>
              laisser DOF détecter les contrôleurs standards (DudesCab, LedWiz, Pinscape, PacLed...)</label></td></tr>
    </table>

    <h3 style="margin-top:14px;">Strip adressable (backboard, matrice, undercab)</h3>
    <label><input type="checkbox" name="has_strip" value="1" %s>
        Déclarer un contrôleur de strips adressables</label>

    <table style="margin-top:8px;">
      <tr><td>Contrôleur</td>
          <td><select name="strip_controller">
                <option value="TeensyStripController" selected>TeensyStripController (USB série)</option>
                <option value="WemosD1MPStripController">WemosD1MPStripController (réseau)</option>
              </select></td></tr>
      <tr><td>Nom</td><td><input type="text" name="strip_name" value="TeensyStripController 1"></td></tr>
      <tr><td>Port série</td>
          <td><input type="text" name="com_port" value="auto">
              <small>« auto » = trouve le Teensy tout seul (recommandé, robuste au changement de port au boot)</small></td></tr>
      <tr><td>Hôte Wemos (si réseau)</td><td><input type="text" name="wemos_host" value=""></td></tr>
      <tr><td>LEDs par sortie</td><td>%s</td></tr>
    </table>

    <h3 style="margin-top:14px;">Toy matrice (LedStrip)</h3>
    <table>
      <tr><td>Nom du toy</td><td><input type="text" name="toy_name" value="Backboard"></td></tr>
      <tr><td>Largeur (LEDs)</td><td><input type="number" name="toy_width" value="144" min="1" max="1024" style="width:90px;"></td></tr>
      <tr><td>Hauteur (LEDs)</td><td><input type="number" name="toy_height" value="16" min="1" max="1024" style="width:90px;"></td></tr>
      <tr><td>Arrangement</td><td><select name="arrangement">%s</select></td></tr>
      <tr><td>Ordre des couleurs</td><td><select name="color_order">%s</select></td></tr>
      <tr><td>Luminosité (1-100)</td>
          <td><input type="number" name="brightness" value="25" min="1" max="100" style="width:90px;">
              <span class="warn">garder BAS : la pleine luminosité d'une grosse matrice
              peut dépasser la capacité de l'alimentation</span></td></tr>
      <tr><td>N° LedWiz équivalent</td>
          <td><input type="number" name="ledwiz_number" value="30" min="1" max="128" style="width:90px;">
              <small>doit correspondre au device n° du DOF Config Tool (30 = habituel pour MX/adressable)</small></td></tr>
      <tr><td>Sorties LedWiz équiv.</td>
          <td><input type="number" name="ledwiz_outputs" value="9" min="1" max="64" style="width:90px;"></td></tr>
    </table>

    <details style="margin-top:12px;">
      <summary>Mode avancé : config JSON brute (multi-strips, ArtNet, PinOne)</summary>
      <p><small>Si rempli, ce JSON remplace tout le formulaire ci-dessus.
      Format : voir <code>%s sample</code>.</small></p>
      <textarea name="raw_json" rows="8" style="width:100%%;font-family:monospace;"></textarea>
    </details>

    <p style="margin-top:14px;">
      <button class="button" type="submit">Générer l'aperçu</button>
    </p>
  </form>
</div>""" % (hint, strip_checked, led_inputs, arr_opts, co_opts, esc(str(TOOL_PATH)))

    @app.route("/dof/hardware")
    def dof_hardware_page():
        devices, det_rows = detection_rows()
        raw_usb = _run(["lsusb"])
        body = """
<div class="card">
  <h2>Matériel DOF &amp; cabinet.xml</h2>
  <p>
    Détection réelle des contrôleurs branchés (par VID/PID udev) et gestion du
    <code>cabinet.xml</code>. Chaque cab est différent : Dude's Cab, Teensy,
    KL25Z, Pico, LedWiz, PacLed... tout est optionnel, seule la réalité du
    matériel branché compte.
  </p>
  <p>
    <a class="button secondary" href="/dof">Retour DOF</a>
    <a class="button secondary" href="/dof/commander">DOF Commander</a>
    <a class="button secondary" href="/dof/hardware">Rafraîchir</a>
  </p>
</div>

<div class="card" style="margin-top:20px;">
  <h2>Contrôleurs détectés</h2>
  <table>
    <tr><th style="text-align:left;">Périphérique</th><th style="text-align:left;">Type</th>
        <th style="text-align:left;">VID</th><th style="text-align:left;">Série</th>
        <th style="text-align:left;">cabinet.xml</th></tr>
    %s
  </table>
  <p><small>« AutoConfig » : DOF le trouve tout seul, rien à déclarer.
  « à déclarer » : doit figurer dans cabinet.xml (strips adressables).</small></p>
  <details style="margin-top:8px;"><summary>lsusb brut</summary><pre>%s</pre></details>
</div>
%s
%s
""" % (det_rows, esc(raw_usb), current_cabinet_card(), wizard_card(devices))
        return page("Matériel DOF", body)

    @app.route("/dof/hardware/detect.json")
    def dof_hardware_detect_json():
        tool = _load_tool()
        if tool is None:
            return jsonify({"ok": False, "error": "outil dof-cabinet absent"}), 500
        try:
            return jsonify({"ok": True, "devices": tool.detect()})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.route("/dof/hardware/generate", methods=["POST"])
    def dof_hardware_generate():
        tool = _load_tool()
        if tool is None:
            return page("Matériel DOF", '<div class="card"><p class="bad">Outil dof-cabinet absent.</p></div>')
        try:
            cfg = _config_from_form(request.form)
            xml = tool.gen(cfg)
        except Exception as e:
            return page("Matériel DOF", """
<div class="card"><h2>Erreur de génération</h2><p class="bad">%s</p>
<p><a class="button" href="/dof/hardware">Retour</a></p></div>""" % esc(str(e)))
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        GENERATED_CFG.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        GENERATED_XML.write_text(xml, encoding="utf-8")
        cab = _cabinet_path()
        cur = ""
        if cab and cab.exists():
            try:
                cur = cab.read_text(errors="replace")
            except Exception:
                pass
        same = (cur.strip() == xml.strip()) if cur else False
        status = ('<p class="ok">Identique au cabinet.xml actuel — rien à appliquer.</p>' if same else
                  ('<p class="warn">Différent du cabinet.xml actuel. L\'appliquer le remplacera '
                   '(sauvegarde automatique).</p>' if cur else
                   '<p class="warn">Aucun cabinet.xml actuel : celui-ci sera installé.</p>'))
        body = """
<div class="card">
  <h2>Aperçu du cabinet.xml généré</h2>
  %s
  <pre style="max-height:480px;overflow:auto;background:#050007;border:1px solid #5f2a91;border-radius:12px;padding:12px;">%s</pre>
  <form method="post" action="/dof/hardware/apply"
        onsubmit="return confirm('Remplacer le cabinet.xml ? (sauvegarde automatique)');">
    <label style="display:block;margin:8px 0;">
      <input type="checkbox" name="restart_vpinfe" value="1" checked>
      Redémarrer VPinFE après application (nécessaire pour recharger DOF)
    </label>
    <button class="button" type="submit">Appliquer ce cabinet.xml</button>
    <a class="button secondary" href="/dof/hardware">Retour / modifier</a>
  </form>
</div>""" % (status, esc(xml))
        return page("Matériel DOF", body)

    @app.route("/dof/hardware/apply", methods=["POST"])
    def dof_hardware_apply():
        if not GENERATED_XML.exists():
            return page("Matériel DOF", '<div class="card"><p class="bad">Aucun aperçu généré. '
                        'Repasse par l\'assistant.</p><p><a class="button" href="/dof/hardware">Retour</a></p></div>')
        d = _cfgdir()
        if d is None:
            return page("Matériel DOF", '<div class="card"><p class="bad">Dossier directoutputconfig '
                        'introuvable (VPX non installé ?).</p><p><a class="button" href="/dof/hardware">Retour</a></p></div>')
        cab = d / "cabinet.xml"
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_note = "aucun fichier précédent"
        if cab.exists():
            backup = BACKUP_DIR / ("cabinet.xml.bak-" + stamp)
            shutil.copy2(cab, backup)
            backup_note = str(backup)
        shutil.copy2(GENERATED_XML, cab)
        try:
            shutil.chown(str(cab), user="pinball", group="pinball")
        except Exception:
            pass
        restart_log = ""
        if request.form.get("restart_vpinfe") == "1":
            restart_log = _run(["systemctl", "restart", "pincabos-vpinfe.service"], timeout=30)
        body = """
<div class="card">
  <h2>cabinet.xml appliqué</h2>
  <table>
    <tr><td>Fichier</td><td><code>%s</code></td></tr>
    <tr><td>Sauvegarde</td><td><code>%s</code></td></tr>
    <tr><td>Redémarrage VPinFE</td><td><code>%s</code></td></tr>
  </table>
  <p><a class="button" href="/dof/hardware">Retour Matériel DOF</a>
     <a class="button secondary" href="/dof">Page DOF</a></p>
</div>""" % (esc(str(cab)), esc(backup_note),
             esc(restart_log.strip() or ("demandé" if request.form.get("restart_vpinfe") == "1" else "non demandé")))
        return page("Matériel DOF", body)

    @app.route("/dof/hardware/restore", methods=["POST"])
    def dof_hardware_restore():
        backups = sorted(BACKUP_DIR.glob("cabinet.xml.bak-*"), reverse=True)
        cab = _cabinet_path()
        if not backups or cab is None:
            return page("Matériel DOF", '<div class="card"><p class="bad">Aucune sauvegarde à restaurer.</p>'
                        '<p><a class="button" href="/dof/hardware">Retour</a></p></div>')
        shutil.copy2(backups[0], cab)
        try:
            shutil.chown(str(cab), user="pinball", group="pinball")
        except Exception:
            pass
        return redirect("/dof/hardware")

    return True
