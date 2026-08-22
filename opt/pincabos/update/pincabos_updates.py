#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, sys, tempfile, urllib.request
from pathlib import Path

CONFIG = Path('/etc/pincabos/updates.json')
STATE = Path('/var/lib/pincabos/updates/state.json')
CACHE = Path('/var/cache/pincabos/updates')
BACKUPS = Path('/opt/pincabos/backups/updates')
VERSION_FILES = [Path('/opt/pincabos/config/version.json'), Path('/opt/pincabos/version.json')]
SERVICES = ['pincabos-webapp.service','pincabos-vpinfe.service','pincabos-fulldmd.service','pincabos-dof.service']

class UpdateError(RuntimeError): pass

def load_json(path, default=None):
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except Exception: return {} if default is None else default

def save_json(path, data):
    p=Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    tmp=p.with_suffix(p.suffix+'.tmp')
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    os.replace(tmp,p)

def config():
    d=load_json(CONFIG,{})
    return d.get('repository','KarotsSugarpie/PinCabOS'), d.get('channel','beta')

def local_version():
    st=load_json(STATE,{})
    if st.get('installed_version'): return str(st['installed_version'])
    for p in VERSION_FILES:
        d=load_json(p,{})
        if d.get('version'): return str(d['version'])
    return 'unknown'

def api_json(url):
    req=urllib.request.Request(url, headers={'User-Agent':'PinCabOS-Updates/4','Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode('utf-8'))

def download(url, dest):
    req=urllib.request.Request(url, headers={'User-Agent':'PinCabOS-Updates/4','Accept':'application/octet-stream'})
    with urllib.request.urlopen(req, timeout=60) as r, open(dest,'wb') as f:
        shutil.copyfileobj(r,f)

def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def allowed(rel):
    if not rel or rel.startswith('/') or '..' in Path(rel).parts: return False
    prefixes=(
      'opt/pincabos/web/','opt/pincabos/bin/','opt/pincabos/script/','opt/pincabos/update/','opt/pincabos/modules/',
      'usr/local/bin/pincabos-','usr/local/sbin/pincabos-','etc/systemd/system/pincabos-',
      'etc/lightdm/lightdm.conf.d/','etc/tmpfiles.d/pincabos-','etc/udev/rules.d/','etc/sudoers.d/','etc/polkit-1/rules.d/'
    )
    exact={'usr/local/bin/getpcos','usr/local/sbin/getpcos'}
    if rel in exact: return True
    if not rel.startswith(prefixes): return False
    forbidden=('opt/pincabos/web/.venv/','opt/pincabos/web/backups/','opt/pincabos/build/','opt/pincabos/backups/','opt/pincabos/logs/')
    return not rel.startswith(forbidden) and '__pycache__' not in Path(rel).parts and not rel.endswith(('.pyc','.pyo'))

def release():
    repo, channel=config()
    data=api_json(f'https://api.github.com/repos/{repo}/releases?per_page=30')
    for r in data:
        if r.get('draft'): continue
        if channel=='stable' and r.get('prerelease'): continue
        assets={a['name']:a for a in r.get('assets',[]) if a.get('name')}
        meta_asset=assets.get('release.json')
        if not meta_asset: continue
        try:
            meta=api_json(meta_asset['browser_download_url'])
        except Exception:
            continue
        if int(meta.get('schema',0)) < 4: continue
        if meta.get('repository') != repo: continue
        if meta.get('version') != r.get('tag_name'): continue
        if channel!='dev' and meta.get('channel') != channel: continue
        meta['_release']=r; meta['_assets']=assets
        return meta
    return None

def status():
    repo, channel=config()
    print(f'Repository       : {repo}')
    print(f'Channel          : {channel}')
    print(f'Installed version: {local_version()}')
    st=load_json(STATE,{})
    if st.get('last_backup'): print(f'Last backup      : {st["last_backup"]}')

def check():
    status(); print()
    m=release()
    if not m:
        print('Available version: none compatible')
        return 2
    print(f'Available version: {m["version"]}')
    print(f'Release URL      : {m["_release"].get("html_url","")}')
    return 0

def require_root():
    if os.geteuid()!=0: raise UpdateError('This command requires root.')

def validate_list(path):
    rows=[]
    for raw in Path(path).read_text(encoding='utf-8').splitlines():
        rel=raw.strip()
        if not rel: continue
        if not allowed(rel): raise UpdateError(f'Path refused: {rel}')
        rows.append(rel)
    return sorted(set(rows))

def active_services():
    out=[]
    for s in SERVICES:
        if subprocess.run(['systemctl','is-active','--quiet',s]).returncode==0: out.append(s)
    return out

def restart_services(items):
    subprocess.run(['systemctl','daemon-reload'],check=False)
    for s in items: subprocess.run(['systemctl','restart',s],check=False)

def validate_installed(rows):
    for rel in rows:
        p=Path('/')/rel
        if not p.exists() or p.is_symlink(): continue
        try: first=p.open('rb').readline(200).decode('utf-8','ignore').strip()
        except Exception: first=''
        if first.startswith('#!') and 'python' in first:
            subprocess.run(['python3','-m','py_compile',str(p)],check=True,env={**os.environ,'PYTHONPYCACHEPREFIX':'/tmp/pincabos-update-pycache'})
        elif first.startswith('#!') and ('bash' in first or first.endswith('/sh')):
            subprocess.run(['bash','-n',str(p)],check=True)
        elif rel.endswith('.py'):
            subprocess.run(['python3','-m','py_compile',str(p)],check=True,env={**os.environ,'PYTHONPYCACHEPREFIX':'/tmp/pincabos-update-pycache'})
        if rel.startswith('etc/sudoers.d/') and shutil.which('visudo'):
            subprocess.run(['visudo','-cf',str(p)],check=True,stdout=subprocess.DEVNULL)

def do_update():
    require_root(); CACHE.mkdir(parents=True,exist_ok=True); BACKUPS.mkdir(parents=True,exist_ok=True)
    m=release()
    if not m: raise UpdateError('No compatible GitHub Release found.')
    if local_version()==m['version']:
        print(f'GO [OK] Already up to date: {m["version"]}'); return 0
    assets=m['_assets']
    names=[m.get('archive','pincabos-update.tar.zst'),m.get('files','files.list'),m.get('remove','remove.list')]
    for n in names:
        if n not in assets: raise UpdateError(f'Missing Release asset: {n}')
    work=Path(tempfile.mkdtemp(prefix='pincabos-update-',dir=str(CACHE)))
    try:
        archive=work/names[0]; files=work/names[1]; remove=work/names[2]
        for n,p in zip(names,[archive,files,remove]): download(assets[n]['browser_download_url'],p)
        if sha256(archive).lower()!=str(m.get('archive_sha256','')).lower(): raise UpdateError('Archive SHA256 mismatch.')
        rows=validate_list(files); rem=validate_list(remove) if remove.stat().st_size else []
        actual=sorted(set(x.rstrip('/') for x in subprocess.check_output(['tar','--zstd','-tf',str(archive)],text=True).splitlines() if x and not x.endswith('/')))
        if rows!=actual: raise UpdateError('Archive content differs from files.list.')
        stamp=subprocess.check_output(['date','+%Y%m%d-%H%M%S'],text=True).strip()
        bdir=BACKUPS/stamp; bdir.mkdir(parents=True)
        existing=[]; new=[]
        for rel in sorted(set(rows+rem)):
            p=Path('/')/rel
            (existing if p.exists() or p.is_symlink() else new).append(rel)
        (bdir/'existing.list').write_text(''.join(x+'\n' for x in existing),encoding='utf-8')
        (bdir/'new.list').write_text(''.join(x+'\n' for x in new),encoding='utf-8')
        (bdir/'previous-version').write_text(local_version()+'\n',encoding='utf-8')
        prev=load_json(STATE,{})
        (bdir/'previous-state.json').write_text(json.dumps(prev,indent=2)+'\n',encoding='utf-8')
        if existing:
            subprocess.run(['tar','--zstd','-cpf',str(bdir/'backup.tar.zst'),'-C','/','-T',str(bdir/'existing.list')],check=True)
        svcs=active_services()
        for s in svcs: subprocess.run(['systemctl','stop',s],check=False)
        try:
            subprocess.run(['tar','--zstd','-xpf',str(archive),'-C','/'],check=True)
            for rel in rem:
                p=Path('/')/rel
                if p.is_dir() and not p.is_symlink(): shutil.rmtree(p,ignore_errors=True)
                else:
                    try: p.unlink()
                    except FileNotFoundError: pass
            validate_installed(rows)
        except Exception:
            for rel in new:
                p=Path('/')/rel
                if p.is_dir() and not p.is_symlink(): shutil.rmtree(p,ignore_errors=True)
                else:
                    try: p.unlink()
                    except FileNotFoundError: pass
            if (bdir/'backup.tar.zst').exists(): subprocess.run(['tar','--zstd','-xpf',str(bdir/'backup.tar.zst'),'-C','/'],check=False)
            restart_services(svcs)
            raise
        restart_services(svcs)
        save_json(STATE,{'installed_version':m['version'],'installed_files':rows,'last_backup':str(bdir),'channel':config()[1]})
        print(f'GO [OK] Update installed: {m["version"]}')
        print(f'GO [OK] Backup: {bdir}')
        return 0
    finally:
        shutil.rmtree(work,ignore_errors=True)

def rollback_last():
    require_root(); st=load_json(STATE,{})
    bdir=Path(st.get('last_backup',''))
    if not bdir.is_dir(): raise UpdateError('No rollback backup available.')
    new=[x for x in (bdir/'new.list').read_text(encoding='utf-8').splitlines() if x]
    svcs=active_services()
    for s in svcs: subprocess.run(['systemctl','stop',s],check=False)
    for rel in new:
        if not allowed(rel): raise UpdateError(f'Rollback path refused: {rel}')
        p=Path('/')/rel
        if p.is_dir() and not p.is_symlink(): shutil.rmtree(p,ignore_errors=True)
        else:
            try: p.unlink()
            except FileNotFoundError: pass
    if (bdir/'backup.tar.zst').exists(): subprocess.run(['tar','--zstd','-xpf',str(bdir/'backup.tar.zst'),'-C','/'],check=True)
    prev=load_json(bdir/'previous-state.json',{})
    save_json(STATE,prev)
    restart_services(svcs)
    print(f'GO [OK] Rollback restored: {(bdir/"previous-version").read_text().strip()}')
    return 0

def main():
    ap=argparse.ArgumentParser(prog='getpcos'); ap.add_argument('command',choices=['status','check','update','rollback']); a=ap.parse_args()
    try:
        return {'status':lambda:(status() or 0),'check':check,'update':do_update,'rollback':rollback_last}[a.command]()
    except Exception as e:
        print(f'NOGO [!!] {e}',file=sys.stderr); return 1
if __name__=='__main__': raise SystemExit(main())
