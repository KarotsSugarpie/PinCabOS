"""Page WebApp « Tables : identification VPS et diagnostic ».

PINCABOS_VPS_V1 — voir opt/pincabos/tools/pincabos_vps.py (le moteur). Cette
page ne fait que l'appeler : liste des tables avec leur identifiant VPS, ce
qui manque (ROM, pack, B2S, POV, couleurs), choix manuel quand plusieurs
entrees VPS se ressemblent, rafraichissement de la base.
"""
from __future__ import annotations

import sys
from pathlib import Path

from flask import redirect, request

# le moteur vit dans /opt/pincabos/tools ; ce fichier porte un autre nom
# (pincabos_webapp_vps) pour ne pas se masquer lui-meme a l'import.
sys.path.insert(0, "/opt/pincabos/tools")
import pincabos_vps as vps  # noqa: E402


def _safe_dir(name: str) -> Path | None:
    """Un dossier de table = un nom simple sous la racine des tables, rien d'autre."""
    name = (name or "").strip()
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        return None
    d = (vps.TABLES_ROOT / name)
    try:
        if d.resolve().parent != vps.TABLES_ROOT.resolve() or not d.is_dir():
            return None
    except OSError:
        return None
    return d


def register(app, page, esc):
    def _badge(text, kind):
        colors = {"ok": "#2e7d4f", "warn": "#a8720e", "bad": "#b23a3a", "info": "#5b6b7f"}
        return f'<span style="display:inline-block;padding:1px 7px;border-radius:3px;border:1px solid {colors[kind]};color:{colors[kind]};font-size:.8em;white-space:nowrap;">{esc(text)}</span>'

    def _rom_badge(diag):
        r = diag["rom"]
        if r["status"] == "ok" and not r["warnings"]:
            return _badge("ROM " + ", ".join(r["present"]), "ok")
        if r["status"] == "ok":
            return _badge("ROM incomplete ?", "warn")
        if r["status"] == "absente":
            return _badge("ROM absente : " + ", ".join(r["expected"][:2]), "bad")
        if r["status"] == "non referencee":
            return _badge("ROM non referencee", "warn")
        return _badge("sans ROM (DMD logiciel)", "info")

    def _pack_badge(diag):
        p = diag["pup"]
        if not p["root"]:
            return _badge("pas de pack", "info") if not p["vps_count"] else _badge(f"pack dispo ({p['vps_count']})", "info")
        if not p["packs"] and not p["screens_at_root"]:
            return _badge("pack sans screens.pup", "bad")
        if p["alias_ok"] is False:
            return _badge("pack : nom ≠ ROM (lien pose)", "warn")
        return _badge("pack OK", "ok")

    def _simple_badge(section, label):
        if section["present"]:
            return _badge(label + " OK", "ok")
        if section["vps_count"]:
            return _badge(f"{label} dispo ({section['vps_count']})", "info")
        return _badge(label + " —", "info")

    def _head(notice=""):
        st = vps.db_status()
        base = (f"Base VPS : <b>{st['entries']}</b> tables, telechargee il y a <b>{st['age_days']}</b> j"
                + (" — <span class='warn'>a rafraichir</span>" if st.get("stale") else "")) if st["present"] else "<span class='warn'>Base VPS absente : clique « Rafraichir la base ».</span>"
        return f"""
<div class="card">
  <h2>Tables : identification VPS et diagnostic</h2>
  <p>Chaque table est rattachee a sa fiche <a href="https://virtualpinballspreadsheet.github.io/" target="_blank" rel="noopener">Virtual Pinball Spreadsheet</a>,
  ce qui permet de dire avant de lancer ce qui manque : ROM attendue, pack PuP complet et bien nomme, B2S, POV, couleurs alternatives.
  L'identifiant est ecrit dans le manifeste de la table (<code>pincabos-table-manifest.json</code>, champ <code>vpsid</code>). Rien n'est modifie dans les ini.</p>
  <p>{base}</p>
  <form method="post" action="/tables/vps/refresh" style="display:inline"><button class="button" type="submit">Rafraichir la base</button></form>
  <form method="post" action="/tables/vps/identify" style="display:inline;margin-left:8px"><button class="button" type="submit">Identifier toutes les tables</button></form>
</div>
{notice}"""

    def _rows_html(rows):
        out = ['<div class="card" style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:.92em">',
               '<tr><th style="text-align:left;padding:6px">Table</th><th style="text-align:left;padding:6px">Fiche VPS</th><th style="text-align:left;padding:6px">Etat</th><th style="text-align:left;padding:6px"></th></tr>']
        for r in rows:
            e = r.get("entry") or {}
            if r["status"] == "ok":
                fiche = f'<a href="{esc(e["url"])}" target="_blank" rel="noopener"><code>{esc(e["id"])}</code></a> {esc(e["name"])} ({esc(str(e.get("manufacturer") or ""))} {esc(str(e.get("year") or ""))})' + (" " + _badge("a confirmer", "warn") if r["how"] == "nom approchant" else "")
            elif r["status"] == "ambigu":
                fiche = _badge(f"{len(r['candidates'])} fiches possibles", "warn") + f' <a class="button" href="/tables/vps/choose?dir={esc(r["folder"])}">Choisir</a>'
            else:
                fiche = _badge("aucune fiche", "bad") + f' <a class="button" href="/tables/vps/choose?dir={esc(r["folder"])}">Chercher</a>'
            d = r["diag"]
            etat = " ".join([_rom_badge(d), _pack_badge(d), _simple_badge(d["b2s"], "B2S"), _simple_badge(d["pov"], "POV"), _simple_badge(d["altcolor"], "couleurs")])
            if d.get("broken"):
                etat += " " + _badge("broken (VPS)", "bad")
            out.append(f'<tr style="border-top:1px solid rgba(255,255,255,.15)"><td style="padding:6px;vertical-align:top"><b>{esc(r["folder"])}</b></td>'
                       f'<td style="padding:6px;vertical-align:top">{fiche}</td><td style="padding:6px;vertical-align:top">{etat}</td>'
                       f'<td style="padding:6px;vertical-align:top"><a class="button" href="/tables/vps/table?dir={esc(r["folder"])}">Detail</a></td></tr>')
        out.append("</table></div>")
        return "".join(out)

    @app.route("/tables/vps")
    def vps_index():
        db = vps.load_db()
        if not db:
            return page("Tables VPS", _head())
        rows = vps.scan_tables(vps.TABLES_ROOT, db)
        nb_ok = sum(1 for r in rows if r["status"] == "ok")
        pbs = sum(len(r["problemes"]) for r in rows)
        notice = f'<div class="card"><p><b>{len(rows)}</b> tables, <b>{nb_ok}</b> identifiees, <b>{pbs}</b> probleme(s) detecte(s).</p></div>'
        return page("Tables VPS", _head(notice) + _rows_html(rows))

    @app.route("/tables/vps/refresh", methods=["POST"])
    def vps_refresh():
        try:
            r = vps.refresh(force=True)
            notice = f'<div class="card"><p>Base VPS {esc(r["reason"])} : {r["entries"]} tables.</p></div>'
        except Exception as exc:
            notice = f'<div class="card"><p class="warn">Telechargement impossible : {esc(str(exc))}</p></div>'
        db = vps.load_db()
        rows = vps.scan_tables(vps.TABLES_ROOT, db) if db else []
        return page("Tables VPS", _head(notice) + (_rows_html(rows) if rows else ""))

    @app.route("/tables/vps/identify", methods=["POST"])
    def vps_identify():
        db = vps.load_db()
        if not db:
            return redirect("/tables/vps")
        rows = vps.scan_tables(vps.TABLES_ROOT, db, apply=True)
        ecrits = sum(1 for r in rows if r.get("applied"))
        amb = sum(1 for r in rows if r["status"] == "ambigu")
        notice = f'<div class="card"><p>Identification faite : <b>{ecrits}</b> manifeste(s) mis a jour' + (f', <b>{amb}</b> table(s) a choisir a la main.' if amb else ".") + "</p></div>"
        return page("Tables VPS", _head(notice) + _rows_html(rows))

    @app.route("/tables/vps/table")
    def vps_table():
        d = _safe_dir(request.args.get("dir", ""))
        if d is None:
            return redirect("/tables/vps")
        db = vps.load_db()
        res = vps.identify(d, db)
        entry = vps.entry_by_id(db, res["entry"]["id"]) if res.get("entry") else None
        diag = vps.diagnostic(d, entry, res.get("rom", ""))
        pbs = vps.problemes(diag)
        e = res.get("entry") or {}

        def liste(files, vide):
            if not files:
                return f"<i>{vide}</i>"
            items = []
            for f in files:
                lib = esc(" / ".join(f.get("authors") or []) or f.get("version") or f.get("id") or "fichier")
                items.append(f'<li>{(f"<a href=\"{esc(f['url'])}\" target=\"_blank\" rel=\"noopener\">{lib}</a>" if f.get("url") else lib)}'
                             + (f' <span style="opacity:.7">{esc(str(f.get("version") or ""))}</span>' if f.get("version") and f.get("authors") else "") + "</li>")
            return "<ul>" + "".join(items) + "</ul>"

        ident = (f'<p>Fiche VPS : <a href="{esc(e["url"])}" target="_blank" rel="noopener"><code>{esc(e["id"])}</code></a> <b>{esc(e["name"])}</b> ({esc(str(e.get("manufacturer") or ""))} {esc(str(e.get("year") or ""))}) — rattachee par <i>{esc(res["how"])}</i>'
                 + (f' · IPDB {esc(e["ipdbid"])}' if e.get("ipdbid") else "") + "</p>") if e else \
            f'<p class="warn">Aucune fiche VPS rattachee. <a class="button" href="/tables/vps/choose?dir={esc(d.name)}">Chercher</a></p>'
        body = _head() + f"""
<div class="card">
  <h2>{esc(d.name)}</h2>
  {ident}
  {"<p class='warn'>" + "<br>".join(esc(p) for p in pbs) + "</p>" if pbs else "<p>Aucun probleme detecte.</p>"}
  <h3>ROM</h3>
  <p>Attendue par VPS : <code>{esc(", ".join(diag["rom"]["expected"]) or "aucune (table originale a DMD logiciel)")}</code><br>
     Presente dans <code>pinmame/roms</code> : <code>{esc(", ".join(diag["rom"]["present"]) or "aucune")}</code>
     {"".join(f"<br>{esc(s)}.zip : {n} fichier(s)" for s, n in diag["rom"]["zip_files"].items())}</p>
  {liste(diag["rom"]["vps"], "")}
  <h3>PuP-Pack</h3>
  <p>{("Dossier <code>" + esc(diag["pup"]["root"]) + "</code> · packs : " + esc(", ".join(diag["pup"]["packs"]) or ("screens.pup a la racine" if diag["pup"]["screens_at_root"] else "aucun screens.pup"))) if diag["pup"]["root"] else "Aucun pack installe."}
     {" · nom du pack ≠ ROM, le lanceur pose un lien <code>pupvideos/&lt;ROM&gt;</code>" if diag["pup"]["alias_ok"] is False else ""}</p>
  <p>Packs connus de VPS ({diag["pup"]["vps_count"]}) :</p>{liste(diag["pup"]["vps"], "aucun")}
  <h3>B2S</h3>
  <p>Present : <code>{esc(", ".join(diag["b2s"]["present"]) or "non")}</code> · connus de VPS : {diag["b2s"]["vps_count"]}</p>{liste(diag["b2s"]["vps"], "")}
  <h3>POV</h3>
  <p>Present : <code>{esc(", ".join(diag["pov"]["present"]) or "non")}</code> · connus de VPS : {diag["pov"]["vps_count"]}</p>{liste(diag["pov"]["vps"], "")}
  <h3>Couleurs alternatives (Serum / altcolor)</h3>
  <p>Present : <b>{"oui" if diag["altcolor"]["present"] else "non"}</b> · connus de VPS : {diag["altcolor"]["vps_count"]}</p>{liste(diag["altcolor"]["vps"], "")}
  <p>Versions VPX connues de VPS : <code>{esc(", ".join(diag["vpx_versions"]) or "-")}</code></p>
  <p><a class="button" href="/tables/vps">Retour a la liste</a></p>
</div>"""
        return page("Tables VPS", body)

    @app.route("/tables/vps/choose", methods=["GET", "POST"])
    def vps_choose():
        d = _safe_dir(request.values.get("dir", ""))
        if d is None:
            return redirect("/tables/vps")
        db = vps.load_db()
        if request.method == "POST":
            vpsid = (request.form.get("vpsid") or "").strip()
            entry = vps.entry_by_id(db, vpsid)
            if entry:
                res = {"status": "ok", "entry": vps._summary(entry), "how": "choix manuel"}
                vps.apply_manifest(d, res, force=True, confirmed=True)
            return redirect(f"/tables/vps/table?dir={d.name}")
        q = (request.args.get("q") or "").strip()
        res = vps.identify(d, db)
        cands = res["candidates"]
        if q:
            n = vps.normalize(q)
            cands = [vps._summary(t) for t in db if n and n in vps.normalize(t.get("name", ""))][:30]
        opts = "".join(f'<label style="display:block;padding:4px 0"><input type="radio" name="vpsid" value="{esc(c["id"])}"> <b>{esc(c["name"])}</b> ({esc(str(c.get("manufacturer") or ""))} {esc(str(c.get("year") or ""))}) <a href="{esc(c["url"])}" target="_blank" rel="noopener">fiche</a></label>' for c in cands)
        body = _head() + f"""
<div class="card">
  <h2>Choisir la fiche VPS de « {esc(d.name)} »</h2>
  <form method="get" action="/tables/vps/choose"><input type="hidden" name="dir" value="{esc(d.name)}">
    <input type="text" name="q" value="{esc(q)}" placeholder="Chercher un titre dans la base VPS" style="width:60%;padding:6px"> <button class="button" type="submit">Chercher</button></form>
  <form method="post" action="/tables/vps/choose"><input type="hidden" name="dir" value="{esc(d.name)}">
    {opts or "<p><i>Aucune fiche proposee : utilise la recherche.</i></p>"}
    {"<p><button class='button' type='submit'>Rattacher cette fiche</button></p>" if opts else ""}
  </form>
  <p><a class="button" href="/tables/vps">Retour</a></p>
</div>"""
        return page("Tables VPS", body)

    @app.route("/api/vps/tables")
    def vps_api_tables():
        from flask import jsonify
        db = vps.load_db()
        return jsonify({"db": vps.db_status(), "tables": vps.scan_tables(vps.TABLES_ROOT, db) if db else []})
