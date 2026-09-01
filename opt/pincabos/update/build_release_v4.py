#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def load_engine(repo: Path):
    path = (
        repo
        / "opt/pincabos/update/"
        "pincabos_updates.py"
    )

    spec = (
        importlib.util.spec_from_file_location(
            "pincabos_updates_release_engine",
            path
        )
    )

    if (
        spec is None
        or spec.loader is None
    ):
        raise SystemExit(
            "NOGO [!!] "
            "Impossible de charger "
            "le moteur V4."
        )

    mod = (
        importlib.util.module_from_spec(
            spec
        )
    )

    spec.loader.exec_module(
        mod
    )

    allowed = getattr(
        mod,
        "allowed",
        None
    )

    if not callable(
        allowed
    ):
        raise SystemExit(
            "NOGO [!!] "
            "allowed() absent."
        )

    return allowed


def sha256(path: Path):
    h = hashlib.sha256()

    with path.open(
        "rb"
    ) as f:
        for chunk in iter(
            lambda:
                f.read(
                    1024 * 1024
                ),
            b""
        ):
            h.update(
                chunk
            )

    return h.hexdigest()


def validate_script(path: Path):
    if (
        path.is_symlink()
        or not path.is_file()
    ):
        return

    try:
        first = path.open(
            "r",
            encoding="utf-8",
            errors="strict"
        ).readline().strip()

    except (
        UnicodeDecodeError,
        OSError
    ):
        return

    if (
        first.startswith("#!")
        and "python" in first
    ):
        compile(
            path.read_text(
                encoding="utf-8"
            ),
            str(path),
            "exec"
        )

    elif (
        first.startswith("#!")
        and (
            "bash" in first
            or first.endswith("/sh")
        )
    ):
        subprocess.run(
            [
                "bash",
                "-n",
                str(path)
            ],
            check=True
        )

    elif path.suffix == ".py":
        compile(
            path.read_text(
                encoding="utf-8"
            ),
            str(path),
            "exec"
        )

    elif path.suffix == ".sh":
        if first.startswith("#!"):
            return

        subprocess.run(
            [
                "bash",
                "-n",
                str(path)
            ],
            check=True
        )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--version",
        required=True
    )

    parser.add_argument(
        "--display-version",
        required=True
    )

    parser.add_argument(
        "--channel",
        required=True,
        choices=[
            "stable",
            "beta",
            "dev"
        ]
    )

    parser.add_argument(
        "--out",
        required=True
    )

    parser.add_argument(
        "--reboot-required",
        action="store_true"
    )

    args = parser.parse_args()

    repo = (
        Path(__file__)
        .resolve()
        .parents[3]
    )

    out = Path(
        args.out
    ).resolve()

    out.mkdir(
        parents=True,
        exist_ok=True
    )

    allowed = load_engine(
        repo
    )

    rows = []

    for path in repo.rglob("*"):
        if ".git" in path.parts:
            continue

        if not (
            path.is_file()
            or path.is_symlink()
        ):
            continue

        rel = (
            path.relative_to(repo)
            .as_posix()
        )

        if allowed(rel):
            rows.append(
                rel
            )

    rows = sorted(
        set(rows)
    )

    if not rows:
        raise SystemExit(
            "NOGO [!!] "
            "Aucun fichier gere."
        )

    for rel in rows:
        validate_script(
            repo / rel
        )

    # Git stocke sudoers comme 100644.
    # La Release doit les transporter 0440.
    for rel in rows:
        if not rel.startswith(
            "etc/sudoers.d/"
        ):
            continue

        path = (
            repo
            / rel
        )

        if (
            path.exists()
            and not path.is_symlink()
        ):
            path.chmod(
                0o440
            )

            if shutil.which(
                "visudo"
            ):
                subprocess.run(
                    [
                        "visudo",
                        "-cf",
                        str(path)
                    ],
                    check=True,
                    stdout=subprocess.DEVNULL
                )

    files = (
        out
        / "files.list"
    )

    files.write_text(
        "".join(
            rel + "\n"
            for rel in rows
        ),
        encoding="utf-8"
    )

    legacy = [
        "opt/pincabos/script/"
        "build-update.sh",

        "opt/pincabos/script/"
        "publish-update.sh",

        "opt/pincabos/update/"
        "client/getpcos",

        "opt/pincabos/update/"
        "client/install-getpcos.sh",

        "opt/pincabos/update/"
        "managed-paths.conf",

        "usr/local/sbin/"
        "build-update.sh",
    ]

    removals = sorted(
        rel
        for rel in legacy
        if allowed(rel)
    )

    remove = (
        out
        / "remove.list"
    )

    remove.write_text(
        "".join(
            rel + "\n"
            for rel in removals
        ),
        encoding="utf-8"
    )

    archive = (
        out
        / "pincabos-update.tar.zst"
    )

    subprocess.run(
        [
            "tar",
            "--zstd",
            "--verbatim-files-from",
            "--owner=0",
            "--group=0",
            "--numeric-owner",
            "-cpf",
            str(archive),
            "-C",
            str(repo),
            "-T",
            str(files),
        ],
        check=True
    )

    actual = sorted(
        set(
            x.rstrip("/")
            for x
            in subprocess.check_output(
                [
                    "tar",
                    "--zstd",
                    "-tf",
                    str(archive)
                ],
                text=True
            ).splitlines()
            if x
            and not x.endswith("/")
        )
    )

    if actual != rows:
        raise SystemExit(
            "NOGO [!!] "
            "Archive != files.list"
        )

    source_sha = (
        os.environ.get(
            "GITHUB_SHA"
        )
        or subprocess.check_output(
            [
                "git",
                "-C",
                str(repo),
                "rev-parse",
                "HEAD"
            ],
            text=True
        ).strip()
    )

    meta = {
        "schema": 4,
        "version":
            args.version,
        "display_version":
            args.display_version,
        "channel":
            args.channel,
        "repository":
            "PinCabOS/PinCabOS",
        "archive":
            "pincabos-update.tar.zst",
        "archive_sha256":
            sha256(archive),
        "files":
            "files.list",
        "remove":
            "remove.list",
        "file_count":
            len(rows),
        "remove_count":
            len(removals),
        "source_sha":
            source_sha,
        "reboot_required":
            bool(
                args.reboot_required
            ),
        "built_at":
            datetime.now(
                timezone.utc
            ).isoformat().replace(
                "+00:00",
                "Z"
            ),
    }

    release = (
        out
        / "release.json"
    )

    release.write_text(
        json.dumps(
            meta,
            indent=2,
            ensure_ascii=False
        ) + "\n",
        encoding="utf-8"
    )

    audit = (
        out
        / "audit.sha256"
    )

    with audit.open(
        "w",
        encoding="utf-8"
    ) as f:
        for path in [
            archive,
            files,
            remove,
            release,
        ]:
            f.write(
                f"{sha256(path)}  "
                f"{path.name}\n"
            )

    print(
        "GO [OK] Full Release: "
        f"{len(rows)} fichiers"
    )

    print(
        "GO [OK] Version: "
        f"{args.display_version}"
    )

    print(
        "GO [OK] Tag: "
        f"{args.version}"
    )

    print(
        "GO [OK] SHA256: "
        f"{meta['archive_sha256']}"
    )

    print(
        "GO [OK] Reboot required: "
        f"{meta['reboot_required']}"
    )


if __name__ == "__main__":
    main()
