"""Versioned, one-source public-contract probe on the preserved physical ledger.

This is a component probe, not the complete build or a readiness decision.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_client import MethodExecutor,MethodTeacher,TEACHER_BINARY,TEACHER_SHA
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.preflight import science_files,scientific_code_binding,score_source
from legal_skill_guard.rr.source_program import compile_source,compiler_prompt,program_schema
from legal_skill_guard.rr.source_execution import assess_source,prepare_followup,accept_followup


QUESTION='Can an actual TRAIN clause compile into a compact source-scoped DAG, factual observations and independent Omega checking without native-answer delegation?'
OFFLINE_RECEIPT='reports/rr_method_runtime_20261107/offline_method_run_v2.json'


def load(root,run_id,source_id=None,library_path=None,compiler_role='executor'):
    cfg=json.loads((root/'configs/rr_v2_preflight.json').read_text())
    manifest=json.loads((root/cfg['source_manifest']).read_text())
    packet_path=root/'data/packets/rr_v2/public_train.json'
    if hashlib.sha256(packet_path.read_bytes()).hexdigest()!=manifest['packet_sha256']['public_train']:
        raise ValueError('Original public TRAIN packet changed')
    packet=json.loads(packet_path.read_text())
    if packet['split']!='train' or packet['contains_gold_or_reference_program']:
        raise ValueError('Compiler input must contain public TRAIN only')
    public={s['key']:s for s in packet['sources']}
    train=manifest['formal_train_order']
    dev=[s['key'] for bank in manifest['split']['datasets'].values() for s in bank['dev']]
    if set(train)!=set(public) or len(train)!=128:raise ValueError('Fixed TRAIN scope differs')
    # This diagnostic chooses by public size only, before reading any labels.
    if source_id is not None and source_id not in train:raise ValueError('Probe source outside original fixed TRAIN')
    source=public[source_id] if source_id else min((public[s] for s in train if public[s]['dataset']=='SARA_v2_Binary'),
               key=lambda s:(len(s['public']['rules']),train.index(s['key'])))
    teacher={**cfg['teacher'],'executable':TEACHER_BINARY}
    if hashlib.sha256(Path(TEACHER_BINARY).read_bytes()).hexdigest()!=TEACHER_SHA:
        raise ValueError('Previously verified teacher binary changed')
    library=None;library_hash=None
    if library_path:
        raw=(root/library_path).read_bytes();frozen=json.loads(raw)
        if digest(frozen['content'])!=frozen['sha256'] or not frozen['content']['frozen']:
            raise ValueError('Probe library is not the actual frozen component')
        library=frozen['content'];library_hash=hashlib.sha256(raw).hexdigest()
        prefix=set(train[:train.index(source['key'])])
        if any(not set(p['evidence_sources'])<=prefix for p in library['patterns']):
            raise ValueError('Probe cannot receive patterns learned from itself or future sources')
    config={'executor':cfg['executor'],'teacher':teacher,'data_hash':manifest['data_hash'],
            'question':QUESTION,'source_selection':'explicit original TRAIN source; no labels loaded' if source_id else 'shortest original SARA rule text; no labels loaded',
            'library':library,'library_file_sha256':library_hash,'compiler_role':compiler_role}
    stage=root/'artifacts/rr_method_runtime_20261107'/run_id
    return cfg,manifest,source,config,{'train':train,'dev':dev},stage


def compiler_record(root,origin,source,config):
    stage=root/'artifacts/rr_method_runtime_20261107'/origin
    seal=json.loads((stage/'seal.json').read_text())
    if seal['run_id']!=origin or seal['source']!=source or seal['config']['teacher']!=config['teacher']:
        raise ValueError('Paid compiler record requires identical public source and teacher')
    cfg=json.loads((root/'configs/rr_v2_preflight.json').read_text())
    with sqlite3.connect(root/cfg['ledger_path']) as db:
        row=db.execute('select role,source,status,result from calls where id=?',(origin+':compile',)).fetchone()
    if not row or row[:3]!=('teacher',source['key'],'completed'):
        raise ValueError('No completed paid compiler response exists for this source')
    response=json.loads(row[3]);program=json.loads((stage/'program.json').read_text())
    if response['value']!=program or response['source_ids']!=[source['key']]:
        raise ValueError('Saved compiler program differs from the immutable paid response')
    return seal,response,program


def paid_compiler(root,origin,source,config,system,user,schema):
    seal,response,program=compiler_record(root,origin,source,config)
    if (seal['system'],seal['user'],seal['schema'])!=(system,user,schema):
        raise ValueError('Paid compiler response requires identical public source, teacher, prompt and schema')
    return program,{'paid_call_id':origin+':compile','generation_binding':seal['binding'],
        'program_hash':digest(program),'response_sha256':response['response_sha256'],
        'source_prompt_schema_teacher_unchanged':True,'new_teacher_calls':0}


def executor_candidate(root,origin,source,config):
    stage=root/'artifacts/rr_method_runtime_20261107'/origin
    seal=json.loads((stage/'seal.json').read_text())
    if (seal['run_id']!=origin or seal['source']!=source or
            seal['config']['compiler_role']!='executor' or seal['config']['executor']!=config['executor']):
        raise ValueError('Executor repair requires its own candidate, identical public source and executor profile')
    cfg=json.loads((root/'configs/rr_v2_preflight.json').read_text())
    with sqlite3.connect('file:'+str(root/cfg['ledger_path'])+'?mode=ro',uri=True) as db:
        row=db.execute('select role,purpose,source,status,result from calls where id=?',(origin+':compile',)).fetchone()
    if not row or row[:4]!=('executor','method_train_synthesis',source['key'],'completed'):
        raise ValueError('No completed independent executor candidate exists')
    from legal_skill_guard.rr.raw_recovery import _unique_object
    response=json.loads(row[4]);program=json.loads((stage/'program.json').read_text())
    if json.loads(response['content'],object_pairs_hook=_unique_object)!=program:
        raise ValueError('Saved candidate differs from the immutable executor response')
    return seal,program,{'paid_call_id':origin+':compile','program_hash':digest(program),
        'request_hash':response['request_hash'],'generation_binding':seal['binding'],
        'teacher_candidate_used':False,'new_model_calls':0}


def prepare(root,run_id,compiler_origin=None,repair_origin=None,source_id=None,library_path=None,compiler_role='executor',executor_repair_origin=None):
    cfg,manifest,source,config,sources,stage=load(root,run_id,source_id,library_path,compiler_role)
    receipt=json.loads((root/OFFLINE_RECEIPT).read_text())
    files=science_files(root)
    if receipt['exit_code'] or not receipt['network_blocked'] or receipt['files']!=files:
        raise ValueError('Current source/version needs successful offline evidence')
    with sqlite3.connect(root/cfg['ledger_path']) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('Reconcile the existing physical request; do not duplicate it')
    auth=json.loads((root/'docs/rr_v2/method_runtime_authorization_20261107.json').read_text())
    previous=None;feedback=None;executor_origin=None
    if sum(x is not None for x in (compiler_origin,repair_origin,executor_repair_origin))>1:
        raise ValueError('Choose one exact reuse or repair origin')
    if compiler_role!='teacher' and (compiler_origin or repair_origin):
        raise ValueError('Teacher candidate/cache cannot stand in for independent executor compilation')
    if executor_repair_origin:
        if compiler_role!='executor':raise ValueError('Executor repair origin requires executor compilation')
        from legal_skill_guard.rr.source_validation import validation_feedback
        old_seal,previous,executor_origin=executor_candidate(root,executor_repair_origin,source,config)
        feedback=validation_feedback(source,previous)
    if repair_origin:_,_,previous=compiler_record(root,repair_origin,source,config)
    system,user=compiler_prompt(source,config['library'],previous_program=previous,validation_feedback=feedback)
    schema=program_schema(source,config['library'])
    if executor_origin:
        executor_origin['changed_contract_fields']=[key for key,value in
            (('system',system),('user',user),('schema',schema)) if old_seal[key]!=value]
        if not executor_origin['changed_contract_fields'] or not feedback['issues']:
            raise ValueError('A real retry requires specific offline diagnostics and a changed contract')
    origin=None
    if compiler_origin:
        _,origin=paid_compiler(root,compiler_origin,source,config,system,user,schema)
    seal={'run_id':run_id,'question':QUESTION,'files':files,'config':config,'sources':sources,
        'binding':{'code_hash':scientific_code_binding(files),'config_hash':digest(config)},
        'authorization_hash':digest(auth),'source':source,'system':system,'user':user,
        'schema':schema,'compiler_origin':origin,'repair_origin':repair_origin,'library_path':library_path,
        'executor_repair_origin':executor_origin,'validation_feedback':feedback,
        'offline_evidence_hash':digest(receipt),
        'original_model_resources_only':True,'not_a_readiness_receipt':True}
    immutable_json(stage/'seal.json',seal)
    return {'prepared':True,'stage':str(stage),'source':source['key'],'new_model_calls':0}


def paid_observation(root,source,config,payload):
    cfg=json.loads((root/'configs/rr_v2_preflight.json').read_text())
    with sqlite3.connect(root/cfg['ledger_path']) as db:
        rows=db.execute("select id,result from calls where role='executor' and source=? and status='completed' and purpose='method_primitive_observation' order by reserved_at",(source['key'],)).fetchall()
    for call_id,raw in rows:
        response=json.loads(raw);path=Path(response['artifact_directory'])
        request=json.loads((path/'request.json').read_text())
        if request['payload']!=payload:continue
        seal=json.loads((path.parent.parent/'seal.json').read_text())
        if seal['source']!=source or seal['config']['executor']!=config['executor']:
            continue
        return response,{'paid_call_id':call_id,'request_hash':response['request_hash'],
            'payload_hash':digest(payload),'new_executor_calls':0,
            'source_payload_profile_unchanged':True}
    return None,None


def execute_program(root,source,program,config,stage,executor,run_id):
    from legal_skill_guard.rr.raw_recovery import _unique_object
    compiled=compile_source(source,program,library=config['library']);observed={}
    result={'before':assess_source(compiled)}
    if result['before']['status']!='completion_stable':
        prepared=prepare_followup(compiled,compilation='answer_separating',tokenize=executor.tokenize,
            request_config=config['executor'],thinking=config['executor']['enable_thinking'],library=config['library'])
        result['followup_request']=prepared
        immutable_json(stage/'followup_request.json',prepared)
        if prepared['kind']!='no_followup':
            messages,schema=prepared['messages'],prepared['schema'];response=None
            factual=prepared['kind']=='factual_observation'
            if factual:
                response,origin=paid_observation(root,source,config,
                    executor.payload(messages=messages,thinking=config['executor']['enable_thinking'],schema=schema))
                if origin:result['observation_response_origin']=origin
            if response is None:
                response=executor.generate(run_id+(':observe' if factual else ':followup'),
                    source=source['key'],purpose='method_primitive_observation' if factual else 'method_train_synthesis',
                    messages=messages,thinking=config['executor']['enable_thinking'],schema=schema)
            parsed=json.loads(response['content'],object_pairs_hook=_unique_object)
            compiled,observed=accept_followup(compiled,prepared,parsed,library=config['library'])
            immutable_json(stage/'accepted_observations.json',observed)
            if not factual:immutable_json(stage/'followup_program.json',compiled['program'])
    result['after']=assess_source(compiled,observed)
    result.update(enforced_scope_bindings=compiled['scope_bindings'],missing_scope_sources=compiled['missing_scope_sources'],
        unused_scope_sources=compiled['unused_scope_sources'],final_program_hash=digest(compiled['program']))
    if result['after']['certificate']:
        result.update(certificate=result['after']['certificate'],execution=result['after']['execution'])
    return result


def run(root,run_id):
    stage=root/'artifacts/rr_method_runtime_20261107'/run_id
    seal=json.loads((stage/'seal.json').read_text())
    cfg,manifest,source,config,sources,stage=load(root,run_id,seal['source']['key'],seal['library_path'],seal['config']['compiler_role'])
    # Source selection is already sealed; an explicit source ID on resume is
    # the same original public source, not a changed scientific selection.
    config['source_selection']=seal['config']['source_selection']
    if science_files(root)!=seal['files'] or seal['source']!=source or seal['config']!=config:
        raise ValueError('Frozen probe source/configuration changed')
    ledger=MethodLedger(root/cfg['ledger_path'],run_id=run_id,binding=seal['binding'],sources=sources,
        authorization_hash=seal['authorization_hash'],question=QUESTION)
    teacher=MethodTeacher(ledger,stage,config['teacher'])
    executor=MethodExecutor(ledger,stage,config['executor'])
    result={'run_id':run_id,'source':source['key'],'status':'in_progress','full_goal_complete':False,
            'binding':seal['binding'],'oracle_calls':0,'test_labels_read':False,'compiler_role':config['compiler_role']}
    try:
        if seal['compiler_origin']:
            origin=seal['compiler_origin']['paid_call_id'].removesuffix(':compile')
            program,result['compiler_response_origin']=paid_compiler(root,origin,source,config,
                seal['system'],seal['user'],seal['schema'])
            if result['compiler_response_origin']!=seal['compiler_origin']:
                raise ValueError('Paid component provenance changed')
        elif config['compiler_role']=='teacher':
            response=teacher.summarize(run_id+':compile',source_ids=[source['key']],
                system_prompt=seal['system'],user_prompt=seal['user'],output_schema=seal['schema'])
            program=response['value']
        else:
            from legal_skill_guard.rr.raw_recovery import _unique_object
            response=executor.generate(run_id+':compile',source=source['key'],purpose='method_train_synthesis',
                messages=[{'role':'system','content':seal['system']},{'role':'user','content':seal['user']}],
                thinking=config['executor']['enable_thinking'],schema=seal['schema'])
            program=json.loads(response['content'],object_pairs_hook=_unique_object)
        immutable_json(stage/'program.json',program)
        result.update(execute_program(root,source,program,config,stage,executor,run_id))
        grade_path=root/'data/packets/rr_v2/grading_only/train.json'
        if hashlib.sha256(grade_path.read_bytes()).hexdigest()!=manifest['packet_sha256']['grading_train']:
            raise ValueError('Original TRAIN grading packet changed')
        grade=json.loads(grade_path.read_text())['sources'][source['key']]
        result['TRAIN_score']=score_source(source,{'answer':result['after']['answer']},grade)
        result['status']='component_probe_completed'
    except Exception as exc:
        result.update(status='component_probe_unresolved',error_type=type(exc).__name__,error=str(exc))
        if hasattr(exc,'diagnostics'):result['diagnostics']=exc.diagnostics
        if hasattr(exc,'path'):result['field_path']=list(exc.path)
    result['bound_files_unchanged']=science_files(root)==seal['files']
    book=ledger.export()
    result['ledger_totals']={k:book[k] for k in ('executor_used','teacher_used')}
    result['new_requests']=[r for r in book['calls'] if r['id'].startswith(run_id+':')]
    immutable_json(stage/'result.json',result)
    immutable_json(root/'reports/rr_method_runtime_20261107'/('source_probe_'+run_id+'.json'),result)
    return {k:result[k] for k in ('status','source','ledger_totals','full_goal_complete')}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['prepare','run'])
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--compiler-origin')
    parser.add_argument('--repair-origin')
    parser.add_argument('--executor-repair-origin')
    parser.add_argument('--source-id')
    parser.add_argument('--library-path')
    parser.add_argument('--compiler-role',choices=['executor','teacher'],default='executor')
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    print(json.dumps(prepare(root,args.run_id,args.compiler_origin,args.repair_origin,args.source_id,args.library_path,args.compiler_role,args.executor_repair_origin) if args.action=='prepare' else run(root,args.run_id),ensure_ascii=False))


if __name__=='__main__':main()
