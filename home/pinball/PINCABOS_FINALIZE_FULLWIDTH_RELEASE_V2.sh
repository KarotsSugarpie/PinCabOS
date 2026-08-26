#!/usr/bin/env bash
set -Eeuo pipefail

REPO="KarotsSugarpie/PinCabOS"
WORK="/home/pinball/pincabos-fullwidth-auto-release-20260822-093232"
SRC="$WORK/source"
BRANCH="feat/fullwidth-updates-auto-release-20260822-093232"
EXPECTED_MAIN="07df37b43762b5864b6fe73687910ff314693203"
DIST="$WORK/final-dist"

fail() {
    echo
    echo "==============================================================="
    echo " NOGO [!!] FINALISATION PINCABOS"
    echo "==============================================================="
    echo "Work conserve : $WORK"
    exit 1
}

trap '
RC=$?
if [ "$RC" -ne 0 ]; then
    echo
    echo "NOGO [!!] Erreur ligne $LINENO - code $RC"
    echo "Work conserve : '"$WORK"'"
fi
' ERR

echo "==============================================================="
echo " PINCABOS - FINALISATION FULLWIDTH + UPDATES V4"
echo " RELEASE COMPLETE + VERSION = NUMERO PR"
echo " AUCUN RECLONE - AUCUN REBOOT"
echo "==============================================================="
echo

cd "$SRC"

echo "=== 1. GARDE GITHUB ==="

[ "$(git branch --show-current)" = "$BRANCH" ] || {
    echo "NOGO [!!] Mauvaise branche."
    fail
}

git fetch origin main

MAIN_NOW="$(git rev-parse origin/main)"

echo "Main attendu : $EXPECTED_MAIN"
echo "Main actuel  : $MAIN_NOW"

[ "$MAIN_NOW" = "$EXPECTED_MAIN" ] || {
    echo "NOGO [!!] main a change."
    fail
}

if git ls-remote \
    --exit-code \
    --heads \
    origin \
    "$BRANCH" \
    >/dev/null 2>&1
then
    echo "NOGO [!!] Branche deja presente sur GitHub."
    fail
fi

echo "GO [OK] Aucun push precedent."
echo

echo "=== 2. COMPLETION DU SPARSE CHECKOUT ==="

cat > .git/info/sparse-checkout <<'EOF'
/.github/workflows/
/opt/pincabos/web/
/opt/pincabos/bin/
/opt/pincabos/script/
/opt/pincabos/update/
/opt/pincabos/modules/
/opt/pincabos/config/version.json
/opt/pincabos/version.json
/usr/local/bin/
/usr/local/sbin/
/etc/systemd/system/
/etc/lightdm/lightdm.conf.d/
/etc/tmpfiles.d/
/etc/udev/rules.d/
/etc/sudoers.d/
/etc/polkit-1/rules.d/
EOF

git sparse-checkout reapply

echo "GO [OK] Tous les chemins geres par Updates V4 sont presents."
echo

echo "=== 3. DO_UPDATE FINAL - REMPLACEMENT COMPLET ==="

python3 - <<'PY'
from pathlib import Path

p = Path("opt/pincabos/update/pincabos_updates.py")
s = p.read_text(encoding="utf-8")

for required in (
    "def local_tag():",
    "def display_version_from_tag(",
    "def sync_version_files(",
):
    if required not in s:
        raise SystemExit(
            f"NOGO [!!] Helper moteur absent : {required}"
        )

start = s.find("def do_update():")

if start < 0:
    raise SystemExit(
        "NOGO [!!] do_update() introuvable."
    )

end = s.find(
    "\ndef rollback_last():",
    start
)

if end < 0:
    raise SystemExit(
        "NOGO [!!] rollback_last() introuvable."
    )

new = r'''def do_update():
    require_root()

    CACHE.mkdir(
        parents=True,
        exist_ok=True
    )

    BACKUPS.mkdir(
        parents=True,
        exist_ok=True
    )

    m = release()

    if not m:
        raise UpdateError(
            'No compatible GitHub Release found.'
        )

    if local_tag() == m['version']:
        print(
            f'GO [OK] Already up to date: '
            f'{m["version"]}'
        )
        return 0

    assets = m['_assets']

    names = [
        m.get(
            'archive',
            'pincabos-update.tar.zst'
        ),
        m.get(
            'files',
            'files.list'
        ),
        m.get(
            'remove',
            'remove.list'
        ),
    ]

    for name in names:
        if name not in assets:
            raise UpdateError(
                f'Missing Release asset: {name}'
            )

    work = Path(
        tempfile.mkdtemp(
            prefix='pincabos-update-',
            dir=str(CACHE)
        )
    )

    try:
        archive = work / names[0]
        files = work / names[1]
        remove = work / names[2]

        for name, target in zip(
            names,
            [archive, files, remove]
        ):
            download(
                assets[name][
                    'browser_download_url'
                ],
                target
            )

        expected_sha = str(
            m.get(
                'archive_sha256',
                ''
            )
        ).lower()

        actual_sha = sha256(
            archive
        ).lower()

        if actual_sha != expected_sha:
            raise UpdateError(
                'Archive SHA256 mismatch.'
            )

        rows = validate_list(
            files
        )

        explicit_remove = (
            validate_list(remove)
            if remove.stat().st_size
            else []
        )

        previous_state = load_json(
            STATE,
            {}
        )

        previous_files = [
            str(x).strip()
            for x in previous_state.get(
                'installed_files',
                []
            )
            if str(x).strip()
            and allowed(str(x).strip())
        ]

        stale = sorted(
            set(previous_files)
            - set(rows)
        )

        removals = sorted(
            set(
                explicit_remove
                + stale
            )
        )

        if stale:
            print(
                'INFO [--] '
                f'{len(stale)} ancien(s) '
                'fichier(s) gere(s) '
                'seront retires.'
            )

        actual_archive = sorted(
            set(
                x.rstrip('/')
                for x
                in subprocess.check_output(
                    [
                        'tar',
                        '--zstd',
                        '-tf',
                        str(archive)
                    ],
                    text=True
                ).splitlines()
                if x
                and not x.endswith('/')
            )
        )

        if rows != actual_archive:
            raise UpdateError(
                'Archive content differs '
                'from files.list.'
            )

        stamp = subprocess.check_output(
            [
                'date',
                '+%Y%m%d-%H%M%S'
            ],
            text=True
        ).strip()

        backup_dir = (
            BACKUPS
            / stamp
        )

        backup_dir.mkdir(
            parents=True
        )

        existing = []
        new_files = []
        owners = {}

        for rel in sorted(
            set(
                rows
                + removals
            )
        ):
            target = (
                Path('/')
                / rel
            )

            if (
                target.exists()
                or target.is_symlink()
            ):
                existing.append(
                    rel
                )

                try:
                    stat = (
                        target.lstat()
                    )

                    owners[rel] = {
                        'uid': stat.st_uid,
                        'gid': stat.st_gid,
                    }

                except OSError:
                    pass

            else:
                new_files.append(
                    rel
                )

        (
            backup_dir
            / 'existing.list'
        ).write_text(
            ''.join(
                x + '\n'
                for x in existing
            ),
            encoding='utf-8'
        )

        (
            backup_dir
            / 'new.list'
        ).write_text(
            ''.join(
                x + '\n'
                for x in new_files
            ),
            encoding='utf-8'
        )

        (
            backup_dir
            / 'owners.json'
        ).write_text(
            json.dumps(
                owners,
                indent=2
            ) + '\n',
            encoding='utf-8'
        )

        (
            backup_dir
            / 'previous-version'
        ).write_text(
            local_tag()
            + '\n',
            encoding='utf-8'
        )

        (
            backup_dir
            / 'previous-state.json'
        ).write_text(
            json.dumps(
                previous_state,
                indent=2
            ) + '\n',
            encoding='utf-8'
        )

        if existing:
            subprocess.run(
                [
                    'tar',
                    '--zstd',
                    '-cpf',
                    str(
                        backup_dir
                        / 'backup.tar.zst'
                    ),
                    '-C',
                    '/',
                    '-T',
                    str(
                        backup_dir
                        / 'existing.list'
                    )
                ],
                check=True
            )

        services = active_services()

        for service in services:
            subprocess.run(
                [
                    'systemctl',
                    'stop',
                    service
                ],
                check=False
            )

        try:
            subprocess.run(
                [
                    'tar',
                    '--zstd',
                    '-xpf',
                    str(archive),
                    '-C',
                    '/'
                ],
                check=True
            )

            # Les fichiers deja existants
            # conservent leur UID/GID.
            for rel, meta in owners.items():
                target = (
                    Path('/')
                    / rel
                )

                if not (
                    target.exists()
                    or target.is_symlink()
                ):
                    continue

                try:
                    uid = int(
                        meta['uid']
                    )

                    gid = int(
                        meta['gid']
                    )

                    if target.is_symlink():
                        os.lchown(
                            target,
                            uid,
                            gid
                        )
                    else:
                        os.chown(
                            target,
                            uid,
                            gid
                        )

                except OSError as exc:
                    print(
                        'WARNING [--] '
                        'Owner restore failed '
                        f'for {rel}: {exc}'
                    )

            # Sécurité stricte sudoers.
            for rel in rows:
                if not rel.startswith(
                    'etc/sudoers.d/'
                ):
                    continue

                target = (
                    Path('/')
                    / rel
                )

                if (
                    target.exists()
                    and not target.is_symlink()
                ):
                    target.chmod(
                        0o440
                    )

            for rel in removals:
                target = (
                    Path('/')
                    / rel
                )

                if (
                    target.is_dir()
                    and not target.is_symlink()
                ):
                    shutil.rmtree(
                        target,
                        ignore_errors=True
                    )

                else:
                    try:
                        target.unlink()
                    except FileNotFoundError:
                        pass

            validate_installed(
                rows
            )

        except Exception:
            for rel in new_files:
                target = (
                    Path('/')
                    / rel
                )

                if (
                    target.is_dir()
                    and not target.is_symlink()
                ):
                    shutil.rmtree(
                        target,
                        ignore_errors=True
                    )

                else:
                    try:
                        target.unlink()
                    except FileNotFoundError:
                        pass

            backup_tar = (
                backup_dir
                / 'backup.tar.zst'
            )

            if backup_tar.exists():
                subprocess.run(
                    [
                        'tar',
                        '--zstd',
                        '-xpf',
                        str(backup_tar),
                        '-C',
                        '/'
                    ],
                    check=False
                )

            restart_services(
                services
            )

            raise

        restart_services(
            services
        )

        display = (
            m.get(
                'display_version'
            )
            or display_version_from_tag(
                m['version']
            )
        )

        reboot_required = bool(
            m.get(
                'reboot_required',
                False
            )
        )

        save_json(
            STATE,
            {
                'installed_version':
                    m['version'],

                'display_version':
                    display,

                'installed_files':
                    rows,

                'last_backup':
                    str(backup_dir),

                'channel':
                    config()[1],

                'reboot_required':
                    reboot_required,
            }
        )

        try:
            sync_version_files(
                display
            )
        except Exception as exc:
            print(
                'WARNING [--] '
                'Version files not '
                f'synchronized: {exc}'
            )

        print(
            'GO [OK] Update installed: '
            f'{display}'
        )

        print(
            'GO [OK] Release tag: '
            f'{m["version"]}'
        )

        print(
            'GO [OK] Backup: '
            f'{backup_dir}'
        )

        print(
            'Reboot required  : '
            + (
                'yes'
                if reboot_required
                else 'no'
            )
        )

        return 0

    finally:
        shutil.rmtree(
            work,
            ignore_errors=True
        )
'''

s = (
    s[:start]
    + new.rstrip()
    + "\n\n"
    + s[end + 1:]
)

p.write_text(
    s,
    encoding="utf-8"
)

print(
    "GO [OK] do_update() "
    "remplace completement."
)
PY

echo

echo "=== 4. BUILDER RELEASE V4 COMPLET ==="

cat > opt/pincabos/update/build_release_v4.py <<'PY'
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
            "KarotsSugarpie/PinCabOS",
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
PY

chmod +x \
    opt/pincabos/update/build_release_v4.py

echo "GO [OK] Builder Full Release cree."
echo

echo "=== 5. RUNNER WEB INDEPENDANT ==="

cat > usr/local/sbin/pincabos-update-web-runner <<'PY'
#!/usr/bin/env python3

import fcntl
import json
import os
import pwd
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


STATE = Path(
    "/tmp/pincabos-update-web-state.json"
)

LOG = Path(
    "/tmp/pincabos-update-web.log"
)

LOCK = Path(
    "/run/lock/pincabos-update-web.lock"
)

ENGINE_STATE = Path(
    "/var/lib/pincabos/updates/state.json"
)


def now():
    return (
        datetime.now(
            timezone.utc
        )
        .isoformat()
        .replace(
            "+00:00",
            "Z"
        )
    )


def pinball_ids():
    try:
        user = pwd.getpwnam(
            "pinball"
        )

        return (
            user.pw_uid,
            user.pw_gid
        )

    except KeyError:
        return (
            -1,
            -1
        )


def chown_pinball(path):
    uid, gid = pinball_ids()

    if uid < 0:
        return

    try:
        os.chown(
            path,
            uid,
            gid
        )
    except OSError:
        pass


def save_state(data):
    tmp = Path(
        f"{STATE}.tmp.{os.getpid()}"
    )

    tmp.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False
        ) + "\n",
        encoding="utf-8"
    )

    tmp.chmod(
        0o644
    )

    chown_pinball(
        tmp
    )

    os.replace(
        tmp,
        STATE
    )

    chown_pinball(
        STATE
    )


def load_json(path):
    try:
        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    except Exception:
        return {}


def prepare_log():
    LOG.write_text(
        "",
        encoding="utf-8"
    )

    LOG.chmod(
        0o644
    )

    chown_pinball(
        LOG
    )


def base_state(
    action,
    reboot_after=False
):
    return {
        "running": True,
        "pid": os.getpid(),
        "action": action,
        "status": "running",
        "message":
            f"Operation lancee : {action}",
        "started_at": now(),
        "finished_at": "",
        "last_exit_code": None,
        "reboot_after":
            bool(reboot_after),
        "reboot_recommended":
            False,
        "reboot_scheduled":
            False,
    }


def main():
    if len(sys.argv) < 2:
        return 2

    action = (
        sys.argv[1]
        .strip()
        .lower()
    )

    reboot_after = (
        len(sys.argv) >= 3
        and sys.argv[2] == "1"
    )

    if action not in {
        "check",
        "update",
        "rollback",
        "reboot",
    }:
        return 2

    LOCK.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    lock_file = LOCK.open(
        "w"
    )

    try:
        fcntl.flock(
            lock_file.fileno(),
            fcntl.LOCK_EX
            | fcntl.LOCK_NB
        )

    except BlockingIOError:
        return 75

    state = base_state(
        action,
        reboot_after
    )

    prepare_log()
    save_state(
        state
    )

    if action == "reboot":
        state.update(
            {
                "status":
                    "success",
                "message":
                    "Redemarrage planifie.",
                "running":
                    False,
                "finished_at":
                    now(),
                "last_exit_code":
                    0,
                "reboot_scheduled":
                    True,
            }
        )

        save_state(
            state
        )

        time.sleep(
            3
        )

        subprocess.run(
            [
                "/usr/bin/systemctl",
                "reboot"
            ],
            check=False
        )

        return 0

    with LOG.open(
        "w",
        encoding="utf-8"
    ) as output:
        process = subprocess.Popen(
            [
                "/usr/local/sbin/getpcos",
                action
            ],
            stdout=output,
            stderr=subprocess.STDOUT,
            text=True
        )

        rc = process.wait()

    LOG.chmod(
        0o644
    )

    chown_pinball(
        LOG
    )

    engine = load_json(
        ENGINE_STATE
    )

    reboot_required = bool(
        engine.get(
            "reboot_required",
            False
        )
    )

    state.update(
        {
            "running":
                False,
            "finished_at":
                now(),
            "last_exit_code":
                rc,
            "status":
                (
                    "success"
                    if rc == 0
                    else "error"
                ),
            "message":
                (
                    "Operation terminee."
                    if rc == 0
                    else
                    f"Operation en erreur "
                    f"(code {rc})."
                ),
            "reboot_recommended":
                (
                    reboot_required
                    if action == "update"
                    else False
                ),
        }
    )

    save_state(
        state
    )

    if (
        rc == 0
        and action == "update"
        and reboot_after
        and reboot_required
    ):
        state[
            "reboot_scheduled"
        ] = True

        state[
            "message"
        ] = (
            "Mise a jour terminee. "
            "Redemarrage requis et planifie."
        )

        save_state(
            state
        )

        time.sleep(
            4
        )

        subprocess.run(
            [
                "/usr/bin/systemctl",
                "reboot"
            ],
            check=False
        )

    return rc


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
PY

chmod 0755 \
    usr/local/sbin/pincabos-update-web-runner

echo "GO [OK] Runner Web externe cree."
echo

echo "=== 6. BRANCHEMENT DE LA PAGE WEB SUR LE RUNNER ==="

python3 - <<'PY'
from pathlib import Path
import re

p = Path(
    "opt/pincabos/web/"
    "pincabos_updates.py"
)

s = p.read_text(
    encoding="utf-8"
)

s = re.sub(
    r'''WEBSTATE\s*=\s*Path\(
        ["'][^"']*web-state\.json["']
        \)''',
    'WEBSTATE = Path('
    '"/tmp/pincabos-update-web-state.json")',
    s,
    count=1,
    flags=re.X
)


def replace_function(
    source,
    name,
    replacement
):
    pattern = re.compile(
        rf'^def {re.escape(name)}'
        r'\(.*?(?=^def |\Z)',
        re.M | re.S
    )

    result, count = pattern.subn(
        replacement.rstrip()
        + "\n\n",
        source,
        count=1
    )

    if count != 1:
        raise SystemExit(
            f"NOGO [!!] Fonction "
            f"{name} non remplacee: "
            f"{count}"
        )

    return result


s = replace_function(
    s,
    "_run_action",
    r'''
def _run_action(
    action,
    reboot_after=False
):
    flag = (
        "1"
        if reboot_after
        else "0"
    )

    subprocess.Popen(
        [
            "sudo",
            "-n",
            "/usr/local/sbin/"
            "pincabos-update-web-runner",
            action,
            flag,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
'''
)

s = replace_function(
    s,
    "_launch_reboot_delayed",
    r'''
def _launch_reboot_delayed(
    delay_sec=4
):
    subprocess.Popen(
        [
            "sudo",
            "-n",
            "/usr/local/sbin/"
            "pincabos-update-web-runner",
            "reboot",
            "0",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
'''
)

if not re.search(
    r'^def register\(',
    s,
    flags=re.M
):
    if (
        "def _pincabos_updates_register("
        not in s
    ):
        raise SystemExit(
            "NOGO [!!] "
            "register Updates absent."
        )

    s = s.rstrip() + r'''

def register(app, page):
    return _pincabos_updates_register(
        app,
        page
    )
''' + "\n"

if (
    'WEBSTATE = Path('
    '"/tmp/pincabos-update-web-state.json")'
    not in s
):
    raise SystemExit(
        "NOGO [!!] WEBSTATE non corrige."
    )

p.write_text(
    s,
    encoding="utf-8"
)

print(
    "GO [OK] Boutons Web -> "
    "runner independant."
)
PY

echo

echo "=== 7. SUDOERS MINIMAL ==="

chmod u+w \
    etc/sudoers.d/pincabos-updates-web \
    2>/dev/null || true

cat > etc/sudoers.d/pincabos-updates-web <<'EOF'
pinball ALL=(root) NOPASSWD: /usr/local/sbin/pincabos-update-web-runner
EOF

chmod 0440 \
    etc/sudoers.d/pincabos-updates-web

sudo visudo \
    -cf \
    etc/sudoers.d/pincabos-updates-web

rm -f \
    usr/local/sbin/pincabos-update-reboot

echo "GO [OK] Aucun sudo bash."
echo "GO [OK] Aucun sudo getpcos direct depuis le Web."
echo

echo "=== 8. WORKFLOW AUTO RELEASE ==="

cat > .github/workflows/pincabos-release-v4.yml <<'YAML'
name: PinCabOS Release V4

on:
  pull_request_target:
    types:
      - closed

  workflow_dispatch:
    inputs:
      pr_number:
        description: Numero de PR a publier
        required: false
        type: string

      channel:
        description: Canal
        required: true
        default: beta
        type: choice
        options:
          - stable
          - beta
          - dev

permissions:
  contents: write
  pull-requests: read

concurrency:
  group: pincabos-release-v4
  cancel-in-progress: false

jobs:
  release:
    if: >
      github.event_name == 'workflow_dispatch' ||
      github.event.pull_request.merged == true

    runs-on: ubuntu-latest

    steps:
      - name: Checkout main
        uses: actions/checkout@v4
        with:
          ref: main
          fetch-depth: 0

      - name: Install tools
        run: |
          sudo apt-get update
          sudo apt-get install -y zstd

      - name: Resolve merged PR
        id: version
        env:
          GH_TOKEN: ${{ github.token }}
          EVENT_PR: ${{ github.event.pull_request.number }}
          INPUT_PR: ${{ inputs.pr_number }}
          INPUT_CHANNEL: ${{ inputs.channel }}
        shell: bash
        run: |
          set -Eeuo pipefail

          latest="$(
            gh pr list \
              --repo "$GITHUB_REPOSITORY" \
              --state merged \
              --limit 100 \
              --json number,mergedAt \
              --jq \
              'sort_by(.mergedAt) | last | .number'
          )"

          if [[ -z "$latest" || "$latest" == "null" ]]; then
            echo "Aucune PR mergee." >&2
            exit 1
          fi

          if [[ "$GITHUB_EVENT_NAME" == "workflow_dispatch" ]]; then
            pr="${INPUT_PR:-$latest}"
            channel="${INPUT_CHANNEL:-beta}"
          else
            pr="$EVENT_PR"
            channel="beta"
          fi

          if [[ "$pr" != "$latest" ]]; then
            echo "PR #$pr n'est plus la derniere mergee."
            echo "publish=false" >> "$GITHUB_OUTPUT"
            exit 0
          fi

          display="Alpha 2.${pr}"
          date_tag="$(date -u +%Y%m%d)"
          tag="alpha2.${pr}-${channel}.${date_tag}.1"

          echo "publish=true" >> "$GITHUB_OUTPUT"
          echo "pr=$pr" >> "$GITHUB_OUTPUT"
          echo "display=$display" >> "$GITHUB_OUTPUT"
          echo "channel=$channel" >> "$GITHUB_OUTPUT"
          echo "tag=$tag" >> "$GITHUB_OUTPUT"

          echo "PR      : #$pr"
          echo "Version : $display"
          echo "Tag     : $tag"

      - name: Synchronize source version
        if: steps.version.outputs.publish == 'true'
        env:
          DISPLAY_VERSION: ${{ steps.version.outputs.display }}
        shell: bash
        run: |
          set -Eeuo pipefail

          python3 - <<'PY'
          import json
          import os
          from datetime import datetime, timezone
          from pathlib import Path

          display = os.environ["DISPLAY_VERSION"]

          stamp = datetime.now(
              timezone.utc
          ).strftime("%Y-%m-%dT%H:%M:%SZ")

          for path in [
              Path("opt/pincabos/config/version.json"),
              Path("opt/pincabos/version.json"),
          ]:
              if not path.exists():
                  continue

              data = json.loads(
                  path.read_text(
                      encoding="utf-8"
                  )
              )

              data["version"] = display

              if "updated_at" in data:
                  data["updated_at"] = (
                      stamp
                      .replace("T", " ")
                      .replace("Z", "")
                  )

              if "generated_at" in data:
                  data["generated_at"] = stamp

              path.write_text(
                  json.dumps(
                      data,
                      indent=2,
                      ensure_ascii=False
                  ) + "\n",
                  encoding="utf-8"
              )
          PY

          git config user.name "PinCabOS Release"
          git config user.email "pincabos@localhost"

          git add \
            opt/pincabos/config/version.json \
            opt/pincabos/version.json

          if ! git diff --cached --quiet; then
            git commit \
              -m "chore(release): ${DISPLAY_VERSION} [skip ci]"

            git push origin HEAD:main
          fi

      - name: Validate sources
        if: steps.version.outputs.publish == 'true'
        shell: bash
        run: |
          set -Eeuo pipefail

          python3 - <<'PY'
          from pathlib import Path

          for path in [
              Path("opt/pincabos/update/pincabos_updates.py"),
              Path("opt/pincabos/update/build_release_v4.py"),
              Path("opt/pincabos/web/pincabos_updates.py"),
              Path("opt/pincabos/web/tools.py"),
              Path("usr/local/sbin/pincabos-update-web-runner"),
          ]:
              compile(
                  path.read_text(
                      encoding="utf-8"
                  ),
                  str(path),
                  "exec"
              )
          PY

          bash -n usr/local/sbin/getpcos
          bash -n usr/local/bin/getpcos

          sudo visudo \
            -cf \
            etc/sudoers.d/pincabos-updates-web

      - name: Build full Release
        if: steps.version.outputs.publish == 'true'
        env:
          VERSION: ${{ steps.version.outputs.tag }}
          DISPLAY_VERSION: ${{ steps.version.outputs.display }}
          CHANNEL: ${{ steps.version.outputs.channel }}
        shell: bash
        run: |
          set -Eeuo pipefail

          rm -rf dist

          GITHUB_SHA="$(git rev-parse HEAD)" \
          python3 \
            opt/pincabos/update/build_release_v4.py \
            --version "$VERSION" \
            --display-version "$DISPLAY_VERSION" \
            --channel "$CHANNEL" \
            --out dist

          cd dist

          sha256sum -c audit.sha256

          echo
          echo "=== RELEASE.JSON ==="
          cat release.json

          echo
          echo "=== FILE COUNT ==="
          wc -l files.list

      - name: Publish GitHub Release
        if: steps.version.outputs.publish == 'true'
        env:
          GH_TOKEN: ${{ github.token }}
          VERSION: ${{ steps.version.outputs.tag }}
          DISPLAY_VERSION: ${{ steps.version.outputs.display }}
          CHANNEL: ${{ steps.version.outputs.channel }}
          PRNUM: ${{ steps.version.outputs.pr }}
        shell: bash
        run: |
          set -Eeuo pipefail

          title="$(
            gh pr view \
              "$PRNUM" \
              --repo "$GITHUB_REPOSITORY" \
              --json title \
              --jq '.title'
          )"

          notes="$(
            printf \
              'PinCabOS %s\n\nRelease automatique apres merge de la PR #%s.\n\n%s\n\nRelease complete des fichiers geres par Updates V4. Validation SHA-256, backup et rollback.' \
              "$DISPLAY_VERSION" \
              "$PRNUM" \
              "$title"
          )"

          extra=()

          if [[ "$CHANNEL" != "stable" ]]; then
            extra+=(--prerelease)
          fi

          if gh release view \
              "$VERSION" \
              --repo "$GITHUB_REPOSITORY" \
              >/dev/null 2>&1
          then
            gh release upload \
              "$VERSION" \
              dist/pincabos-update.tar.zst \
              dist/files.list \
              dist/remove.list \
              dist/release.json \
              dist/audit.sha256 \
              --repo "$GITHUB_REPOSITORY" \
              --clobber
          else
            gh release create \
              "$VERSION" \
              dist/pincabos-update.tar.zst \
              dist/files.list \
              dist/remove.list \
              dist/release.json \
              dist/audit.sha256 \
              --repo "$GITHUB_REPOSITORY" \
              --target "$(git rev-parse HEAD)" \
              --title "PinCabOS $DISPLAY_VERSION" \
              --notes "$notes" \
              "${extra[@]}"
          fi

          echo "GO [OK] Release publiee : $VERSION"
YAML

echo "GO [OK] Workflow automatique configure."
echo

echo "=== 9. NORMALISATION WHITESPACE ==="

chmod u+w \
    etc/sudoers.d/pincabos-updates-web

python3 - <<'PY'
from pathlib import Path

paths = [
    Path(
        ".github/workflows/"
        "pincabos-release-v4.yml"
    ),
    Path(
        "opt/pincabos/update/"
        "pincabos_updates.py"
    ),
    Path(
        "opt/pincabos/update/"
        "build_release_v4.py"
    ),
    Path(
        "opt/pincabos/web/"
        "pincabos_updates.py"
    ),
    Path(
        "opt/pincabos/web/"
        "tools.py"
    ),
    Path(
        "opt/pincabos/web/static/"
        "pincabos-appearance-dashboard-menu-v2.css"
    ),
    Path(
        "usr/local/sbin/"
        "pincabos-update-web-runner"
    ),
    Path(
        "etc/sudoers.d/"
        "pincabos-updates-web"
    ),
]

for path in paths:
    if not path.exists():
        continue

    text = path.read_text(
        encoding="utf-8"
    )

    lines = [
        line.rstrip(
            " \t"
        )
        for line
        in text.splitlines()
    ]

    while (
        lines
        and lines[-1] == ""
    ):
        lines.pop()

    path.write_text(
        "\n".join(lines)
        + "\n",
        encoding="utf-8"
    )

    print(
        f"GO [OK] {path}"
    )
PY

chmod 0440 \
    etc/sudoers.d/pincabos-updates-web

echo

echo "=== 10. VALIDATION AVANT GITHUB ==="

export PYTHONPYCACHEPREFIX="$WORK/final-pycache"

rm -rf \
    "$PYTHONPYCACHEPREFIX"

mkdir -p \
    "$PYTHONPYCACHEPREFIX"

python3 -m py_compile \
    opt/pincabos/update/pincabos_updates.py \
    opt/pincabos/update/build_release_v4.py \
    opt/pincabos/web/pincabos_updates.py \
    opt/pincabos/web/tools.py \
    usr/local/sbin/pincabos-update-web-runner

bash -n \
    usr/local/sbin/getpcos

bash -n \
    usr/local/bin/getpcos

sudo visudo \
    -cf \
    etc/sudoers.d/pincabos-updates-web

git diff --check

grep -q \
    'PINCABOS_FULLWIDTH_GLOBAL_V1_BEGIN' \
    opt/pincabos/web/static/pincabos-appearance-dashboard-menu-v2.css

grep -q \
    'PCOSUpdatePinCabOS.png' \
    opt/pincabos/web/tools.py

grep -q \
    '/tmp/pincabos-update-web-state.json' \
    opt/pincabos/web/pincabos_updates.py

grep -q \
    'pincabos-update-web-runner' \
    opt/pincabos/web/pincabos_updates.py

grep -q \
    'pincabos-update-web-runner' \
    etc/sudoers.d/pincabos-updates-web

if grep -Eq \
    '/bin/bash|/usr/bin/bash|/sbin/reboot' \
    etc/sudoers.d/pincabos-updates-web
then
    echo "NOGO [!!] Sudoers trop permissif."
    fail
fi

echo
echo "--- DIFF FINAL ---"

git status --short

echo
git diff --stat

echo
echo "==============================================================="
echo " GO [OK] PREFLIGHT FINAL COMPLET"
echo " A PARTIR D'ICI GITHUB SERA MODIFIE"
echo "==============================================================="
echo

echo "=== 11. COMMIT + PUSH ==="

git config user.name \
    "PinCabOS Integration"

git config user.email \
    "pincabos@localhost"

git add -A

git diff \
    --cached \
    --check

git commit \
    -m "feat(web): full width and automatic PR releases"

git fetch origin main

[ "$(git rev-parse origin/main)" = "$EXPECTED_MAIN" ] || {
    echo "NOGO [!!] main vient de changer."
    fail
}

git push \
    -u origin \
    "$BRANCH"

echo "GO [OK] Branche poussee."
echo

echo "=== 12. CREATION PR ==="

PR_URL="$(
    gh pr create \
        --repo "$REPO" \
        --base main \
        --head "$BRANCH" \
        --title "PinCabOS Full Width + Updates Auto Release" \
        --body "Full Width global PinCabOS et finalisation Updates V4.

- Full Width via CSS global injecte sur toutes les pages
- page Updates professionnelle
- carte Updates en premiere position
- image PCOSUpdatePinCabOS.png
- boutons Updates via runner root independant du WebApp
- sudoers minimal
- Release complete des fichiers geres
- SHA-256
- backup et rollback
- version Alpha 2.XX = numero de la derniere PR mergee
- GitHub Release automatique apres merge"
)"

PRNUM="$(
    gh pr view \
        "$BRANCH" \
        --repo "$REPO" \
        --json number \
        --jq '.number'
)"

DISPLAY="Alpha 2.${PRNUM}"
TAG="alpha2.${PRNUM}-beta.$(date -u +%Y%m%d).1"

echo "PR      : #$PRNUM"
echo "URL     : $PR_URL"
echo "Version : $DISPLAY"
echo "Tag     : $TAG"
echo

echo "=== 13. VERSION SOURCE = PR #$PRNUM ==="

python3 - "$PRNUM" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

pr = int(
    sys.argv[1]
)

display = (
    f"Alpha 2.{pr}"
)

stamp = datetime.now(
    timezone.utc
).strftime(
    "%Y-%m-%dT%H:%M:%SZ"
)

for path in [
    Path(
        "opt/pincabos/config/version.json"
    ),
    Path(
        "opt/pincabos/version.json"
    ),
]:
    if not path.exists():
        continue

    data = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    data[
        "version"
    ] = display

    if "updated_at" in data:
        data[
            "updated_at"
        ] = (
            stamp
            .replace(
                "T",
                " "
            )
            .replace(
                "Z",
                ""
            )
        )

    if "generated_at" in data:
        data[
            "generated_at"
        ] = stamp

    path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False
        ) + "\n",
        encoding="utf-8"
    )

    print(
        f"GO [OK] "
        f"{path} -> {display}"
    )
PY

git add \
    opt/pincabos/config/version.json \
    opt/pincabos/version.json

git diff \
    --cached \
    --check

git commit \
    -m "chore(version): $DISPLAY"

git push

echo "GO [OK] Version PR synchronisee."
echo

echo "=== 14. BUILD LOCAL DE LA RELEASE COMPLETE ==="

rm -rf "$DIST"

GITHUB_SHA="$(git rev-parse HEAD)" \
python3 \
    opt/pincabos/update/build_release_v4.py \
    --version "$TAG" \
    --display-version "$DISPLAY" \
    --channel beta \
    --out "$DIST"

cd "$DIST"

sha256sum \
    -c audit.sha256

echo
echo "--- RELEASE JSON ---"

cat release.json

echo
echo "--- NOMBRE DE FICHIERS ---"

wc -l files.list

echo

for REQUIRED in \
    opt/pincabos/update/pincabos_updates.py \
    opt/pincabos/update/build_release_v4.py \
    opt/pincabos/web/pincabos_updates.py \
    opt/pincabos/web/tools.py \
    opt/pincabos/web/static/pincabos-appearance-dashboard-menu-v2.css \
    usr/local/sbin/pincabos-update-web-runner \
    etc/sudoers.d/pincabos-updates-web
do
    grep -Fxq \
        "$REQUIRED" \
        files.list || {
            echo "NOGO [!!] Absent : $REQUIRED"
            fail
        }
done

BAD_OWNER="$(
    tar \
        --zstd \
        --numeric-owner \
        -tvf pincabos-update.tar.zst \
        | awk '
            $2 != "0/0" {
                print
                exit
            }
        '
)"

if [ -n "$BAD_OWNER" ]; then
    echo "NOGO [!!] Owner archive incorrect:"
    echo "$BAD_OWNER"
    fail
fi

echo "GO [OK] Archive root:root."
echo "GO [OK] Release locale valide."
echo

cd "$SRC"

echo "=== 15. MERGE PR #$PRNUM ==="

git fetch origin main

[ "$(git rev-parse origin/main)" = "$EXPECTED_MAIN" ] || {
    echo "NOGO [!!] main a change avant merge."
    fail
}

gh pr merge \
    "$PRNUM" \
    --repo "$REPO" \
    --squash \
    --delete-branch

MERGED="$(
    gh pr view \
        "$PRNUM" \
        --repo "$REPO" \
        --json merged \
        --jq '.merged'
)"

[ "$MERGED" = "true" ] || {
    echo "NOGO [!!] PR non mergee."
    fail
}

echo "GO [OK] PR #$PRNUM mergee."
echo "GO [OK] Version = $DISPLAY"
echo

echo "=== 16. DECLENCHEMENT RELEASE ==="

DISPATCH=0

for TRY in $(seq 1 15); do
    if gh workflow run \
        pincabos-release-v4.yml \
        --repo "$REPO" \
        -f pr_number="$PRNUM" \
        -f channel=beta
    then
        DISPATCH=1
        break
    fi

    echo "Workflow pas encore indexe..."
    sleep 5
done

[ "$DISPATCH" = "1" ] || {
    echo "NOGO [!!] Workflow impossible a lancer."
    fail
}

echo "GO [OK] Workflow lance."
echo

echo "=== 17. ATTENTE RELEASE $TAG ==="

FOUND=""

for N in $(seq 1 60); do
    if gh release view \
        "$TAG" \
        --repo "$REPO" \
        >/dev/null 2>&1
    then
        FOUND=1
        break
    fi

    printf "Attente %02d/60\r" "$N"
    sleep 10
done

echo

if [ -z "$FOUND" ]; then
    echo "NOGO [!!] Release non detectee."

    gh run list \
        --repo "$REPO" \
        --workflow pincabos-release-v4.yml \
        --limit 10 || true

    fail
fi

echo "GO [OK] Release detectee."
echo

echo "=== 18. AUDIT ASSETS ==="

gh release view \
    "$TAG" \
    --repo "$REPO" \
    --json tagName,name,isPrerelease,url,assets \
    --jq '
      "Tag       : \(.tagName)",
      "Nom       : \(.name)",
      "Prerelease: \(.isPrerelease)",
      "URL       : \(.url)",
      "Assets:",
      (.assets[].name)
    '

ASSETS="$(
    gh release view \
        "$TAG" \
        --repo "$REPO" \
        --json assets \
        --jq '
          [
            .assets[].name
            | select(
                . == "pincabos-update.tar.zst"
                or . == "files.list"
                or . == "remove.list"
                or . == "release.json"
                or . == "audit.sha256"
            )
          ]
          | length
        '
)"

[ "$ASSETS" = "5" ] || {
    echo "NOGO [!!] Assets incomplets."
    fail
}

echo "GO [OK] Les 5 assets sont presents."
echo

echo "=== 19. CHECK CAB AVANT UPDATE ==="

sudo /usr/local/sbin/getpcos check

echo
echo "=== 20. UPDATE REEL ==="

sudo /usr/local/sbin/getpcos update

echo
echo "=== 21. STATUS APRES UPDATE ==="

sudo /usr/local/sbin/getpcos status

echo

sudo python3 - "$TAG" "$DISPLAY" <<'PY'
import json
import sys
from pathlib import Path

tag = sys.argv[1]
display = sys.argv[2]

state = json.loads(
    Path(
        "/var/lib/pincabos/"
        "updates/state.json"
    ).read_text(
        encoding="utf-8"
    )
)

print(
    "installed_version:",
    state.get(
        "installed_version"
    )
)

if (
    state.get(
        "installed_version"
    )
    != tag
):
    raise SystemExit(
        "NOGO [!!] "
        "installed_version incorrect."
    )

for path in [
    Path(
        "/opt/pincabos/config/"
        "version.json"
    ),
    Path(
        "/opt/pincabos/version.json"
    ),
]:
    if not path.exists():
        continue

    data = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    print(
        f"{path}: "
        f"{data.get('version')}"
    )

    if (
        data.get(
            "version"
        )
        != display
    ):
        raise SystemExit(
            f"NOGO [!!] "
            f"Version incorrecte: {path}"
        )

print(
    "GO [OK] "
    "Version Alpha synchronisee."
)
PY

echo

echo "=== 22. SERVICES ==="

for SERVICE in \
    pincabos-webapp.service \
    pincabos-vpinfe.service
do
    VALUE="$(
        systemctl \
            is-active \
            "$SERVICE" \
            2>/dev/null || true
    )"

    echo "$SERVICE : $VALUE"

    [ "$VALUE" = "active" ] || {
        echo "NOGO [!!] Service non actif."
        fail
    }
done

echo "GO [OK] Services actifs."
echo

echo "=== 23. FULL WIDTH LIVE ==="

curl -sS \
    http://127.0.0.1/static/pincabos-appearance-dashboard-menu-v2.css \
    -o "$WORK/fullwidth-live.css"

grep -q \
    'PINCABOS_FULLWIDTH_GLOBAL_V1_BEGIN' \
    "$WORK/fullwidth-live.css"

TOOLS_HTTP="$(
    curl \
        -sS \
        -o "$WORK/tools-live.html" \
        -w '%{http_code}' \
        http://127.0.0.1/tools
)"

UPDATES_HTTP="$(
    curl \
        -sS \
        -o "$WORK/updates-live.html" \
        -w '%{http_code}' \
        http://127.0.0.1/tools/updates
)"

echo "/tools         : HTTP $TOOLS_HTTP"
echo "/tools/updates : HTTP $UPDATES_HTTP"

[ "$TOOLS_HTTP" = "200" ] || fail
[ "$UPDATES_HTTP" = "200" ] || fail

echo "GO [OK] Full Width global charge."
echo

echo "=== 24. TEST BOUTON VERIFIER ==="

curl \
    -sS \
    -X POST \
    -H 'Content-Type: application/json' \
    -d '{"action":"check","reboot_after":false}' \
    http://127.0.0.1/api/updates/run

echo

STATE=""

for N in $(seq 1 30); do
    sleep 1

    STATE="$(
        curl \
            -sS \
            http://127.0.0.1/api/updates/state
    )"

    RUNNING="$(
        printf '%s' "$STATE" \
        | python3 -c '
import json
import sys
d=json.load(sys.stdin)
print(
    "1"
    if d.get("running")
    else "0"
)
'
    )"

    [ "$RUNNING" = "0" ] && break
done

printf '%s\n' "$STATE" \
    | python3 -m json.tool

echo
echo "--- LOG CHECK ---"

cat \
    /tmp/pincabos-update-web.log \
    || true

echo

STATUS="$(
    printf '%s' "$STATE" \
    | python3 -c '
import json
import sys
print(
    json.load(sys.stdin)
    .get("status","")
)
'
)"

[ "$STATUS" = "success" ] || {
    echo "NOGO [!!] Bouton Verifier en echec."
    fail
}

echo "GO [OK] Bouton Verifier fonctionne."
echo

echo "=== 25. TEST BOUTON INSTALLER ==="

curl \
    -sS \
    -X POST \
    -H 'Content-Type: application/json' \
    -d '{"action":"update","reboot_after":false}' \
    http://127.0.0.1/api/updates/run

echo

STATE=""

for N in $(seq 1 30); do
    sleep 1

    STATE="$(
        curl \
            -sS \
            http://127.0.0.1/api/updates/state
    )"

    RUNNING="$(
        printf '%s' "$STATE" \
        | python3 -c '
import json
import sys
d=json.load(sys.stdin)
print(
    "1"
    if d.get("running")
    else "0"
)
'
    )"

    [ "$RUNNING" = "0" ] && break
done

printf '%s\n' "$STATE" \
    | python3 -m json.tool

echo
echo "--- LOG UPDATE ---"

cat \
    /tmp/pincabos-update-web.log \
    || true

echo

STATUS="$(
    printf '%s' "$STATE" \
    | python3 -c '
import json
import sys
print(
    json.load(sys.stdin)
    .get("status","")
)
'
)"

[ "$STATUS" = "success" ] || {
    echo "NOGO [!!] Bouton Installer en echec."
    fail
}

grep -q \
    'Already up to date' \
    /tmp/pincabos-update-web.log || {
        echo "NOGO [!!] Already up to date absent."
        fail
    }

echo "GO [OK] Bouton Installer fonctionne."
echo

echo "==============================================================="
echo " GO [OK] PINCABOS UPDATES FINALISE"
echo "==============================================================="
echo
echo "PR               : #$PRNUM"
echo "Version          : $DISPLAY"
echo "Release          : $TAG"
echo "Full Width       : OK"
echo "Release complete : OK"
echo "Auto version PR  : OK"
echo "Runner Web       : OK"
echo "Check Web        : OK"
echo "Install Web      : OK"
echo "Reboot           : NON"
echo
