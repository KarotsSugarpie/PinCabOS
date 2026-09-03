#!/usr/bin/env python3
"""Sous-page PinCabOS Link pour le runtime isolé VPX MultiPlayers."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from typing import Callable, Optional

from flask import Blueprint, Response, jsonify, make_response, request


PINFORGE_MODULE = "PINCABOS_LINK_VPX_MULTIPLAYERS_LAB_V1"
AGENT = "/opt/pincabos/apps/VPX_MultiPlayers/bin/pincabos-multiplayer-agent"
ROOM_CODE_PATTERN = re.compile(r"^[A-Z0-9]{6}$")
TABLE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ /-]{0,180}\.vpx$", re.I)
ALLOWED_ACTIONS = frozenset(
    {"create", "join", "prepare", "ready", "start", "launch", "stop"}
)

multiplayer_link_blueprint = Blueprint("pincaboslink_multiplayer_v1", __name__)
_page_renderer: Optional[Callable[[str, str], str]] = None
_csrf_validator: Optional[Callable[[], bool]] = None
_csrf_token = ""


def _normalize_room_code(value: object) -> str:
    return "".join(
        character
        for character in str(value or "").strip().upper()
        if character not in " -\t\r\n"
    )


def _agent_arguments(action: str, payload: dict) -> list[str]:
    if action not in ALLOWED_ACTIONS:
        raise ValueError("action_invalid")
    if action == "create":
        return ["create"]
    if action == "join":
        code = _normalize_room_code(payload.get("room_code"))
        if not ROOM_CODE_PATTERN.fullmatch(code):
            raise ValueError("room_code_invalid")
        return ["join", code]
    if action in {"prepare", "ready", "launch"}:
        table = str(payload.get("table") or "").strip()
        if not TABLE_PATTERN.fullmatch(table) or ".." in table.split("/"):
            raise ValueError("test_table_invalid")
        arguments = [action, table]
        if action == "launch":
            arguments.append("--detach")
        return arguments
    return [action]


def _run_agent(arguments: list[str]) -> tuple[dict, int]:
    if not os.path.isfile(AGENT) or not os.access(AGENT, os.X_OK):
        return {"ok": False, "error": "multiplayer_agent_not_installed"}, 503
    command = [AGENT, *arguments]
    if os.geteuid() != 0:
        sudo = shutil.which("sudo")
        if not sudo:
            return {"ok": False, "error": "sudo_unavailable"}, 503
        command = [sudo, "-n", *command]
    try:
        result = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=40,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "multiplayer_agent_timeout"}, 504
    except OSError:
        return {"ok": False, "error": "multiplayer_agent_unavailable"}, 503
    try:
        value = json.loads(result.stdout or "{}")
    except ValueError:
        return {"ok": False, "error": "multiplayer_agent_response_invalid"}, 502
    if not isinstance(value, dict):
        return {"ok": False, "error": "multiplayer_agent_response_invalid"}, 502
    if result.returncode != 0 or value.get("ok") is False:
        return value, 409
    return value, 200


def _body(csrf_token: str) -> str:
    return r"""
<style>
.pco-mp{display:grid;gap:16px}.pco-mp-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.pco-mp-actions{display:flex;gap:8px;flex-wrap:wrap}.pco-mp-input{min-height:44px;padding:10px 12px;border:1px solid rgba(255,122,0,.75);border-radius:9px;background:#090a11;color:#fff}.pco-mp-code{font:900 2rem/1 ui-monospace,monospace;letter-spacing:.16em;color:#ffb15c}.pco-mp-state{white-space:pre-wrap;overflow-wrap:anywhere}.pco-mp-mode{display:flex;gap:9px;flex-wrap:wrap}.pco-mp-mode button.active{border-color:#43d17b;color:#d4ffe1}.pco-mp-warn{color:#ffcb89}.pco-mp-ok{color:#7ef0a7}@media(max-width:850px){.pco-mp-grid{grid-template-columns:1fr}}
</style>
<section class="pco-mp" data-marker="PINCABOS_LINK_VPX_MULTIPLAYERS_LAB_V1">
  <div>
    <h1>VPX MultiPlayers — LAB</h1>
    <p>Runtime VPX séparé. Le VPX privé et VPinFE ne sont pas utilisés.</p>
  </div>
  <div class="card">
    <h2>Mode de la room</h2>
    <div class="pco-mp-mode">
      <button id="mp-score" class="button secondary" type="button">SCORE BATTLE</button>
      <button id="mp-live" class="button active" type="button">LIVE MULTIPLAYERS — LAB</button>
    </div>
    <div id="mp-mode-message" class="pco-mp-warn">Le LAB utilise uniquement le moteur isolé VPX_MultiPlayers.</div>
  </div>
  <div id="mp-live-panel" class="pco-mp-grid">
    <div class="card">
      <h2>Room et code</h2>
      <div id="mp-code" class="pco-mp-code">------</div>
      <div class="pco-mp-actions" style="margin-top:12px">
        <button id="mp-create" class="button" type="button">CRÉER / ACTIVER</button>
        <button id="mp-copy" class="button secondary" type="button" disabled>COPIER LE CODE</button>
      </div>
      <div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap">
        <input id="mp-room" class="pco-mp-input" maxlength="8" placeholder="ABC123" autocomplete="off">
        <button id="mp-join" class="button secondary" type="button">REJOINDRE</button>
      </div>
      <p class="pco-mp-warn">Les comptes doivent déjà être membres de la même room sur pincabos.cc.</p>
    </div>
    <div class="card">
      <h2>Moteur isolé</h2>
      <div id="mp-engine">Vérification...</div>
      <input id="mp-table" class="pco-mp-input" value="poc.vpx" aria-label="Table de test" style="width:100%;margin-top:12px">
      <div class="pco-mp-actions" style="margin-top:12px">
        <button data-action="prepare" class="button secondary" type="button">PRÉPARER</button>
        <button data-action="ready" class="button secondary" type="button">PRÊT</button>
        <button data-action="start" class="button" type="button">DÉMARRER</button>
        <button data-action="launch" class="button" type="button">LANCER LE MOTEUR</button>
        <button data-action="stop" class="button danger" type="button">ARRÊTER</button>
      </div>
    </div>
    <div class="card" style="grid-column:1/-1">
      <h2>État des cabinets</h2>
      <div id="mp-members" class="pco-mp-state">Aucune session active.</div>
      <div id="mp-message" class="pco-mp-state" style="margin-top:12px"></div>
    </div>
  </div>
</section>
<script>
(()=>{"use strict";
const CSRF="__CSRF_JS__",message=document.getElementById("mp-message");let current=null;
async function api(path,options={}){const method=options.method||"GET",headers=Object.assign({"Accept":"application/json"},options.headers||{});if(method!=="GET")headers["X-PinCabOS-Link-CSRF"]=CSRF;const response=await fetch(path,Object.assign({},options,{headers,cache:"no-store"}));let value={};try{value=await response.json();}catch(_e){}if(!response.ok||value.ok===false)throw new Error(value.error||("HTTP "+response.status));return value;}
function render(value){current=value;const runtime=value.local_runtime||{},session=value.session||null;document.getElementById("mp-engine").innerHTML=runtime.engine_ready?'<span class="pco-mp-ok">MOTEUR ISOLÉ PRÊT</span><br>'+String(runtime.engine_sha256||"").slice(0,16)+'…':'<span class="pco-mp-warn">MOTEUR ISOLÉ NON INSTALLÉ</span>';const code=session&&session.room_code?String(session.room_code):"";document.getElementById("mp-code").textContent=code||"------";document.getElementById("mp-copy").disabled=!code;const members=document.getElementById("mp-members");if(!session){members.textContent="Aucune session active.";return;}const lines=["PHASE: "+String(session.phase||"").toUpperCase()];(session.members||[]).forEach(item=>{const ready=!!item.ready_manifest_hash;const role=session.master_cabinet_id===item.cabinet_id?"MAÎTRE":"RÉPLIQUE";lines.push("J"+item.player_number+" · CAB "+item.cabinet_id+" · CONNECTÉ · "+(ready?"PACKAGE IDENTIQUE · MOTEUR PRÊT":"EN ATTENTE")+" · "+role);});members.textContent=lines.join("\n");}
async function refresh(){try{render(await api("/pincabos-link/api/multiplayer/status"));message.textContent="";}catch(e){message.textContent="NOGO — "+e.message;}}
async function action(name,extra={}){message.textContent="Commande "+name+"...";try{const value=await api("/pincabos-link/api/multiplayer/action",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(Object.assign({action:name},extra))});message.textContent="GO — "+name;await refresh();return value;}catch(e){message.textContent="NOGO — "+e.message;}}
document.getElementById("mp-create").onclick=()=>action("create");document.getElementById("mp-join").onclick=()=>action("join",{room_code:document.getElementById("mp-room").value});document.getElementById("mp-copy").onclick=async()=>{const code=current&&current.session&&current.session.room_code;if(code){await navigator.clipboard.writeText(code);message.textContent="Code copié : "+code;}};document.querySelectorAll("[data-action]").forEach(button=>button.onclick=()=>action(button.dataset.action,{table:document.getElementById("mp-table").value}));document.getElementById("mp-score").onclick=()=>{document.getElementById("mp-live-panel").hidden=true;document.getElementById("mp-score").classList.add("active");document.getElementById("mp-live").classList.remove("active");document.getElementById("mp-mode-message").textContent="Score Battle conserve son fonctionnement actuel; aucun moteur LAB n'est lancé.";};document.getElementById("mp-live").onclick=()=>{document.getElementById("mp-live-panel").hidden=false;document.getElementById("mp-live").classList.add("active");document.getElementById("mp-score").classList.remove("active");document.getElementById("mp-mode-message").textContent="Le LAB utilise uniquement le moteur isolé VPX_MultiPlayers.";};refresh();setInterval(refresh,3000);
})();
</script>
""".replace("__CSRF_JS__", json.dumps(csrf_token)[1:-1])


@multiplayer_link_blueprint.get("/pincabos-link/multiplayer")
def multiplayer_page() -> Response:
    if _page_renderer is None:
        return Response("WebApp renderer unavailable.", status=500)
    response = make_response(_page_renderer("VPX MultiPlayers — LAB", _body(_csrf_token)))
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@multiplayer_link_blueprint.get("/pincabos-link/api/multiplayer/status")
def multiplayer_status():
    payload, status = _run_agent(["status"])
    return jsonify(payload), status


@multiplayer_link_blueprint.post("/pincabos-link/api/multiplayer/action")
def multiplayer_action():
    if _csrf_validator is None or not _csrf_validator():
        return jsonify({"ok": False, "error": "invalid_csrf"}), 403
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "error": "json_required"}), 415
    try:
        arguments = _agent_arguments(str(payload.get("action") or ""), payload)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    value, status = _run_agent(arguments)
    return jsonify(value), status


def register_pincaboslink_multiplayer(
    app,
    page_renderer: Callable[[str, str], str],
    csrf_validator: Callable[[], bool],
    csrf_token: str,
) -> None:
    global _page_renderer, _csrf_validator, _csrf_token
    _page_renderer = page_renderer
    _csrf_validator = csrf_validator
    _csrf_token = csrf_token
    if multiplayer_link_blueprint.name not in app.blueprints:
        app.register_blueprint(multiplayer_link_blueprint)
