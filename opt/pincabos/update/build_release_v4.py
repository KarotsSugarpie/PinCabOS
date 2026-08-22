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
