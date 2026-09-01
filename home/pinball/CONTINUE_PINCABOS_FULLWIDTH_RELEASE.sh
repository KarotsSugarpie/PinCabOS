#!/usr/bin/env bash
set -Eeuo pipefail

REPO="PinCabOS/PinCabOS"
WORK="/home/pinball/pincabos-fullwidth-auto-release-20260822-093232"
SRC="$WORK/source"
BRANCH="feat/fullwidth-updates-auto-release-20260822-093232"
EXPECTED_MAIN="07df37b43762b5864b6fe73687910ff314693203"
V4_BASE_SHA="$EXPECTED_MAIN"
DIST="$WORK/preflight-dist"

fail() {
    echo
    echo "==============================================================="
    echo " NOGO [!!] CONTINUATION FULLWIDTH / AUTO RELEASE"
    echo "==============================================================="
    echo "Work conserve : $WORK"
    exit 1
}

trap 'RC=$?; if [ "$RC" -ne 0 ]; then echo; echo "NOGO [!!] Erreur ligne $LINENO - code $RC"; echo "Work conserve : $WORK"; fi' ERR

echo "==============================================================="
echo " PINCABOS - CONTINUATION FULLWIDTH + AUTO RELEASE"
echo " FIX WHITESPACE + RELEASE CUMULATIVE"
echo " AUCUN RECLONE - AUCUN REBOOT"
echo "==============================================================="
echo

echo "=== 1. GARDE MAIN / BRANCHE ==="

[ -d "$SRC/.git" ] || fail
cd "$SRC"

CURRENT_BRANCH="$(git branch --show-current)"

[ "$CURRENT_BRANCH" = "$BRANCH" ] || {
    echo "NOGO [!!] Branche actuelle : $CURRENT_BRANCH"
    fail
}

git fetch origin main

CURRENT_MAIN="$(git rev-parse origin/main)"

echo "Main attendu : $EXPECTED_MAIN"
echo "Main actuel  : $CURRENT_MAIN"

[ "$CURRENT_MAIN" = "$EXPECTED_MAIN" ] || {
    echo "NOGO [!!] main a change. Aucun push."
    fail
}

if git ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>&1; then
    echo "NOGO [!!] La branche existe deja sur GitHub."
    echo "On ne pousse rien pour eviter un etat ambigu."
    fail
fi

echo "GO [OK] GitHub toujours intact pour cette branche."
echo

echo "=== 2. NORMALISATION WHITESPACE ==="

python3 - <<'PY'
from pathlib import Path

paths = [
    Path(".github/workflows/pincabos-release-v4.yml"),
    Path("etc/sudoers.d/pincabos-updates-web"),
    Path("opt/pincabos/update/build_release_v4.py"),
    Path("opt/pincabos/update/pincabos_updates.py"),
    Path("opt/pincabos/web/pincabos_updates.py"),
    Path("opt/pincabos/web/static/pincabos-appearance-dashboard-menu-v2.css"),
    Path("opt/pincabos/web/tools.py"),
    Path("usr/local/sbin/pincabos-update-reboot"),
]

for p in paths:
    if not p.is_file():
        continue

    raw = p.read_bytes()

    if b"\0" in raw:
        continue

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        continue

    lines = [line.rstrip(" \t") for line in text.splitlines()]

    while lines and lines[-1] == "":
        lines.pop()

    p.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8"
    )

    print(f"GO [OK] Normalise : {p}")
PY

echo
echo "=== 3. SECURITE UPDATE POUR SAUTER PLUSIEURS RELEASES ==="

python3 - <<'PY'
from pathlib import Path

p = Path("opt/pincabos/update/pincabos_updates.py")
s = p.read_text(encoding="utf-8")

old = """        rows=validate_list(files); rem=validate_list(remove) if remove.stat().st_size else []
        actual=sorted(set(x.rstrip('/') for x in subprocess.check_output(['tar','--zstd','-tf',str(archive)],text=True).splitlines() if x and not x.endswith('/')))
        if rows!=actual: raise UpdateError('Archive content differs from files.list.')
        stamp=subprocess.check_output(['date','+%Y%m%d-%H%M%S'],text=True).strip()
        bdir=BACKUPS/stamp; bdir.mkdir(parents=True)
        existing=[]; new=[]
        for rel in sorted(set(rows+rem)):
            p=Path('/')/rel
            (existing if p.exists() or p.is_symlink() else new).append(rel)
        (bdir/'existing.list').write_text(''.join(x+'\\n' for x in existing),encoding='utf-8')
        (bdir/'new.list').write_text(''.join(x+'\\n' for x in new),encoding='utf-8')
        (bdir/'previous-version').write_text(local_tag()+'\\n',encoding='utf-8')
        prev=load_json(STATE,{})
        (bdir/'previous-state.json').write_text(json.dumps(prev,indent=2)+'\\n',encoding='utf-8')
"""

new = """        rows=validate_list(files)
        explicit_rem=validate_list(remove) if remove.stat().st_size else []
        prev=load_json(STATE,{})
        previous_installed=[
            str(x).strip()
            for x in prev.get('installed_files',[])
            if str(x).strip() and allowed(str(x).strip())
        ]
        stale=sorted(set(previous_installed)-set(rows))
        rem=sorted(set(explicit_rem+stale))
        if stale:
            print(f'INFO [--] Stale managed files to remove: {len(stale)}')
        actual=sorted(set(x.rstrip('/') for x in subprocess.check_output(['tar','--zstd','-tf',str(archive)],text=True).splitlines() if x and not x.endswith('/')))
        if rows!=actual: raise UpdateError('Archive content differs from files.list.')
        stamp=subprocess.check_output(['date','+%Y%m%d-%H%M%S'],text=True).strip()
        bdir=BACKUPS/stamp; bdir.mkdir(parents=True)
        existing=[]; new=[]; owners={}
        for rel in sorted(set(rows+rem)):
            p=Path('/')/rel
            if p.exists() or p.is_symlink():
                existing.append(rel)
                try:
                    st=p.lstat()
                    owners[rel]={'uid':st.st_uid,'gid':st.st_gid}
                except OSError:
                    pass
            else:
                new.append(rel)
        (bdir/'existing.list').write_text(''.join(x+'\\n' for x in existing),encoding='utf-8')
        (bdir/'new.list').write_text(''.join(x+'\\n' for x in new),encoding='utf-8')
        (bdir/'owners.json').write_text(json.dumps(owners,indent=2)+'\\n',encoding='utf-8')
        (bdir/'previous-version').write_text(local_tag()+'\\n',encoding='utf-8')
        (bdir/'previous-state.json').write_text(json.dumps(prev,indent=2)+'\\n',encoding='utf-8')
"""

if old in s:
    s = s.replace(old, new, 1)
elif "Stale managed files to remove" in s and "owners.json" in s:
    print("GO [OK] Stale/owners deja corriges.")
else:
    raise SystemExit(
        "NOGO [!!] Bloc do_update inattendu; aucune modification."
    )

old2 = """            subprocess.run(['tar','--zstd','-xpf',str(archive),'-C','/'],check=True)
            for rel in rem:
                p=Path('/')/rel
                if p.is_dir() and not p.is_symlink(): shutil.rmtree(p,ignore_errors=True)
                else:
                    try: p.unlink()
                    except FileNotFoundError: pass
            validate_installed(rows)
"""

new2 = """            subprocess.run(['tar','--zstd','-xpf',str(archive),'-C','/'],check=True)
            for rel,meta in owners.items():
                p=Path('/')/rel
                if not (p.exists() or p.is_symlink()):
                    continue
                try:
                    if p.is_symlink():
                        os.lchown(p,int(meta['uid']),int(meta['gid']))
                    else:
                        os.chown(p,int(meta['uid']),int(meta['gid']))
                except OSError as e:
                    print(f'WARNING [--] Owner restore failed for {rel}: {e}')
            for rel in rows:
                if rel.startswith('etc/sudoers.d/'):
                    p=Path('/')/rel
                    if p.exists() and not p.is_symlink():
                        p.chmod(0o440)
            for rel in rem:
                p=Path('/')/rel
                if p.is_dir() and not p.is_symlink(): shutil.rmtree(p,ignore_errors=True)
                else:
                    try: p.unlink()
                    except FileNotFoundError: pass
            validate_installed(rows)
"""

if old2 in s:
    s = s.replace(old2, new2, 1)
elif "Owner restore failed" in s:
    print("GO [OK] Owner/sudoers deja corriges.")
else:
    raise SystemExit(
        "NOGO [!!] Bloc extraction inattendu; aucune modification."
    )

p.write_text(s, encoding="utf-8")

print("GO [OK] Fichiers obsoletes geres.")
print("GO [OK] UID/GID existants preserves.")
print("GO [OK] Sudoers force a 0440 apres extraction.")
PY

echo
echo "=== 4. ARCHIVE RELEASE NORMALISEE ROOT:ROOT ==="

python3 - <<'PY'
from pathlib import Path

p = Path("opt/pincabos/update/build_release_v4.py")
s = p.read_text(encoding="utf-8")

old = """            "tar",
            "--zstd",
            "--verbatim-files-from",
            "-cpf",
"""

new = """            "tar",
            "--zstd",
            "--verbatim-files-from",
            "--owner=0",
            "--group=0",
            "--numeric-owner",
            "-cpf",
"""

if old in s:
    s = s.replace(old, new, 1)
elif '"--numeric-owner"' in s:
    print("GO [OK] Tar deja normalise.")
else:
    raise SystemExit(
        "NOGO [!!] Commande tar du builder introuvable."
    )

p.write_text(s, encoding="utf-8")

print("GO [OK] Nouveaux fichiers Release = root:root.")
PY

echo
echo "=== 5. WORKFLOW = RELEASE CUMULATIVE DEPUIS V4 ==="

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
            requested="${INPUT_PR:-$latest}"
            channel="${INPUT_CHANNEL:-beta}"
          else
            requested="$EVENT_PR"
            channel="beta"
          fi

          if [[ "$requested" != "$latest" ]]; then
            echo "PR #$requested n'est plus la derniere PR mergee (#$latest)."
            echo "publish=false" >> "$GITHUB_OUTPUT"
            exit 0
          fi

          date_tag="$(date -u +%Y%m%d)"
          display="Alpha 2.${latest}"
          tag="alpha2.${latest}-${channel}.${date_tag}.1"

          echo "publish=true" >> "$GITHUB_OUTPUT"
          echo "pr=$latest" >> "$GITHUB_OUTPUT"
          echo "channel=$channel" >> "$GITHUB_OUTPUT"
          echo "display=$display" >> "$GITHUB_OUTPUT"
          echo "tag=$tag" >> "$GITHUB_OUTPUT"

          echo "Derniere PR mergee : #$latest"
          echo "Display version     : $display"
          echo "Release tag         : $tag"

      - name: Build cumulative update lists
        if: steps.identity.outputs.publish == 'true'
        env:
          V4_BASE_SHA: 07df37b43762b5864b6fe73687910ff314693203
        shell: bash
        run: |
          set -Eeuo pipefail

          git cat-file -e "${V4_BASE_SHA}^{commit}"

          git diff \
            --name-only \
            --diff-filter=ACMRTUXB \
            "${V4_BASE_SHA}..HEAD" \
            > /tmp/pincabos-changed.list

          git diff \
            --name-only \
            --diff-filter=D \
            "${V4_BASE_SHA}..HEAD" \
            > /tmp/pincabos-removed.list

          echo "=== CUMULATIVE CHANGES SINCE UPDATES V4 ==="
          cat /tmp/pincabos-changed.list || true

          echo
          echo "=== CUMULATIVE REMOVALS SINCE UPDATES V4 ==="
          cat /tmp/pincabos-removed.list || true

      - name: Synchronize source Alpha version
        if: steps.identity.outputs.publish == 'true'
        env:
          GH_TOKEN: ${{ github.token }}
          DISPLAY_VERSION: ${{ steps.identity.outputs.display }}
          PRNUM: ${{ steps.identity.outputs.pr }}
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

          if [[ "$latest" != "$PRNUM" ]]; then
            echo "Une PR plus recente est apparue: #$latest" >&2
            exit 1
          fi

          python3 - <<'PY'
          import json
          import os
          from datetime import datetime, timezone
          from pathlib import Path

          display = os.environ["DISPLAY_VERSION"]
          stamp = datetime.now(
              timezone.utc
          ).strftime("%Y-%m-%dT%H:%M:%SZ")

          for p in [
              Path("opt/pincabos/config/version.json"),
              Path("opt/pincabos/version.json"),
          ]:
              if not p.exists():
                  continue

              data = json.loads(
                  p.read_text(encoding="utf-8")
              )

              data["version"] = display

              if "updated_at" in data:
                  data["updated_at"] = (
                      stamp.replace("T", " ").replace("Z", "")
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

              print(f"{p} -> {display}")
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
              Path("opt/pincabos/update/pincabos_updates.py"),
              Path("opt/pincabos/update/build_release_v4.py"),
              Path("opt/pincabos/web/pincabos_updates.py"),
              Path("opt/pincabos/web/tools.py"),
          ]:
              compile(
                  p.read_text(encoding="utf-8"),
                  str(p),
                  "exec"
              )
          PY

          bash -n usr/local/sbin/getpcos
          bash -n usr/local/bin/getpcos

          if [[ -f usr/local/sbin/pincabos-update-reboot ]]; then
            bash -n usr/local/sbin/pincabos-update-reboot
          fi

      - name: Build cumulative Release
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
          echo "=== CUMULATIVE FILES.LIST ==="
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
              'PinCabOS %s\n\nRelease automatique apres merge de la PR #%s.\n\n%s\n\nPackage cumulatif depuis Updates V4. SHA-256, backup et rollback.' \
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

echo "GO [OK] Les Releases seront cumulatives depuis Updates V4."
echo

echo "=== 6. RENORMALISATION FINALE ==="

python3 - <<'PY'
from pathlib import Path

for p in [
    Path(".github/workflows/pincabos-release-v4.yml"),
    Path("opt/pincabos/update/pincabos_updates.py"),
    Path("opt/pincabos/update/build_release_v4.py"),
]:
    text = p.read_text(encoding="utf-8")
    lines = [x.rstrip(" \t") for x in text.splitlines()]

    while lines and lines[-1] == "":
        lines.pop()

    p.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8"
    )
PY

echo "GO [OK] Whitespace normalise."
echo

echo "=== 7. VALIDATION COMPLETE AVANT PUSH ==="

export PYTHONPYCACHEPREFIX="$WORK/pycache-final"

rm -rf "$PYTHONPYCACHEPREFIX"
mkdir -p "$PYTHONPYCACHEPREFIX"

python3 -m py_compile \
    opt/pincabos/update/pincabos_updates.py \
    opt/pincabos/update/build_release_v4.py \
    opt/pincabos/web/pincabos_updates.py \
    opt/pincabos/web/tools.py

bash -n usr/local/sbin/getpcos
bash -n usr/local/bin/getpcos
bash -n usr/local/sbin/pincabos-update-reboot

sudo visudo -cf etc/sudoers.d/pincabos-updates-web

git diff --check

python3 - <<'PY'
import subprocess

allowed = {
    ".github/workflows/pincabos-release-v4.yml",
    "etc/sudoers.d/pincabos-updates-web",
    "opt/pincabos/update/build_release_v4.py",
    "opt/pincabos/update/pincabos_updates.py",
    "opt/pincabos/web/pincabos_updates.py",
    "opt/pincabos/web/static/pincabos-appearance-dashboard-menu-v2.css",
    "opt/pincabos/web/static/pincabos-assets/PCOSUpdatePinCabOS.png",
    "opt/pincabos/web/tools.py",
    "usr/local/sbin/pincabos-update-reboot",
}

out = subprocess.check_output(
    ["git", "status", "--porcelain=v1"],
    text=True
)

paths = []

for line in out.splitlines():
    if not line:
        continue

    path = line[3:]

    if " -> " in path:
        path = path.split(" -> ", 1)[1]

    paths.append(path)

print("--- FICHIERS MODIFIES ---")

for path in paths:
    print(path)

bad = sorted(set(paths) - allowed)

if bad:
    raise SystemExit(
        "NOGO [!!] Fichiers hors perimetre:\n"
        + "\n".join(bad)
    )

required = {
    ".github/workflows/pincabos-release-v4.yml",
    "opt/pincabos/update/pincabos_updates.py",
    "opt/pincabos/web/pincabos_updates.py",
    "opt/pincabos/web/static/pincabos-appearance-dashboard-menu-v2.css",
    "opt/pincabos/web/tools.py",
}

missing = sorted(required - set(paths))

if missing:
    raise SystemExit(
        "NOGO [!!] Modifications requises absentes:\n"
        + "\n".join(missing)
    )

print("GO [OK] Diff limite au chantier demande.")
PY

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
    'Build cumulative Release' \
    .github/workflows/pincabos-release-v4.yml

grep -q \
    'Stale managed files to remove' \
    opt/pincabos/update/pincabos_updates.py

grep -q \
    -- '--numeric-owner' \
    opt/pincabos/update/build_release_v4.py

echo
git diff --stat
echo

echo "==============================================================="
echo " GO [OK] PREFLIGHT FINAL COMPLET"
echo " A PARTIR D'ICI SEULEMENT GITHUB SERA MODIFIE"
echo "==============================================================="
echo

echo "=== 8. COMMIT INITIAL + PUSH ==="

git config user.name "PinCabOS Integration"
git config user.email "pincabos@localhost"

git add -A
git diff --cached --check

git commit \
    -m "feat(web): full width and automatic PR releases"

git fetch origin main

[ "$(git rev-parse origin/main)" = "$EXPECTED_MAIN" ] || {
    echo "NOGO [!!] main a change juste avant le push."
    fail
}

git push -u origin "$BRANCH"

echo "GO [OK] Branche poussee."
echo

echo "=== 9. CREATION DE LA PR ==="

PR_URL="$(
    gh pr create \
        --repo "$REPO" \
        --base main \
        --head "$BRANCH" \
        --title "PinCabOS Full Width + Updates Auto Release" \
        --body "Passe les pages PinCabOS en Full Width via la couche CSS globale.

Updates V4 :
- page Updates professionnelle
- carte Updates en premiere position
- image PCOSUpdatePinCabOS.png
- correction du Web state root/pinball
- reboot Web restreint
- version Alpha 2.XX = numero de la derniere PR mergee
- workflow Release automatique
- Release cumulative permettant de sauter plusieurs versions
- suppressions cumulatives et rollback conserve."
)"

PRNUM="$(
    gh pr view \
        "$BRANCH" \
        --repo "$REPO" \
        --json number \
        --jq '.number'
)"

DISPLAY_VERSION="Alpha 2.${PRNUM}"
RELEASE_PREFIX="alpha2.${PRNUM}-beta."
TAG_PREFLIGHT="alpha2.${PRNUM}-beta.$(date -u +%Y%m%d).1"

echo "PR      : #$PRNUM"
echo "URL     : $PR_URL"
echo "Version : $DISPLAY_VERSION"
echo

echo "=== 10. VERSION SOURCE = NUMERO DE PR ==="

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

for p in [
    Path("opt/pincabos/config/version.json"),
    Path("opt/pincabos/version.json"),
]:
    if not p.exists():
        continue

    data = json.loads(
        p.read_text(encoding="utf-8")
    )

    data["version"] = display

    if "updated_at" in data:
        data["updated_at"] = (
            stamp.replace("T", " ").replace("Z", "")
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

    print(f"GO [OK] {p} -> {display}")
PY

git add \
    opt/pincabos/config/version.json \
    opt/pincabos/version.json

git diff --cached --check

git commit \
    -m "chore(version): $DISPLAY_VERSION"

git push

echo "GO [OK] Version PR synchronisee."
echo

echo "=== 11. PREFLIGHT PACKAGE CUMULATIF AVANT MERGE ==="

git diff \
    --name-only \
    --diff-filter=ACMRTUXB \
    "${V4_BASE_SHA}..HEAD" \
    > "$WORK/changed-cumulative.list"

git diff \
    --name-only \
    --diff-filter=D \
    "${V4_BASE_SHA}..HEAD" \
    > "$WORK/removed-cumulative.list"

rm -rf "$DIST"

GITHUB_SHA="$(git rev-parse HEAD)" \
python3 \
    opt/pincabos/update/build_release_v4.py \
    --version "$TAG_PREFLIGHT" \
    --display-version "$DISPLAY_VERSION" \
    --channel beta \
    --files-from "$WORK/changed-cumulative.list" \
    --remove-from "$WORK/removed-cumulative.list" \
    --out "$DIST"

cd "$DIST"

sha256sum -c audit.sha256

[ -f "$SRC/opt/pincabos/web/static/pincabos-assets/PCOSUpdatePinCabOS.png" ] || {
    echo "NOGO [!!] Image PCOSUpdatePinCabOS.png absente."
    fail
}

for REQUIRED in \
    opt/pincabos/update/pincabos_updates.py \
    opt/pincabos/web/pincabos_updates.py \
    opt/pincabos/web/tools.py \
    opt/pincabos/web/static/pincabos-appearance-dashboard-menu-v2.css \
    usr/local/sbin/pincabos-update-reboot \
    etc/sudoers.d/pincabos-updates-web
do
    grep -Fxq "$REQUIRED" files.list || {
        echo "NOGO [!!] Fichier requis absent : $REQUIRED"
        fail
    }
done

BAD_OWNER="$(
    tar \
        --zstd \
        --numeric-owner \
        -tvf pincabos-update.tar.zst \
        | awk '$2 != "0/0" {print; exit}'
)"

if [ -n "$BAD_OWNER" ]; then
    echo "NOGO [!!] Archive contient un owner non root/root:"
    echo "$BAD_OWNER"
    fail
fi

echo "GO [OK] Archive root:root."

python3 - "$TAG_PREFLIGHT" "$DISPLAY_VERSION" <<'PY'
import json
import sys
from pathlib import Path

tag = sys.argv[1]
display = sys.argv[2]

data = json.loads(
    Path("release.json").read_text(
        encoding="utf-8"
    )
)

assert data["version"] == tag
assert data["display_version"] == display
assert data["channel"] == "beta"

print("GO [OK] release.json conforme.")
PY

echo "GO [OK] Package cumulatif preflight valide."
echo

cd "$SRC"

echo "=== 12. GARDE MAIN AVANT MERGE ==="

git fetch origin main

CURRENT_MAIN="$(git rev-parse origin/main)"

echo "Main attendu : $EXPECTED_MAIN"
echo "Main actuel  : $CURRENT_MAIN"

[ "$CURRENT_MAIN" = "$EXPECTED_MAIN" ] || {
    echo "NOGO [!!] Une autre modification est arrivee sur main."
    echo "La PR reste ouverte; aucun merge automatique."
    fail
}

echo "GO [OK] main toujours identique."
echo

echo "=== 13. MERGE PR #$PRNUM ==="

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

echo "GO [OK] PR #$PRNUM mergee -> $DISPLAY_VERSION"
echo

echo "=== 14. DECLENCHEMENT DU WORKFLOW RELEASE ==="

DISPATCHED=0

for TRY in $(seq 1 12); do
    if gh workflow run \
        pincabos-release-v4.yml \
        --repo "$REPO" \
        -f pr_number="$PRNUM" \
        -f channel=beta
    then
        DISPATCHED=1
        break
    fi

    echo "Workflow pas encore indexe; attente 5 secondes..."
    sleep 5
done

if [ "$DISPATCHED" = "1" ]; then
    echo "GO [OK] Workflow Release V4 declenche."
else
    echo "INFO [--] Dispatch manuel non confirme."
    echo "Le trigger merge reste actif."
fi

echo
echo "=== 15. ATTENTE RELEASE ==="

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

    printf "Attente Release... %02d/60\r" "$N"
    sleep 10
done

echo

if [ -z "$RELEASE_TAG" ]; then
    echo "NOGO [!!] Release automatique non detectee."
    echo

    gh run list \
        --repo "$REPO" \
        --workflow pincabos-release-v4.yml \
        --limit 10 || true

    fail
fi

echo "GO [OK] Release detectee : $RELEASE_TAG"
echo

echo "=== 16. AUDIT DES 5 ASSETS ==="

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

[ "$ASSET_COUNT" = "5" ] || {
    echo "NOGO [!!] Assets officiels incomplets."
    fail
}

echo "GO [OK] Les 5 assets sont presents."
echo

echo "=== 17. CHECK CAB ==="

sudo /usr/local/sbin/getpcos check

echo
echo "=== 18. UPDATE REEL DU CAB ==="

sudo /usr/local/sbin/getpcos update

echo
echo "=== 19. VALIDATION VERSION INSTALLEE ==="

sudo /usr/local/sbin/getpcos status

sudo python3 - "$RELEASE_TAG" "$DISPLAY_VERSION" <<'PY'
import json
import sys
from pathlib import Path

tag = sys.argv[1]
display = sys.argv[2]

state = json.loads(
    Path(
        "/var/lib/pincabos/updates/state.json"
    ).read_text(
        encoding="utf-8"
    )
)

if state.get("installed_version") != tag:
    raise SystemExit(
        "NOGO [!!] installed_version incorrect: "
        + str(state.get("installed_version"))
    )

if state.get("display_version") != display:
    raise SystemExit(
        "NOGO [!!] display_version incorrect: "
        + str(state.get("display_version"))
    )

print("GO [OK] State Updates conforme.")

for p in [
    Path("/opt/pincabos/config/version.json"),
    Path("/opt/pincabos/version.json"),
]:
    if not p.exists():
        continue

    data = json.loads(
        p.read_text(
            encoding="utf-8"
        )
    )

    print(f"{p}: {data.get('version')}")

    if data.get("version") != display:
        raise SystemExit(
            f"NOGO [!!] Version incorrecte dans {p}"
        )

print("GO [OK] Alpha version synchronisee.")
PY

echo
echo "=== 20. SERVICES ==="

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

    [ "$STATE" = "active" ] || {
        echo "NOGO [!!] Service non actif : $SERVICE"
        fail
    }
done

echo "GO [OK] Services actifs."
echo

echo "=== 21. FULL WIDTH LIVE ==="

CSS_HTTP="$(
    curl -sS \
        -o "$WORK/global-css-live.css" \
        -w '%{http_code}' \
        http://127.0.0.1/static/pincabos-appearance-dashboard-menu-v2.css
)"

[ "$CSS_HTTP" = "200" ] || {
    echo "NOGO [!!] CSS global HTTP $CSS_HTTP"
    fail
}

grep -q \
    'PINCABOS_FULLWIDTH_GLOBAL_V1_BEGIN' \
    "$WORK/global-css-live.css"

TOOLS_HTTP="$(
    curl -sS \
        -o "$WORK/tools-live.html" \
        -w '%{http_code}' \
        http://127.0.0.1/tools
)"

UPDATES_HTTP="$(
    curl -sS \
        -o "$WORK/updates-live.html" \
        -w '%{http_code}' \
        http://127.0.0.1/tools/updates
)"

echo "HTTP /tools         : $TOOLS_HTTP"
echo "HTTP /tools/updates : $UPDATES_HTTP"

[ "$TOOLS_HTTP" = "200" ] || fail
[ "$UPDATES_HTTP" = "200" ] || fail

grep -q \
    'pincabos-appearance-dashboard-menu-v2.css' \
    "$WORK/tools-live.html"

grep -q \
    'PinCabOS Updates' \
    "$WORK/updates-live.html"

echo "GO [OK] Full Width global charge."
echo

echo "=== 22. TEST BOUTON WEB - VERIFIER ==="

curl -sS \
    -X POST \
    -H 'Content-Type: application/json' \
    -d '{"action":"check","reboot_after":false}' \
    http://127.0.0.1/api/updates/run

echo

STATE_JSON=""

for N in $(seq 1 30); do
    sleep 1

    STATE_JSON="$(
        curl -sS \
            http://127.0.0.1/api/updates/state
    )"

    RUNNING="$(
        printf '%s' "$STATE_JSON" \
        | python3 -c '
import json,sys
d=json.load(sys.stdin)
print("1" if d.get("running") else "0")
'
    )"

    [ "$RUNNING" = "0" ] && break
done

printf '%s\n' "$STATE_JSON" \
    | python3 -m json.tool

echo
echo "--- LOG WEB CHECK ---"

cat /tmp/pincabos-update-web.log || true

echo

WEB_STATUS="$(
    printf '%s' "$STATE_JSON" \
    | python3 -c '
import json,sys
print(json.load(sys.stdin).get("status",""))
'
)"

[ "$WEB_STATUS" = "success" ] || {
    echo "NOGO [!!] Bouton Verifier en echec."
    fail
}

echo "GO [OK] Bouton Verifier fonctionne."
echo

echo "=== 23. TEST BOUTON WEB - INSTALLER ==="
echo "Le cab est deja a jour; getpcos doit confirmer Already up to date."
echo

curl -sS \
    -X POST \
    -H 'Content-Type: application/json' \
    -d '{"action":"update","reboot_after":false}' \
    http://127.0.0.1/api/updates/run

echo

STATE_JSON=""

for N in $(seq 1 30); do
    sleep 1

    STATE_JSON="$(
        curl -sS \
            http://127.0.0.1/api/updates/state
    )"

    RUNNING="$(
        printf '%s' "$STATE_JSON" \
        | python3 -c '
import json,sys
d=json.load(sys.stdin)
print("1" if d.get("running") else "0")
'
    )"

    [ "$RUNNING" = "0" ] && break
done

printf '%s\n' "$STATE_JSON" \
    | python3 -m json.tool

echo
echo "--- LOG WEB UPDATE ---"

cat /tmp/pincabos-update-web.log || true

echo

WEB_STATUS="$(
    printf '%s' "$STATE_JSON" \
    | python3 -c '
import json,sys
print(json.load(sys.stdin).get("status",""))
'
)"

[ "$WEB_STATUS" = "success" ] || {
    echo "NOGO [!!] Bouton Installer en echec."
    fail
}

grep -q \
    'Already up to date' \
    /tmp/pincabos-update-web.log || {
        echo "NOGO [!!] Le test Installer n'a pas confirme Already up to date."
        fail
    }

echo "GO [OK] Bouton Installer fonctionne."
echo

echo "==============================================================="
echo " GO [OK] FULLWIDTH + AUTO RELEASE + UPDATE VALIDES"
echo "==============================================================="
echo
echo "PR               : #$PRNUM"
echo "Version affichee : $DISPLAY_VERSION"
echo "Release          : $RELEASE_TAG"
echo "Full Width       : actif globalement"
echo "Release format   : cumulatif depuis V4"
echo "Check Web        : OK"
echo "Install Web      : OK"
echo "Reboot           : NON"
echo "Work             : $WORK"
