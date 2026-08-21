# PinCabOS local VPinFE theme integration

Base upstream: VPinFE v2.6.1

This patch adds support for the locally installed PinCabOS theme in the
native VPinFE Themes manager.

The local PinCabOS theme remains outside the official remote theme registry.

Expected Manager behavior:

- PinCabOS appears as a theme card.
- PinCabOS is detected as Installed.
- PinCabOS is detected as Active when selected.
- PinCabOS is detected as Configurable.
- A Local badge is shown.
- Refresh Registry preserves the local theme.
- The local PinCabOS theme does not expose the normal remote Delete action.

Canonical patch:

    v2.6.1-pincabos-local-theme-card.patch

The complete generated PyInstaller runtime is intentionally not stored as
part of this patch. Rebuild VPinFE from the upstream v2.6.1 source after
applying the patch.
