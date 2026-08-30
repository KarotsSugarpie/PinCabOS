#!/usr/bin/env python3
# PinCabOS Smart Import archive hardening self-test

import importlib.util
import shutil
import tempfile
import zipfile
from pathlib import Path

ENTRYPOINT = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "pincabos-smart-archive-import.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "pincabos_smart_import_hardening_test_target",
        ENTRYPOINT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Impossible de charger {ENTRYPOINT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expect_runtime_error(callable_obj, marker):
    try:
        callable_obj()
    except RuntimeError as exc:
        if marker not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}") from exc
        return
    raise AssertionError(f"RuntimeError attendu avec marqueur {marker!r}")


def main():
    module = load_module()

    assert module.pincabos_zip_looks_like_rom(["u26.bin", "u27.bin"])
    assert module.pincabos_zip_looks_like_rom(["rom1.716", "rom2.716"])
    assert not module.pincabos_zip_looks_like_rom(["README.txt", "manual.pdf"])
    assert not module.pincabos_zip_looks_like_rom(["config.json", "helper.dll"])

    with tempfile.TemporaryDirectory(prefix="pincabos-hardening-test-") as td:
        root = Path(td)
        first = root / "media.zip"
        second = root / "media.7z"
        first.write_bytes(b"one")
        second.write_bytes(b"two")
        first_dest = module.pincabos_archive_extract_dir(root, "archive", first)
        second_dest = module.pincabos_archive_extract_dir(root, "archive", second)
        assert first_dest != second_dest

        if shutil.which("7z"):
            invalid = root / "corrupt.PinCabOs"
            invalid.write_bytes(b"not an archive\n")
            expect_runtime_error(lambda: module.archive_kind(invalid), "ARCHIVE ILLISIBLE:")

            support_zip = root / "support.zip"
            with zipfile.ZipFile(support_zip, "w") as zf:
                zf.writestr("README.txt", "support")
                zf.writestr("config.json", "{}")
            assert module.archive_kind(support_zip) == "support_archive"

            rom_zip = root / "rom.zip"
            with zipfile.ZipFile(rom_zip, "w") as zf:
                zf.writestr("u26.bin", b"rom")
                zf.writestr("u27.bin", b"rom")
            assert module.archive_kind(rom_zip) == "rom_zip"

            table_package = root / "table.PinCabOs"
            with zipfile.ZipFile(table_package, "w") as zf:
                zf.writestr("Test Table.vpx", b"vpx")
            assert module.archive_kind(table_package) == "table_archive"

            batch = root / "batch"
            batch.mkdir()
            unusual_rom = batch / "oddrom.zip"
            with zipfile.ZipFile(unusual_rom, "w") as zf:
                zf.writestr("chipA.xyz", b"rom")
                zf.writestr("chipB.xyz", b"rom")
            extract_root = root / "extract"
            resource_manifest = {
                "resources": [{
                    "stored_name": unusual_rom.name,
                    "resource_type": "romFile",
                    "vpsid": "selftest-rom",
                }]
            }
            module.extract_all_inputs(batch, extract_root, resource_manifest)
            copied_roms = list(extract_root.rglob("oddrom.zip"))
            assert len(copied_roms) == 1
            assert module.archive_kind(copied_roms[0]) == "rom_zip"

        old_logs = module.core.IMPORT_LOGS_ROOT
        try:
            module.core.IMPORT_LOGS_ROOT = root / "logs"
            table_dir = root / "Table"
            table_dir.mkdir()
            path = module.write_import_tree_log(
                table_dir,
                "Test Table",
                "testrom",
                {"root": ["Test Table.vpx"]},
            )
            path = Path(path)
            payload = path.read_bytes()
            assert b"\\n" not in payload
            assert b"\n" in payload
        finally:
            module.core.IMPORT_LOGS_ROOT = old_logs

    print("GO [OK] Smart Import archive hardening self-test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
