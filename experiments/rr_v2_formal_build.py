"""Seal and run the single authorized 128-source fresh formal build; no evaluation."""
from __future__ import annotations

import argparse
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
from urllib.request import build_opener, ProxyHandler

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.client import ExecutorClient
from legal_skill_guard.rr.compilation import prepare_request
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.formal import FormalRun
from legal_skill_guard.rr.ledger import BudgetError, BudgetLedger
from legal_skill_guard.rr.preflight import atomic_json, science_files
from legal_skill_guard.rr.readiness import current_binding

ROOT=Path(__file__).resolve().parents[1]
BASE='artifacts/rr_v2_formal_build_20261106'
EVIDENCE='reports/rr_v2_evidence/formal_build_20261106'


def prepare(root=ROOT):
    cfg=json.loads((root/'configs/rr_v2_preflight.json').read_text())
    formal=json.loads((root/'configs/rr_v2_formal.json').read_text())
    protocol=json.loads((root/'reports/legalskillguard_rule_reasoning_protocol_v2.json').read_text())
    baseline=json.loads((root/BASE/'baseline.json').read_text())
    manifest=json.loads((root/cfg['source_manifest']).read_text())
    auth=json.loads((root/formal['authorization']).read_text())
    offline=json.loads((root/'reports/rr_v2_evidence/offline_latest.json').read_text())
    files=science_files(root);binding=current_binding(root)
    allowed={'legal_skill_guard/rr/formal.py','experiments/rr_v2_formal_build.py','experiments/rr_v2_offline.py',
        'tests/test_rr_formal_build.py','tests/test_rr_pipeline.py','tests/test_rr_controls_and_scoring.py',
        'configs/rr_v2_formal.json','configs/rr_v2_preflight.json','reports/legalskillguard_rule_reasoning_protocol_v2.json'}
    changed={n for n in set(files)|set(baseline['protected_files']) if files.get(n)!=baseline['protected_files'].get(n)}
    if not changed<=allowed or binding['config_hash']!=baseline['prior_readiness']['execution_binding']['config_hash']:
        raise ValueError('Only launch/restore changes are allowed; executor/teacher/mechanisms stay fixed')
    if offline['exit_code'] or not offline['network_blocked'] or any(
        hashlib.sha256((root/p).read_bytes()).hexdigest()!=h for p,h in offline['files'].items()):
        raise ValueError('Current offline acceptance required')
    required={p for p in files if p.endswith('.py') and p.startswith(('legal_skill_guard/rr/','experiments/rr_v2','tests/test_rr'))}
    if not required<=set(offline['files']):raise ValueError('Offline receipt misses launch or recovery code')
    if len(manifest['formal_train_order'])!=128 or len(set(manifest['formal_train_order']))!=128 or not set(manifest['pilot_order'])<=set(manifest['formal_train_order']):
        raise ValueError('Original 128 training sources and original pilot subset required')
    if cfg['executor']['enable_thinking'] is not False or cfg['teacher']['model']!='gpt-5.6-sol' or cfg['teacher']['reasoning_effort']!='high' or cfg['teacher']['retries']!=0:
        raise ValueError('Fixed OFF executor and teacher high configuration required')
    if not formal['start_from_empty'] or formal['reuse_preflight_completion_records'] or formal['evaluation_enabled'] or formal['frozen_test_enabled']:
        raise ValueError('Only a fresh build without evaluation is authorized')
    if not formal['run_enabled'] or not formal['full_build_enabled'] or not protocol['run_enabled'] or protocol['execution_request'].get('formal_eval_enabled') or protocol['execution_request']['frozen_test_enabled']:
        raise ValueError('Build-only launch gates differ')
    if auth['executor_allocation']!=protocol['request_budget']['executor_allocation'] or sum(auth['executor_allocation'].values())!=6000:
        raise ValueError('Append-only budget reallocation differs')
    ctx=json.loads((root/BASE/'initial_context_check.json').read_text())
    if len(ctx['records'])!=128 or any(not x['fits'] for x in ctx['records']):raise ValueError('All initial inputs must fit without truncation')
    public=json.loads((root/'data/packets/rr_v2/public_train.json').read_text())
    sources={s['key']:s for s in public['sources']}
    contract=[]
    for sid in manifest['formal_train_order']:
        q=prepare_request(sources[sid],system_suffix='\nCurrent learned role constraints: []',request_config=cfg['executor'],thinking=False)
        contract.append({'source':sid,'messages_hash':digest(q['messages']),'schema_hash':digest(q['schema'])})
    # Reconfirm the local service and the longest prompt's actual OFF template.
    env=ExecutorClient(None,root/formal['artifact_directory'],cfg['executor'])
    card=env.readiness()
    largest=max(ctx['records'],key=lambda x:x['input_tokens'])
    q=prepare_request(sources[largest['source']],system_suffix='\nCurrent learned role constraints: []',request_config=cfg['executor'],thinking=False)
    assert env.tokenize(q['messages'],thinking=False)['count']==largest['input_tokens']
    transport=baseline['prior_readiness']['teacher_transport']
    if hashlib.sha256(Path(transport['executable']).read_bytes()).hexdigest()!=transport['executable_sha256']:
        raise ValueError('Previously verified Codex CLI transport changed')
    with sqlite3.connect(root/cfg['ledger_path']) as db:
        spec=json.loads(db.execute("select value from meta where key='spec'").fetchone()[0])
        old_calls=db.execute('select * from calls order by id').fetchall()
        counts=dict(db.execute('select role,count(*) from calls group by role'))
        spent=dict(db.execute('select bucket,count(*) from calls group by bucket'))
    if counts!=baseline['counts'] or any(x[6]=='reserved' for x in old_calls) or digest(old_calls)!=baseline['calls_hash']:
        raise ValueError('Preserve terminal127/4 original ledger before launch')
    if any(spent.get(k,0)>v for k,v in auth['executor_allocation'].items()):raise ValueError('Reallocation cannot erase existing spend')
    policy={'execution_binding':{k:binding[k] for k in ('code_hash','config_hash')},'allocation':auth['executor_allocation'],
        'authorization_hash':digest(auth),'order_hash':digest(manifest['formal_train_order']),
        'baseline_counts':counts,'formal_executor_max':256,'formal_teacher_max':16,
        'future_executor_reserve':5472,'teacher_total_max':20}
    ledger=BudgetLedger(root/cfg['ledger_path'],sources=manifest['allowlist'],code_hash=spec['code_hash'],config_hash=spec['config_hash'])
    with ledger.transaction() as db:
        key='formal_run:'+formal['run_id'];prior=db.execute('select value from meta where key=?',(key,)).fetchone()
        if prior and json.loads(prior[0])!=policy:raise ValueError('Formal policy is immutable')
        db.execute('insert or ignore into meta values (?,?)',(key,json.dumps(policy)))
    seal={'binding':binding,'protected_files':files,'formal_config':formal,'teacher_transport':transport,
        'executor_config':cfg['executor'],'teacher_config':cfg['teacher'],
        'ledger_origin_binding':{k:spec[k] for k in ('code_hash','config_hash')},'policy':policy,
        'initial_library_patterns':0,'reuse_preflight_completion_records':False,
        'initial_contracts':contract,'offline_evidence_hash':digest(offline),'model_card':card,
        'baseline_calls_hash':baseline['calls_hash'],'baseline_oracle_hash':baseline['oracle_hash']}
    immutable_json(root/formal['artifact_directory']/'seal.json',seal)
    path=root/EVIDENCE;path.mkdir(parents=True,exist_ok=True)
    immutable_json(path/'launch_checks.json',{'binding':binding,'launch_only_changed_paths':sorted(changed),
        'core_generation_paths_unchanged':True,'old_counts':counts,'budget_policy':policy,
        'context_sources':128,'max_initial_tokens':largest['input_tokens'],'model_generations_added':0,
        'formal_evaluation_enabled':False,'frozen_test_enabled':False})
    print(json.dumps({'sealed':True,'binding':binding,'sources':128,'initial_patterns':0,'budget':policy}),flush=True)
    return seal


def reconcile(run):
    """Recover preserved terminal outputs; orphaned attempts remain charged."""
    with run.ledger.transaction() as db:
        pending=db.execute("select id,request_hash from calls where status='reserved'").fetchall()
    for cid,request_hash in pending:
        if not cid.startswith(run.run_id+':'):raise BudgetError('Unrelated request is still live; do not restart it')
        directory=run.artifacts/'calls'/digest(cid)
        result=directory/'result.json';failure=directory/'failure.json'
        if result.exists():
            value=json.loads(result.read_text())
            req=json.loads((directory/'request.json').read_text())
            if 'request_hash' in req and req['request_hash']!=request_hash:raise BudgetError('Response reservation differs')
            run.ledger.finish(cid,status='completed',result=value)
        elif failure.exists():run.ledger.finish(cid,status='failed',result=json.loads(failure.read_text()))
        elif (directory/'wire_response.json').exists():
            req=json.loads((directory/'request.json').read_text())
            if req['request_hash']!=request_hash:raise BudgetError('Preserved response reservation differs')
            observed=json.loads((directory/'wire_response.json').read_text())
            raw=json.loads(base64.b64decode(observed['body_b64']))
            if not raw.get('choices') or not isinstance(raw.get('usage'),dict):
                raise BudgetError('Preserved wire response needs explicit failure reconciliation')
            msg=raw['choices'][0].get('message',{})
            value={'content':msg.get('content') or '', 'reasoning_content':msg.get('reasoning_content'),
                'finish_reason':raw['choices'][0].get('finish_reason'),'raw_id':raw.get('id'),
                'usage':raw['usage'],'thinking_requested':req['payload']['chat_template_kwargs']['enable_thinking'],
                'serving_template_tokens_sha256':digest(req['tokenization']['tokens']),
                'serving_template_suffix_tokens':req['tokenization']['tokens'][-24:],
                'elapsed_seconds':observed['elapsed_seconds'],'incremental_api_cash_usd':0,'gpu_cost_usd':None,
                'billing_basis':'existing_local_service_no_per_request_API_invoice','request_hash':request_hash,
                'artifact_directory':str(directory),'recovered_complete_wire_response':True}
            immutable_json(result,value);run.ledger.finish(cid,status='completed',result=value)
        else:
            # The run lock proves the old controller is gone. Do not overlap a
            # possible outstanding executor computation on the shared service.
            opener=build_opener(ProxyHandler({}))
            with opener.open('http://127.0.0.1:8000/metrics',timeout=30) as response:metrics=response.read().decode()
            active=[float(line.rsplit(' ',1)[-1]) for line in metrics.splitlines() if not line.startswith('#') and
                    ('num_requests_running{' in line or 'num_requests_waiting{' in line)]
            if not active or any(active):raise BudgetError('Wait for the outstanding service request; no duplicate dispatch')
            run.ledger.finish(cid,status='failed',result={'error_type':'InterruptedClient','usage':None,
                'elapsed_seconds':None,'reserved_and_charged':True,'complete_response_preserved':False})


def run(root=ROOT):
    cfg=json.loads((root/'configs/rr_v2_formal.json').read_text());directory=root/cfg['artifact_directory']
    directory.mkdir(parents=True,exist_ok=True)
    with (directory/'controller.lock').open('a+') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc:raise BudgetError('The existing formal controller is still running') from exc
        owner=FormalRun(root,partition='train')
        identity={'pid':os.getpid(),'start_ticks':Path('/proc/self/stat').read_text().split()[21],
            'run_id':owner.run_id,'binding':owner.binding,'status':'running','started_at':time.time()}
        atomic_json(directory/'process_identity.json',identity)
        try:
            reconcile(owner)
            result=owner.train()
            immutable_json(directory/'completion.json',result)
            atomic_json(directory/'process_identity.json',{**identity,'status':'complete','finished_at':time.time()})
            print(json.dumps({'event':'build_complete','sources':result['sources'],'batches':result['batches'],
                'executor_total':result['ledger']['executor_used'],'teacher_total':result['ledger']['teacher_used']}),flush=True)
        except BaseException as exc:
            atomic_json(directory/'process_identity.json',{**identity,'status':'stopped_with_error','error_type':type(exc).__name__,
                'error':str(exc),'finished_at':time.time()})
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','run']);args=parser.parse_args()
    {'prepare':prepare,'run':run}[args.action]()
