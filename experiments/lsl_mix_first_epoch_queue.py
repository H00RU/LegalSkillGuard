"""Resume existing acquisition, then execute the first fixed mixed epoch.

No Goal is created or completed here. File locks and completed-stage receipts
prevent restarting an already completed pass. Later epochs/DEV remain explicit
continuations of the same fixed protocol, never a claim made by this queue.
"""
from pathlib import Path
import fcntl
import json
import os
import sqlite3
import subprocess
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from legal_skill_guard.lsl.data import load_json,write_json,sha


def main():
    import httpx
    out=ROOT/'artifacts/lsl_mixed256_20261110';bank=out/'candidates/common-canonical/train'
    location=out/'first_epoch_queue';location.mkdir(exist_ok=True)
    lock=(location/'run.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    def status(stage,**kw):
        write_json(location/'status.json',{'pid':os.getpid(),'stage':stage,'time':time.time(),'goal_complete':False,**kw})
        print(json.dumps({'stage':stage,**kw}),flush=True)
    def command(script,*args):
        status('running_child',script=script,args=list(map(str,args)))
        subprocess.run([sys.executable,'-u',str(ROOT/'experiments'/script),*map(str,args)],cwd=ROOT,check=True)
    status('awaiting_existing_candidate_job')
    while not (bank/'complete.json').exists():
        unit=subprocess.run(['systemctl','--user','is-active','legal-lsl-mix256-candidates-common-v5.service'],capture_output=True,text=True)
        if unit.stdout.strip()!='active':raise RuntimeError('Existing candidate queue stopped before completion; inspect raw results instead of launching it twice')
        time.sleep(10)
    if not (bank/'local/complete.json').exists():raise RuntimeError('Finish the bound offline canonical regrade before training; do not repeat generation')
    if not (bank/'composition/preparation.json').exists():command('lsl_mix_composition_training.py','--bank',bank,'--prepare')
    db=sqlite3.connect(out.parent/'rr_v2_preflight/research_ledger.sqlite3')
    pending=db.execute("select id,source from calls where status='reserved'").fetchall();db.close()
    if pending:raise RuntimeError('Preserve still-pending requests before changing GPU ownership: '+repr(pending))
    serving=subprocess.run(['systemctl','--user','is-active','legal-lsl-mix256-common-serving.service'],capture_output=True,text=True).stdout.strip()
    if serving=='active':
        metrics=httpx.get('http://127.0.0.1:8000/metrics',trust_env=False,timeout=10).text
        values=[line for line in metrics.splitlines() if line.startswith(('vllm:num_requests_running','vllm:num_requests_waiting'))]
        if not values or any(float(v.rsplit(' ',1)[1])!=0 for v in values):raise RuntimeError('Serving still has real requests: '+repr(values))
        write_json(location/'resource_boundary.json',{'time':time.time(),'metrics':values,'ledger_pending':0,
            'old_common_serving_unit':'legal-lsl-mix256-common-serving.service','original_restore_record':'../resource_handoff.json'})
        subprocess.run(['systemctl','--user','stop','legal-lsl-mix256-common-serving.service'],check=True)
    if not (bank/'composition/encoding.json').exists():command('lsl_mix_composition_training.py','--bank',bank,'--encode')
    if not (out/'composition/common_initialization/complete.json').exists():command('lsl_mix_composition_training.py','--bank',bank,'--train','--epoch','0','--mode','ordinary')
    # CPU head optimization and GPU LoRA optimize disjoint parameters against
    # the already frozen identical source records; no new inference is running.
    composition=subprocess.Popen([sys.executable,'-u',str(ROOT/'experiments/lsl_mix_composition_training.py'),
        '--bank',str(bank),'--train','--epoch','1','--mode','ordinary'],cwd=ROOT)
    try:
        for arm in ('Base','M1','HardEM','ExecutionFilter'):
            if not (out/'acquisition'/arm/'epoch1/complete.json').exists():
                command('lsl_mix_acquisition_training.py','--arm',arm,'--epoch','1','--bank',bank)
        if composition.wait()!=0:raise RuntimeError('Ordinary composition training failed; GPU results preserved')
        for mode in ('directed','contrast'):
            if not (out/'composition'/mode/'epoch1/complete.json').exists():
                command('lsl_mix_composition_training.py','--bank',bank,'--train','--epoch','1','--mode',mode)
    finally:
        if composition.poll() is None:composition.wait()
    status('first_mixed_epoch_complete_DEV_and_epochs2_3_required')
    write_json(location/'complete.json',{'first_mixed_epoch':True,'four_acquisition_models':True,
        'three_composition_models':True,'remaining':['epoch1 DEV80x7','epochs2/3 TRAIN256 and DEV80x7','phase review and delivery'],
        'goal_complete':False,'TEST':False})


if __name__=='__main__':
    try:main()
    except BaseException as e:
        write_json(ROOT/'artifacts/lsl_mixed256_20261110/first_epoch_queue/failure.json',
            {'error':type(e).__name__+': '+str(e),'traceback':traceback.format_exc(),'time':time.time(),'goal_complete':False})
        raise
