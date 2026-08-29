"""Page de mise a jour de VPX-BGFX (telechargement lourd, donc asynchrone).

PINCABOS_VPX_UPDATE_UI_V1

Le moteur est /opt/pincabos/tools/pincabos-vpx-update (--status/--install/
--rollback). L'asset BGFX linux x64 pese ~150 Mo : l'install tourne donc en
tache de fond (compte pinball, qui possede ~/vpx), et la page suit la
progression via un journal. Rien pour les releases 'DO NOT USE' : l'updater ne
les propose jamais.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
from pathlib import Path

from flask import jsonify

UPDATER = "/opt/pincabos/tools/pincabos-vpx-update"
RUN = Path("/run/pincabos-vpx-update")
LOG = RUN / "log"
PIDF = RUN / "pid"


def _status() -> dict:
    try:
        r = subprocess.run([UPDATER, "--status"], capture_output=True,
                           text=True, timeout=45)
        d = json.loads((r.stdout or "").strip() or "{}")
    except Exception as exc:
        d = {"installed": None, "available": None, "up_to_date": None,
             "ok": False, "error": str(exc)}
    d["running"] = _running()
    try:
        d["log"] = LOG.read_text(encoding="utf-8", errors="replace")[-4000:]
    except Exception:
        d["log"] = ""
    return d


def _running() -> bool:
    try:
        pid = int(PIDF.read_text())
    except Exception:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _lancer(action: str) -> bool:
    if _running():
        return False
    RUN.mkdir(parents=True, exist_ok=True)
    log = LOG.open("w")
    proc = subprocess.Popen([UPDATER, action], stdout=log,
                            stderr=subprocess.STDOUT, start_new_session=True)
    PIDF.write_text(str(proc.pid))
    return True


_BODY = """
<div style="max-width:720px;margin:0 auto;font-family:system-ui,sans-serif;">
  <h1 style="font-size:1.4rem;">Mise à jour de VPX-BGFX</h1>
  <p style="opacity:.8;">Moteur Visual Pinball X (build BGFX). Le téléchargement fait ~150 Mo.</p>
  <div id="carte" style="border:1px solid #3a3a3a;border-radius:10px;padding:16px;margin:16px 0;background:#1c1c1c;">
    <div id="etat">Lecture de l'état…</div>
  </div>
  <div style="display:flex;gap:10px;flex-wrap:wrap;">
    <button id="btn-install" style="padding:10px 16px;border-radius:8px;border:0;background:#2d6cdf;color:#fff;font-weight:600;cursor:pointer;">Mettre à jour</button>
    <button id="btn-rollback" style="padding:10px 16px;border-radius:8px;border:1px solid #666;background:transparent;color:#ddd;cursor:pointer;">Version précédente</button>
  </div>
  <pre id="journal" style="margin-top:16px;padding:12px;background:#111;border-radius:8px;min-height:2.5em;white-space:pre-wrap;overflow:auto;max-height:280px;"></pre>
</div>
<script>
const etat=document.getElementById('etat'),journal=document.getElementById('journal');
const bI=document.getElementById('btn-install'),bR=document.getElementById('btn-rollback');
let poll=null;
function rendre(s){
  if(s.error){etat.innerHTML='<span style="color:#e66">Erreur : '+s.error+'</span>';}
  else{
    const ajour=s.up_to_date;
    etat.innerHTML='<div>Version installée : <b>'+(s.installed||'—')+'</b></div>'
      +'<div>Dernière disponible : <b>'+(s.available||'—')+'</b></div>'
      +'<div style="margin-top:6px;color:'+(ajour?'#5fbf5f':'#e0a94b')+'">'
      +(s.running?'Opération en cours…':(ajour?'À jour':'Mise à jour disponible'))+'</div>';
    bI.textContent=(s.installed&&ajour)?'Réinstaller':'Mettre à jour';
  }
  bI.disabled=bR.disabled=!!s.running;
  if(s.log!==undefined) journal.textContent=s.log;
  if(s.running && !poll){ poll=setInterval(charger,2000); }
  if(!s.running && poll){ clearInterval(poll); poll=null; }
}
async function charger(){try{const r=await fetch('/api/vpx-updates/state',{cache:'no-store'});rendre(await r.json());}catch(e){etat.textContent='État indisponible : '+e;}}
async function lancer(action){bI.disabled=bR.disabled=true;journal.textContent='Démarrage…';
  try{await fetch('/api/vpx-updates/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action})});}catch(e){}
  setTimeout(charger,800);}
bI.onclick=()=>lancer('install');bR.onclick=()=>lancer('rollback');charger();
</script>
"""


def register(app, page):
    @app.get("/tools/vpx/update")
    def pincabos_vpx_updates_page():
        return page("Update VPX-BGFX", _BODY)

    @app.get("/api/vpx-updates/state")
    def pincabos_vpx_updates_state():
        return jsonify(_status())

    @app.post("/api/vpx-updates/run")
    def pincabos_vpx_updates_run():
        from flask import request
        action = (request.get_json(silent=True) or {}).get("action")
        if action not in ("install", "rollback"):
            return jsonify({"ok": False, "error": "action invalide"}), 400
        lance = _lancer(action)
        return jsonify({"ok": lance, "running": _running(),
                        "error": None if lance else "operation deja en cours"})
