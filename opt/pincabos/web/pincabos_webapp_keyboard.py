"""PinCabOS system keyboard WebApp page and API."""
from __future__ import annotations

import hmac
import html
import json
import secrets
import subprocess
from typing import Any, Callable

from flask import jsonify, request, session

MARKER = 'PCO-KEYBOARD-WIDGET-V1'
TOOL = '/usr/local/sbin/pincabos-keyboard-layout'


def _tool(*args: str, timeout: int = 25) -> dict[str, Any]:
    try:
        proc = subprocess.run(['/usr/bin/sudo', '-n', TOOL, *args], text=True, capture_output=True, timeout=timeout, check=False)
    except Exception as error:
        return {'ok': False, 'error': str(error)}
    raw = (proc.stdout or proc.stderr or '').strip()
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            if proc.returncode != 0:
                data.setdefault('ok', False)
            return data
    except Exception:
        pass
    return {'ok': False, 'error': raw or f'Commande clavier en erreur ({proc.returncode}).'}


def _csrf() -> str:
    token = session.get('_pco_keyboard_csrf')
    if not isinstance(token, str) or len(token) < 24:
        token = secrets.token_urlsafe(32)
        session['_pco_keyboard_csrf'] = token
    return token


def _csrf_ok() -> bool:
    supplied = request.headers.get('X-PCO-Keyboard-CSRF', '')
    expected = session.get('_pco_keyboard_csrf', '')
    return isinstance(expected, str) and bool(expected) and hmac.compare_digest(expected, supplied)


def _option(code: str, label: str, selected: str) -> str:
    return f'<option value="{html.escape(code)}"{" selected" if code == selected else ""}>{html.escape(label)} [{html.escape(code)}]</option>'


def _page_html(status: dict[str, Any], layouts: list[dict[str, str]], token: str) -> str:
    configured = status.get('configured') if isinstance(status.get('configured'), dict) else {}
    selected_layout = str(configured.get('layout') or 'ca')
    selected_variant = str(configured.get('variant') or '')
    options = ''.join(_option(str(row.get('code', '')), str(row.get('label', '')), selected_layout) for row in layouts if row.get('code'))
    live = status.get('live') if isinstance(status.get('live'), dict) else {}
    live_text = 'Indisponible'
    if live.get('available'):
        live_text = f"{live.get('layout', '?')} {live.get('variant', '')}".strip()
    elif live.get('detail'):
        live_text = str(live.get('detail'))
    status_error = '' if status.get('ok') else f'<div class="kbd-alert bad">Lecture système impossible : {html.escape(str(status.get("error", "inconnue")))}</div>'
    return f'''<!-- {MARKER} -->
<style>
.kbd-page{{max-width:980px;margin:0 auto;padding:22px 16px 44px;color:#f8f2ff}}
.kbd-hero,.kbd-card{{background:linear-gradient(145deg,#1c0d2d,#100617);border:1px solid #5e3182;border-radius:16px;box-shadow:0 14px 36px rgba(0,0,0,.28)}}
.kbd-hero{{padding:22px;margin-bottom:16px}}.kbd-hero h1{{margin:0;color:#ffbd00;font-size:1.7rem}}.kbd-hero p{{margin:8px 0 0;color:#d1c0dd}}
.kbd-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin:16px 0}}.kbd-card{{padding:15px}}.kbd-card h2{{font-size:1rem;color:#ffbd00;margin:0 0 8px}}.kbd-value{{font-size:1.2rem;font-weight:800;word-break:break-word}}
.kbd-form{{display:grid;gap:14px}}.kbd-choices{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:9px}}.kbd-choice,.kbd-button{{border:1px solid #74409d;border-radius:10px;background:#251037;color:#fff;padding:11px 12px;cursor:pointer;font-weight:700;text-align:left}}.kbd-choice:hover,.kbd-choice.active{{border-color:#ffb000;background:#3a1757}}.kbd-button{{background:#ff7900;color:#190a21;border-color:#ffbd00;text-align:center}}.kbd-button:disabled{{opacity:.55;cursor:wait}}
.kbd-label{{display:grid;gap:6px;font-weight:700;color:#f7eaff}}select,input{{border:1px solid #74409d;background:#0d0713;color:#fff;border-radius:9px;padding:10px;font:inherit}}.kbd-hint{{font-size:.88rem;color:#cbb9d7;margin:0}}.kbd-alert{{border-radius:10px;padding:11px 12px;margin:12px 0}}.kbd-alert.good{{background:#123624;border:1px solid #38b66c}}.kbd-alert.bad{{background:#481526;border:1px solid #e35a79}}.kbd-test{{min-height:52px;resize:vertical}}code{{color:#ffd16a}}@media(max-width:600px){{.kbd-page{{padding:12px}}.kbd-hero{{padding:16px}}}}
</style>
<main class="kbd-page" data-pco-keyboard="1" data-csrf="{html.escape(token)}">
  <section class="kbd-hero"><h1>⌨ Clavier système</h1><p>Choisis une disposition XKB. Le changement est conservé pour le système et appliqué tout de suite à la session graphique lorsque disponible.</p></section>
  {status_error}
  <section class="kbd-grid">
    <article class="kbd-card"><h2>Configuration permanente</h2><div class="kbd-value" id="kbd-configured">{html.escape(selected_layout)} {html.escape(selected_variant)}</div><p class="kbd-hint">/etc/default/keyboard + règle X11 PinCabOS</p></article>
    <article class="kbd-card"><h2>Session graphique actuelle</h2><div class="kbd-value" id="kbd-live">{html.escape(live_text)}</div><p class="kbd-hint">DISPLAY :0, utilisateur pinball</p></article>
  </section>
  <section class="kbd-card"><h2>Disposition à utiliser</h2><div class="kbd-form">
    <div class="kbd-choices">
      <button class="kbd-choice" type="button" data-layout="ca" data-variant="">Français Canada<br><small>ca</small></button>
      <button class="kbd-choice" type="button" data-layout="us" data-variant="">English US<br><small>us</small></button>
      <button class="kbd-choice" type="button" data-layout="fr" data-variant="">Français France<br><small>fr</small></button>
      <button class="kbd-choice" type="button" data-layout="gb" data-variant="">English UK<br><small>gb</small></button>
    </div>
    <label class="kbd-label">Autre disposition <select id="kbd-layout">{options}</select></label>
    <label class="kbd-label">Variante (facultative) <select id="kbd-variant"><option value="">Disposition standard</option></select></label>
    <p class="kbd-hint">La liste vient des règles XKB installées sur cette machine. Teste le résultat dans le champ ci-dessous avant de quitter la page.</p>
    <input id="kbd-test" class="kbd-test" autocomplete="off" placeholder="Zone de test : tape ici après l’application.">
    <button id="kbd-apply" class="kbd-button" type="button">Appliquer le clavier système</button>
    <div id="kbd-result" aria-live="polite"></div>
  </div></section>
</main>
<script>
(()=>{{
 const root=document.querySelector('[data-pco-keyboard]'); if(!root)return;
 const token=root.dataset.csrf, layout=document.getElementById('kbd-layout'), variant=document.getElementById('kbd-variant'), apply=document.getElementById('kbd-apply'), result=document.getElementById('kbd-result');
 const esc=(v)=>String(v??'').replace(/[&<>"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));
 async function variants(){{ const r=await fetch('/api/keyboard/variants?layout='+encodeURIComponent(layout.value),{{cache:'no-store'}}); const d=await r.json(); variant.innerHTML='<option value="">Disposition standard</option>'; if(d.ok) for(const x of d.variants||[]){{const o=document.createElement('option');o.value=x.code;o.textContent=`${{x.label}} [${{x.code}}]`;variant.appendChild(o);}} }}
 async function applyLayout(){{ apply.disabled=true; result.innerHTML=''; try{{const r=await fetch('/keyboard/apply',{{method:'POST',headers:{{'Content-Type':'application/json','X-PCO-Keyboard-CSRF':token}},body:JSON.stringify({{layout:layout.value,variant:variant.value}})}});const d=await r.json();if(!r.ok||!d.ok)throw new Error(d.error||'Application refusée.');const c=d.configured||{{}};document.getElementById('kbd-configured').textContent=((c.layout||'')+' '+(c.variant||'')).trim();const l=d.live||{{}};document.getElementById('kbd-live').textContent=l.available?(((l.layout||'')+' '+(l.variant||'')).trim()):'Configuration enregistrée — reconnecte ou redémarre la session';const warn=(d.warnings||[]).map(esc).join('<br>');result.innerHTML='<div class="kbd-alert good"><strong>Clavier appliqué.</strong>'+ (warn?'<br>'+warn:'') +'</div>';}}catch(e){{result.innerHTML='<div class="kbd-alert bad">'+esc(e.message||e)+'</div>';}}finally{{apply.disabled=false;}} }}
 layout.addEventListener('change',variants); document.querySelectorAll('.kbd-choice').forEach(b=>b.addEventListener('click',async()=>{{layout.value=b.dataset.layout;await variants();variant.value=b.dataset.variant||'';}})); apply.addEventListener('click',applyLayout); variants().then(()=>{{variant.value={json.dumps(selected_variant)};}}).catch(()=>{{}});
}})();
</script>'''


def register_keyboard_routes(app: Any, page: Callable[[str, str], str]) -> None:
    def keyboard_page() -> str:
        status = _tool('status')
        listing = _tool('layouts')
        layouts = listing.get('layouts') if isinstance(listing.get('layouts'), list) else []
        return page('Clavier système', _page_html(status, layouts, _csrf()))

    def variants_api():
        layout = str(request.args.get('layout', '')).strip()
        return jsonify(_tool('variants', layout))

    def status_api():
        return jsonify(_tool('status'))

    def apply_api():
        if not _csrf_ok():
            return jsonify({'ok': False, 'error': 'Session clavier invalide. Recharge la page.'}), 403
        payload = request.get_json(silent=True) or {}
        layout = str(payload.get('layout', '')).strip()
        variant = str(payload.get('variant', '')).strip()
        data = _tool('set', layout, variant or '-', timeout=35)
        return jsonify(data), (200 if data.get('ok') else 400)

    routes = [
        ('pco_keyboard_page', '/keyboard', keyboard_page, ['GET']),
        ('pco_keyboard_variants', '/api/keyboard/variants', variants_api, ['GET']),
        ('pco_keyboard_status', '/api/keyboard/status', status_api, ['GET']),
        ('pco_keyboard_apply', '/keyboard/apply', apply_api, ['POST']),
    ]
    for endpoint, rule, view, methods in routes:
        if endpoint not in app.view_functions:
            app.add_url_rule(rule, endpoint=endpoint, view_func=view, methods=methods)
