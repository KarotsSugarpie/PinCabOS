"""Gestion du stockage de la WebApp PinCabOS : disques externes USB et partages SMB (/tools/external-disks).

Aplatissement (PINCABOS_WEBAPP_MODULES_V1, lot 8) de trois couches qui se remplaçaient l'une l'autre au
démarrage : les routes d'origine d'app.py, leurs remplacements à chaud (démontage sûr, montage SMB enveloppé)
et le module externe `PinCabOS-NtwkDRV.py` de Karots Sugarpie (page, déconnexion SMB, montage / démontage USB).
Chaque chemin a ici une seule vue : celle qui répondait réellement à l'exécution. Le code est repris tel quel.

`page()` (gabarit commun) est fourni par app.py à l'enregistrement : `register(app, page)`.
"""
from __future__ import annotations

import datetime
import json
import os
import shutil
import subprocess
from pathlib import Path

from flask import Blueprint, current_app, request

from pincabos_webapp_core import esc

disques_bp = Blueprint("disques", __name__)

page = None  # gabarit HTML commun, posé par register()


# ---------------------------------------------------------------------------
# Page, déconnexion SMB, USB : repris de PinCabOS-NtwkDRV.py (Karots Sugarpie)
# ---------------------------------------------------------------------------
NETWORK_ROOT = Path("/home/pinball/NetworkDrives")
SMB_CRED_ROOT = Path("/home/pinball/.config/pincabos/smb")
SMB_DISCONNECTED_ROOT = Path("/home/pinball/.config/pincabos/smb-disconnected")
SMB_UMOUNT_HELPER = "/usr/local/sbin/pincabos-smb-umount"
USB_HELPER = "/usr/local/sbin/pincabos-usb-disk"

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
    # PINCABOS_USB_MOUNT_V1
    #
    # On enumere les supports USB qu'ils soient montes ou non. L'ancienne
    # version ne parcourait que /media/pinball : comme rien ne monte les
    # cles sur un cabinet, la liste etait vide en permanence et un support
    # branche passait pour non reconnu.
    try:
        sortie = subprocess.run(
            [USB_HELPER, "list", "--json"],
            capture_output=True,
            text=True,
            timeout=20,
        ).stdout
        supports = json.loads(sortie)
    except Exception:
        supports = []

    return supports if isinstance(supports, list) else []


def _usb_taille(octets) -> str:
    try:
        valeur = float(octets)
    except (TypeError, ValueError):
        return ""
    for unite in ("o", "Ko", "Mo", "Go", "To"):
        if valeur < 1000 or unite == "To":
            return f"{valeur:.0f} {unite}" if unite == "o" else f"{valeur:.1f} {unite}"
        valeur /= 1000
    return ""


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
        nom = item.get("etiquette") or item.get("nom") or "support"
        details = " — ".join(
            p for p in (
                _usb_taille(item.get("taille")),
                (item.get("systeme") or "").upper(),
                item.get("peripherique", ""),
            ) if p
        )

        if item.get("montage"):
            etat = f'<span class="ok">Monté</span> — <code>{esc(item["montage"])}</code>'
            action = f"""
  <form action="/tools/external-disks/usb/unmount" method="post" style="display:inline; margin-left:10px;">
    <input type="hidden" name="uuid" value="{esc(item.get("uuid", ""))}">
    <button class="button secondary" type="submit">Démonter</button>
  </form>"""
        elif item.get("montable"):
            etat = '<span class="avert">Non monté</span>'
            action = f"""
  <form action="/tools/external-disks/usb/mount" method="post" style="display:inline; margin-left:10px;">
    <input type="hidden" name="uuid" value="{esc(item.get("uuid", ""))}">
    <button class="button" type="submit">Monter</button>
  </form>"""
        else:
            etat = f'<span class="bad">Inutilisable</span> — {esc(item.get("raison", ""))}'
            action = ""

        usb_list += f"""
<li style="margin-bottom:10px;">
  <strong>{esc(nom)}</strong> — {etat}<br>
  <small>{esc(details)}</small>{action}
</li>
"""

    if not usb_list:
        usb_list = "<li>Aucun support USB détecté. Branchez-en un, puis rafraîchissez cette page.</li>"

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
  <h2>Stockage USB</h2>
  <p>Les supports USB branchés apparaissent ici — clés comme disques durs. Une fois montés, ils sont accessibles dans <strong>PinCab Explorer → Stockage USB</strong>.</p>
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

@disques_bp.route("/tools/external-disks")
def tools_external_disks():
    return _external_disks_page(page, esc)


@disques_bp.route("/tools/external-disks/smb/disconnect", methods=["POST"])
def tools_external_disks_smb_disconnect():
    return _disconnect_view(page, esc)


def _usb_action(action):
    uuid = (request.form.get("uuid") or "").strip()
    if not uuid:
        return _result_page(page, esc, "Support non précisé", False,
                            "Aucun identifiant de support n'a été transmis.")
    resultat = _run(["/usr/bin/sudo", "-n", USB_HELPER, action, uuid], timeout=90)
    sortie = (resultat.stdout or "") + (resultat.stderr or "")
    reussi = resultat.returncode == 0
    titre = "Support monté" if action == "mount" else "Support démonté"
    return _result_page(
        page, esc,
        titre if reussi else "Opération refusée",
        reussi,
        sortie.strip() or ("Terminé." if reussi else "Échec sans message."),
    )


@disques_bp.route("/tools/external-disks/usb/mount", methods=["POST"])
def tools_external_disks_usb_mount():
    return _usb_action("mount")


@disques_bp.route("/tools/external-disks/usb/unmount", methods=["POST"])
def tools_external_disks_usb_unmount():
    return _usb_action("unmount")


# ---------------------------------------------------------------------------
# Détection et montage SMB : repris d'app.py
# ---------------------------------------------------------------------------

@disques_bp.route("/tools/external-disks/smb/detect", methods=["POST"])
def tools_external_disks_smb_detect():
    import json
    import re
    import time
    import uuid
    import subprocess
    from pathlib import Path

    drive_name = request.form.get("drive_name", "").strip()
    server = request.form.get("server", "").strip()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    domain = request.form.get("domain", "").strip() or "WORKGROUP"

    if not server or not username:
        return page("Gestion du stockage", """
<div class="card">
  <h2>Erreur SMB</h2>
  <p class="bad">Serveur/IP et login requis.</p>
  <p><a class="button" href="/tools/external-disks">Retour</a></p>
</div>
""")

    safe_name = re.sub(r"[^A-Za-z0-9._ -]+", "_", drive_name).strip()
    if not safe_name:
        safe_name = server.replace(".", "-").replace("/", "-")

    session_id = uuid.uuid4().hex
    session_dir = Path("/home/pinball/.config/pincabos/smb-sessions")
    session_dir.mkdir(parents=True, exist_ok=True)

    session_file = session_dir / (session_id + ".json")
    session_file.write_text(json.dumps({
        "drive_name": safe_name,
        "server": server,
        "username": username,
        "password": password,
        "domain": domain,
        "created": time.time(),
    }, indent=2, ensure_ascii=False))
    session_file.chmod(0o600)

    cmd = ["smbclient", "-L", "//" + server, "-U", username + "%" + password, "-m", "SMB3", "-g"]

    if domain:
        cmd.extend(["-W", domain])

    shares = []
    error = ""

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
        output = (r.stdout + "\\n" + r.stderr)

        for line in output.splitlines():
            line = line.strip()

            # Format attendu avec -g : Disk|ShareName|Comment
            if line.startswith("Disk|"):
                parts = line.split("|")
                if len(parts) >= 2:
                    share = parts[1].strip()
                    if share and not share.endswith("$"):
                        shares.append(share)

        if r.returncode != 0 and not shares:
            error = output[-4000:]

    except Exception as e:
        error = str(e)

    if not shares:
        body = f"""
<div class="card">
  <h2>Aucun partage détecté</h2>

  <p class="bad">
    PinCabOS n’a pas réussi à détecter les partages disponibles.
    Vérifie l’adresse/IP, le login, le mot de passe et les permissions du compte.
  </p>

  <h3>Détail</h3>
  <pre>{esc(error)}</pre>

  <p>
    <a class="button" href="/tools/external-disks">Retour</a>
  </p>
</div>
"""
        return page("Partages SMB", body)

    options = ""
    for share in shares:
        options += f'<option value="{esc(share)}">{esc(share)}</option>'

    body = f"""
<div class="card">
  <h2>Partages SMB détectés</h2>

  <p>
    Connexion réussie au serveur : <strong>{esc(server)}</strong>
  </p>

  <form action="/tools/external-disks/smb/mount" method="post">
    <input type="hidden" name="session_id" value="{esc(session_id)}">

    <label>Choisir le partage à monter</label><br>
    <select name="share" style="width:90%; padding:8px; margin:8px 0;">
      {options}
    </select><br><br>

    <button class="button" type="submit">Monter le partage sélectionné</button>
    <a class="button secondary" href="/tools/external-disks">Annuler</a>
  </form>
</div>
"""
    return page("Partages SMB", body)


def _smb_mount_impl():
    import json
    import re
    import subprocess
    from pathlib import Path

    session_id = request.form.get("session_id", "").strip()
    share = request.form.get("share", "").strip()

    session_file = Path("/home/pinball/.config/pincabos/smb-sessions") / (session_id + ".json")

    if not session_id or not share or not session_file.exists():
        return page("Gestion du stockage", """
<div class="card">
  <h2>Erreur SMB</h2>
  <p class="bad">Session SMB invalide ou expirée.</p>
  <p><a class="button" href="/tools/external-disks">Retour</a></p>
</div>
""")

    data = json.loads(session_file.read_text())

    drive_name = data["drive_name"]
    server = data["server"]
    username = data["username"]
    password = data["password"]
    domain = data.get("domain") or "WORKGROUP"

    safe_name = re.sub(r"[^A-Za-z0-9._ -]+", "_", drive_name).strip()
    if not safe_name:
        safe_name = share

    mount_root = Path("/home/pinball/NetworkDrives")
    mount_point = mount_root / safe_name

    cred_root = Path("/home/pinball/.config/pincabos/smb")
    cred_root.mkdir(parents=True, exist_ok=True)
    mount_point.mkdir(parents=True, exist_ok=True)

    cred_file = cred_root / (safe_name + ".cred")
    cred_file.write_text(
        "username=" + username + "\n" +
        "password=" + password + "\n" +
        "domain=" + domain + "\n"
    )
    cred_file.chmod(0o600)

    try:
        subprocess.run(["chown", "-R", "pinball:pinball", str(mount_root), str(cred_root)], timeout=30)
    except Exception:
        pass

    source = f"//{server}/{share}"

    # PINCABOS_SECURE_SMB_MOUNT_V1
    cmd = [
        "/usr/bin/sudo", "-n",
        "/usr/local/sbin/pincabos-smb-mount",
        source, str(mount_point), str(cred_file),
    ]

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=75)
        output = (r.stdout + "\\n" + r.stderr).strip()
    except subprocess.TimeoutExpired as e:
        output = "Le montage SMB a dépassé le délai. Le serveur NAS ne répond pas assez vite ou les options SMB sont incompatibles.\\n"
        output += "Commande: " + " ".join(str(part) for part in cmd)
        r = type("Result", (), {"returncode": 124})()

    try:
        session_file.unlink()
    except Exception:
        pass

    if r.returncode != 0:
        body = f"""
<div class="card">
  <h2>Montage SMB échoué</h2>

  <p class="bad">Le partage a été détecté, mais le montage a échoué.</p>

  <h3>Détail</h3>
  <pre>{esc(output)}</pre>

  <p>
    <a class="button" href="/tools/external-disks">Retour</a>
  </p>
</div>
"""
        return page("Gestion du stockage", body)

    body = f"""
<div class="card">
  <h2>Partage SMB monté</h2>

  <p class="ok">
    Le partage <strong>{esc(share)}</strong> est maintenant monté dans :
  </p>

  <pre>{esc(str(mount_point))}</pre>

  <p>
    <a class="button" href="/tools/commander?root=Lecteurs%20SMB">Ouvrir dans PinCab Explorer</a>
    <a class="button secondary" href="/tools/external-disks">Retour Gestion du stockage</a>
  </p>
</div>
"""
    return page("Gestion du stockage", body)


@disques_bp.route("/tools/external-disks/smb/mount", methods=["POST"])
def tools_external_disks_smb_mount():
    """Montage SMB « sûr » : toute exception non gérée devient une page lisible avec le détail (ex-enveloppe d'app.py)."""
    try:
        return _smb_mount_impl()
    except Exception as exc:
        current_app.logger.exception(
            "PINCABOS SMB: exception non geree dans la route de montage"
        )
        detail = f"{type(exc).__name__}: {exc}"
        return page("Montage SMB échoué", f"""
<div class="card">
  <h2>Montage SMB échoué</h2>
  <p class="bad">
    La page a intercepté une erreur interne au lieu de retourner une erreur 500.
  </p>
  <p><strong>Détail réel :</strong></p>
  <pre>{esc(detail)}</pre>
  <p>
    <a class="button" href="/tools/external-disks">Retour</a>
  </p>
</div>
""")


# ---------------------------------------------------------------------------
# Démontage SMB sûr : repris d'app.py (vue qui remplaçait l'alias vide)
# ---------------------------------------------------------------------------

def _pincabos_direct_mount_child(root_text, requested_name):
    from pathlib import Path

    name = (requested_name or "").strip()

    if (
        not name
        or name in {".", ".."}
        or "/" in name
        or "\\" in name
        or "\x00" in name
    ):
        return None

    root = Path(root_text).resolve()
    target = (root / name).resolve(strict=False)

    if target.parent != root:
        return None

    return target


def _pincabos_external_disk_result(title, ok, detail, back_url):
    cls = "ok" if ok else "bad"
    label = "Démontage réussi" if ok else "Démontage échoué"

    return page(title, f"""
<div class="card">
  <h2>{label}</h2>
  <p class="{cls}">{esc(detail)}</p>
  <p>
    <a class="button" href="{esc(back_url)}">Retour</a>
  </p>
</div>
""")


@disques_bp.route("/tools/external-disks/smb/unmount", methods=["POST"])
def tools_external_disks_smb_unmount():
    import subprocess

    target = _pincabos_direct_mount_child(
        str(NETWORK_ROOT),
        request.form.get("drive_name", ""),
    )

    if target is None:
        return _pincabos_external_disk_result(
            "Gestion du stockage",
            False,
            "Nom de lecteur SMB invalide.",
            "/tools/external-disks",
        )

    try:
        result = subprocess.run(
            [
                "/usr/bin/sudo",
                "-n",
                SMB_UMOUNT_HELPER,
                str(target),
            ],
            capture_output=True,
            text=True,
            timeout=45,
        )

        output = (result.stdout + "\n" + result.stderr).strip()

    except subprocess.TimeoutExpired:
        return _pincabos_external_disk_result(
            "Gestion du stockage",
            False,
            "Le démontage SMB a dépassé le délai.",
            "/tools/external-disks",
        )

    if result.returncode != 0:
        return page("Gestion du stockage", f"""
<div class="card">
  <h2>Démontage SMB échoué</h2>
  <p class="bad">Le lecteur est peut-être encore utilisé.</p>
  <h3>Détail</h3>
  <pre>{esc(output or "Aucun détail retourné.")}</pre>
  <p><a class="button" href="/tools/external-disks">Retour</a></p>
</div>
""")

    # Le mot de passe SMB ne reste pas apres un demontage reussi.
    try:
        cred = (
            Path("/home/pinball/.config/pincabos/smb")
            / (target.name + ".cred")
        )
        cred.unlink(missing_ok=True)
    except Exception:
        pass

    return _pincabos_external_disk_result(
        "Gestion du stockage",
        True,
        output or "Lecteur SMB démonté.",
        "/tools/external-disks",
    )


# ---------------------------------------------------------------------------
# Lien « disques » sur la page Commander (PINCABOS_EXTERNAL_DISKS_MENU_V2), repris d'app.py
# ---------------------------------------------------------------------------

@disques_bp.after_app_request
def pincabos_external_disks_menu_link(response):
    try:
        from flask import request as _request
        import re as _re
        from html import escape as _html_escape

        if _request.path.rstrip("/") != "/tools/commander":
            return response

        if response.status_code != 200 or response.is_streamed:
            return response

        if response.mimetype != "text/html":
            return response

        body = response.get_data(as_text=True)

        if 'data-pcx-external-disks-menu="1"' in body:
            return response

        pattern = _re.compile(
            r'(?P<link>'
            r'<a\b'
            r'(?P<attrs>[^>]*\bhref\s*=\s*(?P<quote>["\'])'
            r'/tools/commander\?root=Lecteurs(?:%20|\+| )SMB[^"\']*(?P=quote)[^>]*)>'
            r'(?P<label>.*?)'
            r'</a>)',
            _re.IGNORECASE | _re.DOTALL,
        )

        match = pattern.search(body)
        if not match:
            return response

        visible = _re.sub(r"<[^>]+>", " ", match.group("label"))
        visible = " ".join(visible.split()).lower()

        if "lecteurs smb" not in visible:
            return response

        class_match = _re.search(
            r'\bclass\s*=\s*(["\'])(.*?)\1',
            match.group("attrs"),
            _re.IGNORECASE | _re.DOTALL,
        )

        css_class = class_match.group(2) if class_match else "pcx-btn"

        # Enleve toute classe de selection ou etat actif copiee du SMB.
        css_class = " ".join(
            token for token in css_class.split()
            if not any(
                flag in token.lower()
                for flag in ("active", "selected", "current")
            )
        )

        css_class = _html_escape(css_class or "pcx-btn", quote=True)

        link = (
            '\n<a class="' + css_class + '" '
            'href="/tools/external-disks" '
            'data-pcx-external-disks-menu="1" '
            'title="Gerer le stockage : disque interne, cles USB et partages SMB">'
            '💾 Stockage</a>'
        )

        response.set_data(body[:match.end()] + link + body[match.end():])
        return response

    except Exception:
        return response


def register(app, page_fn):
    """Enregistre la gestion du stockage (USB, SMB) sur l'application."""
    global page
    page = page_fn
    app.register_blueprint(disques_bp)
