from __future__ import annotations

import configparser
import html
import json
import re
import subprocess
import sys
from pathlib import Path

from flask import Blueprint, redirect, request, url_for

screen_bp = Blueprint("screen", __name__)

CFG_DIR = Path("/opt/pincabos/config/screens")
CFG_FILE = CFG_DIR / "screens.json"
VPINFE_INI = Path("/home/pinball/.config/vpinfe/vpinfe.ini")
VPX_INI = Path("/home/pinball/.local/share/VPinballX/10.8/VPinballX.ini")
XRANDR_HELPER = Path("/opt/pincabos/tools/pincabos-screen-xrandr.sh")


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def run_cmd(cmd, timeout=30) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        return p.returncode, p.stdout
    except Exception as e:
        return 99, f"Erreur commande: {e}"


def xrandr_query() -> str:
    rc, out = run_cmd(["/usr/bin/sudo", "-n", str(XRANDR_HELPER), "query"], timeout=15)
    if rc != 0:
        return out
    return out


def parse_xrandr(raw: str) -> list[dict]:
    screens = []
    current = None

    for line in raw.splitlines():
        m = re.match(r"^([A-Za-z0-9_.:-]+)\s+connected(?:\s+primary)?\s*(?:(\d+)x(\d+)\+(-?\d+)\+(-?\d+))?.*$", line)
        if m:
            current = {
                "output": m.group(1),
                "connected": True,
                "primary": " connected primary " in f" {line} ",
                "current": f"{m.group(2)}x{m.group(3)}" if m.group(2) else "",
                "x": m.group(4) or "",
                "y": m.group(5) or "",
                "modes": [],
            }
            screens.append(current)
            continue

        if current:
            mm = re.match(r"^\s+(\d+x\d+)\s+(.+)$", line)
            if mm:
                mode = mm.group(1)
                rest = mm.group(2)
                rates = []
                for r in re.findall(r"(\d+(?:\.\d+)?)\*?\+?", rest):
                    try:
                        rates.append(r)
                    except Exception:
                        pass
                if not rates:
                    rates = [""]
                current["modes"].append({"mode": mode, "rates": rates})

    return screens


def load_cfg() -> dict:
    try:
        if CFG_FILE.exists():
            return json.loads(CFG_FILE.read_text(errors="replace") or "{}")
    except Exception:
        pass
    return {
        "cabinet_mode": True,
        "playfield_orientation": "landscape",
        "playfield_rotation": "0",
        "roles": {},
    }


def save_cfg(data: dict) -> None:
    CFG_DIR.mkdir(parents=True, exist_ok=True)
    data["updated_by"] = "PinCabOS WebApp screen.py"
    CFG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def mode_options(screen: dict, selected_mode: str, selected_rate: str, prefix: str) -> str:
    out = ['<option value="">-- Auto / inchangé --</option>']
    for item in screen.get("modes", []):
        mode = item.get("mode", "")
        for rate in item.get("rates", [""]):
            value = f"{mode}@{rate}" if rate else mode
            label = f"{mode} {rate}Hz" if rate else mode
            sel = "selected" if mode == selected_mode and (not selected_rate or rate == selected_rate) else ""
            out.append(f'<option value="{esc(value)}" {sel}>{esc(label)}</option>')
    return "\n".join(out)


def screen_options(screens: list[dict], selected: str) -> str:
    out = ['<option value="">-- Aucun --</option>']
    for idx, sc in enumerate(screens):
        label = f'ID {idx} — {sc["output"]}'
        if sc.get("current"):
            label += f' — {sc["current"]}+{sc.get("x") or "0"}+{sc.get("y") or "0"}'
        if sc.get("primary"):
            label += " — primary X11"
        sel = "selected" if sc["output"] == selected else ""
        out.append(f'<option value="{esc(sc["output"])}" {sel}>{esc(label)}</option>')
    return "\n".join(out)


def find_screen(screens, output):
    for sc in screens:
        if sc.get("output") == output:
            return sc
    return screens[0] if screens else {"modes": []}


def parse_mode_rate(value: str) -> tuple[str, str]:
    value = str(value or "")
    if "@" in value:
        a, b = value.split("@", 1)
        return a, b
    return value, ""


def write_from_form(form) -> dict:
    data = load_cfg()
    roles = {}

    for role in ("playfield", "backglass", "fulldmd", "topper"):
        output = form.get(f"{role}_output", "").strip()
        mode, rate = parse_mode_rate(form.get(f"{role}_mode", "").strip())
        roles[role] = {
            "output": output,
            "mode": mode,
            "rate": rate,
        }

    data["roles"] = roles

    # PINCABOS_SCREEN_PAGE_TRUTH_V1
    # screens.json porte deux schemas : les objets de premier niveau, que lit
    # tout le systeme (topologie, politique B2S, placement des fenetres), et
    # la cle "roles" ecrite ici. La chaine de roles assurait la recopie ;
    # quand elle est masquee, un changement de role n'atteint plus personne.
    # On alimente donc les deux, pour que la page reste la source de verite
    # meme sans cette chaine.
    screens_courants = parse_xrandr(xrandr_query())
    for role, choix in roles.items():
        # PINCABOS_SCREEN_PAGE_NONE_ROLE_GUARD_V1
        # find_screen() retombe volontairement sur le premier ecran pour
        # l'affichage des menus. Cette tolerance ne doit jamais etre utilisee
        # lors de l'ecriture : "-- Aucun --" doit reellement supprimer le role.
        sortie = str(choix.get("output") or "")
        if not sortie:
            data.pop(role, None)
            continue
        sc = next(
            (s for s in screens_courants if s.get("output") == sortie),
            None,
        )
        if not sc:
            continue
        largeur_hauteur = sc.get("current") or ""
        x = sc.get("x") or "0"
        y = sc.get("y") or "0"
        ancien = data.get(role) if isinstance(data.get(role), dict) else {}
        data[role] = {
            **ancien,
            "name": sc["output"],
            "geometry": f"{largeur_hauteur}+{x}+{y}" if largeur_hauteur else "",
            "x": int(x),
            "y": int(y),
            "is_primary": bool(sc.get("primary")),
            "available": True,
        }
        if largeur_hauteur and "x" in largeur_hauteur:
            l, h = largeur_hauteur.split("x", 1)
            if l.isdigit() and h.isdigit():
                data[role]["width"] = int(l)
                data[role]["height"] = int(h)

    data["cabinet_mode"] = bool(form.get("cabinet_mode"))
    data["playfield_orientation"] = form.get("playfield_orientation", "landscape")
    data["playfield_rotation"] = form.get("playfield_rotation", "0")
    save_cfg(data)
    return data


def role_index(screens: list[dict], output: str) -> str:
    """Identifiant de l'ecran tel que le comptent les applications.

    PINCABOS_APP_SCREEN_INDEX_V1

    VPinFE numerote les sorties dans l'ordre ou le serveur X les declare, et
    ne compte que celles qui affichent quelque chose. Une sortie branchee mais
    eteinte ne doit donc pas consommer un numero, sans quoi tous les ecrans
    suivants se decalent.
    """
    index = 0
    for sc in screens:
        if not sc.get("current"):
            continue
        if sc.get("output") == output:
            return str(index)
        index += 1
    return ""


def apply_vpinfe() -> str:
    raw = xrandr_query()
    screens = parse_xrandr(raw)
    cfg = load_cfg()
    roles = cfg.get("roles", {})

    cp = configparser.ConfigParser()
    cp.optionxform = str.lower
    if VPINFE_INI.exists():
        cp.read(VPINFE_INI)

    if not cp.has_section("Displays"):
        cp.add_section("Displays")

    pf_id = role_index(screens, roles.get("playfield", {}).get("output", ""))
    bg_id = role_index(screens, roles.get("backglass", {}).get("output", ""))
    fd_id = role_index(screens, roles.get("fulldmd", {}).get("output", ""))

    cp.set("Displays", "tablescreenid", pf_id)
    cp.set("Displays", "bgscreenid", bg_id)
    cp.set("Displays", "fulldmdscreenid", fd_id)
    cp.set("Displays", "dmdscreenid", fd_id)
    cp.set("Displays", "cabmode", "true" if cfg.get("cabinet_mode", True) else "false")
    cp.set("Displays", "tableorientation", str(cfg.get("playfield_orientation", "landscape")))
    cp.set("Displays", "tablerotation", str(cfg.get("playfield_rotation", "0")))

    if not cp.has_section("PinCabOS.Screens"):
        cp.add_section("PinCabOS.Screens")
    cp.set("PinCabOS.Screens", "playfield_id", pf_id)
    cp.set("PinCabOS.Screens", "backglass_id", bg_id)
    cp.set("PinCabOS.Screens", "fulldmd_id", fd_id)

    VPINFE_INI.parent.mkdir(parents=True, exist_ok=True)
    with VPINFE_INI.open("w") as f:
        cp.write(f)

    return f"GO: VPinFE mis à jour: {VPINFE_INI}"


def apply_vpx() -> str:
    # Essaie d'abord la fonction existante app.py, si elle est chargée.
    for modname in ("app", "__main__"):
        mod = sys.modules.get(modname)
        fn = getattr(mod, "pincabos_gpu_apply_config_to_vpx", None) if mod else None
        if callable(fn):
            try:
                return str(fn())
            except Exception as e:
                return f"NOGO: fonction app.py pincabos_gpu_apply_config_to_vpx a échoué: {e}"

    return "WARN: fonction VPX existante non trouvée dans app.py; screens.json a été sauvegardé seulement."


def page_wrap(title: str, body: str):
    for modname in ("app", "__main__"):
        mod = sys.modules.get(modname)
        fn = getattr(mod, "page", None) if mod else None
        if callable(fn):
            try:
                return fn(title, body)
            except TypeError:
                pass
            except Exception:
                pass

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{esc(title)}</title>
<link rel="stylesheet" href="/static/pincabos-branding.css">
<link rel="stylesheet" href="/static/pincabos-global-compact.css">
<style>
body{{font-family:system-ui;margin:24px;background:#14001f;color:#fff}}
.card{{background:#220033;border:1px solid rgba(255,138,0,.35);border-radius:18px;padding:18px;margin:14px 0}}
.button,button{{background:#ff8a00;color:#000;border:0;border-radius:10px;padding:10px 14px;font-weight:800;cursor:pointer;text-decoration:none;display:inline-block}}
.secondary{{background:#3a164d;color:#fff}}
select,input{{background:#110019;color:#fff;border:1px solid rgba(255,255,255,.25);border-radius:10px;padding:9px;width:100%}}
.grid{{display:grid;grid-template-columns:repeat(3,minmax(220px,1fr));gap:14px}}
pre{{background:#08000d;color:#eee;border-radius:12px;padding:12px;overflow:auto}}
</style></head><body>{body}</body></html>"""


@screen_bp.route("/screen", methods=["GET"])
def screen_page():
    raw = xrandr_query()
    screens = parse_xrandr(raw)
    cfg = load_cfg()
    roles = cfg.get("roles", {})

    def role_reel(role: str) -> str:
        """Sortie effectivement associee au role, telle que le systeme la voit.

        On privilegie l'objet de premier niveau — celui que lisent la
        topologie et le placement des fenetres — et on retombe sur "roles"
        quand il est absent, par exemple sur une installation neuve.
        """
        entree = cfg.get(role)
        if isinstance(entree, dict) and entree.get("name"):
            return str(entree["name"])
        return str(roles.get(role, {}).get("output", ""))

    # PINCABOS_SCREEN_IDENTIFY_V1
    # Un lien plutot qu'un bouton : ces cartes vivent a l'interieur du
    # formulaire de reglages, et un formulaire imbrique n'est pas valide.
    # L'action n'ecrit rien — elle affiche un panneau quelques secondes.
    def identification(sortie: str) -> str:
        if not sortie:
            return ""
        return (
            "<a class='button secondary' style='margin-top:12px;display:inline-block'"
            f" href='/screen/identify?output={esc(sortie)}'>Identifier cet écran</a>"
            "<div style='opacity:.6;font-size:.85em;margin-top:6px'>"
            "Affiche le nom de la sortie sur l'écran concerné, et le fait clignoter."
            "</div>"
        )

    def role_card(role, title):
        selected_output = role_reel(role)
        selected_mode = roles.get(role, {}).get("mode", "")
        selected_rate = roles.get(role, {}).get("rate", "")
        sc = find_screen(screens, selected_output)
        return f"""
        <div class="card">
          <h3>{esc(title)}</h3>
          <label>Écran</label>
          <select name="{role}_output">{screen_options(screens, selected_output)}</select>
          <label style="margin-top:10px;display:block;">Résolution supportée</label>
          <select name="{role}_mode" data-role="{role}">{mode_options(sc, selected_mode, selected_rate, role)}</select>
          {identification(selected_output)}
        </div>
        """

    # Les resolutions de chaque sortie, pour que le choix d'un ecran mette la
    # liste a jour sans aller-retour serveur.
    modes_par_sortie = json.dumps(
        {
            sc["output"]: [
                {"valeur": f'{item["mode"]}@{r}' if r else item["mode"],
                 "libelle": f'{item["mode"]} {r}Hz' if r else item["mode"]}
                for item in sc.get("modes", [])
                for r in item.get("rates", [""])
            ]
            for sc in screens
        },
        ensure_ascii=False,
    )

    cab_checked = "checked" if cfg.get("cabinet_mode", True) else ""
    land_sel = "selected" if cfg.get("playfield_orientation", "landscape") == "landscape" else ""
    port_sel = "selected" if cfg.get("playfield_orientation") == "portrait" else ""
    rot = str(cfg.get("playfield_rotation", "0"))

    body = f"""
    <h1>Assignation écrans</h1>
    <p>Sélectionne manuellement le Playfield / Primary, Backglass / Secondary, FullDMD / Tertiary — et le Topper pour les cabinets à 4 écrans — avec une résolution supportée par chaque écran.</p>

    <form method="post" action="/screen/save">
      <div class="grid">
        <script id="pco-modes" type="application/json">{modes_par_sortie}</script>
        <script>
        // PINCABOS_SCREEN_PAGE_TRUTH_V1 — a la selection d'un ecran, on
        // reconstruit la liste de ses resolutions. Le choix courant est
        // conserve s'il existe encore sur la nouvelle sortie.
        (function () {{
          var modes = JSON.parse(document.getElementById('pco-modes').textContent);
          function relier(role) {{
            var sortie = document.querySelector('select[name="' + role + '_output"]');
            var resolution = document.querySelector('select[name="' + role + '_mode"]');
            if (!sortie || !resolution) return;
            sortie.addEventListener('change', function () {{
              var garde = resolution.value;
              var liste = modes[sortie.value] || [];
              resolution.innerHTML = '<option value="">-- Auto / inchangé --</option>';
              liste.forEach(function (m) {{
                var o = document.createElement('option');
                o.value = m.valeur;
                o.textContent = m.libelle;
                if (m.valeur === garde) o.selected = true;
                resolution.appendChild(o);
              }});
            }});
          }}
          ['playfield', 'backglass', 'fulldmd'].forEach(relier);
        }})();
        </script>
        {role_card("playfield", "Playfield / Primary")}
        {role_card("backglass", "Backglass / Secondary")}
        {role_card("fulldmd", "FullDMD / Tertiary")}
        {role_card("topper", "Topper / Quaternary (optionnel)")}
      </div>

      <div class="card">
        <h3>Options PinCab</h3>
        <label><input type="checkbox" name="cabinet_mode" value="1" {cab_checked} style="width:auto;"> Cabinet Mode</label>

        <div class="grid" style="margin-top:12px;">
          <div>
            <label>Playfield Orientation</label>
            <select name="playfield_orientation">
              <option value="landscape" {land_sel}>Landscape</option>
              <option value="portrait" {port_sel}>Portrait</option>
            </select>
          </div>
          <div>
            <label>Playfield Rotation</label>
            <select name="playfield_rotation">
              <option value="0" {"selected" if rot == "0" else ""}>0</option>
              <option value="90" {"selected" if rot == "90" else ""}>90</option>
              <option value="180" {"selected" if rot == "180" else ""}>180</option>
              <option value="270" {"selected" if rot == "270" else ""}>270</option>
            </select>
          </div>
        </div>

        <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:16px;">
          <button type="submit">Sauvegarder assignation</button>
          <button formaction="/screen/apply-system" formmethod="post" type="submit">Appliquer résolutions système</button>
          <button formaction="/screen/apply-vpinfe" formmethod="post" type="submit">Appliquer à VPinFE</button>
          <button formaction="/screen/apply-vpx" formmethod="post" type="submit">Appliquer à VPX</button>
          <button formaction="/screen/apply-all" formmethod="post" type="submit">Appliquer tout + redémarrer VPinFE</button>
          <a class="button secondary" href="/gpu">Retour GPU</a>
        </div>
      </div>
    </form>

    <div class="card">
      <h3>Détection xrandr</h3>
      <pre>{esc(raw)}</pre>
    </div>

    <div class="card">
      <h3>Config actuelle</h3>
      <pre>{esc(json.dumps(cfg, indent=2, ensure_ascii=False))}</pre>
    </div>
    """
    return page_wrap("Assignation écrans", body)


# PINCABOS_SCREEN_IDENTIFY_V1
IDENTIFIER = Path("/opt/pincabos/bin/pincabos-identifier-ecran")


@screen_bp.route("/screen/identify", methods=["GET", "POST"])
def identifier_ecran():
    """Affiche son nom sur un ecran physique.

    Aucun privilege : la session X appartient a pinball, comme la webapp.
    La sortie demandee est confrontee a celles que le systeme declare, pour
    ne jamais transmettre une valeur venue telle quelle de l'exterieur.
    """
    sortie = (request.args.get("output") or request.form.get("output") or "").strip()
    connues = {sc["output"] for sc in parse_xrandr(xrandr_query())}

    if sortie in connues and IDENTIFIER.is_file():
        run_cmd([str(IDENTIFIER), sortie], timeout=10)

    return redirect(url_for("screen.screen_page"))


@screen_bp.route("/screen/save", methods=["POST"])
def screen_save():
    write_from_form(request.form)
    return redirect(url_for("screen.screen_page"))


@screen_bp.route("/screen/apply-system", methods=["POST"])
def screen_apply_system():
    write_from_form(request.form)
    rc, out = run_cmd(["/usr/bin/sudo", "-n", str(XRANDR_HELPER), "apply"], timeout=30)
    body = f"<h1>Appliquer résolutions système</h1><div class='card'><pre>{esc(out)}</pre></div><a class='button' href='/screen'>Retour</a>"
    return page_wrap("Apply system screens", body), (200 if rc == 0 else 500)


@screen_bp.route("/screen/apply-vpinfe", methods=["POST"])
def screen_apply_vpinfe():
    write_from_form(request.form)
    out = apply_vpinfe()
    body = f"<h1>Appliquer à VPinFE</h1><div class='card'><pre>{esc(out)}</pre></div><a class='button' href='/screen'>Retour</a>"
    return page_wrap("Apply VPinFE screens", body)


@screen_bp.route("/screen/apply-vpx", methods=["POST"])
def screen_apply_vpx():
    write_from_form(request.form)
    out = apply_vpx()
    body = f"<h1>Appliquer à VPX</h1><div class='card'><pre>{esc(out)}</pre></div><a class='button' href='/screen'>Retour</a>"
    return page_wrap("Apply VPX screens", body)


@screen_bp.route("/screen/apply-all", methods=["POST"])
def screen_apply_all():
    write_from_form(request.form)
    rc, sysout = run_cmd(["/usr/bin/sudo", "-n", str(XRANDR_HELPER), "apply"], timeout=30)
    vpinfe = apply_vpinfe()
    vpx = apply_vpx()
    rcrc, restart = run_cmd(["/usr/bin/sudo", "-n", "/bin/systemctl", "restart", "pincabos-vpinfe.service"], timeout=20)
    out = (
        "===== SYSTEM / XRANDR =====\n" + sysout +
        "\n\n===== VPinFE =====\n" + vpinfe +
        "\n\n===== VPX =====\n" + vpx +
        "\n\n===== RESTART VPinFE =====\n" + restart
    )
    ok = rc == 0 and rcrc == 0
    body = f"<h1>Appliquer tout</h1><div class='card'><pre>{esc(out)}</pre></div><a class='button' href='/screen'>Retour</a>"
    return page_wrap("Apply all screens", body), (200 if ok else 500)
