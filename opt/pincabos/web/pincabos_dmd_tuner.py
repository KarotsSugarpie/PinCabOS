# PINCABOS_DMD_RUNTIME_COORDINATE_FIX_V43
from __future__ import annotations

import configparser
import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path

from flask import Response, jsonify, request

TABLES_ROOT = Path('/home/pinball/Tables').resolve()
RUNTIME_DIR = Path('/run/pincabos-b2s-dmd-tuner')
COMMAND_FILE = RUNTIME_DIR / 'command.env'
STATE_FILE = RUNTIME_DIR / 'state.env'
HQ_PREVIEW = Path('/run/pincabos-scoreview-x11-hq/preview.jpg')
DASHBOARD_PREVIEW = Path('/run/pincabos-dashboard-live/screen2.jpg')
HELPER = Path('/usr/local/sbin/pincabos-b2s-dmd-tuner-helper')
GLOBAL_INI = Path('/home/pinball/.local/share/VPinballX/10.8/VPinballX.ini')
VPINFE_INI = Path('/home/pinball/.config/vpinfe/vpinfe.ini')
LOCK = threading.RLock()


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
            if '=' in line:
                key, value = line.split('=', 1)
                values[key.strip()] = value.strip()
    except OSError:
        pass
    return values


def _int(value, fallback=0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _active_table() -> dict | None:
    rows: list[dict] = []
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            args = [
                item.decode('utf-8', errors='replace')
                for item in (proc / 'cmdline').read_bytes().split(b'\0')
                if item
            ]
            executable = os.readlink(proc / 'exe')
        except OSError:
            continue
        if 'VPinballX' not in Path(executable).name:
            continue
        table_arg = next((item for item in args if item.casefold().endswith('.vpx')), None)
        if not table_arg:
            continue
        table = Path(table_arg).resolve()
        try:
            table.relative_to(TABLES_ROOT)
        except ValueError:
            continue
        if table.is_file():
            rows.append({'pid': int(proc.name), 'table': table})
    return sorted(rows, key=lambda item: item['pid'], reverse=True)[0] if rows else None


def _screen_geometry() -> dict[str, int]:
    for authority in ('/home/pinball/.Xauthority', '/run/lightdm/root/:0'):
        env = os.environ.copy()
        env.update({'DISPLAY': ':0', 'XAUTHORITY': authority})
        try:
            result = subprocess.run(
                ['/usr/bin/xrandr', '--query'], env=env, text=True,
                capture_output=True, timeout=3, check=False,
            )
        except Exception:
            continue
        for line in result.stdout.splitlines():
            if not re.match(r'^DP-2\s+connected\b', line):
                continue
            match = re.search(r'(\d+)x(\d+)\+(\d+)\+(\d+)', line)
            if match:
                return dict(zip(('w', 'h', 'x', 'y'), map(int, match.groups())))
    return {'w': 1920, 'h': 1200, 'x': 5760, 'y': 0}


def _scoreview_window() -> dict | None:
    for authority in ('/home/pinball/.Xauthority', '/run/lightdm/root/:0'):
        env = os.environ.copy()
        env.update({'DISPLAY': ':0', 'XAUTHORITY': authority, 'XDG_RUNTIME_DIR': '/run/user/1000'})
        try:
            result = subprocess.run(
                ['/usr/bin/wmctrl', '-lGx'], env=env, text=True,
                capture_output=True, timeout=3, check=False,
            )
        except Exception:
            continue
        for line in result.stdout.splitlines():
            if not line.rstrip().endswith('Visual Pinball Score View'):
                continue
            parts = line.split(None, 7)
            if len(parts) >= 8:
                return {
                    'id': parts[0], 'x': _int(parts[2]), 'y': _int(parts[3]),
                    'w': _int(parts[4]), 'h': _int(parts[5]),
                }
    return None


def _read_ini_values(table: Path) -> dict[str, int]:
    values = {'overlay': 1, 'auto': 1, 'x': 0, 'y': 0, 'w': 640, 'h': 160}
    ini = table.with_suffix('.ini')
    if not ini.is_file():
        return values
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    try:
        parser.read(ini, encoding='utf-8')
    except Exception:
        return values
    section = next((s for s in parser.sections() if s.casefold() == 'plugin.b2slegacy'), None)
    if not section:
        return values
    options = {key.casefold(): value for key, value in parser.items(section)}
    values['overlay'] = _int(options.get('scoreviewdmdoverlay'), 1)
    values['auto'] = _int(options.get('scoreviewdmdautopos'), 1)
    values['x'] = _int(options.get('scoreviewdmdx'), 0)
    values['y'] = _int(options.get('scoreviewdmdy'), 0)
    values['w'] = max(1, _int(options.get('scoreviewdmdw'), 640))
    values['h'] = max(1, _int(options.get('scoreviewdmdh'), 160))
    return values


def _read_sections(path: Path, names: tuple[str, ...]) -> dict[str, str]:
    if not path.is_file():
        return {}
    text = path.read_text(encoding='utf-8', errors='replace')
    sections: dict[str, str] = {}
    for name in names:
        match = re.search(
            rf'(?ims)^\s*\[{re.escape(name)}\]\s*$\n(.*?)(?=^\s*\[|\Z)', text,
        )
        if match:
            sections[name] = match.group(1).strip()
    return sections


def _table_ini_payload(table: Path) -> dict:
    ini = table.with_suffix('.ini')
    return {
        'path': str(ini),
        'exists': ini.is_file(),
        'sections': _read_sections(ini, (
            'Displays', 'ScoreView', 'Plugin.B2SLegacy',
            'Plugin.ScoreView', 'PinCabOS.ScoreViewWindow',
        )),
    }


def _official_payload() -> dict:
    return {
        'vpx': {
            'path': str(GLOBAL_INI),
            'sections': _read_sections(GLOBAL_INI, ('Displays', 'ScoreView', 'Plugin.B2SLegacy', 'Plugin.ScoreView')),
        },
        'vpinfe': {
            'path': str(VPINFE_INI),
            'sections': _read_sections(VPINFE_INI, ('Displays',)),
        },
    }


def _clamp(data: dict, pid: int) -> dict:
    # Coordonnées internes du cadre DMD B2SLegacy, pas géométrie X11 DP-2.
    auto = bool(data.get('auto', False))
    x = max(0, min(65535, _int(data.get('x'), 0)))
    y = max(0, min(65535, _int(data.get('y'), 0)))
    w = max(1, min(65535, _int(data.get('w'), 640)))
    h = max(1, min(65535, _int(data.get('h'), 160)))
    return {'pid': pid, 'enabled': True, 'auto': auto, 'x': x, 'y': y, 'w': w, 'h': h}


def _write_command(values: dict) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    temporary = COMMAND_FILE.with_name(f'command.env.tmp.{os.getpid()}.{threading.get_ident()}')
    temporary.write_text(
        f"PID={values['pid']}\nENABLED=1\nAUTO={1 if values['auto'] else 0}\n"
        f"X={values['x']}\nY={values['y']}\nW={values['w']}\nH={values['h']}\n",
        encoding='utf-8',
    )
    os.chmod(temporary, 0o660)
    os.replace(temporary, COMMAND_FILE)


def _runtime_for_pid(pid: int) -> dict | None:
    state = _read_env(STATE_FILE)
    if _int(state.get('PID'), -1) != pid:
        return None
    return {
        'overlay': bool(_int(state.get('ENABLED'), 1)),
        'auto': bool(_int(state.get('AUTO'), 0)),
        'x': max(0, _int(state.get('X'), 0)),
        'y': max(0, _int(state.get('Y'), 0)),
        'w': max(1, _int(state.get('W'), 1)),
        'h': max(1, _int(state.get('H'), 1)),
        'override': bool(_int(state.get('OVERRIDE'), 0)),
    }


def _wait_runtime(values: dict) -> dict:
    deadline = time.monotonic() + 1.8
    latest = None
    while time.monotonic() < deadline:
        latest = _runtime_for_pid(values['pid'])
        if latest:
            if values['auto'] and latest['auto']:
                return latest
            if not values['auto'] and all(latest[key] == values[key] for key in ('x', 'y', 'w', 'h')):
                return latest
        time.sleep(0.04)
    raise RuntimeError(
        'Le plugin DMD temps réel ne confirme pas la commande. '
        f'Demandé={values}; état={latest}'
    )


def _status_payload() -> dict:
    active = _active_table()
    screen = _screen_geometry()
    window = _scoreview_window()
    base = {
        'ok': True,
        'running': bool(active),
        'screen': screen,
        'full_dmd_window': window,
        'full_dmd_locked': bool(window and window['x'] == screen['x'] and window['y'] == screen['y'] and window['w'] == screen['w'] and window['h'] == screen['h']),
        'preview': '/api/fulldmd/dmd-overlay/preview',
        'official': _official_payload(),
    }
    if not active:
        return base
    table: Path = active['table']
    values = _read_ini_values(table)
    source = 'table-ini'
    runtime = _runtime_for_pid(active['pid'])
    if runtime:
        values.update(runtime)
        source = 'runtime-plugin'
    command = _read_env(COMMAND_FILE)
    if not runtime and _int(command.get('PID'), -1) == active['pid']:
        values.update({
            'auto': bool(_int(command.get('AUTO'), values['auto'])),
            'x': _int(command.get('X'), values['x']),
            'y': _int(command.get('Y'), values['y']),
            'w': _int(command.get('W'), values['w']),
            'h': _int(command.get('H'), values['h']),
        })
        source = 'commande-en-attente'
    base.update({
        'pid': active['pid'],
        'table_name': table.stem,
        'table_path': str(table),
        'ini_path': str(table.with_suffix('.ini')),
        'source': source,
        'runtime_ready': runtime is not None,
        'auto': bool(values['auto']),
        'x': max(0, _int(values['x'])),
        'y': max(0, _int(values['y'])),
        'w': max(1, _int(values['w'], 640)),
        'h': max(1, _int(values['h'], 160)),
        'table_ini': _table_ini_payload(table),
    })
    return base


def _replace_first_info_card(body: str, replacement: str) -> str:
    for existing_id in (
        'pincabos-dmd-overlay-only-v4', 'pincabos-scoreview-x11-v35',
        'pincabos-scoreview-x11-v34', 'pincabos-scoreview-x11-v33',
        'pincabos-scoreview-x11-v2', 'pincabos-b2s-dmd-tuner-v1',
    ):
        marker = re.search(rf'<div\b[^>]*id=["\']{re.escape(existing_id)}["\'][^>]*>', body, re.I)
        if marker:
            start = marker.start()
            depth = 0
            for token in re.finditer(r'<div\b[^>]*>|</div\s*>', body[marker.start():], re.I):
                value = token.group(0).lower()
                depth += 1 if value.startswith('<div') else -1
                if depth == 0:
                    end = marker.start() + token.end()
                    return body[:start] + replacement + body[end:]
    marker = re.search(r'<div\b[^>]*class=["\'][^"\']*\bfulldmd-info-card\b[^"\']*["\'][^>]*>', body, re.I)
    if not marker:
        marker = re.search(r'<div\b[^>]*class=["\'][^"\']*\bcard\b[^"\']*["\'][^>]*>', body, re.I)
    if not marker:
        return body
    start = marker.start()
    depth = 0
    for token in re.finditer(r'<div\b[^>]*>|</div\s*>', body[marker.start():], re.I):
        depth += 1 if token.group(0).lower().startswith('<div') else -1
        if depth == 0:
            return body[:start] + replacement + body[marker.start() + token.end():]
    return body


def _card_html() -> str:
    return r'''
<div id="pincabos-dmd-overlay-only-v4" class="card pco-dmd4-card">
<style>
.pco-dmd4-card{min-height:760px;padding:16px;box-sizing:border-box}.pco-dmd4-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.pco-dmd4-head h2{margin:0 0 5px}.pco-dmd4-badges{display:flex;gap:7px;flex-wrap:wrap;justify-content:flex-end}.pco-dmd4-badge{border:1px solid #ff8700;border-radius:999px;padding:6px 10px;font-weight:800}.pco-dmd4-badge.ok{border-color:#22d77a;color:#55f7a3}.pco-dmd4-grid{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(360px,.8fr);gap:16px;margin-top:12px}.pco-dmd4-preview{min-height:620px;border:1px solid rgba(255,135,0,.65);border-radius:14px;background:#000;overflow:hidden}.pco-dmd4-preview img{width:100%;height:100%;display:block;object-fit:contain;background:#000}.pco-dmd4-controls{display:flex;flex-direction:column;gap:10px}.pco-dmd4-panel{border:1px solid rgba(255,135,0,.38);border-radius:13px;padding:12px;background:rgba(0,0,0,.18)}.pco-dmd4-title{font-weight:900;margin-bottom:9px;color:#ffb000}.pco-dmd4-step,.pco-dmd4-actions{display:flex;gap:8px;flex-wrap:wrap}.pco-dmd4-step button.active{outline:2px solid #ff9500}.pco-dmd4-pad{display:grid;grid-template-columns:repeat(3,58px);grid-template-rows:repeat(3,44px);gap:7px;justify-content:center}.pco-dmd4-pad button{font-size:20px}.pco-dmd4-fields{display:grid;grid-template-columns:1fr 1fr;gap:9px}.pco-dmd4-fields label{text-align:center}.pco-dmd4-fields input{width:100%;box-sizing:border-box;text-align:center;font-size:18px;font-weight:900;padding:10px;border:1px solid #ff8700;border-radius:10px;background:#050008;color:#fff}.pco-dmd4-resize{display:grid;grid-template-columns:1fr auto auto;gap:8px;align-items:center;margin-top:8px}.pco-dmd4-message{min-height:42px;font-weight:800;white-space:pre-wrap}.pco-dmd4-message.ok{color:#4cf49a}.pco-dmd4-message.err{color:#ff6969}.pco-dmd4-disabled{opacity:.45;pointer-events:none}.pco-table-dmd4-card{margin-top:14px;border:1px solid rgba(255,135,0,.65);border-radius:14px;padding:13px;background:rgba(0,0,0,.17)}.pco-table-dmd4-card h3{color:#ffb000}.pco-table-dmd4-card pre{white-space:pre-wrap;max-height:300px;overflow:auto;border:1px solid rgba(255,135,0,.55);border-radius:10px;padding:10px;background:#050008}.pco-table-dmd4-path{display:block;margin:7px 0;overflow-wrap:anywhere}.pco-table-dmd4-sections{display:grid;grid-template-columns:1fr 1fr;gap:10px}@media(max-width:1100px){.pco-dmd4-grid{grid-template-columns:1fr}.pco-dmd4-preview{min-height:400px}.pco-table-dmd4-sections{grid-template-columns:1fr}}
</style>
<div class="pco-dmd4-head"><div><h2>Réglage du DMD dans le FullDMD</h2><div id="pco-dmd4-table">Recherche de la table active…</div></div><div class="pco-dmd4-badges"><span id="pco-dmd4-vpx" class="pco-dmd4-badge">VPX arrêté</span><span id="pco-dmd4-runtime" class="pco-dmd4-badge">DMD runtime</span><span id="pco-dmd4-full" class="pco-dmd4-badge">FullDMD B2S plein DP-2</span></div></div>
<div class="pco-dmd4-grid"><div class="pco-dmd4-preview"><img id="pco-dmd4-preview" alt="Capture réelle DP-2"></div><div id="pco-dmd4-controls" class="pco-dmd4-controls pco-dmd4-disabled">
<div class="pco-dmd4-panel"><div class="pco-dmd4-title">Pas du DMD</div><div class="pco-dmd4-step"><button type="button" class="button active" data-step="1" title="Pas exact de 1 unité DMD">1 px exact</button><button type="button" class="button secondary" data-step="10">10 px</button><button type="button" class="button secondary" data-step="50">50 px</button></div></div>
<div class="pco-dmd4-panel"><div class="pco-dmd4-title">Déplacement du DMD en temps réel</div><div class="pco-dmd4-pad"><span></span><button type="button" class="button" data-dy="-1">↑</button><span></span><button type="button" class="button" data-dx="-1">←</button><button type="button" class="button secondary" id="pco-dmd4-center">●</button><button type="button" class="button" data-dx="1">→</button><span></span><button type="button" class="button" data-dy="1">↓</button><span></span></div></div>
<div class="pco-dmd4-panel"><div class="pco-dmd4-title">Valeurs réelles du DMD ScoreView</div><div class="pco-dmd4-fields"><label>X<input id="pco-dmd4-x" type="number" min="0"></label><label>Y<input id="pco-dmd4-y" type="number" min="0"></label><label>Largeur<input id="pco-dmd4-w" type="number" min="1"></label><label>Hauteur<input id="pco-dmd4-h" type="number" min="1"></label></div><div class="pco-dmd4-resize"><span>Largeur du DMD</span><button type="button" class="button secondary" data-dw="-1">−</button><button type="button" class="button secondary" data-dw="1">+</button></div><div class="pco-dmd4-resize"><span>Hauteur du DMD</span><button type="button" class="button secondary" data-dh="-1">−</button><button type="button" class="button secondary" data-dh="1">+</button></div></div>
<div class="pco-dmd4-panel"><div class="pco-dmd4-actions"><button type="button" class="button secondary" id="pco-dmd4-detect">Détecter le DMD actuel</button><button type="button" class="button" id="pco-dmd4-apply">Appliquer maintenant</button><button type="button" class="button secondary" id="pco-dmd4-auto">Détection automatique du DMD</button><button type="button" class="button secondary" id="pco-dmd4-cancel">Annuler</button><button type="button" class="button secondary" id="pco-dmd4-reset">Réinitialiser</button><button type="button" class="button" id="pco-dmd4-save">Enregistrer le DMD pour cette table</button></div></div>
<div id="pco-dmd4-message" class="pco-dmd4-message"></div></div></div>
<script>
(()=>{"use strict";const root=document.getElementById('pincabos-dmd-overlay-only-v4');if(!root||root.dataset.ready==='1')return;root.dataset.ready='1';const $=id=>document.getElementById(id);const fields={x:$('pco-dmd4-x'),y:$('pco-dmd4-y'),w:$('pco-dmd4-w'),h:$('pco-dmd4-h')};let status=null,opening=null,step=1,busy=false,nudgeQueue=Promise.resolve();const csrf=()=>document.querySelector('meta[name="pincabos-csrf-token"]')?.content||'';const msg=(text,kind='')=>{const e=$('pco-dmd4-message');e.textContent=text||'';e.className='pco-dmd4-message '+kind};const read=()=>({x:Number(fields.x.value)||0,y:Number(fields.y.value)||0,w:Number(fields.w.value)||1,h:Number(fields.h.value)||1,auto:false});const write=s=>{for(const k of ['x','y','w','h'])fields[k].value=Number(s?.[k]??0)};async function get(url){const r=await fetch(url,{cache:'no-store',credentials:'same-origin'});const d=await r.json().catch(()=>({}));if(!r.ok||d.ok===false)throw Error(d.error||`HTTP ${r.status}`);return d}async function post(url,payload={}){const headers={'Content-Type':'application/json','Accept':'application/json'};const token=csrf();if(token)headers['X-PinCabOS-CSRF']=token;const r=await fetch(url,{method:'POST',cache:'no-store',credentials:'same-origin',headers,body:JSON.stringify(payload)});const d=await r.json().catch(()=>({}));if(!r.ok||d.ok===false)throw Error(d.error||`HTTP ${r.status}`);return d}
function ensureTableCard(){let card=document.getElementById('pco-table-dmd4-card');if(card)return card;const heading=[...document.querySelectorAll('h1,h2,h3,h4,div')].find(e=>e.textContent.trim()==='Valeurs actuelles VPX / VPinFE');const host=heading?.closest('.card,.fulldmd-info-card')||heading?.parentElement;if(!host)return null;card=document.createElement('div');card.id='pco-table-dmd4-card';card.className='pco-table-dmd4-card';host.appendChild(card);return card}const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));function renderTable(){const card=ensureTableCard();if(!card)return;if(!status?.running){card.innerHTML='<h3>Table active — valeurs FullDMD / DMD ScoreView</h3><div>Aucune table VPX active.</div>';return}const info=status.table_ini||{};const blocks=Object.entries(info.sections||{}).map(([name,text])=>`<div><h4>[${esc(name)}]</h4><pre>${esc(text)}</pre></div>`).join('')||'<div>Aucune section trouvée.</div>';card.innerHTML=`<h3>Table active — valeurs FullDMD / DMD ScoreView</h3><strong>${esc(status.table_name)}</strong><code class="pco-table-dmd4-path">${esc(info.path||status.ini_path)}</code><div class="pco-table-dmd4-sections">${blocks}</div>`}
function render(){const running=!!status?.running;$('pco-dmd4-table').textContent=running?`Table active : ${status.table_name}`:'Aucune table VPX active';$('pco-dmd4-vpx').textContent=running?'VPX actif':'VPX arrêté';$('pco-dmd4-vpx').className='pco-dmd4-badge '+(running?'ok':'');$('pco-dmd4-runtime').textContent=status?.runtime_ready?'DMD runtime détecté':`Source : ${status?.source||'aucune'}`;$('pco-dmd4-runtime').className='pco-dmd4-badge '+(status?.runtime_ready?'ok':'');$('pco-dmd4-full').textContent=status?.full_dmd_locked?'FullDMD B2S plein DP-2':'FullDMD en attente de verrouillage';$('pco-dmd4-full').className='pco-dmd4-badge '+(status?.full_dmd_locked?'ok':'');$('pco-dmd4-controls').classList.toggle('pco-dmd4-disabled',!running);renderTable()}
async function load(force=false){try{const d=await get('/api/fulldmd/dmd-overlay/status?t='+Date.now());const pidChanged=!status||status.pid!==d.pid;status=d;if(force||pidChanged||!busy){write(d);if(force||pidChanged)opening={x:d.x,y:d.y,w:d.w,h:d.h,auto:d.auto}}render()}catch(e){msg(e.message,'err')}}async function apply(payload=read()){if(!status?.running||busy)return;busy=true;try{const d=await post('/api/fulldmd/dmd-overlay/apply',payload);Object.assign(status,d.state);write(d.state);render();msg(`DMD appliqué en temps réel : X=${d.state.x}, Y=${d.state.y}, ${d.state.w}×${d.state.h}`,'ok')}catch(e){msg(e.message,'err');await load(true)}finally{busy=false}}
function queueNudge(delta){
    nudgeQueue=nudgeQueue.then(async()=>{
        busy=true;
        try{
            const d=await post('/api/fulldmd/dmd-overlay/nudge',delta);
            Object.assign(status,d.state);
            write(d.state);
            render();
            msg(`DMD ajusté exactement : X=${d.state.x}, Y=${d.state.y}, ${d.state.w}×${d.state.h}`,'ok');
        }catch(e){
            msg(e.message,'err');
            await load(true);
        }finally{
            busy=false;
        }
    });
    return nudgeQueue;
}
root.querySelectorAll('[data-step]').forEach(b=>b.addEventListener('click',()=>{step=Number(b.dataset.step)||1;root.querySelectorAll('[data-step]').forEach(x=>x.classList.toggle('active',x===b))}));root.querySelectorAll('[data-dx]').forEach(b=>b.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();queueNudge({dx:step*Number(b.dataset.dx)})}));root.querySelectorAll('[data-dy]').forEach(b=>b.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();queueNudge({dy:-step*Number(b.dataset.dy)})}));root.querySelectorAll('[data-dw]').forEach(b=>b.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();queueNudge({dw:step*Number(b.dataset.dw)})}));root.querySelectorAll('[data-dh]').forEach(b=>b.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();queueNudge({dh:step*Number(b.dataset.dh)})}));$('pco-dmd4-center').addEventListener('click',()=>{const p=read(),s=status.screen;p.x=Math.floor((s.w-p.w)/2);p.y=Math.floor((s.h-p.h)/2);apply(p)});$('pco-dmd4-detect').addEventListener('click',async()=>{await load(true);msg(status.runtime_ready?'Valeurs réelles relues directement du plugin DMD.':'Valeurs chargées du INI; le runtime apparaîtra dès que le DMD rend une image.',status.runtime_ready?'ok':'')});$('pco-dmd4-apply').addEventListener('click',()=>apply(read()));$('pco-dmd4-auto').addEventListener('click',()=>apply({...read(),auto:true}));$('pco-dmd4-cancel').addEventListener('click',()=>opening&&apply({...opening}));$('pco-dmd4-reset').addEventListener('click',async()=>{try{const d=await post('/api/fulldmd/dmd-overlay/reset',{});Object.assign(status,d.state);write(d.state);opening={...d.state};render();msg(`DMD réinitialisé. Backup : ${d.backup}`,'ok')}catch(e){msg(e.message,'err')}});$('pco-dmd4-save').addEventListener('click',async()=>{try{const applied=await post('/api/fulldmd/dmd-overlay/apply',read());const d=await post('/api/fulldmd/dmd-overlay/save',applied.state);Object.assign(status,d.state);write(d.state);opening={...d.state};render();msg(`DMD enregistré dans ${d.ini}\nBackup : ${d.backup}`,'ok')}catch(e){msg(e.message,'err')}});Object.values(fields).forEach(input=>input.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();apply(read())}}));const preview=$('pco-dmd4-preview');const refresh=()=>preview.src='/api/fulldmd/dmd-overlay/preview?t='+Date.now();load(true);refresh();setInterval(()=>load(false),1000);setInterval(refresh,250)})();
</script></div>'''


def register_dmd_tuner(app, page=None, esc=None) -> None:
    if app.extensions.get('pincabos_dmd_overlay_only_v4'):
        return
    app.extensions['pincabos_dmd_overlay_only_v4'] = True

    @app.get('/api/fulldmd/dmd-overlay/status')
    @app.get('/api/fulldmd/dmd-tuner/status')
    def dmd_overlay_status():
        return jsonify(_status_payload())

    @app.get('/api/fulldmd/dmd-overlay/preview')
    @app.get('/api/fulldmd/dmd-tuner/preview')
    def dmd_overlay_preview():
        source = HQ_PREVIEW if HQ_PREVIEW.is_file() else DASHBOARD_PREVIEW
        if not source.is_file():
            return Response(status=404)
        try:
            payload = source.read_bytes()
        except OSError:
            return Response(status=503)
        return Response(payload, mimetype='image/jpeg', headers={
            'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
            'Pragma': 'no-cache',
            'X-PinCabOS-Preview': 'hq' if source == HQ_PREVIEW else 'dashboard-fallback',
        })

    @app.post('/api/fulldmd/dmd-overlay/apply')
    @app.post('/api/fulldmd/dmd-tuner/adjust')
    def dmd_overlay_apply():
        active = _active_table()
        if not active:
            return jsonify(ok=False, error='Aucune table VPX active.'), 409
        values = _clamp(request.get_json(silent=True) or {}, active['pid'])
        try:
            with LOCK:
                _write_command(values)
                actual = _wait_runtime(values)
        except Exception as exc:
            return jsonify(ok=False, error=str(exc)), 409
        return jsonify(ok=True, state={**values, **actual})

    @app.post('/api/fulldmd/dmd-overlay/nudge')
    def dmd_overlay_nudge():
        active = _active_table()
        if not active:
            return jsonify(ok=False, error='Aucune table VPX active.'), 409

        data = request.get_json(silent=True) or {}
        delta = {
            'dx': max(-1000, min(1000, _int(data.get('dx'), 0))),
            'dy': max(-1000, min(1000, _int(data.get('dy'), 0))),
            'dw': max(-1000, min(1000, _int(data.get('dw'), 0))),
            'dh': max(-1000, min(1000, _int(data.get('dh'), 0))),
        }

        if not any(delta.values()):
            return jsonify(ok=False, error='Delta DMD vide.'), 400

        try:
            with LOCK:
                current = _runtime_for_pid(active['pid'])
                if current is None:
                    current = _read_ini_values(active['table'])

                requested = {
                    'auto': False,
                    'x': _int(current.get('x'), 0) + delta['dx'],
                    'y': _int(current.get('y'), 0) + delta['dy'],
                    'w': _int(current.get('w'), 640) + delta['dw'],
                    'h': _int(current.get('h'), 160) + delta['dh'],
                }

                values = _clamp(requested, active['pid'])
                _write_command(values)
                actual = _wait_runtime(values)
        except Exception as exc:
            return jsonify(ok=False, error=str(exc)), 409

        return jsonify(ok=True, delta=delta, state={**values, **actual})

    @app.post('/api/fulldmd/dmd-overlay/save')
    @app.post('/api/fulldmd/dmd-tuner/save')
    def dmd_overlay_save():
        active = _active_table()
        if not active:
            return jsonify(ok=False, error='Aucune table VPX active.'), 409
        values = _clamp(request.get_json(silent=True) or {}, active['pid'])
        command = [
            '/usr/bin/sudo', str(HELPER), 'save', str(active['table']),
            '1' if values['auto'] else '0', str(values['x']), str(values['y']),
            str(values['w']), str(values['h']),
        ]
        result = subprocess.run(command, text=True, capture_output=True, timeout=20, check=False)
        if result.returncode != 0:
            return jsonify(ok=False, error=(result.stderr or result.stdout or 'Échec du helper.').strip()), 500
        try:
            saved = json.loads(result.stdout)
        except json.JSONDecodeError:
            return jsonify(ok=False, error='Réponse invalide du helper.'), 500
        return jsonify(ok=True, backup=saved.get('backup'), ini=saved.get('ini'), state=values)

    @app.post('/api/fulldmd/dmd-overlay/reset')
    @app.post('/api/fulldmd/dmd-tuner/reset')
    def dmd_overlay_reset():
        active = _active_table()
        if not active:
            return jsonify(ok=False, error='Aucune table VPX active.'), 409
        screen = _screen_geometry()
        values = {'pid': active['pid'], 'enabled': True, 'auto': True, 'x': 0, 'y': 0, 'w': min(640, screen['w']), 'h': min(160, screen['h'])}
        result = subprocess.run([
            '/usr/bin/sudo', str(HELPER), 'save', str(active['table']), '1', '0', '0', str(values['w']), str(values['h']),
        ], text=True, capture_output=True, timeout=20, check=False)
        if result.returncode != 0:
            return jsonify(ok=False, error=(result.stderr or result.stdout or 'Échec du helper.').strip()), 500
        saved = json.loads(result.stdout)
        with LOCK:
            _write_command(values)
        return jsonify(ok=True, backup=saved.get('backup'), state=values)

    @app.after_request
    def dmd_overlay_inject(response):
        if request.path.rstrip('/') != '/fulldmd' or response.status_code != 200:
            return response
        if 'text/html' not in response.headers.get('Content-Type', ''):
            return response
        try:
            body = response.get_data(as_text=True)
            updated = _replace_first_info_card(body, _card_html())
            if updated != body:
                response.set_data(updated)
                response.headers['Content-Length'] = str(len(updated.encode('utf-8')))
        except Exception:
            app.logger.exception('Injection du tuner DMD V4 impossible.')
        return response
