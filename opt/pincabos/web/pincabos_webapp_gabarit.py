"""Gabarit commun de la WebApp PinCabOS : `page(title, body)` (entête, menu, styles, pied de page), état et
bascule de l'écran WebApp, pied de page support, état d'achèvement de la première exécution.

Code déplacé tel quel depuis app.py (PINCABOS_WEBAPP_MODULES_V1, lot 12). Pas de routes ici : les modules de
pages reçoivent `page` par `register(app, page)` et app.py la réexporte pour les modules historiques qui la
lisent dans ses globals.
"""
from __future__ import annotations

from pathlib import Path

from pincabos_webapp_admin_pages import pincabos_footer_supporters_inline_html
from pincabos_webapp_core import esc, get_ip, pincabos_version
from pincabos_webapp_firstrun import firstrun_load_cfg, firstrun_required_keys


# PINCABOS_WEBAPP_SCREEN_STATE_V3_BEGIN
PCO_WEBAPP_SCREEN_STATE_FILE = Path(
    "/opt/pincabos/config/webapp-screen-autostart.conf"
)


def pincabos_webapp_screen_state():
    """
    État mémorisé des écrans WebApp demandés par PinCabOS.
    Un bouton glow seulement lorsque sa valeur vaut 1.
    """
    state = {"playfield": "0", "backglass": "0"}

    try:
        if not PCO_WEBAPP_SCREEN_STATE_FILE.exists():
            return state

        for line in PCO_WEBAPP_SCREEN_STATE_FILE.read_text(
            errors="replace"
        ).splitlines():
            line = line.strip()

            if not line or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip().upper()
            value = "1" if value.strip() == "1" else "0"

            if key == "PLAYFIELD":
                state["playfield"] = value
            elif key == "BACKGLASS":
                state["backglass"] = value

    except Exception:
        return {"playfield": "0", "backglass": "0"}

    return state


def webapp_screen_toggle_html():
    state = pincabos_webapp_screen_state()

    pf_class = (
        "screen-toggle-on"
        if state["playfield"] == "1"
        else "screen-toggle-off"
    )
    bg_class = (
        "screen-toggle-on"
        if state["backglass"] == "1"
        else "screen-toggle-off"
    )

    pf_pressed = "true" if state["playfield"] == "1" else "false"
    bg_pressed = "true" if state["backglass"] == "1" else "false"

    return f"""
    <form action="/toggle-webapp-screen" method="post" class="nav-inline-form">
      <input type="hidden" name="screen" value="playfield">
      <button
        class="button nav-action screen-toggle-btn {pf_class}"
        type="submit"
        aria-pressed="{pf_pressed}"
        title="Afficher ou retirer PinCabOS du Playfield">
        PlayField
      </button>
    </form>

    <form action="/toggle-webapp-screen" method="post" class="nav-inline-form">
      <input type="hidden" name="screen" value="backglass">
      <button
        class="button nav-action screen-toggle-btn {bg_class}"
        type="submit"
        aria-pressed="{bg_pressed}"
        title="Afficher ou retirer PinCabOS du Backglass">
        BackGlass
      </button>
    </form>
"""
# PINCABOS_WEBAPP_SCREEN_STATE_V3_END


def safe_file_text(path, fallback=""):
    try:
        f = Path(path)
        if f.exists():
            return f.read_text(errors="replace")
    except Exception as e:
        return f"Erreur lecture {path}: {e}"
    return fallback
def pincabos_support_footer_html():
    ver = pincabos_version() if "pincabos_version" in globals() else {}
    qr_name = "pcbo_pay_qr_bbb5611b723f953dc3fad1e42e7dbd66fe9fa8d53de4293c.png"

    def v(key, fallback=""):
        try:
            return esc(str(ver.get(key, fallback) or fallback))
        except Exception:
            return esc(str(fallback))

    try:
        supporters_html = pincabos_footer_supporters_inline_html()
    except Exception:
        supporters_html = (
            '<section id="pincabos-footer-supporters-inline-v14" '
            'class="pincabos-footer-supporters-inline-v14">'
            '<h2>Testeurs / Soutiens fondateurs</h2>'
            '<p>Merci aux personnes qui soutiennent PinCabOS.</p>'
            '</section>'
        )

    return f"""
<!-- PINCABOS_FOOTER_LAYOUT_V14_1 -->
<div class="footer pincabos-support-footer-safe pco-footer-layout-v14"
     id="pincabos-support-footer-static">

  <!-- PINCABOS_FOOTER_QR_DIRECT_LEFT_V11 -->
  <div class="pincabos-support-qr-safe pco-footer-qr-direct-left-v11">
      <h3 class="pincabos-support-title-left-v3">Soutenir PinCabOS</h3>
    <img src="/static/pincabos-assets/{esc(qr_name)}" alt="QR Code PayPal PinCabOS">
    <div class="pincabos-support-qr-label-safe">QR Code PayPal PinCabOS</div>
  </div>


  <div class="pco-footer-main-v14">
    <div class="pincabos-release-notes-safe">
      <h2>Notes de version</h2>
      <div class="pincabos-release-grid-safe">
        <p><strong>Nom :</strong> {v("name", "PinCabOS")}</p>
        <p><strong>Version :</strong> {v("version", "Development")}</p>
        <p><strong>Build :</strong> {v("build", "dev")}</p>
        <p><strong>Canal :</strong> {v("channel", ver.get("update_channel", ""))}</p>
        <p><strong>Codename :</strong> {v("codename", "")}</p>
        <p><strong>Auteur :</strong> {v("author", "Karots Sugarpie")}</p>
        <p><strong>Site :</strong> pincabos.cc</p>
      </div>
    </div>

    <div class="pincabos-support-text-safe">
<p>Si vous aimez PinCabOS,<br>vous pouvez me le montrer en offrant ce que vous voulez.<br>Merci pour votre soutien.</p>
      <div class="pincabos-paypal-form-safe">
        <form action="https://www.paypal.com/ncp/payment/SE79XX45T2NBG" method="post" target="_blank">
          <input class="pp-SE79XX45T2NBG-safe" type="submit" value="Faire un don">
          <img class="pincabos-paypal-cards-safe" src="https://www.paypalobjects.com/images/Debit_Credit_APM.svg" alt="cards">
          <section class="pincabos-paypal-powered-safe">Optimisé par <img src="https://www.paypalobjects.com/paypal-ui/logos/svg/paypal-wordmark-color.svg" alt="paypal"></section>
        </form>
      </div>
    </div>
  </div>

  <aside class="pco-footer-right-v14" aria-label="Soutien et contributeurs">
    {supporters_html}
  </aside>
</div>
"""


def page(title, body):
    ip = get_ip()
    logo_html = ""
    if Path("/opt/pincabos/web/static/pincabos-logo.png").exists():
        logo_html = '<img src="/static/pincabos-logo.png" class="logo" alt="PinCabOS Logo">'

    return f"""<!doctype html>
<html>
<head>
  <title>PinCabOS - {esc(title)}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {{
      margin: 0;
      font-family: Arial, sans-serif;
      background:
        linear-gradient(rgba(0,0,0,0.72), rgba(0,0,0,0.72)),
        url('/static/pincabos-logo.png') center center / min(70vw, 760px) auto no-repeat fixed,
        #000000;
      color: #fff;
      padding: 30px;
    }}
    .top {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 20px;
      margin-bottom: 25px;
      background: rgba(29, 11, 46, 0.65);
      border: 1px solid rgba(255,122,0,0.65);
      border-radius: var(--pco-appearance-card-radius, 18px);
      padding: 14px 18px;
      box-shadow: 0 0 25px rgba(255, 122, 0, 0.20);
    }}
    .brand-left {{
      display: flex;
      align-items: center;
      gap: 16px;
      min-width: 0;
    }}
    .logo {{
      max-width: 190px;
      width: 190px;
      height: auto;
      filter: drop-shadow(0 0 20px rgba(255,122,0,0.6));
      flex-shrink: 0;
    }}
    .brand-title {{
      color: var(--pco-appearance-accent, #ffb000);
      font-size: 20px;
      font-weight: bold;
      text-shadow: 0 0 15px rgba(255,122,0,0.75);
      white-space: normal;
      line-height: 1.25;
    }}
    .brand-subtitle {{
      color: var(--pco-appearance-muted-text, #d8b8ff);
      font-size: 15px;
      font-weight: normal;
      margin-top: 4px;
      text-shadow: 0 0 12px rgba(216,184,255,0.55);
    }}
    h1 {{
      display: none;
    }}
    .subtitle {{
      display: none;
    }}
    .nav {{
      text-align: right;
      margin-bottom: 0;
      flex-shrink: 0;
    }}
    @media (max-width: 850px) {{
      .top {{
        flex-direction: column;
        align-items: center;
        text-align: center;
      }}
      .brand-left {{
        flex-direction: column;
      }}
      .nav {{
        text-align: center;
      }}
    }}
    .nav a, .button {{
      display: inline-block;
      background: var(--pco-appearance-button-bg, #ff7a00);
      color: var(--pco-appearance-button-text, #160020);
      padding: 10px 15px;
      border-radius: var(--pco-appearance-button-radius, 10px);
      text-decoration: none;
      font-weight: bold;
      margin: 5px;
      border: none;
      cursor: pointer;
    }}
    .secondary {{
      background: var(--pco-appearance-secondary-bg, #5f2a91) !important;
      color: var(--pco-appearance-secondary-text, white) !important;
      border: 1px solid var(--pco-appearance-accent2, #ff7a00) !important;
    }}
    .nav a.active {{
      background: var(--pco-appearance-nav-active-bg, #ff7a00) !important;
      color: var(--pco-appearance-nav-active-text, #160020) !important;
      border: 1px solid var(--pco-appearance-accent, #ffb000) !important;
      box-shadow: 0 0 18px rgba(255,122,0,0.8);
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 20px;
    }}
    .card {{
      background: var(--pco-appearance-card-bg, rgba(29, 11, 46, 0.76));
      border: 1px solid var(--pco-appearance-card-border, #ff7a00);
      border-radius: var(--pco-appearance-card-radius, 18px);
      padding: 22px;
      box-shadow: var(--pco-appearance-card-shadow, 0 0 25px rgba(255, 122, 0, 0.25));
    }}
    .card h2 {{
      margin-top: 0;
      color: var(--pco-appearance-accent, #ffb000);
    }}
    .ok {{ color: #00ff99; font-weight: bold; }}
    .bad {{ color: #ff5555; font-weight: bold; }}
    .warn {{ color: var(--pco-appearance-accent, #ffb000); font-weight: bold; }}
    code {{
      background: #000;
      color: var(--pco-appearance-accent, #ffb000);
      padding: 4px 8px;
      border-radius: 6px;
      display: inline-block;
      margin: 2px 0;
    }}
    pre {{
      white-space: pre-wrap;
      background: var(--pco-appearance-input-bg, #050007);
      color: var(--pco-appearance-input-text, #eee);
      padding: 15px;
      border-radius: 12px;
      border: 1px solid var(--pco-appearance-purple, #5f2a91);
      height: 520px;
      overflow-y: scroll;
      font-size: 13px;
    }}
    .progress-wrap {{
      background: var(--pco-appearance-input-bg, #050007);
      border: 1px solid var(--pco-appearance-card-border, #ff7a00);
      border-radius: 14px;
      overflow: hidden;
      height: 30px;
      margin: 15px 0;
      box-shadow: 0 0 15px rgba(255,122,0,0.4);
    }}
    .progress-bar {{
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, #ff7a00, #ff00cc, #00eaff);
      color: #000;
      font-weight: bold;
      text-align: center;
      line-height: 30px;
      transition: width 0.5s ease;
    }}
    .running {{
      animation: glow 1.2s infinite alternate;
    }}
    @keyframes glow {{
      from {{ filter: brightness(1); }}
      to {{ filter: brightness(1.5); }}
    }}
    .footer {{
      margin-top: 30px;
      color: var(--pco-appearance-accent, #ffb000);
      font-size: 14px;
      opacity: 0.9;
      text-align: center;
    }}

    .nav-tools form {{
      display: inline-flex;
      gap: 6px;
      align-items: center;
      margin: 0;
    }}

    .nav-tools select {{
      padding: 6px;
      border-radius: 8px;
      border: 1px solid var(--pco-appearance-card-border, #ff7a00);
      background: #160020;
      color: #fff;
    }}

    .pincabos-nav a,
    .pincabos-nav button {{
      min-height: 38px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      line-height: 1;
    }}


    .pincabos-nav {{
      margin: 18px auto 0 auto;
      max-width: 1220px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}

    .nav-row {{
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      align-items: center;
      gap: 8px;
    }}

    .nav-pages {{
      padding: 10px;
      border-radius: var(--pco-appearance-card-radius, 18px);
      background: rgba(12, 0, 22, 0.58);
      border: 1px solid rgba(255, 122, 0, 0.25);
      box-shadow: 0 0 22px rgba(95, 42, 145, 0.22);
    }}

    .nav-tools-clean {{
      padding: 10px;
      border-radius: var(--pco-appearance-card-radius, 18px);
      background: rgba(255, 122, 0, 0.07);
      border: 1px solid rgba(95, 42, 145, 0.45);
      box-shadow: inset 0 0 18px rgba(0, 0, 0, 0.18);
    }}

    .nav-inline-form {{
      margin: 0;
      display: inline-flex;
      align-items: center;
    }}

    .nav-label {{
      color: var(--pco-appearance-accent, #ffb000);
      font-weight: 800;
      padding: 0 4px;
      text-shadow: 0 0 10px rgba(255, 122, 0, 0.45);
    }}

    .nav-action {{
      white-space: nowrap;
    }}

    .pincabos-nav a,
    .pincabos-nav button {{
      min-height: 38px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      line-height: 1;
    }}


     .top-language-widget {{
      position: absolute;
      top: 18px;
      right: 22px;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: flex-end;
      gap: 8px;
      width: min(330px, calc(100vw - 44px));
      padding: 8px 10px;
      border-radius: 14px;
      background: rgba(10, 0, 20, 0.96);
      border: 1px solid rgba(255, 122, 0, 0.45);
      box-shadow: 0 0 18px rgba(255, 122, 0, 0.20);
      z-index: 999;
    }}

    /* PINCABOS_LIVE_STATUS_BODY_ROOT_V10 */
    /* The status host belongs directly under <body>, not inside the navigation.
       This avoids transformed/stacked parent containers and anchors the compact
       card directly below Language at the far right. */
    .pco-impexp-live-menu-row {{
      display:none !important;
    }}
    #pco-impexp-live-overlay-root {{
      display:none;
      position:fixed !important;
      z-index:2147483000 !important;
      top:78px !important;
      right:18px !important;
      width:min(440px, calc(100vw - 36px)) !important;
      margin:0 !important;
      padding:0 !important;
      background:transparent !important;
      border:0 !important;
      box-shadow:none !important;
      pointer-events:none !important;
    }}
    #pco-impexp-live-overlay-root.is-active {{
      display:block !important;
    }}
    #pco-impexp-live-overlay-root .pco-impexp-menu-status {{
      display:grid !important;
      grid-template-columns:minmax(0,1fr) auto;
      grid-template-areas:
        "title pct"
        "current counter"
        "track track";
      gap:4px 12px;
      align-items:center;
      width:100% !important;
      margin:0 !important;
      padding:11px 13px !important;
      min-height:0 !important;
      border:1px solid rgba(255,132,20,.58) !important;
      border-radius:16px !important;
      background:linear-gradient(180deg,rgba(132,61,10,.98),rgba(101,42,7,.98)) !important;
      box-shadow:0 10px 22px rgba(0,0,0,.38) !important;
      color:#fff;
      text-align:left;
      pointer-events:auto !important;
    }}
    #pco-impexp-live-overlay-root .pcos-bxp6-titleline,
    #pco-impexp-live-overlay-root .pcos-bip-global-head {{
      grid-area:title;
      display:flex;
      align-items:center;
      gap:7px;
      min-width:0;
    }}
    #pco-impexp-live-overlay-root .pcos-bxp6-pct,
    #pco-impexp-live-overlay-root .pcos-bip-global-pct {{
      grid-area:pct;
      justify-self:end;
      font-size:1.05rem;
      font-weight:900;
      line-height:1;
    }}
    #pco-impexp-live-overlay-root .pcos-bxp6-title,
    #pco-impexp-live-overlay-root .pcos-bip-global-title {{
      font-size:.88rem;
      font-weight:900;
      letter-spacing:.03em;
      text-transform:uppercase;
    }}
    #pco-impexp-live-overlay-root .pcos-bxp6-current,
    #pco-impexp-live-overlay-root .pcos-bip-global-current {{
      grid-area:current;
      display:block;
      min-width:0;
      margin:0;
      overflow:hidden;
      white-space:nowrap;
      text-overflow:ellipsis;
      font-size:.84rem;
      font-weight:700;
      line-height:1.2;
    }}
    #pco-impexp-live-overlay-root .pcos-bxp6-counter,
    #pco-impexp-live-overlay-root .pcos-bip-global-count {{
      grid-area:counter;
      display:block;
      justify-self:end;
      margin:0;
      white-space:nowrap;
      font-size:.77rem;
      font-weight:700;
      opacity:.95;
    }}
    #pco-impexp-live-overlay-root .pcos-bxp6-track,
    #pco-impexp-live-overlay-root .pcos-bip-global-track {{
      grid-area:track;
      display:block;
      width:100%;
      height:5px;
      margin:2px 0 0 !important;
      border-radius:999px;
      overflow:hidden;
    }}

    /* PINCABOS_LIVE_STOP_BUTTON_V11 */
    #pco-impexp-live-overlay-root .pcos-bxp6-actions,
    #pco-impexp-live-overlay-root .pcos-bip-global-actions {{
      grid-area:pct;
      display:flex;
      align-items:center;
      justify-self:end;
      gap:8px;
    }}
    #pco-impexp-live-overlay-root .pcos-live-stop {{
      border:1px solid rgba(255,216,160,.8);
      border-radius:8px;
      padding:4px 8px;
      background:rgba(53,14,7,.72);
      color:#fff3e1;
      font:inherit;
      font-size:.72rem;
      font-weight:900;
      line-height:1;
      cursor:pointer;
    }}
    #pco-impexp-live-overlay-root .pcos-live-stop:hover:not(:disabled) {{
      filter:brightness(1.18);
    }}
    #pco-impexp-live-overlay-root .pcos-live-stop:disabled {{
      opacity:.58;
      cursor:wait;
    }}

    @media (max-width:700px) {{
      #pco-impexp-live-overlay-root {{
        top:66px !important;
        right:10px !important;
        width:calc(100vw - 20px) !important;
      }}
    }}
    #pco-impexp-live-menu-slot .pco-impexp-menu-status {{
      width:100%;
    }}

    .top-language-widget span {{
      color: var(--pco-appearance-accent, #ffb000);
      font-weight: 800;
      font-size: 13px;
      white-space: nowrap;
      text-shadow: 0 0 10px rgba(255,122,0,0.45);
    }}

    .top-language-widget select {{
      padding: 7px 10px;
      border-radius: var(--pco-appearance-button-radius, 10px);
      border: 1px solid var(--pco-appearance-card-border, #ff7a00);
      background: #160020;
      color: #fff;
      font-weight: 700;
      outline: none;
    }}

    #google_translate_element {{
      display: none;
    }}

    .goog-te-banner-frame.skiptranslate,
    iframe.goog-te-banner-frame {{
      display: none !important;
    }}

    body {{
      top: 0 !important;
    }}

    .goog-logo-link,
    .goog-te-gadget span {{
      display: none !important;
    }}

    .goog-te-gadget {{
      color: transparent !important;
      font-size: 0 !important;
    }}


    .import-progress-box {{
      display: none;
      margin-top: 14px;
      padding: 12px;
      border-radius: 14px;
      border: 1px solid rgba(255, 122, 0, 0.45);
      background: rgba(10, 0, 20, 0.72);
      box-shadow: 0 0 18px rgba(255, 122, 0, 0.18);
    }}

    .import-progress-label {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      color: var(--pco-appearance-accent, #ffb000);
      font-weight: 800;
      margin-bottom: 8px;
    }}

    .import-progress-track {{
      height: 18px;
      background: #160020;
      border: 1px solid var(--pco-appearance-purple, #5f2a91);
      border-radius: 999px;
      overflow: hidden;
    }}

    .import-progress-bar {{
      height: 100%;
      width: 0%;
      background: var(--pco-appearance-button-bg, #ff7a00);
      box-shadow: 0 0 16px rgba(255,122,0,0.85);
      transition: width 0.25s ease;
    }}

    .import-progress-note {{
      margin-top: 8px;
      font-size: 13px;
      color: #ddd;
    }}

    .import-spinner {{
      display: inline-block;
      width: 14px;
      height: 14px;
      border: 2px solid rgba(255,255,255,0.25);
      border-top-color: #ff7a00;
      border-radius: 50%;
      animation: pincabSpin 0.9s linear infinite;
      vertical-align: middle;
      margin-right: 6px;
    }}

    @keyframes pincabSpin {{
      to {{ transform: rotate(360deg); }}
    }}


.np-grid-safe{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
.np-panel-safe{{border:1px solid rgba(255,176,0,.25);border-radius:16px;padding:16px;background:rgba(0,0,0,.18)}}
.np-panel-safe h3{{margin-top:0;color:#ffb000}}
.nudge-scope-safe{{position:relative;width:240px;height:240px;margin:10px auto;border-radius:50%;border:2px solid rgba(255,176,0,.6);background:radial-gradient(circle,rgba(255,176,0,.12),rgba(0,0,0,.25))}}
.nudge-scope-safe:before,.nudge-scope-safe:after{{content:"";position:absolute;background:rgba(255,176,0,.35)}}
.nudge-scope-safe:before{{left:50%;top:0;width:1px;height:100%}}
.nudge-scope-safe:after{{top:50%;left:0;height:1px;width:100%}}
.nudge-dot-safe{{position:absolute;left:50%;top:50%;width:16px;height:16px;transform:translate(-50%,-50%);border-radius:50%;background:#ff2b2b;box-shadow:0 0 12px rgba(255,43,43,.9)}}
.plunger-track-safe{{position:relative;height:28px;margin:36px 8px;border-radius:999px;border:1px solid rgba(255,176,0,.45);background:rgba(0,0,0,.35)}}
.plunger-pointer-safe{{position:absolute;left:50%;top:-9px;width:10px;height:46px;transform:translateX(-50%);border-radius:8px;background:#ff2b2b;box-shadow:0 0 12px rgba(255,43,43,.9)}}
.np-fields-safe{{display:grid;grid-template-columns:repeat(2,minmax(160px,1fr));gap:10px}}
.np-fields-safe label{{display:flex;flex-direction:column;gap:5px;font-weight:700}}
.np-fields-safe .checkline{{flex-direction:row;align-items:center}}
.np-fields-safe input,.np-fields-safe select{{max-width:100%}}
@media(max-width:950px){{.np-grid-safe{{grid-template-columns:1fr}}}}


.np-grid-safe{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
.np-panel-safe{{border:1px solid rgba(255,176,0,.25);border-radius:16px;padding:16px;background:rgba(0,0,0,.18)}}
.np-panel-safe h3{{margin-top:0;color:#ffb000}}
.nudge-scope-safe{{position:relative;width:240px;height:240px;margin:10px auto;border-radius:50%;border:2px solid rgba(255,176,0,.6);background:radial-gradient(circle,rgba(255,176,0,.12),rgba(0,0,0,.25))}}
.nudge-scope-safe:before,.nudge-scope-safe:after{{content:"";position:absolute;background:rgba(255,176,0,.35)}}
.nudge-scope-safe:before{{left:50%;top:0;width:1px;height:100%}}
.nudge-scope-safe:after{{top:50%;left:0;height:1px;width:100%}}
.nudge-dot-safe{{position:absolute;left:50%;top:50%;width:16px;height:16px;transform:translate(-50%,-50%);border-radius:50%;background:#ff2b2b;box-shadow:0 0 12px rgba(255,43,43,.9)}}
.plunger-track-safe{{position:relative;height:28px;margin:36px 8px;border-radius:999px;border:1px solid rgba(255,176,0,.45);background:rgba(0,0,0,.35)}}
.plunger-pointer-safe{{position:absolute;left:50%;top:-9px;width:10px;height:46px;transform:translateX(-50%);border-radius:8px;background:#ff2b2b;box-shadow:0 0 12px rgba(255,43,43,.9)}}
.np-fields-safe{{display:grid;grid-template-columns:repeat(2,minmax(160px,1fr));gap:10px}}
.np-fields-safe label{{display:flex;flex-direction:column;gap:5px;font-weight:700}}
.np-fields-safe .checkline{{flex-direction:row;align-items:center}}
.np-fields-safe input,.np-fields-safe select{{max-width:100%}}
@media(max-width:950px){{.np-grid-safe{{grid-template-columns:1fr}}}}


/* PINCABOS-LOG-NEWLINES-START */
pre,
#job-log,
.firstrun-log {{
  white-space: pre-wrap !important;
  overflow-wrap: anywhere !important;
  word-break: break-word !important;
}}
/* PINCABOS-LOG-NEWLINES-END */

</style>
<script 
  src="https://www.paypal.com/sdk/js?client-id=BAA5atlZ6zhL2iAHU4cMNpDOLyPpnZ4tBNxVfg_ZowsRSbQM5voDWVamM3F_Rw_vmwtMFrLxcT2kbgohM0&components=hosted-buttons&disable-funding=venmo&currency=CAD">
</script>

<script src="/static/pincabos-i18n.js?v=20260705-single-loader-v3"></script>
<script src="/static/pincabos-quick-access-i18n-v1.js?v=20260705-v1" defer></script>
<link rel="stylesheet" href="/static/pincabos-dashboard-compact.css">
<link rel="stylesheet" href="/static/pincabos-branding.css?v=branding">
<link rel="stylesheet" href="/static/pincabos-header-fix.css?v=20260515232444">
<link rel="stylesheet" href="/static/pincabos-menu-pro-v1.css?v=menu-logo-direct-v7">
<link rel="stylesheet" href="/static/pincabos-global-compact.css">
<link rel="stylesheet" href="/static/pincabos-footer.css">
<link rel="stylesheet" href="/static/pincabos-support-footer.css">
<link rel="stylesheet" href="/static/pincabos-footer-layout-v14.css?v=footer-layout-repair-v4">
<link rel="stylesheet" href="/static/pincabos-services-taskmanager.css">
<link rel="stylesheet" href="/static/pincabos-menu-icons.css">
<link rel="stylesheet" href="/static/pincabos-fulldmd-compact.css?v=20260515164207">
  <link rel="stylesheet" href="/static/pincabos-webapp-screen-toggle.css?v=20260705-glow-v3">
<link rel="stylesheet" href="/static/pincabos-appearance-vars.css?v=appearance">
<!-- PINCABOS_THEME_GLOBAL_LINK_V2 -->
<link rel="stylesheet" href="/static/pincabos-theme-global.css?v=20260701-theme-v2">

<link rel="icon" type="image/png" href="/static/branding/favicon.png?v=branding">
  <link rel="stylesheet" href="/static/pincabos-commander-purple-buttons-v1.css?v=1">
  <link rel="stylesheet" href="/static/pincabos-system-message-tray-v1.css?v=tray-tiny-text-x-v2-20260713-184235">
  <link rel="stylesheet" href="/static/pincabos-single-batch-status-v1.css?v=single-status-v1-20260715-170001"><!-- PINCABOS_SINGLE_BATCH_STATUS_OWNER_V1 -->
  <link rel="stylesheet" href="/static/pincabos-audio-widget-final-v1.css?v=1">
</head>
<body>

<div class="top-language-widget">
  <div id="google_translate_element"></div>
  <span>Langue :</span>
  <select id="pincabos_language_select" onchange="setPinCabOSLanguage(this.value)">
              <option value="fr">Français</option>
              <option value="en">English</option>
              <option value="es">Español</option>
              <option value="it">Italiano</option>
              <option value="de">Deutsch</option>
              <option value="nl">Nederlands</option>
            </select>
</div>

  <div class="top">
    <div class="brand-left">
      {logo_html}
      <div class="brand-title">
<div class="brand-subtitle"></div>
      </div>
    </div>

    <div class="nav">
    

<nav class="pincabos-nav">
  <!-- PINCABOS_MENU_LOGO_RAIL_V1 -->
  <div class="pco-menu-logo-rail" role="img" aria-label="PinCabOS">
    <img src="/static/pincabos-assets/PCOSMenuLogo.png?v=menu-logo-rail-v1"
         alt="PinCabOS">
  </div>
  <div class="nav-row nav-pages">
<a href="/" class="{ 'active' if title == 'Tableau de bord' else 'secondary' }"><span class="menu-ico">📊</span> Tableau de bord</a> 


    <a href="/inputs" class="{ 'active' if title == 'Inputs' else 'secondary' }"><span class="menu-ico">🎛️</span> Inputs</a>

<a href="/tools" class="{ 'active' if title == 'Outils' else 'secondary' }"><span class="menu-ico">🧰</span> Outils PinCabOS</a>


    <a href="/pincabos-link" class="{ 'active' if title == 'PinCabOS Link' else 'secondary' }"><span class="menu-ico">&#128279;</span> PinCabOS Link</a>
    <a href="/about" class="{ 'active' if title == 'À propos' else 'secondary' }"><span class="menu-ico">ℹ️</span> À propos</a>
    <span class="pco-menu-tools">
      <button type="button" id="pco-menu-pin-btn" class="pco-menu-tool-btn pco-menu-pin-btn" title="Épingler le menu" aria-label="Épingler le menu" onclick="return window.pcoMenuTogglePin(event);">📌</button>
      <button type="button" id="pco-menu-close-btn" class="pco-menu-tool-btn pco-menu-close-btn" title="Fermer la page" aria-label="Fermer la page" onclick="return window.pcoMenuClosePage(event);">X</button>
    </span>
    <link rel="stylesheet" href="/static/pincabos-menu-tools.css?v=20260615131347">
    <script src="/static/pincabos-menu-tools.js?v=20260615131347"></script>
 </div>

  <div class="nav-row nav-tools-clean">
    <span class="nav-vpinfe-vps-group" style="display:inline-flex;align-items:center;gap:8px;flex:0 0 auto;">
      <!-- PINCABOS_QUICK_ACCESS_I18N_V1 -->
      <span class="pco-quick-access-label" data-i18n="nav.quick_access" data-pco-i18n-quick-access="1">Accès rapides</span>
      <a href="http://{ip}:8001" target="_blank" class="secondary nav-action">Ouvrir VPinFE</a>
      <a href="https://virtualpinballspreadsheet.github.io/" target="_blank" rel="noopener noreferrer" class="secondary nav-action">Ouvrir VPS</a>
      <!-- PinCabOS topbar tools copy buttons -->
      <a class="button pco-topbar-tool-copy" href="/tools/commander">PinCab Explorer</a>
      <a class="button pco-topbar-tool-copy" href="/console">PinCab Console</a>
      <!-- /PinCabOS topbar tools copy buttons -->
    </span>

    <span class="nav-label" style="margin-left:auto;">Afficher PinCabOS WebApp sur :</span>

    {webapp_screen_toggle_html()}
  </div>

  <div class="nav-row pco-impexp-live-menu-row" aria-live="polite">
    <div id="pco-impexp-live-menu-slot"></div>
  </div>
</nav>
  </div>

  </div>
  </div>

  {body}

  
{pincabos_support_footer_html()}

<script src="/static/pincabos-progress-reset.js"></script>
<script src="/static/pincabos-dashboard-compact.js"></script>
<script src="/static/pincabos-explorer-same-tab-v2.js?v=20260716-vps-new-tab-v2"></script>
<script src="/static/pincabos-header-final.js?v=20260515232444"></script>
<!-- footer now rendered server-side; JS injection disabled -->
<script src="/static/pincabos-fulldmd-compact.js"></script>
<script src="/static/pincabos-fulldmd-layout-no-global-dmd-v1.js?v=20260802-101209"></script>

  <div id="firstrun-popup" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.72);z-index:999999;align-items:center;justify-content:center;">
    <div style="max-width:620px;width:92%;border:1px solid rgba(255,176,0,.55);border-radius:20px;padding:22px;background:rgba(18,0,30,.96);box-shadow:0 0 35px rgba(255,122,0,.35);">
      <div style="text-align:center;margin-bottom:14px;">
        <img src="/static/branding/firstrun-welcome.png?v=welcome"
             alt="Bienvenue PinCabOS"
             style="max-width:260px;width:70%;height:auto;border-radius:14px;box-shadow:0 0 22px rgba(255,122,0,.28);">
      </div>
      <h2>🚀 Bienvenue dans PinCabOS</h2>
      <p>Avant d’utiliser PinCabOS, Jarvis recommande de compléter l’assistant Premier Démarrage.</p>
      <p>Checklist : accès WebApp réseau, GPU/pilotes, puis détection et assignation des écrans.</p>
      <p>
        <a class="button" href="/first-run">🚀 Démarrer l’assistant</a>
        <button class="button secondary" onclick="closeFirstRunPopup()">Plus tard</button>
      </p>
      <label>
        <input type="checkbox" id="firstrun-disable">
        Ne plus afficher automatiquement
      </label>
    </div>
  </div>

  <script>
  async function closeFirstRunPopup(){{
    var chk = document.getElementById("firstrun-disable");
    var disable = chk ? chk.checked : false;
    if(disable){{
      await fetch("/first-run/popup-disable", {{method:"POST"}});
    }}
    var p = document.getElementById("firstrun-popup");
    if(p) p.style.display = "none";
  }}

  window.addEventListener("load", function(){{
    // PINCABOS_FIRSTRUN_3STEP_COMPLETE_V3
    var shouldShow = "{'1' if (title in ['Dashboard', 'Tableau de bord'] and firstrun_load_cfg().get('show_popup', True) and not pincabos_firstrun_is_complete()) else '0'}";
    if(shouldShow === "1"){{
      setTimeout(function(){{
        var p = document.getElementById("firstrun-popup");
        if(p) p.style.display = "flex";
      }}, 650);
    }}
  }});
  </script>

  <script defer src="/static/pincabos-system-message-tray-v1.js?v=menu-free-space-v4"></script>
  <script defer src="/static/pincabos-single-batch-status-v1.js?v=single-status-v1-20260715-170001"></script>
  <script defer src="/static/pincabos-audio-mute-icons-v1.js?v=2"></script>
</body>
</html>"""


def pincabos_firstrun_is_complete():
    # PINCABOS_FIRSTRUN_3STEP_COMPLETE_V3
    # Une fois les trois etapes sauvegardees, First Run est termine.
    # Un etat temporaire GPU ne doit jamais reactiver l'assistant.
    try:
        cfg = firstrun_load_cfg()
        keys = firstrun_required_keys()
        return bool(keys) and all(bool(cfg.get(key)) for key in keys)
    except Exception:
        return False
