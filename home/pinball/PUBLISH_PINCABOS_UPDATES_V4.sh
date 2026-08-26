#!/usr/bin/env bash
set -Eeuo pipefail
clear

REPO="KarotsSugarpie/PinCabOS"
VERSION="alpha2.40-beta.20260822.1"
CHANNEL="beta"
STAMP="$(date +%Y%m%d-%H%M%S)"
WORK="/home/pinball/pincabos-updates-v4-source-$STAMP"
SRC="$WORK/source"
BRANCH="feat/updates-v4-clean-$STAMP"

ok(){ printf 'GO [OK] %s\n' "$*"; }
fail(){ printf 'NOGO [!!] %s\n' "$*" >&2; exit 1; }
trap 'rc=$?; if (( rc != 0 )); then echo; echo "==============================================================="; echo " NOGO [!!] UPDATES V4 SOURCE / RELEASE"; echo "==============================================================="; echo "Work conserve: '$WORK'"; fi' EXIT

echo "==============================================================="
echo " PINCABOS - PUBLICATION UPDATES V4 PROPRE"
echo " SOURCE GITHUB + RELEASE GITHUB ACTIONS"
echo " AUCUN REBOOT"
echo "==============================================================="
echo "Version : $VERSION"
echo "Canal   : $CHANNEL"
echo

[[ "$(id -un)" == "pinball" ]] || fail "Executer comme pinball, pas avec sudo."
command -v git >/dev/null || fail "git absent"
command -v gh >/dev/null || fail "gh absent"
command -v python3 >/dev/null || fail "python3 absent"
gh auth status >/dev/null 2>&1 || fail "gh non authentifie"
[[ -s /opt/pincabos/update/pincabos_updates.py ]] || fail "Moteur V4 live absent"
[[ -s /opt/pincabos/web/tools.py ]] || fail "tools.py live absent"
[[ -x /usr/local/sbin/getpcos ]] || fail "getpcos V4 live absent"

if gh release view "$VERSION" -R "$REPO" >/dev/null 2>&1; then
  fail "La Release $VERSION existe deja."
fi

LIVE_WEBMOD="$(python3 - <<'PY'
from pathlib import Path
import re
s=Path('/opt/pincabos/web/tools.py').read_text(encoding='utf-8', errors='replace')
m=re.search(r'from\s+([A-Za-z_][A-Za-z0-9_]*)\s+import\s+register\s+as\s+_pincabos_updates_register', s)
print(m.group(1) if m else '')
PY
)"
[[ -n "$LIVE_WEBMOD" ]] || fail "Module Web V4 introuvable dans tools.py"
[[ -s "/opt/pincabos/web/$LIVE_WEBMOD.py" ]] || fail "Fichier Web V4 absent: /opt/pincabos/web/$LIVE_WEBMOD.py"
ok "Module Web V4 detecte: $LIVE_WEBMOD.py"

echo
echo "=== 1. CLONE SPARSE LEGER DE MAIN ==="
mkdir -p "$WORK"
git clone --depth 1 --filter=blob:none --no-checkout "https://github.com/$REPO.git" "$SRC"
cd "$SRC"
git sparse-checkout init --no-cone
cat > .git/info/sparse-checkout <<'EOF'
/opt/pincabos/update/
/opt/pincabos/web/tools.py
/opt/pincabos/web/*update*.py
/opt/pincabos/script/build-update.sh
/opt/pincabos/script/publish-update.sh
/opt/pincabos/modules/system/mod-updates*
/usr/local/sbin/getpcos
/usr/local/sbin/build-update.sh
/usr/local/bin/getpcos
/.github/workflows/
EOF
git checkout main
BASE_SHA="$(git rev-parse HEAD)"
ok "Main source: $BASE_SHA"
git switch -c "$BRANCH"

echo
echo "=== 2. REMPLACEMENT TOTAL DE L'ANCIEN UPDATER DANS LA SOURCE ==="
rm -rf opt/pincabos/update
mkdir -p opt/pincabos/update opt/pincabos/web usr/local/sbin usr/local/bin .github/workflows
cp /opt/pincabos/update/pincabos_updates.py opt/pincabos/update/pincabos_updates.py
cp "/opt/pincabos/web/$LIVE_WEBMOD.py" "opt/pincabos/web/$LIVE_WEBMOD.py"
cp /usr/local/sbin/getpcos usr/local/sbin/getpcos
rm -f usr/local/bin/getpcos
cat > usr/local/bin/getpcos <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail
exec /usr/local/sbin/getpcos "$@"
EOF
chmod +x usr/local/bin/getpcos usr/local/sbin/getpcos opt/pincabos/update/pincabos_updates.py
rm -f opt/pincabos/script/build-update.sh opt/pincabos/script/publish-update.sh usr/local/sbin/build-update.sh
rm -f opt/pincabos/modules/system/mod-updates* 2>/dev/null || true

python3 - "$LIVE_WEBMOD" <<'PY'
from pathlib import Path
import re, sys
module=sys.argv[1]
p=Path('opt/pincabos/web/tools.py')
s=p.read_text(encoding='utf-8')

# Nettoyage de toute ancienne carte Updates connue.
s=re.sub(r'\n?\s*<!--\s*PINCABOS_UPDATES_V[0-9]+_CARD_START\s*-->.*?<!--\s*PINCABOS_UPDATES_V[0-9]+_CARD_END\s*-->\s*\n?', '\n', s, flags=re.S)
# Nettoyage de toute ancienne registration V3/V4 marquee.
s=re.sub(r'\n?\s*#\s*PINCABOS_UPDATES_V[0-9]+_REGISTER_START.*?#\s*PINCABOS_UPDATES_V[0-9]+_REGISTER_END\s*\n?', '\n', s, flags=re.S)
# Si une ancienne carte sans marqueur existe, refus plutot que doublon silencieux.
if 'href="/tools/updates"' in s:
    raise SystemExit('NOGO [!!] Une carte /tools/updates non marquee existe deja dans tools.py source')

card='''
        <!-- PINCABOS_UPDATES_V4_CARD_START -->
        <a class="tool-card" href="/tools/updates">
          <div class="pco-tool-art" style="display:grid;place-items:center;font-size:64px;color:#ff9b25">↻</div>
          <div class="pco-tool-body">
            <strong>PinCabOS Updates</strong>
            <span class="pco-tool-description">Verifier, installer ou restaurer les mises a jour PinCabOS publiees sur GitHub Releases.</span>
            <div class="pco-tool-footer"><span>Ouvrir Updates</span><span class="pco-tool-open">→</span></div>
          </div>
        </a>
        <!-- PINCABOS_UPDATES_V4_CARD_END -->
'''
anchor='<a class="tool-card" href="/tools/appearance">'
idx=s.find(anchor)
if idx < 0:
    raise SystemExit('NOGO [!!] Ancre carte Apparence introuvable dans tools.py source')
s=s[:idx]+card+s[idx:]

register=f'''
    # PINCABOS_UPDATES_V4_REGISTER_START
    try:
        from {module} import register as _pincabos_updates_register
        _pincabos_updates_register(app, page)
    except Exception as _pincabos_updates_error:
        try:
            app.logger.exception("PinCabOS Updates registration failed: %s", _pincabos_updates_error)
        except Exception:
            pass
    # PINCABOS_UPDATES_V4_REGISTER_END
'''
anchor2='    _tools_register_appearance_routes(app)'
idx=s.find(anchor2)
if idx < 0:
    raise SystemExit('NOGO [!!] Ancre registration tools introuvable')
s=s[:idx]+register+s[idx:]
p.write_text(s, encoding='utf-8')
print('GO [OK] tools.py source integre a Updates V4.')
PY

cat > opt/pincabos/update/build_release_v4.py <<'PY'
#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, importlib.util, json, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

def load_engine(repo: Path):
    path=repo/'opt/pincabos/update/pincabos_updates.py'
    spec=importlib.util.spec_from_file_location('pincabos_updates_release_engine', path)
    mod=importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    fn=getattr(mod,'allowed',None)
    if not callable(fn):
        raise SystemExit('NOGO [!!] allowed() absent du moteur V4')
    return fn

def sha256(path: Path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()

def validate_script(path: Path):
    if path.is_symlink() or not path.is_file(): return
    try:
        first=path.open('r',encoding='utf-8',errors='strict').readline().strip()
    except (UnicodeDecodeError, OSError):
        return
    rel=str(path)
    if first.startswith('#!') and 'python' in first:
        compile(path.read_text(encoding='utf-8'), rel, 'exec')
    elif first.startswith('#!') and ('bash' in first or first.endswith('/sh')):
        subprocess.run(['bash','-n',str(path)],check=True)
    elif path.suffix=='.py':
        compile(path.read_text(encoding='utf-8'), rel, 'exec')
    elif path.suffix=='.sh':
        # Une extension .sh peut contenir du Python dans PinCabOS; le shebang est prioritaire.
        if first.startswith('#!'):
            return
        subprocess.run(['bash','-n',str(path)],check=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--version',required=True)
    ap.add_argument('--channel',required=True,choices=['stable','beta','dev'])
    ap.add_argument('--out',required=True)
    args=ap.parse_args()
    repo=Path(__file__).resolve().parents[3]
    out=Path(args.out).resolve(); out.mkdir(parents=True,exist_ok=True)
    allowed=load_engine(repo)
    rows=[]
    for p in repo.rglob('*'):
        if '.git' in p.parts: continue
        if not (p.is_file() or p.is_symlink()): continue
        rel=p.relative_to(repo).as_posix()
        if allowed(rel):
            rows.append(rel)
    rows=sorted(set(rows))
    if not rows: raise SystemExit('NOGO [!!] Aucun fichier autorise pour la Release')
    for rel in rows: validate_script(repo/rel)
    files=out/'files.list'
    files.write_text(''.join(x+'\n' for x in rows),encoding='utf-8')
    legacy=[
      'opt/pincabos/script/build-update.sh',
      'opt/pincabos/script/publish-update.sh',
      'opt/pincabos/update/client/getpcos',
      'opt/pincabos/update/client/install-getpcos.sh',
      'opt/pincabos/update/managed-paths.conf',
      'usr/local/sbin/build-update.sh',
    ]
    removals=sorted(x for x in legacy if allowed(x))
    remove=out/'remove.list'
    remove.write_text(''.join(x+'\n' for x in removals),encoding='utf-8')
    archive=out/'pincabos-update.tar.zst'
    subprocess.run(['tar','--zstd','--verbatim-files-from','-cpf',str(archive),'-C',str(repo),'-T',str(files)],check=True)
    actual=sorted(set(x.rstrip('/') for x in subprocess.check_output(['tar','--zstd','-tf',str(archive)],text=True).splitlines() if x and not x.endswith('/')))
    if actual != rows:
        raise SystemExit('NOGO [!!] Archive != files.list')
    meta={
      'schema':4,
      'version':args.version,
      'channel':args.channel,
      'repository':'KarotsSugarpie/PinCabOS',
      'archive':'pincabos-update.tar.zst',
      'archive_sha256':sha256(archive),
      'files':'files.list',
      'remove':'remove.list',
      'file_count':len(rows),
      'remove_count':len(removals),
      'source_sha':os.environ.get('GITHUB_SHA') or subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip(),
      'built_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
    }
    release=out/'release.json'
    release.write_text(json.dumps(meta,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    audit=out/'audit.sha256'
    with audit.open('w',encoding='utf-8') as f:
        for p in [archive,files,remove,release]: f.write(f'{sha256(p)}  {p.name}\n')
    print(f'GO [OK] Release package: {len(rows)} fichiers, {len(removals)} suppressions')
    print(f'GO [OK] SHA256 archive: {meta["archive_sha256"]}')
if __name__=='__main__': main()
PY
chmod +x opt/pincabos/update/build_release_v4.py

cat > .github/workflows/pincabos-release-v4.yml <<'YML'
name: PinCabOS Release V4
on:
  workflow_dispatch:
    inputs:
      version:
        description: Release tag/version
        required: true
        type: string
      channel:
        description: Update channel
        required: true
        default: beta
        type: choice
        options: [stable, beta, dev]
permissions:
  contents: write
jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install zstd
        run: sudo apt-get update && sudo apt-get install -y zstd
      - name: Validate V4 sources
        run: |
          python3 - <<'PY'
          from pathlib import Path
          for p in [
              Path('opt/pincabos/update/pincabos_updates.py'),
              Path('opt/pincabos/update/build_release_v4.py'),
          ]:
              compile(p.read_text(encoding='utf-8'), str(p), 'exec')
          PY
          bash -n usr/local/sbin/getpcos
          bash -n usr/local/bin/getpcos
      - name: Build release assets
        run: |
          rm -rf dist
          python3 opt/pincabos/update/build_release_v4.py \
            --version '${{ inputs.version }}' \
            --channel '${{ inputs.channel }}' \
            --out dist
          cd dist
          sha256sum -c audit.sha256
      - name: Create GitHub Release
        env:
          GH_TOKEN: ${{ github.token }}
          VERSION: ${{ inputs.version }}
          CHANNEL: ${{ inputs.channel }}
        run: |
          if gh release view "$VERSION" >/dev/null 2>&1; then
            echo "Release already exists: $VERSION" >&2
            exit 1
          fi
          extra=()
          if [[ "$CHANNEL" != "stable" ]]; then extra+=(--prerelease); fi
          gh release create "$VERSION" \
            dist/pincabos-update.tar.zst \
            dist/files.list \
            dist/remove.list \
            dist/release.json \
            dist/audit.sha256 \
            --target "$GITHUB_SHA" \
            --title "PinCabOS $VERSION" \
            --notes "PinCabOS Updates V4 clean release. Distributed from official GitHub Releases with SHA-256 validation, backup and rollback." \
            "${extra[@]}"
YML

# Normalisation des permissions source.
chmod 0755 opt/pincabos/update/pincabos_updates.py opt/pincabos/update/build_release_v4.py usr/local/sbin/getpcos usr/local/bin/getpcos

echo
echo "=== 3. PREFLIGHT LOCAL AVANT PUSH ==="
export PYTHONPYCACHEPREFIX="/tmp/pincabos-v4-pycache-$UID"
mkdir -p "$PYTHONPYCACHEPREFIX"
python3 -m py_compile opt/pincabos/update/pincabos_updates.py "opt/pincabos/web/$LIVE_WEBMOD.py" opt/pincabos/update/build_release_v4.py
bash -n usr/local/sbin/getpcos
bash -n usr/local/bin/getpcos
python3 - <<'PY'
from pathlib import Path
s=Path('opt/pincabos/web/tools.py').read_text(encoding='utf-8')
assert s.count('href="/tools/updates"') == 1, 'Carte Updates dupliquee/manquante'
assert s.count('PINCABOS_UPDATES_V4_REGISTER_START') == 1, 'Registration Updates V4 invalide'
print('GO [OK] Integration tools.py unique.')
PY
python3 opt/pincabos/update/build_release_v4.py --version "$VERSION" --channel "$CHANNEL" --out "$WORK/preflight-dist"
(
 cd "$WORK/preflight-dist"
 sha256sum -c audit.sha256
)
git diff --check
ok "PREFLIGHT LOCAL COMPLET VALIDE."

echo
echo "=== 4. COMMIT + PUSH + PR ==="
git config user.name "PinCabOS Integration"
git config user.email "pincabos@localhost"
git add -A
[[ -n "$(git status --porcelain)" ]] || fail "Aucun changement source detecte"
git status --short
git diff --cached --stat
git commit -m "feat(updates): rebuild PinCabOS Updates V4 on GitHub Releases"
git push -u origin "$BRANCH"
PR_URL="$(gh pr create -R "$REPO" --base main --head "$BRANCH" --title "PinCabOS Updates V4 clean GitHub Releases" --body "Rebuilds the PinCabOS update subsystem from a clean V4 base. Removes the legacy pincabos.cc publisher/client, adds GitHub Releases updater, Web Tools integration, deterministic Release builder and GitHub Actions publishing workflow.")"
ok "PR creee: $PR_URL"
PR_NUM="$(gh pr view "$PR_URL" -R "$REPO" --json number --jq .number)"
HEAD_SHA="$(git rev-parse HEAD)"

gh pr merge "$PR_NUM" -R "$REPO" --squash --delete-branch --match-head-commit "$HEAD_SHA"
ok "PR #$PR_NUM mergee."

echo
echo "=== 5. DECLENCHEMENT DE LA RELEASE GITHUB ==="
# Attendre que le workflow nouvellement merge soit visible par l'API.
for i in $(seq 1 20); do
  if gh workflow view pincabos-release-v4.yml -R "$REPO" >/dev/null 2>&1; then break; fi
  sleep 2
done
gh workflow view pincabos-release-v4.yml -R "$REPO" >/dev/null 2>&1 || fail "Workflow V4 non visible apres merge"
BEFORE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
gh workflow run pincabos-release-v4.yml -R "$REPO" --ref main -f version="$VERSION" -f channel="$CHANNEL"
RUN_ID=""
for i in $(seq 1 30); do
  RUN_ID="$(gh run list -R "$REPO" --workflow pincabos-release-v4.yml --branch main --event workflow_dispatch --limit 5 --json databaseId,createdAt --jq '.[0].databaseId // empty' 2>/dev/null || true)"
  [[ -n "$RUN_ID" ]] && break
  sleep 2
done
[[ -n "$RUN_ID" ]] || fail "Run GitHub Actions introuvable"
ok "Workflow run: $RUN_ID"
gh run watch "$RUN_ID" -R "$REPO" --exit-status

echo
echo "=== 6. VERIFICATION RELEASE + CLIENT ==="
gh release view "$VERSION" -R "$REPO" --json name,tagName,isPrerelease,url,assets --jq '{tag:.tagName,name:.name,prerelease:.isPrerelease,url:.url,assets:[.assets[].name]}'
for asset in pincabos-update.tar.zst files.list remove.list release.json audit.sha256; do
  gh release view "$VERSION" -R "$REPO" --json assets --jq '.assets[].name' | grep -Fxq "$asset" || fail "Asset manquant: $asset"
done
ok "Tous les assets V4 sont presents."
/usr/local/sbin/getpcos check

echo
echo "==============================================================="
echo " GO [OK] PINCABOS UPDATES V4 PUBLIE"
echo "==============================================================="
echo "Version : $VERSION"
echo "PR      : #$PR_NUM"
echo "Run     : $RUN_ID"
echo "Work    : $WORK"
