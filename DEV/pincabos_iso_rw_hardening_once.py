#!/usr/bin/env python3
from pathlib import Path
import re

PATH = Path("opt/pincabos/script/iso.sh")
text = PATH.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"NOGO [{label}] expected 1 match, found {count}")
    text = text.replace(old, new, 1)
    print(f"GO [OK] {label}")


def regex_once(pattern: str, replacement: str, label: str) -> None:
    global text
    rx = re.compile(pattern, re.S)
    matches = list(rx.finditer(text))
    if len(matches) != 1:
        raise SystemExit(f"NOGO [{label}] expected 1 match, found {len(matches)}")
    text = rx.sub(lambda _m: replacement, text, count=1)
    print(f"GO [OK] {label}")


# ---------------------------------------------------------------------------
# 1) Helper embedded in the ISO: refuse RO/unwritable /target before copying.
# ---------------------------------------------------------------------------
old = '''findmnt "$TARGET" >/dev/null || { echo "ERROR: $TARGET not mounted"; exit 1; }

# PINCABOS_LIVE_SQUASHFS_V1
'''
new = '''findmnt "$TARGET" >/dev/null || { echo "ERROR: $TARGET not mounted"; exit 1; }

# PINCABOS_TARGET_RW_PREFLIGHT_V1
TARGET_MOUNT_OPTIONS="$(findmnt -rn -o OPTIONS --target "$TARGET" 2>/dev/null || true)"
case ",$TARGET_MOUNT_OPTIONS," in
  *,rw,*) ;;
  *)
    echo "ERROR: target is not mounted read-write: $TARGET"
    findmnt -T "$TARGET" -o SOURCE,TARGET,FSTYPE,OPTIONS 2>/dev/null || true
    exit 76
    ;;
esac

TARGET_RW_PROBE="$TARGET/.pincabos-rw-probe-$$"
if ! (
  umask 077
  printf 'PinCabOS write probe\\n' > "$TARGET_RW_PROBE"
  sync "$TARGET_RW_PROBE" 2>/dev/null || sync
  rm -f "$TARGET_RW_PROBE"
); then
  rm -f "$TARGET_RW_PROBE" 2>/dev/null || true
  echo "ERROR: target write probe failed before payload extraction"
  findmnt -T "$TARGET" -o SOURCE,TARGET,FSTYPE,OPTIONS 2>/dev/null || true
  exit 77
fi

echo "GO [OK] target filesystem is mounted RW and writable"

# PINCABOS_LIVE_SQUASHFS_V1
'''
replace_once(old, new, "payload helper RW preflight")


# ---------------------------------------------------------------------------
# 2) Central live-installer target guard + one safe repair for fresh installs.
# ---------------------------------------------------------------------------
old = '''prepare_target_mount() {
  umount -R "$TARGET" 2>/dev/null || true
  rm -rf "$TARGET"
  mkdir -p "$TARGET"
}

write_fstab() {
'''
new = '''prepare_target_mount() {
  umount -R "$TARGET" 2>/dev/null || true
  rm -rf "$TARGET"
  mkdir -p "$TARGET"
}

# PINCABOS_TARGET_RW_GUARD_V1
target_mount_options() {
  findmnt -rn -o OPTIONS --target "$TARGET" 2>/dev/null || true
}

target_is_rw() {
  local options
  options="$(target_mount_options)"
  case ",$options," in
    *,rw,*) return 0 ;;
    *) return 1 ;;
  esac
}

target_write_probe() {
  local probe="$TARGET/.pincabos-rw-probe-$$"
  if ! (
    umask 077
    printf 'PinCabOS write probe\\n' > "$probe"
    sync "$probe" 2>/dev/null || sync
    rm -f "$probe"
  ) 2>/dev/null; then
    rm -f "$probe" 2>/dev/null || true
    return 1
  fi
  return 0
}

verify_target_rw() {
  mountpoint -q "$TARGET" || {
    pco_error "Target root is not mounted: $TARGET"
    return 1
  }

  if ! target_is_rw; then
    pco_warn "Target root is not RW; attempting one remount read-write"
    mount -o remount,rw "$TARGET" 2>/dev/null || true
  fi

  target_is_rw || {
    pco_error "Target root remains read-only"
    findmnt -T "$TARGET" -o SOURCE,TARGET,FSTYPE,OPTIONS 2>/dev/null || true
    return 1
  }

  target_write_probe || {
    pco_error "Target root write probe failed"
    findmnt -T "$TARGET" -o SOURCE,TARGET,FSTYPE,OPTIONS 2>/dev/null || true
    return 1
  }

  pco_go "Target root mounted RW and write-tested"
}

show_target_storage_diagnostics() {
  echo
  pco_step "Target storage diagnostics"
  findmnt -T "$TARGET" -o SOURCE,TARGET,FSTYPE,OPTIONS 2>/dev/null || true
  lsblk -o NAME,TYPE,SIZE,FSTYPE,FSUSE%,MOUNTPOINTS,MODEL "$DISK" 2>/dev/null || true
  echo
  echo "Recent kernel storage/filesystem messages:"
  dmesg 2>/dev/null \\
    | grep -Ei 'EXT4-fs|I/O error|Buffer I/O|blk_update_request|read-only|remount|nvme|ata[0-9].*(error|reset|failed)' \\
    | tail -120 || true
}

recover_fresh_target_filesystem_once() {
  local mode="$1"
  local fsck_rc=0

  if [ "$mode" = "upgrade" ]; then
    pco_error "Automatic filesystem repair is disabled in upgrade mode"
    return 1
  fi

  pco_warn "Target became read-only/unwritable during install."
  pco_warn "One automatic ext4 repair + payload retry will be attempted."

  sync || true
  umount -R "$TARGET" 2>/dev/null || true
  mountpoint -q "$TARGET" && {
    pco_error "Unable to unmount target for filesystem repair"
    return 1
  }

  set +e
  e2fsck -fy "$ROOT_PART"
  fsck_rc="$?"
  set -e

  case "$fsck_rc" in
    0|1) ;;
    *)
      pco_error "e2fsck failed or requires reboot (code $fsck_rc)"
      return 1
      ;;
  esac

  prepare_target_mount
  mount -o rw "$ROOT_PART" "$TARGET" || {
    pco_error "Unable to remount repaired root filesystem"
    return 1
  }
  verify_target_rw || return 1

  mkdir -p "$TARGET/boot/efi"
  mount "$EFI_PART" "$TARGET/boot/efi" || {
    pco_error "Unable to remount EFI partition after filesystem repair"
    return 1
  }
  mountpoint -q "$TARGET/boot/efi" || {
    pco_error "EFI partition is not mounted after filesystem repair"
    return 1
  }

  pco_go "Target filesystem repaired, remounted and ready for one retry"
}

write_fstab() {
'''
replace_once(old, new, "live installer RW guard")


# ---------------------------------------------------------------------------
# 3) Capture payload failure and retry once only if /target actually went RO.
# ---------------------------------------------------------------------------
install_payload = '''install_payload() {
  local mode="$1"
  local payload_rc=0
  local retry_done=0

  echo
  pco_step "Installing PinCabOS payload"

  verify_target_rw || {
    show_target_storage_diagnostics
    return 1
  }

  set +e
  PINCABOS_INSTALL_MODE="$mode" \\
    "$PAYLOAD_DIR/pincabos-v8.1g-install-cab-payload-to-target.sh" "$TARGET" "$PAYLOAD_DIR"
  payload_rc="$?"
  set -e

  if [ "$payload_rc" -ne 0 ]; then
    pco_error "Payload extraction/install failed (code $payload_rc)"
    show_target_storage_diagnostics

    if [ "$mode" != "upgrade" ] && { ! target_is_rw || ! target_write_probe; }; then
      if recover_fresh_target_filesystem_once "$mode"; then
        retry_done=1
        echo
        pco_step "Retrying PinCabOS payload once after ext4 repair"
        set +e
        PINCABOS_INSTALL_MODE="$mode" \\
          "$PAYLOAD_DIR/pincabos-v8.1g-install-cab-payload-to-target.sh" "$TARGET" "$PAYLOAD_DIR"
        payload_rc="$?"
        set -e
      fi
    fi
  fi

  if [ "$payload_rc" -ne 0 ]; then
    pco_error "Payload install failed permanently (code $payload_rc, retry=$retry_done)"
    show_target_storage_diagnostics
    return "$payload_rc"
  fi

  verify_target_rw || {
    show_target_storage_diagnostics
    return 1
  }

  apply_target_regional
  apply_target_orientation
  refresh_target_initrd_for_orientation

  test -f "$TARGET/etc/pincabos/orientation.conf"
  test -d "$TARGET/opt/pincabos"
  test -d "$TARGET/home/pinball/vpinfe"
  ls "$TARGET"/boot/vmlinuz-* >/dev/null
  ls "$TARGET"/boot/initrd.img-* >/dev/null

  pco_go "Payload PinCabOS installé et vérifié"
}

final_boot_refresh()'''
regex_once(
    r'install_payload\(\) \{.*?\n\}\n\nfinal_boot_refresh\(\)',
    install_payload,
    "payload retry/recovery",
)


# ---------------------------------------------------------------------------
# 4) Explicit RW mount + write probe for full, dualboot and upgrade paths.
# ---------------------------------------------------------------------------
for mode in ("full", "dualboot"):
    old = f'''  prepare_target_mount
  mount "$ROOT_PART" "$TARGET"
  mkdir -p "$TARGET/boot/efi"
  mount "$EFI_PART" "$TARGET/boot/efi"

  mountpoint -q "$TARGET"
  mountpoint -q "$TARGET/boot/efi"

  pco_go "Partitions root et EFI montées"

  install_payload "{mode}"
'''
    new = f'''  prepare_target_mount
  mount -o rw "$ROOT_PART" "$TARGET"
  verify_target_rw
  mkdir -p "$TARGET/boot/efi"
  mount "$EFI_PART" "$TARGET/boot/efi"

  mountpoint -q "$TARGET"
  mountpoint -q "$TARGET/boot/efi"

  pco_go "Partitions root et EFI montées (root RW vérifiée)"

  install_payload "{mode}"
'''
    replace_once(old, new, f"{mode} explicit RW mount")

old = '''  unmount_disk_mounts "$DISK"
  prepare_target_mount
  mount "$ROOT_PART" "$TARGET" || { pco_error "$(t up_none)"; return 1; }

  # An update must not be able to wipe a stranger's disk: refuse anything that
'''
new = '''  unmount_disk_mounts "$DISK"
  prepare_target_mount
  mount -o rw "$ROOT_PART" "$TARGET" || { pco_error "$(t up_none)"; return 1; }
  verify_target_rw || {
    show_target_storage_diagnostics
    umount -R "$TARGET" 2>/dev/null || true
    return 1
  }

  # An update must not be able to wipe a stranger's disk: refuse anything that
'''
replace_once(old, new, "upgrade explicit RW mount")


# ---------------------------------------------------------------------------
# 5) Small reliability cleanup found during the same audit.
# ---------------------------------------------------------------------------
replace_once(
    '''    pco_choose_language

    pco_choose_language

    while true; do
''',
    '''    pco_choose_language

    while true; do
''',
    "duplicate language prompt removal",
)

replace_once(
    '''chmod +x "$PAYLOAD_FULL/pincabos-v8.1g-install-cab-payload-to-target.sh"

rm -rf "$PAYLOAD_ISO_READY"
''',
    '''chmod +x "$PAYLOAD_FULL/pincabos-v8.1g-install-cab-payload-to-target.sh"
bash -n "$PAYLOAD_FULL/pincabos-v8.1g-install-cab-payload-to-target.sh" \\
  || die "Generated payload helper has a Bash syntax error"
echo "GO [OK] generated payload helper syntax valid"

rm -rf "$PAYLOAD_ISO_READY"
''',
    "payload helper syntax validation",
)

replace_once(
    '''chmod 755 "$ROOTFS_DIR/usr/local/sbin/pincabos-live-installer"

echo
echo "=== PinCabOS lean live TTY boot ==="
''',
    '''chmod 755 "$ROOTFS_DIR/usr/local/sbin/pincabos-live-installer"
bash -n "$ROOTFS_DIR/usr/local/sbin/pincabos-live-installer" \\
  || die "Generated live installer has a Bash syntax error"
echo "GO [OK] generated live installer syntax valid"

echo
echo "=== PinCabOS lean live TTY boot ==="
''',
    "live installer syntax validation",
)

replace_once(
    '''mksquashfs "$ROOTFS_DIR" "$SQUASHFS" -comp xz -b 1M -noappend

echo
echo "=== 16) Integrate payload into ISO tree ==="
''',
    '''mksquashfs "$ROOTFS_DIR" "$SQUASHFS" -comp xz -b 1M -noappend
unsquashfs -s "$SQUASHFS" >/dev/null \\
  || die "Repacked live squashfs metadata validation failed"
echo "GO [OK] repacked live squashfs metadata valid"

echo
echo "=== 16) Integrate payload into ISO tree ==="
''',
    "squashfs metadata validation",
)


markers = (
    "PINCABOS_TARGET_RW_PREFLIGHT_V1",
    "PINCABOS_TARGET_RW_GUARD_V1",
    "recover_fresh_target_filesystem_once",
    'mount -o rw "$ROOT_PART" "$TARGET"',
    "generated payload helper syntax valid",
    "generated live installer syntax valid",
    "repacked live squashfs metadata valid",
)
for marker in markers:
    if marker not in text:
        raise SystemExit(f"NOGO missing marker after patch: {marker}")

PATH.write_text(text, encoding="utf-8")
print("GO [OK] iso.sh hardening patch complete")
