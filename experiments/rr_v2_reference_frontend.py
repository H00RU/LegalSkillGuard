"""TRAIN-only representative validation of the reference-based compiler route.

No new Goal, dataset, model configuration, teacher request or TEST entry point.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3
from jsonschema import ValidationError

from experiments.rr_v2_source_probe import load
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_client import MethodExecutor,MethodTeacher
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.method_run import load_executor_lock
from legal_skill_guard.rr.model_horn import assess_model_horn
from legal_skill_guard.rr.atom_frontend import atom_prompt,atom_schema,decode_atom_response
from legal_skill_guard.rr.source_inference import _decode
from legal_skill_guard.rr.preflight import science_files,scientific_code_binding,score_source
from legal_skill_guard.rr.strict_contract import obj
from legal_skill_guard.rr.client import WireError
from legal_skill_guard.inference.codex_cli_client import CodexInvocationError

OFFLINE='reports/rr_method_runtime_20261107/offline_reference_frontend_v20_20261108.json'
QUESTION='Do source-aligned model atoms with source-preserved connective structure resolve the observed Horn head/guard errors while preserving full source semantics under locked OFF?'
TEACHER_QUESTION='Can the fixed teacher produce a complete, independently source-checked Horn compiler template on earlier original TRAIN through the short program interface?'


def prepare(root,run_id,source_id,library_path,role='executor'):
    cfg,manifest,source,config,sources,stage=load(root,run_id,source_id,library_path,role)
    if source['dataset']!='ProofWriter_OWA_depth5':raise ValueError('The first reference frontend validation is logic-only')
    load_executor_lock(root,config['executor'])
    question=TEACHER_QUESTION if role=='teacher' else QUESTION
    config.update(question=question,frontend='source_aligned_atoms_v1',
        common_frontend_available_to_all_arms=True,selected_profile='teacher_material' if role=='teacher' else 'M11',
        library_role='preserved earlier-TRAIN library control, not fresh library learning')
    from legal_skill_guard.rr.compiler_templates import validate_template
    prefix=set(sources['train'][:sources['train'].index(source_id)])
    public={s['key']:s for s in json.loads((root/'data/packets/rr_v2/public_train.json').read_text())['sources']}
    for template in (config['library'] or {}).get('compiler_templates',[]):
        validate_template(template);previous=template['source']
        if previous['key'] not in prefix or previous!=public[previous['key']]:
            raise ValueError('Compiler templates must be exact strictly earlier original TRAIN sources')
    files=science_files(root);offline=json.loads((root/OFFLINE).read_text())
    if files!=offline['files'] or offline['exit_code'] or not offline['network_blocked']:
        raise ValueError('This actual frontend needs matching passed offline evidence')
    with sqlite3.connect('file:'+str(root/cfg['ledger_path'])+'?mode=ro',uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():raise ValueError('Reconcile the actual pending request')
        rows=db.execute("select id,result from calls where source=? and id like ? order by reserved_at",
            (source_id,'method_runtime_ast_v1_20261107:build:%')).fetchall()
    baseline=[]
    for cid,encoded in rows:
        value=json.loads(encoded);baseline.append({'call_id':cid,'finish_reason':value.get('finish_reason'),
            'usage':value.get('usage'),'elapsed_seconds':value.get('elapsed_seconds'),
            'raw_content_sha256':hashlib.sha256(value.get('content','').encode()).hexdigest()})
    messages=atom_prompt(source,config['library']);schema=atom_schema(source)
    client=MethodExecutor(None,stage,config['executor'])
    tokens=client.tokenize(messages,thinking=False)['count']
    if tokens+config['executor']['max_tokens']>config['executor']['context_tokens']:
        raise ValueError('Full original public input does not fit; no truncation')
    authorization=json.loads((root/'docs/rr_v2/method_runtime_authorization_20261107.json').read_text())
    seal={'run_id':run_id,'question':question,'files':files,'source':source,'sources':sources,
        'config':config,'library_path':library_path,'messages':messages,'schema':schema,'input_tokens':tokens,
        'schema_order_sha256':hashlib.sha256(json.dumps(schema,ensure_ascii=False).encode()).hexdigest(),
        'binding':{'code_hash':scientific_code_binding(files),'config_hash':digest(config)},
        'source_manifest':cfg['source_manifest'],'source_manifest_hash':digest(manifest),
        'ledger_path':cfg['ledger_path'],'authorization_hash':digest(authorization),
        'offline_receipt_hash':digest(offline),'baseline_paid_responses':baseline,
        'new_baseline_model_calls':0,'original_parsing_calls_per_source':1 if role=='teacher' else 2,
        'TEST_authorized':False,'full_goal_complete':False}
    immutable_json(stage/'seal.json',seal)
    return {'prepared':True,'source':source_id,'input_tokens':tokens,'prior_responses':len(baseline),'new_model_calls':0}


def run(root,run_id):
    stage=root/'artifacts/rr_method_runtime_20261107'/run_id
    seal=json.loads((stage/'seal.json').read_text())
    if science_files(root)!=seal['files']:raise ValueError('Frozen frontend version changed')
    role=seal['config']['compiler_role']
    cfg,manifest,source,current,sources,_=load(root,run_id,seal['source']['key'],seal['library_path'],role)
    if source!=seal['source'] or digest(manifest)!=seal['source_manifest_hash']:
        raise ValueError('Original source/data binding changed')
    if current['executor']!=seal['config']['executor'] or current['library']!=seal['config']['library']:
        raise ValueError('Frozen model or earlier-TRAIN library changed')
    schema=atom_schema(source)
    if schema!=seal['schema'] or hashlib.sha256(json.dumps(schema,ensure_ascii=False).encode()).hexdigest()!=seal['schema_order_sha256']:
        raise ValueError('Ordered source-aligned schema changed')
    path=stage/'result.json'
    if path.exists():return json.loads(path.read_text())
    ledger=MethodLedger(root/seal['ledger_path'],run_id=run_id,binding=seal['binding'],sources=sources,
        authorization_hash=seal['authorization_hash'],question=seal['question'])
    executor=MethodExecutor(ledger,stage,seal['config']['executor'])
    teacher=MethodTeacher(ledger,stage,seal['config']['teacher']) if role=='teacher' else None
    attempts=[];feedback=None;result=None;program=None
    for step in range(seal['original_parsing_calls_per_source']):
        if science_files(root)!=seal['files']:raise ValueError('Frozen frontend version changed')
        messages=atom_prompt(source,seal['config']['library'],feedback=feedback)
        request_record={'messages':messages,'schema':schema,'compiler_role':role,'executor_enable_thinking':False}
        if role=='teacher':request_record['teacher_reasoning_effort']=seal['config']['teacher']['reasoning_effort']
        immutable_json(stage/('request'+str(step)+'.json'),request_record)
        call_id=run_id+(':compile' if role=='teacher' else ':parse:'+str(step))
        try:
            if role=='teacher':
                paid=teacher.summarize(call_id,source_ids=[source['key']],system_prompt=messages[0]['content'],
                    user_prompt=messages[1]['content'],output_schema=schema)
                with sqlite3.connect('file:'+str(root/seal['ledger_path'])+'?mode=ro',uri=True) as db:
                    request_hash=db.execute('select request_hash from calls where id=?',(call_id,)).fetchone()[0]
                response={'content':json.dumps(paid['value'],ensure_ascii=False),'request_hash':request_hash,
                    'finish_reason':'teacher_structured_success_not_provider_finish_reason',
                    'usage':paid['invocation'].get('usage'), 'elapsed_seconds':paid['elapsed_seconds'],
                    'cache_hit':paid.get('cache_hit',False)}
            else:
                response=executor.generate(call_id,source=source['key'],purpose='method_train_synthesis',
                    messages=messages,thinking=False,schema=schema)
        except (WireError,CodexInvocationError) as exc:
            attempts.append({'step':step,'call_id':call_id,'transport_error_type':type(exc).__name__,
                'transport_error':str(exc),'physical_ledger_and_client_failure_artifact_preserved':True})
            break
        item={'step':step,'request_hash':response['request_hash'],'finish_reason':response['finish_reason'],
            'usage':response['usage'],'elapsed_seconds':response['elapsed_seconds'],
            'cache_hit':response['cache_hit'],'raw_content_sha256':hashlib.sha256(response['content'].encode()).hexdigest()}
        try:
            parsed,program_code=decode_atom_response(source,_decode(response['content']));program=parsed.export()
            result=assess_model_horn(parsed,seal['config']['library'],interface='ordinary_IO_local_binding_repair' if role=='teacher' else 'collision_refined')
            item.update(program=program,result=result)
            if result['certificate_status']=='completion_stable':
                attempts.append(item);break
            if result['certificate_status']=='unsupported_no_certificate' and not program['missing_units']:
                # A missing library/backend component is not repaired by
                # regenerating an already source-correct model program.
                attempts.append(item);break
            feedback={'missing_source_units':program['missing_units'],
                'previous_complete_program':response['content'],
                'instruction':'Translate the missing source units; keep every correct source formula and do not invent an answer.'}
        except (ValueError,TypeError,KeyError,ValidationError) as exc:
            item.update(error_type=type(exc).__name__,error=str(exc),diagnostics=getattr(exc,'diagnostics',None))
            feedback={'error':item['error'],'diagnostics':item['diagnostics'],
                'instruction':'Repair this concrete source/formalization error, preserving every guard and variable sharing; no native answer.'}
            result=None
        attempts.append(item)
    output={'run_id':run_id,'source':source['key'],'source_hash':source['content_hash'],'binding':seal['binding'],
        'compiler_role':role,'independent_executor_compilation':role=='executor',
        'frontend':'source_aligned_atoms_v1','attempts':attempts,'program':program,'result':result,
        'original_model_config_unchanged':True,'executor_enable_thinking':False,
        'baseline_paid_responses':seal['baseline_paid_responses'],'new_baseline_model_calls':0,
        'old_library_control_not_fresh_learning':True,'oracle_calls':0,'TEST_labels_read':False,
        'full_goal_complete':False,'status':'component_unresolved'}
    if result and result['certificate_status']=='completion_stable' and role=='teacher':
        from legal_skill_guard.rr.compiler_templates import make_template
        template=make_template(source,program_code,{'role':'teacher','call_id':call_id,
            'request_hash':response['request_hash'],'model':paid['model'],
            'result_file_sha256':hashlib.sha256((stage/'calls'/digest(call_id)/'result.json').read_bytes()).hexdigest()})
        immutable_json(stage/'compiler_template.json',template)
        output.update(status='teacher_training_template_validated',compiler_template_hash=template['template_hash'],
            fresh_executor_core_success=False,TRAIN_labels_read=False)
    elif result and result['certificate_status']=='completion_stable':
        grade_path=root/'data/packets/rr_v2/grading_only/train.json'
        if hashlib.sha256(grade_path.read_bytes()).hexdigest()!=manifest['packet_sha256']['grading_train']:
            raise ValueError('Original TRAIN grading packet changed')
        grade=json.loads(grade_path.read_text())['sources'][source['key']]
        output['TRAIN_score']=score_source(source,result,grade)
        output['status']='component_executed_and_scored'
    output['bound_files_unchanged']=science_files(root)==seal['files']
    book=ledger.export();output['ledger_totals']={k:book[k] for k in ('executor_used','teacher_used')}
    immutable_json(path,output)
    immutable_json(root/'reports/rr_method_runtime_20261107'/('reference_frontend_'+run_id+'.json'),output)
    return {k:output[k] for k in ('run_id','source','status','ledger_totals','full_goal_complete')}


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run']);p.add_argument('--run-id',required=True)
    p.add_argument('--source-id');p.add_argument('--library-path');p.add_argument('--role',choices=['executor','teacher'],default='executor');args=p.parse_args();root=Path(__file__).resolve().parents[1]
    if args.action=='prepare':value=prepare(root,args.run_id,args.source_id,args.library_path,args.role)
    else:
        stage=root/'artifacts/rr_method_runtime_20261107'/args.run_id
        with (stage/'component.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);value=run(root,args.run_id)
    print(json.dumps(value,ensure_ascii=False))


if __name__=='__main__':main()
