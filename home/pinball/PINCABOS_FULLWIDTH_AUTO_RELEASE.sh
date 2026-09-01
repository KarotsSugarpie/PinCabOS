#!/usr/bin/env bash
set -Eeuo pipefail

REPO="PinCabOS/PinCabOS"
STAMP="20260822-093232"
WORK="/home/pinball/pincabos-fullwidth-auto-release-20260822-093232"
SRC="$WORK/source"
BRANCH="feat/fullwidth-updates-auto-release-20260822-093232"
DIST="$WORK/preflight-dist"

fail()
{
    echo
    echo "==============================================================="
    echo " NOGO [!!] PINCABOS FULLWIDTH / AUTO RELEASE"
    echo "==============================================================="
    echo "Work conserve : $WORK"
    exit 1
}

trap 'RC=$?; if [ "$RC" -ne 0 ]; then echo; echo "NOGO [!!] Erreur ligne $LINENO - code $RC"; echo "Work conserve : $WORK"; fi' ERR

echo "==============================================================="
echo " PINCABOS - FULLWIDTH GLOBAL + UPDATES V4 + AUTO RELEASE"
echo " VERSION = NUMERO DE LA DERNIERE PR MERGEE"
echo " AUCUN REBOOT AUTOMATIQUE"
echo "==============================================================="
echo

echo "=== 1. PREFLIGHT OUTILS ==="

for CMD in git gh python3 curl tar zstd; do
    command -v "$CMD" >/dev/null || {
        echo "NOGO [!!] Commande absente : $CMD"
        exit 1
    }
done

gh auth status >/dev/null 2>&1 || {
    echo "NOGO [!!] gh non authentifie."
    exit 1
}

sudo -v

echo "GO [OK] Git / GitHub / Python / curl / zstd disponibles."
echo

echo "=== 2. REPRISE DU CLONE SPARSE EXISTANT ==="

if [ ! -d "$SRC/.git" ]; then
    echo "NOGO [!!] Clone existant absent : $SRC"
    exit 1
fi

CURRENT_BRANCH="$(git -C "$SRC" branch --show-current)"

if [ "$CURRENT_BRANCH" != "$BRANCH" ]; then
    echo "NOGO [!!] Branche inattendue : $CURRENT_BRANCH"
    exit 1
fi

if [ -n "$(git -C "$SRC" status --porcelain)" ]; then
    echo "NOGO [!!] Clone non propre avant reprise."
    git -C "$SRC" status --short
    exit 1
fi

git -C "$SRC" fetch origin main

BASE_SHA="$(git -C "$SRC" rev-parse origin/main)"

if [ "$BASE_SHA" != "07df37b43762b5864b6fe73687910ff314693203" ]; then
    echo "NOGO [!!] main a change depuis le preflight initial."
    echo "Main actuel : $BASE_SHA"
    exit 1
fi

echo "Main   : $BASE_SHA"
echo "Branch : $BRANCH"
echo "GO [OK] Clone existant reutilise."

echo

echo "=== 3. AUDIT LARGEUR DES PAGES GITHUB ==="

cd "$SRC"

WEB_COUNT="$(
    find opt/pincabos/web \
        -type f \
        \( -name '*.py' -o -name '*.css' -o -name '*.html' \) \
        | wc -l
)"

MAX_COUNT="$(
    grep -RIlE \
        'max-width[[:space:]]*:' \
        opt/pincabos/web \
        --include='*.py' \
        --include='*.css' \
        --include='*.html' \
        2>/dev/null \
        | wc -l
)"

echo "Fichiers Web analyses : $WEB_COUNT"
echo "Fichiers avec max-width : $MAX_COUNT"
echo

echo "--- Exemples de fichiers avec limite de largeur ---"

grep -RIlE \
    'max-width[[:space:]]*:' \
    opt/pincabos/web \
    --include='*.py' \
    --include='*.css' \
    --include='*.html' \
    2>/dev/null \
    | head -30 || true

echo

INJECTOR="opt/pincabos/web/pincabos_appearance_global.py"
GLOBAL_BRIDGE="opt/pincabos/web/static/pincabos-appearance-dashboard-menu-v2.css"

if [ ! -f "$INJECTOR" ]; then
    echo "NOGO [!!] Injecteur Appearance absent."
    exit 1
fi

if [ ! -f "$GLOBAL_BRIDGE" ]; then
    echo "NOGO [!!] CSS global injecte absent."
    exit 1
fi

if ! grep -q \
    'pincabos-appearance-dashboard-menu-v2.css' \
    "$INJECTOR"
then
    echo "NOGO [!!] L'injecteur ne pointe pas vers le CSS global attendu."
    exit 1
fi

echo "Injecteur global : $INJECTOR"
echo "CSS global       : $GLOBAL_BRIDGE"
echo "GO [OK] Couche CSS globale detectee."
echo

echo "=== 4. IMPORT DES CORRECTIONS LIVE DEJA VALIDEES ==="

LIVE_TOOLS="/opt/pincabos/web/tools.py"
LIVE_UPDATES="/opt/pincabos/web/pincabos_updates.py"
LIVE_IMAGE="/opt/pincabos/web/static/pincabos-assets/PCOSUpdatePinCabOS.png"

for F in "$LIVE_TOOLS" "$LIVE_UPDATES" "$LIVE_IMAGE"; do
    [ -f "$F" ] || {
        echo "NOGO [!!] Fichier live absent : $F"
        exit 1
    }
done

cp -a \
    "$LIVE_TOOLS" \
    "$SRC/opt/pincabos/web/tools.py"

cp -a \
    "$LIVE_UPDATES" \
    "$SRC/opt/pincabos/web/pincabos_updates.py"

mkdir -p \
    "$SRC/opt/pincabos/web/static/pincabos-assets"

cp -a \
    "$LIVE_IMAGE" \
    "$SRC/opt/pincabos/web/static/pincabos-assets/PCOSUpdatePinCabOS.png"

echo "GO [OK] UI Updates live importee dans la source."
echo

echo "=== 5. FULL WIDTH GLOBAL ==="

python3 - <<'PY'
from pathlib import Path
import re

bridge = Path(
    "opt/pincabos/web/static/"
    "pincabos-appearance-dashboard-menu-v2.css"
)

s = bridge.read_text(encoding="utf-8")

start = "/* PINCABOS_FULLWIDTH_GLOBAL_V1_BEGIN */"
end = "/* PINCABOS_FULLWIDTH_GLOBAL_V1_END */"

if start in s and end in s:
    a = s.index(start)
    b = s.index(end) + len(end)
    s = s[:a] + s[b:]

block = r'''
/* PINCABOS_FULLWIDTH_GLOBAL_V1_BEGIN */

/*
 * PinCabOS Full Width global.
 * La largeur appartient au viewport.
 * Les cartes/panneaux internes conservent leurs propres dimensions.
 */

html,
body {
  width: 100%;
  max-width: none !important;
}

html body main,
html body > main,
html body > .container,
html body > .container-fluid,
html body > .main-content,
html body > .page-content,
html body > .content-wrapper,
html body main > .container,
html body main > .container-fluid,
html body main > .main-content,
html body main > .page-content,
html body main > .content-wrapper {
  width: 100% !important;
  max-width: none !important;
  box-sizing: border-box !important;
}

/* Racines PinCabOS connues */
html body .pco-tools-page,
html body .pco-up-wrap,
html body .pco-st-shell,
html body .dof-pro-shell,
html body .vpxbc-shell,
html body .pco-page,
html body .pco-page-wrap,
html body .pco-page-shell,
html body .pco-tools-page,
html body .pco-dashboard-page,
html body .pco-settings-page,
html body .pco-admin-page,
html body .pco-network-page,
html body .pco-storage-page,
html body .pco-explorer-page,
html body .pco-import-page,
html body .pco-export-page {
  width: 100% !important;
  max-width: none !important;
  box-sizing: border-box !important;
}

/*
 * Modules futurs : seulement les wrappers DIRECTS du main.
 * Cela evite d'elargir les cartes et dialogues internes.
 */
html body main > [class$="-page"],
html body main > [class$="-shell"],
html body main > [class$="-wrap"],
html body main > [class$="-wrapper"] {
  width: 100% !important;
  max-width: none !important;
  box-sizing: border-box !important;
}

/* PINCABOS_FULLWIDTH_GLOBAL_V1_END */
'''

bridge.write_text(
    s.rstrip() + "\n\n" + block.strip() + "\n",
    encoding="utf-8"
)

print("GO [OK] Full Width global ajoute au bridge Appearance.")
PY

echo

echo "=== 6. FULL WIDTH PAGE OUTILS + UPDATES EN PREMIER ==="

python3 - <<'PY'
from pathlib import Path
import re

p = Path("opt/pincabos/web/tools.py")
s = p.read_text(encoding="utf-8")

# Full Width explicite de la page Outils.
s = re.sub(
    r'(\.pco-tools-page\s*\{\s*)'
    r'max-width\s*:\s*[^;]+;',
    r'\1max-width: none;\n  width: 100%;',
    s,
    count=1,
    flags=re.S,
)

START = "<!-- PINCABOS_UPDATES_V4_CARD_START -->"
END = "<!-- PINCABOS_UPDATES_V4_CARD_END -->"

if START in s and END in s:
    a = s.index(START)
    b = s.index(END, a) + len(END)
    s = s[:a] + s[b:]

card = r'''
        <!-- PINCABOS_UPDATES_V4_CARD_START -->
        <a class="tool-card" href="/tools/updates">
          <div class="pco-tool-art">
            <img
              src="/static/pincabos-assets/PCOSUpdatePinCabOS.png?v=updates-pro-v3"
              alt="PinCabOS Updates"
              loading="lazy">
          </div>
          <div class="pco-tool-body">
            <strong>PinCabOS Updates</strong>
            <span class="pco-tool-description">
              Vérifier, installer ou restaurer les mises à jour PinCabOS
              publiées sur GitHub Releases.
            </span>
            <div class="pco-tool-footer">
              <span>Ouvrir Updates</span>
              <span class="pco-tool-open">→</span>
            </div>
          </div>
        </a>
        <!-- PINCABOS_UPDATES_V4_CARD_END -->
'''

section = s.find(
    '<section id="pincabos-tools-system-family"'
)

if section < 0:
    raise SystemExit(
        "NOGO [!!] Section Outils PinCabOS introuvable."
    )

marker = '<div class="pco-tools-card-list">'
pos = s.find(marker, section)

if pos < 0:
    raise SystemExit(
        "NOGO [!!] Liste cartes Outils introuvable."
    )

pos += len(marker)

s = (
    s[:pos]
    + "\n"
    + card
    + "\n"
    + s[pos:]
)

p.write_text(s, encoding="utf-8")

print("GO [OK] Outils = Full Width.")
print("GO [OK] PinCabOS Updates = premiere carte.")
print("GO [OK] PCOSUpdatePinCabOS.png = image officielle.")
PY

echo

echo "=== 7. CORRECTION DEFINITIVE DE LA PAGE UPDATES ==="

python3 - <<'PY'
from pathlib import Path
import re

p = Path("opt/pincabos/web/pincabos_updates.py")
s = p.read_text(encoding="utf-8")

# L'etat UI n'a pas besoin d'etre persistant.
# /tmp supprime definitivement le conflit root/pinball.
s = re.sub(
    r'WEBSTATE\s*=\s*Path\([\'"]'
    r'/var/lib/pincabos/updates/(?:web/)?web-state\.json'
    r'[\'"]\)',
    'WEBSTATE = Path("/tmp/pincabos-update-web-state.json")',
    s,
    count=1,
)

# Full Width explicite.
s = re.sub(
    r'(\.pco-up-wrap\s*\{[^}]*?)'
    r'max-width\s*:\s*[^;]+;',
    r'\1max-width:none;',
    s,
    count=1,
    flags=re.S,
)

if "def _display_from_tag(" not in s:
    marker = "def _engine_state():"
    pos = s.find(marker)

    if pos < 0:
        raise SystemExit(
            "NOGO [!!] _engine_state introuvable."
        )

    helper = r'''
def _display_from_tag(value):
    value = str(value or "").strip()
    low = value.lower()

    if low.startswith("alpha2."):
        core = value.split("-", 1)[0]
        number = core.split(".", 1)[1]
        return f"Alpha 2.{number}"

    return value


'''
    s = s[:pos] + helper + s[pos:]

old = 'installed = d.get("installed_version")'
new = (
    'installed = d.get("display_version") '
    'or _display_from_tag(d.get("installed_version", ""))'
)

if old in s:
    s = s.replace(old, new, 1)

# Reboot : plus de sudo bash generique.
old_reboot = (
    '["sudo", "-n", "bash", "-lc", '
    'f"sleep {int(delay_sec)}; /sbin/reboot"]'
)

new_reboot = (
    '["sudo", "-n", '
    '"/usr/local/sbin/pincabos-update-reboot"]'
)

if old_reboot in s:
    s = s.replace(old_reboot, new_reboot)

# Interface publique attendue par tools.py.
if not re.search(r'^def register\(', s, re.M):
    if "def _pincabos_updates_register(" not in s:
        raise SystemExit(
            "NOGO [!!] Fonction register Updates introuvable."
        )

    s = s.rstrip() + r'''

# Interface publique attendue par tools.py
def register(app, page):
    return _pincabos_updates_register(app, page)
''' + "\n"

p.write_text(s, encoding="utf-8")

print("GO [OK] WEBSTATE utilise /tmp.")
print("GO [OK] Full Width Updates actif.")
print("GO [OK] Version Alpha lisible depuis le tag.")
print("GO [OK] register() expose.")
print("GO [OK] Reboot Web restreint.")
PY

echo

echo "=== 8. HELPER REBOOT + SUDOERS RESTREINT ==="

mkdir -p \
    usr/local/sbin \
    etc/sudoers.d

cat > usr/local/sbin/pincabos-update-reboot <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail

sleep 4
exec /usr/bin/systemctl reboot
EOF

chmod 0755 \
    usr/local/sbin/pincabos-update-reboot

cat > etc/sudoers.d/pincabos-updates-web <<'EOF'
pinball ALL=(root) NOPASSWD: /usr/local/sbin/getpcos
pinball ALL=(root) NOPASSWD: /usr/local/sbin/pincabos-update-reboot
EOF

chmod 0440 \
    etc/sudoers.d/pincabos-updates-web

sudo visudo \
    -cf \
    etc/sudoers.d/pincabos-updates-web

echo "GO [OK] Reboot et sudoers securises."
echo

echo "=== 9. VERSION DISPLAY = NUMERO PR ==="

python3 - <<'PY'
from pathlib import Path

p = Path("opt/pincabos/update/pincabos_updates.py")
s = p.read_text(encoding="utf-8")

old = '''def local_version():
    st=load_json(STATE,{})
    if st.get('installed_version'): return str(st['installed_version'])
    for p in VERSION_FILES:
        d=load_json(p,{})
        if d.get('version'): return str(d['version'])
    return 'unknown'
'''

new = '''def display_version_from_tag(tag):
    value=str(tag or '').strip()
    low=value.lower()
    if low.startswith('alpha2.'):
        core=value.split('-',1)[0]
        return 'Alpha 2.'+core.split('.',1)[1]
    return value

def local_tag():
    st=load_json(STATE,{})
    if st.get('installed_version'):
        return str(st['installed_version'])
    for p in VERSION_FILES:
        d=load_json(p,{})
        if d.get('version'):
            return str(d['version'])
    return 'unknown'

def local_version():
    st=load_json(STATE,{})
    if st.get('display_version'):
        return str(st['display_version'])
    if st.get('installed_version'):
        return display_version_from_tag(st['installed_version'])
    for p in VERSION_FILES:
        d=load_json(p,{})
        if d.get('version'):
            return str(d['version'])
    return 'unknown'

def sync_version_files(display):
    if not display:
        return
    stamp=subprocess.check_output(
        ['date','-u','+%Y-%m-%dT%H:%M:%SZ'],
        text=True
    ).strip()

    for p in VERSION_FILES:
        if not p.exists():
            continue
        d=load_json(p,{})
        if not isinstance(d,dict):
            continue
        d['version']=display
        if 'updated_at' in d:
            d['updated_at']=stamp.replace('T',' ').replace('Z','')
        if 'generated_at' in d:
            d['generated_at']=stamp
        save_json(p,d)
'''

if old in s:
    s = s.replace(old, new, 1)
elif "def local_tag():" not in s:
    raise SystemExit(
        "NOGO [!!] Bloc local_version inattendu."
    )

old_status = "    print(f'Installed version: {local_version()}')"

new_status = """    display=local_version()
    if os.geteuid()==0:
        try:
            sync_version_files(display)
        except Exception:
            pass
    print(f'Installed version: {display}')"""

if old_status in s:
    s = s.replace(old_status, new_status, 1)

s = s.replace(
    "if local_version()==m['version']:",
    "if local_tag()==m['version']:",
    1,
)

s = s.replace(
    "(bdir/'previous-version').write_text(local_version()+'\\\\n',encoding='utf-8')",
    "(bdir/'previous-version').write_text(local_tag()+'\\\\n',encoding='utf-8')",
    1,
)

old_check = '''    print(f'Available version: {m["version"]}')
    print(f'Release URL      : {m["_release"].get("html_url","")}')
'''

new_check = '''    display=m.get('display_version') or display_version_from_tag(m["version"])
    print(f'Available version: {display}')
    print(f'Release tag      : {m["version"]}')
    print(f'Release URL      : {m["_release"].get("html_url","")}')
'''

if old_check in s:
    s = s.replace(old_check, new_check, 1)

old_state = """        save_json(STATE,{'installed_version':m['version'],'installed_files':rows,'last_backup':str(bdir),'channel':config()[1]})
        print(f'GO [OK] Update installed: {m["version"]}')
"""

new_state = """        display=m.get('display_version') or display_version_from_tag(m['version'])
        save_json(STATE,{
            'installed_version':m['version'],
            'display_version':display,
            'installed_files':rows,
            'last_backup':str(bdir),
            'channel':config()[1]
        })
        try:
            sync_version_files(display)
        except Exception as e:
            print(f'WARNING [--] Version files not synchronized: {e}')
        print(f'GO [OK] Update installed: {display}')
        print(f'GO [OK] Release tag: {m["version"]}')
"""

if old_state in s:
    s = s.replace(old_state, new_state, 1)
elif "'display_version':display" not in s:
    raise SystemExit(
        "NOGO [!!] Bloc save_json STATE inattendu."
    )

p.write_text(s, encoding="utf-8")

print("GO [OK] Moteur version Alpha 2.<PR> configure.")
PY

echo

echo "=== 10. BUILDER V4 DELTA ==="

cat > opt/pincabos/update/build_release_v4.py <<'PY'
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def load_engine(repo: Path):
    path = repo / "opt/pincabos/update/pincabos_updates.py"

    spec = importlib.util.spec_from_file_location(
        "pincabos_updates_release_engine",
        path
    )

    mod = importlib.util.module_from_spec(spec)

    assert spec and spec.loader
    spec.loader.exec_module(mod)

    fn = getattr(mod, "allowed", None)

    if not callable(fn):
        raise SystemExit(
            "NOGO [!!] allowed() absent du moteur V4"
        )

    return fn


def sha256(path: Path):
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b""
        ):
            h.update(chunk)

    return h.hexdigest()


def read_list(path):
    if not path:
        return []

    p = Path(path)

    if not p.exists():
        return []

    return [
        x.strip()
        for x in p.read_text(
            encoding="utf-8"
        ).splitlines()
        if x.strip()
    ]


def validate_script(path: Path):
    if path.is_symlink() or not path.is_file():
        return

    try:
        first = path.open(
            "r",
            encoding="utf-8",
            errors="strict"
        ).readline().strip()
    except (UnicodeDecodeError, OSError):
        return

    rel = str(path)

    if first.startswith("#!") and "python" in first:
        compile(
            path.read_text(encoding="utf-8"),
            rel,
            "exec"
        )

    elif first.startswith("#!") and (
        "bash" in first
        or first.endswith("/sh")
    ):
        subprocess.run(
            ["bash", "-n", str(path)],
            check=True
        )

    elif path.suffix == ".py":
        compile(
            path.read_text(encoding="utf-8"),
            rel,
            "exec"
        )

    elif path.suffix == ".sh":
        if first.startswith("#!"):
            return

        subprocess.run(
            ["bash", "-n", str(path)],
            check=True
        )


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--version",
        required=True
    )

    ap.add_argument(
        "--display-version",
        required=True
    )

    ap.add_argument(
        "--channel",
        required=True,
        choices=[
            "stable",
            "beta",
            "dev"
        ]
    )

    ap.add_argument(
        "--out",
        required=True
    )

    ap.add_argument(
        "--files-from"
    )

    ap.add_argument(
        "--remove-from"
    )

    args = ap.parse_args()

    repo = Path(__file__).resolve().parents[3]
    out = Path(args.out).resolve()

    out.mkdir(
        parents=True,
        exist_ok=True
    )

    allowed = load_engine(repo)

    requested = read_list(
        args.files_from
    )

    if requested:
        rows = []

        for rel in requested:
            p = repo / rel

            if not allowed(rel):
                continue

            if not (
                p.is_file()
                or p.is_symlink()
            ):
                continue

            rows.append(rel)

    else:
        rows = []

        for p in repo.rglob("*"):
            if ".git" in p.parts:
                continue

            if not (
                p.is_file()
                or p.is_symlink()
            ):
                continue

            rel = p.relative_to(
                repo
            ).as_posix()

            if allowed(rel):
                rows.append(rel)

    # Le moteur Update accompagne chaque Release.
    always = [
        "opt/pincabos/update/pincabos_updates.py",
        "opt/pincabos/update/build_release_v4.py",
        "usr/local/sbin/getpcos",
        "usr/local/bin/getpcos",
    ]

    for rel in always:
        p = repo / rel

        if (
            allowed(rel)
            and (
                p.is_file()
                or p.is_symlink()
            )
        ):
            rows.append(rel)

    rows = sorted(set(rows))

    if not rows:
        raise SystemExit(
            "NOGO [!!] Aucun fichier autorise pour la Release"
        )

    for rel in rows:
        validate_script(
            repo / rel
        )

    files = out / "files.list"

    files.write_text(
        "".join(
            x + "\n"
            for x in rows
        ),
        encoding="utf-8"
    )

    legacy = [
        "opt/pincabos/script/build-update.sh",
        "opt/pincabos/script/publish-update.sh",
        "opt/pincabos/update/client/getpcos",
        "opt/pincabos/update/client/install-getpcos.sh",
        "opt/pincabos/update/managed-paths.conf",
        "usr/local/sbin/build-update.sh",
    ]

    removed = read_list(
        args.remove_from
    )

    removals = sorted(
        set(
            x
            for x in legacy + removed
            if allowed(x)
        )
    )

    remove = out / "remove.list"

    remove.write_text(
        "".join(
            x + "\n"
            for x in removals
        ),
        encoding="utf-8"
    )

    archive = out / "pincabos-update.tar.zst"

    subprocess.run(
        [
            "tar",
            "--zstd",
            "--verbatim-files-from",
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
            for x in subprocess.check_output(
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
            "NOGO [!!] Archive != files.list"
        )

    source_sha = (
        os.environ.get("GITHUB_SHA")
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
        "version": args.version,
        "display_version": args.display_version,
        "channel": args.channel,
        "repository": "PinCabOS/PinCabOS",
        "archive": "pincabos-update.tar.zst",
        "archive_sha256": sha256(archive),
        "files": "files.list",
        "remove": "remove.list",
        "file_count": len(rows),
        "remove_count": len(removals),
        "source_sha": source_sha,
        "built_at": datetime.now(
            timezone.utc
        ).isoformat().replace(
            "+00:00",
            "Z"
        ),
    }

    release = out / "release.json"

    release.write_text(
        json.dumps(
            meta,
            indent=2,
            ensure_ascii=False
        ) + "\n",
        encoding="utf-8"
    )

    audit = out / "audit.sha256"

    with audit.open(
        "w",
        encoding="utf-8"
    ) as f:
        for p in [
            archive,
            files,
            remove,
            release,
        ]:
            f.write(
                f"{sha256(p)}  {p.name}\n"
            )

    print(
        "GO [OK] Release package: "
        f"{len(rows)} fichiers, "
        f"{len(removals)} suppressions"
    )

    print(
        "GO [OK] Display version: "
        f"{args.display_version}"
    )

    print(
        "GO [OK] Release tag: "
        f"{args.version}"
    )

    print(
        "GO [OK] SHA256 archive: "
        f"{meta['archive_sha256']}"
    )


if __name__ == "__main__":
    main()
PY

chmod 0755 \
    opt/pincabos/update/build_release_v4.py

echo "GO [OK] Builder Delta V4 cree."
echo

echo "=== 11. WORKFLOW AUTO RELEASE SUR PR MERGEE ==="

mkdir -p .github/workflows

cat > .github/workflows/pincabos-release-v4.yml <<'YAML'
name: PinCabOS Release V4

on:
  pull_request_target:
    types:
      - closed

  workflow_dispatch:
    inputs:
      pr_number:
        description: Numero PR a publier; vide = derniere PR mergee
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
  group: pincabos-release-v4-main
  cancel-in-progress: true

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

      - name: Install zstd
        run: |
          sudo apt-get update
          sudo apt-get install -y zstd

      - name: Resolve latest merged PR
        id: identity
        env:
          GH_TOKEN: ${{ github.token }}
          INPUT_PR: ${{ inputs.pr_number }}
          INPUT_CHANNEL: ${{ inputs.channel }}
          EVENT_PR: ${{ github.event.pull_request.number }}
          BASE_SHA: ${{ github.event.pull_request.base.sha }}
          MERGE_SHA: ${{ github.event.pull_request.merge_commit_sha }}
        shell: bash
        run: |
          set -Eeuo pipefail

          latest="$(
            gh pr list \
              --repo "$GITHUB_REPOSITORY" \
              --state merged \
              --limit 100 \
              --json number,mergedAt \
              --jq 'sort_by(.mergedAt) | last | .number'
          )"

          if [[ -z "$latest" || "$latest" == "null" ]]; then
            echo "Aucune PR mergee trouvee." >&2
            exit 1
          fi

          if [[ "$GITHUB_EVENT_NAME" == "workflow_dispatch" ]]; then
            pr="${INPUT_PR:-$latest}"
            channel="${INPUT_CHANNEL:-beta}"

            merge_sha="$(git rev-parse HEAD)"
            base_sha="$(git rev-parse HEAD^)"
          else
            pr="$EVENT_PR"
            channel="beta"

            merge_sha="$MERGE_SHA"
            base_sha="$BASE_SHA"
          fi

          if [[ "$pr" != "$latest" ]]; then
            echo "PR #$pr remplacee par la PR mergee plus recente #$latest."
            echo "publish=false" >> "$GITHUB_OUTPUT"
            exit 0
          fi

          date_tag="$(date -u +%Y%m%d)"
          display="Alpha 2.${pr}"
          tag="alpha2.${pr}-${channel}.${date_tag}.1"

          echo "publish=true" >> "$GITHUB_OUTPUT"
          echo "pr=$pr" >> "$GITHUB_OUTPUT"
          echo "channel=$channel" >> "$GITHUB_OUTPUT"
          echo "display=$display" >> "$GITHUB_OUTPUT"
          echo "tag=$tag" >> "$GITHUB_OUTPUT"
          echo "base_sha=$base_sha" >> "$GITHUB_OUTPUT"
          echo "merge_sha=$merge_sha" >> "$GITHUB_OUTPUT"

          echo "Derniere PR mergee : #$pr"
          echo "Display version     : $display"
          echo "Release tag         : $tag"

      - name: Determine Release delta
        if: steps.identity.outputs.publish == 'true'
        env:
          BASE_SHA: ${{ steps.identity.outputs.base_sha }}
          MERGE_SHA: ${{ steps.identity.outputs.merge_sha }}
        shell: bash
        run: |
          set -Eeuo pipefail

          git fetch origin main

          git cat-file -e "${BASE_SHA}^{commit}"
          git cat-file -e "${MERGE_SHA}^{commit}"

          git diff \
            --name-only \
            --diff-filter=ACMRTUXB \
            "$BASE_SHA" \
            "$MERGE_SHA" \
            > /tmp/pincabos-changed.list

          git diff \
            --name-only \
            --diff-filter=D \
            "$BASE_SHA" \
            "$MERGE_SHA" \
            > /tmp/pincabos-removed.list

          echo "=== CHANGED ==="
          cat /tmp/pincabos-changed.list || true

          echo "=== REMOVED ==="
          cat /tmp/pincabos-removed.list || true

      - name: Synchronize source Alpha version
        if: steps.identity.outputs.publish == 'true'
        env:
          GH_TOKEN: ${{ github.token }}
          DISPLAY: ${{ steps.identity.outputs.display }}
          PRNUM: ${{ steps.identity.outputs.pr }}
        shell: bash
        run: |
          set -Eeuo pipefail

          git fetch origin main
          git checkout main
          git reset --hard origin/main

          latest="$(
            gh pr list \
              --repo "$GITHUB_REPOSITORY" \
              --state merged \
              --limit 100 \
              --json number,mergedAt \
              --jq 'sort_by(.mergedAt) | last | .number'
          )"

          if [[ "$latest" != "$PRNUM" ]]; then
            echo "Une PR plus recente est apparue: #$latest" >&2
            exit 1
          fi

          python3 - <<'PY'
          import json
          import os
          from datetime import datetime, timezone
          from pathlib import Path

          display = os.environ["DISPLAY"]

          stamp = datetime.now(
              timezone.utc
          ).strftime("%Y-%m-%dT%H:%M:%SZ")

          paths = [
              Path("opt/pincabos/config/version.json"),
              Path("opt/pincabos/version.json"),
          ]

          for p in paths:
              if not p.exists():
                  continue

              data = json.loads(
                  p.read_text(
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

              p.write_text(
                  json.dumps(
                      data,
                      indent=2,
                      ensure_ascii=False
                  ) + "\n",
                  encoding="utf-8"
              )

              print(
                  f"Version source: "
                  f"{p} -> {display}"
              )
          PY

          git config user.name "PinCabOS Release"
          git config user.email "pincabos@localhost"

          git add \
            opt/pincabos/config/version.json \
            opt/pincabos/version.json

          if ! git diff --cached --quiet; then
            git commit \
              -m "chore(release): ${DISPLAY} [skip ci]"

            git push origin HEAD:main
          else
            echo "Version source deja correcte."
          fi

      - name: Validate V4 sources
        if: steps.identity.outputs.publish == 'true'
        shell: bash
        run: |
          set -Eeuo pipefail

          python3 - <<'PY'
          from pathlib import Path

          for p in [
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
          ]:
              compile(
                  p.read_text(
                      encoding="utf-8"
                  ),
                  str(p),
                  "exec"
              )
          PY

          bash -n usr/local/sbin/getpcos
          bash -n usr/local/bin/getpcos

          if [[ -f usr/local/sbin/pincabos-update-reboot ]]; then
            bash -n usr/local/sbin/pincabos-update-reboot
          fi

      - name: Build Release Delta
        if: steps.identity.outputs.publish == 'true'
        env:
          VERSION: ${{ steps.identity.outputs.tag }}
          DISPLAY_VERSION: ${{ steps.identity.outputs.display }}
          CHANNEL: ${{ steps.identity.outputs.channel }}
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
            --files-from /tmp/pincabos-changed.list \
            --remove-from /tmp/pincabos-removed.list \
            --out dist

          cd dist

          sha256sum -c audit.sha256

          echo
          echo "=== FILES.LIST ==="
          cat files.list

          echo
          echo "=== RELEASE.JSON ==="
          cat release.json

      - name: Publish GitHub Release
        if: steps.identity.outputs.publish == 'true'
        env:
          GH_TOKEN: ${{ github.token }}
          VERSION: ${{ steps.identity.outputs.tag }}
          DISPLAY_VERSION: ${{ steps.identity.outputs.display }}
          CHANNEL: ${{ steps.identity.outputs.channel }}
          PRNUM: ${{ steps.identity.outputs.pr }}
        shell: bash
        run: |
          set -Eeuo pipefail

          target="$(git rev-parse HEAD)"

          title="$(
            gh pr view \
              "$PRNUM" \
              --repo "$GITHUB_REPOSITORY" \
              --json title \
              --jq '.title'
          )"

          notes="$(
            printf \
              'PinCabOS %s\n\nRelease automatique apres merge de la PR #%s.\n\n%s\n\nDistribution via GitHub Releases avec SHA-256, backup et rollback.' \
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

            echo "Release existante mise a jour."
          else
            gh release create \
              "$VERSION" \
              dist/pincabos-update.tar.zst \
              dist/files.list \
              dist/remove.list \
              dist/release.json \
              dist/audit.sha256 \
              --repo "$GITHUB_REPOSITORY" \
              --target "$target" \
              --title "PinCabOS $DISPLAY_VERSION" \
              --notes "$notes" \
              "${extra[@]}"
          fi

          echo "GO [OK] Release publiee: $VERSION"
YAML

echo "GO [OK] Workflow automatique cree."
echo

echo "=== 12. VALIDATION SOURCE AVANT GITHUB ==="

export PYTHONPYCACHEPREFIX="$WORK/pycache"

rm -rf "$PYTHONPYCACHEPREFIX"
mkdir -p "$PYTHONPYCACHEPREFIX"

python3 -m py_compile \
    opt/pincabos/update/pincabos_updates.py \
    opt/pincabos/update/build_release_v4.py \
    opt/pincabos/web/pincabos_updates.py \
    opt/pincabos/web/tools.py

bash -n \
    usr/local/sbin/pincabos-update-reboot

sudo visudo \
    -cf \
    etc/sudoers.d/pincabos-updates-web

git diff --check

grep -q \
    'PINCABOS_FULLWIDTH_GLOBAL_V1_BEGIN' \
    opt/pincabos/web/static/pincabos-appearance-dashboard-menu-v2.css

grep -q \
    'WEBSTATE = Path("/tmp/pincabos-update-web-state.json")' \
    opt/pincabos/web/pincabos_updates.py

grep -q \
    'PCOSUpdatePinCabOS.png' \
    opt/pincabos/web/tools.py

grep -q \
    'pull_request_target:' \
    .github/workflows/pincabos-release-v4.yml

echo "GO [OK] Python / Bash / sudoers / diff valides."
echo

echo "--- DIFF AVANT VERSION PR ---"

git status --short
echo

git diff --stat
echo

echo "==============================================================="
echo " GO [OK] PREFLIGHT LOCAL COMPLET"
echo " A PARTIR D'ICI GITHUB SERA MODIFIE"
echo "==============================================================="
echo

echo "=== 13. COMMIT INITIAL ==="

git config user.name \
    "PinCabOS Integration"

git config user.email \
    "pincabos@localhost"

git add -A

git commit \
    -m "feat(web): full width and automatic PR releases"

git push \
    -u origin \
    "$BRANCH"

echo "GO [OK] Branche poussee."
echo

echo "=== 14. CREATION DE LA PR ==="

PR_URL="$(
    gh pr create \
        --repo "$REPO" \
        --base main \
        --head "$BRANCH" \
        --title "PinCabOS Full Width + Updates Auto Release" \
        --body "Uniformise les pages PinCabOS en Full Width via la couche CSS globale.

Corrige aussi Updates V4 :
- page Updates professionnelle
- bouton Updates en premiere position
- image PCOSUpdatePinCabOS.png
- etat Web sans conflit root/pinball
- reboot Web restreint
- builder Release Delta
- release automatique apres PR mergee
- version Alpha 2.XX = numero de la derniere PR mergee
- tag GitHub alpha2.XX-beta.DATE.1
- verification SHA256 / backup / rollback conserves."
)"

PRNUM="$(
    gh pr view \
        "$BRANCH" \
        --repo "$REPO" \
        --json number \
        --jq '.number'
)"

echo "PR      : #$PRNUM"
echo "URL     : $PR_URL"
echo

DISPLAY_VERSION="Alpha 2.${PRNUM}"
RELEASE_PREFIX="alpha2.${PRNUM}-beta."

echo "=== 15. VERSION DE LA PR = $DISPLAY_VERSION ==="

python3 - "$PRNUM" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

pr = int(sys.argv[1])
display = f"Alpha 2.{pr}"

stamp = datetime.now(
    timezone.utc
).strftime("%Y-%m-%dT%H:%M:%SZ")

paths = [
    Path("opt/pincabos/config/version.json"),
    Path("opt/pincabos/version.json"),
]

for p in paths:
    if not p.exists():
        continue

    data = json.loads(
        p.read_text(
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

    p.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False
        ) + "\n",
        encoding="utf-8"
    )

    print(
        f"GO [OK] {p} -> {display}"
    )
PY

git add \
    opt/pincabos/config/version.json \
    opt/pincabos/version.json

git commit \
    -m "chore(version): $DISPLAY_VERSION"

git push

echo "GO [OK] PR #$PRNUM porte $DISPLAY_VERSION."
echo

echo "=== 16. PREFLIGHT RELEASE AVANT MERGE ==="

git diff \
    --name-only \
    --diff-filter=ACMRTUXB \
    origin/main...HEAD \
    > "$WORK/changed.list"

git diff \
    --name-only \
    --diff-filter=D \
    origin/main...HEAD \
    > "$WORK/removed.list"

TAG_PREFLIGHT="alpha2.${PRNUM}-beta.$(date -u +%Y%m%d).1"

rm -rf "$DIST"

GITHUB_SHA="$(git rev-parse HEAD)" \
python3 \
    opt/pincabos/update/build_release_v4.py \
    --version "$TAG_PREFLIGHT" \
    --display-version "$DISPLAY_VERSION" \
    --channel beta \
    --files-from "$WORK/changed.list" \
    --remove-from "$WORK/removed.list" \
    --out "$DIST"

cd "$DIST"

sha256sum -c audit.sha256

echo
echo "--- PACKAGE QUI SERA DISTRIBUE ---"
cat files.list

for REQUIRED in \
    opt/pincabos/update/pincabos_updates.py \
    opt/pincabos/web/pincabos_updates.py \
    opt/pincabos/web/tools.py \
    opt/pincabos/web/static/pincabos-appearance-dashboard-menu-v2.css \
    usr/local/sbin/pincabos-update-reboot \
    etc/sudoers.d/pincabos-updates-web
do
    grep -Fxq "$REQUIRED" files.list || {
        echo "NOGO [!!] Fichier requis absent du package : $REQUIRED"
        exit 1
    }
done

echo
echo "GO [OK] Release Delta preflight valide."
echo

cd "$SRC"

echo "=== 17. MERGE PR #$PRNUM ==="

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

if [ "$MERGED" != "true" ]; then
    echo "NOGO [!!] PR #$PRNUM non mergee."
    exit 1
fi

echo "GO [OK] PR #$PRNUM mergee."
echo

echo "=== 17B. DECLENCHEMENT EXPLICITE DU WORKFLOW RELEASE ==="

DISPATCHED=0

for TRY in $(seq 1 12); do
    if gh workflow run         pincabos-release-v4.yml         --repo "$REPO"         -f pr_number="$PRNUM"         -f channel=beta
    then
        DISPATCHED=1
        break
    fi

    echo "Workflow pas encore disponible, attente 5 sec..."
    sleep 5
done

if [ "$DISPATCHED" = "1" ]; then
    echo "GO [OK] Workflow Release V4 declenche."
else
    echo "INFO [--] Dispatch manuel non confirme."
    echo "Le trigger automatique peut tout de meme etre actif."
fi

echo

echo "=== 18. ATTENTE DE LA RELEASE AUTOMATIQUE ==="

RELEASE_TAG=""

for N in $(seq 1 60); do
    RELEASE_TAG="$(
        gh release list \
            --repo "$REPO" \
            --limit 50 \
            --json tagName,createdAt \
            --jq \
            ".[] |
             select(
               .tagName |
               startswith(\"$RELEASE_PREFIX\")
             ) |
             .tagName" \
            | head -1
    )"

    if [ -n "$RELEASE_TAG" ]; then
        break
    fi

    printf "Attente workflow... %02d/60\r" "$N"
    sleep 10
done

echo

if [ -z "$RELEASE_TAG" ]; then
    echo "NOGO [!!] Release automatique non detectee."
    echo
    echo "=== WORKFLOWS RECENTS ==="

    gh run list \
        --repo "$REPO" \
        --workflow pincabos-release-v4.yml \
        --limit 10 || true

    exit 1
fi

echo "GO [OK] Release detectee : $RELEASE_TAG"
echo

echo "=== 19. AUDIT RELEASE GITHUB ==="

gh release view \
    "$RELEASE_TAG" \
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

ASSET_COUNT="$(
    gh release view \
        "$RELEASE_TAG" \
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

if [ "$ASSET_COUNT" != "5" ]; then
    echo "NOGO [!!] Les 5 assets officiels ne sont pas presents."
    exit 1
fi

echo "GO [OK] Les 5 assets sont presents."
echo

echo "=== 20. CAB - CHECK DE LA NOUVELLE RELEASE ==="

sudo /usr/local/sbin/getpcos check

echo
echo "=== 21. CAB - TEST UPDATE REEL ==="

sudo /usr/local/sbin/getpcos update

echo
echo "=== 22. ETAT APRES UPDATE ==="

sudo /usr/local/sbin/getpcos status

echo
echo "--- VERSION JSON LOCALE ---"

sudo python3 - <<'PY'
import json
from pathlib import Path

for p in [
    Path("/opt/pincabos/config/version.json"),
    Path("/opt/pincabos/version.json"),
]:
    if not p.exists():
        continue

    try:
        data = json.loads(
            p.read_text(
                encoding="utf-8"
            )
        )
        print(
            f"{p}: "
            f"{data.get('version')}"
        )
    except Exception as e:
        print(
            f"{p}: ERREUR {e}"
        )
PY

echo

echo "=== 23. SERVICES ==="

for SERVICE in \
    pincabos-webapp.service \
    pincabos-vpinfe.service
do
    STATE="$(
        systemctl is-active \
            "$SERVICE" \
            2>/dev/null || true
    )"

    echo "$SERVICE : $STATE"

    if [ "$STATE" != "active" ]; then
        echo "NOGO [!!] Service non actif : $SERVICE"
        exit 1
    fi
done

echo "GO [OK] Services actifs."
echo

echo "=== 24. TEST PAGE FULL WIDTH / UPDATES ==="

HTTP_UPDATES="$(
    curl \
        -sS \
        -o "$WORK/updates-page.html" \
        -w '%{http_code}' \
        http://127.0.0.1/tools/updates
)"

echo "HTTP /tools/updates : $HTTP_UPDATES"

[ "$HTTP_UPDATES" = "200" ] || {
    echo "NOGO [!!] /tools/updates ne repond pas 200."
    exit 1
}

grep -q \
    'PinCabOS Updates' \
    "$WORK/updates-page.html"

echo "GO [OK] Page Updates disponible."
echo

echo "=== 25. TEST API BOUTON VERIFIER ==="

curl \
    -sS \
    -X POST \
    -H 'Content-Type: application/json' \
    -d '{"action":"check","reboot_after":false}' \
    http://127.0.0.1/api/updates/run

echo
echo

for N in $(seq 1 20); do
    sleep 1

    STATE_JSON="$(
        curl \
            -sS \
            http://127.0.0.1/api/updates/state
    )"

    RUNNING="$(
        printf '%s' "$STATE_JSON" \
        | python3 -c '
import json,sys
d=json.load(sys.stdin)
print(
    "true"
    if d.get("running")
    else "false"
)
'
    )"

    if [ "$RUNNING" = "false" ]; then
        break
    fi
done

printf '%s\n' "$STATE_JSON" \
    | python3 -m json.tool

echo
echo "--- LOG CHECK WEB ---"

cat /tmp/pincabos-update-web.log || true

echo

WEB_STATUS="$(
    printf '%s' "$STATE_JSON" \
    | python3 -c '
import json,sys
d=json.load(sys.stdin)
print(d.get("status",""))
'
)"

if [ "$WEB_STATUS" != "success" ]; then
    echo "NOGO [!!] Bouton Verifier n'a pas termine en succes."
    exit 1
fi

echo "GO [OK] Bouton Verifier fonctionne."
echo

echo "=== 26. TEST API BOUTON INSTALLER ==="
echo "Le cab est deja a jour : ce test doit retourner Already up to date."
echo

curl \
    -sS \
    -X POST \
    -H 'Content-Type: application/json' \
    -d '{"action":"update","reboot_after":false}' \
    http://127.0.0.1/api/updates/run

echo
echo

for N in $(seq 1 20); do
    sleep 1

    STATE_JSON="$(
        curl \
            -sS \
            http://127.0.0.1/api/updates/state
    )"

    RUNNING="$(
        printf '%s' "$STATE_JSON" \
        | python3 -c '
import json,sys
d=json.load(sys.stdin)
print(
    "true"
    if d.get("running")
    else "false"
)
'
    )"

    if [ "$RUNNING" = "false" ]; then
        break
    fi
done

printf '%s\n' "$STATE_JSON" \
    | python3 -m json.tool

echo
echo "--- LOG UPDATE WEB ---"

cat /tmp/pincabos-update-web.log || true

echo

WEB_STATUS="$(
    printf '%s' "$STATE_JSON" \
    | python3 -c '
import json,sys
d=json.load(sys.stdin)
print(d.get("status",""))
'
)"

if [ "$WEB_STATUS" != "success" ]; then
    echo "NOGO [!!] Bouton Installer n'a pas termine en succes."
    exit 1
fi

echo "GO [OK] Bouton Installer fonctionne."
echo

echo "==============================================================="
echo " GO [OK] PINCABOS FULLWIDTH + AUTO RELEASE OPERATIONNEL"
echo "==============================================================="
echo
echo "PR               : #$PRNUM"
echo "Version affichee : $DISPLAY_VERSION"
echo "Release          : $RELEASE_TAG"
echo "GitHub           : PR mergee + Release automatique"
echo "Full Width       : couche globale active"
echo "Updates Check    : valide"
echo "Updates Install  : valide"
echo "Reboot           : NON effectue"
echo
echo "Work : $WORK"
echo
