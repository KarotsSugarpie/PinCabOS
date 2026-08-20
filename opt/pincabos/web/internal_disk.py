"""Page de gestion du disque interne dedie aux tables.

PINCABOS_INTERNAL_DISK_PAGE_V1

Beaucoup de proprietaires rangent leurs tables sur un disque separe, souvent
formate en NTFS parce qu'il a d'abord servi sous Windows. Cette page permet
de l'adopter comme bibliotheque.

Le mecanisme retenu est le montage LIE et non le lien symbolique : de nombreux
composants codent /home/pinball/Tables en dur, et plusieurs valident les
chemins par resolve(strict=True).relative_to(TABLES_ROOT). Un lien symbolique
resout vers le disque et fait echouer ces controles ; un montage lie laisse
les chemins inchanges, si bien qu'aucun composant n'a a changer.

Tout le travail privilegie passe par /usr/local/sbin/pincabos-internal-disk,
qui refuse le disque systeme et les supports amovibles.
"""
from __future__ import annotations

import html
import json
import subprocess
from pathlib import Path

from flask import Blueprint, redirect, request, url_for

internal_disk_bp = Blueprint("internal_disk", __name__)

AIDE = "/usr/local/sbin/pincabos-internal-disk"
TABLES = Path("/home/pinball/Tables")


def esc(v) -> str:
    return html.escape("" if v is None else str(v), quote=True)


def aide(*args: str, timeout: int = 60) -> tuple[int, str]:
    try:
        p = subprocess.run(
            ["/usr/bin/sudo", "-n", AIDE, *args],
            text=True, capture_output=True, timeout=timeout, check=False,
        )
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as e:  # noqa: BLE001
        return 99, f"Commande indisponible : {e}"


def taille_lisible(octets) -> str:
    try:
        n = float(octets)
    except (TypeError, ValueError):
        return ""
    for unite in ("o", "Ko", "Mo", "Go", "To"):
        if n < 1024 or unite == "To":
            return f"{n:.0f} {unite}" if unite == "o" else f"{n:.1f} {unite}"
        n /= 1024
    return ""


def page(titre: str, corps: str) -> str:
    # PINCABOS_INTERNAL_DISK_THEME_V1
    #
    # L'application expose son propre gabarit : menu, entete, pied de page.
    # S'en passer donnait une page correcte mais visiblement etrangere au
    # reste de l'interface. On l'emprunte quand il existe, et on garde le
    # rendu autonome ci-dessous pour les appels hors application.
    import sys as _sys

    for _nom in ("app", "__main__"):
        _module = _sys.modules.get(_nom)
        _gabarit = getattr(_module, "page", None) if _module else None
        if callable(_gabarit):
            try:
                return _gabarit(titre, corps)
            except TypeError:
                pass
            except Exception:
                pass

    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>PinCabOS — {esc(titre)}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="/static/pincabos-theme-global.css">
<style>
 body {{ font-family: Arial, sans-serif; background:#12101a; color:#eee; padding:18px; }}
 .card {{ background:#1c1a26; border:1px solid #322e40; border-radius:8px;
          padding:16px; margin-bottom:16px; }}
 h1,h2,h3 {{ color:#ffb43b; }}
 table {{ border-collapse:collapse; width:100%; }}
 td,th {{ padding:7px 9px; border-bottom:1px solid #322e40; text-align:left; }}
 .button {{ display:inline-block; background:#ffb43b; color:#201a10; padding:8px 14px;
            border:0; border-radius:5px; text-decoration:none; cursor:pointer; font-weight:600; }}
 .button.secondary {{ background:#3a3550; color:#eee; }}
 .avert {{ color:#ffcf7a; }}
 pre {{ background:#0e0d14; padding:10px; border-radius:6px; overflow-x:auto; }}
</style></head><body>
<h1>{esc(titre)}</h1>
{corps}
<p style="margin-top:22px;"><a class="button secondary" href="/tools/external-disks">Retour aux disques</a></p>
</body></html>"""


def bloc_etat() -> str:
    _, etat = aide("status")
    lie = "Tables" in etat and "dossier local" not in etat
    resume = ("<p>La bibliothèque de tables est actuellement servie par un disque dédié.</p>"
              if lie else
              "<p>Les tables sont dans le dossier local du cabinet.</p>")
    return f"""<div class="card"><h2>État</h2>{resume}<pre>{esc(etat.strip())}</pre>
      <form method="post" action="/tools/internal-disk/release"
            onsubmit="return confirm('Libérer le disque ? Les tables redeviendront celles du dossier local.');">
        <button class="button secondary" type="submit">Libérer le disque</button>
      </form></div>"""


@internal_disk_bp.route("/tools/internal-disk", methods=["GET"])
def page_disque():
    rc, sortie = aide("list")
    try:
        partitions = json.loads(sortie) if rc == 0 else []
    except json.JSONDecodeError:
        partitions = []

    if not partitions:
        corps = bloc_etat() + """<div class="card"><h2>Aucun disque interne disponible</h2>
          <p>Aucune partition interne exploitable n'a été détectée. Sont volontairement
          exclus le disque système, les supports amovibles — qui relèvent de la page des
          clés USB — et les partitions sans système de fichiers ou sans identifiant stable.</p></div>"""
        return page("Disque interne", corps)

    lignes = "".join(
        f"""<tr><td><strong>{esc(p.get('label') or p['device'])}</strong><br>
             <small>{esc(p['device'])} — {esc(p['fstype'])} — {esc(taille_lisible(p.get('size')))}</small></td>
            <td>{'<em>déjà monté sur ' + esc(p['mountpoint']) + '</em>' if p.get('mountpoint') else ''}</td>
            <td><form method="post" action="/tools/internal-disk/probe">
                  <input type="hidden" name="uuid" value="{esc(p['uuid'])}">
                  <button class="button" type="submit">Explorer</button>
                </form></td></tr>"""
        for p in partitions
    )

    corps = bloc_etat() + f"""<div class="card"><h2>Disques internes détectés</h2>
      <p>Choisis le disque qui contient tes tables, puis le dossier à utiliser.
      Le NTFS est pris en charge&nbsp;: il sera monté aux droits du compte du cabinet,
      sans quoi le frontend ne pourrait rien y écrire.</p>
      <table><tbody>{lignes}</tbody></table></div>"""
    return page("Disque interne", corps)


@internal_disk_bp.route("/tools/internal-disk/probe", methods=["POST"])
def explorer():
    uuid = (request.form.get("uuid") or "").strip()
    if not uuid:
        return page("Disque interne", '<div class="card"><p>Disque non précisé.</p></div>'), 400

    rc, sortie = aide("probe", uuid)
    try:
        donnees = json.loads(sortie)
    except json.JSONDecodeError:
        return page("Disque interne", f"""<div class="card"><h2>Lecture impossible</h2>
          <pre>{esc(sortie.strip())}</pre></div>"""), 500

    dossiers = donnees.get("dossiers", [])
    if not dossiers:
        options = '<option value="">— racine du disque —</option>'
    else:
        options = '<option value="">— racine du disque —</option>' + "".join(
            f'<option value="{esc(d["nom"])}">{esc(d["nom"])}'
            + (f' — {d["tables"]} table(s)' if d.get("tables") else "")
            + "</option>"
            for d in dossiers
        )

    tables_presentes = any(TABLES.iterdir()) if TABLES.is_dir() else False
    # PINCABOS_INTERNAL_DISK_DEPLACER_V1
    # Une installation fraiche livre des tables d'exemple : le dossier n'est
    # donc presque jamais vide, et refuser sans proposer d'issue renvoyait
    # chaque proprietaire a la ligne de commande.
    combien = len(list(TABLES.iterdir())) if TABLES.is_dir() else 0
    avertissement = (f"""<p class="avert"><strong>Attention&nbsp;:</strong> le dossier de tables
      actuel contient déjà {combien} élément(s). Un montage lié les rendrait invisibles
      sans les effacer, ce qui laisserait croire à une perte&nbsp;: l'adoption les déplace
      donc vers le disque, ou refuse.</p>
      <p><label><input type="checkbox" name="deplacer" value="1" required>
      <strong>Déplacer ces {combien} élément(s) vers le disque</strong></label><br>
      <small>Ils sont transférés dans le dossier choisi ci-dessus, sans copie ni
      suppression. Si un nom existe déjà des deux côtés, rien n'est déplacé et
      l'opération s'interrompt.</small></p>""" if tables_presentes else "")

    corps = f"""<div class="card"><h2>Choix du dossier</h2>
      <p>Les dossiers de ce disque sont listés avec le nombre de tables qu'ils contiennent,
      pour que le bon se reconnaisse au premier coup d'œil.</p>
      {avertissement}
      <form method="post" action="/tools/internal-disk/adopt">
        <input type="hidden" name="uuid" value="{esc(uuid)}">
        <label>Dossier des tables</label><br>
        <select name="sous_dossier" style="min-width:320px;padding:6px;">{options}</select>
        <p style="margin-top:14px;">
          <label><input type="checkbox" name="au_demarrage" value="1" checked>
          Monter automatiquement au démarrage</label><br>
          <small>Décoché, le montage ne vaut que jusqu'au prochain redémarrage.
          Coché, une entrée est ajoutée dans <code>fstab</code> avec l'option
          <code>nofail</code>&nbsp;: un disque débranché n'empêchera jamais le cabinet de démarrer.</small>
        </p>
        <button class="button" type="submit">Adopter ce disque</button>
      </form></div>"""
    return page("Disque interne", corps)


@internal_disk_bp.route("/tools/internal-disk/adopt", methods=["POST"])
def adopter():
    uuid = (request.form.get("uuid") or "").strip()
    sous = (request.form.get("sous_dossier") or "").strip()
    boot = request.form.get("au_demarrage")
    if not uuid:
        return page("Disque interne", '<div class="card"><p>Disque non précisé.</p></div>'), 400

    args = ["adopt", uuid, sous]
    if boot:
        args.append("--boot")
    if request.form.get("deplacer"):
        args.append("--deplacer")
    rc, sortie = aide(*args, timeout=120)

    titre = "Disque adopté" if rc == 0 else "Adoption refusée"
    suite = ("""<p>Le frontend doit être redémarré pour relire sa bibliothèque.</p>
      <form method="post" action="/tools/internal-disk/restart-frontend">
        <button class="button" type="submit">Redémarrer le frontend</button>
      </form>""" if rc == 0 else "")

    return page("Disque interne", f"""<div class="card"><h2>{esc(titre)}</h2>
      <pre>{esc(sortie.strip())}</pre>{suite}</div>"""), (200 if rc == 0 else 500)


# PINCABOS_INTERNAL_DISK_RESTART_V1
#
# /service-control se termine par redirect(request.referrer). Appele depuis
# une page nee d'un POST, il y renvoyait le navigateur en GET — methode que
# cette route refuse, d'ou un « Method Not Allowed » alors que le service
# redemarrait correctement. On redirige donc vers une page consultable.
@internal_disk_bp.route("/tools/internal-disk/restart-frontend", methods=["POST"])
def redemarrer_frontend():
    import subprocess as _sp

    from flask import redirect as _redirect

    try:
        _sp.Popen(
            ["/usr/bin/sudo", "/usr/bin/systemctl", "restart", "pincabos-vpinfe.service"],
            stdout=_sp.DEVNULL,
            stderr=_sp.DEVNULL,
        )
    except Exception:
        pass
    return _redirect("/tools/internal-disk")


@internal_disk_bp.route("/tools/internal-disk/release", methods=["POST"])
def liberer():
    rc, sortie = aide("release", timeout=60)
    return page("Disque interne", f"""<div class="card"><h2>Disque libéré</h2>
      <pre>{esc(sortie.strip())}</pre>
      <p>Les tables redeviennent celles du dossier local du cabinet.</p></div>"""), (200 if rc == 0 else 500)
