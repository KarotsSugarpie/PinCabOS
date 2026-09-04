#!/usr/bin/env python3
"""pincabos_network : le réseau du cab par NetworkManager (PINCABOS_RESEAU_V1).

Une seule API, nmcli : NetworkManager est le moteur réseau des cabs et range
lui-même ses profils dans /etc/netplan/90-NM-*.yaml. Ce module ne réécrit
aucun YAML.

Règles (Yann, 05/09/2026) :
  - DHCP par défaut ;
  - si le DHCP a répondu, ses valeurs (adresse, passerelle, DNS) sont la
    proposition pour l'adressage fixe ;
  - sans DHCP : DNS 9.9.9.9 puis 1.1.1.1, la passerelle reste à saisir, on ne
    peut pas la deviner ;
  - Wi-Fi : seulement si un matériel compatible est présent (carte interne
    ou clé USB), choix du SSID dans le balayage ou saisie d'un SSID caché,
    chiffrement détecté (ouvert, WPA/WPA2, WPA3, entreprise 802.1X) ou choisi.

Héritage : l'ancienne page écrivait /etc/netplan/99-pincabos-network.yaml.
Ce fichier est mis de côté (sauvegardé) avant toute prise en charge par
NetworkManager, sinon les deux se contredisent au redémarrage.

Utilisable en module (page web) et en CLI (pincabos-network). Toutes les
commandes passent par un exécuteur injectable : les tests rejouent des
sorties nmcli réelles sans toucher au réseau.
"""
from __future__ import annotations

import ipaddress
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

DNS_SANS_DHCP = ["9.9.9.9", "1.1.1.1"]
TYPES_UTILES = ("ethernet", "wifi")
NETPLAN_LEGACY = "etc/netplan/99-pincabos-network.yaml"
BACKUP_DIR = Path("/opt/pincabos/backups/network")
PREFIXE_CONNEXION = "PinCabOS"
SECURITES = ("auto", "open", "wpa-psk", "sae", "wpa-eap")


class Resultat:
    __slots__ = ("rc", "out", "err")

    def __init__(self, rc, out="", err=""):
        self.rc, self.out, self.err = rc, out, err


def executer(cmd, timeout=60) -> Resultat:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return Resultat(r.returncode, r.stdout, r.stderr)
    except FileNotFoundError:
        return Resultat(127, "", f"commande absente : {cmd[0]}")
    except subprocess.TimeoutExpired:
        return Resultat(124, "", f"délai dépassé : {' '.join(cmd)}")


# ---------------------------------------------------------------- nmcli -t
def champs(ligne: str) -> list:
    """Découpe une ligne `nmcli -t` : « : » sépare, « \\: » est un deux-points littéral."""
    out, cour, i = [], [], 0
    while i < len(ligne):
        c = ligne[i]
        if c == "\\" and i + 1 < len(ligne):
            cour.append(ligne[i + 1])
            i += 2
            continue
        if c == ":":
            out.append("".join(cour))
            cour = []
        else:
            cour.append(c)
        i += 1
    out.append("".join(cour))
    return out


def peripheriques(run=executer) -> list:
    r = run(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"])
    out = []
    for ligne in r.out.splitlines():
        f = champs(ligne)
        if len(f) < 4 or f[1] not in TYPES_UTILES:
            continue
        out.append({"device": f[0], "type": f[1], "state": f[2], "connection": f[3]})
    return out


def wifi_materiel(run=executer, devices=None) -> dict:
    """Présence d'un matériel Wi-Fi (carte interne ou clé USB) et état de la radio."""
    r = run(["nmcli", "-t", "-f", "WIFI-HW,WIFI", "radio"])
    f = champs(r.out.strip().splitlines()[0]) if r.out.strip() else ["missing", "enabled"]
    devs = devices if devices is not None else peripheriques(run)
    wifi_devs = [d["device"] for d in devs if d["type"] == "wifi"]
    return {"present": (f[0] != "missing") or bool(wifi_devs), "radio": f[1] if len(f) > 1 else "enabled", "devices": wifi_devs}


def details_peripherique(device: str, run=executer) -> dict:
    r = run(["nmcli", "-t", "-f", "GENERAL.CONNECTION,GENERAL.STATE,GENERAL.HWADDR,IP4.ADDRESS,IP4.GATEWAY,IP4.DNS,DHCP4.OPTION",
             "device", "show", device])
    d = {"connection": "", "state": "", "hwaddr": "", "addresses": [], "gateway": "", "dns": [], "dhcp": {}}
    for ligne in r.out.splitlines():
        f = champs(ligne)
        if len(f) < 2:
            continue
        cle, val = f[0], ":".join(f[1:])
        base = re.sub(r"\[\d+\]$", "", cle)
        if base == "GENERAL.CONNECTION":
            d["connection"] = val
        elif base == "GENERAL.STATE":
            d["state"] = val
        elif base == "GENERAL.HWADDR":
            d["hwaddr"] = val
        elif base == "IP4.ADDRESS" and val:
            d["addresses"].append(val)
        elif base == "IP4.GATEWAY":
            d["gateway"] = val
        elif base == "IP4.DNS" and val:
            d["dns"].append(val)
        elif base == "DHCP4.OPTION" and " = " in val:
            k, v = val.split(" = ", 1)
            d["dhcp"][k.strip()] = v.strip()
    return d


def ipv4_connexion(connection: str, run=executer) -> dict:
    if not connection:
        return {"method": "", "addresses": "", "gateway": "", "dns": ""}
    r = run(["nmcli", "-t", "-f", "ipv4.method,ipv4.addresses,ipv4.gateway,ipv4.dns", "connection", "show", connection])
    d = {"method": "", "addresses": "", "gateway": "", "dns": ""}
    for ligne in r.out.splitlines():
        f = champs(ligne)
        if len(f) >= 2 and f[0].startswith("ipv4."):
            d[f[0][5:]] = ":".join(f[1:])
    return d


def etat(device: str, run=executer) -> dict:
    """Ce que voit l'interface aujourd'hui : méthode, adresse, passerelle, DNS, bail DHCP."""
    det = details_peripherique(device, run)
    conn = ipv4_connexion(det["connection"], run)
    methode = conn["method"] or ("auto" if det["dhcp"] else "")
    return {
        "device": device, "connection": det["connection"], "state": det["state"], "hwaddr": det["hwaddr"],
        "method": "manual" if methode == "manual" else ("auto" if methode == "auto" else methode),
        "address": det["addresses"][0] if det["addresses"] else "", "gateway": det["gateway"], "dns": det["dns"],
        "dhcp": det["dhcp"],
        "manual": {"addresses": conn["addresses"], "gateway": conn["gateway"], "dns": conn["dns"]},
    }


def prefixe_depuis_masque(masque: str) -> int:
    try:
        return ipaddress.IPv4Network(f"0.0.0.0/{masque}").prefixlen
    except ValueError:
        return 24


def proposition(e: dict) -> dict:
    """Valeurs proposées pour l'adressage fixe, et d'où elles viennent."""
    if e.get("method") == "manual" and (e["manual"]["addresses"] or e["address"]):
        adr = (e["manual"]["addresses"] or e["address"]).split(",")[0].strip()
        gw = e["manual"]["gateway"] or e["gateway"]
        dns = [x for x in re.split(r"[,\s]+", e["manual"]["dns"] or "") if x] or list(e["dns"])
        return {"address": adr, "gateway": gw, "dns": dns or list(DNS_SANS_DHCP), "source": "manuel"}
    dhcp = e.get("dhcp") or {}
    ip = dhcp.get("ip_address", "")
    if ip:
        prefix = e["address"].split("/")[1] if e.get("address") and "/" in e["address"] else str(prefixe_depuis_masque(dhcp.get("subnet_mask", "255.255.255.0")))
        gw = (dhcp.get("routers") or e.get("gateway") or "").split()[0] if (dhcp.get("routers") or e.get("gateway")) else ""
        dns = [x for x in re.split(r"[,\s]+", dhcp.get("domain_name_servers", "")) if x] or list(e.get("dns") or [])
        return {"address": f"{ip}/{prefix}", "gateway": gw, "dns": dns or list(DNS_SANS_DHCP), "source": "dhcp"}
    adr = e.get("address", "")
    if adr and not adr.startswith("169.254."):
        return {"address": adr, "gateway": e.get("gateway", ""), "dns": list(e.get("dns") or DNS_SANS_DHCP), "source": "courant"}
    return {"address": "", "gateway": "", "dns": list(DNS_SANS_DHCP), "source": "aucune"}


def valider_fixe(address: str, gateway: str, dns) -> dict:
    """Erreurs bloquantes, avertissements, et valeurs normalisées."""
    erreurs, avert = [], []
    address = (address or "").strip()
    gateway = (gateway or "").strip()
    if isinstance(dns, str):
        dns = [x for x in re.split(r"[,\s;]+", dns) if x]
    dns = [x.strip() for x in (dns or []) if x.strip()]
    iface = None
    if not address:
        erreurs.append("adresse IP manquante (ex. 192.168.1.50/24)")
    elif "/" not in address:
        erreurs.append("préfixe manquant après l'adresse (ex. /24)")
    else:
        try:
            iface = ipaddress.IPv4Interface(address)
            if iface.ip == iface.network.network_address and iface.network.prefixlen < 31:
                erreurs.append("l'adresse est celle du réseau, pas d'une machine")
            elif iface.ip == iface.network.broadcast_address and iface.network.prefixlen < 31:
                erreurs.append("l'adresse est celle de diffusion, pas d'une machine")
        except ValueError:
            erreurs.append(f"adresse invalide : {address}")
    gw = None
    if not gateway:
        erreurs.append("passerelle manquante : sans DHCP elle ne peut pas être devinée")
    else:
        try:
            gw = ipaddress.IPv4Address(gateway)
        except ValueError:
            erreurs.append(f"passerelle invalide : {gateway}")
    if not dns:
        erreurs.append("au moins un serveur DNS")
    for s in dns:
        try:
            ipaddress.IPv4Address(s)
        except ValueError:
            erreurs.append(f"DNS invalide : {s}")
    if iface is not None and gw is not None:
        if gw == iface.ip:
            erreurs.append("la passerelle ne peut pas être l'adresse de la machine")
        elif gw not in iface.network:
            avert.append(f"la passerelle {gw} est hors du réseau {iface.network} : vérifie le préfixe")
    return {"erreurs": erreurs, "avertissements": avert, "address": address, "gateway": gateway, "dns": dns}


# ---------------------------------------------------------------- application IPv4
def connexion_du_peripherique(device: str, run=executer) -> str:
    det = details_peripherique(device, run)
    if det["connection"]:
        return det["connection"]
    nom = f"{PREFIXE_CONNEXION} {device}"
    r = run(["nmcli", "-t", "-f", "NAME", "connection", "show"])
    if nom not in [champs(l)[0] for l in r.out.splitlines()]:
        r = run(["nmcli", "connection", "add", "type", "ethernet", "ifname", device, "con-name", nom])
        if r.rc != 0:
            raise RuntimeError(f"création du profil {nom} impossible : {r.err.strip() or r.out.strip()}")
    return nom


NETPLAN_DIR = "etc/netplan"


def _fichiers_netplan_tiers(root: Path) -> list:
    """Les fichiers netplan qui ne sont pas ceux de NetworkManager (90-NM-<uuid>.yaml)."""
    d = root / NETPLAN_DIR
    if not d.is_dir():
        return []
    return sorted(f for f in d.glob("*.yaml") if not f.name.startswith("90-NM-"))


def _stanzas_du_peripherique(texte: str, device: str) -> list:
    """Sections (ethernets/wifis) qui définissent `device`, sans dépendre de PyYAML."""
    trouvees = []
    section = None
    for ligne in texte.splitlines():
        m = re.match(r"^  (ethernets|wifis|bridges|bonds|vlans):\s*$", ligne)
        if m:
            section = m.group(1)
            continue
        if re.match(r"^  \S", ligne):
            section = None
            continue
        if section and re.match(rf"^    {re.escape(device)}:\s*$", ligne):
            trouvees.append(section)
    return trouvees


def takeover_necessaire(device: str, root: Path = Path("/")) -> list:
    """Fichiers netplan tiers (installateur, ancienne page) qui définissent encore `device`.

    Tant qu'un tel fichier existe, netplan fusionne son `dhcp4: true` avec le
    profil NetworkManager : une IP fixe devient « DHCP + adresse fixe » (vu
    sur le cab de Yann, 05/09/2026). NetworkManager doit être seul à parler de
    l'interface."""
    out = []
    for f in _fichiers_netplan_tiers(root):
        try:
            texte = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _stanzas_du_peripherique(texte, device):
            out.append(f)
    return out


def _retirer_stanza(texte: str, device: str) -> str:
    """Retire les blocs `    <device>:` (et leurs lignes indentées) des sections réseau."""
    lignes = texte.splitlines()
    out, i = [], 0
    while i < len(lignes):
        l = lignes[i]
        if re.match(rf"^    {re.escape(device)}:\s*$", l):
            i += 1
            while i < len(lignes) and (lignes[i].startswith("      ") or not lignes[i].strip()):
                i += 1
            continue
        out.append(l)
        i += 1
    # une section devenue vide est retirée
    res, i = [], 0
    while i < len(out):
        m = re.match(r"^  (ethernets|wifis|bridges|bonds|vlans):\s*$", out[i])
        if m and (i + 1 >= len(out) or not out[i + 1].startswith("    ")):
            i += 1
            continue
        res.append(out[i])
        i += 1
    return "\n".join(res).rstrip("\n") + "\n"


def legacy_present(device: str, root: Path = Path("/")) -> bool:
    return bool(takeover_necessaire(device, root))


def legacy_takeover(device: str, root: Path = Path("/"), run=executer, backup_dir: Path | None = None) -> list:
    """NetworkManager prend la main sur `device` : les fichiers netplan tiers qui le
    définissent (01-pincabos-dhcp.yaml de l'installateur, 99-pincabos-network.yaml de
    l'ancienne page) sont sauvegardés puis débarrassés de sa section, et netplan
    est régénéré. Idempotent : rien à faire = « OK »."""
    fichiers = takeover_necessaire(device, root)
    if not fichiers:
        return [f"OK: NetworkManager est déjà seul à définir {device}"]
    bdir = Path(backup_dir or BACKUP_DIR) / ("netplan-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    bdir.mkdir(parents=True, exist_ok=True)
    journal = []
    for f in fichiers:
        shutil.copy2(f, bdir / f.name)
        texte = f.read_text(encoding="utf-8", errors="replace")
        reste = _retirer_stanza(texte, device)
        if re.search(r"^  (ethernets|wifis|bridges|bonds|vlans):", reste, re.M):
            f.write_text(reste, encoding="utf-8")
            journal.append(f"GO: {f.name} : section {device} retirée (sauvegarde {bdir})")
        else:
            f.unlink()
            journal.append(f"GO: {f.name} ne définissait que {device} : mis de côté dans {bdir}")
    if root == Path("/"):
        r = run(["netplan", "generate"])
        journal.append("GO: netplan generate" if r.rc == 0 else f"WARN: netplan generate : {r.err.strip()[-160:]}")
        r = run(["nmcli", "connection", "reload"])
        journal.append("GO: profils NetworkManager rechargés" if r.rc == 0 else f"WARN: nmcli connection reload : {r.err.strip()[-160:]}")
    return journal


def _appliquer(device: str, reglages: list, run=executer) -> list:
    con = connexion_du_peripherique(device, run)
    r = run(["nmcli", "connection", "modify", con] + reglages)
    if r.rc != 0:
        return [f"NOGO: nmcli connection modify {con} : {r.err.strip() or r.out.strip()}"]
    r = run(["nmcli", "connection", "up", con], timeout=90)
    if r.rc != 0:
        return [f"GO: profil {con} enregistré", f"NOGO: activation : {r.err.strip() or r.out.strip()}"]
    return [f"GO: profil {con} enregistré et activé sur {device}"]


def appliquer_dhcp(device: str, run=executer) -> list:
    return _appliquer(device, ["ipv4.method", "auto", "ipv4.addresses", "", "ipv4.gateway", "", "ipv4.dns", "", "ipv4.ignore-auto-dns", "no"], run)


def appliquer_fixe(device: str, address: str, gateway: str, dns, run=executer) -> list:
    v = valider_fixe(address, gateway, dns)
    if v["erreurs"]:
        return ["NOGO: " + e for e in v["erreurs"]]
    journal = ["WARN: " + a for a in v["avertissements"]]
    return journal + _appliquer(device, ["ipv4.method", "manual", "ipv4.addresses", v["address"], "ipv4.gateway", v["gateway"],
                                         "ipv4.dns", " ".join(v["dns"]), "ipv4.ignore-auto-dns", "yes"], run)


# ---------------------------------------------------------------- Wi-Fi
def securite_mode(security: str) -> str:
    s = (security or "").upper()
    if not s.strip() or s.strip() == "--":
        return "open"
    if "802.1X" in s:
        return "wpa-eap"
    if "WEP" in s and "WPA" not in s:
        return "wep"
    if "WPA3" in s and "WPA2" not in s and "WPA1" not in s:
        return "sae"
    return "wpa-psk"


def wifi_capacites(device: str, run=executer) -> dict:
    """Ce que la carte sait faire (nmcli WIFI-PROPERTIES) : bandes et chiffrements."""
    r = run(["nmcli", "-t", "-f", "WIFI-PROPERTIES", "device", "show", device])
    props = {}
    for ligne in r.out.splitlines():
        f = champs(ligne)
        if len(f) >= 2 and f[0].startswith("WIFI-PROPERTIES."):
            props[f[0][len("WIFI-PROPERTIES."):]] = f[1].strip().lower() in ("yes", "oui", "true")
    return {
        "2ghz": props.get("2GHZ", True), "5ghz": props.get("5GHZ", False),
        "wpa": props.get("WPA", True), "wpa2": props.get("CCMP", True) or props.get("RSN", True),
        "wep": props.get("WEP40", False) or props.get("WEP104", False),
        "brut": props,
    }


def compatible(reseau: dict, caps: dict | None) -> tuple:
    """(compatible, raison) d'un réseau vu au balayage face aux capacités de la carte."""
    if reseau.get("mode") == "wep":
        return False, "WEP obsolète, non pris en charge"
    if caps and reseau.get("freq", 0) >= 4900 and not caps.get("5ghz", False):
        return False, "réseau 5 GHz, carte 2,4 GHz seulement"
    if caps and reseau.get("mode") in ("wpa-psk", "sae") and not caps.get("wpa2", True):
        return False, "WPA2/WPA3 non pris en charge par la carte"
    return True, ""


def wifi_scan(run=executer, rescan: bool = True, caps: dict | None = None) -> list:
    r = run(["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY,CHAN,BSSID,IN-USE,FREQ", "device", "wifi", "list", "--rescan", "yes" if rescan else "no"], timeout=45)
    meilleurs = {}
    for ligne in r.out.splitlines():
        f = champs(ligne)
        if len(f) < 3 or not f[0]:
            continue
        try:
            signal = int(f[1] or 0)
        except ValueError:
            signal = 0
        m = re.match(r"(\d+)", f[6]) if len(f) > 6 else None
        res = {"ssid": f[0], "signal": signal, "security": f[2], "mode": securite_mode(f[2]),
               "chan": f[3] if len(f) > 3 else "", "bssid": f[4] if len(f) > 4 else "",
               "in_use": (len(f) > 5 and f[5].strip() == "*"), "freq": int(m.group(1)) if m else 0}
        res["compatible"], res["raison"] = compatible(res, caps)
        if res["ssid"] not in meilleurs or signal > meilleurs[res["ssid"]]["signal"] or res["in_use"]:
            meilleurs[res["ssid"]] = res
    return sorted(meilleurs.values(), key=lambda x: (-x["in_use"], -x["compatible"], -x["signal"], x["ssid"].lower()))


def wifi_connus(run=executer) -> list:
    r = run(["nmcli", "-t", "-f", "NAME,TYPE,DEVICE,AUTOCONNECT", "connection", "show"])
    out = []
    for ligne in r.out.splitlines():
        f = champs(ligne)
        if len(f) >= 2 and f[1] == "802-11-wireless":
            out.append({"name": f[0], "device": f[2] if len(f) > 2 else "", "active": bool(len(f) > 2 and f[2])})
    return out


def wifi_arguments(ssid: str, password: str, securite: str, identity: str = "", hidden: bool = False) -> list:
    """Arguments nmcli du profil Wi-Fi selon le chiffrement retenu."""
    args = ["ssid", ssid]
    if hidden:
        args += ["wifi.hidden", "yes"]
    if securite == "open":
        return args
    if securite in ("wpa-psk", "sae"):
        if not 8 <= len(password) <= 63:
            raise ValueError("mot de passe Wi-Fi : entre 8 et 63 caractères")
        return args + ["wifi-sec.key-mgmt", securite, "wifi-sec.psk", password]
    if securite == "wpa-eap":
        if not identity or not password:
            raise ValueError("réseau entreprise (802.1X) : identifiant et mot de passe requis")
        return args + ["wifi-sec.key-mgmt", "wpa-eap", "802-1x.eap", "peap", "802-1x.phase2-auth", "mschapv2",
                       "802-1x.identity", identity, "802-1x.password", password]
    if securite == "wep":
        raise ValueError("WEP n'est pas pris en charge (obsolète et non sûr)")
    raise ValueError(f"chiffrement inconnu : {securite}")


def wifi_join(ssid: str, password: str = "", securite: str = "auto", identity: str = "", hidden: bool = False,
              run=executer, scan=None) -> list:
    ssid = (ssid or "").strip()
    if not ssid:
        return ["NOGO: SSID manquant"]
    mat = wifi_materiel(run)
    if not mat["present"] or not mat["devices"]:
        return ["NOGO: aucun matériel Wi-Fi détecté (carte interne ou clé USB compatible)"]
    if mat["radio"] != "enabled":
        run(["nmcli", "radio", "wifi", "on"])
    device = mat["devices"][0]
    if securite == "auto":
        reseaux = scan if scan is not None else wifi_scan(run, rescan=not hidden, caps=wifi_capacites(device, run))
        trouve = next((r for r in reseaux if r["ssid"] == ssid), None)
        if trouve and not trouve.get("compatible", True):
            return [f"NOGO: réseau « {ssid} » incompatible avec la carte : {trouve.get('raison', '')}"]
        if trouve:
            securite = trouve["mode"]
        elif hidden:
            securite = "wpa-psk" if password else "open"
        else:
            return [f"NOGO: réseau « {ssid} » non vu au balayage ; coche « SSID caché » ou relance le balayage"]
    try:
        args = wifi_arguments(ssid, password, securite, identity, hidden)
    except ValueError as exc:
        return [f"NOGO: {exc}"]
    for c in wifi_connus(run):
        if c["name"] == ssid:
            run(["nmcli", "connection", "delete", ssid])
    r = run(["nmcli", "connection", "add", "type", "wifi", "ifname", device, "con-name", ssid] + args)
    if r.rc != 0:
        return [f"NOGO: création du profil : {r.err.strip() or r.out.strip()}"]
    r = run(["nmcli", "connection", "up", ssid], timeout=90)
    if r.rc != 0:
        run(["nmcli", "connection", "delete", ssid])
        msg = (r.err.strip() or r.out.strip())[-200:]
        if "Secrets were required" in msg or "802-11-wireless-security" in msg or "password" in msg.lower():
            return [f"NOGO: connexion refusée par « {ssid} » : mot de passe ou chiffrement incorrect"]
        return [f"NOGO: connexion à « {ssid} » impossible : {msg}"]
    return [f"GO: connecté à « {ssid} » sur {device} ({securite}) ; reconnexion automatique au démarrage"]


def wifi_forget(ssid: str, run=executer) -> list:
    if ssid not in [c["name"] for c in wifi_connus(run)]:
        return [f"OK: « {ssid} » n'est pas un réseau connu"]
    r = run(["nmcli", "connection", "delete", ssid])
    return [f"GO: réseau « {ssid} » oublié"] if r.rc == 0 else [f"NOGO: {r.err.strip() or r.out.strip()}"]


# ---------------------------------------------------------------- nom de machine
RE_HOSTNAME = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
RE_NETBIOS = re.compile(r"^[A-Za-z0-9-]{1,15}$")


def hostname_set(nom: str, netbios: str = "", root: Path = Path("/"), run=executer) -> list:
    nom = (nom or "").strip()
    netbios = (netbios or "").strip()
    if not RE_HOSTNAME.match(nom):
        return ["NOGO: nom de machine invalide (lettres, chiffres, tirets, 63 caractères maximum)"]
    if netbios and not RE_NETBIOS.match(netbios):
        return ["NOGO: nom NetBIOS invalide (15 caractères maximum, lettres, chiffres, tirets)"]
    journal = []
    if root == Path("/"):
        r = run(["hostnamectl", "set-hostname", nom])
        journal.append(f"GO: nom de machine : {nom}" if r.rc == 0 else f"NOGO: hostnamectl : {r.err.strip() or r.out.strip()}")
        if r.rc != 0:
            return journal
    hosts = root / "etc/hosts"
    if hosts.exists():
        lignes = hosts.read_text(encoding="utf-8", errors="replace").splitlines()
        nouvelles, vu = [], False
        for l in lignes:
            if l.startswith("127.0.1.1"):
                nouvelles.append(f"127.0.1.1\t{nom}")
                vu = True
            else:
                nouvelles.append(l)
        if not vu:
            nouvelles.insert(1 if nouvelles else 0, f"127.0.1.1\t{nom}")
        hosts.write_text("\n".join(nouvelles) + "\n", encoding="utf-8")
        journal.append("GO: /etc/hosts à jour")
    smb = root / "etc/samba/smb.conf"
    if netbios and smb.exists():
        texte = smb.read_text(encoding="utf-8", errors="replace")
        if re.search(r"(?mi)^\s*netbios name\s*=", texte):
            texte = re.sub(r"(?mi)^(\s*)netbios name\s*=.*$", rf"\1netbios name = {netbios}", texte)
        else:
            texte = re.sub(r"(?m)^\[global\]\s*$", f"[global]\n   netbios name = {netbios}", texte, count=1)
        smb.write_text(texte, encoding="utf-8")
        journal.append(f"GO: nom NetBIOS : {netbios}")
        if root == Path("/"):
            run(["systemctl", "reload-or-restart", "smbd"])
    return journal


# ---------------------------------------------------------------- vue d'ensemble
def resume(run=executer) -> dict:
    devs = peripheriques(run)
    wifi = wifi_materiel(run, devs)
    interfaces = []
    for d in devs:
        e = etat(d["device"], run)
        e["type"] = d["type"]
        e["proposition"] = proposition(e)
        interfaces.append(e)
    if wifi["devices"]:
        wifi["capacites"] = wifi_capacites(wifi["devices"][0], run)
    return {"interfaces": interfaces, "wifi": wifi, "hostname": _hostname(run),
            "legacy": legacy_present(devs[0]["device"]) if devs else False}


def _hostname(run=executer) -> str:
    r = run(["hostnamectl", "--static"])
    return r.out.strip() if r.rc == 0 else ""


USAGE = """usage : pincabos-network status [--json]
        pincabos-network proposal <interface> [--json]
        pincabos-network dhcp <interface>
        pincabos-network static <interface> <adresse/prefixe> <passerelle> <dns1[,dns2]>
        pincabos-network wifi-scan [--json]
        pincabos-network wifi-join <ssid> [--password P] [--security auto|open|wpa-psk|sae|wpa-eap] [--identity U] [--hidden]
        pincabos-network wifi-forget <ssid>
        pincabos-network hostname <nom> [--netbios NOM]
        pincabos-network netplan-takeover <interface> [--root DIR]   (root : NetworkManager seul maître de l'interface)
"""


def _opt(args, nom, defaut=""):
    return args[args.index(nom) + 1] if nom in args and args.index(nom) + 1 < len(args) else defaut


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(USAGE)
        return 0
    cmd, args = argv[0], argv[1:]
    as_json = "--json" in args
    pos = [a for a in args if not a.startswith("--")]
    if cmd == "status":
        r = resume()
        if as_json:
            print(json.dumps(r, indent=2, ensure_ascii=False))
            return 0
        print(f"machine : {r['hostname']}   wifi : {'présent' if r['wifi']['present'] else 'aucun matériel'} ({', '.join(r['wifi']['devices']) or '-'})")
        for e in r["interfaces"]:
            p = e["proposition"]
            print(f"{e['device']:<10} {e['type']:<9} {e['state']:<22} {e['method'] or '-':<7} {e['address'] or '-':<20} gw {e['gateway'] or '-':<15} dns {','.join(e['dns']) or '-'}")
            print(f"{'':<10} proposition fixe ({p['source']}) : {p['address'] or '?'} gw {p['gateway'] or '?'} dns {','.join(p['dns'])}")
        if r["legacy"]:
            print(f"WARN: un fichier netplan tiers définit encore une interface : NetworkManager prendra la main à la prochaine application")
        return 0
    if cmd == "proposal" and pos:
        p = proposition(etat(pos[0]))
        print(json.dumps(p, ensure_ascii=False) if as_json else f"{p['address'] or '?'} gw {p['gateway'] or '?'} dns {','.join(p['dns'])} ({p['source']})")
        return 0
    if cmd in ("dhcp", "static") and pos:
        journal = []
        if legacy_present(pos[0]):
            import os
            if os.geteuid() != 0:
                print(f"NOGO: {', '.join(f.name for f in takeover_necessaire(pos[0]))} définit encore {pos[0]} ; lance d'abord : sudo pincabos-network netplan-takeover {pos[0]}")
                return 1
            journal += legacy_takeover(pos[0])
        journal += appliquer_dhcp(pos[0]) if cmd == "dhcp" else appliquer_fixe(pos[0], *(pos[1:4] + [""] * (4 - len(pos))))
        print("\n".join(journal))
        return 1 if any(l.startswith("NOGO") for l in journal) else 0
    if cmd == "wifi-scan":
        res = wifi_scan(rescan=True)
        print(json.dumps(res, ensure_ascii=False, indent=2) if as_json else "\n".join(f"{r['signal']:>3}%  {r['mode']:<8} {r['ssid']}{'  (connecté)' if r['in_use'] else ''}" for r in res) or "aucun réseau vu")
        return 0
    if cmd == "wifi-join" and pos:
        journal = wifi_join(pos[0], _opt(args, "--password"), _opt(args, "--security", "auto"), _opt(args, "--identity"), "--hidden" in args)
        print("\n".join(journal))
        return 1 if any(l.startswith("NOGO") for l in journal) else 0
    if cmd == "wifi-forget" and pos:
        print("\n".join(wifi_forget(pos[0])))
        return 0
    if cmd == "hostname" and pos:
        journal = hostname_set(pos[0], _opt(args, "--netbios"))
        print("\n".join(journal))
        return 1 if any(l.startswith("NOGO") for l in journal) else 0
    if cmd in ("netplan-takeover", "legacy-takeover") and pos:
        # --root DIR : arborescence d'une cible d'installation (pas de netplan generate)
        racine = Path(_opt(args, "--root", "/"))
        print("\n".join(legacy_takeover(pos[0], root=racine)))
        return 0
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
