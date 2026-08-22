from __future__ import annotations
import html, subprocess
from flask import request, redirect

def _run(args, root=False, timeout=45):
    cmd=(['sudo','/usr/local/sbin/getpcos'] if root else ['/usr/local/sbin/getpcos'])+args
    try:
        p=subprocess.run(cmd,text=True,capture_output=True,timeout=timeout)
        return (p.stdout+p.stderr).strip(), p.returncode
    except Exception as e:
        return f'NOGO [!!] {e}',1

def _page(message=''):
    status,_=_run(['status'])
    extra=f'<pre>{html.escape(message)}</pre>' if message else ''
    return f'''
    <div style="max-width:1100px;margin:auto">
      <h1>PinCabOS Updates</h1>
      <p>Nouveau moteur propre base sur les GitHub Releases officielles.</p>
      <pre>{html.escape(status)}</pre>{extra}
      <div style="display:flex;gap:12px;flex-wrap:wrap">
        <form method="post"><input type="hidden" name="action" value="check"><button>Verifier les mises a jour</button></form>
        <form method="post" onsubmit="return confirm('Installer la mise a jour PinCabOS disponible ?')"><input type="hidden" name="action" value="update"><button>Installer la mise a jour</button></form>
        <form method="post" onsubmit="return confirm('Restaurer la derniere sauvegarde Update ?')"><input type="hidden" name="action" value="rollback"><button>Rollback</button></form>
      </div>
    </div>'''

def register(app, page):
    @app.route('/tools/updates',methods=['GET','POST'])
    def pincabos_updates_v4():
        msg=''
        if request.method=='POST':
            action=request.form.get('action','')
            if action=='check': msg,_=_run(['check'])
            elif action in ('update','rollback'):
                # Demarre hors du worker WebApp: l'update peut redemarrer ce service.
                log=open('/tmp/pincabos-update-web.log','ab',buffering=0)
                subprocess.Popen(['sudo','/usr/local/sbin/getpcos',action],stdout=log,stderr=log,start_new_session=True)
                return redirect('/tools/updates?started='+action)
        if request.args.get('started'):
            msg='Operation lancee: '+request.args['started']+'\nLog: /tmp/pincabos-update-web.log'
        return page('PinCabOS Updates',_page(msg))
