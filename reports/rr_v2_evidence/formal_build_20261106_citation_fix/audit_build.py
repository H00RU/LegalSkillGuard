"""Read-only audit/reporting of the fixed formal build; never generates text.

Live mode checks committed prefixes. Final mode requires all128 and B1/B8.
Optional mechanism re-execution only uses exact already-recorded oracle views.
This file is unbound evidence tooling, not part of the running scientific code.
"""
from __future__ import annotations
import argparse
import base64
from collections import Counter
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import socket
import sqlite3
import subprocess
from unittest.mock import patch

from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.learning import SkillLibrary
from legal_skill_guard.rr.preflight import science_files,scientific_code_binding
from legal_skill_guard.rr.source_learning import DurableOracle,OracleUnavailable,learn_source

ROOT=Path(__file__).resolve().parents[3]
RUN_ID='rr_v2_formal_build_20261106_citation_fix'
BASE=ROOT/'artifacts/rr_v2_formal_build_20261106'
RUN=BASE/'run_citation_fix'
OUT=ROOT/'reports/rr_v2_evidence/formal_build_20261106_citation_fix'


def read(path):return json.loads(Path(path).read_text())
def dump(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def sql_state(path):
    with sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True) as db:
        db.execute('begin')
        return {'calls':db.execute('select * from calls order by id').fetchall(),
            'meta':db.execute('select * from meta order by key').fetchall(),
            'oracle':db.execute('select * from oracle_views order by source,view_hash').fetchall()}


def mechanism_check(record,source,grade,ledger_path):
    """Execute current learning, not a cached learning result, on recorded views.

    An attempt sees its actually recorded view sequence, rather than later views
    from the same source. Missing information is never filled by a new oracle.
    """
    traces=[]
    for attempt in record['learning_attempts']:
        expected=attempt['learning'];step=attempt['step'];allowed=expected['oracle_views']
        class Scope:
            path=ledger_path
            def _source(self,sid):
                if sid!=source['key']:raise ValueError('Wrong training source')
            def reserve_oracle(self,*a):raise RuntimeError('Audit cannot obtain new labels')
        durable=DurableOracle(Scope(),ROOT/'artifacts/rr_v2_preflight/oracle_guard',source,grade)
        class RecordedOracle:
            def cached_views(self):return [deepcopy(v['view']) for v in allowed]
            def query(self,view):
                key=digest(view);items=[v for v in allowed if v['view_hash']==key]
                if len(items)!=1:raise RuntimeError('Learning requested an unrecorded view during audit')
                item=items[0]
                directory=durable.root/'oracle_views'/digest(source['key'])/key
                request=read(directory/'request.json')
                if request['reference_hash']!=digest(grade) or request['source']!=source['key'] or digest(request['view'])!=key:
                    raise ValueError('Recorded oracle provenance differs')
                if item.get('status')=='reference_failed':
                    if not (directory/'failure.json').exists():raise ValueError('Missing charged oracle failure')
                    raise OracleUnavailable(item['error'])
                actual=durable.query(view)
                if digest(actual)!=digest(item['answer']):raise ValueError('Recorded oracle answer differs')
                return actual
        trace={}
        computed=learn_source(source,grade,RecordedOracle(),proposal=record['calls'][step]['analysis'].get('proposal'),trace=trace)
        if digest(computed)!=digest(expected):
            raise ValueError('Current learning re-execution differs: '+record['source']+' step '+str(step))
        checks=trace.get('selected_connector_semantics',[])
        traces.append({'step':step,'learning_exact':True,'trace':trace,
            'semantic_observations':len(checks),
            'semantic_observations_matching':sum(digest(c['prediction'])==digest(c['reference_answer']) for c in checks),
            'reference_views_available':1+sum(v.get('status')!='reference_failed' for v in allowed),
            'not_new_model_generation':True,'not_cached_learning_result':True})
    return traces


def audit(final=False,mechanisms=False):
    seal=read(RUN/'seal.json');cfg=read(ROOT/'configs/rr_v2_preflight.json')
    formal=read(ROOT/'configs/rr_v2_formal.json');protocol=read(ROOT/'reports/legalskillguard_rule_reasoning_protocol_v2.json')
    manifest=read(ROOT/cfg['source_manifest']);binding=seal['binding'];order=manifest['formal_train_order']
    current_files=science_files(ROOT);expected_files=seal['protected_files']
    processing_binding=binding;processing_revision=None;processing=None
    if (RUN/'processing_repair.json').exists():
        processing=read(RUN/'processing_repair.json');processing_binding=processing['processing_binding'];processing_revision=digest(processing)
        changed={p for p in set(current_files)|set(expected_files) if current_files.get(p)!=expected_files.get(p)}
        allowed={'legal_skill_guard/rr/source_learning.py','legal_skill_guard/rr/formal.py','tests/test_rr_sara_reference_recovery.py'}
        if processing['parent_seal_hash']!=digest(seal) or processing['generation_binding']!=binding or \
                processing['run_id']!=RUN_ID or changed!=set(processing['changed_files']) or not changed<=allowed or \
                processing_binding!={**binding,'code_hash':scientific_code_binding(current_files)}:
            raise ValueError('Processing continuation is not compatible with the sealed generation contract')
        for name,wanted in processing['proof_files'].items():
            if sha(ROOT/name)!=wanted:raise ValueError('Processing continuation evidence changed')
        expected_files=processing['protected_files']
    if current_files!=expected_files or formal!=seal['formal_config']:
        raise ValueError('Frozen scientific files or configuration changed')
    if formal['evaluation_enabled'] or formal['frozen_test_enabled'] or protocol['execution_request'].get('formal_eval_enabled') or protocol['execution_request']['frozen_test_enabled']:
        raise ValueError('Evaluation/test gate opened')
    state=read(RUN/'state.json') if (RUN/'state.json').exists() else {'complete_sources':0,'source_record_hashes':[]}
    n=state['complete_sources']
    if not 0<=n<=128:raise ValueError('Invalid source progress')
    records=[read(RUN/'sources'/(digest(sid)+'.json')) for sid in order[:n]]
    if state['source_record_hashes']!=[digest(r) for r in records]:raise ValueError('Committed source prefix differs')
    dbpath=ROOT/cfg['ledger_path'];db=sql_state(dbpath);old=sql_state(BASE/'prior_ledger.citation_fix.sqlite3')
    original=sql_state(BASE/'prior_ledger.sqlite3')
    byid={r[0]:r for r in db['calls']};meta=dict(db['meta']);views={(r[0],r[1]):r for r in db['oracle']}
    if not all(byid[r[0]]==r for r in old['calls']) or not all(meta[k]==v for k,v in old['meta']) or not all(views[(r[0],r[1])]==r for r in old['oracle']):
        raise ValueError('Historical call/meta/oracle records changed')
    if not all(byid[r[0]]==r for r in original['calls']) or not all(meta[k]==v for k,v in original['meta']) or not all(views[(r[0],r[1])]==r for r in original['oracle']):
        raise ValueError('Original127/4 baseline records changed')
    resume_origin=sql_state(BASE/'preserved_before_sara_query_fix/ledger.sqlite3') if processing else None
    if resume_origin and (not all(byid[r[0]]==r for r in resume_origin['calls']) or
            not all(meta[k]==v for k,v in resume_origin['meta']) or
            not all(views[(r[0],r[1])]==r for r in resume_origin['oracle'])):
        raise ValueError('Compatible continuation rewrote pre-repair call/meta/oracle history')
    current=[r for r in db['calls'] if r[0].startswith(RUN_ID+':')]
    if any(r[2] not in {'formal_train','formal_teacher_summary'} for r in current):raise ValueError('Unexpected formal purpose')
    E=[r for r in current if r[1]=='executor'];T=[r for r in current if r[1]=='teacher']
    if len(E)>256 or len(T)>seal['policy']['formal_teacher_max'] or max(Counter(r[4] for r in E).values(),default=0)>2:
        raise ValueError('Formal call cap exceeded')
    if max(Counter(r[0].rsplit(':',1)[0] for r in T).values(),default=0)>2:raise ValueError('Teacher per-batch cap exceeded')
    if max(Counter(r[0] for r in db['oracle']).values(),default=0)>4:raise ValueError('Combined oracle source budget exceeded')
    counts=Counter(r[1] for r in db['calls'])
    if counts['executor']>6000 or counts['teacher']>20:raise ValueError('Original global allocation exceeded')
    library=SkillLibrary(stage='formal_train');source_rows=[];raw_checks=[]
    for index,record in enumerate(records):
        sid=order[index]
        if record['source']!=sid or record['run_id']!=RUN_ID or record['binding']!=binding or record['generation_binding']!=binding or record['offline_mock'] or record['record_kind']!='fresh_formal_training' or record['generation_thinking'] is not False:
            raise ValueError('Source is not a fresh current formal record')
        if processing:
            if index<processing['preserved_sources']:
                if digest(record)!=processing['preserved_record_hashes'][index]:raise ValueError('Compatible preserved source record changed')
            elif record.get('processing_revision')!=processing_revision or record.get('processing_binding')!=processing_binding:
                raise ValueError('New source has the wrong processing revision')
        if record['library_before_hash']!=digest(library.export()):raise ValueError('Library was seeded or source order changed')
        for call in record['calls']:
            cid=f'{RUN_ID}:{sid}:{call["step"]}'
            row=byid[cid]
            if row[5]!=call['request_hash'] or row[1:3]!=('executor','formal_train') or row[4]!=sid or row[6] not in {'completed','failed'}:
                raise ValueError('Call differs from cumulative physical accounting')
            result=json.loads(row[8]);directory=RUN/'calls'/digest(cid)
            if row[6]=='completed':
                req=read(directory/'request.json');payload=req['payload']
                wire=read(directory/'wire_request.json');literal=base64.b64decode(wire['body_b64'])
                if hashlib.sha256(literal).hexdigest()!=wire['body_sha256'] or json.loads(literal)!=payload:
                    raise ValueError('Literal wire request changed')
                returned=json.loads(base64.b64decode(read(directory/'wire_response.json')['body_b64']))
                if returned['usage']!=result['usage'] or (returned['choices'][0]['message'].get('content') or '')!=result['content']:
                    raise ValueError('Literal wire response changed')
                if result['usage']['prompt_tokens']!=req['tokenization']['count']:
                    raise ValueError('Measured prompt tokens differ from the serving template')
                for key in ('model','temperature','top_p','top_k','max_tokens','seed'):
                    if payload[key]!=cfg['executor'][key]:raise ValueError('Executor generation configuration changed')
                if payload['chat_template_kwargs']!={'enable_thinking':False} or result.get('reasoning_content'):
                    raise ValueError('Thinking OFF not observed')
                if result['content']!=call['raw_content'] or result['usage']!=call['usage']:
                    raise ValueError('Raw content/usage was replaced')
                if req['tokenization']['count']+payload['max_tokens']>cfg['executor']['context_tokens']:
                    raise ValueError('Request exceeded context')
                expected=digest({'request':{'thinking':False,'payload':payload},'spec':seal_spec(db),'execution_binding':{k:binding[k] for k in ('code_hash','config_hash')}})
                if expected!=row[5]:raise ValueError('Exact wire request binding differs')
            else:
                if call['raw_content']!='':raise ValueError('Failed call was replaced with invented text')
            raw_checks.append({'id':cid,'status':row[6],'request_hash':row[5]})
        learning=record['learning'];pattern=learning.get('learned_pattern')
        if len(learning['oracle_views'])>4:raise ValueError('Source views exceed shared limit')
        if pattern:library.add(pattern,source=sid)
        analysis=record['analysis']
        source_rows.append({'index':index,'source':sid,'dataset':record['dataset'],
            'record_hash':digest(record),'calls':len(record['calls']),'task_correct':record['score']['task_correct'],
            'A_status':analysis['certificate_status'],'A_fallback':analysis.get('fallback_used',False),
            'IR_status':analysis['program_status'],'diagnostics':analysis.get('diagnostics',[]),
            'residual_units':len(analysis['residual_units']),'translation_actions':record['translation_actions'],
            'B_status':learning['status'],'B_synthesis_status':learning.get('connector_synthesis_status'),
            'B_pattern_graphs':len((pattern or {}).get('graphs',[])),
            'B_collisions':len(learning.get('refinement',{}).get('collisions',[])),
            'oracle_views':len(learning['oracle_views']),
            'reference_failures':learning.get('reference_failures',0),
            'length_truncated_calls':sum(byid[f'{RUN_ID}:{sid}:{c["step"]}'][6]=='completed' and json.loads(byid[f'{RUN_ID}:{sid}:{c["step"]}'][8]).get('finish_reason')=='length' for c in record['calls'])})
    batches=[];frozen=[]
    for batch in range(1,n//16+1):
        p=RUN/'batches'/f'B{batch}.json';b=read(p)
        if b['binding']!=binding or b['completed_sources']!=order[:batch*16] or b['source_record_hashes']!=[digest(r) for r in records[:batch*16]]:
            raise ValueError('Batch checkpoint differs')
        teacher=b['teacher_batch_record']
        if teacher['source_ids']!=order[(batch-1)*16:batch*16] or teacher['reuse_requires_matching_binding']!=binding:
            raise ValueError('Old teacher summary reused')
        ids=[r[0] for r in T if r[0].startswith(f'{RUN_ID}:teacher:B{batch}:')]
        if not 1<=len(ids)<=2:raise ValueError('Formal batch must have a new bounded teacher invocation')
        group=records[(batch-1)*16:batch*16]
        common=[{'source':r['source'],'dataset':r['dataset'],
                 'program_status':r['analysis']['program_status'],
                 'certificate_status':r['analysis']['certificate_status'],
                 'learning_status':r['learning']['status'],
                 'refinement':r['learning'].get('refinement'),
                 'pattern':r['learning'].get('learned_pattern')} for r in group]
        for cid in ids:
            req=read(RUN/'calls'/digest(cid)/'request.json')
            if req['config']!=cfg['teacher'] or req['source_ids']!=teacher['source_ids'] or req['purpose']!='formal_teacher_summary':
                raise ValueError('Teacher effective request configuration/source scope differs')
            if json.loads(req['user_prompt'])!={'common_first_16_training_records':common,'current_parameterized_library':b['library']}:
                raise ValueError('Teacher did not receive this batch of fresh records/current library')
            expected=digest({'request':req,'spec':seal_spec(db),'execution_binding':{k:binding[k] for k in ('code_hash','config_hash')}})
            if byid[cid][5]!=expected:raise ValueError('Teacher exact request binding differs')
            if byid[cid][6]=='completed' and read(RUN/'calls'/digest(cid)/'result.json')!=json.loads(byid[cid][8]):
                raise ValueError('Teacher raw result differs from ledger')
        if not set(teacher['accepted_pattern_hashes'])<={p['pattern_hash'] for p in b['library']['patterns']}:
            raise ValueError('Teacher invented a verified library pattern')
        if teacher['response']:
            response=teacher['response']
            if response['model']!='gpt-5.6-sol':raise ValueError('Teacher model differs')
            if not any(json.loads(byid[cid][8])==response for cid in ids if byid[cid][6]=='completed'):
                raise ValueError('Teacher response not in current ledger')
        batches.append({'batch':batch,'checkpoint_sha256':sha(p),'teacher_accepted':teacher['batch_record_accepted'],
            'teacher_requests':len(ids),'teacher_pending_proposals':len(teacher['pending_proposals']),
            'pattern_count':len(b['library']['patterns'])})
        if batch in (1,8):
            snap=SkillLibrary.restore(RUN/f'B{batch}.frozen.json').export()
            prefix=SkillLibrary(stage=f'formal_B{batch}')
            for rec in records[:batch*16]:
                if rec['learning'].get('learned_pattern'):prefix.add(rec['learning']['learned_pattern'],source=rec['source'])
            prefix.frozen=True
            if prefix.export()!=snap:raise ValueError('Frozen library does not match current source prefix')
            frozen.append({'checkpoint':f'B{batch}','sha256':sha(RUN/f'B{batch}.frozen.json'),'patterns':len(snap['patterns'])})
    identity=read(RUN/'process_identity.json');pid=Path('/proc')/str(identity['pid'])
    alive=pid.exists() and (pid/'stat').read_text().split()[21]==identity['start_ticks']
    if final:
        if n!=128 or len(batches)!=8 or len(frozen)!=2 or identity['status']!='complete' or alive or not (RUN/'completion.json').exists() or any(r[6]=='reserved' for r in db['calls']):
            raise ValueError('The complete build and terminal controller are not yet proven')
        if not read(RUN/'completion.json')['training_complete']:raise ValueError('Missing terminal completion')
        if {r['id'] for r in raw_checks}!={r[0] for r in E}:
            raise ValueError('A charged formal executor request is absent from source records')
        if sha(Path(seal['teacher_transport']['executable']))!=seal['teacher_transport']['executable_sha256']:
            raise ValueError('Bound teacher CLI transport changed')
    traces=[]
    if mechanisms:
        public={r['key']:r for r in read(ROOT/'data/packets/rr_v2/public_train.json')['sources']}
        grading=read(ROOT/'data/packets/rr_v2/grading_only/train.json')['sources']
        def deny(*a,**kw):raise RuntimeError('Mechanism audit cannot use network, models or subprocesses')
        with patch.object(socket.socket,'connect',deny),patch.object(socket.socket,'connect_ex',deny),patch.object(subprocess,'run',deny),patch.object(subprocess,'Popen',deny):
            for rec in records:
                traces.append({'source':rec['source'],'checks':mechanism_check(rec,public[rec['source']],grading[rec['source']],dbpath)})
        dump(OUT/'mechanism_reexecution.json',{'binding':binding,'processing_binding':processing_binding,
            'processing_revision':processing_revision,'sources':len(traces),'new_model_calls':0,'new_oracle_views':0,'traces':traces})
    usage=[]
    for row in current:
        result=json.loads(row[8]) if row[8] else {};u=result.get('usage') or result.get('invocation',{}).get('usage')
        usage.append({'id':row[0],'role':row[1],'status':row[6],'source':row[4],'usage':u,
            'elapsed_seconds':result.get('elapsed_seconds'),'finish_reason':result.get('finish_reason'),
            'incremental_api_cash_usd':result.get('incremental_api_cash_usd'),'actual_cash_invoice_available':result.get('actual_cash_invoice_available',False)})
    summary={'captured_utc':datetime.now(timezone.utc).isoformat(),'binding':binding,'processing_binding':processing_binding,
        'processing_revision':processing_revision,'compatible_preserved_sources':processing['preserved_sources'] if processing else 0,'final':final,
        'complete_sources':n,'total_sources':128,'completed_batches':len(batches),'controller_alive':alive,
        'controller_status':identity['status'],'old_call_rows_preserved':len(old['calls']),
        'old_meta_values_preserved':len(old['meta']),'old_oracle_rows_preserved':len(old['oracle']),
        'original_goal_call_rows_preserved':len(original['calls']),
        'original_goal_meta_values_preserved':len(original['meta']),
        'compatible_resume_call_rows_preserved':len(resume_origin['calls']) if resume_origin else None,
        'compatible_resume_meta_values_preserved':len(resume_origin['meta']) if resume_origin else None,
        'compatible_resume_oracle_rows_preserved':len(resume_origin['oracle']) if resume_origin else None,
        'baseline_counts':{'executor':192,'teacher':6},'failed_older_run_counts':{'executor':65,'teacher':2},
        'formal_executor_requests':len(E),'formal_teacher_requests':len(T),'cumulative_counts':dict(counts),
        'pending':sum(r[6]=='reserved' for r in db['calls']),'combined_oracle_rows':len(db['oracle']),
        'frozen_files_unchanged':True,'initial_library_empty':True,'old_completion_records_reused':False,
        'actual_raw_requests_verified':len(raw_checks),'batches':batches,'frozen_libraries':frozen,
        'A_statuses':dict(Counter(r['A_status'] for r in source_rows)),
        'B_statuses':dict(Counter(r['B_status'] for r in source_rows)),
        'B_synthesis_statuses':dict(Counter(str(r['B_synthesis_status']) for r in source_rows)),
        'training_task_correct':sum(r['task_correct'] for r in source_rows),
        'training_scores_not_formal_evaluation':True,'formal_evaluation_enabled':False,'frozen_test_enabled':False}
    dump(OUT/('final_audit.json' if final else 'live_audit.json'),summary)
    dump(OUT/'source_status.json',source_rows);dump(OUT/'request_ledger.json',usage)
    print(json.dumps(summary,ensure_ascii=False),flush=True)
    return summary


def seal_spec(db):return json.loads(dict(db['meta'])['spec'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--final',action='store_true');p.add_argument('--mechanisms',action='store_true');a=p.parse_args()
    audit(a.final,a.mechanisms)
