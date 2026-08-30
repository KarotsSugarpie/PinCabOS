"""Onglet unique des mises a jour : OS, VPinFE, vpxtool et VPX.

PINCABOS_UPDATES_HUB_V2

Les mises a jour etaient eclatees : une tuile/page par composant (PinCabOS,
VPinFE, vpxtool, VPX). Ce hub les rassemble en une seule vue. Il ne
reimplemente rien : il lit l'etat agrege ecrit par pincabos-updates-check
(rafraichi par un timer), et route chaque composant vers sa page de gestion
existante, qui garde ses propres garde-fous.

Le fichier d'etat est lu tel quel (instantane, hors ligne). Le bouton
'Verifier maintenant' relance l'agregateur cote serveur (compte pinball, qui
possede /opt/pincabos/state).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from flask import jsonify

ETAT = Path("/opt/pincabos/state/updates-available.json")
AGREGATEUR = "/opt/pincabos/tools/pincabos-updates-check"

# Chaque composant renvoie vers sa page de gestion canonique.
PAGES = {
    "pincabos": "/tools/updates",
    "vpinfe": "/tools/vpinfe/update",
    "vpxtool": "/tools/vpxtool/update",
    "vpx": "/tools/vpx/update",
}


def _etat() -> dict:
    try:
        return json.loads(ETAT.read_text(encoding="utf-8"))
    except Exception:
        return {"components": [], "any_update": False, "generated_at": None}


def _rafraichir() -> dict:
    try:
        subprocess.run([AGREGATEUR], capture_output=True, text=True, timeout=90)
    except Exception:
        pass
    return _etat()


_BODY = """
<div style="max-width:820px;margin:0 auto;font-family:system-ui,sans-serif;">
  <h1 style="font-size:1.4rem;">Mises à jour</h1>
  <p style="opacity:.8;">Tous les composants PinCabOS au même endroit.</p>

  <div style="display:flex;justify-content:flex-end;margin:10px 0;">
    <button id="btn-check" style="padding:8px 14px;border-radius:8px;border:1px solid #666;background:transparent;color:#ddd;cursor:pointer;">Vérifier maintenant</button>
  </div>

  <table style="width:100%;border-collapse:collapse;background:#1c1c1c;border-radius:10px;overflow:hidden;">
    <thead>
      <tr style="text-align:left;background:#242424;">
        <th style="padding:10px 12px;">Composant</th>
        <th style="padding:10px 12px;">Installée</th>
        <th style="padding:10px 12px;">Disponible</th>
        <th style="padding:10px 12px;">État</th>
        <th style="padding:10px 12px;"></th>
      </tr>
    </thead>
    <tbody id="lignes"><tr><td colspan="5" style="padding:14px 12px;opacity:.7;">Lecture de l'état…</td></tr></tbody>
  </table>

  <p id="maj-date" style="opacity:.55;font-size:.85rem;margin-top:10px;"></p>
</div>

<script>
const PAGES = {"pincabos":"/tools/updates","vpinfe":"/tools/vpinfe/update","vpxtool":"/tools/vpxtool/update","vpx":"/tools/vpx/update"};
const tbody = document.getElementById("lignes");
const btn = document.getElementById("btn-check");
const majDate = document.getElementById("maj-date");

function esc(s){ return String(s==null?"":s).replace(/[&<>\"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;"}[c])); }

function rendre(data){
  const comps = (data && data.components) || [];
  if(!comps.length){ tbody.innerHTML = '<tr><td colspan="5" style="padding:14px 12px;opacity:.7;">État indisponible — cliquez « Vérifier maintenant ».</td></tr>'; return; }
  tbody.innerHTML = comps.map(c=>{
    const href = c.manage_url || PAGES[c.key] || "";
    const externe = /^https?:/.test(href);
    const cible = externe ? ' target="_blank" rel="noopener"' : '';
    let etat;
    if(!c.ok) etat = '<span style="color:#e0a94b">vérification impossible</span>';
    else if(c.update_available) etat = '<span style="color:#e0a94b;font-weight:600">● Mise à jour disponible</span>';
    else etat = '<span style="color:#5fbf5f">À jour</span>';
    let bouton = "";
    if(href){
      const label = c.update_available ? (externe ? "Voir la build" : "Mettre à jour") : (externe ? "Voir la release" : "Gérer");
      const style = c.update_available ? 'background:#2d6cdf;color:#fff;font-weight:600;' : 'border:1px solid #555;color:#ccc;';
      bouton = '<a href="'+href+'"'+cible+' style="padding:6px 12px;border-radius:8px;text-decoration:none;'+style+'">'+label+'</a>';
    }
    return '<tr style="border-top:1px solid #333;">'
      + '<td style="padding:10px 12px;font-weight:600;">'+esc(c.name)+'</td>'
      + '<td style="padding:10px 12px;">'+esc(c.installed||"—")+'</td>'
      + '<td style="padding:10px 12px;">'+esc(c.available||"—")+'</td>'
      + '<td style="padding:10px 12px;">'+etat+'</td>'
      + '<td style="padding:10px 12px;text-align:right;">'+bouton+'</td>'
      + '</tr>';
  }).join("");
  if(data.generated_at) majDate.textContent = "Dernière vérification : " + esc(data.generated_at);
}

async function charger(){
  try{ const r = await fetch("/api/updates-all/state",{cache:"no-store"}); rendre(await r.json()); }
  catch(e){ tbody.innerHTML = '<tr><td colspan="5" style="padding:14px 12px;">Erreur : '+esc(e)+'</td></tr>'; }
}

btn.onclick = async ()=>{
  btn.disabled = true; const t = btn.textContent; btn.textContent = "Vérification…";
  try{ const r = await fetch("/api/updates-all/check",{method:"POST"}); rendre(await r.json()); }
  catch(e){ /* on garde l'affichage courant */ }
  finally{ btn.disabled = false; btn.textContent = t; }
};

charger();
</script>
"""


def register(app, page):
    @app.get("/tools/updates-all")
    def pincabos_updates_hub_page():
        return page("Mises à jour", _BODY)

    @app.get("/api/updates-all/state")
    def pincabos_updates_hub_state():
        return jsonify(_etat())

    @app.post("/api/updates-all/check")
    def pincabos_updates_hub_check():
        return jsonify(_rafraichir())
