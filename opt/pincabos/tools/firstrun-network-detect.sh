#!/usr/bin/env bash
# PinCabOS-File created by Karots Sugarpie
set -u

echo "===== Redémarrage / détection réseau PinCabOS PROFOND ====="
date

echo
echo "--- User / droits ---"
whoami
id

echo
echo "--- Mode ---"
echo "Mode profond First Run: restart services réseau + netplan apply."
echo "Sur une connexion distante, la console/WebApp peut couper quelques secondes."
echo "Sur un vrai cab en localhost, c'est le comportement voulu."

echo
echo "--- Services réseau avant ---"
systemctl is-active NetworkManager 2>/dev/null && echo "NetworkManager actif" || true
systemctl is-active systemd-networkd 2>/dev/null && echo "systemd-networkd actif" || true
systemctl is-active systemd-resolved 2>/dev/null && echo "systemd-resolved actif" || true

echo
echo "--- Interfaces avant ---"
ip -br addr || true
ip route || true

echo
echo "--- Restart services réseau si présents ---"

if systemctl list-unit-files NetworkManager.service >/dev/null 2>&1; then
  echo "Restart NetworkManager..."
  systemctl restart NetworkManager.service 2>&1 || true
fi

if systemctl list-unit-files systemd-networkd.service >/dev/null 2>&1; then
  echo "Restart systemd-networkd..."
  systemctl restart systemd-networkd.service 2>&1 || true
fi

if systemctl list-unit-files systemd-resolved.service >/dev/null 2>&1; then
  echo "Restart systemd-resolved..."
  systemctl restart systemd-resolved.service 2>&1 || true
fi

echo
echo "--- Netplan apply si disponible ---"
if command -v netplan >/dev/null 2>&1; then
  netplan apply 2>&1 || true
fi

echo
echo "--- Attente stabilisation réseau ---"
sleep 8

echo
echo "--- Renouvellement DHCP si possible ---"
IFACE="$(ip route | awk '/^default/ {print $5; exit}')"
if [ -n "${IFACE:-}" ] && command -v networkctl >/dev/null 2>&1; then
  echo "Interface par défaut: $IFACE"
  networkctl renew "$IFACE" 2>&1 || true
  sleep 4
fi

echo
echo "--- Interfaces après ---"
ip -br link || true
ip -br addr || true

echo
echo "--- Routes après ---"
ip route || true

GW="$(ip route | awk '/^default/ {print $3; exit}')"
IFACE="$(ip route | awk '/^default/ {print $5; exit}')"

echo
echo "Interface détectée: ${IFACE:-aucune}"
echo "Gateway détectée  : ${GW:-aucune}"

echo
echo "--- DNS ---"
resolvectl status 2>/dev/null | head -n 140 || cat /etc/resolv.conf || true

echo
echo "--- Tests réseau ---"
if [ -n "${GW:-}" ]; then
  echo "Test gateway: $GW"
  ping -c 1 -W 2 "$GW" 2>&1 || true
else
  echo "Aucune gateway détectée."
fi

echo
echo "Test Internet IP: 1.1.1.1"
ping -c 1 -W 2 1.1.1.1 2>&1 || true

echo
echo "Test DNS: update.pincabos.cc"
getent hosts update.pincabos.cc 2>&1 || true

echo
echo "--- Résultat résumé ---"
IPV4="$(ip -4 addr show scope global | awk '/inet / {print $2; exit}')"
DNSOK="$(getent hosts update.pincabos.cc >/dev/null 2>&1 && echo oui || echo non)"
GWOK="non"
if [ -n "${GW:-}" ] && ping -c 1 -W 2 "$GW" >/dev/null 2>&1; then
  GWOK="oui"
fi
NETOK="non"
if ping -c 1 -W 2 1.1.1.1 >/dev/null 2>&1; then
  NETOK="oui"
fi

echo "IPv4 globale : ${IPV4:-absente}"
echo "Interface    : ${IFACE:-absente}"
echo "Gateway      : ${GW:-absente}"
echo "Gateway OK   : $GWOK"
echo "Internet OK  : $NETOK"
echo "DNS OK       : $DNSOK"

echo
if [ -n "${IPV4:-}" ] && [ "$GWOK" = "oui" ] && [ "$NETOK" = "oui" ] && [ "$DNSOK" = "oui" ]; then
  echo "RESULTAT: OK réseau fonctionnel."
  exit 0
else
  echo "RESULTAT: ATTENTION réseau incomplet."
  exit 0
fi
