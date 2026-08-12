#!/usr/bin/env bash
set -Eeuo pipefail
clear

hr(){ printf '%*s\n' 72 '' | tr ' ' '='; }
go(){ echo "GO [OK] $*"; }
warn(){ echo "WARN   $*"; }
die(){ echo "ERREUR $*" >&2; exit 1; }

hr
echo " PINCABOS V8.1G — INTEGRATION INSTALLER UPGRADES"
hr

[ "${EUID:-$(id -u)}" -eq 0 ] || die "lance ce script avec sudo/root"
[ $# -eq 1 ] || die "usage: $0 /chemin/racine/arbre-ISO"

ROOT="$(readlink -f "$1")"
HERE="$(cd -- "$(dirname -- "$0")" && pwd)"
LIVE="$ROOT/usr/local/sbin/pincabos-live-installer"
PAYLOAD="$ROOT/pincabos-payload/pincabos-v8.1g-install-cab-payload-to-target.sh"
P01="$HERE/01-pincabos-live-installer-regional-orientation.patch"
P02="$HERE/02-install-cab-payload-to-target-uid1000-root-admin.patch"
P03="$HERE/03-pinball-uid1000-root-admin-after-02.patch"

[ -f "$LIVE" ] || die "introuvable: $LIVE"
[ -f "$PAYLOAD" ] || die "introuvable: $PAYLOAD"
[ -f "$P01" ] || die "patch absent: $P01"
[ -f "$P02" ] || die "patch absent: $P02"
[ -f "$P03" ] || die "patch absent: $P03"

STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="/root/pincabos-installer-upgrades-backup-$STAMP"
mkdir -p "$BACKUP/usr/local/sbin" "$BACKUP/pincabos-payload"
cp -a "$LIVE" "$BACKUP/usr/local/sbin/"
cp -a "$PAYLOAD" "$BACKUP/pincabos-payload/"
go "Sauvegarde: $BACKUP"

echo
hr
echo " 1) Regional dynamique + orientation"
hr
if grep -q 'PINCABOS_REGIONAL_SETUP_DYNAMIC_V1' "$LIVE"; then
  go "deja present — patch 01 ignore"
else
  patch --dry-run -d "$ROOT" -p1 < "$P01" >/dev/null || die "dry-run patch 01 impossible"
  patch -d "$ROOT" -p1 < "$P01"
  go "patch 01 applique"
fi

echo
hr
echo " 2) pinball resolvable + UID 1000 + admin complet"
hr
HAS_2B=0; HAS_2C=0
grep -q "PINCABOS FIX: rendre 'pinball' resolvable" "$PAYLOAD" && HAS_2B=1 || true
grep -q 'PINCABOS POLICY: pinball UID 1000' "$PAYLOAD" && HAS_2C=1 || true

if [ "$HAS_2B" -eq 0 ] && [ "$HAS_2C" -eq 0 ]; then
  patch --dry-run -d "$ROOT" -p1 < "$P02" >/dev/null || die "dry-run patch 02 impossible"
  patch -d "$ROOT" -p1 < "$P02"
  go "correctif 2b + politique 2c appliques"
elif [ "$HAS_2B" -eq 1 ] && [ "$HAS_2C" -eq 0 ]; then
  patch --dry-run -d "$ROOT" -p1 < "$P03" >/dev/null || die "dry-run patch 03 impossible"
  patch -d "$ROOT" -p1 < "$P03"
  go "2b deja present; politique 2c ajoutee"
elif [ "$HAS_2B" -eq 1 ] && [ "$HAS_2C" -eq 1 ]; then
  go "2b et 2c deja presents — rien a faire"
else
  die "etat incoherent: politique 2c presente sans correctif 2b"
fi

echo
hr
echo " 3) Validation syntaxique"
hr
bash -n "$LIVE"
go "bash -n live installer"
bash -n "$PAYLOAD"
go "bash -n payload installer"

grep -q 'apply_target_orientation' "$LIVE" || die "apply_target_orientation absent"
grep -q 'pco_gen_locales' "$LIVE" || die "pco_gen_locales absent"
grep -q 'PINCABOS POLICY: pinball UID 1000' "$PAYLOAD" || die "politique pinball absente"
grep -q 'NOPASSWD: ALL' "$PAYLOAD" || die "sudo NOPASSWD absent"
grep -q 'polkit.Result.YES' "$PAYLOAD" || die "regle Polkit absente"

echo
hr
echo " RESULTAT"
hr
go "Regional dynamique"
go "Claviers XKB dynamiques"
go "Fuseaux horaires dynamiques"
go "Orientation 0/90/180/270 + Plymouth"
go "Correctif live pinball UID/GID 1000"
go "Validation cible pinball uid=1000 gid=1000"
go "sudo root NOPASSWD"
go "Polkit sans authentification"
echo
echo "Rollback fichiers source:"
echo "  cp -a '$BACKUP/usr/local/sbin/pincabos-live-installer' '$LIVE'"
echo "  cp -a '$BACKUP/pincabos-payload/pincabos-v8.1g-install-cab-payload-to-target.sh' '$PAYLOAD'"
echo
