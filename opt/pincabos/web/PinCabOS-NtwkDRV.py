# PinCabOS-NtwkDRV.py
# Module externe pour Gestion du stockage / SMB.
# Garde la mise en page PinCabOS, mais évite le vieux scan silencieux de app.py.

from pathlib import Path
from flask import request
import datetime
import json
import os
import shutil
import subprocess


NETWORK_ROOT = Path("/home/pinball/NetworkDrives")
SMB_CRED_ROOT = Path("/home/pinball/.config/pincabos/smb")
SMB_DISCONNECTED_ROOT = Path("/home/pinball/.config/pincabos/smb-disconnected")
SMB_UMOUNT_HELPER = "/usr/local/sbin/pincabos-smb-umount"

USB_ROOTS = [
    Path("/media/pinball"),
    Path("/run/media/pinball"),
]


def _run(cmd, timeout=15):
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _is_mountpoint(path):
    try:
        return _run(["/usr/bin/mountpoint", "-q", str(path)], timeout=10).returncode == 0
    except Exception:
        return False


def _direct_child(root, name):
    name = (name or "").strip()
    if not name or "/" in name or "\\" in name or name in {".", ".."}:
        return None

    root = Path(root)
    target = root / name

    try:
        root_abs = os.path.abspath(str(root))
        target_abs = os.path.abspath(str(target))
        if os.path.commonpath([root_abs, target_abs]) != root_abs:
            return None
    except Exception:
        return None

    return target


def _findmnt_smb_targets():
    items = {}

    try:
        result = _run(
            [
                "/usr/bin/findmnt",
                "-J",
                "-t",
                "cifs,smb3,smbfs",
                "-o",
                "TARGET,SOURCE,FSTYPE",
            ],
            timeout=10,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return items

        data = json.loads(result.stdout)
        for fs in data.get("filesystems", []):
            target = fs.get("target") or ""
            source = fs.get("source") or ""
            target_path = Path(target)

            try:
                root_abs = os.path.abspath(str(NETWORK_ROOT))
                target_abs = os.path.abspath(str(target_path))
                if os.path.commonpath([root_abs, target_abs]) != root_abs:
                    continue
            except Exception:
                continue

            try:
                rel = target_path.relative_to(NETWORK_ROOT)
                if len(rel.parts) != 1:
                    continue
            except Exception:
                continue

            items[target_path.name] = {
                "name": target_path.name,
                "path": target_path,
                "source": source,
            }
    except Exception:
        pass

    return items


def _smb_entries():
    NETWORK_ROOT.mkdir(parents=True, exist_ok=True)
    items = {}

    # 1) Dossiers connus/configurés.
    try:
        for d in NETWORK_ROOT.iterdir():
            if d.is_dir():
                items[d.name] = {
                    "name": d.name,
                    "path": d,
                    "source": "",
                }
    except Exception:
        pass

    # 2) Montages réels détectés par findmnt, même si le scan dossier échoue.
    items.update(_findmnt_smb_targets())

    return [items[k] for k in sorted(items.keys(), key=lambda x: x.lower())]


def _usb_entries():
    items = {}

    for root in USB_ROOTS:
        if not root.exists():
            continue

        try:
            for d in root.iterdir():
                if d.is_dir() and _is_mountpoint(d):
                    items[d.name] = {
                        "name": d.name,
                        "path": d,
                    }
        except Exception:
            pass

    return [items[k] for k in sorted(items.keys(), key=lambda x: x.lower())]


def _result_page(page, esc, title, ok, message):
    cls = "ok" if ok else "bad"
    return page("Gestion du stockage", f"""
<div class="card">
  <h2>{esc(title)}</h2>
  <pre class="{cls}">{esc(message or "")}</pre>
  <p><a class="button" href="/tools/external-disks">Retour</a></p>
</div>
""")


def _disconnect_view(page, esc):
    target = _direct_child(
        NETWORK_ROOT,
        request.form.get("drive_name", ""),
    )

    if target is None:
        return _result_page(
            page,
            esc,
            "Déconnexion SMB échouée",
            False,
            "Nom de lecteur SMB invalide.",
        )

    messages = []

    if _is_mountpoint(target):
        try:
            result = _run(
                [
                    "/usr/bin/sudo",
                    "-n",
                    SMB_UMOUNT_HELPER,
                    str(target),
                ],
                timeout=45,
            )
            output = (result.stdout + "\n" + result.stderr).strip()
        except subprocess.TimeoutExpired:
            return _result_page(
                page,
                esc,
                "Déconnexion SMB échouée",
                False,
                "La déconnexion SMB a dépassé le délai pendant le démontage.",
            )

        if result.returncode != 0:
            return page("Gestion du stockage", f"""
<div class="card">
  <h2>Déconnexion SMB échouée</h2>
  <p class="bad">Le lecteur est peut-être encore utilisé.</p>
  <h3>Détail</h3>
  <pre>{esc(output or "Aucun détail retourné.")}</pre>
  <p><a class="button" href="/tools/external-disks">Retour</a></p>
</div>
""")

        messages.append(output or "Montage SMB arrêté.")

    try:
        cred = SMB_CRED_ROOT / (target.name + ".cred")
        if cred.exists():
            cred.unlink()
            messages.append("Identifiants SMB supprimés.")
    except Exception as e:
        messages.append(f"Identifiants SMB non supprimés: {e}")

    # Déconnecter retire l'entrée seulement après démontage confirmé.
    if _is_mountpoint(target):
        return _result_page(
            page,
            esc,
            "Déconnexion SMB partielle",
            False,
            "Le lecteur est encore monté. Entrée conservée.",
        )

    try:
        if target.exists() and target.is_dir():
            try:
                target.rmdir()
                messages.append("Entrée SMB retirée de la liste.")
            except OSError:
                SMB_DISCONNECTED_ROOT.mkdir(parents=True, exist_ok=True)
                stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
                archive_target = SMB_DISCONNECTED_ROOT / f"{target.name}-{stamp}"
                shutil.move(str(target), str(archive_target))
                messages.append(f"Dossier local non vide déplacé vers {archive_target}.")
    except Exception as e:
        return _result_page(
            page,
            esc,
            "Déconnexion SMB partielle",
            False,
            f"Erreur pendant le retrait de l'entrée: {e}",
        )

    return _result_page(
        page,
        esc,
        "Déconnexion SMB terminée",
        True,
        "\n".join(messages) or "Lecteur SMB déconnecté.",
    )


def _external_disks_page(page, esc):
    usb_list = ""
    for item in _usb_entries():
        usb_list += f"""
<li style="margin-bottom:10px;">
  <strong>{esc(item["name"])}</strong> —
  <span class="ok">Monté</span> —
  <code>{esc(str(item["path"]))}</code>
  <form action="/tools/external-disks/usb/unmount" method="post" style="display:inline; margin-left:10px;">
    <input type="hidden" name="drive_name" value="{esc(item["name"])}">
    <button class="button secondary" type="submit">Démonter</button>
  </form>
</li>
"""

    if not usb_list:
        usb_list = "<li>Aucune clé USB montée.</li>"

    smb_list = ""
    for item in _smb_entries():
        name = item["name"]
        path = item["path"]
        mounted = _is_mountpoint(path)

        cls = "ok" if mounted else "warn"
        status = "Monté" if mounted else "Non monté"

        disconnect_button = f"""
<form action="/tools/external-disks/smb/disconnect" method="post" style="display:inline; margin-left:8px;" onsubmit="return confirm('Confirmer la déconnexion de ce lecteur SMB ?');">
  <input type="hidden" name="drive_name" value="{esc(name)}">
  <button class="button secondary" type="submit">Déconnecter</button>
</form>
"""

        if mounted:
            action_button = f"""
<form action="/tools/external-disks/smb/unmount" method="post" style="display:inline; margin-left:10px;">
  <input type="hidden" name="drive_name" value="{esc(name)}">
  <button class="button secondary" type="submit">Démonter</button>
</form>
{disconnect_button}
"""
        else:
            action_button = f"""
<a class="button secondary" href="#connecter-smb" style="display:inline-block; margin-left:10px;">
  Monter / reconnecter
</a>
{disconnect_button}
"""

        smb_list += f"""
<li style="margin-bottom:10px;">
  <strong>{esc(name)}</strong> —
  <span class="{cls}">{status}</span> —
  <code>{esc(str(path))}</code>
  {action_button}
</li>
"""

    if not smb_list:
        smb_list = "<li>Aucun lecteur SMB monté/configuré.</li>"

    body = f"""
<!-- PINCABOS_STOCKAGE_INTERNE_V1 -->
<div class="card">
  <h2>Disque interne</h2>

  <p>
    Héberger la bibliothèque de tables sur un second disque interne, y compris
    un disque NTFS repris d'un ancien cabinet Windows. Le dossier des tables
    reste au choix, et le montage au démarrage est optionnel.
  </p>

  <p>
    <a class="button" href="/tools/internal-disk">Gérer le disque interne</a>
  </p>
</div>

<div class="card" style="margin-top:20px;">
  <h2>Partages réseau</h2>

  <p>
    Ajoute un partage SMB / NAS / Windows à PinCabOS.
    Après montage, il apparaîtra dans <strong>PinCab Explorer → Lecteurs SMB</strong>.
  </p>

  <p>
    <a class="button secondary" href="/tools">Retour Outils</a>
    <a class="button" href="/tools/commander?root=Lecteurs%20SMB">Ouvrir Lecteurs SMB dans PinCab Explorer</a>
  </p>
</div>

<div class="card" style="margin-top:20px;">
  <h2 id="connecter-smb">Connecter un partage SMB</h2>

  <p>Étape 1 : entre les informations du serveur. PinCabOS va se connecter et détecter les partages disponibles.</p>

  <form action="/tools/external-disks/smb/detect" method="post">
    <label>Nom du lecteur dans PinCabOS</label>
    <input name="display_name" placeholder="exemple: NAS-Tables">

    <label style="margin-top:12px;">Adresse serveur ou IP</label>
    <input name="server" placeholder="exemple: 192.168.254.10 ou NAS-SYNOLOGY">

    <label style="margin-top:12px;">Login</label>
    <input name="username" placeholder="utilisateur SMB">

    <label style="margin-top:12px;">Password</label>
    <input type="password" name="password" placeholder="mot de passe SMB">

    <label style="margin-top:12px;">Domaine / Workgroup optionnel</label>
    <input name="domain" placeholder="WORKGROUP" value="WORKGROUP">

    <p style="margin-top:16px;">
      <button class="button" type="submit">Connecter et détecter les partages</button>
    </p>
  </form>
</div>

<div class="card" style="margin-top:20px;">
  <h2>Clés USB</h2>
  <p>Les clés USB montées automatiquement apparaissent ici et dans <strong>PinCab Explorer → Clés USB</strong>.</p>
  <ul>
    {usb_list}
  </ul>
</div>

<div class="card" style="margin-top:20px;">
  <h2>Lecteurs SMB</h2>
  <ul>
    {smb_list}
  </ul>
</div>
"""

    return page("Gestion du stockage", body)


def _replace_or_add_route(app, rule_path, methods, endpoint_name, view_func):
    wanted_methods = set(methods)

    for rule in app.url_map.iter_rules():
        if rule.rule == rule_path and wanted_methods.issubset(rule.methods):
            app.view_functions[rule.endpoint] = view_func
            return "replaced"

    app.add_url_rule(
        rule_path,
        endpoint=endpoint_name,
        view_func=view_func,
        methods=list(methods),
    )
    return "added"


def register(app, page, esc, shlex_quote=None):
    def external_disks_view():
        return _external_disks_page(page, esc)

    def smb_disconnect_view():
        return _disconnect_view(page, esc)

    page_mode = _replace_or_add_route(
        app,
        "/tools/external-disks",
        ["GET"],
        "pincabos_ntwkdrv_external_disks",
        external_disks_view,
    )

    disconnect_mode = _replace_or_add_route(
        app,
        "/tools/external-disks/smb/disconnect",
        ["POST"],
        "pincabos_ntwkdrv_smb_disconnect",
        smb_disconnect_view,
    )

    print(f"GO: PinCabOS-NtwkDRV module loaded page={page_mode} disconnect={disconnect_mode}")
