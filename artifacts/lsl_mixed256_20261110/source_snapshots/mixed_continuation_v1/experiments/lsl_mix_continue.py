"""Continue the fixed remaining epochs/DEV, never TEST or paper writing.

This queue joins existing jobs rather than starting them twice. Compatible
dense native composition examples and frozen features are reused exactly.
Completion here only requests the human-facing server evidence review.
"""
from pathlib import Path
import fcntl
import json
import os
import subprocess
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from legal_skill_guard.lsl.data import load_json,write_json,sha


def compose_examples(out,bank,previous):
    rows={r['key']:r for r in load_json(out/'open_dataset.json')['records']if r['split']=='train'}
    old={r['source']:r for r in load_json(previous/'composition/examples.json')}
    local={r['source']:r for r in load_json(bank/'local/tables.json')}
    if set(old)!=set(local)or set(old)!=set(rows):raise ValueError('Mixed source manifest changed')
    examples=[];reused=0
    for key,row in rows.items():
        d=row['dataset']
        if d in ('NormBench','ProofWriter_OWA_depth5'):
            examples.append(old[key]);reused+=1
        else:examples.append({'source':key,'dataset':d,'squares':local[key].get('squares',[])})
    location=bank/'composition';location.mkdir(exist_ok=True)
    write_json(location/'examples.json',examples)
    write_json(location/'preparation.json',{'TRAIN_sources':256,'reused_dense_native_sources':reused,
        'parent_examples_sha256':sha(previous/'composition/examples.json'),
        'local_tables_sha256':sha(bank/'local/tables.json'),'examples_sha256':sha(location/'examples.json'),
        'native_source_labels_and_masks_unchanged':True,'TEST':False})


def main():
    out=ROOT/'artifacts/lsl_mixed256_20261110';location=out/'mixed_continuation';location.mkdir(exist_ok=True)
    lock=(location/'run.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    def status(stage,**kw):
        write_json(location/'status.json',{'stage':stage,'time':time.time(),'pid':os.getpid(),'goal_complete':False,**kw})
        print(json.dumps({'stage':stage,**kw}),flush=True)
    def run(script,*args):
        status('running_child',script=script,args=list(map(str,args)))
        subprocess.run([sys.executable,'-u',str(ROOT/'experiments'/script),*map(str,args)],cwd=ROOT,check=True)
    def joined(receipt,unit):
        while not receipt.exists():
            state=subprocess.run(['systemctl','--user','is-active',unit],capture_output=True,text=True).stdout.strip()
            if state!='active':raise RuntimeError('Existing job ended without receipt; preserve and diagnose, do not duplicate: '+unit)
            time.sleep(10)
        # A receipt is written just before process exit; wait for real GPU
        # ownership release before loading the next serving/training process.
        while subprocess.run(['systemctl','--user','is-active',unit],capture_output=True,text=True).stdout.strip()=='active':time.sleep(1)
    status('joining_existing_first_epoch_and_DEV')
    joined(out/'first_epoch_queue/complete.json','legal-lsl-mix256-first-epoch-queue.service')
    joined(out/'dev/epoch1/complete.json','legal-lsl-mix256-dev-e1.service')
    banks={1:out/'candidates/common-canonical/train'}
    for epoch in (2,3):
        previous_epoch=epoch-1;stage='epoch%d-provider'%previous_epoch;bank=out/'candidates'/stage/'train';banks[epoch]=bank
        if not (out/'acquisition/ExecutionFilter'/('epoch%d'%epoch)/'complete.json').exists()or not (out/'composition/contrast'/('epoch%d'%epoch)/'complete.json').exists():
            # Inference is a separate process, so no stale HF CUDA allocation
            # remains resident when the next LoRA trainer acquires the GPU.
            status('serving_previous_epoch_for_fixed_TRAIN',epoch=epoch)
            code='from pathlib import Path;from experiments.lsl_mix_dev import serve,checkpoints;out=Path('+repr(str(out))+');serve(out,'+str(previous_epoch)+',checkpoints(out,'+str(previous_epoch)+'))'
            subprocess.run([sys.executable,'-c',code],cwd=ROOT,check=True)
            checkpoint=load_json(out/'acquisition/Base'/('epoch%d'%previous_epoch)/'complete.json')['checkpoint']
            if not (bank/'complete.json').exists():
                run('lsl_mix_candidate_generation.py','--stage',stage,'--split','train','--checkpoint',checkpoint,'--alias','Base')
            if not (bank/'local/complete.json').exists():run('lsl_mix_local_candidates.py','--stage',stage,'--alias','Base')
            if not (bank/'composition/preparation.json').exists():compose_examples(out,bank,banks[previous_epoch])
            code='from pathlib import Path;from experiments.lsl_mix_dev import stop_serving;stop_serving(Path('+repr(str(out))+'),'+str(previous_epoch)+')'
            subprocess.run([sys.executable,'-c',code],cwd=ROOT,check=True)
            if not (bank/'composition/encoding.json').exists():run('lsl_mix_composition_training.py','--bank',bank,'--encode')
            for mode in ('ordinary','directed','contrast'):
                if not (out/'composition'/mode/('epoch%d'%epoch)/'complete.json').exists():
                    run('lsl_mix_composition_training.py','--bank',bank,'--train','--epoch',epoch,'--mode',mode)
            for arm in ('Base','M1','HardEM','ExecutionFilter'):
                if not (out/'acquisition'/arm/('epoch%d'%epoch)/'complete.json').exists():
                    run('lsl_mix_acquisition_training.py','--bank',bank,'--arm',arm,'--epoch',epoch)
        if not (out/'dev'/('epoch%d'%epoch)/'complete.json').exists():run('lsl_mix_dev.py','--epoch',epoch)
    summaries={str(e):load_json(out/'dev'/('epoch%d'%e)/'summary.json')for e in (1,2,3)}
    write_json(out/'dev_learning_curves.json',summaries)
    status('fixed_three_epoch_matrix_complete_server_review_required')
    write_json(location/'complete.json',{'TRAIN_sources_per_acquisition_epoch':256,'mixed_epochs':3,
        'systems':7,'DEV_sources_per_system_epoch':80,'curves_sha256':sha(out/'dev_learning_curves.json'),
        'TEST_opened':False,'paper_started':False,'goal_complete':False,'server_review_required':True})


if __name__=='__main__':
    try:main()
    except BaseException as e:
        write_json(ROOT/'artifacts/lsl_mixed256_20261110/mixed_continuation/failure.json',
            {'error':type(e).__name__+': '+str(e),'traceback':traceback.format_exc(),'time':time.time(),'goal_complete':False})
        raise
