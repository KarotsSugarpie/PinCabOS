#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import time
import traceback
import uuid
from pathlib import Path

STATE_DIR = Path('/var/lib/pincabos/media-recorder')
LOG_DIR = STATE_DIR / 'logs'
HISTORY_DIR = STATE_DIR / 'history'
JOB_FILE = STATE_DIR / 'job.json'
STATUS_FILE = STATE_DIR / 'status.json'
CONTROL_FILE = STATE_DIR / 'control.json'
RECORDER = Path('/opt/pincabos/web/recorder.py')
VPINFE_SERVICE = 'pincabos-vpinfe.service'


def atomic_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp-' + uuid.uuid4().hex)
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    os.chmod(tmp, 0o664)
    os.replace(tmp, path)


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {} if default is None else default


def stamp():
    return time.strftime('%Y-%m-%d %H:%M:%S')


def systemctl(*args):
    return subprocess.run(['/usr/bin/systemctl', *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)


def service_active(name):
    return systemctl('is-active', '--quiet', name).returncode == 0


def kill_vpx():
    subprocess.run(['/usr/bin/pkill', '-TERM', '-u', 'pinball', '-f', 'VPinballX'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    time.sleep(1.5)
    subprocess.run(['/usr/bin/pkill', '-KILL', '-u', 'pinball', '-f', 'VPinballX'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def control_action():
    return str(read_json(CONTROL_FILE, {}).get('action') or '').strip().lower()


def clear_control():
    atomic_json(CONTROL_FILE, {'action': '', 'at': stamp()})


def write_status(base, **updates):
    data = dict(base)
    data.update(updates)
    data['updated_at'] = stamp()
    atomic_json(STATUS_FILE, data)
    return data


def append_log(path: Path, line: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as fh:
        fh.write(line.rstrip() + '\n')
        fh.flush()


def run_recorder(job, table, log_path, status):
    cmd = [
        str(RECORDER), '--table', str(table), '--screens', ','.join(job['screens']),
        '--type', job['type'], '--wait', str(job['wait']), '--duration', str(job['duration']),
        '--fps', str(job['fps']), '--quality', job['quality'], '--encoder', job['encoder'],
        '--source', job['source'], '--mode', job['mode'], '-v',
    ]
    if job.get('keep_other_type'):
        cmd.append('--keep-other-type')
    append_log(log_path, '\n$ ' + ' '.join(repr(x) if ' ' in x else x for x in cmd))
    with log_path.open('a', encoding='utf-8') as log:
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, text=True, start_new_session=True)
        stop_sent = False
        while proc.poll() is None:
            action = control_action()
            if action == 'stop' and not stop_sent:
                status = write_status(status, state='stopping', message='Arrêt demandé; fermeture de la table courante...')
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                stop_sent = True
            elif action == 'pause':
                status = write_status(status, state='pausing', message='Pause demandée; appliquée après la table courante.')
            time.sleep(0.5)
        return proc.returncode, status


def process_job(job):
    job_id = str(job.get('id') or 'unknown')
    tables = list(job.get('tables') or [])
    log_path = LOG_DIR / f'{job_id}.log'
    status = {
        'state': 'running', 'job_id': job_id, 'index': 0, 'total': len(tables),
        'current_table': '', 'message': 'Initialisation Recorder...', 'log_file': str(log_path),
        'started_at': stamp(), 'results': [],
    }
    status = write_status(status)
    clear_control()
    was_active = service_active(VPINFE_SERVICE)
    append_log(log_path, f'[{stamp()}] JOB {job_id} - {len(tables)} table(s)')
    append_log(log_path, f'[{stamp()}] VPinFE actif avant batch: {was_active}')
    final_state = 'completed'
    try:
        if was_active:
            r = systemctl('stop', VPINFE_SERVICE)
            append_log(log_path, f'[{stamp()}] systemctl stop {VPINFE_SERVICE}: rc={r.returncode}')
            if r.stdout.strip():
                append_log(log_path, r.stdout.strip())
            if service_active(VPINFE_SERVICE):
                raise RuntimeError('VPinFE refuse de s\'arrêter.')
        status = write_status(status, message='VPinFE arrêté. Début des captures.')

        for idx, table in enumerate(tables, start=1):
            while control_action() == 'pause':
                status = write_status(status, state='paused', index=idx-1, current_table='', message='Batch en pause entre deux tables.')
                time.sleep(0.5)
            if control_action() == 'resume':
                clear_control()
            if control_action() == 'stop':
                final_state = 'stopped'
                break

            status = write_status(status, state='running', index=idx-1, current_table=table, message=f'Table {idx}/{len(tables)}')
            append_log(log_path, f'\n[{stamp()}] ===== TABLE {idx}/{len(tables)} =====')
            append_log(log_path, table)
            rc, status = run_recorder(job, table, log_path, status)
            result = {'table': table, 'rc': rc, 'ok': rc == 0, 'finished_at': stamp()}
            status.setdefault('results', []).append(result)
            status = write_status(status, index=idx, current_table=table, message=('GO [OK]' if rc == 0 else f'NOGO [X] code {rc}'))

            if control_action() == 'stop':
                final_state = 'stopped'
                kill_vpx()
                break
            if control_action() == 'pause':
                continue
            if rc != 0:
                append_log(log_path, f'[{stamp()}] NOGO table, poursuite du batch.')

        if final_state == 'completed':
            failures = [x for x in status.get('results', []) if not x.get('ok')]
            if failures:
                final_state = 'completed_with_errors'
    except Exception as exc:
        final_state = 'failed'
        append_log(log_path, f'[{stamp()}] ERROR: {exc}')
        append_log(log_path, traceback.format_exc())
        status = write_status(status, message=str(exc))
    finally:
        kill_vpx()
        if was_active:
            r = systemctl('start', VPINFE_SERVICE)
            append_log(log_path, f'[{stamp()}] systemctl start {VPINFE_SERVICE}: rc={r.returncode}')
            if r.stdout.strip():
                append_log(log_path, r.stdout.strip())
        restored = service_active(VPINFE_SERVICE) if was_active else not service_active(VPINFE_SERVICE)
        append_log(log_path, f'[{stamp()}] VPinFE restauré selon état initial: {restored}')
        status = write_status(status, state=final_state, current_table='', message=f'Batch terminé: {final_state}', finished_at=stamp(), vpinfe_restored=restored)
        clear_control()
        try:
            HISTORY_DIR.mkdir(parents=True, exist_ok=True)
            history = HISTORY_DIR / f'{job_id}.json'
            atomic_json(history, {'job': job, 'status': status})
        except Exception:
            pass
        try:
            JOB_FILE.unlink(missing_ok=True)
        except Exception:
            pass


def main():
    for d in (STATE_DIR, LOG_DIR, HISTORY_DIR):
        d.mkdir(parents=True, exist_ok=True)
        os.chmod(d, 0o775)
    if not STATUS_FILE.exists():
        atomic_json(STATUS_FILE, {'state': 'idle', 'index': 0, 'total': 0, 'message': 'Worker prêt.', 'updated_at': stamp()})
    while True:
        try:
            if JOB_FILE.is_file():
                job = read_json(JOB_FILE, {})
                if isinstance(job, dict) and job.get('id'):
                    process_job(job)
                else:
                    JOB_FILE.unlink(missing_ok=True)
            time.sleep(0.75)
        except KeyboardInterrupt:
            break
        except Exception:
            time.sleep(2)


if __name__ == '__main__':
    main()
