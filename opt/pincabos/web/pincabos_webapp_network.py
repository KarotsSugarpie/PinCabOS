# PinCabOS WebApp module : Réseau (PINCABOS_RESEAU_V1).
# Page /network : nom de machine, chaque interface (DHCP par défaut, adressage
# fixe proposé depuis le bail DHCP), Wi-Fi seulement si un matériel est présent
# (balayage, chiffrement détecté et compatibilité avec la carte), hotspot.
# Toute la logique vit dans /opt/pincabos/tools/pincabos_network.py (CLI
# pincabos-network) ; cette page ne fait que présenter et relayer.
from __future__ import annotations

import html
import subprocess
import sys

from flask import redirect, request

if "/opt/pincabos/tools" not in sys.path:
    sys.path.insert(0, "/opt/pincabos/tools")
import pincabos_network as net  # noqa: E402

CLI = "/opt/pincabos/tools/pincabos-network"
_page = None
_esc = html.escape


def esc(v):
    return _esc("" if v is None else str(v))


def _classe(ligne: str) -> str:
    if ligne.startswith("GO"):
        return "good"
    if ligne.startswith("NOGO"):
        return "bad"
    if ligne.startswith("WARN"):
        return "warn"
    return ""


def resultat(titre: str, journal: list, retour: str = "/network"):
    lignes = "".join(f"<div class='{_classe(l)}'><code>{esc(l)}</code></div>" for l in journal)
    body = f"""
<div class="card">
  <h1>{esc(titre)}</h1>
  {lignes or "<p>Rien à faire.</p>"}
  <p style="margin-top:14px"><a class="button" href="{esc(retour)}">Retour Réseau</a></p>
</div>
"""
    return _page("Réseau", body)


def _sudo(*args, timeout=90) -> list:
    """Actions qui exigent root : par la commande, sous sudo (pinball : NOPASSWD)."""
    try:
        r = subprocess.run(["/usr/bin/sudo", "-n", CLI, *args], capture_output=True, text=True, timeout=timeout)
        return [l for l in (r.stdout + r.stderr).splitlines() if l.strip()] or [f"NOGO: {CLI} {' '.join(args)} : aucun retour (code {r.returncode})"]
    except Exception as exc:
        return [f"NOGO: {exc}"]


def carte_interface(e: dict) -> str:
    p = e["proposition"]
    dev = e["device"]
    genre = "Wi-Fi" if e["type"] == "wifi" else "Ethernet"
    if p["source"] == "dhcp":
        note = "Valeurs reçues du DHCP, proposées telles quelles pour un adressage fixe."
    elif p["source"] == "manuel":
        note = "Configuration fixe actuelle."
    elif p["source"] == "courant":
        note = "Valeurs actuellement en place sur l'interface."
    else:
        note = "Aucune réponse DHCP : DNS proposés 9.9.9.9 et 1.1.1.1 ; la passerelle ne peut pas être devinée, elle est à saisir."
    dhcp_sel = "selected" if e["method"] != "manual" else ""
    fixe_sel = "selected" if e["method"] == "manual" else ""
    etat_ip = e["address"] or "aucune adresse"
    return f"""
<div class="card">
  <h2>{esc(genre)} · <code>{esc(dev)}</code></h2>
  <p>État : <code>{esc(e['state'] or 'inconnu')}</code> · mode : <code>{esc('DHCP' if e['method'] == 'auto' else 'IP fixe' if e['method'] == 'manual' else e['method'] or '?')}</code>
     · adresse : <code>{esc(etat_ip)}</code> · passerelle : <code>{esc(e['gateway'] or '—')}</code> · DNS : <code>{esc(', '.join(e['dns']) or '—')}</code>
     · MAC : <code>{esc(e['hwaddr'] or '—')}</code></p>
  <form method="post" action="/network/apply-mode" onsubmit="return confirmerReseau(this)">
    <input type="hidden" name="iface" value="{esc(dev)}">
    <label>Adressage</label>
    <select name="mode" onchange="basculerFixe(this)" style="width:90%;padding:8px;margin:6px 0">
      <option value="dhcp" {dhcp_sel}>DHCP automatique (par défaut)</option>
      <option value="static" {fixe_sel}>IP fixe</option>
    </select>
    <div class="fixe" style="{'display:block' if fixe_sel else 'display:none'}">
      <p style="opacity:.75;font-size:.9em">{esc(note)}</p>
      <label>Adresse IP / préfixe</label>
      <input name="address" value="{esc(p['address'])}" placeholder="192.168.1.50/24" style="width:90%;padding:8px;margin:6px 0">
      <label>Passerelle</label>
      <input name="gateway" value="{esc(p['gateway'])}" placeholder="192.168.1.1" style="width:90%;padding:8px;margin:6px 0">
      <label>DNS (séparés par des virgules)</label>
      <input name="dns" value="{esc(', '.join(p['dns']))}" placeholder="9.9.9.9, 1.1.1.1" style="width:90%;padding:8px;margin:6px 0">
    </div>
    <button class="button" type="submit">Appliquer sur {esc(dev)}</button>
  </form>
</div>
"""


def carte_wifi(r: dict, reseaux: list, connus: list) -> str:
    w = r["wifi"]
    if not w["present"]:
        return """
<div class="card">
  <h2>Wi-Fi</h2>
  <p class="warn">Aucun matériel Wi-Fi détecté sur ce cab. Une carte interne ou une clé USB compatible apparaîtra ici dès qu'elle sera branchée.</p>
</div>
"""
    caps = w.get("capacites") or {}
    bandes = " · ".join(b for b, ok in (("2,4 GHz", caps.get("2ghz", True)), ("5 GHz", caps.get("5ghz", False))) if ok) or "?"
    lignes = []
    for x in reseaux:
        etat = "connecté" if x["in_use"] else ("" if x["compatible"] else "incompatible : " + x["raison"])
        bouton = "" if not x["compatible"] else f"<button class='button secondary' type='button' onclick='choisirSsid({esc(_json(x['ssid']))}, {esc(_json(x['mode']))})'>Joindre</button>"
        lignes.append(f"<tr><td>{esc(x['ssid'])}</td><td>{x['signal']} %</td><td><code>{esc(x['security'] or 'ouvert')}</code></td>"
                      f"<td class='{'good' if x['in_use'] else 'warn' if not x['compatible'] else ''}'>{esc(etat)}</td><td>{bouton}</td></tr>")
    table = ("<table><tr><th>Réseau</th><th>Signal</th><th>Chiffrement</th><th>État</th><th></th></tr>" + "".join(lignes) + "</table>") if lignes else "<p class='warn'>Aucun réseau vu au balayage.</p>"
    connus_html = "".join(
        f"<li>{esc(c['name'])} {'<span class=good>(actif)</span>' if c['active'] else ''} "
        f"<form method='post' action='/network/wifi-forget' style='display:inline'><input type='hidden' name='ssid' value='{esc(c['name'])}'>"
        f"<button class='button secondary' type='submit'>Oublier</button></form></li>" for c in connus) or "<li>aucun</li>"
    return f"""
<div class="card">
  <h2>Wi-Fi · <code>{esc(', '.join(w['devices']))}</code></h2>
  <p>Carte : {esc(bandes)} · WPA2 {'oui' if caps.get('wpa2', True) else 'non'} · radio : <code>{esc(w['radio'])}</code>.
     Le chiffrement est détecté au balayage ; un réseau que la carte ne peut pas joindre est marqué incompatible.</p>
  {table}
  <p><a class="button secondary" href="/network?rescan=1">Relancer le balayage</a></p>
  <h3>Joindre un réseau</h3>
  <form method="post" action="/network/wifi-join">
    <label>Réseau (SSID)</label>
    <input name="ssid" id="wifi_ssid" placeholder="choisis dans la liste ou saisis un SSID caché" style="width:90%;padding:8px;margin:6px 0">
    <label class="checkline"><input type="checkbox" name="hidden" value="1"> SSID caché (non diffusé)</label>
    <label>Chiffrement</label>
    <select name="security" id="wifi_security" style="width:90%;padding:8px;margin:6px 0">
      <option value="auto">Détecté automatiquement</option>
      <option value="open">Ouvert (sans mot de passe)</option>
      <option value="wpa-psk">WPA / WPA2 personnel</option>
      <option value="sae">WPA3 personnel</option>
      <option value="wpa-eap">Entreprise (802.1X, identifiant + mot de passe)</option>
    </select>
    <label>Identifiant (réseau entreprise seulement)</label>
    <input name="identity" style="width:90%;padding:8px;margin:6px 0">
    <label>Mot de passe</label>
    <input name="password" type="password" style="width:90%;padding:8px;margin:6px 0">
    <button class="button" type="submit">Joindre</button>
  </form>
  <h3>Réseaux connus</h3>
  <ul>{connus_html}</ul>
  <h3>Hotspot PinCabOS</h3>
  <form method="post" action="/network/wifi-hotspot">
    <input name="ssid" value="PinCabOS_WiFi" style="width:90%;padding:8px;margin:6px 0">
    <input name="password" type="password" placeholder="Mot de passe (8 caractères minimum)" style="width:90%;padding:8px;margin:6px 0">
    <button class="button" type="submit">Activer le hotspot</button>
  </form>
  <form method="post" action="/network/wifi-hotspot-stop" style="margin-top:8px"><button class="button secondary" type="submit">Désactiver le hotspot</button></form>
</div>
"""


def _json(s: str) -> str:
    import json
    return json.dumps(s, ensure_ascii=False)


JS = """
<script>
function basculerFixe(sel) {
  var bloc = sel.form.querySelector('.fixe');
  if (bloc) bloc.style.display = sel.value === 'static' ? 'block' : 'none';
}
function confirmerReseau(form) {
  var mode = form.querySelector('select[name="mode"]').value;
  if (mode !== 'static') return confirm("Repasser " + form.iface.value + " en DHCP ?");
  var a = form.querySelector('input[name="address"]').value;
  return confirm("Fixer " + form.iface.value + " sur " + a + " ? Si tu changes d'adresse, reconnecte-toi ensuite sur la nouvelle.");
}
function choisirSsid(ssid, mode) {
  var s = document.getElementById('wifi_ssid'); if (s) s.value = ssid;
  var m = document.getElementById('wifi_security'); if (m) m.value = 'auto';
  var p = document.querySelector('input[name="password"]'); if (p) { p.value = ''; if (mode !== 'open') p.focus(); }
}
</script>
"""


def network_page():
    rescan = request.args.get("rescan") == "1"
    r = net.resume(run=net.executer)
    reseaux, connus = [], []
    if r["wifi"]["present"]:
        caps = r["wifi"].get("capacites")
        reseaux = net.wifi_scan(run=net.executer, rescan=rescan, caps=caps)
        connus = net.wifi_connus(run=net.executer)
    cartes = "".join(carte_interface(e) for e in r["interfaces"]) or "<div class='card'><p class='warn'>Aucune interface réseau (Ethernet ou Wi-Fi) détectée.</p></div>"
    legacy = (f"<p class='warn'>Un ancien fichier <code>{esc(net.NETPLAN_LEGACY)}</code> est présent : il sera mis de côté "
              "(sauvegardé) à la prochaine application, NetworkManager prend la main.</p>") if r.get("legacy") else ""
    body = f"""
{JS}
<div class="card">
  <h1>Réseau</h1>
  <p>DHCP par défaut. Pour un adressage fixe, les valeurs reçues du DHCP sont proposées ; sans DHCP, DNS 9.9.9.9 et 1.1.1.1, passerelle à saisir.
     Ligne de commande équivalente : <code>pincabos-network</code>.</p>
  {legacy}
</div>
<div class="card">
  <h2>Nom du système</h2>
  <form method="post" action="/network/hostname">
    <label>Nom de machine</label>
    <input name="hostname" value="{esc(r['hostname'])}" placeholder="pincabos" style="width:90%;padding:8px;margin:6px 0">
    <label>Nom NetBIOS / SMB (15 caractères max, optionnel)</label>
    <input name="netbios" maxlength="15" placeholder="PINCABOS" style="width:90%;padding:8px;margin:6px 0">
    <button class="button" type="submit">Appliquer le nom</button>
  </form>
</div>
{cartes}
{carte_wifi(r, reseaux, connus)}
"""
    return _page("Réseau", body)


def network_apply_mode():
    iface = (request.form.get("iface") or "").strip()
    mode = (request.form.get("mode") or "dhcp").strip()
    if not iface or iface not in [d["device"] for d in net.peripheriques(run=net.executer)]:
        return resultat("Configuration réseau", [f"NOGO: interface inconnue : {iface or '(vide)'}"])
    journal = []
    if net.legacy_present(iface):
        journal += _sudo("legacy-takeover", iface)
    if mode == "static":
        v = net.valider_fixe(request.form.get("address", ""), request.form.get("gateway", ""), request.form.get("dns", ""))
        if v["erreurs"]:
            return resultat(f"IP fixe sur {iface} : refusé", ["NOGO: " + e for e in v["erreurs"]] + ["INFO: rien n'a été modifié"])
        journal += net.appliquer_fixe(iface, v["address"], v["gateway"], v["dns"], run=net.executer)
        return resultat(f"IP fixe sur {iface}", journal)
    journal += net.appliquer_dhcp(iface, run=net.executer)
    return resultat(f"DHCP sur {iface}", journal)


def network_wifi_join():
    journal = net.wifi_join(
        request.form.get("ssid", ""), request.form.get("password", ""), request.form.get("security", "auto") or "auto",
        request.form.get("identity", ""), request.form.get("hidden") == "1", run=net.executer)
    return resultat("Connexion Wi-Fi", journal)


def network_wifi_forget():
    return resultat("Réseau Wi-Fi oublié", net.wifi_forget(request.form.get("ssid", ""), run=net.executer))


def network_hostname():
    nom = (request.form.get("hostname") or "").strip()
    netbios = (request.form.get("netbios") or "").strip()
    if not net.RE_HOSTNAME.match(nom) or (netbios and not net.RE_NETBIOS.match(netbios)):
        return resultat("Nom du système : refusé", ["NOGO: nom de machine ou NetBIOS invalide (lettres, chiffres, tirets ; NetBIOS 15 caractères max)"])
    args = ["hostname", nom] + (["--netbios", netbios] if netbios else [])
    return resultat("Nom du système", _sudo(*args))


def network_wifi_scan_json():
    from flask import jsonify
    if not net.wifi_materiel(run=net.executer)["present"]:
        return jsonify({"present": False, "reseaux": []})
    return jsonify({"present": True, "reseaux": net.wifi_scan(run=net.executer, rescan=True)})


def register(app, page, esc_fn=None):
    global _page, _esc
    _page = page
    if esc_fn:
        _esc = esc_fn
    app.add_url_rule("/network", "pco_network_page", network_page)
    app.add_url_rule("/network/apply-mode", "pco_network_apply_mode", network_apply_mode, methods=["POST"])
    app.add_url_rule("/network/wifi-join", "pco_network_wifi_join", network_wifi_join, methods=["POST"])
    app.add_url_rule("/network/wifi-forget", "pco_network_wifi_forget", network_wifi_forget, methods=["POST"])
    app.add_url_rule("/network/hostname", "pco_network_hostname", network_hostname, methods=["POST"])
    app.add_url_rule("/api/network/wifi-scan", "pco_network_wifi_scan", network_wifi_scan_json)
