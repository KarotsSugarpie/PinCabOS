PinCabOS - Module Policy

Purpose:
- Modules are reusable shell blocks.
- Main scripts may call modules.
- Modules must not be edited during an install run.
- A module should be replaced by a new version, not patched in place.

Rules:
1. One module = one task family.
2. Modules should be idempotent when possible.
3. Modules must log to /opt/pincabos/logs when they do heavy work.
4. Modules must not download other modules directly.
5. Critical modules must create backups before changing files.
6. Modules must not modify go-pincabos.sh.
7. Modules must be auditable alone.
8. Modules should return clean exit codes.

Status format:
- GO [√] success
- NOGO [***] ERR-REFERENCE failure
