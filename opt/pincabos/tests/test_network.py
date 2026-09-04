"""pincabos_network : le réseau du cab par NetworkManager (PINCABOS_RESEAU_V1).

Les sorties nmcli sont celles du cab de Yann (eno1, DHCP) complétées d'un
matériel Wi-Fi simulé ; un faux exécuteur enregistre les commandes.
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from _charge import charger

m = charger("opt/pincabos/tools/pincabos_network.py", "pco_network")

STATUS_ETH = "eno1:ethernet:connected:netplan-eno1\nlo:loopback:connected (externally):lo\n"
STATUS_WIFI = STATUS_ETH + "wlp3s0:wifi:disconnected:\n"
SHOW_ENO1 = """GENERAL.CONNECTION:netplan-eno1
GENERAL.STATE:100 (connected)
GENERAL.HWADDR:04\\:D4\\:C4\\:A8\\:65\\:ED
IP4.ADDRESS[1]:172.18.40.80/24
IP4.GATEWAY:172.18.40.254
IP4.DNS[1]:172.18.41.254
DHCP4.OPTION[2]:dhcp_lease_time = 28800
DHCP4.OPTION[3]:dhcp_server_identifier = 172.18.40.254
DHCP4.OPTION[5]:domain_name_servers = 172.18.41.254
DHCP4.OPTION[7]:ip_address = 172.18.40.80
DHCP4.OPTION[27]:routers = 172.18.40.254
DHCP4.OPTION[28]:subnet_mask = 255.255.255.0
"""
CONN_AUTO = "ipv4.method:auto\nipv4.addresses:\nipv4.gateway:\nipv4.dns:\n"
CONN_MANUAL = "ipv4.method:manual\nipv4.addresses:192.168.1.50/24\nipv4.gateway:192.168.1.1\nipv4.dns:9.9.9.9,1.1.1.1\n"
SHOW_SANS_DHCP = "GENERAL.CONNECTION:netplan-eno1\nGENERAL.STATE:100 (connected)\nIP4.ADDRESS[1]:169.254.12.7/16\nIP4.GATEWAY:\n"
WIFI_LIST = """Maison:82:WPA2:6:AA\\:BB\\:CC\\:DD\\:EE\\:01:*:2437 MHz
Maison:61:WPA2:36:AA\\:BB\\:CC\\:DD\\:EE\\:02::5180 MHz
Voisin:40:WPA1 WPA2:1:AA\\:BB\\:CC\\:DD\\:EE\\:03::2412 MHz
Cafe:70::11:AA\\:BB\\:CC\\:DD\\:EE\\:04::2462 MHz
Bureau:55:WPA2 802.1X:44:AA\\:BB\\:CC\\:DD\\:EE\\:05::5220 MHz
Neuf:66:WPA3:48:AA\\:BB\\:CC\\:DD\\:EE\\:06::5240 MHz
Vieux:30:WEP:3:AA\\:BB\\:CC\\:DD\\:EE\\:07::2422 MHz
:20:WPA2:1:AA\\:BB\\:CC\\:DD\\:EE\\:08::2412 MHz
"""
PROPS_24 = "WIFI-PROPERTIES.WEP40:yes\nWIFI-PROPERTIES.WEP104:yes\nWIFI-PROPERTIES.TKIP:yes\nWIFI-PROPERTIES.CCMP:yes\nWIFI-PROPERTIES.AP:yes\nWIFI-PROPERTIES.ADHOC:yes\nWIFI-PROPERTIES.2GHZ:yes\nWIFI-PROPERTIES.5GHZ:no\n"


class Faux:
    """Exécuteur : répond depuis une table, enregistre tout."""

    def __init__(self, reponses=None, wifi=False, manual=False, sans_dhcp=False):
        self.commandes = []
        self.reponses = reponses or {}
        self.wifi, self.manual, self.sans_dhcp = wifi, manual, sans_dhcp
        self.connexions = ["netplan-eno1", "lo", "PinCabOS DHCP"] + (["Maison"] if wifi else [])

    def __call__(self, cmd, timeout=60):
        self.commandes.append(list(cmd))
        c = " ".join(cmd)
        for cle, rep in self.reponses.items():
            if c.startswith(cle):
                return m.Resultat(*rep) if isinstance(rep, tuple) else m.Resultat(0, rep)
        if c.startswith("nmcli -t -f DEVICE,TYPE,STATE,CONNECTION device status"):
            return m.Resultat(0, STATUS_WIFI if self.wifi else STATUS_ETH)
        if c.startswith("nmcli -t -f WIFI-HW,WIFI radio"):
            return m.Resultat(0, ("enabled:enabled\n" if self.wifi else "missing:enabled\n"))
        if c.startswith("nmcli -t -f GENERAL.CONNECTION,") and "device show eno1" in c:
            return m.Resultat(0, SHOW_SANS_DHCP if self.sans_dhcp else SHOW_ENO1)
        if c.startswith("nmcli -t -f ipv4.method") and "connection show netplan-eno1" in c:
            return m.Resultat(0, CONN_MANUAL if self.manual else CONN_AUTO)
        if c.startswith("nmcli -t -f WIFI-PROPERTIES device show"):
            return m.Resultat(0, PROPS_24)
        if c.startswith("nmcli -t -f SSID,SIGNAL,SECURITY"):
            return m.Resultat(0, WIFI_LIST)
        if c.startswith("nmcli -t -f NAME,TYPE,DEVICE,AUTOCONNECT connection show"):
            lignes = [f"{n}:{'802-11-wireless' if n == 'Maison' else '802-3-ethernet'}:{'wlp3s0' if n == 'Maison' else ''}:yes" for n in self.connexions]
            return m.Resultat(0, "\n".join(lignes) + "\n")
        if c.startswith("nmcli -t -f NAME connection show"):
            return m.Resultat(0, "\n".join(self.connexions) + "\n")
        if c.startswith("hostnamectl --static"):
            return m.Resultat(0, "PinCabOs\n")
        return m.Resultat(0, "")


class Lecture(unittest.TestCase):
    def test_champs_avec_deux_points_echappes(self):
        self.assertEqual(m.champs("GENERAL.HWADDR:04\\:D4\\:C4"), ["GENERAL.HWADDR", "04:D4:C4"])
        self.assertEqual(m.champs("a:b::c"), ["a", "b", "", "c"])

    def test_peripheriques_et_wifi_absent(self):
        f = Faux()
        devs = m.peripheriques(f)
        self.assertEqual(devs, [{"device": "eno1", "type": "ethernet", "state": "connected", "connection": "netplan-eno1"}])
        w = m.wifi_materiel(f, devs)
        self.assertFalse(w["present"])
        self.assertEqual(w["devices"], [])

    def test_wifi_present(self):
        f = Faux(wifi=True)
        w = m.wifi_materiel(f)
        self.assertTrue(w["present"])
        self.assertEqual(w["devices"], ["wlp3s0"])

    def test_etat_dhcp(self):
        e = m.etat("eno1", Faux())
        self.assertEqual(e["method"], "auto")
        self.assertEqual(e["address"], "172.18.40.80/24")
        self.assertEqual(e["gateway"], "172.18.40.254")
        self.assertEqual(e["dns"], ["172.18.41.254"])
        self.assertEqual(e["dhcp"]["routers"], "172.18.40.254")
        self.assertEqual(e["hwaddr"], "04:D4:C4:A8:65:ED")


class Proposition(unittest.TestCase):
    def test_depuis_le_bail_dhcp(self):
        p = m.proposition(m.etat("eno1", Faux()))
        self.assertEqual(p, {"address": "172.18.40.80/24", "gateway": "172.18.40.254", "dns": ["172.18.41.254"], "source": "dhcp"})

    def test_sans_dhcp_dns_par_defaut_passerelle_vide(self):
        p = m.proposition(m.etat("eno1", Faux(sans_dhcp=True)))
        self.assertEqual(p, {"address": "", "gateway": "", "dns": ["9.9.9.9", "1.1.1.1"], "source": "aucune"})

    def test_deja_en_fixe(self):
        p = m.proposition(m.etat("eno1", Faux(manual=True)))
        self.assertEqual(p["source"], "manuel")
        self.assertEqual(p["address"], "192.168.1.50/24")
        self.assertEqual(p["dns"], ["9.9.9.9", "1.1.1.1"])

    def test_masque_vers_prefixe(self):
        self.assertEqual(m.prefixe_depuis_masque("255.255.255.0"), 24)
        self.assertEqual(m.prefixe_depuis_masque("255.255.0.0"), 16)
        self.assertEqual(m.prefixe_depuis_masque("n'importe"), 24)


class Validation(unittest.TestCase):
    def test_bonnes_valeurs(self):
        v = m.valider_fixe("192.168.1.50/24", "192.168.1.1", "9.9.9.9, 1.1.1.1")
        self.assertEqual(v["erreurs"], [])
        self.assertEqual(v["avertissements"], [])
        self.assertEqual(v["dns"], ["9.9.9.9", "1.1.1.1"])

    def test_erreurs(self):
        v = m.valider_fixe("192.168.1.50", "", "")
        self.assertIn("préfixe manquant après l'adresse (ex. /24)", v["erreurs"])
        self.assertTrue(any("passerelle manquante" in e for e in v["erreurs"]))
        self.assertIn("au moins un serveur DNS", v["erreurs"])
        self.assertTrue(m.valider_fixe("192.168.1.0/24", "192.168.1.1", "1.1.1.1")["erreurs"])
        self.assertTrue(m.valider_fixe("192.168.1.255/24", "192.168.1.1", "1.1.1.1")["erreurs"])
        self.assertTrue(m.valider_fixe("192.168.1.50/24", "192.168.1.50", "1.1.1.1")["erreurs"])
        self.assertTrue(m.valider_fixe("abc/24", "192.168.1.1", "x")["erreurs"])

    def test_passerelle_hors_reseau_avertit_sans_bloquer(self):
        v = m.valider_fixe("192.168.1.50/24", "10.0.0.1", "1.1.1.1")
        self.assertEqual(v["erreurs"], [])
        self.assertTrue(v["avertissements"])


class ApplicationIPv4(unittest.TestCase):
    def test_fixe(self):
        f = Faux()
        j = m.appliquer_fixe("eno1", "172.18.40.80/24", "172.18.40.254", ["172.18.41.254"], f)
        self.assertTrue(j[-1].startswith("GO:"), j)
        mod = next(c for c in f.commandes if c[:3] == ["nmcli", "connection", "modify"])
        self.assertEqual(mod[3], "netplan-eno1")
        self.assertEqual(mod[4:], ["ipv4.method", "manual", "ipv4.addresses", "172.18.40.80/24", "ipv4.gateway", "172.18.40.254",
                                   "ipv4.dns", "172.18.41.254", "ipv4.ignore-auto-dns", "yes"])
        self.assertIn(["nmcli", "connection", "up", "netplan-eno1"], f.commandes)

    def test_dhcp(self):
        f = Faux()
        j = m.appliquer_dhcp("eno1", f)
        self.assertTrue(j[-1].startswith("GO:"), j)
        mod = next(c for c in f.commandes if c[:3] == ["nmcli", "connection", "modify"])
        self.assertEqual(mod[4:6], ["ipv4.method", "auto"])
        self.assertIn("ipv4.ignore-auto-dns", mod)

    def test_valeurs_invalides_n_ecrivent_rien(self):
        f = Faux()
        j = m.appliquer_fixe("eno1", "192.168.1.0/24", "", "", f)
        self.assertTrue(all(l.startswith("NOGO") for l in j))
        self.assertFalse([c for c in f.commandes if c[:3] == ["nmcli", "connection", "modify"]])

    def test_profil_cree_si_absent(self):
        f = Faux(reponses={"nmcli -t -f GENERAL.CONNECTION,": "GENERAL.CONNECTION:\nGENERAL.STATE:30 (disconnected)\n"})
        m.appliquer_dhcp("eno1", f)
        self.assertIn(["nmcli", "connection", "add", "type", "ethernet", "ifname", "eno1", "con-name", "PinCabOS eno1"], f.commandes)

    def test_activation_ratee(self):
        f = Faux(reponses={"nmcli connection up": (4, "", "Error: Connection activation failed")})
        j = m.appliquer_dhcp("eno1", f)
        self.assertTrue(any(l.startswith("NOGO") for l in j))


class Heritage(unittest.TestCase):
    """Les fichiers netplan tiers (installateur, ancienne page) ne doivent plus parler
    de l'interface : netplan fusionnait leur dhcp4: true avec le profil NM."""

    BASE = "network:\n  version: 2\n  renderer: NetworkManager\n  ethernets:\n    eno1:\n      dhcp4: true\n      dhcp6: true\n      optional: true\n"
    DEUX = BASE + "    enp2s0:\n      dhcp4: true\n"
    NM = "network:\n  version: 2\n  ethernets:\n    eno1:\n      renderer: NetworkManager\n      match: {}\n      addresses:\n      - \"172.18.40.80/24\"\n      networkmanager:\n        uuid: \"10838d80\"\n        name: \"netplan-eno1\"\n"

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "etc/netplan").mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_detection(self):
        (self.root / "etc/netplan/01-pincabos-dhcp.yaml").write_text(self.BASE, encoding="utf-8")
        (self.root / "etc/netplan/90-NM-10838d80.yaml").write_text(self.NM, encoding="utf-8")
        self.assertEqual([f.name for f in m.takeover_necessaire("eno1", self.root)], ["01-pincabos-dhcp.yaml"])
        self.assertEqual(m.takeover_necessaire("wlp3s0", self.root), [])
        self.assertTrue(m.legacy_present("eno1", self.root))

    def test_prise_en_main_fichier_dedie(self):
        p = self.root / "etc/netplan/01-pincabos-dhcp.yaml"
        p.write_text(self.BASE, encoding="utf-8")
        (self.root / "etc/netplan/90-NM-10838d80.yaml").write_text(self.NM, encoding="utf-8")
        f = Faux()
        j = m.legacy_takeover("eno1", self.root, f, backup_dir=self.root / "backups")
        self.assertFalse(p.exists(), "ne definissait que eno1 : mis de cote")
        self.assertEqual(len(list((self.root / "backups").rglob("01-pincabos-dhcp.yaml"))), 1)
        self.assertEqual((self.root / "etc/netplan/90-NM-10838d80.yaml").read_text(encoding="utf-8"), self.NM, "le fichier de NM n'est pas touche")
        self.assertTrue(j[0].startswith("GO:"))
        self.assertEqual(f.commandes, [], "racine de test : ni netplan generate ni reload")
        self.assertEqual(m.legacy_takeover("eno1", self.root, f)[0][:3], "OK:")

    def test_prise_en_main_garde_les_autres_interfaces(self):
        p = self.root / "etc/netplan/01-pincabos-dhcp.yaml"
        p.write_text(self.DEUX, encoding="utf-8")
        m.legacy_takeover("eno1", self.root, Faux(), backup_dir=self.root / "backups")
        reste = p.read_text(encoding="utf-8")
        self.assertNotIn("eno1", reste)
        self.assertIn("    enp2s0:\n      dhcp4: true\n", reste)
        self.assertIn("renderer: NetworkManager", reste)
        self.assertEqual(m._stanzas_du_peripherique(reste, "enp2s0"), ["ethernets"])

    def test_ancienne_page(self):
        p = self.root / m.NETPLAN_LEGACY
        p.write_text("network:\n  version: 2\n  renderer: NetworkManager\n  ethernets:\n    eno1:\n      dhcp4: false\n      addresses:\n        - 192.168.254.237/24\n", encoding="utf-8")
        self.assertTrue(m.legacy_present("eno1", self.root))
        j = m.legacy_takeover("eno1", self.root, Faux(), backup_dir=self.root / "backups")
        self.assertFalse(p.exists())
        self.assertTrue(j[0].startswith("GO:"))

    def test_absent(self):
        self.assertFalse(m.legacy_present("eno1", self.root))
        self.assertEqual(m.legacy_takeover("eno1", self.root, Faux())[0][:3], "OK:")


class WiFi(unittest.TestCase):
    def test_modes_de_securite(self):
        self.assertEqual(m.securite_mode(""), "open")
        self.assertEqual(m.securite_mode("--"), "open")
        self.assertEqual(m.securite_mode("WPA2"), "wpa-psk")
        self.assertEqual(m.securite_mode("WPA1 WPA2"), "wpa-psk")
        self.assertEqual(m.securite_mode("WPA2 WPA3"), "wpa-psk")
        self.assertEqual(m.securite_mode("WPA3"), "sae")
        self.assertEqual(m.securite_mode("WPA2 802.1X"), "wpa-eap")
        self.assertEqual(m.securite_mode("WEP"), "wep")

    def test_balayage_dedoublonne_et_compatibilite(self):
        f = Faux(wifi=True)
        caps = m.wifi_capacites("wlp3s0", f)
        self.assertFalse(caps["5ghz"])
        res = m.wifi_scan(f, caps=caps)
        noms = [r["ssid"] for r in res]
        self.assertEqual(noms[0], "Maison", "le réseau en cours d'abord")
        self.assertNotIn("", noms, "SSID caché ignoré")
        maison = next(r for r in res if r["ssid"] == "Maison")
        self.assertEqual(maison["signal"], 82, "le meilleur point d'accès du SSID")
        self.assertTrue(maison["in_use"])
        self.assertEqual(maison["bssid"], "AA:BB:CC:DD:EE:01")
        self.assertEqual(next(r for r in res if r["ssid"] == "Cafe")["mode"], "open")
        neuf = next(r for r in res if r["ssid"] == "Neuf")
        self.assertFalse(neuf["compatible"])
        self.assertIn("5 GHz", neuf["raison"])
        vieux = next(r for r in res if r["ssid"] == "Vieux")
        self.assertFalse(vieux["compatible"])
        self.assertTrue(all(r["compatible"] for r in res if r["ssid"] in ("Maison", "Voisin", "Cafe")))

    def test_arguments_nmcli(self):
        self.assertEqual(m.wifi_arguments("Maison", "motdepasse", "wpa-psk"), ["ssid", "Maison", "wifi-sec.key-mgmt", "wpa-psk", "wifi-sec.psk", "motdepasse"])
        self.assertEqual(m.wifi_arguments("Cafe", "", "open", hidden=True), ["ssid", "Cafe", "wifi.hidden", "yes"])
        self.assertIn("sae", m.wifi_arguments("Neuf", "motdepasse", "sae"))
        eap = m.wifi_arguments("Bureau", "secret", "wpa-eap", identity="yann")
        self.assertIn("802-1x.identity", eap)
        self.assertIn("mschapv2", eap)
        with self.assertRaises(ValueError):
            m.wifi_arguments("Maison", "court", "wpa-psk")
        with self.assertRaises(ValueError):
            m.wifi_arguments("Bureau", "secret", "wpa-eap")
        with self.assertRaises(ValueError):
            m.wifi_arguments("Vieux", "x", "wep")

    def test_connexion(self):
        f = Faux(wifi=True)
        j = m.wifi_join("Voisin", "motdepasse", run=f)
        self.assertTrue(j[0].startswith("GO:"), j)
        add = next(c for c in f.commandes if c[:3] == ["nmcli", "connection", "add"])
        self.assertEqual(add[3:9], ["type", "wifi", "ifname", "wlp3s0", "con-name", "Voisin"])
        self.assertIn("wpa-psk", add)
        self.assertIn(["nmcli", "connection", "up", "Voisin"], f.commandes)
        self.assertNotIn(["nmcli", "connection", "delete", "Voisin"], f.commandes)

    def test_reconnexion_remplace_le_profil(self):
        f = Faux(wifi=True)
        m.wifi_join("Maison", "motdepasse", run=f)
        self.assertIn(["nmcli", "connection", "delete", "Maison"], f.commandes)

    def test_refus(self):
        f = Faux(wifi=True, reponses={"nmcli connection up Voisin": (4, "", "Error: Connection activation failed: Secrets were required, but not provided")})
        j = m.wifi_join("Voisin", "mauvais-mdp", run=f)
        self.assertIn("mot de passe ou chiffrement incorrect", j[0])
        self.assertIn(["nmcli", "connection", "delete", "Voisin"], f.commandes, "le profil raté ne reste pas")

    def test_sans_materiel(self):
        j = m.wifi_join("Maison", "motdepasse", run=Faux())
        self.assertIn("aucun matériel Wi-Fi", j[0])

    def test_incompatible_et_cache(self):
        f = Faux(wifi=True)
        self.assertIn("incompatible", m.wifi_join("Neuf", "motdepasse", run=f)[0])
        self.assertIn("non vu au balayage", m.wifi_join("Inconnu", "motdepasse", run=f)[0])
        j = m.wifi_join("Inconnu", "motdepasse", hidden=True, run=f)
        self.assertTrue(j[0].startswith("GO:"), j)
        add = next(c for c in f.commandes if c[:3] == ["nmcli", "connection", "add"] and "Inconnu" in c)
        self.assertIn("wifi.hidden", add)

    def test_oubli(self):
        f = Faux(wifi=True)
        self.assertTrue(m.wifi_forget("Maison", f)[0].startswith("GO:"))
        self.assertTrue(m.wifi_forget("Jamais", f)[0].startswith("OK:"))


class NomDeMachine(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "etc/samba").mkdir(parents=True)
        (self.root / "etc/hosts").write_text("127.0.0.1\tlocalhost\n127.0.1.1\tPinCabOs\n", encoding="utf-8")
        (self.root / "etc/samba/smb.conf").write_text("[global]\n   workgroup = WORKGROUP\n\n[tables]\n   path = /home/pinball/Tables\n", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_validation(self):
        self.assertTrue(m.hostname_set("pas d espace", root=self.root)[0].startswith("NOGO"))
        self.assertTrue(m.hostname_set("-debut", root=self.root)[0].startswith("NOGO"))
        self.assertTrue(m.hostname_set("cab", "beaucoup-trop-long-pour-netbios", root=self.root)[0].startswith("NOGO"))

    def test_fichiers(self):
        j = m.hostname_set("cab-salon", "CABSALON", root=self.root, run=Faux())
        self.assertIn("127.0.1.1\tcab-salon", (self.root / "etc/hosts").read_text(encoding="utf-8"))
        smb = (self.root / "etc/samba/smb.conf").read_text(encoding="utf-8")
        self.assertIn("netbios name = CABSALON", smb)
        self.assertLess(smb.index("netbios name"), smb.index("[tables]"))
        m.hostname_set("cab-salon", "AUTRE", root=self.root, run=Faux())
        smb = (self.root / "etc/samba/smb.conf").read_text(encoding="utf-8")
        self.assertEqual(smb.count("netbios name"), 1)
        self.assertIn("= AUTRE", smb)


class Resume(unittest.TestCase):
    def test_vue_d_ensemble(self):
        r = m.resume(Faux(wifi=True))
        self.assertEqual(r["hostname"], "PinCabOs")
        self.assertTrue(r["wifi"]["present"])
        self.assertIn("capacites", r["wifi"])
        eno = next(i for i in r["interfaces"] if i["device"] == "eno1")
        self.assertEqual(eno["proposition"]["source"], "dhcp")
        self.assertFalse(r["legacy"])


if __name__ == "__main__":
    unittest.main()
