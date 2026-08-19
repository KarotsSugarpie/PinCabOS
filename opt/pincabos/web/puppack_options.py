# PINCABOS_PUPPACK_PAGE_V1
#
# Page "PuP-Packs" : choisir la disposition d'ecrans d'un PuP-Pack.
#
# Les packs sont livres non configures et le choix se fait, sous Windows,
# en lancant un "Option N.bat" qui recopie les *.pup de la variante retenue
# a la racine du pack. Cette page fait la meme chose, en montrant ce que
# chaque option vise reellement et en signalant celles qui demandent un
# ecran absent du cabinet.
#
# Aucun privilege : les tables appartiennent a pinball, comme la webapp.

from __future__ import annotations

import html
import json
import re
import subprocess
import sys
from pathlib import Path

from flask import Blueprint, current_app, redirect, request, url_for

puppack_bp = Blueprint("puppack", __name__)

OUTIL = Path("/opt/pincabos/bin/pincabos-puppack-option")
TABLES_ROOT = Path("/home/pinball/Tables")
PUP_DIR_NAMES = {"pupvideos", "pupvideo", "pinupvideo", "pinupvideos"}

ETIQUETTES = {
    "playfield": "Plateau",
    "backglass": "Fronton",
    "fulldmd": "FullDMD",
    "topper": "Topper",
}


def esc(valeur) -> str:
    return html.escape("" if valeur is None else str(valeur), quote=True)


def outil(*arguments, attendu_json: bool = True):
    try:
        resultat = subprocess.run(
            [sys.executable, str(OUTIL), *arguments],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=60,
        )
    except Exception as erreur:  # noqa: BLE001
        return None, f"Erreur d'appel : {erreur}"

    if not attendu_json:
        return resultat.stdout, ""

    try:
        return json.loads(resultat.stdout), ""
    except ValueError:
        return None, resultat.stdout.strip() or "Sortie illisible."


def page_wrap(titre: str, corps: str):
    for nom in ("app", "__main__"):
        module = sys.modules.get(nom)
        fonction = getattr(module, "page", None) if module else None
        if callable(fonction):
            try:
                return fonction(titre, corps)
            except TypeError:
                pass
            except Exception:  # noqa: BLE001
                pass

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{esc(titre)}</title>
<link rel="stylesheet" href="/static/pincabos-branding.css">
<link rel="stylesheet" href="/static/pincabos-global-compact.css">
<style>
body{{font-family:system-ui;margin:24px;background:#14001f;color:#fff}}
.card{{background:#220033;border:1px solid rgba(255,138,0,.35);border-radius:18px;padding:18px;margin:14px 0}}
.button,button{{background:#ff8a00;color:#000;border:0;border-radius:10px;padding:10px 14px;font-weight:800;cursor:pointer;text-decoration:none;display:inline-block}}
.secondary{{background:#3a164d;color:#fff}}
select,input{{background:#110019;color:#fff;border:1px solid rgba(255,255,255,.25);border-radius:10px;padding:9px}}
.alerte{{border-color:rgba(255,80,80,.6);background:#33000f}}
.option{{border:1px solid rgba(255,255,255,.18);border-radius:14px;padding:12px;margin:10px 0}}
.option.reco{{border-color:rgba(255,138,0,.75)}}
.marque{{font-size:.8em;font-weight:800;border-radius:999px;padding:2px 9px;margin-left:8px}}
.m-reco{{background:#ff8a00;color:#000}}
.m-inst{{background:#2f7d32;color:#fff}}
.m-inc{{background:#5a1a1a;color:#ffbcbc}}
.notice{{opacity:.75;white-space:pre-wrap;margin:6px 0 0}}
</style></head><body>{corps}</body></html>"""


def bandeau_surfaces(surfaces: list[str]) -> str:
    if not surfaces:
        return "aucune surface"
    return ", ".join(ETIQUETTES.get(s, s) for s in surfaces)


# Les styles voyagent avec le contenu : lorsque le theme de PinCabOS fournit
# le gabarit, la feuille de secours de ce module n'est jamais chargee. Le
# prefixe evite aussi de heurter les classes du theme — « notice » y designe
# deja les bulles d'information, ce qui expediait nos textes dans un coin de
# l'ecran.
STYLES = """<style>
.pcxpup-box{background:rgba(20,0,32,.55);border:1px solid rgba(255,138,0,.35);
  border-radius:16px;padding:16px 18px;margin:14px 0}
.pcxpup-box.alerte{border-color:rgba(255,95,95,.6);background:rgba(60,0,18,.5)}
.pcxpup-box h2{margin:0 0 10px;font-size:1.15em}
.pcxpup-meta{opacity:.75;margin:4px 0;font-size:.94em}
.pcxpup-chemin{opacity:.45;font-size:.82em;word-break:break-all;margin-top:8px}
.pcxpup-opt{display:grid;grid-template-columns:auto 1fr;gap:12px;align-items:start;
  border:1px solid rgba(255,255,255,.14);border-radius:12px;padding:12px 14px;
  margin:10px 0;cursor:pointer}
.pcxpup-opt:hover{border-color:rgba(255,255,255,.3)}
.pcxpup-opt.reco{border-color:rgba(255,138,0,.7);background:rgba(255,138,0,.07)}
.pcxpup-titre{font-weight:800;line-height:1.5}
.pcxpup-tag{display:inline-block;font-size:.72em;font-weight:800;letter-spacing:.02em;
  border-radius:999px;padding:3px 10px;margin:0 0 0 8px;vertical-align:middle;
  white-space:nowrap}
.pcxpup-t-inst{background:#2f7d32;color:#fff}
.pcxpup-t-reco{background:#ff8a00;color:#1a0d00}
.pcxpup-t-part{background:#4a3410;color:#ffd9a0}
.pcxpup-t-non{background:#5a1a1a;color:#ffbcbc}
.pcxpup-surf{opacity:.8;font-size:.92em;margin-top:4px}
.pcxpup-texte{opacity:.65;font-size:.9em;margin:8px 0 0;white-space:pre-wrap;
  line-height:1.45}
.pcxpup-actions{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin-top:14px}
.pcxpup-bouton{background:#ff8a00;color:#1a0d00;border:0;border-radius:10px;
  padding:10px 16px;font-weight:800;cursor:pointer}
.pcxpup-bouton.discret{background:rgba(255,255,255,.12);color:#fff}
.pcxpup-choix{display:flex;gap:10px;align-items:flex-start;margin-top:6px}
.pcxpup-choix input{margin-top:3px}
</style>"""


def joli_nom(option: dict) -> str:
    """Nom d'option lisible : « Option 4 — PupPack onBG Topper on BG DMD »."""
    brut = option["id"]
    if option.get("numero"):
        brut = re.sub(r"^option[\s_-]*\d+[\s_-]*", "", brut, flags=re.I)
        return f"Option {option['numero']} — {brut.replace('_', ' ').strip()}"
    return brut.replace("_", " ")


@puppack_bp.route("/tools/puppack", methods=["GET"])
def puppack_page():
    tables, erreur = outil("list", "--json")
    if tables is None:
        corps = STYLES + f"<div class='pcxpup-box alerte'><h2>PuP-Packs</h2><pre>{esc(erreur)}</pre></div>"
        return page_wrap("PuP-Packs", corps)

    choisie = request.args.get("table", "")
    message = request.args.get("message", "")

    morceaux = [STYLES, "<h1>PuP-Packs</h1>"]

    if message:
        morceaux.append(f"<div class='pcxpup-box'><pre>{esc(message)}</pre></div>")

    non_configures = [
        t for t in tables if t.get("pack") and t.get("statut") in ("non-configure", "incompatible")
    ]
    if non_configures:
        noms = ", ".join(esc(t["nom"]) for t in non_configures)
        morceaux.append(
            "<div class='pcxpup-box alerte'>"
            "<h2>Packs non configurés</h2>"
            "<p>Ces tables possèdent un PuP-Pack dont aucun écran n'est actif. "
            "Tant qu'aucune disposition n'est choisie, le pack n'affiche rien — "
            "le fronton reste noir en mode PuP-Pack.</p>"
            f"<p><strong>{noms}</strong></p></div>"
        )

    if not tables:
        morceaux.append("<div class='pcxpup-box'><p>Aucune table ne possède de PuP-Pack.</p></div>")
        return page_wrap("PuP-Packs", "".join(morceaux))

    liste_tables = []
    for entree in tables:
        marque = "" if entree.get("configure") else "   (non configuré)"
        selection = " selected" if entree["table"] == choisie else ""
        liste_tables.append(
            f"<option value='{esc(entree['table'])}'{selection}>"
            f"{esc(entree['nom'])}{esc(marque)}</option>"
        )

    morceaux.append(
        "<div class='pcxpup-box'><h2>Table</h2>"
        "<form method='get' action='/tools/puppack'>"
        "<select name='table' onchange='this.form.submit()'>"
        "<option value=''>— choisir une table —</option>"
        + "".join(liste_tables)
        + "</select> <noscript><button class='pcxpup-bouton' type='submit'>Afficher</button>"
        "</noscript></form></div>"
    )

    if not choisie:
        return page_wrap("PuP-Packs", "".join(morceaux))

    etat, erreur = outil("show", choisie, "--json")
    if etat is None:
        morceaux.append(f"<div class='pcxpup-box alerte'><pre>{esc(erreur)}</pre></div>")
        return page_wrap("PuP-Packs", "".join(morceaux))

    statut = etat.get("statut", "")
    if statut == "ok":
        resume = f"Pack configuré — {bandeau_surfaces(etat.get('surfaces', []))}"
    elif statut == "partiel":
        resume = (
            f"Pack configuré — {bandeau_surfaces(etat.get('visibles', []))} s'affiche ; "
            f"{bandeau_surfaces(etat.get('manquantes', []))} n'existe pas sur ce cabinet."
        )
    elif statut == "incompatible":
        resume = (
            "Ce pack ne vise que des écrans absents "
            f"({bandeau_surfaces(etat.get('manquantes', []))}) : rien ne s'affichera."
        )
    else:
        resume = "Pack non configuré : aucun écran actif."

    classe = "pcxpup-box" if statut in ("ok", "partiel") else "pcxpup-box alerte"
    coche_pup = " checked" if etat.get("pup_obligatoire") else ""
    morceaux.append(
        f"<div class='{classe}'><h2>{esc(etat.get('nom', ''))}</h2>"
        f"<p class='pcxpup-meta'>{esc(resume)}</p>"
        f"<p class='pcxpup-meta'>Écrans de ce cabinet : "
        f"{esc(bandeau_surfaces(etat.get('cabinet', [])))}</p>"
        "<form method='post' action='/tools/puppack/mode'>"
        f"<input type='hidden' name='table' value='{esc(choisie)}'>"
        "<label class='pcxpup-choix'>"
        f"<input type='checkbox' name='obligatoire' value='oui'{coche_pup} "
        "onchange='this.form.submit()'>"
        "<span>Cette table ne fonctionne pas sans son PuP-Pack — la lancer "
        "directement, sans proposer le choix Original au démarrage.</span></label>"
        "<noscript><button class='pcxpup-bouton' type='submit'>Appliquer</button></noscript>"
        "</form>"
        f"<div class='pcxpup-chemin'>{esc(etat.get('pack', ''))}</div></div>"
    )

    options = etat.get("options", [])
    if not options:
        morceaux.append(
            "<div class='pcxpup-box'><p>Ce pack ne propose pas de variantes : "
            "il s'utilise tel qu'il est livré.</p></div>"
        )
        return page_wrap("PuP-Packs", "".join(morceaux))

    blocs = []
    for option in options:
        etiquettes = ""
        if option.get("installee"):
            etiquettes += "<span class='pcxpup-tag pcxpup-t-inst'>installée</span>"
        if option.get("recommandee"):
            etiquettes += "<span class='pcxpup-tag pcxpup-t-reco'>recommandée</span>"
        if not option.get("utilisable"):
            etiquettes += "<span class='pcxpup-tag pcxpup-t-non'>aucun écran disponible</span>"
        elif option.get("manquantes"):
            absents = bandeau_surfaces(option["manquantes"])
            etiquettes += f"<span class='pcxpup-tag pcxpup-t-part'>{esc(absents)} inutilisé</span>"

        coche = " checked" if option.get("installee") else ""
        texte = option.get("description", "")
        blocs.append(
            f"<label class='pcxpup-opt{' reco' if option.get('recommandee') else ''}'>"
            f"<input type='radio' name='option' value='{esc(option['id'])}'{coche}>"
            "<span>"
            f"<span class='pcxpup-titre'>{esc(joli_nom(option))}</span>{etiquettes}"
            f"<div class='pcxpup-surf'>Surfaces utilisées : "
            f"{esc(bandeau_surfaces(option.get('surfaces', [])))}</div>"
            + (f"<div class='pcxpup-texte'>{esc(texte)}</div>" if texte else "")
            + "</span></label>"
        )

    restauration = ""
    if etat.get("sauvegarde"):
        restauration = (
            "<button class='pcxpup-bouton discret' type='submit' "
            "form='pcxpup-restaurer'>Revenir à l'état d'origine</button>"
        )

    morceaux.append(
        "<div class='pcxpup-box'><h2>Disposition d'écrans</h2>"
        "<form method='post' action='/tools/puppack/apply'>"
        f"<input type='hidden' name='table' value='{esc(choisie)}'>"
        + "".join(blocs)
        + "<div class='pcxpup-actions'>"
        "<button class='pcxpup-bouton' type='submit'>Installer cette disposition</button>"
        + restauration
        + "</div></form>"
        "<form id='pcxpup-restaurer' method='post' action='/tools/puppack/restore'>"
        f"<input type='hidden' name='table' value='{esc(choisie)}'></form>"
        "</div>"
    )

    return page_wrap("PuP-Packs", "".join(morceaux))


@puppack_bp.route("/tools/puppack/mode", methods=["POST"])
def puppack_mode():
    table = request.form.get("table", "")
    if not table:
        return redirect(url_for("puppack.puppack_page"))

    voulu = "oui" if request.form.get("obligatoire") else "non"
    sortie, erreur = outil("pup-obligatoire", table, voulu, attendu_json=False)
    return redirect(
        url_for("puppack.puppack_page", table=table, message=(sortie or erreur or "").strip())
    )


@puppack_bp.route("/tools/puppack/apply", methods=["POST"])
def puppack_apply():
    table = request.form.get("table", "")
    option = request.form.get("option", "")
    if not table or not option:
        return redirect(url_for("puppack.puppack_page", table=table, message="Choisissez une option."))

    sortie, erreur = outil("apply", table, option, attendu_json=False)
    return redirect(url_for("puppack.puppack_page", table=table, message=(sortie or erreur or "").strip()))


@puppack_bp.route("/tools/puppack/restore", methods=["POST"])
def puppack_restore():
    table = request.form.get("table", "")
    if not table:
        return redirect(url_for("puppack.puppack_page"))

    sortie, erreur = outil("restore", table, attendu_json=False)
    return redirect(url_for("puppack.puppack_page", table=table, message=(sortie or erreur or "").strip()))


# ------------------------------------------------------- bouton dans l'Explorateur
#
# Le proprietaire qui vient d'importer un pack se trouve dans son dossier,
# pas dans un menu Outils. On lui met le choix des ecrans sous la main, et
# seulement la ou cela a un sens : dans un dossier de PuP-Pack.


def table_du_dossier(dossier: Path) -> Path | None:
    """Table a laquelle appartient ce dossier de pack."""
    courant = dossier
    for _ in range(6):
        if courant == TABLES_ROOT or courant.parent == courant:
            return None
        try:
            vpx = sorted(courant.glob("*.vpx"))
        except OSError:
            vpx = []
        if vpx:
            return vpx[0]
        courant = courant.parent
    return None


def dossier_de_pack(chemin: Path) -> bool:
    if not chemin.is_dir():
        return False
    if (chemin / "screens.pup").is_file():
        return True
    if chemin.name.casefold() in PUP_DIR_NAMES:
        return True
    try:
        return any(
            enfant.is_dir() and enfant.name.casefold().replace(" ", "").startswith("pup-pack_option")
            for enfant in chemin.iterdir()
        )
    except OSError:
        return False


def banniere_pour(chemin_relatif: str) -> str:
    try:
        dossier = (TABLES_ROOT / chemin_relatif.lstrip("/")).resolve(strict=True)
        dossier.relative_to(TABLES_ROOT.resolve())
    except (OSError, ValueError):
        return ""

    if not dossier_de_pack(dossier):
        return ""

    table = table_du_dossier(dossier)
    if table is None:
        return ""

    etat, _ = outil("show", str(table), "--json")
    statut = (etat or {}).get("statut", "")
    options = (etat or {}).get("options", [])

    if statut == "non-configure":
        texte = "Ce PuP-Pack n'est pas configure : aucun ecran actif, il n'affichera rien."
        classe = "pcx-pup-banner pcx-pup-alerte"
    elif statut == "incompatible":
        manquantes = bandeau_surfaces((etat or {}).get("manquantes", []))
        texte = f"Ce PuP-Pack ne vise que des ecrans absents ({manquantes}) : rien ne s'affichera."
        classe = "pcx-pup-banner pcx-pup-alerte"
    elif statut == "partiel":
        manquantes = bandeau_surfaces((etat or {}).get("manquantes", []))
        texte = f"PuP-Pack configure ; il prevoit aussi {manquantes}, absent de ce cabinet."
        classe = "pcx-pup-banner"
    elif not options:
        return ""
    else:
        installee = (etat or {}).get("option_installee", "") or "disposition personnalisee"
        texte = f"PuP-Pack configure — {installee}"
        classe = "pcx-pup-banner"

    lien = "/tools/puppack?table=" + html.escape(str(table), quote=True).replace(" ", "%20")
    return (
        f"<div class='{classe}' style=\"margin:10px 0;padding:12px 14px;border-radius:14px;"
        "border:1px solid rgba(255,138,0,.5);background:rgba(255,138,0,.08);"
        'display:flex;gap:12px;align-items:center;flex-wrap:wrap">'
        f"<span>{esc(texte)}</span>"
        f"<a class='button' href=\"{lien}\" style=\"background:#ff8a00;color:#000;border-radius:10px;"
        'padding:8px 12px;font-weight:800;text-decoration:none">Options d\'ecrans</a>'
        "</div>"
    )


ZONES_INERTES = (
    r"<!--.*?-->",
    r"<style\b[^>]*>.*?</style>",
    r"<script\b[^>]*>.*?</script>",
)


def ouverture_du_corps(corps: str) -> int:
    """Position juste apres la vraie balise d'ouverture du document.

    Les pages de PinCabOS parlent d'elles-memes : leurs commentaires HTML et
    leurs feuilles de style citent la balise <body> pour expliquer ou tel
    element doit s'ancrer. Se fier a la premiere occurrence textuelle place
    la banniere dans un commentaire, ou le navigateur l'ignore sans rien
    signaler — on l'a vu deux fois.

    On neutralise donc les zones ou une balise ne peut pas etre reelle, en
    conservant les positions, avant de chercher.
    """
    neutre = list(corps)
    for motif in ZONES_INERTES:
        for zone in re.finditer(motif, corps, re.I | re.S):
            for index in range(zone.start(), zone.end()):
                neutre[index] = " "

    neutre = "".join(neutre)
    trouve = re.search(r"<body\b[^>]*>", neutre, re.I)
    if not trouve:
        return -1
    depart = trouve.end()

    # On vise la liste des fichiers de l'Explorateur, nommement : une
    # premiere tentative sur le premier <table> venu cassait la mise en
    # page, ce tableau n'etant pas celui-la. La banniere se pose donc juste
    # au-dessus de la liste, dans le cadre, sous le chemin affiche.
    liste = re.search(
        r'<table\b[^>]*class="[^"]*\bpcx-table\b[^"]*"[^>]*>', neutre[depart:], re.I
    )
    if liste:
        return depart + liste.start()

    # Gabarit different : on reste en tete de corps plutot que de deviner.
    return depart


def install_puppack_explorer_button(app) -> str:
    """Injecte la banniere dans la vue Explorateur, sans toucher a son code."""
    endpoint = None
    for regle in app.url_map.iter_rules():
        if regle.rule == "/tools/commander" and "GET" in regle.methods:
            endpoint = regle.endpoint
            break
    if not endpoint:
        return "absent"

    original = app.view_functions.get(endpoint)
    if not original:
        return "absent"
    if getattr(original, "_pco_puppack_wrapped", False):
        return "deja"

    def enveloppe(*arguments, **nommes):
        reponse = current_app.make_response(original(*arguments, **nommes))

        if "text/html" not in reponse.headers.get("Content-Type", ""):
            return reponse

        try:
            banniere = banniere_pour(request.args.get("path", ""))
        except Exception:  # noqa: BLE001
            banniere = ""
        if not banniere:
            return reponse

        corps = reponse.get_data(as_text=True)
        position = ouverture_du_corps(corps)
        if position < 0:
            return reponse

        nouveau = corps[:position] + banniere + corps[position:]
        reponse.set_data(nouveau)
        reponse.headers["Content-Length"] = str(len(reponse.get_data()))
        return reponse

    enveloppe._pco_puppack_wrapped = True
    app.view_functions[endpoint] = enveloppe
    return "installe"
