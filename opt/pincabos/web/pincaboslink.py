#!/usr/bin/env python3
"""PinCabOS Link: native WebApp shell + live account mirror + shared chat."""

from __future__ import annotations

import base64
import hmac
import html
import json
import re
import secrets
import shutil
import subprocess
from typing import Callable, Optional

from flask import Blueprint, Response, jsonify, make_response, request


PINFORGE_MODULE = "PINCABOS_LINK_UI_V4_ACCOUNT_MIRROR_CHAT"
HEARTBEAT_TIMER = "pincabos-link-heartbeat.timer"
PAIR_HELPER = "/usr/local/sbin/pincabos-link-web-pair"
ACCOUNT_BRIDGE = "/usr/local/sbin/pincabos-account-bridge"
BACKGLASS_HELPER = "/usr/local/sbin/pincabos-chat-backglass"
PAIR_PATTERN = re.compile(r"^[23456789ABCDEFGHJKLMNPQRSTUVWXYZ]{12}$")
CSRF_TOKEN = secrets.token_urlsafe(32)

pincaboslink_blueprint = Blueprint("pincaboslink_v1", __name__)
_page_renderer: Optional[Callable[[str, str], str]] = None


def _systemctl(action: str) -> str:
    executable = shutil.which("systemctl")
    if not executable:
        return "indisponible"
    try:
        result = subprocess.run(
            [executable, action, HEARTBEAT_TIMER],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return "indisponible"
    values = result.stdout.strip().splitlines()
    return values[0][:40] if values else "indisponible"


def _normalize_pairing_code(value: str) -> str:
    return "".join(
        character
        for character in str(value or "").upper()
        if character not in " -\t\r\n"
    )


def _join_cabinet(code: str) -> tuple[bool, str]:
    sudo = shutil.which("sudo")
    if not sudo:
        return False, "sudo est indisponible sur ce PinCab."

    try:
        result = subprocess.run(
            [sudo, "-n", PAIR_HELPER, code],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=45,
        )
    except subprocess.TimeoutExpired:
        return False, "La liaison a expire. Verifiez Internet et reessayez."
    except OSError:
        return False, "Impossible de lancer le service de liaison."

    status = result.stdout.strip().splitlines()
    marker = status[-1].strip() if status else "PAIR_FAILED"

    if result.returncode == 0 and marker == "PAIR_OK":
        return True, "PinCab associe avec succes a pincabos.cc."

    messages = {
        "PAIR_INVALID": "Le numero de liaison est invalide.",
        "PAIR_NETWORK": "Impossible de joindre pincabos.cc. Verifiez Internet.",
        "PAIR_REJECTED": "Numero refuse, expire ou deja utilise. Generez une nouvelle cle.",
        "PAIR_FAILED": "La liaison a echoue. Generez une nouvelle cle et reessayez.",
    }
    return False, messages.get(
        marker,
        "La liaison a echoue. Generez une nouvelle cle et reessayez.",
    )


def _csrf_ok() -> bool:
    supplied = str(
        request.headers.get("X-PinCabOS-Link-CSRF")
        or request.form.get("csrf_token")
        or ""
    )
    return hmac.compare_digest(supplied, CSRF_TOKEN)


def _bridge_json(*args: str, input_text: str | None = None):
    sudo = shutil.which("sudo")
    if not sudo:
        return {"ok": False, "error": "sudo_unavailable"}, 500

    try:
        result = subprocess.run(
            [sudo, "-n", ACCOUNT_BRIDGE, *args],
            input=input_text,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=35,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "bridge_timeout"}, 504
    except OSError:
        return {"ok": False, "error": "bridge_unavailable"}, 500

    try:
        payload = json.loads(result.stdout or "{}")
    except Exception:
        return {"ok": False, "error": "bridge_response_invalid"}, 502

    if not isinstance(payload, dict):
        return {"ok": False, "error": "bridge_response_invalid"}, 502

    remote_status = payload.pop("_http_status", None)
    if isinstance(remote_status, int):
        status = remote_status
    elif result.returncode == 0:
        status = 200
    else:
        status = 502

    if status < 100 or status > 599:
        status = 502

    return payload, status


def _display_action(action: str) -> str:
    sudo = shutil.which("sudo")
    if not sudo:
        return "ERROR"

    try:
        result = subprocess.run(
            [sudo, "-n", BACKGLASS_HELPER, action],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=30,
        )
    except Exception:
        return "ERROR"

    return (result.stdout or "").strip()


def _main_body(
    active: str,
    enabled: str,
    state_class: str,
    state_text: str,
    message: str,
    message_class: str,
) -> str:
    message_html = ""
    if message:
        message_html = (
            '<div class="pco-link-message '
            + html.escape(message_class)
            + '">'
            + html.escape(message)
            + "</div>"
        )

    body = r"""
<style>
/* PINCABOS_LINK_ACCOUNT_MIRROR_CHAT_V1 */
.pco-link-native{width:100%;margin:0 auto}
.pco-link-heading{margin-bottom:16px}
.pco-link-heading h1{margin-bottom:5px}
.pco-link-heading p{margin:0;opacity:.78}
.pco-link-main-card{border-color:rgba(255,122,0,.8)}
.pco-link-form{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:center;margin-top:14px}
.pco-link-input{width:100%;min-height:44px;padding:10px 14px;border:1px solid rgba(255,122,0,.85);border-radius:10px;background:rgba(5,5,12,.92);color:#fff;font:700 1rem/1.2 ui-monospace,SFMono-Regular,Consolas,monospace;letter-spacing:.08em;text-transform:uppercase;outline:none}
.pco-link-join{min-height:44px;padding:0 24px;white-space:nowrap;font-weight:900}
.pco-link-hint{margin-top:9px;opacity:.7;font-size:.9rem}
.pco-link-message{margin-top:12px;padding:11px 13px;border-radius:9px;font-weight:750}
.pco-link-message.success{color:#cbffdb;background:rgba(18,57,34,.88);border:1px solid #28643b}
.pco-link-message.error{color:#ffd0d0;background:rgba(66,26,26,.9);border:1px solid #743030}
.pco-mirror-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:15px;margin-top:15px}
.pco-mirror-wide{grid-column:1/-1}
.pco-profile{display:grid;grid-template-columns:auto minmax(0,1fr);gap:14px;align-items:center}
.pco-avatar{width:72px;height:72px;border-radius:50%;display:grid;place-items:center;overflow:hidden;background:linear-gradient(135deg,#ff7a18,#a970ff);font-size:1.3rem;font-weight:900}
.pco-avatar img{width:100%;height:100%;object-fit:cover}
.pco-muted{opacity:.7}
.pco-kv{display:grid;grid-template-columns:minmax(120px,.65fr) 1fr;gap:7px 14px;margin-top:12px}
.pco-kv span:nth-child(odd){opacity:.68}
.pco-list{display:grid;gap:9px}
.pco-item{padding:11px 12px;border:1px solid rgba(255,255,255,.10);border-radius:10px;background:rgba(7,8,14,.42)}
.pco-row{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap}
.pco-badge{display:inline-flex;padding:4px 8px;border-radius:999px;font-size:.78rem;font-weight:800;background:rgba(255,255,255,.08)}
.pco-badge.ok{color:#bfffd2;background:rgba(28,110,57,.35)}
.pco-badge.warn{color:#ffe0a8;background:rgba(130,78,15,.35)}
.pco-friend-button{width:100%;text-align:left;cursor:pointer}
.pco-friend-button.active{border-color:#ff7a18;box-shadow:0 0 0 1px rgba(255,122,24,.35)}
.pco-chat-head{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.pco-chat-actions{display:flex;gap:8px;flex-wrap:wrap}
.pco-chat-messages{height:330px;overflow-y:auto;display:flex;flex-direction:column;gap:8px;padding:12px 3px;margin-top:12px;border-top:1px solid rgba(255,255,255,.08);border-bottom:1px solid rgba(255,255,255,.08)}
.pco-chat-message{max-width:82%;padding:9px 11px;border-radius:12px;background:#252b3b;white-space:pre-wrap;overflow-wrap:anywhere}
.pco-chat-message.own{align-self:flex-end;background:linear-gradient(135deg,rgba(255,134,28,.32),rgba(149,92,255,.30))}
.pco-chat-message.friend{align-self:flex-start}
.pco-chat-message time{display:block;margin-top:4px;opacity:.58;font-size:.74rem}
.pco-chat-form{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;margin-top:11px}
.pco-chat-form textarea{min-height:64px;resize:vertical}
.pco-statusline{margin-top:8px;min-height:1.2em;opacity:.76}
.pco-loading{opacity:.72;padding:16px 0}
@media(max-width:850px){.pco-mirror-grid,.pco-link-form,.pco-chat-form{grid-template-columns:1fr}.pco-mirror-wide{grid-column:auto}.pco-link-join{width:100%}}
</style>

<section class="pco-link-native" data-marker="PINCABOS_LINK_ACCOUNT_MIRROR_CHAT_V1">
  <div class="pco-link-heading">
    <h1>PinCabOS Link</h1>
    <p>Votre compte pincabos.cc et votre chat, directement dans la WebApp du cabinet.</p>
  </div>

  <div class="card pco-link-main-card">
    <h2>Joindre ce PinCab a pincabos.cc</h2>
    <p>Generez une cle de liaison dans <strong>Mon compte</strong> sur pincabos.cc, entrez-la ici puis cliquez sur <strong>JOINDRE</strong>.</p>
    <form class="pco-link-form" method="post" action="/pincabos-link" autocomplete="off">
      <input type="hidden" name="csrf_token" value="__CSRF__">
      <input class="pco-link-input" type="text" name="pairing_code" maxlength="24" required spellcheck="false" autocapitalize="characters" placeholder="XXXX-XXXX-XXXX" aria-label="Numero de liaison">
      <button class="button pco-link-join" type="submit">JOINDRE</button>
    </form>
    __MESSAGE__
    <p class="pco-link-hint">Aucun iframe. Les donnees ci-dessous viennent directement de pincabos.cc avec l'identite securisee de ce PinCab.</p>
  </div>

  <div class="pco-mirror-grid">
    <div class="card">
      <h2>Mon compte pincabos.cc</h2>
      <div id="pco-account-profile" class="pco-loading">Chargement du compte...</div>
    </div>

    <div class="card">
      <h2>Presence du cabinet</h2>
      <div class="pco-kv">
        <span>Etat local</span><strong>__STATE_TEXT__</strong>
        <span>Heartbeat</span><strong>__ACTIVE__</strong>
        <span>Demarrage auto</span><strong>__ENABLED__</strong>
        <span>Frequence</span><strong>60 secondes</strong>
        <span>Hors ligne apres</span><strong>180 secondes</strong>
      </div>
    </div>

    <div class="card">
      <h2>Mes PinCabs</h2>
      <div id="pco-account-cabinets" class="pco-loading">Chargement...</div>
    </div>

    <div class="card">
      <h2>Amis et demandes</h2>
      <div id="pco-account-friends" class="pco-loading">Chargement...</div>
    </div>

    <div class="card pco-mirror-wide">
      <div class="pco-chat-head">
        <div>
          <h2 style="margin-bottom:4px">Chat PinCabOS</h2>
          <div id="pco-chat-title" class="pco-muted">Choisissez un ami.</div>
        </div>
        <div class="pco-chat-actions">
          <button id="pco-chat-backglass" class="button secondary" type="button">Afficher le chat au BackGlass</button>
        </div>
      </div>
      <div id="pco-chat-messages" class="pco-chat-messages">
        <div class="pco-muted">Aucune conversation selectionnee.</div>
      </div>
      <form id="pco-chat-form" class="pco-chat-form">
        <textarea id="pco-chat-input" maxlength="2000" placeholder="Ecrire un message..." disabled></textarea>
        <button id="pco-chat-send" class="button" type="submit" disabled>ENVOYER</button>
      </form>
      <div id="pco-chat-status" class="pco-statusline"></div>
    </div>
  </div>
</section>

<script>
(() => {
  "use strict";
  const CSRF = "__CSRF_JS__";
  const state = {ctx:null, friendId:null, lastId:0, chatTimer:null, accountTimer:null};

  function el(tag, cls, text){
    const n=document.createElement(tag);
    if(cls)n.className=cls;
    if(text!==undefined&&text!==null)n.textContent=String(text);
    return n;
  }

  function initials(user){
    const source=(user&&(user.display_name||user.username))||"PC";
    return source.split(/\s+/).filter(Boolean).slice(0,2).map(x=>x.charAt(0).toUpperCase()).join("")||"PC";
  }

  function avatar(user){
    const box=el("div","pco-avatar");
    if(user&&user.avatar&&user.avatar.present){
      const img=el("img");
      img.alt="Avatar";
      img.src="/pincabos-link/api/avatar/"+encodeURIComponent(user.id);
      img.addEventListener("error",()=>{box.replaceChildren(el("span","",initials(user)));},{once:true});
      box.appendChild(img);
    }else{
      box.appendChild(el("span","",initials(user)));
    }
    return box;
  }

  async function api(path, options){
    const supplied=options||{};
    const method=String(supplied.method||"GET").toUpperCase();
    const headers=Object.assign({"Accept":"application/json"},supplied.headers||{});
    if(method!=="GET") headers["X-PinCabOS-Link-CSRF"]=CSRF;
    const response=await fetch(path,Object.assign({},supplied,{headers,cache:"no-store"}));
    let data={};
    try{data=await response.json();}catch(_e){}
    if(!response.ok||data.ok===false){
      const e=new Error(data.error||("HTTP "+response.status));
      e.code=data.error||"request_failed";
      throw e;
    }
    return data;
  }

  function formatPresence(p){
    const s=(p&&p.status)||"offline";
    return ({online:"EN LIGNE",away:"ABSENT",invisible:"INVISIBLE",offline:"HORS LIGNE"})[s]||s.toUpperCase();
  }

  function renderProfile(){
    const host=document.getElementById("pco-account-profile");
    const u=state.ctx&&state.ctx.user;
    if(!u){host.textContent="Compte indisponible.";return;}
    const wrap=el("div","pco-profile");
    wrap.appendChild(avatar(u));
    const info=el("div");
    info.appendChild(el("h3","",u.display_name||u.username));
    info.appendChild(el("div","pco-muted","@"+u.username));
    const kv=el("div","pco-kv");
    [["Courriel",u.email||"—"],["Role",u.role||"user"],["Courriel verifie",u.email_verified?"Oui":"Non"],["Presence",formatPresence(u.presence)]].forEach(([a,b])=>{kv.append(el("span","",a),el("strong","",b));});
    info.appendChild(kv);
    wrap.appendChild(info);
    host.replaceChildren(wrap);
  }

  function renderCabinets(){
    const host=document.getElementById("pco-account-cabinets");
    const list=Array.isArray(state.ctx&&state.ctx.cabinets)?state.ctx.cabinets:[];
    if(!list.length){host.textContent="Aucun PinCab associe.";return;}
    const box=el("div","pco-list");
    list.forEach(c=>{
      const item=el("div","pco-item");
      const top=el("div","pco-row");
      top.appendChild(el("strong","",c.cabinet_name));
      top.appendChild(el("span","pco-badge "+(c.device_online?"ok":"warn"),c.device_online?"EN LIGNE":"HORS LIGNE"));
      item.appendChild(top);
      item.appendChild(el("div","pco-muted",c.cabinet_uuid));
      const details=el("div","pco-kv");
      [["Liaison",c.pairing_status],["BackGlass chat",c.remote&&c.remote.backglass_enabled?"Active":"Desactive"],["Agent distant",c.remote&&c.remote.agent_ready?"Pret":"Non pret"]].forEach(([a,b])=>{details.append(el("span","",a),el("strong","",b));});
      item.appendChild(details);
      box.appendChild(item);
    });
    host.replaceChildren(box);
  }

  function renderFriends(){
    const host=document.getElementById("pco-account-friends");
    const friends=Array.isArray(state.ctx&&state.ctx.friends)?state.ctx.friends:[];
    const incoming=(state.ctx&&state.ctx.requests&&state.ctx.requests.incoming)||[];
    const outgoing=(state.ctx&&state.ctx.requests&&state.ctx.requests.outgoing)||[];
    const box=el("div","pco-list");
    if(!friends.length) box.appendChild(el("div","pco-muted","Aucun ami accepte."));
    friends.forEach(f=>{
      const b=el("button","button secondary pco-friend-button"+(Number(state.friendId)===Number(f.id)?" active":""));
      b.type="button";
      const row=el("div","pco-row");
      row.appendChild(el("strong","",f.display_name||f.username));
      row.appendChild(el("span","pco-badge",formatPresence(f.presence)));
      b.appendChild(row);
      b.appendChild(el("div","pco-muted","@"+f.username+" · ouvrir le chat"));
      b.addEventListener("click",()=>selectFriend(Number(f.id)));
      box.appendChild(b);
    });
    if(incoming.length||outgoing.length){
      box.appendChild(el("div","pco-muted","Demandes recues : "+incoming.length+" · envoyees : "+outgoing.length));
    }
    host.replaceChildren(box);
  }

  function currentCabinet(){
    if(!state.ctx)return null;
    const id=Number(state.ctx.device&&state.ctx.device.cabinet_id);
    return (state.ctx.cabinets||[]).find(c=>Number(c.id)===id)||null;
  }

  function renderBackglassButton(){
    const button=document.getElementById("pco-chat-backglass");
    const cab=currentCabinet();
    const on=!!(cab&&cab.remote&&cab.remote.backglass_enabled);
    button.textContent=on?"Fermer le chat du BackGlass":"Afficher le chat au BackGlass";
    button.dataset.enabled=on?"1":"0";
  }

  function renderAll(){
    renderProfile();
    renderCabinets();
    renderFriends();
    renderBackglassButton();
  }

  async function loadContext(){
    try{
      state.ctx=await api("/pincabos-link/api/context");
      renderAll();
      if(!state.friendId&&state.ctx.friends&&state.ctx.friends.length) selectFriend(Number(state.ctx.friends[0].id));
    }catch(e){
      document.getElementById("pco-account-profile").textContent="Impossible de lire le compte pincabos.cc : "+e.code;
    }
  }

  function friendById(id){
    return ((state.ctx&&state.ctx.friends)||[]).find(f=>Number(f.id)===Number(id))||null;
  }

  function selectFriend(id){
    state.friendId=Number(id);
    state.lastId=0;
    const friend=friendById(id);
    document.getElementById("pco-chat-title").textContent=friend?("Conversation avec "+(friend.display_name||friend.username)):"Conversation";
    document.getElementById("pco-chat-messages").replaceChildren();
    document.getElementById("pco-chat-input").disabled=false;
    document.getElementById("pco-chat-send").disabled=false;
    renderFriends();
    pollChat();
  }

  function appendMessage(m){
    const host=document.getElementById("pco-chat-messages");
    if(state.lastId===0&&host.querySelector(".pco-muted"))host.replaceChildren();
    const own=state.ctx&&state.ctx.user&&Number(m.sender_user_id)===Number(state.ctx.user.id);
    const item=el("div","pco-chat-message "+(own?"own":"friend"));
    item.appendChild(el("div","",m.body));
    item.appendChild(el("time","",m.created_at||""));
    host.appendChild(item);
    state.lastId=Math.max(state.lastId,Number(m.id)||0);
    host.scrollTop=host.scrollHeight;
  }

  async function pollChat(){
    if(!state.friendId)return;
    try{
      const data=await api("/pincabos-link/api/chat/"+encodeURIComponent(state.friendId)+"?after_id="+encodeURIComponent(state.lastId));
      (data.messages||[]).forEach(appendMessage);
      document.getElementById("pco-chat-status").textContent="";
    }catch(e){
      document.getElementById("pco-chat-status").textContent="Chat : "+e.code;
    }
  }

  document.getElementById("pco-chat-form").addEventListener("submit",async(ev)=>{
    ev.preventDefault();
    if(!state.friendId)return;
    const input=document.getElementById("pco-chat-input");
    const message=input.value.trim();
    if(!message)return;
    const send=document.getElementById("pco-chat-send");
    send.disabled=true;
    try{
      const data=await api("/pincabos-link/api/chat/"+encodeURIComponent(state.friendId),{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message})});
      input.value="";
      if(data.message)appendMessage(data.message);
    }catch(e){
      document.getElementById("pco-chat-status").textContent="Envoi : "+e.code;
    }finally{send.disabled=false;input.focus();}
  });

  document.getElementById("pco-chat-backglass").addEventListener("click",async()=>{
    const button=document.getElementById("pco-chat-backglass");
    const enabled=button.dataset.enabled!=="1";
    button.disabled=true;
    try{
      await api("/pincabos-link/api/backglass",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({enabled})});
      await loadContext();
    }catch(e){
      document.getElementById("pco-chat-status").textContent="BackGlass : "+e.code;
    }finally{button.disabled=false;}
  });

  loadContext();
  api("/pincabos-link/api/presence",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"}).catch(()=>{});
  state.accountTimer=setInterval(loadContext,15000);
  state.chatTimer=setInterval(pollChat,4000);
  setInterval(()=>api("/pincabos-link/api/presence",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"}).catch(()=>{}),30000);
})();
</script>
"""
    return (
        body.replace("__CSRF__", html.escape(CSRF_TOKEN, quote=True))
        .replace("__CSRF_JS__", json.dumps(CSRF_TOKEN)[1:-1])
        .replace("__MESSAGE__", message_html)
        .replace("__STATE_TEXT__", html.escape(state_text))
        .replace("__ACTIVE__", html.escape(active))
        .replace("__ENABLED__", html.escape(enabled))
    )


def _backglass_html() -> str:
    return r"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Chat PinCabOS BackGlass</title>
<style>
:root{color-scheme:dark;--bg:#06070d;--panel:#141722;--line:#30364a;--orange:#ff7a18;--purple:#a970ff;--text:#f7f7fb;--muted:#aeb4c6}
*{box-sizing:border-box}
body{margin:0;height:100vh;background:radial-gradient(circle at top right,#281840 0,transparent 40%),radial-gradient(circle at top left,#3b1b09 0,transparent 38%),var(--bg);color:var(--text);font-family:system-ui,-apple-system,"Segoe UI",sans-serif;overflow:hidden}
.shell{height:100vh;display:grid;grid-template-columns:330px 1fr;gap:14px;padding:14px}
.panel{background:rgba(20,23,34,.96);border:1px solid var(--line);border-radius:15px;overflow:hidden}
.sidebar{display:flex;flex-direction:column}
.brand{padding:18px;border-bottom:1px solid var(--line);font-size:1.25rem;font-weight:900}.brand .pin{color:var(--orange)}.brand .os{color:var(--purple)}
.friends{padding:12px;overflow:auto;display:grid;gap:8px}
.friend{padding:11px;border:1px solid var(--line);border-radius:10px;background:#191d2a;color:#fff;text-align:left;cursor:pointer}.friend.active{border-color:var(--orange)}
.main{display:grid;grid-template-rows:auto 1fr auto;min-width:0}
.head{padding:14px 16px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;gap:10px}
.head h1{font-size:1.1rem;margin:0}.muted{color:var(--muted)}
.close{border:1px solid #6c3140;background:#35141d;color:#ffd3da;border-radius:9px;padding:9px 12px;font-weight:800;cursor:pointer}
.messages{padding:16px;overflow:auto;display:flex;flex-direction:column;gap:9px}
.msg{max-width:76%;padding:10px 12px;border-radius:13px;background:#252b3b;white-space:pre-wrap;overflow-wrap:anywhere}.msg.own{align-self:flex-end;background:linear-gradient(135deg,rgba(255,134,28,.35),rgba(149,92,255,.34))}.msg.friend{align-self:flex-start}.msg time{display:block;margin-top:5px;font-size:.72rem;color:#aab1c3}
.form{padding:12px;border-top:1px solid var(--line);display:grid;grid-template-columns:1fr auto;gap:10px}
textarea{min-height:64px;max-height:160px;resize:none;padding:11px;border:1px solid #41475d;border-radius:10px;background:#0c0f17;color:#fff;font:inherit}
.send{padding:0 22px;border:1px solid #ff9343;border-radius:10px;background:#d85d08;color:#fff;font-weight:900;cursor:pointer}
@media(max-width:900px){.shell{grid-template-columns:250px 1fr}}
</style>
</head>
<body>
<div class="shell">
  <aside class="panel sidebar">
    <div class="brand"><span class="pin">Pin</span>Cab<span class="os">OS</span> Chat</div>
    <div id="friends" class="friends"><div class="muted">Chargement...</div></div>
  </aside>
  <main class="panel main">
    <div class="head">
      <div><h1 id="title">Chat PinCabOS</h1><div id="status" class="muted">Connexion a pincabos.cc...</div></div>
      <button id="close" class="close" type="button">FERMER LE CHAT</button>
    </div>
    <div id="messages" class="messages"><div class="muted">Choisissez un ami.</div></div>
    <form id="form" class="form">
      <textarea id="input" maxlength="2000" placeholder="Ecrire un message..." disabled></textarea>
      <button id="send" class="send" type="submit" disabled>ENVOYER</button>
    </form>
  </main>
</div>
<script>
(() => {
"use strict";
const CSRF="__CSRF_JS__";
const state={ctx:null,friendId:null,lastId:0};

async function api(path,options){
  const supplied=options||{},method=String(supplied.method||"GET").toUpperCase(),headers=Object.assign({"Accept":"application/json"},supplied.headers||{});
  if(method!=="GET")headers["X-PinCabOS-Link-CSRF"]=CSRF;
  const r=await fetch(path,Object.assign({},supplied,{headers,cache:"no-store"}));
  let d={};try{d=await r.json();}catch(_e){}
  if(!r.ok||d.ok===false)throw new Error(d.error||("HTTP "+r.status));
  return d;
}
function node(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=String(text);return n;}
function friend(id){return ((state.ctx&&state.ctx.friends)||[]).find(x=>Number(x.id)===Number(id));}
function renderFriends(){
  const host=document.getElementById("friends");host.replaceChildren();
  const list=(state.ctx&&state.ctx.friends)||[];
  if(!list.length){host.appendChild(node("div","muted","Aucun ami accepte."));return;}
  list.forEach(f=>{const b=node("button","friend"+(Number(f.id)===Number(state.friendId)?" active":""),(f.display_name||f.username)+" · @"+f.username);b.type="button";b.onclick=()=>selectFriend(Number(f.id));host.appendChild(b);});
}
function selectFriend(id){
  state.friendId=Number(id);state.lastId=0;
  const f=friend(id);document.getElementById("title").textContent=f?("Chat avec "+(f.display_name||f.username)):"Chat PinCabOS";
  document.getElementById("messages").replaceChildren();
  document.getElementById("input").disabled=false;document.getElementById("send").disabled=false;
  renderFriends();poll();
}
function append(m){
  const host=document.getElementById("messages"),own=state.ctx&&state.ctx.user&&Number(m.sender_user_id)===Number(state.ctx.user.id);
  const box=node("div","msg "+(own?"own":"friend"));box.append(node("div","",m.body),node("time","",m.created_at||""));host.appendChild(box);
  state.lastId=Math.max(state.lastId,Number(m.id)||0);host.scrollTop=host.scrollHeight;
}
async function context(){
  try{state.ctx=await api("/pincabos-link/api/context");renderFriends();document.getElementById("status").textContent="Synchronise avec pincabos.cc";if(!state.friendId&&state.ctx.friends&&state.ctx.friends.length)selectFriend(Number(state.ctx.friends[0].id));}
  catch(e){document.getElementById("status").textContent="Connexion impossible : "+e.message;}
}
async function poll(){if(!state.friendId)return;try{const d=await api("/pincabos-link/api/chat/"+state.friendId+"?after_id="+state.lastId);(d.messages||[]).forEach(append);}catch(e){document.getElementById("status").textContent="Chat : "+e.message;}}
document.getElementById("form").onsubmit=async ev=>{ev.preventDefault();if(!state.friendId)return;const input=document.getElementById("input"),msg=input.value.trim();if(!msg)return;try{const d=await api("/pincabos-link/api/chat/"+state.friendId,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:msg})});input.value="";if(d.message)append(d.message);}catch(e){document.getElementById("status").textContent="Envoi : "+e.message;}};
document.getElementById("close").onclick=async()=>{try{await api("/pincabos-link/api/backglass",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({enabled:false})});document.getElementById("status").textContent="Fermeture...";}catch(e){document.getElementById("status").textContent="Fermeture : "+e.message;}};
context();setInterval(context,15000);setInterval(poll,4000);setInterval(()=>api("/pincabos-link/api/presence",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"}).catch(()=>{}),30000);
})();
</script>
</body>
</html>""".replace("__CSRF_JS__", json.dumps(CSRF_TOKEN)[1:-1])


@pincaboslink_blueprint.route("/pincabos-link", methods=["GET", "POST"])
def pincaboslink_page() -> Response:
    if _page_renderer is None:
        return Response(
            "PinCabOS WebApp renderer unavailable.",
            status=500,
            content_type="text/plain; charset=utf-8",
        )

    active = _systemctl("is-active")
    enabled = _systemctl("is-enabled")
    healthy = active == "active" and enabled == "enabled"
    state_class = "ok" if healthy else "warn"
    state_text = "Liaison active" if healthy else "Liaison a verifier"
    message = ""
    message_class = ""

    if request.method == "POST":
        submitted_csrf = str(request.form.get("csrf_token") or "")
        if not hmac.compare_digest(submitted_csrf, CSRF_TOKEN):
            message = "Requete refusee. Rechargez la page et reessayez."
            message_class = "error"
        else:
            code = _normalize_pairing_code(request.form.get("pairing_code") or "")
            if not PAIR_PATTERN.fullmatch(code):
                message = "Format invalide. Entrez la cle de liaison a 12 caracteres."
                message_class = "error"
            else:
                success, message = _join_cabinet(code)
                message_class = "success" if success else "error"

    body = _main_body(
        active=active,
        enabled=enabled,
        state_class=state_class,
        state_text=state_text,
        message=message,
        message_class=message_class,
    )
    response = make_response(_page_renderer("PinCabOS Link", body))
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@pincaboslink_blueprint.get("/pincabos-link/chat-backglass")
def pincaboslink_chat_backglass() -> Response:
    response = Response(
        _backglass_html(),
        status=200,
        content_type="text/html; charset=utf-8",
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@pincaboslink_blueprint.get("/pincabos-link/api/context")
def pincaboslink_api_context():
    payload, status = _bridge_json("context")
    return jsonify(payload), status


@pincaboslink_blueprint.post("/pincabos-link/api/presence")
def pincaboslink_api_presence():
    if not _csrf_ok():
        return jsonify({"ok": False, "error": "invalid_csrf"}), 403
    payload, status = _bridge_json("presence")
    return jsonify(payload), status


@pincaboslink_blueprint.route(
    "/pincabos-link/api/chat/<int:friend_user_id>",
    methods=["GET", "POST"],
)
def pincaboslink_api_chat(friend_user_id: int):
    if request.method == "GET":
        try:
            after_id = max(0, int(request.args.get("after_id") or 0))
        except ValueError:
            after_id = 0
        payload, status = _bridge_json(
            "chat-get",
            str(friend_user_id),
            str(after_id),
        )
        return jsonify(payload), status

    if not _csrf_ok():
        return jsonify({"ok": False, "error": "invalid_csrf"}), 403

    data = request.get_json(silent=True) or {}
    message = str(data.get("message") or "").strip()
    if not message or len(message) > 2000:
        return jsonify({"ok": False, "error": "invalid_message"}), 400

    payload, status = _bridge_json(
        "chat-post",
        str(friend_user_id),
        input_text=message,
    )
    return jsonify(payload), status


@pincaboslink_blueprint.get("/pincabos-link/api/avatar/<int:user_id>")
def pincaboslink_api_avatar(user_id: int):
    payload, status = _bridge_json("avatar", str(user_id))
    if status != 200 or payload.get("ok") is not True:
        return Response(status=status)

    mime = str(payload.get("mime") or "")
    raw = str(payload.get("data_base64") or "")

    try:
        data = base64.b64decode(raw, validate=True)
    except Exception:
        return Response(status=502)

    if mime not in {"image/png", "image/jpeg", "image/jpg"}:
        return Response(status=502)

    response = Response(data, status=200, content_type=mime)
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@pincaboslink_blueprint.route(
    "/pincabos-link/api/backglass",
    methods=["GET", "POST"],
)
def pincaboslink_api_backglass():
    if request.method == "GET":
        payload, status = _bridge_json("backglass-get")
        if status == 200 and payload.get("ok") is True:
            payload["local_window"] = _display_action("status")
        return jsonify(payload), status

    if not _csrf_ok():
        return jsonify({"ok": False, "error": "invalid_csrf"}), 403

    data = request.get_json(silent=True) or {}
    enabled = data.get("enabled")
    if not isinstance(enabled, bool):
        return jsonify({"ok": False, "error": "invalid_enabled"}), 400

    payload, status = _bridge_json(
        "backglass-set",
        "1" if enabled else "0",
    )

    if status == 200 and payload.get("ok") is True:
        payload["local_window"] = _display_action(
            "open" if enabled else "close"
        )

    return jsonify(payload), status


def register_pincaboslink(
    app,
    page_renderer: Callable[[str, str], str],
) -> None:
    global _page_renderer
    _page_renderer = page_renderer
    if pincaboslink_blueprint.name not in app.blueprints:
        app.register_blueprint(pincaboslink_blueprint)
