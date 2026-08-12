#!/usr/bin/env bash
set -Eeuo pipefail
PATH="/usr/sbin:/usr/bin:/sbin:/bin"

CONF="/etc/netplan/00-pincabos-dhcp4.yaml"

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

if [[ -f "$CONF" ]]; then
  if grep -Eqi '^[[:space:]]*dhcp4:[[:space:]]*true' "$CONF"; then
    mode="dhcp"
  elif grep -Eqi '^[[:space:]]*dhcp4:[[:space:]]*false' "$CONF"; then
    mode="static"
  fi
fi

if [[ "$mode" == "inconnu" ]] && ip -4 route show default 2>/dev/null | grep -q 'proto dhcp'; then
  mode="dhcp"
fi

printf 'interface=%s\n' "$iface"
printf 'mode=%s\n' "$mode"
printf 'ipcidr=%s\n' "$ipcidr"
printf 'gateway=%s\n' "$gateway"
printf 'dns=%s\n' "$dns"
