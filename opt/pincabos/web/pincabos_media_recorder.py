from __future__ import annotations

import html
import json
import os
import time
import uuid
from pathlib import Path

from flask import jsonify, request

STATE_DIR = Path('/var/lib/pincabos/media-recorder')
LOG_DIR = STATE_DIR / 'logs'
JOB_FILE = STATE_DIR / 'job.json'
STATUS_FILE = STATE_DIR / 'status.json'
CONTROL_FILE = STATE_DIR / 'control.json'
TABLES_ROOT = Path('/home/pinball/Tables').resolve()

ALLOWED_SCREENS = {'playfield', 'backglass', 'fulldmd', 'topper'}
ALLOWED_TYPES = {'image', 'video', 'both'}
ALLOWED_MODES = {'auto', 'original', 'pup'}
ALLOWED_SOURCES = {'auto', 'screen', 'window'}
ALLOWED_QUALITIES = {'low', 'medium', 'high', 'max'}
ALLOWED_ENCODERS = {'auto', 'nvenc', 'x264'}
ALLOWED_FPS = {15, 24, 25, 30, 50, 60}
ACTIVE_STATES = {'queued', 'running', 'pausing', 'paused', 'stopping'}

# PINCABOS_MEDIA_RECORDER_UI_V2_1
MR_MEDIA_VARIANTS = {
    "playfield": {
        "image": ("table.png", "table.jpg", "table.jpeg", "table.webp"),
        "video": ("table.mp4", "table.webm", "table.mkv", "table.avi"),
    },
    "backglass": {
        "image": ("bg.png", "bg.jpg", "bg.jpeg", "bg.webp"),
        "video": ("bg.mp4", "bg.webm", "bg.mkv", "bg.avi"),
    },
    "fulldmd": {
        "image": ("dmd.png", "dmd.jpg", "dmd.jpeg", "dmd.webp"),
        "video": ("dmd.mp4", "dmd.webm", "dmd.mkv", "dmd.avi"),
    },
    "topper": {
        "image": ("topper.png", "topper.jpg", "topper.jpeg", "topper.webp"),
        "video": ("topper.mp4", "topper.webm", "topper.mkv", "topper.avi"),
    },
}


def _mr_media_presence(table_dir: Path) -> dict:
    media_dir = table_dir / "medias"

    result = {
        role: {
            "image": False,
            "video": False,
        }
        for role in MR_MEDIA_VARIANTS
    }

    if not media_dir.is_dir():
        return result

    try:
        existing = {
            item.name.casefold()
            for item in media_dir.iterdir()
            if item.is_file()
        }
    except Exception:
        return result

    for role, kinds in MR_MEDIA_VARIANTS.items():
        for kind, filenames in kinds.items():
            result[role][kind] = any(
                name.casefold() in existing
                for name in filenames
            )

    return result


def _mr_presence_badges(presence: dict) -> str:
    labels = (
        ("playfield", "PF"),
        ("backglass", "BG"),
        ("fulldmd", "DMD"),
        ("topper", "TOP"),
    )

    output = []

    for role, label in labels:
        state = presence.get(role) or {}

        image = bool(state.get("image"))
        video = bool(state.get("video"))

        if image and video:
            level = "full"
        elif image or video:
            level = "partial"
        else:
            level = "none"

        image_mark = "✓" if image else "·"
        video_mark = "✓" if video else "·"

        output.append(
            '<span class="mr-pres-chip '
            + level
            + '" title="'
            + label
            + ' — Image '
            + ("présente" if image else "absente")
            + ' / Vidéo '
            + ("présente" if video else "absente")
            + '">'
            + label
            + ' <b>I'
            + image_mark
            + '</b> <b>V'
            + video_mark
            + '</b></span>'
        )

    return "".join(output)



def _atomic_json(path: Path, payload: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp-' + uuid.uuid4().hex)
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    os.chmod(tmp, 0o664)
    os.replace(tmp, path)


def _read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {} if default is None else default


def _safe_float(value, default, minimum, maximum):
    try:
        value = float(value)
    except Exception:
        value = float(default)
    return max(float(minimum), min(float(maximum), value))


def _safe_int(value, default, allowed):
    try:
        value = int(value)
    except Exception:
        value = int(default)
    return value if value in allowed else int(default)


def _table_inventory():
    out = []
    if not TABLES_ROOT.is_dir():
        return out
    for p in sorted(TABLES_ROOT.glob('*/*.vpx'), key=lambda x: (x.parent.name.lower(), x.name.lower())):
        try:
            rp = p.resolve(strict=True)
            rp.relative_to(TABLES_ROOT)
        except Exception:
            continue
        out.append({'name': p.parent.name, 'file': p.name, 'path': str(rp), 'presence': _mr_media_presence(p.parent)})
    return out


def _validate_tables(values):
    if not isinstance(values, list):
        raise ValueError('La sélection de tables est invalide.')
    seen = set()
    out = []
    for raw in values:
        try:
            p = Path(str(raw)).resolve(strict=True)
            p.relative_to(TABLES_ROOT)
        except Exception:
            raise ValueError(f'Table hors de /home/pinball/Tables: {raw}')
        if p.suffix.lower() != '.vpx' or not p.is_file():
            raise ValueError(f'Fichier VPX invalide: {p}')
        s = str(p)
        if s not in seen:
            seen.add(s)
            out.append(s)
    if not out:
        raise ValueError('Sélectionne au moins une table.')
    return out


def _status_payload():
    status = _read_json(STATUS_FILE, {'state': 'idle'})
    if not isinstance(status, dict):
        status = {'state': 'idle'}
    status.setdefault('state', 'idle')
    status.setdefault('updated_at', time.strftime('%Y-%m-%d %H:%M:%S'))
    return status


def _log_tail(status, limit=60000):
    log_path = str(status.get('log_file') or '').strip()
    if not log_path:
        return ''
    try:
        p = Path(log_path).resolve(strict=True)
        p.relative_to(LOG_DIR.resolve())
        size = p.stat().st_size
        with p.open('rb') as fh:
            if size > limit:
                fh.seek(size - limit)
            raw = fh.read()
        return raw.decode('utf-8', errors='replace')
    except Exception:
        return ''


def _page_body():
    tables = _table_inventory()
    options = ''.join(
        '<label class="mr-table-row" data-search="' + html.escape((t['name'] + ' ' + t['file']).lower(), quote=True) + '">'
        '<input type="checkbox" name="table" value="' + html.escape(t['path'], quote=True) + '">'
        '<span class="mr-table-main"><strong>' + html.escape(t['name']) + '</strong><small>' + html.escape(t['file']) + '</small></span>'
        '<span class="mr-presence">' + _mr_presence_badges(t.get('presence') or {}) + '</span>'
        '</label>'
        for t in tables
    )
    return f'''
<style>
.mr-wrap{{max-width:none;width:100%;margin:0 auto}} .mr-grid{{display:grid;grid-template-columns:minmax(420px,1.15fr) minmax(360px,.85fr);gap:18px}}
.mr-card{{background:rgba(20,10,34,.82);border:1px solid rgba(202,132,255,.24);border-radius:18px;padding:18px;box-shadow:0 14px 32px rgba(0,0,0,.22)}}
.mr-card h2{{margin-top:0}} .mr-toolbar{{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:10px}}
.mr-search{{flex:1;min-width:240px;padding:10px 12px;border-radius:10px;border:1px solid #624080;background:#0b0711;color:#fff}}
.mr-table-list{{height:470px;overflow:auto;border:1px solid rgba(255,255,255,.12);border-radius:12px;background:#08050d;padding:5px}}
.mr-table-row{{display:flex;align-items:flex-start;gap:10px;padding:9px;border-radius:9px;border-bottom:1px solid rgba(255,255,255,.06);cursor:pointer}}
.mr-table-row:hover{{background:rgba(151,69,230,.12)}} .mr-table-row input{{margin-top:3px;flex:0 0 auto}} .mr-table-row>.mr-table-main{{display:flex;flex:1 1 auto;min-width:0;flex-direction:column;gap:2px}}
.mr-presence{{margin-left:auto;display:flex;flex:0 0 auto;flex-wrap:wrap;justify-content:flex-end;gap:4px;max-width:55%}}
.mr-pres-chip{{display:inline-flex;align-items:center;gap:3px;padding:2px 6px;border-radius:999px;font-size:10px;line-height:1.25;font-weight:800;white-space:nowrap;border:1px solid rgba(255,255,255,.12);background:rgba(255,255,255,.04);color:#9d92aa}}
.mr-pres-chip.full{{border-color:rgba(118,227,154,.45);background:rgba(118,227,154,.12);color:#9cf0ba}}
.mr-pres-chip.partial{{border-color:rgba(255,148,31,.50);background:rgba(255,148,31,.12);color:#ffc06e}}
.mr-pres-chip.none{{opacity:.52}}
.mr-table-row small{{color:#a99ab8;word-break:break-all}} .mr-fields{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}}
.mr-field label,.mr-field>span{{display:block;color:#d5c5e3;font-size:12px;font-weight:800;margin-bottom:5px}} .mr-field input,.mr-field select{{width:100%;padding:10px;border-radius:10px;border:1px solid #63427e;background:#0b0711;color:#fff}}
.mr-checks{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:8px 0 14px}} .mr-check{{padding:10px;border:1px solid rgba(255,255,255,.12);border-radius:10px;background:rgba(255,255,255,.03)}}
.mr-actions{{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}} .mr-btn{{border:0;border-radius:10px;padding:10px 15px;font-weight:900;cursor:pointer;background:#ff941f;color:#180b00}} .mr-btn.secondary{{background:#7d4ab0;color:#fff}} .mr-btn.danger{{background:#a23b45;color:#fff}}
.mr-status{{font-size:16px;font-weight:900}} .mr-status[data-state="running"],.mr-status[data-state="completed"]{{color:#76e39a}} .mr-status[data-state="failed"]{{color:#ff7f88}} .mr-status[data-state="paused"],.mr-status[data-state="pausing"]{{color:#ffd36a}}
.mr-progress{{height:14px;background:#09060d;border-radius:999px;overflow:hidden;border:1px solid rgba(255,255,255,.12);margin:10px 0}} .mr-progress>div{{height:100%;width:0;background:linear-gradient(90deg,#8f49d8,#ff941f);transition:width .25s}}
.mr-log{{height:560px;overflow:auto;white-space:pre-wrap;background:#030205;color:#ded7e6;border:1px solid rgba(255,255,255,.12);border-radius:12px;padding:12px;font:12px/1.45 monospace}}
.mr-muted{{color:#a99ab8}} @media(max-width:980px){{.mr-grid{{grid-template-columns:1fr}}.mr-table-list{{height:360px}}}}
</style>
<div class="mr-wrap">
  <div class="card" style="margin-bottom:18px"><h1>🎥 PinCab Recorder</h1><p>Capture automatiquement les médias VPX. VPinFE est arrêté par le worker pendant le batch puis restauré à la fin.</p></div>
  <div class="mr-grid">
    <section class="mr-card">
      <h2>1. Tables <span class="mr-muted">({len(tables)} détectées)</span></h2>
      <div class="mr-toolbar"><input id="mr-search" class="mr-search" placeholder="Rechercher une table..."><button class="mr-btn secondary" type="button" id="mr-all">Tout</button><button class="mr-btn secondary" type="button" id="mr-none">Aucune</button></div>
      <div class="mr-table-list" id="mr-table-list">{options}</div>
    </section>
    <section class="mr-card">
      <h2>2. Capture</h2>
      <div class="mr-checks">
        <label class="mr-check"><input type="checkbox" class="mr-screen" value="playfield" checked> Playfield</label>
        <label class="mr-check"><input type="checkbox" class="mr-screen" value="backglass" checked> Backglass</label>
        <label class="mr-check"><input type="checkbox" class="mr-screen" value="fulldmd" checked> FullDMD</label>
        <label class="mr-check"><input type="checkbox" class="mr-screen" value="topper"> Topper</label>
      </div>
      <div class="mr-fields">
        <div class="mr-field"><span>Type</span><select id="mr-type"><option value="image">Image PNG</option><option value="video">Vidéo MP4</option><option value="both">Les deux — PNG + MP4</option></select></div>
        <div class="mr-field"><span>Attente après VPX</span><input id="mr-wait" type="number" min="0" max="300" step="1" value="20"></div>
        <div class="mr-field"><span>Durée vidéo</span><input id="mr-duration" type="number" min="1" max="120" step="1" value="10"></div>
        <div class="mr-field"><span>FPS</span><select id="mr-fps"><option>15</option><option>24</option><option>25</option><option selected>30</option><option>50</option><option>60</option></select></div>
        <div class="mr-field"><span>Qualité</span><select id="mr-quality"><option>low</option><option>medium</option><option selected>high</option><option>max</option></select></div>
        <div class="mr-field"><span>Encodeur</span><select id="mr-encoder"><option selected>auto</option><option>nvenc</option><option>x264</option></select></div>
        <div class="mr-field"><span>Source</span><select id="mr-source"><option selected>auto</option><option>screen</option><option>window</option></select></div>
        <div class="mr-field"><span>Mode table</span><select id="mr-mode"><option selected>auto</option><option>original</option><option>pup</option></select></div>
      </div>
      <label class="mr-check" style="display:block;margin-top:12px"><input id="mr-keep-other" type="checkbox"> Conserver aussi l'ancien média de l'autre type</label>
      <div class="mr-actions"><button class="mr-btn" id="mr-start">▶ Démarrer</button><button class="mr-btn secondary" id="mr-pause">⏸ Pause</button><button class="mr-btn secondary" id="mr-resume">▶ Reprendre</button><button class="mr-btn danger" id="mr-stop">■ Arrêter</button></div>
      <p id="mr-message" class="mr-muted"></p>
    </section>
  </div>
  <section class="mr-card" style="margin-top:18px">
    <div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap"><div><h2 style="margin-bottom:6px">3. État du batch</h2><div id="mr-status" class="mr-status" data-state="idle">IDLE</div></div><div id="mr-count" class="mr-muted">0 / 0</div></div>
    <div class="mr-progress"><div id="mr-progress-bar"></div></div>
    <div id="mr-current" class="mr-muted" style="margin-bottom:10px">Aucune table active.</div>
    <pre id="mr-log" class="mr-log">Aucun journal.</pre>
  </section>
</div>
<script>
(()=>{{
 const q=s=>document.querySelector(s), qa=s=>[...document.querySelectorAll(s)];
 const msg=(t,bad=false)=>{{q('#mr-message').textContent=t||'';q('#mr-message').style.color=bad?'#ff7f88':'';}};
 q('#mr-search').addEventListener('input',e=>{{const s=e.target.value.trim().toLowerCase();qa('.mr-table-row').forEach(r=>r.style.display=!s||r.dataset.search.includes(s)?'flex':'none');}});
 q('#mr-all').onclick=()=>qa('.mr-table-row').filter(r=>r.style.display!=='none').forEach(r=>r.querySelector('input').checked=true);
 q('#mr-none').onclick=()=>qa('.mr-table-row input').forEach(x=>x.checked=false);
 const mrSyncType=()=>{{
   const both=q('#mr-type').value==='both';
   const keep=q('#mr-keep-other');
   if(both){{
     keep.checked=true;
     keep.disabled=true;
   }}else{{
     keep.disabled=false;
   }}
 }};
 q('#mr-type').addEventListener('change',mrSyncType);
 mrSyncType();
 async function post(url,data){{const r=await fetch(url,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(data)}});const j=await r.json().catch(()=>({{ok:false,error:'Réponse invalide'}}));if(!r.ok||j.ok===false)throw new Error(j.error||('HTTP '+r.status));return j;}}
 q('#mr-start').onclick=async()=>{{try{{msg('Création du job...');const tables=qa('.mr-table-row input:checked').map(x=>x.value);const screens=qa('.mr-screen:checked').map(x=>x.value);await post('/api/media-recorder/start',{{tables,screens,type:q('#mr-type').value,wait:q('#mr-wait').value,duration:q('#mr-duration').value,fps:q('#mr-fps').value,quality:q('#mr-quality').value,encoder:q('#mr-encoder').value,source:q('#mr-source').value,mode:q('#mr-mode').value,keep_other_type:q('#mr-keep-other').checked}});msg('Job envoyé au worker.');refresh();}}catch(e){{msg(e.message,true);}}}};
 q('#mr-pause').onclick=()=>post('/api/media-recorder/control',{{action:'pause'}}).then(()=>msg('Pause demandée après la table courante.')).catch(e=>msg(e.message,true));
 q('#mr-resume').onclick=()=>post('/api/media-recorder/control',{{action:'resume'}}).then(()=>msg('Reprise demandée.')).catch(e=>msg(e.message,true));
 q('#mr-stop').onclick=()=>post('/api/media-recorder/control',{{action:'stop'}}).then(()=>msg('Arrêt demandé.')).catch(e=>msg(e.message,true));
 async function refresh(){{try{{const r=await fetch('/api/media-recorder/status',{{cache:'no-store'}});const j=await r.json();const s=j.status||{{}};const st=s.state||'idle';q('#mr-status').textContent=st.toUpperCase();q('#mr-status').dataset.state=st;const total=Number(s.total||0),idx=Number(s.index||0);q('#mr-count').textContent=idx+' / '+total;q('#mr-progress-bar').style.width=(total?Math.max(0,Math.min(100,idx*100/total)):0)+'%';q('#mr-current').textContent=s.current_table||s.message||'Aucune table active.';const log=q('#mr-log');const atBottom=(log.scrollHeight-log.scrollTop-log.clientHeight)<80;log.textContent=j.log||'Aucun journal.';if(atBottom)log.scrollTop=log.scrollHeight;}}catch(e){{}}}}
 refresh();setInterval(refresh,1500);
}})();
</script>
'''


def register(app, page):
    @app.route('/tools/media-recorder')
    def pincabos_media_recorder_page():
        return page('PinCab Recorder', _page_body())

    @app.route('/api/media-recorder/status')
    def pincabos_media_recorder_status():
        status = _status_payload()
        return jsonify({'ok': True, 'status': status, 'log': _log_tail(status)})

    @app.route('/api/media-recorder/start', methods=['POST'])
    def pincabos_media_recorder_start():
        current = _status_payload()
        if str(current.get('state')) in ACTIVE_STATES:
            return jsonify({'ok': False, 'error': 'Un batch Recorder est déjà actif.'}), 409
        payload = request.get_json(silent=True) or {}
        try:
            tables = _validate_tables(payload.get('tables'))
            screens = [str(x) for x in (payload.get('screens') or []) if str(x) in ALLOWED_SCREENS]
            if not screens:
                raise ValueError('Sélectionne au moins un écran.')
            media_type = str(payload.get('type') or 'image')
            if media_type not in ALLOWED_TYPES:
                raise ValueError('Type de média invalide.')
            mode = str(payload.get('mode') or 'auto')
            source = str(payload.get('source') or 'auto')
            quality = str(payload.get('quality') or 'high')
            encoder = str(payload.get('encoder') or 'auto')
            if mode not in ALLOWED_MODES or source not in ALLOWED_SOURCES or quality not in ALLOWED_QUALITIES or encoder not in ALLOWED_ENCODERS:
                raise ValueError('Paramètre Recorder invalide.')
            job_id = time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8]
            job = {
                'id': job_id,
                'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'tables': tables,
                'screens': screens,
                'type': media_type,
                'wait': _safe_float(payload.get('wait'), 20, 0, 300),
                'duration': _safe_float(payload.get('duration'), 10, 1, 120),
                'fps': _safe_int(payload.get('fps'), 30, ALLOWED_FPS),
                'quality': quality,
                'encoder': encoder,
                'source': source,
                'mode': mode,
                'keep_other_type': (media_type == 'both') or bool(payload.get('keep_other_type', False)),
            }
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            log_file = LOG_DIR / f'{job_id}.log'
            _atomic_json(CONTROL_FILE, {'action': ''})
            _atomic_json(JOB_FILE, job)
            _atomic_json(STATUS_FILE, {
                'state': 'queued', 'job_id': job_id, 'index': 0, 'total': len(tables),
                'current_table': '', 'message': 'Job en attente du worker.',
                'log_file': str(log_file), 'updated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            })
            return jsonify({'ok': True, 'job_id': job_id})
        except ValueError as exc:
            return jsonify({'ok': False, 'error': str(exc)}), 400
        except Exception as exc:
            return jsonify({'ok': False, 'error': f'Création du job impossible: {exc}'}), 500

    @app.route('/api/media-recorder/control', methods=['POST'])
    def pincabos_media_recorder_control():
        action = str((request.get_json(silent=True) or {}).get('action') or '').strip().lower()
        if action not in {'pause', 'resume', 'stop'}:
            return jsonify({'ok': False, 'error': 'Action invalide.'}), 400
        _atomic_json(CONTROL_FILE, {'action': action, 'at': time.strftime('%Y-%m-%d %H:%M:%S')})
        return jsonify({'ok': True, 'action': action})
