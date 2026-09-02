#!/usr/bin/env python3
"""Dedicated PinCabOS Link Backglass A/V window authorized by Lobby state."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable, Optional

from flask import Blueprint, Response, jsonify, request, send_file


PINFORGE_MODULE = "PINCABOS_LINK_LOBBY_AV_V1"
LIVEKIT_CLIENT_VERSION = "2.22.2"
SCREENS_FILE = Path("/opt/pincabos/config/screens/screens.json")
LIVE_CAPTURE_DIR = Path("/run/pincabos-dashboard-live")

lobby_av_blueprint = Blueprint("pincaboslink_lobby_av_v1", __name__)
_bridge_json: Optional[Callable] = None
_csrf_ok: Optional[Callable[[], bool]] = None
_display_action: Optional[Callable[[str], str]] = None
_csrf_token = ""


def _bridge(*args: str):
    if _bridge_json is None:
        return {"ok": False, "error": "bridge_unavailable"}, 500
    return _bridge_json(*args)


def _require_csrf():
    return bool(_csrf_ok and _csrf_ok())


def _backglass_preview_path() -> Path | None:
    try:
        config = json.loads(SCREENS_FILE.read_text(encoding="utf-8"))
    except Exception:
        config = {}

    backglass = config.get("backglass")
    screens = config.get("all_screens")
    slot = None

    if isinstance(backglass, dict):
        for key in ("slot", "index", "screen_index"):
            try:
                value = int(backglass.get(key))
            except (TypeError, ValueError):
                continue
            if 0 <= value <= 8:
                slot = value
                break

    if slot is None and isinstance(backglass, dict) and isinstance(screens, list):
        target = next(
            (
                str(backglass.get(key) or "")
                for key in ("output", "connector", "name", "display")
                if backglass.get(key)
            ),
            "",
        )
        if target:
            for index, screen in enumerate(screens):
                if not isinstance(screen, dict):
                    continue
                values = {
                    str(screen.get(key) or "")
                    for key in ("output", "connector", "name", "display")
                }
                if target in values:
                    slot = index
                    break

    # Cabinet de référence: playfield=0, backglass=1, FullDMD=2.
    # Le fallback reste une lecture seule et ne change aucune configuration.
    if slot is None:
        slot = 1

    path = LIVE_CAPTURE_DIR / f"screen{slot}.jpg"
    try:
        resolved = path.resolve(strict=True)
        root = LIVE_CAPTURE_DIR.resolve(strict=True)
    except OSError:
        return None
    if resolved.parent != root or not resolved.is_file():
        return None
    return resolved


def _lobby_av_html() -> str:
    return r'''<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PinCabOS Lobby Audio / Vidéo</title>
<style>
:root{color-scheme:dark;--bg:#05060b;--panel:#11141e;--line:#30364a;--orange:#ff7a18;--purple:#a970ff;--text:#f8f8fb;--muted:#aeb4c6;--green:#43d17b;--red:#ff6675}
*{box-sizing:border-box}
body{margin:0;height:100vh;overflow:hidden;background:radial-gradient(circle at 50% -20%,#331a51 0,transparent 42%),radial-gradient(circle at 5% 90%,#4b2008 0,transparent 38%),var(--bg);color:var(--text);font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
button,input{font:inherit}
.shell{height:100vh;display:grid;grid-template-rows:auto minmax(0,1fr) auto;gap:10px;padding:10px}
.bar{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;padding:10px 13px;border:1px solid var(--line);border-radius:12px;background:rgba(17,20,30,.96)}
.brand{font-size:1.1rem;font-weight:950}.brand .pin{color:var(--orange)}.brand .os{color:var(--purple)}
.status{color:var(--muted);font-size:.9rem}.actions{display:flex;gap:7px;align-items:center;flex-wrap:wrap}
button{min-height:38px;padding:0 13px;border:1px solid #4a5168;border-radius:9px;background:#222737;color:#fff;font-weight:850;cursor:pointer}
button.primary{border-color:#ff984f;background:#d85d08}button.good{border-color:#318651;background:#174c2c}button.danger{border-color:#7b3540;background:#481820}button:disabled{opacity:.42;cursor:not-allowed}
.grid{min-height:0;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));grid-template-rows:repeat(2,minmax(0,1fr));gap:10px}
.zone{position:relative;min-height:0;overflow:hidden;border:1px solid var(--line);border-radius:14px;background:linear-gradient(160deg,rgba(23,27,41,.97),rgba(8,10,16,.97))}
.zone.speaking{border-color:var(--orange);box-shadow:0 0 22px rgba(255,122,24,.38)}
.zone-title{position:absolute;z-index:4;left:9px;right:9px;top:8px;display:flex;justify-content:space-between;gap:8px;padding:6px 8px;border-radius:8px;background:rgba(0,0,0,.66);font-size:.78rem;font-weight:900}
.media{height:100%;display:grid;place-items:center;color:#81899e;font-weight:850;text-align:center;padding:45px 15px 15px}
.media video{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;background:#04050a}.media audio{display:none}
.guest-1{grid-column:1;grid-row:1}.guest-2{grid-column:2;grid-row:1}.guest-3{grid-column:3;grid-row:1}.lobby{grid-column:1;grid-row:2}.local{grid-column:2;grid-row:2}.b2s{grid-column:3;grid-row:2}
.lobby-content{height:100%;overflow:auto;padding:48px 13px 13px}.lobby-name{color:var(--orange);font-weight:950;font-size:1.08rem}.kv{display:grid;grid-template-columns:auto 1fr;gap:6px 10px;margin-top:10px;font-size:.88rem}.kv span:nth-child(odd){color:var(--muted)}
.members{display:grid;gap:5px;margin-top:10px}.member{display:flex;justify-content:space-between;gap:8px;padding:6px 8px;border-radius:7px;background:#1a1e2b;font-size:.82rem}.ready{color:var(--green)}.not-ready{color:#ffbc72}
.empty-room{display:grid;place-items:center;height:100%;padding:20px;color:var(--muted);text-align:center;font-weight:800}
.b2s img{width:100%;height:100%;object-fit:contain;background:#000}.b2s-note{position:absolute;left:9px;right:9px;bottom:8px;z-index:3;padding:5px 7px;border-radius:7px;background:rgba(0,0,0,.7);color:var(--muted);font-size:.72rem}
@media(max-width:1050px){.grid{grid-template-columns:repeat(2,minmax(0,1fr));grid-template-rows:repeat(3,minmax(0,1fr))}.guest-1{grid-column:1;grid-row:1}.guest-2{grid-column:2;grid-row:1}.guest-3{grid-column:1;grid-row:2}.lobby{grid-column:2;grid-row:2}.local{grid-column:1;grid-row:3}.b2s{grid-column:2;grid-row:3}}
</style>
</head>
<body>
<main class="shell">
  <header class="bar">
    <div><div class="brand"><span class="pin">Pin</span>Cab<span class="os">OS</span> Lobby A/V</div><div id="status" class="status">Synchronisation avec pincabos.cc...</div></div>
    <div class="actions">
      <button id="connect" class="primary" type="button" disabled>REJOINDRE L'APPEL</button>
      <button id="mic" type="button" disabled>MICRO OFF</button>
      <button id="cam" type="button" disabled>CAMÉRA OFF</button>
      <button id="hangup" class="danger" type="button" disabled>RACCROCHER</button>
      <button id="close" class="danger" type="button">FERMER</button>
    </div>
  </header>
  <section class="grid">
    <article id="guest1" class="zone guest-1"><div class="zone-title"><span>INVITÉ 1</span><span>EN ATTENTE</span></div><div class="media">SLOT DISTANT</div></article>
    <article id="guest2" class="zone guest-2"><div class="zone-title"><span>INVITÉ 2</span><span>EN ATTENTE</span></div><div class="media">SLOT DISTANT</div></article>
    <article id="guest3" class="zone guest-3"><div class="zone-title"><span>INVITÉ 3</span><span>EN ATTENTE</span></div><div class="media">SLOT DISTANT</div></article>
    <article class="zone lobby"><div class="zone-title"><span>LOBBY A/V</span><span id="roomState">HORS LIGNE</span></div><div id="lobby" class="lobby-content"><div class="empty-room">Rejoignez d'abord une room sur pincabos.cc.</div></div></article>
    <article id="local" class="zone local"><div class="zone-title"><span>JOUEUR LOCAL</span><span id="localMedia">MIC OFF · CAM OFF</span></div><div class="media">CAMÉRA DÉSACTIVÉE</div></article>
    <article class="zone b2s"><div class="zone-title"><span>B2S LOCAL</span><span>LECTURE SEULE</span></div><img id="b2s" alt="Aperçu Backglass local"><div class="b2s-note">Miroir local uniquement — VPX/BGFX/VPinFE intacts</div></article>
  </section>
  <footer class="bar">
    <div id="sync" class="status">La room pincabos.cc est consultée en lecture seule pour autoriser et ordonner les participants A/V.</div>
  </footer>
</main>
<script src="https://cdn.jsdelivr.net/npm/livekit-client@__LIVEKIT_VERSION__/dist/livekit-client.umd.min.js"></script>
<script>
(() => {
"use strict";
const CSRF="__CSRF__";
const state={room:null,av:null,lk:null,mic:false,cam:false};
const $=id=>document.getElementById(id);
const html=value=>String(value??"").replace(/[&<>"']/g,character=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[character]);

async function api(path,options){
  const supplied=options||{},method=String(supplied.method||"GET").toUpperCase(),headers=Object.assign({"Accept":"application/json"},supplied.headers||{});
  if(method!=="GET")headers["X-PinCabOS-Link-CSRF"]=CSRF;
  const response=await fetch(path,Object.assign({},supplied,{headers,cache:"no-store"}));
  let data={};try{data=await response.json();}catch(_error){}
  if(!response.ok||data.ok===false){const error=new Error(data.error||("HTTP "+response.status));error.code=data.error||("HTTP "+response.status);throw error;}
  return data;
}

function identity(userId){return "pincabos-user-"+Number(userId);}
function participant(userId){
  if(!state.lk)return null;
  const value=identity(userId);
  if(state.lk.localParticipant.identity===value)return state.lk.localParticipant;
  return state.lk.remoteParticipants.get(value)||null;
}
function resetZone(zone,label,status){zone.dataset.identity="";zone.classList.remove("speaking");zone.querySelector(".zone-title span:first-child").textContent=label;zone.querySelector(".zone-title span:last-child").textContent=status;const media=zone.querySelector(".media");media.replaceChildren("SLOT DISTANT");}
function attachParticipant(zone,member,isLocal){
  const p=participant(member.user_id);zone.dataset.identity=identity(member.user_id);
  zone.querySelector(".zone-title span:first-child").textContent=(isLocal?"JOUEUR LOCAL":"SLOT "+member.slot)+" — "+member.display_name;
  zone.querySelector(".zone-title span:last-child").textContent=p?"CONNECTÉ":"EN ATTENTE";
  const media=zone.querySelector(".media");media.replaceChildren(p?"MÉDIA DÉSACTIVÉ":"CONNEXION EN ATTENTE");
  if(!p)return;
  p.trackPublications.forEach(publication=>{
    if(!publication.track)return;
    publication.track.detach();
    const element=publication.track.attach();
    if(publication.kind==="video")media.replaceChildren(element);else zone.appendChild(element);
  });
}
function renderMedia(){
  const guests=[$("guest1"),$("guest2"),$("guest3")];
  guests.forEach((zone,index)=>resetZone(zone,"INVITÉ "+(index+1),"EN ATTENTE"));
  const local=$("local"),localMedia=local.querySelector(".media");local.dataset.identity="";localMedia.replaceChildren("CAMÉRA DÉSACTIVÉE");
  if(!state.room||!state.room.me)return;
  attachParticipant(local,state.room.me,true);
  state.room.members.filter(member=>Number(member.user_id)!==Number(state.room.me.user_id)).sort((a,b)=>a.slot-b.slot).slice(0,3).forEach((member,index)=>attachParticipant(guests[index],member,false));
}
function renderLobby(){
  const room=state.room,host=$("lobby");
  if(!room){
    host.innerHTML='<div class="empty-room">Rejoignez d\'abord une room sur pincabos.cc.</div>';
    $("roomState").textContent="HORS LIGNE";$("connect").disabled=true;renderMedia();return;
  }
  const members=room.members.map(member=>'<div class="member"><span>S'+Number(member.slot)+' · '+html(member.display_name)+' · '+html(member.cab_name)+'</span><strong>'+(Number(member.user_id)===Number(room.me&&room.me.user_id)?'LOCAL':'DISTANT')+'</strong></div>').join('');
  host.innerHTML='<div class="lobby-name">'+html(room.name)+' · '+html(room.code)+'</div><div class="kv"><span>Participants A/V</span><strong>'+Number(room.member_count)+' / '+Number(room.max_players)+'</strong></div><div class="members">'+members+'</div>';
  $("roomState").textContent="AUTORISÉ";$("connect").disabled=!!state.lk;
  renderMedia();
}
async function loadState(){
  try{const data=await api("/pincabos-link/api/lobby");state.room=data.room;$("status").textContent=state.room?"Autorisé · "+state.room.code:"Aucune room active";renderLobby();}
  catch(error){$("status").textContent="Synchronisation : "+error.code;}
}
function speakers(values){document.querySelectorAll(".zone.speaking").forEach(zone=>zone.classList.remove("speaking"));(values||[]).forEach(p=>{const zone=document.querySelector('.zone[data-identity="'+p.identity+'"]');if(zone)zone.classList.add("speaking");});}
async function connect(){
  if(!state.room||state.lk)return;
  if(!window.LivekitClient){$("status").textContent="SDK LiveKit indisponible";return;}
  try{
    const data=await api("/pincabos-link/api/lobby/av-token",{method:"POST",body:"{}",headers:{"Content-Type":"application/json"}}),LK=window.LivekitClient;
    state.av=data.av;state.lk=new LK.Room({adaptiveStream:true,dynacast:true});
    state.lk.on(LK.RoomEvent.ParticipantConnected,renderMedia).on(LK.RoomEvent.ParticipantDisconnected,renderMedia).on(LK.RoomEvent.TrackSubscribed,renderMedia).on(LK.RoomEvent.TrackUnsubscribed,renderMedia).on(LK.RoomEvent.LocalTrackPublished,renderMedia).on(LK.RoomEvent.LocalTrackUnpublished,renderMedia).on(LK.RoomEvent.ActiveSpeakersChanged,speakers).on(LK.RoomEvent.Disconnected,()=>{$("status").textContent="Appel terminé";});
    await state.lk.connect(data.av.url,data.av.token,{autoSubscribe:true});try{await state.lk.startAudio();}catch(_error){}
    $("mic").disabled=false;$("cam").disabled=false;$("hangup").disabled=false;$("connect").disabled=true;$("status").textContent="Appel connecté · micro et caméra OFF";renderMedia();
  }catch(error){state.lk=null;$("status").textContent="A/V : "+error.code;}
}
async function hangup(){if(state.lk){await state.lk.disconnect();state.lk=null;}state.av=null;state.mic=false;state.cam=false;$("mic").textContent="MICRO OFF";$("cam").textContent="CAMÉRA OFF";$("mic").disabled=true;$("cam").disabled=true;$("hangup").disabled=true;renderLobby();}
async function toggleMic(){if(!state.lk)return;try{state.mic=!state.mic;await state.lk.localParticipant.setMicrophoneEnabled(state.mic);$("mic").textContent=state.mic?"MICRO ON":"MICRO OFF";$("localMedia").textContent=(state.mic?"MIC ON":"MIC OFF")+" · "+(state.cam?"CAM ON":"CAM OFF");}catch(error){state.mic=false;$("mic").textContent="MICRO OFF";$("status").textContent="Micro : "+error.message;}}
async function toggleCam(){if(!state.lk)return;try{state.cam=!state.cam;await state.lk.localParticipant.setCameraEnabled(state.cam);$("cam").textContent=state.cam?"CAMÉRA ON":"CAMÉRA OFF";$("localMedia").textContent=(state.mic?"MIC ON":"MIC OFF")+" · "+(state.cam?"CAM ON":"CAM OFF");renderMedia();}catch(error){state.cam=false;$("cam").textContent="CAMÉRA OFF";$("status").textContent="Caméra : "+error.message;}}
async function closeWindow(){await hangup();fetch("/pincabos-link/api/lobby/window",{method:"POST",headers:{"Content-Type":"application/json","X-PinCabOS-Link-CSRF":CSRF},body:JSON.stringify({action:"close"})}).catch(()=>{});}
function refreshB2s(){const image=$("b2s");image.src="/pincabos-link/api/lobby/b2s-preview?t="+Date.now();}

$("connect").onclick=connect;$("mic").onclick=toggleMic;$("cam").onclick=toggleCam;$("hangup").onclick=hangup;$("close").onclick=closeWindow;
document.addEventListener("keydown",event=>{if(event.repeat)return;if(event.key==="Enter"&&!state.lk)connect();else if(event.key==="Escape")hangup();else if(event.key.toLowerCase()==="m")toggleMic();else if(event.key.toLowerCase()==="v")toggleCam();});
setInterval(loadState,2000);setInterval(refreshB2s,500);loadState();refreshB2s();
})();
</script>
</body>
</html>'''.replace("__CSRF__", _csrf_token).replace(
        "__LIVEKIT_VERSION__",
        LIVEKIT_CLIENT_VERSION,
    )


@lobby_av_blueprint.get("/pincabos-link/lobby-av")
def lobby_av_page() -> Response:
    response = Response(
        _lobby_av_html(),
        status=200,
        content_type="text/html; charset=utf-8",
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(self), microphone=(self)"
    return response


@lobby_av_blueprint.get("/pincabos-link/api/lobby")
def lobby_state():
    payload, status = _bridge("lobby-state")
    return jsonify(payload), status


@lobby_av_blueprint.post("/pincabos-link/api/lobby/av-token")
def lobby_av_token():
    if not _require_csrf():
        return jsonify({"ok": False, "error": "invalid_csrf"}), 403
    payload, status = _bridge("lobby-av-token")
    return jsonify(payload), status


@lobby_av_blueprint.route(
    "/pincabos-link/api/lobby/window",
    methods=["GET", "POST"],
)
def lobby_window():
    if _display_action is None:
        return jsonify({"ok": False, "error": "window_helper_unavailable"}), 500
    if request.method == "GET":
        return jsonify({"ok": True, "window": _display_action("status")})
    if not _require_csrf():
        return jsonify({"ok": False, "error": "invalid_csrf"}), 403
    data = request.get_json(silent=True) or {}
    action = str(data.get("action") or "")
    if action not in {"open", "close"}:
        return jsonify({"ok": False, "error": "invalid_action"}), 400
    result = _display_action(action)
    return jsonify({"ok": result in {"OPEN", "CLOSED"}, "window": result})


@lobby_av_blueprint.get("/pincabos-link/api/lobby/b2s-preview")
def lobby_b2s_preview():
    path = _backglass_preview_path()
    if path is None:
        return Response(status=404)
    response = send_file(path, mimetype="image/jpeg", conditional=False, max_age=0)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-PinCabOS-Capture-Age"] = str(
        max(0, int(time.time() - path.stat().st_mtime))
    )
    return response


def register_pincaboslink_lobby_av(
    app,
    bridge_json: Callable,
    csrf_ok: Callable[[], bool],
    csrf_token: str,
    display_action: Callable[[str], str],
) -> None:
    global _bridge_json, _csrf_ok, _csrf_token, _display_action
    _bridge_json = bridge_json
    _csrf_ok = csrf_ok
    _csrf_token = csrf_token
    _display_action = display_action
    if lobby_av_blueprint.name not in app.blueprints:
        app.register_blueprint(lobby_av_blueprint)
