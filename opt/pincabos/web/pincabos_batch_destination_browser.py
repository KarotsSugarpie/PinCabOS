# PINCABOS_BATCH_DESTINATION_BROWSER_V3
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

from flask import jsonify, request


def register_pincabos_batch_destination_browser(
    app,
    mounted_destinations_fn,
    inside_fn,
    local_exports,
):
    marker = "PINCABOS_BATCH_DESTINATION_BROWSER_V3_UI"

    def safe_relative(value):
        raw = str(value or "").strip().replace("\\", "/").strip("/")

        if raw in ("", "."):
            return Path()

        if "\x00" in raw:
            raise ValueError("Chemin de destination invalide.")

        candidate = Path(raw)

        if candidate.is_absolute():
            raise ValueError("Chemin absolu refusé.")

        for part in candidate.parts:
            if part in ("", ".", ".."):
                raise ValueError("Remontée de chemin refusée.")

        return candidate

    def get_root(kind, mount_target=""):
        kind = str(kind or "").strip().lower()

        if kind == "local":
            local_exports.mkdir(parents=True, exist_ok=True)
            return local_exports.resolve()

        if kind == "mount":
            mounted = {
                entry["target"]: entry
                for entry in mounted_destinations_fn()
            }

            if mount_target not in mounted:
                raise RuntimeError(
                    "Destination USB/SMB invalide ou plus montée. Recharge la page."
                )

            root = Path(mount_target).resolve()

            if not root.exists() or not root.is_dir():
                raise RuntimeError("Le montage sélectionné n'est plus accessible.")

            return root

        raise RuntimeError("Type de destination invalide.")

    def resolve_folder(kind, mount_target="", relative="", writable=False):
        root = get_root(kind, mount_target)
        relative_path = safe_relative(relative)
        folder = (root / relative_path).resolve()

        if not inside_fn(folder, root):
            raise RuntimeError("Chemin hors destination refusé.")

        if not folder.exists() or not folder.is_dir():
            raise RuntimeError("Dossier destination introuvable.")

        if writable and not os.access(folder, os.W_OK | os.X_OK):
            raise RuntimeError(
                f"Pinball ne peut pas écrire dans la destination : {folder}"
            )

        return root, folder, relative_path

    def relative_text(relative_path):
        value = relative_path.as_posix()
        return "" if value in ("", ".") else value

    def destination_root(kind, mount_target="", relative=""):
        _root, folder, _relative = resolve_folder(
            kind,
            mount_target,
            relative,
            writable=True,
        )
        return folder

    @app.route("/api/batch-export/browse", methods=["GET"])
    def pincabos_batch_export_browse_v3():
        try:
            kind = request.args.get("kind", "local")
            mount_target = request.args.get("mount_target", "")
            relative = request.args.get("relative", "")

            root, folder, relative_path = resolve_folder(
                kind,
                mount_target,
                relative,
                writable=False,
            )

            folders = []

            for child in sorted(folder.iterdir(), key=lambda item: item.name.lower()):
                try:
                    if child.name.startswith(".") or child.is_symlink() or not child.is_dir():
                        continue

                    folders.append({
                        "name": child.name,
                        "writable": bool(os.access(child, os.W_OK | os.X_OK)),
                    })
                except OSError:
                    continue

            try:
                stat = os.statvfs(folder)
                free_bytes = stat.f_bavail * stat.f_frsize
            except OSError:
                free_bytes = 0

            return jsonify({
                "ok": True,
                "root": str(root),
                "display_path": str(folder),
                "relative": relative_text(relative_path),
                "writable": bool(os.access(folder, os.W_OK | os.X_OK)),
                "free_bytes": free_bytes,
                "folders": folders,
            })

        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/batch-export/mkdir", methods=["POST"])
    def pincabos_batch_export_mkdir_v3():
        try:
            data = request.get_json(silent=True) or {}

            kind = data.get("kind", "local")
            mount_target = data.get("mount_target", "")
            relative = data.get("relative", "")
            folder_name = str(data.get("name", "")).strip()

            if (
                not folder_name
                or folder_name in {".", ".."}
                or "/" in folder_name
                or "\\" in folder_name
                or "\x00" in folder_name
            ):
                raise ValueError("Nom de dossier invalide.")

            root, current, _relative = resolve_folder(
                kind,
                mount_target,
                relative,
                writable=True,
            )

            target = (current / folder_name).resolve()

            if not inside_fn(target, root):
                raise RuntimeError("Création hors destination refusée.")

            if target.exists():
                raise RuntimeError("Un fichier ou dossier porte déjà ce nom.")

            target.mkdir(mode=0o775)

            return jsonify({
                "ok": True,
                "display_path": str(target),
                "relative": relative_text(target.relative_to(root)),
            })

        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.after_request
    def pincabos_batch_destination_browser_ui_v3(response):
        if app.config.get("PINCABOS_IMPEXP_NATIVE_UI"):
            return response
        if request.method != "GET" or request.path != "/tools/batch-export":
            return response

        if response.direct_passthrough:
            return response

        if "text/html" not in (response.content_type or ""):
            return response

        try:
            body = response.get_data(as_text=True)
        except Exception:
            return response

        if marker in body:
            return response

        injection = r"""
<!-- PINCABOS_BATCH_DESTINATION_BROWSER_V3_UI -->
<style>
#pco-dest-browser-v3 { margin-top:16px; padding:16px; border:1px solid rgba(160,104,255,.48); border-radius:14px; background:rgba(0,0,0,.25); }
#pco-dest-browser-v3 .pco-db-path { margin:10px 0; padding:10px; border-radius:8px; background:rgba(0,0,0,.42); overflow-wrap:anywhere; }
#pco-dest-browser-v3 .pco-db-actions { display:flex; gap:8px; flex-wrap:wrap; margin:12px 0; }
#pco-dest-browser-v3 .pco-db-folders { display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:8px; max-height:320px; overflow:auto; margin-top:12px; }
#pco-dest-browser-v3 .pco-db-folder { padding:10px; text-align:left; border:1px solid rgba(255,255,255,.14); border-radius:8px; background:rgba(255,255,255,.04); color:inherit; cursor:pointer; }
#pco-dest-browser-v3 .pco-db-folder:hover { border-color:#a068ff; background:rgba(160,104,255,.14); }
#pco-dest-browser-v3 .pco-db-create { display:flex; gap:8px; flex-wrap:wrap; margin-top:12px; }
#pco-dest-browser-v3 .pco-db-create input { flex:1 1 250px; }
</style>

<script>
(function() {
  const form = document.querySelector('form[action="/tools/batch-export/run"]');
  if (!form || document.getElementById('pco-dest-browser-v3')) return;

  const mountSelect = form.querySelector('select[name="mount_target"]');
  const destinationPanel = mountSelect ? mountSelect.closest('.pco-batch-panel') : form;

  const hidden = document.createElement('input');
  hidden.type = 'hidden';
  hidden.name = 'destination_subpath';
  hidden.value = '';
  form.appendChild(hidden);

  const panel = document.createElement('section');
  panel.id = 'pco-dest-browser-v3';
  panel.innerHTML = `
    <h4 style="margin-top:0;">Parcourir USB / SMB</h4>
    <!-- PINCABOS_BATCH_DIRECT_DESTINATION_V1_UI --><p>Choisis le dossier où PinCabOS déposera directement les fichiers <code>.PinCabOS</code>.</p>
    <div class="pco-db-actions">
      <button type="button" class="button secondary" id="pco-db-open-v3">Parcourir les dossiers</button>
      <button type="button" class="button secondary" id="pco-db-use-v3" disabled>Utiliser ce dossier</button>
    </div>
    <div class="pco-db-path" id="pco-db-selected-v3">Destination choisie : racine du stockage sélectionné</div>
    <div id="pco-db-content-v3" hidden>
      <div class="pco-db-path" id="pco-db-path-v3">Chargement…</div>
      <div id="pco-db-info-v3"></div>
      <div class="pco-db-actions">
        <button type="button" class="button secondary" id="pco-db-parent-v3">← Dossier parent</button>
        <button type="button" class="button secondary" id="pco-db-refresh-v3">Actualiser</button>
      </div>
      <div class="pco-db-create">
        <input type="text" id="pco-db-name-v3" placeholder="Nom du nouveau dossier">
        <button type="button" class="button secondary" id="pco-db-mkdir-v3">Créer le dossier</button>
      </div>
      <div class="pco-db-folders" id="pco-db-folders-v3"></div>
    </div>
  `;
  destinationPanel.appendChild(panel);

  const content = document.getElementById('pco-db-content-v3');
  const openButton = document.getElementById('pco-db-open-v3');
  const useButton = document.getElementById('pco-db-use-v3');
  const selectedText = document.getElementById('pco-db-selected-v3');
  const pathText = document.getElementById('pco-db-path-v3');
  const infoText = document.getElementById('pco-db-info-v3');
  const folders = document.getElementById('pco-db-folders-v3');
  const parentButton = document.getElementById('pco-db-parent-v3');
  const refreshButton = document.getElementById('pco-db-refresh-v3');
  const mkdirButton = document.getElementById('pco-db-mkdir-v3');
  const mkdirName = document.getElementById('pco-db-name-v3');

  let state = null;
  let selectionKey = '';

  function currentKind() {
    const choice = form.querySelector('input[name="destination_kind"]:checked');
    return choice ? choice.value : 'local';
  }

  function currentMount() {
    return mountSelect ? mountSelect.value : '';
  }

  function sourceKey() {
    return currentKind() + '|' +
      (currentKind() === 'mount' ? currentMount() : 'local');
  }

  function parentOf(relative) {
    const parts = (relative || '').split('/').filter(Boolean);
    parts.pop();
    return parts.join('/');
  }

  function childOf(relative, name) {
    return [relative, name].filter(Boolean).join('/');
  }

  function setMessage(text, cssClass) {
    infoText.textContent = text || '';
    infoText.className = cssClass || '';
  }

  function resetSelection() {
    hidden.value = '';
    selectionKey = '';
    state = null;
    content.hidden = true;
    useButton.disabled = true;
    selectedText.textContent =
      'Destination choisie : racine du stockage sélectionné';
  }

  async function browse(relative) {
    if (currentKind() === 'mount' && !currentMount()) {
      content.hidden = false;
      pathText.textContent = 'Exploration impossible';
      setMessage('Choisis un USB ou SMB monté avant de parcourir.', 'bad');
      return;
    }

    content.hidden = false;
    pathText.textContent = 'Chargement…';
    folders.innerHTML = '';
    setMessage('', '');

    const params = new URLSearchParams({
      kind: currentKind(),
      relative: relative || ''
    });

    if (currentKind() === 'mount') {
      params.set('mount_target', currentMount());
    }

    try {
      const response = await fetch(
        '/api/batch-export/browse?' + params.toString()
      );

      const data = await response.json();

      if (!response.ok || !data.ok) {
        throw new Error(data.error || 'Exploration impossible.');
      }

      state = data;
      pathText.textContent = data.display_path;

      setMessage(
        (data.writable ? 'Écriture autorisée' : 'Lecture seule') +
        (data.free_bytes
          ? ' — espace libre : ' +
            (data.free_bytes / 1024 / 1024 / 1024).toFixed(2) + ' GiB'
          : ''),
        data.writable ? 'ok' : 'warn'
      );

      parentButton.disabled = !data.relative;
      useButton.disabled = !data.writable;
      mkdirButton.disabled = !data.writable;

      if (!data.folders.length) {
        const empty = document.createElement('div');
        empty.textContent = 'Aucun sous-dossier visible.';
        folders.appendChild(empty);
      }

      data.folders.forEach(function(folder) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'pco-db-folder';
        button.textContent =
          '📁 ' + folder.name +
          (folder.writable ? '' : ' — lecture seule');

        button.addEventListener('click', function() {
          browse(childOf(data.relative, folder.name));
        });

        folders.appendChild(button);
      });

    } catch (error) {
      pathText.textContent = 'Exploration impossible';
      setMessage(error.message || String(error), 'bad');
      useButton.disabled = true;
      mkdirButton.disabled = true;
    }
  }

  openButton.addEventListener('click', function() {
    browse(selectionKey === sourceKey() ? hidden.value : '');
  });

  parentButton.addEventListener('click', function() {
    browse(parentOf(state ? state.relative : ''));
  });

  refreshButton.addEventListener('click', function() {
    browse(state ? state.relative : '');
  });

  useButton.addEventListener('click', function() {
    if (!state || !state.writable) return;

    hidden.value = state.relative || '';
    selectionKey = sourceKey();

    selectedText.textContent =
      'Destination choisie : ' + state.display_path;

    setMessage('Destination retenue : les fichiers .PinCabOS seront déposés directement ici.', 'ok');
  });

  mkdirButton.addEventListener('click', async function() {
    const name = mkdirName.value.trim();

    if (!state || !state.writable) return;

    if (!name) {
      setMessage('Entre un nom de dossier.', 'bad');
      return;
    }

    mkdirButton.disabled = true;

    try {
      const response = await fetch('/api/batch-export/mkdir', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          kind: currentKind(),
          mount_target:
            currentKind() === 'mount' ? currentMount() : '',
          relative: state.relative || '',
          name: name
        })
      });

      const data = await response.json();

      if (!response.ok || !data.ok) {
        throw new Error(data.error || 'Création impossible.');
      }

      mkdirName.value = '';
      await browse(data.relative);

      if (state && state.writable) {
        hidden.value = state.relative || '';
        selectionKey = sourceKey();
        selectedText.textContent =
          'Destination choisie : ' + state.display_path;
      }

    } catch (error) {
      setMessage(error.message || String(error), 'bad');
    } finally {
      mkdirButton.disabled = !state || !state.writable;
    }
  });

  form.querySelectorAll(
    'input[name="destination_kind"]'
  ).forEach(function(input) {
    input.addEventListener('change', resetSelection);
  });

  if (mountSelect) {
    mountSelect.addEventListener('change', resetSelection);
  }
})();
</script>
"""

        if "</body>" in body:
            body = body.replace("</body>", injection + "</body>", 1)
        else:
            body += injection

        response.set_data(body)
        response.headers.pop("Content-Length", None)
        return response

    return SimpleNamespace(destination_root=destination_root)
