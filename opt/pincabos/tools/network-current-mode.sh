#!/usr/bin/env bash
# PinCabOS-File created by Karots Sugarpie
# V2 (PINCABOS_NETWORK_V2) : le mode rapporte est le mode EFFECTIF.
# La V1 deduisait le mode d'un SEUL fichier netplan (00-pincabos-dhcp4.yaml),
# qui pouvait etre supplante par un autre fichier ou par un profil
# NetworkManager : la page annoncait "static" alors que l'interface etait
# restee en DHCP, en affichant l'adresse DHCP lue en direct.
set -Eeuo pipefail
PATH="/usr/sbin:/usr/bin:/sbin:/bin"

CONF="/etc/netplan/99-pincabos-network.yaml"
LEGACY="/etc/netplan/00-pincabos-dhcp4.yaml"

find_main_iface() {
  local iface=""

  iface="$(
    ip -4 route show default 2>/dev/null |
    awk '/^default/ {
      for (i=1; i<=NF; i++) {
        if ($i == "dev") {
          print $(i+1)
          exit
        }
      }
    }'
  )"

  if [[ -n "$iface" && -d "/sys/class/net/$iface" ]]; then
    printf '%s\n' "$iface"
    return 0
  fi

  ip -o link show 2>/dev/null |
  awk -F': ' '
    $2 !~ /^(lo|docker|br-|veth|virbr|zt|tailscale)/ {
      split($2, a, "@")
      print a[1]
      exit
    }
  '
}

iface="$(find_main_iface || true)"
ipcidr=""
gateway=""
dns=""
mode="inconnu"

if [[ -n "$iface" ]]; then
  ipcidr="$(
    ip -o -4 addr show dev "$iface" scope global 2>/dev/null |
    awk '{print $4; exit}'
  )"

  gateway="$(
    ip -4 route show default dev "$iface" 2>/dev/null |
    awk '/^default/ {
      for (i=1; i<=NF; i++) {
        if ($i == "via") {
          print $(i+1)
          exit
        }
      }
    }'
  )"

  if command -v resolvectl >/dev/null 2>&1; then
    dns="$(
      resolvectl dns "$iface" 2>/dev/null |
      awk -F': ' 'NF > 1 {print $2; exit}' |
      awk '{$1=$1; print}' |
      tr ' ' ','
    )"
  fi
fi

if [[ -z "$dns" && -r /etc/resolv.conf ]]; then
  dns="$(
    awk '/^nameserver[[:space:]]+/ {print $2}' /etc/resolv.conf |
    grep -v '^127\.0\.0\.53$' |
    paste -sd, -
  )"
fi

# 1) NetworkManager gere l'interface sur le systeme installe : sa methode IPv4
#    est la verite (manual = fixe, auto = DHCP).
if [[ -n "$iface" ]] && command -v nmcli >/dev/null 2>&1; then
  connection="$(
    nmcli -t -f DEVICE,CONNECTION device status 2>/dev/null |
    awk -F: -v dev="$iface" '$1 == dev {print $2; exit}'
  )"
  if [[ -n "$connection" && "$connection" != "--" ]]; then
    method="$(nmcli -g ipv4.method connection show "$connection" 2>/dev/null || true)"
    case "$method" in
      manual) mode="static" ;;
      auto)   mode="dhcp" ;;
    esac
  fi
fi

# 2) Route par defaut obtenue en DHCP.
if [[ "$mode" == "inconnu" ]] && ip -4 route show default 2>/dev/null | grep -q 'proto dhcp'; then
  mode="dhcp"
fi

# 3) Adresse sans bail = adresse fixe.
if [[ "$mode" == "inconnu" && -n "$iface" ]]; then
  if ip -o -4 addr show dev "$iface" scope global 2>/dev/null | grep -q 'valid_lft forever'; then
    mode="static"
  fi
fi

# 4) Dernier recours : la configuration PinCabOS, fichier prioritaire d'abord.
if [[ "$mode" == "inconnu" ]]; then
  for candidate in "$CONF" "$LEGACY"; do
    [[ -f "$candidate" ]] || continue
    if grep -Eqi '^[[:space:]]*dhcp4:[[:space:]]*true' "$candidate"; then
      mode="dhcp"
      break
    elif grep -Eqi '^[[:space:]]*dhcp4:[[:space:]]*false' "$candidate"; then
      mode="static"
      break
    fi
  done
fi

printf 'interface=%s\n' "$iface"
printf 'mode=%s\n' "$mode"
printf 'ipcidr=%s\n' "$ipcidr"
printf 'gateway=%s\n' "$gateway"
printf 'dns=%s\n' "$dns"
