#!/bin/bash
# PinCabOS-File created by Karots Sugarpie
set -e

SSID="$1"
PASS="$2"

if [ -z "$SSID" ]; then
  echo "Usage: $0 SSID PASSWORD"
  exit 1
fi

systemctl enable --now NetworkManager 2>/dev/null || true

echo "Réseaux WiFi visibles:"
nmcli dev wifi list || true

echo
echo "Connexion au WiFi: $SSID"

# PINCABOS_WIFI_KEYMGMT_V1
#
# « nmcli dev wifi connect » laisse NetworkManager deviner la securite du
# reseau d'apres son cache de scan. Cache perime, ou profil bancal laisse
# par un essai precedent, et l'on obtient :
#   Error: 802-11-wireless-security.key-mgmt: property is missing.
# — puis chaque nouvel essai retombe sur le meme profil casse. Constate sur
# une Freebox par un testeur.
#
# On construit donc le profil explicitement : les restes d'essais precedents
# sont supprimes, la securite est lue dans le scan, et key-mgmt est toujours
# renseigne.

IFACE="$(nmcli -t -f DEVICE,TYPE dev status 2>/dev/null | awk -F: '$2=="wifi"{print $1; exit}')"
[ -n "$IFACE" ] || { echo "ECHEC: aucune interface WiFi detectee." >&2; exit 1; }

# Les profils du meme nom — dont ceux qu'un echec precedent a laisses sans
# key-mgmt — sont retires avant de recreer proprement.
nmcli -t -f NAME connection show 2>/dev/null | while IFS= read -r nom; do
  [ "$nom" = "$SSID" ] && nmcli connection delete "$nom" >/dev/null 2>&1 || true
done

SECURITE="$(nmcli -t -f SSID,SECURITY dev wifi list 2>/dev/null \
            | awk -F: -v s="$SSID" '$1 == s {print $2; exit}')"

if [ -z "$PASS" ]; then
  nmcli connection add type wifi ifname "$IFACE" con-name "$SSID" ssid "$SSID" >/dev/null
else
  case "$SECURITE" in
    *WPA3*)
      # WPA3 pur = SAE ; un reseau mixte WPA2/WPA3 annonce les deux et
      # tombe dans la branche wpa-psk, que les deux modes acceptent.
      if echo "$SECURITE" | grep -qE 'WPA[12]'; then
        GESTION_CLE="wpa-psk"
      else
        GESTION_CLE="sae"
      fi
      ;;
    *) GESTION_CLE="wpa-psk" ;;
  esac
  nmcli connection add type wifi ifname "$IFACE" con-name "$SSID" ssid "$SSID" \
        wifi-sec.key-mgmt "$GESTION_CLE" wifi-sec.psk "$PASS" >/dev/null
fi

if ! nmcli connection up "$SSID"; then
  # Un profil qui ne monte pas ne doit pas rester pour polluer l'essai
  # suivant — c'est precisement le piege que l'on corrige.
  nmcli connection delete "$SSID" >/dev/null 2>&1 || true
  echo "ECHEC: connexion refusee. Verifiez le mot de passe." >&2
  exit 1
fi

echo
echo "État réseau:"
# PINCABOS_WIFI_JOIN_VERIFY_V1
# nmcli rend la main avant que l'association soit etablie : sans cette
# verification, un mot de passe refuse ressemble a une reussite.
etat=""
for _ in $(seq 1 15); do
  etat="$(nmcli -t -f DEVICE,STATE,CONNECTION dev status 2>/dev/null \
          | awk -F: -v s="$SSID" '$3 == s && $2 == "connected" {print $1}')"
  [ -n "$etat" ] && break
  sleep 1
done
if [ -n "$etat" ]; then
  echo "CONNECTE: $SSID sur $etat"
  nmcli -t -f IP4.ADDRESS,IP4.GATEWAY dev show "$etat" 2>/dev/null | sed 's/^/  /'
else
  echo "ECHEC: association a $SSID non etablie apres 15 s." >&2
  echo "Verifiez le mot de passe et la portee du reseau." >&2
  nmcli connection delete "$SSID" >/dev/null 2>&1 || true
  nmcli device status || true
  exit 1
fi

nmcli device status || true
ip -br a
