"""Page web de mise a jour de vpxtool, sur le modele de la page VPinFE.

PINCABOS_VPXTOOL_UPDATE_UI_V1

Le moteur est l'updater autonome /opt/pincabos/tools/pincabos-vpxtool-update
(--status / --install / --rollback), declenche via sudo -n (le compte pinball,
qui fait tourner le webapp, y est autorise par etc/sudoers.d/pincabos-vpxtool-
updates). L'installation ne prend que quelques secondes (~7 Mo), donc l'action
est synchrone : plus simple et plus robuste que la machinerie asynchrone, tout
en offrant la meme experience — statut, boutons, journal.
"""
from __future__ import annotations

import json
import subprocess

from flask import jsonify, request

UPDATER = "/opt/pincabos/tools/pincabos-vpxtool-update"


def _status() -> dict:
    try:
        r = subprocess.run(["sudo", "-n", UPDATER, "--status"],
                           capture_output=True, text=True, timeout=30)
        data = json.loads((r.stdout or "").strip() or "{}")
        if not isinstance(data, dict):
            return {"error": "reponse inattendue"}
        return data
    except Exception as exc:
        return {"error": str(exc)}


def _run(action: str) -> tuple[int, str]:
    flag = {"install": "--install", "rollback": "--rollback"}[action]
    r = subprocess.run(["sudo", "-n", UPDATER, flag],
                       capture_output=True, text=True, timeout=300)
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()


_BODY = """
<div style="max-width:720px;margin:0 auto;font-family:system-ui,sans-serif;">
  <h1 style="font-size:1.4rem;">Mise a jour de vpxtool</h1>
  <p style="opacity:.8;">Moteur des mods <code>.dif</code> / VPU Remix utilise par l'import.</p>

  <div id="carte" style="border:1px solid #3a3a3a;border-radius:10px;padding:16px;margin:16px 0;background:#1c1c1c;">
    <div id="etat">Lecture de l'etat...</div>
  </div>

  <div style="display:flex;gap:10px;flex-wrap:wrap;">
    <button id="btn-install" style="padding:10px 16px;border-radius:8px;border:0;background:#2d6cdf;color:#fff;font-weight:600;cursor:pointer;">Installer / Mettre a jour</button>
    <button id="btn-rollback" style="padding:10px 16px;border-radius:8px;border:1px solid #666;background:transparent;color:#ddd;cursor:pointer;">Revenir a la version precedente</button>
  </div>

  <pre id="journal" style="margin-top:16px;padding:12px;background:#111;border-radius:8px;min-height:2.5em;white-space:pre-wrap;overflow:auto;"></pre>
</div>

<script>
const etat = document.getElementById('etat');
const journal = document.getElementById('journal');
const bInstall = document.getElementById('btn-install');
const bRollback = document.getElementById('btn-rollback');

function rendreEtat(s) {
  if (s.error) { etat.innerHTML = '<span style="color:#e66">Erreur : ' + s.error + '</span>'; return; }
  const inst = s.installed || 'aucune';
  const cible = s.target || '?';
  const ajour = s.up_to_date;
  etat.innerHTML =
    '<div>Version installee : <b>' + inst + '</b></div>' +
    '<div>Version cible : <b>' + cible + '</b></div>' +
    '<div style="margin-top:6px;color:' + (ajour ? '#5fbf5f' : '#e0a94b') + '">' +
    (ajour ? 'A jour' : 'Mise a jour disponible') + '</div>';
  bInstall.textContent = (s.installed && ajour) ? 'Reinstaller' : (s.installed ? 'Mettre a jour' : 'Installer');
}

async function charger() {
  try { const r = await fetch('/api/vpxtool-updates/state'); rendreEtat(await r.json()); }
  catch (e) { etat.textContent = 'Etat indisponible : ' + e; }
}

async function lancer(action) {
  bInstall.disabled = bRollback.disabled = true;
  journal.textContent = 'Operation en cours...';
  try {
    const r = await fetch('/api/vpxtool-updates/run', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({action})
    });
    const d = await r.json();
    journal.textContent = (d.output || '') + '\\n\\n' + (d.ok ? '[OK]' : '[ECHEC rc=' + d.rc + ']');
    if (d.state) rendreEtat(d.state);
  } catch (e) { journal.textContent = 'Erreur : ' + e; }
  finally { bInstall.disabled = bRollback.disabled = false; }
}

bInstall.onclick = () => lancer('install');
bRollback.onclick = () => lancer('rollback');
charger();
</script>
"""


def register(app, page):
    @app.get("/tools/vpxtool/update")
    def pincabos_vpxtool_updates_page():
        return page("Update vpxtool", _BODY)

    @app.get("/api/vpxtool-updates/state")
    def pincabos_vpxtool_updates_state():
        return jsonify(_status())

    @app.post("/api/vpxtool-updates/run")
    def pincabos_vpxtool_updates_run():
        payload = request.get_json(silent=True) or {}
        action = payload.get("action") or request.form.get("action")
        if action not in ("install", "rollback"):
            return jsonify({"ok": False, "error": "action invalide"}), 400
        rc, out = _run(action)
        return jsonify({"ok": rc == 0, "rc": rc, "output": out,
                        "state": _status()})
