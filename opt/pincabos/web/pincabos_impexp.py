# PINCABOS_IMPEXP_NATIVE_V1
# PINCABOS_IMPEXP_MODAL_FIX_V1
# PINCABOS_IMPEXP_LAYOUT_V2_NO_HERO_WORKFLOW_IN_PRIMARY
# PINCABOS_IMPEXP_LIVE_CARDS_REMOVED_V1
"""Native two-column Import Center and Export Center for PinCabOS.

Presentation only. Existing Smart and Batch engines remain the source of truth.
"""
from __future__ import annotations

import html
import os
import subprocess
from pathlib import Path

from flask import request


MARKER = "PINCABOS_IMPEXP_NATIVE_V1"


def register_pincabos_impexp_routes(app, app_globals):
    if app.config.get("PINCABOS_IMPEXP_NATIVE_V1_REGISTERED"):
        return
    app.config["PINCABOS_IMPEXP_NATIVE_V1_REGISTERED"] = True

    page = app_globals["page"]
    tables_dir_fn = app_globals["pincabos_vpx_tables_dir"]

    def esc(value):
        return html.escape("" if value is None else str(value), quote=True)

    def tables():
        root = Path(tables_dir_fn()).resolve()
        if not root.is_dir():
            return []
        return [
            child for child in sorted(root.iterdir(), key=lambda item: item.name.lower())
            if child.is_dir() and not child.name.startswith(".")
        ]

    def mounts():
        network_types = {"cifs", "smb3", "smbfs", "nfs", "nfs4", "fuse.sshfs", "sshfs", "davfs", "fuse.davfs"}
        allowed_prefixes = ("/media/", "/run/media/", "/mnt/")
        result = []
        try:
            proc = subprocess.run(
                ["/usr/bin/findmnt", "-rn", "-o", "TARGET,SOURCE,FSTYPE"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                timeout=8, check=False,
            )
        except Exception:
            return result
        seen = set()
        for raw in (proc.stdout or "").splitlines():
            fields = raw.split()
            if len(fields) < 3:
                continue
            target, source, fstype = fields[0], fields[1], fields[2].lower()
            if target in seen:
                continue
            is_network = fstype in network_types
            is_storage = target == "/mnt" or target.startswith(allowed_prefixes)
            if not is_network and not is_storage:
                continue
            if not Path(target).is_dir() or not os.path.ismount(target):
                continue
            kind = "SMB / réseau" if is_network else "USB / disque monté"
            result.append({"target": target, "label": f"{kind} — {target} ({source}, {fstype})"})
            seen.add(target)
        return sorted(result, key=lambda item: item["target"].lower())

    def shell_css():
        return r"""
<style id="pincabos-impexp-native-style">
.pco-ie{max-width:1880px;margin:0 auto;color:#f8f3ff}
.pco-ie *{box-sizing:border-box}
.pco-ie a{text-decoration:none}
.pco-ie-logo{position:relative;z-index:1;display:flex;align-items:center;justify-content:center;width:210px;height:118px;flex:0 0 210px;padding:8px;border:1px solid rgba(255,255,255,.17);border-radius:17px;background:rgba(0,0,0,.27);box-shadow:inset 0 0 22px rgba(255,255,255,.035)}
.pco-ie-logo img{display:block;max-width:100%;max-height:100%;object-fit:contain}
.pco-ie-column-head{min-height:164px}
.pco-ie-column-title{align-items:center}
.pco-ie-workflow{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:14px;padding:10px;border:1px solid rgba(255,255,255,.11);border-radius:12px;background:rgba(0,0,0,.20)}
.pco-ie-workflow-step{min-width:0;padding:8px 9px;border:1px solid rgba(255,255,255,.08);border-radius:9px;background:rgba(255,255,255,.025)}
.pco-ie-workflow-step b{display:block;color:#eee7f5;font-size:12px}
.pco-ie-workflow-step span{display:block;margin-top:3px;color:#ada1bb;font-size:11px;line-height:1.3}
.pco-ie-workflow-step.is-ready{border-color:rgba(191,130,255,.55);background:rgba(130,59,211,.17)}
.pco-ie-column.export .pco-ie-workflow-step.is-ready{border-color:rgba(255,166,66,.65);background:rgba(235,101,9,.14)}
.pco-ie-workflow-step i{display:inline-grid;place-items:center;width:18px;height:18px;margin-right:6px;border-radius:50%;background:rgba(255,255,255,.11);color:#fff;font-size:10px;font-style:normal;font-weight:900}

.pco-ie-hero{position:relative;overflow:hidden;padding:28px 30px;margin:0 0 22px;border:1px solid rgba(255,150,31,.38);border-radius:24px;background:radial-gradient(circle at 12% 105%,rgba(134,51,229,.28),transparent 34%),radial-gradient(circle at 91% 4%,rgba(255,119,18,.24),transparent 31%),linear-gradient(135deg,rgba(19,9,34,.97),rgba(7,4,15,.98));box-shadow:0 20px 52px rgba(0,0,0,.36)}
.pco-ie-hero:after{content:"";position:absolute;left:8%;right:8%;bottom:0;height:2px;background:linear-gradient(90deg,transparent,#8746e1,#ff831a,transparent)}
.pco-ie-hero-grid{position:relative;z-index:1;display:grid;grid-template-columns:minmax(0,1.4fr) minmax(530px,.9fr);gap:26px;align-items:center}
.pco-ie-brand{display:flex;align-items:center;gap:20px}
.pco-ie-mark{width:88px;height:88px;display:grid;place-items:center;flex:0 0 88px;border:1px solid rgba(255,178,84,.55);border-radius:24px;background:linear-gradient(145deg,rgba(133,58,229,.42),rgba(255,120,22,.28));box-shadow:inset 0 0 35px rgba(255,255,255,.07),0 0 34px rgba(140,59,226,.20);font-size:43px}
.pco-ie-kicker{margin:0 0 5px;color:#ffc05e;font-size:11px;font-weight:900;letter-spacing:.17em;text-transform:uppercase}
.pco-ie h1{margin:0;color:#fff;font-size:clamp(30px,3vw,49px);letter-spacing:-.045em}.pco-ie h1 em{font-style:normal;color:#ff9b2e}.pco-ie-lead{max-width:890px;margin:9px 0 0;color:#d9cce7;font-size:15px;line-height:1.55}
.pco-ie-features{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.pco-ie-feature{min-height:93px;padding:12px;border:1px solid rgba(255,255,255,.14);border-radius:14px;background:rgba(255,255,255,.045)}.pco-ie-feature b{display:block;color:#ffc366;font-size:13px}.pco-ie-feature span{display:block;margin-top:6px;color:#cfc4d8;font-size:12px;line-height:1.38}
.pco-ie-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:22px;align-items:start}.pco-ie-column{min-width:0;padding:16px;border:1px solid rgba(255,255,255,.13);border-radius:23px;background:linear-gradient(180deg,rgba(20,10,36,.93),rgba(7,5,14,.95));box-shadow:0 18px 45px rgba(0,0,0,.25)}.pco-ie-column.export{border-color:rgba(255,143,28,.36)}
.pco-ie-column-head{position:relative;min-height:170px;overflow:hidden;padding:23px;border:1px solid rgba(168,99,255,.50);border-radius:18px;background:radial-gradient(circle at 6% 110%,rgba(137,58,235,.40),transparent 45%),linear-gradient(135deg,rgba(47,21,83,.95),rgba(10,5,21,.94));}.pco-ie-column.export .pco-ie-column-head{border-color:rgba(255,137,28,.55);background:radial-gradient(circle at 6% 110%,rgba(255,105,20,.34),transparent 46%),linear-gradient(135deg,rgba(69,27,19,.96),rgba(13,6,12,.96))}
.pco-ie-column-head:after{content:"";position:absolute;right:-35px;bottom:-65px;width:210px;height:210px;border:2px solid rgba(255,255,255,.09);border-radius:50%;box-shadow:0 0 0 26px rgba(255,255,255,.025),0 0 0 56px rgba(255,255,255,.02)}.pco-ie-column-title{position:relative;z-index:1;display:flex;align-items:center;gap:14px}.pco-ie-icon{display:grid;place-items:center;width:58px;height:58px;border:1px solid rgba(255,255,255,.25);border-radius:18px;background:rgba(255,255,255,.08);font-size:28px}.pco-ie-column h2{margin:0;color:#fff;font-size:28px;letter-spacing:-.035em}.pco-ie-column h2 strong{color:#cfa1ff}.pco-ie-column.export h2 strong{color:#ffad4d}.pco-ie-column-head p{position:relative;z-index:1;max-width:560px;margin:13px 0 0;color:#ded3e7;line-height:1.5}
.pco-ie-card{margin-top:15px;padding:18px;border:1px solid rgba(255,255,255,.14);border-radius:16px;background:rgba(255,255,255,.035)}.pco-ie-card h3{margin:0;color:#fff;font-size:17px}.pco-ie-card h3 span{color:#c89dff}.pco-ie-column.export .pco-ie-card h3 span{color:#ffad4d}.pco-ie-card p{margin:7px 0 0;color:#cbbfd6;font-size:13px;line-height:1.48}
.pco-ie-field{display:block;margin-top:14px;color:#efe7f7;font-size:13px;font-weight:800}.pco-ie-field small{display:block;margin:5px 0 7px;color:#afa1bb;font-weight:500}.pco-ie input[type=file],.pco-ie select,.pco-ie input[type=text]{width:100%;padding:11px 12px;border:1px solid rgba(255,255,255,.19);border-radius:10px;background:#0b0812;color:#fff;font:inherit}.pco-ie input[type=file]{padding:9px}
.pco-ie-actions{display:flex;gap:9px;flex-wrap:wrap;margin-top:14px}.pco-ie .button,.pco-ie button{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:39px;padding:9px 13px;border:1px solid rgba(255,255,255,.18);border-radius:10px;background:rgba(255,255,255,.08);color:#fff;font:700 13px inherit;cursor:pointer}.pco-ie .button:hover,.pco-ie button:hover{filter:brightness(1.12)}.pco-ie .pco-ie-primary{border-color:rgba(188,121,255,.85);background:linear-gradient(135deg,#7835cb,#a55bed);box-shadow:0 8px 22px rgba(130,50,215,.23)}.pco-ie-column.export .pco-ie-primary{border-color:rgba(255,165,65,.90);background:linear-gradient(135deg,#d95a08,#ff982d);box-shadow:0 8px 22px rgba(255,109,13,.20)}.pco-ie .pco-ie-muted{background:rgba(255,255,255,.045)}
.pco-ie-note{display:flex;gap:9px;align-items:flex-start;margin-top:13px;padding:10px 11px;border:1px solid rgba(154,104,255,.34);border-radius:10px;background:rgba(117,55,193,.12);color:#ddd2e8;font-size:12px;line-height:1.4}.pco-ie-error-note{border-color:rgba(255,92,92,.75)!important;background:rgba(145,25,25,.18)!important;color:#ffd9d9!important}.pco-ie-column.export .pco-ie-note{border-color:rgba(255,145,40,.35);background:rgba(255,106,16,.10)}
.pco-ie-split{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.pco-ie-steps{display:grid;gap:12px;margin-top:13px}.pco-ie-step{display:grid;grid-template-columns:29px minmax(0,1fr);gap:9px}.pco-ie-num{display:grid;place-items:center;width:27px;height:27px;border-radius:50%;background:rgba(153,81,234,.25);border:1px solid rgba(194,143,255,.62);color:#f4eaff;font-size:12px;font-weight:900}.pco-ie-column.export .pco-ie-num{background:rgba(255,113,15,.18);border-color:rgba(255,177,80,.62)}.pco-ie-step b{display:block;color:#f3edf8;font-size:13px}.pco-ie-step span{display:block;margin-top:3px;color:#bcaec8;font-size:12px;line-height:1.35}
.pco-ie-kv{display:grid;grid-template-columns:100px minmax(0,1fr);gap:7px 10px;margin-top:13px;font-size:12px}.pco-ie-kv dt{color:#a99bb5}.pco-ie-kv dd{margin:0;color:#fff;overflow-wrap:anywhere}.pco-ie-kv code,.pco-ie-summary code{color:#ffbf69;word-break:break-word}
.pco-ie-radio{display:block;margin-top:11px;padding:10px;border:1px solid rgba(255,255,255,.12);border-radius:10px;background:rgba(0,0,0,.18);cursor:pointer}.pco-ie-radio input{margin-right:8px;accent-color:#ff8620}.pco-ie-radio span{color:#d9cfdf;font-size:13px}.pco-ie-summary{margin-top:12px;padding:11px;border:1px solid rgba(255,177,81,.30);border-radius:10px;background:rgba(255,123,14,.09);color:#eee;font-size:12px;line-height:1.45}
.pco-ie-console{margin-top:15px;padding:14px;border:1px solid rgba(255,156,48,.35);border-radius:14px;background:rgba(0,0,0,.30)}.pco-ie-console-head{display:flex;justify-content:space-between;gap:10px;align-items:center}.pco-ie-console strong{color:#fff}.pco-ie-state{padding:4px 8px;border:1px solid rgba(255,184,82,.44);border-radius:999px;color:#ffd18b;font-size:11px;font-weight:900}.pco-ie-progress{height:9px;overflow:hidden;margin-top:10px;border-radius:999px;background:rgba(255,255,255,.12)}.pco-ie-progress i{display:block;width:0;height:100%;border-radius:inherit;background:linear-gradient(90deg,#9145e8,#ff8d25);transition:width .35s}.pco-ie-log{max-height:150px;overflow:auto;margin:10px 0 0;padding:9px;border:1px solid rgba(255,255,255,.10);border-radius:8px;background:#050507;color:#ddd;white-space:pre-wrap;font:11px/1.42 ui-monospace,SFMono-Regular,Menlo,monospace}
.pco-ie-footer{display:grid;grid-template-columns:1.3fr 1fr 1fr;gap:12px;margin-top:22px;padding:15px 17px;border:1px solid rgba(255,255,255,.13);border-radius:16px;background:rgba(8,5,14,.86);color:#cfc3da;font-size:12px;line-height:1.45}.pco-ie-footer b{display:block;color:#fff}
.pco-ie-modal[hidden]{display:none!important}.pco-ie-modal{position:fixed!important;z-index:2147483647!important;inset:0!important;display:grid!important;place-items:center!important;padding:18px!important;isolation:isolate!important;pointer-events:auto!important;background:#07040b!important;backdrop-filter:none!important}.pco-ie-modal-panel{position:relative!important;z-index:1!important;width:min(960px,100%)!important;max-height:min(780px,92vh)!important;display:flex!important;flex-direction:column!important;overflow:hidden!important;border:1px solid rgba(255,151,38,.78)!important;border-radius:18px!important;background:#100a18!important;box-shadow:0 30px 100px rgba(0,0,0,.92)!important}body.pco-ie-modal-open{overflow:hidden!important}.pco-ie-modal-head,.pco-ie-modal-foot{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:15px 17px;border-bottom:1px solid rgba(255,255,255,.12)}.pco-ie-modal-foot{border-top:1px solid rgba(255,255,255,.12);border-bottom:0}.pco-ie-modal-head h3{margin:0;color:#fff}.pco-ie-modal-body{overflow:auto;padding:16px}.pco-ie-tablelist{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:12px}.pco-ie-tablechoice{display:flex;gap:9px;align-items:center;padding:9px;border:1px solid rgba(255,255,255,.11);border-radius:9px;background:rgba(255,255,255,.035);color:#e8e1ef;font-size:13px;overflow-wrap:anywhere}.pco-ie-tablechoice input{accent-color:#ff8620}
.pco-ie-dest-grid{display:grid;grid-template-columns:1fr auto;gap:9px;margin-top:12px}.pco-ie-dest-browser{display:none;margin-top:12px;padding:12px;border:1px solid rgba(255,169,69,.34);border-radius:11px;background:rgba(0,0,0,.20)}.pco-ie-dest-browser.show{display:block}.pco-ie-folder-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;max-height:190px;overflow:auto;margin-top:10px}.pco-ie-folder{justify-content:flex-start!important;text-align:left}.pco-ie-hidden{display:none!important}
@media(max-width:1180px){.pco-ie-hero-grid,.pco-ie-grid{grid-template-columns:1fr}.pco-ie-features{grid-template-columns:repeat(4,minmax(0,1fr))}}@media(max-width:760px){.pco-ie{padding:0}.pco-ie-column-title{align-items:flex-start}.pco-ie-logo{width:104px;height:82px;flex-basis:104px;padding:5px}.pco-ie-workflow{grid-template-columns:1fr}.pco-ie-hero{padding:20px}.pco-ie-brand{align-items:flex-start}.pco-ie-mark{width:64px;height:64px;flex-basis:64px;font-size:31px}.pco-ie-features,.pco-ie-split,.pco-ie-tablelist,.pco-ie-footer{grid-template-columns:1fr}.pco-ie-grid{gap:14px}.pco-ie-column{padding:11px}.pco-ie-dest-grid{grid-template-columns:1fr}.pco-ie-kv{grid-template-columns:85px minmax(0,1fr)}}
</style>
"""

    def import_page():
        return shell_css() + r"""
<div class="pco-ie">
  <div class="pco-ie-grid">
    <section class="pco-ie-column">
      <header class="pco-ie-column-head"><div class="pco-ie-column-title"><div class="pco-ie-logo"><img src="/static/pincabos-assets/PCOSImport.png?v=impexp-layout-v2" alt="PinCabOS Smart Import"></div><div><h2><strong>Smart</strong> Import</h2><p>Analysez une archive ou ses fichiers associés, puis confirmez son installation guidée.</p></div></div></header>
      <section class="pco-ie-card"><h3><span>1.</span> Analyser une archive</h3><p>La première étape prépare le lot sans publier de table dans votre collection.</p>
        <form method="post" action="/tools/import-table/analyze" enctype="multipart/form-data">
          <!-- PINCABOS_SMART_IMPORT_REAL_QUEUE_V1 -->
          <link rel="stylesheet" href="/static/pincabos-smart-import-queue-real-v1.css?v=1">

          <div class="pco-ie-field">
            Archives ou fichiers associés
            <small>
              Ajoutez la table VPX, le B2S, la ROM et les autres
              fichiers depuis plusieurs emplacements.
            </small>

            <input
              id="pcoSmartImportPackages"
              name="packages"
              type="file"
              multiple
              hidden
              tabindex="-1"
              aria-hidden="true"
            >

            <input
              id="pcoSmartImportExpectedCount"
              name="expected_count"
              type="hidden"
              value="0"
            >

            <div class="pco-smart-import-queue">
              <div class="pco-smart-import-queue-toolbar">
                <button
                  id="pcoSmartImportAddFiles"
                  class="button pco-ie-muted"
                  type="button"
                >
                  📂 Parcourir / Ajouter des fichiers
                </button>

                <button
                  id="pcoSmartImportClearFiles"
                  class="button pco-ie-muted"
                  type="button"
                  disabled
                >
                  Vider la liste
                </button>

                <span
                  id="pcoSmartImportFileCount"
                  class="pco-smart-import-queue-count"
                >
                  0 fichier
                </span>
              </div>

              <div
                id="pcoSmartImportFileList"
                class="pco-smart-import-file-list"
              >
                <div class="pco-smart-import-queue-empty">
                  Aucun fichier sélectionné.
                </div>
              </div>

              <div
                id="pcoSmartImportQueueMessage"
                class="pco-ie-note"
                hidden
                aria-live="polite"
              ></div>
            </div>
          </div>

          <script src="/static/pincabos-smart-import-queue-real-v1.js?v=1"></script>
          <div class="pco-ie-actions"><button class="pco-ie-primary" type="submit">🔍 Analyser l’import</button><a class="button pco-ie-muted" href="/tools/commander">🗂️ PinCab Explorer</a><a class="button pco-ie-muted" href="/tools">← Outils</a></div>
        </form><div class="pco-ie-note">ⓘ L’analyse ne modifie pas la collection de tables.</div>
        <div class="pco-ie-workflow" aria-label="État du cheminement Smart Import"><div class="pco-ie-workflow-step is-ready"><b><i>1</i>Prêt à analyser</b><span>Ajoute les fichiers puis lance l’analyse.</span></div><div class="pco-ie-workflow-step"><b><i>2</i>Association</b><span>Détection table, dépendances et VPSdb.</span></div><div class="pco-ie-workflow-step"><b><i>3</i>Installation</b><span>Confirmation avant toute publication.</span></div></div>
      </section>
    </section>
    <section class="pco-ie-column export">
      <header class="pco-ie-column-head"><div class="pco-ie-column-title"><div class="pco-ie-logo"><img src="/static/pincabos-assets/PCOSImport.png?v=impexp-layout-v2" alt="PinCabOS Smart Batch Import"></div><div><h2><strong>Smart Batch</strong> Import</h2><p>Importez plusieurs packages <code>.PinCabOS</code>, un à la fois, avec suivi live et protection des conflits.</p></div></div></header>
      <form id="pco-batch-import-native" action="/tools/batch-import/run" method="post" enctype="multipart/form-data">
        <section class="pco-ie-card"><h3><span>1.</span> Packages portables</h3><p>Utilisez le Batch Import pour les exports portables PinCabOS.</p><label class="pco-ie-field">Packages <code>.PinCabOS</code><input name="archives" type="file" accept=".pincabos,.PinCabOS" multiple required></label><div class="pco-ie-note">ⓘ Les archives sont validées avant extraction. Les packages corrompus ou sans manifest sont refusés.</div></section>
        <section class="pco-ie-card"><h3><span>2.</span> Table déjà installée</h3><label class="pco-ie-radio"><input name="conflict_mode" value="skip" type="radio" checked><span><b>Ignorer la table existante</b><br>Conserve l’installation actuelle.</span></label><label class="pco-ie-radio"><input name="conflict_mode" value="rename" type="radio"><span><b>Importer sous un nouveau nom</b><br>Crée une copie sans écraser la table actuelle.</span></label><label class="pco-ie-radio"><input name="conflict_mode" value="replace" type="radio"><span><b>Remplacer après backup automatique</b><br>La version actuelle est déplacée avant l’import.</span></label><div class="pco-ie-summary">📁 Backups de remplacement : <code>/home/pinball/Backups/PinCabOS-BatchImport/</code></div></section>
        <section class="pco-ie-card"><h3><span>3.</span> Exécution</h3><p>Le Batch refuse de démarrer lorsqu’une table VPX est active. Les imports ne sont jamais parallèles.</p><div class="pco-ie-actions"><button class="pco-ie-primary" type="submit">⚡ Lancer en arrière-plan</button><a class="button pco-ie-muted" href="/tools/import-table">↶ Smart Import</a></div><div id="pco-bi-message" class="pco-ie-note" hidden aria-live="polite"></div></section>
      </form>
    </section>
  </div>
  <footer class="pco-ie-footer"><div><b>ⓘ Imports validés et sécurisés</b>Votre collection PinCabOS reste protégée.</div><div><b>Destination</b><code>/home/pinball/Tables</code></div><div><b>Documentation</b>Consultez l’aide PinCabOS pour les packages portables.</div></footer>
</div>
<script id="pincabos-impexp-import-js">
(() => {
  const form = document.getElementById('pco-batch-import-native');
  if (!form) return;
  const message = document.getElementById('pco-bi-message');
  const button = form.querySelector('button[type="submit"]');
  const say = (text, error=false) => {
    if (!message) return;
    message.hidden = false;
    message.textContent = text;
    message.classList.toggle('pco-ie-error-note', Boolean(error));
  };
  const call = async (url, options) => {
    const response = await fetch(url, Object.assign({cache:'no-store'}, options || {}));
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) throw Error(payload.error || ('HTTP ' + response.status));
    return payload;
  };
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const input = form.querySelector('[name="archives"]');
    if (!input || !input.files.length) {
      say('Choisis au moins une archive .PinCabOS.', true);
      return;
    }
    // PINCABOS_BATCH_IMPORT_UPLOAD_EVENTS_V12
    button.disabled = true;
    const uploadTotal = input.files.length;
    say('Téléversement de ' + uploadTotal + ' archive(s) en cours…', false);
    window.dispatchEvent(new CustomEvent(
      'pcos-batch-import-uploading',
      {detail:{total:uploadTotal}}
    ));
    try {
      const payload = await call(
        '/api/batch-import/live/start',
        {method:'POST', body:new FormData(form)}
      );
      window.dispatchEvent(new CustomEvent(
        'pcos-batch-import-started',
        {detail:payload.job || {}}
      ));
      say('Import démarré. Progression affichée dans le menu.', false);
    } catch (error) {
      window.dispatchEvent(
        new CustomEvent('pcos-batch-import-upload-failed')
      );
      say('Lancement impossible : ' + error.message, true);
      button.disabled = false;
    }
  });

  const anForm = document.querySelector('form[action="/tools/import-table/analyze"]');
  if (anForm) {
    anForm.addEventListener('submit', (ev) => {
      const inp = anForm.querySelector('input[type="file"]');
      const files = Array.from((inp && inp.files) || []);
      if (!files.length) return;
      if (!window.XMLHttpRequest || !window.FormData) return;
      ev.preventDefault();
      let host = document.getElementById('pco-si-progress');
      let fill = document.getElementById('pco-si-fill');
      if (!host) {
        host = document.createElement('div');
        host.id = 'pco-si-progress';
        host.style.cssText = 'margin-top:10px;font-size:13px;color:#ffb347;';
        const track = document.createElement('div');
        track.style.cssText = 'margin-top:6px;height:14px;background:#2a2a2a;border-radius:7px;overflow:hidden;';
        fill = document.createElement('div');
        fill.id = 'pco-si-fill';
        fill.style.cssText = 'height:100%;width:0%;background:linear-gradient(90deg,#ff7a00,#ffb347);transition:width .2s;';
        track.appendChild(fill);
        anForm.appendChild(host);
        anForm.appendChild(track);
      }
      const btn = anForm.querySelector('button[type="submit"], input[type="submit"]');
      if (btn) btn.disabled = true;
      const totalMb = files.reduce((a, f) => a + f.size, 0) / (1024 * 1024);
      const names = files.map(f => f.name).join(', ');
      const started = Date.now();
      host.textContent = 'Envoi de ' + names + ' (' + totalMb.toFixed(1) + ' Mo)…';
      const xhr = new XMLHttpRequest();
      xhr.open('POST', anForm.action, true);
      xhr.responseType = 'json';
      xhr.setRequestHeader('X-PCOS-Async', '1');
      xhr.upload.onprogress = (e) => {
        if (!e.lengthComputable) return;
        const pct = Math.round(100 * e.loaded / e.total);
        const secs = Math.max((Date.now() - started) / 1000, 0.2);
        const mbps = (e.loaded / (1024 * 1024)) / secs;
        if (fill) fill.style.width = pct + '%';
        host.textContent = 'Envoi ' + pct + '% — ' + names + ' (' + totalMb.toFixed(1) + ' Mo, ' + mbps.toFixed(1) + ' Mo/s)';
      };
      xhr.onerror = () => {
        host.textContent = 'Erreur réseau pendant l’envoi.';
        if (btn) btn.disabled = false;
      };
      xhr.onload = () => {
        const data = xhr.response || {};
        if (xhr.status >= 200 && xhr.status < 300 && data && data.next) {
          if (fill) fill.style.width = '100%';
          host.textContent = 'Envoi terminé — analyse en cours…';
          window.location.href = data.next;
        } else {
          host.textContent = 'Analyse impossible : ' + ((data && data.error) || ('HTTP ' + xhr.status));
          if (btn) btn.disabled = false;
        }
      };
      xhr.send(new FormData(anForm));
    });
  }
})();
</script>
"""

    def export_page():
        rows = tables()
        options = "".join(f'<option value="{esc(item.name)}">{esc(item.name)}</option>' for item in rows)
        choices = "".join(f'<label class="pco-ie-tablechoice"><input type="checkbox" value="{esc(item.name)}"><span>{esc(item.name)}</span></label>' for item in rows)
        mount_options = "".join(f'<option value="{esc(item["target"])}">{esc(item["label"])}</option>' for item in mounts())
        single = (f'<option value="">Choisir une table…</option>{options}') if rows else '<option value="">Aucune table détectée</option>'
        return shell_css() + f"""
<div class="pco-ie">
  <div class="pco-ie-grid">
    <section class="pco-ie-column">
      <header class="pco-ie-column-head"><div class="pco-ie-column-title"><div class="pco-ie-logo"><img src="/static/pincabos-assets/PCOSExport.png?v=impexp-layout-v2" alt="PinCabOS Smart Export"></div><div><h2><strong>Smart</strong> Export</h2><p>Créez un package portable complet pour une table sélectionnée.</p></div></div></header>
      <section class="pco-ie-card"><h3><span>1.</span> Sélectionner une table</h3><p>L’export Smart prépare une archive <code>.PinCabOS</code> téléchargeable sans modifier la table locale.</p><form method="post" action="/tools/export-table"><label class="pco-ie-field">Table installée<select name="table_folder" required>{single}</select></label><div class="pco-ie-actions"><button class="pco-ie-primary" type="submit">📦 Préparer l’export</button><a class="button pco-ie-muted" href="/tools/commander">🗂️ PinCab Explorer</a><a class="button pco-ie-muted" href="/tools">← Outils</a></div></form><div class="pco-ie-note">ⓘ La création du package ne supprime aucun fichier local.</div><div class="pco-ie-workflow" aria-label="État du cheminement Smart Export"><div class="pco-ie-workflow-step is-ready"><b><i>1</i>Prêt à préparer</b><span>Choisis une table installée.</span></div><div class="pco-ie-workflow-step"><b><i>2</i>Validation</b><span>Manifest et contenu sont contrôlés.</span></div><div class="pco-ie-workflow-step"><b><i>3</i>Téléchargement</b><span>Le package portable est créé.</span></div></div></section>
    </section>
    <section class="pco-ie-column export">
      <header class="pco-ie-column-head"><div class="pco-ie-column-title"><div class="pco-ie-logo"><img src="/static/pincabos-assets/PCOSExport.png?v=impexp-layout-v2" alt="PinCabOS Smart Batch Export"></div><div><h2><strong>Smart Batch</strong> Export</h2><p>Exportez plusieurs tables, une à la fois, avec sélection native, destination guidée et progression live.</p></div></div></header>
      <form id="pco-batch-export-native" action="/tools/batch-export/run" method="post">
        <section class="pco-ie-card"><h3><span>1.</span> Tables à exporter</h3><p>Utilise le sélecteur pour cocher précisément les tables à inclure.</p><div class="pco-ie-actions"><button type="button" class="pco-ie-primary" id="pco-open-table-modal">☑ Choisir les tables</button><span class="button pco-ie-muted" id="pco-selected-count">0 table sélectionnée</span></div><div class="pco-ie-summary" id="pco-selected-summary">Aucune table sélectionnée.</div><div id="pco-table-hidden"></div></section>
        <section class="pco-ie-card"><h3><span>2.</span> Destination</h3><p>Les fichiers <code>.PinCabOS</code> sont déposés directement dans le dossier choisi.</p>
          <label class="pco-ie-radio"><input type="radio" name="destination_kind" value="local" checked><span><b>Dossier local</b><br><code>/home/pinball/Exports</code></span></label>
          <label class="pco-ie-radio"><input type="radio" name="destination_kind" value="mount"><span><b>USB ou SMB déjà monté</b><br>Choisis un montage puis parcours ses dossiers.</span></label>
          <div class="pco-ie-dest-grid"><select id="pco-mount-target" name="mount_target"><option value="">Sélectionner un montage détecté</option>{mount_options}</select><button type="button" id="pco-open-dest">📁 Parcourir</button></div>
          <input type="hidden" name="destination_subpath" id="pco-dest-subpath" value=""><div class="pco-ie-summary" id="pco-dest-summary">Destination : <code>/home/pinball/Exports</code></div>
          <div class="pco-ie-dest-browser" id="pco-dest-browser"><div class="pco-ie-actions"><button type="button" id="pco-dest-parent">← Parent</button><button type="button" id="pco-dest-refresh">Actualiser</button><button type="button" id="pco-dest-use" class="pco-ie-primary">Utiliser ce dossier</button></div><div class="pco-ie-summary" id="pco-dest-path">Chargement…</div><div class="pco-ie-folder-list" id="pco-dest-folders"></div></div>
          <div class="pco-ie-note">ⓘ Chaque package copié est contrôlé par SHA-256 après la copie.</div></section>
        <section class="pco-ie-card"><h3><span>3.</span> Exécution</h3><p>Le préflight vérifie l’espace libre et bloque le Batch lorsqu’une table VPX est active. Les exports sont toujours séquentiels.</p><div class="pco-ie-actions"><button class="pco-ie-primary" type="submit">⚡ Lancer en arrière-plan</button><a class="button pco-ie-muted" href="/tools/export-table">↶ Smart Export</a></div><div id="pco-be-message" class="pco-ie-note" hidden aria-live="polite"></div></section>
      </form>
    </section>
  </div>
  <footer class="pco-ie-footer"><div><b>ⓘ Exports validés et sécurisés</b>Votre collection reste portable et protégée.</div><div><b>Dossier local</b><code>/home/pinball/Exports</code></div><div><b>Documentation</b>USB et SMB doivent être montés avant l’export.</div></footer>
</div>
<div class="pco-ie-modal" id="pco-table-modal" hidden><section class="pco-ie-modal-panel" role="dialog" aria-modal="true" aria-labelledby="pco-table-modal-title"><header class="pco-ie-modal-head"><div><h3 id="pco-table-modal-title">Sélection des tables</h3><p id="pco-modal-count">0 table sélectionnée</p></div><button type="button" id="pco-modal-close">× Fermer</button></header><div class="pco-ie-modal-body"><input type="text" id="pco-table-filter" placeholder="Rechercher une table…"><div class="pco-ie-actions"><button type="button" id="pco-select-all">Sélectionner tout</button><button type="button" id="pco-clear-all">Désélectionner tout</button></div><div class="pco-ie-tablelist" id="pco-table-list">{choices or '<p>Aucune table détectée.</p>'}</div></div><footer class="pco-ie-modal-foot"><span id="pco-modal-foot-count">0 table</span><div class="pco-ie-actions"><button type="button" id="pco-modal-cancel">Annuler</button><button type="button" id="pco-modal-confirm" class="pco-ie-primary">Confirmer la sélection</button></div></footer></section></div>
<script id="pincabos-impexp-export-js">
(() => {{
  const q=id=>document.getElementById(id), form=q('pco-batch-export-native'), modal=q('pco-table-modal'), list=q('pco-table-list'); if(!form||!modal) return;
  let chosen=new Set(), draft=new Set(), rel='';
  const plural=n=>n===1?'table sélectionnée':'tables sélectionnées';
  const choices=()=>Array.from(list.querySelectorAll('input[type=checkbox]'));
  function renderCount(){{const n=chosen.size;q('pco-selected-count').textContent=n+' '+plural(n);q('pco-selected-summary').innerHTML=n?Array.from(chosen).map(x=>'<code>'+escapeHtml(x)+'</code>').join(' · '):'Aucune table sélectionnée.';q('pco-table-hidden').innerHTML=Array.from(chosen).map(x=>'<input type="hidden" name="table_folder" value="'+escapeAttr(x)+'">').join('');}}
  function escapeHtml(s){{const d=document.createElement('div');d.textContent=s;return d.innerHTML;}} function escapeAttr(s){{return escapeHtml(s).replace(/"/g,'&quot;');}}
  function modalCount(){{const n=draft.size;q('pco-modal-count').textContent=n+' '+plural(n);q('pco-modal-foot-count').textContent=n+' '+(n===1?'table':'tables');}}
  function showModal(){{
    // Move the dialog directly under <body>: it cannot be trapped in an
    // ancestor stacking context created by the page shell or global theme.
    if(modal.parentElement!==document.body) document.body.appendChild(modal);
    draft=new Set(chosen);
    choices().forEach(c=>c.checked=draft.has(c.value));
    modalCount();
    document.body.classList.add('pco-ie-modal-open');
    modal.hidden=false;
    modal.style.pointerEvents='auto';
    q('pco-table-filter').focus();
  }}
  function closeModal(){{
    modal.hidden=true;
    document.body.classList.remove('pco-ie-modal-open');
  }}
  q('pco-open-table-modal').addEventListener('click',showModal);q('pco-modal-close').addEventListener('click',closeModal);q('pco-modal-cancel').addEventListener('click',closeModal);
  q('pco-modal-confirm').addEventListener('click',()=>{{chosen=new Set(draft);renderCount();closeModal();}});
  q('pco-table-filter').addEventListener('input',e=>{{const term=e.target.value.toLowerCase();list.querySelectorAll('.pco-ie-tablechoice').forEach(x=>x.classList.toggle('pco-ie-hidden',!x.textContent.toLowerCase().includes(term)));}});
  q('pco-select-all').addEventListener('click',()=>{{choices().forEach(c=>{{if(!c.closest('.pco-ie-tablechoice').classList.contains('pco-ie-hidden')){{c.checked=true;draft.add(c.value);}}}});modalCount();}});
  q('pco-clear-all').addEventListener('click',()=>{{choices().forEach(c=>{{c.checked=false;draft.delete(c.value);}});modalCount();}});
  choices().forEach(c=>c.addEventListener('change',()=>{{c.checked?draft.add(c.value):draft.delete(c.value);modalCount();}}));
  modal.addEventListener('click',e=>{{if(e.target===modal) closeModal();}});
  const kind=()=>form.querySelector('input[name=destination_kind]:checked').value;
  const mount=()=>q('pco-mount-target').value;
  function destText(path){{q('pco-dest-summary').innerHTML='Destination : <code>'+escapeHtml(path)+'</code>';}}
  function local(){{return kind()==='local';}}
  async function browse(){{const useLocal=local();if(!useLocal&&!mount()){{q('pco-dest-path').textContent='Sélectionne un montage USB / SMB.';q('pco-dest-browser').classList.add('show');return;}}const params=new URLSearchParams({{kind:useLocal?'local':'mount',mount_target:useLocal?'':mount(),relative:rel}});try{{const r=await fetch('/api/batch-export/browse?'+params);const d=await r.json();if(!r.ok||!d.ok)throw Error(d.error||'Lecture impossible');q('pco-dest-browser').classList.add('show');q('pco-dest-path').textContent=d.display_path+(d.writable?'':' — non accessible en écriture');q('pco-dest-use').disabled=!d.writable;q('pco-dest-folders').innerHTML=(d.folders||[]).map(x=>'<button type="button" class="pco-ie-folder" data-name="'+escapeAttr(x.name)+'">📁 '+escapeHtml(x.name)+(x.writable?'':' · lecture seule')+'</button>').join('')||'<span>Aucun sous-dossier.</span>';q('pco-dest-folders').querySelectorAll('[data-name]').forEach(b=>b.addEventListener('click',()=>{{rel=rel?rel+'/'+b.dataset.name:b.dataset.name;browse();}}));}}catch(e){{q('pco-dest-browser').classList.add('show');q('pco-dest-path').textContent='Erreur : '+e.message;}}}}
  q('pco-open-dest').addEventListener('click',browse);q('pco-dest-refresh').addEventListener('click',browse);q('pco-dest-parent').addEventListener('click',()=>{{rel=rel.split('/').filter(Boolean).slice(0,-1).join('/');browse();}});q('pco-dest-use').addEventListener('click',()=>{{q('pco-dest-subpath').value=rel;const root=local()?'/home/pinball/Exports':mount();destText(rel?root+'/'+rel:root);q('pco-dest-browser').classList.remove('show');}});
  form.querySelectorAll('input[name=destination_kind]').forEach(r=>r.addEventListener('change',()=>{{rel='';q('pco-dest-subpath').value='';destText(local()?'/home/pinball/Exports':(mount()||'Sélectionne un montage'));}}));q('pco-mount-target').addEventListener('change',()=>{{if(!local()){{rel='';q('pco-dest-subpath').value='';destText(mount()||'Sélectionne un montage');}}}});
  const message=q('pco-be-message');
  const say=(text,error=false)=>{{if(!message)return;message.hidden=false;message.textContent=text;message.classList.toggle('pco-ie-error-note',Boolean(error));}};
  const call=async(url,opt)=>{{const r=await fetch(url,Object.assign({{cache:'no-store'}},opt||{{}}));const d=await r.json().catch(()=>({{}}));if(!r.ok||d.ok===false)throw Error(d.error||('HTTP '+r.status));return d;}};
  form.addEventListener('submit',async e=>{{e.preventDefault();if(!chosen.size){{say('Choisis au moins une table.',true);showModal();return;}}if(!local()&&!mount()){{say('Sélectionne un montage USB / SMB.',true);return;}}const btn=form.querySelector('button[type=submit]');btn.disabled=true;say('Export mis en file. Suis la progression dans le menu Langue.');try{{const fields=Array.from(new FormData(form).entries());await call('/api/batch-export/live/start',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{fields}})}});}}catch(err){{say('Lancement impossible : '+err.message,true);btn.disabled=false;}}}});
  renderCount();destText('/home/pinball/Exports');
}})();
</script>
"""

    @app.route("/tools/import-table", methods=["GET"])
    def pincabos_impexp_import_center():
        return page("Import Center", import_page())

    @app.route("/tools/export-table", methods=["GET"])
    def pincabos_impexp_export_center():
        return page("Export Center", export_page())
